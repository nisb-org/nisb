// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/use_left_sidebar_context_menu.js
import { ref, computed } from 'vue'

function _norm_dir(v) {
  return String(v || '')
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/+$/, '')
}

function _to_number(v, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

export function use_left_sidebar_context_menu() {
  const context_menu = ref({
    visible: false,
    x: 0,
    y: 0,
    targetType: null,
    targetPath: null,
    baseDir: '',
    targetName: null,
    targetFileType: null,
    targetId: null,
    targetTitle: null,
    extensions: []
  })

  const visible_extensions = computed(() => {
    const exts = Array.isArray(context_menu.value.extensions) ? context_menu.value.extensions : []
    return exts.filter((e) => e && e.id && e.visible !== false)
  })

  async function show_context_menu(detail = {}) {
    const targetType = detail?.targetType || null
    const normalizedTargetPath = detail?.targetPath == null ? null : _norm_dir(detail.targetPath)
    const normalizedBaseDir = _norm_dir(detail?.baseDir || '')

    const effectiveTargetPath =
      normalizedTargetPath ||
      (targetType === 'create' ? normalizedBaseDir || null : null)

    context_menu.value = {
      visible: true,
      x: _to_number(detail?.x, 0),
      y: _to_number(detail?.y, 0),
      targetType,
      targetPath: effectiveTargetPath,
      baseDir: normalizedBaseDir,
      targetName: detail?.targetName || null,
      targetFileType: detail?.targetFileType || null,
      targetId: detail?.targetId || null,
      targetTitle: detail?.targetTitle || null,
      extensions: Array.isArray(detail?.extensions) ? detail.extensions : []
    }
  }

  function hide_context_menu() {
    context_menu.value.visible = false
  }

  return {
    context_menu,
    visible_extensions,
    show_context_menu,
    hide_context_menu
  }
}
