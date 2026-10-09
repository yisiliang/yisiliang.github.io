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
}
