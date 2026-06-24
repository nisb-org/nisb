// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/use_left_sidebar_uploads.js
import { useI18n } from 'vue-i18n'

export function use_left_sidebar_uploads({ call_tool, current_dir, file_input, dir_input }) {
  const { t } = useI18n()

  const MAX_UPLOAD_SIZE_MB = 200
  const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

  const FILE_WRITE_BASE64_TOOL = 'nisb_file_write_base64'
  const FILE_WRITE_BASE64_CHUNK_TOOL = 'nisb_file_write_base64_chunk'
  const CHUNK_BYTES = 2 * 1024 * 1024
  const SINGLE_UPLOAD_LIMIT_BYTES = 8 * 1024 * 1024

  function clean_path_part(value) {
    return String(value || '')
      .trim()
      .replace(/\\/g, '/')
      .replace(/\/+/g, '/')
      .replace(/^\/+/, '')
      .replace(/\/+$/, '')
  }

  function join_upload_path(base, name) {
    const b = clean_path_part(base)
    const n = clean_path_part(name)
    if (!b) return n
    if (!n) return b
    return `${b}/${n}`
  }

  function dirname(path) {
    const p = clean_path_part(path)
    if (!p) return ''
    const idx = p.lastIndexOf('/')
    if (idx <= 0) return ''
    return p.slice(0, idx)
  }

  function as_agent_files_focus_root(path) {
    const p = clean_path_part(path)
    if (!p) return 'agent_files'
    if (p === 'agent_files' || p.startsWith('agent_files/')) return p
    if (p === 'storage' || p.startsWith('storage/')) return p
    return `agent_files/${p}`
  }

  function capability_focus_root_for_file(filename) {
    return as_agent_files_focus_root(dirname(filename))
  }

  function capability_focus_root_for_dir(path) {
    return as_agent_files_focus_root(dirname(path))
  }

  function uint8_to_base64(u8) {
    const chunk = 0x8000
    let binary = ''

    for (let i = 0; i < u8.length; i += chunk) {
      const sub = u8.subarray(i, i + chunk)
      binary += String.fromCharCode(...sub)
    }

    return btoa(binary)
  }

  function unwrap_tool_result(result) {
    if (result?.tool_results && typeof result.tool_results === 'object') return result.tool_results
    if (result?.result && typeof result.result === 'object') return result.result
    return result
  }

  function result_success(result) {
    const r = unwrap_tool_result(result)
    if (!r) return false
    if (r.success === false) return false
    if (r.error) return false
    return true
  }

  function result_message(result) {
    const r = unwrap_tool_result(result)
    return r?.message || r?.error || result?.message || result?.error || t('files.upload.unknownError')
  }

  function upload_common_args(filename, description) {
    return {
      filename,
      overwrite: false,
      description,
      auto_categorize: false,
      _capability_focus_root: capability_focus_root_for_file(filename)
    }
  }

  async function upload_binary_single({ filename, file, description }) {
    const ab = await file.arrayBuffer()
    const b64 = uint8_to_base64(new Uint8Array(ab))

    return await call_tool(FILE_WRITE_BASE64_TOOL, {
      ...upload_common_args(filename, description),
      data_base64: b64
    })
  }

  async function upload_binary_chunked({ filename, file, description }) {
    const total_chunks = Math.ceil(file.size / CHUNK_BYTES)
    const upload_id = `up_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
    const common = upload_common_args(filename, description)

    for (let chunk_index = 0; chunk_index < total_chunks; chunk_index++) {
      const start = chunk_index * CHUNK_BYTES
      const end = Math.min(file.size, start + CHUNK_BYTES)
      const blob = file.slice(start, end)
      const ab = await blob.arrayBuffer()
      const b64 = uint8_to_base64(new Uint8Array(ab))

      const result = await call_tool(FILE_WRITE_BASE64_CHUNK_TOOL, {
        ...common,
        upload_id,
        chunk_index,
        total_chunks,
        data_base64: b64
      })

      if (!result_success(result)) return result
    }

    return {
      success: true,
      message: t('files.upload.chunkedDone')
    }
  }

  async function upload_file_entry({ file, filename, description }) {
    if (file.size <= SINGLE_UPLOAD_LIMIT_BYTES) {
      return await upload_binary_single({ filename, file, description })
    }

    return await upload_binary_chunked({ filename, file, description })
  }

  function notify_refresh_after_upload() {
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
  }

  function size_limit_message(name) {
    return t('files.upload.fileTooLarge', {
      name,
      limit: MAX_UPLOAD_SIZE_MB
    })
  }

  function file_description() {
    return t('files.upload.uploadedAt', {
      time: new Date().toLocaleString()
    })
  }

  function dir_file_description() {
    return t('files.upload.directoryUploadedAt', {
      time: new Date().toLocaleString()
    })
  }

  async function handle_file_upload(e) {
    const files = e?.target?.files
    if (!files || files.length === 0) return

    const base_dir = clean_path_part(current_dir.value)

    let success_count = 0
    let fail_count = 0
    const errors = []

    for (const file of files) {
      try {
        if (file.size > MAX_UPLOAD_SIZE_BYTES) {
          errors.push(size_limit_message(file.name))
          fail_count++
          continue
        }

        const filename = join_upload_path(base_dir, file.name)
        const result = await upload_file_entry({
          file,
          filename,
          description: file_description()
        })

        if (result_success(result)) {
          success_count++
        } else {
          errors.push(`${file.name}: ${result_message(result)}`)
          fail_count++
        }
      } catch (err) {
        errors.push(`${file.name}: ${err?.message || String(err)}`)
        fail_count++
      }
    }

    e.target.value = ''

    if (success_count > 0) {
      notify_refresh_after_upload()
    }

    let msg = ''
    if (success_count > 0) {
      msg += t('files.upload.fileSuccessLine', { count: success_count })
    }
    if (fail_count > 0) {
      if (msg) msg += '\n'
      msg += t('files.upload.fileFailureBlock', {
        count: fail_count,
        errors: errors.join('\n')
      })
    }

    alert(msg || t('files.upload.fileDone'))
  }

  async function handle_dir_upload(e) {
    const files = e?.target?.files
    if (!files || files.length === 0) return

    const base_dir = clean_path_part(current_dir.value)

    const dir_set = new Set()
    const file_entries = []

    for (const file of files) {
      const rel_path = clean_path_part(file.webkitRelativePath || file.name)
      if (!rel_path) continue

      const last_slash = rel_path.lastIndexOf('/')
      const dir_part = last_slash > -1 ? rel_path.slice(0, last_slash) : ''
      if (dir_part) dir_set.add(dir_part)

      file_entries.push({ file, rel_path })
    }

    const dirs = Array.from(dir_set).sort((a, b) => {
      return a.split('/').length - b.split('/').length
    })

    for (const dir of dirs) {
      try {
        const dir_path = join_upload_path(base_dir, dir)
        await call_tool('nisb_dir_create', {
          path: dir_path,
          _capability_focus_root: capability_focus_root_for_dir(dir_path)
        })
      } catch {}
    }

    let success_count = 0
    let fail_count = 0
    const errors = []

    for (const entry of file_entries) {
      const { file, rel_path } = entry

      try {
        if (file.size > MAX_UPLOAD_SIZE_BYTES) {
          errors.push(size_limit_message(rel_path))
          fail_count++
          continue
        }

        const filename = join_upload_path(base_dir, rel_path)
        const result = await upload_file_entry({
          file,
          filename,
          description: dir_file_description()
        })

        if (result_success(result)) {
          success_count++
        } else {
          errors.push(`${rel_path}: ${result_message(result)}`)
          fail_count++
        }
      } catch (err) {
        errors.push(`${rel_path}: ${err?.message || String(err)}`)
        fail_count++
      }
    }

    e.target.value = ''

    if (success_count > 0) {
      notify_refresh_after_upload()
    }

    let msg = t('files.upload.directorySummary', { count: success_count })
    if (fail_count > 0) {
      msg += `\n${t('files.upload.directoryFailureBlock', {
        count: fail_count,
        errors: errors.join('\n')
      })}`
    }

    alert(msg)
  }

  function trigger_upload() {
    file_input.value?.click()
  }

  function trigger_dir_upload() {
    dir_input.value?.click()
  }

  return {
    trigger_upload,
    trigger_dir_upload,
    handle_file_upload,
    handle_dir_upload
  }
}
