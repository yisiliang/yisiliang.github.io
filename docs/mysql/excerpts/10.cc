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
