import { useSettingsStore } from '../../../stores/settings'

export function create_left_sidebar_txt_convert_actions({
  call_tool,
  toast,
  hide_context_menu,
  current_workspace,
  pick_cm,
  cm_target_path,
  cm_target_name,
  extract_nisb_file_path,
  normalize_rel_path,
  pick_display_name_from_path,
  get_uid,
  t
}) {
  const settings = useSettingsStore()

  function format_message(template, params = {}) {
    return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
      if (params?.[key] === undefined || params?.[key] === null) return ''
      return String(params[key])
    })
  }

  function tr(key, params = {}, fallback = '') {
    let text = ''
    if (typeof t === 'function') {
      try {
        text = t(key, params)
      } catch {
        text = ''
      }
    }
    if (!text || text === key) text = fallback || key
    return format_message(text, params)
  }

  function _is_txt(name) {
    return /\.txt$/i.test(String(name || '').trim())
  }

  function _workspace_id_optional() {
    const ws = current_workspace?.value || current_workspace || {}
    if (typeof ws === 'string') return ws.trim()
    return String(ws?.id || ws?.workspace_id || ws?.workspaceId || '').trim()
  }

  function _open_file(path_rel) {
    window.dispatchEvent(
      new CustomEvent('nisb-open-file', {
        detail: {
          path: path_rel,
          rel_path: path_rel,
          workspace_id: _workspace_id_optional(),
          workspaceId: _workspace_id_optional()
        }
      })
    )
  }

  function _refresh_file_tree() {
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh', { detail: {} }))
    window.dispatchEvent(new CustomEvent('nisb-refresh-file-tree', { detail: {} }))
  }

  function _is_exists_response(result) {
    const msg = String(result?.message || result?.error || '').trim()
    if (!msg) return false

    return (
      /overwrite=false/i.test(msg) ||
      /target\s+(md|markdown|directory)\s+exists/i.test(msg) ||
      /exists\s*\(overwrite=false\)/i.test(msg)
    )
  }

  function _pick_existing_md_path(result) {
    const direct = String(
      result?.md_path ||
        result?.target_md_path ||
        result?.existing_md_path ||
        result?.existing_path ||
        result?.path ||
        ''
    ).trim()

    if (direct) return direct

    const msg = String(result?.message || result?.error || '').trim()
    const match = msg.match(/:\s*([^\r\n]+\.md)\s*$/i)
    return match ? String(match[1] || '').trim() : ''
  }

  async function handle_txt_to_structured_md(cm_in) {
    const cm = pick_cm(cm_in)
    const p0 = cm_target_path(cm)
    const n0 = cm_target_name(cm) || p0

    const p_raw = extract_nisb_file_path(p0) || p0
    const n = n0

    hide_context_menu()

    if (!p_raw) {
      return toast(
        tr('files.convert.txt.pathMissing', {}, 'TXT path was not found.'),
        'error',
        2500
      )
    }

    if (!_is_txt(n) && !_is_txt(p_raw)) {
      return toast(
        tr('files.convert.txt.notExpectedFile', {}, 'Current file is not .txt.'),
        'info',
        2200
      )
    }

    const uid = typeof get_uid === 'function' ? get_uid() : 'nisb_default_user'
    const wsid = _workspace_id_optional()

    const txt_path = normalize_rel_path(p_raw)
    const display = pick_display_name_from_path(txt_path) || n

    toast(
      tr('files.convert.txt.start', { name: display }, 'Start converting: {name}'),
      'info',
      1600
    )

    const args_base = {
      uid,
      workspace_id: wsid,
      locale: settings.locale || 'en',
      txt_path,
      output_md_path: '',
      overwrite: false,
      language_hint: 'auto',
      max_lines: 200000
    }

    let r
    try {
      r = await call_tool('nisb_txt_convert_to_structured_md', args_base)
    } catch (e) {
      return toast(
        tr(
          'files.convert.txt.failed',
          { error: e?.message || String(e) },
          'Conversion failed: {error}'
        ),
        'error',
        3500
      )
    }

    if (!r?.success && _is_exists_response(r)) {
      const existing_path = _pick_existing_md_path(r)

      if (existing_path) {
        const existing_name = pick_display_name_from_path(existing_path) || 'converted.md'
        _refresh_file_tree()
        _open_file(existing_path)

        return toast(
          tr(
            'files.convert.txt.alreadyExists',
            { name: existing_name },
            'Already exists: {name}'
          ),
          'info',
          2600
        )
      }

      const msg = String(r?.message || r?.error || '').trim()
      const ok = confirm(
        tr(
          'files.convert.common.overwriteConfirm',
          { message: msg },
          'Target already exists. Overwrite it?\n\n{message}'
        )
      )

      if (!ok) {
        return toast(
          tr('files.convert.common.overwriteCancelled', {}, 'Overwrite cancelled.'),
          'info',
          2200
        )
      }

      try {
        r = await call_tool('nisb_txt_convert_to_structured_md', {
          ...args_base,
          overwrite: true
        })
      } catch (e) {
        return toast(
          tr(
            'files.convert.txt.failed',
            { error: e?.message || String(e) },
            'Conversion failed: {error}'
          ),
          'error',
          3500
        )
      }
    }

    if (!r?.success) {
      return toast(
        tr(
          'files.convert.txt.failed',
          {
            error:
              r?.message ||
              r?.error ||
              tr('files.convert.common.unknownErrorLower', {}, 'unknown error')
          },
          'Conversion failed: {error}'
        ),
        'error',
        3500
      )
    }

    const md_path = String(r?.md_path || '').trim()
    if (!md_path) {
      return toast(
        tr(
          'files.convert.txt.successNoPath',
          {},
          'Conversion succeeded, but md_path was not returned.'
        ),
        'warning',
        2600
      )
    }

    _refresh_file_tree()
    _open_file(md_path)

    if (r?.already_exists) {
      return toast(
        tr(
          'files.convert.txt.alreadyExists',
          { name: pick_display_name_from_path(md_path) || 'converted.md' },
          'Already exists: {name}'
        ),
        'info',
        2200
      )
    }

    return toast(
      tr(
        'files.convert.txt.completed',
        { name: pick_display_name_from_path(md_path) || 'converted.md' },
        'Conversion completed: {name}'
      ),
      'success',
      2200
    )
  }

  return {
    handle_txt_to_structured_md
  }
}

export default create_left_sidebar_txt_convert_actions
