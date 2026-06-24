<template>
  <div class="display-mode-container" ref="noteContainer">
    <textarea
      ref="taRef"
      :value="content"
      class="hidden-textarea"
      @input="onInput"
      @keydown.ctrl.e.prevent="emit('toggle-edit-mode')"
    />

    <div
      class="preview-content"
      ref="previewEl"
      v-html="renderedHtml"
      @mouseup="handleMouseUp"
      @click="handleClick"
      @paste="onPaste"
      @dragover.prevent
      @drop.prevent="onDrop"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useImageLoader } from '../../composables/useImageLoader'
import useMCP from '../../composables/useMCP'

const props = defineProps({
  content: { type: String, required: true },
  renderedHtml: { type: String, required: true },
  onContentChange: { type: Function, required: true },
  onOpenLightbox: { type: Function, default: null },
  notePath: { type: String, default: '' }
})

const emit = defineEmits(['update:content', 'toggle-edit-mode', 'focus-hidden-input'])

const { t } = useI18n()
const noteContainer = ref(null)
const previewEl = ref(null)
const taRef = ref(null)

const { callTool } = useMCP()
const { enhanceMarkdownDom } = useImageLoader()

function onInput(e) {
  emit('update:content', e.target.value)
  props.onContentChange()
}

function handleMouseUp() {
  setTimeout(() => {
    const selection = window.getSelection()
    const selectedText = selection?.toString() || ''
    if (!selectedText.trim()) emit('focus-hidden-input')
  }, 0)
}

function handleClick(e) {
  let target = e.target
  if (!target) return

  const btn = target.closest?.('button[data-action="plain-load-more"]')
  if (btn) {
    e.preventDefault()
    e.stopPropagation()
    window.dispatchEvent(new CustomEvent('nisb-plain-load-more'))
  }
}

let __alive = true
let __enhanceTimer = null
let __enhanceIdleId = null
let __enhanceSeq = 0

function _cancelEnhanceJobs() {
  if (__enhanceTimer) clearTimeout(__enhanceTimer)
  __enhanceTimer = null

  if (__enhanceIdleId && 'cancelIdleCallback' in window) {
    try {
      window.cancelIdleCallback(__enhanceIdleId)
    } catch {}
  }
  __enhanceIdleId = null
}

function _isPlainPreHtml(html) {
  const s = String(html || '')
  return s.includes('class="plain-pre"') || s.includes("class='plain-pre'")
}

function _needsEnhance(html) {
  const s = String(html || '')
  if (!s.trim()) return false
  if (s.includes('<img')) return true
  if (s.includes('<a')) return true
  if (s.includes('<pre')) return true
  return false
}

async function enhance(seq) {
  await nextTick()
  if (!__alive) return
  if (seq !== __enhanceSeq) return

  const root = previewEl.value || noteContainer.value
  if (!root) return

  try {
    await enhanceMarkdownDom({
      rootEl: root,
      onOpenLightbox: props.onOpenLightbox || null,
      run_id: seq,
      eager_images: 6
    })
  } catch {}
}

function scheduleEnhance() {
  _cancelEnhanceJobs()

  const html = String(props.renderedHtml || '')
  if (_isPlainPreHtml(html)) return
  if (!_needsEnhance(html)) return

  const seq = ++__enhanceSeq

  __enhanceTimer = setTimeout(() => {
    const run = () => enhance(seq)
    if ('requestIdleCallback' in window) {
      __enhanceIdleId = window.requestIdleCallback(run, { timeout: 800 })
    } else {
      setTimeout(run, 0)
    }
  }, 120)
}

watch(
  () => props.renderedHtml,
  () => {
    scheduleEnhance()
  }
)

onMounted(() => {
  scheduleEnhance()
})

onUnmounted(() => {
  __alive = false
  _cancelEnhanceJobs()
})

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(String(fr.result || ''))
    fr.onerror = reject
    fr.readAsDataURL(file)
  })
}

async function insertImageFile(file) {
  if (!file) return

  const note_path = String(props.notePath || '').trim()
  if (!note_path) {
    toast(t('note.messages.imagePasteNeedsSavedNote'), 'info')
    return
  }

  const name = String(file.name || '')
  const dataUrl = await readFileAsDataURL(file)

  const res = await callTool('nisb_feed_image_stage_upload', {
    note_path,
    image_base64: dataUrl,
    filename: name,
    alt: 'image'
  })
  if (!res || res.success === false) throw new Error(res?.message || 'Upload image failed.')

  const md = String(res.markdown || '').trim()
  if (!md) return

  const cur = String(props.content || '')
  const next = cur.trimEnd() + '\n\n' + md + '\n'
  emit('update:content', next)
  props.onContentChange()
  toast(t('note.messages.imageInserted'), 'success')
}

async function onPaste(e) {
  if (e?.defaultPrevented) return

  try {
    const items = Array.from(e?.clipboardData?.items || [])
    const imgItem = items.find((it) => it.kind === 'file' && String(it.type || '').startsWith('image/'))
    if (!imgItem) return

    e.preventDefault()

    const file = imgItem.getAsFile()
    await insertImageFile(file)
  } catch (err) {
    toast(err?.message || t('note.messages.pasteImageFailed'), 'error')
  }
}

async function onDrop(e) {
  try {
    const files = Array.from(e?.dataTransfer?.files || [])
    const img = files.find((f) => String(f.type || '').startsWith('image/'))
    if (!img) return
    await insertImageFile(img)
  } catch (err) {
    toast(err?.message || t('note.messages.dropImageFailed'), 'error')
  }
}
</script>

<style scoped>
.display-mode-container {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-width: 0;
  min-height: 0;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
}

.hidden-textarea {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 1px;
  height: 1px;
}

.display-mode-container .preview-content {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  margin: 0;
  padding: clamp(1.25rem, 2.5vw, 2.35rem) clamp(1.25rem, 4vw, 3rem) 3rem;

  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 3%, transparent), transparent 30%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
  color: var(--text-main);

  line-height: var(--text-line-height);
  font-size: var(--editor-font-size);
  cursor: text;
  word-wrap: break-word;
  overflow-wrap: break-word;
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;

  scrollbar-gutter: stable;
  content-visibility: auto;
  contain-intrinsic-size: 1000px 2000px;
}

.display-mode-container .preview-content > :first-child {
  margin-top: 0;
}

.display-mode-container .preview-content :deep(h1),
.display-mode-container .preview-content :deep(h2),
.display-mode-container .preview-content :deep(h3),
.display-mode-container .preview-content :deep(h4),
.display-mode-container .preview-content :deep(h5),
.display-mode-container .preview-content :deep(h6) {
  color: var(--text-main);
  letter-spacing: -0.015em;
  scroll-margin-top: 1rem;
}

.display-mode-container .preview-content :deep(p),
.display-mode-container .preview-content :deep(li),
.display-mode-container .preview-content :deep(blockquote) {
  overflow-wrap: break-word;
}

.display-mode-container .preview-content :deep(a) {
  color: var(--selected);
  text-decoration-color: color-mix(in srgb, var(--selected) 38%, transparent);
  text-underline-offset: 0.18em;
}

.display-mode-container .preview-content :deep(blockquote) {
  margin-inline: 0;
  padding: 0.65rem 0.9rem;
  border-left: 3px solid color-mix(in srgb, var(--selected) 46%, var(--line));
  border-radius: 0 13px 13px 0;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 66%, transparent)
    );
  color: var(--text-secondary);
}

.display-mode-container .preview-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 15px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  box-shadow:
    0 16px 36px rgba(0, 0, 0, 0.12),
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
}

.display-mode-container .preview-content :deep(code) {
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 7px;
  padding: 0.08rem 0.28rem;
  background: color-mix(in srgb, var(--sidebar-bg) 68%, transparent);
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.display-mode-container .preview-content :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
  box-sizing: border-box;
  margin: 1rem 0;
  padding: 0.95rem 1rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-x;
  overscroll-behavior-x: contain;
}

.display-mode-container .preview-content :deep(pre > code) {
  display: block;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  white-space: pre;
}

.display-mode-container .preview-content :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  -webkit-overflow-scrolling: touch;
}

.display-mode-container .preview-content :deep(th),
.display-mode-container .preview-content :deep(td) {
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  padding: 0.45rem 0.6rem;
}

.display-mode-container .preview-content :deep(hr) {
  border: 0;
  border-top: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  margin: 1.4rem 0;
}

@media (max-width: 720px) {
  .display-mode-container .preview-content {
    padding: 1rem 1rem 2.25rem;
  }
}
</style>
