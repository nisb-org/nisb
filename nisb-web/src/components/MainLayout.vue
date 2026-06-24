<template>
  <div
    ref="layoutRef"
    class="layout-container"
    :class="{
      'right-as-main': rightAsMain,
      'lights-off': lightsOff,
      'reading-opt-on': readingEnabled
    }"
  >
    <div class="left-sidebar" :class="{ collapsed: leftWidth === 0 }" :style="{ width: leftWidth + 'px' }">
      <LeftSidebar v-if="leftWidth > 0" />
    </div>

    <div v-if="leftWidth > 0" class="handle left-handle" @pointerdown="startDragLeft" title=""></div>
    <div v-if="leftWidth > 0" class="divider left-divider" @pointerdown="startDragLeft"></div>

    <div
      class="editor-area"
      :class="{
        'pane-main': !rightAsMain,
        'pane-secondary': rightAsMain,
        'edge-collapsed': rightAsMain && edgeWidthLocal === 0
      }"
      :style="editorAreaStyle"
    >
      <Editor />
    </div>

    <div
      v-if="edgeWidthLocal > 0"
      class="divider right-divider"
      @pointerdown="startDragRight"
      :title="rightAsMain ? 'QA' : ''"
    ></div>

    <div v-else class="handle right-handle" @pointerdown="startDragRight" :title="rightAsMain ? 'QA' : ''"></div>

    <div
      class="right-sidebar"
      :class="{
        'pane-main': rightAsMain,
        'pane-secondary': !rightAsMain,
        collapsed: !rightAsMain && edgeWidthLocal === 0
      }"
      :style="rightSidebarStyle"
    >
      <RightSidebar v-if="rightSidebarVisible" />
    </div>

    <ToastHost />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import LeftSidebar from './LeftSidebar.vue'
import Editor from './Editor.vue'
import RightSidebar from './RightSidebar.vue'
import ToastHost from './ToastHost.vue'
import { usePaneSwapDrag } from '../composables/usePaneSwapDrag'
import { useReadingOptimizer } from '../composables/useReadingOptimizer'
import useMCP from '../composables/useMCP'

const { callTool } = useMCP()

const layoutRef = ref(null)
const leftWidth = ref(280)

const MOBILE_BP_PX = 768
const MOBILE_MAX_RATIO = 0.78
const DEFAULT_LEFT_WIDTH = 280

function _isMobileWidth() {
  return window.innerWidth <= MOBILE_BP_PX
}

function _isMobilePortrait() {
  try {
    if (window.matchMedia) {
      return window.matchMedia(`(max-width: ${MOBILE_BP_PX}px) and (orientation: portrait)`).matches
    }
  } catch {}

  try {
    return window.innerWidth <= MOBILE_BP_PX && window.innerHeight >= window.innerWidth
  } catch {}

  return false
}

function _edgeMaxRatio() {
  return _isMobileWidth() ? MOBILE_MAX_RATIO : 0.6
}

function _rightOpenMinPx() {
  return _isMobileWidth() ? 280 : 260
}

function _safeReadStorage(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function _safeWriteStorage(key, value) {
  try {
    localStorage.setItem(key, String(value))
  } catch {}
}

function _safeRestoreStorage(key, previousValue) {
  try {
    if (previousValue === null || typeof previousValue === 'undefined') localStorage.removeItem(key)
    else localStorage.setItem(key, String(previousValue))
  } catch {}
}

function _parseWidth(raw) {
  const n = parseInt(String(raw || ''), 10)
  return Number.isFinite(n) ? n : null
}

function _clampEdgeWidth(width) {
  const n = Number(width)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(n, window.innerWidth * _edgeMaxRatio()))
}

function _clampLeftWidth(width) {
  const n = Number(width)
  if (!Number.isFinite(n)) return DEFAULT_LEFT_WIDTH
  return Math.max(0, Math.min(n, window.innerWidth * _edgeMaxRatio()))
}

const {
  rightAsMain,
  edgeWidth,
  begin: beginEdgeDrag,
  update: updateEdgeDrag,
  end: endEdgeDrag,
  syncWidth,
  getOpenWidthForCurrentMode
} = usePaneSwapDrag({
  storageKeySwap: 'nisb_layout_rightAsMain',
  storageKeyWidth: 'nisb_rightWidth',
  minWidth: 0,
  maxRatio: _edgeMaxRatio(),
  resistanceZonePx: 60,
  resistanceFactor: 0.22,
  swapThresholdPx: 56,
  mainWidthRatio: 0.62,
  secondaryMinPx: _rightOpenMinPx(),
  secondaryCapPx: 520
})

const edgeWidthLocal = computed(() => edgeWidth.value)

let activeDrag = null
let startX = 0
let startLeftWidth = 0
let dragEl = null
let activePointerId = null
let mobilePortraitInitialLayoutApplied = false

function emit_toast(message, type = 'info', duration = 2500) {
  const msg = String(message || '')
  if (!msg) return
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message: msg, type, duration } }))
}

function syncWidthWithoutPersist(nextWidth) {
  const prev = _safeReadStorage('nisb_rightWidth')
  syncWidth(_clampEdgeWidth(nextWidth))
  _safeRestoreStorage('nisb_rightWidth', prev)
}

function setRightAsMainWithoutPersist(nextValue) {
  const prev = _safeReadStorage('nisb_layout_rightAsMain')
  rightAsMain.value = !!nextValue
  _safeRestoreStorage('nisb_layout_rightAsMain', prev)
}

function applyMobilePortraitInitialLayout() {
  if (mobilePortraitInitialLayoutApplied) return false
  if (!_isMobilePortrait()) return false

  mobilePortraitInitialLayoutApplied = true
  leftWidth.value = 0
  setRightAsMainWithoutPersist(false)
  syncWidthWithoutPersist(0)
  return true
}

function startDragLeft(e) {
  activeDrag = 'left'
  startX = e.clientX
  startLeftWidth = leftWidth.value

  dragEl = e.currentTarget
  activePointerId = e.pointerId

  try {
    if (dragEl && activePointerId != null) dragEl.setPointerCapture(activePointerId)
  } catch {}

  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function startDragRight(e) {
  activeDrag = 'right'
  beginEdgeDrag(e.clientX)

  dragEl = e.currentTarget
  activePointerId = e.pointerId

  try {
    if (dragEl && activePointerId != null) dragEl.setPointerCapture(activePointerId)
  } catch {}

  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function handleMouseMove(e) {
  if (!activeDrag) return

  if (typeof e.buttons === 'number' && e.buttons === 0) {
    handleMouseUp()
    return
  }

  if (activeDrag === 'left') {
    const deltaX = e.clientX - startX
    const newWidth = startLeftWidth + deltaX
    leftWidth.value = _clampLeftWidth(newWidth)
    return
  }

  if (activeDrag === 'right') {
    const swapped = updateEdgeDrag(e.clientX)
    if (swapped && rightAsMain.value) emit_toast('QA', 'success', 1200)
  }
}

function broadcastSidebarState() {
  window.dispatchEvent(
    new CustomEvent('sidebar-state-changed', {
      detail: { left: leftWidth.value, right: edgeWidth.value }
    })
  )
}

function handleMouseUp() {
  if (activeDrag === 'left') {
    _safeWriteStorage('nisb_leftWidth', leftWidth.value)
  } else if (activeDrag === 'right') {
    endEdgeDrag()
    _safeWriteStorage('nisb_rightWidth', edgeWidth.value)
  }

  try {
    if (dragEl && activePointerId != null) dragEl.releasePointerCapture(activePointerId)
  } catch {}

  dragEl = null
  activePointerId = null

  broadcastSidebarState()
  activeDrag = null
  document.body.style.cursor = 'default'
  document.body.style.userSelect = 'auto'
}

function handlePointerCancel() {
  handleMouseUp()
}

function handleToggleLeft() {
  leftWidth.value = leftWidth.value > 0 ? 0 : DEFAULT_LEFT_WIDTH
  _safeWriteStorage('nisb_leftWidth', leftWidth.value)
  broadcastSidebarState()
}

function handleToggleRight() {
  const maxW = window.innerWidth * _edgeMaxRatio()
  const desired = Math.max(getOpenWidthForCurrentMode(), _rightOpenMinPx())
  const next = edgeWidth.value === 0 ? Math.min(desired, maxW) : 0
  syncWidth(next)
  broadcastSidebarState()
}

function handlePaneSwapToggle() {
  const next = !rightAsMain.value
  rightAsMain.value = next

  try {
    localStorage.setItem('nisb_layout_rightAsMain', next ? '1' : '0')
  } catch {}

  const maxW = window.innerWidth * _edgeMaxRatio()
  syncWidth(Math.max(0, Math.min(edgeWidth.value, maxW)))

  broadcastSidebarState()
}

const editorAreaStyle = computed(() => {
  if (!rightAsMain.value) return {}
  return { width: edgeWidthLocal.value + 'px' }
})

const rightSidebarStyle = computed(() => {
  if (!rightAsMain.value) return { width: edgeWidthLocal.value + 'px' }
  return {}
})

const rightSidebarVisible = computed(() => {
  if (!rightAsMain.value) return edgeWidthLocal.value > 0
  return true
})

const lightsOff = ref(false)
const LIGHTSKEY = 'nisb_lights_off'

function setLightsOff(next) {
  const v = !!next
  lightsOff.value = v
  _safeWriteStorage(LIGHTSKEY, v ? '1' : '0')
  window.dispatchEvent(new CustomEvent('nisb-lights-changed', { detail: { off: v } }))
}

function handleToggleLights() {
  setLightsOff(!lightsOff.value)
}

function handleSetLights(e) {
  const off = !!(e?.detail && Object.prototype.hasOwnProperty.call(e.detail, 'off') ? e.detail.off : false)
  setLightsOff(off)
}

const reading = useReadingOptimizer(layoutRef)
const readingEnabled = computed(() => reading.enabled.value)

function handleReadingStateEvent(e) {
  const enabled = !!e?.detail?.enabled
  if (enabled) setLightsOff(false)
}

async function applyServerDefaultPresetOnBoot() {
  try {
    const res = await callTool('nisb_readopt_get_default_preset', {})
    const hasDefault = !!(res && (res.hasdefault === true || res.has_default === true || res.hasDefault === true))
    const prefs = res?.preset?.prefs ? res.preset.prefs : null
    if (hasDefault && prefs) {
      reading.setPrefs(prefs)
      return
    }
  } catch {}

  reading.reset()
}

onMounted(async () => {
  const savedLeft = _parseWidth(_safeReadStorage('nisb_leftWidth'))
  if (savedLeft !== null) leftWidth.value = _clampLeftWidth(savedLeft)

  const savedEdge = _parseWidth(_safeReadStorage('nisb_rightWidth'))
  if (savedEdge !== null) syncWidth(_clampEdgeWidth(savedEdge))

  const savedLights = _safeReadStorage(LIGHTSKEY)
  lightsOff.value = savedLights === '1'

  applyMobilePortraitInitialLayout()

  document.addEventListener('pointermove', handleMouseMove)
  document.addEventListener('pointerup', handleMouseUp)
  document.addEventListener('pointercancel', handlePointerCancel)

  window.addEventListener('toggle-left-sidebar', handleToggleLeft)
  window.addEventListener('toggle-right-sidebar', handleToggleRight)

  window.addEventListener('nisb_pane_swap_toggle', handlePaneSwapToggle)

  window.addEventListener('nisb-toggle-lights', handleToggleLights)
  window.addEventListener('nisb-set-lights', handleSetLights)
  window.addEventListener('nisb-reading-state', handleReadingStateEvent)

  reading.mount()
  await applyServerDefaultPresetOnBoot()
  setTimeout(broadcastSidebarState, 100)
})

onUnmounted(() => {
  document.removeEventListener('pointermove', handleMouseMove)
  document.removeEventListener('pointerup', handleMouseUp)
  document.removeEventListener('pointercancel', handlePointerCancel)

  window.removeEventListener('toggle-left-sidebar', handleToggleLeft)
  window.removeEventListener('toggle-right-sidebar', handleToggleRight)
  window.removeEventListener('nisb_pane_swap_toggle', handlePaneSwapToggle)

  window.removeEventListener('nisb-toggle-lights', handleToggleLights)
  window.removeEventListener('nisb-set-lights', handleSetLights)
  window.removeEventListener('nisb-reading-state', handleReadingStateEvent)

  reading.unmount()
})
</script>

<style scoped>
.layout-container {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--editor-bg);
}

.layout-container.reading-opt-on {
  --nisb-read-text-opacity: 1;
  --nisb-read-font-size: 16px;
  --nisb-read-line-height: 1.6;
  --nisb-read-padding: 0px;
  --nisb-read-warm-alpha: 0;
  --nisb-read-scroll-behavior: auto;
}

.left-sidebar {
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--sidebar-bg);
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: 1px solid var(--line);
  box-shadow: none;
  position: relative;
}

.left-sidebar.collapsed {
  width: 0 !important;
  overflow: hidden;
  border-right: none;
  box-shadow: none;
}

.divider {
  width: 0;
  height: 100%;
  cursor: col-resize;
  flex-shrink: 0;
  user-select: none;
  z-index: 10;
  background: transparent;
  position: relative;
}

.divider::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -4px;
  right: -4px;
  background: transparent;
  cursor: col-resize;
  pointer-events: auto;
}

.handle {
  width: 0;
  height: 100%;
  cursor: col-resize;
  flex-shrink: 0;
  background: transparent;
  user-select: none;
  z-index: 100;
  position: relative;
  transition: none;
  pointer-events: all;
}

.handle::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 14px;
  background: transparent;
  pointer-events: auto;
  cursor: col-resize;
}

.left-handle::after {
  left: 0;
}

.right-handle::after {
  right: 0;
}

.editor-area,
.right-sidebar {
  background: var(--pane-bg);
}

.pane-main {
  --pane-bg: var(--editor-bg);
}

.pane-secondary {
  --pane-bg: var(--sidebar-bg);
}

.editor-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 300px;
  position: relative;
}

@media (max-width: 768px) {
  .editor-area {
    min-width: 0 !important;
  }

  .right-as-main .right-sidebar {
    min-width: 0 !important;
  }
}

.layout-container.reading-opt-on .editor-area::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 224, 178, var(--nisb-read-warm-alpha));
  pointer-events: none;
  z-index: 1;
}

.layout-container.reading-opt-on .editor-area {
  scroll-behavior: var(--nisb-read-scroll-behavior);
}

.layout-container.reading-opt-on .editor-area :deep(.detail-scroll),
.layout-container.reading-opt-on .editor-area :deep(.timeline),
.layout-container.reading-opt-on .editor-area :deep(.dock-main),
.layout-container.reading-opt-on .editor-area :deep(.library-detail) {
  scroll-behavior: var(--nisb-read-scroll-behavior);
}

.layout-container.reading-opt-on .editor-area :deep(.preview-content),
.layout-container.reading-opt-on .editor-area :deep(.zen-markdown),
.layout-container.reading-opt-on .editor-area :deep(.reading),
.layout-container.reading-opt-on .editor-area :deep(.detail-scroll),
.layout-container.reading-opt-on .editor-area :deep(.timeline),
.layout-container.reading-opt-on .editor-area :deep(.detail-wrap) {
  font-size: var(--nisb-read-font-size);
  line-height: var(--nisb-read-line-height);
}

.layout-container.reading-opt-on .editor-area :deep(.preview-content),
.layout-container.reading-opt-on .editor-area :deep(.reading) {
  padding-left: var(--nisb-read-padding);
  padding-right: var(--nisb-read-padding);
  box-sizing: border-box;
}

.layout-container.reading-opt-on .editor-area :deep(.preview-content),
.layout-container.reading-opt-on .editor-area :deep(.zen-markdown),
.layout-container.reading-opt-on .editor-area :deep(.reading),
.layout-container.reading-opt-on .editor-area :deep(.timeline) {
  opacity: var(--nisb-read-text-opacity);
}

.layout-container.reading-opt-on .editor-area :deep(img),
.layout-container.reading-opt-on .editor-area :deep(video),
.layout-container.reading-opt-on .editor-area :deep(canvas) {
  opacity: 1 !important;
}

.layout-container.reading-opt-on .editor-area :deep(.library-detail) {
  padding-left: var(--nisb-read-padding) !important;
  padding-right: var(--nisb-read-padding) !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.layout-container.reading-opt-on .editor-area :deep(.doc-panel) {
  margin-top: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
}

.layout-container.reading-opt-on .editor-area :deep(.doc-panel-body) {
  border-top: 0 !important;
  padding-top: 0 !important;
}

.layout-container.reading-opt-on .editor-area :deep(.doc-panel-header),
.layout-container.reading-opt-on .editor-area :deep(.param-bar),
.layout-container.reading-opt-on .editor-area :deep(.continuous-row) {
  padding-left: var(--nisb-read-padding) !important;
  padding-right: var(--nisb-read-padding) !important;
}

.right-as-main .editor-area {
  flex: 0 0 auto;
  min-width: 0;
}

.edge-collapsed {
  width: 0 !important;
  overflow: hidden;
}

.right-sidebar {
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border-left: 1px solid var(--line);
  box-shadow: none;
  position: relative;
}

.right-sidebar.collapsed {
  width: 0 !important;
  overflow: hidden;
  border-left: none;
  box-shadow: none;
}

.right-as-main .right-sidebar {
  flex: 1 1 auto;
  min-width: 300px;
  border-left: none;
  border-right: 1px solid var(--line);
  box-shadow: none;
}

.left-sidebar {
  order: 1;
}

.left-divider,
.left-handle {
  order: 2;
}

.editor-area {
  order: 3;
}

.right-divider,
.right-handle {
  order: 5;
}

.right-sidebar {
  order: 6;
}

.right-as-main .right-sidebar {
  order: 3;
}

.right-as-main .editor-area {
  order: 6;
}

.layout-container.lights-off {
  --nisb-lights-dim: 0.3;
  --nisb-lights-blur: 10px;
  --nisb-lights-sat: 1.25;
  --nisb-lights-overlay: rgba(0, 0, 0, 0.22);
  --nisb-lights-overlay-z: 999;
}

.layout-container.lights-off .left-sidebar {
  pointer-events: none;
}

.layout-container.lights-off .left-sidebar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--nisb-lights-overlay);
  backdrop-filter: blur(var(--nisb-lights-blur)) saturate(var(--nisb-lights-sat)) brightness(var(--nisb-lights-dim));
  -webkit-backdrop-filter: blur(var(--nisb-lights-blur)) saturate(var(--nisb-lights-sat)) brightness(var(--nisb-lights-dim));
  pointer-events: none;
  z-index: var(--nisb-lights-overlay-z);
}

.layout-container.lights-off .right-sidebar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--nisb-lights-overlay);
  backdrop-filter: blur(var(--nisb-lights-blur)) saturate(var(--nisb-lights-sat)) brightness(var(--nisb-lights-dim));
  -webkit-backdrop-filter: blur(var(--nisb-lights-blur)) saturate(var(--nisb-lights-sat)) brightness(var(--nisb-lights-dim));
  pointer-events: none;
  z-index: var(--nisb-lights-overlay-z);
}

.layout-container.lights-off .right-sidebar :deep(.sidebar-body) {
  pointer-events: auto;
}

.layout-container.lights-off .right-sidebar :deep(.header) {
  background: rgba(3, 3, 3, 0.22);
  border-bottom: 1px solid rgba(10, 10, 10, 0.5);
  position: relative;
}

.layout-container.lights-off .right-sidebar :deep(.lights-toggle-btn) {
  border-color: rgba(255, 220, 100, 0.8) !important;
  background: rgba(255, 220, 100, 0.15) !important;
  color: #ffd864 !important;
  box-shadow: 0 0 12px rgba(255, 220, 100, 0.4);
  transform: scale(1.05);
  z-index: calc(var(--nisb-lights-overlay-z) + 1) !important;
  position: relative !important;
}

.layout-container.lights-off .right-sidebar :deep(.lights-toggle-btn:hover) {
  background: rgba(255, 220, 100, 0.25) !important;
  box-shadow: 0 0 20px rgba(255, 220, 100, 0.6);
  transform: scale(1.08);
}

.layout-container.lights-off .right-sidebar :deep(.theme-toggle-btn),
.layout-container.lights-off .right-sidebar :deep(.collapse-btn) {
  opacity: 0.4;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

.layout-container.lights-off .right-sidebar :deep(.header-title) {
  opacity: 0.3;
}

.layout-container.lights-off .editor-area {
  filter: none !important;
  backdrop-filter: none !important;
}
</style>
