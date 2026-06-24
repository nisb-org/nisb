import { nextTick } from 'vue'
import { useImageLoader } from '../../useImageLoader'

export function use_chat_panel_dom({ chat_root, emit_open_lightbox }) {
  const { enhanceMarkdownDom } = useImageLoader()

  async function enhance_chat_dom() {
    await nextTick()
    if (!chat_root.value) return
    await enhanceMarkdownDom({
      rootEl: chat_root.value,
      onOpenLightbox: ({ src, alt }) => emit_open_lightbox({ src, alt }),
    })
  }

  return { enhance_chat_dom }
}

