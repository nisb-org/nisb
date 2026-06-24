<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/LibrarySearchPanel.vue -->
<template>
  <div class="panel library-search-panel" :class="{ hidden_by_reader_chrome: reader_chrome_hidden }" v-if="store.libraryId">
    <div v-if="!store.panelOpen" class="collapsed" @click="store.openPanel()">
      <div class="collapsed-left">
        <div class="collapsed-line">
          <div class="chips">
            <template v-if="activeDocId">
              <button
                class="chip"
                :class="{ on: reader.continuous }"
                @click.stop="toggleContinuous"
                :title="continuousTitle"
                type="button"
              >
                {{ continuousChipText }}
              </button>

              <button
                class="chip"
                :class="{ on: reader.showTranslation }"
                @click.stop="toggleTranslation"
                :title="translationTitle"
                type="button"
              >
                {{ translationChipText }}
              </button>

              <button
                class="chip"
                :class="{ on: reader.smartPretranslate }"
                @click.stop="togglePretranslate"
                :title="pretranslateTitle"
                type="button"
              >
                {{ pretranslateChipText }}
              </button>

              <button
                class="chip icon"
                @click.stop="openSpanTools"
                :title="t('library.center.searchPanel.spanToolsTitle')"
                type="button"
              >
                ⚡
              </button>

              <span class="chip meta" v-if="reader.smartPretranslate && reader.continuous" :title="progressTitle">
                {{ progressChipText }}
                <span v-if="progress.paused">⏸</span>
                <span v-else>▶</span>
              </span>
            </template>

            <span
              v-else
              class="chip meta"
              :title="t('library.center.searchPanel.noDocumentHint')"
            >
              {{ t('library.center.searchPanel.noDocumentSelected') }}
            </span>
          </div>
        </div>

        <div class="collapsed-sub muted">{{ collapsedResultText }}</div>
      </div>

      <button class="mini-icon" @click.stop="store.openPanel()" :title="t('library.center.searchPanel.expand')" type="button">▴</button>
    </div>

    <template v-else>
      <div class="reader-bar" v-if="activeDocId">
        <div class="reader-controls">
          <button class="chip" :class="{ on: reader.continuous }" @click="toggleContinuous" :title="continuousTitle" type="button">
            {{ continuousChipText }}
          </button>

          <button class="chip" :class="{ on: reader.showTranslation }" @click="toggleTranslation" :title="translationTitle" type="button">
            {{ translationChipText }}
          </button>

          <button
            class="chip"
            :class="{ on: reader.compareMode }"
            @click="toggleCompare"
            :title="compareTitle"
            type="button"
          >
            {{ compareChipText }}
          </button>

          <select
            class="select tiny"
            v-model="reader.lang"
            :disabled="!reader.continuous"
            @change="setLang"
            :title="t('library.center.searchPanel.targetLanguage')"
          >
            <option
              v-for="lang in targetLanguageOptions"
              :key="lang.value"
              :value="lang.value"
            >
              {{ lang.label }}
            </option>
          </select>

          <button
            class="chip"
            :class="{ on: reader.smartPretranslate }"
            @click="togglePretranslate"
            :title="pretranslateExpandedTitle"
            type="button"
          >
            {{ pretranslateChipText }}
          </button>

          <select
            class="select tiny"
            v-model.number="reader.pretranslateSpans"
            :disabled="!reader.continuous || !reader.smartPretranslate"
            @change="setPretranslateAhead"
            :title="t('library.center.searchPanel.pretranslateSpanCount')"
          >
            <option :value="1">{{ t('library.center.searchPanel.pretranslateOption', { count: 1 }) }}</option>
            <option :value="2">{{ t('library.center.searchPanel.pretranslateOption', { count: 2 }) }}</option>
            <option :value="3">{{ t('library.center.searchPanel.pretranslateOption', { count: 3 }) }}</option>
            <option :value="5">{{ t('library.center.searchPanel.pretranslateOption', { count: 5 }) }}</option>
            <option :value="10">{{ t('library.center.searchPanel.pretranslateOption', { count: 10 }) }}</option>
          </select>

          <button class="chip icon" @click="openSpanTools" :title="t('library.center.searchPanel.spanToolsTitle')" type="button">⚡</button>

          <span class="chip meta" v-if="reader.smartPretranslate && reader.continuous" :title="progressTitle">
            {{ progressChipText }}
            <span v-if="progress.paused">⏸</span>
            <span v-else>▶</span>
          </span>

          <button
            class="btn tiny subtle"
            v-if="reader.smartPretranslate && reader.continuous && !progress.paused"
            :disabled="!hasPretranslateWork"
            @click="cancelPretranslate"
            :title="t('library.center.searchPanel.cancelPretranslateTitle')"
            type="button"
          >
            {{ t('library.center.searchPanel.cancel') }}
          </button>

          <button
            class="btn tiny subtle"
            v-else-if="reader.smartPretranslate && reader.continuous && progress.paused"
            :disabled="!reader.smartPretranslate"
            @click="resumePretranslate"
            :title="t('library.center.searchPanel.resumePretranslateTitle')"
            type="button"
          >
            {{ t('library.center.searchPanel.resume') }}
          </button>

          <button class="chip icon collapse-btn" @click="close_panel_and_release_reader_chrome()" :title="t('library.center.searchPanel.collapse')" type="button">▾</button>
        </div>
      </div>

      <div class="search-area">
        <div class="search-row">
          <input
            class="input"
            v-model="store.query"
            :placeholder="placeholderText"
            @keydown.enter.prevent="store.search()"
          />
          <button class="btn" :disabled="store.loading || !store.canSearch" @click="store.search()" type="button">
            {{ store.loading ? t('library.center.searchPanel.searching') : t('library.center.searchPanel.search') }}
          </button>
        </div>

        <div class="filters-row">
          <div class="seg">
            <button class="seg-btn" :class="{ active: store.scope === 'doc' }" @click="store.setScope('doc')" type="button">
              {{ t('library.center.searchPanel.scopeDoc') }}
            </button>
            <button class="seg-btn" :class="{ active: store.scope === 'library' }" @click="store.setScope('library')" type="button">
              {{ t('library.center.searchPanel.scopeLibrary') }}
            </button>
            <button class="seg-btn" :class="{ active: store.scope === 'global' }" @click="store.setScope('global')" type="button">
              {{ t('library.center.searchPanel.scopeGlobal') }}
            </button>
          </div>

          <div class="seg">
            <button class="seg-btn" :class="{ active: store.mode === 'chunk' }" @click="store.setMode('chunk')" type="button">
              {{ t('library.center.searchPanel.modeChunk') }}
            </button>
            <button class="seg-btn" :class="{ active: store.mode === 'evidence' }" @click="store.setMode('evidence')" type="button">
              {{ t('library.center.searchPanel.modeEvidence') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="store.error" class="msg error">{{ store.error }}</div>

      <div class="list" v-if="store.items.length">
        <div
          v-for="(it, idx) in store.items"
          :key="itemKey(it, idx)"
          class="item"
          :class="{ active: isSelected(it) }"
          @click="select(it)"
        >
          <div class="meta">
            <span class="score">{{ formatScore(it) }}</span>
            <span class="muted" v-if="it?.library_id">{{ t('library.center.searchPanel.metaLibrary', { id: it.library_id }) }}</span>
            <span class="muted" v-if="it?.doc_id">{{ t('library.center.searchPanel.metaDoc', { id: it.doc_id }) }}</span>
            <span
              class="muted"
              v-if="it?.chunk_id !== undefined && it?.chunk_id !== null && it?.chunk_id !== ''"
            >
              {{ t('library.center.searchPanel.metaChunk', { id: it.chunk_id }) }}
            </span>
            <span class="muted" v-if="displaySpan(it) !== '?'">
              {{ t('library.center.searchPanel.metaSpan', { id: displaySpan(it) }) }}
            </span>
          </div>

          <div class="text">{{ previewText(it) }}</div>

          <details v-if="hasExpandableText(it)" class="details" @click.stop>
            <summary>{{ t('library.center.searchPanel.expandContent') }}</summary>
            <div class="details-body selectable">{{ fullText(it) }}</div>
          </details>

          <div class="actions">
            <button class="mini-btn" :disabled="!canJump(it)" @click.stop="jump(it)" type="button">
              {{ t('library.center.searchPanel.jump') }}
            </button>
            <button class="mini-btn" :disabled="!String(fullText(it) || '').trim()" @click.stop="copyItem(it)" type="button">
              {{ t('library.center.searchPanel.copy') }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLibrarySearchStore } from '../../stores/librarySearch'

const { t, locale } = useI18n()
const store = useLibrarySearchStore()

const READER_TARGET_LANG_PREF_KEY = 'nisb_library_reader_target_lang_v1'

const SUPPORTED_READER_LANGS = [
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
]

const reader = ref({
  continuous: false,
  showTranslation: false,
  compareMode: false,
  smartPretranslate: false,
  pretranslateSpans: 2,
  lang: load_reader_lang_pref() || default_reader_lang_from_locale()
})

const targetLanguageOptions = computed(() => [
  { value: 'zh-CN', label: t('library.center.searchPanel.targetLanguages.zhCN') },
  { value: 'en', label: t('library.center.searchPanel.targetLanguages.en') },
  { value: 'ja', label: t('library.center.searchPanel.targetLanguages.ja') },
  { value: 'ko', label: t('library.center.searchPanel.targetLanguages.ko') },
  { value: 'fr', label: t('library.center.searchPanel.targetLanguages.fr') },
  { value: 'de', label: t('library.center.searchPanel.targetLanguages.de') },
  { value: 'es', label: t('library.center.searchPanel.targetLanguages.es') },
  { value: 'pt-BR', label: t('library.center.searchPanel.targetLanguages.ptBR') },
  { value: 'it', label: t('library.center.searchPanel.targetLanguages.it') },
  { value: 'ru', label: t('library.center.searchPanel.targetLanguages.ru') },
  { value: 'ar', label: t('library.center.searchPanel.targetLanguages.ar') },
  { value: 'hi', label: t('library.center.searchPanel.targetLanguages.hi') },
  { value: 'vi', label: t('library.center.searchPanel.targetLanguages.vi') },
  { value: 'th', label: t('library.center.searchPanel.targetLanguages.th') },
  { value: 'id', label: t('library.center.searchPanel.targetLanguages.id') }
])

function normalize_reader_lang(value) {
  const s = String(value || '').trim()
  const lower = s.toLowerCase()

  if (!lower) return ''
  if (lower === 'zh' || lower === 'zh-cn' || lower === 'zh-hans' || lower.startsWith('zh_cn')) return 'zh-CN'
  if (lower === 'pt-br' || lower === 'pt_br') return 'pt-BR'

  const exact = SUPPORTED_READER_LANGS.find((lang) => lang.toLowerCase() === lower)
  if (exact) return exact

  const base = lower.split(/[-_]/)[0]
  const byBase = SUPPORTED_READER_LANGS.find((lang) => lang.toLowerCase() === base)
  return byBase || 'zh-CN'
}

function default_reader_lang_from_locale() {
  return normalize_reader_lang(locale.value || navigator.language || 'zh-CN') || 'zh-CN'
}

function load_reader_lang_pref() {
  try {
    const raw = localStorage.getItem(READER_TARGET_LANG_PREF_KEY)
    return raw ? normalize_reader_lang(raw) : ''
  } catch {
    return ''
  }
}

function save_reader_lang_pref(lang) {
  const normalized = normalize_reader_lang(lang)
  if (!normalized) return

  try {
    localStorage.setItem(READER_TARGET_LANG_PREF_KEY, normalized)
  } catch {}
}

const progress = ref({
  total: 0,
  translated: 0,
  refused: 0,
  queue: 0,
  running: 0,
  paused: false
})

const _active_library_id = ref('')
const _active_doc_id = ref('')

const activeLibraryId = computed(() => String(store.libraryId || _active_library_id.value || '').trim())

const activeDocId = computed(() => {
  const raw = store.docId || _active_doc_id.value
  if (raw === null || raw === undefined) return ''
  return String(raw).trim()
})

watch(
  () => store.docId,
  (v) => {
    const s = v === null || v === undefined ? '' : String(v).trim()
    if (!s) _active_doc_id.value = ''
  }
)

const placeholderText = computed(() => {
  if (store.scope === 'doc') {
    return activeDocId.value
      ? t('library.center.searchPanel.placeholderDocReady')
      : t('library.center.searchPanel.placeholderDocEmpty')
  }
  if (store.scope === 'library') return t('library.center.searchPanel.placeholderLibrary')
  return t('library.center.searchPanel.placeholderGlobal')
})

const progressTitle = computed(() => {
  return [
    t('library.center.searchPanel.progressTotal', { count: progress.value.total }),
    t('library.center.searchPanel.progressTranslated', { count: progress.value.translated }),
    t('library.center.searchPanel.progressRefused', { count: progress.value.refused }),
    t('library.center.searchPanel.progressQueue', { count: progress.value.queue }),
    t('library.center.searchPanel.progressRunning', { count: progress.value.running })
  ].join('\n')
})

const progressChipText = computed(() => {
  return t('library.center.searchPanel.progressShort', {
    translated: progress.value.translated,
    total: progress.value.total
  })
})

const collapsedResultText = computed(() => {
  return store.items.length
    ? t('library.center.searchPanel.resultCount', { count: store.items.length })
    : ''
})

const hasPretranslateWork = computed(() => Number(progress.value.queue || 0) > 0 || Number(progress.value.running || 0) > 0)

const continuousTitle = computed(() => {
  return reader.value.continuous
    ? t('library.center.searchPanel.disableContinuous')
    : t('library.center.searchPanel.enableContinuous')
})

const translationTitle = computed(() => {
  return reader.value.showTranslation
    ? t('library.center.searchPanel.disableTranslation')
    : t('library.center.searchPanel.enableTranslation')
})

const pretranslateTitle = computed(() => {
  return reader.value.smartPretranslate
    ? t('library.center.searchPanel.disablePretranslate')
    : t('library.center.searchPanel.enablePretranslate')
})

const pretranslateExpandedTitle = computed(() => t('library.center.searchPanel.smartPretranslateTitle'))

const compareTitle = computed(() => t('library.center.searchPanel.compareTitle'))

const continuousChipText = computed(() => {
  return t('library.center.searchPanel.continuousChip', {
    state: reader.value.continuous ? '🟢' : '🔴'
  })
})

const translationChipText = computed(() => {
  return t('library.center.searchPanel.translationChip', {
    state: reader.value.showTranslation ? '🟢' : '🔴'
  })
})

const pretranslateChipText = computed(() => {
  return t('library.center.searchPanel.pretranslateChip', {
    state: reader.value.smartPretranslate ? '🟢' : '🔴'
  })
})

const compareChipText = computed(() => {
  return t('library.center.searchPanel.compareChip', {
    state: reader.value.compareMode ? '🟢' : '🔴'
  })
})

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function openSpanTools() {
  if (!activeLibraryId.value || !activeDocId.value) {
    alert(t('library.center.searchPanel.openDocumentFirst'))
    return
  }

  window.dispatchEvent(
    new CustomEvent('nisb-span-artifacts-open', {
      detail: {
        libraryId: activeLibraryId.value,
        docId: activeDocId.value,
        spanIndex: null,
        reader: window.nisbReaderState || null
      }
    })
  )

  window.dispatchEvent(
    new CustomEvent('nisb-library-artifacts-toggle', {
      detail: { libraryId: activeLibraryId.value, docId: activeDocId.value }
    })
  )
}

function itemKey(it, idx) {
  return it?.id || it?.event_id || `${it?.library_id || ''}:${it?.doc_id || ''}:${it?.chunk_id || ''}:${it?.span_index || ''}:${idx}`
}

function isSelected(it) {
  const s = store.selected
  if (!s) return false
  if (s === it) return true
  if (s.id && it?.id && s.id === it.id) return true

  const sLib = String(s.library_id || s.libraryId || '')
  const sDoc = String(s.doc_id || s.docId || '')
  const sChunk = String(s.chunk_id || s.chunkId || '')
  const sSpan = String(s.span_index || s.spanIndex || '')

  const iLib = String(it?.library_id || it?.libraryId || '')
  const iDoc = String(it?.doc_id || it?.docId || '')
  const iChunk = String(it?.chunk_id || it?.chunkId || '')
  const iSpan = String(it?.span_index || it?.spanIndex || '')

  return sLib === iLib && sDoc === iDoc && sChunk === iChunk && sSpan === iSpan
}

function select(it) {
  store.selectItem(it)
}

function jump(it) {
  store.selectItem(it)
  store.jumpSelected()
}

function _scoreValue(it) {
  const r = Number(
    it?.relevance ??
    it?.similarity ??
    it?.score ??
    0
  )
  return Number.isFinite(r) ? r : 0
}

function formatScore(it) {
  const r = _scoreValue(it)
  if (!Number.isFinite(r)) return '—'
  if (r <= 1) return `${(r * 100).toFixed(1)}%`
  return `${r.toFixed(1)}%`
}

function _spanFromItem(it) {
  const candidates = [
    it?.span_index,
    it?.spanIndex,
    it?.span_id,
    it?.spanId,
    it?.start_span,
    it?.startSpan,
    it?.span_start,
    it?.spanStart
  ]

  for (const v of candidates) {
    const n = Number(v)
    if (Number.isFinite(n)) return n
  }
  return null
}

function displaySpan(it) {
  const v = _spanFromItem(it)
  return v === null || v === undefined ? '?' : v
}

function canJump(it) {
  const span = _spanFromItem(it)
  const lib = it?.library_id || it?.libraryId || activeLibraryId.value
  const doc = it?.doc_id || it?.docId || activeDocId.value
  return !!lib && !!doc && Number.isFinite(span)
}

function fullText(it) {
  return String(
    it?.text ??
    it?.quote ??
    it?.snippet ??
    it?.excerpt ??
    it?.content ??
    it?.chunk_text ??
    ''
  )
}

function previewText(it) {
  const text = fullText(it)
  if (!text) return t('library.center.searchPanel.noText')
  return text.length > 220 ? `${text.slice(0, 220)}…` : text
}

function hasExpandableText(it) {
  const text = fullText(it)
  return !!text && text.length > 220
}

async function copyToClipboard(text) {
  const value = String(text || '')
  if (!value.trim()) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {}

  try {
    const ta = document.createElement('textarea')
    ta.value = value
    ta.setAttribute('readonly', 'true')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return !!ok
  } catch {
    return false
  }
}

async function copyItem(it) {
  const ok = await copyToClipboard(fullText(it))
  toast(
    ok ? t('library.center.searchPanel.copiedToast') : t('library.center.searchPanel.copyFailedToast'),
    ok ? 'info' : 'error'
  )
}

function sendReaderControl(action, value = null) {
  if (!activeLibraryId.value || !activeDocId.value) return
  window.dispatchEvent(
    new CustomEvent('nisb-library-reader-control', {
      detail: { libraryId: activeLibraryId.value, docId: activeDocId.value, action, value }
    })
  )
}

function toggleContinuous() {
  if (!activeDocId.value) return
  sendReaderControl('toggle_continuous', !reader.value.continuous)
}

function toggleTranslation() {
  if (!activeDocId.value) return

  if (!reader.value.continuous) {
    sendReaderControl('toggle_continuous', true)
    setTimeout(() => sendReaderControl('toggle_translation', true), 0)
    return
  }

  sendReaderControl('toggle_translation', !reader.value.showTranslation)
}

function togglePretranslate() {
  if (!activeDocId.value) return

  if (!reader.value.continuous) {
    sendReaderControl('toggle_continuous', true)
    setTimeout(() => sendReaderControl('toggle_pretranslate', true), 0)
    return
  }

  sendReaderControl('toggle_pretranslate', !reader.value.smartPretranslate)
}

function toggleCompare() {
  if (!activeDocId.value) return

  const want = !reader.value.compareMode
  if (!want) {
    sendReaderControl('toggle_compare', false)
    return
  }

  if (!reader.value.continuous) sendReaderControl('toggle_continuous', true)

  setTimeout(() => {
    if (!reader.value.showTranslation) sendReaderControl('toggle_translation', true)
    setTimeout(() => sendReaderControl('toggle_compare', true), 0)
  }, 0)
}

function setPretranslateAhead() {
  sendReaderControl('set_pretranslate_ahead', Number(reader.value.pretranslateSpans || 2))
}

function cancelPretranslate() {
  sendReaderControl('cancel_pretranslate', true)
}

function resumePretranslate() {
  sendReaderControl('resume_pretranslate', true)
}

function setLang() {
  const lang = normalize_reader_lang(reader.value.lang || default_reader_lang_from_locale())
  reader.value.lang = lang
  save_reader_lang_pref(lang)
  sendReaderControl('set_lang', lang)
}

function onReaderState(evt) {
  const payload = evt?.detail || null
  if (!payload) return

  try {
    if (Object.prototype.hasOwnProperty.call(payload, 'libraryId')) _active_library_id.value = String(payload.libraryId || '')
    if (Object.prototype.hasOwnProperty.call(payload, 'docId')) _active_doc_id.value = String(payload.docId || '')
  } catch {}

  if (payload.libraryId && store.libraryId && payload.libraryId !== store.libraryId) return
  if (!activeDocId.value) return

  const r = payload.reader || {}
  const lang = normalize_reader_lang(r.lang || load_reader_lang_pref() || default_reader_lang_from_locale())

  reader.value = {
    continuous: !!r.continuous,
    showTranslation: !!r.showTranslation,
    compareMode: !!r.compareMode,
    smartPretranslate: !!r.smartPretranslate,
    pretranslateSpans: Number(r.pretranslateSpans || 2),
    lang
  }

  const p = payload.progress || {}
  progress.value = {
    total: Number(p.total || 0),
    translated: Number(p.translated || 0),
    refused: Number(p.refused || 0),
    queue: Number(p.queue || 0),
    running: Number(p.running || 0),
    paused: !!p.paused
  }
}

watch(
  () => locale.value,
  () => {
    if (load_reader_lang_pref()) return
    reader.value.lang = default_reader_lang_from_locale()
  }
)

onMounted(() => {
  window.addEventListener('nisb-reader-state-changed', onReaderState)
})

onUnmounted(() => {
  window.removeEventListener('nisb-reader-state-changed', onReaderState)
})

function emit_reader_chrome_search_lock(locked) {
  try {
    window.dispatchEvent(
      new CustomEvent('nisb-library-reader-chrome-search-lock', {
        detail: {
          libraryId: store.libraryId,
          locked: !!locked
        }
      })
    )
  } catch {}
}


function close_panel_and_release_reader_chrome() {
  emit_reader_chrome_search_lock(false)
  store.closePanel()
}

const reader_chrome_hidden = ref(false)

function on_reader_chrome_visibility(evt) {
  const detail = evt?.detail || {}
  const incomingLibraryId = String(detail.libraryId || '').trim()
  const activeLibraryId = String(store.libraryId || '').trim()

  if (incomingLibraryId && activeLibraryId && incomingLibraryId !== activeLibraryId) return

  reader_chrome_hidden.value = detail.visible === false
}

onMounted(() => {
  window.addEventListener('nisb-library-reader-chrome-visibility', on_reader_chrome_visibility)
})

onUnmounted(() => {
  window.removeEventListener('nisb-library-reader-chrome-visibility', on_reader_chrome_visibility)
  reader_chrome_hidden.value = false
})




watch(
  () => !!store.panelOpen,
  (open) => {
    emit_reader_chrome_search_lock(!!open)
  },
  { immediate: true }
)

</script>

<style scoped>
.panel {
  flex: 0 0 auto;
  min-width: 0;
  padding: 0.62rem 0.72rem 0.72rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  box-shadow:
    0 -1px 0 color-mix(in srgb, white 5%, transparent) inset,
    0 -12px 30px rgba(0, 0, 0, 0.04);
}

.collapsed {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.62rem;
  padding: 0.58rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  cursor: pointer;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 22px rgba(0, 0, 0, 0.045);
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.collapsed:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 12px 26px rgba(0, 0, 0, 0.06);
}

.collapsed-left {
  min-width: 0;
  display: grid;
  gap: 0.36rem;
}

.collapsed-line {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.58rem;
}

.collapsed-sub {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chips {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.chips::-webkit-scrollbar {
  display: none;
}

.reader-bar {
  min-width: 0;
  margin-bottom: 0.62rem;
  padding: 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 16px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 36%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 12px 26px rgba(0, 0, 0, 0.05);
}

.reader-controls {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.reader-controls::-webkit-scrollbar {
  display: none;
}

.search-area {
  min-width: 0;
  display: grid;
  gap: 0.5rem;
}

.search-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
}

.filters-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.filters-row::-webkit-scrollbar {
  display: none;
}

.seg {
  flex: 0 0 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  padding: 0.16rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

.seg-btn {
  min-height: 28px;
  box-sizing: border-box;
  padding: 0 0.58rem;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.seg-btn:hover,
.seg-btn:focus-visible {
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
  outline: none;
}

.seg-btn.active {
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 40%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--selected) 18%, transparent) inset,
    0 4px 10px rgba(0, 0, 0, 0.05);
}

.input {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0.48rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 64%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  line-height: 1.3;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.input::placeholder {
  color: var(--text-muted, var(--text-secondary));
}

.input:focus {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 84%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 62%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.06);
}

.btn,
.mini-icon,
.mini-btn,
.chip,
.select {
  font-family: inherit;
}

.btn {
  flex: 0 0 auto;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 50%, transparent)
    );
  color: var(--selected);
  cursor: pointer;
  font-size: 0.74rem;
  font-weight: 780;
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

.btn:hover:enabled,
.btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active:enabled {
  transform: translateY(1px);
}

.btn.subtle {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn.tiny {
  min-height: 30px;
  padding: 0 0.58rem;
  border-radius: 10px;
  font-size: 0.7rem;
}

.select {
  flex: 0 0 auto;
  min-height: 30px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 10px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1.2;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

.select:focus {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.06);
}

.select:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.select.tiny {
  min-width: 84px;
}

.chip {
  flex: 0 0 auto;
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.28rem;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  user-select: none;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.chip:hover,
.chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.chip:active {
  transform: translateY(1px);
}

.chip.on {
  border-color: color-mix(in srgb, #16a34a 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      rgba(22, 163, 74, 0.13),
      color-mix(in srgb, var(--selected-bg) 38%, transparent)
    );
  color: #16a34a;
}

.chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.chip.meta {
  cursor: default;
  border-color: color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
}

.chip.meta:hover {
  border-color: color-mix(in srgb, var(--line) 78%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.chip.icon {
  min-width: 32px;
  padding: 0 0.5rem;
  font-size: 0.78rem;
}

.collapse-btn {
  margin-left: auto;
}

.mini-icon {
  flex: 0 0 auto;
  width: 34px;
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.82rem;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.mini-icon:hover,
.mini-icon:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
  outline: none;
}

.mini-icon:active {
  transform: translateY(1px);
}

.msg {
  margin-top: 0.52rem;
  padding: 0.58rem 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 58%, transparent);
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.msg.error {
  border-color: color-mix(in srgb, #ef4444 38%, var(--line));
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.list {
  min-width: 0;
  max-height: min(40vh, 320px);
  margin-top: 0.62rem;
  padding-right: 0.16rem;
  display: grid;
  gap: 0.52rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.list::-webkit-scrollbar {
  width: 8px;
}

.list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.item {
  min-width: 0;
  padding: 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  cursor: pointer;
  box-shadow: 0 1px 0 color-mix(in srgb, white 5%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.item:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 24%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.055);
}

.item:active {
  transform: translateY(1px);
}

.item.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 9%, transparent), transparent 34%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
}

.meta {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 0.46rem;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.68rem;
  line-height: 1.35;
}

.score {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 0.42rem;
  border: 1px solid color-mix(in srgb, #16a34a 30%, var(--line));
  border-radius: 999px;
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
  font-variant-numeric: tabular-nums;
  font-weight: 760;
}

.text {
  min-width: 0;
  margin-top: 0.46rem;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  line-height: 1.48;
  opacity: 0.96;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.details {
  margin-top: 0.52rem;
}

.details summary {
  width: fit-content;
  max-width: 100%;
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
}

.details summary:hover {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.details-body {
  min-width: 0;
  margin-top: 0.46rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-main, var(--text));
  font-size: 0.76rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.actions {
  margin-top: 0.54rem;
  display: flex;
  align-items: center;
  gap: 0.46rem;
  flex-wrap: wrap;
}

.mini-btn {
  min-height: 28px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.7rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.mini-btn:hover:enabled,
.mini-btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.mini-btn:active:enabled {
  transform: translateY(1px);
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.muted {
  color: var(--text-secondary);
  opacity: 0.78;
}

.selectable {
  user-select: text;
}

@media (max-width: 720px) {
  .panel {
    padding: 0.54rem 0.58rem 0.62rem;
  }

  .search-row {
    grid-template-columns: 1fr;
  }

  .search-row .btn {
    width: 100%;
  }

  .reader-controls,
  .chips,
  .filters-row {
    gap: 0.36rem;
  }
}

@media (max-width: 460px) {
  .collapsed {
    grid-template-columns: 1fr;
  }

  .mini-icon {
    width: 100%;
  }

  .collapse-btn {
    margin-left: 0;
  }

  .reader-controls {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 2px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }

  .reader-controls .chip,
  .reader-controls .select,
  .reader-controls .btn {
    flex: 0 0 auto;
  }

  .chip.icon {
    flex: 0 0 auto;
  }
}



.library-search-panel.hidden_by_reader_chrome {
  max-height: 0 !important;
  min-height: 0 !important;
  height: 0 !important;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  border-width: 0 !important;
  opacity: 0;
  transform: translateY(16px);
  overflow: hidden !important;
  pointer-events: none;
}

.library-search-panel {
  transition:
    max-height 0.16s ease,
    height 0.16s ease,
    margin 0.16s ease,
    padding 0.16s ease,
    border-width 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

</style>

