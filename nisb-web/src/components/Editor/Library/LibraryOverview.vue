<template>
  <div class="overview">
    <header class="overview-topbar">
      <div class="topbar-title-block">
        <div class="title">{{ t('library.center.overview.title') }}</div>
        <div class="sub">{{ t('library.center.overview.subtitle') }}</div>
      </div>

      <div class="topbar-meta">
        <span class="meta-chip mono">{{ libraryOptions.length }}</span>
        <span class="meta-chip mono">{{ viewItems.length }}</span>
        <span class="meta-chip mono">{{ rawItems.length }}</span>
        <span v-if="evidenceItems.length" class="meta-chip active mono">{{ evidenceItems.length }}</span>
      </div>

      <button class="topbar-btn" type="button" :disabled="loading" @click="refresh">
        {{ loading ? t('library.center.bookmarksPanel.loading') : t('library.center.bookmarksPanel.refresh') }}
      </button>
    </header>

    <main class="overview-body">
      <section class="search-stage">
        <KnowledgeHubSearchPanel
          :library-options="libraryOptions"
          :doc-meta="docMeta"
          :current-library-id="props.libraryId || ''"
          @results="onSearchResults"
        />
      </section>

      <section class="results-stage">
        <LibraryBookmarksPanel
          v-model:type-filter="typeFilter"
          v-model:time-range="timeRange"
          v-model:query="filterQuery"
          v-model:library-filter="libraryFilter"
          :library-options="libraryOptions"
          :items="viewItems"
          :loading="loading"
          :can-load-more="canLoadMore"
          @refresh="refresh"
          @load-more="loadMore"
          @jump="jumpTo"
          @open-tools="openTools"
          @copy-item="copyItem"
          @delete-item="deleteItem"
          @convert-to-bookmark="convertToBookmark"
          @convert-to-annotation="convertToAnnotation"
        />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'
import KnowledgeHubSearchPanel from './KnowledgeHubSearchPanel.vue'
import LibraryBookmarksPanel from './LibraryBookmarksPanel.vue'

const props = defineProps({
  libraryId: { type: String, default: null }
})

const { callTool } = useMCP()
const { t, locale } = useI18n()

const loading = ref(false)
const typeFilter = ref('all')
const timeRange = ref('all')
const filterQuery = ref('')
const libraryFilter = ref('')
const limit = ref(50)

const rawItems = ref([])
const evidenceItems = ref([])
const libraryCatalog = ref([])

const DOC_META_KEY = 'nisb-doc-meta-cache:v1'
const FILTER_KEY = 'nisb-library-overview-filter:v2'
const docMeta = ref({})

function safeText(v) {
  const s = String(v == null ? '' : v)
  return s.replace(/\s+/g, ' ').trim()
}

function fmtLocal(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(locale.value || undefined)
  } catch {
    return String(iso)
  }
}

function loadDocMeta() {
  try {
    const raw = localStorage.getItem(DOC_META_KEY)
    if (!raw) return {}
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : {}
  } catch {
    return {}
  }
}

function saveDocMeta(obj) {
  try {
    localStorage.setItem(DOC_META_KEY, JSON.stringify(obj))
  } catch {}
}

function loadFilters() {
  try {
    const raw = localStorage.getItem(FILTER_KEY)
    if (!raw) return null
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : null
  } catch {
    return null
  }
}

function saveFilters() {
  try {
    localStorage.setItem(
      FILTER_KEY,
      JSON.stringify({
        typeFilter: typeFilter.value,
        timeRange: timeRange.value,
        filterQuery: filterQuery.value,
        libraryFilter: libraryFilter.value
      })
    )
  } catch {}
}

function kindLabel(kind) {
  if (kind === 'bookmark') return t('library.center.overview.kind.bookmark')
  if (kind === 'annotation') return t('library.center.overview.kind.annotation')
  if (kind === 'evidence') return t('library.center.overview.kind.evidence')
  return String(kind || '')
}

function onDocMeta(evt) {
  const d = evt?.detail || null
  const libId = String(d?.libraryId || '').trim()
  const docId = String(d?.docId || '').trim()
  const filename = String(d?.filename || '').trim()
  if (!libId || !docId) return

  const next = { ...(docMeta.value || {}) }
  const libMap = { ...(next[libId] || {}) }
  libMap[docId] = {
    filename: filename || libMap[docId]?.filename || '',
    filetype: String(d?.filetype || libMap[docId]?.filetype || '').trim(),
    chunks: Number(d?.chunks ?? libMap[docId]?.chunks ?? 0) || 0,
    updatedAt: new Date().toISOString()
  }
  next[libId] = libMap
  docMeta.value = next
  saveDocMeta(next)
}

function resolveDocTitle(libraryId, docId) {
  const libMap = docMeta.value?.[libraryId] || null
  const meta = libMap?.[docId] || null
  const fn = String(meta?.filename || '').trim()
  return fn || ''
}

function normalizeBookmark(b) {
  const libraryId = String(b?.library_id || b?.libraryid || '').trim()
  const docId = String(b?.doc_id || b?.docid || '').trim()
  const spanIndex = Number(b?.span_index ?? b?.spanindex ?? 0) || 0
  const createdAt = String(b?.created_at || b?.createdat || '').trim()
  const bookmarkId = String(b?.bookmark_id || b?.bookmarkid || '').trim()

  const title = safeText(b?.title || '')
  const note = safeText(b?.note || '')
  const preview = note || title || t('library.center.overview.emptyContent')

  return {
    key: `bm:${bookmarkId || `${libraryId}:${docId}:${spanIndex}:${createdAt}`}`,
    kind: 'bookmark',
    rawId: bookmarkId,
    libraryId,
    docId,
    docTitle: resolveDocTitle(libraryId, docId),
    spanIndex,
    createdAt,
    createdAtLocal: fmtLocal(createdAt),
    preview: preview.length > 240 ? preview.slice(0, 240) + '…' : preview,
    reader: b?.reader ?? null,
    canDelete: !!bookmarkId
  }
}

function normalizeAnnotation(a) {
  const libraryId = String(a?.library_id || a?.libraryid || '').trim()
  const docId = String(a?.doc_id || a?.docid || '').trim()
  const spanIndex = Number(a?.span_index ?? a?.spanindex ?? 0) || 0
  const createdAt = String(a?.created_at || a?.createdat || '').trim()
  const annotationId = String(a?.annotation_id || a?.annotationid || '').trim()

  const content = safeText(a?.content || '')
  const preview = content || t('library.center.overview.emptyContent')

  return {
    key: `ann:${annotationId || `${libraryId}:${docId}:${spanIndex}:${createdAt}`}`,
    kind: 'annotation',
    rawId: annotationId,
    libraryId,
    docId,
    docTitle: resolveDocTitle(libraryId, docId),
    spanIndex,
    createdAt,
    createdAtLocal: fmtLocal(createdAt),
    preview: preview.length > 240 ? preview.slice(0, 240) + '…' : preview,
    reader: a?.reader ?? null,
    canDelete: !!annotationId
  }
}

function sortByTimeDesc(items) {
  return [...items].sort((x, y) => {
    const tx = Date.parse(x.createdAt || '') || 0
    const ty = Date.parse(y.createdAt || '') || 0
    return ty - tx
  })
}

function pickArray(res, keys) {
  if (!res || typeof res !== 'object') return []
  for (const key of keys) {
    if (Array.isArray(res[key])) return res[key]
  }
  const data = res.data
  if (data && typeof data === 'object') {
    for (const key of keys) {
      if (Array.isArray(data[key])) return data[key]
    }
  }
  return []
}

function normalizeLibraryId(lib) {
  return String(lib?.library_id || lib?.libraryId || lib?.id || '').trim()
}

async function loadLibraries() {
  try {
    const res = await callTool('nisb_library_list', {})
    const arr = pickArray(res, ['libraries', 'items', 'data'])
    libraryCatalog.value = arr.map(normalizeLibraryId).filter(Boolean)
  } catch {
    libraryCatalog.value = []
  }
}

const libraryOptions = computed(() => {
  const set = new Set()

  for (const id of libraryCatalog.value || []) {
    const s = String(id || '').trim()
    if (s) set.add(s)
  }

  for (const it of rawItems.value || []) {
    const s = String(it?.libraryId || '').trim()
    if (s) set.add(s)
  }

  for (const it of evidenceItems.value || []) {
    const s = String(it?.libraryId || '').trim()
    if (s) set.add(s)
  }

  return Array.from(set).sort()
})

function matchesText(it, qLower) {
  if (!qLower) return true
  const hay = `${it.kind} ${it.libraryId} ${it.docId} ${it.docTitle || ''} ${it.spanIndex} ${it.preview}`.toLowerCase()
  return hay.includes(qLower)
}

const viewItems = computed(() => {
  const q = safeText(filterQuery.value).toLowerCase()
  const lib = String(libraryFilter.value || '').trim()
  const tFilter = String(typeFilter.value || 'all')

  const all = [...(evidenceItems.value || []), ...(rawItems.value || [])]

  let filtered = all
  if (tFilter === 'bookmark') filtered = filtered.filter((it) => it.kind === 'bookmark')
  if (tFilter === 'annotation') filtered = filtered.filter((it) => it.kind === 'annotation')

  if (lib) filtered = filtered.filter((it) => String(it.libraryId) === lib)
  if (q) filtered = filtered.filter((it) => matchesText(it, q))

  return filtered
})

const canLoadMore = computed(() => {
  return viewItems.value.length >= Math.floor(limit.value * 0.9)
})

function onSearchResults(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : []
  const patched = items.map((it) => ({
    ...it,
    docTitle: it.docTitle || resolveDocTitle(it.libraryId, it.docId)
  }))
  evidenceItems.value = patched
}

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const args = {
      library_id: null,
      time_range: timeRange.value || 'all',
      limit: Number(limit.value) || 50
    }

    const [libRes, bmRes, annRes] = await Promise.allSettled([
      callTool('nisb_library_list', {}),
      callTool('nisb_bookmark_list_all', args),
      callTool('nisb_annotation_list_all', args)
    ])

    if (libRes.status === 'fulfilled') {
      const arr = pickArray(libRes.value, ['libraries', 'items', 'data'])
      libraryCatalog.value = arr.map(normalizeLibraryId).filter(Boolean)
    }

    const bmValue = bmRes.status === 'fulfilled' ? bmRes.value : null
    const annValue = annRes.status === 'fulfilled' ? annRes.value : null

    const bookmarks = bmValue?.status === 'success' && Array.isArray(bmValue.bookmarks) ? bmValue.bookmarks : []
    const annotations = annValue?.status === 'success' && Array.isArray(annValue.annotations) ? annValue.annotations : []

    const merged = [...bookmarks.map(normalizeBookmark), ...annotations.map(normalizeAnnotation)]
    rawItems.value = sortByTimeDesc(merged)
  } catch (e) {
    rawItems.value = []
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: e?.message || t('library.center.overview.loadFailed'), type: 'error' }
      })
    )
  } finally {
    loading.value = false
  }
}

function loadMore() {
  limit.value = Number(limit.value || 0) + 50
  refresh()
}

function dispatchOpenLibraryDoc(it) {
  if (!it || !it.libraryId || !it.docId) return
  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: it.libraryId,
        docId: it.docId,
        spanIndex: it.spanIndex,
        reader: it.reader || window.nisbReaderState || null
      }
    })
  )
}

function jumpTo(it) {
  dispatchOpenLibraryDoc(it)
}

function openTools(it) {
  if (!it || !it.libraryId || !it.docId) return
  dispatchOpenLibraryDoc(it)

  const payload = {
    libraryId: it.libraryId,
    docId: it.docId,
    spanIndex: it.spanIndex,
    reader: it.reader || window.nisbReaderState || null
  }
  const fire = () => window.dispatchEvent(new CustomEvent('nisb-span-artifacts-open', { detail: payload }))
  setTimeout(fire, 120)
  setTimeout(fire, 420)
  setTimeout(fire, 820)
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      return true
    } catch {
      return false
    }
  }
}

async function copyItem(it) {
  if (!it) return
  const payload = JSON.stringify({ libraryId: it.libraryId, docId: it.docId, spanIndex: it.spanIndex }, null, 0)
  const ok = await copyToClipboard(payload)
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: {
        message: ok ? t('library.center.overview.copyLocatorSuccess') : t('library.center.overview.copyFailed'),
        type: ok ? 'success' : 'error'
      }
    })
  )
}

async function deleteItem(it) {
  if (!it || !it.canDelete) return

  const ok = window.confirm(
    t('library.center.overview.deleteConfirm', {
      kind: kindLabel(it.kind),
      libraryId: it.libraryId,
      docId: it.docId,
      spanIndex: it.spanIndex,
      spanLabel: t('library.center.overview.span')
    })
  )
  if (!ok) return

  try {
    if (it.kind === 'bookmark') {
      const res = await callTool('nisb_bookmark_delete', { bookmark_id: it.rawId, bookmarkId: it.rawId })
      if (res?.status !== 'success') return alert(res?.message || t('library.center.overview.deleteFailed'))
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated'))
    } else if (it.kind === 'annotation') {
      const res = await callTool('nisb_span_annotation_delete', { annotation_id: it.rawId, annotationId: it.rawId })
      if (res?.status !== 'success') return alert(res?.message || t('library.center.overview.deleteFailed'))
      window.dispatchEvent(new CustomEvent('nisb-span-annotation-updated'))
    }

    window.dispatchEvent(new CustomEvent('nisb-library-updated'))
    await refresh()
  } catch (e) {
    alert(e?.message || String(e))
  }
}

function buildAutoTitle(it) {
  const base = it.docTitle || it.docId
  return t('library.center.overview.autoTitle', {
    base,
    spanIndex: it.spanIndex,
    spanLabel: t('library.center.overview.span')
  })
}

async function convertToBookmark(it) {
  if (!it || it.kind !== 'evidence') return

  const ok = window.confirm(
    t('library.center.overview.convertToBookmarkConfirm', {
      libraryId: it.libraryId,
      docId: it.docId,
      spanIndex: it.spanIndex,
      spanLabel: t('library.center.overview.span')
    })
  )
  if (!ok) return

  try {
    const res = await callTool('nisb_bookmark_add', {
      library_id: it.libraryId,
      libraryId: it.libraryId,
      doc_id: it.docId,
      docId: it.docId,
      span_index: it.spanIndex,
      spanIndex: it.spanIndex,
      title: buildAutoTitle(it),
      note: safeText(it.preview || '')
    })

    if (res?.status !== 'success') return alert(res?.message || t('library.center.overview.convertToBookmarkFailed'))

    window.dispatchEvent(new CustomEvent('nisb-bookmark-updated'))
    window.dispatchEvent(new CustomEvent('nisb-library-updated'))
    await refresh()
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('library.center.overview.convertToBookmarkSuccess'), type: 'success' }
      })
    )
  } catch (e) {
    alert(e?.message || String(e))
  }
}

async function convertToAnnotation(it) {
  if (!it || it.kind !== 'evidence') return

  const ok = window.confirm(
    t('library.center.overview.convertToAnnotationConfirm', {
      libraryId: it.libraryId,
      docId: it.docId,
      spanIndex: it.spanIndex,
      spanLabel: t('library.center.overview.span')
    })
  )
  if (!ok) return

  try {
    const res = await callTool('nisb_span_annotation_add', {
      library_id: it.libraryId,
      libraryId: it.libraryId,
      doc_id: it.docId,
      docId: it.docId,
      span_index: it.spanIndex,
      spanIndex: it.spanIndex,
      content: safeText(it.preview || ''),
      reader: window.nisbReaderState || null
    })

    if (res?.status !== 'success') return alert(res?.message || t('library.center.overview.convertToAnnotationFailed'))

    window.dispatchEvent(new CustomEvent('nisb-span-annotation-updated'))
    window.dispatchEvent(new CustomEvent('nisb-library-updated'))
    await refresh()
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('library.center.overview.convertToAnnotationSuccess'), type: 'success' }
      })
    )
  } catch (e) {
    alert(e?.message || String(e))
  }
}

watch([typeFilter, timeRange, filterQuery, libraryFilter], () => {
  saveFilters()
})

watch(timeRange, () => {
  limit.value = 50
  refresh()
})

watch(
  () => props.libraryId,
  () => {
    if (!libraryCatalog.value.length) loadLibraries()
  },
  { immediate: true }
)

onMounted(() => {
  docMeta.value = loadDocMeta()

  const f = loadFilters()
  if (f) {
    if (f.typeFilter) typeFilter.value = f.typeFilter
    if (f.timeRange) timeRange.value = f.timeRange
    if (typeof f.filterQuery === 'string') filterQuery.value = f.filterQuery
    if (typeof f.libraryFilter === 'string') libraryFilter.value = f.libraryFilter
  }

  window.addEventListener('nisb-library-doc-meta', onDocMeta)
  loadLibraries()
  refresh()
})

onUnmounted(() => {
  window.removeEventListener('nisb-library-doc-meta', onDocMeta)
})
</script>

<style scoped>
.overview {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 16% 12%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    radial-gradient(circle at 92% 4%, rgba(22, 163, 74, 0.055), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
}

.overview-topbar {
  --nisb-library-bar-height: 50px;

  position: relative;
  z-index: 3;
  flex: 0 0 auto;
  min-width: 0;
  height: var(--nisb-library-bar-height);
  min-height: var(--nisb-library-bar-height);
  max-height: var(--nisb-library-bar-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.64rem;
  padding: 0.44rem 0.78rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 26px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.overview-topbar::-webkit-scrollbar {
  display: none;
}

.overview-topbar::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 22%, var(--line)),
      transparent
    );
  opacity: 0.72;
}

.topbar-title-block {
  flex: 1 1 auto;
  min-width: 180px;
  display: grid;
  gap: 0.1rem;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1.18;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.24;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-meta {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.36rem;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  box-sizing: border-box;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 34%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  max-width: 100%;
}

.meta-chip.active {
  border-color: color-mix(in srgb, #16a34a 38%, var(--line));
  background: rgba(22, 163, 74, 0.13);
  color: #16a34a;
}

.topbar-btn {
  flex: 0 0 auto;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 0.7rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.topbar-btn:hover:not(:disabled),
.topbar-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 11%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.topbar-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.topbar-btn:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.overview-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, 0.76fr) minmax(0, 1.24fr);
  gap: 0.72rem;
  padding: 0.72rem;
  overflow: hidden;
}

.search-stage,
.results-stage {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.search-stage {
  display: flex;
}

.results-stage {
  display: flex;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 980px) {
  .overview-body {
    grid-template-columns: minmax(280px, 0.82fr) minmax(0, 1.18fr);
    gap: 0.62rem;
    padding: 0.62rem;
  }
}

@media (max-width: 760px) {
  .overview {
    overflow: hidden;
  }

  .overview-topbar {
    --nisb-library-bar-height: 52px;

    height: var(--nisb-library-bar-height);
    min-height: var(--nisb-library-bar-height);
    max-height: var(--nisb-library-bar-height);
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.42rem;
    padding: 0.38rem 0.56rem;
    overflow: hidden;
  }

  .topbar-title-block {
    min-width: 0;
    display: grid;
    gap: 0.04rem;
  }

  .title {
    font-size: 0.88rem;
    line-height: 1.12;
  }

  .sub {
    max-width: 100%;
    font-size: 0.66rem;
    line-height: 1.12;
  }

  .topbar-meta {
    min-width: 0;
    max-width: 34vw;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.22rem;
    overflow: hidden;
  }

  .meta-chip {
    min-height: 22px;
    min-width: 0;
    padding: 0 0.44rem;
    font-size: 0.66rem;
  }

  .topbar-btn {
    min-height: 30px;
    padding: 0 0.58rem;
    border-radius: 11px;
    font-size: 0.72rem;
  }

  .overview-body {
    display: block;
    min-height: 0;
    padding: 0.58rem;
    overflow-y: auto;
    overflow-x: hidden;
    overscroll-behavior: contain;
    scrollbar-width: thin;
  }

  .overview-body::-webkit-scrollbar {
    width: 8px;
  }

  .overview-body::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: color-mix(in srgb, var(--line) 72%, transparent);
  }

  .search-stage,
  .results-stage {
    display: block;
    min-width: 0;
    min-height: 0;
    overflow: visible;
  }

  .search-stage {
    margin-bottom: 0.62rem;
  }

  .results-stage {
    min-height: 0;
    padding-bottom: 0.72rem;
  }

  .results-stage :deep(.panel) {
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .results-stage :deep(.content),
  .results-stage :deep(.list) {
    min-height: 0;
    overflow: visible;
  }
}

@media (max-width: 520px) {
  .overview-topbar {
    --nisb-library-bar-height: 50px;

    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 0.3rem;
    padding: 0.34rem 0.42rem;
  }

  .title {
    font-size: 0.82rem;
  }

  .sub {
    font-size: 0.61rem;
  }

  .topbar-meta {
    max-width: 30vw;
    gap: 0.16rem;
  }

  .meta-chip {
    min-height: 20px;
    padding: 0 0.34rem;
    font-size: 0.62rem;
  }

  .meta-chip.active {
    display: none;
  }

  .topbar-btn {
    min-height: 28px;
    padding: 0 0.48rem;
    border-radius: 10px;
    font-size: 0.68rem;
  }

  .overview-body {
    padding: 0.5rem;
  }
}
</style>
