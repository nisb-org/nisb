<template>
  <section
    class="markdown_code_block"
    :class="{ is_streaming: !closed }"
  >
    <header class="markdown_code_head">
      <div class="markdown_code_meta">
        <span class="markdown_code_lang mono">{{ languageLabel }}</span>
        <span v-if="!closed" class="markdown_code_state">
          <span class="state_dot" aria-hidden="true"></span>
          {{ t('chat.panel.codeBlock.streaming') }}
        </span>
      </div>

      <button
        class="copy_btn"
        type="button"
        :disabled="!codeText"
        :aria-label="copyAriaLabel"
        @click="copyCode"
      >
        {{ copyLabel }}
      </button>
    </header>

    <pre class="markdown_code_pre" tabindex="0"><code>{{ codeText }}</code></pre>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  block: {
    type: Object,
    required: true,
  },
})

const { t } = useI18n()

const copyState = ref('idle')
let copyTimer = null

const closed = computed(() => !!props.block?.meta?.closed)

const languageLabel = computed(() => {
  const lang = String(props.block?.meta?.lang || '').trim()
  return lang || t('chat.panel.codeBlock.fallbackLanguage')
})

const codeText = computed(() => {
  return String(props.block?.meta?.code_text || props.block?.text || '')
})

const copyLabel = computed(() => {
  if (copyState.value === 'copied') return t('chat.panel.codeBlock.copied')
  if (copyState.value === 'failed') return t('chat.panel.codeBlock.copyFailed')
  return t('chat.panel.codeBlock.copy')
})

const copyAriaLabel = computed(() => {
  return t('chat.panel.codeBlock.copyAria', {
    lang: languageLabel.value,
  })
})

function resetCopyStateSoon() {
  if (copyTimer) window.clearTimeout(copyTimer)

  copyTimer = window.setTimeout(() => {
    copyState.value = 'idle'
    copyTimer = null
  }, 1400)
}

async function writeClipboard(text) {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()

  try {
    const ok = document.execCommand('copy')
    if (!ok) throw new Error('copy_failed')
  } finally {
    document.body.removeChild(textarea)
  }
}

async function copyCode() {
  const text = codeText.value
  if (!text) return

  try {
    await writeClipboard(text)
    copyState.value = 'copied'
  } catch {
    copyState.value = 'failed'
  }

  resetCopyStateSoon()
}

onBeforeUnmount(() => {
  if (copyTimer) window.clearTimeout(copyTimer)
})
</script>

<style scoped>
.markdown_code_block {
  --markdown-code-text-font-size: var(
    --nisb-read-code-font-size,
    var(
      --nisb-reading-code-font-size,
      var(
        --reading-code-font-size,
        var(
          --reader-code-font-size,
          calc(
            var(
              --nisb-read-font-size,
              var(
                --nisb-reading-font-size,
                var(
                  --reading-font-size,
                  var(--reader-font-size, var(--editor-font-size, 0.95rem))
                )
              )
            ) * 0.92
          )
        )
      )
    )
  );
  --markdown-code-ui-font-size: max(0.7rem, calc(var(--markdown-code-text-font-size) * 0.82));
  --markdown-code-small-font-size: max(0.68rem, calc(var(--markdown-code-text-font-size) * 0.78));
  --markdown-code-copy-font-size: max(0.7rem, calc(var(--markdown-code-text-font-size) * 0.8));
  --markdown-code-line-height: var(
    --nisb-read-line-height,
    var(
      --nisb-reading-line-height,
      var(
        --reading-line-height,
        var(--reader-line-height, var(--code-line-height, 1.62))
      )
    )
  );

  min-width: 0;
  margin: 0.9rem 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, transparent)
    );
  color: var(--text-main);
  font-size: var(--markdown-code-text-font-size);
  line-height: var(--markdown-code-line-height);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.markdown_code_block.is_streaming {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--selected) 12%, transparent) inset,
    0 10px 28px color-mix(in srgb, var(--selected) 6%, transparent);
}

.markdown_code_head {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.72rem;
  padding: 0.58rem 0.72rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
}

.markdown_code_meta {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  flex-wrap: wrap;
}

.markdown_code_lang {
  min-width: 0;
  max-width: min(48vw, 360px);
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 64%, transparent);
  color: var(--text-main);
  font-size: var(--markdown-code-ui-font-size);
  font-weight: 780;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.markdown_code_state {
  display: inline-flex;
  align-items: center;
  gap: 0.34rem;
  min-height: 24px;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--selected) 26%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 9%, transparent);
  color: var(--selected);
  font-size: var(--markdown-code-small-font-size);
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.state_dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 12%, transparent);
  animation: pulseDot 1.1s ease-in-out infinite;
}

.copy_btn {
  flex: 0 0 auto;
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: var(--markdown-code-copy-font-size);
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.copy_btn:hover:not(:disabled),
.copy_btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.copy_btn:active:not(:disabled) {
  transform: translateY(1px);
}

.copy_btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.markdown_code_pre {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin: 0;
  padding: 0.86rem 0.95rem;
  overflow-x: auto;
  overflow-y: hidden;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  font-size: var(--markdown-code-text-font-size);
  line-height: var(--markdown-code-line-height);
  tab-size: 2;
  white-space: pre;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 76%, transparent) transparent;
}

.markdown_code_pre:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--selected) 38%, transparent);
  outline-offset: -2px;
}

.markdown_code_pre::-webkit-scrollbar {
  height: 8px;
}

.markdown_code_pre::-webkit-scrollbar-track {
  background: transparent;
}

.markdown_code_pre::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.markdown_code_pre code {
  min-width: max-content;
  display: inline-block;
  color: inherit;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
  font-size: inherit;
  line-height: inherit;
  overflow-wrap: normal;
  word-break: normal;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

@keyframes pulseDot {
  0%,
  100% {
    opacity: 0.56;
    transform: scale(0.9);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 640px) {
  .markdown_code_block {
    margin: 0.78rem 0;
    border-radius: 13px;
  }

  .markdown_code_head {
    align-items: stretch;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.62rem;
  }

  .markdown_code_meta {
    width: 100%;
  }

  .markdown_code_lang {
    max-width: 100%;
  }

  .copy_btn {
    width: 100%;
  }

  .markdown_code_pre {
    padding: 0.74rem 0.78rem;
    font-size: var(--markdown-code-text-font-size);
    line-height: var(--markdown-code-line-height);
  }
}

@media (max-width: 420px) {
  .markdown_code_state,
  .markdown_code_lang {
    width: 100%;
    justify-content: center;
  }
}
</style>
