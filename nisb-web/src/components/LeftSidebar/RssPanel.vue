<template>
  <div class="rss-panel">
    <div class="head">
      <div class="title-block">
        <div class="title">{{ t('rss.left.title') }}</div>
        <div class="head-meta">
          <span class="summary-chip mono">{{ feeds.length }}</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn" type="button" @click="openGate" :title="t('rss.left.actions.openGateTitle')">
          {{ t('rss.left.actions.openGate') }}
        </button>
        <button class="btn" type="button" @click="refresh(false)" :title="t('rss.left.actions.refreshTitle')">
          {{ t('rss.left.actions.refresh') }}
        </button>
      </div>
    </div>

    <div class="add-card">
      <input
        class="inp"
        v-model="newUrl"
        :placeholder="t('rss.left.addPlaceholder')"
        @keydown.enter.prevent="addFeed"
      />
      <button class="btn primary" type="button" :disabled="!newUrl.trim()" @click="addFeed">
        {{ t('rss.left.add') }}
      </button>
    </div>

    <div class="list">
      <div v-if="loading" class="state-box">
        {{ t('rss.left.loading') }}
      </div>

      <div v-else-if="!feeds.length" class="state-box empty">
        {{ t('rss.left.empty') }}
      </div>

      <button
        v-else
        v-for="f in feeds"
        :key="feedKey(f)"
        class="feed-item"
        :class="{ active: feedIdOf(f) && feedIdOf(f) === currentFeedId }"
        type="button"
        :title="feedUrl(f)"
        :aria-label="feedDisplayName(f)"
        @click="openFeed(f)"
        @contextmenu.prevent="showRssContextMenu($event, f)"
      >
        <span class="feed-accent"></span>

        <span class="feed-content">
          <span class="feed-top">
            <span class="name">{{ feedDisplayName(f) }}</span>
          </span>

          <span v-if="feedUrl(f)" class="url mono" :title="feedUrl(f)">
            {{ feedUrl(f) }}
          </span>

          <span class="tag-row">
            <span v-if="feedTags(f).length" class="tag-wrap">
              <span v-for="tag in feedTags(f)" :key="tag" class="tag-chip">
                {{ tag }}
              </span>
            </span>
            <span v-else class="tag-chip muted">
              {{ t('rss.left.noTags') }}
            </span>
          </span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'

const emit = defineEmits(['show-context-menu'])
const { callTool } = useMCP()
const { t } = useI18n()

const feeds = ref([])
const newUrl = ref('')
const loading = ref(false)
const currentFeedId = ref('')

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function isOk(r) {
  if (!r || typeof r !== 'object') return false
  if (r.success === true) return true
  if (String(r.status || '').toLowerCase() === 'success') return true
  return false
}

function pickArray(r, keys) {
  if (!r || typeof r !== 'object') return []
  for (const k of keys) {
    if (Array.isArray(r[k])) return r[k]
  }
  const d = r.data
  if (d && typeof d === 'object') {
    for (const k of keys) {
      if (Array.isArray(d[k])) return d[k]
    }
  }
  return []
}

function feedIdOf(f) {
  return String(f?.feed_id || f?.feedId || f?.id || '').trim()
}

function feedUrl(f) {
  return String(f?.url || f?.feed_url || f?.feedUrl || '').trim()
}

function feedKey(f) {
  return feedIdOf(f) || feedUrl(f) || feedDisplayName(f)
}

function feedTags(f) {
  if (!Array.isArray(f?.tags)) return []
  return f.tags.map((x) => String(x || '').trim()).filter(Boolean).slice(0, 6)
}

function feedDisplayName(f) {
  return f?.custom_name || f?.customName || f?.title || f?.name || f?.url || t('rss.left.untitledFeed')
}

async function loadFeeds() {
  loading.value = true
  try {
    const r = await callTool('nisb_rss_list_feeds', {})
    feeds.value = pickArray(r, ['feeds', 'items', 'data']) || []
  } finally {
    loading.value = false
  }
}

async function refresh(showToast = false) {
  try {
    await loadFeeds()
    if (showToast) toast(t('rss.left.messages.refreshSuccess'), 'success')
  } catch (e) {
    toast(
      t('rss.left.messages.refreshFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

async function addFeed() {
  const url = newUrl.value.trim()
  if (!url) return
  try {
    const r = await callTool('nisb_rss_add_feed', { url })
    if (isOk(r)) {
      newUrl.value = ''
      await refresh(false)
      toast(t('rss.left.messages.addSuccess'), 'success')
    } else {
      toast(
        t('rss.left.messages.addFailed', {
          error: r?.message || r?.detail || t('rss.left.messages.unknownError')
        }),
        'error'
      )
    }
  } catch (e) {
    toast(
      t('rss.left.messages.addFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

function openFeed(f) {
  const feedId = feedIdOf(f)
  if (!feedId) return
  currentFeedId.value = feedId
  window.dispatchEvent(new CustomEvent('nisb-open-rss', { detail: { feedId } }))
}

function openGate() {
  window.dispatchEvent(new CustomEvent('nisb-open-rss-gate', { detail: { feedId: '', query: '' } }))
}

function showRssContextMenu(e, feed) {
  const feedId = feedIdOf(feed)
  emit('show-context-menu', {
    x: e.clientX,
    y: e.clientY,
    targetType: 'rss',
    targetId: feedId,
    targetName: feedDisplayName(feed),
    targetPath: feedUrl(feed)
  })
}

function onRefreshEvent() {
  refresh(false)
}

function onOpenRssEvent(e) {
  const feedId = String(e?.detail?.feedId || '').trim()
  if (feedId) currentFeedId.value = feedId
}

onMounted(async () => {
  await refresh(false)
  window.addEventListener('nisb-rss-refresh', onRefreshEvent)
  window.addEventListener('nisb-open-rss', onOpenRssEvent)
})

onUnmounted(() => {
  window.removeEventListener('nisb-rss-refresh', onRefreshEvent)
  window.removeEventListener('nisb-open-rss', onOpenRssEvent)
})
</script>

<style scoped>
.rss-panel {
  height: 100%;
  min-height: 0;
  min-width: 0;
  padding: 0.55rem;
  display: flex;
  flex-direction: column;
  gap: 0.58rem;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.head {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.38rem 0.42rem 0.42rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.05);
}

.title-block {
  min-width: 0;
  display: grid;
  gap: 0.28rem;
}

.title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.25;
}

.head-meta,
.actions {
  display: flex;
  align-items: center;
  gap: 0.38rem;
  min-width: 0;
}

.actions {
  flex: 0 0 auto;
  justify-content: flex-end;
}

.summary-chip,
.tag-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 23px;
  box-sizing: border-box;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  max-width: 100%;
}

.summary-chip {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
}

.add-card {
  flex: 0 0 auto;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.46rem;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.inp {
  width: 100%;
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0.48rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.8rem;
  line-height: 1.35;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.inp::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.inp:focus {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.btn {
  min-height: 30px;
  box-sizing: border-box;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 90%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
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
  opacity: 0.55;
  cursor: not-allowed;
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 0.46rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.02rem 0.05rem 0.7rem;
  scrollbar-width: thin;
}

.list::-webkit-scrollbar {
  width: 8px;
}

.list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.state-box {
  margin-top: 0.15rem;
  padding: 0.9rem 0.75rem;
  border: 1px dashed color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.state-box.empty {
  border-style: dashed;
}

.feed-item {
  position: relative;
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: 0.55rem;
  padding: 0.62rem 0.64rem;
  border: 1px solid transparent;
  border-radius: 13px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.feed-item:hover,
.feed-item:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 44%, transparent),
      color-mix(in srgb, var(--editor-bg) 36%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06);
  outline: none;
}

.feed-item.active {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

.feed-accent {
  flex: 0 0 auto;
  width: 3px;
  margin: 0.14rem 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 80%, transparent);
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.feed-item:hover .feed-accent,
.feed-item:focus-visible .feed-accent,
.feed-item.active .feed-accent {
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.feed-content {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.24rem;
}

.feed-top {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.name {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 760;
  line-height: 1.28;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-item:hover .name,
.feed-item:focus-visible .name,
.feed-item.active .name {
  color: var(--selected);
}

.url {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.7rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-row,
.tag-wrap {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.28rem;
}

.tag-chip {
  min-height: 21px;
  padding: 0 0.46rem;
  font-size: 0.68rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 60%, transparent);
}

.feed-item:hover .tag-chip,
.feed-item:focus-visible .tag-chip,
.feed-item.active .tag-chip {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 40%, var(--editor-bg));
}

.muted {
  color: var(--text-secondary);
  opacity: 0.72;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 520px) {
  .rss-panel {
    padding: 0.45rem;
  }

  .head {
    align-items: stretch;
    flex-direction: column;
    gap: 0.45rem;
  }

  .actions {
    width: 100%;
  }

  .actions .btn {
    flex: 1 1 auto;
  }

  .add-card {
    grid-template-columns: 1fr;
  }

  .add-card .btn {
    width: 100%;
  }
}
</style>
