<template>
  <div class="header" ref="header_ref">
    <div
      class="tab-group"
      ref="tab_group_ref"
      @mouseenter="on_tab_group_enter"
      @mouseleave="on_tab_group_leave"
      @mousemove="on_tab_group_mouse_move"
      @scroll="on_tab_group_scroll"
    >
      <div
        class="tab-list"
        role="tablist"
        :aria-label="tablist_label"
      >
        <button
          class="tab-btn"
          :class="{ active: active_tab === 'conversations' }"
          type="button"
          role="tab"
          :aria-selected="active_tab === 'conversations'"
          :title="t('sidebar.tabs.conversations')"
          @mouseenter="on_tab_mouse_enter('conversations')"
          @mouseleave="on_tab_mouse_leave"
          @click="switch_tab('conversations')"
        >
          <span class="tab-icon" aria-hidden="true">💬</span>
          <span class="tab-label">{{ t('sidebar.tabs.conversations') }}</span>
        </button>

        <button
          class="tab-btn"
          :class="{ active: active_tab === 'files' }"
          type="button"
          role="tab"
          :aria-selected="active_tab === 'files'"
          :title="t('sidebar.tabs.files')"
          @mouseenter="on_tab_mouse_enter('files')"
          @mouseleave="on_tab_mouse_leave"
          @click="switch_tab('files')"
        >
          <span class="tab-icon" aria-hidden="true">📁</span>
          <span class="tab-label">{{ t('sidebar.tabs.files') }}</span>
        </button>

        <button
          class="tab-btn"
          :class="{ active: active_tab === 'libraries' }"
          type="button"
          role="tab"
          :aria-selected="active_tab === 'libraries'"
          :title="t('sidebar.tabs.libraries')"
          @mouseenter="on_tab_mouse_enter('libraries')"
          @mouseleave="on_tab_mouse_leave"
          @click="switch_tab('libraries')"
        >
          <span class="tab-icon" aria-hidden="true">📚</span>
          <span class="tab-label">{{ t('sidebar.tabs.libraries') }}</span>
        </button>

        <button
          class="tab-btn"
          :class="{ active: active_tab === 'timeline' }"
          type="button"
          role="tab"
          :aria-selected="active_tab === 'timeline'"
          :title="t('sidebar.tabs.timeline')"
          @mouseenter="on_tab_mouse_enter('timeline')"
          @mouseleave="on_tab_mouse_leave"
          @click="switch_tab('timeline')"
        >
          <span class="tab-icon" aria-hidden="true">🕒</span>
          <span class="tab-label">{{ t('sidebar.tabs.timeline') }}</span>
        </button>

        <button
          class="tab-btn"
          :class="{ active: active_tab === 'rss' }"
          type="button"
          role="tab"
          :aria-selected="active_tab === 'rss'"
          :title="t('sidebar.tabs.rss')"
          @mouseenter="on_tab_mouse_enter('rss')"
          @mouseleave="on_tab_mouse_leave"
          @click="switch_tab('rss')"
        >
          <span class="tab-icon" aria-hidden="true">📰</span>
          <span class="tab-label">{{ t('sidebar.tabs.rss') }}</span>
        </button>
      </div>

      <button
        class="search-btn"
        type="button"
        @click="emit('open_search')"
        :title="t('sidebar.actions.search')"
        :aria-label="t('sidebar.actions.search')"
      >
        <span aria-hidden="true">🔍</span>
      </button>

      <button
        v-if="show_file_actions"
        class="upload-btn"
        type="button"
        @click="emit('trigger_upload')"
        :title="t('sidebar.actions.uploadFile')"
        :aria-label="t('sidebar.actions.uploadFile')"
      >
        <span aria-hidden="true">📤</span>
      </button>

      <button
        v-if="show_file_actions"
        class="upload-btn"
        type="button"
        @click="emit('trigger_dir_upload')"
        :title="t('sidebar.actions.uploadDirectory')"
        :aria-label="t('sidebar.actions.uploadDirectory')"
      >
        <span aria-hidden="true">📁⤴</span>
      </button>
    </div>

    <div class="header-actions">
      <button
        class="collapse-btn"
        type="button"
        @click="emit('collapse')"
        :title="t('sidebar.actions.collapse')"
        :aria-label="t('sidebar.actions.collapse')"
      >
        <span class="collapse-icon" aria-hidden="true">│</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useHoverScroll } from '../../composables/useHoverScroll'

const { t } = useI18n()

defineProps({
  active_tab: { type: String, required: true },
  show_file_actions: { type: Boolean, default: false }
})

const emit = defineEmits(['switch_tab', 'open_search', 'trigger_upload', 'trigger_dir_upload', 'collapse'])

const tablist_label = computed(() => {
  return [
    t('sidebar.tabs.conversations'),
    t('sidebar.tabs.files'),
    t('sidebar.tabs.libraries'),
    t('sidebar.tabs.timeline'),
    t('sidebar.tabs.rss')
  ].join(' / ')
})

const TAB_HOVER_DELAY_MS = 400

let tab_hover_timer = null

const header_ref = ref(null)
const tab_group_ref = ref(null)

function clear_tab_hover_timer() {
  if (tab_hover_timer) {
    clearTimeout(tab_hover_timer)
    tab_hover_timer = null
  }
}

function switch_tab(tab) {
  clear_tab_hover_timer()
  emit('switch_tab', tab)
}

function on_tab_mouse_enter(tab) {
  clear_tab_hover_timer()
  tab_hover_timer = setTimeout(() => {
    tab_hover_timer = null
    emit('switch_tab', tab)
  }, TAB_HOVER_DELAY_MS)
}

function on_tab_mouse_leave() {
  clear_tab_hover_timer()
}

const {
  onRowEnter: on_tab_group_enter,
  onRowLeave: on_tab_group_leave,
  onScroll: on_tab_group_scroll,
  onMouseMove: on_tab_group_mouse_move
} = useHoverScroll(tab_group_ref, { activeHeight: 10 })

onUnmounted(() => {
  clear_tab_hover_timer()
})
</script>

<style scoped>
.header {
  --nisb-sidebar-bar-height: 44px;
  --nisb-sidebar-control-height: 32px;
  --nisb-sidebar-radius: 12px;
  --nisb-sidebar-bg:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 34%, transparent)
    );
  --nisb-sidebar-bg-hover:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  --nisb-sidebar-bg-active:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 12%, transparent)
    );
  --nisb-sidebar-border: color-mix(in srgb, var(--line) 84%, transparent);
  --nisb-sidebar-border-hover: color-mix(in srgb, var(--selected) 28%, var(--line));
  --nisb-sidebar-border-active: color-mix(in srgb, var(--selected) 58%, var(--line));
  --nisb-sidebar-ring: color-mix(in srgb, var(--selected) 12%, transparent);

  position: relative;
  z-index: 40;
  width: 100%;
  min-width: 0;
  height: var(--nisb-sidebar-bar-height);
  min-height: var(--nisb-sidebar-bar-height);
  max-height: var(--nisb-sidebar-bar-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 70%, transparent)
    );
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow: hidden;
}

.header::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 20%, var(--line)),
      transparent
    );
  opacity: 0.68;
}

.tab-group {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 5px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.tab-group::-webkit-scrollbar {
  display: none;
}

.tab-list {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: max-content;
}

.tab-btn,
.search-btn,
.upload-btn,
.collapse-btn {
  box-sizing: border-box;
  border: 1px solid var(--nisb-sidebar-border);
  border-radius: var(--nisb-sidebar-radius);
  background: var(--nisb-sidebar-bg);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  line-height: 1;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 8%, transparent) inset,
    0 1px 2px rgba(0, 0, 0, 0.035);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.tab-btn:hover,
.tab-btn:focus-visible,
.search-btn:hover,
.search-btn:focus-visible,
.upload-btn:hover,
.upload-btn:focus-visible,
.collapse-btn:hover,
.collapse-btn:focus-visible {
  border-color: var(--nisb-sidebar-border-hover);
  background: var(--nisb-sidebar-bg-hover);
  color: var(--text-main, var(--text));
  box-shadow:
    0 0 0 2px var(--nisb-sidebar-ring),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.tab-btn:active,
.search-btn:active,
.upload-btn:active,
.collapse-btn:active {
  transform: translateY(1px);
}

.tab-btn {
  flex: 0 0 auto;
  min-width: max-content;
  max-width: none;
  min-height: var(--nisb-sidebar-control-height);
  height: var(--nisb-sidebar-control-height);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.38rem;
  padding: 0 0.66rem;
  font-size: 0.8rem;
  font-weight: 760;
  white-space: nowrap;
}

.tab-btn.active {
  border-color: var(--nisb-sidebar-border-active);
  background: var(--nisb-sidebar-bg-active);
  color: var(--selected);
  font-weight: 820;
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 24px rgba(0, 0, 0, 0.10);
}

.tab-icon,
.tab-label {
  flex: 0 0 auto;
  line-height: 1;
}

.tab-icon {
  font-size: 0.9rem;
}

.tab-label {
  max-width: 7.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-actions {
  position: relative;
  z-index: 45;
  flex: 0 0 auto;
  min-width: max-content;
  display: flex;
  align-items: center;
  gap: 5px;
}

.search-btn,
.upload-btn,
.collapse-btn {
  width: var(--nisb-sidebar-control-height);
  height: var(--nisb-sidebar-control-height);
  min-width: var(--nisb-sidebar-control-height);
  max-width: var(--nisb-sidebar-control-height);
  min-height: var(--nisb-sidebar-control-height);
  max-height: var(--nisb-sidebar-control-height);
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 0.9rem;
}

.collapse-icon {
  font-size: 15px;
  font-weight: 820;
  line-height: 1;
}

@media (max-width: 520px) {
  .header {
    padding: 6px;
  }

  .tab-group,
  .tab-list,
  .header-actions {
    gap: 4px;
  }

  .tab-btn {
    padding: 0 0.54rem;
  }

  .tab-label {
    max-width: 6.2rem;
  }
}

@media (max-width: 420px) {
  .tab-btn {
    gap: 0.3rem;
    padding: 0 0.48rem;
  }

  .tab-label {
    max-width: 5.4rem;
  }
}
</style>
