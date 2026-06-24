<template>
  <div class="app" :data-theme="theme">
    <ToastHost />
    <router-view />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import ToastHost from './components/ToastHost.vue'

const theme = ref('light')

function norm_theme(v) {
  const s = String(v || '').trim().toLowerCase()
  return s === 'dark' ? 'dark' : 'light'
}

function apply_theme_to_dom(t) {
  const v = norm_theme(t)

  // 1) .app（保持历史选择器可用）
  try {
    const appEl = document.querySelector('.app')
    if (appEl) appEl.setAttribute('data-theme', v)
  } catch {}

  // 2) <html>（:root 在 HTML 文档中对应 html）[web:155]
  try {
    const htmlEl = document.documentElement
    if (htmlEl) {
      htmlEl.setAttribute('data-theme', v)
      if (v === 'dark') htmlEl.classList.add('dark')
      else htmlEl.classList.remove('dark')
    }
  } catch {}

  // 3) <body>
  try {
    const bodyEl = document.body
    if (bodyEl) {
      bodyEl.setAttribute('data-theme', v)
      if (v === 'dark') bodyEl.classList.add('dark')
      else bodyEl.classList.remove('dark')
    }
  } catch {}
}

function set_theme(next, { persist = true } = {}) {
  const v = norm_theme(next)
  theme.value = v

  if (persist) {
    try {
      localStorage.setItem('nisb_theme', v)
    } catch {}
  }

  apply_theme_to_dom(v)

  // ✅ 广播：给右侧栏等同步图标状态（只用 snake_case 事件名）
  window.dispatchEvent(new CustomEvent('nisb_theme_applied', { detail: { theme: v } }))
}

function load_theme_initial() {
  try {
    const saved = String(localStorage.getItem('nisb_theme') || '').trim()
    if (saved) return norm_theme(saved)
  } catch {}

  const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  return isDark ? 'dark' : 'light'
}

function on_storage(e) {
  if (!e || e.key !== 'nisb_theme') return
  // 注意：storage 事件只在“其它 tab”触发，本 tab 改 localStorage 不会触发 [web:187]
  set_theme(e.newValue, { persist: false })
}

function on_theme_set(e) {
  const t = e?.detail?.theme
  set_theme(t, { persist: true })
}

function on_theme_toggle() {
  const next = theme.value === 'dark' ? 'light' : 'dark'
  set_theme(next, { persist: true })
}

onMounted(() => {
  set_theme(load_theme_initial(), { persist: false })

  window.addEventListener('storage', on_storage)
  window.addEventListener('nisb_theme_set', on_theme_set)
  window.addEventListener('nisb_theme_toggle', on_theme_toggle)
})

onUnmounted(() => {
  window.removeEventListener('storage', on_storage)
  window.removeEventListener('nisb_theme_set', on_theme_set)
  window.removeEventListener('nisb_theme_toggle', on_theme_toggle)
})
</script>

<style>
/* 全局基础：颜色继承 + 盒模型 */
*,
*::before,
*::after {
  box-sizing: border-box;
  color: inherit;
}

/* ===== Zen 风格基础变量（浅色） ===== */
:root {
  --font-main: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  --font-mono: "Monaco", "Menlo", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;

  --text-main: #141414;
  --text-secondary: #818181;
  --text-muted: #a0a0a0;

  --text-line-height: 1.6;
  --text-paragraph-gap: 0.8rem;
  --editor-max-width: 72ch;
  --editor-font-size: 0.95rem;

  --code-line-height: 1.6;

  --editor-bg: #eaeaea;
  --editor-card-bg: rgba(255, 255, 255, 0.86);
  --sidebar-bg: #f1f1f1;
  --sidebar-card-bg: rgba(255, 255, 255, 0.9);

  --glass-bg: rgba(248, 248, 248, 0.6);
  --glass-border: rgba(0, 0, 0, 0.06);
  --glass-shadow: 0 15px 20px rgba(0, 0, 0, 0.06);

  --sidebar-item-text: #818181;
  --sidebar-item-dot: #626262;

  --selected: #3c69bc;
  --selected-bg: #e8eaef;
  --btn-inactive-bg: #6e6e6e;
  --btn-active-text: #212121;
  --btn-active-bg: #f2f2f2;

  --line: #e3e3e3;

  --h1: #e74d47;
  --h2: #d79440;
  --h3: #07aaf6;
  --h4: #a36efb;
  --h5: #6dd7d7;
  --h6: #afbf05;

  --code-inline-bg-light: rgba(0, 0, 0, 0.04);
  --code-block-bg-light: rgba(0, 0, 0, 0.06);
  --blockquote-border: rgba(0, 0, 0, 0.2);
  --table-header-bg-light: rgba(0, 0, 0, 0.06);

  --icon-inactive: #8c8c8c;
  --icon-active: #4b4b4b;
}

/* ===== 深色模式变量（历史兼容：挂在 .app[data-theme="dark"] 上） ===== */
.app[data-theme="dark"] {
  --text-main: #e3e3e3;
  --text-secondary: #9e9e9e;
  --text-muted: #8a8a8a;

  --editor-bg: #151515;
  --editor-card-bg: rgba(28, 28, 28, 0.9);
  --sidebar-bg: #1c1c1c;
  --sidebar-card-bg: rgba(24, 24, 24, 0.96);

  --glass-bg: rgba(28, 28, 28, 0.7);
  --glass-border: rgba(255, 255, 255, 0.04);
  --glass-shadow: 0 15px 20px rgba(0, 0, 0, 0.4);

  --sidebar-item-text: #9e9e9e;
  --sidebar-item-dot: #777777;

  --selected: #5482c5;
  --selected-bg: #393a3a;
  --btn-inactive-bg: #3c3c3c;
  --btn-active-text: #d1d1d1;
  --btn-active-bg: #393a3a;

  --line: #333333;

  --h1: #e74d47;
  --h2: #d79440;
  --h3: #07aaf6;
  --h4: #a36efb;
  --h5: #6dd7d7;
  --h6: #afbf05;

  --code-inline-bg-light: rgba(255, 255, 255, 0.08);
  --code-block-bg-light: rgba(0, 0, 0, 0.45);
  --blockquote-border: rgba(245, 245, 245, 0.3);
  --table-header-bg-light: rgba(245, 245, 245, 0.08);

  --icon-inactive: #8c8c8c;
  --icon-active: #d1d1d1;
}

html,
body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
}

body {
  font-family: var(--font-main);
  color: var(--text-main);
  background: var(--editor-bg);
}

#app {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.app {
  width: 100%;
  height: 100vh;
  display: flex;
  background: var(--editor-bg);
  color: var(--text-main);
  transition: background-color 0.25s ease, color 0.25s ease;
}
</style>

