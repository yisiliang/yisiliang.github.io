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
