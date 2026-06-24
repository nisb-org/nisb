<template>
  <div class="role_form_block">
    <div class="form_surface">
      <div class="form_grid identity_grid">
        <label class="field">
          <span>{{ t('room.roleFormFields.fields.name.label') }}</span>
          <input
            v-model="form.name"
            type="text"
            :placeholder="t('room.roleFormFields.fields.name.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.slug.label') }}</span>
          <input
            v-model="form.slug"
            type="text"
            :placeholder="t('room.roleFormFields.fields.slug.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.avatar.label') }}</span>
          <input
            v-model="form.avatar"
            type="text"
            :placeholder="t('room.roleFormFields.fields.avatar.placeholder')"
          />
        </label>

        <label class="field checkbox_field">
          <span>{{ t('room.roleFormFields.fields.enabled.label') }}</span>
          <input v-model="form.enabled" type="checkbox" />
        </label>

        <label class="field field_full prompt_field">
          <span>{{ t('room.roleFormFields.fields.systemPrompt.label') }}</span>
          <textarea
            v-model="form.system_prompt"
            rows="4"
            :placeholder="t('room.roleFormFields.fields.systemPrompt.placeholder')"
          ></textarea>
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.libraryId.label') }}</span>
          <input
            v-model="form.library_id"
            type="text"
            :placeholder="t('room.roleFormFields.fields.libraryId.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.groupId.label') }}</span>
          <input
            v-model="form.group_id"
            type="text"
            :placeholder="t('room.roleFormFields.fields.groupId.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.docId.label') }}</span>
          <input
            v-model="form.doc_id"
            type="text"
            :placeholder="t('room.roleFormFields.fields.docId.placeholder')"
          />
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.storeScope.label') }}</span>
          <select v-model="form.store_scope">
            <option value="doc">{{ t('room.roleFormFields.scopeOptions.doc') }}</option>
            <option value="library">{{ t('room.roleFormFields.scopeOptions.library') }}</option>
            <option value="global">{{ t('room.roleFormFields.scopeOptions.global') }}</option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('room.roleFormFields.fields.evidenceScope.label') }}</span>
          <select v-model="form.evidence_scope">
            <option value="doc">{{ t('room.roleFormFields.scopeOptions.doc') }}</option>
            <option value="library">{{ t('room.roleFormFields.scopeOptions.library') }}</option>
            <option value="global">{{ t('room.roleFormFields.scopeOptions.global') }}</option>
          </select>
        </label>
      </div>
    </div>

    <div class="time_surface">
      <div class="field field_full time_block">
        <span>{{ t('room.roleFormFields.time.title') }}</span>
        <div class="time_hint">
          {{ t('room.roleFormFields.time.hintBefore') }}
          <code>time_filter_days</code>
          {{ t('room.roleFormFields.time.hintMiddle') }}
          <code>time_start / time_end</code>
          {{ t('room.roleFormFields.time.hintAfter') }}
        </div>
      </div>

      <div class="time_mode_switch">
        <button
          type="button"
          class="time_mode_chip"
          :class="{ active: timeUiMode === 'days' }"
          @click.stop="switchToDaysMode"
        >
          {{ t('room.roleFormFields.time.modeDays') }}
        </button>

        <button
          type="button"
          class="time_mode_chip"
          :class="{ active: timeUiMode === 'range' }"
          @click.stop="switchToRangeMode"
        >
          {{ t('room.roleFormFields.time.modeRange') }}
        </button>

        <button
          type="button"
          class="time_mode_chip danger"
          @click.stop="clearTimeRange"
        >
          {{ t('room.roleFormFields.time.clear') }}
        </button>
      </div>

      <div class="form_grid time_grid">
        <template v-if="timeUiMode === 'days'">
          <div class="field field_full">
            <span>{{ t('room.roleFormFields.time.quick') }}</span>
            <div class="time_chip_list">
              <button
                v-for="n in [1, 3, 7, 30]"
                :key="`days-${n}`"
                type="button"
                class="time_chip"
                :class="{ active: Number(form.time_filter_days) === n }"
                @click.stop="pickDocTimeDays(n)"
              >
                {{ t('room.roleFormFields.time.shortcutDays', { count: n }) }}
              </button>
            </div>
          </div>

          <label class="field">
            <span>{{ t('room.roleFormFields.time.timeFilterDays') }}</span>
            <input
              v-model.number="draftDocDays"
              type="number"
              min="1"
              max="3650"
              step="1"
              :placeholder="t('room.roleFormFields.time.timeFilterDaysPlaceholder')"
              @change="applyDocTimeDays"
              @blur="applyDocTimeDays"
            />
          </label>

          <div class="field">
            <span>{{ t('room.roleFormFields.time.descriptionLabel') }}</span>
            <div class="time_readonly_box">
              {{ t('room.roleFormFields.time.daysReadonlyBefore') }}
              <code>time_start</code>
              {{ t('room.roleFormFields.time.daysReadonlyMiddle') }}
              <code>time_end</code>
              {{ t('room.roleFormFields.time.daysReadonlyAfter') }}
            </div>
          </div>
        </template>

        <template v-else>
          <div class="field field_full">
            <span>{{ t('room.roleFormFields.time.relativeQuick') }}</span>
            <div class="time_chip_list">
              <button type="button" class="time_chip" @click.stop="setRelativePreset(14, 7)">
                {{ t('room.roleFormFields.time.relativePreset', { older: 14, newer: 7 }) }}
              </button>

              <button type="button" class="time_chip" @click.stop="setRelativePreset(21, 14)">
                {{ t('room.roleFormFields.time.relativePreset', { older: 21, newer: 14 }) }}
              </button>

              <button type="button" class="time_chip" @click.stop="setRelativePreset(30, 21)">
                {{ t('room.roleFormFields.time.relativePreset', { older: 30, newer: 21 }) }}
              </button>

              <button type="button" class="time_chip" @click.stop="setRelativePreset(60, 30)">
                {{ t('room.roleFormFields.time.relativePreset', { older: 60, newer: 30 }) }}
              </button>
            </div>
          </div>

          <label class="field">
            <span>{{ t('room.roleFormFields.time.olderDaysAgoLabel') }}</span>
            <input
              v-model.number="draftOlderDaysAgo"
              type="number"
              min="0"
              max="3650"
              step="1"
              :placeholder="t('room.roleFormFields.time.olderDaysAgoPlaceholder')"
              @change="applyRelativeDrafts"
              @blur="applyRelativeDrafts"
            />
          </label>

          <label class="field">
            <span>{{ t('room.roleFormFields.time.newerDaysAgoLabel') }}</span>
            <input
              v-model.number="draftNewerDaysAgo"
              type="number"
              min="0"
              max="3650"
              step="1"
              :placeholder="t('room.roleFormFields.time.newerDaysAgoPlaceholder')"
              @change="applyRelativeDrafts"
              @blur="applyRelativeDrafts"
            />
          </label>

          <label class="field">
            <span>{{ t('room.roleFormFields.time.timeStart') }}</span>
            <input
              v-model="form.time_start"
              type="text"
              :placeholder="t('room.roleFormFields.time.timeStartPlaceholder')"
            />
          </label>

          <label class="field">
            <span>{{ t('room.roleFormFields.time.timeEnd') }}</span>
            <input
              v-model="form.time_end"
              type="text"
              :placeholder="t('room.roleFormFields.time.timeEndPlaceholder')"
            />
          </label>
        </template>

        <div class="field field_full time_summary_block">
          <div class="time_summary">{{ timeSummary }}</div>
          <div class="time_hint">{{ timeEffectiveHint }}</div>
        </div>
      </div>
    </div>

    <div class="tool_policy">
      <div
        v-if="toolPolicyNotice"
        class="tool_policy_notice"
        role="status"
      >
        {{ toolPolicyNotice }}
      </div>

      <label
        v-for="key in effectiveToolPolicyKeys"
        :key="key"
        class="toggle_item"
        :class="{ pending: isPendingToolPolicy(key), active: Boolean(form.tool_policy?.[key]) }"
        :title="isPendingToolPolicy(key) ? t('room.roleFormFields.toolPolicy.pendingTitle') : ''"
      >
        <input
          :checked="Boolean(form.tool_policy?.[key])"
          type="checkbox"
          @change="handleToolPolicyChange(key, $event)"
        />
        <span>{{ toolPolicyLabel(key) }}</span>
        <small v-if="isPendingToolPolicy(key)" class="toggle_badge">
          {{ t('room.roleFormFields.toolPolicy.pendingBadge') }}
        </small>
      </label>
    </div>

    <RoomRoleProviderBindingPanel
      :form="form"
      :provider-options="providerOptions"
      :resolved-workspace="resolvedWorkspace"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomRoleFormTime } from '../../../composables/editor/room/use_room_role_form_time'
import RoomRoleProviderBindingPanel from './RoomRoleProviderBindingPanel.vue'

const props = defineProps({
  form: { type: Object, required: true },
  toolPolicyKeys: { type: Array, default: () => [] },
  providerOptions: { type: Array, default: () => [] },
  resolvedWorkspace: { type: Object, default: () => ({}) },
})

const { t } = useI18n()

const FALLBACK_TOOL_POLICY_KEYS = ['rag', 'web', 'mcp', 'code', 'fs_read', 'fs_write']

const PENDING_TOOL_POLICY_KEYS = new Set(['web', 'code', 'fs_read', 'fs_write'])

const toolPolicyNotice = ref('')
let toolPolicyNoticeTimer = null

const effectiveToolPolicyKeys = computed(() => {
  return Array.isArray(props.toolPolicyKeys) && props.toolPolicyKeys.length
    ? props.toolPolicyKeys
    : FALLBACK_TOOL_POLICY_KEYS
})

function safeString(value, defaultValue = '') {
  if (value == null) return defaultValue
  const out = String(value).trim()
  return out || defaultValue
}

function toolPolicyLabel(key) {
  const normalized = safeString(key)
  const map = {
    rag: t('room.roleFormFields.toolPolicy.labels.rag'),
    web: t('room.roleFormFields.toolPolicy.labels.web'),
    mcp: t('room.roleFormFields.toolPolicy.labels.mcp'),
    code: t('room.roleFormFields.toolPolicy.labels.code'),
    fs_read: t('room.roleFormFields.toolPolicy.labels.fsRead'),
    fs_write: t('room.roleFormFields.toolPolicy.labels.fsWrite'),
  }
  return map[normalized] || normalized
}

function ensureToolPolicy() {
  if (!props.form.tool_policy || typeof props.form.tool_policy !== 'object') {
    props.form.tool_policy = {}
  }
  return props.form.tool_policy
}

function isPendingToolPolicy(key) {
  return PENDING_TOOL_POLICY_KEYS.has(safeString(key))
}

function showToolPolicyNotice(key) {
  const feature = toolPolicyLabel(key)
  toolPolicyNotice.value = t('room.roleFormFields.toolPolicy.pendingNotice', { feature })

  if (toolPolicyNoticeTimer) {
    clearTimeout(toolPolicyNoticeTimer)
  }

  toolPolicyNoticeTimer = window.setTimeout(() => {
    toolPolicyNotice.value = ''
    toolPolicyNoticeTimer = null
  }, 2600)
}

function handleToolPolicyChange(key, event) {
  const normalized = safeString(key)
  const toolPolicy = ensureToolPolicy()

  if (isPendingToolPolicy(normalized)) {
    toolPolicy[normalized] = false
    if (event?.target) {
      event.target.checked = false
    }
    showToolPolicyNotice(normalized)
    return
  }

  toolPolicy[normalized] = Boolean(event?.target?.checked)
}

watchEffect(() => {
  const toolPolicy = props.form?.tool_policy
  if (!toolPolicy || typeof toolPolicy !== 'object') return

  PENDING_TOOL_POLICY_KEYS.forEach((key) => {
    if (toolPolicy[key]) {
      toolPolicy[key] = false
    }
  })
})

onBeforeUnmount(() => {
  if (toolPolicyNoticeTimer) {
    clearTimeout(toolPolicyNoticeTimer)
  }
})

const {
  timeUiMode,
  draftDocDays,
  draftOlderDaysAgo,
  draftNewerDaysAgo,
  switchToDaysMode,
  switchToRangeMode,
  clearTimeRange,
  pickDocTimeDays,
  applyDocTimeDays,
  setRelativePreset,
  applyRelativeDrafts,
  timeSummary,
  timeEffectiveHint,
} = useRoomRoleFormTime(props.form, t)
</script>

<style scoped>
.role_form_block {
  display: grid;
  gap: 12px;
  margin-top: 12px;
  min-width: 0;
}

.form_surface,
.time_surface,
.tool_policy {
  min-width: 0;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.form_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 11px;
  min-width: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field > span {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
}

.field input,
.field textarea,
.field select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main);
  padding: 10px 11px;
  font-family: inherit;
  font-size: 0.83rem;
  line-height: 1.45;
  outline: none;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.field textarea {
  min-height: 104px;
  resize: vertical;
}

.field select {
  cursor: pointer;
}

.field input::placeholder,
.field textarea::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.field input:focus,
.field textarea:focus,
.field select:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent);
}

.prompt_field textarea {
  min-height: 118px;
}

.field_full {
  grid-column: 1 / -1;
}

.checkbox_field {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 41px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
}

.checkbox_field input {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
  margin: 0;
  padding: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.time_surface {
  border-color: color-mix(in srgb, var(--selected) 16%, var(--line));
}

.time_block {
  gap: 4px;
  margin-bottom: 10px;
}

.time_hint {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.time_hint code,
.time_readonly_box code {
  font-family: var(--font-mono);
  color: var(--text-main);
  overflow-wrap: anywhere;
}

.time_mode_switch {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 11px;
}

.time_mode_chip,
.time_chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.time_mode_chip:hover,
.time_chip:hover {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 58%, var(--editor-bg));
  color: var(--selected);
}

.time_mode_chip:active,
.time_chip:active {
  transform: translateY(1px);
}

.time_mode_chip.active,
.time_chip.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 70%, transparent);
  color: var(--selected);
}

.time_mode_chip.danger:hover {
  border-color: rgba(239, 68, 68, 0.38);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.time_chip_list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.time_summary_block {
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
}

.time_summary {
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 680;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.time_readonly_box {
  min-height: 42px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  border: 1px dashed var(--line);
  border-radius: 11px;
  padding: 10px 11px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.tool_policy {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tool_policy_notice {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(245, 158, 11, 0.34);
  border-radius: 12px;
  padding: 9px 11px;
  background: rgba(245, 158, 11, 0.09);
  color: #d97706;
  font-size: 0.8rem;
  line-height: 1.5;
}

.toggle_item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 31px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1;
  cursor: pointer;
  user-select: none;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease;
}

.toggle_item:hover {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
}

.toggle_item.active {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
}

.toggle_item.pending {
  border-style: dashed;
  opacity: 0.82;
}

.toggle_item input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.toggle_badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 18px;
  padding: 0 6px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1;
}

@media (max-width: 860px) {
  .form_grid {
    grid-template-columns: 1fr;
  }

  .time_mode_switch,
  .time_chip_list {
    flex-direction: row;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .role_form_block {
    gap: 10px;
  }

  .form_surface,
  .time_surface,
  .tool_policy {
    padding: 12px;
    border-radius: 14px;
  }

  .time_mode_switch,
  .time_chip_list {
    width: 100%;
  }

  .time_mode_chip,
  .time_chip {
    flex: 1 1 auto;
    min-width: 0;
  }

  .tool_policy {
    align-items: stretch;
  }

  .toggle_item {
    flex: 1 1 auto;
    justify-content: center;
    min-width: 0;
  }
}

@media (max-width: 420px) {
  .time_mode_chip,
  .time_chip,
  .toggle_item {
    width: 100%;
    flex-basis: 100%;
  }

  .checkbox_field {
    align-items: flex-start;
  }

  .time_mode_chip,
  .time_chip {
    white-space: normal;
    line-height: 1.25;
    padding-top: 6px;
    padding-bottom: 6px;
  }
}
</style>
