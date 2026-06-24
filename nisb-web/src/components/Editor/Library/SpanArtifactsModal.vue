<template>
  <teleport to=".app">
    <div v-if="open" class="nisb-modal-mask" @click.self="close">
      <div class="nisb-modal nisb-modal-mid">
        <div class="nisb-modal-title">
          {{ t('library.center.spanArtifacts.title') }}
          <span class="muted" style="margin-left: 0.5rem;">
            {{ libraryId }} · {{ docId }} · {{ t('library.center.spanArtifacts.spanLabel', { span: spanIndex }) }}
          </span>
        </div>

        <div class="tabs">
          <button class="tab-btn" :class="{ active: tab === 'bookmark' }" @click="tab = 'bookmark'" type="button">
            {{ t('library.center.spanArtifacts.tabs.bookmark') }}
          </button>
          <button class="tab-btn" :class="{ active: tab === 'annotation' }" @click="tab = 'annotation'" type="button">
            {{ t('library.center.spanArtifacts.tabs.annotation') }}
          </button>

          <div class="tab-meta muted">
            {{
              t('library.center.spanArtifacts.tabMeta', {
                bookmarks: bookmarks.length,
                annotations: annotations.length
              })
            }}
          </div>
        </div>

        <div class="nisb-modal-body">
          <div v-if="tab === 'bookmark'">
            <div class="toolbar">
              <button class="mini-btn" :disabled="loadingBookmark" @click="addBookmark" type="button">
                {{
                  loadingBookmark
                    ? t('library.center.spanArtifacts.bookmark.processing')
                    : t('library.center.spanArtifacts.bookmark.add')
                }}
              </button>
            </div>

            <div v-if="loadingBookmark" class="tip">
              {{ t('library.center.spanArtifacts.bookmark.loading') }}
            </div>
            <div v-else-if="!bookmarks.length" class="tip">
              {{ t('library.center.spanArtifacts.bookmark.empty') }}
            </div>

            <div v-else class="list scroll-list">
              <div
                v-for="it in bookmarks"
                :key="bookmarkKey(it)"
                class="item"
                :class="{ highlight: Number(spanOf(it)) === Number(spanIndex) }"
              >
                <div class="item-main" @click="jumpByBookmark(it)">
                  <div class="item-title">
                    {{ it.title || t('library.center.spanArtifacts.spanLabel', { span: spanOf(it) }) }}
                    <span class="pill">{{ t('library.center.spanArtifacts.spanLabel', { span: spanOf(it) }) }}</span>
                  </div>
                  <div class="item-sub muted">{{ formatTime(it.created_at) }}</div>
                  <div v-if="it.note" class="item-note">{{ it.note }}</div>
                </div>

                <button
                  class="item-del"
                  :title="t('library.center.spanArtifacts.bookmark.remove')"
                  @click.stop="delBookmark(it)"
                  type="button"
                >
                  ×
                </button>
              </div>
            </div>
          </div>

          <div v-else>
            <div class="add-row">
              <input
                v-model="annotationInput"
                class="nisb-input"
                :placeholder="t('library.center.spanArtifacts.annotation.placeholder')"
                @keydown.enter.prevent="addAnnotation"
              />
              <button class="mini-btn" :disabled="loadingAnnotation" @click="addAnnotation" type="button">
                {{
                  loadingAnnotation
                    ? t('library.center.spanArtifacts.annotation.submitting')
                    : t('library.center.spanArtifacts.annotation.add')
                }}
              </button>
            </div>

            <div v-if="loadingAnnotation" class="tip">
              {{ t('library.center.spanArtifacts.annotation.loading') }}
            </div>
            <div v-else-if="!annotations.length" class="tip">
              {{ t('library.center.spanArtifacts.annotation.empty') }}
            </div>

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
                    <span class="pill">{{ t('library.center.spanArtifacts.spanLabel', { span: spanOf(it) }) }}</span>
                  </div>
                  <div class="item-sub muted">{{ formatTime(it.created_at) }}</div>
                  <div class="item-note">{{ it.content }}</div>
                </div>

                <button
                  class="item-del"
                  :title="t('library.center.spanArtifacts.annotation.remove')"
                  @click.stop="delAnnotation(it)"
                  type="button"
                >
                  ×
                </button>
              </div>
            </div>

            <div class="muted" style="margin-top: 0.6rem; font-size: 0.82rem;">
              {{ t('library.center.spanArtifacts.annotation.hint') }}
            </div>
          </div>
        </div>

        <div class="nisb-modal-actions">
          <button class="modal-btn" @click="close" type="button">
            {{ t('library.center.spanArtifacts.close') }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'

const props = defineProps({
  open: { type: Boolean, default: false },
  libraryId: { type: String, required: true },
  docId: { type: String, required: true },
  spanIndex: { type: Number, required: true },
  reader: { type: Object, default: null }
})

const emit = defineEmits(['close'])
const { t } = useI18n()
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
  const t0 = String(s || '').trim().replace(/\s+/g, ' ')
  return t0.length > 50 ? t0.slice(0, 50) + '…' : t0
}

function _n(v) {
  const x = Number(v)
  return Number.isFinite(x) ? x : null
}

function spanOf(it) {
  return _n(it?.span_index) ?? 0
}

function bookmarkIdOf(it) {
  return it?.bookmark_id ?? null
}

function annotationIdOf(it) {
  return it?.annotation_id ?? null
}

function bookmarkKey(it) {
  return String(bookmarkIdOf(it) ?? `${props.docId}:${spanOf(it)}`)
}

function annotationKey(it) {
  return String(annotationIdOf(it) ?? `${props.docId}:${spanOf(it)}`)
}

function dispatchOpenLibraryDocStable(payload) {
  if (!payload?.libraryId || !payload?.docId) return

  if (payload.reader) window.nisbReaderState = payload.reader

  const fire = () => {
    window.dispatchEvent(new CustomEvent('nisb-open-library-doc', { detail: payload }))
  }

  fire()
  setTimeout(fire, 60)
  setTimeout(fire, 220)
  setTimeout(fire, 700)
}

async function refreshBookmarks() {
  loadingBookmark.value = true
  try {
    const res = await callTool(
      'nisb_bookmark_list',
      { library_id: props.libraryId, doc_id: props.docId },
      { trackLoading: false }
    )
    bookmarks.value = res?.status === 'success' ? res.bookmarks || [] : []
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
      { library_id: props.libraryId, doc_id: props.docId },
      { trackLoading: false }
    )
    annotations.value = res?.status === 'success' ? res.annotations || [] : []
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

async function addBookmark() {
  loadingBookmark.value = true
  try {
    const res = await callTool(
      'nisb_bookmark_add',
      {
        library_id: props.libraryId,
        doc_id: props.docId,
        span_index: Number(props.spanIndex || 0),
        title: t('library.center.spanArtifacts.spanLabel', { span: Number(props.spanIndex || 0) }),
        note: '',
        reader: props.reader || window.nisbReaderState || null
      },
      { trackLoading: false }
    )
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated', { detail: { bookmark: res.bookmark } }))
      await refreshBookmarks()
    } else {
      alert(
        t('library.center.spanArtifacts.bookmark.addFailed', {
          message: res?.message || t('library.center.spanArtifacts.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('library.center.spanArtifacts.bookmark.addFailed', {
        message: e?.message || String(e)
      })
    )
  } finally {
    loadingBookmark.value = false
  }
}

async function delBookmark(it) {
  const bid = bookmarkIdOf(it)
  if (!bid) {
    alert(t('library.center.spanArtifacts.bookmark.removeMissingId'))
    return
  }

  const ok = confirm(
    t('library.center.spanArtifacts.bookmark.removeConfirm', {
      title: it.title || t('library.center.spanArtifacts.spanLabel', { span: spanOf(it) })
    })
  )
  if (!ok) return

  loadingBookmark.value = true
  try {
    const res = await callTool('nisb_bookmark_delete', { bookmark_id: bid }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-bookmark-updated', { detail: { bookmark_id: bid } }))
      await refreshBookmarks()
    } else {
      alert(
        t('library.center.spanArtifacts.bookmark.removeFailed', {
          message: res?.message || t('library.center.spanArtifacts.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('library.center.spanArtifacts.bookmark.removeFailed', {
        message: e?.message || String(e)
      })
    )
  } finally {
    loadingBookmark.value = false
  }
}

function jumpByBookmark(it) {
  const payload = {
    libraryId: String(it?.library_id || props.libraryId || '').trim(),
    docId: String(it?.doc_id || props.docId || '').trim(),
    spanIndex: Number(spanOf(it) || 0),
    reader: it?.reader || props.reader || window.nisbReaderState || null
  }
  dispatchOpenLibraryDocStable(payload)
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
        reader: props.reader || window.nisbReaderState || null
      },
      { trackLoading: false }
    )
    if (res?.status === 'success') {
      annotationInput.value = ''
      window.dispatchEvent(new CustomEvent('nisb-span-annotation-updated', { detail: { annotation: res.annotation } }))
      await refreshAnnotations()
    } else {
      alert(
        t('library.center.spanArtifacts.annotation.addFailed', {
          message: res?.message || t('library.center.spanArtifacts.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('library.center.spanArtifacts.annotation.addFailed', {
        message: e?.message || String(e)
      })
    )
  } finally {
    loadingAnnotation.value = false
  }
}

async function delAnnotation(it) {
  const aid = annotationIdOf(it)
  if (!aid) {
    alert(t('library.center.spanArtifacts.annotation.removeMissingId'))
    return
  }

  const ok = confirm(
    t('library.center.spanArtifacts.annotation.removeConfirm', {
      span: spanOf(it),
      content: it.content || ''
    })
  )
  if (!ok) return

  loadingAnnotation.value = true
  try {
    const res = await callTool('nisb_span_annotation_delete', { annotation_id: aid }, { trackLoading: false })
    if (res?.status === 'success') {
      window.dispatchEvent(new CustomEvent('nisb-span-annotation-updated', { detail: { annotation_id: aid } }))
      await refreshAnnotations()
    } else {
      alert(
        t('library.center.spanArtifacts.annotation.removeFailed', {
          message: res?.message || t('library.center.spanArtifacts.unknownError')
        })
      )
    }
  } catch (e) {
    alert(
      t('library.center.spanArtifacts.annotation.removeFailed', {
        message: e?.message || String(e)
      })
    )
  } finally {
    loadingAnnotation.value = false
  }
}

function jumpByAnnotation(it) {
  const payload = {
    libraryId: String(it?.library_id || props.libraryId || '').trim(),
    docId: String(it?.doc_id || props.docId || '').trim(),
    spanIndex: Number(spanOf(it) || 0),
    reader: it?.reader || props.reader || window.nisbReaderState || null
  }
  dispatchOpenLibraryDocStable(payload)
  close()
}

function onBookmarkUpdated() {
  if (!props.open) return
  if (tab.value !== 'bookmark') return
  refreshBookmarks()
}

function onSpanAnnotationUpdated() {
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
  window.addEventListener('nisb-span-annotation-updated', onSpanAnnotationUpdated)
})

onUnmounted(() => {
  window.removeEventListener('nisb-bookmark-updated', onBookmarkUpdated)
  window.removeEventListener('nisb-span-annotation-updated', onSpanAnnotationUpdated)
})
</script>

<style scoped>
.nisb-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  box-sizing: border-box;
  padding: 1.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--selected) 12%, transparent), transparent 42%),
    rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.nisb-modal {
  width: min(640px, calc(100vw - 24px));
  max-height: min(760px, calc(100vh - 24px));
  min-width: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 92%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 22px 60px rgba(0, 0, 0, 0.26);
  overflow: hidden;
}

.nisb-modal-mid {
  width: min(680px, calc(100vw - 24px));
}

.nisb-modal-title {
  min-width: 0;
  padding: 0.86rem 0.94rem 0.7rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1.32;
  overflow-wrap: break-word;
}

.nisb-modal-title .muted {
  display: inline-block;
  max-width: 100%;
  vertical-align: middle;
}

.tabs {
  min-width: 0;
  padding: 0.62rem 0.72rem;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tab-btn {
  flex: 0 0 auto;
  min-height: 31px;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.tab-btn:hover,
.tab-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.tab-btn.active {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
  color: var(--selected);
}

.tab-btn:active {
  transform: translateY(1px);
}

.tab-meta {
  flex: 0 0 auto;
  margin-left: auto;
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  font-size: 0.7rem;
  font-weight: 730;
  white-space: nowrap;
}

.nisb-modal-body {
  min-width: 0;
  min-height: 0;
  padding: 0.72rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  font-size: 0.84rem;
}

.nisb-modal-body::-webkit-scrollbar {
  width: 8px;
}

.nisb-modal-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.muted {
  color: var(--text-secondary);
  line-height: 1.5;
  overflow-wrap: break-word;
}

.nisb-modal-actions {
  min-width: 0;
  padding: 0.68rem 0.82rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.modal-btn,
.mini-btn,
.item-del {
  font-family: inherit;
}

.modal-btn {
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
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
    transform 0.12s ease;
}

.modal-btn:hover,
.modal-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.modal-btn:active {
  transform: translateY(1px);
}

.nisb-input {
  width: 100%;
  min-width: 0;
  min-height: 36px;
  box-sizing: border-box;
  padding: 0.5rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 12px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.35;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.nisb-input:focus {
  border-color: color-mix(in srgb, var(--selected) 50%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 84%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

.mini-btn {
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
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

.mini-btn:hover:not(:disabled),
.mini-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.mini-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mini-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.toolbar {
  min-width: 0;
  display: flex;
  gap: 0.42rem;
  margin: 0 0 0.58rem;
}

.add-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.62rem;
}

.tip {
  box-sizing: border-box;
  padding: 0.9rem 0.78rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.list {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 0.46rem;
}

.scroll-list {
  max-height: min(440px, calc(100vh - 330px));
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 0.25rem;
  scrollbar-width: thin;
}

.scroll-list::-webkit-scrollbar {
  width: 8px;
}

.scroll-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.item {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.58rem;
  align-items: start;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 15px;
  padding: 0.64rem 0.68rem;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 5%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.item:hover,
.item:focus-within {
  border-color: color-mix(in srgb, var(--selected) 32%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 12px 24px rgba(0, 0, 0, 0.075);
}

.item.highlight {
  border-color: color-mix(in srgb, var(--selected) 54%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 56%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
}

.item-main {
  min-width: 0;
  cursor: pointer;
}

.item-title {
  min-width: 0;
  display: flex;
  gap: 0.42rem;
  align-items: center;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.36;
  overflow-wrap: break-word;
}

.item-sub {
  margin-top: 0.18rem;
  font-size: 0.72rem;
}

.item-note {
  margin-top: 0.42rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.48;
  white-space: normal;
  overflow-wrap: break-word;
}

.pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  box-sizing: border-box;
  padding: 0 0.46rem;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 30%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
}

.item-del {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border: 1px solid color-mix(in srgb, rgba(239, 68, 68, 0.55) 50%, var(--line));
  border-radius: 10px;
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.08),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  color: #ef4444;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  opacity: 0.82;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.item-del:hover,
.item-del:focus-visible {
  border-color: rgba(239, 68, 68, 0.62);
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.15),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 8px 18px rgba(0, 0, 0, 0.08);
  opacity: 1;
  outline: none;
}

.item-del:active {
  transform: translateY(1px);
}

@media (max-width: 620px) {
  .nisb-modal-mask {
    padding: 0.7rem;
    align-items: stretch;
  }

  .nisb-modal,
  .nisb-modal-mid {
    width: 100%;
    max-height: 100%;
  }

  .nisb-modal-title {
    padding: 0.78rem 0.78rem 0.64rem;
  }

  .tabs {
    padding: 0.58rem 0.66rem;
  }

  .tab-meta {
    margin-left: 0;
  }

  .nisb-modal-body {
    padding: 0.66rem;
  }

  .add-row {
    grid-template-columns: 1fr;
  }

  .mini-btn,
  .modal-btn {
    width: 100%;
  }

  .nisb-modal-actions {
    justify-content: stretch;
  }
}

@media (max-width: 420px) {
  .nisb-modal-mask {
    padding: 0;
  }

  .nisb-modal,
  .nisb-modal-mid {
    border-radius: 0;
    border-left: 0;
    border-right: 0;
  }

  .tabs {
    flex-wrap: nowrap;
  }

  .item {
    grid-template-columns: minmax(0, 1fr);
  }

  .item-del {
    justify-self: start;
  }

  .item-title {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
