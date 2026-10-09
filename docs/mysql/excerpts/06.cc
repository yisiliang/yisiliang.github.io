/**
  Optimizes one query block into a query execution plan (QEP.)

  This is the entry point to the query optimization phase. This phase
  applies both logical (equivalent) query rewrites, cost-based join
  optimization, and rule-based access path selection. Once an optimal
  plan is found, the member function creates/initializes all
  structures needed for query execution. The main optimization phases
  are outlined below:

    -# Logical transformations:
      - Outer to inner joins transformation.
      - Equality/constant propagation.
      - Partition pruning.
      - COUNT(*), MIN(), MAX() constant substitution in case of
        implicit grouping.
      - ORDER BY optimization.
    -# Perform cost-based optimization of table order and access path
       selection. See JOIN::make_join_plan()
    -# Post-join order optimization:
       - Create optimal table conditions from the where clause and the
         join conditions.
       - Inject outer-join guarding conditions.
       - Adjust data access methods after determining table condition
         (several times.)
       - Optimize ORDER BY/DISTINCT.
    -# Code generation
       - Set data access functions.
       - Try to optimize away sorting/distinct.
       - Setup temporary table usage for grouping and/or sorting.

  @retval false Success.
  @retval true Error, error code saved in member JOIN::error.
*/
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
         implicit_grouping);

  const bool has_windows = m_windows.elements != 0;

  if (has_windows && Window::setup_windows2(thd, &m_windows))
    return true; /* purecov: inspected */

  if (query_block->olap == ROLLUP_TYPE && optimize_rollup())
    return true; /* purecov: inspected */

  if (alloc_func_list()) return true; /* purecov: inspected */

  if (query_block->get_optimizable_conditions(thd, &where_cond, &having_cond))
    return true;

  for (Item_rollup_group_item *item : query_block->rollup_group_items) {
    rollup_group_items.push_back(item);
  }
  for (Item_rollup_sum_switcher *item : query_block->rollup_sums) {
    rollup_sums.push_back(item);
  }

  set_optimized();

  tables_list = query_block->leaf_tables;

  if (alloc_indirection_slices()) return true;

  // The base ref items from query block are assigned as JOIN's ref items
  ref_items[REF_SLICE_ACTIVE] = query_block->base_ref_items;

  /* dump_TABLE_LIST_graph(query_block, query_block->leaf_tables); */
  /*
    Run optimize phase for all derived tables/views used in this SELECT,
    including those in semi-joins.
  */
  // if (query_block->materialized_derived_table_count) {
  {  // WL#6570
    for (Table_ref *tl = query_block->leaf_tables; tl; tl = tl->next_leaf) {
      tl->access_path_for_derived = nullptr;
      if (tl->is_view_or_derived()) {
        if (tl->optimize_derived(thd)) return true;
      } else if (tl->is_table_function()) {
        TABLE *const table = tl->table;
        if (!table->has_storage_handler()) {
          if (setup_tmp_table_handler(
                  thd, table,
                  query_block->active_options() | TMP_TABLE_ALL_COLUMNS))
            return true; /* purecov: inspected */
        }

        table->file->stats.records = 2;
      }
    }
  }

  if (thd->lex->using_hypergraph_optimizer()) {
    // The hypergraph optimizer also wants all subselect items to be optimized,
    // so that it has cost information to attach to filter nodes.
    for (Query_expression *unit = query_block->first_inner_query_expression();
         unit; unit = unit->next_query_expression()) {
      // Derived tables and const subqueries are already optimized
      if (!unit->is_optimized() &&
          unit->optimize(thd, /*materialize_destination=*/nullptr,
                         /*create_iterators=*/false,
                         /*finalize_access_paths=*/false))
        return true;
    }

    // The hypergraph optimizer does not do const tables,
    // nor does it evaluate subqueries during optimization.
    query_block->add_active_options(OPTION_NO_CONST_TABLES |
                                    OPTION_NO_SUBQUERY_DURING_OPTIMIZATION);
  }

  has_lateral = false;

  /* dump_TABLE_LIST_graph(query_block, query_block->leaf_tables); */

  row_limit = ((select_distinct || !order.empty() || !group_list.empty())
                   ? HA_POS_ERROR
                   : query_expression()->select_limit_cnt);
  // m_select_limit is used to decide if we are likely to scan the whole table.
  m_select_limit = query_expression()->select_limit_cnt;

  if (query_expression()->first_query_block()->active_options() &
      OPTION_FOUND_ROWS) {
    /*
      Calculate found rows (ie., keep counting rows even after we hit LIMIT) if
      - LIMIT is set, and
      - This is the outermost query block (for a UNION query, this is the
        block that contains the limit applied on the final UNION
        evaluation, cf query_term.h for explanation).
     */
    calc_found_rows = m_select_limit != HA_POS_ERROR &&
                      (!query_expression()->is_set_operation() ||
                       query_block == set_operand_block);
  }
  if (having_cond || calc_found_rows) m_select_limit = HA_POS_ERROR;

  if (query_expression()->select_limit_cnt == 0 && !calc_found_rows) {
    zero_result_cause = "Zero limit";
    best_rowcount = 0;
    set_root_access_path(create_access_paths_for_zero_rows());
    goto setup_subq_exit;
  }

  if (where_cond || query_block->outer_join) {
    if (optimize_cond(thd, &where_cond, &cond_equal, &query_block->m_table_nest,
                      &query_block->cond_value)) {
      error = 1;
      DBUG_PRINT("error", ("Error from optimize_cond"));
      return true;
    }
    if (query_block->cond_value == Item::COND_FALSE) {
      zero_result_cause = "Impossible WHERE";
      best_rowcount = 0;
      set_root_access_path(create_access_paths_for_zero_rows());
      goto setup_subq_exit;
    }
  }
  if (having_cond) {
    if (optimize_cond(thd, &having_cond, &cond_equal, nullptr,
                      &query_block->having_value)) {
      error = 1;
      DBUG_PRINT("error", ("Error from optimize_cond"));
      return true;
    }
    if (query_block->having_value == Item::COND_FALSE) {
      zero_result_cause = "Impossible HAVING";
      best_rowcount = 0;
      set_root_access_path(create_access_paths_for_zero_rows());
      goto setup_subq_exit;
    }
  }

  if (query_block->partitioned_table_count && prune_table_partitions()) {
    error = 1;
    DBUG_PRINT("error", ("Error from prune_partitions"));
    return true;
  }

  /*
     Try to optimize count(*), min() and max() to const fields if
     there is implicit grouping (aggregate functions but no
     group_list). In this case, the result set shall only contain one
     row.
  */
  if (tables_list && implicit_grouping &&
      !(query_block->active_options() & OPTION_NO_CONST_TABLES)) {
    aggregate_evaluated outcome;
    if (optimize_aggregated_query(thd, query_block, *fields, where_cond,
                                  &outcome)) {
      error = 1;
      DBUG_PRINT("error", ("Error from optimize_aggregated_query"));
      return true;
    }
    switch (outcome) {
      case AGGR_REGULAR:
        // Query was not (fully) evaluated. Revert to regular optimization.
        break;
      case AGGR_DELAYED:
        // Query was not (fully) evaluated. Revert to regular optimization,
        // but indicate that storage engine supports HA_COUNT_ROWS_INSTANT.
        select_count = true;
        break;
      case AGGR_COMPLETE: {
        // All SELECT expressions are fully evaluated
        DBUG_PRINT("info", ("Select tables optimized away"));
        zero_result_cause = "Select tables optimized away";
        tables_list = nullptr;  // All tables resolved
        best_rowcount = 1;
        const_tables = tables = primary_tables = query_block->leaf_table_count;
        AccessPath *path =
            NewFakeSingleRowAccessPath(thd, /*count_examined_rows=*/true);
        path = attach_access_paths_for_having_and_limit(path);
        m_root_access_path = path;
        /*
          There are no relevant conditions left from the WHERE;
          optimize_aggregated_query() will not return AGGR_COMPLETE if there are
          any table-independent conditions, and all other conditions have been
          optimized away by it. Thus, remove the condition, unless we have
          EXPLAIN (in which case we will keep it for printing).
        */
        if (!thd->lex->is_explain()) {
#ifndef NDEBUG
          // Verify, to be sure.
          if (where_cond != nullptr) {
            Item *table_independent_conds = make_cond_for_table(
                thd, where_cond, PSEUDO_TABLE_BITS, table_map(0),
                /*exclude_expensive_cond=*/true);
            assert(table_independent_conds == nullptr);
          }
#endif
          where_cond = nullptr;
        }
        goto setup_subq_exit;
      }
      case AGGR_EMPTY:
        // It was detected that the result tables are empty
        DBUG_PRINT("info", ("No matching min/max row"));
        zero_result_cause = "No matching min/max row";
        set_root_access_path(create_access_paths_for_zero_rows());
        goto setup_subq_exit;
    }
  }

  if (thd->lex->using_hypergraph_optimizer() &&
      query_block->is_table_value_constructor) {
    // Let the hypergraph optimizer handle table value constructors, even though
    // they are table-less queries.
  } else if (tables_list == nullptr) {
    DBUG_PRINT("info", ("No tables"));
    best_rowcount = 1;
    error = 0;
    if (make_tmp_tables_info()) return true;
    count_field_types(query_block, &tmp_table_param, *fields, false, false);
    // Make plan visible for EXPLAIN
    set_plan_state(NO_TABLES);
    create_access_paths();
    return false;
  }
  error = -1;  // Error is sent to client

  {
    m_windowing_steps = false;  // initialization
    m_windows_sort = false;
    List_iterator<Window> li(m_windows);
    Window *w;
    while ((w = li++))
      if (w->needs_sorting()) {
        m_windows_sort = true;
        break;
      }
  }

  if (!thd->lex->using_hypergraph_optimizer()) {
    sort_by_table = get_sort_by_table(order.order, group_list.order,
                                      query_block->leaf_tables);
  }

  if ((where_cond || !group_list.empty() || !order.empty()) &&
      substitute_gc(thd, query_block, where_cond, group_list.order,
                    order.order)) {
    // We added hidden fields to the all_fields list, count them.
    count_field_types(query_block, &tmp_table_param, query_block->fields, false,
                      false);
  }
  // Ensure there are no errors prior making query plan
  if (thd->is_error()) return true;

  if (thd->lex->using_hypergraph_optimizer()) {
    // Get the WHERE and HAVING clauses with the IN-to-EXISTS predicates
    // removed, so that we can plan both with and without the IN-to-EXISTS
    // conversion.
    Item *where_cond_no_in2exists = remove_in2exists_conds(where_cond);
    Item *having_cond_no_in2exists = remove_in2exists_conds(having_cond);

    UnstructuredTrace unstructured_trace;
    if (thd->opt_trace.is_started()) {
      thd->opt_trace.set_unstructured_trace(&unstructured_trace);
    }

    // Add the contents of unstructured_trace to the JSON tree when we exit
    // this scope.
    const auto copy_trace = create_scope_guard([&]() {
      if (thd->opt_trace.is_started()) {
        MoveUnstructuredToStructuredTrace(thd);
      }
    });

    SaveCondEqualLists(cond_equal);

    m_root_access_path = FindBestQueryPlan(thd, query_block);
    if (finalize_access_paths && m_root_access_path != nullptr) {
      if (FinalizePlanForQueryBlock(thd, query_block)) {
        return true;
      }
    }

    // If this query block was modified by IN-to-EXISTS conversion,
    // the outer query block may want to undo that conversion and materialize
    // us instead, depending on cost. (Materialization has high initial cost,
    // but looking up in the materialized table is typically cheaper than
    // running the entire query.) If so, we will need to plan the query again,
    // but with all extra conditions added by IN-to-EXISTS removed, as those
    // are specific to the values referred to by the outer query.
    //
    // Thus, we detect this here, and plan a second query plan. There are
    // computations that could be shared between the two plans (e.g. join order
    // between tables for which there is no IN-to-EXISTS-related condition),
    // so it is somewhat wasteful, but experiments have shown that planning
    // both at the same time quickly clutters the code with such handling;
    // there are so many places such filters could be added (base table filters,
    // filters after various types of joins, join conditions, post-join filters,
    // HAVING, possibly others) that trying to plan paths both with and without
    // them incurs complexity that is not justified by the small computational
    // gain it would bring.
    if (where_cond != where_cond_no_in2exists ||
        having_cond != having_cond_no_in2exists) {
      if (TraceStarted(thd)) {
        Trace(thd)
            << "\nPlanning an alternative with in2exists conditions removed:\n";
      }
      where_cond = where_cond_no_in2exists;
      having_cond = having_cond_no_in2exists;
      assert(!finalize_access_paths);
      m_root_access_path_no_in2exists = FindBestQueryPlan(thd, query_block);
    } else {
      m_root_access_path_no_in2exists = nullptr;
    }

    if (m_root_access_path == nullptr) {
      return true;
    }
    set_plan_state(PLAN_READY);
    DEBUG_SYNC(thd, "after_join_optimize");
    return false;
  }

  // ----------------------------------------------------------------------------
  //       All of this is never called for the hypergraph join optimizer!
  // ----------------------------------------------------------------------------

  assert(!thd->lex->using_hypergraph_optimizer());
  // Don't expect to get here if the hypergraph optimizer is enabled via an
  // optimizer switch. The "is_regular()" case is necessary for SET statements.
  assert(!thd->optimizer_switch_flag(OPTIMIZER_SWITCH_HYPERGRAPH_OPTIMIZER) ||
         !thd->stmt_arena->is_regular());

  // Set up join order and initial access paths
  THD_STAGE_INFO(thd, stage_statistics);
  if (make_join_plan()) {
    if (thd->killed) thd->send_kill_message();
    DBUG_PRINT("error", ("Error: JOIN::make_join_plan() failed"));
    return true;
  }

  // At this stage, join_tab==NULL, JOIN_TABs are listed in order by best_ref.
  ASSERT_BEST_REF_IN_JOIN_ORDER(this);

  if (zero_result_cause != nullptr) {  // Can be set by make_join_plan().
    set_root_access_path(create_access_paths_for_zero_rows());
    goto setup_subq_exit;
  }

  if (!query_block->is_non_primitive_grouped()) {
    /* Remove distinct if only const tables */
    select_distinct &= !plan_is_const();
  }

  if (const_tables && !thd->locked_tables_mode &&
      !(query_block->active_options() & SELECT_NO_UNLOCK)) {
    TABLE *ct[MAX_TABLES];
    for (uint i = 0; i < const_tables; i++) {
      ct[i] = best_ref[i]->table();
      ct[i]->file->ha_index_or_rnd_end();
    }
    mysql_unlock_some_tables(thd, ct, const_tables);
  }
  if (!where_cond && query_block->outer_join) {
    /* Handle the case where we have an OUTER JOIN without a WHERE */
    where_cond = new Item_func_true();  // Always true
  }

  error = 0;
  /*
    Among the equal fields belonging to the same multiple equality
    choose the one that is to be retrieved first and substitute
    all references to these in where condition for a reference for
    the selected field.
  */
  if (where_cond) {
    where_cond =
        substitute_for_best_equal_field(thd, where_cond, cond_equal, map2table);
    if (thd->is_error()) {
      error = 1;
      DBUG_PRINT("error", ("Error from substitute_for_best_equal"));
      return true;
    }
    where_cond->update_used_tables();
    DBUG_EXECUTE("where",
                 print_where(thd, where_cond, "after substitute_best_equal",
                             QT_ORDINARY););
  }

  /*
    Perform the same optimization on field evaluation for all join conditions.
  */
  for (uint i = const_tables; i < tables; ++i) {
    JOIN_TAB *const tab = best_ref[i];
    if (tab->position() != nullptr && tab->join_cond() != nullptr) {
      tab->set_join_cond(substitute_for_best_equal_field(
          thd, tab->join_cond(), tab->cond_equal, map2table));
      if (thd->is_error()) {
        error = 1;
        DBUG_PRINT("error", ("Error from substitute_for_best_equal"));
        return true;
      }
      tab->join_cond()->update_used_tables();
      if (tab->join_cond()->walk(&Item::cast_incompatible_args,
                                 enum_walk::POSTFIX, nullptr)) {
        return true;
      }
    }
  }

  if (init_ref_access()) {
    error = 1;
    DBUG_PRINT("error", ("Error from init_ref_access"));
    return true;
  }

  // Update table dependencies after assigning ref access fields
  update_depend_map();

  THD_STAGE_INFO(thd, stage_preparing);

  if (make_join_query_block(this, where_cond)) {
    if (thd->is_error()) return true;

    zero_result_cause = "Impossible WHERE noticed after reading const tables";
    set_root_access_path(create_access_paths_for_zero_rows());
    goto setup_subq_exit;
  }

  // Inject cast nodes into the WHERE conditions
  if (where_cond != nullptr && where_cond->walk(&Item::cast_incompatible_args,
                                                enum_walk::POSTFIX, nullptr)) {
    return true;
  }
  error = -1; /* if goto err */

  if (optimize_distinct_group_order()) return true;

  if ((query_block->active_options() & SELECT_NO_JOIN_CACHE) ||
      query_block->ftfunc_list->elements)
    no_jbuf_after = 0;

  /* Perform FULLTEXT search before all regular searches */
  if (query_block->has_ft_funcs() && optimize_fts_query()) return true;

  /*
    By setting child_subquery_can_materialize so late we gain the following:
    JOIN::compare_costs_of_subquery_strategies() can test this variable to
    know if we are have finished evaluating constant conditions, which itself
    helps determining fanouts.
  */
  child_subquery_can_materialize = true;

  /*
    It's necessary to check const part of HAVING cond as
    there is a chance that some cond parts may become
    const items after make_join_plan() (for example
    when Item is a reference to const table field from
    outer join).
    This check is performed only for those conditions
    which do not use aggregate functions. In such case
    temporary table may not be used and const condition
    elements may be lost during further having
    condition transformation in JOIN::exec.
  */
  if (having_cond && !having_cond->has_aggregation() && (const_tables > 0)) {
    having_cond->update_used_tables();
    if (remove_eq_conds(thd, having_cond, &having_cond,
                        &query_block->having_value)) {
      error = 1;
      DBUG_PRINT("error", ("Error from remove_eq_conds"));
      return true;
    }
    if (query_block->having_value == Item::COND_FALSE) {
      having_cond = new Item_func_false();
      zero_result_cause =
          "Impossible HAVING noticed after reading const tables";
      set_root_access_path(create_access_paths_for_zero_rows());
      goto setup_subq_exit;
    }
  }

  // Inject cast nodes into the HAVING conditions
  if (having_cond != nullptr &&
      having_cond->walk(&Item::cast_incompatible_args, enum_walk::POSTFIX,
                        nullptr)) {
    return true;
  }
  // Traverse the expressions and inject cast nodes to compatible data types,
  // if needed.
  for (Item *item : *fields) {
    if (item->walk(&Item::cast_incompatible_args, enum_walk::POSTFIX,
                   nullptr)) {
      return true;
    }
  }

  // Also GROUP BY expressions, so that find_in_group_list() doesn't
  // inadvertently fail because the SELECT list has casts that GROUP BY doesn't.
  for (ORDER *ord = group_list.order; ord != nullptr; ord = ord->next) {
    if ((*ord->item)
            ->walk(&Item::cast_incompatible_args, enum_walk::POSTFIX,
                   nullptr)) {
      return true;
    }
  }

  // See if this subquery can be evaluated with subselect_indexsubquery_engine
  if (const int ret = replace_index_subquery()) {
    if (ret == -1) {
      // Error (e.g. allocation failed, or some condition was attempted
      // evaluated statically and failed).
      return true;
    }

    create_access_paths_for_index_subquery();
    set_plan_state(PLAN_READY);
    /*
      We leave optimize() because the rest of it is only about order/group
      which those subqueries don't have and about setting up plan which
      we're not going to use due to different execution method.
    */
    return false;
  }

  {
    /*
      If the hint FORCE INDEX FOR ORDER BY/GROUP BY is used for the first
      table (it does not make sense for other tables) then we cannot do join
      buffering.
    */
    if (!plan_is_const()) {
      const TABLE *const first = best_ref[const_tables]->table();
      if ((first->force_index_order && !order.empty()) ||
          (first->force_index_group && !group_list.empty()))
        no_jbuf_after = 0;
    }

    bool simple_sort = true;
    const Table_map_restorer deps_lateral(
        &deps_of_remaining_lateral_derived_tables);
    // Check whether join cache could be used
    for (uint i = const_tables; i < tables; i++) {
      JOIN_TAB *const tab = best_ref[i];
      if (!tab->position()) continue;
      if (setup_join_buffering(tab, this, no_jbuf_after)) return true;
      if (tab->use_join_cache() != JOIN_CACHE::ALG_NONE) simple_sort = false;
      assert(tab->type() != JT_FT ||
             tab->use_join_cache() == JOIN_CACHE::ALG_NONE);
      if (has_lateral && get_lateral_deps(*best_ref[i]) != 0) {
        deps_of_remaining_lateral_derived_tables =
            calculate_deps_of_remaining_lateral_derived_tables(all_table_map,
                                                               i + 1);
      }
    }
    if (!simple_sort) {
      /*
        A join buffer is used for this table. We here inform the optimizer
        that it should not rely on rows of the first non-const table being in
        order thanks to an index scan; indeed join buffering of the present
        table subsequently changes the order of rows.
      */
      simple_order = simple_group = false;
    }
  }

  if (!plan_is_const() && !order.empty()) {
    /*
      Force using of tmp table if sorting by a SP or UDF function due to
      their expensive and probably non-deterministic nature.
    */
    for (ORDER *tmp_order = order.order; tmp_order;
         tmp_order = tmp_order->next) {
      Item *item = *tmp_order->item;
      if (item->cost().IsExpensive()) {
        /* Force tmp table without sort */
        simple_order = simple_group = false;
        break;
      }
    }
  }

  /*
    Check if we need to create a temporary table prior to any windowing.

    (1) If there is ROLLUP, which happens before DISTINCT, windowing and ORDER
    BY, any of those clauses needs the result of ROLLUP in a tmp table.

    Rows which ROLLUP adds to the result are visible only to DISTINCT,
    windowing and ORDER BY which we handled above. So for the rest of
    conditions ((2), etc), we can do as if there were no ROLLUP.

    (2) If all tables are constant, the query's result is guaranteed to have 0
    or 1 row only, so all SQL clauses discussed below (DISTINCT, ORDER BY,
    GROUP BY, windowing, SQL_BUFFER_RESULT) are useless and need no tmp
    table.

    (3) If there is GROUP BY which isn't resolved by using an index or sorting
    the first table, we need a tmp table to compute the grouped rows.
    GROUP BY happens before windowing; so it is a pre-windowing tmp
    table.

    (4) (5) If there is DISTINCT, or ORDER BY which isn't resolved by using an
    index or sorting the first table, those clauses need an input tmp table.
    If we have windowing, as those clauses are used after windowing, they can
    use the last window's tmp table.

    (6) If there are different ORDER BY and GROUP BY orders, ORDER BY needs an
    input tmp table, so it's like (5).

    (7) If the user wants us to buffer the result, we need a tmp table. But
    windowing creates one anyway, and so does the materialization of a derived
    table.

    See also the computation of Window::m_short_circuit,
    where we make sure to create a tmp table if the clauses above want one.

    (8) If the first windowing step needs sorting, filesort() will be used; it
    can sort one table but not a join of tables, so we need a tmp table
    then. If GROUP BY was optimized away, the pre-windowing result is 0 or 1
    row so doesn't need sorting.
  */

  if (rollup_state != RollupState::NONE &&  // (1)
      (select_distinct || has_windows || !order.empty()))
    need_tmp_before_win = true;

  /*
    If we have full-text columns involved in aggregation, we may need to
    materialize them. Materialization is needed if the result of a full-text
    search (the MATCH function) is accessed after aggregation, as the saving and
    loading of rows in AggregateIterator does not include FTS information. If we
    have a GROUP BY, we'll either have an aggregate-to-table or a sort, which
    fixes the issue. However, in the case of implicit grouping, we need to force
    the temporary table here.
   */
  if (!need_tmp_before_win && implicit_grouping &&
      contains_non_aggregated_fts()) {
    need_tmp_before_win = true;
  }

  if (!plan_is_const())  // (2)
  {
    if ((!group_list.empty() && !simple_group) ||                       // (3)
        (!has_windows && (select_distinct ||                            // (4)
                          (!order.empty() && !simple_order) ||          // (5)
                          (!group_list.empty() && !order.empty()))) ||  // (6)
        ((query_block->active_options() & OPTION_BUFFER_RESULT) &&
         !has_windows &&
         !(query_expression()->derived_table &&
           query_expression()
               ->derived_table->uses_materialization())) ||     // (7)
        (has_windows && (primary_tables - const_tables) > 1 &&  // (8)
         m_windows[0]->needs_sorting() && !group_optimized_away))
      need_tmp_before_win = true;
  }

  DBUG_EXECUTE("info", TEST_join(this););

  if (alloc_qep(tables)) return (error = 1); /* purecov: inspected */

  if (!plan_is_const()) {
    // Test if we can use an index instead of sorting
    test_skip_sort();

    if (finalize_table_conditions(thd)) return true;
  }

  if (make_join_readinfo(this, no_jbuf_after))
    return true; /* purecov: inspected */

  if (make_tmp_tables_info()) return true;

  /*
    If we decided to not sort after all, update the cost of the JOIN.
    Windowing sorts are handled elsewhere
  */
  if (sort_cost > 0.0 &&
      !explain_flags.any(ESP_USING_FILESORT, ESC_WINDOWING)) {
    best_read -= sort_cost;
    sort_cost = 0.0;
  }

  count_field_types(query_block, &tmp_table_param, *fields, false, false);

  create_access_paths();

  // Creating iterators may evaluate a constant hash join condition, which may
  // fail:
  if (thd->is_error()) return true;

  if (rollup_state != RollupState::NONE && query_block->has_ft_funcs()) {
    if (check_access_path_with_fts()) {
      return true;
    }
  }

  /*
    At this stage, we have set up an AccessPath 'plan'. Traverse the
    AccessPath structures and find components which may be offloaded to
    the engines. This process is allowed to modify the AccessPath itself.
    (Removing/modifying FILTERs where pushed to the engines, change JOIN*
    algorithms being used, modify aggregate expressions, ...).
    This will later affects which type of Iterator we should create. Thus no
    Iterators should be set up until after push_to_engines() has completed.

    Note that when the Hypergraph optimizer is used, there is an entirely
    different code path to push_to_engine(). (We create the AcccesPath directly
    instead of converting the QEP_TABs into an AccessPath structure).
    In the HG case we push_to_engine() when FinalizePlanForQueryBlock()
    has finalized the 'plan'.
  */
  if (push_to_engines()) return true;

  // Make plan visible for EXPLAIN
  set_plan_state(PLAN_READY);

  DEBUG_SYNC(thd, "after_join_optimize");

  error = 0;
  return false;

setup_subq_exit:

  assert(zero_result_cause != nullptr);
  assert(m_root_access_path != nullptr);
  /*
    Even with zero matching rows, subqueries in the HAVING clause may
    need to be evaluated if there are aggregate functions in the
    query. If this JOIN is part of an outer query, subqueries in HAVING may
    be evaluated several times in total; so subquery materialization makes
    sense.
  */
  child_subquery_can_materialize = true;

  trace_steps.end();  // because all steps are done
  Opt_trace_object(trace, "empty_result").add_alnum("cause", zero_result_cause);

  having_for_explain = having_cond;
  error = 0;

  if (!qep_tab && best_ref) {
    /*
      After creation of JOIN_TABs in make_join_plan(), we have shortcut due to
      some zero_result_cause. For simplification, if we have JOIN_TABs we
      want QEP_TABs too.
    */
    if (alloc_qep(tables)) return true; /* purecov: inspected */
    unplug_join_tabs();
  }

  set_plan_state(ZERO_RESULT);
  return false;
}
