<template>
  <div
    v-if="visible"
    ref="menuEl"
    class="zen-context-menu"
    :class="menu_classes"
    :style="{
      top: clamped_y + 'px',
      left: clamped_x + 'px',
      position: 'fixed'
    }"
    role="menu"
    @click.stop
    @contextmenu.prevent.stop
    @keydown.esc.stop.prevent="emit('close')"
  >
    <template v-if="context_menu.targetType === 'library'">
      <button type="button" class="menu-item" role="menuitem" @click="emit_action('library_rename')">
        {{ t('library.left.contextMenu.rename') }}
      </button>
      <button type="button" class="menu-item" role="menuitem" @click="emit_action('library_info')">
        {{ t('library.left.contextMenu.info') }}
      </button>

      <div class="menu-separator"></div>

      <button type="button" class="menu-item danger" role="menuitem" @click="emit_action('library_delete')">
        {{ t('library.left.contextMenu.delete') }}
      </button>
    </template>

    <template v-else-if="context_menu.targetType === 'create'">
      <button type="button" class="menu-item primary-ish" role="menuitem" @click="emit_action('create_file_in_dir')">
        {{ t('files.contextMenu.createFile') }}
      </button>
      <button type="button" class="menu-item primary-ish" role="menuitem" @click="emit_action('create_dir_in_dir')">
        {{ t('files.contextMenu.createFolder') }}
      </button>
    </template>

    <template v-else-if="context_menu.targetType === 'file'">
      <template v-if="context_menu.targetFileType === 'directory'">
        <button type="button" class="menu-item primary-ish" role="menuitem" @click="emit_action('create_file_in_dir')">
          {{ t('files.contextMenu.createFileHere') }}
        </button>
        <button type="button" class="menu-item primary-ish" role="menuitem" @click="emit_action('create_dir_in_dir')">
          {{ t('files.contextMenu.createFolderHere') }}
        </button>

        <template v-if="visible_extensions.length">
          <div class="menu-separator"></div>

          <template v-for="ext in visible_extensions" :key="ext.id">
            <button type="button" class="menu-item extension" role="menuitem" @click="emit_extension_click(ext)">
              {{ ext.title }}
            </button>
          </template>
        </template>

        <div class="menu-separator"></div>

        <button type="button" class="menu-item capability" role="menuitem" @click="emit_action('send_dir_to_library')">
          {{ t('files.contextMenu.sendDirectoryToLibrary') }}
        </button>
        <button type="button" class="menu-item capability" role="menuitem" @click="emit_action('batch_notes_to_brain')">
          {{ t('files.contextMenu.directoryToBrain') }}
        </button>

        <div class="menu-separator"></div>

        <button type="button" class="menu-item danger" role="menuitem" @click="emit_action('delete_recursive')">
          {{ t('files.contextMenu.deleteDirectoryRecursive') }}
        </button>

        <div class="menu-separator"></div>
      </template>

      <button type="button" class="menu-item favorite" role="menuitem" @click="emit_action('toggle_favorite')">
        {{ t('files.contextMenu.toggleFavorite') }}
      </button>

      <div class="favorite-highlight-panel" role="group" :aria-label="t('files.highlight.title')">
        <div class="highlight-panel-head">
          <span>{{ t('files.highlight.title') }}</span>
          <span v-if="current_highlight_color_label" class="highlight-current">
            {{ current_highlight_color_label }}
          </span>
        </div>

        <div class="highlight-color-row">
          <button
            v-for="color in favorite_highlight_colors"
            :key="color.key"
            type="button"
            class="highlight-color-btn"
            :class="{ active: current_highlight_color === color.key }"
            :style="favorite_highlight_style(color.key)"
            :title="highlight_color_title(color.key)"
            :aria-label="highlight_color_title(color.key)"
            @click="emit_favorite_highlight(color.key)"
          >
            <span></span>
          </button>
        </div>

        <button
          type="button"
          class="highlight-clear-btn"
          @click="emit_favorite_highlight_clear"
        >
          {{ t('files.highlight.clear') }}
        </button>
      </div>

      <button type="button" class="menu-item" role="menuitem" @click="emit_action('copy_internal_link')">
        {{ t('files.contextMenu.copyInternalLink') }}
      </button>

      <template v-if="context_menu.targetFileType === 'file'">
        <div class="menu-separator"></div>

        <button
          v-if="is_binary_file(context_menu.targetName)"
          type="button"
          class="menu-item preview"
          role="menuitem"
          @click="emit_action('open_binary_new_tab')"
        >
          {{ t('files.contextMenu.openBinaryNewTab') }}
        </button>

        <button type="button" class="menu-item capability" role="menuitem" @click="emit_action('send_file_to_library')">
          {{ t('files.contextMenu.sendFileToLibrary') }}
        </button>

        <button
          v-if="is_txt_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('txt_to_structured_md')"
        >
          {{ t('files.contextMenu.txtToStructuredMd') }}
        </button>

        <button
          v-if="is_epub_file(context_menu.targetName)"
          type="button"
          class="menu-item preview"
          role="menuitem"
          @click="emit_action('epub_read_new_tab')"
        >
          {{ t('files.contextMenu.epubReadNewTab') }}
        </button>

        <button
          v-if="is_pdf_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('pdf_to_note')"
        >
          {{ t('files.contextMenu.pdfToNote') }}
        </button>

        <button
          v-if="is_epub_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('epub_to_note')"
        >
          {{ t('files.contextMenu.epubToNote') }}
        </button>

        <button
          v-if="is_doc_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('doc_to_note')"
        >
          {{ t('files.contextMenu.docToNote') }}
        </button>

        <button
          v-if="is_docx_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('docx_to_note')"
        >
          {{ t('files.contextMenu.docxToNote') }}
        </button>

        <button
          v-if="is_ppt_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('ppt_to_note')"
        >
          {{ t('files.contextMenu.pptToNote') }}
        </button>

        <button
          v-if="is_pptx_file(context_menu.targetName)"
          type="button"
          class="menu-item convert"
          role="menuitem"
          @click="emit_action('pptx_to_note')"
        >
          {{ t('files.contextMenu.pptxToNote') }}
        </button>

        <button
          v-if="false"
          type="button"
          class="menu-item capability"
          role="menuitem"
          @click="emit_action('note_to_brain')"
        >
          {{ t('files.contextMenu.noteToBrain') }}
        </button>

        <button
          v-if="is_image_file(context_menu.targetName)"
          type="button"
          class="menu-item preview"
          role="menuitem"
          @click="emit_action('copy_image_reference')"
        >
          {{ t('files.contextMenu.copyImageReference') }}
        </button>

        <div class="menu-separator"></div>
      </template>

      <button type="button" class="menu-item" role="menuitem" @click="emit_action('rename')">
        {{ t('files.contextMenu.rename') }}
      </button>
      <button type="button" class="menu-item" role="menuitem" @click="emit_action('move')">
        {{ t('files.contextMenu.moveTo') }}
      </button>
      <button type="button" class="menu-item danger" role="menuitem" @click="emit_action('delete')">
        {{ t('files.contextMenu.delete') }}
      </button>
    </template>

    <template v-else-if="context_menu.targetType === 'rss'">
      <button type="button" class="menu-item" role="menuitem" @click="emit_action('rss_rename')">
        {{ t('rss.left.contextMenu.rename') }}
      </button>
      <button type="button" class="menu-item" role="menuitem" @click="emit_action('rss_edit_tags')">
        {{ t('rss.left.contextMenu.editTags') }}
      </button>

      <div class="menu-separator"></div>

      <button type="button" class="menu-item danger" role="menuitem" @click="emit_action('rss_delete')">
        {{ t('rss.left.contextMenu.delete') }}
      </button>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  FAVORITE_HIGHLIGHT_COLORS,
  favorite_highlight_style,
  normalize_favorite_highlight_color
} from '../../composables/left_sidebar/file_browser/favorite_highlight_colors'

const props = defineProps({
  visible: { type: Boolean, default: false },
  context_menu: { type: Object, required: true },
  visible_extensions: { type: Array, default: () => [] },
  is_binary_file: { type: Function, required: true },
  is_pdf_file: { type: Function, required: true },
  is_epub_file: { type: Function, required: true },
  is_image_file: { type: Function, required: true }
})

const emit = defineEmits(['action', 'close'])

const { t } = useI18n()

const menuEl = ref(null)

const clamped_x = ref(0)
const clamped_y = ref(0)

const favorite_highlight_colors = FAVORITE_HIGHLIGHT_COLORS

const current_highlight_color = computed(() => normalize_favorite_highlight_color(
  props.context_menu?.favoriteHighlightColor || props.context_menu?.highlight_color
))

const current_highlight_color_label = computed(() => (
  current_highlight_color.value ? t(`files.highlight.colors.${current_highlight_color.value}`) : ''
))

function highlight_color_title(colorKey) {
  const key = normalize_favorite_highlight_color(colorKey)
  return key ? t('files.highlight.highlightedAs', { color: t(`files.highlight.colors.${key}`) }) : ''
}

function target_file_type() {
  const type = String(props.context_menu?.targetFileType || props.context_menu?.type || 'file').trim()
  return type === 'directory' ? 'directory' : 'file'
}

function target_path() {
  return String(
    props.context_menu?.path ||
    props.context_menu?.targetPath ||
    props.context_menu?.target_path ||
    props.context_menu?.filePath ||
    props.context_menu?.file_path ||
    ''
  ).trim()
}

function target_workspace_id() {
  return String(
    props.context_menu?.ws ||
    props.context_menu?.workspace_id ||
    props.context_menu?.workspaceId ||
    ''
  ).trim()
}

function toast_context_menu_error(message) {
  try {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message,
          type: 'error',
          duration: 2600
        }
      })
    )
  } catch {}
}

function emit_favorite_highlight(colorKey) {
  const color = normalize_favorite_highlight_color(colorKey)
  const path = target_path()

  if (!path || !color) {
    toast_context_menu_error(t('files.controller.messages.highlightUpdateFailed'))
    emit('close')
    return
  }

  window.dispatchEvent(
    new CustomEvent('nisb-favorites-highlight-set', {
      detail: {
        path,
        type: target_file_type(),
        color,
        workspace_id: target_workspace_id()
      }
    })
  )

  emit('close')
}

function emit_favorite_highlight_clear() {
  const path = target_path()

  if (!path) {
    toast_context_menu_error(t('files.controller.messages.highlightUpdateFailed'))
    emit('close')
    return
  }

  window.dispatchEvent(
    new CustomEvent('nisb-favorites-highlight-clear', {
      detail: {
        path,
        type: target_file_type(),
        workspace_id: target_workspace_id()
      }
    })
  )

  emit('close')
}

const menu_classes = computed(() => {
  const targetType = String(props.context_menu?.targetType || 'unknown')
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '-')
  const targetFileType = String(props.context_menu?.targetFileType || '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '-')

  return {
    [`target-${targetType}`]: true,
    [`file-type-${targetFileType}`]: !!targetFileType,
    'is-file-menu': targetType === 'file',
    'is-directory-menu': targetType === 'file' && targetFileType === 'directory'
  }
})

function is_doc_file(name) {
  return /\.doc$/i.test(String(name || '').trim())
}
function is_docx_file(name) {
  return /\.docx$/i.test(String(name || '').trim())
}
function is_ppt_file(name) {
  return /\.ppt$/i.test(String(name || '').trim())
}
function is_pptx_file(name) {
  return /\.pptx$/i.test(String(name || '').trim())
}
function is_txt_file(name) {
  return /\.txt$/i.test(String(name || '').trim())
}

function _num(v, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function _wait_raf() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

async function clamp_to_viewport() {
  await nextTick()
  await _wait_raf()

  const margin = 8
  const vw = _num(window.innerWidth, 0)
  const vh = _num(window.innerHeight, 0)

  let x = _num(props.context_menu?.x, 0)
  let y = _num(props.context_menu?.y, 0)

  let mw = 280
  let mh = 240
  const el = menuEl.value
  if (el && typeof el.getBoundingClientRect === 'function') {
    const r = el.getBoundingClientRect()
    const rw = _num(r.width, 0)
    const rh = _num(r.height, 0)
    if (rw > 40) mw = rw
    if (rh > 40) mh = rh
  }

  if (x < margin) x = margin
  if (x + mw + margin > vw) x = Math.max(margin, vw - mw - margin)

  const space_below = vh - y - margin
  const space_above = y - margin

  if (space_below < mh && space_above >= Math.min(mh, vh - margin * 2)) {
    y = y - mh
  }

  if (y < margin) y = margin
  if (y + mh + margin > vh) y = Math.max(margin, vh - mh - margin)

  clamped_x.value = Math.round(x)
  clamped_y.value = Math.round(y)
}

watch(
  () => [
    props.visible,
    props.context_menu?.x,
    props.context_menu?.y,
    props.context_menu?.targetType,
    props.context_menu?.targetFileType,
    props.context_menu?.targetName,
    props.visible_extensions.length
  ],
  async () => {
    if (!props.visible) return
    await clamp_to_viewport()
  },
  { immediate: true }
)

function emit_action(action) {
  emit('action', { action })
  emit('close')
}

function emit_extension_click(ext) {
  emit('action', { action: 'extension_click', payload: { ext } })
}

function on_resize() {
  if (!props.visible) return
  clamp_to_viewport()
}

onMounted(() => {
  window.addEventListener('resize', on_resize)
})

onUnmounted(() => {
  window.removeEventListener('resize', on_resize)
})
</script>

<style scoped>
.zen-context-menu {
  z-index: 2147483647;
  width: max-content;
  min-width: 248px;
  max-width: min(360px, calc(100vw - 16px));
  max-height: calc(100vh - 16px);
  overflow-x: hidden;
  overflow-y: auto;
  box-sizing: border-box;
  display: grid;
  gap: 3px;
  padding: 7px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 42%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 90%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.30),
    0 2px 14px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(16px);
  scrollbar-width: thin;
  transform-origin: top left;
  animation: context-menu-in 0.11s ease-out;
}

.zen-context-menu.is-directory-menu {
  min-width: 278px;
}

.zen-context-menu.is-file-menu {
  min-width: 286px;
}

.menu-item {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 10px;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.25;
  text-align: left;
  white-space: normal;
  overflow-wrap: break-word;
  transition:
    background 0.14s ease,
    border-color 0.14s ease,
    color 0.14s ease,
    transform 0.12s ease;
}

.menu-item:hover,
.menu-item:focus-visible {
  outline: none;
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--text-main, var(--text));
}

.menu-item:active {
  transform: translateY(1px);
}

.menu-item.primary-ish {
  color: var(--text-main, var(--text));
}

.menu-item.primary-ish:hover,
.menu-item.primary-ish:focus-visible {
  border-color: color-mix(in srgb, #16a34a 32%, var(--line));
  background: color-mix(in srgb, #16a34a 9%, var(--editor-bg));
  color: #16a34a;
}

.menu-item.capability:hover,
.menu-item.capability:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg));
  color: var(--selected);
}

.menu-item.convert:hover,
.menu-item.convert:focus-visible,
.menu-item.preview:hover,
.menu-item.preview:focus-visible,
.menu-item.extension:hover,
.menu-item.extension:focus-visible {
  border-color: color-mix(in srgb, #16a34a 28%, var(--line));
  background: color-mix(in srgb, #16a34a 8%, var(--editor-bg));
  color: var(--text-main, var(--text));
}

.menu-item.favorite:hover,
.menu-item.favorite:focus-visible {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: color-mix(in srgb, #d97706 10%, var(--editor-bg));
  color: #d97706;
}

.favorite-highlight-panel {
  min-width: 0;
  display: grid;
  gap: 7px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, #d97706 20%, var(--line));
  border-radius: 11px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, #d97706 8%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
}

.highlight-panel-head {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1.25;
}

.highlight-current {
  flex: 0 0 auto;
  max-width: 120px;
  overflow: hidden;
  color: #d97706;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.highlight-color-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.highlight-color-btn {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--favorite-highlight-color, #d97706) 34%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--favorite-highlight-color, #d97706) 11%, var(--editor-bg));
  cursor: pointer;
  padding: 0;
  transition:
    border-color 0.14s ease,
    background 0.14s ease,
    transform 0.12s ease,
    box-shadow 0.14s ease;
}

.highlight-color-btn span {
  width: 11px;
  height: 11px;
  border-radius: 999px;
  background: var(--favorite-highlight-color, #d97706);
  box-shadow: 0 0 0 2px color-mix(in srgb, white 22%, transparent) inset;
}

.highlight-color-btn:hover,
.highlight-color-btn:focus-visible,
.highlight-color-btn.active {
  outline: none;
  border-color: color-mix(in srgb, var(--favorite-highlight-color, #d97706) 72%, var(--line));
  background: color-mix(in srgb, var(--favorite-highlight-color, #d97706) 18%, var(--editor-bg));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--favorite-highlight-color, #d97706) 12%, transparent);
}

.highlight-color-btn:active {
  transform: translateY(1px);
}

.highlight-clear-btn {
  width: 100%;
  min-height: 28px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 9px;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  text-align: center;
  transition:
    background 0.14s ease,
    border-color 0.14s ease,
    color 0.14s ease;
}

.highlight-clear-btn:hover,
.highlight-clear-btn:focus-visible {
  outline: none;
  border-color: color-mix(in srgb, #d97706 30%, var(--line));
  background: color-mix(in srgb, #d97706 8%, var(--editor-bg));
  color: #d97706;
}

.menu-item.danger {
  color: #ef4444;
}

.menu-item.danger:hover,
.menu-item.danger:focus-visible {
  border-color: rgba(239, 68, 68, 0.42);
  background: rgba(239, 68, 68, 0.10);
  color: #ef4444;
}

.menu-separator {
  width: calc(100% - 10px);
  max-width: calc(100% - 10px);
  height: 1px;
  box-sizing: border-box;
  margin: 3px 5px;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--line) 84%, transparent),
    transparent
  );
}

@keyframes context-menu-in {
  from {
    opacity: 0;
    transform: translateY(-2px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 420px) {
  .zen-context-menu {
    min-width: min(286px, calc(100vw - 16px));
    max-width: calc(100vw - 16px);
    border-radius: 13px;
  }

  .menu-item {
    min-height: 36px;
    font-size: 0.82rem;
  }
}
</style>

