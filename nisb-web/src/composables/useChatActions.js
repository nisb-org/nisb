import { ref, provide, inject } from 'vue'

const REGISTRY_KEY = Symbol('nisb.chat.actions')

export function createChatActionsRegistry() {
  const actions = ref([]) // { id, side:'left'|'right', order, component }

  function register(action) {
    if (!action?.id) return
    const exists = actions.value.find(a => a.id === action.id)
    if (!exists) actions.value.push(action)
    actions.value.sort((a, b) => (a.side === b.side) ? a.order - b.order : (a.side === 'left' ? -1 : 1))
  }

  function unregister(id) {
    actions.value = actions.value.filter(a => a.id !== id)
  }

  provide(REGISTRY_KEY, { actions, register, unregister })
  return { actions, register, unregister }
}

export function useChatActionsRegistry() {
  const reg = inject(REGISTRY_KEY, null)
  return reg
}

