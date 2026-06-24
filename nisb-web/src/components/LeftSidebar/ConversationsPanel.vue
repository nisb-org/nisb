<template>
  <div class="conv-container">
    <div class="conv-header">
      <div class="conv-header-left">
        <span class="conv-title">{{ t('sidebar.conversations.title') }}</span>
        <span v-if="activeLabelName" class="label-filter-pill">
          🏷 {{ activeLabelName }}
        </span>
      </div>

      <div class="conv-header-actions">
        <button
          class="tag-filter-btn"
          type="button"
          @click.stop="toggleLabelFilterPanel"
          :title="t('sidebar.conversations.filterByLabel')"
        >
          🏷
        </button>
        <button
          class="new-conv-btn"
          type="button"
          @click="createNewConversation"
          :title="t('sidebar.conversations.create')"
        >
          +
        </button>
      </div>
    </div>

    <div v-if="labelFilterVisible" class="label-filter-panel" @click.stop>
      <div class="label-filter-header">
        <span>{{ t('sidebar.conversations.labels.title') }}</span>
        <button class="label-filter-close" type="button" @click="labelFilterVisible = false">✕</button>
      </div>

      <div class="label-filter-body">
        <div class="label-filter-row">
          <button class="label-chip" type="button" :class="{ selected: labelFilter === 'ALL' }" @click="setLabelFilter('ALL')">
            {{ t('sidebar.conversations.labels.all') }}
          </button>
          <button
            class="label-chip"
            type="button"
            :class="{ selected: labelFilter === '__UNLABELED__' }"
            @click="setLabelFilter('__UNLABELED__')"
          >
            {{ t('sidebar.conversations.labels.unlabeled') }}
            <span class="label-count">{{ unlabeledCount }}</span>
          </button>
        </div>

        <div v-if="loadingLabels" class="label-empty">{{ t('sidebar.conversations.labels.loading') }}</div>
        <div v-else-if="!labels.length" class="label-empty">{{ t('sidebar.conversations.labels.empty') }}</div>

        <div v-else class="label-list">
          <button
            v-for="lab in labels"
            :key="lab.label"
            class="label-chip"
            type="button"
            :class="{ selected: labelFilter === lab.label }"
            @click="setLabelFilter(lab.label)"
          >
            {{ lab.label }}
            <span class="label-count">{{ lab.count }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="conv-list">
      <div v-if="loadingConvs" class="empty-tip">{{ t('sidebar.conversations.loading') }}</div>
      <div v-else-if="!conversations.length" class="empty-tip">{{ t('sidebar.conversations.empty') }}</div>

      <template v-else>
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentConvId }"
          @click="openConversation(conv)"
          @mouseenter="onConvMouseEnter(conv, $event)"
          @mousemove="onConvMouseMove($event)"
          @mouseleave="onConvMouseLeave()"
          @contextmenu.prevent="showConvContextMenu($event, conv)"
        >
          <span class="conv-icon">💬</span>

          <div class="conv-content">
            <div class="conv-title-line">
              <span class="conv-name" :aria-label="conv.title || t('sidebar.conversations.newConversation')">
                {{ conv.title || t('sidebar.conversations.newConversation') }}
              </span>

              <span class="conv-count">
                {{ t('sidebar.conversations.turnCount', { count: conv.turn_count || 0 }) }}
              </span>
            </div>

            <span class="conv-time">
              {{ formatConvTime(conv.last_updated || conv.created_at) }}
            </span>
          </div>
        </div>

        <div class="load-more-wrap" v-if="!loadingConvs">
          <button v-if="hasMore" class="load-more-btn" :disabled="loadingMore" @click="loadMore" type="button">
            <span v-if="loadingMore">{{ t('sidebar.conversations.loadMoreLoading') }}</span>
            <span v-else>{{ t('sidebar.conversations.loadMore') }}</span>
          </button>
          <div v-else class="load-more-end">{{ t('sidebar.conversations.reachedEarliest') }}</div>
        </div>
      </template>
    </div>

    <div
      v-if="menu.visible"
      class="zen-context-menu"
      :style="{ top: menu.y + 'px', left: menu.x + 'px' }"
      @click.stop
    >
      <div class="menu-item" @click="handleConvRename">✏️ {{ t('sidebar.conversations.rename') }}</div>
      <div class="menu-item danger" @click="handleConvDelete">🗑️ {{ t('sidebar.conversations.delete') }}</div>
    </div>

    <div v-if="tip.visible" class="path-tooltip" :style="{ left: tip.x + 'px', top: tip.y + 'px' }">
      {{ tip.text }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { useChatConfigStore } from '../../stores/chatConfig'

const { t } = useI18n()
const { callTool } = useMCP()
const chatCfg = useChatConfigStore()

const PAGE_SIZE = 50

const conversations = ref([])
const loadingConvs = ref(false)
const loadingMore = ref(false)

const cursor = ref(null)
const hasMore = ref(true)

const currentConvId = ref(null)

const labels = ref([])
const unlabeledCount = ref(0)
const loadingLabels = ref(false)
const labelFilter = ref('ALL')
const labelFilterVisible = ref(false)

const activeLabelName = computed(() => {
  if (labelFilter.value === 'ALL') return ''
  if (labelFilter.value === '__UNLABELED__') return t('sidebar.conversations.labels.unlabeled')
  return labelFilter.value
})

const menu = ref({ visible: false, x: 0, y: 0, targetId: null, targetTitle: null })
const tip = ref({ visible: false, text: '', x: 0, y: 0 })

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalizeDisplayText(value) {
  const text = safeString(value)
  if (!text) return ''

  return text
    .replace(/\\r\\n/g, '\n')
    .replace(/\\\\r\\\\n/g, '\n')
    .replace(/\\\\n/g, '\n')
    .replace(/\\\\r/g, '\n')
}

function normalizeConversationTitle(value, fallback = '') {
  const text = normalizeDisplayText(value).trim()
  if (text) return text
  return normalizeDisplayText(fallback).trim()
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

function positionTip(e) {
  const margin = 12
  const offsetX = 14
  const offsetY = 18
  tip.value.x = clamp(e.clientX + offsetX, margin, window.innerWidth - margin - 40)
  tip.value.y = clamp(e.clientY + offsetY, margin, window.innerHeight - margin - 24)
}

function formatConvTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return d.toTimeString().slice(0, 5)
  return `${d.getMonth() + 1}-${d.getDate()} ${d.toTimeString().slice(0, 5)}`
}

function buildTipText(conv) {
  const title = normalizeConversationTitle(conv?.title, t('sidebar.conversations.newConversation'))
  const id = safeString(conv?.id).trim()
  const labs = Array.isArray(conv?.labels) ? conv.labels : []
  const separator = t('sidebar.conversations.tooltip.labelSeparator')
  const labStr = labs.length
    ? t('sidebar.conversations.tooltip.labelsWithItems', { items: labs.join(separator) })
    : t('sidebar.conversations.tooltip.labelsEmpty')
  const timeValue = formatConvTime(conv?.last_updated || conv?.created_at)
  const timeStr = timeValue ? t('sidebar.conversations.tooltip.time', { time: timeValue }) : ''
  const idStr = id ? t('sidebar.conversations.tooltip.id', { id }) : ''
  return [title, idStr, labStr, timeStr].filter(Boolean).join(' · ')
}

function showTip(conv, e) {
  tip.value.text = buildTipText(conv)
  if (!tip.value.text) return
  tip.value.visible = true
  positionTip(e)
}

function moveTip(e) {
  if (!tip.value.visible) return
  positionTip(e)
}

function hideTip() {
  tip.value.visible = false
}

function normalize(list) {
  return (list || []).map((c) => ({
    ...c,
    title: normalizeConversationTitle(c?.title),
    labels: Array.isArray(c.labels) ? c.labels : []
  }))
}

function buildHistoryArgs() {
  const args = { limit: PAGE_SIZE }
  if (cursor.value) args.cursor = cursor.value
  if (labelFilter.value && labelFilter.value !== 'ALL') args.label = labelFilter.value
  return args
}

async function loadPage({ reset = false } = {}) {
  if (loadingConvs.value || loadingMore.value) return

  if (reset) {
    conversations.value = []
    cursor.value = null
    hasMore.value = true
  }

  if (!hasMore.value && !reset) return

  if (reset) loadingConvs.value = true
  else loadingMore.value = true

  try {
    const res = await callTool('nisb_chat_history', buildHistoryArgs())
    if (res && res.status === 'success' && Array.isArray(res.conversations)) {
      const page = normalize(res.conversations)

      if (reset) {
        conversations.value = page
      } else {
        const seen = new Set(conversations.value.map((x) => x.id))
        for (const c of page) {
          if (!seen.has(c.id)) conversations.value.push(c)
        }
      }

      hasMore.value = !!res.has_more
      cursor.value = res.next_cursor || (page.length ? page[page.length - 1].id : cursor.value)
    } else {
      if (reset) conversations.value = []
      hasMore.value = false
    }
  } catch (e) {
    console.error('[ConversationsPanel] history load failed:', e)
    if (reset) conversations.value = []
    hasMore.value = false
  } finally {
    loadingConvs.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  await loadPage({ reset: false })
}

async function loadLabels() {
  loadingLabels.value = true
  try {
    const res = await callTool('nisb_chat_list_labels', {})
    if (res && res.status === 'success' && Array.isArray(res.labels)) {
      labels.value = res.labels
      unlabeledCount.value = Number(res.unlabeled_count || 0)
    } else {
      labels.value = []
      unlabeledCount.value = 0
    }
  } catch (e) {
    console.error('[ConversationsPanel] labels load failed:', e)
    labels.value = []
    unlabeledCount.value = 0
  } finally {
    loadingLabels.value = false
  }
}

function toggleLabelFilterPanel() {
  labelFilterVisible.value = !labelFilterVisible.value
  if (labelFilterVisible.value && !labels.value.length && !loadingLabels.value) loadLabels()
}

async function setLabelFilter(val) {
  labelFilter.value = val
  labelFilterVisible.value = false
  await loadPage({ reset: true })
}

function openConversation(conv) {
  if (chatCfg.chat?.mode === 'room') chatCfg.exitRoomHard()

  const id = String(conv.id)
  currentConvId.value = id

  window.dispatchEvent(
    new CustomEvent('nisb-open-conversation', {
      detail: {
        convId: id,
        title: normalizeConversationTitle(conv.title, t('sidebar.conversations.newConversation'))
      }
    })
  )
}

function onConvMouseEnter(conv, e) {
  showTip(conv, e)
}

function onConvMouseMove(e) {
  moveTip(e)
}

function onConvMouseLeave() {
  hideTip()
}

async function createNewConversation() {
  try {
    const defaultTitle = t('sidebar.conversations.newConversation')
    const res = await callTool('nisb_chat_create', { title: defaultTitle })
    if (res && res.status === 'success') {
      await loadLabels()
      await loadPage({ reset: true })
      currentConvId.value = res.conv_id
      window.dispatchEvent(
        new CustomEvent('nisb-open-conversation', {
          detail: { convId: res.conv_id, title: defaultTitle }
        })
      )
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      alert(
        t('sidebar.conversations.messages.createFailed', {
          error: res?.message || t('common.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('sidebar.conversations.messages.createFailed', {
        error: e?.message || t('common.unknownError')
      })
    )
  }
}

function showConvContextMenu(e, conv) {
  hideTip()
  menu.value = {
    visible: true,
    x: e.clientX,
    y: e.clientY,
    targetId: conv.id,
    targetTitle: normalizeConversationTitle(conv.title, t('sidebar.conversations.newConversation'))
  }
}

function hideMenu() {
  menu.value.visible = false
  labelFilterVisible.value = false
}

async function handleConvRename() {
  const newTitle = prompt(t('sidebar.conversations.messages.renamePrompt'), menu.value.targetTitle)
  if (!newTitle || newTitle === menu.value.targetTitle) {
    hideMenu()
    return
  }

  try {
    const result = await callTool('nisb_chat_rename', { conv_id: menu.value.targetId, new_title: newTitle })
    if (result && result.status === 'success') {
      await loadLabels()
      await loadPage({ reset: true })
    } else {
      alert(
        t('sidebar.conversations.messages.renameFailed', {
          error: result?.message || t('common.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('sidebar.conversations.messages.renameFailed', {
        error: e?.message || t('common.unknownError')
      })
    )
  } finally {
    hideMenu()
  }
}

async function handleConvDelete() {
  const convId = menu.value.targetId
  const uiTitle = normalizeConversationTitle(
    menu.value.targetTitle,
    t('sidebar.conversations.newConversation')
  )

  const res = await callTool('nisb_chat_conversation_trash_delete', {
    conv_id: convId,
    reason: 'ui_delete_conversation'
  })

  if (!res || !res.success) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('sidebar.conversations.messages.deleteFailed', {
            error: res?.message || t('common.unknownError')
          }),
          type: 'error'
        }
      })
    )
    hideMenu()
    return
  }

  const bulkId = res.bulk_id
  const apiDisplayName = normalizeConversationTitle(res?.display_name)
  const name = uiTitle || apiDisplayName || convId

  window.dispatchEvent(new CustomEvent('nisb-conversations-refresh'))
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: {
        message: t('sidebar.conversations.messages.movedToTrash', { name, bulkId }),
        type: 'success',
        duration: 9000,
        actionText: t('sidebar.conversations.undo'),
        actionEvent: 'nisb-conv-undo-bulk',
        actionDetail: { bulk_id: bulkId }
      }
    })
  )

  hideMenu()
}

function handleLabelsUpdated(e) {
  const detail = e.detail || {}
  const convId = detail.convId
  const labs = detail.labels || []
  if (!convId) return
  const target = conversations.value.find((c) => c.id === convId)
  if (target) target.labels = labs
  loadLabels()
}

async function onUndoConvBulk(evt) {
  const bulkId = evt?.detail?.bulk_id
  if (!bulkId) return
  const r = await callTool('nisb_chat_conversation_trash_restore', { bulk_id: bulkId, overwrite: false })
  if (!r || !r.success) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('sidebar.conversations.messages.undoFailed', {
            error: r?.message || t('common.unknownError')
          }),
          type: 'error'
        }
      })
    )
    return
  }
  window.dispatchEvent(new CustomEvent('nisb-conversations-refresh'))
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: {
        message: t('sidebar.conversations.messages.undoSuccess'),
        type: 'success'
      }
    })
  )
}

async function onConversationsRefresh() {
  await loadLabels()
  await loadPage({ reset: true })
}

onMounted(() => {
  loadLabels()
  loadPage({ reset: true })
  window.addEventListener('click', hideMenu)
  window.addEventListener('nisb-chat-labels-updated', handleLabelsUpdated)
  window.addEventListener('nisb-conv-undo-bulk', onUndoConvBulk)
  window.addEventListener('nisb-conversations-refresh', onConversationsRefresh)
})

onUnmounted(() => {
  window.removeEventListener('click', hideMenu)
  window.removeEventListener('nisb-chat-labels-updated', handleLabelsUpdated)
  window.removeEventListener('nisb-conv-undo-bulk', onUndoConvBulk)
  window.removeEventListener('nisb-conversations-refresh', onConversationsRefresh)
})
</script>

<style scoped>
.conv-container {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.52rem;
  padding: 0.55rem;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.conv-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  padding: 0.42rem;
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

.conv-header-left {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.conv-header-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.32rem;
}

.conv-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 800;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.label-filter-pill {
  max-width: 8rem;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 740;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-filter-btn,
.new-conv-btn,
.label-filter-close {
  width: 30px;
  height: 30px;
  min-width: 30px;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
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
  font-size: 0.78rem;
  font-weight: 760;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.new-conv-btn {
  font-size: 0.9rem;
}

.tag-filter-btn:hover,
.tag-filter-btn:focus-visible,
.new-conv-btn:hover,
.new-conv-btn:focus-visible,
.label-filter-close:hover,
.label-filter-close:focus-visible {
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

.tag-filter-btn:active,
.new-conv-btn:active,
.label-filter-close:active {
  transform: translateY(1px);
}

.label-filter-panel {
  position: absolute;
  top: 45px;
  right: 8px;
  z-index: 9999;
  width: min(280px, calc(100% - 16px));
  max-height: min(380px, calc(100% - 56px));
  display: flex;
  flex-direction: column;
  gap: 0.52rem;
  padding: 0.58rem;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 18px 42px rgba(0, 0, 0, 0.22),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.label-filter-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 790;
  line-height: 1.35;
}

.label-filter-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  overflow: hidden;
}

.label-filter-row,
.label-list {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.32rem;
}

.label-list {
  max-height: 180px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
  scrollbar-width: thin;
}

.label-list::-webkit-scrollbar {
  width: 8px;
}

.label-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.label-chip {
  max-width: 100%;
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.28rem;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 730;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.label-chip:hover,
.label-chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.label-chip.selected {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.label-count {
  flex: 0 0 auto;
  color: inherit;
  font-size: 0.68rem;
  opacity: 0.78;
}

.label-empty,
.empty-tip {
  padding: 0.82rem 0.72rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.conv-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 0.38rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.02rem 0.04rem 0.7rem;
  scrollbar-width: thin;
}

.conv-list::-webkit-scrollbar {
  width: 8px;
}

.conv-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.conv-item {
  position: relative;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  gap: 0.52rem;
  padding: 0.58rem 0.62rem;
  border: 1px solid transparent;
  border-radius: 13px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.conv-item::before {
  content: "";
  position: absolute;
  left: 0.34rem;
  top: 0.62rem;
  bottom: 0.62rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 80%, transparent);
  opacity: 0;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.conv-item:hover,
.conv-item:focus-within {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 44%, transparent),
      color-mix(in srgb, var(--editor-bg) 36%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06);
}

.conv-item.active {
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

.conv-item:hover::before,
.conv-item.active::before {
  opacity: 1;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.conv-icon {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  margin-left: 0.18rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 72%, transparent);
  font-size: 0.92rem;
  line-height: 1;
}

.conv-item:hover .conv-icon,
.conv-item.active .conv-icon {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
}

.conv-content {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.conv-title-line {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.36rem;
}

.conv-name {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 750;
  line-height: 1.32;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item:hover .conv-name {
  color: var(--selected);
  font-weight: 790;
}

.conv-item.active .conv-name {
  color: var(--selected);
  font-weight: 840;
  letter-spacing: -0.01em;
}

.conv-count {
  flex: 0 0 auto;
  min-height: 21px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.44rem;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 730;
  line-height: 1;
  white-space: nowrap;
}

.conv-item:hover .conv-count {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 40%, var(--editor-bg));
}

.conv-item.active .conv-count {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  font-weight: 780;
}

.conv-time {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.69rem;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item.active .conv-time {
  color: color-mix(in srgb, var(--selected) 72%, var(--text-secondary));
  font-weight: 720;
}

.zen-context-menu {
  position: fixed;
  z-index: 20000;
  min-width: 150px;
  max-width: min(260px, calc(100vw - 18px));
  padding: 0.32rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 18px 42px rgba(0, 0, 0, 0.22),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: hidden;
}

.menu-item {
  min-width: 0;
  min-height: 30px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0 0.58rem;
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1.2;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.menu-item:hover {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
}

.menu-item.danger {
  color: #ef4444;
}

.menu-item.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.path-tooltip {
  position: fixed;
  z-index: 20000;
  max-width: min(560px, calc(100vw - 24px));
  padding: 0.5rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.42;
  pointer-events: none;
  box-shadow:
    0 16px 34px rgba(0, 0, 0, 0.18),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  white-space: normal;
  overflow-wrap: anywhere;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.load-more-wrap {
  padding: 0.46rem 0.18rem 0.62rem;
  display: flex;
  justify-content: center;
}

.load-more-btn {
  min-height: 30px;
  box-sizing: border-box;
  padding: 0 0.82rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.load-more-btn:hover:not(:disabled),
.load-more-btn:focus-visible:not(:disabled) {
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

.load-more-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.load-more-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.load-more-end {
  padding: 0.34rem 0.6rem;
  border: 1px dashed color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.2;
  opacity: 0.82;
}

@media (max-width: 520px) {
  .conv-container {
    padding: 0.45rem;
  }

  .conv-header {
    align-items: stretch;
    flex-direction: column;
  }

  .conv-header-actions {
    width: 100%;
  }

  .tag-filter-btn,
  .new-conv-btn {
    flex: 1 1 auto;
    width: auto;
  }

  .label-filter-panel {
    left: 8px;
    right: 8px;
    width: auto;
  }

  .label-chip {
    flex: 1 1 auto;
  }

  .conv-item {
    padding: 0.56rem;
  }

  .conv-title-line {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.22rem;
  }

  .conv-count {
    align-self: flex-start;
  }

  .load-more-btn {
    width: 100%;
    white-space: normal;
  }
}
</style>
