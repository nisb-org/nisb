<template>
  <Teleport to="body">
    <div
      ref="mask_el"
      class="zen-modal-mask"
      data-nisb-modal="library-export-translated"
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
          <div class="title">{{ modal_title }}</div>
          <button class="icon-btn" :title="t('library.center.exportTranslatedModal.close')" @click="on_cancel" :disabled="submitting">✕</button>
        </div>

        <div class="zen-modal-body">
          <div class="row" v-if="can_export_single_doc || can_export_library_batch">
            <div class="label">{{ t('library.center.exportTranslatedModal.scope') }}</div>
            <div class="inline-options">
              <label v-if="can_export_single_doc" class="check-row">
                <input type="radio" v-model="export_scope" value="single_doc" />
                <span>{{ t('library.center.exportTranslatedModal.scopeSingle') }}</span>
              </label>

              <label v-if="can_export_library_batch" class="check-row">
                <input type="radio" v-model="export_scope" value="library_batch" />
                <span>{{ t('library.center.exportTranslatedModal.scopeBatch', { count: library_doc_count }) }}</span>
              </label>
            </div>
          </div>

          <template v-if="export_scope === 'single_doc'">
            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.currentDocument') }}</div>
              <div class="path mono">{{ doc?.filename || doc?.doc_id || '' }}</div>
            </div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.documentId') }}</div>
              <div class="path mono">{{ doc?.doc_id || '' }}</div>
            </div>
          </template>

          <template v-else>
            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.currentLibrary') }}</div>
              <div class="path mono">{{ library?.library_name || library_id }}</div>
            </div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.documentCount') }}</div>
              <div class="path mono">{{ library_doc_count }}</div>
            </div>
          </template>

          <div class="row">
            <div class="label">{{ t('library.center.exportTranslatedModal.exportFormat') }}</div>
            <div class="inline-options">
              <label class="check-row">
                <input type="radio" v-model="export_format" value="md" />
                <span>{{ t('library.center.exportTranslatedModal.formatMarkdown') }}</span>
              </label>
              <label class="check-row">
                <input type="radio" v-model="export_format" value="pdf" />
                <span>{{ t('library.center.exportTranslatedModal.formatPdf') }}</span>
              </label>
            </div>
          </div>

          <div class="input-row">
            <div class="label">{{ t('library.center.exportTranslatedModal.targetLanguage') }}</div>
            <div class="input-wrap">
              <input
                v-model.trim="target_language"
                class="name-input mono"
                :placeholder="t('library.center.exportTranslatedModal.targetLanguagePlaceholder')"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
          </div>

          <div v-if="export_scope === 'single_doc'" class="input-row">
            <div class="label">{{ t('library.center.exportTranslatedModal.exportFilename') }}</div>
            <div class="input-wrap">
              <input
                v-model.trim="export_filename"
                class="name-input mono"
                :placeholder="default_export_filename"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
          </div>

          <div class="row">
            <div class="label">{{ t('library.center.exportTranslatedModal.exportMethod') }}</div>
            <div class="stack-options">
              <label class="check-row">
                <input type="checkbox" v-model="save_to_nisb" />
                <span>{{ t('library.center.exportTranslatedModal.saveToNisb') }}</span>
              </label>

              <label class="check-row">
                <input type="checkbox" v-model="download_to_local" />
                <span>
                  {{
                    export_scope === 'library_batch'
                      ? t('library.center.exportTranslatedModal.downloadToLocalBatch')
                      : t('library.center.exportTranslatedModal.downloadToLocal')
                  }}
                </span>
              </label>

              <label class="check-row">
                <input type="checkbox" v-model="include_untranslated" />
                <span>{{ t('library.center.exportTranslatedModal.includeUntranslated') }}</span>
              </label>
            </div>
          </div>

          <div v-if="export_scope === 'library_batch' && download_to_local" class="hint-inline">
            {{ t('library.center.exportTranslatedModal.batchDownloadHint') }}
          </div>

          <template v-if="save_to_nisb">
            <div class="path-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.destinationDirectory') }}</div>

              <div class="crumb-box">
                <div class="crumb-multiline">
                  <button class="crumb-btn" @click.stop="set_dest_dir('')" :title="t('library.center.exportTranslatedModal.rootPathTitle')">user</button>
                  <span class="crumb-sep">/</span>

                  <template v-if="dest_segments.length">
                    <template v-for="seg in dest_segments" :key="seg.path">
                      <button
                        class="crumb-btn"
                        @click.stop="set_dest_dir(seg.path)"
                        :title="crumb_title(seg.path)"
                      >
                        {{ seg.name }}
                      </button>
                      <span class="crumb-sep">/</span>
                    </template>
                  </template>

                  <button
                    v-if="can_choose_child_dir && dest_has_child_dirs"
                    class="crumb-child-inline-btn"
                    :class="{ active: dest_child_panel_open }"
                    :title="t('library.center.exportTranslatedModal.chooseChildDirectory')"
                    @click.stop="toggle_dest_child_panel"
                  >
                    ▾
                  </button>
                </div>
              </div>
            </div>

            <div v-if="dest_child_panel_open" class="child-panel">
              <div class="child-panel-header">
                <div class="child-panel-title">{{ t('library.center.exportTranslatedModal.childDirectories') }}</div>
                <button class="child-panel-close" :title="t('library.center.exportTranslatedModal.collapse')" @click.stop="dest_child_panel_open = false">✕</button>
              </div>

              <div class="child-panel-body">
                <div v-if="dest_child_loading" class="child-empty">{{ t('library.center.exportTranslatedModal.loadingInline') }}</div>

                <template v-else>
                  <div v-if="!dest_child_dirs.length" class="child-empty">{{ t('library.center.exportTranslatedModal.noChildDirectories') }}</div>

                  <button
                    v-for="d in dest_child_dirs"
                    :key="d.path"
                    class="child-item"
                    @click.stop="pick_dest_child_dir(d)"
                    :title="crumb_title(d.path)"
                  >
                    <span class="child-icon">📁</span>
                    <span class="child-name">{{ d.name }}</span>
                  </button>
                </template>
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.directoryPath') }}</div>

              <div class="input-wrap">
                <div class="prefix mono">user/</div>
                <input
                  ref="dest_input_el"
                  v-model="dest_dir_text"
                  class="name-input mono"
                  :placeholder="dest_input_placeholder"
                  @keydown.enter.prevent="on_confirm"
                  @keydown.esc.prevent="on_cancel"
                  autocomplete="off"
                  spellcheck="false"
                />
              </div>
            </div>
          </template>

          <template v-if="export_format === 'pdf'">
            <div class="section-divider"></div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.layout') }}</div>
              <div class="inline-options">
                <label class="check-row">
                  <input type="radio" v-model="pdf_layout_mode" value="auto" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.layoutAuto') }}</span>
                </label>
                <label class="check-row">
                  <input type="radio" v-model="pdf_layout_mode" value="cjk_chars" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.layoutCjkChars') }}</span>
                </label>
                <label class="check-row">
                  <input type="radio" v-model="pdf_layout_mode" value="en_words" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.layoutEnWords') }}</span>
                </label>
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.lineCharsCjk') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_line_chars_cjk"
                  class="name-input mono"
                  type="number"
                  min="8"
                  max="60"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.lineCharsCjkPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.lineWordsEn') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_line_words_en"
                  class="name-input mono"
                  type="number"
                  min="3"
                  max="20"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.lineWordsEnPlaceholder')"
                />
              </div>
            </div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.widthStrategy') }}</div>
              <div class="stack-options">
                <label class="check-row">
                  <input type="checkbox" v-model="pdf_auto_fit_page_width" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.autoFitPageWidth') }}</span>
                </label>
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.pageWidthMm') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_page_width_mm"
                  class="name-input mono"
                  type="number"
                  min="55"
                  max="210"
                  :disabled="pdf_auto_fit_page_width"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.autoPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.pageHeightMm') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_page_height_mm"
                  class="name-input mono"
                  type="number"
                  min="100"
                  max="297"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.pageHeightPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.marginLeftRightMm') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_margin_left_right_mm"
                  class="name-input mono"
                  type="number"
                  min="1"
                  max="40"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.marginLeftRightPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.marginTopBottomMm') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_margin_top_bottom_mm"
                  class="name-input mono"
                  type="number"
                  min="2"
                  max="40"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.marginTopBottomPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.fontSizePt') }}</div>
              <div class="input-wrap">
                <input
                  v-model.number="pdf_font_size_pt"
                  class="name-input mono"
                  type="number"
                  min="8"
                  max="28"
                  step="0.1"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.autoPlaceholder')"
                />
              </div>
            </div>

            <div class="input-row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.fontPath') }}</div>
              <div class="input-wrap">
                <input
                  v-model.trim="pdf_font_path"
                  class="name-input mono"
                  :placeholder="t('library.center.exportTranslatedModal.pdf.fontPathPlaceholder')"
                  autocomplete="off"
                  spellcheck="false"
                />
              </div>
            </div>

            <div class="section-divider"></div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.pageStyle') }}</div>
              <div class="stack-options">
                <label class="check-row">
                  <input type="checkbox" v-model="pdf_enable_page_background" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.enablePageBackground') }}</span>
                </label>

                <label class="check-row">
                  <input type="checkbox" v-model="pdf_enable_header_decoration" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.enableHeaderDecoration') }}</span>
                </label>

                <label class="check-row">
                  <input type="checkbox" v-model="pdf_enable_paragraph_spacing" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.enableParagraphSpacing') }}</span>
                </label>

                <label class="check-row">
                  <input type="checkbox" v-model="pdf_enable_annotation_card_style" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.enableAnnotationCardStyle') }}</span>
                </label>
              </div>
            </div>

            <div class="section-divider"></div>

            <div class="row">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.exportAnnotations') }}</div>
              <div class="stack-options">
                <label class="check-row">
                  <input type="checkbox" v-model="pdf_include_span_annotations" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.includeSpanAnnotations') }}</span>
                </label>
              </div>
            </div>

            <div class="row" v-if="pdf_include_span_annotations">
              <div class="label">{{ t('library.center.exportTranslatedModal.pdf.annotationStyle') }}</div>
              <div class="stack-options">
                <label class="check-row">
                  <input type="radio" v-model="pdf_annotation_style" value="below_card" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.annotationStyleBelowCard') }}</span>
                </label>

                <label class="check-row">
                  <input type="radio" v-model="pdf_annotation_style" value="endnotes" />
                  <span>{{ t('library.center.exportTranslatedModal.pdf.annotationStyleEndnotes') }}</span>
                </label>
              </div>
            </div>

            <div v-if="pdf_include_span_annotations" class="annotation-preview">
              <div class="annotation-preview-title">{{ t('library.center.exportTranslatedModal.pdf.previewTitle') }}</div>

              <template v-if="pdf_annotation_style === 'below_card'">
                <div class="annotation-demo-text">{{ t('library.center.exportTranslatedModal.pdf.previewText') }}</div>
                <div class="annotation-demo-card">
                  <div class="annotation-demo-bar"></div>
                  <div class="annotation-demo-main">
                    <div class="annotation-demo-head">{{ t('library.center.exportTranslatedModal.pdf.previewCardHead') }}</div>
                    <div class="annotation-demo-body">{{ t('library.center.exportTranslatedModal.pdf.previewCardBody1') }}</div>
                    <div class="annotation-demo-body">{{ t('library.center.exportTranslatedModal.pdf.previewCardBody2') }}</div>
                  </div>
                </div>
              </template>

              <template v-else>
                <div class="annotation-demo-text">{{ t('library.center.exportTranslatedModal.pdf.previewEndnotesText') }}</div>
                <div class="annotation-demo-endnotes">
                  <div class="annotation-demo-head">{{ t('library.center.exportTranslatedModal.pdf.previewArchiveTitle') }}</div>
                  <div class="annotation-demo-body">{{ t('library.center.exportTranslatedModal.pdf.previewArchiveBody1') }}</div>
                  <div class="annotation-demo-body">{{ t('library.center.exportTranslatedModal.pdf.previewArchiveBody2') }}</div>
                </div>
              </template>
            </div>
          </template>

          <div class="hint">
            {{ t('library.center.exportTranslatedModal.footerHint') }}
          </div>
        </div>

        <div class="zen-modal-footer">
          <button class="btn" @click="on_cancel" :disabled="submitting">{{ t('library.center.exportTranslatedModal.cancel') }}</button>
          <button class="btn primary" :disabled="!can_confirm || submitting" @click="on_confirm">
            {{ submitting ? t('library.center.exportTranslatedModal.exporting') : t('library.center.exportTranslatedModal.startExport') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const modal_style_text = `
  background: var(--editor-bg) !important;
  color: var(--text) !important;
  border-color: var(--line) !important;
`

const props = defineProps({
  library_id: { type: String, required: true },
  library: { type: Object, default: null },
  doc: { type: Object, default: null },
  documents: { type: Array, default: () => [] },
  call_tool: { type: Function, default: null },
  submitting: { type: Boolean, default: false },
  initial_scope: { type: String, default: 'single_doc' }
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

function _is_dir_type(t0) {
  const s = String(t0 || '').toLowerCase()
  return s === 'directory' || s === 'dir' || s === 'folder'
}

function _to_segments(dir_text) {
  const p = _norm_dir(dir_text || '')
  if (!p) return []
  const parts = p.split('/').filter(Boolean)
  const segs = []
  let acc = ''
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part
    segs.push({ name: part, path: acc })
  }
  return segs
}

function crumb_title(path) {
  const p = _norm_dir(path || '')
  return p ? `user/${p}/` : 'user/'
}

const library_doc_count = computed(() => {
  return Array.isArray(props.documents) ? props.documents.filter((d) => d && d.doc_id).length : 0
})

const can_export_single_doc = computed(() => {
  return !!props.doc?.doc_id
})

const can_export_library_batch = computed(() => {
  return library_doc_count.value > 0
})

function resolve_initial_scope() {
  const requested = String(props.initial_scope || 'single_doc').trim()
  if (requested === 'library_batch' && can_export_library_batch.value) return 'library_batch'
  if (requested === 'single_doc' && can_export_single_doc.value) return 'single_doc'
  if (can_export_single_doc.value) return 'single_doc'
  if (can_export_library_batch.value) return 'library_batch'
  return 'single_doc'
}

const export_scope = ref(resolve_initial_scope())
const export_format = ref('md')
const target_language = ref('zh-CN')
const export_filename = ref('')
const save_to_nisb = ref(true)
const download_to_local = ref(true)
const include_untranslated = ref(false)

const pdf_layout_mode = ref('auto')
const pdf_line_chars_cjk = ref(20)
const pdf_line_words_en = ref(8)
const pdf_auto_fit_page_width = ref(true)
const pdf_page_width_mm = ref(null)
const pdf_page_height_mm = ref(170)
const pdf_margin_left_right_mm = ref(4)
const pdf_margin_top_bottom_mm = ref(6)
const pdf_font_size_pt = ref(null)
const pdf_font_path = ref('')

const pdf_include_span_annotations = ref(false)
const pdf_annotation_style = ref('below_card')

const pdf_enable_page_background = ref(true)
const pdf_enable_header_decoration = ref(true)
const pdf_enable_paragraph_spacing = ref(true)
const pdf_enable_annotation_card_style = ref(true)

const modal_title = computed(() => {
  return export_scope.value === 'library_batch'
    ? t('library.center.exportTranslatedModal.titleBatch')
    : t('library.center.exportTranslatedModal.titleSingle')
})

function build_default_export_dir(scope) {
  if (scope === 'library_batch') {
    return _norm_dir(`agent_files/library_translated_exports/${props.library_id}`)
  }
  return _norm_dir(`agent_files/library_translated_exports/${props.library_id}/${props.doc?.doc_id || ''}`)
}

const default_export_dir_value = computed(() => {
  return build_default_export_dir(export_scope.value)
})

const default_export_filename = computed(() => {
  const raw = String(props.doc?.filename || props.doc?.doc_id || t('library.center.exportTranslatedModal.defaultDocumentName')).trim()
  const idx = raw.lastIndexOf('.')
  const base = idx > 0 ? raw.slice(0, idx) : raw
  const ext = export_format.value === 'pdf' ? '.pdf' : '.md'
  return `${base || t('library.center.exportTranslatedModal.defaultDocumentName')}_${t('library.center.exportTranslatedModal.defaultFilenameSuffix')}_${target_language.value || 'zh-CN'}${ext}`
})

const dest_input_placeholder = computed(() => {
  if (export_scope.value === 'library_batch') {
    return t('library.center.exportTranslatedModal.directoryPlaceholderBatch')
  }
  return t('library.center.exportTranslatedModal.directoryPlaceholderSingle')
})

const can_choose_child_dir = computed(() => typeof props.call_tool === 'function')

const dest_dir_text = ref(default_export_dir_value.value)

const dest_dir_display = computed(() => _norm_dir(dest_dir_text.value || ''))
const dest_segments = computed(() => _to_segments(dest_dir_display.value))
const dest_dir_trimmed = computed(() => _trim(dest_dir_display.value || ''))

const can_confirm = computed(() => {
  if (export_scope.value === 'single_doc' && !can_export_single_doc.value) return false
  if (export_scope.value === 'library_batch' && !can_export_library_batch.value) return false
  if (download_to_local.value) return true
  if (save_to_nisb.value && dest_dir_trimmed.value) return true
  return false
})

watch(
  () => props.initial_scope,
  () => {
    export_scope.value = resolve_initial_scope()
  }
)

watch(
  [can_export_single_doc, can_export_library_batch],
  () => {
    export_scope.value = resolve_initial_scope()
  }
)

watch(
  () => export_scope.value,
  async () => {
    if (save_to_nisb.value) {
      dest_dir_text.value = default_export_dir_value.value
    }
    dest_child_panel_open.value = false
    await ensure_dest_child_dirs_loaded()
  }
)

watch(
  () => save_to_nisb.value,
  async () => {
    if (save_to_nisb.value && !dest_dir_trimmed.value) {
      dest_dir_text.value = default_export_dir_value.value
    }
    dest_child_panel_open.value = false
    await ensure_dest_child_dirs_loaded()
  }
)

watch(
  () => export_format.value,
  () => {
    if (export_format.value !== 'pdf') {
      pdf_include_span_annotations.value = false
      pdf_annotation_style.value = 'below_card'
    }
  }
)

const dest_child_panel_open = ref(false)
const dest_child_loading = ref(false)
const dest_child_dirs = ref([])
const dest_child_loaded_key = ref('')

const dest_has_child_dirs = computed(() => {
  if (!can_choose_child_dir.value) return false
  if (dest_child_loaded_key.value !== dest_dir_display.value) return false
  return Array.isArray(dest_child_dirs.value) && dest_child_dirs.value.length > 0
})

async function _load_child_dirs(for_base_dir) {
  if (typeof props.call_tool !== 'function') return []
  const r = await props.call_tool('nisb_dir_list', { path: for_base_dir || '' })
  const list = r && r.success && Array.isArray(r.entries) ? r.entries : []
  return list
    .filter((e) => e && _is_dir_type(e.type))
    .filter((e) => !String(e.name || '').startsWith('.'))
    .map((e) => {
      const p = for_base_dir ? `${for_base_dir}/${e.name}` : e.name
      return { name: e.name, path: p }
    })
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
}

async function ensure_dest_child_dirs_loaded() {
  const key = dest_dir_display.value
  if (dest_child_loaded_key.value === key) return

  if (!can_choose_child_dir.value || !save_to_nisb.value) {
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
  dest_dir_text.value = _norm_dir(p || '')
  dest_child_panel_open.value = false
  await ensure_dest_child_dirs_loaded()
  await nextTick()
  try {
    dest_input_el.value?.focus?.()
  } catch (_e) {}
}

async function toggle_dest_child_panel() {
  if (!can_choose_child_dir.value || !save_to_nisb.value) return
  await ensure_dest_child_dirs_loaded()
  dest_child_panel_open.value = !dest_child_panel_open.value
}

async function pick_dest_child_dir(d) {
  const p = _norm_dir(d?.path || '')
  if (!p) return
  dest_dir_text.value = p
  dest_child_panel_open.value = false
  await ensure_dest_child_dirs_loaded()
  await nextTick()
  try {
    dest_input_el.value?.focus?.()
  } catch (_e) {}
}

function on_confirm() {
  if (!can_confirm.value || props.submitting) return

  emit('confirm', {
    export_scope: export_scope.value,
    export_format: export_format.value,
    target_language: _trim(target_language.value || 'zh-CN') || 'zh-CN',
    export_filename: export_scope.value === 'single_doc' ? _trim(export_filename.value || '') : '',
    save_to_nisb: !!save_to_nisb.value,
    download_to_local: !!download_to_local.value,
    include_untranslated: !!include_untranslated.value,
    export_user_dir: save_to_nisb.value ? dest_dir_trimmed.value : '',
    pdf_layout_mode: pdf_layout_mode.value || 'auto',
    pdf_line_chars_cjk: Number(pdf_line_chars_cjk.value || 20),
    pdf_line_words_en: Number(pdf_line_words_en.value || 8),
    pdf_auto_fit_page_width: !!pdf_auto_fit_page_width.value,
    pdf_page_width_mm: pdf_auto_fit_page_width.value ? null : Number(pdf_page_width_mm.value || 0),
    pdf_page_height_mm: Number(pdf_page_height_mm.value || 170),
    pdf_margin_left_right_mm: Number(pdf_margin_left_right_mm.value || 4),
    pdf_margin_top_bottom_mm: Number(pdf_margin_top_bottom_mm.value || 6),
    pdf_font_size_pt:
      pdf_font_size_pt.value == null || pdf_font_size_pt.value === ''
        ? null
        : Number(pdf_font_size_pt.value),
    pdf_font_path: _trim(pdf_font_path.value || ''),
    pdf_include_span_annotations: export_format.value === 'pdf' ? !!pdf_include_span_annotations.value : false,
    pdf_annotation_style: export_format.value === 'pdf' ? (pdf_annotation_style.value || 'below_card') : 'below_card',
    pdf_enable_page_background: export_format.value === 'pdf' ? !!pdf_enable_page_background.value : true,
    pdf_enable_header_decoration: export_format.value === 'pdf' ? !!pdf_enable_header_decoration.value : true,
    pdf_enable_paragraph_spacing: export_format.value === 'pdf' ? !!pdf_enable_paragraph_spacing.value : true,
    pdf_enable_annotation_card_style: export_format.value === 'pdf' ? !!pdf_enable_annotation_card_style.value : true
  })
}

function on_cancel() {
  if (props.submitting) return
  emit('cancel')
}

const mask_el = ref(null)
const theme_src_el = ref(null)
const dest_input_el = ref(null)

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
        count += 1
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
:global([data-nisb-modal="library-export-translated"]) {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 2147483647 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-sizing: border-box !important;
  padding: 18px !important;
  isolation: isolate !important;
  background:
    radial-gradient(circle at 18% 12%, color-mix(in srgb, var(--selected) 16%, transparent), transparent 34%),
    radial-gradient(circle at 82% 88%, rgba(15, 23, 42, 0.28), transparent 38%),
    rgba(0, 0, 0, 0.46) !important;
  backdrop-filter: blur(16px) saturate(1.08) !important;
  -webkit-backdrop-filter: blur(16px) saturate(1.08) !important;
}

.zen-modal {
  width: min(820px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  min-height: 0;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 88%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 9%, transparent) inset,
    0 24px 70px rgba(0, 0, 0, 0.38);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.zen-modal-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.76rem;
  padding: 0.88rem 0.92rem 0.76rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.title {
  min-width: 0;
  color: var(--text);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.28;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-btn {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.icon-btn:hover:enabled,
.icon-btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.icon-btn:active:enabled {
  transform: translateY(1px);
}

.icon-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.zen-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 0.88rem 0.92rem;
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.zen-modal-body::-webkit-scrollbar,
.child-panel-body::-webkit-scrollbar {
  width: 8px;
}

.zen-modal-body::-webkit-scrollbar-thumb,
.child-panel-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.row,
.path-row,
.input-row {
  min-width: 0;
  display: grid;
  grid-template-columns: 122px minmax(0, 1fr);
  gap: 0.68rem;
}

.row {
  align-items: center;
}

.path-row,
.input-row {
  align-items: start;
}

.label {
  min-width: 0;
  padding-top: 0.42rem;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 740;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.path {
  min-width: 0;
  padding: 0.55rem 0.64rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 52%, transparent)
    );
  color: var(--text);
  font-size: 0.74rem;
  line-height: 1.42;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inline-options {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.52rem;
  flex-wrap: wrap;
}

.stack-options {
  min-width: 0;
  display: grid;
  gap: 0.48rem;
}

.check-row {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.48rem;
  color: var(--text);
  font-size: 0.78rem;
  line-height: 1.42;
  overflow-wrap: break-word;
}

.check-row input {
  flex: 0 0 auto;
  accent-color: var(--selected);
}

.hint-inline,
.hint {
  min-width: 0;
  padding: 0.56rem 0.66rem;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 26%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.hint {
  opacity: 0.9;
}

.crumb-box {
  min-width: 0;
  padding: 0.56rem 0.64rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 50%, transparent)
    );
}

.crumb-multiline {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.28rem 0.24rem;
  color: var(--text-secondary);
  line-height: 1.32;
  overflow-wrap: anywhere;
}

.crumb-btn {
  min-width: 0;
  max-width: 100%;
  padding: 0.08rem 0.18rem;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: anywhere;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.crumb-btn:hover,
.crumb-btn:focus-visible {
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  outline: none;
}

.crumb-sep {
  color: var(--text-secondary);
  opacity: 0.62;
  user-select: none;
}

.crumb-child-inline-btn {
  flex: 0 0 auto;
  width: 24px;
  height: 22px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 8px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  font-size: 0.76rem;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.crumb-child-inline-btn:hover,
.crumb-child-inline-btn:focus-visible,
.crumb-child-inline-btn.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent);
  outline: none;
}

.child-panel {
  min-width: 0;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 15px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 36%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 58%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 10px 22px rgba(0, 0, 0, 0.045);
}

.child-panel-header {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.56rem;
  padding: 0.1rem 0.12rem 0.46rem;
}

.child-panel-title {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 820;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.child-panel-close {
  flex: 0 0 auto;
  width: 28px;
  height: 26px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 9px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.child-panel-close:hover,
.child-panel-close:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  outline: none;
}

.child-panel-body {
  max-height: 190px;
  padding: 0.12rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.child-empty {
  padding: 0.72rem;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.child-item {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  padding: 0.52rem 0.58rem;
  border: 1px solid transparent;
  border-radius: 11px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.12s ease;
}

.child-item:hover,
.child-item:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 36%, transparent);
  color: var(--selected);
  outline: none;
}

.child-item:active {
  transform: translateY(1px);
}

.child-icon {
  flex: 0 0 auto;
}

.child-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-wrap {
  min-width: 0;
  display: flex;
  align-items: stretch;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 70%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 56%, transparent)
    );
  overflow: hidden;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.input-wrap:focus-within {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 82%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 58%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.06);
}

.prefix {
  flex: 0 0 auto;
  padding: 0.62rem 0.64rem;
  border-right: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.3;
  opacity: 0.86;
  background: color-mix(in srgb, var(--sidebar-bg) 34%, transparent);
}

.name-input {
  flex: 1 1 auto;
  min-width: 0;
  width: 100%;
  padding: 0.62rem 0.64rem;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: 0.78rem;
  line-height: 1.35;
}

.name-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.72;
}

.name-input:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.section-divider {
  height: 1px;
  margin: 0.12rem 0;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--line) 86%, transparent),
      transparent
    );
}

.annotation-preview {
  min-width: 0;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, #d97706 26%, var(--line));
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, rgba(217, 119, 6, 0.1), transparent 36%),
    linear-gradient(
      135deg,
      rgba(217, 119, 6, 0.06),
      color-mix(in srgb, var(--editor-bg) 62%, transparent)
    );
  display: flex;
  flex-direction: column;
  gap: 0.56rem;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.annotation-preview-title {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 820;
  line-height: 1.3;
}

.annotation-demo-text {
  color: var(--text);
  font-size: 0.78rem;
  line-height: 1.62;
  overflow-wrap: break-word;
}

.annotation-demo-card {
  min-width: 0;
  margin-left: 1rem;
  display: flex;
  align-items: stretch;
  border: 1px solid rgba(217, 119, 6, 0.22);
  border-radius: 13px;
  overflow: hidden;
  background:
    linear-gradient(
      135deg,
      rgba(255, 247, 237, 0.74),
      rgba(254, 243, 199, 0.54)
    );
}

.annotation-demo-bar {
  flex: 0 0 auto;
  width: 4px;
  background: #d97706;
}

.annotation-demo-main {
  min-width: 0;
  padding: 0.62rem 0.66rem;
  display: flex;
  flex-direction: column;
  gap: 0.38rem;
}

.annotation-demo-head {
  color: color-mix(in srgb, var(--text) 86%, #92400e);
  font-size: 0.74rem;
  font-weight: 820;
  line-height: 1.3;
  overflow-wrap: break-word;
}

.annotation-demo-body {
  color: color-mix(in srgb, var(--text-secondary) 86%, #92400e);
  font-size: 0.74rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.annotation-demo-endnotes {
  min-width: 0;
  padding: 0.66rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  display: flex;
  flex-direction: column;
  gap: 0.38rem;
}

.zen-modal-footer {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  gap: 0.52rem;
  padding: 0.76rem 0.92rem 0.88rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 44%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow: 0 -1px 0 color-mix(in srgb, white 5%, transparent) inset;
}

.btn {
  flex: 0 0 auto;
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
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

.btn:hover:enabled,
.btn:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 40%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active:enabled {
  transform: translateY(1px);
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 78%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
  color: var(--selected);
}

.btn.primary:hover:enabled,
.btn.primary:focus-visible:enabled {
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 30%, transparent)
    );
}

.btn.primary:disabled,
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  :global([data-nisb-modal="library-export-translated"]) {
    align-items: stretch !important;
    padding: 10px !important;
  }

  .zen-modal {
    width: 100%;
    max-height: calc(100vh - 20px);
    border-radius: 16px;
  }

  .row,
  .path-row,
  .input-row {
    grid-template-columns: 1fr;
    gap: 0.38rem;
  }

  .label {
    padding-top: 0;
  }

  .inline-options {
    gap: 0.44rem;
  }

  .path {
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .annotation-demo-card {
    margin-left: 0;
  }
}

@media (max-width: 460px) {
  :global([data-nisb-modal="library-export-translated"]) {
    padding: 0 !important;
  }

  .zen-modal {
    width: 100%;
    max-height: 100vh;
    border-radius: 0;
    border-left: 0;
    border-right: 0;
  }

  .zen-modal-header {
    padding: 0.78rem 0.78rem 0.68rem;
  }

  .zen-modal-body {
    padding: 0.72rem;
    gap: 0.62rem;
  }

  .zen-modal-footer {
    padding: 0.68rem 0.72rem 0.78rem;
    display: grid;
    grid-template-columns: 1fr;
  }

  .btn {
    width: 100%;
  }

  .inline-options {
    align-items: stretch;
    display: grid;
    grid-template-columns: 1fr;
  }

  .check-row {
    width: 100%;
  }

  .prefix {
    max-width: 42%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
