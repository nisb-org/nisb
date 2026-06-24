<template>
  <div class="room-wrapper" ref="rootRef">
    <button
      class="room-btn"
      type="button"
      :disabled="disabled || busy"
      :class="{ 'toggle-on': is_room_mode, open: show_menu }"
      @click="toggle_menu"
      :title="is_room_mode ? t('chat.roomMenu.button.activeTitle', { title: current_room_title }) : t('chat.roomMenu.button.title')"
      :aria-label="t('chat.roomMenu.button.ariaLabel')"
      aria-haspopup="menu"
      :aria-expanded="show_menu ? 'true' : 'false'"
    >
      <span class="room-icon" aria-hidden="true">🫧</span>
      <span class="btn-text">{{ t('chat.roomMenu.button.text') }}</span>
      <span v-if="is_room_mode" class="btn-chip">{{ t('chat.roomMenu.button.on') }}</span>
      <span class="btn-caret" aria-hidden="true">▾</span>
    </button>

    <Teleport to="body">
      <div
        v-if="show_menu"
        class="room-popover-scrim"
        aria-hidden="true"
        @click.stop="close_menu"
      ></div>

      <div
        v-if="show_menu"
        ref="menuRef"
        class="room-menu room-menu-floating"
        :style="menu_style"
        role="menu"
        :aria-label="t('chat.roomMenu.button.ariaLabel')"
        @click.stop
      >
        <div class="menu-header">
          <div class="menu-title-wrap">
            <div class="menu-title">{{ t('chat.roomMenu.header.title') }}</div>
            <div class="menu-subtitle">
              {{ t('chat.roomMenu.header.currentMode') }}
              <strong>{{ t(is_room_mode ? 'chat.roomMenu.modes.room' : 'chat.roomMenu.modes.llm') }}</strong>
            </div>

            <div class="menu-status-row" aria-live="polite">
              <span class="status-chip primary">
                {{ t(is_room_mode ? 'chat.roomMenu.modes.room' : 'chat.roomMenu.modes.llm') }}
              </span>
              <span v-if="is_room_mode && current_room_is_federated" class="status-chip accent">
                {{ t('chat.roomMenu.status.federatedRoom', { label: current_room_federated_label }) }}
              </span>
              <span v-else-if="is_room_mode" class="status-chip">
                {{ t('chat.roomMenu.status.localRoom') }}
              </span>
              <span v-else class="status-chip">
                {{ t('chat.roomMenu.status.noActiveRoom') }}
              </span>
              <span v-if="current_room_run_id" class="status-chip warn">
                {{ t('chat.roomMenu.status.activeRun') }}
              </span>
            </div>

            <div class="room-boundary-card">
              <div class="room-boundary-title">{{ t('chat.roomMenu.boundary.title') }}</div>
              <div class="room-boundary-chips">
                <span class="boundary-chip">{{ t('chat.roomMenu.boundary.roomRuntime') }}</span>
                <span class="boundary-chip">{{ t('chat.roomMenu.boundary.roles') }}</span>
                <span class="boundary-chip">{{ t('chat.roomMenu.boundary.supervisor') }}</span>
                <span class="boundary-chip">{{ t('chat.roomMenu.boundary.federationSnapshot') }}</span>
              </div>
              <div class="room-boundary-hint">{{ t('chat.roomMenu.boundary.hint') }}</div>
            </div>
          </div>

          <div class="menu-actions">
            <button class="mini-btn" type="button" @click="refresh_rooms" :disabled="busy || loading_rooms">
              {{ loading_rooms ? t('chat.roomMenu.actions.refreshing') : t('chat.roomMenu.actions.refresh') }}
            </button>

            <button
              v-if="is_room_mode"
              class="mini-btn"
              type="button"
              @click="refresh_current_room"
              :disabled="busy || refreshing_current_room || !active_room_id"
            >
              {{ refreshing_current_room ? t('chat.roomMenu.actions.syncingCurrent') : t('chat.roomMenu.actions.syncCurrent') }}
            </button>

            <button
              v-if="is_room_mode"
              class="mini-btn danger"
              type="button"
              @click="exit_room"
              :disabled="busy"
            >
              {{ t('chat.roomMenu.actions.exit') }}
            </button>
          </div>
        </div>

        <div v-if="error_text" class="menu-error">
          {{ error_text }}
        </div>

        <div v-if="is_room_mode && current_room_card" class="menu-section">
          <div class="section-title">{{ t('chat.roomMenu.sections.current') }}</div>

          <div class="current-room-card">
            <div class="current-room-top">
              <div class="current-room-title-wrap">
                <div class="current-room-title">{{ current_room_title }}</div>
                <div class="current-room-id mono">{{ active_room_id }}</div>
              </div>

              <div class="current-room-badges">
                <span class="meta-chip strong">{{ t('chat.roomMenu.current.participants', { count: current_room_participants_count }) }}</span>
                <span class="meta-chip strong">{{ t('chat.roomMenu.current.roles', { count: current_room_roles_count }) }}</span>
                <span class="meta-chip strong" :class="{ accent: current_room_active_roles_count > 0 }">
                  {{ t('chat.roomMenu.current.activeRoles', { count: current_room_active_roles_count }) }}
                </span>
              </div>
            </div>

            <div class="current-room-flags">
              <span v-if="current_room_supervisor_enabled" class="flag-chip">{{ t('chat.roomMenu.current.supervisorEnabled') }}</span>
              <span v-if="current_room_inherit_workspace_context" class="flag-chip">{{ t('chat.roomMenu.current.inheritWorkspaceContext') }}</span>
              <span v-if="current_room_inherit_focus_root" class="flag-chip">{{ t('chat.roomMenu.current.inheritFocusRoot') }}</span>
              <span v-if="current_room_default_role_name" class="flag-chip">
                {{ t('chat.roomMenu.current.defaultRole', { name: current_room_default_role_name }) }}
              </span>
              <span v-if="current_room_is_federated" class="flag-chip federated-flag">
                {{ t('chat.roomMenu.current.federatedLabel', { label: current_room_federated_label }) }}
              </span>
            </div>

            <div v-if="current_room_run_id" class="run-box">
              <div class="run-row">
                <span class="run-label">{{ t('chat.roomMenu.current.runId') }}</span>
                <span class="run-value mono">{{ current_room_run_id }}</span>
                <span class="running-dot" />
              </div>
            </div>

            <div v-if="current_room_last_plan_summary" class="plan-box">
              <div class="plan-label">{{ t('chat.roomMenu.current.latestPlan') }}</div>
              <div class="plan-text">{{ current_room_last_plan_summary }}</div>
            </div>

            <div class="row-actions">
              <button class="ghost-btn" type="button" @click="copy_text(active_room_id)">
                {{ t('chat.roomMenu.actions.copyRoomId') }}
              </button>

              <button
                class="ghost-btn"
                type="button"
                @click="copy_text(current_room_join_key)"
                :disabled="!current_room_join_key"
              >
                {{ t('chat.roomMenu.actions.copyJoinKey') }}
              </button>

              <button
                class="ghost-btn"
                type="button"
                @click="refresh_current_room"
                :disabled="busy || refreshing_current_room || !active_room_id"
              >
                {{ t('chat.roomMenu.actions.refreshDetails') }}
              </button>
            </div>
          </div>
        </div>

        <div class="menu-section">
          <div class="section-title">{{ t('chat.roomMenu.sections.create') }}</div>

          <label class="field">
            <span>{{ t('chat.roomMenu.create.titleLabel') }}</span>
            <input
              v-model="create_form.title"
              type="text"
              :placeholder="t('chat.roomMenu.create.titlePlaceholder')"
              :disabled="busy"
              @keydown.enter.prevent="submit_create"
            />
          </label>

          <label class="field">
            <span>{{ t('chat.roomMenu.create.participantsLabel') }}</span>
            <input
              v-model="create_form.participants_text"
              type="text"
              :placeholder="t('chat.roomMenu.create.participantsPlaceholder')"
              :disabled="busy"
              @keydown.enter.prevent="submit_create"
            />
          </label>

          <div class="row-actions">
            <button class="primary-btn" type="button" @click="submit_create" :disabled="busy">
              {{ busy ? t('chat.roomMenu.actions.processing') : t('chat.roomMenu.actions.createAndEnter') }}
            </button>
          </div>

          <div v-if="created_room.room_id" class="created-box">
            <div class="created-line">
              <span class="label">{{ t('chat.roomMenu.create.createdRoomId') }}</span>
              <span class="value mono">{{ created_room.room_id }}</span>
            </div>

            <div class="created-line">
              <span class="label">{{ t('chat.roomMenu.create.createdJoinKey') }}</span>
              <span class="value mono">{{ created_room.join_key || t('chat.roomMenu.create.emptyValue') }}</span>
            </div>

            <div class="row-actions">
              <button
                class="ghost-btn"
                type="button"
                @click="copy_text(created_room.join_key)"
                :disabled="!created_room.join_key"
              >
                {{ t('chat.roomMenu.actions.copyJoinKey') }}
              </button>
            </div>
          </div>
        </div>

        <div class="menu-section">
          <div class="section-title">{{ t('chat.roomMenu.sections.join') }}</div>

          <label class="field">
            <span>{{ t('chat.roomMenu.join.roomIdLabel') }}</span>
            <input
              v-model="join_form.room_id"
              type="text"
              :placeholder="t('chat.roomMenu.join.roomIdPlaceholder')"
              :disabled="busy"
              @keydown.enter.prevent="submit_join"
            />
          </label>

          <label class="field">
            <span>{{ t('chat.roomMenu.join.joinKeyLabel') }}</span>
            <input
              v-model="join_form.join_key"
              type="text"
              :placeholder="t('chat.roomMenu.join.joinKeyPlaceholder')"
              :disabled="busy"
              @keydown.enter.prevent="submit_join"
            />
          </label>

          <div class="row-actions">
            <button class="primary-btn" type="button" @click="submit_join" :disabled="busy">
              {{ t('chat.roomMenu.actions.joinAndEnter') }}
            </button>
          </div>
        </div>

        <div class="menu-section">
          <div class="section-title">{{ t('chat.roomMenu.sections.recent') }}</div>

          <RoomRecentRoomsList
            :loading="loading_rooms"
            :items="merged_recent_rooms"
            :active-room-id="active_room_id"
            @enter="enter_room"
            @copy-key="copy_text"
          />
        </div>

        <div class="menu-footer">
          <div class="footer-text">{{ t('chat.roomMenu.footer.closeHint') }}</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../../composables/useMCP'
import { useChatConfigStore } from '../../../../stores/chatConfig'
import { useRoomStore } from '../../../../stores/room'
import RoomRecentRoomsList from './RoomRecentRoomsList.vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const { t } = useI18n()
const { callTool } = useMCP()
const chat_cfg = useChatConfigStore()
const room_store = useRoomStore()

const rootRef = ref(null)
const menuRef = ref(null)
const show_menu = ref(false)
const busy = ref(false)
const loading_rooms = ref(false)
const refreshing_current_room = ref(false)
const error_text = ref('')
const rooms = ref([])
const joined_rooms = ref([])
const menu_style = ref({
  left: '8px',
  top: '8px',
  width: '460px',
  maxHeight: '78vh',
})

const create_form = reactive({
  title: t('chat.roomMenu.create.defaults.title'),
  participants_text: '',
})

const join_form = reactive({
  room_id: '',
  join_key: '',
})

const created_room = reactive({
  room_id: '',
  join_key: '',
})

const is_room_mode = computed(() => String(chat_cfg.chat?.mode || '') === 'room')
const active_room_id = computed(() => String(chat_cfg.chat?.roomId || '').trim())

const current_room_card = computed(() => room_store.room || null)
const current_room_title = computed(() => String(room_store.room?.title || active_room_id.value || t('chat.roomMenu.current.fallbackTitle')))
const current_room_join_key = computed(() => String(room_store.room?.join_key || ''))
const current_room_participants_count = computed(() =>
  Array.isArray(room_store.room?.participants) ? room_store.room.participants.length : 0
)
const current_room_roles_count = computed(() =>
  Array.isArray(room_store.roles) ? room_store.roles.length : 0
)
const current_room_active_roles_count = computed(() =>
  Array.isArray(room_store.roomState?.active_roles) ? room_store.roomState.active_roles.length : 0
)
const current_room_supervisor_enabled = computed(() => !!room_store.roomState?.supervisor_enabled)
const current_room_inherit_workspace_context = computed(() => !!room_store.roomState?.inherit_workspace_context)
const current_room_inherit_focus_root = computed(() => !!room_store.roomState?.inherit_focus_root)
const current_room_run_id = computed(() => String(room_store.roomState?.current_run_id || '').trim())
const current_room_is_federated = computed(() => room_store.isFederatedRoom(active_room_id.value))
const current_room_federated_label = computed(() => {
  const session = room_store.federationRoomSession || {}
  return String(session.remote_label || session.peer_id || 'peer').trim()
})

const current_room_default_role_name = computed(() => {
  const roleId = String(room_store.roomState?.default_reply_role_id || '').trim()
  if (!roleId) return ''
  const role = Array.isArray(room_store.roles)
    ? room_store.roles.find((r) => String(r?.role_id || '') === roleId)
    : null
  return String(role?.name || role?.slug || roleId)
})

const current_room_last_plan_summary = computed(() => {
  const evt = room_store.lastPlanEvent
  return String(evt?.payload?.plan_summary || '').trim()
})

const merged_recent_rooms = computed(() => {
  const activeRid = active_room_id.value
  const activeTitle = String(room_store.room?.title || '').trim()

  return [...rooms.value, ...joined_rooms.value].map((row) => {
    if (
      activeRid &&
      activeTitle &&
      String(row?.room_id || '').trim() === activeRid &&
      !String(row?.display_title || row?.title || '').trim()
    ) {
      return {
        ...row,
        display_title: activeTitle,
      }
    }
    return row
  })
})

let menu_raf = 0
let menu_resize_observer = null

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function safe_array(v) {
  return Array.isArray(v) ? v : []
}

function safe_object(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function pick_primary_payload(res) {
  const root = safe_object(res)
  const candidates = [
    safe_object(root.data),
    safe_object(root.payload),
    safe_object(root.result),
    root,
  ]

  for (const item of candidates) {
    if (Object.keys(item).length > 0) return item
  }

  return {}
}

function normalized_status_from(res) {
  const root = safe_object(res)
  const payload = pick_primary_payload(res)
  const candidates = [
    payload.status,
    root.status,
  ]

  for (const raw of candidates) {
    const s = safe_string(raw).trim().toLowerCase()
    if (!s) continue
    if (['ok', 'success', 'succeeded'].includes(s)) return 'success'
    if (['warning', 'partial_success', 'partial_error'].includes(s)) return 'warning'
    if (['error', 'failed', 'fail'].includes(s)) return 'error'
    return s
  }

  if (payload.success === false || root.success === false) return 'error'
  return 'success'
}

function assert_tool_success(res, fallback_message = t('chat.roomMenu.errors.operationFailed')) {
  const root = safe_object(res)
  const payload = pick_primary_payload(res)
  const status = normalized_status_from(res)

  if (status && status !== 'success' && status !== 'warning') {
    throw new Error(
      safe_string(payload?.message || root?.message || fallback_message) || fallback_message
    )
  }

  if (payload.success === false || root.success === false) {
    throw new Error(
      safe_string(payload?.message || root?.message || fallback_message) || fallback_message
    )
  }

  return payload
}

function pick_first_tool_result(data, matcher) {
  const rows = safe_array(data?.tool_results)
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    if (matcher(row)) return row
  }
  return null
}

function extract_room_list(data) {
  const row = pick_first_tool_result(
    data,
    (x) => x.type === 'room_list' && Array.isArray(x.rooms)
  )
  if (row) return safe_array(row.rooms)
  return safe_array(data?.rooms)
}

function extract_room_info(data) {
  const row = pick_first_tool_result(
    data,
    (x) => x.type === 'room_info' && typeof x.room === 'object'
  )

  if (row) {
    return {
      room: row.room || null,
      roles: safe_array(row.roles),
      state: safe_object(row.state),
    }
  }

  const top_room = data?.room && typeof data.room === 'object' ? data.room : null
  const top_roles = Array.isArray(data?.roles) ? data.roles : []
  const top_state = data?.state && typeof data.state === 'object' ? data.state : {}

  return {
    room: top_room,
    roles: top_roles,
    state: top_state,
  }
}

function participants_count(room) {
  return Array.isArray(room?.participants) ? room.participants.length : 0
}

function normalize_local_rooms(items) {
  return safe_array(items)
    .filter((room) => room && typeof room === 'object')
    .map((room) => {
      const room_id = safe_string(room.room_id).trim()
      return {
        ...room,
        room_id,
        join_key: safe_string(room.join_key).trim(),
        participants_count: participants_count(room),
        display_title: safe_string(room.title).trim() || room_id,
        _room_kind: 'local',
        _menu_key: `local:${room_id}`,
      }
    })
}

function normalize_joined_rooms(items) {
  return safe_array(items)
    .filter((room) => room && typeof room === 'object' && room.enabled !== false)
    .map((room) => {
      const room_id = safe_string(room.room_id).trim()
      const peer_id = safe_string(room.peer_id).trim()
      const target_peer_id = safe_string(room.target_peer_id).trim()
      const owner_room_id = safe_string(room.owner_room_id).trim() || room_id
      const local_owner_user_id = safe_string(room.local_owner_user_id || room.owner_user_id).trim()
      const owner_user_id = safe_string(room.owner_user_id || room.local_owner_user_id).trim()
      const count = Number(room.participants_count)

      return {
        ...room,
        room_id,
        peer_id,
        target_peer_id,
        owner_room_id,
        remote_user_id: safe_string(room.remote_user_id).trim(),
        local_owner_user_id,
        owner_user_id,
        remote_label: safe_string(room.remote_label).trim(),
        join_key: safe_string(room.join_key).trim(),
        participants_count: Number.isFinite(count) && count >= 0 ? count : 0,
        display_title: safe_string(room.title).trim() || room_id,
        _room_kind: 'federated',
        _menu_key: `fed:${peer_id}:${room_id}`,
      }
    })
}

function parse_participants_text(text) {
  return String(text || '')
    .split(',')
    .map((s) => String(s || '').trim())
    .filter(Boolean)
}

function reset_created_room() {
  created_room.room_id = ''
  created_room.join_key = ''
}

function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max)
}

function cleanup_menu_raf() {
  if (menu_raf) {
    cancelAnimationFrame(menu_raf)
    menu_raf = 0
  }
}

function cleanup_resize_observer() {
  if (menu_resize_observer) {
    try {
      menu_resize_observer.disconnect()
    } catch {}
    menu_resize_observer = null
  }
}

function compute_menu_position() {
  const anchorEl = rootRef.value
  const menuEl = menuRef.value
  if (!show_menu.value || !anchorEl || !menuEl) return

  const rect = anchorEl.getBoundingClientRect()
  const vw = window.innerWidth || document.documentElement.clientWidth || 0
  const vh = window.innerHeight || document.documentElement.clientHeight || 0

  const gutter = 8
  const gap = 8
  const availableWidth = Math.max(260, vw - gutter * 2)
  const preferredWidth = 500
  const width = Math.min(preferredWidth, availableWidth)

  const preferredMaxHeight = Math.floor(vh * 0.78)
  const spaceAbove = Math.max(0, Math.floor(rect.top - gap - gutter))
  const spaceBelow = Math.max(0, Math.floor(vh - rect.bottom - gap - gutter))

  let placement = 'above'
  if (spaceAbove < 280 && spaceBelow > spaceAbove) placement = 'below'
  else if (spaceBelow >= 360 && spaceBelow > spaceAbove) placement = 'below'

  let maxHeight = Math.min(preferredMaxHeight, placement === 'above' ? spaceAbove : spaceBelow)
  if (maxHeight < 240) {
    const useBelow = spaceBelow >= spaceAbove
    placement = useBelow ? 'below' : 'above'
    maxHeight = Math.min(preferredMaxHeight, useBelow ? spaceBelow : spaceAbove)
  }

  maxHeight = Math.max(220, Math.min(maxHeight || preferredMaxHeight, Math.max(220, vh - gutter * 2)))

  const measuredHeight = Math.min(menuEl.scrollHeight || menuEl.offsetHeight || maxHeight, maxHeight)
  const left = clamp(Math.round(rect.left), gutter, Math.max(gutter, vw - width - gutter))

  let top = placement === 'above'
    ? Math.round(rect.top - gap - measuredHeight)
    : Math.round(rect.bottom + gap)

  top = clamp(top, gutter, Math.max(gutter, vh - measuredHeight - gutter))

  menu_style.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
  }
}

function schedule_menu_position() {
  cleanup_menu_raf()
  menu_raf = requestAnimationFrame(() => {
    compute_menu_position()
  })
}

function bind_menu_resize_observer() {
  cleanup_resize_observer()
  if (typeof ResizeObserver === 'undefined') return

  const menuEl = menuRef.value
  const anchorEl = rootRef.value
  if (!menuEl && !anchorEl) return

  menu_resize_observer = new ResizeObserver(() => {
    schedule_menu_position()
  })

  if (menuEl) menu_resize_observer.observe(menuEl)
  if (anchorEl) menu_resize_observer.observe(anchorEl)
}

function toggle_menu() {
  if (props.disabled || busy.value) return
  show_menu.value = !show_menu.value

  if (show_menu.value) {
    refresh_rooms()
    if (active_room_id.value) {
      refresh_current_room()
    }
  }
}

function close_menu() {
  show_menu.value = false
}

function handle_click_outside(event) {
  if (!show_menu.value) return

  const rootEl = rootRef.value
  const menuEl = menuRef.value
  const target = event.target

  if (rootEl && rootEl.contains(target)) return
  if (menuEl && menuEl.contains(target)) return

  close_menu()
}

function handle_keydown(event) {
  if (event.key === 'Escape') {
    close_menu()
  }
}

function handle_window_relayout() {
  if (!show_menu.value) return
  schedule_menu_position()
}

async function refresh_rooms() {
  loading_rooms.value = true
  error_text.value = ''

  try {
    const [localResult, joinedResult] = await Promise.allSettled([
      callTool('nisb_room_shared_list', {}),
      callTool('nisb_fed_list_joined_rooms', {}),
    ])

    let next_error = ''

    if (localResult.status === 'fulfilled') {
      try {
        const data = assert_tool_success(localResult.value, t('chat.roomMenu.errors.loadRoomsFailed'))
        rooms.value = normalize_local_rooms(extract_room_list(data))
      } catch (err) {
        rooms.value = []
        next_error = err?.message || String(err)
      }
    } else {
      rooms.value = []
      next_error = localResult.reason?.message || String(localResult.reason || t('chat.roomMenu.errors.loadRoomsFailed'))
    }

    if (joinedResult.status === 'fulfilled') {
      try {
        const data = assert_tool_success(joinedResult.value, t('chat.roomMenu.errors.loadRoomsFailed'))
        joined_rooms.value = normalize_joined_rooms(data?.rooms)
      } catch {
        joined_rooms.value = []
      }
    } else {
      joined_rooms.value = []
    }

    error_text.value = next_error
  } catch (err) {
    error_text.value = err?.message || String(err)
    rooms.value = []
    joined_rooms.value = []
  } finally {
    loading_rooms.value = false
    if (show_menu.value) {
      nextTick(() => {
        schedule_menu_position()
      })
    }
  }
}

async function refresh_current_room() {
  const rid = String(active_room_id.value || '').trim()
  if (!rid) return

  refreshing_current_room.value = true
  error_text.value = ''

  try {
    await room_store.loadRoomBundle(callTool, rid)
  } catch (err) {
    error_text.value = err?.message || String(err)
  } finally {
    refreshing_current_room.value = false
    if (show_menu.value) {
      nextTick(() => {
        schedule_menu_position()
      })
    }
  }
}

async function enter_room(input) {
  const row = safe_object(input)
  const rid = String(row.room_id || input || '').trim()
  if (!rid) return

  busy.value = true
  error_text.value = ''

  try {
    if (safe_string(row._room_kind) === 'federated') {
      room_store.setFederationRoomSession({
        enabled: true,
        peer_id: safe_string(row.peer_id),
        target_peer_id: safe_string(row.target_peer_id),
        room_id: rid,
        owner_room_id: safe_string(row.owner_room_id || rid),
        remote_user_id: safe_string(row.remote_user_id),
        local_owner_user_id: safe_string(row.local_owner_user_id || row.owner_user_id),
        owner_user_id: safe_string(row.owner_user_id || row.local_owner_user_id),
        remote_label: safe_string(row.remote_label),
      })

      const restored = await room_store.ensureFederationContextForRoomId(callTool, rid, {
        clearLocal: true,
      })

      if (restored?.ok === false) {
        throw new Error(
          restored.message || 'Federated room session restore failed.'
        )
      }
    } else {
      room_store.clearFederationRoomSession()
    }

    chat_cfg.enterRoom(rid)
    room_store.setRoomId(rid)
    await room_store.loadRoomBundle(callTool, rid)
    close_menu()
  } catch (err) {
    error_text.value = err?.message || String(err)
  } finally {
    busy.value = false
  }
}

async function exit_room() {
  busy.value = true
  error_text.value = ''

  try {
    room_store.closeAllOverlays()
    room_store.clearFederationRoomSession()
    room_store.resetRoom()
    chat_cfg.exitRoomHard()
    close_menu()
  } catch (err) {
    error_text.value = err?.message || String(err)
  } finally {
    busy.value = false
  }
}

async function submit_create() {
  const title = String(create_form.title || '').trim() || t('chat.roomMenu.create.defaults.title')
  const participants = parse_participants_text(create_form.participants_text)

  busy.value = true
  error_text.value = ''
  reset_created_room()

  try {
    const res = await callTool('nisb_room_shared_create', {
      title,
      participants,
    })

    const data = assert_tool_success(res, t('chat.roomMenu.errors.createRoomFailed'))
    const info = extract_room_info(data)
    const room = info.room || {}

    const created_room_id =
      String(room?.room_id || '').trim() ||
      String(data?.conv_id || '').trim()

    created_room.room_id = created_room_id
    created_room.join_key = String(room?.join_key || '').trim()

    await refresh_rooms()

    if (created_room.room_id) {
      await enter_room({
        room_id: created_room.room_id,
        join_key: created_room.join_key,
        _room_kind: 'local',
      })
    }
  } catch (err) {
    error_text.value = err?.message || String(err)
  } finally {
    busy.value = false
    if (show_menu.value) {
      nextTick(() => {
        schedule_menu_position()
      })
    }
  }
}

async function submit_join() {
  const room_id = String(join_form.room_id || '').trim()
  const join_key = String(join_form.join_key || '').trim()

  if (!room_id || !join_key) {
    error_text.value = t('chat.roomMenu.errors.joinFieldsRequired')
    return
  }

  busy.value = true
  error_text.value = ''

  try {
    const res = await callTool('nisb_room_shared_join', {
      room_id,
      join_key,
    })

    assert_tool_success(res, t('chat.roomMenu.errors.joinRoomFailed'))

    await refresh_rooms()
    await enter_room({
      room_id,
      join_key,
      _room_kind: 'local',
    })

    join_form.room_id = ''
    join_form.join_key = ''
  } catch (err) {
    error_text.value = err?.message || String(err)
  } finally {
    busy.value = false
    if (show_menu.value) {
      nextTick(() => {
        schedule_menu_position()
      })
    }
  }
}

async function copy_text(text) {
  const value = String(text || '').trim()
  if (!value) return

  try {
    await navigator.clipboard.writeText(value)
  } catch {
    const input = document.createElement('textarea')
    input.value = value
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
  }
}

watch(
  () => show_menu.value,
  async (val) => {
    if (!val) {
      cleanup_menu_raf()
      cleanup_resize_observer()
      return
    }

    await nextTick()
    compute_menu_position()
    bind_menu_resize_observer()
  }
)

watch(
  () => [
    is_room_mode.value,
    active_room_id.value,
    current_room_run_id.value,
    current_room_last_plan_summary.value,
    current_room_roles_count.value,
    current_room_active_roles_count.value,
    current_room_participants_count.value,
    current_room_is_federated.value,
    current_room_federated_label.value,
    loading_rooms.value,
    refreshing_current_room.value,
    merged_recent_rooms.value.length,
    error_text.value,
  ],
  () => {
    if (!show_menu.value) return
    nextTick(() => {
      schedule_menu_position()
    })
  }
)

onMounted(() => {
  document.addEventListener('mousedown', handle_click_outside, true)
  document.addEventListener('keydown', handle_keydown)
  window.addEventListener('resize', handle_window_relayout)
  window.addEventListener('scroll', handle_window_relayout, true)
  refresh_rooms()
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handle_click_outside, true)
  document.removeEventListener('keydown', handle_keydown)
  window.removeEventListener('resize', handle_window_relayout)
  window.removeEventListener('scroll', handle_window_relayout, true)
  cleanup_menu_raf()
  cleanup_resize_observer()
})
</script>

<style scoped>
.room-wrapper {
  position: relative;
  flex: 0 0 auto;
  min-width: 0;
}

.room-btn {
  min-width: 0;
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.room-btn:hover:not(:disabled),
.room-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.room-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.room-btn.toggle-on,
.room-btn.open {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 64%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.room-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.room-icon {
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--selected) 14%, transparent), transparent 56%),
    color-mix(in srgb, var(--selected-bg) 34%, transparent);
  font-size: 0.82rem;
  line-height: 1;
}

.btn-text {
  min-width: 0;
  font-size: 0.8rem;
  font-weight: 760;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-chip {
  flex: 0 0 auto;
  min-height: 18px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.38rem;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 56%, transparent);
  color: var(--selected);
  font-size: 0.66rem;
  font-weight: 820;
  line-height: 1;
}

.btn-caret {
  flex: 0 0 auto;
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.82;
}

.room-popover-scrim {
  position: fixed;
  inset: 0;
  z-index: 2147482999;
  background: color-mix(in srgb, #020617 22%, transparent);
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  animation: roomScrimIn 0.14s ease-out;
}

.room-menu {
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 24px 72px rgba(0, 0, 0, 0.28),
    0 2px 14px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(24px) saturate(1.12);
  -webkit-backdrop-filter: blur(24px) saturate(1.12);
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  isolation: isolate;
  animation: roomMenuGlassIn 0.16s ease-out;
}

.room-menu::-webkit-scrollbar {
  width: 8px;
}

.room-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.room-menu-floating {
  position: fixed;
  left: 8px;
  top: 8px;
  width: min(500px, calc(100vw - 16px));
  max-height: min(78vh, calc(100vh - 16px));
  z-index: 2147483000;
}

.menu-header {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin: 0.58rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 26%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.menu-title-wrap {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.42rem;
}

.menu-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.92rem;
  font-weight: 830;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.menu-subtitle {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.menu-subtitle strong {
  color: var(--text-main, var(--text));
  font-weight: 820;
}

.menu-status-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.status-chip,
.boundary-chip,
.meta-chip,
.flag-chip {
  max-width: 100%;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 44%, transparent);
  color: var(--text-secondary);
  font-size: 0.69rem;
  font-weight: 740;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.status-chip.primary,
.meta-chip.strong {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 810;
}

.status-chip.accent,
.meta-chip.accent,
.federated-flag {
  border-color: color-mix(in srgb, #3b82f6 38%, var(--line));
  background: rgba(59, 130, 246, 0.09);
  color: #3b82f6;
  font-weight: 800;
}

.status-chip.warn {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
  font-weight: 800;
}

.room-boundary-card {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
  padding: 0.52rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 34%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 62%, transparent)
    );
}

.room-boundary-title {
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 810;
  line-height: 1.35;
}

.room-boundary-chips {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.boundary-chip {
  min-height: 22px;
  font-size: 0.67rem;
  font-weight: 750;
}

.room-boundary-hint {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.48;
  overflow-wrap: break-word;
}

.menu-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 0.42rem;
  flex-wrap: wrap;
  min-width: 0;
}

.menu-error {
  margin: 0.58rem 0.58rem 0;
  padding: 0.62rem 0.68rem;
  border: 1px solid rgba(239, 68, 68, 0.32);
  border-radius: 13px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8rem;
  font-weight: 690;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.menu-section {
  min-width: 0;
  display: grid;
  gap: 0.62rem;
  margin: 0.58rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.section-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 810;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.current-room-card,
.created-box {
  min-width: 0;
  display: grid;
  gap: 0.62rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 40%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
}

.current-room-top {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
}

.current-room-title-wrap {
  flex: 1 1 auto;
  min-width: 0;
}

.current-room-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.current-room-id {
  margin-top: 0.28rem;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.current-room-badges,
.current-room-flags {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.current-room-badges {
  flex: 0 1 auto;
  justify-content: flex-end;
}

.flag-chip {
  min-height: 24px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
  font-size: 0.72rem;
}

.run-box,
.plan-box {
  min-width: 0;
  padding: 0.6rem 0.64rem;
  border-radius: 13px;
  overflow: hidden;
}

.run-box {
  border: 1px solid rgba(217, 119, 6, 0.32);
  background: rgba(217, 119, 6, 0.09);
}

.run-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.46rem;
}

.run-label {
  flex: 0 0 auto;
  color: #d97706;
  font-size: 0.75rem;
  font-weight: 780;
  line-height: 1.35;
}

.run-value {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.74rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.running-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #d97706;
  animation: room-pulse 1.2s ease-in-out infinite;
}

@keyframes room-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }

  50% {
    opacity: 0.36;
    transform: scale(0.72);
  }
}

.plan-box {
  border: 1px solid rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.08);
}

.plan-label {
  margin-bottom: 0.34rem;
  color: #3b82f6;
  font-size: 0.74rem;
  font-weight: 800;
  line-height: 1.35;
}

.plan-text {
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  line-height: 1.52;
  overflow-wrap: break-word;
}

.field {
  min-width: 0;
  display: grid;
  gap: 0.36rem;
}

.field span {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 740;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.field input {
  width: 100%;
  min-width: 0;
  height: 34px;
  box-sizing: border-box;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 60%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 680;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.field input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.field input:focus {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 30%, transparent),
      color-mix(in srgb, var(--editor-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.row-actions {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.46rem;
}

.created-box {
  margin-top: 0.12rem;
  border-style: dashed;
}

.created-line {
  min-width: 0;
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr);
  gap: 0.5rem;
  align-items: baseline;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.label {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 740;
}

.value {
  min-width: 0;
  color: var(--text-main, var(--text));
  overflow-wrap: anywhere;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

.menu-footer {
  margin: 0.58rem;
  padding: 0.52rem 0.58rem;
  border: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
}

.footer-text {
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.primary-btn,
.ghost-btn,
.mini-btn {
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.primary-btn {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected) 88%, #1f2937),
      color-mix(in srgb, var(--selected) 76%, #111827)
    );
  color: #fff;
}

.ghost-btn:hover:not(:disabled),
.mini-btn:hover:not(:disabled),
.primary-btn:hover:not(:disabled),
.ghost-btn:focus-visible,
.mini-btn:focus-visible,
.primary-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.primary-btn:hover:not(:disabled),
.primary-btn:focus-visible {
  color: #fff;
  opacity: 0.94;
}

.ghost-btn:active:not(:disabled),
.mini-btn:active:not(:disabled),
.primary-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mini-btn {
  min-height: 30px;
  padding: 0 0.66rem;
  font-size: 0.72rem;
}

.mini-btn.danger {
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.mini-btn.danger:hover:not(:disabled),
.mini-btn.danger:focus-visible {
  border-color: rgba(239, 68, 68, 0.42);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@keyframes roomScrimIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes roomMenuGlassIn {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 640px) {
  .room-popover-scrim {
    background: color-mix(in srgb, #020617 24%, transparent);
    backdrop-filter: blur(10px) saturate(1.12);
    -webkit-backdrop-filter: blur(10px) saturate(1.12);
  }

  .room-menu-floating {
    width: calc(100vw - 16px);
  }

  .menu-header {
    flex-direction: column;
    align-items: stretch;
  }

  .menu-actions {
    justify-content: flex-start;
  }

  .current-room-top {
    flex-direction: column;
  }

  .current-room-badges {
    justify-content: flex-start;
  }

  .created-line {
    grid-template-columns: minmax(0, 1fr);
    gap: 0.18rem;
  }

  .primary-btn,
  .ghost-btn,
  .mini-btn {
    flex: 1 1 auto;
  }
}

@media (max-width: 420px) {
  .row-actions,
  .menu-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .primary-btn,
  .ghost-btn,
  .mini-btn {
    width: 100%;
  }
}
</style>
