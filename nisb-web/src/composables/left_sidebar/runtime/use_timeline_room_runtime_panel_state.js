import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { use_chat_panel_room_runtime_view_model } from '../../editor/chat_panel/use_chat_panel_room_runtime_view_model'
import {
  safeArray,
  safeObject,
  safeString,
  normalizeRuntimeViewMode,
} from './room_runtime_panel_shared'
import {
  extractFormalLegalRuntimeFact,
} from './room_runtime_formal'
import {
  normalizeRuntimeControlSnapshot,
  normalizeRuntimeState,
  normalizeContinuationStatus,
  isTerminalContinuationStatus,
  normalizeContinuationRuntime,
} from './room_runtime_continuation'
import {
  isRuntimeProcessEvent,
  collectRuntimeRunOptions,
  pickReplayResultEvent,
  pickReplayFinalPayload,
  pickReplayAvailableRuns,
  resolveReplayBundleForRun,
} from './room_runtime_replay'
import { use_timeline_room_runtime_actions } from './use_timeline_room_runtime_actions'
import { use_timeline_room_runtime_panel_display_state } from './use_timeline_room_runtime_panel_display_state'

export function use_timeline_room_runtime_panel_state({ roomStore, callTool }) {
  const { t } = useI18n()

  const replayRunSelection = ref('')

  const runtimeBase = computed(() => safeObject(roomStore.runtime))

  const roomRuntimeRoomId = computed(() => {
    return safeString(roomStore.roomId || roomStore.activeRoomId).trim()
  })

  const roomRuntimeViewMode = computed(() => {
    return normalizeRuntimeViewMode(runtimeBase.value.view_mode)
  })

  const roomRuntimeSelectedRunId = computed(() => {
    return safeString(runtimeBase.value.selected_run_id).trim()
  })

  const roomRuntimeReplayBundleRaw = computed(() => {
    return safeObject(runtimeBase.value.replay_bundle)
  })

  const roomRuntimeReplaySelectedRunId = computed(() => {
    return safeString(
      replayRunSelection.value ||
        roomRuntimeSelectedRunId.value ||
        roomRuntimeReplayBundleRaw.value.run_id
    ).trim()
  })

  const roomRuntimeReplayBundle = computed(() => {
    return resolveReplayBundleForRun(runtimeBase.value, roomRuntimeReplaySelectedRunId.value, roomStore)
  })

  const roomRuntimeCurrentProcessItems = computed(() => {
    const explicit = safeArray(runtimeBase.value.items)
    if (explicit.length) return explicit
    return safeArray(roomStore.items).filter(isRuntimeProcessEvent)
  })

  const roomRuntimeReplayProcessItems = computed(() => {
    const bundle = roomRuntimeReplayBundle.value
    const directItems = safeArray(bundle.items)
    if (directItems.length) return directItems.filter(isRuntimeProcessEvent)
    return safeArray(bundle.events).filter(isRuntimeProcessEvent)
  })

  const roomRuntimeProcessItems = computed(() => {
    return roomRuntimeViewMode.value === 'replay'
      ? roomRuntimeReplayProcessItems.value
      : roomRuntimeCurrentProcessItems.value
  })

  const roomRuntimeResultEvent = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return pickReplayResultEvent(roomRuntimeReplayBundle.value, roomRuntimeReplayProcessItems.value)
    }

    const explicit = roomStore.runtimeResultEvent
    if (explicit) return explicit
    return roomRuntimeCurrentProcessItems.value.length
      ? roomRuntimeCurrentProcessItems.value[roomRuntimeCurrentProcessItems.value.length - 1]
      : null
  })

  const roomRuntimeResultPayload = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      const fromFinal = pickReplayFinalPayload(roomRuntimeReplayBundle.value)
      if (Object.keys(fromFinal).length) return fromFinal

      const explicit = safeObject(roomRuntimeReplayBundle.value.result_payload)
      if (Object.keys(explicit).length) return explicit

      return safeObject(roomRuntimeResultEvent.value?.payload || roomRuntimeResultEvent.value)
    }

    const explicit = safeObject(roomStore.runtimeResultPayload)
    if (Object.keys(explicit).length) return explicit
    return safeObject(roomRuntimeResultEvent.value?.payload || roomRuntimeResultEvent.value)
  })

  const roomRuntimeResultText = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      const explicit = safeString(
        roomRuntimeReplayBundle.value.result_text ||
          roomRuntimeReplayBundle.value.summary ||
          roomRuntimeReplayBundle.value.final_read_model?.message ||
          roomRuntimeReplayBundle.value.final_read_model?.content ||
          roomRuntimeReplayBundle.value.final_read_model?.response
      ).trim()
      if (explicit) return explicit
    } else {
      const explicit = safeString(roomStore.runtimeResultText).trim()
      if (explicit) return explicit
    }

    return safeString(
      roomRuntimeResultPayload.value.response ||
        roomRuntimeResultPayload.value.content ||
        roomRuntimeResultPayload.value.message
    ).trim()
  })

  const roomRuntimeDisplayRunId = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeString(
        roomRuntimeReplayBundle.value.run_id || roomRuntimeReplaySelectedRunId.value
      ).trim()
    }

    return safeString(runtimeBase.value.run_id || roomStore.roomState?.current_run_id).trim()
  })

  const roomRuntimeCurrentRunId = computed(() => {
    return safeString(
      roomStore.roomState?.current_run_id ||
        runtimeBase.value.run_id ||
        roomRuntimeDisplayRunId.value
    ).trim()
  })

  const roomRuntimeLoading = computed(() => {
    return roomRuntimeViewMode.value === 'replay'
      ? !!runtimeBase.value.replay_loading
      : !!runtimeBase.value.loading
  })

  const roomRuntimeError = computed(() => {
    return roomRuntimeViewMode.value === 'replay'
      ? safeString(runtimeBase.value.replay_error).trim()
      : safeString(runtimeBase.value.error).trim()
  })

  const roomRuntimeRunOptions = computed(() => {
    const replayAvailableRuns = safeArray(
      pickReplayAvailableRuns(runtimeBase.value, roomRuntimeReplayBundleRaw.value)
    )
      .map((item) => {
        const row = safeObject(item)
        const runId = safeString(row.run_id || row.id || row.value).trim()
        if (!runId) return null
        const startedAt = safeString(row.started_at).trim()
        let timeText = ''
        if (startedAt) {
          try {
            const d = new Date(startedAt)
            if (!Number.isNaN(d.getTime())) {
              timeText = d.toTimeString().slice(0, 5)
            }
          } catch {}
        }
        return {
          value: runId,
          label: timeText ? `${runId} · ${timeText}` : runId,
        }
      })
      .filter(Boolean)

    if (replayAvailableRuns.length) return replayAvailableRuns
    return collectRuntimeRunOptions(roomStore)
  })

  const roomRuntimeSupervisorSkills = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.runtime_supervisor_skills ||
          roomRuntimeReplayBundle.value.supervisor_skills
      )
    }

    return safeObject(runtimeBase.value.runtime_supervisor_skills || roomStore.runtimeSupervisorSkills)
  })

  const roomRuntimeSupervisorSkillsSummary = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.runtime_supervisor_skills_summary ||
          roomRuntimeReplayBundle.value.supervisor_skills_summary
      )
    }

    return safeObject(
      runtimeBase.value.runtime_supervisor_skills_summary || roomStore.runtimeSupervisorSkillsSummary
    )
  })

  const roomRuntimeSupervisorMemory = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.runtime_supervisor_memory ||
          roomRuntimeReplayBundle.value.supervisor_memory
      )
    }

    return safeObject(runtimeBase.value.runtime_supervisor_memory || roomStore.runtimeSupervisorMemory)
  })

  const roomRuntimeSupervisorMemorySummary = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.runtime_supervisor_memory_summary ||
          roomRuntimeReplayBundle.value.supervisor_memory_summary
      )
    }

    return safeObject(
      runtimeBase.value.runtime_supervisor_memory_summary || roomStore.runtimeSupervisorMemorySummary
    )
  })

  const runtimeVM = use_chat_panel_room_runtime_view_model({
    process_items: roomRuntimeProcessItems,
    result_event: roomRuntimeResultEvent,
    result_payload: roomRuntimeResultPayload,
    result_text: roomRuntimeResultText,
    runtime_supervisor_skills: roomRuntimeSupervisorSkills,
    runtime_supervisor_skills_summary: roomRuntimeSupervisorSkillsSummary,
    runtime_supervisor_memory: roomRuntimeSupervisorMemory,
    runtime_supervisor_memory_summary: roomRuntimeSupervisorMemorySummary,
  })

  const runtimeProcessEntriesVM = runtimeVM.processEntries || computed(() => [])
  const runtimeResultEntryVM = runtimeVM.resultEntry || computed(() => null)
  const runtimeResultTextDisplayVM = runtimeVM.resultTextDisplay || computed(() => '')
  const runtimeHeadlineVM = runtimeVM.runtimeHeadline || computed(() => '')
  const runtimeBadgeSummaryVM = runtimeVM.runtimeBadgeSummary || computed(() => '')
  const runtimeHasTerminalResultVM = runtimeVM.hasTerminalResult || computed(() => false)
  const runtimeLatestProcessStageVM = runtimeVM.latestProcessStage || computed(() => '')
  const runtimeSkillSummaryVM = runtimeVM.runtimeSkillSummary || computed(() => '')
  const runtimeSkillEntriesVM = runtimeVM.runtimeSkillEntries || computed(() => [])
  const runtimeMemorySummaryVM = runtimeVM.runtimeMemorySummary || computed(() => ({}))
  const runtimeMemoryEntriesVM = runtimeVM.runtimeMemoryEntries || computed(() => [])

  const roomRuntimeStateSnapshot = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.room_state_snapshot ||
          roomRuntimeReplayBundle.value.room_state ||
          roomRuntimeReplayBundle.value.state_snapshot ||
          roomRuntimeReplayBundle.value.state
      )
    }
    return safeObject(roomStore.roomState)
  })

  const roomRuntimeControlSnapshotRaw = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') {
      return safeObject(
        roomRuntimeReplayBundle.value.runtime_control_snapshot ||
          roomRuntimeReplayBundle.value.control_snapshot ||
          roomRuntimeReplayBundle.value.current_runtime_control_snapshot ||
          {}
      )
    }

    return safeObject(
      runtimeBase.value.runtime_control_snapshot ||
        runtimeBase.value.control_snapshot ||
        roomStore.runtimeControlSnapshot ||
        roomStore.roomState?.runtime_control_snapshot ||
        roomStore.roomState ||
        {}
    )
  })

  const roomRuntimeControlSnapshot = computed(() => {
    return normalizeRuntimeControlSnapshot(roomRuntimeControlSnapshotRaw.value)
  })

  const roomRuntimeFormalLegalFact = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return null

    return extractFormalLegalRuntimeFact({
      runtimeBase: runtimeBase.value,
      roomState: roomRuntimeStateSnapshot.value,
      controlSnapshot: roomRuntimeControlSnapshot.value,
      controlSnapshotRaw: roomRuntimeControlSnapshotRaw.value,
      resultPayload: roomRuntimeResultPayload.value,
      resultEvent: roomRuntimeResultEvent.value,
    })
  })

  const roomRuntimeLive = computed(() => {
    if (roomRuntimeViewMode.value === 'replay') return false
    if (roomRuntimeFormalLegalFact.value) return false

    const control = roomRuntimeControlSnapshot.value
    const runtimeState = normalizeRuntimeState(control.runtimeState)
    const runtimePhase = normalizeRuntimeState(control.runtimePhase)

    if (['running', 'resumed', 'pause_requested'].includes(runtimeState)) return true
    if (runtimePhase === 'waiting_checkpoint' || runtimeState === 'waiting_checkpoint') return true

    if (['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(runtimeState)) {
      return false
    }

    const continuationStatus = normalizeContinuationStatus(control.continuationStatus)
    if (['running', 'pause_requested', 'resumed'].includes(continuationStatus)) return true
    if (isTerminalContinuationStatus(continuationStatus)) return false

    const explicit = runtimeBase.value.live_hint
    if (typeof explicit === 'boolean') return explicit

    return false
  })

  const {
    runtimeActionPending,
    runtimeActionError,
    optimisticPauseRequested,
    optimisticResumePending,
    resetRuntimeActionState,
    handleRuntimeRefresh,
    handleRuntimeSwitchMode,
    handleRuntimeSelectRun,
    handleRuntimePauseCurrent,
    handleRuntimeResumeFromCheckpoint,
  } = use_timeline_room_runtime_actions({
    roomStore,
    callTool,
    t,
    replayRunSelection,
    roomRuntimeRoomId,
    roomRuntimeViewMode,
    roomRuntimeReplaySelectedRunId,
    roomRuntimeDisplayRunId,
    roomRuntimeReplayBundle,
    roomRuntimeSelectedRunId,
    roomRuntimeRunOptions,
    roomRuntimeCurrentRunId,
    roomRuntimeContinuation: computed(() => roomRuntimeContinuation.value),
  })

  const roomRuntimeContinuation = computed(() => {
    const runtime = normalizeContinuationRuntime({
      controlSnapshot: roomRuntimeControlSnapshot.value,
      roomState: roomRuntimeStateSnapshot.value,
      resultPayload: roomRuntimeResultPayload.value,
      resultEvent: roomRuntimeResultEvent.value,
      replayBundle: roomRuntimeReplayBundle.value,
      live: roomRuntimeLive.value,
      latestStage: runtimeLatestProcessStageVM.value,
      t,
    })

    if (roomRuntimeViewMode.value !== 'current') return runtime

    if (
      optimisticPauseRequested.value &&
      runtime.canPauseCurrent !== true &&
      runtime.canResume !== true &&
      !['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(runtime.continuationStatus)
    ) {
      runtime.pauseRequested = true
      runtime.pauseRequestAccepted = true
      runtime.continuationStatus = 'pause_requested'
      if (!runtime.runtimePhase) runtime.runtimePhase = 'waiting_checkpoint'
      if (!runtime.controlBlockReason) runtime.controlBlockReason = 'pause_requested_pending_checkpoint'
      if (!runtime.interruptionReason) runtime.interruptionReason = 'pause_requested'
    }

    if (
      optimisticResumePending.value &&
      runtime.canResume !== true &&
      !['completed', 'completed_after_resume', 'budget_exhausted'].includes(runtime.continuationStatus)
    ) {
      runtime.continuationMode = 'resumed'
      runtime.resumeReady = false
      runtime.controlBlockReason = 'run_running'
      if (!['running', 'resumed'].includes(runtime.continuationStatus)) {
        runtime.continuationStatus = 'resumed'
      }
      if (!runtime.runtimeState) runtime.runtimeState = 'resumed'
    }

    return runtime
  })

  const displayState = use_timeline_room_runtime_panel_display_state({
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
  })

  watch(
    () => roomRuntimeSelectedRunId.value,
    (value) => {
      const runId = safeString(value).trim()
      if (runId) replayRunSelection.value = runId
    },
    { immediate: true }
  )

  watch(
    () => roomRuntimeViewMode.value,
    (mode) => {
      resetRuntimeActionState()
      if (mode !== 'replay') replayRunSelection.value = ''
    }
  )

  watch(
    () => roomRuntimeRoomId.value,
    () => {
      replayRunSelection.value = ''
      resetRuntimeActionState()
    }
  )

  watch(
    () => [
      roomRuntimeContinuation.value.continuationStatus,
      roomRuntimeContinuation.value.runtimeState,
      roomRuntimeContinuation.value.runtimePhase,
      roomRuntimeContinuation.value.canResume,
      roomRuntimeContinuation.value.canPauseCurrent,
    ],
    ([status, runtimeState, runtimePhase, canResume]) => {
      const token = normalizeContinuationStatus(status)
      const stateToken = normalizeRuntimeState(runtimeState)
      const phaseToken = normalizeRuntimeState(runtimePhase)

      if (canResume === true) {
        optimisticPauseRequested.value = false
        if (runtimeActionPending.value === 'pause') runtimeActionPending.value = ''
      }

      if (
        ['pause_requested', 'interrupted', 'budget_exhausted'].includes(token) ||
        ['pause_requested', 'interrupted', 'budget_exhausted'].includes(stateToken) ||
        phaseToken === 'waiting_checkpoint'
      ) {
        optimisticPauseRequested.value = false
        if (runtimeActionPending.value === 'pause') runtimeActionPending.value = ''
      }

      if (
        ['resumed', 'running', 'completed_after_resume', 'completed'].includes(token) ||
        ['resumed', 'running', 'completed_after_resume', 'completed'].includes(stateToken)
      ) {
        optimisticResumePending.value = false
        if (runtimeActionPending.value === 'resume') runtimeActionPending.value = ''
      }

      if (isTerminalContinuationStatus(token) && token !== 'interrupted') {
        optimisticPauseRequested.value = false
      }
    }
  )

  return {
    room_runtime_room_id: roomRuntimeRoomId,
    room_runtime_live: roomRuntimeLive,
    room_runtime_error: roomRuntimeError,
    room_runtime_loading: roomRuntimeLoading,

    room_runtime_control_snapshot: roomRuntimeControlSnapshot,
    room_runtime_control_snapshot_raw: roomRuntimeControlSnapshotRaw,

    ...displayState,

    handleRuntimeRefresh,
    handleRuntimeSwitchMode,
    handleRuntimeSelectRun,
    handleRuntimePauseCurrent,
    handleRuntimeResumeFromCheckpoint,
  }
}

export default use_timeline_room_runtime_panel_state
