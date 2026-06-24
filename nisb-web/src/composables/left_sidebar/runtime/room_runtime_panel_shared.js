export function safeArray(value) {
  return Array.isArray(value) ? value : []
}

export function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

export function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

export function safeNumber(value, fallback = 0) {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed || trimmed.toLowerCase() === 'null' || trimmed.toLowerCase() === 'undefined') {
      return fallback
    }
  }
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

export function safeBoolean(value, fallback = false) {
  if (typeof value === 'boolean') return value
  const token = safeString(value).trim().toLowerCase()
  if (!token) return fallback
  if (['1', 'true', 'yes', 'on'].includes(token)) return true
  if (['0', 'false', 'no', 'off'].includes(token)) return false
  return fallback
}

export function normalizeToken(value) {
  return safeString(value).trim().toLowerCase()
}

export function normalizeRuntimeViewMode(value) {
  return normalizeToken(value) === 'replay' ? 'replay' : 'current'
}

export function normalizeRuntimePayload(value) {
  const src = safeObject(value)
  const candidates = [src.payload, src.data, src.result, src.value, src]
  for (const candidate of candidates) {
    const obj = safeObject(candidate)
    if (Object.keys(obj).length) return obj
  }
  return {}
}

export function translateWithFallback(t, key, fallback, params = {}) {
  const translated = safeString(t(key, params)).trim()
  if (translated && translated !== key) return translated
  return fallback
}

export function getRuntimeTimeText(item) {
  const raw = safeString(item?.ts || item?.created_at || item?.updated_at).trim()
  if (!raw) return ''
  try {
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) return ''
    return d.toTimeString().slice(0, 5)
  } catch {
    return ''
  }
}

export function normalizeSummaryObject(raw, sourceType = '') {
  if (!raw) return {}

  if (typeof raw === 'string') {
    const text = raw.trim()
    return text
      ? {
          has_skills: true,
          summary_text: text,
          source_type: sourceType,
        }
      : {}
  }

  if (typeof raw !== 'object' || Array.isArray(raw)) return {}

  return {
    ...raw,
    source_type: safeString(raw.source_type).trim() || sourceType,
  }
}

export function readSummaryText(raw) {
  if (!raw) return ''
  if (typeof raw === 'string') return raw.trim()
  if (typeof raw !== 'object' || Array.isArray(raw)) return ''
  return safeString(raw.summary_text || raw.message || raw.status_text || raw.status).trim()
}

export function hasObjectContent(raw) {
  return !!readSummaryText(raw) || Object.keys(safeObject(raw)).length > 0
}

export function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key)
}

export function hasUsableValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return !!value.trim()
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

export function hasPresentValue(obj, key) {
  if (!obj || typeof obj !== 'object') return false
  if (!hasOwn(obj, key)) return false
  const value = obj[key]
  if (typeof value === 'boolean' || typeof value === 'number') return true
  return hasUsableValue(value)
}

export function readCandidateValue(candidates, keys = []) {
  for (const candidate of safeArray(candidates)) {
    const row = safeObject(candidate)
    for (const key of keys) {
      if (!key || !hasOwn(row, key)) continue
      const value = row[key]
      if (hasUsableValue(value)) return value
      if (typeof value === 'boolean' || typeof value === 'number') return value
    }
  }
  return undefined
}

export function readCandidateRaw(candidates, keys = []) {
  for (const candidate of safeArray(candidates)) {
    const row = safeObject(candidate)
    for (const key of keys) {
      if (!key || !hasPresentValue(row, key)) continue
      return row[key]
    }
  }
  return undefined
}

export function readCandidateString(candidates, keys = []) {
  const value = readCandidateRaw(candidates, keys)
  if (value === undefined || value === null) return ''
  return safeString(value).trim()
}

export function readCandidateBoolean(candidates, keys = []) {
  const value = readCandidateRaw(candidates, keys)
  if (value === undefined) return undefined
  return safeBoolean(value, false)
}

export function readCandidateNumber(candidates, keys = []) {
  const value = readCandidateRaw(candidates, keys)
  if (value === undefined) return undefined
  return safeNumber(value, 0)
}

export function readCandidateArray(candidates, keys = []) {
  const value = readCandidateRaw(candidates, keys)
  if (value === undefined) return []
  return safeArray(value)
}

export function collectNestedObjects(value, bucket = []) {
  const row = safeObject(value)
  if (!Object.keys(row).length) return bucket

  bucket.push(row)

  const nestedKeys = [
    'payload',
    'data',
    'result',
    'value',
    'runtime_control_snapshot',
    'control_snapshot',
    'formal_runtime_packet',
    'current_formal_runtime_packet',
    'packet',
    'event',
  ]

  for (const key of nestedKeys) {
    const nested = safeObject(row[key])
    if (Object.keys(nested).length) {
      collectNestedObjects(nested, bucket)
    }
  }

  return bucket
}

export function collectToolResultObjects(value) {
  const root = safeObject(value)
  const rows = []

  const toolResults = safeArray(root.tool_results || root.results || root.items)

  for (const item of toolResults) {
    const row = safeObject(item)
    if (!Object.keys(row).length) continue
    rows.push(row)

    const payload = normalizeRuntimePayload(row.payload || row.result || row.data || row.value)
    if (Object.keys(payload).length) rows.push(payload)
  }

  return rows
}

export function preferDefined(primary, fallback) {
  return primary === undefined ? fallback : primary
}

export function humanizeToken(value) {
  return safeString(value).trim().replace(/_/g, ' ')
}

export function truncateText(value, limit = 220) {
  const text = safeString(value).trim()
  if (!text) return ''
  if (text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 1)).trim()}…`
}

export function toSentence(value) {
  const text = safeString(value).trim()
  if (!text) return ''
  return /[。！？!?.]$/.test(text) ? text : `${text}.`
}

export function pushUniquePart(parts, value) {
  const text = safeString(value).trim()
  if (!text) return
  if (!parts.includes(text)) parts.push(text)
}

export function formatStage(stage) {
  const text = safeString(stage).trim()
  if (!text) return ''
  return humanizeToken(text)
}

export function dedupeEntries(entries) {
  const seen = new Set()
  return safeArray(entries).filter((entry, idx) => {
    const row = safeObject(entry)
    const key =
      safeString(row.id).trim() ||
      [safeString(row.badge).trim(), safeString(row.title).trim(), safeString(row.actor).trim(), idx].join('|')

    if (!key) return false
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

