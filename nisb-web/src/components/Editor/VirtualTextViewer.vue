<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/VirtualTextViewer.vue -->
<template>
  <div class="vtv-root">
    <div class="vtv-toolbar" v-if="showToolbar">
      <button
        class="vtv-btn"
        type="button"
        @click="toggle_wrap"
        :title="wrap ? t('note.reader.virtualText.wrapOnTitle') : t('note.reader.virtualText.wrapOffTitle')"
      >
        {{ wrap ? t('note.reader.virtualText.wrapOn') : t('note.reader.virtualText.wrapOff') }}
      </button>

      <div class="vtv-spacer" />

      <button
        v-if="showScrollHint"
        class="vtv-chip"
        type="button"
        @click="apply_now"
        :title="t('note.reader.virtualText.scrollHintTitle')"
      >
        {{ t('note.reader.virtualText.scrollHint') }}
      </button>

      <span
        v-if="indexing"
        class="vtv-chip vtv-chip-muted"
        :title="t('note.reader.virtualText.indexingTitle')"
      >
        {{ t('note.reader.virtualText.indexing') }}
      </span>
    </div>

    <div ref="wrapRef" class="vtv-wrap" :class="{ wrap: wrap }" @scroll="on_scroll" @wheel.passive="on_wheel">
      <div class="vtv-spacer-div" :style="{ height: totalHeightPx }">
        <pre class="vtv-pre" :style="{ transform: `translateY(${topOffsetPx}px)` }">{{ visibleText }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  text: { type: String, default: '' },

  lineHeight: { type: Number, default: 20 },
  overscan: { type: Number, default: 120 },

  showToolbar: { type: Boolean, default: true },
  initialWrap: { type: Boolean, default: true },

  showHint: { type: Boolean, default: true },
  dragDebounceMs: { type: Number, default: 140 }
})

const { t } = useI18n()

const wrapRef = ref(null)

const wrap = ref(!!props.initialWrap)

const viewStart = ref(0)
const viewEnd = ref(0)

const lastWheelTs = ref(0)
let rafId = 0
let debounceTimer = null
let hintTimer = null

const showScrollHint = ref(false)

/**
 * ✅ 不再 split('\n')：
 * - 保存原始 text
 * - 建“行号 -> 字符位置”稀疏检查点（每 200 行一个）
 * - 渲染窗口时，只在小范围扫描取子串
 */
const raw_text = ref('')
const total_lines = ref(1)

const indexing = ref(false)
let __index_seq = 0
let __index_timer = null

const CHECKPOINT_EVERY = 200
const TIME_SLICE_MS = 10

// checkpoints: [{ line: 1-based line_no, pos: char_index_of_line_start }]
const checkpoints = ref([])

function _cancel_indexing() {
  if (__index_timer) clearTimeout(__index_timer)
  __index_timer = null
  indexing.value = false
}

function _count_lines_fast(s) {
  const t = String(s || '')
  if (!t) return 1
  let n = 1
  for (let i = 0; i < t.length; i++) {
    if (t.charCodeAt(i) === 10) n += 1
  }
  return n
}

function _build_checkpoints_async(text, seq) {
  _cancel_indexing()
  indexing.value = true
  checkpoints.value = [{ line: 1, pos: 0 }]

  const s = String(text || '')
  const len = s.length

  let i = 0
  let line_no = 1
  let next_checkpoint_line = CHECKPOINT_EVERY + 1 // line 201,401,...

  const step = () => {
    if (seq !== __index_seq) return
    const t0 = performance.now()

    while (i < len) {
      if (s.charCodeAt(i) === 10) {
        line_no += 1
        const line_start_pos = i + 1
        if (line_no === next_checkpoint_line) {
          checkpoints.value.push({ line: line_no, pos: line_start_pos })
          next_checkpoint_line += CHECKPOINT_EVERY
        }
      }
      i += 1

      if (performance.now() - t0 > TIME_SLICE_MS) {
        __index_timer = setTimeout(step, 0)
        return
      }
    }

    total_lines.value = Math.max(1, line_no)
    indexing.value = false
    __index_timer = null
  }

  __index_timer = setTimeout(step, 0)
}

function _find_checkpoint_for_line(line) {
  const target = Math.max(1, Number(line || 1))
  const arr = checkpoints.value
  if (!arr || arr.length === 0) return { line: 1, pos: 0 }

  // binary search: last checkpoint with cp.line <= target
  let lo = 0
  let hi = arr.length - 1
  let best = arr[0]

  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const cp = arr[mid]
    if (cp.line <= target) {
      best = cp
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return best
}

function _pos_for_line_start(line) {
  const s = raw_text.value
  const len = s.length
  const target = Math.max(1, Number(line || 1))

  if (target === 1) return 0
  if (!s) return 0

  const cp = _find_checkpoint_for_line(target)
  let cur_line = cp.line
  let pos = cp.pos

  // scan forward to target line
  while (pos < len && cur_line < target) {
    const nl = s.indexOf('\n', pos)
    if (nl === -1) return len
    cur_line += 1
    pos = nl + 1
  }
  return Math.max(0, Math.min(len, pos))
}

function _slice_lines(start_line, end_line) {
  const s = raw_text.value
  if (!s) return ''

  const sl = Math.max(1, Number(start_line || 1))
  const el = Math.max(sl, Number(end_line || sl))

  const start_pos = _pos_for_line_start(sl)
  if (start_pos >= s.length) return ''

  // 为了避免再做一次“全局索引”，这里从 start_pos 向前扫描 end_line-start_line 个换行即可
  let pos = start_pos
  let need = el - sl
  while (pos < s.length && need > 0) {
    const nl = s.indexOf('\n', pos)
    if (nl === -1) {
      pos = s.length
      break
    }
    pos = nl + 1
    need -= 1
  }
  return s.slice(start_pos, pos)
}

watch(
  () => props.text,
  (t) => {
    const s = String(t || '')
    raw_text.value = s
    total_lines.value = _count_lines_fast(s)

    viewStart.value = 0
    viewEnd.value = 0
    showScrollHint.value = false

    // 超大文本：默认关闭换行，避免 pre-wrap 对超长内容的排版压力
    if (s.length > 2 * 1024 * 1024) wrap.value = false
    else wrap.value = !!props.initialWrap

    __index_seq += 1
    const seq = __index_seq
    _build_checkpoints_async(s, seq)

    queue_update_now(true)
  },
  { immediate: true }
)

watch(
  () => props.initialWrap,
  (v) => {
    wrap.value = !!v
  }
)

const totalHeightPx = computed(() => `${Math.max(1, total_lines.value) * props.lineHeight}px`)
const topOffsetPx = computed(() => viewStart.value * props.lineHeight)

const visibleText = computed(() => {
  const s = Math.max(0, viewStart.value)
  const e = Math.max(s, viewEnd.value)
  // line_no is 1-based
  return _slice_lines(s + 1, e + 1)
})

function compute_range() {
  const el = wrapRef.value
  if (!el) return { s: 0, e: 0 }

  const scrollTop = el.scrollTop
  const h = el.clientHeight

  const first = Math.floor(scrollTop / props.lineHeight)
  const count = Math.ceil(h / props.lineHeight)

  const s = Math.max(0, first - props.overscan)
  const e = Math.min(total_lines.value, first + count + props.overscan)
  return { s, e }
}

function apply_range() {
  const { s, e } = compute_range()
  viewStart.value = s
  viewEnd.value = e
}

function queue_update_now(force = false) {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    rafId = 0
    apply_range()
    if (force) showScrollHint.value = false
  })
}

function on_wheel() {
  lastWheelTs.value = Date.now()
  showScrollHint.value = false
  queue_update_now()
}

function on_scroll() {
  const now = Date.now()
  const isWheel = now - lastWheelTs.value < 80

  if (isWheel) {
    queue_update_now()
    return
  }

  if (!props.showHint) {
    showScrollHint.value = false
  } else {
    showScrollHint.value = true
    if (hintTimer) clearTimeout(hintTimer)
    hintTimer = setTimeout(() => {
      showScrollHint.value = false
    }, Math.max(200, props.dragDebounceMs + 80))
  }

  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    apply_range()
  }, Math.max(60, props.dragDebounceMs))
}

function apply_now() {
  showScrollHint.value = false
  apply_range()
}

function toggle_wrap() {
  wrap.value = !wrap.value
}

onMounted(() => {
  queue_update_now(true)
})

onUnmounted(() => {
  __index_seq += 1
  _cancel_indexing()

  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = null
  if (hintTimer) clearTimeout(hintTimer)
  hintTimer = null
})
</script>

<style scoped>
.vtv-root {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 90%, var(--sidebar-bg))
    );
  color: var(--text-main);
}

.vtv-toolbar {
  position: relative;
  flex: 0 0 auto;
  min-height: 42px;
  box-sizing: border-box;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.vtv-toolbar::-webkit-scrollbar {
  display: none;
}

.vtv-toolbar::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 16%, var(--line)),
      transparent
    );
  opacity: 0.58;
}

.vtv-spacer {
  flex: 1 1 auto;
  min-width: 0.5rem;
}

.vtv-btn {
  height: 28px;
  min-width: max-content;
  box-sizing: border-box;
  padding: 0 0.65rem;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 740;
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

.vtv-btn:hover,
.vtv-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.vtv-btn:active {
  transform: translateY(1px);
}

.vtv-chip {
  min-height: 26px;
  min-width: max-content;
  box-sizing: border-box;
  padding: 0.34rem 0.62rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--selected) 26%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 68%, transparent)
    );
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  user-select: none;
  cursor: pointer;
  white-space: nowrap;
}

.vtv-chip-muted {
  opacity: 0.78;
  cursor: default;
  color: var(--text-secondary);
  border-color: color-mix(in srgb, var(--line) 86%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 64%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
}

.vtv-wrap {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 0;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 20px;
  scrollbar-gutter: stable;
}

.vtv-spacer-div {
  position: relative;
  width: 100%;
}

.vtv-pre {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  box-sizing: border-box;
  margin: 0;
  padding: 1.35rem 1.6rem 2.25rem;
  white-space: pre;
  tab-size: 2;
  overflow-wrap: normal;
  color: var(--text-main);
}

.vtv-wrap.wrap .vtv-pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 720px) {
  .vtv-toolbar {
    padding-inline: 8px;
  }

  .vtv-pre {
    padding: 1rem 1rem 2rem;
  }
}
</style>

