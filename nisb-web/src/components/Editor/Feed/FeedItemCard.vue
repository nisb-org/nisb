<template>
  <div
    ref="cardRef"
    class="card"
    :class="[
      {
        active: props.active,
        unread: isUnread,
        read: readState === 'read',
      },
      `mode-${cardMode}`,
    ]"
    @click="handleCardClick"
  >
    <div class="card-topline">
      <div class="source-wrap">
        <span class="source-dot" aria-hidden="true"></span>
        <span class="source-chip" :title="sourceTooltip">{{ sourceLabel }}</span>
      </div>

      <div class="state-wrap">
        <span v-if="readState" class="state-chip" :class="readState">
          {{ readState === "unread" ? t("feed.itemCard.state.unread") : t("feed.itemCard.state.read") }}
        </span>

        <span v-if="notificationCount > 0" class="state-chip notify">
          {{ t("feed.itemCard.signals.notifications", { count: notificationCount }) }}
        </span>
      </div>
    </div>

    <div class="card-header">
      <h3 class="title" :title="safeTitle">{{ safeTitle }}</h3>
    </div>

    <div class="meta-row">
      <span class="author" :title="authorTooltip">
        <img
          v-if="authorAvatar"
          class="avatar"
          :src="authorAvatar"
          :alt="t('feed.itemCard.author.avatarAlt')"
        />
        <span v-if="cardMode !== 'minimal'" class="author-text">{{ authorDisplayText }}</span>
      </span>

      <span v-if="displayTime" class="time" :title="createdAtText">{{ displayTime }}</span>

      <span v-if="typeof scoreValue !== 'undefined'" class="score" :title="scoreTitle">
        {{ scoreDisplay }}
      </span>
    </div>

    <div class="excerpt" v-if="excerpt">{{ excerpt }}</div>

    <div class="signal-row" v-if="commentCount > 0 || notificationCount > 0">
      <span v-if="commentCount > 0" class="signal-chip comments">
        {{ t("feed.itemCard.signals.comments", { count: commentCount }) }}
      </span>

      <span v-if="notificationCount > 0" class="signal-chip notifications">
        {{ t("feed.itemCard.signals.notifications", { count: notificationCount }) }}
      </span>
    </div>

    <div class="tags-row" v-if="tags.length > 0">
      <span
        v-for="(tag, idx) in visibleTags"
        :key="idx"
        class="tag"
        :title="tag"
        @click.stop="handleTagClick(tag)"
      >
        #{{ tag }}
      </span>

      <span
        v-if="tags.length > visibleTagCount"
        class="tag-more"
        :title="tags.slice(visibleTagCount).join(', ')"
      >
        +{{ tags.length - visibleTagCount }}
      </span>
    </div>

    <div class="actions-row" @click.stop>
      <button
        class="action-btn"
        :class="{ 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="cardMode === 'minimal' ? t('feed.itemCard.vote.like') : ''"
        @click="vote('like')"
      >
        <span v-if="cardMode === 'full'">👍 {{ counts.like || 0 }}</span>
        <span v-else-if="cardMode === 'compact'">👍 {{ counts.like || 0 }}</span>
        <span v-else>👍</span>
      </button>

      <button
        class="action-btn"
        :class="{ bookmarked, 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="cardMode === 'minimal' ? (bookmarked ? t('feed.itemCard.bookmark.unbookmark') : t('feed.itemCard.bookmark.bookmark')) : ''"
        @click="toggleBookmark"
      >
        <span v-if="cardMode === 'full'">⭐ {{ counts.bookmark || 0 }}</span>
        <span v-else-if="cardMode === 'compact'">⭐ {{ counts.bookmark || 0 }}</span>
        <span v-else>⭐</span>
      </button>

      <button
        class="action-btn"
        :class="{ 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="cardMode === 'minimal' ? t('feed.itemCard.vote.boost') : ''"
        @click="vote('boost')"
      >
        <span v-if="cardMode === 'full'">🔄 {{ counts.boost || 0 }}</span>
        <span v-else-if="cardMode === 'compact'">🔄 {{ counts.boost || 0 }}</span>
        <span v-else>🔄</span>
      </button>

      <button
        class="action-btn downvote"
        :class="{ 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="t('feed.itemCard.vote.downvote')"
        @click="vote('downvote')"
      >
        <span v-if="cardMode === 'full'">👎 {{ counts.downvote_24h || 0 }}</span>
        <span v-else-if="cardMode === 'compact'">👎 {{ counts.downvote_24h || 0 }}</span>
        <span v-else>👎</span>
      </button>

      <button
        class="action-btn spam"
        :class="{ 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="t('feed.itemCard.vote.spam')"
        @click="vote('spam')"
      >
        <span v-if="cardMode === 'full'">🚫 {{ counts.spam_7d || 0 }}</span>
        <span v-else-if="cardMode === 'compact'">🚫 {{ counts.spam_7d || 0 }}</span>
        <span v-else>🚫</span>
      </button>

      <button
        v-if="props.showDelete"
        class="action-btn danger"
        :class="{ 'icon-only': cardMode === 'minimal' }"
        type="button"
        :disabled="voting"
        :title="t('feed.itemCard.actions.delete')"
        @click="handleDelete"
      >
        🗑
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

const props = defineProps({
  item: { type: Object, required: true },
  active: { type: Boolean, default: false },
  showDelete: { type: Boolean, default: false },
})

const emit = defineEmits(["open", "click-tag", "delete", "voted"])
const { t, locale } = useI18n()
const { callTool } = useMCP()

const cardRef = ref(null)
const cardWidth = ref(0)
const bookmarked = ref(false)
const voting = ref(false)

let ro = null
let cleanupRO = null

function firstString(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined") continue
    const s = String(value).trim()
    if (s) return s
  }
  return ""
}

function numberFrom(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined" || value === "") continue
    const n = Number(value)
    if (Number.isFinite(n)) return Math.max(0, n)
  }
  return 0
}

function hasOwn(obj, key) {
  return !!obj && Object.prototype.hasOwnProperty.call(obj, key)
}

const safeTitle = computed(() => String(props.item?.title || t("feed.itemCard.fallbacks.untitled")))

const counts = computed(() => props.item?.counts || {})
const scoreValue = computed(() => props.item?.score)

const sourceLabel = computed(() => {
  return firstString(
    props.item?.source_display_name,
    props.item?.source_name,
    props.item?.source_title,
    props.item?.source?.display_name,
    props.item?.source?.name,
    props.item?.source?.title,
    props.item?.source_type,
    props.item?.provider,
    props.item?.source_id
  ) || t("feed.itemCard.fallbacks.unknownSource")
})

const sourceTooltip = computed(() => {
  const sourceType = firstString(props.item?.source_type, props.item?.source?.type)
  const sourceId = firstString(props.item?.source_id, props.item?.source?.id, props.item?.source_ref)
  const parts = [sourceLabel.value]
  if (sourceType && sourceType !== sourceLabel.value) parts.push(sourceType)
  if (sourceId && sourceId !== sourceLabel.value) parts.push(sourceId)
  return parts.join(" · ")
})

const authorId = computed(() => {
  const a = props.item?.author
  if (typeof a === "string") return a.trim()
  if (typeof a === "object") {
    const v = a.user_id || a.userId || a.id
    return v ? String(v).trim() : ""
  }
  return ""
})

const authorDisplayName = computed(() => {
  return String(props.item?.author_display_name || props.item?.author?.display_name || "").trim()
})

const authorLabel = computed(() => {
  const dn = authorDisplayName.value
  return dn ? `${dn} (@${authorId.value})` : (authorId.value || t("feed.itemCard.fallbacks.unknownAuthor"))
})

const authorAvatar = computed(() => {
  return String(props.item?.author_avatar_url || props.item?.author?.avatar_url || "").trim()
})

const createdAtText = computed(() => {
  return props.item?.created_at || props.item?.createdAt || props.item?.createdat || ""
})

const cardMode = computed(() => {
  const w = cardWidth.value
  if (w === 0) return "full"
  if (w >= 520) return "full"
  if (w >= 360) return "compact"
  return "minimal"
})

const excerpt = computed(() => {
  const raw = String(props.item?.excerpt || props.item?.content_excerpt || "").trim()
  const limit = cardMode.value === "full" ? 220 : cardMode.value === "compact" ? 160 : 110
  return raw.length > limit ? raw.slice(0, limit) + "…" : raw
})

const tags = computed(() => {
  const raw = props.item?.tags || []
  return Array.isArray(raw) ? raw.filter(Boolean).map((tag) => String(tag).trim()).filter(Boolean) : []
})

const readState = computed(() => {
  const it = props.item || {}

  if (it.unread === true || it.viewer_unread === true) return "unread"
  if (it.read === false || it.viewer_read === false) return "unread"
  if (hasOwn(it, "read_at") && !it.read_at) return "unread"
  if (hasOwn(it, "viewer_read_at") && !it.viewer_read_at) return "unread"

  if (it.read === true || it.viewer_read === true) return "read"
  if (it.unread === false || it.viewer_unread === false) return "read"
  if (it.read_at || it.viewer_read_at) return "read"

  return ""
})

const isUnread = computed(() => readState.value === "unread")

const commentCount = computed(() => {
  const c = counts.value
  return numberFrom(
    c.comment,
    c.comments,
    c.comment_count,
    c.comments_count,
    props.item?.comment_count,
    props.item?.comments_count,
    props.item?.reply_count,
    props.item?.replies_count
  )
})

const notificationCount = computed(() => {
  const c = counts.value
  return numberFrom(
    c.notification,
    c.notifications,
    c.notification_count,
    c.notifications_count,
    c.unread_notification,
    c.unread_notifications,
    props.item?.notification_count,
    props.item?.notifications_count,
    props.item?.unread_notification_count,
    props.item?.unread_notifications_count
  )
})

function syncBookmarkedFromItem() {
  bookmarked.value = !!(props.item?.bookmarked || props.item?.viewer_bookmarked)
}

watch(
  () => props.item?.id,
  () => syncBookmarkedFromItem(),
  { immediate: true }
)

const authorDisplayText = computed(() => {
  if (cardMode.value === "full") return authorLabel.value
  return authorDisplayName.value || authorId.value || t("feed.itemCard.fallbacks.unknownAuthor")
})

const authorTooltip = computed(() => authorLabel.value)

function formatRelativeTimeShort(raw) {
  try {
    const date = new Date(raw)
    const now = new Date()
    const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000)
    const cutoffs = [60, 3600, 86400, 86400 * 7, 86400 * 30, 86400 * 365, Infinity]
    const units = ["second", "minute", "hour", "day", "week", "month", "year"]
    const unitIndex = cutoffs.findIndex((cutoff) => cutoff > Math.abs(diffSeconds))
    const divisor = unitIndex ? cutoffs[unitIndex - 1] : 1
    const value = Math.round(diffSeconds / divisor)
    const rtf = new Intl.RelativeTimeFormat(locale.value || "en", { numeric: "auto", style: "short" })
    return rtf.format(value, units[unitIndex])
  } catch {
    return raw
  }
}

const displayTime = computed(() => {
  const raw = createdAtText.value
  if (!raw) return ""

  if (cardMode.value === "full") return raw
  if (cardMode.value === "compact") return raw.replace(/:\d{2}Z?$/, "")

  return formatRelativeTimeShort(raw)
})

const scoreTitle = computed(() => {
  const s = scoreValue.value
  if (typeof s === "undefined") return ""
  return t("feed.itemCard.score.title", { score: s })
})

const scoreDisplay = computed(() => {
  const s = scoreValue.value
  if (typeof s === "undefined") return ""

  const n = Number(s)
  if (!Number.isFinite(n)) return String(s)

  if (cardMode.value === "minimal") return n >= 0 ? `↑${n}` : `↓${Math.abs(n)}`
  return t("feed.itemCard.score.inline", { score: n })
})

const visibleTagCount = computed(() => {
  if (cardMode.value === "full") return 5
  if (cardMode.value === "compact") return 3
  return 2
})

const visibleTags = computed(() => tags.value.slice(0, visibleTagCount.value))

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function handleCardClick() {
  emit("open", props.item)
}

function handleTagClick(tag) {
  emit("click-tag", tag)
}

function handleDelete() {
  emit("delete", props.item)
}

async function vote(voteType) {
  if (voting.value) return

  voting.value = true
  try {
    const res = await callTool("nisb_feed_vote", { feed_id: props.item?.id, vote_type: voteType })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.itemCard.toast.voteFailed"))

    toast(t("feed.itemCard.toast.voted"), "success")
    await callTool("nisb_feed_compact", {})
    emit("voted")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    toast(e?.message || t("feed.itemCard.toast.voteFailed"), "error")
  } finally {
    voting.value = false
  }
}

async function toggleBookmark() {
  if (voting.value) return

  const voteType = bookmarked.value ? "unbookmark" : "bookmark"
  voting.value = true

  try {
    const res = await callTool("nisb_feed_vote", { feed_id: props.item?.id, vote_type: voteType })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.itemCard.toast.voteFailed"))

    bookmarked.value = !bookmarked.value
    toast(
      bookmarked.value ? t("feed.itemCard.toast.bookmarked") : t("feed.itemCard.toast.unbookmarked"),
      "success"
    )

    await callTool("nisb_feed_compact", {})
    emit("voted")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    toast(e?.message || t("feed.itemCard.toast.bookmarkFailed"), "error")
  } finally {
    voting.value = false
  }
}

function setupWidthObserver() {
  const el = cardRef.value
  if (!el) return () => {}

  const apply = () => {
    cardWidth.value = Math.round(el.getBoundingClientRect().width || 0)
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
})

onUnmounted(() => {
  cleanupRO && cleanupRO()
  cleanupRO = null
})
</script>

<style scoped>
.card {
  position: relative;
  width: min(100%, 840px);
  min-width: 0;
  margin: 0 auto 0.78rem;
  padding: 0.82rem 0.88rem 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 46%, transparent)
    );
  color: var(--text, var(--text-main));
  cursor: pointer;
  box-sizing: border-box;
  overflow: hidden;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.card::before {
  content: "";
  position: absolute;
  left: 0.52rem;
  top: 0.72rem;
  bottom: 0.72rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 78%, transparent);
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.15s ease,
    background 0.15s ease;
}

.card:hover {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 56%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.06);
}

.card:hover::before {
  opacity: 0.55;
  background: color-mix(in srgb, var(--selected) 44%, transparent);
}

.card.active {
  border-color: color-mix(in srgb, var(--selected) 52%, var(--line));
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 12%, transparent), transparent 36%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 14px 30px rgba(0, 0, 0, 0.08);
}

.card.active::before {
  opacity: 1;
  background: color-mix(in srgb, var(--selected) 76%, transparent);
}

.card.unread:not(.active)::before {
  opacity: 0.85;
  background: #d97706;
}

.card-topline {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  margin-bottom: 0.52rem;
  padding-left: 0.34rem;
}

.source-wrap {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
}

.source-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 52%, var(--line));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.source-chip {
  min-width: 0;
  max-width: min(360px, 52vw);
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-wrap {
  flex: 0 0 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.34rem;
}

.state-chip,
.signal-chip {
  min-width: 0;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.46rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.69rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.state-chip.unread {
  border-color: rgba(217, 119, 6, 0.32);
  background: rgba(217, 119, 6, 0.1);
  color: #d97706;
  font-weight: 830;
}

.state-chip.read {
  opacity: 0.82;
}

.state-chip.notify,
.signal-chip.notifications {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.card-header {
  min-width: 0;
  margin-bottom: 0.48rem;
  padding-left: 0.34rem;
}

.title {
  min-width: 0;
  margin: 0;
  color: var(--text, var(--text-main));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.34;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.meta-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.46rem;
  margin-bottom: 0.62rem;
  padding-left: 0.34rem;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.35;
  overflow: hidden;
}

.author {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  flex: 1 1 auto;
}

.avatar {
  flex: 0 0 auto;
  width: 1.18rem;
  height: 1.18rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  object-fit: cover;
}

.author-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time {
  flex: 0 0 auto;
  white-space: nowrap;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.score {
  flex: 0 0 auto;
  color: var(--selected);
  font-weight: 820;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.excerpt {
  min-width: 0;
  margin-bottom: 0.66rem;
  padding-left: 0.34rem;
  color: color-mix(in srgb, var(--text, var(--text-main)) 88%, var(--text-secondary));
  font-size: 0.82rem;
  line-height: 1.5;
  opacity: 0.96;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.signal-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  flex-wrap: wrap;
  margin-bottom: 0.62rem;
  padding-left: 0.34rem;
}

.signal-chip.comments {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 30%, transparent);
  color: var(--selected);
}

.tags-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  flex-wrap: wrap;
  margin-bottom: 0.7rem;
  padding-left: 0.34rem;
  overflow: hidden;
}

.tag,
.tag-more {
  min-width: 0;
  max-width: 100%;
  min-height: 23px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.tag {
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.tag:hover,
.tag:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
  outline: none;
}

.tag-more {
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  background: color-mix(in srgb, var(--sidebar-bg) 44%, transparent);
  color: var(--text-secondary);
  cursor: help;
}

.actions-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding-left: 0.34rem;
  overflow: hidden;
}

.action-btn {
  flex: 0 0 auto;
  min-height: 29px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.34rem;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
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

.action-btn:hover:not(:disabled),
.action-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.action-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.action-btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.action-btn.bookmarked {
  border-color: rgba(217, 119, 6, 0.38);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.12),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: #d97706;
  font-weight: 830;
}

.action-btn.icon-only {
  min-width: 30px;
  padding: 0 0.5rem;
  font-size: 0.9rem;
}

.action-btn.downvote:hover:not(:disabled),
.action-btn.downvote:focus-visible:not(:disabled) {
  border-color: rgba(217, 119, 6, 0.48);
  background: rgba(217, 119, 6, 0.1);
  color: #d97706;
  box-shadow:
    0 0 0 2px rgba(217, 119, 6, 0.1),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.action-btn.spam:hover:not(:disabled),
.action-btn.spam:focus-visible:not(:disabled),
.action-btn.danger:hover:not(:disabled),
.action-btn.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.52);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.card.mode-compact {
  padding: 0.74rem 0.72rem 0.72rem;
}

.card.mode-compact .source-chip {
  max-width: 44vw;
}

.card.mode-compact .title {
  font-size: 0.88rem;
}

.card.mode-compact .excerpt {
  font-size: 0.79rem;
  -webkit-line-clamp: 2;
}

.card.mode-minimal {
  padding: 0.68rem 0.64rem;
  border-radius: 13px;
}

.card.mode-minimal::before {
  left: 0.38rem;
  top: 0.62rem;
  bottom: 0.62rem;
}

.card.mode-minimal .card-topline {
  gap: 0.36rem;
  margin-bottom: 0.42rem;
  padding-left: 0.28rem;
}

.card.mode-minimal .source-chip {
  max-width: 50vw;
  font-size: 0.68rem;
}

.card.mode-minimal .state-chip.notify {
  display: none;
}

.card.mode-minimal .card-header,
.card.mode-minimal .meta-row,
.card.mode-minimal .excerpt,
.card.mode-minimal .signal-row,
.card.mode-minimal .tags-row,
.card.mode-minimal .actions-row {
  padding-left: 0.28rem;
}

.card.mode-minimal .title {
  font-size: 0.84rem;
  -webkit-line-clamp: 2;
}

.card.mode-minimal .meta-row {
  gap: 0.36rem;
  margin-bottom: 0.5rem;
  font-size: 0.7rem;
}

.card.mode-minimal .excerpt {
  font-size: 0.76rem;
  -webkit-line-clamp: 2;
}

.card.mode-minimal .tag,
.card.mode-minimal .tag-more,
.card.mode-minimal .signal-chip {
  min-height: 22px;
  font-size: 0.66rem;
  padding: 0 0.42rem;
}

@media (max-width: 720px) {
  .card {
    width: 100%;
    margin-bottom: 0.68rem;
    padding: 0.74rem 0.72rem 0.72rem;
    border-radius: 14px;
  }

  .card-topline {
    align-items: flex-start;
  }

  .state-wrap {
    max-width: 42%;
    flex-wrap: wrap;
  }

  .meta-row {
    flex-wrap: wrap;
    overflow: visible;
  }

  .author {
    flex: 1 1 100%;
  }

  .time,
  .score {
    flex: 0 0 auto;
  }

  .actions-row {
    gap: 0.34rem;
  }
}

@media (max-width: 420px) {
  .card {
    padding: 0.66rem 0.62rem;
    border-radius: 13px;
  }

  .card-topline {
    flex-wrap: wrap;
  }

  .state-wrap {
    max-width: 100%;
    justify-content: flex-start;
  }

  .source-chip {
    max-width: 72vw;
  }

  .action-btn {
    min-height: 31px;
  }
}
</style>
