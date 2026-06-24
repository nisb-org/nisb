<template>
  <div
    class="attach-wrapper"
    :data-tooltip="t('chat.attachFromFilesAction.button.tooltip')"
  >
    <button
      type="button"
      class="attach-btn"
      :disabled="props.disabled"
      :aria-label="t('chat.attachFromFilesAction.button.ariaLabel')"
      @click="openFileDialog"
    >
      <span class="attach-icon-shell" aria-hidden="true">
        <span class="attach-icon">📎</span>
      </span>
    </button>

    <input
      ref="fileInput"
      type="file"
      class="hidden-input"
      multiple
      @change="handleFiles"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['insert'])
const { t } = useI18n()
const fileInput = ref(null)

function openFileDialog() {
  if (props.disabled || !fileInput.value) return
  fileInput.value.value = ''
  fileInput.value.click()
}

function escapeMarkdownLabel(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/\[/g, '\\[')
    .replace(/\]/g, '\\]')
    .replace(/\r?\n/g, ' ')
    .trim()
}

function escapeMarkdownDestination(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/\)/g, '\\)')
    .replace(/\r?\n/g, ' ')
    .trim()
}

function buildPlaceholderMarkdown(file) {
  const name = escapeMarkdownLabel(file?.name)
  if (!name) return ''

  const pendingText = escapeMarkdownDestination(
    t('chat.attachFromFilesAction.placeholder.pendingUpload')
  )

  return `[${name}](${pendingText})\n`
}

function handleFiles(event) {
  const files = Array.from(event?.target?.files || [])
  if (!files.length) return

  const content = files
    .map((file) => buildPlaceholderMarkdown(file))
    .filter(Boolean)
    .join('')

  if (content) {
    emit('insert', content)
  }

  if (fileInput.value) {
    fileInput.value.value = ''
  }
}
</script>

<style scoped>
.attach-wrapper {
  position: relative;
  flex: 0 0 auto;
  min-width: 0;
}

.hidden-input {
  display: none;
}

.attach-btn {
  width: 36px;
  height: 36px;
  min-width: 36px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 56%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.92rem;
  line-height: 1;
  white-space: nowrap;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 6px 18px rgba(15, 23, 42, 0.05);
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.attach-btn:hover:not(:disabled),
.attach-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 13%, transparent), transparent 58%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 56%, transparent),
      color-mix(in srgb, var(--editor-bg) 50%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 10px 24px rgba(15, 23, 42, 0.09),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  outline: none;
}

.attach-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.attach-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.attach-icon-shell {
  width: 22px;
  height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--selected) 16%, transparent), transparent 58%),
    color-mix(in srgb, var(--selected-bg) 32%, transparent);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 4px 12px rgba(15, 23, 42, 0.05);
}

.attach-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transform: translateY(-0.5px);
}

.attach-wrapper::after {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 9px);
  z-index: 2147483000;
  width: max-content;
  max-width: min(280px, 80vw);
  box-sizing: border-box;
  padding: 0.44rem 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 11px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 46%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 12px 30px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  content: attr(data-tooltip);
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.4;
  overflow-wrap: anywhere;
  pointer-events: none;
  text-align: center;
  transform: translateX(-50%) translateY(3px);
  opacity: 0;
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.attach-wrapper::before {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 4px);
  z-index: 2147483000;
  width: 8px;
  height: 8px;
  border-right: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 88%, transparent);
  content: '';
  pointer-events: none;
  transform: translateX(-50%) translateY(3px) rotate(45deg);
  opacity: 0;
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.attach-wrapper:hover::after,
.attach-wrapper:focus-within::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.attach-wrapper:hover::before,
.attach-wrapper:focus-within::before {
  opacity: 1;
  transform: translateX(-50%) translateY(0) rotate(45deg);
}

@media (max-width: 420px) {
  .attach-wrapper::after {
    left: 0;
    right: auto;
    max-width: min(260px, calc(100vw - 24px));
    text-align: left;
    transform: translateY(3px);
  }

  .attach-wrapper::before {
    left: 14px;
    transform: translateY(3px) rotate(45deg);
  }

  .attach-wrapper:hover::after,
  .attach-wrapper:focus-within::after {
    transform: translateY(0);
  }

  .attach-wrapper:hover::before,
  .attach-wrapper:focus-within::before {
    transform: translateY(0) rotate(45deg);
  }
}
</style>
