<template>
  <div class="provider_card" :class="{ disabled: !mcpEnabled, enabled: mcpEnabled }">
    <div class="provider_head">
      <div class="provider_title_block">
        <div class="provider_title">{{ t('room.roleFormFields.provider.title') }}</div>
        <div class="provider_desc">
          {{ t('room.roleFormFields.provider.description') }}
        </div>
      </div>

      <div class="provider_state" :class="{ on: mcpEnabled }">
        {{
          mcpEnabled
            ? t('room.roleFormFields.provider.stateOn')
            : t('room.roleFormFields.provider.stateOff')
        }}
      </div>
    </div>

    <div class="form_grid top_gap">
      <label class="field">
        <span>{{ t('room.roleFormFields.provider.providerLabel') }}</span>
        <select v-model="form.mcp_binding.provider_id" :disabled="!mcpEnabled">
          <option value="">{{ t('room.roleFormFields.provider.providerPlaceholder') }}</option>
          <option
            v-for="provider in normalizedProviderOptions"
            :key="provider.provider_id"
            :value="provider.provider_id"
          >
            {{ providerOptionLabel(provider) }}
          </option>
        </select>
      </label>

      <label v-if="toolTemplateOptions.length > 1" class="field">
        <span>{{ t('room.roleFormFields.provider.toolLabel') }}</span>
        <select v-model="form.mcp_binding.tool_name" :disabled="!mcpEnabled || !selectedProvider">
          <option
            v-for="tool in toolTemplateOptions"
            :key="tool.tool_name"
            :value="tool.tool_name"
          >
            {{ tool.label || tool.tool_name }}
          </option>
        </select>
      </label>
    </div>

    <div v-if="selectedProvider" class="provider_info">
      <div class="provider_label_row">
        <div class="provider_label">
          {{ selectedProvider.label || selectedProvider.provider_id }}
        </div>

        <span
          class="provider_type_badge"
          :class="{
            is_room: selectedProviderIsRoomProvider,
            is_imported: selectedProviderIsImported,
          }"
        >
          {{
            selectedProviderIsRoomProvider
              ? t('room.roleFormFields.provider.typeRoomProvider')
              : t('room.roleFormFields.provider.typePresetProvider')
          }}
        </span>

        <span v-if="selectedProviderIsImported" class="provider_type_badge is_imported">
          {{ t('room.roleFormFields.provider.importedRemote') }}
        </span>

        <span v-if="selectedProviderResolvedFromSnapshot" class="provider_type_badge is_snapshot">
          {{ t('room.roleFormFields.provider.snapshotFallback') }}
        </span>
      </div>

      <div class="provider_hint">
        {{ selectedProvider.description || t('room.roleFormFields.provider.selectedDefault') }}
      </div>

      <div class="provider_meta">
        <span class="meta_chip" :class="{ ok: providerAvailable, bad: !providerAvailable }">
          {{
            providerAvailable
              ? t('room.roleFormFields.provider.available')
              : t('room.roleFormFields.provider.unavailable')
          }}
        </span>

        <span class="meta_chip" :class="{ ok: authConfigured, bad: authRequired && !authConfigured }">
          {{
            authRequired
              ? (authConfigured
                ? t('room.roleFormFields.provider.authReady')
                : t('room.roleFormFields.provider.authMissing'))
              : t('room.roleFormFields.provider.authNone')
          }}
        </span>

        <span
          v-if="selectedProviderOriginLabel"
          class="meta_chip"
          :class="{ ok: selectedProviderIsImported }"
        >
          {{ t('room.roleFormFields.provider.originValue', { value: selectedProviderOriginLabel }) }}
        </span>

        <span v-if="selectedProviderIsRoomProvider" class="meta_chip ok">
          {{
            t('room.roleFormFields.provider.sourceRoomValue', {
              value: selectedRoomSource.room_id || t('room.roleFormFields.provider.unknown'),
            })
          }}
        </span>

        <span
          v-if="selectedProviderIsRoomProvider"
          class="meta_chip"
          :class="{ ok: selectedRoomSource.shared_room_config_enabled, bad: !selectedRoomSource.shared_room_config_enabled }"
        >
          {{
            t('room.roleFormFields.provider.sharedAutoReplyValue', {
              state: selectedRoomSource.shared_room_config_enabled
                ? t('room.roleFormFields.provider.on')
                : t('room.roleFormFields.provider.off'),
            })
          }}
        </span>

        <span
          v-if="selectedProviderIsRoomProvider"
          class="meta_chip"
          :class="{ ok: !selectedRoomBoundary.owner_private_scope_exposed, bad: selectedRoomBoundary.owner_private_scope_exposed }"
        >
          {{
            t('room.roleFormFields.provider.ownerPrivateScopeValue', {
              state: selectedRoomBoundary.owner_private_scope_exposed
                ? t('room.roleFormFields.provider.exposed')
                : t('room.roleFormFields.provider.closed'),
            })
          }}
        </span>
      </div>

      <div v-if="providerStatusText" class="provider_status_text">
        {{ providerStatusText }}
      </div>

      <div v-if="selectedProviderIsRoomProvider" class="room_provider_summary top_gap">
        <div class="room_provider_summary_title">
          {{ t('room.roleFormFields.provider.roomProviderSummaryTitle') }}
        </div>

        <div class="room_provider_summary_grid">
          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">provider_id</span>
            <code class="room_provider_summary_value">{{ selectedProvider.provider_id || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">provider_origin</span>
            <code class="room_provider_summary_value">{{ selectedProvider.provider_origin || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">source_room_id</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.room_id || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">reply_mode</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.reply_mode || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">shared_supervisor</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.shared_supervisor_enabled ? 'true' : 'false' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">shared_room_config</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.shared_room_config_enabled ? 'true' : 'false' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">workspace</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.workspace_label || selectedRoomSource.workspace_id || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">focus_root</span>
            <code class="room_provider_summary_value">{{ selectedRoomSource.focus_root_label || selectedRoomSource.focus_root || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">descriptor_version</span>
            <code class="room_provider_summary_value">{{ selectedProvider.descriptor_version || selectedProvider.share_ref_version || '-' }}</code>
          </div>

          <div class="room_provider_summary_item">
            <span class="room_provider_summary_key">share_ref</span>
            <code class="room_provider_summary_value">
              {{ selectedProvider.share_ref ? t('room.roleFormFields.provider.present') : '-' }}
            </code>
          </div>
        </div>

        <div class="room_provider_boundary_note">
          {{ roomProviderBoundaryNote }}
        </div>
      </div>
    </div>

    <div v-if="providerFields.length" class="form_grid params_grid top_gap">
      <template v-for="field in providerFields" :key="field.key">
        <label v-if="field.type !== 'boolean'" class="field">
          <span>{{ field.label }}</span>
          <input
            v-if="field.type === 'integer' || field.type === 'number'"
            v-model.number="form.mcp_binding.params[field.key]"
            type="number"
            :disabled="!mcpEnabled"
            :min="field.minimum"
            :max="field.maximum"
            :step="field.type === 'integer' ? 1 : 'any'"
            :placeholder="field.placeholder"
          />
          <input
            v-else
            v-model="form.mcp_binding.params[field.key]"
            type="text"
            :disabled="!mcpEnabled"
            :placeholder="field.placeholder"
          />
          <small v-if="field.description" class="field_hint">{{ field.description }}</small>
        </label>

        <label v-else class="field checkbox_field">
          <span>{{ field.label }}</span>
          <input
            v-model="form.mcp_binding.params[field.key]"
            type="checkbox"
            :disabled="!mcpEnabled"
          />
        </label>
      </template>
    </div>

    <div v-if="selectedProvider" class="boundary_card top_gap">
      <div class="boundary_title">{{ t('room.roleFormFields.provider.boundaryTitle') }}</div>
      <div class="boundary_desc">
        {{ boundaryMessage }}
      </div>

      <div
        v-if="boundaryNotice"
        class="boundary_notice"
        role="status"
      >
        {{ boundaryNotice }}
      </div>

      <div class="form_grid top_gap">
        <label
          class="field checkbox_field boundary_pending"
          :title="t('room.roleFormFields.provider.pendingBoundaryTitle')"
        >
          <span>
            {{ t('room.roleFormFields.provider.inheritWorkspace') }}
            <small class="boundary_badge">
              {{ t('room.roleFormFields.provider.pendingBadge') }}
            </small>
          </span>
          <input
            :checked="Boolean(form.mcp_binding?.inherit_workspace_context)"
            type="checkbox"
            :disabled="!mcpEnabled || !supportsWorkspaceContext"
            @change="handleBoundaryToggle('inherit_workspace_context', $event)"
          />
        </label>

        <label
          class="field checkbox_field boundary_pending"
          :title="t('room.roleFormFields.provider.pendingBoundaryTitle')"
        >
          <span>
            {{ t('room.roleFormFields.provider.inheritFocusRoot') }}
            <small class="boundary_badge">
              {{ t('room.roleFormFields.provider.pendingBadge') }}
            </small>
          </span>
          <input
            :checked="Boolean(form.mcp_binding?.inherit_focus_root)"
            type="checkbox"
            :disabled="!mcpEnabled || !supportsFocusRoot"
            @change="handleBoundaryToggle('inherit_focus_root', $event)"
          />
        </label>
      </div>

      <div class="workspace_hint">
        <div>
          {{
            t('room.roleFormFields.provider.workspaceIdValue', {
              value: resolvedWorkspace.workspace_id || t('room.roleFormFields.common.dash'),
            })
          }}
        </div>
        <div>
          {{
            t('room.roleFormFields.provider.focusRootValue', {
              value: resolvedWorkspace.focus_root || t('room.roleFormFields.provider.rootDirectory'),
            })
          }}
        </div>
        <div v-if="selectedProviderIsRoomProvider" class="workspace_hint_strong">
          {{ t('room.roleFormFields.provider.roomProviderConsumerBoundaryHint') }}
        </div>
        <div v-if="selectedProviderIsImported" class="workspace_hint_strong">
          {{ t('room.roleFormFields.provider.importedSnapshotHint') }}
        </div>
      </div>
    </div>

    <details v-if="selectedProvider" class="advanced_block top_gap">
      <summary>{{ t('room.roleFormFields.provider.advanced') }}</summary>
      <div class="advanced_inner">
        <div class="advanced_line">
          <span class="advanced_label">{{ t('room.roleFormFields.provider.advancedLabels.providerId') }}</span>
          <span>{{ form.mcp_binding.provider_id || t('room.roleFormFields.common.dash') }}</span>
        </div>

        <div class="advanced_line">
          <span class="advanced_label">{{ t('room.roleFormFields.provider.advancedLabels.providerType') }}</span>
          <span>{{ form.mcp_binding.provider_type || 'preset' }}</span>
        </div>

        <div class="advanced_line">
          <span class="advanced_label">provider_origin</span>
          <span>{{ form.mcp_binding.provider_origin || selectedProvider.provider_origin || '-' }}</span>
        </div>

        <div class="advanced_line">
          <span class="advanced_label">{{ t('room.roleFormFields.provider.advancedLabels.toolName') }}</span>
          <span>{{ form.mcp_binding.tool_name || 'search' }}</span>
        </div>

        <div v-if="selectedProvider.share_ref || form.mcp_share_ref || form.mcp_binding.share_ref" class="advanced_line">
          <span class="advanced_label">share_ref</span>
          <span>{{ selectedProvider.share_ref || form.mcp_share_ref || form.mcp_binding.share_ref }}</span>
        </div>

        <div v-if="selectedProviderIsRoomProvider" class="advanced_line">
          <span class="advanced_label">{{ t('room.roleFormFields.provider.advancedLabels.sourceRoom') }}</span>
          <span>{{ selectedRoomSource.room_id || '-' }}</span>
        </div>

        <div v-if="selectedProviderIsRoomProvider" class="advanced_line">
          <span class="advanced_label">{{ t('room.roleFormFields.provider.advancedLabels.sharedBoundary') }}</span>
          <span>{{ t('room.roleFormFields.provider.advancedSharedBoundaryOnly') }}</span>
        </div>

        <div class="advanced_line">
          <span class="advanced_label">snapshot</span>
          <span>
            {{
              selectedProviderResolvedFromSnapshot
                ? t('room.roleFormFields.provider.snapshotFallbackActive')
                : t('room.roleFormFields.provider.snapshotCatalogBacked')
            }}
          </span>
        </div>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomRoleProviderBindingPanel } from '../../../composables/editor/room/use_room_role_provider_binding_panel'

const props = defineProps({
  form: { type: Object, required: true },
  providerOptions: { type: Array, default: () => [] },
  resolvedWorkspace: { type: Object, default: () => ({}) },
})

const { t } = useI18n()

const mcpEnabled = computed(() => !!props.form?.tool_policy?.mcp)

const PENDING_BOUNDARY_KEYS = new Set(['inherit_workspace_context', 'inherit_focus_root'])

const boundaryNotice = ref('')
let boundaryNoticeTimer = null

function ensureMcpBinding() {
  if (!props.form.mcp_binding || typeof props.form.mcp_binding !== 'object') {
    props.form.mcp_binding = {}
  }
  return props.form.mcp_binding
}

function boundaryFeatureLabel(key) {
  if (key === 'inherit_workspace_context') {
    return t('room.roleFormFields.provider.inheritWorkspace')
  }
  if (key === 'inherit_focus_root') {
    return t('room.roleFormFields.provider.inheritFocusRoot')
  }
  return key
}

function showBoundaryNotice(key) {
  const feature = boundaryFeatureLabel(key)
  boundaryNotice.value = t('room.roleFormFields.provider.pendingBoundaryNotice', { feature })

  if (boundaryNoticeTimer) {
    clearTimeout(boundaryNoticeTimer)
  }

  boundaryNoticeTimer = window.setTimeout(() => {
    boundaryNotice.value = ''
    boundaryNoticeTimer = null
  }, 2600)
}

function handleBoundaryToggle(key, event) {
  const binding = ensureMcpBinding()

  if (PENDING_BOUNDARY_KEYS.has(key)) {
    binding[key] = false
    if (event?.target) {
      event.target.checked = false
    }
    showBoundaryNotice(key)
    return
  }

  binding[key] = Boolean(event?.target?.checked)
}

watchEffect(() => {
  const binding = props.form?.mcp_binding
  if (!binding || typeof binding !== 'object') return

  PENDING_BOUNDARY_KEYS.forEach((key) => {
    if (binding[key]) {
      binding[key] = false
    }
  })
})

onBeforeUnmount(() => {
  if (boundaryNoticeTimer) {
    clearTimeout(boundaryNoticeTimer)
  }
})

const {
  normalizedProviderOptions,
  providerOptionLabel,
  toolTemplateOptions,
  selectedProvider,
  selectedProviderIsRoomProvider,
  selectedProviderIsImported,
  selectedProviderResolvedFromSnapshot,
  selectedProviderOriginLabel,
  selectedRoomSource,
  selectedRoomBoundary,
  providerFields,
  providerAvailable,
  authRequired,
  authConfigured,
  providerStatusText,
  supportsWorkspaceContext,
  supportsFocusRoot,
  boundaryMessage,
  roomProviderBoundaryNote,
} = useRoomRoleProviderBindingPanel(props, t)
</script>

<style scoped>
.provider_card {
  min-width: 0;
  margin-top: 12px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    opacity 0.16s ease;
}

.provider_card.enabled {
  border-color: color-mix(in srgb, var(--selected) 18%, var(--line));
}

.provider_card.disabled {
  opacity: 0.78;
}

.provider_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.provider_title_block {
  min-width: 0;
}

.provider_title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.provider_desc {
  max-width: 760px;
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.provider_state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.provider_state.on {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
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
.field select {
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

.field select {
  cursor: pointer;
}

.field input:disabled,
.field select:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.field input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.field input:focus,
.field select:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.field_hint {
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.checkbox_field {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 41px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
}

.checkbox_field input {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
  margin: 0;
  padding: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.provider_info {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
}

.provider_label_row {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  min-width: 0;
}

.provider_label {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.provider_type_badge,
.meta_chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 23px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--sidebar-bg) 78%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
}

.provider_type_badge.is_room,
.meta_chip.ok {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
}

.provider_type_badge.is_imported {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.09);
  color: #d97706;
}

.provider_type_badge.is_snapshot {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
}

.meta_chip.bad {
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.provider_hint {
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.provider_meta {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.provider_status_text {
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--sidebar-bg) 74%, transparent);
  color: var(--text-secondary);
  font-size: 0.79rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.room_provider_summary {
  padding: 12px;
  border: 1px solid rgba(34, 197, 94, 0.24);
  border-radius: 14px;
  background:
    linear-gradient(
      180deg,
      rgba(34, 197, 94, 0.08),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
}

.room_provider_summary_title {
  color: var(--text-main);
  font-size: 0.86rem;
  font-weight: 820;
  line-height: 1.35;
}

.room_provider_summary_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin-top: 10px;
}

.room_provider_summary_item {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
}

.room_provider_summary_key {
  display: block;
  color: var(--text-secondary);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.7rem;
  font-weight: 720;
  line-height: 1.35;
}

.room_provider_summary_value {
  display: block;
  margin-top: 5px;
  color: var(--text-main);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.74rem;
  line-height: 1.5;
  word-break: normal;
  overflow-wrap: anywhere;
}

.room_provider_boundary_note {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.params_grid {
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.boundary_card {
  padding: 12px;
  border: 1px dashed color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
}

.boundary_title {
  color: var(--text-main);
  font-size: 0.88rem;
  font-weight: 820;
  line-height: 1.35;
}

.boundary_desc {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.boundary_notice {
  box-sizing: border-box;
  margin-top: 10px;
  border: 1px solid rgba(245, 158, 11, 0.34);
  border-radius: 12px;
  padding: 9px 11px;
  background: rgba(245, 158, 11, 0.09);
  color: #d97706;
  font-size: 0.8rem;
  line-height: 1.5;
}

.boundary_pending {
  border-style: dashed;
  opacity: 0.88;
}

.boundary_pending > span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.boundary_badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 18px;
  padding: 0 6px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1;
}

.workspace_hint {
  margin-top: 10px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 74%, transparent);
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.workspace_hint_strong {
  margin-top: 7px;
  color: var(--text-main);
  font-weight: 640;
}

.advanced_block {
  border: 1px dashed var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  overflow: hidden;
}

.advanced_block summary {
  cursor: pointer;
  padding: 11px 12px;
  color: var(--text-main);
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
}

.advanced_block summary:hover {
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
}

.advanced_inner {
  display: grid;
  gap: 8px;
  padding: 0 12px 12px;
}

.advanced_line {
  display: grid;
  grid-template-columns: minmax(112px, 0.26fr) minmax(0, 1fr);
  gap: 10px;
  min-width: 0;
  color: var(--text-main);
  font-size: 0.8rem;
  line-height: 1.5;
}

.advanced_label {
  min-width: 0;
  color: var(--text-secondary);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.72rem;
  font-weight: 720;
}

.advanced_line span:last-child {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: normal;
}

.top_gap {
  margin-top: 12px;
}

@media (max-width: 860px) {
  .form_grid,
  .room_provider_summary_grid {
    grid-template-columns: 1fr;
  }

  .provider_head {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .provider_card,
  .provider_info,
  .room_provider_summary,
  .boundary_card {
    border-radius: 14px;
  }

  .provider_state {
    align-self: flex-start;
  }

  .checkbox_field {
    align-items: flex-start;
  }

  .advanced_line {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}

@media (max-width: 420px) {
  .provider_type_badge,
  .meta_chip {
    white-space: normal;
    text-align: center;
    line-height: 1.25;
    padding-top: 4px;
    padding-bottom: 4px;
  }
}
</style>
