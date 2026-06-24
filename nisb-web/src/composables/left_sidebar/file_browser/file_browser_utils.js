export function is_workspace_id_safe(wid) {
  const s = String(wid || '').trim()
  return s.startsWith('workspace_')
}

export function normalize_path(p) {
  return String(p || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\/+/, '')
}

export function normalize_type(t) {
  const s = String(t || '').toLowerCase().trim()
  return s === 'directory' ? 'directory' : 'file'
}

export function fav_key(item) {
  return `${normalize_path(item?.path)}|${normalize_type(item?.type)}`
}

export function sort_by_pinned_at_desc(list) {
  return (list || [])
    .slice()
    .sort((a, b) => String(b?.pinned_at || '').localeCompare(String(a?.pinned_at || '')))
}

export function get_parent_dir(path) {
  if (!path) return ''
  const idx = String(path).lastIndexOf('/')
  if (idx === -1) return ''
  return String(path).slice(0, idx)
}

export function get_base_name(path) {
  if (!path) return ''
  const parts = String(path).split('/')
  return parts[parts.length - 1] || ''
}

export function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

