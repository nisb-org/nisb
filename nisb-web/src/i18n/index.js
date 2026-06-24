import { createI18n } from 'vue-i18n'
import zhCN from '../locales/zh-CN'
import en from '../locales/en'
import { normalizeLocale } from '../stores/settings'

export const UI_DEFAULT_LOCALE = 'en'

const messages = {
  en,
  'zh-CN': zhCN
}

function normalizeUiLocale(locale) {
  return normalizeLocale(locale || UI_DEFAULT_LOCALE)
}

export function createNisbI18n(initialLocale = UI_DEFAULT_LOCALE) {
  const locale = normalizeUiLocale(initialLocale)

  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: UI_DEFAULT_LOCALE,
    messages,
    missingWarn: false,
    fallbackWarn: false
  })
}

export function applyI18nLocale(i18n, locale) {
  const next = normalizeUiLocale(locale)

  if (i18n?.global?.locale) {
    i18n.global.locale.value = next
  }

  try {
    document.documentElement.setAttribute('lang', next)
  } catch {}

  return next
}
