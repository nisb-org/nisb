import { nextTick } from 'vue'
import { safe_local_storage_set } from '../../../utils/storage_safe'

export function useEditorFileIO(ctx) {
  const {
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

    debouncedAutoSave,

    forceExitEditMode,
    syncFromContent
  } = ctx

  let autoSaveTimer = null
  let fileLoadController = null
  let fileLoadRunId = 0

  const FILE_READ_BASE64_TOOL = 'nisb_file_read_base64'
  const BINARY_READ_MAX_BYTES = 50 * 1024 * 1024

  const EDITOR_CACHE_MAX_BYTES = 512 * 1024
  const OUTLINE_PATH_MAX_BYTES = 32 * 1024

  const lastSavedSnapshotByPath = new Map()

  const LINE_COUNT_LIMIT = 500000
  function _count_lines_limited(text, limit = LINE_COUNT_LIMIT) {
    const s = String(text || '')
    if (!s) return 0
    let n = 1
    for (let i = 0; i < s.length; i++) {
      if (s.charCodeAt(i) === 10) {
        n += 1
        if (n >= limit) return limit
      }
    }
    return n
  }

  const __is_firefox = (() => {
    try {
      return /firefox/i.test(String(navigator.userAgent || ''))
    } catch {
      return false
    }
  })()

  function _normalizeContentForSave(value) {
    return String(value ?? '')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
  }

  function _rememberSavedSnapshot(path, text) {
    const p = String(path || '').trim()
    if (!p) return
    lastSavedSnapshotByPath.set(p, _normalizeContentForSave(text))
  }

  function _getSavedSnapshot(path) {
    const p = String(path || '').trim()
    if (!p) return null
    if (!lastSavedSnapshotByPath.has(p)) return null
    return String(lastSavedSnapshotByPath.get(p) || '')
  }

  function _isSameAsSavedSnapshot(path, text) {
    const prev = _getSavedSnapshot(path)
    if (prev === null) return false
    const next = _normalizeContentForSave(text)
    return prev === next
  }

  function _request_idle(cb, { timeout = 600 } = {}) {
    if (typeof window.requestIdleCallback === 'function') return window.requestIdleCallback(cb, { timeout })
    return window.setTimeout(() => cb({ didTimeout: true, timeRemaining: () => 0 }), 0)
  }

  function _cancel_idle(id) {
    try {
      if (typeof window.cancelIdleCallback === 'function') window.cancelIdleCallback(id)
      else clearTimeout(id)
    } catch {}
  }

  let __cache_timer = null
  let __cache_idle_id = null
  let __cache_write_run_id = 0

  function _cancel_cache_write() {
    if (__cache_timer) clearTimeout(__cache_timer)
    __cache_timer = null
    if (__cache_idle_id !== null) _cancel_idle(__cache_idle_id)
    __cache_idle_id = null
  }

  function _schedule_cache_write({ run_id, path } = {}) {
    _cancel_cache_write()

    const my_run = Number.isFinite(Number(run_id)) ? Number(run_id) : fileLoadRunId
    const p = String(path || '').trim()
    const snapshot = String(content.value || '')

    __cache_timer = setTimeout(() => {
      const do_write = () => {
        try {
          if (my_run !== fileLoadRunId) return

          if (p) {
            safe_local_storage_set('nisb_outline_file_path', p, { max_bytes: OUTLINE_PATH_MAX_BYTES })
          }

          const max_chars = __is_firefox ? 220_000 : 420_000
          if (snapshot && snapshot.length <= max_chars) {
            safe_local_storage_set('nisb_editor_content', snapshot, { max_bytes: EDITOR_CACHE_MAX_BYTES })
          }
        } catch {}
      }

      __cache_idle_id = _request_idle(do_write, { timeout: 800 })
    }, __is_firefox ? 220 : 160)
  }

  function _persistLocalCaches(text, path) {
    const p = String(path || '').trim()
    const snapshot = String(text || '')

    if (p) {
      safe_local_storage_set('nisb_outline_file_path', p, { max_bytes: OUTLINE_PATH_MAX_BYTES })
    }

    const max_chars = __is_firefox ? 220_000 : 420_000
    if (snapshot && snapshot.length <= max_chars) {
      safe_local_storage_set('nisb_editor_content', snapshot, { max_bytes: EDITOR_CACHE_MAX_BYTES })
    }
  }

  function _getUid() {
    try {
      const uid = String(localStorage.getItem('nisb_user_id') || '').trim()
      return uid || 'nisb_default_user'
    } catch {
      return 'nisb_default_user'
    }
  }

  function _ext(name) {
    const n = String(name || '').toLowerCase()
    const i = n.lastIndexOf('.')
    return i >= 0 ? n.slice(i) : ''
  }

  function _isImageByName(name) {
    const e = _ext(name)
    return ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.bmp'].includes(e)
  }

  function _looksLikeNotFoundMessage(msg) {
    const s = String(msg || '')
    return s.includes('文件不存在') || s.toLowerCase().includes('not found')
  }

  async function _readBinaryViaBase64(filename, signal) {
    const uid = _getUid()
    const r = await callTool(
      FILE_READ_BASE64_TOOL,
      { filename: String(filename || '').trim(), uid, max_bytes: BINARY_READ_MAX_BYTES },
      { signal }
    )

    if (!r?.success) throw new Error(r?.message || 'Read failed')

    return {
      mime: String(r?.mime || '').trim() || 'application/octet-stream',
      dataBase64: String(r?.data_base64 || '')
    }
  }

  function isCurrentFileLoadedSafe() {
    const p = String(currentFile.value?.path || '')
    if (!p) return true
    if (fileLoading.value) return false
    if (!loadedFilePath.value) return false
    return p === loadedFilePath.value
  }

  function onContentChange() {
    if (!isCurrentFileLoadedSafe()) return

    if (currentFile.value && !isImageMode.value && !isCodeMode.value && !isPdfMode.value) {
      if (saveStatus.value === 'saved') saveStatus.value = 'unsaved'
    }

    _schedule_cache_write({ run_id: fileLoadRunId, path: String(currentFile.value?.path || '').trim() })
  }

  function clearAutoSaveTimer() {
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }

  function setAutoSaveTimer(timerId) {
    clearAutoSaveTimer()
    autoSaveTimer = timerId
  }

  async function autoSave(getEditorDocString) {
    if (!isCurrentFileLoadedSafe()) return
    if (!currentFile.value || isImageMode.value || isCodeMode.value || isPdfMode.value) return

    const path = String(currentFile.value.path || '').trim()
    if (!path) return

    let contentToSave = content.value
    if (typeof getEditorDocString === 'function') {
      const s = getEditorDocString()
      if (typeof s === 'string') contentToSave = s
    }

    contentToSave = _normalizeContentForSave(contentToSave)

    if (!String(contentToSave || '').trim() || autoSaving.value) return

    if (_isSameAsSavedSnapshot(path, contentToSave)) {
      _persistLocalCaches(contentToSave, path)
      saveStatus.value = 'saved'
      return
    }

    autoSaving.value = true
    try {
      const result = await callTool('nisb_file_update', { filename: path, content: contentToSave })
      if (result && result.success) {
        _rememberSavedSnapshot(path, contentToSave)
        _persistLocalCaches(contentToSave, path)
        saveStatus.value = 'saved'
      } else {
        saveStatus.value = 'unsaved'
      }
    } catch {
      saveStatus.value = 'unsaved'
    } finally {
      autoSaving.value = false
    }
  }

  function _is_signal_aborted(signal) {
    try {
      return !!signal?.aborted
    } catch {
      return false
    }
  }

  async function _yield_main_thread() {
    await new Promise((r) => setTimeout(r, 0))
  }

  async function _base64_to_uint8array_chunked(b64, { run_id, signal, chunk = 1 << 20 } = {}) {
    if (run_id !== fileLoadRunId) return null
    if (_is_signal_aborted(signal)) return null

    const s = String(b64 || '')
    if (!s) return new Uint8Array(0)

    let bin = ''
    try {
      bin = atob(s)
    } catch {
      return null
    }

    const len = bin.length
    const bytes = new Uint8Array(len)

    for (let i = 0; i < len; i += chunk) {
      if (run_id !== fileLoadRunId) return null
      if (_is_signal_aborted(signal)) return null

      const end = Math.min(len, i + chunk)
      for (let j = i; j < end; j++) bytes[j] = bin.charCodeAt(j)

      await _yield_main_thread()
    }

    return bytes
  }

  function startLoadFile(path) {
    __cache_write_run_id += 1
    _cancel_cache_write()

    if (fileLoadController) {
      try {
        fileLoadController.abort()
      } catch {}
      fileLoadController = null
    }

    revokePdfUrlIfAny()

    fileLoading.value = true
    loadedFilePath.value = ''

    fileLoadRunId += 1
    const runId = fileLoadRunId
    fileLoadController = new AbortController()

    isPdfMode.value = false
    pdfMetadata.value = {}

    loadFile(path, runId, fileLoadController.signal)
  }

  async function loadFile(path, runId, signal) {
    let result = null

    try {
      result = await callTool('nisb_file_read', { filename: path }, { signal })
      if (runId !== fileLoadRunId) return
      if (_is_signal_aborted(signal)) return

      if (!result?.success) {
        const msg = String(result?.message || '')
        const nameGuess = String(currentFile.value?.name || '')
        const isPdfGuess = isPdfFile(nameGuess) || isPdfFile(path)
        const isImgGuess = _isImageByName(nameGuess) || _isImageByName(path)

        if (_looksLikeNotFoundMessage(msg) && (isPdfGuess || isImgGuess)) {
          const b = await _readBinaryViaBase64(path, signal)

          if (runId !== fileLoadRunId) return
          if (_is_signal_aborted(signal)) return

          if (isPdfGuess) {
            if (typeof forceExitEditMode === 'function') forceExitEditMode()

            isPdfMode.value = true
            isImageMode.value = false
            isCodeMode.value = false
            editMode.value = false

            pdfMetadata.value = { type: 'pdf', mime_type: b.mime, via: 'base64_fallback' }

            const bytes =
              (await _base64_to_uint8array_chunked(b.dataBase64, { run_id: runId, signal })) || base64ToUint8Array(b.dataBase64)

            if (runId !== fileLoadRunId) return
            if (_is_signal_aborted(signal)) return

            const blob = new Blob([bytes], { type: 'application/pdf' })
            pdfObjectUrl.value = URL.createObjectURL(blob)

            saveStatus.value = 'saved'
            return
          }

          if (isImgGuess) {
            if (typeof forceExitEditMode === 'function') forceExitEditMode()

            isPdfMode.value = false
            isImageMode.value = true
            isCodeMode.value = false
            editMode.value = false

            content.value = `data:${b.mime};base64,${b.dataBase64}`
            imageMetadata.value = { type: 'image', mime_type: b.mime, via: 'base64_fallback' }
            saveStatus.value = 'saved'
            return
          }
        }

        window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message: '❌ 读取失败：' + (result?.message || ''), type: 'error' } }))
        return
      }

      const meta = result.metadata || {}
      const isImg = meta.type === 'image'
      const isPdf = meta.type === 'pdf' || meta.mime_type === 'application/pdf' || isPdfFile(currentFile.value?.name)
      const isCode = !isImg && !isPdf && currentFile.value && isCodeFile(currentFile.value.name)

      loadedLineCount.value = 0

      if (isPdf) {
        if (typeof forceExitEditMode === 'function') forceExitEditMode()

        isPdfMode.value = true
        isImageMode.value = false
        isCodeMode.value = false
        editMode.value = false

        pdfMetadata.value = meta

        const b64 = result.content || ''
        const bytes = (await _base64_to_uint8array_chunked(b64, { run_id: runId, signal })) || base64ToUint8Array(b64)

        if (runId !== fileLoadRunId) return
        if (_is_signal_aborted(signal)) return

        const blob = new Blob([bytes], { type: 'application/pdf' })
        pdfObjectUrl.value = URL.createObjectURL(blob)

        saveStatus.value = 'saved'
        return
      }

      if (isImg) {
        if (typeof forceExitEditMode === 'function') forceExitEditMode()

        isPdfMode.value = false
        isImageMode.value = true
        isCodeMode.value = false
        editMode.value = false

        content.value = result.content
        imageMetadata.value = meta
        saveStatus.value = 'saved'
        return
      }

      if (isCode) {
        if (typeof forceExitEditMode === 'function') forceExitEditMode()

        isPdfMode.value = false
        isImageMode.value = false
        isCodeMode.value = true
        editMode.value = false

        const lang = getCodeLanguage(currentFile.value.name)
        const rawCode = String(result.content || '')
        content.value = `\`\`\`${lang}\n${rawCode}\n\`\`\``
        loadedLineCount.value = _count_lines_limited(rawCode)
        saveStatus.value = 'saved'
        _rememberSavedSnapshot(String(path || '').trim(), rawCode)
        return
      }

      isPdfMode.value = false
      isImageMode.value = false
      isCodeMode.value = false

      const textContent = String(result.content || '')
      content.value = textContent
      loadedLineCount.value = _count_lines_limited(textContent)
      saveStatus.value = 'saved'
      _rememberSavedSnapshot(String(path || '').trim(), textContent)

      _schedule_cache_write({ run_id: runId, path: String(path || '').trim() })

      await nextTick()

      if (runId !== fileLoadRunId) return
      if (_is_signal_aborted(signal)) return

      if (editMode.value && typeof syncFromContent === 'function') {
        try {
          syncFromContent(content.value)
        } catch {}
      }

      if (!useLazyMarkdown.value && isMarkdownFile.value) {
      }
    } catch (e) {
      if (e && e.name === 'AbortError') return
      window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message: '❌ 读取失败：' + (e?.message || ''), type: 'error' } }))
    } finally {
      if (runId === fileLoadRunId) {
        fileLoading.value = false
        loadedFilePath.value = String(path || '')
      }
    }
  }

  function abortFileLoading() {
    fileLoadRunId += 1
    _cancel_cache_write()

    if (fileLoadController) {
      try {
        fileLoadController.abort()
      } catch {}
      fileLoadController = null
    }
  }

  return {
    clearAutoSaveTimer,
    setAutoSaveTimer,

    autoSave,

    isCurrentFileLoadedSafe,
    onContentChange,

    startLoadFile,
    abortFileLoading
  }
}
