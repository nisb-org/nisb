import { ref } from 'vue'
import { useMCP } from './useMCP'
import { useSettingsStore } from '../stores/settings'
import { safe_local_storage_set } from '../utils/storage_safe'
import filesEn from '../locales/en/files.js'
import filesZh from '../locales/zh-CN/files.js'

const FILE_LOCALES = {
  en: filesEn,
  'zh-CN': filesZh
}

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalize_locale(locale) {
  const raw = safe_string(locale).trim()
  if (raw.toLowerCase().startsWith('zh')) return 'zh-CN'
  return 'en'
}

function get_path_value(source, path) {
  const parts = safe_string(path).split('.').filter(Boolean)
  let cur = source

  for (const part of parts) {
    if (!cur || typeof cur !== 'object') return ''
    cur = cur[part]
  }

  return typeof cur === 'string' ? cur : ''
}

function format_template(template, vars = {}) {
  return safe_string(template).replace(/\{([^}]+)\}/g, (_, key) => {
    const value = vars?.[key]
    return value === null || value === undefined ? '' : String(value)
  })
}

function unwrap_result(result) {
  if (result && typeof result === 'object' && result.result && typeof result.result === 'object') {
    return result.result
  }

  return result || {}
}

function has_cjk(text) {
  return /[\u3400-\u9fff]/.test(safe_string(text))
}

export function useNoteOperations() {
  const { callTool } = useMCP()
  const settings = useSettingsStore()

  const saving = ref(false)
  const hebbianProcessing = ref(false)
  const hebbianStatus = ref('idle')
  const hebbianLastTime = ref('')

  const EDITOR_CACHE_MAX_BYTES = 512 * 1024
  const OUTLINE_PATH_MAX_BYTES = 32 * 1024

  const lastSavedSnapshotByPath = new Map()

  function current_locale() {
    return normalize_locale(settings?.locale || 'en')
  }

  function text(key, vars = {}) {
    const locale = current_locale()
    const pack = FILE_LOCALES[locale] || FILE_LOCALES.en
    const fallbackPack = FILE_LOCALES.en

    const template =
      get_path_value(pack, `noteOperations.${key}`) ||
      get_path_value(fallbackPack, `noteOperations.${key}`) ||
      key

    return format_template(template, vars)
  }

  function visible_error(value, fallbackKey = 'unknownError') {
    const locale = current_locale()
    const data = unwrap_result(value)
    const raw = safe_string(data?.message || data?.error || data?.detail || value?.message).trim()

    if (raw && !(locale !== 'zh-CN' && has_cjk(raw))) {
      return raw
    }

    return text(fallbackKey)
  }

  function locale_for_date() {
    return current_locale() === 'zh-CN' ? 'zh-CN' : 'en-US'
  }

  function _toast(message, type = 'info') {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message, type }
      })
    )
  }

  function _normalizeContentForSave(value) {
    return String(value ?? '')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
  }

  function _resolveContentToSave(content, editMode, editorView, isCodeMode) {
    let contentToSave = content

    if (isCodeMode) {
      const match = String(contentToSave || '').match(/^``````$/)
      if (match) {
        contentToSave = String(contentToSave || '').replace(/^``````$/, '')
      }
    } else if (editMode && editorView) {
      try {
        contentToSave = editorView.state.doc.toString()
      } catch {}
    }

    return String(contentToSave ?? '')
  }

  function _persistEditorCaches(contentToSave, path) {
    safe_local_storage_set('nisb_editor_content', contentToSave, { max_bytes: EDITOR_CACHE_MAX_BYTES })
    safe_local_storage_set('nisb_outline_file_path', path, { max_bytes: OUTLINE_PATH_MAX_BYTES })
  }

  function _rememberSavedSnapshot(path, contentToSave) {
    const p = String(path || '').trim()
    if (!p) return
    lastSavedSnapshotByPath.set(p, _normalizeContentForSave(contentToSave))
  }

  function _isSameAsLastSaved(path, contentToSave) {
    const p = String(path || '').trim()
    if (!p) return false
    if (!lastSavedSnapshotByPath.has(p)) return false
    const prev = String(lastSavedSnapshotByPath.get(p) || '')
    const next = _normalizeContentForSave(contentToSave)
    return prev === next
  }

  function _isSuccessResult(result) {
    const data = unwrap_result(result)
    const status = String(data?.status || '').trim().toLowerCase()
    return status === 'success' || status === 'ok' || data?.success === true
  }

  function _buildInternalEditorSaveArgs(base = {}) {
    return {
      ...base,
      locale: current_locale(),
      _internal_editor_save: true
    }
  }

  function _shouldToastSuccess(reason) {
    return reason === 'manual'
  }

  function _shouldToastError(reason) {
    return reason === 'manual'
  }

  async function saveNote(currentFile, content, editMode, editorView, isCodeMode, currentDir, options = {}) {
    if (saving.value) {
      return { success: false, status: 'saving' }
    }

    const reason = String(options?.reason || 'manual').trim().toLowerCase()
    const contentToSave = _resolveContentToSave(content, editMode, editorView, isCodeMode)

    saving.value = true
    try {
      if (currentFile && currentFile.path) {
        if (_isSameAsLastSaved(currentFile.path, contentToSave)) {
          _persistEditorCaches(contentToSave, currentFile.path)
          return {
            success: true,
            status: 'saved',
            skipped: true,
            file: currentFile
          }
        }

        const result = await callTool(
          'nisb_file_update',
          _buildInternalEditorSaveArgs({
            filename: currentFile.path,
            content: contentToSave
          })
        )

        const data = unwrap_result(result)

        if (_isSuccessResult(data)) {
          _rememberSavedSnapshot(currentFile.path, contentToSave)
          _persistEditorCaches(contentToSave, currentFile.path)

          if (_shouldToastSuccess(reason)) {
            _toast(text('fileSaved', { name: currentFile.name || currentFile.path || '' }), 'success')
          }

          return {
            success: true,
            status: 'saved',
            file: currentFile
          }
        }

        if (_shouldToastError(reason)) {
          _toast(text('saveFailed', { error: visible_error(data) }), 'error')
        }

        return {
          success: false,
          status: 'unsaved',
          message: visible_error(data)
        }
      }

      const ts = new Date()
      const defaultBase = ts.toISOString().slice(0, 16).replace('T', '_').replace(/:/g, '-')
      const suggestedName = defaultBase + '.md'
      const baseDir = currentDir || ''

      const filename = prompt(
        text('unsavedPrompt'),
        (baseDir ? baseDir + '/' : '') + suggestedName
      )

      if (!filename) {
        return { success: false, status: 'cancelled' }
      }

      const result = await callTool(
        'nisb_file_create',
        _buildInternalEditorSaveArgs({
          filename,
          content: contentToSave,
          description: text('createDescription', {
            time: new Date().toLocaleString(locale_for_date())
          }),
          auto_categorize: false
        })
      )

      const data = unwrap_result(result)

      if (_isSuccessResult(data)) {
        const name = filename.split('/').pop()

        _rememberSavedSnapshot(filename, contentToSave)
        _persistEditorCaches(contentToSave, filename)

        window.dispatchEvent(
          new CustomEvent('nisb-file-created', {
            detail: { path: filename, name }
          })
        )

        window.dispatchEvent(
          new CustomEvent('nisb-open-file', {
            detail: { path: filename, name }
          })
        )

        if (_shouldToastSuccess(reason)) {
          _toast(text('createdAndSaved', { filename }), 'success')
        }

        return {
          success: true,
          status: 'saved',
          file: { path: filename, name }
        }
      }

      if (_shouldToastError(reason)) {
        _toast(text('saveFailed', { error: visible_error(data) }), 'error')
      }

      return {
        success: false,
        status: 'unsaved',
        message: visible_error(data)
      }
    } catch (error) {
      if (_shouldToastError(reason)) {
        _toast(text('saveFailed', { error: visible_error(error) }), 'error')
      }
      return {
        success: false,
        status: 'unsaved',
        message: visible_error(error)
      }
    } finally {
      saving.value = false
    }
  }

  async function noteToBrain(currentFile) {
    if (!currentFile?.path) {
      _toast(text('noFileOpen'), 'info')
      return
    }

    const filename = currentFile.path
    const displayName = currentFile.name || currentFile.path

    hebbianProcessing.value = true
    hebbianStatus.value = 'idle'

    try {
      _toast(text('processingNote', { name: displayName }), 'info')

      const res = await callTool('nisb_note_to_brain', {
        filename,
        locale: current_locale()
      })

      const data = unwrap_result(res)

      if (_isSuccessResult(data)) {
        hebbianStatus.value = 'done'
        hebbianLastTime.value = text('justNow')

        _toast(text('noteSentToBrain', { name: displayName }), 'success')

        window.dispatchEvent(
          new CustomEvent('nisb-hebbian-completed', {
            detail: { source: filename, type: 'note' }
          })
        )

        setTimeout(() => {
          hebbianStatus.value = 'idle'
        }, 3000)
      } else {
        _toast(text('noteToBrainFailed', { error: visible_error(data) }), 'error')
      }
    } catch (error) {
      _toast(text('noteToBrainException', { error: visible_error(error) }), 'error')
    } finally {
      hebbianProcessing.value = false
    }
  }

  function resetHebbianStatus() {
    hebbianStatus.value = 'idle'
    hebbianLastTime.value = ''
  }

  return {
    saving,
    hebbianProcessing,
    hebbianStatus,
    hebbianLastTime,
    saveNote,
    noteToBrain,
    resetHebbianStatus
  }
}
