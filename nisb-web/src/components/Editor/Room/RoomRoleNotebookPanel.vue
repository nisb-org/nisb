<template>
  <div class="notebook_panel" :class="{ blocked: !workspaceId }">
    <div class="notebook_head">
      <div class="notebook_title_block">
        <div class="notebook_title">{{ t('room.roleNotebookPanel.title') }}</div>
      </div>

      <div
        v-if="workspaceId"
        class="workspace_chip"
        :title="workspaceId"
      >
        {{ workspaceId }}
      </div>
    </div>

    <div v-if="!workspaceId" class="notebook_warning" role="status">
      {{ t('room.roleNotebookPanel.warningNoWorkspace') }}
    </div>

    <div class="form_grid">
      <label class="field">
        <span>{{ t('room.roleNotebookPanel.fields.title.label') }}</span>
        <input v-model="form.title" type="text" />
      </label>

      <label class="field">
        <span>{{ t('room.roleNotebookPanel.fields.sectionTitle.label') }}</span>
        <input
          v-model="form.section_title"
          type="text"
          :placeholder="t('room.roleNotebookPanel.fields.sectionTitle.placeholder')"
        />
      </label>

      <label class="field">
        <span>{{ t('room.roleNotebookPanel.fields.filename.label') }}</span>
        <input v-model="form.filename" type="text" />
      </label>

      <label class="field">
        <span>{{ t('room.roleNotebookPanel.fields.notebookDir.label') }}</span>
        <input
          v-model="form.notebook_dir"
          type="text"
          :placeholder="t('room.roleNotebookPanel.fields.notebookDir.placeholder')"
        />
      </label>

      <label class="field field_full summary_field">
        <span>{{ t('room.roleNotebookPanel.fields.summaryMd.label') }}</span>
        <textarea
          v-model="form.summary_md"
          rows="8"
          :placeholder="t('room.roleNotebookPanel.fields.summaryMd.placeholder')"
        ></textarea>
      </label>
    </div>

    <div class="card_actions">
      <button class="ghost_btn" type="button" @click="$emit('fill-template')">
        {{ t('room.roleNotebookPanel.actions.fillTemplate') }}
      </button>

      <button
        class="primary_btn"
        type="button"
        :disabled="busy || !workspaceId"
        @click="$emit('submit')"
      >
        {{
          busy
            ? t('room.roleNotebookPanel.actions.submitting')
            : t('room.roleNotebookPanel.actions.submit')
        }}
      </button>
    </div>

    <div v-if="statusText" class="notebook_status" role="status">
      {{ statusText }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  form: { type: Object, required: true },
  resolvedWorkspace: { type: Object, default: () => ({}) },
  busy: { type: Boolean, default: false },
  statusText: { type: String, default: '' },
})

defineEmits(['fill-template', 'submit'])

const { t } = useI18n()

const workspaceId = computed(() => String(props.resolvedWorkspace?.workspace_id || '').trim())
</script>

<style scoped>
.notebook_panel {
  min-width: 0;
  margin-top: 12px;
  padding: 13px;
  border: 1px solid color-mix(in srgb, var(--selected) 16%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.notebook_panel.blocked {
  border-color: rgba(239, 68, 68, 0.22);
}

.notebook_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  margin-bottom: 12px;
}

.notebook_title_block {
  min-width: 0;
}

.notebook_title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.workspace_chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: min(320px, 42vw);
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid rgba(34, 197, 94, 0.34);
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notebook_warning {
  box-sizing: border-box;
  margin-bottom: 12px;
  padding: 10px 11px;
  border: 1px solid rgba(239, 68, 68, 0.32);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.notebook_status {
  margin-top: 12px;
  padding: 10px 11px;
  border: 1px solid rgba(34, 197, 94, 0.32);
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.form_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 11px;
  min-width: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field > span {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
}

.field input,
.field textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  padding: 10px 11px;
  font-family: inherit;
  font-size: 0.83rem;
  line-height: 1.45;
  outline: none;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.field textarea {
  resize: vertical;
}

.summary_field textarea {
  min-height: 180px;
}

.field input::placeholder,
.field textarea::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.field input:focus,
.field textarea:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.field_full {
  grid-column: 1 / -1;
}

.card_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.primary_btn,
.ghost_btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.primary_btn {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected) 90%, #1f2937);
  color: #fff;
}

.primary_btn:hover:not(:disabled) {
  opacity: 0.94;
}

.ghost_btn {
  color: var(--text-secondary);
}

.ghost_btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 58%, var(--editor-bg));
  color: var(--selected);
}

.primary_btn:active:not(:disabled),
.ghost_btn:active:not(:disabled) {
  transform: translateY(1px);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 860px) {
  .form_grid {
    grid-template-columns: 1fr;
  }

  .notebook_head {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace_chip {
    align-self: flex-start;
    max-width: 100%;
  }
}

@media (max-width: 720px) {
  .notebook_panel {
    border-radius: 14px;
    padding: 12px;
  }

  .card_actions {
    justify-content: stretch;
  }

  .card_actions button {
    flex: 1 1 auto;
    min-width: 0;
  }
}

@media (max-width: 420px) {
  .card_actions button {
    width: 100%;
    flex-basis: 100%;
  }
}
</style>
