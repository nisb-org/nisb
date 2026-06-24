import { nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  create_assistant_message,
  create_user_message,
} from './use_chat_panel_message_writer'

const DEFAULT_ASSISTANT_GREETING_ZH = '你好！我是 NISB 助手。'
const DEFAULT_ASSISTANT_GREETING_EN = 'Hello! I am the NISB assistant.'

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function resolve_default_assistant_greeting(locale_value = '') {
  const token = safe_string(locale_value).trim().toLowerCase()
  return token.startsWith('en') ? DEFAULT_ASSISTANT_GREETING_EN : DEFAULT_ASSISTANT_GREETING_ZH
}

function is_default_assistant_greeting(value) {
  const text = safe_string(value).trim()
  if (!text) return false

  return text === DEFAULT_ASSISTANT_GREETING_ZH || text === DEFAULT_ASSISTANT_GREETING_EN
}

function create_default_messages(greeting = DEFAULT_ASSISTANT_GREETING_ZH) {
  return [
    create_assistant_message({
      id: 'assistant_welcome',
      role: 'assistant',
      content: greeting,
      response: greeting,
      citations: [],
      pending: false,
      tool_calls: [],
      tool_results: [],
    }),
  ]
}

function read_turn_role(turn) {
  return String(
    turn?.role ||
    turn?.turn_type ||
    'user'
  ).trim()
}

function read_turn_text(turn) {
  return String(
    turn?.content ||
    turn?.response ||
    turn?.text ||
    ''
  )
}

function has_meaningful_runtime_messages(messages_ref) {
  const list = Array.isArray(messages_ref?.value) ? messages_ref.value : []

  return list.some((msg) => {
    const role = String(msg?.role || '').trim()
    const text = String(msg?.response || msg?.content || '').trim()

    if (role === 'user' && text) return true

    if (role === 'assistant') {
      if (text && !is_default_assistant_greeting(text)) return true
      if (Array.isArray(msg?.tool_calls) && msg.tool_calls.length > 0) return true
      if (Array.isArray(msg?.tool_results) && msg.tool_results.length > 0) return true
      if (msg?.pending) return true
    }

    return false
  })
}

function has_meaningful_loaded_turns(turns) {
  const list = Array.isArray(turns) ? turns : []

  return list.some((turn) => {
    const role = read_turn_role(turn)
    const text = read_turn_text(turn).trim()

    if (role === 'user' && text) return true
    if (role === 'assistant' && text) return true

    return false
  })
}

export function use_chat_panel_llm_conversation_lane({
  call_tool,
  messages,
  internal_conv_id,
  scroll_to_bottom,
  emit_chat_outline_update,
  enhance_chat_dom,
}) {
  const { locale } = useI18n({ useScope: 'global' })
  const defaultAssistantGreeting = computed(() =>
    resolve_default_assistant_greeting(locale.value)
  )

  async function loadConversation(convId) {
    if (!convId) return

    try {
      const result = await call_tool('nisb_chat_load', { conv_id: convId })

      if (result.status !== 'success') return

      const turns = Array.isArray(result.turns) ? result.turns : []
      const runtime_has_content = has_meaningful_runtime_messages(messages)
      const loaded_has_content = has_meaningful_loaded_turns(turns)

      console.debug('[chat-load] result-status', result?.status)
      console.debug('[chat-load] conv-id', convId)
      console.debug('[chat-load] turns-length', turns.length)
      console.debug('[chat-load] runtime-has-content', runtime_has_content)
      console.debug('[chat-load] loaded-has-content', loaded_has_content)
      console.debug('[chat-load] first-turn', turns[0])

      if (runtime_has_content && !loaded_has_content) {
        internal_conv_id.value = convId
        localStorage.setItem('nisb_last_conv_id', String(convId))
        return
      }

      if (!loaded_has_content) {
        messages.value = create_default_messages(defaultAssistantGreeting.value)
        internal_conv_id.value = convId
        localStorage.setItem('nisb_last_conv_id', String(convId))

        nextTick(() => {
          scroll_to_bottom()
          emit_chat_outline_update()
          enhance_chat_dom()
        })
        return
      }

      const next_messages = []

      for (const turn of turns) {
        const role = read_turn_role(turn)
        const text = read_turn_text(turn)

        if (role === 'assistant') {
          next_messages.push(
            create_assistant_message({
              id: turn.id,
              role: 'assistant',
              content: text,
              response: text,
              citations: Array.isArray(turn?.citations) ? turn.citations : [],
              pending: false,
              tool_calls: Array.isArray(turn?.tool_calls) ? turn.tool_calls : [],
              tool_results: Array.isArray(turn?.tool_results) ? turn.tool_results : [],
            })
          )
          continue
        }

        next_messages.push(
          create_user_message({
            id: turn.id,
            role,
            content: text,
            response: text,
            citations: Array.isArray(turn?.citations) ? turn.citations : [],
            pending: false,
          })
        )
      }

      console.debug('[chat-load] next-messages-length-before-write', next_messages.length)
      console.debug('[chat-load] first-next-message', next_messages[0])

      messages.value = next_messages

      console.debug('[chat-load] messages-length-after-write', messages.value.length)
      console.debug('[chat-load] first-message-after-write', messages.value[0])

      internal_conv_id.value = convId
      localStorage.setItem('nisb_last_conv_id', String(convId))

      setTimeout(() => {
        console.debug('[chat-load] messages-length-after-300ms', messages.value.length)
        console.debug('[chat-load] first-message-after-300ms', messages.value[0])
      }, 300)

      nextTick(() => {
        scroll_to_bottom()
        emit_chat_outline_update()
        enhance_chat_dom()
      })
    } catch (e) {
      console.error('加载对话失败:', e)
    }
  }

  return { loadConversation }
}

export default use_chat_panel_llm_conversation_lane

