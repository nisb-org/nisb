<template>
  <div class="search-section-wrapper">
    <div class="search-controls">
      <div class="tabs-row">
        <div class="tab-group">
          <span class="tab-label">范围</span>
          <button
            v-for="s in scope_options"
            :key="s.value"
            class="scope-tab"
            :class="{ active: current_scope === s.value }"
            @click="set_scope(s.value)"
          >
            {{ s.label }}
          </button>
        </div>

        <div class="tab-group">
          <span class="tab-label">模式</span>
          <button
            v-for="m in mode_options"
            :key="m.value"
            class="scope-tab"
            :class="{ active: current_mode === m.value }"
            @click="set_mode(m.value)"
          >
            {{ m.label }}
          </button>
        </div>
      </div>

      <div class="search-section">
        <input
          v-model="search_model"
          type="text"
          class="search-input"
          :placeholder="search_placeholder"
          @keydown.enter.prevent="on_submit"
        />
        <button class="search-btn" @click="on_submit" :disabled="searching">
          {{ searching ? '⏳' : '🔍' }}
        </button>
        <button
          v-if="search_model"
          class="clear-btn"
          @click="clear_search"
          title="清空"
        >
          ×
        </button>
      </div>

      <div class="search-status-line">
        <span class="status-pill">scope: {{ current_scope }}</span>
        <span class="status-pill">mode: {{ current_mode }}</span>
        <span v-if="search_model_trimmed" class="status-pill text-pill" :title="search_model_trimmed">
          query: {{ search_model_trimmed }}
        </span>
      </div>
    </div>

    <div v-if="normalized_results.length" class="search-results">
      <div class="results-header">
        <span>🔍 搜索结果（{{ normalized_results.length }}）</span>
        <span class="results-meta">{{ current_scope }} · {{ current_mode }}</span>
      </div>

      <div
        v-for="item in normalized_results"
        :key="item._result_key"
        class="result-item"
        @click="emit_result_click(item)"
      >
        <div class="result-score">
          {{ format_score(item._score_value) }}
        </div>

        <div class="result-body">
          <div v-if="item._title" class="result-title" :title="item._title">
            {{ item._title }}
          </div>

          <div class="result-text">
            {{ item._preview_text }}
          </div>

          <details
            v-if="item._full_text && item._full_text !== item._preview_text"
            class="result-details"
            @click.stop
          >
            <summary>展开内容</summary>
            <div class="result-details-body">{{ item._full_text }}</div>
          </details>

          <div class="result-meta-line">
            <span class="meta-main">
              {{ item._doc_label }}
            </span>
            <span v-if="item._location_label" class="meta-sep">·</span>
            <span v-if="item._location_label" class="meta-main">
              {{ item._location_label }}
            </span>
            <span v-if="item._sub_label" class="meta-sep">·</span>
            <span v-if="item._sub_label" class="meta-sub">
              {{ item._sub_label }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="searching" class="empty-tip">
      正在搜索…
    </div>

    <div v-else class="empty-tip muted">
      （暂无搜索结果）
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  searchQuery: { type: String, default: '' },
  searching: { type: Boolean, default: false },
  searchResults: { type: Array, default: () => [] },
  scope: { type: String, default: 'library' }, // doc | library | global
  mode: { type: String, default: 'evidence' } // chunk | evidence
})

const emit = defineEmits([
  'update:searchQuery',
  'update:scope',
  'update:mode',
  'search-submit',
  'result-click'
])

const scope_options = [
  { value: 'doc', label: 'doc' },
  { value: 'library', label: 'library' },
  { value: 'global', label: 'global' }
]

const mode_options = [
  { value: 'chunk', label: 'chunk' },
  { value: 'evidence', label: 'evidence' }
]

const current_scope = ref('library')
const current_mode = ref('evidence')

function _normalize_scope(value) {
  const s = String(value || '').trim().toLowerCase()
  if (s === 'doc' || s === 'library' || s === 'global') return s
  return 'library'
}

function _normalize_mode(value) {
  const s = String(value || '').trim().toLowerCase()
  if (s === 'chunk' || s === 'evidence') return s
  return 'evidence'
}

function _apply_incoming_scope_and_mode(scope_value, mode_value) {
  const raw_scope = String(scope_value || '').trim().toLowerCase()
  const raw_mode = String(mode_value || '').trim().toLowerCase()

  if (raw_scope === 'chunk' || raw_scope === 'evidence') {
    current_mode.value = _normalize_mode(raw_scope)
    if (!raw_mode) return
  }

  current_scope.value = _normalize_scope(raw_scope)
  current_mode.value = _normalize_mode(raw_mode || current_mode.value)
}

watch(
  () => [props.scope, props.mode],
  ([scope_value, mode_value]) => {
    _apply_incoming_scope_and_mode(scope_value, mode_value)
  },
  { immediate: true }
)

const search_model = computed({
  get() {
    return String(props.searchQuery || '')
  },
  set(val) {
    emit('update:searchQuery', String(val || ''))
  }
})

const search_model_trimmed = computed(() => String(search_model.value || '').trim())

const search_placeholder = computed(() => {
  const scope_map = {
    doc: '当前文档',
    library: '当前库',
    global: '全局'
  }
  const mode_map = {
    chunk: 'Chunk',
    evidence: 'Evidence'
  }
  return `在${scope_map[current_scope.value] || '当前库'}内搜索${mode_map[current_mode.value] || 'Evidence'}...`
})

function set_scope(scope) {
  const next = _normalize_scope(scope)
  current_scope.value = next
  emit('update:scope', next)
}

function set_mode(mode) {
  const next = _normalize_mode(mode)
  current_mode.value = next
  emit('update:mode', next)
}

function on_submit() {
  const payload = {
    query: search_model_trimmed.value,
    scope: current_scope.value,
    mode: current_mode.value
  }

  emit('update:scope', current_scope.value)
  emit('update:mode', current_mode.value)
  emit('search-submit', payload)
}

function clear_search() {
  search_model.value = ''
  emit('update:scope', current_scope.value)
  emit('update:mode', current_mode.value)
}

function _pick_text(item) {
  return String(
    item?.quote ||
    item?.excerpt ||
    item?.text ||
    item?.chunk_text ||
    ''
  ).trim()
}

function _pick_title(item) {
  return String(
    item?.doc_title ||
    item?.doc_filename ||
    item?.filename ||
    ''
  ).trim()
}

function _pick_score(item) {
  const score = Number(
    item?.relevance ??
    item?.similarity ??
    item?.score ??
    0
  )
  return Number.isFinite(score) ? score : 0
}

function _preview_text(text) {
  if (!text) return '（无内容）'
  return text.length > 180 ? `${text.slice(0, 180)}…` : text
}

function _location_label(item) {
  const span_index = Number(item?.span_index)
  const chunk_id = Number(item?.chunk_id)

  if (Number.isFinite(span_index)) return `Span ${span_index}`
  if (Number.isFinite(chunk_id)) return `Chunk ${chunk_id}`
  return ''
}

function _sub_label(item) {
  const parts = []

  if (item?.library_id) parts.push(`lib ${item.library_id}`)
  if (item?.doc_id) parts.push(`doc ${item.doc_id}`)

  return parts.join(' · ')
}

const normalized_results = computed(() => {
  const arr = Array.isArray(props.searchResults) ? props.searchResults : []

  return arr.map((item, idx) => {
    const full_text = _pick_text(item)
    const title = _pick_title(item)
    const doc_label = String(item?.doc_filename || item?.filename || item?.doc_title || item?.doc_id || '未命名文档')
    const location = _location_label(item)
    const sub = _sub_label(item)
    const score = _pick_score(item)

    return {
      ...item,
      _result_key: `${doc_label}::${location}::${idx}`,
      _title: title,
      _full_text: full_text,
      _preview_text: _preview_text(full_text),
      _doc_label: doc_label,
      _location_label: location,
      _sub_label: sub,
      _score_value: score
    }
  })
})

function format_score(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0.0%'
  if (n <= 1) return `${(n * 100).toFixed(1)}%`
  return `${n.toFixed(1)}%`
}

function emit_result_click(item) {
  emit('result-click', {
    ...item,
    scope: current_scope.value,
    mode: current_mode.value
  })
}
</script>

<style scoped>
.search-section-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.search-controls {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.tabs-row {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.tab-group {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
  align-items: center;
}

.tab-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  flex-shrink: 0;
  margin-right: 0.15rem;
}

.scope-tab {
  padding: 0.3rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text-secondary);
  text-transform: lowercase;
}

.scope-tab:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.scope-tab.active {
  background: rgba(60, 105, 188, 0.15);
  border-color: rgba(60, 105, 188, 0.5);
  color: var(--selected);
  font-weight: 600;
}

.search-section {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.search-input {
  flex: 1;
  padding: 0.6rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-main);
  font-size: 0.9rem;
  transition: all var(--transition-normal) ease;
}

.search-input:focus {
  outline: none;
  border-color: var(--selected);
  box-shadow: 0 0 0 2px rgba(60, 105, 188, 0.1);
}

.search-btn {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  border: none;
  background: var(--selected);
  color: #fff;
  cursor: pointer;
  font-size: 1.1rem;
  transition: all var(--transition-normal) var(--ease-smooth);
  flex-shrink: 0;
}

.search-btn:hover:enabled {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(60, 105, 188, 0.3);
}

.search-btn:disabled {
  opacity: 0.7;
  cursor: default;
}

.clear-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1.2rem;
  transition: all var(--transition-normal) var(--ease-smooth);
  flex-shrink: 0;
}

.clear-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.search-status-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.status-pill {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.12rem 0.45rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  background: transparent;
}

.text-pill {
  max-width: 100%;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.search-results {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.results-meta {
  font-size: 0.76rem;
  font-weight: 500;
  opacity: 0.85;
  text-transform: lowercase;
}

.result-item {
  display: flex;
  gap: 0.8rem;
  padding: 0.8rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  transition: all var(--transition-normal) ease;
  cursor: pointer;
}

.result-item:hover {
  border-color: var(--selected);
  box-shadow: 0 2px 6px rgba(60, 105, 188, 0.12);
  background: rgba(60, 105, 188, 0.05);
}

.result-score {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--selected);
  flex-shrink: 0;
  min-width: 54px;
  text-align: right;
}

.result-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.32rem;
}

.result-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text);
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.result-text {
  line-height: 1.6;
  color: var(--text);
  font-size: 0.9rem;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.result-details {
  margin-top: 0.05rem;
}

.result-details summary {
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.result-details-body {
  margin-top: 0.35rem;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.result-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  align-items: center;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.meta-main {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.meta-sub {
  opacity: 0.9;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.meta-sep {
  opacity: 0.55;
}

.empty-tip {
  padding: 0.25rem 0.1rem;
  font-size: 0.84rem;
}

.muted {
  color: var(--text-secondary);
}

@media (max-width: 768px) {
  .tab-group {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
  }

  .tab-group::-webkit-scrollbar {
    height: 0;
  }

  .scope-tab,
  .tab-label {
    flex-shrink: 0;
  }

  .search-input {
    font-size: 16px;
  }

  .result-item {
    padding: 0.75rem 0.75rem;
  }
}
</style>

