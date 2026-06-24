import { ref, unref } from 'vue'

export function use_library_doc_state({
  library_id_ref,
  selected_doc_id_ref,
  call_tool,
  library_search,
  begin_load_docs
}) {
  const library = ref(null)
  const stats = ref(null)
  const documents = ref([])
  const loading_docs = ref(false)

  const selected_doc = ref(null)
  const selected_doc_open_token = ref(0)
  const doc_list_visible = ref(true)

  let load_docs_timer = null

  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function get_selected_doc_id() {
    return String(unref(selected_doc_id_ref) || '').trim()
  }

  function get_doc_id(doc) {
    return String(doc?.doc_id || doc?.docid || '').trim()
  }

  function bump_selected_doc_open_token() {
    selected_doc_open_token.value += 1
  }

  function storage_key(suffix) {
    return `nisb_library_${suffix}_${get_library_id()}`
  }

  function get_persisted_last_doc_id() {
    try {
      return (localStorage.getItem(storage_key('last_doc_id')) || '').trim()
    } catch {
      return ''
    }
  }

  function set_persisted_last_doc_id(doc_id) {
    try {
      localStorage.setItem(storage_key('last_doc_id'), String(doc_id || ''))
    } catch {}
  }

  function get_persisted_focus_mode() {
    try {
      return (localStorage.getItem(storage_key('focus_mode')) || '').trim()
    } catch {
      return ''
    }
  }

  function set_persisted_focus_mode(mode) {
    try {
      localStorage.setItem(storage_key('focus_mode'), String(mode || ''))
    } catch {}
  }

  function clear_last_open_payload() {
    try {
      if (Object.prototype.hasOwnProperty.call(window, '__nisb_last_library_doc_open')) {
        delete window.__nisb_last_library_doc_open
      }
    } catch {}
  }

  function broadcast_doc_meta(doc) {
    try {
      const d = doc || null
      window.dispatchEvent(
        new CustomEvent('nisb-library-doc-meta', {
          detail: {
            libraryId: get_library_id(),
            docId: d?.doc_id || null,
            filename: d?.filename || '',
            filetype: d?.filetype || 'txt',
            chunks: Number(d?.chunks || 0)
          }
        })
      )
    } catch {}
  }

  function clear_global_reader_state(reason = 'no_doc') {
    const snapshot = {
      continuous: false,
      showTranslation: false,
      smartPretranslate: false,
      pretranslateSpans: 2,
      lang: 'zh-CN',
      compareMode: false
    }

    try {
      window.nisbReaderState = snapshot
    } catch {}

    try {
      window.dispatchEvent(
        new CustomEvent('nisb-reader-state-changed', {
          detail: {
            libraryId: get_library_id(),
            docId: null,
            reader: snapshot,
            progress: { total: 0, translated: 0, refused: 0, queue: 0, running: 0, paused: false },
            reason
          }
        })
      )
    } catch {}
  }

  async function load_library_info() {
    try {
      const res = await call_tool('nisb_library_get_info', { library_id: get_library_id() })
      library.value = res && res.status === 'success' ? (res.info || {}) : null

      const stat_res = await call_tool('nisb_library_stats', { library_id: get_library_id() })
      if (stat_res && stat_res.status === 'success') {
        const s = stat_res.stats || {}
        stats.value = {
          doc_count: s.doc_count ?? 0,
          concept_count: s.concept_count ?? 0,
          relation_count: s.relation_count ?? 0
        }
      } else {
        stats.value = {
          doc_count: library.value?.doc_count || 0,
          concept_count: library.value?.concept_count || 0,
          relation_count: library.value?.relation_count || 0
        }
      }
    } catch (e) {
      console.error('[LibraryDetail] Failed to load library info:', e)
    }
  }

  function set_selected_doc(doc, { focus = false, bump = true } = {}) {
    if (!doc || !get_doc_id(doc)) return

    selected_doc.value = doc

    if (focus) {
      doc_list_visible.value = false
    }

    if (bump) {
      bump_selected_doc_open_token()
    }

    library_search.setContext({ libraryId: get_library_id(), docId: get_doc_id(doc) })
    broadcast_doc_meta(doc)
  }

  function apply_auto_selection() {
    if (!Array.isArray(documents.value) || !documents.value.length) return

    const forced_id = get_selected_doc_id()
    if (forced_id) {
      const found = documents.value.find((d) => d && get_doc_id(d) === forced_id)
      if (found) {
        set_selected_doc(found, { focus: true, bump: true })
      }
      return
    }

    if (!selected_doc.value) {
      const last_id = get_persisted_last_doc_id()
      if (last_id) {
        const found = documents.value.find((d) => d && get_doc_id(d) === last_id)
        if (found) set_selected_doc(found, { focus: false, bump: true })
      }
    } else {
      const selected_id = get_doc_id(selected_doc.value)
      const fresh = documents.value.find((d) => d && get_doc_id(d) === selected_id)
      if (fresh && fresh !== selected_doc.value) {
        set_selected_doc(fresh, { focus: false, bump: false })
      }
    }

    const mode = get_persisted_focus_mode()
    if (mode === 'focus' && selected_doc.value) doc_list_visible.value = false
    if (mode === 'list') doc_list_visible.value = true

    if (selected_doc.value?.doc_id) {
      library_search.setContext({ libraryId: get_library_id(), docId: selected_doc.value.doc_id })
      broadcast_doc_meta(selected_doc.value)
    } else {
      library_search.setContext({ libraryId: get_library_id(), docId: null })
      broadcast_doc_meta(null)
      clear_last_open_payload()
      clear_global_reader_state('apply_auto_selection_no_doc')
    }
  }

  async function load_documents_impl(token) {
    const res = await call_tool(
      'nisb_doc_stats',
      { library_id: get_library_id() },
      { signal: token?.signal, trackLoading: false }
    )
    if (token?.isStale?.()) return

    if (res && res.status === 'success') {
      if (Array.isArray(res.documents)) documents.value = res.documents
      else if (Array.isArray(res.raw?.documents)) documents.value = res.raw.documents
      else documents.value = []
    } else {
      documents.value = []
    }

    apply_auto_selection()
  }

  async function load_documents() {
    if (load_docs_timer) clearTimeout(load_docs_timer)

    load_docs_timer = setTimeout(async () => {
      const token = begin_load_docs()
      const lib_id_at_start = get_library_id()

      loading_docs.value = true
      try {
        await new Promise((resolve) => requestAnimationFrame(() => resolve()))
        if (token.isStale()) return
        if (get_library_id() !== lib_id_at_start) return

        await load_documents_impl(token)
        if (token.isStale()) return
      } catch (e) {
        if (e && e.name === 'AbortError') return
        console.error('[LibraryDetail] Failed to load documents:', e)
        if (!token.isStale()) documents.value = []
      } finally {
        if (!token.isStale()) loading_docs.value = false
      }
    }, 80)
  }

  function toggle_doc_list() {
    doc_list_visible.value = !doc_list_visible.value
  }

  function reset_doc_state(reason = 'reset') {
    selected_doc.value = null
    bump_selected_doc_open_token()
    library_search.setContext({ libraryId: get_library_id(), docId: null })
    broadcast_doc_meta(null)
    clear_last_open_payload()
    clear_global_reader_state(reason)
  }

  function reset_library_state() {
    library.value = null
    stats.value = null
    documents.value = []

    const mode = get_persisted_focus_mode()
    doc_list_visible.value = mode === 'focus' ? false : true
  }

  function select_doc(doc) {
    if (!doc || !get_doc_id(doc)) return

    set_selected_doc(doc, { focus: true, bump: true })
  }

  function handle_selected_doc_change(d) {
    if (d?.doc_id) set_persisted_last_doc_id(d.doc_id)
    if (!d) {
      doc_list_visible.value = true
      clear_last_open_payload()
      clear_global_reader_state('selected_doc_cleared')
    }
    broadcast_doc_meta(d)
  }

  function handle_doc_list_visible_change(visible) {
    set_persisted_focus_mode(visible ? 'list' : 'focus')
  }

  function initialize_mount_state() {
    const mode = get_persisted_focus_mode()
    if (!mode) set_persisted_focus_mode('list')

    library_search.setContext({ libraryId: get_library_id(), docId: selected_doc.value?.doc_id || null })
    broadcast_doc_meta(selected_doc.value)

    if (!selected_doc.value) {
      clear_last_open_payload()
      clear_global_reader_state('mounted_no_doc')
    }
  }

  function format_time(iso) {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      return d.toLocaleString()
    } catch {
      return iso
    }
  }

  return {
    library,
    stats,
    documents,
    loading_docs,
    selected_doc,
    selected_doc_open_token,
    doc_list_visible,
    load_library_info,
    load_documents,
    apply_auto_selection,
    toggle_doc_list,
    reset_doc_state,
    reset_library_state,
    select_doc,
    handle_selected_doc_change,
    handle_doc_list_visible_change,
    initialize_mount_state,
    clear_last_open_payload,
    broadcast_doc_meta,
    clear_global_reader_state,
    format_time
  }
}
