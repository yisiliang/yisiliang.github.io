/** Splits an index page to halves and inserts the tuple. It is assumed
 that mtr holds an x-latch to the index tree. NOTE: the tree x-latch is
 released within this function! NOTE that the operation of this
 function must always succeed, we cannot reverse it: therefore enough
 free disk space (2 pages) must be guaranteed to be available before
 this function is called.
 @return inserted record */
rec_t *btr_page_split_and_insert(
    uint32_t flags,        /*!< in: undo logging and locking flags */
    btr_cur_t *cursor,     /*!< in: cursor at which to insert; when the
                           function returns, the cursor is positioned
                           on the predecessor of the inserted record */
    ulint **offsets,       /*!< out: offsets on inserted record */
    mem_heap_t **heap,     /*!< in/out: pointer to memory heap, or NULL */
    const dtuple_t *tuple, /*!< in: tuple to insert */
    mtr_t *mtr)            /*!< in: mtr */
{
  buf_block_t *block;
  page_t *page;
  page_zip_des_t *page_zip;
  page_no_t page_no;
  byte direction;
  page_no_t hint_page_no;
  buf_block_t *new_block;
  page_t *new_page;
  page_zip_des_t *new_page_zip;
  rec_t *split_rec;
  buf_block_t *left_block;
  buf_block_t *right_block;
  buf_block_t *insert_block;
  page_cur_t *page_cursor;
  rec_t *first_rec;
  byte *buf = nullptr; /* remove warning */
  rec_t *move_limit;
  bool insert_will_fit;
  bool insert_left;
  ulint n_iterations = 0;
  rec_t *rec;
  ulint n_uniq;
  dict_index_t *index;

  index = cursor->index;

  if (dict_index_is_spatial(index)) {
    /* Split rtree page and update parent */
    return (
        rtr_page_split_and_insert(flags, cursor, offsets, heap, tuple, mtr));
  }

  if (!*heap) {
    *heap = mem_heap_create(1024, UT_LOCATION_HERE);
  }
  n_uniq = dict_index_get_n_unique_in_tree(cursor->index);
func_start:
  ut_ad(tuple->m_heap != *heap);
  mem_heap_empty(*heap);
  *offsets = nullptr;

  ut_ad(mtr_memo_contains_flagged(mtr, dict_index_get_lock(cursor->index),
                                  MTR_MEMO_X_LOCK | MTR_MEMO_SX_LOCK) ||
        cursor->index->table->is_intrinsic());
  ut_ad(!dict_index_is_online_ddl(cursor->index) || (flags & BTR_CREATE_FLAG) ||
        cursor->index->is_clustered());
  ut_ad(rw_lock_own_flagged(dict_index_get_lock(cursor->index),
                            RW_LOCK_FLAG_X | RW_LOCK_FLAG_SX) ||
        cursor->index->table->is_intrinsic());

  block = btr_cur_get_block(cursor);
  page = buf_block_get_frame(block);
  page_zip = buf_block_get_page_zip(block);

  ut_ad(
      mtr_is_block_fix(mtr, block, MTR_MEMO_PAGE_X_FIX, cursor->index->table));
  ut_ad(!page_is_empty(page));

  /* try to insert to the next page if possible before split */
  rec =
      btr_insert_into_right_sibling(flags, cursor, offsets, *heap, tuple, mtr);

  if (rec != nullptr) {
    return (rec);
  }

  page_no = block->page.id.page_no();

  /* 1. Decide the split record; split_rec == NULL means that the
  tuple to be inserted should be the first record on the upper
  half-page */
  insert_left = false;

  if (n_iterations > 0) {
    direction = FSP_UP;
    hint_page_no = page_no + 1;
    split_rec = btr_page_get_split_rec(cursor, tuple);

    if (split_rec == nullptr) {
      insert_left =
          btr_page_tuple_smaller(cursor, tuple, offsets, n_uniq, heap);
    }
  } else if (btr_page_get_split_rec_to_right(cursor, &split_rec)) {
    direction = FSP_UP;
    hint_page_no = page_no + 1;

  } else if (btr_page_get_split_rec_to_left(cursor, &split_rec)) {
    direction = FSP_DOWN;
    hint_page_no = page_no - 1;
    ut_ad(split_rec);
  } else {
    direction = FSP_UP;
    hint_page_no = page_no + 1;

    /* If there is only one record in the index page, we
    can't split the node in the middle by default. We need
    to determine whether the new record will be inserted
    to the left or right. */

    if (page_get_n_recs(page) > 1) {
      split_rec = page_get_middle_rec(page);
    } else if (btr_page_tuple_smaller(cursor, tuple, offsets, n_uniq, heap)) {
      split_rec = page_rec_get_next(page_get_infimum_rec(page));
    } else {
      split_rec = nullptr;
    }
  }

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
    insert_will_fit =
        !new_page_zip &&
        btr_page_insert_fits(cursor, split_rec, offsets, tuple, heap);
  } else {
    if (!insert_left) {
      ut::delete_arr(buf);
      buf = nullptr;
    }

    insert_will_fit =
        !new_page_zip &&
        btr_page_insert_fits(cursor, nullptr, offsets, tuple, heap);
  }

  if (!srv_read_only_mode && !cursor->index->table->is_intrinsic() &&
      insert_will_fit && page_is_leaf(page) &&
      !dict_index_is_online_ddl(cursor->index)) {
    mtr->memo_release(dict_index_get_lock(cursor->index),
                      MTR_MEMO_X_LOCK | MTR_MEMO_SX_LOCK);

    /* NOTE: We cannot release root block latch here, because it
    has segment header and already modified in most of cases.*/
  }

  /* 5. Move then the records to the new page */
  if (direction == FSP_DOWN) {
    /*          fputs("Split left\n", stderr); */

    if (false
#ifdef UNIV_ZIP_COPY
        || page_zip
#endif /* UNIV_ZIP_COPY */
        || !page_move_rec_list_start(new_block, block, move_limit,
                                     cursor->index, mtr)) {
      /* For some reason, compressing new_page failed,
      even though it should contain fewer records than
      the original page.  Copy the page byte for byte
      and then delete the records from both pages
      as appropriate.  Deleting will always succeed. */
      ut_a(new_page_zip);

      page_zip_copy_recs(new_page_zip, new_page, page_zip, page, cursor->index,
                         mtr);
      page_delete_rec_list_end(move_limit - page + new_page, new_block,
                               cursor->index, ULINT_UNDEFINED, ULINT_UNDEFINED,
                               mtr);

      /* Update the lock table and possible hash index. */

      if (!dict_table_is_locking_disabled(cursor->index->table)) {
        lock_move_rec_list_start(new_block, block, move_limit,
                                 new_page + PAGE_NEW_INFIMUM);
      }

      btr_search_update_hash_on_move(new_block, block, cursor->index);

      /* Delete the records from the source page. */

      page_delete_rec_list_start(move_limit, block, cursor->index, mtr);
    }

    left_block = new_block;
    right_block = block;

    if (!dict_table_is_locking_disabled(cursor->index->table)) {
      lock_update_split_left(right_block, left_block);
    }
  } else {
    /*          fputs("Split right\n", stderr); */

    if (false
#ifdef UNIV_ZIP_COPY
        || page_zip
#endif /* UNIV_ZIP_COPY */
        || !page_move_rec_list_end(new_block, block, move_limit, cursor->index,
                                   mtr)) {
      /* For some reason, compressing new_page failed,
      even though it should contain fewer records than
      the original page.  Copy the page byte for byte
      and then delete the records from both pages
      as appropriate.  Deleting will always succeed. */
      ut_a(new_page_zip);

      page_zip_copy_recs(new_page_zip, new_page, page_zip, page, cursor->index,
                         mtr);
      page_delete_rec_list_start(move_limit - page + new_page, new_block,
                                 cursor->index, mtr);

      /* Update the lock table and possible hash index. */
      if (!dict_table_is_locking_disabled(cursor->index->table)) {
        lock_move_rec_list_end(new_block, block, move_limit);
      }

      ut_ad(!dict_index_is_spatial(index));

      btr_search_update_hash_on_move(new_block, block, cursor->index);

      /* Delete the records from the source page. */

      page_delete_rec_list_end(move_limit, block, cursor->index,
                               ULINT_UNDEFINED, ULINT_UNDEFINED, mtr);
    }

    left_block = block;
    right_block = new_block;

    if (!dict_table_is_locking_disabled(cursor->index->table)) {
      lock_update_split_right(right_block, left_block);
    }
  }

#ifdef UNIV_ZIP_DEBUG
  if (page_zip) {
    ut_a(page_zip_validate(page_zip, page, cursor->index));
    ut_a(page_zip_validate(new_page_zip, new_page, cursor->index));
  }
#endif /* UNIV_ZIP_DEBUG */

  /* At this point, split_rec, move_limit and first_rec may point
  to garbage on the old page. */

  /* 6. The split and the tree modification is now completed. Decide the
  page where the tuple should be inserted */

  if (insert_left) {
    insert_block = left_block;
  } else {
    insert_block = right_block;
  }

  /* 7. Reposition the cursor for insert and try insertion */
  page_cursor = btr_cur_get_page_cur(cursor);

  page_cur_search(insert_block, cursor->index, tuple, page_cursor);

  rec = page_cur_tuple_insert(page_cursor, tuple, cursor->index, offsets, heap,
                              mtr);

#ifdef UNIV_ZIP_DEBUG
  {
    page_t *insert_page = buf_block_get_frame(insert_block);

    page_zip_des_t *insert_page_zip = buf_block_get_page_zip(insert_block);

    ut_a(!insert_page_zip ||
         page_zip_validate(insert_page_zip, insert_page, cursor->index));
  }
#endif /* UNIV_ZIP_DEBUG */

  if (rec != nullptr) {
    goto func_exit;
  }

  /* 8. If insert did not fit, try page reorganization.
  For compressed pages, page_cur_tuple_insert() will have
  attempted this already. */

  if (page_cur_get_page_zip(page_cursor) ||
      !btr_page_reorganize(page_cursor, cursor->index, mtr)) {
    goto insert_failed;
  }

  rec = page_cur_tuple_insert(page_cursor, tuple, cursor->index, offsets, heap,
                              mtr);

  if (rec == nullptr) {
    /* The insert did not fit on the page: loop back to the
    start of the function for a new split */
  insert_failed:
    /* We play safe and reset the free bits for new_page */
    if (!cursor->index->is_clustered() &&
        !cursor->index->table->is_temporary()) {
      ibuf_reset_free_bits(new_block);
      ibuf_reset_free_bits(block);
    }

    n_iterations++;
    ut_ad(n_iterations < 2 || buf_block_get_page_zip(insert_block));
    ut_ad(!insert_will_fit);

    goto func_start;
  }

func_exit:
  /* Insert fit on the page: update the free bits for the
  left and right pages in the same mtr */

  if (!cursor->index->is_clustered() && !cursor->index->table->is_temporary() &&
      page_is_leaf(page)) {
    ibuf_update_free_bits_for_two_pages_low(left_block, right_block, mtr);
  }

  MONITOR_INC(MONITOR_INDEX_SPLIT);

  ut_ad(page_validate(buf_block_get_frame(left_block), cursor->index));
  ut_ad(page_validate(buf_block_get_frame(right_block), cursor->index));

  ut_ad(!rec || rec_offs_validate(rec, cursor->index, *offsets));
  return (rec);
}
