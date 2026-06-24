<template>
  <section class="quick_card">
    <div class="card_head">
      <div>
        <div class="card_title">
          {{ t('room.workspaceQuickSaveCard.header.title') }}
        </div>
        <div class="card_subtitle">
          {{ t('room.workspaceQuickSaveCard.header.subtitle') }}
        </div>
      </div>
      <span class="state_badge" :class="{ active: props.workspace_ready }">
        {{
          props.workspace_ready
            ? t('room.workspaceQuickSaveCard.header.ready')
            : t('room.workspaceQuickSaveCard.header.unbound')
        }}
      </span>
    </div>

    <div v-if="!props.workspace_ready" class="empty_block">
      {{ t('room.workspaceQuickSaveCard.empty.noWorkspace') }}
    </div>

    <template v-else>
      <div class="section_block">
        <div class="section_title">
          {{ t('room.workspaceQuickSaveCard.sections.recommendedActions') }}
        </div>
        <div class="action_grid">
          <button
            class="action_btn primary"
            type="button"
            :disabled="!room_note_path"
            @click="open_relative_path(room_note_path, 'roomNote')"
          >
            {{ t('room.workspaceQuickSaveCard.actions.openRoomNote') }}
          </button>

          <button
            class="action_btn"
            type="button"
            :disabled="!agent_notebook_path"
            @click="open_relative_path(agent_notebook_path, 'agentNotebook')"
          >
            {{ t('room.workspaceQuickSaveCard.actions.openAgentNotebook') }}
          </button>

          <button
            class="action_btn"
            type="button"
            :disabled="!props.focus_root"
            @click="copy_text(props.focus_root, t('room.workspaceQuickSaveCard.status.copiedFocusRoot'))"
          >
            {{ t('room.workspaceQuickSaveCard.actions.copyFocusRoot') }}
          </button>

          <button
            class="action_btn"
            type="button"
            :disabled="!props.workspace_id"
            @click="copy_text(props.workspace_id, t('room.workspaceQuickSaveCard.status.copiedWorkspaceId'))"
          >
            {{ t('room.workspaceQuickSaveCard.actions.copyWorkspaceId') }}
          </button>
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">
          {{ t('room.workspaceQuickSaveCard.sections.recommendedPaths') }}
        </div>
        <div class="path_list">
          <div class="path_row">
            <span class="path_label">{{ t('room.workspaceQuickSaveCard.paths.roomNote') }}</span>
            <code class="path_value">{{ room_note_path || t('room.workspaceQuickSaveCard.common.dash') }}</code>
          </div>
          <div class="path_row">
            <span class="path_label">{{ t('room.workspaceQuickSaveCard.paths.agentNotebook') }}</span>
            <code class="path_value">{{ agent_notebook_path || t('room.workspaceQuickSaveCard.common.dash') }}</code>
          </div>
          <div class="path_row">
            <span class="path_label">{{ t('room.workspaceQuickSaveCard.paths.focusRoot') }}</span>
            <code class="path_value">{{ visible_focus_root || t('room.workspaceQuickSaveCard.common.dash') }}</code>
          </div>
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">
          {{ t('room.workspaceQuickSaveCard.sections.draft') }}
        </div>
        <textarea
          v-model="draft_text"
          class="draft_textarea"
          :placeholder="t('room.workspaceQuickSaveCard.fields.draftPlaceholder')"
        />
        <div class="draft_actions">
          <button
            class="small_btn"
            type="button"
            :disabled="!draft_trimmed"
            @click="copy_text(draft_trimmed, t('room.workspaceQuickSaveCard.status.copiedDraft'))"
          >
            {{ t('room.workspaceQuickSaveCard.actions.copyDraft') }}
          </button>
          <button
            class="small_btn"
            type="button"
            :disabled="!draft_trimmed || !room_note_path"
            @click="open_relative_path(room_note_path, 'roomNote')"
          >
            {{ t('room.workspaceQuickSaveCard.actions.openRoomNotePaste') }}
          </button>
          <button
            class="small_btn subtle"
            type="button"
            :disabled="!draft_text"
            @click="clear_draft"
          >
            {{ t('room.workspaceQuickSaveCard.actions.clear') }}
          </button>
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">
          {{ t('room.workspaceQuickSaveCard.sections.roomInfo') }}
        </div>
        <div class="mini_facts">
          <div class="mini_fact">
            <span>{{ t('room.workspaceQuickSaveCard.facts.roomId') }}</span>
            <strong>{{ props.room_id || t('room.workspaceQuickSaveCard.common.dash') }}</strong>
          </div>
          <div class="mini_fact">
            <span>{{ t('room.workspaceQuickSaveCard.facts.defaultAgent') }}</span>
            <strong>{{ props.default_agent_id || t('room.workspaceQuickSaveCard.common.defaultAgentFallback') }}</strong>
          </div>
          <div class="mini_fact">
            <span>{{ t('room.workspaceQuickSaveCard.facts.activeRoles') }}</span>
            <strong>{{ active_role_count }}</strong>
          </div>
          <div class="mini_fact">
            <span>{{ t('room.workspaceQuickSaveCard.facts.replyMode') }}</span>
            <strong>{{ reply_mode_text }}</strong>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'

const props = defineProps({
  workspace_ready: { type: Boolean, default: false },
  workspace_id: { type: String, default: '' },
  focus_root: { type: String, default: '' },
  room_id: { type: String, default: '' },
  room_state: { type: Object, default: () => ({}) },
  snapshot: { type: Object, default: () => ({}) },
  default_agent_id: { type: String, default: 'agent' },
})

const emit = defineEmits(['saved', 'status', 'open_relative_path'])

const { t } = useI18n()
const draft_text = ref('')

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function normalize_relative_path(value) {
  let s = safe_string(value).trim().replace(/\\\\/g, '/')
  while (s.includes('//')) s = s.replace(/\/\//g, '/')
  s = s.replace(/^\/+|\/+$/g, '')
  const parts = s
    .split('/')
    .map((item) => safe_string(item).trim())
    .filter((item) => item && item !== '.' && item !== '..')
  return parts.join('/')
}

function display_path(path) {
  const raw = safe_string(path).trim()
  if (!raw) return ''
  const visible = safe_string(to_user_visible_path(raw)).trim()
  return visible || raw
}

const room_note_path = computed(() => {
  return normalize_relative_path(props.snapshot?.suggested_room_note_relative_path || '')
})

const agent_notebook_path = computed(() => {
  return normalize_relative_path(props.snapshot?.suggested_agent_notebook_relative_path || '')
})

const visible_focus_root = computed(() => {
  return display_path(props.focus_root)
})

const draft_trimmed = computed(() => safe_string(draft_text.value).trim())

const active_role_count = computed(() => {
  return Array.isArray(props.room_state?.active_roles) ? props.room_state.active_roles.length : 0
})

const reply_mode_text = computed(() => {
  const mode = safe_string(props.room_state?.reply_mode || 'manual').trim() || 'manual'
  const key_map = {
    manual: 'manual',
    direct_role: 'directRole',
    supervisor_direct: 'supervisorDirect',
    supervisor: 'supervisor',
  }
  const key = key_map[mode]
  return key ? t(`room.workspaceQuickSaveCard.replyModes.${key}`) : mode
})

function resolve_path_label(label) {
  const key_map = {
    roomNote: 'roomNote',
    agentNotebook: 'agentNotebook',
    path: 'path',
  }
  const key = key_map[label] || 'path'
  return t(`room.workspaceQuickSaveCard.pathLabels.${key}`)
}

async function copy_text(value, success_message = '') {
  const text = safe_string(value).trim()
  if (!text) {
    emit('status', {
      message: t('room.workspaceQuickSaveCard.status.noContent'),
      is_error: true,
    })
    return
  }

  try {
    await navigator.clipboard.writeText(text)
    emit('status', {
      message: success_message || t('room.workspaceQuickSaveCard.status.copied'),
      is_error: false,
    })
  } catch {
    emit('status', {
      message: t('room.workspaceQuickSaveCard.status.copyFailed'),
      is_error: true,
    })
  }
}

function open_relative_path(path, label = 'path') {
  const normalized = normalize_relative_path(path)
  if (!normalized) {
    emit('status', {
      message: t('room.workspaceQuickSaveCard.status.pathEmpty'),
      is_error: true,
    })
    return
  }

  emit('open_relative_path', normalized)
  emit('saved', {
    relative_path: normalized,
    message: t('room.workspaceQuickSaveCard.status.savedPathMessage', {
      label: resolve_path_label(label),
      path: normalized,
    }),
  })
}

function clear_draft() {
  draft_text.value = ''
  emit('status', {
    message: t('room.workspaceQuickSaveCard.status.draftCleared'),
    is_error: false,
  })
}
</script>

<style scoped>
.quick_card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  padding: 0.95rem;
  min-width: 0;
}

.card_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
}

.card_title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 700;
}

.card_subtitle {
  margin-top: 0.25rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.state_badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.62rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--sidebar-bg);
  color: var(--text-secondary);
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.state_badge.active {
  border-color: rgba(46, 139, 87, 0.3);
  color: #2e8b57;
  background: rgba(46, 139, 87, 0.08);
}

.section_block {
  margin-top: 0.95rem;
  padding-top: 0.95rem;
  border-top: 1px solid var(--line);
}

.section_title {
  color: var(--text-main);
  font-size: 0.87rem;
  font-weight: 700;
  margin-bottom: 0.65rem;
}

.action_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.action_btn,
.small_btn {
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--sidebar-bg);
  color: var(--text-main);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action_btn {
  min-height: 40px;
  padding: 0.65rem 0.75rem;
  font-size: 0.84rem;
}

.action_btn.primary {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.08);
}

.action_btn:hover:not(:disabled),
.small_btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.action_btn:disabled,
.small_btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.path_list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.path_row {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.62rem 0.68rem;
}

.path_label {
  display: block;
  color: var(--text-secondary);
  font-size: 0.74rem;
  margin-bottom: 0.22rem;
}

.path_value {
  display: block;
  color: var(--text-main);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
  word-break: break-all;
  white-space: pre-wrap;
}

.draft_textarea {
  width: 100%;
  min-height: 128px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  color: var(--text-main);
  padding: 0.75rem 0.8rem;
  box-sizing: border-box;
  font-family: inherit;
  outline: none;
}

.draft_textarea:focus {
  border-color: var(--selected);
}

.draft_actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.small_btn {
  min-height: 34px;
  padding: 0 0.75rem;
  font-size: 0.78rem;
}

.small_btn.subtle {
  color: var(--text-secondary);
}

.mini_facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.mini_fact {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.62rem 0.68rem;
  min-width: 0;
}

.mini_fact span {
  display: block;
  color: var(--text-secondary);
  font-size: 0.74rem;
  margin-bottom: 0.2rem;
}

.mini_fact strong {
  display: block;
  color: var(--text-main);
  font-size: 0.82rem;
  word-break: break-word;
}

.empty_block {
  margin-top: 0.95rem;
  padding: 0.9rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

@media (max-width: 720px) {
  .card_head {
    flex-direction: column;
    align-items: stretch;
  }

  .action_grid,
  .mini_facts {
    grid-template-columns: 1fr;
  }

  .draft_actions {
    flex-direction: column;
  }
}
</style>

