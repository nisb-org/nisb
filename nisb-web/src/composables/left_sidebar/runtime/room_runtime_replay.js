import {
  safeArray,
  safeObject,
  safeString,
  safeBoolean,
  normalizeToken,
  normalizeRuntimePayload,
  getRuntimeTimeText,
  readCandidateValue,
  truncateText,
} from './room_runtime_panel_shared'

export function isRuntimeProcessEvent(item) {
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

function deriveRuntimeResultEventFromItems(items) {
  const rows = safeArray(items)
  const finals = rows.filter((item) => safeString(item?.type).trim() === 'room.final')
  if (finals.length) return finals[finals.length - 1]

  const fallbacks = rows.filter((item) =>
    ['room.message', 'room.supervisor', 'room.error', 'room.abort', 'room.aborted'].includes(
      safeString(item?.type).trim()
    )
  )

  return fallbacks.length ? fallbacks[fallbacks.length - 1] : null
}

function getRuntimeRunIdFromItem(item) {
  return safeString(item?.run_id || item?.payload?.run_id).trim()
}

export function collectRuntimeRunOptions(roomStore) {
  const map = new Map()

  const pushCandidate = (runId, item = null, source = '') => {
    const rid = safeString(runId).trim()
    if (!rid) return

    const existing = safeObject(map.get(rid))
    const type = safeString(item?.type).trim()
    const timeText = getRuntimeTimeText(item)

    const rank =
      type === 'room.final'
        ? 5
        : type === 'room.error'
          ? 4
          : type === 'room.aborted'
            ? 4
            : type === 'room.abort'
              ? 4
              : type === 'room.message'
                ? 3
                : type === 'room.supervisor'
                  ? 3
                  : type === 'room.delegate'
                    ? 2
                    : type === 'room.plan'
                      ? 1
                      : 0

    map.set(rid, {
      value: rid,
      runId: rid,
      timeText: existing.timeText || timeText,
      rank: Math.max(Number(existing.rank || 0), rank),
      source: existing.source || source,
    })
  }

  const sourceLists = [
    safeArray(roomStore.items),
    safeArray(roomStore.runtime?.items),
    safeArray(roomStore.runtime?.replay_bundle?.items),
  ]

  sourceLists.forEach((list, listIdx) => {
    list.forEach((item) => {
      if (!isRuntimeProcessEvent(item)) return
      pushCandidate(getRuntimeRunIdFromItem(item), item, `list_${listIdx}`)
    })
  })

  pushCandidate(roomStore.runtime?.run_id, null, 'runtime')
  pushCandidate(roomStore.runtime?.selected_run_id, null, 'selected')
  pushCandidate(roomStore.roomState?.current_run_id, null, 'room_state')
  pushCandidate(roomStore.latestCompletedRunId, null, 'getter')

  return Array.from(map.values())
    .sort((a, b) => {
      if ((b.rank || 0) !== (a.rank || 0)) return (b.rank || 0) - (a.rank || 0)
      if ((b.timeText || '') !== (a.timeText || '')) {
        return (b.timeText || '').localeCompare(a.timeText || '')
      }
      return String(b.runId || '').localeCompare(String(a.runId || ''))
    })
    .map((item) => ({
      value: item.value,
      label: item.timeText ? `${item.runId} · ${item.timeText}` : item.runId,
    }))
}

export function pickReplayResultEvent(replayBundle, replayItems = []) {
  const bundle = safeObject(replayBundle)

  const directCandidates = [
    bundle.result_event,
    bundle.final_event,
    bundle.final_result_event,
    bundle.final_read_model,
    bundle.final,
    bundle.final_result,
    bundle.replay_read_model,
    bundle.audit_read_model,
    bundle.audit,
    bundle.result,
  ]

  for (const item of directCandidates) {
    const row = safeObject(item)
    if (Object.keys(row).length) return row
  }

  return deriveRuntimeResultEventFromItems(replayItems)
}

export function pickReplayFinalPayload(replayBundle) {
  const bundle = safeObject(replayBundle)

  const directCandidates = [
    bundle.final_read_model,
    bundle.final,
    bundle.final_result,
    bundle.replay_read_model,
    bundle.audit_read_model,
    bundle.audit,
    bundle.result_payload,
    bundle.result,
  ]

  for (const item of directCandidates) {
    const payload = normalizeRuntimePayload(item)
    if (Object.keys(payload).length) return payload
  }

  const events = safeArray(bundle.events)
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = safeObject(events[i])
    if (safeString(event.type).trim() !== 'room.final') continue
    const payload = normalizeRuntimePayload(event.payload || event)
    if (Object.keys(payload).length) return payload
  }

  const items = safeArray(bundle.items)
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = safeObject(items[i])
    if (safeString(item.type).trim() !== 'room.final') continue
    const payload = normalizeRuntimePayload(item.payload || item)
    if (Object.keys(payload).length) return payload
  }

  const phases = safeArray(bundle.phases)
  for (let i = phases.length - 1; i >= 0; i -= 1) {
    const phase = safeObject(phases[i])
    const payload = normalizeRuntimePayload(phase.payload || phase.result || phase.data)
    if (Object.keys(payload).length) return payload
  }

  return {}
}

export function normalizeRuntimeActionResponse(raw) {
  if (typeof raw === 'string') {
    const status = normalizeToken(raw)
    return {
      accepted: ['accepted', 'success', 'ok'].includes(status),
      status,
      message: safeString(raw).trim(),
    }
  }

  const src = safeObject(raw)
  const candidates = [
    src,
    safeObject(src.payload),
    safeObject(src.data),
    safeObject(src.result),
    normalizeRuntimePayload(src),
  ].filter((row) => Object.keys(row).length > 0)

  const status = normalizeToken(readCandidateValue(candidates, ['status', 'state']))
  const acceptedFlag = readCandidateValue(candidates, [
    'accepted',
    'success',
    'ok',
    'pause_requested',
    'resume_started',
    'resume_accepted',
  ])
  const message = safeString(
    readCandidateValue(candidates, ['message', 'detail', 'status_text', 'text'])
  ).trim()

  return {
    accepted: safeBoolean(acceptedFlag, false) || ['accepted', 'success', 'ok'].includes(status),
    status,
    message,
  }
}

function mapRuntimeEventTypeClass(type) {
  const token = safeString(type).trim()
  if (token === 'room.final') return 'final'
  if (['room.error', 'room.abort', 'room.aborted'].includes(token)) return 'error'
  if (['room.route', 'room.delegate'].includes(token)) return 'route'
  if (token === 'room.supervisor') return 'supervisor'
  if (token === 'room.plan') return 'plan'
  return 'message'
}

export function readRunIdSelectionInput(input) {
  if (typeof input === 'string' || typeof input === 'number') {
    return safeString(input).trim()
  }

  const row = safeObject(input)
  return safeString(
    row.target?.value ||
      row.detail?.run_id ||
      row.detail?.runId ||
      row.run_id ||
      row.runId ||
      row.value
  ).trim()
}

export function buildFallbackRuntimeResultEntry({
  t,
  viewMode,
  baseEntry,
  headline,
  summaryText,
  resultText,
  resultPayload,
  resultEvent,
}) {
  const fallback = safeObject(baseEntry)
  if (Object.keys(fallback).length) {
    return {
      ...fallback,
      title:
        safeString(fallback.title).trim() ||
        safeString(headline).trim() ||
        t(viewMode === 'replay' ? 'runtime.card.defaultHeadline.replay' : 'runtime.card.defaultHeadline.current'),
      summary: safeString(fallback.summary).trim() || safeString(summaryText).trim(),
    }
  }

  const payload = normalizeRuntimePayload(resultPayload)
  const event = safeObject(resultEvent)
  const type = safeString(event.type).trim()

  const text = safeString(
    resultText ||
      payload.response ||
      payload.content ||
      payload.message ||
      payload.detail ||
      payload.error
  ).trim()

  const summary = safeString(summaryText).trim() || truncateText(text, 320)
  const title =
    safeString(headline).trim() ||
    t(viewMode === 'replay' ? 'runtime.card.defaultHeadline.replay' : 'runtime.card.defaultHeadline.current')

  if (!title && !summary && !Object.keys(payload).length && !Object.keys(event).length) return null

  const badge =
    type === 'room.final'
      ? t('runtime.timeline.badges.final')
      : type === 'room.error'
        ? t('runtime.timeline.badges.error')
        : type === 'room.abort' || type === 'room.aborted'
          ? t('runtime.timeline.badges.aborted')
          : viewMode === 'replay'
            ? t('runtime.card.badges.replay')
            : t('runtime.timeline.badges.runtime')

  return {
    id: safeString(event.id || event.event_id || '').trim() || `${viewMode}-${badge}-${title}`,
    type: type || (viewMode === 'replay' ? 'room.final' : 'room.message'),
    typeClass: mapRuntimeEventTypeClass(type || (viewMode === 'replay' ? 'room.final' : 'room.message')),
    badge,
    title,
    summary,
  }
}

export function pickReplayAvailableRuns(runtimeBase, bundle) {
  const directLists = [
    safeArray(bundle?.available_runs),
    safeArray(runtimeBase?.replay_available_runs),
    safeArray(runtimeBase?.available_runs),
  ]

  for (const list of directLists) {
    if (list.length) return list
  }

  const mapCandidates = [
    safeObject(runtimeBase?.replay_by_run_id),
    safeObject(runtimeBase?.replayByRunId),
    safeObject(runtimeBase?.replay_results_by_run_id),
    safeObject(runtimeBase?.replayResultsByRunId),
    safeObject(runtimeBase?.replay_bundle_by_run_id),
    safeObject(runtimeBase?.replayBundleByRunId),
  ]

  for (const map of mapCandidates) {
    const keys = Object.keys(map)
    if (!keys.length) continue
    return keys.map((key) => ({ run_id: key }))
  }

  return []
}

function filterRuntimeItemsByRun(items, runId) {
  const rid = safeString(runId).trim()
  if (!rid) return safeArray(items)
  return safeArray(items).filter(
    (item) => isRuntimeProcessEvent(item) && getRuntimeRunIdFromItem(item) === rid
  )
}

export function resolveReplayBundleForRun(runtimeBase, runId, roomStore) {
  const runtime = safeObject(runtimeBase)
  const rid = safeString(runId).trim()

  const byRunMaps = [
    safeObject(runtime.replay_by_run_id),
    safeObject(runtime.replayByRunId),
    safeObject(runtime.replay_results_by_run_id),
    safeObject(runtime.replayResultsByRunId),
    safeObject(runtime.replay_bundle_by_run_id),
    safeObject(runtime.replayBundleByRunId),
    safeObject(roomStore?.runtime?.replay_by_run_id),
    safeObject(roomStore?.runtime?.replayByRunId),
  ]

  if (rid) {
    for (const map of byRunMaps) {
      const candidate = safeObject(map[rid])
      if (Object.keys(candidate).length) return candidate
    }
  }

  const bundleCandidates = [
    safeObject(runtime.replay_bundle),
    safeObject(roomStore?.runtime?.replay_bundle),
  ]

  for (const bundle of bundleCandidates) {
    if (!Object.keys(bundle).length) continue

    const bundleRunId = safeString(
      bundle.run_id || bundle.selected_run_id || bundle.target_run_id
    ).trim()

    if (!rid || !bundleRunId || bundleRunId === rid) return bundle

    const matchedItems = filterRuntimeItemsByRun(bundle.items, rid)
    const matchedEvents = filterRuntimeItemsByRun(bundle.events, rid)

    if (matchedItems.length || matchedEvents.length) {
      return {
        ...bundle,
        run_id: rid,
        items: matchedItems.length ? matchedItems : safeArray(bundle.items),
        events: matchedEvents.length ? matchedEvents : safeArray(bundle.events),
      }
    }
  }

  if (rid) {
    const runtimeItems =
      filterRuntimeItemsByRun(runtime.items, rid).length
        ? filterRuntimeItemsByRun(runtime.items, rid)
        : filterRuntimeItemsByRun(roomStore?.items, rid)

    if (runtimeItems.length) {
      return {
        run_id: rid,
        items: runtimeItems,
      }
    }
  }

  return {}
}

