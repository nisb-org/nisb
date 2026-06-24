import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export function use_room_settings_external_mcp_publish({
  room_id_value,
  call_room_tool,
  dispatch_toast,
  safe_string,
  safe_array,
  safe_object,
  assert_tool_success,
  pick_first_tool_result,
  t: injected_t,
  translate,
  locale_value,
  settings_locale,
} = {}) {
  let i18n_t = null
  let i18n_locale = null

  try {
    const i18n = useI18n({ useScope: 'global' })
    i18n_t = i18n.t
    i18n_locale = i18n.locale
  } catch (_) {}

  function s(value) {
    if (typeof safe_string === 'function') return safe_string(value)
    if (value === undefined || value === null) return ''
    return String(value)
  }

  function obj(value) {
    if (typeof safe_object === 'function') return safe_object(value)
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  }

  function arr(value) {
    if (typeof safe_array === 'function') return safe_array(value)
    return Array.isArray(value) ? value : []
  }

  function format_template(template, vars = {}) {
    return s(template).replace(/\{([^}]+)\}/g, (_, key) => {
      const value = vars?.[key]
      return value === undefined || value === null ? '' : String(value)
    })
  }

  function stored_locale() {
    if (typeof localStorage === 'undefined') return ''

    try {
      const raw = localStorage.getItem('nisb_settings_v2')
      if (!raw) return ''
      const parsed = JSON.parse(raw)
      return s(parsed?.locale).trim()
    } catch (_) {
      return ''
    }
  }

  function current_locale() {
    const raw = first_non_empty(
      locale_value?.value,
      locale_value,
      settings_locale?.value,
      settings_locale,
      i18n_locale?.value,
      stored_locale(),
      'en'
    )

    if (raw.toLowerCase().startsWith('zh')) return 'zh-CN'
    return 'en'
  }

  function pick_translate_function() {
    if (typeof injected_t === 'function') return injected_t
    if (typeof translate === 'function') return translate
    if (typeof i18n_t === 'function') return i18n_t
    return null
  }

  function tr(key, fallback = '', vars = {}) {
    const full_key = key.includes('.') ? key : `room.externalMcpPublish.${key}`
    const fn = pick_translate_function()

    if (fn) {
      try {
        const value = s(fn(full_key, vars)).trim()
        if (value && value !== full_key) return value
      } catch (_) {}
    }

    return format_template(fallback || full_key, vars)
  }

  function has_cjk(text) {
    return /[\u3400-\u9fff]/.test(s(text))
  }

  function visible_raw_text(value) {
    const text = s(value).trim()
    if (!text) return ''
    if (current_locale() !== 'zh-CN' && has_cjk(text)) return ''
    return text
  }

  function visible_error(value, fallback_key, fallback, vars = {}) {
    const row = obj(value)
    const raw = s(row?.message || row?.error || row?.detail || value?.message || value).trim()

    if (raw && !(current_locale() !== 'zh-CN' && has_cjk(raw))) {
      return raw
    }

    return tr(fallback_key, fallback, vars)
  }

  function localized_payload(base = {}) {
    return {
      ...obj(base),
      locale: current_locale(),
    }
  }

  function toast(message, type = 'info') {
    const text = s(message).trim()
    if (!text) return
    if (typeof dispatch_toast === 'function') {
      dispatch_toast(text, type)
    }
  }

  function default_external_mcp_client_label() {
    return tr('defaultClientLabel', 'External MCP client')
  }

  const external_mcp_publish_status = ref({})
  const external_mcp_publish_loading = ref(false)
  const external_mcp_publish_error = ref('')
  const external_mcp_publish_plaintext_token = ref('')
  const external_mcp_publish_last_config_kind = ref('')
  const external_mcp_publish_last_config_text = ref('')
  const external_mcp_publish_copy_loading_kind = ref('')
  const external_mcp_publish_enable_loading = ref(false)
  const external_mcp_publish_revoke_loading = ref(false)
  const external_mcp_publish_regenerate_loading = ref(false)

  const external_mcp_publish_expires_in_days = ref('30')
  const external_mcp_publish_max_calls = ref('')
  const external_mcp_publish_client_label = ref(default_external_mcp_client_label())
  const external_mcp_publish_endpoint_url = ref('')

  let last_default_client_label = external_mcp_publish_client_label.value

  watch(
    () => current_locale(),
    () => {
      const next_default = default_external_mcp_client_label()
      const current = s(external_mcp_publish_client_label.value).trim()

      if (!current || current === last_default_client_label) {
        external_mcp_publish_client_label.value = next_default
      }

      last_default_client_label = next_default
    }
  )

  function default_external_mcp_endpoint() {
    const configured = s(external_mcp_publish_endpoint_url.value).trim()
    if (configured) return configured

    if (typeof window !== 'undefined' && window.location?.origin) {
      return `${window.location.origin}/nisb/mcp`
    }

    return ''
  }

  function positive_int(value, fallback = 0) {
    const n = Number.parseInt(s(value).trim(), 10)
    if (Number.isFinite(n) && n > 0) return n
    return fallback
  }

  function positive_number(value, fallback = 0) {
    const text = s(value).trim()
    if (!text) return fallback

    const n = Number.parseFloat(text)
    if (Number.isFinite(n) && n > 0) return n

    return fallback
  }

  function is_past_timestamp(value) {
    const text = s(value).trim()
    if (!text) return false
    const t = Date.parse(text)
    if (!Number.isFinite(t)) return false
    return t > 0 && t <= Date.now()
  }

  function stringify_config(value) {
    if (!value) return ''
    if (typeof value === 'string') return value.trim()

    try {
      return JSON.stringify(value, null, 2)
    } catch (_) {
      return ''
    }
  }

  function parse_json_text(value) {
    const text = s(value).trim()
    if (!text) return {}
    try {
      const parsed = JSON.parse(text)
      return obj(parsed)
    } catch (_) {
      return {}
    }
  }

  function first_non_empty(...values) {
    for (const value of values) {
      const text = s(value).trim()
      if (text) return text
    }
    return ''
  }

  function first_config_value(...values) {
    for (const value of values) {
      if (!value) continue
      if (typeof value === 'string' && value.trim()) return value.trim()
      if (typeof value === 'object' && Object.keys(value).length) return value
    }
    return ''
  }

  function infer_publish_state(raw = {}) {
    const row = obj(raw)
    const explicit = s(
      row.status ||
      row.publish_state ||
      row.publication_state ||
      row.external_publish_state ||
      row.state ||
      ''
    ).trim().toLowerCase()

    if (['active', 'published', 'enabled'].includes(explicit)) return 'active'
    if (['revoked', 'disabled_revoked'].includes(explicit)) return 'revoked'
    if (['expired'].includes(explicit)) return 'expired'
    if (['not_published', 'unpublished', 'disabled', 'inactive', 'missing'].includes(explicit)) {
      return 'not_published'
    }

    if (s(row.revoked_at).trim()) return 'revoked'
    if (is_past_timestamp(row.expires_at)) return 'expired'

    const has_record = !!(
      s(row.publish_id).trim() ||
      s(row.token_hash).trim() ||
      s(row.provider_id).trim() ||
      s(row.source_room_id).trim()
    )

    return has_record ? 'active' : 'not_published'
  }

  function normalize_external_mcp_publish_record(raw = {}) {
    const row = obj(raw)
    const room_id = s(room_id_value?.value).trim()
    const source_room_id = first_non_empty(row.source_room_id, row.room_id, room_id)
    const provider_id = first_non_empty(row.provider_id, source_room_id ? `room_provider__${source_room_id}` : '')
    const publish_state = infer_publish_state(row)

    return {
      publish_id: s(row.publish_id).trim(),
      source_room_id,
      provider_id,
      owner_user_id: s(row.owner_user_id).trim(),
      token_hash: s(row.token_hash).trim(),
      publish_state,
      is_published: publish_state === 'active',
      is_revoked: publish_state === 'revoked',
      is_expired: publish_state === 'expired',
      created_at: s(row.created_at).trim(),
      updated_at: s(row.updated_at).trim(),
      expires_at: s(row.expires_at).trim(),
      revoked_at: s(row.revoked_at).trim(),
      allowed_mode: s(row.allowed_mode).trim() || 'ask_room',
      result_view: s(row.result_view).trim() || 'final_result_only',
      source_observation_allowed: !!row.source_observation_allowed,
      owner_private_scope_exposed: !!row.owner_private_scope_exposed,
      max_calls: row.max_calls === undefined || row.max_calls === null ? '' : String(row.max_calls),
      daily_call_limit: row.daily_call_limit === undefined || row.daily_call_limit === null ? '' : String(row.daily_call_limit),
      used_count: Number.isFinite(Number(row.used_count)) ? Number(row.used_count) : 0,
      last_used_at: s(row.last_used_at).trim(),
      client_label: s(row.client_label).trim(),
      endpoint_url: first_non_empty(
        row.endpoint_url,
        row.mcp_endpoint_url,
        row.url,
        default_external_mcp_endpoint()
      ),
      generic_mcp_config: first_config_value(
        row.generic_mcp_config,
        row.generic_config,
        row.mcp_config
      ),
      librechat_config: first_config_value(
        row.librechat_config,
        row.librechat_mcp_config
      ),
      message: visible_raw_text(row.message || row.status_message),
    }
  }

  const external_mcp_publish_record = computed(() => {
    return normalize_external_mcp_publish_record(external_mcp_publish_status.value)
  })

  const external_mcp_publish_state = computed(() => {
    return external_mcp_publish_record.value.publish_state
  })

  function extract_external_publish_payload(data = {}) {
    const picked = typeof pick_first_tool_result === 'function'
      ? pick_first_tool_result(
          data,
          (x) => {
            const type = s(x?.type).trim().toLowerCase()
            return (
              type === 'external_mcp_publish' ||
              type === 'room_mcp_external_publish' ||
              type === 'external_mcp_publish_status' ||
              !!x?.external_mcp_publish ||
              !!x?.publish ||
              !!x?.publication ||
              !!x?.publish_id ||
              !!x?.token_hash ||
              !!x?.plaintext_token
            )
          }
        )
      : null

    const payload = obj(picked || data)
    const parsed_text_payload = parse_json_text(payload.text)
    const nested = obj(
      payload.external_mcp_publish ||
      payload.room_mcp_external_publish ||
      payload.publish ||
      payload.publication ||
      payload.record ||
      parsed_text_payload.external_mcp_publish ||
      parsed_text_payload.publish ||
      parsed_text_payload.record ||
      parsed_text_payload ||
      {}
    )

    return obj({
      ...nested,
      plaintext_token: first_non_empty(
        payload.plaintext_token,
        payload.external_mcp_publish_token,
        payload.token,
        parsed_text_payload.plaintext_token,
        parsed_text_payload.external_mcp_publish_token,
        nested.plaintext_token,
        nested.external_mcp_publish_token
      ),
      external_mcp_publish_token: first_non_empty(
        payload.external_mcp_publish_token,
        payload.plaintext_token,
        payload.token,
        parsed_text_payload.external_mcp_publish_token,
        parsed_text_payload.plaintext_token,
        nested.external_mcp_publish_token,
        nested.plaintext_token
      ),
      access_token: first_non_empty(
        payload.access_token,
        parsed_text_payload.access_token,
        nested.access_token
      ),
      bearer_token: first_non_empty(
        payload.bearer_token,
        parsed_text_payload.bearer_token,
        nested.bearer_token
      ),
      plaintext_token_available: !!(
        payload.plaintext_token_available ||
        parsed_text_payload.plaintext_token_available ||
        nested.plaintext_token_available
      ),
      config: obj(
        payload.config ||
        parsed_text_payload.config ||
        nested.config
      ),
      generic_mcp_config: first_config_value(
        nested.generic_mcp_config,
        nested.generic_config,
        nested.mcp_config,
        payload.generic_mcp_config,
        payload.generic_config,
        payload.config?.generic_mcp_config,
        payload.config?.generic_mcp_config_json,
        parsed_text_payload.generic_mcp_config,
        parsed_text_payload.config?.generic_mcp_config,
        parsed_text_payload.config?.generic_mcp_config_json
      ),
      librechat_config: first_config_value(
        nested.librechat_config,
        nested.librechat_mcp_config,
        payload.librechat_config,
        payload.librechat_mcp_config,
        payload.config?.librechat_config,
        payload.config?.librechat_config_json,
        payload.config?.librechat_config_yaml,
        parsed_text_payload.librechat_config,
        parsed_text_payload.config?.librechat_config,
        parsed_text_payload.config?.librechat_config_json,
        parsed_text_payload.config?.librechat_config_yaml
      ),
    })
  }

  function extract_plaintext_token(payload = {}) {
    const row = obj(payload)
    return first_non_empty(
      row.external_mcp_publish_token,
      row.plaintext_token,
      row.token,
      row.access_token,
      row.bearer_token
    )
  }

  function apply_external_publish_payload(payload = {}, options = {}) {
    const { allow_plaintext_token = false } = obj(options)
    const row = obj(payload)
    const record = normalize_external_mcp_publish_record(row)
    const token = allow_plaintext_token ? extract_plaintext_token(row) : ''

    external_mcp_publish_status.value = record
    external_mcp_publish_error.value = ''

    if (token) {
      external_mcp_publish_plaintext_token.value = token
    } else if (!allow_plaintext_token) {
      external_mcp_publish_plaintext_token.value = ''
    }

    if (token) {
      const librechat_text = resolve_external_mcp_publish_config_text('librechat', {
        record,
        token,
        allow_backend_config: true,
      })
      const generic_text = resolve_external_mcp_publish_config_text('generic', {
        record,
        token,
        allow_backend_config: true,
      })

      external_mcp_publish_last_config_kind.value = 'librechat'
      external_mcp_publish_last_config_text.value = librechat_text || generic_text
    }

    return record
  }

  function reset_external_mcp_publish_state(options = {}) {
    const { clear_token = true } = obj(options)

    external_mcp_publish_status.value = {}
    external_mcp_publish_loading.value = false
    external_mcp_publish_error.value = ''
    external_mcp_publish_copy_loading_kind.value = ''
    external_mcp_publish_enable_loading.value = false
    external_mcp_publish_revoke_loading.value = false
    external_mcp_publish_regenerate_loading.value = false

    if (clear_token) {
      external_mcp_publish_plaintext_token.value = ''
      external_mcp_publish_last_config_kind.value = ''
      external_mcp_publish_last_config_text.value = ''
    }
  }

  function build_external_publish_mutation_payload(input = {}) {
    const row = obj(input)
    const room_id = s(row.room_id || room_id_value?.value).trim()

    const expires_in_days = positive_number(
      row.expires_in_days === undefined ? external_mcp_publish_expires_in_days.value : row.expires_in_days,
      0
    )

    const max_calls_was_provided = Object.prototype.hasOwnProperty.call(row, 'max_calls')
    const max_calls_source = max_calls_was_provided
      ? row.max_calls
      : external_mcp_publish_max_calls.value
    const max_calls_text = s(max_calls_source).trim()

    const daily_call_limit = positive_int(row.daily_call_limit, 0)
    const client_label = first_non_empty(
      row.client_label,
      external_mcp_publish_client_label.value,
      default_external_mcp_client_label()
    )
    const endpoint_url = first_non_empty(row.endpoint_url, external_mcp_publish_endpoint_url.value, default_external_mcp_endpoint())

    const payload = { room_id }

    if (expires_in_days > 0) payload.expires_in_days = expires_in_days

    if (max_calls_was_provided || max_calls_text) {
      payload.max_calls = max_calls_text
    }

    if (daily_call_limit > 0) payload.daily_call_limit = daily_call_limit
    if (client_label) payload.client_label = client_label
    if (endpoint_url) payload.endpoint_url = endpoint_url

    return localized_payload(payload)
  }

  function build_generic_mcp_config_text(record = {}, token = '') {
    const row = normalize_external_mcp_publish_record(record)
    const endpoint = first_non_empty(row.endpoint_url, default_external_mcp_endpoint(), '<external_mcp_endpoint>')
    const bearer = token || '<external_mcp_publish_token>'

    return JSON.stringify({
      type: 'streamable-http',
      url: endpoint,
      headers: {
        Authorization: `Bearer ${bearer}`,
      },
    }, null, 2)
  }

  function build_librechat_config_text(record = {}, token = '') {
    const row = normalize_external_mcp_publish_record(record)
    const endpoint = first_non_empty(row.endpoint_url, default_external_mcp_endpoint(), '<external_mcp_endpoint>')
    const bearer = token || '<external_mcp_publish_token>'

    return JSON.stringify({
      mcpServers: {
        nisb_room: {
          type: 'streamable-http',
          url: endpoint,
          headers: {
            Authorization: `Bearer ${bearer}`,
          },
        },
      },
    }, null, 2)
  }

  function resolve_external_mcp_publish_config_text(kind = 'generic', options = {}) {
    const row = obj(options)
    const record = normalize_external_mcp_publish_record(row.record || external_mcp_publish_status.value)
    const token = s(row.token || external_mcp_publish_plaintext_token.value).trim()
    const allow_backend_config = row.allow_backend_config !== false

    if (token) {
      if (kind === 'librechat') {
        return build_librechat_config_text(record, token)
      }

      return build_generic_mcp_config_text(record, token)
    }

    if (allow_backend_config) {
      if (kind === 'librechat') {
        const text = stringify_config(record.librechat_config)
        if (text) return text
      }

      const generic_text = stringify_config(record.generic_mcp_config)
      if (generic_text) return generic_text
    }

    if (kind === 'librechat') {
      return build_librechat_config_text(record, '')
    }

    return build_generic_mcp_config_text(record, '')
  }

  async function copy_text_to_clipboard(text = '') {
    const value = s(text).trim()
    if (!value) return false

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }

    if (typeof document !== 'undefined') {
      const textarea = document.createElement('textarea')
      textarea.value = value
      textarea.setAttribute('readonly', 'readonly')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      const copied = document.execCommand('copy')
      document.body.removeChild(textarea)
      return !!copied
    }

    return false
  }

  async function load_external_mcp_publish(options = {}) {
    const { silent = true } = obj(options)
    const room_id = s(room_id_value?.value).trim()

    if (!room_id) {
      reset_external_mcp_publish_state()
      return {}
    }

    external_mcp_publish_loading.value = true
    external_mcp_publish_error.value = ''

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_external_publish_get', localized_payload({ room_id })),
        tr('loadStatusFailed', 'Failed to load external MCP publish status')
      )

      const payload = extract_external_publish_payload(data)
      const record = apply_external_publish_payload(payload, {
        allow_plaintext_token: false,
      })

      return record
    } catch (error) {
      const text = visible_error(
        error,
        'loadStatusFailed',
        'Failed to load external MCP publish status'
      )
      external_mcp_publish_error.value = text
      external_mcp_publish_status.value = normalize_external_mcp_publish_record({
        source_room_id: room_id,
        publish_state: 'not_published',
        message: text,
      })

      if (!silent) {
        toast(text, 'error')
      }

      return external_mcp_publish_status.value
    } finally {
      external_mcp_publish_loading.value = false
    }
  }

  async function handle_external_mcp_publish_enable(input = {}) {
    const payload = build_external_publish_mutation_payload(input)

    if (!payload.room_id) {
      toast(tr('missingRoomIdEnable', 'Missing room_id, unable to enable external MCP publishing'), 'error')
      return {}
    }

    external_mcp_publish_enable_loading.value = true
    external_mcp_publish_error.value = ''
    external_mcp_publish_plaintext_token.value = ''
    external_mcp_publish_last_config_kind.value = ''
    external_mcp_publish_last_config_text.value = ''

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_external_publish_enable', payload),
        tr('enableFailed', 'Failed to enable external MCP publishing')
      )

      const result_payload = extract_external_publish_payload(data)
      const record = apply_external_publish_payload(result_payload, {
        allow_plaintext_token: true,
      })

      toast(tr('enableSuccess', 'External MCP publishing is enabled. The token will only be shown once.'), 'success')
      return record
    } catch (error) {
      const text = visible_error(
        error,
        'enableFailed',
        'Failed to enable external MCP publishing'
      )
      external_mcp_publish_error.value = text
      toast(text, 'error')
      return {}
    } finally {
      external_mcp_publish_enable_loading.value = false
    }
  }

  async function handle_external_mcp_publish_revoke() {
    const room_id = s(room_id_value?.value).trim()

    if (!room_id) {
      toast(tr('missingRoomIdRevoke', 'Missing room_id, unable to revoke external MCP publishing'), 'error')
      return false
    }

    external_mcp_publish_revoke_loading.value = true
    external_mcp_publish_error.value = ''

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_external_publish_revoke', localized_payload({ room_id })),
        tr('revokeFailed', 'Failed to revoke external MCP publishing')
      )

      const payload = extract_external_publish_payload(data)
      const fallback = {
        ...obj(external_mcp_publish_status.value),
        ...obj(payload),
        revoked_at: first_non_empty(payload.revoked_at, new Date().toISOString()),
        publish_state: 'revoked',
      }

      apply_external_publish_payload(fallback, {
        allow_plaintext_token: false,
      })

      external_mcp_publish_plaintext_token.value = ''
      external_mcp_publish_last_config_kind.value = ''
      external_mcp_publish_last_config_text.value = ''

      toast(tr('revokeSuccess', 'External MCP publishing has been revoked.'), 'success')
      return true
    } catch (error) {
      const text = visible_error(
        error,
        'revokeFailed',
        'Failed to revoke external MCP publishing'
      )
      external_mcp_publish_error.value = text
      toast(text, 'error')
      return false
    } finally {
      external_mcp_publish_revoke_loading.value = false
    }
  }

  async function handle_external_mcp_publish_regenerate(input = {}) {
    const payload = build_external_publish_mutation_payload(input)

    if (!payload.room_id) {
      toast(tr('missingRoomIdRegenerate', 'Missing room_id, unable to regenerate the token'), 'error')
      return {}
    }

    external_mcp_publish_regenerate_loading.value = true
    external_mcp_publish_error.value = ''
    external_mcp_publish_plaintext_token.value = ''
    external_mcp_publish_last_config_kind.value = ''
    external_mcp_publish_last_config_text.value = ''

    try {
      const data = assert_tool_success(
        await call_room_tool('nisb_room_mcp_external_publish_regenerate', payload),
        tr('regenerateFailed', 'Failed to regenerate the external MCP token')
      )

      const result_payload = extract_external_publish_payload(data)
      const record = apply_external_publish_payload(result_payload, {
        allow_plaintext_token: true,
      })

      toast(tr('regenerateSuccess', 'A new external MCP token has been generated. The old token should stop working immediately.'), 'success')
      return record
    } catch (error) {
      const text = visible_error(
        error,
        'regenerateFailed',
        'Failed to regenerate the external MCP token'
      )
      external_mcp_publish_error.value = text
      toast(text, 'error')
      return {}
    } finally {
      external_mcp_publish_regenerate_loading.value = false
    }
  }

  async function handle_external_mcp_publish_copy_config(kind = 'generic') {
    const normalized_kind = kind === 'librechat' ? 'librechat' : 'generic'
    external_mcp_publish_copy_loading_kind.value = normalized_kind
    external_mcp_publish_error.value = ''

    try {
      const text = resolve_external_mcp_publish_config_text(normalized_kind, {
        allow_backend_config: true,
      })

      if (!text) {
        throw new Error(tr('noConfigToCopy', 'There is no MCP configuration to copy'))
      }

      const copied = await copy_text_to_clipboard(text)
      if (!copied) {
        throw new Error(tr('clipboardUnsupported', 'This environment does not support copying to the clipboard'))
      }

      external_mcp_publish_last_config_kind.value = normalized_kind
      external_mcp_publish_last_config_text.value = text

      toast(
        normalized_kind === 'librechat'
          ? tr('copyLibrechatSuccess', 'MCP client configuration copied.')
          : tr('copyGenericSuccess', 'Generic MCP configuration copied.'),
        'success'
      )

      return true
    } catch (error) {
      const text = visible_error(
        error,
        'copyConfigFailed',
        'Failed to copy MCP configuration'
      )
      external_mcp_publish_error.value = text
      toast(text, 'error')
      return false
    } finally {
      external_mcp_publish_copy_loading_kind.value = ''
    }
  }

  async function handle_external_mcp_publish_copy_token() {
    const token = s(external_mcp_publish_plaintext_token.value).trim()

    if (!token) {
      toast(tr('noPlaintextTokenToCopy', 'There is no plaintext token to copy. After refresh, the token will not be shown again.'), 'error')
      return false
    }

    try {
      const copied = await copy_text_to_clipboard(token)
      if (!copied) {
        throw new Error(tr('clipboardUnsupported', 'This environment does not support copying to the clipboard'))
      }

      toast(tr('copyTokenSuccess', 'External MCP token copied.'), 'success')
      return true
    } catch (error) {
      const text = visible_error(
        error,
        'copyTokenFailed',
        'Failed to copy token'
      )
      external_mcp_publish_error.value = text
      toast(text, 'error')
      return false
    }
  }

  async function refresh_external_mcp_publish(options = {}) {
    return load_external_mcp_publish(options)
  }

  return {
    external_mcp_publish_status,
    external_mcp_publish_record,
    external_mcp_publish_state,
    external_mcp_publish_loading,
    external_mcp_publish_error,
    external_mcp_publish_plaintext_token,
    external_mcp_publish_last_config_kind,
    external_mcp_publish_last_config_text,
    external_mcp_publish_copy_loading_kind,
    external_mcp_publish_enable_loading,
    external_mcp_publish_revoke_loading,
    external_mcp_publish_regenerate_loading,
    external_mcp_publish_expires_in_days,
    external_mcp_publish_max_calls,
    external_mcp_publish_client_label,
    external_mcp_publish_endpoint_url,

    reset_external_mcp_publish_state,
    load_external_mcp_publish,
    refresh_external_mcp_publish,
    handle_external_mcp_publish_enable,
    handle_external_mcp_publish_revoke,
    handle_external_mcp_publish_regenerate,
    handle_external_mcp_publish_copy_config,
    handle_external_mcp_publish_copy_token,
    resolve_external_mcp_publish_config_text,
  }
}
