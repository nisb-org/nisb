<template>
  <div class="tree-node" ref="nodeEl">
    <div
      class="file-item"
      :class="{
        selected: isSelected,
        'in-library-file': isInLibraryFile,
        focused: isFocused,
        covered: isDir && hasCoverage,
        directory: isDir,
        file: isFile,
        'favorite-highlighted': hasFavoriteHighlight
      }"
      :style="baseStyle"
      @click.stop="onClick"
      @contextmenu.prevent.stop="onContextMenu"
    >
      <input
        v-if="batchMode"
        class="batch-checkbox"
        type="checkbox"
        :checked="isBatchSelected(path)"
        @click.stop
        @change.stop="onBatchChange"
        :title="batchSelectTitle"
      />

      <span class="file-icon">{{ iconText }}</span>
      <span class="file-name">{{ displayName }}</span>
      <span
        v-if="hasFavoriteHighlight"
        class="highlight-dot"
        :title="favoriteHighlightTitle"
      ></span>

      <span v-if="isFile && hasHebbianMark" class="hebbian-mark" :title="hebbianMarkTitle">◦</span>
      <span v-if="isFile && librarySent" class="library-mark" :title="libraryFileTitle">▢</span>
      <span v-if="isDir && hasCoverage" class="library-dir-mark" :title="libraryDirTitle">▢</span>

      <span
        v-if="isDir"
        class="focus-dot"
        :class="{ active: isFocused }"
        :title="focusTitle"
        @click.stop.prevent="onFocusRootClick"
      >
        {{ isFocused ? '◉' : '○' }}
      </span>

      <span
        class="fav-star"
        :class="{ active: isFavorite }"
        :title="favoriteTitle"
        @click.stop.prevent="onToggleFavorite"
      >
        {{ isFavorite ? '★' : '☆' }}
      </span>
    </div>

    <div v-if="expanded" class="children">
      <div v-if="loadingChildren" class="empty-tip">{{ loadingChildrenText }}</div>

      <FileTreeNode
        v-else
        v-for="child in children"
        :key="child.path"
        :workspace-id="workspaceId"
        :node="{ name: child.name, type: child.type }"
        :path="child.path"
        :level="level + 1"
        :selected-path="selectedPath"
        :expanded-paths="expandedPaths"
        :scroll-target-path="scrollTargetPath"
        :call-tool="callTool"
        :favorite-map="favoriteMap"
        :favorite-meta-map="favoriteMetaMap"
        :metadata-call-tool="metadataCallTool"
        :focused-root-path="focusedRootPath"
        :library-status-map="libraryStatusMap"
        :apply-toggle-result="applyToggleResult"
        :refresh-library-status="refreshLibraryStatus"
        :batch-mode="batchMode"
        :is-batch-selected="isBatchSelected"
        :set-batch-selected="setBatchSelected"
        @select="(p) => emit('select', p)"
        @set-current-path="(p) => emit('set-current-path', p)"
        @toggle-expand="(payload) => emit('toggle-expand', payload)"
        @focus-root="(p) => emit('focus-root', p)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { get_parent_dir, get_base_name } from '../../../composables/left_sidebar/file_browser/file_browser_utils'
import {
  favorite_highlight_style,
  normalize_favorite_highlight_color
} from '../../../composables/left_sidebar/file_browser/favorite_highlight_colors'
import { normalizeToolResponse } from '../../../composables/left_sidebar/actions/response_normalizer'

defineOptions({ name: 'FileTreeNode' })

const props = defineProps({
  workspaceId: { type: String, required: true },
  node: { type: Object, required: true },
  path: { type: String, required: true },
  level: { type: Number, required: true },

  selectedPath: { type: String, required: false, default: '' },
  expandedPaths: { type: Array, required: false, default: () => [] },
  scrollTargetPath: { type: String, required: false, default: '' },

  callTool: { type: Function, required: true },
  metadataCallTool: { type: Function, required: false, default: null },
  favoriteMap: { type: Object, required: true },
  favoriteMetaMap: { type: Object, required: false, default: () => ({}) },
  focusedRootPath: { type: String, required: false, default: '' },
  libraryStatusMap: { type: Object, required: true },
  applyToggleResult: { type: Function, required: true },
  refreshLibraryStatus: { type: Function, required: true },

  batchMode: { type: Boolean, required: false, default: false },
  isBatchSelected: { type: Function, required: false, default: () => false },
  setBatchSelected: { type: Function, required: false, default: () => {} }
})

const emit = defineEmits(['select', 'set-current-path', 'toggle-expand', 'focus-root'])

const { t } = useI18n()

const expanded = ref(false)
const children = ref([])
const loadingChildren = ref(false)
const hasHebbianMark = ref(false)
const nodeEl = ref(null)

const DEFAULT_CONVERTED_NAME = 'converted.md'

const isDir = computed(() => props.node?.type === 'directory')
const isFile = computed(() => props.node?.type === 'file')

const iconText = computed(() => (isDir.value ? (expanded.value ? '📂' : '📁') : '📄'))
const displayName = computed(() => String(props.node?.name || get_base_name(props.path) || props.path))

const isFavorite = computed(() => !!props.favoriteMap?.[props.path])
const isFocused = computed(() => isDir.value && String(props.focusedRootPath || '') === props.path)

const favoriteMeta = computed(() => props.favoriteMetaMap?.[props.path] || null)
const highlightColor = computed(() => normalize_favorite_highlight_color(favoriteMeta.value?.highlight_color))
const hasFavoriteHighlight = computed(() => !!highlightColor.value)
const highlightColorLabel = computed(() => (
  highlightColor.value ? t(`files.highlight.colors.${highlightColor.value}`) : ''
))
const favoriteHighlightTitle = computed(() => (
  highlightColorLabel.value ? t('files.highlight.highlightedAs', { color: highlightColorLabel.value }) : ''
))

const libraryStatus = computed(() => props.libraryStatusMap?.[props.path] || null)
const librarySent = computed(() => !!(libraryStatus.value && libraryStatus.value.sent))
const isSelected = computed(() => props.path === props.selectedPath)
const isInLibraryFile = computed(() => isFile.value && librarySent.value)
const libraryNames = computed(() => {
  const ls = libraryStatus.value
  return Array.isArray(ls?.libraries) ? ls.libraries : []
})

const directoryCoverage = computed(() => {
  if (!isDir.value) return 0
  const v = Number(libraryStatus.value?.coverage || 0)
  if (!Number.isFinite(v) || v < 0) return 0
  return Math.max(0, Math.min(1, v))
})

const hasCoverage = computed(() => directoryCoverage.value > 0)

const batchSelectTitle = computed(() => t('files.treeNode.batchSelect'))
const hebbianMarkTitle = computed(() => t('files.treeNode.hebbianMarked'))
const focusTitle = computed(() => (
  isFocused.value ? t('files.treeNode.clearFocus') : t('files.treeNode.focusHere')
))
const favoriteTitle = computed(() => (
  isFavorite.value ? t('files.treeNode.unsetFavorite') : t('files.treeNode.setFavorite')
))
const loadingChildrenText = computed(() => t('files.treeNode.loadingChildren'))
const libraryDirTitle = computed(() => (
  isDir.value && hasCoverage.value
    ? t('files.treeNode.libraryCoverage', { percent: (directoryCoverage.value * 100).toFixed(0) })
    : ''
))
const libraryFileTitle = computed(() => getLibraryFileTitle())

function toast(message, type = 'info', duration = 2500) {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type, duration } }))
}

function getInfo(res, fallbackText = t('files.treeNode.messages.actionCompleted')) {
  return normalizeToolResponse(res, fallbackText)
}

function getDataValue(res, key, fallback = undefined) {
  const info = getInfo(res)
  if (info?.data && info.data[key] !== undefined) return info.data[key]
  if (res && res[key] !== undefined) return res[key]
  return fallback
}

function getDataArray(res, key) {
  const info = getInfo(res)
  if (Array.isArray(info?.data?.[key])) return info.data[key]
  if (Array.isArray(res?.[key])) return res[key]
  return []
}

function favoriteCallTool(toolName, args = {}, options = undefined) {
  const fn = typeof props.metadataCallTool === 'function' ? props.metadataCallTool : props.callTool
  return fn(toolName, args, options)
}

function getLibraryFileTitle() {
  const names = libraryNames.value
  if (!names.length) return t('files.treeNode.inLibrary')
  if (names.length <= 3) {
    return t('files.treeNode.inLibraries', { names: names.join(', ') })
  }
  return t('files.treeNode.inLibrariesMore', {
    names: names.slice(0, 3).join(', '),
    extraCount: names.length - 3
  })
}

function updateHebbianFromStorage() {
  try {
    const key = `hebbian_mark_${props.path}`
    if (localStorage.getItem(key)) hasHebbianMark.value = true
  } catch {}
}

function onHebbianCompleted(e) {
  const source = e?.detail?.source
  if (source === props.path) {
    hasHebbianMark.value = true
    try {
      const key = `hebbian_mark_${props.path}`
      localStorage.setItem(key, String(Date.now()))
    } catch {}
  }
}

function hasExtension(name, ext) {
  return String(name || '').toLowerCase().endsWith(ext)
}
function is_epub_name(name) {
  return hasExtension(name, '.epub')
}
function is_docx_name(name) {
  return hasExtension(name, '.docx')
}
function is_pptx_name(name) {
  return hasExtension(name, '.pptx')
}
function is_doc_name(name) {
  return hasExtension(name, '.doc')
}
function is_ppt_name(name) {
  return hasExtension(name, '.ppt')
}

function resolveMdPath(res) {
  const v = getDataValue(res, 'md_path', '')
  return String(v || '').trim()
}

async function convertOfficeAndOpen(kind, srcPath, srcName) {
  const tool =
    kind === 'doc'
      ? 'nisb_doc_convert_to_note'
      : kind === 'docx'
        ? 'nisb_docx_convert_to_note'
        : kind === 'ppt'
          ? 'nisb_ppt_convert_to_note'
          : 'nisb_pptx_convert_to_note'

  const argKey =
    kind === 'doc'
      ? 'doc_path'
      : kind === 'docx'
        ? 'docx_path'
        : kind === 'ppt'
          ? 'ppt_path'
          : 'pptx_path'

  const argsBase = {
    [argKey]: srcPath,
    workspace_id: props.workspaceId,
    output_md_path: '',
    image_dirname: 'images',
    overwrite: false
  }

  try {
    toast(t('files.treeNode.messages.convertingToMarkdown', { kind: kind.toUpperCase() }), 'info', 2500)
    let r = await props.callTool(tool, argsBase)
    let info = getInfo(r, t('files.treeNode.messages.conversionCompleted'))

    if (info.success) {
      const mdPath = resolveMdPath(r)
      if (!mdPath) {
        toast(t('files.treeNode.messages.missingMdPath'), 'error', 3500)
        return
      }
      window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
      const openName = get_base_name(mdPath) || (srcName ? `${srcName}.md` : DEFAULT_CONVERTED_NAME)
      window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: mdPath, name: openName } }))
      return
    }

    const msg = String(info.message || info.text || '')
    if (msg.includes('Busy:') || msg.includes('max_concurrent=1') || msg.toLowerCase().includes('lock')) {
      toast(msg || t('files.treeNode.messages.busy'), 'warning', 3500)
      return
    }

    const mdPath0 = resolveMdPath(r)
    const isExists =
      msg.includes('overwrite=false') ||
      msg.includes('Target markdown exists') ||
      msg.includes('already exists') ||
      msg.includes('exists (overwrite=false)')

    if (isExists) {
      if (mdPath0) {
        window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
        window.dispatchEvent(
          new CustomEvent('nisb-open-file', {
            detail: {
              path: mdPath0,
              name: get_base_name(mdPath0) || DEFAULT_CONVERTED_NAME
            }
          })
        )
        toast(t('files.treeNode.messages.alreadyExistsOpened'), 'success', 2200)
        return
      }
      const ok = confirm(msg)
      if (!ok) {
        toast(t('files.treeNode.messages.overwriteCanceled'), 'info', 1800)
        return
      }
      r = await props.callTool(tool, { ...argsBase, overwrite: true })
      info = getInfo(r, t('files.treeNode.messages.conversionCompleted'))
      if (info.success) {
        const mdPath = resolveMdPath(r)
        if (!mdPath) {
          toast(t('files.treeNode.messages.missingMdPath'), 'error', 3500)
          return
        }
        window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
        window.dispatchEvent(
          new CustomEvent('nisb-open-file', {
            detail: {
              path: mdPath,
              name: get_base_name(mdPath) || DEFAULT_CONVERTED_NAME
            }
          })
        )
        toast(t('files.treeNode.messages.generated'), 'success', 2200)
        return
      }
    }

    toast(String(info.text || t('files.treeNode.messages.conversionFailed')), 'error', 3500)
  } catch (e) {
    toast(e?.message || String(e), 'error', 3500)
  }
}

function openFileWithGuards() {
  const name = String(props.node?.name || '')
  if (is_epub_name(name) || is_epub_name(props.path)) {
    window.dispatchEvent(new CustomEvent('nisb-open-epub', { detail: { path: props.path, name } }))
    return
  }
  if (is_doc_name(name) || is_doc_name(props.path)) return convertOfficeAndOpen('doc', props.path, name)
  if (is_docx_name(name) || is_docx_name(props.path)) return convertOfficeAndOpen('docx', props.path, name)
  if (is_ppt_name(name) || is_ppt_name(props.path)) return convertOfficeAndOpen('ppt', props.path, name)
  if (is_pptx_name(name) || is_pptx_name(props.path)) return convertOfficeAndOpen('pptx', props.path, name)

  window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: props.path, name } }))
}

async function activate() {
  emit('select', props.path)

  if (isFile.value) {
    openFileWithGuards()
    return
  }

  expanded.value = !expanded.value
  emit('toggle-expand', { path: props.path, expanded: expanded.value })

  if (expanded.value) emit('set-current-path', props.path)

  if (children.value.length === 0 && expanded.value) await loadChildren()
}

function onClick() {
  activate()
}

function onContextMenu(e) {
  emit('set-current-path', get_parent_dir(props.path))
  const isFocusedNow = isDir.value && String(props.focusedRootPath || '') === props.path

  window.dispatchEvent(
    new CustomEvent('file-context-menu', {
      detail: {
        x: e.clientX,
        y: e.clientY,
        targetType: 'file',
        targetFileType: isDir.value ? 'directory' : 'file',
        targetName: String(props.node?.name || ''),
        path: props.path,
        name: String(props.node?.name || ''),
        type: props.node?.type,
        ws: props.workspaceId,
        favoriteHighlightColor: highlightColor.value,
        extensions: [
          {
            id: 'focus_root',
            title: t('files.treeNode.contextMenuFocusHere'),
            visible: isDir.value && !isFocusedNow,
            payload: { path: props.path }
          },
          {
            id: 'clear_focus_root',
            title: t('files.treeNode.contextMenuClearFocus'),
            visible: isDir.value && isFocusedNow,
            payload: {}
          }
        ]
      }
    })
  )
}

function onBatchChange(e) {
  const checked = !!e?.target?.checked
  props.setBatchSelected(props.path, checked, {
    type: String(props.node?.type || ''),
    name: String(props.node?.name || '')
  })
}

async function loadChildren() {
  loadingChildren.value = true
  try {
    const result = await props.callTool('nisb_dir_list', { path: props.path })
    const info = getInfo(result, t('files.treeNode.messages.directoryLoaded'))
    const listRaw = getDataArray(result, 'entries')

    if (info.success && Array.isArray(listRaw)) {
      const list = listRaw
        .filter((e) => !String(e.name || '').startsWith('.'))
        .map((e) => ({ name: e.name, type: e.type, path: `${props.path}/${e.name}` }))
      children.value = list
      await props.refreshLibraryStatus(list.map((c) => c.path))
    } else {
      children.value = []
    }
  } finally {
    loadingChildren.value = false
  }
}

function autoExpandIfNeeded(sel) {
  if (!isDir.value) return
  const bySelection = !!(sel && (sel === props.path || String(sel).startsWith(props.path)))
  const byState = Array.isArray(props.expandedPaths) && props.expandedPaths.includes(props.path)
  if (bySelection || byState) {
    if (!expanded.value) {
      expanded.value = true
      emit('toggle-expand', { path: props.path, expanded: true })
      emit('set-current-path', props.path)
      loadChildren()
    }
  }
}

async function onToggleFavorite() {
  try {
    const res = await favoriteCallTool('nisb_favorites_toggle_file', {
      path: props.path,
      type: props.node?.type,
      workspace_id: props.workspaceId
    })
    const info = getInfo(res, t('files.treeNode.messages.favoritesUpdated'))
    if (info.success) {
      props.applyToggleResult(getDataValue(res, 'item', null), !!getDataValue(res, 'pinned', false))
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: {
            message: info.text || t('files.treeNode.messages.favoritesUpdated'),
            type: info.isWarning ? 'warning' : 'info'
          }
        })
      )
      window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    } else {
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: {
            message: info.text || t('files.treeNode.messages.favoritesUpdateFailed'),
            type: 'error'
          }
        })
      )
    }
  } catch (e) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: e?.message || String(e),
          type: 'error'
        }
      })
    )
  }
}

function onFocusRootClick() {
  if (!isDir.value) return
  emit('focus-root', props.path)
}

function getScrollParent(el) {
  let cur = el?.parentElement || null

  while (cur && cur !== document.body && cur !== document.documentElement) {
    try {
      const style = window.getComputedStyle(cur)
      const oy = String(style.overflowY || '')
      const canScroll = /(auto|scroll|overlay)/.test(oy) && cur.scrollHeight > cur.clientHeight + 4
      if (canScroll) return cur
    } catch {}

    cur = cur.parentElement
  }

  return null
}

function scrollNodeToReadingBand() {
  const el = nodeEl.value
  if (!el) return false

  const scroller = getScrollParent(el)
  if (!scroller || typeof scroller.scrollTo !== 'function') return false

  try {
    const er = el.getBoundingClientRect()
    const sr = scroller.getBoundingClientRect()
    const targetTop = scroller.scrollTop + (er.top - sr.top) - scroller.clientHeight * 0.62
    const maxTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
    const top = Math.max(0, Math.min(maxTop, targetTop))

    scroller.scrollTo({ top, behavior: 'smooth' })
    return true
  } catch {
    return false
  }
}

function maybeScrollIntoView() {
  if (!nodeEl.value) return
  if (!props.scrollTargetPath) return
  if (props.scrollTargetPath !== props.path) return

  requestAnimationFrame(() => {
    if (scrollNodeToReadingBand()) return

    try {
      nodeEl.value.scrollIntoView({ block: 'center', behavior: 'smooth' })
    } catch {}
  })
}

const baseStyle = computed(() => {
  const coverage = isDir.value ? directoryCoverage.value : 0
  const hasCov = coverage > 0
  const coverageOpacity = hasCov ? 0.4 + 0.6 * Math.min(1, coverage + 0.25) : 1

  return {
    '--tree-indent': `${0.5 + props.level * 1.08}rem`,
    '--coverage-opacity': String(isDir.value && hasCov ? coverageOpacity : 1),
    ...favorite_highlight_style(highlightColor.value)
  }
})

onMounted(() => {
  updateHebbianFromStorage()
  window.addEventListener('nisb-hebbian-completed', onHebbianCompleted)
  autoExpandIfNeeded(props.selectedPath)
  maybeScrollIntoView()
})

onUnmounted(() => {
  window.removeEventListener('nisb-hebbian-completed', onHebbianCompleted)
})

watch(
  () => props.selectedPath,
  (val) => autoExpandIfNeeded(val)
)
watch(
  () => props.expandedPaths,
  () => autoExpandIfNeeded(props.selectedPath)
)
watch(
  () => props.scrollTargetPath,
  () => maybeScrollIntoView()
)
</script>

<style scoped>
.tree-node {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.file-item {
  position: relative;
  min-width: 0;
  min-height: 28px;
  display: flex;
  align-items: center;
  gap: 0.36rem;
  padding: 0.24rem 0.38rem;
  padding-left: var(--tree-indent, 0.5rem);
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  opacity: var(--coverage-opacity, 1);
  font-size: 0.82rem;
  line-height: 1.35;
  transition:
    background 0.15s var(--ease-smooth, ease),
    border-color 0.15s var(--ease-smooth, ease),
    color 0.15s var(--ease-smooth, ease),
    opacity 0.15s var(--ease-smooth, ease),
    transform 0.15s var(--ease-smooth, ease);
}

.file-item:hover {
  border-color: color-mix(in srgb, var(--selected) 20%, transparent);
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--text-main, var(--text));
}

.file-item.selected {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent) 0%,
      color-mix(in srgb, var(--selected) 12%, transparent) 100%
    );
  color: var(--selected);
  font-weight: 760;
}

.file-item.in-library-file:not(.selected) {
  color: var(--text-main, var(--text));
}

.file-item.focused {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
}

.file-item.favorite-highlighted:not(.selected) {
  border-color: color-mix(in srgb, var(--favorite-highlight-color, #d97706) 22%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--favorite-highlight-color, #d97706) 8%, transparent),
      transparent 72%
    );
  color: var(--text-main, var(--text));
}

.file-item.favorite-highlighted::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 999px;
  background: var(--favorite-highlight-color, #d97706);
  opacity: 0.68;
  pointer-events: none;
}

.file-item.favorite-highlighted.selected::before {
  opacity: 0.9;
}

.file-icon {
  flex: 0 0 auto;
  width: 1.2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  line-height: 1;
}

.file-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  overflow-wrap: anywhere;
}

.highlight-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border: 1px solid color-mix(in srgb, var(--favorite-highlight-color, #d97706) 64%, var(--line));
  border-radius: 999px;
  background: var(--favorite-highlight-color, #d97706);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--favorite-highlight-color, #d97706) 11%, transparent);
  opacity: 0.9;
}

.batch-checkbox {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  margin: 0 4px 0 0;
  accent-color: var(--selected, #7fb0ff);
  opacity: 0.86;
}

.hebbian-mark,
.library-mark,
.library-dir-mark {
  flex: 0 0 auto;
  min-width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  line-height: 1;
  opacity: 0.66;
  transition:
    opacity 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.hebbian-mark {
  border-color: color-mix(in srgb, #16a34a 24%, var(--line));
  background: color-mix(in srgb, #16a34a 8%, transparent);
  color: #16a34a;
}

.library-mark,
.library-dir-mark {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.library-dir-mark {
  opacity: 0.52;
}

.file-item:hover .hebbian-mark,
.file-item:hover .library-mark,
.file-item:hover .library-dir-mark,
.file-item.selected .hebbian-mark,
.file-item.selected .library-mark,
.file-item.selected .library-dir-mark {
  opacity: 0.95;
}

.focus-dot,
.fav-star {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.82rem;
  line-height: 1;
  opacity: 0.34;
  transition:
    opacity 0.15s ease,
    transform 0.12s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.file-item:hover .focus-dot,
.file-item:hover .fav-star {
  opacity: 0.88;
}

.focus-dot:hover,
.fav-star:hover {
  transform: scale(1.06);
}

.focus-dot.active {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  opacity: 0.96;
}

.fav-star.active {
  border-color: color-mix(in srgb, #d97706 34%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
  opacity: 0.96;
}

.children {
  min-width: 0;
  display: flex;
  flex-direction: column;
  margin-left: 0.55rem;
  padding-left: 0.25rem;
  border-left: 1px solid color-mix(in srgb, var(--line) 62%, transparent);
}

.empty-tip {
  margin: 0.25rem 0 0.25rem 0.4rem;
  padding: 0.45rem 0.55rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

@media (max-width: 420px) {
  .file-item {
    gap: 0.3rem;
    padding-right: 0.3rem;
  }

  .focus-dot,
  .fav-star {
    width: 24px;
    height: 24px;
  }

  .children {
    margin-left: 0.35rem;
  }
}
</style>

