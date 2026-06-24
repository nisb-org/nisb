<template>
  <div class="settings-section settings-language-section">
    <div class="settings-card is-accent">
      <div class="language-head">
        <div class="settings-main">
          <div class="language-title">{{ t('settings.language.title') }}</div>
          <div class="muted settings-hint">{{ t('settings.language.description') }}</div>
        </div>

        <span class="language-chip mono">
          {{ currentLocale }}
        </span>
      </div>
    </div>

    <div class="language-options" role="radiogroup" :aria-label="t('settings.language.title')">
      <button
        v-for="option in options"
        :key="option.value"
        class="language-option"
        :class="{ active: currentLocale === option.value }"
        type="button"
        role="radio"
        :aria-checked="currentLocale === option.value"
        @click="selectLocale(option.value)"
      >
        <span class="language-option-name">{{ t(option.labelKey) }}</span>
        <span class="language-option-code mono">{{ option.value }}</span>
      </button>
    </div>

    <div class="settings-card language-hint-card">
      <div class="muted settings-hint">{{ t('settings.language.immediate') }}</div>
      <div class="muted settings-hint">{{ t('settings.language.fallbackHint') }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '../../../stores/settings'

const { t } = useI18n()
const settings = useSettingsStore()

const options = [
  { value: 'en', labelKey: 'settings.language.en' },
  { value: 'zh-CN', labelKey: 'settings.language.zhCN' }
]

const currentLocale = computed(() => settings.locale)

function selectLocale(locale) {
  settings.setLocale(locale)
}
</script>

<style scoped>
.settings-language-section {
  min-width: 0;
}

.settings-main {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.language-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.language-title {
  color: var(--text-main, var(--text));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.language-chip {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 62%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.language-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.language-option {
  display: grid;
  gap: 6px;
  min-width: 0;
  min-height: 82px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: var(--text-main, var(--text));
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease,
    box-shadow 0.16s ease;
}

.language-option:hover {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 32%, var(--editor-bg));
}

.language-option:active {
  transform: translateY(1px);
}

.language-option.active {
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 72%, var(--editor-bg));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #fff 4%, transparent);
}

.language-option-name {
  min-width: 0;
  font-size: 0.86rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.language-option-code {
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.35;
}

.language-option.active .language-option-code {
  color: var(--selected);
}

.language-hint-card {
  gap: 7px;
}

@media (max-width: 640px) {
  .language-head {
    display: grid;
  }

  .language-chip {
    justify-self: start;
  }

  .language-options {
    grid-template-columns: 1fr;
  }
}
</style>

