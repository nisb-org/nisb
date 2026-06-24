<template>
  <div class="recent-rooms-panel">
    <div v-if="loading" class="empty-block loading">
      <span class="empty-dot" aria-hidden="true" />
      <span>{{ t('chat.roomMenu.recent.loading') }}</span>
    </div>

    <div v-else-if="!items.length" class="empty-block">
      <span class="empty-icon" aria-hidden="true">∅</span>
      <span>{{ t('chat.roomMenu.recent.empty') }}</span>
    </div>

    <div v-else class="room-list">
      <div
        v-for="room in items"
        :key="room._menu_key || room.room_id"
        class="room-item"
        :class="{ active: is_active(room) }"
      >
        <div
          class="room-main"
          role="button"
          tabindex="0"
          @click="emit('enter', room)"
          @keydown.enter.prevent="emit('enter', room)"
          @keydown.space.prevent="emit('enter', room)"
        >
          <div class="room-name-row">
            <span class="room-name">{{ display_title(room) }}</span>

            <span v-if="is_active(room)" class="active-badge">
              {{ t('chat.roomMenu.recent.currentBadge') }}
            </span>

            <span v-if="room._room_kind === 'federated'" class="fed-badge">
              {{ federation_badge_text(room) }}
            </span>
          </div>

          <div class="room-meta">
            <span class="meta-chip">
              {{ t('chat.roomMenu.recent.id', { id: room.room_id }) }}
            </span>

            <span v-if="show_participants(room)" class="meta-chip">
              {{ t('chat.roomMenu.recent.participants', { count: normalized_participants_count(room) }) }}
            </span>

            <span v-if="room._room_kind === 'federated' && room.peer_id" class="meta-chip accent-subtle mono-chip">
              {{ t('chat.roomMenu.recent.peerLabel', { id: room.peer_id }) }}
            </span>
          </div>
        </div>

        <div class="room-item-actions">
          <button class="mini-btn" type="button" @click.stop="emit('enter', room)">
            {{ t('chat.roomMenu.actions.enter') }}
          </button>

          <button
            class="mini-btn"
            type="button"
            @click.stop="emit('copy-key', room.join_key || '')"
            :disabled="!room.join_key"
          >
            {{ t('chat.roomMenu.actions.copyKey') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  loading: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },
  activeRoomId: { type: String, default: '' },
})

const emit = defineEmits([
  'enter',
  'copy-key',
])

const { t } = useI18n()

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function normalized_participants_count(room) {
  const n = Number(room?.participants_count)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

function show_participants(room) {
  return safe_string(room?._room_kind) === 'local' || normalized_participants_count(room) > 0
}

function is_active(room) {
  const rid = safe_string(room?.room_id).trim()
  return !!rid && rid === safe_string(props.activeRoomId).trim()
}

function display_title(room) {
  return safe_string(room?.display_title || room?.title || room?.room_id).trim()
}

function federation_badge_text(room) {
  const label = safe_string(room?.remote_label || room?.peer_id || t('chat.roomMenu.recent.peerFallback')).trim()
  return t('chat.roomMenu.recent.federatedLabel', { label })
}
</script>

<style scoped>
.recent-rooms-panel {
  min-width: 0;
}

.room-list {
  min-width: 0;
  display: grid;
  gap: 0.52rem;
}

.room-item {
  min-width: 0;
  display: grid;
  gap: 0.56rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.14s ease;
}

.room-item:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 24%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.06);
}

.room-item.active {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 44%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.room-main {
  min-width: 0;
  display: grid;
  gap: 0.44rem;
  cursor: pointer;
  outline: none;
}

.room-main:focus-visible {
  border-radius: 11px;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent);
}

.room-name-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.room-name {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 790;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.room-item.active .room-name {
  color: var(--selected);
  font-weight: 840;
}

.active-badge,
.fed-badge,
.meta-chip {
  max-width: 100%;
  min-height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.active-badge {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 820;
}

.fed-badge,
.meta-chip.accent-subtle {
  border-color: color-mix(in srgb, #3b82f6 34%, var(--line));
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
  font-weight: 800;
}

.room-meta {
  min-width: 0;
  display: flex;
  gap: 0.34rem;
  flex-wrap: wrap;
}

.meta-chip {
  min-height: 21px;
  font-size: 0.67rem;
  font-weight: 730;
}

.mono-chip {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

.room-item-actions {
  min-width: 0;
  display: flex;
  gap: 0.42rem;
  flex-wrap: wrap;
}

.mini-btn {
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.mini-btn:hover:not(:disabled),
.mini-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.mini-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.empty-block {
  min-height: 74px;
  box-sizing: border-box;
  display: grid;
  place-items: center;
  gap: 0.34rem;
  padding: 0.82rem;
  border: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary);
  text-align: center;
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.empty-icon {
  width: 25px;
  height: 25px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 820;
  line-height: 1;
}

.empty-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 12%, transparent);
  animation: room-recent-pulse 1.15s ease-in-out infinite;
}

.empty-block.loading {
  color: var(--text-main, var(--text));
}

@keyframes room-recent-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }

  50% {
    opacity: 0.34;
    transform: scale(0.72);
  }
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .room-item-actions {
    align-items: stretch;
  }

  .mini-btn {
    flex: 1 1 auto;
  }
}

@media (max-width: 420px) {
  .room-item-actions {
    flex-direction: column;
  }

  .mini-btn {
    width: 100%;
  }
}
</style>
