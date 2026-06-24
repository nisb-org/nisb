<template>
  <div class="search-row">
    <div class="search-main">
      <div v-if="selected_doc" class="doc-name">
        {{ selected_doc.filename || selected_doc.doc_id || selected_doc.docid }}
      </div>
      <div v-else class="doc-name muted">{{ t('library.center.topActionBar.noDocumentSelected') }}</div>
    </div>

    <div class="right-actions">
      <button
        class="ghost-btn export-btn"
        :disabled="uploading || loading_docs || exporting_translated || (!documents.length && !selected_doc)"
        :title="export_button_title || t('library.center.topActionBar.exportTranslatedTitle')"
        @click="$emit('open_export')"
        type="button"
      >
        {{ exporting_translated ? t('library.center.topActionBar.exporting') : t('library.center.topActionBar.exportTranslated') }}
      </button>

      <button
        class="ghost-btn"
        :disabled="uploading || exporting_translated"
        :title="doc_list_visible ? t('library.center.topActionBar.hideDocumentListTitle') : t('library.center.topActionBar.showDocumentListTitle')"
        @click="$emit('toggle_doc_list')"
        type="button"
      >
        {{ doc_list_visible ? t('library.center.topActionBar.focusMode') : t('library.center.topActionBar.listMode') }}
      </button>

      <button
        class="batch-delete-btn"
        :disabled="uploading || loading_docs || !documents.length || exporting_translated"
        :title="t('library.center.topActionBar.batchDeleteTitle')"
        @click="$emit('open_batch_delete')"
        type="button"
      >
        {{ t('library.center.topActionBar.batchDelete') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  selected_doc: { type: Object, default: null },
  documents: { type: Array, default: () => [] },
  uploading: { type: Boolean, default: false },
  loading_docs: { type: Boolean, default: false },
  exporting_translated: { type: Boolean, default: false },
  doc_list_visible: { type: Boolean, default: true },
  export_button_title: { type: String, default: '' }
})

defineEmits(['open_export', 'toggle_doc_list', 'open_batch_delete'])

const { t } = useI18n()
</script>

<style scoped>
.search-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.search-main {
  flex: 1;
  min-width: 0;
}

.right-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.doc-name {
  padding: 0.6rem 0.75rem;
  border-radius: 12px;
  background: rgba(60, 105, 188, 0.08);
  border: 1px solid rgba(60, 105, 188, 0.16);
  font-size: 0.9rem;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.muted {
  color: var(--text-secondary);
  line-height: 1.5;
}

.ghost-btn {
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
  white-space: nowrap;
  height: fit-content;
}

.ghost-btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.export-btn {
  border-style: dashed;
  font-weight: 600;
}

.batch-delete-btn {
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
  white-space: nowrap;
  height: fit-content;
}

.batch-delete-btn:hover:not(:disabled) {
  background: rgba(200, 80, 80, 0.12);
  border-color: rgba(200, 80, 80, 0.45);
  color: var(--text);
}

.batch-delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
