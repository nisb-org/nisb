<!-- src/components/Editor/Chat/CitationList.vue -->
<template>
  <section v-if="items.length > 0" class="citations">
    <header class="citation_head">
      <div class="citation_title_stack">
        <div class="label">{{ t('chat.citations.title') }}</div>
        <div class="citation_subtitle">
          {{ t('chat.citations.sourceCount', { count: items.length }) }}
        </div>
      </div>

      <button type="button" class="toggle" @click="expanded = !expanded">
        {{ expanded ? t('chat.citations.collapseDetails') : t('chat.citations.expandDetails') }}
      </button>
    </header>

    <div class="chips" :aria-label="t('chat.citations.chipsAria')">
      <button
        v-for="(citation, idx) in items"
        :key="citation.key"
        type="button"
        class="chip"
        :class="[
          `chip_${citation.kind}`,
          citation.unavailable ? 'is_unavailable' : '',
        ]"
        :disabled="isDisabled(citation)"
        :title="tooltipOf(citation)"
        @click="handleClick(citation)"
      >
        <span class="chip_index">#{{ idx + 1 }}</span>
        <span class="chip_main">
          <span class="chip_label">{{ chipLabelOf(citation) }}</span>
          <span class="chip_meta">{{ chipMetaOf(citation) }}</span>
        </span>
      </button>
    </div>

    <div v-if="expanded" class="detail">
      <article
        v-for="(citation, idx) in items"
        :key="`${citation.key}_detail`"
        class="source_card"
        :class="[
          `source_card_${citation.kind}`,
          citation.unavailable ? 'is_unavailable' : '',
        ]"
      >
        <div class="source_top">
          <div class="source_badges">
            <span class="source_badge">
              {{ citation.kind === 'web' ? t('chat.citations.kind.web') : t('chat.citations.kind.local') }}
            </span>
            <span class="source_badge muted">#{{ idx + 1 }}</span>
            <span v-if="citation.unavailable" class="source_badge warn">
              {{ t('chat.citations.unavailable') }}
            </span>
          </div>

          <button
            type="button"
            class="open_btn"
            :disabled="isDisabled(citation)"
            @click="handleClick(citation)"
          >
            {{ citation.kind === 'web' ? t('chat.citations.openWeb') : t('chat.citations.openSource') }}
          </button>
        </div>

        <div v-if="citation.kind === 'web'" class="source_main">
          <div class="source_title" :title="citation.title || citation.url">
            {{ citation.title || citation.url || t('chat.citations.webFallbackHost') }}
          </div>

          <a
            v-if="citation.url"
            class="source_link mono"
            :href="citation.url"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ citation.url }}
          </a>
        </div>

        <div v-else class="source_main">
          <div class="source_title" :title="citation.docLabel">
            {{ citation.docLabel }}
          </div>

          <div class="summary_grid">
            <div v-if="citation.libraryId" class="summary_item">
              <span>{{ t('chat.citations.fields.library') }}</span>
              <strong class="mono">{{ citation.libraryId }}</strong>
            </div>

            <div class="summary_item">
              <span>{{ t('chat.citations.fields.document') }}</span>
              <strong class="mono">{{ citation.docId || t('chat.citations.defaultDocumentId') }}</strong>
            </div>

            <div class="summary_item">
              <span>{{ t('chat.citations.fields.span') }}</span>
              <strong class="mono">{{ citation.spanIndex ?? '?' }}</strong>
            </div>

            <div v-if="citation.chunkId" class="summary_item">
              <span>{{ t('chat.citations.fields.chunk') }}</span>
              <strong class="mono">{{ citation.chunkId }}</strong>
            </div>

            <div v-if="citation.pageLabel" class="summary_item">
              <span>{{ t('chat.citations.fields.page') }}</span>
              <strong class="mono">{{ citation.pageLabel }}</strong>
            </div>

            <div v-if="citation.sectionLabel" class="summary_item">
              <span>{{ t('chat.citations.fields.section') }}</span>
              <strong>{{ citation.sectionLabel }}</strong>
            </div>

            <div v-if="citation.rankLabel" class="summary_item">
              <span>{{ t('chat.citations.fields.rank') }}</span>
              <strong class="mono">{{ citation.rankLabel }}</strong>
            </div>

            <div v-if="citation.relevanceLabel" class="summary_item">
              <span>{{ t('chat.citations.fields.relevance') }}</span>
              <strong class="mono">{{ citation.relevanceLabel }}</strong>
            </div>
          </div>
        </div>

        <blockquote v-if="citation.quote" class="quote">
          {{ citation.quote }}
        </blockquote>

        <p v-if="citation.note" class="note">
          {{ citation.note }}
        </p>

        <details class="raw_details">
          <summary>{{ t('chat.citations.rawMetadata') }}</summary>
          <pre class="raw_pre">{{ formatJson(citation.raw) }}</pre>
        </details>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLibrarySearchStore } from '../../../stores/librarySearch'
import {
  readLocalEvidenceSettings,
  onSettingsUpdated,
  NISB_LOCAL_EVIDENCE_SYNC_KEY,
  NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY
} from '../../../composables/useNisbSettings'

const { t } = useI18n()
const librarySearch = useLibrarySearchStore()

const props = defineProps({
  citations: { type: Array, default: () => [] }
})

const expanded = ref(false)

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

function pickUrl(citation) {
  const url =
    citation?.url ||
    citation?.href ||
    citation?.link ||
    citation?.source_url ||
    citation?.sourceUrl ||
    ''

  return safeString(url).trim()
}

function hostOf(url) {
  try {
    const parsed = new URL(url)
    return parsed.host
  } catch {
    return ''
  }
}

function getGlobalReader() {
  try {
    return window.__nisbReaderState || window.nisbReaderState || null
  } catch {
    return null
  }
}

function docLabelOf(citation) {
  const title = safeString(
    citation?.doc_title ||
    citation?.docTitle ||
    citation?.title ||
    citation?.name ||
    citation?.filename ||
    citation?.source_title ||
    citation?.sourceTitle
  ).trim()

  if (title) return title
  return safeString(citation?.doc_id).trim() || t('chat.citations.defaultDocumentId')
}

function firstNonEmpty(...values) {
  for (const value of values) {
    const text = safeString(value).trim()
    if (text) return text
  }
  return ''
}

function numberOrNull(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function compactNumber(value) {
  const num = numberOrNull(value)
  if (num === null) return ''
  if (num >= 0 && num <= 1) return num.toFixed(2)
  return String(num)
}

function formatJson(value) {
  try {
    return JSON.stringify(value ?? null, null, 2)
  } catch {
    return safeString(value)
  }
}

const items = computed(() => {
  const list = Array.isArray(props.citations) ? props.citations.filter(Boolean) : []

  return list.map((citation, index) => {
    const url = pickUrl(citation)
    const kind = url ? 'web' : 'local'

    const libraryId = safeString(citation?.library_id || citation?.libraryId).trim()
    const docId = safeString(citation?.doc_id || citation?.docId).trim()

    const spanRaw =
      citation?.span_index ??
      citation?.spanIndex ??
      citation?.span ??
      citation?.span_id

    const spanIndex = numberOrNull(spanRaw)

    const chunkId = firstNonEmpty(
      citation?.chunk_id,
      citation?.chunkId,
      citation?.chunk
    )

    const pageLabel = firstNonEmpty(
      citation?.page,
      citation?.page_number,
      citation?.pageNumber
    )

    const sectionLabel = firstNonEmpty(
      citation?.section,
      citation?.section_title,
      citation?.sectionTitle,
      citation?.heading
    )

    const rankLabel = firstNonEmpty(
      citation?.rank,
      citation?.rerank_rank,
      citation?.search_rank
    )

    const relevanceLabel = compactNumber(
      citation?.relevance ??
      citation?.score ??
      citation?.similarity ??
      citation?.rank_score
    )

    const quote = firstNonEmpty(
      citation?.quote,
      citation?.excerpt,
      citation?.text,
      citation?.snippet
    )

    const note = firstNonEmpty(citation?.note, citation?.summary)

    const title = firstNonEmpty(
      citation?.title,
      citation?.name,
      citation?.source_title,
      citation?.sourceTitle
    )

    const host = url ? hostOf(url) : ''

    return {
      key: firstNonEmpty(
        citation?.id,
        citation?.citation_id,
        citation?.citationId,
        `${kind}_${index}_${url || docId || title || 'citation'}`
      ),
      kind,
      libraryId,
      docId,
      spanIndex,
      chunkId,
      pageLabel,
      sectionLabel,
      rankLabel,
      relevanceLabel,
      docLabel: docLabelOf(citation),
      quote,
      note,
      url,
      host,
      title,
      unavailable:
        kind === 'web'
          ? !url
          : !libraryId || !docId,
      raw: citation
    }
  })
})

function chipLabelOf(citation) {
  if (!citation) return ''
  if (citation.kind === 'web') {
    return citation.host || citation.title || t('chat.citations.webFallbackHost')
  }
  return citation.docLabel || t('chat.citations.defaultDocumentId')
}

function chipMetaOf(citation) {
  if (!citation) return ''
  if (citation.kind === 'web') return t('chat.citations.kind.web')

  const parts = []
  if (citation.spanIndex !== null && citation.spanIndex !== undefined) {
    parts.push(t('chat.citations.spanLabel', { spanIndex: citation.spanIndex }))
  }
  if (citation.pageLabel) {
    parts.push(t('chat.citations.pageShort', { page: citation.pageLabel }))
  }
  if (citation.relevanceLabel) {
    parts.push(t('chat.citations.relevanceShort', { relevance: citation.relevanceLabel }))
  }
  return parts.join(' · ') || t('chat.citations.kind.local')
}

function tooltipOf(citation) {
  if (!citation) return ''
  if (citation.kind === 'web') return citation.url || citation.title || ''
  return citation.quote || localMetaOf(citation)
}

function isDisabled(citation) {
  if (!citation) return true
  if (citation.kind === 'web') return !String(citation.url || '').trim()
  return !String(citation.libraryId || '').trim() || !String(citation.docId || '').trim()
}

function localMetaOf(citation) {
  if (!citation || citation.kind !== 'local') return ''

  const parts = []

  if (citation.libraryId) {
    parts.push(t('chat.citations.libraryLabel', { libraryId: citation.libraryId }))
  }

  parts.push(
    t('chat.citations.documentLabel', {
      docId: citation.docId || t('chat.citations.defaultDocumentId')
    })
  )

  parts.push(
    t('chat.citations.spanLabel', {
      spanIndex: citation.spanIndex ?? '?'
    })
  )

  return parts.join(' · ')
}

function highlightDetailOf(citation) {
  const quote = firstNonEmpty(
    citation?.highlightText,
    citation?.highlight_text,
    citation?.highlightQuote,
    citation?.highlight_quote,
    citation?.quote,
    citation?.excerpt,
    citation?.text,
    citation?.snippet
  )

  const note = firstNonEmpty(citation?.note, citation?.summary)
  const mode = quote ? 'quote' : 'span'

  return {
    quote,
    note,
    highlightText: quote,
    highlightQuote: quote,
    highlightMode: mode,
    highlightSource: 'chat_citation',
    highlight_text: quote,
    highlight_quote: quote,
    highlight_mode: mode,
    highlight_source: 'chat_citation'
  }
}

const localSyncEnabled = ref(true)
const localAutoselectEnabled = ref(true)

let offSettingsUpdated = null
let autoOpenTimer = null
let autoOpenRunId = 0

const mountedReady = ref(false)
const lastEmittedLocalSig = ref('')
const lastAutoOpenSig = ref('')

function applyLocalEvidenceSettingsFromStorage() {
  const settings = readLocalEvidenceSettings()
  localSyncEnabled.value = !!settings.sync
  localAutoselectEnabled.value = !!settings.autoselect

  if (!localSyncEnabled.value) {
    localAutoselectEnabled.value = false
  }
}

const localItems = computed(() => {
  return items.value
    .filter((citation) => citation.kind === 'local')
    .filter((citation) => {
      const libraryId = String(citation.libraryId || '').trim()
      const docId = String(citation.docId || '').trim()
      return !!libraryId && !!docId && Number.isFinite(citation.spanIndex)
    })
    .map((citation) => {
      const highlight = highlightDetailOf(citation)

      return {
        library_id: String(citation.libraryId || '').trim(),
        doc_id: String(citation.docId || '').trim(),
        span_index: Number(citation.spanIndex),
        quote: highlight.quote,
        note: highlight.note,
        doc_label: String(citation.docLabel || '').trim(),
        highlight_text: highlight.highlight_text,
        highlight_quote: highlight.highlight_quote,
        highlight_mode: highlight.highlight_mode,
        highlight_source: highlight.highlight_source
      }
    })
})

function localSig(list) {
  return (Array.isArray(list) ? list : [])
    .map((item) => `${item.library_id}|${item.doc_id}|${item.span_index}|${String(item.quote || '').slice(0, 80)}`)
    .join(';;')
}

const localItemsSig = computed(() => localSig(localItems.value))

function emitLocalCitationsEvent(list) {
  window.dispatchEvent(
    new CustomEvent('nisb-chat-local-citations', {
      detail: {
        items: (Array.isArray(list) ? list : []).map((item) => ({
          library_id: item.library_id,
          doc_id: item.doc_id,
          span_index: Number(item.span_index),
          quote: item.quote || '',
          note: item.note || '',
          doc_label: item.doc_label || '',
          highlight_text: item.highlight_text || item.quote || '',
          highlight_quote: item.highlight_quote || item.quote || '',
          highlight_mode: item.highlight_mode || (item.quote ? 'quote' : 'span'),
          highlight_source: item.highlight_source || 'chat_citation'
        }))
      }
    })
  )
}

function isLibraryDockedRightNow() {
  try {
    const dockState = window.__nisbLibraryDockState
    return !!(dockState && dockState.docked === true && dockState.side === 'right')
  } catch {
    return false
  }
}

function shouldAutoOpenFirstLocal() {
  if (!localSyncEnabled.value) return false
  if (!localAutoselectEnabled.value) return false
  return isLibraryDockedRightNow()
}

function scheduleAutoOpenFirstLocal(list, sig, { force = false } = {}) {
  try {
    if (autoOpenTimer) clearTimeout(autoOpenTimer)
  } catch {
  } finally {
    autoOpenTimer = null
  }

  if (!shouldAutoOpenFirstLocal()) return
  if (!Array.isArray(list) || !list.length) return
  if (!force && sig === lastAutoOpenSig.value) return

  const first = list[0]
  const currentRunId = ++autoOpenRunId

  autoOpenTimer = setTimeout(() => {
    if (currentRunId !== autoOpenRunId) return

    const libraryId = String(first.library_id || '').trim()
    const docId = String(first.doc_id || '').trim()
    const spanIndex = Number(first.span_index)

    if (!libraryId || !docId || !Number.isFinite(spanIndex)) return

    try {
      if (typeof librarySearch.setMode === 'function') {
        librarySearch.setMode('evidence')
      } else if ('mode' in librarySearch) {
        librarySearch.mode = 'evidence'
      }
    } catch {
    }

    try {
      if (typeof librarySearch.set_context_from_chat_local_citations === 'function') {
        librarySearch.set_context_from_chat_local_citations({
          libraryId,
          docId,
          preserveResults: true
        })
      } else if (typeof librarySearch.setContext === 'function') {
        librarySearch.setContext({
          libraryId,
          docId,
          preserveResults: true,
          source: 'chat_local_citations'
        })
      }
    } catch {
    }

    const quote = String(first.quote || first.highlight_text || '').trim()
    const note = String(first.note || '').trim()

    const openDetail = {
      libraryId,
      docId,
      spanIndex,
      reader: getGlobalReader(),
      quote,
      note,
      highlightText: quote,
      highlightQuote: quote,
      highlightMode: quote ? 'quote' : 'span',
      highlightSource: 'chat_citation'
    }

    try {
      window.__nisb_last_library_doc_open = openDetail
    } catch {
    }

    window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: openDetail }))
    lastAutoOpenSig.value = sig
  }, 16)
}

function syncCurrentLocalItems({ force = false } = {}) {
  if (!mountedReady.value) return

  const list = localItems.value
  const sig = localItemsSig.value

  if (!localSyncEnabled.value) {
    lastEmittedLocalSig.value = ''
    lastAutoOpenSig.value = ''
    return
  }

  if (force || sig !== lastEmittedLocalSig.value) {
    emitLocalCitationsEvent(list)
    lastEmittedLocalSig.value = sig
  }

  scheduleAutoOpenFirstLocal(list, sig, { force })
}

onMounted(() => {
  mountedReady.value = true
  applyLocalEvidenceSettingsFromStorage()

  offSettingsUpdated = onSettingsUpdated((event) => {
    const detail = event?.detail || {}
    const key = String(detail.key || '')

    if (key !== NISB_LOCAL_EVIDENCE_SYNC_KEY && key !== NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY) {
      return
    }

    const prevSync = !!localSyncEnabled.value
    const prevAutoselect = !!localAutoselectEnabled.value

    applyLocalEvidenceSettingsFromStorage()

    const syncChanged = prevSync !== localSyncEnabled.value
    const autoselectChanged = prevAutoselect !== localAutoselectEnabled.value

    if (!localSyncEnabled.value) {
      lastEmittedLocalSig.value = ''
      lastAutoOpenSig.value = ''
      return
    }

    if (syncChanged || autoselectChanged) {
      syncCurrentLocalItems({ force: true })
    }
  })

  syncCurrentLocalItems({ force: true })
})

onUnmounted(() => {
  try {
    if (typeof offSettingsUpdated === 'function') offSettingsUpdated()
  } catch {
  }

  try {
    if (autoOpenTimer) clearTimeout(autoOpenTimer)
  } catch {
  } finally {
    autoOpenTimer = null
  }
})

watch(
  () => localItemsSig.value,
  () => {
    if (!mountedReady.value) return
    syncCurrentLocalItems()
  }
)

function pushLocalCitationToEvidence(citation) {
  if (!citation || citation.kind !== 'local') return false

  const libraryId = String(citation.libraryId || '').trim()
  const docId = String(citation.docId || '').trim()
  const spanIndex = citation.spanIndex

  if (!libraryId || !docId || !Number.isFinite(spanIndex)) return false

  try {
    if (typeof librarySearch.setMode === 'function') {
      librarySearch.setMode('evidence')
    } else if ('mode' in librarySearch) {
      librarySearch.mode = 'evidence'
    }
  } catch {
  }

  const highlight = highlightDetailOf(citation)

  const payload = {
    library_id: libraryId,
    doc_id: docId,
    span_index: Number(spanIndex),
    chunk_id: citation.chunkId || null,
    relevance: Number(citation.relevanceLabel || 0) || 0,
    quote: highlight.quote,
    text: highlight.quote,
    highlight_text: highlight.highlight_text,
    highlight_quote: highlight.highlight_quote,
    highlight_mode: highlight.highlight_mode,
    highlight_source: highlight.highlight_source
  }

  if (typeof librarySearch.selectItem === 'function') {
    librarySearch.selectItem(payload)
  } else {
    try {
      librarySearch.selected = payload
    } catch {
    }
  }

  return true
}

function handleClick(citation) {
  if (!citation) return

  if (citation.kind === 'web') {
    if (citation.url) window.open(citation.url, '_blank', 'noopener,noreferrer')
    return
  }

  const libraryId = String(citation.libraryId || '').trim()
  const docId = String(citation.docId || '').trim()

  if (!libraryId || !docId) return

  try {
    if (typeof librarySearch.set_context_from_user_click === 'function') {
      librarySearch.set_context_from_user_click({
        libraryId,
        docId,
        preserveResults: true
      })
    } else if (typeof librarySearch.setContext === 'function') {
      librarySearch.setContext({
        libraryId,
        docId,
        preserveResults: true,
        source: 'user_click'
      })
    }
  } catch {
  }

  const hasSpan = Number.isFinite(citation.spanIndex)
  if (hasSpan) pushLocalCitationToEvidence(citation)

  const highlight = highlightDetailOf(citation)

  const openDetail = {
    libraryId,
    docId,
    spanIndex: hasSpan ? Number(citation.spanIndex) : null,
    reader: getGlobalReader(),
    quote: highlight.quote,
    note: highlight.note,
    highlightText: highlight.highlightText,
    highlightQuote: highlight.highlightQuote,
    highlightMode: highlight.highlightMode,
    highlightSource: highlight.highlightSource
  }

  try {
    window.__nisb_last_library_doc_open = openDetail
  } catch {
  }

  window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: openDetail }))

  if (hasSpan) {
    window.dispatchEvent(
      new CustomEvent('nisb-open-doc-span', {
        detail: {
          library_id: libraryId,
          doc_id: docId,
          span_index: Number(citation.spanIndex),
          quote: highlight.quote,
          note: highlight.note,
          highlight_text: highlight.highlight_text,
          highlight_quote: highlight.highlight_quote,
          highlightText: highlight.highlightText,
          highlightQuote: highlight.highlightQuote,
          highlight_mode: highlight.highlight_mode,
          highlightMode: highlight.highlightMode,
          highlight_source: highlight.highlight_source,
          highlightSource: highlight.highlightSource
        }
      })
    )
  }
}
</script>

<style scoped>
.citations {
  min-width: 0;
  margin-top: 0.86rem;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 86%, transparent)
    );
  color: var(--text-main);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.citation_head {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.66rem;
}

.citation_title_stack {
  min-width: 0;
}

.label {
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.citation_subtitle {
  margin-top: 0.16rem;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 680;
  line-height: 1.4;
  overflow-wrap: break-word;
}

.chips {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.42rem;
}

.chip {
  min-width: 0;
  max-width: min(100%, 360px);
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.28rem 0.54rem 0.28rem 0.34rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 60%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.chip:hover:not(:disabled),
.chip:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.chip:active:not(:disabled) {
  transform: translateY(1px);
}

.chip:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.chip_index {
  flex: 0 0 auto;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.42rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 10%, transparent);
  color: var(--selected);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
  font-size: 0.68rem;
  font-weight: 820;
}

.chip_main {
  min-width: 0;
  display: inline-flex;
  align-items: baseline;
  gap: 0.34rem;
}

.chip_label {
  min-width: 0;
  max-width: min(42vw, 220px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip_meta {
  flex: 0 1 auto;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.66rem;
  opacity: 0.88;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail {
  min-width: 0;
  display: grid;
  gap: 0.62rem;
  margin-top: 0.74rem;
}

.source_card {
  min-width: 0;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 46%, transparent)
    );
  overflow: hidden;
}

.source_card.is_unavailable {
  border-color: color-mix(in srgb, #d97706 32%, var(--line));
}

.source_top {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.66rem;
  margin-bottom: 0.62rem;
}

.source_badges {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.source_badge {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.46rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 8%, transparent);
  color: var(--selected);
  font-size: 0.66rem;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.source_badge.muted {
  border-color: color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
}

.source_badge.warn {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
}

.open_btn,
.toggle {
  flex: 0 0 auto;
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.open_btn:hover:not(:disabled),
.open_btn:focus-visible:not(:disabled),
.toggle:hover,
.toggle:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.open_btn:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.open_btn:active:not(:disabled),
.toggle:active {
  transform: translateY(1px);
}

.source_main {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
}

.source_title {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.86rem;
  font-weight: 800;
  line-height: 1.4;
  overflow-wrap: break-word;
}

.source_link {
  min-width: 0;
  color: var(--selected);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
  text-decoration: none;
}

.source_link:hover {
  text-decoration: underline;
  text-underline-offset: 0.16em;
}

.summary_grid {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.42rem;
}

.summary_item {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
  padding: 0.46rem 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 62%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 40%, transparent);
}

.summary_item span {
  color: var(--text-secondary);
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1.25;
}

.summary_item strong {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.74rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.quote {
  margin: 0.62rem 0 0;
  padding: 0.62rem 0.7rem;
  border: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  border-left: 3px solid color-mix(in srgb, var(--selected) 48%, var(--line));
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 44%, transparent);
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.note {
  margin: 0.5rem 0 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.raw_details {
  min-width: 0;
  margin-top: 0.58rem;
  border-top: 1px dashed color-mix(in srgb, var(--line) 70%, transparent);
  padding-top: 0.48rem;
}

.raw_details summary {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.35;
}

.raw_details summary:hover {
  color: var(--selected);
}

.raw_pre {
  max-width: 100%;
  margin: 0.48rem 0 0;
  padding: 0.62rem;
  overflow: auto;
  border: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  color: var(--text-main);
  font-size: 0.72rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 74%, transparent) transparent;
}

.raw_pre::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.raw_pre::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

@media (max-width: 860px) {
  .summary_grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .citations {
    padding: 0.66rem;
    border-radius: 14px;
  }

  .citation_head,
  .source_top {
    align-items: stretch;
    flex-direction: column;
  }

  .toggle,
  .open_btn {
    width: 100%;
  }

  .chip {
    max-width: 100%;
  }

  .chip_main {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.18rem;
  }

  .chip_label,
  .chip_meta {
    max-width: 100%;
    white-space: normal;
    overflow-wrap: break-word;
  }

  .source_card {
    padding: 0.62rem;
    border-radius: 12px;
  }

  .source_badges {
    width: 100%;
  }

  .quote {
    padding: 0.58rem 0.62rem;
  }
}

@media (max-width: 420px) {
  .chips {
    display: grid;
    grid-template-columns: 1fr;
  }

  .chip {
    width: 100%;
  }
}
</style>

