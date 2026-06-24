<template>
  <div v-if="open" class="nisb-modal-mask" @click.self="$emit('close')">
    <section class="nisb-modal" role="dialog" aria-modal="true" :aria-label="labels.title">
      <header class="modal-head">
        <div class="title-wrap">
          <div class="eyebrow-row">
            <span class="eyebrow-chip">{{ labels.eyebrow }}</span>
            <span class="status-chip">{{ labels.safeChange }}</span>
          </div>
          <h2 class="nisb-modal-title">{{ labels.title }}</h2>
          <p class="modal-desc">{{ labels.description }}</p>
        </div>

        <button
          class="icon-btn"
          :aria-label="labels.close"
          :disabled="working"
          type="button"
          @click="$emit('close')"
        >
          ×
        </button>
      </header>

      <div class="nisb-modal-body">
        <section class="field-card">
          <label class="field-label" for="library-rename-input">
            {{ labels.newFilename }}
          </label>
          <input
            id="library-rename-input"
            class="nisb-input"
            :value="rename_value"
            :placeholder="labels.placeholder"
            :disabled="working"
            @input="$emit('update:rename_value', $event.target.value)"
            @keydown.enter.prevent="$emit('confirm')"
          />
          <p class="field-hint">{{ labels.inputHint }}</p>
        </section>

        <section class="meta-card">
          <div class="card-topline">
            <span class="card-title">{{ labels.currentDocument }}</span>
            <span class="mini-chip">{{ labels.metadata }}</span>
          </div>

          <dl class="meta-list">
            <div class="meta-row">
              <dt>{{ labels.current }}</dt>
              <dd class="natural-value">{{ documentName }}</dd>
            </div>

            <div v-if="documentId" class="meta-row">
              <dt>{{ labels.docIdLabel }}</dt>
              <dd class="machine-value">{{ documentId }}</dd>
            </div>

            <div v-if="documentPath" class="meta-row">
              <dt>{{ labels.pathLabel }}</dt>
              <dd class="machine-value">{{ documentPath }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <footer class="nisb-modal-actions">
        <button class="modal-btn ghost" :disabled="working" @click="$emit('close')" type="button">
          {{ labels.cancel }}
        </button>
        <button class="modal-btn primary" :disabled="working" @click="$emit('confirm')" type="button">
          {{ working ? labels.saving : labels.confirm }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import enLibrary from '../../../locales/en/library'
import zhCNLibrary from '../../../locales/zh-CN/library'

const props = defineProps({
  open: { type: Boolean, default: false },
  target_doc: { type: Object, default: null },
  rename_value: { type: String, default: '' },
  working: { type: Boolean, default: false },
  locale: { type: String, default: '' },
  t: { type: Function, default: null }
})

defineEmits(['close', 'confirm', 'update:rename_value'])

const LIBRARY_LOCALES = {
  en: enLibrary,
  'zh-CN': zhCNLibrary
}

function stringValue(value) {
  return String(value ?? '').trim()
}

function normalizeLocale(value) {
  const raw = stringValue(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function localStorageFirst(keys, fallback = '') {
  for (const key of keys) {
    try {
      if (typeof localStorage === 'undefined') continue
      const value = localStorage.getItem(key)
      if (value !== null && stringValue(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function currentLocale(explicitLocale = '') {
  if (stringValue(explicitLocale)) return normalizeLocale(explicitLocale)

  const fromWindow = (() => {
    try {
      if (typeof window === 'undefined') return ''
      return (
        window?.__nisb_locale ||
        window?.__nisb_ui_locale ||
        window?.__NISB_LOCALE__ ||
        window?.__NISB_UI_LOCALE__ ||
        ''
      )
    } catch {
      return ''
    }
  })()

  const fromStorage = localStorageFirst(
    [
      'nisb_locale',
      'nisb_ui_locale',
      'nisb_language',
      'nisb_settings_locale',
      'locale',
      'ui_locale',
      'language'
    ],
    ''
  )

  const fromDocument = (() => {
    try {
      if (typeof document === 'undefined') return ''
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  return normalizeLocale(fromWindow || fromStorage || fromDocument || 'en')
}

function deepGet(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function formatText(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function text(path, params = {}, fallback = '') {
  if (typeof props.t === 'function') {
    const externalValue = props.t(path, params)
    if (stringValue(externalValue) && externalValue !== path) return externalValue
  }

  const locale = currentLocale(props.locale)
  const messages = LIBRARY_LOCALES[locale] || LIBRARY_LOCALES.en
  const value = deepGet(messages, path, deepGet(LIBRARY_LOCALES.en, path, fallback))
  return formatText(value || fallback || path, params)
}

const labels = computed(() => ({
  title: text('center.renameDocModal.title', {}, 'Rename book'),
  eyebrow: text('center.renameDocModal.eyebrow', {}, 'Library document'),
  safeChange: text('center.renameDocModal.safeChange', {}, 'Display name only'),
  close: text('center.renameDocModal.close', {}, 'Close'),
  description: text(
    'center.renameDocModal.description',
    {},
    'Only the display name will be changed. The library-level index and metadata.json will be updated, but doc_id will not change.'
  ),
  newFilename: text('center.renameDocModal.newFilename', {}, 'New filename'),
  placeholder: text('center.renameDocModal.placeholder', {}, 'Example: my_book.txt'),
  inputHint: text('center.renameDocModal.inputHint', {}, 'The stored document identity remains unchanged.'),
  currentDocument: text('center.renameDocModal.currentDocument', {}, 'Current document'),
  metadata: text('center.renameDocModal.metadata', {}, 'Metadata'),
  current: text('center.renameDocModal.current', {}, 'Current'),
  docIdLabel: text('center.renameDocModal.docIdLabel', {}, 'doc_id'),
  pathLabel: text('center.renameDocModal.pathLabel', {}, 'path'),
  unknownDocument: text('center.renameDocModal.unknownDocument', {}, 'Untitled document'),
  cancel: text('center.renameDocModal.cancel', {}, 'Cancel'),
  saving: text('center.renameDocModal.saving', {}, 'Saving…'),
  confirm: text('center.renameDocModal.confirm', {}, 'Confirm rename')
}))

const documentName = computed(() => {
  return (
    stringValue(props.target_doc?.filename) ||
    stringValue(props.target_doc?.title) ||
    stringValue(props.target_doc?.name) ||
    stringValue(props.target_doc?.doc_id) ||
    labels.value.unknownDocument
  )
})

const documentId = computed(() => stringValue(props.target_doc?.doc_id))
const documentPath = computed(() => {
  return (
    stringValue(props.target_doc?.path) ||
    stringValue(props.target_doc?.source_path) ||
    stringValue(props.target_doc?.file_path) ||
    stringValue(props.target_doc?.uri)
  )
})
</script>

<style scoped>
.nisb-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 2147483000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background:
    radial-gradient(circle at 18% 12%, rgba(84, 132, 255, 0.18), transparent 34%),
    radial-gradient(circle at 86% 18%, rgba(22, 163, 74, 0.12), transparent 30%),
    rgba(12, 18, 32, 0.42);
  backdrop-filter: blur(18px) saturate(1.08);
  -webkit-backdrop-filter: blur(18px) saturate(1.08);
}

.nisb-modal {
  width: min(560px, calc(100vw - 28px));
  max-height: min(720px, calc(100vh - 28px));
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, rgba(255, 255, 255, 0.45));
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--editor-bg) 92%, transparent), color-mix(in srgb, var(--sidebar-bg) 78%, transparent)),
    color-mix(in srgb, var(--editor-bg) 88%, transparent);
  box-shadow:
    0 24px 80px rgba(15, 23, 42, 0.28),
    0 1px 0 rgba(255, 255, 255, 0.28) inset;
  color: var(--text);
}

.modal-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1rem 0.85rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
}

.title-wrap {
  min-width: 0;
}

.eyebrow-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
}

.eyebrow-chip,
.status-chip,
.mini-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  max-width: 100%;
  padding: 0.18rem 0.58rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 78%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.status-chip {
  border-color: color-mix(in srgb, #16a34a 45%, var(--line));
  background: color-mix(in srgb, #16a34a 10%, transparent);
  color: color-mix(in srgb, #16a34a 82%, var(--text));
}

.nisb-modal-title {
  margin: 0;
  color: var(--text);
  font-size: 0.98rem;
  font-weight: 820;
  line-height: 1.28;
  overflow-wrap: break-word;
}

.modal-desc {
  max-width: 46rem;
  margin: 0.42rem 0 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.icon-btn {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 1.18rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.icon-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
  transform: translateY(-1px);
}

.icon-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.nisb-modal-body {
  display: grid;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  overflow: auto;
  max-height: calc(100vh - 220px);
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 80%, transparent) transparent;
}

.nisb-modal-body::-webkit-scrollbar {
  width: 8px;
}

.nisb-modal-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 82%, transparent);
}

.field-card,
.meta-card {
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--sidebar-bg) 72%, transparent), color-mix(in srgb, var(--editor-bg) 62%, transparent));
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.field-card {
  padding: 0.9rem;
}

.field-label {
  display: block;
  margin-bottom: 0.42rem;
  color: var(--text);
  font-size: 0.76rem;
  font-weight: 780;
  line-height: 1.3;
}

.nisb-input {
  width: 100%;
  min-height: 42px;
  padding: 0.62rem 0.72rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  outline: none;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text);
  font-size: 0.86rem;
  line-height: 1.45;
  overflow-wrap: break-word;
  transition:
    border-color var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    background var(--transition-normal) var(--ease-smooth);
}

.nisb-input:focus {
  border-color: var(--selected);
  background: color-mix(in srgb, var(--editor-bg) 94%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 18%, transparent);
}

.nisb-input:disabled {
  opacity: 0.64;
  cursor: not-allowed;
}

.field-hint {
  margin: 0.46rem 0 0;
  color: var(--text-secondary);
  font-size: 0.77rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.meta-card {
  padding: 0.85rem;
}

.card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  margin-bottom: 0.65rem;
}

.card-title {
  min-width: 0;
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.meta-list {
  display: grid;
  gap: 0.5rem;
  margin: 0;
}

.meta-row {
  display: grid;
  grid-template-columns: minmax(86px, 0.32fr) minmax(0, 1fr);
  gap: 0.65rem;
  align-items: start;
  padding: 0.56rem 0.6rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 56%, transparent);
}

.meta-row dt {
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.meta-row dd {
  min-width: 0;
  margin: 0;
  color: var(--text);
  font-size: 0.8rem;
  line-height: 1.45;
}

.natural-value {
  overflow-wrap: break-word;
}

.machine-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  overflow-wrap: anywhere;
}

.nisb-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  padding: 0.85rem 1rem 1rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 42%, transparent);
}

.modal-btn {
  min-height: 38px;
  padding: 0.5rem 0.9rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 780;
  line-height: 1.25;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.modal-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.modal-btn.ghost:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.modal-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 64%, var(--line));
  background: linear-gradient(135deg, color-mix(in srgb, var(--selected) 92%, #ffffff 6%), color-mix(in srgb, var(--selected) 72%, #111827 8%));
  color: #ffffff;
  box-shadow: 0 12px 28px color-mix(in srgb, var(--selected) 28%, transparent);
}

.modal-btn.primary:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 78%, #ffffff);
  box-shadow: 0 16px 34px color-mix(in srgb, var(--selected) 34%, transparent);
}

.modal-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (max-width: 640px) {
  .nisb-modal-mask {
    align-items: stretch;
    padding: 0.65rem;
  }

  .nisb-modal {
    width: 100%;
    max-height: calc(100vh - 1.3rem);
    display: flex;
    flex-direction: column;
    border-radius: 18px;
  }

  .modal-head {
    padding: 0.9rem 0.85rem 0.78rem;
  }

  .nisb-modal-body {
    flex: 1;
    max-height: none;
    padding: 0.8rem 0.85rem;
  }

  .meta-row {
    grid-template-columns: 1fr;
    gap: 0.22rem;
  }

  .nisb-modal-actions {
    flex-direction: column-reverse;
    padding: 0.8rem 0.85rem 0.9rem;
  }

  .modal-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
