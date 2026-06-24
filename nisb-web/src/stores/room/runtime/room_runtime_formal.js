import {
  safe_array,
  safe_object,
  safe_string,
  normalize_bool,
  normalize_int,
} from '../room_shared'
import {
  sort_runtime_events,
  normalize_room_runtime_event,
  get_runtime_result_event_from_list,
} from '../room_event_helpers'
import {
  get_runtime_payload,
  get_runtime_run_id,
  normalize_tool_results,
} from '../room_protocol'

const TERMINAL_RUNTIME_EVENT_TYPES = new Set([
  'room.final',
  'room.abort',
  'room.aborted',
  'room.error',
  'room.runtime_manual',
  'room.runtime_skipped',
  'room.runtime_denied',
  'room.runtime_no_auto_reply',
  'room.runtime_no-auto-reply',
])

const ACTIVE_RUNTIME_STATUS_TOKENS = [
  'running',
  'live',
  'processing',
  'planning',
  'delegating',
  'synthesizing',
  'working',
  'in_progress',
  'queued',
  'pending',
  '处理中',
  '运行中',
  '规划中',
  '委派中',
  '汇总中',
]

const TERMINAL_RUNTIME_STATUS_TOKENS = [
  'completed',
  'complete',
  'done',
  'finished',
  'failed',
  'error',
  'aborted',
  'abort',
  'cancelled',
  'canceled',
  'terminated',
  'timed_out',
  'timed out',
  'success',
  'successful',
  '已完成',
  '已结束',
  '完成',
  '失败',
  '错误',
  '已中止',
  '中止',
  '已取消',
  '取消',
]

const LEGAL_RUNTIME_STATUS_TOKENS = [
  'manual',
  'skipped',
  'skip',
  'denied',
  'deny',
  'no-auto-reply',
  'no_auto_reply',
  'no auto reply',
  'room.runtime_manual',
  'room.runtime_skipped',
  'room.runtime_denied',
  'room.runtime_no_auto_reply',
  'room.runtime_no-auto-reply',
]

function first_array_candidate(...values) {
  let first_array = null

  for (const value of values) {
    if (!Array.isArray(value)) continue
    if (!first_array) first_array = value
    if (value.length > 0) return value
  }

  return first_array || []
}

function pick_runtime_event_list(src) {
  const payload = safe_object(src)

  return first_array_candidate(
    payload.items,
    payload.events,
    payload.process_items,
    payload.processItems,
    payload.timeline_items,
    payload.timelineItems,
    payload.timeline
  )
}

function normalize_runtime_status_value(value) {
  return safe_string(value).trim().toLowerCase()
}

function is_terminal_runtime_event_type(value) {
  return TERMINAL_RUNTIME_EVENT_TYPES.has(safe_string(value).trim())
}

export function is_active_runtime_status_text(value) {
  const token = normalize_runtime_status_value(value)
  if (!token) return false
  return ACTIVE_RUNTIME_STATUS_TOKENS.some((item) => token.includes(item))
}

export function is_terminal_runtime_status_text(value) {
  const token = normalize_runtime_status_value(value)
  if (!token) return false
  return TERMINAL_RUNTIME_STATUS_TOKENS.some((item) => token.includes(item))
}

function is_legal_runtime_status_text(value) {
  const token = normalize_runtime_status_value(value)
  if (!token) return false
  return LEGAL_RUNTIME_STATUS_TOKENS.some((item) => token.includes(item))
}

function normalize_legal_runtime_kind(value) {
  const token = normalize_runtime_status_value(value)
  if (!token) return ''

  if (token.includes('manual')) return 'manual'
  if (token.includes('denied') || token.includes('deny')) return 'denied'
  if (token.includes('skipped') || token.includes('skip')) return 'skipped'
  if (
    token.includes('no-auto-reply') ||
    token.includes('no_auto_reply') ||
    token.includes('no auto reply')
  ) {
    return 'no-auto-reply'
  }

  return ''
}

export function build_legal_runtime_status_label(kind = '') {
  if (kind === 'manual') return '人工处理'
  if (kind === 'skipped') return '已跳过'
  if (kind === 'denied') return '已拒绝'
  if (kind === 'no-auto-reply') return '未自动回复'
  return ''
}

export function build_legal_runtime_result_text(fact = null) {
  const src = safe_object(fact)
  const kind = safe_string(src.kind).trim()
  const message = safe_string(src.message).trim()
  if (message) return message

  if (kind === 'manual') return '消息已进入时间线，当前按人工处理执行。'
  if (kind === 'skipped') return '消息已进入时间线，但当前未触发自动回复。'
  if (kind === 'denied') return '消息已进入时间线，但当前共享能力未获授权执行。'
  if (kind === 'no-auto-reply') return '消息已进入时间线，当前配置未触发自动回复。'
  return ''
}

function pick_first_legal_runtime_status(...values) {
  for (const value of values) {
    const text = safe_string(value).trim()
    if (!text) continue
    if (is_legal_runtime_status_text(text)) return text
  }
  return ''
}

export function extract_legal_runtime_fact(payload = {}, statusText = '') {
  const data = safe_object(payload)
  const formalPacket = safe_object(
    data.formal_runtime_packet ||
      data.current_formal_runtime_packet ||
      data.runtime_packet ||
      data.current_runtime_packet ||
      data.packet
  )
  const runtimeControlSnapshot = safe_object(
    data.runtime_control_snapshot ||
      data.current_runtime_control_snapshot ||
      data.control_snapshot
  )

  const containers = [
    data,
    formalPacket,
    runtimeControlSnapshot,
    safe_object(data.result),
    safe_object(data.payload),
    safe_object(data.current_formal_runtime_packet),
    safe_object(data.current_runtime_control_snapshot),
  ]

  for (const row of containers) {
    const directStatus = pick_first_legal_runtime_status(
      row.type,
      row.event_type,
      row.packet_type,
      row.formal_runtime_type,
      row.current_formal_runtime_type,
      row.kind,
      row.status,
      row.status_text,
      row.runtime_status,
      row.formal_runtime_status,
      row.disposition,
      row.outcome
    )

    if (!directStatus) continue

    return {
      kind: normalize_legal_runtime_kind(directStatus),
      reasonCode: safe_string(
        row.reason_code ||
          row.skip_reason_code ||
          row.deny_reason_code ||
          row.code
      ).trim(),
      path: safe_string(
        row.path ||
          row.runtime_path ||
          row.delivery_path
      ).trim(),
      message: safe_string(
        row.message ||
          row.summary ||
          row.response ||
          row.content
      ).trim(),
      at: safe_string(
        row.latest_formal_runtime_packet_at ||
          row.packet_at ||
          row.updated_at ||
          row.ts
      ).trim(),
    }
  }

  const toolResults = safe_array(normalize_tool_results(data))
  for (const item of toolResults) {
    const row = safe_object(item)
    const rowStatus = pick_first_legal_runtime_status(
      row.type,
      row.status,
      row.status_text,
      row.runtime_status,
      row.formal_runtime_status,
      row.disposition,
      row.outcome,
      row.result?.status,
      row.result?.formal_runtime_status,
      row.payload?.status,
      row.payload?.formal_runtime_status
    )

    if (!rowStatus) continue

    return {
      kind: normalize_legal_runtime_kind(rowStatus),
      reasonCode: safe_string(
        row.reason_code ||
          row.skip_reason_code ||
          row.deny_reason_code ||
          row.code
      ).trim(),
      path: safe_string(row.path || row.runtime_path).trim(),
      message: safe_string(
        row.message ||
          row.summary ||
          row.response ||
          row.content
      ).trim(),
      at: safe_string(row.updated_at || row.ts).trim(),
    }
  }

  const explicitStatus = pick_first_legal_runtime_status(statusText)
  if (explicitStatus) {
    return {
      kind: normalize_legal_runtime_kind(explicitStatus),
      reasonCode: '',
      path: '',
      message: '',
      at: '',
    }
  }

  return null
}

export function build_formal_runtime_payload(source = {}) {
  const src = safe_object(source)

  const formalRuntimePacket = safe_object(
    src.formal_runtime_packet ||
      src.current_formal_runtime_packet ||
      src.runtime_packet ||
      src.current_runtime_packet ||
      src.packet
  )

  const currentFormalRuntimePacket = safe_object(
    src.current_formal_runtime_packet ||
      src.formal_runtime_packet ||
      formalRuntimePacket
  )

  const runtimeControlSnapshot = safe_object(
    src.runtime_control_snapshot ||
      src.current_runtime_control_snapshot ||
      src.control_snapshot
  )

  const currentRuntimeControlSnapshot = safe_object(
    src.current_runtime_control_snapshot ||
      src.runtime_control_snapshot ||
      runtimeControlSnapshot
  )

  return {
    ...runtimeControlSnapshot,
    ...currentRuntimeControlSnapshot,
    ...formalRuntimePacket,
    ...currentFormalRuntimePacket,
    formal_runtime_packet: formalRuntimePacket,
    current_formal_runtime_packet: currentFormalRuntimePacket,
    runtime_control_snapshot: runtimeControlSnapshot,
    current_runtime_control_snapshot: currentRuntimeControlSnapshot,
    formal_runtime_status: safe_string(
      src.formal_runtime_status ||
        currentFormalRuntimePacket.status ||
        currentFormalRuntimePacket.type ||
        currentRuntimeControlSnapshot.status ||
        currentRuntimeControlSnapshot.type
    ).trim(),
    latest_formal_runtime_packet_at: safe_string(
      src.latest_formal_runtime_packet_at ||
        currentFormalRuntimePacket.updated_at ||
        currentFormalRuntimePacket.ts ||
        currentRuntimeControlSnapshot.updated_at ||
        currentRuntimeControlSnapshot.ts
    ).trim(),
  }
}

function has_formal_runtime_fields(source = {}) {
  const payload = build_formal_runtime_payload(source)
  return (
    Object.keys(safe_object(payload.formal_runtime_packet)).length > 0 ||
    Object.keys(safe_object(payload.current_formal_runtime_packet)).length > 0 ||
    Object.keys(safe_object(payload.runtime_control_snapshot)).length > 0 ||
    Object.keys(safe_object(payload.current_runtime_control_snapshot)).length > 0 ||
    !!safe_string(payload.formal_runtime_status).trim() ||
    !!safe_string(payload.latest_formal_runtime_packet_at).trim()
  )
}

function is_success_like_runtime_value(value) {
  const token = normalize_runtime_status_value(value)
  if (!token) return false

  return (
    token.includes('completed') ||
    token.includes('complete') ||
    token.includes('done') ||
    token.includes('finished') ||
    token.includes('success') ||
    token.includes('successful') ||
    token.includes('已完成') ||
    token.includes('完成')
  )
}

function has_top_level_success_formal_runtime(source = {}) {
  const payload = build_formal_runtime_payload(source)

  const formalPacket = safe_object(payload.formal_runtime_packet)
  const currentFormalPacket = safe_object(payload.current_formal_runtime_packet)

  const containers = [
    currentFormalPacket,
    formalPacket,
    safe_object(source),
    safe_object(source.result),
    safe_object(source.payload),
  ]

  for (const row of containers) {
    const type = safe_string(
      row.type ||
        row.event_type ||
        row.packet_type ||
        row.formal_runtime_type
    ).trim()

    const status = safe_string(
      row.status ||
        row.status_text ||
        row.runtime_status ||
        row.formal_runtime_status ||
        row.outcome
    ).trim()

    if (type === 'room.final') return true
    if (is_success_like_runtime_value(status)) return true
  }

  return false
}

export function resolve_effective_legal_runtime_fact({
  result_event = null,
  result_payload = {},
  status_text = '',
} = {}) {
  const event = safe_object(result_event)
  const payload = safe_object(result_payload)
  const explicitStatus = safe_string(status_text).trim()
  const eventType = safe_string(event.type).trim()

  const topLevelSuccess =
    eventType === 'room.final' ||
    has_top_level_success_formal_runtime(payload)

  if (!topLevelSuccess) {
    return extract_legal_runtime_fact(payload, explicitStatus || eventType)
  }

  return extract_legal_runtime_fact(
    {
      formal_runtime_packet: safe_object(payload.formal_runtime_packet),
      current_formal_runtime_packet: safe_object(
        payload.current_formal_runtime_packet ||
          payload.formal_runtime_packet
      ),
      formal_runtime_status: safe_string(payload.formal_runtime_status).trim(),
      latest_formal_runtime_packet_at: safe_string(
        payload.latest_formal_runtime_packet_at
      ).trim(),
    },
    ''
  )
}

export function format_runtime_time(ts) {
  const raw = safe_string(ts).trim()
  if (!raw) return ''

  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw

  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')
  const second = `${date.getSeconds()}`.padStart(2, '0')

  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

export function build_legal_runtime_result_entry(
  fact = null,
  fallback_run_id = '',
  payload = {}
) {
  const src = safe_object(fact)
  const kind = safe_string(src.kind).trim()
  if (!kind) return null

  const data = safe_object(payload)
  const badge =
    kind === 'manual'
      ? 'MANUAL'
      : kind === 'skipped'
        ? 'SKIPPED'
        : kind === 'denied'
          ? 'DENIED'
          : 'NO-AUTO-REPLY'

  return {
    key: `legal-${kind}-${fallback_run_id || 'result'}`,
    badge,
    actor: '',
    timeText: format_runtime_time(
      src.at ||
        data.latest_formal_runtime_packet_at ||
        data.ts ||
        ''
    ),
    metaChips: [
      fallback_run_id ? `run: ${fallback_run_id}` : '',
      safe_string(src.reasonCode).trim()
        ? `reason: ${safe_string(src.reasonCode).trim()}`
        : '',
      safe_string(src.path).trim()
        ? `path: ${safe_string(src.path).trim()}`
        : '',
    ].filter(Boolean),
  }
}

export function normalize_runtime_order(value, fallback = 'asc') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'desc') return 'desc'
  return fallback === 'desc' ? 'desc' : 'asc'
}

export function normalize_runtime_view_mode(value, fallback = 'current') {
  const s = safe_string(value).trim().toLowerCase()
  if (s === 'replay') return 'replay'
  return fallback === 'replay' ? 'replay' : 'current'
}

export function filter_runtime_process_items_for_run(
  items = [],
  runId = '',
  viewMode = 'current'
) {
  const normalizedViewMode = normalize_runtime_view_mode(viewMode, 'current')
  const targetRunId = safe_string(runId).trim()
  const rows = sort_runtime_events(items)

  if (normalizedViewMode === 'replay') return rows
  if (!targetRunId) return rows

  return rows.filter((item) => {
    const itemRunId = safe_string(get_runtime_run_id(item)).trim()
    if (!itemRunId) return true
    return itemRunId === targetRunId
  })
}

export function has_terminal_runtime_evidence(
  items = [],
  resultEvent = null,
  statusText = ''
) {
  if (is_terminal_runtime_event_type(safe_string(resultEvent?.type).trim())) return true
  if (is_terminal_runtime_status_text(statusText)) return true
  if (is_legal_runtime_status_text(statusText)) return true

  return safe_array(items).some((item) => {
    return is_terminal_runtime_event_type(safe_string(item?.type).trim())
  })
}

export function get_terminal_runtime_status_label(
  resultEvent = null,
  processItems = [],
  statusText = ''
) {
  const explicitStatus = safe_string(statusText).trim()

  if (is_terminal_runtime_event_type(safe_string(resultEvent?.type).trim())) {
    const type = safe_string(resultEvent?.type).trim()
    if (type === 'room.final') return '已完成'
    if (type === 'room.error') return '运行失败'
    if (type === 'room.abort' || type === 'room.aborted') return '已中止'
    if (type === 'room.runtime_manual') return '人工处理'
    if (type === 'room.runtime_skipped') return '已跳过'
    if (type === 'room.runtime_denied') return '已拒绝'
    if (type === 'room.runtime_no_auto_reply' || type === 'room.runtime_no-auto-reply') return '未自动回复'
  }

  const terminalItem = safe_array(processItems).find((item) =>
    is_terminal_runtime_event_type(safe_string(item?.type).trim())
  )

  if (terminalItem) {
    const type = safe_string(terminalItem?.type).trim()
    if (type === 'room.final') return '已完成'
    if (type === 'room.error') return '运行失败'
    if (type === 'room.abort' || type === 'room.aborted') return '已中止'
    if (type === 'room.runtime_manual') return '人工处理'
    if (type === 'room.runtime_skipped') return '已跳过'
    if (type === 'room.runtime_denied') return '已拒绝'
    if (type === 'room.runtime_no_auto_reply' || type === 'room.runtime_no-auto-reply') return '未自动回复'
  }

  if (explicitStatus) {
    if (is_legal_runtime_status_text(explicitStatus)) {
      return build_legal_runtime_status_label(
        normalize_legal_runtime_kind(explicitStatus)
      )
    }
    if (is_terminal_runtime_status_text(explicitStatus)) return explicitStatus
  }

  return ''
}

function normalize_runtime_result_event(value) {
  if (!value || typeof value !== 'object') return null
  const normalized = normalize_room_runtime_event(value)
  return Object.keys(normalized).length ? normalized : null
}

export function pick_effective_runtime_result_event({
  view_mode = 'current',
  run_id = '',
  process_items = [],
  result_event = null,
} = {}) {
  const mode = normalize_runtime_view_mode(view_mode, 'current')
  const targetRunId = safe_string(run_id).trim()
  const incoming = normalize_runtime_result_event(result_event)
  const scopedItems = filter_runtime_process_items_for_run(process_items, targetRunId, mode)

  if (mode === 'replay') {
    return incoming || get_runtime_result_event_from_list(scopedItems) || null
  }

  if (incoming) {
    const incomingRunId = safe_string(get_runtime_run_id(incoming)).trim()
    if (!targetRunId || !incomingRunId || incomingRunId === targetRunId) {
      return incoming
    }
  }

  return get_runtime_result_event_from_list(scopedItems) || null
}

export function pick_effective_runtime_result_payload({
  view_mode = 'current',
  run_id = '',
  result_event = null,
  result_payload = {},
} = {}) {
  const mode = normalize_runtime_view_mode(view_mode, 'current')
  const targetRunId = safe_string(run_id).trim()
  const payload = safe_object(result_payload)
  const payloadRunId = safe_string(payload.run_id || payload.runId).trim()
  const effectiveEvent = safe_object(result_event)
  const eventPayload = safe_object(get_runtime_payload(effectiveEvent))
  const eventRunId = safe_string(get_runtime_run_id(effectiveEvent)).trim()

  if (!Object.keys(effectiveEvent).length) {
    if (mode === 'current' && targetRunId && payloadRunId && payloadRunId !== targetRunId) {
      return {}
    }
    return payload
  }

  if (mode === 'replay') {
    return Object.keys(payload).length ? payload : eventPayload
  }

  if (targetRunId) {
    if (eventRunId && eventRunId !== targetRunId) {
      return {}
    }
    if (payloadRunId && payloadRunId !== targetRunId) {
      return eventPayload
    }
  }

  const effectiveEventId = safe_string(effectiveEvent.id).trim()
  const payloadEventId = safe_string(
    payload.event_id ||
      payload.eventId ||
      payload.id
  ).trim()

  if (effectiveEventId && payloadEventId && effectiveEventId !== payloadEventId) {
    return eventPayload
  }

  return Object.keys(payload).length ? payload : eventPayload
}

export function normalize_room_runtime_bundle_payload(payload) {
  const src = safe_object(payload)
  const raw_items = pick_runtime_event_list(src)

  const formal_runtime_packet = safe_object(
    src.formal_runtime_packet ||
      src.current_formal_runtime_packet ||
      src.runtime_packet ||
      src.current_runtime_packet ||
      src.packet
  )

  const current_formal_runtime_packet = safe_object(
    src.current_formal_runtime_packet ||
      src.formal_runtime_packet ||
      formal_runtime_packet
  )

  const runtime_control_snapshot = safe_object(
    src.runtime_control_snapshot ||
      src.current_runtime_control_snapshot ||
      src.control_snapshot
  )

  const current_runtime_control_snapshot = safe_object(
    src.current_runtime_control_snapshot ||
      src.runtime_control_snapshot ||
      runtime_control_snapshot
  )

  return {
    type: 'room_runtime_events',
    items: sort_runtime_events(raw_items),
    limit: normalize_int(src.limit, 0),
    returned_count: normalize_int(src.returned_count, raw_items.length),
    order: normalize_runtime_order(src.order, 'asc'),
    run_id: safe_string(
      src.run_id ||
        src.runId ||
        src.current_run_id ||
        src.currentRunId
    ).trim(),
    latest_event_id: safe_string(
      src.latest_event_id ||
        src.latestEventId ||
        src.tail_event_id ||
        src.tailEventId
    ).trim(),
    include_all_runs: normalize_bool(src.include_all_runs ?? src.includeAllRuns, false),
    after_event_found: normalize_bool(src.after_event_found ?? src.afterEventFound, false),
    message: safe_string(src.message).trim(),
    loaded_at: safe_string(
      src.loaded_at ||
        src.loadedAt ||
        src.updated_at ||
        src.updatedAt
    ).trim(),

    formal_runtime_packet,
    current_formal_runtime_packet,
    runtime_control_snapshot,
    current_runtime_control_snapshot,
    formal_runtime_status: safe_string(
      src.formal_runtime_status ||
        current_formal_runtime_packet.status ||
        current_formal_runtime_packet.type ||
        runtime_control_snapshot.status ||
        runtime_control_snapshot.type
    ).trim(),
    latest_formal_runtime_packet_at: safe_string(
      src.latest_formal_runtime_packet_at ||
        src.formal_runtime_packet_at ||
        current_formal_runtime_packet.updated_at ||
        current_formal_runtime_packet.ts ||
        current_runtime_control_snapshot.updated_at ||
        current_runtime_control_snapshot.ts
    ).trim(),
  }
}

function normalize_runtime_phase_list(list) {
  return safe_array(list)
    .map((item) => safe_object(item))
    .filter((item) => Object.keys(item).length > 0)
}

export function normalize_room_runtime_replay_bundle_payload(payload) {
  const src = safe_object(payload)
  const raw_items = pick_runtime_event_list(src)
  const items = sort_runtime_events(raw_items)

  const result_event =
    normalize_runtime_result_event(
      src.result_event ||
        src.resultEvent ||
        src.final_event ||
        src.finalEvent ||
        src.result ||
        src.event ||
        src.final
    ) ||
    get_runtime_result_event_from_list(items) ||
    null

  const explicit_result_payload = safe_object(
    src.result_payload ||
      src.resultPayload ||
      src.final_payload ||
      src.finalPayload ||
      src.response_payload ||
      src.responsePayload ||
      result_event?.payload
  )

  const final_response = safe_string(src.final_response || src.finalResponse).trim()
  const final_summary = safe_string(src.final_summary || src.finalSummary).trim()

  const payload_response = safe_string(explicit_result_payload.response).trim()
  const payload_content = safe_string(explicit_result_payload.content).trim()
  const payload_message = safe_string(explicit_result_payload.message).trim()
  const payload_status = safe_string(explicit_result_payload.status).trim()

  const summary = safe_string(
    src.summary ||
      src.result_summary ||
      src.resultSummary ||
      final_summary ||
      payload_message ||
      final_response
  ).trim()

  const result_text = safe_string(
    src.result_text ||
      src.resultText ||
      final_response ||
      src.response ||
      src.content ||
      payload_response ||
      payload_content ||
      payload_message ||
      final_summary
  ).trim()

  const result_payload = {
    ...explicit_result_payload,
    response: payload_response || final_response || result_text,
    content: payload_content || final_response || result_text,
    message: payload_message || final_summary || summary,
    status: payload_status || safe_string(src.status).trim(),
    final_response: final_response || safe_string(explicit_result_payload.final_response).trim(),
    final_summary: final_summary || safe_string(explicit_result_payload.final_summary).trim(),
  }

  const run_id = safe_string(
    src.run_id ||
      src.runId ||
      src.requested_run_id ||
      src.requestedRunId
  ).trim()

  const requested_run_id = safe_string(
    src.requested_run_id ||
      src.requestedRunId ||
      run_id
  ).trim()

  const derived_run_id = safe_string(
    src.derived_run_id ||
      src.derivedRunId
  ).trim()

  const latest_event_id = safe_string(
    src.latest_event_id ||
      src.latestEventId ||
      src.tail_event_id ||
      src.tailEventId
  ).trim()

  const tail_event_id = safe_string(
    src.tail_event_id ||
      src.tailEventId ||
      src.latest_event_id ||
      src.latestEventId
  ).trim()

  return {
    type: 'room_runtime_replay',

    run_id,
    requested_run_id,
    derived_run_id,
    requested_run_found: normalize_bool(
      src.requested_run_found ?? src.requestedRunFound,
      !!requested_run_id
    ),

    status: safe_string(src.status).trim(),
    started_at: safe_string(src.started_at || src.startedAt).trim(),
    finished_at: safe_string(src.finished_at || src.finishedAt).trim(),
    current_phase: safe_string(src.current_phase || src.currentPhase).trim(),
    supervisor_phase: safe_string(src.supervisor_phase || src.supervisorPhase).trim(),

    items,
    events: items,
    phases: normalize_runtime_phase_list(src.phases || src.stage_items || src.stageItems),
    relations: safe_array(src.relations),
    tool_activity: safe_array(src.tool_activity || src.toolActivity),
    evidence: safe_array(src.evidence),
    available_runs: safe_array(src.available_runs || src.availableRuns),

    latest_event_id,
    tail_event_id,

    result_event,
    result_payload,
    result_text,
    citations: safe_array(src.citations || src.result_citations || result_payload.citations),

    summary,
    headline: safe_string(src.headline || src.title).trim(),
    badge_summary: safe_string(src.badge_summary || src.badgeSummary).trim(),

    source: safe_string(src.source).trim() || 'replay',
    message: safe_string(src.message).trim(),
    loaded_at: safe_string(
      src.loaded_at ||
        src.loadedAt ||
        src.updated_at ||
        src.updatedAt ||
        src.finished_at ||
        src.finishedAt
    ).trim(),

    final_summary,
    final_response,
    audit: safe_object(src.audit),
    room_state_snapshot: safe_object(src.room_state_snapshot || src.roomStateSnapshot),
    runtime_control_snapshot: safe_object(
      src.runtime_control_snapshot ||
        src.control_snapshot
    ),
  }
}

function default_runtime_fallback() {
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
    replay_bundle: normalize_room_runtime_replay_bundle_payload({}),
  }
}

function resolve_formal_runtime_state_fields(src = {}, fallback = {}) {
  const incomingPayload = build_formal_runtime_payload(src)
  const fallbackPayload = build_formal_runtime_payload(fallback)

  const incomingHasFormal = has_formal_runtime_fields(src)
  const fallbackHasFormal = has_formal_runtime_fields(fallback)

  const incomingTopLevelSuccess = has_top_level_success_formal_runtime(src)
  const fallbackTopLevelSuccess = has_top_level_success_formal_runtime(fallback)

  const incomingFact = incomingTopLevelSuccess
    ? extract_legal_runtime_fact(
        {
          formal_runtime_packet: incomingPayload.formal_runtime_packet,
          current_formal_runtime_packet: incomingPayload.current_formal_runtime_packet,
          formal_runtime_status: safe_string(incomingPayload.formal_runtime_status).trim(),
          latest_formal_runtime_packet_at: safe_string(
            incomingPayload.latest_formal_runtime_packet_at
          ).trim(),
        },
        safe_string(incomingPayload.formal_runtime_status).trim()
      )
    : extract_legal_runtime_fact(
        incomingPayload,
        safe_string(incomingPayload.formal_runtime_status).trim()
      )

  const fallbackFact = fallbackTopLevelSuccess
    ? extract_legal_runtime_fact(
        {
          formal_runtime_packet: fallbackPayload.formal_runtime_packet,
          current_formal_runtime_packet: fallbackPayload.current_formal_runtime_packet,
          formal_runtime_status: safe_string(fallbackPayload.formal_runtime_status).trim(),
          latest_formal_runtime_packet_at: safe_string(
            fallbackPayload.latest_formal_runtime_packet_at
          ).trim(),
        },
        safe_string(fallbackPayload.formal_runtime_status).trim()
      )
    : extract_legal_runtime_fact(
        fallbackPayload,
        safe_string(fallbackPayload.formal_runtime_status).trim()
      )

  if (incomingTopLevelSuccess) return incomingPayload
  if (incomingFact?.kind) return incomingPayload
  if (!incomingHasFormal && fallbackTopLevelSuccess) return fallbackPayload
  if (!incomingHasFormal && fallbackFact?.kind) return fallbackPayload
  if (!incomingHasFormal && fallbackHasFormal) return fallbackPayload

  return incomingPayload
}

export function normalize_runtime_state(
  value,
  fallback = default_runtime_fallback()
) {
  const src = safe_object(value)
  const fb = safe_object(fallback)

  const replay_bundle = normalize_room_runtime_replay_bundle_payload(
    src.replay_bundle === undefined ? fb.replay_bundle : src.replay_bundle
  )

  const selected_run_id = safe_string(
    src.selected_run_id === undefined ? fb.selected_run_id : src.selected_run_id
  ).trim() ||
    safe_string(replay_bundle.requested_run_id || replay_bundle.run_id).trim()

  const tail_event_id = safe_string(
    src.tail_event_id === undefined ? fb.tail_event_id : src.tail_event_id
  ).trim() ||
    safe_string(replay_bundle.tail_event_id || replay_bundle.latest_event_id).trim()

  const resolvedFormal = resolve_formal_runtime_state_fields(src, fb)

  return {
    items:
      src.items !== undefined
        ? sort_runtime_events(src.items)
        : sort_runtime_events(fb.items),
    loading:
      src.loading === undefined
        ? normalize_bool(fb.loading, false)
        : normalize_bool(src.loading, false),
    loaded_once:
      src.loaded_once === undefined
        ? normalize_bool(fb.loaded_once, false)
        : normalize_bool(src.loaded_once, false),
    error:
      src.error === undefined
        ? safe_string(fb.error).trim()
        : safe_string(src.error).trim(),
    expanded:
      src.expanded === undefined
        ? normalize_bool(fb.expanded, true)
        : normalize_bool(src.expanded, true),
    include_all_runs:
      src.include_all_runs === undefined
        ? normalize_bool(fb.include_all_runs, false)
        : normalize_bool(src.include_all_runs, false),
    order: normalize_runtime_order(
      src.order === undefined ? fb.order : src.order,
      safe_string(fb.order).trim() || 'asc'
    ),
    run_id:
      src.run_id === undefined
        ? safe_string(fb.run_id).trim()
        : safe_string(src.run_id).trim(),
    latest_event_id:
      src.latest_event_id === undefined
        ? safe_string(fb.latest_event_id).trim()
        : safe_string(src.latest_event_id).trim(),
    live_hint:
      src.live_hint === undefined && src.live === undefined
        ? normalize_bool(fb.live_hint, false)
        : normalize_bool(src.live_hint ?? src.live, false),
    last_loaded_at:
      src.last_loaded_at === undefined && src.loaded_at === undefined
        ? safe_string(fb.last_loaded_at).trim()
        : safe_string(src.last_loaded_at || src.loaded_at).trim(),
    limit:
      src.limit === undefined
        ? normalize_int(fb.limit, 0)
        : normalize_int(src.limit, 0),
    returned_count:
      src.returned_count === undefined
        ? normalize_int(fb.returned_count, safe_array(fb.items).length)
        : normalize_int(src.returned_count, safe_array(src.items).length),
    after_event_found:
      src.after_event_found === undefined
        ? normalize_bool(fb.after_event_found, false)
        : normalize_bool(src.after_event_found, false),

    formal_runtime_packet: safe_object(resolvedFormal.formal_runtime_packet),
    current_formal_runtime_packet: safe_object(
      resolvedFormal.current_formal_runtime_packet
    ),
    runtime_control_snapshot: safe_object(resolvedFormal.runtime_control_snapshot),
    current_runtime_control_snapshot: safe_object(
      resolvedFormal.current_runtime_control_snapshot
    ),
    formal_runtime_status: safe_string(resolvedFormal.formal_runtime_status).trim(),
    latest_formal_runtime_packet_at: safe_string(
      resolvedFormal.latest_formal_runtime_packet_at
    ).trim(),

    view_mode: normalize_runtime_view_mode(
      src.view_mode === undefined ? fb.view_mode : src.view_mode,
      safe_string(fb.view_mode).trim() || 'current'
    ),
    selected_run_id,
    tail_event_id,

    replay_loading:
      src.replay_loading === undefined
        ? normalize_bool(fb.replay_loading, false)
        : normalize_bool(src.replay_loading, false),
    replay_loaded_once:
      src.replay_loaded_once === undefined
        ? normalize_bool(fb.replay_loaded_once, false)
        : normalize_bool(src.replay_loaded_once, false),
    replay_error:
      src.replay_error === undefined
        ? safe_string(fb.replay_error).trim()
        : safe_string(src.replay_error).trim(),
    replay_bundle,
  }
}

