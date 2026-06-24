<template>
  <Teleport :to="teleportTarget" v-if="mounted && teleportTarget">
    <div
      v-if="btn.visible"
      class="sel-fab"
      :style="{ left: btn.x + 'px', top: btn.y + 'px' }"
    >
      <button
        class="fab-btn"
        type="button"
        :title="t('selectionTranslate.fab.title')"
        :aria-label="t('selectionTranslate.fab.title')"
        @pointerdown.stop.prevent="openModal"
      >
        {{ t('selectionTranslate.fab.label') }}
      </button>
    </div>

    <div
      v-if="modal.open"
      class="sel-modal-mask"
      :data-theme="theme"
      @click="closeModal"
    >
      <div
        class="sel-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="t('selectionTranslate.modal.title')"
        @click.stop
      >
        <div class="sel-modal-header">
          <div class="title-wrap">
            <div class="title">{{ t('selectionTranslate.modal.title') }}</div>
            <div class="version-chip">{{ t('selectionTranslate.modal.version') }}</div>
          </div>

          <button
            class="x"
            type="button"
            :title="t('selectionTranslate.modal.close')"
            :aria-label="t('selectionTranslate.modal.close')"
            @click="closeModal"
          >
            ×
          </button>
        </div>

        <div class="sel-modal-body">
          <section class="block">
            <div class="label">{{ t('selectionTranslate.source.label') }}</div>
            <div class="text">{{ modal.sourceText }}</div>

            <div v-if="modal.phonetics" class="phonetics">
              {{ modal.phonetics }}
            </div>

            <div class="row">
              <button
                class="mini-btn"
                type="button"
                :disabled="modal.phonLoading"
                @click="loadPhonetics"
              >
                {{
                  modal.phonLoading
                    ? t('selectionTranslate.actions.loadingPhonetics')
                    : t('selectionTranslate.actions.showPhonetics')
                }}
              </button>

              <button
                class="mini-btn"
                type="button"
                :disabled="modal.ttsLoading"
                @click="speakTextAndAutoPlay(modal.sourceText)"
              >
                {{
                  modal.ttsLoading
                    ? t('selectionTranslate.actions.generating')
                    : t('selectionTranslate.actions.speakSource')
                }}
              </button>

              <button class="mini-btn" type="button" @click="copySource">
                {{ t('selectionTranslate.actions.copySource') }}
              </button>
            </div>

            <audio
              v-if="modal.audioUrl"
              ref="audioRef"
              class="audio-player"
              :src="modal.audioUrl"
              controls
            />
          </section>

          <section class="block">
            <div class="row top-row">
              <div class="label label-tight">
                {{ t('selectionTranslate.translation.label') }}
              </div>

              <div class="lang-row">
                <span class="lang-label">{{ t('selectionTranslate.target.label') }}</span>
                <select
                  class="lang-select"
                  v-model="modal.targetLanguage"
                  :title="t('selectionTranslate.target.label')"
                  @change="handleTargetLanguageChange"
                >
                  <option v-for="opt in languageOptions" :key="opt.code" :value="opt.code">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
            </div>

            <div class="meta-row">
              <span v-if="modeHintText" class="mode-chip">{{ modeHintText }}</span>
              <span v-if="modal.cacheHit" class="cache-chip">
                {{ t('selectionTranslate.status.cacheHit') }}
              </span>
            </div>

            <div v-if="modal.loading" class="muted loading-line" aria-live="polite">
              {{ t('selectionTranslate.status.translating') }}
            </div>

            <div v-else>
              <div v-if="modal.dict.main" class="dict-main">
                <span class="dict-tag">{{ t('selectionTranslate.dict.meaning') }}</span>
                <span class="dict-text">{{ modal.dict.main }}</span>
              </div>

              <div v-if="modal.dict.examples && modal.dict.examples.length" class="dict-section">
                <div class="dict-tag dict-heading">
                  {{ t('selectionTranslate.dict.examples') }}
                </div>

                <ul class="dict-list">
                  <li v-for="(ex, idx) in modal.dict.examples" :key="idx" class="dict-li">
                    <div v-if="ex.src" class="dict-example-row">
                      <div class="dict-example-src">{{ ex.src }}</div>
                      <button
                        v-if="shouldShowExamplePlay(ex, 'src')"
                        class="pill-play"
                        type="button"
                        :disabled="modal.ttsLoading"
                        :title="t('selectionTranslate.actions.speakExample')"
                        :aria-label="t('selectionTranslate.actions.speakExample')"
                        @click="speakTextAndAutoPlay(ex.src)"
                      >
                        ▶
                      </button>
                    </div>

                    <div v-if="ex.trans" class="dict-example-row dict-example-trans-row">
                      <div class="dict-example-trans">{{ ex.trans }}</div>
                      <button
                        v-if="shouldShowExamplePlay(ex, 'trans')"
                        class="pill-play"
                        type="button"
                        :disabled="modal.ttsLoading"
                        :title="t('selectionTranslate.actions.speakExample')"
                        :aria-label="t('selectionTranslate.actions.speakExample')"
                        @click="speakTextAndAutoPlay(ex.trans)"
                      >
                        ▶
                      </button>
                    </div>
                  </li>
                </ul>
              </div>

              <div v-if="modal.dict.notes" class="dict-section">
                <div class="dict-tag dict-heading">
                  {{ t('selectionTranslate.dict.notes') }}
                </div>
                <div class="dict-text">{{ modal.dict.notes }}</div>
              </div>

              <div v-if="!modal.dict.main && modal.translatedText" class="text">
                {{ modal.translatedText }}
              </div>

              <div v-if="!hasTranslationOutput && !modal.loading" class="muted empty-line">
                {{ t('selectionTranslate.status.empty') }}
              </div>
            </div>

            <div class="row footer-row">
              <button
                class="mini-btn"
                type="button"
                :disabled="modal.loading || !hasTranslationOutput"
                @click="copyTranslated"
              >
                {{ t('selectionTranslate.actions.copyBoth') }}
              </button>

              <button
                class="mini-btn"
                type="button"
                :disabled="modal.loading"
                @click="translateNow(true)"
              >
                {{ t('selectionTranslate.actions.retranslate') }}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'

const { callTool } = useMCP()
const { t, locale } = useI18n({ useScope: 'global' })

const mounted = ref(false)
const teleportTarget = ref('')
const theme = ref('light')
const audioRef = ref(null)

let themeObserver = null
let selectionTimer = null
let onWindowMouseDown = null

const LONG_TEXT_THRESHOLD = 700
const MAX_SELECTION_CHARS = 12000
const TARGET_LANGUAGE_STORAGE_KEY = 'nisb_selection_translate_target_language_v1'

const SUPPORTED_LANGUAGE_CODES = [
  'zh-CN',
  'zh-TW',
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
]

const SUPPORTED_LANGUAGE_SET = new Set(SUPPORTED_LANGUAGE_CODES)

const languageOptions = computed(() =>
  SUPPORTED_LANGUAGE_CODES.map((code) => ({
    code,
    label: t(`selectionTranslate.languages.${code}`),
  }))
)

const modeHintText = computed(() => {
  if (modal.modeHintKey === 'chunks') return t('selectionTranslate.mode.chunks')
  if (modal.modeHintKey === 'dict') return t('selectionTranslate.mode.dict')
  return ''
})

const hasTranslationOutput = computed(() => {
  return !!(
    modal.translatedText ||
    modal.dict.main ||
    modal.dict.notes ||
    (Array.isArray(modal.dict.examples) && modal.dict.examples.length)
  )
})

const btn = reactive({
  visible: false,
  x: 0,
  y: 0,
  text: '',
})

const modal = reactive({
  open: false,
  loading: false,
  sourceText: '',
  translatedText: '',
  targetLanguage: resolveInitialTargetLanguage(),
  cacheHit: false,

  modeHintKey: '',

  ttsLoading: false,
  audioUrl: '',

  phonLoading: false,
  phonetics: '',

  dict: { main: '', examples: [], notes: '' },
})

function readCurrentLocale() {
  return String(locale?.value || locale || '').trim()
}

function defaultTargetLanguageFromLocale(value = readCurrentLocale()) {
  const current = String(value || '').trim().toLowerCase()
  if (current.startsWith('zh')) return 'zh-CN'
  if (current.startsWith('en')) return 'en'
  return 'en'
}

function readStoredTargetLanguage() {
  try {
    const value = String(localStorage.getItem(TARGET_LANGUAGE_STORAGE_KEY) || '').trim()
    return SUPPORTED_LANGUAGE_SET.has(value) ? value : ''
  } catch {
    return ''
  }
}

function persistTargetLanguage(value) {
  const normalized = SUPPORTED_LANGUAGE_SET.has(value) ? value : defaultTargetLanguageFromLocale()
  modal.targetLanguage = normalized
  try {
    localStorage.setItem(TARGET_LANGUAGE_STORAGE_KEY, normalized)
  } catch {}
}

function resolveInitialTargetLanguage() {
  return readStoredTargetLanguage() || defaultTargetLanguageFromLocale()
}

function resolveThemeTarget() {
  const app = document.querySelector('.app')
  if (app) return { target: '.app', node: app }

  const appRoot = document.querySelector('#app')
  if (appRoot) return { target: '#app', node: appRoot }

  return { target: 'body', node: document.documentElement }
}

function readThemeFromNode(node) {
  const value = node?.getAttribute?.('data-theme')
  return value === 'dark' ? 'dark' : 'light'
}

function normalizeTextForTranslate(value) {
  const text = String(value || '').replace(/\r\n/g, '\n')
  return text.trim().replace(/\n{3,}/g, '\n\n').slice(0, MAX_SELECTION_CHARS)
}

function getSelectionText() {
  const selection = window.getSelection()
  const text = String(selection?.toString?.() || '').trim()
  if (!text) return ''
  return text.length > MAX_SELECTION_CHARS ? text.slice(0, MAX_SELECTION_CHARS) : text
}

function updateButtonPosFromSelection() {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) return false

  const range = selection.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  if (!rect || (rect.width === 0 && rect.height === 0)) return false

  const margin = 10
  btn.x = Math.max(margin, Math.min(window.innerWidth - margin - 34, rect.right + 8))
  btn.y = Math.max(margin, Math.min(window.innerHeight - margin - 34, rect.top - 10))
  return true
}

function onSelectionChange() {
  if (selectionTimer) clearTimeout(selectionTimer)

  selectionTimer = setTimeout(() => {
    if (modal.open) return

    const text = getSelectionText()
    if (!text) {
      btn.visible = false
      btn.text = ''
      return
    }

    btn.text = text
    btn.visible = updateButtonPosFromSelection()
  }, 80)
}

async function copyText(text) {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return
    }
  } catch {}

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

function makeHashish(text) {
  const source = String(text || '')
  let hash = 2166136261

  for (let i = 0; i < source.length; i += 1) {
    hash ^= source.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }

  return (hash >>> 0).toString(16)
}

function cacheGet(key) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function cacheSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify({ ...value, _ts: Date.now() }))
    return true
  } catch {
    return false
  }
}

function resetModalForText(finalText) {
  modal.sourceText = finalText
  modal.translatedText = ''
  modal.cacheHit = false
  modal.audioUrl = ''
  modal.phonetics = ''
  modal.dict = { main: '', examples: [], notes: '' }
  modal.modeHintKey = ''
}

function openModal() {
  const live = getSelectionText()
  const finalText = normalizeTextForTranslate(live || btn.text)
  if (!finalText) return

  modal.targetLanguage = readStoredTargetLanguage() || defaultTargetLanguageFromLocale()
  modal.open = true
  resetModalForText(finalText)
  btn.visible = false
  translateNow(false)
}

function closeModal() {
  modal.open = false
  btn.visible = false
}

function shouldUseChunkTranslate(text) {
  const value = String(text || '').trim()
  if (!value) return false

  if (value.length >= LONG_TEXT_THRESHOLD) return true

  const paragraphCount = value.split(/\n{2,}/).filter(Boolean).length
  if (paragraphCount >= 2) return true

  const lineCount = value.split('\n').filter(Boolean).length
  if (lineCount >= 4) return true

  const sentencePunctuation = (value.match(/[.!?;\u3002\uff01\uff1f\uff1b]/g) || []).length
  if (sentencePunctuation >= 2) return true

  const commaPunctuation = (value.match(/[,;\uff0c\uff1b]/g) || []).length
  if (commaPunctuation >= 6) return true

  const maxLineLength = Math.max(...value.split('\n').map((line) => String(line || '').length))
  if (maxLineLength >= 180) return true

  return false
}

async function handleTargetLanguageChange() {
  persistTargetLanguage(modal.targetLanguage)
  await translateNow(false)
}

async function translateNow(force = false) {
  const text = normalizeTextForTranslate(modal.sourceText)
  if (!text) return

  modal.loading = true
  modal.cacheHit = false
  modal.dict = { main: '', examples: [], notes: '' }
  modal.modeHintKey = ''

  const lang = SUPPORTED_LANGUAGE_SET.has(modal.targetLanguage)
    ? modal.targetLanguage
    : defaultTargetLanguageFromLocale()

  modal.targetLanguage = lang

  const modeKey = shouldUseChunkTranslate(text) ? 'chunks' : 'dict'
  const hash = makeHashish(text)
  const key = `nisb_translate_v3:${modeKey}:${lang}:${hash}`

  if (!force) {
    const hit = cacheGet(key)
    if (hit && (typeof hit.translated_text === 'string' || hit.dict)) {
      modal.translatedText = hit.translated_text || ''
      modal.dict = hit.dict || { main: '', examples: [], notes: '' }
      modal.cacheHit = true
      modal.loading = false
      modal.modeHintKey = hit.mode_key || modeKey
      return
    }
  }

  try {
    modal.modeHintKey = modeKey

    if (modeKey === 'chunks') {
      const res = await callTool('nisb_util_translate_chunks', {
        text,
        target_language: lang,
        backend: 'mini',
        chunk_chars: 900,
        max_chars: MAX_SELECTION_CHARS,
      })

      if (res && res.status === 'success') {
        modal.translatedText = res.translated_text || ''
        modal.dict = { main: '', examples: [], notes: '' }

        cacheSet(key, {
          translated_text: modal.translatedText,
          dict: null,
          target_language: lang,
          mode_key: modeKey,
        })
      } else {
        throw new Error(res?.message || 'translate_chunks failed')
      }
    } else {
      const res = await callTool('nisb_util_translate', {
        text,
        target_language: lang,
        backend: 'mini',
        max_chars: 2000,
        mode: 'dictionary',
      })

      if (res && res.status === 'success') {
        modal.translatedText = res.translated_text || ''
        modal.dict = res.dict || { main: '', examples: [], notes: '' }

        cacheSet(key, {
          translated_text: modal.translatedText,
          dict: modal.dict,
          target_language: lang,
          mode_key: modeKey,
        })
      } else {
        throw new Error(res?.message || 'translate failed')
      }
    }
  } catch (error) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('selectionTranslate.toast.translateFailed', { error: formatError(error) }),
          type: 'error',
        },
      })
    )
  } finally {
    modal.loading = false
  }
}

async function loadPhonetics() {
  const text = modal.sourceText || ''
  if (!text.trim()) return

  if (!/[a-zA-Z]/.test(text)) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('selectionTranslate.toast.phoneticsEnglishOnly'), type: 'info' },
      })
    )
    return
  }

  modal.phonLoading = true

  try {
    const res = await callTool('nisb_util_phonetics', {
      text: text.slice(0, 200),
      max_chars: 200,
    })

    if (res && res.status === 'success') {
      modal.phonetics = res.phonetics || ''
    } else if (res && res.message === 'non_english_like_text') {
      window.dispatchEvent(
        new CustomEvent('nisb-toast', {
          detail: { message: t('selectionTranslate.toast.phoneticsNonEnglish'), type: 'info' },
        })
      )
    } else {
      throw new Error(res?.message || 'phonetics failed')
    }
  } catch (error) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('selectionTranslate.toast.phoneticsFailed', { error: formatError(error) }),
          type: 'error',
        },
      })
    )
  } finally {
    modal.phonLoading = false
  }
}

function isEnglishLike(value) {
  const text = String(value || '').trim()
  if (!text) return false
  if (!/[a-zA-Z]/.test(text)) return false

  const letters = (text.match(/[a-zA-Z]/g) || []).length
  return letters >= Math.min(6, text.length)
}

function detectPrimaryScript(value) {
  const text = String(value || '').trim()
  if (!text) return ''

  const counts = {
    cjk: (text.match(/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g) || []).length,
    kana: (text.match(/[\u3040-\u30ff]/g) || []).length,
    hangul: (text.match(/[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]/g) || []).length,
    arabic: (text.match(/[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/g) || []).length,
    cyrillic: (text.match(/[\u0400-\u04ff]/g) || []).length,
    latin: (text.match(/[A-Za-z]/g) || []).length,
  }

  let bestScript = ''
  let bestCount = 0

  Object.entries(counts).forEach(([script, count]) => {
    if (count > bestCount) {
      bestScript = script
      bestCount = count
    }
  })

  return bestCount > 0 ? bestScript : ''
}

function isSamePrimaryScript(value, script) {
  if (!script) return false
  return detectPrimaryScript(value) === script
}

function getExampleSpeakField(example) {
  const sourceScript = detectPrimaryScript(modal.sourceText)
  const targetLanguage = String(modal.targetLanguage || '').toLowerCase()

  if (sourceScript && sourceScript !== 'latin') {
    if (isSamePrimaryScript(example?.src, sourceScript)) return 'src'
    if (isSamePrimaryScript(example?.trans, sourceScript)) return 'trans'
    return ''
  }

  if (targetLanguage === 'en') {
    if (example?.trans && isEnglishLike(example.trans) && !isEnglishLike(example.src)) return 'trans'
    return ''
  }

  if (example?.src && isEnglishLike(example.src)) return 'src'
  if (example?.trans && isEnglishLike(example.trans)) return 'trans'

  return ''
}

function shouldShowExamplePlay(example, field) {
  const value = String(example?.[field] || '').trim()
  if (!value) return false
  return getExampleSpeakField(example) === field
}

async function speakTextAndAutoPlay(rawText) {
  const base = String(rawText || '').trim()
  if (!base) return

  modal.ttsLoading = true

  const text = normalizeTextForTranslate(base).slice(0, 1500)
  const hash = makeHashish(text)
  const format = 'mp3'
  const key = `nisb_tts_v1:${format}:${hash}`

  const hit = cacheGet(key)
  if (hit && typeof hit.audioUrl === 'string') {
    modal.audioUrl = hit.audioUrl
    modal.ttsLoading = false
    await nextTick()
    await tryAutoPlay()
    return
  }

  try {
    const res = await callTool('nisb_tts_speak', {
      text,
      format,
      max_chars: 1500,
    })

    if (res && res.status === 'success' && res.audio_base64) {
      modal.audioUrl = `data:audio/${res.format || 'mp3'};base64,${res.audio_base64}`
      cacheSet(key, { audioUrl: modal.audioUrl })
      await nextTick()
      await tryAutoPlay()
    } else {
      throw new Error(res?.message || 'TTS failed')
    }
  } catch (error) {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: {
          message: t('selectionTranslate.toast.ttsFailed', { error: formatError(error) }),
          type: 'error',
        },
      })
    )
  } finally {
    modal.ttsLoading = false
  }
}

async function tryAutoPlay() {
  try {
    const element = audioRef.value
    if (!element) return

    const result = element.play()
    if (result && typeof result.then === 'function') await result
  } catch {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: t('selectionTranslate.toast.autoplayBlocked'), type: 'info' },
      })
    )
  }
}

async function copySource() {
  await copyText(modal.sourceText || '')

  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message: t('selectionTranslate.toast.sourceCopied'), type: 'info' },
    })
  )
}

async function copyTranslated() {
  const parts = []

  if (modal.sourceText) {
    parts.push(t('selectionTranslate.copy.sourceLabel'))
    parts.push(modal.sourceText)
    parts.push('')
  }

  parts.push(t('selectionTranslate.copy.translationLabel'))

  if (modal.dict.main) parts.push(modal.dict.main)
  else if (modal.translatedText) parts.push(modal.translatedText)

  if (modal.dict.examples && modal.dict.examples.length) {
    parts.push('')
    parts.push(t('selectionTranslate.copy.examplesLabel'))

    modal.dict.examples.forEach((example) => {
      if (example.src) parts.push(example.src)
      if (example.trans) parts.push(example.trans)
      parts.push('')
    })
  }

  if (modal.dict.notes) {
    parts.push(t('selectionTranslate.copy.notesLabel'))
    parts.push(modal.dict.notes)
  }

  const fullText = parts.join('\n').trim()
  if (!fullText) return

  await copyText(fullText)

  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message: t('selectionTranslate.toast.translatedCopied'), type: 'info' },
    })
  )
}

function formatError(error) {
  return String(error?.message || error || t('common.unknownError'))
}

watch(locale, () => {
  if (readStoredTargetLanguage()) return
  modal.targetLanguage = defaultTargetLanguageFromLocale()
})

onMounted(async () => {
  await nextTick()
  mounted.value = true
  modal.targetLanguage = resolveInitialTargetLanguage()

  const { target, node } = resolveThemeTarget()
  teleportTarget.value = target

  theme.value = readThemeFromNode(node || document.documentElement)
  themeObserver = new MutationObserver(() => {
    theme.value = readThemeFromNode(node || document.documentElement)
  })
  themeObserver.observe(node || document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })

  document.addEventListener('selectionchange', onSelectionChange)
  window.addEventListener('scroll', onSelectionChange, true)
  window.addEventListener('resize', onSelectionChange)

  onWindowMouseDown = () => {
    if (!modal.open) btn.visible = false
  }

  window.addEventListener('mousedown', onWindowMouseDown)
})

onUnmounted(() => {
  document.removeEventListener('selectionchange', onSelectionChange)
  window.removeEventListener('scroll', onSelectionChange, true)
  window.removeEventListener('resize', onSelectionChange)

  if (onWindowMouseDown) window.removeEventListener('mousedown', onWindowMouseDown)
  if (selectionTimer) clearTimeout(selectionTimer)
  if (themeObserver) themeObserver.disconnect()
})
</script>

<style scoped>
.sel-fab {
  position: fixed;
  z-index: 20000;
}

.fab-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 999px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 90%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 12px 30px rgba(0, 0, 0, 0.16),
    0 1px 0 color-mix(in srgb, white 22%, transparent) inset;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 820;
  line-height: 1;
  backdrop-filter: blur(14px) saturate(145%);
  -webkit-backdrop-filter: blur(14px) saturate(145%);
  transition:
    transform 0.14s ease,
    background 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.fab-btn:hover,
.fab-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 66%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  box-shadow:
    0 16px 36px rgba(0, 0, 0, 0.2),
    0 0 0 3px color-mix(in srgb, var(--selected) 12%, transparent);
  outline: none;
  transform: translateY(-1px);
}

.sel-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 21000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background:
    radial-gradient(circle at 20% 16%, color-mix(in srgb, var(--selected) 13%, transparent), transparent 34%),
    rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(10px) saturate(115%);
  -webkit-backdrop-filter: blur(10px) saturate(115%);
}

.sel-modal {
  width: min(620px, calc(100vw - 28px));
  max-height: min(84vh, 760px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 84%, transparent)
    );
  color: var(--text-main);
  box-shadow:
    0 26px 70px rgba(0, 0, 0, 0.26),
    0 1px 0 color-mix(in srgb, white 18%, transparent) inset;
  backdrop-filter: blur(22px) saturate(142%);
  -webkit-backdrop-filter: blur(22px) saturate(142%);
}

.sel-modal-header {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.title-wrap {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.version-chip {
  min-height: 23px;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 0.16rem 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.x {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.x:hover,
.x:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, transparent);
  color: var(--text-main);
  outline: none;
}

.sel-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.block {
  min-width: 0;
  padding: 13px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 38%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 13%, transparent) inset,
    0 10px 28px rgba(0, 0, 0, 0.06);
}

.label {
  margin-bottom: 7px;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1.3;
}

.label-tight {
  margin: 0;
}

.text {
  max-width: 100%;
  color: var(--text-main);
  font-size: 0.92rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
  min-width: 0;
}

.top-row {
  justify-content: space-between;
  margin-top: 0;
}

.footer-row {
  align-items: center;
}

.mini-btn {
  min-height: 31px;
  max-width: 100%;
  padding: 0.38rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 62%, transparent)
    );
  color: var(--text-secondary);
  box-shadow: 0 1px 0 color-mix(in srgb, white 10%, transparent) inset;
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 760;
  line-height: 1.2;
  overflow-wrap: break-word;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.mini-btn:hover:enabled,
.mini-btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 20px rgba(0, 0, 0, 0.08);
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
  font-size: 0.82rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.loading-line,
.empty-line {
  margin-top: 10px;
}

.lang-row {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  min-width: 0;
}

.lang-label {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 760;
}

.lang-select {
  min-width: 138px;
  max-width: 220px;
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-main);
  font: inherit;
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1.2;
  padding: 0 0.5rem;
  outline: none;
}

.lang-select:focus {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 12%, transparent);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 9px;
  min-height: 24px;
}

.mode-chip,
.cache-chip {
  min-height: 23px;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 0.16rem 0.52rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1.2;
  overflow-wrap: break-word;
}

.mode-chip {
  border: 1px solid color-mix(in srgb, var(--selected) 20%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.cache-chip {
  border: 1px solid color-mix(in srgb, #16a34a 24%, var(--line));
  background: color-mix(in srgb, #16a34a 11%, transparent);
  color: color-mix(in srgb, #16a34a 76%, var(--text-main));
}

.audio-player {
  width: 100%;
  max-width: 100%;
  margin-top: 10px;
  display: block;
}

.phonetics {
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.dict-main {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 8px;
  min-width: 0;
}

.dict-section {
  margin-top: 11px;
  min-width: 0;
}

.dict-tag {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 780;
  line-height: 1.45;
}

.dict-heading {
  margin-bottom: 5px;
}

.dict-text {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.9rem;
  line-height: 1.58;
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

.dict-list {
  list-style: none;
  padding: 0;
  margin: 5px 0 0;
}

.dict-li {
  padding: 8px 0;
  border-top: 1px solid color-mix(in srgb, var(--line) 46%, transparent);
}

.dict-li:first-child {
  border-top: none;
  padding-top: 2px;
}

.dict-example-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.dict-example-src,
.dict-example-trans {
  min-width: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

.dict-example-src {
  flex: 1 1 auto;
  color: var(--text-secondary);
}

.dict-example-trans {
  margin-top: 3px;
  color: var(--text-main);
}

.dict-example-trans-row {
  margin-top: 3px;
}

.dict-example-trans-row .dict-example-trans {
  flex: 1 1 auto;
  margin-top: 0;
}

.pill-play {
  width: 28px;
  height: 24px;
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 64%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.72rem;
  line-height: 1;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.pill-play:hover:enabled,
.pill-play:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, transparent);
  color: var(--selected);
  outline: none;
}

.pill-play:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .sel-modal-mask {
    align-items: stretch;
    padding: 10px;
  }

  .sel-modal {
    width: 100%;
    max-height: calc(100dvh - 20px);
    border-radius: 18px;
  }

  .sel-modal-header {
    padding: 13px 13px 11px;
  }

  .sel-modal-body {
    padding: 12px;
  }

  .block {
    padding: 12px;
  }

  .top-row,
  .lang-row {
    align-items: stretch;
  }

  .top-row {
    flex-direction: column;
    gap: 8px;
  }

  .lang-row {
    width: 100%;
    justify-content: space-between;
  }

  .lang-select {
    flex: 1 1 auto;
    max-width: none;
  }

  .footer-row .mini-btn {
    flex: 1 1 100%;
  }
}

@media (max-width: 420px) {
  .row .mini-btn {
    flex: 1 1 100%;
  }

  .dict-main {
    flex-direction: column;
    gap: 4px;
  }

  .version-chip {
    width: 100%;
  }
}
</style>

