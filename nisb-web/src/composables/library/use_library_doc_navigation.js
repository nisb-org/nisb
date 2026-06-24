import { ref, watch, nextTick, unref } from 'vue'

export function use_library_doc_navigation({
  library_id_ref,
  root_el,
  selected_doc,
  documents,
  doc_list_visible,
  library_search,
  broadcast_doc_meta,
  load_documents,
  close_export_translated_modal,
  close_batch_delete,
  cancel_rename_doc,
  cancel_delete_doc,
  reset_doc_state,
  emit_back
}) {
  const span_tools_open = ref(false)
  const span_tools_span_index = ref(0)
  const span_tools_reader = ref(null)
  const pending_span_open = ref(null)

  const bound = ref(false)

  let open_doc_debounce_timer = null
  let open_doc_pending_payload = null
  let apply_doc_state_retry_timers = []

  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function close_span_tools() {
    span_tools_open.value = false
    span_tools_span_index.value = 0
    span_tools_reader.value = null
  }

  function is_finite_number(v) {
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  function find_visible_span_index() {
    try {
      const container_rect = root_el.value ? root_el.value.getBoundingClientRect() : { top: 0, bottom: window.innerHeight }
      const els = document.querySelectorAll('.continuous-span[data-span-index]')
      for (const el of els) {
        const r = el.getBoundingClientRect()
        if (r.bottom >= container_rect.top && r.top <= container_rect.bottom) {
          const sid = is_finite_number(el.getAttribute('data-span-index'))
          if (sid !== null) return sid
        }
      }
    } catch {}
    return null
  }

  function open_span_modal_now(payload) {
    const sid_from_payload = is_finite_number(payload?.spanIndex ?? payload?.span_index)
    const sid_from_view = find_visible_span_index()
    span_tools_span_index.value = sid_from_view ?? sid_from_payload ?? 0
    span_tools_reader.value = payload?.reader ?? window.nisbReaderState ?? null
    span_tools_open.value = true
  }

  function is_docked_right_now() {
    try {
      const d = window.__nisbLibraryDockState
      return !!(d && d.docked === true && d.side === 'right')
    } catch {
      return false
    }
  }

  function on_show_doc_list(evt) {
    const payload = evt?.detail || null
    if (payload?.libraryId && payload.libraryId !== get_library_id()) return
    doc_list_visible.value = true
  }

  function on_span_artifacts_open(evt) {
    if (is_docked_right_now()) return

    const d = evt?.detail || null
    if (!d) return
    if (d.libraryId && d.libraryId !== get_library_id()) return

    const target_doc_id = String(d.docId || '').trim()
    const current_doc_id = String(selected_doc.value?.doc_id || selected_doc.value?.docid || '').trim()

    if (target_doc_id && current_doc_id && target_doc_id !== current_doc_id) {
      pending_span_open.value = d
      window.dispatchEvent(
        new CustomEvent('nisb-open-library-doc', {
          detail: {
            libraryId: get_library_id(),
            docId: target_doc_id,
            spanIndex: d.spanIndex ?? d.span_index ?? null,
            reader: d.reader ?? window.nisbReaderState ?? null
          }
        })
      )
      return
    }

    open_span_modal_now(d)
  }

  watch(
    () => (selected_doc.value?.doc_id || selected_doc.value?.docid || ''),
    async () => {
      const p = pending_span_open.value
      if (!p) return
      const target_doc_id = String(p.docId || '').trim()
      const current_doc_id = String(selected_doc.value?.doc_id || selected_doc.value?.docid || '').trim()
      if (!target_doc_id || !current_doc_id || target_doc_id !== current_doc_id) return
      pending_span_open.value = null
      await nextTick()
      open_span_modal_now(p)
    }
  )

  function pick_span_index(p) {
    if (!p || typeof p !== 'object') return null
    const raw = p.spanIndex ?? p.span_index ?? p.startSpan ?? p.start_span ?? null
    const n = raw === null || raw === undefined ? null : Number(raw)
    return Number.isFinite(n) ? n : null
  }

  function merge_open_payload(prev, next) {
    if (!prev) return next
    if (!next) return prev

    const prev_span = pick_span_index(prev)
    const next_span = pick_span_index(next)

    if (prev_span !== null && next_span === null) {
      return { ...next, spanIndex: prev_span }
    }
    return next
  }

  function dispatch_apply_doc_state_stable(p) {
    try {
      window.__nisb_last_library_doc_open = p
    } catch {}

    const fire = () => {
      window.dispatchEvent(new CustomEvent('nisb-apply-library-doc-state', { detail: p }))
    }

    fire()
    apply_doc_state_retry_timers.push(setTimeout(fire, 60))
    apply_doc_state_retry_timers.push(setTimeout(fire, 220))
    apply_doc_state_retry_timers.push(setTimeout(fire, 700))
  }

  function same_open_payload(a, b) {
    if (!a || !b) return false
    const al = String(a.libraryId || '')
    const bl = String(b.libraryId || '')
    const ad = String(a.docId || '')
    const bd = String(b.docId || '')
    const as = a.spanIndex === undefined ? null : a.spanIndex
    const bs = b.spanIndex === undefined ? null : b.spanIndex
    return al === bl && ad === bd && String(as) === String(bs)
  }

  async function on_open_library_doc(evt) {
    const payload = evt?.detail || null
    if (!payload) return

    const patched_payload = { ...payload, reader: payload?.reader ?? window.nisbReaderState ?? null }
    if (patched_payload.libraryId !== get_library_id()) return

    if (open_doc_debounce_timer) clearTimeout(open_doc_debounce_timer)

    const merged = merge_open_payload(open_doc_pending_payload, patched_payload)
    if (same_open_payload(open_doc_pending_payload, merged)) return

    open_doc_pending_payload = merged

    open_doc_debounce_timer = setTimeout(async () => {
      const p = open_doc_pending_payload
      open_doc_pending_payload = null
      open_doc_debounce_timer = null
      if (!p) return

      try {
        if (!Array.isArray(documents.value) || !documents.value.length) {
          await load_documents()
        }

        const target_id = String(p.docId || '').trim()
        if (target_id) {
          let found = documents.value.find((d) => d && d.doc_id === target_id)
          if (!found) {
            await load_documents()
            found = documents.value.find((d) => d && d.doc_id === target_id)
          }
          if (found) {
            selected_doc.value = found
            doc_list_visible.value = false
            library_search.setContext({ libraryId: get_library_id(), docId: found.doc_id })
            broadcast_doc_meta(found)

            await nextTick()
            await new Promise((resolve) => requestAnimationFrame(() => resolve()))
          }
        }

        dispatch_apply_doc_state_stable(p)
      } catch (e) {
        console.error('[库详情] on_open_library_doc 去抖执行失败:', e)
      }
    }, 80)
  }

  function handle_keydown(e) {
    if (e.key !== 'Escape') return

    close_span_tools()

    if (close_export_translated_modal) {
      const before = typeof close_export_translated_modal === 'function'
      if (before) {
        close_export_translated_modal()
      }
    }

    if (close_batch_delete) close_batch_delete()
    if (cancel_rename_doc) cancel_rename_doc()
    if (cancel_delete_doc) cancel_delete_doc()

    reset_doc_state('escape_back')
    emit_back()
  }

  function bind_global_listeners() {
    if (bound.value) return
    bound.value = true
    window.addEventListener('keydown', handle_keydown)
    window.addEventListener('nisb-open-library-doc', on_open_library_doc)
    window.addEventListener('nisb-library-show-doc-list', on_show_doc_list)
    window.addEventListener('nisb-span-artifacts-open', on_span_artifacts_open)
  }

  function unbind_global_listeners() {
    if (!bound.value) return
    bound.value = false
    window.removeEventListener('keydown', handle_keydown)
    window.removeEventListener('nisb-open-library-doc', on_open_library_doc)
    window.removeEventListener('nisb-library-show-doc-list', on_show_doc_list)
    window.removeEventListener('nisb-span-artifacts-open', on_span_artifacts_open)
  }

  function cleanup_navigation() {
    if (open_doc_debounce_timer) {
      clearTimeout(open_doc_debounce_timer)
      open_doc_debounce_timer = null
    }

    open_doc_pending_payload = null
    pending_span_open.value = null

    if (Array.isArray(apply_doc_state_retry_timers) && apply_doc_state_retry_timers.length) {
      for (const t of apply_doc_state_retry_timers) clearTimeout(t)
      apply_doc_state_retry_timers = []
    }

    try {
      if (Object.prototype.hasOwnProperty.call(window, '__nisb_last_library_doc_open')) {
        delete window.__nisb_last_library_doc_open
      }
    } catch {}

    close_span_tools()
  }

  return {
    span_tools_open,
    span_tools_span_index,
    span_tools_reader,
    close_span_tools,
    bind_global_listeners,
    unbind_global_listeners,
    cleanup_navigation
  }
}

