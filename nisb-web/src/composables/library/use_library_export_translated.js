import { computed, ref, unref } from 'vue'
import { useI18n } from 'vue-i18n'

export function use_library_export_translated({
  library_id_ref,
  selected_doc,
  documents,
  doc_list_visible,
  call_tool,
  ensure_library_id
}) {
  const { t } = useI18n()

  function tt(key, params = {}) {
    return t(`library.center.exportTranslated.${key}`, params)
  }

  const export_modal_open = ref(false)
  const exporting_translated = ref(false)

  const export_initial_scope = computed(() => {
    if (!doc_list_visible.value && selected_doc.value?.doc_id) return 'single_doc'
    return 'library_batch'
  })

  const export_button_title = computed(() => {
    const has_single_doc = !!selected_doc.value?.doc_id
    const has_library_docs = Array.isArray(documents.value) && documents.value.some((d) => d && d.doc_id)

    if (!has_single_doc && !has_library_docs) return tt('buttonUnavailable')
    if (!doc_list_visible.value && selected_doc.value?.doc_id) return tt('buttonSingle')
    return tt('buttonBatch')
  })

  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  function open_export_translated_modal() {
    if (exporting_translated.value) return

    const has_single_doc = !!selected_doc.value?.doc_id
    const has_library_docs = Array.isArray(documents.value) && documents.value.some((d) => d && d.doc_id)

    if (!has_single_doc && !has_library_docs) {
      alert(tt('noExportableDocsInLibrary'))
      return
    }

    export_modal_open.value = true
  }

  function close_export_translated_modal() {
    if (exporting_translated.value) return
    export_modal_open.value = false
  }

  function build_default_export_user_dir(export_scope, doc) {
    if (export_scope === 'library_batch') {
      return `agent_files/library_translated_exports/${get_library_id()}`
    }
    return `agent_files/library_translated_exports/${get_library_id()}/${doc?.doc_id || ''}`
  }

  function download_text_to_local(filename, content) {
    const blob = new Blob([String(content || '')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || tt('defaultMarkdownFilename')
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 800)
  }

  function download_base64_pdf_to_local(filename, base64_text) {
    const binary = atob(String(base64_text || ''))
    const len = binary.length
    const bytes = new Uint8Array(len)
    for (let i = 0; i < len; i += 1) {
      bytes[i] = binary.charCodeAt(i)
    }
    const blob = new Blob([bytes], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || tt('defaultPdfFilename')
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 800)
  }

  function download_base64_zip_to_local(filename, base64_text) {
    const binary = atob(String(base64_text || ''))
    const len = binary.length
    const bytes = new Uint8Array(len)
    for (let i = 0; i < len; i += 1) {
      bytes[i] = binary.charCodeAt(i)
    }
    const blob = new Blob([bytes], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || tt('defaultMarkdownPackageFilename')
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 800)
  }

  async function export_one_translated_doc(doc, payload) {
    const common_payload = {
      library_id: get_library_id(),
      doc_id: doc.doc_id,
      target_language: payload?.target_language || 'zh-CN',
      export_filename: payload?.export_scope === 'single_doc' ? (payload?.export_filename || '') : '',
      save_to_nisb: !!payload?.save_to_nisb,
      include_untranslated: !!payload?.include_untranslated,
      export_user_dir: payload?.save_to_nisb
        ? (payload?.export_user_dir || build_default_export_user_dir(payload?.export_scope, doc))
        : ''
    }

    if (payload?.export_format === 'pdf') {
      return await call_tool('nisb_library_export_translated_pdf', {
        ...common_payload,
        return_base64: !!payload?.download_to_local,
        layout_mode: payload?.pdf_layout_mode || 'auto',
        line_chars_cjk: Number(payload?.pdf_line_chars_cjk || 20),
        line_words_en: Number(payload?.pdf_line_words_en || 8),
        auto_fit_page_width: !!payload?.pdf_auto_fit_page_width,
        page_width_mm: payload?.pdf_auto_fit_page_width ? null : Number(payload?.pdf_page_width_mm || 0),
        page_height_mm: Number(payload?.pdf_page_height_mm || 170),
        margin_left_right_mm: Number(payload?.pdf_margin_left_right_mm || 4),
        margin_top_bottom_mm: Number(payload?.pdf_margin_top_bottom_mm || 6),
        font_size_pt:
          payload?.pdf_font_size_pt == null || payload?.pdf_font_size_pt === ''
            ? null
            : Number(payload?.pdf_font_size_pt),
        font_path: payload?.pdf_font_path || '',
        include_span_annotations: !!payload?.pdf_include_span_annotations,
        annotation_style: payload?.pdf_annotation_style || 'below_card',
        enable_page_background: !!payload?.pdf_enable_page_background,
        enable_header_decoration: !!payload?.pdf_enable_header_decoration,
        enable_paragraph_spacing: !!payload?.pdf_enable_paragraph_spacing,
        enable_annotation_card_style: !!payload?.pdf_enable_annotation_card_style
      })
    }

    return await call_tool('nisb_library_export_translated_md', {
      ...common_payload,
      return_content: !!payload?.download_to_local
    })
  }

  function build_single_pdf_message(res) {
    return [
      res.message || tt('singlePdfDone'),
      res.saved_to_nisb && res.export_path ? tt('savedPath', { path: res.export_path }) : '',
      tt('translatedSpans', {
        translated: res.translated_span_count || 0,
        total: res.total_span_count || 0
      }),
      tt('layoutMode', { value: res.layout_mode || 'auto' }),
      tt('pageMode', { value: res.page_mode || 'adaptive' }),
      tt('pageSize', {
        width: res.page_width_mm || '-',
        height: res.page_height_mm || '-'
      }),
      tt('marginLeftRight', { value: res.margin_left_right_mm || 4 }),
      tt('marginTopBottom', { value: res.margin_top_bottom_mm || 6 }),
      tt('lineCharsCjk', { value: res.line_chars_cjk || 20 }),
      tt('lineWordsEn', { value: res.line_words_en || 8 }),
      tt('fontName', { value: res.font_name || '-' }),
      res.font_size ? tt('fontSize', { value: res.font_size }) : '',
      Number(res.embedded_images_count || 0) > 0 ? tt('embeddedImages', { value: res.embedded_images_count }) : '',
      Number(res.missing_images_count || 0) > 0 ? tt('missingImages', { value: res.missing_images_count }) : '',
      Number(res.missing_span_count || 0) > 0 ? tt('missingSpans', { value: res.missing_span_count }) : ''
    ].filter(Boolean).join('\n')
  }

  function build_single_md_message(res) {
    return [
      res.message || tt('singleMarkdownDone'),
      res.saved_to_nisb && res.export_path ? tt('savedPath', { path: res.export_path }) : '',
      tt('translatedSpans', {
        translated: res.translated_span_count || 0,
        total: res.total_span_count || 0
      }),
      res.returned_package
        ? tt('localPackage', {
            value: res.markdown_package_filename || tt('defaultPackageGenerated')
          })
        : '',
      Number(res.packaged_images_count || 0) > 0 ? tt('packagedImages', { value: res.packaged_images_count }) : '',
      Number(res.missing_packaged_images_count || 0) > 0
        ? tt('missingPackagedImages', { value: res.missing_packaged_images_count })
        : '',
      Number(res.missing_span_count || 0) > 0 ? tt('missingSpans', { value: res.missing_span_count }) : ''
    ].filter(Boolean).join('\n')
  }

  async function maybe_download_single_result(doc, payload, res) {
    if (!payload?.download_to_local) return

    if (payload?.export_format === 'pdf') {
      if (!res?.pdf_base64) {
        throw new Error(
          tt('backendMissingPdfBase64', {
            name: doc.filename || doc.doc_id
          })
        )
      }
      download_base64_pdf_to_local(res.export_filename, res.pdf_base64)
      return
    }

    if (res?.markdown_package_base64) {
      download_base64_zip_to_local(
        res.markdown_package_filename ||
          ((res.export_filename || tt('defaultMarkdownFilename')).replace(/\.md$/i, '') + '_md_images.zip'),
        res.markdown_package_base64
      )
      return
    }

    if (res?.markdown_content) {
      download_text_to_local(res.export_filename, res.markdown_content)
      return
    }

    throw new Error(
      tt('backendMissingMarkdownResult', {
        name: doc.filename || doc.doc_id
      })
    )
  }

  function get_docs_for_export(export_scope) {
    if (export_scope === 'single_doc') {
      return selected_doc.value?.doc_id ? [selected_doc.value] : []
    }
    return (Array.isArray(documents.value) ? documents.value : []).filter((d) => d && d.doc_id)
  }

  async function confirm_export_translated(payload) {
    if (!ensure_library_id()) return

    const export_scope = payload?.export_scope || 'single_doc'
    const docs_to_export = get_docs_for_export(export_scope)
    if (!docs_to_export.length) {
      alert(export_scope === 'single_doc' ? tt('noFocusedDoc') : tt('noBatchDocs'))
      return
    }

    exporting_translated.value = true
    try {
      if (export_scope === 'single_doc') {
        const doc = docs_to_export[0]
        const res = await export_one_translated_doc(doc, payload)

        if (!res || res.status !== 'success') {
          alert(
            payload?.export_format === 'pdf'
              ? tt('pdfExportFailed', { message: res?.message || tt('unknownError') })
              : tt('markdownExportFailed', { message: res?.message || tt('unknownError') })
          )
          return
        }

        await maybe_download_single_result(doc, payload, res)
        alert(payload?.export_format === 'pdf' ? build_single_pdf_message(res) : build_single_md_message(res))
        export_modal_open.value = false
        return
      }

      const success_items = []
      const failed_items = []

      for (let i = 0; i < docs_to_export.length; i += 1) {
        const doc = docs_to_export[i]
        try {
          const res = await export_one_translated_doc(doc, payload)
          if (!res || res.status !== 'success') {
            failed_items.push({
              doc_id: doc.doc_id,
              filename: doc.filename || doc.doc_id,
              message: res?.message || tt('unknownError')
            })
            continue
          }

          await maybe_download_single_result(doc, payload, res)
          success_items.push({
            doc_id: doc.doc_id,
            filename: doc.filename || doc.doc_id,
            export_path: res.export_path || '',
            translated_span_count: Number(res.translated_span_count || 0),
            total_span_count: Number(res.total_span_count || 0)
          })

          await sleep(180)
        } catch (e) {
          failed_items.push({
            doc_id: doc.doc_id,
            filename: doc.filename || doc.doc_id,
            message: e?.message || String(e)
          })
        }
      }

      const failed_docs_text = failed_items.length
        ? `${tt('failedDocsHeader')}\n${failed_items
            .slice(0, 8)
            .map((it) =>
              tt('failedDocItem', {
                filename: it.filename,
                message: it.message
              })
            )
            .join('\n')}${failed_items.length > 8 ? `\n${tt('failedDocsMore')}` : ''}`
        : ''

      const msg = [
        tt('batchDone'),
        tt('batchScopeCurrentLibrary'),
        tt('totalCount', { value: docs_to_export.length }),
        tt('successCount', { value: success_items.length }),
        tt('failedCount', { value: failed_items.length }),
        payload?.save_to_nisb
          ? tt('savedDirectory', {
              value: payload?.export_user_dir || build_default_export_user_dir('library_batch', null)
            })
          : '',
        payload?.download_to_local
          ? tt('localDownloadTriggered', { value: success_items.length })
          : '',
        failed_docs_text
      ].filter(Boolean).join('\n')

      alert(msg)
      export_modal_open.value = false
    } catch (e) {
      console.error('[library] export translated failed:', e)
      alert(tt('exportFailed', { message: e?.message || String(e) }))
    } finally {
      exporting_translated.value = false
    }
  }

  return {
    export_modal_open,
    exporting_translated,
    export_initial_scope,
    export_button_title,
    open_export_translated_modal,
    close_export_translated_modal,
    confirm_export_translated
  }
}
