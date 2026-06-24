export function safe_array(v) {
  return Array.isArray(v) ? v : []
}

export function safe_object(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

export function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

export function is_plain_object(v) {
  return !!v && typeof v === 'object' && !Array.isArray(v)
}

export function normalize_bool(v, fallback = false) {
  if (v === true) return true
  if (v === false) return false
  const s = safe_string(v).trim().toLowerCase()
  if (!s) return !!fallback
  if (['true', '1', 'yes', 'on'].includes(s)) return true
  if (['false', '0', 'no', 'off'].includes(s)) return false
  return !!fallback
}

export function normalize_int(v, fallback = 0) {
  const raw = safe_string(v).trim()
  if (!raw) return fallback
  const n = Number(raw)
  if (!Number.isFinite(n)) return fallback
  return Math.max(0, Math.trunc(n))
}

export function normalize_float(v, fallback = 0) {
  const raw = safe_string(v).trim()
  if (!raw) return fallback
  const n = Number(raw)
  if (!Number.isFinite(n)) return fallback
  return n
}

