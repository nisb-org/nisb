import { createApp, h } from 'vue'
import { useMCP } from '../../../composables/useMCP'
import BatchMoveModal from '../../../components/LeftSidebar/file_browser/BatchMoveModal.vue'

let active = null

function cleanup_active() {
  if (!active) return
  try {
    active.app?.unmount?.()
  } catch {}
  try {
    active.el?.remove?.()
  } catch {}
  try {
    active.resolve?.(null)
  } catch {}
  active = null
}

export function open_batch_move_modal({ count = 0, focus_dir = '', default_dest_dir = '' }) {
  cleanup_active()

  // 从 useMCP 拿到 callTool
  const { callTool } = useMCP()

  return new Promise((resolve) => {
    const host = document.createElement('div')
    host.setAttribute('data-nisb-modal', 'batch-move')
    document.body.appendChild(host)

    const app = createApp({
      render() {
        return h(BatchMoveModal, {
          count,
          focus_dir,
          default_dest_dir,
          call_tool: callTool,   // ✅ 传给 Modal，注意和 Modal 里 props 一致
          onConfirm: (dest_dir) => {
            try {
              resolve(String(dest_dir || '').trim() || null)
            } finally {
              cleanup_active()
            }
          },
          onCancel: () => {
            try {
              resolve(null)
            } finally {
              cleanup_active()
            }
          }
        })
      }
    })

    active = { app, el: host, resolve }
    app.mount(host)
  })
}

