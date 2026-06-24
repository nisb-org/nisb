<template>
  <section class="section_card">
    <div class="section_title">
      {{ t('room.settingsWorkspaceCard.workspaceContext.title') }}
    </div>
    <div class="section_subtitle">
      {{ t('room.settingsWorkspaceCard.workspaceContext.description') }}
    </div>

    <div class="form_grid top_gap">
      <label class="field field_full">
        <span>{{ t('room.settingsWorkspaceCard.fields.workspace.label') }}</span>
        <select
          :value="form.workspace_id"
          :disabled="busy || workspace_options_loading || workspace_focus_loading"
          @change="onWorkspaceChange"
        >
          <option value="">
            {{ t('room.settingsWorkspaceCard.fields.workspace.unboundOption') }}
          </option>
          <option
            v-for="workspace in workspace_options"
            :key="String(workspace.id || '')"
            :value="String(workspace.id || '')"
          >
            {{ workspace.display_name || workspace.name || workspace.id }}
          </option>
        </select>
        <div class="field_hint">
          {{ t('room.settingsWorkspaceCard.fields.workspace.hint') }}
        </div>
      </label>

      <div class="field readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.fields.workspaceId.label') }}</span>
        <div class="readonly_box">
          {{ form.workspace_id || t('room.settingsWorkspaceCard.common.unbound') }}
        </div>
      </div>

      <div class="field readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.fields.workspaceName.label') }}</span>
        <div class="readonly_box">
          {{ form.workspace_name || t('room.settingsWorkspaceCard.common.unbound') }}
        </div>
      </div>

      <div class="field field_full readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.fields.focusRoot.label') }}</span>
        <div class="readonly_box">
          {{ visibleFocusRoot || t('room.settingsWorkspaceCard.fields.focusRoot.unbound') }}
        </div>
        <div class="field_hint">
          {{ t('room.settingsWorkspaceCard.fields.focusRoot.hint') }}
        </div>
      </div>

      <div class="field field_full readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.fields.focusLabel.label') }}</span>
        <div class="readonly_box">
          {{ form.focus_label || t('room.settingsWorkspaceCard.fields.focusLabel.unbound') }}
        </div>
      </div>
    </div>

    <div v-if="workspace_options_error" class="warning_box warning_box_warn top_gap">
      {{ workspace_options_error }}
    </div>

    <div v-else-if="workspace_options_loading || workspace_focus_loading" class="helper_text">
      {{ t('room.settingsWorkspaceCard.loading.workspaceOptions') }}
    </div>

    <div class="context_actions">
      <button
        class="ghost_btn"
        type="button"
        :disabled="busy || !room_id_value || !form.workspace_id"
        @click="apply_context_to_sidebar"
      >
        {{ t('room.settingsWorkspaceCard.actions.applyToSidebarPreview') }}
      </button>

      <button
        class="ghost_btn"
        type="button"
        :disabled="busy || !room_id_value || !form.focus_root"
        @click="clear_focus_root_only"
      >
        {{ t('room.settingsWorkspaceCard.actions.clearFocusRootOnly') }}
      </button>

      <button
        class="danger_btn"
        type="button"
        :disabled="busy || !room_id_value"
        @click="clear_workspace_context_all"
      >
        {{ t('room.settingsWorkspaceCard.actions.clearWorkspaceContextAll') }}
      </button>
    </div>

    <div class="section_title top_gap">
      {{ t('room.settingsWorkspaceCard.supervisorSkills.title') }}
    </div>
    <div class="section_subtitle">
      {{ t('room.settingsWorkspaceCard.supervisorSkills.description') }}
    </div>

    <div class="context_actions top_gap">
      <button
        class="ghost_btn"
        type="button"
        :disabled="skillsRefreshDisabled"
        @click="onRefreshSupervisorSkills"
      >
        {{
          supervisor_skills_loading
            ? t('room.settingsWorkspaceCard.loading.refresh')
            : t('room.settingsWorkspaceCard.actions.refreshSkills')
        }}
      </button>
    </div>

    <div class="form_grid top_gap">
      <div class="field readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.stats.enabledCount') }}</span>
        <div class="readonly_box">
          {{ skillsHasResult ? enabled_supervisor_skill_count : t('room.settingsWorkspaceCard.common.dash') }}
        </div>
      </div>

      <div class="field readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.stats.itemsCount') }}</span>
        <div class="readonly_box">
          {{ skillsHasResult ? skillsItems.length : t('room.settingsWorkspaceCard.common.dash') }}
        </div>
      </div>

      <div class="field field_full readonly_field">
        <span>{{ t('room.settingsWorkspaceCard.stats.skillsRoot') }}</span>
        <div class="readonly_box">
          {{
            skillsHasResult
              ? (visibleSkillsRoot || t('room.settingsWorkspaceCard.common.dash'))
              : t('room.settingsWorkspaceCard.common.dash')
          }}
        </div>
      </div>
    </div>

    <div v-if="!room_id_value" class="helper_text top_gap">
      {{ t('room.settingsWorkspaceCard.supervisorSkills.noRoomId') }}
    </div>

    <div v-else-if="!form.workspace_id" class="helper_text top_gap">
      {{ t('room.settingsWorkspaceCard.supervisorSkills.noWorkspace') }}
    </div>

    <div v-else-if="!form.focus_root" class="helper_text top_gap">
      {{ t('room.settingsWorkspaceCard.supervisorSkills.noFocusRoot') }}
    </div>

    <div v-else-if="supervisor_skills_error" class="warning_box warning_box_warn top_gap">
      {{ supervisor_skills_error }}
    </div>

    <div v-else-if="supervisor_skills_loading" class="helper_text top_gap">
      {{ t('room.settingsWorkspaceCard.loading.supervisorSkills') }}
    </div>

    <template v-else-if="skillsHasResult">
      <div v-if="skillsItems.length" class="skills_list top_gap">
        <div
          v-for="item in skillsItems"
          :key="String(item.skill_id || item.relative_path || item.filename || item.title || '')"
          class="skill_card"
          :class="{ skill_card_active: isLocalEnabled(item.skill_id) }"
        >
          <label class="skill_checkbox_line">
            <input
              type="checkbox"
              :checked="isLocalEnabled(item.skill_id)"
              :disabled="busy"
              @change="onToggleSupervisorSkill(item.skill_id)"
            />

            <div class="skill_body">
              <div class="skill_title_row">
                <div class="skill_title">
                  {{ item.title || item.name || item.skill_id || t('room.settingsWorkspaceCard.skillCard.untitled') }}
                </div>

                <div class="skill_tags">
                  <span class="tag" :class="{ tag_active: isSavedEnabled(item) }">
                    {{
                      t('room.settingsWorkspaceCard.skillCard.saved', {
                        value: booleanText(isSavedEnabled(item)),
                      })
                    }}
                  </span>
                  <span class="tag" :class="{ tag_active: isLocalEnabled(item.skill_id) }">
                    {{
                      t('room.settingsWorkspaceCard.skillCard.local', {
                        value: booleanText(isLocalEnabled(item.skill_id)),
                      })
                    }}
                  </span>
                </div>
              </div>

              <div class="skill_path">
                {{ displaySkillPath(item) }}
              </div>

              <div class="field_hint">
                {{
                  t('room.settingsWorkspaceCard.skillCard.meta', {
                    skillId: item.skill_id || t('room.settingsWorkspaceCard.common.dash'),
                    size: item.size ?? 0,
                    updatedAt: item.updated_at || t('room.settingsWorkspaceCard.common.dash'),
                  })
                }}
              </div>
            </div>
          </label>
        </div>
      </div>

      <div v-else class="helper_text top_gap">
        {{ t('room.settingsWorkspaceCard.supervisorSkills.empty') }}
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'

const props = defineProps({
  form: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  room_id_value: { type: String, default: '' },
  workspace_options: { type: Array, default: () => [] },
  workspace_options_loading: { type: Boolean, default: false },
  workspace_focus_loading: { type: Boolean, default: false },
  workspace_options_error: { type: String, default: '' },
  handle_workspace_selection_change: { type: Function, required: true },
  apply_context_to_sidebar: { type: Function, required: true },
  clear_focus_root_only: { type: Function, required: true },
  clear_workspace_context_all: { type: Function, required: true },

  supervisor_skills_loading: { type: Boolean, default: false },
  supervisor_skills_error: { type: String, default: '' },
  supervisor_skills_result: { type: Object, default: () => ({}) },
  enabled_supervisor_skill_count: { type: Number, default: 0 },
  refresh_supervisor_skills: { type: Function, default: async () => {} },
  toggle_supervisor_skill: { type: Function, default: () => {} },
  is_supervisor_skill_enabled_locally: { type: Function, default: () => false },
  get_saved_supervisor_skill_enabled: { type: Function, default: () => false },
})

const { t } = useI18n()

function isPlainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function displayPath(path) {
  const raw = String(path || '').trim()
  if (!raw) return ''
  const visible = String(to_user_visible_path(raw) || '').trim()
  return visible || raw
}

const skillsResult = computed(() => {
  return isPlainObject(props.supervisor_skills_result) ? props.supervisor_skills_result : {}
})

const skillsItems = computed(() => {
  return Array.isArray(skillsResult.value.items) ? skillsResult.value.items : []
})

const skillsHasResult = computed(() => {
  return Object.keys(skillsResult.value).length > 0
})

const skillsRoot = computed(() => {
  return String(skillsResult.value.skills_root || '').trim()
})

const visibleFocusRoot = computed(() => {
  return displayPath(props.form?.focus_root)
})

const visibleSkillsRoot = computed(() => {
  return displayPath(skillsRoot.value)
})

const skillsRefreshDisabled = computed(() => {
  return (
    props.busy ||
    props.supervisor_skills_loading ||
    !props.room_id_value ||
    !props.form?.workspace_id ||
    !props.form?.focus_root
  )
})

function booleanText(value) {
  return value
    ? t('room.settingsWorkspaceCard.common.trueValue')
    : t('room.settingsWorkspaceCard.common.falseValue')
}

function displaySkillPath(item) {
  const raw = String(item?.relative_path || '').trim()
  if (!raw) return t('room.settingsWorkspaceCard.common.dash')
  return displayPath(raw) || t('room.settingsWorkspaceCard.common.dash')
}

function onWorkspaceChange(event) {
  const value = String(event?.target?.value || '').trim()
  props.handle_workspace_selection_change(value)
}

async function onRefreshSupervisorSkills() {
  await props.refresh_supervisor_skills()
}

function onToggleSupervisorSkill(skillId) {
  props.toggle_supervisor_skill(skillId)
}

function isLocalEnabled(skillId) {
  return !!props.is_supervisor_skill_enabled_locally(skillId)
}

function isSavedEnabled(skill) {
  return !!props.get_saved_supervisor_skill_enabled(skill)
}
</script>

<style scoped>
.skills_list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.8rem;
}

.skill_card {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.85rem;
  transition: all 0.2s ease;
}

.skill_card_active {
  border-color: var(--selected);
  background: var(--selected-bg);
}

.skill_checkbox_line {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
}

.skill_checkbox_line input {
  margin-top: 0.2rem;
}

.skill_body {
  min-width: 0;
  flex: 1;
}

.skill_title_row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.skill_title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.4;
  word-break: break-word;
}

.skill_tags {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.skill_path {
  margin-top: 0.55rem;
  color: var(--text-secondary);
  font-size: 0.78rem;
  word-break: break-all;
}
</style>

