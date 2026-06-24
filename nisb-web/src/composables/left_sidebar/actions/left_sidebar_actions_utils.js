// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/actions/left_sidebar_actions_utils.js

export function toast(message, type = 'info', duration = 2000) {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type, duration } }))
}

export function pick_cm(context_menu_ref, cm_in) {
  if (cm_in && typeof cm_in === 'object') return cm_in
  return context_menu_ref?.value || {}
}

export function cm_target_path(cm) {
  // ✅ 兼容 create 菜单的 baseDir 字段
  return String(cm?.targetPath || cm?.path || cm?.baseDir || cm?.base_dir || '').trim()
}

export function cm_target_name(cm) {
  return String(cm?.targetName || cm?.name || '').trim()
}

export function cm_target_file_type(cm) {
  return String(cm?.targetFileType || cm?.type || '').trim() || 'file'
}

export function cm_target_id(cm) {
  return cm?.targetId ?? cm?.id ?? null
}

export function cm_extensions(cm) {
  return Array.isArray(cm?.extensions) ? cm.extensions : []
}

export function extract_nisb_file_path(maybe_url) {
  const s = String(maybe_url || '').trim()
  if (!s) return ''
  if (!s.startsWith('nisb://')) return s
  try {
    const u = new URL(s)
    const p = u.searchParams.get('path')
    if (!p) return ''
    try {
      return decodeURIComponent(p)
    } catch {
      return p
    }
  } catch {
    return ''
  }
}

export async function copy_to_clipboard(text) {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {}

  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    return true
  } catch {
    return false
  }
}

export function get_uid() {
  try {
    const uid = String(localStorage.getItem('nisb_user_id') || '').trim()
    return uid || 'nisb_default_user'
  } catch {
    return 'nisb_default_user'
  }
}

export function normalize_rel_path(p) {
  return String(p || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
}

export function ext(name) {
  const n = String(name || '').toLowerCase()
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i) : ''
}

export function is_binary_file(filename) {
  const e = ext(filename)
  return ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'].includes(e)
}

export function is_pdf_file(filename) {
  return /\.pdf$/i.test(String(filename || ''))
}

export function is_epub_file(filename) {
  return /\.epub$/i.test(String(filename || ''))
}

export function is_doc_file(filename) {
  return /\.doc$/i.test(String(filename || ''))
}

export function is_docx_file(filename) {
  return /\.docx$/i.test(String(filename || ''))
}

export function is_ppt_file(filename) {
  return /\.ppt$/i.test(String(filename || ''))
}

export function is_pptx_file(filename) {
  return /\.pptx$/i.test(String(filename || ''))
}

export function is_image_file(filename) {
  return /\.(png|jpg|jpeg|gif|bmp|webp|svg)$/i.test(String(filename || ''))
}

export function get_parent_dir(path) {
  if (!path) return ''
  const idx = String(path).lastIndexOf('/')
  if (idx === -1) return ''
  return String(path).slice(0, idx)
}

export function looks_timeout_resp(r) {
  const msg = String(r?.message || '')
  if (!msg) return false
  if (!msg.toLowerCase().includes('timeout')) return false
  if (r?.partial !== true) return false
  return true
}

export function pick_display_name_from_path(p) {
  const s = String(p || '').trim()
  if (!s) return ''
  const parts = s.split('/')
  return parts[parts.length - 1] || s
}

