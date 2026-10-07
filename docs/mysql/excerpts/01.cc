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
