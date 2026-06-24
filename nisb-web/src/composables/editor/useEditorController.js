import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

import { useMCP } from '../useMCP'
import { useSettingsStore } from '../../stores/settings'
import { useNoteOperations } from '../useNoteOperations'
import { useHoverScroll } from '../useHoverScroll'
import { useLatestOnly } from '../useLatestOnly'

import { useLibrarySearchStore } from '../../stores/librarySearch'
import { useChatConfigStore } from '../../stores/chatConfig'
import { useRoomStore } from '../../stores/room'

import { useEditorFileIO } from './modules/useEditorFileIO'
import { useEditorCodeMirror } from './modules/useEditorCodeMirror'
import { useEditorMarkdownPreview } from './modules/useEditorMarkdownPreview'
import { useEditorNavigationEvents } from './modules/useEditorNavigationEvents'
import { useEditorNoteAutosave } from './modules/useEditorNoteAutosave'
import { useEditorPreviewClipboard } from './modules/useEditorPreviewClipboard'
import { useEditorOutlineBridge } from './modules/useEditorOutlineBridge'
import { useEditorScrollSync } from './modules/useEditorScrollSync'

import { countLinesLimited } from './utils/lineCount'
import { isCodeFile, getCodeLanguage, isPdfFile } from './utils/fileKinds'
import { normalizeLibraryReader } from './utils/libraryReader'

import { safe_local_storage_get, safe_local_storage_set, safe_local_storage_remove } from '../../utils/storage_safe'
import enRoot from '../../locales/en.js'
import zhCNRoot from '../../locales/zh-CN.js'

const EDITOR_CONTROLLER_LOCALES = {
  en: enRoot,
  'zh-CN': zhCNRoot
}

function _string_value(value) {
  return String(value ?? '').trim()
}

function _normalize_locale(value) {
  const raw = _string_value(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function _local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key)
      if (value !== null && _string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function _current_locale() {
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

  const fromStorage = _local_storage_first(
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

  return _normalize_locale(fromWindow || fromStorage || fromDocument || 'en')
}

function _deep_get(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function _format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function _t(path, params = {}, fallback = '') {
  const messages = EDITOR_CONTROLLER_LOCALES[_current_locale()] || EDITOR_CONTROLLER_LOCALES.en
  const value = _deep_get(messages, path, _deep_get(EDITOR_CONTROLLER_LOCALES.en, path, fallback))
  return _format_text(value || fallback || path, params)
}

function _toast(message, type = 'info') {
  try {
    window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
  } catch {}
}

export function useEditorController() {
  const chatCfg = useChatConfigStore()
  const roomStore = useRoomStore()
  const { callTool } = useMCP()
  useSettingsStore()

  const librarySearch = useLibrarySearchStore()

  const {
    saving,
    hebbianProcessing,
    hebbianStatus,
    hebbianLastTime,
    saveNote: saveNoteOp,
    noteToBrain: noteToBrainOp,
    resetHebbianStatus
  } = useNoteOperations()

  const currentView = ref('main')
  const currentMode = ref('note')
  const editMode = ref(false)

  const currentLibraryId = ref(null)
  const currentLibraryDocId = ref(null)

  const libraryDockedRight = ref(false)

  function _setDockedRight(next) {
    const v = !!next
    libraryDockedRight.value = v
    try {
      window.__nisbLibraryDockState = { docked: v, side: 'right', ts: Date.now() }
    } catch {}
    try {
      window.dispatchEvent(new CustomEvent('nisb-library-dock', { detail: { docked: v, side: 'right' } }))
    } catch {}
  }

  function _set_library_search_context_from_user_click({ lib, doc } = {}) {
    const libraryId = String(lib || '').trim()
    const docId = String(doc || '').trim()
    if (!libraryId) return

    try {
      if (typeof librarySearch.set_context_from_user_click === 'function') {
        librarySearch.set_context_from_user_click({ libraryId, docId, preserveResults: true })
        return
      }
    } catch {}

    try {
      if (typeof librarySearch.setContext === 'function') {
        librarySearch.setContext({ libraryId, docId, preserveResults: true, source: 'user_click' })
      }
    } catch {}
  }

  function _set_library_search_context_from_editor({ lib, doc } = {}) {
    const libraryId = String(lib || '').trim()
    const docId = String(doc || '').trim()
    if (!libraryId) return

    try {
      if (typeof librarySearch.setContext === 'function') {
        librarySearch.setContext({ libraryId, docId, preserveResults: true, source: 'editor' })
      }
    } catch {}
  }

  function toggleLibraryDockRight(force = null) {
    const next = typeof force === 'boolean' ? force : !libraryDockedRight.value
    _setDockedRight(next)

    try {
      const lib = currentLibraryId.value
      const doc = currentLibraryDocId.value
      if (lib) _set_library_search_context_from_editor({ lib, doc })
    } catch {}

    if (next) {
      if (rightCollapsed.value) {
        window.dispatchEvent(new CustomEvent('toggle-right-sidebar'))
      }

      switchMode('chat')
      _toast(
        _t(
          'editorController.libraryDockedToast',
          {},
          '📚 Library docked to the right sidebar: read on the right / chat in the center'
        ),
        'success'
      )
    } else {
      switchMode('library')
      _toast(_t('editorController.libraryRestoredToast', {}, '↩ Restored: library is back in the center'), 'success')
    }
  }

  function _onDockToggleRequest(e) {
    const d = e?.detail || {}
    if (d && Object.prototype.hasOwnProperty.call(d, 'docked')) toggleLibraryDockRight(!!d.docked)
    else toggleLibraryDockRight()
  }

  let __suppressLibraryAutoSwitchUntil = 0
  let __modeBeforeAutoSwitch = null

  function markSuppressLibraryAutoSwitch(ms = 900) {
    __suppressLibraryAutoSwitchUntil = Date.now() + Number(ms || 0)
  }

  function shouldSuppressLibraryAutoSwitch() {
    return Date.now() < __suppressLibraryAutoSwitchUntil
  }

  function _normalizeOpenDocPayload(d) {
    const p = d && typeof d === 'object' ? d : {}

    const lib = String(p.libraryId || p.library_id || '').trim()
    const doc = String(p.docId || p.doc_id || '').trim()

    const spanRaw =
      p.spanIndex ??
      p.span_index ??
      p.spanId ??
      p.span_id ??
      (p.span && typeof p.span === 'object' ? p.span.index : null) ??
      (p.extra && typeof p.extra === 'object' && p.extra.span && typeof p.extra.span === 'object'
        ? p.extra.span.index
        : null) ??
      null

    const spanIndex = spanRaw === null || spanRaw === undefined ? null : Number(spanRaw)
    const safeSpanIndex = Number.isFinite(spanIndex) ? spanIndex : null

    const reader = p.reader ?? window.__nisbReaderState ?? window.nisbReaderState ?? null

    return {
      ...p,
      libraryId: lib || p.libraryId || '',
      docId: doc || p.docId || '',
      spanIndex: safeSpanIndex,
      reader
    }
  }

  function onOpenLibraryDocCapture(e) {
    const d = e?.detail || null
    if (!d) return
    if (!libraryDockedRight.value) return

    __modeBeforeAutoSwitch = currentMode.value || 'chat'
    markSuppressLibraryAutoSwitch(1500)

    const payload = _normalizeOpenDocPayload(d)
    const lib = String(payload.libraryId || '').trim()
    const doc = String(payload.docId || '').trim()
    if (!lib || !doc) return

    try {
      if (rightCollapsed.value) window.dispatchEvent(new CustomEvent('toggle-right-sidebar'))
    } catch {}

    try {
      currentLibraryId.value = lib
      currentLibraryDocId.value = doc
    } catch {}

    _set_library_search_context_from_user_click({ lib, doc })

    try {
      window.__nisb_last_library_doc_open = payload
    } catch {}

    try {
      window.dispatchEvent(
        new CustomEvent('nisb-library-reader-control', {
          detail: { libraryId: lib, docId: doc, action: 'toggle_continuous', value: true }
        })
      )
    } catch {}

    const fireApply = () => {
      try {
        window.dispatchEvent(new CustomEvent('nisb-apply-library-doc-state', { detail: payload }))
      } catch {}
    }
    setTimeout(fireApply, 0)
    setTimeout(fireApply, 180)
  }

  const currentRssFeedId = ref('')
  const currentRssGateFeedId = ref('')
  const currentRssGateQuery = ref('')

  const modeSelectorRef = ref(null)
  const { onRowEnter: onModeRowEnter, onRowLeave: onModeRowLeave, onScroll: onModeScroll, onMouseMove: onModeMouseMove } =
    useHoverScroll(modeSelectorRef, {
      activeHeight: 10,
      ignorePredicate: (e) => {
        const t = e?.target
        if (!t || typeof t.closest !== 'function') return false
        return !!t.closest('.note-hover-actions') || !!t.closest('.library-hover-actions')
      }
    })

  const content = ref('')
  const leftCollapsed = ref(false)
  const rightCollapsed = ref(false)
  const editorContainer = ref(null)

  const currentFile = ref(null)
  const currentDir = ref('')

  const fileHistory = ref([])
  const forwardHistory = ref([])

  const isImageMode = ref(false)
  const imageMetadata = ref({})

  const isCodeMode = ref(false)

  const isPdfMode = ref(false)
  const pdfMetadata = ref({})
  const pdfObjectUrl = ref('')

  const autoSaving = ref(false)
  const saveStatus = ref('saved')

  const lastSavedComparable = ref('')
  const lastSavedFilePath = ref('')
  const lastLoadedBaselinePath = ref('')

  const fileLoading = ref(false)
  const loadedFilePath = ref('')
  const loadedLineCount = ref(0)

  const EDITOR_CACHE_MAX_BYTES = 512 * 1024

  const MARKDOWN_LAZY_LINES = 3000
  const NON_MARKDOWN_VIRTUAL_LINES = 1000

  const isMarkdownFile = computed(() => /\.md$/i.test(String(currentFile.value?.name || '')))
  const useLazyMarkdown = computed(() => isMarkdownFile.value && loadedLineCount.value >= MARKDOWN_LAZY_LINES)
  const useVirtualText = computed(() => !isMarkdownFile.value && loadedLineCount.value >= NON_MARKDOWN_VIRTUAL_LINES)
  const lazyMdRef = ref(null)

  const selectedModel = ref('gpt-4o-mini')
  const currentConvId = ref(null)

  const labelsPanelVisible = ref(false)
  const labelsPanelRef = ref(null)

  const canGoBack = computed(() => fileHistory.value.length > 0)
  const canGoForward = computed(() => forwardHistory.value.length > 0)

  const publishing = ref(false)

  const { begin: beginDocOpen } = useLatestOnly()

  function revokePdfUrlIfAny() {
    try {
      if (pdfObjectUrl.value) URL.revokeObjectURL(pdfObjectUrl.value)
    } catch {}
    pdfObjectUrl.value = ''
  }

  function base64ToUint8Array(b64) {
    const binary = atob(b64)
    const len = binary.length
    const bytes = new Uint8Array(len)
    for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i)
    return bytes
  }

  function formatFileSize(bytes) {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    let size = bytes
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    return `${size.toFixed(2)} ${units[unitIndex]}`
  }

  let fileIOApi = null
  let codeMirrorApi = null

  function _normalizeComparableText(text) {
    return String(text ?? '').replace(/\r\n?/g, '\n')
  }

  function _getCurrentFilePath() {
    return String(currentFile.value?.path || '').trim()
  }

  function _hasPersistedCurrentFile() {
    return !!_getCurrentFilePath()
  }

  function _hasBaselineForCurrentFile() {
    const p = _getCurrentFilePath()
    return !!p && p === lastSavedFilePath.value
  }

  function _getCurrentTextSnapshot({ preferEditor = editMode.value } = {}) {
    if (preferEditor) {
      const s = codeMirrorApi?.getEditorDocString?.()
      if (typeof s === 'string') return s
    }
    return String(content.value || '')
  }

  function _captureSavedBaseline(text = null, opts = {}) {
    const filePath = String(opts.filePath || _getCurrentFilePath()).trim()
    const sourceText = text === null || text === undefined ? _getCurrentTextSnapshot({ preferEditor: !!opts.preferEditor }) : text

    lastSavedComparable.value = _normalizeComparableText(sourceText)
    lastSavedFilePath.value = filePath
    if (filePath) lastLoadedBaselinePath.value = filePath

    if (opts.markStatusSaved !== false && filePath) {
      saveStatus.value = 'saved'
    }
  }

  function _isCurrentPersistedNoteDirty(text = null) {
    if (!_hasPersistedCurrentFile()) return true
    if (!_hasBaselineForCurrentFile()) return false
    const next = _normalizeComparableText(text === null || text === undefined ? _getCurrentTextSnapshot({ preferEditor: true }) : text)
    return next !== lastSavedComparable.value
  }

  function _syncSaveStatusFromBaseline({ preferEditor = editMode.value, keepExistingWhenNoBaseline = true } = {}) {
    if (!_hasPersistedCurrentFile()) {
      saveStatus.value = 'unsaved'
      return true
    }

    if (!_hasBaselineForCurrentFile()) {
      if (!keepExistingWhenNoBaseline) saveStatus.value = 'saved'
      return false
    }

    const currentText = _normalizeComparableText(_getCurrentTextSnapshot({ preferEditor }))
    const dirty = currentText !== lastSavedComparable.value
    saveStatus.value = dirty ? 'unsaved' : 'saved'
    return dirty
  }

  function _clearPendingAutoSaveIfAny() {
    try {
      fileIOApi?.clearAutoSaveTimer?.()
    } catch {}
  }

  function _handleTrackedContentChange({ preferEditor = editMode.value } = {}) {
    if (!_hasPersistedCurrentFile()) {
      fileIOApi?.onContentChange?.()
      return
    }

    if (!_hasBaselineForCurrentFile()) {
      saveStatus.value = 'saved'
      _clearPendingAutoSaveIfAny()
      return
    }

    const dirty = _syncSaveStatusFromBaseline({ preferEditor, keepExistingWhenNoBaseline: true })
    if (!dirty) {
      _clearPendingAutoSaveIfAny()
      return
    }

    fileIOApi?.onContentChange?.()
  }

  function _pseudoEditorViewForSave() {
    const get = () => String(codeMirrorApi?.getEditorDocString?.() || content.value || '')
    return {
      state: {
        doc: {
          toString: get,
          get length() {
            return get().length
          }
        }
      },
      dispatch() {}
    }
  }

  async function _performInternalNoteSave(reason = 'manual') {
    const ev = editMode.value ? _pseudoEditorViewForSave() : null
    return await saveNoteOp(
      currentFile.value,
      content.value,
      editMode.value,
      ev,
      isCodeMode.value,
      currentDir.value,
      { reason }
    )
  }

  const noteAutosaveApi = useEditorNoteAutosave({
    content,
    loadedLineCount,
    saveStatus,
    autoSaving,
    currentFile,
    countLinesLimited,
    getFileIOApi: () => fileIOApi,
    getCodeMirrorApi: () => codeMirrorApi,
    performAutoSave: ({ reason = 'autosave' } = {}) => _performInternalNoteSave(reason)
  })

  function guardedDebouncedAutoSave(...args) {
    if (!_hasPersistedCurrentFile()) return
    if (!_hasBaselineForCurrentFile()) return

    const dirty = _syncSaveStatusFromBaseline({ preferEditor: true, keepExistingWhenNoBaseline: true })
    if (!dirty) {
      _clearPendingAutoSaveIfAny()
      return
    }

    noteAutosaveApi.debouncedAutoSave(...args)
  }

  codeMirrorApi = useEditorCodeMirror({
    callTool,

    editorContainer,
    content,
    loadedLineCount,
    editMode,
    currentFile,

    isImageMode,
    isCodeMode,
    isPdfMode,
    isMarkdownFile,

    isCurrentFileLoadedSafe: () => (fileIOApi ? fileIOApi.isCurrentFileLoadedSafe() : true),
    debouncedAutoSave: guardedDebouncedAutoSave,
    onContentChange: () => _handleTrackedContentChange({ preferEditor: true })
  })

  fileIOApi = useEditorFileIO({
    callTool,

    currentFile,
    content,
    loadedLineCount,
    fileLoading,
    loadedFilePath,
    saveStatus,
    autoSaving,

    isImageMode,
    imageMetadata,
    isCodeMode,
    isPdfMode,
    pdfMetadata,
    pdfObjectUrl,
    editMode,

    isCodeFile,
    getCodeLanguage,
    isPdfFile,
    base64ToUint8Array,
    revokePdfUrlIfAny,
    isMarkdownFile,
    useLazyMarkdown,

    debouncedAutoSave: guardedDebouncedAutoSave,

    forceExitEditMode: codeMirrorApi.forceExitEditMode,
    syncFromContent: codeMirrorApi.syncFromContent
  })

  const previewApi = useEditorMarkdownPreview({
    callTool,
    content,
    isImageMode,
    isCodeMode,
    isPdfMode,
    useLazyMarkdown,
    useVirtualText
  })

  const {
    renderedHtml,
    scheduleLoadMarkdownImages,
    onLazyChunkRendered,
    lightboxVisible,
    lightboxImage,
    lightboxAlt,
    openLightbox,
    closeLightbox,
    handleOpenLightboxEvent
  } = previewApi

  const previewClipboardApi = useEditorPreviewClipboard({
    callTool,
    currentView,
    currentMode,
    editMode,
    isImageMode,
    isCodeMode,
    isPdfMode,
    currentFile,
    content,
    getFileIOApi: () => fileIOApi,
    applyExternalNoteContent: noteAutosaveApi.applyExternalNoteContent
  })

  const { handlePasteWebClip } = previewClipboardApi

  const outlineBridgeApi = useEditorOutlineBridge({
    currentMode,
    currentFile,
    loadedLineCount,
    useLazyMarkdown,
    isMarkdownFile,
    isImageMode,
    isPdfMode,
    isCodeMode,
    content,
    lazyMdRef
  })

  const scrollSyncApi = useEditorScrollSync({
    currentMode,
    editMode,
    currentFile,
    isImageMode,
    isPdfMode,
    isMarkdownFile,
    editorContainer,
    codeMirrorApi
  })

  watch(
    () => String(currentFile.value?.path || '').trim(),
    (p) => {
      try {
        safe_local_storage_set('nisb_outline_file_path', p || '', { max_bytes: 16 * 1024 })
      } catch {}
    },
    { immediate: true }
  )

  watch(
    () => String(currentFile.value?.path || '').trim(),
    (path, oldPath) => {
      if (!path) {
        lastSavedComparable.value = ''
        lastSavedFilePath.value = ''
        lastLoadedBaselinePath.value = ''
        return
      }

      if (path !== oldPath && path !== lastSavedFilePath.value) {
        lastLoadedBaselinePath.value = ''
      }
    },
    { immediate: true }
  )

  watch(
    () => [fileLoading.value, String(currentFile.value?.path || '').trim(), String(loadedFilePath.value || '').trim()],
    ([loading, currentPath, loadedPath]) => {
      if (loading) return

      const filePath = currentPath || loadedPath
      if (!filePath) return
      if (currentPath && loadedPath && currentPath !== loadedPath) return
      if (filePath === lastLoadedBaselinePath.value && filePath === lastSavedFilePath.value) return

      _captureSavedBaseline(String(content.value || ''), { filePath, markStatusSaved: true })
    }
  )

  watch(
    () => currentMode.value,
    (m) => {
      if (!libraryDockedRight.value) return
      if (!shouldSuppressLibraryAutoSwitch()) return
      if (m !== 'library') return

      const backTo = __modeBeforeAutoSwitch || 'chat'
      if (backTo === 'library') return

      currentView.value = 'main'
      currentMode.value = backTo
    }
  )

  watch(
    () => [
      currentMode.value,
      String(currentFile.value?.path || ''),
      loadedLineCount.value,
      useLazyMarkdown.value,
      isMarkdownFile.value,
      isImageMode.value,
      isPdfMode.value,
      isCodeMode.value
    ],
    () => {
      outlineBridgeApi.emitOutlineContext()
    },
    { immediate: true }
  )

  watch(
    () => currentMode.value,
    (m) => outlineBridgeApi.emitOutlineMode(m),
    { immediate: true }
  )

  function _switchModeCore(mode) {
    currentView.value = 'main'

    if (currentMode.value === 'note' && editMode.value) {
      const s = codeMirrorApi.getEditorDocString?.()
      if (typeof s === 'string') {
        content.value = s
        loadedLineCount.value = countLinesLimited(content.value || '')
        _handleTrackedContentChange({ preferEditor: false })
      }
      codeMirrorApi.forceExitEditMode()
    }

    currentMode.value = mode
  }

  const navApi = useEditorNavigationEvents({
    currentView,
    currentMode,
    editMode,
    currentFile,
    currentDir,
    saveStatus,
    saving,
    autoSaving,
    content,
    loadedLineCount,
    leftCollapsed,
    rightCollapsed,

    fileHistory,
    forwardHistory,

    lazyMdRef,
    useLazyMarkdown,

    canGoBack,
    canGoForward,

    currentConvId,
    currentLibraryId,
    currentLibraryDocId,
    currentRssFeedId,

    currentRssGateFeedId,
    currentRssGateQuery,

    startLoadFile: fileIOApi.startLoadFile,
    clearAutoSaveTimer: fileIOApi.clearAutoSaveTimer,
    revokePdfUrlIfAny,
    abortFileLoading: fileIOApi.abortFileLoading,

    switchMode: _switchModeCore,
    toggleEditMode: scrollSyncApi.toggleEditMode,
    emitOutlineMode: outlineBridgeApi.emitOutlineMode,

    beginDocOpen,
    normalizeLibraryReader,

    chatCfg,
    librarySearch,
    roomStore,
    callTool,

    saveCurrentNote: handleSaveNote,
    isCurrentNoteDirty: () => {
      if (_hasPersistedCurrentFile()) {
        return _isCurrentPersistedNoteDirty(_getCurrentTextSnapshot({ preferEditor: true }))
      }
      return saveStatus.value === 'unsaved'
    }
  })

  function onContentChange() {
    _handleTrackedContentChange({ preferEditor: editMode.value })
  }

  function toggleEditMode() {
    if (!editMode.value) {
      _syncSaveStatusFromBaseline({ preferEditor: false, keepExistingWhenNoBaseline: true })
      _clearPendingAutoSaveIfAny()
    } else {
      const s = codeMirrorApi.getEditorDocString?.()
      if (typeof s === 'string') {
        content.value = s
        loadedLineCount.value = countLinesLimited(content.value || '')
      }
      _handleTrackedContentChange({ preferEditor: true })
    }

    scrollSyncApi.toggleEditMode()
  }

  function focusHiddenInput() {
    const textarea = document.querySelector('.hidden-textarea')
    if (textarea) textarea.focus()
  }

  function toggleLeftSidebar() {
    window.dispatchEvent(new CustomEvent('toggle-left-sidebar'))
  }

  function toggleRightSidebar() {
    window.dispatchEvent(new CustomEvent('toggle-right-sidebar'))
  }

  function _modeLabel(mode) {
    if (mode === 'chat') return _t('editorController.modeLabels.chat', {}, 'Chat')
    if (mode === 'feed') return _t('editorController.modeLabels.feed', {}, 'Feed')
    if (mode === 'library') return _t('editorController.modeLabels.library', {}, 'Library')
    if (mode === 'note') return _t('editorController.modeLabels.note', {}, 'Notes')
    return _t('editorController.modeLabels.other', {}, 'Other content')
  }

  async function switchMode(mode) {
    currentView.value = 'main'

    if (mode !== 'note') {
      const ok = await navApi.guardBeforeLeaveCurrentNote({ targetLabel: _modeLabel(mode) })
      if (!ok) return false
    }

    _switchModeCore(mode)
    return true
  }

  async function createNewNote() {
    const hasUnsaved = currentFile.value && saveStatus.value === 'unsaved'
    if (hasUnsaved) {
      const ok = confirm(
        _t(
          'editorController.unsavedLeaveConfirm',
          {},
          'The current note has unsaved changes. Continuing will discard those changes. Continue?'
        )
      )
      if (!ok) return
    }

    fileIOApi.abortFileLoading()
    revokePdfUrlIfAny()
    _clearPendingAutoSaveIfAny()

    fileLoading.value = false
    loadedFilePath.value = ''
    loadedLineCount.value = 0

    currentFile.value = null
    saveStatus.value = 'unsaved'
    isPdfMode.value = false
    isImageMode.value = false
    isCodeMode.value = false

    lastSavedComparable.value = ''
    lastSavedFilePath.value = ''
    lastLoadedBaselinePath.value = ''

    content.value = ''
    loadedLineCount.value = countLinesLimited(content.value)

    safe_local_storage_remove('nisb_editor_content')
    safe_local_storage_remove('nisb_outline_file_path')

    currentView.value = 'main'
    currentMode.value = 'note'

    if (editMode.value) {
      codeMirrorApi.syncFromContent(content.value)
    } else {
      toggleEditMode()
    }
  }

  async function handleSaveNote(opts = {}) {
    const reason = String(opts?.reason || 'manual').trim() || 'manual'
    const snapshot = _getCurrentTextSnapshot({ preferEditor: true })
    const canSkipWrite = _hasPersistedCurrentFile() && _hasBaselineForCurrentFile() && !_isCurrentPersistedNoteDirty(snapshot)

    if (canSkipWrite) {
      _clearPendingAutoSaveIfAny()
      _captureSavedBaseline(snapshot, { filePath: _getCurrentFilePath(), markStatusSaved: true })
      return { success: true, status: 'saved', skipped: true }
    }

    const result = await _performInternalNoteSave(reason)

    if (result.success) {
      if (result.file) currentFile.value = result.file
      _captureSavedBaseline(snapshot, {
        filePath: String(result.file?.path || _getCurrentFilePath()).trim(),
        markStatusSaved: true
      })
      saveStatus.value = result.status || 'saved'
    } else {
      saveStatus.value = result.status || 'unsaved'
    }

    return result
  }

  async function handleNoteToBrain() {
    await noteToBrainOp(currentFile.value)
  }

  function toggleLabelsPanel() {
    if (!currentConvId.value) {
      _toast(_t('editorController.selectConversationFirst', {}, 'Please select a conversation history item on the left first'), 'info')
      return
    }
    labelsPanelVisible.value = !labelsPanelVisible.value
  }

  async function handlePublishNote() {
    if (publishing.value) return

    if (!currentFile.value || !currentFile.value.path) {
      _toast(_t('editorController.publishNoFile', {}, 'No file to publish.'), 'error')
      return
    }

    if (!isMarkdownFile.value) {
      _toast(_t('editorController.publishMarkdownOnly', {}, 'Only Markdown notes can be published.'), 'error')
      return
    }

    let md = content.value || ''
    const s = codeMirrorApi.getEditorDocString?.()
    if (editMode.value && typeof s === 'string') md = s

    if (!String(md || '').trim()) {
      _toast(_t('editorController.publishEmptyContent', {}, 'Empty content.'), 'error')
      return
    }

    publishing.value = true
    try {
      try {
        const beforePublishText = _getCurrentTextSnapshot({ preferEditor: true })
        const canSkipWrite = _hasPersistedCurrentFile() && _hasBaselineForCurrentFile() && !_isCurrentPersistedNoteDirty(beforePublishText)

        if (canSkipWrite) {
          _clearPendingAutoSaveIfAny()
          _captureSavedBaseline(beforePublishText, { filePath: _getCurrentFilePath(), markStatusSaved: true })
        } else {
          const r = await _performInternalNoteSave('publish_sync')
          if (r && r.success) {
            if (r.file) currentFile.value = r.file
            _captureSavedBaseline(beforePublishText, {
              filePath: String(r.file?.path || _getCurrentFilePath()).trim(),
              markStatusSaved: true
            })
            saveStatus.value = 'saved'
          } else {
            saveStatus.value = r?.status || 'unsaved'
          }
        }
      } catch {
        _toast(_t('editorController.publishSaveFailedContinue', {}, 'Save failed, still publishing…'), 'error')
      }

      const title = String(currentFile.value.name || '').replace(/\.md$/i, '') || _t('editorController.untitled', {}, 'Untitled')
      const res = await callTool('nisb_feed_publish', {
        note_path: currentFile.value.path,
        title,
        content_md: md,
        locale: _current_locale()
      })

      if (!res || res.success === false) throw new Error(res?.message || _t('editorController.publishFailed', {}, 'Publish failed.'))

      _toast(_t('editorController.publishSuccess', {}, 'Published to Feed.'), 'success')
      window.dispatchEvent(new CustomEvent('nisb-feed-refresh'))
      await switchMode('feed')
    } catch (e) {
      _toast(e?.message || _t('editorController.publishFailed', {}, 'Publish failed.'), 'error')
    } finally {
      publishing.value = false
    }
  }

  async function handleGoBackFile() {
    return await navApi.handleGoBackFile()
  }

  async function handleGoForwardFile() {
    return await navApi.handleGoForwardFile()
  }

  function handleBackFromLibrary() {
    navApi.handleBackFromLibrary()
  }

  function handleBackFromRss() {
    navApi.handleBackFromRss()
  }

  function handleBackFromRssGate() {
    navApi.handleBackFromRssGate()
  }

  function cmGetEditorStats() {
    return codeMirrorApi.getEditorStats()
  }

  function cmToggleLineNumbers() {
    return codeMirrorApi.toggleLineNumbers()
  }

  function cmToggleLineWrapping() {
    return codeMirrorApi.toggleLineWrapping()
  }

  function cmFoldAll() {
    codeMirrorApi.foldAllBlocks()
  }

  function cmUnfoldAll() {
    codeMirrorApi.unfoldAllBlocks()
  }

  watch(
    () => content.value,
    () => {
      if (useLazyMarkdown.value || useVirtualText.value) return
      if (editMode.value) return
      if (isImageMode.value || isPdfMode.value) return
      if (isMarkdownFile.value) scheduleLoadMarkdownImages()
    }
  )

  watch(
    () => editMode.value,
    (isEdit) => {
      if (!isEdit) {
        if (!useLazyMarkdown.value && !useVirtualText.value && isMarkdownFile.value) {
          scheduleLoadMarkdownImages()
        }
      }
    }
  )

  watch(
    () => currentMode.value,
    (newMode, oldMode) => {
      if (oldMode === 'note' && editMode.value) {
        const s = codeMirrorApi.getEditorDocString?.()
        if (typeof s === 'string') {
          content.value = s
          loadedLineCount.value = countLinesLimited(content.value || '')
          _handleTrackedContentChange({ preferEditor: false })
        }
      }

      if (oldMode === 'note' && newMode !== 'note') {
        codeMirrorApi.forceExitEditMode()
      }
    }
  )

  watch(
    () => currentFile.value,
    () => resetHebbianStatus()
  )

  onMounted(() => {
    const saved = safe_local_storage_get('nisb_editor_content', '')
    if (saved) {
      content.value = saved
      loadedLineCount.value = countLinesLimited(saved)
    }

    try {
      const initLeft = Number(localStorage.getItem('nisb_left_width'))
      const initRight = Number(localStorage.getItem('nisb_right_width'))
      if (Number.isFinite(initLeft) || Number.isFinite(initRight)) {
        window.dispatchEvent(
          new CustomEvent('sidebar-state-changed', {
            detail: {
              left: Number.isFinite(initLeft) ? initLeft : 280,
              right: Number.isFinite(initRight) ? initRight : 280
            }
          })
        )
      }
    } catch {}

    navApi.mount()

    window.addEventListener('nisb-open-lightbox', handleOpenLightboxEvent)
    window.addEventListener('paste', handlePasteWebClip, true)

    window.addEventListener('nisb-library-dock-toggle', _onDockToggleRequest)
    window.addEventListener('nisb-open-library-doc', onOpenLibraryDocCapture, true)
    window.addEventListener('nisb-outline-jump', outlineBridgeApi.handleOutlineJumpEvent, true)

    try {
      window.__vue_dbg_useLazyMarkdown = useLazyMarkdown
      window.__vue_dbg_lazyMdRef = lazyMdRef
      window.__vue_dbg_isMarkdownFile = isMarkdownFile
      window.__vue_dbg_currentMode = currentMode
      console.log('[dbg expose]', {
        useLazyMarkdown: useLazyMarkdown.value,
        hasLazyRef: !!lazyMdRef.value,
        isMarkdown: isMarkdownFile.value,
        mode: currentMode.value
      })
    } catch {}
  })

  onUnmounted(() => {
    fileIOApi.clearAutoSaveTimer()
    fileIOApi.abortFileLoading()
    revokePdfUrlIfAny()
    scrollSyncApi.cleanup()

    navApi.unmount()

    window.removeEventListener('nisb-open-lightbox', handleOpenLightboxEvent)
    window.removeEventListener('paste', handlePasteWebClip, true)
    window.removeEventListener('nisb-library-dock-toggle', _onDockToggleRequest)
    window.removeEventListener('nisb-open-library-doc', onOpenLibraryDocCapture, true)
    window.removeEventListener('nisb-outline-jump', outlineBridgeApi.handleOutlineJumpEvent, true)
  })

  return {
    saving,
    hebbianProcessing,
    hebbianStatus,
    hebbianLastTime,

    currentView,
    currentMode,
    editMode,

    currentFile,
    currentDir,
    fileLoading,
    loadedFilePath,
    loadedLineCount,

    saveStatus,
    autoSaving,

    leftCollapsed,
    rightCollapsed,

    content,
    renderedHtml,
    isMarkdownFile,
    useLazyMarkdown,
    useVirtualText,
    editorContainer,

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
    onModeScroll,
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
    handleBackFromLibrary,
    currentRssFeedId,
    handleBackFromRss,

    currentRssGateFeedId,
    currentRssGateQuery,
    handleBackFromRssGate,

    libraryDockedRight,
    toggleLibraryDockRight,

    cmGetEditorStats,
    cmToggleLineNumbers,
    cmToggleLineWrapping,
    cmFoldAll,
    cmUnfoldAll,

    getDefaultHideLineNumbers: codeMirrorApi.getDefaultHideLineNumbers,
    setDefaultHideLineNumbers: codeMirrorApi.setDefaultHideLineNumbers
  }
}

