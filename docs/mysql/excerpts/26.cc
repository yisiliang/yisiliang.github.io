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
