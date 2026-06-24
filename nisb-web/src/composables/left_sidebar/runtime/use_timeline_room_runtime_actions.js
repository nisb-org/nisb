import { onUnmounted, ref } from 'vue'
import { safeString, normalizeRuntimeViewMode } from './room_runtime_panel_shared'
import {
  normalizeRuntimeActionResponse,
  readRunIdSelectionInput,
} from './room_runtime_replay'

const RUNTIME_ACTION_TOOLS = {
  pause: 'nisb_room_runtime_pause_current',
  resume: 'nisb_room_runtime_resume_from_checkpoint',
}

export function use_timeline_room_runtime_actions({
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
  roomRuntimeContinuation,
}) {
  const runtimeActionPending = ref('')
  const runtimeActionError = ref('')
  const optimisticPauseRequested = ref(false)
  const optimisticResumePending = ref(false)

  let acceptedRefreshTimer = null

  function clearAcceptedRefreshTimer() {
    if (acceptedRefreshTimer) {
      clearTimeout(acceptedRefreshTimer)
      acceptedRefreshTimer = null
    }
  }

  function resetRuntimeActionState({ keepError = false } = {}) {
    runtimeActionPending.value = ''
    optimisticPauseRequested.value = false
    optimisticResumePending.value = false
    if (!keepError) runtimeActionError.value = ''
    clearAcceptedRefreshTimer()
  }

  async function handleRuntimeRefresh() {
    const rid = roomRuntimeRoomId.value
    if (!rid) return

    try {
      if (roomRuntimeViewMode.value === 'replay') {
        const runId = safeString(
          roomRuntimeReplaySelectedRunId.value ||
            roomRuntimeDisplayRunId.value ||
            roomRuntimeReplayBundle.value?.run_id ||
            roomRuntimeSelectedRunId.value ||
            roomRuntimeRunOptions.value[0]?.value
        ).trim()

        if (!runId) return

        replayRunSelection.value = runId

        if (typeof roomStore.setRuntimeReplayRunId === 'function') {
          roomStore.setRuntimeReplayRunId(runId)
        }

        if (typeof roomStore.refreshRuntimeReplay === 'function') {
          await roomStore.refreshRuntimeReplay(callTool, rid, {
            run_id: runId,
            selected_run_id: runId,
            silent: false,
            set_view_mode: true,
          })
        }
        return
      }

      if (typeof roomStore.refreshRuntimeEvents === 'function') {
        await roomStore.refreshRuntimeEvents(callTool, rid, {
          silent: false,
          reset: false,
        })
      }
    } catch (e) {
      console.error('[时间线] 刷新 Room runtime 失败:', e)
    }
  }

  function scheduleAcceptedRefresh() {
    clearAcceptedRefreshTimer()
    Promise.resolve().then(() => handleRuntimeRefresh())
    acceptedRefreshTimer = setTimeout(() => {
      handleRuntimeRefresh()
    }, 1200)
  }

  onUnmounted(() => {
    clearAcceptedRefreshTimer()
  })

  async function handleRuntimeSwitchMode(mode) {
    const nextMode = normalizeRuntimeViewMode(mode)
    const rid = roomRuntimeRoomId.value
    if (!rid) return

    resetRuntimeActionState()

    try {
      if (nextMode === 'current') {
        replayRunSelection.value = ''

        if (typeof roomStore.setRuntimeViewMode === 'function') {
          roomStore.setRuntimeViewMode('current')
        }
        if (typeof roomStore.resetRuntimeReplay === 'function') {
          roomStore.resetRuntimeReplay({
            preserve_view_mode: true,
            preserve_selected_run: false,
          })
        }
        if (typeof roomStore.refreshRuntimeEvents === 'function') {
          await roomStore.refreshRuntimeEvents(callTool, rid, {
            silent: false,
            reset: false,
          })
        }
        return
      }

      const targetRunId = safeString(
        roomRuntimeReplaySelectedRunId.value ||
          roomRuntimeRunOptions.value[0]?.value ||
          roomStore.latestCompletedRunId ||
          roomStore.runtime?.run_id ||
          roomStore.roomState?.current_run_id
      ).trim()

      if (typeof roomStore.setRuntimeViewMode === 'function') {
        roomStore.setRuntimeViewMode('replay')
      }

      if (targetRunId) {
        replayRunSelection.value = targetRunId
      }

      if (targetRunId && typeof roomStore.setRuntimeReplayRunId === 'function') {
        roomStore.setRuntimeReplayRunId(targetRunId)
      }

      if (targetRunId && typeof roomStore.refreshRuntimeReplay === 'function') {
        await roomStore.refreshRuntimeReplay(callTool, rid, {
          run_id: targetRunId,
          selected_run_id: targetRunId,
          silent: false,
          set_view_mode: true,
        })
      }
    } catch (e) {
      console.error('[时间线] 切换 Room runtime 视图失败:', e)
    }
  }

  async function handleRuntimeSelectRun(input) {
    const rid = roomRuntimeRoomId.value
    const targetRunId = readRunIdSelectionInput(input)

    if (!rid || !targetRunId) return

    resetRuntimeActionState()
    replayRunSelection.value = targetRunId

    try {
      if (typeof roomStore.setRuntimeViewMode === 'function') {
        roomStore.setRuntimeViewMode('replay')
      }
      if (typeof roomStore.setRuntimeReplayRunId === 'function') {
        roomStore.setRuntimeReplayRunId(targetRunId)
      }
      if (typeof roomStore.refreshRuntimeReplay === 'function') {
        await roomStore.refreshRuntimeReplay(callTool, rid, {
          run_id: targetRunId,
          selected_run_id: targetRunId,
          silent: false,
          set_view_mode: true,
        })
      }
    } catch (e) {
      console.error('[时间线] 切换回放 run 失败:', e)
    }
  }

  async function handleRuntimePauseCurrent() {
    const rid = roomRuntimeRoomId.value
    const runId = roomRuntimeCurrentRunId.value
    const runtime = roomRuntimeContinuation.value

    if (!rid || !runId) return
    if (runtimeActionPending.value === 'pause') return
    if (runtime?.canPauseCurrent !== true) return

    runtimeActionError.value = ''
    runtimeActionPending.value = 'pause'

    try {
      const result = await callTool(RUNTIME_ACTION_TOOLS.pause, {
        room_id: rid,
        run_id: runId,
      })

      const action = normalizeRuntimeActionResponse(result)
      if (!action.accepted) {
        throw new Error(action.message || t('runtime.timeline.errors.pauseNotAccepted'))
      }

      runtimeActionPending.value = ''
      optimisticPauseRequested.value = true
      optimisticResumePending.value = false
      scheduleAcceptedRefresh()
    } catch (e) {
      runtimeActionPending.value = ''
      runtimeActionError.value = safeString(e?.message || e).trim() || t('runtime.timeline.errors.pauseFailed')
      console.error('[时间线] Pause current run 失败:', e)
    }
  }

  async function handleRuntimeResumeFromCheckpoint() {
    const rid = roomRuntimeRoomId.value
    const runtime = roomRuntimeContinuation.value

    if (!rid) return
    if (runtimeActionPending.value === 'resume') return
    if (runtime?.canResume !== true) return

    runtimeActionError.value = ''
    runtimeActionPending.value = 'resume'

    const payload = {
      room_id: rid,
    }

    if (runtime.resumeCheckpointRef) {
      payload.resume_checkpoint_ref = runtime.resumeCheckpointRef
    }

    if (runtime.resumeToken) {
      payload.resume_token = runtime.resumeToken
    }

    try {
      const result = await callTool(RUNTIME_ACTION_TOOLS.resume, payload)
      const action = normalizeRuntimeActionResponse(result)

      if (!action.accepted) {
        throw new Error(action.message || t('runtime.timeline.errors.resumeNotAccepted'))
      }

      runtimeActionPending.value = ''
      optimisticPauseRequested.value = false
      optimisticResumePending.value = true
      scheduleAcceptedRefresh()
    } catch (e) {
      runtimeActionPending.value = ''
      runtimeActionError.value = safeString(e?.message || e).trim() || t('runtime.timeline.errors.resumeFailed')
      console.error('[时间线] Resume from checkpoint 失败:', e)
    }
  }

  return {
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
  }
}

export default use_timeline_room_runtime_actions
