import enLibrary from '../../../locales/en/library'
import zhCNLibrary from '../../../locales/zh-CN/library'
import { normalizeToolResponse, pickDataValue } from './response_normalizer'

const LIBRARY_LOCALES = {
  en: enLibrary,
  'zh-CN': zhCNLibrary
}

function _string(value) {
  return String(value ?? '').trim()
}

function _normalize_locale(value) {
  const raw = _string(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function _ls_get_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key)
      if (value !== null && _string(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function _current_locale(explicitLocale = '') {
  if (_string(explicitLocale)) return _normalize_locale(explicitLocale)

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

  const fromStorage = _ls_get_first(
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

function _format(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function _make_t(explicitLocale = '') {
  return function t(path, params = {}, fallback = '') {
    const locale = _current_locale(explicitLocale)
    const messages = LIBRARY_LOCALES[locale] || LIBRARY_LOCALES.en
    const value = _deep_get(messages, path, _deep_get(LIBRARY_LOCALES.en, path, fallback))
    return _format(value || fallback || path, params)
  }
}

export function create_left_sidebar_library_actions({
  call_tool,
  hide_context_menu,
  library_list_ref,
  pick_cm,
  cm_target_id,
  cm_target_name,
  locale = '',
  t: external_t = null
}) {
  const local_t = _make_t(locale)

  function t(path, params = {}, fallback = '') {
    if (typeof external_t === 'function') {
      const externalValue = external_t(path, params)
      if (_string(externalValue) && externalValue !== path) return externalValue
    }
    return local_t(path, params, fallback)
  }

  function _alert(message) {
    try {
      alert(message)
    } catch {}
  }

  function _confirm(message) {
    try {
      return confirm(message)
    } catch {
      return false
    }
  }

  function _prompt(message, defaultValue = '') {
    try {
      return prompt(message, defaultValue)
    } catch {
      return null
    }
  }

  function _unknown_error() {
    return t('left.actionDialogs.unknownError', {}, 'Unknown error')
  }

  function _tool_args(args = {}) {
    return {
      ...args,
      locale: _current_locale(locale)
    }
  }

  async function handle_library_rename(cm_in) {
    const cm = pick_cm(cm_in)
    const oldName = cm_target_name(cm)
    const libraryId = cm_target_id(cm)
    const new_name = _prompt(
      t('left.actionDialogs.renamePrompt', {}, 'Enter a new name:'),
      oldName
    )

    if (!new_name || new_name === oldName) {
      hide_context_menu()
      return
    }

    try {
      const result = await call_tool(
        'nisb_library_rename',
        _tool_args({
          library_id: libraryId,
          new_name
        })
      )
      const info = normalizeToolResponse(
        result,
        t('left.actionDialogs.renameSuccessFallback', {}, 'Library renamed successfully')
      )

      if (info.success) {
        _alert(
          t('left.actionDialogs.successPrefix', {}, '✅ ') +
            (info.text || t('left.actionDialogs.renameSuccessFallback', {}, 'Library renamed successfully'))
        )
        library_list_ref.value?.loadLibraries()
      } else {
        _alert(
          t('left.actionDialogs.renameFailed', { error: info.text || _unknown_error() }, 'Rename failed: {error}')
        )
      }
    } catch (e) {
      _alert(
        t(
          'left.actionDialogs.renameFailed',
          { error: e?.message || String(e) },
          'Rename failed: {error}'
        )
      )
    } finally {
      hide_context_menu()
    }
  }

  async function handle_library_info(cm_in) {
    const cm = pick_cm(cm_in)
    const libraryId = cm_target_id(cm)

    try {
      const result = await call_tool(
        'nisb_library_get_info',
        _tool_args({ library_id: libraryId })
      )
      const info = normalizeToolResponse(
        result,
        t('left.actionDialogs.infoSuccessFallback', {}, 'Library info loaded')
      )

      if (info.success) {
        const lib = pickDataValue(result, 'info', {}) || {}

        _alert(
          t(
            'left.actionDialogs.infoBody',
            {
              name: String(lib.library_name || cm_target_name(cm) || ''),
              docCount: String(lib.doc_count ?? 0),
              conceptCount: String(lib.concept_count ?? 0),
              relationCount: String(lib.relation_count ?? 0),
              createdAt: String(lib.created_at || '')
            },
            'Library info:\nName: {name}\nDocuments: {docCount}\nConcepts: {conceptCount}\nRelations: {relationCount}\nCreated at: {createdAt}'
          )
        )
      } else {
        _alert(
          t('left.actionDialogs.infoFailed', { error: info.text || _unknown_error() }, 'Failed to get info: {error}')
        )
      }
    } catch (e) {
      _alert(
        t(
          'left.actionDialogs.infoFailed',
          { error: e?.message || String(e) },
          'Failed to get info: {error}'
        )
      )
    } finally {
      hide_context_menu()
    }
  }

  async function handle_library_delete(cm_in) {
    const cm = pick_cm(cm_in)
    const libraryId = cm_target_id(cm)
    const libraryName = cm_target_name(cm) || ''

    if (
      !_confirm(
        t(
          'left.actionDialogs.deleteConfirm',
          { name: libraryName },
          'Delete library {name}? This will permanently delete the library and all documents. This action cannot be undone.'
        )
      )
    ) {
      hide_context_menu()
      return
    }

    try {
      const result = await call_tool(
        'nisb_library_delete',
        _tool_args({ library_id: libraryId })
      )
      const info = normalizeToolResponse(
        result,
        t('left.actionDialogs.deleteSuccessFallback', {}, 'Library deleted successfully')
      )

      if (info.success) {
        _alert(
          t('left.actionDialogs.successPrefix', {}, '✅ ') +
            (info.text || t('left.actionDialogs.deleteSuccessFallback', {}, 'Library deleted successfully'))
        )
        library_list_ref.value?.loadLibraries()
      } else {
        _alert(
          t('left.actionDialogs.deleteFailed', { error: info.text || _unknown_error() }, 'Delete failed: {error}')
        )
      }
    } catch (e) {
      _alert(
        t(
          'left.actionDialogs.deleteFailed',
          { error: e?.message || String(e) },
          'Delete failed: {error}'
        )
      )
    } finally {
      hide_context_menu()
    }
  }

  return {
    handle_library_rename,
    handle_library_info,
    handle_library_delete
  }
}
