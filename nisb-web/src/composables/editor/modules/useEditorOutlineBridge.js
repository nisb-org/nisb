import { nextTick } from 'vue'

export function useEditorOutlineBridge(ctx) {
  const {
    currentMode,
    currentFile,
    loadedLineCount,
    useLazyMarkdown,
    isMarkdownFile,
    isImageMode,
    isPdfMode,
    isCodeMode,
    content,
    lazyMdRef
  } = ctx

  let outlineCtxSeq = 0
  let __jumpSeq = 0

  function emitOutlineMode(mode) {
    window.dispatchEvent(new CustomEvent('nisb-outline-mode-changed', { detail: { mode } }))
  }

  function _is_firefox() {
    try {
      return /firefox/i.test(String(navigator.userAgent || ''))
    } catch {
      return false
    }
  }

  function _collect_outline_context() {
    let path = ''
    let line_count = 0
    let use_lazy_markdown = false
    let is_markdown = false
    let content_text = ''

    const isFirefox = _is_firefox()

    try {
      const in_note = currentMode.value === 'note'
      const md = !!isMarkdownFile.value
      const blocked = !!isImageMode.value || !!isPdfMode.value || !!isCodeMode.value

      if (in_note && md && !blocked) {
        path = String(currentFile.value?.path || '').trim()
        line_count = Number(loadedLineCount.value || 0)
        use_lazy_markdown = !!useLazyMarkdown.value
        is_markdown = true

        const s = String(content.value || '')
        const max_chars = isFirefox ? 180_000 : 320_000
        if (s && s.length > 0 && s.length <= max_chars) {
          content_text = s
        } else {
          content_text = ''
        }
      }
    } catch {}

    return {
      path,
      line_count,
      use_lazy_markdown,
      is_markdown,
      content_text
    }
  }

  function emitOutlineContext(extra = {}) {
    const seq = ++outlineCtxSeq
    const ctx0 = _collect_outline_context()

    try {
      window.dispatchEvent(
        new CustomEvent('nisb-outline-context', {
          detail: {
            ...ctx0,
            seq,
            ts: Date.now(),
            ...extra
          }
        })
      )
    } catch {}

    Promise.resolve()
      .then(() => nextTick())
      .then(() => {
        if (seq !== outlineCtxSeq) return

        const ctx1 = _collect_outline_context()

        try {
          window.dispatchEvent(
            new CustomEvent('nisb-outline-context', {
              detail: {
                ...ctx1,
                seq,
                ts: Date.now(),
                post_flush: true
              }
            })
          )
        } catch {}
      })
      .catch(() => {})
  }

  function pickPreviewRootForAnchor(anchor_key, base_anchor) {
    const roots = Array.from(document.querySelectorAll('.display-mode-container .preview-content') || [])
    if (!roots.length) return null

    if (anchor_key) {
      for (const r of roots) {
        try {
          if (r.querySelector && r.querySelector(`#heading-${CSS.escape(anchor_key)}`)) return r
        } catch {}
      }
    }

    if (anchor_key) {
      for (const r of roots) {
        try {
          if (r.querySelector && r.querySelector(`[data-heading-key="${anchor_key}"]`)) return r
        } catch {}
      }
    }

    if (base_anchor) {
      for (const r of roots) {
        try {
          if (r.querySelector && r.querySelector(`[data-heading-anchor="${base_anchor}"]`)) return r
        } catch {}
      }
    }

    return roots[0] || null
  }

  function scrollHeadingIntoView({ anchor_key, base_anchor, occ, highlight }) {
    const root = pickPreviewRootForAnchor(anchor_key, base_anchor)
    if (!root) return false

    let el = null

    if (anchor_key) {
      try {
        el = root.querySelector(`#heading-${CSS.escape(anchor_key)}`)
      } catch {}
    }

    if (!el && anchor_key) {
      try {
        el = root.querySelector(`[data-heading-key="${anchor_key}"]`)
      } catch {}
    }

    if (!el && base_anchor) {
      try {
        const nodes = Array.from(
          root.querySelectorAll(
            `h1[data-heading-anchor="${base_anchor}"],h2[data-heading-anchor="${base_anchor}"],h3[data-heading-anchor="${base_anchor}"],h4[data-heading-anchor="${base_anchor}"],h5[data-heading-anchor="${base_anchor}"],h6[data-heading-anchor="${base_anchor}"]`
          )
        )
        if (nodes.length) {
          const k = Number(occ || 1)
          const idx = Number.isFinite(k) && k >= 1 ? k - 1 : 0
          el = nodes[Math.min(nodes.length - 1, Math.max(0, idx))] || null
        }
      } catch {}
    }

    if (!el) return false

    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } catch {
      try {
        el.scrollIntoView(true)
      } catch {}
    }

    if (highlight) {
      try {
        el.classList.add('highlight-flash')
        setTimeout(() => el.classList.remove('highlight-flash'), 1500)
      } catch {}
    }

    return true
  }

  async function handleOutlineJumpEvent(e) {
    const myJumpSeq = ++__jumpSeq
    const d = e?.detail || {}

    const preview = !!d.preview
    const text = String(d.text || '').trim()

    const anchor_key = String(d.anchor_key || d.anchor || '').trim()
    let base_anchor = String(d.base_anchor || '').trim()
    let occ = d.occ === null || d.occ === undefined ? null : Number(d.occ)

    if (!base_anchor && anchor_key) {
      if (anchor_key.includes('--')) {
        const parts = anchor_key.split('--')
        const last = parts.pop()
        base_anchor = parts.join('--')
        const n = Number(last)
        if (!Number.isFinite(occ)) occ = Number.isFinite(n) ? n : null
      } else {
        base_anchor = anchor_key
      }
    }

    if (!anchor_key && !text) return
    if (currentMode.value !== 'note') return
    if (!isMarkdownFile.value) return
    if (isImageMode.value || isPdfMode.value || isCodeMode.value) return

    if (useLazyMarkdown.value) {
      try {
        await nextTick()
      } catch {}
    }

    if (myJumpSeq !== __jumpSeq) return

    if (useLazyMarkdown.value && lazyMdRef.value && typeof lazyMdRef.value.jumpTo === 'function') {
      try {
        await lazyMdRef.value.jumpTo({
          anchor_key,
          anchor: base_anchor,
          occ,
          text,
          highlight: !preview
        })

        if (myJumpSeq !== __jumpSeq) return

        try {
          e.stopImmediatePropagation()
          if (typeof e.preventDefault === 'function') e.preventDefault()
        } catch {}
        return
      } catch {}
    }

    const ok = scrollHeadingIntoView({
      anchor_key,
      base_anchor,
      occ,
      highlight: !preview
    })

    if (ok) {
      try {
        e.stopImmediatePropagation()
        if (typeof e.preventDefault === 'function') e.preventDefault()
      } catch {}
    }
  }

  return {
    emitOutlineMode,
    emitOutlineContext,
    handleOutlineJumpEvent
  }
}
