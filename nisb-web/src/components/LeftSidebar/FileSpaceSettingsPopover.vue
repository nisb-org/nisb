<template>
  <div class="fs-settings" @click.stop>
    <button class="fs-gear-btn" :title="t('files.settings.title')" @click.stop="toggle">
      ⚙
    </button>

    <div v-if="open" class="fs-popover">
      <div class="fs-popover-title">{{ t('files.settings.title') }}</div>

      <label class="fs-option">
        <input
          type="checkbox"
          :checked="settings.hover_expand_enabled.value"
          @change="onToggleHoverExpand"
        />
        <span>{{ t('files.settings.hoverExpand') }}</span>
      </label>

      <div class="fs-hint">
        {{ t('files.settings.hoverExpandHint') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { use_file_space_settings } from '../../stores/file_space_settings'

const { t } = useI18n()
const settings = use_file_space_settings()
const open = ref(false)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function onToggleHoverExpand(e) {
  settings.set_hover_expand_enabled(!!e.target.checked)
}

function onDocClick() {
  if (open.value) close()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.fs-settings {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.fs-gear-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.fs-gear-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.fs-popover {
  position: absolute;
  top: 28px;
  right: 0;
  min-width: 220px;
  background: var(--sidebar-bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.18);
  padding: 0.6rem 0.65rem;
  z-index: 20000;
}

.fs-popover-title {
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--text-main);
  margin-bottom: 0.45rem;
}

.fs-option {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.fs-hint {
  margin-top: 0.45rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  opacity: 0.85;
  line-height: 1.35;
}
</style>
