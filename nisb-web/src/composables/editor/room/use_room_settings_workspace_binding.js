export function use_room_settings_workspace_binding({
  form,
  busy,
  room_id_value,
  callTool,
  room_store,
  normalize_focus_root_client,
  fill_form_from_store,
}) {
  function dispatch_toast(message, type = 'success') {
    window.dispatchEvent(new CustomEvent('nisb-toast', {
      detail: { message, type },
    }))
  }

  function build_workspace_context_detail({ source = 'room_settings_preview' } = {}) {
    const workspace_id = String(form.workspace_id || '').trim()
    const workspace_name = String(form.workspace_name || '').trim()
    const focus_root = normalize_focus_root_client(form.focus_root)
    const focus_label = String(form.focus_label || '').trim()

    return {
      room_id: room_id_value.value,
      workspace_id,
      workspace_name,
      focus_root,
      focus_label,
      clear_focus_root: !focus_root,
      source,
    }
  }

  function apply_context_to_sidebar() {
    const detail = build_workspace_context_detail({ source: 'room_settings_preview' })
    window.dispatchEvent(new CustomEvent('nisb_room_apply_workspace_context', { detail }))
    dispatch_toast('已应用到左侧栏（仅预览，未保存房间设置）', 'success')
  }

  async function clear_focus_root_only() {
    if (!room_id_value.value) return

    busy.value = true
    try {
      await callTool('nisb_room_workspace_clear', {
        room_id: room_id_value.value,
        clear_workspace: false,
        clear_focus_root: true,
      })

      form.focus_root = ''
      form.focus_label = ''

      await room_store.refreshRoomInfo(callTool, room_id_value.value)
      fill_form_from_store()

      window.dispatchEvent(new CustomEvent('nisb_room_clear_workspace_context', {
        detail: {
          room_id: room_id_value.value,
          clear_workspace: false,
          clear_focus_root: true,
          source: 'room_settings_clear_focus_root',
        },
      }))

      dispatch_toast('已清空 room 的 focus_root', 'success')
    } catch (error) {
      dispatch_toast(`清空 focus_root 失败：${error?.message || error || '未知错误'}`, 'error')
    } finally {
      busy.value = false
    }
  }

  async function clear_workspace_context_all() {
    if (!room_id_value.value) return

    busy.value = true
    try {
      await callTool('nisb_room_workspace_clear', {
        room_id: room_id_value.value,
        clear_workspace: true,
        clear_focus_root: true,
      })

      form.workspace_id = ''
      form.workspace_name = ''
      form.focus_root = ''
      form.focus_label = ''

      await room_store.refreshRoomInfo(callTool, room_id_value.value)
      fill_form_from_store()

      window.dispatchEvent(new CustomEvent('nisb_room_clear_workspace_context', {
        detail: {
          room_id: room_id_value.value,
          clear_workspace: true,
          clear_focus_root: true,
          source: 'room_settings_clear_all',
        },
      }))

      dispatch_toast('已清空 room 的 workspace_context', 'success')
    } catch (error) {
      dispatch_toast(`清空 workspace_context 失败：${error?.message || error || '未知错误'}`, 'error')
    } finally {
      busy.value = false
    }
  }

  return {
    dispatch_toast,
    build_workspace_context_detail,
    apply_context_to_sidebar,
    clear_focus_root_only,
    clear_workspace_context_all,
  }
}
