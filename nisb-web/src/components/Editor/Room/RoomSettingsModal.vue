<template>
  <div
    v-if="visible"
    class="modal_mask"
    role="presentation"
    @click="close_modal"
  >
    <div
      class="modal_panel"
      role="dialog"
      aria-modal="true"
      :aria-label="t('room.settingsModal.title')"
      @click.stop
    >
      <div class="modal_header">
        <div class="modal_title_block">
          <div class="modal_kicker">
            <span class="kicker_dot"></span>
            <span>{{ t('room.settingsModal.kicker') }}</span>
          </div>

          <h3>{{ t('room.settingsModal.title') }}</h3>

          <p class="modal_desc">
            {{ t('room.settingsModal.description') }}
          </p>
        </div>

        <button
          class="close_btn"
          type="button"
          :title="t('room.settingsModal.actions.close')"
          :aria-label="t('room.settingsModal.actions.close')"
          @click="close_modal"
        >
          ×
        </button>
      </div>

      <div class="modal_body">
        <RoomSettingsBasicCard
          :form="form"
          :show_federation_section="show_federation_section"
          :can_manage_federation="can_manage_federation"
          :can_issue_federation_invite="can_issue_federation_invite"
          :federation_peers="federation_peers"
          :federation_target_peer_id="federation_target_peer_id"
          :federation_invite_ttl_seconds="federation_invite_ttl_seconds"
          :federation_invite_ttl_options="federation_invite_ttl_options"
          :federation_invite_history_filter="federation_invite_history_filter"
          :federation_invite_history_filter_options="federation_invite_history_filter_options"
          :federation_invite_busy="federation_invite_busy"
          :federation_invite_error="federation_invite_error"
          :federation_last_invite="federation_last_invite"
          :federation_invites="federation_invites"
          :federation_invites_loading="federation_invites_loading"
          :federation_invites_error="federation_invites_error"
          :federation_revoke_busy_invite_id="federation_revoke_busy_invite_id"
          :federation_extend_busy_invite_id="federation_extend_busy_invite_id"
          :federation_joined_members="federation_joined_members"
          :federation_joined_members_loading="federation_joined_members_loading"
          :federation_joined_members_error="federation_joined_members_error"
          :federation_revoke_member_busy_uid="federation_revoke_member_busy_uid"
          :federation_summary_counts="federation_summary_counts"
          :federation_summary_notes="federation_summary_notes"
          :issue_federation_room_invite="issue_federation_room_invite"
          :refresh_federation_room_invites="refresh_federation_room_invites"
          :refresh_federation_joined_members="refresh_federation_joined_members"
          :revoke_federation_room_invite="revoke_federation_room_invite"
          :revoke_federated_member_access="revoke_federated_member_access"
          :set_federation_invite_history_filter="set_federation_invite_history_filter"
          :extend_federation_room_invite="extend_federation_room_invite"
          @update:federation_target_peer_id="federation_target_peer_id = $event"
          @update:federation_invite_ttl_seconds="federation_invite_ttl_seconds = $event"
        />

        <RoomSettingsOrchestrationCard
          :key="orchestration_card_key"
          :form="form"
          :roles="roles"
          :default_role_label="default_role_label"
          :show_supervisor_settings="show_supervisor_settings"
          :reply_mode_supervisor_warning="reply_mode_supervisor_warning"
          :reply_mode_supervisor_direct_warning="reply_mode_supervisor_direct_warning"
          :reply_mode_direct_role_warning="reply_mode_direct_role_warning"
          :orchestration_summary="orchestration_summary"
          :supervisor_fs_audit="supervisor_fs_audit"
          :supervisor_notebook_audit="supervisor_notebook_audit"
          :fs_tool_call_count="fs_tool_call_count"
          :fs_tool_result_count="fs_tool_result_count"
          :notebook_tool_call_count="notebook_tool_call_count"
          :notebook_tool_result_count="notebook_tool_result_count"
          :normalized_workspace_id_preview="normalized_workspace_id_preview"
          :normalized_focus_root_preview="normalized_focus_root_preview"
          :room_mcp_publication="room_mcp_publication"
          :room_mcp_share_ref_preview="room_mcp_share_ref_preview"
          :room_mcp_share_ref_loading="room_mcp_share_ref_loading"
          :room_mcp_share_ref_error="room_mcp_share_ref_error"
          :room_mcp_share_ref_last_issued_at="room_mcp_share_ref_last_issued_at"
          :room_mcp_share_ref_status="room_mcp_share_ref_status"
          :room_mcp_grants="room_mcp_grants"
          :room_mcp_grants_loading="room_mcp_grants_loading"
          :room_mcp_grants_status="room_mcp_grants_status"
          :room_mcp_grant_revoke_loading_id="room_mcp_grant_revoke_loading_id"
          :external_mcp_publish_status="external_mcp_publish_status"
          :external_mcp_publish_loading="external_mcp_publish_loading"
          :external_mcp_publish_error="external_mcp_publish_error"
          :external_mcp_publish_plaintext_token="external_mcp_publish_plaintext_token"
          :external_mcp_publish_copy_loading_kind="external_mcp_publish_copy_loading_kind"
          :external_mcp_publish_enable_loading="external_mcp_publish_enable_loading"
          :external_mcp_publish_revoke_loading="external_mcp_publish_revoke_loading"
          :external_mcp_publish_regenerate_loading="external_mcp_publish_regenerate_loading"
          :role_label="role_label"
          :handle_default_role_change="handle_default_role_change"
          :handle_reply_mode_change="handle_reply_mode_change"
          :handle_supervisor_provider_change="handle_supervisor_provider_change"
          :handle_room_mcp_share_ref_generate="handle_room_mcp_share_ref_generate"
          :handle_room_mcp_share_ref_copy="handle_room_mcp_share_ref_copy"
          :handle_room_mcp_grant_list_refresh="handle_room_mcp_grant_list_refresh"
          :handle_room_mcp_grant_revoke="handle_room_mcp_grant_revoke"
          :handle_external_mcp_publish_enable="handle_external_mcp_publish_enable"
          :handle_external_mcp_publish_revoke="handle_external_mcp_publish_revoke"
          :handle_external_mcp_publish_regenerate="handle_external_mcp_publish_regenerate"
          :handle_external_mcp_publish_copy_config="handle_external_mcp_publish_copy_config"
          :handle_external_mcp_publish_copy_token="handle_external_mcp_publish_copy_token"
          :refresh_external_mcp_publish="refresh_external_mcp_publish"
        />

        <RoomSettingsRolesCard
          :form="form"
          :roles="roles"
          :busy="busy"
          :can_manage_room_roles="can_manage_room_roles"
          :is_room_owner="is_room_owner"
          :is_explicit_member_readonly="is_explicit_member_readonly"
          :is_role_shared="(roleId) => shared_role_ids_set.has(String(roleId || ''))"
          :is_role_active="is_role_active"
          :toggle_active_role="toggle_active_role"
          :select_all_roles="select_all_roles"
          :clear_active_roles="clear_active_roles"
          :keep_only_default_role="keep_only_default_role"
          :set_default_role="set_default_role"
        />

        <RoomSettingsWorkspaceCard
          :form="form"
          :busy="busy"
          :room_id_value="room_id_value"
          :workspace_options="workspace_options"
          :workspace_options_loading="workspace_options_loading"
          :workspace_focus_loading="workspace_focus_loading"
          :workspace_options_error="workspace_options_error"
          :handle_workspace_selection_change="handle_workspace_selection_change"
          :apply_context_to_sidebar="apply_context_to_sidebar"
          :clear_focus_root_only="clear_focus_root_only"
          :clear_workspace_context_all="clear_workspace_context_all"
          :supervisor_skills_loading="supervisor_skills_loading"
          :supervisor_skills_error="supervisor_skills_error"
          :supervisor_skills_result="supervisor_skills_result"
          :enabled_supervisor_skill_count="enabled_supervisor_skill_count"
          :refresh_supervisor_skills="refresh_supervisor_skills"
          :toggle_supervisor_skill="toggle_supervisor_skill"
          :is_supervisor_skill_enabled_locally="is_supervisor_skill_enabled_locally"
          :get_saved_supervisor_skill_enabled="get_saved_supervisor_skill_enabled"
        />
      </div>

      <div class="modal_footer">
        <div class="footer_hint">
          {{ footer_hint_text }}
        </div>

        <div class="footer_actions">
          <button class="ghost_btn" type="button" @click="close_modal">
            {{ t('room.settingsModal.actions.cancel') }}
          </button>

          <button
            class="primary_btn"
            type="button"
            @click="submit_and_close"
            :disabled="busy || !room_id_value || !can_edit_room_state"
          >
            {{ busy ? t('room.settingsModal.actions.saving') : t('room.settingsModal.actions.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import RoomSettingsBasicCard from './RoomSettingsBasicCard.vue'
import RoomSettingsOrchestrationCard from './RoomSettingsOrchestrationCard.vue'
import RoomSettingsRolesCard from './RoomSettingsRolesCard.vue'
import RoomSettingsWorkspaceCard from './RoomSettingsWorkspaceCard.vue'
import { use_room_settings_form } from '../../../composables/editor/room/use_room_settings_form'

const props = defineProps({
  visible: { type: Boolean, default: false },
  room_id: { type: String, default: '' },
})

const emit = defineEmits(['close'])
const { t } = useI18n()

const {
  busy,
  form,
  room_id_value,
  roles,

  is_room_owner,
  is_explicit_member_readonly,
  can_edit_room_state,
  can_manage_room_roles,
  show_federation_section,
  can_manage_federation,
  can_issue_federation_invite,
  shared_role_ids_set,

  federation_peers,
  federation_target_peer_id,
  federation_invite_ttl_seconds,
  federation_invite_ttl_options,
  federation_invite_history_filter,
  federation_invite_history_filter_options,
  federation_invite_busy,
  federation_invite_error,
  federation_last_invite,
  federation_invites,
  federation_invites_loading,
  federation_invites_error,
  federation_revoke_busy_invite_id,
  federation_extend_busy_invite_id,

  federation_joined_members,
  federation_joined_members_loading,
  federation_joined_members_error,
  federation_revoke_member_busy_uid,
  federation_summary_counts,
  federation_summary_notes,

  set_federation_invite_history_filter,
  refresh_federation_room_invites,
  refresh_federation_joined_members,
  issue_federation_room_invite,
  revoke_federation_room_invite,
  revoke_federated_member_access,
  extend_federation_room_invite,

  supervisor_fs_audit,
  supervisor_notebook_audit,
  fs_tool_call_count,
  fs_tool_result_count,
  notebook_tool_call_count,
  notebook_tool_result_count,
  normalized_workspace_id_preview,
  normalized_focus_root_preview,
  default_role_label,
  show_supervisor_settings,
  reply_mode_supervisor_warning,
  reply_mode_supervisor_direct_warning,
  reply_mode_direct_role_warning,
  orchestration_summary,

  room_mcp_publication,

  room_mcp_share_ref_preview,
  room_mcp_share_ref_loading,
  room_mcp_share_ref_error,
  room_mcp_share_ref_last_issued_at,
  room_mcp_share_ref_status,

  room_mcp_grants,
  room_mcp_grants_loading,
  room_mcp_grants_status,
  room_mcp_grant_revoke_loading_id,

  external_mcp_publish_status,
  external_mcp_publish_loading,
  external_mcp_publish_error,
  external_mcp_publish_plaintext_token,
  external_mcp_publish_copy_loading_kind,
  external_mcp_publish_enable_loading,
  external_mcp_publish_revoke_loading,
  external_mcp_publish_regenerate_loading,

  role_label,
  is_role_active,
  set_default_role,
  handle_default_role_change,
  handle_reply_mode_change,
  handle_supervisor_provider_change,
  handle_room_mcp_share_ref_generate,
  handle_room_mcp_share_ref_copy,
  handle_room_mcp_grant_list_refresh,
  handle_room_mcp_grant_revoke,
  handle_external_mcp_publish_enable,
  handle_external_mcp_publish_revoke,
  handle_external_mcp_publish_regenerate,
  handle_external_mcp_publish_copy_config,
  handle_external_mcp_publish_copy_token,
  refresh_external_mcp_publish,

  toggle_active_role,
  select_all_roles,
  clear_active_roles,
  keep_only_default_role,
  workspace_options,
  workspace_options_loading,
  workspace_focus_loading,
  workspace_options_error,
  handle_workspace_selection_change,
  apply_context_to_sidebar,
  clear_focus_root_only,
  clear_workspace_context_all,
  supervisor_skills_loading,
  supervisor_skills_error,
  supervisor_skills_result,
  enabled_supervisor_skill_count,
  refresh_supervisor_skills,
  toggle_supervisor_skill,
  is_supervisor_skill_enabled_locally,
  get_saved_supervisor_skill_enabled,
  submit_save,
} = use_room_settings_form(props)

const orchestration_card_key = computed(() => {
  const current_room_id = String(room_id_value?.value || props.room_id || '').trim()
  return current_room_id || 'room-settings-orchestration'
})

const footer_hint_text = computed(() => {
  if (is_explicit_member_readonly.value) {
    return t('room.settingsModal.footer.readonlyFederation')
  }

  if (form.p6_test_panel_enabled && form.p6_notebook_probe_actor === 'supervisor') {
    return t('room.settingsModal.footer.p6Supervisor')
  }

  if (form.p6_test_panel_enabled && form.p6_notebook_probe_actor === 'worker') {
    return t('room.settingsModal.footer.p6Worker')
  }

  if (form.p6_test_panel_enabled && form.p6_notebook_probe_actor === 'skill') {
    return t('room.settingsModal.footer.p6Skill')
  }

  if (form.reply_mode === 'supervisor') {
    return t('room.settingsModal.footer.supervisorMode', {
      provider: form.supervisor_provider || t('room.settingsModal.common.defaultProvider'),
      model: form.supervisor_model || t('room.settingsModal.common.systemDefault'),
      fsRead: form.supervisor_fs_read_enabled
        ? t('room.settingsModal.common.on')
        : t('room.settingsModal.common.off'),
      notebook: form.supervisor_notebook_write_enabled
        ? t('room.settingsModal.common.on')
        : t('room.settingsModal.common.off'),
    })
  }

  if (form.default_reply_role_id) {
    return t('room.settingsModal.footer.defaultRole', {
      role: default_role_label.value,
    })
  }

  return t('room.settingsModal.footer.fallback')
})

function close_modal() {
  if (busy.value) return
  emit('close')
}

async function submit_and_close() {
  await submit_save({
    on_success: () => emit('close'),
  })
}

function on_keydown(e) {
  if (!props.visible) return
  if (e.key !== 'Escape') return
  close_modal()
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      window.addEventListener('keydown', on_keydown)
      return
    }

    window.removeEventListener('keydown', on_keydown)
  },
  { immediate: true }
)

onUnmounted(() => {
  window.removeEventListener('keydown', on_keydown)
})
</script>

<style scoped>
.modal_mask {
  position: fixed;
  inset: 0;
  z-index: 1250;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background:
    radial-gradient(circle at 22% 12%, rgba(84, 130, 197, 0.18), transparent 32%),
    rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
}

.modal_panel {
  width: min(1120px, 96vw);
  height: min(900px, 92vh);
  max-height: 92vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--sidebar-bg) 96%, transparent);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.035) inset;
}

.modal_header {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid var(--line);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 98%, var(--selected-bg) 2%),
      var(--sidebar-bg)
    );
}

.modal_title_block {
  min-width: 0;
}

.modal_kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 24px;
  padding: 0 9px;
  margin-bottom: 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 26%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 72%, transparent);
  color: var(--selected);
  font-size: 0.74rem;
  font-weight: 750;
  line-height: 1;
}

.kicker_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 15%, transparent);
}

.modal_header h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.22rem;
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.025em;
}

.modal_desc {
  max-width: 72rem;
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.55;
}

.modal_body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      var(--editor-bg)
    );
}

.modal_body::-webkit-scrollbar {
  width: 10px;
}

.modal_body::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background-clip: content-box;
  background-color: color-mix(in srgb, var(--text-secondary) 35%, transparent);
}

/* Shared child-card system */
:deep(.section_card) {
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--sidebar-bg) 92%, transparent);
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 14px;
  box-shadow:
    0 8px 24px rgba(0, 0, 0, 0.035),
    0 0 0 1px rgba(255, 255, 255, 0.025) inset;
}

:deep(.section_card:last-child) {
  margin-bottom: 0;
}

:deep(.section_head) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

:deep(.section_title) {
  color: var(--text-main);
  font-size: 0.96rem;
  font-weight: 800;
  line-height: 1.32;
  letter-spacing: -0.012em;
}

:deep(.section_subtitle) {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
}

:deep(.section_actions) {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
}

:deep(.top_gap) {
  margin-top: 12px;
}

/* Form system */
:deep(.form_grid) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

:deep(.field) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

:deep(.field span) {
  font-size: 0.8rem;
  font-weight: 650;
  color: var(--text-secondary);
  line-height: 1.35;
}

:deep(.field input),
:deep(.field textarea),
:deep(.field select) {
  width: 100%;
  min-height: 40px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  padding: 9px 11px;
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.45;
  outline: none;
  transition:
    background var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    border-color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    box-shadow var(--transition-normal, 0.18s) var(--ease-smooth, ease);
}

:deep(.field textarea) {
  resize: vertical;
  min-height: 92px;
}

:deep(.field input:focus),
:deep(.field textarea:focus),
:deep(.field select:focus) {
  border-color: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

:deep(.field input:disabled),
:deep(.field textarea:disabled),
:deep(.field select:disabled) {
  opacity: 0.62;
  cursor: not-allowed;
}

:deep(.field_full) {
  grid-column: 1 / -1;
}

:deep(.field_hint) {
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.55;
}

/* Readonly/value boxes */
:deep(.readonly_field) {
  min-height: 100%;
}

:deep(.readonly_box) {
  min-height: 40px;
  padding: 9px 11px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  display: flex;
  align-items: center;
  line-height: 1.45;
  word-break: break-word;
}

/* Toggles */
:deep(.toggle_group) {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  overflow: hidden;
}

:deep(.toggle_row) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 13px;
  border-bottom: 1px solid var(--line);
}

:deep(.toggle_row:last-child) {
  border-bottom: none;
}

:deep(.toggle_text) {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

:deep(.toggle_text strong) {
  color: var(--text-main);
  font-size: 0.88rem;
  line-height: 1.35;
}

:deep(.toggle_text span) {
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.45;
}

:deep(.helper_text) {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

/* Code/value text */
:deep(code),
:deep(.helper_text code),
:deep(.warning_box code),
:deep(.audit_card code),
:deep(.readonly_box code) {
  font-family: var(--font-mono);
  font-size: 0.78em;
  word-break: break-all;
}

/* Supervisor / nested panels */
:deep(.supervisor_box) {
  margin-top: 12px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
}

:deep(.supervisor_box_head) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

:deep(.supervisor_capability_box) {
  margin-top: 13px;
  padding-top: 13px;
  border-top: 1px dashed var(--line);
}

:deep(.audit_grid) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

:deep(.audit_card) {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 90%, transparent);
  padding: 12px;
}

:deep(.audit_title) {
  color: var(--text-main);
  font-weight: 800;
  font-size: 0.86rem;
  margin-bottom: 8px;
}

:deep(.audit_line) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
}

:deep(.audit_line:last-child) {
  border-bottom: none;
}

:deep(.audit_line span) {
  color: var(--text-secondary);
  font-size: 0.78rem;
  min-width: 88px;
}

:deep(.audit_line code) {
  color: var(--text-main);
  font-size: 0.76rem;
  text-align: right;
}

/* Notices */
:deep(.warning_box) {
  margin-top: 12px;
  padding: 11px 12px;
  border-radius: 13px;
  border: 1px solid var(--line);
  font-size: 0.82rem;
  line-height: 1.55;
}

:deep(.warning_box_info) {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.085);
  color: var(--text-main);
}

:deep(.warning_box_warn) {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.11);
  color: var(--text-main);
}

/* Roles */
:deep(.role_grid) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

:deep(.role_card) {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  padding: 12px;
  transition:
    background var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    border-color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    box-shadow var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    opacity var(--transition-normal, 0.18s) var(--ease-smooth, ease);
}

:deep(.role_card.active) {
  border-color: color-mix(in srgb, var(--selected) 72%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 70%, var(--editor-bg));
}

:deep(.role_card.default_role) {
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--selected) 26%, transparent),
    0 8px 20px rgba(0, 0, 0, 0.035);
}

:deep(.role_card.disabled_role) {
  opacity: 0.62;
}

:deep(.role_card_top) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

:deep(.role_checkbox_line) {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  flex: 1;
  cursor: pointer;
}

:deep(.role_checkbox_line input) {
  margin-top: 3px;
}

:deep(.role_identity) {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
}

:deep(.role_avatar) {
  font-size: 1.08rem;
  line-height: 1;
}

:deep(.role_name_wrap) {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

:deep(.role_name) {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 720;
  line-height: 1.35;
  word-break: break-word;
}

:deep(.role_slug) {
  color: var(--text-secondary);
  font-size: 0.76rem;
  margin-top: 3px;
  word-break: break-all;
}

:deep(.role_meta_row) {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

:deep(.role_prompt_preview) {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 0.81rem;
  line-height: 1.55;
  max-height: 76px;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Tags/chips */
:deep(.tag) {
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-size: 0.72rem;
  font-weight: 680;
  line-height: 1;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
}

:deep(.tag_active) {
  border-color: color-mix(in srgb, var(--selected) 55%, var(--line));
  color: var(--selected);
  background: color-mix(in srgb, var(--selected-bg) 72%, transparent);
}

:deep(.tag_default) {
  border-color: rgba(59, 130, 246, 0.36);
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.09);
}

:deep(.tag_disabled) {
  border-color: rgba(220, 85, 85, 0.36);
  color: #d55;
  background: rgba(220, 38, 38, 0.07);
}

/* Action rows and empty states */
:deep(.context_actions) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

:deep(.empty_block) {
  margin-top: 12px;
  padding: 14px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  line-height: 1.55;
}

/* Footer */
.modal_footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border-top: 1px solid var(--line);
  background:
    linear-gradient(
      180deg,
      var(--sidebar-bg),
      color-mix(in srgb, var(--sidebar-bg) 96%, var(--editor-bg) 4%)
    );
}

.footer_hint {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.45;
}

.footer_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
}

/* Buttons shared by children */
.primary_btn,
:deep(.ghost_btn),
.close_btn,
:deep(.danger_btn),
:deep(.mini_btn) {
  height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  font-family: inherit;
  font-size: 0.84rem;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  transition:
    background var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    border-color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    color var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    box-shadow var(--transition-normal, 0.18s) var(--ease-smooth, ease),
    opacity var(--transition-normal, 0.18s) var(--ease-smooth, ease);
}

.primary_btn {
  background: var(--selected);
  border-color: var(--selected);
  color: #fff;
}

.primary_btn:hover:not(:disabled) {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 16%, transparent);
}

:deep(.ghost_btn),
.close_btn,
:deep(.danger_btn),
:deep(.mini_btn) {
  color: var(--text-secondary);
}

:deep(.ghost_btn:hover:not(:disabled)),
.close_btn:hover:not(:disabled),
:deep(.mini_btn:hover:not(:disabled)) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 12%, transparent);
}

:deep(.danger_btn:hover:not(:disabled)) {
  background: rgba(220, 38, 38, 0.085);
  border-color: #dc2626;
  color: #dc2626;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
}

.close_btn {
  width: 36px;
  height: 36px;
  padding: 0;
  flex: 0 0 auto;
  font-size: 1.25rem;
  font-weight: 500;
}

:deep(.mini_btn) {
  height: 30px;
  padding: 0 10px;
  font-size: 0.76rem;
  flex-shrink: 0;
}

button:disabled,
:deep(button:disabled) {
  opacity: 0.52;
  cursor: not-allowed;
  box-shadow: none;
}

@media (max-width: 860px) {
  .modal_mask {
    padding: 0;
    align-items: stretch;
  }

  .modal_panel {
    width: 100vw;
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .modal_header {
    padding: 14px;
  }

  .modal_body {
    padding: 12px;
  }

  :deep(.form_grid),
  :deep(.role_grid),
  :deep(.audit_grid) {
    grid-template-columns: 1fr;
  }

  .modal_footer,
  :deep(.section_head),
  :deep(.role_card_top),
  :deep(.supervisor_box_head) {
    flex-direction: column;
    align-items: stretch;
  }

  .footer_actions {
    width: 100%;
  }

  .footer_actions > button {
    flex: 1 1 0;
  }
}
</style>
