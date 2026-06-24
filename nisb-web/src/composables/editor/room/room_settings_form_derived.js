import { computed } from 'vue'

export function use_room_settings_form_derived({
  t,
  form,
  roles,
  workspace_options,
  safe_array,
  safe_string,
  normalize_focus_root_client,
  normalize_skill_ids_client,
  normalize_supervisor_skill_strategy_client,
  normalize_worker_concurrency_client,
}) {
  const workspace_options_for_select = computed(() => {
    const list = safe_array(workspace_options.value)
    const wid = safe_string(form.workspace_id).trim()

    if (!wid) return list
    if (list.some((item) => safe_string(item?.id).trim() === wid)) return list

    const fallback_name = safe_string(form.workspace_name).trim() || wid
    return [
      ...list,
      {
        id: wid,
        name: fallback_name,
        description: '',
        icon: '',
        display_name: t('room.settingsForm.workspace.currentBoundDisplayName', {
          name: fallback_name,
        }),
      },
    ]
  })

  const selected_workspace_option = computed(() => {
    const wid = safe_string(form.workspace_id).trim()
    return safe_array(workspace_options.value)
      .find((item) => safe_string(item?.id).trim() === wid) || null
  })

  const selected_workspace_display_name = computed(() => {
    return safe_string(
      selected_workspace_option.value?.display_name ||
      selected_workspace_option.value?.name ||
      form.workspace_name ||
      form.workspace_id
    ).trim()
  })

  const normalized_workspace_id_preview = computed(() => (
    safe_string(form.workspace_id).trim()
  ))

  const normalized_focus_root_preview = computed(() => (
    normalize_focus_root_client(form.focus_root)
  ))

  const enabled_supervisor_skill_count = computed(() => (
    normalize_skill_ids_client(form.enabled_supervisor_skill_ids).length
  ))

  function role_label(role) {
    return String(
      role?.name ||
      role?.slug ||
      role?.role_id ||
      t('room.settingsForm.defaults.roleFallback')
    )
  }

  function normalize_worker_concurrency_for_summary(value) {
    if (typeof normalize_worker_concurrency_client === 'function') {
      return normalize_worker_concurrency_client(value, 1)
    }

    const raw = Number(value)
    if (!Number.isFinite(raw)) return 1

    return Math.min(4, Math.max(1, Math.trunc(raw)))
  }

  const worker_concurrency_value = computed(() => {
    return normalize_worker_concurrency_for_summary(form.max_worker_concurrency)
  })

  function append_worker_concurrency_summary(text) {
    const base = safe_string(text).trim()
    const suffix = t('room.settingsForm.summaries.workerConcurrencySuffix', {
      value: worker_concurrency_value.value,
    })

    return `${base} ${suffix}`.trim()
  }

  const default_role_label = computed(() => {
    const role_id = safe_string(form.default_reply_role_id).trim()
    if (!role_id) return t('room.settingsOrchestrationCard.common.emptyOption')
    const role = roles.value.find((item) => safe_string(item?.role_id) === role_id)
    return role_label(role || { role_id })
  })

  const show_supervisor_settings = computed(() => {
    return form.reply_mode === 'supervisor' ||
      form.reply_mode === 'supervisor_direct' ||
      !!form.supervisor_enabled
  })

  const reply_mode_supervisor_warning = computed(() => {
    return form.reply_mode === 'supervisor' &&
      !!safe_string(form.default_reply_role_id).trim()
  })

  const reply_mode_supervisor_direct_warning = computed(() => {
    return form.reply_mode === 'supervisor_direct' && (
      !!safe_string(form.default_reply_role_id).trim() ||
      (Array.isArray(form.active_roles) && form.active_roles.length > 0)
    )
  })

  const reply_mode_direct_role_warning = computed(() => {
    return form.reply_mode === 'direct_role' &&
      !safe_string(form.default_reply_role_id).trim()
  })

  const orchestration_summary = computed(() => {
    const provider = safe_string(form.supervisor_provider).trim()
      || t('room.settingsModal.common.defaultProvider')
    const model = safe_string(form.supervisor_model).trim()
      || t('room.settingsModal.common.systemDefault')
    const strategy = normalize_supervisor_skill_strategy_client(
      form.supervisor_skill_strategy,
      'builtin_plus_custom'
    )

    if (form.reply_mode === 'manual') {
      if (form.supervisor_enabled) {
        return append_worker_concurrency_summary(
          t('room.settingsForm.summaries.manualWithSupervisor')
        )
      }

      return append_worker_concurrency_summary(
        t('room.settingsForm.summaries.manual')
      )
    }

    if (form.reply_mode === 'supervisor_direct') {
      return append_worker_concurrency_summary(
        t('room.settingsForm.summaries.supervisorDirect', {
          provider,
          model,
          strategy,
        })
      )
    }

    if (form.reply_mode === 'supervisor') {
      return append_worker_concurrency_summary(
        t('room.settingsForm.summaries.supervisor', {
          provider,
          model,
          strategy,
        })
      )
    }

    if (form.reply_mode === 'direct_role') {
      if (form.default_reply_role_id) {
        return append_worker_concurrency_summary(
          t('room.settingsForm.summaries.directRoleWithRole', {
            role: default_role_label.value,
          })
        )
      }

      return append_worker_concurrency_summary(
        t('room.settingsForm.summaries.directRoleWithoutRole')
      )
    }

    return append_worker_concurrency_summary(
      t('room.settingsForm.summaries.unknown')
    )
  })

  return {
    workspace_options_for_select,
    selected_workspace_display_name,
    normalized_workspace_id_preview,
    normalized_focus_root_preview,
    enabled_supervisor_skill_count,
    role_label,
    default_role_label,
    show_supervisor_settings,
    reply_mode_supervisor_warning,
    reply_mode_supervisor_direct_warning,
    reply_mode_direct_role_warning,
    worker_concurrency_value,
    orchestration_summary,
  }
}
