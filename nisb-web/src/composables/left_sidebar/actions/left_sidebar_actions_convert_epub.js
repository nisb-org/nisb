import { useSettingsStore } from '../../../stores/settings'

export function create_left_sidebar_epub_convert_actions({
  call_tool,
  toast,
  hide_context_menu,
  current_workspace,
  pick_cm,
  cm_target_path,
  cm_target_name,
  extract_nisb_file_path,
  is_epub_file,
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

  const EPUB_CONVERT_TOOL = 'nisb_epub_convert_to_note'
  const EPUB_CONVERT_MAX_SECONDS = 1800

  function pick_open_path_from_convert_resp(r) {
    const mode = String(r?.mode || '').trim().toLowerCase()
    if (mode === 'split') return String(r?.index_md_path || '').trim()
    return String(r?.md_path || '').trim()
  }

  async function handle_epub_to_note(cm_in) {
    const cm = pick_cm(cm_in)

    const epub_path0 = cm_target_path(cm)
    const epub_name0 = cm_target_name(cm) || epub_path0

    const epub_path = extract_nisb_file_path(epub_path0) || epub_path0
    const epub_name = epub_name0

    hide_context_menu()

    if (!epub_path || (!is_epub_file(epub_name) && !is_epub_file(epub_path))) {
      toast(tr('files.convert.epub.pathMissing', {}, 'EPUB path was not found.'), 'error')
      return
    }

    const uid = (() => {
      try {
        const v = String(localStorage.getItem('nisb_user_id') || '').trim()
        return v || 'nisb_default_user'
      } catch {
        return 'nisb_default_user'
      }
    })()

    toast(
      tr(
        'files.convert.epub.progress',
        {},
        '⏳ Converting EPUB to Markdown (md_part_max_lines=2000, auto/split)...'
      ),
      'info',
      2500
    )

    try {
      const args_base = {
        epub_path,
        uid,
        workspace_id: current_workspace.value,
        locale: settings.locale || 'en',
        output_md_path: '',
        image_dirname: 'images',
        max_seconds: EPUB_CONVERT_MAX_SECONDS,

        md_part_max_lines: 2000,
        split_mode: 'auto',
        split_threshold_lines: 2000,
        target_lines_per_part: 2000
      }

      let r = await call_tool(EPUB_CONVERT_TOOL, { ...args_base, overwrite: false })

      if (r && r.success === false) {
        const msg = String(r.message || '')
        const is_exists =
          msg.includes('overwrite=false') ||
          msg.includes('Target directory exists') ||
          msg.includes('Target markdown exists') ||
          msg.includes('exists (overwrite=false)')

        if (is_exists) {
          const ok = confirm(
            tr(
              'files.convert.common.overwriteConfirm',
              { message: msg },
              'Target already exists. Overwrite it?\n\n{message}'
            )
          )
          if (!ok) {
            toast(
              tr('files.convert.common.overwriteCancelled', {}, 'Overwrite cancelled.'),
              'info'
            )
            return
          }
          r = await call_tool(EPUB_CONVERT_TOOL, { ...args_base, overwrite: true })
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

      const open_path = pick_open_path_from_convert_resp(r)
      const open_name = pick_display_name_from_path(open_path) || 'converted.md'

      window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))

      const mode = String(r?.mode || '').trim().toLowerCase()
      if (mode === 'split') {
        toast(
          tr('files.convert.common.generatedSplit', { name: open_name }, '✅ Generated: {name} (split)'),
          'success',
          2800
        )
      } else {
        toast(
          tr(
            'files.convert.common.generatedImages',
            { name: open_name, count: Number(r?.images_count || 0) },
            '✅ Generated: {name} (images: {count})'
          ),
          'success',
          2800
        )
      }

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

  return { handle_epub_to_note }
}

