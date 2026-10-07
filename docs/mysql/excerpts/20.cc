static trx_t *lock_wait_choose_victim(
    const ut::vector<uint> &cycle_ids,
    const ut::vector<waiting_trx_info_t> &infos) {
  /* We are iterating over various transactions comparing their trx_weight_ge,
  which is computed based on number of locks held thus we need exclusive latch
  on the whole lock_sys. In theory number of locks should not change while the
  transaction is waiting, but instead of proving that they can not wake up, it
  is easier to assert that we hold the mutex */
  ut_ad(locksys::owns_exclusive_global_latch());
  ut_ad(!cycle_ids.empty());
  trx_t *chosen_victim = nullptr;
  auto sorted_trxs = lock_wait_order_for_choosing_victim(cycle_ids, infos);

  for (auto *trx : sorted_trxs) {
    if (chosen_victim == nullptr) {
      chosen_victim = trx;
      continue;
    }

    if (trx_is_high_priority(chosen_victim) || trx_is_high_priority(trx)) {
      auto victim = trx_arbitrate(trx, chosen_victim);

      if (victim != nullptr) {
        if (victim == trx) {
          chosen_victim = trx;
        } else {
          ut_a(victim == chosen_victim);
        }
        continue;
      }
    }

    if (trx_weight_ge(chosen_victim, trx)) {
      /* The joining transaction is 'smaller',
      choose it as the victim and roll it back. */
      chosen_victim = trx;
    }
