<template>
  <div
    class="library-detail"
    :class="{
      'reader-chrome-compact': reader_chrome_compact
    }"
    ref="root_el"
    @pointerdown.capture="on_reader_chrome_pointer_down"
    @pointermove.capture="on_reader_chrome_pointer_move"
    @pointerup.capture="on_reader_chrome_pointer_up"
    @wheel.capture="on_reader_chrome_scroll_intent"
    @touchmove.capture="on_reader_chrome_scroll_intent"
    @scroll.capture="on_reader_chrome_scroll_intent"
  >
    <LibraryHeader
      :library="library"
      :stats="stats"
      :uploading="uploading"
      :reader_chrome_toggle_available="reader_chrome_toggle_available"
      :reader_chrome_visible="reader_chrome_visible"
      @upload-click="trigger_upload"
      @back-click="go_back"
      @toggle-reader-chrome="toggle_reader_chrome"
    />

    <input
      ref="file_input"
      type="file"
      accept=".txt,.md"
      multiple
      style="display: none"
      @change="handle_file_upload"
    />

    <div v-if="upload_queue.length" class="upload-queue">
      <div class="upload-queue-header">
        <div class="title">{{ labels.uploadQueueTitle }}</div>
        <div class="actions">
          <button class="queue-btn" :disabled="!uploading" @click="cancel_uploads" type="button">
            {{ labels.stop }}
          </button>
          <button class="queue-btn" :disabled="uploading" @click="clear_queue" type="button">
            {{ labels.clear }}
          </button>
        </div>
      </div>

      <div class="upload-items">
        <div v-for="it in upload_queue" :key="it.id" class="upload-item" :class="it.status">
          <div class="name">{{ it.name }}</div>
          <div class="status">
            <span v-if="it.status === 'queued'">{{ labels.statusQueued }}</span>
            <span v-else-if="it.status === 'uploading'">{{ labels.statusUploading }}</span>
            <span v-else-if="it.status === 'success'">{{ labels.statusSuccess }}</span>
            <span v-else>{{ labels.statusFailed }}</span>
            <span class="msg" v-if="it.message"> · {{ it.message }}</span>
          </div>
        </div>
      </div>
    </div>

    <transition name="reader-chrome-fade">
      <div
        v-show="reader_chrome_visible"
        class="library-detail-top-actions"
      >
        <LibraryTopActionBar
          :selected_doc="selected_doc"
          :documents="documents"
          :uploading="uploading"
          :loading_docs="loading_docs"
          :exporting_translated="exporting_translated"
          :doc_list_visible="doc_list_visible"
          :export_button_title="export_button_title"
          @open_export="open_export_translated_modal"
          @toggle_doc_list="toggle_doc_list"
          @open_batch_delete="open_batch_delete"
        />
      </div>
    </transition>

    <LibraryDocumentsList
      v-if="doc_list_visible"
      :documents="documents"
      :loading-docs="loading_docs"
      :selected-doc="selected_doc"
      :format-time="format_time"
      :locale="current_locale"
      :t="t"
      @select-doc="select_doc"
      @show-doc-info="show_doc_info"
      @delete-doc="request_delete_doc"
      @rename-doc="request_rename_doc"
    />

    <div v-else-if="!selected_doc" class="focus-empty">
      <div class="focus-empty-title">{{ labels.focusTitle }}</div>
      <div class="focus-empty-sub">{{ labels.focusSubtitle }}</div>
      <button class="ghost-btn" @click="doc_list_visible = true" type="button">
        {{ labels.openList }}
      </button>
    </div>

    <LibraryDocPanel
      v-if="selected_doc"
      :key="`${libraryId}:${selected_doc?.doc_id || selected_doc?.docid || ''}:${selected_doc_open_token}`"
      :library-id="libraryId"
      :doc="selected_doc"
      :scroll-target="root_el"
    />

    <SpanArtifactsModal
      v-if="selected_doc"
      :open="span_tools_open"
      :library-id="libraryId"
      :doc-id="(selected_doc?.doc_id || selected_doc?.docid || '')"
      :span-index="span_tools_span_index"
      :reader="span_tools_reader"
      @close="close_span_tools"
    />

    <LibraryExportTranslatedModal
      v-if="export_modal_open"
      :library_id="libraryId"
      :library="library"
      :doc="selected_doc"
      :documents="documents"
      :call_tool="callTool"
      :submitting="exporting_translated"
      :initial_scope="export_initial_scope"
      @confirm="confirm_export_translated"
      @cancel="close_export_translated_modal"
    />

    <LibraryBatchDeleteModal
      :open="batch_delete_open"
      :working="batch_delete_working"
      :filter_text="batch_delete_filter"
      :filtered_docs="filtered_docs"
      :selected_map="batch_selected_map"
      :selected_count="selected_batch_count"
      @close="close_batch_delete"
      @confirm="confirm_batch_delete"
      @update:filter_text="batch_delete_filter = $event"
      @select_all_filtered="select_all_filtered"
      @clear_selection="clear_batch_selection"
      @toggle_select="toggle_batch_select"
    />

    <LibraryDeleteConfirmModal
      :open="delete_dialog_open"
      :target_doc="delete_target_doc"
      :working="delete_working"
      :locale="current_locale"
      :t="t"
      @close="cancel_delete_doc"
      @confirm="confirm_delete_doc"
    />

    <LibraryRenameDocModal
      :open="rename_dialog_open"
      :target_doc="rename_target_doc"
      :rename_value="rename_value"
      :working="rename_working"
      :locale="current_locale"
      :t="t"
      @close="cancel_rename_doc"
      @confirm="confirm_rename_doc"
      @update:rename_value="rename_value = $event"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, onActivated, onDeactivated } from 'vue'

import { useMCP } from '../../composables/useMCP'
import { useLatestOnly } from '../../composables/useLatestOnly'
import { useLibrarySearchStore } from '../../stores/librarySearch'
import enLibrary from '../../locales/en/library'
import zhCNLibrary from '../../locales/zh-CN/library'

import {
  use_library_detail_runtime,
  use_library_doc_state,
  use_library_upload_queue,
  use_library_export_translated,
  use_library_doc_navigation,
  use_library_doc_mutations
} from '../../composables/library/index.js'

import LibraryHeader from './Library/LibraryHeader.vue'
import LibraryDocumentsList from './Library/LibraryDocumentsList.vue'
import LibraryDocPanel from './Library/LibraryDocPanel.vue'
import SpanArtifactsModal from './Library/SpanArtifactsModal.vue'
import LibraryExportTranslatedModal from './Library/LibraryExportTranslatedModal.vue'
import LibraryTopActionBar from './Library/LibraryTopActionBar.vue'
import LibraryBatchDeleteModal from './Library/LibraryBatchDeleteModal.vue'
import LibraryDeleteConfirmModal from './Library/LibraryDeleteConfirmModal.vue'
import LibraryRenameDocModal from './Library/LibraryRenameDocModal.vue'

const props = defineProps({
  libraryId: { type: String, required: true },
  selectedDocId: { type: String, default: null }
})

const emit = defineEmits(['back'])
const { callTool } = useMCP()
const library_search = useLibrarySearchStore()
const { begin: begin_load_docs } = useLatestOnly()

const root_el = ref(null)
const library_id_ref = computed(() => props.libraryId)
const selected_doc_id_ref = computed(() => props.selectedDocId)

const LIBRARY_LOCALES = {
  en: enLibrary,
  'zh-CN': zhCNLibrary
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

function local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key)
      if (value !== null && string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function detect_locale() {
  const fromWindow = (() => {
    try {
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

  const fromStorage = local_storage_first(
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
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  return normalize_locale(fromWindow || fromStorage || fromDocument || 'en')
}

const current_locale = computed(() => detect_locale())

function deep_get(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function t(path, params = {}, fallback = '') {
  const messages = LIBRARY_LOCALES[current_locale.value] || LIBRARY_LOCALES.en
  const value = deep_get(messages, path, deep_get(LIBRARY_LOCALES.en, path, fallback))
  return format_text(value || fallback || path, params)
}

const labels = computed(() => ({
  uploadQueueTitle: t('center.detail.uploadQueueTitle', {}, 'Upload queue (sequential)'),
  stop: t('center.detail.stop', {}, 'Stop'),
  clear: t('center.detail.clear', {}, 'Clear'),
  statusQueued: t('center.detail.statusQueued', {}, 'Queued'),
  statusUploading: t('center.detail.statusUploading', {}, 'Uploading…'),
  statusSuccess: t('center.detail.statusSuccess', {}, 'Success'),
  statusFailed: t('center.detail.statusFailed', {}, 'Failed'),
  focusTitle: t('center.detail.focusTitle', {}, 'Focused reading'),
  focusSubtitle: t('center.detail.focusSubtitle', {}, 'Click a book name on the left, or switch back to “List” to choose a document.'),
  openList: t('center.detail.openList', {}, 'Open list')
}))

const {
  library,
  stats,
  documents,
  loading_docs,
  selected_doc,
  selected_doc_open_token,
  doc_list_visible,
  load_library_info,
  load_documents,
  apply_auto_selection,
  toggle_doc_list,
  reset_doc_state,
  reset_library_state,
  select_doc,
  handle_selected_doc_change,
  handle_doc_list_visible_change,
  initialize_mount_state,
  clear_last_open_payload,
  broadcast_doc_meta,
  clear_global_reader_state,
  format_time
} = use_library_doc_state({
  library_id_ref,
  selected_doc_id_ref,
  call_tool: callTool,
  library_search,
  begin_load_docs
})

const {
  ensure_library_id,
  refresh_after_mutation
} = use_library_detail_runtime({
  library_id_ref,
  load_library_info,
  load_documents
})

const {
  file_input,
  upload_queue,
  uploading,
  trigger_upload,
  cancel_uploads,
  clear_queue,
  handle_file_upload,
  reset_upload_state
} = use_library_upload_queue({
  library_id_ref,
  call_tool: callTool,
  refresh_after_mutation
})

const {
  export_modal_open,
  exporting_translated,
  export_initial_scope,
  export_button_title,
  open_export_translated_modal,
  close_export_translated_modal,
  confirm_export_translated
} = use_library_export_translated({
  library_id_ref,
  selected_doc,
  documents,
  doc_list_visible,
  call_tool: callTool,
  ensure_library_id
})

const {
  delete_dialog_open,
  delete_target_doc,
  delete_working,
  rename_dialog_open,
  rename_target_doc,
  rename_value,
  rename_working,
  batch_delete_open,
  batch_delete_working,
  batch_delete_filter,
  batch_selected_map,
  filtered_docs,
  selected_batch_count,
  open_batch_delete,
  close_batch_delete,
  toggle_batch_select,
  select_all_filtered,
  clear_batch_selection,
  confirm_batch_delete,
  request_delete_doc,
  cancel_delete_doc,
  confirm_delete_doc,
  request_rename_doc,
  cancel_rename_doc,
  confirm_rename_doc,
  reset_mutation_state
} = use_library_doc_mutations({
  library_id_ref,
  documents,
  selected_doc,
  library_search,
  call_tool: callTool,
  ensure_library_id,
  refresh_after_mutation,
  reset_doc_state,
  broadcast_doc_meta,
  locale_ref: current_locale,
  t
})

function go_back() {
  reset_doc_state('back_to_overview')
  emit('back')
}

const {
  span_tools_open,
  span_tools_span_index,
  span_tools_reader,
  close_span_tools,
  bind_global_listeners,
  unbind_global_listeners,
  cleanup_navigation
} = use_library_doc_navigation({
  library_id_ref,
  root_el,
  selected_doc,
  documents,
  doc_list_visible,
  library_search,
  broadcast_doc_meta,
  load_documents,
  close_export_translated_modal,
  close_batch_delete,
  cancel_rename_doc,
  cancel_delete_doc,
  reset_doc_state,
  emit_back: () => emit('back')
})

function show_doc_info(doc) {
  alert(
    t('center.detail.docInfoTitle', {}, '📄 Document info') +
      '\n\n' +
      t('center.detail.docInfoId', { value: doc.doc_id }, 'ID: {value}') +
      '\n' +
      t('center.detail.docInfoFilename', { value: doc.filename || t('center.detail.unknown', {}, 'Unknown') }, 'Filename: {value}') +
      '\n' +
      t('center.detail.docInfoType', { value: doc.filetype || 'txt' }, 'Type: {value}') +
      '\n' +
      t('center.detail.docInfoChunks', { value: doc.chunks || 0 }, 'chunks: {value}')
  )
}

onMounted(() => {
  load_library_info()
  load_documents()
  bind_global_listeners()
  initialize_mount_state()
})

onUnmounted(() => {
  unbind_global_listeners()
  cleanup_navigation()
  clear_last_open_payload()
  clear_global_reader_state('unmounted')
})

onActivated(() => {
  bind_global_listeners()
})

onDeactivated(() => {
  unbind_global_listeners()
  cleanup_navigation()
  clear_last_open_payload()
  clear_global_reader_state('deactivated')
})

watch(
  () => props.selectedDocId,
  () => apply_auto_selection()
)

watch(
  () => selected_doc.value,
  (d) => handle_selected_doc_change(d)
)

watch(
  () => doc_list_visible.value,
  (visible) => handle_doc_list_visible_change(visible)
)

watch(
  () => props.libraryId,
  () => {
    begin_load_docs()

    close_export_translated_modal()
    cleanup_navigation()

    reset_doc_state('library_changed')
    reset_library_state()
    reset_upload_state()
    reset_mutation_state()

    load_library_info()
    load_documents()
  }
)

/* Responsive library reader chrome:
   - compact center width: tap reveals, scroll hides
   - wide center width: explicit header toggle
*/
const library_detail_width = ref(0)
const reader_chrome_tap_visible = ref(false)
const reader_chrome_user_hidden = ref(false)
const reader_chrome_search_locked = ref(false)

const READER_CHROME_COMPACT_WIDTH = 560
const READER_CHROME_TOGGLE_WIDTH = 680
const READER_CHROME_TAP_MOVE_LIMIT = 10

let reader_chrome_resize_observer = null
let reader_chrome_auto_hide_timer = null
let reader_chrome_pointer = null

const reader_chrome_compact = computed(() => {
  const w = Number(library_detail_width.value || 0)
  return w > 0 && w <= READER_CHROME_COMPACT_WIDTH
})

const reader_chrome_toggle_available = computed(() => {
  const w = Number(library_detail_width.value || 0)
  return w >= READER_CHROME_TOGGLE_WIDTH && has_reader_selected_doc()
})

const reader_chrome_visible = computed(() => {
  if (reader_chrome_compact.value) return !!reader_chrome_tap_visible.value || !!reader_chrome_search_locked.value
  return !reader_chrome_user_hidden.value
})

const reader_chrome_body_hidden = computed(() => {
  return has_reader_selected_doc() && !reader_chrome_visible.value
})

function has_reader_selected_doc() {
  try {
    const d = selected_doc?.value ?? selected_doc
    return !!(d && (d.doc_id || d.docid || d.id))
  } catch {
    return false
  }
}

function emit_reader_chrome_visibility() {
  try {
    window.dispatchEvent(
      new CustomEvent('nisb-library-reader-chrome-visibility', {
        detail: {
          libraryId: props.libraryId,
          docId: selected_doc?.value?.doc_id || selected_doc?.value?.docid || '',
          visible: !!reader_chrome_visible.value,
          compact: !!reader_chrome_compact.value
        }
      })
    )
  } catch {}
}

function clear_reader_chrome_auto_hide_timer() {
  if (reader_chrome_auto_hide_timer) {
    clearTimeout(reader_chrome_auto_hide_timer)
    reader_chrome_auto_hide_timer = null
  }
}

function schedule_reader_chrome_auto_hide() {
  clear_reader_chrome_auto_hide_timer()
}

function update_library_detail_width() {
  const el = root_el.value
  if (!el || typeof el.getBoundingClientRect !== 'function') return
  const rect = el.getBoundingClientRect()
  const w = Number(rect.width || 0)
  if (Number.isFinite(w) && w > 0) library_detail_width.value = Math.round(w)
}

function toggle_reader_chrome() {
  if (reader_chrome_compact.value) {
    reader_chrome_tap_visible.value = !reader_chrome_tap_visible.value
    if (reader_chrome_tap_visible.value) schedule_reader_chrome_auto_hide()
    return
  }

  reader_chrome_user_hidden.value = !reader_chrome_user_hidden.value
}


function event_path_contains_library_search_panel(evt) {
  try {
    const path = typeof evt?.composedPath === 'function' ? evt.composedPath() : []
    return path.some((node) => node?.classList?.contains?.('library-search-panel'))
  } catch {
    return false
  }
}

function on_reader_chrome_search_lock(evt) {
  const detail = evt?.detail || {}
  const incomingLibraryId = String(detail.libraryId || '').trim()
  const activeLibraryId = String(props.libraryId || '').trim()

  if (incomingLibraryId && activeLibraryId && incomingLibraryId !== activeLibraryId) return

  reader_chrome_search_locked.value = !!detail.locked

  if (reader_chrome_search_locked.value) {
    reader_chrome_tap_visible.value = true
    clear_reader_chrome_auto_hide_timer()
  } else if (reader_chrome_compact.value) {
    reader_chrome_tap_visible.value = false
    clear_reader_chrome_auto_hide_timer()
  }
}

function on_reader_chrome_pointer_down(evt) {
  if (!reader_chrome_compact.value) return
  if (!evt || evt.button > 0) return
  reader_chrome_pointer = {
    x: Number(evt.clientX || 0),
    y: Number(evt.clientY || 0),
    moved: false
  }
}

function on_reader_chrome_pointer_move(evt) {
  if (!reader_chrome_compact.value || !reader_chrome_pointer) return
  const dx = Math.abs(Number(evt.clientX || 0) - reader_chrome_pointer.x)
  const dy = Math.abs(Number(evt.clientY || 0) - reader_chrome_pointer.y)
  if (dx > READER_CHROME_TAP_MOVE_LIMIT || dy > READER_CHROME_TAP_MOVE_LIMIT) {
    reader_chrome_pointer.moved = true
  }
}

function on_reader_chrome_pointer_up(evt) {
  if (!reader_chrome_compact.value || !reader_chrome_pointer) return
  const start = reader_chrome_pointer
  reader_chrome_pointer = null

  const dx = Math.abs(Number(evt?.clientX || 0) - start.x)
  const dy = Math.abs(Number(evt?.clientY || 0) - start.y)
  const is_tap = !start.moved && dx <= READER_CHROME_TAP_MOVE_LIMIT && dy <= READER_CHROME_TAP_MOVE_LIMIT

  if (!is_tap) return

  if (reader_chrome_search_locked.value && !event_path_contains_library_search_panel(evt)) {
    reader_chrome_search_locked.value = false
    reader_chrome_tap_visible.value = false
    clear_reader_chrome_auto_hide_timer()
    return
  }

  reader_chrome_tap_visible.value = true
  schedule_reader_chrome_auto_hide()
}

function on_reader_chrome_scroll_intent() {
  if (!reader_chrome_compact.value) return
  reader_chrome_pointer = null
  if (reader_chrome_search_locked.value) return
  reader_chrome_tap_visible.value = false
  clear_reader_chrome_auto_hide_timer()
}


onMounted(() => {
  update_library_detail_width()

  try {
    if (typeof ResizeObserver !== 'undefined' && root_el.value) {
      reader_chrome_resize_observer = new ResizeObserver(() => update_library_detail_width())
      reader_chrome_resize_observer.observe(root_el.value)
    } else {
      window.addEventListener('resize', update_library_detail_width)
    }
  } catch {
    window.addEventListener('resize', update_library_detail_width)
  }


  window.addEventListener('nisb-library-reader-chrome-search-lock', on_reader_chrome_search_lock)
})

onUnmounted(() => {
  clear_reader_chrome_auto_hide_timer()

  try {
    if (reader_chrome_resize_observer) reader_chrome_resize_observer.disconnect()
  } catch {}

  reader_chrome_resize_observer = null
  window.removeEventListener('resize', update_library_detail_width)
  window.removeEventListener('nisb-library-reader-chrome-search-lock', on_reader_chrome_search_lock)

})

watch(reader_chrome_visible, emit_reader_chrome_visibility, { immediate: true })
watch(() => selected_doc.value, emit_reader_chrome_visibility)
watch(() => props.libraryId, emit_reader_chrome_visibility)

watch(reader_chrome_compact, (compact) => {
  reader_chrome_search_locked.value = false
  if (compact) {
    reader_chrome_tap_visible.value = false
    clear_reader_chrome_auto_hide_timer()
  } else {
    reader_chrome_tap_visible.value = false
  }
})


</script>

<style scoped>
.library-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  gap: 1.15rem;
  overflow-y: auto;
}

.muted {
  color: var(--text-secondary);
  line-height: 1.5;
}

.ghost-btn {
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
  white-space: nowrap;
  height: fit-content;
}

.ghost-btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.focus-empty {
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 1.1rem;
  background: var(--editor-bg);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: flex-start;
}

.focus-empty-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}

.focus-empty-sub {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.upload-queue {
  padding: 0.75rem 0.9rem;
  border-radius: 10px;
  border: 1px dashed var(--line);
  background: var(--editor-bg);
}

.upload-queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.45rem;
}

.upload-queue-header .title {
  font-size: 0.9rem;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 0.4rem;
}

.queue-btn {
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
}

.queue-btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.queue-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.upload-items {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 180px;
  overflow-y: auto;
}

.upload-item {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.3rem 0.5rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.upload-item.uploading {
  background: rgba(120, 120, 120, 0.08);
}

.upload-item.success {
  background: rgba(80, 160, 80, 0.12);
}

.upload-item.error {
  background: rgba(200, 80, 80, 0.12);
}

.name {
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status {
  white-space: nowrap;
  opacity: 0.9;
}

.msg {
  opacity: 0.8;
}

.library-detail-top-actions {
  min-width: 0;
}

.reader-chrome-fade-enter-active,
.reader-chrome-fade-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease,
    max-height 0.16s ease,
    margin 0.16s ease;
  overflow: hidden;
}

.reader-chrome-fade-enter-from,
.reader-chrome-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
  margin-top: 0;
  margin-bottom: 0;
  pointer-events: none;
}


.reader-chrome-compact {
  touch-action: pan-y;
}

</style>

