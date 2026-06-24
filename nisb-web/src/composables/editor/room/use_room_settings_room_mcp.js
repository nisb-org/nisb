import { ref } from 'vue'

export function use_room_settings_room_mcp({
  form,
  room_id_value,
  call_room_tool,
  dispatch_toast,
  safe_string,
  safe_array,
  safe_object,
  assert_tool_success,
  pick_first_tool_result,
  normalize_reply_mode_client,
}) {
  const room_mcp_publication = ref({})
  const room_mcp_share_ref_preview = ref('')
  const room_mcp_share_ref_loading = ref(false)
  const room_mcp_share_ref_error = ref('')
  const room_mcp_share_ref_last_issued_at = ref('')
  const room_mcp_share_ref_status = ref({})
  const room_mcp_grants = ref([])
  const room_mcp_grants_loading = ref(false)
  const room_mcp_grants_status = ref({})
  const room_mcp_grant_revoke_loading_id = ref('')

  function build_room_mcp_boundary_hint_local() {
    const reply_mode = normalize_reply_mode_client(form.reply_mode, 'manual')
    const shared_room_enabled = !!form.shared_room_config_enabled
    const shared_supervisor_enabled = !!form.shared_supervisor_enabled

    if (!shared_room_enabled) {
      return [
        'shared_room_config=false',
        `reply_mode=${reply_mode}`,
        'room-configured shared capability may resolve to no-auto-reply/manual semantics',
        'owner_private_scope_exposed=false',
      ].join('; ')
    }

    return [
      'shared_room_config=true',
      `reply_mode=${reply_mode}`,
      `shared_supervisor=${shared_supervisor_enabled ? 'true' : 'false'}`,
      'room-configured shared capability only',
      'owner_private_scope_exposed=false',
    ].join('; ')
  }

  function build_local_room_mcp_publication_fallback() {
    const room_id = safe_string(room_id_value.value).trim()
    const publish_enabled = !!form.room_mcp_provider_enabled
    const publish_label = safe_string(form.room_mcp_provider_name).trim()
    const publish_summary = safe_string(form.room_mcp_provider_summary).trim()

    return {
      provider_id: room_id ? `room_provider__${room_id}` : '',
      source_room_id: room_id,
      publish_enabled,
      publish_label,
      publish_summary,
      boundary_hint: build_room_mcp_boundary_hint_local(),
      visibility_mode: 'room_visible_and_grant_capable',
      publication_state: publish_enabled ? 'active' : 'disabled',
      published_at: '',
      updated_at: '',
    }
  }

  function normalize_room_mcp_publication_client(raw = {}) {
    const row = safe_object(raw)
    const fallback = build_local_room_mcp_publication_fallback()
    const publish_enabled = row.publish_enabled === undefined
      ? !!fallback.publish_enabled
      : !!row.publish_enabled

    let publication_state = safe_string(row.publication_state).trim().toLowerCase()
    if (publication_state !== 'active' && publication_state !== 'disabled') {
      publication_state = publish_enabled ? 'active' : 'disabled'
    }

    return {
      provider_id: safe_string(row.provider_id).trim() || fallback.provider_id,
      source_room_id: safe_string(row.source_room_id).trim() || fallback.source_room_id,
      publish_enabled,
      publish_label: safe_string(row.publish_label).trim() || fallback.publish_label,
      publish_summary: safe_string(row.publish_summary).trim() || fallback.publish_summary,
      boundary_hint: safe_string(row.boundary_hint).trim() || fallback.boundary_hint,
      visibility_mode: safe_string(row.visibility_mode).trim() || fallback.visibility_mode,
      publication_state,
      published_at: safe_string(row.published_at || row.created_at).trim() || fallback.published_at,
      updated_at: safe_string(row.updated_at).trim() || fallback.updated_at,
    }
  }

  function normalize_room_mcp_grant_scope_client(raw = {}) {
    const row = safe_object(raw)
    const result_view = safe_string(row.result_view).trim()

    return {
      result_view: result_view === 'full_result' ? 'full_result' : 'final_result_only',
      bind_as_worker: row.bind_as_worker === undefined ? true : !!row.bind_as_worker,
      observe_source_room: !!row.observe_source_room,
    }
  }

  function normalize_room_mcp_grant_audience_client(raw = {}) {
    const row = safe_object(raw)
    const peer_id = safe_string(
      row.peer_id || row.remote_peer_id || row.target_peer_id || row.federation_peer_id
    ).trim()
    const consumer_room_id = safe_string(row.consumer_room_id).trim()
    const remote_user_id = safe_string(row.remote_user_id).trim()
    const uid = safe_string(row.uid || row.user_id || row.target_user_id).trim()

    let type = safe_string(row.type).trim()
    if (!type) {
      if (consumer_room_id) type = 'consumer_room'
      else if (peer_id) type = 'peer_consumer'
      else if (remote_user_id) type = 'remote_user'
      else if (uid) type = 'target_user'
      else type = 'share_ref_bearer'
    }

    return {
      type,
      peer_id,
      remote_peer_id: safe_string(row.remote_peer_id || peer_id).trim(),
      target_peer_id: safe_string(row.target_peer_id || peer_id).trim(),
      source_peer_id: safe_string(row.source_peer_id).trim(),
      federation_peer_id: safe_string(row.federation_peer_id || peer_id).trim(),
      remote_user_id,
      consumer_room_id,
      uid,
      remote_label: safe_string(row.remote_label || row.label).trim(),
      note: safe_string(row.note).trim(),
    }
  }

  function normalize_room_mcp_grant_route_identity_client(raw = {}, audience = {}) {
    const row = safe_object(raw)
    const aud = normalize_room_mcp_grant_audience_client(audience)
    const peer_id = safe_string(
      row.peer_id || row.remote_peer_id || row.target_peer_id || row.federation_peer_id || aud.peer_id
    ).trim()

    return {
      peer_id,
      remote_peer_id: safe_string(row.remote_peer_id || aud.remote_peer_id || peer_id).trim(),
      target_peer_id: safe_string(row.target_peer_id || aud.target_peer_id || peer_id).trim(),
      source_peer_id: safe_string(row.source_peer_id || aud.source_peer_id).trim(),
      federation_peer_id: safe_string(row.federation_peer_id || aud.federation_peer_id || peer_id).trim(),
      remote_user_id: safe_string(row.remote_user_id || aud.remote_user_id).trim(),
      consumer_room_id: safe_string(row.consumer_room_id || aud.consumer_room_id).trim(),
      uid: safe_string(row.uid || aud.uid).trim(),
      remote_label: safe_string(row.remote_label || aud.remote_label).trim(),
    }
  }

  function normalize_room_mcp_grant_row_client(raw = {}) {
    const row = safe_object(raw)
    const scope = normalize_room_mcp_grant_scope_client(row.scope)
    const audience = normalize_room_mcp_grant_audience_client(row.audience)
    const route_identity = normalize_room_mcp_grant_route_identity_client(
      row.route_identity || row,
      audience
    )

    const revoked_at = safe_string(row.revoked_at).trim()
    const expires_at = safe_string(row.expires_at).trim()

    let grant_state = safe_string(row.grant_state || row.state).trim().toLowerCase()
    if (!grant_state) {
      if (revoked_at) grant_state = 'revoked'
      else grant_state = 'active'
    }
    if (!['active', 'revoked', 'expired', 'resolved', 'consumed', 'denied'].includes(grant_state)) {
      grant_state = revoked_at ? 'revoked' : 'active'
    }

    return {
      grant_id: safe_string(row.grant_id).trim(),
      artifact_id: safe_string(row.artifact_id).trim(),
      provider_id: safe_string(row.provider_id).trim(),
      source_room_id: safe_string(row.source_room_id).trim() || safe_string(room_id_value.value).trim(),
      grant_mode: safe_string(row.grant_mode).trim() || 'share_artifact',
      discovery_mode: safe_string(row.discovery_mode).trim() || 'granted_visible',
      grant_state,
      audience,
      scope,
      issued_at: safe_string(row.issued_at).trim(),
      expires_at,
      revocable: row.revocable === undefined ? true : !!row.revocable,
      revoked_at,
      revoked_by: safe_string(row.revoked_by).trim(),
      descriptor_ref: safe_string(row.descriptor_ref).trim(),
      boundary_hint: safe_string(row.boundary_hint).trim(),
      resolution_source: safe_string(row.resolution_source).trim() || 'grant_artifact',
      last_resolved_at: safe_string(row.last_resolved_at).trim(),
      last_consumed_at: safe_string(row.last_consumed_at).trim(),
      external_result_view: safe_string(row.external_result_view).trim() || scope.result_view,
      source_observation_allowed: !!row.source_observation_allowed,
      route_identity,
    }
  }

  function normalize_room_mcp_grants_status_client(raw = {}, grantsValue = []) {
    const row = safe_object(raw)
    const grants = safe_array(grantsValue)

    const total = Number.isFinite(Number(row.total)) ? Number(row.total) : grants.length
    const active = Number.isFinite(Number(row.active))
      ? Number(row.active)
      : grants.filter((item) => safe_string(item?.grant_state).trim() === 'active').length
    const revoked = Number.isFinite(Number(row.revoked))
      ? Number(row.revoked)
      : grants.filter((item) => safe_string(item?.grant_state).trim() === 'revoked').length
    const expired = Number.isFinite(Number(row.expired))
      ? Number(row.expired)
      : grants.filter((item) => safe_string(item?.grant_state).trim() === 'expired').length
    const other = Number.isFinite(Number(row.other))
      ? Number(row.other)
      : Math.max(0, total - active - revoked - expired)

    return {
      total,
      active,
      revoked,
      expired,
      other,
      updated_at: safe_string(row.updated_at).trim(),
      status: safe_string(row.status).trim() || 'success',
      message: safe_string(row.message).trim(),
    }
  }

  function extract_room_mcp_publication_payload(data = {}) {
    const row = pick_first_tool_result(
      data,
      (x) => safe_string(x?.type).trim().toLowerCase() === 'room_mcp_publication'
    )

    const payload = safe_object(row || data)
    return normalize_room_mcp_publication_client(
      payload.publication || payload.room_mcp_publication || payload
    )
  }

  function extract_room_mcp_grants_payload(data = {}) {
    const row = pick_first_tool_result(
      data,
      (x) => safe_string(x?.type).trim().toLowerCase() === 'room_mcp_grants'
    )

    const payload = safe_object(row || data)
    const grants = safe_array(payload.grants).map((item) => normalize_room_mcp_grant_row_client(item))
    const status = normalize_room_mcp_grants_status_client(payload, grants)

    return { grants, status }
  }

  function build_room_mcp_share_ref_status_payload(next = {}) {
    const src = safe_object(next)
    return {
      code: safe_string(src.code).trim(),
      status: safe_string(src.status).trim(),
      message: safe_string(src.message).trim(),
      issued_at: safe_string(src.issued_at).trim(),
      provider_id: safe_string(src.provider_id).trim(),
      provider_name: safe_string(src.provider_name).trim(),
      source_room_id: safe_string(src.source_room_id).trim(),
      grant: normalize_room_mcp_grant_row_client(src.grant),
      artifact: safe_object(src.artifact),
      publication: normalize_room_mcp_publication_client(src.publication),
    }
  }

  function resolve_room_mcp_grant_key(item = {}) {
    const row = safe_object(item)
    return safe_string(row.grant_id || row.artifact_id).trim()
  }

  function reset_room_mcp_publication_state({ keep_form_fallback = false } = {}) {
    room_mcp_publication.value = keep_form_fallback
      ? build_local_room_mcp_publication_fallback()
      : {}
  }

  function reset_room_mcp_share_ref_state() {
    room_mcp_share_ref_preview.value = ''
    room_mcp_share_ref_loading.value = false
    room_mcp_share_ref_error.value = ''
    room_mcp_share_ref_last_issued_at.value = ''
    room_mcp_share_ref_status.value = {}
  }

  function reset_room_mcp_grants_state() {
    room_mcp_grants.value = []
    room_mcp_grants_loading.value = false
    room_mcp_grants_status.value = normalize_room_mcp_grants_status_client({
      total: 0,
      active: 0,
      revoked: 0,
      expired: 0,
      other: 0,
      status: 'idle',
      message: '',
      updated_at: '',
    }, [])
    room_mcp_grant_revoke_loading_id.value = ''
  }

  function sync_room_mcp_publication_ui_fallback() {
    room_mcp_publication.value = normalize_room_mcp_publication_client(room_mcp_publication.value)
  }

  async function load_room_mcp_publication(options = {}) {
    const { silent = false } = safe_object(options)
    const room_id = safe_string(room_id_value.value).trim()

    if (!room_id) {
      reset_room_mcp_publication_state({ keep_form_fallback: false })
      return {}
    }

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_publication_get', { room_id }),
        '加载 publication 失败'
      )

      const publication = extract_room_mcp_publication_payload(data)
      room_mcp_publication.value = publication
      return publication
    } catch (error) {
      const fallback = build_local_room_mcp_publication_fallback()
      room_mcp_publication.value = fallback
      if (!silent) {
        room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
          ...safe_object(room_mcp_share_ref_status.value),
          code: 'warning',
          status: 'warning',
          message: safe_string(error?.message || error || '加载 publication 失败').trim(),
          publication: fallback,
        })
      }
      return fallback
    }
  }

  async function handle_room_mcp_grant_list_refresh(options = {}) {
    const { silent = false } = safe_object(options)
    const room_id = safe_string(room_id_value.value).trim()

    if (!room_id) {
      reset_room_mcp_grants_state()
      return []
    }

    room_mcp_grants_loading.value = true
    room_mcp_grants_status.value = normalize_room_mcp_grants_status_client({
      ...safe_object(room_mcp_grants_status.value),
      status: 'loading',
      message: '',
    }, room_mcp_grants.value)

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_grant_list', { room_id }),
        '加载 grant 列表失败'
      )

      const { grants, status } = extract_room_mcp_grants_payload(data)
      room_mcp_grants.value = grants
      room_mcp_grants_status.value = status
      return grants
    } catch (error) {
      room_mcp_grants.value = []
      room_mcp_grants_status.value = normalize_room_mcp_grants_status_client({
        total: 0,
        active: 0,
        revoked: 0,
        expired: 0,
        other: 0,
        status: 'error',
        message: safe_string(error?.message || error || '加载 grant 列表失败').trim(),
      }, [])
      if (!silent) {
        dispatch_toast(
          safe_string(error?.message || error || '加载 grant 列表失败').trim(),
          'error'
        )
      }
      return []
    } finally {
      room_mcp_grants_loading.value = false
    }
  }

  async function handle_room_mcp_share_ref_generate() {
    room_mcp_share_ref_loading.value = true
    room_mcp_share_ref_error.value = ''
    room_mcp_share_ref_status.value = {}

    try {
      const room_id = safe_string(room_id_value.value).trim()
      if (!room_id) {
        throw new Error('缺少 room_id，无法生成 artifact')
      }

      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_share_ref_issue', { room_id }),
        '生成 artifact 失败'
      )

      const row = pick_first_tool_result(
        data,
        (x) => (
          safe_string(x?.type).trim().toLowerCase() === 'room_mcp_share_ref' ||
          !!safe_string(x?.share_ref).trim() ||
          !!safe_string(x?.ref).trim()
        )
      )

      const payload = safe_object(row || data)
      const share_ref = safe_string(
        payload.share_ref ||
        payload.ref ||
        payload.shareRef
      ).trim()

      if (!share_ref) {
        throw new Error('后端已返回，但未提供 artifact / share ref')
      }

      const grant = normalize_room_mcp_grant_row_client(payload.grant || payload)
      const artifact = safe_object(payload.artifact)
      const publication = normalize_room_mcp_publication_client(payload.publication || room_mcp_publication.value)

      const issued_at = safe_string(
        grant.issued_at ||
        artifact.issued_at ||
        payload.issued_at ||
        payload.generated_at ||
        payload.updated_at
      ).trim()

      const provider_id = safe_string(
        payload.provider_id ||
        artifact.provider_id ||
        grant.provider_id ||
        publication.provider_id
      ).trim()

      room_mcp_share_ref_preview.value = share_ref
      room_mcp_share_ref_last_issued_at.value = issued_at
      room_mcp_share_ref_error.value = ''
      room_mcp_publication.value = publication
      room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
        code: 'success',
        status: 'success',
        message: safe_string(payload.message || payload.status_message).trim()
          || 'artifact 已生成，可复制给 consumer 侧粘贴导入。',
        issued_at,
        provider_id,
        provider_name: safe_string(payload.provider_name).trim(),
        source_room_id: safe_string(
          payload.source_room_id ||
          artifact.source_room_id ||
          grant.source_room_id ||
          room_id
        ).trim(),
        grant,
        artifact,
        publication,
      })

      await refresh_room_mcp_owner_state({ silent: true })
      return share_ref
    } catch (error) {
      room_mcp_share_ref_error.value = safe_string(
        error?.message || error || '生成 artifact 失败'
      )
      room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
        code: 'error',
        status: 'error',
        message: room_mcp_share_ref_error.value,
        publication: room_mcp_publication.value,
      })
      return ''
    } finally {
      room_mcp_share_ref_loading.value = false
    }
  }

  async function handle_room_mcp_share_ref_copy(value = '') {
    const text = safe_string(value || room_mcp_share_ref_preview.value).trim()

    if (!text) {
      room_mcp_share_ref_error.value = '当前没有可复制的 artifact / share ref'
      room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
        ...safe_object(room_mcp_share_ref_status.value),
        code: 'error',
        status: 'error',
        message: room_mcp_share_ref_error.value,
      })
      return false
    }

    room_mcp_share_ref_error.value = ''

    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
          ...safe_object(room_mcp_share_ref_status.value),
          code: 'success',
          status: 'success',
          message: 'artifact 已复制。',
        })
        return true
      }

      if (typeof document !== 'undefined') {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'readonly')
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
          ...safe_object(room_mcp_share_ref_status.value),
          code: 'success',
          status: 'success',
          message: 'artifact 已复制。',
        })
        return true
      }

      throw new Error('当前环境不支持复制到剪贴板')
    } catch (error) {
      room_mcp_share_ref_error.value = safe_string(
        error?.message || error || '复制 artifact 失败'
      )
      room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
        ...safe_object(room_mcp_share_ref_status.value),
        code: 'error',
        status: 'error',
        message: room_mcp_share_ref_error.value,
      })
      return false
    }
  }

  async function handle_room_mcp_grant_revoke(input = {}) {
    const room_id = safe_string(room_id_value.value).trim()
    const payload = safe_object(input)
    const grant = normalize_room_mcp_grant_row_client(payload.grant || payload)
    const grant_id = safe_string(payload.grant_id || grant.grant_id).trim()
    const artifact_id = safe_string(payload.artifact_id || grant.artifact_id).trim()
    const loading_id = resolve_room_mcp_grant_key({ grant_id, artifact_id })

    if (!room_id) {
      dispatch_toast('缺少 room_id，无法撤销 grant', 'error')
      return false
    }
    if (!grant_id && !artifact_id) {
      dispatch_toast('缺少 grant_id 或 artifact_id，无法撤销 grant', 'error')
      return false
    }

    room_mcp_grant_revoke_loading_id.value = loading_id

    try {
      assert_tool_success(
        await call_room_tool('nisb_room_mcp_grant_revoke', {
          room_id,
          grant_id,
          artifact_id,
        }),
        '撤销 grant 失败'
      )

      const current_status = safe_object(room_mcp_share_ref_status.value)
      const current_grant = normalize_room_mcp_grant_row_client(current_status.grant)
      if (current_grant.grant_id && current_grant.grant_id === grant_id) {
        room_mcp_share_ref_status.value = build_room_mcp_share_ref_status_payload({
          ...current_status,
          grant: {
            ...current_grant,
            grant_state: 'revoked',
          },
          message: '当前 artifact 对应 grant 已撤销。',
        })
      }

      await refresh_room_mcp_owner_state({ silent: true })
      dispatch_toast('grant 已撤销', 'success')
      return true
    } catch (error) {
      dispatch_toast(
        safe_string(error?.message || error || '撤销 grant 失败').trim(),
        'error'
      )
      return false
    } finally {
      room_mcp_grant_revoke_loading_id.value = ''
    }
  }

  async function refresh_room_mcp_owner_state(options = {}) {
    const { silent = true } = safe_object(options)
    await load_room_mcp_publication({ silent })
    await handle_room_mcp_grant_list_refresh({ silent })
  }

  return {
    room_mcp_publication,
    room_mcp_share_ref_preview,
    room_mcp_share_ref_loading,
    room_mcp_share_ref_error,
    room_mcp_share_ref_last_issued_at,
    room_mcp_share_ref_status,
    room_mcp_grants,
    room_mcp_grants_loading,
    room_mcp_grants_status,
    room_mcp_grant_revoke_loading_id,
    reset_room_mcp_publication_state,
    reset_room_mcp_share_ref_state,
    reset_room_mcp_grants_state,
    sync_room_mcp_publication_ui_fallback,
    load_room_mcp_publication,
    handle_room_mcp_grant_list_refresh,
    handle_room_mcp_share_ref_generate,
    handle_room_mcp_share_ref_copy,
    handle_room_mcp_grant_revoke,
    refresh_room_mcp_owner_state,
  }
}
