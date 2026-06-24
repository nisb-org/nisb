<template>
  <div ref="wrapRef" class="room-header">
    <div class="header-top">
      <button
        class="icon-btn back-btn tooltip-host"
        type="button"
        @click="$emit('back-click')"
        :data-tooltip="t('room.header.actions.exitRoom')"
        :aria-label="t('room.header.actions.exitRoom')"
      >
        ←
      </button>

      <div class="title-cluster">
        <div class="room-title-wrap tooltip-host" :data-tooltip="roomTitle">
          <h2 class="room-title" :aria-label="roomTitle">{{ roomTitle }}</h2>
        </div>

        <div class="stats-strip tooltip-host" :data-tooltip="statsTitle" :aria-label="statsTitle">
          <span class="stats-item">
            <span class="stats-icon" aria-hidden="true">👥</span>
            <span class="stats-value">{{ participantsCount }}</span>
            <span v-if="statsTextMode === 'full'" class="stats-label">
              {{ t('room.header.stats.users') }}
            </span>
          </span>

          <span class="stats-sep" aria-hidden="true">·</span>

          <span class="stats-item">
            <span class="stats-icon" aria-hidden="true">🎭</span>
            <span class="stats-value">{{ rolesCount }}</span>
            <span v-if="statsTextMode === 'full'" class="stats-label">
              {{ t('room.header.stats.roles') }}
            </span>
          </span>

          <span class="stats-sep" aria-hidden="true">·</span>

          <span class="stats-item" :class="{ active: activeRolesCount > 0 }">
            <span class="stats-icon" aria-hidden="true">🧠</span>
            <span class="stats-value">{{ activeRolesCount }}</span>
            <span v-if="statsTextMode === 'full'" class="stats-label">
              {{ t('room.header.stats.active') }}
            </span>
          </span>
        </div>
      </div>

      <div class="header-right">
        <span v-if="isRunning" class="room-badge running-badge">
          {{ t('room.header.stats.running') }}
        </span>

        <span class="room-badge">{{ roomBadgeText }}</span>

        <span v-if="supervisorEnabled" class="room-badge supervisor-badge">
          {{ supervisorBadgeText }}
        </span>

        <div v-if="!compactActions" class="room-actions">
          <button
            class="action-btn tooltip-host"
            type="button"
            @click="openWorkspaceDrawer"
            :data-tooltip="t('room.header.actions.workspace')"
            :aria-label="t('room.header.actions.workspace')"
          >
            {{ workspaceActionText }}
          </button>
          <button
            class="action-btn tooltip-host"
            type="button"
            @click="$emit('refresh-click')"
            :data-tooltip="t('room.header.actions.refresh')"
            :aria-label="t('room.header.actions.refresh')"
          >
            {{ t('room.header.actions.refresh') }}
          </button>
          <button
            class="action-btn tooltip-host"
            type="button"
            @click="$emit('roles-click')"
            :data-tooltip="t('room.header.actions.roles')"
            :aria-label="t('room.header.actions.roles')"
          >
            {{ t('room.header.actions.roles') }}
          </button>
          <button
            class="action-btn tooltip-host"
            type="button"
            @click="$emit('settings-click')"
            :data-tooltip="t('room.header.actions.settings')"
            :aria-label="t('room.header.actions.settings')"
          >
            {{ t('room.header.actions.settings') }}
          </button>
        </div>

        <div v-else ref="menuWrapRef" class="room-actions compact-actions">
          <button
            class="icon-btn action-icon-btn"
            type="button"
            @click="toggleActionsMenu"
            :aria-label="t('room.header.actions.menu')"
            :aria-expanded="actionsOpen ? 'true' : 'false'"
          >
            ⋯
          </button>

          <div v-if="actionsOpen" class="actions-menu" role="menu">
            <button class="menu-item" type="button" role="menuitem" @click="onMenuWorkspace">
              {{ t('room.header.actions.workspace') }}
            </button>
            <button class="menu-item" type="button" role="menuitem" @click="onMenuRefresh">
              {{ t('room.header.actions.refresh') }}
            </button>
            <button class="menu-item" type="button" role="menuitem" @click="onMenuRoles">
              {{ t('room.header.actions.roles') }}
            </button>
            <button class="menu-item" type="button" role="menuitem" @click="onMenuSettings">
              {{ t('room.header.actions.settings') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="hasWorkspaceBinding || hasFocusBinding" class="bindings-row">
      <button
        v-if="hasWorkspaceBinding"
        class="binding-chip workspace-chip tooltip-host"
        type="button"
        :data-tooltip="workspaceDisplayTitle || t('room.header.bindings.openWorkspace')"
        :aria-label="workspaceDisplayTitle || t('room.header.bindings.openWorkspace')"
        @click="openWorkspaceDrawer"
      >
        <span class="binding-label">{{ workspaceBindingLabel }}</span>
        <span class="binding-value">{{ workspaceDisplayText }}</span>
      </button>

      <button
        v-if="hasFocusBinding"
        class="binding-chip focus-chip tooltip-host"
        type="button"
        :data-tooltip="focusBindingTitle"
        :aria-label="focusBindingTitle"
        @click="onFocusBindingClick"
      >
        <span class="binding-label">{{ focusBindingLabel }}</span>
        <span class="binding-value">{{ focusDisplayText }}</span>
      </button>
    </div>

    <div v-if="lastPlanSummary" class="plan-row">
      <div class="plan-chip tooltip-host" :data-tooltip="lastPlanSummary" :aria-label="lastPlanSummary">
        <span class="plan-label">{{ planLabelText }}</span>
        <span class="plan-text" :style="planTextStyle">{{ lastPlanSummary }}</span>
      </div>
    </div>

    <RoomWorkspaceDrawer
      :visible="workspaceDrawerVisible"
      :room_id="roomId"
      :room_state="props.room_state"
      :workspace_id="workspaceId"
      :workspace_name="workspaceName"
      :focus_root="focusRoot"
      :focus_label="focusLabel"
      @close="workspaceDrawerVisible = false"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomStore } from '../../../stores/room'
import RoomWorkspaceDrawer from './RoomWorkspaceDrawer.vue'

const props = defineProps({
  room: { type: Object, default: null },
  room_state: { type: Object, default: () => ({}) },
  roles_count: { type: Number, default: 0 },
  participants_count: { type: Number, default: 0 },
})

const emit = defineEmits(['back-click', 'refresh-click', 'roles-click', 'settings-click'])
const { t } = useI18n()
const room_store = useRoomStore()
const workspaceDrawerVisible = ref(false)

const wrapRef = ref(null)
const menuWrapRef = ref(null)
const panelWidth = ref(0)
const actionsOpen = ref(false)

let ro = null

const roomId = computed(() => {
  return String(
    props.room?.room_id ||
    props.room?.id ||
    room_store.roomId ||
    room_store.room?.room_id ||
    room_store.room?.id ||
    ''
  ).trim()
})

const roomTitle = computed(() => String(props.room?.title || t('room.header.fallbackTitle')))
const rolesCount = computed(() => Number(props.roles_count || 0))
const participantsCount = computed(() => Number(props.participants_count || 0))

const activeRolesCount = computed(() => {
  return Array.isArray(props.room_state?.active_roles) ? props.room_state.active_roles.length : 0
})

const inheritWorkspaceContext = computed(() => !!props.room_state?.inherit_workspace_context)
const inheritFocusRoot = computed(() => !!props.room_state?.inherit_focus_root)
const supervisorEnabled = computed(() => !!props.room_state?.supervisor_enabled)

const isRunning = computed(() => {
  return !!String(props.room_state?.current_run_id || '').trim()
})

const workspaceContext = computed(() => {
  if (props.room_state?.workspace_context && typeof props.room_state.workspace_context === 'object') {
    return props.room_state.workspace_context
  }
  return {}
})

const workspaceId = computed(() => {
  return String(
    props.room_state?.workspace_id ||
    workspaceContext.value?.workspace_id ||
    ''
  ).trim()
})

const workspaceName = computed(() => {
  return String(
    props.room_state?.workspace_name ||
    workspaceContext.value?.workspace_name ||
    ''
  ).trim()
})

const focusRoot = computed(() => {
  return String(
    props.room_state?.focus_root ||
    workspaceContext.value?.focus_root ||
    ''
  ).trim()
})

const focusLabel = computed(() => {
  return String(
    props.room_state?.focus_label ||
    workspaceContext.value?.focus_label ||
    ''
  ).trim()
})

const hasWorkspaceBinding = computed(() => !!workspaceId.value)
const hasFocusBinding = computed(() => !!focusRoot.value)

const workspaceDisplayText = computed(() => {
  return workspaceName.value || workspaceId.value || ''
})

const workspaceDisplayTitle = computed(() => {
  const parts = []
  if (workspaceName.value) parts.push(workspaceName.value)
  if (workspaceId.value && workspaceId.value !== workspaceName.value) parts.push(workspaceId.value)
  return parts.join(' · ')
})

const focusDisplayText = computed(() => {
  return focusLabel.value || focusRoot.value || ''
})

const focusBindingTitle = computed(() => {
  const root = normalizeNisbPath(focusRoot.value)
  const wid = String(workspaceId.value || '').trim()
  if (wid && root) {
    return t('room.header.bindings.focusTitleWorkspaceAndRoot', {
      workspace: wid,
      root
    })
  }
  if (wid) {
    return t('room.header.bindings.focusTitleWorkspace', {
      workspace: wid
    })
  }
  if (root) {
    return t('room.header.bindings.focusTitleRoot', {
      root
    })
  }
  return t('room.header.bindings.focusTitleFallback')
})

const lastPlanSummary = computed(() => {
  const plan_evt = room_store.lastPlanEvent
  return String(plan_evt?.payload?.plan_summary || '').trim()
})

const compactActions = computed(() => {
  const w = panelWidth.value
  if (w === 0) return false
  return w < 1160
})

const textMode = computed(() => {
  const w = panelWidth.value
  if (w === 0) return 'full'
  if (w >= 1180) return 'full'
  if (w >= 760) return 'short'
  return 'compact'
})

const statsTextMode = computed(() => {
  const w = panelWidth.value
  if (w === 0) return 'full'
  if (w >= 980) return 'full'
  return 'compact'
})

const roomBadgeText = computed(() => {
  if (textMode.value === 'compact') return t('room.header.badges.roomCompact')
  return t('room.header.badges.room')
})

const supervisorBadgeText = computed(() => {
  if (textMode.value === 'compact') return t('room.header.badges.supervisorCompact')
  if (textMode.value === 'short') return t('room.header.badges.supervisorCompact')
  return t('room.header.badges.supervisor')
})

const workspaceActionText = computed(() => {
  return textMode.value === 'full'
    ? t('room.header.actions.workspace')
    : t('room.header.actions.workspaceShort')
})

const workspaceBindingLabel = computed(() => {
  if (textMode.value === 'compact') return '📁'
  if (textMode.value === 'short') return t('room.header.bindings.workspaceShort')
  return t('room.header.bindings.workspace')
})

const focusBindingLabel = computed(() => {
  if (textMode.value === 'compact') return '🎯'
  if (textMode.value === 'short') return t('room.header.bindings.focusShort')
  return t('room.header.bindings.focus')
})

const planLabelText = computed(() => {
  if (textMode.value === 'compact') return t('room.header.plan.short')
  return t('room.header.plan.latest')
})

const planLineClamp = computed(() => {
  const w = panelWidth.value
  if (w === 0) return 2
  if (w >= 1360) return 3
  if (w >= 900) return 2
  return 1
})

const planTextStyle = computed(() => {
  return {
    WebkitLineClamp: String(planLineClamp.value),
  }
})

const statsTitle = computed(() => {
  const parts = [
    t('room.header.stats.usersCount', { count: participantsCount.value }),
    t('room.header.stats.rolesCount', { count: rolesCount.value }),
    t('room.header.stats.activeCount', { count: activeRolesCount.value }),
  ]

  if (isRunning.value) parts.push(t('room.header.stats.running'))
  if (inheritWorkspaceContext.value) parts.push(t('room.header.stats.inheritWorkspaceContext'))
  if (inheritFocusRoot.value) parts.push(t('room.header.stats.inheritFocusRoot'))

  return parts.join(' · ')
})

function normalizeNisbPath(p) {
  if (!p) return ''

  return String(p)
    .trim()
    .replace(/\\+/g, '/')
    .replace(/^\/+/, '')
}

function setupWidthObserver() {
  const el = wrapRef.value
  if (!el || typeof ResizeObserver === 'undefined') return

  const apply = () => {
    panelWidth.value = Math.round(el.getBoundingClientRect().width || 0)
  }

  ro = new ResizeObserver(() => apply())
  ro.observe(el)
  apply()
}

function cleanupWidthObserver() {
  try {
    ro && ro.disconnect()
  } catch {}
  ro = null
}

function openWorkspaceDrawer() {
  if (!workspaceId.value) {
    window.dispatchEvent(new CustomEvent('nisb-toast', {
      detail: {
        message: t('room.header.messages.workspaceNotBound'),
        type: 'warning'
      }
    }))
    return
  }
  workspaceDrawerVisible.value = true
}

function isElementActuallyVisible(el) {
  if (!el) return false
  try {
    const rect = el.getBoundingClientRect()
    const style = window.getComputedStyle(el)
    if (style.display === 'none' || style.visibility === 'hidden') return false
    return rect.width > 0 && rect.height > 0
  } catch {
    return false
  }
}

function isLeftSidebarCollapsedByUI() {
  const collapsedToggle = document.querySelector('.sidebar-toggle-btn.left-toggle.collapsed')
  return isElementActuallyVisible(collapsedToggle)
}

function ensureLeftSidebarOpen() {
  const collapsed = isLeftSidebarCollapsedByUI()
  if (!collapsed) return false
  window.dispatchEvent(new CustomEvent('toggle-left-sidebar'))
  return true
}

function dispatchLeftSidebarFilesTab() {
  window.dispatchEvent(
    new CustomEvent('nisb-left-sidebar-switch-tab', {
      detail: {
        tab: 'files',
        source: 'room_header_focus_binding'
      }
    })
  )
}

function dispatchFocusRoot(root) {
  window.dispatchEvent(
    new CustomEvent('nisb_file_focus_root', {
      detail: {
        path: root,
        source: 'room_header_focus_binding'
      }
    })
  )
}

function dispatchTreeReveal(root) {
  window.dispatchEvent(
    new CustomEvent('nisb-file-tree-focus-path', {
      detail: {
        path: root,
        type: 'directory',
        source: 'room_header_focus_binding'
      }
    })
  )
}

function focusLeftSidebarToRoot(root) {
  dispatchLeftSidebarFilesTab()
  dispatchFocusRoot(root)
  dispatchTreeReveal(root)
}

function dispatchRoomWorkspaceContextApply(payload) {
  window.dispatchEvent(
    new CustomEvent('nisb_room_apply_workspace_context', {
      detail: {
        ...payload,
        source: 'room_header_focus_binding'
      }
    })
  )
}

function writePendingLeftSidebarIntent({ workspace_id = '', focus_root = '', focus_label = '' } = {}) {
  const wid = String(workspace_id || '').trim()
  const root = normalizeNisbPath(focus_root || '')
  const label = String(focus_label || '').trim()

  try {
    window.__nisb_pending_left_sidebar_intent = {
      tab: 'files',
      workspace_id: wid,
      focus_root: root,
      focus_label: label,
      reveal_path: root,
      reveal_type: 'directory',
      prefer_workspace_snapshot: !!wid,
      source: 'room_header_focus_binding',
      ts: Date.now()
    }
  } catch {}
}

function onFocusBindingClick() {
  const wid = String(workspaceId.value || '').trim()
  const root = normalizeNisbPath(focusRoot.value)
  const label = String(focusLabel.value || '').trim()

  if (!wid && !root) {
    window.dispatchEvent(new CustomEvent('nisb-toast', {
      detail: {
        message: t('room.header.messages.noWorkspaceOrFocus'),
        type: 'warning'
      }
    }))
    return
  }

  const wasCollapsed = isLeftSidebarCollapsedByUI()

  if (wasCollapsed) {
    writePendingLeftSidebarIntent({
      workspace_id: wid,
      focus_root: root,
      focus_label: label
    })
    ensureLeftSidebarOpen()

    window.dispatchEvent(new CustomEvent('nisb-toast', {
      detail: {
        message: wid
          ? t('room.header.messages.openingWorkspaceWithState', { workspace: wid })
          : t('room.header.messages.openingFocusRoot', { root }),
        type: 'info'
      }
    }))
    return
  }

  if (wid) {
    dispatchRoomWorkspaceContextApply({
      workspace_id: wid,
      focus_root: root,
      focus_label: label,
      prefer_workspace_snapshot: true
    })

    window.dispatchEvent(new CustomEvent('nisb-toast', {
      detail: {
        message: t('room.header.messages.restoringWorkspaceState', { workspace: wid }),
        type: 'info'
      }
    }))
    return
  }

  focusLeftSidebarToRoot(root)
  setTimeout(() => dispatchTreeReveal(root), 120)

  window.dispatchEvent(new CustomEvent('nisb-toast', {
    detail: {
      message: t('room.header.messages.jumpedToFocusRoot', { root }),
      type: 'info'
    }
  }))
}

function closeActionsMenu() {
  actionsOpen.value = false
}

function toggleActionsMenu() {
  actionsOpen.value = !actionsOpen.value
}

function onMenuWorkspace() {
  closeActionsMenu()
  openWorkspaceDrawer()
}

function onMenuRefresh() {
  closeActionsMenu()
  emit('refresh-click')
}

function onMenuRoles() {
  closeActionsMenu()
  emit('roles-click')
}

function onMenuSettings() {
  closeActionsMenu()
  emit('settings-click')
}

function onDocPointerDown(e) {
  if (!actionsOpen.value) return
  const el = menuWrapRef.value
  if (!el) return
  if (el.contains(e.target)) return
  actionsOpen.value = false
}

function onKeydown(e) {
  if (e.key !== 'Escape') return
  if (actionsOpen.value) {
    e.preventDefault()
    actionsOpen.value = false
  }
}

watch(
  () => compactActions.value,
  (val) => {
    if (!val) actionsOpen.value = false
  }
)

onMounted(() => {
  setupWidthObserver()
  window.addEventListener('pointerdown', onDocPointerDown, true)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  cleanupWidthObserver()
  window.removeEventListener('pointerdown', onDocPointerDown, true)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.room-header {
  position: relative;
  flex-shrink: 0;
  min-width: 0;
  isolation: auto;
  box-sizing: border-box;
  padding: 0.54rem 0.72rem 0.62rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  overflow: visible;
}

.header-top {
  min-width: 0;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.title-cluster {
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 0.46rem;
}

.room-title-wrap {
  min-width: 0;
  flex: 1 1 auto;
}

.room-title {
  min-width: 0;
  margin: 0;
  color: var(--text-main, var(--text));
  font-size: 0.98rem;
  font-weight: 830;
  line-height: 1.22;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stats-strip {
  flex: 0 0 auto;
  min-width: 0;
  min-height: 27px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.34rem;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  white-space: nowrap;
}

.stats-item {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.23rem;
}

.stats-item.active {
  color: var(--selected);
}

.stats-icon {
  font-size: 0.76rem;
  line-height: 1;
}

.stats-value {
  color: var(--text-main, var(--text));
  font-size: 0.77rem;
  font-weight: 810;
  line-height: 1;
}

.stats-item.active .stats-value {
  color: var(--selected);
}

.stats-label {
  color: var(--text-secondary);
  font-size: 0.71rem;
  font-weight: 720;
  line-height: 1;
}

.stats-sep {
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.56;
}

.header-right {
  flex: 0 0 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
}

.room-badge {
  min-height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--selected) 36%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-size: 0.68rem;
  font-weight: 820;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.supervisor-badge {
  border-color: color-mix(in srgb, #16a34a 34%, var(--line));
  background: rgba(22, 163, 74, 0.08);
  color: #16a34a;
}

.running-badge {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
}

.bindings-row {
  position: relative;
  z-index: 40;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.48rem;
  margin-top: 0.52rem;
}

.binding-chip {
  position: relative;
  z-index: 1;
  width: 100%;
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.34rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-family: inherit;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.14s ease;
}

.binding-chip.tooltip-host:hover,
.binding-chip.tooltip-host:focus-visible {
  z-index: 80;
}

.binding-chip:hover,
.binding-chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  outline: none;
}

.binding-chip:active {
  transform: translateY(1px);
}

.workspace-chip {
  border-color: color-mix(in srgb, #6366f1 24%, var(--line));
  background:
    linear-gradient(
      135deg,
      rgba(99, 102, 241, 0.08),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
}

.focus-chip {
  border-color: color-mix(in srgb, #16a34a 24%, var(--line));
  background:
    linear-gradient(
      135deg,
      rgba(22, 163, 74, 0.08),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
}

.binding-label {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
  white-space: nowrap;
}

.binding-chip:hover .binding-label,
.binding-chip:focus-visible .binding-label {
  color: var(--selected);
}

.binding-value {
  min-width: 0;
  flex: 1 1 auto;
  color: var(--text-main, var(--text));
  font-size: 0.77rem;
  font-weight: 710;
  line-height: 1.35;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.binding-chip:hover .binding-value,
.binding-chip:focus-visible .binding-value {
  color: var(--selected);
}

.plan-row {
  position: relative;
  z-index: 5;
  min-width: 0;
  margin-top: 0.52rem;
}

.plan-chip {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  gap: 0.52rem;
  padding: 0.48rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.plan-label {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.73rem;
  font-weight: 780;
  line-height: 1.45;
  white-space: nowrap;
}

.plan-text {
  min-width: 0;
  flex: 1 1 auto;
  display: -webkit-box;
  overflow: hidden;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 690;
  line-height: 1.48;
  -webkit-box-orient: vertical;
  overflow-wrap: break-word;
}

.room-actions {
  position: relative;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  min-width: 0;
}

.compact-actions {
  gap: 0;
}

.icon-btn,
.action-btn {
  min-height: 32px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
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

.icon-btn {
  width: 32px;
  min-width: 32px;
  padding: 0;
}

.action-btn {
  padding: 0 0.72rem;
}

.action-icon-btn {
  width: 32px;
  min-width: 32px;
  height: 32px;
  font-size: 1rem;
  font-weight: 820;
  letter-spacing: 0.02em;
}

.icon-btn:hover,
.action-btn:hover,
.icon-btn:focus-visible,
.action-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.icon-btn:active,
.action-btn:active {
  transform: translateY(1px);
}

.back-btn {
  flex: 0 0 auto;
  border-radius: 11px;
  font-size: 1rem;
  font-weight: 820;
}

.actions-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 2147482000;
  width: 176px;
  max-width: min(240px, calc(100vw - 24px));
  max-height: min(260px, calc(100vh - 160px));
  box-sizing: border-box;
  padding: 0.32rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      var(--editor-bg),
      color-mix(in srgb, var(--sidebar-bg) 96%, var(--editor-bg))
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 16px 40px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
}

.actions-menu::-webkit-scrollbar {
  width: 8px;
}

.actions-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.menu-item {
  width: 100%;
  min-height: 34px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.52rem;
  padding: 0 0.62rem;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1.2;
  text-align: left;
  overflow-wrap: anywhere;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.menu-item:hover,
.menu-item:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, transparent);
  color: var(--selected);
  outline: none;
}

.tooltip-host {
  position: relative;
}

.tooltip-host::after {
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  z-index: 120;
  max-width: min(360px, 82vw);
  box-sizing: border-box;
  padding: 0.44rem 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      135deg,
      var(--editor-bg),
      color-mix(in srgb, var(--sidebar-bg) 98%, var(--editor-bg))
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 12px 28px rgba(0, 0, 0, 0.2);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  content: attr(data-tooltip);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.45;
  opacity: 0;
  overflow-wrap: anywhere;
  pointer-events: none;
  text-align: center;
  transform: translateX(-50%) translateY(2px);
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
  white-space: normal;
}

.tooltip-host:hover::after,
.tooltip-host:focus-visible::after,
.tooltip-host:focus-within::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

@media (max-width: 980px) {
  .room-header {
    padding: 0.5rem 0.64rem 0.58rem;
  }

  .title-cluster {
    gap: 0.38rem;
  }

  .stats-strip {
    padding: 0 0.5rem;
  }
}

@media (max-width: 760px) {
  .room-title {
    font-size: 0.94rem;
  }

  .stats-strip {
    min-height: 25px;
    padding: 0 0.48rem;
  }

  .stats-value,
  .stats-label,
  .binding-value,
  .plan-text {
    font-size: 0.75rem;
  }

  .room-badge {
    min-height: 20px;
    padding: 0 0.4rem;
    font-size: 0.65rem;
  }

  .binding-chip {
    min-height: 30px;
    padding: 0.32rem 0.56rem;
  }

  .plan-chip {
    padding: 0.44rem 0.58rem;
  }
}

@media (max-width: 620px) {
  .bindings-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .title-cluster {
    gap: 0.34rem;
  }

  .header-right {
    gap: 0.34rem;
  }

  .stats-strip.tooltip-host::after,
  .room-title-wrap.tooltip-host::after {
    left: 0;
    transform: translateY(2px);
    text-align: left;
  }

  .stats-strip.tooltip-host:hover::after,
  .stats-strip.tooltip-host:focus-visible::after,
  .room-title-wrap.tooltip-host:hover::after,
  .room-title-wrap.tooltip-host:focus-within::after {
    transform: translateY(0);
  }
}

@media (max-width: 480px) {
  .room-header {
    padding: 0.44rem 0.52rem 0.54rem;
  }

  .header-top {
    gap: 0.42rem;
  }

  .title-cluster {
    gap: 0.28rem;
  }

  .room-title {
    font-size: 0.91rem;
  }

  .stats-strip {
    min-height: 23px;
    padding: 0 0.42rem;
  }

  .stats-icon,
  .stats-value,
  .stats-sep {
    font-size: 0.71rem;
  }

  .binding-label,
  .binding-value,
  .plan-label,
  .plan-text {
    font-size: 0.73rem;
  }

  .action-icon-btn,
  .back-btn {
    width: 30px;
    min-width: 30px;
    height: 30px;
  }

  .tooltip-host::after {
    left: 0;
    max-width: min(280px, calc(100vw - 20px));
    text-align: left;
    transform: translateY(2px);
  }

  .tooltip-host:hover::after,
  .tooltip-host:focus-visible::after,
  .tooltip-host:focus-within::after {
    transform: translateY(0);
  }

}

/* nisb mobile room binding chips one-line patch */
@media (max-width: 620px) {
  .bindings-row {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    gap: 0.32rem !important;
    margin-top: 0.42rem !important;
  }

  .binding-chip {
    min-height: 28px !important;
    padding: 0.24rem 0.42rem !important;
    border-radius: 10px !important;
    gap: 0.28rem !important;
  }

  .binding-label {
    font-size: 0.68rem !important;
  }

  .binding-value {
    min-width: 0 !important;
    font-size: 0.72rem !important;
    line-height: 1.16 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }
}

@media (max-width: 480px) {
  .bindings-row {
    gap: 0.24rem !important;
    margin-top: 0.36rem !important;
  }

  .binding-chip {
    min-height: 27px !important;
    padding: 0.2rem 0.34rem !important;
    border-radius: 9px !important;
    gap: 0.22rem !important;
  }

  .binding-label {
    font-size: 0.64rem !important;
  }

  .binding-value {
    font-size: 0.68rem !important;
  }
}


/* nisb room header mobile binding one-line patch */
@media (max-width: 620px) {
  .bindings-row {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    gap: 0.32rem !important;
    margin-top: 0.42rem !important;
  }

  .binding-chip {
    min-height: 28px !important;
    padding: 0.24rem 0.42rem !important;
    border-radius: 10px !important;
    gap: 0.28rem !important;
    overflow: hidden !important;
  }

  .binding-label {
    font-size: 0.68rem !important;
  }

  .binding-value {
    min-width: 0 !important;
    font-size: 0.72rem !important;
    line-height: 1.16 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }
}

@media (max-width: 480px) {
  .bindings-row {
    gap: 0.24rem !important;
    margin-top: 0.36rem !important;
  }

  .binding-chip {
    min-height: 27px !important;
    padding: 0.2rem 0.34rem !important;
    border-radius: 9px !important;
    gap: 0.22rem !important;
  }

  .binding-label {
    font-size: 0.64rem !important;
  }

  .binding-value {
    font-size: 0.68rem !important;
  }
}
/* end nisb room header mobile binding one-line patch */
</style>
