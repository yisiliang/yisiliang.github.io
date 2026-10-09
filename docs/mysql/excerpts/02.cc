static void *handle_connection(void *arg) {
  Global_THD_manager *thd_manager = Global_THD_manager::get_instance();
  Connection_handler_manager *handler_manager =
      Connection_handler_manager::get_instance();
  Channel_info *channel_info = static_cast<Channel_info *>(arg);
  bool pthread_reused [[maybe_unused]] = false;

  if (my_thread_init()) {
    connection_errors_internal++;
    channel_info->send_error_and_close_channel(ER_OUT_OF_RESOURCES, 0, false);
    handler_manager->inc_aborted_connects();
    Connection_handler_manager::dec_connection_count();
    delete channel_info;
    my_thread_exit(nullptr);
    return nullptr;
  }

  for (;;) {
    THD *thd = init_new_thd(channel_info);
    if (thd == nullptr) {
      connection_errors_internal++;
      handler_manager->inc_aborted_connects();
      Connection_handler_manager::dec_connection_count();
      break;  // We are out of resources, no sense in continuing.
    }

#ifdef HAVE_PSI_THREAD_INTERFACE
    if (pthread_reused) {
      /*
        Reusing existing pthread:
        Create new instrumentation for the new THD job,
        and attach it to this running pthread.
      */
      PSI_thread *psi = PSI_THREAD_CALL(new_thread)(key_thread_one_connection,
                                                    0 /* no sequence number */,
                                                    thd, thd->thread_id());
      PSI_THREAD_CALL(set_thread_os_id)(psi);
      PSI_THREAD_CALL(set_thread)(psi);
    }
#endif

#ifdef HAVE_PSI_THREAD_INTERFACE
    /* Find the instrumented thread */
    PSI_thread *psi = PSI_THREAD_CALL(get_thread)();
    /* Save it within THD, so it can be inspected */
    thd->set_psi(psi);
#endif /* HAVE_PSI_THREAD_INTERFACE */
    mysql_thread_set_psi_id(thd->thread_id());
    mysql_thread_set_psi_THD(thd);
    const MYSQL_SOCKET socket =
        thd->get_protocol_classic()->get_vio()->mysql_socket;
    mysql_socket_set_thread_owner(socket);
    thd_manager->add_thd(thd);

    if (thd_prepare_connection(thd))
      handler_manager->inc_aborted_connects();
    else {
      while (thd_connection_alive(thd)) {
        if (do_command(thd)) break;
      }
      end_connection(thd);
    }
    close_connection(thd, 0, false, false);

    thd->get_stmt_da()->reset_diagnostics_area();
    thd->release_resources();

    // Clean up errors now, before possibly waiting for a new connection.
#if OPENSSL_VERSION_NUMBER < 0x10100000L
    ERR_remove_thread_state(nullptr);
#endif /* OPENSSL_VERSION_NUMBER < 0x10100000L */
    thd_manager->remove_thd(thd);
    Connection_handler_manager::dec_connection_count();

#ifdef HAVE_PSI_THREAD_INTERFACE
    /* Stop telemetry, while THD is still available. */
    if (psi != nullptr) {
      PSI_THREAD_CALL(abort_telemetry)(psi);
    }

    /* Decouple THD and the thread instrumentation. */
    thd->set_psi(nullptr);
    mysql_thread_set_psi_THD(nullptr);
#endif /* HAVE_PSI_THREAD_INTERFACE */

    delete thd;

#ifdef HAVE_PSI_THREAD_INTERFACE
    /* Delete the instrumentation for the job that just completed. */
    PSI_THREAD_CALL(delete_current_thread)();
#endif /* HAVE_PSI_THREAD_INTERFACE */

    // Server is shutting down so end the pthread.
    if (connection_events_loop_aborted()) break;

    channel_info = Per_thread_connection_handler::block_until_new_connection();
    if (channel_info == nullptr) break;
    pthread_reused = true;
    if (connection_events_loop_aborted()) {
      // Close the channel and exit as server is undergoing shutdown.
      channel_info->send_error_and_close_channel(ER_SERVER_SHUTDOWN, 0, false);
      delete channel_info;
      channel_info = nullptr;
      Connection_handler_manager::dec_connection_count();
      break;
    }
  }

  my_thread_end();
  my_thread_exit(nullptr);
  return nullptr;
}
