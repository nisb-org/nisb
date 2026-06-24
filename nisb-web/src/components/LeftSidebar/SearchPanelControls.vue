<template>
  <div class="search-controls">
    <div class="controls-row">
      <div class="module-toggle-group">
        <button
          v-for="item in moduleItems"
          :key="item.key"
          type="button"
          class="module-chip"
          :class="[item.key, { active: !!modelValue?.[item.key], inactive: !modelValue?.[item.key] }]"
          :disabled="searching"
          @click="toggleModule(item.key)"
        >
          <span class="chip-label">{{ item.label }}</span>
          <span class="chip-count">{{ safeCount(item.key) }}</span>
        </button>
      </div>

      <div class="preset-actions">
        <button type="button" class="preset-btn" :disabled="searching" @click="$emit('select-all')">
          {{ t('sidebar.search.controls.presets.all') }}
        </button>
        <button type="button" class="preset-btn" :disabled="searching" @click="$emit('select-workspace')">
          {{ t('sidebar.search.controls.presets.workspace') }}
        </button>
        <button type="button" class="preset-btn subtle" :disabled="searching" @click="$emit('reset-defaults')">
          {{ t('sidebar.search.controls.presets.reset') }}
        </button>
      </div>
    </div>

    <div class="controls-hint">
      {{ t('sidebar.search.controls.hint') }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({
      chat: true,
      dirs: true,
      files: true,
      library: true
    })
  },
  counts: {
    type: Object,
    default: () => ({
      chat: 0,
      dirs: 0,
      files: 0,
      library: 0
    })
  },
  searching: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'select-all', 'select-workspace', 'reset-defaults'])
const { t } = useI18n()

const moduleItems = computed(() => [
  { key: 'chat', label: t('sidebar.search.controls.modules.chat') },
  { key: 'dirs', label: t('sidebar.search.controls.modules.dirs') },
  { key: 'files', label: t('sidebar.search.controls.modules.files') },
  { key: 'library', label: t('sidebar.search.controls.modules.library') }
])

function safeCount(key) {
  const value = Number(props?.counts?.[key] || 0)
  return Number.isFinite(value) ? value : 0
}

function toggleModule(key) {
  const next = {
    chat: !!props.modelValue?.chat,
    dirs: !!props.modelValue?.dirs,
    files: !!props.modelValue?.files,
    library: !!props.modelValue?.library
  }
  next[key] = !next[key]
  emit('update:modelValue', next)
}
</script>

<style scoped>
.search-controls {
  padding: 0.72rem 1rem 0.68rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.016) 0%, rgba(255, 255, 255, 0.008) 100%);
}

.controls-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
}

.module-toggle-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
  flex: 1;
}

.module-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.34rem;
  padding: 0.28rem 0.54rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.16s ease;
  font-size: 0.74rem;
  line-height: 1;
}

.module-chip:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.12);
  color: var(--text-main);
}

.module-chip.active {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.045);
}

.module-chip.inactive {
  opacity: 0.48;
}

.module-chip.chat.active {
  border-color: rgba(59, 130, 246, 0.16);
}

.module-chip.dirs.active {
  border-color: rgba(245, 158, 11, 0.17);
}

.module-chip.files.active {
  border-color: rgba(34, 197, 94, 0.16);
}

.module-chip.library.active {
  border-color: rgba(168, 85, 247, 0.17);
}

.chip-label {
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.chip-count {
  min-width: 1rem;
  padding: 0.02rem 0.24rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.055);
  font-size: 0.66rem;
  text-align: center;
  opacity: 0.9;
  font-feature-settings: 'tnum';
}

.preset-actions {
  display: flex;
  align-items: center;
  gap: 0.34rem;
  flex-wrap: wrap;
}

.preset-btn {
  padding: 0.28rem 0.52rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.018);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.16s ease;
}

.preset-btn:hover:not(:disabled) {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.12);
}

.preset-btn.subtle {
  opacity: 0.82;
}

.controls-hint {
  margin-top: 0.5rem;
  font-size: 0.68rem;
  color: var(--text-secondary);
  opacity: 0.68;
  letter-spacing: 0.01em;
}

.module-chip:disabled,
.preset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

