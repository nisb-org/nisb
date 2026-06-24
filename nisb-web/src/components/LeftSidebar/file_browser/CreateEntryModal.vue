<template>
  <Teleport to="body">
    <div
      ref="mask_el"
      class="zen-modal-mask"
      data-nisb-modal="create-entry"
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
          <div class="title">
            {{ kind === 'dir' ? tt('files.createEntry.folderTitle') : tt('files.createEntry.fileTitle') }}
          </div>
          <button class="icon-btn" :title="tt('common.close')" @click="on_cancel">✕</button>
        </div>

        <div class="zen-modal-body">
          <div class="path-row">
            <div class="label">{{ tt('files.createEntry.location') }}</div>

            <div class="crumb-box">
              <div class="crumb-multiline">
                <button class="crumb-btn" @click.stop="set_base_dir('agent_files')" :title="tt('files.root.userTitleWithSlash')">
                  {{ tt('files.root.userLabel') }}
                </button>
                <span class="crumb-sep">/</span>

                <template v-if="base_segments.length">
                  <template v-for="seg in base_segments" :key="seg.path">
                    <button
                      class="crumb-btn"
                      @click.stop="set_base_dir(seg.path)"
                      :title="`${seg.displayPath || to_user_visible_path(seg.path)}/`"
                    >
                      {{ seg.displayName || seg.name }}
                    </button>
                    <span class="crumb-sep">/</span>
                  </template>
                </template>

                <button
                  v-if="can_choose_child_dir && has_child_dirs"
                  class="crumb-child-inline-btn"
                  :class="{ active: child_panel_open }"
                  :title="tt('files.createEntry.chooseChildDir')"
                  @click.stop="toggle_child_panel"
                >
                  ▾
                </button>
              </div>
            </div>
          </div>

          <div v-if="child_panel_open" class="child-panel">
            <div class="child-panel-header">
              <div class="child-panel-title">{{ tt('files.createEntry.childDirs') }}</div>
              <button
                class="child-panel-close"
                :title="tt('files.createEntry.collapse')"
                @click.stop="child_panel_open = false"
              >
                ✕
              </button>
            </div>

            <div class="child-panel-body">
              <div v-if="child_loading" class="child-empty">
                {{ tt('files.createEntry.childLoading') }}
              </div>

              <template v-else>
                <div v-if="!child_dirs.length" class="child-empty">
                  {{ tt('files.createEntry.childEmpty') }}
                </div>

                <button
                  v-for="d in child_dirs"
                  :key="d.path"
                  class="child-item"
                  @click.stop="pick_child_dir(d)"
                  :title="`${to_user_visible_path(d.path)}/`"
                >
                  <span class="child-icon">📁</span>
                  <span class="child-name">{{ d.name }}</span>
                </button>
              </template>
            </div>
          </div>

          <div class="input-row">
            <div class="label">
              {{ kind === 'dir' ? tt('files.createEntry.folderName') : tt('files.createEntry.fileName') }}
            </div>

            <div class="input-wrap">
              <input
                ref="name_input_el"
                v-model="name_base"
                class="name-input"
                :placeholder="kind === 'dir' ? tt('files.createEntry.folderPlaceholder') : tt('files.createEntry.filePlaceholder')"
                @keydown.enter.prevent="on_confirm"
                @keydown.esc.prevent="on_cancel"
                autocomplete="off"
                spellcheck="false"
              />

              <template v-if="kind !== 'dir'">
                <div class="ext-split">.</div>
                <input
                  v-model="ext"
                  class="ext-input"
                  placeholder="md"
                  :title="tt('files.createEntry.extTitle')"
                  @keydown.enter.prevent="on_confirm"
                  @keydown.esc.prevent="on_cancel"
                  autocomplete="off"
                  spellcheck="false"
                />
              </template>
            </div>
          </div>

          <div v-if="error_text" class="error">
            {{ error_text }}
          </div>

          <div class="preview" v-if="final_name">
            {{ tt('files.createEntry.previewPrefix') }}<span class="mono">{{ final_path_display }}</span>
          </div>
          <div class="preview muted" v-else>
            {{ kind === 'dir' ? tt('files.createEntry.enterFolderName') : tt('files.createEntry.enterFileName') }}
          </div>
        </div>

        <div class="zen-modal-footer">
          <button class="btn" @click="on_cancel">{{ tt('common.cancel') }}</button>
          <button class="btn primary" :disabled="!final_name" @click="on_confirm">
            {{ tt('files.createEntry.confirm') }}
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
      createEntry: {
        fileTitle: '新建文件',
        folderTitle: '新建目录',
        location: '位置',
        chooseChildDir: '选择子目录',
        childDirs: '子目录',
        collapse: '收起',
        childLoading: '正在加载子目录...',
        childEmpty: '当前目录下没有可选子目录',
        folderName: '目录名',
        fileName: '文件名',
        folderPlaceholder: '请输入目录名',
        filePlaceholder: '请输入文件名',
        extTitle: '文件扩展名',
        previewPrefix: '将创建：',
        enterFolderName: '请输入目录名',
        enterFileName: '请输入文件名',
        confirm: '创建'
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
      createEntry: {
        fileTitle: 'New file',
        folderTitle: 'New folder',
        location: 'Location',
        chooseChildDir: 'Choose child directory',
        childDirs: 'Child directories',
        collapse: 'Collapse',
        childLoading: 'Loading child directories...',
        childEmpty: 'No child directories in current location',
        folderName: 'Folder name',
        fileName: 'File name',
        folderPlaceholder: 'Enter folder name',
        filePlaceholder: 'Enter file name',
        extTitle: 'File extension',
        previewPrefix: 'Will create: ',
        enterFolderName: 'Enter folder name',
        enterFileName: 'Enter file name',
        confirm: 'Create'
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
  kind:         { type: String,   default: 'file' },
  base_dir:     { type: String,   default: '' },
  default_name: { type: String,   default: '' },
  default_ext:  { type: String,   default: 'md' },
  call_tool:    { type: Function, default: null }
})

const emit = defineEmits(['confirm', 'cancel'])

function _norm_dir(s) {
  return String(s || '')
    .trim()
    .replace(/\\\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/+$/, '')
}

function _trim(s) {
  return String(s || '').trim()
}

function _split_filename(v) {
  const s = _trim(v)
  const idx = s.lastIndexOf('.')
  if (idx <= 0) return { base: s, ext: '' }
  if (idx === s.length - 1) return { base: s.slice(0, idx), ext: '' }
  return { base: s.slice(0, idx), ext: s.slice(idx + 1) }
}

function _is_name_ok(s) {
  const v = _trim(s)
  if (!v) return false
  if (v.includes('/') || v.includes('\\')) return false
  return true
}

const base_dir_local = ref(_norm_dir(props.base_dir || 'agent_files'))

watch(
  () => props.base_dir,
  async (v) => {
    base_dir_local.value = _norm_dir(v || 'agent_files')
    child_panel_open.value = false
    await ensure_child_dirs_loaded()
  }
)

const base_dir_display = computed(() => _norm_dir(base_dir_local.value || ''))

const base_segments = computed(() => {
  return to_user_visible_segments(base_dir_display.value)
})

async function set_base_dir(p) {
  base_dir_local.value = _norm_dir(p || 'agent_files')
  child_panel_open.value = false
  await ensure_child_dirs_loaded()
}

const init = _split_filename(props.default_name || '')
const name_base = ref(init.base || '')
const ext = ref(_trim(init.ext) || _trim(props.default_ext || 'md'))

watch(
  () => props.default_name,
  (v) => {
    const s = _split_filename(v || '')
    name_base.value = s.base || ''
    if (s.ext) ext.value = s.ext
  }
)

const error_text = ref('')

const final_name = computed(() => {
  error_text.value = ''
  if (props.kind === 'dir') {
    if (!_is_name_ok(name_base.value)) return ''
    return _trim(name_base.value)
  }
  if (!_is_name_ok(name_base.value)) return ''
  const b = _trim(name_base.value)
  const e = _trim(ext.value).replace(/^\./, '')
  if (!e) return b
  return `${b}.${e}`
})

const final_path_display = computed(() => {
  const base = base_dir_display.value || 'agent_files'
  const n = final_name.value
  if (!n) return ''
  return to_user_visible_path(`${base}/${n}`)
})

function on_confirm() {
  const n = final_name.value
  if (!n) return
  emit('confirm', { name: n, base_dir: base_dir_display.value || 'agent_files' })
}

function on_cancel() {
  emit('cancel')
}

const can_choose_child_dir = computed(() => typeof props.call_tool === 'function')
const child_panel_open = ref(false)
const child_loading = ref(false)
const child_dirs = ref([])
const child_loaded_key = ref('')

function _is_dir_type(t) {
  const s = String(t || '').toLowerCase()
  return s === 'directory' || s === 'dir' || s === 'folder'
}

const has_child_dirs = computed(() => {
  if (!can_choose_child_dir.value) return false
  if (child_loaded_key.value !== base_dir_display.value) return false
  return Array.isArray(child_dirs.value) && child_dirs.value.length > 0
})

async function _load_child_dirs(for_base_dir) {
  if (typeof props.call_tool !== 'function') {
    child_dirs.value = []
    child_loaded_key.value = for_base_dir || ''
    return
  }

  child_loading.value = true
  try {
    const r = await props.call_tool('nisb_dir_list', { path: for_base_dir || '' })
    const list = r && r.success && Array.isArray(r.entries) ? r.entries : []
    child_dirs.value = list
      .filter((e) => e && _is_dir_type(e.type))
      .filter((e) => !String(e.name || '').startsWith('.'))
      .map((e) => {
        const p = for_base_dir ? `${for_base_dir}/${e.name}` : e.name
        return { name: e.name, path: p }
      })
      .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
    child_loaded_key.value = for_base_dir || ''
  } catch (_e) {
    child_dirs.value = []
    child_loaded_key.value = for_base_dir || ''
  } finally {
    child_loading.value = false
  }
}

async function ensure_child_dirs_loaded() {
  const key = base_dir_display.value
  if (child_loaded_key.value === key) return
  await _load_child_dirs(key)
}

async function toggle_child_panel() {
  if (!can_choose_child_dir.value) return
  await ensure_child_dirs_loaded()
  child_panel_open.value = !child_panel_open.value
}

async function pick_child_dir(d) {
  const p = _norm_dir(d?.path || '')
  if (!p) return
  base_dir_local.value = p
  child_panel_open.value = false
  await ensure_child_dirs_loaded()
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
  } catch {
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
    } catch {}
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
  } catch {
    mo = null
  }
}

function teardown_theme_observer() {
  try {
    mo?.disconnect?.()
  } catch {}
  mo = null
  if (raf_id) cancelAnimationFrame(raf_id)
  raf_id = 0
}

const name_input_el = ref(null)

function on_doc_keydown(e) {
  if (e?.key === 'Escape') on_cancel()
}

onMounted(async () => {
  ensure_theme_src()
  sync_theme_vars_once()
  setup_theme_observer()

  document.addEventListener('keydown', on_doc_keydown, true)

  await nextTick()
  await ensure_child_dirs_loaded()
  try {
    name_input_el.value?.focus?.()
    name_input_el.value?.select?.()
  } catch {}
})

onUnmounted(() => {
  document.removeEventListener('keydown', on_doc_keydown, true)
  teardown_theme_observer()
})
</script>

<style scoped>
:global([data-nisb-modal="create-entry"]) {
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
  width: min(600px, calc(100vw - 36px));
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

.path-row,
.input-row {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  align-items: start;
  gap: 10px;
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

.name-input,
.ext-input {
  min-height: 40px;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.35;
}

.name-input {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0 10px;
}

.ext-split {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 0 2px;
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
  user-select: none;
}

.ext-input {
  flex: 0 0 74px;
  width: 74px;
  padding: 0 10px;
  border-left: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  color: var(--text-secondary);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

.name-input::placeholder,
.ext-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.preview {
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-main, var(--text));
  font-size: 0.76rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.preview .mono {
  overflow-wrap: anywhere;
}

.error {
  padding: 10px;
  border: 1px solid rgba(239, 68, 68, 0.36);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.10);
  color: #ef4444;
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

.muted {
  color: var(--text-secondary);
  opacity: 1;
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

@media (max-width: 640px) {
  :global([data-nisb-modal="create-entry"]) {
    align-items: stretch !important;
    padding: 0 !important;
  }

  .zen-modal {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

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
    grid-template-columns: 1fr auto 74px;
  }

  .name-input {
    min-width: 0;
  }
}
</style>

