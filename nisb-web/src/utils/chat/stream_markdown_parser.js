function normalize_newlines(text) {
  return String(text || '').replace(/\r\n?/g, '\n')
}

function read_line(text, start) {
  const idx = text.indexOf('\n', start)
  if (idx === -1) {
    return {
      line: text.slice(start),
      next: text.length,
      has_newline: false,
    }
  }

  return {
    line: text.slice(start, idx),
    next: idx + 1,
    has_newline: true,
  }
}

function is_blank_line(line) {
  return /^\s*$/.test(String(line || ''))
}

function is_fence_line(line) {
  return /^\s*```/.test(String(line || ''))
}

function is_heading_line(line) {
  return /^(#{1,6})\s+/.test(String(line || ''))
}

function is_quote_line(line) {
  return /^\s{0,3}>\s?/.test(String(line || ''))
}

function is_list_line(line) {
  return /^\s{0,3}(?:[-*+]|\\d+\.)\s+/.test(String(line || ''))
}

function is_list_continuation_line(line) {
  return /^\s{2,}\S/.test(String(line || ''))
}

function is_block_start(line) {
  return (
    is_fence_line(line) ||
    is_heading_line(line) ||
    is_quote_line(line) ||
    is_list_line(line)
  )
}

function extract_code_language(opening_line) {
  const m = String(opening_line || '').match(/^\s*```([^\s`]*)/)
  return String(m?.[1] || '').trim()
}

function extract_code_text(raw_text, closed = false) {
  const normalized = normalize_newlines(raw_text)
  const lines = normalized.split('\n')
  if (lines.length === 0) return ''

  lines.shift()

  if (closed) {
    let idx = lines.length - 1
    while (idx >= 0 && lines[idx] === '') idx -= 1
    if (idx >= 0 && is_fence_line(lines[idx])) {
      lines.splice(idx, 1)
    }
  }

  return lines.join('\n')
}

function make_block(seq, type, text, meta = {}) {
  return {
    id: `md_block_${seq}`,
    type,
    text: String(text || ''),
    meta: meta && typeof meta === 'object' ? meta : {},
    is_tail: false,
  }
}

function make_tail_block(seq, type, text, meta = {}) {
  return {
    id: `md_tail_${seq}`,
    type,
    text: String(text || ''),
    meta: meta && typeof meta === 'object' ? meta : {},
    is_tail: true,
  }
}

function parse_code_block(text, start, final, seq) {
  const open = read_line(text, start)
  const lang = extract_code_language(open.line)

  if (!open.has_newline && !final) {
    return {
      sealed_blocks: [],
      active_tail_block: make_tail_block(seq, 'code', text.slice(start), {
        lang,
        closed: false,
        code_text: extract_code_text(text.slice(start), false),
      }),
      next_index: text.length,
      next_seq: seq,
    }
  }

  let pos = open.next
  let closed = false
  let end = text.length

  while (pos < text.length) {
    const line_info = read_line(text, pos)

    if (is_fence_line(line_info.line)) {
      closed = true
      end = line_info.next
      break
    }

    if (!line_info.has_newline) {
      pos = text.length
      break
    }

    pos = line_info.next
  }

  if (!closed && !final) {
    const raw_tail = text.slice(start)
    return {
      sealed_blocks: [],
      active_tail_block: make_tail_block(seq, 'code', raw_tail, {
        lang,
        closed: false,
        code_text: extract_code_text(raw_tail, false),
      }),
      next_index: text.length,
      next_seq: seq,
    }
  }

  const raw_block = closed ? text.slice(start, end) : text.slice(start)

  return {
    sealed_blocks: [
      make_block(seq, 'code', raw_block, {
        lang,
        closed,
        code_text: extract_code_text(raw_block, closed),
      }),
    ],
    active_tail_block: null,
    next_index: closed ? end : text.length,
    next_seq: seq + 1,
  }
}

function parse_heading_block(text, start, final, seq) {
  const line_info = read_line(text, start)

  if (!line_info.has_newline && !final) {
    return {
      sealed_blocks: [],
      active_tail_block: make_tail_block(seq, 'heading', text.slice(start), {}),
      next_index: text.length,
      next_seq: seq,
    }
  }

  return {
    sealed_blocks: [make_block(seq, 'heading', line_info.line, {})],
    active_tail_block: null,
    next_index: line_info.next,
    next_seq: seq + 1,
  }
}

function parse_quote_block(text, start, final, seq) {
  let pos = start

  while (pos < text.length) {
    const line_info = read_line(text, pos)
    if (!is_quote_line(line_info.line)) break

    if (!line_info.has_newline) {
      if (!final) {
        return {
          sealed_blocks: [],
          active_tail_block: make_tail_block(seq, 'quote', text.slice(start), {}),
          next_index: text.length,
          next_seq: seq,
        }
      }

      pos = text.length
      break
    }

    pos = line_info.next
  }

  const raw_block = text.slice(start, pos)
  return {
    sealed_blocks: [make_block(seq, 'quote', raw_block, {})],
    active_tail_block: null,
    next_index: pos,
    next_seq: seq + 1,
  }
}

function parse_list_block(text, start, final, seq) {
  let pos = start
  let saw_any = false

  while (pos < text.length) {
    const line_info = read_line(text, pos)
    const line = line_info.line

    if (!saw_any) {
      if (!is_list_line(line)) break
      saw_any = true
    } else if (!(is_list_line(line) || is_list_continuation_line(line) || is_blank_line(line))) {
      break
    }

    if (!line_info.has_newline) {
      if (!final) {
        return {
          sealed_blocks: [],
          active_tail_block: make_tail_block(seq, 'list', text.slice(start), {}),
          next_index: text.length,
          next_seq: seq,
        }
      }

      pos = text.length
      break
    }

    pos = line_info.next
  }

  const raw_block = text.slice(start, pos)
  return {
    sealed_blocks: [make_block(seq, 'list', raw_block, {})],
    active_tail_block: null,
    next_index: pos,
    next_seq: seq + 1,
  }
}

function parse_paragraph_block(text, start, final, seq) {
  let pos = start

  while (pos < text.length) {
    const line_info = read_line(text, pos)
    const line = line_info.line

    if (pos !== start && is_blank_line(line)) {
      const raw_block = text.slice(start, pos)
      return {
        sealed_blocks: [make_block(seq, 'paragraph', raw_block, {})],
        active_tail_block: null,
        next_index: pos,
        next_seq: seq + 1,
      }
    }

    if (pos !== start && is_block_start(line)) {
      const raw_block = text.slice(start, pos)
      return {
        sealed_blocks: [make_block(seq, 'paragraph', raw_block, {})],
        active_tail_block: null,
        next_index: pos,
        next_seq: seq + 1,
      }
    }

    if (!line_info.has_newline) {
      if (!final) {
        return {
          sealed_blocks: [],
          active_tail_block: make_tail_block(seq, 'paragraph', text.slice(start), {}),
          next_index: text.length,
          next_seq: seq,
        }
      }

      pos = text.length
      break
    }

    pos = line_info.next
  }

  const raw_block = text.slice(start, pos)
  if (!raw_block) {
    return {
      sealed_blocks: [],
      active_tail_block: null,
      next_index: pos,
      next_seq: seq,
    }
  }

  return {
    sealed_blocks: [make_block(seq, 'paragraph', raw_block, {})],
    active_tail_block: null,
    next_index: pos,
    next_seq: seq + 1,
  }
}

export function parse_stream_markdown_fragment(text, options = {}) {
  const final = !!options.final
  let seq = Number.isFinite(options.start_seq) ? Number(options.start_seq) : 1

  const normalized = normalize_newlines(text)
  const sealed_blocks = []
  let active_tail_block = null
  let pos = 0

  while (pos < normalized.length) {
    const line_info = read_line(normalized, pos)

    if (is_blank_line(line_info.line)) {
      if (!line_info.has_newline) break
      pos = line_info.next
      continue
    }

    let parsed = null

    if (is_fence_line(line_info.line)) {
      parsed = parse_code_block(normalized, pos, final, seq)
    } else if (is_heading_line(line_info.line)) {
      parsed = parse_heading_block(normalized, pos, final, seq)
    } else if (is_quote_line(line_info.line)) {
      parsed = parse_quote_block(normalized, pos, final, seq)
    } else if (is_list_line(line_info.line)) {
      parsed = parse_list_block(normalized, pos, final, seq)
    } else {
      parsed = parse_paragraph_block(normalized, pos, final, seq)
    }

    if (Array.isArray(parsed?.sealed_blocks) && parsed.sealed_blocks.length > 0) {
      sealed_blocks.push(...parsed.sealed_blocks)
    }

    if (parsed?.active_tail_block) {
      active_tail_block = parsed.active_tail_block
      seq = Number.isFinite(parsed.next_seq) ? Number(parsed.next_seq) : seq
      pos = normalized.length
      break
    }

    seq = Number.isFinite(parsed?.next_seq) ? Number(parsed.next_seq) : seq
    pos = Number.isFinite(parsed?.next_index) ? Number(parsed.next_index) : normalized.length
  }

  if (final && active_tail_block) {
    sealed_blocks.push(
      make_block(seq, active_tail_block.type, active_tail_block.text, active_tail_block.meta || {})
    )
    active_tail_block = null
    seq += 1
  }

  return {
    sealed_blocks,
    active_tail_block,
    next_block_seq: seq,
  }
}

export function parse_stream_markdown_text(text, options = {}) {
  return parse_stream_markdown_fragment(text, options)
}

export function normalize_stream_markdown_text(text) {
  return normalize_newlines(text)
}

export function get_code_block_text(block) {
  if (!block || block.type !== 'code') return ''
  return String(block?.meta?.code_text || '')
}

export function get_code_block_lang(block) {
  if (!block || block.type !== 'code') return ''
  return String(block?.meta?.lang || '')
}

export function is_code_block_closed(block) {
  if (!block || block.type !== 'code') return false
  return !!block?.meta?.closed
}

