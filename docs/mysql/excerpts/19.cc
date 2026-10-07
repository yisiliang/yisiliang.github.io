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
