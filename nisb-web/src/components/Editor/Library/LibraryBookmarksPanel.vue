<template>
  <div class="panel">
    <div class="panel-head">
      <div class="head-text">
        <div class="title">{{ t('library.center.bookmarksPanel.title') }}</div>
        <div class="sub">{{ t('library.center.bookmarksPanel.subtitle') }}</div>
      </div>

      <div class="head-actions">
        <span class="count-chip mono">{{ items.length }}</span>
        <button class="ghost-btn compact" :disabled="loading" @click="emit('refresh')" type="button">
          {{ t('library.center.bookmarksPanel.refresh') }}
        </button>
        <button class="ghost-btn compact" :disabled="loading || !canLoadMore" @click="emit('loadMore')" type="button">
          {{ t('library.center.bookmarksPanel.loadMore') }}
        </button>
      </div>
    </div>

    <div class="toolbar">
      <div class="seg">
        <button class="seg-btn" :class="{ active: typeFilter === 'all' }" @click="emit('update:typeFilter', 'all')" type="button">
          {{ t('library.center.bookmarksPanel.filters.type.all') }}
        </button>
        <button
          class="seg-btn"
          :class="{ active: typeFilter === 'bookmark' }"
          @click="emit('update:typeFilter', 'bookmark')"
          type="button"
        >
          {{ t('library.center.bookmarksPanel.filters.type.bookmark') }}
        </button>
        <button
          class="seg-btn"
          :class="{ active: typeFilter === 'annotation' }"
          @click="emit('update:typeFilter', 'annotation')"
          type="button"
        >
          {{ t('library.center.bookmarksPanel.filters.type.annotation') }}
        </button>
      </div>

      <div class="filter-grid">
        <select
          class="nisb-select library-select"
          :value="libraryFilter"
          @change="onLibChange"
          :title="t('library.center.bookmarksPanel.filters.libraryTitle')"
        >
          <option value="">{{ t('library.center.bookmarksPanel.filters.allLibraries') }}</option>
          <option v-for="id in libraryOptions" :key="id" :value="id">{{ id }}</option>
        </select>

        <input
          class="nisb-input"
          :value="query"
          @input="emit('update:query', $event.target.value)"
          :placeholder="t('library.center.bookmarksPanel.filters.queryPlaceholder')"
        />

        <select
          class="nisb-select range-select"
          :value="timeRange"
          @change="onTimeChange"
          :title="t('library.center.bookmarksPanel.filters.timeRangeTitle')"
        >
          <option value="all">{{ t('library.center.bookmarksPanel.filters.timeRange.all') }}</option>
          <option value="30d">{{ t('library.center.bookmarksPanel.filters.timeRange.30d') }}</option>
          <option value="7d">{{ t('library.center.bookmarksPanel.filters.timeRange.7d') }}</option>
        </select>
      </div>
    </div>

    <div class="content">
      <div v-if="loading" class="tip">{{ t('library.center.bookmarksPanel.loading') }}</div>
      <div v-else-if="!items || !items.length" class="tip">{{ t('library.center.bookmarksPanel.empty') }}</div>

      <div v-else class="list">
        <article v-for="it in items" :key="it.key" class="item">
          <span class="row-accent"></span>

          <div class="main" @click="jumpLocal(it)">
            <div class="line1">
              <span class="kind">{{ kindIcon(it.kind) }}</span>

              <span v-if="it.kind === 'evidence'" class="pill score">
                {{ t('library.center.bookmarksPanel.score', { score: it.scoreText }) }}
              </span>
              <span v-else class="pill">{{ kindLabel(it.kind) }}</span>

              <span class="dot">·</span>
              <span class="docTitle" :title="it.docTitle || it.docId">{{ it.docTitle || it.docId }}</span>
              <span class="dot">·</span>
              <span class="lib mono" :title="it.libraryId">{{ it.libraryId }}</span>
              <span class="dot">·</span>
              <span class="span-chip mono">{{ t('library.center.bookmarksPanel.span', { index: it.spanIndex }) }}</span>
            </div>

            <div class="line2">{{ it.preview }}</div>

            <div class="line3">
              <span class="muted mono">{{ it.docId }}</span>
              <span class="dot">·</span>
              <span class="muted">{{ it.createdAtLocal || it.createdAt }}</span>
            </div>
          </div>

          <div class="actions" :aria-label="t('library.center.bookmarksPanel.actionsAriaLabel')">
            <button class="mini-btn" @click.stop="jumpLocal(it)" type="button">
              {{ t('library.center.bookmarksPanel.actions.jump') }}
            </button>
            <button class="mini-btn" @click.stop="openToolsLocal(it)" type="button">
              {{ t('library.center.bookmarksPanel.actions.tools') }}
            </button>
            <button class="mini-btn" @click.stop="copyItemLocal(it)" type="button">
              {{ t('library.center.bookmarksPanel.actions.copy') }}
            </button>

            <button v-if="it.kind === 'evidence'" class="mini-btn" @click.stop="emit('convertToBookmark', it)" type="button">
              {{ t('library.center.bookmarksPanel.actions.convertToBookmark') }}
            </button>
            <button v-if="it.kind === 'evidence'" class="mini-btn" @click.stop="emit('convertToAnnotation', it)" type="button">
              {{ t('library.center.bookmarksPanel.actions.convertToAnnotation') }}
            </button>

            <button
              v-if="it.canDelete"
              class="mini-btn danger"
              @click.stop="emit('deleteItem', it)"
              type="button"
              :title="t('library.center.bookmarksPanel.actions.delete')"
            >
              {{ t('library.center.bookmarksPanel.actions.delete') }}
            </button>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  typeFilter: { type: String, default: 'all' },
  timeRange: { type: String, default: 'all' },
  query: { type: String, default: '' },
  libraryFilter: { type: String, default: '' },
  libraryOptions: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  canLoadMore: { type: Boolean, default: false }
})

const emit = defineEmits([
  'update:typeFilter',
  'update:timeRange',
  'update:query',
  'update:libraryFilter',
  'refresh',
  'loadMore',
  'jump',
  'openTools',
  'copyItem',
  'deleteItem',
  'convertToBookmark',
  'convertToAnnotation'
])

const { t } = useI18n()

function kindIcon(kind) {
  if (kind === 'bookmark') return '🔖'
  if (kind === 'annotation') return '💬'
  if (kind === 'evidence') return '🧠'
  return '•'
}

function kindLabel(kind) {
  if (kind === 'bookmark') return t('library.center.bookmarksPanel.kind.bookmark')
  if (kind === 'annotation') return t('library.center.bookmarksPanel.kind.annotation')
  if (kind === 'evidence') return t('library.center.bookmarksPanel.kind.evidence')
  return String(kind || '')
}

function onLibChange(e) {
  emit('update:libraryFilter', e?.target?.value ?? '')
}

function onTimeChange(e) {
  emit('update:timeRange', e?.target?.value ?? 'all')
}

function _s(v) {
  return String(v ?? '').trim()
}

function _n(v) {
  const x = Number(v)
  return Number.isFinite(x) ? x : null
}

function _spanIndexOf(it) {
  return _n(it?.spanIndex) ?? _n(it?.span_index) ?? 0
}

function _buildOpenPayload(it) {
  return {
    libraryId: _s(it?.libraryId || props.libraryFilter || it?.library_id),
    docId: _s(it?.docId || it?.doc_id),
    spanIndex: Number(_spanIndexOf(it) || 0),
    reader: it?.reader || window.nisbReaderState || null
  }
}

function dispatchOpenLibraryDocStable(payload) {
  if (!payload?.libraryId || !payload?.docId) return

  try {
    if (payload.reader) window.nisbReaderState = payload.reader
  } catch {}

  const fire = () => {
    try {
      window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: payload }))
    } catch {}
  }

  fire()
  setTimeout(fire, 60)
  setTimeout(fire, 220)
  setTimeout(fire, 700)
}

function jumpLocal(it) {
  emit('jump', it)
  const payload = _buildOpenPayload(it)
  dispatchOpenLibraryDocStable(payload)
}

function openToolsLocal(it) {
  emit('openTools', it)

  const payload = _buildOpenPayload(it)
  dispatchOpenLibraryDocStable(payload)

  const fireTools = () => {
    try {
      window.dispatchEvent(new CustomEvent('nisb-span-artifacts-open', { detail: payload }))
    } catch {}
  }

  fireTools()
  setTimeout(fireTools, 120)
  setTimeout(fireTools, 320)
  setTimeout(fireTools, 900)
}

async function copyItemLocal(it) {
  emit('copyItem', it)

  try {
    const txt = JSON.stringify(it ?? {}, null, 2)
    await navigator.clipboard.writeText(txt)
  } catch {}
}
</script>

<style scoped>
.panel {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: block;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 92% 0%, rgba(22, 163, 74, 0.06), transparent 32%),
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
  pointer-events: auto;
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
  min-width: 0;
  min-height: 54px;
  box-sizing: border-box;
  padding: 0.72rem 0.82rem 0.64rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
  display: grid;
  grid-template-columns: minmax(0, 1fr) max-content;
  align-items: center;
  gap: 0.72rem;
}

.head-text {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.88rem;
  font-weight: 820;
  line-height: 1.22;
  overflow-wrap: break-word;
}

.sub {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.34;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.head-actions {
  min-width: 0;
  display: inline-grid;
  grid-auto-flow: column;
  grid-auto-columns: max-content;
  align-items: center;
  justify-content: end;
  gap: 0.36rem;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.head-actions::-webkit-scrollbar {
  display: none;
}

.count-chip,
.pill,
.span-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  max-width: 100%;
}

.count-chip {
  flex: 0 0 auto;
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 36%, var(--editor-bg));
  color: var(--selected);
}

.toolbar {
  min-width: 0;
  box-sizing: border-box;
  padding: 0.62rem 0.72rem 0.66rem;
  display: grid;
  grid-template-columns: minmax(196px, 0.64fr) minmax(0, 1.36fr);
  gap: 0.52rem;
  align-items: center;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.filter-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(120px, 0.82fr) minmax(168px, 1.18fr) minmax(104px, 0.52fr);
  gap: 0.42rem;
  align-items: center;
}

.seg {
  min-width: 0;
  display: inline-flex;
  max-width: 100%;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 13px;
  overflow: hidden;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.seg-btn {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 35px;
  box-sizing: border-box;
  padding: 0 0.64rem;
  border: 0;
  border-right: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.seg-btn:last-child {
  border-right: 0;
}

.seg-btn:hover,
.seg-btn:focus-visible {
  color: var(--selected);
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  outline: none;
}

.seg-btn.active {
  color: var(--selected);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
}

.nisb-select,
.nisb-input {
  width: 100%;
  min-width: 0;
  min-height: 35px;
  box-sizing: border-box;
  padding: 0.46rem 0.6rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  line-height: 1.35;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
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

.ghost-btn {
  flex: 0 0 auto;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
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
  line-height: 1;
  white-space: nowrap;
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

.ghost-btn.compact {
  min-height: 30px;
  padding: 0 0.58rem;
  font-size: 0.72rem;
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

.content {
  min-width: 0;
  min-height: 0;
  overflow: visible;
}

.tip {
  box-sizing: border-box;
  margin: 0.86rem;
  padding: 1.05rem 0.9rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.list {
  min-width: 0;
  min-height: 100%;
  box-sizing: border-box;
  padding: 0.76rem;
  display: grid;
  align-content: start;
  gap: 0.58rem;
  overflow: visible;
}

.item {
  position: relative;
  min-width: 0;
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr);
  gap: 0.68rem;
  padding: 0.72rem 0.76rem;
  border: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 5%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
  pointer-events: auto;
}

.item:hover,
.item:focus-within {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 46%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 14px 26px rgba(0, 0, 0, 0.08);
}

.row-accent {
  grid-row: 1 / span 2;
  width: 4px;
  min-height: 100%;
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected) 52%, var(--line)),
      color-mix(in srgb, #16a34a 38%, var(--line))
    );
  opacity: 0.62;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease;
}

.item:hover .row-accent,
.item:focus-within .row-accent {
  opacity: 1;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.main {
  min-width: 0;
  cursor: pointer;
}

.line1 {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.36rem;
  color: var(--text-main, var(--text));
  flex-wrap: wrap;
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.36;
}

.item:hover .line1,
.item:focus-within .line1 {
  color: var(--selected);
}

.kind {
  flex: 0 0 auto;
  line-height: 1;
}

.pill.score {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, var(--editor-bg));
  color: var(--selected);
}

.dot {
  opacity: 0.68;
  flex: 0 0 auto;
}

.docTitle,
.lib {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.docTitle {
  max-width: min(34rem, 100%);
}

.lib {
  max-width: min(16rem, 100%);
  color: var(--text-secondary);
}

.span-chip {
  min-height: 22px;
  padding: 0 0.46rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 62%, transparent);
  font-size: 0.68rem;
}

.line2 {
  margin-top: 0.46rem;
  color: var(--text-secondary);
  font-size: 0.81rem;
  line-height: 1.48;
  white-space: normal;
  overflow-wrap: break-word;
}

.line3 {
  margin-top: 0.42rem;
  min-width: 0;
  display: flex;
  gap: 0.36rem;
  align-items: center;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.35;
  flex-wrap: wrap;
}

.muted {
  min-width: 0;
  max-width: min(28rem, 100%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  grid-column: 2;
  min-width: 0;
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  flex-wrap: wrap;
  align-items: center;
  pointer-events: auto;
}

.mini-btn {
  min-height: 30px;
  max-width: 100%;
  box-sizing: border-box;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  pointer-events: auto;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.mini-btn:hover,
.mini-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 56%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.mini-btn:active {
  transform: translateY(1px);
}

.mini-btn.danger {
  border-color: rgba(239, 68, 68, 0.36);
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.08),
      color-mix(in srgb, var(--editor-bg) 52%, transparent)
    );
  color: #ef4444;
}

.mini-btn.danger:hover,
.mini-btn.danger:focus-visible {
  border-color: rgba(239, 68, 68, 0.58);
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.15),
      color-mix(in srgb, var(--editor-bg) 52%, transparent)
    );
  color: #ef4444;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@container (max-width: 760px) {
  .panel-head {
    grid-template-columns: minmax(0, 1fr) max-content;
    gap: 0.52rem;
    padding: 0.66rem 0.72rem 0.58rem;
  }

  .sub {
    display: none;
  }

  .head-actions {
    gap: 0.3rem;
  }

  .ghost-btn.compact {
    min-height: 28px;
    padding: 0 0.5rem;
    font-size: 0.7rem;
  }

  .count-chip {
    min-height: 22px;
    padding: 0 0.48rem;
  }

  .toolbar {
    grid-template-columns: 1fr;
    padding: 0.58rem 0.68rem 0.62rem;
  }

  .filter-grid {
    grid-template-columns: minmax(120px, 0.8fr) minmax(160px, 1.2fr);
  }

  .range-select {
    grid-column: 1 / -1;
  }
}

@container (max-width: 520px) {
  .panel-head {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .head-actions {
    justify-content: start;
    width: 100%;
    max-width: 100%;
  }

  .filter-grid {
    grid-template-columns: 1fr;
  }

  .seg,
  .nisb-select,
  .nisb-input,
  .ghost-btn {
    width: 100%;
  }

  .seg-btn {
    flex: 1;
  }

  .item {
    grid-template-columns: 4px minmax(0, 1fr);
  }

  .actions {
    justify-content: flex-start;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
    gap: 0.4rem;
  }

  .mini-btn {
    width: 100%;
    text-align: center;
    justify-content: center;
  }
}

@container (max-width: 380px) {
  .head-actions {
    grid-auto-flow: row;
    grid-template-columns: auto 1fr 1fr;
  }

  .ghost-btn.compact {
    width: 100%;
  }

  .title {
    font-size: 0.84rem;
  }

  .mini-btn {
    white-space: normal;
    line-height: 1.15;
    padding: 0.32rem 0.45rem;
  }
}
</style>
