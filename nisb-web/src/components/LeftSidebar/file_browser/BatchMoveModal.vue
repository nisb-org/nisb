<template>
  <Teleport to="body">
    <div
      ref="mask_el"
      class="zen-modal-mask"
      data-nisb-modal="batch-move"
      @mousedown.self="on_cancel"
    >
      <div
        class="zen-modal"
        :style="modal_style_text"
        role="dialog"
        aria-modal="true"
        @mousedown.stop
      >
        <div class="zen-modal-header">
          <div class="title">{{ tt('files.batchMove.title') }}</div>
          <button class="icon-btn" :title="tt('common.close')" @click="on_cancel">✕</button>
        </div>

        <div class="zen-modal-body">
          <div class="row">
            <div class="label">{{ tt('files.batchMove.currentFocus') }}</div>
            <div class="path mono">
              {{ focus_dir_visible }}{{ focus_dir_visible ? '/' : '' }}
            </div>
          </div>

          <div class="row">
            <div class="label">{{ tt('files.batchMove.selectedCount') }}</div>
            <div class="path">{{ tt('files.batchMove.selectedCountValue', { count }) }}</div>
          </div>

          <div class="path-row">
            <div class="label">{{ tt('files.batchMove.targetDirectory') }}</div>

            <div class="crumb-box">
              <div class="crumb-multiline">
                <button
                  class="crumb-btn"
                  @click.stop="set_dest_dir('agent_files')"
                  :title="tt('files.root.userTitleWithSlash')"
                >
                  {{ tt('files.root.userLabel') }}
                </button>
                <span class="crumb-sep">/</span>

                <template v-if="dest_segments.length">
                  <template v-for="seg in dest_segments" :key="seg.path">
                    <button
                      class="crumb-btn"
                      @click.stop="set_dest_dir(seg.path)"
                      :title="`${seg.displayPath || to_user_visible_path(seg.path)}/`"
                    >
                      {{ seg.displayName || seg.name }}
                    </button>
                    <span class="crumb-sep">/</span>
                  </template>
                </template>

                <button
                  v-if="can_choose_child_dir && dest_has_child_dirs"
                  class="crumb-child-inline-btn"
                  :class="{ active: dest_child_panel_open }"
                  :title="tt('files.batchMove.chooseChildDir')"
                  @click.stop="toggle_dest_child_panel"
                >
                  ▾
                </button>
              </div>
            </div>
          </div>

          <div v-if="dest_child_panel_open" class="child-panel">
            <div class="child-panel-header">
              <div class="child-panel-title">{{ tt('files.batchMove.childDirs') }}</div>
              <button
                class="child-panel-close"
                :title="tt('files.batchMove.collapse')"
                @click.stop="dest_child_panel_open = false"
              >
                ✕
              </button>
            </div>

            <div class="child-panel-body">
              <div v-if="dest_child_loading" class="child-empty">
                {{ tt('files.batchMove.childLoading') }}
              </div>

              <template v-else>
                <div v-if="!dest_child_dirs.length" class="child-empty">
                  {{ tt('files.batchMove.childEmpty') }}
                </div>

                <button
                  v-for="d in dest_child_dirs"
                  :key="d.path"
                  class="child-item"
                  @click.stop="pick_dest_child_dir(d)"
                  :title="`${to_user_visible_path(d.path)}/`"
                >
                  <span class="child-icon">📁</span>
                  <span class="child-name">{{ d.name }}</span>
                </button>
              </template>
            </div>
          </div>

          <div class="input-row">
            <div class="label">{{ tt('files.batchMove.directoryPath') }}</div>

            <div class="input-wrap">
              <div class="prefix mono">{{ tt('files.root.userLabel') }}/</div>
              <input
                ref="dest_input_el"
                v-model="dest_dir_text"
                class="name-input mono"
                :placeholder="tt('files.batchMove.inputPlaceholder')"
                @keydown.enter.prevent="on_confirm"
                @keydown.esc.prevent="on_cancel"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
          </div>

          <div class="hint">
            {{ tt('files.batchMove.hint') }}
          </div>
        </div>

        <div class="zen-modal-footer">
          <button class="btn" @click="on_cancel">{{ tt('common.cancel') }}</button>
          <button class="btn primary" :disabled="!dest_dir_trimmed" @click="on_confirm">
            {{ tt('files.batchMove.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDynamicModalI18n } from '../../../composables/use_dynamic_modal_i18n'
import {
  from_user_visible_path,
  to_user_visible_path,
  to_user_visible_segments
} from '../../../composables/left_sidebar/file_browser/file_path_display'

const FALLBACK_MESSAGES = {
  'zh-CN': {
    common: {
      close: '关闭',
      cancel: '取消'
    },
    files: {
      root: {
        userLabel: 'user',
        userTitleWithSlash: 'user/'
      },
      batchMove: {
        title: '批量移动',
        currentFocus: '当前聚焦',
        selectedCount: '已选数量',
        selectedCountValue: '{count} 项',
        targetDirectory: '目标目录',
        chooseChildDir: '选择子目录',
        childDirs: '子目录',
        collapse: '收起',
        childLoading: '（加载中…）',
        childEmpty: '（当前目录下没有子目录）',
        directoryPath: '目录路径',
        inputPlaceholder: '例如：books/docs',
        hint: '说明：将把所选文件/目录移动到目标目录下（保持原名称）。如选择目录则递归移动其全部内容。',
        confirm: '开始移动'
      }
    }
  },
  en: {
    common: {
      close: 'Close',
      cancel: 'Cancel'
    },
    files: {
      root: {
        userLabel: 'user',
        userTitleWithSlash: 'user/'
      },
      batchMove: {
        title: 'Batch move',
        currentFocus: 'Current focus',
        selectedCount: 'Selected items',
        selectedCountValue: '{count} item(s)',
        targetDirectory: 'Target directory',
        chooseChildDir: 'Choose child directory',
        childDirs: 'Child directories',
        collapse: 'Collapse',
        childLoading: '(Loading...)',
        childEmpty: '(No child directories in current location)',
        directoryPath: 'Directory path',
        inputPlaceholder: 'Example: books/docs',
        hint: 'Note: selected files/directories will be moved into the target directory while keeping their original names. If a directory is selected, all of its contents will be moved recursively.',
        confirm: 'Start move'
      }
    }
  }
}

const { t: tt } = useDynamicModalI18n({
  fallbackMessages: FALLBACK_MESSAGES,
  defaultLocale: 'zh-CN'
})

const modal_style_text = `
  color: var(--text) !important;
  border-color: var(--line) !important;
`

const props = defineProps({
  count: { type: Number, default: 0 },
  focus_dir: { type: String, default: '' },
  default_dest_dir: { type: String, default: '' },
  call_tool: { type: Function, default: null }
})

const emit = defineEmits(['confirm', 'cancel'])

function _trim(s) {
  return String(s || '').trim()
}

function _norm_dir(s) {
  let v = String(s || '').trim()
  v = v.split('\\').join('/')
  while (v.startsWith('/')) v = v.slice(1)
  while (v.endsWith('/')) v = v.slice(0, -1)
  return v
}

function _is_dir_type(t) {
  const s = String(t || '').toLowerCase()
  return s === 'directory' || s === 'dir' || s === 'folder'
}

function _to_virtual_input_dir(real_dir) {
  const visible = to_user_visible_path(real_dir)
  if (!visible || visible === 'user') return ''
  if (visible.startsWith('user/')) return visible.slice('user/'.length)
  return visible
}

function _from_virtual_input_dir(input_dir) {
  const p = _norm_dir(input_dir || '')
  if (!p) return 'agent_files'
  if (p === 'user' || p.startsWith('user/')) return from_user_visible_path(p)
  if (p === 'agent_files' || p.startsWith('agent_files/')) return p
  return `agent_files/${p}`
}

const focus_dir_display = computed(() => _norm_dir(props.focus_dir || 'agent_files'))
const focus_dir_visible = computed(() => to_user_visible_path(focus_dir_display.value || 'agent_files'))

const can_choose_child_dir = computed(() => typeof props.call_tool === 'function')

const dest_dir_text = ref(_to_virtual_input_dir(props.default_dest_dir || 'agent_files'))

const dest_child_panel_open = ref(false)
const dest_child_loading = ref(false)
const dest_child_dirs = ref([])
const dest_child_loaded_key = ref('')

const dest_dir_display = computed(() => _from_virtual_input_dir(dest_dir_text.value || ''))
const dest_segments = computed(() => to_user_visible_segments(dest_dir_display.value))
const dest_dir_trimmed = computed(() => _trim(dest_dir_display.value || 'agent_files'))

const dest_has_child_dirs = computed(() => {
  if (!can_choose_child_dir.value) return false
  if (dest_child_loaded_key.value !== dest_dir_display.value) return false
  return Array.isArray(dest_child_dirs.value) && dest_child_dirs.value.length > 0
})

watch(
  () => props.default_dest_dir,
  async (v) => {
    dest_dir_text.value = _to_virtual_input_dir(v || 'agent_files')
    dest_child_panel_open.value = false
    await ensure_dest_child_dirs_loaded()
  }
)

async function _load_child_dirs(for_base_dir) {
  if (typeof props.call_tool !== 'function') return []
  const r = await props.call_tool('nisb_dir_list', { path: for_base_dir || 'agent_files' })
  const list = r && r.success && Array.isArray(r.entries) ? r.entries : []
  return list
    .filter((e) => e && _is_dir_type(e.type))
    .filter((e) => !String(e.name || '').startsWith('.'))
    .map((e) => {
      const p = for_base_dir ? `${for_base_dir}/${e.name}` : `agent_files/${e.name}`
      return { name: e.name, path: p }
    })
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
}

async function ensure_dest_child_dirs_loaded() {
  const key = dest_dir_display.value || 'agent_files'
  if (dest_child_loaded_key.value === key) return

  if (!can_choose_child_dir.value) {
    dest_child_dirs.value = []
    dest_child_loaded_key.value = key
    return
  }

  dest_child_loading.value = true
  try {
    dest_child_dirs.value = await _load_child_dirs(key)
    dest_child_loaded_key.value = key
  } catch (_e) {
    dest_child_dirs.value = []
    dest_child_loaded_key.value = key
  } finally {
    dest_child_loading.value = false
  }
}

watch(
  () => dest_dir_display.value,
  async () => {
    dest_child_panel_open.value = false
    await ensure_dest_child_dirs_loaded()
  }
)

async function set_dest_dir(p) {
  dest_dir_text.value = _to_virtual_input_dir(p || 'agent_files')
  dest_child_panel_open.value = false
  await ensure_dest_child_dirs_loaded()
  await nextTick()
  try {
    dest_input_el.value?.focus?.()
  } catch (_e) {}
}

async function toggle_dest_child_panel() {
  if (!can_choose_child_dir.value) return
  await ensure_dest_child_dirs_loaded()
  dest_child_panel_open.value = !dest_child_panel_open.value
}

async function pick_dest_child_dir(d) {
  const p = _norm_dir(d?.path || '')
  if (!p) return
  dest_dir_text.value = _to_virtual_input_dir(p)
  dest_child_panel_open.value = false
  await ensure_dest_child_dirs_loaded()
  await nextTick()
  try {
    dest_input_el.value?.focus?.()
  } catch (_e) {}
}

function on_confirm() {
  const v = dest_dir_trimmed.value || 'agent_files'
  if (!v) return
  emit('confirm', v)
}

function on_cancel() {
  emit('cancel')
}

const mask_el = ref(null)
const theme_src_el = ref(null)

const THEME_VARS = [
  '--editor-bg',
  '--sidebar-bg',
  '--line',
  '--text',
  '--text-secondary',
  '--selected',
  '--selected-bg'
]

function _has_theme_vars(el) {
  try {
    const cs = window.getComputedStyle(el)
    const a = String(cs.getPropertyValue('--editor-bg') || '').trim()
    const b = String(cs.getPropertyValue('--text') || '').trim()
    return !!(a && b)
  } catch (_e) {
    return false
  }
}

function find_theme_source_el() {
  const app = document.querySelector('#app')
  if (app && _has_theme_vars(app)) return app

  if (app) {
    try {
      const walker = document.createTreeWalker(app, NodeFilter.SHOW_ELEMENT)
      let n = walker.currentNode
      let count = 0
      while (n && count < 1200) {
        if (_has_theme_vars(n)) return n
        n = walker.nextNode()
        count++
      }
    } catch (_e) {}
  }

  if (_has_theme_vars(document.documentElement)) return document.documentElement
  if (_has_theme_vars(document.body)) return document.body
  return document.documentElement
}

function ensure_theme_src() {
  const el = find_theme_source_el()
  theme_src_el.value = el
  return el
}

function sync_theme_vars_once() {
  const host = mask_el.value
  if (!host) return
  const src = theme_src_el.value || ensure_theme_src()
  const cs = window.getComputedStyle(src)
  for (const k of THEME_VARS) {
    const v = String(cs.getPropertyValue(k) || '').trim()
    if (v) host.style.setProperty(k, v)
  }
}

let mo = null
let raf_id = 0

function schedule_sync_theme() {
  if (raf_id) return
  raf_id = requestAnimationFrame(() => {
    raf_id = 0
    if (!theme_src_el.value || !_has_theme_vars(theme_src_el.value)) {
      ensure_theme_src()
    }
    sync_theme_vars_once()
  })
}

function setup_theme_observer() {
  teardown_theme_observer()
  const src = ensure_theme_src()
  try {
    mo = new MutationObserver(() => schedule_sync_theme())
    const opts = { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] }
    mo.observe(src, opts)
    mo.observe(document.documentElement, opts)
    mo.observe(document.body, opts)
  } catch (_e) {
    mo = null
  }
}

function teardown_theme_observer() {
  try {
    mo?.disconnect?.()
  } catch (_e) {}
  mo = null
  if (raf_id) cancelAnimationFrame(raf_id)
  raf_id = 0
}

const dest_input_el = ref(null)

function on_doc_keydown(e) {
  if (e?.key === 'Escape') on_cancel()
}

onMounted(async () => {
  ensure_theme_src()
  sync_theme_vars_once()
  setup_theme_observer()

  document.addEventListener('keydown', on_doc_keydown, true)

  await nextTick()
  await ensure_dest_child_dirs_loaded()
  try {
    dest_input_el.value?.focus?.()
    dest_input_el.value?.select?.()
  } catch (_e) {}
})

onUnmounted(() => {
  document.removeEventListener('keydown', on_doc_keydown, true)
  teardown_theme_observer()
})
</script>

<style scoped>
:global([data-nisb-modal="batch-move"]) {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 2147483647 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 18px !important;
  box-sizing: border-box !important;
  isolation: isolate !important;
  background:
    radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--selected) 14%, transparent), transparent 34%),
    radial-gradient(circle at 82% 8%, color-mix(in srgb, #16a34a 8%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.34) !important;
}

.zen-modal {
  width: min(660px, calc(100vw - 36px));
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
  color: var(--text);
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.30),
    0 2px 18px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(16px);
}

.zen-modal-header {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 15px 16px 13px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.96rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.icon-btn {
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
}

.icon-btn:hover {
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.icon-btn:active {
  transform: translateY(1px);
}

.zen-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 12px;
  overflow: auto;
  padding: 12px;
  scrollbar-width: thin;
}

.row,
.path-row,
.input-row {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
}

.label {
  padding-top: 8px;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.path {
  min-width: 0;
  padding: 9px 10px;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.crumb-box {
  min-width: 0;
  padding: 9px 10px;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
}

.crumb-multiline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 4px;
  min-width: 0;
  color: var(--text-secondary);
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.crumb-btn {
  min-height: 23px;
  max-width: 100%;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 4px;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 760;
  line-height: 1.15;
  overflow-wrap: anywhere;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.crumb-btn:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, var(--editor-bg));
  color: var(--selected);
  text-decoration: none;
}

.crumb-sep {
  color: var(--text-secondary);
  opacity: 0.65;
  user-select: none;
}

.crumb-child-inline-btn {
  flex: 0 0 auto;
  width: 26px;
  height: 22px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.crumb-child-inline-btn:hover,
.crumb-child-inline-btn.active {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 60%, var(--editor-bg));
  color: var(--selected);
}

.child-panel {
  display: grid;
  gap: 7px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 13px;
  background: color-mix(in srgb, var(--selected-bg) 28%, var(--editor-bg));
}

.child-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 2px;
}

.child-panel-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 790;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.child-panel-close {
  flex: 0 0 auto;
  width: 30px;
  height: 28px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.child-panel-close:hover {
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.child-panel-body {
  max-height: 210px;
  overflow: auto;
  display: grid;
  gap: 6px;
  padding: 2px;
  scrollbar-width: thin;
}

.child-empty {
  padding: 10px;
  border: 1px dashed color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.child-item {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  color: var(--text-main, var(--text));
  cursor: pointer;
  text-align: left;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.child-item:hover {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  color: var(--selected);
  transform: translateX(2px);
}

.child-icon {
  flex: 0 0 auto;
}

.child-name {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.input-wrap {
  min-width: 0;
  display: flex;
  align-items: stretch;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.input-wrap:focus-within {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.prefix {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-right: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1;
  background: color-mix(in srgb, var(--sidebar-bg) 56%, transparent);
}

.name-input {
  flex: 1 1 auto;
  min-width: 0;
  padding: 10px;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  line-height: 1.35;
}

.name-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.hint {
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.zen-modal-footer {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 12px;
  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
}

.btn {
  min-height: 36px;
  min-width: 96px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.78rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 730;
  line-height: 1;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected) 88%, #1f2937);
  color: #fff;
}

.btn.primary:disabled {
  opacity: 0.54;
  cursor: not-allowed;
  transform: none;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

@media (max-width: 640px) {
  :global([data-nisb-modal="batch-move"]) {
    align-items: stretch !important;
    padding: 0 !important;
  }

  .zen-modal {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

  .row,
  .path-row,
  .input-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .label {
    padding-top: 0;
  }

  .zen-modal-footer {
    display: grid;
    grid-template-columns: 1fr;
  }

  .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .zen-modal-header,
  .zen-modal-body,
  .zen-modal-footer {
    padding-left: 10px;
    padding-right: 10px;
  }

  .input-wrap {
    display: grid;
    grid-template-columns: 1fr;
  }

  .prefix {
    min-height: 32px;
    border-right: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  }
}
</style>

