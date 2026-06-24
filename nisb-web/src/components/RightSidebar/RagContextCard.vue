<template>
  <div class="ragctx-card" :class="variant" @mouseenter="onEnter" @mouseleave="onLeave">
    <div class="ragctx-header">
      <div class="ragctx-title">
        {{ t('chat.ragContextCard.title') }}
        <span class="ragctx-sub">{{ t('chat.ragContextCard.modeLabel', { mode: modeLabel }) }}</span>
      </div>

      <div class="ragctx-actions">
        <button
          type="button"
          class="mini-btn"
          @click="setScopeGlobal"
          :title="t('chat.ragContextCard.actions.setGlobalTitle')"
          :aria-label="t('chat.ragContextCard.actions.setGlobalTitle')"
        >
          🌐
        </button>
        <button
          type="button"
          class="mini-btn"
          @click="clearContext"
          :title="t('chat.ragContextCard.actions.clearContextTitle')"
          :aria-label="t('chat.ragContextCard.actions.clearContextTitle')"
        >
          🧹
        </button>
        <button
          type="button"
          class="mini-btn"
          @click="close"
          :title="t('chat.ragContextCard.actions.closeTitle')"
          :aria-label="t('chat.ragContextCard.actions.closeTitle')"
        >
          ×
        </button>
      </div>
    </div>

    <div class="ragctx-body">
      <div class="ragctx-left">
        <div class="search-row">
          <input
            v-model="libQuery"
            class="search-input"
            :placeholder="t('chat.ragContextCard.search.libraryPlaceholder')"
          />
        </div>

        <div v-if="loadingLibs" class="tip">{{ t('chat.ragContextCard.states.loadingLibraries') }}</div>
        <div v-else-if="filteredLibs.length === 0" class="tip">{{ t('chat.ragContextCard.states.emptyLibraries') }}</div>

        <div v-else class="list">
          <div
            v-for="lib in filteredLibs"
            :key="lib.library_id"
            class="row"
            :class="{ active: lib.library_id === activeLibraryId }"
            @click="activateLibrary(lib)"
            :title="lib.library_name"
          >
            <span class="lib-icon" :style="{ color: lib.color || '#3B82F6' }">{{ lib.icon || '🏛️' }}</span>
            <span class="lib-name">{{ lib.library_name }}</span>
            <span class="lib-meta">{{ lib.doc_count || 0 }}</span>
          </div>
        </div>

        <button
          v-if="activeLibraryId"
          type="button"
          class="use-btn"
          @click="useActiveLibrary"
          :title="t('chat.ragContextCard.actions.useThisLibraryTitle')"
        >
          {{ t('chat.ragContextCard.actions.useThisLibrary') }}
        </button>
      </div>

      <div class="ragctx-right">
        <div class="group-box">
          <div class="group-title">{{ t('chat.ragContextCard.group.title') }}</div>

          <div class="group-current">
            <span class="pill">{{ t('chat.ragContextCard.current.groupId', { value: selectedGroupId || emptyMark }) }}</span>
            <button
              v-if="selectedGroupId"
              class="mini-link"
              type="button"
              @click="clearGroupOnly"
              :title="t('chat.ragContextCard.actions.clearGroupOnlyTitle')"
            >
              {{ t('chat.ragContextCard.actions.clearGroupOnly') }}
            </button>
          </div>

          <div class="search-row">
            <input
              v-model="groupQuery"
              class="search-input"
              :placeholder="t('chat.ragContextCard.search.groupPlaceholder')"
            />
          </div>

          <div v-if="loadingGroups" class="tip">{{ t('chat.ragContextCard.states.loadingGroups') }}</div>
          <div v-else-if="filteredGroups.length === 0" class="tip">{{ t('chat.ragContextCard.states.emptyGroups') }}</div>

          <div v-else class="list">
            <div
              v-for="g in filteredGroups"
              :key="g.group_id"
              class="row"
              :class="{ active: g.group_id === selectedGroupId }"
              @click="useGroup(g)"
              :title="g.group_name"
            >
              <span class="lib-icon" :style="{ color: g.color || '#3B82F6' }">{{ g.icon || '📚' }}</span>
              <span class="lib-name">{{ g.group_name }}</span>
              <span class="lib-meta mono">{{ g.group_id }}</span>
            </div>
          </div>

          <div class="group-hint">
            {{ t('chat.ragContextCard.group.hint') }}
          </div>
        </div>

        <div class="docs-head">
          <div class="docs-title">{{ t('chat.ragContextCard.docs.title') }}</div>
          <div class="docs-hint" v-if="activeLibraryId">{{ t('chat.ragContextCard.docs.clickToSelectAndClose') }}</div>
          <div class="docs-hint" v-else>{{ t('chat.ragContextCard.docs.selectLibraryFirst') }}</div>
        </div>

        <div v-if="!activeLibraryId" class="tip">{{ t('chat.ragContextCard.states.noLibrarySelected') }}</div>

        <template v-else>
          <div class="search-row">
            <input
              v-model="docQuery"
              class="search-input"
              :placeholder="t('chat.ragContextCard.search.docPlaceholder')"
            />
          </div>

          <div v-if="docsLoading(activeLibraryId)" class="tip">{{ t('chat.ragContextCard.states.loadingDocuments') }}</div>

          <div v-else-if="docsError(activeLibraryId)" class="tip error">
            {{ t('chat.ragContextCard.states.docLoadFailed', { error: docsError(activeLibraryId) }) }}
          </div>

          <div v-else-if="filteredDocs.length === 0" class="tip">{{ t('chat.ragContextCard.states.emptyDocuments') }}</div>

          <div v-else class="list">
            <div
              v-for="(doc, i) in filteredDocs"
              :key="doc.doc_id || doc.filename || i"
              class="row doc"
              :class="{ active: doc.doc_id === activeDocId }"
              @click="selectDoc(activeLibraryId, doc)"
              :title="doc.filename || doc.doc_id"
            >
              <span class="doc-name">{{ doc.filename || doc.doc_id }}</span>
              <span class="doc-meta">{{ doc.filetype || t('chat.ragContextCard.docs.defaultFiletype') }} · {{ doc.chunks || 0 }}</span>
            </div>
          </div>
        </template>

        <div class="current">
          <div class="current-title">{{ t('chat.ragContextCard.current.title') }}</div>
          <div class="current-line">
            <span class="pill">{{ t('chat.ragContextCard.current.store', { scope: scopeLabel(ragStoreScope) }) }}</span>
            <span class="pill">{{ t('chat.ragContextCard.current.evidence', { scope: scopeLabel(ragEvidenceScope) }) }}</span>
          </div>
          <div class="current-line dim">
            <span class="mono">{{ t('chat.ragContextCard.current.groupId', { value: selectedGroupId || emptyMark }) }}</span>
          </div>
          <div class="current-line dim">
            <span class="mono">{{ t('chat.ragContextCard.current.libraryId', { value: selectedLibraryId || emptyMark }) }}</span>
          </div>
          <div class="current-line dim">
            <span class="mono">{{ t('chat.ragContextCard.current.docId', { value: selectedDocId || emptyMark }) }}</span>
          </div>
        </div>

        <div v-if="showSidebarInfoBoxes" class="scope-box">
          <div class="scope-title">
            {{ t('chat.ragContextCard.summary.docTimeTitle') }}
            <span class="scope-sub">
              {{ t('chat.ragContextCard.summary.readOnlyLabel', { value: t('chat.ragContextCard.summary.readOnlySub') }) }}
            </span>
          </div>

          <div class="scope-line">
            <span class="pill">{{ t('chat.ragContextCard.summary.enabled', { value: boolLabel(docTimeEnabled) }) }}</span>
            <span class="pill">{{ t('chat.ragContextCard.summary.mode', { value: docTimeModeLabel }) }}</span>
            <span class="pill" v-if="docTimeMode === 'days'">{{ t('chat.ragContextCard.summary.days', { value: docTimeDaysLabel }) }}</span>
            <span class="pill" v-else>{{ t('chat.ragContextCard.summary.range', { value: docTimeRelativeLabel }) }}</span>
          </div>

          <div class="scope-hint">
            {{ t('chat.ragContextCard.summary.docTimeHint') }}
          </div>
        </div>

        <div v-if="showSidebarInfoBoxes" class="scope-box">
          <div class="scope-title">
            {{ t('chat.ragContextCard.summary.rssTitle') }}
            <span class="scope-sub">
              {{ t('chat.ragContextCard.summary.readOnlyLabel', { value: t('chat.ragContextCard.summary.readOnlySub') }) }}
            </span>
          </div>

          <div class="scope-line">
            <span class="pill">{{ t('chat.ragContextCard.summary.enabled', { value: boolLabel(rssReferenceEnabled) }) }}</span>
            <span class="pill">{{ t('chat.ragContextCard.summary.days', { value: rssReferenceDaysLabel }) }}</span>
            <span class="pill">{{ t('chat.ragContextCard.summary.limit', { value: rssReferenceLimit }) }}</span>
          </div>

          <div class="scope-line">
            <span class="pill">{{ t('chat.ragContextCard.summary.minScore', { value: rssReferenceMinScore }) }}</span>
            <span class="pill">{{ t('chat.ragContextCard.summary.strictLexical', { value: boolLabel(rssReferenceStrictLexical) }) }}</span>
          </div>

          <div class="scope-hint">
            {{ t('chat.ragContextCard.summary.rssHint') }}
          </div>
        </div>

        <div class="footer-hint">
          {{ t('chat.ragContextCard.footerHint') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useMCP } from '../../composables/useMCP'
import { useChatConfigStore } from '../../stores/chatConfig'

const props = defineProps({
  mode: { type: String, default: 'cite' },
  variant: { type: String, default: 'sidebar' },
  applyModeOnSelect: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'mouseenter', 'mouseleave'])

const { t } = useI18n()
const { callTool } = useMCP()
const chatCfg = useChatConfigStore()
if (typeof chatCfg.hydrate === 'function') chatCfg.hydrate()

const { rag } = storeToRefs(chatCfg)

const loadingLibs = ref(false)
const libs = ref([])
const libQuery = ref('')
const docQuery = ref('')

const activeLibraryId = ref(null)
const activeDocId = ref(null)

const docsMap = ref({})

const loadingGroups = ref(false)
const groups = ref([])
const groupQuery = ref('')

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function boolLabel(value) {
  return value ? t('chat.ragContextCard.common.true') : t('chat.ragContextCard.common.false')
}

function scopeLabel(value) {
  const s = String(value || 'global').trim().toLowerCase()
  if (s === 'library') return t('chat.ragContextCard.scopes.library')
  if (s === 'doc') return t('chat.ragContextCard.scopes.doc')
  return t('chat.ragContextCard.scopes.global')
}

function docsState(library_id) {
  const id = String(library_id || '').trim()
  if (!id) return { loading: false, docs: [], error: '' }
  if (!docsMap.value[id]) docsMap.value[id] = { loading: false, docs: [], error: '' }
  return docsMap.value[id]
}
function docsLoading(library_id) {
  return !!docsState(library_id).loading
}
function docsError(library_id) {
  return String(docsState(library_id).error || '')
}

const emptyMark = computed(() => t('chat.ragContextCard.common.emptyMark'))
const modeLabel = computed(() => (props.mode === 'ground' ? t('chat.ragContextCard.mode.ground') : t('chat.ragContextCard.mode.cite')))
const showSidebarInfoBoxes = computed(() => String(props.variant || 'sidebar') !== 'menu')

const selectedLibraryId = computed(() => rag.value?.context?.libraryId || null)
const selectedDocId = computed(() => rag.value?.context?.docId || null)
const selectedGroupId = computed(() => rag.value?.context?.group_id || null)
const ragStoreScope = computed(() => rag.value?.storeScope || 'global')
const ragEvidenceScope = computed(() => rag.value?.evidenceScope || 'global')

const docTimeEnabled = computed(() => !!rag.value?.docTime?.enabled)
const docTimeMode = computed(() => String(rag.value?.docTime?.mode || 'days'))
const docTimeDays = computed(() => {
  const n = Number(rag.value?.docTime?.days)
  return Number.isFinite(n) ? Math.max(0, Math.min(3650, Math.trunc(n))) : 3
})
const docTimeDaysLabel = computed(() => (docTimeDays.value === 0 ? t('chat.ragContextCard.common.all') : String(docTimeDays.value)))
const docTimeModeLabel = computed(() =>
  docTimeMode.value === 'relative'
    ? t('chat.ragContextCard.docTimeModes.relative')
    : t('chat.ragContextCard.docTimeModes.days')
)

const docTimeRelativeLabel = computed(() => {
  const rel = rag.value?.docTime?.relative || {}
  const older = Number(rel?.olderDaysAgo)
  const newer = Number(rel?.newerDaysAgo)
  if (!Number.isFinite(older) && !Number.isFinite(newer)) return emptyMark.value
  return t('chat.ragContextCard.relativeRangeLabel', {
    older: Number.isFinite(older) ? older : emptyMark.value,
    newer: Number.isFinite(newer) ? newer : emptyMark.value,
  })
})

const rssRefState = computed(() => rag.value?.rssReference || rag.value?.rss || {})
const rssReferenceEnabled = computed(() => !!rssRefState.value?.enabled)
const rssReferenceDaysLabel = computed(() => {
  const n = Number(rssRefState.value?.days)
  const fixed = Number.isFinite(n) ? Math.max(0, Math.min(3650, Math.trunc(n))) : 7
  return fixed === 0 ? t('chat.ragContextCard.common.all') : String(fixed)
})
const rssReferenceLimit = computed(() => {
  const n = Number(rssRefState.value?.limit)
  return Number.isFinite(n) ? Math.max(1, Math.min(20, Math.trunc(n))) : 8
})
const rssReferenceMinScore = computed(() => {
  const n = Number(rssRefState.value?.minScore)
  return Number.isFinite(n) ? n.toFixed(2) : '0.28'
})
const rssReferenceStrictLexical = computed(() => !!rssRefState.value?.strictLexical)

const filteredLibs = computed(() => {
  const q = (libQuery.value || '').trim().toLowerCase()
  if (!q) return libs.value
  return libs.value.filter((l) => {
    return String(l.library_name || '').toLowerCase().includes(q) || String(l.library_id || '').toLowerCase().includes(q)
  })
})

const filteredDocs = computed(() => {
  if (!activeLibraryId.value) return []
  const docs = docsState(activeLibraryId.value).docs || []
  const q = (docQuery.value || '').trim().toLowerCase()
  if (!q) return docs
  return docs.filter((d) => {
    const name = String(d?.filename || '').toLowerCase()
    const id = String(d?.doc_id || '').toLowerCase()
    return name.includes(q) || id.includes(q)
  })
})

const filteredGroups = computed(() => {
  const q = (groupQuery.value || '').trim().toLowerCase()
  if (!q) return groups.value
  return groups.value.filter((g) => {
    return String(g?.group_name || '').toLowerCase().includes(q) || String(g?.group_id || '').toLowerCase().includes(q)
  })
})

async function loadLibraries() {
  if (loadingLibs.value) return
  loadingLibs.value = true
  try {
    const res = await callTool('nisb_library_list', {})
    if (res && res.status === 'success') {
      const rawList = Array.isArray(res.libraries) ? res.libraries : []
      libs.value = rawList.map((lib) => {
        const stats = lib.stats || {}
        return {
          library_id: lib.library_id || 'unknown_library',
          library_name: lib.library_name || lib.name || t('chat.ragContextCard.library.untitled'),
          icon: lib.icon || '🏛️',
          color: lib.color || '#3B82F6',
          doc_count: lib.doc_count != null ? lib.doc_count : (stats.doc_count != null ? stats.doc_count : 0),
        }
      })
    } else {
      libs.value = []
    }
  } finally {
    loadingLibs.value = false
  }
}

async function loadGroups() {
  if (loadingGroups.value) return
  loadingGroups.value = true
  try {
    const res = await callTool('nisb_library_group_list', {})
    if (res && res.status === 'success') {
      groups.value = Array.isArray(res.groups) ? res.groups : []
    } else {
      groups.value = []
    }
  } catch {
    groups.value = []
  } finally {
    loadingGroups.value = false
  }
}

async function loadDocs(library_id) {
  const id = String(library_id || '').trim()
  if (!id) return

  const st = docsState(id)
  if (st.loading) return
  st.loading = true
  st.error = ''

  try {
    const res = await callTool('nisb_doc_stats', { library_id: id })
    if (res && res.status === 'success') {
      const docs = Array.isArray(res.documents) ? res.documents : (Array.isArray(res.raw?.documents) ? res.raw.documents : [])
      st.docs = docs.map((d) => ({
        doc_id: d.doc_id || '',
        filename: d.filename || '',
        filetype: d.filetype || '',
        chunks: d.chunks,
        created_at: d.created_at,
      }))
    } else {
      st.error = String(res?.message || t('chat.ragContextCard.errors.docStatsFailed'))
    }
  } catch (e) {
    st.error = String(e?.message || e)
  } finally {
    st.loading = false
  }
}

function _applyModeIfNeeded() {
  if (!props.applyModeOnSelect) return
  chatCfg.setRagMode(props.mode === 'ground' ? 'ground' : 'cite')
}

function activateLibrary(lib) {
  const id = String(lib?.library_id || '').trim()
  if (!id) return
  activeLibraryId.value = id
  activeDocId.value = null
  docQuery.value = ''
  loadDocs(id)
}

function useActiveLibrary() {
  if (!activeLibraryId.value) return
  _applyModeIfNeeded()
  chatCfg.setRagContext({
    libraryId: activeLibraryId.value,
    docId: null,
    group_id: null,
    storeScope: 'library',
    evidenceScope: 'library',
  })
  toast(t('chat.ragContextCard.toast.librarySelected', { id: activeLibraryId.value }), 'success')
  emit('close')
}

function selectDoc(library_id, doc) {
  const lib_id = String(library_id || '').trim()
  const doc_id = String(doc?.doc_id || '').trim()
  if (!lib_id || !doc_id) return

  activeLibraryId.value = lib_id
  activeDocId.value = doc_id

  _applyModeIfNeeded()
  chatCfg.setRagContext({
    libraryId: lib_id,
    docId: doc_id,
    group_id: null,
    storeScope: 'doc',
    evidenceScope: 'doc',
  })
  toast(t('chat.ragContextCard.toast.docSelected', { id: doc_id }), 'success')
  emit('close')
}

function useGroup(g) {
  const gid = String(g?.group_id || '').trim()
  if (!gid) return

  _applyModeIfNeeded()

  chatCfg.setRagContext({
    libraryId: null,
    docId: null,
    group_id: gid,
    storeScope: 'global',
    evidenceScope: 'global',
  })

  toast(t('chat.ragContextCard.toast.groupSelected', { id: gid }), 'success')
  emit('close')
}

function clearGroupOnly() {
  chatCfg.setRagContext({
    libraryId: selectedLibraryId.value,
    docId: selectedDocId.value,
    group_id: null,
    storeScope: ragStoreScope.value,
    evidenceScope: ragEvidenceScope.value,
  })
  toast(t('chat.ragContextCard.toast.groupCleared'), 'info')
}

function setScopeGlobal() {
  chatCfg.clearRagContext()
  toast(t('chat.ragContextCard.toast.switchedGlobal'), 'info')
}

function clearContext() {
  chatCfg.clearRagContext()
  activeDocId.value = null
  toast(t('chat.ragContextCard.toast.contextCleared'), 'info')
}

function close() {
  emit('close')
}
function onEnter() { emit('mouseenter') }
function onLeave() { emit('mouseleave') }

loadLibraries()
loadGroups()
</script>

<style scoped>
.ragctx-card {
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 16px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 44%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 80%, transparent)
    );
  color: var(--text-secondary);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.ragctx-card.sidebar {
  margin: 0.55rem;
}

.ragctx-card.menu {
  margin: 0;
  border-radius: 14px;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 14px 34px rgba(0, 0, 0, 0.12);
}

.ragctx-header {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.58rem;
  padding: 0.58rem 0.62rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
}

.ragctx-title {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.ragctx-sub {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 720;
  line-height: 1.25;
  opacity: 0.9;
  white-space: nowrap;
}

.ragctx-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.32rem;
}

.mini-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.86rem;
  font-weight: 760;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.mini-btn:hover,
.mini-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 6px 14px rgba(0, 0, 0, 0.06);
  outline: none;
}

.mini-btn:active {
  transform: translateY(1px);
}

.ragctx-body {
  min-width: 0;
  display: flex;
  gap: 0;
  height: clamp(280px, 48vh, 540px);
}

.ragctx-left,
.ragctx-right {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0.58rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.ragctx-left::-webkit-scrollbar,
.ragctx-right::-webkit-scrollbar {
  width: 8px;
}

.ragctx-left::-webkit-scrollbar-thumb,
.ragctx-right::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.ragctx-left {
  border-right: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 26%, transparent);
}

.ragctx-right {
  background: color-mix(in srgb, var(--editor-bg) 16%, transparent);
}

.search-row {
  flex: 0 0 auto;
  min-width: 0;
  margin-bottom: 0.46rem;
}

.search-input {
  width: 100%;
  min-width: 0;
  height: 32px;
  box-sizing: border-box;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 64%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 680;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    color 0.15s ease;
}

.search-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.search-input:hover,
.search-input:focus {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 34%, transparent),
      color-mix(in srgb, var(--editor-bg) 64%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.tip {
  flex: 0 0 auto;
  min-width: 0;
  margin: 0.12rem 0 0.38rem;
  padding: 0.52rem 0.58rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 40%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.tip.error {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: color-mix(in srgb, #ef4444 86%, var(--text-main, var(--text)));
  font-weight: 690;
}

.list {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.32rem;
}

.row {
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  padding: 0.42rem 0.5rem;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.row:hover,
.row:focus-within {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 38%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.row:active {
  transform: translateY(1px);
}

.row.active {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 68%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
}

.lib-icon {
  flex: 0 0 20px;
  width: 20px;
  text-align: center;
  font-size: 0.9rem;
  line-height: 1;
}

.lib-name,
.doc-name {
  flex: 1 1 auto;
  min-width: 0;
  color: inherit;
  font-size: 0.78rem;
  font-weight: 730;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lib-meta,
.doc-meta {
  flex: 0 0 auto;
  max-width: 42%;
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 720;
  line-height: 1.25;
  opacity: 0.86;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row.active .lib-meta,
.row.active .doc-meta {
  color: var(--selected);
  opacity: 0.9;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace);
  overflow-wrap: anywhere;
}

.use-btn {
  flex: 0 0 auto;
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.5rem;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 11px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 38%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 780;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.use-btn:hover,
.use-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
  outline: none;
}

.use-btn:active {
  transform: translateY(1px);
}

.group-box,
.current,
.scope-box {
  flex: 0 0 auto;
  min-width: 0;
  padding: 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 40%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
}

.group-box {
  margin-bottom: 0.58rem;
}

.current,
.scope-box {
  margin-top: 0.58rem;
}

.group-title,
.docs-title,
.current-title,
.scope-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 810;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.group-title {
  margin-bottom: 0.38rem;
}

.group-current {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.46rem;
  margin-bottom: 0.46rem;
}

.mini-link {
  flex: 0 0 auto;
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.69rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.mini-link:hover,
.mini-link:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.group-hint,
.scope-hint,
.footer-hint {
  min-width: 0;
  margin-top: 0.42rem;
  color: var(--text-secondary);
  font-size: 0.73rem;
  line-height: 1.48;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  opacity: 0.9;
}

.docs-head {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.38rem;
}

.docs-hint {
  flex: 0 1 auto;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.35;
  text-align: right;
  opacity: 0.88;
  overflow-wrap: break-word;
}

.row.doc {
  align-items: flex-start;
  flex-direction: column;
  gap: 0.16rem;
}

.row.doc .doc-meta {
  max-width: 100%;
}

.current-title {
  margin-bottom: 0.38rem;
}

.current-line,
.scope-line {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.35;
}

.current-line + .current-line,
.scope-line + .scope-line {
  margin-top: 0.34rem;
}

.current-line.dim {
  opacity: 0.92;
}

.pill {
  max-width: 100%;
  min-height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 750;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.scope-title {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-bottom: 0.38rem;
}

.scope-sub {
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 720;
  line-height: 1.25;
  opacity: 0.9;
  white-space: nowrap;
}

.footer-hint {
  flex: 0 0 auto;
  margin-top: 0.58rem;
  padding: 0.5rem 0.54rem;
  border: 1px dashed color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 34%, transparent);
}

@media (max-width: 980px) {
  .ragctx-body {
    flex-direction: column;
    height: clamp(360px, 62vh, 620px);
  }

  .ragctx-left {
    border-right: none;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  }
}

@media (max-width: 520px) {
  .ragctx-card.sidebar {
    margin: 0.45rem;
  }

  .ragctx-header {
    flex-direction: column;
    align-items: stretch;
  }

  .ragctx-actions {
    justify-content: flex-start;
  }

  .ragctx-title {
    flex-wrap: wrap;
  }

  .group-current,
  .docs-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .docs-hint {
    text-align: left;
  }

  .mini-link,
  .use-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
