ulint trx_purge(ulint n_purge_threads, /*!< in: number of purge tasks
                                       to submit to the work queue */
                ulint batch_size,      /*!< in: the maximum number of records
                                       to purge in one batch */
                bool truncate)         /*!< in: truncate history if true */
{
  que_thr_t *thr = nullptr;
  ulint n_pages_handled;

  ut_a(n_purge_threads > 0);

  srv_dml_needed_delay = trx_purge_dml_delay();

  /* The number of tasks submitted should be completed. */
  ut_a(purge_sys->n_submitted == purge_sys->n_completed);

  rw_lock_x_lock(&purge_sys->latch, UT_LOCATION_HERE);

  trx_sys->mvcc->clone_oldest_view(&purge_sys->view);

  rw_lock_x_unlock(&purge_sys->latch);

#ifdef UNIV_DEBUG
  if (srv_purge_view_update_only_debug) {
    return (0);
  }
#endif /* UNIV_DEBUG */

  /* Fetch the UNDO recs that need to be purged. */
  n_pages_handled = trx_purge_attach_undo_recs(n_purge_threads, batch_size);

  /* Submit the tasks to the work queue. */
  for (ulint i = 0; i < n_purge_threads - 1; ++i) {
    thr = que_fork_scheduler_round_robin(purge_sys->query, thr);
