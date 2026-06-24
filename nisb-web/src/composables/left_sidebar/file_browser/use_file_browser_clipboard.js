import { normalize_path } from './file_browser_utils'

async function copy_text_safe(text) {
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
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return !!ok
  } catch {
    return false
  }
}

function escape_markdown_link_text(name) {
  return String(name || '').replace(/[\[\]]/g, '\\$&')
}

function is_image_path(p) {
  return /\.(png|jpg|jpeg|webp|gif|bmp|svg)$/i.test(String(p || '').toLowerCase())
}

function build_nisb_file_url({ path, type = 'file', ws = '' }) {
  const u = new URL('nisb://file')
  if (ws) u.searchParams.set('ws', ws)
  u.searchParams.set('type', type)
  u.searchParams.set('path', normalize_path(path))
  return u.toString()
}

export function use_file_browser_clipboard() {
  async function on_copy_internal_link(evt) {
    const d = evt?.detail || {}
    const raw_path = String(d.path || '').trim()
    if (!raw_path) return

    const path = normalize_path(raw_path)
    const raw_type = String(d.type || '').toLowerCase()
    const is_dir = raw_type === 'directory' || raw_type === 'dir'
    const ws = String(d.ws || '').trim()

    const url = build_nisb_file_url({ path, type: is_dir ? 'directory' : 'file', ws })
    const name = escape_markdown_link_text(path.split('/').pop() || (is_dir ? 'folder' : 'file'))

    let text_to_copy = url
    if (is_dir) text_to_copy = `[${name}/](${url})`
    else text_to_copy = is_image_path(path) ? `![${name}](${url})` : `[${name}](${url})`

    const ok = await copy_text_safe(text_to_copy)
    window.dispatchEvent(
      new CustomEvent('nisb-toast', { detail: { message: ok ? '已复制内部链接' : '复制失败', type: ok ? 'info' : 'error' } })
    )
  }

  return { on_copy_internal_link }
}

