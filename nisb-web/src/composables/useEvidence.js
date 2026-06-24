// /opt/mcp-gateway/nisb-web/src/composables/useEvidence.js
import { computed } from 'vue'
import { useLibrarySearchStore } from '../stores/librarySearch'

export function useEvidence() {
  const store = useLibrarySearchStore()

  // 兼容旧 API：暴露同名字段
  const loading = computed(() => store.loading)
  const error = computed(() => store.error)
  const items = computed(() => store.items)
  const selected = computed(() => store.selected)

  async function searchEvidence({
    query,
    libraryId,
    docId,
    topK = 8,
    maxChars = 8000,
    docTitle = ''
  } = {}) {
    // 统一走 store（避免重复实现）
    store.setContext({
      libraryId,
      docId,
      preserveResults: false
    })

    store.setScope('doc')
    store.setMode('evidence')
    store.query = String(query ?? '')
    // docTitle 目前后端只是回显/记录，不影响 evidence 主流程；这里先不强塞入 store
    // （需要的话，下轮我们给 store.search 增加 extraArgs 扩展口）
    await store.search({ topK, maxChars })
  }

  function selectEvidence(it) {
    store.selectItem(it)
  }

  function jumpToReader(it) {
    if (it) store.selectItem(it)
    store.jumpSelected()
  }

  return {
    loading,
    error,
    items,
    selected,

    searchEvidence,
    selectEvidence,
    jumpToReader
  }
}

