import { ref, computed, unref } from 'vue'

function string_value(value) {
  return String(value ?? '').trim()
}

function normalize_locale(value) {
  const raw = string_value(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      if (typeof localStorage === 'undefined') continue
      const value = localStorage.getItem(key)
      if (value !== null && string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function runtime_locale() {
  const from_window = (() => {
    try {
      if (typeof window === 'undefined') return ''
      return (
        window?.__nisb_locale ||
        window?.__nisb_ui_locale ||
        window?.__NISB_LOCALE__ ||
        window?.__NISB_UI_LOCALE__ ||
        ''
      )
    } catch {
      return ''
    }
  })()

  const from_storage = local_storage_first(
    [
      'nisb_locale',
      'nisb_ui_locale',
      'nisb_language',
      'nisb_settings_locale',
      'locale',
      'ui_locale',
      'language'
    ],
    ''
  )

  const from_document = (() => {
    try {
      if (typeof document === 'undefined') return ''
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  const from_navigator = (() => {
    try {
      if (typeof navigator === 'undefined') return ''
      return navigator?.language || ''
    } catch {
      return ''
    }
  })()

  return normalize_locale(from_window || from_storage || from_document || from_navigator || 'en')
}

export function use_library_doc_mutations({
  library_id_ref,
  documents,
  selected_doc,
  library_search,
  call_tool,
  ensure_library_id,
  refresh_after_mutation,
  reset_doc_state,
  broadcast_doc_meta,
  locale_ref = null,
  t: external_t = null
}) {
  const delete_dialog_open = ref(false)
  const delete_target_doc = ref(null)
  const delete_working = ref(false)

  const rename_dialog_open = ref(false)
  const rename_target_doc = ref(null)
  const rename_value = ref('')
  const rename_working = ref(false)

  const batch_delete_open = ref(false)
  const batch_delete_working = ref(false)
  const batch_delete_filter = ref('')
  const batch_selected_map = ref({})

  function current_locale() {
    return normalize_locale(unref(locale_ref) || runtime_locale())
  }

  function text(path, params = {}, fallback = '') {
    if (typeof external_t === 'function') {
      try {
        const value = external_t(path, params, fallback)
        if (string_value(value) && value !== path) return value
      } catch {}
    }
    return format_text(fallback || path, params)
  }

  function unknown_error() {
    return text('center.docMutations.unknownError', {}, 'Unknown error')
  }

  function error_detail(value) {
    return string_value(value) || unknown_error()
  }

  function alert_message(message) {
    try {
      alert(message)
    } catch {}
  }

  function tool_args(args = {}) {
    return {
      ...args,
      locale: current_locale(),
      ui_locale: current_locale()
    }
  }

  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function close_batch_delete_now() {
    batch_delete_open.value = false
    batch_delete_filter.value = ''
    batch_selected_map.value = {}
  }

  const filtered_docs = computed(() => {
    const q = (batch_delete_filter.value || '').trim().toLowerCase()
    const list = Array.isArray(documents.value) ? documents.value : []
    if (!q) return list
    return list.filter((d) => {
      const fn = String(d?.filename || '').toLowerCase()
      const id = String(d?.doc_id || '').toLowerCase()
      return fn.includes(q) || id.includes(q)
    })
  })

  const selected_batch_ids = computed(() => {
    const map = batch_selected_map.value || {}
    return Object.keys(map).filter((key) => map[key])
  })

  const selected_batch_count = computed(() => selected_batch_ids.value.length)

  function open_batch_delete() {
    batch_delete_filter.value = ''
    batch_selected_map.value = {}
    batch_delete_open.value = true
  }

  function close_batch_delete() {
    if (batch_delete_working.value) return
    close_batch_delete_now()
  }

  function toggle_batch_select(doc_id) {
    const id = string_value(doc_id)
    if (!id || batch_delete_working.value) return

    const map = { ...(batch_selected_map.value || {}) }
    map[id] = !map[id]
    batch_selected_map.value = map
  }

  function select_all_filtered() {
    if (batch_delete_working.value) return

    const map = { ...(batch_selected_map.value || {}) }
    for (const doc of filtered_docs.value) {
      if (doc?.doc_id) map[doc.doc_id] = true
    }
    batch_selected_map.value = map
  }

  function clear_batch_selection() {
    if (batch_delete_working.value) return
    batch_selected_map.value = {}
  }

  async function confirm_batch_delete() {
    if (!ensure_library_id()) return

    const ids = selected_batch_ids.value
    if (!ids.length) {
      alert_message(text('center.docMutations.batchDeleteNoSelection', {}, 'Select at least one document to delete.'))
      return
    }

    batch_delete_working.value = true
    try {
      const res = await call_tool(
        'nisb_library_doc_delete_batch',
        tool_args({
          library_id: get_library_id(),
          doc_ids: ids,
          delete_dir: true,
          continue_on_error: true,
          ignore_missing: true
        })
      )

      if (res && res.status === 'success') {
        if (selected_doc.value && ids.includes(selected_doc.value.doc_id)) {
          selected_doc.value = null
          library_search.setContext({ libraryId: get_library_id(), docId: null })
        }

        alert_message(
          text(
            'center.docMutations.batchDeleteSuccess',
            { count: ids.length },
            'Batch delete completed. Deleted {count} document(s).'
          )
        )

        close_batch_delete_now()
        await refresh_after_mutation({ retryDocs: 1, retryDelayMs: 250 })
      } else {
        alert_message(
          text(
            'center.docMutations.batchDeleteFailed',
            { error: error_detail(res?.message) },
            'Batch delete failed: {error}'
          )
        )
      }
    } catch (e) {
      alert_message(
        text(
          'center.docMutations.batchDeleteFailed',
          { error: error_detail(e?.message || String(e)) },
          'Batch delete failed: {error}'
        )
      )
    } finally {
      batch_delete_working.value = false
    }
  }

  function request_delete_doc(doc) {
    delete_target_doc.value = doc
    delete_dialog_open.value = true
  }

  function cancel_delete_doc() {
    delete_dialog_open.value = false
    delete_target_doc.value = null
  }

  async function confirm_delete_doc() {
    if (!ensure_library_id()) return
    if (!delete_target_doc.value) return

    delete_working.value = true
    try {
      const res = await call_tool(
        'nisb_library_doc_delete',
        tool_args({
          library_id: get_library_id(),
          doc_id: delete_target_doc.value.doc_id
        })
      )

      if (res && res.status === 'success') {
        if (selected_doc.value && selected_doc.value.doc_id === delete_target_doc.value.doc_id) {
          reset_doc_state('delete_doc_cleared')
        }
        await refresh_after_mutation({ retryDocs: 1, retryDelayMs: 250 })
        cancel_delete_doc()
      } else {
        alert_message(
          text(
            'center.docMutations.deleteFailed',
            { error: error_detail(res?.message) },
            'Delete failed: {error}'
          )
        )
      }
    } catch (e) {
      alert_message(
        text(
          'center.docMutations.deleteFailed',
          { error: error_detail(e?.message || String(e)) },
          'Delete failed: {error}'
        )
      )
    } finally {
      delete_working.value = false
    }
  }

  function request_rename_doc(doc) {
    rename_target_doc.value = doc
    rename_value.value = (doc?.filename || '').trim()
    rename_dialog_open.value = true
  }

  function cancel_rename_doc() {
    rename_dialog_open.value = false
    rename_target_doc.value = null
    rename_value.value = ''
  }

  async function confirm_rename_doc() {
    if (!ensure_library_id()) return

    const doc = rename_target_doc.value
    const new_name = (rename_value.value || '').trim()
    if (!doc) return

    if (!new_name) {
      alert_message(text('center.docMutations.newFilenameRequired', {}, 'New filename cannot be empty.'))
      return
    }

    rename_working.value = true
    try {
      const res = await call_tool(
        'nisb_library_doc_rename',
        tool_args({
          library_id: get_library_id(),
          doc_id: doc.doc_id,
          new_filename: new_name
        })
      )

      if (res && res.status === 'success') {
        if (selected_doc.value && selected_doc.value.doc_id === doc.doc_id) {
          selected_doc.value = { ...selected_doc.value, filename: new_name }
          broadcast_doc_meta(selected_doc.value)
        }
        await refresh_after_mutation({ retryDocs: 1, retryDelayMs: 250 })
        cancel_rename_doc()
      } else {
        alert_message(
          text(
            'center.docMutations.renameFailed',
            { error: error_detail(res?.message) },
            'Rename failed: {error}'
          )
        )
      }
    } catch (e) {
      alert_message(
        text(
          'center.docMutations.renameFailed',
          { error: error_detail(e?.message || String(e)) },
          'Rename failed: {error}'
        )
      )
    } finally {
      rename_working.value = false
    }
  }

  function reset_mutation_state() {
    cancel_delete_doc()
    cancel_rename_doc()
    batch_delete_filter.value = ''
    batch_selected_map.value = {}
    batch_delete_open.value = false
    batch_delete_working.value = false
  }

  return {
    delete_dialog_open,
    delete_target_doc,
    delete_working,
    rename_dialog_open,
    rename_target_doc,
    rename_value,
    rename_working,
    batch_delete_open,
    batch_delete_working,
    batch_delete_filter,
    batch_selected_map,
    filtered_docs,
    selected_batch_ids,
    selected_batch_count,
    open_batch_delete,
    close_batch_delete,
    toggle_batch_select,
    select_all_filtered,
    clear_batch_selection,
    confirm_batch_delete,
    request_delete_doc,
    cancel_delete_doc,
    confirm_delete_doc,
    request_rename_doc,
    cancel_rename_doc,
    confirm_rename_doc,
    reset_mutation_state
  }
}
