// /opt/mcp-gateway/nisb-web/src/composables/library_reader/use_reader_translation.js
import { ref } from 'vue'
import { use_nisb_uri_repair } from './use_nisb_uri_repair'
import { use_reader_translate_cache_memory } from './use_reader_translate_cache_memory'

export function use_reader_translation({
  call_tool,
  library_id_ref,
  doc_id_ref,
  target_language_ref,
  translate_backend_ref,
  continuous_enabled_ref,
  smart_pretranslate_ref,
  pretranslate_ahead_ref,
  pretranslate_paused_ref,
  continuous_spans_ref,
  build_reader_snapshot,
  schedule_enhance_markdown_dom,
  sync_all_states,
  is_abort_like
}) {
  const { repair_nisb_uris_by_source } = use_nisb_uri_repair()
  const { cache_set_span, cache_get_span, cache_del_span, cache_clear_doc } = use_reader_translate_cache_memory({
    library_id_ref,
    doc_id_ref,
    target_language_ref
  })

  const PRETRANSLATE_CONCURRENCY = 1
  const queue = ref([])
  const running_map = ref(new Map())

  function apply_translate_cache_to_spans(spans, lang = null) {
    if (!Array.isArray(spans) || !spans.length) return
    for (const s of spans) {
      const sid = Number(s?.span_index)
      if (!Number.isFinite(sid)) continue
      const rec = cache_get_span(sid, lang)
      if (!rec) continue

      const refused = rec.refused === true
      const text = String(rec.translated_text || '')
      if (refused) {
        s.translated_text = ''
        s.translation_refused = true
        s.translation_refusal_text = String(rec.refusal_text || '')
        s.from_cache = true
      } else if (text.trim()) {
        s.translated_text = repair_nisb_uris_by_source(s.text, text)
        s.translation_refused = false
        s.translation_refusal_text = ''
        s.from_cache = true
      }
    }
  }

  function cancel_pretranslate(reason = 'unknown') {
    pretranslate_paused_ref.value = true
    queue.value = []

    for (const [sid, c] of running_map.value.entries()) {
      try {
        c.abort(reason)
      } catch {}
      const span = continuous_spans_ref.value.find((s) => Number(s?.span_index) === Number(sid))
      if (span) span.translating = false
    }
    running_map.value = new Map()
    sync_all_states()
  }

  function resume_pretranslate() {
    pretranslate_paused_ref.value = false
    sync_all_states()
    kick_pretranslate()
  }

  function enqueue_pretranslate(span) {
    if (!smart_pretranslate_ref.value) return
    if (pretranslate_paused_ref.value) return
    if (!span) return
    if (span.translated_text || span.translating || span.translation_refused) return
    if (queue.value.includes(span.span_index)) return
    if (running_map.value.has(span.span_index)) return

    queue.value.push(span.span_index)
    sync_all_states()
    kick_pretranslate()
  }

  function kick_pretranslate() {
    if (!smart_pretranslate_ref.value) {
      queue.value = []
      sync_all_states()
      return
    }
    if (pretranslate_paused_ref.value) return

    while (running_map.value.size < PRETRANSLATE_CONCURRENCY && queue.value.length > 0) {
      const next_index = queue.value.shift()
      if (next_index === undefined) break

      const span = continuous_spans_ref.value.find((s) => Number(s?.span_index) === Number(next_index))
      if (!span || span.translated_text || span.translation_refused) continue

      const controller = new AbortController()
      running_map.value = new Map(running_map.value).set(next_index, controller)
      sync_all_states()

      ;(async () => {
        try {
          await translate_span(span, { silent: true, force: false, signal: controller.signal, backend: 'mini' })
        } finally {
          const next = new Map(running_map.value)
          next.delete(next_index)
          running_map.value = next
          sync_all_states()
          if (queue.value.length > 0) kick_pretranslate()
        }
      })()
    }
  }

  function ensure_ahead_translated(base_index) {
    if (!smart_pretranslate_ref.value) return
    if (pretranslate_paused_ref.value) return

    const ahead = Number(pretranslate_ahead_ref.value || 2)
    let translated_count = 0
    const candidates = []

    for (let i = 1; i <= ahead; i++) {
      const span = continuous_spans_ref.value[base_index + i]
      if (!span) break
      if (span.translated_text || span.translation_refused) translated_count += 1
      else candidates.push(span)
    }

    const need = ahead - translated_count
    if (need <= 0) return
    for (let i = 0; i < need && i < candidates.length; i++) {
      enqueue_pretranslate(candidates[i])
    }
  }

  async function translate_span(span, options = {}) {
    const { silent = false, force = false, signal = null, backend = 'mini' } = options
    if (!span || !doc_id_ref.value) return
    if (!force && (span.translated_text || span.translating || span.translation_refused)) return

    span.translating = true
    sync_all_states()

    const reader = build_reader_snapshot()
    reader.showTranslation = true

    try {
      const res = await call_tool(
        'nisb_library_translate_span',
        {
          library_id: library_id_ref.value,
          doc_id: doc_id_ref.value,
          span_start: span.span_start,
          span_end: span.span_end,
          target_language: target_language_ref.value,
          backend: backend,
          reader,
          span_index: Number(span.span_index),
          force: !!force,
          continuous: !!continuous_enabled_ref.value,
          show_translation: true,
          lang: target_language_ref.value,
          smart_pretranslate: !!smart_pretranslate_ref.value,
          pretranslate_spans: Number(pretranslate_ahead_ref.value || 2)
        },
        { signal: signal || undefined, trackLoading: false }
      )

      if (res && res.status === 'success') {
        span.from_cache = !!res.from_cache

        if (res.refused === true) {
          span.translated_text = ''
          span.translation_refused = true
          span.translation_refusal_text = res.refusal_text || ''
          if (!silent) alert('❌ 该段翻译被模型拒绝（已隔离，不会污染缓存译文）。可点击"强制重译"再次尝试。')

          try {
            cache_set_span(
              span.span_index,
              { refused: true, refusal_text: span.translation_refusal_text || '', translated_text: '' },
              target_language_ref.value
            )
          } catch {}
        } else {
          const raw_t = String(res.translated_text || '')
          const fixed_t = repair_nisb_uris_by_source(span.text, raw_t)

          span.translated_text = fixed_t
          span.translation_refused = false
          span.translation_refusal_text = ''

          try {
            const t = String(span.translated_text || '')
            if (t.trim()) {
              cache_set_span(span.span_index, { refused: false, refusal_text: '', translated_text: t }, target_language_ref.value)
            }
          } catch {}
        }

        schedule_enhance_markdown_dom(0)
      } else if (!silent) {
        alert('❌ 段落翻译失败：' + (res?.message || '未知错误'))
      }
    } catch (e) {
      if (is_abort_like(e, { signal })) return
      console.error('[连续阅读] 段落翻译失败:', e)
      if (!silent) alert('❌ 段落翻译失败：' + (e?.message || e))
    } finally {
      span.translating = false
      sync_all_states()
    }
  }

  async function handle_translate_click(span) {
    if (!span) return

    const has_visible_translation = !!(span.translated_text && String(span.translated_text).trim())
    const was_refused = span.translation_refused === true
    const should_force = has_visible_translation || was_refused

    const exist = running_map.value.get(span.span_index)
    if (exist) {
      try {
        exist.abort('manual_override')
      } catch {}
      const next = new Map(running_map.value)
      next.delete(span.span_index)
      running_map.value = next
    }

    try {
      cache_del_span(span.span_index, target_language_ref.value)
    } catch {}

    span.translated_text = null
    span.from_cache = false
    span.translation_refused = false
    span.translation_refusal_text = ''
    sync_all_states()

    const controller = new AbortController()
    await translate_span(span, { silent: false, force: should_force, signal: controller.signal, backend: translate_backend_ref.value })

    const idx = continuous_spans_ref.value.findIndex((s) => Number(s?.span_index) === Number(span.span_index))
    if (idx !== -1) ensure_ahead_translated(idx)
  }

  return {
    queue,
    running_map,
    cache_clear_doc,

    apply_translate_cache_to_spans,
    translate_span,
    handle_translate_click,

    enqueue_pretranslate,
    kick_pretranslate,
    ensure_ahead_translated,
    cancel_pretranslate,
    resume_pretranslate
  }
}

