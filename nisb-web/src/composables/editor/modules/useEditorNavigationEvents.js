import { nextTick } from 'vue'
import enRoot from '../../../locales/en.js'
import zhCNRoot from '../../../locales/zh-CN.js'

const NAV_LOCALES = {
  en: enRoot,
  'zh-CN': zhCNRoot
}

function _string_value(value) {
  return String(value ?? '').trim()
}

function _normalize_locale(value) {
  const raw = _string_value(value).replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function _local_storage_first(keys, fallback = '') {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key)
      if (value !== null && _string_value(value)) return String(value)
    } catch {}
  }
  return String(fallback || '')
}

function _current_locale() {
  const fromWindow = (() => {
    try {
      return (
        window?.__nisb_locale ||
        window?.__nisb_ui_locale ||
        window?.__NISB_LOCALE__ ||
        window?.__NISB_UI_LOCALE__ ||
        ''
      )
    } catch {
      return ''
    }
  })()

  const fromStorage = _local_storage_first(
    [
      'nisb_locale',
      'nisb_ui_locale',
      'nisb_language',
      'nisb_settings_locale',
      'locale',
      'ui_locale',
      'language'
    ],
    ''
  )

  const fromDocument = (() => {
    try {
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  return _normalize_locale(fromWindow || fromStorage || fromDocument || 'en')
}

function _deep_get(obj, path, fallback = '') {
  const keys = String(path || '').split('.').filter(Boolean)
  let cur = obj

  for (const key of keys) {
    if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback
    cur = cur[key]
  }

  return cur == null ? fallback : cur
}

function _format_text(template, params = {}) {
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ''))
}

function _t(path, params = {}, fallback = '') {
  const messages = NAV_LOCALES[_current_locale()] || NAV_LOCALES.en
  const value = _deep_get(messages, path, _deep_get(NAV_LOCALES.en, path, fallback))
  return _format_text(value || fallback || path, params)
}

export function useEditorNavigationEvents(ctx) {
  const {
    currentView,
    currentMode,
    editMode,
    currentFile,
    currentDir,
    saveStatus,
    saving,
    autoSaving,

    leftCollapsed,
    rightCollapsed,

    fileHistory,
    forwardHistory,

    lazyMdRef,
    useLazyMarkdown,

    canGoBack,
    canGoForward,

    currentConvId,
    currentLibraryId,
    currentLibraryDocId,
    currentRssFeedId,

    currentRssGateFeedId,
    currentRssGateQuery,

    startLoadFile,
    clearAutoSaveTimer,
    revokePdfUrlIfAny,
    abortFileLoading,
    switchMode,
    toggleEditMode,
    emitOutlineMode,
    beginDocOpen,
    normalizeLibraryReader,
    chatCfg,
    librarySearch,
    roomStore,
    callTool,

    saveCurrentNote,
    isCurrentNoteDirty
  } = ctx

  let __openDocTimer = null
  let __applyLibraryDocTimer = null
  let __historyNavInFlight = false

  async function _runExclusiveHistoryNav(task) {
    if (__historyNavInFlight) return false
    __historyNavInFlight = true
    try {
      await task()
      return true
    } finally {
      __historyNavInFlight = false
    }
  }

  const __pendingRssOpenKey = '__nisb_pending_rss_open_article'

  function __setPendingRssOpen(feed_id, article_id) {
    try {
      window[__pendingRssOpenKey] = {
        feed_id: String(feed_id || '').trim(),
        article_id: String(article_id || '').trim(),
        ts: Date.now()
      }
    } catch {}
  }

  function __dispatchRssOpen(feed_id, article_id) {
    window.dispatchEvent(
      new CustomEvent('nisb_rss_open_article', {
        detail: { feed_id: String(feed_id || '').trim(), article_id: String(article_id || '').trim() }
      })
    )
  }

  function _toast(message, type = 'info') {
    try {
      window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
    } catch {}
  }

  function _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  function _is_epub_path(path, name) {
    const p = String(path || '')
    const n = String(name || '')
    return /\.epub$/i.test(n) || /\.epub$/i.test(p)
  }

  async function _restoreCurrentRoomIfNeeded() {
    const mode = String(chatCfg?.chat?.mode || '').trim()
    const rid = String(chatCfg?.chat?.roomId || '').trim()

    if (mode !== 'room' || !rid) return false
    if (!roomStore || typeof roomStore.ensureFederationContextForRoomId !== 'function') return false
    if (typeof callTool !== 'function') return false

    const restored = await roomStore.ensureFederationContextForRoomId(callTool, rid, {
      clearLocal: false
    })

    if (restored?.ok === false) {
      _toast(
        restored.message ||
          _t(
            'note.navigation.restoreFederatedRoomFailed',
            {},
            'Failed to restore federated room context. Please re-enter from Recent.'
          ),
        'error'
      )
      try {
        chatCfg.exitRoomHard?.()
      } catch {}
      return true
    }

    try {
      currentView.value = 'main'
      currentMode.value = 'chat'
      emitOutlineMode('chat')

      chatCfg.enterRoom?.(rid)
      roomStore.setRoomId?.(rid)
      await roomStore.loadRoomBundle?.(callTool, rid)
      return true
    } catch (e) {
      _toast(e?.message || _t('note.navigation.restoreCurrentRoomFailed', {}, 'Failed to restore the current room.'), 'error')
      try {
        chatCfg.exitRoomHard?.()
      } catch {}
      return true
    }
  }

  function _push_current_to_history_if_needed() {
    if (!currentFile.value || !currentFile.value.path) return
    const top = fileHistory.value[fileHistory.value.length - 1]
    if (!top || top.path !== currentFile.value.path) {
      fileHistory.value.push({ path: currentFile.value.path, name: currentFile.value.name })
    }
  }

  function _push_current_to_forward_if_needed() {
    if (!currentFile.value || !currentFile.value.path) return
    const top = forwardHistory.value[forwardHistory.value.length - 1]
    if (!top || top.path !== currentFile.value.path) {
      forwardHistory.value.push({ path: currentFile.value.path, name: currentFile.value.name })
    }
  }

  function _open_entry_no_history(entry) {
    const path = entry?.path
    const name = entry?.name
    if (!path) return

    if (_is_epub_path(path, name)) {
      window.dispatchEvent(new CustomEvent('nisb-open-epub', { detail: { path, name, no_history: true } }))
      return
    }

    window.dispatchEvent(new CustomEvent('nisb-open-file', { detail: { path, name, no_history: true } }))
  }

  function _is_dirty_note_active() {
    if (currentView.value !== 'main') return false
    if (currentMode.value !== 'note') return false

    if (typeof isCurrentNoteDirty === 'function') {
      return !!isCurrentNoteDirty()
    }

    return saveStatus.value === 'unsaved'
  }

  async function _wait_for_save_idle(timeout_ms = 4000) {
    const deadline = Date.now() + Number(timeout_ms || 0)

    while (Date.now() < deadline) {
      if (!saving?.value && !autoSaving?.value) return true
      await _sleep(60)
    }

    return !saving?.value && !autoSaving?.value
  }

  async function _try_flush_current_note_before_leave(reason = 'leave_guard') {
    if (typeof saveCurrentNote !== 'function') return !_is_dirty_note_active()

    clearAutoSaveTimer()

    try {
      await _wait_for_save_idle(1200)
      const result = await saveCurrentNote({ reason })
      await _wait_for_save_idle(3000)

      if (result?.success) return !_is_dirty_note_active()
      return !_is_dirty_note_active()
    } catch {
      return false
    }
  }

  async function guardBeforeLeaveCurrentNote(opts = {}) {
    if (!_is_dirty_note_active()) return true

    const target_label =
      String(opts.targetLabel || _t('note.navigation.defaultTargetLabel', {}, 'Other content')).trim() ||
      _t('note.navigation.defaultTargetLabel', {}, 'Other content')
    const name =
      String(currentFile.value?.name || _t('note.navigation.currentNote', {}, 'Current note')).trim() ||
      _t('note.navigation.currentNote', {}, 'Current note')
    const has_file = !!String(currentFile.value?.path || '').trim()

    clearAutoSaveTimer()

    if (has_file) {
      const flushed = await _try_flush_current_note_before_leave('before_leave_flush')
      if (flushed) return true
    }

    if (!has_file) {
      const discard_new = window.confirm(
        _t(
          'note.navigation.unsavedNewNoteConfirm',
          { name, target: target_label },
          '{name} has not been saved as a file.\n\nContinuing to “{target}” will discard the current unsaved content.\n\nOK: discard and continue\nCancel: stay on the current note'
        )
      )
      return !!discard_new
    }

    const retry_save = window.confirm(
      _t(
        'note.navigation.unsavedRetrySaveConfirm',
        { name, target: target_label },
        '{name} has unsaved changes.\n\nOK: save now and continue to “{target}”\nCancel: go to discard confirmation'
      )
    )

    if (retry_save) {
      const saved = await _try_flush_current_note_before_leave('before_leave_confirm')
      if (saved) return true
      _toast(_t('note.navigation.saveFailedKeepUnsaved', {}, 'Save failed. Unsaved changes are still kept.'), 'error')
    }

    const discard = window.confirm(
      _t(
        'note.navigation.unsavedDiscardConfirm',
        { name, target: target_label },
        '{name} still has unsaved changes.\n\nOK: discard changes and continue to “{target}”\nCancel: stay on the current note'
      )
    )

    return !!discard
  }

  function isTypingTarget(el) {
    if (!el) return false
    const tag = String(el.tagName || '').toUpperCase()
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
    if (el.isContentEditable) return true
    return false
  }

  function handleKeydownEditMode(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
      e.preventDefault()
      if (currentMode.value === 'note') toggleEditMode()
    }
  }

  function handleKeydownGlobal(e) {
    if (isTypingTarget(e.target)) return
    if (currentView.value !== 'main') return
    if (currentMode.value !== 'note') return

    if (e.altKey && e.key === 'ArrowLeft') {
      if (!canGoBack.value) return
      e.preventDefault()
      handleGoBackFile()
    }
    if (e.altKey && e.key === 'ArrowRight') {
      if (!canGoForward.value) return
      e.preventDefault()
      handleGoForwardFile()
    }
  }

  async function handleFileOpen(evt) {
    const d = evt?.detail || {}
    const path = String(d.path || '').trim()
    const name = d.name
    const no_history = !!d.no_history
    if (!path) return

    if (_is_epub_path(path, name)) {
      window.dispatchEvent(new CustomEvent('nisb-open-epub', { detail: { path, name, no_history } }))
      return
    }

    const current_path = String(currentFile.value?.path || '').trim()
    if (currentView.value === 'main' && currentMode.value === 'note' && current_path === path) {
      return
    }

    const ok = await guardBeforeLeaveCurrentNote({ targetLabel: name || path })
    if (!ok) return

    clearAutoSaveTimer()

    if (!no_history) {
      if (currentFile.value && currentFile.value.path && currentFile.value.path !== path) {
        _push_current_to_history_if_needed()
        forwardHistory.value = []
      }
    }

    currentFile.value = { path, name }
    saveStatus.value = 'saved'
    currentView.value = 'main'

    startLoadFile(path)

    if (currentMode.value !== 'note') switchMode('note')
    emitOutlineMode('note')
  }

  async function handleEpubOpen(evt) {
    const d = evt?.detail || {}
    const path = String(d.path || '').trim()
    const name = d.name
    const no_history = !!d.no_history
    if (!path) return

    const current_path = String(currentFile.value?.path || '').trim()
    if (currentView.value === 'main' && currentMode.value === 'note' && current_path === path) {
      return
    }

    const ok = await guardBeforeLeaveCurrentNote({ targetLabel: name || path })
    if (!ok) return

    clearAutoSaveTimer()

    try {
      abortFileLoading()
    } catch {}
    try {
      revokePdfUrlIfAny()
    } catch {}

    if (!no_history) {
      if (currentFile.value && currentFile.value.path && currentFile.value.path !== path) {
        _push_current_to_history_if_needed()
        forwardHistory.value = []
      }
    }

    currentFile.value = { path, name }
    saveStatus.value = 'saved'
    currentView.value = 'main'

    if (currentMode.value !== 'note') switchMode('note')

    emitOutlineMode('epub')
  }

  function handleOpenDir(evt) {
    const { path } = evt.detail || {}
    const p = String(path || '').trim().replace(/^\/+/, '')
    if (!p) return

    currentDir.value = p

    window.dispatchEvent(new CustomEvent('nisb_file_focus_root', { detail: { path: p } }))
    _toast(_t('note.toolbar.focusedDirectoryToast', { path: p }, '◉ Focused directory: {path}'), 'info')
  }

  async function handleGoBackFile() {
    return await _runExclusiveHistoryNav(async () => {
      if (!fileHistory.value.length) return

      const preview = fileHistory.value[fileHistory.value.length - 1]
      const currentPathBefore = String(currentFile.value?.path || '').trim()

      const ok = await guardBeforeLeaveCurrentNote({
        targetLabel: preview?.name || preview?.path || _t('note.navigation.previousFile', {}, 'Previous file')
      })
      if (!ok) return

      if (currentPathBefore !== String(currentFile.value?.path || '').trim()) return
      if (!fileHistory.value.length) return

      _push_current_to_forward_if_needed()

      const prev = fileHistory.value.pop()
      if (!prev || !prev.path) return

      clearAutoSaveTimer()
      _open_entry_no_history(prev)
    })
  }

  async function handleGoForwardFile() {
    return await _runExclusiveHistoryNav(async () => {
      if (!forwardHistory.value.length) return

      const preview = forwardHistory.value[forwardHistory.value.length - 1]
      const currentPathBefore = String(currentFile.value?.path || '').trim()

      const ok = await guardBeforeLeaveCurrentNote({
        targetLabel: preview?.name || preview?.path || _t('note.navigation.nextFile', {}, 'Next file')
      })
      if (!ok) return

      if (currentPathBefore !== String(currentFile.value?.path || '').trim()) return
      if (!forwardHistory.value.length) return

      _push_current_to_history_if_needed()

      const next = forwardHistory.value.pop()
      if (!next || !next.path) return

      clearAutoSaveTimer()
      _open_entry_no_history(next)
    })
  }

  async function handleOutlineJump(evt) {
    const d = evt?.detail || {}
    const anchorRaw = String(d.anchor || '').trim()
    const textRaw = String(d.text || '').trim()
    const preview = !!d.preview

    if (!anchorRaw && !textRaw) return

    const isChatAnchor = anchorRaw.startsWith('chat-')
    if (isChatAnchor) {
      currentView.value = 'main'
      if (currentMode.value !== 'chat') currentMode.value = 'chat'
      await nextTick()

      const chatContainer =
        document.querySelector('.message-content.preview-content') ||
        document.querySelector('.message-content') ||
        document.querySelector('.preview-content')

      if (!chatContainer) return

      const el =
        (anchorRaw ? chatContainer.querySelector(`[data-chat-anchor="${anchorRaw}"]`) : null) ||
        (anchorRaw ? document.querySelector(`[data-chat-anchor="${anchorRaw}"]`) : null)

      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        if (!preview) {
          el.classList.add('highlight-flash')
          setTimeout(() => el.classList.remove('highlight-flash'), 1500)
        }
      }
      return
    }

    if (!currentFile.value) return

    currentView.value = 'main'
    if (currentMode.value !== 'note') currentMode.value = 'note'
    if (editMode.value) toggleEditMode()

    if (!editMode.value && useLazyMarkdown.value) {
      await nextTick()
      try {
        if (preview) {
          const container =
            document.querySelector('.display-mode-container .preview-content') ||
            document.querySelector('.preview-content')
          if (!container) return

          const el = anchorRaw
            ? container.querySelector(`#heading-${anchorRaw}`) ||
              container.querySelector(`[data-heading-anchor="${anchorRaw}"]`)
            : null

          if (el && typeof el.scrollIntoView === 'function') {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
          return
        }

        const doJump = async () => {
          await lazyMdRef.value.jumpTo({
            anchor: anchorRaw,
            text: textRaw,
            highlight: true
          })
        }

        if (lazyMdRef.value && typeof lazyMdRef.value.jumpTo === 'function') {
          await doJump()
        } else {
          for (let i = 0; i < 20; i++) {
            await new Promise((r) => setTimeout(r, 30))
            if (lazyMdRef.value && typeof lazyMdRef.value.jumpTo === 'function') {
              await doJump()
              break
            }
          }
        }
      } catch {}
      return
    }

    await nextTick()

    const container =
      document.querySelector('.display-mode-container .preview-content') ||
      document.querySelector('.preview-content')
    if (!container) return

    let target = null

    if (anchorRaw) {
      target =
        container.querySelector(`#heading-${anchorRaw}`) ||
        container.querySelector(`[data-heading-anchor="${anchorRaw}"]`)
    }

    if (!target && textRaw) {
      const all = container.querySelectorAll('h1, h2, h3, h4, h5, h6')
      all.forEach((el) => {
        const t = String(el.textContent || '').trim()
        if (!target && t === textRaw) target = el
      })
    }

    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      target.classList.add('highlight-flash')
      setTimeout(() => target.classList.remove('highlight-flash'), 1500)
    }
  }

  function handleOpenConversation(evt) {
    const { convId } = evt.detail || {}
    if (!convId) return

    abortFileLoading()
    revokePdfUrlIfAny()

    if (chatCfg.chat?.mode === 'room') chatCfg.exitRoomHard()

    currentView.value = 'main'
    currentMode.value = 'chat'
    currentConvId.value = String(convId)
    emitOutlineMode('chat')
  }

  function handleOpenLibrary(evt) {
    const { libraryId } = evt.detail || {}
    const id = libraryId
    if (!id) return

    abortFileLoading()
    revokePdfUrlIfAny()

    currentLibraryId.value = id
    currentLibraryDocId.value = null

    currentView.value = 'main'
    currentMode.value = 'library'
    librarySearch.setContext({ libraryId: id, docId: null })

    try {
      localStorage.setItem('nisb_last_library_id', String(id))
    } catch {}
  }

  function handleOpenLibraryDocImpl(evt) {
    const detail = evt?.detail || {}
    const libraryId = detail.libraryId
    const docId = detail.docId
    if (!libraryId || !docId) return

    abortFileLoading()
    revokePdfUrlIfAny()

    const spanIndexRaw = Number.isFinite(detail.spanIndex) ? detail.spanIndex : null

    const payload = {
      libraryId,
      docId,
      reader: normalizeLibraryReader(detail.reader || null),
      spanIndex: spanIndexRaw
    }

    try {
      window.__nisb_last_library_doc_open = payload
    } catch {}

    currentLibraryId.value = libraryId
    currentLibraryDocId.value = docId

    currentView.value = 'main'
    currentMode.value = 'library'
    librarySearch.setContext({ libraryId, docId })

    if (__applyLibraryDocTimer) clearTimeout(__applyLibraryDocTimer)
    __applyLibraryDocTimer = setTimeout(() => {
      window.dispatchEvent(new CustomEvent('nisb-apply-library-doc-state', { detail: payload }))
    }, 0)

    try {
      localStorage.setItem('nisb_last_library_id', String(libraryId))
    } catch {}
  }

  function handleOpenLibraryDoc(evt) {
    if (__openDocTimer) clearTimeout(__openDocTimer)

    __openDocTimer = setTimeout(async () => {
      const t = beginDocOpen()
      window.__nisbDocSwitchSeq = t.id

      await new Promise((r) => requestAnimationFrame(() => r()))
      if (t.isStale()) return

      try {
        handleOpenLibraryDocImpl(evt)
        if (t.isStale()) return
      } catch (e) {
        if (e && e.name === 'AbortError') return
        throw e
      }
    }, 120)
  }

  function handleBackFromLibrary() {
    currentView.value = 'main'
    currentMode.value = 'note'
    currentLibraryId.value = null
    currentLibraryDocId.value = null
    librarySearch.setContext({ libraryId: null, docId: null })
  }

  function handleCurrentDirChanged(evt) {
    currentDir.value = evt?.detail?.path || ''
  }

  function handleOpenRss(evt) {
    const { feedId } = evt.detail || {}
    if (!feedId) return
    currentRssFeedId.value = feedId
    currentView.value = 'rss'
  }

  function handleBackFromRss() {
    currentView.value = 'main'
    currentRssFeedId.value = ''
  }

  function handleOpenRssGate(evt) {
    const d = evt?.detail || {}
    const feedId = String(d.feedId || '').trim()
    const query = String(d.query || '').trim()
    currentRssGateFeedId.value = feedId
    currentRssGateQuery.value = query
    currentView.value = 'rss_gate'
  }

  function handleBackFromRssGate() {
    currentView.value = 'main'
    currentRssGateFeedId.value = ''
    currentRssGateQuery.value = ''
  }

  async function handleOpenRssArticle(evt) {
    const d = evt?.detail || {}
    const feedId = String(d.feed_id || '').trim()
    const articleId = String(d.article_id || '').trim()
    if (!feedId || !articleId) return

    __setPendingRssOpen(feedId, articleId)

    currentRssFeedId.value = feedId
    currentView.value = 'rss'

    await nextTick()
    __dispatchRssOpen(feedId, articleId)
    requestAnimationFrame(() => __dispatchRssOpen(feedId, articleId))
    setTimeout(() => __dispatchRssOpen(feedId, articleId), 80)
  }

  function handleSidebarStateChanged(e) {
    const d = e?.detail || {}
    const left = Number(d.left)
    const right = Number(d.right)
    if (Number.isFinite(left)) leftCollapsed.value = left <= 0
    if (Number.isFinite(right)) rightCollapsed.value = right <= 0
  }

  function mount() {
    try {
      chatCfg?.hydrate?.()
    } catch {}

    window.addEventListener('keydown', handleKeydownEditMode)
    window.addEventListener('keydown', handleKeydownGlobal)

    window.addEventListener('sidebar-state-changed', handleSidebarStateChanged)

    window.addEventListener('nisb-open-file', handleFileOpen)
    window.addEventListener('nisb-open-epub', handleEpubOpen)

    window.addEventListener('nisb-open-dir', handleOpenDir)
    window.addEventListener('nisb-open-conversation', handleOpenConversation)

    window.addEventListener('nisb-open-library', handleOpenLibrary)
    window.addEventListener('nisb-open-library-doc', handleOpenLibraryDoc)

    window.addEventListener('nisb-current-dir-changed', handleCurrentDirChanged)
    window.addEventListener('nisb-outline-jump', handleOutlineJump)

    window.addEventListener('nisb-open-rss', handleOpenRss)
    window.addEventListener('nisb-open-rss-gate', handleOpenRssGate)

    window.addEventListener('nisb_open_rss_article', handleOpenRssArticle)

    queueMicrotask(() => {
      void _restoreCurrentRoomIfNeeded()
    })
  }

  function unmount() {
    if (__openDocTimer) clearTimeout(__openDocTimer)
    if (__applyLibraryDocTimer) clearTimeout(__applyLibraryDocTimer)

    window.removeEventListener('sidebar-state-changed', handleSidebarStateChanged)

    window.removeEventListener('nisb-open-conversation', handleOpenConversation)

    window.removeEventListener('nisb-open-file', handleFileOpen)
    window.removeEventListener('nisb-open-epub', handleEpubOpen)

    window.removeEventListener('nisb-open-dir', handleOpenDir)

    window.removeEventListener('nisb-open-library', handleOpenLibrary)
    window.removeEventListener('nisb-open-library-doc', handleOpenLibraryDoc)

    window.removeEventListener('nisb-current-dir-changed', handleCurrentDirChanged)
    window.removeEventListener('nisb-outline-jump', handleOutlineJump)

    window.removeEventListener('nisb-open-rss', handleOpenRss)
    window.removeEventListener('nisb-open-rss-gate', handleOpenRssGate)

    window.removeEventListener('nisb_open_rss_article', handleOpenRssArticle)

    window.removeEventListener('keydown', handleKeydownEditMode)
    window.removeEventListener('keydown', handleKeydownGlobal)
  }

  return {
    mount,
    unmount,
    handleGoBackFile,
    handleGoForwardFile,
    handleBackFromLibrary,
    handleBackFromRss,
    handleBackFromRssGate,
    guardBeforeLeaveCurrentNote
  }
}
