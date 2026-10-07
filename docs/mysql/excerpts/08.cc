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
