/**
  @param[in] thd                       Thread handle.
  @param[in] all                       Session transaction if true, statement
                                       otherwise.
  @param[in] ignore_global_read_lock   Allow commit to complete even if a
                                       global read lock is active. This can be
                                       used to allow changes to internal tables
                                       (e.g. slave status tables).

  @retval
    0   ok
  @retval
    1   transaction was rolled back
  @retval
    2   error during commit, data may be inconsistent

  @todo
    Since we don't support nested statement transactions in 5.0,
    we can't commit or rollback stmt transactions while we are inside
    stored functions or triggers. So we simply do nothing now.
    TODO: This should be fixed in later ( >= 5.1) releases.
*/

int ha_commit_trans(THD *thd, bool all, bool ignore_global_read_lock) {
  int error = 0;
  THD_STAGE_INFO(thd, stage_waiting_for_handler_commit);
  bool run_slave_post_commit = false;
  bool need_clear_owned_gtid = false;
  /*
    Save transaction owned gtid into table before transaction prepare
    if binlog is disabled, or binlog is enabled and log_replica_updates
    is disabled with slave SQL thread or slave worker thread.
  */
  std::tie(error, need_clear_owned_gtid) = commit_owned_gtids(thd, all);

  /*
    'all' means that this is either an explicit commit issued by
    user, or an implicit commit issued by a DDL.
  */
  Transaction_ctx *trn_ctx = thd->get_transaction();
  const Transaction_ctx::enum_trx_scope trx_scope =
      all ? Transaction_ctx::SESSION : Transaction_ctx::STMT;

  /*
    "real" is a nick name for a transaction for which a commit will
    make persistent changes. E.g. a 'stmt' transaction inside a 'all'
    transaction is not 'real': even though it's possible to commit it,
    the changes are not durable as they might be rolled back if the
    enclosing 'all' transaction is rolled back.
  */
  const bool is_real_trans =
      all || !trn_ctx->is_active(Transaction_ctx::SESSION);
#ifndef NDEBUG
  bool transaction_to_skip = false;
  DBUG_EXECUTE_IF("replica_crash_after_commit", {
    transaction_to_skip = is_already_logged_transaction(thd);
  });
#endif  // NDEBUG
  auto ha_info = trn_ctx->ha_trx_info(trx_scope);
  XID_STATE *xid_state = trn_ctx->xid_state();

  DBUG_TRACE;

  DBUG_PRINT("info", ("all=%d thd->in_sub_stmt=%d ha_info=%p is_real_trans=%d",
                      all, thd->in_sub_stmt, ha_info.head(), is_real_trans));
  /*
    We must not commit the normal transaction if a statement
    transaction is pending. Otherwise statement transaction
    flags will not get propagated to its normal transaction's
    counterpart.
  */
  assert(!trn_ctx->is_active(Transaction_ctx::STMT) || !all);

  DBUG_EXECUTE_IF("pre_commit_error", {
    error = true;
    my_error(ER_UNKNOWN_ERROR, MYF(0));
  });

  /*
    When atomic DDL is executed on the slave, we would like to
    to update slave applier state as part of DDL's transaction.
    Call Relay_log_info::pre_commit() hook to do this before DDL
    gets committed in the following block.
    Failed atomic DDL statements should've been marked as executed/committed
    during statement rollback, though some like GRANT may continue until
    this point.
    When applying a DDL statement on a slave and the statement is filtered
    out by a table filter, we report an error "ER_REPLICA_IGNORED_TABLE" to
    warn slave applier thread. We need to save the DDL statement's gtid
    into mysql.gtid_executed system table if the binary log is disabled
    on the slave and gtids are enabled.
  */
  if (is_real_trans && is_atomic_ddl_commit_on_slave(thd) &&
      (!thd->is_error() ||
       (thd->is_operating_gtid_table_implicitly &&
        thd->get_stmt_da()->mysql_errno() == ER_REPLICA_IGNORED_TABLE))) {
    run_slave_post_commit = true;
    error = error || thd->rli_slave->pre_commit();

    DBUG_EXECUTE_IF("rli_pre_commit_error", {
      error = true;
      my_error(ER_UNKNOWN_ERROR, MYF(0));
    });
    DBUG_EXECUTE_IF("replica_crash_before_commit", {
      /* This pre-commit crash aims solely at atomic DDL */
      DBUG_SUICIDE();
    });
  }

  if (thd->in_sub_stmt) {
    assert(0);
    /*
      Since we don't support nested statement transactions in 5.0,
      we can't commit or rollback stmt transactions while we are inside
      stored functions or triggers. So we simply do nothing now.
      TODO: This should be fixed in later ( >= 5.1) releases.
    */
    if (!all) return 0;
    /*
      We assume that all statements which commit or rollback main transaction
      are prohibited inside of stored functions or triggers. So they should
      bail out with error even before ha_commit_trans() call. To be 100% safe
      let us throw error in non-debug builds.
    */
    my_error(ER_COMMIT_NOT_ALLOWED_IN_SF_OR_TRG, MYF(0));
    return 2;
  }

  MDL_request mdl_request;
  bool release_mdl = false;
  if (ha_info && !error) {
    uint rw_ha_count = 0;
    bool rw_trans;

    DBUG_EXECUTE_IF("crash_commit_before", DBUG_SUICIDE(););

    /*
     skip 2PC if the transaction is empty and it is not marked as started (which
     can happen when the slave's binlog is disabled)
    */
    if (ha_info->is_started())
      rw_ha_count = ha_check_and_coalesce_trx_read_only(thd, ha_info, all);
    trn_ctx->set_rw_ha_count(trx_scope, rw_ha_count);
    /* rw_trans is true when we in a transaction changing data */
    rw_trans = is_real_trans && (rw_ha_count > 0);

    DBUG_EXECUTE_IF("dbug.enabled_commit", {
      const char act[] = "now signal Reached wait_for signal.commit_continue";
      assert(!debug_sync_set_action(thd, STRING_WITH_LEN(act)));
    };);
    DEBUG_SYNC(thd, "ha_commit_trans_before_acquire_commit_lock");
    if (rw_trans && !ignore_global_read_lock) {
      /*
        Acquire a metadata lock which will ensure that COMMIT is blocked
        by an active FLUSH TABLES WITH READ LOCK (and vice versa:
        COMMIT in progress blocks FTWRL).

        We allow the owner of FTWRL to COMMIT; we assume that it knows
        what it does.
      */
      MDL_REQUEST_INIT(&mdl_request, MDL_key::COMMIT, "", "",
                       MDL_INTENTION_EXCLUSIVE, MDL_EXPLICIT);

      DBUG_PRINT("debug", ("Acquire MDL commit lock"));
      if (thd->mdl_context.acquire_lock(&mdl_request,
                                        thd->variables.lock_wait_timeout)) {
        ha_rollback_trans(thd, all);
        return 1;
      }
      release_mdl = true;

      DEBUG_SYNC(thd, "ha_commit_trans_after_acquire_commit_lock");
    }

    if (rw_trans && stmt_has_updated_trans_table(ha_info) &&
        check_readonly(thd, true)) {
      ha_rollback_trans(thd, all);
      error = 1;
      goto end;
    }

    if (!trn_ctx->no_2pc(trx_scope) && (trn_ctx->rw_ha_count(trx_scope) > 1))
      error = tc_log->prepare(thd, all);
  }
  /*
    The state of XA transaction is changed to Prepared, intermediately.
    It's going to change to the regular NOTR at the end.
    The fact of the Prepared state is of interest to binary logger.
  */
  if (!error && all && xid_state->has_state(XID_STATE::XA_IDLE)) {
    assert(
        thd->lex->sql_command == SQLCOM_XA_COMMIT &&
        static_cast<Sql_cmd_xa_commit *>(thd->lex->m_sql_cmd)->get_xa_opt() ==
            XA_ONE_PHASE);

    xid_state->set_state(XID_STATE::XA_PREPARED);
  }
  if (error || (error = tc_log->commit(thd, all))) {
    ha_rollback_trans(thd, all);
    error = 1;
    goto end;
  }
/*
        Mark multi-statement (any autocommit mode) or single-statement
        (autocommit=1) transaction as rolled back
*/
#ifdef HAVE_PSI_TRANSACTION_INTERFACE
  if (is_real_trans && thd->m_transaction_psi != nullptr) {
    MYSQL_COMMIT_TRANSACTION(thd->m_transaction_psi);
    thd->m_transaction_psi = nullptr;
  }
#endif
  DBUG_EXECUTE_IF("crash_commit_after",
                  if (!thd->is_operating_gtid_table_implicitly)
                      DBUG_SUICIDE(););
end:
  if (release_mdl && mdl_request.ticket) {
    /*
      We do not always immediately release transactional locks
      after ha_commit_trans() (see uses of ha_enable_transaction()),
      thus we release the commit blocker lock as soon as it's
      not needed.
    */
    DBUG_PRINT("debug", ("Releasing MDL commit lock"));
    thd->mdl_context.release_lock(mdl_request.ticket);
  }
  /* Free resources and perform other cleanup even for 'empty' transactions. */
  if (is_real_trans) {
    trn_ctx->cleanup();
    thd->tx_priority = 0;
  }

  if (need_clear_owned_gtid) {
    thd->server_status &= ~SERVER_STATUS_IN_TRANS;
    /*
      Release the owned GTID when binlog is disabled, or binlog is
      enabled and log_replica_updates is disabled with slave SQL thread
      or slave worker thread.
    */
    if (error)
      gtid_state->update_on_rollback(thd);
    else
      gtid_state->update_on_commit(thd);
  } else {
    if (has_commit_order_manager(thd) && error) {
      gtid_state->update_on_rollback(thd);
    }
  }
  if (run_slave_post_commit) {
    DBUG_EXECUTE_IF("replica_crash_after_commit", DBUG_SUICIDE(););

    thd->rli_slave->post_commit(error != 0);
    /*
      SERVER_STATUS_IN_TRANS may've been gained by pre_commit alone
      when the main DDL transaction is filtered out of execution.
      In such case the status has to be reset now.

      TODO: move/refactor this handling onto trans_commit/commit_implicit()
            the caller level.
    */
    thd->server_status &= ~SERVER_STATUS_IN_TRANS;
  } else {
    DBUG_EXECUTE_IF("replica_crash_after_commit", {
      if (thd->slave_thread && thd->rli_slave &&
          thd->rli_slave->current_event &&
          thd->rli_slave->current_event->get_type_code() ==
              mysql::binlog::event::XID_EVENT &&
          !thd->is_operating_substatement_implicitly &&
          !thd->is_operating_gtid_table_implicitly && !transaction_to_skip)
        DBUG_SUICIDE();
    });
  }

  return error;
}
