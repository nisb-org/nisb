<template>
  <div class="sidebar">
    <LeftSidebarHeader
      :active_tab="active_tab"
      :show_file_actions="active_tab === 'files'"
      @switch_tab="(t) => (active_tab = t)"
      @open_search="show_search_panel = true"
      @trigger_upload="trigger_upload"
      @trigger_dir_upload="trigger_dir_upload"
      @collapse="collapse_sidebar"
    />

    <input
      ref="file_input"
      type="file"
      multiple
      accept=".txt,.md,.json,.py,.js,.html,.css,.yaml,.yml,.sh,.env,.pdf,.epub,.mobi,.azw3,.djvu,.chm,.zip,.rar,.7z,.jpg,.jpeg,.png,.gif,.bmp,.webp"
      style="display: none"
      @change="handle_file_upload"
    />
    <input ref="dir_input" type="file" webkitdirectory multiple style="display: none" @change="handle_dir_upload" />

    <div class="tab-content">
      <ConversationsPanel v-if="active_tab === 'conversations'" />
      <LibraryList v-if="active_tab === 'libraries'" ref="library_list_ref" @show-context-menu="show_context_menu" />
      <TimelineView v-if="active_tab === 'timeline'" />
      <FileBrowser v-if="active_tab === 'files'" :workspace-id="current_workspace" @show-context-menu="show_context_menu" />
      <RssPanel v-if="active_tab === 'rss'" @show-context-menu="show_context_menu" />
    </div>

    <LeftSidebarWorkspaceBar
      :workspaces="workspaces"
      :current_workspace="current_workspace"
      @change_workspace="on_workspace_change"
      @open_settings="open_settings"
    />

    <SettingsModal
      :open="settings_modal_open"
      :workspace-id="current_workspace"
      :workspace-name="current_workspace_name"
      @close="settings_modal_open = false"
    />

    <LeftSidebarContextMenu
      :visible="context_menu.visible"
      :context_menu="context_menu"
      :visible_extensions="visible_extensions"
      :is_binary_file="is_binary_file"
      :is_pdf_file="is_pdf_file"
      :is_epub_file="is_epub_file"
      :is_image_file="is_image_file"
      @action="on_context_menu_action"
      @close="hide_context_menu"
    />

    <SearchPanel :visible="show_search_panel" @close="show_search_panel = false" />

    <FileSendToLibraryDialog
      :visible="send_to_library_dialog.visible"
      :source-path="send_to_library_dialog.sourcePath"
      :source-name="send_to_library_dialog.sourceName"
      :source-type="send_to_library_dialog.sourceType"
      @close="send_to_library_dialog.visible = false"
      @sent="handle_send_to_library_sent"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../composables/useMCP'

import SearchPanel from './LeftSidebar/SearchPanel.vue'
import LibraryList from './LeftSidebar/LibraryList.vue'
import TimelineView from './LeftSidebar/TimelineView.vue'
import ConversationsPanel from './LeftSidebar/ConversationsPanel.vue'
import FileBrowser from './LeftSidebar/FileBrowser.vue'
import FileSendToLibraryDialog from './LeftSidebar/FileSendToLibraryDialog.vue'
import RssPanel from './LeftSidebar/RssPanel.vue'
import SettingsModal from './LeftSidebar/SettingsModal.vue'

import LeftSidebarHeader from './LeftSidebar/LeftSidebarHeader.vue'
import LeftSidebarWorkspaceBar from './LeftSidebar/LeftSidebarWorkspaceBar.vue'
import LeftSidebarContextMenu from './LeftSidebar/LeftSidebarContextMenu.vue'

import { use_left_sidebar_context_menu } from '../composables/left_sidebar/use_left_sidebar_context_menu'
import { use_left_sidebar_workspaces } from '../composables/left_sidebar/use_left_sidebar_workspaces'
import { use_left_sidebar_uploads } from '../composables/left_sidebar/use_left_sidebar_uploads'
import { use_left_sidebar_actions } from '../composables/left_sidebar/use_left_sidebar_actions'
import { normalizeToolResponse, pickDataValue } from '../composables/left_sidebar/actions/response_normalizer'

const { t } = useI18n()
const { callTool: call_tool } = useMCP()

const WORKSPACE_UI_EVENT_DELAY_MS = 20
const WORKSPACE_UI_EVENT_SPLIT_GAP_MS = 28
const WORKSPACE_UI_REFRESH_DEBOUNCE_MS = 96
const WORKSPACE_UI_IDLE_TIMEOUT_MS = 1200
const WORKSPACE_REVEAL_RETRY_DELAYS_MS = [0, 180, 520]

let __alive = true
let __workspace_switch_seq = 0
let __workspace_switch_inflight = false
let __workspace_switch_pending_job = null

let __workspace_refresh_timer = null
let __workspace_refresh_idle_id = null

const __async_event_timers = new Set()
const __reveal_timers = new Set()
const __pending_intent_timers = new Set()

function _request_idle(cb, { timeout = 800 } = {}) {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    return window.requestIdleCallback(cb, { timeout })
  }
  return window.setTimeout(() => cb({ didTimeout: true, timeRemaining: () => 0 }), 0)
}

function _cancel_idle(id) {
  try {
    if (typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') window.cancelIdleCallback(id)
    else clearTimeout(id)
  } catch {}
}

function _set_workspace_switch_state(partial = {}) {
  try {
    const prev = window.__nisb_workspace_switch_state && typeof window.__nisb_workspace_switch_state === 'object'
      ? window.__nisb_workspace_switch_state
      : {}
    window.__nisb_workspace_switch_state = {
      ...prev,
      ...partial
    }
  } catch {}
}

function _clear_workspace_refresh_queue() {
  if (__workspace_refresh_timer) clearTimeout(__workspace_refresh_timer)
  __workspace_refresh_timer = null

  if (__workspace_refresh_idle_id !== null) {
    _cancel_idle(__workspace_refresh_idle_id)
    __workspace_refresh_idle_id = null
  }
}

function _clear_async_event_timers() {
  try {
    for (const id of __async_event_timers) clearTimeout(id)
  } catch {}
  __async_event_timers.clear()
}

function _clear_reveal_timers() {
  try {
    for (const id of __reveal_timers) clearTimeout(id)
  } catch {}
  __reveal_timers.clear()
}

function _clear_pending_intent_timers() {
  try {
    for (const id of __pending_intent_timers) clearTimeout(id)
  } catch {}
  __pending_intent_timers.clear()
}

function _schedule_pending_intent_retry(delay) {
  const timer = setTimeout(() => {
    __pending_intent_timers.delete(timer)
    void consume_pending_left_sidebar_intent()
  }, Math.max(0, Number(delay || 0)))
  __pending_intent_timers.add(timer)
}

function _schedule_workspace_ui_refresh(reason = 'workspace-switch', seq = 0) {
  _clear_workspace_refresh_queue()

  __workspace_refresh_timer = setTimeout(() => {
    __workspace_refresh_timer = null

    __workspace_refresh_idle_id = _request_idle(
      () => {
        __workspace_refresh_idle_id = null
        if (!__alive) return
        if (seq && seq !== __workspace_switch_seq) return

        void _dispatch_window_event_async(
          'nisb-favorites-refresh',
          { reason },
          { seq, delay: 0 }
        )

        void _dispatch_window_event_async(
          'nisb-file-tree-refresh',
          { reason },
          { seq, delay: WORKSPACE_UI_EVENT_SPLIT_GAP_MS }
        )
      },
      { timeout: WORKSPACE_UI_IDLE_TIMEOUT_MS }
    )
  }, WORKSPACE_UI_REFRESH_DEBOUNCE_MS)
}

function _dispatch_window_event_async(event_name, detail = {}, { seq = 0, delay = WORKSPACE_UI_EVENT_DELAY_MS } = {}) {
  return new Promise((resolve) => {
    const timer = setTimeout(async () => {
      __async_event_timers.delete(timer)

      if (!__alive) {
        resolve(false)
        return
      }

      if (seq && seq !== __workspace_switch_seq) {
        resolve(false)
        return
      }

      window.dispatchEvent(
        new CustomEvent(event_name, {
          detail
        })
      )

      await nextTick()
      resolve(true)
    }, Math.max(0, Number(delay || 0)))

    __async_event_timers.add(timer)
  })
}

function normalize_sidebar_tab(value) {
  const raw = String(value || '').trim().toLowerCase()
  if (!raw) return ''
  if (raw === 'libraries' || raw === 'library') return 'libraries'
  if (raw === 'files' || raw === 'file') return 'files'
  if (raw === 'timeline') return 'timeline'
  if (raw === 'rss' || raw === 'feed' || raw === 'feeds') return 'rss'
  if (raw === 'conversations' || raw === 'conversation' || raw === 'chat') return 'conversations'
  return ''
}

function read_pending_left_sidebar_intent() {
  try {
    const v = window.__nisb_pending_left_sidebar_intent
    return v && typeof v === 'object' ? v : null
  } catch {
    return null
  }
}

function clear_pending_left_sidebar_intent() {
  try {
    delete window.__nisb_pending_left_sidebar_intent
  } catch {}
}

const initial_pending_intent = read_pending_left_sidebar_intent()
const initial_pending_tab = normalize_sidebar_tab(initial_pending_intent?.tab || '')

const active_tab = ref(initial_pending_tab || 'conversations')
const show_search_panel = ref(false)

const library_list_ref = ref(null)

const send_to_library_dialog = ref({
  visible: false,
  sourcePath: '',
  sourceName: '',
  sourceType: 'file'
})

function collapse_sidebar() {
  window.dispatchEvent(new CustomEvent('toggle-left-sidebar'))
}

function dispatch_toast(message, type = 'success') {
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message, type }
    })
  )
}

function switch_left_sidebar_tab(tab, opts = {}) {
  const next_tab = normalize_sidebar_tab(tab)
  if (!next_tab) return
  active_tab.value = next_tab

  if (opts.refreshFiles && next_tab === 'files') {
    _schedule_workspace_ui_refresh('switch-left-sidebar-tab', 0)
  }
}

function normalize_focus_root_client(value) {
  let s = String(value || '').trim().replace(/\\\\/g, '/')
  while (s.includes('//')) s = s.replace(/\/{2,}/g, '/')
  s = s.replace(/^\/+|\/+$/g, '')
  const parts = s
    .split('/')
    .map((x) => String(x || '').trim())
    .filter((x) => x && x !== '.' && x !== '..')
  return parts.join('/')
}

function normalize_relative_path_client(value) {
  let s = String(value || '').trim().replace(/\\\\/g, '/')
  while (s.includes('//')) s = s.replace(/\/{2,}/g, '/')
  s = s.replace(/^\/+|\/+$/g, '')
  const parts = s
    .split('/')
    .map((x) => String(x || '').trim())
    .filter((x) => x && x !== '.' && x !== '..')
  return parts.join('/')
}

function join_rel_path(a, b) {
  const aa = normalize_relative_path_client(a)
  const bb = normalize_relative_path_client(b)
  if (!aa) return bb
  if (!bb) return aa
  return `${aa}/${bb}`
}

async function persist_focus_root_to_ui(path, label = '', workspace_id = '', opts = {}) {
  const focus_root = normalize_focus_root_client(path)
  if (!focus_root) return false

  const seq = Number(opts?.seq || 0)
  const refresh = opts?.refresh === true
  const refresh_reason = String(opts?.refresh_reason || 'persist-focus-root').trim() || 'persist-focus-root'

  const ok = await _dispatch_window_event_async(
    'nisb_file_focus_root',
    {
      path: focus_root,
      label: String(label || '').trim(),
      source: 'room_workspace_context',
      workspace_id: String(workspace_id || '').trim()
    },
    { seq }
  )

  if (ok && refresh) {
    _schedule_workspace_ui_refresh(refresh_reason, seq)
  }

  return ok
}

async function clear_focus_root_from_ui(opts = {}) {
  const seq = Number(opts?.seq || 0)
  const refresh = opts?.refresh === true
  const refresh_reason = String(opts?.refresh_reason || 'clear-focus-root').trim() || 'clear-focus-root'

  const ok = await _dispatch_window_event_async(
    'nisb_file_clear_focus_root',
    {
      source: 'room_workspace_context'
    },
    { seq }
  )

  if (ok && refresh) {
    _schedule_workspace_ui_refresh(refresh_reason, seq)
  }

  return ok
}

async function apply_workspace_snapshot_to_ui(workspace_id, opts = {}) {
  const wid = String(workspace_id || '').trim()
  if (!wid) return {}

  const seq = Number(opts?.seq || 0)

  const r = await call_tool('nisb_workspace_files_state_apply', { workspace_id: wid })

  if (seq && seq !== __workspace_switch_seq) return {}

  const info = normalizeToolResponse(r, t('sidebar.workspace.restoreSnapshotSuccess'))
  if (!info.success) {
    throw new Error(String(info.text || t('sidebar.workspace.restoreSnapshotFailed')))
  }

  const files_state = pickDataValue(r, 'files_state', {})
  const current_state =
    files_state && typeof files_state === 'object' && files_state.current && typeof files_state.current === 'object'
      ? files_state.current
      : {}

  const focused_root_path = String(current_state?.focused_root_path || '').trim()

  if (focused_root_path) {
    await persist_focus_root_to_ui(focused_root_path, '', wid, {
      seq,
      refresh: false
    })
  } else {
    await clear_focus_root_from_ui({
      seq,
      refresh: false
    })
  }

  if (seq && seq !== __workspace_switch_seq) return {}

  _schedule_workspace_ui_refresh('workspace-apply', seq)
  return current_state
}

async function perform_workspace_switch(workspace_id, { apply_snapshot = true } = {}) {
  const wid = String(workspace_id || '').trim()
  if (!wid) return { seq: __workspace_switch_seq, workspace_id: '', stale: true, snapshot_current: {} }

  const seq = ++__workspace_switch_seq

  _set_workspace_switch_state({
    busy: true,
    seq,
    workspace_id: wid,
    started_at: Date.now()
  })

  try {
    switch_left_sidebar_tab('files', { refreshFiles: false })
    current_workspace.value = wid

    await handle_workspace_change()

    if (seq !== __workspace_switch_seq) {
      return { seq, workspace_id: wid, stale: true, snapshot_current: {} }
    }

    let snapshot_current = {}
    if (apply_snapshot) {
      snapshot_current = await apply_workspace_snapshot_to_ui(wid, { seq })
    }

    if (seq !== __workspace_switch_seq) {
      return { seq, workspace_id: wid, stale: true, snapshot_current: {} }
    }

    return { seq, workspace_id: wid, stale: false, snapshot_current }
  } finally {
    if (seq === __workspace_switch_seq) {
      _set_workspace_switch_state({
        busy: false,
        seq,
        workspace_id: wid,
        finished_at: Date.now()
      })
    }
  }
}

function _resolve_stale_switch_job(job) {
  if (!job) return
  try {
    job.resolve({
      seq: __workspace_switch_seq,
      workspace_id: String(job.workspace_id || '').trim(),
      stale: true,
      snapshot_current: {}
    })
  } catch {}
}

async function _drain_workspace_switch_queue() {
  if (__workspace_switch_inflight) return
  if (!__workspace_switch_pending_job) return

  const job = __workspace_switch_pending_job
  __workspace_switch_pending_job = null
  __workspace_switch_inflight = true

  try {
    const result = await perform_workspace_switch(job.workspace_id, job.options || {})
    job.resolve(result)
  } catch (error) {
    job.reject(error)
  } finally {
    __workspace_switch_inflight = false
    if (__workspace_switch_pending_job) {
      void _drain_workspace_switch_queue()
    }
  }
}

function request_workspace_switch_latest(workspace_id, options = {}) {
  const wid = String(workspace_id || '').trim()
  if (!wid) {
    return Promise.resolve({
      seq: __workspace_switch_seq,
      workspace_id: '',
      stale: true,
      snapshot_current: {}
    })
  }

  return new Promise((resolve, reject) => {
    if (__workspace_switch_pending_job) {
      _resolve_stale_switch_job(__workspace_switch_pending_job)
    }

    __workspace_switch_pending_job = {
      workspace_id: wid,
      options,
      resolve,
      reject
    }

    if (!__workspace_switch_inflight) {
      void _drain_workspace_switch_queue()
    }
  })
}

function _schedule_reveal_event(detail, { seq = 0, delay = 0 } = {}) {
  const timer = setTimeout(() => {
    __reveal_timers.delete(timer)

    if (!__alive) return
    if (seq && seq !== __workspace_switch_seq) return

    window.dispatchEvent(
      new CustomEvent('nisb-file-tree-focus-path', {
        detail
      })
    )
  }, Math.max(0, Number(delay || 0)))

  __reveal_timers.add(timer)
}

async function reveal_path_to_ui(path, type = 'directory', opts = {}) {
  const target_path = normalize_relative_path_client(path)
  if (!target_path) return

  const seq = Number(opts?.seq || 0)
  const target_type = String(type || 'directory').trim().toLowerCase() === 'file' ? 'file' : 'directory'

  _clear_reveal_timers()
  await nextTick()

  for (const delay of WORKSPACE_REVEAL_RETRY_DELAYS_MS) {
    _schedule_reveal_event(
      {
        path: target_path,
        type: target_type
      },
      { seq, delay }
    )
  }
}

async function apply_workspace_context_to_ui({
  workspace_id = '',
  focus_root = '',
  focus_label = '',
  reveal_path = '',
  reveal_type = 'directory',
  prefer_workspace_snapshot = false
} = {}) {
  const wid = String(workspace_id || '').trim()
  const requested_focus_root = normalize_focus_root_client(focus_root || '')
  const requested_focus_label = String(focus_label || '').trim()
  const effective_reveal_type = String(reveal_type || 'directory').trim().toLowerCase()

  switch_left_sidebar_tab('files', { refreshFiles: false })

  let seq = __workspace_switch_seq
  let snapshot_current = {}
  let snapshot_focus_root = ''

  if (wid && wid !== String(current_workspace.value || '').trim()) {
    const switched = await request_workspace_switch_latest(wid, {
      apply_snapshot: !!prefer_workspace_snapshot
    })
    seq = switched.seq
    if (switched.stale) {
      return {
        workspace_id: wid,
        focused_root_path: ''
      }
    }
    snapshot_current = switched.snapshot_current || {}
    snapshot_focus_root = normalize_focus_root_client(snapshot_current?.focused_root_path || '')
  } else if (wid && prefer_workspace_snapshot) {
    seq = ++__workspace_switch_seq

    _set_workspace_switch_state({
      busy: true,
      seq,
      workspace_id: wid,
      started_at: Date.now()
    })

    try {
      snapshot_current = await apply_workspace_snapshot_to_ui(wid, { seq })
      snapshot_focus_root = normalize_focus_root_client(snapshot_current?.focused_root_path || '')
      if (seq !== __workspace_switch_seq) {
        return {
          workspace_id: wid,
          focused_root_path: ''
        }
      }
    } finally {
      if (seq === __workspace_switch_seq) {
        _set_workspace_switch_state({
          busy: false,
          seq,
          workspace_id: wid,
          finished_at: Date.now()
        })
      }
    }
  }

  const final_workspace_id = wid || String(current_workspace.value || '').trim()

  if (!snapshot_focus_root && requested_focus_root) {
    await persist_focus_root_to_ui(requested_focus_root, requested_focus_label, final_workspace_id, {
      seq,
      refresh: false
    })
    _schedule_workspace_ui_refresh('workspace-context-focus-root', seq)
  }

  const final_focus_root = snapshot_focus_root || requested_focus_root || ''
  const final_reveal_path = normalize_relative_path_client(reveal_path || final_focus_root || '')

  if (final_reveal_path) {
    await reveal_path_to_ui(final_reveal_path, effective_reveal_type || 'directory', { seq })
  }

  return {
    workspace_id: final_workspace_id,
    focused_root_path: final_focus_root
  }
}

const { context_menu, visible_extensions, show_context_menu, hide_context_menu } = use_left_sidebar_context_menu()

const {
  workspaces,
  current_workspace,
  current_workspace_name,
  settings_modal_open,
  init_workspace_from_backend_then_local,
  load_workspaces,
  handle_workspace_change,
  open_settings,

  on_workspaces_refresh,
  on_workspace_switch_request,
  on_focus_root_persist,
  on_clear_focus_root_persist,

  suppress_focus_persist
} = use_left_sidebar_workspaces({ call_tool })

async function on_workspace_change(new_wid) {
  const wid = String(new_wid || '').trim()
  if (!wid) return

  await request_workspace_switch_latest(wid, { apply_snapshot: true })
}

const current_dir = ref('')
function on_current_dir_changed(e) {
  current_dir.value = e?.detail?.path || ''
}

const file_input = ref(null)
const dir_input = ref(null)

const { trigger_upload, trigger_dir_upload, handle_file_upload, handle_dir_upload } = use_left_sidebar_uploads({
  call_tool,
  current_dir,
  file_input,
  dir_input
})

const {
  is_binary_file,
  is_pdf_file,
  is_epub_file,
  is_image_file,
  on_context_menu_action,
  handle_send_to_library_sent,
  cleanup_binary_blob_urls
} = use_left_sidebar_actions({
  call_tool,
  context_menu,
  hide_context_menu,
  show_context_menu,
  current_workspace,
  workspaces,
  library_list_ref,
  send_to_library_dialog,
  suppress_focus_persist
})

async function on_file_context_menu(e) {
  const d = e?.detail || {}
  const target_type = String(d.targetType || 'file').trim() || 'file'

  const target_path = target_type === 'create' ? String(d.baseDir || '').trim() : String(d.path || '').trim()
  const target_name = target_type === 'create' ? '' : String(d.name || '').trim()
  const target_file_type = target_type === 'create' ? 'directory' : String(d.type || 'file').trim()

  await show_context_menu({
    x: d.x,
    y: d.y,
    targetType: target_type,
    targetPath: target_path,
    targetName: target_name,
    targetFileType: target_file_type,
    targetId: null,
    targetTitle: null,
    extensions: Array.isArray(d.extensions) ? d.extensions : []
  })
}

function on_click_global() {
  hide_context_menu()
}

function on_left_sidebar_switch_tab(evt) {
  const d = evt?.detail || {}
  const tab = d.tab || d.active_tab || ''
  const refreshFiles = d.refresh_files === true || d.refreshFiles === true
  switch_left_sidebar_tab(tab, { refreshFiles })
}

function on_workspace_switch_request_with_tab(evt) {
  switch_left_sidebar_tab('files', { refreshFiles: false })
  return on_workspace_switch_request(evt)
}

async function on_undo_bulk(evt) {
  const bulk_id = evt?.detail?.bulk_id
  if (!bulk_id) return

  const r = await call_tool('nisb_fs_bulk_restore', { bulk_id, overwrite: false })
  const info = normalizeToolResponse(r, t('files.bulk.undoSuccess'))

  if (!info.success) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('files.bulk.undoFailed', {
            error: info.text || t('common.unknownError')
          }),
          type: 'error'
        }
      })
    )
    return
  }

  _schedule_workspace_ui_refresh('undo-bulk', 0)
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message: t('files.bulk.undoSuccess'), type: 'success' }
    })
  )
}

async function on_room_apply_workspace_context(evt) {
  const d = evt?.detail || {}

  const workspace_id = String(d.workspace_id || d.workspaceId || '').trim()
  const focus_root = normalize_focus_root_client(d.focus_root || d.focusRoot || '')
  const focus_label = String(d.focus_label || d.focusLabel || '').trim()
  const clear_focus_root = d.clear_focus_root === true
  const prefer_workspace_snapshot =
    d.prefer_workspace_snapshot === true || (workspace_id && d.prefer_workspace_snapshot !== false)

  try {
    if (workspace_id || focus_root) {
      await apply_workspace_context_to_ui({
        workspace_id,
        focus_root,
        focus_label,
        reveal_path: focus_root,
        reveal_type: 'directory',
        prefer_workspace_snapshot
      })

      if (workspace_id) {
        dispatch_toast(t('sidebar.workspace.restoreRoomWorkspaceSuccess'), 'success')
      } else {
        dispatch_toast(t('sidebar.workspace.applyRoomFocusSuccess'), 'success')
      }
      return
    }

    if (clear_focus_root) {
      switch_left_sidebar_tab('files', { refreshFiles: false })
      await clear_focus_root_from_ui({
        seq: ++__workspace_switch_seq,
        refresh: true,
        refresh_reason: 'room-clear-workspace-context'
      })
      dispatch_toast(t('sidebar.workspace.clearRoomFocusSuccess'), 'success')
    }
  } catch (error) {
    dispatch_toast(
      t('sidebar.workspace.applyRoomContextFailed', {
        error: error?.message || error || t('common.unknownError')
      }),
      'error'
    )
  }
}

async function on_room_clear_workspace_context(evt) {
  const d = evt?.detail || {}
  const clear_focus_root = d.clear_focus_root !== false

  if (clear_focus_root) {
    switch_left_sidebar_tab('files', { refreshFiles: false })
    await clear_focus_root_from_ui({
      seq: ++__workspace_switch_seq,
      refresh: true,
      refresh_reason: 'room-clear-workspace-context'
    })
  }

  dispatch_toast(t('sidebar.workspace.clearRoomFocusSuccess'), 'success')
}

function build_saved_target_path(detail) {
  const scoped_path = normalize_relative_path_client(detail?.scoped_path || '')
  if (scoped_path) return scoped_path

  const focus_root = normalize_focus_root_client(detail?.focus_root || '')
  const relative_path = normalize_relative_path_client(detail?.relative_path || '')
  return join_rel_path(focus_root, relative_path)
}

async function on_room_workspace_saved(evt) {
  const d = evt?.detail || {}

  const workspace_id = String(d.workspace_id || '').trim()
  const focus_root = normalize_focus_root_client(d.focus_root || '')
  const target_path = build_saved_target_path(d)

  try {
    switch_left_sidebar_tab('files', { refreshFiles: false })

    let seq = __workspace_switch_seq

    if (workspace_id && workspace_id !== String(current_workspace.value || '').trim()) {
      const switched = await request_workspace_switch_latest(workspace_id, { apply_snapshot: false })
      seq = switched.seq
      if (switched.stale) return
    }

    if (focus_root) {
      await persist_focus_root_to_ui(focus_root, '', workspace_id || String(current_workspace.value || '').trim(), {
        seq,
        refresh: false
      })
      _schedule_workspace_ui_refresh('room-workspace-saved', seq)
    } else {
      _schedule_workspace_ui_refresh('room-workspace-saved', seq)
    }

    await nextTick()

    if (target_path) {
      await reveal_path_to_ui(target_path, 'file', { seq })
    }
  } catch (error) {
    dispatch_toast(
      t('files.revealSavedFileFailed', {
        error: error?.message || error || t('common.unknownError')
      }),
      'error'
    )
  }
}

async function apply_pending_left_sidebar_intent(intent) {
  if (!intent || typeof intent !== 'object') return false

  const target_tab = normalize_sidebar_tab(intent.tab || 'files') || 'files'
  const pending_workspace_id = String(intent.workspace_id || '').trim()
  const pending_focus_root = normalize_focus_root_client(intent.focus_root || '')
  const pending_focus_label = String(intent.focus_label || '').trim()
  const pending_reveal_path = normalize_relative_path_client(intent.reveal_path || pending_focus_root || '')
  const pending_reveal_type = String(intent.reveal_type || 'directory').trim().toLowerCase()
  const prefer_workspace_snapshot =
    intent.prefer_workspace_snapshot === true || (pending_workspace_id && intent.prefer_workspace_snapshot !== false)

  switch_left_sidebar_tab(target_tab, { refreshFiles: false })

  await apply_workspace_context_to_ui({
    workspace_id: pending_workspace_id,
    focus_root: pending_focus_root,
    focus_label: pending_focus_label,
    reveal_path: pending_reveal_path,
    reveal_type: pending_reveal_type,
    prefer_workspace_snapshot
  })

  return true
}

async function consume_pending_left_sidebar_intent() {
  const intent = read_pending_left_sidebar_intent()
  if (!intent) return false

  try {
    const ok = await apply_pending_left_sidebar_intent(intent)
    if (ok) {
      clear_pending_left_sidebar_intent()
      return true
    }
  } catch {}

  return false
}

onMounted(async () => {
  __alive = true

  if (!localStorage.getItem('nisb_user_id')) localStorage.setItem('nisb_user_id', 'nisb_default_user')

  window.addEventListener('file-context-menu', on_file_context_menu)
  window.addEventListener('click', on_click_global)
  window.addEventListener('nisb-current-dir-changed', on_current_dir_changed)
  window.addEventListener('nisb-fs-undo-bulk', on_undo_bulk)

  window.addEventListener('nisb_workspaces_refresh', on_workspaces_refresh)
  window.addEventListener('nisb_workspace_switch_request', on_workspace_switch_request_with_tab)

  window.addEventListener('nisb_file_focus_root', on_focus_root_persist)
  window.addEventListener('nisb_file_clear_focus_root', on_clear_focus_root_persist)
  window.addEventListener('nisb-left-sidebar-switch-tab', on_left_sidebar_switch_tab)

  window.addEventListener('nisb_room_apply_workspace_context', on_room_apply_workspace_context)
  window.addEventListener('nisb_room_clear_workspace_context', on_room_clear_workspace_context)
  window.addEventListener('nisb-room-workspace-saved', on_room_workspace_saved)

  try {
    await init_workspace_from_backend_then_local()
    await load_workspaces()
  } finally {
    await consume_pending_left_sidebar_intent()
    _schedule_pending_intent_retry(120)
    _schedule_pending_intent_retry(420)
  }
})

onUnmounted(() => {
  __alive = false

  window.removeEventListener('file-context-menu', on_file_context_menu)
  window.removeEventListener('click', on_click_global)
  window.removeEventListener('nisb-current-dir-changed', on_current_dir_changed)
  window.removeEventListener('nisb-fs-undo-bulk', on_undo_bulk)

  window.removeEventListener('nisb_workspaces_refresh', on_workspaces_refresh)
  window.removeEventListener('nisb_workspace_switch_request', on_workspace_switch_request_with_tab)

  window.removeEventListener('nisb_file_focus_root', on_focus_root_persist)
  window.removeEventListener('nisb_file_clear_focus_root', on_clear_focus_root_persist)
  window.removeEventListener('nisb-left-sidebar-switch-tab', on_left_sidebar_switch_tab)

  window.removeEventListener('nisb_room_apply_workspace_context', on_room_apply_workspace_context)
  window.removeEventListener('nisb_room_clear_workspace_context', on_room_clear_workspace_context)
  window.removeEventListener('nisb-room-workspace-saved', on_room_workspace_saved)

  _clear_workspace_refresh_queue()
  _clear_async_event_timers()
  _clear_reveal_timers()
  _clear_pending_intent_timers()
  cleanup_binary_blob_urls()
})
</script>

<style scoped src="./LeftSidebar/LeftSidebar.css"></style>
