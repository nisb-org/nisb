import { createApp, h } from 'vue'
import BatchRenameModal from '../../../components/LeftSidebar/file_browser/BatchRenameModal.vue'

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

export function open_batch_rename_modal({ count = 0, focus_dir = '', items = [] }) {
  cleanup_active()

  return new Promise((resolve) => {
    const host = document.createElement('div')
    host.setAttribute('data-nisb-modal', 'batch-rename')
    document.body.appendChild(host)

    const app = createApp({
      render() {
        return h(BatchRenameModal, {
          count,
          focus_dir,
          items,
          onConfirm: (rules) => {
            try {
              resolve(rules || null)
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

