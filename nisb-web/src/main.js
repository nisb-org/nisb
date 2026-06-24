// src/main.js

import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useChatConfigStore } from './stores/chatConfig'
import { useSettingsStore } from './stores/settings'
import { useMCP } from './composables/useMCP'
import { createNisbI18n, applyI18nLocale } from './i18n'

import './assets/themes/zen.css'

function hasAuthToken() {
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

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const settings = useSettingsStore()
const chatCfg = useChatConfigStore()
const { callTool } = useMCP()

settings.setRemoteLocaleSaver(async (payload) => {
  return await callTool('nisb_user_preferences_set', payload)
})

if (typeof chatCfg.hydrate === 'function') {
  chatCfg.hydrate()
}

const i18n = createNisbI18n(settings.locale)
app.use(i18n)
applyI18nLocale(i18n, settings.locale)

watch(
  () => settings.locale,
  (next) => {
    applyI18nLocale(i18n, next)
  }
)

if (hasAuthToken()) {
  void settings.hydrateRemoteLocalePreference(callTool)
}

app.use(router)
app.mount('#app')
