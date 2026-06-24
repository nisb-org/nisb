// /opt/mcp-gateway/nisb-web/src/composables/editor/modules/useEditorCodeMirror.js
import { nextTick } from 'vue'
import { EditorView, minimalSetup } from 'codemirror'
import { markdown as mdLang } from '@codemirror/lang-markdown'
import { EditorState, Compartment, EditorSelection } from '@codemirror/state'
import { foldGutter, foldKeymap, foldAll, unfoldAll } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { keymap } from '@codemirror/view'
import { lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, dropCursor } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import { bracketMatching } from '@codemirror/language'
import { safe_local_storage_set } from '../../../utils/storage_safe'

export function useEditorCodeMirror(ctx) {
  const {
    callTool,

    editorContainer,
    content,
    loadedLineCount,
    editMode,
    currentFile,

    isImageMode,
    isCodeMode,
    isPdfMode,

    isMarkdownFile,

    isCurrentFileLoadedSafe,
    debouncedAutoSave,
    onContentChange
  } = ctx

  let editorView = null

  const lineNumbersCompartment = new Compartment()
  const lineWrappingCompartment = new Compartment()

  const EDITOR_CACHE_MAX_BYTES = 512 * 1024

  let defaultHideLineNumbers = false
  try {
    defaultHideLineNumbers = localStorage.getItem('nisb_cm_default_hide_line_numbers') === '1'
  } catch {}

  let lineNumbersEnabled = !defaultHideLineNumbers
  let lineWrappingEnabled = true

  function getDefaultHideLineNumbers() {
    return !!defaultHideLineNumbers
  }

  function setDefaultHideLineNumbers(v) {
    defaultHideLineNumbers = !!v
    safe_local_storage_set('nisb_cm_default_hide_line_numbers', defaultHideLineNumbers ? '1' : '0', { max_bytes: 4 * 1024 })

    if (defaultHideLineNumbers && lineNumbersEnabled) toggleLineNumbers()
    return !!defaultHideLineNumbers
  }

  function applyDefaultLineNumbersOnEnterEdit() {
    lineNumbersEnabled = !defaultHideLineNumbers
  }

  function getEditorDocString() {
    try {
      if (!editorView) return null
      return editorView.state.doc.toString()
    } catch {
      return null
    }
  }

  function _count_words_fast(text) {
    const s = String(text || '')
    let inWord = false
    let n = 0
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i)
      const isWs = c === 9 || c === 10 || c === 13 || c === 32
      if (isWs) {
        inWord = false
      } else if (!inWord) {
        inWord = true
        n += 1
      }
    }
    return n
  }

  function getEditorStats() {
    if (!editorView) return { chars: 0, words: 0, lines: 0 }
    const text = editorView.state.doc.toString()
    const lines = editorView.state.doc.lines
    const chars = text.length
    const words = _count_words_fast(text)
    return { chars, words, lines }
  }

  function _get_scroll_dom() {
    try {
      if (!editorView) return null
      return editorView.scrollDOM || null
    } catch {
      return null
    }
  }

  function _get_top_panels_height_px(view) {
    try {
      if (!view) return 0

      const direct =
        view.dom?.querySelector?.('.cm-panels-top') ||
        view.dom?.querySelector?.('.cm-panels.cm-panels-top') ||
        view.dom?.querySelector?.('.cm-panels') ||
        null

      if (!direct) return 0

      const h = Number(direct.getBoundingClientRect?.().height || 0)
      if (!Number.isFinite(h) || h <= 0) return 0

      return Math.ceil(h)
    } catch {
      return 0
    }
  }

  function _scroll_margins_ext() {
    return EditorView.scrollMargins.of((view) => {
      const topPanelsH = _get_top_panels_height_px(view)
      if (!topPanelsH) return null
      return { top: topPanelsH + 16 }
    })
  }

  function _ensure_selection_not_covered_by_top_panels(view) {
    try {
      if (!view) return false
      const topH = _get_top_panels_height_px(view)
      if (!topH) return false

      const head = view.state.selection.main.head
      const headRect = view.coordsAtPos(head)
      const scrollRect = view.scrollDOM?.getBoundingClientRect?.()
      if (!scrollRect) return false

      const coveredBottom = scrollRect.top + topH + 8

      if (!headRect) {
        view.dispatch({
          effects: EditorView.scrollIntoView(head, { y: 'start', yMargin: topH + 20 })
        })
        return true
      }

      if (headRect.top < coveredBottom) {
        view.dispatch({
          effects: EditorView.scrollIntoView(head, { y: 'start', yMargin: topH + 20 })
        })
        return true
      }

      return false
    } catch {
      return false
    }
  }

  function _get_content_padding_top_px() {
    try {
      const root = editorContainer.value
      if (!root) return 0
      const el = root.querySelector('.cm-content')
      if (!(el instanceof HTMLElement)) return 0
      const cs = window.getComputedStyle(el)
      const pt = Number.parseFloat(String(cs.paddingTop || '0'))
      return Number.isFinite(pt) ? Math.max(0, pt) : 0
    } catch {
      return 0
    }
  }

  function _get_gutters_width_px() {
    try {
      const root = editorContainer.value
      if (!root) return 0
      const el = root.querySelector('.cm-gutters')
      if (!(el instanceof HTMLElement)) return 0
      return Math.max(0, el.getBoundingClientRect().width || 0)
    } catch {
      return 0
    }
  }

  function _capture_viewport_top_pos() {
    try {
      if (!editorView) return null
      const sd = _get_scroll_dom()
      if (!sd) return null

      const r = sd.getBoundingClientRect()
      const padTop = _get_content_padding_top_px()
      const gutters = _get_gutters_width_px()

      const x = Math.min(r.right - 2, r.left + Math.max(8, gutters + 8))
      const y = Math.min(r.bottom - 2, r.top + Math.max(8, padTop + 2))

      const pos = editorView.posAtCoords({ x, y })
      if (pos === null || pos === undefined) return null
      return pos
    } catch {
      return null
    }
  }

  function _restore_viewport_top_pos(pos, y_margin = 40) {
    try {
      if (!editorView) return false
      const p = Number(pos)
      if (!Number.isFinite(p)) return false
      const safe = Math.max(0, Math.min(editorView.state.doc.length, p))

      editorView.dispatch({
        effects: EditorView.scrollIntoView(safe, { y: 'start', yMargin: Number(y_margin || 0) })
      })
      return true
    } catch {
      return false
    }
  }

  function scrollToDocLine(line_number, opts = {}) {
    try {
      if (!editorView) return false
      const n = Math.max(1, Math.min(editorView.state.doc.lines, Number(line_number || 1)))
      const line = editorView.state.doc.line(n)
      const pos = line.from
      const y_margin = Number(opts?.y_margin ?? opts?.yMargin ?? 60)
      return _restore_viewport_top_pos(pos, y_margin)
    } catch {
      return false
    }
  }

  function toggleLineNumbers() {
    const topPos = _capture_viewport_top_pos()

    lineNumbersEnabled = !lineNumbersEnabled
    if (!editorView) return lineNumbersEnabled
    editorView.dispatch({
      effects: lineNumbersCompartment.reconfigure(lineNumbersEnabled ? [lineNumbers(), highlightActiveLineGutter()] : [])
    })

    requestAnimationFrame(() => {
      if (topPos !== null) _restore_viewport_top_pos(topPos, 40)
    })
    setTimeout(() => {
      if (topPos !== null) _restore_viewport_top_pos(topPos, 40)
    }, 80)

    return lineNumbersEnabled
  }

  function toggleLineWrapping() {
    const topPos = _capture_viewport_top_pos()

    lineWrappingEnabled = !lineWrappingEnabled
    if (!editorView) return lineWrappingEnabled
    editorView.dispatch({
      effects: lineWrappingCompartment.reconfigure(lineWrappingEnabled ? [EditorView.lineWrapping] : [])
    })

    requestAnimationFrame(() => {
      if (topPos !== null) _restore_viewport_top_pos(topPos, 60)
    })
    setTimeout(() => {
      if (topPos !== null) _restore_viewport_top_pos(topPos, 60)
    }, 100)

    return lineWrappingEnabled
  }

  let __fold_busy = false

  function foldAllBlocks() {
    if (!editorView) return
    if (__fold_busy) return
    __fold_busy = true
    try {
      foldAll(editorView)
    } finally {
      setTimeout(() => {
        __fold_busy = false
      }, 0)
    }
  }

  function unfoldAllBlocks() {
    if (!editorView) return
    if (__fold_busy) return

    const lines = Number(editorView.state.doc.lines || 0)
    if (lines > 20000) {
      const ok = confirm(`当前文档约 ${lines} 行，展开全部可能卡顿，是否继续？`)
      if (!ok) return
    }

    __fold_busy = true
    // 让出主线程一拍，避免与 UI 切换/滚动恢复硬抢
    setTimeout(() => {
      try {
        if (!editorView) return
        unfoldAll(editorView)
      } finally {
        __fold_busy = false
      }
    }, 0)
  }

  function forceScrollHeightRefresh() {
    try {
      if (!editorContainer.value) return
      const scroller = editorContainer.value.querySelector('.cm-scroller')
      if (!scroller) return

      void scroller.offsetHeight
      void scroller.scrollHeight

      window.setTimeout(() => {
        try {
          void scroller.offsetHeight
          void scroller.scrollHeight
          scroller.scrollTop = scroller.scrollTop
        } catch {}
      }, 100)

      window.setTimeout(() => {
        try {
          void scroller.offsetHeight
          void scroller.scrollHeight
        } catch {}
      }, 300)
    } catch {}
  }

  function insertTextAtCursor(md) {
    if (!editorView) return
    const insert = String(md || '')
    if (!insert) return
    const sel = editorView.state.selection.main
    editorView.dispatch({
      changes: { from: sel.from, to: sel.to, insert },
      selection: { anchor: sel.from + insert.length }
    })

    content.value = editorView.state.doc.toString()
    loadedLineCount.value = editorView.state.doc.lines
  }

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

  async function uploadStageImageAndInsert(file) {
    const note_path = String(currentFile.value?.path || '').trim()
    if (!note_path) {
      _toast('请先保存笔记后再粘贴图片（需要确定落盘目录 images/）。', 'info')
      return
    }

    const dataUrl = await readFileAsDataURL(file)
    const res = await callTool('nisb_feed_image_stage_upload', {
      note_path,
      image_base64: dataUrl,
      filename: String(file?.name || ''),
      alt: 'image'
    })
    if (!res || res.success === false) throw new Error(res?.message || 'Upload image failed.')

    const md = String(res.markdown || '').trim()
    if (!md) return
    insertTextAtCursor(`\n\n${md}\n\n`)
    _toast('Image inserted.', 'success')
  }

  let __cmPasteBound = false
  let __onCmPaste = null
  let __onCmDrop = null
  let __onCmDragOver = null

  function bindCodeMirrorImagePasteDrop() {
    if (!editorView || __cmPasteBound) return
    __cmPasteBound = true

    const dom = editorView.dom

    __onCmPaste = async (e) => {
      try {
        const items = Array.from(e?.clipboardData?.items || [])
        const imgItem = items.find((it) => it.kind === 'file' && String(it.type || '').startsWith('image/'))
        if (!imgItem) return
        const file = imgItem.getAsFile()
        if (!file) return
        e.preventDefault()
        await uploadStageImageAndInsert(file)
      } catch (err) {
        _toast(err?.message || 'Paste image failed.', 'error')
      }
    }

    __onCmDragOver = (e) => {
      const types = Array.from(e?.dataTransfer?.types || [])
      if (types.includes('Files')) e.preventDefault()
    }

    __onCmDrop = async (e) => {
      try {
        const files = Array.from(e?.dataTransfer?.files || [])
        const img = files.find((f) => String(f.type || '').startsWith('image/'))
        if (!img) return
        e.preventDefault()
        await uploadStageImageAndInsert(img)
      } catch (err) {
        _toast(err?.message || 'Drop image failed.', 'error')
      }
    }

    dom.addEventListener('paste', __onCmPaste)
    dom.addEventListener('dragover', __onCmDragOver)
    dom.addEventListener('drop', __onCmDrop)
  }

  function unbindCodeMirrorImagePasteDrop() {
    if (!__cmPasteBound) return
    __cmPasteBound = false
    try {
      if (editorView?.dom && __onCmPaste) editorView.dom.removeEventListener('paste', __onCmPaste)
      if (editorView?.dom && __onCmDragOver) editorView.dom.removeEventListener('dragover', __onCmDragOver)
      if (editorView?.dom && __onCmDrop) editorView.dom.removeEventListener('drop', __onCmDrop)
    } catch {}
    __onCmPaste = null
    __onCmDrop = null
    __onCmDragOver = null
  }

  function selectNextOccurrenceCustom(view) {
    const state = view.state
    const selection = state.selection
    const ranges = selection.ranges

    if (selection.main.empty) {
      const word = state.wordAt(selection.main.from)
      if (word) {
        view.dispatch({
          selection: EditorSelection.create([EditorSelection.range(word.from, word.to)])
        })
        return true
      }
      return false
    }

    const mainRange = selection.main
    const searchText = state.sliceDoc(mainRange.from, mainRange.to)
    if (!searchText) return false

    const doc = state.doc.toString()
    let searchFrom = mainRange.to
    let nextIndex = doc.indexOf(searchText, searchFrom)

    if (nextIndex === -1) {
      nextIndex = doc.indexOf(searchText, 0)
      if (nextIndex !== -1 && nextIndex < mainRange.from) {
        const overlaps = ranges.some(
          (r) =>
            (nextIndex >= r.from && nextIndex < r.to) ||
            (nextIndex + searchText.length > r.from && nextIndex + searchText.length <= r.to)
        )
        if (overlaps) return false
      } else {
        return false
      }
    }

    const newRanges = [...ranges, EditorSelection.range(nextIndex, nextIndex + searchText.length)]
    view.dispatch({
      selection: EditorSelection.create(newRanges, newRanges.length - 1),
      scrollIntoView: true
    })
    return true
  }

  function initCodeMirror() {
    if (!editorContainer.value) return

    if (editorView) {
      try {
        unbindCodeMirrorImagePasteDrop()
      } catch {}
      editorView.destroy()
      editorView = null
    }

    let dragCopyMode = false

    let __search_scroll_fix_raf = null
    let __search_scroll_fix_timer = null

    const startState = EditorState.create({
      doc: content.value,
      extensions: [
        minimalSetup,
        _scroll_margins_ext(),

        history(),
        drawSelection(),
        dropCursor(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        bracketMatching(),

        lineNumbersCompartment.of(lineNumbersEnabled ? [lineNumbers(), highlightActiveLineGutter()] : []),
        lineWrappingCompartment.of(lineWrappingEnabled ? [EditorView.lineWrapping] : []),

        foldGutter(),
        closeBrackets(),

        ...(isMarkdownFile.value ? [mdLang()] : []),

        EditorView.domEventHandlers({
          mousedown(event, view) {
            if (event.altKey && event.button === 0) {
              event.preventDefault()
              const pos = view.posAtCoords({ x: event.clientX, y: event.clientY })
              if (pos !== null) {
                const newRanges = [...view.state.selection.ranges, EditorSelection.cursor(pos)]
                view.dispatch({
                  selection: EditorSelection.create(newRanges, newRanges.length - 1)
                })
              }
              return true
            }
            return false
          },

          dragstart(event) {
            dragCopyMode = event.ctrlKey || event.metaKey
            return false
          },

          drop(event, view) {
            if (!dragCopyMode) return false

            const pos = view.posAtCoords({ x: event.clientX, y: event.clientY })
            if (pos === null) return false

            const selection = view.state.selection.main
            if (selection.empty) return false

            event.preventDefault()

            const text = view.state.sliceDoc(selection.from, selection.to)

            view.dispatch({
              changes: { from: pos, insert: text },
              selection: EditorSelection.cursor(pos + text.length)
            })

            dragCopyMode = false
            return true
          },

          dragend() {
            dragCopyMode = false
            return false
          }
        }),

        keymap.of([
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...historyKeymap,
          ...searchKeymap,
          ...foldKeymap,
          { key: 'Mod-d', preventDefault: true, run: selectNextOccurrenceCustom }
        ]),

        EditorView.updateListener.of((update) => {
          if (update.selectionSet && !update.docChanged) {
            try {
              if (__search_scroll_fix_raf) cancelAnimationFrame(__search_scroll_fix_raf)
              if (__search_scroll_fix_timer) clearTimeout(__search_scroll_fix_timer)
            } catch {}

            __search_scroll_fix_raf = requestAnimationFrame(() => {
              try {
                _ensure_selection_not_covered_by_top_panels(update.view)
              } catch {}
            })
            __search_scroll_fix_timer = setTimeout(() => {
              try {
                _ensure_selection_not_covered_by_top_panels(update.view)
              } catch {}
            }, 80)
          }

          if (!update.docChanged) return
          if (!isCurrentFileLoadedSafe()) return

          content.value = update.state.doc.toString()
          // ✅ 不再 split：直接用 CM 的 lines
          loadedLineCount.value = update.state.doc.lines

          safe_local_storage_set('nisb_editor_content', content.value, { max_bytes: EDITOR_CACHE_MAX_BYTES })

          if (currentFile.value && !isImageMode.value && !isCodeMode.value && !isPdfMode.value) {
            debouncedAutoSave()
          }
        })
      ]
    })

    editorView = new EditorView({ state: startState, parent: editorContainer.value })

    try {
      bindCodeMirrorImagePasteDrop()
    } catch {}

    nextTick(() => forceScrollHeightRefresh())
  }

  function destroyCodeMirror() {
    if (!editorView) return
    try {
      unbindCodeMirrorImagePasteDrop()
    } catch {}
    editorView.destroy()
    editorView = null
  }

  function forceExitEditMode() {
    if (!editMode.value) return
    editMode.value = false
    destroyCodeMirror()
  }

  function toggleEditMode() {
    if (isImageMode.value || isCodeMode.value || isPdfMode.value) return

    if (editMode.value && editorView) {
      content.value = editorView.state.doc.toString()
      loadedLineCount.value = editorView.state.doc.lines
      if (typeof onContentChange === 'function') onContentChange()
    }

    const next = !editMode.value
    if (next) applyDefaultLineNumbersOnEnterEdit()

    editMode.value = next

    if (editMode.value) nextTick(() => initCodeMirror())
    else destroyCodeMirror()
  }

  function syncFromContent(newContent) {
    if (!editMode.value) return
    if (!editorView) return
    editorView.dispatch({
      changes: { from: 0, to: editorView.state.doc.length, insert: String(newContent || '') }
    })
  }

  return {
    initCodeMirror,
    destroyCodeMirror,
    toggleEditMode,
    forceExitEditMode,

    getEditorDocString,
    getEditorStats,

    toggleLineNumbers,
    toggleLineWrapping,
    foldAllBlocks,
    unfoldAllBlocks,

    syncFromContent,

    scrollToDocLine,

    getDefaultHideLineNumbers,
    setDefaultHideLineNumbers
  }
}

