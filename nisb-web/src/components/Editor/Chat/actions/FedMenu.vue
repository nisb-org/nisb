<template>
  <div class="fed-wrapper" ref="wrapRef" @click.stop>
    <button
      ref="btnRef"
      class="fed-btn"
      :class="{ active: open }"
      type="button"
      @click="toggle"
      :disabled="disabled"
      aria-haspopup="menu"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-label="t('chat.fedMenu.button.ariaLabel')"
      :title="t('chat.fedMenu.button.title')"
    >
      <span class="btn-badge" aria-hidden="true">F</span>
      <span class="btn-text">{{ t('chat.fedMenu.button.text') }}</span>
      <span class="btn-caret" aria-hidden="true">▾</span>
    </button>

    <div
      v-if="open"
      class="fed-popover-scrim"
      aria-hidden="true"
      @click.stop="open = false"
    ></div>

    <div
      v-if="open"
      class="fed-panel"
      :style="panelStyle"
      role="menu"
      :aria-label="t('chat.fedMenu.button.ariaLabel')"
      @click.stop
    >
      <div class="fed-panel-head">
        <div class="fed-panel-title">{{ t('chat.fedMenu.panel.title') }}</div>
        <div class="fed-panel-subtitle">{{ t('chat.fedMenu.panel.subtitle') }}</div>

        <div class="fed-status-row" aria-live="polite">
          <span class="fed-status-chip" :class="{ active: marketEnabled }">
            {{ marketEnabled ? t('chat.fedMenu.status.marketOn') : t('chat.fedMenu.status.marketOff') }}
          </span>
          <span class="fed-status-chip">
            {{ t('chat.fedMenu.status.enabledPeers', { count: enabledPeerCount }) }}
          </span>
          <span class="fed-status-chip" :class="{ active: importedInviteCount > 0 }">
            {{ t('chat.fedMenu.status.importedInvites', { count: importedInviteCount }) }}
          </span>
        </div>

        <div class="fed-boundary-card">
          <div class="fed-boundary-title">{{ t('chat.fedMenu.boundary.title') }}</div>
          <div class="fed-boundary-chips">
            <span class="fed-boundary-chip mono">{{ t('chat.fedMenu.boundary.importedRemote') }}</span>
            <span class="fed-boundary-chip mono">{{ t('chat.fedMenu.boundary.shareRef') }}</span>
            <span class="fed-boundary-chip mono">{{ t('chat.fedMenu.boundary.sourceRoomId') }}</span>
            <span class="fed-boundary-chip">{{ t('chat.fedMenu.boundary.finalOnly') }}</span>
            <span class="fed-boundary-chip">{{ t('chat.fedMenu.boundary.sourceObservation') }}</span>
          </div>
          <div class="fed-boundary-hint">{{ t('chat.fedMenu.boundary.hint') }}</div>
        </div>
      </div>

      <div class="fed-section fed-section-compact">
        <label class="fed-toggle">
          <span class="fed-toggle-check">
            <input type="checkbox" :checked="marketEnabled" @change="onToggleMarket($event)" />
          </span>
          <span class="fed-toggle-copy">
            <span class="fed-toggle-title">{{ t('chat.fedMenu.market.enableEvidence') }}</span>
            <span class="muted">{{ t('chat.fedMenu.market.hint') }}</span>
          </span>
        </label>
      </div>

      <FedMenuPasteSection
        :paste-text="pasteText"
        :paste-err="pasteErr"
        :paste-ok="pasteOk"
        :paste-hint="pasteHint"
        :importing-paste="importingPaste"
        :copying-federation-info="copyingFederationInfo"
        :imported-invite-entries="importedInviteEntries"
        :mask-invite-token="maskInviteToken"
        @update:paste-text="pasteText = $event"
        @paste-from-clipboard="pasteFromClipboard"
        @import-federation-info="importFederationInfo"
        @copy-federation-info="copyFederationInfo"
        @apply-imported-invite="applyImportedInvite"
        @remove-imported-invite="removeImportedInvite"
      />

      <FedMenuPeersSection
        :t="t"
        :loading-peers="loadingPeers"
        :peers="peers"
        :checking-health="checkingHealth"
        :peer-health-map="peerHealthMap"
        :saving="saving"
        :err="err"
        :ok="ok"
        :form="form"
        :invite-form="inviteForm"
        :peer-selected="peerSelected"
        @load-peers="loadPeers"
        @check-peer-health="checkPeerHealth"
        @toggle-peer="togglePeer"
        @apply-peer-to-form="applyPeerToForm"
        @save-peer="savePeer"
      />

      <FedMenuAcceptInviteSection
        :invite-form="inviteForm"
        :enabled-peers="enabledPeers"
        :accepting-invite="acceptingInvite"
        :can-retry-invite="canRetryInvite"
        :invite-err="inviteErr"
        :invite-ok="inviteOk"
        :invite-hint="inviteHint"
        @accept-room-invite="acceptRoomInvite"
        @retry-last-accept="retryLastAccept"
      />

      <div class="fed-section fed-foot">
        <div class="muted">{{ t('chat.fedMenu.hint') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, unref } from 'vue'
import { useI18n } from 'vue-i18n'
import FedMenuPasteSection from './fed-menu/FedMenuPasteSection.vue'
import FedMenuPeersSection from './fed-menu/FedMenuPeersSection.vue'
import FedMenuAcceptInviteSection from './fed-menu/FedMenuAcceptInviteSection.vue'
import { useFedMenu } from './fed-menu/useFedMenu'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const { t } = useI18n()

const {
  wrapRef,
  btnRef,
  open,
  panelStyle,
  marketEnabled,
  loadingPeers,
  peers,
  saving,
  copyingFederationInfo,
  err,
  ok,
  form,
  pasteText,
  pasteErr,
  pasteOk,
  pasteHint,
  importingPaste,
  importedInviteEntries,
  checkingHealth,
  peerHealthMap,
  acceptingInvite,
  inviteErr,
  inviteOk,
  inviteHint,
  inviteForm,
  enabledPeers,
  canRetryInvite,
  toggle,
  onToggleMarket,
  peerSelected,
  togglePeer,
  loadPeers,
  savePeer,
  copyFederationInfo,
  pasteFromClipboard,
  importFederationInfo,
  maskInviteToken,
  applyPeerToForm,
  applyImportedInvite,
  removeImportedInvite,
  checkPeerHealth,
  acceptRoomInvite,
  retryLastAccept,
} = useFedMenu(props)

function countArray(value) {
  const raw = unref(value)
  return Array.isArray(raw) ? raw.length : 0
}

const enabledPeerCount = computed(() => countArray(enabledPeers))
const importedInviteCount = computed(() => countArray(importedInviteEntries))
</script>

<style scoped>
.fed-wrapper {
  position: relative;
  flex-shrink: 0;
}

.fed-btn {
  min-width: 0;
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
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
  font-family: inherit;
  cursor: pointer;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.fed-btn:hover:not(:disabled),
.fed-btn:focus-visible,
.fed-btn.active {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 56%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.fed-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.fed-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 1px solid color-mix(in srgb, var(--selected) 26%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 46%, transparent);
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 780;
  line-height: 1;
}

.btn-text {
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1;
  opacity: 0.96;
}

.btn-caret {
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.78;
}

.fed-popover-scrim {
  position: fixed;
  inset: 0;
  z-index: 2147482999;
  background: color-mix(in srgb, #020617 22%, transparent);
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  animation: fedScrimIn 0.14s ease-out;
}

.fed-panel {
  position: fixed;
  left: 0;
  top: 0;
  width: min(500px, 94vw);
  max-height: min(84vh, 820px);
  overflow-y: auto;
  overflow-x: hidden;
  z-index: 2147483000;
  display: grid;
  gap: 10px;
  box-sizing: border-box;
  padding: 12px;
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
  scrollbar-width: thin;
  isolation: isolate;
  animation: fedPanelGlassIn 0.16s ease-out;
}

.fed-panel::-webkit-scrollbar {
  width: 8px;
}

.fed-panel::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.fed-panel-head {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 10px;
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

.fed-panel-title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.fed-panel-subtitle {
  color: var(--text-secondary);
  font-size: 0.79rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.fed-status-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.36rem;
}

.fed-status-chip {
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

.fed-status-chip.active {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 810;
}

.fed-boundary-card {
  min-width: 0;
  display: grid;
  gap: 7px;
  padding: 9px;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 34%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 62%, transparent)
    );
}

.fed-boundary-title {
  color: var(--text-main);
  font-size: 0.78rem;
  font-weight: 810;
  line-height: 1.35;
}

.fed-boundary-chips {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.fed-boundary-chip {
  max-width: 100%;
  min-height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  font-size: 0.67rem;
  font-weight: 750;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.fed-boundary-chip.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

.fed-boundary-hint {
  color: var(--text-secondary);
  font-size: 0.73rem;
  line-height: 1.48;
  overflow-wrap: break-word;
}

.fed-section,
:deep(.fed-section) {
  display: grid;
  gap: 9px;
  min-width: 0;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.fed-section-compact {
  padding: 9px 10px;
}

.fed-toggle {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  cursor: pointer;
}

.fed-toggle-check {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--selected-bg) 28%, var(--editor-bg));
}

.fed-toggle-check input {
  margin: 0;
  accent-color: var(--selected);
}

.fed-toggle-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.fed-toggle-title {
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 740;
  line-height: 1.4;
}

.fed-foot {
  border-style: dashed;
}

:deep(.row),
:deep(.section-row) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  min-width: 0;
}

:deep(.row.head),
:deep(.section-head) {
  justify-content: space-between;
  align-items: flex-start;
}

:deep(.row.foot) {
  justify-content: flex-start;
}

:deep(.row-actions) {
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex-wrap: wrap;
  min-width: 0;
}

:deep(.ttl) {
  color: var(--text-main);
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.35;
}

:deep(.mini),
:deep(.save) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 31px;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

:deep(.mini:hover:not(:disabled)),
:deep(.mini:focus-visible:not(:disabled)) {
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

:deep(.save) {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected) 88%, #1f2937);
  color: #fff;
}

:deep(.save:hover:not(:disabled)),
:deep(.save:focus-visible:not(:disabled)) {
  opacity: 0.94;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent);
  outline: none;
}

:deep(.mini:active:not(:disabled)),
:deep(.save:active:not(:disabled)) {
  transform: translateY(1px);
}

:deep(.save:disabled),
:deep(.mini:disabled) {
  opacity: 0.56;
  cursor: not-allowed;
}

:deep(.chk) {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  color: var(--text-main);
  font-size: 0.82rem;
  line-height: 1.45;
}

:deep(.peer-list) {
  display: grid;
  gap: 7px;
  min-width: 0;
}

:deep(.peer-item) {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  color: var(--text-main);
  font-size: 0.82rem;
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

:deep(.peer-item input[type='checkbox']) {
  margin-top: 3px;
  accent-color: var(--selected);
}

:deep(.peer-main) {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
}

:deep(.peer-id) {
  min-width: 0;
  max-width: 100%;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}

:deep(.peer-actions) {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
  flex-wrap: wrap;
}

:deep(.peer-use) {
  flex-shrink: 0;
}

:deep(.health-pill) {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 0.44rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 720;
  line-height: 1;
}

:deep(.health-ok) {
  color: #16a34a;
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.08);
}

:deep(.health-bad) {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
}

:deep(.health-warn),
:deep(.health-unknown) {
  color: #d97706;
  border-color: rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.08);
}

:deep(.sep) {
  height: 1px;
  background: color-mix(in srgb, var(--line) 86%, transparent);
}

:deep(.form) {
  display: grid;
  gap: 8px;
  min-width: 0;
}

:deep(.ipt) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 68%, transparent);
  color: var(--text-main);
  padding: 0.62rem 0.68rem;
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.45;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

:deep(.ipt::placeholder) {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

:deep(.ipt:focus) {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 56%, transparent);
}

:deep(.ta) {
  min-height: 118px;
  resize: vertical;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

:deep(.muted) {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

:deep(.err) {
  padding: 8px 9px;
  border: 1px solid rgba(239, 68, 68, 0.32);
  border-radius: 11px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

:deep(.ok) {
  color: #16a34a;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

:deep(.ok-box) {
  display: grid;
  gap: 0.32rem;
  padding: 9px 10px;
  border: 1px solid rgba(34, 197, 94, 0.3);
  background: rgba(34, 197, 94, 0.08);
  border-radius: 11px;
}

:deep(.invite-note) {
  line-height: 1.5;
}

:deep(.draft-list) {
  display: grid;
  gap: 7px;
  min-width: 0;
}

:deep(.draft-item) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 9px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

:deep(.draft-main) {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 4px;
}

:deep(.draft-title) {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  min-width: 0;
}

:deep(.draft-actions) {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

:deep(.danger-lite) {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
}

@keyframes fedScrimIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes fedPanelGlassIn {
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
  .fed-popover-scrim {
    background: color-mix(in srgb, #020617 24%, transparent);
    backdrop-filter: blur(10px) saturate(1.12);
    -webkit-backdrop-filter: blur(10px) saturate(1.12);
  }

  .fed-panel {
    width: min(94vw, 460px);
    max-height: min(84vh, calc(100vh - 16px));
    padding: 11px;
  }

  :deep(.row),
  :deep(.section-row),
  :deep(.row.head),
  :deep(.section-head) {
    align-items: flex-start;
    flex-direction: column;
  }

  :deep(.row-actions),
  :deep(.peer-actions),
  :deep(.draft-actions) {
    width: 100%;
  }

  :deep(.row-actions .mini),
  :deep(.row-actions .save),
  :deep(.peer-actions .mini),
  :deep(.draft-actions .mini) {
    flex: 1 1 auto;
  }

  :deep(.peer-item),
  :deep(.draft-item) {
    flex-direction: column;
  }
}

@media (max-width: 420px) {
  .fed-panel {
    width: calc(100vw - 16px);
  }

  :deep(.row-actions .mini),
  :deep(.row-actions .save),
  :deep(.peer-actions .mini),
  :deep(.draft-actions .mini) {
    width: 100%;
    flex-basis: 100%;
  }
}
</style>
