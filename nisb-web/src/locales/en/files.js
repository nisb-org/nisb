export default {
  favorites: {
    title: '★ Favorites',
    emptyHint: '(No favorites yet; right-click a file/directory → Set as favorite)',
    directories: 'Directories',
    files: 'Files',
    focus: '◉ Focus',
    unfocus: '○ Clear focus',
    remove: 'Remove favorite'
  },
  highlight: {
    title: 'Pinned highlight',
    clear: 'Clear highlight',
    highlightedAs: 'Highlighted as {color}',
    colors: {
      amber: 'Amber',
      blue: 'Blue',
      emerald: 'Emerald',
      violet: 'Violet',
      rose: 'Rose',
      cyan: 'Cyan',
      slate: 'Slate'
    }
  },
  root: {
    userLabel: 'user',
    userTitle: 'user',
    userTitleWithSlash: 'user/'
  },
  loading: '(Loading…)',
  empty: '(Directory is empty)',
  actions: {
    collapseAllDirs: 'Collapse all directories',
    createInCurrentDir: 'Create in current directory'
  },
  upload: {
    unknownError: 'Unknown error',
    chunkedDone: 'Chunked upload completed',
    fileTooLarge: '{name}: file is too large (limit {limit}MB)',
    uploadedAt: 'Uploaded at {time}',
    directoryUploadedAt: 'Directory uploaded at {time}',
    fileSuccessLine: 'Uploaded {count} file(s) successfully',
    fileFailureBlock: 'Failed {count} file(s):\n{errors}',
    fileDone: 'Upload completed',
    directorySummary: 'Directory upload completed\nSuccessful files: {count}',
    directoryFailureBlock: 'Failed files: {count}\n{errors}'
  },
  settings: {
    title: 'File space settings',
    hoverExpand: 'Auto-expand directories on hover',
    hoverExpandHint: 'Recommended off by default to avoid accidental frequent expand / collapse.'
  },
  contextMenu: {
    createFile: '📄 Create file',
    createFolder: '📁 Create folder',
    createFileHere: '📄 Create file here',
    createFolderHere: '📁 Create folder here',
    sendDirectoryToLibrary: '📚 Send directory to library...',
    directoryToBrain: '🧠 Send directory to brain',
    deleteDirectoryRecursive: '🧨 Recursively delete directory',
    toggleFavorite: '⭐ Add to / remove from favorites',
    copyInternalLink: '🔗 Copy internal link',
    openBinaryNewTab: '↗ Preview in new tab (PDF/image)',
    sendFileToLibrary: '📚 Send to library...',
    txtToStructuredMd: '📝 Convert to note (TXT → structured MD)',
    epubReadNewTab: '📖 Read in new tab (EPUB)',
    pdfToNote: '📝 Convert to note (MD + images)',
    epubToNote: '📝 Convert to note (MD + images)',
    docToNote: '📝 Convert to note (DOC → MD + images)',
    docxToNote: '📝 Convert to note (DOCX → MD + images)',
    pptToNote: '📝 Convert to note (PPT → MD + images)',
    pptxToNote: '📝 Convert to note (PPTX → MD + images)',
    noteToBrain: '🧠 Send to brain',
    copyImageReference: '📋 Copy image reference',
    focusThisDirectory: '◉ Focus this directory',
    clearFocus: '○ Clear focus',
    rename: '✏️ Rename',
    moveTo: '📦 Move to...',
    delete: '🗑️ Delete',
    unimplementedAction: 'Menu action is not implemented: {action}'
  },
  convert: {
    common: {
      unknownError: 'Unknown error',
      unknownErrorLower: 'unknown error',
      targetPathMissing: 'Target path was not found.',
      alreadyExistsOpen: '✅ Already exists: {name} (opened)',
      overwriteConfirm: 'Target already exists. Overwrite it?\n\n{message}',
      overwriteCancelled: 'Overwrite cancelled.',
      convertFailed: '❌ Conversion failed: {error}',
      exception: '❌ Conversion exception: {error}',
      generated: '✅ Generated: {name}',
      generatedSplit: '✅ Generated: {name} (split)',
      generatedImages: '✅ Generated: {name} (images: {count})'
    },

    pdf: {
      pathMissing: 'PDF path was not found.',
      progress: '⏳ Converting PDF to Markdown. This may take a while...',
      completed: 'PDF conversion completed',
      overwriteCompleted: 'PDF overwrite conversion completed',
      resumeCompleted: 'PDF resume conversion completed',
      busy: '⏳ Another PDF is being converted. Please wait until the current task finishes.',
      timeoutResumeConfirm: 'Conversion timed out ({done}/{total} pages). Continue from page {next}?',
      resumeCancelled: 'Resume cancelled. Generated partial files were kept.',
      resumeProgress: '⏳ Resuming conversion...',
      resumeFailed: '❌ Resume conversion failed: {error}',
      resumeGenerated: '✅ Generated: {name} (resume)'
    },

    office: {
      notExpectedFile: 'Current file is not {ext}.',
      progress: '⏳ Converting {kind} to Markdown...',
      busy: '⏳ Another document is being converted. Please wait until the current task finishes.'
    },

    epub: {
      pathMissing: 'EPUB path was not found.',
      progress: '⏳ Converting EPUB to Markdown (md_part_max_lines=2000, auto/split)...'
    },

    txt: {
      pathMissing: 'TXT path was not found.',
      notExpectedFile: 'Current file is not .txt.',
      start: 'Start converting: {name}',
      failed: 'Conversion failed: {error}',
      successNoPath: 'Conversion succeeded, but md_path was not returned.',
      alreadyExists: 'Already exists: {name}',
      completed: 'Conversion completed: {name}'
    }
  },

  open: {
    epub: {
      pathMissing: 'EPUB path was not found.',
      notExpectedFile: 'Current file is not .epub.',
      openFailed: 'Failed to open EPUB: {error}'
    },

    binary: {
      pathMissing: 'File path was not found.',
      unsupported: 'This file does not support binary preview.',
      previewFailed: 'Preview failed: {error}'
    }
  },

  binary: {
    filenameRequired: 'filename is required',
    readFailed: 'Read failed',
    popupBlocked: 'The browser blocked the new window. Please allow pop-ups or use the context menu.',
    popupBlockedShort: 'The browser blocked the new window. Please allow pop-ups.',
    epub: {
      readerTitle: 'EPUB Reader',
      loading: '⏳ Loading EPUB…',
      prevPage: 'Previous page',
      nextPage: 'Next page',
      close: 'Close',
      readerLoading: 'Loading EPUB reader… If it fails, the epub.js CDN may be blocked by the network policy.',
      cdnFailed: 'epub.js failed to load.\n\nSuggestion: make sure https://unpkg.com/epubjs/dist/epub.min.js is reachable.',
      readFailedPrefix: 'Failed to read EPUB: '
    }
  },

  controller: {
    messages: {
      actionCompleted: 'Action completed',
      libraryStatusRefreshed: 'Library status refreshed',
      directoryLoaded: 'Directory loaded',
      favoritesLoaded: 'Favorites loaded',
      favoritesUpdated: 'Favorites updated',
      favoritesUpdateFailed: 'Failed to update favorites',
      highlightUpdated: 'Highlight updated',
      highlightCleared: 'Highlight cleared',
      highlightUpdateFailed: 'Failed to update highlight',
      actionFailed: 'Action failed',
      focusBeforeBatchAction: 'Please focus a directory before using batch actions',
      focusBeforeBatchMove: 'Please focus a directory before using batch move',
      focusBeforeBatchRename: 'Please focus a directory before using batch rename',
      noSelection: 'No files or directories selected',
      batchDeleteConfirmAgain: '🗑 {count} item(s) selected: click delete again to confirm (within 5 seconds)',
      batchDeleteStarted: '🧨 Batch recursive delete in progress: {count} item(s)...',
      movedToTrash: '✅ Moved to trash',
      batchDeleteFailed: '❌ Batch delete failed: {error}',
      batchDeleteException: '❌ Batch delete error: {error}',
      unknownError: 'Unknown error',
      selectionNotInFocusedDir: 'The selected items are not inside the current focused directory; canceled',
      destinationRequired: 'Target directory cannot be empty',
      ignoredDescendants: '{count} descendant item(s) were automatically ignored because their parent directory was selected',
      batchMoveStarted: '🚚 Starting move: {count} item(s) → user/{dest}/',
      moveProgress: '🚚 Moving {index}/{total}: {name}',
      moveCompleted: 'Move completed',
      defaultMoveFailed: 'Move failed',
      cannotMoveIntoSelf: '{name}: the target directory cannot be inside itself',
      moveFailed: '{name}: {error}',
      batchMoveSummaryWarning: '⚠️ Move completed: {success} succeeded, {failed} failed',
      batchMoveSummarySuccess: '✅ Move completed: {count} item(s)',
      batchRenameStarted: '✎ Starting rename: {count} item(s)',
      renameProgress: '✎ Renaming {index}/{total}: {name}',
      renameCompleted: 'Rename completed',
      defaultRenameFailed: 'Rename failed',
      renameFailed: '{name}: {error}',
      batchRenameSummaryWarning: '⚠️ Rename completed: {success} succeeded, {failed} failed',
      batchRenameSummarySuccess: '✅ Rename completed: {count} item(s)',
      addedToFavorites: 'Added to favorites: {name}',
      removedFromFavorites: 'Removed from favorites: {name}',
      failJoiner: '; '
    }
  },
  batch: {
    selectedTitle: '{count} selected',
    selectedLabel: '{count} selected',
    selectAllCurrentLevel: 'Select all at current level',
    moveSelected: 'Batch move (controlled concurrency + progress toast)',
    renameSelected: 'Rule-based batch rename (with preview + progress toast)',
    deleteSelected: 'Batch recursive delete (double-click to confirm, toast only)',
    exit: 'Exit batch mode',
    enter: 'Batch mode (focused directory only: delete / move / rename)'
  },
  createEntry: {
    title: 'New',
    file: 'File',
    folder: 'Folder',
    fileTitle: 'New file',
    folderTitle: 'New folder',
    location: 'Create location',
    chooseChildDir: 'Choose child directory',
    childDirs: 'Child directories',
    collapse: 'Collapse',
    childLoading: '(Loading…)',
    childEmpty: '(No child directories under the current directory)',
    fileName: 'Filename',
    folderName: 'Folder name',
    filePlaceholder: 'note',
    folderPlaceholder: 'notes',
    extTitle: 'Extension (editable, can be empty)',
    previewPrefix: 'Will be created as:',
    enterFileName: 'Please enter a filename.',
    enterFolderName: 'Please enter a folder name.',
    confirm: 'Create'
  },
  batchMove: {
    title: 'Batch move',
    currentFocus: 'Current focus',
    selectedCount: 'Selected items',
    selectedCountValue: '{count} selected',
    currentDirectory: 'Current directory',
    targetDirectory: 'Target directory',
    chooseChildDir: 'Choose child directory',
    childDirs: 'Child directories',
    collapse: 'Collapse',
    childLoading: 'Loading child directories...',
    childEmpty: 'No selectable child directories under the current directory',
    directoryPath: 'Directory path',
    inputPlaceholder: 'Example: agent_files/docs',
    hint: 'Note: selected files and directories will be moved into the target directory while keeping their original names. If a directory is selected, all of its contents will be moved recursively.',
    confirm: 'Move here'
  },
  batchRename: {
    title: 'Rule-based batch rename',
    selectedCountValue: '{count} selected',
    applyTo: 'Apply to',
    applyToAll: 'Files + folders',
    applyToFiles: 'Files only',
    applyToDirs: 'Folders only',
    prefix: 'Prefix',
    prefixPlaceholder: 'For example: 2026_',
    suffix: 'Suffix',
    suffixPlaceholder: 'For example: _done',
    find: 'Find',
    findPlaceholder: 'For example: draft',
    replace: 'Replace',
    replacePlaceholder: 'For example: final',
    numbering: 'Numbering',
    enable: 'Enable',
    numberingStart: 'Start',
    numberingWidth: 'Width',
    numberingDelimiter: 'Delimiter',
    numberingDelimiterPlaceholder: '_',
    previewTitle: 'Preview (up to 30 items)',
    conflictWarning: 'Name conflicts exist, cannot apply',
    hint: 'Note: renaming changes only the name itself (the parent directory stays the same). Files keep their extensions, and numbering is applied before the extension.',
    confirm: 'Apply rules'
  },
  bulk: {
    undoSuccess: 'This recursive delete has been undone',
    undoFailed: 'Undo failed: {error}'
  },
  treeNode: {
    batchSelect: 'Batch select',
    hebbianMarked: 'Sent to brain',
    inLibrary: 'Sent to library',
    inLibraries: 'Sent to: {names}',
    inLibrariesMore: 'Sent to: {names} and {extraCount} more libraries',
    libraryCoverage: 'Library coverage: {percent}%',
    focusHere: '◉ Focus',
    clearFocus: '○ Clear focus',
    setFavorite: 'Set as favorite',
    unsetFavorite: 'Unset favorite',
    loadingChildren: '(Loading…)',
    contextMenuFocusHere: '◉ Focus this directory',
    contextMenuClearFocus: '○ Clear focus',
    messages: {
      actionCompleted: 'Action completed',
      directoryLoaded: 'Directory loaded',
      favoritesUpdated: 'Favorites updated',
      favoritesUpdateFailed: 'Failed to update favorites',
      conversionCompleted: 'Conversion completed',
      convertingToMarkdown: '⏳ Converting {kind} → Markdown…',
      busy: 'Busy, please try again later',
      missingMdPath: 'md_path was not returned',
      alreadyExistsOpened: '✅ Already exists, opened',
      overwriteCanceled: 'Overwrite canceled',
      generated: '✅ Generated',
      conversionFailed: 'Conversion failed'
    }
  },
  sendToLibrary: {
    title: 'Send to library',
    sourceDirectory: 'Source directory: ',
    sourceFile: 'Source file: ',
    targetLibrary: 'Target library',
    loadingLibraries: 'Loading library list...',
    noLibraries: 'No libraries available yet. Create one in the Library panel first',
    libraryIdMissing: '(Missing library ID)',
    mode: 'Send mode',
    copyDirectory: 'Copy (keep the source directory)',
    copyFile: 'Copy (keep the source file)',
    moveDirectory: 'Move (delete sent files from the source directory after sending)',
    moveFile: 'Move (delete the source file after sending)',
    confirm: 'Send to library',
    sending: 'Sending...',
    messages: {
      loadLibrariesCompleted: 'Library list loaded',
      loadLibrariesFailed: 'Failed to load library list: {error}',
      loadLibrariesException: 'Library list error: {error}',
      sendFailed: 'Failed to send to library: {error}',
      sendException: 'Send to library error: {error}',
      sendFailedGeneric: 'Send failed',
      unknownError: 'Unknown error',
      directorySentCopy: 'Directory sent to library (mode: copy)',
      directorySentMove: 'Directory sent to library (mode: move)',
      fileSentCopy: 'File sent to library (mode: copy)',
      fileSentMove: 'File sent to library (mode: move)'
    }
  },
  autoSave: {
    unknownError: 'Unknown error',
    fileSaved: '✅ File saved\n\n📁 {name}',
    saveFailed: '❌ Save failed: {error}',
    quickNoteSaved: '✅ Saved as a quick note'
  },
  noteOperations: {
    unknownError: 'Unknown error',
    fileSaved: '✅ File saved\n\n📁 {name}',
    saveFailed: '❌ Save failed: {error}',
    unsavedPrompt: 'The current content is not linked to a file yet. Enter a relative path to save it, such as notes/my_note.md:',
    createDescription: 'Created at {time}',
    createdAndSaved: '✅ Created and saved file\n\n📁 {filename}',
    noFileOpen: 'No file is open',
    processingNote: '🧠 Processing: {name}',
    justNow: 'Just now',
    noteSentToBrain: '✅ Note sent to brain\n📁 {name}\n💡 Use the graph tools to view the relationship network',
    noteToBrainFailed: '❌ Failed to send note to brain: {error}',
    noteToBrainException: '❌ Note-to-brain error: {error}'
  },
  revealSavedFileFailed: 'Failed to reveal saved file: {error}'
}

