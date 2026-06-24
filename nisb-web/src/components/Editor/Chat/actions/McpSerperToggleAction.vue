<template>
  <button
    type="button"
    class="action-btn"
    :class="{ 'toggle-on': enabled }"
    :aria-pressed="enabled ? 'true' : 'false'"
    :aria-label="t('chat.mcpSerperToggleAction.button.ariaLabel')"
    :data-tooltip="t('chat.mcpSerperToggleAction.button.tooltip')"
    @click="toggle"
  >
    <span class="action-icon" aria-hidden="true">🔍</span>
    <span class="action-text">
      {{ t('chat.mcpSerperToggleAction.button.label', { state: enabledStateLabel }) }}
    </span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useChatConfigStore } from '../../../../stores/chatConfig'

const { t } = useI18n()
const store = useChatConfigStore()

if (typeof store.hydrate === 'function') {
  store.hydrate()
}

const { mcp } = storeToRefs(store)

const enabled = computed(() => !!mcp.value.serperEnabled)
const enabledStateLabel = computed(() => (
  enabled.value
    ? t('chat.mcpSerperToggleAction.state.on')
    : t('chat.mcpSerperToggleAction.state.off')
))

function toggle() {
  store.setSerperEnabled(!enabled.value)
}
</script>

<style scoped>
.action-btn {
  position: relative;
  min-height: 34px;
  max-width: 100%;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.38rem;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.action-btn:hover,
.action-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.action-btn:active {
  transform: translateY(1px);
}

.action-btn.toggle-on {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  color: var(--selected);
  font-weight: 820;
}

.action-icon {
  width: 19px;
  height: 19px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 20%, var(--line));
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--selected) 12%, transparent), transparent 56%),
    color-mix(in srgb, var(--selected-bg) 28%, transparent);
  line-height: 1;
}

.action-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-btn::after {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 8px);
  z-index: 2147483000;
  max-width: min(280px, 80vw);
  box-sizing: border-box;
  padding: 0.42rem 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 26px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  content: attr(data-tooltip);
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1.4;
  overflow-wrap: anywhere;
  pointer-events: none;
  text-align: center;
  transform: translateX(-50%) translateY(2px);
  opacity: 0;
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.action-btn:hover::after,
.action-btn:focus-visible::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

@media (max-width: 420px) {
  .action-btn {
    min-width: 0;
  }

  .action-btn::after {
    left: 0;
    right: auto;
    transform: translateY(2px);
    text-align: left;
  }

  .action-btn:hover::after,
  .action-btn:focus-visible::after {
    transform: translateY(0);
  }
}
</style>
