<!-- /opt/mcp-gateway/nisb-web/src/components/RightSidebar/EvidencePanel.vue -->
<template>
  <div v-if="localSyncEnabled || rssItems.length || marketItems.length" class="panel">
    <div class="head">
      <div class="title">{{ t('rightSidebar.evidencePanel.title') }}</div>
      <div class="meta muted">
        <span v-if="rssItems.length">{{ t('rightSidebar.evidencePanel.meta.rssCount', { count: rssItems.length }) }}</span>
        <span v-if="rssItems.length && marketItems.length">·</span>
        <span v-if="marketItems.length">{{ t('rightSidebar.evidencePanel.meta.marketCount', { count: marketItems.length }) }}</span>
        <span v-if="rssItems.length || marketItems.length">·</span>

        <template v-if="localSyncEnabled">
          <span>{{ t('rightSidebar.evidencePanel.meta.localCount', { count: localItems.length }) }}</span>

          <span class="dot">·</span>
          <button
            class="mini ghost"
            type="button"
            :title="localAutoSelectEnabled
              ? t('rightSidebar.evidencePanel.meta.pauseAutoLinkTitle')
              : t('rightSidebar.evidencePanel.meta.resumeAutoLinkTitle')"
            @click="toggleLocalAutoSelect"
          >
            {{ localAutoSelectEnabled
              ? t('rightSidebar.evidencePanel.meta.pauseAutoLink')
              : t('rightSidebar.evidencePanel.meta.resumeAutoLink') }}
          </button>
        </template>

      </div>
    </div>

    <div v-if="rssItems.length" class="block">
      <div class="block-title">{{ t('rightSidebar.evidencePanel.sections.rssEvidence') }}</div>

      <div class="list">
        <div v-for="(it, i) in rssItems" :key="it.object_ref || it.url || i" class="row">
          <a class="row-main" :href="it.url" target="_blank" rel="noreferrer" :title="it.url || ''">
            <div class="t selectable">{{ it.title || it.url }}</div>
            <div class="q selectable">{{ it.quote || it.excerpt || '' }}</div>

            <div class="sub-row">
              <div class="sub-left muted selectable" :title="subTitle(it)">
                <span>{{ (it.published_at || '').slice(0, 19) }}</span>
                <span v-if="it.feed_id"> · {{ it.feed_id }}</span>
              </div>

              <button
                class="mini"
                type="button"
                :disabled="publishingKey === (it.object_ref || it.url) || !it.object_ref"
                @click.prevent="publishRss(it)"
                :title="it.object_ref
                  ? t('rightSidebar.evidencePanel.rss.publishTitle')
                  : t('rightSidebar.evidencePanel.rss.publishDisabledTitle')"
              >
                {{ publishingKey === (it.object_ref || it.url)
                  ? t('rightSidebar.evidencePanel.rss.publishing')
                  : t('rightSidebar.evidencePanel.rss.publish') }}
              </button>
            </div>
          </a>
        </div>
      </div>

      <div v-if="publishMsg" class="hint">{{ publishMsg }}</div>
    </div>

    <div v-if="marketItems.length" class="block">
      <div class="block-title">{{ t('rightSidebar.evidencePanel.sections.marketEvidence') }}</div>
      <div class="list">
        <div v-for="(it, i) in marketItems" :key="it.listing_id || it.object_ref || i" class="row">
          <div class="row-main">
            <div class="t selectable">{{ it.title || it.object_ref || t('rightSidebar.evidencePanel.market.fallbackTitle') }}</div>
            <div class="q selectable">{{ it.quote || it.object_ref || '' }}</div>
            <div class="sub muted selectable">
              <span v-if="it.peer_id">{{ t('rightSidebar.evidencePanel.market.peer', { peerId: it.peer_id }) }}</span>
              <span v-if="it.listing_id"> · {{ it.listing_id }}</span>
            </div>
          </div>

          <div class="row-actions">
            <button class="mini" type="button" @click="copy(it.object_ref || '')" :disabled="!it.object_ref">
              {{ t('rightSidebar.evidencePanel.market.copyRef') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="localSyncEnabled" class="block">
      <div class="block-title">{{ t('rightSidebar.evidencePanel.sections.localEvidence') }}</div>

      <div v-if="localItems.length" class="local-list">
        <button
          v-for="it in localItems"
          :key="it.key"
          type="button"
          class="local-item selectable"
          :class="{ active: it.key === activeKey }"
          @click="selectLocal(it, { source: 'user_click' })"
          :title="it.quote"
        >
          <div class="local-top">
            <span class="pill pill-lib" :title="t('rightSidebar.evidencePanel.local.libraryTitle', { value: it.library_id })">
              {{ t('rightSidebar.evidencePanel.local.libraryShort') }} {{ it.library_id }}
            </span>
            <span class="pill pill-doc" :title="t('rightSidebar.evidencePanel.local.docTitle', { value: it.doc_id })">
              {{ t('rightSidebar.evidencePanel.local.docShort') }} {{ it.doc_id }}
            </span>
            <span class="pill pill-span" :title="t('rightSidebar.evidencePanel.local.spanTitle', { value: it.span_index })">
              {{ t('rightSidebar.evidencePanel.local.spanShort') }} {{ it.span_index }}
            </span>
          </div>
          <div class="local-quote selectable">{{ it.quote }}</div>
        </button>
      </div>

      <div v-else class="hint muted">
        {{ t('rightSidebar.evidencePanel.local.emptyHint') }}
      </div>

      <EvidenceCard />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { useLibrarySearchStore } from '../../stores/librarySearch'
import EvidenceCard from './EvidenceCard.vue'
import {
  readLocalEvidenceSettings,
  writeLocalEvidenceSettings,
  onSettingsUpdated,
  NISB_LOCAL_EVIDENCE_SYNC_KEY,
  NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY
} from '../../composables/useNisbSettings'

const props = defineProps({
  rssEvidence: { type: Array, default: () => [] },
  marketEvidence: { type: Array, default: () => [] }
})

const { t } = useI18n()
const { callTool } = useMCP()
const librarySearch = useLibrarySearchStore()

const rssItems = computed(() => (Array.isArray(props.rssEvidence) ? props.rssEvidence : []))
const marketItems = computed(() => (Array.isArray(props.marketEvidence) ? props.marketEvidence : []))

const publishingKey = ref('')
const publishMsg = ref('')

const localItems = ref([])
const activeKey = ref('')
const lastLocalSig = ref('')

const localSyncEnabled = ref(true)
const localAutoSelectEnabled = ref(true)

let _off_settings_updated = null
let _local_evt_timer = null
let _local_evt_pending = null

const MAX_LOCAL_ITEMS = 40

function _getGlobalReader() {
  try {
    return window.__nisbReaderState || window.nisbReaderState || null
  } catch {
    return null
  }
}

function _applyLocalEvidenceSettingsFromStorage() {
  const s = readLocalEvidenceSettings()
  localSyncEnabled.value = !!s.sync
  localAutoSelectEnabled.value = !!s.autoselect
  if (!localSyncEnabled.value) localAutoSelectEnabled.value = false

  if (!localSyncEnabled.value) {
    localItems.value = []
    activeKey.value = ''
    lastLocalSig.value = ''
  }
}

function subTitle(it) {
  const a = (it?.published_at || '').slice(0, 19)
  const b = it?.feed_id ? ` · ${it.feed_id}` : ''
  return `${a}${b}`.trim()
}

function _sig(list) {
  return (Array.isArray(list) ? list : [])
    .map((x) => `${x.library_id}|${x.doc_id}|${x.span_index}|${String(x.quote || '').slice(0, 40)}`)
    .join(';;')
}

function _normalizeIncomingLocal(raw, idx) {
  const lib = String(raw?.library_id || '').trim()
  const doc = String(raw?.doc_id || '').trim()
  const span = Number(raw?.span_index)
  const quote = String(raw?.quote || raw?.text || '').trim()

  if (!lib || !doc || !Number.isFinite(span)) return null

  return {
    key: `${lib}::${doc}::${span}::${idx}`,
    library_id: lib,
    doc_id: doc,
    span_index: span,
    quote
  }
}

function _toEvidencePayload(it) {
  return {
    library_id: it.library_id,
    doc_id: it.doc_id,
    span_index: Number(it.span_index),
    chunk_id: null,
    relevance: 0,
    quote: it.quote || '',
    text: it.quote || ''
  }
}

function _applyLocalItems(normalized) {
  const trimmed = normalized.slice(0, MAX_LOCAL_ITEMS)
  localItems.value = trimmed

  const sig = _sig(trimmed)
  lastLocalSig.value = sig

  if (activeKey.value) {
    const still = trimmed.find((x) => x.key === activeKey.value)
    if (!still) activeKey.value = ''
  }
}

function onLocalCitationsEvent(e) {
  if (!localSyncEnabled.value) return

  const arr = Array.isArray(e?.detail?.items) ? e.detail.items : []
  _local_evt_pending = arr

  if (_local_evt_timer) clearTimeout(_local_evt_timer)
  _local_evt_timer = setTimeout(() => {
    const rawArr = _local_evt_pending
    _local_evt_pending = null
    _local_evt_timer = null

    const normalized = (Array.isArray(rawArr) ? rawArr : [])
      .map(_normalizeIncomingLocal)
      .filter(Boolean)

    _applyLocalItems(normalized)
  }, 60)
}

function selectLocal(it, opts = {}) {
  if (!it) return

  const source = String(opts?.source || 'user_click')
  activeKey.value = it.key

  try {
    if (typeof librarySearch.setMode === 'function') librarySearch.setMode('evidence')
    else if ('mode' in librarySearch) librarySearch.mode = 'evidence'
  } catch {
    // ignore
  }

  const lib = it.library_id
  const doc = it.doc_id

  try {
    if (source === 'user_click' && typeof librarySearch.set_context_from_user_click === 'function') {
      librarySearch.set_context_from_user_click({ libraryId: lib, docId: doc, preserveResults: true })
    } else if (typeof librarySearch.setContext === 'function') {
      librarySearch.setContext({ libraryId: lib, docId: doc, preserveResults: true, source })
    }
  } catch {
    // ignore
  }

  const payload = _toEvidencePayload(it)
  if (typeof librarySearch.selectItem === 'function') {
    librarySearch.selectItem(payload)
  } else {
    try {
      librarySearch.selected = payload
    } catch {
      // ignore
    }
  }

  const openDetail = {
    libraryId: lib,
    docId: doc,
    spanIndex: Number(it.span_index),
    reader: _getGlobalReader()
  }

  try {
    window.__nisb_last_library_doc_open = openDetail
  } catch {
    // ignore
  }

  window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: openDetail }))
}

function toggleLocalAutoSelect() {
  if (!localSyncEnabled.value) return

  const next = !localAutoSelectEnabled.value
  localAutoSelectEnabled.value = next

  writeLocalEvidenceSettings({
    sync: !!localSyncEnabled.value,
    autoselect: !!localAutoSelectEnabled.value
  })
}

onMounted(() => {
  _applyLocalEvidenceSettingsFromStorage()

  _off_settings_updated = onSettingsUpdated((e) => {
    const d = e?.detail || {}
    const k = String(d.key || '')
    if (k !== NISB_LOCAL_EVIDENCE_SYNC_KEY && k !== NISB_LOCAL_EVIDENCE_AUTOSELECT_KEY) return
    _applyLocalEvidenceSettingsFromStorage()
  })

  window.addEventListener('nisb-chat-local-citations', onLocalCitationsEvent)
})

onUnmounted(() => {
  window.removeEventListener('nisb-chat-local-citations', onLocalCitationsEvent)

  try {
    if (typeof _off_settings_updated === 'function') _off_settings_updated()
  } catch {
    // ignore
  }

  try {
    if (_local_evt_timer) clearTimeout(_local_evt_timer)
  } catch {
    // ignore
  } finally {
    _local_evt_timer = null
    _local_evt_pending = null
  }
})

async function publishRss(it) {
  publishMsg.value = ''
  const object_ref = it?.object_ref
  if (!object_ref) {
    publishMsg.value = t('rightSidebar.evidencePanel.publish.missingObjectRef')
    return
  }
  publishingKey.value = object_ref
  try {
    const res = await callTool('nisb_market_publish', {
      object_ref,
      title: it?.title || '',
      tags: ['rss'],
      visibility: 'private',
      payload: { url: it?.url || '', published_at: it?.published_at || '' }
    })
    publishMsg.value = res?.success
      ? t('rightSidebar.evidencePanel.publish.success')
      : t('rightSidebar.evidencePanel.publish.failed', { message: res?.message || '' })
  } catch (e) {
    publishMsg.value = t('rightSidebar.evidencePanel.publish.failed', { message: e?.message || String(e) })
  } finally {
    publishingKey.value = ''
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(String(text || ''))
  } catch {
    // ignore
  }
}
</script>

<style scoped>
.panel {
  min-width: 0;
  display: grid;
  gap: 0.72rem;
  padding: 0.7rem 0.65rem 0.85rem;
  overflow-x: hidden;
}

.head {
  min-width: 0;
  display: grid;
  gap: 0.35rem;
  padding: 0.62rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 16%, var(--line));
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 48%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 64%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.meta {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 690;
  line-height: 1.35;
}

.meta > span:not(.dot) {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
}

.dot {
  opacity: 0.58;
}

.block {
  min-width: 0;
  display: grid;
  gap: 0.48rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
}

.block-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.block-title::before {
  content: '';
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 10%, transparent);
  opacity: 0.82;
}

.list,
.local-list {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
}

.row {
  min-width: 0;
  display: grid;
  gap: 0.45rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 13px;
  padding: 0.58rem 0.62rem;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.row:hover {
  border-color: color-mix(in srgb, var(--selected) 32%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.08);
  transform: translateX(1px);
}

.row-main {
  min-width: 0;
  display: block;
  color: inherit;
  text-decoration: none;
}

.t {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.83rem;
  font-weight: 780;
  line-height: 1.38;
  white-space: normal;
  word-break: normal;
  overflow-wrap: break-word;
}

.q {
  min-width: 0;
  margin-top: 0.28rem;
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 520;
  line-height: 1.45;
  white-space: normal;
  word-break: normal;
  overflow-wrap: break-word;
}

.sub,
.sub-row {
  min-width: 0;
  margin-top: 0.35rem;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 640;
  line-height: 1.32;
}

.sub-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.sub-left {
  flex: 1 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.35rem;
  min-width: 0;
}

.muted {
  color: var(--text-secondary);
  opacity: 1;
}

.hint {
  min-width: 0;
  padding: 0.52rem 0.58rem;
  border: 1px dashed color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 620;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.mini {
  flex: 0 0 auto;
  min-height: 25px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 0.52rem;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  user-select: none;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.mini:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  color: var(--selected);
}

.mini:active:not(:disabled) {
  transform: translateY(1px);
}

.mini:disabled {
  opacity: 0.56;
  cursor: not-allowed;
  filter: saturate(0.78);
}

.mini.ghost {
  min-height: 23px;
  padding: 0 0.48rem;
  border-color: color-mix(in srgb, var(--line) 86%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 64%, transparent);
  font-size: 0.72rem;
}

.local-item {
  position: relative;
  width: 100%;
  min-width: 0;
  display: grid;
  gap: 0.34rem;
  text-align: left;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.55rem 0.58rem;
  font-family: inherit;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.local-item:hover {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--text-main, var(--text));
  transform: translateX(1px);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.08);
}

.local-item.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 68%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--text-main, var(--text));
}

.local-item.active::before {
  content: '';
  position: absolute;
  left: 0.42rem;
  top: 0.56rem;
  bottom: 0.56rem;
  width: 3px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.local-top {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.32rem;
}

.pill {
  max-width: 100%;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 38%, transparent);
  color: var(--text-secondary);
  padding: 0 0.42rem;
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  overflow-wrap: anywhere;
}

.pill-lib {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.pill-doc {
  max-width: 12.5rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pill-span {
  border-color: color-mix(in srgb, #16a34a 24%, var(--line));
  background: color-mix(in srgb, #16a34a 8%, transparent);
  color: #16a34a;
}

.local-quote {
  min-width: 0;
  color: inherit;
  font-size: 0.79rem;
  font-weight: 560;
  line-height: 1.45;
  white-space: normal;
  word-break: normal;
  overflow-wrap: break-word;
}

.selectable {
  user-select: text;
}

@media (max-width: 420px) {
  .panel {
    padding: 0.58rem 0.5rem 0.7rem;
  }

  .head,
  .block {
    border-radius: 14px;
  }

  .sub-row {
    align-items: stretch;
    flex-direction: column;
    gap: 0.35rem;
  }

  .sub-left {
    white-space: normal;
    overflow-wrap: break-word;
  }

  .row-actions {
    justify-content: stretch;
  }

  .mini {
    flex: 1 1 auto;
  }

  .pill-doc {
    max-width: 100%;
  }
}
</style>

