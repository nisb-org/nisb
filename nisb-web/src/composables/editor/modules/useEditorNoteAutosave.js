import { safe_local_storage_set } from '../../../utils/storage_safe'

export function useEditorNoteAutosave(ctx) {
  const {
    content,
    loadedLineCount,
    saveStatus,
    autoSaving,
    currentFile,
    countLinesLimited,
    getFileIOApi,
    getCodeMirrorApi,
    performAutoSave
  } = ctx

  const EDITOR_CACHE_MAX_BYTES = 512 * 1024

  function markNoteUnsaved() {
    saveStatus.value = 'unsaved'
    try {
      safe_local_storage_set('nisb_editor_content', String(content.value || ''), { max_bytes: EDITOR_CACHE_MAX_BYTES })
    } catch {}
  }

  async function _runAutoSaveNow() {
    const fileIOApi = typeof getFileIOApi === 'function' ? getFileIOApi() : null
    const codeMirrorApi = typeof getCodeMirrorApi === 'function' ? getCodeMirrorApi() : null

    if (typeof performAutoSave === 'function') {
      autoSaving.value = true
      try {
        const result = await performAutoSave({
          reason: 'autosave',
          getEditorDocString: codeMirrorApi?.getEditorDocString
        })

        if (result?.success) {
          saveStatus.value = result?.status || 'saved'
        } else if (result?.status && result.status !== 'cancelled') {
          saveStatus.value = result.status
        } else {
          saveStatus.value = 'unsaved'
        }
      } finally {
        autoSaving.value = false
      }
      return
    }

    if (!fileIOApi) return
    await fileIOApi.autoSave(codeMirrorApi?.getEditorDocString)
  }

  function debouncedAutoSave() {
    const fileIOApi = typeof getFileIOApi === 'function' ? getFileIOApi() : null
    if (!fileIOApi) return

    fileIOApi.clearAutoSaveTimer()
    saveStatus.value = 'unsaved'

    const id = setTimeout(async () => {
      await _runAutoSaveNow()
    }, 3000)

    fileIOApi.setAutoSaveTimer(id)
  }

  function scheduleNoteAutosaveIfAllowed({ requirePath = true } = {}) {
    const fileIOApi = typeof getFileIOApi === 'function' ? getFileIOApi() : null
    if (!fileIOApi) return false
    if (!fileIOApi.isCurrentFileLoadedSafe()) return false
    if (requirePath && !String(currentFile.value?.path || '').trim()) return false

    debouncedAutoSave()
    return true
  }

  function applyExternalNoteContent(nextValue, { autoSave = false, requirePath = true } = {}) {
    const nextText = String(nextValue || '')
    const prevText = String(content.value || '')

    if (nextText === prevText) return false

    content.value = nextText
    loadedLineCount.value = typeof countLinesLimited === 'function' ? countLinesLimited(nextText) : 0

    const fileIOApi = typeof getFileIOApi === 'function' ? getFileIOApi() : null
    if (fileIOApi && typeof fileIOApi.onContentChange === 'function') {
      fileIOApi.onContentChange()
    } else {
      try {
        safe_local_storage_set('nisb_editor_content', nextText, { max_bytes: EDITOR_CACHE_MAX_BYTES })
      } catch {}
    }

    markNoteUnsaved()

    if (autoSave) {
      scheduleNoteAutosaveIfAllowed({ requirePath })
    }

    return true
  }

  return {
    debouncedAutoSave,
    markNoteUnsaved,
    scheduleNoteAutosaveIfAllowed,
    applyExternalNoteContent
  }
}
