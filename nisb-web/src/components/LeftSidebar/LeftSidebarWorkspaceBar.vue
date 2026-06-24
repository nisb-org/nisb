<template>
  <div class="bottom-workspace" ref="root_el">
    <div class="ws-picker" :class="{ open }">
      <button
        class="workspace-selector"
        type="button"
        @click="toggle_open"
        :title="current_label"
        aria-haspopup="menu"
        :aria-expanded="String(open)"
      >
        <span class="ws-main">
          <span class="ws-dot" aria-hidden="true"></span>
          <span class="ws-label">{{ current_label }}</span>
        </span>
        <span class="ws-caret" aria-hidden="true">▾</span>
      </button>

      <div v-if="open" class="workspace-menu" role="menu" @click.stop>
        <button
          v-for="ws in visible_workspaces"
          :key="ws.id"
          class="workspace-item"
          :class="{ active: ws.id === current_workspace }"
          type="button"
          role="menuitem"
          :title="ws.label"
          @click="select_ws(ws.id)"
        >
          <span class="ws-check" aria-hidden="true">{{ ws.id === current_workspace ? '✓' : '' }}</span>
          <span class="ws-name">{{ ws.label }}</span>
          <span v-if="ws.id === current_workspace" class="ws-active-dot" aria-hidden="true"></span>
        </button>
      </div>
    </div>

    <button
      class="settings-btn"
      type="button"
      @click="emit('open_settings')"
      :title="t('sidebar.workspace.settings')"
      :aria-label="t('sidebar.workspace.settings')"
    >
      <span aria-hidden="true">⚙️</span>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  workspaces: { type: Array, default: () => [] },
  current_workspace: { type: String, required: true }
})

const emit = defineEmits(['change_workspace', 'open_settings'])
const { t } = useI18n()

const open = ref(false)
const root_el = ref(null)

const visible_workspaces = computed(() => {
  const arr = Array.isArray(props.workspaces) ? props.workspaces : []
  return arr
    .map((ws) => {
      const id = String(ws?.id || '').trim()
      const name = String(ws?.name || '').trim()
      return {
        id,
        label: name || id
      }
    })
    .filter((ws) => ws.id)
})

const current_label = computed(() => {
  const wid = String(props.current_workspace || '').trim()
  const ws = visible_workspaces.value.find((x) => x.id === wid)
  return String(ws?.label || wid || '').trim() || t('sidebar.workspace.current')
})

function toggle_open() {
  open.value = !open.value
}

function close_open() {
  open.value = false
}

function select_ws(workspace_id) {
  const wid = String(workspace_id || '').trim()
  if (!wid) return
  emit('change_workspace', wid)
  close_open()
}

function on_doc_click(e) {
  if (!open.value) return
  const el = root_el.value
  if (!el) return
  if (el.contains(e.target)) return
  close_open()
}

function on_doc_keydown(e) {
  if (!open.value) return
  if (e.key === 'Escape') close_open()
}

onMounted(() => {
  document.addEventListener('click', on_doc_click, true)
  document.addEventListener('keydown', on_doc_keydown, true)
})

onUnmounted(() => {
  document.removeEventListener('click', on_doc_click, true)
  document.removeEventListener('keydown', on_doc_keydown, true)
})
</script>

<style scoped>
.bottom-workspace {
  position: relative;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: visible;
}

.ws-picker {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
}

.workspace-selector {
  width: 100%;
  min-width: 0;
  min-height: var(--nisb-sidebar-control-height, 32px);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.48rem;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 740;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.workspace-selector:hover,
.workspace-selector:focus-visible,
.ws-picker.open .workspace-selector {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.workspace-selector:active {
  transform: translateY(1px);
}

.ws-main {
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
}

.ws-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 10%, transparent);
  opacity: 0.88;
}

.ws-label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-caret {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.82;
  transition:
    color 0.15s ease,
    opacity 0.15s ease,
    transform 0.15s ease;
}

.ws-picker.open .ws-caret {
  color: var(--selected);
  opacity: 1;
  transform: rotate(180deg);
}

.settings-btn {
  width: var(--nisb-sidebar-control-height, 32px);
  height: var(--nisb-sidebar-control-height, 32px);
  min-width: var(--nisb-sidebar-control-height, 32px);
  max-width: var(--nisb-sidebar-control-height, 32px);
  min-height: var(--nisb-sidebar-control-height, 32px);
  max-height: var(--nisb-sidebar-control-height, 32px);
  flex: 0 0 auto;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.settings-btn:hover,
.settings-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.settings-btn:active {
  transform: translateY(1px);
}

.workspace-menu {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 2147483647;
  min-width: 248px;
  max-width: min(360px, calc(100vw - 16px));
  max-height: min(340px, calc(100vh - 16px));
  box-sizing: border-box;
  display: grid;
  gap: 3px;
  padding: 7px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 42%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 90%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.30),
    0 2px 14px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  transform-origin: bottom left;
  animation: workspace-menu-in 0.11s ease-out;
}

.workspace-item {
  position: relative;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 10px;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.25;
  text-align: left;
  transition:
    background 0.14s ease,
    border-color 0.14s ease,
    color 0.14s ease,
    transform 0.12s ease;
}

.workspace-item:hover,
.workspace-item:focus-visible {
  outline: none;
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--text-main, var(--text));
}

.workspace-item:active {
  transform: translateY(1px);
}

.workspace-item.active {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg));
  color: var(--selected);
}

.workspace-item.active::before {
  content: '';
  position: absolute;
  left: 0.34rem;
  top: 7px;
  bottom: 7px;
  width: 3px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.ws-check {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--selected);
  font-size: 0.78rem;
  font-weight: 800;
  line-height: 1;
}

.ws-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-active-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 10%, transparent);
}

@keyframes workspace-menu-in {
  from {
    opacity: 0;
    transform: translateY(2px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 420px) {
  .bottom-workspace {
    gap: 6px;
  }

  .workspace-selector {
    padding: 0 0.54rem;
  }

  .workspace-menu {
    bottom: calc(100% + 7px);
    min-width: min(248px, calc(100vw - 16px));
    max-width: calc(100vw - 16px);
    max-height: min(300px, 46vh);
    border-radius: 13px;
  }

  .workspace-item {
    min-height: 36px;
    font-size: 0.82rem;
  }
}
</style>
