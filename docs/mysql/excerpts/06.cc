bool JOIN::optimize(bool finalize_access_paths) {
  DBUG_TRACE;

  uint no_jbuf_after = UINT_MAX;
  Query_block *const set_operand_block =
      query_expression()->non_simple_result_query_block();

  assert(query_block->leaf_table_count == 0 ||
         thd->lex->is_query_tables_locked() ||
         query_block == set_operand_block);
  assert(tables == 0 && primary_tables == 0 && tables_list == (Table_ref *)1);

  // to prevent double initialization on EXPLAIN
  if (optimized) return false;

  DEBUG_SYNC(thd, "before_join_optimize");

  THD_STAGE_INFO(thd, stage_optimizing);

  Opt_trace_context *const trace = &thd->opt_trace;
  const Opt_trace_object trace_wrapper(trace);
  Opt_trace_object trace_optimize(trace, "join_optimization");
  trace_optimize.add_select_number(query_block->select_number);
  Opt_trace_array trace_steps(trace, "steps");

  count_field_types(query_block, &tmp_table_param, *fields, false, false);

  assert(tmp_table_param.sum_func_count == 0 || !group_list.empty() ||
