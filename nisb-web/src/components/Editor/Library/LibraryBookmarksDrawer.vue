<template>
  <div class="bm-drawer" :class="{ open }">
    <div class="bm-head" @click="toggle">
      <div class="bm-title">书签</div>
      <div class="bm-meta">{{ open ? '收起' : '展开' }} · {{ total }} 条</div>
    </div>

    <div v-if="open" class="bm-body">
      <div class="bm-actions">
        <button class="bm-btn" :disabled="loading" @click="refresh">刷新</button>
        <button
          class="bm-btn"
          :disabled="loading"
          @click="filterMode = filterMode === 'doc' ? 'library' : 'doc'"
        >
          {{ filterMode === 'doc' ? '仅本书' : '全库' }}
        </button>
      </div>

      <div v-if="loading" class="bm-tip">⏳ 加载书签…</div>
      <div v-else-if="!items.length" class="bm-tip">（暂无书签）</div>

      <div v-else class="bm-list">
        <div v-for="it in items" :key="it.bookmark_id" class="bm-item">
          <div class="bm-main" @click="openBookmark(it)">
            <div class="bm-line1">
              <span class="bm-name">{{ it.title || `Span ${it.span_index}` }}</span>
              <span class="bm-pill">Span {{ it.span_index }}</span>
            </div>
            <div class="bm-line2">
              <span class="bm-muted">{{ it.doc_id }}</span>
              <span class="bm-dot">·</span>
              <span class="bm-muted">{{ formatTime(it.created_at) }}</span>
            </div>
            <div v-if="it.note" class="bm-note">{{ it.note }}</div>
          </div>

          <button class="bm-del" title="移除书签" @click.stop="del(it)">×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useMCP } from '../../../composables/useMCP'

const props = defineProps({
  libraryId: { type: String, required: true },
  selectedDocId: { type: String, default: null }
})

const { callTool } = useMCP()

const open = ref(false)
const loading = ref(false)
const items = ref([])
const filterMode = ref('doc') // 'doc' | 'library'

const total = computed(() => items.value.length)

function toggle() {
  open.value = !open.value
  if (open.value) refresh()
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function refresh() {
  loading.value = true
  try {
    const args = { library_id: props.libraryId }
    if (filterMode.value === 'doc' && props.selectedDocId) args.doc_id = props.selectedDocId

    const res = await callTool('nisb_bookmark_list', args, { trackLoading: false })
    items.value = res?.status === 'success' ? (res.bookmarks || []) : []
  } catch (e) {
    console.error('[书签] 加载失败:', e)
    items.value = []
  } finally {
    loading.value = false
  }
}

function openBookmark(it) {
  // ✅ 关键：把 reader 状态也带上（如果 bookmark 里没存 reader，这里会退化为 null）
  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: it.library_id,
        docId: it.doc_id,
        spanIndex: it.span_index,
        reader: it.reader || null
      }
    })
  )
}

async function del(it) {
  if (!confirm(`移除书签？\n\n${it.title || `Span ${it.span_index}`}`)) return
  try {
    const res = await callTool('nisb_bookmark_delete', { bookmark_id: it.bookmark_id }, { trackLoading: false })
    if (res?.status === 'success') {
      await refresh()
    } else {
      alert('移除失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('移除失败：' + (e?.message || e))
  }
}

function onBookmarkUpdated() {
  // 只在抽屉展开时刷新，避免无意义请求
  if (!open.value) return
  refresh()
}

watch(
  () => [props.libraryId, props.selectedDocId],
  () => {
    if (!open.value) return
    refresh()
  }
)

onMounted(() => {
  window.addEventListener('nisb-bookmark-updated', onBookmarkUpdated)
})

onUnmounted(() => {
  window.removeEventListener('nisb-bookmark-updated', onBookmarkUpdated)
})

defineExpose({ refresh, toggle })
</script>

<style scoped>
.bm-drawer {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  overflow: hidden;
}
.bm-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.65rem 0.75rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
}
.bm-head:hover {
  background: var(--selected-bg);
}
.bm-title {
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--text);
}
.bm-meta {
  font-size: 0.78rem;
  color: var(--text-secondary);
}
.bm-body {
  padding: 0.65rem 0.75rem 0.75rem;
}
.bm-actions {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
}
.bm-btn {
  padding: 0.25rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text-secondary);
}
.bm-btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}
.bm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.bm-tip {
  padding: 0.75rem 0.2rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
}
.bm-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.bm-item {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.6rem;
  transition: all var(--transition-normal) var(--ease-smooth);
}
.bm-item:hover {
  border-color: var(--selected);
  background: rgba(60, 105, 188, 0.06);
}
.bm-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.bm-line1 {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  min-width: 0;
}
.bm-name {
  font-size: 0.88rem;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bm-pill {
  flex-shrink: 0;
  font-size: 0.72rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.08rem 0.4rem;
  color: var(--text-secondary);
}
.bm-line2 {
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  display: flex;
  gap: 0.25rem;
  align-items: center;
  white-space: nowrap;
}
.bm-dot {
  opacity: 0.7;
}
.bm-muted {
  overflow: hidden;
  text-overflow: ellipsis;
}
.bm-note {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.35;
  white-space: normal;
}
.bm-del {
  width: 22px;
  height: 22px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0.75;
}
.bm-del:hover {
  background: rgba(120, 120, 120, 0.10);
  border-color: var(--selected);
  color: var(--selected);
  opacity: 1;
}
</style>

