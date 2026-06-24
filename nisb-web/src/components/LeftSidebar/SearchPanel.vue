<template>
  <div v-if="visible" class="search-panel-overlay" @click.self="close">
    <div
      class="search-panel"
      role="dialog"
      aria-modal="true"
      :aria-label="t('sidebar.search.placeholder')"
    >
      <div class="search-header">
        <div class="search-input-shell">
          <span class="search-icon" aria-hidden="true">🔍</span>
          <input
            ref="searchInput"
            v-model="query"
            type="text"
            class="search-input"
            :placeholder="t('sidebar.search.placeholder')"
            @input="handleSearch"
            @keydown.esc="close"
            @keydown.enter.prevent="triggerSearchNow"
          />
        </div>

        <button
          v-if="debugPanelAvailable"
          class="debug-btn"
          :class="{ active: showDebugPanel }"
          type="button"
          @click="toggleDebugPanel"
          :title="showDebugPanel ? t('sidebar.search.actions.closeDebug') : t('sidebar.search.actions.openDebug')"
        >
          {{ showDebugPanel ? t('sidebar.search.actions.debugOn') : t('sidebar.search.actions.debugOff') }}
        </button>

        <button class="close-btn" type="button" @click="close" :title="t('common.close')">
          ✕
        </button>
      </div>

      <div class="controls-shell">
        <SearchPanelControls
          :model-value="enabledCategories"
          :counts="displayCounts"
          :searching="searching"
          @update:modelValue="applyEnabledCategories"
          @select-all="applySelectAll"
          @select-workspace="applyWorkspacePreset"
          @reset-defaults="resetCategoryDefaults"
        />
      </div>

      <div v-if="searching" class="search-state loading">
        {{ t('sidebar.search.loading') }}
      </div>

      <div v-else-if="!query.trim()" class="search-state placeholder">
        <p>{{ t('sidebar.search.initialTitle') }}</p>
        <p class="hint">{{ t('sidebar.search.initialHint') }}</p>
      </div>

      <div v-else-if="!hasEnabledCategory" class="search-state placeholder">
        <p>{{ t('sidebar.search.noCategoryTitle') }}</p>
        <p class="hint">{{ t('sidebar.search.noCategoryHint') }}</p>
      </div>

      <div v-else-if="totalResults === 0" class="search-state empty">
        <p>{{ t('sidebar.search.emptyTitle') }}</p>
        <p class="hint">{{ t('sidebar.search.emptyHint') }}</p>

        <div v-if="showDebugPanel && debugMeta.enabled" class="debug-panel compact">
          <div class="debug-panel-header">
            <span class="debug-title">{{ t('sidebar.search.debug.infoTitle') }}</span>
            <button class="debug-toggle" type="button" @click="debugOpen = !debugOpen">
              {{ debugOpen ? t('sidebar.search.actions.collapse') : t('sidebar.search.actions.expand') }}
            </button>
          </div>

          <div v-if="debugOpen" class="debug-grid">
            <div class="debug-item">
              <span class="debug-key">status</span>
              <span class="debug-value">{{ debugMeta.status || '-' }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">message</span>
              <span class="debug-value">{{ debugMeta.message || '-' }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">sync.mode</span>
              <span class="debug-value">{{ debugMeta.sync_mode || '-' }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">took_ms</span>
              <span class="debug-value">{{ debugMeta.took_ms }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">open</span>
              <span class="debug-value">{{ debugMeta.open_elapsed_ms }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">sync</span>
              <span class="debug-value">{{ debugMeta.sync_elapsed_ms }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">query</span>
              <span class="debug-value">{{ debugMeta.query_elapsed_ms }}</span>
            </div>
            <div class="debug-item">
              <span class="debug-key">selected_index_total</span>
              <span class="debug-value">{{ debugMeta.selected_index_total }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="search-results">
        <div
          v-if="normalizedQueryText && normalizedQueryText !== query.trim()"
          class="search-status subtle"
        >
          {{ t('sidebar.search.normalizedQuery', { query: normalizedQueryText }) }}
        </div>

        <div v-if="showDebugPanel && debugMeta.enabled" class="debug-panel">
          <div class="debug-panel-header">
            <div class="debug-title-wrap">
              <div class="debug-title">{{ t('sidebar.search.debug.devObservation') }}</div>
              <div class="debug-subtitle">
                total={{ totalResults }} · sync.mode={{ debugMeta.sync_mode || '-' }} · mode={{ debugMeta.mode || '-' }}
              </div>
            </div>
            <button class="debug-toggle" type="button" @click="debugOpen = !debugOpen">
              {{ debugOpen ? t('sidebar.search.actions.collapseDebug') : t('sidebar.search.actions.expandDebug') }}
            </button>
          </div>

          <div v-if="debugOpen" class="debug-content">
            <div class="debug-grid">
              <div class="debug-item">
                <span class="debug-key">status</span>
                <span class="debug-value">{{ debugMeta.status || '-' }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">message</span>
                <span class="debug-value">{{ debugMeta.message || '-' }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">took_ms</span>
                <span class="debug-value">{{ debugMeta.took_ms }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">sync.mode</span>
                <span class="debug-value">{{ debugMeta.sync_mode || '-' }}</span>
              </div>

              <div class="debug-item">
                <span class="debug-key">open_elapsed_ms</span>
                <span class="debug-value">{{ debugMeta.open_elapsed_ms }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">sync_elapsed_ms</span>
                <span class="debug-value">{{ debugMeta.sync_elapsed_ms }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">query_elapsed_ms</span>
                <span class="debug-value">{{ debugMeta.query_elapsed_ms }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">selected_index_total</span>
                <span class="debug-value">{{ debugMeta.selected_index_total }}</span>
              </div>

              <div class="debug-item">
                <span class="debug-key">group.chat</span>
                <span class="debug-value">{{ debugMeta.group_counts.chat }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">group.dirs</span>
                <span class="debug-value">{{ debugMeta.group_counts.dirs }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">group.files</span>
                <span class="debug-value">{{ debugMeta.group_counts.files }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">group.library</span>
                <span class="debug-value">{{ debugMeta.group_counts.library }}</span>
              </div>

              <div class="debug-item">
                <span class="debug-key">used_fast_path</span>
                <span class="debug-value">{{ debugMeta.used_fast_path }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">fallback_to_db_open</span>
                <span class="debug-value">{{ debugMeta.fallback_to_db_open }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">busy_timeout</span>
                <span class="debug-value">{{ debugMeta.busy_timeout }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">mmap_size</span>
                <span class="debug-value">{{ debugMeta.mmap_size }}</span>
              </div>

              <div class="debug-item">
                <span class="debug-key">journal_mode</span>
                <span class="debug-value">{{ debugMeta.journal_mode || '-' }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">temp_store</span>
                <span class="debug-value">{{ debugMeta.temp_store || '-' }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">db_path</span>
                <span class="debug-value debug-path">{{ debugMeta.db_path || '-' }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-key">query_tokens</span>
                <span class="debug-value debug-path">{{ debugMeta.query_tokens.join(', ') || '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="results.chat.length > 0" class="result-section chat-section">
          <div class="section-head">
            <div class="section-title">{{ t('sidebar.search.sections.chat', { count: results.chat.length }) }}</div>
            <div class="section-count">{{ showCount.chat }}/{{ results.chat.length }}</div>
          </div>

          <div class="results-list">
            <div
              v-for="item in visibleChat"
              :key="item.conv_id"
              class="result-item"
              @click="openConversation(item)"
            >
              <div class="result-title">{{ item.title || t('sidebar.search.results.newConversation') }}</div>
              <div class="result-meta">
                <span>{{ formatDate(item.created_at) }}</span>
                <span>{{ t('sidebar.search.results.messageCount', { count: item.turn_count }) }}</span>
                <span v-if="item.match_type" class="match-badge">
                  {{ chatMatchLabel(item) }}
                </span>
              </div>
              <div v-if="item.snippet" class="result-snippet">{{ item.snippet }}</div>
            </div>
          </div>

          <div v-if="hasMoreChat" class="section-expand">
            <button class="expand-btn" type="button" @click="loadMoreChat" :disabled="searching">
              {{ t('sidebar.search.actions.expandChat', { count: PAGE_SIZE }) }}
            </button>
            <span class="count">{{ showCount.chat }}/{{ results.chat.length }}</span>
          </div>
        </div>

        <div v-if="results.dirs.length > 0" class="result-section dir-section">
          <div class="section-head">
            <div class="section-title">{{ t('sidebar.search.sections.dirs', { count: results.dirs.length }) }}</div>
            <div class="section-count">{{ showCount.dirs }}/{{ results.dirs.length }}</div>
          </div>

          <div class="results-list">
            <div
              v-for="item in visibleDirs"
              :key="item.__key"
              class="result-item"
              @click="openDirectory(item)"
            >
              <div class="result-title">
                {{ item.dirname || getBasename(item.path) || t('sidebar.search.results.unnamedDirectory') }}
                <span class="title-subtle">{{ t('sidebar.search.results.focusToFiles') }}</span>
              </div>
              <div class="result-meta">
                <span class="path">{{ item.path }}</span>
                <span v-if="item.match_type" class="match-badge">
                  {{ dirMatchLabel(item) }}
                </span>
              </div>
              <div v-if="item.snippet" class="result-snippet">{{ item.snippet }}</div>
            </div>
          </div>

          <div v-if="hasMoreDirs" class="section-expand">
            <button class="expand-btn" type="button" @click="loadMoreDirs" :disabled="searching">
              {{ t('sidebar.search.actions.expandDirs', { count: PAGE_SIZE }) }}
            </button>
            <span class="count">{{ showCount.dirs }}/{{ results.dirs.length }}</span>
          </div>
        </div>

        <div v-if="mergedFiles.length > 0" class="result-section file-section">
          <div class="section-head">
            <div class="section-title">{{ t('sidebar.search.sections.files', { count: mergedFiles.length }) }}</div>
            <div class="section-count">{{ showCount.files }}/{{ mergedFiles.length }}</div>
          </div>

          <div class="results-list">
            <div
              v-for="item in visibleFiles"
              :key="item.__key"
              class="result-item"
              @click="openDocument(item)"
            >
              <div class="result-title">{{ item.filename }}</div>
              <div class="result-meta">
                <span class="path">{{ getPathShort(item.path) }}</span>
                <span v-if="item.match_type" class="match-badge">
                  {{ fileMatchLabel(item) }}
                </span>
                <span v-if="item.__sourceLabel" class="source-tag">{{ item.__sourceLabel }}</span>
              </div>
              <div v-if="item.snippet" class="result-snippet">{{ item.snippet }}</div>
            </div>
          </div>

          <div v-if="hasMoreFiles" class="section-expand">
            <button class="expand-btn" type="button" @click="loadMoreFiles" :disabled="searching">
              {{ t('sidebar.search.actions.expandFiles', { count: PAGE_SIZE }) }}
            </button>
            <span class="count">{{ showCount.files }}/{{ mergedFiles.length }}</span>
          </div>
        </div>

        <div v-if="results.library.length > 0" class="result-section library-section">
          <div class="section-head">
            <div class="section-title">{{ t('sidebar.search.sections.library', { count: results.library.length }) }}</div>
            <div class="section-count">{{ showCount.library }}/{{ results.library.length }}</div>
          </div>

          <div class="results-list">
            <div
              v-for="item in visibleLibrary"
              :key="libraryKey(item)"
              class="result-item"
              @click="openLibraryOrBook(item)"
            >
              <div class="result-title">
                <template v-if="isLibraryDocHit(item)">
                  {{ item.title || item.filename || item.doc_title || item.doc_id || t('sidebar.search.results.unnamed') }}
                  <span class="library-name"> — {{ item.library_name || item.library_id }}</span>
                </template>
                <template v-else>
                  {{ item.library_name || item.library_id }}
                </template>
              </div>
              <div class="result-meta">
                <span v-if="item.library_id">library_id: {{ item.library_id }}</span>
                <span v-if="isLibraryDocHit(item) && (item.doc_id || item.docId)">doc_id: {{ item.doc_id || item.docId }}</span>
                <span v-if="item.match_type" class="match-badge">
                  {{ libraryMatchLabel(item) }}
                </span>
              </div>
              <div v-if="item.snippet || item.description" class="result-snippet">
                {{ item.snippet || item.description }}
              </div>
            </div>
          </div>

          <div v-if="hasMoreLibrary" class="section-expand">
            <button class="expand-btn" type="button" @click="loadMoreLibrary" :disabled="searching">
              {{ t('sidebar.search.actions.expandLibrary', { count: PAGE_SIZE }) }}
            </button>
            <span class="count">{{ showCount.library }}/{{ results.library.length }}</span>
          </div>
        </div>

        <div v-if="hasMoreAny" class="global-expand">
          <div class="global-expand-main">
            <div class="expand-title">{{ t('sidebar.search.sections.global') }}</div>
            <div class="expand-status">
              {{ showCount.chat }}/{{ results.chat.length }} |
              {{ showCount.dirs }}/{{ results.dirs.length }} |
              {{ showCount.files }}/{{ mergedFiles.length }} |
              {{ showCount.library }}/{{ results.library.length }}
            </div>
          </div>

          <button
            class="expand-btn global"
            type="button"
            @click="loadMoreAll"
            :disabled="searching"
          >
            {{ t('sidebar.search.actions.expandAll', { count: PAGE_SIZE }) }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import SearchPanelControls from './SearchPanelControls.vue'
import { useSearchPanelHelpers } from '../../composables/left_sidebar/search_panel/useSearchPanelHelpers'
import { useSearchPanelSearch } from '../../composables/left_sidebar/search_panel/useSearchPanelSearch'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])
const searchInput = ref(null)
const { t } = useI18n()

const {
  formatDate,
  getBasename,
  getPathShort,
  chatMatchLabel,
  fileMatchLabel,
  dirMatchLabel,
  libraryMatchLabel,
  isLibraryDocHit,
  libraryKey,
  normalizePathValue
} = useSearchPanelHelpers()

const {
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
  hasEnabledCategory,
  debugPanelAvailable,
  showDebugPanel,
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
  cancelPendingAndReset
} = useSearchPanelSearch({
  isVisible: () => props.visible
})

function emit_switch_to_files() {
  window.dispatchEvent(
    new CustomEvent('nisb-left-sidebar-switch-tab', {
      detail: {
        tab: 'files',
        refreshFiles: false
      }
    })
  )
}

function emit_after_files_mount(event_name, detail) {
  nextTick(() => {
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent(event_name, { detail }))
    }, 0)
  })
}

function openConversation(item) {
  if (!item?.conv_id) return
  window.dispatchEvent(new CustomEvent('nisb-open-conversation', {
    detail: { convId: item.conv_id, title: item.title }
  }))
  close()
}

function openDirectory(item) {
  const path = normalizePathValue(item?.path)
  if (!path) return
  emit_switch_to_files()
  emit_after_files_mount('nisb-open-dir', { path })
  close()
}

function openDocument(item) {
  const path = normalizePathValue(item?.path)
  if (!path) return
  emit_switch_to_files()
  emit_after_files_mount('nisb-open-file', {
    path,
    name: item.filename
  })
  close()
}

function openLibraryOrBook(item) {
  const libraryId = item.library_id || item.libraryId
  const libraryName = item.library_name || item.libraryName
  const docId = item.doc_id || item.docId

  if (libraryId && docId) {
    window.dispatchEvent(new CustomEvent('nisb-open-library-doc', {
      detail: { libraryId, docId, libraryName }
    }))
    close()
    return
  }

  if (!libraryId) return

  window.dispatchEvent(new CustomEvent('nisb-open-library', {
    detail: { libraryId, libraryName }
  }))
  close()
}

function close() {
  emit('close')
  query.value = ''
  cancelPendingAndReset()
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      nextTick(() => {
        searchInput.value?.focus()
      })
    } else {
      cancelPendingOnly()
    }
  }
)

onUnmounted(() => {
  cancelPendingOnly()
})
</script>

<style scoped>
.search-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 10vh 18px 18px;
  background:
    radial-gradient(circle at 24% 0%, color-mix(in srgb, var(--selected) 14%, transparent), transparent 34%),
    radial-gradient(circle at 78% 8%, color-mix(in srgb, #16a34a 8%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.26);
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.search-panel {
  width: min(820px, calc(100vw - 36px));
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 88%, transparent)
    );
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.30),
    0 2px 18px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(16px);
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-18px); }
  to { opacity: 1; transform: translateY(0); }
}

.search-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
}

.search-input-shell {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 80%, transparent);
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.search-input-shell:focus-within {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 94%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.search-icon {
  flex: 0 0 auto;
  opacity: 0.82;
  line-height: 1;
}

.search-input {
  flex: 1 1 auto;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.94rem;
  font-weight: 680;
  line-height: 1.35;
}

.search-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 74%, transparent);
  font-weight: 560;
}

.debug-btn,
.close-btn,
.debug-toggle,
.expand-btn {
  font-family: inherit;
}

.debug-btn,
.close-btn {
  flex: 0 0 auto;
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.debug-btn {
  padding: 0 0.74rem;
  font-size: 0.74rem;
  font-weight: 760;
  white-space: nowrap;
}

.close-btn {
  width: 34px;
  height: 34px;
  font-size: 1rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.debug-btn:hover,
.close-btn:hover {
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.debug-btn:active,
.close-btn:active,
.expand-btn:active {
  transform: translateY(1px);
}

.debug-btn.active {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 62%, var(--editor-bg));
  color: var(--selected);
}

.controls-shell {
  flex: 0 0 auto;
  padding: 10px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 36%, transparent);
}

.search-state {
  flex: 1 1 auto;
  min-height: 220px;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 6px;
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}

.search-state p {
  margin: 0;
  max-width: 560px;
  overflow-wrap: break-word;
}

.search-state p:first-child {
  color: var(--text-main, var(--text));
  font-size: 0.95rem;
  font-weight: 760;
  line-height: 1.45;
}

.search-state.loading {
  color: var(--selected);
}

.hint {
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
  opacity: 0.86;
}

.search-results {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 12px;
  overflow-y: auto;
  padding: 12px;
  background:
    linear-gradient(180deg, color-mix(in srgb, #fff 2%, transparent), transparent 120px);
  scrollbar-width: thin;
}

.search-status.subtle {
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 60%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.debug-panel {
  padding: 11px;
  border: 1px dashed color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 14px;
  background: color-mix(in srgb, var(--selected-bg) 22%, var(--editor-bg));
}

.debug-panel.compact {
  width: min(560px, 100%);
  margin-top: 12px;
  text-align: left;
}

.debug-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.debug-title-wrap {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.debug-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.debug-subtitle {
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.debug-toggle {
  flex: 0 0 auto;
  min-height: 30px;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--selected-bg) 45%, var(--editor-bg));
  color: var(--selected);
  cursor: pointer;
  font-size: 0.74rem;
  font-weight: 740;
  white-space: nowrap;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease;
}

.debug-toggle:hover {
  background: color-mix(in srgb, var(--selected-bg) 68%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
}

.debug-content {
  margin-top: 10px;
}

.debug-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.debug-item {
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
}

.debug-key {
  display: block;
  margin-bottom: 3px;
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.debug-value {
  display: block;
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.75rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.debug-path {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

.result-section {
  --section-color: var(--selected);
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--section-color) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--section-color) 8%, transparent) 0%,
      color-mix(in srgb, var(--editor-bg) 70%, transparent) 62%
    );
  box-shadow: inset 0 1px 0 color-mix(in srgb, #fff 4%, transparent);
}

.chat-section {
  --section-color: #3b82f6;
}

.dir-section {
  --section-color: #d97706;
}

.file-section {
  --section-color: #16a34a;
}

.library-section {
  --section-color: #a855f7;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.section-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: 0.01em;
  overflow-wrap: break-word;
}

.section-count,
.count,
.expand-status {
  color: var(--text-secondary);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.72rem;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.results-list {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.result-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.result-item:hover {
  border-color: color-mix(in srgb, var(--section-color) 34%, var(--line));
  background: color-mix(in srgb, var(--section-color) 7%, var(--editor-bg));
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.13);
  transform: translateX(3px);
}

.result-title {
  min-width: 0;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.28rem;
  margin-bottom: 4px;
  color: var(--text-main, var(--text));
  font-size: 0.9rem;
  font-weight: 760;
  line-height: 1.38;
  overflow-wrap: break-word;
}

.title-subtle,
.library-name {
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 620;
  line-height: 1.35;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  min-width: 0;
  margin-bottom: 3px;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.4;
}

.result-meta span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.path {
  flex: 1 1 180px;
  min-width: 0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-snippet {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.match-badge,
.source-tag {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.match-badge {
  border: 1px solid color-mix(in srgb, var(--section-color) 30%, var(--line));
  background: color-mix(in srgb, var(--section-color) 8%, transparent);
  color: var(--section-color);
}

.source-tag {
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 64%, transparent);
  color: var(--text-secondary);
}

.section-expand,
.global-expand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.section-expand {
  padding-top: 2px;
}

.expand-btn {
  flex: 1 1 auto;
  min-height: 32px;
  padding: 0 0.75rem;
  border: 1px solid color-mix(in srgb, var(--section-color) 34%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--section-color) 8%, var(--editor-bg));
  color: var(--section-color);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease,
    box-shadow 0.16s ease;
}

.expand-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--section-color) 14%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--section-color) 52%, var(--line));
}

.expand-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  transform: none;
}

.global-expand {
  justify-content: space-between;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 38%, transparent),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
}

.global-expand-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.expand-title {
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 780;
  line-height: 1.35;
}

.expand-btn.global {
  flex: 0 0 auto;
  min-width: 160px;
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected) 88%, #1f2937);
  color: #fff;
  box-shadow: 0 6px 16px color-mix(in srgb, var(--selected) 18%, transparent);
}

.expand-btn.global:hover:not(:disabled) {
  background: var(--selected);
  color: #fff;
  transform: translateY(-1px);
}

@media (max-width: 720px) {
  .search-panel-overlay {
    align-items: stretch;
    padding: 0;
  }

  .search-panel {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

  .search-header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 9px;
  }

  .search-input-shell {
    grid-column: 1 / -1;
  }

  .debug-btn {
    width: 100%;
  }

  .debug-grid {
    grid-template-columns: 1fr;
  }

  .debug-panel-header,
  .section-head,
  .section-expand,
  .global-expand {
    display: grid;
    grid-template-columns: 1fr;
  }

  .expand-btn,
  .expand-btn.global {
    width: 100%;
    min-width: 0;
    white-space: normal;
  }

  .path {
    white-space: normal;
  }
}

@media (max-width: 420px) {
  .search-header,
  .controls-shell,
  .search-results {
    padding-left: 10px;
    padding-right: 10px;
  }

  .result-section {
    padding: 10px;
  }

  .debug-btn,
  .close-btn {
    width: 100%;
  }

  .close-btn {
    height: 34px;
  }
}
</style>
