<template>
  <div v-if="props.open" class="nisb-modal-mask" @click.self="$emit('close')">
    <section class="nisb-modal nisb-modal-wide" role="dialog" aria-modal="true" :aria-label="t('library.center.batchDeleteModal.title')">
      <header class="modal-head">
        <div class="title-wrap">
          <div class="eyebrow-row">
            <span class="danger-chip">{{ t('library.center.batchDeleteModal.eyebrow') }}</span>
            <span class="irreversible-chip">{{ t('library.center.batchDeleteModal.irreversible') }}</span>
            <span class="count-chip">{{ t('library.center.batchDeleteModal.selectedCount', { count: props.selected_count }) }}</span>
          </div>

          <h2 class="nisb-modal-title">{{ t('library.center.batchDeleteModal.title') }}</h2>
          <p class="modal-desc">{{ t('library.center.batchDeleteModal.description') }}</p>
        </div>

        <button
          class="icon-btn"
          :aria-label="t('library.center.batchDeleteModal.close')"
          :disabled="props.working"
          type="button"
          @click="$emit('close')"
        >
          ×
        </button>
      </header>

      <div class="nisb-modal-body">
        <section class="danger-card">
          <div class="card-topline">
            <span class="card-title">{{ t('library.center.batchDeleteModal.deletionScope') }}</span>
            <span class="mini-danger">{{ t('library.center.batchDeleteModal.permanent') }}</span>
          </div>

          <div class="scope-grid">
            <span class="scope-chip">{{ t('library.center.batchDeleteModal.sourceText') }}</span>
            <span class="scope-chip">{{ t('library.center.batchDeleteModal.analysisResults') }}</span>
            <span class="scope-chip">{{ t('library.center.batchDeleteModal.translationCache') }}</span>
          </div>
        </section>

        <section class="toolbar-card">
          <div class="toolbar-topline">
            <div class="toolbar-title-wrap">
              <span class="card-title">{{ t('library.center.batchDeleteModal.documentList') }}</span>
              <span class="toolbar-hint">{{ t('library.center.batchDeleteModal.filterHint') }}</span>
            </div>

            <div class="batch-meta">
              <span class="meta-chip">{{ t('library.center.batchDeleteModal.filteredCount', { count: props.filtered_docs.length }) }}</span>
              <span class="meta-chip selected">{{ t('library.center.batchDeleteModal.selectedCount', { count: props.selected_count }) }}</span>
            </div>
          </div>

          <div class="batch-toolbar">
            <input
              class="nisb-input"
              :value="props.filter_text"
              :disabled="props.working"
              @input="$emit('update:filter_text', $event.target.value)"
              :placeholder="t('library.center.batchDeleteModal.filterPlaceholder')"
            />

            <button
              class="mini-btn"
              @click="$emit('select_all_filtered')"
              :disabled="props.working || !props.filtered_docs.length"
              type="button"
            >
              {{ t('library.center.batchDeleteModal.selectAllFiltered') }}
            </button>

            <button
              class="mini-btn"
              @click="$emit('clear_selection')"
              :disabled="props.working || props.selected_count === 0"
              type="button"
            >
              {{ t('library.center.batchDeleteModal.clearSelection') }}
            </button>
          </div>
        </section>

        <section class="list-card">
          <div class="card-topline list-topline">
            <span class="card-title">{{ t('library.center.batchDeleteModal.reviewSelection') }}</span>
            <span class="mini-chip">{{ selection_ratio }}</span>
          </div>

          <div v-if="props.filtered_docs.length" class="batch-list">
            <label v-for="doc in props.filtered_docs" :key="doc_key(doc)" class="batch-item" :class="{ selected: !!props.selected_map[doc.doc_id] }">
              <span class="checkbox-shell">
                <input
                  type="checkbox"
                  :checked="!!props.selected_map[doc.doc_id]"
                  :disabled="props.working"
                  @change="$emit('toggle_select', doc.doc_id)"
                />
              </span>

              <span class="batch-item-main">
                <span class="batch-item-title">{{ doc.filename || doc.title || doc.name || doc.doc_id }}</span>

                <span class="batch-item-sub">
                  <span class="machine-value">{{ doc.doc_id }}</span>
                  <span class="dot-separator">·</span>
                  <span>{{ doc.filetype || t('library.center.batchDeleteModal.fallbackFiletype') }}</span>
                  <span class="dot-separator">·</span>
                  <span>{{ t('library.center.batchDeleteModal.chunks', { count: doc.chunks || 0 }) }}</span>
                </span>
              </span>

              <span v-if="!!props.selected_map[doc.doc_id]" class="selected-marker">
                {{ t('library.center.batchDeleteModal.selectedBadge') }}
              </span>
            </label>
          </div>

          <div v-else class="empty-state">
            <div class="empty-icon">∅</div>
            <div class="empty-copy">
              <div class="empty-title">{{ t('library.center.batchDeleteModal.emptyTitle') }}</div>
              <div class="empty-desc">{{ t('library.center.batchDeleteModal.emptyDescription') }}</div>
            </div>
          </div>
        </section>
      </div>

      <footer class="nisb-modal-actions">
        <button class="modal-btn ghost" :disabled="props.working" @click="$emit('close')" type="button">
          {{ t('library.center.batchDeleteModal.cancel') }}
        </button>

        <button
          class="modal-btn danger"
          :disabled="props.working || props.selected_count === 0"
          @click="$emit('confirm')"
          type="button"
        >
          {{ confirm_button_text }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
  working: { type: Boolean, default: false },
  filter_text: { type: String, default: '' },
  filtered_docs: { type: Array, default: () => [] },
  selected_map: { type: Object, default: () => ({}) },
  selected_count: { type: Number, default: 0 }
})

defineEmits([
  'close',
  'confirm',
  'update:filter_text',
  'select_all_filtered',
  'clear_selection',
  'toggle_select'
])

const { t } = useI18n()

const confirm_button_text = computed(() => {
  if (props.working) return t('library.center.batchDeleteModal.deleting')
  return t('library.center.batchDeleteModal.confirmDelete', { count: props.selected_count })
})

const selection_ratio = computed(() => {
  const total = props.filtered_docs.length
  return t('library.center.batchDeleteModal.selectionRatio', {
    selected: props.selected_count,
    total
  })
})

function doc_key(doc) {
  return String(doc?.doc_id || doc?.filename || doc?.path || Math.random())
}
</script>

<style scoped>
.nisb-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 2147483000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background:
    radial-gradient(circle at 18% 12%, rgba(239, 68, 68, 0.16), transparent 34%),
    radial-gradient(circle at 86% 18%, rgba(217, 119, 6, 0.12), transparent 30%),
    rgba(12, 18, 32, 0.46);
  backdrop-filter: blur(18px) saturate(1.08);
  -webkit-backdrop-filter: blur(18px) saturate(1.08);
}

.nisb-modal {
  width: min(570px, calc(100vw - 28px));
  max-height: min(780px, calc(100vh - 28px));
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, #ef4444 28%, var(--line));
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--editor-bg) 92%, transparent), color-mix(in srgb, var(--sidebar-bg) 78%, transparent)),
    color-mix(in srgb, var(--editor-bg) 88%, transparent);
  box-shadow:
    0 24px 80px rgba(15, 23, 42, 0.3),
    0 1px 0 rgba(255, 255, 255, 0.26) inset;
  color: var(--text);
}

.nisb-modal-wide {
  width: min(820px, calc(100vw - 28px));
}

.modal-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1rem 0.85rem;
  border-bottom: 1px solid color-mix(in srgb, #ef4444 18%, var(--line));
}

.title-wrap {
  min-width: 0;
}

.eyebrow-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
}

.danger-chip,
.irreversible-chip,
.count-chip,
.mini-chip,
.mini-danger,
.meta-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  max-width: 100%;
  padding: 0.18rem 0.58rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 78%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.danger-chip,
.mini-danger {
  border-color: color-mix(in srgb, #ef4444 52%, var(--line));
  background: color-mix(in srgb, #ef4444 11%, transparent);
  color: color-mix(in srgb, #ef4444 86%, var(--text));
}

.irreversible-chip {
  border-color: color-mix(in srgb, #d97706 48%, var(--line));
  background: color-mix(in srgb, #d97706 11%, transparent);
  color: color-mix(in srgb, #d97706 84%, var(--text));
}

.count-chip,
.meta-chip.selected {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 88%, transparent);
  color: var(--selected);
}

.nisb-modal-title {
  margin: 0;
  color: var(--text);
  font-size: 0.98rem;
  font-weight: 820;
  line-height: 1.28;
  overflow-wrap: break-word;
}

.modal-desc {
  max-width: 54rem;
  margin: 0.42rem 0 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.icon-btn {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 1.18rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.icon-btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, #ef4444 54%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: color-mix(in srgb, #ef4444 84%, var(--text));
  transform: translateY(-1px);
}

.icon-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.nisb-modal-body {
  display: grid;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  overflow: auto;
  max-height: calc(100vh - 220px);
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 80%, transparent) transparent;
}

.nisb-modal-body::-webkit-scrollbar,
.batch-list::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.nisb-modal-body::-webkit-scrollbar-thumb,
.batch-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 82%, transparent);
}

.danger-card,
.toolbar-card,
.list-card {
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--sidebar-bg) 72%, transparent), color-mix(in srgb, var(--editor-bg) 62%, transparent));
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.danger-card {
  padding: 0.85rem;
  border-color: color-mix(in srgb, #ef4444 24%, var(--line));
  background:
    linear-gradient(145deg, color-mix(in srgb, #ef4444 8%, transparent), color-mix(in srgb, var(--editor-bg) 70%, transparent));
}

.toolbar-card,
.list-card {
  padding: 0.85rem;
}

.card-topline,
.toolbar-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem;
  margin-bottom: 0.65rem;
}

.list-topline {
  align-items: center;
}

.card-title {
  min-width: 0;
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.toolbar-title-wrap {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.toolbar-hint {
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.scope-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  min-height: 25px;
  max-width: 100%;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, #ef4444 28%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text);
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: break-word;
}

.batch-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.4rem;
}

.batch-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 0.5rem;
  align-items: center;
}

.nisb-input {
  width: 100%;
  min-height: 40px;
  padding: 0.58rem 0.72rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  outline: none;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text);
  font-size: 0.84rem;
  line-height: 1.45;
  overflow-wrap: break-word;
  transition:
    border-color var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    background var(--transition-normal) var(--ease-smooth);
}

.nisb-input:focus {
  border-color: var(--selected);
  background: color-mix(in srgb, var(--editor-bg) 94%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 18%, transparent);
}

.nisb-input:disabled {
  opacity: 0.64;
  cursor: not-allowed;
}

.mini-btn {
  min-height: 40px;
  padding: 0.52rem 0.72rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text);
  font-size: 0.78rem;
  font-weight: 760;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.mini-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
  transform: translateY(-1px);
}

.mini-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  transform: none;
}

.batch-list {
  max-height: 360px;
  overflow: auto;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 45%, transparent);
}

.batch-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: flex-start;
  padding: 0.66rem 0.72rem;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 52%, transparent);
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth);
}

.batch-item:last-child {
  border-bottom: 0;
}

.batch-item:hover {
  background: color-mix(in srgb, var(--selected-bg) 52%, transparent);
}

.batch-item.selected {
  background: color-mix(in srgb, var(--selected-bg) 68%, transparent);
}

.checkbox-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-top: 0.05rem;
}

.checkbox-shell input[type='checkbox'] {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.checkbox-shell input[type='checkbox']:disabled {
  cursor: not-allowed;
}

.batch-item-main {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
}

.batch-item-title {
  min-width: 0;
  color: var(--text);
  font-size: 0.87rem;
  font-weight: 760;
  line-height: 1.38;
  overflow-wrap: break-word;
}

.batch-item-sub {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.machine-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  overflow-wrap: anywhere;
}

.dot-separator {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.selected-marker {
  align-self: center;
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  padding: 0.16rem 0.5rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 82%, transparent);
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1.2;
  white-space: nowrap;
}

.empty-state {
  min-height: 160px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px dashed color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
}

.empty-icon {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 70%, transparent);
  color: var(--text-secondary);
  font-size: 1rem;
  font-weight: 800;
}

.empty-copy {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
}

.empty-title {
  color: var(--text);
  font-size: 0.82rem;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.empty-desc {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.nisb-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  padding: 0.85rem 1rem 1rem;
  border-top: 1px solid color-mix(in srgb, #ef4444 18%, var(--line));
  background: color-mix(in srgb, var(--sidebar-bg) 42%, transparent);
}

.modal-btn {
  min-height: 38px;
  padding: 0.5rem 0.9rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 780;
  line-height: 1.25;
  cursor: pointer;
  transition:
    background var(--transition-normal) var(--ease-smooth),
    border-color var(--transition-normal) var(--ease-smooth),
    color var(--transition-normal) var(--ease-smooth),
    box-shadow var(--transition-normal) var(--ease-smooth),
    transform var(--transition-normal) var(--ease-smooth);
}

.modal-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.modal-btn.ghost:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.modal-btn.danger {
  border-color: color-mix(in srgb, #ef4444 70%, var(--line));
  background: linear-gradient(135deg, color-mix(in srgb, #ef4444 92%, #ffffff 4%), color-mix(in srgb, #b91c1c 82%, #111827 8%));
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(239, 68, 68, 0.24);
}

.modal-btn.danger:hover:not(:disabled) {
  border-color: color-mix(in srgb, #ef4444 78%, #ffffff);
  box-shadow: 0 16px 34px rgba(239, 68, 68, 0.3);
}

.modal-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (max-width: 760px) {
  .toolbar-topline,
  .card-topline {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-meta {
    justify-content: flex-start;
  }

  .batch-toolbar {
    grid-template-columns: 1fr;
  }

  .mini-btn {
    width: 100%;
    justify-content: center;
  }

  .batch-item {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .selected-marker {
    grid-column: 2;
    justify-self: flex-start;
  }
}

@media (max-width: 640px) {
  .nisb-modal-mask {
    align-items: stretch;
    padding: 0.65rem;
  }

  .nisb-modal {
    width: 100%;
    max-height: calc(100vh - 1.3rem);
    display: flex;
    flex-direction: column;
    border-radius: 18px;
  }

  .modal-head {
    padding: 0.9rem 0.85rem 0.78rem;
  }

  .nisb-modal-body {
    flex: 1;
    max-height: none;
    padding: 0.8rem 0.85rem;
  }

  .batch-list {
    max-height: none;
  }

  .nisb-modal-actions {
    flex-direction: column-reverse;
    padding: 0.8rem 0.85rem 0.9rem;
  }

  .modal-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
