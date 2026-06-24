export const FILES_REAL_ROOT = 'agent_files'
export const FILES_DISPLAY_ROOT = 'user'

export function normalize_file_path_display_value(value) {
  return String(value || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\/+|\/+$/g, '')
}

export function to_user_visible_path(path) {
  const p = normalize_file_path_display_value(path)
  if (!p) return ''
  if (p === FILES_REAL_ROOT) return FILES_DISPLAY_ROOT
  if (p.startsWith(`${FILES_REAL_ROOT}/`)) {
    return `${FILES_DISPLAY_ROOT}/${p.slice(FILES_REAL_ROOT.length + 1)}`
  }
  return p
}

export function from_user_visible_path(path) {
  const p = normalize_file_path_display_value(path)
  if (!p) return ''
  if (p === FILES_DISPLAY_ROOT) return FILES_REAL_ROOT
  if (p.startsWith(`${FILES_DISPLAY_ROOT}/`)) {
    return `${FILES_REAL_ROOT}/${p.slice(FILES_DISPLAY_ROOT.length + 1)}`
  }
  return p
}

export function to_user_visible_text(value) {
  const text = String(value || '')
  if (!text) return ''

  return text.replace(
    /(^|[^A-Za-z0-9_])agent_files(?=\/|$|[^A-Za-z0-9_])/g,
    (_, prefix) => `${prefix}${FILES_DISPLAY_ROOT}`
  )
}

export function to_user_visible_segments(realPath) {
  const p = normalize_file_path_display_value(realPath)
  if (!p) return []

  if (p === FILES_REAL_ROOT) return []

  if (p.startsWith(`${FILES_REAL_ROOT}/`)) {
    const rest = p.slice(FILES_REAL_ROOT.length + 1)
    const parts = rest.split('/').filter(Boolean)
    const segs = []
    let acc = FILES_REAL_ROOT

    for (const part of parts) {
      acc = `${acc}/${part}`
      segs.push({
        name: part,
        displayName: part,
        path: acc,
        displayPath: to_user_visible_path(acc)
      })
    }

    return segs
  }

  const parts = p.split('/').filter(Boolean)
  const segs = []
  let acc = ''

  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part
    segs.push({
      name: part,
      displayName: part,
      path: acc,
      displayPath: to_user_visible_path(acc)
    })
  }

  return segs
}
