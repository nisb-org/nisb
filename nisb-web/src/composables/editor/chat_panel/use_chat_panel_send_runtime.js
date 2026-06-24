import { computed, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomStore } from '../../../stores/room'
import { resolve_chat_dispatch } from './use_chat_panel_dispatch'
import {
  create_empty_stream_state,
  patch_message_by_id,
  read_message_by_id,
} from './use_chat_panel_message_writer'
import {
  finalize_stream_markdown,
  mark_stream_markdown_done,
} from '../../chat/use_stream_markdown'
import {
  build_messages_tail_signature,
  ensure_message_stream_state,
  is_terminal_status,
  make_request_id,
} from './use_chat_panel_send_runtime_shared'
import { create_chat_send_lane } from './use_chat_panel_chat_send_lane'
import { create_room_send_lane } from './use_chat_panel_room_send_lane'

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

function read_maybe_ref(value) {
  if (value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, 'value')) {
    return value.value
  }
  return value
}

function format_template(template, vars = {}) {
  return safe_string(template).replace(/\{([^}]+)\}/g, (_, key) => {
    const value = vars?.[key]
    return value === undefined || value === null ? '' : String(value)
  })
}

function normalize_token(value) {
  return safe_string(value).trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function normalize_continuation_status(value) {
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

  return ''
}

function normalize_runtime_state(value) {
  return normalize_continuation_status(value) || normalize_token(value)
}

function is_active_continuation_status(value) {
  return ['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(
    normalize_continuation_status(value)
  )
}

function is_terminal_continuation_status(value) {
  return ['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(
    normalize_continuation_status(value)
  )
}

function fallback_translate(_key, fallback, vars = {}) {
  return format_template(fallback, vars)
}

function format_room_runtime_message(status, translate_text = fallback_translate) {
  const tr = typeof translate_text === 'function' ? translate_text : fallback_translate
  const token = normalize_continuation_status(status) || normalize_token(status)

  if (token === 'pause_requested') return tr('status.pauseRequested', 'pause requested')
  if (token === 'waiting_checkpoint') return tr('status.waitingCheckpoint', 'waiting checkpoint')
  if (token === 'interrupted') return tr('status.interrupted', 'interrupted')
  if (token === 'resumed') return tr('status.resumed', 'resumed')
  if (token === 'completed_after_resume') return tr('status.completedAfterResume', 'completed after resume')
  if (token === 'completed') return tr('status.completed', 'completed')
  if (token === 'budget_exhausted') return tr('status.budgetExhausted', 'budget exhausted')
  if (token === 'running') return tr('status.roomRuntimeActive', 'room runtime active')
  if (token === 'aborted') return tr('status.aborted', 'aborted')
  if (token === 'error') return tr('status.error', 'error')

  return token || tr('status.roomRuntimeActive', 'room runtime active')
}

function format_control_block_message(reason, fallback_status = '', translate_text = fallback_translate) {
  const tr = typeof translate_text === 'function' ? translate_text : fallback_translate
  const token = normalize_token(reason)

  if (token === 'pause_requested' || token === 'pause_requested_pending_checkpoint') {
    return tr('control.pauseRequested', 'Pause requested. Waiting for a safe checkpoint.')
  }
  if (token === 'waiting_checkpoint') {
    return tr('control.waitingCheckpoint', 'A safe checkpoint is pending. New prompts are temporarily blocked.')
  }
  if (token === 'interrupted_resume_ready' || token === 'resume_ready') {
    return tr('control.resumeReady', 'The current run is interrupted. Resume from the checkpoint first.')
  }
  if (token === 'interrupted') {
    return tr('control.interrupted', 'The current run is interrupted. New prompts are temporarily blocked.')
  }
  if (token === 'run_running' || token === 'running') {
    return tr('control.running', 'The current run is still active. New prompts are temporarily blocked.')
  }
  if (token === 'budget_exhausted') {
    return tr('control.budgetExhausted', 'The step budget is exhausted. Sending is temporarily unavailable.')
  }
  if (token === 'error_blocking_resume' || token === 'resume_blocked_error') {
    return tr('control.resumeBlockedError', 'A blocking resume error is present. New prompts are temporarily blocked.')
  }

  const fallback = safe_string(reason).trim()
  if (fallback) return fallback

  return format_room_runtime_message(fallback_status || 'running', tr)
}

function has_usable_value(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return !!value.trim()
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

function has_own(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key)
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

  const runtime_state = normalize_runtime_state(
    read_control_value(candidates, ['runtime_state', 'runtimeState', 'state'])
  )

  const runtime_phase = normalize_runtime_state(
    read_control_value(candidates, ['runtime_phase', 'runtimePhase', 'phase'])
  )

  return {
    runtime_state,
    runtime_phase,
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
    pause_requested: safe_boolean(
      read_control_value(candidates, ['pause_requested', 'pauseRequested']),
      false
    ),
    pause_request_accepted: safe_boolean(
      read_control_value(candidates, ['pause_request_accepted', 'pauseRequestAccepted']),
      false
    ),
    pause_effective: safe_boolean(
      read_control_value(candidates, ['pause_effective', 'pauseEffective']),
      false
    ),
    resume_ready: safe_boolean(
      read_control_value(candidates, ['resume_ready', 'resumeReady']),
      false
    ),
    budget_exhausted: safe_boolean(
      read_control_value(candidates, ['budget_exhausted', 'budgetExhausted']),
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

function resolve_effective_stream_mode({ payload, use_stream }) {
  const requested = !!use_stream
  if (!requested) return false

  const stream_capability = String(
    payload?.stream_capability || payload?.streamCapability || ''
  ).trim().toLowerCase()

  if (
    stream_capability === 'sse' ||
    stream_capability === 'native_stream' ||
    stream_capability === 'stream'
  ) {
    return true
  }

  return true
}

function normalize_time_filter_days(value) {
  if (value === null || value === undefined || value === '') return null
  let n = parseInt(value, 10)
  if (Number.isNaN(n)) return null
  n = Math.max(0, Math.min(3650, n))
  return n
}

function normalize_time_boundary(value) {
  if (value === null || value === undefined || value === '') return null
  const s = String(value).trim()
  if (!s) return null

  const ms = Date.parse(s)
  if (!Number.isFinite(ms)) return null

  return new Date(ms).toISOString()
}

function resolve_runtime_doc_time_window(runtime_options = {}) {
  const overrides = runtime_options?.payload_overrides || {}

  const raw_time_start =
    overrides.time_start !== undefined
      ? overrides.time_start
      : runtime_options?.time_start

  const raw_time_end =
    overrides.time_end !== undefined
      ? overrides.time_end
      : runtime_options?.time_end

  const time_start = normalize_time_boundary(raw_time_start)
  const time_end = normalize_time_boundary(raw_time_end)

  if (time_start !== null || time_end !== null) {
    return {
      mode: 'relative',
      time_filter_days: null,
      time_start,
      time_end,
    }
  }

  const raw_time_filter_days =
    overrides.time_filter_days !== undefined
      ? overrides.time_filter_days
      : runtime_options?.time_filter_days

  return {
    mode: 'days',
    time_filter_days: normalize_time_filter_days(raw_time_filter_days),
    time_start: null,
    time_end: null,
  }
}

function apply_runtime_payload_overrides(payload = {}, runtime_options = {}) {
  const next_payload = {
    ...(payload || {}),
  }

  const resolved = resolve_runtime_doc_time_window(runtime_options)

  if (resolved.mode === 'relative') {
    delete next_payload.time_filter_days

    if (resolved.time_start !== null) next_payload.time_start = resolved.time_start
    else delete next_payload.time_start

    if (resolved.time_end !== null) next_payload.time_end = resolved.time_end
    else delete next_payload.time_end

    return next_payload
  }

  delete next_payload.time_start
  delete next_payload.time_end

  if (resolved.time_filter_days !== null) {
    next_payload.time_filter_days = resolved.time_filter_days
  } else {
    delete next_payload.time_filter_days
  }

  return next_payload
}

export function use_chat_panel_send_runtime({
  props,
  emit,
  chat_cfg,
  selected_attachments,
  messages,
  input_text,
  is_thinking,
  is_uploading,
  call_tool,
  call_tool_stream,
  cancel_by_dedupe_key,
  scroll_to_bottom,
  settings = {},
  agent_cfg = {},
  t: injected_t,
  translate,
  locale_value,
  settings_locale,
}) {
  const room_store = useRoomStore()

  let i18n_t = null
  let i18n_locale = null

  try {
    const i18n = useI18n({ useScope: 'global' })
    i18n_t = i18n.t
    i18n_locale = i18n.locale
  } catch (_) {}

  function current_locale_marker() {
    const candidates = [
      locale_value,
      settings_locale,
      settings?.locale,
      settings?.settings?.locale,
      agent_cfg?.locale,
      i18n_locale,
      'en',
    ]

    for (const candidate of candidates) {
      const value = safe_string(read_maybe_ref(candidate)).trim()
      if (value) return value
    }

    return 'en'
  }

  function pick_translate_function() {
    if (typeof injected_t === 'function') return injected_t
    if (typeof translate === 'function') return translate
    if (typeof i18n_t === 'function') return i18n_t
    return null
  }

  function tr(key, fallback = '', vars = {}) {
    current_locale_marker()

    const full_key = key.includes('.') ? `room.chatRuntime.${key}` : `room.chatRuntime.${key}`
    const fn = pick_translate_function()

    if (fn) {
      try {
        const value = safe_string(fn(full_key, vars)).trim()
        if (value && value !== full_key) return value
      } catch (_) {}
    }

    return format_template(fallback || full_key, vars)
  }

  const active_stream_state = ref(create_empty_stream_state())
  const current_conv_id = ref('')
  const follow_bottom_state = ref({
    active: false,
    request_id: '',
    until: 0,
    max_until: 0,
  })
  const room_post_state = ref({
    active: false,
    request_id: '',
    room_id: '',
    started_at: 0,
  })

  const local_room_runtime_stop = ref({
    room_id: '',
    run_id: '',
    until: 0,
  })

  const stream_runtime = {
    seq: 0,
    abort: null,
    dedupe_key: '',
    assistant_message_id: '',
  }

  watch(
    () => props.convId,
    (value) => {
      current_conv_id.value = String(value || '').trim()
    },
    { immediate: true }
  )

  const stream_banner_visible = computed(() => {
    return !!active_stream_state.value.streaming
  })

  const stream_banner_text = computed(() => {
    const stage = String(active_stream_state.value.stage || '').trim()
    if (stage === 'tool_call') return tr('stream.toolCall', 'Calling tool...')
    if (stage === 'tool_result') return tr('stream.toolResult', 'Tool returned. Preparing the answer...')
    if (stage === 'final') return tr('stream.final', 'Finishing output...')
    if (stage === 'meta') return tr('stream.meta', 'Preparing request...')
    if (stage === 'room_runtime') return tr('stream.roomRuntime', 'Room is running...')
    return tr('stream.default', 'Streaming response...')
  })

  const room_runtime_control_snapshot = computed(() => {
    return normalize_runtime_control_snapshot(
      room_store.runtimeControlSnapshot ||
        room_store.runtime?.runtime_control_snapshot ||
        room_store.runtime?.control_snapshot ||
        room_store.roomState?.runtime_control_snapshot ||
        room_store.roomState ||
        {}
    )
  })

  const current_room_runtime_gate = computed(() => {
    const chat_mode = safe_string(chat_cfg?.chat?.mode).trim().toLowerCase()
    const room_id = safe_string(chat_cfg?.chat?.roomId).trim()

    if (chat_mode !== 'room' || !room_id) {
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
        active: false,
        terminal: false,
      }
    }

    const control = room_runtime_control_snapshot.value

    const continuation_status = normalize_continuation_status(
      room_store.roomState?.continuation_status
    )

    const current_run_status = normalize_continuation_status(
      room_store.roomState?.current_run_status || room_store.currentRunStatus
    )

    const current_run_id = safe_string(
      room_store.roomState?.current_run_id || room_store.currentRunId
    ).trim()

    const runtime_state = normalize_runtime_state(control.runtime_state)
    const runtime_phase = normalize_runtime_state(control.runtime_phase)
    const can_accept_new_prompt = control.can_accept_new_prompt
    const control_block_reason = safe_string(control.control_block_reason).trim()
    const can_pause_current = !!control.can_pause_current
    const can_resume = !!control.can_resume

    let active = false
    let terminal = false

    if (runtime_state) {
      active = ['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(runtime_state)
      terminal = ['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(runtime_state)
    } else if (continuation_status) {
      active = is_active_continuation_status(continuation_status)
      terminal = is_terminal_continuation_status(continuation_status)
    } else if (current_run_status) {
      active = is_active_continuation_status(current_run_status)
      terminal = is_terminal_continuation_status(current_run_status)
    }

    if (!active && !terminal && current_run_id && room_store.runtimeLive === true) {
      active = true
    }

    return {
      room_id,
      current_run_id,
      continuation_status,
      current_run_status,
      runtime_state,
      runtime_phase,
      can_accept_new_prompt,
      control_block_reason,
      can_pause_current,
      can_resume,
      active,
      terminal,
    }
  })

  function emit_stream_state(patch = {}) {
    active_stream_state.value = {
      ...active_stream_state.value,
      ...patch,
    }
    emit('stream-state', { ...active_stream_state.value })
  }

  function emit_stream_final(payload = {}) {
    emit('stream-final', payload)
  }

  function reset_stream_state() {
    active_stream_state.value = create_empty_stream_state()
  }

  function update_conv_id(next_value, options = {}) {
    const next_conv_id = String(next_value || '').trim()
    if (!next_conv_id) return

    current_conv_id.value = next_conv_id

    if (options.emit_upstream === false) return
    emit('update-conv-id', next_conv_id)
  }

  function clear_active_stream_handles() {
    stream_runtime.abort = null
    stream_runtime.dedupe_key = ''
    stream_runtime.assistant_message_id = ''
  }

  function clear_selected_attachments() {
    if (selected_attachments && Array.isArray(selected_attachments.value)) {
      selected_attachments.value = []
    }
  }

  function hard_scroll_to_bottom() {
    nextTick(() => {
      try {
        scroll_to_bottom?.(true)
      } catch {}
    })
  }

  function activate_follow_bottom(request_id = '', options = {}) {
    const now = Date.now()
    const idle_ms = Math.max(1000, Number(options.idle_ms || 8000))
    const max_ms = Math.max(idle_ms, Number(options.max_ms || 120000))

    follow_bottom_state.value = {
      active: true,
      request_id: String(request_id || '').trim(),
      until: now + idle_ms,
      max_until: now + max_ms,
    }
  }

  function extend_follow_bottom(extra_ms = 8000) {
    const state = follow_bottom_state.value
    if (!state?.active) return

    const now = Date.now()
    if (now >= Number(state.max_until || 0)) {
      follow_bottom_state.value = {
        active: false,
        request_id: '',
        until: 0,
        max_until: 0,
      }
      return
    }

    follow_bottom_state.value = {
      ...state,
      until: Math.min(
        Number(state.max_until || 0),
        Math.max(Number(state.until || 0), now + Math.max(1000, Number(extra_ms || 0)))
      ),
    }
  }

  function deactivate_follow_bottom() {
    follow_bottom_state.value = {
      active: false,
      request_id: '',
      until: 0,
      max_until: 0,
    }
  }

  function should_follow_bottom() {
    const state = follow_bottom_state.value
    if (!state?.active) return false

    const now = Date.now()
    if (now > Number(state.until || 0) || now > Number(state.max_until || 0)) {
      deactivate_follow_bottom()
      return false
    }
    return true
  }

  function clear_local_room_runtime_stop() {
    local_room_runtime_stop.value = {
      room_id: '',
      run_id: '',
      until: 0,
    }
  }

  function mark_local_room_runtime_stop(payload = {}) {
    const room_id = safe_string(
      payload?.room_id || chat_cfg?.chat?.roomId || active_stream_state.value.conv_id
    ).trim()
    const run_id = safe_string(
      payload?.run_id || current_room_runtime_gate.value.current_run_id
    ).trim()

    if (!room_id) return

    local_room_runtime_stop.value = {
      room_id,
      run_id,
      until: Date.now() + 2 * 60 * 1000,
    }
  }

  function is_local_room_runtime_stop_active(room_id = '', run_id = '') {
    const state = local_room_runtime_stop.value
    const now = Date.now()

    if (!state?.room_id || now > Number(state.until || 0)) {
      clear_local_room_runtime_stop()
      return false
    }

    if (safe_string(state.room_id).trim() !== safe_string(room_id).trim()) {
      return false
    }

    const saved_run_id = safe_string(state.run_id).trim()
    const next_run_id = safe_string(run_id).trim()

    if (saved_run_id && next_run_id && saved_run_id !== next_run_id) {
      return false
    }

    return true
  }

  watch(
    () => build_messages_tail_signature(messages?.value),
    (next_value, prev_value) => {
      if (!next_value || next_value === prev_value) return
      if (!should_follow_bottom()) return
      extend_follow_bottom(9000)
      hard_scroll_to_bottom()
    }
  )

  function begin_room_runtime(payload = {}) {
    const room_id = safe_string(
      payload?.room_id || payload?.conv_id || chat_cfg?.chat?.roomId || active_stream_state.value.conv_id
    ).trim()

    if (!room_id) return

    const request_id = safe_string(
      payload?.request_id || payload?.requestId || payload?.run_id || active_stream_state.value.request_id
    ).trim()

    const status = safe_string(
      payload?.status || active_stream_state.value.status || 'running'
    ).trim() || 'running'

    const message = safe_string(
      payload?.message || active_stream_state.value.message || format_room_runtime_message(status, tr)
    ).trim() || format_room_runtime_message(status, tr)

    active_stream_state.value = {
      ...active_stream_state.value,
      request_id,
      conv_id: room_id,
      status,
      message,
      streaming: true,
      stage: 'room_runtime',
      rag_mode:
        safe_string(active_stream_state.value.rag_mode).trim() ||
        safe_string(settings?.rag_mode).trim() ||
        'off',
      mode_used:
        safe_string(active_stream_state.value.mode_used).trim() ||
        safe_string(settings?.mode_used).trim(),
    }

    emit('stream-state', { ...active_stream_state.value })

    try {
      if (is_thinking && !is_thinking.value) {
        is_thinking.value = true
      }
    } catch {}
  }

  async function stop_room_runtime_current(payload = {}) {
    const room_id = safe_string(
      payload?.room_id || chat_cfg?.chat?.roomId || active_stream_state.value.conv_id
    ).trim()

    if (!room_id) return null

    const run_id = safe_string(
      payload?.run_id || current_room_runtime_gate.value.current_run_id
    ).trim()

    try {
      return await call_tool('nisb_room_runtime_stop_current', {
        room_id,
        run_id,
        reason: safe_string(payload?.reason || 'manual_stop').trim() || 'manual_stop',
        write_aborted_message: true,
      })
    } catch (ex) {
      console.warn('[room-runtime] stop_current failed', ex)
      return null
    }
  }

  function stop_local_stream() {
    const request_id = active_stream_state.value.request_id
    const conv_id = active_stream_state.value.conv_id
    const rag_mode = active_stream_state.value.rag_mode
    const mode_used = active_stream_state.value.mode_used
    const mcp_overrides = active_stream_state.value.mcp_overrides
    const is_room_runtime = safe_string(active_stream_state.value.stage).trim() === 'room_runtime'

    if (is_room_runtime) {
      const room_id = conv_id || chat_cfg?.chat?.roomId || ''
      const run_id = current_room_runtime_gate.value.current_run_id

      mark_local_room_runtime_stop({
        room_id,
        run_id,
      })

      void stop_room_runtime_current({
        room_id,
        run_id,
        reason: 'manual_stop',
      })
    }

    if (stream_runtime.assistant_message_id) {
      const current_message = read_message_by_id(messages, stream_runtime.assistant_message_id)
      const current_text = String(current_message?.response || current_message?.content || '')
      const next_text = current_text || tr('messages.stopped', 'Stopped.')
      const current_stream = ensure_message_stream_state(current_message, next_text)

      patch_message_by_id(messages, stream_runtime.assistant_message_id, {
        pending: false,
        content: next_text,
        response: next_text,
        status: 'aborted',
        message: format_room_runtime_message('aborted', tr),
        stream_markdown: mark_stream_markdown_done(
          finalize_stream_markdown(current_stream, next_text)
        ),
      })
    }

    try {
      if (stream_runtime.dedupe_key) {
        cancel_by_dedupe_key(stream_runtime.dedupe_key)
      }
    } catch {}

    try {
      if (stream_runtime.abort && typeof stream_runtime.abort.abort === 'function') {
        stream_runtime.abort.abort()
      }
    } catch {}

    stream_runtime.seq += 1
    clear_active_stream_handles()
    reset_stream_state()
    deactivate_follow_bottom()

    try {
      if (is_thinking?.value) {
        is_thinking.value = false
      }
    } catch {}

    emit('stream-state', {
      ...create_empty_stream_state(),
      request_id,
      conv_id,
      rag_mode,
      mode_used,
      mcp_overrides,
      status: 'aborted',
      message: format_room_runtime_message('aborted', tr),
    })
  }

  function finish_room_runtime(payload = {}) {
    const current = active_stream_state.value || {}
    const next_request_id =
      String(payload?.request_id || '').trim() ||
      String(payload?.requestId || '').trim() ||
      String(current.request_id || '').trim()

    const next_status =
      String(payload?.status || '').trim() ||
      String(current.status || '').trim() ||
      'success'

    const next_message =
      String(payload?.message || '').trim() ||
      String(current.message || '').trim()

    if (is_terminal_continuation_status(next_status) || next_status === 'error' || next_status === 'aborted') {
      clear_local_room_runtime_stop()
    }

    const next_stage = is_terminal_status(next_status)
      ? (next_status === 'error' ? 'error' : 'final')
      : 'final'

    active_stream_state.value = {
      ...current,
      request_id: next_request_id,
      status: next_status,
      message: next_message,
      streaming: false,
      stage: next_stage,
    }

    emit('stream-state', { ...active_stream_state.value })
    deactivate_follow_bottom()
    clear_active_stream_handles()

    try {
      if (is_thinking?.value) {
        is_thinking.value = false
      }
    } catch {}
  }

  watch(
    () => ({
      chat_mode: safe_string(chat_cfg?.chat?.mode).trim().toLowerCase(),
      room_id: safe_string(chat_cfg?.chat?.roomId).trim(),
      gate_room_id: current_room_runtime_gate.value.room_id,
      continuation_status: current_room_runtime_gate.value.continuation_status,
      current_run_status: current_room_runtime_gate.value.current_run_status,
      current_run_id: current_room_runtime_gate.value.current_run_id,
      runtime_state: current_room_runtime_gate.value.runtime_state,
      runtime_phase: current_room_runtime_gate.value.runtime_phase,
      can_accept_new_prompt: !!current_room_runtime_gate.value.can_accept_new_prompt,
      control_block_reason: safe_string(current_room_runtime_gate.value.control_block_reason).trim(),
      runtime_active: !!current_room_runtime_gate.value.active,
      runtime_terminal: !!current_room_runtime_gate.value.terminal,
      local_stage: safe_string(active_stream_state.value.stage).trim(),
      local_conv_id: safe_string(active_stream_state.value.conv_id).trim(),
      local_status: safe_string(active_stream_state.value.status).trim(),
      room_post_active: !!room_post_state.value?.active,
      room_post_room_id: safe_string(room_post_state.value?.room_id).trim(),
    }),
    (state) => {
      const is_room_mode = state.chat_mode === 'room'
      const room_id = state.room_id

      if (!is_room_mode || !room_id) {
        clear_local_room_runtime_stop()

        const is_local_room_runtime =
          state.local_stage === 'room_runtime' &&
          (!state.local_conv_id || state.local_conv_id === state.room_id)

        if (is_local_room_runtime && active_stream_state.value.streaming) {
          finish_room_runtime({
            status: safe_string(active_stream_state.value.status).trim() || 'success',
            message: safe_string(active_stream_state.value.message).trim() || tr('status.roomRuntimeDetached', 'room runtime detached'),
          })
        }
        return
      }

      if (state.runtime_terminal) {
        clear_local_room_runtime_stop()

        const owns_local_room_runtime =
          state.local_stage === 'room_runtime' &&
          (!state.local_conv_id || state.local_conv_id === room_id)

        if (owns_local_room_runtime || is_thinking?.value) {
          const next_status =
            state.runtime_state ||
            state.continuation_status ||
            state.current_run_status ||
            'success'

          finish_room_runtime({
            request_id: safe_string(active_stream_state.value.request_id).trim(),
            status: next_status,
            message: format_room_runtime_message(next_status, tr),
          })
        }
        return
      }

      if (state.runtime_active) {
        const next_status =
          state.runtime_state ||
          state.continuation_status ||
          (['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(state.current_run_status)
            ? state.current_run_status
            : 'running')

        if (is_local_room_runtime_stop_active(room_id, state.current_run_id)) {
          try {
            if (is_thinking.value) is_thinking.value = false
          } catch {}
          return
        }

        const should_sync =
          state.local_stage !== 'room_runtime' ||
          state.local_conv_id !== room_id ||
          normalize_continuation_status(state.local_status) !== normalize_continuation_status(next_status)

        if (should_sync) {
          begin_room_runtime({
            room_id,
            run_id: state.current_run_id,
            status: next_status,
            message: format_room_runtime_message(next_status, tr),
          })
        } else {
          try {
            if (!is_thinking.value) is_thinking.value = true
          } catch {}
        }

        return
      }

      if (!state.runtime_active && !state.room_post_active) {
        const owns_local_room_runtime =
          state.local_stage === 'room_runtime' &&
          (!state.local_conv_id || state.local_conv_id === room_id)

        if (owns_local_room_runtime || is_thinking?.value) {
          finish_room_runtime({
            request_id: safe_string(active_stream_state.value.request_id).trim(),
            status: safe_string(active_stream_state.value.status).trim() || 'success',
            message: safe_string(active_stream_state.value.message).trim() || tr('status.roomRuntimeIdle', 'room runtime idle'),
          })
        }
      }
    },
    { immediate: true }
  )

  const chat_lane = create_chat_send_lane({
    messages,
    input_text,
    is_thinking,
    is_uploading,
    call_tool,
    call_tool_stream,
    cancel_by_dedupe_key,
    current_conv_id,
    stream_runtime,
    stop_local_stream,
    emit_stream_state,
    emit_stream_final,
    update_conv_id,
    clear_selected_attachments,
    hard_scroll_to_bottom,
    activate_follow_bottom,
    extend_follow_bottom,
    clear_active_stream_handles,
  })

  const room_lane = create_room_send_lane({
    props,
    chat_cfg,
    settings,
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
  })

  async function send_message(raw, runtime_options = {}) {
    const normalized_raw = String(raw || '').trim()
    if (!normalized_raw || is_uploading.value) return

    const request_id = make_request_id()
    const chat_mode = String(chat_cfg?.chat?.mode || '').trim().toLowerCase()
    const is_room_mode = chat_mode === 'room'
    const room_id = String(chat_cfg?.chat?.roomId || '').trim()

    if (is_room_mode) {
      if (!room_id) {
        emit_stream_state({
          ...create_empty_stream_state(),
          request_id,
          conv_id: '',
          stage: 'error',
          status: 'error',
          message: tr('errors.roomIdMissing', 'room_id missing in room mode'),
          streaming: false,
        })

        try {
          if (is_thinking?.value) {
            is_thinking.value = false
          }
        } catch {}

        return
      }

      const gate = current_room_runtime_gate.value

      if (
        has_meaningful_runtime_control(room_runtime_control_snapshot.value) &&
        !gate.can_accept_new_prompt
      ) {
        if (!is_local_room_runtime_stop_active(room_id, gate.current_run_id)) {
          begin_room_runtime({
            room_id,
            run_id: gate.current_run_id,
            status:
              gate.runtime_state ||
              gate.continuation_status ||
              gate.current_run_status ||
              'running',
            message: format_control_block_message(
              gate.control_block_reason,
              gate.runtime_state || gate.continuation_status || gate.current_run_status || 'running',
              tr
            ),
          })
        }
        return
      }

      if (room_lane.is_room_post_busy(room_id)) {
        if (!is_local_room_runtime_stop_active(room_id, gate.current_run_id)) {
          begin_room_runtime({
            room_id,
            status: gate.runtime_state || 'running',
            message: format_room_runtime_message(gate.runtime_state || 'running', tr),
          })
        }
        return
      }

      clear_local_room_runtime_stop()
      await room_lane.send_room_message(normalized_raw, request_id, runtime_options)
      return
    }

    if (is_thinking.value) return

    const { payload, tool_name, use_stream } = resolve_chat_dispatch({
      raw_input: normalized_raw,
      request_id,
      model: props.model,
      conv_id: current_conv_id.value || props.convId || '',
      chat_cfg,
      selected_attachments: Array.isArray(selected_attachments?.value)
        ? selected_attachments.value
        : [],
      settings: runtime_options.settings || settings || {},
      agent_cfg: runtime_options.agent_cfg || agent_cfg || {},
    })

    const final_payload = apply_runtime_payload_overrides(payload, runtime_options)

    const effective_use_stream = resolve_effective_stream_mode({
      tool_name,
      payload: final_payload,
      use_stream,
    })

    if (effective_use_stream) {
      await chat_lane.send_chat_message_stream(normalized_raw, tool_name, final_payload, request_id)
      return
    }

    await chat_lane.send_chat_message_non_stream(normalized_raw, tool_name, final_payload, request_id)
  }

  return {
    active_stream_state,
    stream_banner_visible,
    stream_banner_text,
    stop_local_stream,
    begin_room_runtime,
    finish_room_runtime,
    send_message,
  }
}

export default use_chat_panel_send_runtime
