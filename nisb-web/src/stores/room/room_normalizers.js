import {
  safe_array,
  safe_object,
  safe_string,
  normalize_bool,
  normalize_int,
  normalize_float,
} from './room_shared'
import {
  sort_room_items,
} from './room_event_helpers'

export {
  normalize_runtime_order,
  normalize_runtime_view_mode,
  normalize_room_runtime_bundle_payload,
  normalize_room_runtime_replay_bundle_payload,
  normalize_runtime_state,
  format_runtime_time,
} from './runtime/room_runtime_formal'

export {
  get_runtime_event_badge,
  get_runtime_event_kind_class,
  build_runtime_actor,
  normalize_room_runtime_audit_cards,
  normalize_room_runtime_tool_activity,
  normalize_room_runtime_result_entry,
  normalize_room_runtime_timeline_entries,
  normalize_room_runtime_run_options,
  normalize_room_runtime_status_text,
  normalize_room_runtime_display_bundle,
} from './runtime/room_runtime_display'

export function normalize_id_list(list) {
  const uniq = new Set()
  const out = []

  for (const item of safe_array(list)) {
    const s = safe_string(item).trim()
    if (!s || uniq.has(s)) continue
    uniq.add(s)
    out.push(s)
  }

  return out
}

export function normalize_reply_mode(value, fallback = '') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'manual') return 'manual'
  if (s === 'supervisor') return 'supervisor'
  if (s === 'supervisor_direct') return 'supervisor_direct'
  if (s === 'direct_role') return 'direct_role'

  const fb = safe_string(fallback).trim().toLowerCase()
  if (fb === 'manual') return 'manual'
  if (fb === 'supervisor') return 'supervisor'
  if (fb === 'supervisor_direct') return 'supervisor_direct'
  if (fb === 'direct_role') return 'direct_role'
  return ''
}

export function normalize_worker_concurrency(value, fallback = 2) {
  const raw = value === undefined || value === null || value === ''
    ? fallback
    : value
  const n = Number.parseInt(String(raw), 10)
  if (!Number.isFinite(n)) {
    return fallback === 1 || fallback === 3 || fallback === 4 ? fallback : 2
  }
  return Math.max(1, Math.min(4, n))
}

export function derive_reply_mode_from_state(state, fallback = 'manual') {
  const src = safe_object(state)
  const explicit = normalize_reply_mode(src.reply_mode, '')
  if (explicit) return explicit
  if (normalize_bool(src.supervisor_enabled, false)) return 'supervisor'
  if (safe_string(src.default_reply_role_id).trim()) return 'direct_role'
  return normalize_reply_mode(fallback, 'manual') || 'manual'
}

export function normalize_supervisor_provider(value, fallback = '') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'openai') return 'openai'
  if (s === 'anthropic') return 'anthropic'
  const fb = safe_string(fallback).trim().toLowerCase()
  return fb === 'openai' || fb === 'anthropic' ? fb : ''
}

export function normalize_supervisor_skill_strategy(
  value,
  fallback = 'builtin_plus_custom'
) {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'builtin_only') return 'builtin_only'
  if (s === 'custom_only') return 'custom_only'
  if (s === 'builtin_plus_custom') return 'builtin_plus_custom'

  const fb = safe_string(fallback).trim().toLowerCase()
  if (fb === 'builtin_only') return 'builtin_only'
  if (fb === 'custom_only') return 'custom_only'
  return 'builtin_plus_custom'
}

export function normalize_relative_path(value) {
  let s = safe_string(value).trim().replace(/\\\\/g, '/')
  s = s.replace(/\/{2,}/g, '/')
  s = s.replace(/^\/+|\/+$/g, '')

  const parts = s
    .split('/')
    .map((x) => safe_string(x).trim())
    .filter((x) => x && x !== '.' && x !== '..')

  return parts.join('/')
}

export function normalize_filename(value, fallback = 'supervisor.md') {
  const raw = safe_string(value).trim().replace(/\\\\/g, '/')
  if (!raw) return fallback

  const parts = raw
    .split('/')
    .map((x) => safe_string(x).trim())
    .filter(Boolean)

  const base = parts.length ? parts[parts.length - 1] : ''

  if (!base || base === '.' || base === '..') return fallback
  return base.toLowerCase().endsWith('.md') ? base : `${base}.md`
}

export function normalize_fs_read_scope(value, fallback = 'minimal') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'minimal' || s === 'user_ro') return s
  return fallback === 'user_ro' ? 'user_ro' : 'minimal'
}

export function normalize_room_mcp_overrides(value) {
  const src = safe_object(value)
  return {
    fs_read_enabled: normalize_bool(src.fs_read_enabled, false),
    fs_read_scope: normalize_fs_read_scope(src.fs_read_scope, 'minimal'),
    notebook_write_enabled: normalize_bool(src.notebook_write_enabled, false),
    notebook_dir: normalize_relative_path(src.notebook_dir) || '_room_supervisor_notebooks',
    notebook_filename: normalize_filename(src.notebook_filename, 'supervisor.md'),
    notebook_title: safe_string(src.notebook_title).trim() || 'Supervisor notebook',
    notebook_section_title: safe_string(src.notebook_section_title).trim() || 'latest',
    fs_write_scope: safe_string(src.fs_write_scope).trim(),
    fs_dangerous_enabled: normalize_bool(src.fs_dangerous_enabled, false),
  }
}

export function normalize_room_mcp_provider_status(value, fallback = '') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'published') return 'published'
  if (s === 'disabled') return 'disabled'
  if (s === 'draft') return 'draft'
  if (s === 'unpublished') return 'unpublished'

  const fb = safe_string(fallback).trim().toLowerCase()
  if (fb === 'published') return 'published'
  if (fb === 'disabled') return 'disabled'
  if (fb === 'draft') return 'draft'
  if (fb === 'unpublished') return 'unpublished'
  return ''
}

export function normalize_room_mcp_shared_boundary(value) {
  const src = safe_object(value)
  return {
    owner_private_scope_exposed: normalize_bool(src.owner_private_scope_exposed, false),
  }
}

export function normalize_room_mcp_provider_source(value) {
  const src = safe_object(value)
  return {
    room_id: safe_string(src.room_id).trim(),
    reply_mode: normalize_reply_mode(src.reply_mode, ''),
    workspace_id: safe_string(src.workspace_id).trim(),
    workspace_name: safe_string(src.workspace_name || src.workspace_label).trim(),
    focus_root: normalize_relative_path(src.focus_root),
    focus_label: safe_string(src.focus_label || src.focus_root_label).trim(),
    shared_room_config_enabled: normalize_bool(src.shared_room_config_enabled, false),
    shared_supervisor_enabled: normalize_bool(src.shared_supervisor_enabled, false),
    shared_boundary: normalize_room_mcp_shared_boundary(src.shared_boundary),
  }
}

export function normalize_room_mcp_provider_boundary_hint(value) {
  const src = safe_object(value)
  return {
    supports_workspace_context: normalize_bool(src.supports_workspace_context, false),
    supports_focus_root: normalize_bool(src.supports_focus_root, false),
    default_inherit_workspace_context: normalize_bool(src.default_inherit_workspace_context, false),
    default_inherit_focus_root: normalize_bool(src.default_inherit_focus_root, false),
    message: safe_string(src.message).trim(),
  }
}

export function normalize_room_mcp_tool_templates(list, fallbackToolName = 'search') {
  const rows = safe_array(list)
    .map((item) => {
      const row = safe_object(item)
      const tool_name = safe_string(
        row.tool_name || row.name || fallbackToolName
      ).trim()
      if (!tool_name) return null

      return {
        tool_name,
        label: safe_string(row.label || tool_name).trim() || tool_name,
        description: safe_string(row.description).trim(),
        requested_mode: safe_string(row.requested_mode || 'mcp').trim() || 'mcp',
      }
    })
    .filter(Boolean)

  if (rows.length) return rows

  return [
    {
      tool_name: fallbackToolName,
      label: fallbackToolName,
      description: '',
      requested_mode: 'mcp',
    },
  ]
}

export function normalize_room_mcp_provider_option(value) {
  const src = safe_object(value)
  const provider_id = safe_string(src.provider_id || src.id).trim().toLowerCase()
  if (!provider_id) return null

  const tool_templates = normalize_room_mcp_tool_templates(
    src.tool_templates,
    safe_string(src.tool_name || src.tool || 'search').trim() || 'search'
  )
  const first_tool = tool_templates[0] || { tool_name: 'search' }

  return {
    provider_id,
    provider_type: safe_string(src.provider_type || src.type).trim() || 'preset',
    label: safe_string(src.label || src.name || provider_id).trim() || provider_id,
    description: safe_string(src.description).trim(),
    tool_templates,
    tool_name: safe_string(first_tool.tool_name).trim() || 'search',
    params_defaults: safe_object(src.params_defaults || src.default_params),
    params_schema: safe_object(src.params_schema || src.param_schema),
    auth_state: {
      type: safe_string(src?.auth_state?.type).trim(),
      required: normalize_bool(src?.auth_state?.required, false),
      configured: normalize_bool(src?.auth_state?.configured, false),
      message: safe_string(src?.auth_state?.message).trim(),
    },
    availability: {
      available: normalize_bool(src?.availability?.available, true),
      reason: safe_string(src?.availability?.reason).trim(),
      message: safe_string(src?.availability?.message).trim(),
    },
    boundary_hint: normalize_room_mcp_provider_boundary_hint(src.boundary_hint),
    room_source: normalize_room_mcp_provider_source(src.room_source),
  }
}

export function normalize_room_mcp_provider_summary(value, providers = []) {
  const src = safe_object(value)
  const rows = safe_array(providers)

  if (
    src.total !== undefined ||
    src.available !== undefined ||
    src.unavailable !== undefined ||
    src.auth_required !== undefined ||
    src.auth_configured !== undefined ||
    src.auth_missing !== undefined
  ) {
    return {
      total: normalize_int(src.total, rows.length),
      available: normalize_int(src.available, 0),
      unavailable: normalize_int(src.unavailable, 0),
      auth_required: normalize_int(src.auth_required, 0),
      auth_configured: normalize_int(src.auth_configured, 0),
      auth_missing: normalize_int(src.auth_missing, 0),
    }
  }

  let available = 0
  let unavailable = 0
  let auth_required = 0
  let auth_configured = 0
  let auth_missing = 0

  for (const item of rows) {
    const auth_state = safe_object(item.auth_state)
    const item_available = normalize_bool(item?.availability?.available, true)
    if (item_available) available += 1
    else unavailable += 1

    if (normalize_bool(auth_state.required, false)) {
      auth_required += 1
      if (normalize_bool(auth_state.configured, false)) auth_configured += 1
      else auth_missing += 1
    }
  }

  return {
    total: rows.length,
    available,
    unavailable,
    auth_required,
    auth_configured,
    auth_missing,
  }
}

export function normalize_room_mcp_provider_registry_payload(payload) {
  const src = safe_object(payload)
  const providers = safe_array(src.providers)
    .map((item) => normalize_room_mcp_provider_option(item))
    .filter(Boolean)

  return {
    providers,
    summary: normalize_room_mcp_provider_summary(src.summary, providers),
  }
}

export function normalize_room_state(state) {
  const src = safe_object(state)
  const reply_mode = derive_reply_mode_from_state(src, 'manual')
  const room_mcp_provider_enabled = normalize_bool(src.room_mcp_provider_enabled, false)
  const room_mcp_provider_status = normalize_room_mcp_provider_status(
    src.room_mcp_provider_status,
    room_mcp_provider_enabled ? 'published' : 'disabled'
  )

  return {
    summary: safe_string(src.summary),
    scratchpad: safe_string(src.scratchpad),
    active_roles: normalize_id_list(src.active_roles),
    enabled_supervisor_skill_ids: normalize_id_list(src.enabled_supervisor_skill_ids),
    supervisor_skill_strategy: normalize_supervisor_skill_strategy(
      src.supervisor_skill_strategy,
      'builtin_plus_custom'
    ),
    inherit_workspace_context:
      src.inherit_workspace_context === undefined
        ? true
        : normalize_bool(src.inherit_workspace_context, true),
    inherit_focus_root:
      src.inherit_focus_root === undefined
        ? true
        : normalize_bool(src.inherit_focus_root, true),
    default_reply_role_id: safe_string(src.default_reply_role_id).trim(),
    supervisor_enabled: normalize_bool(src.supervisor_enabled, false),
    reply_mode,
    max_worker_concurrency: normalize_worker_concurrency(
      src.max_worker_concurrency ?? src.worker_concurrency,
      2
    ),

    shared_room_config_enabled: normalize_bool(src.shared_room_config_enabled, false),
    shared_role_ids: normalize_id_list(src.shared_role_ids),
    shared_supervisor_enabled: normalize_bool(src.shared_supervisor_enabled, false),

    room_mcp_provider_enabled,
    room_mcp_provider_status,
    room_mcp_provider_id: safe_string(src.room_mcp_provider_id).trim(),
    room_mcp_provider_name: safe_string(src.room_mcp_provider_name).trim(),
    room_mcp_provider_summary: safe_string(src.room_mcp_provider_summary).trim(),
    room_mcp_provider_semantic_summary: safe_string(src.room_mcp_provider_semantic_summary).trim(),
    room_mcp_provider_boundary_summary: safe_string(src.room_mcp_provider_boundary_summary).trim(),
    room_mcp_provider_published_at: safe_string(src.room_mcp_provider_published_at).trim(),
    room_mcp_provider_updated_at: safe_string(src.room_mcp_provider_updated_at).trim(),
    room_mcp_provider_source: normalize_room_mcp_provider_source(
      src.room_mcp_provider_source || src.room_source
    ),

    supervisor_provider: normalize_supervisor_provider(src.supervisor_provider),
    supervisor_model: safe_string(src.supervisor_model).trim(),
    supervisor_temperature:
      safe_string(src.supervisor_temperature).trim() === ''
        ? ''
        : normalize_float(src.supervisor_temperature, 0),
    supervisor_max_tokens:
      safe_string(src.supervisor_max_tokens).trim() === ''
        ? ''
        : normalize_int(src.supervisor_max_tokens, 0),

    supervisor_step_budget_total:
      safe_string(src.supervisor_step_budget_total).trim() === ''
        ? 0
        : Math.max(0, normalize_int(src.supervisor_step_budget_total, 0)),

    mcp_overrides: normalize_room_mcp_overrides(src.mcp_overrides),

    current_run_id: safe_string(src.current_run_id).trim(),
    current_run_status: safe_string(src.current_run_status).trim(),
    current_run_roles: normalize_id_list(src.current_run_roles),
    current_delegate_role_id: safe_string(src.current_delegate_role_id).trim(),
    current_delegate_role_name: safe_string(src.current_delegate_role_name).trim(),
    current_delegate_index: normalize_int(src.current_delegate_index, 0),
    current_delegate_total: normalize_int(src.current_delegate_total, 0),
    last_plan_summary: safe_string(src.last_plan_summary),
    last_plan_at: safe_string(src.last_plan_at),
    last_run_finished_at: safe_string(src.last_run_finished_at),
    last_message_id: safe_string(src.last_message_id).trim(),
    last_message_at: safe_string(src.last_message_at).trim(),

    workspace_id: safe_string(src.workspace_id).trim(),
    workspace_name: safe_string(src.workspace_name).trim(),
    focus_root: normalize_relative_path(src.focus_root),
    focus_label: safe_string(src.focus_label).trim(),
    workspace_context_updated_at: safe_string(src.workspace_context_updated_at).trim(),
    updated_at: safe_string(src.updated_at).trim(),

    last_supervisor_fs_read_at: safe_string(src.last_supervisor_fs_read_at).trim(),
    last_supervisor_fs_read_enabled: normalize_bool(src.last_supervisor_fs_read_enabled, false),
    last_supervisor_fs_read_status: safe_string(src.last_supervisor_fs_read_status).trim(),
    last_supervisor_fs_read_reason: safe_string(src.last_supervisor_fs_read_reason).trim(),
    last_supervisor_fs_read_focus_root: normalize_relative_path(src.last_supervisor_fs_read_focus_root),
    last_supervisor_fs_read_scope: normalize_fs_read_scope(
      src.last_supervisor_fs_read_scope,
      'minimal'
    ),
    last_supervisor_tool_calls: safe_array(src.last_supervisor_tool_calls),
    last_supervisor_tool_results: safe_array(src.last_supervisor_tool_results),

    last_supervisor_notebook_write_at: safe_string(src.last_supervisor_notebook_write_at).trim(),
    last_supervisor_notebook_write_status: safe_string(src.last_supervisor_notebook_write_status).trim(),
    last_supervisor_notebook_write_message: safe_string(src.last_supervisor_notebook_write_message).trim(),
    last_supervisor_notebook_relative_path: normalize_relative_path(
      src.last_supervisor_notebook_relative_path
    ),
    last_supervisor_notebook_tool_calls: safe_array(src.last_supervisor_notebook_tool_calls),
    last_supervisor_notebook_tool_results: safe_array(src.last_supervisor_notebook_tool_results),
  }
}

export function normalize_room_items_cursor(value) {
  const src = safe_object(value)
  const before_offset = normalize_int(src.before_offset, 0)
  const before_event_id = safe_string(src.before_event_id).trim()
  if (!before_offset && !before_event_id) return {}
  return {
    before_offset,
    before_event_id,
  }
}

export function normalize_room_items_bundle_payload(payload) {
  const src = safe_object(payload)
  const raw_items = safe_array(src.items)

  return {
    items: sort_room_items(raw_items),
    limit: normalize_int(src.limit, 0),
    order: safe_string(src.order).trim().toLowerCase() === 'desc' ? 'desc' : 'asc',
    returned_count: normalize_int(src.returned_count, raw_items.length),
    has_more: normalize_bool(src.has_more, false),
    next_cursor: normalize_room_items_cursor(src.next_cursor),
    source: safe_string(src.source).trim() || 'tail_window',
    byte_budget: normalize_int(src.byte_budget, 0),
    relation_expand: normalize_bool(src.relation_expand, true),
    before_event_id: safe_string(src.before_event_id).trim(),
    file_size: normalize_int(src.file_size, 0),
    window_start_offset: normalize_int(src.window_start_offset, 0),
    window_end_offset: normalize_int(src.window_end_offset, 0),
    selected_oldest_offset: normalize_int(src.selected_oldest_offset, 0),
    selected_newest_offset: normalize_int(src.selected_newest_offset, 0),
  }
}

