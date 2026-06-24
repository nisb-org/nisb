import { is_non_english } from './chat_panel_utils'

export function use_chat_panel_translator({ call_tool, get_query_translate_model }) {
  async function translate_to_english(text) {
    const raw = String(text || '').trim()
    if (!raw) return ''

    try {
      const result = await call_tool(
        'nisb_llm_call',
        {
          model: get_query_translate_model(),
          system_prompt:
            'You are a query translator for search and Q&A systems.\n' +
            "Translate the user's query into English.\n" +
            'Rules:\n' +
            '- Keep named entities (people, places, organizations)\n' +
            '- Use natural English, not word-by-word translation\n' +
            '- Do NOT add explanations\n' +
            '- Output English only',
          user_prompt: raw,
          max_tokens: 200,
          temperature: 0.2,
        },
        { timeout_ms: 30000, retry: 1 }
      )

      const translated = String(result?.response || '').trim()
      if (!translated || translated.length < 3 || is_non_english(translated)) {
        // eslint-disable-next-line no-console
        console.warn('[TRANSLATE] Translation invalid, fallback to original.')
        return ''
      }

      // eslint-disable-next-line no-console
      console.log(`[TRANSLATE] "${raw}" → "${translated}"`)
      return translated
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[TRANSLATE] Error:', e)
      return ''
    }
  }

  async function translate_to_original_lang(text, target_lang) {
    const raw = String(text || '').trim()
    const lang = String(target_lang || '').trim().toLowerCase()
    if (!raw) return raw
    if (!lang || lang === 'en') return raw

    const lang_map = { zh: 'Chinese', ja: 'Japanese', ko: 'Korean', ar: 'Arabic', ru: 'Russian' }
    const target_name = lang_map[lang] || lang

    try {
      const result = await call_tool(
        'nisb_llm_call',
        {
          model: 'gpt-4o-mini',
          system_prompt:
            `You are a translator.\n` +
            `Translate the assistant's response into ${target_name}.\n` +
            `Keep markdown formatting, citations, and technical terms.\n` +
            `Output ${target_name} only.`,
          user_prompt: raw,
          max_tokens: 3000,
          temperature: 0.2,
        },
        { timeout_ms: 30000, retry: 1 }
      )

      const translated = String(result?.response || '').trim()
      return translated || raw
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[TRANSLATE_BACK] Error:', e)
      return raw
    }
  }

  return { translate_to_english, translate_to_original_lang }
}

