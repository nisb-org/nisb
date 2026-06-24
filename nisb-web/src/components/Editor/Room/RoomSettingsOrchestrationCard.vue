<template>
  <section class="section_card orchestration_card">
    <div class="section_head orchestration_head">
      <div class="orchestration_title_block">
        <div class="orchestration_eyebrow">
          <span class="orchestration_dot"></span>
          <span>{{ t('room.settingsOrchestrationCard.eyebrow') }}</span>
        </div>

        <div class="section_title">
          {{ t('room.settingsOrchestrationCard.title') }}
        </div>

        <div class="section_subtitle orchestration_subtitle">
          {{ t('room.settingsOrchestrationCard.subtitle') }}
        </div>
      </div>

      <div class="orchestration_chips">
        <span class="tag" :class="{ tag_active: !!form.shared_room_config_enabled }">
          {{ sharedAutoReplyChipText }}
        </span>

        <span class="tag" :class="{ tag_active: !!form.supervisor_enabled }">
          {{ supervisorChipText }}
        </span>

        <span class="tag tag_default">
          {{ replyModeChipText }}
        </span>

        <span class="tag tag_default">
          {{ workerConcurrencyChipText }}
        </span>
      </div>
    </div>

    <div class="settings_cluster">
      <div class="cluster_head">
        <div>
          <div class="cluster_title">
            {{ t('room.settingsOrchestrationCard.sections.roomBehavior.title') }}
          </div>
          <div class="cluster_subtitle">
            {{ t('room.settingsOrchestrationCard.sections.roomBehavior.subtitle') }}
          </div>
        </div>
      </div>

      <div class="toggle_group orchestration_toggle_group">
        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.settingsOrchestrationCard.toggles.sharedAutoReply.title') }}</strong>
            <span>{{ t('room.settingsOrchestrationCard.toggles.sharedAutoReply.description') }}</span>
          </div>
          <input v-model="form.shared_room_config_enabled" type="checkbox" />
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.settingsOrchestrationCard.toggles.supervisorEnabled.title') }}</strong>
            <span>{{ t('room.settingsOrchestrationCard.toggles.supervisorEnabled.description') }}</span>
          </div>
          <input v-model="form.supervisor_enabled" type="checkbox" />
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.settingsOrchestrationCard.toggles.inheritWorkspaceContext.title') }}</strong>
            <span>{{ t('room.settingsOrchestrationCard.toggles.inheritWorkspaceContext.description') }}</span>
          </div>
          <input v-model="form.inherit_workspace_context" type="checkbox" />
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.settingsOrchestrationCard.toggles.inheritFocusRoot.title') }}</strong>
            <span>{{ t('room.settingsOrchestrationCard.toggles.inheritFocusRoot.description') }}</span>
          </div>
          <input v-model="form.inherit_focus_root" type="checkbox" />
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.settingsOrchestrationCard.toggles.applyAfterSave.title') }}</strong>
            <span>{{ t('room.settingsOrchestrationCard.toggles.applyAfterSave.description') }}</span>
          </div>
          <input v-model="form.apply_after_save" type="checkbox" />
        </label>
      </div>
    </div>

    <div class="settings_cluster mcp_cluster">
      <div class="cluster_head">
        <div>
          <div class="cluster_title">
            {{ t('room.settingsOrchestrationCard.sections.mcpCapabilities.title') }}
          </div>
          <div class="cluster_subtitle">
            {{ t('room.settingsOrchestrationCard.sections.mcpCapabilities.subtitle') }}
          </div>
        </div>
      </div>

      <RoomSettingsRoomMcpPanel
        :form="form"
        :room_mcp_publication="props.room_mcp_publication"
        :room_mcp_share_ref_preview="props.room_mcp_share_ref_preview"
        :room_mcp_share_ref_loading="props.room_mcp_share_ref_loading"
        :room_mcp_share_ref_error="props.room_mcp_share_ref_error"
        :room_mcp_share_ref_last_issued_at="props.room_mcp_share_ref_last_issued_at"
        :room_mcp_share_ref_status="props.room_mcp_share_ref_status"
        :room_mcp_grants="props.room_mcp_grants"
        :room_mcp_grants_loading="props.room_mcp_grants_loading"
        :room_mcp_grants_status="props.room_mcp_grants_status"
        :room_mcp_grant_revoke_loading_id="props.room_mcp_grant_revoke_loading_id"
        :external_mcp_publish_status="props.external_mcp_publish_status"
        :external_mcp_publish_loading="props.external_mcp_publish_loading"
        :external_mcp_publish_error="props.external_mcp_publish_error"
        :external_mcp_publish_plaintext_token="props.external_mcp_publish_plaintext_token"
        :external_mcp_publish_copy_loading_kind="props.external_mcp_publish_copy_loading_kind"
        :external_mcp_publish_enable_loading="props.external_mcp_publish_enable_loading"
        :external_mcp_publish_revoke_loading="props.external_mcp_publish_revoke_loading"
        :external_mcp_publish_regenerate_loading="props.external_mcp_publish_regenerate_loading"
        :handle_room_mcp_share_ref_generate="props.handle_room_mcp_share_ref_generate"
        :handle_room_mcp_share_ref_copy="props.handle_room_mcp_share_ref_copy"
        :handle_room_mcp_grant_list_refresh="props.handle_room_mcp_grant_list_refresh"
        :handle_room_mcp_grant_revoke="props.handle_room_mcp_grant_revoke"
        :handle_external_mcp_publish_enable="props.handle_external_mcp_publish_enable"
        :handle_external_mcp_publish_revoke="props.handle_external_mcp_publish_revoke"
        :handle_external_mcp_publish_regenerate="props.handle_external_mcp_publish_regenerate"
        :handle_external_mcp_publish_copy_config="props.handle_external_mcp_publish_copy_config"
        :handle_external_mcp_publish_copy_token="props.handle_external_mcp_publish_copy_token"
        :refresh_external_mcp_publish="props.refresh_external_mcp_publish"
      />
    </div>

    <div class="settings_cluster">
      <div class="cluster_head">
        <div>
          <div class="cluster_title">
            {{ t('room.settingsOrchestrationCard.sections.replyRouting.title') }}
          </div>
          <div class="cluster_subtitle">
            {{ t('room.settingsOrchestrationCard.sections.replyRouting.subtitle') }}
          </div>
        </div>
      </div>

      <div class="form_grid top_gap">
        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.replyMode.label') }}</span>
          <select v-model="form.reply_mode" @change="onReplyModeChange">
            <option value="manual">{{ t('room.settingsOrchestrationCard.fields.replyMode.options.manual') }}</option>
            <option value="direct_role">{{ t('room.settingsOrchestrationCard.fields.replyMode.options.directRole') }}</option>
            <option value="supervisor_direct">{{ t('room.settingsOrchestrationCard.fields.replyMode.options.supervisorDirect') }}</option>
            <option value="supervisor">{{ t('room.settingsOrchestrationCard.fields.replyMode.options.supervisor') }}</option>
          </select>
        </label>

        <div class="field readonly_field">
          <span>{{ t('room.settingsOrchestrationCard.fields.orchestrationSummary.label') }}</span>
          <div class="readonly_box">
            {{ displayText(props.orchestration_summary) }}
          </div>
        </div>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.workerConcurrency.label') }}</span>
          <select v-model.number="form.max_worker_concurrency" @change="onWorkerConcurrencyChange">
            <option value="1">{{ t('room.settingsOrchestrationCard.fields.workerConcurrency.options.option1') }}</option>
            <option value="2">{{ t('room.settingsOrchestrationCard.fields.workerConcurrency.options.option2') }}</option>
            <option value="3">{{ t('room.settingsOrchestrationCard.fields.workerConcurrency.options.option3') }}</option>
            <option value="4">{{ t('room.settingsOrchestrationCard.fields.workerConcurrency.options.option4') }}</option>
          </select>
          <div class="field_hint">
            {{ t('room.settingsOrchestrationCard.fields.workerConcurrency.hint') }}
          </div>
        </label>

        <div class="field readonly_field">
          <span>{{ t('room.settingsOrchestrationCard.fields.workerConcurrencySummary.label') }}</span>
          <div class="readonly_box">
            {{ workerConcurrencySummary }}
          </div>
        </div>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.defaultReplyRole.label') }}</span>
          <select v-model="form.default_reply_role_id" @change="onDefaultRoleChange">
            <option value="">{{ t('room.settingsOrchestrationCard.fields.defaultReplyRole.emptyOption') }}</option>
            <option
              v-for="role in roles_list"
              :key="String(role.role_id || '')"
              :value="String(role.role_id || '')"
            >
              {{ props.role_label(role) }}
            </option>
          </select>
        </label>

        <div class="field readonly_field">
          <span>{{ t('room.settingsOrchestrationCard.fields.defaultReplyRoleSummary.label') }}</span>
          <div class="readonly_box">
            {{ defaultReplyRoleSummary }}
          </div>
        </div>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.stepBudget.label') }}</span>
          <input
            v-model="form.supervisor_step_budget_total"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            :placeholder="t('room.settingsOrchestrationCard.fields.stepBudget.placeholder')"
          />
          <div class="field_hint">
            {{ t('room.settingsOrchestrationCard.fields.stepBudget.hint') }}
          </div>
        </label>

        <div class="field readonly_field">
          <span>{{ t('room.settingsOrchestrationCard.fields.stepBudgetSummary.label') }}</span>
          <div class="readonly_box">
            {{ stepBudgetSummary }}
          </div>
        </div>
      </div>

      <div class="helper_text">
        {{ t('room.settingsOrchestrationCard.helpers.replyModeGuide') }}
      </div>
    </div>

    <div v-if="props.show_supervisor_settings" class="supervisor_box supervisor_settings_cluster">
      <div class="supervisor_box_head">
        <div>
          <div class="section_title">{{ t('room.settingsOrchestrationCard.supervisorModelSection.title') }}</div>
          <div class="section_subtitle">
            {{ t('room.settingsOrchestrationCard.supervisorModelSection.subtitle') }}
          </div>
        </div>

        <span class="tag" :class="{ tag_active: !!form.supervisor_enabled }">
          {{ supervisorChipText }}
        </span>
      </div>

      <div class="form_grid top_gap">
        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.supervisorSkillStrategy.label') }}</span>
          <select v-model="form.supervisor_skill_strategy">
            <option value="builtin_plus_custom">
              {{ t('room.settingsOrchestrationCard.fields.supervisorSkillStrategy.options.builtinPlusCustom') }}
            </option>
            <option value="builtin_only">
              {{ t('room.settingsOrchestrationCard.fields.supervisorSkillStrategy.options.builtinOnly') }}
            </option>
            <option value="custom_only">
              {{ t('room.settingsOrchestrationCard.fields.supervisorSkillStrategy.options.customOnly') }}
            </option>
          </select>
          <div class="field_hint">
            {{ t('room.settingsOrchestrationCard.fields.supervisorSkillStrategy.hint') }}
          </div>
        </label>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.supervisorProvider.label') }}</span>
          <select v-model="form.supervisor_provider" @change="onSupervisorProviderChange">
            <option value="openai">openai</option>
            <option value="anthropic">anthropic</option>
          </select>
        </label>

        <div class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.supervisorModel.label') }}</span>
          <ModelSelector
            v-model="form.supervisor_model"
            :provider="form.supervisor_provider"
            :single-provider="true"
            :include-disabled="true"
            :allow-disabled-selection="true"
          />
          <div class="field_hint">
            {{ t('room.settingsOrchestrationCard.fields.supervisorModel.hint') }}
          </div>
        </div>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.supervisorTemperature.label') }}</span>
          <input
            v-model="form.supervisor_temperature"
            type="number"
            step="0.1"
            min="0"
            :placeholder="t('room.settingsOrchestrationCard.fields.supervisorTemperature.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.settingsOrchestrationCard.fields.supervisorMaxTokens.label') }}</span>
          <input
            v-model="form.supervisor_max_tokens"
            type="number"
            min="1"
            step="1"
            :placeholder="t('room.settingsOrchestrationCard.fields.supervisorMaxTokens.placeholder')"
          />
        </label>
      </div>

      <div class="helper_text supervisor_state_line">
        {{ currentSupervisorStateText }}
      </div>

      <div class="warning_box warning_box_info top_gap">
        {{ t('room.settingsOrchestrationCard.warnings.strategyInfo') }}
      </div>

      <div class="supervisor_capability_box">
        <div class="section_title">{{ t('room.settingsOrchestrationCard.supervisorCapabilitySection.title') }}</div>
        <div class="section_subtitle">
          {{ t('room.settingsOrchestrationCard.supervisorCapabilitySection.subtitle') }}
        </div>

        <div class="toggle_group top_gap">
          <label class="toggle_row">
            <div class="toggle_text">
              <strong>{{ t('room.settingsOrchestrationCard.supervisorCapabilities.fsReadEnabled.title') }}</strong>
              <span>{{ t('room.settingsOrchestrationCard.supervisorCapabilities.fsReadEnabled.description') }}</span>
            </div>
            <input v-model="form.supervisor_fs_read_enabled" type="checkbox" />
          </label>

          <label class="toggle_row">
            <div class="toggle_text">
              <strong>{{ t('room.settingsOrchestrationCard.supervisorCapabilities.notebookWriteEnabled.title') }}</strong>
              <span>{{ t('room.settingsOrchestrationCard.supervisorCapabilities.notebookWriteEnabled.description') }}</span>
            </div>
            <input v-model="form.supervisor_notebook_write_enabled" type="checkbox" />
          </label>
        </div>

        <div class="form_grid top_gap">
          <label class="field">
            <span>{{ t('room.settingsOrchestrationCard.fields.fsReadScope.label') }}</span>
            <select v-model="form.supervisor_fs_read_scope">
              <option value="minimal">minimal</option>
              <option value="user_ro">user_ro</option>
            </select>
          </label>

          <div class="field readonly_field">
            <span>{{ t('room.settingsOrchestrationCard.fields.workspaceFocusPreview.label') }}</span>
            <div class="readonly_box">
              {{ workspaceFocusPreviewText }}
            </div>
          </div>

          <label class="field">
            <span>{{ t('room.settingsOrchestrationCard.fields.notebookDir.label') }}</span>
            <input
              v-model="form.supervisor_notebook_dir"
              type="text"
              :placeholder="t('room.settingsOrchestrationCard.fields.notebookDir.placeholder')"
            />
          </label>

          <label class="field">
            <span>{{ t('room.settingsOrchestrationCard.fields.notebookFilename.label') }}</span>
            <input
              v-model="form.supervisor_notebook_filename"
              type="text"
              :placeholder="t('room.settingsOrchestrationCard.fields.notebookFilename.placeholder')"
            />
          </label>

          <label class="field">
            <span>{{ t('room.settingsOrchestrationCard.fields.notebookTitle.label') }}</span>
            <input
              v-model="form.supervisor_notebook_title"
              type="text"
              :placeholder="t('room.settingsOrchestrationCard.fields.notebookTitle.placeholder')"
            />
          </label>

          <label class="field">
            <span>{{ t('room.settingsOrchestrationCard.fields.notebookSectionTitle.label') }}</span>
            <input
              v-model="form.supervisor_notebook_section_title"
              type="text"
              :placeholder="t('room.settingsOrchestrationCard.fields.notebookSectionTitle.placeholder')"
            />
          </label>
        </div>

        <div class="warning_box warning_box_info top_gap">
          {{ t('room.settingsOrchestrationCard.warnings.notebookInfo') }}
        </div>

        <div v-if="show_p6_test_panel" class="p6_cluster top_gap">
          <div class="section_title">{{ t('room.settingsOrchestrationCard.p6TestControlSection.title') }}</div>
          <div class="section_subtitle">
            {{ t('room.settingsOrchestrationCard.p6TestControlSection.subtitle') }}
          </div>

          <div class="toggle_group top_gap">
            <label class="toggle_row">
              <div class="toggle_text">
                <strong>{{ t('room.settingsOrchestrationCard.p6TestControlSection.panelEnabled.title') }}</strong>
                <span>{{ t('room.settingsOrchestrationCard.p6TestControlSection.panelEnabled.description') }}</span>
              </div>
              <input v-model="form.p6_test_panel_enabled" type="checkbox" />
            </label>
          </div>

          <div v-if="form.p6_test_panel_enabled" class="form_grid top_gap">
            <label class="field">
              <span>{{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.label') }}</span>
              <select v-model="form.p6_notebook_probe_actor">
                <option value="off">{{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.options.off') }}</option>
                <option value="supervisor">{{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.options.supervisor') }}</option>
                <option value="worker">{{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.options.worker') }}</option>
                <option value="skill">{{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.options.skill') }}</option>
              </select>
              <div class="field_hint">
                {{ t('room.settingsOrchestrationCard.fields.p6ProbeActor.hint') }}
              </div>
            </label>

            <div class="field readonly_field">
              <span>{{ t('room.settingsOrchestrationCard.fields.p6ProbeSummary.label') }}</span>
              <div class="readonly_box">
                {{ p6_probe_summary }}
              </div>
            </div>
          </div>

          <div v-if="form.p6_test_panel_enabled" class="warning_box warning_box_warn top_gap">
            {{ t('room.settingsOrchestrationCard.warnings.p6TemporaryUse') }}
          </div>
        </div>

        <div class="audit_grid">
          <div class="audit_card">
            <div class="audit_title">{{ t('room.settingsOrchestrationCard.audit.fs.title') }}</div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.enabled') }}</span>
              <code>{{ boolText(fs_audit.enabled) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.status') }}</span>
              <code>{{ displayText(fs_audit.status) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.reason') }}</span>
              <code>{{ displayText(fs_audit.reason) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.focusRoot') }}</span>
              <code>{{ displayText(fs_audit.focus_root) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.scope') }}</span>
              <code>{{ displayText(fs_audit.scope, 'room.settingsOrchestrationCard.common.defaultScope') }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.updatedAt') }}</span>
              <code>{{ displayText(fs_audit.at) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.toolCalls') }}</span>
              <code>{{ props.fs_tool_call_count }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.fs.fields.toolResults') }}</span>
              <code>{{ props.fs_tool_result_count }}</code>
            </div>
          </div>

          <div class="audit_card">
            <div class="audit_title">{{ t('room.settingsOrchestrationCard.audit.notebook.title') }}</div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.status') }}</span>
              <code>{{ displayText(notebook_audit.status) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.message') }}</span>
              <code>{{ displayText(notebook_audit.message) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.relativePath') }}</span>
              <code>{{ displayText(notebook_audit.relative_path) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.updatedAt') }}</span>
              <code>{{ displayText(notebook_audit.at) }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.toolCalls') }}</span>
              <code>{{ props.notebook_tool_call_count }}</code>
            </div>
            <div class="audit_line">
              <span>{{ t('room.settingsOrchestrationCard.audit.notebook.fields.toolResults') }}</span>
              <code>{{ props.notebook_tool_result_count }}</code>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="notice_stack">
      <div v-if="form.reply_mode === 'manual'" class="warning_box warning_box_info">
        {{ t('room.settingsOrchestrationCard.warnings.replyModeManual') }}
      </div>

      <div v-if="props.reply_mode_supervisor_direct_warning" class="warning_box warning_box_info">
        {{ t('room.settingsOrchestrationCard.warnings.replyModeSupervisorDirect') }}
      </div>

      <div v-if="props.reply_mode_supervisor_warning" class="warning_box warning_box_info">
        {{ t('room.settingsOrchestrationCard.warnings.replyModeSupervisor') }}
      </div>

      <div v-if="props.reply_mode_direct_role_warning" class="warning_box warning_box_warn">
        {{ t('room.settingsOrchestrationCard.warnings.replyModeDirectRole') }}
      </div>
    </div>

    <div class="helper_text orchestration_footer_hint">
      {{ t('room.settingsOrchestrationCard.helpers.defaultRoleSync') }}
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'
import ModelSelector from '../../ModelSelector.vue'
import RoomSettingsRoomMcpPanel from './RoomSettingsRoomMcpPanel.vue'

const props = defineProps({
  form: { type: Object, required: true },
  roles: { type: Array, default: () => [] },
  default_role_label: { type: String, default: '' },
  show_supervisor_settings: { type: Boolean, default: false },
  reply_mode_supervisor_warning: { type: Boolean, default: false },
  reply_mode_supervisor_direct_warning: { type: Boolean, default: false },
  reply_mode_direct_role_warning: { type: Boolean, default: false },
  orchestration_summary: { type: String, default: '' },
  supervisor_fs_audit: { type: Object, default: () => ({}) },
  supervisor_notebook_audit: { type: Object, default: () => ({}) },
  fs_tool_call_count: { type: Number, default: 0 },
  fs_tool_result_count: { type: Number, default: 0 },
  notebook_tool_call_count: { type: Number, default: 0 },
  notebook_tool_result_count: { type: Number, default: 0 },
  normalized_workspace_id_preview: { type: String, default: '' },
  normalized_focus_root_preview: { type: String, default: '' },

  room_mcp_publication: { type: Object, default: () => ({}) },

  room_mcp_share_ref_preview: { type: String, default: '' },
  room_mcp_share_ref_loading: { type: Boolean, default: false },
  room_mcp_share_ref_error: { type: String, default: '' },
  room_mcp_share_ref_last_issued_at: { type: String, default: '' },
  room_mcp_share_ref_status: { type: Object, default: () => ({}) },

  room_mcp_grants: { type: Array, default: () => [] },
  room_mcp_grants_loading: { type: Boolean, default: false },
  room_mcp_grants_status: { type: Object, default: () => ({}) },
  room_mcp_grant_revoke_loading_id: { type: String, default: '' },

  external_mcp_publish_status: { type: Object, default: () => ({}) },
  external_mcp_publish_loading: { type: Boolean, default: false },
  external_mcp_publish_error: { type: String, default: '' },
  external_mcp_publish_plaintext_token: { type: String, default: '' },
  external_mcp_publish_copy_loading_kind: { type: String, default: '' },
  external_mcp_publish_enable_loading: { type: Boolean, default: false },
  external_mcp_publish_revoke_loading: { type: Boolean, default: false },
  external_mcp_publish_regenerate_loading: { type: Boolean, default: false },

  role_label: { type: Function, required: true },
  handle_default_role_change: { type: Function, required: true },
  handle_reply_mode_change: { type: Function, required: true },
  handle_supervisor_provider_change: { type: Function, required: true },

  handle_room_mcp_share_ref_generate: { type: Function, default: null },
  handle_room_mcp_share_ref_copy: { type: Function, default: null },
  handle_room_mcp_grant_list_refresh: { type: Function, default: null },
  handle_room_mcp_grant_revoke: { type: Function, default: null },

  handle_external_mcp_publish_enable: { type: Function, default: null },
  handle_external_mcp_publish_revoke: { type: Function, default: null },
  handle_external_mcp_publish_regenerate: { type: Function, default: null },
  handle_external_mcp_publish_copy_config: { type: Function, default: null },
  handle_external_mcp_publish_copy_token: { type: Function, default: null },
  refresh_external_mcp_publish: { type: Function, default: null },
})

const { t } = useI18n()

const show_p6_test_panel = false

const roles_list = computed(() => {
  return Array.isArray(props.roles) ? props.roles : []
})

const fs_audit = computed(() => {
  return props.supervisor_fs_audit && typeof props.supervisor_fs_audit === 'object'
    ? props.supervisor_fs_audit
    : {}
})

const notebook_audit = computed(() => {
  return props.supervisor_notebook_audit && typeof props.supervisor_notebook_audit === 'object'
    ? props.supervisor_notebook_audit
    : {}
})

function displayPathText(value) {
  const raw = String(value ?? '').trim()
  if (!raw) return ''

  const direct = String(to_user_visible_path(raw) || '').trim()
  if (direct && direct !== raw) return direct

  return raw.replace(/(^|[\s"'`(（\[【📁])agent_files(?=\/|$)/g, '$1user')
}

function displayText(value, fallbackKey = 'room.settingsOrchestrationCard.common.emptyValue') {
  const text = displayPathText(value)
  return text || t(fallbackKey)
}

function boolText(value) {
  return value
    ? t('room.settingsOrchestrationCard.common.trueValue')
    : t('room.settingsOrchestrationCard.common.falseValue')
}

function normalizeWorkerConcurrency(value) {
  const raw = Number(value)
  if (!Number.isFinite(raw)) return 1
  return Math.min(4, Math.max(1, Math.trunc(raw)))
}

function onDefaultRoleChange(event) {
  props.handle_default_role_change(event)
}

function onReplyModeChange(event) {
  props.handle_reply_mode_change(event)
}

function onSupervisorProviderChange(event) {
  props.handle_supervisor_provider_change(event)
}

function onWorkerConcurrencyChange() {
  if (!props.form || typeof props.form !== 'object') return
  props.form.max_worker_concurrency = normalizeWorkerConcurrency(props.form.max_worker_concurrency)
}

const workerConcurrencyValue = computed(() => {
  return normalizeWorkerConcurrency(props.form?.max_worker_concurrency)
})

const workerConcurrencyChipText = computed(() => {
  return t('room.settingsOrchestrationCard.chips.workerConcurrency', {
    value: workerConcurrencyValue.value,
  })
})

const workerConcurrencySummary = computed(() => {
  const value = workerConcurrencyValue.value

  if (value <= 1) {
    return t('room.settingsOrchestrationCard.fields.workerConcurrencySummary.safest', { value })
  }

  if (value === 2) {
    return t('room.settingsOrchestrationCard.fields.workerConcurrencySummary.recommended', { value })
  }

  if (value === 3) {
    return t('room.settingsOrchestrationCard.fields.workerConcurrencySummary.faster', { value })
  }

  return t('room.settingsOrchestrationCard.fields.workerConcurrencySummary.experimental', { value })
})

const defaultRoleLabelResolved = computed(() => {
  return String(props.default_role_label || '').trim()
    || t('room.settingsOrchestrationCard.common.emptyOption')
})

const defaultReplyRoleSummary = computed(() => {
  if (props.form?.default_reply_role_id) {
    return t('room.settingsOrchestrationCard.fields.defaultReplyRoleSummary.withRole', {
      role: defaultRoleLabelResolved.value,
    })
  }

  return t('room.settingsOrchestrationCard.fields.defaultReplyRoleSummary.withoutRole')
})

const stepBudgetValue = computed(() => {
  const raw = props.form?.supervisor_step_budget_total
  if (raw === 0 || raw === '0') return '0'
  const text = String(raw ?? '').trim()
  return text || t('room.settingsOrchestrationCard.common.defaultStepBudget')
})

const stepBudgetSummary = computed(() => {
  const value = stepBudgetValue.value
  const current = t('room.settingsOrchestrationCard.fields.stepBudgetSummary.current', { value })

  if (value === '0') {
    return `${current} ${t('room.settingsOrchestrationCard.fields.stepBudgetSummary.unlimited')}`
  }

  return `${current} ${t('room.settingsOrchestrationCard.fields.stepBudgetSummary.limited', { value })}`
})

const currentSupervisorStateText = computed(() => {
  return t('room.settingsOrchestrationCard.helpers.currentSupervisorState', {
    strategy: String(props.form?.supervisor_skill_strategy || '').trim()
      || t('room.settingsOrchestrationCard.common.defaultSkillStrategy'),
    provider: String(props.form?.supervisor_provider || '').trim()
      || t('room.settingsOrchestrationCard.common.defaultProvider'),
    model: String(props.form?.supervisor_model || '').trim()
      || t('room.settingsOrchestrationCard.common.defaultModel'),
    budget: stepBudgetValue.value,
  })
})

const workspaceFocusPreviewText = computed(() => {
  if (props.normalized_focus_root_preview) {
    return t('room.settingsOrchestrationCard.fields.workspaceFocusPreview.withFocus', {
      workspace: props.normalized_workspace_id_preview || t('room.settingsOrchestrationCard.common.emptyValue'),
      root: displayPathText(props.normalized_focus_root_preview),
    })
  }

  return t('room.settingsOrchestrationCard.fields.workspaceFocusPreview.withoutFocus')
})

const p6_probe_summary = computed(() => {
  const form = props.form || {}
  const enabled = !!form.p6_test_panel_enabled
  const actor = String(form.p6_notebook_probe_actor || 'off').trim() || 'off'

  if (!enabled) {
    return t('room.settingsOrchestrationCard.p6ProbeSummary.disabled')
  }

  if (actor === 'supervisor') {
    return t('room.settingsOrchestrationCard.p6ProbeSummary.supervisor')
  }

  if (actor === 'worker') {
    return t('room.settingsOrchestrationCard.p6ProbeSummary.worker')
  }

  if (actor === 'skill') {
    return t('room.settingsOrchestrationCard.p6ProbeSummary.skill')
  }

  return t('room.settingsOrchestrationCard.p6ProbeSummary.off')
})

const sharedAutoReplyChipText = computed(() => {
  return props.form?.shared_room_config_enabled
    ? t('room.settingsOrchestrationCard.chips.sharedAutoReplyOn')
    : t('room.settingsOrchestrationCard.chips.sharedAutoReplyOff')
})

const supervisorChipText = computed(() => {
  return props.form?.supervisor_enabled
    ? t('room.settingsOrchestrationCard.chips.supervisorOn')
    : t('room.settingsOrchestrationCard.chips.supervisorOff')
})

const replyModeChipText = computed(() => {
  const mode = String(props.form?.reply_mode || 'manual').trim()

  if (mode === 'direct_role') {
    return t('room.settingsOrchestrationCard.fields.replyMode.options.directRole')
  }

  if (mode === 'supervisor_direct') {
    return t('room.settingsOrchestrationCard.fields.replyMode.options.supervisorDirect')
  }

  if (mode === 'supervisor') {
    return t('room.settingsOrchestrationCard.fields.replyMode.options.supervisor')
  }

  return t('room.settingsOrchestrationCard.fields.replyMode.options.manual')
})
</script>

<style scoped>
.orchestration_card {
  position: relative;
}

.orchestration_head {
  padding-bottom: 2px;
}

.orchestration_title_block {
  min-width: 0;
}

.orchestration_eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 23px;
  padding: 0 9px;
  margin-bottom: 8px;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 70%, transparent);
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
}

.orchestration_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

.orchestration_subtitle {
  max-width: 820px;
}

.orchestration_chips {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
}

.settings_cluster {
  margin-top: 14px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
}

.mcp_cluster {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
}

.cluster_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.cluster_title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.cluster_subtitle {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.orchestration_toggle_group {
  margin-top: 12px;
}

.supervisor_settings_cluster {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, var(--selected-bg) 4%),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
}

.supervisor_state_line {
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.p6_cluster {
  padding: 12px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 74%, transparent);
}

.notice_stack {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.notice_stack .warning_box {
  margin-top: 0;
}

.orchestration_footer_hint {
  margin-top: 12px;
}

input[type="checkbox"] {
  width: 17px;
  height: 17px;
  accent-color: var(--selected);
  cursor: pointer;
  flex: 0 0 auto;
}

@media (max-width: 860px) {
  .orchestration_chips {
    justify-content: flex-start;
  }

  .settings_cluster {
    padding: 12px;
  }
}
</style>

