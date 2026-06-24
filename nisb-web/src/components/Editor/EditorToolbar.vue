<template>
  <button
    v-show="leftCollapsed"
    class="sidebar-toggle-btn left-toggle collapsed"
    @click="$emit('toggle-left-sidebar')"
    :title="left_toggle_title"
    type="button"
  >
    <span class="toggle-icon">│</span>
  </button>

  <div
    ref="noteWrapEl"
    class="note-tab-wrap"
    :class="{ 'actions-open': note_actions_open }"
    @mouseenter="on_note_mouse_enter"
    @mouseleave="on_note_mouse_leave"
    @click="on_note_tab_click"
  >
    <button
      class="tab-mode-btn"
      :class="{
        active: currentView === 'main' && currentMode === 'note',
        'note-saving': currentView === 'main' && currentMode === 'note' && (saving || autoSaving),
        'note-unsaved': currentView === 'main' && currentMode === 'note' && !saving && !autoSaving && saveStatus === 'unsaved'
      }"
      type="button"
      :title="note_tab_title"
    >
      📝 {{ note_tab_label }}
    </button>

    <div v-if="currentView === 'main' && currentMode === 'note'" class="note-hover-spacer" aria-hidden="true"></div>

    <div
      v-if="currentView === 'main' && currentMode === 'note'"
      class="note-hover-actions"
      @click.stop
      @mousedown.stop
      @mouseenter="on_actions_mouse_enter"
      @mouseleave="on_actions_mouse_leave"
    >
      <button
        v-show="!isImageMode && !isCodeMode"
        class="mini-action-btn"
        @click="on_toggle_edit_mode_click"
        :title="note_edit_mode_title"
        type="button"
      >
        <span class="mini-icon">{{ editMode ? '✏️' : '👁️' }}</span>
      </button>

      <button
        class="mini-action-btn"
        :class="{ disabled: !canGoBack }"
        :disabled="!canGoBack"
        @click="on_go_back_click"
        :title="go_back_title"
        type="button"
      >
        <span class="mini-icon">⬅</span>
      </button>

      <button
        class="mini-action-btn"
        :class="{ disabled: !canGoForward }"
        :disabled="!canGoForward"
        @click="on_go_forward_click"
        :title="go_forward_title"
        type="button"
      >
        <span class="mini-icon">➡</span>
      </button>

      <button
        class="mini-action-btn"
        :class="{ disabled: !currentFile || !currentFile.path }"
        :disabled="!currentFile || !currentFile.path"
        @click="on_copy_internal_link_click"
        :title="copy_internal_link_title"
        type="button"
      >
        <span class="mini-icon">{{ internal_link_copied ? '✅' : '🔗' }}</span>
      </button>

      <button
        class="mini-action-btn"
        :class="{ disabled: !currentFile || !currentFile.path }"
        :disabled="!currentFile || !currentFile.path"
        @click="on_toggle_favorite_click"
        :title="favorite_title"
        type="button"
      >
        <span class="mini-icon">{{ is_current_file_favorite ? '★' : '☆' }}</span>
      </button>

      <button
        class="mini-action-btn"
        :class="{ disabled: !currentFile || !currentFile.path }"
        :disabled="!currentFile || !currentFile.path"
        @click="on_focus_dir_click"
        :title="focus_dir_title"
        type="button"
      >
        <span class="mini-icon">◉</span>
      </button>

      <button
        v-show="!isImageMode && !isCodeMode"
        class="mini-action-btn"
        :class="{
          'mini-save-saving': saving || autoSaving,
          'mini-save-saved': !saving && !autoSaving && saveStatus === 'saved',
          'mini-save-unsaved': !saving && !autoSaving && saveStatus === 'unsaved'
        }"
        @click="on_save_note_click"
        :disabled="saving || autoSaving"
        :title="save_note_title"
        type="button"
      >
        <span class="mini-icon">{{ saving || autoSaving ? '💾' : saveStatus === 'saved' ? '✅' : '⏳' }}</span>
      </button>
    </div>
  </div>

  <div
    class="library-tab-wrap"
    @mouseenter="libraryHovering = true"
    @mouseleave="libraryHovering = false"
    @click="$emit('switch-mode', 'library')"
  >
    <button
      class="tab-mode-btn"
      :class="{ active: currentView === 'main' && currentMode === 'library' }"
      type="button"
      :title="library_tab_title"
    >
      🗂️ {{ library_tab_label }}
    </button>

    <div v-if="currentView === 'main' && (currentMode === 'library' || libraryHovering)" class="library-hover-spacer" aria-hidden="true"></div>

    <div v-if="currentView === 'main' && (currentMode === 'library' || libraryHovering)" class="library-hover-actions" @click.stop @mousedown.stop>
      <button
        class="mini-action-btn"
        @click="$emit('toggle-library-dock-right')"
        :title="library_dock_title"
        type="button"
      >
        <span class="mini-icon">{{ libraryDockedRight ? '↩' : '➡' }}</span>
      </button>
    </div>
  </div>

  <div class="feed-tab-selector" @click="$emit('switch-mode', 'feed')">
    <button
      class="tab-mode-btn"
      :class="{ active: currentView === 'main' && currentMode === 'feed' }"
      type="button"
      :title="feed_tab_title"
    >
      📰 {{ feed_tab_label }}
    </button>
  </div>

  <div
    class="chat-selector"
    :class="{ active: currentView === 'main' && currentMode === 'chat' }"
    @click="$emit('switch-mode', 'chat')"
  >
    <ModelSelector
      v-model="localSelectedModel"
      :active="currentView === 'main' && currentMode === 'chat'"
      @click.stop="$emit('switch-mode', 'chat')"
    />
  </div>

  <div class="mode-spacer"></div>

  <button
    v-if="currentView === 'main' && currentMode === 'library' && librarySubMode === 'detail'"
    class="action-btn"
    @click.stop="$emit('back-to-overview')"
    type="button"
    :title="back_to_overview_title"
  >
    ← {{ back_to_overview_label }}
  </button>

  <button
    v-if="currentView === 'main' && currentMode === 'chat'"
    class="action-btn tag-action-btn"
    :class="{ tagged: currentConvLabels.length > 0, 'tag-action-btn-disabled': !currentConvId }"
    @click.stop="$emit('toggle-labels-panel')"
    :title="conversation_labels_title"
    type="button"
  >
    <span>{{ conversation_labels_text }}</span>
  </button>

  <button
    v-if="currentView === 'main' && currentMode === 'note' && !isImageMode && !isCodeMode"
    class="action-btn"
    @click="$emit('create-new-note')"
    type="button"
  >
    ＋ {{ new_note_label }}
  </button>

  <button
    v-if="currentView === 'main' && currentMode === 'note' && currentFile && currentFile.path && !isImageMode && !isCodeMode"
    class="action-btn"
    :class="{ 'status-publishing': publishing }"
    :disabled="publishing"
    @click="$emit('publish-note')"
    type="button"
    :title="publish_note_title"
  >
    <span>{{ publish_note_label }}</span>
  </button>

  <button
    v-if="false"
    type="button"
    class="toolbar-btn brain-btn"
    :class="{ 'status-processing': hebbianProcessing, 'status-done': hebbianStatus === 'done' }"
    :disabled="hebbianProcessing"
    :title="hebbian_title"
    @click="$emit('note-to-brain')"
  >
    <span>{{ hebbian_label }}</span>
  </button>

  <button
    v-show="rightCollapsed"
    class="sidebar-toggle-btn right-toggle collapsed"
    @click="$emit('toggle-right-sidebar')"
    :title="right_toggle_title"
    type="button"
  >
    <span class="toggle-icon">│</span>
  </button>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ModelSelector from '../ModelSelector.vue'

const props = defineProps({
  currentView: { type: String, required: true },
  currentMode: { type: String, required: true },
  editMode: { type: Boolean, required: true },
  currentFile: { type: Object, default: null },
  selectedModel: { type: String, required: true },
  currentConvId: { type: [String, Number, null], default: null },
  currentConvLabels: { type: Array, default: () => [] },
  leftCollapsed: { type: Boolean, default: false },
  rightCollapsed: { type: Boolean, default: false },
  isImageMode: { type: Boolean, default: false },
  isCodeMode: { type: Boolean, default: false },
  saveStatus: { type: String, default: 'saved' },
  saving: { type: Boolean, default: false },
  autoSaving: { type: Boolean, default: false },
  hebbianProcessing: { type: Boolean, default: false },
  hebbianStatus: { type: [Boolean, String], default: false },
  hebbianLastTime: { type: String, default: '' },
  canGoBack: { type: Boolean, default: false },
  canGoForward: { type: Boolean, default: false },
  publishing: { type: Boolean, default: false },
  libraryDockedRight: { type: Boolean, default: false },
  librarySubMode: { type: String, default: 'overview' }
})

const emit = defineEmits([
  'toggle-left-sidebar',
  'toggle-right-sidebar',
  'switch-mode',
  'toggle-edit-mode',
  'toggle-labels-panel',
  'create-new-note',
  'save-note',
  'note-to-brain',
  'go-back-file',
  'go-forward-file',
  'update:selected-model',
  'publish-note',
  'toggle-library-dock-right',
  'back-to-overview'
])

const { t } = useI18n()

const libraryHovering = ref(false)
const localSelectedModel = ref(props.selectedModel)

const noteWrapEl = ref(null)
const note_actions_open = ref(false)
const is_touch_like = ref(false)

let note_close_timer = null
let actions_hovering = false

const current_toolbar_namespace = computed(() => {
  switch (props.currentMode) {
    case 'library':
      return 'library.center.toolbar'
    case 'feed':
      return 'feed.toolbar'
    case 'chat':
      return 'chat.toolbar'
    default:
      return 'note.toolbar'
  }
})

function toolbar_t(key, params = {}) {
  return t(`${current_toolbar_namespace.value}.${key}`, params)
}

const left_toggle_title = computed(() => toolbar_t('expandLeftSidebar'))
const right_toggle_title = computed(() => toolbar_t('expandRightSidebar'))

const note_tab_title = computed(() => t('note.toolbar.tab'))
const note_tab_label = computed(() => t('note.toolbar.tab'))

const note_edit_mode_title = computed(() => {
  if (props.currentFile?.name) return props.currentFile.name
  return props.editMode ? t('note.toolbar.switchToEdit') : t('note.toolbar.switchToPreview')
})

const library_tab_title = computed(() => t('library.center.toolbar.tab'))
const library_tab_label = computed(() => t('library.center.toolbar.tab'))

const library_dock_title = computed(() => {
  return props.libraryDockedRight
    ? t('library.center.toolbar.restoreToCenter')
    : t('library.center.toolbar.dockToRight')
})

const feed_tab_title = computed(() => t('feed.toolbar.tabTitle'))
const feed_tab_label = computed(() => t('feed.toolbar.tab'))

const back_to_overview_title = computed(() => t('library.center.toolbar.backToOverviewTitle'))
const back_to_overview_label = computed(() => t('library.center.toolbar.backToOverview'))

const conversation_labels_title = computed(() => {
  return props.currentConvId
    ? t('chat.toolbar.manageLabels')
    : t('chat.toolbar.selectConversationFirst')
})

const conversation_labels_text = computed(() => {
  if (props.currentConvLabels.length === 0) {
    return `🏷 ${t('chat.toolbar.labels')}`
  }
  return `🏷 ${props.currentConvLabels.join(t('chat.toolbar.labelsSeparator'))}`
})

const new_note_label = computed(() => t('note.toolbar.newNote'))

const publish_note_title = computed(() => t('note.toolbar.publishCurrentNoteToFeed'))
const publish_note_label = computed(() => {
  return props.publishing
    ? `📤 ${t('note.toolbar.publishing')}`
    : `📤 ${t('note.toolbar.publish')}`
})

const hebbian_title = computed(() => {
  return props.hebbianStatus === 'done'
    ? t('note.toolbar.noteToBrainLastTime', { time: props.hebbianLastTime })
    : t('note.toolbar.noteToBrainHint')
})

const hebbian_label = computed(() => {
  if (props.hebbianProcessing) return `🧠 ${t('note.toolbar.noteToBrainProcessing')}`
  if (props.hebbianStatus === 'done') return `🧠 ${t('note.toolbar.noteToBrainDone')}`
  return `🧠 ${t('note.toolbar.noteToBrain')}`
})

function _clear_note_close_timer() {
  if (note_close_timer) {
    clearTimeout(note_close_timer)
    note_close_timer = null
  }
}

function _detect_touch_like() {
  try {
    const mql = window.matchMedia && window.matchMedia('(hover: none)')
    const hover_none = !!(mql && mql.matches)
    const touch_points = Number(navigator.maxTouchPoints || 0) > 0
    is_touch_like.value = hover_none || touch_points
  } catch {
    is_touch_like.value = false
  }
}

function open_note_actions() {
  note_actions_open.value = true
  _clear_note_close_timer()
}

function close_note_actions() {
  note_actions_open.value = false
  _clear_note_close_timer()
}

function schedule_close_note_actions_desktop() {
  _clear_note_close_timer()
  note_close_timer = setTimeout(() => {
    if (actions_hovering) return
    note_actions_open.value = false
    note_close_timer = null
  }, 3000)
}

function on_note_mouse_enter() {
  if (is_touch_like.value) return
  if (props.currentView !== 'main' || props.currentMode !== 'note') return
  open_note_actions()
}

function on_note_mouse_leave() {
  if (is_touch_like.value) return
  if (props.currentView !== 'main' || props.currentMode !== 'note') return
  schedule_close_note_actions_desktop()
}

function on_actions_mouse_enter() {
  if (is_touch_like.value) return
  actions_hovering = true
  _clear_note_close_timer()
}

function on_actions_mouse_leave() {
  if (is_touch_like.value) return
  actions_hovering = false
  if (props.currentView !== 'main' || props.currentMode !== 'note') return
  schedule_close_note_actions_desktop()
}

function _event_path_contains(el, evt) {
  try {
    if (!el || !evt) return false
    const path = typeof evt.composedPath === 'function' ? evt.composedPath() : null
    if (Array.isArray(path)) return path.includes(el)
    return el.contains(evt.target)
  } catch {
    return false
  }
}

function on_global_pointer_down(evt) {
  if (!is_touch_like.value) return
  if (!note_actions_open.value) return
  const wrap = noteWrapEl.value
  if (!wrap) return
  if (_event_path_contains(wrap, evt)) return
  close_note_actions()
}

function on_note_tab_click() {
  if (props.currentView !== 'main' || props.currentMode !== 'note') {
    close_note_actions()
    emit('switch-mode', 'note')

    if (!is_touch_like.value) {
      open_note_actions()
      schedule_close_note_actions_desktop()
    }

    return
  }

  if (note_actions_open.value) {
    close_note_actions()
    return
  }

  open_note_actions()

  if (!is_touch_like.value) {
    schedule_close_note_actions_desktop()
  }
}

const platform_is_mac = ref(false)
const shortcut_back_hint = computed(() => (platform_is_mac.value ? '⌘ + ⌥ + ←' : 'Ctrl + Alt + ←'))
const shortcut_forward_hint = computed(() => (platform_is_mac.value ? '⌘ + ⌥ + →' : 'Ctrl + Alt + →'))

const go_back_title = computed(() => {
  return t('note.toolbar.goBackWithShortcut', { shortcut: shortcut_back_hint.value })
})

const go_forward_title = computed(() => {
  return t('note.toolbar.goForwardWithShortcut', { shortcut: shortcut_forward_hint.value })
})

const internal_link_copied = ref(false)
let internal_link_copied_timer = null

const copy_internal_link_title = computed(() => {
  return internal_link_copied.value
    ? t('note.toolbar.copiedInternalLink')
    : t('note.toolbar.copyInternalLink')
})

function escape_markdown_link_text(name) {
  return String(name || '').replace(/[\\[\]]/g, '\\$&')
}

function guess_basename(path) {
  const p = String(path || '').replace(/\\/g, '/')
  const parts = p.split('/').filter(Boolean)
  return parts.length ? parts[parts.length - 1] : t('note.toolbar.defaultDocumentName')
}

function normalize_nisb_path(p) {
  if (!p) return ''
  return String(p).trim().replace(/\\/g, '/').replace(/\/+/g, '/').replace(/^\/+/, '')
}

function build_current_doc_internal_url() {
  const path_raw = props.currentFile?.path
  if (!path_raw) return ''

  const path = normalize_nisb_path(path_raw)
  const ws = props.currentFile?.ws ? String(props.currentFile.ws) : 'workspace_work'
  return `nisb://file?ws=${encodeURIComponent(ws)}&type=file&path=${encodeURIComponent(path)}`
}

function build_current_doc_internal_markdown() {
  const url = build_current_doc_internal_url()
  if (!url) return ''

  const display_name_raw = props.currentFile?.name ? String(props.currentFile.name) : guess_basename(props.currentFile?.path)
  const display_name = escape_markdown_link_text(display_name_raw)
  return `[${display_name}](${url})`
}

async function copy_current_doc_internal_link() {
  const md = build_current_doc_internal_markdown()
  if (!md) return

  internal_link_copied.value = false
  if (internal_link_copied_timer) clearTimeout(internal_link_copied_timer)

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(md)
    } else {
      const ta = document.createElement('textarea')
      ta.value = md
      ta.setAttribute('readonly', 'true')
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      ta.style.top = '-9999px'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }

    internal_link_copied.value = true
    internal_link_copied_timer = setTimeout(() => {
      internal_link_copied.value = false
      internal_link_copied_timer = null
    }, 1200)
  } catch {
    internal_link_copied.value = false
  }
}

const favorite_map = ref({})

function on_favorites_snapshot(e) {
  const detail = e?.detail || {}
  const map = detail.favorite_map || {}
  favorite_map.value = map && typeof map === 'object' ? map : {}
}

const is_current_file_favorite = computed(() => {
  const p = normalize_nisb_path(props.currentFile?.path)
  if (!p) return false
  return !!favorite_map.value[p]
})

const favorite_title = computed(() => {
  return is_current_file_favorite.value
    ? t('note.toolbar.removeFromFavorites')
    : t('note.toolbar.addToFavorites')
})

function toggle_current_file_favorite() {
  const p = normalize_nisb_path(props.currentFile?.path)
  if (!p) return
  window.dispatchEvent(new CustomEvent('nisb-favorites-toggle', { detail: { path: p, type: 'file' } }))
}

function get_parent_dir(path) {
  const p = normalize_nisb_path(path)
  if (!p) return ''
  const idx = p.lastIndexOf('/')
  if (idx <= 0) return ''
  return p.slice(0, idx)
}

const focus_dir_title = computed(() => {
  const p = normalize_nisb_path(props.currentFile?.path)
  if (!p) return t('note.toolbar.focusCurrentDirectory')
  const parent = get_parent_dir(p)
  return parent
    ? t('note.toolbar.focusDirectoryTo', { path: parent })
    : t('note.toolbar.clearDirectoryFocus')
})

function ensure_left_sidebar_open_and_files_active() {
  window.dispatchEvent(
    new CustomEvent('nisb-left-sidebar-switch-tab', {
      detail: {
        tab: 'files',
        source: 'editor_toolbar_focus_dir'
      }
    })
  )

  if (props.leftCollapsed) {
    emit('toggle-left-sidebar')
  }
}

function focus_current_doc_parent_dir() {
  const p = normalize_nisb_path(props.currentFile?.path)
  if (!p) return

  ensure_left_sidebar_open_and_files_active()

  const parent = get_parent_dir(p)

  if (parent) {
    window.dispatchEvent(new CustomEvent('nisb_file_focus_root', { detail: { path: parent } }))
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('note.toolbar.focusedDirectoryToast', { path: parent }),
          type: 'info'
        }
      })
    )
    return
  }

  window.dispatchEvent(new CustomEvent('nisb_file_clear_focus_root', { detail: {} }))
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: {
        message: t('note.toolbar.clearedDirectoryToast'),
        type: 'info'
      }
    })
  )
}

function close_after_action_if_touch(opts = {}) {
  if (!is_touch_like.value) return
  const keep_open = !!opts.keep_open
  if (keep_open) return
  close_note_actions()
}

function on_toggle_edit_mode_click() {
  emit('toggle-edit-mode')
  close_after_action_if_touch()
}

function on_go_back_click() {
  if (!props.canGoBack) return
  emit('go-back-file')
  close_after_action_if_touch({ keep_open: true })
}

function on_go_forward_click() {
  if (!props.canGoForward) return
  emit('go-forward-file')
  close_after_action_if_touch({ keep_open: true })
}

async function on_copy_internal_link_click() {
  await copy_current_doc_internal_link()
  close_after_action_if_touch()
}

function on_toggle_favorite_click() {
  toggle_current_file_favorite()
  close_after_action_if_touch()
}

function on_focus_dir_click() {
  focus_current_doc_parent_dir()
  close_after_action_if_touch()
}

const save_note_title = computed(() => {
  if (props.saving || props.autoSaving) return t('note.toolbar.saveSaving')
  if (props.saveStatus === 'saved') return t('note.toolbar.saveSaved')
  return t('note.toolbar.savePending')
})

function on_save_note_click() {
  emit('save-note')
  close_after_action_if_touch()
}

function is_editable_target(el) {
  if (!el) return false
  const t = el
  const tag = (t.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
  if (t.isContentEditable) return true
  if (typeof t.closest === 'function') {
    if (t.closest('[contenteditable="true"]')) return true
    if (t.closest('.cm-editor')) return true
    if (t.closest('.monaco-editor')) return true
    if (t.closest('[role="textbox"]')) return true
  }
  return false
}

function on_global_keydown(e) {
  if (!e) return
  if (e.defaultPrevented) return
  if (e.isComposing) return
  if (props.currentView !== 'main' || props.currentMode !== 'note') return
  if (is_editable_target(e.target)) return
  if (typeof e.getModifierState === 'function' && e.getModifierState('AltGraph')) return

  const is_arrow_left = e.key === 'ArrowLeft'
  const is_arrow_right = e.key === 'ArrowRight'
  if (!is_arrow_left && !is_arrow_right) return

  const hit_windows_linux = e.ctrlKey && e.altKey
  const hit_macos = e.metaKey && e.altKey
  const hit = hit_windows_linux || hit_macos
  if (!hit) return

  e.preventDefault()
  e.stopPropagation()

  if (is_arrow_left) {
    if (props.canGoBack) emit('go-back-file')
    return
  }
  if (is_arrow_right) {
    if (props.canGoForward) emit('go-forward-file')
  }
}

onMounted(() => {
  window.addEventListener('nisb-favorites-snapshot', on_favorites_snapshot)

  const ua = navigator.userAgent || ''
  const platform = navigator.platform || ''
  platform_is_mac.value = /Mac|iPhone|iPad|iPod/i.test(platform) || /Macintosh/i.test(ua)

  _detect_touch_like()

  window.addEventListener('keydown', on_global_keydown, { capture: true })
  window.addEventListener('pointerdown', on_global_pointer_down, { capture: true })
})

onUnmounted(() => {
  window.removeEventListener('nisb-favorites-snapshot', on_favorites_snapshot)
  window.removeEventListener('keydown', on_global_keydown, { capture: true })
  window.removeEventListener('pointerdown', on_global_pointer_down, { capture: true })
  _clear_note_close_timer()
})

watch(
  () => props.selectedModel,
  (val) => {
    if (val !== localSelectedModel.value) localSelectedModel.value = val
  }
)

watch(localSelectedModel, (val) => {
  emit('update:selected-model', val)
})

watch(
  () => [props.currentView, props.currentMode],
  ([view, mode]) => {
    if (view !== 'main' || mode !== 'note') close_note_actions()
  }
)
</script>

<style scoped>
.sidebar-toggle-btn,
.tab-mode-btn,
.mini-action-btn,
.action-btn {
  --toolbar-control-height: 32px;
  --toolbar-radius: 12px;
  --toolbar-bg:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 34%, transparent)
    );
  --toolbar-bg-hover:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  --toolbar-bg-active:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 12%, transparent)
    );
  --toolbar-ring: color-mix(in srgb, var(--selected) 12%, transparent);
  --toolbar-border: color-mix(in srgb, var(--line) 84%, transparent);
  --toolbar-border-hover: color-mix(in srgb, var(--selected) 28%, var(--line));
  --toolbar-border-active: color-mix(in srgb, var(--selected) 58%, var(--line));

  height: var(--toolbar-control-height);
  min-height: var(--toolbar-control-height);
  max-height: var(--toolbar-control-height);
  box-sizing: border-box;

  border: 1px solid var(--toolbar-border);
  border-radius: var(--toolbar-radius);
  background: var(--toolbar-bg);
  color: var(--text-secondary);

  cursor: pointer;
  font-family: inherit;
  line-height: 1;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 1px 2px rgba(0, 0, 0, 0.035);

  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.sidebar-toggle-btn:hover,
.sidebar-toggle-btn:focus-visible,
.tab-mode-btn:hover,
.tab-mode-btn:focus-visible,
.mini-action-btn:hover:not(:disabled),
.mini-action-btn:focus-visible:not(:disabled),
.action-btn:hover:not(:disabled),
.action-btn:focus-visible:not(:disabled) {
  border-color: var(--toolbar-border-hover);
  background: var(--toolbar-bg-hover);
  color: var(--text-main, var(--text));
  box-shadow:
    0 0 0 2px var(--toolbar-ring),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.sidebar-toggle-btn:active,
.tab-mode-btn:active,
.mini-action-btn:active:not(:disabled),
.action-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.sidebar-toggle-btn {
  width: 32px;
  min-width: 32px;
  max-width: 32px;
  padding: 0;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  flex: 0 0 auto;
}

.toggle-icon {
  font-size: 14px;
  font-weight: 520;
  line-height: 1;
  opacity: 0.86;
}

.left-toggle {
  margin-right: 0.35rem;
}

.right-toggle {
  margin-left: 0.25rem;
}

.note-tab-wrap,
.library-tab-wrap,
.library-tab-selector,
.feed-tab-selector,
.chat-selector {
  --toolbar-control-height: 32px;
  --toolbar-radius: 12px;
  --toolbar-bg:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 34%, transparent)
    );
  --toolbar-bg-hover:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  --toolbar-bg-active:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 12%, transparent)
    );
  --toolbar-ring: color-mix(in srgb, var(--selected) 12%, transparent);
  --toolbar-border: color-mix(in srgb, var(--line) 84%, transparent);
  --toolbar-border-hover: color-mix(in srgb, var(--selected) 28%, var(--line));
  --toolbar-border-active: color-mix(in srgb, var(--selected) 58%, var(--line));

  position: relative;
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  min-width: max-content;
}

.note-tab-wrap {
  --note-hover-space: 16.2rem;
}

.library-tab-wrap {
  --library-hover-space: 3.25rem;
}

.tab-mode-btn {
  min-width: max-content;
  max-width: none;
  padding: 0 0.78rem;

  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.38rem;

  flex: 0 0 auto;

  font-size: 0.82rem;
  font-weight: 760;
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
}

.tab-mode-btn.active {
  border-color: var(--toolbar-border-active);
  background: var(--toolbar-bg-active);
  color: var(--selected);
  font-weight: 820;
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.10);
}

.tab-mode-btn.note-unsaved {
  border-color: rgba(217, 119, 6, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.13),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #d97706;
}

.tab-mode-btn.note-unsaved:hover,
.tab-mode-btn.note-unsaved:focus-visible {
  border-color: rgba(217, 119, 6, 0.76);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.17),
      color-mix(in srgb, var(--editor-bg) 68%, transparent)
    );
  color: #d97706;
  box-shadow:
    0 0 0 3px rgba(217, 119, 6, 0.12),
    0 10px 22px rgba(0, 0, 0, 0.09);
}

.tab-mode-btn.note-saving {
  border-color: rgba(37, 99, 235, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(37, 99, 235, 0.13),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #2563eb;
  animation: toolbarPulse 1.5s infinite;
}

.note-hover-spacer,
.library-hover-spacer {
  width: 0;
  flex: 0 0 auto;
  transition: width 0.15s ease;
}

.note-tab-wrap.actions-open .note-hover-spacer {
  width: var(--note-hover-space);
}

.library-tab-wrap:hover .library-hover-spacer,
.library-tab-wrap:has(.library-hover-actions:hover) .library-hover-spacer {
  width: var(--library-hover-space);
}

.note-hover-actions,
.library-hover-actions {
  position: absolute;
  top: 50%;

  display: inline-flex;
  align-items: center;
  gap: 0.35rem;

  padding: 3px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 9%, transparent), transparent 44%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 90%, transparent)
    );
  box-shadow:
    0 18px 42px rgba(0, 0, 0, 0.18),
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);

  opacity: 0;
  pointer-events: none;
  transform: translateY(-50%) translateX(-4px);

  transition:
    opacity 0.15s ease,
    transform 0.15s ease,
    border-color 0.15s ease;
  z-index: 30;
}

.note-hover-actions {
  left: calc(100% - var(--note-hover-space));
}

.library-hover-actions {
  left: calc(100% - var(--library-hover-space));
}

.note-tab-wrap.actions-open .note-hover-actions,
.library-tab-wrap:hover .library-hover-actions,
.library-hover-actions:hover {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(-50%) translateX(0);
}

.note-tab-wrap.actions-open .note-hover-actions,
.library-tab-wrap:hover .library-hover-actions {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
}

.mini-action-btn {
  width: 30px;
  min-width: 30px;
  max-width: 30px;
  height: 30px;
  min-height: 30px;
  max-height: 30px;
  padding: 0;
  border-radius: 11px;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  flex: 0 0 auto;
}

.mini-action-btn:disabled,
.mini-action-btn.disabled {
  opacity: 0.48;
  cursor: not-allowed;
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

.mini-icon {
  font-size: 14px;
  line-height: 1;
}

.mini-action-btn.mini-save-unsaved {
  border-color: rgba(217, 119, 6, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.13),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
  color: #d97706;
}

.mini-action-btn.mini-save-unsaved:hover:not(:disabled),
.mini-action-btn.mini-save-unsaved:focus-visible:not(:disabled) {
  border-color: rgba(217, 119, 6, 0.78);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.17),
      color-mix(in srgb, var(--editor-bg) 66%, transparent)
    );
  color: #d97706;
  box-shadow:
    0 0 0 3px rgba(217, 119, 6, 0.12),
    0 10px 22px rgba(0, 0, 0, 0.09);
}

.mini-action-btn.mini-save-saved {
  border-color: rgba(22, 163, 74, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(22, 163, 74, 0.12),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #16a34a;
}

.mini-action-btn.mini-save-saving {
  border-color: rgba(37, 99, 235, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(37, 99, 235, 0.12),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #2563eb;
  animation: toolbarPulse 1.5s infinite;
}

.mode-spacer {
  flex: 1 1 auto;
  min-width: 0.5rem;
}

.action-btn {
  min-width: max-content;
  max-width: 18rem;
  padding: 0 0.78rem;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  flex: 0 0 auto;

  font-size: 0.82rem;
  font-weight: 760;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-btn:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.action-btn.status-processing,
.action-btn.status-publishing {
  border-color: rgba(37, 99, 235, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(37, 99, 235, 0.12),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #2563eb;
  animation: toolbarPulse 1.5s infinite;
}

.action-btn.status-done {
  border-color: rgba(22, 163, 74, 0.52);
  background:
    linear-gradient(
      135deg,
      rgba(22, 163, 74, 0.12),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #16a34a;
}

.tag-action-btn {
  max-width: min(18rem, 34vw);
}

.tag-action-btn span {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
}

.tag-action-btn.tagged {
  border-color: var(--toolbar-border-active);
  background: var(--toolbar-bg-active);
  color: var(--selected);
  font-weight: 820;
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.10);
}

.tag-action-btn-disabled {
  opacity: 0.58;
}

.chat-selector {
  min-width: 0;
}

.chat-selector :deep(.model-selector) {
  width: 100%;
  min-width: 0;
}

.chat-selector :deep(.model-btn) {
  height: var(--toolbar-control-height) !important;
  min-height: var(--toolbar-control-height) !important;
  max-height: var(--toolbar-control-height) !important;
  border-radius: var(--toolbar-radius) !important;
  font-size: 0.82rem;
  font-weight: 760;
}

.chat-selector :deep(.model-btn:hover),
.chat-selector :deep(.model-btn:focus-visible) {
  border-color: var(--toolbar-border-hover) !important;
  background: var(--toolbar-bg-hover) !important;
  color: var(--text-main, var(--text)) !important;
  box-shadow:
    0 0 0 2px var(--toolbar-ring),
    0 8px 18px rgba(0, 0, 0, 0.08) !important;
}

.chat-selector.active :deep(.model-btn),
.chat-selector :deep(.model-btn.active),
.chat-selector :deep(.model-btn.open) {
  border-color: var(--toolbar-border-active) !important;
  background: var(--toolbar-bg-active) !important;
  color: var(--selected) !important;
  font-weight: 820;
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.10) !important;
}

@media (max-width: 960px) {
  .tab-mode-btn,
  .action-btn {
    padding-inline: 0.62rem;
  }

  .tag-action-btn {
    max-width: 12rem;
  }

  .note-tab-wrap {
    --note-hover-space: 14.2rem;
  }
}

@media (max-width: 720px) {
  .tab-mode-btn,
  .action-btn {
    padding-inline: 0.54rem;
    font-size: 0.78rem;
  }

  .chat-selector :deep(.model-btn) {
    font-size: 0.78rem;
  }

  .note-tab-wrap {
    --note-hover-space: 13rem;
  }

  .mini-action-btn {
    width: 29px;
    min-width: 29px;
    max-width: 29px;
  }

  .tag-action-btn {
    max-width: 10rem;
  }
}

@keyframes toolbarPulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.68;
  }
}
</style>

