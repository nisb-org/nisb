import {
  safeArray,
  safeObject,
  safeString,
  safeBoolean,
  normalizeToken,
  readCandidateRaw,
  readCandidateString,
  readCandidateBoolean,
  readCandidateNumber,
  readCandidateArray,
  preferDefined,
  humanizeToken,
  truncateText,
  toSentence,
  pushUniquePart,
  formatStage,
} from './room_runtime_panel_shared'
import { pickReplayFinalPayload } from './room_runtime_replay'

export function normalizeContinuationMode(value) {
  const token = normalizeToken(value)
  if (['fresh', 'resumed', 'restart_fresh'].includes(token)) return token
  if (token === 'resume') return 'resumed'
  if (token === 'new' || token === 'initial') return 'fresh'
  return ''
}

export function normalizeRuntimeState(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'completed after resume') return 'completed_after_resume'
  if (token === 'budget exhausted') return 'budget_exhausted'
  if (token === 'step_budget_exhausted' || token === 'exhausted') return 'budget_exhausted'
  if (token === 'pause requested') return 'pause_requested'
  if (token === 'waiting checkpoint') return 'waiting_checkpoint'
  return token.replace(/\s+/g, '_')
}

export function normalizeContinuationStatus(value) {
  const token = normalizeRuntimeState(value)
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
    return token === 'waiting_checkpoint' ? 'pause_requested' : token
  }
  return ''
}

export function isTerminalContinuationStatus(status) {
  return ['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(
    normalizeContinuationStatus(status)
  )
}

function formatContinuationModeLabel(t, value) {
  const token = normalizeContinuationMode(value)
  if (token === 'resumed') return t('runtime.timeline.mode.resumed')
  if (token === 'restart_fresh') return t('runtime.timeline.mode.restartFresh')
  if (token === 'fresh') return t('runtime.timeline.mode.fresh')
  return humanizeToken(token)
}

function formatContinuationStatusLabel(t, status, runtimePhase = '') {
  const token = normalizeContinuationStatus(status)
  const phase = normalizeRuntimeState(runtimePhase)

  if (phase === 'waiting_checkpoint') return t('runtime.timeline.badges.waitingCheckpoint')
  if (token === 'pause_requested') return t('runtime.card.status.pauseRequested')
  if (token === 'interrupted') return t('runtime.card.status.interrupted')
  if (token === 'resumed') return t('runtime.card.status.resumed')
  if (token === 'completed_after_resume') return t('runtime.card.status.completedAfterResume')
  if (token === 'completed') return t('runtime.card.status.completed')
  if (token === 'budget_exhausted') return t('runtime.card.status.budgetExhausted')
  if (token === 'running') return t('runtime.card.status.running')
  return humanizeToken(token)
}

export function formatContinuationStatusText(t, status, runtimePhase = '') {
  const token = normalizeContinuationStatus(status)
  const phase = normalizeRuntimeState(runtimePhase)

  if (phase === 'waiting_checkpoint') return t('runtime.timeline.status.waitingCheckpoint')
  if (token === 'pause_requested') return t('runtime.card.status.pauseRequested')
  if (token === 'interrupted') return t('runtime.card.status.interrupted')
  if (token === 'resumed') return t('runtime.card.status.resumed')
  if (token === 'completed_after_resume') return t('runtime.card.status.completedAfterResume')
  if (token === 'completed') return t('runtime.card.status.completed')
  if (token === 'budget_exhausted') return t('runtime.card.status.budgetExhausted')
  if (token === 'running') return t('runtime.card.status.running')
  return ''
}

function formatInterruptionReason(t, reason) {
  const token = normalizeToken(reason)
  if (!token) return ''
  if (token === 'pause_requested') return t('runtime.card.reason.pauseRequested')
  if (token === 'manual_pause') return t('runtime.card.reason.pauseRequested')
  if (token === 'step_budget_exhausted' || token === 'budget_exhausted') {
    return t('runtime.card.reason.stepBudgetExhausted')
  }
  if (token === 'new_topic_detected') return t('runtime.card.reason.newTopicDetected')
  if (token === 'checkpoint_missing') return t('runtime.card.reason.checkpointMissing')
  return humanizeToken(token)
}

function mapContinuationTypeClass(status) {
  const token = normalizeContinuationStatus(status)
  if (token === 'interrupted' || token === 'budget_exhausted') return 'error'
  if (token === 'completed' || token === 'completed_after_resume') return 'final'
  if (token === 'pause_requested') return 'message'
  if (token === 'resumed') return 'route'
  if (token === 'running') return 'supervisor'
  return 'message'
}

function summarizeEffectDispositions(t, effectDispositions, skippedEffects) {
  const rows = safeArray(effectDispositions)
  const counts = rows.reduce((acc, item) => {
    const key = normalizeToken(item?.disposition || item?.status || item?.action || item?.effect_disposition)
    if (!key) return acc
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const skippedCount = counts.skip || safeArray(skippedEffects).length || 0
  const reuseCount = counts.reuse || 0
  const executeCount = counts.execute || 0
  const repairCount = counts.repair || counts.reconcile || 0
  const totalCount = rows.length || skippedCount

  let effectSummary = ''

  if (skippedCount > 0 && totalCount === skippedCount) {
    effectSummary = t('runtime.timeline.effects.allSkipped', { count: skippedCount })
  } else if (totalCount > 0) {
    const parts = []
    if (skippedCount > 0) parts.push(t('runtime.timeline.effects.skipCount', { count: skippedCount }))
    if (reuseCount > 0) parts.push(t('runtime.timeline.effects.reuseCount', { count: reuseCount }))
    if (executeCount > 0) parts.push(t('runtime.timeline.effects.executeCount', { count: executeCount }))
    if (repairCount > 0) parts.push(t('runtime.timeline.effects.repairCount', { count: repairCount }))
    effectSummary = parts.length
      ? t('runtime.timeline.effects.summaryDisposition', { items: parts.join('，') })
      : t('runtime.timeline.effects.recorded', { count: totalCount })
  }

  return {
    skippedCount,
    effectSummary,
  }
}

function hasRuntimeControlContent(snapshot) {
  const row = safeObject(snapshot)
  return Object.keys(row).some((key) => row[key] !== undefined && row[key] !== null && row[key] !== '')
}

export function normalizeRuntimeControlSnapshot(raw) {
  const src = safeObject(raw)
  const candidates = [
    src,
    safeObject(src.runtime_control_snapshot),
    safeObject(src.control_snapshot),
  ].filter((row) => Object.keys(row).length > 0)

  const runtimeState = normalizeRuntimeState(
    readCandidateRaw(candidates, ['runtime_state', 'runtimeState', 'state'])
  )
  const runtimePhase = normalizeRuntimeState(
    readCandidateRaw(candidates, ['runtime_phase', 'runtimePhase', 'phase'])
  )
  const currentRunStatus = normalizeRuntimeState(
    readCandidateRaw(candidates, ['current_run_status', 'currentRunStatus'])
  )
  const continuationMode = normalizeContinuationMode(
    readCandidateRaw(candidates, ['continuation_mode', 'continuationMode'])
  )
  const continuationStatus = normalizeContinuationStatus(
    readCandidateRaw(candidates, ['continuation_status', 'continuationStatus'])
  )

  const pauseRequested = readCandidateBoolean(candidates, ['pause_requested', 'pauseRequested'])
  const pauseRequestAccepted = readCandidateBoolean(candidates, ['pause_request_accepted', 'pauseRequestAccepted'])
  const pauseReason = readCandidateString(candidates, ['pause_reason', 'pauseReason'])
  const pauseRequestedAt = readCandidateString(candidates, ['pause_requested_at', 'pauseRequestedAt'])
  const pauseEffective = readCandidateBoolean(candidates, ['pause_effective', 'pauseEffective'])
  const pausedAt = readCandidateString(candidates, ['paused_at', 'pausedAt'])
  const pauseEffectiveAt = readCandidateString(candidates, ['pause_effective_at', 'pauseEffectiveAt'])

  const resumeReady = readCandidateBoolean(candidates, ['resume_ready', 'resumeReady'])
  const resumeFromCheckpoint = readCandidateBoolean(candidates, ['resume_from_checkpoint', 'resumeFromCheckpoint'])
  const resumeCheckpointRef = readCandidateString(candidates, ['resume_checkpoint_ref', 'resumeCheckpointRef'])
  const resumeToken = readCandidateString(candidates, ['resume_token', 'resumeToken'])
  const resumeReason = readCandidateString(candidates, ['resume_reason', 'resumeReason'])
  const errorBlockingResume = readCandidateBoolean(candidates, ['error_blocking_resume', 'errorBlockingResume'])

  const canAcceptNewPrompt = readCandidateBoolean(candidates, ['can_accept_new_prompt', 'canAcceptNewPrompt'])
  const controlBlockReason = readCandidateString(candidates, ['control_block_reason', 'controlBlockReason'])
  const canPauseCurrent = readCandidateBoolean(candidates, ['can_pause_current', 'canPauseCurrent'])
  const canResume = readCandidateBoolean(candidates, ['can_resume', 'canResume'])

  const resumedFromRunId = readCandidateString(candidates, ['resumed_from_run_id', 'resumedFromRunId'])
  const resumedFromEventId = readCandidateString(candidates, ['resumed_from_event_id', 'resumedFromEventId'])
  const resumedFromStage = readCandidateString(candidates, ['resumed_from_stage', 'resumedFromStage'])
  const checkpointStage = readCandidateString(candidates, ['checkpoint_stage', 'checkpointStage'])
  const checkpointSummary = readCandidateString(candidates, ['checkpoint_summary', 'checkpointSummary'])
  const interruptionReason = readCandidateString(candidates, ['interruption_reason', 'interruptionReason'])
  const lastCompletedStep = readCandidateString(candidates, ['last_completed_step', 'lastCompletedStep'])

  const skippedEffects = readCandidateArray(candidates, ['skipped_effects', 'skippedEffects'])
  const effectDispositions = readCandidateArray(candidates, ['effect_dispositions', 'effectDispositions'])

  const stepBudgetTotal = readCandidateNumber(candidates, ['step_budget_total', 'stepBudgetTotal'])
  const stepBudgetUsed = readCandidateNumber(candidates, ['step_budget_used', 'stepBudgetUsed'])
  const stepBudgetRemaining = readCandidateNumber(candidates, ['step_budget_remaining', 'stepBudgetRemaining'])

  const budgetStatus = normalizeRuntimeState(
    readCandidateRaw(candidates, ['budget_status', 'budgetStatus'])
  )
  const budgetExhausted = readCandidateBoolean(candidates, ['budget_exhausted', 'budgetExhausted'])

  return {
    runtimeState,
    runtimePhase,
    currentRunStatus,
    canAcceptNewPrompt,
    controlBlockReason,
    pauseRequested,
    pauseRequestAccepted,
    pauseReason,
    pauseRequestedAt,
    pauseEffective,
    pausedAt,
    pauseEffectiveAt,
    resumeReady,
    resumeFromCheckpoint,
    resumeCheckpointRef,
    resumeToken,
    resumeReason,
    errorBlockingResume,
    continuationMode,
    continuationStatus,
    resumedFromRunId,
    resumedFromEventId,
    resumedFromStage,
    checkpointStage,
    checkpointSummary,
    interruptionReason,
    lastCompletedStep,
    skippedEffects,
    effectDispositions,
    stepBudgetTotal,
    stepBudgetUsed,
    stepBudgetRemaining,
    budgetStatus,
    budgetExhausted,
    canPauseCurrent,
    canResume,
  }
}

function deriveContinuationStatus({
  runtimeState,
  explicitStatus,
  currentRunStatus,
  payloadStatus,
  live,
  pauseRequested,
  budgetExhausted,
  budgetStatus,
  continuationMode,
}) {
  if (explicitStatus) return explicitStatus

  const normalizedRuntimeState = normalizeRuntimeState(runtimeState)
  if (normalizedRuntimeState === 'waiting_checkpoint') return 'pause_requested'
  if (normalizeContinuationStatus(normalizedRuntimeState)) {
    return normalizeContinuationStatus(normalizedRuntimeState)
  }

  if (
    budgetExhausted ||
    budgetStatus === 'budget_exhausted' ||
    currentRunStatus === 'budget_exhausted' ||
    payloadStatus === 'budget_exhausted'
  ) {
    return 'budget_exhausted'
  }

  if (currentRunStatus === 'interrupted' || payloadStatus === 'interrupted') return 'interrupted'
  if (payloadStatus === 'success') {
    return continuationMode === 'resumed' ? 'completed_after_resume' : 'completed'
  }
  if (pauseRequested && live) return 'pause_requested'
  if (continuationMode === 'resumed' && live) return 'resumed'
  if (live || currentRunStatus === 'running') return 'running'
  return ''
}

export function normalizeContinuationRuntime({
  controlSnapshot,
  roomState,
  resultPayload,
  resultEvent,
  replayBundle,
  live,
  latestStage,
  t,
}) {
  const normalizedControl = normalizeRuntimeControlSnapshot(controlSnapshot)
  const stateRow = safeObject(roomState)
  const payloadRow = safeObject(resultPayload)
  const finalPayloadRow = pickReplayFinalPayload(replayBundle)
  const eventRow = safeObject(resultEvent?.payload || resultEvent)

  const displayCandidates = [
    normalizedControl,
    stateRow,
    payloadRow,
    finalPayloadRow,
    eventRow,
  ].filter((row) => Object.keys(safeObject(row)).length > 0)

  const explicitMode =
    normalizedControl.continuationMode ||
    normalizeContinuationMode(
      readCandidateRaw(displayCandidates, ['continuation_mode', 'last_supervisor_continuation_mode'])
    )

  const explicitStatus =
    normalizedControl.continuationStatus ||
    normalizeContinuationStatus(
      readCandidateRaw(displayCandidates, ['continuation_status', 'last_supervisor_continuation_status'])
    )

  const runtimeState = normalizedControl.runtimeState
  const runtimePhase = normalizedControl.runtimePhase
  const currentRunStatus =
    normalizedControl.currentRunStatus ||
    normalizeRuntimeState(
      readCandidateRaw(displayCandidates, ['current_run_status', 'last_supervisor_status'])
    )

  const pauseRequested = preferDefined(
    normalizedControl.pauseRequested,
    safeBoolean(
      readCandidateRaw(displayCandidates, ['pause_requested', 'last_supervisor_pause_requested']),
      false
    )
  ) || runtimeState === 'pause_requested' || runtimeState === 'waiting_checkpoint'

  const pauseRequestAccepted = preferDefined(
    normalizedControl.pauseRequestAccepted,
    safeBoolean(readCandidateRaw(displayCandidates, ['pause_request_accepted']), false)
  )

  const pauseReason =
    normalizedControl.pauseReason ||
    safeString(
      readCandidateRaw(displayCandidates, ['pause_reason', 'last_supervisor_pause_reason'])
    ).trim()

  const pauseRequestedAt =
    normalizedControl.pauseRequestedAt ||
    safeString(readCandidateRaw(displayCandidates, ['pause_requested_at'])).trim()

  const pauseEffective = preferDefined(
    normalizedControl.pauseEffective,
    safeBoolean(readCandidateRaw(displayCandidates, ['pause_effective']), false)
  )

  const pausedAt =
    normalizedControl.pausedAt ||
    safeString(
      readCandidateRaw(displayCandidates, ['paused_at', 'last_supervisor_paused_at'])
    ).trim()

  const pauseEffectiveAt =
    normalizedControl.pauseEffectiveAt ||
    safeString(readCandidateRaw(displayCandidates, ['pause_effective_at'])).trim()

  let interruptionReason =
    normalizedControl.interruptionReason ||
    safeString(readCandidateRaw(displayCandidates, ['interruption_reason'])).trim()

  const resumeReady = preferDefined(
    normalizedControl.resumeReady,
    safeBoolean(readCandidateRaw(displayCandidates, ['resume_ready']), false)
  )

  const resumeFromCheckpoint = preferDefined(
    normalizedControl.resumeFromCheckpoint,
    safeBoolean(
      readCandidateRaw(displayCandidates, [
        'resume_from_checkpoint',
        'last_supervisor_resume_from_checkpoint',
      ]),
      false
    )
  )

  const resumeCheckpointRef =
    normalizedControl.resumeCheckpointRef ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'resume_checkpoint_ref',
        'last_supervisor_resume_checkpoint_ref',
      ])
    ).trim()

  const resumeToken =
    normalizedControl.resumeToken ||
    safeString(readCandidateRaw(displayCandidates, ['resume_token'])).trim()

  const resumeReason =
    normalizedControl.resumeReason ||
    safeString(readCandidateRaw(displayCandidates, ['resume_reason'])).trim()

  const errorBlockingResume = preferDefined(
    normalizedControl.errorBlockingResume,
    safeBoolean(readCandidateRaw(displayCandidates, ['error_blocking_resume']), false)
  )

  const canAcceptNewPrompt = preferDefined(
    normalizedControl.canAcceptNewPrompt,
    safeBoolean(readCandidateRaw(displayCandidates, ['can_accept_new_prompt']), false)
  )

  const controlBlockReason =
    normalizedControl.controlBlockReason ||
    safeString(readCandidateRaw(displayCandidates, ['control_block_reason'])).trim()

  const resumedFromRunId =
    normalizedControl.resumedFromRunId ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'resumed_from_run_id',
        'last_supervisor_resumed_from_run_id',
      ])
    ).trim()

  const resumedFromEventId =
    normalizedControl.resumedFromEventId ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'resumed_from_event_id',
        'last_supervisor_resumed_from_event_id',
      ])
    ).trim()

  const resumedFromStage =
    normalizedControl.resumedFromStage ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'resumed_from_stage',
        'last_supervisor_resumed_from_stage',
        'last_supervisor_memory_resume_checkpoint_stage',
      ])
    ).trim()

  let checkpointStage =
    normalizedControl.checkpointStage ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'checkpoint_stage',
        'last_supervisor_phase',
        'last_supervisor_memory_checkpoint_stage',
        'last_supervisor_memory_resume_checkpoint_stage',
        'last_supervisor_memory_write_checkpoint_stage',
      ])
    ).trim()

  let checkpointSummary =
    normalizedControl.checkpointSummary ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'checkpoint_summary',
        'last_supervisor_memory_checkpoint_summary',
        'last_supervisor_memory_resume_checkpoint_summary',
        'last_supervisor_memory_write_checkpoint_summary',
      ])
    ).trim()

  const lastCompletedStep =
    normalizedControl.lastCompletedStep ||
    safeString(
      readCandidateRaw(displayCandidates, [
        'last_completed_step',
        'last_supervisor_last_completed_step',
      ])
    ).trim()

  const skippedEffects =
    normalizedControl.skippedEffects.length
      ? normalizedControl.skippedEffects
      : safeArray(
          readCandidateRaw(displayCandidates, ['skipped_effects', 'last_supervisor_skipped_effects'])
        )

  const effectDispositions =
    normalizedControl.effectDispositions.length
      ? normalizedControl.effectDispositions
      : safeArray(
          readCandidateRaw(displayCandidates, [
            'effect_dispositions',
            'last_supervisor_effect_dispositions',
          ])
        )

  const stepBudgetTotal = preferDefined(
    normalizedControl.stepBudgetTotal,
    readCandidateNumber(displayCandidates, ['step_budget_total'])
  )

  const stepBudgetUsed = preferDefined(
    normalizedControl.stepBudgetUsed,
    readCandidateNumber(displayCandidates, ['step_budget_used'])
  )

  const stepBudgetRemaining = preferDefined(
    normalizedControl.stepBudgetRemaining,
    readCandidateNumber(displayCandidates, ['step_budget_remaining'])
  )

  const budgetStatus =
    normalizedControl.budgetStatus ||
    normalizeRuntimeState(readCandidateRaw(displayCandidates, ['budget_status']))

  const budgetExhausted = preferDefined(
    normalizedControl.budgetExhausted,
    safeBoolean(readCandidateRaw(displayCandidates, ['budget_exhausted']), false)
  )

  const canPauseCurrent = preferDefined(
    normalizedControl.canPauseCurrent,
    safeBoolean(readCandidateRaw(displayCandidates, ['can_pause_current']), false)
  )

  const canResume = preferDefined(
    normalizedControl.canResume,
    safeBoolean(readCandidateRaw(displayCandidates, ['can_resume']), false)
  )

  if ((budgetExhausted || budgetStatus === 'budget_exhausted') && !interruptionReason) {
    interruptionReason = 'step_budget_exhausted'
  }

  const payloadStatus = normalizeRuntimeState(
    payloadRow.status || finalPayloadRow.status || eventRow.status
  )

  const hasResumeLineage = !!(resumedFromRunId || resumedFromEventId || resumedFromStage)

  const hasResumeMarkers = !!(
    resumeFromCheckpoint ||
    resumeCheckpointRef ||
    resumeToken ||
    hasResumeLineage ||
    resumeReady ||
    canResume
  )

  const hasControlTruth = hasRuntimeControlContent(normalizedControl)

  const hasRuntimeHints = !!(
    hasControlTruth ||
    explicitMode ||
    explicitStatus ||
    payloadStatus ||
    currentRunStatus ||
    hasResumeMarkers ||
    pauseRequested ||
    pauseRequestAccepted ||
    pauseReason ||
    pauseRequestedAt ||
    pausedAt ||
    pauseEffectiveAt ||
    interruptionReason ||
    checkpointStage ||
    checkpointSummary ||
    lastCompletedStep ||
    skippedEffects.length ||
    effectDispositions.length ||
    (stepBudgetTotal ?? 0) > 0 ||
    (stepBudgetUsed ?? 0) > 0 ||
    (stepBudgetRemaining ?? 0) > 0 ||
    budgetStatus ||
    budgetExhausted ||
    safeString(latestStage).trim() ||
    live
  )

  let continuationMode = explicitMode || ''

  const tentativeStatus = deriveContinuationStatus({
    runtimeState,
    explicitStatus,
    currentRunStatus,
    payloadStatus,
    live,
    pauseRequested,
    budgetExhausted,
    budgetStatus,
    continuationMode,
  })

  if (!continuationMode && hasResumeLineage && ['resumed', 'completed_after_resume'].includes(tentativeStatus)) {
    continuationMode = 'resumed'
  }

  const continuationStatus = deriveContinuationStatus({
    runtimeState,
    explicitStatus,
    currentRunStatus,
    payloadStatus,
    live,
    pauseRequested,
    budgetExhausted,
    budgetStatus,
    continuationMode,
  })

  if (!checkpointStage) checkpointStage = safeString(latestStage).trim()

  if (!checkpointSummary && continuationStatus === 'completed' && payloadRow.message) {
    checkpointSummary = safeString(payloadRow.message).trim()
  }

  const effectStats = summarizeEffectDispositions(t, effectDispositions, skippedEffects)

  return {
    hasContinuation: hasRuntimeHints,
    hasControlTruth,
    runtimeState,
    runtimePhase,
    currentRunStatus,
    canAcceptNewPrompt,
    controlBlockReason,
    pauseRequested,
    pauseRequestAccepted,
    pauseReason,
    pauseRequestedAt,
    pauseEffective,
    pausedAt,
    pauseEffectiveAt,
    interruptionReason,
    resumeReady,
    resumeFromCheckpoint,
    resumeCheckpointRef,
    resumeToken,
    resumeReason,
    errorBlockingResume,
    continuationMode,
    continuationStatus,
    resumedFromRunId,
    resumedFromEventId,
    resumedFromStage,
    lastCompletedStep,
    checkpointStage,
    checkpointSummary,
    skippedEffects,
    effectDispositions,
    stepBudgetTotal: stepBudgetTotal ?? 0,
    stepBudgetUsed: stepBudgetUsed ?? 0,
    stepBudgetRemaining: stepBudgetRemaining ?? 0,
    budgetStatus,
    budgetExhausted: !!budgetExhausted,
    canPauseCurrent: canPauseCurrent === true,
    canResume: canResume === true,
    skippedEffectCount: effectStats.skippedCount,
    effectSummary: effectStats.effectSummary,
  }
}

export function buildContinuationHeadline(t, runtime, fallbackHeadline = '') {
  const status = runtime.continuationStatus
  const phase = normalizeRuntimeState(runtime.runtimePhase)

  if (status === 'interrupted') return t('runtime.card.headline.interrupted')
  if (phase === 'waiting_checkpoint') return t('runtime.timeline.headline.waitingCheckpoint')
  if (status === 'pause_requested') return t('runtime.card.headline.pauseRequested')
  if (status === 'completed_after_resume') return t('runtime.card.headline.completedAfterResume')
  if (status === 'completed') return t('runtime.card.headline.completed')
  if (status === 'budget_exhausted') return t('runtime.card.headline.budgetExhausted')
  if (status === 'resumed') return t('runtime.card.headline.resumed')
  if (status === 'running') return t('runtime.card.headline.running')
  if (runtime.continuationMode === 'resumed') return t('runtime.card.headline.lineageResumed')
  if (runtime.continuationMode === 'restart_fresh') return t('runtime.card.headline.restartFresh')
  if (runtime.continuationMode === 'fresh') return fallbackHeadline || t('runtime.card.defaultHeadline.current')
  return fallbackHeadline || t('runtime.card.defaultHeadline.current')
}

export function buildContinuationBadgeParts(t, runtime) {
  const parts = []

  if (runtime.continuationMode) {
    pushUniquePart(parts, formatContinuationModeLabel(t, runtime.continuationMode))
  }

  if (runtime.runtimePhase === 'waiting_checkpoint') {
    pushUniquePart(parts, t('runtime.timeline.badges.waitingCheckpoint'))
  } else if (runtime.continuationStatus && runtime.continuationStatus !== 'running') {
    pushUniquePart(parts, formatContinuationStatusLabel(t, runtime.continuationStatus, runtime.runtimePhase))
  }

  if (runtime.canResume) {
    pushUniquePart(parts, t('runtime.timeline.badges.resumable'))
  }

  if (runtime.continuationStatus === 'completed_after_resume' && runtime.resumedFromStage) {
    pushUniquePart(
      parts,
      t('runtime.timeline.badges.fromStage', { stage: formatStage(runtime.resumedFromStage) })
    )
  }

  if (
    runtime.checkpointStage &&
    !['completed', 'completed_after_resume'].includes(runtime.continuationStatus)
  ) {
    pushUniquePart(
      parts,
      t('runtime.timeline.badges.checkpointStage', { stage: formatStage(runtime.checkpointStage) })
    )
  }

  if (runtime.skippedEffectCount > 0) {
    pushUniquePart(
      parts,
      t('runtime.timeline.badges.skippedEffects', { count: runtime.skippedEffectCount })
    )
  }

  if (
    runtime.continuationStatus === 'budget_exhausted' ||
    runtime.interruptionReason === 'step_budget_exhausted' ||
    runtime.budgetStatus === 'budget_exhausted'
  ) {
    pushUniquePart(parts, t('runtime.timeline.badges.budgetExhausted'))
  }

  return parts
}

export function buildContinuationSummary(t, runtime) {
  if (!runtime.hasContinuation) return ''

  const parts = []
  const stageText = formatStage(runtime.checkpointStage)
  const resumedStageText = formatStage(runtime.resumedFromStage)
  const reasonText = formatInterruptionReason(t, runtime.interruptionReason)
  const checkpointSummary = truncateText(runtime.checkpointSummary, 220)
  const effectSummary = runtime.effectSummary
  const phase = normalizeRuntimeState(runtime.runtimePhase)

  if (runtime.continuationStatus === 'interrupted') {
    if (stageText && reasonText) {
      parts.push(t('runtime.timeline.summary.interruptedAtStageWithReason', { stage: stageText, reason: reasonText }))
    } else if (stageText) {
      parts.push(t('runtime.timeline.summary.interruptedAtStage', { stage: stageText }))
    } else if (reasonText) {
      parts.push(t('runtime.timeline.summary.interruptedWithReason', { reason: reasonText }))
    } else {
      parts.push(t('runtime.timeline.summary.interrupted'))
    }

    if (runtime.canResume) {
      parts.push(t('runtime.timeline.summary.canResume'))
    }

    if (checkpointSummary) parts.push(toSentence(checkpointSummary))
    if (effectSummary) parts.push(toSentence(effectSummary))
    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'budget_exhausted') {
    if (stageText) {
      parts.push(t('runtime.timeline.summary.budgetStoppedAtStage', { stage: stageText }))
    } else {
      parts.push(t('runtime.timeline.summary.budgetStopped'))
    }

    if (checkpointSummary) parts.push(toSentence(checkpointSummary))
    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'pause_requested') {
    if (phase === 'waiting_checkpoint') {
      if (stageText) {
        parts.push(t('runtime.timeline.summary.pauseWaitingStage', { stage: stageText }))
      } else {
        parts.push(t('runtime.timeline.summary.pauseWaiting'))
      }
    } else if (stageText) {
      parts.push(t('runtime.timeline.summary.pauseWillStopAtStage', { stage: stageText }))
    } else {
      parts.push(t('runtime.timeline.summary.pauseWillStop'))
    }

    if (runtime.pauseReason && normalizeToken(runtime.pauseReason) !== 'pause_requested') {
      parts.push(t('runtime.timeline.summary.pauseReason', { reason: runtime.pauseReason }))
    } else if (checkpointSummary) {
      parts.push(toSentence(checkpointSummary))
    }

    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'completed_after_resume') {
    if (resumedStageText) {
      parts.push(t('runtime.timeline.summary.completedAfterResumeFromStage', { stage: resumedStageText }))
    } else {
      parts.push(t('runtime.timeline.summary.completedAfterResume'))
    }

    if (effectSummary) parts.push(toSentence(effectSummary))
    if (checkpointSummary) parts.push(toSentence(checkpointSummary))
    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'completed') {
    parts.push(
      runtime.continuationMode === 'fresh'
        ? t('runtime.timeline.summary.completedFresh')
        : t('runtime.timeline.summary.completed')
    )
    if (effectSummary) parts.push(toSentence(effectSummary))
    if (checkpointSummary) parts.push(toSentence(checkpointSummary))
    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'resumed') {
    if (resumedStageText) {
      parts.push(t('runtime.timeline.summary.resumedFromStage', { stage: resumedStageText }))
    } else {
      parts.push(t('runtime.timeline.summary.resumed'))
    }

    if (checkpointSummary) {
      parts.push(toSentence(checkpointSummary))
    } else if (effectSummary) {
      parts.push(toSentence(effectSummary))
    }

    return parts.join(' ')
  }

  if (runtime.continuationStatus === 'running') {
    if (stageText) {
      parts.push(t('runtime.timeline.summary.runningAtStage', { stage: stageText }))
    } else {
      parts.push(t('runtime.timeline.summary.running'))
    }

    if (checkpointSummary) parts.push(toSentence(checkpointSummary))
    return parts.join(' ')
  }

  if (runtime.continuationMode === 'resumed') {
    return t('runtime.timeline.summary.lineageResumed')
  }

  if (runtime.continuationMode === 'restart_fresh') {
    return t('runtime.timeline.summary.restartFresh')
  }

  return ''
}

export function buildContinuationResultEntry(t, runtime, baseEntry, headline, summary) {
  const fallback = safeObject(baseEntry)
  if (!runtime.hasContinuation) return fallback

  const badge =
    runtime.runtimePhase === 'waiting_checkpoint'
      ? t('runtime.timeline.badges.waitingCheckpoint')
      : formatContinuationStatusLabel(t, runtime.continuationStatus, runtime.runtimePhase) ||
        formatContinuationModeLabel(t, runtime.continuationMode) ||
        safeString(fallback.badge).trim() ||
        t('runtime.timeline.badges.runtime')

  const title =
    safeString(headline).trim() ||
    safeString(fallback.title).trim() ||
    t('runtime.card.defaultHeadline.current')

  const nextSummary = safeString(summary).trim() || safeString(fallback.summary).trim()

  const typeClass =
    mapContinuationTypeClass(runtime.continuationStatus) ||
    safeString(fallback.typeClass).trim() ||
    'message'

  return {
    ...fallback,
    badge,
    title,
    summary: nextSummary,
    typeClass,
  }
}

export function buildContinuationEntries(t, runtime, timeText = '') {
  if (!runtime.hasContinuation) return []

  const rows = []

  if (runtime.continuationStatus || runtime.continuationMode || runtime.runtimePhase) {
    rows.push({
      id: `runtime-status-${runtime.runtimePhase || runtime.continuationStatus || runtime.continuationMode}`,
      type: 'room.message',
      typeClass: mapContinuationTypeClass(runtime.continuationStatus),
      badge:
        runtime.runtimePhase === 'waiting_checkpoint'
          ? t('runtime.timeline.badges.waitingCheckpoint')
          : formatContinuationModeLabel(t, runtime.continuationMode) || t('runtime.timeline.badges.runtime'),
      title:
        runtime.runtimePhase === 'waiting_checkpoint'
          ? t('runtime.timeline.entry.waitingCheckpoint')
          : runtime.continuationStatus
            ? t('runtime.timeline.entry.status', {
                value: formatContinuationStatusLabel(t, runtime.continuationStatus, runtime.runtimePhase),
              })
            : t('runtime.timeline.entry.mode', {
                value: formatContinuationModeLabel(t, runtime.continuationMode),
              }),
      actor:
        runtime.canResume
          ? t('runtime.timeline.badges.resumable')
          : runtime.resumedFromStage
            ? t('runtime.timeline.entry.fromStage', { stage: formatStage(runtime.resumedFromStage) })
            : '',
      timeText,
    })
  }

  if (runtime.checkpointStage || runtime.interruptionReason || runtime.resumeFromCheckpoint) {
    rows.push({
      id: `runtime-checkpoint-${runtime.checkpointStage || runtime.interruptionReason || 'checkpoint'}`,
      type: 'room.route',
      typeClass:
        runtime.continuationStatus === 'interrupted' || runtime.continuationStatus === 'budget_exhausted'
          ? 'error'
          : 'route',
      badge: t('runtime.timeline.badges.checkpoint'),
      title: runtime.checkpointStage ? formatStage(runtime.checkpointStage) : t('runtime.timeline.entry.checkpoint'),
      actor: runtime.interruptionReason
        ? formatInterruptionReason(t, runtime.interruptionReason)
        : runtime.canResume
          ? t('runtime.timeline.badges.resumable')
          : '',
      timeText: '',
    })
  }

  if (runtime.effectSummary) {
    rows.push({
      id: `runtime-effects-${runtime.skippedEffectCount}-${safeArray(runtime.effectDispositions).length}`,
      type: 'room.supervisor',
      typeClass: 'supervisor',
      badge: t('runtime.timeline.badges.effects'),
      title: runtime.effectSummary,
      actor: '',
      timeText: '',
    })
  }

  return rows.slice(0, 3)
}

export function formatControlBlockReasonHint(t, reason, runtime) {
  const token = normalizeToken(reason)
  const stageText = formatStage(runtime.checkpointStage)

  if (!token) return ''
  if (token === 'pause_requested_pending_checkpoint') {
    return stageText
      ? t('runtime.timeline.hint.pauseWaitingStage', { stage: stageText })
      : t('runtime.timeline.hint.pauseWaiting')
  }
  if (token === 'resume_ready') {
    return stageText
      ? t('runtime.timeline.hint.resumeFromStage', { stage: stageText })
      : t('runtime.timeline.hint.resumeFromRecent')
  }
  if (token === 'run_running') {
    return t('runtime.timeline.hint.runRunning')
  }
  if (token === 'budget_exhausted') {
    return t('runtime.timeline.hint.budgetExhausted')
  }
  if (token === 'resume_blocked_error') {
    return t('runtime.timeline.hint.resumeBlockedError')
  }
  return humanizeToken(token)
}

