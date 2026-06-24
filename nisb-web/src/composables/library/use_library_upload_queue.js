import { ref, unref } from 'vue'

export function use_library_upload_queue({ library_id_ref, call_tool, refresh_after_mutation }) {
  const file_input = ref(null)
  const upload_queue = ref([])
  const uploading = ref(false)
  const upload_cancel_requested = ref(false)

  function get_library_id() {
    return String(unref(library_id_ref) || '').trim()
  }

  function trigger_upload() {
    if (uploading.value) return
    file_input.value?.click()
  }

  function cancel_uploads() {
    upload_cancel_requested.value = true
  }

  function clear_queue() {
    if (uploading.value) return
    upload_queue.value = []
  }

  async function run_upload_queue() {
    if (uploading.value) return

    uploading.value = true
    upload_cancel_requested.value = false

    try {
      for (const item of upload_queue.value) {
        if (upload_cancel_requested.value) break
        if (item.status !== 'queued') continue

        const file = item.fileRef
        if (!file) {
          item.status = 'error'
          item.message = '未找到文件引用'
          continue
        }

        if (file.size > 50 * 1024 * 1024) {
          item.status = 'error'
          item.message = '文件过大（限制 50MB）'
          continue
        }

        item.status = 'uploading'
        item.message = ''

        try {
          const content = await file.text()
          const result = await call_tool('nisb_fs_send_to_library', {
            library_id: get_library_id(),
            filename: file.name,
            content,
            target_dir: 'uploads/web',
            mode: 'move'
          })

          if (result && (result.status === 'success' || result.status === 'warning')) {
            item.status = 'success'
            item.message = result.message || '✅ 上传完成'
          } else {
            item.status = 'error'
            item.message = '❌ 上传失败：' + (result?.message || '未知错误')
          }
        } catch (err) {
          console.error('[上传队列] 单文件失败:', err)
          item.status = 'error'
          item.message = '❌ 上传失败：' + (err?.message || String(err))
        }
      }
    } finally {
      uploading.value = false
      upload_cancel_requested.value = false
      await refresh_after_mutation({ retryDocs: 1, retryDelayMs: 250 })
    }
  }

  async function handle_file_upload(e) {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    if (!files.length) return

    const items = files.map((f, idx) => ({
      id: `${Date.now()}_${idx}`,
      name: f.name || `file_${idx}`,
      size: f.size || 0,
      fileRef: f,
      status: 'queued',
      message: ''
    }))

    upload_queue.value.push(...items)
    await run_upload_queue()
  }

  function reset_upload_state() {
    upload_queue.value = []
    uploading.value = false
    upload_cancel_requested.value = false
    if (file_input.value) file_input.value.value = ''
  }

  return {
    file_input,
    upload_queue,
    uploading,
    upload_cancel_requested,
    trigger_upload,
    cancel_uploads,
    clear_queue,
    handle_file_upload,
    run_upload_queue,
    reset_upload_state
  }
}

