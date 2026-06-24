import { useRoomStore } from '../../../stores/room'
import {
  create_assistant_message,
  create_empty_stream_state,
  create_user_message,
  normalize_tool_call,
  normalize_tool_result,
  push_message,
  read_array,
  read_string,
} from './use_chat_panel_message_writer'
import {
  create_empty_stream_markdown_state,
  finalize_stream_markdown,
  mark_stream_markdown_error,
} from '../../chat/use_stream_markdown'
import {
  apply_common_meta,
  apply_final_meta,
  build_state_patch,
  dispatch_room_refresh,
  unwrap_tool_result,
} from './use_chat_panel_send_runtime_shared'

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function safe_object(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safe_boolean(value, fallback = false) {
  if (typeof value === 'boolean') return value
  const token = safe_string(value).trim().toLowerCase()
  if (!token) return fallback
  if (['1', 'true', 'yes', 'on'].includes(token)) return true
  if (['0', 'false', 'no', 'off'].includes(token)) return false
  return fallback
}

function normalize_token(value) {
  return safe_string(value).trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function normalize_runtime_state(value) {
  const token = normalize_token(value)

  if (
    [
      'running',
      'pause_requested',
      'waiting_checkpoint',
      'interrupted',
      'resumed',
      'completed',
      'completed_after_resume',
      'budget_exhausted',
    ].includes(token)
  ) {
    return token
  }

  if (token === 'step_budget_exhausted' || token === 'exhausted') {
    return 'budget_exhausted'
  }

  return token
}

function format_control_block_message(reason, fallback_status = '') {
  const token = normalize_token(reason)

  if (token === 'pause_requested' || token === 'pause_requested_pending_checkpoint') {
    return '已请求暂停，正在等待安全 checkpoint。'
  }

  if (token === 'waiting_checkpoint') {
    return '当前正在等待安全 checkpoint，暂不接受新问题。'
  }

  if (token === 'interrupted_resume_ready' || token === 'resume_ready') {
    return '当前运行已中断，请先从 checkpoint 恢复。'
  }

  if (token === 'interrupted') {
    return '当前运行已中断，暂不接受新问题。'
  }

  if (token === 'run_running' || token === 'running') {
    return '当前运行中，暂不接受新问题。'
  }

  if (token === 'budget_exhausted') {
    return 'step budget 已耗尽，当前不可继续发送。'
  }

  if (token === 'error_blocking_resume' || token === 'resume_blocked_error') {
    return '当前存在阻断恢复的错误，暂不接受新问题。'
  }

  const fallback = safe_string(reason).trim()
  if (fallback) return fallback

  const status = normalize_runtime_state(fallback_status)
  if (status === 'pause_requested') return '已请求暂停，正在等待安全 checkpoint。'
  if (status === 'waiting_checkpoint') return '当前正在等待安全 checkpoint，暂不接受新问题。'
  if (status === 'interrupted') return '当前运行已中断，暂不接受新问题。'
  if (status === 'budget_exhausted') return 'step budget 已耗尽，当前不可继续发送。'
  return '当前运行中，暂不接受新问题。'
}

function has_own(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key)
}

function has_usable_value(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return !!value.trim()
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

function read_control_value(candidates, keys = []) {
  for (const candidate of candidates) {
    const row = safe_object(candidate)
    for (const key of keys) {
      if (!key || !has_own(row, key)) continue
      const value = row[key]
      if (has_usable_value(value)) return value
      if (typeof value === 'boolean' || typeof value === 'number') return value
    }
  }
  return undefined
}

function normalize_runtime_control_snapshot(raw) {
  const src = safe_object(raw)
  const candidates = [
    src,
    safe_object(src.runtime_control_snapshot),
    safe_object(src.control_snapshot),
  ].filter((row) => Object.keys(row).length > 0)

  return {
    runtime_state: normalize_runtime_state(
      read_control_value(candidates, ['runtime_state', 'runtimeState', 'state'])
    ),
    runtime_phase: normalize_runtime_state(
      read_control_value(candidates, ['runtime_phase', 'runtimePhase', 'phase'])
    ),
    can_accept_new_prompt: safe_boolean(
      read_control_value(candidates, ['can_accept_new_prompt', 'canAcceptNewPrompt']),
      true
    ),
    control_block_reason: safe_string(
      read_control_value(candidates, ['control_block_reason', 'controlBlockReason'])
    ).trim(),
    can_pause_current: safe_boolean(
      read_control_value(candidates, ['can_pause_current', 'canPauseCurrent']),
      false
    ),
    can_resume: safe_boolean(
      read_control_value(candidates, ['can_resume', 'canResume']),
      false
    ),
  }
}

function has_meaningful_runtime_control(snapshot = {}) {
  const src = safe_object(snapshot)
  return !!(
    safe_string(src.runtime_state).trim() ||
    safe_string(src.runtime_phase).trim() ||
    safe_string(src.control_block_reason).trim() ||
    src.can_pause_current === true ||
    src.can_resume === true ||
    src.pause_requested === true ||
    src.pause_request_accepted === true ||
    src.pause_effective === true ||
    src.resume_ready === true ||
    src.budget_exhausted === true ||
    src.can_accept_new_prompt === false
  )
}

function normalize_probe_actor(value, fallback = 'off') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'supervisor') return 'supervisor'
  if (s === 'worker') return 'worker'
  if (s === 'skill') return 'skill'
  if (s === 'off') return 'off'
  return fallback
}

const P6_TEST_CONTROL_SESSION_KEY_PREFIX = 'nisb_room_p6_test_control:'

function read_p6_test_control_session(roomId = '') {
  try {
    const rid = safe_string(roomId).trim()
    if (!rid || typeof window === 'undefined' || !window.sessionStorage) {
      return {}
    }

    const raw = window.sessionStorage.getItem(`${P6_TEST_CONTROL_SESSION_KEY_PREFIX}${rid}`)
    if (!raw) return {}

    const parsed = safe_object(JSON.parse(raw))
    return {
      panel_enabled: !!parsed.panel_enabled,
      notebook_probe_actor: normalize_probe_actor(parsed.notebook_probe_actor || 'off', 'off'),
    }
  } catch {
    return {}
  }
}

function build_p6_test_control_payload(roomId = '') {
  const control = read_p6_test_control_session(roomId)

  if (!control.panel_enabled) return null
  if (control.notebook_probe_actor === 'off') return null

  return {
    enabled: true,
    notebook_probe_actor: control.notebook_probe_actor,
  }
}

const FORMAL_LEGAL_RUNTIME_TYPES = new Set([
  'room.runtime_manual',
  'room.runtime_skipped',
  'room.runtime_denied',
  'room.runtime_no_auto_reply',
  'room.runtime_no-auto-reply',
])

function normalize_formal_runtime_type(value) {
  const token = safe_string(value).trim().toLowerCase()
  if (!token) return ''
  if (token === 'room.runtime_no-auto-reply') return 'room.runtime_no_auto_reply'
  return FORMAL_LEGAL_RUNTIME_TYPES.has(token) ? token : ''
}

function find_formal_runtime_packet(tool_results = []) {
  const rows = Array.isArray(tool_results) ? tool_results : []

  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const row = safe_object(rows[idx])
    const type = normalize_formal_runtime_type(row.type)
    if (!type) continue
    return {
      ...row,
      type,
    }
  }

  return {}
}

function find_latest_room_event(tool_results = []) {
  const rows = Array.isArray(tool_results) ? tool_results : []

  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const row = safe_object(rows[idx])
    if (safe_string(row.type).trim() !== 'room_event') continue

    const event = safe_object(row.event)
    if (Object.keys(event).length > 0) return event
  }

  return {}
}

function build_post_formal_runtime_patch(result = {}) {
  const src = safe_object(result)
  const tool_results = read_array(src, 'tool_results')
  const formal_runtime_packet = find_formal_runtime_packet(tool_results)

  if (!Object.keys(formal_runtime_packet).length) {
    return null
  }

  const room_event = find_latest_room_event(tool_results)

  return {
    items: [],
    loading: false,
    loaded_once: true,
    error: '',
    run_id: '',
    latest_event_id: safe_string(room_event.id).trim(),
    tail_event_id: '',
    live_hint: false,

    formal_runtime_packet,
    runtime_control_snapshot: safe_object(
      src.runtime_control_snapshot || src.control_snapshot
    ),
    formal_runtime_status: safe_string(
      formal_runtime_packet.type || formal_runtime_packet.status
    ).trim(),
    latest_formal_runtime_packet_at: safe_string(
      formal_runtime_packet.updated_at ||
      formal_runtime_packet.recorded_at ||
      room_event.ts ||
      ''
    ).trim(),
  }
}

export function create_room_send_lane({
  props,
  chat_cfg,
  settings = {},
  messages,
  input_text,
  is_thinking,
  is_uploading,
  call_tool,
  room_post_state,
  emit_stream_state,
  hard_scroll_to_bottom,
  activate_follow_bottom,
  extend_follow_bottom,
  clear_selected_attachments,
  clear_active_stream_handles,
}) {
  const room_store = useRoomStore()

  function resolve_room_id(payload = {}) {
    const payload_room_id = safe_string(payload?.room_id).trim()
    if (payload_room_id) return payload_room_id

    const chat_room_id = safe_string(chat_cfg?.chat?.roomId).trim()
    if (chat_room_id) return chat_room_id

    const store_room_id = safe_string(room_store?.roomId || room_store?.room?.room_id).trim()
    if (store_room_id) return store_room_id

    return ''
  }

  async function call_room_tool(tool, args = {}) {
    const next_args = {
      ...safe_object(args),
    }

    const room_id = resolve_room_id(next_args)
    if (room_id && !next_args.room_id) {
      next_args.room_id = room_id
    }

    if (typeof room_store?.callRoomTool === 'function') {
      return await room_store.callRoomTool(call_tool, tool, next_args)
    }

    return await call_tool(tool, next_args, { normalize_chat_payload: true })
  }
  
  function resolve_room_sender_uid(room_id = '') {
    const rid = safe_string(room_id).trim()

    const local_uid = safe_string(
      globalThis?.localStorage?.getItem?.('nisb_user_id')
    ).trim()

    if (!rid) return local_uid

    const is_federated =
      typeof room_store?.isFederatedRoom === 'function'
        ? room_store.isFederatedRoom(rid)
        : false

    if (!is_federated) {
      return local_uid
    }

    const session = safe_object(room_store?.federationRoomSession)
    const session_room_id = safe_string(session.room_id).trim()
    const owner_room_id = safe_string(session.owner_room_id).trim()

    const matched =
      !!session.enabled &&
      (session_room_id === rid || owner_room_id === rid)

    if (!matched) {
      return local_uid
    }

    return safe_string(session.remote_user_id).trim() || local_uid
  }

  function get_current_room_runtime_gate(room_id = '') {
    const rid = safe_string(room_id || chat_cfg?.chat?.roomId).trim()

    if (!rid) {
      return {
        room_id: '',
        current_run_id: '',
        continuation_status: '',
        current_run_status: '',
        runtime_state: '',
        runtime_phase: '',
        can_accept_new_prompt: true,
        control_block_reason: '',
        can_pause_current: false,
        can_resume: false,
      }
    }

    const control = normalize_runtime_control_snapshot(
      room_store.runtimeControlSnapshot ||
        room_store.runtime?.runtime_control_snapshot ||
        room_store.runtime?.control_snapshot ||
        room_store.roomState?.runtime_control_snapshot ||
        room_store.roomState ||
        {}
    )

    return {
      room_id: rid,
      current_run_id: safe_string(
        room_store.roomState?.current_run_id || room_store.currentRunId
      ).trim(),
      continuation_status: normalize_runtime_state(room_store.roomState?.continuation_status),
      current_run_status: normalize_runtime_state(
        room_store.roomState?.current_run_status || room_store.currentRunStatus
      ),
      runtime_state: control.runtime_state,
      runtime_phase: control.runtime_phase,
      can_accept_new_prompt: control.can_accept_new_prompt,
      control_block_reason: control.control_block_reason,
      can_pause_current: !!control.can_pause_current,
      can_resume: !!control.can_resume,
    }
  }

  function activate_room_post(room_id = '', request_id = '') {
    room_post_state.value = {
      active: true,
      room_id: String(room_id || '').trim(),
      request_id: String(request_id || '').trim(),
      started_at: Date.now(),
    }
  }

  function clear_room_post(request_id = '') {
    const current = room_post_state.value
    const next_request_id = String(request_id || '').trim()

    if (next_request_id && current?.request_id && current.request_id !== next_request_id) {
      return
    }

    room_post_state.value = {
      active: false,
      room_id: '',
      request_id: '',
      started_at: 0,
    }
  }

  function is_room_post_busy(room_id = '') {
    const state = room_post_state.value
    if (!state?.active) return false
    if (!room_id) return true
    return String(state.room_id || '').trim() === String(room_id || '').trim()
  }

  async function call_room_shared_post(payload = {}) {
    const room_id = resolve_room_id(payload)
    if (!room_id) {
      throw new Error('room_id missing in room send lane')
    }

    return await call_room_tool('nisb_room_shared_post', {
      ...safe_object(payload),
      room_id,
    })
  }

  async function send_room_message(raw, request_id, runtime_options = {}) {
    const normalized_raw = String(raw || '').trim()
    const room_id = resolve_room_id()
    if (!normalized_raw || !room_id || is_uploading.value) {
      return {
        accepted: false,
        reason: 'invalid_request',
      }
    }

    const runtime_gate = get_current_room_runtime_gate(room_id)
    const runtime_control = normalize_runtime_control_snapshot(
      room_store.runtimeControlSnapshot ||
        room_store.runtime?.runtime_control_snapshot ||
        room_store.runtime?.control_snapshot ||
        room_store.roomState?.runtime_control_snapshot ||
        room_store.roomState ||
        {}
    )

    if (has_meaningful_runtime_control(runtime_control) && !runtime_gate.can_accept_new_prompt) {
      return {
        accepted: false,
        blocked: true,
        room_id,
        request_id,
        current_run_id: runtime_gate.current_run_id,
        runtime_state:
          runtime_gate.runtime_state ||
          runtime_gate.continuation_status ||
          runtime_gate.current_run_status,
        control_block_reason: runtime_gate.control_block_reason,
        message: format_control_block_message(
          runtime_gate.control_block_reason,
          runtime_gate.runtime_state ||
            runtime_gate.continuation_status ||
            runtime_gate.current_run_status
        ),
      }
    }

    if (is_room_post_busy(room_id)) {
      return {
        accepted: false,
        busy: true,
        room_id,
        request_id,
      }
    }

    activate_room_post(room_id, request_id)

    if (typeof room_store?.setRuntimeViewMode === 'function') {
      room_store.setRuntimeViewMode('current')
    }

    if (typeof room_store?.patchRuntimeState === 'function') {
      room_store.patchRuntimeState({
        items: [],
        loading: true,
        loaded_once: false,
        error: '',
        run_id: '',
        latest_event_id: '',
        tail_event_id: '',
        live_hint: false,
        formal_runtime_packet: {},
        runtime_control_snapshot: {},
        formal_runtime_status: '',
        latest_formal_runtime_packet_at: '',
      })
    }

    const sender_uid = resolve_room_sender_uid(room_id)

    const user_message = create_user_message({
      content: normalized_raw,
      response: normalized_raw,
      request_id,
      ...(sender_uid ? { sender: sender_uid } : {}),
    })

    activate_follow_bottom(request_id, {
      idle_ms: 15000,
      max_ms: 180000,
    })

    push_message(messages, user_message)
    input_text.value = ''
    is_thinking.value = true
    hard_scroll_to_bottom()

    const ctx = {
      ...create_empty_stream_state(),
      request_id,
      conv_id: room_id,
      rag_mode: read_string(runtime_options.settings || settings || {}, 'rag_mode') || 'off',
      mcp_overrides: {},
    }

    let room_runtime_started = false

    emit_stream_state(
      build_state_patch(ctx, {
        streaming: true,
        stage: 'meta',
      })
    )

    try {
      const payload = {
        room_id,
        content: normalized_raw,
        request_id,
        model: props.model,
        rag_mode: read_string(runtime_options.settings || settings || {}, 'rag_mode'),
        mode_used: read_string(runtime_options.settings || settings || {}, 'mode_used'),
      }

      const p6_test_control = build_p6_test_control_payload(room_id)
      if (p6_test_control) {
        payload.p6_test_control = p6_test_control
      }

      const raw_result = await call_room_shared_post(payload)

      const result = unwrap_tool_result(raw_result)
      const result_status = read_string(result, 'status')
      const result_message = read_string(result, 'message')

      if (result_status && result_status !== 'success') {
        throw new Error(result_message || 'Room 发送失败')
      }

      apply_common_meta(ctx, result)
      apply_final_meta(ctx, result)

      const raw_tool_calls = read_array(result, 'tool_calls')
      const raw_tool_results = read_array(result, 'tool_results')

      ctx.tool_calls = raw_tool_calls.map((item) => normalize_tool_call(item))
      ctx.tool_results = raw_tool_results.map((item) => normalize_tool_result(item))
      ctx.status = result_status || 'success'
      ctx.message = result_message || 'room runtime started'

      const formalRuntimePatch = build_post_formal_runtime_patch(result)

      if (formalRuntimePatch && typeof room_store?.patchRuntimeState === 'function') {
        room_store.patchRuntimeState(formalRuntimePatch)
      }

      if (formalRuntimePatch && typeof room_store?.patchRoomState === 'function') {
        room_store.patchRoomState({
          current_run_id: '',
          current_run_status: '',
          current_delegate_role_id: '',
          current_delegate_role_name: '',
          current_delegate_index: 0,
          current_delegate_total: 0,
        })
      }

      if (p6_test_control) {
        ctx.p6_test_control = p6_test_control
      }

      room_runtime_started = true

      emit_stream_state(
        build_state_patch(ctx, {
          streaming: true,
          stage: 'room_runtime',
          status: ctx.status,
          message: ctx.message,
          p6_test_control: p6_test_control || undefined,
        })
      )

      if (!formalRuntimePatch) {
        dispatch_room_refresh(room_id, ctx.request_id)
      }
      extend_follow_bottom(30000)
      hard_scroll_to_bottom()
      clear_selected_attachments()

      return {
        accepted: true,
        room_id,
        request_id,
        status: ctx.status,
        message: ctx.message,
      }
    } catch (error) {
      const error_text = error?.message || String(error || 'Room 发送失败')
      ctx.status = 'error'
      ctx.message = error_text

      const assistant_message = create_assistant_message({
        content: error_text,
        response: error_text,
        pending: false,
        request_id,
        status: 'error',
        message: error_text,
        stream_markdown: mark_stream_markdown_error(
          finalize_stream_markdown(create_empty_stream_markdown_state(), error_text)
        ),
      })

      push_message(messages, assistant_message)
      hard_scroll_to_bottom()

      emit_stream_state(
        build_state_patch(ctx, {
          streaming: false,
          stage: 'error',
          status: 'error',
          message: error_text,
        })
      )

      return {
        accepted: false,
        error: true,
        room_id,
        request_id,
        status: 'error',
        message: error_text,
      }
    } finally {
      if (!room_runtime_started) {
        is_thinking.value = false
      }
      clear_active_stream_handles()
      clear_room_post(request_id)
    }
  }

  return {
    is_room_post_busy,
    send_room_message,
  }
}

export default create_room_send_lane

