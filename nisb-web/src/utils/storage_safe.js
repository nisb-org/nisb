const __quota_failure_ts_by_key = new Map()
let __last_prune_ts = 0

function _estimate_bytes(v) {
  try {
    if (typeof v === 'string') return new Blob([v]).size
    return new Blob([String(v ?? '')]).size
  } catch {
    try {
      return String(v ?? '').length * 2
    } catch {
      return 0
    }
  }
}

function _is_quota_exceeded_error(e) {
  const name = String(e?.name || '')
  const msg = String(e?.message || e || '')
  if (name === 'QuotaExceededError') return true
  if (msg.toLowerCase().includes('quota')) return true
  if (msg.toLowerCase().includes('exceeded')) return true
  return false
}

function _now() {
  return Date.now()
}

function _recent_quota_failure_for_key(key, cooldown_ms) {
  const ts = Number(__quota_failure_ts_by_key.get(String(key || '')) || 0)
  return ts > 0 && _now() - ts < Math.max(0, Number(cooldown_ms || 0))
}

function _mark_quota_failure_for_key(key) {
  __quota_failure_ts_by_key.set(String(key || ''), _now())
}

function _clear_quota_failure_for_key(key) {
  __quota_failure_ts_by_key.delete(String(key || ''))
}

export function safe_local_storage_remove(key) {
  try {
    localStorage.removeItem(String(key || ''))
    _clear_quota_failure_for_key(key)
    return true
  } catch {
    return false
  }
}

export function safe_local_storage_get(key, fallback = '') {
  try {
    const v = localStorage.getItem(String(key || ''))
    return v == null ? fallback : v
  } catch {
    return fallback
  }
}

export function safe_local_storage_prune_by_prefix(prefixes = [], opts = {}) {
  try {
    const ps = Array.isArray(prefixes) ? prefixes.filter(Boolean).map((s) => String(s)) : []
    if (!ps.length) return { ok: true, removed: 0 }

    const keep_keys = Array.isArray(opts.keep_keys) ? opts.keep_keys.map((s) => String(s)) : []
    const keep = new Set(keep_keys)

    const max_remove = Number.isFinite(Number(opts.max_remove)) ? Math.max(1, Number(opts.max_remove)) : Infinity

    const keys = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (!k) continue
      if (keep.has(k)) continue
      if (ps.some((p) => k.startsWith(p))) keys.push(k)
    }

    let removed = 0
    for (const k of keys) {
      if (removed >= max_remove) break
      try {
        localStorage.removeItem(k)
        removed += 1
      } catch {}
    }
    return { ok: true, removed }
  } catch {
    return { ok: false, removed: 0 }
  }
}

/**
 * 安全写入 localStorage：
 * - 默认限制 max_bytes（避免把大正文塞进 localStorage）
 * - 默认跳过“相同值重复写入”，减少同步阻塞
 * - 遇到 QuotaExceededError：清理少量缓存 key 后重试一次；仍失败则跳过，不抛异常
 * - 对同一 key 的 quota 失败做短冷却，避免 Firefox / 紧张配额环境里反复 prune + setItem
 */
export function safe_local_storage_set(key, value, opts = {}) {
  const k = String(key || '')
  if (!k) return { ok: false, skipped: true, reason: 'empty_key', bytes: 0 }

  const max_bytes = Number.isFinite(Number(opts.max_bytes)) ? Number(opts.max_bytes) : 512 * 1024
  const skip_if_same = opts.skip_if_same !== false
  const compare_existing_max_bytes = Number.isFinite(Number(opts.compare_existing_max_bytes))
    ? Number(opts.compare_existing_max_bytes)
    : 768 * 1024

  const quota_cooldown_ms = Number.isFinite(Number(opts.quota_cooldown_ms)) ? Number(opts.quota_cooldown_ms) : 1800
  const prune_cooldown_ms = Number.isFinite(Number(opts.prune_cooldown_ms)) ? Number(opts.prune_cooldown_ms) : 1500
  const prune_max_remove = Number.isFinite(Number(opts.prune_max_remove)) ? Math.max(1, Number(opts.prune_max_remove)) : 24

  const prune_prefixes =
    Array.isArray(opts.prune_prefixes) && opts.prune_prefixes.length
      ? opts.prune_prefixes
      : [
          'nisb_outline_cache_v',
          'nisb_outline_cache_index_',
          'nisb_editor_cache_',
          'nisb_fs_state_',
          'nisb_fs_focus_root_'
        ]

  const keep_keys =
    Array.isArray(opts.keep_keys) && opts.keep_keys.length
      ? opts.keep_keys
      : [
          'nisb_outline_file_path',
          'nisb_outline_hover_enabled'
        ]

  const v = typeof value === 'string' ? value : String(value ?? '')
  const bytes = _estimate_bytes(v)

  if (max_bytes > 0 && bytes > max_bytes) {
    try {
      localStorage.removeItem(k)
    } catch {}
    _clear_quota_failure_for_key(k)
    return { ok: true, skipped: true, reason: `too_large>${max_bytes}`, bytes }
  }

  if (skip_if_same && bytes <= compare_existing_max_bytes) {
    try {
      const prev = localStorage.getItem(k)
      if (prev === v) {
        return { ok: true, skipped: true, reason: 'same_value', bytes }
      }
    } catch {}
  }

  if (_recent_quota_failure_for_key(k, quota_cooldown_ms)) {
    return { ok: false, skipped: true, reason: 'quota_cooldown', bytes }
  }

  try {
    localStorage.setItem(k, v)
    _clear_quota_failure_for_key(k)
    return { ok: true, skipped: false, reason: 'ok', bytes }
  } catch (e) {
    if (!_is_quota_exceeded_error(e)) {
      return { ok: false, skipped: true, reason: 'set_failed', bytes, error: String(e?.message || e) }
    }

    _mark_quota_failure_for_key(k)

    const now = _now()
    if (now - __last_prune_ts >= prune_cooldown_ms) {
      __last_prune_ts = now
      safe_local_storage_prune_by_prefix(prune_prefixes, {
        keep_keys,
        max_remove: prune_max_remove
      })
    }

    try {
      localStorage.setItem(k, v)
      _clear_quota_failure_for_key(k)
      return { ok: true, skipped: false, reason: 'ok_after_prune', bytes }
    } catch (e2) {
      try {
        localStorage.removeItem(k)
      } catch {}
      _mark_quota_failure_for_key(k)
      return { ok: false, skipped: true, reason: 'quota_exceeded', bytes, error: String(e2?.message || e2) }
    }
  }
}
