<template>
  <div ref="wrapRef" class="n-wrap" :class="`mode-${notifMode}`">
    <div class="n-top">
      <div class="title-stack">
        <div class="n-title">{{ t("feed.notifications.title") }}</div>

        <div class="n-states">
          <span v-if="unreadCount > 0" class="state-chip unread">{{ unreadCount }}</span>
          <span v-else class="state-chip read">{{ t("feed.notifications.actions.read") }}</span>
          <span v-if="items.length > 0" class="state-chip count">{{ items.length }}</span>
        </div>
      </div>

      <div class="n-top-actions">
        <button
          class="btn"
          type="button"
          @click="markAllRead"
          :disabled="loading || allReadBusy || unreadCount <= 0"
        >
          {{ allReadBusy ? t("feed.notifications.actions.loading") : compactLabel("markAllRead") }}
        </button>

        <button class="btn" type="button" @click="refresh" :disabled="loading || allReadBusy">
          {{ compactLabel("refresh") }}
        </button>
      </div>
    </div>

    <div v-if="loading && items.length === 0" class="state-list" aria-busy="true">
      <div v-for="n in 5" :key="n" class="skeleton-card">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line title"></div>
        <div class="skeleton-line body"></div>
      </div>
    </div>

    <div v-else-if="error && items.length === 0" class="state-card error">
      <div class="state-title">{{ t("feed.notifications.toast.loadFailed") }}</div>
      <div class="state-desc">{{ error }}</div>
      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.notifications.actions.loading") : t("feed.notifications.actions.refresh") }}
      </button>
    </div>

    <div v-else-if="!loading && items.length === 0" class="state-card empty">
      <div class="state-title">{{ t("feed.notifications.states.empty") }}</div>
    </div>

    <div v-else class="n-list">
      <div v-if="error" class="inline-error">
        <span>{{ error }}</span>
        <button class="btn small" type="button" @click="refresh" :disabled="loading">
          {{ loading ? t("feed.notifications.actions.loading") : t("feed.notifications.actions.refresh") }}
        </button>
      </div>

      <div
        v-for="it in items"
        :key="it.id"
        class="n-item"
        :class="{ unread: !isRead(it), read: isRead(it), busy: busyIds.has(String(it.id || '')) }"
      >
        <div class="n-main">
          <div class="n-meta">
            <span class="actor" :title="actorLabel(it)">
              <img
                v-if="actorAvatar(it)"
                class="av"
                :src="actorAvatar(it)"
                :alt="t('feed.notifications.actor.avatarAlt')"
              />
              <span v-if="notifMode !== 'minimal'" class="u">{{ actorDisplayText(it) }}</span>
            </span>

            <span class="tp" :title="typeLabel(it)">{{ typeLabel(it) }}</span>

            <span v-if="sourceLabel(it) && notifMode !== 'minimal'" class="source-chip" :title="sourceTooltip(it)">
              {{ sourceLabel(it) }}
            </span>

            <span v-if="notifMode !== 'minimal'" class="time-chip" :title="createdAt(it)">
              {{ displayTime(createdAt(it)) }}
            </span>

            <span class="read-chip" :class="{ unread: !isRead(it), read: isRead(it) }">
              {{ isRead(it) ? t("feed.notifications.actions.read") : t("feed.notifications.actions.markRead") }}
            </span>
          </div>

          <div class="n-ref" v-if="feedId(it)" :title="t('feed.notifications.ref.feed', { id: feedId(it) })">
            {{ t("feed.notifications.ref.feed", { id: feedId(it) }) }}
          </div>
        </div>

        <div class="n-actions">
          <button class="btn small" type="button" @click="markRead(it)" :disabled="isRead(it) || busyIds.has(String(it.id || ''))">
            {{
              isRead(it)
                ? (notifMode === "minimal" ? "✓" : t("feed.notifications.actions.read"))
                : (notifMode === "minimal" ? "⭕" : t("feed.notifications.actions.markRead"))
            }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading && items.length > 0" class="refresh-strip">
      {{ t("feed.notifications.actions.loading") }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

const emit = defineEmits(["unread"])
const { t } = useI18n()
const { callTool } = useMCP()

const wrapRef = ref(null)
const panelWidth = ref(0)

let ro = null
let cleanupRO = null
let requestSeq = 0

const items = ref([])
const loading = ref(false)
const allReadBusy = ref(false)
const error = ref("")
const busyIds = ref(new Set())
const unreadCount = ref(0)

const notifMode = computed(() => {
  const w = panelWidth.value
  if (w === 0) return "full"
  if (w >= 520) return "full"
  if (w >= 360) return "compact"
  return "minimal"
})

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function firstString(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined") continue
    const s = String(value).trim()
    if (s) return s
  }
  return ""
}

function compactLabel(kind) {
  if (kind === "markAllRead") {
    return notifMode.value === "minimal"
      ? t("feed.notifications.actions.markAllReadCompact")
      : t("feed.notifications.actions.markAllRead")
  }

  if (notifMode.value === "minimal") return t("feed.notifications.actions.refreshCompact")
  return loading.value ? t("feed.notifications.actions.loading") : t("feed.notifications.actions.refresh")
}

function actorAvatar(it) {
  return firstString(it?.actor_avatar_url, it?.actor?.avatar_url)
}

function actorLabel(it) {
  const uid = firstString(it?.actor_user_id, it?.actor?.user_id, it?.actor?.userId, it?.actor?.id)
  const dn = firstString(it?.actor_display_name, it?.actor?.display_name)
  const finalUid = uid || t("feed.notifications.actor.unknown")
  return dn ? `${dn} (@${finalUid})` : finalUid
}

function actorDisplayText(it) {
  if (notifMode.value === "full") return actorLabel(it)

  return (
    firstString(it?.actor_display_name, it?.actor?.display_name) ||
    firstString(it?.actor_user_id, it?.actor?.user_id, it?.actor?.userId, it?.actor?.id) ||
    t("feed.notifications.actor.unknown")
  )
}

function typeLabel(it) {
  return firstString(it?.type, it?.event_type, it?.eventName, it?.kind)
}

function sourceLabel(it) {
  return firstString(
    it?.source_display_name,
    it?.source_name,
    it?.source?.display_name,
    it?.source?.name,
    it?.source_type,
    it?.provider,
    it?.origin
  )
}

function sourceTooltip(it) {
  const label = sourceLabel(it)
  const sourceType = firstString(it?.source_type, it?.source?.type)
  const sourceId = firstString(it?.source_id, it?.source?.id, it?.source_ref)
  const parts = [label]

  if (sourceType && sourceType !== label) parts.push(sourceType)
  if (sourceId && sourceId !== label) parts.push(sourceId)

  return parts.filter(Boolean).join(" · ")
}

function createdAt(it) {
  return firstString(it?.created_at, it?.createdAt, it?.createdat)
}

function feedId(it) {
  return firstString(it?.feed_id, it?.feedId, it?.target_feed_id, it?.targetFeedId)
}

function isRead(it) {
  if (it?.read === true || it?.acknowledged === true || it?.ack === true) return true
  if (it?.read_at || it?.readAt || it?.acknowledged_at || it?.acknowledgedAt) return true
  return false
}

function normalizeItems(arr) {
  if (!Array.isArray(arr)) return []
  return arr.filter((it) => it && typeof it === "object").filter((it) => firstString(it.id))
}

function setBusy(id, busy) {
  const next = new Set(busyIds.value)
  if (busy) next.add(id)
  else next.delete(id)
  busyIds.value = next
}

function displayTime(raw) {
  if (!raw) return ""

  if (notifMode.value === "full") return raw
  if (notifMode.value === "compact") return raw.replace(/:\d{2}Z?$/, "")

  try {
    const date = new Date(raw)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.max(0, Math.floor(diffMs / 60000))
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 60) return t("feed.notifications.time.minute", { count: diffMins })
    if (diffHours < 24) return t("feed.notifications.time.hour", { count: diffHours })
    if (diffDays < 7) return t("feed.notifications.time.day", { count: diffDays })
    return t("feed.notifications.time.week", { count: Math.floor(diffDays / 7) })
  } catch {
    return raw
  }
}

async function refresh() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ""

  try {
    const res = await callTool("nisb_feed_notifications", { limit: 80 })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.notifications.toast.loadFailed"))

    if (seq !== requestSeq) return

    items.value = normalizeItems(res.items)
    unreadCount.value = Number(res.unread_count || items.value.filter((it) => !isRead(it)).length || 0)
    emit("unread", unreadCount.value)
  } catch (e) {
    if (seq !== requestSeq) return
    error.value = e?.message || t("feed.notifications.toast.loadFailed")
    toast(error.value, "error")
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function markRead(it) {
  const id = firstString(it?.id)
  if (!id || isRead(it) || busyIds.value.has(id)) return

  setBusy(id, true)

  try {
    const res = await callTool("nisb_feed_mark_read", { notification_id: id })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.notifications.toast.markReadFailed"))
    await refresh()
  } catch (e) {
    toast(e?.message || t("feed.notifications.toast.markReadFailed"), "error")
  } finally {
    setBusy(id, false)
  }
}

async function markAllRead() {
  if (allReadBusy.value) return

  allReadBusy.value = true

  try {
    const res = await callTool("nisb_feed_mark_all_read", {})
    if (!res || res.success === false) throw new Error(res?.message || t("feed.notifications.toast.markAllReadFailed"))
    await refresh()
  } catch (e) {
    toast(e?.message || t("feed.notifications.toast.markAllReadFailed"), "error")
  } finally {
    allReadBusy.value = false
  }
}

function setupWidthObserver() {
  const el = wrapRef.value
  if (!el) return () => {}

  const apply = () => {
    panelWidth.value = Math.round(el.getBoundingClientRect().width || 0)
  }

  apply()

  if (typeof ResizeObserver === "undefined") return () => {}

  ro = new ResizeObserver(() => apply())
  ro.observe(el)

  return () => {
    try {
      ro && ro.disconnect()
    } catch {}
    ro = null
  }
}

onMounted(() => {
  cleanupRO = setupWidthObserver()
  refresh()
})

onUnmounted(() => {
  requestSeq += 1

  cleanupRO && cleanupRO()
  cleanupRO = null
})

defineExpose({ refresh, markAllRead })
</script>

<style scoped>
.n-wrap {
  position: relative;
  height: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.9rem;
  color: var(--text, var(--text-main));
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.n-wrap::-webkit-scrollbar {
  width: 8px;
}

.n-wrap::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.n-top {
  position: sticky;
  top: -0.9rem;
  z-index: 5;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin: -0.9rem -0.9rem 0.78rem;
  padding: 0.78rem 0.9rem 0.68rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 64%, transparent)
    );
  backdrop-filter: blur(14px) saturate(1.05);
  -webkit-backdrop-filter: blur(14px) saturate(1.05);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.title-stack {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.38rem;
}

.n-title {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.n-states {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.state-chip {
  min-width: 0;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.state-chip.unread {
  border-color: rgba(217, 119, 6, 0.32);
  background: rgba(217, 119, 6, 0.1);
  color: #d97706;
  font-weight: 830;
}

.state-chip.read {
  border-color: color-mix(in srgb, #16a34a 26%, var(--line));
  background: rgba(22, 163, 74, 0.09);
  color: #16a34a;
}

.n-top-actions {
  flex: 0 0 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.46rem;
  flex-wrap: wrap;
}

.n-list {
  min-width: 0;
  display: grid;
  gap: 0.72rem;
}

.n-item {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.72rem;
  box-sizing: border-box;
  padding: 0.76rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    opacity 0.15s ease,
    box-shadow 0.15s ease;
}

.n-item.unread {
  border-color: rgba(217, 119, 6, 0.36);
  background:
    radial-gradient(circle at 0% 0%, rgba(217, 119, 6, 0.11), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 46%, transparent)
    );
}

.n-item.read {
  opacity: 0.86;
}

.n-item.busy {
  opacity: 0.68;
}

.n-main {
  min-width: 0;
}

.n-meta {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.35;
}

.actor {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.34rem;
  flex: 0 1 auto;
}

.av {
  flex: 0 0 auto;
  width: 1.2rem;
  height: 1.2rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  object-fit: cover;
}

.u {
  min-width: 0;
  max-width: min(260px, 42vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 760;
}

.tp,
.source-chip,
.time-chip,
.read-chip {
  min-width: 0;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.46rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.tp {
  max-width: min(240px, 46vw);
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.source-chip {
  max-width: min(220px, 40vw);
  overflow: hidden;
  text-overflow: ellipsis;
}

.time-chip {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
}

.read-chip.unread {
  border-color: rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
}

.read-chip.read {
  border-color: color-mix(in srgb, #16a34a 24%, var(--line));
  background: rgba(22, 163, 74, 0.08);
  color: #16a34a;
}

.n-ref {
  min-width: 0;
  margin-top: 0.54rem;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 680;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.n-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
}

.btn {
  flex: 0 0 auto;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.btn.small {
  min-height: 28px;
  padding: 0 0.58rem;
  font-size: 0.72rem;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.state-list {
  display: grid;
  gap: 0.72rem;
}

.skeleton-card,
.state-card {
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.skeleton-card {
  padding: 0.78rem;
}

.skeleton-line {
  display: block;
  height: 12px;
  margin-top: 0.58rem;
  border-radius: 999px;
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--line) 42%, transparent),
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--line) 42%, transparent)
    );
  background-size: 220% 100%;
  animation: shimmer 1.3s ease-in-out infinite;
}

.skeleton-line:first-child {
  margin-top: 0;
}

.skeleton-line.short {
  width: 38%;
}

.skeleton-line.title {
  width: 72%;
}

.skeleton-line.body {
  width: 88%;
}

@keyframes shimmer {
  0% {
    background-position: 120% 0;
  }

  100% {
    background-position: -120% 0;
  }
}

.state-card {
  padding: 0.9rem;
  color: var(--text-secondary);
}

.state-card.empty {
  text-align: center;
}

.state-card.error {
  border-color: rgba(239, 68, 68, 0.28);
  background:
    radial-gradient(circle at 0% 0%, rgba(239, 68, 68, 0.08), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.state-title {
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.state-card.error .state-title {
  color: #ef4444;
}

.state-desc {
  margin-top: 0.42rem;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.state-card .btn {
  margin-top: 0.72rem;
}

.inline-error {
  min-width: 0;
  padding: 0.58rem 0.66rem;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  box-sizing: border-box;
}

.inline-error span {
  min-width: 0;
  font-size: 0.74rem;
  font-weight: 720;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.refresh-strip {
  position: sticky;
  bottom: 0.64rem;
  z-index: 4;
  width: fit-content;
  max-width: calc(100% - 1rem);
  margin: 0.74rem auto 0;
  padding: 0.38rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 46%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 12px 28px rgba(0, 0, 0, 0.14);
  backdrop-filter: blur(12px) saturate(1.04);
  -webkit-backdrop-filter: blur(12px) saturate(1.04);
}

.mode-compact .n-item {
  grid-template-columns: minmax(0, 1fr);
}

.mode-compact .n-actions {
  justify-content: flex-start;
}

.mode-compact .u {
  max-width: min(220px, 48vw);
}

.mode-minimal .n-top {
  flex-direction: column;
  align-items: stretch;
}

.mode-minimal .n-top-actions {
  width: 100%;
  justify-content: stretch;
}

.mode-minimal .n-top-actions .btn {
  flex: 1 1 0;
}

.mode-minimal .n-item {
  grid-template-columns: minmax(0, 1fr);
  gap: 0.56rem;
  padding: 0.66rem;
  border-radius: 14px;
}

.mode-minimal .n-actions {
  justify-content: flex-start;
}

.mode-minimal .tp,
.mode-minimal .read-chip {
  max-width: 100%;
}

@media (max-width: 720px) {
  .n-wrap {
    padding: 0.74rem 0.64rem;
  }

  .n-top {
    top: -0.74rem;
    margin: -0.74rem -0.64rem 0.68rem;
    padding: 0.68rem 0.64rem 0.62rem;
  }

  .n-item {
    grid-template-columns: minmax(0, 1fr);
  }

  .n-actions {
    justify-content: flex-start;
  }

  .inline-error {
    align-items: stretch;
    flex-direction: column;
  }

  .inline-error .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .n-wrap {
    padding: 0.64rem 0.52rem;
  }

  .n-top {
    top: -0.64rem;
    margin: -0.64rem -0.52rem 0.62rem;
    padding: 0.62rem 0.52rem 0.58rem;
  }

  .n-top {
    flex-direction: column;
    align-items: stretch;
  }

  .n-top-actions {
    width: 100%;
  }

  .n-top-actions .btn {
    flex: 1 1 0;
  }

  .n-item {
    padding: 0.62rem;
  }

  .btn {
    min-height: 31px;
  }
}
</style>
