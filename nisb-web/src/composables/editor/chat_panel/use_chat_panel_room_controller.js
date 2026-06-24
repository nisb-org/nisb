import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomStore } from '../../../stores/room'
import { use_chat_panel_room_runtime_reader } from './use_chat_panel_room_runtime_reader'
import {
  normalize_tool_results,
  unwrap_tool_result,
  normalize_status_token,
} from '../../../stores/room/room_protocol'
import {
  normalize_room_runtime_display_bundle,
} from '../../../stores/room/room_normalizers'

const DEFAULT_ASSISTANT_GREETING_ZH = '你好！我是 NISB 助手。'
const DEFAULT_ASSISTANT_GREETING_EN = 'Hello! I am the NISB assistant.'

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function safeString(v) {
  return v === null || v === undefined ? '' : String(v)
}

function resolveDefaultAssistantGreeting(localeValue = '') {
  const token = safeString(localeValue).trim().toLowerCase()
  return token.startsWith('en') ? DEFAULT_ASSISTANT_GREETING_EN : DEFAULT_ASSISTANT_GREETING_ZH
}

function normalizeDisplayText(value) {
  const text = safeString(value)
  if (!text) return ''

  return text
    .replace(/\\r\\n/g, '\n')
    .replace(/\\\\r\\\\n/g, '\n')
    .replace(/\\\\n/g, '\n')
    .replace(/\\\\r/g, '\n')
}

function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function isPlainObject(v) {
  return !!v && typeof v === 'object' && !Array.isArray(v)
}

function safeBoolean(value, fallback = false) {
  if (typeof value === 'boolean') return value
  const token = safeString(value).trim().toLowerCase()
  if (!token) return fallback
  if (['1', 'true', 'yes', 'on'].includes(token)) return true
  if (['0', 'false', 'no', 'off'].includes(token)) return false
  return fallback
}

function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key)
}

function hasUsableValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return !!value.trim()
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

function readControlValue(candidates, keys = []) {
  for (const candidate of safeArray(candidates)) {
    const row = safeObject(candidate)
    for (const key of keys) {
      if (!key || !hasOwn(row, key)) continue
      const value = row[key]
      if (hasUsableValue(value)) return value
      if (typeof value === 'boolean' || typeof value === 'number') return value
    }
  }
  return undefined
}

function normalizeRuntimeStatusToken(value) {
  return safeString(value)
    .trim()
    .toLowerCase()
    .replace(/[\\s-]+/g, '_')
}

function normalizeRuntimeState(value) {
  const token = normalizeRuntimeStatusToken(value)

  if (!token) return ''
  if (token === 'completed_after_resume') return 'completed_after_resume'
  if (token === 'completed after resume') return 'completed_after_resume'
  if (token === 'budget_exhausted') return 'budget_exhausted'
  if (token === 'budget exhausted') return 'budget_exhausted'
  if (token === 'step_budget_exhausted' || token === 'exhausted') return 'budget_exhausted'
  if (token === 'pause_requested') return 'pause_requested'
  if (token === 'pause requested') return 'pause_requested'
  if (token === 'waiting_checkpoint') return 'waiting_checkpoint'
  if (token === 'waiting checkpoint') return 'waiting_checkpoint'
  return token
}

function normalizeContinuationStatusToken(value) {
  const token = normalizeRuntimeState(value)

  if (
    [
      'running',
      'pause_requested',
      'interrupted',
      'resumed',
      'completed',
      'completed_after_resume',
      'budget_exhausted',
    ].includes(token)
  ) {
    return token
  }

  return ''
}

function normalizeRuntimeControlSnapshot(raw) {
  const src = safeObject(raw)
  const candidates = [
    src,
    safeObject(src.runtime_control_snapshot),
    safeObject(src.control_snapshot),
  ].filter((row) => Object.keys(row).length > 0)

  return {
    runtimeState: normalizeRuntimeState(
      readControlValue(candidates, ['runtime_state', 'runtimeState', 'state'])
    ),
    runtimePhase: normalizeRuntimeState(
      readControlValue(candidates, ['runtime_phase', 'runtimePhase', 'phase'])
    ),
    canAcceptNewPrompt: safeBoolean(
      readControlValue(candidates, ['can_accept_new_prompt', 'canAcceptNewPrompt']),
      false
    ),
    controlBlockReason: safeString(
      readControlValue(candidates, ['control_block_reason', 'controlBlockReason'])
    ).trim(),
    canPauseCurrent: safeBoolean(
      readControlValue(candidates, ['can_pause_current', 'canPauseCurrent']),
      false
    ),
    canResume: safeBoolean(
      readControlValue(candidates, ['can_resume', 'canResume']),
      false
    ),
    pauseRequested: safeBoolean(
      readControlValue(candidates, ['pause_requested', 'pauseRequested']),
      false
    ),
    pauseRequestAccepted: safeBoolean(
      readControlValue(candidates, ['pause_request_accepted', 'pauseRequestAccepted']),
      false
    ),
    pauseEffective: safeBoolean(
      readControlValue(candidates, ['pause_effective', 'pauseEffective']),
      false
    ),
    resumeReady: safeBoolean(
      readControlValue(candidates, ['resume_ready', 'resumeReady']),
      false
    ),
    budgetExhausted: safeBoolean(
      readControlValue(candidates, ['budget_exhausted', 'budgetExhausted']),
      false
    ),
  }
}

function isMeaningfulRuntimeControl(snapshot) {
  const ctl = normalizeRuntimeControlSnapshot(snapshot)
  return !!(
    ctl.runtimeState ||
    ctl.runtimePhase ||
    ctl.controlBlockReason ||
    ctl.canPauseCurrent ||
    ctl.canResume ||
    ctl.pauseRequested ||
    ctl.pauseRequestAccepted ||
    ctl.pauseEffective ||
    ctl.resumeReady ||
    ctl.budgetExhausted ||
    ctl.canAcceptNewPrompt === false
  )
}

function shouldNudgeForRuntimeStatus(nextStatus, prevStatus) {
  const nextToken = normalizeRuntimeStatusToken(nextStatus)
  const prevToken = normalizeRuntimeStatusToken(prevStatus)

  if (!nextToken || nextToken === prevToken) return false

  return [
    'running',
    'pause_requested',
    'interrupted',
    'resumed',
    'completed',
    'completed_after_resume',
    'budget_exhausted',
  ].includes(nextToken)
}

function shouldNudgeForRuntimeControl(nextControl, prevControl) {
  const next = normalizeRuntimeControlSnapshot(nextControl)
  const prev = normalizeRuntimeControlSnapshot(prevControl)

  const comparableKeys = [
    'runtimeState',
    'runtimePhase',
    'canAcceptNewPrompt',
    'controlBlockReason',
    'canPauseCurrent',
    'canResume',
    'pauseRequested',
    'pauseRequestAccepted',
    'pauseEffective',
    'resumeReady',
    'budgetExhausted',
  ]

  return comparableKeys.some((key) => next[key] !== prev[key])
}

function isTerminalRuntimeEventType(value) {
  return [
    'room.final',
    'room.abort',
    'room.aborted',
    'room.error',
  ].includes(safeString(value).trim())
}

function isContinuationTerminalRuntimeStatus(value) {
  const token = normalizeContinuationStatusToken(value)
  return [
    'interrupted',
    'completed',
    'completed_after_resume',
    'budget_exhausted',
  ].includes(token)
}

function isContinuationActiveRuntimeStatus(value) {
  const token = normalizeContinuationStatusToken(value)
  return [
    'running',
    'pause_requested',
    'resumed',
  ].includes(token)
}

function isTerminalRuntimeStatus(value) {
  const token = normalizeRuntimeStatusToken(value)
  if (!token) return false

  if (isContinuationTerminalRuntimeStatus(token)) return true

  return [
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
  ].some((item) => token.includes(item))
}

function isActiveRuntimeStatus(value) {
  const token = normalizeRuntimeStatusToken(value)
  if (!token) return false

  if (isContinuationActiveRuntimeStatus(token)) return true

  return [
    'live',
    'processing',
    'planning',
    'delegating',
    'synthesizing',
    'working',
    'in_progress',
    'queued',
    'pending',
    'waiting_checkpoint',
    '处理中',
    '运行中',
    '规划中',
    '委派中',
    '汇总中',
  ].some((item) => token.includes(item))
}

function extractRuntimeRunId(item) {
  const src = safeObject(item)
  const payload = safeObject(src.payload)
  return safeString(src.run_id || payload.run_id || payload.runId).trim()
}

function readRuntimeEntryStatus(item) {
  const src = safeObject(item)
  const payload = safeObject(src.payload)

  return safeString(
    src.status ||
    payload.status ||
    payload.state ||
    payload.phase
  ).trim()
}

function isTerminalRuntimeEntry(item) {
  if (!item || typeof item !== 'object') return false
  if (isTerminalRuntimeEventType(item?.type)) return true
  return isTerminalRuntimeStatus(readRuntimeEntryStatus(item))
}

function filterProcessItemsByRunId(items, runId = '') {
  const targetRunId = safeString(runId).trim()
  const rows = safeArray(items)

  if (!targetRunId) return rows

  return rows.filter((item) => {
    const itemRunId = extractRuntimeRunId(item)
    if (!itemRunId) return false
    return itemRunId === targetRunId
  })
}

function deriveLatestRuntimeRunId(items) {
  const rows = safeArray(items)
  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const runId = extractRuntimeRunId(rows[idx])
    if (runId) return runId
  }
  return ''
}

function pickResultEventForRun(items, runId = '') {
  const rows = filterProcessItemsByRunId(items, runId)

  const finals = rows.filter((item) => safeString(item?.type).trim() === 'room.final')
  if (finals.length) return finals[finals.length - 1]

  const terminals = rows.filter((item) =>
    ['room.error', 'room.abort', 'room.aborted'].includes(safeString(item?.type).trim())
  )
  if (terminals.length) return terminals[terminals.length - 1]

  const fallback = rows.filter((item) =>
    ['room.message', 'room.supervisor'].includes(safeString(item?.type).trim())
  )

  return fallback.length ? fallback[fallback.length - 1] : null
}

function pickLatestTerminalRuntimeEvent(items) {
  const rows = safeArray(items)
  for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
    const item = rows[idx]
    if (isTerminalRuntimeEntry(item)) {
      return item
    }
  }
  return null
}

function extractWhoAmI(data) {
  const rows = normalize_tool_results(data)

  for (const row of rows) {
    const payloads = [
      safeObject(row),
      safeObject(row.data),
      safeObject(row.result),
      safeObject(row.payload),
      safeObject(row.value),
    ]

    for (const payload of payloads) {
      const uid = safeString(payload.uid || payload.user_id).trim()
      const basepath = safeString(payload.basepath || payload.base_path).trim()
      if (uid || basepath) {
        return { uid, basepath }
      }
    }
  }

  const top = unwrap_tool_result(data)
  return {
    uid: safeString(top.uid || top.user_id).trim(),
    basepath: safeString(top.basepath || top.base_path).trim(),
  }
}

function normalizeFormalBody(obj, fallback = '') {
  const src = safeObject(obj)
  const candidates = [src.response, src.content, src.message, src.text]

  for (const item of candidates) {
    const s = normalizeDisplayText(item)
    if (s) return s
  }

  return normalizeDisplayText(fallback)
}

function normalizeFormalMessage(obj, fallback = '') {
  const src = safeObject(obj)
  const candidates = [src.message, src.response, src.content, src.text]

  for (const item of candidates) {
    const s = normalizeDisplayText(item)
    if (s) return s
  }

  return normalizeDisplayText(fallback)
}

function buildMessageLocalId(prefix = 'room_msg', seed = '') {
  const p = safeString(prefix).trim() || 'room_msg'
  const s = safeString(seed).trim()
  if (s) return `${p}_${s}`
  return `${p}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function normalizeMessageBodyText(value) {
  const src = safeObject(value)
  return normalizeDisplayText(src.response || src.content || src.message || src.text).trim()
}

function normalizeRenderedMessageKey(value) {
  const src = safeObject(value)

  const id = safeString(src.id).trim()
  if (id) return `id:${id}`

  const requestId = safeString(src.request_id).trim()
  const role = safeString(src.role).trim()
  const sender = safeString(src.sender).trim()
  const senderType = safeString(src.sender_type).trim() || (role === 'user' ? 'user' : '')
  const roomEventType = safeString(src.room_event_type).trim()
  const runId = safeString(src.run_id).trim()
  const body = normalizeMessageBodyText(src)

  if (requestId && (senderType === 'user' || role === 'user')) {
    return `user_request:${requestId}`
  }

  if (requestId && roomEventType) {
    return `request_event:${requestId}|${roomEventType}`
  }

  const localId = safeString(src.local_id).trim()
  if (localId) return `local:${localId}`

  return `fallback:${roomEventType}|${sender}|${senderType}|${runId}|${body}`
}

function mergeRenderedMessages(existing, incoming) {
  const merged = new Map()

  for (const item of safeArray(existing)) {
    const key = normalizeRenderedMessageKey(item)
    merged.set(key, safeObject(item))
  }

  for (const item of safeArray(incoming)) {
    const key = normalizeRenderedMessageKey(item)
    merged.set(key, {
      ...safeObject(merged.get(key)),
      ...safeObject(item),
      pending: false,
    })
  }

  return Array.from(merged.values()).sort((a, b) => {
    const ak = `${safeString(a?.ts)}|${safeString(a?.id || a?.local_id)}`
    const bk = `${safeString(b?.ts)}|${safeString(b?.id || b?.local_id)}`
    if (ak < bk) return -1
    if (ak > bk) return 1
    return 0
  })
}

function normalizePagingState(value) {
  const src = safeObject(value)
  return {
    hasmore: !!(src.hasmore ?? src.has_more),
    nextcursor: safeObject(src.nextcursor ?? src.next_cursor),
    loadedonce: !!(src.loadedonce ?? src.loaded_once),
    loadingolder: !!(src.loadingolder ?? src.loading_older),
  }
}

function isRuntimeProcessEvent(item) {
  const type = safeString(item?.type).trim()
  return [
    'room.plan',
    'room.delegate',
    'room.supervisor',
    'room.route',
    'room.message',
    'room.final',
    'room.abort',
    'room.aborted',
    'room.error',
  ].includes(type)
}

export function use_chat_panel_room_controller({
  call_tool,
  chat_cfg,
  props,
  messages,
  internal_conv_id,
  load_conversation,
  scroll_to_bottom,
  is_thinking,
}) {
  const { locale } = useI18n({ useScope: 'global' })
  const room_store = useRoomStore()
  const defaultAssistantGreeting = computed(() =>
    resolveDefaultAssistantGreeting(locale.value)
  )

  function resolveRoleLabelText(key) {
    const loc = safeString(locale.value || 'en').toLowerCase()
    const isZh = loc.startsWith('zh')

    if (key === 'you') return isZh ? '你' : 'You'
    if (key === 'user') return isZh ? '用户' : 'User'
    if (key === 'system') return isZh ? '系统' : 'System'
    if (key === 'role') return isZh ? '角色' : 'Role'
    if (key === 'supervisor') return 'Supervisor'
    if (key === 'ai') return 'AI'
    return ''
  }

  const myUid = ref(
    safeString(globalThis?.localStorage?.getItem?.('nisb_user_id')).trim()
  )
  const isRoomMode = computed(() => (chat_cfg.chat && chat_cfg.chat.mode) === 'room')
  const activeRoomId = computed(() => safeString(chat_cfg.chat?.roomId).trim())

  const hasMoreOlder = computed(() => {
    return !!(room_store.hasMoreOlder ?? normalizePagingState(room_store.itemsPagingState).hasmore)
  })

  const loadingOlder = computed(() => {
    return !!(room_store.loadingOlder ?? normalizePagingState(room_store.itemsPagingState).loadingolder)
  })

  const roomItemsPaging = computed(() => {
    const normalized = normalizePagingState(room_store.itemsPagingState)
    return {
      ...safeObject(room_store.itemsPagingState),
      hasmore: normalized.hasmore,
      nextcursor: normalized.nextcursor,
      loadedonce: normalized.loadedonce,
      loadingolder: normalized.loadingolder,
    }
  })

  const roomRuntimeViewMode = computed(() => {
    return safeString(room_store.runtimeViewMode).trim() === 'replay' ? 'replay' : 'current'
  })

  const roomRuntimeSelectedReplayRunId = computed(() => {
    return safeString(room_store.runtimeSelectedReplayRunId).trim()
  })

  const roomRuntimeRunOptions = computed(() => {
    return safeArray(room_store.runtimeRunOptions)
  })

  const roomRuntimeExpanded = computed(() => {
    return !!safeObject(room_store.runtimeState).expanded
  })

  const roomRuntimeLoading = computed(() => {
    const runtimeState = safeObject(room_store.runtimeState)
    if (roomRuntimeViewMode.value === 'replay') {
      return !!runtimeState.replay_loading
    }
    return !!runtimeState.loading
  })

  const roomRuntimeError = computed(() => {
    const runtimeState = safeObject(room_store.runtimeState)
    if (roomRuntimeViewMode.value === 'replay') {
      return safeString(runtimeState.replay_error)
    }
    return safeString(runtimeState.error)
  })

  const roomRuntimeControlSnapshot = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return normalizeRuntimeControlSnapshot(
        room_store.runtimeReplayBundle?.runtime_control_snapshot ||
          room_store.runtimeReplayBundle?.control_snapshot ||
          safeObject(safeObject(room_store.runtimeState).replay_bundle).runtime_control_snapshot ||
          safeObject(safeObject(room_store.runtimeState).replay_bundle).control_snapshot ||
          {}
      )
    }

    return normalizeRuntimeControlSnapshot(
      room_store.runtimeControlSnapshot ||
        room_store.runtime?.runtime_control_snapshot ||
        room_store.runtime?.control_snapshot ||
        room_store.roomState?.runtime_control_snapshot ||
        room_store.roomState ||
        {}
    )
  })

  const currentLaneRuntimeItems = computed(() => {
    const explicitItems = room_store.runtimeItems
    if (Array.isArray(explicitItems)) return explicitItems

    return safeArray(room_store.items).filter(isRuntimeProcessEvent)
  })

  const currentLaneRuntimeProcessItems = computed(() => {
    const explicit = room_store.runtimeProcessItems
    if (Array.isArray(explicit)) return explicit

    return safeArray(currentLaneRuntimeItems.value).filter(isRuntimeProcessEvent)
  })

  const currentRuntimeRunId = computed(() => {
    return safeString(
      room_store.runtimeRunId ||
      room_store.currentRunId ||
      deriveLatestRuntimeRunId(currentLaneRuntimeProcessItems.value)
    ).trim()
  })

  const currentRuntimeProcessItems = computed(() => {
    return filterProcessItemsByRunId(
      currentLaneRuntimeProcessItems.value,
      currentRuntimeRunId.value
    )
  })

  const currentRuntimeResultEvent = computed(() => {
    const currentRunId = currentRuntimeRunId.value
    const explicit = room_store.runtimeResultEvent

    if (explicit) {
      const explicitRunId = extractRuntimeRunId(explicit)

      if (isTerminalRuntimeEntry(explicit)) {
        return explicit
      }

      if (!currentRunId || !explicitRunId || explicitRunId === currentRunId) {
        return explicit
      }
    }

    const scoped = pickResultEventForRun(currentRuntimeProcessItems.value, currentRunId)
    if (scoped) {
      return scoped
    }

    const terminalFallback = pickLatestTerminalRuntimeEvent(currentLaneRuntimeProcessItems.value)
    if (terminalFallback) {
      return terminalFallback
    }

    return pickResultEventForRun(currentLaneRuntimeProcessItems.value, '')
  })

  const currentRuntimeResultPayload = computed(() => {
    const explicit = safeObject(room_store.runtimeResultPayload)
    const currentRunId = currentRuntimeRunId.value
    const explicitRunId = safeString(explicit.run_id || explicit.runId).trim()

    if (Object.keys(explicit).length > 0) {
      const explicitStatus = safeString(
        explicit.status || explicit.state || explicit.phase
      ).trim()

      if (isTerminalRuntimeStatus(explicitStatus)) {
        return explicit
      }

      if (!currentRunId || !explicitRunId || explicitRunId === currentRunId) {
        return explicit
      }
    }

    return safeObject(currentRuntimeResultEvent.value?.payload)
  })

  const currentRuntimeResultText = computed(() => {
    const explicit = normalizeDisplayText(room_store.runtimeResultText).trim()
    if (explicit) return explicit

    const payload = currentRuntimeResultPayload.value
    return normalizeDisplayText(
      payload.response ||
      payload.content ||
      payload.message
    ).trim()
  })

  const replayRuntimeBundle = computed(() => {
    return safeObject(safeObject(room_store.runtimeState).replay_bundle)
  })

  const replayRuntimeProcessItems = computed(() => {
    return safeArray(replayRuntimeBundle.value.items)
  })

  const replayRuntimeResultEvent = computed(() => {
    const explicit = safeObject(replayRuntimeBundle.value.result_event)
    return Object.keys(explicit).length ? explicit : null
  })

  const replayRuntimeResultPayload = computed(() => {
    return safeObject(replayRuntimeBundle.value.result_payload)
  })

  const replayRuntimeResultText = computed(() => {
    return normalizeDisplayText(replayRuntimeBundle.value.result_text).trim()
  })

  const replayRuntimeRunId = computed(() => {
    return safeString(
      replayRuntimeBundle.value.run_id ||
      roomRuntimeSelectedReplayRunId.value
    ).trim()
  })

  const roomRuntimeProcessItems = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return replayRuntimeProcessItems.value
    return currentRuntimeProcessItems.value
  })

  const roomRuntimeResultEvent = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return replayRuntimeResultEvent.value
    return currentRuntimeResultEvent.value
  })

  const roomRuntimeResultPayload = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return replayRuntimeResultPayload.value
    return currentRuntimeResultPayload.value
  })

  const roomRuntimeResultText = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return replayRuntimeResultText.value
    return currentRuntimeResultText.value
  })

  const roomRuntimeRunId = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return replayRuntimeRunId.value
    return currentRuntimeRunId.value
  })

  const roomRuntimeVisible = computed(() => {
    const state = safeObject(room_store.runtimeState)
    if (state.visible !== undefined) return !!state.visible
    if (typeof room_store.runtimeVisible === 'boolean') return room_store.runtimeVisible
    return !!isRoomMode.value
  })

  const roomRuntimeLive = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return false

    const control = roomRuntimeControlSnapshot.value
    const runtimeState = normalizeRuntimeState(control.runtimeState)
    const runtimePhase = normalizeRuntimeState(control.runtimePhase)

    if (
      ['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(runtimeState) ||
      runtimePhase === 'waiting_checkpoint'
    ) {
      return true
    }

    if (['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(runtimeState)) {
      return false
    }

    const continuationStatus = normalizeContinuationStatusToken(
      room_store.roomState?.continuation_status
    )
    if (isContinuationActiveRuntimeStatus(continuationStatus)) return true
    if (isContinuationTerminalRuntimeStatus(continuationStatus)) return false

    const explicit = room_store.runtimeLive
    const currentStatus = safeString(room_store.currentRunStatus || room_store.roomState?.current_run_status).trim()
    const normalizedCurrentStatus = normalizeRuntimeStatusToken(currentStatus)

    const resultEntry = currentRuntimeResultEvent.value
    const resultType = safeString(resultEntry?.type).trim()
    const resultStatus = safeString(
      resultEntry?.status ||
      resultEntry?.payload?.status ||
      currentRuntimeResultPayload.value?.status
    ).trim()

    if (isTerminalRuntimeEventType(resultType)) return false
    if (isTerminalRuntimeStatus(resultStatus)) return false
    if (isTerminalRuntimeStatus(currentStatus)) return false

    if (normalizedCurrentStatus === 'pause_requested') return true
    if (isActiveRuntimeStatus(currentStatus)) return true

    if (explicit === true) return true
    if (explicit === false) return false

    const runId = currentRuntimeRunId.value
    if (!runId) return false

    const currentRows = currentRuntimeProcessItems.value
    if (!currentRows.length) return false

    const hasTerminalRow = currentRows.some((item) => isTerminalRuntimeEntry(item))
    if (hasTerminalRow) return false

    return currentRows.some((item) => {
      const type = safeString(item?.type).trim()
      const status = readRuntimeEntryStatus(item)
      if (isTerminalRuntimeEventType(type)) return false
      if (isTerminalRuntimeStatus(status)) return false
      return !!type
    })
  })

  const roomRuntimeDisplayBundle = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return normalize_room_runtime_display_bundle({
        view_mode: 'replay',
        run_id: replayRuntimeRunId.value,
        process_items: replayRuntimeProcessItems.value,
        result_event: replayRuntimeResultEvent.value,
        result_payload: replayRuntimeResultPayload.value,
        result_text: replayRuntimeResultText.value,
        run_options: roomRuntimeRunOptions.value,
        selected_run_id: roomRuntimeSelectedReplayRunId.value,
        error: roomRuntimeError.value,
        loading: roomRuntimeLoading.value,
        live: false,
        replay_items: replayRuntimeProcessItems.value,
        replay_result_text: replayRuntimeResultText.value,
      })
    }

    return normalize_room_runtime_display_bundle({
      view_mode: 'current',
      run_id: currentRuntimeRunId.value,
      status_text: safeString(room_store.runtimeStatusText).trim(),
      process_items: currentRuntimeProcessItems.value,
      result_event: currentRuntimeResultEvent.value,
      result_payload: currentRuntimeResultPayload.value,
      result_text: currentRuntimeResultText.value,
      run_options: roomRuntimeRunOptions.value,
      selected_run_id: '',
      error: roomRuntimeError.value,
      loading: roomRuntimeLoading.value,
      live: roomRuntimeLive.value,
      replay_items: [],
      replay_result_text: '',
    })
  })

  const roomRuntimeStatusText = computed(() => {
    return safeString(roomRuntimeDisplayBundle.value.status_text).trim()
  })

  const roomRuntimeDisplayResultEntry = computed(() => {
    return safeObject(roomRuntimeDisplayBundle.value.result_entry)
  })

  const roomRuntimeTimelineEntries = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.timeline_entries)
  })

  const roomRuntimeAuditCards = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.audit_cards)
  })

  const roomRuntimeToolCallRows = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.tool_call_rows)
  })

  const roomRuntimeToolResultRows = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.tool_result_rows)
  })

  const roomRuntimeHeadline = computed(() => {
    return safeString(roomRuntimeDisplayBundle.value.headline).trim()
  })

  const roomRuntimeBadgeSummary = computed(() => {
    return safeString(roomRuntimeDisplayBundle.value.badge_summary).trim()
  })

  const roomRuntimeSkillSummary = computed(() => {
    return safeObject(roomRuntimeDisplayBundle.value.skill_summary)
  })

  const roomRuntimeSkillCards = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.skill_cards)
  })

  const roomRuntimeSkillActivityRows = computed(() => {
    return safeArray(roomRuntimeDisplayBundle.value.skill_activity_rows)
  })

  const roomRuntimeState = computed(() => roomRuntimeControlSnapshot.value.runtimeState)
  const roomRuntimePhase = computed(() => roomRuntimeControlSnapshot.value.runtimePhase)
  const roomRuntimeCanAcceptNewPrompt = computed(() => roomRuntimeControlSnapshot.value.canAcceptNewPrompt)
  const roomRuntimeControlBlockReason = computed(() => roomRuntimeControlSnapshot.value.controlBlockReason)
  const roomRuntimeCanPauseCurrent = computed(() => roomRuntimeControlSnapshot.value.canPauseCurrent)
  const roomRuntimeCanResume = computed(() => roomRuntimeControlSnapshot.value.canResume)
  const roomRuntimePauseRequested = computed(() => roomRuntimeControlSnapshot.value.pauseRequested)
  const roomRuntimePauseRequestAccepted = computed(() => roomRuntimeControlSnapshot.value.pauseRequestAccepted)
  const roomRuntimePauseEffective = computed(() => roomRuntimeControlSnapshot.value.pauseEffective)
  const roomRuntimeResumeReady = computed(() => roomRuntimeControlSnapshot.value.resumeReady)
  const roomRuntimeBudgetExhausted = computed(() => roomRuntimeControlSnapshot.value.budgetExhausted)

  function toggleRoomRuntimeExpanded() {
    if (typeof room_store.setRuntimeExpanded === 'function') {
      room_store.setRuntimeExpanded(!roomRuntimeExpanded.value)
    }
  }

  function buildEmptyRoomPlaceholder() {
    return [{
      local_id: buildMessageLocalId('room_placeholder'),
      role: 'assistant',
      sender: 'system',
      sender_type: 'system',
      content: '',
      response: '',
      status: 'success',
      message: '',
      citations: [],
      rss_evidence: [],
      market_evidence: [],
      evidence_query: '',
      evidence_tools: [],
      evidence_result: {},
      tool_calls: [],
      tool_results: [],
      pending: false,
      meta: null,
    }]
  }

  function mapRoomMessageLike(row) {
    const src = safeObject(row)
    const sender = safeString(src.sender)
    const sender_type = safeString(src.sender_type)
    const role_id = safeString(src.role_id)
    const role_name = safeString(src.role_name)
    const avatar = safeString(src.avatar)
    const request_id = safeString(src.request_id)
    const response = normalizeFormalBody(src, '')
    const isMine = sender_type === 'user' && sender && sender === safeString(myUid.value)
    const raw_tool_calls = safeArray(src.tool_calls)
    const raw_tool_results = safeArray(src.tool_results)

    if (!response && !sender && !sender_type && !raw_tool_calls.length && !raw_tool_results.length) {
      return null
    }

    const nextMeta = {
      ...(isPlainObject(src.meta) ? src.meta : {}),
    }

    if (raw_tool_calls.length || raw_tool_results.length) {
      nextMeta.room_audit = {
        tool_calls: raw_tool_calls,
        tool_results: raw_tool_results,
      }
    }

    return {
      id: safeString(src.id),
      local_id: buildMessageLocalId(
        'room_msg',
        safeString(src.id || request_id || src.ts || src.run_id || response)
      ),
      ts: src.ts || '',
      request_id,
      role: isMine ? 'user' : (safeString(src.role) || (sender_type === 'user' ? 'user' : 'assistant')),
      sender,
      sender_type,
      role_id,
      role_name,
      avatar,
      model: safeString(src.model),
      mode_used: safeString(src.mode_used || 'off'),
      content: response,
      response,
      status: normalize_status_token(src.status || 'success') || 'success',
      message: normalizeFormalMessage(src, ''),
      citations: safeArray(src.citations),
      rss_evidence: safeArray(src.rss_evidence),
      market_evidence: safeArray(src.market_evidence),
      evidence_query: safeString(src.evidence_query),
      evidence_tools: safeArray(src.evidence_tools),
      evidence_result: isPlainObject(src.evidence_result) ? src.evidence_result : {},
      tool_calls: raw_tool_calls,
      tool_results: raw_tool_results,
      pending: false,
      room_event_type: safeString(src.room_event_type || ''),
      run_id: safeString(src.run_id || ''),
      meta: Object.keys(nextMeta).length ? nextMeta : null,
    }
  }

  function mapRoomEventToMessage(e) {
    if (!e || typeof e !== 'object') return null

    const directMessage = mapRoomMessageLike(e)
    if (directMessage && !safeString(e?.type)) {
      return directMessage
    }

    const eventType = safeString(e?.type).trim()
    const p = safeObject(e?.payload)
    const request_id = safeString(e?.request_id || p?.request_id)

    if (eventType === 'room.message') {
      return mapRoomMessageLike({
        id: safeString(e?.id),
        ts: e?.ts || '',
        request_id,
        room_event_type: eventType,
        run_id: safeString(e?.run_id || ''),
        sender: p?.sender,
        sender_type: p?.sender_type,
        role_id: p?.role_id,
        role_name: p?.role_name,
        avatar: p?.avatar,
        model: p?.model,
        mode_used: p?.mode_used || 'off',
        response: p?.response,
        content: p?.content,
        status: p?.status,
        message: p?.message,
        citations: p?.citations,
        rss_evidence: p?.rss_evidence,
        market_evidence: p?.market_evidence,
        evidence_query: p?.evidence_query,
        evidence_tools: p?.evidence_tools,
        evidence_result: p?.evidence_result || null,
        tool_calls: p?.tool_calls,
        tool_results: p?.tool_results,
        meta: {
          packet_type: 'room.message',
          room_event_id: safeString(e?.id),
        },
      })
    }

    if (eventType === 'room.final') {
      return mapRoomMessageLike({
        id: safeString(e?.id),
        ts: e?.ts || '',
        request_id,
        room_event_type: eventType,
        run_id: safeString(e?.run_id || ''),
        role: 'assistant',
        sender: safeString(p?.sender || 'supervisor'),
        sender_type: safeString(p?.sender_type || 'supervisor'),
        role_id: safeString(p?.role_id || ''),
        role_name: safeString(p?.role_name || 'Supervisor'),
        avatar: safeString(p?.avatar || '🧠'),
        model: safeString(p?.model || ''),
        mode_used: safeString(p?.mode_used || 'off'),
        response: p?.response,
        content: p?.content,
        status: p?.status,
        message: p?.message,
        citations: p?.citations,
        rss_evidence: p?.rss_evidence,
        market_evidence: p?.market_evidence,
        evidence_query: p?.evidence_query,
        evidence_tools: p?.evidence_tools,
        evidence_result: p?.evidence_result || null,
        tool_calls: p?.tool_calls,
        tool_results: p?.tool_results,
        meta: {
          plan_summary: safeString(p?.plan_summary || ''),
          packet_type: 'room.final',
          room_event_id: safeString(e?.id),
        },
      })
    }

    return null
  }

  function isActiveFederatedRoom() {
    const rid = safeString(activeRoomId.value).trim()
    if (!rid) return false

    if (typeof room_store?.isFederatedRoom === 'function') {
      return room_store.isFederatedRoom(rid)
    }

    const session = safeObject(room_store?.federationRoomSession)
    return !!session.enabled
  }

  function getRoleLabel(msg) {
    const sender = safeString(msg?.sender).trim()
    const senderType = safeString(msg?.sender_type).trim()
    const my = safeString(myUid.value).trim()
    const roleName = safeString(msg?.role_name).trim()
    const avatar = safeString(msg?.avatar || '🤖').trim()
    const roomEventType = safeString(msg?.room_event_type).trim()
    const isFederatedRoom = isActiveFederatedRoom()

    const labelYou = resolveRoleLabelText('you')
    const labelUser = resolveRoleLabelText('user')
    const labelRole = resolveRoleLabelText('role')
    const labelSupervisor = resolveRoleLabelText('supervisor')
    const labelAI = resolveRoleLabelText('ai')
    const labelSystem = resolveRoleLabelText('system')

    if (roomEventType === 'room.final') {
      return `${avatar} ${roleName || labelSupervisor}`
    }
    if (senderType === 'role') {
      return `${avatar} ${roleName || sender || labelRole}`
    }
    if (senderType === 'supervisor') {
      return `${avatar} ${roleName || labelSupervisor}`
    }
    if (senderType === 'ai') {
      return `🤖 ${labelAI}`
    }
    if (senderType === 'system') {
      return `ℹ️ ${labelSystem}`
    }
    if (msg?.role === 'user') {
      if (!isFederatedRoom && sender && my && sender === my) {
        return `👤 ${labelYou}`
      }
      if (sender) {
        return `👤 ${sender}`
      }
      return `👤 ${isFederatedRoom ? labelUser : labelYou}`
    }
    if (sender) {
      return `👤 ${sender}`
    }
    return `🤖 ${labelAI}`
  }

  function existingRenderableMessages() {
    return safeArray(messages.value).filter((msg) => {
      const body = safeString(msg?.response || msg?.content).trim()
      const hasToolActivity =
        safeArray(msg?.tool_calls).length > 0 || safeArray(msg?.tool_results).length > 0
      return !!body || hasToolActivity
    })
  }

  function mapStoreItemsToMessages() {
    return safeArray(room_store.items)
      .map(mapRoomEventToMessage)
      .filter(Boolean)
  }

  function applyRoomMessagesFromStore({ preserve_existing_on_empty = true } = {}) {
    const mapped = mapStoreItemsToMessages()

    if (mapped.length) {
      const existing = existingRenderableMessages()

      const optimisticOnly = existing.filter((msg) => {
        const src = safeObject(msg)
        const id = safeString(src.id).trim()
        const requestId = safeString(src.request_id).trim()
        const role = safeString(src.role).trim()
        return !!src.pending || (!id && !!requestId && role === 'user')
      })

      const merged = mergeRenderedMessages(optimisticOnly, mapped)
      messages.value = merged.length ? merged : buildEmptyRoomPlaceholder()
      return messages.value
    }

    const existing = preserve_existing_on_empty ? existingRenderableMessages() : []
    messages.value = existing.length ? existing : buildEmptyRoomPlaceholder()
    return messages.value
  }

  const runtimeReader = use_chat_panel_room_runtime_reader({
    call_tool,
    chat_cfg,
    activeRoomId,
    isRoomMode,
    is_thinking,
    messages,
    scroll_to_bottom,
    room_store,
    hasMoreOlder,
    loadingOlder,
    roomRuntimeLive,
    roomRuntimeStatusText,
    roomRuntimeRunId,
    roomRuntimeResultEvent,
    roomRuntimeViewMode,
    roomRuntimeSelectedReplayRunId,
    buildMessageLocalId,
    existingRenderableMessages,
    applyRoomMessagesFromStore,
  })

  function setRoomRuntimeViewMode(mode) {
    return runtimeReader.setRoomRuntimeViewMode(mode)
  }

  function ensureCurrentRoomRuntimeMode() {
    if (!isRoomMode.value) return
    if (!safeString(activeRoomId.value).trim()) return
    if (roomRuntimeViewMode.value === 'current') return
    runtimeReader.setRoomRuntimeViewMode('current')
  }

  function shouldPollRoomRuntime() {
    if (!isRoomMode.value) return false
    if (!safeString(activeRoomId.value).trim()) return false
    return runtimeReader.shouldPollRoomRuntime()
  }

  function pollRoomRuntimeNow(opts = {}) {
    const next = safeObject(opts)
    const mode = safeString(next.mode).trim().toLowerCase()
    if (mode !== 'replay') {
      ensureCurrentRoomRuntimeMode()
    }
    return runtimeReader.pollRoomRuntimeNow(next)
  }

  function scheduleRoomRuntimePoll(delay) {
    if (!shouldPollRoomRuntime()) return
    return runtimeReader.scheduleRoomRuntimePoll(delay)
  }

  async function refreshRoomRuntime(opts = {}) {
    const next = safeObject(opts)
    const mode = safeString(next.mode).trim().toLowerCase()
    if (mode !== 'replay') {
      ensureCurrentRoomRuntimeMode()
    }
    return await runtimeReader.refreshRoomRuntime(next)
  }

  async function nudgeRoomRuntimePolling(opts = {}) {
    const control = roomRuntimeControlSnapshot.value
    if (roomRuntimeViewMode.value === 'replay' && isMeaningfulRuntimeControl(control)) {
      ensureCurrentRoomRuntimeMode()
    }
    return await runtimeReader.nudgeRoomRuntimePolling(opts)
  }

  watch(
    () => chat_cfg.chat?.mode,
    async (mode, prev) => {
      if (prev === 'room' && mode !== 'room') {
        runtimeReader.stopRuntimeReader()

        room_store.resetRoom()

        messages.value = [{
          local_id: buildMessageLocalId('chat_default'),
          role: 'assistant',
          content: defaultAssistantGreeting.value,
          response: defaultAssistantGreeting.value,
          status: 'success',
          message: '',
          citations: [],
          rss_evidence: [],
          market_evidence: [],
          evidence_query: '',
          evidence_tools: [],
          evidence_result: {},
          tool_calls: [],
          tool_results: [],
          pending: false,
          meta: null,
        }]

        const id = safeString(props.convId).trim()
        internal_conv_id.value = id || null
        if (id) await load_conversation(id)
      }
    }
  )

  watch(
    [() => chat_cfg.chat?.mode, () => activeRoomId.value],
    async ([mode, rid], [prevMode, prevRid]) => {
      if (mode !== 'room') return

      const roomId = safeString(rid).trim()
      if (!roomId) return

      const changed = prevMode !== 'room' || safeString(prevRid).trim() !== roomId
      if (!changed) return

      setRoomRuntimeViewMode('current')
      await runtimeReader.requestRoomSwitch(roomId)
    },
    { immediate: true, flush: 'sync' }
  )

  watch(
    [
      () => room_store.currentRunId,
      () => room_store.currentRunStatus,
      () => room_store.roomState?.continuation_status,
      () => roomRuntimeControlSnapshot.value.runtimeState,
      () => roomRuntimeControlSnapshot.value.runtimePhase,
      () => roomRuntimeControlSnapshot.value.canAcceptNewPrompt,
      () => roomRuntimeControlSnapshot.value.controlBlockReason,
      () => roomRuntimeControlSnapshot.value.canPauseCurrent,
      () => roomRuntimeControlSnapshot.value.canResume,
      () => roomRuntimeControlSnapshot.value.pauseRequested,
      () => roomRuntimeControlSnapshot.value.pauseRequestAccepted,
      () => roomRuntimeControlSnapshot.value.pauseEffective,
      () => roomRuntimeControlSnapshot.value.resumeReady,
      () => roomRuntimeControlSnapshot.value.budgetExhausted,
      () => activeRoomId.value,
      () => chat_cfg.chat?.mode,
    ],
    (
      [
        runId,
        runStatus,
        continuationStatus,
        runtimeState,
        runtimePhase,
        canAcceptNewPrompt,
        controlBlockReason,
        canPauseCurrent,
        canResume,
        pauseRequested,
        pauseRequestAccepted,
        pauseEffective,
        resumeReady,
        budgetExhausted,
        roomId,
        mode,
      ],
      [
        prevRunId,
        prevRunStatus,
        prevContinuationStatus,
        prevRuntimeState,
        prevRuntimePhase,
        prevCanAcceptNewPrompt,
        prevControlBlockReason,
        prevCanPauseCurrent,
        prevCanResume,
        prevPauseRequested,
        prevPauseRequestAccepted,
        prevPauseEffective,
        prevResumeReady,
        prevBudgetExhausted,
      ]
    ) => {
      if (mode !== 'room') return
      if (!safeString(roomId).trim()) return

      const nextRunId = safeString(runId).trim()
      const prevId = safeString(prevRunId).trim()
      const nextStatus = safeString(runStatus).trim()
      const nextContinuationStatus = safeString(continuationStatus).trim()

      const nextControl = normalizeRuntimeControlSnapshot({
        runtime_state: runtimeState,
        runtime_phase: runtimePhase,
        can_accept_new_prompt: canAcceptNewPrompt,
        control_block_reason: controlBlockReason,
        can_pause_current: canPauseCurrent,
        can_resume: canResume,
        pause_requested: pauseRequested,
        pause_request_accepted: pauseRequestAccepted,
        pause_effective: pauseEffective,
        resume_ready: resumeReady,
        budget_exhausted: budgetExhausted,
      })

      const prevControl = normalizeRuntimeControlSnapshot({
        runtime_state: prevRuntimeState,
        runtime_phase: prevRuntimePhase,
        can_accept_new_prompt: prevCanAcceptNewPrompt,
        control_block_reason: prevControlBlockReason,
        can_pause_current: prevCanPauseCurrent,
        can_resume: prevCanResume,
        pause_requested: prevPauseRequested,
        pause_request_accepted: prevPauseRequestAccepted,
        pause_effective: prevPauseEffective,
        resume_ready: prevResumeReady,
        budget_exhausted: prevBudgetExhausted,
      })

      const hasMeaningfulStatus =
        isActiveRuntimeStatus(nextStatus) ||
        isTerminalRuntimeStatus(nextStatus) ||
        isContinuationActiveRuntimeStatus(nextContinuationStatus) ||
        isContinuationTerminalRuntimeStatus(nextContinuationStatus)

      const hasMeaningfulControl = isMeaningfulRuntimeControl(nextControl)

      if (!nextRunId && !hasMeaningfulStatus && !hasMeaningfulControl) {
        return
      }

      if (roomRuntimeViewMode.value === 'replay' && hasMeaningfulControl) {
        ensureCurrentRoomRuntimeMode()
      }

      const runChanged = !!nextRunId && nextRunId !== prevId
      const currentStatusNeedsNudge = shouldNudgeForRuntimeStatus(nextStatus, prevRunStatus)
      const continuationStatusNeedsNudge = shouldNudgeForRuntimeStatus(
        nextContinuationStatus,
        prevContinuationStatus
      )
      const controlNeedsNudge = shouldNudgeForRuntimeControl(nextControl, prevControl)

      if (!runChanged && !currentStatusNeedsNudge && !continuationStatusNeedsNudge && !controlNeedsNudge) {
        return
      }

      const reason = runChanged
        ? 'current_run_changed'
        : controlNeedsNudge
          ? 'runtime_control_changed'
          : continuationStatusNeedsNudge
            ? 'continuation_status_changed'
            : 'current_run_status_changed'

      Promise.resolve(
        runtimeReader.nudgeRoomRuntimePolling({
          reason,
          force: true,
        })
      ).catch(() => {})
    },
    { flush: 'sync' }
  )

  room_store.refreshWhoAmI(call_tool, {})
    .then((whoami) => {
      myUid.value = whoami?.uid || localStorage.getItem('nisb_user_id') || 'unknown'
    })
    .catch(async () => {
      try {
        const raw = await call_tool('nisb_room_shared_whoami', {})
        const whoami = extractWhoAmI(raw)
        myUid.value = whoami.uid || localStorage.getItem('nisb_user_id') || 'unknown'
        if (typeof room_store.setWhoAmI === 'function') {
          room_store.setWhoAmI(raw)
        }
      } catch {
        myUid.value = localStorage.getItem('nisb_user_id') || 'unknown'
      }
    })

  return {
    myUid,
    isRoomMode,
    activeRoomId,
    hasMoreOlder,
    loadingOlder,
    roomItemsPaging,

    roomRuntimeExpanded,
    roomRuntimeLoading,
    roomRuntimeError,
    roomRuntimeLive,
    roomRuntimeVisible,
    roomRuntimeProcessItems,
    roomRuntimeResultEvent,
    roomRuntimeResultPayload,
    roomRuntimeResultText,
    roomRuntimeRunId,
    roomRuntimeStatusText,
    roomRuntimeViewMode,
    roomRuntimeRunOptions,
    roomRuntimeSelectedReplayRunId,

    roomRuntimeControlSnapshot,
    roomRuntimeState,
    roomRuntimePhase,
    roomRuntimeCanAcceptNewPrompt,
    roomRuntimeControlBlockReason,
    roomRuntimeCanPauseCurrent,
    roomRuntimeCanResume,
    roomRuntimePauseRequested,
    roomRuntimePauseRequestAccepted,
    roomRuntimePauseEffective,
    roomRuntimeResumeReady,
    roomRuntimeBudgetExhausted,

    roomRuntimeDisplayBundle,
    roomRuntimeDisplayResultEntry,
    roomRuntimeTimelineEntries,
    roomRuntimeAuditCards,
    roomRuntimeToolCallRows,
    roomRuntimeToolResultRows,
    roomRuntimeHeadline,
    roomRuntimeBadgeSummary,
    roomRuntimeSkillSummary,
    roomRuntimeSkillCards,
    roomRuntimeSkillActivityRows,

    getRoleLabel,
    toggleRoomRuntimeExpanded,
    setRoomRuntimeViewMode,
    ensureCurrentRoomRuntimeMode,
    selectRoomRuntimeReplayRun: runtimeReader.selectRoomRuntimeReplayRun,
    resetRoomRuntimeLane: runtimeReader.resetRoomRuntimeLane,
    clearRoomRuntimePoller: runtimeReader.clearRoomRuntimePoller,
    shouldPollRoomRuntime,
    pollRoomRuntimeNow,
    scheduleRoomRuntimePoll,
    refreshRoomRuntimeEvents: runtimeReader.refreshRoomRuntimeEvents,
    refreshRoomRuntimeReplay: runtimeReader.refreshRoomRuntimeReplay,
    refreshRoomRuntime,
    nudgeRoomRuntimePolling,
    loadRoomMessages: runtimeReader.loadRoomMessages,
    loadOlderRoomMessages: runtimeReader.loadOlderRoomMessages,
    requestRoomSwitch: runtimeReader.requestRoomSwitch,
  }
}

export default use_chat_panel_room_controller
