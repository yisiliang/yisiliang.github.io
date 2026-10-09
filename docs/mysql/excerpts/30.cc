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

  const auto checkpoint_file = log.m_files.find(checkpoint.m_checkpoint_lsn);

  /* When reading checkpoints from redo log files, error would be reported
  if checkpoint_lsn was outside the redo log file from which it was read,
  and such file would be skipped. If no checkpoint was found because of that,
  then recv_find_max_checkpoint would return false. Therefore here we know
  that InnoDB found a valid checkpoint (for which there is a redo log file
  which contains the checkpoint_lsn). */
  if (checkpoint_file == log.m_files.end()) {
    ut_d(ut_error);
    ut_o(return DB_ERROR);
  }

  log.last_checkpoint_lsn.store(checkpoint.m_checkpoint_lsn);

  const auto file_path = log_file_path(log.m_files_ctx, checkpoint_file->m_id);
  ib::info(ER_IB_MSG_LOG_CHECKPOINT_FOUND,
           ulonglong{checkpoint.m_checkpoint_lsn}, file_path.c_str());

  Log_checkpoint_header checkpoint_header;

  auto checkpoint_file_handle =
      checkpoint_file->open(Log_file_access_mode::READ_ONLY);

  if (!checkpoint_file_handle.is_open()) {
    return DB_CANNOT_OPEN_FILE;
  }

  dberr_t err = log_checkpoint_header_read(checkpoint_file_handle,
                                           checkpoint.m_checkpoint_header_no,
                                           checkpoint_header);
  if (err != DB_SUCCESS) {
    return err;
  }

  checkpoint_file_handle.close();

  const lsn_t checkpoint_lsn = checkpoint.m_checkpoint_lsn;

  ut_a(checkpoint_lsn == checkpoint_header.m_checkpoint_lsn);

  /* Start reading the log from the checkpoint LSN up. */

  ut_ad(RECV_SCAN_SIZE <= log.buf_size);

  ut_ad(recv_sys->n_addrs == 0);

  /* NOTE: we always do a 'recovery' at startup, but only if
  there is something wrong we will print a message to the
  user about recovery: */

  if (checkpoint_lsn != flush_lsn) {
    if (checkpoint_lsn < flush_lsn) {
      ib::warn(ER_IB_MSG_RECOVERY_CHECKPOINT_FROM_BEFORE_CLEAN_SHUTDOWN,
               ulonglong{checkpoint_lsn}, ulonglong{flush_lsn});
    }

    if (!recv_needed_recovery) {
      ib::info(ER_IB_MSG_RECOVERY_IS_NEEDED, ulonglong{flush_lsn},
               ulonglong{checkpoint_lsn});

      if (srv_read_only_mode) {
        ib::error(ER_IB_MSG_RECOVERY_IN_READ_ONLY);

        return DB_ERROR;
      }

      recv_init_crash_recovery();
    }
  }

  err = recv_recovery_begin(log, checkpoint_lsn);
  if (err != DB_SUCCESS) {
    return err;
  }

  if (srv_read_only_mode && log.m_scanned_lsn > checkpoint_lsn) {
    ib::error(ER_IB_MSG_RECOVERY_IN_READ_ONLY);
    return DB_ERROR;
  }

  lsn_t recovered_lsn;

  recovered_lsn = recv_sys->recovered_lsn;

  ut_a(recv_needed_recovery || checkpoint_lsn == recovered_lsn);

  ut_a(!srv_read_only_mode || !recv_needed_recovery);
  ut_a(!srv_read_only_mode || checkpoint_lsn == recovered_lsn);

  log.recovered_lsn = recovered_lsn;

  ut_a(log.m_files.find(recovered_lsn) != log.m_files.end());

  /* If it is at block boundary, add header size. */
  auto check_scanned_lsn = log.m_scanned_lsn;
  if (check_scanned_lsn % OS_FILE_LOG_BLOCK_SIZE == 0) {
    check_scanned_lsn += LOG_BLOCK_HDR_SIZE;
  }

  if (check_scanned_lsn < checkpoint_lsn ||
      check_scanned_lsn < recv_max_page_lsn) {
    ib::error(ER_IB_MSG_737, ulonglong{log.m_scanned_lsn},
              ulonglong{checkpoint_lsn}, ulonglong{recv_max_page_lsn});
  }

  if (recovered_lsn < checkpoint_lsn) {
    /* No harm in trying to do RO access. */
    if (!srv_read_only_mode) {
      ut_error;
    }

    return DB_ERROR;
  }

  if ((recv_sys->found_corrupt_log && srv_force_recovery == 0) ||
      recv_sys->found_corrupt_fs) {
    return DB_ERROR;
  }

  /* Disallow checkpoints until recovery is finished, and changes gathered
  in recv_sys->metadata_recover (dict_metadata) are transferred to
  dict_table_t objects (happens in srv0start.cc). */

  err = log_start(log, checkpoint_lsn, recovered_lsn, false);
  if (err != DB_SUCCESS) {
    return err;
  }

  /* Make the preservation of max checkpoint info on disk certain by writing
  the checkpoint also to the other checkpoint header. After that both headers
  will have the same checkpoint_lsn. This is an extra protection in case next
  checkpoint write will become corrupted because of crash during the write. */

  if (!srv_read_only_mode) {
    log.next_checkpoint_header_no =
        log_next_checkpoint_header(checkpoint.m_checkpoint_header_no);

    err = log_files_next_checkpoint(log, checkpoint_lsn);
    if (err != DB_SUCCESS) {
      return err;
    }
  }

  mutex_enter(&recv_sys->mutex);
  recv_sys->apply_log_recs = true;
  mutex_exit(&recv_sys->mutex);

  /* The database is now ready to start almost normal processing of user
  transactions: transaction rollbacks and the application of the log
  records in the hash table can be run in background. */

  return DB_SUCCESS;
}
