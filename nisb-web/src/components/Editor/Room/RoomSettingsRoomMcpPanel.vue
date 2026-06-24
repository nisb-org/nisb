<template>
  <div class="supervisor_box top_gap room_mcp_panel">
    <div class="room_mcp_head">
      <div class="room_mcp_title_block">
        <div class="room_mcp_eyebrow">
          <span class="room_mcp_dot"></span>
          <span>{{ t('room.roomMcpPanel.eyebrow') }}</span>
        </div>

        <div class="section_title">
          {{ t('room.roomMcpPanel.title') }}
        </div>

        <div class="section_subtitle room_mcp_subtitle">
          {{ t('room.roomMcpPanel.subtitle') }}
        </div>
      </div>

      <div class="room_mcp_state_chips">
        <span class="tag" :class="{ tag_active: !!form.room_mcp_provider_enabled }">
          {{ providerEnabledChipText }}
        </span>

        <span class="tag" :class="{ tag_active: !!form.shared_room_config_enabled }">
          {{ sharedCapabilityChipText }}
        </span>
      </div>
    </div>

    <div class="mcp_subpanel provider_config_panel top_gap">
      <div class="subpanel_head">
        <div>
          <div class="subpanel_title">
            {{ t('room.roomMcpPanel.sections.provider.title') }}
          </div>
          <div class="subpanel_subtitle">
            {{ t('room.roomMcpPanel.sections.provider.subtitle') }}
          </div>
        </div>
      </div>

      <div class="toggle_group top_gap">
        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.roomMcpPanel.toggles.providerEnabled.title') }}</strong>
            <span>{{ t('room.roomMcpPanel.toggles.providerEnabled.description') }}</span>
          </div>
          <input v-model="form.room_mcp_provider_enabled" type="checkbox" />
        </label>
      </div>

      <div class="form_grid top_gap">
        <label class="field">
          <span>{{ t('room.roomMcpPanel.fields.providerName.label') }}</span>
          <input
            v-model="form.room_mcp_provider_name"
            type="text"
            :placeholder="t('room.roomMcpPanel.fields.providerName.placeholder')"
          />
          <div class="field_hint">
            {{ t('room.roomMcpPanel.fields.providerName.hint') }}
          </div>
        </label>

        <label class="field">
          <span>{{ t('room.roomMcpPanel.fields.providerSummary.label') }}</span>
          <input
            v-model="form.room_mcp_provider_summary"
            type="text"
            :placeholder="t('room.roomMcpPanel.fields.providerSummary.placeholder')"
          />
          <div class="field_hint">
            {{ t('room.roomMcpPanel.fields.providerSummary.hint') }}
          </div>
        </label>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.publishStatus.label') }}</span>
          <div class="readonly_box status_readout">
            {{ roomMcpPublishStatusText }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.boundarySummary.label') }}</span>
          <div class="readonly_box status_readout">
            {{ roomMcpBoundarySummaryText }}
          </div>
        </div>
      </div>

      <div class="helper_text boundary_helper">
        {{ t('room.roomMcpPanel.helpers.providerBoundary') }}
      </div>
    </div>

    <RoomSettingsExternalMcpPublishCard
      :external_mcp_publish_status="external_mcp_publish_status"
      :external_mcp_publish_loading="external_mcp_publish_loading"
      :external_mcp_publish_error="external_mcp_publish_error"
      :external_mcp_publish_plaintext_token="external_mcp_publish_plaintext_token"
      :external_mcp_publish_copy_loading_kind="external_mcp_publish_copy_loading_kind"
      :external_mcp_publish_enable_loading="external_mcp_publish_enable_loading"
      :external_mcp_publish_revoke_loading="external_mcp_publish_revoke_loading"
      :external_mcp_publish_regenerate_loading="external_mcp_publish_regenerate_loading"
      :handle_external_mcp_publish_enable="handle_external_mcp_publish_enable"
      :handle_external_mcp_publish_revoke="handle_external_mcp_publish_revoke"
      :handle_external_mcp_publish_regenerate="handle_external_mcp_publish_regenerate"
      :handle_external_mcp_publish_copy_config="handle_external_mcp_publish_copy_config"
      :handle_external_mcp_publish_copy_token="handle_external_mcp_publish_copy_token"
      :refresh_external_mcp_publish="refresh_external_mcp_publish"
    />

    <div class="mcp_subpanel top_gap">
      <div class="subpanel_head">
        <div>
          <div class="subpanel_title">
            {{ t('room.roomMcpPanel.sections.publication.title') }}
          </div>
          <div class="subpanel_subtitle">
            {{ t('room.roomMcpPanel.sections.publication.subtitle') }}
          </div>
        </div>
      </div>

      <div class="record_grid top_gap">
        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.publicationState.label') }}</span>
          <code>{{ publicationStateText }}</code>
        </div>

        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.providerId.label') }}</span>
          <code>{{ publicationProviderIdText }}</code>
        </div>

        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.visibilityMode.label') }}</span>
          <code>{{ publicationVisibilityModeText }}</code>
        </div>

        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.boundaryHint.label') }}</span>
          <strong>{{ publicationBoundaryHintText }}</strong>
        </div>

        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.publishedAt.label') }}</span>
          <strong>{{ publicationPublishedAtText }}</strong>
        </div>

        <div class="record_tile">
          <span>{{ t('room.roomMcpPanel.fields.updatedAt.label') }}</span>
          <strong>{{ publicationUpdatedAtText }}</strong>
        </div>
      </div>

      <div class="helper_text boundary_helper">
        {{ t('room.roomMcpPanel.helpers.publicationBoundary') }}
      </div>
    </div>

    <div class="mcp_subpanel top_gap">
      <div class="subpanel_head">
        <div>
          <div class="subpanel_title">
            {{ t('room.roomMcpPanel.sections.shareRef.title') }}
          </div>
          <div class="subpanel_subtitle">
            {{ t('room.roomMcpPanel.sections.shareRef.subtitle') }}
          </div>
        </div>
      </div>

      <div class="form_grid top_gap">
        <div class="field readonly_field field_full">
          <span>{{ t('room.roomMcpPanel.fields.shareRefPreview.label') }}</span>
          <div class="readonly_box artifact_preview_box">
            {{ roomMcpShareRefPreviewText }}
          </div>
          <div class="field_hint">
            {{ t('room.roomMcpPanel.fields.shareRefPreview.hint') }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.shareRefStatus.label') }}</span>
          <div class="readonly_box">
            {{ roomMcpShareRefStatusText }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.issuedAt.label') }}</span>
          <div class="readonly_box">
            {{ roomMcpShareRefIssuedAtText }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.consumerBoundary.label') }}</span>
          <div class="readonly_box">
            {{ roomMcpShareRefBoundaryHintText }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.grantId.label') }}</span>
          <div class="readonly_box">
            {{ currentGrantIdText }}
          </div>
        </div>

        <div class="field readonly_field">
          <span>{{ t('room.roomMcpPanel.fields.artifactId.label') }}</span>
          <div class="readonly_box">
            {{ currentArtifactIdText }}
          </div>
        </div>
      </div>

      <div class="helper_text boundary_helper">
        {{ t('room.roomMcpPanel.helpers.shareRefBoundary') }}
      </div>

      <div class="toggle_group top_gap">
        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.roomMcpPanel.actions.generateArtifact.title') }}</strong>
            <span>{{ t('room.roomMcpPanel.actions.generateArtifact.description') }}</span>
          </div>
          <button
            class="primary_btn action_btn"
            type="button"
            :disabled="roomMcpShareRefGenerateDisabled"
            @click="onGenerateRoomMcpShareRef"
          >
            {{ roomMcpShareRefGenerateButtonText }}
          </button>
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.roomMcpPanel.actions.copyArtifact.title') }}</strong>
            <span>{{ t('room.roomMcpPanel.actions.copyArtifact.description') }}</span>
          </div>
          <button
            class="ghost_btn action_btn"
            type="button"
            :disabled="roomMcpShareRefCopyDisabled"
            @click="onCopyRoomMcpShareRef"
          >
            {{ roomMcpShareRefCopyButtonText }}
          </button>
        </label>

        <label class="toggle_row">
          <div class="toggle_text">
            <strong>{{ t('room.roomMcpPanel.actions.refreshGrants.title') }}</strong>
            <span>{{ t('room.roomMcpPanel.actions.refreshGrants.description') }}</span>
          </div>
          <button
            class="ghost_btn action_btn"
            type="button"
            :disabled="grantListRefreshDisabled"
            @click="onRefreshGrantList"
          >
            {{ grantListRefreshButtonText }}
          </button>
        </label>
      </div>

      <div
        v-if="roomMcpShareRefErrorText"
        class="warning_box warning_box_warn top_gap"
      >
        {{ roomMcpShareRefErrorText }}
      </div>

      <div
        v-else-if="!form.room_mcp_provider_enabled"
        class="warning_box warning_box_info top_gap"
      >
        {{ t('room.roomMcpPanel.notices.providerDisabled') }}
      </div>

      <div
        v-else-if="!form.shared_room_config_enabled"
        class="warning_box warning_box_warn top_gap"
      >
        {{ t('room.roomMcpPanel.notices.sharedAutoReplyDisabled') }}
      </div>

      <div
        v-else
        class="warning_box warning_box_info top_gap"
      >
        {{ t('room.roomMcpPanel.notices.artifactReady') }}
      </div>
    </div>

    <div class="mcp_subpanel grant_management_panel top_gap">
      <div class="subpanel_head">
        <div>
          <div class="subpanel_title">
            {{ t('room.roomMcpPanel.sections.grants.title') }}
          </div>
          <div class="subpanel_subtitle">
            {{ t('room.roomMcpPanel.sections.grants.subtitle') }}
          </div>
        </div>
      </div>

      <div class="grant_summary_grid top_gap">
        <div class="metric_tile">
          <span>{{ t('room.roomMcpPanel.fields.grantTotal.label') }}</span>
          <strong>{{ grantCountText }}</strong>
        </div>

        <div class="metric_tile metric_active">
          <span>{{ t('room.roomMcpPanel.fields.grantActive.label') }}</span>
          <strong>{{ grantActiveCountText }}</strong>
        </div>

        <div class="metric_tile metric_revoked">
          <span>{{ t('room.roomMcpPanel.fields.grantRevoked.label') }}</span>
          <strong>{{ grantRevokedCountText }}</strong>
        </div>

        <div class="metric_tile metric_expired">
          <span>{{ t('room.roomMcpPanel.fields.grantExpired.label') }}</span>
          <strong>{{ grantExpiredCountText }}</strong>
        </div>
      </div>

      <div
        v-if="grantRows.length"
        class="grant_list top_gap"
      >
        <div
          v-for="item in grantRows"
          :key="item.grant_id || item.artifact_id || item.descriptor_ref || item.issued_at"
          class="grant_card"
        >
          <div class="grant_card_head">
            <div class="grant_card_title">
              {{ item.grant_id || t('room.roomMcpPanel.grant.untitled') }}
            </div>

            <div class="grant_card_state" :class="grantStateClass(item.grant_state)">
              {{ normalizeGrantStateText(item.grant_state) }}
            </div>
          </div>

          <div class="grant_card_body">
            <div class="grant_meta_row">
              <span>artifact_id</span>
              <strong>{{ item.artifact_id || t('room.roomMcpPanel.values.none') }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>discovery_mode</span>
              <strong>{{ item.discovery_mode || t('room.roomMcpPanel.values.none') }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>result_view</span>
              <strong>{{ item.scope?.result_view || 'final_result_only' }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>audience</span>
              <strong>{{ formatGrantAudience(item.audience) }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>issued_at</span>
              <strong>{{ item.issued_at || t('room.roomMcpPanel.values.none') }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>expires_at</span>
              <strong>{{ item.expires_at || t('room.roomMcpPanel.values.none') }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>last_resolved_at</span>
              <strong>{{ item.last_resolved_at || t('room.roomMcpPanel.values.none') }}</strong>
            </div>

            <div class="grant_meta_row">
              <span>last_consumed_at</span>
              <strong>{{ item.last_consumed_at || t('room.roomMcpPanel.values.none') }}</strong>
            </div>
          </div>

          <div class="grant_card_actions">
            <button
              class="danger_btn"
              type="button"
              :disabled="grantRevokeDisabled(item)"
              @click="onRevokeGrant(item)"
            >
              {{ grantRevokeButtonText(item) }}
            </button>
          </div>
        </div>
      </div>

      <div
        v-else
        class="warning_box warning_box_info top_gap"
      >
        {{ t('room.roomMcpPanel.notices.noGrants') }}
      </div>
    </div>

    <div
      v-if="form.room_mcp_provider_enabled && !form.shared_room_config_enabled"
      class="warning_box warning_box_warn top_gap"
    >
      {{ t('room.roomMcpPanel.notices.providerEnabledSharedOff') }}
    </div>

    <div
      v-else-if="form.room_mcp_provider_enabled"
      class="warning_box warning_box_info top_gap"
    >
      {{ t('room.roomMcpPanel.notices.providerEnabledSharedOn') }}
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import RoomSettingsExternalMcpPublishCard from './RoomSettingsExternalMcpPublishCard.vue'

const props = defineProps({
  form: { type: Object, required: true },

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

  handle_room_mcp_share_ref_generate: { type: Function, default: null },
  handle_room_mcp_share_ref_copy: { type: Function, default: null },
  handle_room_mcp_grant_list_refresh: { type: Function, default: null },
  handle_room_mcp_grant_revoke: { type: Function, default: null },

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

const shareRefCopied = ref(false)
let shareRefCopiedTimer = null

const publicationRecord = computed(() => {
  return props.room_mcp_publication && typeof props.room_mcp_publication === 'object'
    ? props.room_mcp_publication
    : {}
})

const shareRefStatusObject = computed(() => {
  return props.room_mcp_share_ref_status && typeof props.room_mcp_share_ref_status === 'object'
    ? props.room_mcp_share_ref_status
    : {}
})

const grantsStatusObject = computed(() => {
  return props.room_mcp_grants_status && typeof props.room_mcp_grants_status === 'object'
    ? props.room_mcp_grants_status
    : {}
})

const grantRows = computed(() => {
  return Array.isArray(props.room_mcp_grants) ? props.room_mcp_grants : []
})

const currentArtifactRecord = computed(() => {
  const status = shareRefStatusObject.value || {}
  const directGrant = status.grant && typeof status.grant === 'object' ? status.grant : null
  const directArtifact = status.artifact && typeof status.artifact === 'object' ? status.artifact : null

  return {
    grant: directGrant || {},
    artifact: directArtifact || {},
  }
})

const providerEnabledChipText = computed(() => {
  return props.form?.room_mcp_provider_enabled
    ? t('room.roomMcpPanel.chips.providerOn')
    : t('room.roomMcpPanel.chips.providerOff')
})

const sharedCapabilityChipText = computed(() => {
  return props.form?.shared_room_config_enabled
    ? t('room.roomMcpPanel.chips.sharedOn')
    : t('room.roomMcpPanel.chips.sharedOff')
})

const roomMcpPublishStatusText = computed(() => {
  const form = props.form || {}
  const publication = publicationRecord.value
  const enabled = !!form.room_mcp_provider_enabled
  const name = String(form.room_mcp_provider_name || '').trim()
  const summary = String(form.room_mcp_provider_summary || '').trim()
  const publicationState = String(publication.publication_state || '').trim()
  const publishEnabled = publication.publish_enabled === true

  if (!enabled) {
    return t('room.roomMcpPanel.publishStatus.notPublished')
  }

  if (publicationState === 'active' || publishEnabled) {
    if (name && summary) {
      return t('room.roomMcpPanel.publishStatus.publishedWithNameSummary', { name, summary })
    }
    if (name) {
      return t('room.roomMcpPanel.publishStatus.publishedWithName', { name })
    }
    if (summary) {
      return t('room.roomMcpPanel.publishStatus.publishedWithSummary', { summary })
    }
    return t('room.roomMcpPanel.publishStatus.publishedDefault')
  }

  return t('room.roomMcpPanel.publishStatus.pendingSaveOrRefresh')
})

const roomMcpBoundarySummaryText = computed(() => {
  const publication = publicationRecord.value
  const boundaryHint = String(publication.boundary_hint || '').trim()
  if (boundaryHint) return boundaryHint

  const form = props.form || {}
  const sharedEnabled = !!form.shared_room_config_enabled
  const replyMode = String(form.reply_mode || 'manual').trim() || 'manual'

  if (!sharedEnabled) {
    return t('room.roomMcpPanel.boundary.sharedOff')
  }

  return t('room.roomMcpPanel.boundary.sharedOn', { replyMode })
})

const publicationStateText = computed(() => {
  const publication = publicationRecord.value
  const state = String(publication.publication_state || '').trim()
  if (state === 'active') return 'active'
  if (state === 'disabled') return 'disabled'
  if (props.form?.room_mcp_provider_enabled) return 'pending-save-or-refresh'
  return 'not-published'
})

const publicationProviderIdText = computed(() => {
  return String(publicationRecord.value.provider_id || '').trim() || t('room.roomMcpPanel.values.none')
})

const publicationVisibilityModeText = computed(() => {
  return String(publicationRecord.value.visibility_mode || '').trim() || 'room_visible_and_grant_capable'
})

const publicationBoundaryHintText = computed(() => {
  return String(publicationRecord.value.boundary_hint || '').trim() || roomMcpBoundarySummaryText.value
})

const publicationPublishedAtText = computed(() => {
  return String(publicationRecord.value.published_at || '').trim() || t('room.roomMcpPanel.values.none')
})

const publicationUpdatedAtText = computed(() => {
  return String(publicationRecord.value.updated_at || '').trim() || t('room.roomMcpPanel.values.none')
})

const roomMcpShareRefPreviewText = computed(() => {
  const preview = String(props.room_mcp_share_ref_preview || '').trim()
  if (preview) return preview

  if (!props.form?.room_mcp_provider_enabled) {
    return t('room.roomMcpPanel.shareRefPreview.providerDisabled')
  }

  return t('room.roomMcpPanel.shareRefPreview.notGenerated')
})

const roomMcpShareRefStatusText = computed(() => {
  const status = shareRefStatusObject.value
  const code = String(
    status.code ||
    status.status ||
    status.kind ||
    ''
  ).trim()

  const message = String(
    status.message ||
    status.user_message ||
    ''
  ).trim()

  if (props.room_mcp_share_ref_loading) {
    return t('room.roomMcpPanel.shareRefStatus.loading')
  }

  if (props.room_mcp_share_ref_error) {
    return String(props.room_mcp_share_ref_error).trim()
  }

  if (message) {
    return message
  }

  if (props.room_mcp_share_ref_preview) {
    return code
      ? t('room.roomMcpPanel.shareRefStatus.readyWithCode', { code })
      : t('room.roomMcpPanel.shareRefStatus.ready')
  }

  return t('room.roomMcpPanel.shareRefStatus.notGenerated')
})

const roomMcpShareRefIssuedAtText = computed(() => {
  const status = shareRefStatusObject.value
  const grant = currentArtifactRecord.value.grant || {}
  const artifact = currentArtifactRecord.value.artifact || {}

  return String(
    props.room_mcp_share_ref_last_issued_at ||
    grant.issued_at ||
    artifact.issued_at ||
    status.issued_at ||
    status.generated_at ||
    status.updated_at ||
    ''
  ).trim() || t('room.roomMcpPanel.values.none')
})

const roomMcpShareRefBoundaryHintText = computed(() => {
  const artifact = currentArtifactRecord.value.artifact || {}
  const boundaryHint = String(artifact.boundary_hint || '').trim()
  if (boundaryHint) return boundaryHint

  const form = props.form || {}
  const replyMode = String(form.reply_mode || 'manual').trim() || 'manual'
  const sharedEnabled = !!form.shared_room_config_enabled
  const supervisorEnabled = !!form.supervisor_enabled

  return t('room.roomMcpPanel.shareRefBoundary.generatedHint', {
    replyMode,
    sharedEnabled: sharedEnabled ? 'true' : 'false',
    supervisorEnabled: supervisorEnabled ? 'true' : 'false',
  })
})

const currentGrantIdText = computed(() => {
  const grant = currentArtifactRecord.value.grant || {}
  const artifact = currentArtifactRecord.value.artifact || {}
  return String(grant.grant_id || artifact.grant_id || '').trim() || t('room.roomMcpPanel.values.none')
})

const currentArtifactIdText = computed(() => {
  const grant = currentArtifactRecord.value.grant || {}
  const artifact = currentArtifactRecord.value.artifact || {}
  return String(grant.artifact_id || artifact.artifact_id || '').trim() || t('room.roomMcpPanel.values.none')
})

const roomMcpShareRefGenerateDisabled = computed(() => {
  return !!props.room_mcp_share_ref_loading || !props.form?.room_mcp_provider_enabled
})

const roomMcpShareRefCopyDisabled = computed(() => {
  return !!props.room_mcp_share_ref_loading || !String(props.room_mcp_share_ref_preview || '').trim()
})

const roomMcpShareRefGenerateButtonText = computed(() => {
  if (props.room_mcp_share_ref_loading) return t('room.roomMcpPanel.actions.generateArtifact.generating')
  if (props.room_mcp_share_ref_preview) return t('room.roomMcpPanel.actions.generateArtifact.buttonRefresh')
  return t('room.roomMcpPanel.actions.generateArtifact.buttonGenerate')
})

const roomMcpShareRefCopyButtonText = computed(() => {
  if (shareRefCopied.value) return t('room.roomMcpPanel.actions.copyArtifact.copied')
  return t('room.roomMcpPanel.actions.copyArtifact.copy')
})

const roomMcpShareRefErrorText = computed(() => {
  return String(props.room_mcp_share_ref_error || '').trim()
})

const grantListRefreshDisabled = computed(() => {
  return !!props.room_mcp_grants_loading || typeof props.handle_room_mcp_grant_list_refresh !== 'function'
})

const grantListRefreshButtonText = computed(() => {
  if (props.room_mcp_grants_loading) return t('room.roomMcpPanel.actions.refreshGrants.refreshing')
  return t('room.roomMcpPanel.actions.refreshGrants.refresh')
})

const grantCountText = computed(() => {
  const total = Number(grantsStatusObject.value.total)
  if (Number.isFinite(total) && total >= 0) return String(total)
  return String(grantRows.value.length)
})

const grantActiveCountText = computed(() => {
  const value = Number(grantsStatusObject.value.active)
  if (Number.isFinite(value) && value >= 0) return String(value)
  return String(grantRows.value.filter(item => String(item?.grant_state || '').trim() === 'active').length)
})

const grantRevokedCountText = computed(() => {
  const value = Number(grantsStatusObject.value.revoked)
  if (Number.isFinite(value) && value >= 0) return String(value)
  return String(grantRows.value.filter(item => String(item?.grant_state || '').trim() === 'revoked').length)
})

const grantExpiredCountText = computed(() => {
  const value = Number(grantsStatusObject.value.expired)
  if (Number.isFinite(value) && value >= 0) return String(value)
  return String(grantRows.value.filter(item => String(item?.grant_state || '').trim() === 'expired').length)
})

function normalizeGrantStateText(value) {
  const state = String(value || '').trim().toLowerCase()
  if (state === 'active') return 'active'
  if (state === 'revoked') return 'revoked'
  if (state === 'expired') return 'expired'
  return state || t('room.roomMcpPanel.values.unknown')
}

function grantStateClass(value) {
  const state = normalizeGrantStateText(value)
  if (state === 'active') return 'grant_state_active'
  if (state === 'revoked') return 'grant_state_revoked'
  if (state === 'expired') return 'grant_state_expired'
  return 'grant_state_unknown'
}

function formatGrantAudience(audience) {
  const row = audience && typeof audience === 'object' ? audience : {}
  const type = String(row.type || '').trim()
  const peerId = String(row.peer_id || '').trim()
  const remoteUserId = String(row.remote_user_id || '').trim()
  const consumerRoomId = String(row.consumer_room_id || '').trim()

  if (peerId && remoteUserId) {
    return `${type || 'peer_consumer'} / ${peerId} / ${remoteUserId}`
  }
  if (consumerRoomId) {
    return `${type || 'consumer_room'} / ${consumerRoomId}`
  }
  if (type) {
    return type
  }
  return t('room.roomMcpPanel.values.unspecified')
}

function grantRevokeDisabled(item) {
  const state = String(item?.grant_state || '').trim().toLowerCase()
  if (typeof props.handle_room_mcp_grant_revoke !== 'function') return true
  if (props.room_mcp_grant_revoke_loading_id) return true
  return state !== 'active'
}

function grantRevokeButtonText(item) {
  const key = item?.grant_id || item?.artifact_id || ''
  const state = String(item?.grant_state || '').trim().toLowerCase()

  if (props.room_mcp_grant_revoke_loading_id && props.room_mcp_grant_revoke_loading_id === key) {
    return t('room.roomMcpPanel.actions.revokeGrant.revoking')
  }
  if (state !== 'active') {
    return t('room.roomMcpPanel.actions.revokeGrant.unavailable')
  }
  return t('room.roomMcpPanel.actions.revokeGrant.revoke')
}

function markShareRefCopied() {
  shareRefCopied.value = true
  if (shareRefCopiedTimer) {
    clearTimeout(shareRefCopiedTimer)
  }
  shareRefCopiedTimer = setTimeout(() => {
    shareRefCopied.value = false
    shareRefCopiedTimer = null
  }, 1600)
}

async function onGenerateRoomMcpShareRef() {
  if (roomMcpShareRefGenerateDisabled.value) return
  if (typeof props.handle_room_mcp_share_ref_generate !== 'function') return
  await props.handle_room_mcp_share_ref_generate()
}

async function onCopyRoomMcpShareRef() {
  if (roomMcpShareRefCopyDisabled.value) return

  const text = String(props.room_mcp_share_ref_preview || '').trim()
  if (!text) return

  if (typeof props.handle_room_mcp_share_ref_copy === 'function') {
    const copied = await props.handle_room_mcp_share_ref_copy(text)
    if (copied !== false) {
      markShareRefCopied()
    }
    return
  }

  if (typeof navigator !== 'undefined' && navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      markShareRefCopied()
    } catch (_) {
      // Keep silent; the unified toast/error path can be handled by the caller.
    }
  }
}

async function onRefreshGrantList() {
  if (grantListRefreshDisabled.value) return
  await props.handle_room_mcp_grant_list_refresh()
}

async function onRevokeGrant(item) {
  if (grantRevokeDisabled(item)) return
  if (typeof props.handle_room_mcp_grant_revoke !== 'function') return

  await props.handle_room_mcp_grant_revoke({
    grant_id: String(item?.grant_id || '').trim(),
    artifact_id: String(item?.artifact_id || '').trim(),
    grant: item,
  })
}

onBeforeUnmount(() => {
  if (shareRefCopiedTimer) {
    clearTimeout(shareRefCopiedTimer)
    shareRefCopiedTimer = null
  }
})
</script>

<style scoped>
.room_mcp_panel {
  position: relative;
  overflow: hidden;
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
}

.room_mcp_panel::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: color-mix(in srgb, var(--selected) 58%, transparent);
  opacity: 0.62;
}

.room_mcp_head {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.room_mcp_title_block {
  min-width: 0;
}

.room_mcp_eyebrow {
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

.room_mcp_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

.room_mcp_subtitle {
  max-width: 780px;
}

.room_mcp_state_chips {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
  flex: 0 0 auto;
}

.mcp_subpanel {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.provider_config_panel {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, var(--selected-bg) 3%),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.subpanel_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.subpanel_title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.subpanel_subtitle {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.status_readout {
  align-items: flex-start;
}

.boundary_helper {
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
}

.record_grid,
.grant_summary_grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.record_tile,
.metric_tile {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.record_tile span,
.metric_tile span {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 680;
  line-height: 1.25;
}

.record_tile strong,
.record_tile code,
.metric_tile strong {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 760;
  line-height: 1.35;
  word-break: break-word;
}

.record_tile code {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 620;
}

.metric_tile strong {
  font-size: 1.05rem;
  font-variant-numeric: tabular-nums;
}

.metric_active {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.07);
}

.metric_revoked {
  border-color: rgba(239, 68, 68, 0.26);
  background: rgba(239, 68, 68, 0.07);
}

.metric_expired {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.08);
}

.artifact_preview_box {
  align-items: flex-start;
  min-height: 72px;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  white-space: pre-wrap;
  word-break: break-all;
}

.action_btn {
  flex: 0 0 auto;
  min-width: 124px;
}

.grant_management_panel {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.grant_list {
  display: grid;
  gap: 12px;
}

.grant_card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
  box-shadow:
    0 8px 20px rgba(0, 0, 0, 0.035),
    0 0 0 1px rgba(255, 255, 255, 0.02) inset;
}

.grant_card_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.grant_card_title {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.86rem;
  font-weight: 800;
  line-height: 1.35;
  word-break: break-all;
}

.grant_card_state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.grant_state_active {
  border-color: rgba(34, 197, 94, 0.38);
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.grant_state_revoked {
  border-color: rgba(239, 68, 68, 0.38);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.grant_state_expired {
  border-color: rgba(245, 158, 11, 0.42);
  background: rgba(245, 158, 11, 0.11);
  color: #d97706;
}

.grant_state_unknown {
  border-color: color-mix(in srgb, var(--text-secondary) 28%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  color: var(--text-secondary);
}

.grant_card_body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.grant_meta_row {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.grant_meta_row span {
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 680;
  line-height: 1.25;
}

.grant_meta_row strong {
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 620;
  line-height: 1.45;
  word-break: break-all;
}

.grant_card_actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

input[type="checkbox"] {
  width: 17px;
  height: 17px;
  accent-color: var(--selected);
  cursor: pointer;
  flex: 0 0 auto;
}

@media (max-width: 980px) {
  .record_grid,
  .grant_summary_grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .room_mcp_head {
    flex-direction: column;
  }

  .room_mcp_state_chips {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .record_grid,
  .grant_summary_grid,
  .grant_card_body {
    grid-template-columns: 1fr;
  }

  .room_mcp_panel .toggle_row {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .room_mcp_panel .toggle_text {
    width: 100%;
    min-width: 0;
  }

  .room_mcp_panel .toggle_text strong,
  .room_mcp_panel .toggle_text span {
    display: block;
    max-width: 100%;
    word-break: normal;
    overflow-wrap: break-word;
  }

  .action_btn {
    width: 100%;
    min-width: 0;
  }

  .grant_card_head {
    flex-direction: column;
  }

  .grant_card_actions {
    justify-content: stretch;
  }

  .grant_card_actions button {
    width: 100%;
  }
}
</style>

