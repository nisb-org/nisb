// /opt/mcp-gateway/nisb-web/src/composables/useNisbSettings.js

export const NISB_LOCAL_EVIDENCE_SYNC_KEY = 'nisb_local_evidence_sync_v1'
export const NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY = 'nisb_local_evidence_autoselect_v1'

// 兼容你之前已经上线并在用的旧 key（迁移用）
const LEGACY_AUTOSYNC_KEY = 'nisb_local_evidence_autosync_v1'

export function readBool(key, defaultVal = true) {
  try {
    const v = String(localStorage.getItem(key) || '').trim()
    if (!v) return defaultVal
    if (v === '0') return false
    if (v === '1') return true
    return defaultVal
  } catch {
    return defaultVal
  }
}

export function writeBool(key, val, { broadcast = true } = {}) {
  try {
    localStorage.setItem(key, val ? '1' : '0')
  } catch {
    // ignore
  }
  if (broadcast) broadcastSetting(key, val)
}

export function broadcastSetting(key, val) {
  try {
    window.dispatchEvent(new CustomEvent('nisb_settings_updated', { detail: { key, value: val ? '1' : '0' } }))
  } catch {
    // ignore
  }
}

export function onSettingsUpdated(handler) {
  window.addEventListener('nisb_settings_updated', handler)
  return () => window.removeEventListener('nisb_settings_updated', handler)
}

/**
 * 本地证据设置（两级开关）
 * - sync: 是否更新列表展示
 * - autoselect: 列表更新后是否自动选中首条（会触发库联动）
 */
export function readLocalEvidenceSettings() {
  const sync = readBool(NISB_LOCAL_EVIDENCE_SYNC_KEY, true)
  const autoselect = readBool(NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY, true)

  // 迁移：如果新 key 没写过，但旧 key 存在，则按旧 key 推导
  try {
    const legacy = String(localStorage.getItem(LEGACY_AUTOSYNC_KEY) || '').trim()
    const hasNew =
      localStorage.getItem(NISB_LOCAL_EVIDENCE_SYNC_KEY) !== null ||
      localStorage.getItem(NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY) !== null

    if (!hasNew && (legacy === '0' || legacy === '1')) {
      const legacyOn = legacy !== '0'
      return { sync: legacyOn, autoselect: legacyOn }
    }
  } catch {
    // ignore
  }

  return { sync, autoselect }
}

export function writeLocalEvidenceSettings({ sync, autoselect }, { broadcast = true } = {}) {
  const s = !!sync
  const a = !!autoselect

  writeBool(NISB_LOCAL_EVIDENCE_SYNC_KEY, s, { broadcast })
  writeBool(NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY, a, { broadcast })

  // 迁移：写入新 key 后，清理旧 key（避免以后读到歧义）
  try {
    localStorage.removeItem(LEGACY_AUTOSYNC_KEY)
  } catch {
    // ignore
  }
}

