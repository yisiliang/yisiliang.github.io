# MySQL源码学习手册

> 源码之下，系统之上。沿一条SQL，读懂Server、InnoDB和提交恢复。

**固定版本：mysql-8.4.0（8.4 LTS起点）**；官方提交：`dc86e412f18b36ce271f791026714e8caa0ec919`。这是一份固定源码基线的机制教程，不是最新补丁部署建议。研究覆盖Classic Protocol、Server优化执行与InnoDB；不覆盖NDB、X Protocol、商业插件及完整SQL语法。

[交互阅读](index.html) · [离线包](mysql-offline.zip) · [核验记录](VERIFICATION.md) · [源码许可](source-notices.txt)

每章先说明为什么需要这一步，再落到对象、字段、条件和失败路径。流程图是作者机制示意，省略支线，不能代替完整源码。真实节选是固定SHA连续窗口，短窗口可能起止于函数中间，完整上下文由永久链接提供。实验SQL**未执行**，所有预期均需在隔离的MySQL8.4环境复核。

## 阅读路径

- 请求主线：02→03→04→05→06→07→08→09。
- 存储与恢复：10→11→12→13→14→15→24。
- 并发一致性：16→17→18→19→20→25。
- 提交与复制：21→22→23→26→27。

<a id="chapter-01"></a>

## 01 · 阅读地图：先分清三本账

研究MySQL不能把SQL执行、存储引擎和复制日志揉成一个黑箱。Server层拥有连接上下文THD、语法树、优化器和协议结果；handler把访问动作交给引擎；InnoDB管理页、记录版本、事务与物理恢复；binlog描述对外复制的事务历史。下文固定mysql-8.4.0，选择8.4 LTS起点是为了稳定源码坐标，不意味着部署时应使用这个早期补丁。

阅读时一直保留三个问题：记录当前由哪个事务改过？哪些页修改已经能从redo重做？Server认为哪些事务已经写入binlog？前三者分别涉及DB_TRX_ID/undo链、LSN和XID/GTID，编号不能互换。COMMIT时交叉这些账本，恢复时再对账。

本章节选的ha_commit_trans是Server级提交入口，不是InnoDB单独提交。参数all区分完整事务与语句级提交边界；同一连接里还存在语句事务与完整事务的不同参与者列表。把函数名中的commit直接解释为“磁盘页全部写完”，后面的两阶段提交就会读错。

![图1：阅读地图：先分清三本账](diagrams/01.svg)

**真实源码窗口：**[sql/handler.cc · L1786–L1827](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/handler.cc#L1786-L1827)。

```cpp
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
```

<a id="chapter-02"></a>

## 02 · 连接与THD：会话状态的所有者

默认每连接线程路径由handle_connection持有channel_info，建立THD，完成连接准备，然后反复do_command。线程缓存可以复用工作线程，所以连接生命周期与操作系统线程生命周期不能画成永久一一对应。企业线程池插件、X Protocol均不在这条默认Classic Protocol路径内。

THD不只是“线程编号”：它带着当前SQL、LEX、诊断区、事务上下文、会话变量、killed标记与MDL上下文。客户端执行SET SESSION会改变后续语句解释或执行条件，但不会改变别的THD。读调用链时，应分别看会话长期对象与每语句mem_root分配的短期对象。

循环退出会触发连接资源和会话清理。KILL QUERY与KILL CONNECTION在语句取消和连接终止上的语义不同；执行器读取killed后发送错误，而连接断开还会引发未完成事务回滚。连接池归还连接前若未重置事务或会话变量，就可能把前一个请求的状态交给下一个请求，这是应用层复用边界，不是InnoDB读错了数据。

![图2：连接与THD：会话状态的所有者](diagrams/02.svg)

**真实源码窗口：**[sql/conn_handler/connection_handler_per_thread.cc · L299–L316](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/conn_handler/connection_handler_per_thread.cc#L299-L316)。

```cpp

    if (thd_prepare_connection(thd))
      handler_manager->inc_aborted_connects();
    else {
      while (thd_connection_alive(thd)) {
        if (do_command(thd)) break;
      }
      end_connection(thd);
    }
    close_connection(thd, 0, false, false);

    thd->get_stmt_da()->reset_diagnostics_area();
    thd->release_resources();

    // Clean up errors now, before possibly waiting for a new connection.
#if OPENSSL_VERSION_NUMBER < 0x10100000L
    ERR_remove_thread_state(nullptr);
#endif /* OPENSSL_VERSION_NUMBER < 0x10100000L */
```

<a id="chapter-03"></a>

## 03 · COM_QUERY：字节进入SQL执行入口

do_command读取并解释协议命令后进入dispatch_command。COM_QUERY分支先把查询文本复制到THD，再初始化Parser_state和digest状态，最后dispatch_sql_command。这里还要处理查询属性、多语句和错误清理，不能把“收到文本”与“SQL合法”视为同一时点。

alloc_query失败时直接跳出，Parser_state初始化失败也不执行SQL。m_input.m_has_digest和m_compute_digest决定语句摘要处理；摘要服务于监控聚合，不是结果缓存。原查询文本和归一化digest是不同信息，不能仅凭digest追溯某一次请求的参数。

prepared statement使用COM_STMT_PREPARE/EXECUTE另外的协议分支，参数类型与文本解析重用边界不同。本手册主线选择COM_QUERY是为了让解析→优化→执行链更直观。长SQL、语法错误或分号多语句应先核对协议入口，再沿诊断区追踪；不要一上来去找B+树代码。

![图3：COM_QUERY：字节进入SQL执行入口](diagrams/03.svg)

**真实源码窗口：**[sql/sql_parse.cc · L2079–L2114](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/sql_parse.cc#L2079-L2114)。

```cpp
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
```

<a id="chapter-04"></a>

## 04 · 词法与语法：文本如何成为查询结构

lex_one_token负责从Lex_input_stream取字符并分类，关键字和标识符通过字符集、转义及SQL模式解释。sql/sql_yacc.yy声明Bison语法与语义动作，语法树随后形成Query_expression、Query_block、Item等结构。parse_sql在sql_parse.cc包装解析过程，错误写入THD诊断区。

WHERE a=1在这里是表达式树，不是已经选好了索引；表名出现也不意味着表已经成功打开。语法合法之后，名称解析还需要把列引用绑定到表和字段，对聚合、类型转换等做语义检查。词法、语法、解析后准备阶段各自有不同失败条件。

源码中有大量解析上下文与mem_root对象。生命周期边界解释了为什么不能保存某个Item指针给下一次COM_QUERY继续用。排查SQL注入也要在协议和解析边界思考：参数绑定传入值与字符串拼接改变语法结构是不同操作，索引优化无法弥补错误的查询结构。

![图4：词法与语法：文本如何成为查询结构](diagrams/04.svg)

**真实源码窗口：**[sql/sql_lex.cc · L1432–L1456](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/sql_lex.cc#L1432-L1456)。

```cpp
static int lex_one_token(Lexer_yystype *yylval, THD *thd) {
  uchar c = 0;
  bool comment_closed;
  int tokval, result_state;
  uint length;
  enum my_lex_states state;
  Lex_input_stream *lip = &thd->m_parser_state->m_lip;
  const CHARSET_INFO *cs = thd->charset();
  const my_lex_states *state_map = cs->state_maps->main_map;
  const uchar *ident_map = cs->ident_map;

  lip->yylval = yylval;  // The global state

  lip->start_token();
  state = lip->next_state;
  lip->next_state = MY_LEX_START;
  for (;;) {
    switch (state) {
      case MY_LEX_START:  // Start of token
        // Skip starting whitespace
        while (state_map[c = lip->yyPeek()] == MY_LEX_SKIP) {
          if (c == '\n') lip->yylineno++;

          lip->yySkip();
        }
```

<a id="chapter-05"></a>

## 05 · 打开表与MDL：结构为什么不能随意变化

Server需要在执行期间确保表结构与已准备的访问对象一致，MDL即元数据锁。MDL_context属于THD，MDL_ticket记录已经授予的锁，MDL_request描述请求的对象和锁类型。普通事务访问表与ALTER TABLE之间因此会产生等待，哪怕没有冲突的数据行。

MDL与InnoDB行锁不是同一套锁：前者保护对象定义/名称和操作边界，后者保护索引记录与范围。长事务即使已经停止跑SQL，也可能持有到事务结束的MDL票据，阻挡需要更强锁的DDL。新的普通查询还可能受等待队列影响，看起来像“ALTER卡住全库”，实际需要看对象粒度和队列。

本章节选是MDL_context::acquire_lock入口窗口；继续从MDL_context::acquire_lock追等待和授予逻辑。诊断实验使用performance_schema.metadata_locks，区分GRANTED/PENDING并连接threads。仅观察PROCESSLIST的Waiting for table metadata lock能定位方向，却不能直接判定谁持有阻塞票据。

![图5：打开表与MDL：结构为什么不能随意变化](diagrams/05.svg)

**真实源码窗口：**[sql/mdl.cc · L3371–L3427](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/mdl.cc#L3371-L3427)。

```cpp
  if (lock_wait_timeout == 0) {
    /*
      Resort to try_acquire_lock() in case of zero timeout.

      This allows to avoid unnecessary deadlock detection attempt and "fake"
      deadlocks which might result from it.
      In case of failure to acquire lock, try_acquire_lock() preserves
      invariants by updating MDL_lock::fast_path_state and obtrusive locks
      count. It also performs SE notification if needed.
    */
    if (try_acquire_lock(mdl_request)) return true;

    if (!mdl_request->ticket) {
      /* We have failed to acquire lock instantly. */
      DEBUG_SYNC(get_thd(), "mdl_acquire_lock_wait");
      my_error(ER_LOCK_WAIT_TIMEOUT, MYF(0));
      return true;
    }
    return false;
  }

  /* Normal, non-zero timeout case. */

  MDL_lock *lock;
  MDL_ticket *ticket = nullptr;
  struct timespec abs_timeout;
  MDL_wait::enum_wait_status wait_status;
  /* Do some work outside the critical section. */
  set_timespec(&abs_timeout, lock_wait_timeout);

  if (try_acquire_lock_impl(mdl_request, &ticket)) return true;

  if (mdl_request->ticket) {
    /*
      We have managed to acquire lock without waiting.
      MDL_lock, MDL_context and MDL_request were updated
      accordingly, so we can simply return success.
    */
    return false;
  }

  /*
    Our attempt to acquire lock without waiting has failed.
    As a result of this attempt we got MDL_ticket with m_lock
    member pointing to the corresponding MDL_lock object which
    has MDL_lock::m_rwlock write-locked.
  */
  lock = ticket->m_lock;

  lock->m_waiting.add_ticket(ticket);

  /*
    Once we added a pending ticket to the waiting queue,
    we must ensure that our wait slot is empty, so
    that our lock request can be scheduled. Do that in the
    critical section formed by the acquired write lock on MDL_lock.
  */
```

<a id="chapter-06"></a>

## 06 · 优化器：成本是在选计划，不是在保证速度

JOIN::optimize组织查询块优化，处理条件、表依赖、常量表、连接顺序和访问路径。8.4源码同时有传统优化器与其他优化路径，不能看见JOIN就把所有SQL都归为单一算法。统计估计参与成本比较，最终执行器面对真实数据，估计行数和实际行数可以严重不同。

同一个联合索引(a,b)既可能缩小扫描范围，也可能提供顺序、覆盖输出或ICP过滤。优化器判断的是这些收益与回表、随机读、排序成本的组合，不是“出现索引就一定用”。隐式类型转换、条件选择性、数据分布偏斜会改变候选路径的可用性或成本。

使用EXPLAIN FORMAT=TREE看结构，用EXPLAIN ANALYZE看执行测量，再用optimizer_trace追为何某候选被拒绝。ANALYZE会真实执行查询，不能把写入或昂贵SQL当无副作用解释命令。计划变化的失败后果常是放大扫描与回表次数，先比estimated/actual rows，再考虑更新统计或设计索引，而不是盲目FORCE INDEX。

![图6：优化器：成本是在选计划，不是在保证速度](diagrams/06.svg)

**真实源码窗口：**[sql/sql_optimizer.cc · L362–L389](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/sql_optimizer.cc#L362-L389)。

```cpp
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
```

<a id="chapter-07"></a>

## 07 · 迭代执行器：一行一行往上拉

Query_expression::ExecuteIteratorQuery初始化结果发送并驱动根迭代器。FilterIterator::Read不断调用m_source->Read，返回值非零立即传播；得到行后m_condition->val_int，未匹配时UnlockRow并继续。匹配才返回0。因此一个父节点请求一行可能触发子节点扫描很多行。

Read契约中0表示行，-1通常表示EOF，正数表示错误；不同适配层负责把引擎错误转换过来。thd()->killed与表达式求值错误在过滤过程检查，使取消和异常能沿树上传播。LIMIT通常可提前停止上游请求，但排序、聚合或物化可能先消费大量输入才能给出第一行。

这条链解释了为何“只返回10行”仍很慢：输出行数与底层检查行数不同。查看迭代器actual rows、loops和首行耗时，才能分清过滤浪费、嵌套循环放大与阻塞算子。不要拿客户端收到的结果条数衡量InnoDB做了多少工作。

![图7：迭代执行器：一行一行往上拉](diagrams/07.svg)

**真实源码窗口：**[sql/iterators/composite_iterators.cc · L91–L114](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/iterators/composite_iterators.cc#L91-L114)。

```cpp
int FilterIterator::Read() {
  for (;;) {
    int err = m_source->Read();
    if (err != 0) return err;

    bool matched = m_condition->val_int();

    if (thd()->killed) {
      thd()->send_kill_message();
      return 1;
    }

    /* check for errors evaluating the condition */
    if (thd()->is_error()) return 1;

    if (!matched) {
      m_source->UnlockRow();
      continue;
    }

    // Successful row.
    return 0;
  }
}
```

<a id="chapter-08"></a>

## 08 · handler边界：SQL执行器如何进入InnoDB

TableScanIterator::Read调用table()->file->ha_rnd_next，把记录写到Server的record buffer；handler包装层处理监控、访问状态和错误，再进入存储引擎虚函数。索引读取对应ha_index_read_map等入口。InnoDB的index_read/general_fetch把查询转成row_search_mvcc所需的搜索与游标状态。

关键对象prebuilt保存索引、事务、搜索tuple、row template与persistent cursor。Server记录格式和InnoDB页内记录格式不相同，row template参与转换。查询使用哪条索引、是否锁定读和读视图等状态经过这个边界，故handler不是“文件读取函数”。

一条SELECT可能多次跨越边界：二级索引定位、聚簇索引读取、迭代取下一条。在覆盖、ICP、MVCC验证等不同条件下是否回聚簇索引还要看具体分支。引擎报告锁等待或死锁时，Server适配成SQL错误；应用看到1213不意味着解析器失败。

![图8：handler边界：SQL执行器如何进入InnoDB](diagrams/08.svg)

**真实源码窗口：**[sql/iterators/basic_row_iterators.cc · L291–L312](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/iterators/basic_row_iterators.cc#L291-L312)。

```cpp
int TableScanIterator::Read() {
  int tmp;
  if (table()->is_union_or_table()) {
    while ((tmp = table()->file->ha_rnd_next(m_record))) {
      /*
       ha_rnd_next can return RECORD_DELETED for MyISAM when one thread is
       reading and another deleting without locks.
       */
      if (tmp == HA_ERR_RECORD_DELETED && !thd()->killed) continue;
      return HandleError(tmp);
    }
    if (m_examined_rows != nullptr) {
      ++*m_examined_rows;
    }
  } else {
    while (true) {
      if (m_remaining_dups == 0) {  // always initially
        while ((tmp = table()->file->ha_rnd_next(m_record))) {
          if (tmp == HA_ERR_RECORD_DELETED && !thd()->killed) continue;
          return HandleError(tmp);
        }
        if (m_examined_rows != nullptr) {
```

<a id="chapter-09"></a>

## 09 · 聚簇与二级索引：记录与定位键的区别

InnoDB聚簇索引叶子包含行数据，二级索引叶子包含二级键和聚簇定位信息。btr_cur_search_to_nth_level沿树找到指定层的记录位置，搜索使用tuple、比较模式和latch_mode。cursor记录当前页内位置；B+树的页结构与Server层的逻辑行迭代不可混淆。

主键宽度因此不仅影响聚簇树，也放大每个二级索引的定位字段。按二级键扫描再回聚簇树读取非覆盖字段，会增加另一组树查找与页访问。所谓覆盖索引也要考虑MVCC：二级记录不能像聚簇记录一样直接从完整undo链还原旧行，必要时仍需聚簇验证。

随机主键和顺序主键改变插入分布、页分裂及局部性，却不能推出“所有业务必须自增主键”。读写热点、分布式ID与业务唯一约束都要一起评估。源码追踪先固定index->is_clustered()分支，再比较两种访问路径；只画两棵树但忽略ReadView，就解释不全回表。

![图9：聚簇与二级索引：记录与定位键的区别](diagrams/09.svg)

**真实源码窗口：**[storage/innobase/btr/btr0cur.cc · L1539–L1580](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/btr/btr0cur.cc#L1539-L1580)。

```cpp
    /* Go to the child node */
    page_id.reset(space, btr_node_ptr_get_child_page_no(node_ptr, offsets));

    n_blocks++;

    if (UNIV_UNLIKELY(height == 0 && dict_index_is_ibuf(index))) {
      /* We're doing a search on an ibuf tree and we're one
      level above the leaf page. */

      ut_ad(level == 0);

      fetch = cursor->m_fetch_mode;
      rw_latch = RW_NO_LATCH;
      goto retry_page_get;
    }

    if (dict_index_is_spatial(index) && page_mode >= PAGE_CUR_CONTAIN &&
        page_mode != PAGE_CUR_RTREE_INSERT) {
      ut_ad(need_path);
      rtr_node_path_t *path = cursor->rtr_info->path;

      if (!path->empty() && found) {
#ifdef UNIV_DEBUG
        node_visit_t last_visit = path->back();

        ut_ad(last_visit.page_no == page_id.page_no());
#endif /* UNIV_DEBUG */

        path->pop_back();

#ifdef UNIV_DEBUG
        if (page_mode == PAGE_CUR_RTREE_LOCATE &&
            (latch_mode != BTR_MODIFY_LEAF)) {
          btr_pcur_t *cur = cursor->rtr_info->parent_path->back().cursor;
          rec_t *my_node_ptr = cur->get_rec();

          offsets = rec_get_offsets(my_node_ptr, index, offsets,
                                    ULINT_UNDEFINED, UT_LOCATION_HERE, &heap);

          page_no_t my_page_no =
              btr_node_ptr_get_child_page_no(my_node_ptr, offsets);

```

<a id="chapter-10"></a>

## 10 · 页、槽与分裂：B+树的物理变化

索引页有页头、infimum/supremum、用户记录、目录槽和空闲空间。页内记录逻辑顺序与物理存储位置不必一致；目录槽帮助缩小查找区间，再顺着记录链定位。页大小是实例建库相关配置，默认16KiB不代表所有表都必然16KiB。

btr_page_split_and_insert在无法满足插入时处理分裂，把记录分到新页并调整父节点与链。这个动作必须在mini-transaction保护下同时维护多个物理关系，并生成恢复所需日志；不能用“插入一行只改一块页”的成本模型。delete-mark与purge后物理清理也不能画为同一步。

页分裂会造成写放大、空间碎片与latch竞争，顺序插入也可能产生热点。逻辑事务锁保护业务并发语义，页latch保护短时结构一致性；持有latch去等待长事务锁会破坏并发设计，因此源码刻意控制不同临界区。性能诊断应先分清锁等待与页级争用。

![图10：页、槽与分裂：B+树的物理变化](diagrams/10.svg)

**真实源码窗口：**[storage/innobase/btr/btr0btr.cc · L2423–L2482](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/btr/btr0btr.cc#L2423-L2482)。

```cpp
  /* 2. Allocate a new page to the index */
  new_block = btr_page_alloc(cursor->index, hint_page_no, direction,
                             btr_page_get_level(page), mtr, mtr);

  /* New page could not be allocated */
  if (!new_block) {
    return nullptr;
  }

  new_page = buf_block_get_frame(new_block);
  new_page_zip = buf_block_get_page_zip(new_block);
  btr_page_create(new_block, new_page_zip, cursor->index,
                  btr_page_get_level(page), mtr);

  /* 3. Calculate the first record on the upper half-page, and the
  first record (move_limit) on original page which ends up on the
  upper half */

  if (split_rec) {
    first_rec = move_limit = split_rec;

    *offsets = rec_get_offsets(split_rec, cursor->index, *offsets, n_uniq,
                               UT_LOCATION_HERE, heap);

    insert_left = cmp_dtuple_rec(tuple, split_rec, cursor->index, *offsets) < 0;

    if (!insert_left && new_page_zip && n_iterations > 0) {
      /* If a compressed page has already been split,
      avoid further splits by inserting the record
      to an empty page. */
      split_rec = nullptr;
      goto insert_empty;
    }
  } else if (insert_left) {
    ut_a(n_iterations > 0);
    first_rec = page_rec_get_next(page_get_infimum_rec(page));
    move_limit = page_rec_get_next(btr_cur_get_rec(cursor));
  } else {
  insert_empty:
    ut_ad(!split_rec);
    ut_ad(!insert_left);
    buf = ut::new_arr_withkey<byte>(
        UT_NEW_THIS_FILE_PSI_KEY,
        ut::Count{rec_get_converted_size(cursor->index, tuple)});

    first_rec = rec_convert_dtuple_to_rec(buf, cursor->index, tuple);
    move_limit = page_rec_get_next(btr_cur_get_rec(cursor));
  }

  /* 4. Do first the modifications in the tree structure */

  btr_attach_half_pages(flags, cursor->index, block, first_rec, new_block,
                        direction, mtr);

  /* If the split is made on the leaf level and the insert will fit
  on the appropriate half-page, we may release the tree x-latch.
  We can then move the records after releasing the tree latch,
  thus reducing the tree latch contention. */

  if (split_rec) {
```

<a id="chapter-11"></a>

## 11 · Buffer Pool：缓存页为什么还需要状态机

buf_page_get_gen以page_id(space,page_no)定位页，结合page_size、锁模式和mtr返回buf_block_t。page hash解决是否缓存，LRU解决替换倾向，flush list解决脏页刷写；这三张结构的职责不同。block内存固定与页latch也不是同一个保护手段。

读线程撞到正在读取的页需要等待I/O完成，不能拿尚未完整装入的frame继续解释记录。被buffer-fixed或I/O-fixed的页不允许随意淘汰；脏页即使位于LRU尾端，也先需要满足写回条件。缓存不足因此可以同时引发读I/O、脏页刷写和请求等待。

Buffer Pool命中率是总体指标，不能解释所有慢查询。某次执行大量随机回表、冷数据或高并发热点页时，平均命中率仍可能很好。观察读请求、物理读、等待空闲页和脏页趋势，再结合执行计划。扩大内存只是一个手段，不会修正扫描范围太大或锁阻塞。

![图11：Buffer Pool：缓存页为什么还需要状态机](diagrams/11.svg)

**真实源码窗口：**[storage/innobase/buf/buf0buf.cc · L4419–L4444](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/buf/buf0buf.cc#L4419-L4444)。

```cpp
  if (mode == Page_fetch::NORMAL && !fsp_is_system_temporary(page_id.space())) {
    Buf_fetch_normal fetch(page_id, page_size);

    fetch.m_rw_latch = rw_latch;
    fetch.m_guess = guess;
    fetch.m_mode = mode;
    fetch.m_file = location.filename;
    fetch.m_line = location.line;
    fetch.m_mtr = mtr;
    fetch.m_dirty_with_no_latch = dirty_with_no_latch;

    return (fetch.single_page());

  } else {
    Buf_fetch_other fetch(page_id, page_size);

    fetch.m_rw_latch = rw_latch;
    fetch.m_guess = guess;
    fetch.m_mode = mode;
    fetch.m_file = location.filename;
    fetch.m_line = location.line;
    fetch.m_mtr = mtr;
    fetch.m_dirty_with_no_latch = dirty_with_no_latch;

    return (fetch.single_page());
  }
```

<a id="chapter-12"></a>

## 12 · LRU与flush list：淘汰和持久化是两条轴

InnoDB采用带old/young分区的LRU策略减轻大扫描污染。buf_LRU_add_block_low根据old参数插入链表并维护长度；提升与访问时间策略决定是否年轻化，不是每次命中都移到链表头。预读页和单次扫描页若立刻霸占热区，会把业务热点挤出。

flush list按脏页最早修改信息服务checkpoint推进。一个页很热仍可能需要刷盘，一个页很冷也可能是干净页可直接淘汰。这就是为何LRU list与flush list都要存在：前者按访问局部性，后者按恢复与日志复用约束。

读盘压力导致LRU刷写，redo空间压力导致flush list刷写，两者可同时发生但触发原因不同。调参时先看是free page不足还是checkpoint age增长，再评估I/O能力与redo容量。仅看到“后台正在刷盘”就统一增加Buffer Pool，可能把问题延后而没有改善持续写入能力。

![图12：LRU与flush list：淘汰和持久化是两条轴](diagrams/12.svg)

**真实源码窗口：**[storage/innobase/buf/buf0lru.cc · L1647–L1678](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/buf/buf0lru.cc#L1647-L1678)。

```cpp
static inline void buf_LRU_add_block_low(buf_page_t *bpage, bool old) {
  buf_pool_t *buf_pool = buf_pool_from_bpage(bpage);

  ut_ad(mutex_own(&buf_pool->LRU_list_mutex));

  ut_a(buf_page_in_file(bpage));
  ut_ad(!bpage->in_LRU_list);

  if (!old || (UT_LIST_GET_LEN(buf_pool->LRU) < BUF_LRU_OLD_MIN_LEN)) {
    UT_LIST_ADD_FIRST(buf_pool->LRU, bpage);

    bpage->freed_page_clock = buf_pool->freed_page_clock;
  } else {
#ifdef UNIV_LRU_DEBUG
    /* buf_pool->LRU_old must be the first item in the LRU list
    whose "old" flag is set. */
    ut_a(buf_pool->LRU_old->old);
    ut_a(!UT_LIST_GET_PREV(LRU, buf_pool->LRU_old) ||
         !UT_LIST_GET_PREV(LRU, buf_pool->LRU_old)->old);
    ut_a(!UT_LIST_GET_NEXT(LRU, buf_pool->LRU_old) ||
         UT_LIST_GET_NEXT(LRU, buf_pool->LRU_old)->old);
#endif /* UNIV_LRU_DEBUG */
    UT_LIST_INSERT_AFTER(buf_pool->LRU, buf_pool->LRU_old, bpage);

    buf_pool->LRU_old_len++;
  }

  ut_d(bpage->in_LRU_list = true);

  incr_LRU_size_in_bytes(bpage, buf_pool);

  if (UT_LIST_GET_LEN(buf_pool->LRU) > BUF_LRU_OLD_MIN_LEN) {
```

<a id="chapter-13"></a>

## 13 · mini-transaction与redo：物理一致性的最小单元

SQL事务可跨多个表、语句和秒级时间；mini-transaction(mtr)保护短时间的一组页访问与物理修改。mtr维护memo记录固定页和latch资源，日志缓冲收集本次物理修改，提交后释放资源。mtr_commit不等于用户COMMIT，也不意味着SQL事务对其他会话可见。

redo不是简单重放原SQL，而是描述页/记录等底层变化的恢复日志。某次SQL UPDATE可以产生多个mtr；undo页的修改也需要redo保护，否则崩溃后无法可靠回滚未提交事务。区分“undo用于回退逻辑版本”和“redo保护undo页物理恢复”能消除二者互斥的误解。

原子物理修改组在恢复时需要保持完整边界，LSN把日志和页修改关联。读源码应从mtr内部日志提交路径再走log writer，不要把memcpy写到log buffer当成已经落盘。内存中页内容、可写出日志和已持久化日志是不同状态。

![图13：mini-transaction与redo：物理一致性的最小单元](diagrams/13.svg)

**真实源码窗口：**[storage/innobase/mtr/mtr0mtr.cc · L659–L689](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/mtr/mtr0mtr.cc#L659-L689)。

```cpp
void mtr_t::commit() {
  ut_ad(is_active());
  ut_ad(!is_inside_ibuf());
  ut_ad(m_impl.m_magic_n == MTR_MAGIC_N);
  m_impl.m_state = MTR_STATE_COMMITTING;

  DBUG_EXECUTE_IF("mtr_commit_crash", DBUG_SUICIDE(););

  Command cmd(this);

  if (has_any_log_record() ||
      (has_modifications() && m_impl.m_log_mode == MTR_LOG_NO_REDO)) {
    ut_ad(!srv_read_only_mode || m_impl.m_log_mode == MTR_LOG_NO_REDO);

    cmd.execute();
  } else {
    cmd.release_all();
    cmd.release_resources();
  }
#ifndef UNIV_HOTBACKUP
  check_nolog_and_unmark();
#endif /* !UNIV_HOTBACKUP */

  ut_d(remove_from_debug_list());
}

#ifdef UNIV_DEBUG
void mtr_t::remove_from_debug_list() const {
  auto it = s_my_thread_active_mtrs.find(this);
  /* We have to find the MTR that is about to be committed in local context. We
  are not sharing MTRs between threads. */
```

<a id="chapter-14"></a>

## 14 · Redo流水线：write LSN和flush LSN为什么不同

log_write_up_to(log,end_lsn,flush_to_disk)表达的目标非常具体：至少写到end_lsn；如果flush_to_disk为true，还要达到磁盘持久化水位。writer与flusher处理不同步骤，write_lsn不是flushed_to_disk_lsn，OS cache写入与持久化不能混为一谈。

txn生成redo后可先让后台线程批量推进，前台请求等待目标水位。多个事务的LSN落入一次写/刷的覆盖范围，所以“每个COMMIT需要持久化保证”不等于“每个事务独立发一次fsync”。等待事件、通知与忙等优化负责协调，源码函数返回的Wait_stats支持监控等待代价。

日志空间是循环利用的有限资源。生成速度长期快于checkpoint推进时，最终会限制写入；扩大redo容量提供更大缓冲窗口，却不能让慢磁盘永久追上写入速率。崩溃类型也要区分：进程退出、操作系统崩溃和存储设备丢失，对OS cache中尚未flush的日志影响不同。

![图14：Redo流水线：write LSN和flush LSN为什么不同](diagrams/14.svg)

**真实源码窗口：**[storage/innobase/log/log0write.cc · L1135–L1207](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/log/log0write.cc#L1135-L1207)。

```cpp
retry:
  if (log.writer_threads_paused.load(std::memory_order_acquire)) {
    /* the log writer threads are paused not to waste CPU resource. */
    wait_stats +=
        log_self_write_up_to(log, end_lsn, flush_to_disk, &interrupted);

    if (UNIV_UNLIKELY(interrupted)) {
      /* the log writer threads might be working. retry. */
      goto retry;
    }

    DEBUG_SYNC_C("log_flushed_by_self");
    return wait_stats;
  }

  /* the log writer threads are working for high concurrency scale */
  if (flush_to_disk) {
    if (log.flushed_to_disk_lsn.load() >= end_lsn) {
      DEBUG_SYNC_C("log_flushed_by_writer");
      return wait_stats;
    }

    if (srv_flush_log_at_trx_commit != 1) {
      /* We need redo flushed, but because trx != 1, we have
      disabled notifications sent from log_writer to log_flusher.

      The log_flusher might be sleeping for 1 second, and we need
      quick response here. Log_writer avoids waking up log_flusher,
      so we must do it ourselves here.

      However, before we wake up log_flusher, we must ensure that
      log.write_lsn >= lsn. Otherwise log_flusher could flush some
      data which was ready for lsn values smaller than end_lsn and
      return to sleeping for next 1 second. */

      if (log.write_lsn.load() < end_lsn) {
        wait_stats += log_wait_for_write(log, end_lsn, &interrupted);
      }
    }

    /* Wait until log gets flushed up to end_lsn. */
    wait_stats += log_wait_for_flush(log, end_lsn, &interrupted);

    if (UNIV_UNLIKELY(interrupted)) {
      /* the log writer threads might be paused. retry. */
      goto retry;
    }

    DEBUG_SYNC_C("log_flushed_by_writer");
  } else {
    if (log.write_lsn.load() >= end_lsn) {
      return wait_stats;
    }

    /* Wait until log gets written up to end_lsn. */
    wait_stats += log_wait_for_write(log, end_lsn, &interrupted);

    if (UNIV_UNLIKELY(interrupted)) {
      /* the log writer threads might be paused. retry. */
      goto retry;
    }
  }

  return wait_stats;
}

/** @} */

/**************************************************/ /**

 @name Log threads waiting strategy

 *******************************************************/
```

<a id="chapter-15"></a>

## 15 · WAL、刷脏页与doublewrite

buf_flush_write_block_low在写脏页前取get_newest_lsn，若log_sys->flushed_to_disk_lsn落后则调用log_write_up_to(...,true)。这段代码直接体现WAL：数据页不能先于恢复它所需的日志被可靠写出。COMMIT通常不等待所有被改数据页刷盘，因此已提交事务仍可以对应内存脏页。

WAL解决的是写出顺序，doublewrite解决的是页写入撕裂风险。存储系统可能把一页只写了一部分；redo依赖页可解析，损坏页不一定仅靠redo就能补齐。doublewrite在支持的模式中保留可恢复页副本，再写最终位置；8.4具体模式、压缩/原子写能力需要分别看dblwr实现和配置。

oldest_modification服务脏页最早日志需求，newest LSN服务刷页前redo保证，两者不应该互换。刷写线程给页设I/O固定以防同时搬移或淘汰。若看到写延迟上升，应分别看redo flush、doublewrite与数据文件I/O，而不是把它们都归成“数据页fsync”。

![图15：WAL、刷脏页与doublewrite](diagrams/15.svg)

**真实源码窗口：**[storage/innobase/buf/buf0flu.cc · L1198–L1224](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/buf/buf0flu.cc#L1198-L1224)。

```cpp
#endif /* UNIV_IBUF_COUNT_DEBUG */

  ut_ad(recv_recovery_is_on() || bpage->get_newest_lsn() != 0);

  /* Force the log to the disk before writing the modified block */
  if (!srv_read_only_mode) {
    const lsn_t flush_to_lsn = bpage->get_newest_lsn();

    /* Do the check before calling log_write_up_to() because in most
    cases it would allow to avoid call, and because of that we don't
    want those calls because they would have bad impact on the counter
    of calls, which is monitored to save CPU on spinning in log threads. */

    if (log_sys->flushed_to_disk_lsn.load() < flush_to_lsn) {
      Wait_stats wait_stats;

      wait_stats = log_write_up_to(*log_sys, flush_to_lsn, true);

      MONITOR_INC_WAIT_STATS_EX(MONITOR_ON_LOG_, _PAGE_WRITTEN, wait_stats);
    }
  }

  switch (buf_page_get_state(bpage)) {
    case BUF_BLOCK_POOL_WATCH:
    case BUF_BLOCK_ZIP_PAGE: /* The page should be dirty. */
    case BUF_BLOCK_NOT_USED:
    case BUF_BLOCK_READY_FOR_USE:
```

<a id="chapter-16"></a>

## 16 · Undo与版本链：UPDATE之前的值在哪里

聚簇记录带有事务标识DB_TRX_ID和回滚指针DB_ROLL_PTR；有无显式主键还影响隐藏行ID。修改产生的undo保存构建前版本和回滚所需信息。undo不是全行无限复制的概念模型，实际会记录相应字段与操作信息，具体还涉及LOB。

row_vers_build_for_consistent_read读取当前事务ID，反复trx_undo_prev_version_build得到prev_version，再对前版本事务ID调用view->changes_visible。一旦可见，把该版本复制到结果内存；若前版本为空，说明该行在此视图时点尚不存在。记录当前的值不一定就是本次SELECT应返回的值。

版本链的寿命受到最老视图与purge边界约束。不能把“事务提交”画成“undo立即删除”：读者还可能需要它。源码对无法建立历史版本返回DB_MISSING_HISTORY，说明恢复和purge边界有明确不变量。应用长期打开读事务，会让历史积压、空间占用和追链成本持续增长。

![图16：Undo与版本链：UPDATE之前的值在哪里](diagrams/16.svg)

**真实源码窗口：**[storage/innobase/row/row0vers.cc · L1280–L1334](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/row/row0vers.cc#L1280-L1334)。

```cpp
  version = rec;

  for (;;) {
    mem_heap_t *prev_heap = heap;

    heap = mem_heap_create(1024, UT_LOCATION_HERE);

    if (vrow) {
      *vrow = nullptr;
    }

    /* If purge can't see the record then we can't rely on
    the UNDO log record. */

    bool purge_sees =
        trx_undo_prev_version_build(rec, mtr, version, index, *offsets, heap,
                                    &prev_version, nullptr, vrow, 0, lob_undo);

    err = (purge_sees) ? DB_SUCCESS : DB_MISSING_HISTORY;

    if (prev_heap != nullptr) {
      mem_heap_free(prev_heap);
    }

    if (prev_version == nullptr) {
      /* It was a freshly inserted version */
      *old_vers = nullptr;
      ut_ad(!vrow || !(*vrow));
      break;
    }

    *offsets = rec_get_offsets(prev_version, index, *offsets, ULINT_UNDEFINED,
                               UT_LOCATION_HERE, offset_heap);

#if defined UNIV_DEBUG || defined UNIV_BLOB_LIGHT_DEBUG
    ut_a(!rec_offs_any_null_extern(index, prev_version, *offsets));
#endif /* UNIV_DEBUG || UNIV_BLOB_LIGHT_DEBUG */

    trx_id = row_get_rec_trx_id(prev_version, index, *offsets);

    if (view->changes_visible(trx_id, index->table->name)) {
      /* The view already sees this version: we can copy
      it to in_heap and return */

      buf =
          static_cast<byte *>(mem_heap_alloc(in_heap, rec_offs_size(*offsets)));

      *old_vers = rec_copy(buf, prev_version, *offsets);
      rec_offs_make_valid(*old_vers, index, *offsets);

      if (vrow && *vrow) {
        *vrow = dtuple_copy(*vrow, in_heap);
        dtuple_dup_v_fld(*vrow, in_heap);
      }
      break;
```

<a id="chapter-17"></a>

## 17 · ReadView：逐个条件推演可见性

ReadView::prepare记录创建者ID、下一事务ID作为m_low_limit_id、创建时活动读写事务集合m_ids；m_up_limit_id取活动集合最小值或low。名字容易误导：up是“全部可见的低端边界”，low是“全部不可见的高端边界”，不能仅按英文大小猜方向。

changes_visible严格按条件检查：id<up或等于creator直接可见；id>=low不可见；中间区若m_ids为空可见，否则二分查活动集合，不在集合才可见。举例up=100、low=110、ids=[100,105]、creator=108：99可见，100和105不可见，103可见，108自己的版本可见，110不可见。

事务ID100后来提交并不会修改已经创建视图的m_ids，所以老视图仍不能直接看见100的新版本，而是追undo；新视图才重新捕获活动集合。判定条件解释了“提交了别人还看不到”的原因，也解释了自己写入在快照事务中仍可见。ReadView不复制整张表，只存边界和活动事务信息。

![图17：ReadView：逐个条件推演可见性](diagrams/17.svg)

图中每个return均为早返回；只有上一条件未命中才继续下一个判断。最后的活动集合命中意味着不可见，而不是继续向“可见”节点流动。

**真实源码窗口：**[storage/innobase/include/read0types.h · L163–L184](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/include/read0types.h#L163-L184)。

```cpp
  [[nodiscard]] bool changes_visible(trx_id_t id,
                                     const table_name_t &name) const {
    ut_ad(id > 0);

    if (id < m_up_limit_id || id == m_creator_trx_id) {
      return (true);
    }

    check_trx_id_sanity(id, name);

    if (id >= m_low_limit_id) {
      return (false);

    } else if (m_ids.empty()) {
      return (true);
    }

    const ids_t::value_type *p = m_ids.data();

    return (!std::binary_search(p, p + m_ids.size(), id));
  }

```

### 补充证据：ReadView::prepare：边界由活动集合产生

m_ids保存视图创建时的活动读写事务ID，m_up_limit_id取集合首项；m_low_limit_no服务purge，不能拿它替代changes_visible中的m_low_limit_id。

[storage/innobase/read/read0read.cc · L447–L471](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/read/read0read.cc#L447-L471)

```cpp
void ReadView::prepare(trx_id_t id) {
  ut_ad(trx_sys_mutex_own());

  m_creator_trx_id = id;

  m_low_limit_no = trx_get_serialisation_min_trx_no();

  m_low_limit_id = trx_sys_get_next_trx_id_or_no();

  ut_a(m_low_limit_no <= m_low_limit_id);

  if (!trx_sys->rw_trx_ids.empty()) {
    copy_trx_ids(trx_sys->rw_trx_ids);
  } else {
    m_ids.clear();
  }

  /* The first active transaction has the smallest id. */
  m_up_limit_id = !m_ids.empty() ? m_ids.front() : m_low_limit_id;

  ut_a(m_up_limit_id <= m_low_limit_id);

  ut_d(m_view_low_limit_no = m_low_limit_no);
  m_closed = false;
}
```

<a id="chapter-18"></a>

## 18 · RR与RC：快照读取和锁定读取不是一条路

trx_assign_read_view仅在当前事务没有活动视图时调用MVCC::view_open。普通RR事务通常在首次一致性读创建并复用视图，而不是无条件在BEGIN立即拍照；START TRANSACTION WITH CONSISTENT SNAPSHOT是需要单独理解的入口。RC语句边界会关闭相应视图，使下一次一致性读获得更新的快照。

SELECT ... FOR UPDATE和UPDATE属于需要锁协调的访问，不能用一致性读ReadView的结果解释。RR事务可能先读到旧快照，再用锁定读看到较新已提交值，自己的写入也能影响之后结果。这不是隔离实现自相矛盾，而是语句读取模式不同。

同一事务混用两类读取时，业务判定若基于快照读而写入未携带条件或锁，仍可能发生竞态。实验需要两个会话且明确提交顺序；单会话重复SELECT无法证明隔离效果。下文lab记录RR、RC与锁定读的预期变化，实际输出待在目标8.4环境执行确认。

![图18：RR与RC：快照读取和锁定读取不是一条路](diagrams/18.svg)

**真实源码窗口：**[storage/innobase/trx/trx0trx.cc · L2315–L2330](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/trx/trx0trx.cc#L2315-L2330)。

```cpp
ReadView *trx_assign_read_view(trx_t *trx) /*!< in/out: active transaction */
{
  ut_ad(trx_can_be_handled_by_current_thread_or_is_hp_victim(trx));
  ut_ad(trx->state.load(std::memory_order_relaxed) == TRX_STATE_ACTIVE);

  if (srv_read_only_mode) {
    ut_ad(trx->read_view == nullptr);
    return (nullptr);

  } else if (!MVCC::is_view_active(trx->read_view)) {
    trx_sys->mvcc->view_open(trx->read_view, trx);
  }

  return (trx->read_view);
}

```

<a id="chapter-19"></a>

## 19 · 行锁、gap与next-key：锁的是索引范围

lock_rec_lock以mode、block、heap_no、index和事务线程请求记录锁，先走fast path，不满足时slow path处理冲突和等待。记录锁对象通过页与位图定位索引记录，不是把SQL WHERE字符串存起来当锁。扫描路径会影响实际锁住的记录与间隙。

next-key把记录与其前方间隙组合，gap锁保护插入范围。纯gap锁之间可以共存，gap S/X并不像记录S/X那样互斥；它们主要阻止向间隙插入。插入意向锁还要按具体插入位置与已有范围锁判断冲突，不能用“X必定排斥另一把X”解释所有data_locks输出。唯一索引完整等值命中与范围查询、未命中查询的锁行为不能一概而论；隔离级别、访问索引及外键/唯一性检查会改变锁集合。RC通常减少搜索中的gap锁，但仍有约束检查相关例外。

latch短时保护页内存结构，事务锁可能保持到事务结束。慢SQL锁住很多索引项后，其他请求等待不代表某个热点页latch无法释放。使用performance_schema.data_locks/data_lock_waits观察索引名、锁模式、状态和阻塞关系，再把它映射回执行计划与SQL条件。

![图19：行锁、gap与next-key：锁的是索引范围](diagrams/19.svg)

快路径无法处理会进入慢路径，并不直接等于等待。慢路径结合冲突与select_mode决定授予、等待、NOWAIT错误或SKIP LOCKED跳过。

**真实源码窗口：**[storage/innobase/lock/lock0lock.cc · L1936–L1964](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/lock/lock0lock.cc#L1936-L1964)。

```cpp
static dberr_t lock_rec_lock(bool impl, select_mode sel_mode, ulint mode,
                             const buf_block_t *block, ulint heap_no,
                             dict_index_t *index, que_thr_t *thr) {
  ut_ad(locksys::owns_page_shard(block->get_page_id()));
  ut_ad(!srv_read_only_mode);
  ut_ad((LOCK_MODE_MASK & mode) != LOCK_S ||
        lock_table_has(thr_get_trx(thr), index->table, LOCK_IS));
  ut_ad((LOCK_MODE_MASK & mode) != LOCK_X ||
        lock_table_has(thr_get_trx(thr), index->table, LOCK_IX));
  ut_ad((LOCK_MODE_MASK & mode) == LOCK_S || (LOCK_MODE_MASK & mode) == LOCK_X);
  ut_ad(mode - (LOCK_MODE_MASK & mode) == LOCK_GAP ||
        mode - (LOCK_MODE_MASK & mode) == LOCK_REC_NOT_GAP ||
        mode - (LOCK_MODE_MASK & mode) == 0);
  ut_ad(index->is_clustered() || !dict_index_is_online_ddl(index));
  /* Implicit locks are equivalent to LOCK_X|LOCK_REC_NOT_GAP, so we can omit
  creation of explicit lock only if the requested mode was LOCK_REC_NOT_GAP */
  ut_ad(!impl || ((mode & LOCK_REC_NOT_GAP) == LOCK_REC_NOT_GAP));
  /* We try a simplified and faster subroutine for the most
  common cases */
  switch (lock_rec_lock_fast(impl, mode, block, heap_no, index, thr)) {
    case LOCK_REC_SUCCESS:
      return (DB_SUCCESS);
    case LOCK_REC_SUCCESS_CREATED:
      return (DB_SUCCESS_LOCKED_REC);
    case LOCK_REC_FAIL:
      return (
          lock_rec_lock_slow(impl, sel_mode, mode, block, heap_no, index, thr));
    default:
      ut_error;
```

<a id="chapter-20"></a>

## 20 · 死锁检测：等待图和牺牲者选择

两个事务各持有一条记录锁，再请求对方持有的记录，会形成有向等待环。8.4的lock0wait.cc构建等待信息与边，找候选环后重新校验，避免锁状态变化导致误判；不是每次等待都立即认定死锁。

lock_wait_choose_victim比较事务权重，并存在高优先级仲裁。一般倾向选择较小事务回滚，但不应承诺固定回滚“最后来的那个”。事务权重涉及已修改数据和锁数量，且选择需要相应lock_sys保护。检测关闭后仍可由lock wait timeout结束等待，处理时机和错误语义不同。

死锁回滚的是被选事务；普通锁等待超时默认往往只回滚失败语句，完整事务处理还受innodb_rollback_on_timeout等影响。应用捕获1213应重试完整业务事务并控制次数，避免只重跑最后一条UPDATE。统一访问顺序、缩短事务和减少扫描锁范围比增大超时更直接。

![图20：死锁检测：等待图和牺牲者选择](diagrams/20.svg)

**真实源码窗口：**[storage/innobase/lock/lock0wait.cc · L917–L953](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/lock/lock0wait.cc#L917-L953)。

```cpp
static trx_t *lock_wait_choose_victim(
    const ut::vector<uint> &cycle_ids,
    const ut::vector<waiting_trx_info_t> &infos) {
  /* We are iterating over various transactions comparing their trx_weight_ge,
  which is computed based on number of locks held thus we need exclusive latch
  on the whole lock_sys. In theory number of locks should not change while the
  transaction is waiting, but instead of proving that they can not wake up, it
  is easier to assert that we hold the mutex */
  ut_ad(locksys::owns_exclusive_global_latch());
  ut_ad(!cycle_ids.empty());
  trx_t *chosen_victim = nullptr;
  auto sorted_trxs = lock_wait_order_for_choosing_victim(cycle_ids, infos);

  for (auto *trx : sorted_trxs) {
    if (chosen_victim == nullptr) {
      chosen_victim = trx;
      continue;
    }

    if (trx_is_high_priority(chosen_victim) || trx_is_high_priority(trx)) {
      auto victim = trx_arbitrate(trx, chosen_victim);

      if (victim != nullptr) {
        if (victim == trx) {
          chosen_victim = trx;
        } else {
          ut_a(victim == chosen_victim);
        }
        continue;
      }
    }

    if (trx_weight_ge(chosen_victim, trx)) {
      /* The joining transaction is 'smaller',
      choose it as the victim and roll it back. */
      chosen_victim = trx;
    }
```

<a id="chapter-21"></a>

## 21 · 事务提交：内存可见、redo可靠与锁释放

trx_commit_low组织引擎事务提交，trx_commit_in_memory处理内存事务状态、undo历史与锁释放；trx_flush_log_if_needed_low按srv_flush_log_at_trx_commit决定日志写/刷。提交不是一条write系统调用，且binlog开启时Server级协调会改变何时由谁完成持久化等待。

配置1要求写日志并按flush方式保证持久化，配置2写入文件但不在该调用中强制flush，配置0不在此事务提交调用写/刷。后台周期任务提供后续推进，但周期不是严格“一秒最多丢一秒”的实时承诺；调度和硬件都会影响窗口。服务端确认与客户端收到确认也不是同一时间。

rollback需要undo恢复事务修改；已提交修改即使数据页还脏，也由redo提供崩溃重做基础。业务判断COMMIT结果不应依赖连接是否恰好还活着：服务器提交后响应丢失是结果不确定窗口。幂等业务键或事后查询事务结果比简单重试INSERT更可靠。

![图21：事务提交：内存可见、redo可靠与锁释放](diagrams/21.svg)

**真实源码窗口：**[storage/innobase/trx/trx0trx.cc · L1754–L1784](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/trx/trx0trx.cc#L1754-L1784)。

```cpp
static void trx_flush_log_if_needed_low(lsn_t lsn) /*!< in: lsn up to which logs
                                                   are to be flushed. */
{
#ifdef _WIN32
  bool flush = true;
#else
  bool flush = srv_unix_file_flush_method != SRV_UNIX_NOSYNC;
#endif /* _WIN32 */

  Wait_stats wait_stats;

  switch (srv_flush_log_at_trx_commit) {
    case 2:
      /* Write the log but do not flush it to disk */
      flush = false;
      [[fallthrough]];
    case 1:
      /* Write the log and optionally flush it to disk */
      wait_stats = log_write_up_to(*log_sys, lsn, flush);

      MONITOR_INC_WAIT_STATS(MONITOR_TRX_ON_LOG_, wait_stats);

      return;
    case 0:
      /* Do nothing */
      return;
  }
}

/** If required, flushes the log to disk based on the value of
 innodb_flush_log_at_trx_commit. */
```

<a id="chapter-22"></a>

## 22 · Binlog与redo两阶段提交：对齐两个事实

Server的ha_commit_trans根据参与者、读写状态与no_2pc等条件决定是否通过tc_log准备。启用binlog且涉及需要协调的事务时，Server与InnoDB共同维护提交一致性，不能仅按“只有一个存储引擎”判断一定跳过协调。InnoDB trx_prepare_low把undo segment由ACTIVE改为PREPARED，并通过mtr记录此状态。

binlog再写完整事务事件和结束标记，ordered_commit负责flush/sync/commit各阶段。持久化binlog中的提交决定，与InnoDB可恢复的prepared状态结合，让启动恢复能判断悬而未决事务该提交还是回滚。XID服务这次内部协调；GTID标识复制事务，不是InnoDB事务ID或页LSN。

在prepare完成但binlog提交决定未持久化时崩溃，恢复不能随意把prepared事务当已提交；在binlog提交决定持久化后、引擎最终commit未完成时崩溃，则要依据协调日志完成提交。双1配置只是常见持久化要求组合，实际保证还依赖文件系统、硬件与错误策略，不能说“两阶段使任何配置都不丢”。

![图22：Binlog与redo两阶段提交：对齐两个事实](diagrams/22.svg)

这是参与binlog协调事务的成功主线；不是所有只读/空事务、binlog关闭或no_2pc场景的必经步骤。SYNC是否真正同步还受sync_binlog等策略控制。

**真实源码窗口：**[storage/innobase/trx/trx0trx.cc · L2923–L2968](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/trx/trx0trx.cc#L2923-L2968)。

```cpp
static lsn_t trx_prepare_low(
    trx_t *trx,               /*!< in/out: transaction */
    trx_undo_ptr_t *undo_ptr, /*!< in/out: pointer to rollback
                              segment scheduled for prepare. */
    bool noredo_logging)      /*!< in: turn-off redo logging. */
{
  if (undo_ptr->insert_undo != nullptr || undo_ptr->update_undo != nullptr) {
    mtr_t mtr;
    trx_rseg_t *rseg = undo_ptr->rseg;

    mtr_start_sync(&mtr);

    if (noredo_logging) {
      mtr_set_log_mode(&mtr, MTR_LOG_NO_REDO);
    }

    /* Change the undo log segment states from TRX_UNDO_ACTIVE to
    TRX_UNDO_PREPARED: these modifications to the file data
    structure define the transaction as prepared in the file-based
    world, at the serialization point of lsn. */

    rseg->latch();

    if (undo_ptr->insert_undo != nullptr) {
      /* It is not necessary to obtain trx->undo_mutex here
      because only a single OS thread is allowed to do the
      transaction prepare for this transaction. */
      trx_undo_set_state_at_prepare(trx, undo_ptr->insert_undo, false, &mtr);
    }

    if (undo_ptr->update_undo != nullptr) {
      if (!noredo_logging) {
        trx_undo_gtid_set(trx, undo_ptr->update_undo, true);
      }
      trx_undo_set_state_at_prepare(trx, undo_ptr->update_undo, false, &mtr);
    }

    rseg->unlatch();

    /*--------------*/
    /* This mtr commit makes the transaction prepared in
    file-based world. */
    mtr_commit(&mtr);
    /*--------------*/

    if (!noredo_logging) {
```

<a id="chapter-23"></a>

## 23 · 组提交与故障窗口：三阶段不是三次事务

MYSQL_BIN_LOG::ordered_commit用Commit_stage_manager组织队列，每个阶段选leader处理一组THD，followers等待。FLUSH把事务缓存落到binlog文件，SYNC按sync_binlog策略同步，COMMIT按binlog_order_commits等条件完成引擎提交。不同阶段队列可以合并，故一次同步覆盖多个事务。

源码在FLUSH与SYNC间设置crash/debug同步点，恰好提醒“写入文件”还不等于可靠落盘。flush_error与sync_error单独处理，binlog_error_action控制某些错误后的终止策略；仅看函数末尾return 0不足以理解失败路径。opt_binlog_order_commits关闭时，提交阶段走不同线程路径，不能把leader永远提交所有引擎作为无条件事实。

窗口推演：prepare前没有提交决定；prepared但binlog未可靠保存需恢复仲裁；binlog可靠、引擎尚未完成需恢复提交；引擎完成而客户端未收到OK是业务结果不确定。这里不执行kill或断电实验，因为普通发布构建无法直接使用DBUG_SUICIDE。先纸面核对源码时点，再在隔离debug环境进行故障注入。

![图23：组提交与故障窗口：三阶段不是三次事务](diagrams/23.svg)

有序COMMIT队列是条件路径。关闭提交顺序且Clone不要求顺序等情况下，线程通过finish_commit完成对应引擎提交；flush/sync错误与ABORT_SERVER分支应单独追踪。

**真实源码窗口：**[sql/binlog.cc · L9096–L9123](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/binlog.cc#L9096-L9123)。

```cpp
  if (change_stage(thd, Commit_stage_manager::SYNC_STAGE, wait_queue, &LOCK_log,
                   &LOCK_sync)) {
    DBUG_PRINT("return", ("Thread ID: %u, commit_error: %d", thd->thread_id(),
                          thd->commit_error));
    return finish_commit(thd);
  }

  /*
    Shall introduce a delay only if it is going to do sync
    in this ongoing SYNC stage. The "+1" used below in the
    if condition is to count the ongoing sync stage.
    When sync_binlog=0 (where we never do sync in BGC group),
    it is considered as a special case and delay will be executed
    for every group just like how it is done when sync_binlog= 1.
  */
  if (!flush_error && (sync_counter + 1 >= get_sync_period()))
    Commit_stage_manager::get_instance().wait_count_or_timeout(
        opt_binlog_group_commit_sync_no_delay_count,
        opt_binlog_group_commit_sync_delay, Commit_stage_manager::SYNC_STAGE);

  final_queue = Commit_stage_manager::get_instance().fetch_queue_acquire_lock(
      Commit_stage_manager::SYNC_STAGE);

  if (flush_error == 0 && total_bytes > 0) {
    DEBUG_SYNC(thd, "before_sync_binlog_file");
    std::pair<bool, bool> result = sync_binlog_file(false);
    sync_error = result.first;
  }
```

### 补充证据：COMMIT阶段：GTID更新随事务组完成

process_commit_stage_queue在协调日志可靠性检查后调用引擎提交并更新GTID状态。关闭有序提交时要继续读另外分支，不应宣称所有配置都由leader串行完成。

[sql/binlog.cc · L9172–L9197](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/binlog.cc#L9172-L9197)

```cpp
    THD *commit_queue =
        Commit_stage_manager::get_instance().fetch_queue_acquire_lock(
            Commit_stage_manager::COMMIT_STAGE);
    DBUG_EXECUTE_IF("semi_sync_3-way_deadlock",
                    DEBUG_SYNC(thd, "before_process_commit_stage_queue"););

    if (flush_error == 0 && sync_error == 0)
      sync_error = call_after_sync_hook(commit_queue);

    /*
      process_commit_stage_queue will call update_on_commit or
      update_on_rollback for the GTID owned by each thd in the queue.

      This will be done this way to guarantee that GTIDs are added to
      gtid_executed in order, to avoid creating unnecessary temporary
      gaps and keep gtid_executed as a single interval at all times.

      If we allow each thread to call update_on_commit only when they
      are at finish_commit, the GTID order cannot be guaranteed and
      temporary gaps may appear in gtid_executed. When this happen,
      the server would have to add and remove intervals from the
      Gtid_set, and adding and removing intervals requires a mutex,
      which would reduce performance.
    */
    process_commit_stage_queue(thd, commit_queue);

```

### 提交故障窗口对照

| 时点 | 恢复/业务后果 |
|---|---|
| prepare前 | 没有完整提交决定，未完成事务回滚 |
| prepared但binlog决定未可靠保存 | 由协调日志仲裁，不能仅凭prepared提交 |
| binlog提交决定可靠，引擎commit未完成 | 恢复完成提交，对齐两个日志事实 |
| 引擎完成，OK响应丢失 | 数据库已提交，客户端结果不确定，需业务幂等 |

此表假定日志和设备满足对应可靠保存条件，配置放宽、I/O错误或日志损坏应回到具体分支。

<a id="chapter-24"></a>

## 24 · Checkpoint与恢复：日志何时允许复用

checkpoint不是“所有脏页刷完”的瞬间。InnoDB连续评估哪些日志已不再是恢复脏页所必需，结合flush list与近期完成日志信息得到可推进位置。log_update_available_for_checkpoint_lsn先确认m_allow_checkpoints；恢复尚未完成时不信任flush list，不能提前推进。

available_for_checkpoint_lsn只在新值更大时更新，实际checkpoint还受其他约束和保存动作影响。current LSN与checkpoint LSN间距表现恢复/日志复用压力，不等于某个事务尚未提交。redo循环空间要保留还不能覆盖的区间，慢刷页会反过来拖住日志复用并压制前台写入。

recv_recovery_from_checkpoint_start扫描redo、校验块与组边界并组织页恢复；页上的LSN用于判定某物理修改是否已经反映。之后还需处理未完成事务与协调日志，不是只重做就可开放服务。备份恢复不能直接复制运行中的任意ibd文件：一致性点、redo、字典、undo和日志协调共同决定可恢复性。

![图24：Checkpoint与恢复：日志何时允许复用](diagrams/24.svg)

**真实源码窗口：**[storage/innobase/log/log0chkp.cc · L282–L309](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/log/log0chkp.cc#L282-L309)。

```cpp
static void log_update_available_for_checkpoint_lsn(log_t &log) {
  /* Note: log.m_allow_checkpoints is set to true after recovery is finished,
  and changes gathered in recv_sys->metadata_recover are applied to dict_table_t
  objects; or in log_start() if recovery was not needed. We can't trust
  flush lists until recovery is finished, so we must not update lsn available
  for checkpoint (as update would be based on what we can see inside them). */
  if (!log.m_allow_checkpoints.load(std::memory_order_acquire)) {
    return;
  }

  /* Update lsn available for checkpoint. */
  log.recent_closed.advance_tail();
  const lsn_t oldest_lsn = log_compute_available_for_checkpoint_lsn(log);

  log_limits_mutex_enter(log);

  /* 1. The oldest_lsn can decrease in case previously buffer pool flush
        lists were empty and now a new dirty page appeared, which causes
        a maximum delay of log.recent_closed_size being suddenly subtracted.

     2. Race between concurrent log_update_available_for_checkpoint_lsn is
        also possible. */

  if (oldest_lsn > log.available_for_checkpoint_lsn) {
    log.available_for_checkpoint_lsn = oldest_lsn;
  }

  log_limits_mutex_exit(log);
```

### 补充证据：恢复入口：没有可用checkpoint就不能正常重做

恢复初始化flush-list辅助结构，检查force recovery模式，寻找可用checkpoint；找不到会返回DB_ERROR。强制恢复跳过redo是特殊救援模式，不能据此推断正常启动安全性。

[storage/innobase/log/log0recv.cc · L3850–L3875](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/log/log0recv.cc#L3850-L3875)

```cpp
dberr_t recv_recovery_from_checkpoint_start(log_t &log, lsn_t flush_lsn) {
  /* Initialize red-black tree for fast insertions into the
  flush_list during recovery process. */
  buf_flush_init_flush_rbt();

  if (srv_force_recovery >= SRV_FORCE_NO_LOG_REDO) {
    ib::info(ER_IB_MSG_728);

    /* We leave redo log not started and this is read-only mode. */
    ut_a(log.sn == 0);
    ut_a(srv_read_only_mode);

    return DB_SUCCESS;
  }

  recv_recovery_on = true;

  ut_a(log.m_format == Log_format::CURRENT);

  /* Look for the latest checkpoint */
  Log_checkpoint_location checkpoint;
  if (!recv_find_max_checkpoint(log, checkpoint)) {
    ib::error(ER_IB_MSG_RECOVERY_CHECKPOINT_NOT_FOUND);
    return DB_ERROR;
  }

```

<a id="chapter-25"></a>

## 25 · Purge：为什么长事务拖住历史清理

提交后的update undo进入历史清理范围，但只有不再被活动ReadView需要的版本才允许purge。purge线程根据视图边界推进，处理delete-mark记录、二级索引清理与undo历史；它不是把每个已提交事务的undo马上删除。

长时间一致性读固定旧视图，使较新的版本仍须保留。history list length因此增长，磁盘空间、后台清理压力与读追链长度也可能升高。数量指标不是字节数，更不是简单“未提交事务数”。purge赶不上写入与单个老视图钉住边界是两种问题，需要先查最老事务起始时间与状态。

仅杀掉阻塞业务SQL而保留连接事务，可能没有释放ReadView。应确认事务完成或连接回滚。undo tablespace截断与逻辑版本清理也有不同条件，不能期待COMMIT后文件立即变小。实验应观察历史趋势，并在两个会话分别结束读事务后比较，而不以一次状态输出推断持续积压。

![图25：Purge：为什么长事务拖住历史清理](diagrams/25.svg)

**真实源码窗口：**[storage/innobase/trx/trx0purge.cc · L2390–L2423](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/storage/innobase/trx/trx0purge.cc#L2390-L2423)。

```cpp
ulint trx_purge(ulint n_purge_threads, /*!< in: number of purge tasks
                                       to submit to the work queue */
                ulint batch_size,      /*!< in: the maximum number of records
                                       to purge in one batch */
                bool truncate)         /*!< in: truncate history if true */
{
  que_thr_t *thr = nullptr;
  ulint n_pages_handled;

  ut_a(n_purge_threads > 0);

  srv_dml_needed_delay = trx_purge_dml_delay();

  /* The number of tasks submitted should be completed. */
  ut_a(purge_sys->n_submitted == purge_sys->n_completed);

  rw_lock_x_lock(&purge_sys->latch, UT_LOCATION_HERE);

  trx_sys->mvcc->clone_oldest_view(&purge_sys->view);

  rw_lock_x_unlock(&purge_sys->latch);

#ifdef UNIV_DEBUG
  if (srv_purge_view_update_only_debug) {
    return (0);
  }
#endif /* UNIV_DEBUG */

  /* Fetch the UNDO recs that need to be purged. */
  n_pages_handled = trx_purge_attach_undo_recs(n_purge_threads, batch_size);

  /* Submit the tasks to the work queue. */
  for (ulint i = 0; i < n_purge_threads - 1; ++i) {
    thr = que_fork_scheduler_round_robin(purge_sys->query, thr);
```

<a id="chapter-26"></a>

## 26 · 复制与GTID：应用日志不是重放数据页

Classic复制读取source binlog，在replica接收与持久化relay log，然后applier执行事件。apply_event_and_update_pos把事件应用和位点管理联系起来，多线程复制还涉及协调线程、worker及提交顺序；接收进度与执行进度是不同水位。

GTID使用source UUID与事务序列标识事务，gtid_executed描述已执行集合。相同事务可通过集合避免重复执行，但“有GTID”并不意味着数据内容自动一致：过滤、错误跳过、非事务对象或人为修改仍能破坏一致性。复制读取的是binlog事件语义，InnoDB redo则面向本地页恢复，二者不能互当备份。

延迟要区分传输慢、relay积压、worker执行慢与提交依赖等待。Seconds_Behind_Source不是所有故障下都准确的端到端时延。查询performance_schema.replication_applier_status_by_worker的错误、应用事务和时间信息，结合receiver状态判定。8.4使用SOURCE/REPLICA命令，老MASTER/SLAVE术语源码残留不表示文档应该统一沿用。

![图26：复制与GTID：应用日志不是重放数据页](diagrams/26.svg)

**真实源码窗口：**[sql/rpl_replica.cc · L4438–L4477](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/rpl_replica.cc#L4438-L4477)。

```cpp
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
```

<a id="chapter-27"></a>

## 27 · 诊断与实验：把计划、锁和LSN放回同一现场

诊断先构造假设：慢在扫描、锁等待还是持久化？扫描问题看EXPLAIN ANALYZE与rows/loops，锁问题看data_lock_waits/metadata_locks及阻塞事务，持久化问题看redo写/刷、checkpoint与文件I/O等待。每类证据指向不同源码入口，不能从一个“慢查询”结论跳到缓存或加索引。

附带lab.sql建立独立source_lab库，使用显式主键、联合索引及少量数据；sessions.md给出两个会话RR/RC快照、FOR UPDATE、gap等待与死锁调度。SQL与预期是可复现设计，未在本机启动/编译MySQL，也没有伪造EXPLAIN结果。执行前核对SELECT VERSION()和隔离设置。

完成学习时应能连续复述：COM_QUERY建立THD语句状态→解析形成查询块→优化选择访问路径→迭代器Read跨handler→InnoDB游标取页与记录→ReadView或锁决定可读版本→结果返回；写事务另有undo/redo和binlog协调链。复述中如果出现“COMMIT刷全表”“RR等于BEGIN快照”“二级索引永远不回表”，返回对应章重新推演条件。

![图27：诊断与实验：把计划、锁和LSN放回同一现场](diagrams/27.svg)

**真实源码窗口：**[sql/sql_union.cc · L1753–L1780](https://github.com/mysql/mysql-server/blob/dc86e412f18b36ce271f791026714e8caa0ec919/sql/sql_union.cc#L1753-L1780)。

```cpp
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

```

## 源码与官方文档

机制叙述主要来自上述固定源码窗口及其调用上下文，官方文档用于配置和术语核对；没有整段转载官方手册。动态在线手册可能更新，与8.4.0源代码细节有差异时以固定源码说明为准。

- [MySQL官方源码仓库](https://github.com/mysql/mysql-server/tree/dc86e412f18b36ce271f791026714e8caa0ec919)
- [InnoDB多版本机制](https://dev.mysql.com/doc/refman/8.4/en/innodb-multi-versioning.html)
- [Redo日志](https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html)
- [GTID格式与存储](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html)
- [锁与事务](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html)

## 复述与追问

1. 为什么数据页可以比COMMIT更晚刷盘，却不能比相关redo更早可靠写出？
2. ReadView的两个边界和活动事务集合如何判断ID103是否可见？
3. 为什么一个已提交事务的undo仍可能不能purge？
4. 为什么binlog可靠保存后、引擎commit前崩溃，恢复不能一律回滚？
5. 一个LIMIT10的查询为何可能扫描十万行？
6. 为什么metadata lock和data lock要分别查？

答案分别在15/17/25/22–23/07/05与19章。回答应包含字段条件和失败结果，而不是只背定义。
