// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/actions/left_sidebar_actions_binary.js
import { useI18n } from 'vue-i18n'

export function create_left_sidebar_binary_actions({
  call_tool,
  toast,
  get_uid,
  normalize_rel_path
}) {
  const { t } = useI18n()

  function format_message(template, params = {}) {
    return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
      if (params?.[key] === undefined || params?.[key] === null) return ''
      return String(params[key])
    })
  }

  function tr(key, params = {}, fallback = '') {
    let text = ''
    if (typeof t === 'function') {
      try {
        text = t(key, params)
      } catch {
        text = ''
      }
    }
    if (!text || text === key) text = fallback || key
    return format_message(text, params)
  }

  function escape_html(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
  }

  const FILE_READ_BASE64_TOOL = 'nisb_file_read_base64'
  const BINARY_PREVIEW_MAX_BYTES = 25 * 1024 * 1024
  const EPUB_PREVIEW_MAX_BYTES = 200 * 1024 * 1024

  let binary_blob_urls = []

  function b64_to_blob_url(b64, mime) {
    const bin = atob(String(b64 || ''))
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    const blob = new Blob([bytes], { type: mime || 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    binary_blob_urls.push(url)
    return url
  }

  function cleanup_binary_blob_urls() {
    try {
      for (const u of binary_blob_urls) URL.revokeObjectURL(u)
    } catch {}
    binary_blob_urls = []
  }

  async function preview_binary(rel_path) {
    const filename = normalize_rel_path(rel_path)
    if (!filename) throw new Error(tr('files.binary.filenameRequired', {}, 'filename is required'))

    const uid = get_uid()
    const resp = await call_tool('nisb_file_read_base64', {
      filename,
      uid,
      max_bytes: BINARY_PREVIEW_MAX_BYTES
    })

    if (!resp?.success) throw new Error(resp?.message || tr('files.binary.readFailed', {}, 'Read failed'))

    const url = b64_to_blob_url(resp.data_base64, resp.mime)
    const w = window.open(url, '_blank')
    if (!w) {
      throw new Error(
        tr(
          'files.binary.popupBlocked',
          {},
          'The browser blocked the new window. Please allow pop-ups or use the context menu.'
        )
      )
    }

    setTimeout(() => {
      try {
        URL.revokeObjectURL(url)
        binary_blob_urls = binary_blob_urls.filter((u) => u !== url)
      } catch {}
    }, 5 * 60 * 1000)
  }

  function open_epub_window_html({ blob_url, title }) {
    const safe_title = escape_html(title || tr('files.binary.epub.readerTitle', {}, 'EPUB Reader'))

    const labels = {
      prevPage: tr('files.binary.epub.prevPage', {}, 'Previous page'),
      nextPage: tr('files.binary.epub.nextPage', {}, 'Next page'),
      close: tr('files.binary.epub.close', {}, 'Close'),
      loading: tr(
        'files.binary.epub.readerLoading',
        {},
        'Loading EPUB reader… If it fails, the epub.js CDN may be blocked by the network policy.'
      ),
      cdnFailed: tr(
        'files.binary.epub.cdnFailed',
        {},
        'epub.js failed to load.\n\nSuggestion: make sure https://unpkg.com/epubjs/dist/epub.min.js is reachable.'
      ),
      readFailedPrefix: tr('files.binary.epub.readFailedPrefix', {}, 'Failed to read EPUB: ')
    }

    const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>${safe_title}</title>
  <style>
    html, body { height: 100%; margin: 0; background: #0b0f14; color: #d7dde6; font-family: ui-sans-serif, system-ui; }
    .topbar { height: 46px; display: flex; align-items: center; gap: 8px; padding: 0 10px; border-bottom: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03); }
    .btn { width: 34px; height: 34px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.03); color: #d7dde6; cursor: pointer; }
    .btn:hover { background: rgba(255,255,255,0.06); }
    .title { flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 13px; opacity: .9; }
    #viewer { height: calc(100% - 46px); }
    .hint { padding: 10px; font-size: 12px; opacity: .8; }
    .err { padding: 10px; color: #ffb4b4; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="topbar">
    <button class="btn" id="prev" title="${escape_html(labels.prevPage)}">◀</button>
    <button class="btn" id="next" title="${escape_html(labels.nextPage)}">▶</button>
    <div class="title">${safe_title}</div>
    <button class="btn" id="close" title="${escape_html(labels.close)}">✕</button>
  </div>
  <div id="viewer"></div>
  <div class="hint" id="hint">${escape_html(labels.loading)}</div>

  <script src="https://unpkg.com/epubjs/dist/epub.min.js"></script>
  <script>
    (function () {
      const blobUrl = ${JSON.stringify(blob_url)};
      const cdnFailed = ${JSON.stringify(labels.cdnFailed)};
      const readFailedPrefix = ${JSON.stringify(labels.readFailedPrefix)};
      const hintEl = document.getElementById('hint');
      const viewerEl = document.getElementById('viewer');

      function showErr(msg) {
        try { hintEl.remove(); } catch {}
        const el = document.createElement('div');
        el.className = 'err';
        el.textContent = msg;
        document.body.appendChild(el);
      }

      if (!window.ePub) {
        showErr(cdnFailed);
        return;
      }

      fetch(blobUrl).then(r => r.arrayBuffer()).then((ab) => {
        try { hintEl.remove(); } catch {}
        const book = window.ePub(ab);
        const rendition = book.renderTo(viewerEl, { width: '100%', height: '100%' });
        rendition.display();

        document.getElementById('prev').onclick = () => rendition.prev();
        document.getElementById('next').onclick = () => rendition.next();
        document.getElementById('close').onclick = () => window.close();

        window.addEventListener('keydown', (e) => {
          if (e.key === 'ArrowLeft') rendition.prev();
          if (e.key === 'ArrowRight') rendition.next();
          if (e.key === 'Escape') window.close();
        });
      }).catch((e) => {
        showErr(readFailedPrefix + (e && e.message ? e.message : String(e)));
      });
    })();
  </script>
</body>
</html>`
    return html
  }

  async function open_epub_read_new_tab({ epub_path_raw, title }) {
    toast(tr('files.binary.epub.loading', {}, '⏳ Loading EPUB…'), 'info', 1500)

    const uid = get_uid()
    const filename = normalize_rel_path(epub_path_raw)

    const resp = await call_tool(FILE_READ_BASE64_TOOL, {
      filename,
      uid,
      max_bytes: EPUB_PREVIEW_MAX_BYTES
    })

    if (!resp?.success) throw new Error(resp?.message || tr('files.binary.readFailed', {}, 'Read failed'))

    const epub_blob_url = b64_to_blob_url(resp.data_base64, resp.mime || 'application/epub+zip')
    const html = open_epub_window_html({ blob_url: epub_blob_url, title })
    const html_blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const html_url = URL.createObjectURL(html_blob)
    binary_blob_urls.push(html_url)

    const w = window.open(html_url, '_blank')
    if (!w) throw new Error(tr('files.binary.popupBlockedShort', {}, 'The browser blocked the new window. Please allow pop-ups.'))

    setTimeout(() => {
      try {
        URL.revokeObjectURL(html_url)
        binary_blob_urls = binary_blob_urls.filter((u) => u !== html_url)
      } catch {}
    }, 2 * 60 * 1000)

    setTimeout(() => {
      try {
        URL.revokeObjectURL(epub_blob_url)
        binary_blob_urls = binary_blob_urls.filter((u) => u !== epub_blob_url)
      } catch {}
    }, 10 * 60 * 1000)
  }

  return {
    preview_binary,
    open_epub_read_new_tab,
    cleanup_binary_blob_urls
  }
}
