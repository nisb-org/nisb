import { reactive, computed } from 'vue'

const MODE_KEY = 'nisb_reading_mode'
const PREFS_KEY = 'nisb_reading_optimizer_v1'

const DEFAULT_PREFS = {
  brightness: 100,
  fontSize: 16,
  lineHeight: 1.6,
  padding: 0,
  warmth: 0,
  smooth: 0
}

const PRESETS = {
  eye: { brightness: 85, fontSize: 18, lineHeight: 1.8, padding: 20, warmth: 85, smooth: 80 },
  novel: { brightness: 95, fontSize: 17, lineHeight: 1.9, padding: 24, warmth: 90, smooth: 95 },
  academic: { brightness: 100, fontSize: 15, lineHeight: 1.5, padding: 12, warmth: 10, smooth: 40 },
  code: { brightness: 90, fontSize: 14, lineHeight: 1.4, padding: 8, warmth: 0, smooth: 40 }
}

const APPLIED_CSS_VARS = [
  '--nisb-read-text-opacity',
  '--nisb-reading-text-opacity',
  '--reading-text-opacity',
  '--reader-text-opacity',

  '--nisb-read-font-size',
  '--nisb-reading-font-size',
  '--reading-font-size',
  '--reader-font-size',

  '--nisb-read-line-height',
  '--nisb-reading-line-height',
  '--reading-line-height',
  '--reader-line-height',

  '--nisb-read-code-font-size',
  '--nisb-reading-code-font-size',
  '--reading-code-font-size',
  '--reader-code-font-size',

  '--nisb-read-citation-font-size',
  '--nisb-reading-citation-font-size',
  '--reading-citation-font-size',
  '--reader-citation-font-size',

  '--nisb-read-padding',
  '--nisb-reading-padding',
  '--reading-padding',
  '--reader-padding',

  '--nisb-read-warm-alpha',
  '--nisb-reading-warm-alpha',
  '--reading-warm-alpha',
  '--reader-warm-alpha',

  '--nisb-read-scroll-behavior',
  '--nisb-reading-scroll-behavior',
  '--reading-scroll-behavior',
  '--reader-scroll-behavior'
]

function clamp_num(v, min, max) {
  const n = Number(v)
  if (!Number.isFinite(n)) return min
  return Math.max(min, Math.min(max, n))
}

function normalize_prefs(p) {
  return {
    brightness: clamp_num(p?.brightness, 70, 110),
    fontSize: clamp_num(p?.fontSize, 13, 22),
    lineHeight: clamp_num(p?.lineHeight, 1.2, 2.2),
    padding: clamp_num(p?.padding, 0, 36),
    warmth: clamp_num(p?.warmth, 0, 100),
    smooth: clamp_num(p?.smooth, 0, 100)
  }
}

function brightness_to_opacity(br) {
  const b = clamp_num(br, 70, 110)
  if (b >= 100) return 1
  const t = (b - 70) / 30
  return 0.78 + t * (1 - 0.78)
}

function set_vars(el, names, value) {
  for (const name of names) {
    el.style.setProperty(name, value)
  }
}

export function useReadingOptimizer(layoutRef) {
  const state = reactive({
    mode: 'standard',
    prefs: normalize_prefs(DEFAULT_PREFS)
  })

  const enabled = computed(() => state.mode !== 'standard')

  let mounted = false
  let raf_id = 0

  function emit_state() {
    window.dispatchEvent(
      new CustomEvent('nisb-reading-state', {
        detail: { mode: state.mode, prefs: { ...state.prefs }, enabled: enabled.value }
      })
    )
  }

  function clear_applied_vars() {
    const el = layoutRef.value
    if (!el) return

    for (const name of APPLIED_CSS_VARS) {
      el.style.removeProperty(name)
    }
  }

  function apply_to_dom_now() {
    const el = layoutRef.value
    if (!el) return

    if (!enabled.value) {
      clear_applied_vars()
      emit_state()
      return
    }

    const p = normalize_prefs(state.prefs)

    const text_opacity = String(brightness_to_opacity(p.brightness))
    const font_size = `${p.fontSize}px`
    const line_height = `${p.lineHeight}`
    const code_font_size = `${Math.max(12, Math.round(p.fontSize * 0.92))}px`
    const citation_font_size = `${Math.max(11, Math.round(p.fontSize * 0.84))}px`
    const padding = `${p.padding}px`
    const warm_alpha = `${(p.warmth / 100) * 0.28}`
    const scroll_behavior = p.smooth >= 60 ? 'smooth' : 'auto'

    set_vars(
      el,
      [
        '--nisb-read-text-opacity',
        '--nisb-reading-text-opacity',
        '--reading-text-opacity',
        '--reader-text-opacity'
      ],
      text_opacity
    )

    set_vars(
      el,
      [
        '--nisb-read-font-size',
        '--nisb-reading-font-size',
        '--reading-font-size',
        '--reader-font-size'
      ],
      font_size
    )

    set_vars(
      el,
      [
        '--nisb-read-line-height',
        '--nisb-reading-line-height',
        '--reading-line-height',
        '--reader-line-height'
      ],
      line_height
    )

    set_vars(
      el,
      [
        '--nisb-read-code-font-size',
        '--nisb-reading-code-font-size',
        '--reading-code-font-size',
        '--reader-code-font-size'
      ],
      code_font_size
    )

    set_vars(
      el,
      [
        '--nisb-read-citation-font-size',
        '--nisb-reading-citation-font-size',
        '--reading-citation-font-size',
        '--reader-citation-font-size'
      ],
      citation_font_size
    )

    set_vars(
      el,
      [
        '--nisb-read-padding',
        '--nisb-reading-padding',
        '--reading-padding',
        '--reader-padding'
      ],
      padding
    )

    set_vars(
      el,
      [
        '--nisb-read-warm-alpha',
        '--nisb-reading-warm-alpha',
        '--reading-warm-alpha',
        '--reader-warm-alpha'
      ],
      warm_alpha
    )

    set_vars(
      el,
      [
        '--nisb-read-scroll-behavior',
        '--nisb-reading-scroll-behavior',
        '--reading-scroll-behavior',
        '--reader-scroll-behavior'
      ],
      scroll_behavior
    )

    state.prefs = p
    emit_state()
  }

  function schedule_apply() {
    if (raf_id) return
    raf_id = window.requestAnimationFrame(() => {
      raf_id = 0
      apply_to_dom_now()
    })
  }

  function setPrefs(nextPrefs) {
    if (state.mode === 'standard') state.mode = 'custom'
    state.prefs = normalize_prefs({ ...state.prefs, ...(nextPrefs || {}) })
    schedule_apply()
  }

  function applyPreset(presetId) {
    const id = String(presetId || 'standard')
    if (id === 'standard') {
      reset()
      return
    }
    if (!Object.prototype.hasOwnProperty.call(PRESETS, id)) return
    state.mode = id
    state.prefs = normalize_prefs(PRESETS[id])
    schedule_apply()
  }

  function save() {
    try {
      localStorage.setItem(MODE_KEY, state.mode)
      localStorage.setItem(PREFS_KEY, JSON.stringify(state.prefs))
    } catch {}
  }

  function reset() {
    state.mode = 'standard'
    state.prefs = normalize_prefs(DEFAULT_PREFS)

    try {
      localStorage.setItem(MODE_KEY, 'standard')
      localStorage.removeItem(PREFS_KEY)
    } catch {}

    schedule_apply()
  }

  function loadFromStorage() {
    let mode = 'standard'
    let prefs = normalize_prefs(DEFAULT_PREFS)

    try {
      const m = localStorage.getItem(MODE_KEY)
      if (m) mode = String(m)

      const raw = localStorage.getItem(PREFS_KEY)
      if (raw) {
        const obj = JSON.parse(raw)
        prefs = normalize_prefs(obj)
      }
    } catch {}

    state.mode = mode || 'standard'
    state.prefs = prefs
    schedule_apply()
  }

  function onApplyEvent(e) {
    const p = e?.detail?.prefs
    if (!p) return
    setPrefs(p)
  }

  function onPresetEvent(e) {
    const preset = e?.detail?.preset
    if (!preset) return
    applyPreset(preset)
  }

  function onSaveEvent() {
    save()
  }

  function onResetEvent() {
    reset()
  }

  function onRequestEvent() {
    emit_state()
  }

  function mount() {
    if (mounted) return
    mounted = true

    loadFromStorage()

    window.addEventListener('nisb-reading-apply', onApplyEvent)
    window.addEventListener('nisb-reading-preset', onPresetEvent)
    window.addEventListener('nisb-reading-save', onSaveEvent)
    window.addEventListener('nisb-reading-reset', onResetEvent)
    window.addEventListener('nisb-reading-request', onRequestEvent)
  }

  function unmount() {
    if (!mounted) return
    mounted = false

    window.removeEventListener('nisb-reading-apply', onApplyEvent)
    window.removeEventListener('nisb-reading-preset', onPresetEvent)
    window.removeEventListener('nisb-reading-save', onSaveEvent)
    window.removeEventListener('nisb-reading-reset', onResetEvent)
    window.removeEventListener('nisb-reading-request', onRequestEvent)

    if (raf_id) {
      try {
        window.cancelAnimationFrame(raf_id)
      } catch {}
      raf_id = 0
    }
  }

  return { state, enabled, mount, unmount, setPrefs, applyPreset, save, reset }
}
