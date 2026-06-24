import { unref } from 'vue'
import enLibrary from '../../locales/en/library'
import zhCNLibrary from '../../locales/zh-CN/library'

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

function format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function deep_get(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      if (typeof localStorage === 'undefined') continue
      const value = localStorage.getItem(key)
      if (value !== null && string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function runtime_locale() {
  const from_window = (() => {
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

  const from_storage = local_storage_first(
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

  const from_document = (() => {
    try {
      if (typeof document === 'undefined') return ''
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  const from_navigator = (() => {
    try {
      if (typeof navigator === 'undefined') return ''
      return navigator?.language || ''
    } catch {
      return ''
    }
  })()

  return normalize_locale(from_window || from_storage || from_document || from_navigator || 'en')
}

export function use_library_detail_runtime({
  library_id_ref,
  load_library_info,
  load_documents,
  locale_ref = null,
  t: external_t = null
}) {
  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function current_locale() {
    return normalize_locale(unref(locale_ref) || runtime_locale())
  }

  function text(path, params = {}, fallback = '') {
    if (typeof external_t === 'function') {
      try {
        const value = external_t(path, params, fallback)
        if (string_value(value) && value !== path) return value
      } catch {}
    }

    const locale = current_locale()
    const messages = LIBRARY_LOCALES[locale] || LIBRARY_LOCALES.en
    const value = deep_get(messages, path, deep_get(LIBRARY_LOCALES.en, path, fallback))
    return format_text(value || fallback || path, params)
  }

  function alert_message(message) {
    try {
      alert(message)
    } catch {}
  }

  function ensure_library_id() {
    const id = get_library_id()
    if (!id) {
      alert_message(
        text(
          'center.detailRuntime.missingLibraryId',
          {},
          'Library id is empty. Return to the library list and reopen this library.'
        )
      )
      return false
    }
    return true
  }

  function dispatch_timeline_refresh() {
    try {
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } catch {}
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  async function refresh_after_mutation(opts = {}) {
    const { retryDocs = 1, retryDelayMs = 250 } = opts || {}
    await load_library_info()
    await load_documents()
    for (let i = 0; i < Number(retryDocs || 0); i += 1) {
      await sleep(retryDelayMs)
      await load_documents()
    }
    dispatch_timeline_refresh()
  }

  return {
    ensure_library_id,
    dispatch_timeline_refresh,
    sleep,
    refresh_after_mutation
  }
}
