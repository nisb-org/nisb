<template>
  <div class="editor-wrapper" ref="editorRootRef">
    <div
      class="mode-selector"
      v-if="currentView === 'main'"
      ref="modeSelectorRef"
      @mouseenter="onModeRowEnter"
      @mouseleave="onModeRowLeave"
      @mousemove="onModeMouseMove"
    >
      <EditorToolbar
        :current-view="currentView"
        :current-mode="currentMode"
        :edit-mode="editMode"
        :current-file="currentFile"
        :selected-model="selectedModel"
        :current-conv-id="currentConvId"
        :current-conv-labels="labelsPanelRef?.currentConvLabels || []"
        :left-collapsed="leftCollapsed"
        :right-collapsed="rightCollapsed"
        :is-image-mode="isImageMode"
        :is-code-mode="isCodeMode"
        :save-status="saveStatus"
        :saving="saving"
        :auto-saving="autoSaving"
        :hebbian-processing="hebbianProcessing"
        :hebbian-status="hebbianStatus"
        :hebbian-last-time="hebbianLastTime"
        :can-go-back="canGoBack"
        :can-go-forward="canGoForward"
        :publishing="publishing"
        :library-docked-right="libraryDockedRight"
        :library-sub-mode="librarySubMode"
        @toggle-left-sidebar="toggleLeftSidebar"
        @toggle-right-sidebar="toggleRightSidebar"
        @switch-mode="switchMode"
        @toggle-edit-mode="toggleEditMode"
        @toggle-labels-panel="toggleLabelsPanel"
        @create-new-note="createNewNote"
        @save-note="handleSaveNote"
        @note-to-brain="handleNoteToBrain"
        @go-back-file="handleGoBackFile"
        @go-forward-file="handleGoForwardFile"
        @publish-note="handlePublishNote"
        @toggle-library-dock-right="toggleLibraryDockRight"
        @back-to-overview="backToOverview"
        v-model:selected-model="selectedModel"
      />

      <ConversationLabelsPanel
        v-if="labelsPanelVisible"
        :ref="labelsPanelRef"
        :current-conv-id="currentConvId"
        @close="labelsPanelVisible = false"
      />
    </div>

    <template v-if="currentView === 'main'">
      <template v-if="currentMode === 'note'">
        <template v-if="epubActive">
          <div class="epub-preview-container">
            <div class="epub-wrapper">
              <EpubReader :title="epubName" :epub_array_buffer="epub_array_buffer" />
            </div>
          </div>
        </template>

        <template v-else-if="isPdfMode">
          <div class="pdf-preview-container">
            <div class="pdf-wrapper">
              <iframe
                v-if="pdfObjectUrl"
                class="pdf-iframe"
                :src="pdfObjectUrl"
                :title="t('note.preview.pdfTitle')"
              />
              <div v-else class="empty-tip">{{ t('note.preview.pdfLoading') }}</div>
            </div>
          </div>
        </template>

        <template v-else-if="isImageMode">
          <div class="image-preview-container">
            <div class="image-info">
              <span class="file-name">🖼️ {{ currentFile?.name || t('note.preview.imageDefaultName') }}</span>
              <span class="file-size">{{ formatFileSize(imageMetadata.size) }}</span>
            </div>
            <div class="image-wrapper">
              <img
                :src="`data:${imageMetadata.mime_type};base64,${content}`"
                :alt="currentFile?.name || t('note.preview.imageDefaultName')"
                class="preview-image"
              />
            </div>
          </div>
        </template>

        <template v-else-if="!editMode && useLazyMarkdown">
          <LazyMarkdown
            ref="lazyMdRef"
            :content="content"
            :chunk-size="isFirefox ? 450 : 1000"
            :initial-chunks="isFirefox ? 1 : 2"
            :step-chunks="isFirefox ? 1 : 2"
            :root-margin="isFirefox ? '800px 0px 800px 0px' : '1200px 0px 1200px 0px'"
            :on-open-lightbox="openLightbox"
            @chunkRendered="onLazyChunkRendered"
          />
        </template>

        <template v-else-if="!editMode && useVirtualText">
          <VirtualTextViewer :text="content" :line-height="20" :overscan="120" />
        </template>

        <template v-else-if="!editMode">
          <NotePane
            :content="content"
            :rendered-html="renderedHtml"
            :on-content-change="onContentChange"
            :note-path="currentFile?.path || ''"
            :on-open-lightbox="openLightbox"
            @update:content="(val) => (content = val)"
            @toggle-edit-mode="toggleEditMode"
            @focus-hidden-input="focusHiddenInput"
          />
        </template>

        <template v-else>
          <div class="codemirror-container" ref="editorContainer"></div>

          <div class="editor-stats-bar" v-if="editMode && currentMode === 'note' && !isImageMode && !isPdfMode">
            <div class="stats-left">
              <button class="fold-btn" @click="handleFoldAll" :title="t('note.editor.foldAllTitle')">
                {{ t('note.editor.foldAll') }}
              </button>
              <button class="fold-btn" @click="handleUnfoldAll" :title="t('note.editor.unfoldAllTitle')">
                {{ t('note.editor.unfoldAll') }}
              </button>
              <button class="fold-btn" @click="handleToggleLineNumbers" :title="t('note.editor.toggleLineNumbersTitle')">
                {{ lineNumbersVisible ? t('note.editor.hideLineNumbers') : t('note.editor.showLineNumbers') }}
              </button>
              <button class="fold-btn" @click="handleToggleLineWrapping" :title="t('note.editor.toggleLineWrappingTitle')">
                {{ lineWrappingEnabled ? t('note.editor.disableLineWrapping') : t('note.editor.enableLineWrapping') }}
              </button>
            </div>

            <div class="stats-right">
              <span class="stat-item">{{ editorStats.words }} {{ t('note.editor.stats.words') }}</span>
              <span class="stat-divider">•</span>
              <span class="stat-item">{{ editorStats.chars }} {{ t('note.editor.stats.chars') }}</span>
              <span class="stat-divider">•</span>
              <span class="stat-item">{{ editorStats.lines }} {{ t('note.editor.stats.lines') }}</span>
            </div>
          </div>
        </template>
      </template>

      <template v-else-if="currentMode === 'chat'">
        <ChatPanel
          :key="chat_panel_key"
          :model="selectedModel"
          :conv-id="currentConvId"
          @update-conv-id="handle_chat_conv_id_update"
          @stream-state="handle_chat_stream_state"
          @stream-final="handle_chat_stream_final"
        />
      </template>

      <template v-else-if="currentMode === 'feed'">
        <FeedPanel />
      </template>

      <template v-else-if="currentMode === 'library'">
        <div class="library-mode-wrap">
          <LibraryOverview
            v-if="librarySubMode === 'overview'"
            :library-id="currentLibraryId || ''"
          />

          <template v-else>
            <LibraryDetail
              v-if="currentLibraryId"
              :library-id="currentLibraryId"
              :selected-doc-id="currentLibraryDocId"
              @back="backToOverview"
            />
            <div v-else class="library-empty">
              <div class="title">🗂️ {{ t('library.center.empty.title') }}</div>
              <div class="hint">{{ t('library.center.empty.hint') }}</div>
            </div>
          </template>

          <LibrarySearchPanel />
        </div>
      </template>
    </template>

    <template v-else-if="currentView === 'rss'">
      <RSSReader :initial-feed-id="currentRssFeedId" @back="handleBackFromRss" />
    </template>

    <template v-else-if="currentView === 'rss_gate'">
      <RssGatePanel
        :initial-feed-id="currentRssGateFeedId"
        :default-query="currentRssGateQuery"
        @close="handleBackFromRssGate"
      />
    </template>

    <ImageLightbox v-if="lightboxVisible" :src="lightboxImage" :alt="lightboxAlt" @close="closeLightbox" />
    <SelectionTranslateOverlay />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../composables/useMCP'

import LibraryDetail from './Editor/LibraryDetail.vue'
import LibrarySearchPanel from './Editor/LibrarySearchPanel.vue'
import LibraryOverview from './Editor/Library/LibraryOverview.vue'
import LazyMarkdown from './LazyMarkdown.vue'
import VirtualTextViewer from './Editor/VirtualTextViewer.vue'

import ChatPanel from './Editor/ChatPanel.vue'
import EditorToolbar from './Editor/EditorToolbar.vue'
import ImageLightbox from './Editor/ImageLightbox.vue'
import NotePane from './Editor/NotePane.vue'
import ConversationLabelsPanel from './Editor/ConversationLabelsPanel.vue'

import SelectionTranslateOverlay from './Selection/SelectionTranslateOverlay.vue'
import RSSReader from './Editor/RSS/RSSReader.vue'
import RssGatePanel from './Editor/RSS/RssGatePanel.vue'
import FeedPanel from './Editor/Feed/FeedPanel.vue'

import EpubReader from './Editor/EpubReader.vue'

import { useEditorController } from '../composables/editor/useEditorController'

const { callTool } = useMCP()
const { t } = useI18n({ useScope: 'global' })
const isFirefox = /firefox/i.test(String(navigator.userAgent || ''))
const editorRootRef = ref(null)

const {
  saving,
  hebbianProcessing,
  hebbianStatus,
  hebbianLastTime,

  currentView,
  currentMode,
  editMode,

  currentFile,
  currentDir,
  saveStatus,
  autoSaving,

  leftCollapsed,
  rightCollapsed,

  content,
  renderedHtml,
  useLazyMarkdown,
  useVirtualText,

  isImageMode,
  imageMetadata,
  isCodeMode,
  isPdfMode,
  pdfMetadata,
  pdfObjectUrl,

  lightboxVisible,
  lightboxImage,
  lightboxAlt,

  selectedModel,
  currentConvId,

  labelsPanelVisible,
  labelsPanelRef,

  modeSelectorRef,
  onModeRowEnter,
  onModeRowLeave,
  onModeMouseMove,

  canGoBack,
  canGoForward,

  formatFileSize,
  onContentChange,
  openLightbox,
  closeLightbox,
  focusHiddenInput,

  createNewNote,
  handleSaveNote,
  handleNoteToBrain,

  handleGoBackFile,
  handleGoForwardFile,

  toggleLabelsPanel,
  toggleEditMode,
  toggleLeftSidebar,
  toggleRightSidebar,
  switchMode,

  lazyMdRef,
  onLazyChunkRendered,

  publishing,
  handlePublishNote,

  currentLibraryId,
  currentLibraryDocId,

  currentRssFeedId,
  handleBackFromRss,

  currentRssGateFeedId,
  currentRssGateQuery,
  handleBackFromRssGate,

  editorContainer,

  cmGetEditorStats,
  cmToggleLineNumbers,
  cmToggleLineWrapping,
  cmFoldAll,
  cmUnfoldAll,

  libraryDockedRight,
  toggleLibraryDockRight
} = useEditorController()

const librarySubMode = ref('overview')
const chat_stream_state = ref({
  streaming: false,
  stage: '',
  rag_mode: '',
  mcp_overrides: {},
  mode_used: '',
  request_id: '',
  conv_id: '',
  tool_calls: [],
  tool_results: [],
  citations: [],
  rss_evidence: [],
  market_evidence: [],
  evidence_query: '',
  evidence_tools: [],
  evidence_result: {},
  qa_id: '',
  group_id: ''
})

const chat_panel_key = computed(() => {
  return `chat:${String(selectedModel.value || '')}:${String(currentConvId.value || '')}`
})

function handle_chat_conv_id_update(val) {
  currentConvId.value = val || ''
  if (chat_stream_state.value.conv_id !== currentConvId.value) {
    chat_stream_state.value.conv_id = currentConvId.value
  }
}

function handle_chat_stream_state(payload) {
  const p = payload && typeof payload === 'object' ? payload : {}

  chat_stream_state.value = {
    ...chat_stream_state.value,
    ...p,
  }

  const next_conv_id = String(p.conv_id || '')
  if (next_conv_id) {
    chat_stream_state.value.conv_id = next_conv_id
  }
}

function handle_chat_stream_final(payload) {
  const p = payload && typeof payload === 'object' ? payload : {}

  chat_stream_state.value = {
    ...chat_stream_state.value,
    streaming: false,
    rag_mode: String(p.rag_mode || chat_stream_state.value.rag_mode || ''),
    mcp_overrides:
      p.mcp_overrides && typeof p.mcp_overrides === 'object'
        ? p.mcp_overrides
        : chat_stream_state.value.mcp_overrides || {},
    mode_used: String(p.mode_used || chat_stream_state.value.mode_used || ''),
    request_id: String(p.request_id || chat_stream_state.value.request_id || ''),
    conv_id: String(p.conv_id || chat_stream_state.value.conv_id || ''),
    citations: Array.isArray(p.citations) ? p.citations : [],
    rss_evidence: Array.isArray(p.rss_evidence) ? p.rss_evidence : [],
    market_evidence: Array.isArray(p.market_evidence) ? p.market_evidence : [],
    evidence_query: String(p.evidence_query || ''),
    evidence_tools: Array.isArray(p.evidence_tools) ? p.evidence_tools : [],
    evidence_result:
      p.evidence_result && typeof p.evidence_result === 'object'
        ? p.evidence_result
        : {},
    qa_id: String(p.qa_id || ''),
    group_id: String(p.group_id || ''),
    tool_calls: Array.isArray(p.tool_calls) ? p.tool_calls : chat_stream_state.value.tool_calls,
    tool_results: Array.isArray(p.tool_results) ? p.tool_results : chat_stream_state.value.tool_results,
  }

  if (chat_stream_state.value.conv_id) {
    currentConvId.value = chat_stream_state.value.conv_id
  }
}

function backToOverview() {
  librarySubMode.value = 'overview'
}

function enterDetail() {
  librarySubMode.value = 'detail'
}

watch(
  () => [currentMode.value, currentLibraryId.value, currentLibraryDocId.value],
  ([mode, libId]) => {
    if (mode !== 'library') return
    if (!libId) {
      librarySubMode.value = 'overview'
      return
    }
    librarySubMode.value = 'detail'
  },
  { immediate: true }
)

function onOpenLibraryDocFromOverview(evt) {
  try {
    if (currentMode.value !== 'library') return
    if (libraryDockedRight.value) return
    const d = evt?.detail || {}
    if (!d || !d.libraryId || !d.docId) return
    enterDetail()
  } catch {}
}

const EPUB_PREVIEW_MAX_BYTES = 200 * 1024 * 1024

const epubActive = ref(false)
const epubName = ref('')
const epubSize = ref(0)
const epub_array_buffer = ref(null)

let __epub_seq = 0
let __editor_click_capture_el = null

function _toast(message, type = 'info', duration = 2000) {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type, duration } }))
}

function _set_outline_mode(mode) {
  window.dispatchEvent(new CustomEvent('nisb-outline-mode-changed', { detail: { mode } }))
}

function _get_uid() {
  try {
    const uid = String(localStorage.getItem('nisb_user_id') || '').trim()
    return uid || 'nisb_default_user'
  } catch {
    return 'nisb_default_user'
  }
}

function _normalize_rel_path(p) {
  return String(p || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
}

function _normalize_internal_path(p) {
  return String(p || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\/+/, '')
}

function _dispatch_internal_file(path) {
  const p = _normalize_internal_path(path)
  if (!p) return false
  const name = p.split('/').pop() || p
  window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: p, name } }))
  return true
}

function _dispatch_internal_dir(path) {
  const p = _normalize_internal_path(path)
  if (!p) return false
  const name = p.split('/').pop() || p
  window.dispatchEvent(new CustomEvent('nisb-open-dir', { detail: { path: p, name } }))
  return true
}

function _try_handle_internal_link_href(href) {
  const h = String(href || '').trim()
  if (!/^nisb:\/\/+/i.test(h) && !/^nisb:\/\//i.test(h)) return false

  let u = null
  try {
    u = new URL(h)
  } catch {
    return false
  }

  const host = String(u.host || '').toLowerCase()
  if (host !== 'file') return false

  const type = String(u.searchParams.get('type') || '').toLowerCase()
  const qpPath = _normalize_internal_path(u.searchParams.get('path') || '')

  if (qpPath) {
    if (type === 'directory' || type === 'dir') {
      return _dispatch_internal_dir(qpPath)
    }
    return _dispatch_internal_file(qpPath)
  }

  const pathname = _normalize_internal_path(u.pathname || '')
  if (!pathname) return false

  if (type === 'directory' || type === 'dir') {
    return _dispatch_internal_dir(pathname)
  }
  return _dispatch_internal_file(pathname)
}

function _find_anchor_from_target(target) {
  if (!target) return null
  if (typeof target.closest === 'function') {
    return target.closest('a[href]')
  }
  const el = target.parentElement || null
  if (el && typeof el.closest === 'function') {
    return el.closest('a[href]')
  }
  return null
}

function on_editor_internal_link_click_capture(e) {
  try {
    if (currentView.value !== 'main') return
    if (currentMode.value !== 'note') return

    const anchor = _find_anchor_from_target(e?.target)
    if (!anchor) return

    const href = String(anchor.getAttribute('href') || '').trim()
    if (!/^nisb:\/\//i.test(href)) return

    e.preventDefault()
    e.stopPropagation()
    if (typeof e.stopImmediatePropagation === 'function') {
      e.stopImmediatePropagation()
    }

    const ok = _try_handle_internal_link_href(href)
    if (!ok) {
      _toast(t('note.messages.internalLinkResolveFailed'), 'error', 2500)
    }
  } catch {}
}

function _cleanup_epub_state() {
  epub_array_buffer.value = null
}

async function _yield_main_thread() {
  await new Promise((r) => setTimeout(r, 0))
}

async function _b64_to_u8_chunked(b64, seq) {
  const s = String(b64 || '')
  if (!s) return new Uint8Array(0)

  await _yield_main_thread()
  if (seq !== __epub_seq) return null

  const bin = atob(s)
  const len = bin.length
  const bytes = new Uint8Array(len)

  const CHUNK = 1 << 20
  for (let i = 0; i < len; i += CHUNK) {
    if (seq !== __epub_seq) return null
    const end = Math.min(len, i + CHUNK)
    for (let j = i; j < end; j++) bytes[j] = bin.charCodeAt(j)
    await _yield_main_thread()
  }

  return bytes
}

async function on_open_epub(evt) {
  const seq = ++__epub_seq

  const d = evt?.detail || {}
  const path = String(d.path || '').trim()
  const name = String(d.name || '').trim() || (path ? path.split('/').pop() : '') || 'book.epub'
  if (!path) return

  try {
    if (currentMode.value !== 'note') switchMode('note')
  } catch {}

  try {
    if (editMode.value) editMode.value = false
  } catch {}

  epubActive.value = false
  _cleanup_epub_state()

  epubActive.value = true
  epubName.value = name
  epubSize.value = 0
  epub_array_buffer.value = null

  _set_outline_mode('epub')
  _toast(t('note.messages.epubLoading'), 'info', 1500)

  try {
    const uid = _get_uid()
    const resp = await callTool('nisb_file_read_base64', {
      filename: _normalize_rel_path(path),
      uid,
      max_bytes: EPUB_PREVIEW_MAX_BYTES
    })

    if (seq !== __epub_seq) return

    if (!resp?.success) throw new Error(resp?.message || 'Read failed')

    epubSize.value = Number(resp?.size || 0) || 0

    const u8 = await _b64_to_u8_chunked(resp.data_base64, seq)
    if (seq !== __epub_seq) return
    if (!u8) return

    epub_array_buffer.value = u8
  } catch (e) {
    if (seq !== __epub_seq) return
    epubActive.value = false
    _cleanup_epub_state()
    _set_outline_mode('note')
    _toast(
      t('note.messages.epubOpenFailed', { error: e?.message || String(e) }),
      'error',
      3500
    )
  }
}

function on_open_file_clear_epub(evt) {
  const d = evt?.detail || {}
  const name = String(d.name || '').toLowerCase()
  const path = String(d.path || '').toLowerCase()
  const is_epub = name.endsWith('.epub') || path.endsWith('.epub')
  if (is_epub) return
  if (!epubActive.value) return

  __epub_seq++

  epubActive.value = false
  _cleanup_epub_state()
  _set_outline_mode('note')
}

watch(
  () => [currentView.value, currentMode.value, epubActive.value],
  ([view, mode, active]) => {
    try {
      if (view !== 'main') return
      if (mode !== 'note') return
      _set_outline_mode(active ? 'epub' : 'note')
    } catch {}
  },
  { immediate: true }
)

onMounted(() => {
  window.addEventListener('nisb-open-library-doc', onOpenLibraryDocFromOverview)
  window.addEventListener('nisb-open-epub', on_open_epub)
  window.addEventListener('nisb-open-file', on_open_file_clear_epub)

  __editor_click_capture_el = editorRootRef.value
  if (__editor_click_capture_el) {
    __editor_click_capture_el.addEventListener('click', on_editor_internal_link_click_capture, true)
    __editor_click_capture_el.addEventListener('auxclick', on_editor_internal_link_click_capture, true)
  }
})

onUnmounted(() => {
  window.removeEventListener('nisb-open-library-doc', onOpenLibraryDocFromOverview)
  window.removeEventListener('nisb-open-epub', on_open_epub)
  window.removeEventListener('nisb-open-file', on_open_file_clear_epub)

  if (__editor_click_capture_el) {
    __editor_click_capture_el.removeEventListener('click', on_editor_internal_link_click_capture, true)
    __editor_click_capture_el.removeEventListener('auxclick', on_editor_internal_link_click_capture, true)
    __editor_click_capture_el = null
  }

  __epub_seq++

  epubActive.value = false
  _cleanup_epub_state()
  _set_outline_mode('note')
})

const editorStats = ref({ words: 0, chars: 0, lines: 0 })
const lineNumbersVisible = ref(true)
const lineWrappingEnabled = ref(true)

function updateStats() {
  if (editMode.value && cmGetEditorStats) {
    nextTick(() => {
      try {
        editorStats.value = cmGetEditorStats()
      } catch {
        editorStats.value = { words: 0, chars: 0, lines: 0 }
      }
    })
  }
}

watch(() => content.value, updateStats)
watch(
  () => editMode.value,
  (val) => {
    if (val) setTimeout(updateStats, 100)
  }
)

function handleFoldAll() {
  if (cmFoldAll) cmFoldAll()
}
function handleUnfoldAll() {
  if (cmUnfoldAll) cmUnfoldAll()
}
function handleToggleLineNumbers() {
  if (cmToggleLineNumbers) {
    lineNumbersVisible.value = cmToggleLineNumbers()
  }
}
function handleToggleLineWrapping() {
  if (cmToggleLineWrapping) {
    lineWrappingEnabled.value = cmToggleLineWrapping()
  }
}
</script>

<style scoped>
.editor-wrapper {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 38%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.mode-selector {
  --nisb-editor-bar-height: 44px;

  position: relative;
  z-index: 100;
  flex: 0 0 auto;

  display: flex;
  align-items: center;
  gap: 6px;

  width: 100%;
  min-width: 0;
  height: var(--nisb-editor-bar-height);
  min-height: var(--nisb-editor-bar-height);
  max-height: var(--nisb-editor-bar-height);
  box-sizing: border-box;

  padding: 6px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);

  overflow-x: auto;
  overflow-y: hidden;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.mode-selector::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 20%, var(--line)),
      transparent
    );
  opacity: 0.68;
}

.mode-selector::-webkit-scrollbar {
  display: none;
}

.library-mode-wrap {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
}

.library-empty {
  flex: 1 1 auto;
  overflow: auto;
  padding: 1.25rem 1.5rem;
  color: var(--text-secondary);
}

.library-empty .title {
  font-size: 1rem;
  color: var(--text-main);
  margin-bottom: 0.5rem;
  font-weight: 760;
  line-height: 1.35;
}

.library-empty .hint {
  font-size: 0.9rem;
  opacity: 0.9;
  line-height: 1.5;
}

.image-preview-container,
.pdf-preview-container,
.epub-preview-container {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 36%),
    var(--editor-bg);
  min-width: 0;
  min-height: 0;
}

.image-info {
  position: relative;
  flex: 0 0 auto;

  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;

  min-height: 44px;
  box-sizing: border-box;
  padding: 6px 12px;

  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);

  color: var(--text-secondary);
  font-size: 0.84rem;
}

.image-info::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 16%, var(--line)),
      transparent
    );
  opacity: 0.58;
}

.file-name {
  min-width: 0;
  color: var(--text-main);
  font-weight: 720;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
}

.image-wrapper {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  padding: 2rem;
  min-width: 0;
  min-height: 0;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 16px;
  box-shadow:
    0 18px 44px rgba(0, 0, 0, 0.18),
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
}

.pdf-wrapper,
.epub-wrapper {
  flex: 1 1 auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  margin: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 17px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.11),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: var(--editor-bg);
}

.empty-tip {
  margin: auto;
  max-width: min(34rem, calc(100vw - 2rem));
  box-sizing: border-box;
  padding: 1rem 1.25rem;
  border: 1px dashed color-mix(in srgb, var(--line) 90%, transparent);
  border-radius: 16px;
  color: var(--text-secondary);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08);
  font-size: 0.9rem;
  line-height: 1.5;
}

.codemirror-container {
  flex: 1 1 auto;
  overflow: hidden;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  min-width: 0;
  min-height: 0;
  position: relative;
  margin: 10px 10px 0;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 17px 17px 0 0;
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.10),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.editor-stats-bar {
  position: relative;
  flex: 0 0 auto;
  user-select: none;

  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;

  min-height: 38px;
  box-sizing: border-box;
  padding: 5px 10px;

  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);

  font-size: 12px;
  color: var(--text-secondary);

  overflow-x: auto;
  overflow-y: hidden;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.editor-stats-bar::before {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  top: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 15%, var(--line)),
      transparent
    );
  opacity: 0.58;
}

.editor-stats-bar::-webkit-scrollbar {
  display: none;
}

.stats-left,
.stats-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  min-width: max-content;
}

.fold-btn {
  height: 28px;
  min-width: max-content;
  box-sizing: border-box;
  padding: 0 0.62rem;

  border: 1px solid color-mix(in srgb, var(--line) 90%, transparent);
  border-radius: 9px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );

  color: var(--text-secondary);
  cursor: pointer;

  font-size: 11.5px;
  font-family: inherit;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;

  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;

  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.fold-btn:hover,
.fold-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.fold-btn:active {
  transform: translateY(1px);
}

.stat-item {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.stat-divider {
  opacity: 0.35;
}

@media (max-width: 720px) {
  .mode-selector {
    padding: 6px;
    gap: 5px;
  }

  .image-info {
    padding-inline: 10px;
  }

  .editor-stats-bar {
    padding-inline: 8px;
  }
}
</style>

<style>
.codemirror-container .cm-editor {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  font-family: var(--font-mono);
  font-size: 14px;
  background: var(--editor-bg);
  color: var(--text-main);
  border-radius: 17px 17px 0 0;
}

.codemirror-container .cm-scroller {
  position: absolute;
  inset: 0;
  overflow: auto;
}

.codemirror-container .cm-content,
.codemirror-container .cm-gutter {
  min-height: 100%;
}

.codemirror-container .cm-content {
  padding: 2rem;
  line-height: var(--code-line-height);
  max-width: 100%;
  margin: 0;
}

.layout-container.reading-opt-on .codemirror-container .cm-content {
  padding-left: var(--nisb-read-padding) !important;
  padding-right: var(--nisb-read-padding) !important;
}

.layout-container.reading-opt-on .codemirror-container .cm-editor {
  font-size: var(--nisb-read-font-size) !important;
}

.layout-container.reading-opt-on .codemirror-container .cm-content {
  line-height: var(--nisb-read-line-height) !important;
}

.layout-container.reading-opt-on .codemirror-container .cm-line {
  color: var(--text-main) !important;
}

@supports (color: color-mix(in srgb, #000 50%, transparent)) {
  .layout-container.reading-opt-on .codemirror-container .cm-line {
    color: color-mix(in srgb, var(--text-main) calc(var(--nisb-read-text-opacity) * 100%), transparent) !important;
  }
}

.codemirror-container .cm-gutters {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--line);
  color: var(--text-secondary);
}

.codemirror-container .cm-foldGutter {
  width: 16px;
  padding: 0 2px;
}
.codemirror-container .cm-foldPlaceholder {
  background-color: var(--selected-bg);
  border: 1px solid var(--line);
  color: var(--text-secondary);
  border-radius: 3px;
  padding: 0 4px;
  font-size: 11px;
  cursor: pointer;
}

.display-mode-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-height: 0;
}

.display-mode-container .preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 2.5rem 2.5rem 3rem;
  background: var(--editor-bg);
  color: var(--text-main);
  line-height: var(--text-line-height);
  word-wrap: break-word;
  cursor: text;
  max-width: 100%;
  margin: 0;
  font-size: var(--editor-font-size);
}

.highlight-flash {
  animation: flash 1.5s ease-in-out;
}
@keyframes flash {
  0%,
  100% {
    background: transparent;
  }
  50% {
    background: var(--selected-bg);
  }
}
</style>

