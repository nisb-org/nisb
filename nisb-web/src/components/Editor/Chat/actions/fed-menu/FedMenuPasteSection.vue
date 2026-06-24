<template>
  <div class="fed-section">
    <div class="section-head">
      <div class="ttl">{{ t('chat.fedMenu.paste.title') }}</div>
      <div class="row-actions">
        <button
          class="mini"
          type="button"
          @click="$emit('paste-from-clipboard')"
          :disabled="importingPaste"
        >
          {{
            importingPaste
              ? t('chat.fedMenu.paste.pasting')
              : t('chat.fedMenu.paste.pasteClipboard')
          }}
        </button>
        <button
          class="mini"
          type="button"
          @click="$emit('import-federation-info')"
          :disabled="importingPaste"
        >
          {{
            importingPaste
              ? t('chat.fedMenu.paste.importing')
              : t('chat.fedMenu.paste.import')
          }}
        </button>
      </div>
    </div>

    <div class="form">
      <textarea
        class="ipt ta"
        :value="pasteText"
        :placeholder="t('chat.fedMenu.paste.textareaPlaceholder')"
        @input="$emit('update:pasteText', $event.target.value)"
      ></textarea>

      <div class="section-row">
        <div class="muted">
          {{ t('chat.fedMenu.paste.ownerHint') }}
        </div>
        <button
          class="mini"
          type="button"
          @click="$emit('copy-federation-info')"
          :disabled="copyingFederationInfo"
          :title="t('chat.fedMenu.paste.copyMyInfoTitle')"
        >
          {{
            copyingFederationInfo
              ? t('chat.fedMenu.paste.copying')
              : t('chat.fedMenu.paste.copyMyInfo')
          }}
        </button>
      </div>

      <div class="muted">
        {{ t('chat.fedMenu.paste.recommend') }}
      </div>

      <div v-if="pasteErr" class="err">{{ pasteErr }}</div>

      <div v-if="pasteOk" class="ok-box">
        <div class="ok">{{ pasteOk }}</div>
        <div v-if="pasteHint" class="muted invite-note">{{ pasteHint }}</div>
      </div>
    </div>

    <div v-if="importedInviteEntries.length > 0" class="draft-list">
      <div class="section-head">
        <div class="ttl">{{ t('chat.fedMenu.paste.draftsTitle') }}</div>
      </div>

      <div
        v-for="item in importedInviteEntries"
        :key="item._draft_key"
        class="draft-item"
      >
        <div class="draft-main">
          <div class="draft-title">
            <span class="peer-id">{{ item.peer_id || t('chat.fedMenu.paste.unknownPeer') }}</span>
            <span class="muted" v-if="item.remote_label">· {{ item.remote_label }}</span>
          </div>
          <div class="muted">
            <span v-if="item.room_id">
              {{ t('chat.fedMenu.paste.roomPrefix') }} {{ item.room_id }}
            </span>
            <span v-if="item.invite_token">
              · {{ t('chat.fedMenu.paste.invitePrefix') }} {{ maskInviteToken(item.invite_token) }}
            </span>
          </div>
        </div>
        <div class="draft-actions">
          <button class="mini" type="button" @click="$emit('apply-imported-invite', item)">
            {{ t('chat.fedMenu.paste.use') }}
          </button>
          <button
            class="mini danger-lite"
            type="button"
            :aria-label="t('chat.fedMenu.paste.remove')"
            :title="t('chat.fedMenu.paste.remove')"
            @click="$emit('remove-imported-invite', item._draft_key)"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  pasteText: { type: String, default: '' },
  pasteErr: { type: String, default: '' },
  pasteOk: { type: String, default: '' },
  pasteHint: { type: String, default: '' },
  importingPaste: { type: Boolean, default: false },
  copyingFederationInfo: { type: Boolean, default: false },
  importedInviteEntries: { type: Array, default: () => [] },
  maskInviteToken: { type: Function, required: true },
})

defineEmits([
  'update:pasteText',
  'paste-from-clipboard',
  'import-federation-info',
  'copy-federation-info',
  'apply-imported-invite',
  'remove-imported-invite',
])

const { t } = useI18n()
</script>
