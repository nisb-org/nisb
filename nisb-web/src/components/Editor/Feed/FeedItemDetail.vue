<template>
  <div class="detail-wrap" :class="`mode-${headerMode}`" ref="wrapRef">
    <div class="detail-top">
      <div class="title-row">
        <span class="h-title" :title="safeTitle">{{ safeTitle }}</span>

        <button
          class="icon-btn"
          type="button"
          @click="emit('close')"
          :title="t('feed.detail.actions.close')"
          :aria-label="t('feed.detail.actions.close')"
        >
          ×
        </button>
      </div>

      <div class="meta-action-row">
        <div class="meta-cluster">
          <span class="author" :title="authorTooltip">
            <img
              v-if="authorAvatar"
              class="av"
              :src="authorAvatar"
              :alt="t('feed.detail.author.avatarAlt')"
            />
            <span v-if="headerMode !== 'minimal'" class="meta-author">{{ authorDisplayText }}</span>
          </span>

          <span v-if="displayTime" class="meta-time" :title="createdAtText">{{ displayTime }}</span>

          <span v-if="deleted && headerMode !== 'minimal'" class="meta-status">
            {{ t("feed.detail.status.deleted") }}
          </span>
        </div>

        <div class="top-actions">
          <button
            v-if="authorId"
            class="btn mini"
            :class="{ 'icon-only': headerMode === 'minimal' }"
            type="button"
            @click="toggleFollow"
            :disabled="followBusy"
            :title="isFollowing ? t('feed.detail.follow.unfollow') : t('feed.detail.follow.follow')"
          >
            <span v-if="headerMode === 'full'">
              {{ followBusy ? t("feed.detail.common.busy") : (isFollowing ? t("feed.detail.follow.unfollow") : t("feed.detail.follow.follow")) }}
            </span>
            <span v-else-if="headerMode === 'compact'">
              {{ followBusy ? t("feed.detail.common.busy") : (isFollowing ? t("feed.detail.follow.compactUnfollow") : t("feed.detail.follow.compactFollow")) }}
            </span>
            <span v-else>{{ isFollowing ? "💔" : "❤️" }}</span>
          </button>

          <button
            class="btn mini"
            :class="{ 'icon-only': headerMode === 'minimal', active: isBookmarked }"
            type="button"
            @click="toggleBookmark"
            :disabled="bookmarkBusy"
            :title="isBookmarked ? t('feed.detail.bookmark.unbookmark') : t('feed.detail.bookmark.bookmark')"
          >
            <span v-if="headerMode === 'full'">
              {{ bookmarkBusy ? t("feed.detail.common.busy") : (isBookmarked ? t("feed.detail.bookmark.unbookmark") : t("feed.detail.bookmark.bookmark")) }}
            </span>
            <span v-else-if="headerMode === 'compact'">
              {{ bookmarkBusy ? t("feed.detail.common.busy") : (isBookmarked ? t("feed.detail.bookmark.compactUnbookmark") : t("feed.detail.bookmark.compactBookmark")) }}
            </span>
            <span v-else>{{ isBookmarked ? "📑" : "🔖" }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="detail-scroll">
      <div v-if="loading" class="state-card loading">{{ t("feed.detail.states.loading") }}</div>
      <div v-else-if="error" class="state-card error">{{ error }}</div>

      <template v-else>
        <article class="reading">
          <div class="reading-inner">
            <LazyMarkdown
              :content="contentMd"
              :chunkSize="400"
              :initialChunks="6"
              :stepChunks="6"
              :autoEagerMaxLines="1200"
              :autoEagerMaxChars="220000"
            />
          </div>
        </article>

        <section class="comments" v-if="props.item?.id">
          <div class="comments-inner">
            <FeedComments :feedId="String(props.item.id)" @changed="onCommentsChanged" />
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"
import LazyMarkdown from "../../LazyMarkdown.vue"
import FeedComments from "./FeedComments.vue"

const props = defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(["close", "comments-changed"])
const { t, locale } = useI18n()
const { callTool } = useMCP()

const wrapRef = ref(null)
const detailWidth = ref(0)

const loading = ref(false)
const error = ref("")
const contentMd = ref("")
const deleted = ref(false)
const cached = ref(false)

const followBusy = ref(false)
const isFollowing = ref(false)

const bookmarkBusy = ref(false)
const isBookmarked = ref(false)

let ro = null
let cleanupRO = null

const safeTitle = computed(() => String(props.item?.title || t("feed.detail.fallbacks.untitled")))

function pickAuthorId(author) {
  if (!author) return ""
  if (typeof author === "string") return author.trim()
  if (typeof author === "object") {
    const v = author.user_id || author.userId || author.id
    return v ? String(v).trim() : ""
  }
  return ""
}

const authorId = computed(() => pickAuthorId(props.item?.author))

const authorDisplayName = computed(() => {
  return String(props.item?.author_display_name || props.item?.author?.display_name || "").trim()
})

const authorLabel = computed(() => {
  const dn = authorDisplayName.value
  return dn ? `${dn} (@${authorId.value})` : (authorId.value || t("feed.detail.fallbacks.unknownAuthor"))
})

const authorAvatar = computed(() => String(props.item?.author_avatar_url || props.item?.author?.avatar_url || "").trim())

const createdAtText = computed(() => {
  return props.item?.created_at || props.item?.createdAt || props.item?.createdat || ""
})

const headerMode = computed(() => {
  const w = detailWidth.value
  if (w === 0) return "full"
  if (w >= 620) return "full"
  if (w >= 430) return "compact"
  return "minimal"
})

const authorDisplayText = computed(() => {
  if (headerMode.value === "full") return authorLabel.value
  return authorDisplayName.value || authorId.value || t("feed.detail.fallbacks.unknownAuthor")
})

const authorTooltip = computed(() => {
  return authorLabel.value
})

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

  if (headerMode.value === "full") return raw
  if (headerMode.value === "compact") return raw.replace(/:\d{2}Z?$/, "")
  return formatRelativeTimeShort(raw)
})

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

async function callToolCompat(candidates) {
  let lastErr = null

  for (const c of candidates) {
    try {
      const res = await callTool(c.name, c.args)
      if (!res || res.success === false) throw new Error(res?.message || t("feed.detail.errors.toolFailed"))
      return res
    } catch (e) {
      lastErr = e
      const msg = String(e?.message || "")
      const retryable =
        msg.toLowerCase().includes("not found") ||
        msg.toLowerCase().includes("missing") ||
        msg.toLowerCase().includes("invalid")
      if (!retryable) throw e
    }
  }

  throw lastErr || new Error(t("feed.detail.errors.allToolCandidatesFailed"))
}

async function load() {
  loading.value = true
  error.value = ""
  deleted.value = false
  cached.value = false
  contentMd.value = ""

  try {
    const feedId = String(props.item?.id || "").trim()
    if (!feedId) throw new Error(t("feed.detail.errors.missingFeedId"))

    const res = await callToolCompat([
      { name: "nisb_feed_fetch_content", args: { feed_id: feedId } },
      { name: "nisb_feed_fetch_content", args: { feedId } },
    ])

    contentMd.value = String(res.content_md || res.contentmd || "")
    deleted.value = !!res.deleted
    cached.value = !!res.cached
  } catch (e) {
    error.value = e?.message || t("common.unknownError")
  } finally {
    loading.value = false
  }
}

async function loadFollowState() {
  if (!authorId.value) return

  try {
    const res = await callToolCompat([{ name: "nisb_feed_following_list", args: {} }])
    const arr = Array.isArray(res.items) ? res.items : []
    isFollowing.value = arr.includes(authorId.value)
  } catch {}
}

async function loadBookmarkState() {
  const feedId = String(props.item?.id || "").trim()
  if (!feedId) return

  try {
    const res = await callToolCompat([{ name: "nisb_feed_list_bookmarks", args: { limit: 200 } }])
    const arr = Array.isArray(res.items) ? res.items : []
    isBookmarked.value = arr.some((x) => String(x?.id || "") === feedId)
  } catch {}
}

async function toggleFollow() {
  if (!authorId.value) return

  followBusy.value = true
  try {
    if (isFollowing.value) {
      await callToolCompat([{ name: "nisb_feed_unfollow", args: { target_user_id: authorId.value } }])
      isFollowing.value = false
    } else {
      await callToolCompat([{ name: "nisb_feed_follow", args: { target_user_id: authorId.value } }])
      isFollowing.value = true
    }

    try {
      await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
    } catch {}
  } catch (e) {
    toast(e?.message || t("feed.detail.toast.followFailed"), "error")
  } finally {
    followBusy.value = false
  }
}

async function toggleBookmark() {
  const feedId = String(props.item?.id || "").trim()
  if (!feedId) return

  bookmarkBusy.value = true
  try {
    const vote_type = isBookmarked.value ? "unbookmark" : "bookmark"
    await callToolCompat([{ name: "nisb_feed_vote", args: { feed_id: feedId, vote_type } }])
    isBookmarked.value = !isBookmarked.value
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))

    try {
      await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
    } catch {}
  } catch (e) {
    toast(e?.message || t("feed.detail.toast.bookmarkFailed"), "error")
  } finally {
    bookmarkBusy.value = false
  }
}

function onCommentsChanged() {
  emit("comments-changed")
}

function setupWidthObserver() {
  const el = wrapRef.value
  if (!el) return () => {}

  const apply = () => {
    detailWidth.value = Math.round(el.getBoundingClientRect().width || 0)
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

watch(
  () => props.item?.id,
  async () => {
    await load()
    await loadFollowState()
    await loadBookmarkState()
  },
  { immediate: true }
)

onMounted(() => {
  cleanupRO = setupWidthObserver()
})

onUnmounted(() => {
  cleanupRO && cleanupRO()
  cleanupRO = null
})
</script>

<style scoped>
.detail-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--text, var(--text-main));
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 6%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 28%, var(--editor-bg))
    );
}

.detail-wrap::after {
  content: "";
  position: absolute;
  inset: 0;
  background: rgba(255, 224, 178, var(--nisb-read-warm-alpha, 0));
  pointer-events: none;
  z-index: 12;
}

.detail-top {
  position: relative;
  z-index: 14;
  flex: 0 0 auto;
  min-width: 0;
  padding: 0.68rem 0.78rem 0.62rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  backdrop-filter: blur(14px) saturate(1.05);
  -webkit-backdrop-filter: blur(14px) saturate(1.05);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.title-row {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 0.58rem;
}

.h-title {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.meta-action-row {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.62rem;
  margin-top: 0.56rem;
}

.meta-cluster {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.46rem;
  overflow: hidden;
}

.author {
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
}

.av {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 999px;
  object-fit: cover;
}

.meta-author {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-time,
.meta-status {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 680;
  line-height: 1.3;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.meta-status {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.46rem;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-weight: 780;
}

.top-actions {
  flex: 0 0 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.42rem;
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
  min-height: 29px;
  padding: 0 0.62rem;
  border-radius: 10px;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.btn.mini {
  min-height: 28px;
  padding: 0 0.56rem;
  font-size: 0.72rem;
}

.btn.icon-only {
  min-width: 30px;
  padding: 0 0.42rem;
  font-size: 0.9rem;
}

.icon-btn {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  font-size: 1.12rem;
  font-weight: 760;
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

.btn.active {
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

.detail-scroll {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.detail-scroll::-webkit-scrollbar {
  width: 8px;
}

.detail-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.state-card {
  width: min(100%, 860px);
  box-sizing: border-box;
  margin: 0.9rem auto;
  padding: 0.82rem 0.9rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 48%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.state-card.error {
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.reading {
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
  padding: clamp(0.72rem, 2vw, 1.16rem) clamp(0.66rem, 2vw, 1.08rem) 1.2rem;
}

.reading-inner {
  width: min(100%, 860px);
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin: 0 auto;
}

.reading :deep(.preview-content) {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin: 0 auto;
  padding-bottom: 1.25rem;
  overflow-wrap: break-word;
  word-break: normal;
}

.reading :deep(.preview-content *) {
  max-width: 100%;
  box-sizing: border-box;
}

.reading :deep(.preview-content p),
.reading :deep(.preview-content li),
.reading :deep(.preview-content blockquote),
.reading :deep(.preview-content td),
.reading :deep(.preview-content th) {
  overflow-wrap: break-word;
  word-break: normal;
}

.reading :deep(.preview-content a),
.reading :deep(.preview-content code),
.reading :deep(.preview-content kbd),
.reading :deep(.preview-content samp) {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.reading :deep(.preview-content pre) {
  max-width: 100%;
  overflow-x: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  border-radius: 12px;
  scrollbar-width: thin;
}

.reading :deep(.preview-content pre code) {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.reading :deep(.preview-content img),
.reading :deep(.preview-content video),
.reading :deep(.preview-content canvas),
.reading :deep(.preview-content svg) {
  max-width: 100%;
  height: auto;
}

.reading :deep(.preview-content table) {
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  scrollbar-width: thin;
}

.reading :deep(.preview-content iframe) {
  width: 100%;
  max-width: 100%;
}

.reading :deep(.preview-content h1),
.reading :deep(.preview-content h2),
.reading :deep(.preview-content h3),
.reading :deep(.preview-content h4),
.reading :deep(.preview-content h5),
.reading :deep(.preview-content h6) {
  overflow-wrap: break-word;
}

.comments {
  min-width: 0;
  border-top: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
}

.comments-inner {
  width: min(100%, 860px);
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin: 0 auto;
  padding: 0 clamp(0.66rem, 2vw, 1.08rem);
}

.mode-compact .detail-top {
  padding: 0.62rem 0.68rem 0.58rem;
}

.mode-compact .h-title {
  font-size: 0.9rem;
}

.mode-compact .meta-action-row {
  gap: 0.5rem;
}

.mode-compact .meta-cluster {
  gap: 0.38rem;
}

.mode-minimal .detail-top {
  padding: 0.58rem 0.62rem;
}

.mode-minimal .title-row {
  gap: 0.46rem;
}

.mode-minimal .h-title {
  font-size: 0.86rem;
  -webkit-line-clamp: 2;
}

.mode-minimal .meta-action-row {
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.36rem;
}

.mode-minimal .meta-cluster {
  flex: 1 1 auto;
  min-width: 0;
  gap: 0.3rem;
  overflow: hidden;
}

.mode-minimal .top-actions {
  flex: 0 0 auto;
  min-width: max-content;
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.mode-minimal .meta-time {
  font-size: 0.7rem;
}

@media (max-width: 720px) {
  .detail-wrap {
    height: 100%;
  }

  .detail-top {
    padding: 0.62rem 0.64rem 0.58rem;
  }

  .meta-action-row {
    flex-wrap: nowrap;
    align-items: center;
    gap: 0.38rem;
  }

  .meta-cluster {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
  }

  .top-actions {
    flex: 0 0 auto;
    min-width: max-content;
    justify-content: flex-end;
    flex-wrap: nowrap;
  }

  .reading {
    padding: 0.74rem 0.64rem 1.05rem;
  }

  .reading-inner,
  .comments-inner,
  .state-card {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .detail-top {
    padding: 0.56rem 0.56rem;
  }

  .icon-btn {
    width: 31px;
    height: 31px;
  }

  .btn {
    min-height: 30px;
  }

  .reading {
    padding: 0.66rem 0.52rem 0.92rem;
  }

  .comments-inner {
    padding: 0 0.52rem;
  }
}
</style>
