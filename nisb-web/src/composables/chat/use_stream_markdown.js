import {
  parse_stream_markdown_fragment,
  parse_stream_markdown_text,
  normalize_stream_markdown_text,
} from '../../utils/chat/stream_markdown_parser'

export function create_empty_stream_markdown_state() {
  return {
    raw_text: '',
    sealed_blocks: [],
    active_tail_block: null,
    is_final: false,
    is_done: false,
    has_error: false,
    parse_version: 0,
    next_block_seq: 1,
  }
}

function normalize_state(prev) {
  if (!prev || typeof prev !== 'object') {
    return create_empty_stream_markdown_state()
  }

  return {
    raw_text: String(prev.raw_text || ''),
    sealed_blocks: Array.isArray(prev.sealed_blocks) ? prev.sealed_blocks : [],
    active_tail_block:
      prev.active_tail_block && typeof prev.active_tail_block === 'object'
        ? prev.active_tail_block
        : null,
    is_final: !!prev.is_final,
    is_done: !!prev.is_done,
    has_error: !!prev.has_error,
    parse_version: Number.isFinite(prev.parse_version) ? Number(prev.parse_version) : 0,
    next_block_seq: Number.isFinite(prev.next_block_seq) ? Number(prev.next_block_seq) : 1,
  }
}

export function hydrate_stream_markdown_from_text(text, options = {}) {
  const raw_text = normalize_stream_markdown_text(text)
  const final = options.final !== false
  const parsed = parse_stream_markdown_text(raw_text, {
    final,
    start_seq: 1,
  })

  const sealed_blocks = Array.isArray(parsed.sealed_blocks) ? parsed.sealed_blocks : []
  const active_tail_block = parsed.active_tail_block || null

  return {
    raw_text,
    sealed_blocks,
    active_tail_block,
    is_final: !!final,
    is_done: !!options.done,
    has_error: !!options.has_error,
    parse_version: 1,
    next_block_seq: Number.isFinite(parsed.next_block_seq) ? Number(parsed.next_block_seq) : 1,
  }
}

export function append_stream_markdown(prev, chunk) {
  const base = normalize_state(prev)
  const next_chunk = normalize_stream_markdown_text(chunk)

  if (!next_chunk) {
    return {
      ...base,
      parse_version: base.parse_version + 1,
    }
  }

  const tail_text = String(base.active_tail_block?.text || '')
  const parsed = parse_stream_markdown_fragment(`${tail_text}${next_chunk}`, {
    final: false,
    start_seq: base.next_block_seq,
  })

  return {
    raw_text: `${base.raw_text}${next_chunk}`,
    sealed_blocks: [...base.sealed_blocks, ...(parsed.sealed_blocks || [])],
    active_tail_block: parsed.active_tail_block || null,
    is_final: false,
    is_done: false,
    has_error: base.has_error,
    parse_version: base.parse_version + 1,
    next_block_seq: Number.isFinite(parsed.next_block_seq)
      ? Number(parsed.next_block_seq)
      : base.next_block_seq,
  }
}

export function finalize_stream_markdown(prev, final_text = '') {
  const base = normalize_state(prev)
  const next_raw_text = normalize_stream_markdown_text(final_text || base.raw_text)

  if (!next_raw_text) {
    return {
      ...create_empty_stream_markdown_state(),
      is_final: true,
      is_done: true,
      parse_version: base.parse_version + 1,
    }
  }

  if (next_raw_text === base.raw_text || next_raw_text.startsWith(base.raw_text)) {
    const extra = next_raw_text.slice(base.raw_text.length)
    const tail_text = String(base.active_tail_block?.text || '')
    const parsed = parse_stream_markdown_fragment(`${tail_text}${extra}`, {
      final: true,
      start_seq: base.next_block_seq,
    })

    return {
      raw_text: next_raw_text,
      sealed_blocks: [...base.sealed_blocks, ...(parsed.sealed_blocks || [])],
      active_tail_block: null,
      is_final: true,
      is_done: base.is_done,
      has_error: base.has_error,
      parse_version: base.parse_version + 1,
      next_block_seq: Number.isFinite(parsed.next_block_seq)
        ? Number(parsed.next_block_seq)
        : base.next_block_seq,
    }
  }

  const reparsed = parse_stream_markdown_text(next_raw_text, {
    final: true,
    start_seq: 1,
  })

  return {
    raw_text: next_raw_text,
    sealed_blocks: reparsed.sealed_blocks || [],
    active_tail_block: null,
    is_final: true,
    is_done: base.is_done,
    has_error: base.has_error,
    parse_version: base.parse_version + 1,
    next_block_seq: Number.isFinite(reparsed.next_block_seq)
      ? Number(reparsed.next_block_seq)
      : 1,
  }
}

export function mark_stream_markdown_done(prev) {
  const base = normalize_state(prev)
  return {
    ...base,
    is_done: true,
    parse_version: base.parse_version + 1,
  }
}

export function mark_stream_markdown_error(prev) {
  const base = normalize_state(prev)
  return {
    ...base,
    has_error: true,
    parse_version: base.parse_version + 1,
  }
}

export function reset_stream_markdown() {
  return create_empty_stream_markdown_state()
}

