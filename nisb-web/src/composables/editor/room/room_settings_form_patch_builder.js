function derive_shared_mapping_from_form({
  form,
  normalize_role_ids,
  normalize_reply_mode_client,
}) {
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
      shared_room_config_enabled: false,
    }
  }

  if (reply_mode === 'direct_role') {
    return {
      shared_role_ids: default_reply_role_id ? [default_reply_role_id] : [],
      shared_supervisor_enabled: false,
      shared_room_config_enabled: true,
    }
  }

  if (reply_mode === 'supervisor') {
    return {
      shared_role_ids: active_roles,
      shared_supervisor_enabled: active_roles.length > 0,
      shared_room_config_enabled: true,
    }
  }

  if (reply_mode === 'manual') {
    return {
      shared_role_ids: [],
      shared_supervisor_enabled: false,
      shared_room_config_enabled: true,
    }
  }

  return {
    shared_role_ids: current_shared_role_ids,
    shared_supervisor_enabled: current_shared_supervisor_enabled,
    shared_room_config_enabled: true,
  }
}

function normalize_worker_concurrency_payload(value, fallback = 1) {
  const fallback_num = Number(fallback)
  const safe_fallback = Number.isFinite(fallback_num) ? Math.trunc(fallback_num) : 1
  const raw = Number(value)

  if (!Number.isFinite(raw)) {
    return Math.min(4, Math.max(1, safe_fallback))
  }

  return Math.min(4, Math.max(1, Math.trunc(raw)))
}

export function build_room_settings_state_payload({
  room_id,
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
}) {
  const raw_active_roles = normalize_role_ids(form.active_roles)
  const active_roles = [...raw_active_roles]
  const enabled_supervisor_skill_ids = normalize_skill_ids_client(form.enabled_supervisor_skill_ids)
  const supervisor_skill_strategy = normalize_supervisor_skill_strategy_client(
    form.supervisor_skill_strategy,
    'builtin_plus_custom'
  )
  const default_reply_role_id = String(form.default_reply_role_id || '').trim()
  const max_worker_concurrency = typeof normalize_worker_concurrency_client === 'function'
    ? normalize_worker_concurrency_client(form.max_worker_concurrency, 2)
    : normalize_worker_concurrency_payload(form.max_worker_concurrency, 2)
  let reply_mode = normalize_reply_mode_client(form.reply_mode)
  let supervisor_enabled = !!form.supervisor_enabled

  if (reply_mode === 'direct_role' && default_reply_role_id && !active_roles.includes(default_reply_role_id)) {
    active_roles.push(default_reply_role_id)
  }

  if (reply_mode === 'supervisor' || reply_mode === 'supervisor_direct') {
    supervisor_enabled = true
  }

  // The current frontend has no independent worker role picker.
  // If supervisor mode has no active roles, persist it as supervisor_direct.
  if (reply_mode === 'supervisor' && raw_active_roles.length === 0) {
    reply_mode = 'supervisor_direct'
  }

  const shared_mapping = derive_shared_mapping_from_form({
    form: {
      ...form,
      active_roles,
      default_reply_role_id,
      reply_mode,
      supervisor_enabled,
    },
    normalize_role_ids,
    normalize_reply_mode_client,
  })

  return {
    room_id,
    summary: String(form.summary || '').trim(),
    scratchpad: String(form.scratchpad || '').trim(),
    active_roles,
    enabled_supervisor_skill_ids,
    supervisor_skill_strategy,
    inherit_workspace_context: !!form.inherit_workspace_context,
    inherit_focus_root: !!form.inherit_focus_root,
    default_reply_role_id,
    supervisor_enabled,
    reply_mode,
    max_worker_concurrency,

    shared_room_config_enabled: !!shared_mapping.shared_room_config_enabled,
    shared_role_ids: normalize_role_ids(shared_mapping.shared_role_ids || []),
    shared_supervisor_enabled: !!shared_mapping.shared_supervisor_enabled,

    supervisor_provider: normalize_supervisor_provider_client(form.supervisor_provider),
    supervisor_model: String(form.supervisor_model || '').trim(),
    supervisor_temperature: normalize_optional_number_string(form.supervisor_temperature),
    supervisor_max_tokens: normalize_optional_number_string(form.supervisor_max_tokens, { integer: true }),
    supervisor_step_budget_total: Number(
      normalize_step_budget_total_client(form.supervisor_step_budget_total, '0')
    ),
    mcp_overrides: {
      fs_read_enabled: !!form.supervisor_fs_read_enabled,
      fs_read_scope: normalize_fs_read_scope_client(form.supervisor_fs_read_scope),
      notebook_write_enabled: !!form.supervisor_notebook_write_enabled,
      notebook_dir: normalize_relative_path_client(
        form.supervisor_notebook_dir,
        '_room_supervisor_notebooks'
      ) || '_room_supervisor_notebooks',
      notebook_filename: normalize_filename_client(
        form.supervisor_notebook_filename,
        'supervisor.md'
      ),
      notebook_title: String(form.supervisor_notebook_title || 'Supervisor notebook').trim() || 'Supervisor notebook',
      notebook_section_title: String(form.supervisor_notebook_section_title || 'latest').trim() || 'latest',
    },
    p6_test_control: {
      panel_enabled: !!form.p6_test_panel_enabled,
      notebook_probe_actor: normalize_p6_probe_actor_client(form.p6_notebook_probe_actor, 'off'),
    },
  }
}

export function has_workspace_context_detail(detail = {}) {
  return !!detail.workspace_id ||
    !!detail.workspace_name ||
    !!detail.focus_root ||
    !!detail.focus_label
}

