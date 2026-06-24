import { createApp, h } from 'vue'
import * as i18n_module from '../../../i18n'
import CreateEntryModal from '../../../components/LeftSidebar/file_browser/CreateEntryModal.vue'

let active = null

function _resolve_i18n_plugin() {
  const candidates = [
    i18n_module?.default,
    i18n_module?.i18n,
    i18n_module?.app_i18n
  ]

  for (const item of candidates) {
    if (item && typeof item === 'object' && typeof item.install === 'function') {
      return item
    }
  }

  return null
}

function cleanup_active(result = null, { settle = true } = {}) {
  const current = active
  if (!current) return

  active = null

  try {
    current.app?.unmount?.()
  } catch {}

  try {
    current.el?.remove?.()
  } catch {}

  if (settle) {
    try {
      current.resolve?.(result)
    } catch {}
  }
}

// 返回：null | { name, base_dir }
export function open_create_entry_modal({
  kind = 'file',
  base_dir = '',
  default_name = '',
  default_ext = 'md',
  call_tool = null
}) {
  cleanup_active(null)

  return new Promise((resolve) => {
    if (typeof document === 'undefined' || !document.body) {
      resolve(null)
      return
    }

    const host = document.createElement('div')
    host.setAttribute('data-nisb-modal-host', 'create-entry')
    document.body.appendChild(host)

    const app = createApp({
      render() {
        return h(CreateEntryModal, {
          kind,
          base_dir,
          default_name,
          default_ext,
          call_tool,
          onConfirm: (payload) => {
            const name = String(payload?.name || '').trim()
            const base_dir_out = String(payload?.base_dir || '').trim()

            if (!name) {
              cleanup_active(null)
              return
            }

            cleanup_active({
              name,
              base_dir: base_dir_out
            })
          },
          onCancel: () => {
            cleanup_active(null)
          }
        })
      }
    })

    const i18n = _resolve_i18n_plugin()
    if (i18n) {
      try {
        app.use(i18n)
      } catch {}
    }

    active = { app, el: host, resolve }

    try {
      app.mount(host)
    } catch (_e) {
      cleanup_active(null)
    }
  })
}
