<template>
  <div ref="fileListEl" class="file-list">
    <div class="favorites-block">
      <div class="favorites-header">
        <span class="fav-title">{{ t('files.favorites.title') }}</span>
        <span class="fav-count">{{ favorites.length }}</span>
      </div>

      <div v-if="!favorites.length" class="empty-tip">
        {{ t('files.favorites.emptyHint') }}
      </div>

      <div v-if="favoriteDirs.length" class="favorites-list">
        <div class="fav-subtitle">{{ t('files.favorites.directories') }}</div>
        <div
          v-for="fav in favoriteDirs"
          :key="'dir-' + fav.path"
          class="favorite-item"
          :class="{
            selected: selectedPath === fav.path,
            focused: isFocusedPath(fav.path),
            directory: fav.type === 'directory',
            highlighted: !!favoriteHighlightColor(fav)
          }"
          :style="favoriteHighlightStyle(fav)"
          @click="openFavorite(fav)"
          @contextmenu.prevent.stop="onFavoriteContextMenu(fav, $event)"
          @mouseenter="onFavEnter(fav, $event)"
          @mousemove="onFavMove($event)"
          @mouseleave="onFavLeave"
        >
          <span class="fav-icon">📁</span>
          <span class="fav-name">{{ getBaseName(fav.path) }}</span>
          <span
            v-if="favoriteHighlightColor(fav)"
            class="fav-highlight-dot"
            :title="favoriteHighlightTitle(fav)"
          ></span>

          <span
            v-if="fav.type === 'directory'"
            class="fav-focus"
            :class="{ active: isFocusedPath(fav.path) }"
            :title="isFocusedPath(fav.path) ? t('files.favorites.unfocus') : t('files.favorites.focus')"
            @click.stop="toggleFocusRoot(fav.path)"
          >
            {{ isFocusedPath(fav.path) ? '◉' : '○' }}
          </span>

          <span
            class="fav-star fav-star-small active"
            :title="t('files.favorites.remove')"
            @click.stop="toggleFavoriteFromList(fav)"
          >
            ★
          </span>
        </div>
      </div>

      <div v-if="favoriteDirs.length && favoriteFiles.length" class="fav-divider"></div>

      <div v-if="favoriteFiles.length" class="favorites-list">
        <div class="fav-subtitle">{{ t('files.favorites.files') }}</div>
        <div
          v-for="fav in favoriteFiles"
          :key="'file-' + fav.path"
          class="favorite-item"
          :class="{
            selected: selectedPath === fav.path,
            file: fav.type !== 'directory',
            highlighted: !!favoriteHighlightColor(fav)
          }"
          :style="favoriteHighlightStyle(fav)"
          @click="openFavoriteFileOnly(fav)"
          @contextmenu.prevent.stop="onFavoriteContextMenu(fav, $event)"
          @mouseenter="onFavEnter(fav, $event)"
          @mousemove="onFavMove($event)"
          @mouseleave="onFavLeave"
        >
          <span class="fav-icon">📄</span>
          <span class="fav-name">{{ getBaseName(fav.path) }}</span>
          <span
            v-if="favoriteHighlightColor(fav)"
            class="fav-highlight-dot"
            :title="favoriteHighlightTitle(fav)"
          ></span>
          <span
            class="fav-star fav-star-small active"
            :title="t('files.favorites.remove')"
            @click.stop="toggleFavoriteFromList(fav)"
          >
            ★
          </span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="empty-tip">{{ t('files.loading') }}</div>

    <template v-else>
      <div ref="rootRowEl" class="root-row">
        <div class="root-left">
          <div
            ref="crumbScrollEl"
            class="crumb-scroll"
            @mouseenter="on_crumb_enter"
            @mouseleave="on_crumb_leave"
            @mousemove="on_crumb_mouse_move"
          >
            <button class="crumb-btn" @click.stop="clearFocusRoot" :title="t('files.root.userTitle')">
              {{ t('files.root.userLabel') }}
            </button>
            <span class="crumb-sep">/</span>

            <template v-if="focusSegments.length">
              <span class="crumb-sep"></span>
              <template v-for="seg in focusSegments" :key="seg.path">
                <button
                  class="crumb-btn"
                  @click.stop="focusRoot(seg.path)"
                  :title="seg.displayPath || seg.path"
                >
                  {{ seg.displayName || seg.name }}
                </button>
                <span class="crumb-sep">/</span>
              </template>
            </template>
          </div>
        </div>

        <div class="root-right">
          <template v-if="batchMode">
            <span
              class="batch-pill"
              :title="t('files.batch.selectedTitle', { count: batchSelectedCount })"
            >
              {{ t('files.batch.selectedLabel', { count: batchSelectedCount }) }}
            </span>

            <button
              class="new-conv-btn batch-btn"
              @click.stop="selectAllCurrentLevel"
              :title="t('files.batch.selectAllCurrentLevel')"
            >
              ☑
            </button>

            <button
              class="new-conv-btn batch-btn"
              @click.stop="batchMoveSelected"
              :title="t('files.batch.moveSelected')"
            >
              🚚
            </button>

            <button
              class="new-conv-btn batch-btn"
              @click.stop="batchRenameSelected"
              :title="t('files.batch.renameSelected')"
            >
              ✎
            </button>

            <button
              class="new-conv-btn batch-btn danger-btn"
              @click.stop="batchDeleteSelected"
              :title="t('files.batch.deleteSelected')"
            >
              🗑
            </button>

            <button
              class="new-conv-btn batch-btn"
              @click.stop="toggleBatchMode(false)"
              :title="t('files.batch.exit')"
            >
              ✕
            </button>
          </template>

          <template v-else>
            <button
              class="new-conv-btn collapse-all-btn"
              @click.stop="collapseAllDirs"
              :title="t('files.actions.collapseAllDirs')"
            >
              ⤵
            </button>

            <button
              ref="rootPlusBtnEl"
              class="new-conv-btn root-plus-btn"
              @click.stop="on_root_plus_click"
              :title="t('files.actions.createInCurrentDir')"
            >
              ＋
            </button>

            <button
              class="new-conv-btn batch-toggle-btn"
              @click.stop="toggleBatchMode(true)"
              :title="t('files.batch.enter')"
            >
              ☑
            </button>
          </template>
        </div>
      </div>

      <div v-if="!entries.length" class="empty-tip">{{ t('files.empty') }}</div>

      <template v-else>
        <FileTreeNode
          v-for="item in entries"
          :key="item.path"
          :workspace-id="effectiveWorkspaceId"
          :node="{ name: item.name, type: item.type }"
          :path="item.path"
          :level="0"
          :selected-path="selectedPath"
          :expanded-paths="expandedPaths"
          :scroll-target-path="scrollTargetPath"
          :call-tool="fileCapabilityCallTool"
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
          @select="handleSelect"
          @set-current-path="handleSetCurrentPath"
          @toggle-expand="handleToggleExpand"
          @focus-root="toggleFocusRoot"
        />
      </template>
    </template>

    <div v-if="pathTip.visible" class="path-tooltip" :style="{ left: pathTip.x + 'px', top: pathTip.y + 'px' }">
      {{ pathTip.text }}
    </div>
  </div>
</template>

<script setup>
import { ref, toRef, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import FileTreeNode from './file_browser/FileTreeNode.vue'
import { use_file_browser_controller } from '../../composables/left_sidebar/file_browser/use_file_browser_controller'
import {
  favorite_highlight_style,
  normalize_favorite_highlight_color
} from '../../composables/left_sidebar/file_browser/favorite_highlight_colors'

const props = defineProps({
  workspaceId: { type: String, default: 'workspace_work' }
})

const { t } = useI18n()
const { callTool } = useMCP()

const FILE_BROWSER_UI_EVENT_DELAY_MS = 20
const CURRENT_DIR_UPDATE_DEBOUNCE_MS = 48
const DEFAULT_WORKSPACE_ID = 'workspace_work'

const FILE_WRITE_TOOLS = new Set([
  'nisb_file_create',
  'nisb_file_update',
  'nisb_file_rename',
  'nisb_file_move_path',
  'nisb_file_delete',
  'nisb_dir_create',
  'nisb_dir_delete',
  'nisb_dir_move_path',
  'nisb_fs_bulk_delete'
])

const FILE_DANGEROUS_TOOLS = new Set([
  'nisb_file_delete',
  'nisb_dir_delete',
  'nisb_fs_bulk_delete'
])

let __alive = true
let __context_menu_timer = null
let __current_dir_timer = null
let __current_dir_seq = 0

const fileListEl = ref(null)
const rootRowEl = ref(null)
const rootPlusBtnEl = ref(null)

const fileContextRefs = {
  workspace: null,
  focusRoot: null
}

function _string(value) {
  return String(value || '').trim()
}

function _clean_path(value) {
  let s = _string(value).replace(/\\/g, '/')
  while (s.startsWith('/')) s = s.slice(1)
  s = s
    .split('/')
    .map((part) => part.trim())
    .filter(Boolean)
    .join('/')
  return s
}

function _safe_path_from_args(args = {}) {
  if (!args || typeof args !== 'object') return ''

  const direct =
    args.filename ||
    args.path ||
    args.old_path ||
    args.new_path ||
    args.directory ||
    ''

  if (direct) return _clean_path(direct)

  if (Array.isArray(args.paths) && args.paths.length) {
    return _clean_path(args.paths[0])
  }

  return ''
}

function _read_workspace_switch_state() {
  try {
    const s = window.__nisb_workspace_switch_state
    return s && typeof s === 'object' ? s : {}
  } catch {
    return {}
  }
}

function _read_existing_file_context() {
  try {
    const ctx = window.__nisb_file_browser_context
    return ctx && typeof ctx === 'object' ? ctx : {}
  } catch {
    return {}
  }
}

function _read_existing_gate() {
  const ctx = _read_existing_file_context()
  if (ctx?.capability_gate && typeof ctx.capability_gate === 'object') return ctx.capability_gate
  if (ctx?.capabilityGate && typeof ctx.capabilityGate === 'object') return ctx.capabilityGate
  return {}
}

function _current_workspace_id() {
  const gate = _read_existing_gate()
  const ctx = _read_existing_file_context()

  const value =
    fileContextRefs.workspace?.value ||
    gate.workspace_id ||
    ctx.workspace_id ||
    ctx.workspaceId ||
    props.workspaceId ||
    DEFAULT_WORKSPACE_ID

  return _string(value) || DEFAULT_WORKSPACE_ID
}

function _current_focus_root() {
  const gate = _read_existing_gate()
  const ctx = _read_existing_file_context()

  const value =
    fileContextRefs.focusRoot?.value ||
    gate.focus_root ||
    ctx.focus_root ||
    ctx.focusRoot ||
    ''

  return _clean_path(value)
}

function _focus_root_for_tool(toolName, args = {}) {
  const currentFocus = _current_focus_root()
  if (currentFocus) return currentFocus

  if (FILE_DANGEROUS_TOOLS.has(toolName)) {
    return _safe_path_from_args(args)
  }

  return ''
}

function _build_file_capability_gate(toolName, args = {}, existingGate = {}) {
  const isWrite = FILE_WRITE_TOOLS.has(toolName)
  const isDangerous = FILE_DANGEROUS_TOOLS.has(toolName)
  const focusRoot = _focus_root_for_tool(toolName, args)

  return {
    ...existingGate,
    policy_version: Number(existingGate.policy_version || 1),
    workspace_id: _string(existingGate.workspace_id || _current_workspace_id()) || DEFAULT_WORKSPACE_ID,
    focus_root: _clean_path(existingGate.focus_root || focusRoot),
    fs_read_scope: _string(existingGate.fs_read_scope || 'user_ro') || 'user_ro',
    fs_write_scope: isWrite ? 'agent_files' : _string(existingGate.fs_write_scope || 'none') || 'none',
    fs_dangerous_enabled: isDangerous ? true : !!existingGate.fs_dangerous_enabled
  }
}

function _with_file_capability(toolName, args = {}) {
  const safeArgs = args && typeof args === 'object' && !Array.isArray(args) ? args : {}
  const existingGate = safeArgs.capability_gate && typeof safeArgs.capability_gate === 'object' ? safeArgs.capability_gate : {}

  const capability_gate = _build_file_capability_gate(toolName, safeArgs, existingGate)

  return {
    ...safeArgs,
    workspace_id: capability_gate.workspace_id,
    capability_gate
  }
}

async function fileCapabilityCallTool(toolName, args = {}, options = undefined) {
  const name = _string(toolName)
  const finalArgs = _with_file_capability(name, args)
  return callTool(name, finalArgs, options)
}

async function metadataCallTool(toolName, args = {}, options = undefined) {
  return callTool(toolName, args, options)
}

function _build_file_context_payload(extra = {}) {
  const capability_gate = _build_file_capability_gate('__context__', {}, {})

  return {
    workspaceId: capability_gate.workspace_id,
    workspace_id: capability_gate.workspace_id,
    focusRoot: capability_gate.focus_root,
    focus_root: capability_gate.focus_root,
    capabilityGate: capability_gate,
    capability_gate,
    ...extra
  }
}

function _sync_file_browser_context() {
  try {
    window.__nisb_file_browser_context = _build_file_context_payload()
  } catch {}
}

const ctrl = use_file_browser_controller({
  workspace_id_ref: toRef(props, 'workspaceId'),
  call_tool: fileCapabilityCallTool,
  metadata_call_tool: metadataCallTool,
  file_list_el: fileListEl,
  root_row_el: rootRowEl,
  root_plus_btn_el: rootPlusBtnEl
})

const {
  loading,
  entries,
  selectedPath,
  expandedPaths,
  scrollTargetPath,
  favorites,
  libraryStatusMap,
  focusedRootPath,

  batchMode,
  batchSelectedCount,
  isBatchSelected,
  setBatchSelected,
  selectAllCurrentLevel,
  toggleBatchMode,
  batchDeleteSelected,
  batchMoveSelected,
  batchRenameSelected,

  effectiveWorkspaceId,
  focusSegments,
  favoriteDirs,
  favoriteFiles,
  favoriteMap,
  favoriteMetaMap,

  pathTip,
  onFavEnter,
  onFavMove,
  onFavLeave,

  getBaseName,
  isFocusedPath,

  focusRoot,
  clearFocusRoot,
  toggleFocusRoot,
  collapseAllDirs,

  openFavorite,
  onFavoriteContextMenu,
  toggleFavoriteFromList,

  handleSelect,
  handleSetCurrentPath,
  handleToggleExpand,

  applyToggleResult,
  refreshLibraryStatus
} = ctrl

function openFavoriteFileOnly(fav) {
  const path = String(fav?.path || '').trim()
  if (!path) return

  const name = getBaseName(path) || path
  selectedPath.value = path

  window.dispatchEvent(
    new CustomEvent('nisb-open-file', {
      detail: {
        path,
        rel_path: path,
        name
      }
    })
  )
}

fileContextRefs.workspace = effectiveWorkspaceId
fileContextRefs.focusRoot = focusedRootPath

function favoriteHighlightColor(fav) {
  return normalize_favorite_highlight_color(fav?.highlight_color)
}

function favoriteHighlightStyle(fav) {
  return favorite_highlight_style(favoriteHighlightColor(fav))
}

function favoriteHighlightLabel(fav) {
  const key = favoriteHighlightColor(fav)
  return key ? t(`files.highlight.colors.${key}`) : ''
}

function favoriteHighlightTitle(fav) {
  const label = favoriteHighlightLabel(fav)
  return label ? t('files.highlight.highlightedAs', { color: label }) : ''
}

const current_dir = ref('agent_files')

function _safe_int(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 0
  return Math.round(n)
}

function _is_workspace_switch_busy() {
  return !!_read_workspace_switch_state()?.busy
}

function _clear_context_menu_timer() {
  if (__context_menu_timer) clearTimeout(__context_menu_timer)
  __context_menu_timer = null
}

function _clear_current_dir_timer() {
  if (__current_dir_timer) clearTimeout(__current_dir_timer)
  __current_dir_timer = null
}

function _dispatch_window_event_async(event_name, detail = {}, { delay = FILE_BROWSER_UI_EVENT_DELAY_MS } = {}) {
  return new Promise((resolve) => {
    _clear_context_menu_timer()

    __context_menu_timer = setTimeout(() => {
      __context_menu_timer = null

      if (!__alive) {
        resolve(false)
        return
      }

      if (_is_workspace_switch_busy()) {
        resolve(false)
        return
      }

      _sync_file_browser_context()

      window.dispatchEvent(
        new CustomEvent(event_name, {
          detail: _build_file_context_payload(detail)
        })
      )
      resolve(true)
    }, Math.max(0, Number(delay || 0)))
  })
}

function on_current_dir_changed(e) {
  const next_path = _clean_path(e?.detail?.path || '') || 'agent_files'
  const seq = ++__current_dir_seq

  _clear_current_dir_timer()
  __current_dir_timer = setTimeout(() => {
    if (!__alive) return
    if (seq !== __current_dir_seq) return
    current_dir.value = next_path
    _sync_file_browser_context()
  }, CURRENT_DIR_UPDATE_DEBOUNCE_MS)
}

async function on_root_plus_click(e) {
  if (_is_workspace_switch_busy()) return

  const ex = _safe_int(e?.clientX)
  const ey = _safe_int(e?.clientY)

  let x = ex
  let y = ey

  if (!x && !y) {
    const btn = rootPlusBtnEl.value
    if (btn && typeof btn.getBoundingClientRect === 'function') {
      const r = btn.getBoundingClientRect()
      x = _safe_int(r.left + r.width / 2)
      y = _safe_int(r.bottom + 6)
    }
  }

  const base_dir =
    _clean_path(current_dir.value || '') ||
    _clean_path(focusedRootPath?.value || '') ||
    'agent_files'

  await _dispatch_window_event_async('file-context-menu', {
    x,
    y,
    targetType: 'create',
    target_type: 'create',
    baseDir: base_dir,
    base_dir
  })
}

const crumbScrollEl = ref(null)

const is_hover_capable = ref(false)
let hover_mq = null
let hover_mq_handler = null

const CRUMB_EDGE_PX = 18
const CRUMB_MAX_PX_PER_S = 560

let crumb_hovering = false
let crumb_last_x = 0

let crumb_raf = 0
let crumb_last_ts = 0

function _crumb_can_scroll(el) {
  if (!el) return false
  const cw = Number(el.clientWidth || 0)
  const sw = Number(el.scrollWidth || 0)
  return sw > cw + 1
}

function _crumb_compute_speed(el) {
  if (!el || !_crumb_can_scroll(el)) return { dir: 0, speed: 0 }

  const rect = el.getBoundingClientRect()
  const x = Number(crumb_last_x || 0)

  const left_zone = rect.left + CRUMB_EDGE_PX
  const right_zone = rect.right - CRUMB_EDGE_PX

  if (x < left_zone) {
    const t = Math.min(1, (left_zone - x) / CRUMB_EDGE_PX)
    const speed = CRUMB_MAX_PX_PER_S * (0.18 + 0.82 * t)
    return { dir: -1, speed }
  }

  if (x > right_zone) {
    const t = Math.min(1, (x - right_zone) / CRUMB_EDGE_PX)
    const speed = CRUMB_MAX_PX_PER_S * (0.18 + 0.82 * t)
    return { dir: 1, speed }
  }

  return { dir: 0, speed: 0 }
}

function _crumb_stop_raf() {
  if (crumb_raf) cancelAnimationFrame(crumb_raf)
  crumb_raf = 0
  crumb_last_ts = 0
}

function _crumb_tick(ts) {
  if (!crumb_hovering || !is_hover_capable.value) {
    _crumb_stop_raf()
    return
  }

  const el = crumbScrollEl.value
  if (!el || !_crumb_can_scroll(el)) {
    _crumb_stop_raf()
    return
  }

  if (!crumb_last_ts) crumb_last_ts = ts
  const dt = Math.min(0.05, (ts - crumb_last_ts) / 1000)
  crumb_last_ts = ts

  const { dir, speed } = _crumb_compute_speed(el)
  if (dir && speed) {
    el.scrollLeft = Number(el.scrollLeft || 0) + dir * speed * dt
  }

  crumb_raf = requestAnimationFrame(_crumb_tick)
}

function _crumb_start_raf() {
  if (crumb_raf) return
  crumb_last_ts = 0
  crumb_raf = requestAnimationFrame(_crumb_tick)
}

function on_crumb_enter() {
  if (!is_hover_capable.value) return
  crumb_hovering = true
  _crumb_start_raf()
}

function on_crumb_leave() {
  crumb_hovering = false
  _crumb_stop_raf()
}

function on_crumb_mouse_move(e) {
  if (!is_hover_capable.value) return
  crumb_last_x = Number(e?.clientX || 0)
  if (crumb_hovering && !crumb_raf) _crumb_start_raf()
}

function _setup_hover_capability() {
  try {
    if (typeof window === 'undefined' || !window.matchMedia) {
      is_hover_capable.value = false
      return
    }

    hover_mq = window.matchMedia('(hover: hover) and (pointer: fine)')
    is_hover_capable.value = !!hover_mq.matches

    hover_mq_handler = (ev) => {
      is_hover_capable.value = !!ev?.matches
      if (!is_hover_capable.value) {
        crumb_hovering = false
        _crumb_stop_raf()
      }
    }

    if (hover_mq.addEventListener) hover_mq.addEventListener('change', hover_mq_handler)
    else if (hover_mq.addListener) hover_mq.addListener(hover_mq_handler)
  } catch {
    is_hover_capable.value = false
  }
}

function _teardown_hover_capability() {
  try {
    if (!hover_mq || !hover_mq_handler) return
    if (hover_mq.removeEventListener) hover_mq.removeEventListener('change', hover_mq_handler)
    else if (hover_mq.removeListener) hover_mq.removeListener(hover_mq_handler)
  } catch {}
  hover_mq = null
  hover_mq_handler = null
}

onMounted(() => {
  __alive = true
  _setup_hover_capability()
  _sync_file_browser_context()
  window.addEventListener('nisb-current-dir-changed', on_current_dir_changed)
})

onUnmounted(() => {
  __alive = false
  window.removeEventListener('nisb-current-dir-changed', on_current_dir_changed)
  _teardown_hover_capability()
  _crumb_stop_raf()
  _clear_context_menu_timer()
  _clear_current_dir_timer()

  try {
    if (window.__nisb_file_browser_context) {
      delete window.__nisb_file_browser_context
    }
  } catch {}
})
</script>

<style scoped>
.file-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.5rem;
  scrollbar-width: thin;
}

.favorites-block {
  display: grid;
  gap: 0.32rem;
  margin-bottom: 0.12rem;
  padding: 0.45rem;
  border: 1px solid color-mix(in srgb, #d97706 18%, var(--line));
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, #d97706 15%, transparent), transparent 48%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 70%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.08);
}

.favorites-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-width: 0;
  padding: 0 0.05rem 0.12rem;
}

.fav-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.fav-count {
  flex: 0 0 auto;
  min-width: 24px;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.42rem;
  border: 1px solid color-mix(in srgb, #d97706 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, #d97706 9%, transparent);
  color: #d97706;
  font-size: 0.7rem;
  font-weight: 780;
  line-height: 1;
}

.favorites-list {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.16rem;
}

.fav-subtitle {
  padding: 0.04rem 0.1rem;
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1.35;
  letter-spacing: 0.01em;
  overflow-wrap: break-word;
}

.fav-divider {
  height: 1px;
  margin: 0.18rem 0.08rem;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, #d97706 28%, var(--line)),
    transparent
  );
}

.favorite-item {
  position: relative;
  min-width: 0;
  min-height: 30px;
  display: flex;
  align-items: center;
  gap: 0.36rem;
  padding: 0.26rem 0.38rem;
  border: 1px solid transparent;
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 34%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1.35;
  transition:
    background 0.15s var(--ease-smooth, ease),
    border-color 0.15s var(--ease-smooth, ease),
    color 0.15s var(--ease-smooth, ease),
    transform 0.15s var(--ease-smooth, ease);
}

.favorite-item:hover {
  border-color: color-mix(in srgb, #d97706 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, #d97706 12%, transparent),
      color-mix(in srgb, var(--selected-bg) 28%, transparent)
    );
  color: var(--text-main, var(--text));
  transform: translateX(1px);
}

.favorite-item.selected {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, #d97706 10%, transparent)
    );
  color: var(--selected);
  font-weight: 760;
}

.favorite-item.focused:not(.selected) {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 30%, transparent);
  color: var(--text-main, var(--text));
}

.favorite-item.highlighted:not(.selected):not(.focused) {
  border-color: color-mix(in srgb, var(--favorite-highlight-color, #d97706) 24%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--favorite-highlight-color, #d97706) 10%, transparent),
      color-mix(in srgb, var(--editor-bg) 34%, transparent)
    );
  color: var(--text-main, var(--text));
}

.favorite-item.highlighted::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 999px;
  background: var(--favorite-highlight-color, #d97706);
  opacity: 0.76;
  pointer-events: none;
}

.favorite-item.highlighted.selected::before,
.favorite-item.highlighted.focused::before {
  opacity: 0.92;
}

.fav-icon {
  flex: 0 0 auto;
  width: 1.15rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.98rem;
  line-height: 1;
}

.fav-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  overflow-wrap: anywhere;
}

.fav-highlight-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border: 1px solid color-mix(in srgb, var(--favorite-highlight-color, #d97706) 62%, var(--line));
  border-radius: 999px;
  background: var(--favorite-highlight-color, #d97706);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--favorite-highlight-color, #d97706) 12%, transparent);
}

.fav-focus,
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
  opacity: 0.42;
  transition:
    opacity 0.15s ease,
    transform 0.12s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.favorite-item:hover .fav-focus,
.favorite-item:hover .fav-star {
  opacity: 0.9;
}

.fav-focus:hover,
.fav-star:hover {
  transform: scale(1.06);
}

.fav-focus.active {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  opacity: 0.96;
}

.fav-star.active,
.fav-star-small.active {
  border-color: color-mix(in srgb, #d97706 34%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
  opacity: 0.96;
}

.root-row {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
  position: sticky;
  top: 0;
  z-index: 5;
  margin: 0 -0.08rem 0.05rem;
  padding: 0.38rem 0.4rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.root-left {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.crumb-scroll {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.05rem 0;
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1.2;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.crumb-scroll::-webkit-scrollbar {
  height: 0;
}

.crumb-btn {
  flex: 0 0 auto;
  min-height: 24px;
  max-width: 180px;
  display: inline-flex;
  align-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 0.28rem;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 760;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.crumb-btn:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, transparent);
  color: var(--selected);
  text-decoration: none;
}

.crumb-sep {
  flex: 0 0 auto;
  margin: 0 0.08rem;
  color: var(--text-secondary);
  opacity: 0.58;
  user-select: none;
}

.root-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.new-conv-btn {
  min-width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.12s ease;
}

.new-conv-btn:hover {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  color: var(--selected);
}

.new-conv-btn:active {
  transform: translateY(1px);
}

.root-plus-btn,
.collapse-all-btn,
.batch-toggle-btn,
.batch-btn {
  width: 26px;
  height: 26px;
}

.root-plus-btn {
  border-color: color-mix(in srgb, #16a34a 30%, var(--line));
  color: #16a34a;
}

.root-plus-btn:hover {
  border-color: color-mix(in srgb, #16a34a 42%, var(--line));
  background: color-mix(in srgb, #16a34a 10%, transparent);
  color: #16a34a;
}

.batch-pill {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--selected) 26%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 40%, transparent);
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
  white-space: nowrap;
}

.danger-btn {
  border-color: rgba(239, 68, 68, 0.36);
  color: #ef4444;
}

.danger-btn:hover {
  border-color: rgba(239, 68, 68, 0.52);
  background: rgba(239, 68, 68, 0.10);
  color: #ef4444;
}

.empty-tip {
  margin: 0.1rem 0;
  padding: 0.55rem 0.62rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.path-tooltip {
  position: fixed;
  z-index: 2147483647;
  max-width: min(560px, calc(100vw - 24px));
  padding: 0.5rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.42;
  pointer-events: none;
  box-shadow:
    0 16px 34px rgba(0, 0, 0, 0.18),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  white-space: normal;
  overflow-wrap: anywhere;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

@media (max-width: 420px) {
  .file-list {
    padding: 0.42rem;
  }

  .favorites-block {
    padding: 0.4rem;
    border-radius: 13px;
  }

  .root-row {
    align-items: stretch;
    flex-direction: column;
    gap: 0.36rem;
  }

  .root-right {
    width: 100%;
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .batch-pill {
    margin-right: auto;
  }

  .crumb-btn {
    max-width: 140px;
  }
}
</style>
