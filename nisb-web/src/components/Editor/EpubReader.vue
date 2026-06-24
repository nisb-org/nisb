<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/EpubReader.vue -->
<template>
  <div class="epub_reader_root">
    <div class="epub_topbar">
      <button class="btn" type="button" @click="prev_page" :title="t('note.reader.epub.prevPage')">
        {{ t('note.reader.epub.prevPageShort') }}
      </button>
      <button class="btn" type="button" @click="next_page" :title="t('note.reader.epub.nextPage')">
        {{ t('note.reader.epub.nextPageShort') }}
      </button>

      <div class="sep"></div>

      <button class="btn" type="button" @click="prev_chapter" :title="t('note.reader.epub.prevChapter')">
        {{ t('note.reader.epub.prevChapterShort') }}
      </button>
      <button class="btn" type="button" @click="next_chapter" :title="t('note.reader.epub.nextChapter')">
        {{ t('note.reader.epub.nextChapterShort') }}
      </button>

      <div class="title" :title="title">{{ title }}</div>

      <button class="btn btn-icon" type="button" @click="reload" :title="t('note.reader.epub.reload')">↻</button>
    </div>

    <div class="epub_viewer" ref="viewer_el"></div>

    <div v-if="loading" class="hint hint-loading">{{ t('note.reader.epub.loading') }}</div>
    <div v-else-if="!epub_array_buffer" class="hint">{{ t('note.reader.epub.empty') }}</div>
    <div v-if="error" class="err">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ePub from 'epubjs'
import JSZip from 'jszip'

const props = defineProps({
  title: { type: String, default: 'EPUB' },
  epub_array_buffer: { type: [ArrayBuffer, Uint8Array], default: null }
})

const { t } = useI18n()
const viewer_el = ref(null)
const loading = ref(false)
const error = ref('')

const toc_headings = ref([])
const current_toc_index = ref(-1)

let book = null
let rendition = null

let theme_observer = null
let readopt_observer = null
let __apply_raf = 0

const __patched_contents = new WeakSet()

function _get_readopt_root_el() {
  try {
    const el = document.querySelector('.layout-container')
    if (el) return el
  } catch {}
  try {
    const app = document.querySelector('.app')
    if (app) return app
  } catch {}
  return document.documentElement
}

function _safe_css_var(name, fallback) {
  try {
    const el = _get_readopt_root_el()
    const v = getComputedStyle(el).getPropertyValue(name)
    const s = String(v || '').trim()
    return s || fallback
  } catch {
    return fallback
  }
}

function _normalize_css_len(v, fallback) {
  const s = String(v ?? '').trim()
  if (!s) return fallback
  if (/^\d+(\.\d+)?$/.test(s)) return `${s}px`
  return s
}

function _normalize_number(v, fallback) {
  const s = String(v ?? '').trim()
  if (!s) return fallback
  const n = Number(s)
  if (Number.isFinite(n)) return String(n)
  return fallback
}

function _normalize_href(href) {
  const s = String(href || '').trim()
  if (!s) return ''
  return s.split('#')[0]
}

function _dispatch_epub_outline(headings) {
  window.dispatchEvent(new CustomEvent('nisb-epub-outline-update', { detail: { headings } }))
}

function _set_current_index_by_href(href) {
  const target = _normalize_href(href)
  if (!target) return
  const hs = toc_headings.value || []

  for (let i = 0; i < hs.length; i++) {
    const a = _normalize_href(hs[i]?.anchor)
    if (a && a === target) {
      current_toc_index.value = i
      return
    }
  }

  for (let i = 0; i < hs.length; i++) {
    const a = String(hs[i]?.anchor || '').trim()
    if (!a) continue
    if (_normalize_href(a) === target) {
      current_toc_index.value = i
      return
    }
    if (target && a.startsWith(target)) {
      current_toc_index.value = i
      return
    }
    if (target && target.startsWith(_normalize_href(a))) {
      current_toc_index.value = i
      return
    }
  }
}

function _color_for_level(level) {
  const n = Math.max(1, Math.min(6, Number(level || 1)))
  return `var(--h${n})`
}

function _flatten_nav_items(items, level, out) {
  const safe_level = Math.min(Math.max(level, 1), 6)
  ;(items || []).forEach((it) => {
    const text = String(it?.label || it?.title || '').trim()
    const href = String(it?.href || '').trim()

    const has_children = Array.isArray(it?.subitems) && it.subitems.length > 0

    if (text && href) {
      const idx = out.length
      out.push({
        level: safe_level,
        text,
        id: `epub:${idx}`, // ✅ 字符串且唯一，避免 NoteOutlinePanel hover 全高亮
        lineNumber: idx + 1,
        color: _color_for_level(safe_level),
        anchor: href,
        collapsed: false,
        hidden: false,
        hasChildren: has_children
      })
    }

    if (has_children) _flatten_nav_items(it.subitems, safe_level + 1, out)
  })
}

function _schedule_apply() {
  if (!rendition) return
  if (__apply_raf) return
  __apply_raf = requestAnimationFrame(() => {
    __apply_raf = 0
    try {
      _apply_theme_and_layout()
    } catch {}
  })
}

function cleanup() {
  try {
    if (__apply_raf) cancelAnimationFrame(__apply_raf)
  } catch {}
  __apply_raf = 0

  try {
    theme_observer?.disconnect?.()
  } catch {}
  theme_observer = null

  try {
    readopt_observer?.disconnect?.()
  } catch {}
  readopt_observer = null

  try {
    rendition?.off?.('relocated', on_relocated)
  } catch {}
  try {
    rendition?.off?.('rendered', on_rendered)
  } catch {}

  try {
    rendition?.destroy?.()
  } catch {}
  try {
    book?.destroy?.()
  } catch {}

  rendition = null
  book = null

  toc_headings.value = []
  current_toc_index.value = -1
  _dispatch_epub_outline([])
}

function on_keydown(e) {
  if (!rendition) return
  if (e.key === 'ArrowLeft') prev_chapter()
  if (e.key === 'ArrowRight') next_chapter()
}

function on_outline_jump(e) {
  try {
    const anchor = String(e?.detail?.anchor || '').trim()
    if (!anchor) return
    if (!rendition) return
    rendition.display(anchor)
    _set_current_index_by_href(anchor)
  } catch {}
}

function on_outline_mode_changed(e) {
  const mode = String(e?.detail?.mode || '').trim()
  if (mode !== 'epub') return
  try {
    _dispatch_epub_outline(toc_headings.value || [])
  } catch {}
}

function on_reading_state_changed() {
  _schedule_apply()
}

function _ensure_contents_patch(contents) {
  if (!contents || __patched_contents.has(contents)) return
  __patched_contents.add(contents)

  try {
    contents.addStylesheetRules({
      html: {
        'font-size': 'var(--nisb-epub-font-size, 16px) !important',
        background: 'var(--nisb-epub-bg) !important',
        'background-color': 'var(--nisb-epub-bg) !important',
        color: 'var(--nisb-epub-fg) !important',
        'scroll-behavior': 'var(--nisb-epub-scroll, auto) !important'
      },
      body: {
        margin: '0 !important',
        padding: '0 var(--nisb-epub-pad, 0px) !important',
        'font-size': '1rem !important',
        'line-height': 'var(--nisb-epub-line-height, 1.6) !important',
        '-webkit-text-size-adjust': '100% !important',
        background: 'var(--nisb-epub-bg) !important',
        'background-color': 'var(--nisb-epub-bg) !important',
        color: 'var(--nisb-epub-fg) !important',
        'scroll-behavior': 'var(--nisb-epub-scroll, auto) !important'
      },
      'p, li, div, span, blockquote, dd, dt, td, th, figcaption': {
        color: 'var(--nisb-epub-fg) !important',
        'font-size': '1em !important',
        'line-height': 'var(--nisb-epub-line-height, 1.6) !important'
      },
      'h1, h2, h3, h4, h5, h6': {
        color: 'var(--nisb-epub-fg) !important',
        'line-height': '1.25 !important'
      },
      a: { color: 'var(--nisb-epub-link) !important' },
      'img, svg, video, canvas': {
        'max-width': '100% !important',
        height: 'auto !important'
      }
    })
  } catch {}
}

function _apply_vars_to_contents(contents, vars) {
  if (!contents) return
  _ensure_contents_patch(contents)

  try {
    const doc = contents.document
    const root = doc && doc.documentElement ? doc.documentElement : null
    const body = doc && doc.body ? doc.body : null

    const set_var = (el, name, value) => {
      if (!el) return
      try {
        el.style.setProperty(name, String(value), 'important')
      } catch {}
    }

    set_var(root, '--nisb-epub-bg', vars.bg)
    set_var(root, '--nisb-epub-fg', vars.fg)
    set_var(root, '--nisb-epub-link', vars.link)
    set_var(root, '--nisb-epub-pad', vars.pad)
    set_var(root, '--nisb-epub-font-size', vars.font_size)
    set_var(root, '--nisb-epub-line-height', vars.line_height)
    set_var(root, '--nisb-epub-scroll', vars.scroll)

    set_var(body, '--nisb-epub-bg', vars.bg)
    set_var(body, '--nisb-epub-fg', vars.fg)
    set_var(body, '--nisb-epub-link', vars.link)
    set_var(body, '--nisb-epub-pad', vars.pad)
    set_var(body, '--nisb-epub-font-size', vars.font_size)
    set_var(body, '--nisb-epub-line-height', vars.line_height)
    set_var(body, '--nisb-epub-scroll', vars.scroll)
  } catch {}
}

function _read_current_vars() {
  const pad = _normalize_css_len(_safe_css_var('--nisb-read-padding', ''), '0px')
  const font_size = _normalize_css_len(_safe_css_var('--nisb-read-font-size', ''), '16px')
  const line_height = _normalize_number(_safe_css_var('--nisb-read-line-height', ''), '1.6')
  const scroll = String(_safe_css_var('--nisb-read-scroll-behavior', '') || 'auto').trim() || 'auto'

  const bg = _safe_css_var('--editor-bg', '#151515')
  const fg = _safe_css_var('--text-main', '#e3e3e3')
  const link = _safe_css_var('--selected', _safe_css_var('--link', '#7aa2ff'))

  return { pad, font_size, line_height, scroll, bg, fg, link }
}

function _apply_theme_and_layout() {
  if (!rendition) return

  const vars = _read_current_vars()

  try {
    rendition.spread('none')
  } catch {}

  try {
    const cs = rendition.getContents ? rendition.getContents() : []
    ;(cs || []).forEach((c) => _apply_vars_to_contents(c, vars))
  } catch {}

  try {
    rendition.themes && rendition.themes.update && rendition.themes.update('nisb_zen')
  } catch {}
}

function on_relocated(loc) {
  try {
    const href = loc?.start?.href
    if (href) _set_current_index_by_href(href)
  } catch {}
}

function on_rendered(section, contents) {
  try {
    _ensure_contents_patch(contents)
  } catch {}
  _schedule_apply()
}

function _start_theme_observer() {
  try {
    const target = document.querySelector('.app')
    if (!target) return
    theme_observer = new MutationObserver(() => _schedule_apply())
    theme_observer.observe(target, { attributes: true, attributeFilter: ['data-theme'] })
  } catch {}
}

function _start_readopt_observer() {
  try {
    const target = document.querySelector('.layout-container')
    if (!target) return
    readopt_observer = new MutationObserver(() => _schedule_apply())
    readopt_observer.observe(target, { attributes: true, attributeFilter: ['style', 'class'] })
  } catch {}
}

async function load() {
  error.value = ''
  if (!props.epub_array_buffer) return
  if (!viewer_el.value) return

  cleanup()
  loading.value = true

  try {
    window.JSZip = JSZip

    const u8 =
      props.epub_array_buffer instanceof Uint8Array
        ? props.epub_array_buffer
        : new Uint8Array(props.epub_array_buffer)

    book = ePub(u8.buffer, { openAs: 'binary', replacements: 'blobUrl' })

    rendition = book.renderTo(viewer_el.value, {
      width: '100%',
      height: '100%',
      flow: 'scrolled-doc'
    })

    try {
      rendition.on('rendered', on_rendered)
    } catch {}

    _apply_theme_and_layout()
    await rendition.display()

    try {
      const nav = await book.loaded.navigation
      const toc = Array.isArray(nav?.toc) ? nav.toc : Array.isArray(nav) ? nav : []
      const flat = []
      _flatten_nav_items(toc, 1, flat)
      toc_headings.value = flat
      _dispatch_epub_outline(flat)
    } catch {
      toc_headings.value = []
      _dispatch_epub_outline([])
    }

    try {
      rendition.on('relocated', on_relocated)
    } catch {}

    _start_theme_observer()
    _start_readopt_observer()

    window.addEventListener('keydown', on_keydown)
    window.addEventListener('nisb-outline-jump', on_outline_jump)
    window.addEventListener('nisb-outline-mode-changed', on_outline_mode_changed)
    window.addEventListener('nisb-reading-state', on_reading_state_changed)

    setTimeout(() => _schedule_apply(), 80)
  } catch (e) {
    error.value = t('note.reader.epub.renderFailed', { error: e?.message || String(e) })
    toc_headings.value = []
    _dispatch_epub_outline([])
  } finally {
    loading.value = false
  }
}

function prev_page() {
  try {
    if (!rendition) return
    rendition.prev()
  } catch {}
}

function next_page() {
  try {
    if (!rendition) return
    rendition.next()
  } catch {}
}

function prev_chapter() {
  try {
    if (!rendition) return
    const hs = toc_headings.value || []
    if (hs.length === 0) return
    const idx = current_toc_index.value >= 0 ? current_toc_index.value : 0
    const next_idx = Math.max(0, idx - 1)
    current_toc_index.value = next_idx
    const anchor = hs[next_idx]?.anchor
    if (anchor) rendition.display(anchor)
  } catch {}
}

function next_chapter() {
  try {
    if (!rendition) return
    const hs = toc_headings.value || []
    if (hs.length === 0) return
    const idx = current_toc_index.value >= 0 ? current_toc_index.value : 0
    const next_idx = Math.min(hs.length - 1, idx + 1)
    current_toc_index.value = next_idx
    const anchor = hs[next_idx]?.anchor
    if (anchor) rendition.display(anchor)
  } catch {}
}

function reload() {
  load()
}

onMounted(() => load())

onUnmounted(() => {
  window.removeEventListener('keydown', on_keydown)
  window.removeEventListener('nisb-outline-jump', on_outline_jump)
  window.removeEventListener('nisb-outline-mode-changed', on_outline_mode_changed)
  window.removeEventListener('nisb-reading-state', on_reading_state_changed)
  cleanup()
})

watch(
  () => props.epub_array_buffer,
  () => load()
)
</script>

<style scoped>
.epub_reader_root {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
  color: var(--text-main);
}

.epub_topbar {
  position: relative;
  flex: 0 0 auto;
  min-height: 44px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.epub_topbar::-webkit-scrollbar {
  display: none;
}

.epub_topbar::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 16%, var(--line)),
      transparent
    );
  opacity: 0.58;
}

.sep {
  flex: 0 0 auto;
  width: 1px;
  height: 22px;
  margin: 0 2px;
  background: color-mix(in srgb, var(--line) 86%, transparent);
  opacity: 0.9;
}

.btn {
  flex: 0 0 auto;
  height: 30px;
  min-width: max-content;
  box-sizing: border-box;
  padding: 0 0.65rem;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.btn-icon {
  width: 30px;
  min-width: 30px;
  max-width: 30px;
  padding: 0;
}

.btn:hover,
.btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active {
  transform: translateY(1px);
}

.title {
  flex: 1 1 auto;
  min-width: 8rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 780;
  letter-spacing: -0.01em;
}

.epub_viewer {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  scroll-behavior: var(--nisb-read-scroll-behavior, auto);
  background: var(--editor-bg);
  scrollbar-gutter: stable;
}

.hint,
.err {
  position: absolute;
  left: 50%;
  top: 56%;
  transform: translate(-50%, -50%);
  max-width: min(34rem, calc(100% - 2rem));
  box-sizing: border-box;
  padding: 0.85rem 1rem;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 88%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow:
    0 18px 44px rgba(0, 0, 0, 0.14),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  overflow-wrap: break-word;
  pointer-events: none;
}

.hint-loading {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  color: var(--selected);
}

.err {
  border-color: rgba(239, 68, 68, 0.36);
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.12),
      color-mix(in srgb, var(--editor-bg) 84%, transparent)
    );
  color: #ef4444;
}

@media (max-width: 720px) {
  .epub_topbar {
    padding-inline: 8px;
    gap: 5px;
  }

  .title {
    min-width: 6rem;
    font-size: 0.78rem;
  }

  .btn {
    height: 29px;
    padding-inline: 0.52rem;
    font-size: 0.72rem;
  }

  .btn-icon {
    width: 29px;
    min-width: 29px;
    max-width: 29px;
    padding: 0;
  }
}
</style>

