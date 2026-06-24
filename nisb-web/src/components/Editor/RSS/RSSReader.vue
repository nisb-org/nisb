<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/RSS/RSSReader.vue -->
<template>
  <div class="rss_reader">
    <div class="topbar">
      <button class="btn ghost" type="button" @click="$emit('back')">
        {{ t('rss.center.reader.topbar.back') }}
      </button>

      <div class="topbar-title-block">
        <div class="title">{{ t('rss.center.reader.topbar.title') }}</div>
        <div class="topbar-meta">
          <span class="meta-chip mono">{{ filtered_feeds.length }}</span>
          <span class="meta-chip mono">{{ items.length }}</span>
        </div>
      </div>

      <div class="topbar-actions">
        <button
          class="btn active"
          type="button"
          :disabled="!feed_id || !article_id"
          @click="toggle_star"
          :title="current_starred ? t('rss.center.reader.topbar.unstarTitle') : t('rss.center.reader.topbar.starTitle')"
        >
          {{ current_starred ? t('rss.center.reader.topbar.starred') : t('rss.center.reader.topbar.star') }}
        </button>

        <button
          class="btn active"
          type="button"
          :disabled="!feed_id || !article_id"
          @click="toggle_archive"
          :title="current_archived ? t('rss.center.reader.topbar.unarchiveTitle') : t('rss.center.reader.topbar.archiveTitle')"
        >
          {{ current_archived ? t('rss.center.reader.topbar.archived') : t('rss.center.reader.topbar.archive') }}
        </button>

        <button class="btn" type="button" @click="fetch_now" :disabled="!feed_id">
          {{ t('rss.center.reader.topbar.fetch') }}
        </button>
      </div>
    </div>

    <div class="body">
      <aside class="left">
        <section class="control-card">
          <div class="section_title">{{ t('rss.center.reader.sections.tags') }}</div>
          <select class="sel" v-model="selected_tag" @change="on_tag_changed">
            <option value="">{{ t('rss.center.reader.selects.allTags') }}</option>
            <option v-for="tItem in tags" :key="tItem.tag" :value="tItem.tag">
              {{ tItem.tag }} ({{ tItem.count }})
            </option>
          </select>
        </section>

        <section class="control-card">
          <div class="section_title">{{ t('rss.center.reader.sections.feeds') }}</div>
          <select class="sel" v-model="feed_id" @change="on_feed_changed">
            <option value="">{{ t('rss.center.reader.selects.chooseFeed') }}</option>
            <option
              v-for="f in filtered_feeds"
              :key="feed_key(f)"
              :value="feed_id_of(f)"
            >
              {{ feed_display_name(f) }}
            </option>
          </select>
        </section>

        <section class="articles-card">
          <div class="articles-head">
            <div class="section_title">{{ t('rss.center.reader.sections.articles') }}</div>
            <span class="meta-chip mono">{{ items.length }}</span>
          </div>

          <div class="list">
            <div v-if="feed_id && !items.length" class="state-box">
              {{ t('rss.center.reader.states.selectArticle') }}
            </div>

            <button
              v-for="it in items"
              :key="article_key(it)"
              class="row"
              type="button"
              :class="{ active: article_id_of(it) === article_id }"
              @click="open_article(article_id_of(it))"
              :title="article_url(it)"
            >
              <span class="row-accent"></span>

              <span class="row-main">
                <span class="t">{{ it.title || t('rss.center.reader.fallbacks.untitledArticle') }}</span>
                <span class="s">{{ article_time(it) }}</span>

                <span class="badges">
                  <span v-if="it.starred" class="badge">★</span>
                  <span v-if="it.archived" class="badge">🗄</span>
                  <span v-if="it.read" class="badge muted">{{ t('rss.center.reader.badges.read') }}</span>
                </span>
              </span>
            </button>
          </div>
        </section>
      </aside>

      <main class="right">
        <div v-if="loading" class="empty-state">
          {{ t('rss.center.reader.states.loading') }}
        </div>

        <div v-else-if="!content_md" class="empty-state">
          {{ t('rss.center.reader.states.selectArticle') }}
        </div>

        <article v-else class="article-shell">
          <LazyMarkdown :content="content_md" :chunk-size="1000" :initial-chunks="2" :step-chunks="2" />
        </article>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'
import LazyMarkdown from '../../LazyMarkdown.vue'

const props = defineProps({ initialFeedId: { type: String, default: '' } })
defineEmits(['back'])

const { t } = useI18n()
const { callTool } = useMCP()

const LS_DELETED_URLS = 'nisb_rss_deleted_urls'
const PENDING_KEY = '__nisb_pending_rss_open_article'

const feeds = ref([])
const tags = ref([])
const selected_tag = ref('')

const feed_id = ref(props.initialFeedId || '')
const items = ref([])
const article_id = ref('')
const content_md = ref('')
const loading = ref(false)

const deleted_urls = ref(new Set())

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function is_ok(r) {
  if (!r || typeof r !== 'object') return false
  if (r.success === true) return true
  if (String(r.status || '').toLowerCase() === 'success') return true
  return false
}

function pick_array(r, keys) {
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

function feed_id_of(f) {
  return String(f?.feed_id || f?.feedId || f?.id || '').trim()
}

function feed_url(f) {
  return String(f?.url || f?.feed_url || f?.feedUrl || '').trim()
}

function feed_display_name(f) {
  return f?.custom_name || f?.customName || f?.title || f?.name || f?.url || t('rss.center.reader.fallbacks.untitledFeed')
}

function feed_key(f) {
  return feed_id_of(f) || feed_url(f) || feed_display_name(f)
}

function article_id_of(it) {
  return String(it?.article_id || it?.articleId || it?.articleid || it?.id || '').trim()
}

function article_url(it) {
  return String(it?.link || it?.url || '').trim()
}

function article_key(it) {
  return article_id_of(it) || article_url(it) || String(it?.title || '')
}

function article_time(it) {
  return String(it?.published_at || it?.publishedAt || it?.ts || it?.fetched_at || it?.fetchedAt || '').slice(0, 19)
}

function set_local_flag(aid, patch) {
  const idx = items.value.findIndex((x) => article_id_of(x) === aid)
  if (idx < 0) return
  items.value[idx] = { ...items.value[idx], ...patch }
}

function load_deleted_urls() {
  try {
    const raw = localStorage.getItem(LS_DELETED_URLS)
    const arr = raw ? JSON.parse(raw) : []
    deleted_urls.value = new Set(Array.isArray(arr) ? arr : [])
  } catch {
    deleted_urls.value = new Set()
  }
}

function consume_pending_open() {
  try {
    const p = window[PENDING_KEY]
    if (!p || typeof p !== 'object') return null
    const fid = String(p.feed_id || '').trim()
    const aid = String(p.article_id || '').trim()
    if (!fid || !aid) return null
    delete window[PENDING_KEY]
    return { feed_id: fid, article_id: aid }
  } catch {
    return null
  }
}

const filtered_feeds = computed(() => {
  const tag = String(selected_tag.value || '').trim()
  if (!tag) return feeds.value
  return (feeds.value || []).filter((f) => Array.isArray(f?.tags) && f.tags.includes(tag))
})

const current_item = computed(() => {
  const aid = article_id.value
  if (!aid) return null
  return items.value.find((x) => article_id_of(x) === aid) || null
})

const current_starred = computed(() => !!current_item.value?.starred)
const current_archived = computed(() => !!current_item.value?.archived)

async function load_feeds() {
  try {
    const r = await callTool('nisb_rss_list_feeds', {})
    feeds.value = pick_array(r, ['feeds', 'items', 'data'])
  } catch (e) {
    feeds.value = []
    toast(
      t('rss.center.reader.messages.loadFeedsFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

async function load_tags() {
  try {
    const r = await callTool('nisb_rss_list_tags', {})
    tags.value = pick_array(r, ['tags', 'items', 'data'])
  } catch (e) {
    tags.value = []
    toast(
      t('rss.center.reader.messages.loadTagsFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

async function load_articles() {
  if (!feed_id.value) {
    items.value = []
    return
  }

  load_deleted_urls()

  try {
    const r = await callTool('nisb_rss_list_articles', { feed_id: feed_id.value, limit: 200 })
    let arr = pick_array(r, ['items', 'articles', 'data'])

    arr = (arr || []).filter((it) => {
      const url = String(it?.url || it?.link || '').trim()
      if (!url) return true
      return !deleted_urls.value.has(url)
    })

    items.value = arr
  } catch (e) {
    items.value = []
    toast(
      t('rss.center.reader.messages.loadArticlesFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

async function open_article(aid) {
  if (!feed_id.value || !aid) return
  article_id.value = aid
  loading.value = true
  content_md.value = ''

  try {
    const r = await callTool('nisb_rss_get_article', { feed_id: feed_id.value, article_id: aid })
    if (is_ok(r)) {
      content_md.value = r.content_md || r.contentmd || r.content || ''
      set_local_flag(aid, { read: true })
      await load_articles()
    } else {
      content_md.value = r?.message || r?.detail || ''
    }
  } catch (e) {
    content_md.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function fetch_now() {
  if (!feed_id.value) {
    return toast(t('rss.center.reader.messages.chooseFeedFirst'), 'info')
  }

  try {
    const r = await callTool('nisb_rss_fetch', { feed_id: feed_id.value, limit_entries: 80 })
    if (is_ok(r)) {
      await load_articles()
      toast(
        t('rss.center.reader.messages.fetchSuccess', {
          count: r.total_new || r.totalnew || 0
        }),
        'success'
      )
    } else {
      toast(r?.message || r?.detail || t('rss.center.reader.messages.fetchFailed'), 'error')
    }
  } catch (e) {
    toast(e?.message || String(e), 'error')
  }
}

async function toggle_star() {
  if (!feed_id.value || !article_id.value) return
  const next = !current_starred.value

  try {
    const r = await callTool('nisb_rss_set_state', {
      feed_id: feed_id.value,
      article_id: article_id.value,
      state: 'starred',
      value: next
    })

    if (is_ok(r)) {
      set_local_flag(article_id.value, { starred: next })
      await load_articles()
    } else {
      toast(r?.message || r?.detail || t('rss.center.reader.messages.setStateFailed'), 'error')
    }
  } catch (e) {
    toast(e?.message || String(e), 'error')
  }
}

async function toggle_archive() {
  if (!feed_id.value || !article_id.value) return
  const next = !current_archived.value

  try {
    const r = await callTool('nisb_rss_set_state', {
      feed_id: feed_id.value,
      article_id: article_id.value,
      state: 'archived',
      value: next
    })

    if (is_ok(r)) {
      set_local_flag(article_id.value, { archived: next })
      await load_articles()
    } else {
      toast(r?.message || r?.detail || t('rss.center.reader.messages.setStateFailed'), 'error')
    }
  } catch (e) {
    toast(e?.message || String(e), 'error')
  }
}

async function on_feed_changed() {
  article_id.value = ''
  content_md.value = ''
  await load_articles()
}

async function on_tag_changed() {
  const exists = filtered_feeds.value.some((f) => feed_id_of(f) === feed_id.value)
  if (!exists) {
    feed_id.value = ''
    items.value = []
    article_id.value = ''
    content_md.value = ''
  }
}

async function refresh_all() {
  await load_feeds()
  await load_tags()
  if (feed_id.value) await load_articles()
}

async function on_open_article_event(e) {
  const d = e?.detail || {}
  const fid = String(d.feed_id || '').trim()
  const aid = String(d.article_id || '').trim()
  if (!fid || !aid) return

  feed_id.value = fid
  await nextTick()
  await on_feed_changed()
  await open_article(aid)
}

onMounted(async () => {
  load_deleted_urls()
  await refresh_all()

  const pending = consume_pending_open()
  if (pending) await on_open_article_event({ detail: pending })

  window.addEventListener('nisb_open_rss_article', on_open_article_event)
})

onUnmounted(() => {
  window.removeEventListener('nisb_open_rss_article', on_open_article_event)
})

watch(
  () => props.initialFeedId,
  async (v) => {
    if (!v) return
    feed_id.value = v
    await nextTick()
    await on_feed_changed()
  }
)
</script>

<style scoped>
.rss_reader {
  height: 100%;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 38%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
}

.topbar {
  --nisb-rss-bar-height: 48px;

  position: relative;
  z-index: 2;
  flex: 0 0 auto;
  min-width: 0;
  height: var(--nisb-rss-bar-height);
  min-height: var(--nisb-rss-bar-height);
  max-height: var(--nisb-rss-bar-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.46rem 0.65rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.topbar::-webkit-scrollbar {
  display: none;
}

.topbar::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 18%, var(--line)),
      transparent
    );
  opacity: 0.62;
}

.topbar-title-block {
  flex: 1 1 auto;
  min-width: 160px;
  display: grid;
  gap: 0.16rem;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.88rem;
  font-weight: 820;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-meta,
.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.36rem;
  min-width: 0;
}

.topbar-actions {
  flex: 0 0 auto;
}

.meta-chip,
.badge {
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

.meta-chip {
  border-color: color-mix(in srgb, var(--selected) 20%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 32%, var(--editor-bg));
  color: var(--selected);
}

.btn {
  min-height: 31px;
  box-sizing: border-box;
  padding: 0 0.68rem;
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
  font-size: 0.76rem;
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

.btn.ghost {
  background: color-mix(in srgb, var(--editor-bg) 30%, transparent);
}

.btn.active {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 68%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.body {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  overflow: hidden;
}

.left {
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.58rem;
  padding: 0.62rem;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
  scrollbar-width: thin;
}

.control-card,
.articles-card {
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.04);
}

.control-card {
  flex: 0 0 auto;
  display: grid;
  gap: 0.42rem;
  padding: 0.62rem;
}

.articles-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.articles-head {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  padding: 0.62rem 0.62rem 0.5rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
}

.section_title {
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 790;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.sel {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0.48rem 0.58rem;
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

.sel:focus {
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

.list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 0.46rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.55rem;
  scrollbar-width: thin;
}

.list::-webkit-scrollbar,
.left::-webkit-scrollbar,
.right::-webkit-scrollbar {
  width: 8px;
}

.list::-webkit-scrollbar-thumb,
.left::-webkit-scrollbar-thumb,
.right::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.row {
  position: relative;
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: 0.52rem;
  padding: 0.58rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 12px;
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

.row:hover,
.row:focus-visible {
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

.row.active {
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

.row-accent {
  flex: 0 0 auto;
  width: 3px;
  margin: 0.14rem 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 80%, transparent);
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.row:hover .row-accent,
.row:focus-visible .row-accent,
.row.active .row-accent {
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.22rem;
}

.t {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.83rem;
  font-weight: 760;
  line-height: 1.32;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row:hover .t,
.row:focus-visible .t,
.row.active .t {
  color: var(--selected);
}

.s {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.7rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.28rem;
  min-width: 0;
}

.badge {
  min-height: 20px;
  padding: 0 0.42rem;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 60%, transparent);
  font-size: 0.68rem;
}

.row:hover .badge,
.row:focus-visible .badge,
.row.active .badge {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 40%, var(--editor-bg));
}

.right {
  min-height: 0;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 36%),
    var(--editor-bg);
  scrollbar-width: thin;
}

.article-shell {
  box-sizing: border-box;
  width: min(920px, calc(100% - 48px));
  min-height: calc(100% - 48px);
  margin: 24px auto;
  padding: 1.4rem 1.55rem 2rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 88%, var(--sidebar-bg))
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 20px 48px rgba(0, 0, 0, 0.08);
}

.empty-state,
.state-box {
  box-sizing: border-box;
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.empty-state {
  max-width: min(34rem, calc(100vw - 2rem));
  margin: 18vh auto 0;
  padding: 1rem 1.25rem;
  border: 1px dashed color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08);
}

.state-box {
  padding: 0.9rem 0.75rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
}

.muted {
  color: var(--text-secondary);
  opacity: 0.74;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 960px) {
  .body {
    grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  }

  .article-shell {
    width: min(840px, calc(100% - 28px));
    margin: 14px auto;
    padding: 1.1rem 1.2rem 1.6rem;
  }
}

@media (max-width: 760px) {
  .topbar {
    height: auto;
    min-height: 48px;
    max-height: none;
    align-items: stretch;
    flex-wrap: wrap;
    overflow: visible;
  }

  .topbar-title-block {
    order: 3;
    flex-basis: 100%;
  }

  .topbar-actions {
    flex: 1 1 auto;
    justify-content: flex-end;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .topbar-actions::-webkit-scrollbar {
    display: none;
  }

  .body {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(280px, 42vh) minmax(0, 1fr);
  }

  .left {
    border-right: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  }

  .article-shell {
    width: calc(100% - 20px);
    min-height: calc(100% - 20px);
    margin: 10px auto;
    border-radius: 16px;
  }
}

@media (max-width: 520px) {
  .topbar {
    padding: 0.45rem;
  }

  .topbar-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .btn {
    width: 100%;
    white-space: normal;
  }

  .left {
    padding: 0.5rem;
  }

  .article-shell {
    width: 100%;
    min-height: 100%;
    margin: 0;
    border-left: 0;
    border-right: 0;
    border-radius: 0;
    padding: 1rem;
  }
}
</style>
