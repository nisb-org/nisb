// /opt/mcp-gateway/nisb-web/src/composables/editor/modules/useEditorClipboard.js
export function useEditorClipboard(ctx) {
  const {
    callTool,

    // refs
    currentView,
    currentMode,
    editMode,
    currentFile,
    content,
    loadedLineCount,

    // mode refs
    isImageMode,
    isCodeMode,
    isPdfMode,

    // callbacks
    isCurrentFileLoadedSafe,
    onContentChange
  } = ctx

  function _toast(message, type = 'info') {
    window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
  }

  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader()
      fr.onload = () => resolve(String(fr.result || ''))
      fr.onerror = reject
      fr.readAsDataURL(file)
    })
  }

  function _get_note_path_or_toast() {
    const note_path = String(currentFile.value?.path || '').trim()
    if (!note_path) {
      _toast('请先保存笔记后再粘贴（需要确定落盘目录 images/）。', 'info')
      return ''
    }
    return note_path
  }

  async function handlePasteWebClip(e) {
    try {
      if (currentView.value !== 'main') return
      if (currentMode.value !== 'note') return
      if (editMode.value) return
      if (isImageMode.value || isCodeMode.value || isPdfMode.value) return
      if (!isCurrentFileLoadedSafe()) return
      if (!e || e.defaultPrevented) return

      const t = e?.target
      const inDisplayNote = t && typeof t.closest === 'function' ? !!t.closest('.display-mode-container') : false
      if (!inDisplayNote) return

      const cd = e.clipboardData
      if (!cd) return

      const appendToEnd = (md) => {
        const block = String(md || '').trim()
        if (!block) return
        const old = String(content.value || '')
        const next = old.trim() ? old.replace(/\s*$/, '') + '\n\n' + block + '\n' : block + '\n'
        content.value = next
        loadedLineCount.value = String(content.value || '').split('\n').length
        onContentChange()
      }

      // ===== 先处理图片粘贴（文件）=====
      const items = Array.from(cd?.items || [])
      const imgItem = items.find((it) => it.kind === 'file' && String(it.type || '').startsWith('image/'))
      if (imgItem) {
        const file = imgItem.getAsFile()
        if (!file) return

        const note_path = _get_note_path_or_toast()
        if (!note_path) return

        e.preventDefault()
        _toast('Uploading image…', 'info')

        const dataUrl = await readFileAsDataURL(file)
        const res = await callTool('nisb_feed_image_stage_upload', {
          note_path,
          image_base64: dataUrl,
          filename: String(file?.name || ''),
          alt: 'image'
        })
        if (!res || res.success === false) throw new Error(res?.message || 'Upload image failed.')

        const md = String(res.markdown || '').trim()
        if (md) appendToEnd(md)

        _toast('Image inserted.', 'success')
        return
      }

      // ===== 再处理 HTML 剪报 =====
      const html = String(cd.getData('text/html') || '').trim()
      if (!html) return

      const note_path = _get_note_path_or_toast()
      if (!note_path) return

      e.preventDefault()
      _toast('Clipping…', 'info')

      const res = await callTool('nisb_feed_clipboard_import', {
        note_path,
        html,
        base_url: ''
      })
      if (!res || res.success === false) throw new Error(res?.message || 'Clip failed.')

      const md = String(res.markdown || '').trim()
      if (!md) throw new Error('Clip returned empty markdown.')

      appendToEnd(md)

      _toast(`Clipped. Images: ${res.saved_ok || 0}/${res.saved_total || 0}`, 'success')
    } catch (err) {
      _toast(err?.message || 'Clip failed.', 'error')
    }
  }

  return {
    handlePasteWebClip
  }
}

