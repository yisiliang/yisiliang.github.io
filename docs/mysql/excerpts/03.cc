    case COM_QUERY: {
      /*
        IMPORTANT NOTE:

        Every execution path for COM_QUERY should call once
          MYSQL_NOTIFY_STATEMENT_QUERY_ATTRIBUTES()
      */
      assert(thd->m_digest == nullptr);
      thd->m_digest = &thd->m_digest_state;
      thd->m_digest->reset(thd->m_token_array, max_digest_length);

      if (alloc_query(thd, com_data->com_query.query,
                      com_data->com_query.length)) {
        MYSQL_NOTIFY_STATEMENT_QUERY_ATTRIBUTES(thd->m_statement_psi, false);
        break;  // fatal error is set
      }

      const char *packet_end = thd->query().str + thd->query().length;

      if (opt_general_log_raw)
        query_logger.general_log_write(thd, command, thd->query().str,
                                       thd->query().length);

      DBUG_PRINT("query", ("%-.4096s", thd->query().str));

#if defined(ENABLED_PROFILING)
      thd->profiling->set_query_source(thd->query().str, thd->query().length);
#endif

      const LEX_CSTRING orig_query = thd->query();

      Parser_state parser_state;
      if (parser_state.init(thd, thd->query().str, thd->query().length)) {
        MYSQL_NOTIFY_STATEMENT_QUERY_ATTRIBUTES(thd->m_statement_psi, false);
        break;
      }
