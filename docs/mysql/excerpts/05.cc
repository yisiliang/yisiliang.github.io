/**
  Acquire one lock with waiting for conflicting locks to go away if needed.

  @param [in,out] mdl_request Lock request object for lock to be acquired

  @param lock_wait_timeout Seconds to wait before timeout.

  @retval  false   Success. MDL_request::ticket points to the ticket
                   for the lock.
  @retval  true    Failure (Out of resources or waiting is aborted),
*/

bool MDL_context::acquire_lock(MDL_request *mdl_request,
                               Timeout_type lock_wait_timeout) {
  // in order to test bug#34594035 call functions that before the fix
  // caused crash and return failure
  DBUG_EXECUTE_IF("bug34594035_fail_acl_cache_lock",
                  debug_sync(get_thd(), "123", 3);
                  mysql_prlock_wrlock(&m_LOCK_waiting_for);
                  mysql_prlock_unlock(&m_LOCK_waiting_for);
                  DBUG_SET("-d,bug34594035_fail_acl_cache_lock"); return true;);

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
  m_wait.reset_status();

  if (lock->needs_notification(ticket)) lock->notify_conflicting_locks(this);

  mysql_prlock_unlock(&lock->m_rwlock);

#ifdef HAVE_PSI_METADATA_INTERFACE
  PSI_metadata_locker_state state;
  PSI_metadata_locker *locker = nullptr;

  if (ticket->m_psi != nullptr) {
    locker = PSI_METADATA_CALL(start_metadata_wait)(&state, ticket->m_psi,
                                                    __FILE__, __LINE__);
  }
#endif

  will_wait_for(ticket);

  /* There is a shared or exclusive lock on the object. */
  DEBUG_SYNC(get_thd(), "mdl_acquire_lock_wait");

  /*
    Avoid deadlock detection in case when we are sure that introduction of
    pending lock hasn't introduced new deadlocks, because pending lock
    of this type doesn't block acquisition of other locks and there are
    no existing waiters for this context.

    We do this for specific case when we try to acquire S lock on ACL_CACHE
    singleton. While being singleton this lock is acquired by each connection
    attempt and in some cases even by each statement, so on systems with many
    connections deadlock detection can get really expensive.

    Doing the same in a general case is non-trivial (whether addition of
    pending request will create more waiters depends on situation with
    max_write_lock_count at least for object locks) and is likely to provide
    less benefits.

    There is another optimization for case when we try to acquire S lock on
    ACL_CACHE singleton and there are MDL waiters for this context.
    In this case we delay deadlock detection for 1 second in the hope that
    our request will be granted before that and the deadlock detection
    will be skipped. Note that this should be most common case as ACL_CACHE
    lock is supposed to be held for short periods only. If threads acquiring
    S lock on ACL_CACHE have to wait for more than 1 second, then the system
    is likely to be trouble (as it means more than 1 second stalls for any
    statement doing privilege checks).

    We don't apply this optimization in cases when locks are acquired on
    behalf of replication applier with commit order waits, as deadlocks
    are likely in such situation and it is better to detect it ASAP.
  */
  bool delayed_find_deadlock = false;
  if (lock->key.mdl_namespace() != MDL_key::ACL_CACHE ||
      ticket->m_type != MDL_SHARED ||
      get_owner()->might_have_commit_order_waiters()) {
    find_deadlock();
  } else if (has_locks()) {
    // Locks in ACL_CACHE namespace always need connection check, so
    assert(lock->needs_connection_check());
    delayed_find_deadlock = true;
  }

  if (lock->needs_notification(ticket) || lock->needs_connection_check()) {
    struct timespec abs_shortwait;
    set_timespec(&abs_shortwait, 1);
    wait_status = MDL_wait::WS_EMPTY;

    while (cmp_timespec(&abs_shortwait, &abs_timeout) <= 0) {
      /* abs_timeout is far away. Wait a short while and notify locks. */
      wait_status = m_wait.timed_wait(m_owner, &abs_shortwait, false,
                                      mdl_request->key.get_wait_state_name());

      if (wait_status != MDL_wait::WS_EMPTY) break;

      if (lock->needs_connection_check() && !m_owner->is_connected()) {
        /*
          If this is user-level lock and the client is disconnected don't wait
          forever: assume it's the same as statement being killed (this differs
          from pre-5.7 where we treat it as timeout, but is more logical).
          Using MDL_wait::set_status() to set status atomically wastes one
          condition variable wake up but should happen rarely.
          We don't want to do this check for all types of metadata locks since
          in general case we may want to complete wait/operation even when
          connection is lost (e.g. in case of logging into slow/general log).
        */
        if (!m_wait.set_status(MDL_wait::KILLED))
          wait_status = MDL_wait::KILLED;
        break;
      }

      if (lock->needs_notification(ticket)) {
        mysql_prlock_wrlock(&lock->m_rwlock);
        lock->notify_conflicting_locks(this);
        mysql_prlock_unlock(&lock->m_rwlock);
      }

      if (delayed_find_deadlock) {
        find_deadlock();
        delayed_find_deadlock = false;
      }

      set_timespec(&abs_shortwait, 1);
    }
    if (wait_status == MDL_wait::WS_EMPTY)
      wait_status = m_wait.timed_wait(m_owner, &abs_timeout, true,
                                      mdl_request->key.get_wait_state_name());
  } else {
    wait_status = m_wait.timed_wait(m_owner, &abs_timeout, true,
                                    mdl_request->key.get_wait_state_name());
  }

  done_waiting_for();

#ifdef HAVE_PSI_METADATA_INTERFACE
  if (locker != nullptr) {
    PSI_METADATA_CALL(end_metadata_wait)(locker, 0);
  }
#endif

  if (wait_status != MDL_wait::GRANTED) {
    lock->remove_ticket(this, m_pins, &MDL_lock::m_waiting, ticket);

    /*
      If SEs were notified about impending lock acquisition, the failure
      to acquire it requires the same notification as lock release.
    */
    if (ticket->m_hton_notified) {
      mysql_mdl_set_status(ticket->m_psi, MDL_ticket::POST_RELEASE_NOTIFY);
      m_owner->notify_hton_post_release_exclusive(&mdl_request->key);
    }

    MDL_ticket::destroy(ticket);
    switch (wait_status) {
      case MDL_wait::VICTIM:
        my_error(ER_LOCK_DEADLOCK, MYF(0));
        break;
      case MDL_wait::TIMEOUT:
        my_error(ER_LOCK_WAIT_TIMEOUT, MYF(0));
        break;
      case MDL_wait::KILLED:
        if (get_owner()->is_killed() == ER_QUERY_TIMEOUT)
          my_error(ER_QUERY_TIMEOUT, MYF(0));
        else
          my_error(ER_QUERY_INTERRUPTED, MYF(0));
        break;
      default:
        assert(0);
        break;
    }
    return true;
  }

  /*
    We have been granted our request.
    State of MDL_lock object is already being appropriately updated by a
    concurrent thread (@sa MDL_lock:reschedule_waiters()).
    So all we need to do is to update MDL_context and MDL_request objects.
  */
  assert(wait_status == MDL_wait::GRANTED);

  m_ticket_store.push_front(mdl_request->duration, ticket);
  mdl_request->ticket = ticket;

  mysql_mdl_set_status(ticket->m_psi, MDL_ticket::GRANTED);

  return false;
}
