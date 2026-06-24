import { useSettingsStore } from '../../../stores/settings'
import { normalizeToolResponse, pickDataValue } from './response_normalizer'

function format_message(template, params = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
    if (params?.[key] === undefined || params?.[key] === null) return ''
    return String(params[key])
  })
}

function create_action_translator(t) {
  return function tr(key, params = {}, fallback = '') {
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
}

export function create_left_sidebar_pdf_convert_actions({
  call_tool,
  toast,
  hide_context_menu,
  current_workspace,
  pick_cm,
  cm_target_path,
  cm_target_name,
  extract_nisb_file_path,
  is_pdf_file,
  normalize_rel_path,
  looks_timeout_resp,
  pick_display_name_from_path,
  t
}) {
  const tr = create_action_translator(t)
  const settings = useSettingsStore()

  const PDF_CONVERT_TOOL = 'nisb_pdf_convert_to_note'
  const PDF_CONVERT_MAX_SECONDS = 7200

  function pick_open_path_from_convert_resp(res) {
    const mode = String(pickDataValue(res, 'mode', '') || '').trim().toLowerCase()
    if (mode === 'split') return String(pickDataValue(res, 'index_md_path', '') || '').trim()
    return String(pickDataValue(res, 'md_path', '') || '').trim()
  }

  async function handle_pdf_to_note(cm_in) {
    const cm = pick_cm(cm_in)

    const pdf_path0 = cm_target_path(cm)
    const pdf_name0 = cm_target_name(cm) || pdf_path0

    const pdf_path = extract_nisb_file_path(pdf_path0) || pdf_path0
    const pdf_name = pdf_name0

    hide_context_menu()

    if (!pdf_path || !(is_pdf_file(pdf_name) || is_pdf_file(pdf_path))) {
      toast(tr('files.convert.pdf.pathMissing', {}, 'PDF path was not found.'), 'error')
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
        'files.convert.pdf.progress',
        {},
        '⏳ Converting PDF to Markdown. This may take a while...'
      ),
      'info',
      2500
    )

    const dedupe_key = `pdf_convert|${uid}|${normalize_rel_path(pdf_path)}|${String(current_workspace.value || '')}`

    const args_base = {
      pdf_path,
      uid,
      workspace_id: current_workspace.value,
      locale: settings.locale || 'en',

      output_md_path: '',
      image_dirname: 'images',
      image_format: 'png',
      dpi: 150,
      overwrite: false,

      split_mode: 'auto',
      split_threshold_pages: 120,
      split_pages: 25,
      pages_per_batch: 3,
      max_seconds: PDF_CONVERT_MAX_SECONDS,
      write_images: true
    }

    try {
      let r = await call_tool(PDF_CONVERT_TOOL, { ...args_base, overwrite: false }, { retry: 0, dedupe_key })
      let info = normalizeToolResponse(r, tr('files.convert.pdf.completed', {}, 'PDF conversion completed'))

      if (info.success && !!pickDataValue(r, 'already_exists', false)) {
        const open_path = pick_open_path_from_convert_resp(r)
        const open_name = pick_display_name_from_path(open_path) || 'index.md'
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

      if (!info.success) {
        const msg = String(info.message || info.text || '')
        if (msg.includes('Busy:') || msg.includes('max_concurrent=1')) {
          toast(
            tr(
              'files.convert.pdf.busy',
              {},
              '⏳ Another PDF is being converted. Please wait until the current task finishes.'
            ),
            'warning',
            3500
          )
          return
        }
      }

      if (!info.success && looks_timeout_resp(r) && String(pickDataValue(r, 'mode', '') || '').toLowerCase() === 'split') {
        const done = Number(pickDataValue(r, 'pages_done', 0) || 0)
        const total = Number(pickDataValue(r, 'total_pages', 0) || 0)
        const ok_resume = confirm(
          tr(
            'files.convert.pdf.timeoutResumeConfirm',
            { done, total, next: done + 1 },
            'Conversion timed out ({done}/{total} pages). Continue from page {next}?'
          )
        )
        if (!ok_resume) {
          toast(
            tr(
              'files.convert.pdf.resumeCancelled',
              {},
              'Resume cancelled. Generated partial files were kept.'
            ),
            'info',
            2800
          )
          return
        }

        toast(
          tr('files.convert.pdf.resumeProgress', {}, '⏳ Resuming conversion...'),
          'info',
          2500
        )
        const r2 = await call_tool(
          PDF_CONVERT_TOOL,
          {
            ...args_base,
            overwrite: false,
            resume: true,
            resume_from_page: done
          },
          {
            retry: 0,
            dedupe_key: `${dedupe_key}|resume`
          }
        )

        const info2 = normalizeToolResponse(r2, tr('files.convert.pdf.resumeCompleted', {}, 'PDF resume conversion completed'))
        if (!info2.success) {
          toast(
            tr(
              'files.convert.pdf.resumeFailed',
              { error: info2.text || tr('files.convert.common.unknownError', {}, 'Unknown error') },
              '❌ Resume conversion failed: {error}'
            ),
            'error',
            3500
          )
          return
        }

        const open_path2 = pick_open_path_from_convert_resp(r2)
        const open_name2 = pick_display_name_from_path(open_path2) || 'index.md'
        window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
        toast(
          tr(
            'files.convert.pdf.resumeGenerated',
            { name: open_name2 },
            '✅ Generated: {name} (resume)'
          ),
          'success',
          2800
        )
        if (open_path2) window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path: open_path2, name: open_name2 } }))
        return
      }

      if (!info.success) {
        const msg = String(info.message || info.text || '')
        const is_exists =
          msg.includes('overwrite=false') ||
          msg.includes('Target markdown exists') ||
          msg.includes('Target directory exists') ||
          msg.includes('exists (overwrite=false)')

        if (is_exists) {
          const open_path0 = pick_open_path_from_convert_resp(r)
          if (open_path0) {
            const open_name0 = pick_display_name_from_path(open_path0) || 'index.md'
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
            toast(
              tr('files.convert.common.overwriteCancelled', {}, 'Overwrite cancelled.'),
              'info'
            )
            return
          }

          r = await call_tool(
            PDF_CONVERT_TOOL,
            { ...args_base, overwrite: true },
            { retry: 0, dedupe_key: `${dedupe_key}|overwrite_true` }
          )
          info = normalizeToolResponse(r, tr('files.convert.pdf.overwriteCompleted', {}, 'PDF overwrite conversion completed'))
        }
      }

      if (!info.success) {
        toast(
          tr(
            'files.convert.common.convertFailed',
            { error: info.text || tr('files.convert.common.unknownError', {}, 'Unknown error') },
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

      const mode = String(pickDataValue(r, 'mode', '') || '').trim().toLowerCase()
      const imagesCount = Number(pickDataValue(r, 'images_count', 0) || 0)

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
            { name: open_name, count: imagesCount },
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

  return { handle_pdf_to_note }
}

