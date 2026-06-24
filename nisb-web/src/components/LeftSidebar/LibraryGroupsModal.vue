<template>
  <div class="nisb-modal-mask" @click.self="close">
    <div
      class="nisb-modal"
      role="dialog"
      aria-modal="true"
      :aria-label="t('library.left.groups.title')"
    >
      <div class="nisb-modal-header">
        <div class="modal-heading">
          <div class="nisb-modal-title">{{ t('library.left.groups.title') }}</div>
          <div class="modal-subline">
            <span class="summary-chip">
              {{ t('library.left.groups.listTitle') }}
              <span class="mono">{{ groups.length }}</span>
            </span>
            <span class="summary-chip">
              {{ t('library.left.groups.membersLabel') }}
              <span class="mono">{{ selectedMemberCount }}</span>
            </span>
          </div>
        </div>

        <button
          class="modal-close-btn"
          type="button"
          @click="close"
          :aria-label="t('library.left.groups.close')"
        >
          ✕
        </button>
      </div>

      <div class="nisb-modal-body">
        <section class="pane groups-pane">
          <div class="pane-header">
            <div class="pane-title-block">
              <div class="label strong">{{ t('library.left.groups.listTitle') }}</div>
              <div class="pane-meta">
                <span class="meta-chip mono">{{ groups.length }}</span>
              </div>
            </div>

            <button class="mini-btn" type="button" @click="load_groups({ force: true })" :disabled="loading_groups">
              {{ loading_groups ? t('library.left.groups.refreshing') : t('library.left.groups.refresh') }}
            </button>
          </div>

          <div class="pane-body">
            <div v-if="loading_groups" class="state-box">
              {{ t('library.left.groups.loading') }}
            </div>

            <div v-else-if="!groups.length" class="state-box empty">
              {{ t('library.left.groups.empty') }}
            </div>

            <div v-else class="group-list group-list-scroll">
              <div
                v-for="g in groups"
                :key="g.group_id"
                class="group-row"
                :class="{ active: String(g.group_id) === String(edit_group_id) }"
              >
                <button class="g-main" type="button" @click="begin_edit(g)">
                  <span class="g-icon">{{ g.icon || '🧭' }}</span>
                  <span class="g-text">
                    <span class="g-name" :title="g.group_name">{{ g.group_name }}</span>
                    <span class="g-id mono" :title="g.group_id">{{ g.group_id }}</span>
                  </span>
                </button>

                <div class="g-right">
                  <button class="mini-btn" type="button" @click="begin_edit(g)">
                    {{ t('library.left.groups.edit') }}
                  </button>
                  <button class="mini-btn danger" type="button" @click="delete_group(g)">
                    {{ t('library.left.groups.delete') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="pane editor-pane">
          <div class="pane-header">
            <div class="pane-title-block">
              <div class="label strong">{{ t('library.left.groups.editorTitle') }}</div>
              <div class="pane-meta">
                <span v-if="edit_group_id" class="meta-chip mono" :title="edit_group_id">
                  {{ edit_group_id }}
                </span>
                <span v-else class="meta-chip">
                  {{ t('library.left.groups.newGroup') }}
                </span>
              </div>
            </div>

            <button class="mini-btn" type="button" @click="new_group">
              {{ t('library.left.groups.newGroup') }}
            </button>
          </div>

          <div class="pane-body editor-scroll">
            <div class="form">
              <div class="form-card">
                <div class="form-card-title">{{ t('library.left.groups.editorTitle') }}</div>

                <div class="form-row">
                  <div class="label">{{ t('library.left.groups.groupIdLabel') }}</div>
                  <input
                    class="nisb-input mono"
                    v-model="edit_group_id"
                    :placeholder="t('library.left.groups.groupIdPlaceholder')"
                  />
                  <div class="hint muted">{{ t('library.left.groups.groupIdHint') }}</div>
                </div>

                <div class="form-row">
                  <div class="label">{{ t('library.left.groups.groupNameLabel') }}</div>
                  <input
                    class="nisb-input"
                    v-model="edit_group_name"
                    :placeholder="t('library.left.groups.groupNamePlaceholder')"
                  />
                </div>

                <div class="form-row">
                  <div class="label">{{ t('library.left.groups.iconLabel') }}</div>
                  <div class="icon-grid">
                    <button
                      v-for="ic in group_icon_options"
                      :key="ic"
                      class="icon-btn"
                      :class="{ active: String(edit_icon) === String(ic) }"
                      type="button"
                      @click="edit_icon = ic"
                      :title="ic"
                    >
                      {{ ic }}
                    </button>
                  </div>
                  <div class="hint muted">
                    {{ t('library.left.groups.currentIcon') }}
                    <span class="mono">{{ edit_icon }}</span>
                  </div>
                </div>

                <div class="form-row">
                  <div class="label">{{ t('library.left.groups.noteLabel') }}</div>
                  <textarea
                    class="nisb-input"
                    v-model="edit_note"
                    rows="2"
                    :placeholder="t('library.left.groups.notePlaceholder')"
                  />
                </div>
              </div>

              <div class="form-card members-card">
                <div class="form-card-head">
                  <div>
                    <div class="form-card-title">{{ t('library.left.groups.membersLabel') }}</div>
                    <div class="hint muted">{{ t('library.left.groups.memberHint') }}</div>
                  </div>

                  <div class="member-counts">
                    <span class="meta-chip">
                      {{ selectedLibraryCount }}
                    </span>
                    <span class="meta-chip">
                      {{ selectedDocCount }}
                    </span>
                  </div>
                </div>

                <div class="member-box">
                  <div class="member-toolbar">
                    <input
                      class="nisb-input"
                      v-model="lib_filter"
                      :placeholder="t('library.left.groups.filterLibrariesPlaceholder')"
                    />
                    <button class="mini-btn" type="button" @click="load_libraries" :disabled="loading_libs">
                      {{ loading_libs ? t('library.left.groups.loadingLibrariesButton') : t('library.left.groups.loadLibraries') }}
                    </button>
                  </div>

                  <div v-if="loading_libs" class="state-box">
                    {{ t('library.left.groups.loadingLibraries') }}
                  </div>

                  <div v-else-if="!filtered_libs.length" class="state-box empty">
                    {{ t('library.left.groups.emptyLibraries') }}
                  </div>

                  <div v-else class="lib-list">
                    <div v-for="lib in filtered_libs" :key="lib.library_id" class="lib-row">
                      <div class="lib-top">
                        <label class="check library-check">
                          <input
                            type="checkbox"
                            :checked="is_library_all_selected(lib.library_id)"
                            @change="toggle_library_all(lib.library_id)"
                          />
                          <span class="lib-main">
                            <span class="lib-name">{{ lib.icon }} {{ lib.library_name }}</span>
                            <span class="mono muted id-text">({{ lib.library_id }})</span>
                          </span>
                        </label>

                        <button
                          class="mini-btn"
                          type="button"
                          @click="toggle_docs_panel(lib.library_id)"
                          :disabled="is_library_all_selected(lib.library_id)"
                        >
                          {{ docs_open[lib.library_id] ? t('library.left.groups.collapseDocs') : t('library.left.groups.selectDocs') }}
                        </button>
                      </div>

                      <div v-if="docs_open[lib.library_id]" class="docs-panel">
                        <div class="state-box compact" v-if="docs_state(lib.library_id).loading">
                          {{ t('library.left.groups.loadingDocs') }}
                        </div>
                        <div class="state-box compact danger-text" v-else-if="docs_state(lib.library_id).error">
                          {{ t('library.left.groups.messages.loadDocsError', { error: docs_state(lib.library_id).error }) }}
                        </div>
                        <div class="state-box compact empty" v-else-if="!docs_state(lib.library_id).docs.length">
                          {{ t('library.left.groups.docsEmpty') }}
                        </div>

                        <label v-for="d in docs_state(lib.library_id).docs" :key="d.doc_id" class="check doc">
                          <input
                            type="checkbox"
                            :checked="is_doc_selected(lib.library_id, d.doc_id)"
                            @change="toggle_doc(lib.library_id, d.doc_id)"
                          />
                          <span class="doc-main">
                            <span class="doc-name">{{ d.filename || d.doc_id }}</span>
                            <span class="mono muted id-text">{{ d.doc_id }}</span>
                          </span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="nisb-modal-actions">
        <button class="modal-btn" type="button" :disabled="saving" @click="close">
          {{ t('library.left.groups.cancel') }}
        </button>
        <button class="modal-btn primary" type="button" :disabled="saving" @click="save">
          {{ saving ? t('library.left.groups.saving') : t('library.left.groups.save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'

const emit = defineEmits(['close', 'saved'])
const { callTool } = useMCP()
const { t } = useI18n()

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

const group_icon_options = [
  '🧭', '🧩', '🧱', '🧰', '🗂️', '🗃️', '🧺', '🧷',
  '🔎', '🔍', '🧪', '🧬', '🧠', '🧵', '🧾', '🔖',
  '📰', '📌', '🧿', '🛰️', '🗺️', '🎯', '🧯', '🛟'
]

const loading_groups = ref(false)
const saving = ref(false)
const groups = ref([])

const libs = ref([])
const loading_libs = ref(false)
const lib_filter = ref('')

const docs_map = ref({})
const docs_open = ref({})

const edit_group_id = ref('')
const edit_group_name = ref('')
const edit_icon = ref('🧭')
const edit_note = ref('')

const library_all = ref(new Set())
const doc_selected = ref({})

const selectedLibraryCount = computed(() => Array.from(library_all.value || []).length)
const selectedDocCount = computed(() =>
  Object.values(doc_selected.value || {}).filter(Boolean).length
)
const selectedMemberCount = computed(() => selectedLibraryCount.value + selectedDocCount.value)

function close() { emit('close') }
function _norm(s) { return String(s || '').trim() }

function docs_state(library_id) {
  const id = _norm(library_id)
  if (!id) return { loading: false, docs: [], error: '' }
  if (!docs_map.value[id]) docs_map.value[id] = { loading: false, docs: [], error: '' }
  return docs_map.value[id]
}

let _groups_promise = null
let _groups_force_pending = false

async function load_groups({ force = false } = {}) {
  if (_groups_promise) {
    if (force) _groups_force_pending = true
    return _groups_promise
  }

  loading_groups.value = true
  _groups_promise = (async () => {
    try {
      const res = await callTool('nisb_library_group_list', {})
      if (res && res.status === 'success') groups.value = Array.isArray(res.groups) ? res.groups : []
      else {
        groups.value = []
        toast(
          t('library.left.groups.messages.loadGroupsFailed', {
            error: res?.message || t('library.left.messages.unknownError')
          }),
          'error'
        )
      }
    } catch (e) {
      groups.value = []
      toast(
        t('library.left.groups.messages.loadGroupsError', {
          error: e?.message || String(e)
        }),
        'error'
      )
    } finally {
      loading_groups.value = false
    }
  })()

  try {
    await _groups_promise
  } finally {
    _groups_promise = null
    if (_groups_force_pending) {
      _groups_force_pending = false
      return load_groups({ force: false })
    }
  }
}

async function load_libraries() {
  if (loading_libs.value) return
  loading_libs.value = true
  try {
    const res = await callTool('nisb_library_list', {})
    if (res && res.status === 'success') {
      const raw = Array.isArray(res.libraries) ? res.libraries : []
      libs.value = raw.map((lib) => {
        const stats = lib.stats || {}
        return {
          library_id: lib.library_id || 'unknown_library',
          library_name: lib.library_name || lib.name || t('library.left.unnamedLibrary'),
          icon: lib.icon || '🏛️',
          color: lib.color || '#3B82F6',
          doc_count: lib.doc_count != null ? lib.doc_count : (stats.doc_count != null ? stats.doc_count : 0),
        }
      })
    } else {
      libs.value = []
      toast(
        t('library.left.groups.messages.loadLibrariesFailed', {
          error: res?.message || t('library.left.messages.unknownError')
        }),
        'error'
      )
    }
  } catch (e) {
    libs.value = []
    toast(
      t('library.left.groups.messages.loadLibrariesFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    loading_libs.value = false
  }
}

async function load_docs(library_id) {
  const id = _norm(library_id)
  if (!id) return
  const st = docs_state(id)
  if (st.loading) return
  st.loading = true
  st.error = ''
  try {
    const res = await callTool('nisb_doc_stats', { library_id: id })
    if (res && res.status === 'success') {
      const docs = Array.isArray(res.documents)
        ? res.documents
        : (Array.isArray(res.raw?.documents) ? res.raw.documents : [])
      st.docs = docs.map((d) => ({
        doc_id: d.doc_id || '',
        filename: d.filename || '',
      })).filter(x => !!x.doc_id)
    } else {
      st.error = String(res?.message || res?.status || 'nisb_doc_stats')
    }
  } catch (e) {
    st.error = String(e?.message || e)
  } finally {
    st.loading = false
  }
}

const filtered_libs = computed(() => {
  const q = (lib_filter.value || '').trim().toLowerCase()
  if (!q) return libs.value
  return libs.value.filter((l) => {
    return String(l.library_name || '').toLowerCase().includes(q) || String(l.library_id || '').toLowerCase().includes(q)
  })
})

function new_group() {
  edit_group_id.value = ''
  edit_group_name.value = ''
  edit_icon.value = '🧭'
  edit_note.value = ''
  library_all.value = new Set()
  doc_selected.value = {}
  docs_open.value = {}
}

function begin_edit(g) {
  const gid = _norm(g?.group_id)
  if (!gid) return

  edit_group_id.value = gid
  edit_group_name.value = String(g?.group_name || '')
  edit_icon.value = String(g?.icon || '🧭')
  edit_note.value = String(g?.note || '')

  const all = new Set()
  const dm = {}
  const members = Array.isArray(g?.members) ? g.members : []
  for (const m of members) {
    const lid = _norm(m?.library_id)
    const did = m?.doc_id == null ? '' : _norm(m?.doc_id)
    if (!lid) continue
    if (!did) all.add(lid)
    else dm[`${lid}::${did}`] = true
  }
  for (const k of Object.keys(dm)) {
    const lid = k.split('::')[0]
    if (all.has(lid)) delete dm[k]
  }
  library_all.value = all
  doc_selected.value = dm
  docs_open.value = {}
}

function is_library_all_selected(library_id) {
  const id = _norm(library_id)
  return id ? library_all.value.has(id) : false
}

function toggle_library_all(library_id) {
  const lid = _norm(library_id)
  if (!lid) return

  const next = new Set(Array.from(library_all.value))
  if (next.has(lid)) next.delete(lid)
  else next.add(lid)
  library_all.value = next

  if (next.has(lid)) {
    const dm = { ...(doc_selected.value || {}) }
    for (const k of Object.keys(dm)) {
      if (k.startsWith(`${lid}::`)) delete dm[k]
    }
    doc_selected.value = dm
    docs_open.value = { ...(docs_open.value || {}), [lid]: false }
  }
}

function toggle_docs_panel(library_id) {
  const lid = _norm(library_id)
  if (!lid) return
  if (is_library_all_selected(lid)) return

  const next = { ...(docs_open.value || {}) }
  next[lid] = !next[lid]
  docs_open.value = next

  if (next[lid]) {
    if (!docs_state(lid).docs.length) load_docs(lid)
  }
}

function is_doc_selected(library_id, doc_id) {
  const lid = _norm(library_id)
  const did = _norm(doc_id)
  if (!lid || !did) return false
  return !!doc_selected.value?.[`${lid}::${did}`]
}

function toggle_doc(library_id, doc_id) {
  const lid = _norm(library_id)
  const did = _norm(doc_id)
  if (!lid || !did) return
  if (is_library_all_selected(lid)) return

  const dm = { ...(doc_selected.value || {}) }
  const k = `${lid}::${did}`
  dm[k] = !dm[k]
  if (!dm[k]) delete dm[k]
  doc_selected.value = dm
}

function _members_payload() {
  const out = []
  for (const lid of Array.from(library_all.value || [])) out.push({ library_id: lid, doc_id: null })
  for (const k of Object.keys(doc_selected.value || {})) {
    if (!doc_selected.value[k]) continue
    const [lid, did] = k.split('::')
    if (!lid || !did) continue
    if (library_all.value.has(lid)) continue
    out.push({ library_id: lid, doc_id: did })
  }
  return out
}

async function save() {
  const gid = _norm(edit_group_id.value)
  const name = String(edit_group_name.value || '').trim()
  if (!gid) return toast(t('library.left.groups.messages.groupIdRequired'), 'error')
  if (!name) return toast(t('library.left.groups.messages.groupNameRequired'), 'error')

  const members = _members_payload()
  if (!members.length) return toast(t('library.left.groups.messages.membersRequired'), 'error')

  saving.value = true
  try {
    const res = await callTool('nisb_library_group_upsert', {
      group_id: gid,
      group_name: name,
      members,
      icon: String(edit_icon.value || '🧭'),
      note: String(edit_note.value || '')
    })
    if (res && res.status === 'success') {
      toast(t('library.left.groups.messages.saveSuccess'), 'success')
      await load_groups({ force: true })
      window.dispatchEvent(new CustomEvent('nisb-library-updated'))
      emit('saved')
    } else {
      toast(
        t('library.left.groups.messages.saveFailed', {
          error: res?.message || t('library.left.messages.unknownError')
        }),
        'error'
      )
    }
  } catch (e) {
    toast(
      t('library.left.groups.messages.saveFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    saving.value = false
  }
}

async function delete_group(g) {
  const gid = _norm(g?.group_id)
  if (!gid) return
  const ok = window.confirm(t('library.left.groups.messages.deleteConfirm', { groupId: gid }))
  if (!ok) return

  try {
    const res = await callTool('nisb_library_group_delete', { group_id: gid })
    if (res && res.status === 'success') {
      toast(t('library.left.groups.messages.deleteSuccess'), 'success')
      await load_groups({ force: true })
      window.dispatchEvent(new CustomEvent('nisb-library-updated'))
      emit('saved')
      if (String(edit_group_id.value) === gid) new_group()
    } else {
      toast(
        t('library.left.groups.messages.deleteFailed', {
          error: res?.message || t('library.left.messages.unknownError')
        }),
        'error'
      )
    }
  } catch (e) {
    toast(
      t('library.left.groups.messages.deleteFailed', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

load_groups({ force: false })
</script>

<style scoped>
.nisb-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 18px;
  overflow-y: auto;
  background:
    radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--selected) 12%, transparent), transparent 32%),
    radial-gradient(circle at 82% 8%, color-mix(in srgb, #16a34a 8%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.22);
}

.nisb-modal {
  width: min(1040px, calc(100vw - 36px));
  max-height: calc(100vh - 36px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.28),
    0 2px 18px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(16px);
}

.nisb-modal-header {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 15px 16px 13px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
}

.modal-heading {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.nisb-modal-title {
  color: var(--text-main, var(--text));
  font-size: 0.96rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.modal-subline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.summary-chip,
.meta-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  max-width: 100%;
}

.summary-chip {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--selected);
}

.modal-close-btn {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
  font-size: 0.9rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close-btn:hover {
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.modal-close-btn:active {
  transform: translateY(1px);
}

.nisb-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, 0.92fr) minmax(0, 1.28fr);
  gap: 12px;
  padding: 12px;
  overflow: hidden;
}

.pane {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: inset 0 1px 0 color-mix(in srgb, #fff 4%, transparent);
}

.pane-header {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
}

.pane-title-block {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.pane-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.pane-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 10px;
  overflow: auto;
  scrollbar-width: thin;
}

.editor-scroll {
  padding: 10px;
}

.nisb-modal-actions {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 12px;
  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 84%, transparent);
}

.form {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.form-card {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
}

.form-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.form-card-title {
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 790;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.form-row {
  display: grid;
  gap: 0.38rem;
  min-width: 0;
}

.label {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.label.strong {
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 790;
}

.hint,
.muted {
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

.id-text,
.g-id,
.meta-chip.mono {
  overflow-wrap: anywhere;
}

.nisb-input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 0.58rem 0.68rem;
  border: 1px solid var(--line);
  border-radius: 11px;
  outline: none;
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1.35;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

textarea.nisb-input {
  resize: vertical;
  min-height: 62px;
}

.nisb-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.nisb-input:focus {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.modal-btn,
.mini-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 0.72rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
}

.modal-btn {
  min-height: 36px;
  min-width: 96px;
}

.modal-btn:hover:not(:disabled),
.mini-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.modal-btn:active:not(:disabled),
.mini-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.modal-btn:disabled,
.mini-btn:disabled {
  opacity: 0.56;
  cursor: not-allowed;
  transform: none;
}

.modal-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected) 88%, #1f2937);
  color: #fff;
}

.mini-btn.danger {
  border-color: rgba(239, 68, 68, 0.38);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.mini-btn.danger:hover:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.state-box {
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 64%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.state-box.empty {
  border-style: dashed;
}

.state-box.compact {
  padding: 8px 9px;
  border-radius: 10px;
}

.danger-text {
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.group-list {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.group-list-scroll {
  min-height: 120px;
}

.group-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.group-row.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
}

.g-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.g-icon {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 72%, transparent);
  font-size: 1rem;
}

.g-text {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.g-name {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 760;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.g-id {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.g-right {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 0.42rem;
}

.icon-btn {
  height: 36px;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-main, var(--text));
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease;
  font-size: 1rem;
}

.icon-btn:hover {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
}

.icon-btn:active {
  transform: translateY(1px);
}

.icon-btn.active {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 60%, var(--editor-bg));
}

.member-counts {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  flex: 0 0 auto;
}

.member-box {
  min-height: 300px;
  max-height: 48vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
}

.member-toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
}

.lib-list {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 9px;
  overflow: auto;
  padding: 10px;
  scrollbar-width: thin;
}

.lib-row {
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  padding: 9px;
  background: color-mix(in srgb, var(--sidebar-bg) 66%, transparent);
}

.lib-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.check {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  line-height: 1.4;
}

.check input {
  flex: 0 0 auto;
  margin-top: 2px;
  accent-color: var(--selected);
}

.library-check {
  flex: 1 1 auto;
}

.lib-main,
.doc-main {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.lib-name,
.doc-name {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.docs-panel {
  margin-top: 9px;
  display: grid;
  gap: 7px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
}

.check.doc {
  padding: 7px 8px;
  border: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 48%, transparent);
}

@media (max-width: 860px) {
  .nisb-modal-mask {
    padding: 12px;
  }

  .nisb-modal {
    width: min(620px, calc(100vw - 24px));
    max-height: calc(100vh - 24px);
  }

  .nisb-modal-body {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .groups-pane,
  .editor-pane {
    min-height: 360px;
  }

  .member-box {
    max-height: 52vh;
  }
}

@media (max-width: 620px) {
  .nisb-modal-mask {
    padding: 0;
  }

  .nisb-modal {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

  .nisb-modal-header,
  .pane-header,
  .form-card-head,
  .lib-top,
  .member-toolbar,
  .nisb-modal-actions,
  .group-row {
    display: grid;
    grid-template-columns: 1fr;
  }

  .modal-close-btn {
    justify-self: end;
    grid-row: 1;
  }

  .modal-heading {
    grid-row: 2;
  }

  .g-right,
  .member-counts {
    justify-content: stretch;
  }

  .g-right,
  .nisb-modal-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .mini-btn,
  .modal-btn {
    width: 100%;
    white-space: normal;
  }

  .icon-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .member-box {
    min-height: 320px;
    max-height: none;
  }
}

@media (max-width: 420px) {
  .icon-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .summary-chip,
  .meta-chip {
    width: 100%;
  }
}
</style>
