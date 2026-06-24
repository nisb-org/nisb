import { useSettingsStore } from '../../../stores/settings'

export function create_left_sidebar_office_convert_actions({
  call_tool,
  toast,
  hide_context_menu,
  current_workspace,
  pick_cm,
  cm_target_path,
  cm_target_name,
  extract_nisb_file_path,
  normalize_rel_path,
  is_doc_file,
  is_docx_file,
  is_ppt_file,
  is_pptx_file,
  pick_display_name_from_path,
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

  const DOC_CONVERT_TOOL = 'nisb_doc_convert_to_note'
  const DOCX_CONVERT_TOOL = 'nisb_docx_convert_to_note'
  const PPT_CONVERT_TOOL = 'nisb_ppt_convert_to_note'
  const PPTX_CONVERT_TOOL = 'nisb_pptx_convert_to_note'

  async function handle_office_to_note({ kind, cm_in }) {
    const cm = pick_cm(cm_in)

    const src_path0 = cm_target_path(cm)
    const src_name0 = cm_target_name(cm) || src_path0

    const src_path = extract_nisb_file_path(src_path0) || src_path0
    const src_name = src_name0

    hide_context_menu()

    if (!src_path) {
      return toast(
        tr('files.convert.common.targetPathMissing', {}, 'Target path was not found.'),
        'error',
        2500
      )
    }

    if (kind === 'doc' && !(is_doc_file(src_name) || is_doc_file(src_path))) {
      return toast(
        tr('files.convert.office.notExpectedFile', { ext: '.doc' }, 'Current file is not {ext}.'),
        'info',
        2200
      )
    }
    if (kind === 'docx' && !(is_docx_file(src_name) || is_docx_file(src_path))) {
      return toast(
        tr('files.convert.office.notExpectedFile', { ext: '.docx' }, 'Current file is not {ext}.'),
        'info',
        2200
      )
    }
    if (kind === 'ppt' && !(is_ppt_file(src_name) || is_ppt_file(src_path))) {
      return toast(
        tr('files.convert.office.notExpectedFile', { ext: '.ppt' }, 'Current file is not {ext}.'),
        'info',
        2200
      )
    }
    if (kind === 'pptx' && !(is_pptx_file(src_name) || is_pptx_file(src_path))) {
      return toast(
        tr('files.convert.office.notExpectedFile', { ext: '.pptx' }, 'Current file is not {ext}.'),
        'info',
        2200
      )
    }

    const uid = (() => {
      try {
        const v = String(localStorage.getItem('nisb_user_id') || '').trim()
        return v || 'nisb_default_user'
      } catch {
        return 'nisb_default_user'
      }
    })()

    const ws = String(current_workspace.value || '').trim()

    const tool =
      kind === 'doc'
        ? DOC_CONVERT_TOOL
        : kind === 'docx'
          ? DOCX_CONVERT_TOOL
          : kind === 'ppt'
            ? PPT_CONVERT_TOOL
            : PPTX_CONVERT_TOOL

    const path_key =
      kind === 'doc'
        ? 'doc_path'
        : kind === 'docx'
          ? 'docx_path'
          : kind === 'ppt'
            ? 'ppt_path'
            : 'pptx_path'

    const kind_label = String(kind || '').toUpperCase()

    toast(
      tr(
        'files.convert.office.progress',
        { kind: kind_label },
        '⏳ Converting {kind} to Markdown...'
      ),
      'info',
      2500
    )

    const dedupe_key = `office_convert|${kind}|${uid}|${normalize_rel_path(src_path)}|${ws}`

    const args_base = {
      [path_key]: src_path,
      uid,
      workspace_id: current_workspace.value,
      locale: settings.locale || 'en',
      output_md_path: '',
      image_dirname: 'images',
      overwrite: false
    }

    if (kind === 'ppt' || kind === 'pptx') args_base.disable_notes = false

    try {
      let r = await call_tool(tool, { ...args_base, overwrite: false }, { retry: 0, dedupe_key })

      if (r && r.success && r.already_exists) {
        const open_path = String(r?.md_path || '').trim()
        const open_name = pick_display_name_from_path(open_path) || 'converted.md'
        window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
        toast(
          tr(
            'files.convert.common.alreadyExistsOpen',
            { name: open_name },
            '✅ Already exists: {name} (opened)'
          ),
          'success',
          2800
        )
        if (open_path) window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: open_path, name: open_name } }))
        return
      }

      if (r && r.success === false) {
        const msg = String(r.message || '')
        if (msg.includes('Busy:') || msg.includes('max_concurrent=1') || msg.toLowerCase().includes('lock')) {
          toast(
            tr(
              'files.convert.office.busy',
              {},
              '⏳ Another document is being converted. Please wait until the current task finishes.'
            ),
            'warning',
            3500
          )
          return
        }
      }

      if (r && r.success === false) {
        const msg = String(r.message || '')
        const is_exists =
          msg.includes('overwrite=false') ||
          msg.includes('Target markdown exists') ||
          msg.includes('Target directory exists') ||
          msg.includes('exists (overwrite=false)')

        if (is_exists) {
          const open_path0 = String(r?.md_path || '').trim()
          if (open_path0) {
            const open_name0 = pick_display_name_from_path(open_path0) || 'converted.md'
            window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
            toast(
              tr(
                'files.convert.common.alreadyExistsOpen',
                { name: open_name0 },
                '✅ Already exists: {name} (opened)'
              ),
              'success',
              2800
            )
            window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: open_path0, name: open_name0 } }))
            return
          }

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
              'info'
            )
          }

          r = await call_tool(tool, { ...args_base, overwrite: true }, { retry: 0, dedupe_key: `${dedupe_key}|overwrite_true` })
        }
      }

      if (!r || r.success === false) {
        toast(
          tr(
            'files.convert.common.convertFailed',
            { error: r?.message || tr('files.convert.common.unknownError', {}, 'Unknown error') },
            '❌ Conversion failed: {error}'
          ),
          'error',
          3500
        )
        return
      }

      const open_path = String(r?.md_path || '').trim()
      const open_name = pick_display_name_from_path(open_path) || 'converted.md'

      window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
      toast(
        tr('files.convert.common.generated', { name: open_name }, '✅ Generated: {name}'),
        'success',
        2800
      )
      if (open_path) window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: open_path, name: open_name } }))
    } catch (e) {
      toast(
        tr(
          'files.convert.common.exception',
          { error: e?.message || String(e) },
          '❌ Conversion exception: {error}'
        ),
        'error',
        3500
      )
    }
  }

  async function handle_doc_to_note(cm_in) {
    return await handle_office_to_note({ kind: 'doc', cm_in })
  }
  async function handle_docx_to_note(cm_in) {
    return await handle_office_to_note({ kind: 'docx', cm_in })
  }
  async function handle_ppt_to_note(cm_in) {
    return await handle_office_to_note({ kind: 'ppt', cm_in })
  }
  async function handle_pptx_to_note(cm_in) {
    return await handle_office_to_note({ kind: 'pptx', cm_in })
  }

  return {
    handle_doc_to_note,
    handle_docx_to_note,
    handle_ppt_to_note,
    handle_pptx_to_note
  }
}

