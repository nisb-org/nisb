<template>
  <section class="section_card basic_card">
    <div class="basic_head">
      <div class="basic_title_block">
        <div class="basic_eyebrow">
          <span class="basic_dot"></span>
          <span>{{ t('room.settingsBasicCard.eyebrow') }}</span>
        </div>

        <div class="section_title">
          {{ t('room.settingsBasicCard.title') }}
        </div>

        <div class="section_subtitle basic_subtitle">
          {{ t('room.settingsBasicCard.subtitle') }}
        </div>
      </div>

      <div class="basic_chips">
        <span class="basic_chip" :class="{ is_active: room_mcp_provider_enabled }">
          {{ roomMcpProviderChipText }}
        </span>

        <span class="basic_chip" :class="{ is_active: shared_room_config_enabled }">
          {{ sharedAutoReplyChipText }}
        </span>

        <span
          v-if="show_federation_section"
          class="basic_chip"
          :class="{ is_active: can_manage_federation }"
        >
          {{ federationChipText }}
        </span>
      </div>
    </div>

    <div class="basic_panel top_gap">
      <div class="basic_panel_head">
        <div>
          <div class="basic_panel_title">
            {{ t('room.settingsBasicCard.sections.identity.title') }}
          </div>
          <div class="basic_panel_hint">
            {{ t('room.settingsBasicCard.sections.identity.subtitle') }}
          </div>
        </div>
      </div>

      <div class="form_grid top_gap">
        <label class="field field_full">
          <span>{{ t('room.settingsBasicCard.fields.title.label') }}</span>
          <input
            v-model="form.title"
            type="text"
            :placeholder="t('room.settingsBasicCard.fields.title.placeholder')"
          />
        </label>

        <label class="field field_full">
          <span>{{ t('room.settingsBasicCard.fields.summary.label') }}</span>
          <textarea
            v-model="form.summary"
            rows="3"
            :placeholder="t('room.settingsBasicCard.fields.summary.placeholder')"
          ></textarea>
        </label>

        <label class="field field_full">
          <span>{{ t('room.settingsBasicCard.fields.scratchpad.label') }}</span>
          <textarea
            v-model="form.scratchpad"
            rows="5"
            :placeholder="t('room.settingsBasicCard.fields.scratchpad.placeholder')"
          ></textarea>
        </label>
      </div>
    </div>

    <div class="basic_panel capability_panel top_gap">
      <div class="basic_panel_head">
        <div>
          <div class="basic_panel_title">
            {{ t('room.settingsBasicCard.roomMcpSummary.title') }}
          </div>
          <div class="basic_panel_hint">
            {{ t('room.settingsBasicCard.roomMcpSummary.hint') }}
          </div>
        </div>
      </div>

      <div class="summary_grid top_gap">
        <div class="summary_card">
          <div class="summary_label">
            {{ t('room.settingsBasicCard.roomMcpSummary.cards.publishStatus') }}
          </div>
          <div
            class="summary_value"
            :class="{ is_enabled: room_mcp_provider_enabled }"
          >
            {{ roomMcpPublishStatusText }}
          </div>
        </div>

        <div class="summary_card">
          <div class="summary_label">
            {{ t('room.settingsBasicCard.roomMcpSummary.cards.providerName') }}
          </div>
          <div class="summary_value">
            {{ roomMcpProviderNameText }}
          </div>
        </div>

        <div class="summary_card">
          <div class="summary_label">
            {{ t('room.settingsBasicCard.roomMcpSummary.cards.providerSummary') }}
          </div>
          <div class="summary_value summary_multiline">
            {{ roomMcpProviderSummaryText }}
          </div>
        </div>

        <div class="summary_card">
          <div class="summary_label">
            {{ t('room.settingsBasicCard.roomMcpSummary.cards.sharedSemantic') }}
          </div>
          <div class="summary_value summary_multiline">
            {{ sharedReplySemanticText }}
          </div>
        </div>

        <div class="summary_card summary_card_full">
          <div class="summary_label">
            {{ t('room.settingsBasicCard.roomMcpSummary.cards.sharedBoundary') }}
          </div>
          <div class="summary_value summary_multiline">
            {{ sharedBoundarySummaryText }}
          </div>
        </div>
      </div>

      <div
        v-if="room_mcp_provider_enabled && !shared_room_config_enabled"
        class="warning_box warning_box_warn top_gap"
      >
        {{ t('room.settingsBasicCard.roomMcpSummary.notices.providerOnSharedOff') }}
      </div>

      <div
        v-else-if="room_mcp_provider_enabled"
        class="warning_box warning_box_info top_gap"
      >
        {{ t('room.settingsBasicCard.roomMcpSummary.notices.providerOnSharedOn') }}
      </div>
    </div>

    <div
      v-if="show_federation_section"
      class="fed_section"
    >
      <div class="fed_header">
        <div class="fed_title_block">
          <div class="fed_eyebrow">
            {{ t('room.settingsBasicCard.federation.eyebrow') }}
          </div>
          <div class="fed_title">
            {{ t('room.settingsBasicCard.federation.title') }}
          </div>
          <div class="fed_hint">
            {{ t('room.settingsBasicCard.federation.hint') }}
          </div>
        </div>

        <div class="fed_header_chips">
          <span class="fed_state_chip" :class="{ is_active: can_manage_federation }">
            {{ federationManageChipText }}
          </span>
          <span class="fed_state_chip">
            {{ t('room.settingsBasicCard.federation.state.invites', { count: normalized_invites.length }) }}
          </span>
          <span class="fed_state_chip">
            {{ t('room.settingsBasicCard.federation.state.members', { count: normalized_joined_members.length }) }}
          </span>
        </div>
      </div>

      <div
        v-if="can_manage_federation"
        class="fed_panel fed_issue_panel"
      >
        <div class="fed_block_title">
          {{ t('room.settingsBasicCard.federation.issue.title') }}
        </div>

        <div class="fed_issue_grid">
          <label class="field field_full">
            <span>{{ t('room.settingsBasicCard.federation.fields.targetPeer.label') }}</span>
            <select v-model="federation_target_peer_id">
              <option value="">
                {{ t('room.settingsBasicCard.federation.fields.targetPeer.emptyOption') }}
              </option>
              <option
                v-for="peer in normalized_peers"
                :key="peer.peer_id"
                :value="peer.peer_id"
              >
                {{ peer.label || peer.peer_id }} · {{ peer.peer_id }}
              </option>
            </select>
          </label>

          <label class="field field_full">
            <span>{{ t('room.settingsBasicCard.federation.fields.inviteTtl.label') }}</span>
            <select v-model="federation_invite_ttl_seconds">
              <option
                v-for="item in normalized_ttl_options"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </option>
            </select>
          </label>
        </div>

        <div class="fed_actions">
          <button
            class="fed_btn fed_btn_primary"
            type="button"
            :disabled="federation_invite_busy || !federation_target_peer_id"
            @click="handleIssueInvite"
          >
            {{ federation_invite_busy ? t('room.settingsBasicCard.federation.actions.issuing') : t('room.settingsBasicCard.federation.actions.issueInvite') }}
          </button>

          <button
            class="fed_btn"
            type="button"
            :disabled="!canRefreshInvites"
            :title="refreshInvitesDisabledReason || t('room.settingsBasicCard.federation.actions.refreshInvitesTitle')"
            @click="handleRefreshInvites"
          >
            {{ federation_invites_loading ? t('room.settingsBasicCard.federation.actions.refreshing') : t('room.settingsBasicCard.federation.actions.refreshInvites') }}
          </button>
        </div>

        <div class="fed_state_bar">
          <span class="fed_state_chip">
            {{ t('room.settingsBasicCard.federation.state.handler', { state: hasRefreshHandler ? t('room.settingsBasicCard.values.ready') : t('room.settingsBasicCard.values.missing') }) }}
          </span>
          <span class="fed_state_chip">
            {{ t('room.settingsBasicCard.federation.state.loading', { state: federation_invites_loading ? t('room.settingsBasicCard.values.yes') : t('room.settingsBasicCard.values.no') }) }}
          </span>
          <span
            v-if="refreshInvitesDisabledReason"
            class="fed_state_chip fed_state_chip_warn"
          >
            {{ refreshInvitesDisabledReason }}
          </span>
        </div>
      </div>

      <div
        v-if="!can_manage_federation"
        class="warning_box warning_box_warn top_gap"
      >
        {{ t('room.settingsBasicCard.federation.notices.readonly') }}
      </div>

      <div
        v-if="federation_invite_error"
        class="fed_error top_gap"
      >
        {{ federation_invite_error }}
      </div>

      <div
        v-if="federation_invites_error"
        class="fed_error top_gap"
      >
        {{ federation_invites_error }}
      </div>

      <div class="fed_panel">
        <div class="fed_block_title">
          {{ t('room.settingsBasicCard.federation.summary.title') }}
        </div>

        <div class="fed_summary_grid">
          <div
            v-for="item in federation_summary_cards"
            :key="item.key"
            class="fed_summary_card"
          >
            <div class="fed_summary_label">{{ item.label }}</div>
            <div
              class="fed_summary_value"
              :class="item.tone ? `is_${item.tone}` : ''"
            >
              {{ item.value }}
            </div>
          </div>
        </div>

        <div
          v-if="normalized_summary_notes.length"
          class="fed_summary_notes"
        >
          <div
            v-for="note in normalized_summary_notes"
            :key="note"
            class="fed_summary_note"
          >
            {{ note }}
          </div>
        </div>
      </div>

      <div
        v-if="latestInvite"
        class="fed_panel fed_latest"
      >
        <div class="fed_block_title">
          {{ t('room.settingsBasicCard.federation.latestInvite.title') }}
        </div>

        <div class="fed_meta_list">
          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.id') }}</span>
            <div class="fed_meta_value">
              <code class="fed_inline_code">{{ latestInvite.invite_id || emptyValue }}</code>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.status') }}</span>
            <div class="fed_meta_value">
              <strong :class="['fed_status_text', statusClass(latestInvite.status)]">
                {{ inviteStatusText(latestInvite.status) }}
              </strong>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.roomId') }}</span>
            <div class="fed_meta_value">
              <code class="fed_inline_code">{{ latestInvite.room_id || emptyValue }}</code>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.ownerUser') }}</span>
            <div class="fed_meta_value">
              <code class="fed_inline_code">{{ latestInvite.local_owner_user_id || latestInvite.user_id || emptyValue }}</code>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.peer') }}</span>
            <div class="fed_meta_value">
              <strong>{{ latestInvite.target_peer_id || emptyValue }}</strong>
            </div>
          </div>

          <div class="fed_meta_item fed_meta_item_full">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.token') }}</span>
            <div class="fed_meta_value">
              <code class="fed_code_box">{{ latestInvite.invite_token || emptyValue }}</code>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.created') }}</span>
            <div class="fed_meta_value">
              <strong>{{ latestInvite.created_at || emptyValue }}</strong>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.expires') }}</span>
            <div class="fed_meta_value">
              <strong>{{ latestInvite.expires_at || emptyValue }}</strong>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.usedAt') }}</span>
            <div class="fed_meta_value">
              <strong>{{ latestInvite.used_at || emptyValue }}</strong>
            </div>
          </div>

          <div class="fed_meta_item">
            <span class="fed_meta_label">{{ t('room.settingsBasicCard.federation.latestInvite.fields.usedBy') }}</span>
            <div class="fed_meta_value">
              <code class="fed_inline_code">{{ latestInvite.used_by_remote_user_id || emptyValue }}</code>
            </div>
          </div>
        </div>

        <div class="fed_helper_text">
          {{ t('room.settingsBasicCard.federation.latestInvite.helperPrefix') }}
          <code>room_id</code>,
          <code>invite_token</code>,
          <code>owner user_id</code>
          {{ t('room.settingsBasicCard.federation.latestInvite.helperSuffix') }}
        </div>
      </div>

      <div class="fed_panel fed_list">
        <div class="fed_block_title">
          {{ t('room.settingsBasicCard.federation.history.title') }}
        </div>

        <div
          v-if="can_manage_federation"
          class="fed_filter_row"
        >
          <button
            v-for="item in normalized_history_filter_options"
            :key="item.value"
            type="button"
            class="fed_filter_btn"
            :class="{ is_selected: normalized_history_filter === item.value }"
            @click="handleSetHistoryFilter(item.value)"
          >
            {{ item.label }}
          </button>
        </div>

        <div
          v-if="!filtered_invites.length"
          class="fed_empty"
        >
          {{ t('room.settingsBasicCard.federation.history.empty') }}
        </div>

        <div
          v-for="invite in filtered_invites"
          :key="invite.invite_id"
          class="fed_item"
        >
          <div class="fed_item_main">
            <div class="fed_item_row">
              <code class="fed_inline_code fed_item_id">{{ invite.invite_id }}</code>
              <span :class="['fed_badge', statusClass(invite.status)]">
                {{ inviteStatusText(invite.status) }}
              </span>
            </div>

            <div class="fed_item_meta fed_item_meta_grid">
              <span><strong>{{ t('room.settingsBasicCard.federation.history.meta.room') }}:</strong> <code class="fed_inline_code">{{ invite.room_id || emptyValue }}</code></span>
              <span><strong>{{ t('room.settingsBasicCard.federation.history.meta.owner') }}:</strong> <code class="fed_inline_code">{{ invite.local_owner_user_id || emptyValue }}</code></span>
              <span><strong>{{ t('room.settingsBasicCard.federation.history.meta.peer') }}:</strong> {{ invite.target_peer_id || emptyValue }}</span>
              <span><strong>{{ t('room.settingsBasicCard.federation.history.meta.created') }}:</strong> {{ invite.created_at || emptyValue }}</span>
              <span><strong>{{ t('room.settingsBasicCard.federation.history.meta.expires') }}:</strong> {{ invite.expires_at || emptyValue }}</span>
              <span v-if="invite.used_at"><strong>used_at:</strong> {{ invite.used_at }}</span>
              <span v-if="invite.used_by_remote_user_id"><strong>used_by:</strong> <code class="fed_inline_code">{{ invite.used_by_remote_user_id }}</code></span>
              <span class="fed_item_meta_token">
                <strong>{{ t('room.settingsBasicCard.federation.history.meta.token') }}:</strong>
                <code class="fed_code_box fed_code_box_compact">{{ invite.invite_token || invite.token_preview || emptyValue }}</code>
              </span>
            </div>
          </div>

          <div class="fed_item_actions">
            <template v-if="can_manage_federation && invite.is_active">
              <button
                class="fed_btn"
                type="button"
                :disabled="federation_extend_busy_invite_id === invite.invite_id"
                @click="handleExtendInvite(invite.invite_id, 86400)"
              >
                {{ federation_extend_busy_invite_id === invite.invite_id ? t('room.settingsBasicCard.federation.actions.extending') : t('room.settingsBasicCard.federation.actions.extendOneDay') }}
              </button>

              <button
                class="fed_btn"
                type="button"
                :disabled="federation_extend_busy_invite_id === invite.invite_id"
                @click="handleExtendInvite(invite.invite_id, 604800)"
              >
                {{ federation_extend_busy_invite_id === invite.invite_id ? t('room.settingsBasicCard.federation.actions.extending') : t('room.settingsBasicCard.federation.actions.extendSevenDays') }}
              </button>

              <button
                class="fed_btn fed_btn_danger"
                type="button"
                :disabled="federation_revoke_busy_invite_id === invite.invite_id"
                @click="handleRevokeInvite(invite.invite_id)"
              >
                {{ federation_revoke_busy_invite_id === invite.invite_id ? t('room.settingsBasicCard.federation.actions.revoking') : t('room.settingsBasicCard.federation.actions.revoke') }}
              </button>
            </template>
          </div>
        </div>
      </div>

      <div class="fed_panel fed_list">
        <div class="fed_block_title fed_block_title_row">
          <span>{{ t('room.settingsBasicCard.federation.joinedMembers.title') }}</span>

          <button
            v-if="can_manage_federation"
            class="fed_btn"
            type="button"
            :disabled="federation_joined_members_loading"
            @click="handleRefreshJoinedMembers"
          >
            {{ federation_joined_members_loading ? t('room.settingsBasicCard.federation.actions.refreshing') : t('room.settingsBasicCard.federation.actions.refreshMembers') }}
          </button>
        </div>

        <div
          v-if="federation_joined_members_error"
          class="fed_error"
        >
          {{ federation_joined_members_error }}
        </div>

        <div
          v-if="federation_joined_members_loading && !normalized_joined_members.length"
          class="fed_empty"
        >
          {{ t('room.settingsBasicCard.federation.joinedMembers.loading') }}
        </div>

        <div
          v-else-if="!normalized_joined_members.length"
          class="fed_empty"
        >
          {{ t('room.settingsBasicCard.federation.joinedMembers.empty') }}
        </div>

        <div
          v-for="member in normalized_joined_members"
          :key="member.participant_uid"
          class="fed_item"
        >
          <div class="fed_item_main">
            <div class="fed_item_row">
              <code class="fed_inline_code fed_item_id">{{ member.participant_uid }}</code>

              <span :class="['fed_badge', member.is_access_revoked ? 'is_revoked' : 'is_active']">
                {{ memberAccessStatusText(member.access_status) }}
              </span>

              <span class="fed_badge">
                {{ memberTypeText(member.type) }}
              </span>

              <span
                v-if="member.is_owner"
                class="fed_badge"
              >
                owner
              </span>
            </div>

            <div class="fed_item_meta fed_item_meta_grid">
              <span><strong>{{ t('room.settingsBasicCard.federation.joinedMembers.meta.peer') }}:</strong> {{ member.peer_id || emptyValue }}</span>
              <span><strong>remote_user:</strong> <code class="fed_inline_code">{{ member.remote_user_id || emptyValue }}</code></span>
              <span><strong>joined_at:</strong> {{ member.joined_at || emptyValue }}</span>
              <span><strong>last_seen:</strong> {{ member.last_seen || emptyValue }}</span>
            </div>
          </div>

          <div class="fed_item_actions">
            <button
              v-if="can_manage_federation && member.can_revoke_access && !member.is_access_revoked"
              class="fed_btn fed_btn_danger"
              type="button"
              :disabled="federation_revoke_member_busy_uid === member.participant_uid"
              @click="handleRevokeMemberAccess(member.participant_uid)"
            >
              {{ federation_revoke_member_busy_uid === member.participant_uid ? t('room.settingsBasicCard.federation.actions.revoking') : t('room.settingsBasicCard.federation.actions.revokeAccess') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  form: {
    type: Object,
    required: true,
  },
  show_federation_section: {
    type: Boolean,
    default: false,
  },
  can_manage_federation: {
    type: Boolean,
    default: false,
  },
  can_issue_federation_invite: {
    type: Boolean,
    default: false,
  },
  federation_peers: {
    type: Array,
    default: () => [],
  },
  federation_target_peer_id: {
    type: String,
    default: '',
  },
  federation_invite_ttl_seconds: {
    type: Number,
    default: 86400,
  },
  federation_invite_ttl_options: {
    type: Array,
    default: () => [],
  },
  federation_invite_history_filter: {
    type: String,
    default: 'all',
  },
  federation_invite_history_filter_options: {
    type: Array,
    default: () => [],
  },
  federation_invite_busy: {
    type: Boolean,
    default: false,
  },
  federation_invite_error: {
    type: String,
    default: '',
  },
  federation_last_invite: {
    type: Object,
    default: null,
  },
  federation_invites: {
    type: Array,
    default: () => [],
  },
  federation_invites_loading: {
    type: Boolean,
    default: false,
  },
  federation_invites_error: {
    type: String,
    default: '',
  },
  federation_revoke_busy_invite_id: {
    type: String,
    default: '',
  },
  federation_extend_busy_invite_id: {
    type: String,
    default: '',
  },
  federation_joined_members: {
    type: Array,
    default: () => [],
  },
  federation_joined_members_loading: {
    type: Boolean,
    default: false,
  },
  federation_joined_members_error: {
    type: String,
    default: '',
  },
  federation_revoke_member_busy_uid: {
    type: String,
    default: '',
  },
  federation_summary_counts: {
    type: Object,
    default: () => ({
      active_invites: 0,
      used_invites: 0,
      revoked_invites: 0,
      expired_invites: 0,
      joined_federated_members: 0,
      revoked_federated_members: 0,
    }),
  },
  federation_summary_notes: {
    type: Array,
    default: () => [],
  },
  issue_federation_room_invite: {
    type: Function,
    default: null,
  },
  refresh_federation_room_invites: {
    type: Function,
    default: null,
  },
  refresh_federation_joined_members: {
    type: Function,
    default: null,
  },
  revoke_federation_room_invite: {
    type: Function,
    default: null,
  },
  revoke_federated_member_access: {
    type: Function,
    default: null,
  },
  set_federation_invite_history_filter: {
    type: Function,
    default: null,
  },
  extend_federation_room_invite: {
    type: Function,
    default: null,
  },
})

const emit = defineEmits([
  'update:federation_target_peer_id',
  'update:federation_invite_ttl_seconds',
])

const { t } = useI18n()

const room_mcp_provider_enabled = computed(() => !!props.form?.room_mcp_provider_enabled)
const shared_room_config_enabled = computed(() => !!props.form?.shared_room_config_enabled)

const emptyValue = computed(() => t('room.settingsBasicCard.values.emptyDash'))

const roomMcpProviderChipText = computed(() => {
  return room_mcp_provider_enabled.value
    ? t('room.settingsBasicCard.chips.providerOn')
    : t('room.settingsBasicCard.chips.providerOff')
})

const sharedAutoReplyChipText = computed(() => {
  return shared_room_config_enabled.value
    ? t('room.settingsBasicCard.chips.sharedOn')
    : t('room.settingsBasicCard.chips.sharedOff')
})

const federationChipText = computed(() => {
  return props.can_manage_federation
    ? t('room.settingsBasicCard.chips.federationManageable')
    : t('room.settingsBasicCard.chips.federationReadonly')
})

const federationManageChipText = computed(() => {
  return props.can_manage_federation
    ? t('room.settingsBasicCard.federation.state.ownerManage')
    : t('room.settingsBasicCard.federation.state.readonly')
})

const roomMcpProviderNameText = computed(() => {
  const value = String(props.form?.room_mcp_provider_name || '').trim()
  return value || t('room.settingsBasicCard.roomMcpSummary.values.providerNameUnset')
})

const roomMcpProviderSummaryText = computed(() => {
  const value = String(props.form?.room_mcp_provider_summary || '').trim()
  if (value) return value

  return t('room.settingsBasicCard.roomMcpSummary.values.providerSummaryUnset')
})

const roomMcpPublishStatusText = computed(() => {
  if (!room_mcp_provider_enabled.value) {
    return t('room.settingsBasicCard.roomMcpSummary.values.notPublished')
  }
  return t('room.settingsBasicCard.roomMcpSummary.values.published')
})

const sharedReplySemanticText = computed(() => {
  const form = props.form || {}
  const replyMode = String(form.reply_mode || 'manual').trim() || 'manual'
  const defaultRoleId = String(form.default_reply_role_id || '').trim()
  const activeRoles = Array.isArray(form.active_roles) ? form.active_roles.filter(Boolean) : []
  const sharedSupervisorEnabled = !!(
    form.shared_supervisor_enabled ??
    form.supervisor_enabled
  )

  const chunks = [
    `reply_mode=${replyMode}`,
    `active_roles=${activeRoles.length}`,
    `shared_supervisor=${sharedSupervisorEnabled ? 'on' : 'off'}`,
  ]

  if (defaultRoleId) {
    chunks.push(`default_reply_role_id=${defaultRoleId}`)
  }

  return chunks.join('；')
})

const sharedBoundarySummaryText = computed(() => {
  const form = props.form || {}
  const sharedEnabled = !!form.shared_room_config_enabled
  const workspaceId = String(form.workspace_id || '').trim()
  const focusRoot = String(form.focus_root || '').trim()

  const base = sharedEnabled
    ? t('room.settingsBasicCard.roomMcpSummary.values.sharedBoundaryEnabled')
    : t('room.settingsBasicCard.roomMcpSummary.values.sharedBoundaryDisabled')

  const workspaceText = workspaceId
    ? `workspace=${workspaceId}`
    : t('room.settingsBasicCard.roomMcpSummary.values.workspaceUnbound')

  const focusText = focusRoot
    ? `focus_root=${focusRoot}`
    : t('room.settingsBasicCard.roomMcpSummary.values.focusRootUnset')

  return t('room.settingsBasicCard.roomMcpSummary.values.boundaryTemplate', {
    base,
    workspace: workspaceText,
    focus: focusText,
  })
})

const normalized_peers = computed(() => (
  Array.isArray(props.federation_peers) ? props.federation_peers : []
))

const normalized_invites = computed(() => (
  Array.isArray(props.federation_invites) ? props.federation_invites : []
))

const normalized_joined_members = computed(() => {
  const rows = Array.isArray(props.federation_joined_members)
    ? props.federation_joined_members
    : []

  return rows
    .map((item) => ({
      participant_uid: String(item?.participant_uid || item?.uid || '').trim(),
      uid: String(item?.uid || item?.participant_uid || '').trim(),
      type: String(item?.type || 'local').trim().toLowerCase() === 'federated' ? 'federated' : 'local',
      peer_id: String(item?.peer_id || '').trim(),
      remote_user_id: String(item?.remote_user_id || '').trim(),
      joined_at: String(item?.joined_at || '').trim(),
      last_seen: String(item?.last_seen || '').trim(),
      access_status: String(item?.access_status || 'active').trim().toLowerCase() === 'revoked' ? 'revoked' : 'active',
      is_owner: !!item?.is_owner,
      can_revoke_access: !!item?.can_revoke_access,
      is_access_revoked: !!item?.is_access_revoked
        || String(item?.access_status || '').trim().toLowerCase() === 'revoked',
    }))
    .filter((item) => !!item.participant_uid)
})

const normalized_summary_counts = computed(() => {
  const row = props.federation_summary_counts && typeof props.federation_summary_counts === 'object'
    ? props.federation_summary_counts
    : {}

  function num(v) {
    const n = Number(v)
    return Number.isFinite(n) && n >= 0 ? n : 0
  }

  return {
    active_invites: num(row.active_invites),
    used_invites: num(row.used_invites),
    revoked_invites: num(row.revoked_invites),
    expired_invites: num(row.expired_invites),
    joined_federated_members: num(row.joined_federated_members),
    revoked_federated_members: num(row.revoked_federated_members),
  }
})

const federation_summary_cards = computed(() => {
  const c = normalized_summary_counts.value
  return [
    { key: 'active_invites', label: t('room.settingsBasicCard.federation.summary.cards.activeInvites'), value: c.active_invites, tone: 'active' },
    { key: 'used_invites', label: t('room.settingsBasicCard.federation.summary.cards.usedInvites'), value: c.used_invites, tone: 'used' },
    { key: 'revoked_invites', label: t('room.settingsBasicCard.federation.summary.cards.revokedInvites'), value: c.revoked_invites, tone: 'revoked' },
    { key: 'expired_invites', label: t('room.settingsBasicCard.federation.summary.cards.expiredInvites'), value: c.expired_invites, tone: 'expired' },
    { key: 'joined_federated_members', label: t('room.settingsBasicCard.federation.summary.cards.joinedMembers'), value: c.joined_federated_members, tone: '' },
    { key: 'revoked_federated_members', label: t('room.settingsBasicCard.federation.summary.cards.revokedMembers'), value: c.revoked_federated_members, tone: 'revoked' },
  ]
})

const normalized_summary_notes = computed(() => (
  Array.isArray(props.federation_summary_notes)
    ? props.federation_summary_notes
      .map((item) => String(item || '').trim())
      .filter(Boolean)
    : []
))

const normalized_ttl_options = computed(() => {
  const rows = Array.isArray(props.federation_invite_ttl_options)
    ? props.federation_invite_ttl_options
    : []

  const normalized = rows
    .map((item) => ({
      label: String(item?.label || '').trim(),
      value: Number(item?.value || 0),
    }))
    .filter((item) => item.label && Number.isFinite(item.value) && item.value > 0)

  if (normalized.length) return normalized

  return [
    { label: t('room.settingsBasicCard.federation.ttl.oneDay'), value: 86400 },
    { label: t('room.settingsBasicCard.federation.ttl.sevenDays'), value: 604800 },
  ]
})

const normalized_history_filter_options = computed(() => {
  const rows = Array.isArray(props.federation_invite_history_filter_options)
    ? props.federation_invite_history_filter_options
    : []

  const normalized = rows
    .map((item) => ({
      label: String(item?.label || '').trim(),
      value: String(item?.value || '').trim().toLowerCase(),
    }))
    .filter((item) => item.label && item.value)

  if (normalized.length) return normalized

  return [
    { label: t('room.settingsBasicCard.federation.history.filters.all'), value: 'all' },
    { label: t('room.settingsBasicCard.federation.history.filters.active'), value: 'active' },
    { label: t('room.settingsBasicCard.federation.history.filters.used'), value: 'used' },
    { label: t('room.settingsBasicCard.federation.history.filters.revoked'), value: 'revoked' },
    { label: t('room.settingsBasicCard.federation.history.filters.expired'), value: 'expired' },
  ]
})

const normalized_history_filter = computed(() => {
  const s = String(props.federation_invite_history_filter || 'all').trim().toLowerCase()
  if (['active', 'used', 'revoked', 'expired'].includes(s)) return s
  return 'all'
})

const filtered_invites = computed(() => {
  const rows = normalized_invites.value
  const filter = normalized_history_filter.value
  if (filter === 'all') return rows
  return rows.filter((invite) => String(invite?.status || '').trim().toLowerCase() === filter)
})

const latestInvite = computed(() => {
  if (props.federation_last_invite && typeof props.federation_last_invite === 'object') {
    return props.federation_last_invite
  }
  return normalized_invites.value[0] || null
})

const federation_target_peer_id = computed({
  get() {
    return String(props.federation_target_peer_id || '').trim()
  },
  set(value) {
    emit('update:federation_target_peer_id', String(value || '').trim())
  },
})

const federation_invite_ttl_seconds = computed({
  get() {
    const n = Number(props.federation_invite_ttl_seconds || 86400)
    return Number.isFinite(n) && n > 0 ? n : 86400
  },
  set(value) {
    const n = Number(value || 86400)
    emit(
      'update:federation_invite_ttl_seconds',
      Number.isFinite(n) && n > 0 ? n : 86400
    )
  },
})

const hasRefreshHandler = computed(() => typeof props.refresh_federation_room_invites === 'function')

const refreshInvitesDisabledReason = computed(() => {
  if (!props.can_manage_federation) return t('room.settingsBasicCard.federation.disabledReasons.ownerOnly')
  if (!hasRefreshHandler.value) return t('room.settingsBasicCard.federation.disabledReasons.refreshHandlerMissing')
  if (props.federation_invites_loading) return t('room.settingsBasicCard.federation.disabledReasons.inviteListLoading')
  return ''
})

const canRefreshInvites = computed(() => !refreshInvitesDisabledReason.value)

function inviteStatusText(status = '') {
  const s = String(status || '').trim().toLowerCase()
  if (s === 'used') return 'used'
  if (s === 'expired') return 'expired'
  if (s === 'revoked') return 'revoked'
  return 'active'
}

function statusClass(status = '') {
  const s = String(status || '').trim().toLowerCase()
  if (s === 'used') return 'is_used'
  if (s === 'expired') return 'is_expired'
  if (s === 'revoked') return 'is_revoked'
  return 'is_active'
}

function memberTypeText(type = '') {
  return String(type || '').trim().toLowerCase() === 'federated'
    ? 'federated'
    : 'local'
}

function memberAccessStatusText(status = '') {
  return String(status || '').trim().toLowerCase() === 'revoked'
    ? 'revoked'
    : 'active'
}

async function handleIssueInvite() {
  if (!props.can_manage_federation) return
  if (typeof props.issue_federation_room_invite !== 'function') return
  await props.issue_federation_room_invite(federation_target_peer_id.value)
}

async function handleRefreshInvites() {
  if (!props.can_manage_federation) return
  if (typeof props.refresh_federation_room_invites !== 'function') return
  await props.refresh_federation_room_invites()
}

async function handleRefreshJoinedMembers() {
  if (!props.can_manage_federation) return
  if (typeof props.refresh_federation_joined_members !== 'function') return
  await props.refresh_federation_joined_members()
}

function handleSetHistoryFilter(value = 'all') {
  if (!props.can_manage_federation) return
  if (typeof props.set_federation_invite_history_filter !== 'function') return
  props.set_federation_invite_history_filter(value)
}

async function handleExtendInvite(invite_id = '', extend_seconds = 0) {
  if (!props.can_manage_federation) return
  if (typeof props.extend_federation_room_invite !== 'function') return
  await props.extend_federation_room_invite(invite_id, extend_seconds)
}

async function handleRevokeInvite(invite_id = '') {
  if (!props.can_manage_federation) return
  if (typeof props.revoke_federation_room_invite !== 'function') return
  await props.revoke_federation_room_invite(invite_id)
}

async function handleRevokeMemberAccess(participant_uid = '') {
  if (!props.can_manage_federation) return
  if (typeof props.revoke_federated_member_access !== 'function') return
  await props.revoke_federated_member_access(participant_uid)
}
</script>

<style scoped>
.basic_card {
  position: relative;
}

.basic_head,
.fed_header,
.basic_panel_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.basic_title_block,
.fed_title_block {
  min-width: 0;
}

.basic_eyebrow,
.fed_eyebrow {
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

.basic_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

.basic_subtitle {
  max-width: 760px;
}

.basic_chips,
.fed_header_chips,
.fed_state_bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
}

.basic_chip,
.fed_state_chip,
.fed_badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 23px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
}

.basic_chip.is_active,
.fed_state_chip.is_active {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
}

.fed_state_chip_warn {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.09);
  color: #d97706;
}

.basic_panel,
.fed_panel {
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
}

.capability_panel {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, var(--selected-bg) 3%),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.basic_panel_title,
.fed_title,
.fed_block_title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.basic_panel_hint,
.fed_hint {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.summary_grid,
.fed_summary_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.fed_summary_grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary_card,
.fed_summary_card {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: color-mix(in srgb, var(--sidebar-bg) 82%, transparent);
}

.summary_card_full {
  grid-column: 1 / -1;
}

.summary_label,
.fed_summary_label,
.fed_meta_label {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 680;
  line-height: 1.3;
}

.summary_value {
  margin-top: 6px;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 640;
  line-height: 1.55;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.summary_value.is_enabled {
  color: #16a34a;
}

.summary_multiline {
  white-space: pre-wrap;
}

.fed_section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.fed_header {
  margin-bottom: 12px;
}

.fed_issue_panel {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
}

.fed_issue_grid {
  display: grid;
  gap: 12px;
  margin-top: 10px;
}

.fed_actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.fed_state_bar {
  justify-content: flex-start;
  margin-top: 10px;
}

.fed_btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  color: var(--text-main);
  font-size: 0.78rem;
  font-weight: 720;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.fed_btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 54%, var(--editor-bg));
}

.fed_btn:active:not(:disabled) {
  transform: translateY(1px);
}

.fed_btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.fed_btn_primary {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected) 14%, var(--editor-bg));
  color: var(--selected);
}

.fed_btn_danger {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.07);
}

.fed_error {
  padding: 10px 11px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.8rem;
  line-height: 1.5;
}

.fed_panel + .fed_panel {
  margin-top: 12px;
}

.fed_block_title {
  margin-bottom: 10px;
}

.fed_block_title_row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.fed_summary_value {
  margin-top: 6px;
  color: var(--text-main);
  font-size: 1.1rem;
  line-height: 1.1;
  font-weight: 820;
  font-variant-numeric: tabular-nums;
}

.fed_summary_notes {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.fed_summary_note,
.fed_helper_text,
.fed_empty {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
}

.fed_meta_list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  min-width: 0;
}

.fed_meta_item {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fed_meta_item_full {
  grid-column: 1 / -1;
}

.fed_meta_value {
  min-width: 0;
}

.fed_meta_value strong,
.fed_meta_value code {
  display: block;
  min-width: 0;
}

.fed_status_text {
  font-weight: 760;
}

.fed_inline_code,
.fed_code_box {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.fed_inline_code {
  padding: 0;
  background: transparent;
}

.fed_code_box {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 80%, transparent);
  white-space: pre-wrap;
}

.fed_code_box_compact {
  margin-top: 4px;
}

.fed_helper_text {
  margin-top: 10px;
}

.fed_helper_text code {
  font-family: var(--font-mono);
}

.fed_list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fed_filter_row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fed_filter_btn {
  min-height: 27px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
}

.fed_filter_btn.is_selected {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 68%, transparent);
  color: var(--selected);
}

.fed_item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.fed_item_main {
  min-width: 0;
  flex: 1;
}

.fed_item_row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.fed_item_id {
  max-width: 100%;
}

.fed_item_meta_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
}

.fed_item_meta span {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.5;
}

.fed_item_meta strong {
  color: var(--text-main);
  font-weight: 760;
}

.fed_item_meta_token {
  grid-column: 1 / -1;
}

.fed_item_actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.fed_badge.is_active,
.is_active {
  color: #16a34a;
}

.fed_badge.is_used,
.is_used {
  color: #2563eb;
}

.fed_badge.is_expired,
.is_expired {
  color: #d97706;
}

.fed_badge.is_revoked,
.is_revoked {
  color: #ef4444;
}

input[type="checkbox"] {
  width: 17px;
  height: 17px;
  accent-color: var(--selected);
  cursor: pointer;
  flex: 0 0 auto;
}

@media (max-width: 860px) {
  .basic_head,
  .fed_header {
    flex-direction: column;
  }

  .basic_chips,
  .fed_header_chips {
    justify-content: flex-start;
  }

  .fed_summary_grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .summary_grid,
  .fed_meta_list,
  .fed_item_meta_grid,
  .fed_summary_grid {
    grid-template-columns: 1fr;
  }

  .fed_item {
    flex-direction: column;
  }

  .fed_item_actions {
    width: 100%;
    justify-content: stretch;
  }

  .fed_item_actions .fed_btn {
    flex: 1 1 auto;
  }
}
</style>
