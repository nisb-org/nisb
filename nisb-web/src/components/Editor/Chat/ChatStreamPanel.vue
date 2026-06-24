<template>
  <div class="chat_stream_panel">
    <div class="chat_toolbar">
      <div class="toolbar_left">
        <label class="field field_model">
          <span>模型</span>
          <input v-model.trim="model" class="input" placeholder="gpt-4o-mini / claude-3-5-sonnet" />
        </label>

        <label class="field field_mode">
          <span>模式</span>
          <select v-model="rag_mode" class="input">
            <option value="off">off</option>
            <option value="web">web</option>
            <option value="auto">auto</option>
            <option value="cite">cite</option>
            <option value="ground">ground</option>
          </select>
        </label>
      </div>

      <div class="toolbar_right">
        <button class="btn btn_secondary" @click="clear_chat">清空</button>
        <button class="btn btn_danger" :disabled="!current_dedupe_key || !isStreaming" @click="cancel_stream">
          停止
        </button>
      </div>
    </div>

    <div ref="list_ref" class="chat_list">
      <div
        v-for="item in messages"
        :key="item.local_id"
        class="chat_item"
        :class="item.role === 'user' ? 'chat_item_user' : 'chat_item_assistant'"
      >
        <div class="chat_bubble">
          <div class="chat_meta">
            <span class="role">{{ item.role === 'user' ? '你' : '助手' }}</span>
            <span v-if="item.mode_used" class="mode">{{ item.mode_used }}</span>
            <span class="status" :class="status_class(item)">{{ status_text(item) }}</span>
          </div>

          <pre class="chat_content">{{ item.response || item.content }}</pre>

          <div
            v-if="item.role === 'assistant' && item.message && item.message !== (item.response || item.content)"
            class="message_box"
          >
            <div class="evidence_title">message</div>
            <pre class="evidence_pre">{{ item.message }}</pre>
          </div>

          <div v-if="item.role === 'assistant' && has_evidence(item)" class="evidence_box">
            <div v-if="item.citations?.length" class="evidence_block">
              <div class="evidence_title">citations</div>
              <pre class="evidence_pre">{{ format_json(item.citations) }}</pre>
            </div>

            <div v-if="item.rss_evidence?.length" class="evidence_block">
              <div class="evidence_title">rss_evidence</div>
              <pre class="evidence_pre">{{ format_json(item.rss_evidence) }}</pre>
            </div>

            <div v-if="item.market_evidence?.length" class="evidence_block">
              <div class="evidence_title">market_evidence</div>
              <pre class="evidence_pre">{{ format_json(item.market_evidence) }}</pre>
            </div>

            <div v-if="item.evidence_query" class="evidence_block">
              <div class="evidence_title">evidence_query</div>
              <pre class="evidence_pre">{{ item.evidence_query }}</pre>
            </div>

            <div v-if="item.evidence_tools?.length" class="evidence_block">
              <div class="evidence_title">evidence_tools</div>
              <pre class="evidence_pre">{{ format_json(item.evidence_tools) }}</pre>
            </div>

            <div v-if="item.tool_calls?.length" class="evidence_block">
              <div class="evidence_title">tool_calls</div>
              <pre class="evidence_pre">{{ format_json(item.tool_calls) }}</pre>
            </div>

            <div v-if="item.tool_results?.length" class="evidence_block">
              <div class="evidence_title">tool_results</div>
              <pre class="evidence_pre">{{ format_json(item.tool_results) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat_input_bar">
      <div class="input_meta_bar">
        <div class="meta_chips">
          <span class="meta_chip">rag: {{ rag_mode || 'off' }}</span>
          <span class="meta_chip" :class="{ active: !!conv_id }">conv_id</span>
        </div>
        <div class="conv_info">
          <span>conv_id：</span>
          <code>{{ conv_id || '-' }}</code>
        </div>
      </div>

      <div class="input_row">
        <textarea
          v-model="input_text"
          class="textarea"
          rows="4"
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          @keydown="on_keydown"
        />

        <button class="btn btn_primary send_btn" :disabled="sending_disabled" @click="send_message">
          {{ isStreaming ? '发送中...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import useMCP from '@/composables/useMCP'

const { callTool, callToolStream, cancelByDedupeKey, isStreaming } = useMCP()

const model = ref(localStorage.getItem('nisb_chat_model') || 'gpt-4o-mini')
const rag_mode = ref(localStorage.getItem('nisb_chat_rag_mode') || 'off')
const input_text = ref('')
const conv_id = ref(localStorage.getItem('nisb_chat_conv_id') || '')
const list_ref = ref(null)

const messages = ref([])
const current_dedupe_key = ref('')
const current_stream_local_id = ref('')
const current_final_received = ref(false)
const is_loading_history = ref(false)

const sending_disabled = computed(() => !input_text.value.trim() || isStreaming.value)

function make_local_id(prefix = 'msg') {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function safe_object(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function safe_array(v) {
  return Array.isArray(v) ? v : []
}

function normalize_text(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalize_status_token(value) {
  const s = normalize_text(value).trim().toLowerCase()
  if (!s) return ''
  if (['ok', 'success', 'succeeded'].includes(s)) return 'success'
  if (['warning', 'partial_success', 'partial_error'].includes(s)) return 'warning'
  if (['error', 'failed', 'fail'].includes(s)) return 'error'
  return s
}

function extract_tool_results(root) {
  const src = safe_object(root)
  const sources = [
    src.tool_results,
    src.data?.tool_results,
    src.result?.tool_results,
    src.payload?.tool_results,
  ]

  for (const rows of sources) {
    if (Array.isArray(rows)) return rows
  }

  return []
}

function pick_primary_payload(res) {
  const root = safe_object(res)
  const candidates = [
    safe_object(root.data),
    safe_object(root.result),
    safe_object(root.payload),
    root,
  ]

  for (const obj of candidates) {
    if (
      Object.keys(obj).length > 0 &&
      (
        obj.status !== undefined ||
        obj.response !== undefined ||
        obj.content !== undefined ||
        obj.message !== undefined ||
        obj.conv_id !== undefined ||
        obj.turns !== undefined ||
        obj.tool_results !== undefined
      )
    ) {
      return obj
    }
  }

  for (const obj of candidates) {
    if (Object.keys(obj).length > 0) return obj
  }

  return {}
}

function get_explicit_status(res) {
  const root = safe_object(res)
  const candidates = [
    root.status,
    root.data?.status,
    root.result?.status,
    root.payload?.status,
  ]

  for (const item of candidates) {
    const s = normalize_status_token(item)
    if (['success', 'warning', 'error'].includes(s)) return s
  }

  return ''
}

function normalize_formal_body(payload, fallback = '') {
  const src = safe_object(payload)
  const candidates = [
    src.response,
    src.content,
    src.message,
    src.text,
  ]

  for (const item of candidates) {
    const s = normalize_text(item)
    if (s) return s
  }

  return normalize_text(fallback)
}

function normalize_formal_message(payload, fallback = '') {
  const src = safe_object(payload)
  const candidates = [
    src.message,
    src.response,
    src.content,
    src.text,
  ]

  for (const item of candidates) {
    const s = normalize_text(item)
    if (s) return s
  }

  return normalize_text(fallback)
}

function create_message_item(role, overrides = {}) {
  const response = normalize_formal_body(overrides, '')
  return {
    local_id: String(overrides.local_id || make_local_id(role)),
    role: String(role || 'assistant'),
    content: response,
    response,
    streaming: !!overrides.streaming,
    error_text: normalize_text(overrides.error_text || ''),
    status: normalize_status_token(overrides.status || '') || '',
    message: normalize_formal_message(overrides, ''),
    mode_used: normalize_text(overrides.mode_used || ''),
    citations: Array.isArray(overrides.citations) ? overrides.citations : [],
    rss_evidence: Array.isArray(overrides.rss_evidence) ? overrides.rss_evidence : [],
    market_evidence: Array.isArray(overrides.market_evidence) ? overrides.market_evidence : [],
    evidence_query: normalize_text(overrides.evidence_query || ''),
    evidence_tools: Array.isArray(overrides.evidence_tools) ? overrides.evidence_tools : [],
    evidence_result:
      overrides.evidence_result && typeof overrides.evidence_result === 'object'
        ? overrides.evidence_result
        : {},
    tool_calls: Array.isArray(overrides.tool_calls) ? overrides.tool_calls : [],
    tool_results: Array.isArray(overrides.tool_results) ? overrides.tool_results : [],
    request_id: normalize_text(overrides.request_id || ''),
    conv_id: normalize_text(overrides.conv_id || ''),
    qa_id: normalize_text(overrides.qa_id || ''),
    group_id: normalize_text(overrides.group_id || ''),
  }
}

function scroll_to_bottom() {
  nextTick(() => {
    const el = list_ref.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

function format_json(v) {
  try {
    return JSON.stringify(v ?? null, null, 2)
  } catch {
    return String(v ?? '')
  }
}

function has_evidence(item) {
  return Boolean(
    (Array.isArray(item.citations) && item.citations.length > 0) ||
    (Array.isArray(item.rss_evidence) && item.rss_evidence.length > 0) ||
    (Array.isArray(item.market_evidence) && item.market_evidence.length > 0) ||
    item.evidence_query ||
    (Array.isArray(item.evidence_tools) && item.evidence_tools.length > 0) ||
    (Array.isArray(item.tool_calls) && item.tool_calls.length > 0) ||
    (Array.isArray(item.tool_results) && item.tool_results.length > 0)
  )
}

function status_text(item) {
  if (item.streaming) return '流式中'
  const status = normalize_status_token(item.status || '')
  if (item.error_text || status === 'error') return '失败'
  if (status === 'warning') return '警告'
  return '完成'
}

function status_class(item) {
  if (item.streaming) return 'status_streaming'
  const status = normalize_status_token(item.status || '')
  if (item.error_text || status === 'error') return 'status_error'
  if (status === 'warning') return 'status_warning'
  return ''
}

function persist_preferences() {
  localStorage.setItem('nisb_chat_model', model.value)
  localStorage.setItem('nisb_chat_rag_mode', rag_mode.value)
  if (conv_id.value) {
    localStorage.setItem('nisb_chat_conv_id', conv_id.value)
  } else {
    localStorage.removeItem('nisb_chat_conv_id')
  }
}

function clear_runtime_handles() {
  current_dedupe_key.value = ''
  current_stream_local_id.value = ''
  current_final_received.value = false
}

function clear_chat() {
  messages.value = []
  conv_id.value = ''
  persist_preferences()
  clear_runtime_handles()
}

function append_message(message) {
  messages.value = [...messages.value, create_message_item(message.role, message)]
  return messages.value[messages.value.length - 1] || null
}

function find_message_index_by_local_id(local_id) {
  return messages.value.findIndex((x) => String(x?.local_id || '') === String(local_id || ''))
}

function find_current_assistant() {
  if (!current_stream_local_id.value) return null
  const idx = find_message_index_by_local_id(current_stream_local_id.value)
  return idx >= 0 ? messages.value[idx] : null
}

function patch_message(local_id, patch_or_fn = {}) {
  const idx = find_message_index_by_local_id(local_id)
  if (idx < 0) return null

  const current = messages.value[idx]
  const patch =
    typeof patch_or_fn === 'function'
      ? patch_or_fn(current)
      : patch_or_fn

  const next = {
    ...current,
    ...(patch || {}),
  }

  if ('response' in next && !('content' in (patch || {}))) {
    next.content = normalize_text(next.response || '')
  }
  if ('content' in next && !('response' in (patch || {}))) {
    next.response = normalize_text(next.content || '')
  }

  const list = [...messages.value]
  list[idx] = next
  messages.value = list
  return next
}

function ensure_current_assistant() {
  const existing = find_current_assistant()
  if (existing) return existing

  const local_id = make_local_id('assistant')
  const item = create_message_item('assistant', {
    local_id,
    streaming: true,
    conv_id: conv_id.value,
    status: '',
  })

  messages.value = [...messages.value, item]
  current_stream_local_id.value = local_id
  return item
}

function on_keydown(e) {
  if (e.key !== 'Enter') return
  if (e.shiftKey) return
  e.preventDefault()
  if (!sending_disabled.value) send_message()
}

function map_turn_to_message(turn = {}) {
  const role = String(turn.role || turn.turn_type || 'assistant').trim() || 'assistant'
  const payload = safe_object(turn)
  const body = normalize_formal_body(payload, '')
  return create_message_item(role, {
    local_id: make_local_id(role),
    response: body,
    content: body,
    streaming: false,
    error_text: '',
    status: normalize_status_token(payload.status || '') || 'success',
    message: normalize_formal_message(payload, ''),
    mode_used: normalize_text(payload.mode_used || ''),
    citations: Array.isArray(payload.citations) ? payload.citations : [],
    rss_evidence: Array.isArray(payload.rss_evidence) ? payload.rss_evidence : [],
    market_evidence: Array.isArray(payload.market_evidence) ? payload.market_evidence : [],
    evidence_query: normalize_text(payload.evidence_query || ''),
    evidence_tools: Array.isArray(payload.evidence_tools) ? payload.evidence_tools : [],
    evidence_result:
      payload.evidence_result && typeof payload.evidence_result === 'object'
        ? payload.evidence_result
        : {},
    tool_calls: Array.isArray(payload.tool_calls) ? payload.tool_calls : [],
    tool_results: Array.isArray(payload.tool_results) ? payload.tool_results : [],
    conv_id: conv_id.value,
    request_id: normalize_text(payload.request_id || ''),
    qa_id: normalize_text(payload.qa_id || ''),
    group_id: normalize_text(payload.group_id || ''),
  })
}

async function load_conversation(target_conv_id) {
  const next_conv_id = String(target_conv_id || '').trim()
  if (!next_conv_id || isStreaming.value) return

  is_loading_history.value = true
  try {
    const result = await callTool('nisb_chat_load', { conv_id: next_conv_id })
    const payload = pick_primary_payload(result)
    const explicit_status = get_explicit_status(result) || get_explicit_status(payload)

    if (explicit_status && !['success', 'warning'].includes(explicit_status)) return

    const turns = Array.isArray(payload?.turns) ? payload.turns : []
    messages.value = turns
      .filter((turn) => {
        const role = String(turn?.role || turn?.turn_type || '').trim()
        return role === 'user' || role === 'assistant'
      })
      .map((turn) => map_turn_to_message(turn))

    conv_id.value = String(payload?.conv_id || next_conv_id || '')
    persist_preferences()
    clear_runtime_handles()
    scroll_to_bottom()
  } catch (e) {
    console.error('加载对话失败:', e)
  } finally {
    is_loading_history.value = false
  }
}

function apply_common_payload(local_id, payload = {}) {
  const packet = pick_primary_payload(payload)
  const next_conv_id = String(packet.conv_id || '').trim()
  const next_request_id = String(packet.request_id || '').trim()
  const next_mode_used = String(packet.mode_used || '').trim()
  const next_status = get_explicit_status(packet)
  const next_message = normalize_formal_message(packet, '')

  patch_message(local_id, (current) => ({
    request_id: next_request_id || current.request_id || '',
    conv_id: next_conv_id || current.conv_id || '',
    mode_used: next_mode_used || current.mode_used || '',
    status: next_status || current.status || '',
    message: next_message || current.message || '',
  }))

  if (next_conv_id) {
    conv_id.value = next_conv_id
    persist_preferences()
  }
}

function apply_final_payload(local_id, payload = {}) {
  const packet = pick_primary_payload(payload)

  patch_message(local_id, (current) => {
    const final_text = normalize_formal_body(packet, current.response || current.content || '')
    const final_status = get_explicit_status(packet) || current.status || 'success'
    const final_message = normalize_formal_message(packet, current.message || '')

    return {
      streaming: false,
      error_text: final_status === 'error' ? (final_message || current.error_text || '') : '',
      status: final_status,
      message: final_message,
      request_id: String(packet.request_id || current.request_id || ''),
      conv_id: String(packet.conv_id || current.conv_id || ''),
      mode_used: String(packet.mode_used || current.mode_used || ''),
      citations: Array.isArray(packet.citations) ? packet.citations : current.citations,
      rss_evidence: Array.isArray(packet.rss_evidence) ? packet.rss_evidence : current.rss_evidence,
      market_evidence: Array.isArray(packet.market_evidence)
        ? packet.market_evidence
        : current.market_evidence,
      evidence_query: String(packet.evidence_query || current.evidence_query || ''),
      evidence_tools: Array.isArray(packet.evidence_tools)
        ? packet.evidence_tools
        : current.evidence_tools,
      evidence_result:
        packet.evidence_result && typeof packet.evidence_result === 'object'
          ? packet.evidence_result
          : current.evidence_result,
      tool_calls: Array.isArray(packet.tool_calls) ? packet.tool_calls : current.tool_calls,
      tool_results: Array.isArray(packet.tool_results) ? packet.tool_results : current.tool_results,
      qa_id: String(packet.qa_id || current.qa_id || ''),
      group_id: String(packet.group_id || current.group_id || ''),
      content: final_text,
      response: final_text,
    }
  })

  const current = find_current_assistant()
  if (current?.conv_id) {
    conv_id.value = current.conv_id
    persist_preferences()
  }
}

function on_stream_event(event_name, payload = {}) {
  if (event_name === 'meta') {
    const item = ensure_current_assistant()
    apply_common_payload(item.local_id, payload)
    scroll_to_bottom()
    return
  }

  if (event_name === 'delta') {
    const item = ensure_current_assistant()
    const chunk = normalize_formal_body(payload, '')
    patch_message(item.local_id, (current) => {
      const next_text = `${String(current.response || current.content || '')}${chunk}`
      return {
        streaming: true,
        error_text: '',
        status: get_explicit_status(payload) || current.status || '',
        message: normalize_formal_message(payload, current.message || ''),
        request_id: String(payload.request_id || current.request_id || ''),
        conv_id: String(payload.conv_id || current.conv_id || ''),
        mode_used: String(payload.mode_used || current.mode_used || ''),
        content: next_text,
        response: next_text,
      }
    })

    if (payload.conv_id) {
      conv_id.value = String(payload.conv_id)
      persist_preferences()
    }

    scroll_to_bottom()
    return
  }

  if (event_name === 'tool_call') {
    const item = ensure_current_assistant()
    patch_message(item.local_id, (current) => ({
      tool_calls: [...safe_array(current.tool_calls), payload],
      request_id: String(payload.request_id || current.request_id || ''),
      conv_id: String(payload.conv_id || current.conv_id || ''),
    }))
    scroll_to_bottom()
    return
  }

  if (event_name === 'tool_result') {
    const item = ensure_current_assistant()
    patch_message(item.local_id, (current) => ({
      tool_results: [...safe_array(current.tool_results), payload],
      request_id: String(payload.request_id || current.request_id || ''),
      conv_id: String(payload.conv_id || current.conv_id || ''),
    }))
    scroll_to_bottom()
    return
  }

  if (event_name === 'final') {
    current_final_received.value = true
    const item = ensure_current_assistant()
    apply_final_payload(item.local_id, payload)
    scroll_to_bottom()
    return
  }

  if (event_name === 'done') {
    const item = find_current_assistant()
    if (!item) return
    if (!current_final_received.value) {
      patch_message(item.local_id, {
        streaming: false,
        status: item.status || 'success',
      })
    }
    scroll_to_bottom()
    return
  }

  if (event_name === 'error') {
    const item = ensure_current_assistant()
    const error_text = normalize_formal_message(payload, 'stream error')
    patch_message(item.local_id, (current) => {
      const currentBody = current.response || current.content || ''
      const nextBody = currentBody || `错误：${error_text}`
      return {
        streaming: false,
        status: 'error',
        message: error_text,
        error_text,
        content: nextBody,
        response: nextBody,
      }
    })
    scroll_to_bottom()
  }
}

async function send_message() {
  const text = input_text.value.trim()
  if (!text || isStreaming.value) return

  persist_preferences()

  append_message({
    role: 'user',
    content: text,
    response: text,
    streaming: false,
    error_text: '',
    status: 'success',
    message: '',
    mode_used: rag_mode.value,
    citations: [],
    rss_evidence: [],
    market_evidence: [],
    evidence_query: '',
    evidence_tools: [],
    evidence_result: {},
    tool_calls: [],
    tool_results: [],
    request_id: '',
    conv_id: conv_id.value,
    qa_id: '',
    group_id: '',
  })

  const assistant = append_message({
    role: 'assistant',
    content: '',
    response: '',
    streaming: true,
    error_text: '',
    status: '',
    message: '',
    mode_used: '',
    citations: [],
    rss_evidence: [],
    market_evidence: [],
    evidence_query: '',
    evidence_tools: [],
    evidence_result: {},
    tool_calls: [],
    tool_results: [],
    request_id: '',
    conv_id: conv_id.value,
    qa_id: '',
    group_id: '',
  })

  current_stream_local_id.value = assistant.local_id
  current_final_received.value = false
  current_dedupe_key.value = `chat_stream_${Date.now()}_${Math.random().toString(16).slice(2)}`

  const args = {
    conv_id: conv_id.value || '',
    content: text,
    model: model.value,
    rag_mode: rag_mode.value,
  }

  input_text.value = ''
  scroll_to_bottom()

  try {
    const result = await callToolStream('nisb_chat_orchestrate', args, {
      dedupe_key: current_dedupe_key.value,
      onEvent: on_stream_event,
    })

    const item = find_current_assistant()
    if (item && result && typeof result === 'object') {
      apply_final_payload(item.local_id, result)
    }
  } catch (e) {
    const item = find_current_assistant()
    if (item) {
      const error_text = String(e?.message || '请求失败')
      patch_message(item.local_id, (current) => {
        const currentBody = current.response || current.content || ''
        const nextBody = currentBody || `错误：${error_text}`
        return {
          streaming: false,
          status: 'error',
          message: error_text,
          error_text,
          content: nextBody,
          response: nextBody,
        }
      })
    }
  } finally {
    clear_runtime_handles()
    scroll_to_bottom()
  }
}

function cancel_stream() {
  if (!current_dedupe_key.value) return
  cancelByDedupeKey(current_dedupe_key.value)
}

function on_chat_evidence(evt) {
  const detail = evt?.detail || {}
  const last_assistant = [...messages.value].reverse().find((x) => x.role === 'assistant')
  if (!last_assistant) return

  patch_message(last_assistant.local_id, (current) => ({
    citations: Array.isArray(detail.citations) ? detail.citations : current.citations,
    rss_evidence: Array.isArray(detail.rss_evidence) ? detail.rss_evidence : current.rss_evidence,
    market_evidence: Array.isArray(detail.market_evidence)
      ? detail.market_evidence
      : current.market_evidence,
    evidence_query: String(detail.evidence_query || current.evidence_query || ''),
    evidence_tools: Array.isArray(detail.evidence_tools)
      ? detail.evidence_tools
      : current.evidence_tools,
    evidence_result:
      detail.evidence_result && typeof detail.evidence_result === 'object'
        ? detail.evidence_result
        : current.evidence_result,
    qa_id: String(detail.qa_id || current.qa_id || ''),
    group_id: String(detail.group_id || current.group_id || ''),
  }))
}

watch(model, persist_preferences)
watch(rag_mode, persist_preferences)

onMounted(async () => {
  window.addEventListener('nisb-chat-evidence', on_chat_evidence)
  persist_preferences()

  if (conv_id.value) {
    await load_conversation(conv_id.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('nisb-chat-evidence', on_chat_evidence)
  if (current_dedupe_key.value) {
    cancelByDedupeKey(current_dedupe_key.value)
  }
})
</script>

<style scoped>
.chat_stream_panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #0f1115;
  color: #e5e7eb;
}

.chat_toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #22262f;
  background: #11151d;
}

.toolbar_left,
.toolbar_right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex-wrap: wrap;
}

.toolbar_left {
  flex: 1;
}

.field {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.field_model {
  flex: 1 1 360px;
}

.field_mode {
  flex: 0 0 auto;
}

.field span {
  font-size: 12px;
  color: #9ca3af;
  flex-shrink: 0;
}

.input,
.textarea {
  width: 100%;
  border: 1px solid #2b313d;
  background: #151922;
  color: #e5e7eb;
  border-radius: 10px;
  outline: none;
  padding: 10px 12px;
  box-sizing: border-box;
}

.input:focus,
.textarea:focus {
  border-color: #3b82f6;
}

.chat_list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.chat_item {
  display: flex;
  margin-bottom: 14px;
}

.chat_item_user {
  justify-content: flex-end;
}

.chat_item_assistant {
  justify-content: flex-start;
}

.chat_bubble {
  width: min(900px, 92%);
  border: 1px solid #252b36;
  border-radius: 14px;
  background: #151922;
  padding: 12px;
}

.chat_item_user .chat_bubble {
  background: #1e293b;
  border-color: #334155;
}

.chat_meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.role {
  font-weight: 700;
  color: #f3f4f6;
}

.mode {
  padding: 2px 8px;
  border-radius: 999px;
  background: #1f2937;
}

.status {
  color: #9ca3af;
}

.status_streaming {
  color: #22c55e;
}

.status_error {
  color: #ef4444;
}

.status_warning {
  color: #f59e0b;
}

.chat_content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  line-height: 1.65;
  color: #e5e7eb;
}

.message_box {
  margin-top: 12px;
  border-top: 1px dashed #2f3745;
  padding-top: 12px;
}

.evidence_box {
  margin-top: 12px;
  border-top: 1px dashed #2f3745;
  padding-top: 12px;
}

.evidence_block + .evidence_block {
  margin-top: 10px;
}

.evidence_title {
  font-size: 12px;
  color: #93c5fd;
  margin-bottom: 6px;
}

.evidence_pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.55;
  color: #cbd5e1;
}

.chat_input_bar {
  border-top: 1px solid #22262f;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #11151d;
}

.input_meta_bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.meta_chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.meta_chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid #2b313d;
  background: #151922;
  color: #9ca3af;
  font-size: 12px;
}

.meta_chip.active {
  color: #93c5fd;
  border-color: #31548f;
}

.input_row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  min-width: 0;
}

.conv_info {
  font-size: 12px;
  color: #9ca3af;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.conv_info code {
  display: inline-block;
  max-width: min(56vw, 520px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #e5e7eb;
}

.textarea {
  flex: 1 1 0;
  min-width: 0;
  min-height: 56px;
  max-height: 220px;
  resize: vertical;
  line-height: 1.6;
}

.input_actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.btn {
  border: none;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  color: #fff;
  font: inherit;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn:not(:disabled):hover {
  opacity: 0.92;
}

.btn_primary {
  background: #2563eb;
}

.btn_secondary {
  background: #374151;
}

.btn_danger {
  background: #dc2626;
}

.send_btn {
  width: 92px;
  min-height: 56px;
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .chat_toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar_right {
    justify-content: flex-end;
  }

  .chat_bubble {
    width: 100%;
  }

  .conv_info code {
    max-width: 100%;
  }
}

@media (max-width: 640px) {
  .chat_list {
    padding: 12px;
  }

  .field {
    width: 100%;
  }

  .field_model,
  .field_mode {
    flex: 1 1 100%;
  }

  .field {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }

  .input_meta_bar {
    flex-direction: column;
    align-items: stretch;
  }

  .input_row {
    align-items: stretch;
  }

  .send_btn {
    width: 78px;
    min-height: 56px;
  }
}
</style>
