import {
  safe_object,
  safe_string,
  normalize_bool,
  normalize_int,
} from './room_shared'
import {
  assert_tool_success,
  is_cancellation_like_error,
} from './room_protocol'
import {
  extract_room_info,
  extract_room_items_bundle,
  extract_room_runtime_bundle,
  extract_room_runtime_replay_bundle,
} from './room_extractors'
import {
  normalize_room_items_cursor,
  normalize_room_items_bundle_payload,
  normalize_room_runtime_bundle_payload,
  normalize_room_runtime_replay_bundle_payload,
  normalize_runtime_state,
  normalize_runtime_order,
  normalize_runtime_view_mode,
} from './room_normalizers'
import {
  merge_runtime_events,
} from './room_event_helpers'
import {
  DEFAULT_ITEMS_PAGING,
} from './room_state'

async function call_room_loader_tool(ctx, callTool, tool, args = {}, opts = {}) {
  if (typeof callTool === 'function') {
    return await callTool(tool, args, opts)
  }
  if (typeof ctx?.callRoomTool === 'function') {
    return await ctx.callRoomTool(callTool, tool, args, opts)
  }
  throw new Error(`room loader tool unavailable: ${String(tool || '').trim()}`)
}

function debug_room_runtime_loader(tag, payload = {}) {
  try {
    console.debug(`[room-runtime-loader] ${tag}`, JSON.parse(JSON.stringify(payload)))
  } catch {
    console.debug(`[room-runtime-loader] ${tag}`, payload)
  }
}

function get_runtime_loader_call(callTool, ctx) {
  if (typeof callTool === 'function') {
    return callTool
  }
  return async (toolName, toolArgs = {}, toolOpts = {}) =>
    await call_room_loader_tool(ctx, callTool, toolName, toolArgs, toolOpts)
}

function get_replay_tail_event_id_for_request(runtime_state, request_run_id, opts = {}) {
  const explicit_tail_event_id = safe_string(opts?.tail_event_id).trim()
  if (explicit_tail_event_id) return explicit_tail_event_id

  const selected_run_id = safe_string(runtime_state?.selected_run_id).trim()
  const current_tail_event_id = safe_string(runtime_state?.tail_event_id).trim()

  if (!request_run_id || !selected_run_id || !current_tail_event_id) return ''
  if (selected_run_id !== request_run_id) return ''
  return current_tail_event_id
}

function get_preserved_tail_event_id_for_current_refresh(runtime_state) {
  const view_mode = normalize_runtime_view_mode(runtime_state?.view_mode, 'current')
  if (view_mode !== 'replay') return ''
  return safe_string(runtime_state?.tail_event_id).trim()
}

export const room_loader_actions = {
  async refreshWhoAmI(callTool, opts = {}) {
    const raw = await call_room_loader_tool(this, callTool, 'nisb_room_shared_whoami', {}, opts)
    const data = assert_tool_success(raw, '加载用户信息失败')
    return this.setWhoAmI(data)
  },

  async refreshRoomInfo(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) return null

    this.refreshing = true
    this.error = ''

    try {
      const raw = await call_room_loader_tool(
        this,
        callTool,
        'nisb_room_get_info',
        { room_id: rid },
        opts
      )
      const data = assert_tool_success(raw, '加载房间信息失败')
      const info = extract_room_info(data)

      this.roomId = rid
      this.hydrateLastWorkspaceSave(rid)
      this.setRoomInfo(info)
      this.syncRuntimeRunStateFromRoomState()
      this.error = ''

      if (opts?.apply_workspace_context === true) {
        this.emitApplyWorkspaceContextToUi()
      }

      return info
    } catch (err) {
      if (is_cancellation_like_error(err)) {
        this.error = ''
        return {
          room: this.room,
          roles: this.roles,
          state: this.roomState,
          cancelled: true,
        }
      }
      this.error = err?.message || String(err)
      throw err
    } finally {
      this.refreshing = false
    }
  },

  async refreshRoomItems(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) return normalize_room_items_bundle_payload({})

    const append_mode = safe_string(opts?.append_mode).trim() === 'prepend' ? 'prepend' : 'replace'
    const request_limit = normalize_int(opts?.limit, 200) || 200
    const request_order = safe_string(opts?.order).trim().toLowerCase() === 'desc' ? 'desc' : 'asc'
    const request_relation_expand =
      opts?.relation_expand === undefined ? true : normalize_bool(opts?.relation_expand, true)
    const request_byte_budget = normalize_int(opts?.byte_budget, 524288) || 524288
    const existing_cursor = normalize_room_items_cursor(this.itemsPaging?.next_cursor)
    const request_cursor =
      append_mode === 'prepend'
        ? normalize_room_items_cursor(opts?.cursor || existing_cursor)
        : normalize_room_items_cursor(opts?.cursor)
    const request_before_event_id =
      append_mode === 'prepend'
        ? safe_string(opts?.before_event_id || request_cursor.before_event_id).trim()
        : safe_string(opts?.before_event_id).trim()

    if (append_mode === 'prepend') {
      this.itemsPaging = {
        ...DEFAULT_ITEMS_PAGING(),
        ...safe_object(this.itemsPaging),
        loading_older: true,
      }
    } else {
      this.refreshing = true
    }

    this.error = ''

    try {
      const raw = await call_room_loader_tool(
        this,
        callTool,
        'nisb_room_shared_recent',
        {
          room_id: rid,
          limit: request_limit,
          order: request_order,
          cursor: request_cursor,
          before_event_id: request_before_event_id,
          relation_expand: request_relation_expand,
          byte_budget: request_byte_budget,
        },
        opts
      )
      const data = assert_tool_success(raw, '加载房间消息失败')
      const bundle = extract_room_items_bundle(data)

      this.roomId = rid
      this.hydrateLastWorkspaceSave(rid)
      this.setItemsBundle(bundle, { append_mode })
      this.error = ''

      return {
        ...bundle,
        items: this.items,
      }
    } catch (err) {
      if (append_mode === 'prepend') {
        this.itemsPaging = {
          ...DEFAULT_ITEMS_PAGING(),
          ...safe_object(this.itemsPaging),
          loading_older: false,
        }
      }

      if (is_cancellation_like_error(err)) {
        this.error = ''
        return {
          ...normalize_room_items_bundle_payload({
            items: this.items,
            has_more: this.itemsPaging?.has_more,
            next_cursor: this.itemsPaging?.next_cursor,
            source: this.itemsPaging?.source,
            returned_count: this.items.length,
            limit: this.itemsPaging?.limit,
            order: this.itemsPaging?.order,
          }),
          cancelled: true,
        }
      }

      this.error = err?.message || String(err)
      throw err
    } finally {
      if (append_mode !== 'prepend') {
        this.refreshing = false
      }
    }
  },

  async loadOlderRoomItems(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) {
      return {
        items: this.items,
        has_more: false,
        next_cursor: {},
      }
    }

    if (this.itemsPaging?.loading_older) {
      return {
        ...this.itemsPagingState,
        items: this.items,
      }
    }

    if (!this.itemsPaging?.has_more) {
      return {
        ...this.itemsPagingState,
        items: this.items,
      }
    }

    return await this.refreshRoomItems(callTool, rid, {
      ...opts,
      append_mode: 'prepend',
      cursor: opts?.cursor || this.itemsPaging?.next_cursor,
      before_event_id: safe_string(opts?.before_event_id || this.itemsPaging?.next_cursor?.before_event_id).trim(),
      order: 'asc',
      limit: normalize_int(opts?.limit, this.itemsPaging?.limit || 80) || 80,
      relation_expand:
        opts?.relation_expand === undefined
          ? normalize_bool(this.itemsPaging?.relation_expand, true)
          : normalize_bool(opts?.relation_expand, true),
      byte_budget: normalize_int(opts?.byte_budget, this.itemsPaging?.byte_budget || 524288) || 524288,
    })
  },

  async refreshRuntimeEvents(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) return normalize_room_runtime_bundle_payload({})

    const reset = normalize_bool(opts?.reset, false)
    const silent = normalize_bool(opts?.silent, false)

    const current_runtime = normalize_runtime_state(this.runtime)
    const prev_run_id = safe_string(current_runtime.run_id).trim()
    const current_run_from_state = safe_string(this.roomState?.current_run_id).trim()
    const current_run_status_from_state = safe_string(this.roomState?.current_run_status).trim().toLowerCase()
    const preserved_replay_tail_event_id = get_preserved_tail_event_id_for_current_refresh(current_runtime)

    const include_all_runs =
      opts?.include_all_runs === undefined
        ? normalize_bool(current_runtime.include_all_runs, false)
        : normalize_bool(opts?.include_all_runs, false)

    const request_limit =
      normalize_int(opts?.limit, reset ? 160 : 120) || (reset ? 160 : 120)

    const request_order = normalize_runtime_order(
      opts?.order === undefined ? current_runtime.order : opts?.order,
      current_runtime.order || 'asc'
    )

    const explicit_run_id = safe_string(opts?.run_id).trim()
    const request_run_id =
      include_all_runs
        ? ''
        : explicit_run_id || current_run_from_state || (!reset ? prev_run_id : '')

    const run_switched =
      !include_all_runs &&
      !!request_run_id &&
      request_run_id !== prev_run_id

    const request_after_event_id =
      reset || run_switched
        ? ''
        : safe_string(
            opts?.after_event_id ||
            current_runtime.latest_event_id
          ).trim()

    if (reset || run_switched) {
      this.runtime = normalize_runtime_state(
        {
          ...current_runtime,
          items: [],
          loading: !silent,
          loaded_once: false,
          error: '',
          run_id: request_run_id,
          latest_event_id: '',
          tail_event_id: preserved_replay_tail_event_id,
          include_all_runs,
          order: request_order,
          live_hint: current_run_status_from_state === 'running',
          formal_runtime_packet: {},
          runtime_control_snapshot: {},
          formal_runtime_status: '',
          latest_formal_runtime_packet_at: '',
        },
        current_runtime
      )
    } else {
      this.runtime = normalize_runtime_state(
        {
          ...current_runtime,
          loading: !silent || !current_runtime.loaded_once,
          error: '',
          include_all_runs,
          order: request_order,
          run_id: request_run_id || current_runtime.run_id,
          tail_event_id: preserved_replay_tail_event_id || current_runtime.tail_event_id,
          live_hint: current_run_status_from_state === 'running',
        },
        current_runtime
      )
    }

    try {
      const args = {
        room_id: rid,
        limit: request_limit,
        order: request_order,
        include_all_runs,
      }

      if (request_run_id) {
        args.run_id = request_run_id
      }

      if (request_after_event_id) {
        args.after_event_id = request_after_event_id
      }

      debug_room_runtime_loader('events_recent.request', {
        room_id: rid,
        store_room_id: this.roomId,
        owner_room_id: this?.federationRoomSession?.owner_room_id || '',
        peer_id: this?.federationRoomSession?.peer_id || '',
        run_id: args.run_id || '',
        after_event_id: args.after_event_id || '',
        include_all_runs,
        order: request_order,
        limit: request_limit,
      })

      const runtimeCall = get_runtime_loader_call(callTool, this)
      const raw = await runtimeCall(
        'nisb_room_events_recent',
        args,
        opts
      )

      const data = assert_tool_success(raw, '加载运行过程失败')
      const bundle = extract_room_runtime_bundle(data)

      const latest_runtime = normalize_runtime_state(this.runtime)
      const latest_room_run_id = safe_string(this.roomState?.current_run_id).trim()

      const incoming_run_id =
        include_all_runs
          ? ''
          : safe_string(
              bundle.run_id ||
              request_run_id ||
              latest_room_run_id ||
              prev_run_id
            ).trim()

      const latest_runtime_run_id = safe_string(latest_runtime.run_id).trim()
      const response_run_switched =
        !include_all_runs &&
        !!incoming_run_id &&
        incoming_run_id !== prev_run_id

      const stale_current_response =
        !include_all_runs &&
        !!latest_runtime_run_id &&
        !!request_run_id &&
        latest_runtime_run_id !== request_run_id &&
        latest_runtime_run_id !== incoming_run_id

      if (stale_current_response) {
        return {
          ...normalize_room_runtime_bundle_payload({
            items: latest_runtime.items,
            run_id: latest_runtime.run_id,
            latest_event_id: latest_runtime.latest_event_id,
            include_all_runs: latest_runtime.include_all_runs,
            order: latest_runtime.order,
            limit: latest_runtime.limit,
            returned_count: latest_runtime.returned_count,
            after_event_found: latest_runtime.after_event_found,
          }),
          ignored: true,
        }
      }

      let next_items = []

      if (reset || run_switched || response_run_switched) {
        next_items = merge_runtime_events([], bundle.items, 'replace')
      } else if (!include_all_runs && request_after_event_id && bundle.after_event_found === false) {
        next_items = merge_runtime_events([], bundle.items, 'replace')
      } else {
        next_items = merge_runtime_events(latest_runtime.items, bundle.items, 'merge')
      }

      const last_item = next_items[next_items.length - 1]
      const next_latest_event_id = safe_string(bundle.latest_event_id || last_item?.id).trim()
      const latest_run_status_from_state = safe_string(this.roomState?.current_run_status).trim().toLowerCase()

      this.runtime = normalize_runtime_state(
        {
          ...latest_runtime,
          items: next_items,
          loading: false,
          loaded_once: true,
          error: '',
          include_all_runs,
          order: request_order,
          run_id: incoming_run_id,
          latest_event_id: next_latest_event_id,
          tail_event_id: preserved_replay_tail_event_id || next_latest_event_id,
          live_hint: latest_run_status_from_state === 'running',
          last_loaded_at: new Date().toISOString(),
          limit: bundle.limit || request_limit,
          returned_count: bundle.returned_count,
          after_event_found: bundle.after_event_found,
          formal_runtime_packet: bundle.formal_runtime_packet,
          runtime_control_snapshot: bundle.runtime_control_snapshot,
          formal_runtime_status: bundle.formal_runtime_status,
          latest_formal_runtime_packet_at: bundle.latest_formal_runtime_packet_at,
        },
        latest_runtime
      )

      return {
        ...normalize_room_runtime_bundle_payload(bundle),
        items: this.runtime.items,
      }
    } catch (err) {
      debug_room_runtime_loader('events_recent.error', {
        room_id: rid,
        store_room_id: this.roomId,
        owner_room_id: this?.federationRoomSession?.owner_room_id || '',
        peer_id: this?.federationRoomSession?.peer_id || '',
        message: err?.message || String(err),
      })

      const latest_runtime = normalize_runtime_state(this.runtime, current_runtime)
      const latest_run_status_from_state = safe_string(this.roomState?.current_run_status).trim().toLowerCase()

      if (is_cancellation_like_error(err)) {
        this.runtime = normalize_runtime_state(
          {
            ...latest_runtime,
            loading: false,
            tail_event_id: preserved_replay_tail_event_id || latest_runtime.tail_event_id,
            live_hint: latest_run_status_from_state === 'running',
          },
          latest_runtime
        )

        return {
          ...normalize_room_runtime_bundle_payload({
            items: this.runtime.items,
            run_id: this.runtime.run_id,
            latest_event_id: this.runtime.latest_event_id,
            include_all_runs: this.runtime.include_all_runs,
            order: this.runtime.order,
            limit: this.runtime.limit,
            returned_count: this.runtime.returned_count,
            after_event_found: this.runtime.after_event_found,
          }),
          cancelled: true,
        }
      }

      this.runtime = normalize_runtime_state(
        {
          ...latest_runtime,
          loading: false,
          loaded_once: true,
          error: err?.message || String(err),
          tail_event_id: preserved_replay_tail_event_id || safe_string(latest_runtime.tail_event_id).trim(),
          live_hint: latest_run_status_from_state === 'running',
        },
        latest_runtime
      )
      throw err
    }
  },

  async refreshRuntimeReplay(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) return normalize_room_runtime_replay_bundle_payload({})

    const current_runtime = normalize_runtime_state(this.runtime)
    const silent = normalize_bool(opts?.silent, false)
    const set_view_mode =
      opts?.set_view_mode === undefined ? true : normalize_bool(opts?.set_view_mode, true)

    const previous_selected_run_id = safe_string(current_runtime.selected_run_id).trim()

    const request_run_id = safe_string(
      opts?.run_id ||
      opts?.selected_run_id ||
      previous_selected_run_id ||
      this.latestCompletedRunId ||
      current_runtime.run_id ||
      this.roomState?.current_run_id
    ).trim()

    if (!request_run_id) {
      const latest_runtime = normalize_runtime_state(this.runtime)
      this.runtime = normalize_runtime_state({
        ...latest_runtime,
        replay_loading: false,
        replay_loaded_once: false,
        replay_error: '',
        selected_run_id: '',
        tail_event_id: '',
        replay_bundle: normalize_room_runtime_replay_bundle_payload({}),
      }, latest_runtime)
      return normalize_room_runtime_replay_bundle_payload({})
    }

    const replay_run_switched =
      !!previous_selected_run_id &&
      previous_selected_run_id !== request_run_id

    this.runtime = normalize_runtime_state({
      ...current_runtime,
      view_mode: set_view_mode ? 'replay' : normalize_runtime_view_mode(current_runtime.view_mode, 'current'),
      selected_run_id: request_run_id,
      tail_event_id: replay_run_switched ? '' : safe_string(current_runtime.tail_event_id).trim(),
      replay_loading: !silent,
      replay_error: '',
      replay_loaded_once: replay_run_switched ? false : current_runtime.replay_loaded_once,
      replay_bundle: replay_run_switched
        ? normalize_room_runtime_replay_bundle_payload({})
        : normalize_room_runtime_replay_bundle_payload(current_runtime.replay_bundle),
    }, current_runtime)

    try {
      const args = {
        room_id: rid,
        run_id: request_run_id,
      }

      const request_tail_event_id = get_replay_tail_event_id_for_request(this.runtime, request_run_id, opts)
      if (request_tail_event_id) {
        args.tail_event_id = request_tail_event_id
      }

      debug_room_runtime_loader('events_replay.request', {
        room_id: rid,
        store_room_id: this.roomId,
        owner_room_id: this?.federationRoomSession?.owner_room_id || '',
        peer_id: this?.federationRoomSession?.peer_id || '',
        run_id: request_run_id,
        tail_event_id: args.tail_event_id || '',
      })

      const runtimeCall = get_runtime_loader_call(callTool, this)
      const raw = await runtimeCall(
        'nisb_room_events_replay',
        args,
        opts
      )

      const data = assert_tool_success(raw, '加载运行回放失败')
      const bundle = extract_room_runtime_replay_bundle(data)

      const latest_runtime = normalize_runtime_state(this.runtime)
      const active_selected_run_id = safe_string(latest_runtime.selected_run_id).trim()

      if (active_selected_run_id && active_selected_run_id !== request_run_id) {
        return {
          ...normalize_room_runtime_replay_bundle_payload(latest_runtime.replay_bundle),
          ignored: true,
        }
      }

      this.runtime = normalize_runtime_state({
        ...latest_runtime,
        view_mode: set_view_mode ? 'replay' : latest_runtime.view_mode,
        selected_run_id: safe_string(bundle.run_id || request_run_id).trim(),
        tail_event_id: safe_string(bundle.tail_event_id || bundle.latest_event_id || '').trim(),
        replay_loading: false,
        replay_loaded_once: true,
        replay_error: '',
        replay_bundle: bundle,
      }, latest_runtime)

      return {
        ...normalize_room_runtime_replay_bundle_payload(bundle),
        cancelled: false,
      }
    } catch (err) {
      debug_room_runtime_loader('events_replay.error', {
        room_id: rid,
        store_room_id: this.roomId,
        owner_room_id: this?.federationRoomSession?.owner_room_id || '',
        peer_id: this?.federationRoomSession?.peer_id || '',
        run_id: request_run_id,
        message: err?.message || String(err),
      })

      const latest_runtime = normalize_runtime_state(this.runtime, current_runtime)

      if (is_cancellation_like_error(err)) {
        const active_selected_run_id = safe_string(latest_runtime.selected_run_id).trim()

        if (active_selected_run_id && active_selected_run_id !== request_run_id) {
          return {
            ...normalize_room_runtime_replay_bundle_payload(latest_runtime.replay_bundle),
            cancelled: true,
            ignored: true,
          }
        }

        this.runtime = normalize_runtime_state({
          ...latest_runtime,
          replay_loading: false,
          selected_run_id: request_run_id,
          tail_event_id: replay_run_switched ? '' : safe_string(latest_runtime.tail_event_id).trim(),
        }, latest_runtime)

        return {
          ...normalize_room_runtime_replay_bundle_payload(latest_runtime.replay_bundle),
          cancelled: true,
        }
      }

      const active_selected_run_id = safe_string(latest_runtime.selected_run_id).trim()

      if (active_selected_run_id && active_selected_run_id !== request_run_id) {
        return {
          ...normalize_room_runtime_replay_bundle_payload(latest_runtime.replay_bundle),
          ignored: true,
        }
      }

      this.runtime = normalize_runtime_state({
        ...latest_runtime,
        replay_loading: false,
        replay_loaded_once: true,
        replay_error: err?.message || String(err),
        selected_run_id: request_run_id,
        tail_event_id: replay_run_switched ? '' : safe_string(latest_runtime.tail_event_id).trim(),
      }, latest_runtime)

      throw err
    }
  },

  async loadRoomBundle(callTool, room_id, opts = {}) {
    const rid = String(room_id || this.roomId || '').trim()
    if (!rid) return null

    this.loading = true
    this.error = ''
    this.roomId = rid
    this.hydrateLastWorkspaceSave(rid)
    this.resetItemsPaging()
    this.resetRuntime({
      preserve_expanded: true,
      preserve_include_all_runs: true,
      preserve_order: true,
    })

    try {
      const [rawInfo, rawItems] = await Promise.all([
        call_room_loader_tool(
          this,
          callTool,
          'nisb_room_get_info',
          { room_id: rid },
          opts
        ),
        call_room_loader_tool(
          this,
          callTool,
          'nisb_room_shared_recent',
          {
            room_id: rid,
            limit: normalize_int(opts?.limit, 200) || 200,
            order: safe_string(opts?.order).trim().toLowerCase() === 'desc' ? 'desc' : 'asc',
            relation_expand:
              opts?.relation_expand === undefined ? true : normalize_bool(opts?.relation_expand, true),
            byte_budget: normalize_int(opts?.byte_budget, 524288) || 524288,
          },
          opts
        ),
      ])

      const infoData = assert_tool_success(rawInfo, '加载房间信息失败')
      const itemsData = assert_tool_success(rawItems, '加载房间消息失败')

      const info = extract_room_info(infoData)
      const itemsBundle = extract_room_items_bundle(itemsData)

      this.setRoomInfo(info)
      this.setItemsBundle(itemsBundle, { append_mode: 'replace' })
      this.syncRuntimeRunStateFromRoomState()
      this.error = ''

      if (opts?.apply_workspace_context !== false) {
        this.emitApplyWorkspaceContextToUi()
      }

      return { info, items: this.items, itemsBundle: this.itemsPagingState }
    } catch (err) {
      if (is_cancellation_like_error(err)) {
        this.error = ''
        return {
          info: {
            room: this.room,
            roles: this.roles,
            state: this.roomState,
            cancelled: true,
          },
          items: this.items,
          itemsBundle: this.itemsPagingState,
        }
      }
      this.error = err?.message || String(err)
      throw err
    } finally {
      this.loading = false
    }
  },
}
