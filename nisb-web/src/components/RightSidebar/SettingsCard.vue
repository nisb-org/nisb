<template>
  <div class="settings-card">
    <div class="settings-title">{{ t('rightSidebar.settings.topicQa.title') }}</div>

    <label class="settings-toggle">
      <input
        type="checkbox"
        :checked="rightShowLibraryInsights"
        @change="rightShowLibraryInsights = $event.target.checked"
      />
      <span>{{ t('rightSidebar.settings.topicQa.show') }}</span>
    </label>

    <p class="settings-hint">
      {{ t('rightSidebar.settings.topicQa.hint') }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '../../stores/settings'

const { t } = useI18n()
const settings = useSettingsStore()

const rightShowLibraryInsights = computed({
  get: () => settings.rightShowLibraryInsights,
  set: (v) => settings.setRightShowLibraryInsights(!!v)
})
</script>

<style scoped>
.settings-card {
  margin: 0.55rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 44%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.45;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
  overflow: hidden;
}

.settings-title {
  margin: 0 0 0.42rem;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.settings-toggle {
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.54rem;
  margin: 0.24rem 0;
  padding: 0.42rem 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 690;
  line-height: 1.35;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.settings-toggle:hover,
.settings-toggle:focus-within {
  border-color: color-mix(in srgb, var(--selected) 32%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 44%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
}

.settings-toggle:active {
  transform: translateY(1px);
}

.settings-toggle input {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.settings-toggle span {
  min-width: 0;
  flex: 1 1 auto;
  overflow-wrap: break-word;
}

.settings-hint {
  margin: 0.36rem 0 0;
  padding: 0 0.08rem;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.52;
  opacity: 0.86;
  overflow-wrap: break-word;
}

@media (max-width: 420px) {
  .settings-card {
    margin: 0.45rem;
    padding: 0.5rem;
  }

  .settings-toggle {
    align-items: flex-start;
  }

  .settings-toggle input {
    margin-top: 0.1rem;
  }
}
</style>
