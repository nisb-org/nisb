export function useEditorPreviewClipboard(ctx) {
  const {
    callTool,
    currentView,
    currentMode,
    editMode,
    isImageMode,
    isCodeMode,
    isPdfMode,
    currentFile,
    content,
    getFileIOApi,
    applyExternalNoteContent
  } = ctx

  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader()
      fr.onload = () => resolve(String(fr.result || ''))
      fr.onerror = reject
      fr.readAsDataURL(file)
    })
  }

  function _toast(message, type = 'info') {
    window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
  }

  async function handlePasteWebClip(e) {
    try {
      if (currentView.value !== 'main') return
      if (currentMode.value !== 'note') return
      if (editMode.value) return
      if (isImageMode.value || isCodeMode.value || isPdfMode.value) return

      const fileIOApi = typeof getFileIOApi === 'function' ? getFileIOApi() : null
      if (!fileIOApi || !fileIOApi.isCurrentFileLoadedSafe()) return
      if (!e || e.defaultPrevented) return

      const t = e?.target
      const inDisplayNote = t && typeof t.closest === 'function' ? !!t.closest('.display-mode-container') : false
      if (!inDisplayNote) return

      const cd = e.clipboardData
      if (!cd) return

      const note_path = String(currentFile.value?.path || '').trim()

      const appendToEnd = (md) => {
        const block = String(md || '').trim()
        if (!block) return false

        const old = String(content.value || '')
        const next = old.trim() ? old.replace(/\s*$/, '') + '\n\n' + block + '\n' : block + '\n'

        return applyExternalNoteContent(next, {
          autoSave: true,
          requirePath: true
        })
      }

      const items = Array.from(cd?.items || [])
      const imgItem = items.find((it) => it.kind === 'file' && String(it.type || '').startsWith('image/'))
      if (imgItem) {
        e.preventDefault()

        if (!note_path) {
          _toast('请先保存笔记后再粘贴图片（需要确定落盘目录 images/）。', 'info')
          return
        }

        const file = imgItem.getAsFile()
        if (!file) return

        _toast('Uploading image…', 'info')
        const dataUrl = await readFileAsDataURL(file)

        const res = await callTool('nisb_feed_image_stage_upload', {
          note_path,
          image_base64: dataUrl,
          filename: String(file?.name || ''),
          alt: 'image'
        })

        if (!res || res.success === false) {
          throw new Error(res?.message || 'Upload image failed.')
        }

        const md = String(res.markdown || '').trim()
        if (md) appendToEnd(md)

        _toast('Image inserted.', 'success')
        return
      }

      const html = String(cd.getData('text/html') || '').trim()
      if (!html) return

      e.preventDefault()

      if (!note_path) {
        _toast('请先保存笔记后再剪报（需要确定落盘目录 images/）。', 'info')
        return
      }

      _toast('Clipping…', 'info')

      const res = await callTool('nisb_feed_clipboard_import', {
        note_path,
        html,
        base_url: ''
      })

      if (!res || res.success === false) {
        throw new Error(res?.message || 'Clip failed.')
      }

      const md = String(res.markdown || '').trim()
      if (!md) {
        throw new Error('Clip returned empty markdown.')
      }

      appendToEnd(md)
      _toast(`Clipped. Images: ${res.saved_ok || 0}/${res.saved_total || 0}`, 'success')
    } catch (err) {
      window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message: err?.message || 'Clip failed.', type: 'error' } }))
    }
  }

  return {
    handlePasteWebClip
  }
}
