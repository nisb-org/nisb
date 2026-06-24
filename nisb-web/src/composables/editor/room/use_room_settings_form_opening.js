export function use_room_settings_form_opening({
  props,
  callTool,
  room_store,
  room_id_value,
  form,
  show_federation_section,
  can_manage_federation,
  can_issue_federation_invite,
  workspace_options_error,
  supervisor_skills_error,
  supervisor_skills_result,
  current_room_join_key,
  reset_federation_state,
  apply_p6_test_control_to_room_store,
  read_p6_test_control_session,
  fill_form_from_store,
  load_workspace_options,
  hydrate_workspace_snapshot_for_form,
  refresh_supervisor_skills,
  ensure_room_join_key,
  refresh_federation_peers,
  refresh_federation_room_invites,
  refresh_federation_joined_members,
}) {
  async function open_room_settings_form() {
    workspace_options_error.value = ''
    supervisor_skills_error.value = ''
    supervisor_skills_result.value = {}
    reset_federation_state()

    if (room_id_value.value) {
      await room_store.refreshRoomInfo(callTool, room_id_value.value)
      const cached_p6 = read_p6_test_control_session(room_id_value.value)
      if (Object.keys(cached_p6).length) {
        apply_p6_test_control_to_room_store(room_id_value.value, cached_p6)
      }
    }

    fill_form_from_store()
    await load_workspace_options()

    if (form.workspace_id) {
      await hydrate_workspace_snapshot_for_form(form.workspace_id)
    }

    if (String(form.workspace_id || '').trim() && String(form.focus_root || '').trim()) {
      await refresh_supervisor_skills({
        sync_local_from_saved: true,
        force_sync_local: true,
      })
    }

    if (room_id_value.value) {
      try {
        await ensure_room_join_key()
      } catch {
        current_room_join_key.value = ''
      }
    } else {
      current_room_join_key.value = ''
    }

    if (show_federation_section.value) {
      try {
        await refresh_federation_joined_members()
      } catch {
        // noop
      }
    }

    if (can_manage_federation.value) {
      try {
        await refresh_federation_peers()
      } catch {
        // noop
      }

      try {
        await refresh_federation_room_invites()
      } catch {
        // noop
      }
    }
  }

  return {
    open_room_settings_form,
  }
}
