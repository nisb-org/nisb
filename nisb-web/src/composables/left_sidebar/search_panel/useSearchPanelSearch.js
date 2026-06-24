import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../useMCP'
import { normalizeToolResponse } from '../actions/response_normalizer'
import {
  toSafeArray,
  isPlainObject,
  normalizeDisplayText,
  normalizePathValue,
  pathTail,
  normalizeQueryClient,
  pickBetterItem,
  sortResultItems,
  sourceLabel,
  normalizeLogicalModule
} from './useSearchPanelHelpers'

const PAGE_SIZE = 10
const FETCH_LIMIT = 100
const SEARCH_DEBOUNCE_MS = 220
const CACHE_LIMIT = 20
const FILTERS_STORAGE_KEY = 'nisb_search_panel_filters_v1'
const DEBUG_STORAGE_KEY = 'nisb_search_panel_debug_v1'
const DEBUG_PANEL_ALLOWED =
  import.meta.env.DEV === true ||
  String(import.meta.env.VITE_ENABLE_SEARCH_DEBUG_PANEL || '').trim() === '1' ||
  String(import.meta.env.VITE_ENABLE_SEARCH_DEBUG_PANEL || '').trim().toLowerCase() === 'true'

const CACHE_SENSITIVE_CAMEL_RE = /^(?:[A-Z][a-z0-9]+|[a-z][a-z0-9]+)(?:[A-Z][a-z0-9]+){1,}$/
const CACHE_SENSITIVE_EXT_RE = /\.[A-Za-z0-9]{1,12}$/

function emptyResults() {
  return {
    chat: [],
    dirs: [],
    files: [],
    library: [],
    doc: []
  }
}

function emptyCounts() {
  return {
    chat: 0,
    dirs: 0,
    files: 0,
    library: 0,
    doc: 0
  }
}

function emptyDebugMeta() {
  return {
    enabled: false,
    status: '',
    message: '',
    took_ms: 0,
    open_elapsed_ms: 0,
    sync_elapsed_ms: 0,
    query_elapsed_ms: 0,
    sync_mode: '',
    selected_index_total: 0,
    group_counts: {
      chat: 0,
      dirs: 0,
      files: 0,
      library: 0
    },
    used_fast_path: false,
    fallback_to_db_open: false,
    busy_timeout: 0,
    mmap_size: 0,
    journal_mode: '',
    temp_store: '',
    db_path: '',
    query_tokens: [],
    mode: ''
  }
}

function defaultEnabledCategories() {
  return {
    chat: true,
    dirs: true,
    files: true,
    library: true
  }
}

function sanitizeEnabledCategories(value) {
  return {
    chat: !!value?.chat,
    dirs: !!value?.dirs,
    files: !!value?.files,
    library: !!value?.library
  }
}

function sameEnabledCategories(a, b) {
  return !!a && !!b &&
    a.chat === b.chat &&
    a.dirs === b.dirs &&
    a.files === b.files &&
    a.library === b.library
}

function loadEnabledCategories() {
  try {
    const raw = localStorage.getItem(FILTERS_STORAGE_KEY)
    if (!raw) return defaultEnabledCategories()
    return sanitizeEnabledCategories(JSON.parse(raw))
  } catch {
    return defaultEnabledCategories()
  }
}

function saveEnabledCategories(value) {
  try {
    localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(sanitizeEnabledCategories(value)))
  } catch {}
}

function loadDebugPanelEnabled() {
  if (!DEBUG_PANEL_ALLOWED) return false
  try {
    const raw = localStorage.getItem(DEBUG_STORAGE_KEY)
    if (raw == null) return import.meta.env.DEV === true
    return raw === '1' || raw === 'true'
  } catch {
    return import.meta.env.DEV === true
  }
}

function saveDebugPanelEnabled(value) {
  if (!DEBUG_PANEL_ALLOWED) return
  try {
    localStorage.setItem(DEBUG_STORAGE_KEY, value ? '1' : '0')
  } catch {}
}

function dedupeBy(list, keyFn) {
  const map = new Map()
  for (const item of toSafeArray(list)) {
    const key = String(keyFn(item) || '').trim()
    if (!key) continue
    const prev = map.get(key)
    map.set(key, pickBetterItem(prev, item))
  }
  return [...map.values()]
}

function uniqueKeepOrder(values) {
  const out = []
  const seen = new Set()

  for (const value of toSafeArray(values)) {
    const text = String(value || '').trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }

  return out
}

function fileStableKey(item) {
  return String(
    item?.__origin_key ||
    item?.__parent_key ||
    item?.item_key ||
    normalizePathValue(item?.path) ||
    `${item?.__source || ''}:${item?.filename || ''}`
  ).trim()
}

function fileVisualKey(item) {
  const name = normalizeDisplayText(item?.filename).toLowerCase()
  const shortPath = pathTail(item?.path, 2).toLowerCase()
  const matchType = String(item?.match_type || '').trim().toLowerCase()
  const snippet = normalizeDisplayText(item?.snippet).toLowerCase().slice(0, 220)
  return `${name}|${shortPath}|${matchType}|${snippet}`
}

function dedupeVisibleFiles(list) {
  const firstPass = dedupeBy(toSafeArray(list), (x) => fileStableKey(x))
  const secondPass = dedupeBy(firstPass, (x) => fileVisualKey(x) || fileStableKey(x))
  return sortResultItems(
    secondPass.map((item) => ({
      ...item,
      __key: fileStableKey(item) || fileVisualKey(item)
    }))
  )
}

function normalizeChatItem(item) {
  return {
    conv_id: item?.conv_id || '',
    title: String(item?.title || '').trim(),
    created_at: item?.created_at || '',
    turn_count: Number(item?.turn_count || 0),
    hit_count: Number(item?.hit_count || 1),
    match_type: String(item?.match_type || '').trim(),
    match_reason: String(item?.match_reason || '').trim(),
    matched_terms: toSafeArray(item?.matched_terms),
    snippet: String(item?.snippet || '').trim(),
    score: Number(item?.score || 0),
    __key: String(item?.item_key || item?.conv_id || item?.key || '').trim()
  }
}

function normalizeFileItem(item, t) {
  const rawPath = normalizePathValue(item?.path)
  const defaultFilename = t('sidebar.search.results.unnamedFile')
  const filename =
    String(item?.filename || '').trim() ||
    String(item?.title || '').trim() ||
    rawPath.split('/').pop() ||
    defaultFilename

  const rawSourceModules = [
    ...toSafeArray(item?.source_modules),
    item?.source_module,
    item?.raw_module,
    item?.module
  ]

  const sourceModules = uniqueKeepOrder(
    rawSourceModules
      .map((x) => normalizeLogicalModule(x))
      .filter((x) => x === 'files')
  )

  const sourceLabelText = uniqueKeepOrder(
    sourceModules.map((x) => sourceLabel(x, t)).filter(Boolean)
  ).join(' + ')

  const originKey = String(item?.item_key || item?.key || '').trim()
  const parentKey = String(item?.parent_key || '').trim()

  return {
    filename,
    path: rawPath,
    snippet: String(item?.snippet || '').trim(),
    match_type: String(item?.match_type || '').trim(),
    match_reason: String(item?.match_reason || '').trim(),
    matched_terms: toSafeArray(item?.matched_terms),
    score: Number(item?.score || 0),
    hit_count: Number(item?.hit_count || 1),
    __source: 'files',
    __source_modules: sourceModules.length > 0 ? sourceModules : ['files'],
    __sourceLabel: sourceLabelText || sourceLabel('files', t) || 'files',
    __origin_key: originKey,
    __parent_key: parentKey,
    __path_short: pathTail(rawPath, 2),
    __key: originKey || parentKey || `files:${rawPath || filename}`
  }
}

function normalizeDirItem(item, t) {
  const path = normalizePathValue(item?.path)
  const defaultDirname = t('sidebar.search.results.unnamedDirectory')
  const dirname =
    String(item?.dirname || '').trim() ||
    String(item?.title || '').trim() ||
    path.split('/').filter(Boolean).slice(-1)[0] ||
    defaultDirname

  return {
    dirname,
    path,
    snippet: String(item?.snippet || '').trim(),
    match_type: String(item?.match_type || '').trim(),
    match_reason: String(item?.match_reason || '').trim(),
    matched_terms: toSafeArray(item?.matched_terms),
    score: Number(item?.score || 0),
    hit_count: Number(item?.hit_count || 1),
    __key: String(item?.item_key || item?.key || item?.parent_key || `dir:${path || dirname}`).trim()
  }
}

function normalizeLibraryItem(item) {
  return {
    library_id: item?.library_id || item?.libraryId || '',
    library_name: item?.library_name || item?.libraryName || '',
    doc_id: item?.doc_id || item?.docId || '',
    title: String(item?.title || '').trim(),
    filename: String(item?.filename || '').trim(),
    doc_title: String(item?.doc_title || '').trim(),
    snippet: String(item?.snippet || '').trim(),
    description: String(item?.description || '').trim(),
    match_type: String(item?.match_type || '').trim(),
    match_reason: String(item?.match_reason || '').trim(),
    matched_terms: toSafeArray(item?.matched_terms),
    score: Number(item?.score || 0),
    hit_count: Number(item?.hit_count || 1),
    parent_key: String(item?.parent_key || '').trim(),
    key: String(item?.item_key || item?.key || '').trim()
  }
}

function extractGroupItems(grouped, key) {
  const bucket = grouped?.[key]
  if (Array.isArray(bucket)) return bucket
  if (isPlainObject(bucket) && Array.isArray(bucket.items)) return bucket.items
  if (isPlainObject(bucket) && Array.isArray(bucket.results)) return bucket.results
  return []
}

function normalizePayloadFromInfo(info, t) {
  const data = isPlainObject(info?.data) ? info.data : {}
  const grouped = isPlainObject(data?.grouped) ? data.grouped : {}

  const next = {
    chat: sortResultItems(
      dedupeBy(
        extractGroupItems(grouped, 'chat').map(normalizeChatItem),
        (x) => x.conv_id || x.__key
      )
    ),
    dirs: sortResultItems(
      dedupeBy(
        extractGroupItems(grouped, 'dirs').map((item) => normalizeDirItem(item, t)),
        (x) => x.path || x.dirname || x.__key
      )
    ),
    files: dedupeVisibleFiles(
      extractGroupItems(grouped, 'files').map((item) => normalizeFileItem(item, t))
    ),
    library: sortResultItems(
      dedupeBy(
        extractGroupItems(grouped, 'library').map(normalizeLibraryItem),
        (x) => String(x.key || x.parent_key || `${x.library_id}:${x.doc_id || x.title || x.library_name}`).trim()
      )
    ),
    doc: []
  }

  const totals = isPlainObject(data?.totals) ? data.totals : {}

  const counts = {
    chat: Number(totals.chat ?? next.chat.length),
    dirs: Number(totals.dirs ?? next.dirs.length),
    files: Number(totals.files ?? next.files.length),
    library: Number(totals.library ?? next.library.length),
    doc: 0
  }

  const computedTotal =
    counts.chat +
    counts.dirs +
    counts.files +
    counts.library

  const total = Number(data?.total ?? computedTotal)

  const normalized_query =
    String(data?.query_norm || '').trim() ||
    String(data?.normalized_query || '').trim() ||
    String(data?.query || '').trim()

  return {
    results: next,
    total,
    normalized_query,
    counts,
    payloadRoot: data
  }
}

function extractDebugMeta(info, normalizedPayload, showDebugPanelValue, currentMode) {
  const payloadRoot = normalizedPayload?.payloadRoot || {}
  const raw = isPlainObject(info?.raw) ? info.raw : {}
  const evidenceResult = isPlainObject(raw?.evidence_result) ? raw.evidence_result : {}
  const sync = isPlainObject(payloadRoot?.sync) ? payloadRoot.sync : {}
  const runtimePragmas = isPlainObject(sync?.runtime_pragmas) ? sync.runtime_pragmas : {}
  const openRuntime = isPlainObject(sync?.open_runtime) ? sync.open_runtime : {}

  return {
    enabled: !!showDebugPanelValue,
    status: String(info?.status || raw?.status || ''),
    message: String(info?.message || raw?.message || ''),
    took_ms: Number(payloadRoot?.took_ms || evidenceResult?.took_ms || 0),
    open_elapsed_ms: Number(evidenceResult?.open_elapsed_ms || 0),
    sync_elapsed_ms: Number(evidenceResult?.sync_elapsed_ms || 0),
    query_elapsed_ms: Number(evidenceResult?.query_elapsed_ms || 0),
    sync_mode: String(sync?.mode || ''),
    selected_index_total: Number(sync?.selected_index_total || 0),
    group_counts: {
      chat: Number(normalizedPayload?.counts?.chat || 0),
      dirs: Number(normalizedPayload?.counts?.dirs || 0),
      files: Number(normalizedPayload?.counts?.files || 0),
      library: Number(normalizedPayload?.counts?.library || 0)
    },
    used_fast_path: Boolean(openRuntime?.used_fast_path),
    fallback_to_db_open: Boolean(openRuntime?.fallback_to_db_open),
    busy_timeout: Number(runtimePragmas?.busy_timeout || 0),
    mmap_size: Number(runtimePragmas?.mmap_size || 0),
    journal_mode: String(runtimePragmas?.journal_mode || ''),
    temp_store: String(runtimePragmas?.temp_store || ''),
    db_path: String(payloadRoot?.db_path || openRuntime?.db_path || ''),
    query_tokens: toSafeArray(payloadRoot?.query_tokens),
    mode: currentMode
  }
}

function buildSearchCacheKey(rawQuery, normalizedQuery, modules) {
  return JSON.stringify({
    q_raw: String(rawQuery || '').trim(),
    q_norm: String(normalizedQuery || '').trim(),
    modules: toSafeArray(modules).map((x) => String(x || '').trim()),
    limit: FETCH_LIMIT,
    per_module_limit: FETCH_LIMIT,
    fuzzy: true
  })
}

function isCacheSensitiveSearchQuery(rawQuery) {
  const q = String(rawQuery || '').trim()
  if (!q) return false
  if (/\s/.test(q)) return false

  if (q.includes('/') || q.includes('\\')) return true
  if (q.endsWith('.')) return true
  if (q.includes('.')) return true
  if (q.includes('_') || q.includes('-')) return true
  if (CACHE_SENSITIVE_EXT_RE.test(q)) return true
  if (CACHE_SENSITIVE_CAMEL_RE.test(q)) return true

  return false
}

export function useSearchPanelSearch(options = {}) {
  const { callTool } = useMCP()
  const { t } = useI18n()
  const currentMode = String(import.meta.env.MODE || '')
  const isVisible = typeof options.isVisible === 'function'
    ? options.isVisible
    : () => !!options.isVisible

  const query = ref('')
  const searching = ref(false)
  const normalizedQueryText = ref('')
  const results = ref(emptyResults())
  const totalResults = ref(0)
  const debugPanelEnabled = ref(loadDebugPanelEnabled())
  const debugOpen = ref(true)
  const debugMeta = ref(emptyDebugMeta())

  const countsState = ref(emptyCounts())
  const enabledCategories = ref(loadEnabledCategories())

  const showCount = ref({
    chat: PAGE_SIZE,
    dirs: PAGE_SIZE,
    files: PAGE_SIZE,
    library: PAGE_SIZE
  })

  let searchTimer = null
  let activeSearchId = 0
  const searchCache = new Map()

  function toggleDebugPanel() {
    if (!DEBUG_PANEL_ALLOWED) return
    debugPanelEnabled.value = !debugPanelEnabled.value
    saveDebugPanelEnabled(debugPanelEnabled.value)
  }

  function resetPaging() {
    showCount.value = {
      chat: PAGE_SIZE,
      dirs: PAGE_SIZE,
      files: PAGE_SIZE,
      library: PAGE_SIZE
    }
  }

  function resetResults() {
    results.value = emptyResults()
    totalResults.value = 0
    normalizedQueryText.value = ''
    countsState.value = emptyCounts()
    debugMeta.value = emptyDebugMeta()
    resetPaging()
  }

  function cancelPendingOnly() {
    activeSearchId += 1
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
    searching.value = false
  }

  function cancelPendingAndReset() {
    cancelPendingOnly()
    resetResults()
  }

  function clearSearchCache() {
    searchCache.clear()
  }

  function cacheSet(key, value) {
    if (!key) return
    if (searchCache.has(key)) {
      searchCache.delete(key)
    }
    searchCache.set(key, value)
    while (searchCache.size > CACHE_LIMIT) {
      const firstKey = searchCache.keys().next().value
      searchCache.delete(firstKey)
    }
  }

  const hasEnabledCategory = computed(() => {
    const v = enabledCategories.value
    return !!(v.chat || v.dirs || v.files || v.library)
  })

  const debugPanelAvailable = computed(() => DEBUG_PANEL_ALLOWED)

  const showDebugPanel = computed(() => {
    return !!(DEBUG_PANEL_ALLOWED && debugPanelEnabled.value)
  })

  const backendModules = computed(() => {
    const modules = []
    if (enabledCategories.value.chat) modules.push('chat')
    if (enabledCategories.value.dirs) modules.push('dirs')
    if (enabledCategories.value.files) modules.push('files')
    if (enabledCategories.value.library) modules.push('library')
    return modules
  })

  const mergedFiles = computed(() => {
    return dedupeVisibleFiles(results.value.files)
  })

  const displayCounts = computed(() => ({
    chat: enabledCategories.value.chat ? Number(countsState.value.chat || results.value.chat.length || 0) : 0,
    dirs: enabledCategories.value.dirs ? Number(countsState.value.dirs || results.value.dirs.length || 0) : 0,
    files: enabledCategories.value.files ? Number(countsState.value.files || mergedFiles.value.length || 0) : 0,
    library: enabledCategories.value.library ? Number(countsState.value.library || results.value.library.length || 0) : 0
  }))

  const visibleChat = computed(() => results.value.chat.slice(0, showCount.value.chat))
  const visibleDirs = computed(() => results.value.dirs.slice(0, showCount.value.dirs))
  const visibleFiles = computed(() => mergedFiles.value.slice(0, showCount.value.files))
  const visibleLibrary = computed(() => results.value.library.slice(0, showCount.value.library))

  const hasMoreChat = computed(() => results.value.chat.length > showCount.value.chat)
  const hasMoreDirs = computed(() => results.value.dirs.length > showCount.value.dirs)
  const hasMoreFiles = computed(() => mergedFiles.value.length > showCount.value.files)
  const hasMoreLibrary = computed(() => results.value.library.length > showCount.value.library)
  const hasMoreAny = computed(() => hasMoreChat.value || hasMoreDirs.value || hasMoreFiles.value || hasMoreLibrary.value)

  function loadMoreChat() {
    showCount.value.chat = Math.min(results.value.chat.length, showCount.value.chat + PAGE_SIZE)
  }

  function loadMoreDirs() {
    showCount.value.dirs = Math.min(results.value.dirs.length, showCount.value.dirs + PAGE_SIZE)
  }

  function loadMoreFiles() {
    showCount.value.files = Math.min(mergedFiles.value.length, showCount.value.files + PAGE_SIZE)
  }

  function loadMoreLibrary() {
    showCount.value.library = Math.min(results.value.library.length, showCount.value.library + PAGE_SIZE)
  }

  function loadMoreAll() {
    showCount.value.chat = Math.min(results.value.chat.length, showCount.value.chat + PAGE_SIZE)
    showCount.value.dirs = Math.min(results.value.dirs.length, showCount.value.dirs + PAGE_SIZE)
    showCount.value.files = Math.min(mergedFiles.value.length, showCount.value.files + PAGE_SIZE)
    showCount.value.library = Math.min(results.value.library.length, showCount.value.library + PAGE_SIZE)
  }

  function applyEnabledCategories(next) {
    const sanitized = sanitizeEnabledCategories(next)
    if (sameEnabledCategories(sanitized, enabledCategories.value)) return

    enabledCategories.value = sanitized
    saveEnabledCategories(sanitized)

    if (!isVisible()) return

    if (!normalizeQueryClient(query.value) || !hasEnabledCategory.value) {
      cancelPendingAndReset()
      return
    }

    handleSearch(true)
  }

  function applySelectAll() {
    applyEnabledCategories({
      chat: true,
      dirs: true,
      files: true,
      library: true
    })
  }

  function applyWorkspacePreset() {
    applyEnabledCategories({
      chat: false,
      dirs: true,
      files: true,
      library: false
    })
  }

  function resetCategoryDefaults() {
    applyEnabledCategories(defaultEnabledCategories())
  }

  async function executeSearch(requestId, rawQuery) {
    const rawTrimmed = String(rawQuery || '').trim()
    const norm = normalizeQueryClient(rawTrimmed)

    if (!norm || !hasEnabledCategory.value || backendModules.value.length === 0) {
      if (requestId === activeSearchId) {
        searching.value = false
        resetResults()
      }
      return
    }

    const modulesSnapshot = [...backendModules.value]
    const cacheSensitive = isCacheSensitiveSearchQuery(rawTrimmed)
    const cacheKey = buildSearchCacheKey(rawTrimmed, norm, modulesSnapshot)

    if (!cacheSensitive) {
      const cached = searchCache.get(cacheKey)
      if (cached) {
        if (requestId === activeSearchId) {
          results.value = cached.results
          totalResults.value = cached.total
          normalizedQueryText.value = cached.normalized_query || ''
          countsState.value = cached.counts || emptyCounts()
          debugMeta.value = cached.debugMeta || emptyDebugMeta()
          searching.value = false
        }
        return
      }
    }

    try {
      const result = await callTool('nisb_search_cross_module', {
        query: rawTrimmed,
        modules: modulesSnapshot,
        limit: FETCH_LIMIT,
        per_module_limit: FETCH_LIMIT,
        fuzzy: true
      })

      if (requestId !== activeSearchId) return

      const info = normalizeToolResponse(result, t('sidebar.search.messages.completed'))
      if (!info.success) {
        resetResults()
        return
      }

      const payload = normalizePayloadFromInfo(info, t)
      const nextDebugMeta = extractDebugMeta(info, payload, showDebugPanel.value, currentMode)

      results.value = payload.results
      totalResults.value = payload.total
      normalizedQueryText.value = payload.normalized_query || ''
      countsState.value = payload.counts || emptyCounts()
      debugMeta.value = nextDebugMeta

      if (!cacheSensitive) {
        cacheSet(cacheKey, {
          ...payload,
          debugMeta: nextDebugMeta
        })
      }
    } catch (e) {
      if (requestId !== activeSearchId) return
      console.error('[search] failed:', e)
      resetResults()
    } finally {
      if (requestId === activeSearchId) {
        searching.value = false
      }
    }
  }

  function handleSearch(immediate = false) {
    if (searchTimer) clearTimeout(searchTimer)

    const raw = String(query.value || '')
    const norm = normalizeQueryClient(raw)

    if (!norm || !hasEnabledCategory.value || backendModules.value.length === 0) {
      cancelPendingAndReset()
      return
    }

    resetPaging()
    const delay = immediate ? 0 : SEARCH_DEBOUNCE_MS
    const requestId = ++activeSearchId

    searchTimer = setTimeout(async () => {
      if (requestId !== activeSearchId) return
      searching.value = true
      await executeSearch(requestId, raw)
    }, delay)
  }

  function triggerSearchNow() {
    if (!normalizeQueryClient(query.value)) return
    if (!hasEnabledCategory.value) return
    if (searchTimer) clearTimeout(searchTimer)
    handleSearch(true)
  }

  return {
    PAGE_SIZE,
    query,
    searching,
    normalizedQueryText,
    results,
    totalResults,
    debugOpen,
    debugMeta,
    enabledCategories,
    showCount,
    countsState,
    hasEnabledCategory,
    debugPanelAvailable,
    showDebugPanel,
    backendModules,
    mergedFiles,
    displayCounts,
    visibleChat,
    visibleDirs,
    visibleFiles,
    visibleLibrary,
    hasMoreChat,
    hasMoreDirs,
    hasMoreFiles,
    hasMoreLibrary,
    hasMoreAny,
    toggleDebugPanel,
    applyEnabledCategories,
    applySelectAll,
    applyWorkspacePreset,
    resetCategoryDefaults,
    triggerSearchNow,
    handleSearch,
    loadMoreChat,
    loadMoreDirs,
    loadMoreFiles,
    loadMoreLibrary,
    loadMoreAll,
    cancelPendingOnly,
    cancelPendingAndReset,
    clearSearchCache
  }
}

export default useSearchPanelSearch
