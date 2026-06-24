import { describe, it, expect, beforeEach, vi } from 'vitest'
import { effectScope, reactive, nextTick } from 'vue'

const mocked = vi.hoisted(() => ({
  store: null,
  runtimeReader: null,
}))

vi.mock('../../../../stores/room', () => ({
  useRoomStore: () => mocked.store,
}))

vi.mock('../use_chat_panel_room_runtime_reader', () => ({
  use_chat_panel_room_runtime_reader: () => mocked.runtimeReader,
}))

import { use_chat_panel_room_controller } from '../use_chat_panel_room_controller'

function createStore() {
  return reactive({
    hasMoreOlder: false,
    loadingOlder: false,
    itemsPagingState: {},
    runtimeViewMode: 'current',
    runtimeSelectedReplayRunId: '',
    runtimeRunOptions: [],
    runtimeState: {
      expanded: true,
      loading: false,
      error: '',
      replay_loading: false,
      replay_error: '',
      visible: true,
    },
    runtimeVisible: true,
    runtimeLive: undefined,
    currentRunStatus: '',
    currentRunId: '',
    runtimeDisplayProcessItems: null,
    runtimeProcessItems: null,
    items: [],
    runtimeDisplayResultEvent: null,
    runtimeResultEvent: null,
    runtimeDisplayResultPayload: null,
    runtimeDisplayResultText: '',
    runtimeDisplayRunId: '',
    runtimeRunId: '',
    runtimeStatusText: '',
    refreshWhoAmI: vi.fn(async () => ({ uid: 'user_1', basepath: '/tmp/basepath' })),
    resetRoom: vi.fn(),
    setRuntimeExpanded: vi.fn(),
    setWhoAmI: vi.fn(),
  })
}

function createRuntimeReader() {
  return {
    stopRuntimeReader: vi.fn(),
    requestRoomSwitch: vi.fn(async () => {}),
    setRoomRuntimeViewMode: vi.fn(),
    selectRoomRuntimeReplayRun: vi.fn(),
    resetRoomRuntimeLane: vi.fn(),
    clearRoomRuntimePoller: vi.fn(),
    shouldPollRoomRuntime: vi.fn(() => false),
    pollRoomRuntimeNow: vi.fn(),
    scheduleRoomRuntimePoll: vi.fn(),
    refreshRoomRuntimeEvents: vi.fn(),
    refreshRoomRuntimeReplay: vi.fn(),
    refreshRoomRuntime: vi.fn(),
    nudgeRoomRuntimePolling: vi.fn(),
    loadRoomMessages: vi.fn(),
    loadOlderRoomMessages: vi.fn(),
  }
}

describe('use_chat_panel_room_controller', () => {
  beforeEach(() => {
    mocked.store = createStore()
    mocked.runtimeReader = createRuntimeReader()
    localStorage.clear()
  })

  it('derives runtime process items and final result event from store items', async () => {
    const chat_cfg = reactive({
      chat: {
        mode: 'room',
        roomId: 'room_1',
      },
    })

    mocked.store.items = [
      {
        id: 'evt-user',
        type: 'room.message',
        payload: { sender_type: 'user', response: '用户消息' },
      },
      {
        id: 'evt-plan',
        type: 'room.plan',
        run_id: 'run_1',
        payload: { summary: '计划' },
      },
      {
        id: 'evt-supervisor',
        type: 'room.supervisor',
        run_id: 'run_1',
        payload: { message: '综合中' },
      },
      {
        id: 'evt-final',
        type: 'room.final',
        run_id: 'run_1',
        payload: { response: '最终回答' },
      },
    ]

    let api
    const scope = effectScope()
    scope.run(() => {
      api = use_chat_panel_room_controller({
        call_tool: vi.fn(),
        chat_cfg,
        props: reactive({ convId: '' }),
        messages: reactive({ value: [] }),
        internal_conv_id: reactive({ value: null }),
        load_conversation: vi.fn(),
        scroll_to_bottom: vi.fn(),
        is_thinking: reactive({ value: false }),
      })
    })

    await nextTick()

    expect(api.roomRuntimeProcessItems.value.map((x) => x.id)).toEqual([
      'evt-plan',
      'evt-supervisor',
      'evt-final',
    ])
    expect(api.roomRuntimeResultEvent.value.id).toBe('evt-final')
    expect(api.roomRuntimeResultPayload.value.response).toBe('最终回答')
    expect(api.roomRuntimeResultText.value).toBe('最终回答')
    expect(api.roomRuntimeRunId.value).toBe('run_1')
    expect(api.roomRuntimeStatusText.value).toBe('已完成')

    scope.stop()
  })

  it('treats replay mode as non-live and current running mode as live', async () => {
    const chat_cfg = reactive({
      chat: {
        mode: 'room',
        roomId: 'room_1',
      },
    })

    mocked.store.currentRunStatus = 'running'
    mocked.store.currentRunId = 'run_live'
    mocked.store.runtimeViewMode = 'current'

    let api
    let scope = effectScope()
    scope.run(() => {
      api = use_chat_panel_room_controller({
        call_tool: vi.fn(),
        chat_cfg,
        props: reactive({ convId: '' }),
        messages: reactive({ value: [] }),
        internal_conv_id: reactive({ value: null }),
        load_conversation: vi.fn(),
        scroll_to_bottom: vi.fn(),
        is_thinking: reactive({ value: false }),
      })
    })

    await nextTick()
    expect(api.roomRuntimeLive.value).toBe(true)
    scope.stop()

    mocked.store.runtimeViewMode = 'replay'
    scope = effectScope()
    scope.run(() => {
      api = use_chat_panel_room_controller({
        call_tool: vi.fn(),
        chat_cfg,
        props: reactive({ convId: '' }),
        messages: reactive({ value: [] }),
        internal_conv_id: reactive({ value: null }),
        load_conversation: vi.fn(),
        scroll_to_bottom: vi.fn(),
        is_thinking: reactive({ value: false }),
      })
    })

    await nextTick()
    expect(api.roomRuntimeLive.value).toBe(false)
    scope.stop()
  })

  it('requests room switch when entering a room and loads whoami into local identity', async () => {
    const chat_cfg = reactive({
      chat: {
        mode: 'chat',
        roomId: '',
      },
    })

    let api
    const scope = effectScope()
    scope.run(() => {
      api = use_chat_panel_room_controller({
        call_tool: vi.fn(),
        chat_cfg,
        props: reactive({ convId: '' }),
        messages: reactive({ value: [] }),
        internal_conv_id: reactive({ value: null }),
        load_conversation: vi.fn(),
        scroll_to_bottom: vi.fn(),
        is_thinking: reactive({ value: false }),
      })
    })

    await nextTick()
    await Promise.resolve()

    expect(mocked.store.refreshWhoAmI).toHaveBeenCalledTimes(1)

    chat_cfg.chat.mode = 'room'
    chat_cfg.chat.roomId = 'room_99'

    await nextTick()
    await Promise.resolve()

    expect(mocked.runtimeReader.requestRoomSwitch).toHaveBeenCalledWith('room_99')
    expect(api.activeRoomId.value).toBe('room_99')
    expect(api.isRoomMode.value).toBe(true)

    scope.stop()
  })
})

