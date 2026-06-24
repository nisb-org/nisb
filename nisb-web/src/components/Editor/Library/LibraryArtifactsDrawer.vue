<template>
  <div class="art-drawer" :class="{ open }">
    <div class="art-head" @click="toggle">
      <!-- ✅ 标题极简：只保留 ⚡ -->
      <div class="art-title">⚡</div>
      <div class="art-meta">
        <!-- ✅ 展开/收起不再使用中文，避免窄屏独占一行 -->
        <span class="chev">{{ open ? '▾' : '▸' }}</span>
        <span class="meta-pill">书签 {{ bookmarkTotal }}</span>
        <span class="meta-pill">批注 {{ annotationTotal }}</span>
      </div>
    </div>

    <div v-if="open" class="art-body">
      <div class="art-tabs">
        <button class="tab-btn" :class="{ active: tab === 'bookmarks' }" @click="tab = 'bookmarks'">
          书签
        </button>
        <button class="tab-btn" :class="{ active: tab === 'annotations' }" @click="tab = 'annotations'">
          批注
        </button>
      </div>

      <!-- 书签 -->
      <div v-if="tab === 'bookmarks'" class="pane">
        <div class="pane-actions">
          <button class="mini-btn" :disabled="bookmarkLoading" @click="refreshBookmarks">刷新</button>
          <button
            class="mini-btn"
            :disabled="bookmarkLoading"
            @click="bookmarkFilterMode = bookmarkFilterMode === 'doc' ? 'library' : 'doc'"
          >
            {{ bookmarkFilterMode === 'doc' ? '仅本书' : '全库' }}
          </button>
        </div>

        <div v-if="bookmarkLoading" class="tip">⏳ 加载书签…</div>
        <div v-else-if="!bookmarks.length" class="tip">（暂无书签）</div>

        <div v-else class="list scroll-list">
          <div v-for="it in bookmarks" :key="it.bookmark_id" class="item">
            <div class="main" @click="openBookmark(it)">
              <div class="line1">
                <span class="name">{{ it.title || `Span ${it.span_index}` }}</span>
                <span class="pill">Span {{ it.span_index }}</span>
              </div>
              <div class="line2">
                <span class="muted">{{ it.doc_id }}</span>
                <span class="dot">·</span>
                <span class="muted">{{ formatTime(it.created_at) }}</span>
              </div>
              <div v-if="it.note" class="note">{{ it.note }}</div>
            </div>
            <button class="del" title="移除书签" @click.stop="delBookmark(it)">×</button>
          </div>
        </div>
      </div>

      <!-- 批注（chunk + span 合并） -->
      <div v-else class="pane">
        <div class="pane-actions">
          <button class="mini-btn" :disabled="annotationLoading" @click="refreshAnnotations">刷新</button>

          <button
            class="mini-btn"
            :disabled="annotationLoading"
            @click="annotationFilterMode = annotationFilterMode === 'doc' ? 'library' : 'doc'"
          >
            {{ annotationFilterMode === 'doc' ? '仅本书' : '全库' }}
          </button>

          <button
            class="mini-btn"
            :disabled="annotationLoading"
            @click="annotationKind = annotationKind === 'all' ? 'span' : (annotationKind === 'span' ? 'chunk' : 'all')"
            :title="annotationKind === 'all' ? '切换为仅 Span 批注' : (annotationKind === 'span' ? '切换为仅 Chunk 批注' : '切换为全部批注')"
          >
            {{ annotationKind === 'all' ? '全部' : (annotationKind === 'span' ? 'Span' : 'Chunk') }}
          </button>
        </div>

        <!-- 添加：按 kind 分两种输入 -->
        <div class="add-row">
          <button
            class="mini-btn"
            :disabled="annotationLoading"
            @click="addKind = addKind === 'chunk' ? 'span' : 'chunk'"
            :title="addKind === 'chunk' ? '切换为添加 Span 批注' : '切换为添加 Chunk 批注'"
          >
            添加：{{ addKind === 'chunk' ? 'Chunk' : 'Span' }}
          </button>

          <template v-if="addKind === 'chunk'">
            <input
              v-model.number="chunkId"
              type="number"
              min="0"
              class="idx-input"
              :max="Math.max((docChunks || 1) - 1, 0)"
              placeholder="chunk"
            />
          </template>

          <template v-else>
            <input
              v-model.number="spanIndex"
              type="number"
              min="0"
              class="idx-input"
              placeholder="span"
            />
          </template>

          <input
            v-model="annotationText"
            class="text-input"
            placeholder="写一条批注（Enter 提交）"
            @keydown.enter.prevent="addAnnotation"
          />
          <button class="mini-btn" :disabled="annotationLoading" @click="addAnnotation">添加</button>
        </div>

        <div v-if="annotationLoading" class="tip">⏳ 加载批注…</div>
        <div v-else-if="!mergedAnnotations.length" class="tip">（暂无批注）</div>

        <div v-else class="list scroll-list">
          <div v-for="it in mergedAnnotations" :key="it._key" class="item">
            <div class="main" @click="openAnyAnnotation(it)">
              <div class="line1">
                <span class="name">{{ trimOneLine(it.content) }}</span>
                <span class="pill" v-if="it._kind === 'span'">Span {{ it.span_index }}</span>
                <span class="pill" v-else>Chunk {{ it.chunk_id }}</span>
              </div>
              <div class="line2">
                <span class="muted">{{ it.doc_id }}</span>
                <span class="dot">·</span>
                <span class="muted">{{ formatTime(it.created_at) }}</span>
              </div>
              <div class="note">{{ it.content }}</div>
            </div>
            <button
              class="del"
              :title="it._kind === 'span' ? '移除 Span 批注' : '移除 Chunk 批注'"
              @click.stop="delAnyAnnotation(it)"
            >
              ×
            </button>
          </div>
        </div>

        <div class="tip muted-small">
          点击条目会跳转到对应文档：Span 批注会定位到 span；Chunk 批注会把 chunk_id 作为定位提示传递。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useMCP } from '../../../composables/useMCP'

const props = defineProps({
  libraryId: { type: String, required: true },
  selectedDocId: { type: String, default: null },
  docChunks: { type: Number, default: 0 }
})

const { callTool } = useMCP()

const open = ref(false)
const tab = ref('bookmarks')

const bookmarks = ref([])
const bookmarkLoading = ref(false)
const bookmarkFilterMode = ref('doc') // doc|library

// 批注：chunk + span
const chunkAnnotations = ref([])
const spanAnnotations = ref([])
const annotationLoading = ref(false)
const annotationFilterMode = ref('doc') // doc|library
const annotationKind = ref('all') // all|chunk|span

// 添加批注：支持 chunk / span
const addKind = ref('chunk') // chunk|span
const chunkId = ref(0)
const spanIndex = ref(0)
const annotationText = ref('')

const bookmarkTotal = computed(() => bookmarks.value.length)
const annotationTotal = computed(() => mergedAnnotations.value.length)

const mergedAnnotations = computed(() => {
  const src =
    annotationKind.value === 'chunk'
      ? chunkAnnotations.value.map((x) => ({ ...x, _kind: 'chunk', _key: 'c_' + x.annotation_id }))
      : annotationKind.value === 'span'
        ? spanAnnotations.value.map((x) => ({ ...x, _kind: 'span', _key: 's_' + x.annotation_id }))
        : [
            ...chunkAnnotations.value.map((x) => ({ ...x, _kind: 'chunk', _key: 'c_' + x.annotation_id })),
            ...spanAnnotations.value.map((x) => ({ ...x, _kind: 'span', _key: 's_' + x.annotation_id }))
          ]

  return src.sort((a, b) =>
    String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || ''))
  )
})

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

function trimOneLine(s) {
  const t = String(s || '').trim().replace(/\s+/g, ' ')
  return t.length > 40 ? t.slice(0, 40) + '…' : t
}

async function refresh() {
  await Promise.all([refreshBookmarks(), refreshAnnotations()])
}

async function refreshBookmarks() {
  bookmarkLoading.value = true
  try {
    const args = { library_id: props.libraryId }
    if (bookmarkFilterMode.value === 'doc' && props.selectedDocId) args.doc_id = props.selectedDocId
    const res = await callTool('nisb_bookmark_list', args, { trackLoading: false })
    bookmarks.value = res?.status === 'success' ? (res.bookmarks || []) : []
  } catch (e) {
    console.error('[功能抽屉][书签] 列表失败:', e)
    bookmarks.value = []
  } finally {
    bookmarkLoading.value = false
  }
}

async function refreshChunkAnnotations() {
  const args = { library_id: props.libraryId }
  if (annotationFilterMode.value === 'doc' && props.selectedDocId) args.doc_id = props.selectedDocId
  const res = await callTool('nisb_library_annotation_list', args, { trackLoading: false })
  chunkAnnotations.value = res?.status === 'success' ? (res.annotations || []) : []
}

async function refreshSpanAnnotations() {
  const args = { library_id: props.libraryId }
  if (annotationFilterMode.value === 'doc' && props.selectedDocId) args.doc_id = props.selectedDocId
  const res = await callTool('nisb_span_annotation_list', args, { trackLoading: false })
  spanAnnotations.value = res?.status === 'success' ? (res.annotations || []) : []
}

async function refreshAnnotations() {
  annotationLoading.value = true
  try {
    await Promise.all([refreshChunkAnnotations(), refreshSpanAnnotations()])
  } catch (e) {
    console.error('[功能抽屉][批注] 列表失败:', e)
    chunkAnnotations.value = []
    spanAnnotations.value = []
  } finally {
    annotationLoading.value = false
  }
}

function openBookmark(it) {
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

function openAnyAnnotation(it) {
  if (it._kind === 'span') {
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
    return
  }

  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: it.library_id,
        docId: it.doc_id,
        spanIndex: null,
        reader: null,
        chunkId: it.chunk_id
      }
    })
  )
}

async function delBookmark(it) {
  if (!confirm(`移除书签？\n\n${it.title || `Span ${it.span_index}`}`)) return
  try {
    const res = await callTool('nisb_bookmark_delete', { bookmark_id: it.bookmark_id }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated', { detail: { bookmark_id: it.bookmark_id } }))
      await refreshBookmarks()
    } else {
      alert('移除失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('移除失败：' + (e?.message || e))
  }
}

async function addAnnotation() {
  const text = String(annotationText.value || '').trim()
  if (!props.selectedDocId) {
    alert('请先选中文档，再添加批注')
    return
  }
  if (!text) {
    alert('请输入批注内容')
    return
  }

  annotationLoading.value = true
  try {
    if (addKind.value === 'chunk') {
      const cid = Number.isFinite(chunkId.value) ? Number(chunkId.value) : 0
      const res = await callTool(
        'nisb_library_annotation_add',
        {
          library_id: props.libraryId,
          doc_id: props.selectedDocId,
          chunk_id: cid,
          content: text
        },
        { trackLoading: false }
      )
      if (res?.status !== 'success') {
        alert('添加失败：' + (res?.message || '未知错误'))
        return
      }
    } else {
      const sid = Number.isFinite(spanIndex.value) ? Number(spanIndex.value) : 0
      const res = await callTool(
        'nisb_span_annotation_add',
        {
          library_id: props.libraryId,
          doc_id: props.selectedDocId,
          span_index: sid,
          content: text,
          reader: null
        },
        { trackLoading: false }
      )
      if (res?.status !== 'success') {
        alert('添加失败：' + (res?.message || '未知错误'))
        return
      }
    }

    annotationText.value = ''
    window.dispatchEvent(new CustomEvent('nisb-annotation-updated', { detail: { doc_id: props.selectedDocId } }))
    await refreshAnnotations()
  } catch (e) {
    alert('添加失败：' + (e?.message || String(e)))
  } finally {
    annotationLoading.value = false
  }
}

async function delAnyAnnotation(it) {
  if (it._kind === 'span') {
    if (!confirm(`移除批注？\n\nSpan ${it.span_index}\n${it.content}`)) return
    try {
      const res = await callTool('nisb_span_annotation_delete', { annotation_id: it.annotation_id }, { trackLoading: false })
      if (res?.status === 'success') {
        window.dispatchEvent(new CustomEvent('nisb-annotation-updated', { detail: { annotation_id: it.annotation_id } }))
        await refreshAnnotations()
      } else {
        alert('移除失败：' + (res?.message || '未知错误'))
      }
    } catch (e) {
      alert('移除失败：' + (e?.message || String(e)))
    }
    return
  }

  if (!confirm(`移除批注？\n\nChunk ${it.chunk_id}\n${it.content}`)) return
  try {
    const res = await callTool('nisb_library_annotation_delete', { annotation_id: it.annotation_id }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-annotation-updated', { detail: { annotation_id: it.annotation_id } }))
      await refreshAnnotations()
    } else {
      alert('移除失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('移除失败：' + (e?.message || String(e)))
  }
}

function onBookmarkUpdated() {
  if (!open.value) return
  refreshBookmarks()
}
function onAnnotationUpdated() {
  if (!open.value) return
  refreshAnnotations()
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
  window.addEventListener('nisb-annotation-updated', onAnnotationUpdated)
})

onUnmounted(() => {
  window.removeEventListener('nisb-bookmark-updated', onBookmarkUpdated)
  window.removeEventListener('nisb-annotation-updated', onAnnotationUpdated)
})

defineExpose({ refresh, toggle })
</script>

<style scoped>
.art-drawer {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  overflow: hidden;
}
.art-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.65rem 0.75rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
}
.art-head:hover {
  background: var(--selected-bg);
}
.art-title {
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--text);
}
.art-meta {
  font-size: 0.78rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
  max-width: 70%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.art-meta::-webkit-scrollbar {
  height: 0;
}

.chev {
  flex: 0 0 auto;
  opacity: 0.85;
}

.meta-pill {
  flex: 0 0 auto;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.08rem 0.4rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.art-body {
  padding: 0.65rem 0.75rem 0.75rem;
}
.art-tabs {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
}
.tab-btn {
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text-secondary);
}
.tab-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}
.tab-btn.active {
  background: rgba(60, 105, 188, 0.12);
  border-color: rgba(60, 105, 188, 0.45);
  color: var(--selected);
}
.pane-actions {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
}
.mini-btn {
  padding: 0.25rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text-secondary);
}
.mini-btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}
.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.add-row {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
  align-items: center;
}
.idx-input {
  width: 92px;
  padding: 0.35rem 0.55rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-main);
  font-size: 0.82rem;
}
.text-input {
  flex: 1;
  min-width: 0;
  padding: 0.35rem 0.55rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-main);
  font-size: 0.82rem;
}
.tip {
  padding: 0.65rem 0.2rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
}
.muted-small {
  font-size: 0.75rem;
  opacity: 0.8;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.scroll-list {
  max-height: 320px;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.item {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.6rem;
  transition: all var(--transition-normal) var(--ease-smooth);
}
.item:hover {
  border-color: var(--selected);
  background: rgba(60, 105, 188, 0.06);
}
.main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.line1 {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  min-width: 0;
}
.name {
  font-size: 0.88rem;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pill {
  flex-shrink: 0;
  font-size: 0.72rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.08rem 0.4rem;
  color: var(--text-secondary);
}
.line2 {
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  display: flex;
  gap: 0.25rem;
  align-items: center;
  white-space: nowrap;
}
.dot {
  opacity: 0.7;
}
.muted {
  overflow: hidden;
  text-overflow: ellipsis;
}
.note {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.35;
  white-space: normal;
}
.del {
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
.del:hover {
  background: rgba(120, 120, 120, 0.10);
  border-color: var(--selected);
  color: var(--selected);
  opacity: 1;
}
</style>

