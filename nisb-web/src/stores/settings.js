import { defineStore } from 'pinia'

const LS_KEY = 'nisb_settings_v2'

export const DEFAULT_LOCALE = 'en'
export const SUPPORTED_LOCALES = ['en', 'zh-CN']

let remoteLocaleSaver = null

export function normalizeLocale(input) {
  const raw = String(input || '').trim()
  if (!raw) return DEFAULT_LOCALE

  const lowered = raw.toLowerCase()

  if (
    lowered === 'zh' ||
    lowered === 'zh-cn' ||
    lowered === 'zh_cn' ||
    lowered === 'zh-hans' ||
    lowered === 'zh_hans'
  ) {
    return 'zh-CN'
  }

  if (
    lowered === 'en' ||
    lowered === 'en-us' ||
    lowered === 'en_us' ||
    lowered === 'en-gb' ||
    lowered === 'en_gb'
  ) {
    return 'en'
  }

  return SUPPORTED_LOCALES.includes(raw) ? raw : DEFAULT_LOCALE
}

function _loadSettings() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return {}
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : {}
  } catch (e) {
    return {}
  }
}

function _saveSettings(obj) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj))
  } catch (e) {}
}

function _hasExplicitLocale(saved) {
  return saved?.localeExplicit === true
}

function _initialLocale(saved) {
  return _hasExplicitLocale(saved) ? normalizeLocale(saved.locale) : DEFAULT_LOCALE
}

function _hasToken() {
  try {
    return !!String(
      localStorage.getItem('nisb_token') ||
        localStorage.getItem('nisb-token') ||
        localStorage.getItem('nisb_access_token') ||
        localStorage.getItem('access_token') ||
        localStorage.getItem('token') ||
        localStorage.getItem('Authorization') ||
        ''
    ).trim()
  } catch {
    return false
  }
}

function _extractPreferences(res) {
  const root = res && typeof res === 'object' ? res : {}
  const prefs =
    root.preferences ||
    root.data?.preferences ||
    root.result?.preferences ||
    root.payload?.preferences ||
    null

  if (prefs && typeof prefs === 'object') return prefs

  if (Object.prototype.hasOwnProperty.call(root, 'locale')) {
    return {
      locale: root.locale,
      localeExplicit: root.localeExplicit ?? root.locale_explicit
    }
  }

  return null
}

export const useSettingsStore = defineStore('settings', {
  state: () => {
    const saved = _loadSettings()
    const localeExplicit = _hasExplicitLocale(saved)

    return {
      locale: _initialLocale(saved),
      localeExplicit,

      indexUseMiniForced: !!saved.indexUseMiniForced,
      libraryAutoPretranslate: !!saved.libraryAutoPretranslate,

      rightShowLibraryInsights:
        saved.rightShowLibraryInsights === undefined ? true : !!saved.rightShowLibraryInsights,

      outlineGenerateUseMini: !!saved.outlineGenerateUseMini,
      outlineExpandUseMini: !!saved.outlineExpandUseMini,
      outlineShowZhTitle: saved.outlineShowZhTitle === undefined ? true : !!saved.outlineShowZhTitle
    }
  },

  actions: {
    _persist() {
      _saveSettings({
        locale: this.locale,
        localeExplicit: this.localeExplicit === true,
        indexUseMiniForced: this.indexUseMiniForced,
        libraryAutoPretranslate: this.libraryAutoPretranslate,
        rightShowLibraryInsights: this.rightShowLibraryInsights,
        outlineGenerateUseMini: this.outlineGenerateUseMini,
        outlineExpandUseMini: this.outlineExpandUseMini,
        outlineShowZhTitle: this.outlineShowZhTitle
      })
    },

    setRemoteLocaleSaver(fn) {
      remoteLocaleSaver = typeof fn === 'function' ? fn : null
    },

    applyRemoteLocalePreference(payload = {}) {
      const explicit = payload?.localeExplicit === true || payload?.locale_explicit === true
      if (!explicit) return false

      const next = normalizeLocale(payload?.locale)
      this.locale = next
      this.localeExplicit = true
      this._persist()
      return true
    },

    async hydrateRemoteLocalePreference(callTool) {
      if (typeof callTool !== 'function') return false
      if (!_hasToken()) return false

      try {
        const res = await callTool('nisb_user_preferences_get', {})
        const prefs = _extractPreferences(res)
        if (!prefs) return false
        return this.applyRemoteLocalePreference(prefs)
      } catch (e) {
        return false
      }
    },

    async syncRemoteLocalePreference() {
      if (typeof remoteLocaleSaver !== 'function') return false
      if (!_hasToken()) return false

      try {
        await remoteLocaleSaver({
          locale: this.locale,
          localeExplicit: this.localeExplicit === true
        })
        return true
      } catch (e) {
        return false
      }
    },

    setLocale(val) {
      const next = normalizeLocale(val)
      const changed = this.locale !== next || this.localeExplicit !== true

      this.locale = next
      this.localeExplicit = true

      if (changed) {
        this._persist()
      }

      void this.syncRemoteLocalePreference()
    },

    setIndexUseMiniForced(val) {
      this.indexUseMiniForced = !!val
      this._persist()
    },

    setLibraryAutoPretranslate(val) {
      this.libraryAutoPretranslate = !!val
      this._persist()
    },

    setRightShowLibraryInsights(val) {
      this.rightShowLibraryInsights = !!val
      this._persist()
    },

    setOutlineGenerateUseMini(val) {
      this.outlineGenerateUseMini = !!val
      this._persist()
    },

    setOutlineExpandUseMini(val) {
      this.outlineExpandUseMini = !!val
      this._persist()
    },

    setOutlineShowZhTitle(val) {
      this.outlineShowZhTitle = !!val
      this._persist()
    }
  }
})
