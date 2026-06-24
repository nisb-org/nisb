import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

export function useEditorMarkdownPreview(ctx) {
  const { content, isImageMode, isCodeMode, isPdfMode, useLazyMarkdown, useVirtualText } = ctx

  if (!window.__nisb_dompurify_allow_nisb) {
    window.__nisb_dompurify_allow_nisb = true
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      try {
        if (!node || !node.getAttribute) return
        if (String(node.tagName || '').toUpperCase() !== 'A') return
        const href = String(node.getAttribute('href') || '').trim()
        if (!href) return
        if (/^nisb:\/\//i.test(href)) {
          node.setAttribute('href', href)
          node.removeAttribute('target')
          node.removeAttribute('rel')
        }
      } catch {}
    })
  }

  function _normalize_slug(slug) {
    let s = String(slug || '')

    s = s.replace(/[\u200B-\u200D\uFEFF]/g, '')
    s = s.replace(/-+/g, '-').replace(/^-+/, '').replace(/-+$/, '')

    if (s.length >= 6 && s.length % 2 === 0) {
      const half = s.length / 2
      const a = s.slice(0, half)
      const b = s.slice(half)
      if (a && a === b) s = a
    }

    return s
  }

  function _slugify(text) {
    const raw = String(text || '')
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^\w\u4e00-\u9fa5\-]/g, '')
    return _normalize_slug(raw)
  }

  function _clean_heading_text(raw) {
    let s = String(raw || '').trim()
    if (!s) return ''
    s = s.replace(/[\u200B-\u200D\uFEFF]/g, '')
    s = s.replace(/<[^>]*>/g, '')
    s = s.replace(/`+/g, '')
    s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
    s = s.replace(/\*([^*]+)\*/g, '$1')
    s = s.replace(/~~([^~]+)~~/g, '$1')
    s = s.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    return s.trim()
  }

  function transformWikiLinks(raw) {
    return String(raw || '')
  }

  const renderer = new marked.Renderer()
  let __counts = new Map()

  renderer.heading = function (...args) {
    try {
      if (args.length === 1 && args[0] && typeof args[0] === 'object' && Number.isFinite(Number(args[0].depth))) {
        const token = args[0]
        const level = Math.max(1, Math.min(6, Number(token.depth || 1)))
        const rawText = String(token.text || '')

        let innerHtml = rawText
        try {
          if (this && this.parser && typeof this.parser.parseInline === 'function' && Array.isArray(token.tokens)) {
            innerHtml = this.parser.parseInline(token.tokens)
          }
        } catch {}

        const clean = _clean_heading_text(rawText || innerHtml)
        const base = _slugify(clean)

        const prev = __counts.get(base) || 0
        const occ = prev + 1
        __counts.set(base, occ)

        const anchor_key = base ? `${base}--${occ}` : `h--${occ}`

        return `<h${level} id="heading-${anchor_key}" data-heading-anchor="${base}" data-heading-key="${anchor_key}">${innerHtml}</h${level}>`
      }

      const text = args[0]
      const level = Math.max(1, Math.min(6, Number(args[1] || 1)))
      const raw = args.length >= 3 ? String(args[2] || '') : String(text || '')

      const clean = _clean_heading_text(raw)
      const base = _slugify(clean)

      const prev = __counts.get(base) || 0
      const occ = prev + 1
      __counts.set(base, occ)

      const anchor_key = base ? `${base}--${occ}` : `h--${occ}`

      return `<h${level} id="heading-${anchor_key}" data-heading-anchor="${base}" data-heading-key="${anchor_key}">${String(
        text || ''
      )}</h${level}>`
    } catch {
      return `<h2>${String(args?.[0]?.text || args?.[0] || '')}</h2>`
    }
  }

  const lightboxVisible = ref(false)
  const lightboxImage = ref('')
  const lightboxAlt = ref('')

  function openLightbox(src, alt) {
    lightboxImage.value = src
    lightboxAlt.value = alt
    lightboxVisible.value = true
  }

  function closeLightbox() {
    lightboxVisible.value = false
  }

  function handleOpenLightboxEvent(e) {
    const d = e?.detail || {}
    const src = String(d.src || '').trim()
    if (!src) return
    openLightbox(src, String(d.alt || ''))
  }

  const renderedHtml = computed(() => {
    if (useLazyMarkdown.value || useVirtualText.value) return ''
    if (isImageMode.value || isPdfMode.value) return ''
    if (isCodeMode.value) return ''

    __counts = new Map()

    try {
      const mdSource = transformWikiLinks(content.value)
      const html = marked.parse(String(mdSource || ''), { renderer })
      return DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true },
        ALLOW_UNKNOWN_PROTOCOLS: true,
        ADD_ATTR: ['id', 'data-heading-anchor', 'data-heading-key']
      })
    } catch {
      return '<p>Markdown 错误</p>'
    }
  })

  function scheduleLoadMarkdownImages() {}
  function onLazyChunkRendered() {}

  return {
    renderedHtml,
    scheduleLoadMarkdownImages,
    onLazyChunkRendered,

    lightboxVisible,
    lightboxImage,
    lightboxAlt,
    openLightbox,
    closeLightbox,
    handleOpenLightboxEvent
  }
}
