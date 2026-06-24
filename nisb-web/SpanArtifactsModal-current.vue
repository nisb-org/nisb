<template>
  <teleport to=".app">
    <div v-if="open" class="nisb-modal-mask" @click.self="close">
      <div class="nisb-modal nisb-modal-mid">
        <div class="nisb-modal-title">
          Span 功能
          <span class="muted" style="margin-left: 0.5rem;">
            {{ libraryId }} · {{ docId }} · Span {{ spanIndex }}
          </span>
        </div>

        <div class="tabs">
          <button class="tab-btn" :class="{ active: tab === 'bookmark' }" @click="tab = 'bookmark'">书签</button>
          <button class="tab-btn" :class="{ active: tab === 'annotation' }" @click="tab = 'annotation'">批注</button>

          <div class="tab-meta muted">书签 {{ bookmarks.length }} · 批注 {{ annotations.length }}</div>
        </div>

        <div class="nisb-modal-body">
          <!-- Bookmarks -->
          <div v-if="tab === 'bookmark'">
            <div class="toolbar">
              <button class="mini-btn" :disabled="loadingBookmark" @click="addBookmark">
                {{ loadingBookmark ? '处理中…' : '添加书签' }}
              </button>
            </div>

            <div v-if="loadingBookmark" class="tip">⏳ 加载书签…</div>
            <div v-else-if="!bookmarks.length" class="tip">（暂无书签）</div>

            <div v-else class="list scroll-list">
              <div
                v-for="it in bookmarks"
                :key="bookmarkKey(it)"
                class="item"
                :class="{ highlight: Number(spanOf(it)) === Number(spanIndex) }"
              >
                <div class="item-main" @click="jumpByBookmark(it)">
                  <div class="item-title">
                    {{ it.title || `Span ${spanOf(it)}` }}
                    <span class="pill">Span {{ spanOf(it) }}</span>
                  </div>
                  <div class="item-sub muted">{{ formatTime(it.created_at) }}</div>
                  <div v-if="it.note" class="item-note">{{ it.note }}</div>
                </div>

                <button class="item-del" title="移除书签" @click.stop="delBookmark(it)">×</button>
              </div>
            </div>
          </div>

          <!-- Annotations -->
          <div v-else>
            <div class="add-row">
              <input
                v-model="annotationInput"
                class="nisb-input"
                placeholder="写一条批注（Enter 提交）"
                @keydown.enter.prevent="addAnnotation"
              />
              <button class="mini-btn" :disabled="loadingAnnotation" @click="addAnnotation">
                {{ loadingAnnotation ? '提交中…' : '添加' }}
              </button>
            </div>

            <div v-if="loadingAnnotation" class="tip">⏳ 加载批注…</div>
            <div v-else-if="!annotations.length" class="tip">（暂无批注）</div>

            <div v-else class="list scroll-list">
              <div
                v-for="it in annotations"
                :key="annotationKey(it)"
                class="item"
                :class="{ highlight: Number(spanOf(it)) === Number(spanIndex) }"
              >
                <div class="item-main" @click="jumpByAnnotation(it)">
                  <div class="item-title">
                    {{ oneLine(it.content) }}
                    <span class="pill">Span {{ spanOf(it) }}</span>
                  </div>
                  <div class="item-sub muted">{{ formatTime(it.created_at) }}</div>
                  <div class="item-note">{{ it.content }}</div>
                </div>

                <button class="item-del" title="移除批注" @click.stop="delAnnotation(it)">×</button>
              </div>
            </div>

            <div class="muted" style="margin-top: 0.6rem; font-size: 0.82rem;">
              删除后重新添加即可，不需要“修改”。
            </div>
          </div>
        </div>

        <div class="nisb-modal-actions">
          <button class="modal-btn" @click="close">关闭</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useMCP } from '../../../composables/useMCP'

const props = defineProps({
  open: { type: Boolean, default: false },
  libraryId: { type: String, required: true },
  docId: { type: String, required: true },
  spanIndex: { type: Number, required: true },
  reader: { type: Object, default: null }
})

const emit = defineEmits(['close'])
const { callTool } = useMCP()

const tab = ref('bookmark')

const loadingBookmark = ref(false)
const bookmarks = ref([])

const loadingAnnotation = ref(false)
const annotations = ref([])
const annotationInput = ref('')

function close() {
  emit('close')
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function oneLine(s) {
  const t = String(s || '').trim().replace(/\s+/g, ' ')
  return t.length > 50 ? t.slice(0, 50) + '…' : t
}

/** ===== 兼容解析：id / span ===== */
function _n(v) {
  const x = Number(v)
  return Number.isFinite(x) ? x : null
}

function spanOf(it) {
  return (
    _n(it?.span_index) ??
    _n(it?.spanIndex) ??
    _n(it?.span_id) ??
    _n(it?.spanId) ??
    _n(it?.spanid) ??
    _n(it?.span) ??
    0
  )
}

function bookmarkIdOf(it) {
  return (
    it?.bookmark_id ??
    it?.bookmarkId ??
    it?.bookmarkid ??
    it?.id ??
    null
  )
}

function annotationIdOf(it) {
  return (
    it?.annotation_id ??
    it?.annotationId ??
    it?.annotationid ??
    it?.id ??
    null
  )
}

function bookmarkKey(it) {
  return String(bookmarkIdOf(it) ?? `${props.docId}:${spanOf(it)}`)
}

function annotationKey(it) {
  return String(annotationIdOf(it) ?? `${props.docId}:${spanOf(it)}`)
}

/** ===== list：永远“本书 doc”范围 ===== */
async function refreshBookmarks() {
  loadingBookmark.value = true
  try {
    const res = await callTool(
      'nisb_bookmark_list',
      { library_id: props.libraryId, doc_id: props.docId },
      { trackLoading: false }
    )
    bookmarks.value = res?.status === 'success' ? (res.bookmarks || []) : []
  } catch (e) {
    console.error('[SpanModal][bookmark] list failed:', e)
    bookmarks.value = []
  } finally {
    loadingBookmark.value = false
  }
}

async function refreshAnnotations() {
  loadingAnnotation.value = true
  try {
    const res = await callTool(
      'nisb_span_annotation_list',
      // ✅ 不再传 span_index：永远列出本书全部批注
      { library_id: props.libraryId, doc_id: props.docId },
      { trackLoading: false }
    )
    annotations.value = res?.status === 'success' ? (res.annotations || []) : []
  } catch (e) {
    console.error('[SpanModal][annotation] list failed:', e)
    annotations.value = []
  } finally {
    loadingAnnotation.value = false
  }
}

async function refreshActiveTab() {
  if (!props.open) return
  if (tab.value === 'bookmark') await refreshBookmarks()
  else await refreshAnnotations()
}

/** ===== add/del：字段名对齐 + id 兼容 ===== */
async function addBookmark() {
  loadingBookmark.value = true
  try {
    const res = await callTool(
      'nisb_bookmark_add',
      {
        library_id: props.libraryId,
        doc_id: props.docId,
        span_index: Number(props.spanIndex || 0),
        title: `Span ${Number(props.spanIndex || 0)}`,
        note: '',
        reader: props.reader || null
      },
      { trackLoading: false }
    )
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated', { detail: { bookmark: res.bookmark } }))
      await refreshBookmarks()
    } else {
      alert('❌ 添加书签失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('❌ 添加书签失败：' + (e?.message || String(e)))
  } finally {
    loadingBookmark.value = false
  }
}

async function delBookmark(it) {
  const bid = bookmarkIdOf(it)
  if (!bid) {
    alert('❌ 移除失败：bookmark_id 不能为空')
    return
  }
  if (!confirm(`移除书签？\n\n${it.title || `Span ${spanOf(it)}`}`)) return

  loadingBookmark.value = true
  try {
    const res = await callTool('nisb_bookmark_delete', { bookmark_id: bid }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated', { detail: { bookmark_id: bid } }))
      await refreshBookmarks()
    } else {
      alert('❌ 移除失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('❌ 移除失败：' + (e?.message || String(e)))
  } finally {
    loadingBookmark.value = false
  }
}

function jumpByBookmark(it) {
  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: it.library_id || props.libraryId,
        docId: it.doc_id || props.docId,
        spanIndex: spanOf(it),
        reader: it.reader || props.reader || null
      }
    })
  )
  close()
}

async function addAnnotation() {
  const text = String(annotationInput.value || '').trim()
  if (!text) return

  loadingAnnotation.value = true
  try {
    const res = await callTool(
      'nisb_span_annotation_add',
      {
        library_id: props.libraryId,
        doc_id: props.docId,
        span_index: Number(props.spanIndex || 0),
        content: text,
        reader: props.reader || null
      },
      { trackLoading: false }
    )
    if (res?.status === 'success') {
      annotationInput.value = ''
      window.dispatchEvent(new CustomEvent('nisb-annotation-updated', { detail: { annotation: res.annotation } }))
      await refreshAnnotations()
    } else {
      alert('❌ 添加批注失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('❌ 添加批注失败：' + (e?.message || String(e)))
  } finally {
    loadingAnnotation.value = false
  }
}

async function delAnnotation(it) {
  const aid = annotationIdOf(it)
  if (!aid) {
    alert('❌ 移除失败：annotation_id 不能为空')
    return
  }
  if (!confirm(`移除批注？\n\nSpan ${spanOf(it)}\n${it.content}`)) return

  loadingAnnotation.value = true
  try {
    const res = await callTool('nisb_span_annotation_delete', { annotation_id: aid }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-annotation-updated', { detail: { annotation_id: aid } }))
      await refreshAnnotations()
    } else {
      alert('❌ 移除失败：' + (res?.message || '未知错误'))
    }
  } catch (e) {
    alert('❌ 移除失败：' + (e?.message || String(e)))
  } finally {
    loadingAnnotation.value = false
  }
}

function jumpByAnnotation(it) {
  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: it.library_id || props.libraryId,
        docId: it.doc_id || props.docId,
        spanIndex: spanOf(it),
        reader: it.reader || props.reader || null
      }
    })
  )
  close()
}

function onBookmarkUpdated() {
  if (!props.open) return
  if (tab.value !== 'bookmark') return
  refreshBookmarks()
}
function onAnnotationUpdated() {
  if (!props.open) return
  if (tab.value !== 'annotation') return
  refreshAnnotations()
}

watch(
  () => props.open,
  (v) => {
    if (v) refreshActiveTab()
  }
)
watch(
  () => tab.value,
  () => refreshActiveTab()
)
watch(
  () => [props.libraryId, props.docId, props.spanIndex],
  () => refreshActiveTab()
)

onMounted(() => {
  window.addEventListener('nisb-bookmark-updated', onBookmarkUpdated)
  window.addEventListener('nisb-annotation-updated', onAnnotationUpdated)
})

onUnmounted(() => {
  window.removeEventListener('nisb-bookmark-updated', onBookmarkUpdated)
  window.removeEventListener('nisb-annotation-updated', onAnnotationUpdated)
})
</script>

<style scoped>
/* 这套风格直接对齐 LibraryDetail.vue 的批量删除弹窗 */
.nisb-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.nisb-modal {
  width: min(520px, calc(100vw - 24px));
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  padding: 0.9rem 1rem;
}

.nisb-modal-mid {
  width: min(600px, calc(100vw - 24px));
}

.nisb-modal-title {
  font-size: 0.95rem;
  color: var(--text);
}

.nisb-modal-body {
  margin-top: 0.55rem;
  font-size: 0.85rem;
}

.muted {
  color: var(--text-secondary);
  line-height: 1.5;
}

.nisb-modal-actions {
  margin-top: 0.8rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.modal-btn {
  padding: 0.35rem 0.75rem;
  border-radius: 5px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
}
.modal-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.nisb-input {
  width: 100%;
  padding: 0.55rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 0.9rem;
}
.nisb-input:focus {
  border-color: var(--selected);
  box-shadow: 0 2px 10px rgba(60, 105, 188, 0.12);
}

.mini-btn {
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
  white-space: nowrap;
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

.tabs {
  margin-top: 0.6rem;
  display: flex;
  gap: 0.4rem;
  align-items: center;
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
.tab-meta {
  margin-left: auto;
  font-size: 0.78rem;
}

.toolbar {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
  margin-top: 0.2rem;
}

.add-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.55rem;
}

.tip {
  padding: 0.75rem 0.2rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.scroll-list {
  max-height: calc(100vh - 340px);
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
.item.highlight {
  border-color: rgba(60, 105, 188, 0.55);
  background: rgba(60, 105, 188, 0.08);
}
.item-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.item-title {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  min-width: 0;
  font-size: 0.9rem;
  color: var(--text);
}
.item-sub {
  margin-top: 0.15rem;
  font-size: 0.78rem;
}
.item-note {
  margin-top: 0.35rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.35;
  white-space: normal;
}
.pill {
  flex-shrink: 0;
  font-size: 0.72rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.08rem 0.4rem;
  color: var(--text-secondary);
}
.item-del {
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
.item-del:hover {
  background: rgba(120, 120, 120, 0.1);
  border-color: var(--selected);
  color: var(--selected);
  opacity: 1;
}
</style>

