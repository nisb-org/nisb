import { watch } from 'vue'

// ====== Query translate switch (from SettingsModal.vue) ======
const LS_QUERY_TRANSLATE_ENABLED = 'nisb_chat_query_translate_enabled'
const LS_QUERY_TRANSLATE_MODEL = 'nisb_chat_query_translate_model'

// ====== translate sticky intent (auto-disable + auto-restore) ======
const LS_QUERY_TRANSLATE_STICKY_INTENT = 'nisb_chat_query_translate_sticky_intent' // 'true'/'false'
const LS_QUERY_TRANSLATE_AUTO_DISABLED = 'nisb_chat_query_translate_auto_disabled' // 'true'/'false'

export function use_chat_panel_translation_gate({ chat_cfg, selected_attachments }) {
  function get_query_translate_enabled() {
    const v =
      (chat_cfg && chat_cfg.chat && typeof chat_cfg.chat.queryTranslateEnabled === 'boolean')
        ? chat_cfg.chat.queryTranslateEnabled
        : (localStorage.getItem(LS_QUERY_TRANSLATE_ENABLED) === 'true')
    return !!v
  }

  function get_query_translate_model() {
    const v =
      (chat_cfg && chat_cfg.chat && chat_cfg.chat.queryTranslateModel)
        ? String(chat_cfg.chat.queryTranslateModel || '').trim()
        : String(localStorage.getItem(LS_QUERY_TRANSLATE_MODEL) || '').trim()
    return v || 'gpt-4o-mini'
  }

  function set_query_translate_enabled(val) {
    const on = !!val
    localStorage.setItem(LS_QUERY_TRANSLATE_ENABLED, String(on))
    if (typeof chat_cfg?.setQueryTranslateEnabled === 'function') {
      chat_cfg.setQueryTranslateEnabled(on)
    }
  }

  function get_query_translate_sticky_intent() {
    const v = localStorage.getItem(LS_QUERY_TRANSLATE_STICKY_INTENT)
    if (v === null) return null
    return v === 'true'
  }

  function set_query_translate_sticky_intent(val) {
    if (val === null || typeof val === 'undefined') {
      localStorage.removeItem(LS_QUERY_TRANSLATE_STICKY_INTENT)
      return
    }
    localStorage.setItem(LS_QUERY_TRANSLATE_STICKY_INTENT, String(!!val))
  }

  function get_query_translate_auto_disabled() {
    return localStorage.getItem(LS_QUERY_TRANSLATE_AUTO_DISABLED) === 'true'
  }

  function set_query_translate_auto_disabled(val) {
    localStorage.setItem(LS_QUERY_TRANSLATE_AUTO_DISABLED, String(!!val))
  }

  // ✅ 附件：自动关闭翻译；附件清空后按用户意图自动恢复（保持原行为）
  watch(
    () => selected_attachments.value.length,
    (n, prev_n) => {
      if (n > 0 && get_query_translate_enabled()) {
        set_query_translate_sticky_intent(true)
        set_query_translate_auto_disabled(true)
        set_query_translate_enabled(false)
        // eslint-disable-next-line no-console
        console.log('[TRANSLATE_GATE] attachments selected -> auto disable translate (will restore when attachments cleared)')
        return
      }

      if (prev_n > 0 && n === 0) {
        const auto_disabled = get_query_translate_auto_disabled()
        const sticky = get_query_translate_sticky_intent()

        if (auto_disabled && sticky === true) {
          set_query_translate_enabled(true)
          // eslint-disable-next-line no-console
          console.log('[TRANSLATE_GATE] attachments cleared -> restore translate switch (sticky_intent=true)')
        }

        if (auto_disabled) set_query_translate_auto_disabled(false)
      }
    }
  )

  return {
    LS_QUERY_TRANSLATE_ENABLED,
    LS_QUERY_TRANSLATE_MODEL,
    LS_QUERY_TRANSLATE_STICKY_INTENT,
    LS_QUERY_TRANSLATE_AUTO_DISABLED,

    get_query_translate_enabled,
    get_query_translate_model,
    set_query_translate_enabled,
    get_query_translate_sticky_intent,
    set_query_translate_sticky_intent,
    get_query_translate_auto_disabled,
    set_query_translate_auto_disabled,
  }
}

