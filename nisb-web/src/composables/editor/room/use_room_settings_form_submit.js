import {
  build_room_settings_state_payload,
  has_workspace_context_detail,
} from './room_settings_form_patch_builder'

export function use_room_settings_form_submit({
  t,
  form,
  busy,
  room_id_value,
  can_edit_room_state,
  call_room_tool,
  callTool,
  room_store,
  dispatch_toast,
  build_workspace_context_detail,
  apply_p6_test_control_to_room_store,
  write_p6_test_control_session,
  sync_room_join_key_from_store,
  refresh_supervisor_skills,
  normalize_role_ids,
  normalize_skill_ids_client,
  normalize_supervisor_skill_strategy_client,
  normalize_reply_mode_client,
  normalize_worker_concurrency_client,
  normalize_supervisor_provider_client,
  normalize_optional_number_string,
  normalize_step_budget_total_client,
  normalize_fs_read_scope_client,
  normalize_relative_path_client,
  normalize_filename_client,
  normalize_p6_probe_actor_client,
  assert_tool_success,
}) {
  function safe_string(value) {
    return value === null || value === undefined ? '' : String(value)
  }

  function normalize_worker_concurrency_for_submit(value) {
    if (typeof normalize_worker_concurrency_client === 'function') {
      return normalize_worker_concurrency_client(value, 2)
    }

    const raw = Number(value)
    if (!Number.isFinite(raw)) return 1

    return Math.min(4, Math.max(1, Math.trunc(raw)))
  }

  function build_shared_mapping_payload() {
    const shared_room_enabled = !!form.shared_room_config_enabled
    const reply_mode = normalize_reply_mode_client(form.reply_mode, 'manual')
    const default_reply_role_id = String(form.default_reply_role_id || '').trim()
    const active_roles = normalize_role_ids(form.active_roles || [])
    const current_shared_role_ids = normalize_role_ids(form.shared_role_ids || [])
    const current_shared_supervisor_enabled = !!form.shared_supervisor_enabled

    if (!shared_room_enabled) {
      return {
        shared_role_ids: [],
        shared_supervisor_enabled: false,
      }
    }

    if (reply_mode === 'direct_role') {
      return {
        shared_role_ids: default_reply_role_id ? [default_reply_role_id] : [],
        shared_supervisor_enabled: false,
      }
    }

    if (reply_mode === 'supervisor') {
      return {
        shared_role_ids: active_roles,
        shared_supervisor_enabled: active_roles.length > 0,
      }
    }

    if (reply_mode === 'manual') {
      return {
        shared_role_ids: [],
        shared_supervisor_enabled: false,
      }
    }

    return {
      shared_role_ids: current_shared_role_ids,
      shared_supervisor_enabled: current_shared_supervisor_enabled,
    }
  }

  function build_room_mcp_boundary_hint({ shared_payload } = {}) {
    const reply_mode = normalize_reply_mode_client(form.reply_mode, 'manual')
    const shared_room_enabled = !!form.shared_room_config_enabled
    const shared_supervisor_enabled = !!(shared_payload && shared_payload.shared_supervisor_enabled)

    if (!shared_room_enabled) {
      return [
        'shared_room_config=false',
        `reply_mode=${reply_mode}`,
        'room-configured shared capability may resolve to no-auto-reply/manual semantics',
        'owner_private_scope_exposed=false',
      ].join('; ')
    }

    return [
      'shared_room_config=true',
      `reply_mode=${reply_mode}`,
      `shared_supervisor=${shared_supervisor_enabled ? 'true' : 'false'}`,
      'room-configured shared capability only',
      'owner_private_scope_exposed=false',
    ].join('; ')
  }

  function normalize_room_mcp_provider_payload() {
    return {
      room_mcp_provider_enabled: !!form.room_mcp_provider_enabled,
      room_mcp_provider_name: safe_string(form.room_mcp_provider_name).trim(),
      room_mcp_provider_summary: safe_string(form.room_mcp_provider_summary).trim(),
    }
  }

  function normalize_room_mcp_publication_payload({ shared_payload } = {}) {
    const provider_payload = normalize_room_mcp_provider_payload()
    const publish_enabled = !!provider_payload.room_mcp_provider_enabled
    const publish_label = provider_payload.room_mcp_provider_name
    const publish_summary = provider_payload.room_mcp_provider_summary
    const boundary_hint = build_room_mcp_boundary_hint({ shared_payload })

    return {
      room_mcp_publication_patch: {
        publish_enabled,
        publish_label,
        publish_summary,
        boundary_hint,
        visibility_mode: 'room_visible_and_grant_capable',
        publication_state: publish_enabled ? 'active' : 'disabled',
      },
    }
  }

  function build_state_payload() {
    form.max_worker_concurrency = normalize_worker_concurrency_for_submit(
      form.max_worker_concurrency
    )

    return build_room_settings_state_payload({
      room_id: room_id_value.value,
      form,
      normalize_role_ids,
      normalize_skill_ids_client,
      normalize_supervisor_skill_strategy_client,
      normalize_reply_mode_client,
      normalize_worker_concurrency_client,
      normalize_supervisor_provider_client,
      normalize_optional_number_string,
      normalize_step_budget_total_client,
      normalize_fs_read_scope_client,
      normalize_relative_path_client,
      normalize_filename_client,
      normalize_p6_probe_actor_client,
    })
  }

  async function submit_save({ on_success } = {}) {
    if (!room_id_value.value) return

    if (!can_edit_room_state.value) {
      dispatch_toast(t('room.settingsForm.errors.permissionDenied'), 'error')
      return
    }

    busy.value = true
    try {
      const workspace_detail = build_workspace_context_detail({ source: 'room_settings_save' })
      const shared_payload = build_shared_mapping_payload()
      const room_mcp_provider_payload = normalize_room_mcp_provider_payload()
      const room_mcp_publication_payload = normalize_room_mcp_publication_payload({ shared_payload })

      form.shared_role_ids = normalize_role_ids(shared_payload.shared_role_ids || [])
      form.shared_supervisor_enabled = !!shared_payload.shared_supervisor_enabled

      form.room_mcp_provider_enabled = !!room_mcp_provider_payload.room_mcp_provider_enabled
      form.room_mcp_provider_name = room_mcp_provider_payload.room_mcp_provider_name
      form.room_mcp_provider_summary = room_mcp_provider_payload.room_mcp_provider_summary

      assert_tool_success(
        await call_room_tool('nisb_room_update_info', {
          room_id: room_id_value.value,
          title: String(form.title || '').trim() || t('room.settingsForm.defaults.newRoomTitle'),
          shared_room_config_enabled: !!form.shared_room_config_enabled,
          shared_role_ids: form.shared_role_ids,
          shared_supervisor_enabled: !!form.shared_supervisor_enabled,
          room_mcp_provider_enabled: !!form.room_mcp_provider_enabled,
          room_mcp_provider_name: String(form.room_mcp_provider_name || '').trim(),
          room_mcp_provider_summary: String(form.room_mcp_provider_summary || '').trim(),
          room_mcp_publication_patch: room_mcp_publication_payload.room_mcp_publication_patch,
        }),
        t('room.settingsForm.errors.actionFailed')
      )

      const state_payload = build_state_payload()
      write_p6_test_control_session(room_id_value.value, state_payload.p6_test_control)

      assert_tool_success(
        await call_room_tool('nisb_room_update_state', state_payload),
        t('room.settingsForm.errors.actionFailed')
      )

      if (has_workspace_context_detail(workspace_detail)) {
        assert_tool_success(
          await call_room_tool('nisb_room_workspace_set', {
            room_id: room_id_value.value,
            workspace_id: workspace_detail.workspace_id,
            workspace_name: workspace_detail.workspace_name,
            focus_root: workspace_detail.focus_root,
            focus_label: workspace_detail.focus_label,
          }),
          t('room.settingsForm.errors.actionFailed')
        )
      } else {
        assert_tool_success(
          await call_room_tool('nisb_room_workspace_clear', {
            room_id: room_id_value.value,
            clear_workspace: true,
            clear_focus_root: true,
          }),
          t('room.settingsForm.errors.actionFailed')
        )
      }

      await room_store.refreshRoomInfo(callTool, room_id_value.value)
      apply_p6_test_control_to_room_store(room_id_value.value, state_payload.p6_test_control)
      sync_room_join_key_from_store({ preserve_if_empty: true })

      if (String(form.workspace_id || '').trim() && String(form.focus_root || '').trim()) {
        await refresh_supervisor_skills({
          sync_local_from_saved: true,
          force_sync_local: true,
        })
      }

      if (form.apply_after_save) {
        window.dispatchEvent(new CustomEvent('nisb_room_apply_workspace_context', {
          detail: workspace_detail,
        }))
      }

      if (typeof on_success === 'function') {
        on_success()
      }

      dispatch_toast(t('room.settingsForm.toasts.settingsSaved'), 'success')
    } catch (error) {
      dispatch_toast(
        t('room.settingsForm.toasts.saveFailed', {
          message: error?.message || error || t('room.settingsForm.toasts.unknownError'),
        }),
        'error'
      )
    } finally {
      busy.value = false
    }
  }

  return {
    submit_save,
    build_shared_mapping_payload,
    normalize_room_mcp_provider_payload,
    normalize_room_mcp_publication_payload,
    build_room_mcp_boundary_hint,
  }
}

