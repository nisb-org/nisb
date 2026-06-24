// /opt/mcp-gateway/nisb-web/src/composables/library_reader/use_reader_translate_cache_memory.js
export function use_reader_translate_cache_memory({ library_id_ref, doc_id_ref, target_language_ref }) {
  function _get_root() {
    try {
      if (!window.__nisb_library_translate_cache_v1) window.__nisb_library_translate_cache_v1 = {}
      return window.__nisb_library_translate_cache_v1
    } catch {
      return {}
    }
  }

  function _key(lang = null) {
    const lib = String(library_id_ref?.value || '').trim()
    const doc = String(doc_id_ref?.value || '').trim()
    const l = String(lang || target_language_ref?.value || 'zh-CN').trim()
    if (!lib || !doc) return ''
    return `${lib}::${doc}::${l}`
  }

  function _bucket(lang = null) {
    const root = _get_root()
    const k = _key(lang)
    if (!k) return null
    if (!root[k]) root[k] = { by_span_index: {}, updated_at: Date.now() }
    if (!root[k].by_span_index) root[k].by_span_index = {}
    return root[k]
  }

  function cache_set_span(span_index, rec, lang = null) {
    const b = _bucket(lang)
    if (!b) return
    const sid = Number(span_index)
    if (!Number.isFinite(sid)) return
    b.by_span_index[String(sid)] = { ...rec, span_index: sid, updated_at: Date.now() }
    b.updated_at = Date.now()
  }

  function cache_get_span(span_index, lang = null) {
    const b = _bucket(lang)
    if (!b) return null
    const sid = Number(span_index)
    if (!Number.isFinite(sid)) return null
    return b.by_span_index[String(sid)] || null
  }

  function cache_del_span(span_index, lang = null) {
    const b = _bucket(lang)
    if (!b) return
    const sid = Number(span_index)
    if (!Number.isFinite(sid)) return
    try {
      delete b.by_span_index[String(sid)]
      b.updated_at = Date.now()
    } catch {}
  }

  function cache_clear_doc(lang = null) {
    try {
      const root = _get_root()
      const k = _key(lang)
      if (!k) return
      delete root[k]
    } catch {}
  }

  return { cache_set_span, cache_get_span, cache_del_span, cache_clear_doc }
}

