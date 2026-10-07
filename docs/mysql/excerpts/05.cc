  if (lock_wait_timeout == 0) {
    /*
      Resort to try_acquire_lock() in case of zero timeout.

      This allows to avoid unnecessary deadlock detection attempt and "fake"
      deadlocks which might result from it.
      In case of failure to acquire lock, try_acquire_lock() preserves
      invariants by updating MDL_lock::fast_path_state and obtrusive locks
      count. It also performs SE notification if needed.
    */
    if (try_acquire_lock(mdl_request)) return true;

    if (!mdl_request->ticket) {
      /* We have failed to acquire lock instantly. */
      DEBUG_SYNC(get_thd(), "mdl_acquire_lock_wait");
      my_error(ER_LOCK_WAIT_TIMEOUT, MYF(0));
      return true;
    }
    return false;
  }

  /* Normal, non-zero timeout case. */

  MDL_lock *lock;
  MDL_ticket *ticket = nullptr;
  struct timespec abs_timeout;
  MDL_wait::enum_wait_status wait_status;
  /* Do some work outside the critical section. */
  set_timespec(&abs_timeout, lock_wait_timeout);

  if (try_acquire_lock_impl(mdl_request, &ticket)) return true;

  if (mdl_request->ticket) {
    /*
      We have managed to acquire lock without waiting.
      MDL_lock, MDL_context and MDL_request were updated
      accordingly, so we can simply return success.
    */
    return false;
  }

  /*
    Our attempt to acquire lock without waiting has failed.
    As a result of this attempt we got MDL_ticket with m_lock
    member pointing to the corresponding MDL_lock object which
    has MDL_lock::m_rwlock write-locked.
  */
  lock = ticket->m_lock;

  lock->m_waiting.add_ticket(ticket);

  /*
    Once we added a pending ticket to the waiting queue,
    we must ensure that our wait slot is empty, so
    that our lock request can be scheduled. Do that in the
    critical section formed by the acquired write lock on MDL_lock.
  */
