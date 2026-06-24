<template>
  <div
    class="supervisor_box top_gap external_mcp_publish_card"
    :class="rootStateClass"
  >
    <div class="external_header">
      <div class="external_title_group">
        <div class="external_eyebrow">
          <span class="external_eyebrow_dot"></span>
          <span>{{ t('room.externalMcp.eyebrow') }}</span>
        </div>

        <div class="section_title external_title">
          {{ t('room.externalMcp.title') }}
        </div>

        <div class="section_subtitle external_subtitle">
          {{ t('room.externalMcp.subtitle') }}
        </div>
      </div>

      <div class="external_header_actions">
        <div
          class="state_pill"
          :class="statePillClass"
          :title="t('room.externalMcp.fields.status')"
        >
          {{ stateText }}
        </div>

        <button
          class="mini_btn"
          type="button"
          :disabled="busy"
          @click="onRefresh"
        >
          {{ refreshButtonText }}
        </button>
      </div>
    </div>

    <div class="publish_overview_grid top_gap">
      <div class="overview_tile overview_tile_status">
        <span>{{ t('room.externalMcp.fields.status') }}</span>
        <strong :class="stateValueClass">{{ stateText }}</strong>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.providerId') }}</span>
        <code>{{ providerIdText }}</code>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.sourceRoomId') }}</span>
        <code>{{ sourceRoomIdText }}</code>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.resultView') }}</span>
        <code>{{ resultViewText }}</code>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.expiresAt') }}</span>
        <strong>{{ expiresAtText }}</strong>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.lastUsed') }}</span>
        <strong>{{ lastUsedText }}</strong>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.usedCount') }}</span>
        <strong>{{ usedCountText }}</strong>
      </div>

      <div class="overview_tile">
        <span>{{ t('room.externalMcp.fields.clientLabel') }}</span>
        <strong>{{ clientLabelText }}</strong>
      </div>
    </div>

    <div class="publish_config_panel top_gap">
      <div class="config_panel_head">
        <div>
          <div class="config_panel_title">
            {{ t('room.externalMcp.config.title') }}
          </div>
          <div class="config_panel_hint">
            {{ t('room.externalMcp.config.subtitle') }}
          </div>
        </div>
      </div>

      <div class="form_grid top_gap">
        <label class="field">
          <span>{{ t('room.externalMcp.fields.expiresInDays') }}</span>
          <input
            v-model="expiresInDays"
            type="number"
            min="0.0417"
            max="30"
            step="any"
            :placeholder="t('room.externalMcp.placeholders.expiresInDays')"
          />
          <div class="field_hint">
            {{ t('room.externalMcp.hints.expiresInDays') }}
          </div>
        </label>

        <label class="field">
          <span>{{ t('room.externalMcp.fields.maxCalls') }}</span>
          <input
            v-model="maxCalls"
            type="number"
            min="1"
            step="1"
            :placeholder="t('room.externalMcp.placeholders.maxCalls')"
          />
          <div class="field_hint">
            {{ t('room.externalMcp.hints.maxCalls') }}
          </div>
        </label>

        <label class="field">
          <span>{{ t('room.externalMcp.fields.clientLabelInput') }}</span>
          <input
            v-model="clientLabel"
            type="text"
            :placeholder="t('room.externalMcp.placeholders.clientLabel')"
          />
          <div class="field_hint">
            {{ t('room.externalMcp.hints.clientLabel') }}
          </div>
        </label>

        <label class="field">
          <span>{{ t('room.externalMcp.fields.endpoint') }}</span>
          <input
            v-model="endpointUrl"
            type="text"
            :placeholder="t('room.externalMcp.placeholders.endpoint')"
          />
          <div class="field_hint">
            {{ t('room.externalMcp.hints.endpoint') }}
          </div>
        </label>
      </div>
    </div>

    <div
      v-if="plaintextTokenText"
      class="warning_box warning_box_warn top_gap token_notice"
    >
      <div class="token_notice_head">
        <div>
          <div class="token_notice_title">
            {{ t('room.externalMcp.token.onceTitle') }}
          </div>
          <div class="token_notice_subtitle">
            {{ t('room.externalMcp.token.onceSubtitle') }}
          </div>
        </div>

        <button
          class="mini_btn"
          type="button"
          :disabled="busy"
          @click="onCopyToken"
        >
          {{ t('room.externalMcp.actions.copyToken') }}
        </button>
      </div>

      <div class="token_box">
        {{ plaintextTokenText }}
      </div>
    </div>

    <div class="toggle_group top_gap action_stack">
      <label
        v-if="showEnableAction"
        class="toggle_row action_row"
      >
        <div class="toggle_text">
          <strong>{{ enableTitleText }}</strong>
          <span>{{ enableHelpText }}</span>
        </div>

        <button
          class="primary_btn action_btn"
          type="button"
          :disabled="enableDisabled"
          @click="onEnable"
        >
          {{ enableButtonText }}
        </button>
      </label>

      <label
        v-if="showRegenerateAction"
        class="toggle_row action_row"
      >
        <div class="toggle_text">
          <strong>{{ t('room.externalMcp.actions.regenerateTitle') }}</strong>
          <span>{{ t('room.externalMcp.actions.regenerateHelp') }}</span>
        </div>

        <button
          class="primary_btn action_btn"
          type="button"
          :disabled="regenerateDisabled"
          @click="onRegenerate"
        >
          {{ regenerateButtonText }}
        </button>
      </label>

      <label
        v-if="showRevokeAction"
        class="toggle_row action_row"
      >
        <div class="toggle_text">
          <strong>{{ t('room.externalMcp.actions.revokeTitle') }}</strong>
          <span>{{ t('room.externalMcp.actions.revokeHelp') }}</span>
        </div>

        <button
          class="danger_btn action_btn"
          type="button"
          :disabled="revokeDisabled"
          @click="onRevoke"
        >
          {{ revokeButtonText }}
        </button>
      </label>

      <label class="toggle_row action_row">
        <div class="toggle_text">
          <strong>{{ librechatCopyTitle }}</strong>
          <span>{{ copyHelpText }}</span>
        </div>

        <button
          class="ghost_btn action_btn"
          type="button"
          :disabled="copyLibreChatDisabled"
          @click="onCopyLibreChatConfig"
        >
          {{ copyLibreChatButtonText }}
        </button>
      </label>

      <label class="toggle_row action_row">
        <div class="toggle_text">
          <strong>{{ genericCopyTitle }}</strong>
          <span>{{ t('room.externalMcp.actions.copyGenericHelp') }}</span>
        </div>

        <button
          class="ghost_btn action_btn"
          type="button"
          :disabled="copyGenericDisabled"
          @click="onCopyGenericConfig"
        >
          {{ copyGenericButtonText }}
        </button>
      </label>
    </div>

    <div
      v-if="errorText"
      class="warning_box warning_box_warn top_gap"
    >
      {{ errorText }}
    </div>

    <div
      v-else-if="state === 'not_published'"
      class="warning_box warning_box_info top_gap"
    >
      {{ t('room.externalMcp.notices.notPublished') }}
    </div>

    <div
      v-else-if="state === 'active' && !plaintextTokenText"
      class="warning_box warning_box_info top_gap"
    >
      {{ t('room.externalMcp.notices.activeNoToken') }}
    </div>

    <div
      v-else-if="state === 'expired'"
      class="warning_box warning_box_warn top_gap"
    >
      {{ t('room.externalMcp.notices.expired') }}
    </div>

    <div
      v-else-if="state === 'revoked'"
      class="warning_box warning_box_warn top_gap"
    >
      {{ t('room.externalMcp.notices.revoked') }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  external_mcp_publish_status: { type: Object, default: () => ({}) },
  external_mcp_publish_loading: { type: Boolean, default: false },
  external_mcp_publish_error: { type: String, default: '' },
  external_mcp_publish_plaintext_token: { type: String, default: '' },
  external_mcp_publish_copy_loading_kind: { type: String, default: '' },
  external_mcp_publish_enable_loading: { type: Boolean, default: false },
  external_mcp_publish_revoke_loading: { type: Boolean, default: false },
  external_mcp_publish_regenerate_loading: { type: Boolean, default: false },

  handle_external_mcp_publish_enable: { type: Function, default: null },
  handle_external_mcp_publish_revoke: { type: Function, default: null },
  handle_external_mcp_publish_regenerate: { type: Function, default: null },
  handle_external_mcp_publish_copy_config: { type: Function, default: null },
  handle_external_mcp_publish_copy_token: { type: Function, default: null },
  refresh_external_mcp_publish: { type: Function, default: null },
})

const { t } = useI18n()

const expiresInDays = ref('30')
const maxCalls = ref('')
const clientLabel = ref(t('room.externalMcp.defaults.clientLabel'))
const endpointUrl = ref('')

const record = computed(() => {
  return props.external_mcp_publish_status && typeof props.external_mcp_publish_status === 'object'
    ? props.external_mcp_publish_status
    : {}
})

const plaintextTokenText = computed(() => {
  return String(props.external_mcp_publish_plaintext_token || '').trim()
})

const state = computed(() => {
  const row = record.value
  const raw = String(
    row.status ||
    row.publish_state ||
    row.external_publish_state ||
    row.publication_state ||
    row.state ||
    ''
  ).trim().toLowerCase()

  if (raw === 'active' || raw === 'published' || raw === 'enabled') return 'active'
  if (raw === 'revoked') return 'revoked'
  if (raw === 'expired') return 'expired'
  if (raw === 'not_published' || raw === 'unpublished' || raw === 'disabled') return 'not_published'

  if (String(row.revoked_at || '').trim()) return 'revoked'
  if (String(row.publish_id || row.token_hash || row.provider_id || '').trim()) return 'active'

  return 'not_published'
})

const busy = computed(() => {
  return !!(
    props.external_mcp_publish_loading ||
    props.external_mcp_publish_enable_loading ||
    props.external_mcp_publish_revoke_loading ||
    props.external_mcp_publish_regenerate_loading ||
    props.external_mcp_publish_copy_loading_kind
  )
})

const stateText = computed(() => {
  if (props.external_mcp_publish_loading) return t('room.externalMcp.states.loading')
  if (state.value === 'active') return t('room.externalMcp.states.active')
  if (state.value === 'revoked') return t('room.externalMcp.states.revoked')
  if (state.value === 'expired') return t('room.externalMcp.states.expired')
  return t('room.externalMcp.states.notPublished')
})

const rootStateClass = computed(() => {
  if (state.value === 'active') return 'external_mcp_publish_card_active'
  if (state.value === 'revoked') return 'external_mcp_publish_card_revoked'
  if (state.value === 'expired') return 'external_mcp_publish_card_expired'
  return 'external_mcp_publish_card_empty'
})

const statePillClass = computed(() => {
  if (state.value === 'active') return 'state_pill_active'
  if (state.value === 'revoked') return 'state_pill_revoked'
  if (state.value === 'expired') return 'state_pill_expired'
  return 'state_pill_empty'
})

const stateValueClass = computed(() => {
  if (state.value === 'active') return 'state_value_active'
  if (state.value === 'revoked') return 'state_value_revoked'
  if (state.value === 'expired') return 'state_value_expired'
  return 'state_value_empty'
})

const providerIdText = computed(() => {
  return String(record.value.provider_id || '').trim() || t('room.externalMcp.values.none')
})

const sourceRoomIdText = computed(() => {
  return String(record.value.source_room_id || '').trim() || t('room.externalMcp.values.none')
})

const resultViewText = computed(() => {
  return String(record.value.result_view || '').trim() || 'final_result_only'
})

const expiresAtText = computed(() => {
  return String(record.value.expires_at || '').trim() || t('room.externalMcp.values.none')
})

const lastUsedText = computed(() => {
  return String(record.value.last_used_at || '').trim() || t('room.externalMcp.values.neverUsed')
})

const usedCountText = computed(() => {
  const n = Number(record.value.used_count)
  if (Number.isFinite(n) && n >= 0) return String(n)
  return '0'
})

const clientLabelText = computed(() => {
  return String(record.value.client_label || '').trim() || t('room.externalMcp.values.none')
})

const errorText = computed(() => {
  return String(props.external_mcp_publish_error || '').trim()
})

const showEnableAction = computed(() => {
  return state.value === 'not_published' || state.value === 'revoked'
})

const showRegenerateAction = computed(() => {
  return state.value === 'active' || state.value === 'expired'
})

const showRevokeAction = computed(() => {
  return state.value === 'active'
})

const enableTitleText = computed(() => {
  if (state.value === 'revoked') return t('room.externalMcp.actions.reenableTitle')
  return t('room.externalMcp.actions.enableTitle')
})

const enableHelpText = computed(() => {
  if (state.value === 'revoked') return t('room.externalMcp.actions.reenableHelp')
  return t('room.externalMcp.actions.enableHelp')
})

const enableButtonText = computed(() => {
  if (props.external_mcp_publish_enable_loading) return t('room.externalMcp.actions.enabling')
  if (state.value === 'revoked') return t('room.externalMcp.actions.reenable')
  return t('room.externalMcp.actions.enable')
})

const regenerateButtonText = computed(() => {
  if (props.external_mcp_publish_regenerate_loading) return t('room.externalMcp.actions.regenerating')
  if (state.value === 'expired') return t('room.externalMcp.actions.regenerate')
  return t('room.externalMcp.actions.regenerateToken')
})

const revokeButtonText = computed(() => {
  if (props.external_mcp_publish_revoke_loading) return t('room.externalMcp.actions.revoking')
  return t('room.externalMcp.actions.revoke')
})

const refreshButtonText = computed(() => {
  if (props.external_mcp_publish_loading) return t('room.externalMcp.actions.refreshing')
  return t('room.externalMcp.actions.refresh')
})

const librechatCopyTitle = computed(() => {
  return plaintextTokenText.value
    ? t('room.externalMcp.actions.copyLibreChatTitle')
    : t('room.externalMcp.actions.copyLibreChatTemplateTitle')
})

const genericCopyTitle = computed(() => {
  return plaintextTokenText.value
    ? t('room.externalMcp.actions.copyGenericTitle')
    : t('room.externalMcp.actions.copyGenericTemplateTitle')
})

const copyHelpText = computed(() => {
  if (plaintextTokenText.value) {
    return t('room.externalMcp.actions.copyWithTokenHelp')
  }
  return t('room.externalMcp.actions.copyTemplateHelp')
})

const copyLibreChatButtonText = computed(() => {
  if (props.external_mcp_publish_copy_loading_kind === 'librechat') {
    return t('room.externalMcp.actions.copying')
  }
  return t('room.externalMcp.actions.copy')
})

const copyGenericButtonText = computed(() => {
  if (props.external_mcp_publish_copy_loading_kind === 'generic') {
    return t('room.externalMcp.actions.copying')
  }
  return t('room.externalMcp.actions.copy')
})

const enableDisabled = computed(() => {
  return busy.value || typeof props.handle_external_mcp_publish_enable !== 'function'
})

const regenerateDisabled = computed(() => {
  return busy.value || typeof props.handle_external_mcp_publish_regenerate !== 'function'
})

const revokeDisabled = computed(() => {
  return busy.value || typeof props.handle_external_mcp_publish_revoke !== 'function'
})

const copyLibreChatDisabled = computed(() => {
  return busy.value || typeof props.handle_external_mcp_publish_copy_config !== 'function'
})

const copyGenericDisabled = computed(() => {
  return busy.value || typeof props.handle_external_mcp_publish_copy_config !== 'function'
})

function buildMutationInput() {
  return {
    expires_in_days: String(expiresInDays.value || '').trim(),
    max_calls: String(maxCalls.value || '').trim(),
    client_label: String(clientLabel.value || '').trim(),
    endpoint_url: String(endpointUrl.value || '').trim(),
  }
}

async function onEnable() {
  if (enableDisabled.value) return
  await props.handle_external_mcp_publish_enable(buildMutationInput())
}

async function onRegenerate() {
  if (regenerateDisabled.value) return
  await props.handle_external_mcp_publish_regenerate(buildMutationInput())
}

async function onRevoke() {
  if (revokeDisabled.value) return
  await props.handle_external_mcp_publish_revoke()
}

async function onCopyLibreChatConfig() {
  if (copyLibreChatDisabled.value) return
  await props.handle_external_mcp_publish_copy_config('librechat')
}

async function onCopyGenericConfig() {
  if (copyGenericDisabled.value) return
  await props.handle_external_mcp_publish_copy_config('generic')
}

async function onCopyToken() {
  if (busy.value) return
  if (typeof props.handle_external_mcp_publish_copy_token !== 'function') return
  await props.handle_external_mcp_publish_copy_token()
}

async function onRefresh() {
  if (busy.value) return
  if (typeof props.refresh_external_mcp_publish !== 'function') return
  await props.refresh_external_mcp_publish({ silent: false })
}
</script>

<style scoped>
.external_mcp_publish_card {
  position: relative;
  overflow: hidden;
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, var(--selected-bg) 6%),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
}

.external_mcp_publish_card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: color-mix(in srgb, var(--selected) 72%, transparent);
  opacity: 0.72;
}

.external_mcp_publish_card_active::before {
  background: #22c55e;
}

.external_mcp_publish_card_revoked::before {
  background: #ef4444;
}

.external_mcp_publish_card_expired::before {
  background: #f59e0b;
}

.external_header {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.external_title_group {
  min-width: 0;
}

.external_eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 23px;
  padding: 0 9px;
  margin-bottom: 8px;
  border: 1px solid color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 74%, transparent);
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
}

.external_eyebrow_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

.external_title {
  letter-spacing: -0.012em;
}

.external_subtitle {
  max-width: 760px;
}

.external_header_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
}

.state_pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.state_pill_active {
  border-color: rgba(34, 197, 94, 0.38);
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.state_pill_revoked {
  border-color: rgba(239, 68, 68, 0.38);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.state_pill_expired {
  border-color: rgba(245, 158, 11, 0.42);
  background: rgba(245, 158, 11, 0.11);
  color: #d97706;
}

.state_pill_empty {
  border-color: color-mix(in srgb, var(--text-secondary) 24%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  color: var(--text-secondary);
}

.publish_overview_grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.overview_tile {
  min-width: 0;
  min-height: 68px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 7px;
}

.overview_tile_status {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 58%, var(--sidebar-bg));
}

.overview_tile span {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 680;
  line-height: 1.25;
}

.overview_tile strong,
.overview_tile code {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 760;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview_tile code {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 620;
}

.state_value_active {
  color: #16a34a !important;
}

.state_value_revoked {
  color: #ef4444 !important;
}

.state_value_expired {
  color: #d97706 !important;
}

.state_value_empty {
  color: var(--text-secondary) !important;
}

.publish_config_panel {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.config_panel_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.config_panel_title {
  color: var(--text-main);
  font-size: 0.88rem;
  font-weight: 800;
  line-height: 1.35;
}

.config_panel_hint {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
}

.token_notice {
  border-color: rgba(245, 158, 11, 0.42);
  background:
    linear-gradient(
      180deg,
      rgba(245, 158, 11, 0.12),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
}

.token_notice_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.token_notice_title {
  color: var(--text-main);
  font-weight: 800;
  font-size: 0.88rem;
  line-height: 1.35;
}

.token_notice_subtitle {
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.token_box {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  word-break: break-all;
  white-space: pre-wrap;
  padding: 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  max-height: 132px;
  overflow: auto;
}

.action_stack {
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.action_row {
  align-items: center;
}

.action_btn {
  flex: 0 0 auto;
  min-width: 116px;
}

@media (max-width: 980px) {
  .publish_overview_grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .external_header {
    flex-direction: column;
    align-items: stretch;
  }

  .external_header_actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .publish_overview_grid {
    grid-template-columns: 1fr;
  }

  .token_notice_head,
  .action_row {
    flex-direction: column;
    align-items: stretch;
  }

  .action_btn {
    width: 100%;
  }
}
</style>
