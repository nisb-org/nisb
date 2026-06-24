<!-- nisb-web/src/components/Editor/Chat/ChatAttachmentModal.vue -->
<template>
  <div
    class="attachment-modal-mask"
    @click="emit('close')"
    @keydown.esc="emit('close')"
  >
    <section
      class="attachment-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="chat-attachment-modal-title"
      aria-describedby="chat-attachment-modal-desc"
      @click.stop
    >
      <header class="modal-head">
        <div class="title-stack">
          <div id="chat-attachment-modal-title" class="modal-title">
            {{ t('chat.panel.filePicker.title') }}
          </div>
          <div id="chat-attachment-modal-desc" class="modal-subtitle">
            {{ displayPath }}
          </div>
        </div>

        <button
          class="icon-btn close"
          type="button"
          :aria-label="t('common.close')"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <div class="path-surface">
        <div class="path-main">
          <span class="path-label">{{ t('chat.panel.filePicker.currentDir') }}</span>
          <span class="path-value mono" :title="displayPath">{{ displayPath }}</span>
        </div>

        <button
          v-if="canGoParent"
          class="btn mini"
          type="button"
          :title="t('chat.panel.filePicker.goParent')"
          @click="emit('go-parent')"
        >
          ↑
        </button>
      </div>

      <div class="search-row">
        <input
          :value="searchQuery"
          type="text"
          class="search-input"
          :placeholder="t('chat.panel.filePicker.searchPlaceholder')"
          @input="emit('update:searchQuery', $event.target.value)"
        />
      </div>

      <div class="modal-body">
        <div v-if="loading" class="state-card loading-state" aria-busy="true">
          <div class="spinner" aria-hidden="true"></div>
          <div class="state-title">{{ t('chat.panel.filePicker.loading') }}</div>
        </div>

        <div v-else-if="entries.length === 0" class="state-card empty-state">
          <div class="state-icon" aria-hidden="true">📁</div>
          <div class="state-title">{{ t('chat.panel.filePicker.empty') }}</div>
        </div>

        <div v-else class="entry-list">
          <button
            v-for="entry in entries"
            :key="entry.path || entry.name"
            class="entry-item"
            type="button"
            @click="handleEntryClick(entry)"
          >
            <span
              class="file-icon"
              :class="{ directory: entry.type === 'directory' }"
              aria-hidden="true"
            >
              {{ entry.type === 'directory' ? '📁' : resolveFileIcon(entry) }}
            </span>

            <span class="entry-main">
              <span class="file-name" :title="entryDisplayName(entry)">
                {{ entryDisplayName(entry) }}<span v-if="entry.type === 'directory'">/</span>
              </span>
              <span class="file-path mono" :title="entryDisplayPath(entry)">
                {{ entryDisplayPath(entry) }}
              </span>
            </span>

            <span class="entry-kind">
              {{ entryKindLabel(entry) }}
            </span>
          </button>
        </div>
      </div>

      <footer class="modal-foot">
        <span class="foot-hint mono" :title="displayPath">{{ displayPath }}</span>
        <button class="btn" type="button" @click="emit('close')">
          {{ t('common.close') }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  currentDir: { type: String, default: '' },
  searchQuery: { type: String, default: '' },
  entries: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  getFileIcon: { type: Function, default: null },
})

const emit = defineEmits([
  'close',
  'go-parent',
  'enter-directory',
  'select-file',
  'update:searchQuery',
])

const { t } = useI18n()

const INTERNAL_ROOT = 'agent_files'
const USER_ROOT = 'user'

const displayPath = computed(() => {
  return displayWorkspacePath(props.currentDir)
})

const canGoParent = computed(() => {
  const dir = normalizePathText(props.currentDir)
  return !!dir && dir !== INTERNAL_ROOT && dir !== USER_ROOT
})

function normalizePathText(value) {
  return String(value ?? '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/{2,}/g, '/')
    .replace(/\/+$/, '')
}

function displayWorkspacePath(value) {
  const raw = normalizePathText(value)

  if (!raw) return USER_ROOT
  if (raw === USER_ROOT) return USER_ROOT
  if (raw.startsWith(`${USER_ROOT}/`)) return raw
  if (raw === INTERNAL_ROOT) return USER_ROOT
  if (raw.startsWith(`${INTERNAL_ROOT}/`)) {
    const rest = raw.slice(INTERNAL_ROOT.length + 1)
    return rest ? `${USER_ROOT}/${rest}` : USER_ROOT
  }

  return `${USER_ROOT}/${raw}`
}

function entryDisplayPath(entry) {
  return displayWorkspacePath(entry?.path || entry?.relative_path || entry?.name || '')
}

function entryDisplayName(entry) {
  const rawName = normalizePathText(entry?.name || '')
  const rawPath = normalizePathText(entry?.path || entry?.relative_path || '')

  if (rawName && rawName !== INTERNAL_ROOT && !rawName.startsWith(`${INTERNAL_ROOT}/`)) {
    return rawName.split('/').filter(Boolean).pop() || rawName
  }

  const visible = displayWorkspacePath(rawPath || rawName)
  const parts = visible.split('/').filter(Boolean)
  return parts[parts.length - 1] || USER_ROOT
}

function entryKindLabel(entry) {
  if (entry?.type === 'directory') return t('chat.panel.filePicker.kind.directory')
  return t('chat.panel.filePicker.kind.file')
}

function resolveFileIcon(entry) {
  if (props.getFileIcon) return props.getFileIcon(entry?.name || '')
  return '📄'
}

function handleEntryClick(entry) {
  if (!entry) return

  if (entry.type === 'directory') {
    emit('enter-directory', entry)
    return
  }

  emit('select-file', entry)
}
</script>

<style scoped>
.attachment-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 2147483000;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 24px;
  overflow: hidden;
  background: color-mix(in srgb, #020617 26%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: fadeIn 0.16s ease-out;
}

.attachment-modal {
  width: min(760px, 96vw);
  max-height: min(86vh, calc(100vh - 32px));
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, #111827);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 22px 68px rgba(0, 0, 0, 0.28);
  animation: liftIn 0.18s ease-out;
}

.modal-head {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin: 0.62rem 0.62rem 0;
  padding: 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 26%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.title-stack {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.34rem;
}

.modal-title {
  min-width: 0;
  color: var(--text-main, #111827);
  font-size: 0.94rem;
  font-weight: 830;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.modal-subtitle {
  min-width: 0;
  color: var(--text-secondary, #64748b);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.icon-btn {
  flex: 0 0 auto;
  width: 31px;
  height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  font-family: inherit;
  font-size: 1rem;
  font-weight: 760;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.14s ease;
}

.icon-btn:hover,
.icon-btn:focus-visible {
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

.icon-btn:active {
  transform: translateY(1px);
}

.path-surface {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.62rem;
  margin: 0.58rem 0.62rem 0;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
}

.path-main {
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.path-label {
  flex: 0 0 auto;
  color: var(--text-secondary, #64748b);
  font-size: 0.73rem;
  font-weight: 740;
  line-height: 1.35;
  white-space: nowrap;
}

.path-value {
  min-width: 0;
  color: var(--text-main, #111827);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-row {
  flex: 0 0 auto;
  padding: 0.58rem 0.62rem 0;
}

.search-input {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-main, #111827);
  outline: none;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 680;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.search-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
  opacity: 0.92;
}

.search-input:focus {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.modal-body {
  flex: 1 1 auto;
  min-height: 180px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.62rem;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.entry-list {
  min-width: 0;
  display: grid;
  gap: 0.56rem;
}

.entry-item {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.66rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 44%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.14s ease;
}

.entry-item:hover,
.entry-item:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  outline: none;
}

.entry-item:active {
  transform: translateY(1px);
}

.file-icon {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  font-size: 1rem;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.file-icon.directory {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
}

.entry-main {
  min-width: 0;
  flex: 1 1 auto;
  display: grid;
  gap: 0.2rem;
}

.file-name {
  min-width: 0;
  color: var(--text-main, #111827);
  font-size: 0.82rem;
  font-weight: 810;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-item:hover .file-name,
.entry-item:focus-visible .file-name {
  color: var(--selected);
}

.file-path {
  min-width: 0;
  color: var(--text-secondary, #64748b);
  font-size: 0.7rem;
  line-height: 1.4;
  opacity: 0.94;
  overflow-wrap: anywhere;
}

.entry-kind {
  flex: 0 0 auto;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary, #64748b);
  font-size: 0.69rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
}

.state-card {
  min-width: 0;
  margin: 0.2rem;
  padding: 1.2rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary, #64748b);
  text-align: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.loading-state,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.58rem;
}

.state-icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  line-height: 1;
}

.state-title {
  color: var(--text-secondary, #64748b);
  font-size: 0.82rem;
  font-weight: 740;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-top-color: var(--selected);
  border-radius: 999px;
  animation: spin 0.82s linear infinite;
}

.modal-foot {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  margin: 0 0.62rem 0.62rem;
  padding: 0.56rem;
  border: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
}

.foot-hint {
  min-width: 0;
  flex: 1 1 auto;
  color: var(--text-secondary, #64748b);
  font-size: 0.7rem;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn {
  flex: 0 0 auto;
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.73rem;
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

.btn.mini {
  min-height: 28px;
  padding: 0 0.58rem;
  font-size: 0.72rem;
}

.btn:hover,
.btn:focus-visible {
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

.btn:active {
  transform: translateY(1px);
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
  overflow-wrap: anywhere;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes liftIn {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .attachment-modal-mask {
    align-items: stretch;
    padding: 8px;
  }

  .attachment-modal {
    width: 100%;
    max-height: calc(100vh - 16px);
    border-radius: 14px;
  }

  .modal-head {
    margin: 0.48rem 0.48rem 0;
  }

  .path-surface {
    align-items: stretch;
    flex-direction: column;
    margin: 0.58rem 0.48rem 0;
  }

  .path-main {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.28rem;
  }

  .path-value {
    width: 100%;
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .path-surface .btn {
    width: 100%;
  }

  .search-row {
    padding: 0.58rem 0.48rem 0;
  }

  .modal-body {
    padding: 0.48rem;
  }

  .entry-item {
    align-items: flex-start;
  }

  .entry-kind {
    display: none;
  }

  .file-name {
    white-space: normal;
    overflow-wrap: break-word;
  }

  .modal-foot {
    align-items: stretch;
    flex-direction: column;
    margin: 0 0.48rem 0.48rem;
  }

  .modal-foot .btn {
    width: 100%;
  }

  .foot-hint {
    white-space: normal;
    overflow-wrap: anywhere;
  }
}
</style>
