// /opt/mcp-gateway/nisb-web/src/stores/librarySearch.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useMCP } from '../composables/useMCP'
import { readLocalEvidenceSettings } from '../composables/useNisbSettings'
import { useChatConfigStore } from './chatConfig'

function normalize_focus_root_client(value) {
  let s = String(value || '').trim().replace(/\\/g, '/')
  while (s.includes('//')) s = s.replace(/\/\//g, '/')
  s = s.replace(/^\/+|\/+$/g, '')
  const parts = s
    .split('/')
    .map((x) => String(x || '').trim())
    .filter((x) => x && x !== '.' && x !== '..')
  return parts.join('/')
}

export const useLibrarySearchStore = defineStore('librarySearch', () => {
  const { callTool } = useMCP()
  const chatCfg = useChatConfigStore()
  if (typeof chatCfg.hydrate === 'function') chatCfg.hydrate()

  const libraryId = ref(null)
  const docId = ref(null)
  const group_id = ref(null)
  const scope = ref('doc')

  const context = computed(() => ({
    libraryId: libraryId.value,
    docId: docId.value,
    scope: scope.value,
    group_id: group_id.value,
  }))

  const workspace_id = ref('')
  const workspace_name = ref('')
  const focus_root = ref('')
  const focus_label = ref('')

  const workspace_context = computed(() => ({
    workspace_id: String(workspace_id.value || '').trim(),
    workspace_name: String(workspace_name.value || '').trim(),
    focus_root: normalize_focus_root_client(focus_root.value),
    focus_label: String(focus_label.value || '').trim(),
  }))

  const has_workspace_context = computed(() => {
    const snap = workspace_context.value
    return !!snap.workspace_id || !!snap.focus_root
  })

  function set_workspace_context({
    workspace_id: wid,
    workspace_name: wname,
    focus_root: froot,
    focus_label: flabel,
  } = {}) {
    workspace_id.value = String(wid || '').trim()
    workspace_name.value = String(wname || '').trim()
    focus_root.value = normalize_focus_root_client(froot)
    focus_label.value = String(flabel || '').trim()
  }

  function clear_workspace_context({
    clear_workspace = true,
    clear_focus_root = true,
  } = {}) {
    if (clear_workspace) {
      workspace_id.value = ''
      workspace_name.value = ''
    }
    if (clear_focus_root) {
      focus_root.value = ''
      focus_label.value = ''
    }
  }

  function get_workspace_snapshot() {
    const snap = workspace_context.value
    return {
      workspace_id: snap.workspace_id,
      workspace_name: snap.workspace_name,
      focus_root: snap.focus_root,
      focus_label: snap.focus_label,
    }
  }

  const panelOpen = ref(false)
  const mode = ref('chunk')

  const query = ref('')
  const loading = ref(false)
  const error = ref('')
  const items = ref([])
  const selected = ref(null)

  const time_filter_days = ref(0)
  const time_start = ref('')
  const time_end = ref('')

  const time_filter_label = computed(() => {
    const s = String(time_start.value || '').trim()
    const e = String(time_end.value || '').trim()
    if (s || e) return 'custom'

    const n = Number(time_filter_days.value)
    if (!Number.isFinite(n) || n <= 0) return 'all'
    return String(Math.trunc(n))
  })

  function _s(v) {
    return v === null || v === undefined ? '' : String(v)
  }

  function _numOrNull(v) {
    const n = v === null || v === undefined || v === '' ? null : Number(v)
    return Number.isFinite(n) ? n : null
  }

  function _textFromItem(it) {
    return _s(
      it?.text ??
      it?.quote ??
      it?.snippet ??
      it?.excerpt ??
      it?.content ??
      it?.chunk_text ??
      ''
    ).trim()
  }

  function _relevanceFromItem(it) {
    const r = Number(
      it?.relevance ??
      it?.similarity ??
      it?.score ??
      0
    )
    return Number.isFinite(r) ? r : 0
  }

  function _chunkIdFromItem(it) {
    const n =
      _numOrNull(it?.chunk_id) ??
      _numOrNull(it?.chunkId)

    if (n !== null) return n

    const s = _s(it?.chunk_id ?? it?.chunkId).trim()
    return s || null
  }

  function _spanFromItem(it) {
    return (
      _numOrNull(it?.span_index) ??
      _numOrNull(it?.spanIndex) ??
      _numOrNull(it?.span_id) ??
      _numOrNull(it?.spanId) ??
      _numOrNull(it?.start_span) ??
      _numOrNull(it?.startSpan) ??
      _numOrNull(it?.span_start) ??
      _numOrNull(it?.spanStart)
    )
  }

  function _normalizeSelectedItem(raw) {
    const it = raw && typeof raw === 'object' ? raw : {}

    const lib = _s(it.library_id ?? it.libraryId).trim() || null
    const doc = _s(it.doc_id ?? it.docId).trim() || null
    const span = _spanFromItem(it)
    const chunk_id = _chunkIdFromItem(it)
    const text = _textFromItem(it)
    const relevance = _relevanceFromItem(it)

    return {
      ...it,
      library_id: lib,
      doc_id: doc,
      span_index: span,
      chunk_id,
      relevance,
      text
    }
  }

  function set_time_filter_days(days) {
    const n = Number(days)
    time_start.value = ''
    time_end.value = ''
    if (!Number.isFinite(n)) {
      time_filter_days.value = 0
      return
    }
    time_filter_days.value = Math.max(0, Math.min(3650, Math.trunc(n)))
  }

  function set_time_start(v) {
    time_start.value = String(v || '').trim()
  }

  function set_time_end(v) {
    time_end.value = String(v || '').trim()
  }

  function clear_time_window() {
    time_filter_days.value = 0
    time_start.value = ''
    time_end.value = ''
  }

  const canSearch = computed(() => {
    const qOk = !!String(query.value || '').trim()
    if (!qOk) return false

    if (scope.value === 'doc') return !!libraryId.value && !!docId.value
    if (scope.value === 'library') return !!libraryId.value || !!group_id.value
    return true
  })

  function openPanel() {
    panelOpen.value = true
  }

  function closePanel() {
    panelOpen.value = false
  }

  function resetResults() {
    loading.value = false
    error.value = ''
    items.value = []
    selected.value = null
  }

  function clearAll() {
    query.value = ''
    resetResults()
    closePanel()
  }

  function setGroupId(v, { preserveResults = false } = {}) {
    const next = String(v || '').trim() || null
    const changed = group_id.value !== next
    group_id.value = next

    if (!preserveResults && changed) {
      resetResults()
      closePanel()
    }
  }

  function setContext({ libraryId: lib, docId: doc, preserveResults = false, source = 'user' } = {}) {
    if (String(source || '') === 'chat_local_citations') {
      const s = readLocalEvidenceSettings()
      if (!s.autoselect) return
    }

    const nextLib = lib || null
    const nextDoc = doc || null

    const libChanged = libraryId.value !== nextLib
    const docChanged = docId.value !== nextDoc

    libraryId.value = nextLib
    docId.value = nextDoc

    if (!preserveResults && (libChanged || docChanged)) {
      resetResults()
      closePanel()
    }
  }

  function set_context_from_chat_local_citations({ libraryId: lib, docId: doc, preserveResults = true } = {}) {
    setContext({ libraryId: lib, docId: doc, preserveResults, source: 'chat_local_citations' })
  }

  function set_context_from_user_click({ libraryId: lib, docId: doc, preserveResults = true } = {}) {
    setContext({ libraryId: lib, docId: doc, preserveResults, source: 'user_click' })
  }

  function setScope(s) {
    if (s !== 'doc' && s !== 'library' && s !== 'global') return

    const changed = scope.value !== s
    scope.value = s
    error.value = ''

    if (changed) {
      resetResults()
      openPanel()
    }

    if (scope.value === 'doc' && !docId.value) {
      error.value = 'scope=doc 需要先选定一本书（doc）'
    }

    if (scope.value === 'library' && !libraryId.value && !group_id.value) {
      error.value = 'scope=library 需要先选定一个库（libraryId）或一个编组（group_id）'
    }
  }

  function setMode(m) {
    if (m !== 'chunk' && m !== 'evidence') return
    if (mode.value !== m) {
      mode.value = m
      resetResults()
      openPanel()
    }
  }

  function selectItem(it) {
    selected.value = it ? _normalizeSelectedItem(it) : null
  }

  function _getGlobalReader() {
    try {
      return window.__nisbReaderState || window.nisbReaderState || null
    } catch {
      return null
    }
  }

  function jumpSelected() {
    const it = selected.value
    if (!it) return

    const spanIndex = _spanFromItem(it)
    if (!Number.isFinite(spanIndex)) return

    const lib = it.library_id
    const doc = it.doc_id
    if (!lib || !doc) return

    const openDetail = {
      libraryId: String(lib),
      docId: String(doc),
      spanIndex: Number(spanIndex),
      reader: _getGlobalReader()
    }

    try {
      window.__nisb_last_library_doc_open = openDetail
    } catch {}

    window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: openDetail }))
    closePanel()
  }

  function _setItemsArray(arr) {
    items.value = Array.isArray(arr) ? arr : []
  }

  function _extractResults(res) {
    const rawResults = res?.raw?.results
    if (Array.isArray(rawResults)) return rawResults
    if (Array.isArray(res?.results)) return res.results
    if (Array.isArray(res?.items)) return res.items
    return []
  }

  function _buildEvidenceTimeArgs() {
    const s = String(time_start.value || '').trim()
    const e = String(time_end.value || '').trim()
    if (s || e) {
      return {
        time_start: s || undefined,
        time_end: e || undefined
      }
    }

    const n = Number(time_filter_days.value)
    return {
      time_filter_days: Number.isFinite(n) ? Math.max(0, Math.min(3650, Math.trunc(n))) : 0
    }
  }

  function _buildScopeFilterArgs() {
    if (scope.value === 'doc') {
      return {
        library_id: libraryId.value || undefined,
        doc_id: docId.value || undefined,
        group_id: undefined,
      }
    }

    if (scope.value === 'library') {
      if (libraryId.value) {
        return {
          library_id: libraryId.value,
          doc_id: undefined,
          group_id: undefined,
        }
      }
      if (group_id.value) {
        return {
          library_id: undefined,
          doc_id: undefined,
          group_id: group_id.value,
        }
      }
      return {
        library_id: undefined,
        doc_id: undefined,
        group_id: undefined,
      }
    }

    return {
      library_id: undefined,
      doc_id: undefined,
      group_id: undefined,
    }
  }

  async function search({ topK = 8, maxChars = 8000 } = {}) {
    resetResults()

    const q = String(query.value || '').trim()
    if (!q) {
      error.value = 'query 不能为空'
      openPanel()
      return
    }

    if (scope.value === 'doc' && (!libraryId.value || !docId.value)) {
      error.value = '请先打开库文档（scope=doc 需要 libraryId + docId）'
      openPanel()
      return
    }

    if (scope.value === 'library' && !libraryId.value && !group_id.value) {
      error.value = '请先选择一个库或编组（scope=library 需要 libraryId 或 group_id）'
      openPanel()
      return
    }

    openPanel()
    loading.value = true

    try {
      const scopeArgs = _buildScopeFilterArgs()

      if (mode.value === 'evidence') {
        if (scope.value === 'doc') {
          const res = await callTool('nisb_library_doc_evidence', {
            query: q,
            library_id: scopeArgs.library_id,
            doc_id: scopeArgs.doc_id,
            top_k: topK,
            max_chars: maxChars,
            include_text: true
          })

          if (!res || res.status !== 'success') {
            error.value = res?.message || 'Evidence 查询失败'
            return
          }

          _setItemsArray(res.items)
          return
        }

        const res = await callTool('nisb_doc_evidence_scope', {
          query: q,
          scope: scope.value,
          library_id: scopeArgs.library_id,
          doc_id: undefined,
          group_id: scopeArgs.group_id,
          top_k: topK,
          max_chars: maxChars,
          include_text: true,
          ..._buildEvidenceTimeArgs()
        })

        if (!res || res.status !== 'success') {
          error.value = res?.message || 'Evidence(scope) 查询失败'
          return
        }

        _setItemsArray(res.items)
        return
      }

      const args = {
        query: q,
        top_k: topK,
        library_id: scopeArgs.library_id,
        doc_id: scopeArgs.doc_id,
        group_id: scopeArgs.group_id,
      }

      const res = await callTool('nisb_doc_search_hybrid', args)

      if (!res || res.status !== 'success') {
        error.value = res?.message || 'Chunk 查询失败'
        return
      }

      _setItemsArray(_extractResults(res))
    } catch (e) {
      error.value = String(e?.message || e)
    } finally {
      loading.value = false
    }
  }

  return {
    libraryId,
    docId,
    group_id,
    scope,
    context,
    panelOpen,
    mode,
    query,
    loading,
    error,
    items,
    selected,
    canSearch,

    workspace_id,
    workspace_name,
    focus_root,
    focus_label,
    workspace_context,
    has_workspace_context,
    set_workspace_context,
    clear_workspace_context,
    get_workspace_snapshot,

    time_filter_days,
    time_start,
    time_end,
    time_filter_label,
    set_time_filter_days,
    set_time_start,
    set_time_end,
    clear_time_window,

    openPanel,
    closePanel,
    setGroupId,
    setContext,
    set_context_from_chat_local_citations,
    set_context_from_user_click,
    setScope,
    setMode,
    search,
    selectItem,
    jumpSelected,
    clearAll,
    resetResults
  }
})

