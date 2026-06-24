export function use_nisb_uri_repair() {
  function _normalize_nisb_uri(u) {
    const s0 = String(u || '').trim()
    if (!s0) return ''
    return s0.replace(/\s+/g, '')
  }

  function _collect_nisb_uris(text) {
    const out = []
    const src = String(text || '')
    if (!src) return out

    const patterns = [
      /\((\s*nisb\s*:\s*\/\/[^)\s]+)\)/gi,
      /(?:src|href)\s*=\s*["'](\s*nisb\s*:\s*\/\/[^"']+)["']/gi,
      /<(\s*nisb\s*:\s*\/\/[^>\s]+)>/gi,
      /\((nisb%3a%2f%2f[^)\s]+)\)/gi,
      /(?:src|href)\s*=\s*["'](nisb%3a%2f%2f[^"']+)["']/gi,
      /<(nisb%3a%2f%2f[^>\s]+)>/gi
    ]

    for (const re of patterns) {
      re.lastIndex = 0
      let m
      while ((m = re.exec(src))) {
        const uri = _normalize_nisb_uri(m[1])
        if (uri) out.push(uri)
      }
    }
    return out
  }

  function repair_nisb_uris_by_source(source_text, translated_text) {
    const src_uris = _collect_nisb_uris(source_text)
    if (!src_uris.length) return String(translated_text || '')

    let idx = 0
    const take = () => (idx < src_uris.length ? src_uris[idx++] : null)

    const replace_with_next = (full, captured) => {
      const next = take()
      if (!next) return full
      return full.replace(captured, next)
    }

    let out = String(translated_text || '')
    const replace_patterns = [
      /\((\s*nisb\s*:\s*\/\/[^)\s]+)\)/gi,
      /(?:src|href)\s*=\s*["'](\s*nisb\s*:\s*\/\/[^"']+)["']/gi,
      /<(\s*nisb\s*:\s*\/\/[^>\s]+)>/gi,
      /\((nisb%3a%2f%2f[^)\s]+)\)/gi,
      /(?:src|href)\s*=\s*["'](nisb%3a%2f%2f[^"']+)["']/gi,
      /<(nisb%3a%2f%2f[^>\s]+)>/gi
    ]

    for (const re of replace_patterns) {
      out = out.replace(re, (full, captured) => replace_with_next(full, captured))
    }
    return out
  }

  return { repair_nisb_uris_by_source }
}

