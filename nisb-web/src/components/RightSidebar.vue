<template>
  <div class="sidebar" :class="{ 'lights-off-mode': lightsOff }">
    <div
      class="header"
      ref="headerRef"
      @mouseenter="onHeaderEnter"
      @mouseleave="onHeaderLeave"
      @mousemove="onHeaderMouseMove"
      @scroll="onHeaderAreaScroll"
    >
      <div class="header-actions-left">
        <button
          class="collapse-btn"
          @click="collapseSidebar"
          :title="t('rightSidebar.header.collapse')"
          :aria-label="t('rightSidebar.header.collapse')"
          type="button"
        >
          <span class="collapse-icon" aria-hidden="true">│</span>
        </button>

        <button
          class="dock-toggle-btn"
          :class="{ active: dockLibraryRight }"
          :disabled="!dockLibraryRight && !canEnterDock"
          @click="dockLibraryRight ? exitDock() : enterDock()"
          :title="dockToggleTitle"
          :aria-label="dockToggleTitle"
          :aria-pressed="dockLibraryRight ? 'true' : 'false'"
          type="button"
        >
          <span aria-hidden="true">{{ dockLibraryRight ? '↩' : '➡' }}</span>
        </button>

        <button
          ref="lightsBtnRef"
          class="lights-toggle-btn"
          :class="{ active: lightsOff }"
          @click="toggleLights"
          :title="lightsToggleTitle"
          :aria-label="lightsToggleTitle"
          :aria-pressed="lightsOff ? 'true' : 'false'"
          type="button"
        >
          <span aria-hidden="true">{{ lightsOff ? '💡' : '🕯️' }}</span>
        </button>

        <button
          class="readopt-toggle-btn"
          :class="{ active: readOptOpen }"
          @click="toggleReadOpt"
          :title="readOptToggleTitle"
          :aria-label="readOptToggleTitle"
          :aria-pressed="readOptOpen ? 'true' : 'false'"
          type="button"
        >
          <span aria-hidden="true">🎛️</span>
        </button>

        <button
          class="theme-toggle-btn"
          @click="toggleTheme"
          :title="themeToggleTitle"
          :aria-label="themeToggleTitle"
          type="button"
        >
          <span aria-hidden="true">{{ isDark ? '☀️' : '🌙' }}</span>
        </button>

        <button
          class="toggle-all-btn"
          @click="toggleAllNoteOutline"
          :title="t('rightSidebar.header.noteOutlineToggleAll')"
          :aria-label="t('rightSidebar.header.noteOutlineToggleAll')"
          type="button"
        >
          <span aria-hidden="true">{{ noteOutlineAllCollapsed ? '📂' : '📁' }}</span>
        </button>

        <button
          class="insights-toggle-btn"
          :class="{ active: settings.rightShowLibraryInsights }"
          :disabled="dockLibraryRight"
          @click="toggleLibraryInsights"
          :title="insightsToggleTitle"
          :aria-label="insightsToggleTitle"
          :aria-pressed="settings.rightShowLibraryInsights ? 'true' : 'false'"
          type="button"
        >
          <span aria-hidden="true">📚</span>
        </button>

        <button
          class="settings-toggle-btn"
          :class="{ active: uiShowSettings }"
          :disabled="dockLibraryRight"
          @click="uiShowSettings = !uiShowSettings"
          :title="settingsToggleTitle"
          :aria-label="settingsToggleTitle"
          :aria-pressed="uiShowSettings ? 'true' : 'false'"
          type="button"
        >
          <span aria-hidden="true">⚙</span>
        </button>
      </div>

      <div class="header-actions-right">
        <button
          v-if="!dockLibraryRight"
          class="outline-hover-mode-btn"
          :class="{ active: outline_hover_enabled }"
          :title="outline_hover_enabled_title"
          :aria-label="outline_hover_enabled_title"
          :aria-pressed="outline_hover_enabled ? 'true' : 'false'"
          type="button"
          @click="toggle_outline_hover_enabled"
        >
          <span class="outline-hover-mode-icon" aria-hidden="true">📑</span>
        </button>

        <span v-else class="header-title" :title="t('rightSidebar.header.dockIndicator')">📚</span>
      </div>
    </div>

    <div class="sidebar-body" :class="{ docked: dockLibraryRight }">
      <template v-if="dockLibraryRight">
        <div v-if="!effectiveLibraryId" class="dock-empty">
          <div class="dock-empty-title">{{ t('rightSidebar.dock.emptyTitle') }}</div>
          <div class="dock-empty-sub muted">{{ t('rightSidebar.dock.emptySubtitle') }}</div>
        </div>

        <template v-else>
          <div class="dock-layout">
            <div class="dock-main">
              <LibraryDetail
                :library-id="effectiveLibraryId"
                :selected-doc-id="effectiveDocId || null"
                @back="exitDock"
              />
            </div>

            <div class="dock-bottom">
              <LibrarySearchPanel />
            </div>
          </div>
        </template>
      </template>

      <template v-else>
        <EvidencePanel :rssEvidence="rssEvidence" :marketEvidence="marketEvidence" />

        <template v-if="settings.rightShowLibraryInsights">
          <TopicQACard :expanded="qaExpanded" @toggleExpand="qaExpanded = !!$event" />
        </template>

        <template v-if="uiShowSettings">
          <SettingsCard />
          <RssRagSettingsCard />
        </template>

        <NoteOutlinePanel ref="noteOutlineRef" @collapsedChanged="noteOutlineAllCollapsed = $event" />
      </template>
    </div>

    <ReadingOptimizerModal
      v-model="readOptOpen"
      :mode="readingMode"
      :prefs="readingPrefs"
      @apply="onReadApply"
      @preset="onReadPreset"
      @save="onReadSave"
      @reset="onReadReset"
    />
  </div>

  <Teleport to="body">
    <button
      v-if="lightsOff"
      class="lights-escape-btn"
      type="button"
      :style="lightsEscapeStyle"
      :title="lightsToggleTitle"
      :aria-label="lightsToggleTitle"
      aria-pressed="true"
      @click="toggleLights"
    >
      <span aria-hidden="true">💡</span>
    </button>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useHoverScroll } from '../composables/useHoverScroll'
import { useLibrarySearchStore } from '../stores/librarySearch'
import { useSettingsStore } from '../stores/settings'

import EvidencePanel from './RightSidebar/EvidencePanel.vue'
import TopicQACard from './RightSidebar/TopicQACard.vue'
import SettingsCard from './RightSidebar/SettingsCard.vue'
import NoteOutlinePanel from './RightSidebar/NoteOutlinePanel.vue'
import RssRagSettingsCard from './RightSidebar/RssRagSettingsCard.vue'
import ReadingOptimizerModal from './RightSidebar/ReadingOptimizerModal.vue'

import LibraryDetail from './Editor/LibraryDetail.vue'
import LibrarySearchPanel from './Editor/LibrarySearchPanel.vue'

const { t } = useI18n()

const librarySearch = useLibrarySearchStore()
const settings = useSettingsStore()

const dockLibraryRight = ref(false)

const effectiveLibraryId = computed(() => String(librarySearch.libraryId || '').trim())
const effectiveDocId = computed(() => String(librarySearch.docId || '').trim())
const canEnterDock = computed(() => !!effectiveLibraryId.value)

function enterDock() {
  if (!canEnterDock.value) return
  window.dispatchEvent(new CustomEvent('nisb-library-dock-toggle', { detail: { docked: true } }))
}

function exitDock() {
  window.dispatchEvent(new CustomEvent('nisb-library-dock-toggle', { detail: { docked: false } }))
}

function onDockStateChanged(e) {
  const d = e?.detail || {}
  if (typeof d.docked !== 'boolean') return
  dockLibraryRight.value = !!d.docked

  if (dockLibraryRight.value) {
    uiShowSettings.value = false
  }
}


function setGlobalReader(reader) {
  window.nisbReaderState = reader || null
  window.__nisbReaderState = reader || null
}

function getGlobalReader() {
  return window.nisbReaderState || window.__nisbReaderState || null
}

const headerRef = ref(null)
const {
  onRowEnter: onHeaderEnter,
  onRowLeave: onHeaderLeave,
  onScroll: onHeaderScroll,
  onMouseMove: onHeaderMouseMove
} = useHoverScroll(headerRef, { activeHeight: 10 })

function onHeaderAreaScroll(e) {
  onHeaderScroll(e)
  updateLightsEscapePosition()
}

const isDark = ref(false)

function _read_theme_from_storage() {
  try {
    const v = String(localStorage.getItem('nisb_theme') || '').trim().toLowerCase()
    return v === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function sync_theme_flag() {
  isDark.value = _read_theme_from_storage() === 'dark'
}

function on_theme_applied(e) {
  const t0 = String(e?.detail?.theme || '').trim().toLowerCase()
  if (t0 === 'dark') isDark.value = true
  else if (t0 === 'light') isDark.value = false
}

function toggleTheme() {
  window.dispatchEvent(new CustomEvent('nisb_theme_toggle', { detail: {} }))
}

const dockToggleTitle = computed(() => {
  if (dockLibraryRight.value) return t('rightSidebar.header.dockRestore')
  if (canEnterDock.value) return t('rightSidebar.header.dockEnter')
  return t('rightSidebar.header.dockDisabled')
})

const lightsToggleTitle = computed(() =>
  lightsOff.value ? t('rightSidebar.header.lightsOn') : t('rightSidebar.header.lightsOff')
)

const readOptToggleTitle = computed(() =>
  readingMode.value === 'standard'
    ? t('rightSidebar.header.readingOptimizerInactive')
    : t('rightSidebar.header.readingOptimizerActive', { mode: modeLabel.value })
)

const themeToggleTitle = computed(() =>
  isDark.value ? t('rightSidebar.header.themeToLight') : t('rightSidebar.header.themeToDark')
)

const insightsToggleTitle = computed(() => {
  if (dockLibraryRight.value) return t('rightSidebar.header.insightsManagedByDock')
  return settings.rightShowLibraryInsights
    ? t('rightSidebar.header.insightsHide')
    : t('rightSidebar.header.insightsShow')
})

const settingsToggleTitle = computed(() => {
  if (dockLibraryRight.value) return t('rightSidebar.header.settingsHiddenByDock')
  return uiShowSettings.value
    ? t('rightSidebar.header.settingsHide')
    : t('rightSidebar.header.settingsShow')
})

const outline_hover_enabled_key = 'nisb_outline_hover_enabled'
const outline_hover_enabled = ref(true)

function _safe_read_outline_hover_enabled() {
  try {
    const v = String(localStorage.getItem(outline_hover_enabled_key) || '').trim()
    if (v === '0') return false
    if (v === '1') return true
  } catch {}
  return true
}

function sync_outline_hover_enabled_from_storage() {
  outline_hover_enabled.value = _safe_read_outline_hover_enabled()
}

function broadcast_outline_hover_enabled() {
  window.dispatchEvent(
    new CustomEvent('nisb-outline-hover-enabled-changed', {
      detail: { enabled: !!outline_hover_enabled.value }
    })
  )
}

function toast_outline_hover_enabled() {
  const msg = outline_hover_enabled.value
    ? t('rightSidebar.outline.hoverEnabledToast')
    : t('rightSidebar.outline.hoverDisabledToast')
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message: msg, type: 'info' } }))
}

function toggle_outline_hover_enabled() {
  outline_hover_enabled.value = !outline_hover_enabled.value
  try {
    localStorage.setItem(outline_hover_enabled_key, outline_hover_enabled.value ? '1' : '0')
  } catch {}
  broadcast_outline_hover_enabled()
  toast_outline_hover_enabled()
}

const outline_hover_enabled_title = computed(() =>
  outline_hover_enabled.value
    ? t('rightSidebar.header.outlineHoverOn')
    : t('rightSidebar.header.outlineHoverOff')
)

const lightsOff = ref(false)
const lightsBtnRef = ref(null)
const lightsEscapeStyle = ref({})

let __lightsEscapeRaf = null

function updateLightsEscapePosition() {
  if (!lightsOff.value || typeof window === 'undefined') return

  if (__lightsEscapeRaf) {
    window.cancelAnimationFrame(__lightsEscapeRaf)
    __lightsEscapeRaf = null
  }

  __lightsEscapeRaf = window.requestAnimationFrame(() => {
    __lightsEscapeRaf = null

    const el = lightsBtnRef.value
    const rect = el && typeof el.getBoundingClientRect === 'function'
      ? el.getBoundingClientRect()
      : null

    if (!rect || rect.width <= 0 || rect.height <= 0) {
      lightsEscapeStyle.value = {
        top: '8px',
        right: '8px',
        width: '32px',
        height: '32px'
      }
      return
    }

    lightsEscapeStyle.value = {
      left: `${Math.round(rect.left)}px`,
      top: `${Math.round(rect.top)}px`,
      width: `${Math.round(rect.width)}px`,
      height: `${Math.round(rect.height)}px`
    }
  })
}

function syncLightsFromStorage() {
  try {
    const v = localStorage.getItem('nisb_lights_off')
    lightsOff.value = v === '1'
  } catch {
    lightsOff.value = false
  }
}

function onLightsChanged(e) {
  const d = e?.detail || null

  if (d && Object.prototype.hasOwnProperty.call(d, 'off')) {
    lightsOff.value = !!d.off
    return
  }

  syncLightsFromStorage()
}

function toggleLights() {
  const next = !lightsOff.value
  lightsOff.value = next
  window.dispatchEvent(new CustomEvent('nisb-toggle-lights', { detail: { off: next } }))
}

watch(
  lightsOff,
  async (val) => {
    if (!val) return
    await nextTick()
    updateLightsEscapePosition()
  },
  { flush: 'post' }
)

const readOptOpen = ref(false)

const readingMode = ref('standard')
const readingPrefs = reactive({
  brightness: 100,
  fontSize: 16,
  lineHeight: 1.6,
  padding: 0,
  warmth: 0,
  smooth: 0,
  bgDepth: 0
})

const modeLabel = computed(() => {
  const m = readingMode.value
  if (m === 'standard') return t('rightSidebar.readingOptimizer.modes.standard')
  if (m === 'custom') return t('rightSidebar.readingOptimizer.modes.custom')
  if (m === 'eye') return t('rightSidebar.readingOptimizer.modes.eye')
  if (m === 'novel') return t('rightSidebar.readingOptimizer.modes.novel')
  if (m === 'academic') return t('rightSidebar.readingOptimizer.modes.academic')
  if (m === 'code') return t('rightSidebar.readingOptimizer.modes.code')
  return m
})

function syncFromReadingStateEvent(e) {
  const d = e?.detail || {}
  if (typeof d.mode === 'string') readingMode.value = d.mode

  const p = d.prefs || {}
  if (p && typeof p === 'object') {
    if (typeof p.brightness === 'number') readingPrefs.brightness = p.brightness
    if (typeof p.fontSize === 'number') readingPrefs.fontSize = p.fontSize
    if (typeof p.lineHeight === 'number') readingPrefs.lineHeight = p.lineHeight
    if (typeof p.padding === 'number') readingPrefs.padding = p.padding
    if (typeof p.warmth === 'number') readingPrefs.warmth = p.warmth
    if (typeof p.smooth === 'number') readingPrefs.smooth = p.smooth
    if (typeof p.bgDepth === 'number') readingPrefs.bgDepth = p.bgDepth
  }
}

function openReadOpt() {
  readOptOpen.value = true
  window.dispatchEvent(new CustomEvent('nisb-reading-request'))
}

function closeReadOpt() {
  readOptOpen.value = false
}

function toggleReadOpt() {
  readOptOpen.value ? closeReadOpt() : openReadOpt()
}

function onReadApply(prefs) {
  window.dispatchEvent(new CustomEvent('nisb-reading-apply', { detail: { prefs } }))
}

function onReadPreset(preset) {
  window.dispatchEvent(new CustomEvent('nisb-reading-preset', { detail: { preset } }))
}

function onReadSave() {
  window.dispatchEvent(new CustomEvent('nisb-reading-save'))
}

function onReadReset() {
  window.dispatchEvent(new CustomEvent('nisb-reading-reset'))
}

function onKeydown(e) {
  if (e.key === 'Escape' && readOptOpen.value) closeReadOpt()
}

function collapseSidebar() {
  window.dispatchEvent(new CustomEvent('toggle-right-sidebar'))
}

const noteOutlineRef = ref(null)
const noteOutlineAllCollapsed = ref(false)

function toggleAllNoteOutline() {
  if (noteOutlineRef.value && typeof noteOutlineRef.value.toggleAll === 'function') {
    noteOutlineRef.value.toggleAll()
  }
}

function toggleLibraryInsights() {
  if (dockLibraryRight.value) return
  settings.setRightShowLibraryInsights(!settings.rightShowLibraryInsights)
}

const uiShowSettings = ref(true)

watch(
  () => settings.rightShowLibraryInsights,
  (val) => {
    if (!val) uiShowSettings.value = false
  },
  { immediate: true }
)

const qaExpanded = ref(false)

const rssEvidence = ref([])
const marketEvidence = ref([])

function onChatEvidence(evt) {
  const d = evt?.detail || {}
  const rss = Array.isArray(d.rssevidence) ? d.rssevidence : Array.isArray(d.rss_evidence) ? d.rss_evidence : []
  const market = Array.isArray(d.marketevidence)
    ? d.marketevidence
    : Array.isArray(d.market_evidence)
      ? d.market_evidence
      : []
  rssEvidence.value = rss
  marketEvidence.value = market
}

function onLibraryDocOpenedImpl(e) {
  const detail = e?.detail || {}
  const lib = detail.libraryId || detail.library_id || null
  const doc = detail.docId || detail.doc_id || null

  if (detail && Object.prototype.hasOwnProperty.call(detail, 'reader')) {
    setGlobalReader(detail.reader)
  }

  if (lib && doc && typeof librarySearch.setContext === 'function') {
    librarySearch.setContext({ libraryId: lib, docId: doc, preserveResults: true })
  }
}

let __rsTimer = null
let __rsIdleId = null

function _cancelIdle() {
  if (__rsIdleId && 'cancelIdleCallback' in window) {
    try {
      window.cancelIdleCallback(__rsIdleId)
    } catch {}
  }
  __rsIdleId = null
}

function onLibraryDocOpened(e) {
  if (__rsTimer) clearTimeout(__rsTimer)
  _cancelIdle()

  const seqAtCall = window.__nisbDocSwitchSeq || 0

  __rsTimer = setTimeout(() => {
    const run = () => {
      if ((window.__nisbDocSwitchSeq || 0) !== seqAtCall) return
      onLibraryDocOpenedImpl(e)
    }

    if ('requestIdleCallback' in window) {
      __rsIdleId = window.requestIdleCallback(run, { timeout: 800 })
    } else {
      setTimeout(run, 0)
    }
  }, 250)
}

function handleHebbianCompleted(e) {
  const detail = e?.detail || {}
  const source = detail.source || t('rightSidebar.hebbian.unknownSource')
  const sourceLabel = detail.type === 'note'
    ? t('rightSidebar.hebbian.sourceNote')
    : t('rightSidebar.hebbian.sourceGeneric')

  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: {
        message: t('rightSidebar.hebbian.completedToast', { sourceLabel, source }),
        type: 'info'
      }
    })
  )
}

onMounted(() => {
  sync_theme_flag()
  window.addEventListener('nisb_theme_applied', on_theme_applied)

  if (typeof window.nisbReaderState === 'undefined' && typeof window.__nisbReaderState === 'undefined') {
    setGlobalReader(null)
  }

  syncLightsFromStorage()
  updateLightsEscapePosition()

  try {
    const s = window.__nisbLibraryDockState
    if (s && typeof s.docked === 'boolean') dockLibraryRight.value = !!s.docked
  } catch {}

  sync_outline_hover_enabled_from_storage()
  broadcast_outline_hover_enabled()

  window.addEventListener('nisb-chat-evidence', onChatEvidence)
  window.addEventListener('nisb-open-library-doc', onLibraryDocOpened)
  window.addEventListener('nisb-hebbian-completed', handleHebbianCompleted)
  window.addEventListener('nisb-lights-changed', onLightsChanged)
  window.addEventListener('resize', updateLightsEscapePosition)
  window.addEventListener('scroll', updateLightsEscapePosition, true)
  window.addEventListener('nisb-reading-state', syncFromReadingStateEvent)
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('nisb-library-dock', onDockStateChanged)

  window.dispatchEvent(new CustomEvent('nisb-reading-request'))
})

onUnmounted(() => {
  if (__rsTimer) clearTimeout(__rsTimer)
  _cancelIdle()

  window.removeEventListener('nisb-chat-evidence', onChatEvidence)
  window.removeEventListener('nisb-open-library-doc', onLibraryDocOpened)
  window.removeEventListener('nisb-hebbian-completed', handleHebbianCompleted)
  window.removeEventListener('nisb-lights-changed', onLightsChanged)
  window.removeEventListener('resize', updateLightsEscapePosition)
  window.removeEventListener('scroll', updateLightsEscapePosition, true)

  if (__lightsEscapeRaf) {
    window.cancelAnimationFrame(__lightsEscapeRaf)
    __lightsEscapeRaf = null
  }
  window.removeEventListener('nisb-reading-state', syncFromReadingStateEvent)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('nisb-library-dock', onDockStateChanged)
  window.removeEventListener('nisb_theme_applied', on_theme_applied)
})

defineExpose({ getGlobalReader })
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 38%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
}

.header {
  --nisb-sidebar-bar-height: 44px;
  --nisb-sidebar-control-height: 32px;
  --nisb-sidebar-radius: 12px;
  --nisb-sidebar-bg:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 34%, transparent)
    );
  --nisb-sidebar-bg-hover:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  --nisb-sidebar-bg-active:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 12%, transparent)
    );
  --nisb-sidebar-border: color-mix(in srgb, var(--line) 84%, transparent);
  --nisb-sidebar-border-hover: color-mix(in srgb, var(--selected) 28%, var(--line));
  --nisb-sidebar-border-active: color-mix(in srgb, var(--selected) 58%, var(--line));
  --nisb-sidebar-ring: color-mix(in srgb, var(--selected) 12%, transparent);

  position: relative;
  z-index: auto;
  isolation: auto;
  flex: 0 0 auto;
  width: 100%;
  min-width: 0;
  height: var(--nisb-sidebar-bar-height);
  min-height: var(--nisb-sidebar-bar-height);
  max-height: var(--nisb-sidebar-bar-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.header::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 20%, var(--line)),
      transparent
    );
  opacity: 0.68;
}

.header::-webkit-scrollbar {
  display: none;
}

.header-actions-left,
.header-actions-right {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  min-width: max-content;
}

.header-actions-right {
  margin-left: auto;
}

.header-title {
  flex: 0 0 auto;
  width: var(--nisb-sidebar-control-height);
  height: var(--nisb-sidebar-control-height);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: var(--nisb-sidebar-radius);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 38%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  color: var(--selected);
  font-size: 0.95rem;
  line-height: 1;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.collapse-btn,
.theme-toggle-btn,
.lights-toggle-btn,
.readopt-toggle-btn,
.toggle-all-btn,
.insights-toggle-btn,
.settings-toggle-btn,
.dock-toggle-btn,
.outline-hover-mode-btn {
  width: var(--nisb-sidebar-control-height);
  height: var(--nisb-sidebar-control-height);
  min-width: var(--nisb-sidebar-control-height);
  max-width: var(--nisb-sidebar-control-height);
  min-height: var(--nisb-sidebar-control-height);
  max-height: var(--nisb-sidebar-control-height);
  flex: 0 0 auto;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--nisb-sidebar-border);
  border-radius: var(--nisb-sidebar-radius);
  background: var(--nisb-sidebar-bg);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 1px 2px rgba(0, 0, 0, 0.035);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    filter 0.15s ease,
    transform 0.12s ease;
}

.collapse-btn:hover,
.collapse-btn:focus-visible,
.theme-toggle-btn:hover,
.theme-toggle-btn:focus-visible,
.lights-toggle-btn:hover,
.lights-toggle-btn:focus-visible,
.readopt-toggle-btn:hover,
.readopt-toggle-btn:focus-visible,
.toggle-all-btn:hover,
.toggle-all-btn:focus-visible,
.insights-toggle-btn:hover,
.insights-toggle-btn:focus-visible,
.settings-toggle-btn:hover,
.settings-toggle-btn:focus-visible,
.dock-toggle-btn:hover:not(:disabled),
.dock-toggle-btn:focus-visible:not(:disabled),
.outline-hover-mode-btn:hover,
.outline-hover-mode-btn:focus-visible {
  border-color: var(--nisb-sidebar-border-hover);
  background: var(--nisb-sidebar-bg-hover);
  color: var(--text-main, var(--text));
  box-shadow:
    0 0 0 2px var(--nisb-sidebar-ring),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.collapse-btn:active,
.theme-toggle-btn:active,
.lights-toggle-btn:active,
.readopt-toggle-btn:active,
.toggle-all-btn:active,
.insights-toggle-btn:active,
.settings-toggle-btn:active,
.dock-toggle-btn:active:not(:disabled),
.outline-hover-mode-btn:active {
  transform: translateY(1px);
}

.lights-toggle-btn.active,
.readopt-toggle-btn.active,
.insights-toggle-btn.active,
.settings-toggle-btn.active,
.dock-toggle-btn.active,
.outline-hover-mode-btn.active {
  border-color: var(--nisb-sidebar-border-active);
  background: var(--nisb-sidebar-bg-active);
  color: var(--selected);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.10);
}

.lights-toggle-btn.active {
  position: relative;
  z-index: 2147483000;
  isolation: isolate;
  border-color: color-mix(in srgb, #f59e0b 72%, var(--line));
  background:
    radial-gradient(circle at 50% 36%, color-mix(in srgb, #fbbf24 30%, transparent), transparent 56%),
    linear-gradient(
      135deg,
      color-mix(in srgb, #d97706 28%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
  color: #d97706;
  filter: none;
  opacity: 1;
  text-shadow: 0 0 12px color-mix(in srgb, #f59e0b 58%, transparent);
  box-shadow:
    0 0 0 2px color-mix(in srgb, #d97706 18%, transparent),
    0 0 18px color-mix(in srgb, #f59e0b 34%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.18);
}

.lights-escape-btn {
  position: fixed;
  z-index: 2147483647;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, #f59e0b 76%, var(--line));
  border-radius: 12px;
  background:
    radial-gradient(circle at 50% 36%, color-mix(in srgb, #fbbf24 42%, transparent), transparent 58%),
    linear-gradient(
      135deg,
      color-mix(in srgb, #d97706 34%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: #f59e0b;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1;
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  filter: none;
  text-shadow: 0 0 14px color-mix(in srgb, #fbbf24 68%, transparent);
  box-shadow:
    0 0 0 2px color-mix(in srgb, #f59e0b 24%, transparent),
    0 0 22px color-mix(in srgb, #f59e0b 46%, transparent),
    0 12px 28px rgba(0, 0, 0, 0.24);
  transform: translateZ(0);
}

.lights-escape-btn:hover,
.lights-escape-btn:focus-visible {
  border-color: color-mix(in srgb, #fbbf24 88%, var(--line));
  color: #fbbf24;
  outline: none;
  box-shadow:
    0 0 0 3px color-mix(in srgb, #f59e0b 28%, transparent),
    0 0 28px color-mix(in srgb, #fbbf24 58%, transparent),
    0 14px 32px rgba(0, 0, 0, 0.30);
}

.readopt-toggle-btn.active {
  border-color: color-mix(in srgb, #16a34a 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, #16a34a 12%, var(--editor-bg)),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: #16a34a;
}

.dock-toggle-btn.active,
.insights-toggle-btn.active,
.settings-toggle-btn.active,
.outline-hover-mode-btn.active {
  border-color: var(--nisb-sidebar-border-active);
}

.sidebar.lights-off-mode .header .collapse-btn,
.sidebar.lights-off-mode .header .theme-toggle-btn,
.sidebar.lights-off-mode .header .readopt-toggle-btn,
.sidebar.lights-off-mode .header .toggle-all-btn,
.sidebar.lights-off-mode .header .insights-toggle-btn,
.sidebar.lights-off-mode .header .settings-toggle-btn,
.sidebar.lights-off-mode .header .dock-toggle-btn,
.sidebar.lights-off-mode .header .outline-hover-mode-btn,
.sidebar.lights-off-mode .header .header-title {
  opacity: 0.48;
  filter: saturate(0.68) brightness(0.82);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.sidebar.lights-off-mode .header .collapse-btn:hover,
.sidebar.lights-off-mode .header .theme-toggle-btn:hover,
.sidebar.lights-off-mode .header .readopt-toggle-btn:hover,
.sidebar.lights-off-mode .header .toggle-all-btn:hover,
.sidebar.lights-off-mode .header .insights-toggle-btn:hover,
.sidebar.lights-off-mode .header .settings-toggle-btn:hover,
.sidebar.lights-off-mode .header .dock-toggle-btn:hover:not(:disabled),
.sidebar.lights-off-mode .header .outline-hover-mode-btn:hover,
.sidebar.lights-off-mode .header .collapse-btn:focus-visible,
.sidebar.lights-off-mode .header .theme-toggle-btn:focus-visible,
.sidebar.lights-off-mode .header .readopt-toggle-btn:focus-visible,
.sidebar.lights-off-mode .header .toggle-all-btn:focus-visible,
.sidebar.lights-off-mode .header .insights-toggle-btn:focus-visible,
.sidebar.lights-off-mode .header .settings-toggle-btn:focus-visible,
.sidebar.lights-off-mode .header .dock-toggle-btn:focus-visible:not(:disabled),
.sidebar.lights-off-mode .header .outline-hover-mode-btn:focus-visible {
  opacity: 0.74;
  filter: saturate(0.82) brightness(0.94);
}

.sidebar.lights-off-mode .header .lights-toggle-btn.active {
  opacity: 1;
  filter: none;
  pointer-events: auto;
  visibility: visible;
}

.dock-toggle-btn:disabled,
.insights-toggle-btn:disabled,
.settings-toggle-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  box-shadow: none;
  filter: saturate(0.72);
}

.dock-toggle-btn:disabled:hover,
.insights-toggle-btn:disabled:hover,
.settings-toggle-btn:disabled:hover,
.dock-toggle-btn:disabled:focus-visible,
.insights-toggle-btn:disabled:focus-visible,
.settings-toggle-btn:disabled:focus-visible {
  border-color: var(--nisb-sidebar-border);
  background: var(--nisb-sidebar-bg);
  color: var(--text-secondary);
  transform: none;
  outline: none;
}

.collapse-icon {
  font-size: 15px;
  font-weight: 820;
  line-height: 1;
}

.outline-hover-mode-btn {
  padding: 0;
}

.outline-hover-mode-icon {
  line-height: 1;
}



.sidebar-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 76%, transparent)
    );
  scrollbar-width: thin;
}

.sidebar-body.docked {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dock-layout {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.dock-main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.dock-bottom {
  flex: 0 0 auto;
  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.dock-empty {
  margin: 10px 8px;
  padding: 14px;
  border: 1px dashed color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 48%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
}

.dock-empty-title {
  margin-bottom: 6px;
  color: var(--text-main, var(--text));
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.dock-empty-sub {
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.muted {
  color: var(--text-secondary);
}

@media (max-width: 420px) {
  .header {
    padding: 6px;
  }

  .header-actions-left,
  .header-actions-right {
    gap: 4px;
  }

  .dock-empty {
    margin: 8px 7px;
    padding: 12px;
  }
}

</style>

