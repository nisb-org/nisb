<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/Library/LibraryHeader.vue -->
<template>
  <div class="library-header" v-if="library">
    <!-- 左侧：返回按钮 + 库名 -->
    <div class="library-left">
      <button
        class="back-btn"
        type="button"
        @click="$emit('back-click')"
        :title="t('center.header.backTitle', {}, 'Back to main view (Esc)')"
      >
        {{ t('center.header.back', {}, '← Back') }}
      </button>

      <div class="library-title">
        <span class="library-icon" :style="{ color: library.color || '#3B82F6' }">
          {{ library.icon || '📚' }}
        </span>
        <div class="library-text">
          <div class="library-name">{{ library.library_name || library.library_id }}</div>
        </div>
      </div>
    </div>

    <!-- 右侧：上传按钮（桌面端）/ 汉堡菜单（移动端） -->
    <div class="library-right">
      <button
        v-if="reader_chrome_toggle_available"
        class="chrome-toggle-btn"
        type="button"
        @click="$emit('toggle-reader-chrome')"
        :title="
          reader_chrome_visible
            ? t('center.header.hideToolbarTitle', {}, 'Hide document toolbar')
            : t('center.header.showToolbarTitle', {}, 'Show document toolbar')
        "
      >
        {{
          reader_chrome_visible
            ? t('center.header.hideToolbar', {}, 'Hide toolbar')
            : t('center.header.showToolbar', {}, 'Show toolbar')
        }}
      </button>

      <button
        v-if="!isMobile"
        class="upload-btn"
        type="button"
        @click="$emit('upload-click')"
        :disabled="uploading"
        :title="t('center.header.uploadTitle', {}, 'Upload documents to this library (multiple files supported)')"
      >
        {{ uploading ? t('center.header.uploading', {}, '⏳ Uploading...') : t('center.header.upload', {}, '📤 Upload document') }}
      </button>

      <button
        v-if="isMobile"
        class="menu-btn"
        type="button"
        @click="$emit('menu-click')"
        :title="t('center.header.menuTitle', {}, 'Open menu')"
      >
        ☰
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useResponsive } from '../../../composables/useResponsive'
import enLibrary from '../../../locales/en/library'
import zhCNLibrary from '../../../locales/zh-CN/library'

defineProps({
  library: { type: Object, default: null },
  stats: { type: Object, default: null },
  uploading: { type: Boolean, default: false },
  reader_chrome_toggle_available: { type: Boolean, default: false },
  reader_chrome_visible: { type: Boolean, default: true }
})

defineEmits(['upload-click', 'back-click', 'menu-click', 'toggle-reader-chrome'])

const { isMobile } = useResponsive()

const LIBRARY_LOCALES = {
  en: enLibrary,
  'zh-CN': zhCNLibrary
}

function string_value(value) {
  return String(value ?? '').trim()
}

function normalize_locale(value) {
  const raw = string_value(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key)
      if (value !== null && string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function detect_locale() {
  const fromWindow = (() => {
    try {
      return (
        window?.__nisb_locale ||
        window?.__nisb_ui_locale ||
        window?.__NISB_LOCALE__ ||
        window?.__NISB_UI_LOCALE__ ||
        ''
      )
    } catch {
      return ''
    }
  })()

  const fromStorage = local_storage_first(
    [
      'nisb_locale',
      'nisb_ui_locale',
      'nisb_language',
      'nisb_settings_locale',
      'locale',
      'ui_locale',
      'language'
    ],
    ''
  )

  const fromDocument = (() => {
    try {
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  return normalize_locale(fromWindow || fromStorage || fromDocument || 'en')
}

const current_locale = computed(() => detect_locale())

function deep_get(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function t(path, params = {}, fallback = '') {
  const messages = LIBRARY_LOCALES[current_locale.value] || LIBRARY_LOCALES.en
  const value = deep_get(messages, path, deep_get(LIBRARY_LOCALES.en, path, fallback))
  return format_text(value || fallback || path, params)
}
</script>

<style scoped>
.library-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.6rem;
  gap: 0.75rem;
  min-width: 0;
}

.library-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
  flex: 1;
}

.back-btn {
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  white-space: nowrap;
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
  transform: translateX(-2px);
}

.library-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
}

.library-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.library-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.library-name {
  font-size: 1rem;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}

.library-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.upload-btn {
  padding: 0.5rem 0.85rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, var(--selected) 0%, rgba(60, 105, 188, 0.85) 100%);
  color: white;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all var(--transition-normal) var(--ease-smooth);
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(60, 105, 188, 0.25);
}

.upload-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(60, 105, 188, 0.35);
}

.upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.menu-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 1.2rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.chrome-toggle-btn {
  min-height: 38px;
  box-sizing: border-box;
  padding: 0 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.82rem;
  font-weight: 760;
  white-space: nowrap;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 1px 2px rgba(0, 0, 0, 0.035);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.chrome-toggle-btn:hover,
.chrome-toggle-btn:focus-visible {
  outline: none;
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.chrome-toggle-btn:active {
  transform: translateY(1px);
}

/* 移动端优化 */
@media (max-width: 768px) {
  .library-header {
    padding-bottom: 0.5rem;
  }

  .library-icon {
    font-size: 1.3rem;
  }

  .library-name {
    font-size: 0.95rem;
  }

  .back-btn {
    padding: 0.4rem 0.6rem;
    font-size: 0.8rem;
  }
}

@media (max-width: 720px) {
  .chrome-toggle-btn {
    display: none;
  }
}
</style>
