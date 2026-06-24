import {
  safe_array,
  safe_object,
  safe_string,
  is_plain_object,
  normalize_bool,
} from './room_shared'
import {
  extract_whoami,
} from './room_extractors'
import {
  normalize_room_state,
  normalize_room_mcp_overrides,
  normalize_room_items_bundle_payload,
  normalize_room_runtime_bundle_payload,
  normalize_room_runtime_replay_bundle_payload,
  normalize_runtime_state,
  normalize_runtime_order,
  normalize_runtime_view_mode,
} from './room_normalizers'
import {
  merge_room_items,
  sort_runtime_events,
  merge_runtime_events,
} from './room_event_helpers'
import {
  load_last_workspace_save,
  save_last_workspace_save,
  remove_last_workspace_save,
  DEFAULT_LAST_WORKSPACE_SAVE,
} from './room_persistence'
import {
  DEFAULT_STATE,
  DEFAULT_ITEMS_PAGING,
  DEFAULT_RUNTIME_STATE,
  DEFAULT_RUNTIME_REPLAY_BUNDLE,
  create_room_store_state,
} from './room_state'

export const room_core_actions = {
  resetRuntime(opts = {}) {
    const preserve_expanded =
      opts?.preserve_expanded === undefined ? true : normalize_bool(opts.preserve_expanded, true)
    const preserve_include_all_runs =
      opts?.preserve_include_all_runs === undefined ? true : normalize_bool(opts.preserve_include_all_runs, true)
    const preserve_order =
      opts?.preserve_order === undefined ? true : normalize_bool(opts.preserve_order, true)
    const preserve_view_mode =
      opts?.preserve_view_mode === undefined ? false : normalize_bool(opts.preserve_view_mode, false)
    const preserve_selected_run =
      opts?.preserve_selected_run === undefined ? false : normalize_bool(opts.preserve_selected_run, false)
    const preserve_tail_event_id =
      opts?.preserve_tail_event_id === undefined ? false : normalize_bool(opts.preserve_tail_event_id, false)
    const preserve_replay_bundle =
      opts?.preserve_replay_bundle === undefined ? false : normalize_bool(opts.preserve_replay_bundle, false)

    const prev = safe_object(this.runtime)

    this.runtime = normalize_runtime_state({
      ...DEFAULT_RUNTIME_STATE(),
      expanded: preserve_expanded ? normalize_bool(prev.expanded, true) : true,
      include_all_runs: preserve_include_all_runs ? normalize_bool(prev.include_all_runs, false) : false,
      order: preserve_order ? normalize_runtime_order(prev.order, 'asc') : 'asc',
      view_mode: preserve_view_mode ? normalize_runtime_view_mode(prev.view_mode, 'current') : 'current',
      selected_run_id: preserve_selected_run ? safe_string(prev.selected_run_id).trim() : '',
      tail_event_id: preserve_tail_event_id ? safe_string(prev.tail_event_id).trim() : '',
      replay_loaded_once: preserve_replay_bundle ? normalize_bool(prev.replay_loaded_once, false) : false,
      replay_bundle: preserve_replay_bundle
        ? normalize_room_runtime_replay_bundle_payload(prev.replay_bundle)
        : DEFAULT_RUNTIME_REPLAY_BUNDLE(),
      formal_runtime_packet: {},
      runtime_control_snapshot: {},
      formal_runtime_status: '',
      latest_formal_runtime_packet_at: '',
    }, prev)
  },

  resetRuntimeReplay(opts = {}) {
    const preserve_selected_run =
      opts?.preserve_selected_run === undefined ? false : normalize_bool(opts.preserve_selected_run, false)
    const preserve_view_mode =
      opts?.preserve_view_mode === undefined ? false : normalize_bool(opts.preserve_view_mode, false)

    const base = normalize_runtime_state(this.runtime)

    this.runtime = normalize_runtime_state({
      ...base,
      view_mode: preserve_view_mode ? normalize_runtime_view_mode(base.view_mode, 'current') : 'current',
      selected_run_id: preserve_selected_run ? safe_string(base.selected_run_id).trim() : '',
      tail_event_id: '',
      replay_loading: false,
      replay_loaded_once: false,
      replay_error: '',
      replay_bundle: DEFAULT_RUNTIME_REPLAY_BUNDLE(),
    }, base)
  },

  resetRoom() {
    this.$patch(create_room_store_state())
  },

  resetItemsPaging() {
    this.itemsPaging = DEFAULT_ITEMS_PAGING()
  },

  hydrateLastWorkspaceSave(room_id = '') {
    const rid = String(room_id || this.roomId || '').trim()
    this.lastWorkspaceSave = load_last_workspace_save(rid)
    return this.lastWorkspaceSave
  },

  recordLastWorkspaceSave(payload) {
    const rid = String(this.roomId || '').trim()
    const next_value = {
      ...DEFAULT_LAST_WORKSPACE_SAVE(),
      ...safe_object(payload),
      saved_at: String(payload?.saved_at || new Date().toISOString()),
    }
    this.lastWorkspaceSave = next_value
    save_last_workspace_save(rid, next_value)
    return next_value
  },

  clearLastWorkspaceSave(room_id = '') {
    const rid = String(room_id || this.roomId || '').trim()
    this.lastWorkspaceSave = DEFAULT_LAST_WORKSPACE_SAVE()
    remove_last_workspace_save(rid)
  },

  setRoomId(room_id) {
    this.roomId = String(room_id || '').trim()
    this.hydrateLastWorkspaceSave(this.roomId)
  },

  setRoomInfo(payload) {
    const room = is_plain_object(payload?.room) ? payload.room : null
    const roles = safe_array(payload?.roles)
    const state = normalize_room_state(payload?.state)

    this.room = room
    this.roles = roles
    this.roomState = {
      ...DEFAULT_STATE(),
      ...state,
      mcp_overrides: normalize_room_mcp_overrides(state?.mcp_overrides),
      last_supervisor_tool_calls: safe_array(state?.last_supervisor_tool_calls),
      last_supervisor_tool_results: safe_array(state?.last_supervisor_tool_results),
      last_supervisor_notebook_tool_calls: safe_array(state?.last_supervisor_notebook_tool_calls),
      last_supervisor_notebook_tool_results: safe_array(state?.last_supervisor_notebook_tool_results),
    }
  },

  setItems(items) {
    this.items = merge_room_items([], items, 'replace')
  },

  setItemsBundle(bundle, opts = {}) {
    const normalized = normalize_room_items_bundle_payload(bundle)
    const append_mode = safe_string(opts?.append_mode).trim() === 'prepend' ? 'prepend' : 'replace'

    this.items =
      append_mode === 'prepend'
        ? merge_room_items(this.items, normalized.items, 'prepend')
        : merge_room_items([], normalized.items, 'replace')

    const next_meta = {
      ...DEFAULT_ITEMS_PAGING(),
      ...(append_mode === 'prepend' ? safe_object(this.itemsPaging) : {}),
      has_more: normalized.has_more,
      next_cursor: normalized.next_cursor,
      source: normalized.source,
      returned_count: normalized.returned_count,
      limit: normalized.limit,
      order: normalized.order,
      relation_expand: normalized.relation_expand,
      before_event_id: normalized.before_event_id,
      byte_budget: normalized.byte_budget,
      file_size: normalized.file_size,
      window_start_offset: normalized.window_start_offset,
      window_end_offset: normalized.window_end_offset,
      selected_oldest_offset: normalized.selected_oldest_offset,
      selected_newest_offset: normalized.selected_newest_offset,
      loaded_once: true,
      loading_older: false,
    }

    this.itemsPaging = next_meta
    return normalized
  },

  setRuntimeItems(items, opts = {}) {
    const mode = safe_string(opts?.mode).trim() === 'replace' ? 'replace' : 'merge'
    const normalized_items = sort_runtime_events(items)

    this.runtime = {
      ...normalize_runtime_state(this.runtime),
      items:
        mode === 'replace'
          ? merge_runtime_events([], normalized_items, 'replace')
          : merge_runtime_events(this.runtime.items, normalized_items, 'merge'),
      returned_count: normalized_items.length,
    }

    const last_item = this.runtime.items[this.runtime.items.length - 1]
    if (!this.runtime.latest_event_id && last_item?.id) {
      this.runtime.latest_event_id = safe_string(last_item.id).trim()
    }
    if (!this.runtime.tail_event_id && last_item?.id) {
      this.runtime.tail_event_id = safe_string(last_item.id).trim()
    }
  },

  setRuntimeExpanded(expanded) {
    this.runtime = {
      ...normalize_runtime_state(this.runtime),
      expanded: normalize_bool(expanded, true),
    }
  },

  setRuntimeIncludeAllRuns(include_all_runs) {
    this.runtime = {
      ...normalize_runtime_state(this.runtime),
      include_all_runs: normalize_bool(include_all_runs, false),
    }
  },

  setRuntimeViewMode(view_mode) {
    const base = normalize_runtime_state(this.runtime)
    this.runtime = normalize_runtime_state({
      ...base,
      view_mode: normalize_runtime_view_mode(view_mode, base.view_mode || 'current'),
    }, base)
  },

  setRuntimeReplayRunId(run_id) {
    const base = normalize_runtime_state(this.runtime)
    this.runtime = normalize_runtime_state({
      ...base,
      selected_run_id: safe_string(run_id).trim(),
    }, base)
  },

  setRuntimeSnapshot(snapshot) {
    this.runtime = normalize_runtime_state(
      {
        ...safe_object(this.runtime),
        ...safe_object(snapshot),
      },
      this.runtime
    )
  },

  setRuntimeBundle(bundle, opts = {}) {
    const normalized = normalize_room_runtime_bundle_payload(bundle)
    const merge_mode = safe_string(opts?.merge_mode).trim() === 'replace' ? 'replace' : 'merge'
    const base = normalize_runtime_state(this.runtime)

    const next_items =
      merge_mode === 'replace'
        ? merge_runtime_events([], normalized.items, 'replace')
        : merge_runtime_events(base.items, normalized.items, 'merge')

    const last_item = next_items[next_items.length - 1]
    const next_latest_event_id = normalized.latest_event_id || safe_string(last_item?.id).trim()

    this.runtime = normalize_runtime_state(
      {
        ...base,
        items: next_items,
        loading: false,
        loaded_once: true,
        error: '',
        include_all_runs: normalized.include_all_runs,
        order: normalized.order,
        run_id: normalized.run_id || base.run_id || safe_string(this.roomState?.current_run_id).trim(),
        latest_event_id: next_latest_event_id,
        tail_event_id: next_latest_event_id || base.tail_event_id,
        live_hint: this.currentRunStatus === 'running',
        last_loaded_at: normalized.loaded_at || new Date().toISOString(),
        limit: normalized.limit,
        returned_count: normalized.returned_count,
        after_event_found: normalized.after_event_found,
        formal_runtime_packet: normalized.formal_runtime_packet,
        runtime_control_snapshot: normalized.runtime_control_snapshot,
        formal_runtime_status: normalized.formal_runtime_status,
        latest_formal_runtime_packet_at: normalized.latest_formal_runtime_packet_at,
      },
      base
    )

    return normalized
  },

  setRuntimeReplayBundle(bundle, opts = {}) {
    const normalized = normalize_room_runtime_replay_bundle_payload(bundle)
    const base = normalize_runtime_state(this.runtime)
    const set_view_mode =
      opts?.set_view_mode === undefined ? true : normalize_bool(opts.set_view_mode, true)

    this.runtime = normalize_runtime_state({
      ...base,
      view_mode: set_view_mode ? 'replay' : base.view_mode,
      selected_run_id: normalized.run_id || base.selected_run_id,
      tail_event_id: normalized.tail_event_id || normalized.latest_event_id || base.tail_event_id,
      replay_loading: false,
      replay_loaded_once: true,
      replay_error: '',
      replay_bundle: normalized,
    }, base)

    return normalized
  },

  patchRuntimeState(patch) {
    this.runtime = normalize_runtime_state(
      {
        ...safe_object(this.runtime),
        ...safe_object(patch),
      },
      this.runtime
    )
  },

  patchRoomState(patch) {
    if (!patch || typeof patch !== 'object') return
    this.roomState = normalize_room_state({
      ...this.roomState,
      ...safe_object(patch),
    })
  },

  syncRuntimeRunStateFromRoomState() {
    const current_run_id = safe_string(this.roomState?.current_run_id).trim()
    const current_run_status = safe_string(this.roomState?.current_run_status).trim().toLowerCase()

    this.runtime = normalize_runtime_state(
      {
        ...safe_object(this.runtime),
        run_id: safe_string(this.runtime?.run_id).trim() || current_run_id,
        live_hint: current_run_status === 'running',
      },
      this.runtime
    )
  },

  setWhoAmI(payload) {
    const info = extract_whoami(payload)
    this.myUid = info.uid || this.myUid || ''
    this.myBasepath = info.basepath || this.myBasepath || ''
    return info
  },

  openRolesDrawer() {
    this.ui.rolesDrawerOpen = true
  },

  closeRolesDrawer() {
    this.ui.rolesDrawerOpen = false
  },

  openSettingsModal() {
    this.ui.settingsModalOpen = true
  },

  closeSettingsModal() {
    this.ui.settingsModalOpen = false
  },

  closeAllOverlays() {
    this.ui.rolesDrawerOpen = false
    this.ui.settingsModalOpen = false
  },

  emitApplyWorkspaceContextToUi() {
    const workspace_id = String(this.roomState?.workspace_id || '').trim()
    const workspace_name = String(this.roomState?.workspace_name || '').trim()
    const focus_root = String(this.roomState?.focus_root || '').trim()
    const focus_label = String(this.roomState?.focus_label || '').trim()
    const inherit_workspace_context = !!this.roomState?.inherit_workspace_context
    const inherit_focus_root = !!this.roomState?.inherit_focus_root

    if (!inherit_workspace_context && !inherit_focus_root) return
    if (!workspace_id && !focus_root) return

    window.dispatchEvent(new CustomEvent('nisb_room_apply_workspace_context', {
      detail: {
        room_id: this.roomId,
        workspace_id,
        workspace_name,
        focus_root: inherit_focus_root ? focus_root : '',
        focus_label: inherit_focus_root ? focus_label : '',
        clear_focus_root: inherit_focus_root ? !focus_root : false,
        inherit_workspace_context,
        inherit_focus_root,
        source: 'room_open',
      }
    }))
  },

  emitClearWorkspaceContextToUi() {
    window.dispatchEvent(new CustomEvent('nisb_room_clear_workspace_context', {
      detail: {
        room_id: this.roomId,
        clear_workspace: false,
        clear_focus_root: true,
        source: 'room_open',
      }
    }))
  },
}

