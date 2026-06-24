<template>
  <div class="fed-section">
    <div class="section-head">
      <div class="ttl">{{ t('chat.fedMenu.accept.title') }}</div>
    </div>

    <div class="form">
      <select v-model="inviteForm.peer_id" class="ipt">
        <option value="">{{ t('chat.fedMenu.accept.peerPlaceholder') }}</option>
        <option
          v-for="p in enabledPeers"
          :key="p.peer_id"
          :value="String(p.peer_id || '')"
        >
          {{ p.label || p.peer_id }}
        </option>
      </select>

      <input
        v-model="inviteForm.room_id"
        class="ipt"
        :placeholder="t('chat.fedMenu.accept.roomIdPlaceholder')"
      />
      <input
        v-model="inviteForm.invite_token"
        class="ipt"
        :placeholder="t('chat.fedMenu.accept.inviteTokenPlaceholder')"
      />
      <input
        v-model="inviteForm.remote_user_id"
        class="ipt"
        :placeholder="t('chat.fedMenu.accept.remoteUserPlaceholder')"
      />
      <input
        v-model="inviteForm.remote_label"
        class="ipt"
        :placeholder="t('chat.fedMenu.accept.remoteLabelPlaceholder')"
      />
      <input
        v-model="inviteForm.target_peer_id"
        class="ipt"
        :placeholder="t('chat.fedMenu.accept.targetPeerPlaceholder')"
      />

      <div class="row-actions">
        <button
          class="save"
          type="button"
          @click="$emit('accept-room-invite')"
          :disabled="acceptingInvite"
        >
          {{
            acceptingInvite
              ? t('chat.fedMenu.accept.accepting')
              : t('chat.fedMenu.accept.submit')
          }}
        </button>

        <button
          v-if="canRetryInvite"
          class="mini"
          type="button"
          @click="$emit('retry-last-accept')"
          :disabled="acceptingInvite"
        >
          {{ t('chat.fedMenu.accept.retry') }}
        </button>
      </div>

      <div class="muted invite-note">
        {{ t('chat.fedMenu.accept.notePeer') }}
      </div>
      <div class="muted invite-note">
        {{ t('chat.fedMenu.accept.noteTarget') }}
      </div>

      <div v-if="inviteErr" class="err">{{ inviteErr }}</div>
      <div v-if="inviteHint" class="muted invite-note">{{ inviteHint }}</div>

      <div v-if="inviteOk" class="ok-box">
        <div class="ok">{{ inviteOk }}</div>
        <div class="muted invite-note">
          {{ t('chat.fedMenu.accept.joinedNote') }}
        </div>
        <div class="muted invite-note">
          {{ t('chat.fedMenu.accept.exitNote') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  inviteForm: { type: Object, required: true },
  enabledPeers: { type: Array, default: () => [] },
  acceptingInvite: { type: Boolean, default: false },
  canRetryInvite: { type: Boolean, default: false },
  inviteErr: { type: String, default: '' },
  inviteOk: { type: String, default: '' },
  inviteHint: { type: String, default: '' },
})

defineEmits([
  'accept-room-invite',
  'retry-last-accept',
])

const { t } = useI18n()
</script>
