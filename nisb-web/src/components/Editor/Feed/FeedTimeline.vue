<template>
  <div class="timeline">
    <div v-if="loading && items.length === 0" class="state-list" aria-busy="true">
      <div v-for="n in 5" :key="n" class="skeleton-card">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line title"></div>
        <div class="skeleton-line body"></div>
        <div class="skeleton-actions">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>

    <div v-else-if="error && items.length === 0" class="state-card error">
      <div class="state-title">{{ t("feed.timeline.toast.refreshFailed") }}</div>
      <div class="state-desc">{{ error }}</div>
      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.timeline.actions.loading") : t("feed.timeline.actions.loadMore") }}
      </button>
    </div>

    <div v-else-if="!loading && items.length === 0" class="state-card empty">
      <div class="state-title">{{ t("feed.timeline.states.empty") }}</div>
    </div>

    <template v-else>
      <section
        v-for="group in groupedItems"
        :key="group.key"
        class="time-group"
        :class="{ selected: groupHasSelected(group) }"
      >
        <div class="group-head">
          <span class="group-title">{{ group.label }}</span>
          <span class="group-count">{{ group.items.length }}</span>
        </div>

        <FeedItemCard
          v-for="it in group.items"
          :key="it.id"
          :item="it"
          :active="selectedId === String(it.id)"
          :showDelete="mode === 'mine'"
          @open="handleOpen"
          @click-tag="handleTag"
          @delete="handleDelete"
          @voted="handleVoted"
        />
      </section>

      <div v-if="error" class="inline-error">
        <span>{{ error }}</span>
        <button class="btn mini" type="button" @click="refresh" :disabled="loading">
          {{ loading ? t("feed.timeline.actions.loading") : t("feed.timeline.actions.loadMore") }}
        </button>
      </div>
    </template>

    <div class="more-row" v-if="hasMore">
      <button class="btn" type="button" @click="loadMore" :disabled="loadingMore || loading">
        {{ loadingMore ? t("feed.timeline.actions.loading") : t("feed.timeline.actions.loadMore") }}
      </button>
    </div>

    <div v-if="loading && items.length > 0" class="refresh-strip">
      {{ t("feed.timeline.actions.loading") }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"
import FeedItemCard from "./FeedItemCard.vue"

const props = defineProps({
  mode: { type: String, default: "latest" },
  tag: { type: String, default: "" },
  selectedId: { type: String, default: "" },
})

const emit = defineEmits(["open", "select-tag", "delete", "refresh"])

const { t, locale } = useI18n()
const { callTool } = useMCP()

const items = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const cursor = ref(null)
const hasMore = ref(false)
const error = ref("")

let requestSeq = 0

const groupedItems = computed(() => {
  const groups = []
  const byKey = new Map()

  for (const item of items.value) {
    const raw = getItemTime(item)
    const key = getDateKey(raw)
    const label = getDateLabel(raw, key)

    if (!byKey.has(key)) {
      const group = { key, label, items: [] }
      byKey.set(key, group)
      groups.push(group)
    }

    byKey.get(key).items.push(item)
  }

  return groups
})

function getItemTime(item) {
  return item?.created_at || item?.createdAt || item?.createdat || item?.updated_at || item?.updatedAt || ""
}

function getDateKey(raw) {
  if (!raw) return "unknown"

  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return "unknown"

  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

function getDateLabel(raw, key) {
  if (!raw || key === "unknown") return "—"

  try {
    const date = new Date(raw)
    if (Number.isNaN(date.getTime())) return "—"

    return new Intl.DateTimeFormat(locale.value || "en", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date)
  } catch {
    return key
  }
}

function groupHasSelected(group) {
  const selected = String(props.selectedId || "")
  if (!selected) return false
  return group.items.some((item) => String(item?.id || "") === selected)
}

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function normalizeItems(arr) {
  if (!Array.isArray(arr)) return []

  return arr
    .filter((item) => item && typeof item === "object")
    .filter((item) => String(item.id || "").trim())
}

async function fetchPage({ reset } = { reset: true }) {
  const args = { limit: 50, mode: props.mode }

  if (props.mode === "tag_filter") args.tag = props.tag
  if (!reset && cursor.value) args.cursor = cursor.value

  const tool = props.mode === "recommended" ? "nisb_feed_recommend" : "nisb_feed_list"
  const res = await callTool(tool, args)

  if (!res || res.success === false) {
    throw new Error(res?.message || t("feed.timeline.errors.listFailed"))
  }

  const newItems = normalizeItems(res.items)
  const nextCursor = res.next_cursor || null
  const more = !!res.has_more

  if (reset) {
    items.value = newItems
  } else {
    const seen = new Set(items.value.map((x) => String(x.id)))
    const merged = [...items.value]

    for (const it of newItems) {
      const id = String(it.id)
      if (seen.has(id)) continue
      seen.add(id)
      merged.push(it)
    }

    items.value = merged
  }

  cursor.value = nextCursor
  hasMore.value = more
}

async function refresh() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ""

  try {
    cursor.value = null
    hasMore.value = false
    await fetchPage({ reset: true })
  } catch (e) {
    if (seq !== requestSeq) return
    error.value = e?.message || t("feed.timeline.toast.refreshFailed")
    toast(error.value, "error")
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loadingMore.value || loading.value) return

  const seq = ++requestSeq
  loadingMore.value = true
  error.value = ""

  try {
    await fetchPage({ reset: false })
  } catch (e) {
    if (seq !== requestSeq) return
    error.value = e?.message || t("feed.timeline.toast.loadMoreFailed")
    toast(error.value, "error")
  } finally {
    if (seq === requestSeq) loadingMore.value = false
  }
}

function handleOpen(item) {
  emit("open", item)
}

function handleTag(tag) {
  emit("select-tag", tag)
}

function handleDelete(item) {
  emit("delete", item)
}

function handleVoted() {
  emit("refresh")
}

function onFeedRefresh() {
  refresh()
}

watch(
  () => [props.mode, props.tag],
  () => refresh(),
  { immediate: true }
)

onMounted(() => {
  window.addEventListener("nisb-feed-refresh", onFeedRefresh)
})

onUnmounted(() => {
  requestSeq += 1
  window.removeEventListener("nisb-feed-refresh", onFeedRefresh)
})
</script>

<style scoped>
.timeline {
  min-width: 0;
  min-height: 100%;
  box-sizing: border-box;
  padding: 0.78rem 0.76rem 1.28rem;
  color: var(--text, var(--text-main));
}

.time-group {
  position: relative;
  min-width: 0;
  margin-bottom: 0.9rem;
}

.group-head {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.46rem;
  margin: 0 0 0.48rem;
  padding: 0 0.18rem;
}

.group-title {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 820;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-title::before {
  content: "";
  width: 7px;
  height: 7px;
  display: inline-block;
  margin-right: 0.42rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 86%, transparent);
  vertical-align: 0.08em;
}

.time-group.selected .group-title::before {
  background: color-mix(in srgb, var(--selected) 70%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.group-count {
  flex: 0 0 auto;
  min-width: 21px;
  height: 21px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.42rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--sidebar-bg) 36%, transparent);
  color: var(--text-secondary);
  font-size: 0.66rem;
  font-weight: 780;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.state-list {
  display: grid;
  gap: 0.72rem;
}

.skeleton-card {
  width: min(100%, 840px);
  min-width: 0;
  margin: 0 auto;
  padding: 0.82rem 0.88rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-sizing: border-box;
  overflow: hidden;
}

.skeleton-line,
.skeleton-actions span {
  display: block;
  border-radius: 999px;
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--line) 42%, transparent),
      color-mix(in srgb, var(--selected-bg) 30%, transparent),
      color-mix(in srgb, var(--line) 42%, transparent)
    );
  background-size: 220% 100%;
  animation: shimmer 1.3s ease-in-out infinite;
}

.skeleton-line.short {
  width: 36%;
  height: 12px;
  margin-bottom: 0.62rem;
}

.skeleton-line.title {
  width: 78%;
  height: 16px;
  margin-bottom: 0.58rem;
}

.skeleton-line.body {
  width: 92%;
  height: 12px;
  margin-bottom: 0.72rem;
}

.skeleton-actions {
  display: flex;
  gap: 0.38rem;
}

.skeleton-actions span {
  width: 54px;
  height: 24px;
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
  width: min(100%, 840px);
  min-width: 0;
  box-sizing: border-box;
  margin: 0 auto;
  padding: 1rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 16px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 6%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 48%, transparent)
    );
  color: var(--text-secondary);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
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
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 48%, transparent)
    );
}

.state-title {
  color: var(--text, var(--text-main));
  font-size: 0.86rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.state-card.error .state-title {
  color: #ef4444;
}

.state-desc {
  margin-top: 0.44rem;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.state-card .btn {
  margin-top: 0.76rem;
}

.inline-error {
  width: min(100%, 840px);
  min-width: 0;
  margin: 0.1rem auto 0.86rem;
  padding: 0.62rem 0.72rem;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 13px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  box-sizing: border-box;
}

.inline-error span {
  min-width: 0;
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.more-row {
  min-width: 0;
  display: flex;
  justify-content: center;
  padding: 0.78rem 0 0.22rem;
}

.btn {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.74rem;
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

.btn.mini {
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

@media (max-width: 720px) {
  .timeline {
    padding: 0.62rem 0.56rem 1.05rem;
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
  .timeline {
    padding: 0.54rem 0.48rem 0.95rem;
  }

  .group-head {
    margin-bottom: 0.42rem;
  }

  .skeleton-card,
  .state-card {
    border-radius: 14px;
  }

  .more-row .btn {
    width: 100%;
  }
}
</style>
