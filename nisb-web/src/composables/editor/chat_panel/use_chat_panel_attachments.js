import { ref, computed } from 'vue'
import { get_file_icon, is_text_file_by_name } from './chat_panel_utils'

const CHAT_ATTACHMENT_ROOT = 'agent_files/attachments'

function format_message(template, params = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
    if (params?.[key] === undefined || params?.[key] === null) return ''
    return String(params[key])
  })
}

function create_chat_translator(t) {
  return function tr(key, params = {}, fallback = '') {
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
}

function normalize_chat_attachment_name(value) {
  const raw = String(value || '').split('/').pop().split('\\').pop().trim()
  const safe = raw
    .replace(/[\u0000-\u001f]/g, '')
    .replace(/[<>:"|?*]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()

  return safe || `attachment-${Date.now()}`
}

function join_agent_file_path(dir, name) {
  const base = String(dir || CHAT_ATTACHMENT_ROOT).replace(/\/+$/g, '')
  const leaf = normalize_chat_attachment_name(name)
  return `${base}/${leaf}`
}

function dirname_for_capability(path) {
  const normalized = String(path || '').replace(/\\/g, '/').replace(/\/+$/g, '')
  const index = normalized.lastIndexOf('/')
  if (index <= 0) return CHAT_ATTACHMENT_ROOT
  return normalized.slice(0, index) || CHAT_ATTACHMENT_ROOT
}

function normalize_attachment_item(item = {}) {
  return {
    path: String(item?.path || item?.relative_path || item?.relativePath || '').trim(),
    name: String(item?.name || '').trim(),
    type: String(item?.type || '').trim(),
    size: Number(item?.size || 0) || 0,
  }
}

function has_same_attachment(selected_attachments, next_item) {
  if (!selected_attachments || !Array.isArray(selected_attachments.value)) return false
  const next_path = String(next_item?.path || '').trim()
  if (!next_path) return false

  return selected_attachments.value.some(
    (item) => String(item?.path || '').trim() === next_path
  )
}

function push_unique_attachment(selected_attachments, item) {
  if (!selected_attachments || !Array.isArray(selected_attachments.value)) return

  const normalized = normalize_attachment_item(item)
  if (!normalized.path) return

  if (has_same_attachment(selected_attachments, normalized)) {
    return
  }

  selected_attachments.value.push(normalized)
}

function is_file_exists_message(message) {
  const text = String(message || '').trim()
  if (!text) return false
  return text.includes('\u6587\u4ef6\u5df2\u5b58\u5728') || /already exists/i.test(text)
}

function is_success_result(result) {
  if (!result || typeof result !== 'object') return false
  if (result.success === true) return true
  if (String(result.status || '').trim().toLowerCase() === 'success') return true
  return false
}

function read_entries(result) {
  if (Array.isArray(result?.entries)) return result.entries
  if (Array.isArray(result?.items)) return result.items
  return []
}

function emit_toast(message, type = 'info') {
  try {
    window.dispatchEvent(
      new CustomEvent('nisb-toast', {
        detail: { message: String(message || ''), type },
      })
    )
  } catch {}
}

function join_error_lines(errors) {
  return Array.isArray(errors) ? errors.join('\n') : ''
}

export function use_chat_panel_attachments({ call_tool, selected_attachments, t }) {
  const tr = create_chat_translator(t)

  const fileInput = ref(null)
  const isUploading = ref(false)
  const showAttachMenu = ref(false)

  const showFileSystemModal = ref(false)
  const isLoadingFiles = ref(false)
  const currentDir = ref(CHAT_ATTACHMENT_ROOT)
  const dirEntries = ref([])
  const fileSearchQuery = ref('')

  const filteredEntries = computed(() => {
    const query = String(fileSearchQuery.value || '').trim().toLowerCase()
    const entries = Array.isArray(dirEntries.value) ? dirEntries.value : []

    if (!query) return entries

    return entries.filter((entry) =>
      String(entry?.name || '').toLowerCase().includes(query)
    )
  })

  function getFileIcon(entry) {
    return get_file_icon(entry)
  }

  function toggleAttachMenu() {
    showAttachMenu.value = !showAttachMenu.value
  }

  function closeAttachMenu() {
    showAttachMenu.value = false
  }

  function handleGlobalClick(e) {
    if (!e?.target?.closest?.('.attach-btn-wrapper')) closeAttachMenu()
  }

  function triggerFileUpload() {
    closeAttachMenu()
    fileInput.value?.click()
  }

  async function handleFileUpload(e) {
    const files = e?.target?.files
    if (!files || files.length === 0) return

    isUploading.value = true
    let successCount = 0
    let failCount = 0
    let reusedCount = 0
    let createdCount = 0
    const errors = []

    for (const file of files) {
      try {
        if (file.size > 5 * 1024 * 1024) {
          errors.push(
            tr(
              'chat.attachments.upload.fileTooLarge',
              { name: file.name },
              '{name}: File is too large (limit 5 MB)'
            )
          )
          failCount++
          continue
        }

        let content
        const isTextFile = is_text_file_by_name(file.name)

        if (isTextFile) {
          content = await file.text()
        } else {
          content = await new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              const base64 = String(reader.result || '').split(',')[1]
              resolve(base64)
            }
            reader.onerror = reject
            reader.readAsDataURL(file)
          })
        }

        const filename = join_agent_file_path(CHAT_ATTACHMENT_ROOT, file.name)
        const attachmentFocusRoot = dirname_for_capability(filename)

        const result = await call_tool('nisb_file_create', {
          _capability_focus_root: attachmentFocusRoot,
          capability_gate: {
            focus_root: attachmentFocusRoot,
            fs_read_scope: 'agent_files',
            fs_write_scope: 'agent_files',
            fs_dangerous_enabled: false,
          },
          filename,
          content,
          description: tr(
            'chat.attachments.upload.description',
            { time: new Date().toLocaleString() },
            'Chat attachment uploaded at {time}'
          ),
          auto_categorize: false,
        })

        if (is_success_result(result)) {
          successCount++
          createdCount++
          push_unique_attachment(selected_attachments, {
            path: filename,
            name: normalize_chat_attachment_name(file.name),
            type: file.type || '',
            size: file.size,
          })
          continue
        }

        if (is_file_exists_message(result?.message)) {
          successCount++
          reusedCount++
          push_unique_attachment(selected_attachments, {
            path: filename,
            name: normalize_chat_attachment_name(file.name),
            type: file.type || '',
            size: file.size,
          })
          continue
        }

        errors.push(
          tr(
            'chat.attachments.upload.itemFailed',
            {
              name: file.name,
              error: result?.message || tr('chat.attachments.common.unknownError', {}, 'Unknown error')
            },
            '{name}: {error}'
          )
        )
        failCount++
      } catch (err) {
        errors.push(
          tr(
            'chat.attachments.upload.itemFailed',
            { name: file.name, error: err?.message || String(err) },
            '{name}: {error}'
          )
        )
        failCount++
      }
    }

    if (e?.target) e.target.value = ''
    isUploading.value = false

    if (successCount > 0 && failCount > 0) {
      alert(
        tr(
          'chat.attachments.upload.mixedAlert',
          { successCount, failCount, errors: join_error_lines(errors) },
          '✅ Succeeded: {successCount}\n❌ Failed: {failCount}\n{errors}'
        )
      )
    } else if (failCount > 0) {
      alert(
        tr(
          'chat.attachments.upload.failedAlert',
          { errors: join_error_lines(errors) },
          '❌ Upload failed:\n{errors}'
        )
      )
    } else if (reusedCount > 0 && createdCount === 0) {
      emit_toast(
        tr(
          'chat.attachments.upload.reused',
          { count: reusedCount },
          'Reused {count} existing attachments'
        ),
        'success'
      )
    } else if (successCount > 0) {
      emit_toast(
        tr(
          'chat.attachments.upload.added',
          { count: successCount },
          'Added {count} attachments'
        ),
        'success'
      )
    }

    if (createdCount > 0) {
      try {
        window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
      } catch {}
    }
  }

  async function loadDirectory(path) {
    isLoadingFiles.value = true
    try {
      const res = await call_tool('nisb_dir_list', { path })
      if (is_success_result(res)) {
        dirEntries.value = read_entries(res)
          .filter((entry) => !String(entry?.name || '').startsWith('.'))
          .map((entry) => ({
            name: entry.name,
            type: entry.type,
            path: path ? `${path}/${entry.name}` : entry.name,
            size: entry.size || 0,
          }))
        currentDir.value = path
      } else {
        dirEntries.value = []
        currentDir.value = path
      }
    } catch (error) {
      console.error('Failed to load directory:', path, error)
      dirEntries.value = []
    } finally {
      isLoadingFiles.value = false
    }
  }

  async function openFileSystemPicker() {
    closeAttachMenu()
    showFileSystemModal.value = true
    fileSearchQuery.value = ''
    await loadDirectory(currentDir.value || '')
  }

  function closeFileSystemModal() {
    showFileSystemModal.value = false
    fileSearchQuery.value = ''
  }

  async function goParentDir() {
    if (!currentDir.value) return
    const idx = currentDir.value.lastIndexOf('/')
    const parent = idx === -1 ? '' : currentDir.value.slice(0, idx)
    await loadDirectory(parent)
  }

  async function enterDirectory(entry) {
    await loadDirectory(entry.path)
  }

  function selectExistingFile(entry) {
    if (!entry || entry.type === 'directory') return

    push_unique_attachment(selected_attachments, {
      path: entry.path,
      name: entry.name,
      type: entry.type || '',
      size: entry.size || 0,
    })

    emit_toast(
      tr(
        'chat.attachments.picker.selected',
        { name: entry.name },
        'Selected attachment: {name}'
      ),
      'success'
    )
    closeFileSystemModal()
  }

  function removeAttachment(index) {
    if (!selected_attachments || !Array.isArray(selected_attachments.value)) return
    if (index < 0 || index >= selected_attachments.value.length) return
    selected_attachments.value.splice(index, 1)
  }

  return {
    fileInput,
    isUploading,
    showAttachMenu,
    showFileSystemModal,
    isLoadingFiles,
    currentDir,
    dirEntries,
    fileSearchQuery,
    filteredEntries,
    getFileIcon,
    toggleAttachMenu,
    triggerFileUpload,
    openFileSystemPicker,
    closeFileSystemModal,
    goParentDir,
    enterDirectory,
    selectExistingFile,
    handleFileUpload,
    removeAttachment,
    handleGlobalClick,
  }
}

export default use_chat_panel_attachments

