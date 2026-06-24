<template>
  <div class="fed-section">
    <div class="section-head">
      <div class="ttl">{{ t('chat.fedMenu.peers.title') }}</div>
      <div class="row-actions">
        <button class="mini" type="button" @click="$emit('load-peers')" :disabled="loadingPeers">
          {{ loadingPeers ? t('chat.fedMenu.actions.loadingShort') : t('chat.fedMenu.actions.refresh') }}
        </button>
        <button
          class="mini"
          type="button"
          @click="$emit('check-peer-health', inviteForm.peer_id || form.peer_id)"
          :disabled="checkingHealth || !(inviteForm.peer_id || form.peer_id)"
        >
          {{
            checkingHealth
              ? t('chat.fedMenu.peers.checking')
              : t('chat.fedMenu.peers.checkPeer')
          }}
        </button>
      </div>
    </div>

    <div v-if="loadingPeers" class="muted">{{ t('chat.fedMenu.states.loading') }}</div>
    <div v-else-if="peers.length === 0" class="muted">{{ t('chat.fedMenu.states.emptyPeers') }}</div>

    <div v-else class="peer-list">
      <label v-for="p in peers" :key="p.peer_id" class="peer-item">
        <input
          type="checkbox"
          :checked="peerSelected(p.peer_id)"
          :disabled="p.enabled === false"
          @change="$emit('toggle-peer', p.peer_id)"
        />
        <div class="peer-main">
          <span class="peer-id">{{ p.peer_id }}</span>
          <span class="muted" v-if="p.label">· {{ p.label }}</span>
          <span class="muted" v-if="!p.token_present">· {{ t('chat.fedMenu.peers.tokenMissing') }}</span>
          <span class="muted" v-else>· {{ p.token_preview || t('chat.fedMenu.peers.tokenSet') }}</span>
          <span class="muted" v-if="p.enabled === false">· {{ t('chat.fedMenu.peers.disabled') }}</span>
          <span
            v-if="peerHealthMap[p.peer_id]"
            class="health-pill"
            :class="`health-${peerHealthMap[p.peer_id].status || 'unknown'}`"
            :title="peerHealthMap[p.peer_id].message || peerHealthMap[p.peer_id].label"
          >
            {{ peerHealthMap[p.peer_id].label }}
          </span>
        </div>

        <div class="peer-actions">
          <button class="mini peer-use" type="button" @click.stop="$emit('apply-peer-to-form', p)">
            {{ t('chat.fedMenu.peers.use') }}
          </button>
          <button
            class="mini peer-use"
            type="button"
            @click.stop="$emit('check-peer-health', p.peer_id)"
            :disabled="checkingHealth"
          >
            {{ t('chat.fedMenu.peers.check') }}
          </button>
        </div>
      </label>
    </div>

    <div class="sep"></div>

    <div class="section-head">
      <div class="ttl">{{ t('chat.fedMenu.form.title') }}</div>
    </div>

    <div class="form">
      <input v-model="form.peer_id" class="ipt" :placeholder="t('chat.fedMenu.form.peerIdPlaceholder')" />
      <input v-model="form.base_url" class="ipt" :placeholder="t('chat.fedMenu.form.baseUrlPlaceholder')" />
      <input v-model="form.token" class="ipt" :placeholder="t('chat.fedMenu.form.tokenPlaceholder')" />
      <input v-model="form.label" class="ipt" :placeholder="t('chat.fedMenu.form.labelPlaceholder')" />

      <div class="row-actions">
        <button class="save" type="button" @click="$emit('save-peer')" :disabled="saving">
          {{ saving ? t('chat.fedMenu.actions.saving') : t('chat.fedMenu.actions.save') }}
        </button>
        <button
          class="mini"
          type="button"
          @click="$emit('check-peer-health', form.peer_id)"
          :disabled="checkingHealth || !form.peer_id"
        >
          {{
            checkingHealth
              ? t('chat.fedMenu.peers.checking')
              : t('chat.fedMenu.peers.checkThisPeer')
          }}
        </button>
      </div>

      <div class="muted">
        {{ t('chat.fedMenu.peers.editHint') }}
      </div>

      <div v-if="err" class="err">{{ err }}</div>
      <div v-if="ok" class="ok">{{ ok }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  t: { type: Function, required: true },
  loadingPeers: { type: Boolean, default: false },
  peers: { type: Array, default: () => [] },
  checkingHealth: { type: Boolean, default: false },
  peerHealthMap: { type: Object, default: () => ({}) },
  saving: { type: Boolean, default: false },
  err: { type: String, default: '' },
  ok: { type: String, default: '' },
  form: { type: Object, required: true },
  inviteForm: { type: Object, required: true },
  peerSelected: { type: Function, required: true },
})

defineEmits([
  'load-peers',
  'check-peer-health',
  'toggle-peer',
  'apply-peer-to-form',
  'save-peer',
])
</script>
