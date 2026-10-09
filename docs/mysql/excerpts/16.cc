/** Constructs the version of a clustered index record which a consistent
 read should see. We assume that the trx id stored in rec is such that
 the consistent read should not see rec in its present version.
 @param[in]   rec   record in a clustered index; the caller must have a latch
                    on the page; this latch locks the top of the stack of
                    versions of this records
 @param[in]   mtr   mtr holding the latch on rec; it will also hold the latch
                    on purge_view
 @param[in]   index   the clustered index
 @param[in]   offsets   offsets returned by rec_get_offsets(rec, index)
 @param[in]   view   the consistent read view
 @param[in,out]   offset_heap   memory heap from which the offsets are
                                allocated
 @param[in]   in_heap   memory heap from which the memory for *old_vers is
                        allocated; memory for possible intermediate versions
                        is allocated and freed locally within the function
 @param[out]   old_vers   old version, or NULL if the history is missing or
                          the record does not exist in the view, that is, it
                          was freshly inserted afterwards.
 @param[out]   vrow   reports virtual column info if any
 @param[in]   lob_undo   undo log to be applied to blobs.
 @return DB_SUCCESS or DB_MISSING_HISTORY */
dberr_t row_vers_build_for_consistent_read(
    const rec_t *rec, mtr_t *mtr, dict_index_t *index, ulint **offsets,
    ReadView *view, mem_heap_t **offset_heap, mem_heap_t *in_heap,
    rec_t **old_vers, const dtuple_t **vrow, lob::undo_vers_t *lob_undo) {
  DBUG_TRACE;
  const rec_t *version;
  rec_t *prev_version;
  trx_id_t trx_id;
  mem_heap_t *heap = nullptr;
  byte *buf;
  dberr_t err;

  ut_ad(index->is_clustered());
  ut_ad(mtr_memo_contains_page(mtr, rec, MTR_MEMO_PAGE_X_FIX) ||
        mtr_memo_contains_page(mtr, rec, MTR_MEMO_PAGE_S_FIX));
  ut_ad(!rw_lock_own(&(purge_sys->latch), RW_LOCK_S));

  ut_ad(rec_offs_validate(rec, index, *offsets));

  trx_id = row_get_rec_trx_id(rec, index, *offsets);

  /* Reset the collected LOB undo information. */
  if (lob_undo != nullptr) {
    lob_undo->reset();
  }

  ut_ad(!view->changes_visible(trx_id, index->table->name));

  ut_ad(!vrow || !(*vrow));

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
    }

    version = prev_version;
  }

  mem_heap_free(heap);

  return err;
}
