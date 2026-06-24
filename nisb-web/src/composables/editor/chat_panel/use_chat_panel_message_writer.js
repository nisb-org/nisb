import {
  create_empty_stream_markdown_state,
  hydrate_stream_markdown_from_text,
} from '../../chat/use_stream_markdown'

export function new_client_message_id(prefix = 'msg') {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function safe_parse_json(value) {
  if (value == null) return null
  if (typeof value === 'object') return value

  const text = String(value || '').trim()
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export function safe_json_preview(value, limit = 2400) {
  try {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    if (text.length <= limit) return text
    return `${text.slice(0, limit)}\\n...truncated`
  } catch {
    const text = String(value || '')
    if (text.length <= limit) return text
    return `${text.slice(0, limit)}\\n...truncated`
  }
}

export function pick_first(...values) {
  for (const value of values) {
    if (value === undefined || value === null) continue
    if (typeof value === 'string' && !value.trim()) continue
    return value
  }
  return undefined
}

export function arrayify(value) {
  if (Array.isArray(value)) {
    return value.filter((item) => String(item || '').trim())
  }
  if (typeof value === 'string' && value.trim()) {
    return [value.trim()]
  }
  return []
}

export function compact_object(obj) {
  const out = {}
  for (const [key, value] of Object.entries(obj || {})) {
    if (value === undefined || value === null) continue
    if (typeof value === 'string' && !value.trim()) continue
    if (Array.isArray(value) && value.length === 0) continue
    out[key] = value
  }
  return out
}

export function read_string(obj, ...keys) {
  for (const key of keys) {
    const value = obj?.[key]
    if (value === undefined || value === null) continue
    const text = String(value).trim()
    if (!text) continue
    return text
  }
  return ''
}

export function read_array(obj, ...keys) {
  for (const key of keys) {
    const value = obj?.[key]
    if (Array.isArray(value)) return value
  }
  return []
}

export function read_object(obj, ...keys) {
  for (const key of keys) {
    const value = obj?.[key]
    if (value && typeof value === 'object' && !Array.isArray(value)) return value
  }
  return {}
}

export function normalize_display_text(value) {
  const text = value === null || value === undefined ? '' : String(value)
  if (!text) return ''

  return text
    .replace(/\r\n/g, '\n')
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\n')
}

export function create_message_stream_markdown_from_content(content, options = {}) {
  return hydrate_stream_markdown_from_text(normalize_display_text(content), options)
}

export function create_user_message(overrides = {}) {
  const base = { ...overrides }
  const content = normalize_display_text(base.content || base.response || '')
  const response = normalize_display_text(base.response || content)

  return {
    ...base,
    id: String(base.id || new_client_message_id('user')),
    role: 'user',
    content,
    response,
    pending: false,
    citations: Array.isArray(base.citations) ? base.citations : [],
    tool_calls: Array.isArray(base.tool_calls) ? base.tool_calls : [],
    tool_results: Array.isArray(base.tool_results) ? base.tool_results : [],
  }
}

export function create_assistant_message(overrides = {}) {
  const base = { ...overrides }
  const pending =
    base.pending === undefined
      ? true
      : !!base.pending

  const content = normalize_display_text(base.content || base.response || '')
  const response = normalize_display_text(base.response || content)

  const stream_markdown =
    base.stream_markdown && typeof base.stream_markdown === 'object'
      ? base.stream_markdown
      : pending
        ? create_empty_stream_markdown_state()
        : create_message_stream_markdown_from_content(response || content, {
            final: true,
            done: true,
          })

  return {
    ...base,
    id: String(base.id || new_client_message_id('assistant')),
    role: 'assistant',
    content,
    response,
    pending,
    citations: Array.isArray(base.citations) ? base.citations : [],
    tool_calls: Array.isArray(base.tool_calls) ? base.tool_calls : [],
    tool_results: Array.isArray(base.tool_results) ? base.tool_results : [],
    request_id: String(base.request_id || ''),
    conv_id: String(base.conv_id || ''),
    rag_mode: String(base.rag_mode || ''),
    mode_used: String(base.mode_used || ''),
    mcp_overrides: base.mcp_overrides && typeof base.mcp_overrides === 'object' ? base.mcp_overrides : {},
    rss_evidence: Array.isArray(base.rss_evidence) ? base.rss_evidence : [],
    market_evidence: Array.isArray(base.market_evidence) ? base.market_evidence : [],
    evidence_query: String(base.evidence_query || ''),
    evidence_tools: Array.isArray(base.evidence_tools) ? base.evidence_tools : [],
    evidence_result: base.evidence_result && typeof base.evidence_result === 'object' ? base.evidence_result : {},
    qa_id: String(base.qa_id || ''),
    group_id: String(base.group_id || ''),
    status: String(base.status || ''),
    message: normalize_display_text(base.message || ''),
    stream_markdown,
  }
}

export function normalize_tool_call(item) {
  const raw_args = item?.arguments ?? item?.args ?? item?.tool_args ?? item?.toolArgs ?? {}

  return {
    id: String(
      item?.id ||
        item?.tool_call_id ||
        item?.toolCallId ||
        new_client_message_id('tool_call')
    ),
    name: String(
      item?.name ||
        item?.tool_name ||
        item?.toolName ||
        item?.function?.name ||
        'unknown_tool'
    ),
    status: String(item?.status || 'running'),
    arguments_json: safe_json_preview(
      typeof raw_args === 'string' ? safe_parse_json(raw_args) ?? raw_args : raw_args,
      1800
    ),
    arguments_preview: String(
      item?.arguments_preview || item?.argumentsPreview || ''
    ).trim(),
  }
}

export function normalize_tool_result(item) {
  const raw = item?.result ?? item?.data ?? item?.output ?? item?.payload ?? item ?? {}

  return {
    id: String(
      item?.id ||
        item?.tool_call_id ||
        item?.toolCallId ||
        new_client_message_id('tool_result')
    ),
    name: String(item?.name || item?.tool_name || item?.toolName || 'unknown_tool'),
    result_json: safe_json_preview(raw, 2200),
    result_preview: String(item?.preview || item?.result_preview || item?.resultPreview || '').trim(),
  }
}

export function read_message_by_id(messages, message_id) {
  const list = Array.isArray(messages.value) ? messages.value : []
  return list.find((item) => String(item?.id || '') === String(message_id || '')) || null
}

export function patch_message_by_id(messages, message_id, patch = {}) {
  const list = Array.isArray(messages.value) ? [...messages.value] : []
  const idx = list.findIndex((item) => String(item?.id || '') === String(message_id || ''))
  if (idx < 0) return false

  const next_patch = { ...patch }

  if ('response' in next_patch) {
    next_patch.response = normalize_display_text(next_patch.response)
  }
  if ('content' in next_patch) {
    next_patch.content = normalize_display_text(next_patch.content)
  }
  if ('message' in next_patch) {
    next_patch.message = normalize_display_text(next_patch.message)
  }

  if ('response' in next_patch && !('content' in next_patch)) {
    next_patch.content = String(next_patch.response || '')
  }
  if ('content' in next_patch && !('response' in next_patch)) {
    next_patch.response = String(next_patch.content || '')
  }

  list[idx] = {
    ...list[idx],
    ...next_patch,
  }

  messages.value = list
  return true
}

export function push_message(messages, message) {
  const list = Array.isArray(messages.value) ? [...messages.value] : []
  const next_message = { ...message }

  if ('response' in next_message) {
    next_message.response = normalize_display_text(next_message.response)
  }
  if ('content' in next_message) {
    next_message.content = normalize_display_text(next_message.content)
  }
  if ('message' in next_message) {
    next_message.message = normalize_display_text(next_message.message)
  }

  if ('response' in next_message && !('content' in next_message)) {
    next_message.content = String(next_message.response || '')
  }
  if ('content' in next_message && !('response' in next_message)) {
    next_message.response = String(next_message.content || '')
  }

  list.push(next_message)
  messages.value = list
  return list.length - 1
}

export function has_tool_activity(msg) {
  return (
    (Array.isArray(msg?.tool_calls) && msg.tool_calls.length > 0) ||
    (Array.isArray(msg?.tool_results) && msg.tool_results.length > 0)
  )
}

export function format_tool_status(status) {
  const text = String(status || '').trim().toLowerCase()
  if (text === 'done' || text === 'success' || text === 'completed') return '完成'
  if (text === 'error' || text === 'failed') return '失败'
  if (text === 'queued') return '排队中'
  return '执行中'
}

export function create_empty_stream_state() {
  return {
    streaming: false,
    stage: '',
    mode_used: '',
    request_id: '',
    conv_id: '',
    rag_mode: '',
    mcp_overrides: {},
    tool_calls: [],
    tool_results: [],
    citations: [],
    rss_evidence: [],
    market_evidence: [],
    evidence_query: '',
    evidence_tools: [],
    evidence_result: {},
    qa_id: '',
    group_id: '',
    status: '',
    message: '',
  }
}
