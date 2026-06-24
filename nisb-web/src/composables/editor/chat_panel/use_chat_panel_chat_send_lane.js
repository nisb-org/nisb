import {
  create_assistant_message,
  create_empty_stream_state,
  create_user_message,
  normalize_display_text,
  normalize_tool_call,
  normalize_tool_result,
  patch_message_by_id,
  push_message,
  read_array,
  read_message_by_id,
  read_object,
  read_string,
} from './use_chat_panel_message_writer'
import {
  append_stream_markdown,
  create_empty_stream_markdown_state,
  finalize_stream_markdown,
  mark_stream_markdown_done,
  mark_stream_markdown_error,
} from '../../chat/use_stream_markdown'
import {
  apply_common_meta,
  apply_final_meta,
  build_final_payload,
  build_message_patch,
  build_state_patch,
  dispatch_conversations_refresh,
  ensure_message_stream_state,
  read_response_text,
} from './use_chat_panel_send_runtime_shared'

export function create_chat_send_lane({
  messages,
  input_text,
  is_thinking,
  is_uploading,
  call_tool,
  call_tool_stream,
  cancel_by_dedupe_key,
  current_conv_id,
  stream_runtime,
  stop_local_stream,
  emit_stream_state,
  emit_stream_final,
  update_conv_id,
  clear_selected_attachments,
  hard_scroll_to_bottom,
  activate_follow_bottom,
  extend_follow_bottom,
  clear_active_stream_handles,
}) {
  async function send_chat_message_non_stream(raw, tool_name, payload, request_id) {
    const normalized_raw = String(raw || '').trim()
    if (!normalized_raw || is_uploading.value) return

    const user_message = create_user_message({
      content: normalized_raw,
      response: normalized_raw,
    })

    const assistant_message = create_assistant_message({
      content: '',
      response: '',
      pending: true,
      request_id,
      stream_markdown: create_empty_stream_markdown_state(),
    })

    activate_follow_bottom(request_id, {
      idle_ms: 12000,
      max_ms: 90000,
    })

    push_message(messages, user_message)
    push_message(messages, assistant_message)
    hard_scroll_to_bottom()

    const ctx = {
      ...create_empty_stream_state(),
      request_id,
      conv_id: String(payload?.conv_id || current_conv_id.value || '').trim(),
      rag_mode: String(payload?.rag_mode || '').trim(),
      mcp_overrides: read_object(payload, 'mcp_overrides'),
    }

    input_text.value = ''
    is_thinking.value = true

    emit_stream_state(
      build_state_patch(ctx, {
        streaming: true,
        stage: 'meta',
      })
    )

    try {
      const result = await call_tool(tool_name, payload, { normalize_chat_payload: true })
      const result_status = read_string(result, 'status')
      const result_message = read_string(result, 'message')

      if (result_status && result_status !== 'success') {
        throw new Error(result_message || '请求失败')
      }

      apply_common_meta(ctx, result)
      apply_final_meta(ctx, result)

      const raw_tool_calls = read_array(result, 'tool_calls')
      const raw_tool_results = read_array(result, 'tool_results')

      ctx.tool_calls = raw_tool_calls.map((item) => normalize_tool_call(item))
      ctx.tool_results = raw_tool_results.map((item) => normalize_tool_result(item))
      ctx.status = result_status || 'success'
      ctx.message = result_message || ''

      const final_text = normalize_display_text(read_response_text(result))
      const current_message = read_message_by_id(messages, assistant_message.id)
      const current_stream = ensure_message_stream_state(current_message, final_text || '')

      patch_message_by_id(
        messages,
        assistant_message.id,
        build_message_patch(ctx, final_text || '', {
          stream_markdown: mark_stream_markdown_done(
            finalize_stream_markdown(current_stream, final_text || '')
          ),
        })
      )

      extend_follow_bottom(10000)
      hard_scroll_to_bottom()

      emit_stream_state(
        build_state_patch(ctx, {
          streaming: false,
          stage: 'final',
        })
      )

      emit_stream_final(build_final_payload(ctx, final_text || ''))
      update_conv_id(ctx.conv_id)
      dispatch_conversations_refresh()
      clear_selected_attachments()
    } catch (error) {
      const error_text = normalize_display_text(error?.message || String(error || '发送失败'))
      ctx.status = 'error'
      ctx.message = error_text

      const current_message = read_message_by_id(messages, assistant_message.id)
      const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
      const fallback_text = current_text || error_text
      const current_stream = ensure_message_stream_state(current_message, fallback_text)

      patch_message_by_id(
        messages,
        assistant_message.id,
        build_message_patch(ctx, fallback_text, {
          status: 'error',
          message: error_text,
          stream_markdown: mark_stream_markdown_error(
            finalize_stream_markdown(current_stream, fallback_text)
          ),
        })
      )

      extend_follow_bottom(6000)
      hard_scroll_to_bottom()

      emit_stream_state(
        build_state_patch(ctx, {
          streaming: false,
          stage: 'error',
          status: 'error',
          message: error_text,
        })
      )
    } finally {
      is_thinking.value = false
      clear_active_stream_handles()
    }
  }

  async function send_chat_message_stream(raw, tool_name, payload, request_id) {
    const normalized_raw = String(raw || '').trim()
    if (!normalized_raw || is_uploading.value) return

    stop_local_stream()

    const my_seq = ++stream_runtime.seq

    const user_message = create_user_message({
      content: normalized_raw,
      response: normalized_raw,
    })

    const assistant_message = create_assistant_message({
      content: '',
      response: '',
      pending: true,
      request_id,
      stream_markdown: create_empty_stream_markdown_state(),
    })

    stream_runtime.dedupe_key = `chat_panel_stream_${request_id}`
    stream_runtime.assistant_message_id = assistant_message.id

    activate_follow_bottom(request_id, {
      idle_ms: 12000,
      max_ms: 90000,
    })

    push_message(messages, user_message)
    push_message(messages, assistant_message)
    hard_scroll_to_bottom()

    const ctx = {
      ...create_empty_stream_state(),
      request_id,
      conv_id: String(payload?.conv_id || current_conv_id.value || '').trim(),
      rag_mode: String(payload?.rag_mode || '').trim(),
      mcp_overrides: read_object(payload, 'mcp_overrides'),
    }

    let final_received = false

    input_text.value = ''
    is_thinking.value = true

    emit_stream_state(
      build_state_patch(ctx, {
        streaming: true,
        stage: 'meta',
      })
    )

    stream_runtime.abort = {
      abort() {
        try {
          if (stream_runtime.dedupe_key) {
            cancel_by_dedupe_key(stream_runtime.dedupe_key)
          }
        } catch {}
      },
    }

    try {
      const result = await call_tool_stream(tool_name, payload, {
        dedupe_key: stream_runtime.dedupe_key,
        onEvent: (event_name, data) => {
          if (my_seq !== stream_runtime.seq) return

          const ev = String(event_name || '').trim()

          apply_common_meta(ctx, data)
          update_conv_id(ctx.conv_id, { emit_upstream: false })

          if (ev === 'meta') {
            const current_message = read_message_by_id(messages, assistant_message.id)
            if (current_message && !current_message.stream_markdown) {
              patch_message_by_id(messages, assistant_message.id, {
                request_id: ctx.request_id,
                conv_id: ctx.conv_id,
                rag_mode: ctx.rag_mode,
                mode_used: ctx.mode_used,
                mcp_overrides: ctx.mcp_overrides,
                stream_markdown: create_empty_stream_markdown_state(),
              })
            }

            extend_follow_bottom(8000)

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: true,
                stage: 'meta',
              })
            )
            return
          }

          if (ev === 'delta') {
            const chunk = normalize_display_text(
              read_string(
                data,
                'response',
                'content',
                'text',
                'answer',
                'final_text',
                'assistant_response'
              )
            )

            if (chunk) {
              const current_message = read_message_by_id(messages, assistant_message.id)
              const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
              const current_stream = ensure_message_stream_state(current_message, current_text)
              const next_text = `${current_text}${chunk}`

              patch_message_by_id(messages, assistant_message.id, {
                content: next_text,
                response: next_text,
                pending: true,
                request_id: ctx.request_id,
                conv_id: ctx.conv_id,
                rag_mode: ctx.rag_mode,
                mode_used: ctx.mode_used,
                mcp_overrides: ctx.mcp_overrides,
                status: ctx.status,
                message: ctx.message,
                tool_calls: [...ctx.tool_calls],
                tool_results: [...ctx.tool_results],
                stream_markdown: append_stream_markdown(current_stream, chunk),
              })

              extend_follow_bottom(8000)
              hard_scroll_to_bottom()
            }

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: true,
                stage: 'delta',
              })
            )
            return
          }

          if (ev === 'tool_call') {
            ctx.tool_calls = [...ctx.tool_calls, normalize_tool_call(data)]

            patch_message_by_id(messages, assistant_message.id, {
              pending: true,
              tool_calls: [...ctx.tool_calls],
              tool_results: [...ctx.tool_results],
              request_id: ctx.request_id,
              conv_id: ctx.conv_id,
              rag_mode: ctx.rag_mode,
              mode_used: ctx.mode_used,
              mcp_overrides: ctx.mcp_overrides,
              status: ctx.status,
              message: ctx.message,
            })

            extend_follow_bottom(8000)
            hard_scroll_to_bottom()

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: true,
                stage: 'tool_call',
              })
            )
            return
          }

          if (ev === 'tool_result') {
            ctx.tool_results = [...ctx.tool_results, normalize_tool_result(data)]

            patch_message_by_id(messages, assistant_message.id, {
              pending: true,
              tool_calls: [...ctx.tool_calls],
              tool_results: [...ctx.tool_results],
              request_id: ctx.request_id,
              conv_id: ctx.conv_id,
              rag_mode: ctx.rag_mode,
              mode_used: ctx.mode_used,
              mcp_overrides: ctx.mcp_overrides,
              status: ctx.status,
              message: ctx.message,
            })

            extend_follow_bottom(8000)
            hard_scroll_to_bottom()

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: true,
                stage: 'tool_result',
              })
            )
            return
          }

          if (ev === 'final') {
            final_received = true
            apply_final_meta(ctx, data)

            const final_tool_calls = read_array(data, 'tool_calls')
            const final_tool_results = read_array(data, 'tool_results')

            if (final_tool_calls.length > 0) {
              ctx.tool_calls = final_tool_calls.map((item) => normalize_tool_call(item))
            }

            if (final_tool_results.length > 0) {
              ctx.tool_results = final_tool_results.map((item) => normalize_tool_result(item))
            }

            ctx.status = read_string(data, 'status') || ctx.status || 'success'
            ctx.message = read_string(data, 'message') || ctx.message

            const current_message = read_message_by_id(messages, assistant_message.id)
            const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
            const final_text = normalize_display_text(read_response_text(data) || current_text || '')
            const current_stream = ensure_message_stream_state(current_message, final_text)

            patch_message_by_id(
              messages,
              assistant_message.id,
              build_message_patch(ctx, final_text, {
                stream_markdown: mark_stream_markdown_done(
                  finalize_stream_markdown(current_stream, final_text)
                ),
              })
            )

            extend_follow_bottom(8000)
            hard_scroll_to_bottom()

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: false,
                stage: 'final',
              })
            )

            emit_stream_final(build_final_payload(ctx, final_text))
            update_conv_id(ctx.conv_id)
            dispatch_conversations_refresh()
            clear_selected_attachments()
            is_thinking.value = false
            return
          }

          if (ev === 'done') {
            const current_message = read_message_by_id(messages, assistant_message.id)
            const current_stream = ensure_message_stream_state(
              current_message,
              normalize_display_text(current_message?.response || current_message?.content || '')
            )

            patch_message_by_id(messages, assistant_message.id, {
              stream_markdown: mark_stream_markdown_done(current_stream),
            })

            extend_follow_bottom(5000)
            hard_scroll_to_bottom()

            if (!final_received) {
              emit_stream_state(
                build_state_patch(ctx, {
                  streaming: false,
                  stage: 'done',
                })
              )
            }

            is_thinking.value = false
            return
          }

          if (ev === 'error') {
            const error_text = normalize_display_text(read_string(data, 'message') || '流式调用失败')
            ctx.status = 'error'
            ctx.message = error_text

            const current_message = read_message_by_id(messages, assistant_message.id)
            const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
            const fallback_text = current_text || error_text
            const current_stream = ensure_message_stream_state(current_message, fallback_text)

            patch_message_by_id(
              messages,
              assistant_message.id,
              build_message_patch(ctx, fallback_text, {
                status: 'error',
                message: error_text,
                stream_markdown: mark_stream_markdown_error(
                  finalize_stream_markdown(current_stream, fallback_text)
                ),
              })
            )

            extend_follow_bottom(5000)
            hard_scroll_to_bottom()

            emit_stream_state(
              build_state_patch(ctx, {
                streaming: false,
                stage: 'error',
                status: 'error',
                message: error_text,
              })
            )

            is_thinking.value = false
          }
        },
      })

      if (my_seq !== stream_runtime.seq) return

      if (!final_received) {
        apply_common_meta(ctx, result)
        apply_final_meta(ctx, result)
        update_conv_id(ctx.conv_id, { emit_upstream: false })

        const result_tool_calls = read_array(result, 'tool_calls')
        const result_tool_results = read_array(result, 'tool_results')

        if (result_tool_calls.length > 0) {
          ctx.tool_calls = result_tool_calls.map((item) => normalize_tool_call(item))
        }

        if (result_tool_results.length > 0) {
          ctx.tool_results = result_tool_results.map((item) => normalize_tool_result(item))
        }

        if (!ctx.status) {
          ctx.status = read_string(result, 'status') || 'success'
        }
        if (!ctx.message) {
          ctx.message = read_string(result, 'message')
        }

        const current_message = read_message_by_id(messages, assistant_message.id)
        const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
        const final_text = normalize_display_text(read_response_text(result) || current_text || '')
        const current_stream = ensure_message_stream_state(current_message, final_text)

        patch_message_by_id(
          messages,
          assistant_message.id,
          build_message_patch(ctx, final_text, {
            stream_markdown: mark_stream_markdown_done(
              finalize_stream_markdown(current_stream, final_text)
            ),
          })
        )

        extend_follow_bottom(8000)
        hard_scroll_to_bottom()

        emit_stream_state(
          build_state_patch(ctx, {
            streaming: false,
            stage: 'done',
          })
        )

        emit_stream_final(build_final_payload(ctx, final_text))
        update_conv_id(ctx.conv_id)
        if ((ctx.status || 'success') === 'success') {
          dispatch_conversations_refresh()
          clear_selected_attachments()
        }
      }
    } catch (error) {
      if (my_seq !== stream_runtime.seq) return

      const error_text = normalize_display_text(error?.message || String(error || '发送失败'))
      ctx.status = 'error'
      ctx.message = error_text

      const current_message = read_message_by_id(messages, assistant_message.id)
      const current_text = normalize_display_text(current_message?.response || current_message?.content || '')
      const fallback_text = current_text || error_text
      const current_stream = ensure_message_stream_state(current_message, fallback_text)

      patch_message_by_id(
        messages,
        assistant_message.id,
        build_message_patch(ctx, fallback_text, {
          status: 'error',
          message: error_text,
          stream_markdown: mark_stream_markdown_error(
            finalize_stream_markdown(current_stream, fallback_text)
          ),
        })
      )

      extend_follow_bottom(5000)
      hard_scroll_to_bottom()

      emit_stream_state(
        build_state_patch(ctx, {
          streaming: false,
          stage: 'error',
          status: 'error',
          message: error_text,
        })
      )
    } finally {
      if (my_seq === stream_runtime.seq) {
        is_thinking.value = false
        clear_active_stream_handles()
      }
    }
  }

  return {
    send_chat_message_non_stream,
    send_chat_message_stream,
  }
}

export default create_chat_send_lane
