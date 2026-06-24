function normalize_text(raw) {
  return String(raw || '').replace(/\r\n/g, '\n').trim()
}

function normalize_tool_result(res) {
  if (res && typeof res === 'object' && res.result && typeof res.result === 'object') return res.result
  return res || {}
}

function assert_tool_success(res) {
  const data = normalize_tool_result(res)
  if (data?.status && data.status !== 'success') {
    throw new Error(String(data.message || '操作失败'))
  }
  if (data?.success === false) {
    throw new Error(String(data.message || '操作失败'))
  }
  return data
}

function dispatch_saved_event(detail) {
  try {
    window.dispatchEvent(new CustomEvent('nisb-room-workspace-saved', {
      detail: detail || {}
    }))
  } catch {}
}

function get_room_state_last_save(room_store) {
  const from_state = room_store?.roomState?.last_workspace_save
  if (from_state && typeof from_state === 'object') return from_state

  const from_local = room_store?.lastWorkspaceSave
  if (from_local && typeof from_local === 'object') return from_local

  return {}
}

function pick_non_empty_fields(source, keys = []) {
  const out = {}
  for (const key of keys) {
    const value = source?.[key]
    if (value === undefined || value === null) continue
    if (typeof value === 'string' && !value.trim()) continue
    out[key] = value
  }
  return out
}

function normalize_rel_path(value) {
  return String(value || '').trim().replace(/\\/g, '/').replace(/^\/+/, '')
}

function is_legacy_agent_notebook_target(data = {}) {
  const target_kind = String(data?.target_kind || '').trim().toLowerCase()
  const relative_path = normalize_rel_path(data?.relative_path || '')
  const scoped_path = normalize_rel_path(data?.scoped_path || '')
  if (target_kind === 'agent_notebook') return true
  if (relative_path.startsWith('_room_notebooks/')) return true
  if (scoped_path.includes('/_room_notebooks/')) return true
  return false
}

function build_saved_detail(save_data, room_id) {
  return {
    room_id: String(save_data.room_id || room_id),
    workspace_id: String(save_data.workspace_id || ''),
    focus_root: String(save_data.focus_root || ''),
    target_kind: String(save_data.target_kind || 'room_note'),
    relative_path: String(save_data.relative_path || ''),
    scoped_path: String(save_data.scoped_path || ''),
    agent_id: String(save_data.agent_id || ''),
    mode: String(save_data.mode || 'append'),
    title: String(save_data.title || ''),
    section_title: String(save_data.section_title || ''),
    message: String(save_data.message || '写入成功'),
  }
}

function build_confirm_detail(parse_data, room_id, text, room_store) {
  const last_save = get_room_state_last_save(room_store)
  return {
    room_id: String(room_id || ''),
    raw_input: String(text || ''),
    prompt_message: String(parse_data?.prompt_message || '请确认保存目标'),
    target_kind: String(parse_data?.target_kind || ''),
    relative_path: String(parse_data?.relative_path || ''),
    scoped_path: String(parse_data?.scoped_path || ''),
    agent_id: String(parse_data?.agent_id || ''),
    mode: String(parse_data?.mode || ''),
    title: String(parse_data?.title || ''),
    section_title: String(parse_data?.section_title || ''),
    last_target_kind: String(last_save?.target_kind || ''),
    last_relative_path: String(last_save?.relative_path || ''),
    last_scoped_path: String(last_save?.scoped_path || ''),
    last_agent_id: String(last_save?.agent_id || ''),
  }
}

export function use_room_natural_save({ room_store, call_tool, on_status } = {}) {
  function notify(message, is_error = false) {
    if (typeof on_status === 'function') {
      on_status(String(message || ''), !!is_error)
    }
  }

  async function call_room_tool(tool, args = {}, opts = {}) {
    if (typeof room_store?.callRoomTool === 'function') {
      return await room_store.callRoomTool(call_tool, tool, args, opts)
    }
    return await call_tool(tool, args, opts)
  }

  function record_last_workspace_save(detail) {
    if (typeof room_store?.recordLastWorkspaceSave === 'function') {
      room_store.recordLastWorkspaceSave({
        target_kind: detail.target_kind,
        relative_path: detail.relative_path,
        scoped_path: detail.scoped_path,
        agent_id: detail.agent_id,
        saved_at: new Date().toISOString(),
      })
      return
    }

    const state_last_save = get_room_state_last_save(room_store)
    room_store.lastWorkspaceSave = {
      ...state_last_save,
      target_kind: detail.target_kind,
      relative_path: detail.relative_path,
      scoped_path: detail.scoped_path,
      agent_id: detail.agent_id,
      saved_at: new Date().toISOString(),
    }
  }

  async function execute_room_save(room_id, text, save_args = {}) {
    const payload = {
      room_id,
      text,
      rebuild_index: true,
      ...pick_non_empty_fields(save_args, [
        'target_kind',
        'relative_path',
        'scoped_path',
        'agent_id',
        'mode',
        'title',
        'section_title',
      ]),
    }

    if (is_legacy_agent_notebook_target(payload)) {
      notify('Room 内 legacy role notebook / natural save 已收口，请直接发送给 Supervisor 处理。', true)
      return { handled: true, success: false, need_confirm: false, detail: null }
    }

    const save_data = assert_tool_success(await call_room_tool('nisb_room_save_from_text', payload))

    if (!save_data?.handled) {
      return { handled: false, success: false, detail: null }
    }

    if (is_legacy_agent_notebook_target(save_data)) {
      notify('Room 内 legacy role notebook / natural save 已收口，请直接发送给 Supervisor 处理。', true)
      return { handled: true, success: false, need_confirm: false, detail: null }
    }

    const detail = build_saved_detail(save_data, room_id)
    record_last_workspace_save(detail)
    dispatch_saved_event(detail)
    notify(`已写入：${detail.relative_path || detail.scoped_path || '目标文件'}`, false)

    return {
      handled: true,
      success: true,
      need_confirm: false,
      detail,
    }
  }

  async function maybe_handle_room_save_intent(raw_input) {
    const text = normalize_text(raw_input)
    const room_id = String(room_store?.roomId || '').trim()

    if (!room_id || !text) {
      return { handled: false, success: false, need_confirm: false, detail: null }
    }

    try {
      const parse_data = assert_tool_success(await call_room_tool('nisb_room_save_intent_parse', {
        room_id,
        text,
      }))

      if (!parse_data?.handled) {
        return { handled: false, success: false, need_confirm: false, detail: null }
      }

      if (is_legacy_agent_notebook_target(parse_data)) {
        notify('Room 内 legacy role notebook / natural save 已收口，请直接发送给 Supervisor 处理。', true)
        return { handled: false, success: false, need_confirm: false, detail: null }
      }

      if (parse_data?.need_confirm) {
        return {
          handled: true,
          success: false,
          need_confirm: true,
          detail: build_confirm_detail(parse_data, room_id, text, room_store),
        }
      }

      const inferred_save_args = pick_non_empty_fields(parse_data, [
        'target_kind',
        'relative_path',
        'scoped_path',
        'agent_id',
        'mode',
        'title',
        'section_title',
      ])

      if (is_legacy_agent_notebook_target(inferred_save_args)) {
        notify('Room 内 legacy role notebook / natural save 已收口，请直接发送给 Supervisor 处理。', true)
        return { handled: false, success: false, need_confirm: false, detail: null }
      }

      return await execute_room_save(room_id, text, inferred_save_args)
    } catch (error) {
      notify(String(error?.message || error || '写入失败'), true)
      return { handled: true, success: false, need_confirm: false, detail: null }
    }
  }

  async function confirm_room_save_intent(raw_input, overrides = {}) {
    const text = normalize_text(raw_input)
    const room_id = String(room_store?.roomId || '').trim()

    if (!room_id || !text) {
      return { handled: false, success: false, need_confirm: false, detail: null }
    }

    if (is_legacy_agent_notebook_target(overrides)) {
      notify('Room 内 legacy role notebook / natural save 已收口，请直接发送给 Supervisor 处理。', true)
      return { handled: true, success: false, need_confirm: false, detail: null }
    }

    try {
      return await execute_room_save(room_id, text, overrides || {})
    } catch (error) {
      notify(String(error?.message || error || '写入失败'), true)
      return { handled: true, success: false, need_confirm: false, detail: null }
    }
  }

  return {
    maybe_handle_room_save_intent,
    confirm_room_save_intent,
  }
}

export default use_room_natural_save
