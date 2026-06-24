<template>
  <div class="mcp-wrapper">
    <button
      type="button"
      class="mcp-btn"
      :class="{ active: anyEnabled }"
      @click.stop="toggleMenu"
      :title="t('chat.mcpMenu.button.title')"
      :aria-label="t('chat.mcpMenu.button.ariaLabel')"
    >
      🧩
    </button>

    <div
      v-if="open"
      class="mcp-popover-scrim"
      aria-hidden="true"
      @click.stop="open = false"
    ></div>

    <div v-if="open" class="mcp-menu" role="menu" :aria-label="t('chat.mcpMenu.button.ariaLabel')" @click.stop>
      <div class="mcp-menu-head">
        <div class="mcp-menu-title">{{ t('chat.mcpMenu.panel.title') }}</div>
        <div class="mcp-menu-subtitle">{{ t('chat.mcpMenu.panel.subtitle') }}</div>

        <div class="mcp-status-row" aria-live="polite">
          <span class="mcp-chip" :class="{ active: serperEnabledLocal }">
            {{ serperEnabledLocal ? t('chat.mcpMenu.status.serperOn') : t('chat.mcpMenu.status.serperOff') }}
          </span>
          <span class="mcp-chip subtle">{{ t('chat.mcpMenu.status.auditOnly') }}</span>
        </div>
      </div>

      <section class="mcp-section">
        <div class="mcp-section-title">{{ t('chat.mcpMenu.sections.webSearch') }}</div>

        <label class="mcp-toggle-card">
          <span class="mcp-toggle-box">
            <input type="checkbox" v-model="serperEnabledLocal" />
          </span>
          <span class="mcp-toggle-copy">
            <span class="mcp-toggle-title">{{ t('chat.mcpMenu.items.serperSearch') }}</span>
            <span class="mcp-toggle-hint">{{ t('chat.mcpMenu.items.serperHint') }}</span>
          </span>
        </label>
      </section>

      <section class="mcp-section mcp-audit-section">
        <div class="mcp-audit-copy">
          <div class="mcp-section-title">{{ t('chat.mcpMenu.sections.fileAudit') }}</div>
          <div class="mcp-hint">{{ t('chat.mcpMenu.fileAudit.hint') }}</div>
        </div>

        <button type="button" class="mcp-audit-btn" @click="openAudit">
          {{ t('chat.mcpMenu.actions.openAudit') }}
        </button>
      </section>

      <div class="mcp-footnote">
        {{ t('chat.mcpMenu.panel.hint') }}
      </div>
    </div>

    <FsAuditModal :open="auditOpen" @close="auditOpen = false" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useChatConfigStore } from '../../../../stores/chatConfig'
import FsAuditModal from './FsAuditModal.vue'

const FS_READ_SCOPE_USER_RO = 'user_ro'
const FS_READ_SCOPE_MINIMAL = 'minimal'
const FS_WRITE_SCOPE_NONE = 'none'
const FS_WRITE_SCOPE_AGENT_FILES = 'agent_files'

function normalizeFsReadScope(val) {
  const s = String(val || FS_READ_SCOPE_USER_RO).trim().toLowerCase()
  if (s === FS_READ_SCOPE_MINIMAL) return FS_READ_SCOPE_MINIMAL
  return FS_READ_SCOPE_USER_RO
}

function normalizeFsWriteScope(val) {
  const s = String(val || FS_WRITE_SCOPE_NONE).trim().toLowerCase()
  if (s === FS_WRITE_SCOPE_AGENT_FILES || s === 'agentfiles') return FS_WRITE_SCOPE_AGENT_FILES
  return FS_WRITE_SCOPE_NONE
}

function normalizeBool(val) {
  return !!val
}

const { t } = useI18n()
const store = useChatConfigStore()
if (typeof store.hydrate === 'function') store.hydrate()
const { mcp } = storeToRefs(store)

const open = ref(false)
const auditOpen = ref(false)

const serperEnabledLocal = ref(false)
const codeNetworkEnabledLocal = ref(false)
const fsReadScopeLocal = ref(FS_READ_SCOPE_USER_RO)
const fsWriteScopeLocal = ref(FS_WRITE_SCOPE_NONE)
const fsDangerousEnabledLocal = ref(false)

const isDangerousDisabled = computed(() => fsWriteScopeLocal.value === FS_WRITE_SCOPE_NONE)

const anyEnabled = computed(() => {
  return !!serperEnabledLocal.value
})

function syncLocalFromStore() {
  serperEnabledLocal.value = normalizeBool(mcp.value?.serperEnabled)
  codeNetworkEnabledLocal.value = false
  fsReadScopeLocal.value = FS_READ_SCOPE_USER_RO
  fsWriteScopeLocal.value = FS_WRITE_SCOPE_NONE
  fsDangerousEnabledLocal.value = false
}

function enforceHiddenMcpDefaults() {
  if (normalizeBool(mcp.value?.codeNetworkEnabled)) {
    store.setCodeNetworkEnabled(false)
  }

  if (normalizeFsReadScope(mcp.value?.fsReadScope) !== FS_READ_SCOPE_USER_RO) {
    store.setFsReadScope(FS_READ_SCOPE_USER_RO)
  }

  if (normalizeFsWriteScope(mcp.value?.fsWriteScope) !== FS_WRITE_SCOPE_NONE) {
    store.setFsWriteScope(FS_WRITE_SCOPE_NONE)
  }

  if (normalizeBool(mcp.value?.fsDangerousEnabled)) {
    store.setFsDangerousEnabled(false)
  }
}

function toggleMenu() {
  open.value = !open.value
  if (open.value) enforceHiddenMcpDefaults()
}

function openAudit() {
  open.value = false
  auditOpen.value = true
}

function handleGlobalClick(e) {
  const root = e?.target?.closest?.('.mcp-wrapper')
  if (!root) open.value = false
}

watch(
  () => [
    mcp.value?.serperEnabled,
    mcp.value?.codeNetworkEnabled,
    mcp.value?.fsReadScope,
    mcp.value?.fsWriteScope,
    mcp.value?.fsDangerousEnabled,
  ],
  () => {
    syncLocalFromStore()
    enforceHiddenMcpDefaults()
  },
  { immediate: true },
)

watch(serperEnabledLocal, (val) => {
  store.setSerperEnabled(normalizeBool(val))
})

watch(codeNetworkEnabledLocal, (val) => {
  store.setCodeNetworkEnabled(normalizeBool(val))
})

watch(fsReadScopeLocal, (val) => {
  const next = normalizeFsReadScope(val)
  if (fsReadScopeLocal.value !== next) {
    fsReadScopeLocal.value = next
    return
  }
  store.setFsReadScope(next)
})

watch(fsWriteScopeLocal, (val) => {
  const next = normalizeFsWriteScope(val)
  if (fsWriteScopeLocal.value !== next) {
    fsWriteScopeLocal.value = next
    return
  }

  store.setFsWriteScope(next)

  if (next === FS_WRITE_SCOPE_NONE && fsDangerousEnabledLocal.value) {
    fsDangerousEnabledLocal.value = false
  }
})

watch(fsDangerousEnabledLocal, (val) => {
  const next = isDangerousDisabled.value ? false : normalizeBool(val)
  if (fsDangerousEnabledLocal.value !== next) {
    fsDangerousEnabledLocal.value = next
    return
  }
  store.setFsDangerousEnabled(next)
})

onMounted(() => {
  syncLocalFromStore()
  enforceHiddenMcpDefaults()
  document.addEventListener('click', handleGlobalClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
})
</script>

<style scoped>
.mcp-wrapper {
  position: relative;
  flex: 0 0 auto;
  margin-top: 0;
}

.mcp-btn {
  width: 36px;
  height: 36px;
  min-width: 36px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.98rem;
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

.mcp-btn:hover:not(:disabled),
.mcp-btn:focus-visible {
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

.mcp-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mcp-btn.active {
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

.mcp-popover-scrim {
  position: fixed;
  inset: 0;
  z-index: 2147482999;
  background: color-mix(in srgb, #020617 22%, transparent);
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  animation: mcpScrimIn 0.14s ease-out;
}

.mcp-menu {
  position: absolute;
  bottom: calc(100% + 0.46rem);
  left: 0;
  z-index: 2147483000;
  width: min(340px, calc(100vw - 16px));
  min-width: min(318px, calc(100vw - 16px));
  max-height: min(64vh, 520px);
  box-sizing: border-box;
  display: grid;
  gap: 0.54rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 22px 68px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(22px) saturate(1.08);
  -webkit-backdrop-filter: blur(22px) saturate(1.08);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  isolation: isolate;
  animation: mcpMenuGlassIn 0.16s ease-out;
}

.mcp-menu::-webkit-scrollbar {
  width: 8px;
}

.mcp-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

@keyframes mcpScrimIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes mcpMenuGlassIn {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}


.mcp-menu-head {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.mcp-menu-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.86rem;
  font-weight: 830;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.mcp-menu-subtitle {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.mcp-status-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.mcp-chip {
  max-width: 100%;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.69rem;
  font-weight: 740;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.mcp-chip.active {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 810;
}

.mcp-chip.subtle {
  border-style: dashed;
}

.mcp-section {
  min-width: 0;
  display: grid;
  gap: 0.48rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.mcp-section-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 810;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.mcp-toggle-card {
  min-width: 0;
  min-height: 46px;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  gap: 0.58rem;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 38%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

.mcp-toggle-card:hover,
.mcp-toggle-card:focus-within {
  border-color: color-mix(in srgb, var(--selected) 32%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
}

.mcp-toggle-box {
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--selected-bg) 24%, var(--editor-bg));
}

.mcp-toggle-box input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.mcp-toggle-copy {
  min-width: 0;
  display: grid;
  gap: 0.22rem;
}

.mcp-toggle-title {
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.mcp-toggle-hint,
.mcp-hint,
.mcp-footnote {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.73rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.mcp-audit-section {
  border-style: dashed;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 36%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
}

.mcp-audit-copy {
  min-width: 0;
  display: grid;
  gap: 0.28rem;
}

.mcp-audit-btn {
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  justify-self: start;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-main, var(--text));
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
    transform 0.14s ease;
}

.mcp-audit-btn:hover,
.mcp-audit-btn:focus-visible {
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

.mcp-audit-btn:active {
  transform: translateY(1px);
}

.mcp-footnote {
  padding: 0.5rem 0.56rem;
  border: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
}

@media (max-width: 640px) {
  .mcp-menu {
    left: 0;
    right: auto;
    width: min(340px, calc(100vw - 16px));
    min-width: min(300px, calc(100vw - 16px));
  }

  .mcp-audit-btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .mcp-menu {
    width: calc(100vw - 16px);
    min-width: calc(100vw - 16px);
  }
}
</style>

