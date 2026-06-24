<template>
  <div class="settings-section settings-files-section">
    <div class="settings-card is-accent">
      <div class="files-card-head">
        <div class="settings-main">
          <span class="files-card-title">
            {{ t('settings.files.currentWorkspace.label') }}
          </span>
          <span class="muted settings-hint">
            {{ t('settings.files.currentWorkspace.hint') }}
          </span>
        </div>

        <span
          v-if="selected_workspace_id_proxy"
          class="workspace-chip mono"
          :class="{ unsafe: !workspaceIdSafe }"
          :title="selected_workspace_id_proxy"
        >
          {{ selected_workspace_id_proxy }}
        </span>
      </div>

      <div class="files-control-row">
        <select
          class="settings-select files-control-main"
          v-model="selected_workspace_id_proxy"
          @change="$emit('workspace-select-changed')"
          :disabled="busy"
        >
          <option v-for="ws in workspaces" :key="ws.id" :value="ws.id">
            {{ display_workspace_name(ws) }}
          </option>
        </select>

        <button
          class="mini-btn files-control-action"
          type="button"
          @click="$emit('load-workspaces')"
          :disabled="busy"
        >
          {{ t('settings.files.currentWorkspace.refresh') }}
        </button>
      </div>
    </div>

    <div class="settings-card">
      <div class="files-card-head">
        <div class="settings-main">
          <span class="files-card-title">
            {{ t('settings.files.manage.label') }}
          </span>
          <span class="muted settings-hint">
            {{ t('settings.files.manage.hint') }}
          </span>
        </div>
      </div>

      <div
        class="icon-picker files-icon-grid"
        role="group"
        :aria-label="t('settings.files.manage.iconChoicesAria')"
      >
        <button
          v-for="ic in iconChoices"
          :key="ic"
          type="button"
          class="icon-btn"
          :class="{ active: rename_ws_icon_proxy === ic }"
          @click="rename_ws_icon_proxy = ic"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ ic }}
        </button>
      </div>

      <div class="files-inline-actions">
        <input
          class="settings-input"
          type="text"
          v-model="rename_ws_name_proxy"
          :disabled="busy || !workspaceIdSafe"
          :placeholder="t('settings.files.manage.renamePlaceholder')"
          maxlength="32"
        />

        <div class="btn-group">
          <button
            class="mini-btn"
            type="button"
            @click="$emit('rename-workspace')"
            :disabled="busy || !workspaceIdSafe || !rename_ws_name_proxy.trim()"
          >
            {{ t('settings.files.manage.rename') }}
          </button>

          <button
            class="mini-btn danger"
            type="button"
            @click="$emit('delete-workspace')"
            :disabled="busy || !workspaceIdSafe || isDefaultWorkspace"
          >
            {{ t('settings.files.manage.delete') }}
          </button>
        </div>
      </div>
    </div>

    <div class="settings-card">
      <div class="files-card-head">
        <div class="settings-main">
          <span class="files-card-title">
            {{ t('settings.files.create.label') }}
          </span>
          <span class="muted settings-hint">
            {{ t('settings.files.create.hint') }}
          </span>
        </div>
      </div>

      <div
        class="icon-picker files-icon-grid"
        role="group"
        :aria-label="t('settings.files.create.iconChoicesAria')"
      >
        <button
          v-for="ic in iconChoices"
          :key="ic"
          type="button"
          class="icon-btn"
          :class="{ active: new_ws_icon_proxy === ic }"
          @click="new_ws_icon_proxy = ic"
          :disabled="busy"
        >
          {{ ic }}
        </button>
      </div>

      <div class="files-inline-actions">
        <input
          class="settings-input"
          type="text"
          v-model="new_ws_name_proxy"
          :disabled="busy"
          :placeholder="t('settings.files.create.placeholder')"
          maxlength="32"
        />

        <div class="btn-group">
          <button
            class="mini-btn primary"
            type="button"
            @click="$emit('create-workspace')"
            :disabled="busy || !new_ws_name_proxy.trim()"
          >
            {{ t('settings.files.create.submit') }}
          </button>
        </div>
      </div>
    </div>

    <div class="settings-card">
      <div class="files-card-head">
        <div class="settings-main">
          <span class="files-card-title">
            {{ t('settings.files.snapshotFocus.label') }}
          </span>
        </div>
      </div>

      <input
        class="settings-input mono"
        type="text"
        v-model="saved_focused_preview_display_proxy"
        :placeholder="t('settings.files.snapshotFocus.placeholder')"
        :disabled="busy"
      />
    </div>

    <div class="settings-card">
      <div class="files-card-head">
        <div class="settings-main">
          <span class="files-card-title">
            {{ t('settings.files.snapshotFavorites.label') }}
          </span>
        </div>

        <span class="count-chip mono">
          {{ savedFavoritesCount }}
        </span>
      </div>

      <div class="files-action-grid">
        <button
          class="mini-btn"
          type="button"
          @click="$emit('refresh-workspace-files-state')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.snapshotFavorites.refreshPreview') }}
        </button>

        <button
          class="mini-btn"
          type="button"
          @click="$emit('copy-current-favorites-internal-links')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.snapshotFavorites.copyCurrentLinks') }}
        </button>
      </div>

      <div class="favorites-preview muted settings-hint">
        <template v-if="localFavoritesCleared">
          {{ t('settings.files.snapshotFavorites.clearedUnsaved', { fallback: '常用（已清空，未保存）—— 点「保存到工作空间」持久化，或点「应用到 UI」恢复。' }) }}
        </template>
        <template v-else-if="savedFavoritesPreview.length">
          {{ t('settings.files.snapshotFavorites.preview', { items: favorites_preview_text }) }}
        </template>
        <template v-else>
          {{ t('settings.files.snapshotFavorites.empty') }}
        </template>
      </div>
    </div>

    <div class="settings-card settings-actions-card">
      <div class="files-action-grid">
        <button
          class="mini-btn"
          type="button"
          @click="$emit('read-focus-from-local')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.actions.readCurrentFocus') }}
        </button>

        <button
          class="mini-btn"
          type="button"
          @click="$emit('apply-workspace-files-state-to-ui')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.actions.applyToUi') }}
        </button>

        <button
          class="mini-btn primary"
          type="button"
          @click="$emit('save-workspace-snapshot-from-current')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.actions.saveToWorkspace') }}
        </button>

        <button
          class="mini-btn warning"
          type="button"
          @click="$emit('clear-workspace-favorites-local')"
          :disabled="busy || !workspaceIdSafe"
        >
          {{ t('settings.files.actions.clearFavorites', { fallback: '清空常用' }) }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  from_user_visible_path,
  to_user_visible_path,
  to_user_visible_text
} from '../../../composables/left_sidebar/file_browser/file_path_display'

const props = defineProps({
  busy: { type: Boolean, default: false },
  workspaces: { type: Array, default: () => [] },
  iconChoices: { type: Array, default: () => [] },
  selectedWorkspaceId: { type: String, default: '' },
  newWsIcon: { type: String, default: '🧩' },
  newWsName: { type: String, default: '' },
  renameWsIcon: { type: String, default: '🧩' },
  renameWsName: { type: String, default: '' },
  workspaceIdSafe: { type: Boolean, default: false },
  isDefaultWorkspace: { type: Boolean, default: false },
  savedFocusedPreview: { type: String, default: '' },
  savedFavoritesCount: { type: Number, default: 0 },
  savedFavoritesPreview: { type: Array, default: () => [] },
  localFavoritesCleared: { type: Boolean, default: false }
})

const emit = defineEmits([
  'update:selectedWorkspaceId',
  'update:newWsIcon',
  'update:newWsName',
  'update:renameWsIcon',
  'update:renameWsName',
  'update:savedFocusedPreview',
  'load-workspaces',
  'workspace-select-changed',
  'rename-workspace',
  'delete-workspace',
  'create-workspace',
  'refresh-workspace-files-state',
  'copy-current-favorites-internal-links',
  'read-focus-from-local',
  'apply-workspace-files-state-to-ui',
  'save-workspace-snapshot-from-current',
  'clear-workspace-favorites-local'
])

const { t } = useI18n()

const selected_workspace_id_proxy = computed({
  get: () => props.selectedWorkspaceId || '',
  set: (val) => emit('update:selectedWorkspaceId', String(val || ''))
})

const new_ws_icon_proxy = computed({
  get: () => props.newWsIcon || '🧩',
  set: (val) => emit('update:newWsIcon', String(val || '🧩'))
})

const new_ws_name_proxy = computed({
  get: () => props.newWsName || '',
  set: (val) => emit('update:newWsName', String(val || ''))
})

const rename_ws_icon_proxy = computed({
  get: () => props.renameWsIcon || '🧩',
  set: (val) => emit('update:renameWsIcon', String(val || '🧩'))
})

const rename_ws_name_proxy = computed({
  get: () => props.renameWsName || '',
  set: (val) => emit('update:renameWsName', String(val || ''))
})

const saved_focused_preview_proxy = computed({
  get: () => props.savedFocusedPreview || '',
  set: (val) => emit('update:savedFocusedPreview', String(val || ''))
})

const saved_focused_preview_display_proxy = computed({
  get: () => to_user_visible_path(saved_focused_preview_proxy.value),
  set: (val) => emit('update:savedFocusedPreview', from_user_visible_path(val))
})

function display_workspace_name(ws) {
  return to_user_visible_text(ws?.name || '')
}

const favorites_preview_text = computed(() => {
  return (props.savedFavoritesPreview || [])
    .map((item) => to_user_visible_text(item))
    .join(t('settings.files.common.listSeparator'))
})
</script>

<style scoped>
.settings-files-section {
  min-width: 0;
}

.settings-main {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.files-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.files-card-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.workspace-chip,
.count-chip {
  flex: 0 1 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: min(320px, 44vw);
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid rgba(34, 197, 94, 0.34);
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-chip.unsafe {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.count-chip {
  max-width: none;
  min-width: 34px;
}

.files-control-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.files-control-main,
.files-control-action {
  min-width: 0;
}

.files-icon-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.files-inline-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.btn-group {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  min-width: 0;
}

.btn-group .mini-btn {
  flex: 0 0 auto;
}

.files-action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.files-action-grid .mini-btn {
  flex: 1 1 170px;
  min-width: 0;
  white-space: normal;
}

.favorites-preview {
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
}

.settings-actions-card {
  border-color: color-mix(in srgb, var(--selected) 18%, var(--line));
}

.mini-btn.warning {
  background: color-mix(in srgb, #d97706 12%, transparent);
  color: #d97706;
  border-color: rgba(217, 119, 6, 0.34);
}

.mini-btn.warning:hover:not(:disabled) {
  background: color-mix(in srgb, #d97706 22%, transparent);
}

@media (max-width: 720px) {
  .files-card-head,
  .files-control-row,
  .files-inline-actions {
    grid-template-columns: 1fr;
  }

  .files-card-head {
    display: grid;
  }

  .workspace-chip,
  .count-chip {
    justify-self: start;
    max-width: 100%;
  }

  .files-control-action,
  .files-inline-actions .mini-btn,
  .files-action-grid .mini-btn {
    width: 100%;
  }

  .btn-group {
    width: 100%;
  }

  .btn-group .mini-btn {
    flex: 1 1 120px;
    min-width: 0;
  }
}

@media (max-width: 420px) {
  .files-action-grid .mini-btn,
  .btn-group .mini-btn {
    flex-basis: 100%;
  }
}
</style>
