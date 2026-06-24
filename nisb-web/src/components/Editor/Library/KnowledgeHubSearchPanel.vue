<template>
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="title">{{ t('library.center.searchPanel.title') }}</div>
        <div class="sub">{{ t('library.center.searchPanel.subtitle') }}</div>
      </div>
      <span class="state-chip mono">{{ scope }}</span>
    </div>

    <div class="controls">
      <label class="field">
        <span class="label">{{ t('library.center.searchPanel.scopeTitle') }}</span>
        <select class="nisb-select" v-model="scope" :title="t('library.center.searchPanel.scopeTitle')">
          <option value="global">{{ t('library.center.searchPanel.scopeOptions.global') }}</option>
          <option value="library">{{ t('library.center.searchPanel.scopeOptions.library') }}</option>
          <option value="doc">{{ t('library.center.searchPanel.scopeOptions.doc') }}</option>
        </select>
      </label>

      <label class="field">
        <span class="label">{{ t('library.center.searchPanel.libraryTitle') }}</span>
        <select
          class="nisb-select"
          v-model="selectedLibraryId"
          :disabled="scope === 'global'"
          :title="t('library.center.searchPanel.libraryTitle')"
        >
          <option value="">{{ t('library.center.searchPanel.selectLibrary') }}</option>
          <option v-for="id in libraryOptions" :key="id" :value="id">{{ id }}</option>
        </select>
      </label>

      <label v-if="scope === 'doc'" class="field">
        <span class="label">{{ t('library.center.searchPanel.docIdTitle') }}</span>
        <input
          class="nisb-input mono"
          v-model="docId"
          :placeholder="t('library.center.searchPanel.docIdPlaceholder')"
          :title="t('library.center.searchPanel.docIdTitle')"
        />
      </label>

      <label v-if="scope !== 'doc'" class="field">
        <span class="label">{{ t('library.center.searchPanel.groupFilterTitle') }}</span>
        <select
          class="nisb-select"
          v-model="groupIdModel"
          :disabled="loadingGroups"
          :title="t('library.center.searchPanel.groupFilterTitle')"
        >
          <option value="">{{ t('library.center.searchPanel.groupNoFilter') }}</option>
          <option v-for="g in groupOptions" :key="g.group_id" :value="g.group_id">
            {{ (g.icon || '📚') + ' ' + (g.group_name || g.group_id) + ' · ' + g.group_id }}
          </option>
        </select>
      </label>

      <label class="field query-field">
        <span class="label">{{ t('library.center.searchPanel.queryPlaceholder') }}</span>
        <input
          class="nisb-input query-input"
          v-model="query"
          :placeholder="t('library.center.searchPanel.queryPlaceholder')"
          @keydown.enter.prevent="search"
        />
      </label>

      <label class="field">
        <span class="label">{{ t('library.center.searchPanel.topKTitle') }}</span>
        <select class="nisb-select" v-model.number="topK" :title="t('library.center.searchPanel.topKTitle')">
          <option :value="5">{{ t('library.center.searchPanel.topKOption', { value: 5 }) }}</option>
          <option :value="10">{{ t('library.center.searchPanel.topKOption', { value: 10 }) }}</option>
          <option :value="20">{{ t('library.center.searchPanel.topKOption', { value: 20 }) }}</option>
          <option :value="50">{{ t('library.center.searchPanel.topKOption', { value: 50 }) }}</option>
        </select>
      </label>

      <div class="button-row">
        <button
          v-if="scope !== 'doc'"
          class="ghost-btn"
          :disabled="loadingGroups"
          @click="loadGroups"
          type="button"
          :title="t('library.center.searchPanel.refreshGroupsTitle')"
        >
          {{ loadingGroups ? t('library.center.searchPanel.loadingGroups') : t('library.center.searchPanel.refreshGroups') }}
        </button>

        <button class="ghost-btn primary" :disabled="loading || !canSearch" @click="search" type="button">
          {{ loading ? t('library.center.searchPanel.searching') : t('library.center.searchPanel.search') }}
        </button>

        <button class="ghost-btn" :disabled="loading || !lastResultCount" @click="clearResults" type="button">
          {{ t('library.center.searchPanel.clearResults') }}
        </button>
      </div>
    </div>

    <div v-if="lastResultCount || lastQueryText" class="meta-row">
      <span class="pill">{{ t('library.center.searchPanel.resultCount', { count: lastResultCount }) }}</span>
      <span class="pill" v-if="lastQueryText">{{ t('library.center.searchPanel.queryMeta', { query: lastQueryText }) }}</span>
      <span class="pill mono" v-if="selectedLibraryId && scope !== 'global'">{{ t('library.center.searchPanel.libraryMeta', { libraryId: selectedLibraryId }) }}</span>
      <span class="pill mono" v-if="effectiveGroupId">{{ t('library.center.searchPanel.groupMeta', { groupId: effectiveGroupId }) }}</span>
    </div>

    <div v-if="hint" class="hint">{{ hint }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'

const props = defineProps({
  libraryOptions: { type: Array, default: () => [] },
  docMeta: { type: Object, default: () => ({}) },
  currentLibraryId: { type: String, default: '' }
})

const emit = defineEmits(['results'])

const { callTool } = useMCP()
const { t, locale } = useI18n()

const STORAGE_KEY = 'nisb-knowledge-hub-search:v6'

const scope = ref('global')
const selectedLibraryId = ref('')
const docId = ref('')
const query = ref('')
const topK = ref(50)

const loading = ref(false)
const lastResultCount = ref(0)
const lastQueryText = ref('')

const loadingGroups = ref(false)
const groups = ref([])
const selectedGroupId = ref('')

function normalizeId(v) {
  return String(v || '').trim()
}

function currentLibraryIdSafe() {
  return normalizeId(props.currentLibraryId)
}

function applyCurrentLibraryDefault() {
  const currentLibraryId = currentLibraryIdSafe()
  if (!currentLibraryId) return
  if (scope.value !== 'doc') return

  if (!normalizeId(selectedLibraryId.value)) {
    selectedLibraryId.value = currentLibraryId
    persist()
  }
}

const groupOptions = computed(() => {
  const arr = Array.isArray(groups.value) ? groups.value : []
  return arr
    .map((g) => ({
      group_id: String(g?.group_id || '').trim(),
      group_name: String(g?.group_name || '').trim(),
      icon: String(g?.icon || '').trim(),
      color: String(g?.color || '').trim()
    }))
    .filter((g) => !!g.group_id)
})

const effectiveGroupId = computed(() => {
  if (scope.value === 'doc') return ''
  return normalizeId(selectedGroupId.value)
})

const groupIdModel = computed({
  get() {
    if (scope.value === 'doc') return ''
    return normalizeId(selectedGroupId.value)
  },
  set(v) {
    if (scope.value === 'doc') return
    selectedGroupId.value = normalizeId(v)
    persist()
  }
})

const hint = computed(() => {
  if (scope.value === 'global') return t('library.center.searchPanel.hintGlobal')
  if (scope.value === 'library' && !selectedLibraryId.value) return t('library.center.searchPanel.hintLibrary')
  if (scope.value === 'doc') {
    if (!selectedLibraryId.value) return t('library.center.searchPanel.hintDocNeedLibrary')
    if (!docId.value.trim()) return t('library.center.searchPanel.hintDocNeedDocId')
  }
  return ''
})

const canSearch = computed(() => {
  if (!query.value.trim()) return false
  if (scope.value === 'global') return true
  if (scope.value === 'library') return !!normalizeId(selectedLibraryId.value)
  if (scope.value === 'doc') return !!normalizeId(selectedLibraryId.value) && !!docId.value.trim()
  return false
})

function safeText(v) {
  const s = String(v == null ? '' : v)
  return s.replace(/\s+/g, ' ').trim()
}

function toNum(v, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function resolveDocTitle(libraryId, docIdVal) {
  const libMap = props.docMeta?.[libraryId] || null
  const meta = libMap?.[docIdVal] || null
  const fn = String(meta?.filename || '').trim()
  return fn || ''
}

function normalizeEvidenceItem(raw, fallbackLibraryId) {
  const libraryId = String(raw?.library_id || fallbackLibraryId || '').trim()
  const docIdVal = String(raw?.doc_id || '').trim()

  const spanIndex = toNum(raw?.span_index ?? raw?.spanIndex ?? raw?.span_id ?? raw?.span, 0) || 0

  const score = toNum(raw?.score ?? raw?.similarity ?? raw?.distance, null)
  const scoreText = score == null ? '--' : String(Math.round(score * 1000) / 1000)

  const text = safeText(
    raw?.text ||
      raw?.snippet ||
      raw?.content ||
      raw?.chunk_text ||
      raw?.chunk ||
      raw?.evidence ||
      raw?.quote
  )

  const preview = text ? (text.length > 260 ? text.slice(0, 260) + '…' : text) : t('library.center.searchPanel.emptySnippet')

  return {
    kind: 'evidence',
    key: `ev:${libraryId}:${docIdVal}:${spanIndex}:${scoreText}:${Math.random().toString(16).slice(2)}`,
    libraryId,
    docId: docIdVal,
    docTitle: resolveDocTitle(libraryId, docIdVal),
    spanIndex,
    scoreText,
    preview,
    createdAt: new Date().toISOString(),
    createdAtLocal: new Date().toLocaleString(locale.value || undefined),
    canDelete: false
  }
}

function pickList(res) {
  if (!res) return []
  if (Array.isArray(res.items)) return res.items
  if (Array.isArray(res.results)) return res.results
  if (Array.isArray(res.hits)) return res.hits
  return []
}

function persist() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        scope: scope.value,
        selectedLibraryId: selectedLibraryId.value,
        docId: docId.value,
        query: query.value,
        topK: topK.value,
        selectedGroupId: selectedGroupId.value
      })
    )
  } catch {}
}

function restore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const obj = JSON.parse(raw)
    if (!obj || typeof obj !== 'object') return
    if (obj.scope) scope.value = String(obj.scope)
    if (typeof obj.selectedLibraryId === 'string') selectedLibraryId.value = obj.selectedLibraryId
    if (typeof obj.docId === 'string') docId.value = obj.docId
    if (typeof obj.query === 'string') query.value = obj.query
    if (obj.topK != null) topK.value = Number(obj.topK) || 50
    if (typeof obj.selectedGroupId === 'string') selectedGroupId.value = obj.selectedGroupId
  } catch {}
}

async function loadGroups() {
  if (loadingGroups.value) return
  loadingGroups.value = true
  try {
    const res = await callTool('nisb_library_group_list', {})
    if (res?.status === 'success') {
      groups.value = Array.isArray(res.groups) ? res.groups : []

      const exists = groups.value.some(
        (g) => String(g?.group_id || '').trim() === normalizeId(selectedGroupId.value)
      )
      if (!exists) {
        selectedGroupId.value = ''
        persist()
      }
    } else {
      groups.value = []
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: { message: res?.message || t('library.center.searchPanel.groupsLoadFailed'), type: 'error' }
        })
      )
    }
  } catch (e) {
    groups.value = []
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: e?.message || t('library.center.searchPanel.groupsLoadError'), type: 'error' }
      })
    )
  } finally {
    loadingGroups.value = false
  }
}

async function search() {
  if (!canSearch.value || loading.value) return
  loading.value = true
  try {
    persist()

    const q = query.value.trim()
    const k = Number(topK.value) || 50

    let res = null
    if (scope.value === 'doc') {
      res = await callTool('nisb_library_doc_evidence', {
        query: q,
        library_id: normalizeId(selectedLibraryId.value),
        doc_id: docId.value.trim(),
        top_k: k
      })
    } else {
      res = await callTool('nisb_doc_evidence_scope', {
        query: q,
        scope: scope.value,
        library_id: scope.value === 'library' ? normalizeId(selectedLibraryId.value) : null,
        doc_id: null,
        top_k: k,
        group_id: effectiveGroupId.value || undefined
      })
    }

    if (res?.status !== 'success') {
      lastResultCount.value = 0
      lastQueryText.value = q
      emit('results', {
        query: q,
        items: [],
        status: 'error',
        message: res?.message || t('library.center.searchPanel.searchFailed')
      })
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: { message: res?.message || t('library.center.searchPanel.searchFailed'), type: 'error' }
        })
      )
      return
    }

    const list = pickList(res)
    const normalized = list
      .map((x) =>
        normalizeEvidenceItem(
          x,
          scope.value === 'library' || scope.value === 'doc' ? normalizeId(selectedLibraryId.value) : ''
        )
      )
      .filter((x) => x.libraryId && x.docId)

    lastResultCount.value = normalized.length
    lastQueryText.value = q
    emit('results', { query: q, items: normalized, status: 'success' })
  } catch (e) {
    lastResultCount.value = 0
    lastQueryText.value = query.value.trim()
    emit('results', {
      query: query.value.trim(),
      items: [],
      status: 'error',
      message: e?.message || t('library.center.searchPanel.searchError')
    })
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: e?.message || t('library.center.searchPanel.searchError'), type: 'error' }
      })
    )
  } finally {
    loading.value = false
  }
}

function clearResults() {
  lastResultCount.value = 0
  emit('results', { query: lastQueryText.value, items: [], status: 'success' })
}

watch(
  () => props.currentLibraryId,
  () => {
    if (scope.value === 'doc') {
      applyCurrentLibraryDefault()
    }
  },
  { immediate: true }
)

watch(scope, () => {
  if (scope.value === 'global') {
    docId.value = ''
    selectedLibraryId.value = ''
  } else if (scope.value === 'library') {
    docId.value = ''
  } else if (scope.value === 'doc') {
    applyCurrentLibraryDefault()
  }
  persist()
})

watch(selectedLibraryId, () => {
  persist()
})

watch([query, topK, selectedGroupId, docId], () => {
  persist()
})

onMounted(async () => {
  restore()

  if (scope.value === 'doc') {
    applyCurrentLibraryDefault()
  }

  if (scope.value !== 'doc') {
    await loadGroups()
  }
})
</script>

<style scoped>
.panel {
  width: 100%;
  height: 100%;
  max-height: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 32%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 18px 40px rgba(0, 0, 0, 0.08);
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  container-type: inline-size;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.panel::-webkit-scrollbar {
  width: 8px;
}

.panel::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.panel-head {
  flex: 0 0 auto;
  padding: 0.8rem 0.86rem 0.7rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  min-width: 0;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.88rem;
  font-weight: 820;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.sub {
  margin-top: 0.18rem;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.state-chip {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 34%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
}

.controls {
  flex: 0 0 auto;
  padding: 0.72rem 0.78rem 0.64rem;
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.54rem;
  align-items: stretch;
}

.field {
  min-width: 0;
  display: grid;
  gap: 0.3rem;
}

.label {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.71rem;
  font-weight: 740;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nisb-select,
.nisb-input {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  box-sizing: border-box;
  padding: 0.52rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 13px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.8rem;
  line-height: 1.35;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease,
    opacity 0.15s ease;
}

.nisb-select:disabled,
.nisb-input:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.nisb-select:focus,
.nisb-input:focus {
  border-color: color-mix(in srgb, var(--selected) 50%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

.button-row {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 112px), 1fr));
  gap: 0.42rem;
  align-items: stretch;
}

.ghost-btn {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  min-height: 38px;
  box-sizing: border-box;
  padding: 0.36rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1.16;
  white-space: normal;
  overflow-wrap: break-word;
  text-align: center;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.ghost-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 66%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.ghost-btn:hover:not(:disabled),
.ghost-btn:focus-visible:not(:disabled) {
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
    0 10px 22px rgba(0, 0, 0, 0.09);
  outline: none;
}

.ghost-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.meta-row {
  flex: 0 0 auto;
  padding: 0 0.78rem 0.64rem;
  display: flex;
  gap: 0.36rem;
  flex-wrap: wrap;
  align-items: center;
}

.pill {
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  box-sizing: border-box;
  max-width: 100%;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 730;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hint {
  flex: 0 0 auto;
  margin: 0 0.78rem 0.78rem;
  padding: 0.62rem 0.68rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.48;
  overflow-wrap: break-word;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@container (max-width: 420px) {
  .panel-head {
    padding: 0.72rem 0.72rem 0.62rem;
    gap: 0.52rem;
  }

  .controls {
    padding: 0.66rem 0.68rem 0.6rem;
    gap: 0.5rem;
  }

  .button-row {
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 104px), 1fr));
    gap: 0.38rem;
  }

  .ghost-btn {
    min-height: 36px;
    padding: 0.34rem 0.54rem;
    border-radius: 12px;
    font-size: 0.74rem;
  }

  .meta-row {
    padding: 0 0.68rem 0.6rem;
  }

  .hint {
    margin: 0 0.68rem 0.68rem;
  }
}

@container (max-width: 340px) {
  .panel-head {
    display: grid;
  }

  .state-chip {
    justify-self: start;
  }

  .button-row {
    grid-template-columns: 1fr;
  }

  .sub {
    font-size: 0.74rem;
  }

  .nisb-select,
  .nisb-input,
  .ghost-btn {
    min-height: 35px;
  }
}

@media (max-width: 760px) {
  .panel {
    height: auto;
    max-height: none;
    overflow: visible;
  }
}
</style>

