import { getCurrentInstance } from 'vue'

function normalizeLocale(input, defaultLocale = 'zh-CN') {
  const raw = String(input || '').trim().toLowerCase()
  if (!raw) return defaultLocale
  if (raw === 'zh' || raw === 'zh-cn' || raw === 'zh_hans') return 'zh-CN'
  if (raw === 'en' || raw === 'en-us' || raw === 'en_us') return 'en'
  return raw === 'en' ? 'en' : defaultLocale
}

function deepPick(obj, key) {
  const parts = String(key || '').split('.').filter(Boolean)
  let cur = obj
  for (const p of parts) {
    if (!cur || typeof cur !== 'object' || !(p in cur)) return ''
    cur = cur[p]
  }
  return typeof cur === 'string' ? cur : ''
}

function interpolate(template, params = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, name) => {
    const value = params?.[name]
    return value === undefined || value === null ? '' : String(value)
  })
}

export function useDynamicModalI18n({
  fallbackMessages = {},
  defaultLocale = 'zh-CN'
} = {}) {
  const vm = getCurrentInstance()

  function detectLocale() {
    try {
      const gp = vm?.appContext?.config?.globalProperties
      const i18nLocale = gp?.$i18n?.locale
      if (typeof i18nLocale === 'string') {
        return normalizeLocale(i18nLocale, defaultLocale)
      }
      if (i18nLocale && typeof i18nLocale === 'object' && 'value' in i18nLocale) {
        return normalizeLocale(i18nLocale.value, defaultLocale)
      }
    } catch {}

    try {
      const lang = document?.documentElement?.getAttribute?.('lang')
      return normalizeLocale(lang, defaultLocale)
    } catch {}

    return defaultLocale
  }

  function translateByRuntime(key, params = {}) {
    try {
      const gp = vm?.appContext?.config?.globalProperties
      const maybeT = gp?.$t
      if (typeof maybeT !== 'function') return ''

      const result = maybeT(key, params)
      if (typeof result === 'string' && result && result !== key) {
        return result
      }
    } catch {}

    return ''
  }

  function translateByFallback(key, params = {}) {
    const locale = detectLocale()
    const raw =
      deepPick(fallbackMessages?.[locale], key) ||
      deepPick(fallbackMessages?.[defaultLocale], key) ||
      key

    return interpolate(raw, params)
  }

  function t(key, params = {}) {
    return translateByRuntime(key, params) || translateByFallback(key, params)
  }

  return {
    t,
    detectLocale
  }
}

export default useDynamicModalI18n
