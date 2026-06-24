import { nextTick, ref } from 'vue'
import { use_chat_panel_send_runtime } from './use_chat_panel_send_runtime'

function _normalize_bool(v, fallback = false) {
  if (typeof v === 'boolean') return v
  const s = String(v ?? '').trim().toLowerCase()
  if (!s) return !!fallback
  return s === 'true' || s === '1' || s === 'yes' || s === 'on'
}

function _normalize_days(v, fallback = 3) {
  let n = parseInt(v, 10)
  if (Number.isNaN(n)) n = fallback
  return Math.max(0, Math.min(3650, n))
}

function _normalize_limit(v, fallback = 8) {
  let n = parseInt(v, 10)
  if (Number.isNaN(n)) n = fallback
  return Math.max(1, Math.min(20, n))
}

function _normalize_min_score(v, fallback = 0.28) {
  let x = Number(v)
  if (Number.isNaN(x)) x = fallback
  x = Math.max(0.0, Math.min(1.0, x))
  return Math.round(x * 100) / 100
}

function _normalize_doc_time_mode(v) {
  const s = String(v || 'days').trim().toLowerCase()
  return s === 'relative' ? 'relative' : 'days'
}

function _normalize_nullable_non_negative_int(v, fallback = null) {
  if (v === null || v === undefined) return fallback
  const s = String(v).trim()
  if (!s) return fallback

  let n = parseInt(s, 10)
  if (Number.isNaN(n)) return fallback
  n = Math.max(0, Math.min(3650, n))
  return n
}

function _normalize_relative_range(raw = {}) {
  let olderDaysAgo = _normalize_nullable_non_negative_int(raw?.olderDaysAgo, 30)
  let newerDaysAgo = _normalize_nullable_non_negative_int(raw?.newerDaysAgo, 21)

  if (olderDaysAgo === null && newerDaysAgo === null) {
    olderDaysAgo = 30
    newerDaysAgo = 21
  }

  if (
    olderDaysAgo !== null &&
    newerDaysAgo !== null &&
    olderDaysAgo < newerDaysAgo
  ) {
    const tmp = olderDaysAgo
    olderDaysAgo = newerDaysAgo
    newerDaysAgo = tmp
  }

  return {
    olderDaysAgo,
    newerDaysAgo,
  }
}

function _days_ago_to_iso(daysAgo) {
  const n = _normalize_nullable_non_negative_int(daysAgo, null)
  if (n === null) return null
  return new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString()
}

function _safe_trim(v) {
  return String(v ?? '').trim()
}

function _build_doc_time_snapshot(chat_cfg) {
  const raw = chat_cfg?.rag?.docTime || {}
  const enabled = _normalize_bool(raw?.enabled, false)
  const mode = _normalize_doc_time_mode(raw?.mode)
  const days = _normalize_days(raw?.days, 3)
  const relative = _normalize_relative_range(raw?.relative || {})

  let time_filter_days = null
  let time_start = null
  let time_end = null

  if (enabled) {
    if (mode === 'relative') {
      time_start = _days_ago_to_iso(relative.olderDaysAgo)
      time_end = _days_ago_to_iso(relative.newerDaysAgo)

      if (!time_start && !time_end) {
        time_filter_days = days
      }
    } else {
      time_filter_days = days
    }
  }

  return {
    enabled,
    mode,
    days,
    relative,
    time_filter_days,
    time_start,
    time_end,
  }
}

function _build_rss_reference_snapshot(chat_cfg) {
  const raw = chat_cfg?.rag?.rssReference || chat_cfg?.rag?.rss || {}

  return {
    enabled: _normalize_bool(raw?.enabled, true),
    days: _normalize_days(raw?.days, 7),
    limit: _normalize_limit(raw?.limit, 8),
    minScore: _normalize_min_score(raw?.minScore, 0.28),
    strictLexical: _normalize_bool(raw?.strictLexical, true),
  }
}

function _build_rag_context_snapshot(chat_cfg) {
  const rag = chat_cfg?.rag || {}
  const ctx = rag?.context || {}

  return {
    mode: String(rag?.mode || 'off'),
    storeScope: String(rag?.storeScope || 'global'),
    evidenceScope: String(rag?.evidenceScope || 'global'),
    context: {
      libraryId: ctx?.libraryId || null,
      docId: ctx?.docId || null,
      group_id: ctx?.group_id || null,
    },

    docTime: _build_doc_time_snapshot(chat_cfg),
    rssReference: _build_rss_reference_snapshot(chat_cfg),
  }
}

function _build_time_payload_overrides(doc_time = {}) {
  if (!doc_time?.enabled) return {}

  if (doc_time?.mode === 'relative') {
    const payload = {}
    if (doc_time.time_start) payload.time_start = doc_time.time_start
    if (doc_time.time_end) payload.time_end = doc_time.time_end
    return payload
  }

  if (doc_time?.time_filter_days != null) {
    return { time_filter_days: doc_time.time_filter_days }
  }

  return {}
}

export function use_chat_panel_sender({
  props,
  emit,

  call_tool,
  call_tool_stream,

  settings,
  chat_cfg,
  agent_cfg,

  messages,
  input_text,
  selected_attachments,
  is_thinking,
  is_composing,
  stream_ctrl,

  scroll_to_bottom,
  emit_chat_outline_update,
  enhance_chat_dom,
}) {
  const is_uploading = ref(false)

  function cancel_by_dedupe_key() {}

  const runtime = use_chat_panel_send_runtime({
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
    settings,
    agent_cfg,
  })

  function sync_stream_ctrl() {
    if (!stream_ctrl) return

    stream_ctrl.value = {
      abort() {
        runtime.stop_local_stream()
      },
    }
  }

  function build_runtime_options() {
    const rag_snapshot = _build_rag_context_snapshot(chat_cfg)
    const doc_time = rag_snapshot.docTime
    const rss_reference = rag_snapshot.rssReference
    const payload_overrides = _build_time_payload_overrides(doc_time)

    return {
      settings,
      agent_cfg,

      rag_snapshot,
      doc_time,
      rss_reference,

      time_filter_days: doc_time.time_filter_days,
      time_start: doc_time.time_start,
      time_end: doc_time.time_end,

      payload_overrides,
    }
  }

  function can_send_now() {
    if (is_thinking?.value) return false
    if (is_composing?.value) return false
    if (is_uploading?.value) return false
    return true
  }

  function read_input_text() {
    return _safe_trim(input_text?.value)
  }

  sync_stream_ctrl()

  async function refresh_after_send() {
    await nextTick()

    try {
      scroll_to_bottom?.(true)
    } catch {}

    try {
      emit_chat_outline_update?.()
    } catch {}

    try {
      enhance_chat_dom?.()
    } catch {}
  }

  async function send_action() {
    if (!can_send_now()) return

    const raw = read_input_text()
    if (!raw) return

    try {
      await runtime.send_message(raw, build_runtime_options())
    } finally {
      await refresh_after_send()
      sync_stream_ctrl()
    }
  }

  function stopStreaming() {
    runtime.stop_local_stream()
    sync_stream_ctrl()
  }

  function finishRoomRuntime(payload = {}) {
    runtime.finish_room_runtime(payload)
    sync_stream_ctrl()
  }

  function onTextareaKeydown(event) {
    if (!can_send_now()) return

    const is_submit =
      event?.key === 'Enter' &&
      !event?.shiftKey &&
      !!(event?.ctrlKey || event?.metaKey)

    if (!is_submit) return

    event.preventDefault()
    void send_action()
  }

  async function sendChatMessage() {
    return await send_action()
  }

  return {
    onTextareaKeydown,
    sendChatMessage,
    stopStreaming,
    finishRoomRuntime,
    active_stream_state: runtime.active_stream_state,
    stream_banner_visible: runtime.stream_banner_visible,
    stream_banner_text: runtime.stream_banner_text,
  }
}

export default use_chat_panel_sender
