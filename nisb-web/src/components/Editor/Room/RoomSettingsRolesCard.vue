<template>
  <section class="section_card">
    <div class="section_head">
      <div>
        <div class="section_title">
          {{ t('room.settingsRolesCard.title') }}
        </div>
        <div class="section_subtitle">
          {{ t('room.settingsRolesCard.subtitle') }}
        </div>
      </div>

      <div class="section_actions">
        <button
          class="ghost_btn"
          type="button"
          :disabled="props.busy || !props.roles.length || !props.can_manage_room_roles"
          @click="props.select_all_roles"
        >
          {{ t('room.settingsRolesCard.actions.selectAll') }}
        </button>
        <button
          class="ghost_btn"
          type="button"
          :disabled="props.busy || !props.roles.length || !props.can_manage_room_roles"
          @click="props.clear_active_roles"
        >
          {{ t('room.settingsRolesCard.actions.clear') }}
        </button>
        <button
          class="ghost_btn"
          type="button"
          :disabled="props.busy || !props.roles.length || !props.form.default_reply_role_id || !props.can_manage_room_roles"
          @click="props.keep_only_default_role"
        >
          {{ t('room.settingsRolesCard.actions.keepOnlyDefault') }}
        </button>
      </div>
    </div>

    <div class="helper_text">
      {{
        t('room.settingsRolesCard.summary', {
          active: active_role_count,
          total: props.roles.length,
        })
      }}
    </div>

    <div v-if="props.is_explicit_member_readonly" class="warning_box warning_box_info">
      当前账号不是房主；你可以查看 room roles 的启用状态与 shared 标识，但不能修改 active roles 或 default reply role。
    </div>

    <div v-if="!props.roles.length" class="empty_block">
      {{ t('room.settingsRolesCard.empty') }}
    </div>

    <div v-else class="role_grid">
      <div
        v-for="role in props.roles"
        :key="String(role.role_id || '')"
        class="role_card"
        :class="{
          active: props.is_role_active(role.role_id),
          default_role: props.form.default_reply_role_id === String(role.role_id || ''),
          disabled_role: role.enabled === false,
        }"
      >
        <div class="role_card_top">
          <label class="role_checkbox_line" :class="{ readonly_line: !props.can_manage_room_roles }">
            <input
              type="checkbox"
              :checked="props.is_role_active(role.role_id)"
              :disabled="props.busy || !props.can_manage_room_roles"
              @change="props.can_manage_room_roles && props.toggle_active_role(role.role_id)"
            />
            <span class="role_identity">
              <span class="role_avatar">{{ String(role.avatar || '🤖') }}</span>
              <span class="role_name_wrap">
                <strong class="role_name">
                  {{ String(role.name || role.slug || role.role_id || t('room.settingsRolesCard.role.fallbackName')) }}
                </strong>
                <span class="role_slug">@{{ String(role.slug || role.role_id || '') }}</span>
              </span>
            </span>
          </label>

          <button
            class="mini_btn"
            type="button"
            :disabled="props.busy || !props.can_manage_room_roles"
            @click="props.can_manage_room_roles && props.set_default_role(role.role_id)"
          >
            {{
              props.form.default_reply_role_id === String(role.role_id || '')
                ? t('room.settingsRolesCard.actions.defaultCurrent')
                : t('room.settingsRolesCard.actions.setDefault')
            }}
          </button>
        </div>

        <div class="role_meta_row">
          <span
            v-if="props.form.default_reply_role_id === String(role.role_id || '')"
            class="tag tag_default"
          >
            {{ t('room.settingsRolesCard.tags.defaultReply') }}
          </span>
          <span v-if="props.is_role_active(role.role_id)" class="tag tag_active">
            {{ t('room.settingsRolesCard.tags.active') }}
          </span>
          <span v-if="props.is_role_shared(role.role_id)" class="tag">
            shared
          </span>
          <span v-if="role.enabled === false" class="tag tag_disabled">
            {{ t('room.settingsRolesCard.tags.disabled') }}
          </span>
        </div>

        <div class="role_prompt_preview">
          {{ String(role.system_prompt || t('room.settingsRolesCard.role.emptyPrompt')) }}
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  form: { type: Object, required: true },
  roles: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },

  can_manage_room_roles: { type: Boolean, default: false },
  is_room_owner: { type: Boolean, default: false },
  is_explicit_member_readonly: { type: Boolean, default: false },
  is_role_shared: { type: Function, default: () => false },

  is_role_active: { type: Function, required: true },
  toggle_active_role: { type: Function, required: true },
  select_all_roles: { type: Function, required: true },
  clear_active_roles: { type: Function, required: true },
  keep_only_default_role: { type: Function, required: true },
  set_default_role: { type: Function, required: true },
})

const { t } = useI18n()

const active_role_count = computed(() => {
  return Array.isArray(props.form?.active_roles) ? props.form.active_roles.length : 0
})
</script>
