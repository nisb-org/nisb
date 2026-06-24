import {
  read_array,
  read_object,
  read_string,
} from './use_chat_panel_message_writer'
import {
  create_empty_stream_markdown_state,
  finalize_stream_markdown,
  hydrate_stream_markdown_from_text,
} from '../../chat/use_stream_markdown'

export function make_request_id() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
  } catch {}
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function read_response_text(obj) {
  return read_string(
    obj,
    'response',
    'content',
    'text',
    'answer',
    'final_text',
    'assistant_response'
  )
}

export function unwrap_tool_result(res) {
  if (res && typeof res === 'object' && res.result && typeof res.result === 'object') {
    return res.result
  }
  return res || {}
}

export function dispatch_room_refresh(room_id, request_id = '') {
  try {
    window.dispatchEvent(new CustomEvent('nisb-room-refresh-request', {
      detail: {
        room_id: String(room_id || '').trim(),
        request_id: String(request_id || '').trim(),
      }
    }))
  } catch {}
}

export function dispatch_conversations_refresh() {
  try {
    window.dispatchEvent(new CustomEvent('nisb-conversations-refresh'))
  } catch {}
}

export function build_state_patch(ctx, extra = {}) {
  return {
    request_id: ctx.request_id,
    conv_id: ctx.conv_id,
    rag_mode: ctx.rag_mode,
    mcp_overrides: ctx.mcp_overrides,
    mode_used: ctx.mode_used,
    tool_calls: [...ctx.tool_calls],
    tool_results: [...ctx.tool_results],
    citations: [...ctx.citations],
    rss_evidence: [...ctx.rss_evidence],
    market_evidence: [...ctx.market_evidence],
    evidence_query: ctx.evidence_query,
    evidence_tools: [...ctx.evidence_tools],
    evidence_result: ctx.evidence_result,
    qa_id: ctx.qa_id,
    group_id: ctx.group_id,
    status: ctx.status,
    message: ctx.message,
    ...extra,
  }
}

export function build_final_payload(ctx, response = '') {
  return {
    request_id: ctx.request_id,
    conv_id: ctx.conv_id,
    rag_mode: ctx.rag_mode,
    mcp_overrides: ctx.mcp_overrides,
    mode_used: ctx.mode_used,
    citations: [...ctx.citations],
    rss_evidence: [...ctx.rss_evidence],
    market_evidence: [...ctx.market_evidence],
    evidence_query: ctx.evidence_query,
    evidence_tools: [...ctx.evidence_tools],
    evidence_result: ctx.evidence_result,
    qa_id: ctx.qa_id,
    group_id: ctx.group_id,
    tool_calls: [...ctx.tool_calls],
    tool_results: [...ctx.tool_results],
    response: String(response || ''),
    status: ctx.status,
    message: ctx.message,
  }
}

export function build_message_patch(ctx, content, extra = {}) {
  const response = String(content || '')

  return {
    content: response,
    response,
    pending: false,
    citations: [...ctx.citations],
    tool_calls: [...ctx.tool_calls],
    tool_results: [...ctx.tool_results],
    request_id: ctx.request_id,
    conv_id: ctx.conv_id,
    rag_mode: ctx.rag_mode,
    mode_used: ctx.mode_used,
    mcp_overrides: ctx.mcp_overrides,
    rss_evidence: [...ctx.rss_evidence],
    market_evidence: [...ctx.market_evidence],
    evidence_query: ctx.evidence_query,
    evidence_tools: [...ctx.evidence_tools],
    evidence_result: ctx.evidence_result,
    qa_id: ctx.qa_id,
    group_id: ctx.group_id,
    status: ctx.status,
    message: ctx.message,
    ...extra,
  }
}

export function apply_common_meta(ctx, data) {
  const next_request_id = read_string(data, 'request_id')
  const next_conv_id = read_string(data, 'conv_id')
  const next_rag_mode = read_string(data, 'rag_mode')
  const next_mode_used = read_string(data, 'mode_used')
  const next_status = read_string(data, 'status')
  const next_message = read_string(data, 'message')
  const next_mcp_overrides = read_object(data, 'mcp_overrides')

  if (next_request_id) ctx.request_id = next_request_id
  if (next_conv_id) ctx.conv_id = next_conv_id
  if (next_rag_mode) ctx.rag_mode = next_rag_mode
  if (next_mode_used) ctx.mode_used = next_mode_used
  if (next_status) ctx.status = next_status
  if (typeof next_message === 'string' && next_message.length > 0) ctx.message = next_message
  if (Object.keys(next_mcp_overrides).length > 0) {
    ctx.mcp_overrides = next_mcp_overrides
  }
}

export function apply_final_meta(ctx, data) {
  ctx.citations = read_array(data, 'citations')
  ctx.rss_evidence = read_array(data, 'rss_evidence')
  ctx.market_evidence = read_array(data, 'market_evidence')
  ctx.evidence_query = read_string(data, 'evidence_query')
  ctx.evidence_tools = read_array(data, 'evidence_tools')
  ctx.evidence_result = read_object(data, 'evidence_result')
  ctx.qa_id = read_string(data, 'qa_id')
  ctx.group_id = read_string(data, 'group_id')
}

export function ensure_message_stream_state(message, text = '') {
  const existing = message?.stream_markdown
  if (existing && typeof existing === 'object') return existing
  if (String(text || '')) {
    return hydrate_stream_markdown_from_text(String(text || ''), {
      final: false,
      done: false,
      has_error: false,
    })
  }
  return create_empty_stream_markdown_state()
}

function safe_message_key(msg, idx) {
  const id = read_string(msg, 'id', 'local_id')
  if (id) return id
  return `idx_${idx}`
}

export function build_messages_tail_signature(message_list) {
  const list = Array.isArray(message_list) ? message_list : []
  const tail = list.slice(-12)

  return JSON.stringify({
    count: list.length,
    tail: tail.map((msg, idx) => ({
      key: safe_message_key(msg, idx),
      role: read_string(msg, 'role'),
      sender: read_string(msg, 'sender'),
      sender_type: read_string(msg, 'sender_type'),
      room_event_type: read_string(msg, 'room_event_type'),
      pending: !!msg?.pending,
      status: read_string(msg, 'status'),
      response_len: String(msg?.response || msg?.content || '').length,
      tool_calls_len: Array.isArray(msg?.tool_calls) ? msg.tool_calls.length : 0,
      tool_results_len: Array.isArray(msg?.tool_results) ? msg.tool_results.length : 0,
    })),
  })
}

export function is_terminal_status(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return (
    normalized === 'success' ||
    normalized === 'error' ||
    normalized === 'aborted' ||
    normalized === 'cancelled' ||
    normalized === 'canceled' ||
    normalized === 'done' ||
    normalized === 'finished' ||
    normalized === 'completed'
  )
}

export {
  read_array,
  read_object,
  read_string,
  finalize_stream_markdown,
}
