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

