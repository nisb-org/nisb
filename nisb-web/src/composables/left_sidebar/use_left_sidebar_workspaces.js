// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/use_left_sidebar_workspaces.js
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

export function use_left_sidebar_workspaces({ call_tool }) {
  const { t } = useI18n()

  const LS_CURRENT_WORKSPACE_ID = 'nisb_current_workspace_id'
  const LS_FOCUS_ROOT_PREFIX = 'nisb_fs_focus_root_'

  const USER_WORKSPACE_GET_TOOL = 'nisb_user_workspace_get_current'
  const USER_WORKSPACE_SET_TOOL = 'nisb_user_workspace_set_current'

  const workspaces = ref([])
  const current_workspace = ref('workspace_work')
  const settings_modal_open = ref(false)

  const suppress_focus_persist = ref(false)

  let __alive = true

  let __load_workspaces_seq = 0
  let __restore_workspace_state_seq = 0
  let __workspace_switch_seq = 0
  let __focus_persist_seq = 0

  let __favorites_refresh_timer = null
  let __file_tree_refresh_timer = null
  let __workspace_switch_finish_timer = null
  let __focus_persist_timer = null
  let __clear_focus_persist_timer = null
  let __suppress_focus_release_timer = null

  let __ls_current_workspace_idle_id = null
  let __ls_focus_root_idle_id = null
  let __pending_ls_current_workspace = null
  let __pending_ls_focus_root = null

  function safe_string(v) {
    return v === null || v === undefined ? '' : String(v)
  }

  function safe_array(v) {
    return Array.isArray(v) ? v : []
  }

  function safe_object(v) {
    return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
  }

  function unwrap_result(res) {
    if (res && typeof res === 'object' && res.result && typeof res.result === 'object') {
      return res.result
    }
    return res || {}
  }

  function normalized_status(data) {
    const raw = safe_string(data?.status).trim().toLowerCase()
    if (raw) return raw
    if (data?.success === false) return 'error'
    if (data?.success === true) return 'success'
    return ''
  }

  function assert_tool_success(res, fallback_message = '') {
    const fallback = safe_string(fallback_message || t('workspace.operationFailed')).trim() || 'Operation failed'
    const data = unwrap_result(res)
    const status = normalized_status(data)

    if (status && status !== 'success') {
      throw new Error(safe_string(data?.message || fallback) || fallback)
    }
    if (data?.success === false) {
      throw new Error(safe_string(data?.message || fallback) || fallback)
    }

    return data
  }

  function pick_first_tool_result(data, matcher) {
    const rows = safe_array(data?.tool_results)
    for (const row of rows) {
      if (!row || typeof row !== 'object') continue
      if (matcher(row)) return row
    }
    return null
  }

  function is_workspace_id_safe(wid) {
    const s = safe_string(wid).trim()
    return /^workspace_[a-z0-9_]+$/.test(s)
  }

  function _clear_timer(id) {
    try {
      clearTimeout(id)
    } catch {}
  }

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

  function dispatch_toast(message, type = 'success') {
    _dispatch_async('nisb-toast', { message, type }, 0)
  }

  function _begin_suppress_focus_persist() {
    suppress_focus_persist.value = true
    if (__suppress_focus_release_timer) {
      _clear_timer(__suppress_focus_release_timer)
      __suppress_focus_release_timer = null
    }
  }

  function _end_suppress_focus_persist_later(delay = 180) {
    if (__suppress_focus_release_timer) {
      _clear_timer(__suppress_focus_release_timer)
      __suppress_focus_release_timer = null
    }

    __suppress_focus_release_timer = window.setTimeout(() => {
      __suppress_focus_release_timer = null
      if (!__alive) return
      suppress_focus_persist.value = false
    }, Math.max(0, Number(delay || 0)))
  }

  function _emit_workspace_switch_state(payload = {}) {
    try {
      const prev = safe_object(window.__nisb_workspace_switch_state)
      const next = {
        running: !!payload.running,
        seq: Number(payload.seq || prev.seq || 0),
        workspace_id: safe_string(payload.workspace_id || prev.workspace_id).trim(),
        started_at: Number(payload.started_at || prev.started_at || 0),
        finished_at: Number(payload.finished_at || 0),
        ok: payload.ok === undefined ? true : !!payload.ok
      }
      window.__nisb_workspace_switch_state = next
      _dispatch_async('nisb-workspace-switch-state', next, 0)
    } catch {}
  }

  function _mark_workspace_switch_start(workspace_id, seq) {
    _emit_workspace_switch_state({
      running: true,
      seq,
      workspace_id,
      started_at: Date.now(),
      finished_at: 0,
      ok: true
    })
  }

  function _mark_workspace_switch_finish(workspace_id, seq, ok = true, delay = 160) {
    if (__workspace_switch_finish_timer) {
      _clear_timer(__workspace_switch_finish_timer)
      __workspace_switch_finish_timer = null
    }

    __workspace_switch_finish_timer = window.setTimeout(() => {
      __workspace_switch_finish_timer = null
      if (!__alive) return
      if (seq !== __workspace_switch_seq) return

      _emit_workspace_switch_state({
        running: false,
        seq,
        workspace_id,
        started_at: safe_object(window.__nisb_workspace_switch_state).started_at || 0,
        finished_at: Date.now(),
        ok
      })
    }, Math.max(0, Number(delay || 0)))
  }

  function _schedule_ls_current_workspace_write(workspace_id) {
    __pending_ls_current_workspace = safe_string(workspace_id || 'workspace_work').trim() || 'workspace_work'

    if (__ls_current_workspace_idle_id !== null) {
      _cancel_idle(__ls_current_workspace_idle_id)
      __ls_current_workspace_idle_id = null
    }

    __ls_current_workspace_idle_id = _request_idle(
      () => {
        __ls_current_workspace_idle_id = null
        const v = __pending_ls_current_workspace
        __pending_ls_current_workspace = null
        if (!__alive) return
        try {
          localStorage.setItem(LS_CURRENT_WORKSPACE_ID, v)
        } catch {}
      },
      { timeout: 1200 }
    )
  }

  function _schedule_ls_focus_root_write(workspace_id, focused_root_path) {
    const wid = safe_string(workspace_id || 'workspace_work').trim() || 'workspace_work'
    const focused = safe_string(focused_root_path).trim().replace(/^\/+/, '')

    __pending_ls_focus_root = {
      key: `${LS_FOCUS_ROOT_PREFIX}${wid}`,
      focused
    }

    if (__ls_focus_root_idle_id !== null) {
      _cancel_idle(__ls_focus_root_idle_id)
      __ls_focus_root_idle_id = null
    }

    __ls_focus_root_idle_id = _request_idle(
      () => {
        __ls_focus_root_idle_id = null
        const payload = __pending_ls_focus_root
        __pending_ls_focus_root = null
        if (!__alive || !payload?.key) return
        try {
          if (payload.focused) localStorage.setItem(payload.key, payload.focused)
          else localStorage.removeItem(payload.key)
        } catch {}
      },
      { timeout: 1200 }
    )
  }

  function persist_current_workspace_local(wid) {
    _schedule_ls_current_workspace_write(wid)
  }

  function read_current_workspace_local() {
    try {
      return safe_string(localStorage.getItem(LS_CURRENT_WORKSPACE_ID)).trim()
    } catch {
      return ''
    }
  }

  function extract_current_workspace_id(data) {
    const row = pick_first_tool_result(
      data,
      (x) =>
        (x.type === 'user_workspace_current' || x.type === 'workspace_current') &&
        safe_string(x.current_workspace_id).trim()
    )

    if (row) return safe_string(row.current_workspace_id).trim()
    return safe_string(data?.current_workspace_id).trim()
  }

  function extract_workspace_list(data) {
    const row = pick_first_tool_result(
      data,
      (x) => x.type === 'workspace_list' && Array.isArray(x.workspaces)
    )
    if (row) return safe_array(row.workspaces)
    return safe_array(data?.workspaces)
  }

  function extract_workspace_files_state(data) {
    const row = pick_first_tool_result(
      data,
      (x) => x.type === 'workspace_files_state' && x.files_state && typeof x.files_state === 'object'
    )

    if (row) {
      return {
        workspace_id: safe_string(row.workspace_id).trim(),
        files_state: safe_object(row.files_state),
        last_updated: safe_string(row.last_updated).trim(),
        migrate_stats: safe_object(row.migrate_stats)
      }
    }

    return {
      workspace_id: safe_string(data?.workspace_id).trim(),
      files_state: safe_object(data?.files_state),
      last_updated: safe_string(data?.last_updated).trim(),
      migrate_stats: safe_object(data?.migrate_stats)
    }
  }

  async function backend_get_current_workspace_id() {
    try {
      const raw = await call_tool(USER_WORKSPACE_GET_TOOL, {})
      const data = unwrap_result(raw)
      const status = normalized_status(data)
      const wid = extract_current_workspace_id(data)
      if ((!status || status === 'success') && is_workspace_id_safe(wid)) return wid
    } catch {}
    return ''
  }

  async function backend_set_current_workspace_id(wid) {
    const v = safe_string(wid).trim()
    if (!is_workspace_id_safe(v)) return
    try {
      await call_tool(USER_WORKSPACE_SET_TOOL, { workspace_id: v })
    } catch {}
  }

  const current_workspace_name = computed(() => {
    const wid = current_workspace.value
    const ws = safe_array(workspaces.value).find((w) => safe_string(w?.id) === wid)
    return safe_string(ws?.name)
  })

  function _schedule_workspace_apply_ui({ workspace_id, focused, switch_seq = 0, delay_base = 0 }) {
    const wid = safe_string(workspace_id).trim()
    const path = safe_string(focused).trim().replace(/^\/+/, '')

    _schedule_ls_focus_root_write(wid, path)

    if (path) {
      _dispatch_async('nisb_file_focus_root', { path }, delay_base + 0)
    } else {
      _dispatch_async('nisb_file_clear_focus_root', {}, delay_base + 0)
    }

    if (__favorites_refresh_timer) {
      _clear_timer(__favorites_refresh_timer)
      __favorites_refresh_timer = null
    }
    __favorites_refresh_timer = window.setTimeout(() => {
      __favorites_refresh_timer = null
      if (!__alive) return
      if (switch_seq && switch_seq !== __workspace_switch_seq) return
      window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    }, delay_base + 28)

    if (__file_tree_refresh_timer) {
      _clear_timer(__file_tree_refresh_timer)
      __file_tree_refresh_timer = null
    }
    __file_tree_refresh_timer = window.setTimeout(() => {
      __file_tree_refresh_timer = null
      if (!__alive) return
      if (switch_seq && switch_seq !== __workspace_switch_seq) return
      window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    }, delay_base + 64)
  }

  async function init_workspace_from_backend_then_local() {
    const from_backend = await backend_get_current_workspace_id()
    if (is_workspace_id_safe(from_backend)) {
      current_workspace.value = from_backend
      persist_current_workspace_local(from_backend)
      return
    }

    const from_ls = read_current_workspace_local()
    if (is_workspace_id_safe(from_ls)) {
      current_workspace.value = from_ls
      persist_current_workspace_local(from_ls)
      return
    }

    current_workspace.value = 'workspace_work'
    persist_current_workspace_local('workspace_work')
  }

  async function restore_workspace_current_state() {
    const wid = safe_string(current_workspace.value).trim()
    if (!is_workspace_id_safe(wid)) return

    const restore_seq = ++__restore_workspace_state_seq

    _begin_suppress_focus_persist()
    try {
      const data = assert_tool_success(
        await call_tool('nisb_workspace_files_state_get', { workspace_id: wid }),
        t('workspace.getCurrentStateFailed')
      )

      if (!__alive || restore_seq !== __restore_workspace_state_seq) return

      const info = extract_workspace_files_state(data)
      const cur = safe_object(info.files_state?.current)
      const focused = safe_string(cur.focused_root_path).trim().replace(/^\/+/, '')

      _schedule_workspace_apply_ui({
        workspace_id: wid,
        focused,
        switch_seq: 0,
        delay_base: 0
      })
    } finally {
      _end_suppress_focus_persist_later(180)
    }
  }

  async function load_workspaces(options = {}) {
    const restore_current_state = options.restore_current_state !== false
    const load_seq = ++__load_workspaces_seq

    try {
      const data = assert_tool_success(
        await call_tool('nisb_workspace_list', {}),
        t('workspace.loadWorkspacesFailed')
      )

      if (!__alive || load_seq !== __load_workspaces_seq) return

      workspaces.value = extract_workspace_list(data)
    } catch (e) {
      console.error('[workspaces] load failed:', e)
      if (!__alive || load_seq !== __load_workspaces_seq) return
    }

    if (!__alive || load_seq !== __load_workspaces_seq) return

    const ids = new Set(safe_array(workspaces.value).map((w) => safe_string(w?.id)))
    if (!ids.has(current_workspace.value)) {
      if (ids.has('workspace_work')) current_workspace.value = 'workspace_work'
      else current_workspace.value = safe_string(workspaces.value?.[0]?.id || 'workspace_work') || 'workspace_work'
      persist_current_workspace_local(current_workspace.value)
    }

    if (restore_current_state) {
      await restore_workspace_current_state()
    }
  }

  async function handle_workspace_change() {
    const wid = safe_string(current_workspace.value).trim()
    const ws_name = safe_string(
      safe_array(workspaces.value).find((w) => safe_string(w?.id) === wid)?.name || wid
    )

    dispatch_toast(t('workspace.switchRestoring', { name: ws_name }), 'info')

    if (!is_workspace_id_safe(wid)) {
      dispatch_toast(t('workspace.invalidWorkspaceIdRestore'), 'error')
      return
    }

    const switch_seq = ++__workspace_switch_seq
    _mark_workspace_switch_start(wid, switch_seq)

    let focused = ''

    _begin_suppress_focus_persist()
    try {
      const data = assert_tool_success(
        await call_tool('nisb_workspace_files_state_apply', { workspace_id: wid }),
        t('workspace.restoreSnapshotFailed')
      )

      if (!__alive || switch_seq !== __workspace_switch_seq) return

      const info = extract_workspace_files_state(data)
      const cur = safe_object(info.files_state?.current)
      focused = safe_string(cur.focused_root_path).trim().replace(/^\/+/, '')

      _schedule_workspace_apply_ui({
        workspace_id: wid,
        focused,
        switch_seq,
        delay_base: 0
      })

      persist_current_workspace_local(wid)

      backend_set_current_workspace_id(wid).catch(() => {})
      _mark_workspace_switch_finish(wid, switch_seq, true, 180)
    } catch (e) {
      if (__alive && switch_seq === __workspace_switch_seq) {
        dispatch_toast(
          t('workspace.restoreSnapshotException', {
            error: e?.message || String(e)
          }),
          'error'
        )
        _mark_workspace_switch_finish(wid, switch_seq, false, 60)
      }
      return
    } finally {
      _end_suppress_focus_persist_later(200)
    }
  }

  function open_settings() {
    settings_modal_open.value = true
  }

  async function on_workspaces_refresh() {
    await load_workspaces({ restore_current_state: true })
  }

  async function on_workspace_switch_request(e) {
    const wid = safe_string(e?.detail?.workspace_id).trim()
    if (!is_workspace_id_safe(wid)) {
      dispatch_toast(t('workspace.invalidWorkspaceIdSwitch'), 'error')
      return
    }

    if (current_workspace.value === wid && !safe_object(window.__nisb_workspace_switch_state).running) {
      return
    }

    current_workspace.value = wid
    persist_current_workspace_local(wid)
    await handle_workspace_change()
  }

  function on_focus_root_persist(e) {
    const path = safe_string(e?.detail?.path).trim().replace(/^\/+/, '')
    const ws = safe_string(current_workspace.value || 'workspace_work').trim() || 'workspace_work'
    if (!path) return

    _schedule_ls_focus_root_write(ws, path)

    if (suppress_focus_persist.value) return
    if (!is_workspace_id_safe(ws)) return

    const seq = ++__focus_persist_seq

    if (__focus_persist_timer) {
      _clear_timer(__focus_persist_timer)
      __focus_persist_timer = null
    }

    __focus_persist_timer = window.setTimeout(async () => {
      __focus_persist_timer = null
      if (!__alive) return
      if (seq !== __focus_persist_seq) return
      if (suppress_focus_persist.value) return

      try {
        await call_tool('nisb_workspace_files_state_set', {
          workspace_id: ws,
          focused_root_path: path
        })
      } catch {}
    }, 80)
  }

  function on_clear_focus_root_persist() {
    const ws = safe_string(current_workspace.value || 'workspace_work').trim() || 'workspace_work'

    _schedule_ls_focus_root_write(ws, '')

    if (suppress_focus_persist.value) return
    if (!is_workspace_id_safe(ws)) return

    const seq = ++__focus_persist_seq

    if (__clear_focus_persist_timer) {
      _clear_timer(__clear_focus_persist_timer)
      __clear_focus_persist_timer = null
    }

    __clear_focus_persist_timer = window.setTimeout(async () => {
      __clear_focus_persist_timer = null
      if (!__alive) return
      if (seq !== __focus_persist_seq) return
      if (suppress_focus_persist.value) return

      try {
        await call_tool('nisb_workspace_files_state_set', {
          workspace_id: ws,
          focused_root_path: ''
        })
      } catch {}
    }, 80)
  }

  watch(
    () => current_workspace.value,
    (v) => persist_current_workspace_local(safe_string(v || 'workspace_work').trim() || 'workspace_work'),
    { immediate: false }
  )

  onUnmounted(() => {
    __alive = false

    if (__favorites_refresh_timer) _clear_timer(__favorites_refresh_timer)
    if (__file_tree_refresh_timer) _clear_timer(__file_tree_refresh_timer)
    if (__workspace_switch_finish_timer) _clear_timer(__workspace_switch_finish_timer)
    if (__focus_persist_timer) _clear_timer(__focus_persist_timer)
    if (__clear_focus_persist_timer) _clear_timer(__clear_focus_persist_timer)
    if (__suppress_focus_release_timer) _clear_timer(__suppress_focus_release_timer)

    if (__ls_current_workspace_idle_id !== null) {
      _cancel_idle(__ls_current_workspace_idle_id)
      __ls_current_workspace_idle_id = null
    }
    if (__ls_focus_root_idle_id !== null) {
      _cancel_idle(__ls_focus_root_idle_id)
      __ls_focus_root_idle_id = null
    }
  })

  return {
    workspaces,
    current_workspace,
    current_workspace_name,
    settings_modal_open,

    suppress_focus_persist,

    init_workspace_from_backend_then_local,
    load_workspaces,
    handle_workspace_change,
    open_settings,

    on_workspaces_refresh,
    on_workspace_switch_request,
    on_focus_root_persist,
    on_clear_focus_root_persist,

    persist_current_workspace_local
  }
}

