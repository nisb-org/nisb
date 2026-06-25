<template>
  <div ref="wrapRef" class="display-mode-container">
    <div class="preview-content">
      <div
        v-for="c in renderedChunks"
        :key="c.id"
        class="lm-chunk"
        :data-lm-chunk-id="c.id"
        v-html="c.html"
      ></div>

      <div ref="sentinelRef" class="lm-sentinel"></div>

      <div v-if="loading" class="lm-state lm-loading">{{ t('note.reader.lazyMarkdown.loading') }}</div>
      <div v-else-if="done && renderedChunks.length > 0" class="lm-state lm-done">
        {{ t('note.reader.lazyMarkdown.reachedEnd') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useImageLoader } from '../composables/useImageLoader'
import useMCP from '../composables/useMCP'

const emit = defineEmits(['chunkRendered'])

const props = defineProps({
  content: { type: String, default: '' },
  chunkSize: { type: Number, default: 600 },
  initialChunks: { type: Number, default: 3 },
  stepChunks: { type: Number, default: 3 },
  autoEagerMaxLines: { type: Number, default: 800 },
  autoEagerMaxChars: { type: Number, default: 160000 },
  eager: { type: Boolean, default: false },
  rootMargin: { type: String, default: '1200px 0px 1200px 0px' },
  onOpenLightbox: { type: Function, default: null }
})

const { t } = useI18n()
const { callTool } = useMCP()
const { enhanceMarkdownDom } = useImageLoader()

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

const wrapRef = ref(null)
const sentinelRef = ref(null)

const chunks = ref([])
const renderedChunks = ref([])
const nextIndex = ref(0)

const loading = ref(false)
const done = ref(false)

const anchorToChunk = ref(Object.create(null))
const headingMetaByChunk = ref([])

let observer = null
let scrollEl = null

let __alive = true
let __refreshSeq = 0
function _is_stale(seq) {
  return !__alive || seq !== __refreshSeq
}

function _now_ms() {
  try {
    return typeof performance !== 'undefined' && typeof performance.now === 'function' ? performance.now() : Date.now()
  } catch {
    return Date.now()
  }
}

const __is_firefox = (() => {
  try {
    return /firefox/i.test(String(navigator.userAgent || ''))
  } catch {
    return false
  }
})()

function _request_idle(cb, { timeout = 350 } = {}) {
  if (typeof window.requestIdleCallback === 'function') return window.requestIdleCallback(cb, { timeout })
  return window.setTimeout(() => cb({ didTimeout: true, timeRemaining: () => 0 }), 0)
}

function _cancel_idle(id) {
  try {
    if (typeof window.cancelIdleCallback === 'function') window.cancelIdleCallback(id)
    else clearTimeout(id)
  } catch {}
}

function _yield_to_main() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

async function _wait_until_not_loading(seq, max_ms = 1800) {
  const start = Date.now()
  while (!_is_stale(seq) && loading.value) {
    if (Date.now() - start > max_ms) return false
    await _yield_to_main()
  }
  return !_is_stale(seq)
}

/* -----------------------
 * Outline context path (for on-demand full read)
 * ----------------------- */

const OUTLINE_PATH_KEY = 'nisb_outline_file_path'
const currentPath = ref('')

function _read_path_from_storage() {
  try {
    const p = String(localStorage.getItem(OUTLINE_PATH_KEY) || '').trim()
    return p
  } catch {
    return ''
  }
}

function _set_current_path(p) {
  const s = String(p || '').trim()
  if (s && s !== currentPath.value) currentPath.value = s
}

function _on_outline_context(e) {
  const d = e?.detail || {}
  const p = String(d.path || '').trim()
  if (p) _set_current_path(p)
}

/* -----------------------
 * Effective content (allow internal full-text override)
 * ----------------------- */

const overrideContent = ref('')
let __override_for_path = ''
let __full_load_attempt = { path: '', ts: 0 }

function _get_effective_content() {
  const o = String(overrideContent.value || '')
  if (o) return o
  return String(props.content || '')
}

function _maybe_clear_override_if_path_changed() {
  const p = String(currentPath.value || _read_path_from_storage() || '').trim()
  if (!p) return
  if (__override_for_path && __override_for_path !== p) {
    overrideContent.value = ''
    __override_for_path = ''
    __full_load_attempt = { path: '', ts: 0 }
  }
}

async function _try_upgrade_to_full_content(seq) {
  if (_is_stale(seq)) return false

  const p = String(currentPath.value || _read_path_from_storage() || '').trim()
  if (!p) return false

  const now = Date.now()
  if (__full_load_attempt.path === p && now - (__full_load_attempt.ts || 0) < 12_000) return false
  __full_load_attempt = { path: p, ts: now }

  let res = null
  try {
    res = await callTool('nisb_file_read', { filename: p })
  } catch {
    return false
  }

  if (_is_stale(seq)) return false

  const full = String(res?.content ?? res?.text ?? res?.data ?? '')
  if (!full.trim()) return false

  const cur = _get_effective_content()
  if (full.length <= cur.length + 1024) return false

  overrideContent.value = full
  __override_for_path = p

  await refresh()
  return true
}

/* -----------------------
 * Slug / clean (must match anchor_key contract)
 * ----------------------- */

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

/* -----------------------
 * marked renderer: support BOTH old & new signatures
 * ----------------------- */

let __cur_heading_meta = null
let __cur_heading_meta_i = 0

const renderer = new marked.Renderer()

function _next_heading_meta() {
  const meta =
    __cur_heading_meta && __cur_heading_meta_i < __cur_heading_meta.length ? __cur_heading_meta[__cur_heading_meta_i++] : null
  return meta
}

function _extract_base_occ_from_meta(meta, fallback_clean) {
  let base = _normalize_slug(meta?.base || _slugify(fallback_clean))
  let occ = 1

  const metaKey = String(meta?.anchor_key || '').trim()
  if (metaKey) {
    const m = metaKey.match(/^(.*)--(\d+)$/)
    if (m) {
      const mb = _normalize_slug(m[1])
      const n = Number(m[2])
      if (mb) base = mb
      if (Number.isFinite(n) && n >= 1) occ = n
    }
  }

  const anchor_key = base ? `${base}--${occ}` : `h--${occ}`
  const base_anchor = base || ''
  return { anchor_key, base_anchor }
}

renderer.heading = function (...args) {
  try {
    if (args.length === 1 && args[0] && typeof args[0] === 'object' && Number.isFinite(Number(args[0].depth))) {
      const token = args[0]
      const depth = Math.max(1, Math.min(6, Number(token.depth || 1)))
      const rawText = String(token.text || '')

      let innerHtml = rawText
      try {
        if (this && this.parser && typeof this.parser.parseInline === 'function' && Array.isArray(token.tokens)) {
          innerHtml = this.parser.parseInline(token.tokens)
        }
      } catch {}

      const meta = _next_heading_meta()
      const clean = _clean_heading_text(rawText || innerHtml)
      const { anchor_key, base_anchor } = _extract_base_occ_from_meta(meta, clean)

      return `<h${depth} id="heading-${anchor_key}" data-heading-anchor="${base_anchor}" data-heading-key="${anchor_key}">${innerHtml}</h${depth}>`
    }

    const text = args[0]
    const level = Math.max(1, Math.min(6, Number(args[1] || 1)))
    const raw = args.length >= 3 ? String(args[2] || '') : String(text || '')

    const meta = _next_heading_meta()
    const clean = _clean_heading_text(raw)
    const { anchor_key, base_anchor } = _extract_base_occ_from_meta(meta, clean)

    return `<h${level} id="heading-${anchor_key}" data-heading-anchor="${base_anchor}" data-heading-key="${anchor_key}">${String(
      text || ''
    )}</h${level}>`
  } catch {
    return `<h2>${String(args?.[0]?.text || args?.[0] || '')}</h2>`
  }
}

function _escape_html_text(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderChunkToSafeHtml(mdText, chunkIndex) {
  try {
    __cur_heading_meta = headingMetaByChunk.value?.[chunkIndex] || []
    __cur_heading_meta_i = 0

    const html = marked.parse(String(mdText || ''), { renderer })
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      ALLOW_UNKNOWN_PROTOCOLS: true,
      ADD_ATTR: ['id', 'data-heading-anchor', 'data-heading-key', 'controls', 'autoplay', 'download', 'data-nisb-audio-b64', 'data-nisb-audio-url', 'data-nisb-audio-mime', 'data-nisb-audio-name']
    })
  } catch {
    return `<p>${_escape_html_text(t('note.reader.lazyMarkdown.renderFailed'))}</p>`
  } finally {
    __cur_heading_meta = null
    __cur_heading_meta_i = 0
  }
}

/* -----------------------
 * Split into chunks (async)
 * ----------------------- */

async function _split_into_heading_chunks_with_anchor_key_async(text, maxLinesPerChunk, seq) {
  const s = String(text || '')
  const out = []
  const anchorMap = Object.create(null)
  const headMeta = []

  const reHeading = /^#{1,6}\s+(.+?)\s*$/

  let inFence = false
  let chunkStart = 0
  let linesInChunk = 0
  const occMap = new Map()

  function _ensure_meta(idx) {
    if (!headMeta[idx]) headMeta[idx] = []
  }

  let slice_start = _now_ms()

  let i = 0
  const len = s.length

  while (i <= len) {
    if (_is_stale(seq)) return null

    const nl = s.indexOf('\n', i)
    const lineEnd = nl < 0 ? len : nl
    const line = s.slice(i, lineEnd)
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      inFence = !inFence
    } else if (!inFence) {
      const m = line.match(reHeading)
      if (m) {
        if (i > chunkStart) {
          out.push(s.slice(chunkStart, i))
          chunkStart = i
          linesInChunk = 0
        }

        const chunkIndex = out.length
        _ensure_meta(chunkIndex)

        const clean = _clean_heading_text(m[1] || '')
        const base = _slugify(clean)
        const prev = occMap.get(base) || 0
        const occ = prev + 1
        occMap.set(base, occ)

        const anchor_key = base ? `${base}--${occ}` : `h--${occ}`

        if (typeof anchorMap[anchor_key] === 'undefined') anchorMap[anchor_key] = chunkIndex
        if (base && typeof anchorMap[base] === 'undefined') anchorMap[base] = chunkIndex

        headMeta[chunkIndex].push({ anchor_key, base })
      }
    }

    linesInChunk += 1
    i = lineEnd + 1

    if (!inFence && Number.isFinite(maxLinesPerChunk) && maxLinesPerChunk > 0) {
      if (linesInChunk >= maxLinesPerChunk && i <= len) {
        out.push(s.slice(chunkStart, i))
        chunkStart = i
        linesInChunk = 0
      }
    }

    if (nl < 0) break

    const now = _now_ms()
    if (now - slice_start > 10) {
      await _yield_to_main()
      slice_start = _now_ms()
    }
  }

  if (chunkStart <= len) {
    const rest = s.slice(chunkStart)
    if (rest || !out.length) out.push(rest)
  }

  return { out: out.length ? out : [''], anchorMap, headMeta }
}

/* -----------------------
 * Enhance queue (idle, latest-only)
 * ----------------------- */

let __enhance_run_id = 0
let __enhance_idle_id = null
let __enhance_queue_seq = 0
let __enhance_queue = []
let __enhance_queue_set = new Set()
let __enhance_processing = false

function _reset_enhance_queue_for_seq(seq) {
  if (__enhance_idle_id !== null) {
    _cancel_idle(__enhance_idle_id)
    __enhance_idle_id = null
  }
  __enhance_queue_seq = seq
  __enhance_queue = []
  __enhance_queue_set = new Set()
  __enhance_processing = false
  __enhance_run_id += 1
}

function _enqueue_enhance_chunks(chunkIds, seq) {
  if (_is_stale(seq)) return
  if (seq !== __enhance_queue_seq) _reset_enhance_queue_for_seq(seq)

  for (const id of chunkIds || []) {
    const k = Number(id)
    if (!Number.isFinite(k)) continue
    if (__enhance_queue_set.has(k)) continue
    __enhance_queue_set.add(k)
    __enhance_queue.push(k)
  }

  _kick_enhance_queue(seq)
}

function _kick_enhance_queue(seq) {
  if (_is_stale(seq)) return
  if (__enhance_processing) return
  if (!__enhance_queue.length) return

  __enhance_processing = true
  const my_run_id = __enhance_run_id

  if (__enhance_idle_id !== null) {
    _cancel_idle(__enhance_idle_id)
    __enhance_idle_id = null
  }

  __enhance_idle_id = _request_idle(
    async () => {
      __enhance_idle_id = null
      try {
        if (_is_stale(seq)) return
        if (seq !== __enhance_queue_seq) return
        if (my_run_id !== __enhance_run_id) return
        if (!wrapRef.value) return
        if (!__enhance_queue.length) return

        const id = __enhance_queue.shift()
        __enhance_queue_set.delete(id)

        await nextTick()
        if (_is_stale(seq)) return
        if (seq !== __enhance_queue_seq) return
        if (my_run_id !== __enhance_run_id) return
        if (!wrapRef.value) return

        const el = wrapRef.value.querySelector?.(`.lm-chunk[data-lm-chunk-id="${id}"]`)
        if (!el) return

        try {
          await enhanceMarkdownDom({
            rootEl: el,
            onOpenLightbox: typeof props.onOpenLightbox === 'function' ? props.onOpenLightbox : null,
            run_id: my_run_id
          })
        } catch {}
      } finally {
        __enhance_processing = false
        if (!_is_stale(seq) && seq === __enhance_queue_seq && my_run_id === __enhance_run_id && __enhance_queue.length) {
          _kick_enhance_queue(seq)
        }
      }
    },
    { timeout: 800 }
  )
}

/* -----------------------
 * Scroll/observer
 * ----------------------- */

function isScrollableElement(el) {
  if (!el || el === document || el === window) return false
  const st = window.getComputedStyle(el)
  const oy = st.overflowY || st.overflow
  const isScrollStyle = oy === 'auto' || oy === 'scroll' || oy === 'overlay'
  if (!isScrollStyle) return false
  return el.scrollHeight > el.clientHeight + 2
}

function getScrollParent(startEl) {
  let el = startEl
  while (el && el !== document.body && el !== document.documentElement) {
    if (isScrollableElement(el)) return el
    el = el.parentElement
  }
  return null
}

function resolveScrollEl() {
  const w = wrapRef.value
  if (!w) return null
  if (isScrollableElement(w)) return w
  return getScrollParent(w) || null
}

function cleanupScrollListener() {
  try {
    if (scrollEl) scrollEl.removeEventListener('scroll', onScroll, { passive: true })
  } catch {}
  scrollEl = null
}

function setupScrollListener() {
  cleanupScrollListener()
  scrollEl = resolveScrollEl()
  if (scrollEl) {
    try {
      scrollEl.addEventListener('scroll', onScroll, { passive: true })
    } catch {}
  }
}

function cleanupObserver() {
  try {
    if (observer) observer.disconnect()
  } catch {}
  observer = null
}

function setupObserver(seq) {
  cleanupObserver()
  if (_is_stale(seq)) return
  if (!('IntersectionObserver' in window)) return
  if (!sentinelRef.value) return

  const rootEl = resolveScrollEl()
  observer = new IntersectionObserver(
    (entries) => {
      if (_is_stale(seq)) return
      if (!Array.isArray(entries)) return
      for (const entry of entries) {
        if (entry && entry.isIntersecting) {
          loadMore(props.stepChunks, seq)
          break
        }
      }
    },
    { root: rootEl || null, rootMargin: props.rootMargin, threshold: 0 }
  )

  observer.observe(sentinelRef.value)
}

function onScroll() {
  const el = scrollEl
  if (!el) return
  if (done.value || loading.value) return
  const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1200
  if (nearBottom) loadMore(props.stepChunks, __refreshSeq)
}

/* -----------------------
 * Loading chunks (time-sliced)
 * ----------------------- */

async function loadMore(count, seq) {
  if (_is_stale(seq)) return
  if (done.value) return

  if (loading.value) {
    const ok = await _wait_until_not_loading(seq, 1800)
    if (!ok || _is_stale(seq)) return
    if (done.value) return
  }

  if (!chunks.value.length) {
    done.value = true
    return
  }

  loading.value = true
  const newChunkIds = []

  const budget_ms = __is_firefox ? 8 : 12
  let slice_start = _now_ms()

  try {
    const start = nextIndex.value
    const end = Math.min(chunks.value.length, start + Math.max(1, Number(count || 1)))

    for (let idx = start; idx < end; idx++) {
      if (_is_stale(seq)) return

      renderedChunks.value.push({ id: idx, html: renderChunkToSafeHtml(chunks.value[idx], idx) })
      newChunkIds.push(idx)

      const now = _now_ms()
      if (now - slice_start > budget_ms) {
        await _yield_to_main()
        slice_start = _now_ms()
        if (_is_stale(seq)) return
      }
    }

    if (_is_stale(seq)) return

    nextIndex.value = end
    if (nextIndex.value >= chunks.value.length) done.value = true

    await nextTick()
    if (_is_stale(seq)) return

    emit('chunkRendered')
    _enqueue_enhance_chunks(newChunkIds, seq)
  } finally {
    loading.value = false
  }
}

async function loadUntil(targetChunkIndex, seq) {
  if (_is_stale(seq)) return
  if (!Number.isFinite(targetChunkIndex)) return
  const target = Math.max(0, Math.min(chunks.value.length - 1, targetChunkIndex))
  if (target < nextIndex.value) return

  while (!_is_stale(seq) && !done.value && nextIndex.value <= target) {
    const ok = await _wait_until_not_loading(seq, 1800)
    if (!ok || _is_stale(seq)) return

    const remain = target + 1 - nextIndex.value
    const step = Math.max(1, Math.min(remain, Math.max(1, Number(props.stepChunks || 2) * 6)))
    await loadMore(step, seq)
    await nextTick()
  }
}

function computeInitialLoadCount() {
  if (props.eager) return chunks.value.length
  const txt = _get_effective_content()
  const chars = txt.length

  const eagerByChars =
    Number.isFinite(props.autoEagerMaxChars) && props.autoEagerMaxChars > 0 && chars > 0 && chars <= props.autoEagerMaxChars

  let eagerByLines = false
  if (!eagerByChars && Number.isFinite(props.autoEagerMaxLines) && props.autoEagerMaxLines > 0) {
    let c = 1
    let i = 0
    while (c <= props.autoEagerMaxLines + 1) {
      const k = txt.indexOf('\n', i)
      if (k < 0) break
      c += 1
      i = k + 1
    }
    eagerByLines = c > 0 && c <= props.autoEagerMaxLines
  }

  if (eagerByLines || eagerByChars) return chunks.value.length
  return Math.min(chunks.value.length, Math.max(1, props.initialChunks))
}

function _scrollToEl(el) {
  const sc = resolveScrollEl()
  if (sc && typeof sc.getBoundingClientRect === 'function') {
    const rEl = el.getBoundingClientRect()
    const rSc = sc.getBoundingClientRect()
    const top = sc.scrollTop + (rEl.top - rSc.top) - 12
    try {
      sc.scrollTo({ top, behavior: 'smooth' })
    } catch {
      sc.scrollTop = top
    }
    return
  }
  if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

/* -----------------------
 * refresh coordination
 * ----------------------- */

let __refresh_promise = Promise.resolve()
let __refresh_resolve = null

async function refresh() {
  _maybe_clear_override_if_path_changed()

  const seq = ++__refreshSeq
  _reset_enhance_queue_for_seq(seq)

  let resolve = null
  __refresh_promise = new Promise((r) => {
    resolve = r
    __refresh_resolve = r
  })

  cleanupObserver()
  cleanupScrollListener()
  loading.value = true

  try {
    const md = _get_effective_content()
    const split_res = await _split_into_heading_chunks_with_anchor_key_async(md, props.chunkSize, seq)
    if (_is_stale(seq)) return
    if (!split_res) return

    chunks.value = split_res.out
    anchorToChunk.value = split_res.anchorMap
    headingMetaByChunk.value = split_res.headMeta

    renderedChunks.value = []
    nextIndex.value = 0
    done.value = false

    await nextTick()
    if (_is_stale(seq)) return

    setupScrollListener()
    setupObserver(seq)

    loading.value = false

    const n = computeInitialLoadCount()
    await loadMore(n, seq)
  } finally {
    if (_is_stale(seq)) loading.value = false
    try {
      if (resolve && __refresh_resolve === resolve) {
        __refresh_resolve = null
        resolve()
      }
    } catch {}
  }
}

async function _wait_refresh_done(seq, max_ms = 1500) {
  const p = __refresh_promise
  let done_ok = false
  try {
    await Promise.race([
      p.then(() => {
        done_ok = true
      }),
      new Promise((r) => setTimeout(r, max_ms))
    ])
  } catch {}
  if (_is_stale(seq)) return false
  return done_ok || !loading.value
}

/* -----------------------
 * jumpTo
 * ----------------------- */

let __jumpSeq = 0
async function jumpTo(arg1, arg2, arg3) {
  const seq = ++__jumpSeq
  let refresh_seq = __refreshSeq

  let anchor_key = ''
  let base_anchor = ''
  let occ = null
  let text = ''
  let highlight = true

  if (arg1 && typeof arg1 === 'object') {
    anchor_key = String(arg1.anchor_key || arg1.anchorKey || arg1.anchor || '').trim()
    base_anchor = String(arg1.anchor || arg1.base_anchor || '').trim()
    occ = arg1.occ === null || arg1.occ === undefined ? null : Number(arg1.occ)
    text = String(arg1.text || '').trim()
    highlight = typeof arg1.highlight === 'boolean' ? arg1.highlight : true
  } else {
    anchor_key = String(arg1 || '').trim()
    text = String(arg2 || '').trim()
    highlight = typeof arg3 === 'boolean' ? arg3 : true
  }

  if (anchor_key && anchor_key.includes('--') && !base_anchor) {
    const parts = anchor_key.split('--')
    const last = parts.pop()
    base_anchor = parts.join('--')
    const n = Number(last)
    occ = Number.isFinite(n) ? n : null
  }

  if (!anchor_key && base_anchor && Number.isFinite(occ) && occ >= 1) {
    anchor_key = `${base_anchor}--${occ}`
  }

  if (!anchor_key && !base_anchor && text) {
    base_anchor = _slugify(_clean_heading_text(text))
    anchor_key = base_anchor
  }

  if (!anchor_key && !base_anchor) return

  await _wait_refresh_done(refresh_seq, 1500)
  if (seq !== __jumpSeq) return
  if (_is_stale(refresh_seq)) return

  let idx = anchorToChunk.value?.[anchor_key]
  if (!Number.isFinite(idx) && base_anchor) idx = anchorToChunk.value?.[base_anchor]

  if (!Number.isFinite(idx)) {
    const upgraded = await _try_upgrade_to_full_content(refresh_seq)
    if (seq !== __jumpSeq) return
    if (upgraded) {
      refresh_seq = __refreshSeq
      await _wait_refresh_done(refresh_seq, 1500)
      if (seq !== __jumpSeq) return
      if (_is_stale(refresh_seq)) return
      idx = anchorToChunk.value?.[anchor_key]
      if (!Number.isFinite(idx) && base_anchor) idx = anchorToChunk.value?.[base_anchor]
    }
  }

  if (Number.isFinite(idx)) await loadUntil(idx, refresh_seq)
  else await loadMore(props.stepChunks, refresh_seq)

  const max_loops = Number.isFinite(idx) ? 90 : 160

  for (let i = 0; i < max_loops; i++) {
    if (seq !== __jumpSeq) return
    if (_is_stale(refresh_seq)) return

    await nextTick()
    if (_is_stale(refresh_seq)) return

    const root = wrapRef.value || document

    let el = null
    try {
      if (anchor_key) el = root.querySelector?.(`#heading-${CSS.escape(anchor_key)}`)
    } catch {}

    if (!el && anchor_key) {
      try {
        el = root.querySelector?.(`[data-heading-key="${anchor_key}"]`)
      } catch {}
    }

    if (!el && base_anchor) {
      try {
        const nodes = Array.from(
          root.querySelectorAll?.(
            `h1[data-heading-anchor="${base_anchor}"],h2[data-heading-anchor="${base_anchor}"],h3[data-heading-anchor="${base_anchor}"],h4[data-heading-anchor="${base_anchor}"],h5[data-heading-anchor="${base_anchor}"],h6[data-heading-anchor="${base_anchor}"]`
          ) || []
        )
        if (nodes.length) {
          const k = Number.isFinite(occ) && occ >= 1 ? occ - 1 : 0
          el = nodes[Math.min(nodes.length - 1, Math.max(0, k))] || null
        }
      } catch {}
    }

    if (el) {
      _scrollToEl(el)
      if (highlight) {
        el.classList.add('highlight-flash')
        setTimeout(() => el.classList.remove('highlight-flash'), 1500)
      }
      return
    }

    if (done.value) return

    const ok = await _wait_until_not_loading(refresh_seq, 1800)
    if (!ok || _is_stale(refresh_seq)) return
    await loadMore(props.stepChunks, refresh_seq)
  }
}

watch(
  () => props.content,
  async () => {
    _maybe_clear_override_if_path_changed()
    await refresh()
  },
  { immediate: true }
)

async function handle_nisb_audio_download_click(e) {
  const target = e?.target
  const btn = target && typeof target.closest === 'function'
    ? target.closest('[data-nisb-audio-b64], [data-nisb-audio-url]')
    : null
  if (!btn) return

  e.preventDefault()
  e.stopPropagation()

  const b64 = btn.getAttribute('data-nisb-audio-b64') || ''
  const remoteUrl = btn.getAttribute('data-nisb-audio-url') || ''
  const mime = btn.getAttribute('data-nisb-audio-mime') || 'audio/mpeg'
  const name = btn.getAttribute('data-nisb-audio-name') || 'audio.mp3'

  try {
    let blob = null

    if (b64) {
      const raw = atob(b64)
      const buf = new Uint8Array(raw.length)
      for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i)
      blob = new Blob([buf], { type: mime })
    } else if (remoteUrl) {
      btn.setAttribute('disabled', 'disabled')
      btn.classList.add('nisb-audio-download-busy')

      const res = await fetch(remoteUrl, {
        method: 'GET',
        mode: 'cors',
        credentials: 'omit',
      })
      if (!res.ok) throw new Error(`download_failed:${res.status}`)
      blob = await res.blob()
    }

    if (!blob) return

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()

    window.setTimeout(() => {
      URL.revokeObjectURL(url)
      a.remove()
    }, 1000)
  } catch (err) {
    console.warn('nisb audio download error', err)
    if (remoteUrl) {
      window.open(remoteUrl, '_blank', 'noopener,noreferrer')
    }
  } finally {
    try {
      btn.removeAttribute('disabled')
      btn.classList.remove('nisb-audio-download-busy')
    } catch {}
  }
}

onMounted(() => {
  _set_current_path(_read_path_from_storage())
  window.addEventListener('nisb-outline-context', _on_outline_context, true)

  const wEl = wrapRef.value
  if (wEl) {
    wEl.addEventListener('click', handle_nisb_audio_download_click, true)
  }

  setupScrollListener()
  setupObserver(__refreshSeq)
})

onUnmounted(() => {
  __alive = false
  window.removeEventListener('nisb-outline-context', _on_outline_context, true)

  const wEl = wrapRef.value
  if (wEl) {
    wEl.removeEventListener('click', handle_nisb_audio_download_click, true)
  }

  cleanupObserver()
  cleanupScrollListener()
  if (__enhance_idle_id !== null) {
    _cancel_idle(__enhance_idle_id)
    __enhance_idle_id = null
  }
})

defineExpose({ jumpTo })
</script>

<style scoped>
.display-mode-container {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  width: 100%;
  min-width: 0;
  min-height: 0;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
}

.preview-content {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  padding: clamp(1.25rem, 2.5vw, 2.35rem) clamp(1.25rem, 4vw, 3rem) 3rem;
  color: var(--text-main);
  line-height: var(--text-line-height);
  font-size: var(--editor-font-size);
  word-wrap: break-word;
  overflow-wrap: break-word;
  scrollbar-gutter: stable;
}

.lm-chunk {
  max-width: 100%;
  content-visibility: auto;
  contain-intrinsic-size: 800px 1200px;
}

.lm-chunk :deep(p) {
  margin: 0.65rem 0;
}

.lm-chunk :deep(a) {
  color: var(--selected);
  text-decoration-color: color-mix(in srgb, var(--selected) 38%, transparent);
  text-underline-offset: 0.18em;
}

.lm-chunk :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
  box-sizing: border-box;
  margin: 1rem 0;
  padding: 0.95rem 1rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  -webkit-overflow-scrolling: touch;
}

.lm-chunk :deep(pre > code) {
  display: block;
  white-space: pre;
}

.lm-chunk :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 15px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  box-shadow:
    0 16px 36px rgba(0, 0, 0, 0.12),
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
}

.lm-sentinel {
  height: 1px;
}

.lm-state {
  display: inline-flex;
  align-items: center;
  min-height: 25px;
  box-sizing: border-box;
  margin-top: 14px;
  padding: 0.35rem 0.62rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  font-size: 0.74rem;
  font-weight: 720;
  line-height: 1;
  color: var(--text-secondary);
  user-select: none;
}

.lm-loading {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  color: var(--selected);
}

.lm-done {
  opacity: 0.78;
}

.lm-chunk :deep(.nisb-audio-download-btn) {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-height: 2rem;
  margin: 0.45rem 0 0.35rem;
  padding: 0.34rem 0.72rem;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 999px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected) 8%, var(--editor-bg)),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: color-mix(in srgb, var(--selected) 82%, var(--text-main));
  font: inherit;
  font-size: 0.84em;
  font-weight: 720;
  line-height: 1;
  cursor: pointer;
  user-select: none;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 42%, transparent) inset,
    0 8px 20px color-mix(in srgb, var(--selected) 8%, transparent);
  transition:
    transform 0.14s ease,
    border-color 0.14s ease,
    background 0.14s ease,
    box-shadow 0.14s ease;
}

.lm-chunk :deep(.nisb-audio-download-btn:hover) {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected) 13%, var(--editor-bg)),
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 48%, transparent) inset,
    0 10px 24px color-mix(in srgb, var(--selected) 12%, transparent);
}

.lm-chunk :deep(.nisb-audio-download-btn:active) {
  transform: translateY(0);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 28%, transparent) inset,
    0 4px 12px color-mix(in srgb, var(--selected) 7%, transparent);
}

.lm-chunk :deep(.nisb-audio-download-icon) {
  display: inline-grid;
  place-items: center;
  width: 1.18rem;
  height: 1.18rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 13%, transparent);
  color: var(--selected);
  font-size: 0.78em;
  line-height: 1;
}

.lm-chunk :deep(.nisb-audio-download-size) {
  display: inline-flex;
  align-items: center;
  min-height: 1.12rem;
  padding: 0 0.38rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 9%, transparent);
  color: var(--text-secondary);
  font-size: 0.82em;
  font-weight: 680;
}

.lm-chunk :deep(.nisb-audio-download-btn.nisb-audio-download-busy),
.lm-chunk :deep(.nisb-audio-download-btn:disabled) {
  cursor: wait;
  opacity: 0.72;
  transform: none;
}

@media (max-width: 720px) {
  .preview-content {
    padding: 1rem 1rem 2.25rem;
  }
}
</style>

