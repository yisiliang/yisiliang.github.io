  }
  *send_records_ptr = 0;

  thd->get_stmt_da()->reset_current_row_for_condition();

  {
    auto join_cleanup = create_scope_guard([this, thd] {
      for (Query_block *sl = first_query_block(); sl;
           sl = sl->next_query_block()) {
        JOIN *join = sl->join;
        join->join_free();
        thd->inc_examined_row_count(join->examined_rows);
      }
      if (!is_simple() && set_operation()->m_is_materialized)
        thd->inc_examined_row_count(
            query_term()->query_block()->join->examined_rows);
    });

    if (m_root_iterator->Init()) {
      return true;
    }

    PFSBatchMode pfs_batch_mode(m_root_iterator.get());

    for (;;) {
      int error = m_root_iterator->Read();
      DBUG_EXECUTE_IF("bug13822652_1", thd->killed = THD::KILL_QUERY;);

