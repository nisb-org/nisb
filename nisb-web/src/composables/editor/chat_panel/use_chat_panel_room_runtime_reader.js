import { nextTick, onMounted, onUnmounted } from 'vue'

const ROOM_RUNTIME_POLL_FAST_MS = 900
const ROOM_RUNTIME_POLL_IDLE_MS = 1400

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function safeString(v) {
  return v === null || v === undefined ? '' : String(v)
}

function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
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

function normalizeToken(value) {
  return safeString(value).trim().toLowerCase()
}

function normalizeRuntimeViewMode(value) {
  return normalizeToken(value) === 'replay' ? 'replay' : 'current'
}

function normalizeRuntimeState(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'completed after resume') return 'completed_after_resume'
  if (token === 'budget exhausted') return 'budget_exhausted'
  if (token === 'step_budget_exhausted' || token === 'exhausted') return 'budget_exhausted'
  if (token === 'pause requested') return 'pause_requested'
  if (token === 'waiting checkpoint') return 'waiting_checkpoint'
  return token.replace(/\s+/g, '_')
}

function normalizeRuntimeControlSnapshot(raw) {
  const src = safeObject(raw)
  const candidates = [
    src,
    safeObject(src.runtime_control_snapshot),
    safeObject(src.control_snapshot),
  ].filter((row) => Object.keys(row).length > 0)

  const runtimeState = normalizeRuntimeState(
    readControlValue(candidates, ['runtime_state', 'runtimeState', 'state'])
  )
  const runtimePhase = normalizeRuntimeState(
    readControlValue(candidates, ['runtime_phase', 'runtimePhase', 'phase'])
  )
  const canAcceptNewPrompt = safeBoolean(
    readControlValue(candidates, ['can_accept_new_prompt', 'canAcceptNewPrompt']),
    false
  )
  const controlBlockReason = safeString(
    readControlValue(candidates, ['control_block_reason', 'controlBlockReason'])
  ).trim()
  const canPauseCurrent = safeBoolean(
    readControlValue(candidates, ['can_pause_current', 'canPauseCurrent']),
    false
  )
  const canResume = safeBoolean(
    readControlValue(candidates, ['can_resume', 'canResume']),
    false
  )
  const pauseRequested = safeBoolean(
    readControlValue(candidates, ['pause_requested', 'pauseRequested']),
    false
  )
  const pauseRequestAccepted = safeBoolean(
    readControlValue(candidates, ['pause_request_accepted', 'pauseRequestAccepted']),
    false
  )
  const pauseEffective = safeBoolean(
    readControlValue(candidates, ['pause_effective', 'pauseEffective']),
    false
  )
  const resumeReady = safeBoolean(
    readControlValue(candidates, ['resume_ready', 'resumeReady']),
    false
  )
  const budgetExhausted = safeBoolean(
    readControlValue(candidates, ['budget_exhausted', 'budgetExhausted']),
    false
  )

  return {
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
  }
}

function isSnapshotTerminal(snapshot) {
  const ctl = normalizeRuntimeControlSnapshot(snapshot)
  const runtimeState = normalizeRuntimeState(ctl.runtimeState)

  if (['completed', 'completed_after_resume', 'budget_exhausted'].includes(runtimeState)) {
    return true
  }

  if (runtimeState === 'interrupted') {
    return !ctl.canResume
  }

  if (['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(runtimeState)) {
    return false
  }

  return false
}

function isSnapshotPollable(snapshot) {
  const ctl = normalizeRuntimeControlSnapshot(snapshot)
  const runtimeState = normalizeRuntimeState(ctl.runtimeState)
  const runtimePhase = normalizeRuntimeState(ctl.runtimePhase)

  if (
    ['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(runtimeState) ||
    ['waiting_checkpoint'].includes(runtimePhase)
  ) {
    return true
  }

  if (runtimeState === 'interrupted') return false
  if (['completed', 'completed_after_resume', 'budget_exhausted'].includes(runtimeState)) return false

  if (ctl.pauseRequested && !ctl.pauseEffective) return true

  return false
}

function isTerminalRuntimeEventType(value) {
  return [
    'room.final',
    'room.abort',
    'room.aborted',
    'room.error',
  ].includes(safeString(value).trim())
}

function normalizeRuntimeStatusText(value) {
  return safeString(value).trim().toLowerCase()
}

function isTerminalRuntimeStatus(value) {
  const token = normalizeRuntimeStatusText(value)
  if (!token) return false

  const terminalTokens = [
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

  return terminalTokens.some((item) => token.includes(item))
}

function isActiveRuntimeStatus(value) {
  const token = normalizeRuntimeStatusText(value)
  if (!token) return false

  const activeTokens = [
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
    'pause_requested',
    'paused requested',
    'waiting_checkpoint',
    'resumed',
    '处理中',
    '运行中',
    '规划中',
    '委派中',
    '汇总中',
    '暂停请求中',
  ]

  return activeTokens.some((item) => token.includes(item))
}

function normalizeRoomEventKey(item) {
  const src = safeObject(item)
  const id = safeString(src.id).trim()
  if (id) return `id:${id}`

  const localId = safeString(src.local_id).trim()
  if (localId) return `local:${localId}`

  const ts = safeString(src.ts).trim()
  const type = safeString(src.type || src.room_event_type).trim()
  const sender = safeString(src.sender).trim()
  const senderType = safeString(src.sender_type).trim()
  const roleId = safeString(src.role_id).trim()
  const runId = safeString(src.run_id).trim()
  const body = safeString(src.response || src.content).trim()

  return `fallback:${ts}|${type}|${sender}|${senderType}|${roleId}|${runId}|${body}`
}

function roomEventSortKey(item) {
  const src = safeObject(item)
  return `${safeString(src.ts)}|${safeString(src.id || src.local_id)}`
}

function mergeRoomEvents(existing, incoming) {
  const merged = new Map()

  for (const item of safeArray(existing)) {
    const key = normalizeRoomEventKey(item)
    merged.set(key, safeObject(item))
  }

  for (const item of safeArray(incoming)) {
    const key = normalizeRoomEventKey(item)
    merged.set(key, {
      ...safeObject(merged.get(key)),
      ...safeObject(item),
    })
  }

  return Array.from(merged.values()).sort((a, b) => {
    const ka = roomEventSortKey(a)
    const kb = roomEventSortKey(b)
    if (ka < kb) return -1
    if (ka > kb) return 1
    return 0
  })
}

function buildRenderedMessagesSignature(list) {
  const rows = safeArray(list)
  const tail = rows.slice(-16)

  return JSON.stringify({
    count: rows.length,
    tail: tail.map((msg, idx) => ({
      key: safeString(msg?.id || msg?.local_id || `idx_${idx}`),
      role: safeString(msg?.role),
      sender: safeString(msg?.sender),
      sender_type: safeString(msg?.sender_type),
      room_event_type: safeString(msg?.room_event_type),
      status: safeString(msg?.status),
      pending: !!msg?.pending,
      body_len: safeString(msg?.response || msg?.content).length,
      tool_calls_len: safeArray(msg?.tool_calls).length,
      tool_results_len: safeArray(msg?.tool_results).length,
    })),
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

function isCancellationLikeError(error) {
  const name = safeString(error?.name).toLowerCase()
  const msg = safeString(error?.message || error).toLowerCase()

  if (name === 'aborterror') return true
  if (msg.includes('aborted')) return true
  if (msg.includes('aborterror')) return true
  if (msg.includes('请求已取消')) return true
  if (msg.includes('已取消')) return true
  if (msg.includes('cancelled')) return true
  if (msg.includes('canceled')) return true
  if (msg.includes('timeout')) return true
  if (msg.includes('超时')) return true
  return false
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
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

function isRuntimeTimelineEvent(item) {
  const src = safeObject(item)
  const type = safeString(src.type).trim()
  if (!isRuntimeProcessEvent(src)) return false
  if (type !== 'room.message') return true
  const payload = safeObject(src.payload)
  return safeString(payload.sender_type).trim() !== 'user'
}

function getEventLikeId(value) {
  const src = safeObject(value)
  return safeString(src.id || src.event_id || src.eventId).trim()
}

function getEventLikeRunId(value) {
  const src = safeObject(value)
  const payload = safeObject(src.payload)
  return safeString(src.run_id || payload.run_id || payload.runId).trim()
}

function sortEventsAsc(list) {
  return safeArray(list).slice().sort((a, b) => {
    const ak = roomEventSortKey(a)
    const bk = roomEventSortKey(b)
    if (ak < bk) return -1
    if (ak > bk) return 1
    return 0
  })
}

function deriveLatestRuntimeRunIdFromItems(items) {
  const ordered = sortEventsAsc(items)
  for (let idx = ordered.length - 1; idx >= 0; idx -= 1) {
    const row = safeObject(ordered[idx])
    if (!isRuntimeTimelineEvent(row)) continue
    const runId = safeString(row.run_id).trim()
    if (runId) return runId
  }
  return ''
}

function deriveLatestRuntimeEventFromItems(items, runId = '') {
  const ordered = sortEventsAsc(items)
  const targetRunId = safeString(runId).trim()

  for (let idx = ordered.length - 1; idx >= 0; idx -= 1) {
    const row = safeObject(ordered[idx])
    if (!isRuntimeTimelineEvent(row)) continue

    if (targetRunId) {
      const rowRunId = safeString(row.run_id).trim()
      if (rowRunId !== targetRunId) continue
    }

    return row
  }

  return null
}

function hasActiveRuntimeItems(items, runId = '') {
  const ordered = sortEventsAsc(items)
  const targetRunId = safeString(runId).trim()

  for (let idx = ordered.length - 1; idx >= 0; idx -= 1) {
    const row = safeObject(ordered[idx])
    if (!isRuntimeTimelineEvent(row)) continue

    const rowRunId = safeString(row.run_id).trim()
    if (targetRunId) {
      if (!rowRunId || rowRunId !== targetRunId) continue
    }

    const type = safeString(row.type).trim()
    if (!type) continue
    if (isTerminalRuntimeEventType(type)) return false
    return true
  }

  return false
}

function buildStoreOptions(opts = {}) {
  const src = safeObject(opts)

  const relationexpand = src.relationexpand ?? src.relation_expand
  const bytebudget = src.bytebudget ?? src.byte_budget
  const beforeeventid = src.beforeeventid ?? src.before_event_id
  const aftereventid = src.aftereventid ?? src.after_event_id
  const applyworkspacecontext = src.applyworkspacecontext ?? src.apply_workspace_context
  const includeallruns = src.includeallruns ?? src.include_all_runs
  const tail_event_id = src.tail_event_id ?? src.tailEventId

  return {
    ...src,
    relationexpand,
    relation_expand: relationexpand,
    bytebudget,
    byte_budget: bytebudget,
    beforeeventid,
    before_event_id: beforeeventid,
    aftereventid,
    after_event_id: aftereventid,
    applyworkspacecontext,
    apply_workspace_context: applyworkspacecontext,
    includeallruns,
    include_all_runs: includeallruns,
    tail_event_id,
    tailEventId: tail_event_id,
  }
}

export function use_chat_panel_room_runtime_reader({
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
}) {
  let _roomPassiveTimer = null
  let _roomLoadSeq = 0
  let _roomAbortCtrl = null
  let _roomSwitchBusy = false
  let _roomPendingRid = ''

  let _roomLoadBusy = false
  let _roomReloadQueued = false
  let _roomQueuedRid = ''
  let _roomQueuedOpts = null
  let _roomActiveLoadRid = ''

  let _roomPaginationBusy = false
  let _roomPassiveRefreshSuspendedUntil = 0
  let _roomAutoFollowUntil = 0

  let _roomRuntimePollTimer = 0
  let _roomRuntimePollBusy = false

  function isReplayMode() {
    return normalizeRuntimeViewMode(roomRuntimeViewMode?.value) === 'replay'
  }

  function getCurrentStoreRunId() {
    return safeString(room_store.currentRunId || room_store.runtimeRunId).trim()
  }

  function getCurrentStoreRunStatus() {
    return safeString(room_store.currentRunStatus || room_store.runtimeStatusText).trim()
  }

  function getCurrentLaneRuntimeItems() {
    const explicit = room_store.runtimeItems
    if (Array.isArray(explicit)) return explicit
    return safeArray(room_store.items).filter(isRuntimeProcessEvent)
  }

  function getCurrentLaneResultEvent() {
    return safeObject(room_store.runtimeResultEvent)
  }

  function getCurrentRuntimeControlSnapshot() {
    return normalizeRuntimeControlSnapshot(
      room_store.runtimeControlSnapshot ||
        room_store.runtime?.runtime_control_snapshot ||
        room_store.runtime?.control_snapshot ||
        room_store.roomState?.runtime_control_snapshot ||
        room_store.roomState ||
        {}
    )
  }

  function hasTerminalRuntimeEvidence() {
    if (isReplayMode()) return true

    const snapshot = getCurrentRuntimeControlSnapshot()
    const runtimeState = normalizeRuntimeState(snapshot.runtimeState)

    if (['completed', 'completed_after_resume', 'budget_exhausted'].includes(runtimeState)) {
      return true
    }

    if (runtimeState === 'interrupted') {
      return !snapshot.canResume
    }

    if (['running', 'pause_requested', 'waiting_checkpoint', 'resumed'].includes(runtimeState)) {
      return false
    }

    if (isTerminalRuntimeEventType(roomRuntimeResultEvent?.value?.type)) return true
    if (isTerminalRuntimeStatus(roomRuntimeStatusText?.value)) return true

    const currentResult = getCurrentLaneResultEvent()
    if (isTerminalRuntimeEventType(currentResult?.type)) return true

    const currentStatus = getCurrentStoreRunStatus()
    if (isTerminalRuntimeStatus(currentStatus)) return true

    return false
  }

  function clearRoomRuntimePoller() {
    try {
      if (_roomRuntimePollTimer) clearTimeout(_roomRuntimePollTimer)
    } catch {}
    _roomRuntimePollTimer = 0
  }

  function stopRuntimeReader() {
    _clear_room_passive_timer()
    clearRoomRuntimePoller()
    try { _roomAbortCtrl?.abort() } catch {}
    _roomLoadBusy = false
    _roomReloadQueued = false
    _roomQueuedRid = ''
    _roomQueuedOpts = null
    _roomActiveLoadRid = ''
    _roomPaginationBusy = false
    _roomPassiveRefreshSuspendedUntil = 0
    _roomPendingRid = ''
    _roomSwitchBusy = false
    _clear_room_auto_follow()
  }

  function _arm_room_auto_follow(ms = 180000) {
    const nextUntil = Date.now() + Math.max(1000, Number(ms || 0))
    if (nextUntil > _roomAutoFollowUntil) {
      _roomAutoFollowUntil = nextUntil
    }
  }

  function _clear_room_auto_follow() {
    _roomAutoFollowUntil = 0
  }

  function _should_room_auto_follow() {
    return Date.now() < _roomAutoFollowUntil
  }

  function _suspend_passive_refresh(ms = 3500) {
    const until = Date.now() + Math.max(0, Number(ms) || 0)
    if (until > _roomPassiveRefreshSuspendedUntil) {
      _roomPassiveRefreshSuspendedUntil = until
    }
  }

  function _can_run_passive_refresh() {
    if (document.hidden) return false
    if (_roomSwitchBusy) return false
    if (_roomPendingRid) return false
    if (_roomLoadBusy) return false
    if (_roomPaginationBusy) return false
    if (Date.now() < _roomPassiveRefreshSuspendedUntil) return false
    return true
  }

  function _passive_refresh_delay() {
    const snapshot = getCurrentRuntimeControlSnapshot()

    if (!isReplayMode() && isSnapshotPollable(snapshot)) return 1200
    if (roomRuntimeLive.value && !isReplayMode()) return 1200
    if (isActiveRuntimeStatus(roomRuntimeStatusText.value) && !isReplayMode()) return 1600
    return 2400
  }

  function _clear_room_passive_timer() {
    if (_roomPassiveTimer) {
      clearTimeout(_roomPassiveTimer)
      _roomPassiveTimer = null
    }
  }

  function scheduleRoomPassiveRefresh(delayMs = null) {
    _clear_room_passive_timer()

    if (chat_cfg.chat?.mode !== 'room') return
    if (!safeString(activeRoomId.value).trim()) return
    if (document.hidden) return

    const ms = Number.isFinite(delayMs) ? delayMs : _passive_refresh_delay()

    _roomPassiveTimer = setTimeout(async () => {
      try {
        if (_can_run_passive_refresh()) {
          const cur = safeString(activeRoomId.value).trim()
          if (cur) {
            await loadRoomMessages(cur, {
              scroll_to_bottom: false,
              preserve_existing: true,
              runtime_silent: true,
            })
          }
        }
      } finally {
        scheduleRoomPassiveRefresh()
      }
    }, Math.max(500, Number(ms || 0)))
  }

  async function _wait_for_active_load_to_settle(timeoutMs = 1200) {
    const start = Date.now()

    while (_roomLoadBusy && Date.now() - start < timeoutMs) {
      try { _roomAbortCtrl?.abort() } catch {}
      await sleep(40)
    }

    return !_roomLoadBusy
  }

  function _preserve_older_paging_state_after_recent_refresh(previousPaging = {}) {
    const prev = normalizePagingState(previousPaging)
    if (!prev.loadedonce) return

    room_store.itemsPaging = {
      ...safeObject(room_store.itemsPagingState),
      loadedonce: true,
      hasmore: prev.hasmore,
      nextcursor: prev.nextcursor,
      loadingolder: false,
    }
  }

  function _schedule_followup_load(rid = '', opts = {}) {
    const nextRid = safeString(rid || _roomQueuedRid || activeRoomId.value).trim()
    if (!nextRid) return
    _roomReloadQueued = true
    _roomQueuedRid = nextRid
    _roomQueuedOpts = { ...safeObject(opts) }
  }

  async function _run_followup_load_if_needed() {
    if (!_roomReloadQueued) return

    const nextRid = safeString(_roomQueuedRid || activeRoomId.value).trim()
    const nextOpts = safeObject(_roomQueuedOpts)

    _roomReloadQueued = false
    _roomQueuedRid = ''
    _roomQueuedOpts = null

    if (!nextRid) return

    await loadRoomMessages(nextRid, { ...nextOpts, from_queue: true })
  }

  function _perform_room_follow_scroll() {
    nextTick(() => {
      scroll_to_bottom(true)

      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => {
          scroll_to_bottom(true)
        })
      }

      setTimeout(() => {
        scroll_to_bottom(true)
      }, 120)

      setTimeout(() => {
        scroll_to_bottom(true)
      }, 360)
    })
  }

  function _should_reset_current_runtime_lane({
    requestedRunId = '',
    resultEventRunId = '',
    latestItemsRunId = '',
    latestRuntimeEventId = '',
    currentResultEventId = '',
    latestRuntimeEventType = '',
    currentLaneItems = [],
    normalized = {},
  } = {}) {
    if (normalized.reset) return true
    if (normalized.includeallruns) return !!normalized.reset

    const targetRunId = safeString(requestedRunId).trim()
    const resultRunId = safeString(resultEventRunId).trim()
    const latestRunId = safeString(latestItemsRunId).trim()
    const latestType = safeString(latestRuntimeEventType).trim()
    const laneItems = safeArray(currentLaneItems)

    if (targetRunId) {
      if (resultRunId && resultRunId !== targetRunId) {
        return true
      }

      if (!laneItems.length && !safeString(normalized.aftereventid || normalized.after_event_id).trim()) {
        return true
      }

      if (
        latestRunId &&
        latestRunId === targetRunId &&
        latestRuntimeEventId &&
        currentResultEventId &&
        latestRuntimeEventId !== currentResultEventId &&
        latestType === 'room.plan'
      ) {
        return true
      }
    } else if (latestRunId && latestRunId !== resultRunId) {
      return true
    }

    return false
  }

  async function refreshRoomRuntimeEvents(opts = {}) {
    if (isReplayMode() && !opts?.force_current) {
      return safeObject(room_store.runtimeState)
    }

    const rid = safeString(opts?.room_id || opts?.roomId || activeRoomId.value).trim()
    if (!rid) return safeObject(room_store.runtimeState)

    if (typeof room_store.refreshRuntimeEvents !== 'function') {
      return safeObject(room_store.runtimeState)
    }

    const normalized = buildStoreOptions({
      ...opts,
      room_id: rid,
      roomId: rid,
    })

    const snapshot = getCurrentRuntimeControlSnapshot()
    const latestItems = safeArray(room_store.items)
    const latestItemsRunId = deriveLatestRuntimeRunIdFromItems(latestItems)
    const currentStoreRunId = getCurrentStoreRunId()
    const currentStoreRunStatus = getCurrentStoreRunStatus()
    const requestedRunId = safeString(currentStoreRunId || latestItemsRunId).trim()
    const latestRuntimeEvent = deriveLatestRuntimeEventFromItems(latestItems, requestedRunId || latestItemsRunId)
    const latestRuntimeEventId = getEventLikeId(latestRuntimeEvent)
    const latestRuntimeEventType = safeString(safeObject(latestRuntimeEvent).type).trim()

    const currentResultEvent = getCurrentLaneResultEvent()
    const currentResultEventId = getEventLikeId(currentResultEvent)
    const resultEventRunId = getEventLikeRunId(currentResultEvent)
    const currentLaneItems = getCurrentLaneRuntimeItems()

    const terminalBySnapshot = isSnapshotTerminal(snapshot)
    const terminalByStatus =
      isTerminalRuntimeStatus(currentStoreRunStatus) ||
      isTerminalRuntimeStatus(roomRuntimeStatusText?.value)

    const terminalByResult =
      isTerminalRuntimeEventType(currentResultEvent?.type) ||
      isTerminalRuntimeEventType(latestRuntimeEventType)

    const isTerminalCurrentRun =
      !normalized.includeallruns &&
      (terminalBySnapshot || terminalByStatus || terminalByResult)

    let shouldReset = _should_reset_current_runtime_lane({
      requestedRunId,
      resultEventRunId,
      latestItemsRunId,
      latestRuntimeEventId,
      currentResultEventId,
      latestRuntimeEventType,
      currentLaneItems,
      normalized,
    })

    const shouldClearIncrementalCursor = shouldReset || isTerminalCurrentRun
    let nextAfterEventId = safeString(normalized.aftereventid || normalized.after_event_id).trim()

    if (shouldClearIncrementalCursor) {
      nextAfterEventId = ''
      _arm_room_auto_follow(90000)
    }

    return await room_store.refreshRuntimeEvents(call_tool, rid, buildStoreOptions({
      ...normalized,
      room_id: rid,
      roomId: rid,
      reset: shouldReset,
      aftereventid: nextAfterEventId,
      after_event_id: nextAfterEventId,
    }))
  }

  function getStickyReplayRunId(opts = {}) {
    const explicitRunId = safeString(opts?.run_id || opts?.selected_run_id).trim()
    if (explicitRunId) return explicitRunId

    const stickyRunId = safeString(
      roomRuntimeSelectedReplayRunId?.value ||
        room_store.runtime?.selected_run_id ||
        room_store.runtime?.replay_selected_run_id ||
        room_store.runtimeReplayRunId ||
        room_store.runtimeReplayBundle?.selected_run_id ||
        room_store.runtimeReplayBundle?.run_id ||
        room_store.runtime?.replay_bundle?.selected_run_id ||
        room_store.runtime?.replay_bundle?.run_id
    ).trim()

    return stickyRunId
  }

  async function refreshRoomRuntimeReplay(opts = {}) {
    const rid = safeString(opts?.room_id || opts?.roomId || activeRoomId.value).trim()
    if (!rid) return safeObject(room_store.runtimeReplayBundle)

    if (typeof room_store.refreshRuntimeReplay !== 'function') {
      return safeObject(room_store.runtimeReplayBundle)
    }

    const stickyRunId = getStickyReplayRunId(opts)
    const allowFallbackLatest = safeBoolean(opts?.allow_fallback_latest, false)

    const fallbackRunId = allowFallbackLatest
      ? safeString(room_store.latestCompletedRunId).trim()
      : ''

    const selectedRunId = safeString(stickyRunId || fallbackRunId).trim()

    if (!selectedRunId) {
      return safeObject(
        room_store.runtimeReplayBundle ||
          room_store.runtime?.replay_bundle ||
          room_store.runtime?.replayBundle ||
          {}
      )
    }

    if (typeof room_store.setRuntimeReplayRunId === 'function') {
      room_store.setRuntimeReplayRunId(selectedRunId)
    }

    if (typeof room_store.setRuntimeViewMode === 'function') {
      room_store.setRuntimeViewMode('replay')
    }

    return await room_store.refreshRuntimeReplay(call_tool, rid, buildStoreOptions({
      ...opts,
      room_id: rid,
      roomId: rid,
      run_id: selectedRunId,
      selected_run_id: selectedRunId,
      set_view_mode: true,
    }))
  }

  async function refreshRoomRuntime(opts = {}) {
    const requestedMode = normalizeRuntimeViewMode(opts?.view_mode || roomRuntimeViewMode?.value)

    if (requestedMode === 'replay') {
      return await refreshRoomRuntimeReplay({
        silent: false,
        allow_fallback_latest: false,
        ...opts,
      })
    }

    return await refreshRoomRuntimeEvents({
      silent: false,
      force_current: true,
      ...opts,
    })
  }

  async function nudgeRoomRuntimePolling(opts = {}) {
    if (!isRoomMode.value) return null
    if (isReplayMode()) return null
    if (hasTerminalRuntimeEvidence()) return null

    const rid = safeString(opts?.room_id || activeRoomId.value).trim()
    if (!rid) return null

    await refreshRoomRuntimeEvents({
      room_id: rid,
      silent: true,
      force_current: true,
    })

    if (shouldPollRoomRuntime()) {
      scheduleRoomRuntimePoll(0)
    }

    return await loadRoomMessages(rid, {
      scroll_to_bottom: false,
      preserve_existing: true,
      runtime_silent: false,
      ...opts,
    })
  }

  async function setRoomRuntimeViewMode(mode = 'current', opts = {}) {
    const nextMode = normalizeRuntimeViewMode(mode)
    const rid = safeString(opts?.room_id || activeRoomId.value).trim()

    if (!rid) {
      if (typeof room_store.setRuntimeViewMode === 'function') {
        room_store.setRuntimeViewMode(nextMode)
      }
      return safeObject(room_store.runtimeState)
    }

    if (nextMode === 'replay') {
      clearRoomRuntimePoller()
      return await refreshRoomRuntimeReplay({
        ...opts,
        room_id: rid,
        set_view_mode: true,
      })
    }

    if (typeof room_store.setRuntimeViewMode === 'function') {
      room_store.setRuntimeViewMode('current')
    }
    if (typeof room_store.resetRuntimeReplay === 'function') {
      room_store.resetRuntimeReplay({
        preserve_view_mode: true,
        preserve_selected_run: false,
      })
    }

    await refreshRoomRuntimeEvents({
      room_id: rid,
      silent: !!opts?.silent,
      reset: !!opts?.reset_current,
      force_current: true,
    })

    if (shouldPollRoomRuntime()) {
      scheduleRoomRuntimePoll(0)
    }

    return safeObject(room_store.runtimeState)
  }

  async function selectRoomRuntimeReplayRun(runId = '', opts = {}) {
    const rid = safeString(opts?.room_id || activeRoomId.value).trim()
    const selectedRunId = safeString(runId || roomRuntimeSelectedReplayRunId?.value).trim()

    if (!rid || !selectedRunId) return safeObject(room_store.runtimeReplayBundle)

    clearRoomRuntimePoller()

    if (typeof room_store.setRuntimeReplayRunId === 'function') {
      room_store.setRuntimeReplayRunId(selectedRunId)
    }
    if (typeof room_store.setRuntimeViewMode === 'function') {
      room_store.setRuntimeViewMode('replay')
    }

    return await refreshRoomRuntimeReplay({
      ...opts,
      room_id: rid,
      run_id: selectedRunId,
      selected_run_id: selectedRunId,
      set_view_mode: true,
    })
  }

  function resetRoomRuntimeLane() {
    clearRoomRuntimePoller()

    if (typeof room_store.setRuntimeViewMode === 'function') {
      room_store.setRuntimeViewMode('current')
    }
    if (typeof room_store.resetRuntimeReplay === 'function') {
      room_store.resetRuntimeReplay({
        preserve_view_mode: true,
        preserve_selected_run: false,
      })
    }

    if (shouldPollRoomRuntime()) {
      scheduleRoomRuntimePoll(0)
    }
  }

  function shouldPollRoomRuntime() {
    if (!isRoomMode.value) return false
    if (isReplayMode()) return false

    const roomId = safeString(activeRoomId.value).trim()
    if (!roomId) return false

    const snapshot = getCurrentRuntimeControlSnapshot()
    if (isSnapshotPollable(snapshot)) return true
    if (isSnapshotTerminal(snapshot)) return false

    const runId = safeString(getCurrentStoreRunId() || roomRuntimeRunId.value).trim()
    const resultEvent = safeObject(roomRuntimeResultEvent.value || getCurrentLaneResultEvent())
    const resultEventId = getEventLikeId(resultEvent)
    const currentStatus = getCurrentStoreRunStatus()
    const currentLaneItems = getCurrentLaneRuntimeItems()

    if (is_thinking?.value) return true
    if (roomRuntimeLive.value) return true
    if (isActiveRuntimeStatus(roomRuntimeStatusText.value)) return true
    if (isActiveRuntimeStatus(currentStatus)) return true

    if (runId && !resultEventId) {
      return hasActiveRuntimeItems(currentLaneItems, runId)
    }

    return false
  }

  async function pollRoomRuntimeNow(opts = {}) {
    const force = !!opts?.force
    const forceCurrent = !!opts?.force_current
    const roomId = safeString(opts?.room_id || activeRoomId.value).trim()

    if (!roomId) return null
    if (isReplayMode() && !forceCurrent) return null
    if (!force && !shouldPollRoomRuntime()) return null
    if (_roomRuntimePollBusy) return null

    _roomRuntimePollBusy = true

    try {
      await refreshRoomRuntimeEvents({
        room_id: roomId,
        silent: true,
        force_current: true,
      })

      if (!force && hasTerminalRuntimeEvidence()) {
        clearRoomRuntimePoller()
      }

      return await loadRoomMessages(roomId, {
        scroll_to_bottom: false,
        preserve_existing: true,
        runtime_silent: true,
      })
    } catch {
      return null
    } finally {
      _roomRuntimePollBusy = false
    }
  }

  function scheduleRoomRuntimePoll(delay = 0) {
    clearRoomRuntimePoller()

    if (isReplayMode()) return
    if (!shouldPollRoomRuntime()) return

    const nextDelay = Math.max(0, Number(delay) || 0)

    _roomRuntimePollTimer = window.setTimeout(async () => {
      await pollRoomRuntimeNow()

      if (!isReplayMode() && shouldPollRoomRuntime()) {
        scheduleRoomRuntimePoll(is_thinking?.value ? ROOM_RUNTIME_POLL_FAST_MS : ROOM_RUNTIME_POLL_IDLE_MS)
      }
    }, nextDelay)
  }

  async function loadRoomMessages(ridOverride = null, opts = {}) {
    const rid = safeString(ridOverride ?? activeRoomId.value).trim()
    if (!rid) return

    if (_roomLoadBusy) {
      _schedule_followup_load(rid, opts)
      return
    }

    const seq = ++_roomLoadSeq
    _roomLoadBusy = true
    _roomActiveLoadRid = rid

    const normalizedOpts = buildStoreOptions(opts)
    const shouldScrollBottom = normalizedOpts.scroll_to_bottom !== false
    const preserveExisting = normalizedOpts.preserve_existing !== false
    const useBundleLoad = normalizedOpts.use_bundle_load === true || !preserveExisting
    const previousItems = preserveExisting ? safeArray(room_store.items).slice() : []
    const previousPaging = preserveExisting ? normalizePagingState(room_store.itemsPagingState) : {}
    const previousSignature = buildRenderedMessagesSignature(messages.value)
    const previousRuntimeResultEventId = getEventLikeId(room_store.runtimeResultEvent)
    const previousRuntimeResultType = safeString(room_store.runtimeResultEvent?.type).trim()

    let shouldForceBottomAfterApply = false
    let shouldExtendAutoFollow = false

    try {
      if (normalizedOpts.force_abort === true) {
        try { _roomAbortCtrl?.abort() } catch {}
      }

      _roomAbortCtrl = new AbortController()
      const signal = _roomAbortCtrl.signal

      if (useBundleLoad) {
        await room_store.loadRoomBundle(call_tool, rid, buildStoreOptions({
          signal,
          limit: normalizedOpts.limit ?? 200,
          order: 'asc',
          relationexpand: normalizedOpts.relationexpand,
          bytebudget: normalizedOpts.bytebudget,
          applyworkspacecontext: normalizedOpts.applyworkspacecontext,
        }))
      } else {
        await Promise.all([
          room_store.refreshRoomItems(call_tool, rid, buildStoreOptions({
            signal,
            limit: normalizedOpts.limit ?? 200,
            order: 'asc',
            relationexpand: normalizedOpts.relationexpand,
            bytebudget: normalizedOpts.bytebudget,
          })),
          room_store.refreshRoomInfo(call_tool, rid, buildStoreOptions({
            signal,
            applyworkspacecontext: normalizedOpts.applyworkspacecontext,
          })).catch(() => null),
        ])
      }

      if (seq !== _roomLoadSeq) return
      if (safeString(activeRoomId.value).trim() !== rid) return

      if (preserveExisting && previousItems.length) {
        room_store.setItems(mergeRoomEvents(previousItems, room_store.items))
      }

      if (preserveExisting) {
        _preserve_older_paging_state_after_recent_refresh(previousPaging)
      }

      if (!isReplayMode()) {
        await refreshRoomRuntimeEvents(buildStoreOptions({
          signal,
          room_id: rid,
          reset: !!normalizedOpts.reset_runtime || useBundleLoad,
          silent: normalizedOpts.runtime_silent === undefined ? preserveExisting : !!normalizedOpts.runtime_silent,
          includeallruns: normalizedOpts.includeallruns,
          force_current: true,
        }))
      }

      const currentRuntimeResultEvent = room_store.runtimeResultEvent
      const currentRuntimeResultEventId = getEventLikeId(currentRuntimeResultEvent)
      const currentRuntimeResultType = safeString(currentRuntimeResultEvent?.type).trim()

      const applied = applyRoomMessagesFromStore()
      const nextSignature = buildRenderedMessagesSignature(applied)
      const changed = nextSignature !== previousSignature

      if (
        !isReplayMode() &&
        currentRuntimeResultType === 'room.final' &&
        currentRuntimeResultEventId &&
        (
          currentRuntimeResultEventId !== previousRuntimeResultEventId ||
          previousRuntimeResultType !== 'room.final'
        )
      ) {
        shouldForceBottomAfterApply = true
        shouldExtendAutoFollow = true
      }

      if (shouldScrollBottom) {
        shouldForceBottomAfterApply = true
      } else if (changed && _should_room_auto_follow()) {
        shouldForceBottomAfterApply = true
        shouldExtendAutoFollow = true
      }
    } catch (e) {
      if (seq !== _roomLoadSeq) return

      if (isCancellationLikeError(e)) {
        _schedule_followup_load(rid, normalizedOpts)
        return
      }

      const existing = existingRenderableMessages()
      if (existing.length) {
        messages.value = existing
      } else {
        const errText = safeString(e?.message || e)
        messages.value = [{
          local_id: buildMessageLocalId('room_error'),
          role: 'assistant',
          sender: 'system',
          sender_type: 'system',
          content: errText,
          response: errText,
          status: 'error',
          message: errText,
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
    } finally {
      _roomLoadBusy = false
      _roomActiveLoadRid = ''

      if (shouldExtendAutoFollow) {
        _arm_room_auto_follow(90000)
      }

      if (shouldForceBottomAfterApply) {
        _perform_room_follow_scroll()
      }

      await _run_followup_load_if_needed()
    }
  }

  async function loadOlderRoomMessages(opts = {}) {
    const normalizedOpts = buildStoreOptions(opts)
    const rid = safeString(normalizedOpts.room_id || normalizedOpts.roomId || activeRoomId.value).trim()

    if (!rid) return safeArray(messages.value)
    if (chat_cfg.chat?.mode !== 'room') return safeArray(messages.value)
    if (_roomSwitchBusy || _roomPendingRid || _roomPaginationBusy) return safeArray(messages.value)
    if (!hasMoreOlder.value || loadingOlder.value) return safeArray(messages.value)

    _suspend_passive_refresh(4500)

    if (_roomLoadBusy) {
      await _wait_for_active_load_to_settle(1200)
    }

    if (_roomLoadBusy) {
      return safeArray(messages.value)
    }

    _roomPaginationBusy = true

    try {
      await room_store.loadOlderRoomItems(call_tool, rid, buildStoreOptions({
        limit: normalizedOpts.limit,
        cursor: normalizedOpts.cursor,
        beforeeventid: normalizedOpts.beforeeventid,
        bytebudget: normalizedOpts.bytebudget,
        relationexpand: normalizedOpts.relationexpand,
      }))

      if (safeString(activeRoomId.value).trim() !== rid) {
        return safeArray(messages.value)
      }

      applyRoomMessagesFromStore()
      _suspend_passive_refresh(4500)
      return safeArray(messages.value)
    } catch (e) {
      if (isCancellationLikeError(e)) {
        return safeArray(messages.value)
      }
      throw e
    } finally {
      _roomPaginationBusy = false
    }
  }

  function _toastRoomSwitchError(message) {
    try {
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: {
            message: safeString(message || '房间切换失败').trim() || '房间切换失败',
            type: 'error',
          },
        })
      )
    } catch {}
  }

  async function _ensureFederationContextBeforeRoomSwitch(nextRid) {
    const rid = safeString(nextRid).trim()
    if (!rid) {
      return {
        ok: false,
        code: 'room_id_required',
        message: 'room_id is required',
      }
    }

    if (typeof room_store?.ensureFederationContextForRoomId !== 'function') {
      return { ok: true, kind: 'unknown' }
    }

    const res = await room_store.ensureFederationContextForRoomId(call_tool, rid, {
      clearLocal: false,
    })

    if (res?.ok === false) {
      _toastRoomSwitchError(res.message || 'Federated room session 恢复失败，已停止切房。')
    }

    return res || { ok: true }
  }

  async function requestRoomSwitch(targetRid) {
    const rid = safeString(targetRid).trim()
    if (!rid) return

    _roomPendingRid = rid
    if (_roomSwitchBusy) return

    _roomSwitchBusy = true
    try {
      while (_roomPendingRid) {
        const nextRid = _roomPendingRid
        _roomPendingRid = ''

        const federationCtx = await _ensureFederationContextBeforeRoomSwitch(nextRid)
        if (federationCtx?.ok === false) {
          continue
        }

        _clear_room_passive_timer()
        clearRoomRuntimePoller()
        _roomLoadSeq++
        _roomReloadQueued = false
        _roomQueuedRid = ''
        _roomQueuedOpts = null
        _roomPaginationBusy = false
        _roomPassiveRefreshSuspendedUntil = 0
        _clear_room_auto_follow()

        try { _roomAbortCtrl?.abort() } catch {}

        room_store.setRoomId(nextRid)
        room_store.setItems([])
        room_store.resetItemsPaging()

        if (typeof room_store.resetRuntime === 'function') {
          room_store.resetRuntime({
            preserve_expanded: true,
            preserve_include_all_runs: true,
            preserve_order: true,
          })
        }

        if (typeof room_store.setRuntimeViewMode === 'function') {
          room_store.setRuntimeViewMode('current')
        }
        if (typeof room_store.resetRuntimeReplay === 'function') {
          room_store.resetRuntimeReplay({
            preserve_view_mode: true,
            preserve_selected_run: false,
          })
        }

        messages.value = [{
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

        await loadRoomMessages(nextRid, {
          force_abort: true,
          scroll_to_bottom: true,
          preserve_existing: false,
          use_bundle_load: true,
          reset_runtime: true,
          runtime_silent: false,
        })

        scheduleRoomPassiveRefresh(1400)
      }
    } finally {
      _roomSwitchBusy = false
    }
  }

  function handleVisibility() {
    const hidden = document.hidden

    if (hidden) {
      _clear_room_passive_timer()
      clearRoomRuntimePoller()
      try { _roomAbortCtrl?.abort() } catch {}
      return
    }

    if (chat_cfg.chat?.mode !== 'room') return
    if (!safeString(activeRoomId.value).trim()) return

    scheduleRoomPassiveRefresh(600)

    if (!isReplayMode() && shouldPollRoomRuntime()) {
      scheduleRoomRuntimePoll(600)
    }

    if (_can_run_passive_refresh()) {
      void loadRoomMessages(activeRoomId.value, {
        scroll_to_bottom: false,
        preserve_existing: true,
        runtime_silent: true,
      })
    }
  }

  function handleRoomRefreshRequest(event) {
    const currentRid = safeString(activeRoomId.value).trim()
    if (chat_cfg.chat?.mode !== 'room') return

    const targetRid = safeString(
      event?.detail?.room_id || event?.detail?.roomId || currentRid
    ).trim()

    if (!targetRid) return
    if (currentRid && targetRid !== currentRid) return

    _arm_room_auto_follow(180000)
    _suspend_passive_refresh(1200)

    if (isReplayMode()) {
      const snapshot = getCurrentRuntimeControlSnapshot()
      const runtimeState = normalizeRuntimeState(snapshot.runtimeState)

      const hasCurrentControl =
        ['running', 'pause_requested', 'waiting_checkpoint', 'resumed', 'interrupted'].includes(runtimeState) ||
        snapshot.canPauseCurrent ||
        snapshot.canResume ||
        !snapshot.canAcceptNewPrompt

      if (hasCurrentControl || is_thinking?.value) {
        void setRoomRuntimeViewMode('current', {
          room_id: targetRid,
          silent: false,
          reset_current: true,
        })
        return
      }

      void refreshRoomRuntimeReplay({
        room_id: targetRid,
        silent: false,
      })
      return
    }

    void loadRoomMessages(targetRid, {
      scroll_to_bottom: false,
      preserve_existing: true,
      force_abort: true,
      runtime_silent: false,
    })
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('nisb-room-refresh-request', handleRoomRefreshRequest)
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibility)
    window.removeEventListener('nisb-room-refresh-request', handleRoomRefreshRequest)
    stopRuntimeReader()
  })

  return {
    stopRuntimeReader,
    scheduleRoomPassiveRefresh,
    clearRoomRuntimePoller,
    shouldPollRoomRuntime,
    pollRoomRuntimeNow,
    scheduleRoomRuntimePoll,
    refreshRoomRuntimeEvents,
    refreshRoomRuntimeReplay,
    refreshRoomRuntime,
    nudgeRoomRuntimePolling,
    setRoomRuntimeViewMode,
    selectRoomRuntimeReplayRun,
    resetRoomRuntimeLane,
    loadRoomMessages,
    loadOlderRoomMessages,
    requestRoomSwitch,
  }
}

export default use_chat_panel_room_runtime_reader
