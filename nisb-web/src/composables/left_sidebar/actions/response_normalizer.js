function isPlainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function toSafeObject(value) {
  return isPlainObject(value) ? value : {}
}

function toSafeArray(value) {
  return Array.isArray(value) ? value : []
}

function hasOwn(value, key) {
  return !!value && Object.prototype.hasOwnProperty.call(value, key)
}

function isNonEmptyObject(value) {
  return isPlainObject(value) && Object.keys(value).length > 0
}

function isNonEmptyArray(value) {
  return Array.isArray(value) && value.length > 0
}

function firstNonEmptyString(...values) {
  for (const v of values) {
    const s = String(v || '').trim()
    if (s) return s
  }
  return ''
}

const LOGICAL_MODULE_ORDER = ['chat', 'dirs', 'files', 'library']

function normalizeModuleKey(value) {
  const key = String(value || '').trim().toLowerCase()
  if (!key) return ''
  if (key === 'chat') return 'chat'
  if (key === 'dirs') return 'dirs'
  if (key === 'doc' || key === 'files' || key === 'agent_files') return 'files'
  if (key === 'library') return 'library'
  return ''
}

function inferModuleFromItem(item, fallback = '') {
  const direct = normalizeModuleKey(
    item?.module ||
    item?.raw_module ||
    item?.source_module ||
    fallback
  )
  if (direct) return direct

  const sourceKind = String(item?.source_kind || '').toLowerCase()
  if (sourceKind.startsWith('chat_')) return 'chat'
  if (sourceKind.startsWith('dirs_')) return 'dirs'
  if (sourceKind.startsWith('library_')) return 'library'
  if (sourceKind.startsWith('doc_') || sourceKind.startsWith('files_')) return 'files'

  return ''
}

function normalizeItem(item, fallbackModule = '') {
  const obj = toSafeObject(item)
  const module = inferModuleFromItem(obj, fallbackModule)

  const normalized = {
    ...obj
  }

  if (module) normalized.module = module

  if (!normalized.__key) {
    normalized.__key =
      normalized.item_key ||
      normalized.id ||
      normalized.conv_id ||
      normalized.doc_id ||
      normalized.path ||
      `${module || 'item'}::${normalized.title || normalized.filename || 'unknown'}`
  }

  return normalized
}

function createEmptyGrouped() {
  return {
    chat: { results: [], items: [], total: 0 },
    dirs: { results: [], items: [], total: 0 },
    files: { results: [], items: [], total: 0 },
    library: { results: [], items: [], total: 0 }
  }
}

function extractGroupItems(groupPayload, module) {
  if (Array.isArray(groupPayload)) {
    return groupPayload.map((item) => normalizeItem(item, module))
  }

  const obj = toSafeObject(groupPayload)

  if (Array.isArray(obj.results)) {
    return obj.results.map((item) => normalizeItem(item, module))
  }

  if (Array.isArray(obj.items)) {
    return obj.items.map((item) => normalizeItem(item, module))
  }

  return []
}

function normalizeGroupPayload(groupPayload, module) {
  const items = extractGroupItems(groupPayload, module)
  return {
    ...toSafeObject(groupPayload),
    results: items,
    items,
    total: items.length
  }
}

function normalizeGrouped(groupedValue) {
  const grouped = createEmptyGrouped()
  const rawGrouped = toSafeObject(groupedValue)

  for (const [rawModule, payload] of Object.entries(rawGrouped)) {
    const module = normalizeModuleKey(rawModule)
    if (!module) continue
    grouped[module] = normalizeGroupPayload(payload, module)
  }

  return grouped
}

function bucketItemsToGrouped(itemsValue) {
  const grouped = createEmptyGrouped()
  const items = toSafeArray(itemsValue)

  for (const rawItem of items) {
    const item = normalizeItem(rawItem)
    const module = normalizeModuleKey(item.module)
    if (!module || !grouped[module]) continue
    grouped[module].items.push(item)
    grouped[module].results.push(item)
  }

  for (const module of LOGICAL_MODULE_ORDER) {
    grouped[module].total = grouped[module].items.length
  }

  return grouped
}

function flattenGrouped(grouped) {
  const out = []
  for (const module of LOGICAL_MODULE_ORDER) {
    const items = toSafeArray(grouped?.[module]?.items)
    for (const item of items) out.push(item)
  }
  return out
}

function buildGroupedCompat(grouped) {
  const out = {}
  for (const module of LOGICAL_MODULE_ORDER) {
    out[module] = {
      results: toSafeArray(grouped?.[module]?.items),
      items: toSafeArray(grouped?.[module]?.items),
      total: Number(grouped?.[module]?.total || 0)
    }
  }
  return out
}

function buildTotals(grouped) {
  const totals = {}
  for (const module of LOGICAL_MODULE_ORDER) {
    totals[module] = Number(grouped?.[module]?.total || 0)
  }
  return totals
}

function hasLogicalTotals(value) {
  const totals = toSafeObject(value)
  return LOGICAL_MODULE_ORDER.some((module) => totals[module] !== undefined)
}

function hasSearchTaggedItems(itemsValue) {
  const items = toSafeArray(itemsValue)
  return items.some((item) => {
    const obj = toSafeObject(item)
    return !!inferModuleFromItem(obj)
  })
}

function isFormalChatPayload(value) {
  const obj = toSafeObject(value)
  if (!isNonEmptyObject(obj)) return false

  const hasFormalKeys =
    hasOwn(obj, 'response') ||
    hasOwn(obj, 'request_id') ||
    hasOwn(obj, 'conv_id') ||
    hasOwn(obj, 'tool_calls') ||
    hasOwn(obj, 'tool_results') ||
    hasOwn(obj, 'rss_evidence') ||
    hasOwn(obj, 'market_evidence') ||
    hasOwn(obj, 'evidence_query') ||
    hasOwn(obj, 'evidence_tools') ||
    hasOwn(obj, 'evidence_result') ||
    hasOwn(obj, 'citations')

  return !!hasFormalKeys
}

function isSearchPayloadLike(value) {
  const obj = toSafeObject(value)
  if (!isPlainObject(obj) || Object.keys(obj).length === 0) return false

  if (isPlainObject(obj.grouped)) return true
  if (isPlainObject(obj.grouped_results)) return true

  if (typeof obj.query_norm === 'string' && obj.query_norm.trim()) return true
  if (typeof obj.query_compact === 'string' && obj.query_compact.trim()) return true
  if (Array.isArray(obj.query_tokens) && obj.query_tokens.length > 0) return true
  if (Array.isArray(obj.requested_modules) && obj.requested_modules.length > 0) return true
  if (Array.isArray(obj.raw_modules) && obj.raw_modules.length > 0) return true

  if (isPlainObject(obj.sync) && Object.keys(obj.sync).length > 0) return true
  if (hasLogicalTotals(obj.totals)) return true

  if (Array.isArray(obj.results) && hasSearchTaggedItems(obj.results)) return true
  if (Array.isArray(obj.items) && hasSearchTaggedItems(obj.items)) return true

  return false
}

function normalizeSearchPayload(data) {
  const base = toSafeObject(data)

  let grouped = null

  if (isPlainObject(base.grouped)) {
    grouped = normalizeGrouped(base.grouped)
  } else if (isPlainObject(base.grouped_results)) {
    grouped = normalizeGrouped(base.grouped_results)
  } else if (Array.isArray(base.results)) {
    grouped = bucketItemsToGrouped(base.results)
  } else if (Array.isArray(base.items)) {
    grouped = bucketItemsToGrouped(base.items)
  } else {
    grouped = createEmptyGrouped()
  }

  const groupedResults = buildGroupedCompat(grouped)
  const results = flattenGrouped(grouped)
  const totals = buildTotals(grouped)
  const total = LOGICAL_MODULE_ORDER.reduce((sum, module) => sum + Number(totals[module] || 0), 0)

  return {
    ...base,
    grouped,
    grouped_results: groupedResults,
    results,
    items: results,
    totals,
    total
  }
}

function extractResultPayloadCandidates(entry) {
  const obj = toSafeObject(entry)
  const out = []

  const maybePush = (value) => {
    if (isPlainObject(value) && Object.keys(value).length > 0) out.push(value)
  }

  maybePush(obj.data)
  maybePush(obj.result)
  maybePush(obj.payload)
  maybePush(obj.value)
  maybePush(obj.evidence_result)

  if (isPlainObject(obj.raw)) maybePush(obj.raw)
  if (isPlainObject(obj.raw_data)) maybePush(obj.raw_data)

  return out
}

function normalizeToolResultEntry(entry) {
  const obj = toSafeObject(entry)
  const payloadCandidates = extractResultPayloadCandidates(obj)
  const primaryPayload = payloadCandidates[0] || {}

  return {
    ...obj,
    data: isNonEmptyObject(obj.data) ? obj.data : primaryPayload,
    result: isNonEmptyObject(obj.result) ? obj.result : primaryPayload,
    payload: isNonEmptyObject(obj.payload) ? obj.payload : primaryPayload,
    value: isNonEmptyObject(obj.value) ? obj.value : primaryPayload
  }
}

function normalizeToolResults(raw) {
  const direct = toSafeArray(raw?.tool_results).map(normalizeToolResultEntry).filter((x) => isPlainObject(x))
  if (direct.length > 0) return direct

  const nestedData = toSafeArray(raw?.data?.tool_results).map(normalizeToolResultEntry).filter((x) => isPlainObject(x))
  if (nestedData.length > 0) return nestedData

  const nestedResult = toSafeArray(raw?.result?.tool_results).map(normalizeToolResultEntry).filter((x) => isPlainObject(x))
  if (nestedResult.length > 0) return nestedResult

  const nestedPayload = toSafeArray(raw?.payload?.tool_results).map(normalizeToolResultEntry).filter((x) => isPlainObject(x))
  if (nestedPayload.length > 0) return nestedPayload

  return []
}

function flattenPayloadCandidates(raw, firstToolResult) {
  const out = []

  const maybePush = (value) => {
    if (isPlainObject(value) && Object.keys(value).length > 0) out.push(value)
  }

  maybePush(firstToolResult?.data)
  maybePush(firstToolResult?.result)
  maybePush(firstToolResult?.payload)
  maybePush(firstToolResult?.value)

  maybePush(raw?.data)
  maybePush(raw?.result)
  maybePush(raw?.payload)
  maybePush(raw?.evidence_result)

  maybePush(raw)

  return out
}

function pickPrimaryPayload(raw, firstToolResult) {
  const candidates = flattenPayloadCandidates(raw, firstToolResult)

  for (const candidate of candidates) {
    if (isSearchPayloadLike(candidate)) return candidate
  }

  for (const candidate of candidates) {
    if (isFormalChatPayload(candidate)) return candidate
  }

  for (const candidate of candidates) {
    if (isNonEmptyObject(candidate)) return candidate
  }

  return {}
}

function normalizeStatusToken(value) {
  const s = String(value || '').trim().toLowerCase()
  if (!s) return ''

  if (s === 'ok' || s === 'success' || s === 'succeeded') return 'success'
  if (s === 'warning' || s === 'partial_success' || s === 'partial_error') return 'warning'
  if (s === 'error' || s === 'failed' || s === 'fail') return 'error'

  return s
}

function deriveStatus(raw, data, firstToolResult) {
  const candidates = [
    data?.status,
    raw?.status,
    raw?.data?.status,
    raw?.result?.status,
    raw?.payload?.status,
    firstToolResult?.status,
    firstToolResult?.data?.status,
    firstToolResult?.result?.status,
    firstToolResult?.payload?.status
  ]

  for (const candidate of candidates) {
    const normalized = normalizeStatusToken(candidate)
    if (normalized === 'success' || normalized === 'warning' || normalized === 'error') {
      return normalized
    }
  }

  const successCandidates = [
    data?.success,
    raw?.success,
    raw?.data?.success,
    raw?.result?.success,
    raw?.payload?.success,
    firstToolResult?.success,
    firstToolResult?.data?.success,
    firstToolResult?.result?.success,
    firstToolResult?.payload?.success
  ]

  if (successCandidates.some((v) => v === true)) return 'success'
  if (successCandidates.some((v) => v === false)) return 'error'

  if (isFormalChatPayload(data) && normalizeStatusToken(data?.status) !== 'error') {
    return 'success'
  }

  return 'error'
}

function mergeFormalFields(raw, base, toolResults) {
  const source = toSafeObject(base)
  const firstToolResult = toolResults[0] || {}

  const firstPayload =
    toSafeObject(firstToolResult?.data) ||
    toSafeObject(firstToolResult?.result) ||
    toSafeObject(firstToolResult?.payload) ||
    toSafeObject(firstToolResult?.value)

  const merged = {
    ...toSafeObject(raw),
    ...source
  }

  const assignIfMissing = (key, fallbackValue) => {
    if (merged[key] === undefined || merged[key] === null || merged[key] === '') {
      merged[key] = fallbackValue
    }
  }

  assignIfMissing('request_id', firstNonEmptyString(source.request_id, raw.request_id, firstPayload.request_id))
  assignIfMissing('conv_id', firstNonEmptyString(source.conv_id, raw.conv_id, firstPayload.conv_id))
  assignIfMissing('rag_mode', firstNonEmptyString(source.rag_mode, raw.rag_mode, firstPayload.rag_mode))
  assignIfMissing('mode_used', firstNonEmptyString(source.mode_used, raw.mode_used, firstPayload.mode_used))
  assignIfMissing('qa_id', firstNonEmptyString(source.qa_id, raw.qa_id, firstPayload.qa_id))
  assignIfMissing('group_id', firstNonEmptyString(source.group_id, raw.group_id, firstPayload.group_id))
  assignIfMissing('evidence_query', firstNonEmptyString(source.evidence_query, raw.evidence_query, firstPayload.evidence_query))

  if (!isPlainObject(merged.mcp_overrides)) {
    merged.mcp_overrides =
      toSafeObject(source.mcp_overrides) ||
      toSafeObject(raw.mcp_overrides) ||
      toSafeObject(firstPayload.mcp_overrides)
  }

  if (!Array.isArray(merged.tool_results)) {
    merged.tool_results = toolResults
  }

  if (!Array.isArray(merged.tool_calls)) {
    merged.tool_calls = toSafeArray(source.tool_calls)
  }

  if (!Array.isArray(merged.citations)) {
    merged.citations = toSafeArray(source.citations)
  }

  if (!Array.isArray(merged.rss_evidence)) {
    merged.rss_evidence = toSafeArray(source.rss_evidence)
  }

  if (!Array.isArray(merged.market_evidence)) {
    merged.market_evidence = toSafeArray(source.market_evidence)
  }

  if (!Array.isArray(merged.evidence_tools)) {
    merged.evidence_tools = toSafeArray(source.evidence_tools)
  }

  if (!isPlainObject(merged.evidence_result)) {
    merged.evidence_result = toSafeObject(source.evidence_result)
  }

  if (!hasOwn(merged, 'response')) {
    merged.response = firstNonEmptyString(source.response, raw.response, firstPayload.response)
  }

  if (!hasOwn(merged, 'message')) {
    merged.message = firstNonEmptyString(source.message, raw.message, firstPayload.message)
  }

  return merged
}

function pickFirstStructuredToolPayload(toolResults) {
  for (const item of toSafeArray(toolResults)) {
    const candidates = [
      item?.data,
      item?.result,
      item?.payload,
      item?.value
    ]
    for (const c of candidates) {
      if (isPlainObject(c) && Object.keys(c).length > 0) return c
    }
  }
  return {}
}

function buildMergedData(raw, primaryPayload, toolResults) {
  const firstStructuredToolPayload = pickFirstStructuredToolPayload(toolResults)

  const mergedBase = {
    ...toSafeObject(raw),
    ...toSafeObject(primaryPayload),
    tool_results: toolResults
  }

  const mergedWithToolPayload =
    isSearchPayloadLike(firstStructuredToolPayload) || isFormalChatPayload(firstStructuredToolPayload)
      ? {
          ...mergedBase,
          ...toSafeObject(firstStructuredToolPayload),
          tool_results: toolResults
        }
      : mergedBase

  const mergedFormal = mergeFormalFields(raw, mergedWithToolPayload, toolResults)

  if (isSearchPayloadLike(mergedFormal)) {
    return normalizeSearchPayload(mergedFormal)
  }

  return mergedFormal
}

export function normalizeToolResponse(res, fallbackText = '操作完成') {
  const raw = isPlainObject(res) ? res : {}
  const toolResults = normalizeToolResults(raw)
  const firstToolResult = toolResults[0] || null
  const primaryPayload = pickPrimaryPayload(raw, firstToolResult)
  const data = buildMergedData(raw, primaryPayload, toolResults)

  const response = firstNonEmptyString(
    data.response,
    raw.response,
    raw?.data?.response,
    raw?.result?.response,
    raw?.payload?.response,
    firstToolResult?.data?.response,
    firstToolResult?.result?.response,
    firstToolResult?.payload?.response,
    firstToolResult?.value?.response
  )

  const message = firstNonEmptyString(
    data.message,
    raw.message,
    raw?.data?.message,
    raw?.result?.message,
    raw?.payload?.message,
    firstToolResult?.message,
    firstToolResult?.data?.message,
    firstToolResult?.result?.message,
    firstToolResult?.payload?.message,
    firstToolResult?.value?.message
  )

  const text = response || message || fallbackText
  const status = deriveStatus(raw, data, firstToolResult)

  return {
    raw,
    status,
    success: status === 'success' || status === 'warning',
    isWarning: status === 'warning',
    isError: status === 'error',
    response,
    message,
    text,
    toolResults,
    firstToolResult,
    data
  }
}

export function pickDataObject(res, fallback = {}) {
  const info = normalizeToolResponse(res)
  if (isPlainObject(info.data)) return info.data
  return isPlainObject(fallback) ? fallback : {}
}

export function pickGroupedObject(res, fallback = null) {
  const info = normalizeToolResponse(res)
  if (isPlainObject(info.data?.grouped)) return info.data.grouped
  return isPlainObject(fallback) ? fallback : createEmptyGrouped()
}

export function pickDataValue(res, key, fallback = null) {
  const info = normalizeToolResponse(res)

  if (info.data && info.data[key] !== undefined) return info.data[key]

  const raw = info.raw || {}

  if (raw[key] !== undefined) return raw[key]
  if (isPlainObject(raw.data) && raw.data[key] !== undefined) return raw.data[key]
  if (isPlainObject(raw.result) && raw.result[key] !== undefined) return raw.result[key]
  if (isPlainObject(raw.payload) && raw.payload[key] !== undefined) return raw.payload[key]

  const firstToolData = isPlainObject(info.firstToolResult?.data) ? info.firstToolResult.data : {}
  if (firstToolData[key] !== undefined) return firstToolData[key]

  const firstToolResultPayload = isPlainObject(info.firstToolResult?.result) ? info.firstToolResult.result : {}
  if (firstToolResultPayload[key] !== undefined) return firstToolResultPayload[key]

  const firstToolPayloadPayload = isPlainObject(info.firstToolResult?.payload) ? info.firstToolResult.payload : {}
  if (firstToolPayloadPayload[key] !== undefined) return firstToolPayloadPayload[key]

  const firstToolValuePayload = isPlainObject(info.firstToolResult?.value) ? info.firstToolResult.value : {}
  if (firstToolValuePayload[key] !== undefined) return firstToolValuePayload[key]

  return fallback
}

export function pickDataArray(res, key, fallback = []) {
  const info = normalizeToolResponse(res)

  if (Array.isArray(info.data?.[key])) return info.data[key]

  const raw = info.raw || {}

  if (Array.isArray(raw[key])) return raw[key]
  if (Array.isArray(raw?.data?.[key])) return raw.data[key]
  if (Array.isArray(raw?.result?.[key])) return raw.result[key]
  if (Array.isArray(raw?.payload?.[key])) return raw.payload[key]

  const firstToolData = isPlainObject(info.firstToolResult?.data) ? info.firstToolResult.data : {}
  if (Array.isArray(firstToolData?.[key])) return firstToolData[key]

  const firstToolResultPayload = isPlainObject(info.firstToolResult?.result) ? info.firstToolResult.result : {}
  if (Array.isArray(firstToolResultPayload?.[key])) return firstToolResultPayload[key]

  const firstToolPayloadPayload = isPlainObject(info.firstToolResult?.payload) ? info.firstToolResult.payload : {}
  if (Array.isArray(firstToolPayloadPayload?.[key])) return firstToolPayloadPayload[key]

  const firstToolValuePayload = isPlainObject(info.firstToolResult?.value) ? info.firstToolResult.value : {}
  if (Array.isArray(firstToolValuePayload?.[key])) return firstToolValuePayload[key]

  return Array.isArray(fallback) ? fallback : []
}
