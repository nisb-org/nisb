import { DEFAULT_LAST_WORKSPACE_SAVE } from './room_persistence'

export function DEFAULT_STATE() {
  return {
    summary: '',
    scratchpad: '',
    active_roles: [],
    enabled_supervisor_skill_ids: [],
    supervisor_skill_strategy: 'builtin_plus_custom',
    inherit_workspace_context: true,
    inherit_focus_root: true,
    default_reply_role_id: '',
    supervisor_enabled: false,
    reply_mode: 'manual',
    supervisor_provider: '',
    supervisor_model: '',
    supervisor_temperature: '',
    supervisor_max_tokens: '',
    supervisor_step_budget_total: 0,

    mcp_overrides: {
      fs_read_enabled: false,
      fs_read_scope: 'minimal',
      notebook_write_enabled: false,
      notebook_dir: '_room_supervisor_notebooks',
      notebook_filename: 'supervisor.md',
      notebook_title: 'Supervisor notebook',
      notebook_section_title: 'latest',
      fs_write_scope: '',
      fs_dangerous_enabled: false,
    },

    current_run_id: '',
    current_run_status: '',
    current_run_roles: [],
    current_delegate_role_id: '',
    current_delegate_role_name: '',
    current_delegate_index: 0,
    current_delegate_total: 0,
    last_plan_summary: '',
    last_plan_at: '',
    last_run_finished_at: '',
    last_message_id: '',
    last_message_at: '',

    workspace_id: '',
    workspace_name: '',
    focus_root: '',
    focus_label: '',
    workspace_context_updated_at: '',
    updated_at: '',

    last_supervisor_fs_read_at: '',
    last_supervisor_fs_read_enabled: false,
    last_supervisor_fs_read_status: '',
    last_supervisor_fs_read_reason: '',
    last_supervisor_fs_read_focus_root: '',
    last_supervisor_fs_read_scope: 'minimal',
    last_supervisor_tool_calls: [],
    last_supervisor_tool_results: [],

    last_supervisor_notebook_write_at: '',
    last_supervisor_notebook_write_status: '',
    last_supervisor_notebook_write_message: '',
    last_supervisor_notebook_relative_path: '',
    last_supervisor_notebook_tool_calls: [],
    last_supervisor_notebook_tool_results: [],
  }
}

export function DEFAULT_ITEMS_PAGING() {
  return {
    has_more: false,
    next_cursor: {},
    source: '',
    returned_count: 0,
    limit: 0,
    order: 'asc',
    relation_expand: true,
    before_event_id: '',
    byte_budget: 0,
    file_size: 0,
    window_start_offset: 0,
    window_end_offset: 0,
    selected_oldest_offset: 0,
    selected_newest_offset: 0,
    loaded_once: false,
    loading_older: false,
  }
}

export function DEFAULT_RUNTIME_REPLAY_BUNDLE() {
  return {
    type: 'room_runtime_replay',
    run_id: '',
    items: [],
    phases: [],
    latest_event_id: '',
    tail_event_id: '',
    result_event: null,
    result_payload: {},
    result_text: '',
    citations: [],
    summary: '',
    headline: '',
    badge_summary: '',
    source: '',
    message: '',
    loaded_at: '',
    audit: {},
  }
}

export function DEFAULT_RUNTIME_STATE() {
  return {
    items: [],
    loading: false,
    loaded_once: false,
    error: '',
    expanded: true,
    include_all_runs: false,
    order: 'asc',
    run_id: '',
    latest_event_id: '',
    live_hint: false,
    last_loaded_at: '',
    limit: 0,
    returned_count: 0,
    after_event_found: false,

    formal_runtime_packet: {},
    current_formal_runtime_packet: {},
    runtime_control_snapshot: {},
    current_runtime_control_snapshot: {},
    formal_runtime_status: '',
    latest_formal_runtime_packet_at: '',

    view_mode: 'current',
    selected_run_id: '',
    tail_event_id: '',

    replay_loading: false,
    replay_loaded_once: false,
    replay_error: '',
    replay_bundle: DEFAULT_RUNTIME_REPLAY_BUNDLE(),
  }
}

export function create_room_store_state() {
  return {
    roomId: '',
    room: null,
    roles: [],
    roomState: DEFAULT_STATE(),
    items: [],
    itemsPaging: DEFAULT_ITEMS_PAGING(),
    runtime: DEFAULT_RUNTIME_STATE(),
    loading: false,
    refreshing: false,
    error: '',
    myUid: '',
    myBasepath: '',
    lastWorkspaceSave: DEFAULT_LAST_WORKSPACE_SAVE(),
    ui: {
      rolesDrawerOpen: false,
      settingsModalOpen: false,
    },
  }
}
