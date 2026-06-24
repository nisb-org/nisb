import { nextTick } from 'vue'

export function useEditorScrollSync(ctx) {
  const {
    currentMode,
    editMode,
    currentFile,
    isImageMode,
    isPdfMode,
    isMarkdownFile,
    editorContainer,
    codeMirrorApi
  } = ctx

  const scrollAnchorByKey = new Map()
  let scrollRestoreTimer1 = null
  let scrollRestoreTimer2 = null
  const PREVIEW_TO_EDITOR_BIAS_LINES = 4

  function getScrollKey() {
    const f = currentFile.value
    return String(f?.path || f?.id || f?.name || 'unknown_file')
  }

  function clamp01(v) {
    const n = Number(v)
    if (!Number.isFinite(n)) return 0
    return Math.max(0, Math.min(1, n))
  }

  function readScrollRatio(el) {
    if (!el) return 0
    const max = (el.scrollHeight || 0) - (el.clientHeight || 0)
    if (max <= 0) return 0
    return clamp01(el.scrollTop / max)
  }

  function writeScrollRatio(el, ratio) {
    if (!el) return
    const max = (el.scrollHeight || 0) - (el.clientHeight || 0)
    if (max <= 0) {
      el.scrollTop = 0
      return
    }
    const r = clamp01(ratio)
    el.scrollTop = Math.round(r * max)
  }

  function findScrollableFallback(root) {
    if (!root) return null
    const all = Array.from(root.querySelectorAll('*'))
    for (const el of all) {
      if (!(el instanceof HTMLElement)) continue
      const cs = window.getComputedStyle(el)
      const oy = cs?.overflowY
      const canScroll = oy === 'auto' || oy === 'scroll'
      if (!canScroll) continue
      if ((el.scrollHeight || 0) > (el.clientHeight || 0) + 5) return el
    }
    return null
  }

  function getPreviewScrollEl() {
    const root = document.querySelector('.editor-wrapper') || document.body
    const el = root.querySelector('.display-mode-container .preview-content')
    if (el && el instanceof HTMLElement) return el
    return findScrollableFallback(root)
  }

  function getEditorScrollEl() {
    const root = editorContainer.value
    if (!root) return null
    const scroller = root.querySelector('.cm-scroller')
    if (scroller && scroller instanceof HTMLElement) return scroller
    return findScrollableFallback(root)
  }

  function getEditorLineHeightPx() {
    try {
      const root = editorContainer.value
      if (!root) return 20
      const el = root.querySelector('.cm-content') || root.querySelector('.cm-editor') || root
      if (!(el instanceof HTMLElement)) return 20
      const cs = window.getComputedStyle(el)
      const lh = String(cs.lineHeight || '')
      if (lh.endsWith('px')) {
        const v = Number(parseFloat(lh))
        if (Number.isFinite(v) && v > 0) return v
      }
      const fs = Number(parseFloat(String(cs.fontSize || '14px')))
      if (Number.isFinite(fs) && fs > 0) return fs * 1.5
    } catch {}
    return 20
  }

  function setEditorScrollFromRatioWithBias(ratio) {
    const el = getEditorScrollEl()
    if (!el) return
    const max = (el.scrollHeight || 0) - (el.clientHeight || 0)
    if (max <= 0) {
      el.scrollTop = 0
      return
    }
    const r = clamp01(ratio)
    let top = Math.round(r * max)

    const lh = getEditorLineHeightPx()
    const biasPx = Math.max(0, Math.round(Number(PREVIEW_TO_EDITOR_BIAS_LINES || 0) * lh))
    top = Math.max(0, top - biasPx)

    el.scrollTop = top
  }

  function captureAnchorFromPreview() {
    const key = getScrollKey()
    const el = getPreviewScrollEl()
    if (!key || !el) return
    const ratio = readScrollRatio(el)
    scrollAnchorByKey.set(key, { ratio, ts: Date.now() })
  }

  function captureAnchorFromEditor() {
    const key = getScrollKey()
    const el = getEditorScrollEl()
    if (!key || !el) return
    const ratio = readScrollRatio(el)
    scrollAnchorByKey.set(key, { ratio, ts: Date.now() })
  }

  function restoreAnchorToPreview() {
    const key = getScrollKey()
    const anchor = scrollAnchorByKey.get(key)
    if (!anchor) return
    const el = getPreviewScrollEl()
    if (!el) return
    writeScrollRatio(el, anchor.ratio)
  }

  function restoreAnchorToEditor() {
    const key = getScrollKey()
    const anchor = scrollAnchorByKey.get(key)
    if (!anchor) return
    setEditorScrollFromRatioWithBias(anchor.ratio)
  }

  function clearRestoreTimers() {
    try {
      if (scrollRestoreTimer1) clearTimeout(scrollRestoreTimer1)
      if (scrollRestoreTimer2) clearTimeout(scrollRestoreTimer2)
    } catch {}
    scrollRestoreTimer1 = null
    scrollRestoreTimer2 = null
  }

  async function scheduleRestoreAfterToggle() {
    clearRestoreTimers()

    await nextTick()

    const doRestore = () => {
      try {
        if (editMode.value) restoreAnchorToEditor()
        else restoreAnchorToPreview()
      } catch {}
    }

    requestAnimationFrame(doRestore)
    scrollRestoreTimer1 = setTimeout(doRestore, 0)
    scrollRestoreTimer2 = setTimeout(doRestore, 80)
  }

  function shouldDoScrollSync() {
    if (currentMode.value !== 'note') return false
    if (isImageMode.value || isPdfMode.value) return false
    if (!currentFile.value) return false
    if (!isMarkdownFile.value) return false
    return true
  }

  function toggleEditMode() {
    if (!shouldDoScrollSync()) {
      codeMirrorApi.toggleEditMode()
      return
    }

    if (editMode.value) captureAnchorFromEditor()
    else captureAnchorFromPreview()

    codeMirrorApi.toggleEditMode()
    scheduleRestoreAfterToggle()
  }

  function cleanup() {
    clearRestoreTimers()
  }

  return {
    toggleEditMode,
    cleanup
  }
}
