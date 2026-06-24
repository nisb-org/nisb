// /opt/mcp-gateway/nisb-web/src/composables/useHoverScroll.js
import { ref, onMounted, onUnmounted } from 'vue'

export function useHoverScroll(scrollElRef, options = {}) {
  const activeHeight = options.activeHeight ?? 10
  const ignorePredicate = typeof options.ignorePredicate === 'function' ? options.ignorePredicate : null
  const resetOnLeave = options.resetOnLeave ?? true

  // 可选：调小可减少 scrollLeft 写入频率（像素级抖动）
  const scrollEpsilon = Number.isFinite(options.scrollEpsilon) ? Number(options.scrollEpsilon) : 0.5

  const rowHover = ref(false)
  const hasOverflow = ref(false)

  let enterScrollLeft = 0

  // 缓存，避免每次 mousemove 都触发布局读取
  let cachedRect = null
  let cachedRectAt = 0
  let cachedMaxScroll = 0

  // rAF 合并：recompute / mousemove / scroll 都只在每帧执行一次
  function rafThrottle(fn) {
    let rafId = 0
    let lastArgs = null

    const wrapped = (...args) => {
      lastArgs = args
      if (rafId) return
      rafId = window.requestAnimationFrame(() => {
        rafId = 0
        const a = lastArgs
        lastArgs = null
        fn(...(a || []))
      })
    }

    wrapped._cancel = () => {
      if (rafId) window.cancelAnimationFrame(rafId)
      rafId = 0
      lastArgs = null
    }

    return wrapped
  }

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v))
  }

  function updateMetrics() {
    const el = scrollElRef.value
    if (!el) {
      hasOverflow.value = false
      cachedRect = null
      cachedMaxScroll = 0
      return
    }

    // 读：只在合并后的 rAF 中做
    const sw = el.scrollWidth || 0
    const cw = el.clientWidth || 0
    const overflow = sw > cw + 2
    hasOverflow.value = overflow
    cachedMaxScroll = Math.max(0, sw - cw)

    // rect 也只在合并后的 rAF 中读一次
    cachedRect = el.getBoundingClientRect()
    cachedRectAt = performance.now()

    // 写：必要时复位，避免残留 scrollLeft
    if (!overflow && el.scrollLeft !== 0) el.scrollLeft = 0
  }

  const recompute = rafThrottle(updateMetrics)

  function onRowEnter(e) {
    if (ignorePredicate && ignorePredicate(e)) return
    const el = scrollElRef.value
    rowHover.value = true
    enterScrollLeft = el ? el.scrollLeft : 0
    recompute()
  }

  function onRowLeave() {
    rowHover.value = false
    const el = scrollElRef.value
    if (el && resetOnLeave) {
      el.scrollLeft = enterScrollLeft || 0
    }
    recompute()
  }

  function onScroll() {
    // scroll 事件可能非常频繁：只触发合并后的 recompute
    recompute()
  }

  function shouldUseBottomActiveZone(e, rect) {
    // 原逻辑：只在元素底部 activeHeight 区域响应
    return !(e.clientY < rect.bottom - activeHeight || e.clientY > rect.bottom)
  }

  function onMouseMoveImpl(e) {
    if (ignorePredicate && ignorePredicate(e)) return

    const el = scrollElRef.value
    if (!el || !rowHover.value || !hasOverflow.value) return

    // rect 可能因布局变化而失效：超过 300ms 或丢失时刷新一次（仍在 rAF 内）
    if (!cachedRect || performance.now() - cachedRectAt > 300) {
      cachedRect = el.getBoundingClientRect()
      cachedRectAt = performance.now()
      // cachedMaxScroll 可能也变了，顺便刷新（读）
      const sw = el.scrollWidth || 0
      const cw = el.clientWidth || 0
      cachedMaxScroll = Math.max(0, sw - cw)
      hasOverflow.value = sw > cw + 2
      if (!hasOverflow.value) return
    }

    const rect = cachedRect
    if (!rect || !rect.width) return
    if (!shouldUseBottomActiveZone(e, rect)) return

    const ratio = clamp((e.clientX - rect.left) / rect.width, 0, 1)
    const target = cachedMaxScroll * ratio

    // 写入前做个 epsilon 判断，减少 scrollLeft 抖动与 scroll 事件风暴
    if (Math.abs((el.scrollLeft || 0) - target) >= scrollEpsilon) {
      el.scrollLeft = target
    }
  }

  const onMouseMove = rafThrottle(onMouseMoveImpl)

  onMounted(() => {
    window.addEventListener('resize', recompute, { passive: true })
    recompute()
  })

  onUnmounted(() => {
    window.removeEventListener('resize', recompute)
    try {
      recompute._cancel?.()
    } catch {}
    try {
      onMouseMove._cancel?.()
    } catch {}
    cachedRect = null
  })

  return {
    hasOverflow,
    onRowEnter,
    onRowLeave,
    onScroll,
    onMouseMove
  }
}

