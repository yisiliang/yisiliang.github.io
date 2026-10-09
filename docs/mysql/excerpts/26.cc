/**
  Applies the given event and advances the relay log position.

  This is needed by the sql thread to execute events from the binlog,
  and by clients executing BINLOG statements.  Conceptually, this
  function does:

  @code
    ev->apply_event(rli);
    ev->update_pos(rli);
  @endcode

  It also does the following maintenance:

   - Initializes the thread's server_id and time; and the event's
     thread.

   - If !rli->belongs_to_client() (i.e., if it belongs to the slave
     sql thread instead of being used for executing BINLOG
     statements), it does the following things: (1) skips events if it
     is needed according to the server id or slave_skip_counter; (2)
     unlocks rli->data_lock; (3) sleeps if required by 'CHANGE REPLICATION
  SOURCE TO SOURCE_DELAY=X'; (4) maintains the running state of the sql thread
  (rli->thread_state).

   - Reports errors as needed.

  @param ptr_ev a pointer to a reference to the event to apply.

  @param thd The client thread that executes the event (i.e., the
  slave sql thread if called from a replication slave, or the client
  thread if called to execute a BINLOG statement).

  @param rli The relay log info (i.e., the slave's rli if called from
  a replication slave, or the client's thd->rli_fake if called to
  execute a BINLOG statement).

  @note MTS can store NULL to @c ptr_ev location to indicate
        the event is taken over by a Worker.

  @retval SLAVE_APPLY_EVENT_AND_UPDATE_POS_OK
          OK.

  @retval SLAVE_APPLY_EVENT_AND_UPDATE_POS_APPLY_ERROR
          Error calling ev->apply_event().

  @retval SLAVE_APPLY_EVENT_AND_UPDATE_POS_UPDATE_POS_ERROR
          No error calling ev->apply_event(), but error calling
          ev->update_pos().

  @retval SLAVE_APPLY_EVENT_AND_UPDATE_POS_APPEND_JOB_ERROR
          append_item_to_jobs() failed, thread was killed while waiting
          for successful enqueue on worker.
*/
static enum enum_slave_apply_event_and_update_pos_retval
apply_event_and_update_pos(Log_event **ptr_ev, THD *thd, Relay_log_info *rli) {
  int exec_res = 0;
  bool skip_event = false;
  Log_event *ev = *ptr_ev;
  Log_event::enum_skip_reason reason = Log_event::EVENT_SKIP_NOT;

  DBUG_TRACE;

  DBUG_PRINT("exec_event",
             ("%s(type_code: %d; server_id: %d)", ev->get_type_str(),
              ev->get_type_code(), ev->server_id));
  DBUG_PRINT("info",
             ("thd->options: %s%s; rli->last_event_start_time: %lu",
              FLAGSTR(thd->variables.option_bits, OPTION_NOT_AUTOCOMMIT),
              FLAGSTR(thd->variables.option_bits, OPTION_BEGIN),
              (ulong)rli->last_event_start_time));

  /*
    Execute the event to change the database and update the binary
    log coordinates, but first we set some data that is needed for
    the thread.

    The event will be executed unless it is supposed to be skipped.

    Queries originating from this server must be skipped.  Low-level
    events (Format_description_log_event, Rotate_log_event,
    Stop_log_event) from this server must also be skipped. But for
    those we don't want to modify 'group_master_log_pos', because
    these events did not exist on the master.
    Format_description_log_event is not completely skipped.

    Skip queries specified by the user in 'slave_skip_counter'.  We
    can't however skip events that has something to do with the log
    files themselves.

    Filtering on own server id is extremely important, to ignore
    execution of events created by the creation/rotation of the relay
    log (remember that now the relay log starts with its Format_desc,
    has a Rotate etc).
  */
  /*
     Set the unmasked and actual server ids from the event
   */
  thd->server_id = ev->server_id;  // use the original server id for logging
  thd->unmasked_server_id = ev->common_header->unmasked_server_id;
  thd->set_time();  // time the query
  thd->lex->set_current_query_block(nullptr);
  if (!ev->common_header->when.tv_sec)
    my_micro_time_to_timeval(my_micro_time(), &ev->common_header->when);
  ev->thd = thd;  // because up to this point, ev->thd == 0

  if (!(rli->is_mts_recovery() &&
        bitmap_is_set(&rli->recovery_groups, rli->mts_recovery_index))) {
    reason = ev->shall_skip(rli);
  }
#ifndef NDEBUG
  if (rli->is_mts_recovery()) {
    DBUG_PRINT("mta",
               ("Mta is recovering %d, number of bits set %d, "
                "bitmap is set %d, index %lu.\n",
                rli->is_mts_recovery(), bitmap_bits_set(&rli->recovery_groups),
                bitmap_is_set(&rli->recovery_groups, rli->mts_recovery_index),
                rli->mts_recovery_index));
  }
#endif
  if (reason == Log_event::EVENT_SKIP_COUNT) {
    --rli->slave_skip_counter;
    skip_event = true;
  }
  set_timespec_nsec(&rli->ts_exec[0], 0);
  rli->stats_read_time += diff_timespec(&rli->ts_exec[0], &rli->ts_exec[1]);

  if (reason == Log_event::EVENT_SKIP_NOT) {
    // Sleeps if needed, and unlocks rli->data_lock.
    if (sql_delay_event(ev, thd, rli))
      return SLAVE_APPLY_EVENT_AND_UPDATE_POS_OK;

    // Setting positions for STA. Worker positions are set on
    // slave_worker_exec_job_group
    rli->set_group_source_log_start_end_pos(ev);
    exec_res = ev->apply_event(rli);

    DBUG_EXECUTE_IF("simulate_stop_when_mta_in_group",
                    if (rli->mts_group_status == Relay_log_info::MTS_IN_GROUP &&
                        rli->curr_group_seen_begin)
                        DBUG_SET("+d,stop_when_mta_in_group"););

    if (!exec_res && (ev->worker != rli)) {
      if (ev->worker) {
        Slave_job_item item = {ev, rli->get_event_relay_log_number(),
                               rli->get_event_start_pos()};
        Slave_job_item *job_item = &item;
        Slave_worker *w = (Slave_worker *)ev->worker;
        // specially marked group typically with OVER_MAX_DBS_IN_EVENT_MTS db:s
        bool need_sync = ev->is_mts_group_isolated();

        // all events except BEGIN-query must be marked with a non-NULL Worker
        assert(((Slave_worker *)ev->worker) == rli->last_assigned_worker);

        DBUG_PRINT("Log_event::apply_event:",
                   ("-> job item data %p to W_%lu", job_item->data, w->id));

        // Reset mts in-group state
        if (rli->mts_group_status == Relay_log_info::MTS_END_GROUP) {
          // CGAP cleanup
          rli->curr_group_assigned_parts.clear();
          // reset the B-group and Gtid-group marker
          rli->curr_group_seen_begin = rli->curr_group_seen_gtid = false;
          rli->last_assigned_worker = nullptr;
        }
        /*
           Storing GAQ index of the group that the event belongs to
           in the event. Deferred events are handled similarly below.
        */
        ev->mts_group_idx = rli->gaq->assigned_group_index;

        bool append_item_to_jobs_error = false;
        if (rli->curr_group_da.size() > 0) {
          /*
            the current event sorted out which partition the current group
            belongs to. It's time now to processed deferred array events.
          */
          for (uint i = 0; i < rli->curr_group_da.size(); i++) {
            Slave_job_item da_item = rli->curr_group_da[i];
            DBUG_PRINT("mta", ("Assigning job %llu to worker %lu",
                               (da_item.data)->common_header->log_pos, w->id));
            da_item.data->mts_group_idx =
                rli->gaq->assigned_group_index;  // similarly to above
            if (!append_item_to_jobs_error)
              append_item_to_jobs_error = append_item_to_jobs(&da_item, w, rli);
            if (append_item_to_jobs_error) delete da_item.data;
          }
          rli->curr_group_da.clear();
        }
        if (append_item_to_jobs_error)
          return SLAVE_APPLY_EVENT_AND_UPDATE_POS_APPEND_JOB_ERROR;

        DBUG_PRINT("mta", ("Assigning job %llu to worker %lu\n",
                           job_item->data->common_header->log_pos, w->id));

        /* Notice `ev' instance can be destroyed after `append()' */
        if (append_item_to_jobs(job_item, w, rli))
          return SLAVE_APPLY_EVENT_AND_UPDATE_POS_APPEND_JOB_ERROR;
        if (need_sync) {
          /*
            combination of over-max db:s and end of the current group
            forces to wait for the assigned groups completion by assigned
            to the event worker.
            Indeed MTS group status could be safely set to MTS_NOT_IN_GROUP
            after wait_() returns.
            No need to know a possible error out of synchronization call.
          */
          (void)rli->current_mts_submode->wait_for_workers_to_finish(rli);
        }
      }
      *ptr_ev = nullptr;  // announcing the event is passed to w-worker

      if (rli->is_parallel_exec() &&
          rli->mts_online_stat_curr > mts_online_stat_count) {
        time_t my_now = time(nullptr);

        if (((my_now - rli->mts_last_online_stat) >= mts_online_stat_period) ||
            DBUG_EVALUATE_IF("simulate_log_err_ER_RPL_MTA_STATISTICS", 1, 0)) {
          LogErr(INFORMATION_LEVEL, ER_RPL_MTA_STATISTICS,
                 rli->get_for_channel_str(),
                 static_cast<unsigned long>(my_now - rli->mts_last_online_stat),
                 rli->mts_events_assigned, rli->mts_wq_overrun_cnt.load(),
                 rli->mts_wq_overfill_cnt, rli->wq_size_waits_cnt,
                 rli->mts_total_wait_overlap.load(),
                 rli->mts_wq_no_underrun_cnt, rli->mts_total_wait_worker_avail);
          rli->mts_last_online_stat = my_now;
        }

        rli->mts_online_stat_curr = 0;
      }
    }
  } else
    mysql_mutex_unlock(&rli->data_lock);

  set_timespec_nsec(&rli->ts_exec[1], 0);
  rli->stats_exec_time += diff_timespec(&rli->ts_exec[1], &rli->ts_exec[0]);

  DBUG_PRINT("info", ("apply_event error = %d", exec_res));
  if (exec_res == 0) {
    /*
      Positions are not updated here when an XID is processed. To make
      a slave crash-safe, positions must be updated while processing a
      XID event and as such do not need to be updated here again.

      However, if the event needs to be skipped, this means that it
      will not be processed and then positions need to be updated here.

      DDL:s that are not yet committed, as indicated by
      @c has_ddl_committed flag, visit the block.

      See sql/rpl_rli.h for further details.
    */
    int error = 0;
    if (*ptr_ev &&
        ((ev->get_type_code() != mysql::binlog::event::XID_EVENT &&
          !is_committed_ddl(*ptr_ev)) ||
         skip_event ||
         (rli->is_mts_recovery() && !is_any_gtid_event(ev) &&
          (ev->ends_group() || !rli->mts_recovery_group_seen_begin) &&
          bitmap_is_set(&rli->recovery_groups, rli->mts_recovery_index)))) {
#ifndef NDEBUG
      /*
        This only prints information to the debug trace.

        TODO: Print an informational message to the error log?
      */
      static const char *const explain[] = {
          // EVENT_SKIP_NOT,
          "not skipped",
          // EVENT_SKIP_IGNORE,
          "skipped because event should be ignored",
          // EVENT_SKIP_COUNT
          "skipped because event skip counter was non-zero"};
      DBUG_PRINT("info",
                 ("OPTION_BEGIN: %d; IN_STMT: %d",
                  static_cast<bool>(thd->variables.option_bits & OPTION_BEGIN),
                  rli->get_flag(Relay_log_info::IN_STMT)));
      DBUG_PRINT("skip_event",
                 ("%s event was %s", ev->get_type_str(), explain[reason]));
#endif

      error = ev->update_pos(rli);
      /*
        Slave skips an event if the slave_skip_counter is greater than zero.
        We have to free thd's mem_root here after we update the positions
        in the repository table if the event is a skipped event.
        Otherwise, imagine a situation where slave_skip_counter is big number
        and slave is skipping the events and updating the repository.
        All the memory used while these operations are going on is never
        freed unless slave starts executing the events (after slave_skip_counter
        becomes zero).

        Hence we free thd's mem_root here if it is a skipped event.
        (freeing mem_root generally happens from Query_log_event::do_apply_event
        or Rows_log_event::do_apply_event when they find the end of
        the group event).
      */
      if (skip_event) thd->mem_root->ClearForReuse();

#ifndef NDEBUG
      DBUG_PRINT("info", ("update_pos error = %d", error));
      if (!rli->belongs_to_client()) {
        char buf[22];
        DBUG_PRINT("info",
                   ("group %s %s", llstr(rli->get_group_relay_log_pos(), buf),
                    rli->get_group_relay_log_name()));
        DBUG_PRINT("info",
                   ("event %s %s", llstr(rli->get_event_relay_log_pos(), buf),
                    rli->get_event_relay_log_name()));
      }
#endif
    } else {
      /*
        INTVAR_EVENT, RAND_EVENT, USER_VAR_EVENT and ROWS_QUERY_LOG_EVENT are
        deferred event. It means ev->worker is NULL.
      */
      assert(*ptr_ev == ev || rli->is_parallel_exec() ||
             (!ev->worker &&
              (ev->get_type_code() == mysql::binlog::event::INTVAR_EVENT ||
               ev->get_type_code() == mysql::binlog::event::RAND_EVENT ||
               ev->get_type_code() == mysql::binlog::event::USER_VAR_EVENT ||
               ev->get_type_code() ==
                   mysql::binlog::event::ROWS_QUERY_LOG_EVENT)));

      rli->inc_event_relay_log_pos();
    }

    if (!error && rli->is_mts_recovery() &&
        ev->get_type_code() != mysql::binlog::event::ROTATE_EVENT &&
        ev->get_type_code() != mysql::binlog::event::FORMAT_DESCRIPTION_EVENT &&
        ev->get_type_code() != mysql::binlog::event::PREVIOUS_GTIDS_LOG_EVENT) {
      if (ev->starts_group()) {
        rli->mts_recovery_group_seen_begin = true;
      } else if ((ev->ends_group() || !rli->mts_recovery_group_seen_begin) &&
                 !is_any_gtid_event(ev)) {
        rli->mts_recovery_index++;
        if (--rli->mts_recovery_group_cnt == 0) {
          rli->mts_recovery_index = 0;
          LogErr(INFORMATION_LEVEL, ER_RPL_MTA_RECOVERY_COMPLETE,
                 rli->get_for_channel_str(), rli->get_group_relay_log_name(),
                 rli->get_group_relay_log_pos(),
                 rli->get_group_master_log_name(),
                 rli->get_group_master_log_pos());
          /*
             Few tests wait for UNTIL_SQL_AFTER_MTS_GAPS completion.
             Due to existing convention the status won't change
             prior to slave restarts.
             So making of UNTIL_SQL_AFTER_MTS_GAPS completion is done here,
             and only in the debug build to make the test to catch the change
             despite a faulty design of UNTIL checking before execution.
          */
          if (rli->until_condition ==
              Relay_log_info::UNTIL_SQL_AFTER_MTS_GAPS) {
            rli->until_condition = Relay_log_info::UNTIL_DONE;
          }
          // reset the Worker tables to remove last slave session time info
          if ((error = rli->mts_finalize_recovery())) {
            (void)Rpl_info_factory::reset_workers(rli);
          }
        }
        rli->mts_recovery_group_seen_begin = false;
        if (!error)
          error = rli->flush_info(Relay_log_info::RLI_FLUSH_IGNORE_SYNC_OPT);
      }
    }

    if (error) {
      /*
        The update should not fail, so print an error message and
        return an error code.

        TODO: Replace this with a decent error message when merged
        with BUG#24954 (which adds several new error message).
      */
      char buf[22];
      rli->report(ERROR_LEVEL, ER_UNKNOWN_ERROR,
                  "It was not possible to update the positions"
                  " of the relay log information: the replica may"
                  " be in an inconsistent state."
                  " Stopped in %s position %s",
                  rli->get_group_relay_log_name(),
                  llstr(rli->get_group_relay_log_pos(), buf));
      return SLAVE_APPLY_EVENT_AND_UPDATE_POS_UPDATE_POS_ERROR;
    }
  }

  return exec_res ? SLAVE_APPLY_EVENT_AND_UPDATE_POS_APPLY_ERROR
                  : SLAVE_APPLY_EVENT_AND_UPDATE_POS_OK;
}
