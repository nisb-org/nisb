import {
  build_chat_arguments as build_chat_arguments_from_policy,
  resolve_chat_dispatch_policy,
} from './use_chat_panel_dispatch_policy'

export function build_chat_arguments(args) {
  return build_chat_arguments_from_policy(args)
}

export function resolve_chat_dispatch(args) {
  const resolved = resolve_chat_dispatch_policy(args)

  return {
    payload: resolved.payload,
    tool_name: resolved.tool_name,
    use_stream: resolved.use_stream,
  }
}

export default resolve_chat_dispatch
