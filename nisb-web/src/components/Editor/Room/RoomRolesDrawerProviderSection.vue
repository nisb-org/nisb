<template>
  <div class="provider_section_stack">
    <section class="section_card workspace_card">
      <div class="section_head">
        <div>
          <div class="section_title">
            {{ t('room.rolesDrawer.sections.currentWorkspace') }}
          </div>
          <div class="section_subtitle">
            {{ t('room.rolesDrawer.providerSection.workspace.subtitle') }}
          </div>
        </div>
      </div>

      <div class="binding_card">
        <div class="binding_line">
          <span class="label_inline">{{ t('room.rolesDrawer.workspaceFields.workspaceId') }}</span>
          <span class="binding_value">{{ resolvedWorkspace.workspace_id || t('room.rolesDrawer.common.dash') }}</span>
        </div>

        <div class="binding_line">
          <span class="label_inline">{{ t('room.rolesDrawer.workspaceFields.workspaceName') }}</span>
          <span class="binding_value">{{ resolvedWorkspace.workspace_name || t('room.rolesDrawer.common.dash') }}</span>
        </div>

        <div class="binding_line">
          <span class="label_inline">{{ t('room.rolesDrawer.workspaceFields.focusRoot') }}</span>
          <span class="binding_value">
            {{ visible_focus_root || t('room.rolesDrawer.workspaceFields.rootDirectory') }}
          </span>
        </div>

        <div class="binding_line">
          <span class="label_inline">{{ t('room.rolesDrawer.workspaceFields.focusLabel') }}</span>
          <span class="binding_value">{{ resolvedWorkspace.focus_label || t('room.rolesDrawer.common.dash') }}</span>
        </div>
      </div>

      <div class="card_actions">
        <button class="ghost_btn" type="button" @click="emit('open-workspace-drawer')">
          {{ t('room.rolesDrawer.actions.openWorkspace') }}
        </button>
      </div>
    </section>

    <section class="section_card provider_catalog_section">
      <div class="section_head provider_catalog_section_head">
        <div>
          <div class="section_title">
            {{ t('room.rolesDrawer.sections.providerCatalog') }}
          </div>
          <div class="section_subtitle">
            {{ t('room.rolesDrawer.providerSection.catalog.subtitle') }}
          </div>
        </div>

        <div class="section_meta">
          <span class="meta_badge">
            {{ t('room.rolesDrawer.providerSummary.total', { count: summary.total }) }}
          </span>

          <span class="meta_badge success">
            {{ t('room.rolesDrawer.providerSummary.available', { count: summary.available }) }}
          </span>

          <span v-if="summary.unavailable" class="meta_badge danger">
            {{ t('room.rolesDrawer.providerSummary.unavailable', { count: summary.unavailable }) }}
          </span>

          <span v-if="summary.auth_required" class="meta_badge">
            {{ t('room.rolesDrawer.providerSummary.authRequired', { count: summary.auth_required }) }}
          </span>

          <span v-if="summary.auth_missing" class="meta_badge warn">
            {{ t('room.rolesDrawer.providerSummary.authMissing', { count: summary.auth_missing }) }}
          </span>

          <span class="meta_badge">
            {{ t('room.rolesDrawer.providerSection.summary.localRegistry', { count: registryProviderCount }) }}
          </span>

          <span v-if="importedProviderCount" class="meta_badge warn">
            {{ t('room.rolesDrawer.providerSection.summary.pasteImported', { count: importedProviderCount }) }}
          </span>

          <span v-if="grantedVisibleCount" class="meta_badge success">
            {{ t('room.rolesDrawer.providerSection.summary.grantedVisible', { count: grantedVisibleCount }) }}
          </span>

          <span v-if="finalOnlyCount" class="meta_badge">
            {{ t('room.rolesDrawer.providerSection.summary.finalOnly', { count: finalOnlyCount }) }}
          </span>
        </div>
      </div>

      <div class="helper_text">
        {{ t('room.rolesDrawer.providerCatalog.readonlyHint') }}
      </div>

      <div class="import_box">
        <div class="import_box_head">
          <div>
            <div class="section_title">
              {{ t('room.rolesDrawer.providerSection.import.title') }}
            </div>
            <div class="section_subtitle">
              {{ t('room.rolesDrawer.providerSection.import.subtitle') }}
            </div>
          </div>
        </div>

        <textarea
          :value="shareRefInput"
          class="import_textarea"
          rows="4"
          :placeholder="t('room.rolesDrawer.providerSection.import.placeholder')"
          @input="onShareRefInput"
        />

        <div class="card_actions import_actions">
          <button
            class="primary_btn"
            type="button"
            @click="emit('import-remote-provider-from-paste')"
            :disabled="busy || importedProviderBusy || !String(shareRefInput || '').trim()"
          >
            {{
              importedProviderBusy
                ? t('room.rolesDrawer.providerSection.actions.importing')
                : t('room.rolesDrawer.providerSection.actions.importShareRef')
            }}
          </button>

          <button
            class="ghost_btn"
            type="button"
            @click="emit('clear-imported-provider-input')"
            :disabled="busy || importedProviderBusy"
          >
            {{ t('room.rolesDrawer.providerSection.actions.clearInput') }}
          </button>

          <button
            v-if="importedProviderCount"
            class="ghost_btn"
            type="button"
            @click="emit('clear-imported-providers')"
            :disabled="busy || importedProviderBusy"
          >
            {{ t('room.rolesDrawer.providerSection.actions.clearImportedProviders') }}
          </button>
        </div>

        <div class="helper_text import_helper">
          {{ t('room.rolesDrawer.providerSection.import.helper') }}
        </div>

        <div v-if="importedProviderErrorText" class="modal_alert error import_alert">
          {{ importedProviderErrorText }}
        </div>

        <div v-else-if="importedProviderStatusText" class="modal_alert success import_alert">
          {{ importedProviderStatusText }}
        </div>

        <div v-if="importedProviderOptions.length" class="imported_provider_list">
          <div
            v-for="provider in importedProviderOptions"
            :key="`imported-${provider.provider_id}`"
            class="imported_provider_row"
          >
            <div class="imported_provider_info">
              <div class="imported_provider_title">
                {{ provider.label || provider.provider_id }}
              </div>

              <div class="provider_catalog_meta imported_meta">
                <span
                  v-if="providerVisibilitySource(provider) === 'granted_visible'"
                  class="meta_chip warn"
                >
                  {{ t('room.rolesDrawer.providerSection.badges.grantedVisible') }}
                </span>

                <span
                  v-else-if="providerVisibilitySource(provider) === 'room_visible'"
                  class="meta_chip neutral"
                >
                  {{ t('room.rolesDrawer.providerSection.badges.roomVisible') }}
                </span>

                <span
                  v-if="providerExternalResultView(provider) === 'final_result_only'"
                  class="meta_chip neutral"
                >
                  {{ t('room.rolesDrawer.providerSection.badges.finalOnly') }}
                </span>

                <span
                  v-if="providerGrantStateText(provider)"
                  class="meta_chip"
                  :class="{ ok: providerGrantStateIsActive(provider), bad: !providerGrantStateIsActive(provider) }"
                >
                  {{ providerGrantStateText(provider) }}
                </span>

                <span
                  v-if="providerVisibilitySource(provider) === 'granted_visible' && !providerSourceObservationAllowed(provider)"
                  class="meta_chip neutral"
                >
                  {{ t('room.rolesDrawer.providerSection.badges.noSourceObserve') }}
                </span>
              </div>

              <div class="imported_provider_desc">
                {{ providerGrantSummaryText(provider) || providerRoomSourceText(provider) || provider.description || t('room.rolesDrawer.providerSection.import.importedProviderFallback') }}
              </div>
            </div>

            <div class="role_actions">
              <button
                class="ghost_btn mini_btn"
                type="button"
                @click="emit('use-provider-for-create', provider.provider_id)"
                :disabled="!providerIsAvailable(provider)"
              >
                {{ t('room.rolesDrawer.providerSection.actions.useForCreateShort') }}
              </button>

              <button
                class="danger_btn mini_btn"
                type="button"
                @click="emit('remove-imported-provider', provider.provider_id)"
                :disabled="busy || importedProviderBusy"
              >
                {{ t('room.rolesDrawer.providerSection.actions.remove') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!providerOptions.length" class="empty_block">
        {{ t('room.rolesDrawer.providerCatalog.empty') }}
      </div>

      <div v-else class="provider_grid">
        <div
          v-for="provider in providerOptions"
          :key="provider.provider_id"
          class="provider_catalog_card"
          :class="{
            unavailable: !providerIsAvailable(provider),
            selected: isSelectedForCreate(provider.provider_id),
          }"
        >
          <div class="provider_catalog_head">
            <div class="provider_catalog_identity">
              <div class="provider_catalog_title">
                {{ provider.label || provider.provider_id }}
              </div>
              <div class="provider_catalog_desc">
                {{ provider.description || t('room.rolesDrawer.common.dash') }}
              </div>
            </div>
          </div>

          <div class="provider_catalog_meta">
            <span class="meta_chip" :class="{ ok: providerIsAvailable(provider), bad: !providerIsAvailable(provider) }">
              {{
                providerIsAvailable(provider)
                  ? t('room.rolesDrawer.providerCatalog.available')
                  : t('room.rolesDrawer.providerCatalog.unavailable')
              }}
            </span>

            <span class="meta_chip neutral">
              {{ providerAuthTypeLabel(provider) }}
            </span>

            <span
              v-if="providerNeedsAuth(provider)"
              class="meta_chip"
              :class="{ ok: providerAuthConfigured(provider), bad: !providerAuthConfigured(provider) }"
            >
              {{
                providerAuthConfigured(provider)
                  ? t('room.rolesDrawer.providerCatalog.authReady')
                  : t('room.rolesDrawer.providerCatalog.authMissing')
              }}
            </span>

            <span v-if="isRoomSharedProvider(provider)" class="meta_chip neutral">
              {{ t('room.rolesDrawer.providerSection.badges.roomMcp') }}
            </span>

            <span v-if="isImportedProvider(provider)" class="meta_chip warn">
              {{ t('room.rolesDrawer.providerSection.badges.importedRemote') }}
            </span>

            <span
              v-if="providerVisibilitySource(provider) === 'granted_visible'"
              class="meta_chip warn"
            >
              {{ t('room.rolesDrawer.providerSection.badges.grantedVisible') }}
            </span>

            <span
              v-else-if="providerVisibilitySource(provider) === 'room_visible'"
              class="meta_chip neutral"
            >
              {{ t('room.rolesDrawer.providerSection.badges.roomVisible') }}
            </span>

            <span
              v-if="providerExternalResultView(provider) === 'final_result_only'"
              class="meta_chip neutral"
            >
              {{ t('room.rolesDrawer.providerSection.badges.finalOnly') }}
            </span>

            <span
              v-if="providerGrantStateText(provider)"
              class="meta_chip"
              :class="{ ok: providerGrantStateIsActive(provider), bad: !providerGrantStateIsActive(provider) }"
            >
              {{ providerGrantStateText(provider) }}
            </span>

            <span
              v-if="providerVisibilitySource(provider) === 'granted_visible' && !providerSourceObservationAllowed(provider)"
              class="meta_chip neutral"
            >
              {{ t('room.rolesDrawer.providerSection.badges.noSourceObserve') }}
            </span>

            <span v-if="providerSupportsWorkspace(provider)" class="meta_chip">
              {{ t('room.rolesDrawer.providerCatalog.supportsWorkspace') }}
            </span>

            <span v-if="providerSupportsFocusRoot(provider)" class="meta_chip">
              {{ t('room.rolesDrawer.providerCatalog.supportsFocusRoot') }}
            </span>
          </div>

          <div v-if="providerAvailabilityReason(provider)" class="provider_catalog_reason">
            {{ providerAvailabilityReason(provider) }}
          </div>

          <div class="provider_catalog_hint">
            {{ providerStatusText(provider) }}
          </div>

          <div v-if="providerGrantSummaryText(provider)" class="provider_catalog_source">
            {{ providerGrantSummaryText(provider) }}
          </div>

          <div v-else-if="providerRoomSourceText(provider)" class="provider_catalog_source">
            {{ providerRoomSourceText(provider) }}
          </div>

          <div class="provider_catalog_actions">
            <button
              class="primary_btn mini_btn"
              type="button"
              @click="emit('use-provider-for-create', provider.provider_id)"
              :disabled="!providerIsAvailable(provider)"
            >
              {{
                isSelectedForCreate(provider.provider_id)
                  ? t('room.rolesDrawer.actions.selectedForCreate')
                  : t('room.rolesDrawer.actions.useForCreate')
              }}
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'

const props = defineProps({
  resolvedWorkspace: { type: Object, default: () => ({}) },
  providerSummary: { type: Object, default: () => ({}) },
  registryProviderCount: { type: Number, default: 0 },
  importedProviderCount: { type: Number, default: 0 },
  providerOptions: { type: Array, default: () => [] },
  importedProviderOptions: { type: Array, default: () => [] },
  shareRefInput: { type: String, default: '' },
  busy: { type: Boolean, default: false },
  importedProviderBusy: { type: Boolean, default: false },
  importedProviderStatusText: { type: String, default: '' },
  importedProviderErrorText: { type: String, default: '' },

  providerIsAvailable: { type: Function, required: true },
  providerNeedsAuth: { type: Function, required: true },
  providerAuthConfigured: { type: Function, required: true },
  providerSupportsWorkspace: { type: Function, required: true },
  providerSupportsFocusRoot: { type: Function, required: true },
  providerAvailabilityReason: { type: Function, required: true },
  providerAuthTypeLabel: { type: Function, required: true },
  providerRoomSourceText: { type: Function, required: true },
  providerStatusText: { type: Function, required: true },
  isRoomSharedProvider: { type: Function, required: true },
  isImportedProvider: { type: Function, required: true },
  isSelectedForCreate: { type: Function, required: true },
})

const emit = defineEmits([
  'open-workspace-drawer',
  'update:share-ref-input',
  'import-remote-provider-from-paste',
  'clear-imported-provider-input',
  'clear-imported-providers',
  'use-provider-for-create',
  'remove-imported-provider',
])

const { t } = useI18n()

const summary = computed(() => ({
  total: Number(props.providerSummary?.total || 0),
  available: Number(props.providerSummary?.available || 0),
  unavailable: Number(props.providerSummary?.unavailable || 0),
  auth_required: Number(props.providerSummary?.auth_required || 0),
  auth_missing: Number(props.providerSummary?.auth_missing || 0),
}))

const grantedVisibleCount = computed(() =>
  (props.providerOptions || []).filter(
    (provider) => providerVisibilitySource(provider) === 'granted_visible'
  ).length
)

const finalOnlyCount = computed(() =>
  (props.providerOptions || []).filter(
    (provider) => providerExternalResultView(provider) === 'final_result_only'
  ).length
)

const visible_focus_root = computed(() => {
  return displayPath(props.resolvedWorkspace?.focus_root)
})

const resolvedWorkspace = computed(() => {
  return safeObject(props.resolvedWorkspace)
})

function safeString(v) {
  return v === null || v === undefined ? '' : String(v).trim()
}

function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function safeBool(v, fallback = false) {
  if (typeof v === 'boolean') return v
  if (v === null || v === undefined) return fallback
  if (typeof v === 'number') return !!v

  const s = safeString(v).toLowerCase()
  if (!s) return fallback

  return ['1', 'true', 'yes', 'on', 'y'].includes(s)
}

function displayPath(path) {
  const raw = safeString(path)
  if (!raw) return ''
  const visible = safeString(to_user_visible_path(raw))
  return visible || raw
}

function providerVisibilitySource(provider = {}) {
  return safeString(
    provider.visibility_source ||
    safeObject(provider.provider_snapshot).visibility_source
  ).toLowerCase()
}

function providerExternalResultView(provider = {}) {
  const snapshot = safeObject(provider.provider_snapshot)
  const grantScope = safeObject(provider.grant_scope || snapshot.grant_scope)

  return safeString(
    provider.external_result_view ||
    snapshot.external_result_view ||
    grantScope.result_view
  ).toLowerCase()
}

function providerGrantStateText(provider = {}) {
  const state = safeString(
    provider.grant_state ||
    safeObject(provider.provider_snapshot).grant_state
  ).toLowerCase()

  if (!state) return ''
  if (state === 'active') return t('room.rolesDrawer.providerSection.grantStates.active')
  if (state === 'revoked') return t('room.rolesDrawer.providerSection.grantStates.revoked')
  if (state === 'expired') return t('room.rolesDrawer.providerSection.grantStates.expired')

  return t('room.rolesDrawer.providerSection.grantStates.unknown', { state })
}

function providerGrantStateIsActive(provider = {}) {
  const state = safeString(
    provider.grant_state ||
    safeObject(provider.provider_snapshot).grant_state
  ).toLowerCase()

  return state === 'active'
}

function providerSourceObservationAllowed(provider = {}) {
  const snapshot = safeObject(provider.provider_snapshot)
  const grantScope = safeObject(provider.grant_scope || snapshot.grant_scope)

  return safeBool(
    provider.source_observation_allowed,
    safeBool(snapshot.source_observation_allowed, safeBool(grantScope.observe_source_room, false))
  )
}

function providerGrantSummaryText(provider = {}) {
  const snapshot = safeObject(provider.provider_snapshot)
  const publication = safeObject(provider.publication || snapshot.publication)
  const visibilitySource = providerVisibilitySource(provider)
  const resultView = providerExternalResultView(provider)
  const grantState = providerGrantStateText(provider)
  const parts = []

  if (publication.publication_state) {
    parts.push(`publication=${safeString(publication.publication_state)}`)
  }

  if (visibilitySource) {
    parts.push(`visibility=${visibilitySource}`)
  }

  if (resultView) {
    parts.push(`result_view=${resultView}`)
  }

  if (grantState) {
    parts.push(grantState)
  }

  if (visibilitySource === 'granted_visible' && !providerSourceObservationAllowed(provider)) {
    parts.push('source_observation=false')
  }

  return parts.join('；')
}

function onShareRefInput(event) {
  emit('update:share-ref-input', event?.target?.value || '')
}
</script>

<style scoped>
.provider_section_stack {
  display: grid;
  gap: 14px;
}

.section_card {
  position: relative;
  margin: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
}

.workspace_card {
  border-color: color-mix(in srgb, var(--selected) 14%, var(--line));
}

.provider_catalog_section {
  overflow: hidden;
}

.section_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.provider_catalog_section_head {
  margin-bottom: 10px;
}

.section_title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.section_subtitle {
  max-width: 760px;
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.section_meta {
  display: flex;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
  min-width: 0;
}

.meta_badge,
.meta_chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 23px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
}

.meta_badge.success,
.meta_chip.ok {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.09);
  color: #16a34a;
}

.meta_badge.danger,
.meta_chip.bad {
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.meta_badge.warn,
.meta_chip.warn {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.09);
  color: #d97706;
}

.meta_chip.neutral {
  color: var(--text-main);
  border-color: var(--line);
  background: color-mix(in srgb, var(--sidebar-bg) 78%, transparent);
}

.binding_card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin-top: 12px;
  padding: 11px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--sidebar-bg) 84%, transparent);
}

.binding_line {
  display: grid;
  grid-template-columns: minmax(104px, 0.34fr) minmax(0, 1fr);
  gap: 9px;
  min-width: 0;
  color: var(--text-main);
  font-size: 0.82rem;
  line-height: 1.5;
}

.label_inline {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 720;
}

.binding_value {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: normal;
}

.helper_text {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.import_box {
  margin-top: 12px;
  padding: 13px;
  border: 1px dashed color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.import_box_head {
  margin-bottom: 11px;
}

.import_textarea {
  width: 100%;
  min-height: 96px;
  resize: vertical;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 84%, transparent);
  color: var(--text-main);
  font: inherit;
  font-size: 0.82rem;
  line-height: 1.55;
  outline: none;
  box-sizing: border-box;
}

.import_textarea::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 74%, transparent);
}

.import_textarea:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 52%, transparent);
}

.import_helper {
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
}

.imported_provider_list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.imported_provider_row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 80%, transparent);
}

.imported_provider_info {
  min-width: 0;
  flex: 1;
}

.imported_provider_title {
  color: var(--text-main);
  font-size: 0.88rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.imported_provider_desc {
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: 0.79rem;
  line-height: 1.55;
  overflow-wrap: break-word;
  word-break: normal;
}

.imported_meta {
  margin-top: 7px;
}

.provider_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 11px;
  margin-top: 12px;
}

.provider_catalog_card {
  position: relative;
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
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.provider_catalog_card.unavailable {
  opacity: 0.78;
}

.provider_catalog_card.selected {
  border-color: color-mix(in srgb, var(--selected) 56%, var(--line));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--selected-bg) 70%, transparent) inset,
    0 10px 26px rgba(0, 0, 0, 0.04);
}

.provider_catalog_card.selected::before {
  content: "";
  position: absolute;
  inset: 11px auto 11px 0;
  width: 3px;
  border-radius: 999px;
  background: var(--selected);
}

.provider_catalog_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.provider_catalog_identity {
  min-width: 0;
}

.provider_catalog_title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.provider_catalog_desc {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.provider_catalog_meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.provider_catalog_reason {
  margin-top: 10px;
  padding: 8px 9px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 11px;
  background: rgba(239, 68, 68, 0.07);
  color: #ef4444;
  font-size: 0.76rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.provider_catalog_hint {
  min-height: 2.4em;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 0.79rem;
  line-height: 1.52;
  overflow-wrap: break-word;
}

.provider_catalog_source {
  margin-top: 9px;
  padding: 8px 9px;
  border: 1px dashed var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: normal;
}

.provider_catalog_actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 11px;
}

.card_actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.import_actions {
  align-items: stretch;
}

.role_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
  flex: 0 0 auto;
}

.empty_block {
  margin-top: 12px;
  padding: 18px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 80%, transparent);
  text-align: center;
  font-size: 0.84rem;
  line-height: 1.55;
}

.modal_alert {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 13px;
  border: 1px solid var(--line);
  font-size: 0.84rem;
  line-height: 1.5;
}

.modal_alert.error {
  border-color: rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.modal_alert.success {
  border-color: rgba(34, 197, 94, 0.32);
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
}

.import_alert {
  margin-top: 10px;
  margin-bottom: 0;
}

.primary_btn,
.ghost_btn,
.danger_btn,
.mini_btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.primary_btn {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--selected) 90%, #1f2937);
  color: #fff;
}

.primary_btn:hover:not(:disabled) {
  opacity: 0.94;
}

.ghost_btn,
.mini_btn {
  color: var(--text-secondary);
}

.ghost_btn:hover:not(:disabled),
.mini_btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 58%, var(--editor-bg));
  color: var(--selected);
}

.danger_btn {
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.06);
  color: #ef4444;
}

.danger_btn:hover:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.48);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.primary_btn:active:not(:disabled),
.ghost_btn:active:not(:disabled),
.danger_btn:active:not(:disabled),
.mini_btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mini_btn {
  min-height: 29px;
  padding: 0 10px;
  font-size: 0.75rem;
  flex-shrink: 0;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 960px) {
  .section_head {
    flex-direction: column;
    align-items: stretch;
  }

  .section_meta {
    justify-content: flex-start;
  }

  .provider_grid,
  .binding_card {
    grid-template-columns: 1fr;
  }

  .imported_provider_row {
    flex-direction: column;
    align-items: stretch;
  }

  .role_actions {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .provider_section_stack {
    gap: 12px;
  }

  .section_card,
  .import_box,
  .provider_catalog_card,
  .imported_provider_row {
    border-radius: 14px;
  }

  .binding_line {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .card_actions,
  .import_actions,
  .role_actions,
  .provider_catalog_actions {
    width: 100%;
  }

  .card_actions button,
  .import_actions button,
  .role_actions button,
  .provider_catalog_actions button {
    flex: 1 1 auto;
    min-width: 0;
  }
}

@media (max-width: 420px) {
  .card_actions button,
  .import_actions button,
  .role_actions button,
  .provider_catalog_actions button {
    width: 100%;
    flex-basis: 100%;
  }

  .meta_badge,
  .meta_chip {
    white-space: normal;
    text-align: center;
    line-height: 1.25;
    padding-top: 4px;
    padding-bottom: 4px;
  }
}
</style>

