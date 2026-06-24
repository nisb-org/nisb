// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/actions/left_sidebar_actions_extensions.js

export function create_left_sidebar_extensions_actions({
  hide_context_menu,
  pick_cm,
  cm_target_path,
  cm_target_name,
  cm_target_file_type,
  extract_nisb_file_path
}) {
  function handle_extension_click(ext, cm_in) {
    const cm = pick_cm(cm_in)

    const id = String(ext?.id || '').trim()
    const payload = ext?.payload || {}
    hide_context_menu()

    if (id === 'focus_root') {
      const path0 = String(payload?.path || cm_target_path(cm) || '').trim()
      const path = extract_nisb_file_path(path0) || path0
      if (path) window.dispatchEvent(new CustomEvent('nisb_file_focus_root', { detail: { path } }))
      return
    }

    if (id === 'clear_focus_root') {
      window.dispatchEvent(new CustomEvent('nisb_file_clear_focus_root', { detail: {} }))
      return
    }

    window.dispatchEvent(
      new CustomEvent('nisb_file_context_extension', {
        detail: {
          id,
          payload,
          targetPath: cm_target_path(cm),
          targetName: cm_target_name(cm),
          targetFileType: cm_target_file_type(cm)
        }
      })
    )
  }

  return { handle_extension_click }
}

