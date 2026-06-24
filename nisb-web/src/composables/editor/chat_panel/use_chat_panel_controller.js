import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSettingsStore } from '../../../stores/settings'
import { useChatConfigStore } from '../../../stores/chatConfig'
import { useAgentConfigStore } from '../../../stores/agentConfig'

import { render_markdown } from './chat_panel_markdown'
import { use_chat_panel_dom } from './use_chat_panel_dom'
import { use_chat_panel_outline_controller } from './use_chat_panel_outline_controller'
import { use_chat_panel_attachments } from './use_chat_panel_attachments'
import { use_chat_panel_room_controller } from './use_chat_panel_room_controller'
import { use_chat_panel_conversation } from './use_chat_panel_conversation'
import { use_chat_panel_sender } from './use_chat_panel_sender'
import { use_chat_panel_tool_activity_presenter } from './use_chat_panel_tool_activity_presenter'

const DEFAULT_ASSISTANT_MESSAGE_ID = 'assistant_welcome'
const DEFAULT_ASSISTANT_GREETING_FALLBACK = 'Hello! I am the NISB assistant.'
const ROOM_RUNTIME_POLL_FAST_MS = 900

function create_default_messages(greeting = DEFAULT_ASSISTANT_GREETING_FALLBACK) {
  return [
    {
      id: DEFAULT_ASSISTANT_MESSAGE_ID,
      role: 'assistant',
      content: greeting,
      response: greeting,
      citations: [],
      pending: false,
      tool_calls: [],
      tool_results: [],
    },
  ]
}

function safe_array(value) {
  return Array.isArray(value) ? value : []
}

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalize_display_text(value) {
  const text = safe_string(value)
  if (!text) return ''

  return text
    .replace(/\\r\\n/g, '\n')
    .replace(/\\\\r\\\\n/g, '\n')
    .replace(/\\\\n/g, '\n')
    .replace(/\\\\r/g, '\n')
}

function resolve_default_assistant_greeting(t) {
  const key = 'chat.panel.defaultAssistantGreeting'
  let text = ''

  if (typeof t === 'function') {
    try {
      text = t(key)
    } catch {
      text = ''
    }
  }

  if (!text || text === key) return DEFAULT_ASSISTANT_GREETING_FALLBACK
  return normalize_display_text(text).trim() || DEFAULT_ASSISTANT_GREETING_FALLBACK
}

function is_default_assistant_message(item) {
  if (!item || typeof item !== 'object') return false

  const id = safe_string(item?.id).trim()
  const role = safe_string(item?.role).trim()
  if (id !== DEFAULT_ASSISTANT_MESSAGE_ID || role !== 'assistant') return false

  if (!!item?.pending) return false
  if (safe_array(item?.citations).length > 0) return false
  if (safe_array(item?.tool_calls).length > 0) return false
  if (safe_array(item?.tool_results).length > 0) return false

  return true
}

export function use_chat_panel_controller({ props, emit, call_tool, call_tool_stream }) {
  const { locale, t } = useI18n({ useScope: 'global' })

  const settings = useSettingsStore()
  const chatCfg = useChatConfigStore()
  const agentCfg = useAgentConfigStore()

  if (typeof chatCfg.hydrate === 'function') chatCfg.hydrate()
  if (typeof agentCfg.hydrate === 'function') agentCfg.hydrate()

  const chatRoot = ref(null)
  const chatMessagesEl = ref(null)
  const defaultAssistantGreeting = computed(() => resolve_default_assistant_greeting(t))

  const messages = ref(create_default_messages(defaultAssistantGreeting.value))
  const inputText = ref('')
  const isThinking = ref(false)
  const isComposing = ref(false)

  const internalConvId = ref(props.convId || null)
  const streamCtrl = ref(null)

  const selectedAttachments = ref([])

  let _forceScrollRaf1 = 0
  let _forceScrollRaf2 = 0
  let _forceScrollTimer1 = 0
  let _forceScrollTimer2 = 0
  let _forceScrollTimer3 = 0

  function renderMarkdown(text) {
    return render_markdown(normalize_display_text(text))
  }

  function clearForceScrollJobs() {
    try {
      if (_forceScrollRaf1) cancelAnimationFrame(_forceScrollRaf1)
    } catch {}
    try {
      if (_forceScrollRaf2) cancelAnimationFrame(_forceScrollRaf2)
    } catch {}
    try {
      if (_forceScrollTimer1) clearTimeout(_forceScrollTimer1)
    } catch {}
    try {
      if (_forceScrollTimer2) clearTimeout(_forceScrollTimer2)
    } catch {}
    try {
      if (_forceScrollTimer3) clearTimeout(_forceScrollTimer3)
    } catch {}

    _forceScrollRaf1 = 0
    _forceScrollRaf2 = 0
    _forceScrollTimer1 = 0
    _forceScrollTimer2 = 0
    _forceScrollTimer3 = 0
  }

  function applyBottomPosition(el, behavior = 'auto') {
    if (!el) return
    const top = el.scrollHeight || 0

    try {
      el.scrollTop = top
    } catch {}

    try {
      el.scrollTo({ top, behavior })
    } catch {
      try {
        el.scrollTop = top
      } catch {}
    }
  }

  function scrollToBottom(force = false) {
    const el = chatMessagesEl.value
    if (!el) return

    if (force) {
      clearForceScrollJobs()

      applyBottomPosition(el, 'auto')

      nextTick(() => {
        const node = chatMessagesEl.value
        if (!node) return

        applyBottomPosition(node, 'auto')

        _forceScrollRaf1 = requestAnimationFrame(() => {
          const node1 = chatMessagesEl.value
          if (!node1) return

          applyBottomPosition(node1, 'auto')

          _forceScrollRaf2 = requestAnimationFrame(() => {
            const node2 = chatMessagesEl.value
            if (!node2) return
            applyBottomPosition(node2, 'auto')
          })
        })

        _forceScrollTimer1 = window.setTimeout(() => {
          const node3 = chatMessagesEl.value
          if (!node3) return
          applyBottomPosition(node3, 'auto')
        }, 24)

        _forceScrollTimer2 = window.setTimeout(() => {
          const node4 = chatMessagesEl.value
          if (!node4) return
          applyBottomPosition(node4, 'auto')
        }, 96)

        _forceScrollTimer3 = window.setTimeout(() => {
          const node5 = chatMessagesEl.value
          if (!node5) return
          applyBottomPosition(node5, 'auto')
        }, 220)
      })

      return
    }

    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 10
    if (isAtBottom) {
      applyBottomPosition(el, 'smooth')
    }
  }

  function has_pending_assistant_message() {
    const list = Array.isArray(messages.value) ? messages.value : []
    return list.some((item) => item?.role === 'assistant' && !!item?.pending)
  }

  function has_meaningful_local_messages() {
    const list = Array.isArray(messages.value) ? messages.value : []

    return list.some((item) => {
      const role = String(item?.role || '').trim()
      const text = normalize_display_text(item?.response || item?.content).trim()

      if (role === 'user' && text) return true

      if (role === 'assistant') {
        if (is_default_assistant_message(item)) return false
        if (Array.isArray(item?.tool_calls) && item.tool_calls.length > 0) return true
        if (Array.isArray(item?.tool_results) && item.tool_results.length > 0) return true
        if (text) return true
      }

      return false
    })
  }

  const { enhance_chat_dom } = use_chat_panel_dom({
    chat_root: chatRoot,
    emit_open_lightbox: (payload) => emit('open-lightbox', payload),
  })

  const outline = use_chat_panel_outline_controller({ chat_root: chatRoot, messages })

  const attachments = use_chat_panel_attachments({
    call_tool,
    selected_attachments: selectedAttachments,
    t,
  })

  const llmConversation = use_chat_panel_conversation({
    call_tool,
    messages,
    internal_conv_id: internalConvId,
    scroll_to_bottom: scrollToBottom,
    emit_chat_outline_update: outline.emit_chat_outline_update,
    enhance_chat_dom,
  })

  const room = use_chat_panel_room_controller({
    call_tool,
    chat_cfg: chatCfg,
    props,
    messages,
    internal_conv_id: internalConvId,
    load_conversation: llmConversation.loadConversation,
    scroll_to_bottom: scrollToBottom,
    is_thinking: isThinking,
  })

  outline.set_room_outline_context({
    is_room_mode: room.isRoomMode,
    active_room_id: room.activeRoomId,
  })

  const toolPresenter = use_chat_panel_tool_activity_presenter()

  const sender = use_chat_panel_sender({
    props,
    emit,

    call_tool,
    call_tool_stream,

    settings,
    chat_cfg: chatCfg,
    agent_cfg: agentCfg,

    messages,
    input_text: inputText,
    selected_attachments: selectedAttachments,
    is_thinking: isThinking,
    is_composing: isComposing,
    stream_ctrl: streamCtrl,

    scroll_to_bottom: scrollToBottom,
    emit_chat_outline_update: outline.emit_chat_outline_update,
    enhance_chat_dom,
  })

  async function refreshRoomRuntime(opts = {}) {
    return await room.refreshRoomRuntime(opts)
  }

  async function nudgeRoomRuntimePolling(opts = {}) {
    return await room.nudgeRoomRuntimePolling(opts)
  }

  function resetRoomRuntimeLane() {
    room.resetRoomRuntimeLane()
  }

  function finishRoomRuntime(payload = {}) {
    sender.finishRoomRuntime(payload)
  }

  watch(
    () => locale.value,
    () => {
      const list = safe_array(messages.value)
      if (list.length !== 1) return

      const first = list[0]
      if (!is_default_assistant_message(first)) return

      messages.value = create_default_messages(resolve_default_assistant_greeting(t))
    }
  )

  watch(
    () => props.convId,
    (newVal) => {
      if (!newVal) return

      const next_id = String(newVal).trim()
      const prev_id = String(internalConvId.value || '').trim()

      if (!next_id || prev_id === next_id) return

      internalConvId.value = next_id

      try {
        localStorage.setItem('nisb_last_conv_id', next_id)
      } catch {}

      if (room.isRoomMode.value) return

      const is_first_assignment = !prev_id
      const should_skip_reload =
        is_first_assignment &&
        (isThinking.value || has_pending_assistant_message() || has_meaningful_local_messages())

      if (should_skip_reload) return

      llmConversation.loadConversation(next_id)
    }
  )

  watch(
    () => ({
      isRoomMode: !!room.isRoomMode.value,
      activeRoomId: safe_string(room.activeRoomId.value).trim(),
    }),
    (nextState, prevState) => {
      const isRoomMode = !!nextState?.isRoomMode
      const activeRoomId = safe_string(nextState?.activeRoomId).trim()
      const prevRoomMode = !!prevState?.isRoomMode
      const prevRoomId = safe_string(prevState?.activeRoomId).trim()

      if (!isRoomMode || !activeRoomId) {
        room.clearRoomRuntimePoller()
        return
      }

      const roomChanged = !prevRoomMode || activeRoomId !== prevRoomId
      if (!roomChanged) return

      nextTick(() => {
        room.ensureCurrentRoomRuntimeMode()
        room.pollRoomRuntimeNow({ force: true, room_id: activeRoomId })
        room.scheduleRoomRuntimePoll(ROOM_RUNTIME_POLL_FAST_MS)
      })
    },
    { immediate: true }
  )

  watch(
    () => ({
      isRoomMode: !!room.isRoomMode.value,
      activeRoomId: safe_string(room.activeRoomId.value).trim(),
      isThinking: !!isThinking.value,
    }),
    (state) => {
      if (!state?.isRoomMode || !state?.activeRoomId) {
        room.clearRoomRuntimePoller()
        return
      }

      if (room.shouldPollRoomRuntime()) {
        room.scheduleRoomRuntimePoll(state.isThinking ? 0 : ROOM_RUNTIME_POLL_FAST_MS)
        return
      }

      room.clearRoomRuntimePoller()
    },
    { immediate: true }
  )

  watch(
    () => {
      if (!room.isRoomMode.value) return ''

      const list = safe_array(messages.value)
      const last = list.length ? list[list.length - 1] : null

      return [
        safe_string(room.activeRoomId.value).trim(),
        safe_string(last?.id).trim(),
        safe_string(last?.role).trim(),
      ].join('|')
    },
    (signature, prevSignature) => {
      if (!signature || signature === prevSignature) return

      const parts = signature.split('|')
      const role = safe_string(parts[2]).trim()

      if (role !== 'user') return

      nextTick(() => {
        room.ensureCurrentRoomRuntimeMode()
        room.pollRoomRuntimeNow({ force: true })
        room.scheduleRoomRuntimePoll(0)
      })
    }
  )

  onMounted(() => {
    document.addEventListener('click', attachments.handleGlobalClick)

    if (internalConvId.value) {
      llmConversation.loadConversation(internalConvId.value)
    } else {
      const lastConvId = localStorage.getItem('nisb_last_conv_id')
      if (lastConvId) {
        internalConvId.value = lastConvId
        emit('update-conv-id', lastConvId)
        llmConversation.loadConversation(lastConvId)
      } else {
        outline.emit_chat_outline_update()
        nextTick(() => enhance_chat_dom())
      }
    }
  })

  onUnmounted(() => {
    document.removeEventListener('click', attachments.handleGlobalClick)
    clearForceScrollJobs()
    room.clearRoomRuntimePoller()
    try {
      streamCtrl.value?.abort()
    } catch {}
  })

  const filteredEntries = computed(() => attachments.filteredEntries.value)

  return {
    chatRoot,
    chatMessagesEl,
    messages,
    inputText,
    isThinking,
    isComposing,

    selectedAttachments,
    fileInput: attachments.fileInput,
    isUploading: attachments.isUploading,
    showAttachMenu: attachments.showAttachMenu,

    showFileSystemModal: attachments.showFileSystemModal,
    isLoadingFiles: attachments.isLoadingFiles,
    currentDir: attachments.currentDir,
    dirEntries: attachments.dirEntries,
    fileSearchQuery: attachments.fileSearchQuery,
    filteredEntries,

    renderMarkdown,
    getRoleLabel: room.getRoleLabel,
    getFileIcon: attachments.getFileIcon,

    isRoomMode: room.isRoomMode,
    activeRoomId: room.activeRoomId,
    hasMoreOlder: room.hasMoreOlder,
    loadingOlder: room.loadingOlder,
    roomItemsPaging: room.roomItemsPaging,
    loadRoomMessages: room.loadRoomMessages,
    loadOlderRoomMessages: room.loadOlderRoomMessages,
    requestRoomSwitch: room.requestRoomSwitch,

    roomRuntimeVisible: room.roomRuntimeVisible,
    roomRuntimeExpanded: room.roomRuntimeExpanded,
    roomRuntimeLoading: room.roomRuntimeLoading,
    roomRuntimeLive: room.roomRuntimeLive,
    roomRuntimeError: room.roomRuntimeError,
    roomRuntimeStatusText: room.roomRuntimeStatusText,
    roomRuntimeRunId: room.roomRuntimeRunId,
    roomRuntimeProcessItems: room.roomRuntimeProcessItems,
    roomRuntimeResultEvent: room.roomRuntimeResultEvent,
    roomRuntimeResultPayload: room.roomRuntimeResultPayload,
    roomRuntimeResultText: room.roomRuntimeResultText,
    roomRuntimeViewMode: room.roomRuntimeViewMode,
    roomRuntimeRunOptions: room.roomRuntimeRunOptions,
    roomRuntimeSelectedReplayRunId: room.roomRuntimeSelectedReplayRunId,
    roomRuntimeDisplayBundle: room.roomRuntimeDisplayBundle,
    roomRuntimeDisplayResultEntry: room.roomRuntimeDisplayResultEntry,
    roomRuntimeTimelineEntries: room.roomRuntimeTimelineEntries,
    roomRuntimeAuditCards: room.roomRuntimeAuditCards,
    roomRuntimeToolCallRows: room.roomRuntimeToolCallRows,
    roomRuntimeToolResultRows: room.roomRuntimeToolResultRows,
    roomRuntimeHeadline: room.roomRuntimeHeadline,
    roomRuntimeBadgeSummary: room.roomRuntimeBadgeSummary,
    roomRuntimeSkillSummary: room.roomRuntimeSkillSummary,
    roomRuntimeSkillCards: room.roomRuntimeSkillCards,
    roomRuntimeSkillActivityRows: room.roomRuntimeSkillActivityRows,

    toggleRoomRuntimeExpanded: room.toggleRoomRuntimeExpanded,
    setRoomRuntimeViewMode: room.setRoomRuntimeViewMode,
    selectRoomRuntimeReplayRun: room.selectRoomRuntimeReplayRun,

    refreshRoomRuntimeEvents: room.refreshRoomRuntimeEvents,
    refreshRoomRuntime,
    nudgeRoomRuntimePolling,
    resetRoomRuntimeLane,

    hasToolActivity: toolPresenter.has_tool_activity,
    getToolCallRows: toolPresenter.get_tool_call_rows,
    getToolResultRows: toolPresenter.get_tool_result_rows,
    getToolDisplayName: toolPresenter.get_tool_display_name,
    getToolPreview: toolPresenter.get_tool_preview,
    getToolStatusText: toolPresenter.get_tool_status_text,
    getToolStatusClass: toolPresenter.get_tool_status_class,

    toggleAttachMenu: attachments.toggleAttachMenu,
    triggerFileUpload: attachments.triggerFileUpload,
    openFileSystemPicker: attachments.openFileSystemPicker,
    closeFileSystemModal: attachments.closeFileSystemModal,
    goParentDir: attachments.goParentDir,
    enterDirectory: attachments.enterDirectory,
    selectExistingFile: attachments.selectExistingFile,
    handleFileUpload: attachments.handleFileUpload,
    removeAttachment: attachments.removeAttachment,

    onTextareaKeydown: sender.onTextareaKeydown,
    stopStreaming: sender.stopStreaming,
    finishRoomRuntime,
    sendChatMessage: sender.sendChatMessage,
    active_stream_state: sender.active_stream_state,
    stream_banner_visible: sender.stream_banner_visible,
    stream_banner_text: sender.stream_banner_text,
  }
}

export default use_chat_panel_controller

