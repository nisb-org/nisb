<template>
  <div ref="wrapRef" class="feed-wrap">
    <div class="tabs" role="tablist">
      <div class="tabs-left" aria-label="Feed scopes">
        <button
          class="tab"
          :class="{ active: tab === 'mine' }"
          type="button"
          role="tab"
          :aria-selected="tab === 'mine'"
          @click="switchTab('mine')"
        >
          <span v-if="tabTextMode === 'full'">{{ t("feed.panel.tabs.mine.full") }}</span>
          <span v-else-if="tabTextMode === 'noEmoji'">{{ t("feed.panel.tabs.mine.noEmoji") }}</span>
          <span v-else>{{ t("feed.panel.tabs.mine.compact") }}</span>
        </button>

        <button
          class="tab"
          :class="{ active: tab === 'latest' }"
          type="button"
          role="tab"
          :aria-selected="tab === 'latest'"
          @click="switchTab('latest')"
        >
          <span v-if="tabTextMode === 'full'">{{ t("feed.panel.tabs.latest.full") }}</span>
          <span v-else-if="tabTextMode === 'noEmoji'">{{ t("feed.panel.tabs.latest.noEmoji") }}</span>
          <span v-else>{{ t("feed.panel.tabs.latest.compact") }}</span>
        </button>

        <button
          class="tab"
          :class="{ active: tab === 'tags' }"
          type="button"
          role="tab"
          :aria-selected="tab === 'tags'"
          @click="switchTab('tags')"
        >
          <span v-if="tabTextMode === 'full'">{{ t("feed.panel.tabs.tags.full") }}</span>
          <span v-else-if="tabTextMode === 'noEmoji'">{{ t("feed.panel.tabs.tags.noEmoji") }}</span>
          <span v-else>{{ t("feed.panel.tabs.tags.compact") }}</span>
        </button>

        <button
          class="tab"
          :class="{ active: tab === 'foryou' }"
          type="button"
          role="tab"
          :aria-selected="tab === 'foryou'"
          @click="switchTab('foryou')"
        >
          <span v-if="tabTextMode === 'full'">{{ t("feed.panel.tabs.foryou.full") }}</span>
          <span v-else-if="tabTextMode === 'noEmoji'">{{ t("feed.panel.tabs.foryou.noEmoji") }}</span>
          <span v-else>{{ t("feed.panel.tabs.foryou.compact") }}</span>
        </button>

        <div class="pill" v-if="tabMode === 'tag_filter' && activeTag">
          <span class="pill-text">#{{ activeTag }}</span>
          <button class="pill-x" type="button" :title="t('feed.panel.tag.clear')" @click="clearTag">×</button>
        </div>
      </div>

      <div class="tabs-spacer"></div>

      <div v-if="!compactActions" class="tabs-actions">
        <button
          class="icon-btn"
          type="button"
          :title="t('feed.panel.actions.notifications')"
          :aria-label="t('feed.panel.actions.notifications')"
          @click="openNotifications"
        >
          <span aria-hidden="true">🔔</span>
          <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? "99+" : unreadCount }}</span>
        </button>

        <button
          class="icon-btn"
          type="button"
          :title="t('feed.panel.actions.me')"
          :aria-label="t('feed.panel.actions.me')"
          @click="openMe"
        >
          <span aria-hidden="true">👤</span>
        </button>

        <button class="btn" type="button" @click="hardRefresh" :disabled="loadingTop">
          {{ loadingTop ? t("feed.panel.actions.loading") : t("feed.panel.actions.refresh") }}
        </button>
      </div>

      <div v-else class="tabs-actions compact" ref="menuWrapRef">
        <button
          class="icon-btn"
          type="button"
          :title="t('feed.panel.actions.menu')"
          :aria-label="t('feed.panel.actions.menu')"
          :aria-expanded="actionsOpen"
          @click="toggleActionsMenu"
        >
          <span aria-hidden="true">⋯</span>
          <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? "99+" : unreadCount }}</span>
        </button>

        <div v-if="actionsOpen" class="menu" role="menu">
          <button class="menu-item" type="button" role="menuitem" @click="onMenuNotifications">
            <span>{{ t("feed.panel.actions.notifications") }}</span>
            <span v-if="unreadCount > 0" class="menu-badge">{{ unreadCount > 99 ? "99+" : unreadCount }}</span>
          </button>

          <button class="menu-item" type="button" role="menuitem" @click="onMenuMe">
            <span>{{ t("feed.panel.actions.me") }}</span>
          </button>

          <button class="menu-item" type="button" role="menuitem" @click="onMenuRefresh" :disabled="loadingTop">
            <span>{{ loadingTop ? t("feed.panel.actions.loading") : t("feed.panel.actions.refresh") }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="feed-body" :class="{ 'has-detail': !!selectedItem && !useDrawer }">
      <div class="left-pane">
        <div class="left-scroll">
          <template v-if="tab === 'tags'">
            <FeedTagsView @select="onTagSelectedFromCloud" />
          </template>

          <template v-else>
            <FeedTimeline
              :mode="tabMode"
              :tag="activeTag"
              :selectedId="selectedItem?.id || ''"
              @open="openItem"
              @select-tag="onTagSelectedInline"
              @delete="confirmDelete"
              @refresh="hardRefresh"
            />
          </template>
        </div>
      </div>

      <div v-if="selectedItem && !useDrawer" class="detail-pane">
        <FeedItemDetail :item="selectedItem" @close="closeDetail" />
      </div>
    </div>

    <div v-if="selectedItem && useDrawer" class="drawer-mask" @click="closeDetail">
      <div class="drawer detail-drawer" role="dialog" aria-modal="true" @click.stop @keydown.esc="closeDetail">
        <div class="drawer-body">
          <FeedItemDetail :item="selectedItem" @close="closeDetail" />
        </div>
      </div>
    </div>

    <div v-if="notifOpen" class="drawer-mask" @click="closeNotifications">
      <div class="drawer side-drawer" role="dialog" aria-modal="true" @click.stop @keydown.esc="closeNotifications">
        <div class="drawer-actions">
          <button class="btn" type="button" @click="closeNotifications">{{ t("feed.panel.drawer.close") }}</button>
        </div>
        <div class="drawer-body">
          <FeedNotifications ref="notifRef" @unread="(n) => (unreadCount = n)" />
        </div>
      </div>
    </div>

    <div v-if="meOpen" class="drawer-mask" @click="closeMe">
      <div class="drawer side-drawer" role="dialog" aria-modal="true" @click.stop @keydown.esc="closeMe">
        <div class="drawer-actions">
          <button class="btn" type="button" @click="closeMe">{{ t("feed.panel.drawer.close") }}</button>
        </div>
        <div class="drawer-body">
          <FeedMePanel ref="meRef" @open-feed="onMeOpenFeed" />
        </div>
      </div>
    </div>

    <div v-if="deleteTarget" class="confirm-mask" @click="cancelDelete">
      <div class="confirm" role="dialog" aria-modal="true" @click.stop>
        <div class="confirm-title">{{ t("feed.panel.delete.title") }}</div>
        <div class="confirm-desc">{{ t("feed.panel.delete.desc") }}</div>
        <div class="confirm-actions">
          <button class="btn" type="button" @click="cancelDelete">{{ t("feed.panel.delete.cancel") }}</button>
          <button class="btn danger" type="button" @click="doDelete">{{ t("feed.panel.delete.confirm") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

import FeedTimeline from "./FeedTimeline.vue"
import FeedTagsView from "./FeedTagsView.vue"
import FeedItemDetail from "./FeedItemDetail.vue"
import FeedNotifications from "./FeedNotifications.vue"
import FeedMePanel from "./FeedMePanel.vue"

const { t } = useI18n()
const { callTool } = useMCP()

const wrapRef = ref(null)
const menuWrapRef = ref(null)

const tab = ref("latest")
const activeTag = ref("")
const selectedItem = ref(null)

const loadingTop = ref(false)
const panelWidth = ref(0)

let ro = null
let cleanupRO = null

const deleteTarget = ref(null)

const notifOpen = ref(false)
const notifRef = ref(null)
const unreadCount = ref(0)

const meOpen = ref(false)
const meRef = ref(null)

let stopStream = null
let pollTimer = null
let sseStopped = false

const actionsOpen = ref(false)

const tabMode = computed(() => {
  if (tab.value === "mine") return "mine"
  if (tab.value === "foryou") return "recommended"
  if (activeTag.value) return "tag_filter"
  return "latest"
})

const DRAWER_THRESHOLD = 860
const useDrawer = computed(() => panelWidth.value > 0 && panelWidth.value < DRAWER_THRESHOLD)

const compactActions = computed(() => panelWidth.value > 0 && panelWidth.value < 560)

const tabTextMode = computed(() => {
  const w = panelWidth.value
  if (w === 0) return "full"
  if (w >= 480) return "full"
  if (w >= 360) return "noEmoji"
  return "compact"
})

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

let __lockCount = 0
let __savedOverflow = ""

function _lockBodyScroll() {
  if (__lockCount === 0) {
    __savedOverflow = document.body.style.overflow || ""
    document.body.style.overflow = "hidden"
  }
  __lockCount += 1
}

function _unlockBodyScroll() {
  __lockCount = Math.max(0, __lockCount - 1)
  if (__lockCount === 0) document.body.style.overflow = __savedOverflow
}

function _forceUnlockBodyScroll() {
  __lockCount = 0
  document.body.style.overflow = __savedOverflow
}

function _syncBodyLock() {
  const needLock = !!notifOpen.value || !!meOpen.value || (!!selectedItem.value && useDrawer.value)
  if (needLock) {
    if (__lockCount === 0) _lockBodyScroll()
  } else if (__lockCount > 0) {
    _unlockBodyScroll()
  }
}

function setupWidthObserver() {
  const el = wrapRef.value
  if (!el || typeof ResizeObserver === "undefined") return () => {}

  const apply = () => {
    panelWidth.value = Math.round(el.getBoundingClientRect().width || 0)
  }

  ro = new ResizeObserver(() => apply())
  ro.observe(el)
  apply()

  return () => {
    try {
      ro && ro.disconnect()
    } catch {}
    ro = null
  }
}

function switchTab(tKey) {
  const changed = tab.value !== tKey
  tab.value = tKey
  actionsOpen.value = false

  if (changed) closeDetail()
  if (tKey === "latest") activeTag.value = ""
}

function clearTag() {
  activeTag.value = ""
  actionsOpen.value = false
  if (tab.value !== "tags") window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
}

async function openItem(it) {
  selectedItem.value = it
  actionsOpen.value = false
  await nextTick()
  _syncBodyLock()
}

function closeDetail() {
  selectedItem.value = null
  _syncBodyLock()
}

async function hardRefresh() {
  loadingTop.value = true
  try {
    await callTool("nisb_feed_compact", {})
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
    await refreshUnread()
  } catch (e) {
    toast(e?.message || t("feed.panel.toast.refreshFailed"), "error")
  } finally {
    loadingTop.value = false
  }
}

function onTagSelectedFromCloud(tagStr) {
  activeTag.value = String(tagStr || "").trim()
  tab.value = "latest"
  actionsOpen.value = false
  closeDetail()
  window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
}

function onTagSelectedInline(tagStr) {
  activeTag.value = String(tagStr || "").trim()
  tab.value = "latest"
  actionsOpen.value = false
  closeDetail()
  window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
}

function confirmDelete(it) {
  deleteTarget.value = it
  actionsOpen.value = false
}

function cancelDelete() {
  deleteTarget.value = null
}

async function doDelete() {
  const it = deleteTarget.value
  if (!it?.id) {
    deleteTarget.value = null
    return
  }

  try {
    const res = await callTool("nisb_feed_delete_post", { feed_id: it.id })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.panel.toast.deleteFailed"))
    toast(t("feed.panel.toast.deleted"), "success")
    deleteTarget.value = null
    if (selectedItem.value?.id === it.id) closeDetail()
    await hardRefresh()
  } catch (e) {
    toast(e?.message || t("feed.panel.toast.deleteFailed"), "error")
  }
}

async function openMe() {
  meOpen.value = true
  notifOpen.value = false
  actionsOpen.value = false
  _syncBodyLock()
  await nextTick()
  await meRef.value?.refresh?.()
}

function closeMe() {
  meOpen.value = false
  _syncBodyLock()
}

async function onMeOpenFeed(item) {
  await openItem(item)
  closeMe()
}

async function openNotifications() {
  notifOpen.value = true
  meOpen.value = false
  actionsOpen.value = false
  _syncBodyLock()
  await nextTick()

  try {
    await callTool("nisb_feed_mark_all_read", {})
  } catch {}

  await nextTick()
  await notifRef.value?.refresh?.()
  await refreshUnread()
}

function closeNotifications() {
  notifOpen.value = false
  _syncBodyLock()
}

async function refreshUnread() {
  try {
    const res = await callTool("nisb_feed_notifications", { limit: 1 })
    if (!res || res.success === false) return
    unreadCount.value = Number(res.unread_count || 0)
  } catch {}
}

function toggleActionsMenu() {
  actionsOpen.value = !actionsOpen.value
}

async function onMenuNotifications() {
  actionsOpen.value = false
  await openNotifications()
}

async function onMenuMe() {
  actionsOpen.value = false
  await openMe()
}

async function onMenuRefresh() {
  actionsOpen.value = false
  await hardRefresh()
}

function onDocPointerDown(e) {
  if (!actionsOpen.value) return
  const el = menuWrapRef.value
  if (!el) return
  if (el.contains(e.target)) return
  actionsOpen.value = false
}

function getTokenMaybe() {
  return (
    localStorage.getItem("nisb-token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("Authorization") ||
    ""
  )
}

async function startSSE() {
  sseStopped = false
  const token = getTokenMaybe()
  const controller = new AbortController()
  stopStream = () => controller.abort()

  try {
    const headers = {}
    if (token) headers["Authorization"] = token.startsWith("Bearer ") ? token : `Bearer ${token}`

    const resp = await fetch("/api/feed/notifications/stream", {
      method: "GET",
      headers,
      signal: controller.signal,
    })

    if (!resp.ok || !resp.body) throw new Error("SSE not available")

    const reader = resp.body.getReader()
    const decoder = new TextDecoder("utf-8")
    let buf = ""

    while (!sseStopped) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      const parts = buf.split("\n\n")
      buf = parts.pop() || ""

      for (const chunk of parts) {
        const lines = chunk.split("\n")
        for (const ln of lines) {
          if (!ln.startsWith("data:")) continue
          const payload = ln.slice(5).trim()
          if (!payload) continue

          try {
            const msg = JSON.parse(payload)
            if (msg?.type === "notification") {
              await refreshUnread()
              if (notifOpen.value) notifRef.value?.refresh?.()
            }
          } catch {}
        }
      }
    }
  } catch {
    if (sseStopped || controller.signal.aborted) return
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(() => refreshUnread(), 15000)
  }
}

function stopSSEFn() {
  sseStopped = true

  try {
    if (stopStream) stopStream()
  } catch {}
  stopStream = null

  try {
    if (pollTimer) clearInterval(pollTimer)
  } catch {}
  pollTimer = null
}

function onKeydown(e) {
  if (e.key !== "Escape") return

  if (deleteTarget.value) {
    e.preventDefault()
    cancelDelete()
    return
  }

  if (actionsOpen.value) {
    e.preventDefault()
    actionsOpen.value = false
    return
  }

  if (meOpen.value) {
    e.preventDefault()
    closeMe()
    return
  }

  if (notifOpen.value) {
    e.preventDefault()
    closeNotifications()
    return
  }

  if (selectedItem.value) {
    e.preventDefault()
    closeDetail()
  }
}

watch(
  () => compactActions.value,
  () => {
    if (!compactActions.value) actionsOpen.value = false
  }
)

watch(
  () => useDrawer.value,
  () => _syncBodyLock()
)

watch(
  () => selectedItem.value?.id,
  () => _syncBodyLock()
)

watch(
  () => notifOpen.value,
  () => _syncBodyLock()
)

watch(
  () => meOpen.value,
  () => _syncBodyLock()
)

onMounted(async () => {
  cleanupRO = setupWidthObserver()
  window.addEventListener("keydown", onKeydown)
  window.addEventListener("pointerdown", onDocPointerDown, true)

  await hardRefresh()
  await refreshUnread()
  startSSE()
})

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown)
  window.removeEventListener("pointerdown", onDocPointerDown, true)

  cleanupRO && cleanupRO()
  cleanupRO = null

  _forceUnlockBodyScroll()
  stopSSEFn()
})
</script>

<style scoped>
.feed-wrap {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 6%, transparent), transparent 32%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 36%, var(--editor-bg))
    );
  color: var(--text);
}

.tabs {
  flex: 0 0 auto;
  min-width: 0;
  min-height: 52px;
  display: flex;
  align-items: center;
  gap: 0.58rem;
  padding: 0.54rem 0.76rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  backdrop-filter: blur(14px) saturate(1.05);
  -webkit-backdrop-filter: blur(14px) saturate(1.05);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  z-index: 8;
}

.tabs-left {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  flex: 1 1 auto;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.tabs-left::-webkit-scrollbar {
  display: none;
}

.tabs-spacer {
  flex: 1 1 auto;
  min-width: 0;
}

.tab {
  flex: 0 0 auto;
  min-width: 0;
  min-height: 30px;
  padding: 0 0.68rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  box-shadow: none;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.tab:hover,
.tab:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  outline: none;
}

.tab.active {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
  color: var(--selected);
  font-weight: 830;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
}

.tab:active {
  transform: translateY(1px);
}

.pill {
  flex: 0 0 auto;
  max-width: min(240px, 46vw);
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0 0.54rem 0 0.64rem;
  border: 1px solid color-mix(in srgb, #d97706 34%, var(--line));
  border-radius: 999px;
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.11),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: color-mix(in srgb, var(--text) 82%, #d97706);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.pill-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pill-x {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.96rem;
  line-height: 1;
  opacity: 0.72;
  transition:
    background 0.15s ease,
    opacity 0.15s ease,
    color 0.15s ease;
}

.pill-x:hover,
.pill-x:focus-visible {
  background: rgba(217, 119, 6, 0.13);
  color: #d97706;
  opacity: 1;
  outline: none;
}

.tabs-actions {
  position: relative;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.48rem;
}

.tabs-actions.compact {
  gap: 0;
}

.btn,
.icon-btn {
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.btn {
  min-height: 30px;
  padding: 0 0.72rem;
  border-radius: 10px;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.icon-btn {
  position: relative;
  min-width: 32px;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.58rem;
  border-radius: 10px;
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled),
.icon-btn:hover:not(:disabled),
.icon-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active:not(:disabled),
.icon-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled,
.icon-btn:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.btn.danger {
  border-color: color-mix(in srgb, #ef4444 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.1),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: #ef4444;
}

.btn.danger:hover:not(:disabled),
.btn.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.14);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.12),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.badge {
  position: absolute;
  top: -7px;
  right: -7px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border: 2px solid color-mix(in srgb, var(--sidebar-bg) 88%, var(--editor-bg));
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.66rem;
  font-weight: 820;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  box-shadow: 0 4px 10px rgba(239, 68, 68, 0.22);
}

.menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: min(220px, calc(100vw - 28px));
  padding: 0.34rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 18px 44px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(14px) saturate(1.05);
  -webkit-backdrop-filter: blur(14px) saturate(1.05);
  overflow: hidden;
  z-index: 50;
}

.menu-item {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.64rem;
  padding: 0 0.62rem;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 740;
  line-height: 1.25;
  text-align: left;
}

.menu-item:hover:not(:disabled),
.menu-item:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 40%, transparent);
  color: var(--selected);
  outline: none;
}

.menu-item:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.menu-item span:first-child {
  min-width: 0;
  overflow-wrap: break-word;
}

.menu-badge {
  flex: 0 0 auto;
  min-width: 19px;
  height: 19px;
  padding: 0 6px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 820;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.feed-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  overflow: hidden;
}

.feed-body.has-detail {
  grid-template-columns: minmax(320px, 420px) minmax(420px, 1fr);
}

.left-pane {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid transparent;
}

.feed-body.has-detail .left-pane {
  border-right-color: color-mix(in srgb, var(--line) 78%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 24%, transparent)
    );
}

.left-scroll {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.left-scroll::-webkit-scrollbar,
.drawer-body::-webkit-scrollbar {
  width: 8px;
}

.left-scroll::-webkit-scrollbar-thumb,
.drawer-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.detail-pane {
  position: relative;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 92%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 26%, var(--editor-bg))
    );
}

.detail-pane::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.72rem;
  bottom: 0.72rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 42%, transparent);
  opacity: 0.68;
  pointer-events: none;
  z-index: 2;
}

.drawer-mask {
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: flex-end;
  background: rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(12px) saturate(1.04);
  -webkit-backdrop-filter: blur(12px) saturate(1.04);
  z-index: 80;
}

.drawer {
  height: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 6%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    -18px 0 54px rgba(0, 0, 0, 0.22);
  color: var(--text);
}

.detail-drawer {
  width: 100%;
  border-left: 0;
}

.side-drawer {
  width: min(720px, 100%);
}

.drawer-actions {
  flex: 0 0 auto;
  min-height: 50px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.48rem;
  padding: 0.55rem 0.76rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 80%, transparent),
      color-mix(in srgb, var(--editor-bg) 55%, transparent)
    );
}

.drawer-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.confirm-mask {
  position: absolute;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(14px) saturate(1.04);
  -webkit-backdrop-filter: blur(14px) saturate(1.04);
}

.confirm {
  width: min(520px, 100%);
  min-width: 0;
  padding: 1rem;
  border: 1px solid color-mix(in srgb, #ef4444 24%, var(--line));
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, rgba(239, 68, 68, 0.08), transparent 36%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 24px 70px rgba(0, 0, 0, 0.34);
}

.confirm-title {
  color: var(--text);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.confirm-desc {
  margin-top: 0.52rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.confirm-actions {
  margin-top: 0.92rem;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.52rem;
}

@media (max-width: 920px) {
  .feed-body.has-detail {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .tabs {
    min-height: 50px;
    padding: 0.5rem 0.62rem;
    gap: 0.42rem;
  }

  .tab {
    min-height: 29px;
    padding: 0 0.58rem;
  }

  .side-drawer {
    width: 100%;
    border-left: 0;
  }

  .confirm-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .confirm-actions .btn {
    width: 100%;
  }
}

@media (max-width: 520px) {
  .tabs {
    gap: 0.34rem;
  }

  .tabs-left {
    gap: 0.28rem;
  }

  .tab {
    min-height: 28px;
    padding: 0 0.5rem;
    font-size: 0.72rem;
  }

  .pill {
    max-width: 38vw;
    min-height: 26px;
    padding-left: 0.52rem;
  }

  .drawer-actions {
    min-height: 48px;
  }

  .confirm-mask {
    padding: 0.72rem;
  }

  .confirm {
    border-radius: 16px;
  }
}

@media (max-width: 420px) {
  .btn {
    min-height: 32px;
  }

  .confirm-actions {
    grid-template-columns: 1fr;
  }

  .pill {
    max-width: 34vw;
  }
}
</style>
