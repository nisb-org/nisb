<template>
  <div class="library-container">
    <div class="library-header">
      <span class="library-title">{{ t('library.left.title') }}</span>
      <div class="library-header-actions">
        <button class="group-library-btn" @click="openGroupsModal" :title="t('library.left.actions.groups')">
          {{ t('library.left.actions.groupsShort') }}
        </button>

        <button
          class="hover-open-btn"
          :class="{ on: hover_open_enabled }"
          type="button"
          @click="toggle_hover_open"
          :title="hover_open_enabled ? t('library.left.actions.hoverOpenOn') : t('library.left.actions.hoverOpenOff')"
        >
          {{ t('library.left.actions.hoverOpenShort') }}
        </button>

        <button class="new-library-btn" @click="createNewLibrary" :title="t('library.left.actions.create')">＋</button>
      </div>
    </div>

    <div ref="library_list_el" class="library-list">
      <div v-if="loading" class="empty-tip">{{ t('library.left.loading') }}</div>
      <div v-else-if="!libraries.length" class="empty-tip">{{ t('library.left.empty') }}</div>

      <div v-else v-for="library in libraries" :key="library.library_id" class="library-block">
        <div
          class="library-item"
          :ref="(el) => set_library_row_el(library.library_id, el)"
          :class="{ active: library.library_id === currentLibraryId }"
          @click="openLibrary(library)"
          @mouseenter="onLibraryMouseEnter(library)"
          @mouseleave="onLibraryMouseLeave(library)"
          @contextmenu.prevent="showLibraryContextMenu($event, library)"
        >
          <button
            class="fold-btn"
            :style="fold_btn_style(library)"
            @click.stop="toggleLibraryExpand(library.library_id)"
            @mouseenter.stop="onFoldEnter(library.library_id)"
            @mouseleave.stop="onFoldLeave(library.library_id)"
            :title="isExpanded(library.library_id) ? t('library.left.collapseDocs') : t('library.left.expandDocs')"
          >
            {{ isExpanded(library.library_id) ? '▾' : '▸' }}
          </button>

          <div class="library-icon">{{ library.icon }}</div>

          <div class="library-info">
            <div class="library-name">{{ library.library_name }}</div>
            <div class="library-meta">{{ t('library.left.docCount', { count: library_doc_count(library) }) }}</div>
          </div>
        </div>

        <transition name="fade-collapse">
          <div v-if="isExpanded(library.library_id)" class="docs-wrapper">
            <div v-if="docsState(library.library_id).loading" class="docs-tip">{{ t('library.left.docsLoading') }}</div>
            <div v-else-if="!docsState(library.library_id).docs.length" class="docs-tip">{{ t('library.left.docsEmpty') }}</div>

            <div
              v-else
              v-for="doc in docsState(library.library_id).docs"
              :key="doc.doc_id"
              class="doc-row"
              :class="{
                active: library.library_id === currentLibraryId && doc.doc_id === currentDocId,
                hovering: hoveringDocId === doc.doc_id
              }"
              @click="openLibraryDoc(library, doc)"
              @mouseenter="onDocMouseEnter(library, doc)"
              @mouseleave="onDocMouseLeave(doc)"
              :title="doc.filename || doc.doc_id"
            >
              <span class="doc-title">{{ doc.filename || doc.doc_id }}</span>
              <span class="doc-meta-breath">
                {{ t('library.left.docMeta', { filetype: doc.filetype || 'txt', chunks: doc.chunks || 0 }) }}
              </span>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <div v-if="createModalOpen" class="nisb-modal-mask" @click.self="closeCreateModal">
      <div
        class="nisb-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="t('library.left.create.title')"
      >
        <div class="nisb-modal-header">
          <div class="nisb-modal-title">{{ t('library.left.create.title') }}</div>
          <button
            class="modal-close-btn"
            type="button"
            @click="closeCreateModal"
            :aria-label="t('library.left.create.close')"
          >
            ✕
          </button>
        </div>

        <div class="nisb-modal-body">
          <div class="create-preview">
            <span class="preview-dot" :style="{ background: createColor || '#3B82F6' }"></span>
            <span class="preview-icon" :title="createIcon">{{ createIcon }}</span>
            <span class="preview-name" :title="createName || t('library.left.create.unnamed')">
              {{ createName || t('library.left.create.unnamed') }}
            </span>
            <span class="preview-id mono" :title="createId || ''">{{ createId || '' }}</span>
          </div>

          <div class="create-grid">
            <section class="create-card">
              <div class="card-title">{{ t('library.left.create.basicInfo') }}</div>

              <div class="form-row">
                <div class="label">{{ t('library.left.create.nameLabel') }}</div>
                <input
                  ref="nameInputRef"
                  class="nisb-input"
                  v-model="createName"
                  :placeholder="t('library.left.create.namePlaceholder')"
                  @keydown.enter.prevent="submitCreateLibrary"
                />
                <div class="hint muted">{{ t('library.left.create.nameHint') }}</div>
              </div>

              <div class="form-row">
                <div class="label">{{ t('library.left.create.idLabel') }}</div>
                <input
                  class="nisb-input mono"
                  v-model="createId"
                  :placeholder="t('library.left.create.idPlaceholder')"
                  @input="idTouched = true"
                  @keydown.enter.prevent="submitCreateLibrary"
                />
                <div class="hint muted">{{ t('library.left.create.idHint') }}</div>
              </div>
            </section>

            <section class="create-card">
              <div class="card-title">{{ t('library.left.create.appearance') }}</div>

              <div class="form-row">
                <div class="label">{{ t('library.left.create.iconLabel') }}</div>
                <div class="icon-grid">
                  <button
                    v-for="ic in iconOptions"
                    :key="ic"
                    class="icon-btn"
                    :class="{ active: createIcon === ic }"
                    type="button"
                    @click="createIcon = ic"
                    :title="ic"
                  >
                    {{ ic }}
                  </button>
                </div>
                <div class="hint muted">
                  {{ t('library.left.create.currentIcon') }}<span class="mono">{{ createIcon }}</span>
                </div>
              </div>

              <div class="form-row">
                <div class="label">{{ t('library.left.create.colorLabel') }}</div>
                <div class="color-row">
                  <button
                    v-for="c in colorOptions"
                    :key="c"
                    class="color-dot"
                    :class="{ active: createColor === c }"
                    type="button"
                    :style="{ background: c }"
                    @click="createColor = c"
                    :title="c"
                  ></button>

                  <input
                    class="nisb-input mono color-input"
                    v-model="createColor"
                    :placeholder="t('library.left.create.colorPlaceholder')"
                  />
                </div>
                <div class="hint muted">{{ t('library.left.create.colorHint') }}</div>
              </div>

              <div class="form-row">
                <div class="label">{{ t('library.left.create.quickPickLabel') }}</div>
                <div class="quick-row">
                  <button class="mini-btn" type="button" :disabled="!libraries.length" @click="applyFromExisting(0)">
                    {{ t('library.left.create.useFirstLibraryStyle') }}
                  </button>
                  <button class="mini-btn" type="button" :disabled="!libraries.length" @click="applyFromExisting(1)">
                    {{ t('library.left.create.useSecondLibraryStyle') }}
                  </button>
                  <button class="mini-btn" type="button" @click="randomIcon">
                    {{ t('library.left.create.randomIcon') }}
                  </button>
                </div>
                <div class="hint muted">{{ t('library.left.create.quickPickHint') }}</div>
              </div>
            </section>
          </div>
        </div>

        <div class="nisb-modal-actions">
          <button class="modal-btn" :disabled="createWorking" @click="closeCreateModal">
            {{ t('library.left.create.cancel') }}
          </button>
          <button class="modal-btn primary" :disabled="createWorking" @click="submitCreateLibrary">
            {{ createWorking ? t('library.left.create.creating') : t('library.left.create.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <LibraryGroupsModal v-if="groupsModalOpen" @close="closeGroupsModal" @saved="onGroupsSaved" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import LibraryGroupsModal from './LibraryGroupsModal.vue'
import { use_library_hover_open_toggle } from '../../composables/left_sidebar/use_library_hover_open_toggle'
import { use_library_list_scroll_anchor } from '../../composables/left_sidebar/use_library_list_scroll_anchor'
import { useLibrarySearchStore } from '../../stores/librarySearch'

const { t } = useI18n()
const { callTool } = useMCP()
const library_search_store = useLibrarySearchStore()
const emit = defineEmits(['show-context-menu'])

const libraries = ref([])
const loading = ref(false)
const currentLibraryId = ref(null)
const currentDocId = ref(null)

const expandedLibraryId = ref(null)
const libraryDocsMap = ref({})

const HOVER_DELAY = 600
const FOLD_HOVER_DELAY = 120

let _library_hover_timer = null
let _library_hover_id = null

let _doc_hover_timer = null
let _doc_hover_key = null

let _pulse_seq = 0
let _pulse_timer_a = null
let _pulse_timer_b = null

const hoveringDocId = ref(null)
const foldHoverTimers = new Map()

const createModalOpen = ref(false)
const createWorking = ref(false)

const createName = ref('')
const createId = ref('')
const createIcon = ref('📚')
const createColor = ref('#3B82F6')
const idTouched = ref(false)

const nameInputRef = ref(null)

const iconOptions = ['📚', '📖', '🗂️', '🏛️', '📘', '📗', '📕', '📙', '🧠', '🧾', '🔖', '🧩', '🧪', '🧰', '🗃️', '📰']
const colorOptions = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#A855F7', '#06B6D4', '#64748B', '#111827']

const groupsModalOpen = ref(false)

const { hover_open_enabled, toggle_hover_open_enabled } = use_library_hover_open_toggle()

const {
  library_list_el,
  set_library_row_el,
  request_anchor_to_top,
  attach_transitionend_stabilizer,
  detach_transitionend_stabilizer
} = use_library_list_scroll_anchor()

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function _hex_with_alpha(hex, aa) {
  const s = String(hex || '').trim()
  if (/^#[0-9a-fA-F]{6}$/.test(s)) return `${s}${aa}`
  return s || '#64748B'
}

function fold_btn_style(library) {
  const c = String(library?.color || '#64748B').trim() || '#64748B'
  return { color: c, borderColor: _hex_with_alpha(c, '55') }
}

let _doc_count_refresh_seq = 0
let _last_doc_count_refresh_at = 0

function _extract_docs_from_doc_stats(res) {
  const docs = Array.isArray(res?.documents)
    ? res.documents
    : Array.isArray(res?.raw?.documents)
      ? res.raw.documents
      : []
  return Array.isArray(docs) ? docs : []
}

function library_doc_count(library) {
  const id = String(library?.library_id || '')
  const st = libraryDocsMap.value?.[id]
  if (st && Array.isArray(st.docs)) return st.docs.length || 0
  return Number.isFinite(Number(library?.doc_count)) ? Number(library.doc_count) : 0
}

function syncLibraryDocCount(libraryId, count) {
  const idx = libraries.value.findIndex((l) => l.library_id === libraryId)
  if (idx < 0) return
  const cur = libraries.value[idx]
  if (!cur) return
  if (Number.isInteger(count) && count >= 0 && cur.doc_count !== count) {
    libraries.value[idx] = { ...cur, doc_count: count }
  }
}

async function refresh_doc_counts_in_background() {
  const now = Date.now()
  if (now - _last_doc_count_refresh_at < 12000) return
  _last_doc_count_refresh_at = now

  const seq = ++_doc_count_refresh_seq
  const list = Array.isArray(libraries.value) ? libraries.value.slice(0) : []
  if (!list.length) return
  if (list.length > 80) return

  for (const lib of list) {
    if (seq !== _doc_count_refresh_seq) return
    const id = String(lib?.library_id || '')
    if (!id) continue
    try {
      const res = await callTool('nisb_doc_stats', { library_id: id })
      if (res && res.status === 'success') {
        const docs = _extract_docs_from_doc_stats(res)
        syncLibraryDocCount(id, docs.length)
      }
    } catch {}
  }
}

function toggle_hover_open() {
  toggle_hover_open_enabled()
  _cancel_all_hover()
  foldHoverTimers.forEach((t) => clearTimeout(t))
  foldHoverTimers.clear()
}

function openGroupsModal() {
  groupsModalOpen.value = true
}
function closeGroupsModal() {
  groupsModalOpen.value = false
}

async function onGroupsSaved() {
  await loadLibraries()
  window.dispatchEvent(new CustomEvent('nisb-library-updated'))
}

function _cancel_library_hover() {
  if (_library_hover_timer) {
    clearTimeout(_library_hover_timer)
    _library_hover_timer = null
  }
  _library_hover_id = null
}
function _cancel_doc_hover() {
  if (_doc_hover_timer) {
    clearTimeout(_doc_hover_timer)
    _doc_hover_timer = null
  }
  _doc_hover_key = null
}
function _cancel_all_hover() {
  _cancel_library_hover()
  _cancel_doc_hover()
}

function normalizeId(raw) {
  let s = String(raw || '').trim().toLowerCase()
  s = s.replace(/\s+/g, '_')
  s = s.replace(/[^a-z0-9_-]/g, '')
  s = s.replace(/_+/g, '_')
  s = s.replace(/^[-_]+/, '')
  s = s.replace(/[-_]+$/, '')
  return s
}
function isValidLibraryId(id) {
  const v = String(id || '')
  if (!v) return false
  if (!/^[a-z0-9][a-z0-9_-]{0,127}$/.test(v)) return false
  if (!/[a-z0-9]/.test(v)) return false
  return true
}
function makeSafeLibraryId(name) {
  const base = normalizeId(name)
  if (isValidLibraryId(base)) return base
  return `lib_${Date.now().toString(36).slice(-6)}`
}

watch(
  () => createName.value,
  (val) => {
    if (idTouched.value) return
    createId.value = makeSafeLibraryId(val)
  }
)

function openCreateModal() {
  createName.value = ''
  createId.value = ''
  createIcon.value = '📚'
  createColor.value = '#3B82F6'
  idTouched.value = false
  createModalOpen.value = true
  nextTick(() => {
    try {
      nameInputRef.value?.focus?.()
    } catch {}
  })
}
function closeCreateModal() {
  if (createWorking.value) return
  createModalOpen.value = false
}
function applyFromExisting(index) {
  const lib = libraries.value[index]
  if (!lib) return
  if (lib.icon) createIcon.value = lib.icon
  if (lib.color) createColor.value = lib.color
}
function randomIcon() {
  const i = Math.floor(Math.random() * iconOptions.length)
  createIcon.value = iconOptions[i]
}

async function submitCreateLibrary() {
  if (createWorking.value) return

  const name = String(createName.value || '').trim()
  let id = normalizeId(createId.value)

  if (!name) return toast(t('library.left.messages.nameRequired'), 'error')

  if (!idTouched.value || !isValidLibraryId(id)) {
    id = makeSafeLibraryId(name)
    createId.value = id
  }

  if (!isValidLibraryId(id)) {
    return toast(t('library.left.messages.invalidId'), 'error')
  }

  createWorking.value = true
  try {
    const result = await callTool('nisb_library_create', {
      library_id: id,
      library_name: name,
      icon: createIcon.value || '📚',
      color: createColor.value || '#3B82F6'
    })

    if (result && result.status === 'success') {
      toast(`✅ ${result.message || t('library.left.messages.createSuccess')}`, 'success')
      createModalOpen.value = false
      await loadLibraries()

      const created =
        libraries.value.find((x) => x.library_id === id) || {
          library_id: id,
          library_name: name,
          icon: createIcon.value,
          color: createColor.value,
          doc_count: 0
        }
      openLibrary(created, { trigger: 'click' })
    } else {
      toast(
        t('library.left.messages.createFailed', {
          error: result?.message || t('library.left.messages.unknownError')
        }),
        'error'
      )
    }
  } catch (e) {
    toast(
      t('library.left.messages.createFailed', {
        error: e?.message || t('library.left.messages.unknownError')
      }),
      'error'
    )
  } finally {
    createWorking.value = false
  }
}

function createNewLibrary() {
  openCreateModal()
}

function docsState(libraryId) {
  if (!libraryDocsMap.value[libraryId]) libraryDocsMap.value[libraryId] = { loading: false, docs: [] }
  return libraryDocsMap.value[libraryId]
}

function isExpanded(libraryId) {
  return expandedLibraryId.value === libraryId
}

async function loadLibraries() {
  loading.value = true
  try {
    const result = await callTool('nisb_library_list', {})
    if (result && result.status === 'success') {
      const rawList = result.libraries || []
      libraries.value = rawList.map((lib) => {
        const stats = lib.stats || {}
        return {
          library_id: lib.library_id || 'unknown_library',
          library_name: lib.library_name || lib.name || t('library.left.unnamedLibrary'),
          description: lib.description || '',
          icon: lib.icon || '🏛️',
          color: lib.color || '#3B82F6',
          doc_count: lib.doc_count != null ? lib.doc_count : stats.doc_count != null ? stats.doc_count : 0
        }
      })

      refresh_doc_counts_in_background()
    } else {
      libraries.value = []
    }
  } catch (e) {
    console.error('[LibraryList] loadLibraries failed:', e)
    libraries.value = []
  } finally {
    loading.value = false
  }
}

async function loadLibraryDocs(libraryId) {
  const state = docsState(libraryId)
  if (state.loading) return
  state.loading = true
  try {
    const res = await callTool('nisb_doc_stats', { library_id: libraryId })
    if (res && res.status === 'success') {
      const docs = _extract_docs_from_doc_stats(res)
      state.docs = docs.map((d) => ({
        doc_id: d.doc_id,
        filename: d.filename,
        filetype: d.filetype,
        chunks: d.chunks,
        created_at: d.created_at
      }))
      syncLibraryDocCount(libraryId, state.docs.length)
    } else {
      state.docs = []
      syncLibraryDocCount(libraryId, 0)
    }
  } catch (e) {
    console.error('[LibraryList] loadLibraryDocs failed:', e)
    state.docs = []
  } finally {
    state.loading = false
  }
}

function openLibrary(library, opts = {}) {
  const trigger = String(opts?.trigger || 'unknown')
  _cancel_all_hover()
  currentLibraryId.value = library.library_id

  window.dispatchEvent(
    new CustomEvent('nisb-open-library', {
      detail: { libraryId: library.library_id, libraryName: library.library_name, source: 'left_sidebar', trigger }
    })
  )
}

function openLibraryDoc(library, doc, opts = {}) {
  const trigger = String(opts?.trigger || 'unknown')
  _cancel_all_hover()

  currentLibraryId.value = library.library_id
  currentDocId.value = doc.doc_id

  const reader = (() => {
    try {
      return window.nisbReaderState ?? null
    } catch {
      return null
    }
  })()

  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: library.library_id,
        docId: doc.doc_id,
        spanIndex: null,
        reader,
        source: 'left_sidebar',
        trigger
      }
    })
  )
}

function onLibraryMouseEnter(library) {
  if (!hover_open_enabled.value) return
  const id = String(library?.library_id || '')
  _cancel_library_hover()
  _library_hover_id = id
  _library_hover_timer = setTimeout(() => {
    if (_library_hover_id !== id) return
    openLibrary(library, { trigger: 'hover' })
  }, HOVER_DELAY)
}

function onLibraryMouseLeave(library) {
  const id = String(library?.library_id || '')
  if (_library_hover_id === id) _cancel_library_hover()
}

function onDocMouseEnter(library, doc) {
  hoveringDocId.value = doc.doc_id
  _cancel_library_hover()
  if (!hover_open_enabled.value) return

  const key = `${String(library?.library_id || '')}::${String(doc?.doc_id || '')}`
  _cancel_doc_hover()
  _doc_hover_key = key
  _doc_hover_timer = setTimeout(() => {
    if (_doc_hover_key !== key) return
    openLibraryDoc(library, doc, { trigger: 'hover' })
  }, HOVER_DELAY)
}

function onDocMouseLeave() {
  hoveringDocId.value = null
  _cancel_doc_hover()
}

function onFoldEnter(libraryId) {
  if (!hover_open_enabled.value) return

  const id = String(libraryId || '')
  clearTimeout(foldHoverTimers.get(id))
  const timer = setTimeout(() => {
    if (expandedLibraryId.value === id) return
    expandedLibraryId.value = id
    if (!docsState(id).docs.length) loadLibraryDocs(id)
  }, FOLD_HOVER_DELAY)
  foldHoverTimers.set(id, timer)
}

function onFoldLeave(libraryId) {
  const id = String(libraryId || '')
  const tmr = foldHoverTimers.get(id)
  if (tmr) {
    clearTimeout(tmr)
    foldHoverTimers.delete(id)
  }
}

async function toggleLibraryExpand(libraryId) {
  const id = String(libraryId || '')
  _cancel_all_hover()

  if (expandedLibraryId.value === id) {
    expandedLibraryId.value = null
    return
  }

  expandedLibraryId.value = id
  await request_anchor_to_top(id, { offset: 6 })

  if (!docsState(id).docs.length) loadLibraryDocs(id)
}

function showLibraryContextMenu(e, library) {
  emit('show-context-menu', {
    x: e.clientX,
    y: e.clientY,
    targetType: 'library',
    targetId: library.library_id,
    targetName: library.library_name
  })
}

function onKeydownEsc(e) {
  if (e.key !== 'Escape') return
  if (createModalOpen.value) closeCreateModal()
  if (groupsModalOpen.value) closeGroupsModal()
}

function onExternalOpenLibraryDoc(e) {
  const { libraryId, docId } = e?.detail || {}
  if (libraryId) currentLibraryId.value = libraryId
  if (docId) currentDocId.value = docId
}

function build_workspace_snapshot_detail(request_id = '') {
  const snap = library_search_store.get_workspace_snapshot()
  return {
    request_id: String(request_id || '').trim(),
    workspace_id: String(snap.workspace_id || '').trim(),
    workspace_name: String(snap.workspace_name || '').trim(),
    focus_root: String(snap.focus_root || '').trim(),
    focus_label: String(snap.focus_label || '').trim(),
    source: 'left_sidebar_library_list'
  }
}

function on_workspace_snapshot_request(event) {
  const detail = event?.detail || {}
  const request_id = String(detail?.request_id || '').trim()
  window.dispatchEvent(
    new CustomEvent('nisb_workspace_snapshot_response', {
      detail: build_workspace_snapshot_detail(request_id)
    })
  )
}

function on_room_apply_workspace_context(event) {
  const detail = event?.detail || {}
  library_search_store.set_workspace_context({
    workspace_id: detail?.workspace_id,
    workspace_name: detail?.workspace_name,
    focus_root: detail?.focus_root,
    focus_label: detail?.focus_label
  })
}

function on_room_clear_workspace_context(event) {
  const detail = event?.detail || {}
  library_search_store.clear_workspace_context({
    clear_workspace: !!detail?.clear_workspace,
    clear_focus_root: !!detail?.clear_focus_root
  })
}

onMounted(() => {
  attach_transitionend_stabilizer()
  loadLibraries()
  window.addEventListener('nisb-library-updated', loadLibraries)
  window.addEventListener('nisb-open-library-doc', onExternalOpenLibraryDoc)
  window.addEventListener('keydown', onKeydownEsc)
  window.addEventListener('nisb_workspace_snapshot_request', on_workspace_snapshot_request)
  window.addEventListener('nisb_room_apply_workspace_context', on_room_apply_workspace_context)
  window.addEventListener('nisb_room_clear_workspace_context', on_room_clear_workspace_context)
})

onUnmounted(() => {
  detach_transitionend_stabilizer()
  window.removeEventListener('nisb-library-updated', loadLibraries)
  window.removeEventListener('nisb-open-library-doc', onExternalOpenLibraryDoc)
  window.removeEventListener('keydown', onKeydownEsc)
  window.removeEventListener('nisb_workspace_snapshot_request', on_workspace_snapshot_request)
  window.removeEventListener('nisb_room_apply_workspace_context', on_room_apply_workspace_context)
  window.removeEventListener('nisb_room_clear_workspace_context', on_room_clear_workspace_context)

  _cancel_all_hover()

  if (_pulse_timer_a) clearTimeout(_pulse_timer_a)
  if (_pulse_timer_b) clearTimeout(_pulse_timer_b)
  _pulse_timer_a = null
  _pulse_timer_b = null

  foldHoverTimers.forEach((tmr) => clearTimeout(tmr))
  foldHoverTimers.clear()
})

defineExpose({ loadLibraries })
</script>

<style scoped>
.library-container {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
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

.library-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
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

.library-header-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: max-content;
}

.library-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.25;
}

.group-library-btn,
.new-library-btn,
.hover-open-btn {
  min-width: 28px;
  height: 28px;
  min-height: 28px;
  box-sizing: border-box;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  border-radius: 9px;
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

.new-library-btn {
  width: 28px;
  max-width: 28px;
  padding: 0;
  font-size: 1rem;
  font-weight: 800;
}

.group-library-btn:hover,
.group-library-btn:focus-visible,
.new-library-btn:hover,
.new-library-btn:focus-visible,
.hover-open-btn:hover,
.hover-open-btn:focus-visible {
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

.group-library-btn:active,
.new-library-btn:active,
.hover-open-btn:active {
  transform: translateY(1px);
}

.hover-open-btn.on {
  border-color: color-mix(in srgb, var(--selected) 45%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 20px rgba(0, 0, 0, 0.08);
}

.library-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overflow-anchor: none;
  padding: 0.02rem 0.05rem 0.7rem;
  scrollbar-width: thin;
}

.library-list::-webkit-scrollbar {
  width: 8px;
}

.library-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.library-block {
  margin-bottom: 0.36rem;
}

.library-item {
  position: relative;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  padding: 0.56rem 0.58rem;
  border: 1px solid transparent;
  border-radius: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.84rem;
  background: transparent;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.library-item::before {
  content: '';
  position: absolute;
  left: 0.36rem;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.library-item:hover {
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

.library-item.active {
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

.library-item.active::before {
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.fold-btn {
  width: 22px;
  height: 22px;
  min-width: 22px;
  max-width: 22px;
  box-sizing: border-box;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 40%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-family: inherit;
  font-weight: 800;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.library-item:hover .fold-btn,
.library-item.active .fold-btn,
.fold-btn:hover,
.fold-btn:focus-visible {
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, currentColor 12%, transparent),
    0 6px 14px rgba(0, 0, 0, 0.07);
  outline: none;
}

.fold-btn:active {
  transform: translateY(1px);
}

.library-icon {
  flex: 0 0 auto;
  width: 1.45rem;
  min-width: 1.45rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  line-height: 1;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.08));
}

.library-info {
  flex: 1 1 auto;
  min-width: 0;
}

.library-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 760;
  line-height: 1.25;
}

.library-item:hover .library-name,
.library-item.active .library-name {
  color: var(--selected);
}

.library-meta {
  margin-top: 0.12rem;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 620;
  line-height: 1.25;
  opacity: 0.88;
}

.docs-wrapper {
  position: relative;
  margin: 0.2rem 0 0.38rem 1.82rem;
  padding-left: 0.62rem;
  border-left: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
}

.docs-wrapper::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 0.25rem;
  bottom: 0.25rem;
  width: 1px;
  background:
    linear-gradient(
      180deg,
      transparent,
      color-mix(in srgb, var(--selected) 22%, var(--line)),
      transparent
    );
  pointer-events: none;
}

.doc-row {
  position: relative;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.08rem;
  padding: 0.42rem 0.5rem;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.78rem;
  background: transparent;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    color 0.12s ease,
    transform 0.12s ease,
    box-shadow 0.12s ease;
}

.doc-row:hover,
.doc-row.hovering {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 36%, transparent)
    );
  color: var(--selected);
  transform: translateX(2px);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.05);
}

.doc-row.active {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 64%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.06);
}

.doc-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: inherit;
  font-weight: 720;
  line-height: 1.28;
}

.doc-meta-breath {
  max-height: 0;
  margin-top: 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 620;
  line-height: 1.25;
  opacity: 0;
  transform: translateY(-2px);
  transition:
    opacity 0.15s ease,
    max-height 0.15s ease,
    transform 0.15s ease,
    margin-top 0.15s ease;
}

.doc-row:hover .doc-meta-breath,
.doc-row.active .doc-meta-breath,
.doc-row.hovering .doc-meta-breath {
  max-height: 22px;
  margin-top: 0.06rem;
  opacity: 0.86;
  transform: translateY(0);
}

.docs-tip,
.empty-tip {
  box-sizing: border-box;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.docs-tip {
  margin: 0.15rem 0;
  padding: 0.42rem 0.5rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
}

.empty-tip {
  margin: 0.25rem 0.05rem;
  padding: 0.9rem 0.75rem;
  border: 1px dashed color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  text-align: center;
  overflow-wrap: break-word;
}

.fade-collapse-enter-active,
.fade-collapse-leave-active {
  transition:
    opacity 0.15s ease,
    max-height 0.15s ease,
    transform 0.15s ease;
}

.fade-collapse-enter-from,
.fade-collapse-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-2px);
}

.fade-collapse-enter-to,
.fade-collapse-leave-from {
  opacity: 1;
  max-height: 320px;
  transform: translateY(0);
}

.nisb-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  box-sizing: border-box;
  padding: 16px;
  background:
    radial-gradient(circle at 50% 0%, rgba(80, 130, 255, 0.14), transparent 42%),
    rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  overflow-y: auto;
  overflow-x: hidden;
}

.nisb-modal {
  width: min(880px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 84%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  box-shadow:
    0 24px 64px rgba(0, 0, 0, 0.28),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.nisb-modal-header {
  position: relative;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 50px;
  box-sizing: border-box;
  padding: 0.75rem 0.9rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
}

.nisb-modal-header::after {
  content: '';
  position: absolute;
  left: 0.9rem;
  right: 0.9rem;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 20%, var(--line)),
      transparent
    );
  opacity: 0.66;
}

.nisb-modal-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.96rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.modal-close-btn {
  width: 32px;
  height: 32px;
  min-width: 32px;
  max-width: 32px;
  flex: 0 0 auto;
  box-sizing: border-box;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
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
  font-size: 0.82rem;
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

.modal-close-btn:hover,
.modal-close-btn:focus-visible {
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

.modal-close-btn:active {
  transform: translateY(1px);
}

.nisb-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.9rem;
  scrollbar-width: thin;
}

.nisb-modal-actions {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  padding: 0.75rem 0.9rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent)
    );
}

.create-preview {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.62rem 0.72rem;
  border: 1px dashed color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.preview-dot {
  width: 10px;
  height: 10px;
  min-width: 10px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, white 38%, transparent);
  box-shadow:
    0 0 0 4px color-mix(in srgb, currentColor 8%, transparent),
    0 3px 8px rgba(0, 0, 0, 0.16);
}

.preview-icon {
  flex: 0 0 auto;
  font-size: 1.15rem;
  line-height: 1;
}

.preview-name {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-id {
  flex: 0 1 auto;
  max-width: 220px;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.create-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.75rem;
}

.create-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.card-title {
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 0.36rem;
  min-width: 0;
}

.label {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1.35;
}

.hint {
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.muted {
  color: var(--text-secondary);
}

.nisb-input {
  width: 100%;
  min-height: 36px;
  box-sizing: border-box;
  padding: 0.56rem 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 90%, transparent);
  border-radius: 11px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.86rem;
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
      color-mix(in srgb, var(--editor-bg) 80%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

.mono {
  font-family: var(--font-mono);
  overflow-wrap: anywhere;
}

.modal-btn,
.mini-btn {
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
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
  font-size: 0.82rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.modal-btn:hover:not(:disabled),
.modal-btn:focus-visible:not(:disabled),
.mini-btn:hover:not(:disabled),
.mini-btn:focus-visible:not(:disabled) {
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

.modal-btn:active:not(:disabled),
.mini-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.modal-btn:disabled,
.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.modal-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 76%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 0.36rem;
}

.icon-btn {
  height: 34px;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 90%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-family: inherit;
  font-size: 1rem;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.icon-btn:hover,
.icon-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 8px 16px rgba(0, 0, 0, 0.07);
  outline: none;
}

.icon-btn:active {
  transform: translateY(1px);
}

.icon-btn.active {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.color-row {
  display: flex;
  align-items: center;
  gap: 0.44rem;
  flex-wrap: wrap;
  min-width: 0;
}

.color-dot {
  width: 20px;
  height: 20px;
  min-width: 20px;
  box-sizing: border-box;
  border-radius: 999px;
  border: 2px solid color-mix(in srgb, white 18%, transparent);
  cursor: pointer;
  box-shadow:
    0 2px 7px rgba(0, 0, 0, 0.14),
    0 0 0 1px color-mix(in srgb, var(--line) 50%, transparent);
  transition:
    transform 0.12s ease,
    box-shadow 0.12s ease,
    border-color 0.12s ease;
}

.color-dot:hover,
.color-dot:focus-visible {
  transform: scale(1.08);
  outline: none;
}

.color-dot.active {
  border-color: var(--selected);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 16%, transparent),
    0 4px 10px rgba(0, 0, 0, 0.18);
}

.color-input {
  width: 160px;
  min-width: 120px;
  max-width: 100%;
  min-height: 32px;
  padding: 0.46rem 0.56rem;
  font-size: 0.8rem;
}

.quick-row {
  display: flex;
  gap: 0.44rem;
  flex-wrap: wrap;
  min-width: 0;
}

@media (max-width: 860px) {
  .nisb-modal {
    width: min(540px, calc(100vw - 32px));
  }

  .create-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .preview-id {
    display: none;
  }
}

@media (max-width: 520px) {
  .library-container {
    padding: 0.45rem;
  }

  .library-header {
    align-items: stretch;
    flex-direction: column;
    gap: 0.45rem;
  }

  .library-header-actions {
    width: 100%;
    min-width: 0;
  }

  .group-library-btn,
  .hover-open-btn {
    flex: 1 1 auto;
  }

  .nisb-modal-mask {
    padding: 10px;
  }

  .nisb-modal {
    width: calc(100vw - 20px);
    max-height: calc(100vh - 20px);
    border-radius: 16px;
  }

  .nisb-modal-actions {
    flex-wrap: wrap;
  }

  .modal-btn {
    flex: 1 1 auto;
  }

  .icon-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .color-input {
    width: 100%;
  }
}
</style>

