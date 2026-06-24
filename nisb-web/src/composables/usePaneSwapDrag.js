// /opt/mcp-gateway/nisb-web/src/composables/usePaneSwapDrag.js
import { ref } from 'vue'

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n))
}

/**
 * 统一拖拽语义：edgeWidth = “屏幕最右侧那块区域”的宽度
 * - rightAsMain=false（经典）：edge pane = RightSidebar（QA 在右侧）
 * - rightAsMain=true（互换）：edge pane = Editor（笔记区在右侧）
 *
 * 手感永远一致：
 * - 向左拖 => edgeWidth 增加（右侧区域变宽）
 * - 向右拖 => edgeWidth 减少（右侧区域变窄/可到 0 隐藏）
 *
 * ✅ 互换触发规则（终极一致手感）：
 * - 只在 MAX 端越界（继续向左推超过阈值）触发 toggleSwap
 * - MIN 端永远不触发 swap（只允许缩小/隐藏）
 */
export function usePaneSwapDrag(opts = {}) {
  const keySwap = opts.storageKeySwap || 'nisb_layout_rightAsMain'
  const keyWidth = opts.storageKeyWidth || 'nisb_rightWidth'

  const rightAsMain = ref(localStorage.getItem(keySwap) === '1')

  const minWidth = Number.isFinite(opts.minWidth) ? opts.minWidth : 0
  const maxRatio = Number.isFinite(opts.maxRatio) ? opts.maxRatio : 0.6

  const resistanceZonePx = Number.isFinite(opts.resistanceZonePx) ? opts.resistanceZonePx : 60
  const resistanceFactor = Number.isFinite(opts.resistanceFactor) ? opts.resistanceFactor : 0.22
  const swapThresholdPx = Number.isFinite(opts.swapThresholdPx) ? opts.swapThresholdPx : 56

  const mainWidthRatio = Number.isFinite(opts.mainWidthRatio) ? opts.mainWidthRatio : 0.62
  const secondaryMinPx = Number.isFinite(opts.secondaryMinPx) ? opts.secondaryMinPx : 260
  const secondaryCapPx = Number.isFinite(opts.secondaryCapPx) ? opts.secondaryCapPx : 520

  function getMaxWidth() {
    return window.innerWidth * maxRatio
  }

  function getDefaultEdgeWidth(nextRightAsMain) {
    const maxW = getMaxWidth()

    if (!nextRightAsMain) return clamp(280, minWidth, maxW)

    const secondary = Math.min(window.innerWidth * (1 - mainWidthRatio), secondaryCapPx)
    return clamp(Math.max(secondary, secondaryMinPx), minWidth, maxW)
  }

  function persistSwap() {
    localStorage.setItem(keySwap, rightAsMain.value ? '1' : '0')
  }

  function persistWidth(w) {
    localStorage.setItem(keyWidth, String(w))
  }

  function setRightAsMain(val) {
    rightAsMain.value = !!val
    persistSwap()
  }

  const saved = localStorage.getItem(keyWidth)
  const initialWidth = saved
    ? parseInt(saved, 10)
    : Number.isFinite(opts.initialEdgeWidth)
    ? opts.initialEdgeWidth
    : 280

  const edgeWidth = ref(clamp(initialWidth, minWidth, getMaxWidth()))

  let dragging = false
  let startX = 0
  let startEdgeWidth = 0

  function begin(clientX) {
    dragging = true
    startX = clientX
    startEdgeWidth = edgeWidth.value
  }

  function end() {
    dragging = false
    persistWidth(edgeWidth.value)
  }

  function syncWidth(nextWidth) {
    const w = clamp(Number(nextWidth) || 0, minWidth, getMaxWidth())
    edgeWidth.value = w
    if (dragging) {
      startEdgeWidth = w
      startX = startX
    }
    persistWidth(w)
  }

  function toggleSwap() {
    const next = !rightAsMain.value
    setRightAsMain(next)
    const w = getDefaultEdgeWidth(next)
    edgeWidth.value = w
    persistWidth(w)
  }

  /**
   * @param {number} clientX
   * @returns {{ width:number, swapped:boolean }}
   */
  function update(clientX) {
    if (!dragging) return { width: edgeWidth.value, swapped: false }

    const deltaX = clientX - startX
    const maxW = getMaxWidth()

    // 统一公式：向左拖 => 宽度增加；向右拖 => 宽度减少
    const raw = startEdgeWidth - deltaX

    // ✅ 只允许 MAX 端越界触发 swap（保证“向右拖永远缩小/隐藏”）
    if (raw > maxW + swapThresholdPx) {
      toggleSwap()
      startX = clientX
      startEdgeWidth = edgeWidth.value
      return { width: edgeWidth.value, swapped: true }
    }

    // clamp 到 [min, max]
    const clamped = clamp(raw, minWidth, maxW)

    // 阻尼：仅在 MAX 端越界时需要“顶到头还可推”的手感
    // MIN 端不做越界阻尼（让它干脆地缩到 0 隐藏）
    const distToMax = maxW - clamped
    const isTryingPastMax = raw > clamped
    if (isTryingPastMax && distToMax < resistanceZonePx) {
      const extra = raw - clamped
      const damped = clamped + extra * resistanceFactor
      edgeWidth.value = clamp(damped, minWidth, maxW)
      return { width: edgeWidth.value, swapped: false }
    }

    edgeWidth.value = clamped
    return { width: edgeWidth.value, swapped: false }
  }

  function getOpenWidthForCurrentMode() {
    return getDefaultEdgeWidth(rightAsMain.value)
  }

  return {
    rightAsMain,
    edgeWidth,
    begin,
    update,
    end,
    syncWidth,
    setRightAsMain,
    getOpenWidthForCurrentMode
  }
}

