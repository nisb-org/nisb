<template>
  <div class="stream_markdown_renderer">
    <template v-if="has_stream_state">
      <template v-if="has_visible_blocks">
        <template v-for="block in rendered_blocks" :key="`${block.id}_${stream_parse_version}`">
          <MarkdownCodeBlock
            v-if="block.type === 'code'"
            :block="block"
          />

          <div
            v-else
            class="stream_markdown_block"
            :class="[
              `stream_markdown_block_${block.type}`,
              block.is_tail ? 'stream_markdown_block_tail' : 'stream_markdown_block_sealed',
            ]"
            v-html="block.html"
          ></div>
        </template>
      </template>

      <div
        v-else-if="show_placeholder"
        class="stream_markdown_placeholder"
        aria-live="polite"
      >
        <span class="placeholder_dot" aria-hidden="true"></span>
        <span>{{ t('chat.panel.markdown.thinking') }}</span>
      </div>

      <div
        v-else
        class="stream_markdown_block stream_markdown_block_fallback"
        v-html="fallback_html"
      ></div>
    </template>

    <div
      v-else-if="show_placeholder"
      class="stream_markdown_placeholder"
      aria-live="polite"
    >
      <span class="placeholder_dot" aria-hidden="true"></span>
      <span>{{ t('chat.panel.markdown.thinking') }}</span>
    </div>

    <div
      v-else
      class="stream_markdown_block stream_markdown_block_fallback"
      v-html="fallback_html"
    ></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownCodeBlock from './blocks/MarkdownCodeBlock.vue'
import { render_markdown, render_markdown_block } from '../../../composables/editor/chat_panel/chat_panel_markdown'
import { normalize_display_text } from '../../../composables/editor/chat_panel/use_chat_panel_message_writer'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const { t } = useI18n()

function pick_first_text(...values) {
  for (const value of values) {
    const s = String(value || '')
    if (s.trim()) return s
  }
  return ''
}

function escape_html(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalize_markdown_block(block) {
  if (!block || typeof block !== 'object') return block
  if (block.type === 'code') return block

  return {
    ...block,
    text: normalize_display_text(block.text),
    content: normalize_display_text(block.content),
    raw: normalize_display_text(block.raw),
    source: normalize_display_text(block.source),
  }
}

const source_text = computed(() => {
  const msg = props.message || {}
  return normalize_display_text(
    pick_first_text(
      msg?.response,
      msg?.content,
      msg?.text,
      msg?.answer,
      msg?.final_text,
      msg?.assistant_response
    )
  )
})

const stream_state = computed(() => {
  const state = props.message?.stream_markdown
  return state && typeof state === 'object' ? state : null
})

const has_stream_state = computed(() => !!stream_state.value)

const stream_parse_version = computed(() => {
  return Number(stream_state.value?.parse_version || 0)
})

const render_blocks = computed(() => {
  if (!stream_state.value) return []

  const sealed = Array.isArray(stream_state.value.sealed_blocks)
    ? stream_state.value.sealed_blocks
    : []

  const tail = stream_state.value.active_tail_block
    ? [stream_state.value.active_tail_block]
    : []

  return [...sealed, ...tail]
})

function has_visible_html(html) {
  const text = String(html || '').replace(/<[^>]+>/g, '').trim()
  if (text) return true
  return /<(img|pre|code|table|ul|ol|blockquote|hr)(\s|>)/i.test(String(html || ''))
}

const rendered_blocks = computed(() => {
  return render_blocks.value
    .map((block, index) => {
      const normalizedBlock = normalize_markdown_block(block)
      const html = normalizedBlock?.type === 'code'
        ? ''
        : render_markdown_block(normalizedBlock)

      return {
        ...normalizedBlock,
        id: normalizedBlock?.id || `stream_block_${index + 1}`,
        html: String(html || ''),
      }
    })
    .filter((block) => {
      if (block.type === 'code') return true
      return has_visible_html(block.html)
    })
})

const has_visible_blocks = computed(() => rendered_blocks.value.length > 0)

const markdown_fallback_html = computed(() => {
  const text = source_text.value
  if (!text) return ''
  return String(render_markdown(text) || '')
})

const plain_text_fallback_html = computed(() => {
  const text = source_text.value
  if (!text) return ''
  return `<pre class="stream_markdown_plain_fallback">${escape_html(text)}</pre>`
})

const fallback_html = computed(() => {
  if (has_visible_html(markdown_fallback_html.value)) {
    return markdown_fallback_html.value
  }
  return plain_text_fallback_html.value
})

const show_placeholder = computed(() => {
  return !!props.message?.pending && !source_text.value.trim() && rendered_blocks.value.length === 0
})
</script>

<style scoped>
.stream_markdown_renderer {
  --stream-read-font-size: var(
    --nisb-read-font-size,
    var(
      --nisb-reading-font-size,
      var(
        --reading-font-size,
        var(--reader-font-size, var(--editor-font-size, 0.95rem))
      )
    )
  );
  --stream-read-line-height: var(
    --nisb-read-line-height,
    var(
      --nisb-reading-line-height,
      var(
        --reading-line-height,
        var(--reader-line-height, var(--text-line-height, 1.68))
      )
    )
  );
  --stream-read-code-font-size: var(
    --nisb-read-code-font-size,
    var(
      --nisb-reading-code-font-size,
      var(
        --reading-code-font-size,
        var(--reader-code-font-size, 0.9em)
      )
    )
  );

  min-width: 0;
  max-width: 100%;
  color: var(--text-main);
  font-family: var(--font-main);
  font-size: var(--stream-read-font-size);
  line-height: var(--stream-read-line-height);
  opacity: var(--nisb-read-text-opacity, var(--nisb-reading-text-opacity, var(--reading-text-opacity, 1)));
  overflow-wrap: break-word;
  word-break: normal;
}

.stream_markdown_block {
  min-width: 0;
  max-width: 100%;
  color: inherit;
  font: inherit;
  line-height: inherit;
  overflow-wrap: break-word;
}

.stream_markdown_block_tail {
  overflow-wrap: anywhere;
}

.stream_markdown_block :deep(*) {
  max-width: 100%;
  box-sizing: border-box;
}

.stream_markdown_block :deep(p),
.stream_markdown_block :deep(ul),
.stream_markdown_block :deep(ol),
.stream_markdown_block :deep(blockquote),
.stream_markdown_block :deep(table),
.stream_markdown_block :deep(pre) {
  margin-top: 0;
}

.stream_markdown_block :deep(p) {
  margin-bottom: var(--text-paragraph-gap, 0.86rem);
  color: var(--text-main);
  font-size: inherit;
  line-height: inherit;
}

.stream_markdown_block :deep(ul),
.stream_markdown_block :deep(ol) {
  margin-bottom: var(--text-paragraph-gap, 0.86rem);
  padding-left: 1.35rem;
  font-size: inherit;
  line-height: inherit;
}

.stream_markdown_block :deep(li) {
  margin: 0.22rem 0;
  padding-left: 0.08rem;
  font-size: inherit;
  line-height: inherit;
}

.stream_markdown_block :deep(li::marker) {
  color: color-mix(in srgb, var(--selected) 72%, var(--text-secondary));
}

.stream_markdown_block :deep(h1),
.stream_markdown_block :deep(h2),
.stream_markdown_block :deep(h3),
.stream_markdown_block :deep(h4),
.stream_markdown_block :deep(h5),
.stream_markdown_block :deep(h6) {
  color: var(--text-main);
  letter-spacing: -0.01em;
  line-height: 1.24;
  overflow-wrap: break-word;
}

.stream_markdown_block :deep(h1) {
  margin: 1.95rem 0 0.82rem;
  font-size: 1.46em;
  font-weight: 840;
}

.stream_markdown_block :deep(h2) {
  margin: 1.72rem 0 0.72rem;
  font-size: 1.31em;
  font-weight: 820;
}

.stream_markdown_block :deep(h3) {
  margin: 1.42rem 0 0.62rem;
  font-size: 1.18em;
  font-weight: 790;
}

.stream_markdown_block :deep(h4) {
  margin: 1.22rem 0 0.52rem;
  font-size: 1.08em;
  font-weight: 760;
}

.stream_markdown_block :deep(h5),
.stream_markdown_block :deep(h6) {
  color: var(--text-secondary);
  font-size: 1em;
  font-weight: 760;
}

.stream_markdown_block :deep(strong) {
  color: var(--text-main);
  font-weight: 760;
}

.stream_markdown_block :deep(em) {
  color: color-mix(in srgb, var(--text-main) 88%, var(--text-secondary));
}

.stream_markdown_block :deep(a) {
  color: var(--selected);
  text-decoration: none;
  border-bottom: 1px solid color-mix(in srgb, var(--selected) 30%, transparent);
}

.stream_markdown_block :deep(a:hover) {
  border-bottom-color: var(--selected);
  background: color-mix(in srgb, var(--selected) 7%, transparent);
}

.stream_markdown_block :deep(code) {
  max-width: 100%;
  padding: 0.16rem 0.38rem;
  border: 1px solid color-mix(in srgb, var(--selected) 12%, transparent);
  border-radius: 7px;
  background: var(--code-inline-bg-light);
  color: color-mix(in srgb, var(--text-main) 92%, var(--selected));
  font-family: var(--font-mono);
  font-size: 0.88em;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.stream_markdown_block :deep(pre),
.stream_markdown_block :deep(.stream_markdown_plain_fallback) {
  max-width: 100%;
  margin: 0.9rem 0 1.05rem;
  padding: 1rem 1.08rem;
  border: 1px solid var(--line-soft);
  border-radius: 13px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    var(--code-block-bg-light);
  color: var(--text-main);
  overflow: auto;
  position: relative;
  font-family: var(--font-mono);
  font-size: var(--stream-read-code-font-size);
  line-height: var(--code-line-height, 1.62);
  white-space: pre-wrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 74%, transparent) transparent;
}

.stream_markdown_block :deep(pre code) {
  display: block;
  padding: 0;
  border: none;
  border-radius: 0;
  background: none;
  color: inherit;
  font-size: inherit;
  line-height: inherit;
  white-space: pre;
  overflow-wrap: normal;
}

.stream_markdown_block :deep(blockquote) {
  margin: 0.86rem 0 1rem;
  padding: 0.7rem 0.86rem 0.72rem 0.96rem;
  border: 1px solid var(--line-soft);
  border-left: 3px solid var(--blockquote-border);
  border-radius: 12px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--selected) 5%, transparent),
      color-mix(in srgb, var(--surface-card) 62%, transparent)
    );
  color: var(--text-secondary);
  font-size: inherit;
  line-height: inherit;
}

.stream_markdown_block :deep(blockquote p) {
  color: inherit;
}

.stream_markdown_block :deep(table) {
  width: 100%;
  max-width: 100%;
  margin: 0.95rem 0 1.1rem;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--line-soft);
  border-radius: 13px;
  background: color-mix(in srgb, var(--surface-card) 80%, transparent);
  font-size: 0.94em;
  line-height: 1.5;
}

.stream_markdown_block :deep(th),
.stream_markdown_block :deep(td) {
  border: none;
  border-bottom: 1px solid var(--line-soft);
  border-right: 1px solid var(--line-soft);
  padding: 0.68rem 0.78rem;
  vertical-align: top;
  overflow-wrap: break-word;
}

.stream_markdown_block :deep(th:last-child),
.stream_markdown_block :deep(td:last-child) {
  border-right: none;
}

.stream_markdown_block :deep(tr:last-child td) {
  border-bottom: none;
}

.stream_markdown_block :deep(th) {
  background: var(--table-header-bg-light);
  color: var(--text-main);
  font-weight: 760;
}

.stream_markdown_block :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 0.95rem 0;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
}

.stream_markdown_placeholder {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 1.6em;
  color: var(--text-secondary);
  font-family: var(--font-main);
  font-size: var(--stream-read-font-size);
  line-height: var(--stream-read-line-height);
  opacity: 0.86;
}

.placeholder_dot {
  width: 0.48em;
  height: 0.48em;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--selected) 28%, transparent);
  animation: streamPlaceholderPulse 1.18s ease-in-out infinite;
}

:deep(.markdown_code_block),
:deep(.markdown-code-block),
:deep(.code-block),
:deep(.stream-code-block) {
  font-size: var(--stream-read-code-font-size);
  line-height: var(--code-line-height, 1.62);
}

:deep(.markdown_code_block pre),
:deep(.markdown-code-block pre),
:deep(.code-block pre),
:deep(.stream-code-block pre) {
  max-width: 100%;
  overflow-x: auto;
  font-size: inherit;
  line-height: inherit;
}

@keyframes streamPlaceholderPulse {
  0%,
  100% {
    opacity: 0.45;
    transform: scale(0.82);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--selected) 0%, transparent);
  }

  50% {
    opacity: 1;
    transform: scale(1);
    box-shadow: 0 0 0 0.42rem color-mix(in srgb, var(--selected) 14%, transparent);
  }
}

@media (max-width: 768px) {
  .stream_markdown_block :deep(pre),
  .stream_markdown_block :deep(.stream_markdown_plain_fallback) {
    padding: 0.88rem;
    border-radius: 12px;
  }

  .stream_markdown_block :deep(table) {
    display: block;
    overflow-x: auto;
    border-collapse: separate;
    scrollbar-width: thin;
  }

  .stream_markdown_block :deep(th),
  .stream_markdown_block :deep(td) {
    min-width: 8rem;
    padding: 0.58rem 0.66rem;
  }
}
</style>
