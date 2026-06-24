import {
  safe_array,
  safe_object,
  safe_string,
} from '../room_shared'
import {
  normalize_runtime_path,
  normalize_status_token,
  normalize_tool_activity_name,
} from '../room_protocol'

export function pretty_json(value, maxLength = 1800) {
  try {
    const text = JSON.stringify(value, null, 2)
    if (!text) return ''
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength)}\n...`
  } catch {
    const text = safe_string(value)
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength)}...`
  }
}

export function compact_text(value, maxLength = 220) {
  const text = safe_string(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}...`
}

export function build_tool_activity_identity(
  row = {},
  kind = '',
  resolveStructuredName = null
) {
  const src = safe_object(row)
  const structuredName =
    typeof resolveStructuredName === 'function'
      ? safe_string(resolveStructuredName(src)).trim()
      : ''
  const name = structuredName || normalize_tool_activity_name(src)
  const explicitId = safe_string(
    src.tool_call_id ||
      src.call_id ||
      src.id ||
      src.event_id
  ).trim()
  const type = safe_string(src.type || src.kind || kind).trim()
  const status = normalize_status_token(src.status)
  const path = normalize_runtime_path(
    src.relative_path ||
      src.path ||
      src.focus_root ||
      src.target_path
  )
  const message = compact_text(
    src.message ||
      src.summary ||
      src.relative_path ||
      src.path ||
      src.focus_root ||
      src.result?.message ||
      src.value?.message ||
      '',
    180
  )

  return [
    safe_string(kind).trim(),
    explicitId,
    name,
    structuredName,
    type,
    status,
    path,
    message,
  ].filter(Boolean).join('::')
}

export function dedupe_tool_activity_rows(
  list = [],
  kind = '',
  resolveStructuredName = null
) {
  const out = []
  const seen = new Set()

  for (const item of safe_array(list)) {
    const row = safe_object(item)
    if (!Object.keys(row).length) continue

    const identity = build_tool_activity_identity(
      row,
      kind,
      resolveStructuredName
    )
    const fallbackIdentity = pretty_json(row, 600)
    const key = identity || `${kind}:${fallbackIdentity}`

    if (seen.has(key)) continue
    seen.add(key)
    out.push(row)
  }

  return out
}

