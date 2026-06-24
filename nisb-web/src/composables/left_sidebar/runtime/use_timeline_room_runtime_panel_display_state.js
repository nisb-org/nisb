import { computed } from 'vue'
import {
  safeArray,
  safeObject,
  safeString,
  normalizeSummaryObject,
  readSummaryText,
  hasObjectContent,
  pushUniquePart,
  dedupeEntries,
  formatStage,
  getRuntimeTimeText,
} from './room_runtime_panel_shared'
import {
  buildFormalLegalRuntimeHeadline,
  buildFormalLegalRuntimeBadgeParts,
  buildFormalLegalRuntimeSummaryText,
  buildFormalLegalRuntimeResultEntry,
  buildFormalLegalRuntimeRecentEntries,
  buildFormalLegalRuntimeStatusText,
} from './room_runtime_formal'
import {
  normalizeRuntimeState,
  normalizeContinuationStatus,
  isTerminalContinuationStatus,
  buildContinuationHeadline,
  buildContinuationBadgeParts,
  buildContinuationSummary,
  buildContinuationResultEntry,
  buildContinuationEntries,
  formatContinuationStatusText,
  formatControlBlockReasonHint,
} from './room_runtime_continuation'
import { buildFallbackRuntimeResultEntry } from './room_runtime_replay'

export function use_timeline_room_runtime_panel_display_state({
  t,

  roomRuntimeRoomId,
  roomRuntimeViewMode,
  roomRuntimeDisplayRunId,
  roomRuntimeReplaySelectedRunId,
  roomRuntimeReplayBundle,
  roomRuntimeReplayProcessItems,
  roomRuntimeRunOptions,
  roomRuntimeCurrentRunId,
  roomRuntimeLoading,
  roomRuntimeError,
  roomRuntimeLive,

  roomRuntimeFormalLegalFact,
  roomRuntimeContinuation,

  roomRuntimeResultPayload,
  roomRuntimeResultText,
  roomRuntimeResultEvent,

  runtimeResultEntryVM,
  runtimeResultTextDisplayVM,
  runtimeHeadlineVM,
  runtimeBadgeSummaryVM,
  runtimeHasTerminalResultVM,
  runtimeLatestProcessStageVM,
  runtimeProcessEntriesVM,
  runtimeSkillSummaryVM,
  runtimeSkillEntriesVM,
  runtimeMemorySummaryVM,
  runtimeMemoryEntriesVM,

  runtimeActionPending,
  runtimeActionError,
  optimisticResumePending,
}) {
  const room_runtime_selected_run_id = computed(() => {
    return roomRuntimeViewMode.value === 'replay'
      ? roomRuntimeReplaySelectedRunId.value || roomRuntimeDisplayRunId.value
      : ''
  })

  const room_runtime_skill_summary = computed(() => {
    return normalizeSummaryObject(
      runtimeSkillSummaryVM.value,
      roomRuntimeViewMode.value === 'replay' ? 'replay' : 'current'
    )
  })

  const room_runtime_memory_summary = computed(() => {
    return normalizeSummaryObject(
      runtimeMemorySummaryVM.value,
      roomRuntimeViewMode.value === 'replay' ? 'replay' : 'current'
    )
  })

  const room_runtime_has_terminal_result = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      const payload = roomRuntimeResultPayload.value
      if (Object.keys(payload).length) return true
      if (runtimeResultEntryVM.value) return true
      if (safeString(roomRuntimeReplayBundle.value.summary).trim()) return true
      if (safeString(roomRuntimeResultText.value).trim()) return true
      if (roomRuntimeReplayProcessItems.value.length > 0) return true
      return runtimeHasTerminalResultVM.value
    }

    if (roomRuntimeFormalLegalFact.value) return true

    return (
      isTerminalContinuationStatus(roomRuntimeContinuation.value.continuationStatus) ||
      runtimeHasTerminalResultVM.value
    )
  })

  const room_runtime_headline = computed(() => {
    const formalFact = roomRuntimeFormalLegalFact.value
    if (roomRuntimeViewMode.value === 'current' && formalFact) {
      return buildFormalLegalRuntimeHeadline(t, formalFact)
    }

    const runtime = roomRuntimeContinuation.value
    const replayRunId = roomRuntimeDisplayRunId.value || roomRuntimeReplaySelectedRunId.value
    const baseHeadline =
      roomRuntimeViewMode.value === 'replay'
        ? replayRunId
          ? t('runtime.card.defaultHeadline.replayWithId', { id: replayRunId })
          : t('runtime.card.defaultHeadline.replay')
        : safeString(runtimeHeadlineVM.value).trim()

    if (roomRuntimeViewMode.value === 'replay') return baseHeadline
    if (!runtime.hasContinuation) return baseHeadline || t('runtime.card.defaultHeadline.current')
    return buildContinuationHeadline(t, runtime, baseHeadline)
  })

  const room_runtime_badge_summary = computed(() => {
    const formalFact = roomRuntimeFormalLegalFact.value
    const skillSummary = readSummaryText(room_runtime_skill_summary.value)
    const memorySummary = readSummaryText(room_runtime_memory_summary.value)
    const replaySummary = safeString(roomRuntimeReplayBundle.value.summary).trim()

    if (roomRuntimeViewMode.value !== 'replay' && formalFact) {
      const parts = []
      buildFormalLegalRuntimeBadgeParts(t, formalFact).forEach((item) => pushUniquePart(parts, item))
      return parts.join(' · ')
    }

    const parts = []

    if (roomRuntimeViewMode.value !== 'replay') {
      buildContinuationBadgeParts(t, roomRuntimeContinuation.value).forEach((item) =>
        pushUniquePart(parts, item)
      )
    }

    const base = safeString(runtimeBadgeSummaryVM.value).trim()
    if (base) pushUniquePart(parts, base)
    if (skillSummary) pushUniquePart(parts, skillSummary)
    if (memorySummary) pushUniquePart(parts, memorySummary)
    if (roomRuntimeViewMode.value === 'replay' && replaySummary) {
      pushUniquePart(parts, replaySummary)
    }

    return parts.join(' · ')
  })

  const room_runtime_continuation_summary = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return ''
    if (roomRuntimeFormalLegalFact.value) {
      return buildFormalLegalRuntimeSummaryText(t, roomRuntimeFormalLegalFact.value)
    }
    return buildContinuationSummary(t, roomRuntimeContinuation.value)
  })

  const roomRuntimeBaseSummaryText = computed(() => {
    const continuationText = safeString(room_runtime_continuation_summary.value).trim()
    if (continuationText) return continuationText

    const displayText = safeString(runtimeResultTextDisplayVM.value).trim()
    if (displayText) return displayText

    const resultText = safeString(roomRuntimeResultText.value).trim()
    if (resultText) return resultText

    const replaySummary = safeString(roomRuntimeReplayBundle.value.summary).trim()
    if (roomRuntimeViewMode.value === 'replay' && replaySummary) return replaySummary

    const memorySummary = readSummaryText(room_runtime_memory_summary.value)
    if (memorySummary) return memorySummary

    const skillSummary = readSummaryText(room_runtime_skill_summary.value)
    if (skillSummary) return skillSummary

    return ''
  })

  const room_runtime_result_entry = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return buildFallbackRuntimeResultEntry({
        t,
        viewMode: 'replay',
        baseEntry: runtimeResultEntryVM.value,
        headline: room_runtime_headline.value,
        summaryText: roomRuntimeBaseSummaryText.value,
        resultText: roomRuntimeResultText.value,
        resultPayload: roomRuntimeResultPayload.value,
        resultEvent: roomRuntimeResultEvent.value,
      })
    }

    const formalFact = roomRuntimeFormalLegalFact.value
    if (formalFact) {
      return buildFormalLegalRuntimeResultEntry(t, formalFact, runtimeResultEntryVM.value)
    }

    const continuationRuntime = roomRuntimeContinuation.value
    const continuedEntry = buildContinuationResultEntry(
      t,
      continuationRuntime,
      runtimeResultEntryVM.value,
      room_runtime_headline.value,
      roomRuntimeBaseSummaryText.value
    )

    if (continuedEntry && Object.keys(safeObject(continuedEntry)).length) return continuedEntry

    return buildFallbackRuntimeResultEntry({
      t,
      viewMode: 'current',
      baseEntry: runtimeResultEntryVM.value,
      headline: room_runtime_headline.value,
      summaryText: roomRuntimeBaseSummaryText.value,
      resultText: roomRuntimeResultText.value,
      resultPayload: roomRuntimeResultPayload.value,
      resultEvent: roomRuntimeResultEvent.value,
    })
  })

  const room_runtime_latest_stage = computed(() => {
    if (roomRuntimeFormalLegalFact.value) {
      return buildFormalLegalRuntimeStatusText(t, roomRuntimeFormalLegalFact.value.kind)
    }

    return safeString(
      roomRuntimeContinuation.value.checkpointStage ||
        roomRuntimeContinuation.value.lastCompletedStep ||
        runtimeLatestProcessStageVM.value
    ).trim()
  })

  const room_runtime_recent_entries = computed(() => {
    const processRows = safeArray(runtimeProcessEntriesVM.value)
    const skillRows = safeArray(runtimeSkillEntriesVM.value)
    const memoryRows = safeArray(runtimeMemoryEntriesVM.value)

    if (roomRuntimeViewMode.value === 'replay') {
      const baseEntries = [...processRows, ...skillRows, ...memoryRows]
        .filter(Boolean)
        .map((item, idx) => ({
          ...item,
          __order: idx,
          __time: safeString(item?.timeText).trim(),
        }))
        .sort((a, b) => {
          const ta = a.__time
          const tb = b.__time
          if (ta && tb && ta !== tb) return tb.localeCompare(ta)
          return Number(b.__order || 0) - Number(a.__order || 0)
        })
        .map(({ __order, __time, ...rest }) => rest)

      return dedupeEntries(baseEntries).slice(0, 6)
    }

    if (roomRuntimeFormalLegalFact.value) {
      const synthetic = buildFormalLegalRuntimeRecentEntries(t, roomRuntimeFormalLegalFact.value)
      return dedupeEntries(synthetic).slice(0, 3)
    }

    const baseEntries = [...processRows, ...skillRows, ...memoryRows]
      .filter(Boolean)
      .map((item, idx) => ({
        ...item,
        __order: idx,
        __time: safeString(item?.timeText).trim(),
      }))
      .sort((a, b) => {
        const ta = a.__time
        const tb = b.__time
        if (ta && tb && ta !== tb) return tb.localeCompare(ta)
        return Number(b.__order || 0) - Number(a.__order || 0)
      })
      .map(({ __order, __time, ...rest }) => rest)

    const syntheticEntries = buildContinuationEntries(
      t,
      roomRuntimeContinuation.value,
      getRuntimeTimeText(roomRuntimeResultEvent.value)
    )

    return dedupeEntries([...syntheticEntries, ...baseEntries]).slice(0, 6)
  })

  const room_runtime_summary_text = computed(() => {
    const baseText = safeString(roomRuntimeBaseSummaryText.value).trim()
    if (baseText) return baseText

    const entry = room_runtime_result_entry.value
    if (entry?.summary) return safeString(entry.summary).trim()

    const latest = room_runtime_recent_entries.value.length ? room_runtime_recent_entries.value[0] : null
    return safeString(latest?.summary).trim()
  })

  const room_runtime_status_text = computed(() => {
    const formalFact = roomRuntimeFormalLegalFact.value
    if (formalFact) {
      return buildFormalLegalRuntimeStatusText(t, formalFact.kind)
    }

    if (roomRuntimeError.value) return roomRuntimeError.value

    const continuationStatusText = formatContinuationStatusText(
      t,
      roomRuntimeContinuation.value.continuationStatus,
      roomRuntimeContinuation.value.runtimePhase
    )

    if (roomRuntimeViewMode.value === 'replay') {
      if (roomRuntimeLoading.value) return t('runtime.timeline.status.replayLoading')
      if (room_runtime_has_terminal_result.value || room_runtime_result_entry.value) {
        return t('runtime.timeline.status.replayReady')
      }
      if (roomRuntimeDisplayRunId.value) return t('runtime.timeline.status.noReplayResult')
      if (roomRuntimeRunOptions.value.length > 0) return t('runtime.timeline.status.selectReplay')
      return t('runtime.timeline.status.noReplay')
    }

    if (continuationStatusText) return continuationStatusText
    if (roomRuntimeLive.value) return t('runtime.card.status.running')
    if (room_runtime_has_terminal_result.value) return t('runtime.card.status.completed')

    const hasSummary =
      hasObjectContent(room_runtime_skill_summary.value) ||
      hasObjectContent(room_runtime_memory_summary.value)

    if (
      runtimeProcessEntriesVM.value.length > 0 ||
      room_runtime_result_entry.value ||
      room_runtime_recent_entries.value.length > 0 ||
      hasSummary
    ) {
      return t('runtime.timeline.status.viewable')
    }

    return t('runtime.timeline.status.noRuntime')
  })

  const room_runtime_show_pause_action = computed(() => {
    if (roomRuntimeFormalLegalFact.value) return false
    if (roomRuntimeViewMode.value !== 'current') return false
    if (!roomRuntimeRoomId.value) return false
    return roomRuntimeContinuation.value.canPauseCurrent === true
  })

  const room_runtime_pause_disabled = computed(() => {
    if (!room_runtime_show_pause_action.value) return true
    if (!roomRuntimeCurrentRunId.value) return true
    if (runtimeActionPending.value === 'pause') return true
    return false
  })

  const room_runtime_pause_text = computed(() => {
    if (runtimeActionPending.value === 'pause') return t('runtime.timeline.actions.requesting')
    if (
      roomRuntimeContinuation.value.pauseRequestAccepted ||
      roomRuntimeContinuation.value.runtimePhase === 'waiting_checkpoint'
    ) {
      return t('runtime.timeline.actions.pauseRequested')
    }
    return t('runtime.card.actions.pauseCurrent')
  })

  const room_runtime_can_resume_from_checkpoint = computed(() => {
    if (roomRuntimeFormalLegalFact.value) return false
    if (roomRuntimeViewMode.value !== 'current') return false
    return roomRuntimeContinuation.value.canResume === true
  })

  const room_runtime_show_resume_action = computed(() => {
    if (roomRuntimeFormalLegalFact.value) return false
    if (roomRuntimeViewMode.value !== 'current') return false
    return room_runtime_can_resume_from_checkpoint.value === true
  })

  const room_runtime_resume_disabled = computed(() => {
    if (!room_runtime_show_resume_action.value) return true
    if (runtimeActionPending.value === 'resume') return true
    return false
  })

  const room_runtime_resume_text = computed(() => {
    if (runtimeActionPending.value === 'resume') return t('runtime.timeline.actions.resuming')
    return t('runtime.card.actions.resumeFromCheckpoint')
  })

  const room_runtime_control_hint = computed(() => {
    if (roomRuntimeFormalLegalFact.value) return ''
    if (roomRuntimeViewMode.value !== 'current') return ''

    if (runtimeActionError.value) return runtimeActionError.value

    const runtime = roomRuntimeContinuation.value

    if (runtime.canResume) {
      return runtime.checkpointStage
        ? t('runtime.timeline.hint.resumeFromStage', { stage: formatStage(runtime.checkpointStage) })
        : t('runtime.timeline.hint.resumeFromRecent')
    }

    if (
      runtime.pauseRequestAccepted ||
      runtime.runtimePhase === 'waiting_checkpoint' ||
      (runtime.pauseRequested && runtime.canPauseCurrent !== true)
    ) {
      return runtime.checkpointStage
        ? t('runtime.timeline.hint.pauseWaitingStage', { stage: formatStage(runtime.checkpointStage) })
        : t('runtime.timeline.hint.pauseWaiting')
    }

    if (runtime.errorBlockingResume && !runtime.canResume) {
      return t('runtime.timeline.hint.errorBlockingResume')
    }

    if (runtime.continuationStatus === 'budget_exhausted' || runtime.budgetExhausted) {
      return t('runtime.timeline.hint.budgetExhausted')
    }

    if (!runtime.canAcceptNewPrompt && runtime.controlBlockReason) {
      return formatControlBlockReasonHint(t, runtime.controlBlockReason, runtime)
    }

    if (runtime.continuationStatus === 'resumed' || optimisticResumePending.value) {
      return runtime.resumedFromStage
        ? t('runtime.timeline.hint.resumedFromStage', { stage: formatStage(runtime.resumedFromStage) })
        : t('runtime.timeline.hint.resumed')
    }

    return ''
  })

  const show_room_runtime_section = computed(() => {
    if (!roomRuntimeRoomId.value) return false
    if (roomRuntimeLoading.value) return true
    if (roomRuntimeLive.value) return true
    if (roomRuntimeError.value) return true
    if (roomRuntimeFormalLegalFact.value) return true
    if (roomRuntimeContinuation.value.hasContinuation) return true
    if (room_runtime_control_hint.value) return true
    if (runtimeProcessEntriesVM.value.length > 0) return true
    if (room_runtime_result_entry.value) return true
    if (room_runtime_recent_entries.value.length > 0) return true
    if (hasObjectContent(room_runtime_skill_summary.value)) return true
    if (hasObjectContent(room_runtime_memory_summary.value)) return true
    if (roomRuntimeViewMode.value === 'replay' && roomRuntimeRunOptions.value.length > 0) return true
    return false
  })

  const room_runtime_runtime_state = computed(() => {
    return roomRuntimeFormalLegalFact.value
      ? roomRuntimeFormalLegalFact.value.kind
      : roomRuntimeContinuation.value.runtimeState
  })

  const room_runtime_runtime_phase = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.runtimePhase
  })

  const room_runtime_can_accept_new_prompt = computed(() => {
    return roomRuntimeFormalLegalFact.value ? true : roomRuntimeContinuation.value.canAcceptNewPrompt
  })

  const room_runtime_control_block_reason = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.controlBlockReason
  })

  const room_runtime_continuation_mode = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.continuationMode
  })

  const room_runtime_continuation_status = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.continuationStatus
  })

  const room_runtime_pause_requested = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.pauseRequested
  })

  const room_runtime_pause_request_accepted = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.pauseRequestAccepted
  })

  const room_runtime_pause_reason = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.pauseReason
  })

  const room_runtime_pause_requested_at = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.pauseRequestedAt
  })

  const room_runtime_pause_effective = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.pauseEffective
  })

  const room_runtime_paused_at = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.pausedAt
  })

  const room_runtime_pause_effective_at = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.pauseEffectiveAt
  })

  const room_runtime_interruption_reason = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.interruptionReason
  })

  const room_runtime_resume_ready = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.resumeReady
  })

  const room_runtime_resume_from_checkpoint = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.resumeFromCheckpoint
  })

  const room_runtime_resume_checkpoint_ref = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumeCheckpointRef
  })

  const room_runtime_resume_token = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumeToken
  })

  const room_runtime_resume_reason = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumeReason
  })

  const room_runtime_error_blocking_resume = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.errorBlockingResume
  })

  const room_runtime_resumed_from_run_id = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumedFromRunId
  })

  const room_runtime_resumed_from_event_id = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumedFromEventId
  })

  const room_runtime_resumed_from_stage = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.resumedFromStage
  })

  const room_runtime_checkpoint_stage = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.checkpointStage
  })

  const room_runtime_checkpoint_summary = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.checkpointSummary
  })

  const room_runtime_last_completed_step = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.lastCompletedStep
  })

  const room_runtime_skipped_effects = computed(() => {
    return roomRuntimeFormalLegalFact.value ? [] : roomRuntimeContinuation.value.skippedEffects
  })

  const room_runtime_effect_dispositions = computed(() => {
    return roomRuntimeFormalLegalFact.value ? [] : roomRuntimeContinuation.value.effectDispositions
  })

  const room_runtime_step_budget_total = computed(() => {
    return roomRuntimeFormalLegalFact.value ? null : roomRuntimeContinuation.value.stepBudgetTotal
  })

  const room_runtime_step_budget_used = computed(() => {
    return roomRuntimeFormalLegalFact.value ? null : roomRuntimeContinuation.value.stepBudgetUsed
  })

  const room_runtime_step_budget_remaining = computed(() => {
    return roomRuntimeFormalLegalFact.value ? null : roomRuntimeContinuation.value.stepBudgetRemaining
  })

  const room_runtime_budget_status = computed(() => {
    return roomRuntimeFormalLegalFact.value ? '' : roomRuntimeContinuation.value.budgetStatus
  })

  const room_runtime_budget_exhausted = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.budgetExhausted
  })

  const room_runtime_can_pause_current = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.canPauseCurrent
  })

  const room_runtime_can_resume = computed(() => {
    return roomRuntimeFormalLegalFact.value ? false : roomRuntimeContinuation.value.canResume
  })

  return {
    show_room_runtime_section,
    room_runtime_selected_run_id,
    room_runtime_skill_summary,
    room_runtime_memory_summary,
    room_runtime_has_terminal_result,
    room_runtime_headline,
    room_runtime_badge_summary,
    room_runtime_continuation_summary,
    room_runtime_result_entry,
    room_runtime_latest_stage,
    room_runtime_recent_entries,
    room_runtime_summary_text,
    room_runtime_status_text,
    room_runtime_show_pause_action,
    room_runtime_pause_disabled,
    room_runtime_pause_text,
    room_runtime_can_resume_from_checkpoint,
    room_runtime_show_resume_action,
    room_runtime_resume_disabled,
    room_runtime_resume_text,
    room_runtime_control_hint,

    room_runtime_runtime_state,
    room_runtime_runtime_phase,
    room_runtime_can_accept_new_prompt,
    room_runtime_control_block_reason,
    room_runtime_continuation_mode,
    room_runtime_continuation_status,
    room_runtime_pause_requested,
    room_runtime_pause_request_accepted,
    room_runtime_pause_reason,
    room_runtime_pause_requested_at,
    room_runtime_pause_effective,
    room_runtime_paused_at,
    room_runtime_pause_effective_at,
    room_runtime_interruption_reason,
    room_runtime_resume_ready,
    room_runtime_resume_from_checkpoint,
    room_runtime_resume_checkpoint_ref,
    room_runtime_resume_token,
    room_runtime_resume_reason,
    room_runtime_error_blocking_resume,
    room_runtime_resumed_from_run_id,
    room_runtime_resumed_from_event_id,
    room_runtime_resumed_from_stage,
    room_runtime_checkpoint_stage,
    room_runtime_checkpoint_summary,
    room_runtime_last_completed_step,
    room_runtime_skipped_effects,
    room_runtime_effect_dispositions,
    room_runtime_step_budget_total,
    room_runtime_step_budget_used,
    room_runtime_step_budget_remaining,
    room_runtime_budget_status,
    room_runtime_budget_exhausted,
    room_runtime_can_pause_current,
    room_runtime_can_resume,
  }
}

export default use_timeline_room_runtime_panel_display_state
