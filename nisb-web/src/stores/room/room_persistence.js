import {
  safe_object,
  safe_string,
} from './room_shared'

const LAST_WORKSPACE_SAVE_KEY_PREFIX = 'nisb_room_last_workspace_save_'

export function DEFAULT_LAST_WORKSPACE_SAVE() {
  return {
    target_kind: '',
    relative_path: '',
    scoped_path: '',
    agent_id: '',
    saved_at: '',
  }
}

export function load_last_workspace_save(room_id) {
  const rid = safe_string(room_id).trim()
  if (!rid) return DEFAULT_LAST_WORKSPACE_SAVE()

  try {
    const raw = localStorage.getItem(`${LAST_WORKSPACE_SAVE_KEY_PREFIX}${rid}`)
    if (!raw) return DEFAULT_LAST_WORKSPACE_SAVE()
    const data = JSON.parse(raw)
    return { ...DEFAULT_LAST_WORKSPACE_SAVE(), ...safe_object(data) }
  } catch {
    return DEFAULT_LAST_WORKSPACE_SAVE()
  }
}

export function save_last_workspace_save(room_id, payload) {
  const rid = safe_string(room_id).trim()
  if (!rid) return

  try {
    const data = { ...DEFAULT_LAST_WORKSPACE_SAVE(), ...safe_object(payload) }
    localStorage.setItem(`${LAST_WORKSPACE_SAVE_KEY_PREFIX}${rid}`, JSON.stringify(data))
  } catch {}
}

export function remove_last_workspace_save(room_id) {
  const rid = safe_string(room_id).trim()
  if (!rid) return

  try {
    localStorage.removeItem(`${LAST_WORKSPACE_SAVE_KEY_PREFIX}${rid}`)
  } catch {}
}

