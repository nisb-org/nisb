import { describe, it, expect, vi } from 'vitest'

vi.mock('../room_event_helpers', () => {
  function normalizeEvt(evt) {
    return evt && typeof evt === 'object' ? { ...evt } : {}
  }

  function byTsAsc(a, b) {
    const ats = String(a?.ts || '')
    const bts = String(b?.ts || '')
    if (ats !== bts) return ats.localeCompare(bts)
    return String(a?.id || '').localeCompare(String(b?.id || ''))
  }

  return {
    sort_room_items: (list) => (Array.isArray(list) ? [...list].sort(byTsAsc) : []),
    sort_runtime_events: (list) => (Array.isArray(list) ? [...list].sort(byTsAsc) : []),
    normalize_room_runtime_event: normalizeEvt,
    get_runtime_result_event_from_list: (list) => {
      const rows = Array.isArray(list) ? [...list] : []
      const finalEvt = rows.findLast?.((x) => String(x?.type || '').trim() === 'room.final')
      if (finalEvt) return { ...finalEvt }
      const last = rows.length ? rows[rows.length - 1] : null
      return last && typeof last === 'object' ? { ...last } : null
    },
  }
})

import {
  normalize_tool_results,
  unwrap_tool_result,
  assert_tool_success,
} from '../room_protocol'
import {
  normalize_room_state,
  normalize_room_runtime_bundle_payload,
  normalize_room_runtime_replay_bundle_payload,
} from '../room_normalizers'
import {
  extract_room_runtime_bundle,
  extract_room_runtime_replay_bundle,
  extract_room_info,
  extract_whoami,
} from '../room_extractors'

describe('room runtime contract', () => {
  it('normalizes nested tool_results and unwraps the meaningful payload object', () => {
    const raw = {
      status: 'success',
      tool_results: [
        {
          type: 'room_info',
          payload: {
            room: { room_id: 'room_1', title: '测试房间' },
            roles: [{ role_id: 'role_1' }],
            state: { reply_mode: 'supervisor' },
          },
        },
      ],
    }

    const rows = normalize_tool_results(raw)
    const unwrapped = unwrap_tool_result(raw)
    const info = extract_room_info(raw)

    expect(rows).toHaveLength(1)
    expect(rows[0].payload.room.room_id).toBe('room_1')
    expect(unwrapped.room.room_id).toBe('room_1')
    expect(info.room.title).toBe('测试房间')
    expect(info.roles).toHaveLength(1)
    expect(info.state.reply_mode).toBe('supervisor')
  })

  it('assert_tool_success follows formal-first status and throws normalized error messages', () => {
    const ok = assert_tool_success({
      status: 'warning',
      message: '部分成功',
      tool_results: [],
    })

    expect(ok.status).toBe('warning')

    expect(() =>
      assert_tool_success({
        status: 'error',
        response: '显式失败',
        tool_results: [],
      })
    ).toThrow('显式失败')

    expect(() =>
      assert_tool_success({
        tool_results: [{ payload: { success: false, message: '内部失败' } }],
      })
    ).toThrow('操作失败')
  })

  it('normalizes room state and keeps workspace/focus_root boundary defaults formal-first', () => {
    const state = normalize_room_state({
      active_roles: ['role_a', 'role_a', 'role_b'],
      supervisor_enabled: true,
      reply_mode: '',
      inherit_workspace_context: undefined,
      inherit_focus_root: undefined,
      focus_root: '//agent_files///books/信息论/测试//',
      mcp_overrides: {
        fs_read_enabled: 'true',
        fs_read_scope: 'user_ro',
        notebook_write_enabled: 1,
        notebook_dir: '///_room_supervisor_notebooks///',
        notebook_filename: 'supervisor',
      },
    })

    expect(state.reply_mode).toBe('supervisor')
    expect(state.active_roles).toEqual(['role_a', 'role_b'])
    expect(state.inherit_workspace_context).toBe(true)
    expect(state.inherit_focus_root).toBe(true)
    expect(state.focus_root).toBe('agent_files/books/信息论/测试')
    expect(state.mcp_overrides.fs_read_enabled).toBe(true)
    expect(state.mcp_overrides.fs_read_scope).toBe('user_ro')
    expect(state.mcp_overrides.notebook_write_enabled).toBe(true)
    expect(state.mcp_overrides.notebook_dir).toBe('_room_supervisor_notebooks')
    expect(state.mcp_overrides.notebook_filename).toBe('supervisor.md')
  })

  it('extracts and normalizes current runtime bundle from tool_results payload', () => {
    const raw = {
      tool_results: [
        {
          type: 'room_runtime_events',
          payload: {
            items: [
              { id: 'evt-2', type: 'room.final', ts: '2026-03-29T20:10:02+00:00' },
              { id: 'evt-1', type: 'room.plan', ts: '2026-03-29T20:10:01+00:00' },
            ],
            run_id: 'run_1',
            latest_event_id: 'evt-2',
            after_event_found: true,
            include_all_runs: false,
            order: 'desc',
            returned_count: 2,
            message: 'room runtime events loaded',
            loaded_at: '2026-03-29T20:10:03+00:00',
          },
        },
      ],
    }

    const bundle = extract_room_runtime_bundle(raw)
    const normalized = normalize_room_runtime_bundle_payload(bundle)

    expect(bundle.type).toBe('room_runtime_events')
    expect(bundle.run_id).toBe('run_1')
    expect(bundle.latest_event_id).toBe('evt-2')
    expect(bundle.after_event_found).toBe(true)
    expect(bundle.items.map((x) => x.id)).toEqual(['evt-1', 'evt-2'])

    expect(normalized.type).toBe('room_runtime_events')
    expect(normalized.order).toBe('desc')
    expect(normalized.returned_count).toBe(2)
  })

  it('extracts and normalizes replay bundle including result payload, result text and audit', () => {
    const raw = {
      tool_results: [
        {
          type: 'room_run_replay',
          payload: {
            run_id: 'run_9',
            events: [
              { id: 'evt-plan', type: 'room.plan', ts: '2026-03-29T20:10:00+00:00' },
              {
                id: 'evt-final',
                type: 'room.final',
                ts: '2026-03-29T20:10:10+00:00',
                payload: { response: '最终结论' },
              },
            ],
            phases: [{ event_id: 'evt-final', phase: 'final' }],
            final_event: {
              id: 'evt-final',
              type: 'room.final',
              payload: { response: '最终结论', citations: [{ id: 'web:1' }] },
            },
            final_payload: { response: '最终结论', citations: [{ id: 'web:1' }] },
            latest_event_id: 'evt-final',
            tail_event_id: 'evt-final',
            summary: '摘要',
            audit: { type: 'room_supervisor_audit_relation' },
          },
        },
      ],
    }

    const replay = extract_room_runtime_replay_bundle(raw)
    const normalized = normalize_room_runtime_replay_bundle_payload(replay)

    expect(replay.type).toBe('room_runtime_replay')
    expect(replay.run_id).toBe('run_9')
    expect(replay.result_event.id).toBe('evt-final')
    expect(replay.result_payload.response).toBe('最终结论')
    expect(replay.result_text).toBe('最终结论')
    expect(replay.citations).toEqual([{ id: 'web:1' }])
    expect(replay.audit.type).toBe('room_supervisor_audit_relation')

    expect(normalized.tail_event_id).toBe('evt-final')
    expect(normalized.latest_event_id).toBe('evt-final')
  })

  it('extracts whoami payload through nested tool_results', () => {
    const whoami = extract_whoami({
      tool_results: [
        {
          type: 'whoami',
          payload: {
            uid: 'user_123',
            basepath: '/tmp/workspace',
          },
        },
      ],
    })

    expect(whoami).toEqual({
      uid: 'user_123',
      basepath: '/tmp/workspace',
    })
  })
})

