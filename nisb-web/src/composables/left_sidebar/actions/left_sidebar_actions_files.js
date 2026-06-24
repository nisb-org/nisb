import { open_create_entry_modal } from './create_entry_modal_service'
import { normalizeToolResponse, pickDataValue } from './response_normalizer'
import {
  from_user_visible_path,
  to_user_visible_path
} from '../file_browser/file_path_display'

export function create_left_sidebar_file_actions({
  call_tool,
  toast,
  hide_context_menu,
  current_workspace,
  library_list_ref,
  send_to_library_dialog,

  pick_cm,
  cm_target_path,
  cm_target_name,
  cm_target_file_type,

  extract_nisb_file_path,
  copy_to_clipboard,

  is_binary_file,
  is_pdf_file,
  is_epub_file,
  is_image_file,

  get_parent_dir,
  normalize_rel_path
}) {
  const DEFAULT_WORKSPACE_ID = 'workspace_work'

  function _string(value) {
    return String(value || '').trim()
  }

  function _read_browser_context() {
    try {
      const ctx = window.__nisb_file_browser_context
      return ctx && typeof ctx === 'object' ? ctx : {}
    } catch {
      return {}
    }
  }

  function _read_context_gate() {
    const ctx = _read_browser_context()
    if (ctx?.capability_gate && typeof ctx.capability_gate === 'object') return ctx.capability_gate
    if (ctx?.capabilityGate && typeof ctx.capabilityGate === 'object') return ctx.capabilityGate
    return {}
  }

  function _workspace_id(cm) {
    const gate = _read_context_gate()
    const ctx = _read_browser_context()
    const raw =
      cm?.workspace_id ||
      cm?.workspaceId ||
      gate.workspace_id ||
      ctx.workspace_id ||
      ctx.workspaceId ||
      current_workspace?.value ||
      DEFAULT_WORKSPACE_ID

    return _string(raw) || DEFAULT_WORKSPACE_ID
  }

  function _context_focus_root(cm) {
    const gate = _read_context_gate()
    const ctx = _read_browser_context()
    return _clean_path(cm?.focus_root || cm?.focusRoot || gate.focus_root || ctx.focus_root || ctx.focusRoot || '')
  }

  function _extract_path(raw) {
    const value = _string(raw)
    if (!value) return ''
    try {
      const extracted = extract_nisb_file_path(value)
      return _string(extracted || value)
    } catch {
      return value
    }
  }

  function _clean_path(raw) {
    let s = _string(raw).replace(/\\/g, '/')
    while (s.startsWith('/')) s = s.slice(1)
    s = s
      .split('/')
      .map((part) => part.trim())
      .filter(Boolean)
      .join('/')
    return s
  }

  function _target_path(cm) {
    const direct = _extract_path(cm_target_path(cm))
    if (direct) return _clean_path(direct)

    const fallback =
      cm?.baseDir ||
      cm?.base_dir ||
      cm?.targetPath ||
      cm?.target_path ||
      cm?.path ||
      cm?.filename ||
      ''

    return _clean_path(_extract_path(fallback))
  }

  function _target_name(cm) {
    return _string(cm_target_name(cm) || cm?.name || cm?.targetName || cm?.target_name || '')
  }

  function _target_type(cm) {
    return _string(cm_target_file_type(cm) || cm?.type || cm?.targetType || cm?.target_type || 'file') || 'file'
  }

  function _build_capability_gate(cm, { write = true, dangerous = false, focus_root_hint = '' } = {}) {
    const focus_root = _context_focus_root(cm) || (dangerous ? _clean_path(focus_root_hint) : '')

    return {
      policy_version: 1,
      workspace_id: _workspace_id(cm),
      focus_root,
      fs_read_scope: 'user_ro',
      fs_write_scope: write ? 'agent_files' : 'none',
      fs_dangerous_enabled: dangerous ? !!focus_root : false
    }
  }

  function _with_file_capability(args = {}, cm = null, options = {}) {
    const capability_gate = _build_capability_gate(cm, options)

    return {
      ...args,
      workspace_id: capability_gate.workspace_id,
      capability_gate
    }
  }

  function _with_read_capability(args = {}, cm = null) {
    return _with_file_capability(args, cm, { write: false, dangerous: false })
  }

  function _with_write_capability(args = {}, cm = null, options = {}) {
    return _with_file_capability(args, cm, { write: true, dangerous: false, ...options })
  }

  function _with_dangerous_capability(args = {}, cm = null, focus_root_hint = '') {
    return _with_file_capability(args, cm, {
      write: true,
      dangerous: true,
      focus_root_hint
    })
  }

  function _show_alert(message) {
    try {
      alert(message)
    } catch {
      toast(message, 'info')
    }
  }

  function _confirm(message) {
    try {
      return confirm(message)
    } catch {
      return false
    }
  }

  function _prompt(message, defaultValue = '') {
    try {
      return prompt(message, defaultValue)
    } catch {
      return null
    }
  }

  function _success_text(info, fallback) {
    return _string(info?.text) || fallback
  }

  function _error_text(info, fallback = 'Unknown error') {
    return _string(info?.text) || fallback
  }

  function _dispatch_refresh_events() {
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
  }

  function _dispatch_timeline_refresh() {
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
  }

  async function handle_copy_internal_link(cm_in) {
    const cm = pick_cm(cm_in)

    const path0 = _target_path(cm)
    const name0 = _target_name(cm) || path0
    const type = _target_type(cm) || 'file'
    const ws = _workspace_id(cm)

    hide_context_menu()

    const path = _extract_path(path0) || path0
    const name = name0

    if (!path) {
      toast('Target path was not found.', 'error')
      return
    }

    const link = `nisb://file?ws=${encodeURIComponent(ws)}&type=${encodeURIComponent(type)}&path=${encodeURIComponent(path)}`
    const md = `[${name}](${link})`

    const ok = await copy_to_clipboard(md)
    toast(ok ? 'Internal link copied as Markdown.' : 'Copy failed: clipboard access was blocked by the browser.', ok ? 'info' : 'error')
  }

  async function handle_note_to_brain(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)

    hide_context_menu()

    if (!target_path || !target_name) {
      toast('Target file path was not found.', 'error')
      return
    }

    if (!/\.(md|txt)$/i.test(target_name)) {
      toast('Only .md and .txt files can be sent to Brain right now.', 'info')
      return
    }

    try {
      toast(`Processing note: ${target_name}`, 'info')
      const res = await call_tool('nisb_note_to_brain', _with_read_capability({ filename: target_path }, cm))
      const info = normalizeToolResponse(res, `Note sent to Brain: ${target_name}`)

      if (info.success) {
        toast(_success_text(info, `Note sent to Brain: ${target_name}`), info.isWarning ? 'warning' : 'success', 2500)
        try {
          localStorage.setItem(`hebbian_mark_${target_path}`, String(Date.now()))
        } catch {}
        window.dispatchEvent(new CustomEvent('nisb-hebbian-completed', { detail: { source: target_path, type: 'note' } }))
      } else {
        toast(`Failed to send note to Brain: ${_error_text(info)}`, 'error', 3000)
      }
    } catch (e) {
      toast(`Brain processing failed: ${e?.message || String(e)}`, 'error', 3000)
    }
  }

  async function handle_toggle_favorite(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)
    const file_type = _target_type(cm) || 'file'

    hide_context_menu()

    if (!target_path) {
      toast('Target path was not found.', 'error')
      return
    }

    try {
      const res = await call_tool('nisb_favorites_toggle_file', {
        path: target_path,
        type: file_type,
        workspace_id: _workspace_id(cm)
      })
      const info = normalizeToolResponse(res, 'Favorites updated.')
      if (!info.success) {
        toast(_error_text(info, 'Failed to update favorite state.'), 'error')
        return
      }

      const pinned = !!pickDataValue(res, 'pinned', false)
      toast(pinned ? `Added to favorites: ${target_name || target_path}` : `Removed from favorites: ${target_name || target_path}`, 'info')
      window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    } catch (e) {
      toast(`Failed to update favorite state: ${e?.message || String(e)}`, 'error')
    }
  }

  function handle_send_file_to_library(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)

    if (!target_path) {
      hide_context_menu()
      return
    }

    send_to_library_dialog.value = {
      visible: true,
      sourcePath: target_path,
      sourceName: target_name || target_path,
      sourceType: 'file'
    }

    hide_context_menu()
  }

  function handle_send_dir_to_library(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)

    if (!target_path) {
      hide_context_menu()
      return
    }

    send_to_library_dialog.value = {
      visible: true,
      sourcePath: target_path,
      sourceName: `${target_name || target_path}/`,
      sourceType: 'directory'
    }

    hide_context_menu()
  }

  function handle_send_to_library_sent() {
    send_to_library_dialog.value = {
      ...(send_to_library_dialog.value || {}),
      visible: false
    }
    try {
      library_list_ref.value?.loadLibraries()
    } catch {}
  }

  async function handle_batch_notes_to_brain(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)

    hide_context_menu()

    if (!target_path) {
      toast('Target directory path was not found.', 'error')
      return
    }

    const confirmed = _confirm(
      `Send all note files under "${target_name || target_path}" to Brain?\n\nThis will recursively process .md files under the directory. It may take a while depending on the file count.`
    )
    if (!confirmed) return

    try {
      toast(`Processing directory: ${target_name || target_path}. Please wait...`, 'info', 3000)
      const res = await call_tool(
        'nisb_batch_notes_to_brain',
        _with_read_capability(
          {
            directory: target_path,
            file_pattern: '*.md',
            concept_language: 'auto',
            concept_backend: 'llm_gpt4o_mini'
          },
          cm
        )
      )
      const info = normalizeToolResponse(res, 'Batch Brain processing completed.')

      if (info.success) {
        toast(_success_text(info, 'Batch Brain processing completed.'), info.isWarning ? 'warning' : 'success', 2500)
        _dispatch_refresh_events()
        window.dispatchEvent(new CustomEvent('nisb-hebbian-completed', { detail: { source: target_path, type: 'batch_notes' } }))
      } else {
        toast(`Batch Brain processing failed: ${_error_text(info)}`, 'error', 3500)
      }
    } catch (e) {
      toast(`Batch Brain processing failed: ${e?.message || String(e)}`, 'error', 3500)
    }
  }

  async function handle_rename(cm_in) {
    const cm = pick_cm(cm_in)

    const old_path = _target_path(cm)
    const old_name = _target_name(cm)
    const file_type = _target_type(cm) || 'file'

    const new_name = _prompt('Enter a new name:', old_name)
    if (!new_name || new_name === old_name) {
      hide_context_menu()
      return
    }

    try {
      let result

      if (file_type === 'directory') {
        const parent = get_parent_dir(old_path) || ''
        const new_path = parent ? `${parent}/${new_name}` : new_name

        result = await call_tool('nisb_dir_move_path', _with_write_capability({ old_path, new_path }, cm))

        const info = normalizeToolResponse(result, `Directory renamed:\n${old_path} -> ${new_path}`)
        if (info.success) {
          window.dispatchEvent(new CustomEvent('nisb_path_renamed', { detail: { old_path, new_path, type: 'directory' } }))
          _show_alert(_success_text(info, `Directory renamed:\n${old_path} -> ${new_path}`))
          _dispatch_refresh_events()
        } else {
          _show_alert('Rename failed: ' + _error_text(info))
        }
      } else {
        result = await call_tool('nisb_file_rename', _with_write_capability({ old_path, new_name }, cm))

        const info = normalizeToolResponse(result, 'File renamed.')
        if (info.success) {
          const parent = get_parent_dir(old_path) || ''
          const new_path = parent ? `${parent}/${new_name}` : new_name
          window.dispatchEvent(new CustomEvent('nisb_path_renamed', { detail: { old_path, new_path, type: file_type } }))
          _show_alert(_success_text(info, 'File renamed.'))
          _dispatch_refresh_events()
        } else {
          _show_alert('Rename failed: ' + _error_text(info))
        }
      }
    } catch (e) {
      _show_alert('Rename failed: ' + (e?.message || String(e)))
    } finally {
      hide_context_menu()
    }
  }

  async function handle_move(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)
    const file_type = _target_type(cm)

    const default_dir = get_parent_dir(target_path) || 'agent_files'
    const default_dir_display = to_user_visible_path(default_dir)
    const dest_dir_input = _prompt('Enter the destination directory path, for example: user/projects/nisb-core', default_dir_display)
    if (!dest_dir_input) {
      hide_context_menu()
      return
    }

    const dest_dir_real = from_user_visible_path(dest_dir_input)
    const normalized_dir = dest_dir_real.endsWith('/') ? dest_dir_real.slice(0, -1) : dest_dir_real
    const new_path = `${normalized_dir || 'agent_files'}/${target_name}`

    try {
      let result
      if (file_type === 'directory') {
        result = await call_tool('nisb_dir_move_path', _with_write_capability({ old_path: target_path, new_path }, cm))
      } else {
        result = await call_tool('nisb_file_move_path', _with_write_capability({ old_path: target_path, new_path }, cm))
      }

      const label = file_type === 'directory' ? 'Directory' : 'File'
      const info = normalizeToolResponse(result, `${label} moved:\n${target_path} -> ${new_path}`)

      if (info.success) {
        window.dispatchEvent(new CustomEvent('nisb_path_renamed', { detail: { old_path: target_path, new_path, type: file_type } }))
        _show_alert(_success_text(info, `${label} moved:\n${target_path} -> ${new_path}`))
        _dispatch_refresh_events()
      } else {
        _show_alert('Move failed: ' + _error_text(info))
      }
    } catch (e) {
      _show_alert('Move failed: ' + (e?.message || String(e)))
    } finally {
      hide_context_menu()
    }
  }

  async function handle_delete(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)
    const file_type = _target_type(cm) || 'file'

    const confirm_msg =
      file_type === 'directory'
        ? `Delete directory "${target_name || target_path}"? Only empty directories can be deleted by this action.`
        : `Delete "${target_name || target_path}"?`

    if (!_confirm(confirm_msg)) {
      hide_context_menu()
      return
    }

    try {
      let result
      if (file_type === 'directory') {
        result = await call_tool('nisb_dir_delete', _with_dangerous_capability({ path: target_path }, cm, target_path))
      } else {
        result = await call_tool(
          'nisb_file_delete',
          _with_dangerous_capability({ filename: target_path, permanent: false }, cm, target_path)
        )
      }

      const info = normalizeToolResponse(result, 'Deleted.')
      if (info.success) {
        window.dispatchEvent(new CustomEvent('nisb_path_deleted', { detail: { path: target_path, type: file_type } }))
        _show_alert(_success_text(info, 'Deleted.'))
        _dispatch_refresh_events()
        _dispatch_timeline_refresh()
      } else {
        _show_alert('Delete failed: ' + _error_text(info))
      }
    } catch (e) {
      _show_alert('Delete failed: ' + (e?.message || String(e)))
    } finally {
      hide_context_menu()
    }
  }

  async function handle_delete_recursive(cm_in) {
    const cm = pick_cm(cm_in)

    const target_path = _target_path(cm)
    const target_name = _target_name(cm)

    if (!target_path) {
      toast('Target directory path was not found.', 'error')
      hide_context_menu()
      return
    }

    try {
      toast(`Moving to trash: ${target_name || target_path}`, 'info', 1600)
      const result = await call_tool(
        'nisb_fs_bulk_delete',
        _with_dangerous_capability(
          {
            paths: [target_path],
            reason: 'filebrowser_recursive_delete'
          },
          cm,
          target_path
        )
      )
      const info = normalizeToolResponse(result, 'Moved to trash.')

      if (info.success) {
        _dispatch_refresh_events()
        _dispatch_timeline_refresh()
        toast(_success_text(info, 'Moved to trash.'), info.isWarning ? 'warning' : 'success', 2000)
      } else {
        toast('Recursive delete failed: ' + _error_text(info), 'error', 3000)
      }
    } catch (e) {
      toast('Recursive delete failed: ' + (e?.message || String(e)), 'error', 3000)
    } finally {
      hide_context_menu()
    }
  }

  async function handle_copy_image_reference(cm_in) {
    const cm = pick_cm(cm_in)

    const image_path_raw = _target_path(cm)
    const image_name_raw = _target_name(cm)

    const image_path = normalize_rel_path(image_path_raw)
    const alt = (_string(image_name_raw || 'image').replace(/[[\]]/g, '\\$&') || 'image').trim()

    if (!image_path) {
      toast('Image path was not found.', 'error')
      hide_context_menu()
      return
    }

    const src = `nisb://file?path=${encodeURIComponent(image_path)}`
    const markdown_ref = `![${alt}](${src})`

    const ok = await copy_to_clipboard(markdown_ref)
    toast(ok ? 'Image reference copied as Markdown.' : 'Copy failed: clipboard access was blocked by the browser.', ok ? 'info' : 'error')
    hide_context_menu()
  }

  async function handle_create_file_in_dir(cm_in) {
    const cm = pick_cm(cm_in)
    const base_dir = _target_path(cm)

    hide_context_menu()

    const picked = await open_create_entry_modal({
      kind: 'file',
      base_dir,
      default_name: '',
      default_ext: 'md',
      call_tool
    })
    if (!picked) return

    const name = picked.name
    const final_base_dir = picked.base_dir || ''
    const filename = final_base_dir ? `${final_base_dir}/${name}` : name

    try {
      const result = await call_tool(
        'nisb_file_create',
        _with_write_capability(
          {
            filename,
            content: '',
            description: `Created at ${new Date().toLocaleString()}`,
            auto_categorize: false
          },
          cm
        )
      )
      const info = normalizeToolResponse(result, `File created: ${filename}`)

      if (info.success) {
        _show_alert(_success_text(info, `File created: ${filename}`))
        _dispatch_refresh_events()
        window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: filename, name } }))
      } else {
        _show_alert('Create failed: ' + _error_text(info))
      }
    } catch (e) {
      _show_alert('Create failed: ' + (e?.message || String(e)))
    }
  }

  async function handle_create_dir_in_dir(cm_in) {
    const cm = pick_cm(cm_in)
    const base_dir = _target_path(cm)

    hide_context_menu()

    const picked = await open_create_entry_modal({
      kind: 'dir',
      base_dir,
      default_name: '',
      default_ext: '',
      call_tool
    })
    if (!picked) return

    const name = picked.name
    const final_base_dir = picked.base_dir || ''
    const dir_path = final_base_dir ? `${final_base_dir}/${name}` : name

    try {
      const result = await call_tool('nisb_dir_create', _with_write_capability({ path: dir_path }, cm))
      const info = normalizeToolResponse(result, `Directory created: ${dir_path}`)

      if (info.success) {
        _show_alert(_success_text(info, `Directory created: ${dir_path}`))
        _dispatch_refresh_events()
      } else {
        _show_alert('Create directory failed: ' + _error_text(info))
      }
    } catch (e) {
      _show_alert('Create directory failed: ' + (e?.message || String(e)))
    }
  }

  return {
    handle_copy_internal_link,
    handle_note_to_brain,
    handle_toggle_favorite,

    handle_send_file_to_library,
    handle_send_dir_to_library,
    handle_send_to_library_sent,

    handle_batch_notes_to_brain,

    handle_rename,
    handle_move,
    handle_delete,
    handle_delete_recursive,

    handle_copy_image_reference,

    handle_create_file_in_dir,
    handle_create_dir_in_dir
  }
}
