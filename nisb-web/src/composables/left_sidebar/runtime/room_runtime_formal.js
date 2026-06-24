import {
  safeObject,
  safeString,
  normalizeToken,
  normalizeRuntimePayload,
  translateWithFallback,
  getRuntimeTimeText,
  readCandidateValue,
  readCandidateString,
  readCandidateBoolean,
  collectNestedObjects,
  collectToolResultObjects,
} from './room_runtime_panel_shared'

export function normalizeFormalLegalRuntimeKind(value) {
  const raw = normalizeToken(value)
  if (!raw) return ''

  const token = raw.replace(/\s+/g, '_')

  if (
    token === 'room.runtime_manual' ||
    token === 'runtime_manual' ||
    token === 'manual' ||
    raw.includes('人工处理')
  ) {
    return 'manual'
  }

  if (
    token === 'room.runtime_skipped' ||
    token === 'runtime_skipped' ||
    token === 'skipped' ||
    token === 'skip' ||
    token.includes('runtime_skipped') ||
    raw.includes('已跳过')
  ) {
    return 'skipped'
  }

  if (
    token === 'room.runtime_denied' ||
    token === 'runtime_denied' ||
    token === 'denied' ||
    token === 'deny' ||
    token.includes('runtime_denied') ||
    raw.includes('已拒绝')
  ) {
    return 'denied'
  }

  if (
    token === 'room.runtime_no_auto_reply' ||
    token === 'room.runtime_no-auto-reply' ||
    token === 'runtime_no_auto_reply' ||
    token === 'runtime_no-auto-reply' ||
    token === 'no_auto_reply' ||
    token === 'no-auto-reply' ||
    token.includes('runtime_no_auto_reply') ||
    token.includes('runtime_no-auto-reply') ||
    raw.includes('未自动回复')
  ) {
    return 'no-auto-reply'
  }

  return ''
}

export function buildFormalLegalRuntimeStatusText(t, kind) {
  if (kind === 'manual') {
    return translateWithFallback(t, 'runtime.card.status.manual', '人工处理')
  }
  if (kind === 'skipped') {
    return translateWithFallback(t, 'runtime.card.status.skipped', '已跳过')
  }
  if (kind === 'denied') {
    return translateWithFallback(t, 'runtime.card.status.denied', '已拒绝')
  }
  if (kind === 'no-auto-reply') {
    return translateWithFallback(t, 'runtime.card.status.noAutoReply', '未自动回复')
  }
  return ''
}

export function buildFormalLegalRuntimeBadge(kind) {
  if (kind === 'manual') return 'MANUAL'
  if (kind === 'skipped') return 'SKIPPED'
  if (kind === 'denied') return 'DENIED'
  if (kind === 'no-auto-reply') return 'NO-AUTO-REPLY'
  return 'RUNTIME'
}

export function buildFormalLegalRuntimeHeadline(t, fact) {
  const kind = safeString(fact?.kind).trim()

  if (kind === 'manual') {
    return translateWithFallback(t, 'runtime.card.headline.manual', '当前转人工处理')
  }
  if (kind === 'skipped') {
    return translateWithFallback(t, 'runtime.card.headline.skipped', '自动回复已跳过')
  }
  if (kind === 'denied') {
    return translateWithFallback(t, 'runtime.card.headline.denied', '自动回复已拒绝')
  }
  if (kind === 'no-auto-reply') {
    return translateWithFallback(t, 'runtime.card.headline.noAutoReply', '未触发自动回复')
  }

  return translateWithFallback(t, 'runtime.card.defaultHeadline.current', '当前运行')
}

export function buildFormalLegalRuntimeTypeClass(kind) {
  if (kind === 'denied') return 'error'
  return 'message'
}

function buildFormalLegalRuntimeDefaultSummary(kind) {
  if (kind === 'manual') return '消息已进入时间线，当前按人工处理执行。'
  if (kind === 'skipped') return '消息已进入时间线，但当前未触发自动回复。'
  if (kind === 'denied') return '消息已进入时间线，但当前共享能力未获授权执行。'
  if (kind === 'no-auto-reply') return '消息已进入时间线，当前配置未触发自动回复。'
  return ''
}

export function buildFormalLegalRuntimeSummaryText(t, fact = {}) {
  const kind = safeString(fact.kind).trim()
  const reasonCode = safeString(fact.reasonCode).trim()
  const path = safeString(fact.path).trim()
  const message = safeString(fact.message).trim()

  const parts = []

  if (message) {
    parts.push(message)
  } else {
    const fallback = buildFormalLegalRuntimeDefaultSummary(kind)
    if (fallback) parts.push(fallback)
  }

  if (reasonCode) parts.push(`reason: ${reasonCode}`)
  if (path) parts.push(`path: ${path}`)

  if (
    kind === 'skipped' &&
    fact.sharedRoomConfigEnabled === true &&
    fact.sharedSupervisorEnabled === false
  ) {
    parts.push('房间级 Shared Auto Reply 已开启，但 shared supervisor 未共享。')
  }

  return parts.join(' · ')
}

export function buildFormalLegalRuntimeBadgeParts(t, fact = {}) {
  const parts = []
  const statusText = buildFormalLegalRuntimeStatusText(t, fact.kind)
  const reasonCode = safeString(fact.reasonCode).trim()
  const path = safeString(fact.path).trim()

  if (statusText) parts.push(statusText)
  if (reasonCode) parts.push(`reason: ${reasonCode}`)
  if (path) parts.push(`path: ${path}`)

  return parts
}

export function buildFormalLegalRuntimeActorText(fact = {}) {
  const parts = []
  const reasonCode = safeString(fact.reasonCode).trim()
  const path = safeString(fact.path).trim()

  if (reasonCode) parts.push(reasonCode)
  if (path) parts.push(path)

  return parts.join(' · ')
}

function isFormalSuccessStatus(value) {
  const raw = safeString(value).trim()
  const token = normalizeToken(value)
  if (!raw && !token) return false

  if (
    token === 'room.final' ||
    token === 'final' ||
    token === 'success' ||
    token === 'successful' ||
    token === 'completed' ||
    token === 'complete' ||
    token === 'done' ||
    token === 'finished'
  ) {
    return true
  }

  return (
    raw.includes('已完成') ||
    raw.includes('完成') ||
    raw.includes('success') ||
    raw.includes('completed')
  )
}

function collectTopLevelFormalRows({
  runtimeBase,
  roomState,
  controlSnapshotRaw,
  resultPayload,
  resultEvent,
}) {
  const runtime = safeObject(runtimeBase)
  const state = safeObject(roomState)
  const controlRaw = safeObject(controlSnapshotRaw)
  const payload = normalizeRuntimePayload(resultPayload)
  const event = safeObject(resultEvent)
  const eventPayload = normalizeRuntimePayload(resultEvent?.payload || resultEvent)

  const packetCandidates = [
    runtime.formal_runtime_packet,
    runtime.current_formal_runtime_packet,
    controlRaw.formal_runtime_packet,
    controlRaw.current_formal_runtime_packet,
    state.formal_runtime_packet,
    state.current_formal_runtime_packet,
    payload.formal_runtime_packet,
    payload.current_formal_runtime_packet,
    event.formal_runtime_packet,
    event.current_formal_runtime_packet,
    eventPayload.formal_runtime_packet,
    eventPayload.current_formal_runtime_packet,
  ]
    .map((item) => safeObject(item))
    .filter((item) => Object.keys(item).length > 0)

  const statusRows = [
    runtime.formal_runtime_status ? { formal_runtime_status: runtime.formal_runtime_status } : {},
    controlRaw.formal_runtime_status ? { formal_runtime_status: controlRaw.formal_runtime_status } : {},
    state.formal_runtime_status ? { formal_runtime_status: state.formal_runtime_status } : {},
    payload.formal_runtime_status ? { formal_runtime_status: payload.formal_runtime_status } : {},
    event.formal_runtime_status ? { formal_runtime_status: event.formal_runtime_status } : {},
    eventPayload.formal_runtime_status ? { formal_runtime_status: eventPayload.formal_runtime_status } : {},
  ].filter((row) => Object.keys(row).length > 0)

  return {
    runtime,
    state,
    controlRaw,
    payload,
    event,
    eventPayload,
    packetCandidates,
    statusRows,
    topLevelCandidates: [
      ...packetCandidates,
      ...statusRows,
      event,
      eventPayload,
      payload,
      runtime,
      controlRaw,
      state,
    ].filter((row) => Object.keys(safeObject(row)).length > 0),
  }
}

function hasTopLevelSuccessFormalRuntime({
  runtimeBase,
  roomState,
  controlSnapshotRaw,
  resultPayload,
  resultEvent,
}) {
  const {
    runtime,
    state,
    controlRaw,
    payload,
    event,
    eventPayload,
    topLevelCandidates,
  } = collectTopLevelFormalRows({
    runtimeBase,
    roomState,
    controlSnapshotRaw,
    resultPayload,
    resultEvent,
  })

  if (safeString(event.type).trim() === 'room.final') return true
  if (safeString(eventPayload.type).trim() === 'room.final') return true

  const directStatuses = [
    runtime.formal_runtime_status,
    state.formal_runtime_status,
    controlRaw.formal_runtime_status,
    payload.formal_runtime_status,
    event.formal_runtime_status,
    eventPayload.formal_runtime_status,
    runtime.current_run_status,
    state.current_run_status,
    payload.status,
    payload.runtime_status,
    event.status,
    event.runtime_status,
    eventPayload.status,
    eventPayload.runtime_status,
  ]

  if (directStatuses.some((value) => isFormalSuccessStatus(value))) {
    return true
  }

  return topLevelCandidates.some((row) => {
    const src = safeObject(row)
    return [
      src.type,
      src.event_type,
      src.packet_type,
      src.status,
      src.runtime_status,
      src.formal_runtime_status,
      src.formal_runtime_type,
      src.outcome,
      src.disposition,
      src.status_text,
    ].some((value) => isFormalSuccessStatus(value))
  })
}

export function extractFormalLegalRuntimeFact({
  runtimeBase,
  roomState,
  controlSnapshot,
  controlSnapshotRaw,
  resultPayload,
  resultEvent,
}) {
  const runtime = safeObject(runtimeBase)
  const state = safeObject(roomState)
  const control = safeObject(controlSnapshot)
  const controlRaw = safeObject(controlSnapshotRaw)

  const {
    payload,
    eventPayload,
    packetCandidates,
    statusRows,
    topLevelCandidates,
  } = collectTopLevelFormalRows({
    runtimeBase: runtime,
    roomState: state,
    controlSnapshotRaw: controlRaw,
    resultPayload,
    resultEvent,
  })

  const topLevelSuccess = hasTopLevelSuccessFormalRuntime({
    runtimeBase: runtime,
    roomState: state,
    controlSnapshotRaw: controlRaw,
    resultPayload,
    resultEvent,
  })

  const packetPayloadCandidates = packetCandidates
    .map((packet) => normalizeRuntimePayload(packet.payload || packet.data || packet.result || packet.value))
    .filter((item) => Object.keys(item).length > 0)

  const nestedCandidates = topLevelSuccess
    ? []
    : [
        ...collectNestedObjects(runtime),
        ...collectNestedObjects(state),
        ...collectNestedObjects(controlRaw),
        ...collectNestedObjects(payload),
        ...collectNestedObjects(eventPayload),
      ]

  const toolResultCandidates = topLevelSuccess
    ? []
    : [
        ...collectToolResultObjects(payload),
        ...collectToolResultObjects(eventPayload),
        ...packetCandidates.flatMap((packet) => collectToolResultObjects(packet)),
        ...packetPayloadCandidates.flatMap((packet) => collectToolResultObjects(packet)),
      ]

  const legalSearchCandidates = topLevelSuccess
    ? [
        ...packetCandidates,
        ...packetPayloadCandidates,
        ...statusRows,
        payload,
        eventPayload,
        safeObject(resultEvent),
      ]
    : [
        ...packetCandidates,
        ...packetPayloadCandidates,
        ...statusRows,
        ...nestedCandidates,
        ...toolResultCandidates,
        runtime,
        control,
        controlRaw,
        state,
        payload,
        eventPayload,
        safeObject(resultEvent),
      ].filter((row) => Object.keys(safeObject(row)).length > 0)

  const kindCandidates = legalSearchCandidates.flatMap((row) => {
    const src = safeObject(row)
    return [
      src.type,
      src.event_type,
      src.packet_type,
      src.status,
      src.formal_runtime_status,
      src.formal_runtime_type,
      src.runtime_status,
      src.disposition,
      src.outcome,
      src.status_text,
      src.kind,
    ]
  })

  const kind = kindCandidates.map(normalizeFormalLegalRuntimeKind).find(Boolean)
  if (!kind) return null

  if (topLevelSuccess) {
    const topLevelLegalKinds = topLevelCandidates
      .flatMap((row) => {
        const src = safeObject(row)
        return [
          src.type,
          src.event_type,
          src.packet_type,
          src.status,
          src.formal_runtime_status,
          src.formal_runtime_type,
          src.runtime_status,
          src.disposition,
          src.outcome,
          src.status_text,
          src.kind,
        ]
      })
      .map(normalizeFormalLegalRuntimeKind)
      .filter(Boolean)

    if (!topLevelLegalKinds.length) {
      return null
    }
  }

  const candidates = legalSearchCandidates

  const reasonCode = readCandidateString(candidates, [
    'reason_code',
    'skip_reason_code',
    'deny_reason_code',
    'code',
  ])

  const path = readCandidateString(candidates, ['path', 'runtime_path', 'delivery_path'])

  const message = readCandidateString(candidates, [
    'message',
    'summary',
    'response',
    'content',
    'detail',
    'status_text',
  ])

  const sharedRoomConfigEnabled = readCandidateBoolean(candidates, [
    'shared_room_config_enabled_snapshot',
    'shared_room_config_enabled',
  ])

  const sharedSupervisorEnabled = readCandidateBoolean(candidates, [
    'shared_supervisor_enabled_snapshot',
    'shared_supervisor_enabled',
  ])

  const ts = safeString(
    runtime.latest_formal_runtime_packet_at ||
      controlRaw.latest_formal_runtime_packet_at ||
      state.latest_formal_runtime_packet_at ||
      readCandidateValue(candidates, [
        'latest_formal_runtime_packet_at',
        'updated_at',
        'recorded_at',
        'created_at',
        'ts',
      ])
  ).trim()

  return {
    kind,
    reasonCode,
    path,
    message,
    ts,
    sharedRoomConfigEnabled: sharedRoomConfigEnabled === true,
    sharedSupervisorEnabled: sharedSupervisorEnabled === true,
    rawPacket: packetCandidates[0] || {},
  }
}

export function buildFormalLegalRuntimeResultEntry(t, fact = {}, fallbackEntry = null) {
  const fallback = safeObject(fallbackEntry)
  const kind = safeString(fact.kind).trim()
  if (!kind) return fallback

  const title =
    buildFormalLegalRuntimeHeadline(t, fact) ||
    safeString(fallback.title).trim() ||
    translateWithFallback(t, 'runtime.card.defaultHeadline.current', '当前运行')

  return {
    ...fallback,
    id: safeString(fallback.id).trim() || `formal-${kind}-${fact.ts || fact.reasonCode || fact.path || 'result'}`,
    key: safeString(fallback.key).trim() || `formal-${kind}-${fact.ts || fact.reasonCode || fact.path || 'result'}`,
    type: kind === 'no-auto-reply' ? 'room.no_auto_reply' : `room.${kind}`,
    typeClass: buildFormalLegalRuntimeTypeClass(kind),
    badge: buildFormalLegalRuntimeBadge(kind),
    title,
    summary: buildFormalLegalRuntimeSummaryText(t, fact),
    actor: '',
    timeText: getRuntimeTimeText({ ts: fact.ts }),
    metaChips: [
      fact.reasonCode ? `reason: ${fact.reasonCode}` : '',
      fact.path ? `path: ${fact.path}` : '',
    ].filter(Boolean),
  }
}

export function buildFormalLegalRuntimeRecentEntries(t, fact = {}) {
  const kind = safeString(fact.kind).trim()
  if (!kind) return []

  return [
    {
      id: `formal-entry-${kind}-${fact.ts || fact.reasonCode || fact.path || 'entry'}`,
      key: `formal-entry-${kind}-${fact.ts || fact.reasonCode || fact.path || 'entry'}`,
      type: kind === 'no-auto-reply' ? 'room.no_auto_reply' : `room.${kind}`,
      typeClass: buildFormalLegalRuntimeTypeClass(kind),
      badge: buildFormalLegalRuntimeBadge(kind),
      title: buildFormalLegalRuntimeHeadline(t, fact),
      actor: buildFormalLegalRuntimeActorText(fact),
      timeText: getRuntimeTimeText({ ts: fact.ts }),
      summary: buildFormalLegalRuntimeSummaryText(t, fact),
    },
  ]
}

