<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/Library/LibraryContinuousReader.vue -->
<template>
  <div class="doc-panel-continuous">
    <div v-if="continuousReadingEnabled" class="continuous-view" ref="continuousContainer">
      <div v-if="showLoadingTip" class="empty-tip">{{ t('library.center.reader.loadingContinuous') }}</div>
      <!-- loading tip removed to avoid flicker -->

      <div v-else>
        <div
          v-for="span in continuousSpans"
          :key="span.span_index"
          class="continuous-span"
          :id="`nisb-span-${span.span_index}`"
          :data-span-index="span.span_index"
        >
          <div class="continuous-span-header">
            <span
              class="span-meta"
              :title="t('library.center.reader.spanHeaderTitle', { index: span.span_index, start: span.span_start, end: span.span_end })"
            >
              {{ t('library.center.reader.spanLabel', { index: span.span_index }) }}
            </span>

            <div class="span-actions">
              <span v-if="showTranslation && span.from_cache && !span.translation_refused" class="cache-badge">
                {{ t('library.center.reader.cache') }}
              </span>

              <span
                v-if="showTranslation && span.translation_refused"
                class="refusal-badge"
                :title="t('library.center.reader.translationRefusedTitle')"
              >
                {{ t('library.center.reader.translationRefused') }}
              </span>

              <select
                v-if="showTranslation"
                v-model="translateBackend"
                class="continuous-lang"
                style="width: auto;"
                :title="t('library.center.reader.translateBackendTitle')"
              >
                <option value="mini">4o-mini</option>
                <option value="haiku">haiku-3.5</option>
                <option value="haiku-4-5">haiku-4.5</option>
              </select>

              <button
                v-if="showTranslation"
                class="doc-panel-btn span-translate-btn"
                @click="handleTranslateClick(span)"
                :disabled="span.translating"
              >
                {{ getTranslateButtonText(span) }}
              </button>
            </div>
          </div>

          <div v-if="showTranslation && compareMode" class="compare-grid">
            <div class="compare-col">
              <div class="compare-label">{{ t('library.center.reader.originalText') }}</div>
              <div class="preview-content continuous-text" v-html="renderMarkdown(span.text)"></div>
            </div>
            <div class="compare-col">
              <div class="compare-label">{{ t('library.center.reader.translatedText') }}</div>
              <div class="preview-content continuous-text" v-html="renderMarkdown(_renderTranslationText(span))"></div>
            </div>
          </div>

          <div
            v-else
            class="preview-content continuous-text"
            v-html="renderMarkdown(showTranslation ? _renderTranslationText(span) : span.text)"
          ></div>
        </div>
      </div>
    </div>

    <SpanArtifactsModal
      :open="spanToolsOpen"
      :libraryId="props.libraryId"
      :docId="props.docId"
      :spanIndex="spanToolsSpanIndex"
      :reader="spanToolsReader"
      @close="closeSpanTools"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, onDeactivated, onActivated, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useMCP } from '../../../composables/useMCP'
import { useImageLoader } from '../../../composables/useImageLoader'
import { use_reader_translation } from '../../../composables/library_reader/use_reader_translation'
import SpanArtifactsModal from './SpanArtifactsModal.vue'

const props = defineProps({
  libraryId: { type: String, required: true },
  docId: { type: String, required: true },
  scrollTarget: { type: Object, default: null }
})

const { t, locale } = useI18n()
const { callTool } = useMCP()
const { enhanceMarkdownDom } = useImageLoader()

const READER_TARGET_LANG_PREF_KEY = 'nisb_library_reader_target_lang_v1'

const SUPPORTED_READER_LANGS = new Set([
  'zh-CN',
  'en',
  'ja',
  'ko',
  'fr',
  'de',
  'es',
  'pt-BR',
  'it',
  'ru',
  'ar',
  'hi',
  'vi',
  'th',
  'id'
])

const pretranslateAhead = ref(2)
const continuousReadingEnabled = ref(false)
const showTranslation = ref(false)
const compareMode = ref(false)
const targetLanguage = ref(_initialTargetLanguage())
const libraryAutoPretranslate = ref(false)
const pretranslatePaused = ref(false)
const translateBackend = ref('mini')

const continuousSpans = ref([])
const continuousLoading = ref(false)

const _persist_suspended = ref(true)

let _broadcast_timer = null
function _scheduleBroadcastReaderState() {
  if (_broadcast_timer) return
  _broadcast_timer = setTimeout(() => {
    _broadcast_timer = null
    _broadcastReaderStateNow()
  }, 50)
}

let _prefs_write_timer = null
function _save_reader_prefs_debounced() {
  try {
    if (_prefs_write_timer) clearTimeout(_prefs_write_timer)
    _prefs_write_timer = setTimeout(() => {
      _prefs_write_timer = null
      _save_reader_prefs()
    }, 250)
  } catch {}
}

const showLoadingTip = ref(false)
let _loading_tip_timer = null

watch(
  () => continuousLoading.value,
  (v) => {
    if (_loading_tip_timer) {
      clearTimeout(_loading_tip_timer)
      _loading_tip_timer = null
    }
    if (v) {
      _loading_tip_timer = setTimeout(() => {
        showLoadingTip.value = true
      }, 300)
    } else {
      showLoadingTip.value = false
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  if (_loading_tip_timer) {
    clearTimeout(_loading_tip_timer)
    _loading_tip_timer = null
  }
})

const continuousContainer = ref(null)
let scrollListenerTarget = null

let _autoEnablingContinuous = false
let _applyingTimelinePayload = false

const spanToolsOpen = ref(false)
const spanToolsSpanIndex = ref(0)
const spanToolsReader = ref(null)

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function closeSpanTools() {
  spanToolsOpen.value = false
}

function _normalizeLang(val) {
  const s = String(val || '').trim()
  const lower = s.toLowerCase()

  if (!lower) return 'zh-CN'
  if (lower === 'zh' || lower === 'zh-cn' || lower === 'zh-hans' || lower.startsWith('zh_cn')) return 'zh-CN'
  if (lower === 'pt-br' || lower === 'pt_br') return 'pt-BR'

  for (const lang of SUPPORTED_READER_LANGS) {
    if (lang.toLowerCase() === lower) return lang
  }

  const base = lower.split(/[-_]/)[0]
  for (const lang of SUPPORTED_READER_LANGS) {
    if (lang.toLowerCase() === base) return lang
  }

  return 'zh-CN'
}

function _loadTargetLanguagePreference() {
  try {
    const raw = localStorage.getItem(READER_TARGET_LANG_PREF_KEY)
    return raw ? _normalizeLang(raw) : ''
  } catch {
    return ''
  }
}

function _saveTargetLanguagePreference(lang) {
  const normalized = _normalizeLang(lang)
  try {
    localStorage.setItem(READER_TARGET_LANG_PREF_KEY, normalized)
  } catch {}
}

function _initialTargetLanguage() {
  const saved = _loadTargetLanguagePreference()
  if (saved) return saved

  try {
    return _normalizeLang(locale.value || navigator.language || 'zh-CN')
  } catch {
    return 'zh-CN'
  }
}

function _extractSpanIndex(payload) {
  if (!payload || typeof payload !== 'object') return null

  const extra = payload?.extra && typeof payload.extra === 'object' ? payload.extra : {}
  const spanObj =
    payload?.span && typeof payload.span === 'object'
      ? payload.span
      : extra?.span && typeof extra.span === 'object'
        ? extra.span
        : null

  const raw =
    (payload.spanIndex ?? payload.span_index ?? null) ??
    (spanObj ? (spanObj.span_index ?? spanObj.spanIndex ?? spanObj.index ?? null) : null) ??
    null

  const n = raw === null || raw === undefined ? null : Number(raw)
  return Number.isFinite(n) ? n : null
}

function _buildReaderSnapshot() {
  return {
    continuous: !!continuousReadingEnabled.value,
    showTranslation: !!showTranslation.value,
    smartPretranslate: !!libraryAutoPretranslate.value,
    pretranslateSpans: Number(pretranslateAhead.value || 2),
    lang: targetLanguage.value,
    compareMode: !!compareMode.value
  }
}

function _syncGlobalReaderState() {
  try {
    window.nisbReaderState = _buildReaderSnapshot()
  } catch {}
}

let queue = ref([])
let runningMap = ref(new Map())

function _broadcastReaderStateNow() {
  try {
    const spans = Array.isArray(continuousSpans.value) ? continuousSpans.value : []
    const total = spans.length
    const translated = spans.filter((s) => !!String(s?.translated_text || '').trim()).length
    const refused = spans.filter((s) => s?.translation_refused === true).length

    const payload = {
      libraryId: props.libraryId,
      docId: props.docId,
      reader: _buildReaderSnapshot(),
      progress: {
        total,
        translated,
        refused,
        queue: Number(queue.value.length || 0),
        running: Number(runningMap.value.size || 0),
        paused: !!pretranslatePaused.value
      }
    }
    window.dispatchEvent(new CustomEvent('nisb-reader-state-changed', { detail: payload }))
  } catch {}
}

function _broadcastReaderState() {
  _scheduleBroadcastReaderState()
}

function _syncAllStates(persist = true) {
  _syncGlobalReaderState()
  _broadcastReaderState()
  if (persist && !_persist_suspended.value) _save_reader_prefs_debounced()
}

let __enhance_timer = null
function _schedule_enhance_markdown_dom(delay = 0) {
  try {
    if (__enhance_timer) clearTimeout(__enhance_timer)
  } catch {}
  __enhance_timer = setTimeout(async () => {
    __enhance_timer = null
    try {
      if (typeof enhanceMarkdownDom !== 'function') return
      await nextTick()
      const rootEl = continuousContainer.value
      if (!rootEl) return

      enhanceMarkdownDom({
        rootEl,
        onOpenLightbox: (payload) => {
          try {
            window.dispatchEvent(new CustomEvent('nisb-open-lightbox', { detail: payload }))
          } catch {}
        }
      })
    } catch {}
  }, Math.max(0, Number(delay || 0)))
}

const loadController = ref(null)
const pendingOpenPayload = ref(null)

function cancelLoad(reason = 'unknown') {
  if (loadController.value) {
    try {
      loadController.value.abort(reason)
    } catch {}
    loadController.value = null
  }
}

const _reader_prefs_key = computed(() => `nisb_library_reader_prefs_v1:${String(props.libraryId || 'global')}`)

function _snapshot_reader_prefs() {
  return {
    continuous: !!continuousReadingEnabled.value,
    show_translation: !!showTranslation.value,
    smart_pretranslate: !!libraryAutoPretranslate.value,
    compare_mode: !!compareMode.value,
    pretranslate_spans: Number(pretranslateAhead.value || 2),
    lang: String(targetLanguage.value || 'zh-CN'),
    updated_at: new Date().toISOString()
  }
}

function _save_reader_prefs() {
  try {
    localStorage.setItem(_reader_prefs_key.value, JSON.stringify(_snapshot_reader_prefs()))
    _saveTargetLanguagePreference(targetLanguage.value)
  } catch {}
}

function _load_reader_prefs() {
  try {
    const raw = localStorage.getItem(_reader_prefs_key.value)
    if (!raw) return null
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : null
  } catch {
    return null
  }
}

function _isAbortLike(err, controller) {
  const msg = String(err?.message || err || '').toLowerCase()
  const aborted = !!(controller?.signal && controller.signal.aborted)
  const byName = String(err?.name || '').toLowerCase() === 'aborterror'
  const byMsg = msg.includes('abort') || msg.includes('aborted') || msg.includes('reload')
  return aborted || byName || byMsg
}

const _translation = use_reader_translation({
  call_tool: callTool,
  library_id_ref: computed(() => props.libraryId),
  doc_id_ref: computed(() => props.docId),
  target_language_ref: targetLanguage,
  translate_backend_ref: translateBackend,
  continuous_enabled_ref: continuousReadingEnabled,
  smart_pretranslate_ref: libraryAutoPretranslate,
  pretranslate_ahead_ref: pretranslateAhead,
  pretranslate_paused_ref: pretranslatePaused,
  continuous_spans_ref: continuousSpans,
  build_reader_snapshot: _buildReaderSnapshot,
  schedule_enhance_markdown_dom: _schedule_enhance_markdown_dom,
  sync_all_states: _syncAllStates,
  is_abort_like: _isAbortLike
})

queue = _translation.queue
runningMap = _translation.running_map

function _apply_translate_cache_to_spans(spans, lang = null) {
  return _translation.apply_translate_cache_to_spans(spans, lang)
}

function cancelPretranslate(reason = 'unknown') {
  return _translation.cancel_pretranslate(reason)
}

function resumePretranslate() {
  return _translation.resume_pretranslate()
}

function kickPretranslate() {
  return _translation.kick_pretranslate()
}

function ensureAheadTranslated(baseIndex) {
  return _translation.ensure_ahead_translated(baseIndex)
}

async function handleTranslateClick(span) {
  return _translation.handle_translate_click(span)
}

function _cache_clear_doc(lang = null) {
  return _translation.cache_clear_doc(lang)
}

function cancelAllWork(reason = 'unknown') {
  cancelLoad(reason)
  cancelPretranslate(reason)
}

const hasPretranslateWork = computed(() => queue.value.length > 0 || runningMap.value.size > 0)

async function _apply_reader_prefs_for_new_doc() {
  const p = _load_reader_prefs()
  if (!p) return

  try {
    const last = window.__nisb_last_library_doc_open
    if (last && last.libraryId === props.libraryId && last.docId === props.docId) return
  } catch {}

  if (typeof p.lang === 'string' && p.lang) targetLanguage.value = _normalizeLang(p.lang)
  if (Number.isFinite(Number(p.pretranslate_spans))) pretranslateAhead.value = Number(p.pretranslate_spans)

  if (typeof p.show_translation === 'boolean') showTranslation.value = !!p.show_translation
  if (typeof p.smart_pretranslate === 'boolean') libraryAutoPretranslate.value = !!p.smart_pretranslate
  if (typeof p.compare_mode === 'boolean') compareMode.value = !!p.compare_mode

  const wantContinuous = !!(p.continuous || p.show_translation || p.smart_pretranslate || p.compare_mode)
  continuousReadingEnabled.value = wantContinuous

  if (wantContinuous) {
    await loadContinuousReading()
    await nextTick()
    _schedule_enhance_markdown_dom(0)
  }

  _syncAllStates(false)
}

const __dompurify_cfg = {
  USE_PROFILES: { html: true },
  ALLOWED_URI_REGEXP:
    /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|matrix|nisb):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
}

function renderMarkdown(text) {
  if (!text) return ''
  try {
    const html = marked.parse(String(text || ''), {
      breaks: true,
      gfm: true,
      headerIds: true,
      mangle: false
    })
    return DOMPurify.sanitize(html, __dompurify_cfg)
  } catch (e) {
    console.error('[连续阅读] Markdown 渲染错误:', e)
    return `<p>${t('library.center.reader.markdownRenderError')}</p>`
  }
}

function getTranslateButtonText(span) {
  if (span?.translating) return t('library.center.reader.translating')
  if (span?.translated_text) return t('library.center.reader.retranslate')
  if (span?.translation_refused) return t('library.center.reader.forceRetranslate')
  return t('library.center.reader.translateThisSpan')
}

function resetState(opts = {}) {
  const persist = opts?.persist === true

  cancelAllWork('reset')
  continuousReadingEnabled.value = false
  showTranslation.value = false
  compareMode.value = false
  targetLanguage.value = _initialTargetLanguage()
  pretranslateAhead.value = 2
  libraryAutoPretranslate.value = false
  pretranslatePaused.value = false
  translateBackend.value = 'mini'
  continuousSpans.value = []
  continuousLoading.value = false
  _autoEnablingContinuous = false

  spanToolsOpen.value = false
  spanToolsSpanIndex.value = 0
  spanToolsReader.value = null

  _syncAllStates(persist)
}

async function loadContinuousReading(startSpan = 0) {
  if (!props.docId) return

  const start_span = Number.isFinite(Number(startSpan)) ? Math.max(0, Math.trunc(Number(startSpan))) : 0

  cancelLoad('reload')
  continuousLoading.value = true

  cancelPretranslate('reload')
  pretranslatePaused.value = false

  const reader = _buildReaderSnapshot()
  const controller = new AbortController()
  loadController.value = controller

  try {
    const res = await callTool(
      'nisb_library_continuous_read',
      {
        library_id: props.libraryId,
        doc_id: props.docId,
        start_span: start_span,
        max_chars: 8000,
        reader,
        continuous: true,
        show_translation: !!showTranslation.value,
        lang: targetLanguage.value,
        smart_pretranslate: !!libraryAutoPretranslate.value,
        pretranslate_spans: Number(pretranslateAhead.value || 2)
      },
      { signal: controller.signal, trackLoading: false }
    )

    if (res && res.status === 'success' && Array.isArray(res.spans)) {
      continuousSpans.value = res.spans.map((s) => ({
        ...s,
        translated_text: null,
        from_cache: false,
        translating: false,
        translation_refused: false,
        translation_refusal_text: ''
      }))

      try {
        _apply_translate_cache_to_spans(continuousSpans.value, targetLanguage.value)
      } catch {}
    } else {
      continuousSpans.value = []
    }

    await nextTick()
    _schedule_enhance_markdown_dom(0)
  } catch (e) {
    if (_isAbortLike(e, controller)) return
    console.error('[连续阅读] 加载失败:', e)
    alert(t('library.center.reader.continuousLoadFailed', { message: e?.message || e }))
    continuousSpans.value = []
  } finally {
    if (loadController.value === controller) loadController.value = null
    continuousLoading.value = false
    _syncAllStates()
  }
}

function onToggleContinuous() {
  if (continuousReadingEnabled.value) {
    loadContinuousReading()
  } else {
    cancelAllWork('toggle_off')
    continuousSpans.value = []
    showTranslation.value = false
    compareMode.value = false
    libraryAutoPretranslate.value = false
    pretranslatePaused.value = false
    pretranslateAhead.value = 2
    translateBackend.value = 'mini'
  }
  _syncAllStates()
}

function onToggleTranslation() {
  if (!continuousReadingEnabled.value) {
    showTranslation.value = false
    compareMode.value = false
    _syncAllStates()
    return
  }
  if (!showTranslation.value) compareMode.value = false
  _syncAllStates()
}

function _findCurrentVisibleSpanIndex() {
  const container = continuousContainer.value
  if (!container) return null

  const els = Array.from(container.querySelectorAll('.continuous-span'))
  if (!els.length) return null

  const anchorY = 140

  for (const el of els) {
    const rect = el.getBoundingClientRect()
    if (rect.top <= anchorY && rect.bottom >= anchorY) {
      const sid = Number(el.dataset.spanIndex)
      if (Number.isFinite(sid)) return sid
    }
  }

  let best = null
  let bestDist = Infinity
  for (const el of els) {
    const rect = el.getBoundingClientRect()
    const mid = (rect.top + rect.bottom) / 2
    const dist = Math.abs(mid - anchorY)
    if (dist < bestDist) {
      bestDist = dist
      best = el
    }
  }

  if (!best) return null
  const sid = Number(best.dataset.spanIndex)
  return Number.isFinite(sid) ? sid : null
}

async function openSpanToolsFromBottomBar() {
  if (!continuousReadingEnabled.value) {
    toast(t('library.center.reader.enableContinuousBeforeSpanTools'), 'info')
    return
  }

  if (!continuousSpans.value?.length && !continuousLoading.value) {
    await loadContinuousReading()
    await nextTick()
  }

  const sid =
    _findCurrentVisibleSpanIndex() ??
    (Number.isFinite(Number(continuousSpans.value?.[0]?.span_index)) ? Number(continuousSpans.value[0].span_index) : null)

  if (!Number.isFinite(Number(sid))) {
    toast(t('library.center.reader.currentSpanNotFound'), 'error')
    return
  }

  spanToolsSpanIndex.value = Number(sid)
  spanToolsReader.value = _buildReaderSnapshot()
  spanToolsOpen.value = true
}

function onSpanArtifactsOpen(evt) {
  if (!_isDockedRightNow()) return

  const d = evt?.detail || null
  if (!d) return
  if (d.libraryId && d.libraryId !== props.libraryId) return
  if (d.docId && d.docId !== props.docId) return

  openSpanToolsFromBottomBar()
}

function _renderTranslationText(span) {
  if (!span) return ''
  if (span.translation_refused) return t('library.center.reader.translationRefusedPlaceholder')
  return span.translated_text || t('library.center.reader.translationEmptyPlaceholder')
}

const _is_active = ref(true)
let __scroll_raf = null
let __scroll_pending = false

function _cancel_scroll_raf() {
  try {
    if (__scroll_raf) cancelAnimationFrame(__scroll_raf)
  } catch {}
  __scroll_raf = null
  __scroll_pending = false
}

function _runContinuousScrollCheck() {
  if (!_is_active.value) return
  if (!continuousReadingEnabled.value || !libraryAutoPretranslate.value) return
  if (pretranslatePaused.value) return

  const container = continuousContainer.value
  if (!container) return

  const spanEls = container.querySelectorAll('.continuous-span')
  if (!spanEls.length) return

  const containerRect = container.getBoundingClientRect()
  let baseIndex = -1

  spanEls.forEach((el, idx) => {
    const rect = el.getBoundingClientRect()
    if (rect.bottom >= containerRect.top && rect.top <= containerRect.bottom) {
      const span = continuousSpans.value[idx]
      if (span && (span.translated_text || span.translation_refused)) {
        baseIndex = Math.max(baseIndex, idx)
      }
    }
  })

  if (baseIndex >= 0) ensureAheadTranslated(baseIndex)
}

function handleContinuousScroll() {
  if (__scroll_pending) return
  __scroll_pending = true
  __scroll_raf = requestAnimationFrame(() => {
    __scroll_pending = false
    __scroll_raf = null
    _runContinuousScrollCheck()
  })
}

function attachScrollListener() {
  detachScrollListener()
  const target = props.scrollTarget || window
  scrollListenerTarget = target
  try {
    target.addEventListener('scroll', handleContinuousScroll, { passive: true })
  } catch {
    target.addEventListener('scroll', handleContinuousScroll)
  }
}

function detachScrollListener() {
  _cancel_scroll_raf()
  if (scrollListenerTarget) {
    try {
      scrollListenerTarget.removeEventListener('scroll', handleContinuousScroll, { passive: true })
    } catch {
      scrollListenerTarget.removeEventListener('scroll', handleContinuousScroll)
    }
    scrollListenerTarget = null
  }
}

const __last_apply_key = ref('')
const __last_apply_ts = ref(0)

function __make_apply_key(payload) {
  if (!payload || typeof payload !== 'object') return ''
  const lib = String(payload.libraryId || '').trim()
  const doc = String(payload.docId || '').trim()
  const span = _extractSpanIndex(payload)
  const spanKey = Number.isFinite(Number(span)) ? String(Number(span)) : ''
  if (!lib || !doc) return ''
  return `${lib}::${doc}::${spanKey}`
}

function __span_el(spanIndex) {
  const n = Number(spanIndex)
  if (!Number.isFinite(n)) return null

  const local = continuousContainer.value?.querySelector?.(`[data-span-index="${Number(n)}"]`)
  if (local) return local

  return document.getElementById(`nisb-span-${Number(n)}`)
}

async function __scroll_to_span(spanIndex, block = 'start') {
  const n = Number(spanIndex)
  if (!Number.isFinite(n)) return false

  const tryScroll = () => {
    const el = __span_el(n)
    if (el?.scrollIntoView) {
      el.scrollIntoView({ behavior: 'smooth', block })
    }
    return !!el
  }

  try {
    await nextTick()
    if (tryScroll()) return true
    requestAnimationFrame(() => tryScroll())
    setTimeout(() => tryScroll(), 180)
  } catch {}
  return false
}

let __citation_highlight_timer = null
let __citation_highlight_retry_timer = null

function __string_value(value) {
  return String(value ?? '').trim()
}

function __highlight_text_from_payload(payload) {
  return __string_value(
    payload?.highlightText ||
      payload?.highlight_text ||
      payload?.highlightQuote ||
      payload?.highlight_quote ||
      payload?.quote ||
      payload?.excerpt ||
      payload?.text ||
      payload?.snippet ||
      ''
  )
}

function __normalized_char(ch) {
  if (!ch) return ''
  if (/\s/.test(ch)) return ' '
  if (/[\u200B-\u200D\uFEFF]/.test(ch)) return ''
  if (/["'`“”‘’.,;:!?()[\]{}<>，。；：！？（）【】《》、—–\-_/\\|·•]/.test(ch)) return ''
  return ch.toLowerCase()
}

function __build_normalized_index(root) {
  const flat = []
  const map = []
  let lastWasSpace = false

  const walker = document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const parent = node?.parentElement
        if (!parent) return NodeFilter.FILTER_REJECT
        if (parent.closest('mark[data-nisb-citation-hit="1"]')) return NodeFilter.FILTER_REJECT
        if (parent.closest('script,style,select,button')) return NodeFilter.FILTER_REJECT
        if (!String(node.textContent || '').trim()) return NodeFilter.FILTER_REJECT
        return NodeFilter.FILTER_ACCEPT
      }
    }
  )

  let node = walker.nextNode()
  while (node) {
    const text = String(node.textContent || '')
    for (let i = 0; i < text.length; i += 1) {
      const normalized = __normalized_char(text[i])
      if (!normalized) continue

      if (normalized === ' ') {
        if (lastWasSpace) continue
        lastWasSpace = true
      } else {
        lastWasSpace = false
      }

      flat.push(normalized)
      map.push({ node, offset: i })
    }
    node = walker.nextNode()
  }

  return { text: flat.join(''), map }
}

function __normalize_search_text(text) {
  const out = []
  let lastWasSpace = false
  const raw = String(text || '')

  for (let i = 0; i < raw.length; i += 1) {
    const normalized = __normalized_char(raw[i])
    if (!normalized) continue

    if (normalized === ' ') {
      if (lastWasSpace) continue
      lastWasSpace = true
    } else {
      lastWasSpace = false
    }

    out.push(normalized)
  }

  return out.join('').trim()
}

function __quote_candidates(quote) {
  const normalized = __normalize_search_text(quote)
  if (!normalized) return []

  const candidates = []
  const add = (value) => {
    const text = String(value || '').trim()
    if (text.length >= 12 && !candidates.includes(text)) candidates.push(text)
  }

  add(normalized)

  if (normalized.length > 260) {
    add(normalized.slice(0, 240))
    add(normalized.slice(Math.max(0, Math.floor(normalized.length / 2) - 120), Math.floor(normalized.length / 2) + 120))
    add(normalized.slice(-240))
  }

  if (normalized.length > 140) {
    add(normalized.slice(0, 140))
    add(normalized.slice(-140))
  }

  if (normalized.includes(' ')) {
    const words = normalized.split(/\s+/).filter(Boolean)
    for (let size = Math.min(words.length, 22); size >= 8; size -= 2) {
      add(words.slice(0, size).join(' '))
      add(words.slice(Math.max(0, words.length - size)).join(' '))
    }
  } else if (normalized.length > 48) {
    add(normalized.slice(0, 80))
    add(normalized.slice(-80))
    add(normalized.slice(0, 48))
  }

  return candidates
}

function __tokens_with_positions(normalizedText) {
  const text = String(normalizedText || '')
  const tokens = []
  const re = /\S+/g
  let match = null

  while ((match = re.exec(text))) {
    const value = String(match[0] || '').trim()
    if (!value) continue

    tokens.push({
      value,
      start: match.index,
      end: match.index + value.length - 1
    })
  }

  return tokens
}

function __significant_token(value) {
  const token = String(value || '').trim()
  if (!token) return ''
  if (/^\d+$/.test(token)) return ''
  if (token.length <= 2) return ''
  return token
}

function __find_fuzzy_token_window(indexedText, quote) {
  const source = String(indexedText || '')
  const normalizedQuote = __normalize_search_text(quote)

  if (!source || !normalizedQuote) return null
  if (!source.includes(' ') || !normalizedQuote.includes(' ')) return null

  const sourceTokens = __tokens_with_positions(source)
  const quoteTokensRaw = __tokens_with_positions(normalizedQuote).map((x) => x.value)
  const quoteTokens = quoteTokensRaw.map(__significant_token).filter(Boolean)

  if (sourceTokens.length < 4 || quoteTokens.length < 4) return null

  const quoteSet = new Set(quoteTokens)
  const quoteUniqueCount = Math.max(1, quoteSet.size)

  const baseSize = Math.max(6, Math.min(quoteTokensRaw.length, 34))
  const minSize = Math.max(5, Math.floor(baseSize * 0.72))
  const maxSize = Math.min(sourceTokens.length, Math.ceil(baseSize * 1.45) + 4)

  let best = null

  for (let size = minSize; size <= maxSize; size += 1) {
    for (let start = 0; start + size <= sourceTokens.length; start += 1) {
      const end = start + size - 1
      const windowTokens = sourceTokens.slice(start, end + 1)
      const windowValues = windowTokens.map((x) => __significant_token(x.value)).filter(Boolean)

      if (!windowValues.length) continue

      const windowSet = new Set(windowValues)
      let overlap = 0

      for (const token of quoteSet) {
        if (windowSet.has(token)) overlap += 1
      }

      if (overlap < 4) continue

      const overlapRatio = overlap / quoteUniqueCount
      const density = overlap / Math.max(1, windowSet.size)

      let orderBonus = 0
      let cursor = 0

      for (const token of quoteTokens) {
        const found = windowValues.indexOf(token, cursor)
        if (found >= 0) {
          orderBonus += 1
          cursor = found + 1
        }
      }

      const orderRatio = orderBonus / Math.max(1, quoteTokens.length)
      const score = overlapRatio * 0.58 + density * 0.18 + orderRatio * 0.24

      if (!best || score > best.score) {
        best = {
          score,
          overlap,
          start: sourceTokens[start].start,
          end: sourceTokens[end].end
        }
      }
    }
  }

  if (!best) return null

  const strictEnough = best.score >= 0.54 && best.overlap >= 5
  const shortButStrong = quoteTokens.length <= 7 && best.score >= 0.66 && best.overlap >= 4

  return strictEnough || shortButStrong ? best : null
}

function __highlight_fuzzy_window(indexed, quote) {
  const match = __find_fuzzy_token_window(indexed?.text || '', quote)
  if (!match) return null

  const startRef = indexed.map[match.start]
  const endRef = indexed.map[match.end]

  return __highlight_range(startRef, endRef)
}

function __clear_citation_highlight() {
  try {
    if (__citation_highlight_timer) clearTimeout(__citation_highlight_timer)
  } catch {}
  __citation_highlight_timer = null

  try {
    if (__citation_highlight_retry_timer) clearTimeout(__citation_highlight_retry_timer)
  } catch {}
  __citation_highlight_retry_timer = null

  try {
    const root = continuousContainer.value || document
    root.querySelectorAll('mark[data-nisb-citation-hit="1"]').forEach((mark) => {
      const parent = mark.parentNode
      if (!parent) return
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark)
      parent.removeChild(mark)
      try {
        parent.normalize()
      } catch {}
    })

    root.querySelectorAll('.is-citation-target, .is-citation-fallback').forEach((el) => {
      el.classList.remove('is-citation-target', 'is-citation-fallback')
    })
  } catch {}
}

function __arm_citation_highlight_cleanup() {
  try {
    if (__citation_highlight_timer) clearTimeout(__citation_highlight_timer)
  } catch {}

  __citation_highlight_timer = setTimeout(() => {
    __clear_citation_highlight()
  }, 9000)
}

function __highlight_range(startRef, endRef) {
  if (!startRef?.node || !endRef?.node) return null

  try {
    const range = document.createRange()
    range.setStart(startRef.node, startRef.offset)
    range.setEnd(endRef.node, endRef.offset + 1)

    const mark = document.createElement('mark')
    mark.className = 'nisb-citation-hit'
    mark.setAttribute('data-nisb-citation-hit', '1')

    const fragment = range.extractContents()
    mark.appendChild(fragment)
    range.insertNode(mark)

    try {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
    } catch {}

    return mark
  } catch {
    return null
  }
}

function __pulse_span(spanEl, { fallback = false } = {}) {
  if (!spanEl) return false

  spanEl.classList.add(fallback ? 'is-citation-fallback' : 'is-citation-target')

  try {
    spanEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
  } catch {}

  __arm_citation_highlight_cleanup()
  return true
}

async function __highlight_citation_target(spanIndex, payload, attempt = 0) {
  const quote = __highlight_text_from_payload(payload)
  const n = Number(spanIndex)

  if (!Number.isFinite(n)) return false

  await nextTick()

  const spanEl = __span_el(n)
  if (!spanEl) {
    if (attempt < 6) {
      __citation_highlight_retry_timer = setTimeout(() => {
        __highlight_citation_target(n, payload, attempt + 1)
      }, 140 + attempt * 110)
    }
    return false
  }

  __clear_citation_highlight()

  if (!quote) {
    return __pulse_span(spanEl, { fallback: true })
  }

  const roots = Array.from(spanEl.querySelectorAll('.continuous-text, .preview-content'))
    .filter(Boolean)
    .filter((el, index, arr) => arr.indexOf(el) === index)

  if (!roots.length) roots.push(spanEl)

  for (const textRoot of roots) {
    const indexed = __build_normalized_index(textRoot)
    const candidates = __quote_candidates(quote)

    for (const candidate of candidates) {
      const foundAt = indexed.text.indexOf(candidate)
      if (foundAt < 0) continue

      const startRef = indexed.map[foundAt]
      const endRef = indexed.map[foundAt + candidate.length - 1]
      const mark = __highlight_range(startRef, endRef)

      if (mark) {
        spanEl.classList.add('is-citation-target')
        __arm_citation_highlight_cleanup()
        return true
      }
    }
  }

  for (const textRoot of roots) {
    const indexed = __build_normalized_index(textRoot)
    const mark = __highlight_fuzzy_window(indexed, quote)

    if (mark) {
      spanEl.classList.add('is-citation-target')
      __arm_citation_highlight_cleanup()
      return true
    }
  }

  return __pulse_span(spanEl, { fallback: true })
}

function __payload_from_doc_span_event(detail) {
  const d = detail || {}
  const libraryId = __string_value(d.libraryId || d.library_id)
  const docId = __string_value(d.docId || d.doc_id)
  const spanIndex = d.spanIndex ?? d.span_index ?? d.span ?? null

  return {
    ...d,
    libraryId,
    docId,
    spanIndex,
    highlightText: d.highlightText || d.highlight_text || d.highlightQuote || d.highlight_quote || d.quote || '',
    highlightQuote: d.highlightQuote || d.highlight_quote || d.quote || '',
    highlightMode: d.highlightMode || d.highlight_mode || (d.quote ? 'quote' : 'span'),
    highlightSource: d.highlightSource || d.highlight_source || 'doc_span_event'
  }
}

async function onOpenDocSpan(event) {
  const payload = __payload_from_doc_span_event(event?.detail || {})
  if (!payload.libraryId || !payload.docId) return
  if (payload.libraryId !== props.libraryId) return
  if (payload.docId !== props.docId) return

  const spanIndex = _extractSpanIndex(payload)
  if (!Number.isFinite(Number(spanIndex))) return

  if (!continuousReadingEnabled.value) continuousReadingEnabled.value = true
  await loadContinuousReading(Number(spanIndex))
  await __scroll_to_span(spanIndex, 'center')
  await __highlight_citation_target(spanIndex, payload)
}

async function applyLibraryOpenPayload(payload) {
  if (!payload) return false
  if (payload.libraryId !== props.libraryId) return false

  if (payload.docId !== props.docId) {
    pendingOpenPayload.value = payload
    try {
      window.__nisb_last_library_doc_open = payload
    } catch {}
    return false
  }

  const key = __make_apply_key(payload)
  const now = Date.now()
  const spanIndexForDedupe = _extractSpanIndex(payload)
  if (key && key === __last_apply_key.value && now - __last_apply_ts.value < 1200) {
    if (Number.isFinite(Number(spanIndexForDedupe))) {
      await __scroll_to_span(spanIndexForDedupe, 'center')
      await __highlight_citation_target(spanIndexForDedupe, payload)
    }
    return true
  }
  if (key) {
    __last_apply_key.value = key
    __last_apply_ts.value = now
  }

  const prevSuspend = _persist_suspended.value
  _persist_suspended.value = true

  const reader = payload.reader || {}
  _applyingTimelinePayload = true

  try {
    if (reader.lang) targetLanguage.value = _normalizeLang(reader.lang)
    if (Number.isFinite(reader.pretranslateSpans)) pretranslateAhead.value = Number(reader.pretranslateSpans)
    if (typeof reader.compareMode === 'boolean') compareMode.value = !!reader.compareMode
    if (typeof reader.smartPretranslate === 'boolean') libraryAutoPretranslate.value = !!reader.smartPretranslate
    if (typeof reader.showTranslation === 'boolean') showTranslation.value = !!reader.showTranslation
    if (typeof reader.continuous === 'boolean') continuousReadingEnabled.value = !!reader.continuous

    const spanIndex = _extractSpanIndex(payload)
    const hasSpanJump = Number.isFinite(spanIndex)

    if (hasSpanJump) {
      if (!continuousReadingEnabled.value) continuousReadingEnabled.value = true
      await loadContinuousReading(Number(spanIndex))
      await __scroll_to_span(spanIndex, 'center')
      await __highlight_citation_target(spanIndex, payload)
      _syncAllStates(false)
      return true
    }

    const wantContinuous = typeof reader.continuous === 'boolean' ? !!reader.continuous : null

    if (wantContinuous === false) {
      continuousReadingEnabled.value = false
      continuousSpans.value = []
      cancelAllWork('payload_disable')
      showTranslation.value = false
      libraryAutoPretranslate.value = false
      compareMode.value = false
      pretranslatePaused.value = false
      _syncAllStates(false)
      return true
    }

    if (wantContinuous === true) {
      continuousReadingEnabled.value = true
      await loadContinuousReading()
      await nextTick()
      _schedule_enhance_markdown_dom(0)
      _syncAllStates(false)
      return true
    }

    _syncAllStates(false)
    return true
  } finally {
    _applyingTimelinePayload = false
    _persist_suspended.value = prevSuspend
    _syncAllStates(true)
  }
}

function onApplyLibraryDocState(evt) {
  const payload = evt?.detail || null
  applyLibraryOpenPayload(payload)
}

async function onReaderControl(evt) {
  const d = evt?.detail || null
  if (!d) return
  if (d.libraryId && d.libraryId !== props.libraryId) return
  if (d.docId && d.docId !== props.docId) return

  const action = String(d.action || '').trim()
  const value = d.value

  if (action === 'toggle_continuous') {
    const wasOn = !!continuousReadingEnabled.value
    const nextVal = typeof value === 'boolean' ? value : !continuousReadingEnabled.value
    continuousReadingEnabled.value = !!nextVal

    if (continuousReadingEnabled.value) {
      const needLoad = !wasOn || !Array.isArray(continuousSpans.value) || continuousSpans.value.length === 0
      if (needLoad) {
        await loadContinuousReading()
        await nextTick()
        _schedule_enhance_markdown_dom(0)
      } else {
        _schedule_enhance_markdown_dom(0)
      }
    } else {
      onToggleContinuous()
      return
    }

    _syncAllStates()
    return
  }

  if (action === 'toggle_translation') {
    const nextVal = typeof value === 'boolean' ? value : !showTranslation.value

    if (nextVal) {
      if (!continuousReadingEnabled.value) continuousReadingEnabled.value = true
      showTranslation.value = true
      if (!continuousSpans.value?.length && !continuousLoading.value) await loadContinuousReading()
    } else {
      showTranslation.value = false
      compareMode.value = false
    }

    await nextTick()
    _schedule_enhance_markdown_dom(0)

    _syncAllStates()
    return
  }

  if (action === 'toggle_compare') {
    const nextVal = typeof value === 'boolean' ? value : !compareMode.value

    if (nextVal) {
      if (!continuousReadingEnabled.value) continuousReadingEnabled.value = true
      if (!showTranslation.value) showTranslation.value = true
      if (!continuousSpans.value?.length && !continuousLoading.value) await loadContinuousReading()
      compareMode.value = true
    } else {
      compareMode.value = false
    }

    await nextTick()
    _schedule_enhance_markdown_dom(0)

    _syncAllStates()
    return
  }

  if (action === 'toggle_pretranslate') {
    const nextVal = typeof value === 'boolean' ? value : !libraryAutoPretranslate.value
    libraryAutoPretranslate.value = !!nextVal
    if (!libraryAutoPretranslate.value) {
      cancelPretranslate('smart_off')
      pretranslatePaused.value = false
      _syncAllStates()
      return
    }

    pretranslatePaused.value = false
    if (!_autoEnablingContinuous) {
      _autoEnablingContinuous = true
      try {
        if (!continuousReadingEnabled.value) {
          continuousReadingEnabled.value = true
          showTranslation.value = true
          if (!continuousSpans.value?.length && !continuousLoading.value) await loadContinuousReading()
        } else {
          if (!showTranslation.value) showTranslation.value = true
          if (!continuousSpans.value?.length && !continuousLoading.value) await loadContinuousReading()
        }
      } finally {
        _autoEnablingContinuous = false
        _syncAllStates()
      }
    } else {
      _syncAllStates()
    }
    return
  }

  if (action === 'set_pretranslate_ahead') {
    const n = Number(value)
    if (Number.isFinite(n) && n > 0) pretranslateAhead.value = n
    _syncAllStates()
    return
  }

  if (action === 'cancel_pretranslate') {
    cancelPretranslate('user')
    return
  }

  if (action === 'resume_pretranslate') {
    resumePretranslate()
    return
  }

  if (action === 'set_lang') {
    const prevLang = String(targetLanguage.value || 'zh-CN')
    targetLanguage.value = _normalizeLang(value)
    _saveTargetLanguagePreference(targetLanguage.value)

    try {
      _cache_clear_doc(prevLang)
      _cache_clear_doc(String(targetLanguage.value || 'zh-CN'))
    } catch {}

    if (continuousReadingEnabled.value) {
      cancelPretranslate('lang_change')
      pretranslatePaused.value = false
      continuousSpans.value.forEach((span) => {
        span.translated_text = null
        span.from_cache = false
        span.translating = false
        span.translation_refused = false
        span.translation_refusal_text = ''
      })
    }
    _syncAllStates()
    return
  }
}

watch(
  () => targetLanguage.value,
  (newVal, oldVal) => {
    _saveTargetLanguagePreference(newVal)

    try {
      if (oldVal) _cache_clear_doc(String(oldVal))
      if (newVal) _cache_clear_doc(String(newVal))
    } catch {}

    if (!continuousReadingEnabled.value) {
      _syncAllStates()
      return
    }
    cancelPretranslate('lang_change')
    pretranslatePaused.value = false
    continuousSpans.value.forEach((span) => {
      span.translated_text = null
      span.from_cache = false
      span.translating = false
      span.translation_refused = false
      span.translation_refusal_text = ''
    })
    _syncAllStates()
  }
)

watch(
  () => [props.libraryId, props.docId],
  async () => {
    _persist_suspended.value = true

    resetState({ persist: false })
    await nextTick()

    const p = pendingOpenPayload.value || window.__nisb_last_library_doc_open || null
    if (p && p.libraryId === props.libraryId && p.docId === props.docId) {
      const ok = await applyLibraryOpenPayload(p)
      if (ok) {
        pendingOpenPayload.value = null
        try {
          if (window.__nisb_last_library_doc_open === p) delete window.__nisb_last_library_doc_open
        } catch {}
        _persist_suspended.value = false
        _syncAllStates(true)
        _schedule_enhance_markdown_dom(0)
        return
      }
    }

    await _apply_reader_prefs_for_new_doc()

    _persist_suspended.value = false
    _syncAllStates(true)
    _schedule_enhance_markdown_dom(0)
  },
  { immediate: true }
)

watch([continuousReadingEnabled, libraryAutoPretranslate, pretranslateAhead], () => {
  if (continuousReadingEnabled.value && libraryAutoPretranslate.value) attachScrollListener()
  else detachScrollListener()
  _syncAllStates()
})

watch(
  () => [
    continuousReadingEnabled.value,
    showTranslation.value,
    compareMode.value,
    targetLanguage.value,
    libraryAutoPretranslate.value,
    pretranslateAhead.value,
    translateBackend.value,
    pretranslatePaused.value,
    queue.value.length,
    runningMap.value.size,
    continuousSpans.value.length
  ],
  async () => {
    _syncAllStates()
    _schedule_enhance_markdown_dom(60)
  },
  { immediate: true }
)

function _isDockedRightNow() {
  try {
    const d = window.__nisbLibraryDockState
    return !!(d && d.docked === true && d.side === 'right')
  } catch {
    return false
  }
}

function bindGlobalListener() {
  if (_bound.value) return
  _bound.value = true
  window.addEventListener('nisb-apply-library-doc-state', onApplyLibraryDocState)
  window.addEventListener('nisb-library-reader-control', onReaderControl)
  window.addEventListener('nisb-span-artifacts-open', onSpanArtifactsOpen)
  window.addEventListener('nisb-open-doc-span', onOpenDocSpan)
}

function unbindGlobalListener() {
  if (!_bound.value) return
  _bound.value = false
  window.removeEventListener('nisb-apply-library-doc-state', onApplyLibraryDocState)
  window.removeEventListener('nisb-library-reader-control', onReaderControl)
  window.removeEventListener('nisb-span-artifacts-open', onSpanArtifactsOpen)
  window.removeEventListener('nisb-open-doc-span', onOpenDocSpan)
}

const _bound = ref(false)

onMounted(() => {
  _is_active.value = true
  _syncAllStates(false)
  bindGlobalListener()

  nextTick(() => {
    try {
      const last = window.__nisb_last_library_doc_open
      if (last && last.libraryId === props.libraryId && last.docId === props.docId) {
        applyLibraryOpenPayload(last)
        delete window.__nisb_last_library_doc_open
      }
    } catch (e) {
      console.error('[连续阅读] 读取时间线缓存失败:', e)
    } finally {
      _schedule_enhance_markdown_dom(0)
    }
  })

  if (continuousReadingEnabled.value && libraryAutoPretranslate.value) attachScrollListener()
})

onActivated(() => {
  _is_active.value = true
  _syncAllStates(false)
  bindGlobalListener()
  _schedule_enhance_markdown_dom(0)
})

onDeactivated(() => {
  _is_active.value = false
  __clear_citation_highlight()

  detachScrollListener()
  cancelAllWork('deactivated')
  unbindGlobalListener()
})

onUnmounted(() => {
  _is_active.value = false
  __clear_citation_highlight()

  if (_broadcast_timer) {
    clearTimeout(_broadcast_timer)
    _broadcast_timer = null
  }
  if (_prefs_write_timer) {
    clearTimeout(_prefs_write_timer)
    _prefs_write_timer = null
  }
  try {
    if (__enhance_timer) clearTimeout(__enhance_timer)
  } catch {}
  __enhance_timer = null

  detachScrollListener()
  cancelAllWork('unmount')
  unbindGlobalListener()
})
</script>

<style scoped>
.doc-panel-continuous {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.continuous-view {
  width: 100%;
  min-width: 0;
  max-height: none;
  margin-top: 0.62rem;
  padding: 0;
  overflow-y: visible;
  overflow-x: hidden;
}

.continuous-span {
  position: relative;
  min-width: 0;
  margin-bottom: 0.86rem;
  padding: 0.72rem 0.78rem 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 17px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 12px 28px rgba(0, 0, 0, 0.055);
  scroll-margin-top: 76px;
}

.continuous-span::before {
  content: '';
  position: absolute;
  left: 0.62rem;
  top: 0.78rem;
  bottom: 0.78rem;
  width: 3px;
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected) 44%, transparent),
      color-mix(in srgb, #16a34a 36%, transparent)
    );
  opacity: 0.46;
  pointer-events: none;
}

.continuous-span:last-child {
  margin-bottom: 0;
}

.continuous-span-header {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.62rem;
  margin-bottom: 0.58rem;
  padding: 0 0 0.52rem 0.62rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
}

.span-meta {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  min-height: 24px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 30%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.span-actions {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.36rem;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.span-actions::-webkit-scrollbar {
  display: none;
}

.cache-badge,
.refusal-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  box-sizing: border-box;
  padding: 0 0.5rem;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.cache-badge {
  border: 1px solid color-mix(in srgb, #16a34a 34%, var(--line));
  background: rgba(22, 163, 74, 0.12);
  color: #16a34a;
}

.refusal-badge {
  border: 1px solid color-mix(in srgb, #d97706 38%, var(--line));
  background: rgba(217, 119, 6, 0.12);
  color: #d97706;
}

.continuous-lang {
  flex: 0 0 auto;
  width: auto;
  min-width: 94px;
  min-height: 30px;
  box-sizing: border-box;
  padding: 0.34rem 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1.2;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.continuous-lang:focus {
  border-color: color-mix(in srgb, var(--selected) 50%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.doc-panel-btn {
  flex: 0 0 auto;
  min-height: 30px;
  box-sizing: border-box;
  padding: 0 0.6rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 80%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
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

.doc-panel-btn:hover:enabled,
.doc-panel-btn:focus-visible:enabled {
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

.doc-panel-btn:active:enabled {
  transform: translateY(1px);
}

.doc-panel-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.doc-panel-btn.small,
.span-translate-btn {
  min-height: 28px;
  padding: 0 0.54rem;
  font-size: 0.68rem;
}

.compare-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.68rem;
  align-items: start;
  padding-left: 0.62rem;
}

.compare-col {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
}

.compare-label {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  min-height: 23px;
  box-sizing: border-box;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 60%, transparent);
  color: var(--text-secondary);
  font-size: 0.67rem;
  font-weight: 740;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-content {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.86rem;
  line-height: 1.68;
  overflow-wrap: break-word;
}

.continuous-text {
  padding: 0.74rem 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 70%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 58%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

.continuous-span > .continuous-text {
  margin-left: 0.62rem;
}

.preview-content :deep(p) {
  margin: 0.44rem 0;
}

.preview-content :deep(p:first-child) {
  margin-top: 0;
}

.preview-content :deep(p:last-child) {
  margin-bottom: 0;
}

.preview-content :deep(h1),
.preview-content :deep(h2),
.preview-content :deep(h3),
.preview-content :deep(h4),
.preview-content :deep(h5),
.preview-content :deep(h6) {
  margin: 0.82rem 0 0.38rem;
  color: var(--text-main, var(--text));
  font-weight: 820;
  line-height: 1.28;
  overflow-wrap: break-word;
}

.preview-content :deep(h1) {
  font-size: 1.04rem;
}

.preview-content :deep(h2) {
  font-size: 0.98rem;
}

.preview-content :deep(h3) {
  font-size: 0.92rem;
}

.preview-content :deep(h4),
.preview-content :deep(h5),
.preview-content :deep(h6) {
  font-size: 0.88rem;
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
  margin: 0.48rem 0;
  padding-left: 1.18rem;
}

.preview-content :deep(li) {
  margin: 0.22rem 0;
}

.preview-content :deep(blockquote) {
  margin: 0.62rem 0;
  padding: 0.5rem 0.66rem;
  border-left: 3px solid color-mix(in srgb, var(--selected) 48%, var(--line));
  border-radius: 0 12px 12px 0;
  background: color-mix(in srgb, var(--selected-bg) 28%, transparent);
  color: var(--text-secondary);
}

.continuous-span.is-citation-target,
.continuous-span.is-citation-fallback {
  position: relative;
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--selected) 18%, transparent),
    0 16px 42px rgba(66, 133, 244, 0.16);
}

.continuous-span.is-citation-target::after,
.continuous-span.is-citation-fallback::after {
  content: "";
  position: absolute;
  inset: 0.42rem;
  border-radius: 18px;
  pointer-events: none;
  background:
    radial-gradient(
      circle at 18% 16%,
      color-mix(in srgb, var(--selected) 16%, transparent),
      transparent 34%
    );
  opacity: 0.85;
  animation: nisb-citation-span-pulse 1.8s ease-out both;
}

.preview-content :deep(mark.nisb-citation-hit) {
  display: inline;
  padding: 0.06em 0.18em;
  border-radius: 0.42em;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected) 24%, transparent),
      rgba(64, 224, 176, 0.18)
    );
  color: inherit;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--selected) 20%, transparent),
    0 8px 22px rgba(66, 133, 244, 0.16);
  animation: nisb-citation-hit-in 0.42s ease-out both;
}

@keyframes nisb-citation-hit-in {
  from {
    background: color-mix(in srgb, var(--selected) 42%, transparent);
    box-shadow:
      0 0 0 2px color-mix(in srgb, var(--selected) 32%, transparent),
      0 12px 30px rgba(66, 133, 244, 0.24);
  }

  to {
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--selected) 24%, transparent),
        rgba(64, 224, 176, 0.18)
      );
  }
}

@keyframes nisb-citation-span-pulse {
  0% {
    opacity: 0;
    transform: scale(0.985);
  }

  18% {
    opacity: 1;
    transform: scale(1);
  }

  100% {
    opacity: 0;
    transform: scale(1.012);
  }
}

.preview-content :deep(a) {
  color: var(--selected);
  text-decoration: none;
  overflow-wrap: anywhere;
}

.preview-content :deep(a:hover) {
  text-decoration: underline;
}

.preview-content :deep(code) {
  padding: 0.08rem 0.28rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 7px;
  background: color-mix(in srgb, var(--sidebar-bg) 70%, transparent);
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.78em;
  overflow-wrap: anywhere;
}

.preview-content :deep(pre) {
  margin: 0.62rem 0;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 50%, transparent)
    );
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.preview-content :deep(pre::-webkit-scrollbar) {
  height: 8px;
}

.preview-content :deep(pre::-webkit-scrollbar-thumb) {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.preview-content :deep(pre code) {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 0.78rem;
  line-height: 1.55;
  white-space: pre;
  overflow-wrap: normal;
}

.preview-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.62rem 0;
  display: block;
  overflow-x: auto;
  scrollbar-width: thin;
}

.preview-content :deep(th),
.preview-content :deep(td) {
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  padding: 0.42rem 0.5rem;
  text-align: left;
  vertical-align: top;
}

.preview-content :deep(th) {
  background: color-mix(in srgb, var(--selected-bg) 28%, transparent);
  color: var(--text-main, var(--text));
  font-weight: 780;
}

.preview-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.08);
}

.empty-tip {
  box-sizing: border-box;
  margin: 0.62rem 0;
  padding: 1rem 0.82rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

@media (max-width: 900px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .continuous-span {
    padding: 0.66rem;
    border-radius: 16px;
  }

  .continuous-span::before {
    left: 0.5rem;
    top: 0.7rem;
    bottom: 0.7rem;
  }

  .continuous-span-header {
    grid-template-columns: 1fr;
    align-items: stretch;
    gap: 0.5rem;
    padding-left: 0.52rem;
  }

  .span-actions {
    justify-content: flex-start;
  }

  .continuous-span > .continuous-text,
  .compare-grid {
    margin-left: 0;
    padding-left: 0.52rem;
  }
}

@media (max-width: 460px) {
  .continuous-span {
    padding: 0.58rem;
  }

  .continuous-span-header {
    padding-left: 0.42rem;
  }

  .continuous-span > .continuous-text,
  .compare-grid {
    padding-left: 0.42rem;
  }

  .span-actions {
    flex-wrap: wrap;
    overflow: visible;
  }

  .continuous-lang,
  .doc-panel-btn {
    flex: 1 1 120px;
  }

  .doc-panel-btn {
    justify-content: center;
  }

  .continuous-text {
    padding: 0.64rem;
  }
}
</style>

