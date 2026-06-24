import { useI18n } from 'vue-i18n'

import {
  toast as toast_emit,
  pick_cm,
  cm_target_path,
  cm_target_name,
  cm_target_file_type,
  cm_target_id,
  extract_nisb_file_path,
  copy_to_clipboard,
  get_uid,
  normalize_rel_path,
  is_binary_file,
  is_pdf_file,
  is_epub_file,
  is_doc_file,
  is_docx_file,
  is_ppt_file,
  is_pptx_file,
  is_image_file,
  get_parent_dir,
  looks_timeout_resp,
  pick_display_name_from_path
} from './actions/left_sidebar_actions_utils'

import { create_left_sidebar_binary_actions } from './actions/left_sidebar_actions_binary'
import { create_left_sidebar_pdf_convert_actions } from './actions/left_sidebar_actions_convert_pdf'
import { create_left_sidebar_epub_convert_actions } from './actions/left_sidebar_actions_convert_epub'
import { create_left_sidebar_office_convert_actions } from './actions/left_sidebar_actions_convert_office'
import { create_left_sidebar_library_actions } from './actions/left_sidebar_actions_library'
import { create_left_sidebar_file_actions } from './actions/left_sidebar_actions_files'
import { create_left_sidebar_rss_actions } from './actions/left_sidebar_actions_rss'
import { create_left_sidebar_extensions_actions } from './actions/left_sidebar_actions_extensions'
import { create_left_sidebar_txt_convert_actions } from './actions/left_sidebar_actions_convert_txt'

function format_message(template, params = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
    if (params?.[key] === undefined || params?.[key] === null) return ''
    return String(params[key])
  })
}

function create_local_translator(t) {
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

export function use_left_sidebar_actions({
  call_tool,
  context_menu,
  hide_context_menu,
  show_context_menu,
  current_workspace,
  workspaces,
  library_list_ref,
  send_to_library_dialog,
  suppress_focus_persist
}) {
  const { t } = useI18n({ useScope: 'global' })
  const tr = create_local_translator(t)

  function toast(message, type = 'info', duration = 2000) {
    toast_emit(message, type, duration)
  }

  function _pick_cm(cm_in) {
    return pick_cm(context_menu, cm_in)
  }

  const binary_actions = create_left_sidebar_binary_actions({
    call_tool,
    toast,
    get_uid,
    normalize_rel_path
  })

  const pdf_convert_actions = create_left_sidebar_pdf_convert_actions({
    call_tool,
    toast,
    hide_context_menu,
    current_workspace,
    pick_cm: _pick_cm,
    cm_target_path,
    cm_target_name,
    extract_nisb_file_path,
    is_pdf_file,
    normalize_rel_path,
    looks_timeout_resp,
    pick_display_name_from_path,
    t
  })

  const epub_convert_actions = create_left_sidebar_epub_convert_actions({
    call_tool,
    toast,
    hide_context_menu,
    current_workspace,
    pick_cm: _pick_cm,
    cm_target_path,
    cm_target_name,
    extract_nisb_file_path,
    is_epub_file,
    pick_display_name_from_path,
    t
  })

  const office_convert_actions = create_left_sidebar_office_convert_actions({
    call_tool,
    toast,
    hide_context_menu,
    current_workspace,
    pick_cm: _pick_cm,
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
  })

  const txt_convert_actions = create_left_sidebar_txt_convert_actions({
    call_tool,
    toast,
    hide_context_menu,
    current_workspace,
    pick_cm: _pick_cm,
    cm_target_path,
    cm_target_name,
    extract_nisb_file_path,
    normalize_rel_path,
    pick_display_name_from_path,
    get_uid,
    t
  })

  const library_actions = create_left_sidebar_library_actions({
    call_tool,
    hide_context_menu,
    library_list_ref,
    pick_cm: _pick_cm,
    cm_target_id,
    cm_target_name
  })

  const file_actions = create_left_sidebar_file_actions({
    call_tool,
    toast,
    hide_context_menu,
    current_workspace,
    library_list_ref,
    send_to_library_dialog,

    pick_cm: _pick_cm,
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
  })

  const rss_actions = create_left_sidebar_rss_actions({
    call_tool,
    toast,
    hide_context_menu,
    pick_cm: _pick_cm,
    cm_target_id,
    cm_target_name
  })

  const extensions_actions = create_left_sidebar_extensions_actions({
    hide_context_menu,
    pick_cm: _pick_cm,
    cm_target_path,
    cm_target_name,
    cm_target_file_type,
    extract_nisb_file_path
  })

  async function handle_epub_read_new_tab(cm_in) {
    const cm = _pick_cm(cm_in)
    const p0 = cm_target_path(cm)
    const n0 = cm_target_name(cm) || p0

    const p_raw = extract_nisb_file_path(p0) || p0
    const n = n0

    hide_context_menu()

    if (!p_raw) {
      return toast(
        tr('files.open.epub.pathMissing', {}, 'EPUB path was not found.'),
        'error',
        2500
      )
    }

    if (!is_epub_file(n) && !is_epub_file(p_raw)) {
      return toast(
        tr('files.open.epub.notExpectedFile', {}, 'Current file is not .epub.'),
        'info',
        2200
      )
    }

    try {
      await binary_actions.open_epub_read_new_tab({ epub_path_raw: p_raw, title: n })
    } catch (e) {
      toast(
        tr(
          'files.open.epub.openFailed',
          { error: e?.message || String(e) },
          'Failed to open EPUB: {error}'
        ),
        'error',
        3500
      )
    }
  }

  async function on_context_menu_action({ action, payload }) {
    switch (action) {
      case 'library_rename':
        return await library_actions.handle_library_rename()
      case 'library_info':
        return await library_actions.handle_library_info()
      case 'library_delete':
        return await library_actions.handle_library_delete()

      case 'extension_click':
        return extensions_actions.handle_extension_click(payload?.ext)

      case 'toggle_favorite':
        return await file_actions.handle_toggle_favorite()
      case 'copy_internal_link':
        return await file_actions.handle_copy_internal_link()

      case 'open_binary_new_tab': {
        const p = String(context_menu.value.targetPath || '').trim()
        const n = String(context_menu.value.targetName || '').trim() || p
        hide_context_menu()

        if (!p) {
          return toast(
            tr('files.open.binary.pathMissing', {}, 'File path was not found.'),
            'error',
            2500
          )
        }

        if (!is_binary_file(n) && !is_binary_file(p)) {
          return toast(
            tr(
              'files.open.binary.unsupported',
              {},
              'This file does not support binary preview.'
            ),
            'info',
            2200
          )
        }

        try {
          await binary_actions.preview_binary(p)
        } catch (e) {
          toast(
            tr(
              'files.open.binary.previewFailed',
              { error: e?.message || String(e) },
              'Preview failed: {error}'
            ),
            'error',
            3000
          )
        }
        return
      }

      case 'send_file_to_library':
        return file_actions.handle_send_file_to_library()
      case 'send_dir_to_library':
        return file_actions.handle_send_dir_to_library()

      case 'pdf_to_note':
        return await pdf_convert_actions.handle_pdf_to_note()

      case 'epub_read_new_tab':
        return await handle_epub_read_new_tab()
      case 'epub_to_note':
        return await epub_convert_actions.handle_epub_to_note()

      case 'doc_to_note':
        return await office_convert_actions.handle_doc_to_note()
      case 'docx_to_note':
        return await office_convert_actions.handle_docx_to_note()
      case 'ppt_to_note':
        return await office_convert_actions.handle_ppt_to_note()
      case 'pptx_to_note':
        return await office_convert_actions.handle_pptx_to_note()

      case 'txt_to_structured_md':
        return await txt_convert_actions.handle_txt_to_structured_md()

      case 'note_to_brain':
        return await file_actions.handle_note_to_brain()
      case 'batch_notes_to_brain':
        return await file_actions.handle_batch_notes_to_brain()

      case 'copy_image_reference':
        return await file_actions.handle_copy_image_reference()

      case 'rename':
        return await file_actions.handle_rename()
      case 'move':
        return await file_actions.handle_move()
      case 'delete':
        return await file_actions.handle_delete()
      case 'delete_recursive':
        return await file_actions.handle_delete_recursive()

      case 'create_file_in_dir':
        return await file_actions.handle_create_file_in_dir()
      case 'create_dir_in_dir':
        return await file_actions.handle_create_dir_in_dir()

      case 'rss_rename':
        return await rss_actions.handle_rss_rename()
      case 'rss_edit_tags':
        return await rss_actions.handle_rss_edit_tags()
      case 'rss_delete':
        return await rss_actions.handle_rss_delete()

      default:
        toast(
          tr(
            'files.contextMenu.unimplementedAction',
            { action: String(action) },
            'Menu action is not implemented: {action}'
          ),
          'warning',
          2000
        )
    }
  }

  return {
    is_binary_file,
    is_pdf_file,
    is_epub_file,
    is_docx_file,
    is_pptx_file,
    is_image_file,

    on_context_menu_action,
    handle_send_to_library_sent: file_actions.handle_send_to_library_sent,

    cleanup_binary_blob_urls: binary_actions.cleanup_binary_blob_urls
  }
}
