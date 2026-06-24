<template>
  <Teleport to="body">
    <div
      ref="mask_el"
      class="zen-modal-mask"
      data-nisb-modal="batch-rename"
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
          <div class="title">{{ tt('files.batchRename.title') }}</div>
          <button class="icon-btn" :title="tt('common.close')" @click="on_cancel">✕</button>
        </div>

        <div class="zen-modal-body">
          <div class="top-info">
            <div class="pill">
              {{ tt('files.batchRename.selectedCountValue', { count }) }}
            </div>
            <div class="pill mono">
              {{ focus_dir_visible }}{{ focus_dir_visible ? '/' : '' }}
            </div>
          </div>

          <div class="grid">
            <div class="label">{{ tt('files.batchRename.applyTo') }}</div>
            <div class="field">
              <select v-model="apply_to" class="select">
                <option value="all">{{ tt('files.batchRename.applyToAll') }}</option>
                <option value="files">{{ tt('files.batchRename.applyToFiles') }}</option>
                <option value="dirs">{{ tt('files.batchRename.applyToDirs') }}</option>
              </select>
            </div>

            <div class="label">{{ tt('files.batchRename.prefix') }}</div>
            <div class="field">
              <input
                v-model="prefix"
                class="input mono"
                :placeholder="tt('files.batchRename.prefixPlaceholder')"
              />
            </div>

            <div class="label">{{ tt('files.batchRename.suffix') }}</div>
            <div class="field">
              <input
                v-model="suffix"
                class="input mono"
                :placeholder="tt('files.batchRename.suffixPlaceholder')"
              />
            </div>

            <div class="label">{{ tt('files.batchRename.find') }}</div>
            <div class="field">
              <input
                v-model="find_text"
                class="input mono"
                :placeholder="tt('files.batchRename.findPlaceholder')"
              />
            </div>

            <div class="label">{{ tt('files.batchRename.replace') }}</div>
            <div class="field">
              <input
                v-model="replace_text"
                class="input mono"
                :placeholder="tt('files.batchRename.replacePlaceholder')"
              />
            </div>

            <div class="label">{{ tt('files.batchRename.numbering') }}</div>
            <div class="field">
              <label class="chk">
                <input type="checkbox" v-model="numbering_enabled" />
                <span>{{ tt('files.batchRename.enable') }}</span>
              </label>

              <div class="num-row" v-if="numbering_enabled">
                <span class="muted">{{ tt('files.batchRename.numberingStart') }}</span>
                <input v-model.number="numbering_start" type="number" class="num" />

                <span class="muted">{{ tt('files.batchRename.numberingWidth') }}</span>
                <input v-model.number="numbering_pad" type="number" class="num" />

                <span class="muted">{{ tt('files.batchRename.numberingDelimiter') }}</span>
                <input
                  v-model="numbering_delim"
                  class="num mono"
                  :placeholder="tt('files.batchRename.numberingDelimiterPlaceholder')"
                />
              </div>
            </div>
          </div>

          <div class="preview-head">
            <div>{{ tt('files.batchRename.previewTitle') }}</div>
            <div v-if="has_conflict" class="warn">
              {{ tt('files.batchRename.conflictWarning') }}
            </div>
          </div>

          <div class="preview-list">
            <div v-for="row in preview_rows" :key="row.path" class="preview-row">
              <div class="old mono">{{ row.old_name }}</div>
              <div class="arrow">→</div>
              <div class="new mono" :class="{ bad: row.conflict }">{{ row.new_name }}</div>
            </div>
          </div>

          <div class="hint">
            {{ tt('files.batchRename.hint') }}
          </div>
        </div>

        <div class="zen-modal-footer">
          <button class="btn" @click="on_cancel">{{ tt('common.cancel') }}</button>
          <button class="btn primary" :disabled="!can_apply" @click="on_confirm">
            {{ tt('files.batchRename.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useDynamicModalI18n } from '../../../composables/use_dynamic_modal_i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'

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
      batchRename: {
        title: '规则批量重命名',
        selectedCountValue: '已选 {count} 项',
        applyTo: '作用对象',
        applyToAll: '文件 + 目录',
        applyToFiles: '仅文件',
        applyToDirs: '仅目录',
        prefix: '前缀',
        prefixPlaceholder: '例如：2026_',
        suffix: '后缀',
        suffixPlaceholder: '例如：_done',
        find: '查找',
        findPlaceholder: '例如：draft',
        replace: '替换',
        replacePlaceholder: '例如：final',
        numbering: '序号',
        enable: '启用',
        numberingStart: '起始',
        numberingWidth: '位宽',
        numberingDelimiter: '分隔',
        numberingDelimiterPlaceholder: '_',
        previewTitle: '预览（最多 30 项）',
        conflictWarning: '存在重名冲突，无法应用',
        hint: '说明：重命名只改变名称本身（保持原父目录不变）。文件会保留扩展名并在扩展名前应用序号。',
        confirm: '应用规则'
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
      batchRename: {
        title: 'Rule-based batch rename',
        selectedCountValue: '{count} item(s) selected',
        applyTo: 'Apply to',
        applyToAll: 'Files + directories',
        applyToFiles: 'Files only',
        applyToDirs: 'Directories only',
        prefix: 'Prefix',
        prefixPlaceholder: 'Example: 2026_',
        suffix: 'Suffix',
        suffixPlaceholder: 'Example: _done',
        find: 'Find',
        findPlaceholder: 'Example: draft',
        replace: 'Replace',
        replacePlaceholder: 'Example: final',
        numbering: 'Numbering',
        enable: 'Enable',
        numberingStart: 'Start',
        numberingWidth: 'Width',
        numberingDelimiter: 'Delimiter',
        numberingDelimiterPlaceholder: '_',
        previewTitle: 'Preview (up to 30 items)',
        conflictWarning: 'Name conflicts detected; cannot apply',
        hint: 'Note: renaming changes only the name itself and keeps the parent directory unchanged. Files keep their extensions, and numbering is applied before the extension.',
        confirm: 'Apply rules'
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
  items: { type: Array, default: () => [] }
})

const emit = defineEmits(['confirm', 'cancel'])

const apply_to = ref('files')
const prefix = ref('')
const suffix = ref('')
const find_text = ref('')
const replace_text = ref('')

const numbering_enabled = ref(false)
const numbering_start = ref(1)
const numbering_pad = ref(2)
const numbering_delim = ref('_')

function _norm_dir(s) {
  let v = String(s || '').trim()
  v = v.split('\\').join('/')
  while (v.startsWith('/')) v = v.slice(1)
  while (v.endsWith('/')) v = v.slice(0, -1)
  return v
}

const focus_dir_display = computed(() => _norm_dir(props.focus_dir || 'agent_files'))
const focus_dir_visible = computed(() => to_user_visible_path(focus_dir_display.value || 'agent_files'))

function _split_ext(name) {
  const s = String(name || '')
  const idx = s.lastIndexOf('.')
  if (idx <= 0) return { base: s, ext: '' }
  return { base: s.slice(0, idx), ext: s.slice(idx) }
}

function _pad_num(n, width) {
  const w = Math.max(0, Math.min(12, Number(width || 0)))
  const s = String(Math.max(0, Number(n || 0)))
  if (!w) return s
  return s.length >= w ? s : '0'.repeat(w - s.length) + s
}

function _is_file_type(type) {
  return String(type || '').toLowerCase() === 'file'
}

function _is_dir_type(type) {
  const t = String(type || '').toLowerCase()
  return t === 'directory' || t === 'dir' || t === 'folder'
}

function _should_apply(type) {
  if (apply_to.value === 'all') return true
  if (apply_to.value === 'files') return _is_file_type(type)
  if (apply_to.value === 'dirs') return _is_dir_type(type)
  return true
}

const normalized_items = computed(() => {
  const list = Array.isArray(props.items) ? props.items : []
  return list
    .map((x) => ({
      path: _norm_dir(x?.path || ''),
      name: String(x?.name || '').trim(),
      type: String(x?.type || '').trim()
    }))
    .filter((x) => !!x.path)
    .sort((a, b) => a.path.localeCompare(b.path))
})

const rename_map = computed(() => {
  const map = {}
  let seq = Number(numbering_start.value || 1)

  for (const it of normalized_items.value) {
    const old_name = it.name || it.path.split('/').pop() || it.path
    let new_name = old_name

    if (_should_apply(it.type)) {
      const is_file = _is_file_type(it.type)
      const { base, ext } = is_file ? _split_ext(old_name) : { base: old_name, ext: '' }

      let b = base
      const f = String(find_text.value || '')
      const r = String(replace_text.value || '')

      if (f) {
        try {
          b = b.split(f).join(r)
        } catch {}
      }

      b = String(prefix.value || '') + b + String(suffix.value || '')

      if (numbering_enabled.value) {
        const num = _pad_num(seq, numbering_pad.value)
        const delim = String(numbering_delim.value || '_')
        b = b + delim + num
        seq += 1
      }

      new_name = is_file ? `${b}${ext}` : b
    }

    map[it.path] = { old_name, new_name, type: it.type }
  }

  return map
})

const conflict_set = computed(() => {
  const seen = new Set()
  const conflict = new Set()

  for (const it of normalized_items.value) {
    const x = rename_map.value[it.path]
    const key = `${it.type}::${String(x?.new_name || '').trim()}`
    if (seen.has(key)) conflict.add(key)
    else seen.add(key)
  }

  return conflict
})

const has_conflict = computed(() => conflict_set.value.size > 0)

const preview_rows = computed(() => {
  const rows = []
  for (const it of normalized_items.value.slice(0, 30)) {
    const x = rename_map.value[it.path]
    const key = `${it.type}::${String(x?.new_name || '').trim()}`
    rows.push({
      path: it.path,
      old_name: x?.old_name || '',
      new_name: x?.new_name || '',
      conflict: conflict_set.value.has(key)
    })
  }
  return rows
})

const can_apply = computed(() => {
  if (!normalized_items.value.length) return false
  if (has_conflict.value) return false

  for (const it of normalized_items.value) {
    const x = rename_map.value[it.path]
    if (x && x.old_name !== x.new_name) return true
  }

  return false
})

function on_confirm() {
  if (!can_apply.value) return
  emit('confirm', {
    apply_to: apply_to.value,
    prefix: String(prefix.value || ''),
    suffix: String(suffix.value || ''),
    find_text: String(find_text.value || ''),
    replace_text: String(replace_text.value || ''),
    numbering_enabled: !!numbering_enabled.value,
    numbering_start: Number(numbering_start.value || 1),
    numbering_pad: Number(numbering_pad.value || 0),
    numbering_delim: String(numbering_delim.value || '_')
  })
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

function on_doc_keydown(e) {
  if (e?.key === 'Escape') on_cancel()
}

onMounted(async () => {
  ensure_theme_src()
  sync_theme_vars_once()
  setup_theme_observer()

  document.addEventListener('keydown', on_doc_keydown, true)

  await nextTick()
})

onUnmounted(() => {
  document.removeEventListener('keydown', on_doc_keydown, true)
  teardown_theme_observer()
})
</script>

<style scoped>
:global([data-nisb-modal="batch-rename"]) {
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
    radial-gradient(circle at 82% 8%, color-mix(in srgb, #d97706 9%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.34) !important;
}

.zen-modal {
  width: min(860px, calc(100vw - 36px));
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

.top-info {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.pill {
  max-width: 100%;
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 68%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  overflow-wrap: anywhere;
}

.grid {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
}

.label {
  padding-top: 8px;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.field {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.input,
.select,
.num {
  min-height: 36px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-main, var(--text));
  outline: none;
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.35;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.input {
  width: 100%;
  padding: 0 10px;
}

.select {
  width: min(260px, 100%);
  padding: 0 10px;
}

.num {
  width: 74px;
  padding: 0 8px;
}

.input::placeholder,
.num::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.input:focus,
.select:focus,
.num:focus {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.chk {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 56%, transparent);
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1;
}

.chk input {
  accent-color: var(--selected);
}

.num-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.muted {
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.4;
}

.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 780;
  line-height: 1.35;
}

.warn {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid rgba(239, 68, 68, 0.36);
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.10);
  color: #ef4444;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1;
  overflow-wrap: break-word;
}

.preview-list {
  max-height: 280px;
  overflow: auto;
  display: grid;
  gap: 6px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  scrollbar-width: thin;
}

.preview-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 7px 8px;
  border: 1px solid color-mix(in srgb, var(--line) 64%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--sidebar-bg) 54%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.35;
}

.old,
.new {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.old {
  color: var(--text-secondary);
}

.new {
  color: var(--text-main, var(--text));
  font-weight: 740;
}

.arrow {
  text-align: center;
  color: var(--text-secondary);
  opacity: 0.78;
}

.new.bad {
  color: #ef4444;
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

@media (max-width: 720px) {
  :global([data-nisb-modal="batch-rename"]) {
    align-items: stretch !important;
    padding: 0 !important;
  }

  .zen-modal {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

  .grid {
    grid-template-columns: 1fr;
    gap: 7px;
  }

  .label {
    padding-top: 0;
  }

  .preview-head,
  .zen-modal-footer {
    display: grid;
    grid-template-columns: 1fr;
  }

  .btn {
    width: 100%;
  }

  .preview-row {
    grid-template-columns: 1fr;
    gap: 5px;
  }

  .arrow {
    text-align: left;
  }

  .old,
  .new {
    white-space: normal;
    overflow-wrap: anywhere;
  }
}

@media (max-width: 420px) {
  .zen-modal-header,
  .zen-modal-body,
  .zen-modal-footer {
    padding-left: 10px;
    padding-right: 10px;
  }

  .field,
  .num-row {
    display: grid;
    grid-template-columns: 1fr;
    width: 100%;
  }

  .select,
  .num,
  .chk {
    width: 100%;
  }
}
</style>

