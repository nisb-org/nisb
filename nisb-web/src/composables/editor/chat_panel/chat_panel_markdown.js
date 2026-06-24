import { marked } from 'marked'
import DOMPurify from 'dompurify'

let _marked_inited = false

export function ensure_marked_inited() {
  if (_marked_inited) return

  marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
  })

  _marked_inited = true
}

function escape_html(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function parse_markdown_to_html(text) {
  ensure_marked_inited()
  return marked.parse(String(text || ''))
}

function sanitize_html(html) {
  return DOMPurify.sanitize(String(html || ''), {
    USE_PROFILES: { html: true },
    ALLOW_UNKNOWN_PROTOCOLS: true,
  })
}

function render_plain_fallback(text) {
  const escaped = escape_html(text).replace(/\n/g, '<br>')
  return sanitize_html(escaped)
}

function normalize_block_input(block_or_text) {
  if (block_or_text && typeof block_or_text === 'object') {
    return {
      type: String(block_or_text.type || 'paragraph'),
      text: String(block_or_text.text || ''),
      is_tail: !!block_or_text.is_tail,
      meta: block_or_text.meta && typeof block_or_text.meta === 'object'
        ? block_or_text.meta
        : {},
    }
  }

  return {
    type: 'paragraph',
    text: String(block_or_text || ''),
    is_tail: false,
    meta: {},
  }
}

function ensure_tail_renderable_text(type, text, is_tail) {
  let md = String(text || '')
  if (!md) return ''

  if (!is_tail) return md

  if (type === 'heading') {
    if (!md.endsWith('\n')) md += '\n'
    return md
  }

  if (type === 'list') {
    if (!md.endsWith('\n')) md += '\n'
    return md
  }

  if (type === 'quote') {
    if (!md.endsWith('\n')) md += '\n'
    return md
  }

  if (type === 'paragraph') {
    if (!md.endsWith('\n')) md += '\n'
    return md
  }

  return md
}

export function render_markdown(text) {
  try {
    return sanitize_html(parse_markdown_to_html(text))
  } catch {
    return render_plain_fallback(text)
  }
}

export function render_markdown_block(block_or_text) {
  const block = normalize_block_input(block_or_text)
  const prepared = ensure_tail_renderable_text(block.type, block.text, block.is_tail)
  return render_markdown(prepared)
}

