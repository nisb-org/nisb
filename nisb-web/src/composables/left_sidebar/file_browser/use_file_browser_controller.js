import { ref, watch, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  is_workspace_id_safe,
  normalize_path,
  normalize_type,
  fav_key,
  sort_by_pinned_at_desc,
  get_parent_dir,
  get_base_name
} from './file_browser_utils'
import { normalize_favorite_highlight_color } from './favorite_highlight_colors'
import { use_file_browser_tooltip } from './use_file_browser_tooltip'
import { use_file_browser_clipboard } from './use_file_browser_clipboard'
import { open_batch_move_modal } from './batch_move_modal_service'
import { open_batch_rename_modal } from './batch_rename_modal_service'
import { normalizeToolResponse } from '../actions/response_normalizer'
import { to_user_visible_segments } from './file_path_display'

export function use_file_browser_controller({
  workspace_id_ref,
  call_tool,
  metadata_call_tool = null,
  file_list_el,
  root_row_el,
  root_plus_btn_el
}) {
  const { t } = useI18n()
  const favorite_call_tool = typeof metadata_call_tool === 'function' ? metadata_call_tool : call_tool

  const loading = ref(true)
  const entries = ref([])
  const selectedPath = ref(null)
  const currentPath = ref('')
  const expandedPaths = ref([])
  const scrollTargetPath = ref('')

  const favorites = ref([])
  const libraryStatusMap = ref({})

  const focusedRootPath = ref('')

  const effectiveWorkspaceId = computed(() => {
    const w = String(workspace_id_ref?.value || '').trim()
    return is_workspace_id_safe(w) ? w : 'workspace_work'
  })

  const batchMode = ref(false)
  const batchSelectedMap = ref({})
  const pendingBatchDelete = ref({ ts: 0, key: '' })

  const { path_tip, on_fav_enter, on_fav_move, on_fav_leave } = use_file_browser_tooltip()
  const { on_copy_internal_link } = use_file_browser_clipboard()

  let __alive = true

  let __root_load_seq = 0
  let __favorites_load_seq = 0
  let __library_status_seq = 0
  let __workspace_run_seq = 0
  let __focus_run_seq = 0
  let __tree_refresh_run_seq = 0

  let __favorites_snapshot_timer = null
  let __favorites_refresh_event_timer = null
  let __file_tree_refresh_timer = null
  let __timeline_refresh_event_timer = null
  let __global_focus_timer = null
  let __global_clear_focus_timer = null
  let __workspace_watch_timer = null

  let __focus_write_idle_id = null
  let __tree_state_write_idle_id = null
  let __pending_focus_write = null
  let __pending_tree_state_write = null

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

  function _dispatch_async(event_name, detail = {}, delay = 0) {
    window.setTimeout(() => {
      if (!__alive) return
      try {
        window.dispatchEvent(new CustomEvent(event_name, { detail }))
      } catch {}
    }, Math.max(0, Number(delay || 0)))
  }

  function _clear_timer(id) {
    try {
      clearTimeout(id)
    } catch {}
  }

  function getInfo(res, fallbackText = t('files.controller.messages.actionCompleted')) {
    return normalizeToolResponse(res, fallbackText)
  }

  function getDataObject(res) {
    const info = getInfo(res)
    return info?.data && typeof info.data === 'object' ? info.data : {}
  }

  function getDataValue(res, key, fallback = undefined) {
    const data = getDataObject(res)
    if (data[key] !== undefined) return data[key]
    if (res && res[key] !== undefined) return res[key]
    return fallback
  }

  function getDataArray(res, key) {
    const data = getDataObject(res)
    if (Array.isArray(data[key])) return data[key]
    if (Array.isArray(res?.[key])) return res[key]
    return []
  }

  function applyToggleResult(item, pinned) {
    if (!item || !item.path) return
    const k = fav_key(item)
    const cur = Array.isArray(favorites.value) ? favorites.value.slice() : []
    const idx = cur.findIndex((x) => fav_key(x) === k)

    if (pinned) {
      if (idx === -1) cur.unshift(item)
      else cur[idx] = item
    } else {
      if (idx !== -1) cur.splice(idx, 1)
    }

    favorites.value = sort_by_pinned_at_desc(cur)
  }

  function patchFavoriteMetadata(item) {
    if (!item || !item.path) return false

    const p = normalize_path(item.path)
    const tt = normalize_type(item.type)
    if (!p) return false

    const normalized = {
      ...item,
      path: p,
      type: tt,
      highlight_color: normalize_favorite_highlight_color(item.highlight_color),
      highlighted_at: String(item.highlighted_at || '')
    }

    if (!normalized.highlight_color) normalized.highlighted_at = ''

    const k = fav_key(normalized)
    const cur = Array.isArray(favorites.value) ? favorites.value.slice() : []
    const idx = cur.findIndex((x) => fav_key(x) === k)

    if (idx === -1) cur.unshift(normalized)
    else cur[idx] = { ...cur[idx], ...normalized }

    favorites.value = sort_by_pinned_at_desc(cur)
    return true
  }

  const focusSegments = computed(() => {
    return to_user_visible_segments(focusedRootPath.value)
  })

  function getFocusStorageKey() {
    const ws = effectiveWorkspaceId.value || 'workspace_work'
    return `nisb_fs_focus_root_${ws}`
  }

  function getStateStorageKey() {
    const ws = effectiveWorkspaceId.value || 'workspace_work'
    return `nisb_fs_state_${ws}`
  }

  function saveFocusRoot() {
    __pending_focus_write = {
      key: getFocusStorageKey(),
      value: String(focusedRootPath.value || '')
    }

    if (__focus_write_idle_id !== null) {
      _cancel_idle(__focus_write_idle_id)
      __focus_write_idle_id = null
    }

    __focus_write_idle_id = _request_idle(
      () => {
        __focus_write_idle_id = null
        const payload = __pending_focus_write
        __pending_focus_write = null
        if (!__alive || !payload?.key) return
        try {
          localStorage.setItem(payload.key, payload.value)
        } catch {}
      },
      { timeout: 1200 }
    )
  }

  function restoreFocusRoot() {
    try {
      const v = String(localStorage.getItem(getFocusStorageKey()) || '').trim()
      focusedRootPath.value = v
    } catch {
      focusedRootPath.value = ''
    }
  }

  function saveTreeState() {
    __pending_tree_state_write = {
      key: getStateStorageKey(),
      value: JSON.stringify({
        expandedPaths: Array.isArray(expandedPaths.value) ? expandedPaths.value.slice() : [],
        selectedPath: selectedPath.value,
        currentPath: currentPath.value
      })
    }

    if (__tree_state_write_idle_id !== null) {
      _cancel_idle(__tree_state_write_idle_id)
      __tree_state_write_idle_id = null
    }

    __tree_state_write_idle_id = _request_idle(
      () => {
        __tree_state_write_idle_id = null
        const payload = __pending_tree_state_write
        __pending_tree_state_write = null
        if (!__alive || !payload?.key || !payload?.value) return
        try {
          localStorage.setItem(payload.key, payload.value)
        } catch {}
      },
      { timeout: 1200 }
    )
  }

  function restoreTreeState() {
    try {
      const raw = localStorage.getItem(getStateStorageKey())
      if (!raw) return
      const data = JSON.parse(raw)

      if (Array.isArray(data.expandedPaths)) expandedPaths.value = data.expandedPaths
      if (typeof data.selectedPath === 'string') selectedPath.value = data.selectedPath

      if (typeof data.currentPath === 'string') {
        currentPath.value = data.currentPath
        _dispatch_async('nisb-current-dir-changed', { path: currentPath.value }, 0)
      }
    } catch {}
  }

  function isFocusedPath(path) {
    const p = String(path || '').trim().replace(/^\/+/, '')
    return !!p && focusedRootPath.value === p
  }

  function scrollRootRowToOneThird() {
    const container = file_list_el?.value
    const row = root_row_el?.value
    if (!container || !row) return
    try {
      const containerH = container.clientHeight || 0
      if (!containerH) return

      const rowTop = row.offsetTop
      const targetTop = Math.max(0, rowTop - Math.floor(containerH / 3))
      container.scrollTo({ top: targetTop, behavior: 'smooth' })
    } catch {}
  }

  function getListBasePath() {
    const focused = String(focusedRootPath.value || '').trim().replace(/^\/+|\/+$/g, '')
    return focused || 'agent_files'
  }

  function _schedule_favorites_snapshot() {
    if (__favorites_snapshot_timer) _clear_timer(__favorites_snapshot_timer)

    const map = favoriteMap.value
    __favorites_snapshot_timer = window.setTimeout(() => {
      __favorites_snapshot_timer = null
      if (!__alive) return
      try {
        window.dispatchEvent(new CustomEvent('nisb-favorites-snapshot', { detail: { favorite_map: map } }))
      } catch {}
    }, 0)
  }

  function _schedule_favorites_refresh_event(delay = 40) {
    if (__favorites_refresh_event_timer) _clear_timer(__favorites_refresh_event_timer)
    __favorites_refresh_event_timer = window.setTimeout(() => {
      __favorites_refresh_event_timer = null
      if (!__alive) return
      try {
        window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
      } catch {}
    }, Math.max(0, Number(delay || 0)))
  }

  function _schedule_timeline_refresh_event(delay = 40) {
    if (__timeline_refresh_event_timer) _clear_timer(__timeline_refresh_event_timer)
    __timeline_refresh_event_timer = window.setTimeout(() => {
      __timeline_refresh_event_timer = null
      if (!__alive) return
      try {
        window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
      } catch {}
    }, Math.max(0, Number(delay || 0)))
  }

  async function refreshLibraryStatus(paths, opts = {}) {
    const rootSeq = Number(opts.rootSeq || 0)
    const cleaned = (paths || []).map((p) => String(p || '').trim()).filter(Boolean)

    if (!cleaned.length) {
      if (!rootSeq || rootSeq === __root_load_seq) libraryStatusMap.value = {}
      return
    }

    const seq = ++__library_status_seq

    try {
      const res = await call_tool('nisb_fs_library_status_batch', { paths: cleaned })
      if (!__alive) return
      if (seq !== __library_status_seq) return
      if (rootSeq && rootSeq !== __root_load_seq) return

      const info = getInfo(res, t('files.controller.messages.libraryStatusRefreshed'))
      const items = getDataArray(res, 'items')
      if (!info.success || !Array.isArray(items)) return

      const map = {}
      for (const item of items) {
        if (!item || !item.path) continue
        map[item.path] = {
          kind: item.kind,
          sent: !!item.sent,
          coverage: typeof item.coverage === 'number' ? item.coverage : 0,
          libraries: Array.isArray(item.libraries) ? item.libraries : []
        }
      }
      libraryStatusMap.value = map
    } catch {}
  }

  async function loadRoot(opts = {}) {
    const seq = ++__root_load_seq
    const keepLoading = !!opts.keepLoading

    if (!keepLoading) loading.value = true

    try {
      const base = getListBasePath()
      const result = await call_tool('nisb_dir_list', { path: base })

      if (!__alive || seq !== __root_load_seq) return false

      const info = getInfo(result, t('files.controller.messages.directoryLoaded'))
      const dirEntries = getDataArray(result, 'entries')

      if (info.success && Array.isArray(dirEntries)) {
        const nextEntries = dirEntries
          .filter((e) => !String(e.name || '').startsWith('.'))
          .map((e) => {
            const p = base ? `${base}/${e.name}` : e.name
            return { name: e.name, type: e.type, path: p }
          })

        entries.value = nextEntries

        const paths = nextEntries.map((e) => e.path)
        if (paths.length) await refreshLibraryStatus(paths, { rootSeq: seq })
        else if (__alive && seq === __root_load_seq) libraryStatusMap.value = {}
      } else {
        entries.value = []
        libraryStatusMap.value = {}
      }

      return true
    } catch {
      if (__alive && seq === __root_load_seq) {
        entries.value = []
        libraryStatusMap.value = {}
      }
      return false
    } finally {
      if (__alive && seq === __root_load_seq && !keepLoading) loading.value = false
    }
  }

  const favoriteDirs = computed(() => (favorites.value || []).filter((f) => normalize_type(f?.type) === 'directory'))
  const favoriteFiles = computed(() => (favorites.value || []).filter((f) => normalize_type(f?.type) === 'file'))

  const favoriteMap = computed(() => {
    const map = {}
    for (const f of favorites.value || []) {
      const p = normalize_path(f?.path)
      if (p) map[p] = true
    }
    return map
  })

  const favoriteMetaMap = computed(() => {
    const map = {}
    for (const f of favorites.value || []) {
      const p = normalize_path(f?.path)
      if (!p) continue
      map[p] = {
        ...f,
        path: p,
        type: normalize_type(f?.type),
        highlight_color: normalize_favorite_highlight_color(f?.highlight_color)
      }
    }
    return map
  })

  watch(
    favorites,
    () => {
      _schedule_favorites_snapshot()
    },
    { deep: true, immediate: true }
  )

  async function loadFavorites() {
    const seq = ++__favorites_load_seq

    try {
      const res = await favorite_call_tool('nisb_favorites_list_files', { workspace_id: effectiveWorkspaceId.value })

      if (!__alive || seq !== __favorites_load_seq) return false

      const info = getInfo(res, t('files.controller.messages.favoritesLoaded'))
      const items = getDataArray(res, 'items')

      if (info.success && Array.isArray(items)) favorites.value = sort_by_pinned_at_desc(items)
      else favorites.value = []

      return true
    } catch {
      if (__alive && seq === __favorites_load_seq) favorites.value = []
      return false
    } finally {
      if (__alive && seq === __favorites_load_seq) _schedule_favorites_snapshot()
    }
  }

  async function focusRoot(path, opts = {}) {
    const runSeq = ++__focus_run_seq
    const silent = !!opts.silent
    const p = String(path || '').trim().replace(/^\/+/, '')
    if (!p) return
    if (focusedRootPath.value === p) return

    focusedRootPath.value = p
    saveFocusRoot()

    expandedPaths.value = []
    selectedPath.value = p
    currentPath.value = p
    scrollTargetPath.value = p
    saveTreeState()

    _dispatch_async('nisb-current-dir-changed', { path: p }, 0)
    if (!silent) _dispatch_async('nisb_file_focus_root', { path: p }, 0)

    await loadRoot()

    if (!__alive || runSeq !== __focus_run_seq) return
    await nextTick()
    if (!__alive || runSeq !== __focus_run_seq) return
    scrollRootRowToOneThird()
  }

  async function clearFocusRoot(opts = {}) {
    const runSeq = ++__focus_run_seq
    const silent = !!opts.silent
    if (!focusedRootPath.value) return

    focusedRootPath.value = ''
    saveFocusRoot()

    expandedPaths.value = []
    selectedPath.value = null
    currentPath.value = ''
    scrollTargetPath.value = ''
    saveTreeState()

    _dispatch_async('nisb-current-dir-changed', { path: '' }, 0)
    if (!silent) _dispatch_async('nisb_file_clear_focus_root', {}, 0)

    await loadRoot()

    if (!__alive || runSeq !== __focus_run_seq) return
    await nextTick()
    if (!__alive || runSeq !== __focus_run_seq) return
    scrollRootRowToOneThird()
  }

  async function toggleFocusRoot(path) {
    const p = String(path || '').trim().replace(/^\/+/, '')
    if (!p) return
    if (focusedRootPath.value === p) await clearFocusRoot()
    else await focusRoot(p)
  }

  async function collapseAllDirs() {
    expandedPaths.value = []
    selectedPath.value = null
    currentPath.value = focusedRootPath.value ? focusedRootPath.value : ''
    scrollTargetPath.value = ''
    saveTreeState()
    _dispatch_async('nisb-current-dir-changed', { path: currentPath.value }, 0)
    await loadRoot()
  }

  async function on_favorites_toggle(evt) {
    const d = evt?.detail || {}
    const path = String(d.path || '').trim()
    const type = String(d.type || '').trim() || 'file'
    if (!path) return

    try {
      const res = await favorite_call_tool('nisb_favorites_toggle_file', {
        path,
        type,
        workspace_id: effectiveWorkspaceId.value
      })
      const info = getInfo(res, t('files.controller.messages.favoritesUpdated'))
      if (info.success) {
        applyToggleResult(getDataValue(res, 'item', null), !!getDataValue(res, 'pinned', false))
        _dispatch_async(
          'nisb-toast',
          {
            message: info.text || t('files.controller.messages.favoritesUpdated'),
            type: info.isWarning ? 'warning' : 'info'
          },
          0
        )
        _schedule_favorites_refresh_event(50)
      } else {
        _dispatch_async(
          'nisb-toast',
          {
            message: info.text || t('files.controller.messages.favoritesUpdateFailed'),
            type: 'error'
          },
          0
        )
      }
    } catch {
      _dispatch_async(
        'nisb-toast',
        {
          message: t('files.controller.messages.favoritesUpdateFailed'),
          type: 'error'
        },
        0
      )
    }
  }

  async function setFavoriteHighlight(path, type = 'file', color = 'amber') {
    const p = normalize_path(path)
    const tt = normalize_type(type)
    const cc = normalize_favorite_highlight_color(color)

    if (!p || !cc) return false

    try {
      const res = await favorite_call_tool('nisb_favorites_set_highlight', {
        path: p,
        type: tt,
        color: cc,
        workspace_id: effectiveWorkspaceId.value
      })

      const info = getInfo(res, t('files.controller.messages.highlightUpdated'))

      if (info.success) {
        const item = getDataValue(res, 'item', null)
        if (!patchFavoriteMetadata(item)) await loadFavorites()

        _toast(info.text || t('files.controller.messages.highlightUpdated'), info.isWarning ? 'warning' : 'success', 1800)
        _schedule_favorites_refresh_event(50)
        return true
      }

      _toast(info.text || t('files.controller.messages.highlightUpdateFailed'), 'error', 2600)
      return false
    } catch (e) {
      _toast(e?.message || t('files.controller.messages.highlightUpdateFailed'), 'error', 2600)
      return false
    }
  }

  async function clearFavoriteHighlight(path) {
    const p = normalize_path(path)
    if (!p) return false

    try {
      const res = await favorite_call_tool('nisb_favorites_clear_highlight', {
        path: p,
        workspace_id: effectiveWorkspaceId.value
      })

      const info = getInfo(res, t('files.controller.messages.highlightCleared'))

      if (info.success) {
        const item = getDataValue(res, 'item', null)
        if (!patchFavoriteMetadata(item)) await loadFavorites()

        _toast(info.text || t('files.controller.messages.highlightCleared'), info.isWarning ? 'warning' : 'success', 1800)
        _schedule_favorites_refresh_event(50)
        return true
      }

      _toast(info.text || t('files.controller.messages.highlightUpdateFailed'), 'error', 2600)
      return false
    } catch (e) {
      _toast(e?.message || t('files.controller.messages.highlightUpdateFailed'), 'error', 2600)
      return false
    }
  }

  function on_favorites_highlight_set(evt) {
    const d = evt?.detail || {}
    setFavoriteHighlight(d.path, d.type || d.targetFileType || 'file', d.color || 'amber')
  }

  function on_favorites_highlight_clear(evt) {
    const d = evt?.detail || {}
    clearFavoriteHighlight(d.path)
  }

  function isFavoriteExact(path, type) {
    const p = normalize_path(path)
    const tt = normalize_type(type)
    if (!p) return false
    return (favorites.value || []).some((f) => normalize_path(f?.path) === p && normalize_type(f?.type) === tt)
  }

  function replacePrefixPath(path, oldPrefix, newPrefix) {
    const p = normalize_path(path)
    const oldp = normalize_path(oldPrefix)
    const newp = normalize_path(newPrefix)
    if (!p || !oldp || !newp) return path
    if (p === oldp) return newp
    if (p.startsWith(oldp)) return newp + p.slice(oldp.length)
    return path
  }

  function patchUiPathsAfterRename(oldPath, newPath) {
    const oldp = normalize_path(oldPath)
    const newp = normalize_path(newPath)
    if (!oldp || !newp || oldp === newp) return

    if (focusedRootPath.value && (focusedRootPath.value === oldp || String(focusedRootPath.value).startsWith(oldp))) {
      focusedRootPath.value = replacePrefixPath(focusedRootPath.value, oldp, newp)
      saveFocusRoot()
    }

    if (selectedPath.value && (selectedPath.value === oldp || String(selectedPath.value).startsWith(oldp))) {
      selectedPath.value = replacePrefixPath(selectedPath.value, oldp, newp)
    }

    if (currentPath.value && (currentPath.value === oldp || String(currentPath.value).startsWith(oldp))) {
      currentPath.value = replacePrefixPath(currentPath.value, oldp, newp)
      _dispatch_async('nisb-current-dir-changed', { path: currentPath.value }, 0)
    }

    if (scrollTargetPath.value && (scrollTargetPath.value === oldp || String(scrollTargetPath.value).startsWith(oldp))) {
      scrollTargetPath.value = replacePrefixPath(scrollTargetPath.value, oldp, newp)
    }

    if (Array.isArray(expandedPaths.value) && expandedPaths.value.length) {
      expandedPaths.value = expandedPaths.value.map((p) => replacePrefixPath(p, oldp, newp))
    }

    saveTreeState()
  }

  async function on_path_deleted(evt) {
    const d = evt?.detail || {}
    const path = normalize_path(d.path)
    const type = normalize_type(d.type)
    if (!path) return

    if (isFavoriteExact(path, type)) {
      try {
        const res = await favorite_call_tool('nisb_favorites_toggle_file', { path, type, workspace_id: effectiveWorkspaceId.value })
        const info = getInfo(res, t('files.controller.messages.favoritesUpdated'))
        if (info.success) {
          applyToggleResult(getDataValue(res, 'item', null), !!getDataValue(res, 'pinned', false))
        }
      } catch {}
      _schedule_favorites_refresh_event(60)
    }
  }

  async function on_path_renamed(evt) {
    const d = evt?.detail || {}
    const oldPath = normalize_path(d.old_path)
    const newPath = normalize_path(d.new_path)
    const type = normalize_type(d.type)
    if (!oldPath || !newPath || oldPath === newPath) return

    patchUiPathsAfterRename(oldPath, newPath)

    const hadOld = isFavoriteExact(oldPath, type)
    if (!hadOld) return

    const alreadyNew = isFavoriteExact(newPath, type)

    try {
      await favorite_call_tool('nisb_favorites_toggle_file', { path: oldPath, type, workspace_id: effectiveWorkspaceId.value })
    } catch {}

    if (!alreadyNew) {
      try {
        await favorite_call_tool('nisb_favorites_toggle_file', { path: newPath, type, workspace_id: effectiveWorkspaceId.value })
      } catch {}
    }

    _schedule_favorites_refresh_event(60)
  }

  function ensureExpandedForPath(path) {
    if (!path) return
    const segments = String(path).split('/')
    if (segments.length <= 1) return
    for (let i = 0; i < segments.length - 1; i++) {
      const prefix = segments.slice(0, i + 1).join('/')
      if (!expandedPaths.value.includes(prefix)) expandedPaths.value.push(prefix)
    }
  }

  function revealPathInTree(path, delay = 60) {
    const p = normalize_path(path)
    if (!p) return

    const pulse = (ms) => {
      window.setTimeout(() => {
        if (!__alive) return
        scrollTargetPath.value = ''
        window.setTimeout(() => {
          if (!__alive) return
          scrollTargetPath.value = p
        }, 16)
      }, ms)
    }

    pulse(delay)
    pulse(delay + 180)
    pulse(delay + 520)
    pulse(delay + 980)

    window.setTimeout(() => {
      if (!__alive) return
      if (scrollTargetPath.value === p) scrollTargetPath.value = ''
    }, delay + 1800)
  }


  function openFavorite(fav) {
    const path = normalize_path(String(fav?.path || '').trim().replace(/^\/+/, ''))
    const type = normalize_type(fav?.type) || 'file'
    const name = get_base_name(path)
    if (!path) return

    if (type === 'directory') {
      _dispatch_async(
        'nisb_file_focus_root',
        {
          path,
          source: 'favorite_directory'
        },
        0
      )
      return
    }

    selectedPath.value = path
    ensureExpandedForPath(path)
    saveTreeState()
    revealPathInTree(path, 70)
    _dispatch_async('nisb-open-file', { path, name }, 0)
  }

  function onFavoriteContextMenu(fav, e) {
    const path = String(fav?.path || '').trim().replace(/^\/+/, '')
    if (!path) return
    const type = normalize_type(fav?.type) || 'file'
    const isDir = type === 'directory'
    const isFocused = isDir && focusedRootPath.value === path

    _dispatch_async(
      'file-context-menu',
      {
        x: e.clientX,
        y: e.clientY,
        targetType: 'file',
        targetFileType: type,
        targetName: get_base_name(path),
        path,
        name: get_base_name(path),
        type,
        ws: effectiveWorkspaceId.value,
        favoriteHighlightColor: normalize_favorite_highlight_color(fav?.highlight_color),
        extensions: [
          {
            id: 'focus_root',
            title: t('files.contextMenu.focusThisDirectory'),
            visible: isDir && !isFocused,
            payload: { path }
          },
          {
            id: 'clear_focus_root',
            title: t('files.contextMenu.clearFocus'),
            visible: isDir && isFocused,
            payload: {}
          }
        ]
      },
      0
    )
  }

  async function toggleFavoriteFromList(fav) {
    try {
      const res = await favorite_call_tool('nisb_favorites_toggle_file', {
        path: fav.path,
        type: fav.type || 'file',
        workspace_id: effectiveWorkspaceId.value
      })
      const info = getInfo(res, t('files.controller.messages.favoritesUpdated'))
      if (info.success) {
        applyToggleResult(getDataValue(res, 'item', null), !!getDataValue(res, 'pinned', false))
        const pinned = !!getDataValue(res, 'pinned', false)
        _dispatch_async(
          'nisb-toast',
          {
            message: pinned
              ? t('files.controller.messages.addedToFavorites', { name: get_base_name(fav.path) })
              : t('files.controller.messages.removedFromFavorites', { name: get_base_name(fav.path) }),
            type: 'info'
          },
          0
        )
        _schedule_favorites_refresh_event(50)
      } else {
        _dispatch_async(
          'nisb-toast',
          {
            message: info.text || t('files.controller.messages.actionFailed'),
            type: 'error'
          },
          0
        )
      }
    } catch (e) {
      _dispatch_async(
        'nisb-toast',
        {
          message: e?.message || String(e),
          type: 'error'
        },
        0
      )
    }
  }

  function handleSelect(path) {
    selectedPath.value = path
    saveTreeState()
  }

  function handleSetCurrentPath(path) {
    currentPath.value = path
    _dispatch_async('nisb-current-dir-changed', { path }, 0)
    saveTreeState()
  }

  function handleToggleExpand(payload) {
    const { path, expanded } = payload || {}
    if (!path) return
    const idx = expandedPaths.value.indexOf(path)
    if (expanded && idx === -1) expandedPaths.value.push(path)
    else if (!expanded && idx !== -1) expandedPaths.value.splice(idx, 1)
    saveTreeState()
  }

  function onFileTreeFocusPath(evt) {
    const d = evt?.detail || {}
    const rawPath = String(d.path || '').trim().replace(/^\/+/, '')
    if (!rawPath) return
    const type = String(d.type || '').toLowerCase()
    const isDir = type === 'directory' || type === 'dir'

    selectedPath.value = rawPath
    ensureExpandedForPath(rawPath)
    scrollTargetPath.value = rawPath

    if (isDir) {
      currentPath.value = rawPath
      _dispatch_async('nisb-current-dir-changed', { path: rawPath }, 0)
    } else {
      const parent = get_parent_dir(rawPath)
      currentPath.value = parent
      _dispatch_async('nisb-current-dir-changed', { path: parent }, 0)
    }

    saveTreeState()
  }

  function onGlobalFocusRoot(evt) {
    const p = String(evt?.detail?.path || '').trim()
    if (!p) return

    if (__global_focus_timer) _clear_timer(__global_focus_timer)
    __global_focus_timer = window.setTimeout(() => {
      __global_focus_timer = null
      if (!__alive) return
      focusRoot(p, { silent: true })
    }, 16)
  }

  function onGlobalClearFocusRoot() {
    if (__global_clear_focus_timer) _clear_timer(__global_clear_focus_timer)
    __global_clear_focus_timer = window.setTimeout(() => {
      __global_clear_focus_timer = null
      if (!__alive) return
      clearFocusRoot({ silent: true })
    }, 16)
  }

  function getCreateBaseDir() {
    if (currentPath.value) return currentPath.value
    if (focusedRootPath.value) return focusedRootPath.value
    if (selectedPath.value) {
      const parent = get_parent_dir(selectedPath.value)
      if (parent) return parent
    }
    return ''
  }

  function handleGlobalCreateMenu() {
    const baseDir = getCreateBaseDir()
    const rect = root_plus_btn_el?.value?.getBoundingClientRect?.()
    const x = rect ? rect.left : 16
    const y = rect ? rect.bottom : 16
    _dispatch_async('file-context-menu', { x, y, targetType: 'create', baseDir }, 0)
  }

  async function _run_file_tree_refresh(runSeq) {
    await loadRoot()
    if (!__alive || runSeq !== __tree_refresh_run_seq) return
    restoreTreeState()
    await loadFavorites()
  }

  function onFileTreeRefresh() {
    const runSeq = ++__tree_refresh_run_seq

    if (__file_tree_refresh_timer) _clear_timer(__file_tree_refresh_timer)
    __file_tree_refresh_timer = window.setTimeout(() => {
      __file_tree_refresh_timer = null
      if (!__alive || runSeq !== __tree_refresh_run_seq) return
      _run_file_tree_refresh(runSeq)
    }, 32)
  }

  watch(
    () => effectiveWorkspaceId.value,
    () => {
      const runSeq = ++__workspace_run_seq

      if (__workspace_watch_timer) _clear_timer(__workspace_watch_timer)
      __workspace_watch_timer = window.setTimeout(async () => {
        if (!__alive || runSeq !== __workspace_run_seq) return

        restoreFocusRoot()
        await loadRoot()
        if (!__alive || runSeq !== __workspace_run_seq) return

        restoreTreeState()
        await loadFavorites()
        if (!__alive || runSeq !== __workspace_run_seq) return

        await nextTick()
        if (!__alive || runSeq !== __workspace_run_seq) return
        scrollRootRowToOneThird()
      }, 0)
    },
    { immediate: true }
  )

  const batchSelectedCount = computed(() => {
    try {
      return Object.keys(batchSelectedMap.value || {}).length
    } catch {
      return 0
    }
  })

  function _toast(message, type = 'info', duration = 2200) {
    _dispatch_async('nisb-toast', { message, type, duration }, 0)
  }

  function _sleep(ms) {
    return new Promise((r) => setTimeout(r, ms))
  }

  function _batch_key_from_map(map) {
    const keys = Object.keys(map || {}).filter(Boolean).sort()
    return keys.join('|')
  }

  function clearBatchSelection() {
    batchSelectedMap.value = {}
    pendingBatchDelete.value = { ts: 0, key: '' }
  }

  function isBatchSelected(path) {
    const p = normalize_path(path)
    if (!p) return false
    return !!(batchSelectedMap.value && batchSelectedMap.value[p])
  }

  function setBatchSelected(path, checked, meta) {
    const p = normalize_path(path)
    if (!p) return

    const cur = batchSelectedMap.value && typeof batchSelectedMap.value === 'object' ? batchSelectedMap.value : {}
    const next = { ...cur }

    if (checked) {
      next[p] = {
        type: String(meta?.type || ''),
        name: String(meta?.name || get_base_name(p) || '')
      }
    } else {
      delete next[p]
    }

    batchSelectedMap.value = next
    pendingBatchDelete.value = { ts: 0, key: '' }
  }

  function toggleBatchSelect(path) {
    const p = normalize_path(path)
    if (!p) return
    setBatchSelected(p, !isBatchSelected(p), batchSelectedMap.value?.[p] || {})
  }

  function selectAllCurrentLevel() {
    if (!batchMode.value) return

    const list = Array.isArray(entries.value) ? entries.value : []
    const next = {}
    for (const it of list) {
      const p = normalize_path(it?.path)
      if (!p) continue
      next[p] = { type: String(it?.type || ''), name: String(it?.name || get_base_name(p) || '') }
    }

    batchSelectedMap.value = next
    pendingBatchDelete.value = { ts: 0, key: '' }
  }

  function toggleBatchMode(force) {
    const next = typeof force === 'boolean' ? force : !batchMode.value

    if (next) {
      const focus = normalize_path(focusedRootPath.value)
      if (!focus) {
        _toast(t('files.controller.messages.focusBeforeBatchAction'), 'info', 2600)
        return
      }
      batchMode.value = true
      clearBatchSelection()
      return
    }

    batchMode.value = false
    clearBatchSelection()
  }

  function _normalize_dir(s) {
    return String(s || '')
      .trim()
      .replace(/\\/g, '/')
      .replace(/^\/+/, '')
      .replace(/\/+$/, '')
  }

  function _base_name_from_path(p) {
    return get_base_name(p) || String(p || '').split('/').filter(Boolean).pop() || String(p || '')
  }

  function _is_in_focus(path, focus_dir) {
    const p = normalize_path(path)
    const f = normalize_path(focus_dir)
    if (!p || !f) return false
    if (p === f) return true
    return p.startsWith(f + '/')
  }

  function _fold_descendants(items) {
    const list = Array.isArray(items) ? items.slice() : []
    list.sort((a, b) => String(a.path || '').length - String(b.path || '').length)

    const selected_dirs = []
    const out = []
    let ignored = 0

    for (const it of list) {
      const p = normalize_path(it?.path)
      if (!p) continue

      let covered = false
      for (const dirp of selected_dirs) {
        if (p.startsWith(dirp + '/')) {
          covered = true
          break
        }
      }
      if (covered) {
        ignored += 1
        continue
      }

      out.push(it)
      if (String(it?.type || '') === 'directory') selected_dirs.push(p)
    }

    return { items: out, ignored }
  }

  function _get_selected_items_list() {
    const map = batchSelectedMap.value && typeof batchSelectedMap.value === 'object' ? batchSelectedMap.value : {}
    return Object.keys(map)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b))
      .map((path) => {
        const m = map[path] || {}
        return {
          path,
          type: String(m.type || ''),
          name: String(m.name || _base_name_from_path(path))
        }
      })
  }

  async function _run_pool(tasks, concurrency = 2) {
    const c = Math.max(1, Math.min(6, Number(concurrency || 2)))
    let i = 0
    const results = []

    async function worker() {
      while (true) {
        const idx = i
        i += 1
        if (idx >= tasks.length) return
        try {
          results[idx] = await tasks[idx]()
        } catch (e) {
          results[idx] = { ok: false, error: e }
        }
      }
    }

    const workers = Array.from({ length: Math.min(c, tasks.length) }, () => worker())
    await Promise.all(workers)
    return results
  }

  async function batchDeleteSelected() {
    if (!batchMode.value) return

    const map = batchSelectedMap.value && typeof batchSelectedMap.value === 'object' ? batchSelectedMap.value : {}
    const paths = Object.keys(map).filter(Boolean)

    if (!paths.length) {
      _toast(t('files.controller.messages.noSelection'), 'info', 2200)
      return
    }

    const key = _batch_key_from_map(map)
    const now = Date.now()
    const pending = pendingBatchDelete.value || { ts: 0, key: '' }

    if (!pending.ts || pending.key !== key || now - pending.ts > 5000) {
      pendingBatchDelete.value = { ts: now, key }
      _toast(t('files.controller.messages.batchDeleteConfirmAgain', { count: paths.length }), 'warning', 2600)
      return
    }

    pendingBatchDelete.value = { ts: 0, key: '' }

    try {
      _toast(t('files.controller.messages.batchDeleteStarted', { count: paths.length }), 'info', 2200)
      const r = await call_tool('nisb_fs_bulk_delete', { paths, reason: 'filebrowser_batch_delete' })
      const info = getInfo(r, t('files.controller.messages.movedToTrash'))

      if (info.success) {
        _toast(info.text || t('files.controller.messages.movedToTrash'), info.isWarning ? 'warning' : 'success', 2200)
        onFileTreeRefresh()
        _schedule_timeline_refresh_event(50)
        toggleBatchMode(false)
      } else {
        _toast(
          t('files.controller.messages.batchDeleteFailed', {
            error: info.text || t('files.controller.messages.unknownError')
          }),
          'error',
          3200
        )
      }
    } catch (e) {
      _toast(
        t('files.controller.messages.batchDeleteException', {
          error: e?.message || String(e)
        }),
        'error',
        3200
      )
    }
  }

  function _is_descendant_path(child, parent) {
    const c = normalize_path(child)
    const p = normalize_path(parent)
    if (!c || !p) return false
    if (c === p) return false
    return c.startsWith(p + '/')
  }

  async function batchMoveSelected() {
    if (!batchMode.value) return

    const focus = _normalize_dir(focusedRootPath.value)
    if (!focus) {
      _toast(t('files.controller.messages.focusBeforeBatchMove'), 'info', 2600)
      return
    }

    let items = _get_selected_items_list()
    if (!items.length) {
      _toast(t('files.controller.messages.noSelection'), 'info', 2200)
      return
    }

    items = items.filter((it) => _is_in_focus(it.path, focus))
    if (!items.length) {
      _toast(t('files.controller.messages.selectionNotInFocusedDir'), 'warning', 2800)
      return
    }

    const folded = _fold_descendants(items)
    items = folded.items

    const dest_dir = await open_batch_move_modal({
      count: items.length,
      focus_dir: focus,
      default_dest_dir: focus
    })
    if (!dest_dir) return

    const dest = _normalize_dir(dest_dir)
    if (!dest) {
      _toast(t('files.controller.messages.destinationRequired'), 'error', 2500)
      return
    }

    if (folded.ignored) {
      _toast(
        t('files.controller.messages.ignoredDescendants', { count: folded.ignored }),
        'info',
        2600
      )
    }

    _toast(
      t('files.controller.messages.batchMoveStarted', {
        count: items.length,
        dest
      }),
      'info',
      2400
    )
    await _sleep(50)

    let ok_n = 0
    let fail_n = 0
    const fail_msgs = []

    let last_toast_ts = 0

    const tasks = items.map((it, idx) => async () => {
      const i = idx + 1
      const total = items.length

      const name = it.name || _base_name_from_path(it.path)
      const old_path = normalize_path(it.path)
      const new_path = dest ? `${dest}/${name}` : name

      if (it.type === 'directory' && (new_path === old_path || _is_descendant_path(dest, old_path))) {
        fail_n += 1
        fail_msgs.push(
          t('files.controller.messages.cannotMoveIntoSelf', {
            name
          })
        )
        return { ok: false }
      }

      const now = Date.now()
      if (now - last_toast_ts > 350 || i === 1 || i === total) {
        last_toast_ts = now
        _toast(
          t('files.controller.messages.moveProgress', {
            index: i,
            total,
            name
          }),
          'info',
          1200
        )
      }

      let r
      if (it.type === 'directory') r = await call_tool('nisb_dir_move_path', { old_path, new_path })
      else r = await call_tool('nisb_file_move_path', { old_path, new_path })

      const info = getInfo(r, t('files.controller.messages.moveCompleted'))
      if (info.success) {
        ok_n += 1
        _dispatch_async('nisb_path_renamed', { old_path, new_path, type: it.type || 'file' }, 0)
        return { ok: true }
      }

      fail_n += 1
      fail_msgs.push(
        t('files.controller.messages.moveFailed', {
          name,
          error: String(info.text || t('files.controller.messages.defaultMoveFailed'))
        })
      )
      return { ok: false }
    })

    await _run_pool(tasks, 2)

    onFileTreeRefresh()

    if (fail_n) {
      _toast(
        t('files.controller.messages.batchMoveSummaryWarning', {
          success: ok_n,
          failed: fail_n
        }),
        'warning',
        3200
      )
      _toast(fail_msgs.slice(0, 2).join(t('files.controller.messages.failJoiner')), 'warning', 3800)
    } else {
      _toast(
        t('files.controller.messages.batchMoveSummarySuccess', {
          count: ok_n
        }),
        'success',
        2600
      )
    }

    toggleBatchMode(false)
  }

  function _split_ext(name) {
    const s = String(name || '')
    const idx = s.lastIndexOf('.')
    if (idx <= 0) return { base: s, ext: '' }
    return { base: s.slice(0, idx), ext: s.slice(idx) }
  }

  function _pad_num(n, width) {
    const w = Math.max(0, Math.min(12, Number(width || 0)))
    const s = String(Math.max(0, Number(n || 0)))
    if (!w) return s
    return s.length >= w ? s : '0'.repeat(w - s.length) + s
  }

  function _apply_rules_to_name(old_name, type, rules, seq_num) {
    const apply_to = String(rules?.apply_to || 'files')
    const should =
      apply_to === 'all' ||
      (apply_to === 'files' && type === 'file') ||
      (apply_to === 'dirs' && type === 'directory')

    if (!should) return old_name

    const is_file = type === 'file'
    const { base, ext } = is_file ? _split_ext(old_name) : { base: old_name, ext: '' }

    let b = base

    const f = String(rules?.find_text || '')
    const r = String(rules?.replace_text || '')
    if (f) b = b.split(f).join(r)

    b = String(rules?.prefix || '') + b + String(rules?.suffix || '')

    if (rules?.numbering_enabled) {
      const delim = String(rules?.numbering_delim || '_')
      const pad = Number(rules?.numbering_pad || 0)
      const num = _pad_num(seq_num, pad)
      b = b + delim + num
    }

    return is_file ? b + ext : b
  }

  async function batchRenameSelected() {
    if (!batchMode.value) return

    const focus = _normalize_dir(focusedRootPath.value)
    if (!focus) {
      _toast(t('files.controller.messages.focusBeforeBatchRename'), 'info', 2600)
      return
    }

    let items = _get_selected_items_list()
    if (!items.length) {
      _toast(t('files.controller.messages.noSelection'), 'info', 2200)
      return
    }

    items = items.filter((it) => _is_in_focus(it.path, focus))
    if (!items.length) {
      _toast(t('files.controller.messages.selectionNotInFocusedDir'), 'warning', 2800)
      return
    }

    const folded = _fold_descendants(items)
    items = folded.items

    const rules = await open_batch_rename_modal({
      count: items.length,
      focus_dir: focus,
      items
    })
    if (!rules) return

    if (folded.ignored) {
      _toast(
        t('files.controller.messages.ignoredDescendants', { count: folded.ignored }),
        'info',
        2600
      )
    }

    _toast(
      t('files.controller.messages.batchRenameStarted', {
        count: items.length
      }),
      'info',
      2200
    )
    await _sleep(60)

    let ok_n = 0
    let fail_n = 0
    const fail_msgs = []

    let seq = Number(rules.numbering_start || 1)
    let last_toast_ts = 0

    const tasks = items.map((it, idx) => async () => {
      const i = idx + 1
      const total = items.length

      const old_path = normalize_path(it.path)
      const old_name = it.name || _base_name_from_path(old_path)
      const parent = get_parent_dir(old_path) || ''
      const new_name = _apply_rules_to_name(old_name, it.type, rules, rules.numbering_enabled ? seq++ : 0)

      if (!new_name || new_name === old_name) return { ok: true, skipped: true }

      const now = Date.now()
      if (now - last_toast_ts > 350 || i === 1 || i === total) {
        last_toast_ts = now
        _toast(
          t('files.controller.messages.renameProgress', {
            index: i,
            total,
            name: old_name
          }),
          'info',
          1200
        )
      }

      let r
      if (it.type === 'directory') {
        const new_path = parent ? `${parent}/${new_name}` : new_name
        r = await call_tool('nisb_dir_move_path', { old_path, new_path })
        const info = getInfo(r, t('files.controller.messages.renameCompleted'))
        if (info.success) {
          ok_n += 1
          _dispatch_async('nisb_path_renamed', { old_path, new_path, type: 'directory' }, 0)
          return { ok: true }
        }
        fail_n += 1
        fail_msgs.push(
          t('files.controller.messages.renameFailed', {
            name: old_name,
            error: String(info.text || t('files.controller.messages.defaultRenameFailed'))
          })
        )
        return { ok: false }
      }

      r = await call_tool('nisb_file_rename', { old_path, new_name })
      const info = getInfo(r, t('files.controller.messages.renameCompleted'))
      if (info.success) {
        ok_n += 1
        const new_path = parent ? `${parent}/${new_name}` : new_name
        _dispatch_async('nisb_path_renamed', { old_path, new_path, type: it.type || 'file' }, 0)
        return { ok: true }
      }

      fail_n += 1
      fail_msgs.push(
        t('files.controller.messages.renameFailed', {
          name: old_name,
          error: String(info.text || t('files.controller.messages.defaultRenameFailed'))
        })
      )
      return { ok: false }
    })

    await _run_pool(tasks, 2)

    onFileTreeRefresh()

    if (fail_n) {
      _toast(
        t('files.controller.messages.batchRenameSummaryWarning', {
          success: ok_n,
          failed: fail_n
        }),
        'warning',
        3200
      )
      _toast(fail_msgs.slice(0, 2).join(t('files.controller.messages.failJoiner')), 'warning', 3800)
    } else {
      _toast(
        t('files.controller.messages.batchRenameSummarySuccess', {
          count: ok_n
        }),
        'success',
        2600
      )
    }

    toggleBatchMode(false)
  }

  watch(
    () => focusedRootPath.value,
    () => {
      if (batchMode.value) toggleBatchMode(false)
    }
  )

  onMounted(() => {
    __alive = true
    window.addEventListener('nisb-file-tree-refresh', onFileTreeRefresh)
    window.addEventListener('nisb-file-tree-focus-path', onFileTreeFocusPath)
    window.addEventListener('nisb-favorites-refresh', loadFavorites)
    window.addEventListener('nisb-copy-internal-link', on_copy_internal_link)
    window.addEventListener('nisb_file_focus_root', onGlobalFocusRoot)
    window.addEventListener('nisb_file_clear_focus_root', onGlobalClearFocusRoot)
    window.addEventListener('nisb-favorites-toggle', on_favorites_toggle)
    window.addEventListener('nisb-favorites-highlight-set', on_favorites_highlight_set)
    window.addEventListener('nisb-favorites-highlight-clear', on_favorites_highlight_clear)
    window.addEventListener('nisb_path_renamed', on_path_renamed)
    window.addEventListener('nisb_path_deleted', on_path_deleted)
  })

  onUnmounted(() => {
    __alive = false

    if (__favorites_snapshot_timer) _clear_timer(__favorites_snapshot_timer)
    if (__favorites_refresh_event_timer) _clear_timer(__favorites_refresh_event_timer)
    if (__file_tree_refresh_timer) _clear_timer(__file_tree_refresh_timer)
    if (__timeline_refresh_event_timer) _clear_timer(__timeline_refresh_event_timer)
    if (__global_focus_timer) _clear_timer(__global_focus_timer)
    if (__global_clear_focus_timer) _clear_timer(__global_clear_focus_timer)
    if (__workspace_watch_timer) _clear_timer(__workspace_watch_timer)

    if (__focus_write_idle_id !== null) {
      _cancel_idle(__focus_write_idle_id)
      __focus_write_idle_id = null
    }
    if (__tree_state_write_idle_id !== null) {
      _cancel_idle(__tree_state_write_idle_id)
      __tree_state_write_idle_id = null
    }

    window.removeEventListener('nisb-file-tree-refresh', onFileTreeRefresh)
    window.removeEventListener('nisb-file-tree-focus-path', onFileTreeFocusPath)
    window.removeEventListener('nisb-favorites-refresh', loadFavorites)
    window.removeEventListener('nisb-copy-internal-link', on_copy_internal_link)
    window.removeEventListener('nisb_file_focus_root', onGlobalFocusRoot)
    window.removeEventListener('nisb_file_clear_focus_root', onGlobalClearFocusRoot)
    window.removeEventListener('nisb-favorites-toggle', on_favorites_toggle)
    window.removeEventListener('nisb-favorites-highlight-set', on_favorites_highlight_set)
    window.removeEventListener('nisb-favorites-highlight-clear', on_favorites_highlight_clear)
    window.removeEventListener('nisb_path_renamed', on_path_renamed)
    window.removeEventListener('nisb_path_deleted', on_path_deleted)
  })

  return {
    loading,
    entries,
    selectedPath,
    currentPath,
    expandedPaths,
    scrollTargetPath,
    favorites,
    libraryStatusMap,
    focusedRootPath,

    batchMode,
    batchSelectedCount,
    isBatchSelected,
    setBatchSelected,
    toggleBatchSelect,
    selectAllCurrentLevel,
    toggleBatchMode,
    clearBatchSelection,
    batchDeleteSelected,
    batchMoveSelected,
    batchRenameSelected,

    effectiveWorkspaceId,
    focusSegments,
    favoriteDirs,
    favoriteFiles,
    favoriteMap,
    favoriteMetaMap,

    pathTip: path_tip,
    onFavEnter: on_fav_enter,
    onFavMove: on_fav_move,
    onFavLeave: on_fav_leave,

    getBaseName: get_base_name,
    getParentDir: get_parent_dir,
    isFocusedPath,

    focusRoot,
    clearFocusRoot,
    toggleFocusRoot,
    collapseAllDirs,
    openFavorite,
    onFavoriteContextMenu,
    toggleFavoriteFromList,
    setFavoriteHighlight,
    clearFavoriteHighlight,

    handleSelect,
    handleSetCurrentPath,
    handleToggleExpand,

    handleGlobalCreateMenu,

    applyToggleResult,
    refreshLibraryStatus
  }
}

