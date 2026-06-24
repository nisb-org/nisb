<template>
  <div
    class="outline-list"
    :class="[
      { stale: outline_stale },
      `source-${outline_source}`
    ]"
  >
    <div v-if="outline_source === 'note' && loading" class="muted">
      <span class="muted-dot"></span>
      <span class="muted-text">{{ noteLoadingText }}</span>
    </div>

    <div
      v-for="h in headings"
      :key="h.key"
      class="outline-item"
      :class="{
        hidden: h.hidden,
        clickable: h.has_children,
        childless: !h.has_children,
        collapsed: h.collapsed,
        hovering: h.key === hovering_key
      }"
      :style="{
        '--outline-indent': `${Math.max(0, Number(h.level || 1) - 1) * 14}px`,
        '--outline-color': h.color || 'var(--selected)'
      }"
      role="button"
      :tabindex="h.hidden ? -1 : 0"
      :aria-expanded="h.has_children ? String(!h.collapsed) : undefined"
      @click="handle_click(h, $event)"
      @keydown.enter.prevent="handle_click(h, $event)"
      @keydown.space.prevent="handle_click(h, $event)"
      @mouseenter="handle_mouse_enter(h)"
      @mouseleave="handle_mouse_leave"
    >
      <span class="outline-rail" aria-hidden="true"></span>

      <button
        v-if="h.has_children"
        type="button"
        class="collapse-icon-small"
        :class="{ collapsed: h.collapsed }"
        @click.stop="toggle_heading(h)"
      >
        {{ h.collapsed ? '▸' : '▾' }}
      </button>

      <span v-else class="collapse-spacer" aria-hidden="true"></span>

      <span class="outline-text" :title="h.text">{{ h.text }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import useMCP from '../../composables/useMCP'

const emit = defineEmits(['collapsedChanged'])
const { callTool } = useMCP()
const { t } = useI18n()

const headings = ref([])
const hovering_key = ref(null)
const loading = ref(false)
const outline_stale = ref(false)

const outline_source = ref('note') // note / chat / room / epub

const NOTE_STORAGE_KEY = 'nisb_editor_content'
const OUTLINE_HOVER_ENABLED_KEY = 'nisb_outline_hover_enabled'
const OUTLINE_CTX_EVENT = 'nisb-outline-context'

// v4：强制失效旧 v3 缓存，避免 anchor_key 规则变化后“缓存命中但跳不动”
const CACHE_PREFIX = 'nisb_outline_cache_v4:'
const CACHE_INDEX_KEY = 'nisb_outline_cache_index_v4'

// 旧版（v3）清理用
const OLD_CACHE_PREFIX = 'nisb_outline_cache_v3:'
const OLD_CACHE_INDEX_KEY = 'nisb_outline_cache_index_v3'

const CACHE_MAX_ITEMS = 18
const CACHE_MAX_TOTAL_BYTES = 2_200_000
const CACHE_MAX_ENTRY_BYTES = 420_000
const CACHE_MAX_HEADINGS = 9000

// ✅ 本轮最终落点：2000 行起统一进入全量大纲 / 稳定跳转链路
const OUTLINE_FULL_READ_THRESHOLD_LINES = 2000

let preview_timer = null

const ctx_path = ref('')
const ctx_line_count = ref(0)
const ctx_use_lazy_markdown = ref(false)
const ctx_is_markdown = ref(false)
const ctx_seq = ref(0)
const ctx_content_text = ref('')

const outline_hover_enabled = ref(true)

const noteLoadingText = computed(() =>
  outline_stale.value
    ? t('rightSidebar.noteOutline.updating')
    : t('rightSidebar.noteOutline.generating')
)

// ✅ 超大 md 全量读：驻留门槛（避免“点一下马上切走也发起大请求”）
const FULL_READ_DWELL_MS = 260
let __full_read_timer = null
let __full_read_inflight = null // { path, started_ts, promise }

// 记录“当前右侧栏已经确认落地过的大纲对应 path”
// 目的：禁止跨文档错误复用 localStorage 的旧正文快照
let __resolved_outline_path = ''

function _request_idle(cb, { timeout = 800 } = {}) {
  if (typeof window.requestIdleCallback === 'function') return window.requestIdleCallback(cb, { timeout })
  return window.setTimeout(() => cb({ didTimeout: true, timeRemaining: () => 0 }), 0)
}

function _cancel_idle(id) {
  try {
    if (typeof window.cancelIdleCallback === 'function') window.cancelIdleCallback(id)
    else clearTimeout(id)
  } catch {}
}

function normalize_incoming_headings(hs, prefix) {
  const arr = Array.isArray(hs) ? hs : []
  const seen = new Map()

  function pick(v) {
    const s = String(v ?? '').trim()
    return s
  }

  return arr.map((h, i) => {
    const obj = h && typeof h === 'object' ? { ...h } : { text: String(h || '').trim() }

    const text =
      pick(obj.text) ||
      pick(obj.title) ||
      pick(obj.label) ||
      t('rightSidebar.noteOutline.untitledItem', { index: i + 1 })
    const anchor = pick(obj.anchor) || pick(obj.href) || ''
    const level = Number.isFinite(Number(obj.level)) ? Math.max(1, Math.min(6, Number(obj.level))) : 2
    const color = pick(obj.color) || `var(--h${Math.max(1, Math.min(6, level))})`

    const collapsed = !!(obj.collapsed ?? false)
    const hidden = !!(obj.hidden ?? false)

    const has_children =
      typeof obj.has_children === 'boolean'
        ? obj.has_children
        : typeof obj.hasChildren === 'boolean'
          ? obj.hasChildren
          : false

    const raw0 =
      pick(obj.key) ||
      pick(obj.id) ||
      (anchor ? `a:${anchor}` : '') ||
      (text ? `t:${text}` : '') ||
      `i:${i}`

    let base_key = `${prefix}:${raw0}`
    if (base_key.length > 220) base_key = `${prefix}:i:${i}`

    const n = seen.get(base_key) || 0
    seen.set(base_key, n + 1)
    const uniq_key = n > 0 ? `${base_key}#${n}` : base_key

    return {
      ...obj,
      key: uniq_key,
      id: uniq_key,
      level,
      text,
      anchor,
      color,
      collapsed,
      hidden,
      has_children,
      hasChildren: has_children
    }
  })
}

function _safe_read_hover_enabled() {
  try {
    const v = String(localStorage.getItem(OUTLINE_HOVER_ENABLED_KEY) || '').trim()
    if (v === '0') return false
    if (v === '1') return true
  } catch {}
  return true
}

/* -----------------------
 * Anchor_key: MUST match LazyMarkdown rules
 * ----------------------- */

function _normalize_slug(slug) {
  let s = String(slug || '')

  s = s.replace(/[\u200B-\u200D\uFEFF]/g, '')
  s = s.replace(/-+/g, '-').replace(/^-+/, '').replace(/-+$/, '')

  if (s.length >= 6 && s.length % 2 === 0) {
    const half = s.length / 2
    const a = s.slice(0, half)
    const b = s.slice(half)
    if (a && a === b) s = a
  }

  return s
}

function _slugify(text) {
  const raw = String(text || '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fa5\-]/g, '')
  return _normalize_slug(raw)
}

function _clean_heading_text(raw) {
  let s = String(raw || '').trim()
  if (!s) return ''
  s = s.replace(/[\u200B-\u200D\uFEFF]/g, '')
  s = s.replace(/<[^>]*>/g, '')
  s = s.replace(/`+/g, '')
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
  s = s.replace(/\*([^*]+)\*/g, '$1')
  s = s.replace(/~~([^~]+)~~/g, '$1')
  s = s.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  return s.trim()
}

function _color_for_level(level) {
  const n = Math.max(1, Math.min(6, Number(level || 1)))
  return `var(--h${n})`
}

function _apply_has_children(list) {
  const stack = []
  for (let i = 0; i < list.length; i++) {
    const cur = list[i]
    while (stack.length && cur.level <= stack[stack.length - 1].level) stack.pop()
    if (stack.length) stack[stack.length - 1].has_children = true
    stack.push(cur)
  }
}

function _apply_collapse_hidden(list) {
  const parents = []
  for (let i = 0; i < list.length; i++) {
    const cur = list[i]
    while (parents.length && cur.level <= parents[parents.length - 1].level) parents.pop()
    cur.hidden = parents.some((p) => p.collapsed)
    parents.push(cur)
  }
}

function _merge_old_state(new_list, old_list) {
  const old_by_anchor = new Map()
  for (const h of Array.isArray(old_list) ? old_list : []) {
    const k = String(h.anchor || '')
    if (!k) continue
    if (!old_by_anchor.has(k)) old_by_anchor.set(k, h)
  }
  for (const h of new_list) {
    const old = old_by_anchor.get(String(h.anchor || ''))
    if (!old) continue
    h.collapsed = !!old.collapsed
  }
  _apply_collapse_hidden(new_list)
}

function _emit_outline_jump(h, preview = false) {
  const raw = String(h?.anchor || '').trim()
  let base_anchor = ''
  let occ = null

  if (raw.includes('--')) {
    const parts = raw.split('--')
    const last = parts.pop()
    base_anchor = parts.join('--')
    const n = Number(last)
    occ = Number.isFinite(n) ? n : null
  } else {
    base_anchor = raw
    occ = null
  }

  window.dispatchEvent(
    new CustomEvent('nisb-outline-jump', {
      detail: {
        anchor: raw,
        text: String(h?.text || '').trim(),
        preview: !!preview,
        anchor_key: raw,
        base_anchor,
        occ
      }
    })
  )
}

function toggle_heading(h) {
  if (!h.has_children) return
  h.collapsed = !h.collapsed
  _apply_collapse_hidden(headings.value)
}

function handle_click(h, event) {
  if (outline_stale.value) return

  const target = event?.target
  if (target && target.classList && target.classList.contains('collapse-icon-small')) {
    toggle_heading(h)
    return
  }
  if (h.has_children && (event?.ctrlKey || event?.metaKey)) {
    toggle_heading(h)
    return
  }
  _emit_outline_jump(h, false)
}

function handle_mouse_enter(h) {
  if (outline_stale.value) return

  hovering_key.value = String(h?.key || h?.id || '').trim() || null
  clearTimeout(preview_timer)
  if (!outline_hover_enabled.value) return
  preview_timer = setTimeout(() => _emit_outline_jump(h, true), 0)
}

function handle_mouse_leave() {
  hovering_key.value = null
  clearTimeout(preview_timer)
}

function toggle_all() {
  if (!headings.value.length) return
  const any_expanded = headings.value.some((h) => h.has_children && !h.collapsed)
  const next_collapsed = any_expanded

  emit('collapsedChanged', next_collapsed)

  const min_level = Math.min(...headings.value.map((h) => h.level))
  for (const h of headings.value) {
    if (h.level === min_level) {
      if (h.has_children) h.collapsed = next_collapsed
      h.hidden = false
    } else {
      h.hidden = false
    }
  }
  _apply_collapse_hidden(headings.value)
}

/* -----------------------
 * Cache (bounded + idle write)
 * ----------------------- */

function _cache_key(path) {
  return `${CACHE_PREFIX}${path}`
}

function _safe_json_parse(raw) {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function _load_cache_index() {
  try {
    const raw = localStorage.getItem(CACHE_INDEX_KEY)
    const obj = _safe_json_parse(raw || '')
    if (obj && typeof obj === 'object' && Array.isArray(obj.items)) return obj
  } catch {}
  return { items: [] }
}

function _save_cache_index(idx) {
  try {
    localStorage.setItem(CACHE_INDEX_KEY, JSON.stringify(idx))
  } catch {}
}

function _prune_cache_index() {
  const idx = _load_cache_index()
  const items = Array.isArray(idx.items) ? idx.items : []

  const uniq = new Map()
  for (const it of items) {
    const k = String(it?.k || '')
    if (!k) continue
    const ts = Number(it?.ts || 0)
    const bytes = Number(it?.bytes || 0)
    if (!uniq.has(k) || ts > Number(uniq.get(k).ts || 0)) uniq.set(k, { k, ts, bytes })
  }

  const arr = Array.from(uniq.values()).sort((a, b) => Number(b.ts || 0) - Number(a.ts || 0))

  const kept = []
  let total = 0

  for (const it of arr) {
    if (kept.length >= CACHE_MAX_ITEMS) {
      try {
        localStorage.removeItem(String(it.k))
      } catch {}
      continue
    }
    const bytes = Math.max(0, Number(it.bytes || 0))
    if (total + bytes > CACHE_MAX_TOTAL_BYTES) {
      try {
        localStorage.removeItem(String(it.k))
      } catch {}
      continue
    }
    kept.push({ k: String(it.k), ts: Number(it.ts || 0), bytes })
    total += bytes
  }

  _save_cache_index({ items: kept })
}

function _cache_try_get(path) {
  const key = _cache_key(path)
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const obj = _safe_json_parse(raw)
    const hs = Array.isArray(obj?.headings) ? obj.headings : null
    if (!hs || !hs.length) return null
    if (hs.length > CACHE_MAX_HEADINGS) return null
    return { key, obj, headings: hs }
  } catch {
    return null
  }
}

let __cache_write_idle_id = null

function _cache_schedule_put(path, payload, seq, is_stale) {
  if (!path) return

  let json = ''
  try {
    json = JSON.stringify(payload)
  } catch {
    return
  }

  if (!json) return
  if (json.length > CACHE_MAX_ENTRY_BYTES) return

  if (__cache_write_idle_id !== null) {
    _cancel_idle(__cache_write_idle_id)
    __cache_write_idle_id = null
  }

  __cache_write_idle_id = _request_idle(
    () => {
      __cache_write_idle_id = null
      if (is_stale()) return
      if (seq !== __load_seq) return

      const k = _cache_key(path)
      try {
        localStorage.setItem(k, json)
      } catch {}

      const idx = _load_cache_index()
      const items = Array.isArray(idx.items) ? idx.items : []
      items.push({ k, ts: Date.now(), bytes: json.length })
      _save_cache_index({ items })

      _prune_cache_index()
    },
    { timeout: 1500 }
  )
}

function _cleanup_old_cache_v3() {
  _request_idle(
    () => {
      let removed = 0
      try {
        localStorage.removeItem(OLD_CACHE_INDEX_KEY)
      } catch {}

      try {
        const keys = []
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i)
          if (k) keys.push(k)
        }
        for (const k of keys) {
          if (typeof k === 'string' && k.startsWith(OLD_CACHE_PREFIX)) {
            try {
              localStorage.removeItem(k)
              removed += 1
            } catch {}
            if (removed >= 80) break
          }
        }
      } catch {}
    },
    { timeout: 2000 }
  )
}

/* -----------------------
 * Parsing (yielding)
 * ----------------------- */

function _signature(text) {
  const s = String(text || '')
  const len = s.length
  const head = s.slice(0, 128)
  const tail = s.slice(Math.max(0, len - 128))
  return `${len}:${head}:${tail}`
}

function _need_full_read({ line_count }) {
  const n = Math.max(0, Number(line_count || 0))
  return n >= OUTLINE_FULL_READ_THRESHOLD_LINES
}

function _yield_to_main() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

async function _parse_md_headings(text, { max_chars = 900_000, max_lines = 30_000 } = {}, is_stale) {
  const s0 = String(text || '')
  if (!s0) return []

  const s = s0.length > max_chars ? s0.slice(0, max_chars) : s0
  const out = []

  let in_fence = false
  let line_no = 0
  let i = 0

  const occ_map = new Map()

  let slice_start = typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()

  while (i <= s.length) {
    if (is_stale && is_stale()) return null

    const nl = s.indexOf('\n', i)
    const line_end = nl === -1 ? s.length : nl
    const line = s.slice(i, line_end)

    line_no += 1
    if (line_no > max_lines) break

    const trimmed = line.trim()
    if (trimmed.startsWith('```')) {
      in_fence = !in_fence
    } else if (!in_fence) {
      let h = 0
      while (h < 6 && h < line.length && line.charCodeAt(h) === 35) h++
      if (h >= 1 && h <= 6) {
        const next_ch = line.charCodeAt(h)
        const is_space = next_ch === 32 || next_ch === 9
        if (is_space) {
          const raw_text = line.slice(h).trim()
          const clean = _clean_heading_text(raw_text)
          const base = _slugify(clean)
          const prev = occ_map.get(base) || 0
          const occ = prev + 1
          occ_map.set(base, occ)

          const anchor = base ? `${base}--${occ}` : `h--${occ}`

          out.push({
            key: `note:${line_no}:${anchor}`,
            id: `note:${line_no}:${anchor}`,
            level: h,
            text: clean || base || anchor,
            anchor,
            color: _color_for_level(h),
            collapsed: false,
            hidden: false,
            has_children: false,
            hasChildren: false
          })
        }
      }
    }

    if (nl === -1) break
    i = nl + 1

    const now = typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()
    if (now - slice_start > 10) {
      await _yield_to_main()
      slice_start = typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()
    }
  }

  _apply_has_children(out)
  out.forEach((h) => (h.hasChildren = !!h.has_children))
  return out
}

/* -----------------------
 * Main load (debounced + latest-only)
 * ----------------------- */

let __alive = true
let __load_seq = 0
let __raw_text = ''

let __pending_load_timer = null
let __last_ctx_key = ''

function _ctx_key() {
  return [
    String(ctx_path.value || '').trim(),
    String(ctx_line_count.value || 0),
    ctx_use_lazy_markdown.value ? '1' : '0',
    ctx_is_markdown.value ? '1' : '0',
    String(outline_source.value || ''),
    String(ctx_seq.value || 0),
    _signature(String(ctx_content_text.value || ''))
  ].join('|')
}

function _clear_full_read_timer() {
  if (__full_read_timer) clearTimeout(__full_read_timer)
  __full_read_timer = null
}

function _schedule_load_note_outline() {
  if (outline_source.value !== 'note') return
  if (__pending_load_timer) clearTimeout(__pending_load_timer)
  __pending_load_timer = setTimeout(() => {
    __pending_load_timer = null
    _load_note_outline()
  }, 30)
}

async function _maybe_await_inflight_for_same_path(path, is_stale) {
  const inf = __full_read_inflight
  if (!inf) return null
  const same = String(inf.path || '') === String(path || '')
  const too_old = Date.now() - Number(inf.started_ts || 0) > 20_000
  if (!same || too_old) return null
  try {
    const res = await inf.promise
    if (is_stale()) return null
    return res
  } catch {
    return null
  }
}

function _start_inflight(path, p) {
  __full_read_inflight = { path: String(path || ''), started_ts: Date.now(), promise: p }
  p.finally(() => {
    if (__full_read_inflight && __full_read_inflight.promise === p) __full_read_inflight = null
  })
}

async function _load_note_outline() {
  const cur_key = _ctx_key()
  if (cur_key && cur_key === __last_ctx_key && headings.value && headings.value.length) return
  __last_ctx_key = cur_key

  const seq = ++__load_seq

  if (outline_source.value !== 'note') return
  if (!ctx_is_markdown.value) return

  const path = String(ctx_path.value || '').trim()
  const line_count = Number(ctx_line_count.value || 0)

  const is_stale = () => !__alive || seq !== __load_seq

  _clear_full_read_timer()

  if (!path) {
    loading.value = false
    outline_stale.value = false
    __raw_text = ''
    __resolved_outline_path = ''
    headings.value = []
    return
  }

  let local_text = String(ctx_content_text.value || '')
  const can_use_storage_fallback = !local_text && path && path === __resolved_outline_path

  if (!local_text && can_use_storage_fallback) {
    try {
      local_text = String(localStorage.getItem(NOTE_STORAGE_KEY) || '')
    } catch {
      local_text = ''
    }
  }

  if (!local_text && !can_use_storage_fallback) {
    const need_full_without_local = _need_full_read({
      line_count
    })

    if (!need_full_without_local) {
      loading.value = true
      outline_stale.value = true
      return
    }
  }

  const local_headings = await _parse_md_headings(local_text, { max_chars: 900_000, max_lines: 30_000 }, is_stale)
  if (is_stale()) return
  const local_headings_list = Array.isArray(local_headings) ? local_headings : []

  const need_full = _need_full_read({
    line_count
  })

  if (!need_full) {
    const next = local_headings_list
    _merge_old_state(next, headings.value)
    headings.value = next
    __resolved_outline_path = path
    outline_stale.value = false
    loading.value = false
    __raw_text = ''
    return
  }

  const cached = _cache_try_get(path)
  if (cached && cached.headings && cached.headings.length) {
    const next = cached.headings.map((h, idx) => ({
      key: String(h.key || `cache:${idx}:${h.anchor || ''}`),
      id: String(h.id || h.key || `cache:${idx}:${h.anchor || ''}`),
      level: Number(h.level || 1),
      text: String(h.text || ''),
      anchor: String(h.anchor || ''),
      color: String(h.color || _color_for_level(h.level || 1)),
      collapsed: false,
      hidden: false,
      has_children: false,
      hasChildren: false
    }))
    _apply_has_children(next)
    next.forEach((x) => (x.hasChildren = !!x.has_children))
    _merge_old_state(next, headings.value)
    headings.value = next
    __resolved_outline_path = path
  } else if (local_headings_list.length) {
    const next = local_headings_list
    _merge_old_state(next, headings.value)
    headings.value = next
    __resolved_outline_path = path
  }

  loading.value = true

  __full_read_timer = setTimeout(async () => {
    __full_read_timer = null
    if (is_stale()) return

    const reused = await _maybe_await_inflight_for_same_path(path, is_stale)
    if (is_stale()) return

    let res = reused
    if (!res) {
      const p = callTool('nisb_file_read', { filename: path })
      _start_inflight(path, p)
      try {
        res = await p
      } catch {
        if (is_stale()) return
        loading.value = false
        outline_stale.value = false
        return
      }
    }

    if (is_stale()) return

    const ok = res && (res.success === undefined || res.success === true)
    if (!ok) {
      loading.value = false
      outline_stale.value = false
      return
    }

    const raw = typeof res?.content === 'string' ? res.content : String(res?.content || '')
    if (is_stale()) return

    if (!raw.trim()) {
      headings.value = []
      __resolved_outline_path = path
      loading.value = false
      outline_stale.value = false
      return
    }

    __raw_text = raw

    const sig = _signature(__raw_text)
    const parsed = await _parse_md_headings(__raw_text, { max_chars: 20_000_000, max_lines: 1_000_000 }, is_stale)
    if (is_stale()) return
    const parsed_list = Array.isArray(parsed) ? parsed : []

    _merge_old_state(parsed_list, headings.value)
    headings.value = parsed_list
    __resolved_outline_path = path

    const minimal = parsed_list.slice(0, CACHE_MAX_HEADINGS).map((h) => ({
      key: String(h.key || ''),
      id: String(h.id || h.key || ''),
      level: Number(h.level || 1),
      text: String(h.text || ''),
      anchor: String(h.anchor || ''),
      color: String(h.color || _color_for_level(h.level || 1))
    }))

    _cache_schedule_put(path, { sig, ts: Date.now(), headings: minimal }, seq, is_stale)

    loading.value = false
    outline_stale.value = false
    __raw_text = ''
  }, FULL_READ_DWELL_MS)
}

/* -----------------------
 * Events
 * ----------------------- */

function _handle_outline_mode_changed(e) {
  const mode = String(e?.detail?.mode || '').trim()
  _clear_full_read_timer()

  outline_stale.value = false

  if (mode === 'chat') {
    outline_source.value = 'chat'
    headings.value = []
    loading.value = false
    __raw_text = ''
    hovering_key.value = null
    return
  }

  if (mode === 'room') {
    outline_source.value = 'room'
    headings.value = []
    loading.value = false
    __raw_text = ''
    hovering_key.value = null
    return
  }

  if (mode === 'epub') {
    outline_source.value = 'epub'
    headings.value = []
    loading.value = false
    __raw_text = ''
    hovering_key.value = null
    return
  }

  outline_source.value = 'note'
  headings.value = []
  loading.value = false
  __raw_text = ''
  hovering_key.value = null
  _schedule_load_note_outline()
}

function _handle_chat_outline_update(e) {
  _clear_full_read_timer()
  const hs = e?.detail?.headings
  outline_source.value = 'chat'
  outline_stale.value = false
  loading.value = false
  __raw_text = ''
  headings.value = normalize_incoming_headings(hs, 'chat')
}

function _handle_room_outline_update(e) {
  _clear_full_read_timer()
  const hs = e?.detail?.headings
  outline_source.value = 'room'
  outline_stale.value = false
  loading.value = false
  __raw_text = ''
  headings.value = normalize_incoming_headings(hs, 'room')
}

function _handle_epub_outline_update(e) {
  _clear_full_read_timer()
  const hs = e?.detail?.headings
  outline_source.value = 'epub'
  outline_stale.value = false
  loading.value = false
  __raw_text = ''
  headings.value = normalize_incoming_headings(hs, 'epub')
}

function _handle_hover_enabled_changed(e) {
  const enabled = e?.detail?.enabled
  if (typeof enabled === 'boolean') outline_hover_enabled.value = enabled
}

function _handle_outline_context(e) {
  const d = e?.detail || {}

  const incoming_seq = Number(d.seq || 0) || 0
  const incoming_path = String(d.path || '').trim()

  const prev_path = String(ctx_path.value || '').trim()
  const prev_seq = Number(ctx_seq.value || 0)

  const path_changed = incoming_path && incoming_path !== prev_path
  const seq_changed = incoming_seq > 0 && incoming_seq !== prev_seq

  ctx_path.value = incoming_path
  ctx_line_count.value = Number(d.line_count || 0)
  ctx_use_lazy_markdown.value = !!d.use_lazy_markdown
  ctx_is_markdown.value = !!d.is_markdown
  ctx_seq.value = incoming_seq > 0 ? incoming_seq : prev_seq + 1
  ctx_content_text.value = typeof d.content_text === 'string' ? d.content_text : ''

  if (!ctx_path.value || !ctx_is_markdown.value) {
    __load_seq += 1
    _clear_full_read_timer()
    loading.value = false
    outline_stale.value = false
    __raw_text = ''
    hovering_key.value = null
    __resolved_outline_path = ''
    if (outline_source.value === 'note') headings.value = []
    return
  }

  if (outline_source.value !== 'note') return

  if (path_changed || seq_changed) {
    __load_seq += 1
    _clear_full_read_timer()
    __raw_text = ''
    hovering_key.value = null

    outline_stale.value = true
    loading.value = true

    __last_ctx_key = ''
  }

  _schedule_load_note_outline()
}

onMounted(() => {
  __alive = true
  outline_hover_enabled.value = _safe_read_hover_enabled()

  _cleanup_old_cache_v3()

  window.addEventListener('nisb-outline-mode-changed', _handle_outline_mode_changed)
  window.addEventListener('nisb-chat-outline-update', _handle_chat_outline_update)
  window.addEventListener('nisb-room-outline-update', _handle_room_outline_update)
  window.addEventListener('nisb-epub-outline-update', _handle_epub_outline_update)
  window.addEventListener('nisb-outline-hover-enabled-changed', _handle_hover_enabled_changed)
  window.addEventListener(OUTLINE_CTX_EVENT, _handle_outline_context)
})

onUnmounted(() => {
  __alive = false
  __load_seq += 1
  loading.value = false
  outline_stale.value = false
  __raw_text = ''
  hovering_key.value = null

  clearTimeout(preview_timer)
  if (__pending_load_timer) clearTimeout(__pending_load_timer)
  __pending_load_timer = null

  _clear_full_read_timer()

  if (__cache_write_idle_id !== null) {
    _cancel_idle(__cache_write_idle_id)
    __cache_write_idle_id = null
  }

  window.removeEventListener('nisb-outline-mode-changed', _handle_outline_mode_changed)
  window.removeEventListener('nisb-chat-outline-update', _handle_chat_outline_update)
  window.removeEventListener('nisb-room-outline-update', _handle_room_outline_update)
  window.removeEventListener('nisb-epub-outline-update', _handle_epub_outline_update)
  window.removeEventListener('nisb-outline-hover-enabled-changed', _handle_hover_enabled_changed)
  window.removeEventListener(OUTLINE_CTX_EVENT, _handle_outline_context)
})

defineExpose({ toggleAll: toggle_all })
</script>

<style scoped>
.outline-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  padding: 0.55rem 0.5rem 0.7rem;
  scrollbar-width: thin;
}

.outline-list.stale {
  opacity: 0.72;
}

.outline-list.stale .outline-item {
  filter: saturate(0.78);
}

.outline-item {
  --outline-indent: 0px;
  --outline-color: var(--selected);

  position: relative;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.34rem;
  padding: 0.34rem 0.48rem 0.34rem calc(var(--outline-indent) + 0.62rem);
  border: 1px solid transparent;
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 650;
  line-height: 1.32;
  outline: none;
  overflow: hidden;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.outline-item::before {
  content: '';
  position: absolute;
  left: calc(var(--outline-indent) + 0.34rem);
  top: 7px;
  bottom: 7px;
  width: 3px;
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--outline-color) 92%, white 4%),
      color-mix(in srgb, var(--outline-color) 62%, transparent)
    );
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--outline-color) 20%, transparent);
  opacity: 0.72;
}

.outline-item::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background:
    radial-gradient(
      circle at calc(var(--outline-indent) + 0.46rem) 50%,
      color-mix(in srgb, var(--outline-color) 11%, transparent),
      transparent 34%
    );
  opacity: 0;
  transition: opacity 0.15s ease;
}

.outline-item.hidden {
  display: none;
}

.outline-item.clickable {
  font-weight: 760;
}

.outline-item.childless {
  font-weight: 640;
}

.outline-item:hover,
.outline-item:focus-visible,
.outline-item.hovering {
  border-color: color-mix(in srgb, var(--outline-color) 30%, var(--line));
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--outline-color) 12%, var(--selected-bg)),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--text-main, var(--text));
  transform: translateX(2px);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
}

.outline-item:hover::before,
.outline-item:focus-visible::before,
.outline-item.hovering::before {
  width: 4px;
  opacity: 0.95;
}

.outline-item:hover::after,
.outline-item:focus-visible::after,
.outline-item.hovering::after {
  opacity: 1;
}

.outline-item.collapsed {
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--outline-color) 7%, transparent),
      color-mix(in srgb, var(--editor-bg) 34%, transparent)
    );
}

.outline-rail {
  position: absolute;
  left: calc(var(--outline-indent) + 0.26rem);
  top: 50%;
  width: 8px;
  height: 8px;
  border: 1px solid color-mix(in srgb, var(--outline-color) 36%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--outline-color) 26%, var(--editor-bg));
  transform: translateY(-50%);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.outline-item:hover .outline-rail,
.outline-item:focus-visible .outline-rail,
.outline-item.hovering .outline-rail {
  opacity: 0.85;
}

.collapse-icon-small,
.collapse-spacer {
  position: relative;
  z-index: 1;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
}

.collapse-icon-small {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--outline-color) 22%, var(--line));
  border-radius: 8px;
  background: color-mix(in srgb, var(--outline-color) 7%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.82;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.12s ease,
    opacity 0.15s ease;
}

.collapse-icon-small:hover,
.collapse-icon-small:focus-visible {
  border-color: color-mix(in srgb, var(--outline-color) 38%, var(--line));
  background: color-mix(in srgb, var(--outline-color) 13%, transparent);
  color: var(--text-main, var(--text));
  opacity: 1;
  outline: none;
}

.collapse-icon-small:active {
  transform: translateY(1px);
}

.collapse-icon-small.collapsed {
  color: color-mix(in srgb, var(--outline-color) 76%, var(--text-secondary));
}

.collapse-spacer {
  pointer-events: none;
}

.outline-text {
  position: relative;
  z-index: 1;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  user-select: none;
}

.muted {
  min-width: 0;
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  box-sizing: border-box;
  margin: 0 0 0.12rem;
  padding: 0.42rem 0.55rem;
  border: 1px dashed color-mix(in srgb, var(--selected) 20%, var(--line));
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 24%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.muted-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 12%, transparent);
  opacity: 0.82;
}

.muted-text {
  min-width: 0;
  overflow-wrap: break-word;
}

@media (max-width: 420px) {
  .outline-list {
    padding: 0.45rem 0.42rem 0.6rem;
  }

  .outline-item {
    min-height: 36px;
    padding-right: 0.44rem;
    font-size: 0.79rem;
  }

  .collapse-icon-small,
  .collapse-spacer {
    width: 21px;
    height: 21px;
  }
}
</style>

