import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h, nextTick, reactive, ref } from 'vue'
import { mount } from '@vue/test-utils'

const mocked = vi.hoisted(() => ({
  settingsStore: null,
  chatConfigStore: null,
  agentConfigStore: null,
  roomApi: null,
  attachmentsApi: null,
  gateApi: null,
  translatorApi: null,
  conversationApi: null,
  senderApi: null,
  outlineApi: null,
  domApi: null,
  toolPresenterApi: null,
  call_tool: null,
  call_tool_stream: null,
}))

vi.mock('../../../../stores/settings', () => ({
  useSettingsStore: () => mocked.settingsStore,
}))

vi.mock('../../../../stores/chatConfig', () => ({
  useChatConfigStore: () => mocked.chatConfigStore,
}))

vi.mock('../../../../stores/agentConfig', () => ({
  useAgentConfigStore: () => mocked.agentConfigStore,
}))

vi.mock('../chat_panel_markdown', () => ({
  render_markdown: vi.fn((text) => `<p>${text}</p>`),
}))

vi.mock('../use_chat_panel_dom', () => ({
  use_chat_panel_dom: () => mocked.domApi,
}))

vi.mock('../use_chat_panel_outline_controller', () => ({
  use_chat_panel_outline_controller: () => mocked.outlineApi,
}))

vi.mock('../use_chat_panel_translation_gate', () => ({
  use_chat_panel_translation_gate: () => mocked.gateApi,
}))

vi.mock('../use_chat_panel_translator', () => ({
  use_chat_panel_translator: () => mocked.translatorApi,
}))

vi.mock('../use_chat_panel_attachments', () => ({
  use_chat_panel_attachments: () => mocked.attachmentsApi,
}))

vi.mock('../use_chat_panel_room_controller', () => ({
  use_chat_panel_room_controller: () => mocked.roomApi,
}))

vi.mock('../use_chat_panel_conversation', () => ({
  use_chat_panel_conversation: () => mocked.conversationApi,
}))

vi.mock('../use_chat_panel_sender', () => ({
  use_chat_panel_sender: () => mocked.senderApi,
}))

vi.mock('../use_chat_panel_tool_activity_presenter', () => ({
  use_chat_panel_tool_activity_presenter: () => mocked.toolPresenterApi,
}))

import { use_chat_panel_controller } from '../use_chat_panel_controller'

function createMockedState() {
  return {
    settingsStore: {
      hydrate: vi.fn(),
    },

    chatConfigStore: reactive({
      hydrate: vi.fn(),
      chat: reactive({
        mode: 'chat',
        roomId: '',
      }),
    }),

    agentConfigStore: {
      hydrate: vi.fn(),
    },

    roomApi: {
      myUid: ref('user_1'),
      isRoomMode: ref(false),
      activeRoomId: ref(''),
      hasMoreOlder: ref(false),
      loadingOlder: ref(false),
      roomItemsPaging: ref({}),
      loadRoomMessages: vi.fn(),
      loadOlderRoomMessages: vi.fn(),
      requestRoomSwitch: vi.fn(),

      roomRuntimeVisible: ref(true),
      roomRuntimeExpanded: ref(true),
      roomRuntimeLoading: ref(false),
      roomRuntimeLive: ref(false),
      roomRuntimeError: ref(''),
      roomRuntimeStatusText: ref(''),
      roomRuntimeRunId: ref(''),
      roomRuntimeProcessItems: ref([]),
      roomRuntimeResultEvent: ref(null),
      roomRuntimeResultPayload: ref({}),
      roomRuntimeResultText: ref(''),
      roomRuntimeViewMode: ref('current'),
      roomRuntimeRunOptions: ref([]),
      roomRuntimeSelectedReplayRunId: ref(''),

      getRoleLabel: vi.fn(() => '🤖 AI'),
      toggleRoomRuntimeExpanded: vi.fn(),
      setRoomRuntimeViewMode: vi.fn(),
      selectRoomRuntimeReplayRun: vi.fn(),
      resetRoomRuntimeLane: vi.fn(),
      clearRoomRuntimePoller: vi.fn(),
      ensureCurrentRoomRuntimeMode: vi.fn(),
      shouldPollRoomRuntime: vi.fn(() => false),
      pollRoomRuntimeNow: vi.fn(),
      scheduleRoomRuntimePoll: vi.fn(),
      refreshRoomRuntimeEvents: vi.fn(),
      refreshRoomRuntime: vi.fn(),
      nudgeRoomRuntimePolling: vi.fn(),
    },

    attachmentsApi: {
      filteredEntries: ref([]),
      fileInput: ref(null),
      isUploading: ref(false),
      showAttachMenu: ref(false),
      showFileSystemModal: ref(false),
      isLoadingFiles: ref(false),
      currentDir: ref(''),
      dirEntries: ref([]),
      fileSearchQuery: ref(''),
      handleGlobalClick: vi.fn(),
      getFileIcon: vi.fn(() => '📄'),
      toggleAttachMenu: vi.fn(),
      triggerFileUpload: vi.fn(),
      openFileSystemPicker: vi.fn(),
      closeFileSystemModal: vi.fn(),
      goParentDir: vi.fn(),
      enterDirectory: vi.fn(),
      selectExistingFile: vi.fn(),
      handleFileUpload: vi.fn(),
      removeAttachment: vi.fn(),
    },

    gateApi: {
      get_query_translate_enabled: vi.fn(() => false),
      get_query_translate_model: vi.fn(() => ''),
    },

    translatorApi: {
      translate_to_english: vi.fn(async (text) => text),
      translate_to_original_lang: vi.fn(async (text) => text),
    },

    conversationApi: {
      loadConversation: vi.fn(),
    },

    senderApi: {
      onTextareaKeydown: vi.fn(),
      stopStreaming: vi.fn(),
      sendChatMessage: vi.fn(),
    },

    outlineApi: {
      emit_chat_outline_update: vi.fn(),
    },

    domApi: {
      enhance_chat_dom: vi.fn(),
    },

    toolPresenterApi: {
      has_tool_activity: vi.fn(() => false),
      get_tool_call_rows: vi.fn(() => []),
      get_tool_result_rows: vi.fn(() => []),
      get_tool_display_name: vi.fn(() => ''),
      get_tool_preview: vi.fn(() => ''),
      get_tool_status_text: vi.fn(() => ''),
      get_tool_status_class: vi.fn(() => ''),
    },

    call_tool: vi.fn(),
    call_tool_stream: vi.fn(),
  }
}

function mountHarness(initialProps = { convId: '' }) {
  const Harness = defineComponent({
    props: {
      convId: {
        type: String,
        default: '',
      },
    },
    emits: ['update-conv-id', 'open-lightbox'],
    setup(props, { emit }) {
      return use_chat_panel_controller({
        props,
        emit,
        call_tool: mocked.call_tool,
        call_tool_stream: mocked.call_tool_stream,
      })
    },
    render() {
      return h('div')
    },
  })

  return mount(Harness, {
    props: initialProps,
  })
}

describe('use_chat_panel_controller', () => {
  beforeEach(() => {
    Object.assign(mocked, createMockedState())
    localStorage.clear()
  })

  it('loads conversation when convId changes in normal chat mode', async () => {
    const wrapper = mountHarness({ convId: '' })

    await nextTick()

    await wrapper.setProps({ convId: 'conv_123' })
    await nextTick()

    expect(mocked.conversationApi.loadConversation).toHaveBeenCalledWith('conv_123')
  })

  it('starts room runtime polling when entering room mode with a room id', async () => {
    const wrapper = mountHarness({ convId: '' })

    mocked.roomApi.isRoomMode.value = true
    mocked.roomApi.activeRoomId.value = 'room_1'

    await nextTick()
    await Promise.resolve()
    await nextTick()

    expect(mocked.roomApi.ensureCurrentRoomRuntimeMode).toHaveBeenCalled()
    expect(mocked.roomApi.pollRoomRuntimeNow).toHaveBeenCalledWith({
      force: true,
      room_id: 'room_1',
    })
    expect(mocked.roomApi.scheduleRoomRuntimePoll).toHaveBeenCalledWith(900)

    wrapper.unmount()
  })

  it('nudges current runtime immediately when a new user message appears in room mode', async () => {
    const wrapper = mountHarness({ convId: '' })

    mocked.roomApi.isRoomMode.value = true
    mocked.roomApi.activeRoomId.value = 'room_1'

    await nextTick()
    await Promise.resolve()
    await nextTick()

    mocked.roomApi.pollRoomRuntimeNow.mockClear()
    mocked.roomApi.scheduleRoomRuntimePoll.mockClear()
    mocked.roomApi.ensureCurrentRoomRuntimeMode.mockClear()

    wrapper.vm.messages = [
      {
        id: 'user_msg_1',
        role: 'user',
        response: '边界之神与原型转移',
      },
    ]

    await nextTick()
    await Promise.resolve()
    await nextTick()

    expect(mocked.roomApi.ensureCurrentRoomRuntimeMode).toHaveBeenCalled()
    expect(mocked.roomApi.pollRoomRuntimeNow).toHaveBeenCalledWith({ force: true })
    expect(mocked.roomApi.scheduleRoomRuntimePoll).toHaveBeenCalledWith(0)

    wrapper.unmount()
  })
})

