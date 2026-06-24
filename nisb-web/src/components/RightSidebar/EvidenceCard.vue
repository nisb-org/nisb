<!-- /opt/mcp-gateway/nisb-web/src/components/RightSidebar/EvidenceCard.vue -->
<template>
  <div class="evidence-card" v-if="evidenceSelected">
    <div class="evidence-title-row">
      <div class="evidence-title selectable">{{ t('rightSidebar.evidenceCard.title') }}</div>
      <button class="evidence-clear" @click="librarySearch.selectItem(null)" :title="t('rightSidebar.evidenceCard.clear')">
        ✕
      </button>
    </div>

    <div class="evidence-meta">
      <span class="pill">
        {{ displayRelevance }}
      </span>

      <span
        class="muted meta-ellipsis"
        :title="t('rightSidebar.evidenceCard.meta.libraryTitle', { value: evidenceSelected.library_id || '?' })"
      >
        {{ t('rightSidebar.evidenceCard.meta.libraryShort') }} {{ evidenceSelected.library_id || '?' }}
      </span>

      <span
        class="muted meta-ellipsis"
        :title="t('rightSidebar.evidenceCard.meta.docTitle', { value: evidenceSelected.doc_id || '?' })"
      >
        {{ t('rightSidebar.evidenceCard.meta.docShort') }} {{ evidenceSelected.doc_id || '?' }}
      </span>

      <span
        class="muted meta-ellipsis"
        :title="t('rightSidebar.evidenceCard.meta.chunkTitle', { value: chunkDisplay })"
      >
        {{ t('rightSidebar.evidenceCard.meta.chunkShort') }} {{ chunkDisplay }}
      </span>

      <span
        class="muted meta-ellipsis"
        :title="t('rightSidebar.evidenceCard.meta.spanTitle', { value: spanDisplay })"
      >
        {{ t('rightSidebar.evidenceCard.meta.spanShort') }} {{ spanDisplay }}
      </span>
    </div>

    <div class="evidence-body selectable">{{ String(evidenceSelected.text || '') }}</div>

    <div class="evidence-actions">
      <button class="mini-btn" :disabled="!canJump" @click="librarySearch.jumpSelected()">
        {{ t('rightSidebar.evidenceCard.actions.jump') }}
      </button>

      <button class="mini-btn" :disabled="!String(evidenceSelected.text || '').trim()" @click="copyEvidenceText()">
        {{ t('rightSidebar.evidenceCard.actions.copy') }}
      </button>
    </div>

    <div class="evidence-hint muted selectable" v-if="!canJump">
      {{ t('rightSidebar.evidenceCard.hint.cannotJump') }}
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useLibrarySearchStore } from '../../stores/librarySearch'

const { t } = useI18n()
const librarySearch = useLibrarySearchStore()
const { selected, libraryId, docId } = storeToRefs(librarySearch)

function _s(v) {
  return v === null || v === undefined ? '' : String(v)
}

function _numOrNull(v) {
  const n = v === null || v === undefined || v === '' ? null : Number(v)
  return Number.isFinite(n) ? n : null
}

function _normalize_selected(raw) {
  const it = raw && typeof raw === 'object' ? raw : {}

  const lib = _s(it.library_id || it.libraryId || '').trim() || null
  const doc = _s(it.doc_id || it.docId || '').trim() || null

  const span =
    _numOrNull(it.span_index) ??
    _numOrNull(it.spanIndex) ??
    _numOrNull(it.span_id) ??
    _numOrNull(it.spanId) ??
    _numOrNull(it.start_span) ??
    _numOrNull(it.startSpan) ??
    _numOrNull(it.span_start) ??
    _numOrNull(it.spanStart)

  const chunk_num =
    _numOrNull(it.chunk_id) ??
    _numOrNull(it.chunkId)

  const chunk_text = _s(
    it.text ||
    it.quote ||
    it.snippet ||
    it.excerpt ||
    it.content ||
    it.chunk_text ||
    ''
  ).trim()

  const relevanceNum = _numOrNull(it.relevance ?? it.similarity ?? it.score)
  const relevance = relevanceNum === null ? 0 : relevanceNum

  return {
    ...it,
    library_id: lib,
    doc_id: doc,
    span_index: span,
    chunk_id: chunk_num ?? (_s(it.chunk_id || it.chunkId).trim() || null),
    relevance,
    text: chunk_text
  }
}

const evidenceSelected = computed(() => {
  if (!selected.value) return null
  return _normalize_selected(selected.value)
})

const spanValue = computed(() => {
  const it = evidenceSelected.value
  if (!it) return null
  return _numOrNull(it.span_index)
})

const spanDisplay = computed(() => {
  const v = spanValue.value
  return v === null || v === undefined ? '?' : v
})

const chunkDisplay = computed(() => {
  const it = evidenceSelected.value
  if (!it) return '?'
  const raw = it.chunk_id
  if (raw === null || raw === undefined || raw === '') return '?'
  return String(raw)
})

const displayRelevance = computed(() => {
  const it = evidenceSelected.value
  const n = Number(it?.relevance || 0)
  const pct = Number.isFinite(n)
    ? (n <= 1 ? n * 100 : n)
    : 0
  return `${pct.toFixed(1)}%`
})

const canJump = computed(() => {
  const it = evidenceSelected.value
  if (!it) return false

  const lib = it.library_id || _s(libraryId.value).trim()
  const doc = it.doc_id || _s(docId.value).trim()
  return !!lib && !!doc && Number.isFinite(spanValue.value)
})

watch(
  () => selected.value,
  () => {
    if (!selected.value) return

    const norm = _normalize_selected(selected.value)
    const cur = selected.value && typeof selected.value === 'object' ? selected.value : {}
    const cur_span = _numOrNull(cur.span_index)
    const cur_text = _s(cur.text).trim()

    const need_rewrite =
      !_s(cur.library_id).trim() ||
      !_s(cur.doc_id).trim() ||
      cur.chunk_id === undefined ||
      (!Number.isFinite(cur_span) && Number.isFinite(norm.span_index)) ||
      (!cur_text && !!norm.text)

    if (!need_rewrite) return

    try {
      librarySearch.selectItem(norm)
    } catch {}
  },
  { immediate: true }
)

async function copyToClipboard(text) {
  const t0 = String(text || '')
  if (!t0.trim()) return false

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(t0)
      return true
    }
  } catch {}

  try {
    const ta = document.createElement('textarea')
    ta.value = t0
    ta.setAttribute('readonly', 'true')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    ta.style.top = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return !!ok
  } catch {
    return false
  }
}

async function copyEvidenceText() {
  const it = evidenceSelected.value
  if (!it) return
  const ok = await copyToClipboard(String(it.text || ''))
  if (ok) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('rightSidebar.evidenceCard.toasts.copied'), type: 'info' }
      })
    )
  } else {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('rightSidebar.evidenceCard.toasts.copyFailed'), type: 'error' }
      })
    )
  }
}
</script>

<style scoped>
.evidence-card {
  padding: 0.7rem 0.8rem;
  border-bottom: 1px solid var(--line);
  background: var(--sidebar-bg);
  font-size: 0.82rem;
  color: var(--text-secondary);
  min-width: 0;
}

.evidence-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 0.4rem;
  min-width: 0;
}

.evidence-title {
  font-weight: 600;
  color: var(--text-main);
  min-width: 0;
}

.evidence-clear {
  width: 26px;
  height: 26px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
}
.evidence-clear:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.evidence-meta {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
  min-width: 0;
}

.pill {
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-main);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.muted { opacity: 0.75; }

.meta-ellipsis {
  max-width: 14rem;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.evidence-body {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.45;
  color: var(--text-main);
  opacity: 0.92;

  max-height: none;
  overflow: visible;

  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  min-width: 0;
}

.evidence-actions {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.55rem;
  flex-wrap: wrap;
  min-width: 0;
}

.mini-btn {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
  user-select: none;
}
.mini-btn:disabled { opacity: 0.55; cursor: not-allowed; }

.evidence-hint { margin-top: 0.45rem; }

.selectable { user-select: text; }
</style>
