<template>
  <section class="documents-section" aria-live="polite">
    <header class="section-header">
      <div class="section-title-wrap">
        <span class="section-icon" aria-hidden="true">▣</span>
        <div class="section-copy">
          <h2 class="section-title">{{ labels.title }}</h2>
          <p class="section-subtitle">{{ labels.subtitle }}</p>
        </div>
      </div>

      <div class="section-chips">
        <span class="count-chip">{{ text('center.documentsList.count', { count: document_count }, '{count} documents') }}</span>
        <span v-if="selectedDoc" class="selected-chip">{{ labels.selected }}</span>
      </div>
    </header>

    <div v-if="loadingDocs" class="state-card">
      <div class="state-icon" aria-hidden="true">…</div>
      <div class="state-copy">
        <div class="state-title">{{ labels.loading }}</div>
        <div class="state-desc">{{ labels.loadingDescription }}</div>
      </div>
    </div>

    <div v-else-if="!documents || !documents.length" class="state-card empty">
      <div class="state-icon" aria-hidden="true">∅</div>
      <div class="state-copy">
        <div class="state-title">{{ labels.empty }}</div>
        <div class="state-desc">{{ labels.emptyDescription }}</div>
      </div>
    </div>

    <div v-else class="doc-list">
      <article
        v-for="doc in documents"
        :key="doc.doc_id"
        class="doc-item"
        :class="{ active: is_active_doc(doc) }"
      >
        <button class="doc-main" type="button" @click="$emit('select-doc', doc)">
          <span class="doc-main-top">
            <span class="doc-name">{{ display_doc_name(doc) }}</span>
            <span v-if="is_active_doc(doc)" class="active-badge">{{ labels.active }}</span>
          </span>

          <span class="doc-meta-row">
            <span class="filetype-chip">{{ doc.filetype || labels.fallbackFiletype }}</span>
            <span class="doc-meta-text">{{ text('center.documentsList.chunks', { count: doc.chunks || 0 }, '{count} chunks') }}</span>
            <span v-if="doc.created_at" class="doc-meta-text">
              {{ labels.createdAt }}{{ labels.labelSeparator }}{{ formatTime(doc.created_at) }}
            </span>
          </span>

          <span v-if="doc.doc_id" class="doc-id-line">
            <span class="doc-id-label">{{ labels.docId }}</span>
            <span class="machine-value">{{ doc.doc_id }}</span>
          </span>
        </button>

        <div class="doc-actions" :aria-label="labels.actionsAria">
          <button class="doc-btn primary" type="button" @click.stop="$emit('select-doc', doc)">
            {{ is_active_doc(doc) ? labels.collapseActions : labels.viewActions }}
          </button>
          <button class="doc-btn" type="button" @click.stop="$emit('rename-doc', doc)">
            {{ labels.rename }}
          </button>
          <button class="doc-btn" type="button" @click.stop="$emit('show-doc-info', doc)">
            {{ labels.details }}
          </button>
          <button class="doc-btn danger" type="button" @click.stop="$emit('delete-doc', doc)">
            {{ labels.delete }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import enLibrary from '../../../locales/en/library'
import zhCNLibrary from '../../../locales/zh-CN/library'

const props = defineProps({
  documents: { type: Array, default: () => [] },
  loadingDocs: { type: Boolean, default: false },
  selectedDoc: { type: Object, default: null },
  formatTime: { type: Function, required: true },
  locale: { type: String, default: '' },
  t: { type: Function, default: null }
})

defineEmits(['select-doc', 'show-doc-info', 'delete-doc', 'rename-doc'])

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
  title: text('center.documentsList.title', {}, 'Documents'),
  subtitle: text('center.documentsList.subtitle', {}, 'Browse documents in the current library.'),
  loading: text('center.documentsList.loading', {}, 'Loading documents…'),
  loadingDescription: text('center.documentsList.loadingDescription', {}, 'Preparing the library document index.'),
  empty: text('center.documentsList.empty', {}, 'No documents yet'),
  emptyDescription: text('center.documentsList.emptyDescription', {}, 'Upload documents to start reading, analyzing, and translating.'),
  fallbackFiletype: text('center.documentsList.fallbackFiletype', {}, 'txt'),
  createdAt: text('center.documentsList.createdAt', {}, 'Created'),
  labelSeparator: text('center.documentsList.labelSeparator', {}, ': '),
  selected: text('center.documentsList.selected', {}, 'Document selected'),
  active: text('center.documentsList.active', {}, 'Active'),
  docId: text('center.documentsList.docId', {}, 'doc_id'),
  actionsAria: text('center.documentsList.actionsAria', {}, 'Document actions'),
  viewActions: text('center.documentsList.viewActions', {}, 'View'),
  collapseActions: text('center.documentsList.collapseActions', {}, 'Collapse'),
  rename: text('center.documentsList.rename', {}, 'Rename'),
  details: text('center.documentsList.details', {}, 'Details'),
  delete: text('center.documentsList.delete', {}, 'Delete'),
  unknownDocument: text('center.documentsList.unknownDocument', {}, 'Untitled document')
}))

const document_count = computed(() => {
  return Array.isArray(props.documents) ? props.documents.length : 0
})

function display_doc_name(doc) {
  return (
    stringValue(doc?.filename) ||
    stringValue(doc?.title) ||
    stringValue(doc?.name) ||
    stringValue(doc?.doc_id) ||
    labels.value.unknownDocument
  )
}

function is_active_doc(doc) {
  return !!props.selectedDoc && !!doc && props.selectedDoc.doc_id === doc.doc_id
}
</script>

<style scoped>
.documents-section {
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
  min-width: 0;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.8rem 0.86rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--sidebar-bg) 76%, transparent), color-mix(in srgb, var(--editor-bg) 64%, transparent));
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.section-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.62rem;
  min-width: 0;
}

.section-icon {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 12px;
  background: color-mix(in srgb, var(--selected-bg) 72%, transparent);
  color: var(--selected);
  font-size: 0.9rem;
  font-weight: 800;
}

.section-copy {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.section-title {
  margin: 0;
  color: var(--text);
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.28;
  overflow-wrap: break-word;
}

.section-subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.section-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.4rem;
  flex: 0 0 auto;
}

.count-chip,
.selected-chip,
.filetype-chip,
.active-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  max-width: 100%;
  padding: 0.18rem 0.58rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 76%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.selected-chip,
.active-badge {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 86%, transparent);
  color: var(--selected);
}

.state-card {
  min-height: 132px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--sidebar-bg) 68%, transparent), color-mix(in srgb, var(--editor-bg) 58%, transparent));
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.state-icon {
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 70%, transparent);
  color: var(--text-secondary);
  font-size: 1rem;
  font-weight: 820;
}

.state-copy {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.state-title {
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 820;
  line-height: 1.34;
  overflow-wrap: break-word;
}

.state-desc {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.48;
  overflow-wrap: break-word;
}

.doc-list {
  display: grid;
  gap: 0.56rem;
  min-width: 0;
}

.doc-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.72rem;
  align-items: center;
  min-width: 0;
  padding: 0.72rem;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--editor-bg) 86%, transparent), color-mix(in srgb, var(--sidebar-bg) 58%, transparent));
  box-shadow:
    0 10px 28px rgba(15, 23, 42, 0.05),
    0 1px 0 rgba(255, 255, 255, 0.16) inset;
  transition:
    border-color var(--transition-normal) var(--ease-smooth),
    background var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.doc-item:hover {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg)), color-mix(in srgb, var(--sidebar-bg) 68%, transparent));
  box-shadow:
    0 16px 34px rgba(15, 23, 42, 0.08),
    0 0 0 1px color-mix(in srgb, var(--selected) 10%, transparent);
  transform: translateY(-1px);
}

.doc-item.active {
  border-color: color-mix(in srgb, var(--selected) 70%, var(--line));
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--selected-bg) 76%, transparent), color-mix(in srgb, var(--editor-bg) 72%, transparent));
  box-shadow:
    0 18px 38px rgba(15, 23, 42, 0.1),
    0 0 0 2px color-mix(in srgb, var(--selected) 14%, transparent);
}

.doc-main {
  min-width: 0;
  display: grid;
  gap: 0.36rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.doc-main-top {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
}

.doc-name {
  min-width: 0;
  color: var(--text);
  font-size: 0.9rem;
  font-weight: 780;
  line-height: 1.38;
  overflow-wrap: break-word;
}

.doc-meta-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.36rem;
}

.filetype-chip {
  min-height: 22px;
  padding: 0.14rem 0.5rem;
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.doc-meta-text {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.42;
  overflow-wrap: break-word;
}

.doc-id-line {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  align-items: baseline;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.45;
}

.doc-id-label {
  font-weight: 760;
}

.machine-value {
  min-width: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  overflow-wrap: anywhere;
}

.doc-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.36rem;
  max-width: min(48vw, 430px);
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.08rem;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.doc-actions::-webkit-scrollbar {
  display: none;
}

.doc-btn {
  min-height: 34px;
  flex: 0 0 auto;
  padding: 0.42rem 0.68rem;
  border-radius: 11px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.doc-btn:hover {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
  transform: translateY(-1px);
}

.doc-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 78%, transparent);
  color: var(--selected);
}

.doc-btn.danger {
  border-color: color-mix(in srgb, #ef4444 30%, var(--line));
  color: color-mix(in srgb, #ef4444 72%, var(--text-secondary));
}

.doc-btn.danger:hover {
  border-color: color-mix(in srgb, #ef4444 62%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: color-mix(in srgb, #ef4444 86%, var(--text));
}

@media (max-width: 980px) {
  .doc-item {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .doc-actions {
    max-width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .section-header {
    align-items: stretch;
    flex-direction: column;
  }

  .section-chips {
    justify-content: flex-start;
  }

  .doc-item {
    padding: 0.66rem;
    border-radius: 15px;
  }

  .doc-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: visible;
  }

  .doc-btn {
    width: 100%;
    justify-content: center;
    text-align: center;
  }
}

@media (max-width: 420px) {
  .doc-actions {
    grid-template-columns: 1fr;
  }

  .doc-main-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .active-badge {
    align-self: flex-start;
  }
}
</style>
