buf_block_t *buf_page_get_gen(const page_id_t &page_id,
                              const page_size_t &page_size, ulint rw_latch,
                              buf_block_t *guess, Page_fetch mode,
                              ut::Location location, mtr_t *mtr,
                              bool dirty_with_no_latch) {
#ifdef UNIV_DEBUG
  ut_ad(mtr->is_active());

  ut_ad(rw_latch == RW_S_LATCH || rw_latch == RW_X_LATCH ||
        rw_latch == RW_SX_LATCH || rw_latch == RW_NO_LATCH);

  ut_ad(!ibuf_inside(mtr) ||
        ibuf_page_low(page_id, page_size, false, location, nullptr));

  switch (mode) {
    case Page_fetch::NO_LATCH:
      ut_ad(rw_latch == RW_NO_LATCH);
      break;
    case Page_fetch::NORMAL:
    case Page_fetch::SCAN:
    case Page_fetch::IF_IN_POOL:
    case Page_fetch::PEEK_IF_IN_POOL:
    case Page_fetch::IF_IN_POOL_OR_WATCH:
    case Page_fetch::POSSIBLY_FREED:
    case Page_fetch::POSSIBLY_FREED_NO_READ_AHEAD:
      break;
    default:
      ib::fatal(UT_LOCATION_HERE, ER_IB_ERR_UNKNOWN_PAGE_FETCH_MODE)
          << "Unknown fetch mode: " << (int)mode;
      ut_error;
  }

  bool found;
  const page_size_t &space_page_size =
      fil_space_get_page_size(page_id.space(), &found);

  ut_ad(!found || page_size.equals_to(space_page_size));
#endif /* UNIV_DEBUG */

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
}
