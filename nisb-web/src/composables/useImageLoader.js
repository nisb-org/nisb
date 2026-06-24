// /opt/mcp-gateway/nisb-web/src/composables/useImageLoader.js
import { ref } from 'vue'
import { useMCP } from './useMCP'

export function useImageLoader() {
  const { callTool } = useMCP()

  const imageCache = ref(Object.create(null))
  const runId = ref(0)

  const __is_firefox = (() => {
    try {
      return /firefox/i.test(String(navigator.userAgent || ''))
    } catch {
      return false
    }
  })()

  const __placeholder_1x1 =
    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='

  // ---------- LRU cache (防止无限 data_url 占内存) ----------
  const __cache_order = []
  const __cache_max_entries = __is_firefox ? 48 : 96

  function clearCache() {
    imageCache.value = Object.create(null)
    __cache_order.length = 0
  }

  function _cache_get(key) {
    const k = String(key || '')
    if (!k) return ''
    return String(imageCache.value?.[k] || '')
  }

  function _cache_set(key, val) {
    const k = String(key || '')
    const v = String(val || '')
    if (!k || !v) return

    if (!imageCache.value[k]) __cache_order.push(k)
    imageCache.value[k] = v

    while (__cache_order.length > __cache_max_entries) {
      const drop = __cache_order.shift()
      if (!drop) break
      try {
        delete imageCache.value[drop]
      } catch {}
    }
  }

  // ---------- global queue (关键：避免创建海量 pending promise) ----------
  const __q = []
  const __q_set = new WeakSet()
  let __active = 0
  let __pump_scheduled = false
  const __max_concurrency = __is_firefox ? 2 : 4
  const __max_queue = __is_firefox ? 120 : 240

  const __inflight_by_src = new Map()

  function _yield_to_main() {
    return new Promise((r) => setTimeout(r, 0))
  }

  function _normalize_src(s) {
    return String(s || '').trim()
  }

  function _needs_tool_load(rawSrc) {
    const s = _normalize_src(rawSrc)
    if (!s) return false
    if (s.startsWith('http') || s.startsWith('data:') || s.startsWith('/')) return false
    return true
  }

  function parseNisbFilePath(src) {
    const h = _normalize_src(src)
    if (!/^nisb:\/\//i.test(h)) return ''
    try {
      const u = new URL(h)
      if (String(u.host || '').toLowerCase() !== 'file') return ''
      const qp = u.searchParams.get('path')
      if (qp) return String(qp || '').replace(/^\/+/, '')
      const p = String(u.pathname || '').replace(/^\/+/, '')
      return p
    } catch {
      return ''
    }
  }

  function openLightboxCompat(onOpenLightbox, src, alt) {
    if (typeof onOpenLightbox === 'function') {
      try {
        if (onOpenLightbox.length >= 2) onOpenLightbox(src, alt || '')
        else onOpenLightbox({ src, alt: alt || '' })
        return
      } catch {}
    }
    window.dispatchEvent(new CustomEvent('nisb-open-lightbox', { detail: { src, alt: alt || '' } }))
  }

  function bindLightboxIfNeeded(imgEl, src, alt, onOpenLightbox) {
    if (!imgEl) return
    if (imgEl.dataset.nisbLightboxBound === '1') return
    imgEl.dataset.nisbLightboxBound = '1'

    imgEl.style.cursor = 'zoom-in'
    imgEl.addEventListener('click', (ev) => {
      ev.preventDefault()
      ev.stopPropagation()
      openLightboxCompat(onOpenLightbox, src, alt)
    })
  }

  function addCopyButtons(rootEl) {
    const codeBlocks = rootEl.querySelectorAll('pre code')
    codeBlocks.forEach((codeBlock) => {
      const pre = codeBlock.parentElement
      if (!pre) return
      if (pre.dataset.nisbCopyBound === '1') return
      pre.dataset.nisbCopyBound = '1'
      if (pre.querySelector('.copy-btn')) return

      const btn = document.createElement('button')
      btn.className = 'copy-btn'
      btn.type = 'button'
      btn.textContent = '复制'

      btn.addEventListener('click', () => {
        const code = codeBlock.textContent || ''
        navigator.clipboard
          .writeText(code)
          .then(() => {
            const old = btn.textContent
            btn.textContent = '已复制'
            setTimeout(() => (btn.textContent = old), 1200)
          })
          .catch(() => {
            const old = btn.textContent
            btn.textContent = '重试'
            setTimeout(() => (btn.textContent = old), 1200)
          })
      })

      pre.style.position = 'relative'
      pre.appendChild(btn)
    })
  }

  function enhanceLinks(rootEl) {
    const links = rootEl.querySelectorAll('a[href]')
    links.forEach((a) => {
      if (a.dataset.nisbLinkBound === '1') return
      a.dataset.nisbLinkBound = '1'

      const href = _normalize_src(a.getAttribute('href') || '')
      if (!href) return

      if (/^https?:\/\//i.test(href)) {
        a.setAttribute('target', '_blank')
        a.setAttribute('rel', 'noopener noreferrer')
        if (!a.getAttribute('title')) a.setAttribute('title', href)
      }
    })
  }

  async function _fetch_data_url_for_src(rawSrc, myRun) {
    const key = _normalize_src(rawSrc)
    if (!key) return ''

    const cached = _cache_get(key)
    if (cached) return cached

    if (__inflight_by_src.has(key)) {
      try {
        const v = await __inflight_by_src.get(key)
        return String(v || '')
      } catch {
        return ''
      }
    }

    const p = (async () => {
      if (myRun !== runId.value) return ''

      // nisb://file -> nisb_feed_user_file_base64
      if (/^nisb:\/\//i.test(key)) {
        const rel = parseNisbFilePath(key)
        if (!rel) return ''
        let result = null
        try {
          result = await callTool('nisb_feed_user_file_base64', { path: rel })
        } catch {
          return ''
        }
        if (myRun !== runId.value) return ''
        if (result?.success && result?.data_url) return String(result.data_url || '')
        return ''
      }

      // 相对路径 -> nisb_file_read
      let result = null
      try {
        result = await callTool('nisb_file_read', { filename: key })
      } catch {
        return ''
      }
      if (myRun !== runId.value) return ''
      if (result?.success && result?.metadata?.type === 'image' && result?.content) {
        const mime = String(result?.metadata?.mime_type || 'image/png')
        return `data:${mime};base64,${String(result.content)}`
      }
      return ''
    })()

    __inflight_by_src.set(key, p)

    try {
      const dataUrl = await p
      if (myRun !== runId.value) return ''
      if (dataUrl) _cache_set(key, dataUrl)
      return String(dataUrl || '')
    } finally {
      __inflight_by_src.delete(key)
    }
  }

  async function _load_one(img, rawSrc, myRun, onOpenLightbox) {
    if (myRun !== runId.value) return
    if (!img) return

    const s = _normalize_src(rawSrc)
    if (!s) return

    // 浏览器直连
    if (s.startsWith('http') || s.startsWith('data:') || s.startsWith('/')) {
      bindLightboxIfNeeded(img, s, img.alt, onOpenLightbox)
      img.style.opacity = '1'
      return
    }

    img.alt = img.alt || '加载中'
    img.style.opacity = '0.6'

    const dataUrl = await _fetch_data_url_for_src(s, myRun)
    if (myRun !== runId.value) return

    if (dataUrl) {
      try {
        img.setAttribute('src', dataUrl)
      } catch {
        img.src = dataUrl
      }
      img.style.opacity = '1'
      img.alt = img.alt || s.split('/').pop() || 'image'
      bindLightboxIfNeeded(img, dataUrl, img.alt, onOpenLightbox)
    } else {
      img.alt = '图片加载失败'
      img.style.opacity = '1'
    }
  }

  function _schedule_pump() {
    if (__pump_scheduled) return
    __pump_scheduled = true
    setTimeout(_pump, 0)
  }

  async function _pump() {
    __pump_scheduled = false

    // 让出主线程：避免一口气跑太久
    await _yield_to_main()

    while (__active < __max_concurrency && __q.length) {
      const task = __q.shift()
      if (!task) break

      const { img, rawSrc, myRun, onOpenLightbox } = task

      // stale / DOM 已被替换
      if (myRun !== runId.value) continue
      if (!img || !img.isConnected) continue

      __active += 1
      ;(async () => {
        try {
          await _load_one(img, rawSrc, myRun, onOpenLightbox)
        } finally {
          __active -= 1
          if (__q.length) _schedule_pump()
        }
      })()
    }

    if (__q.length && __active === 0) {
      // 防止极端情况下队列卡住
      _schedule_pump()
    }
  }

  function _enqueue_img(img, rawSrc, myRun, onOpenLightbox) {
    if (!img) return
    if (myRun !== runId.value) return

    if (__q_set.has(img)) return
    __q_set.add(img)

    if (__q.length >= __max_queue) return

    __q.push({ img, rawSrc, myRun, onOpenLightbox })
    _schedule_pump()
  }

  function _prepare_lazy_img(img, rawSrc) {
    if (!img) return
    if (img.dataset.nisbLazyPrepared === '1') return
    img.dataset.nisbLazyPrepared = '1'
    img.dataset.nisbRawSrc = _normalize_src(rawSrc)

    try {
      img.setAttribute('src', __placeholder_1x1)
    } catch {}

    img.decoding = img.decoding || 'async'
    img.loading = img.loading || 'lazy'
    img.style.opacity = img.style.opacity || '0.65'
  }

  function _get_or_create_observer(rootEl, myRun, onOpenLightbox) {
    if (rootEl.__nisb_img_observer && rootEl.__nisb_img_observer_run === myRun) return rootEl.__nisb_img_observer

    try {
      if (rootEl.__nisb_img_observer) rootEl.__nisb_img_observer.disconnect()
    } catch {}

    const rootMargin = __is_firefox ? '700px 0px 700px 0px' : '1200px 0px 1200px 0px'

    const obs = new IntersectionObserver(
      (entries) => {
        if (myRun !== runId.value) return
        for (const ent of entries || []) {
          if (!ent || !ent.isIntersecting) continue
          const img = ent.target
          if (!img) continue

          try {
            obs.unobserve(img)
          } catch {}

          const rawSrc = _normalize_src(img?.dataset?.nisbRawSrc || '')
          if (!rawSrc) continue

          _enqueue_img(img, rawSrc, myRun, onOpenLightbox)
        }
      },
      { root: null, rootMargin, threshold: 0 }
    )

    rootEl.__nisb_img_observer = obs
    rootEl.__nisb_img_observer_run = myRun
    return obs
  }

  async function enhanceMarkdownDom(opts) {
    const rootEl = opts?.rootEl || null
    const onOpenLightbox = typeof opts?.onOpenLightbox === 'function' ? opts.onOpenLightbox : null
    if (!rootEl) return

    // ✅ 让出一帧，避免与首屏渲染硬抢主线程
    await new Promise((resolve) => setTimeout(resolve, 0))

    const external_run = opts?.run_id
    if (Number.isFinite(Number(external_run)) && Number(external_run) > 0) {
      runId.value = Number(external_run)
    } else {
      runId.value += 1
    }
    const myRun = runId.value

    // 新一轮：直接清空队列占用（旧轮任务会因 run_id 失效自然退出）
    __q.length = 0
    __q_set.clear?.()
    // WeakSet 没有 clear，这里不做；旧 img 节点被替换后会自然释放引用

    addCopyButtons(rootEl)
    enhanceLinks(rootEl)

    const images = Array.from(rootEl.querySelectorAll('img') || [])
    if (!images.length) return

    const eager_images =
      Number.isFinite(Number(opts?.eager_images)) && Number(opts.eager_images) >= 0
        ? Number(opts.eager_images)
        : __is_firefox
          ? 2
          : 6

    const obs = _get_or_create_observer(rootEl, myRun, onOpenLightbox)

    let eager_done = 0

    for (const img of images) {
      if (myRun !== runId.value) return
      if (!img) continue

      const rawSrc = _normalize_src(img.getAttribute('src') || '')
      if (!rawSrc) continue

      if (!_needs_tool_load(rawSrc)) {
        bindLightboxIfNeeded(img, rawSrc, img.alt, onOpenLightbox)
        img.style.opacity = '1'
        continue
      }

      _prepare_lazy_img(img, rawSrc)

      if (eager_done < eager_images) {
        eager_done += 1
        _enqueue_img(img, rawSrc, myRun, onOpenLightbox)
      } else {
        try {
          obs.observe(img)
        } catch {}
      }
    }

    _schedule_pump()
  }

  return {
    imageCache,
    enhanceMarkdownDom,
    clearCache
  }
}

