<template>
  <div class="settings-section settings-performance-section">
    <div class="settings-card is-accent">
      <label class="settings-toggle-card">
        <span class="settings-toggle-check">
          <input
            class="settings-checkbox"
            type="checkbox"
            :checked="local_evidence_sync"
            @change="on_sync_changed"
          />
        </span>

        <span class="settings-toggle-copy">
          <span class="settings-label-text">
            {{ t('settings.performance.sync.label') }}
          </span>
          <span class="muted settings-hint">
            {{ t('settings.performance.sync.hint') }}
          </span>
        </span>
      </label>
    </div>

    <div class="settings-card" :class="{ disabled: !local_evidence_sync }">
      <label class="settings-toggle-card">
        <span class="settings-toggle-check">
          <input
            class="settings-checkbox"
            type="checkbox"
            :checked="local_evidence_auto_select"
            :disabled="!local_evidence_sync"
            @change="on_auto_select_changed"
          />
        </span>

        <span class="settings-toggle-copy">
          <span class="settings-label-text">
            {{ t('settings.performance.autoSelect.label') }}
          </span>
          <span class="muted settings-hint">
            {{ t('settings.performance.autoSelect.hint') }}
          </span>
        </span>
      </label>
    </div>

    <div class="settings-row actions">
      <button class="mini-btn primary settings-footer-btn" type="button" @click="$emit('save')">
        {{ t('settings.common.save') }}
      </button>
      <button class="mini-btn settings-footer-btn" type="button" @click="$emit('reset')">
        {{ t('settings.common.reset') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  local_evidence_sync: { type: Boolean, default: true },
  local_evidence_auto_select: { type: Boolean, default: true }
})

const emit = defineEmits([
  'update:local_evidence_sync',
  'update:local_evidence_auto_select',
  'save',
  'reset'
])

const { t } = useI18n()

function on_sync_changed(e) {
  const next_sync = !!e?.target?.checked
  emit('update:local_evidence_sync', next_sync)
  if (!next_sync) emit('update:local_evidence_auto_select', false)
}

function on_auto_select_changed(e) {
  emit('update:local_evidence_auto_select', !!e?.target?.checked)
}
</script>

<style scoped>
.settings-performance-section {
  min-width: 0;
}

.settings-card.disabled {
  opacity: 0.6;
}

.settings-toggle-card {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  min-width: 0;
  cursor: pointer;
}

.settings-toggle-check {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--selected-bg) 28%, var(--editor-bg));
}

.settings-checkbox {
  margin: 0;
  accent-color: var(--selected);
}

.settings-toggle-copy {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.settings-footer-btn {
  flex: 0 1 150px;
  min-width: 120px;
}

@media (max-width: 720px) {
  .settings-footer-btn {
    flex: 1 1 100%;
  }
}
</style>
