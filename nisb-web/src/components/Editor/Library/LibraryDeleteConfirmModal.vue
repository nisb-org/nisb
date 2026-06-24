<template>
  <div v-if="open" class="nisb-modal-mask" @click.self="$emit('close')">
    <section class="nisb-modal danger-modal" role="dialog" aria-modal="true" :aria-label="labels.title">
      <header class="modal-head">
        <div class="title-wrap">
          <div class="eyebrow-row">
            <span class="danger-chip">{{ labels.eyebrow }}</span>
            <span class="irreversible-chip">{{ labels.irreversible }}</span>
          </div>
          <h2 class="nisb-modal-title">{{ labels.title }}</h2>
          <p class="modal-desc">{{ labels.warning }}</p>
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
        <section class="danger-card">
          <div class="card-topline">
            <span class="card-title">{{ labels.deletionScope }}</span>
            <span class="mini-danger">{{ labels.permanent }}</span>
          </div>

          <div class="scope-grid">
            <span class="scope-chip">{{ labels.sourceText }}</span>
            <span class="scope-chip">{{ labels.analysisResults }}</span>
            <span class="scope-chip">{{ labels.translationCache }}</span>
          </div>
        </section>

        <section class="meta-card">
          <div class="card-topline">
            <span class="card-title">{{ labels.documentIdentity }}</span>
            <span class="mini-chip">{{ labels.metadata }}</span>
          </div>

          <dl class="meta-list">
            <div class="meta-row">
              <dt>{{ labels.documentLabel }}</dt>
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

            <div v-if="artifactId" class="meta-row">
              <dt>{{ labels.artifactIdLabel }}</dt>
              <dd class="machine-value">{{ artifactId }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <footer class="nisb-modal-actions">
        <button class="modal-btn ghost" :disabled="working" @click="$emit('close')" type="button">
          {{ labels.cancel }}
        </button>
        <button class="modal-btn danger" :disabled="working" @click="$emit('confirm')" type="button">
          {{ working ? labels.deleting : labels.confirm }}
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
  working: { type: Boolean, default: false },
  locale: { type: String, default: '' },
  t: { type: Function, default: null }
})

defineEmits(['close', 'confirm'])

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
  title: text('center.deleteConfirmModal.title', {}, 'Delete book?'),
  eyebrow: text('center.deleteConfirmModal.eyebrow', {}, 'Danger zone'),
  irreversible: text('center.deleteConfirmModal.irreversible', {}, 'Irreversible'),
  close: text('center.deleteConfirmModal.close', {}, 'Close'),
  warning: text(
    'center.deleteConfirmModal.warning',
    {},
    'This will delete the document source text, analysis results, and translation cache. This action cannot be undone.'
  ),
  deletionScope: text('center.deleteConfirmModal.deletionScope', {}, 'Deletion scope'),
  permanent: text('center.deleteConfirmModal.permanent', {}, 'Permanent'),
  sourceText: text('center.deleteConfirmModal.sourceText', {}, 'Source text'),
  analysisResults: text('center.deleteConfirmModal.analysisResults', {}, 'Analysis results'),
  translationCache: text('center.deleteConfirmModal.translationCache', {}, 'Translation cache'),
  documentIdentity: text('center.deleteConfirmModal.documentIdentity', {}, 'Document identity'),
  metadata: text('center.deleteConfirmModal.metadata', {}, 'Metadata'),
  documentLabel: text('center.deleteConfirmModal.documentLabel', {}, 'Document'),
  docIdLabel: text('center.deleteConfirmModal.docIdLabel', {}, 'doc_id'),
  pathLabel: text('center.deleteConfirmModal.pathLabel', {}, 'path'),
  artifactIdLabel: text('center.deleteConfirmModal.artifactIdLabel', {}, 'artifact_id'),
  unknownDocument: text('center.deleteConfirmModal.unknownDocument', {}, 'Untitled document'),
  cancel: text('center.deleteConfirmModal.cancel', {}, 'Cancel'),
  deleting: text('center.deleteConfirmModal.deleting', {}, 'Deleting…'),
  confirm: text('center.deleteConfirmModal.confirm', {}, 'Confirm delete')
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
const artifactId = computed(() => stringValue(props.target_doc?.artifact_id))
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
    radial-gradient(circle at 18% 12%, rgba(239, 68, 68, 0.16), transparent 34%),
    radial-gradient(circle at 86% 18%, rgba(217, 119, 6, 0.12), transparent 30%),
    rgba(12, 18, 32, 0.46);
  backdrop-filter: blur(18px) saturate(1.08);
  -webkit-backdrop-filter: blur(18px) saturate(1.08);
}

.nisb-modal {
  width: min(570px, calc(100vw - 28px));
  max-height: min(740px, calc(100vh - 28px));
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, rgba(255, 255, 255, 0.45));
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--editor-bg) 92%, transparent), color-mix(in srgb, var(--sidebar-bg) 78%, transparent)),
    color-mix(in srgb, var(--editor-bg) 88%, transparent);
  box-shadow:
    0 24px 80px rgba(15, 23, 42, 0.3),
    0 1px 0 rgba(255, 255, 255, 0.26) inset;
  color: var(--text);
}

.danger-modal {
  border-color: color-mix(in srgb, #ef4444 30%, var(--line));
}

.modal-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1rem 0.85rem;
  border-bottom: 1px solid color-mix(in srgb, #ef4444 18%, var(--line));
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

.danger-chip,
.irreversible-chip,
.mini-chip,
.mini-danger {
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

.danger-chip,
.mini-danger {
  border-color: color-mix(in srgb, #ef4444 52%, var(--line));
  background: color-mix(in srgb, #ef4444 11%, transparent);
  color: color-mix(in srgb, #ef4444 86%, var(--text));
}

.irreversible-chip {
  border-color: color-mix(in srgb, #d97706 48%, var(--line));
  background: color-mix(in srgb, #d97706 11%, transparent);
  color: color-mix(in srgb, #d97706 84%, var(--text));
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
  max-width: 48rem;
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
  border-color: color-mix(in srgb, #ef4444 54%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: color-mix(in srgb, #ef4444 84%, var(--text));
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

.danger-card,
.meta-card {
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--sidebar-bg) 72%, transparent), color-mix(in srgb, var(--editor-bg) 62%, transparent));
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.danger-card {
  padding: 0.85rem;
  border-color: color-mix(in srgb, #ef4444 24%, var(--line));
  background:
    linear-gradient(145deg, color-mix(in srgb, #ef4444 8%, transparent), color-mix(in srgb, var(--editor-bg) 70%, transparent));
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

.scope-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  min-height: 25px;
  max-width: 100%;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, #ef4444 28%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text);
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.meta-list {
  display: grid;
  gap: 0.5rem;
  margin: 0;
}

.meta-row {
  display: grid;
  grid-template-columns: minmax(92px, 0.32fr) minmax(0, 1fr);
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
  border-top: 1px solid color-mix(in srgb, #ef4444 18%, var(--line));
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

.modal-btn.danger {
  border-color: color-mix(in srgb, #ef4444 70%, var(--line));
  background: linear-gradient(135deg, color-mix(in srgb, #ef4444 92%, #ffffff 4%), color-mix(in srgb, #b91c1c 82%, #111827 8%));
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(239, 68, 68, 0.24);
}

.modal-btn.danger:hover:not(:disabled) {
  border-color: color-mix(in srgb, #ef4444 78%, #ffffff);
  box-shadow: 0 16px 34px rgba(239, 68, 68, 0.3);
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
