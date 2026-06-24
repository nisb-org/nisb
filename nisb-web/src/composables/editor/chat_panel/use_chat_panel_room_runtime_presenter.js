import { computed, unref } from 'vue'
import { use_chat_panel_tool_activity_presenter } from './use_chat_panel_tool_activity_presenter'
import { use_chat_panel_room_runtime_view_model } from './use_chat_panel_room_runtime_view_model'

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

export function use_chat_panel_room_runtime_presenter({
  loading,
  live,
  error,
  status_text,
  process_items,
  result_event,
  result_payload,
  result_text,
}) {
  const runtimeViewModel = use_chat_panel_room_runtime_view_model({
    process_items,
    result_event,
    result_payload,
    result_text,
  })

  const {
    has_tool_activity,
    get_tool_call_rows,
    get_tool_result_rows,
    get_tool_display_name,
    get_tool_preview,
    get_tool_status_text,
    get_tool_status_class,
  } = use_chat_panel_tool_activity_presenter()

  const displayStatusText = computed(() => {
    const explicit = safeString(unref(status_text)).trim()
    if (explicit) return explicit

    const errorText = safeString(unref(error)).trim()
    if (errorText) return errorText

    if (unref(loading)) return '加载中'
    if (unref(live)) return '运行中'
    if (runtimeViewModel.resultEntry.value || runtimeViewModel.processEntries.value.length > 0) return '可查看'
    return '暂无运行过程'
  })

  const panelEmptyState = computed(() => {
    if (safeString(unref(error)).trim()) return 'error'
    if (unref(loading) && runtimeViewModel.processEntries.value.length === 0) return 'loading'
    if (!runtimeViewModel.resultEntry.value && runtimeViewModel.processEntries.value.length === 0) return 'empty'
    return 'ready'
  })

  const panelResultState = computed(() => {
    if (safeString(unref(error)).trim()) return 'error'
    if (!runtimeViewModel.resultEntry.value) return 'empty'
    if (runtimeViewModel.resultEntry.value.type === 'room.final') return 'final'
    return 'fallback'
  })

  const normalizedResultPayload = computed(() => {
    const entry = runtimeViewModel.resultEntry.value
    if (entry?.payload && Object.keys(entry.payload).length > 0) return entry.payload
    return safeObject(unref(result_payload))
  })

  const showToolActivity = computed(() => {
    return has_tool_activity(normalizedResultPayload.value)
  })

  const toolCallRows = computed(() => {
    return safeArray(get_tool_call_rows(normalizedResultPayload.value)).map((row, idx) => ({
      key: safeString(row?._key || row?.id || `tool_call_${idx}`),
      name: get_tool_display_name(row),
      statusText: get_tool_status_text(row),
      statusClass: get_tool_status_class(row),
      preview: get_tool_preview(row),
      raw: row,
    }))
  })

  const toolResultRows = computed(() => {
    return safeArray(get_tool_result_rows(normalizedResultPayload.value)).map((row, idx) => ({
      key: safeString(row?._key || row?.id || `tool_result_${idx}`),
      name: get_tool_display_name(row),
      statusText: get_tool_status_text(row),
      statusClass: get_tool_status_class(row),
      preview: get_tool_preview(row),
      raw: row,
    }))
  })

  return {
    processEntries: runtimeViewModel.processEntries,
    resultEntry: runtimeViewModel.resultEntry,
    resultTextDisplay: runtimeViewModel.resultTextDisplay,
    resultCitations: runtimeViewModel.resultCitations,
    runtimeHeadline: runtimeViewModel.runtimeHeadline,
    runtimeBadgeSummary: runtimeViewModel.runtimeBadgeSummary,
    hasTerminalResult: runtimeViewModel.hasTerminalResult,
    latestProcessStage: runtimeViewModel.latestProcessStage,
    latestProcessActor: runtimeViewModel.latestProcessActor,
    latestProcessTime: runtimeViewModel.latestProcessTime,

    displayStatusText,
    panelEmptyState,
    panelResultState,
    showToolActivity,
    toolCallRows,
    toolResultRows,
  }
}

