import { ref } from 'vue'
import { useMCP } from './useMCP'
import { useSettingsStore } from '../stores/settings'
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

function is_tool_success(data) {
  const status = safe_string(data?.status).trim().toLowerCase()
  if (status) return status === 'success' || status === 'ok'
  if (data?.success === true) return true
  return false
}

function has_cjk(text) {
  return /[\u3400-\u9fff]/.test(safe_string(text))
}

export function useAutoSave() {
  const { callTool } = useMCP()
  const settings = useSettingsStore()

  const autoSaving = ref(false)
  const saveStatus = ref('saved')
  let autoSaveTimer = null

  function current_locale() {
    return normalize_locale(settings?.locale || 'en')
  }

  function text(key, vars = {}) {
    const locale = current_locale()
    const pack = FILE_LOCALES[locale] || FILE_LOCALES.en
    const fallbackPack = FILE_LOCALES.en

    const template =
      get_path_value(pack, `autoSave.${key}`) ||
      get_path_value(fallbackPack, `autoSave.${key}`) ||
      key

    return format_template(template, vars)
  }

  function visible_error(data, fallbackKey = 'unknownError') {
    const locale = current_locale()
    const raw = safe_string(data?.message || data?.error || data?.detail).trim()

    if (raw && !(locale !== 'zh-CN' && has_cjk(raw))) {
      return raw
    }

    return text(fallbackKey)
  }

  function debouncedAutoSave(getContent, currentFile, delay = 3000) {
    if (autoSaveTimer) clearTimeout(autoSaveTimer)

    saveStatus.value = 'unsaved'

    autoSaveTimer = setTimeout(async () => {
      await autoSave(getContent, currentFile)
    }, delay)
  }

  async function autoSave(getContent, currentFile) {
    if (!currentFile || autoSaving.value) return

    const contentToSave = typeof getContent === 'function' ? getContent() : ''
    if (!contentToSave || !safe_string(contentToSave).trim()) return

    autoSaving.value = true
    saveStatus.value = 'saving'

    try {
      const result = await callTool('nisb_file_update', {
        filename: currentFile.path,
        content: contentToSave,
        locale: current_locale()
      })

      const data = unwrap_result(result)

      if (is_tool_success(data)) {
        saveStatus.value = 'saved'
        console.log('[auto-save] success:', currentFile.name)
      } else {
        saveStatus.value = 'unsaved'
        console.error('[auto-save] failed:', visible_error(data))
      }
    } catch (error) {
      saveStatus.value = 'unsaved'
      console.error('[auto-save] error:', error)
    } finally {
      autoSaving.value = false
    }
  }

  async function manualSave(getContent, currentFile) {
    if (!currentFile) {
      return await saveAsQuickNote(typeof getContent === 'function' ? getContent() : '')
    }

    const contentToSave = typeof getContent === 'function' ? getContent() : ''

    try {
      const result = await callTool('nisb_file_update', {
        filename: currentFile.path,
        content: contentToSave,
        locale: current_locale()
      })

      const data = unwrap_result(result)

      if (is_tool_success(data)) {
        saveStatus.value = 'saved'
        return {
          success: true,
          message: text('fileSaved', {
            name: currentFile.name || currentFile.path || ''
          })
        }
      }

      return {
        success: false,
        message: text('saveFailed', {
          error: visible_error(data)
        })
      }
    } catch (error) {
      return {
        success: false,
        message: text('saveFailed', {
          error: visible_error(error)
        })
      }
    }
  }

  async function saveAsQuickNote(content) {
    try {
      const result = await callTool('nisb_sense_quick_note', {
        content,
        tags: [],
        locale: current_locale()
      })

      const data = unwrap_result(result)

      if (is_tool_success(data)) {
        saveStatus.value = 'saved'
        return {
          success: true,
          message: text('quickNoteSaved')
        }
      }

      return {
        success: false,
        message: text('saveFailed', {
          error: visible_error(data)
        })
      }
    } catch (error) {
      return {
        success: false,
        message: text('saveFailed', {
          error: visible_error(error)
        })
      }
    }
  }

  function cleanup() {
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer)
      autoSaveTimer = null
    }
  }

  return {
    autoSaving,
    saveStatus,
    debouncedAutoSave,
    autoSave,
    manualSave,
    saveAsQuickNote,
    cleanup
  }
}
