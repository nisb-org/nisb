const UNKNOWN_TOOL_NAME = 'Unknown tool'
const LEGACY_UNNAMED_TOOL = '\u672a\u547d\u540d\u5de5\u5177'

function safe_array(value) {
  return Array.isArray(value) ? value : []
}

function safe_object(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function first_non_empty(...values) {
  for (const value of values) {
    const text = safe_string(value).trim()
    if (text) return text
  }
  return ''
}

function is_empty_object(value) {
  return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0
}

function stringify_preview(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value.trim()
  if (Array.isArray(value) && value.length === 0) return ''
  if (is_empty_object(value)) return ''

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return safe_string(value).trim()
  }
}

function compact_preview(value, limit = 420) {
  const text = safe_string(value).trim()
  if (!text) return ''
  if (text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`
}

function normalize_tool_name(value) {
  const text = safe_string(value).trim()
  if (!text) return ''

  const lower = text.toLowerCase()
  if (lower === 'unknown_tool') return ''
  if (text === LEGACY_UNNAMED_TOOL) return ''

  return text
}

function normalize_status_token(value, fallback = '') {
  const s = safe_string(value).trim().toLowerCase()
  if (!s) return safe_string(fallback).trim().toLowerCase()

  if (['queued', 'queue', 'pending', 'running', 'working', 'started', 'in_progress', 'progress'].includes(s)) {
    return 'running'
  }
  if (['ok', 'done', 'success', 'succeeded', 'completed', 'complete', 'finished'].includes(s)) {
    return 'done'
  }
  if (['warning', 'warn', 'partial_success', 'partial-error', 'partial_error', 'partial'].includes(s)) {
    return 'warning'
  }
  if (['error', 'failed', 'fail', 'timeout', 'timed_out'].includes(s)) {
    return 'error'
  }
  if (['cancelled', 'canceled', 'aborted', 'abort', 'skipped'].includes(s)) {
    return 'cancelled'
  }

  return s
}

function format_tool_status_label(status_token, fallback = 'Running') {
  const token = normalize_status_token(status_token)

  if (!token) return fallback
  if (token === 'running') return 'Running'
  if (token === 'done') return 'Done'
  if (token === 'warning') return 'Partial'
  if (token === 'error') return 'Failed'
  if (token === 'cancelled') return 'Cancelled'
  return token
}

function status_i18n_key(status_token) {
  const token = normalize_status_token(status_token)
  if (token === 'done') return 'chat.toolActivity.status.done'
  if (token === 'warning') return 'chat.toolActivity.status.warning'
  if (token === 'error') return 'chat.toolActivity.status.error'
  if (token === 'cancelled') return 'chat.toolActivity.status.cancelled'
  return 'chat.toolActivity.status.running'
}

function normalize_tool_key(kind, item, idx) {
  const src = safe_object(item)
  const id = first_non_empty(
    src.id,
    src.tool_call_id,
    src.toolCallId,
    src.call_id,
    src.callId,
    src.request_id,
    src.requestId,
    src.trace_id,
    src.traceId,
    src.correlation_id,
    src.correlationId,
    src.tool_use_id,
    src.toolUseId,
    src.related_tool_call_id,
    src.relatedToolCallId
  )
  if (id) return `${kind}:${id}`
  return `${kind}:idx:${idx}`
}

const TOOL_NAME_ALIASES = {
  supervisor_fs_read: 'nisb_supervisor_fs_read',
  supervisor_notebook_write: 'nisb_supervisor_notebook_write',
  room_supervisor_fs_read: 'nisb_supervisor_fs_read',
  room_supervisor_notebook_write: 'nisb_supervisor_notebook_write',
  fs_read: 'nisb_supervisor_fs_read',
  notebook_write: 'nisb_supervisor_notebook_write',
}

const INTERNAL_ACTIVITY_TYPES = new Set([
  'room_chat_bridge',
  'room_qascope_bridge',
])

function map_alias_tool_name(value) {
  const raw = safe_string(value).trim()
  if (!raw) return ''

  const direct = normalize_tool_name(raw)
  if (direct.startsWith('nisb_')) return direct

  const normalized = raw.toLowerCase().replace(/[\s-]+/g, '_')
  return TOOL_NAME_ALIASES[normalized] || ''
}

function collect_object_candidates(source) {
  const src = safe_object(source)

  return [
    src,
    safe_object(src.meta),
    safe_object(src.meta?.room_audit),
    safe_object(src.room_audit),
    safe_object(src.payload),
    safe_object(src.result),
    safe_object(src.data),
    safe_object(src.value),
    safe_object(src.tool_call),
    safe_object(src.related_tool_call),
    safe_object(src.parent_tool_call),
    safe_object(src.call),
    safe_object(src.function),
    safe_object(src.request),
    safe_object(src.response),
    safe_object(src.fs_context),
    safe_object(src.notebook_result),
    safe_object(src.evidence_result),
    safe_object(src.supervisor_fs_read),
    safe_object(src.supervisor_notebook_write),
    safe_object(src.payload?.fs_context),
    safe_object(src.payload?.notebook_result),
    safe_object(src.payload?.evidence_result),
    safe_object(src.payload?.supervisor_fs_read),
    safe_object(src.payload?.supervisor_notebook_write),
  ]
}

function map_rows_with_source(rows, bucket) {
  return rows.map((row, idx) => ({
    ...safe_object(row),
    __source_index: idx,
    __source_bucket: bucket,
  }))
}

function collect_array_from_candidates(source, key) {
  const src = safe_object(source)

  const candidates = [
    { bucket: 'root', rows: src[key] },
    { bucket: 'meta_room_audit', rows: src.meta?.room_audit?.[key] },
    { bucket: 'room_audit', rows: src.room_audit?.[key] },
    { bucket: 'payload', rows: src.payload?.[key] },
    { bucket: 'result', rows: src.result?.[key] },
    { bucket: 'data', rows: src.data?.[key] },
    { bucket: 'value', rows: src.value?.[key] },
    { bucket: 'payload_supervisor_fs_read', rows: src.payload?.supervisor_fs_read?.[key] },
    { bucket: 'payload_supervisor_notebook_write', rows: src.payload?.supervisor_notebook_write?.[key] },
    { bucket: 'supervisor_fs_read', rows: src.supervisor_fs_read?.[key] },
    { bucket: 'supervisor_notebook_write', rows: src.supervisor_notebook_write?.[key] },
    { bucket: 'payload_fs_context', rows: src.payload?.fs_context?.[key] },
    { bucket: 'payload_notebook_result', rows: src.payload?.notebook_result?.[key] },
    { bucket: 'payload_evidence_result', rows: src.payload?.evidence_result?.[key] },
    { bucket: 'fs_context', rows: src.fs_context?.[key] },
    { bucket: 'notebook_result', rows: src.notebook_result?.[key] },
    { bucket: 'evidence_result', rows: src.evidence_result?.[key] },
  ]

  let firstEmptyArray = null
  let firstEmptyBucket = ''

  for (const candidate of candidates) {
    const rows = candidate?.rows
    if (!Array.isArray(rows)) continue

    if (rows.length > 0) {
      return map_rows_with_source(rows, candidate.bucket)
    }

    if (!firstEmptyArray) {
      firstEmptyArray = rows
      firstEmptyBucket = candidate.bucket
    }
  }

  if (firstEmptyArray) {
    return map_rows_with_source(firstEmptyArray, firstEmptyBucket)
  }

  return []
}

function normalize_name_from_type(value) {
  const text = normalize_tool_name(value)
  if (!text) return ''

  const alias = map_alias_tool_name(text)
  if (alias) return alias

  const lower = text.toLowerCase()
  if (
    lower === 'tool_call' ||
    lower === 'tool_result' ||
    lower === 'call' ||
    lower === 'result' ||
    lower === 'function_call' ||
    lower === 'function_result'
  ) {
    return ''
  }

  return text
}

function get_raw_tool_call_id(item) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    const id = first_non_empty(
      src.id,
      src.tool_call_id,
      src.toolCallId,
      src.call_id,
      src.callId,
      src.request_id,
      src.requestId,
      src.trace_id,
      src.traceId,
      src.correlation_id,
      src.correlationId,
      src.tool_use_id,
      src.toolUseId,
      src.related_tool_call_id,
      src.relatedToolCallId,
      src.parent_tool_call_id,
      src.parentToolCallId
    )
    if (id) return id
  }

  return ''
}

function get_bucket_inferred_tool_name(item) {
  const bucket = safe_string(item?.__source_bucket).trim().toLowerCase()
  if (!bucket) return ''

  const aliasCandidates = [
    bucket,
    bucket.replace(/^payload_/, ''),
    bucket.replace(/^meta_/, ''),
  ]

  for (const candidate of aliasCandidates) {
    const alias = map_alias_tool_name(candidate)
    if (alias) return alias
  }

  return ''
}

function get_direct_tool_name(item) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    const direct = normalize_tool_name(
      first_non_empty(
        src.name,
        src.tool_name,
        src.toolName,
        src.tool,
        src.function_name,
        src.functionName,
        src.call_name,
        src.callName,
        src.source_tool_name,
        src.sourceToolName
      )
    )
    if (direct) return direct

    const aliasDirect = map_alias_tool_name(
      first_non_empty(
        src.type,
        src.kind,
        src.bucket,
        src.source_type,
        src.sourceType
      )
    )
    if (aliasDirect) return aliasDirect

    const byType = normalize_name_from_type(src.type)
    if (byType) return byType
  }

  const bucketName = get_bucket_inferred_tool_name(item)
  if (bucketName) return bucketName

  return ''
}

function first_preview_from_fields(item, fields) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    for (const field of fields) {
      const preview = stringify_preview(src[field])
      if (preview) return preview
    }
  }

  return ''
}

function get_argument_preview_text(item) {
  return first_preview_from_fields(item, [
    'arguments_preview',
    'arguments_json',
    'arguments',
    'args',
    'input_preview',
    'input_json',
    'input',
    'params',
    'parameters',
    'query',
  ])
}

function get_result_preview_text(item) {
  return first_preview_from_fields(item, [
    'result_preview',
    'result_json',
    'result',
    'output_preview',
    'output_json',
    'output',
    'response',
    'content',
    'message',
    'text',
  ])
}

function get_tool_preview_text(item) {
  return first_non_empty(
    get_argument_preview_text(item),
    get_result_preview_text(item)
  )
}

function get_summary_text(item, kind) {
  const direct = first_preview_from_fields(item, [
    'summary',
    'title',
    'description',
    'status_message',
    'statusMessage',
    'error_message',
    'errorMessage',
    'warning',
    'warning_message',
    'warningMessage',
  ])

  if (direct) return compact_preview(direct)

  const argumentPreview = get_argument_preview_text(item)
  const resultPreview = get_result_preview_text(item)

  if (kind === 'tool_call') return compact_preview(argumentPreview || resultPreview)
  return compact_preview(resultPreview || argumentPreview)
}

function normalize_internal_type_token(value) {
  return safe_string(value).trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function should_hide_tool_activity_row(item) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    const tokens = [
      src.type,
      src.kind,
      src.name,
      src.tool_name,
      src.toolName,
      src.source_tool_name,
      src.sourceToolName,
      src.bridge,
    ]

    for (const token of tokens) {
      const normalized = normalize_internal_type_token(token)
      if (!normalized) continue
      if (INTERNAL_ACTIVITY_TYPES.has(normalized)) return true
      if (normalized.endsWith('_bridge') && normalized.startsWith('room_')) return true
    }
  }

  return false
}

function build_name_lookup(tool_calls, tool_results) {
  const lookup = new Map()

  for (const item of [...safe_array(tool_calls), ...safe_array(tool_results)]) {
    const id = get_raw_tool_call_id(item)
    const name = get_direct_tool_name(item)
    if (id && name && !lookup.has(id)) {
      lookup.set(id, name)
    }
  }

  return lookup
}

function find_name_by_index(rows, index) {
  if (!Number.isInteger(index)) return ''
  if (index < 0 || index >= rows.length) return ''
  return get_direct_tool_name(rows[index])
}

function infer_tool_name(item, own_rows, peer_rows, lookup) {
  const direct = get_direct_tool_name(item)
  if (direct) return direct

  const src = safe_object(item)
  const ownId = get_raw_tool_call_id(src)
  if (ownId && lookup.has(ownId)) {
    return lookup.get(ownId)
  }

  const relatedId = first_non_empty(
    src.tool_call_id,
    src.toolCallId,
    src.call_id,
    src.callId,
    src.request_id,
    src.requestId,
    src.trace_id,
    src.traceId,
    src.correlation_id,
    src.correlationId,
    src.tool_use_id,
    src.toolUseId,
    src.related_tool_call_id,
    src.relatedToolCallId,
    src.parent_tool_call_id,
    src.parentToolCallId
  )
  if (relatedId && lookup.has(relatedId)) {
    return lookup.get(relatedId)
  }

  const sameIndexOwn = find_name_by_index(own_rows, src.__source_index)
  if (sameIndexOwn) return sameIndexOwn

  const sameIndexPeer = find_name_by_index(peer_rows, src.__source_index)
  if (sameIndexPeer) return sameIndexPeer

  if (peer_rows.length === 1) {
    const onlyPeerName = get_direct_tool_name(peer_rows[0])
    if (onlyPeerName) return onlyPeerName
  }

  if (own_rows.length === 1) {
    const onlyOwnName = get_direct_tool_name(own_rows[0])
    if (onlyOwnName) return onlyOwnName
  }

  const bucketName = get_bucket_inferred_tool_name(src)
  if (bucketName) return bucketName

  return UNKNOWN_TOOL_NAME
}

function first_machine_field(item, fields) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    for (const field of fields) {
      const text = safe_string(src[field]).trim()
      if (text) return text
    }
  }

  return ''
}

function infer_role_token(item) {
  const direct = normalize_internal_type_token(
    first_machine_field(item, [
      'role',
      'actor',
      'runtime_role',
      'runtimeRole',
      'executor_role',
      'executorRole',
      'worker_role',
      'workerRole',
      'source_role',
      'sourceRole',
    ])
  )

  if (direct.includes('supervisor')) return 'supervisor'
  if (direct.includes('worker')) return 'worker'
  if (direct.includes('provider')) return 'provider'
  if (direct.includes('room')) return 'room'
  if (direct.includes('assistant')) return 'assistant'

  const bucket = normalize_internal_type_token(item?.__source_bucket)
  const name = normalize_internal_type_token(get_direct_tool_name(item))

  if (bucket.includes('supervisor') || name.includes('supervisor')) return 'supervisor'
  if (bucket.includes('worker') || name.includes('worker')) return 'worker'
  if (bucket.includes('provider') || name.includes('provider')) return 'provider'

  return 'tool'
}

function role_label(role_token) {
  if (role_token === 'supervisor') return 'Supervisor'
  if (role_token === 'worker') return 'Worker'
  if (role_token === 'provider') return 'Provider'
  if (role_token === 'room') return 'Room'
  if (role_token === 'assistant') return 'Assistant'
  return 'Tool'
}

function kind_label(kind) {
  return kind === 'tool_call' ? 'Call' : 'Result'
}

function kind_i18n_key(kind) {
  return kind === 'tool_call'
    ? 'chat.toolActivity.kind.call'
    : 'chat.toolActivity.kind.result'
}

function role_i18n_key(role_token) {
  if (role_token === 'supervisor') return 'chat.toolActivity.role.supervisor'
  if (role_token === 'worker') return 'chat.toolActivity.role.worker'
  if (role_token === 'provider') return 'chat.toolActivity.role.provider'
  if (role_token === 'room') return 'chat.toolActivity.role.room'
  if (role_token === 'assistant') return 'chat.toolActivity.role.assistant'
  return 'chat.toolActivity.role.tool'
}

function get_status_token_from_item(item, kind) {
  const status = first_machine_field(item, [
    'status',
    'state',
    'phase',
    'outcome',
    'result_status',
    'resultStatus',
  ])

  return normalize_status_token(status, kind === 'tool_call' ? 'running' : 'done')
}

function has_any_array(item, keys) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    for (const key of keys) {
      if (Array.isArray(src[key]) && src[key].length > 0) return true
    }
  }

  return false
}

function has_any_field(item, keys) {
  const candidates = collect_object_candidates(item)

  for (const src of candidates) {
    for (const key of keys) {
      const value = src[key]
      if (Array.isArray(value) && value.length > 0) return true
      if (value && typeof value === 'object' && !is_empty_object(value)) return true
      if (safe_string(value).trim()) return true
    }
  }

  return false
}

function has_error_signal(item, status_token) {
  if (normalize_status_token(status_token) === 'error') return true

  return has_any_field(item, [
    'error',
    'error_text',
    'errorText',
    'error_message',
    'errorMessage',
    'exception',
  ])
}

function has_warning_signal(item, status_token) {
  if (normalize_status_token(status_token) === 'warning') return true

  return has_any_field(item, [
    'warning',
    'warnings',
    'warning_text',
    'warningText',
    'warning_message',
    'warningMessage',
  ])
}

function strip_internal_fields(item) {
  const raw = safe_object(item)
  const result = {}

  for (const [key, value] of Object.entries(raw)) {
    if (key.startsWith('__')) continue
    if (key.startsWith('_')) continue
    result[key] = value
  }

  return result
}

function build_machine_fields(item) {
  return {
    provider_id: first_machine_field(item, ['provider_id', 'providerId']),
    artifact_id: first_machine_field(item, ['artifact_id', 'artifactId']),
    source_room_id: first_machine_field(item, ['source_room_id', 'sourceRoomId']),
    request_id: first_machine_field(item, ['request_id', 'requestId']),
    trace_id: first_machine_field(item, ['trace_id', 'traceId']),
    call_id: first_machine_field(item, ['tool_call_id', 'toolCallId', 'call_id', 'callId']),
    grant_id: first_machine_field(item, ['grant_id', 'grantId']),
    share_ref: first_machine_field(item, ['share_ref', 'shareRef']),
  }
}

function build_flags(item, status_token) {
  return {
    has_error: has_error_signal(item, status_token),
    has_warning: has_warning_signal(item, status_token),
    has_citations: has_any_array(item, ['citations', 'references', 'source_citations', 'sourceCitations']),
    has_sources: has_any_array(item, ['sources', 'source_cards', 'sourceCards', 'rss_evidence', 'market_evidence']),
    has_artifacts: has_any_array(item, ['artifacts', 'artifact_refs', 'artifactRefs']) || has_any_field(item, ['artifact_id', 'artifactId']),
    has_external_result_view: has_any_field(item, ['external_result_view', 'externalResultView']),
    has_trace: has_any_field(item, ['trace', 'debug_trace', 'debugTrace', 'runtime_log', 'runtimeLog']),
    has_raw_payload: Object.keys(strip_internal_fields(item)).length > 0,
  }
}

function build_tool_rows(source, kind) {
  const tool_calls = collect_array_from_candidates(source, 'tool_calls')
  const tool_results = collect_array_from_candidates(source, 'tool_results')
  const rows = kind === 'tool_call' ? tool_calls : tool_results
  const peers = kind === 'tool_call' ? tool_results : tool_calls
  const lookup = build_name_lookup(tool_calls, tool_results)

  return rows
    .filter((row) => !should_hide_tool_activity_row(row))
    .map((row, idx) => {
      const status_token = get_status_token_from_item(row, kind)
      const role_token = infer_role_token(row)
      const machine_fields = build_machine_fields(row)
      const flags = build_flags(row, status_token)

      return {
        ...safe_object(row),
        _kind: kind,
        _kind_text: kind_label(kind),
        _kind_i18n_key: kind_i18n_key(kind),
        _key: normalize_tool_key(kind, row, idx),
        _display_name: infer_tool_name(row, rows, peers, lookup),
        _role_token: role_token,
        _role_text: role_label(role_token),
        _role_i18n_key: role_i18n_key(role_token),
        _preview_text: compact_preview(get_tool_preview_text(row)),
        _argument_preview_text: compact_preview(get_argument_preview_text(row)),
        _result_preview_text: compact_preview(get_result_preview_text(row)),
        _summary_text: get_summary_text(row, kind),
        _status_token: status_token || (kind === 'tool_call' ? 'running' : 'done'),
        _status_text: format_tool_status_label(
          status_token,
          kind === 'tool_call' ? 'Running' : 'Done'
        ),
        _status_i18n_key: status_i18n_key(status_token),
        _machine_fields: machine_fields,
        _flags: flags,
        _raw_payload: strip_internal_fields(row),
      }
    })
}

export function use_chat_panel_tool_activity_presenter() {
  function get_tool_call_rows(source) {
    return build_tool_rows(source, 'tool_call')
  }

  function get_tool_result_rows(source) {
    return build_tool_rows(source, 'tool_result')
  }

  function has_tool_activity(source) {
    return (
      get_tool_call_rows(source).length > 0 ||
      get_tool_result_rows(source).length > 0
    )
  }

  function get_tool_display_name(item) {
    return safe_string(item?._display_name || UNKNOWN_TOOL_NAME).trim() || UNKNOWN_TOOL_NAME
  }

  function get_tool_preview(item) {
    return safe_string(item?._preview_text || '').trim()
  }

  function get_tool_summary(item) {
    return safe_string(item?._summary_text || item?._preview_text || '').trim()
  }

  function get_tool_status_text(item) {
    return safe_string(item?._status_text || '').trim()
  }

  function get_tool_status_i18n_key(item) {
    return safe_string(item?._status_i18n_key || status_i18n_key(item?._status_token || item?.status)).trim()
  }

  function get_tool_role_text(item) {
    return safe_string(item?._role_text || role_label(item?._role_token)).trim()
  }

  function get_tool_role_i18n_key(item) {
    return safe_string(item?._role_i18n_key || role_i18n_key(item?._role_token)).trim()
  }

  function get_tool_kind_i18n_key(item) {
    return safe_string(item?._kind_i18n_key || kind_i18n_key(item?._kind)).trim()
  }

  function get_tool_status_class(item) {
    const token = normalize_status_token(item?._status_token || item?.status)
    if (token === 'done') return 'done'
    if (token === 'warning') return 'warning'
    if (token === 'error') return 'error'
    if (token === 'cancelled') return 'cancelled'
    return 'running'
  }

  function get_tool_machine_fields(item) {
    return safe_object(item?._machine_fields)
  }

  function get_tool_flags(item) {
    return safe_object(item?._flags)
  }

  function get_tool_raw_payload(item) {
    return safe_object(item?._raw_payload)
  }

  return {
    has_tool_activity,
    get_tool_call_rows,
    get_tool_result_rows,
    get_tool_display_name,
    get_tool_preview,
    get_tool_summary,
    get_tool_status_text,
    get_tool_status_i18n_key,
    get_tool_role_text,
    get_tool_role_i18n_key,
    get_tool_kind_i18n_key,
    get_tool_status_class,
    get_tool_machine_fields,
    get_tool_flags,
    get_tool_raw_payload,
  }
}
