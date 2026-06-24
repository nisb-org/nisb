<template>
  <div v-if="visible" class="modal_mask" @click="closeDrawer">
    <div class="modal_panel roles_drawer_panel" @click.stop>
      <div class="modal_header">
        <div class="modal_title_block">
          <div class="drawer_eyebrow">
            <span class="drawer_dot"></span>
            <span>{{ t('room.rolesDrawer.sections.existingRoles') }}</span>
          </div>

          <h3>{{ t('room.rolesDrawer.title') }}</h3>
          <p class="modal_desc">{{ t('room.rolesDrawer.description') }}</p>
        </div>

        <div class="modal_actions">
          <button class="ghost_btn" type="button" @click="openWorkspaceDrawer">
            {{ t('room.rolesDrawer.actions.workspace') }}
          </button>

          <button
            class="ghost_btn"
            type="button"
            @click="refreshProviderRegistry"
            :disabled="busy || importedProviderBusy"
            :title="t('room.rolesDrawer.actions.refreshStatusTitle')"
          >
            {{ t('room.rolesDrawer.actions.refreshStatus') }}
          </button>

          <button class="ghost_btn" type="button" @click="refreshRoles" :disabled="busy || importedProviderBusy">
            {{ t('room.rolesDrawer.actions.refresh') }}
          </button>

          <button
            class="close_btn"
            type="button"
            :aria-label="t('room.rolesDrawer.actions.close')"
            @click="closeDrawer"
          >
            ×
          </button>
        </div>
      </div>

      <div class="modal_body">
        <div v-if="errorText" class="modal_alert error">
          {{ errorText }}
        </div>

        <div v-if="successText" class="modal_alert success">
          {{ successText }}
        </div>

        <RoomRolesDrawerProviderSection
          :resolved-workspace="resolvedWorkspace"
          :provider-summary="providerSummary"
          :registry-provider-count="registryProviderCount"
          :imported-provider-count="importedProviderCount"
          :provider-options="providerOptions"
          :imported-provider-options="importedProviderOptions"
          :share-ref-input="importedShareRefInput"
          :busy="busy"
          :imported-provider-busy="importedProviderBusy"
          :imported-provider-status-text="importedProviderStatusText"
          :imported-provider-error-text="importedProviderErrorText"
          :provider-is-available="providerIsAvailable"
          :provider-needs-auth="providerNeedsAuth"
          :provider-auth-configured="providerAuthConfigured"
          :provider-supports-workspace="providerSupportsWorkspace"
          :provider-supports-focus-root="providerSupportsFocusRoot"
          :provider-availability-reason="providerAvailabilityReason"
          :provider-auth-type-label="providerAuthTypeLabel"
          :provider-room-source-text="providerRoomSourceText"
          :provider-status-text="providerStatusText"
          :is-room-shared-provider="isRoomSharedProvider"
          :is-imported-provider="isImportedProvider"
          :is-selected-for-create="isSelectedForCreate"
          @open-workspace-drawer="openWorkspaceDrawer"
          @update:share-ref-input="setImportedShareRefInput"
          @import-remote-provider-from-paste="importRemoteProviderFromPaste"
          @clear-imported-provider-input="clearImportedProviderInput"
          @clear-imported-providers="clearImportedProviders"
          @use-provider-for-create="useProviderForCreate"
          @remove-imported-provider="removeImportedProvider"
        />

        <section class="section_card create_role_card">
          <div class="section_head">
            <div>
              <div class="section_title">{{ t('room.rolesDrawer.sections.createRole') }}</div>
              <div class="helper_text">
                {{ t('room.rolesDrawer.createRole.hint') }}
              </div>
            </div>
          </div>

          <RoomRoleFormFields
            :form="createForm"
            :tool-policy-keys="toolPolicyKeys"
            :provider-options="providerOptions"
            :resolved-workspace="resolvedWorkspace"
          />

          <div class="card_actions">
            <button class="primary_btn" type="button" @click="submitCreate" :disabled="busy || !roomId">
              {{ busy ? t('room.rolesDrawer.actions.creating') : t('room.rolesDrawer.actions.createRole') }}
            </button>

            <button class="ghost_btn" type="button" @click="resetCreateForm" :disabled="busy">
              {{ t('room.rolesDrawer.actions.reset') }}
            </button>
          </div>
        </section>

        <section class="section_card existing_roles_card">
          <div class="section_head">
            <div>
              <div class="section_title">{{ t('room.rolesDrawer.sections.existingRoles') }}</div>
            </div>

            <div class="section_status_chip">
              {{ roles.length }}
            </div>
          </div>

          <div v-if="!roles.length" class="empty_block">
            {{ t('room.rolesDrawer.existingRoles.empty') }}
          </div>

          <div v-for="role in roles" :key="role.role_id" class="role_card">
            <div class="role_card_header">
              <div class="role_title">
                <span class="role_avatar">{{ role.avatar || '🤖' }}</span>

                <div class="role_identity">
                  <strong>{{ role.name || role.slug || role.role_id }}</strong>
                  <span class="role_slug">@{{ role.slug || role.name }}</span>
                </div>
              </div>

              <div class="role_actions">
                <button class="ghost_btn mini_btn" type="button" @click="toggleNotebook(role)">
                  {{
                    openNotebookRoleId === role.role_id
                      ? t('room.rolesDrawer.actions.collapseNotebook')
                      : t('room.rolesDrawer.actions.notebook')
                  }}
                </button>

                <button class="ghost_btn mini_btn" type="button" @click="startEdit(role)">
                  {{ t('room.rolesDrawer.actions.edit') }}
                </button>

                <button class="danger_btn mini_btn" type="button" @click="removeRole(role)" :disabled="busy">
                  {{ t('room.rolesDrawer.actions.delete') }}
                </button>
              </div>
            </div>

            <div v-if="editingRoleId === role.role_id" class="edit_panel">
              <div class="helper_text">
                {{ t('room.rolesDrawer.existingRoles.editHint') }}
              </div>

              <RoomRoleFormFields
                :form="editForm"
                :tool-policy-keys="toolPolicyKeys"
                :provider-options="providerOptions"
                :resolved-workspace="resolvedWorkspace"
              />

              <div class="card_actions">
                <button class="primary_btn" type="button" @click="submitUpdate(role.role_id)" :disabled="busy">
                  {{ t('room.rolesDrawer.actions.save') }}
                </button>

                <button class="ghost_btn" type="button" @click="cancelEdit">
                  {{ t('room.rolesDrawer.actions.cancel') }}
                </button>
              </div>
            </div>

            <div v-else class="role_summary">
              <div class="summary_line">
                <span class="label">{{ t('room.rolesDrawer.roleSummary.prompt') }}</span>
                <span class="summary_value">{{ role.system_prompt || t('room.rolesDrawer.common.dash') }}</span>
              </div>

              <div class="summary_line">
                <span class="label">{{ t('room.rolesDrawer.roleSummary.binding') }}</span>
                <span class="summary_value">{{ formatBinding(role) }}</span>
              </div>

              <div class="summary_line">
                <span class="label">{{ t('room.rolesDrawer.roleSummary.time') }}</span>
                <span class="summary_value">{{ formatDocTime(role) }}</span>
              </div>

              <div class="summary_line">
                <span class="label">{{ t('room.rolesDrawer.roleSummary.tools') }}</span>
                <span class="summary_value">{{ formatTools(role) }}</span>
              </div>

              <div class="summary_line">
                <span class="label">{{ t('room.rolesDrawer.roleSummary.mcp') }}</span>
                <span class="summary_value">{{ formatMcp(role) }}</span>
              </div>
            </div>

            <RoomRoleNotebookPanel
              v-if="openNotebookRoleId === role.role_id"
              :form="ensureNotebookForm(role)"
              :resolved-workspace="resolvedWorkspace"
              :busy="notebookBusyRoleId === role.role_id"
              :status-text="notebookStatusMap[String(role.role_id || '')] || ''"
              @fill-template="fillNotebookTemplate(role)"
              @submit="submitNotebook(role)"
            />
          </div>
        </section>
      </div>

      <div class="modal_footer">
        <div class="footer_hint">
          <span v-if="editingRoleId">
            {{ t('room.rolesDrawer.footer.editing') }}
          </span>

          <span v-else-if="openNotebookRoleId">
            {{ t('room.rolesDrawer.footer.notebook') }}
          </span>

          <span v-else>
            {{ t('room.rolesDrawer.footer.default') }}
          </span>
        </div>

        <div class="footer_actions">
          <button class="ghost_btn" type="button" @click="closeDrawer">
            {{ t('room.rolesDrawer.actions.close') }}
          </button>
        </div>
      </div>

      <RoomWorkspaceDrawer
        :visible="workspaceDrawerVisible"
        :room_id="roomId"
        :room_state="effectiveRoomState"
        :workspace_id="resolvedWorkspace.workspace_id"
        :workspace_name="resolvedWorkspace.workspace_name"
        :focus_root="resolvedWorkspace.focus_root"
        :focus_label="resolvedWorkspace.focus_label"
        @close="workspaceDrawerVisible = false"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'
import { useRoomRolesDrawerForm } from '../../../composables/editor/room/use_room_roles_drawer_form'
import { useRoomRolesDrawerProviderCatalog } from '../../../composables/editor/room/use_room_roles_drawer_provider_catalog'
import { useRoomRolesDrawerRoleSummary } from '../../../composables/editor/room/use_room_roles_drawer_role_summary'
import { useRoomStore } from '../../../stores/room'
import RoomRoleFormFields from './RoomRoleFormFields.vue'
import RoomRoleNotebookPanel from './RoomRoleNotebookPanel.vue'
import RoomWorkspaceDrawer from './RoomWorkspaceDrawer.vue'
import RoomRolesDrawerProviderSection from './RoomRolesDrawerProviderSection.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  room_id: { type: String, default: '' },
  room_state: { type: Object, default: () => ({}) },
  workspace_id: { type: String, default: '' },
  workspace_name: { type: String, default: '' },
  focus_root: { type: String, default: '' },
  focus_label: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const { callTool } = useMCP()
const room_store = useRoomStore()

const {
  toolPolicyKeys,
  createEmptyForm,
  resetForm,
  fillFormFromRole,
  buildPayload,
  validateRolePayload,
  assertToolSuccess,
  extractRoleFromResult,
  fetchProviderOptions,
  getProviderOption,
  normalizeProviderOption,
  normalizeImportedProviderOption,
  normalizeProviderSnapshot,
  buildProviderSnapshot,
  extractImportedProviderOptionFromRole,
  extractImportedProviderOptionsFromRoles,
  mergeProviderOptions,
  isRoomSharedCapabilityProvider,
  isImportedRemoteProvider,
  safeString,
  safeBool,
  safeArray,
  safeObject,
} = useRoomRolesDrawerForm()

const busy = ref(false)
const errorText = ref('')
const successText = ref('')
const editingRoleId = ref('')
const openNotebookRoleId = ref('')
const notebookBusyRoleId = ref('')
const workspaceDrawerVisible = ref(false)

const notebookForms = reactive({})
const notebookStatusMap = reactive({})

const createForm = reactive(createEmptyForm())
const editForm = reactive(createEmptyForm())

const roomId = computed(() => String(props.room_id || room_store.roomId || '').trim())
const roles = computed(() => Array.isArray(room_store.roles) ? room_store.roles : [])

const effectiveRoomState = computed(() => {
  if (props.room_state && typeof props.room_state === 'object' && Object.keys(props.room_state).length) {
    return props.room_state
  }
  if (room_store.roomState && typeof room_store.roomState === 'object') {
    return room_store.roomState
  }
  if (room_store.room_state && typeof room_store.room_state === 'object') {
    return room_store.room_state
  }
  return {}
})

const resolvedWorkspace = computed(() => {
  const roomState = effectiveRoomState.value || {}
  const roomInfo =
    room_store.roomInfo ||
    room_store.currentRoom ||
    room_store.activeRoom ||
    room_store.room ||
    {}

  const workspaceContext =
    roomState.workspace_context ||
    roomInfo.workspace_context ||
    roomInfo.workspace_binding ||
    roomInfo.workspace ||
    {}

  return {
    workspace_id: String(
      props.workspace_id ||
      workspaceContext.workspace_id ||
      roomState.workspace_id ||
      roomInfo.workspace_id ||
      ''
    ).trim(),
    workspace_name: String(
      props.workspace_name ||
      workspaceContext.workspace_name ||
      roomState.workspace_name ||
      roomInfo.workspace_name ||
      ''
    ).trim(),
    focus_root: String(
      props.focus_root ||
      workspaceContext.focus_root ||
      roomState.focus_root ||
      roomInfo.focus_root ||
      ''
    ).trim(),
    focus_label: String(
      props.focus_label ||
      workspaceContext.focus_label ||
      roomState.focus_label ||
      roomInfo.focus_label ||
      ''
    ).trim(),
  }
})

function clearFeedback() {
  errorText.value = ''
  successText.value = ''
}

function dispatchToast(message, type = 'success') {
  window.dispatchEvent(new CustomEvent('nisb-toast', {
    detail: { message, type }
  }))
}

function resetCreateForm() {
  resetForm(createForm, providerOptions.value)
}

function resetEditForm() {
  resetForm(editForm, providerOptions.value)
  editingRoleId.value = ''
}

function closeDrawer() {
  resetEditForm()
  clearFeedback()
  clearImportedFeedback()
  emit('close')
}

function setImportedShareRefInput(value) {
  importedShareRefInput.value = String(value || '')
}

const {
  providerRegistryOptions,
  importedProviderOptions,
  providerRegistrySummary,
  importedShareRefInput,
  importedProviderBusy,
  importedProviderStatusText,
  importedProviderErrorText,
  providerOptions,
  registryProviderCount,
  importedProviderCount,
  providerSummary,
  clearImportedFeedback,
  hydrateImportedProvidersFromRoles,
  isRoomSharedProvider,
  isImportedProvider,
  providerIsAvailable,
  providerNeedsAuth,
  providerAuthConfigured,
  providerSupportsWorkspace,
  providerSupportsFocusRoot,
  providerAvailabilityReason,
  providerAuthTypeLabel,
  providerRoomSourceText,
  providerStatusText,
  providerLabel,
  isSelectedForCreate,
  applyProviderToForm,
  removeImportedProvider,
  clearImportedProviders,
  clearImportedProviderInput,
  importRemoteProviderFromPaste,
  refreshProviderRegistry,
  useProviderForCreate,
} = useRoomRolesDrawerProviderCatalog({
  t,
  callTool,
  room_store,
  roomId,
  roles,
  createForm,
  editForm,
  errorText,
  successText,
  clearFeedback,
  dispatchToast,
  resetCreateForm,
  resetEditForm,
  fetchProviderOptions,
  assertToolSuccess,
  getProviderOption,
  normalizeProviderOption,
  normalizeImportedProviderOption,
  buildProviderSnapshot,
  extractImportedProviderOptionsFromRoles,
  mergeProviderOptions,
  isRoomSharedCapabilityProvider,
  isImportedRemoteProvider,
  safeString,
  safeBool,
  safeArray,
  safeObject,
})

const {
  formatBinding,
  formatDocTime,
  resolveRoleProvider,
  formatTools,
  formatMcp,
  defaultNotebookFilename,
  defaultNotebookTitle,
  defaultNotebookSummary,
} = useRoomRolesDrawerRoleSummary({
  t,
  providerOptions,
  getProviderOption,
  extractImportedProviderOptionFromRole,
  normalizeProviderSnapshot,
  normalizeImportedProviderOption,
  safeString,
  safeObject,
  providerLabel,
  providerIsAvailable,
  isRoomSharedProvider,
  isImportedProvider,
})

function fillEditForm(role) {
  hydrateImportedProvidersFromRoles([role])
  fillFormFromRole(editForm, role, providerOptions.value)
}

function startEdit(role) {
  clearFeedback()
  editingRoleId.value = String(role?.role_id || '')
  fillEditForm(role)
}

function cancelEdit() {
  resetEditForm()
}

async function refreshRoles() {
  if (!roomId.value) return
  busy.value = true
  clearFeedback()

  try {
    await room_store.refreshRoomInfo(callTool, roomId.value)

    if (typeof room_store.loadRoomRoles === 'function') {
      await room_store.loadRoomRoles(callTool, roomId.value)
    }

    hydrateImportedProvidersFromRoles(roles.value)
  } catch (e) {
    errorText.value = String(e?.message || e || t('room.rolesDrawer.messages.refreshRolesFailed'))
    dispatchToast(errorText.value, 'error')
  } finally {
    busy.value = false
  }
}

async function submitCreate() {
  if (!roomId.value) return
  const payload = buildPayload(createForm, providerOptions.value)
  const validationError = validateRolePayload(payload, providerOptions.value)
  if (validationError) {
    errorText.value = validationError
    return
  }

  busy.value = true
  clearFeedback()
  try {
    const data = assertToolSuccess(await callTool('nisb_room_role_create', {
      room_id: roomId.value,
      ...payload,
    }))

    const createdRole = extractRoleFromResult(data)
    await room_store.refreshRoomInfo(callTool, roomId.value)
    if (typeof room_store.loadRoomRoles === 'function') {
      await room_store.loadRoomRoles(callTool, roomId.value)
    }
    hydrateImportedProvidersFromRoles(roles.value)
    resetCreateForm()

    const roleName = safeString(createdRole?.name || payload.name || t('room.rolesDrawer.common.role'))
    const roleSlug = safeString(createdRole?.slug)
    successText.value = roleSlug
      ? t('room.rolesDrawer.messages.roleCreatedWithSlug', { name: roleName, slug: roleSlug })
      : t('room.rolesDrawer.messages.roleCreated', { name: roleName })
    dispatchToast(successText.value, 'success')
  } catch (e) {
    errorText.value = String(e?.message || e || t('room.rolesDrawer.messages.createRoleFailed'))
    dispatchToast(errorText.value, 'error')
  } finally {
    busy.value = false
  }
}

async function submitUpdate(roleId) {
  if (!roomId.value || !roleId) return
  const payload = buildPayload(editForm, providerOptions.value)
  const validationError = validateRolePayload(payload, providerOptions.value)
  if (validationError) {
    errorText.value = validationError
    return
  }

  busy.value = true
  clearFeedback()
  try {
    const data = assertToolSuccess(await callTool('nisb_room_role_update', {
      room_id: roomId.value,
      role_id: String(roleId),
      ...payload,
    }))

    const updatedRole = extractRoleFromResult(data)
    await room_store.refreshRoomInfo(callTool, roomId.value)
    if (typeof room_store.loadRoomRoles === 'function') {
      await room_store.loadRoomRoles(callTool, roomId.value)
    }
    hydrateImportedProvidersFromRoles(roles.value)
    resetEditForm()

    const roleName = safeString(updatedRole?.name || payload.name || roleId)
    const roleSlug = safeString(updatedRole?.slug)
    successText.value = roleSlug
      ? t('room.rolesDrawer.messages.roleUpdatedWithSlug', { name: roleName, slug: roleSlug })
      : t('room.rolesDrawer.messages.roleUpdated', { name: roleName })
    dispatchToast(successText.value, 'success')
  } catch (e) {
    errorText.value = String(e?.message || e || t('room.rolesDrawer.messages.updateRoleFailed'))
    dispatchToast(errorText.value, 'error')
  } finally {
    busy.value = false
  }
}

async function removeRole(role) {
  const roleId = String(role?.role_id || '')
  if (!roomId.value || !roleId) return
  const ok = window.confirm(t('room.rolesDrawer.messages.deleteConfirm', {
    name: role?.name || roleId,
  }))
  if (!ok) return

  busy.value = true
  clearFeedback()
  try {
    assertToolSuccess(await callTool('nisb_room_role_delete', {
      room_id: roomId.value,
      role_id: roleId,
    }))

    await room_store.refreshRoomInfo(callTool, roomId.value)
    if (typeof room_store.loadRoomRoles === 'function') {
      await room_store.loadRoomRoles(callTool, roomId.value)
    }
    hydrateImportedProvidersFromRoles(roles.value)

    if (editingRoleId.value === roleId) resetEditForm()
    if (openNotebookRoleId.value === roleId) openNotebookRoleId.value = ''

    successText.value = t('room.rolesDrawer.messages.roleDeleted', {
      name: String(role?.name || roleId),
    })
    dispatchToast(successText.value, 'success')
  } catch (e) {
    errorText.value = String(e?.message || e || t('room.rolesDrawer.messages.deleteRoleFailed'))
    dispatchToast(errorText.value, 'error')
  } finally {
    busy.value = false
  }
}

function ensureNotebookForm(role) {
  const roleId = String(role?.role_id || '').trim()
  if (!roleId) {
    return {
      title: '',
      section_title: 'latest',
      filename: 'agent.md',
      notebook_dir: '_room_notebooks',
      summary_md: '',
    }
  }

  if (!notebookForms[roleId]) {
    notebookForms[roleId] = {
      title: defaultNotebookTitle(role),
      section_title: 'latest',
      filename: defaultNotebookFilename(role),
      notebook_dir: '_room_notebooks',
      summary_md: defaultNotebookSummary(role),
    }
  }

  return notebookForms[roleId]
}

function toggleNotebook(role) {
  const roleId = String(role?.role_id || '')
  if (!roleId) return
  if (openNotebookRoleId.value === roleId) {
    openNotebookRoleId.value = ''
    return
  }
  ensureNotebookForm(role)
  openNotebookRoleId.value = roleId
}

function fillNotebookTemplate(role) {
  const form = ensureNotebookForm(role)
  form.summary_md = defaultNotebookSummary(role)
  if (!form.title) form.title = defaultNotebookTitle(role)
  if (!form.filename) form.filename = defaultNotebookFilename(role)
}

async function submitNotebook(role) {
  const roleId = String(role?.role_id || '').trim()
  if (!roleId) return

  const workspaceId = String(resolvedWorkspace.value.workspace_id || '').trim()
  if (!workspaceId) {
    notebookStatusMap[roleId] = t('room.rolesDrawer.messages.notebookMissingWorkspace')
    return
  }

  const form = ensureNotebookForm(role)
  const summaryMd = String(form.summary_md || '').trim()
  if (!summaryMd) {
    notebookStatusMap[roleId] = t('room.rolesDrawer.messages.notebookEmptySummary')
    return
  }

  notebookBusyRoleId.value = roleId
  notebookStatusMap[roleId] = ''

  try {
    const data = assertToolSuccess(await callTool('nisb_workspace_agent_notebook_upsert', {
      workspace_id: workspaceId,
      focus_root: String(resolvedWorkspace.value.focus_root || '').trim(),
      agent_id: String(role?.slug || role?.role_id || 'agent').trim(),
      title: String(form.title || defaultNotebookTitle(role)).trim(),
      section_title: String(form.section_title || 'latest').trim(),
      summary_md: summaryMd,
      notebook_dir: String(form.notebook_dir || '_room_notebooks').trim(),
      filename: String(form.filename || defaultNotebookFilename(role)).trim(),
      rebuild_index: true,
    }))
    notebookStatusMap[roleId] = t('room.rolesDrawer.messages.notebookWriteSuccess', {
      path: String(data.relative_path || form.filename || ''),
    })
  } catch (e) {
    notebookStatusMap[roleId] = String(e?.message || e || t('room.rolesDrawer.messages.notebookWriteFailed'))
  } finally {
    notebookBusyRoleId.value = ''
  }
}

function openWorkspaceDrawer() {
  workspaceDrawerVisible.value = true
}

watch(
  () => roles.value,
  (nextRoles) => {
    hydrateImportedProvidersFromRoles(nextRoles)
  },
  { deep: true }
)

watch(
  () => props.visible,
  async (v) => {
    if (!v) {
      clearFeedback()
      clearImportedFeedback()
      resetEditForm()
      return
    }

    clearFeedback()
    clearImportedFeedback()

    if (roomId.value) {
      await refreshRoles()
    }

    await refreshProviderRegistry()
    resetCreateForm()
    resetEditForm()
  },
  { immediate: true }
)
</script>

<style scoped>
.modal_mask {
  position: fixed;
  inset: 0;
  z-index: 1250;
  display: flex;
  align-items: stretch;
  justify-content: flex-end;
  padding: 18px 18px 18px 44px;
  background:
    radial-gradient(circle at 18% 12%, rgba(99, 102, 241, 0.18), transparent 34%),
    radial-gradient(circle at 78% 18%, rgba(14, 165, 233, 0.14), transparent 30%),
    rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(10px) saturate(138%);
  -webkit-backdrop-filter: blur(10px) saturate(138%);
}

.modal_panel {
  position: relative;
  width: min(1120px, calc(100vw - 64px));
  max-height: calc(100vh - 36px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid color-mix(in srgb, var(--line) 82%, rgba(255, 255, 255, 0.28));
  border-radius: 22px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 92%, rgba(255, 255, 255, 0.08)),
      color-mix(in srgb, var(--editor-bg) 90%, transparent)
    );
  box-shadow:
    0 26px 72px rgba(0, 0, 0, 0.34),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  backdrop-filter: blur(18px) saturate(155%);
  -webkit-backdrop-filter: blur(18px) saturate(155%);
  animation: drawerSlideIn 0.18s ease-out;
}

.roles_drawer_panel::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: color-mix(in srgb, var(--selected) 62%, transparent);
  opacity: 0.7;
  pointer-events: none;
}

.modal_header {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 18px 15px;
  border-bottom: 1px solid var(--line);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, rgba(255, 255, 255, 0.08)),
      color-mix(in srgb, var(--sidebar-bg) 80%, transparent)
    );
}

.modal_title_block {
  min-width: 0;
}

.drawer_eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 23px;
  padding: 0 9px;
  margin-bottom: 8px;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 70%, transparent);
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1;
}

.drawer_dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 14%, transparent);
}

.modal_header h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.02rem;
  font-weight: 840;
  letter-spacing: -0.015em;
  line-height: 1.25;
}

.modal_desc {
  max-width: 760px;
  margin: 7px 0 0;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.55;
}

.modal_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  flex: 0 0 auto;
}

.modal_body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 18px;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--text-secondary) 34%, transparent) transparent;
}

.modal_body::-webkit-scrollbar {
  width: 10px;
}

.modal_body::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background-clip: padding-box;
  background-color: color-mix(in srgb, var(--text-secondary) 28%, transparent);
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

.section_card {
  position: relative;
  margin-bottom: 14px;
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

.create_role_card {
  border-color: color-mix(in srgb, var(--selected) 18%, var(--line));
}

.existing_roles_card {
  margin-bottom: 0;
}

.section_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section_title {
  color: var(--text-main);
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
}

.section_status_chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 22%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 58%, transparent);
  color: var(--selected);
  font-size: 0.75rem;
  font-weight: 780;
  font-variant-numeric: tabular-nums;
}

.helper_text {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.card_actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.role_card {
  margin-top: 10px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.035),
    0 0 0 1px rgba(255, 255, 255, 0.02) inset;
}

.role_card_header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.role_title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: var(--text-main);
}

.role_avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  font-size: 1.06rem;
  line-height: 1;
}

.role_identity {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.role_identity strong {
  color: var(--text-main);
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.role_slug {
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.role_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;
  flex: 0 0 auto;
}

.role_summary {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.summary_line {
  display: grid;
  grid-template-columns: minmax(72px, 0.18fr) minmax(0, 1fr);
  gap: 10px;
  min-width: 0;
  color: var(--text-main);
  font-size: 0.84rem;
  line-height: 1.5;
}

.label {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.45;
}

.summary_value {
  min-width: 0;
  color: var(--text-main);
  overflow-wrap: anywhere;
  word-break: normal;
}

.edit_panel {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.empty_block {
  margin-top: 10px;
  padding: 18px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--sidebar-bg) 80%, transparent);
  text-align: center;
  font-size: 0.84rem;
  line-height: 1.55;
}

.modal_footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 18px 15px;
  border-top: 1px solid var(--line);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 94%, rgba(255, 255, 255, 0.04))
    );
}

.footer_hint {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.footer_actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
}

.primary_btn,
.ghost_btn,
.danger_btn,
.close_btn,
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
.close_btn,
.mini_btn {
  color: var(--text-secondary);
}

.ghost_btn:hover:not(:disabled),
.close_btn:hover:not(:disabled),
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
.close_btn:active:not(:disabled),
.mini_btn:active:not(:disabled) {
  transform: translateY(1px);
}

.close_btn {
  width: 34px;
  padding: 0;
  font-size: 1.05rem;
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

@keyframes drawerSlideIn {
  from {
    opacity: 0;
    transform: translateX(18px) scale(0.992);
  }

  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@media (max-width: 960px) {
  .modal_mask {
    padding: 14px;
  }

  .modal_panel {
    width: min(100vw - 28px, 100vw);
  }

  .modal_header {
    flex-direction: column;
    align-items: stretch;
  }

  .modal_actions {
    justify-content: flex-start;
  }

  .role_card_header {
    flex-direction: column;
    align-items: stretch;
  }

  .role_actions {
    justify-content: flex-start;
  }

  .modal_footer {
    flex-direction: column;
    align-items: stretch;
  }

  .footer_actions {
    justify-content: flex-end;
  }
}

@media (max-width: 720px) {
  .modal_mask {
    padding: 0;
  }

  .modal_panel {
    width: 100vw;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
    border-left: 0;
    border-right: 0;
  }

  .modal_header {
    padding: 15px 14px 13px;
  }

  .modal_body {
    padding: 12px;
  }

  .modal_footer {
    padding: 12px 14px 14px;
  }

  .section_card {
    padding: 12px;
    border-radius: 14px;
  }

  .role_card {
    padding: 12px;
    border-radius: 14px;
  }

  .summary_line {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .card_actions,
  .modal_actions,
  .role_actions,
  .footer_actions {
    width: 100%;
  }

  .card_actions button,
  .modal_actions .ghost_btn,
  .role_actions button,
  .footer_actions button {
    flex: 1 1 auto;
    min-width: 0;
  }

  .close_btn {
    flex: 0 0 34px;
  }
}

@media (max-width: 420px) {
  .modal_actions .ghost_btn,
  .role_actions button,
  .card_actions button,
  .footer_actions button {
    width: 100%;
    flex-basis: 100%;
  }

  .modal_actions .close_btn {
    width: 100%;
    flex-basis: 100%;
  }
}
</style>
