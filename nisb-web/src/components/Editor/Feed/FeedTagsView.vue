<template>
  <div class="tags-wrap">
    <div class="top">
      <div class="title-stack">
        <div class="title">{{ t("feed.tagsView.title") }}</div>

        <div class="stats-row" v-if="tags.length > 0">
          <span class="stat-chip">{{ tags.length }}</span>
          <span class="stat-chip strong">{{ totalCount }}</span>
        </div>
      </div>

      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.tagsView.actions.loading") : t("feed.tagsView.actions.refresh") }}
      </button>
    </div>

    <div v-if="loading && tags.length === 0" class="state-list" aria-busy="true">
      <div v-for="n in 12" :key="n" class="skeleton-chip" :class="{ wide: n % 3 === 0, short: n % 4 === 0 }"></div>
    </div>

    <div v-else-if="error && tags.length === 0" class="state-card error">
      <div class="state-title">{{ t("feed.tagsView.toast.loadFailed") }}</div>
      <div class="state-desc">{{ error }}</div>
      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.tagsView.actions.loading") : t("feed.tagsView.actions.refresh") }}
      </button>
    </div>

    <div v-else-if="!loading && tags.length === 0" class="state-card empty">
      <div class="state-title">{{ t("feed.tagsView.states.empty") }}</div>
    </div>

    <template v-else>
      <div v-if="error" class="inline-error">
        <span>{{ error }}</span>
        <button class="btn mini" type="button" @click="refresh" :disabled="loading">
          {{ loading ? t("feed.tagsView.actions.loading") : t("feed.tagsView.actions.refresh") }}
        </button>
      </div>

      <div class="cloud" role="list" :aria-label="t('feed.tagsView.title')">
        <button
          v-for="tItem in normalizedTags"
          :key="tItem.tag"
          type="button"
          class="chip"
          :class="{ active: isActive(tItem.tag) }"
          :style="{ '--tag-size': fontSize(tItem.count) + 'px' }"
          :title="tagTitle(tItem)"
          role="listitem"
          @click="selectTag(tItem.tag)"
        >
          <span class="tag-name">#{{ tItem.tag }}</span>
          <span class="cnt">{{ tItem.count }}</span>
        </button>
      </div>
    </template>

    <div v-if="loading && tags.length > 0" class="refresh-strip">
      {{ t("feed.tagsView.actions.loading") }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

const props = defineProps({
  activeTag: { type: String, default: "" },
})

const emit = defineEmits(["select"])

const { t } = useI18n()
const { callTool } = useMCP()

const tags = ref([])
const loading = ref(false)
const error = ref("")

let requestSeq = 0

const normalizedTags = computed(() => {
  return tags.value
    .map((item) => {
      const tag = String(item?.tag || item?.name || item?.id || "").trim()
      const count = Math.max(0, Number(item?.count || item?.items_count || item?.total || 0))
      return { ...item, tag, count }
    })
    .filter((item) => item.tag)
    .sort((a, b) => {
      const byCount = Number(b.count || 0) - Number(a.count || 0)
      if (byCount !== 0) return byCount
      return String(a.tag || "").localeCompare(String(b.tag || ""))
    })
})

const totalCount = computed(() => {
  return normalizedTags.value.reduce((sum, item) => sum + Number(item.count || 0), 0)
})

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function fontSize(c) {
  const n = Number(c || 0)
  if (n >= 60) return 18
  if (n >= 30) return 16
  if (n >= 12) return 14
  return 13
}

function isActive(tag) {
  return String(props.activeTag || "").trim() === String(tag || "").trim()
}

function tagTitle(item) {
  return `#${item.tag} · ${item.count}`
}

function selectTag(tag) {
  const value = String(tag || "").trim()
  if (!value) return
  emit("select", value)
}

async function refresh() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ""

  try {
    const res = await callTool("nisb_feed_get_tags", {})
    if (!res || res.success === false) throw new Error(res?.message || t("feed.tagsView.toast.loadFailed"))

    if (seq !== requestSeq) return
    tags.value = Array.isArray(res.items) ? res.items : []
  } catch (e) {
    if (seq !== requestSeq) return
    error.value = e?.message || t("feed.tagsView.toast.loadFailed")
    toast(error.value, "error")
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

onMounted(() => {
  refresh()
})

onUnmounted(() => {
  requestSeq += 1
})
</script>

<style scoped>
.tags-wrap {
  position: relative;
  height: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.9rem 0.9rem 1.25rem;
  color: var(--text, var(--text-main));
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.tags-wrap::-webkit-scrollbar {
  width: 8px;
}

.tags-wrap::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.top {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin-bottom: 0.78rem;
}

.title-stack {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.36rem;
}

.title {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.stats-row {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.stat-chip {
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

.stat-chip.strong {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 30%, transparent);
  color: var(--selected);
}

.cloud {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  align-content: flex-start;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.chip {
  max-width: 100%;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.26rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: var(--tag-size);
  font-weight: 760;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.chip:hover,
.chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.chip:active {
  transform: translateY(1px);
}

.chip.active {
  border-color: rgba(217, 119, 6, 0.38);
  background:
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.13),
      color-mix(in srgb, var(--editor-bg) 62%, transparent)
    );
  color: #d97706;
  box-shadow:
    0 0 0 2px rgba(217, 119, 6, 0.1),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.tag-name {
  min-width: 0;
  max-width: min(360px, 70vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cnt {
  flex: 0 0 auto;
  min-height: 20px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.4rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: currentColor;
  opacity: 0.84;
  font-size: 0.72em;
  font-weight: 820;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.state-list {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  align-content: flex-start;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.skeleton-chip {
  width: 118px;
  height: 32px;
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

.skeleton-chip.wide {
  width: 158px;
}

.skeleton-chip.short {
  width: 88px;
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
  min-width: 0;
  box-sizing: border-box;
  padding: 0.9rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
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
  margin-bottom: 0.72rem;
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

@media (max-width: 720px) {
  .tags-wrap {
    padding: 0.74rem 0.64rem 1rem;
  }

  .top {
    gap: 0.56rem;
  }

  .tag-name {
    max-width: 58vw;
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
  .tags-wrap {
    padding: 0.64rem 0.52rem 0.9rem;
  }

  .top {
    align-items: stretch;
    flex-direction: column;
  }

  .top > .btn {
    width: 100%;
  }

  .cloud,
  .state-list {
    gap: 0.42rem;
  }

  .chip {
    max-width: 100%;
    min-height: 31px;
    padding: 0.24rem 0.58rem;
  }

  .tag-name {
    max-width: 68vw;
  }

  .skeleton-chip {
    width: 104px;
  }

  .skeleton-chip.wide {
    width: 136px;
  }

  .skeleton-chip.short {
    width: 78px;
  }
}
</style>
