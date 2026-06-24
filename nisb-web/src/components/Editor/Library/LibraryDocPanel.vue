<template>
  <div class="doc-panel" v-if="doc">
    <div class="doc-panel-scroll" ref="doc_panel_scroller">
      <div v-if="show_doc_actions" class="doc-panel-header">
        <div class="doc-panel-actions" :aria-label="t('library.center.docPanel.actionsAriaLabel')">
          <button
            v-for="a in actions"
            :key="a.key"
            class="action-pill"
            :class="{ active: doc_action_type === a.key }"
            @click="run_doc_action(a.key)"
            :disabled="doc_action_loading"
          >
            {{ doc_action_loading && doc_action_type === a.key ? a.loadingText : a.label }}
          </button>
        </div>
      </div>

      <transition name="fade-drop">
        <div v-if="param_bar_visible" class="param-bar">
          <div class="param-item">
            <span class="param-label">{{ t('library.center.docPanel.chunkLabel') }}</span>
            <input
              v-model.number="chunk_input"
              type="number"
              min="0"
              :max="Math.max((doc.chunks || 1) - 1, 0)"
              class="chunk-input"
              :placeholder="t('library.center.docPanel.chunkPlaceholder')"
            />
          </div>

          <button class="param-close" :title="t('library.center.docPanel.hideParams')" @click="hide_params">×</button>
        </div>
      </transition>

      <LibraryContinuousReader
        :library-id="libraryId"
        :doc-id="doc.doc_id"
        :scroll-target="effective_scroll_target"
      />

      <div class="doc-panel-body" v-if="doc_action_result" ref="result_container">
        <div class="doc-panel-toolbar">
          <span class="doc-panel-label">
            {{ doc_action_type_label }}
            <span v-if="last_used_chunk !== null" class="muted">
              ({{ t('library.center.docPanel.chunkUsed', { chunk: last_used_chunk }) }})
            </span>
          </span>

          <div class="doc-panel-toolbar-actions">
            <button class="ghost-btn" @click="return_to_continuous_reading">
              {{ t('library.center.docPanel.returnToReading') }}
            </button>
          </div>
        </div>

        <div class="preview-content" v-html="render_markdown(doc_action_result)"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted, unref } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useMCP } from '../../../composables/useMCP'
import LibraryContinuousReader from './LibraryContinuousReader.vue'

const props = defineProps({
  libraryId: { type: String, required: true },
  doc: { type: Object, required: true },
  scrollTarget: { type: Object, default: null }
})

const { t, locale } = useI18n()
const { callTool } = useMCP()

const actions = computed(() => [
  {
    key: 'outline',
    label: t('library.center.docPanel.actions.outline'),
    loadingText: t('library.center.docPanel.actions.outlineLoading')
  },
  {
    key: 'summary',
    label: t('library.center.docPanel.actions.summary'),
    loadingText: t('library.center.docPanel.actions.summaryLoading')
  },
  {
    key: 'concepts',
    label: t('library.center.docPanel.actions.concepts'),
    loadingText: t('library.center.docPanel.actions.conceptsLoading')
  },
  {
    key: 'recall',
    label: t('library.center.docPanel.actions.recall'),
    loadingText: t('library.center.docPanel.actions.recallLoading')
  }
])

const doc_action_loading = ref(false)
const doc_action_type = ref('')
const doc_action_result = ref('')

const chunk_input = ref(0)
const last_used_chunk = ref(null)
const show_params = ref(false)

const result_container = ref(null)
const reader_continuous = ref(false)
const doc_panel_scroller = ref(null)

const effective_scroll_target = computed(() => {
  return props.scrollTarget || doc_panel_scroller.value || null
})

const param_bar_visible = computed(() => {
  if (show_params.value) return true
  return ['recall'].includes(doc_action_type.value)
})

const show_doc_actions = computed(() => {
  if (doc_action_result.value || doc_action_loading.value) return true
  return !reader_continuous.value
})

const __dompurify_cfg = {
  USE_PROFILES: { html: true },
  ALLOW_UNKNOWN_PROTOCOLS: true
}

function string_value(value) {
  return String(value ?? '').trim()
}

function normalize_locale(value) {
  const raw = string_value(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function current_ui_locale() {
  return normalize_locale(unref(locale) || '')
}

function output_language_name(ui_locale = current_ui_locale()) {
  if (ui_locale === 'zh-CN') return 'Chinese (Simplified)'
  return 'English'
}

function generated_language_payload() {
  const ui_locale = current_ui_locale()
  return {
    ui_locale,
    output_language: output_language_name(ui_locale)
  }
}

function hide_params() {
  show_params.value = false
}

function send_reader_control(action, value = undefined) {
  try {
    window.dispatchEvent(
      new CustomEvent('nisb-library-reader-control', {
        detail: {
          libraryId: props.libraryId,
          docId: props.doc?.doc_id,
          action,
          value
        }
      })
    )
  } catch {}
}

function apply_reader_state_payload(payload) {
  if (!payload || typeof payload !== 'object') return
  if (payload.libraryId && payload.libraryId !== props.libraryId) return
  if (payload.docId && payload.docId !== props.doc?.doc_id) return

  const reader = payload.reader && typeof payload.reader === 'object' ? payload.reader : payload
  if (typeof reader.continuous === 'boolean') {
    reader_continuous.value = !!reader.continuous
  }
}

function sync_reader_state_from_window() {
  try {
    apply_reader_state_payload({
      libraryId: props.libraryId,
      docId: props.doc?.doc_id,
      reader: window.nisbReaderState || {}
    })
  } catch {}
}

function on_reader_state_changed(evt) {
  apply_reader_state_payload(evt?.detail || null)
}

async function return_to_continuous_reading() {
  doc_action_result.value = ''
  doc_action_type.value = ''
  last_used_chunk.value = null
  show_params.value = false

  await nextTick()
  reader_continuous.value = true
  send_reader_control('toggle_continuous', true)
}

function render_markdown(text) {
  if (!text) return ''
  try {
    const html = marked.parse(String(text || ''), {
      breaks: true,
      gfm: true,
      headerIds: true,
      mangle: false
    })
    return DOMPurify.sanitize(html, __dompurify_cfg)
  } catch (e) {
    console.error('[LibraryDocPanel] markdown render failed:', e)
    return `<p>${t('library.center.docPanel.markdownRenderError')}</p>`
  }
}

function add_copy_buttons() {
  const container = result_container.value
  if (!container) return

  const code_blocks = container.querySelectorAll('.preview-content pre code')
  code_blocks.forEach((code_block) => {
    const pre = code_block.parentElement
    if (!pre || pre.querySelector('.copy-btn')) return

    const btn = document.createElement('button')
    btn.className = 'copy-btn'
    btn.textContent = t('library.center.docPanel.copy')
    btn.addEventListener('click', () => {
      const code = code_block.textContent
      navigator.clipboard.writeText(code).then(() => {
        btn.textContent = t('library.center.docPanel.copied')
        setTimeout(() => {
          btn.textContent = t('library.center.docPanel.copy')
        }, 1500)
      })
    })
    pre.style.position = 'relative'
    pre.appendChild(btn)
  })
}

const doc_action_type_label = computed(() => {
  const labels = {
    outline: t('library.center.docPanel.actions.outline'),
    summary: t('library.center.docPanel.actions.summary'),
    concepts: t('library.center.docPanel.actions.concepts'),
    recall: t('library.center.docPanel.actions.recall')
  }
  return labels[doc_action_type.value] || t('library.center.docPanel.result')
})

function reset_state() {
  doc_action_result.value = ''
  doc_action_type.value = ''
  chunk_input.value = 0
  last_used_chunk.value = null
  show_params.value = false
  reader_continuous.value = false
  nextTick(() => sync_reader_state_from_window())
}

async function run_doc_action(action) {
  if (!props.doc) return

  if (reader_continuous.value) {
    reader_continuous.value = false
    send_reader_control('toggle_continuous', false)
    await nextTick()
  }

  if (action === 'recall') {
    show_params.value = true
    await nextTick()
  }

  doc_action_loading.value = true
  doc_action_type.value = action
  doc_action_result.value = ''

  const chunk_id = Number.isInteger(chunk_input.value) && chunk_input.value >= 0 ? chunk_input.value : 0
  last_used_chunk.value = chunk_id

  const common_payload = {
    doc_id: props.doc.doc_id,
    library_id: props.libraryId,
    ...generated_language_payload()
  }

  try {
    let res = null

    if (action === 'outline') {
      res = await callTool('nisb_doc_generate_outline', { ...common_payload, detail_level: 'detailed' })
      doc_action_result.value = res?.text || res?.message || t('library.center.docPanel.emptyResult')
    } else if (action === 'summary') {
      res = await callTool('nisb_doc_generate_summary', { ...common_payload, summary_level: 'medium' })
      doc_action_result.value = res?.text || res?.message || t('library.center.docPanel.emptyResult')
    } else if (action === 'concepts') {
      res = await callTool('nisb_doc_analyze_concepts', { ...common_payload, return_format: 'text' })
      doc_action_result.value = res?.text || res?.message || t('library.center.docPanel.emptyResult')
    } else if (action === 'recall') {
      res = await callTool('nisb_doc_recall', { ...common_payload, chunk_id, window: 10 })
      doc_action_result.value = res?.text || res?.message || t('library.center.docPanel.emptyResult')
    }

    if (!doc_action_result.value) {
      doc_action_result.value = t('library.center.docPanel.noDisplayableResult')
    }

    nextTick(() => add_copy_buttons())
  } catch (e) {
    console.error('[LibraryDocPanel] doc action failed:', e)
    alert(t('library.center.docPanel.actionFailed', { message: e?.message || String(e) }))
  } finally {
    doc_action_loading.value = false
  }
}

watch(
  () => props.doc && props.doc.doc_id,
  () => {
    reset_state()
  }
)

onMounted(() => {
  sync_reader_state_from_window()
  window.addEventListener('nisb-reader-state-changed', on_reader_state_changed)
})

onUnmounted(() => {
  window.removeEventListener('nisb-reader-state-changed', on_reader_state_changed)
})
</script>

<style scoped>
.doc-panel {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  margin-top: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.doc-panel-scroll {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 0.78rem;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.doc-panel-scroll::-webkit-scrollbar {
  width: 8px;
}

.doc-panel-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.doc-panel-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 0.46rem 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 66%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.055);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.doc-panel-actions {
  min-width: 0;
  width: 100%;
  display: flex;
  flex-wrap: nowrap;
  gap: 0.42rem;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.doc-panel-actions::-webkit-scrollbar {
  display: none;
}

.action-pill {
  flex: 0 0 auto;
  min-height: 31px;
  max-width: 100%;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.action-pill:hover:enabled,
.action-pill:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 62%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.action-pill.active {
  border-color: color-mix(in srgb, var(--selected) 50%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
  color: var(--selected);
}

.action-pill:active:enabled {
  transform: translateY(1px);
}

.action-pill:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.param-bar {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.58rem;
  padding: 0.58rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 38%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 38%, transparent),
      color-mix(in srgb, var(--editor-bg) 62%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.param-item {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.44rem;
}

.param-label {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 740;
  line-height: 1.2;
  white-space: nowrap;
}

.chunk-input {
  width: 96px;
  min-width: 72px;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0.42rem 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 11px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.78rem;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.chunk-input:focus {
  border-color: color-mix(in srgb, var(--selected) 50%, var(--line));
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.param-close {
  flex: 0 0 auto;
  margin-left: auto;
  width: 30px;
  height: 30px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 1rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.param-close:hover,
.param-close:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent);
  outline: none;
}

.param-close:active {
  transform: translateY(1px);
}

.doc-panel-body {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
  padding: 0.82rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 14px 30px rgba(0, 0, 0, 0.06);
}

.doc-panel-toolbar {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.68rem;
}

.doc-panel-toolbar-actions {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.48rem;
}

.doc-panel-label {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 800;
  line-height: 1.3;
  overflow-wrap: break-word;
}

.muted {
  color: var(--text-secondary);
  font-weight: 620;
  margin-left: 0.35rem;
}

.ghost-btn {
  flex: 0 0 auto;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
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
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.ghost-btn:hover:enabled,
.ghost-btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.ghost-btn:active:enabled {
  transform: translateY(1px);
}

.ghost-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.preview-content {
  min-width: 0;
  padding: 0.76rem 0.82rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 58%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  line-height: 1.62;
  overflow-wrap: break-word;
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

.preview-content :deep(p) {
  margin: 0.45rem 0;
}

.preview-content :deep(p:first-child) {
  margin-top: 0;
}

.preview-content :deep(p:last-child) {
  margin-bottom: 0;
}

.preview-content :deep(h1),
.preview-content :deep(h2),
.preview-content :deep(h3),
.preview-content :deep(h4) {
  margin: 0.82rem 0 0.38rem;
  color: var(--text-main, var(--text));
  font-weight: 820;
  line-height: 1.28;
}

.preview-content :deep(h1) {
  font-size: 1rem;
}

.preview-content :deep(h2) {
  font-size: 0.94rem;
}

.preview-content :deep(h3),
.preview-content :deep(h4) {
  font-size: 0.88rem;
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
  margin: 0.44rem 0;
  padding-left: 1.15rem;
}

.preview-content :deep(li) {
  margin: 0.22rem 0;
}

.preview-content :deep(blockquote) {
  margin: 0.62rem 0;
  padding: 0.48rem 0.64rem;
  border-left: 3px solid color-mix(in srgb, var(--selected) 48%, var(--line));
  border-radius: 0 12px 12px 0;
  background: color-mix(in srgb, var(--selected-bg) 30%, transparent);
  color: var(--text-secondary);
}

.preview-content :deep(code) {
  padding: 0.08rem 0.28rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 7px;
  background: color-mix(in srgb, var(--sidebar-bg) 70%, transparent);
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.78em;
  overflow-wrap: anywhere;
}

.preview-content :deep(pre) {
  position: relative;
  margin: 0.62rem 0;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 50%, transparent)
    );
  overflow-x: auto;
  scrollbar-width: thin;
}

.preview-content :deep(pre code) {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 0.78rem;
  line-height: 1.55;
  white-space: pre;
}

.preview-content :deep(a) {
  color: var(--selected);
  text-decoration: none;
}

.preview-content :deep(a:hover) {
  text-decoration: underline;
}

.fade-drop-enter-active,
.fade-drop-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.fade-drop-enter-from,
.fade-drop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.fade-drop-enter-to,
.fade-drop-leave-from {
  opacity: 1;
  transform: translateY(0);
}

@media (max-width: 680px) {
  .doc-panel-toolbar {
    align-items: stretch;
    display: grid;
    grid-template-columns: 1fr;
  }

  .doc-panel-toolbar-actions {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr;
  }

  .ghost-btn {
    width: 100%;
  }

  .param-bar {
    align-items: stretch;
    display: grid;
    grid-template-columns: 1fr auto;
  }

  .param-item {
    align-items: stretch;
    display: grid;
    grid-template-columns: 1fr;
  }

  .chunk-input {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .doc-panel-body {
    padding: 0.66rem;
    border-radius: 16px;
  }

  .preview-content {
    padding: 0.66rem;
  }

  .action-pill {
    min-height: 30px;
    padding: 0 0.58rem;
    font-size: 0.72rem;
  }
}
</style>

<style>
.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  min-height: 26px;
  box-sizing: border-box;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 9px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.copy-btn:hover,
.copy-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.copy-btn:active {
  transform: translateY(1px);
}
</style>

