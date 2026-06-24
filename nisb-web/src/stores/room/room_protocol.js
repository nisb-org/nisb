import {
  safe_array,
  safe_object,
  safe_string,
  is_plain_object,
} from './room_shared'

export function normalize_status_token(value) {
  const s = safe_string(value).trim().toLowerCase()
  if (!s) return ''

  if (['ok', 'success', 'succeeded'].includes(s)) return 'success'
  if (['warning', 'partial_success', 'partial_error'].includes(s)) return 'warning'
  if (['error', 'failed', 'fail'].includes(s)) return 'error'
  if (['aborted', 'abort', 'cancelled', 'canceled', 'terminated'].includes(s)) return 'aborted'
  if (['disabled', 'denied'].includes(s)) return s
  if (['running', 'pending', 'queued', 'processing', 'in_progress'].includes(s)) return 'running'
  if (['finished', 'completed', 'complete', 'done'].includes(s)) return 'finished'
  if (['unavailable', 'not_configured'].includes(s)) return 'unavailable'
  if (['unauthorized', 'forbidden'].includes(s)) return 'unauthorized'
  if (['rate_limited', 'ratelimited'].includes(s)) return 'rate_limited'
  if (['network_error', 'network'].includes(s)) return 'network_error'

  return s
}

export function normalize_tool_results(res) {
  const root = safe_object(res)
  const sources = [
    root.tool_results,
    root.data?.tool_results,
    root.result?.tool_results,
    root.payload?.tool_results,
  ]

  for (const rows of sources) {
    if (!Array.isArray(rows)) continue
    return rows.map((row) => {
      const r = safe_object(row)
      const primary =
        is_plain_object(r.data) && Object.keys(r.data).length
          ? r.data
          : is_plain_object(r.result) && Object.keys(r.result).length
            ? r.result
            : is_plain_object(r.payload) && Object.keys(r.payload).length
              ? r.payload
              : is_plain_object(r.value) && Object.keys(r.value).length
                ? r.value
                : {}

      return {
        ...r,
        data: is_plain_object(r.data) ? r.data : primary,
        result: is_plain_object(r.result) ? r.result : primary,
        payload: is_plain_object(r.payload) ? r.payload : primary,
        value: is_plain_object(r.value) ? r.value : primary,
      }
    })
  }

  return []
}

export function collect_candidate_objects(res) {
  const root = safe_object(res)
  const out = []

  const push = (obj) => {
    if (is_plain_object(obj) && Object.keys(obj).length > 0) out.push(obj)
  }

  push(root)
  push(root.data)
  push(root.result)
  push(root.payload)
  push(root.value)

  for (const row of normalize_tool_results(root)) {
    push(row)
    push(row.data)
    push(row.result)
    push(row.payload)
    push(row.value)
  }

  return out
}

export function unwrap_tool_result(res) {
  const candidates = collect_candidate_objects(res)

  for (const obj of candidates) {
    if (
      is_plain_object(obj.room) ||
      Array.isArray(obj.roles) ||
      is_plain_object(obj.state) ||
      Array.isArray(obj.items) ||
      !!safe_string(obj.uid || obj.user_id).trim()
    ) {
      return obj
    }
  }

  for (const obj of candidates) {
    if (Object.keys(obj).length > 0) return obj
  }

  return {}
}

export function get_explicit_status(data) {
  const root = safe_object(data)
  const candidates = [
    root.status,
    root.data?.status,
    root.result?.status,
    root.payload?.status,
  ]

  for (const item of candidates) {
    const s = normalize_status_token(item)
    if (['success', 'warning', 'error', 'aborted'].includes(s)) return s
  }

  return ''
}

export function normalize_formal_message(raw, data, fallback_message = '操作失败') {
  const root = safe_object(raw)
  const unwrapped = safe_object(data)

  const candidates = [
    root.response,
    root.message,
    root.data?.response,
    root.data?.message,
    root.payload?.response,
    root.payload?.message,
    root.result?.response,
    root.result?.message,
    unwrapped.response,
    unwrapped.message,
  ]

  for (const item of candidates) {
    const s = safe_string(item).trim()
    if (s) return s
  }

  return fallback_message
}

function collect_nested_success_candidates(raw) {
  const rows = normalize_tool_results(raw)
  const values = []

  for (const row of rows) {
    const r = safe_object(row)
    values.push(
      r.success,
      r.data?.success,
      r.result?.success,
      r.payload?.success,
      r.value?.success
    )
  }

  return values
}

export function assert_tool_success(res, fallback_message = '操作失败') {
  const raw = safe_object(res)
  const data = unwrap_tool_result(raw)
  const explicit_status = get_explicit_status(raw)

  if (explicit_status === 'error' || explicit_status === 'aborted') {
    throw new Error(normalize_formal_message(raw, data, fallback_message))
  }

  if (explicit_status === 'success' || explicit_status === 'warning') {
    return raw
  }

  const success_candidates = [
    raw.success,
    raw.data?.success,
    raw.result?.success,
    raw.payload?.success,
    data?.success,
    ...collect_nested_success_candidates(raw),
  ]

  if (success_candidates.some((x) => x === false)) {
    throw new Error(normalize_formal_message(raw, data, fallback_message))
  }

  return raw
}

export function is_cancellation_like_error(error) {
  const name = safe_string(error?.name).trim().toLowerCase()
  const msg = safe_string(error?.message || error).trim().toLowerCase()

  if (name === 'aborterror') return true
  if (msg.includes('请求已取消或超时')) return true
  if (msg.includes('请求已取消')) return true
  if (msg.includes('aborted')) return true
  if (msg.includes('aborterror')) return true
  if (msg.includes('cancelled')) return true
  if (msg.includes('canceled')) return true

  return false
}

export function pick_first_tool_result(data, matcher) {
  const rows = normalize_tool_results(data)
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    if (matcher(row)) return row
  }
  return null
}

export function get_runtime_payload(item) {
  const src = safe_object(item)
  return safe_object(
    src.payload ||
    src.data ||
    src.result ||
    src.value
  )
}

export function get_runtime_run_id(item) {
  const src = safe_object(item)
  const payload = get_runtime_payload(src)
  return safe_string(
    src.run_id ||
    src.runId ||
    payload.run_id ||
    payload.runId
  ).trim()
}

export function normalize_runtime_path(value) {
  let s = safe_string(value).trim().replace(/\\\\/g, '/')
  s = s.replace(/\/{2,}/g, '/')
  s = s.replace(/^\/+|\/+$/g, '')

  const parts = s
    .split('/')
    .map((x) => safe_string(x).trim())
    .filter((x) => x && x !== '.' && x !== '..')

  return parts.join('/')
}

export function normalize_tool_activity_name(value) {
  const src = safe_object(value)
  const type = safe_string(src.type).trim()
  const providerLabel = safe_string(src.provider_label || src.provider_name || src.provider_id).trim()
  const roleLabel = safe_string(src.role_name || src.role_id).trim()

  if (type === 'room_mcp_provider_execution') return providerLabel || 'provider_execution'
  if (type === 'room_mcp_provider_error') return providerLabel || 'provider_error'
  if (type === 'room_role_runtime_fact') return roleLabel || 'role_runtime'

  return safe_string(
    src.tool_name ||
    src.name ||
    src.tool ||
    src.function_name ||
    src.function?.name ||
    src.source_tool_name ||
    src.type
  ).trim() || '未命名工具'
}

function normalize_tool_activity_reason(value) {
  const src = safe_object(value)
  return safe_string(
    src.availability_reason ||
    src.reason ||
    src.error_code ||
    src.error
  ).trim().toLowerCase()
}

function derive_tool_activity_status_text(raw, reason = '') {
  if (!reason) return raw
  if (['unavailable', 'unauthorized', 'rate_limited', 'network_error', 'error'].includes(raw)) {
    return reason
  }
  return raw
}

export function normalize_tool_activity_status(value, is_result = false) {
  const src = safe_object(value)
  const reason = normalize_tool_activity_reason(src)

  let raw =
    normalize_status_token(
      src.status ||
      src.state ||
      (is_result ? 'success' : 'called')
    ) ||
    safe_string(src.status || src.state || (is_result ? 'success' : 'called')).trim().toLowerCase()

  if ((!raw || raw === 'success') && reason) {
    if (reason.startsWith('missing_env:') || reason.startsWith('invalid_params')) {
      raw = 'unavailable'
    } else if (reason.startsWith('upstream_401')) {
      raw = 'unauthorized'
    } else if (reason.startsWith('upstream_429')) {
      raw = 'rate_limited'
    } else if (reason.startsWith('network_error')) {
      raw = 'network_error'
    }
  }

  if (!raw) {
    return {
      statusText: is_result ? 'success' : 'called',
      statusClass: is_result ? 'success' : 'running',
    }
  }

  const statusText = derive_tool_activity_status_text(raw, reason)

  if (raw === 'aborted') {
    return {
      statusText,
      statusClass: 'warning',
    }
  }

  if (raw === 'disabled' || raw === 'denied') {
    return {
      statusText,
      statusClass: 'warning',
    }
  }

  if (raw === 'unavailable' || raw === 'rate_limited') {
    return {
      statusText,
      statusClass: 'warning',
    }
  }

  if (raw === 'unauthorized' || raw === 'network_error') {
    return {
      statusText,
      statusClass: 'error',
    }
  }

  if (
    raw.includes('error') ||
    raw.includes('fail') ||
    reason.startsWith('upstream_401') ||
    reason.startsWith('network_error')
  ) {
    return {
      statusText,
      statusClass: 'error',
    }
  }

  if (
    raw.includes('warning') ||
    raw.includes('partial') ||
    reason.startsWith('missing_env:') ||
    reason.startsWith('invalid_params') ||
    reason.startsWith('upstream_429')
  ) {
    return {
      statusText,
      statusClass: 'warning',
    }
  }

  if (raw === 'running' || raw.includes('pending') || raw.includes('queued') || raw === 'called') {
    return {
      statusText,
      statusClass: 'running',
    }
  }

  if (raw === 'finished') {
    return {
      statusText,
      statusClass: 'success',
    }
  }

  return {
    statusText,
    statusClass: 'success',
  }
}

export function get_supervisor_audit_sections(payload = {}) {
  const src = safe_object(payload)
  const fsRead = safe_object(src.supervisor_fs_read)
  const notebookRead = safe_object(src.supervisor_notebook_read)
  const notebookWrite = safe_object(src.supervisor_notebook_write)

  let actions = []
  for (const key of ['supervisor_fs_actions', 'supervisor_file_actions', 'supervisor_actions']) {
    const rows = src[key]
    if (Array.isArray(rows)) {
      actions = rows.filter((item) => item && typeof item === 'object')
      break
    }
  }

  return {
    supervisor_fs_read: fsRead,
    supervisor_notebook_read: notebookRead,
    supervisor_notebook_write: notebookWrite,
    supervisor_fs_actions: actions,
  }
}

export function get_section_tool_activity(section = {}) {
  const src = safe_object(section)
  return {
    tool_calls: safe_array(src.tool_calls),
    tool_results: safe_array(src.tool_results),
  }
}

function compact_identity_text(value, maxLength = 180) {
  const text = safe_string(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}...`
}

function build_tool_activity_key(prefix, row) {
  const src = safe_object(row)
  const explicitId = safe_string(
    src.tool_call_id ||
    src.call_id ||
    src.request_id ||
    src.id ||
    src.event_id
  ).trim()
  const name = normalize_tool_activity_name(src)
  const type = safe_string(src.type || src.kind).trim()
  const status = normalize_status_token(src.status || src.state)
  const path = normalize_runtime_path(
    src.relative_path ||
    src.path ||
    src.focus_root ||
    src.target_path
  )
  const message = compact_identity_text(
    src.message ||
    src.summary ||
    src.response ||
    src.content ||
    src.relative_path ||
    src.path ||
    src.focus_root ||
    src.result?.message ||
    src.value?.message ||
    ''
  )

  return [
    prefix,
    explicitId,
    name,
    type,
    status,
    path,
    message,
  ].filter(Boolean).join(':')
}

export function dedupe_tool_activity_rows(rows, prefix = 'tool_activity') {
  const out = []
  const seen = new Set()

  safe_array(rows).forEach((row) => {
    const normalized = safe_object(row)
    if (!Object.keys(normalized).length) return

    const key = build_tool_activity_key(prefix, normalized)
    if (seen.has(key)) return
    seen.add(key)
    out.push(normalized)
  })

  return out
}

export function flatten_supervisor_tool_activity(payload = {}) {
  const sections = get_supervisor_audit_sections(payload)

  const toolCalls = []
  const toolResults = []

  const primarySections = [
    safe_object(sections.supervisor_fs_read),
    safe_object(sections.supervisor_notebook_read),
    safe_object(sections.supervisor_notebook_write),
  ]

  for (const section of primarySections) {
    const activity = get_section_tool_activity(section)
    toolCalls.push(...activity.tool_calls)
    toolResults.push(...activity.tool_results)
  }

  for (const action of safe_array(sections.supervisor_fs_actions)) {
    const activity = get_section_tool_activity(action)
    toolCalls.push(...activity.tool_calls)
    toolResults.push(...activity.tool_results)
  }

  return {
    tool_calls: dedupe_tool_activity_rows(toolCalls, 'nested_tool_call'),
    tool_results: dedupe_tool_activity_rows(toolResults, 'nested_tool_result'),
  }
}

export function has_supervisor_audit(payload = {}) {
  const sections = get_supervisor_audit_sections(payload)
  return (
    Object.keys(sections.supervisor_fs_read).length > 0 ||
    Object.keys(sections.supervisor_notebook_read).length > 0 ||
    Object.keys(sections.supervisor_notebook_write).length > 0 ||
    sections.supervisor_fs_actions.length > 0
  )
}

export function get_section_primary_message(section = {}) {
  const src = safe_object(section)
  if (safe_string(src.message).trim()) return safe_string(src.message).trim()
  if (safe_string(src.reason).trim()) return safe_string(src.reason).trim()

  const firstToolResult = safe_array(src.tool_results)[0]
  if (firstToolResult && typeof firstToolResult === 'object') {
    const row = safe_object(firstToolResult)
    return safe_string(
      row.message ||
      row.response ||
      row.content ||
      row.relative_path ||
      row.path
    ).trim()
  }

  return ''
}

export function get_section_primary_path(section = {}) {
  const src = safe_object(section)
  return normalize_runtime_path(
    src.relative_path ||
    src.path
  )
}

export function extract_runtime_result_text(payload = {}, fallback = '') {
  const src = safe_object(payload)
  const notebookWriteMessage = get_section_primary_message(src.supervisor_notebook_write)
  const notebookReadMessage = get_section_primary_message(src.supervisor_notebook_read)
  const fsMessage = get_section_primary_message(src.supervisor_fs_read)

  return safe_string(
    src.response ||
    src.content ||
    src.message ||
    src.summary ||
    notebookWriteMessage ||
    notebookReadMessage ||
    fsMessage ||
    fallback
  ).trim()
}

export function extract_runtime_result_citations(payload = {}) {
  const src = safe_object(payload)
  return safe_array(
    src.citations ||
    src.data?.citations ||
    src.result?.citations ||
    src.payload?.citations ||
    src.value?.citations
  )
}

