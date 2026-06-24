<template>
  <div class="model-selector" ref="selectorRef">
    <button
      class="model-btn"
      :class="{ active, open: isOpen }"
      :title="modelButtonTitle"
      :aria-expanded="isOpen ? 'true' : 'false'"
      aria-haspopup="listbox"
      @click="toggleMenu"
      type="button"
    >
      <span class="model-icon">{{ currentModelIcon }}</span>
      <span class="model-name">{{ currentModelName }}</span>
      <span class="dropdown-arrow" :class="{ open: isOpen }">▼</span>
    </button>

    <Teleport to="body">
      <transition name="dropdown">
        <div
          v-if="isOpen"
          ref="dropdownRef"
          class="model-dropdown"
          :style="dropdownStyle"
          role="listbox"
          @click.stop
        >
          <div class="dropdown-inner">
            <div v-if="loading" class="loading-state">⏳ Loading models...</div>
            <div v-else-if="visibleProviders.length === 0" class="empty-state">No model catalog found</div>

            <template v-else-if="singleProviderMode">
              <div class="provider-inline-head" :class="{ disabled: !singleProviderEnabled }">
                <span class="provider-icon">{{ currentProviderIcon }}</span>
                <span class="provider-name">{{ currentProviderName }}</span>
                <span class="provider-status">{{ singleProviderEnabled ? 'Loaded' : 'Not configured' }}</span>
              </div>

              <div v-if="activeProviderModels.length" class="single-provider-list">
                <div
                  v-for="model in activeProviderModels"
                  :key="model.value"
                  class="model-option"
                  :class="{
                    selected: selectedModel === model.value,
                    disabled: isModelDisabled(model)
                  }"
                  :title="model.value"
                  role="option"
                  :aria-selected="selectedModel === model.value ? 'true' : 'false'"
                  @click="selectModel(model)"
                >
                  <span class="model-check">{{ selectedModel === model.value ? '✓' : '' }}</span>

                  <span class="model-label-wrap">
                    <span class="model-label">{{ model.label }}</span>
                    <span v-if="shouldShowModelId(model)" class="model-id">{{ formatModelId(model) }}</span>
                  </span>

                  <span class="model-meta">
                    <span v-if="model.badge" class="model-badge">{{ model.badge }}</span>
                    <span v-if="isModelDisabled(model)" class="model-disabled-tag">Not configured</span>
                  </span>
                </div>
              </div>

              <div v-else class="empty-state">
                No models for current provider
              </div>
            </template>

            <div v-else>
              <div
                v-for="provider in visibleProviders"
                :key="provider.key"
                class="provider-item"
                @mouseenter="onProviderEnter(provider.key)"
                @mouseleave="onProviderLeave(provider.key)"
              >
                <div
                  class="provider-header"
                  :class="{ disabled: !provider.enabled }"
                  :ref="(el) => setProviderHeaderRef(provider.key, el)"
                  @click="toggleProviderPin(provider.key)"
                >
                  <span class="provider-icon">{{ provider.icon }}</span>
                  <span class="provider-name">{{ provider.name }}</span>
                  <span v-if="!provider.enabled" class="provider-status-pill">Not configured</span>
                  <span class="expand-arrow" :class="{ open: isProviderOpen(provider.key) }">›</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <Teleport to="body">
      <transition name="submenu">
        <div
          v-if="!singleProviderMode && isOpen && activeProviderKey && activeProviderModels.length"
          ref="submenuRef"
          class="model-submenu-float"
          :style="submenuStyle"
          role="listbox"
          @mouseenter="onSubmenuEnter"
          @mouseleave="onSubmenuLeave"
          @click.stop
        >
          <div
            v-for="model in activeProviderModels"
            :key="model.value"
            class="model-option"
            :class="{
              selected: selectedModel === model.value,
              disabled: isModelDisabled(model)
            }"
            :title="model.value"
            role="option"
            :aria-selected="selectedModel === model.value ? 'true' : 'false'"
            @click="selectModel(model)"
          >
            <span class="model-check">{{ selectedModel === model.value ? '✓' : '' }}</span>

            <span class="model-label-wrap">
              <span class="model-label">{{ model.label }}</span>
              <span v-if="shouldShowModelId(model)" class="model-id">{{ formatModelId(model) }}</span>
            </span>

            <span class="model-meta">
              <span v-if="model.badge" class="model-badge">{{ model.badge }}</span>
              <span v-if="isModelDisabled(model)" class="model-disabled-tag">Not configured</span>
            </span>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useMCP } from '../composables/useMCP'

const props = defineProps({
  modelValue: { type: String, default: '' },
  active: { type: Boolean, default: false },
  provider: { type: String, default: '' },
  singleProvider: { type: Boolean, default: false },
  includeDisabled: { type: Boolean, default: true },
  allowDisabledSelection: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'change'])
const { callTool } = useMCP()

const selectorRef = ref(null)
const dropdownRef = ref(null)
const submenuRef = ref(null)

const isOpen = ref(false)
const loading = ref(false)
const providers = ref([])

const selectedModel = ref(props.modelValue || '')

const hoverProvider = ref(null)
const pinnedProvider = ref(null)
const submenuHovering = ref(false)
const lastHoverProvider = ref(null)
let closeHoverTimer = null

const dropdownStyle = ref({})
const submenuStyle = ref({})

const providerHeaderEls = new Map()

const providerMetaMap = {
  openai: { icon: '🤖', name: 'OpenAI' },
  anthropic: { icon: '🧠', name: 'Anthropic' },
  deepseek: { icon: '🔍', name: 'DeepSeek' }
}

function normalizeProviderKey(value) {
  return String(value || '').trim().toLowerCase()
}

function normalizeModelRow(providerKey, row) {
  const modelId = String(row?.model_id || row?.value || '').trim()
  return {
    provider: normalizeProviderKey(row?.provider || providerKey),
    model_id: modelId,
    value: modelId,
    label: String(row?.label || modelId || 'Unknown Model').trim() || 'Unknown Model',
    badge: String(row?.badge || '').trim(),
    family: String(row?.family || '').trim(),
    supports_tools: row?.supports_tools !== false,
    supports_stream: row?.supports_stream !== false,
    enabled: row?.enabled !== false,
    aliases: Array.isArray(row?.aliases) ? row.aliases : [],
    priority: Number.isFinite(Number(row?.priority)) ? Number(row.priority) : 99
  }
}

function buildProviderEntry(key, raw) {
  const providerKey = normalizeProviderKey(key)
  const meta = providerMetaMap[providerKey] || { icon: '🤖', name: providerKey || 'Unknown' }
  const rawModels = Array.isArray(raw?.models) ? raw.models : []
  const models = rawModels.map((item) => normalizeModelRow(providerKey, item))
  return {
    key: providerKey,
    icon: String(raw?.icon || meta.icon || '🤖'),
    name: String(raw?.name || meta.name || providerKey || 'Unknown'),
    enabled: raw?.enabled !== false && models.some((m) => m.enabled),
    models
  }
}

function orderedProviderKeys(source) {
  const preferred = ['openai', 'anthropic', 'deepseek']
  const keys = Object.keys(source || {})
  const result = []
  const seen = new Set()

  for (const key of [...preferred, ...keys]) {
    const k = normalizeProviderKey(key)
    if (!k || seen.has(k) || !source?.[k]) continue
    seen.add(k)
    result.push(k)
  }
  return result
}

function clearHoverCloseTimer() {
  if (closeHoverTimer) clearTimeout(closeHoverTimer)
  closeHoverTimer = null
}

function scheduleCloseHover(delayMs = 220) {
  clearHoverCloseTimer()
  closeHoverTimer = setTimeout(() => {
    if (!pinnedProvider.value && !submenuHovering.value) {
      hoverProvider.value = null
      lastHoverProvider.value = null
    }
  }, delayMs)
}

function setProviderHeaderRef(key, el) {
  if (!key) return
  if (el) providerHeaderEls.set(key, el)
  else providerHeaderEls.delete(key)
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n))
}

const normalizedProvider = computed(() => normalizeProviderKey(props.provider))
const singleProviderMode = computed(() => !!props.singleProvider)

const visibleProviders = computed(() => {
  const rows = Array.isArray(providers.value) ? providers.value : []
  if (singleProviderMode.value && normalizedProvider.value) {
    return rows.filter((item) => item.key === normalizedProvider.value)
  }
  return rows
})

const activeProviderKey = computed(() => {
  if (singleProviderMode.value) {
    if (normalizedProvider.value) return normalizedProvider.value
    return visibleProviders.value[0]?.key || null
  }
  return pinnedProvider.value || hoverProvider.value || null
})

const activeProvider = computed(() => {
  const key = activeProviderKey.value
  if (!key) return null
  return visibleProviders.value.find((item) => item.key === key) || null
})

const activeProviderModels = computed(() => {
  const provider = activeProvider.value
  return Array.isArray(provider?.models) ? provider.models : []
})

const singleProviderEnabled = computed(() => {
  return !!activeProvider.value?.enabled
})

const currentProviderIcon = computed(() => {
  const provider = activeProvider.value
  if (provider?.icon) return provider.icon
  if (normalizedProvider.value && providerMetaMap[normalizedProvider.value]) {
    return providerMetaMap[normalizedProvider.value].icon
  }
  return '🤖'
})

const currentProviderName = computed(() => {
  const provider = activeProvider.value
  if (provider?.name) return provider.name
  if (normalizedProvider.value && providerMetaMap[normalizedProvider.value]) {
    return providerMetaMap[normalizedProvider.value].name
  }
  return 'Model'
})

const currentModelInfo = computed(() => {
  const allProviders = Array.isArray(providers.value) ? providers.value : []
  for (const provider of allProviders) {
    const model = (provider.models || []).find((item) => item.value === selectedModel.value)
    if (model) {
      return {
        icon: provider.icon,
        name: model.label,
        enabled: model.enabled,
        provider: provider.key
      }
    }
  }

  if (singleProviderMode.value && normalizedProvider.value) {
    const meta = providerMetaMap[normalizedProvider.value] || { icon: '🤖', name: 'Model' }
    return {
      icon: meta.icon,
      name: String(selectedModel.value || 'Select model').trim() || 'Select model',
      enabled: true,
      provider: normalizedProvider.value
    }
  }

  return {
    icon: '🤖',
    name: String(selectedModel.value || 'Select model').trim() || 'Select model',
    enabled: true,
    provider: ''
  }
})

const currentModelIcon = computed(() => currentModelInfo.value.icon)
const currentModelName = computed(() => currentModelInfo.value.name)
const modelButtonTitle = computed(() => (isOpen.value ? 'Close model list' : 'Open model list'))

const activeLabelCounts = computed(() => {
  const map = new Map()
  for (const m of activeProviderModels.value) {
    const label = String(m?.label || '').trim()
    if (!label) continue
    map.set(label, (map.get(label) || 0) + 1)
  }
  return map
})

function isProviderOpen(key) {
  return pinnedProvider.value === key || hoverProvider.value === key
}

function isModelDisabled(model) {
  return !model?.enabled
}

function shouldShowModelId(model) {
  const v = String(model?.value || '').trim()
  const label = String(model?.label || '').trim()
  if (!v) return false

  if (label && (activeLabelCounts.value.get(label) || 0) > 1) return true
  if (/\d{4}-\d{2}-\d{2}$/.test(v)) return true
  if (/\d{8}$/.test(v)) return true
  if (/gpt-\d+(\.\d+)+/i.test(v)) return true
  if (v !== label) return true

  return false
}

function formatModelId(model) {
  const v = String(model?.value || '').trim()
  if (!v) return ''

  const m1 = v.match(/gpt-(\d+(?:\.\d+)?)-(\d{4}-\d{2}-\d{2})$/i)
  if (m1) return `${m1[1]} · ${m1[2]}`

  const m2 = v.match(/(\d{4}-\d{2}-\d{2})$/)
  if (m2) return m2[1]

  const m3 = v.match(/(\d{8})$/)
  if (m3) return m3[1]

  if (v.length > 26) return `…${v.slice(-22)}`
  return v
}

async function updateDropdownPosition() {
  await nextTick()
  const sel = selectorRef.value
  const dd = dropdownRef.value
  if (!sel || !dd) return

  const rect = sel.getBoundingClientRect()
  const vw = window.innerWidth || document.documentElement.clientWidth || 360
  const vh = window.innerHeight || document.documentElement.clientHeight || 640
  const pad = 8
  const gap = 8

  dropdownStyle.value = {
    position: 'fixed',
    top: `${Math.round(rect.bottom + gap)}px`,
    left: `${Math.round(rect.left)}px`,
    minWidth: `${Math.max(singleProviderMode.value ? 280 : 220, rect.width)}px`,
    maxWidth: `calc(100vw - ${pad * 2}px)`,
    zIndex: 2147483000
  }

  await nextTick()

  const ddr = dd.getBoundingClientRect()
  let left = ddr.left
  const overflowRight = ddr.right - (vw - pad)
  if (overflowRight > 0) left -= overflowRight
  left = clamp(left, pad, vw - pad - Math.min(ddr.width, vw - pad * 2))
  dropdownStyle.value = { ...dropdownStyle.value, left: `${Math.round(left)}px` }

  const ddr2 = dd.getBoundingClientRect()
  const overflowBottom = ddr2.bottom - (vh - pad)
  if (overflowBottom > 0) {
    const tryTop = rect.top - ddr2.height - gap
    const top = clamp(tryTop, pad, vh - pad - ddr2.height)
    dropdownStyle.value = { ...dropdownStyle.value, top: `${Math.round(top)}px` }
  }
}

async function updateSubmenuPosition() {
  if (singleProviderMode.value) return

  await nextTick()
  const key = activeProviderKey.value
  const headerEl = key ? providerHeaderEls.get(key) : null
  const sm = submenuRef.value
  if (!key || !headerEl || !sm) return

  const rect = headerEl.getBoundingClientRect()
  const vw = window.innerWidth || document.documentElement.clientWidth || 360
  const vh = window.innerHeight || document.documentElement.clientHeight || 640
  const pad = 8
  const gap = 8

  submenuStyle.value = {
    position: 'fixed',
    top: `${Math.round(rect.top)}px`,
    left: `${Math.round(rect.right + gap)}px`,
    minWidth: '300px',
    maxWidth: `calc(100vw - ${pad * 2}px)`,
    maxHeight: '70vh',
    overflowY: 'auto',
    overflowX: 'hidden',
    zIndex: 2147483001
  }

  await nextTick()

  const smRect = sm.getBoundingClientRect()
  const spaceRight = vw - rect.right
  const spaceLeft = rect.left

  const preferBelow = vw <= 520
  const canRight = spaceRight >= smRect.width + pad + gap
  const canLeft = spaceLeft >= smRect.width + pad + gap

  let left = smRect.left
  let top = smRect.top

  if (!preferBelow && canRight) {
    left = rect.right + gap
    top = rect.top
  } else if (!preferBelow && canLeft) {
    left = rect.left - smRect.width - gap
    top = rect.top
  } else {
    left = clamp(rect.left, pad, vw - pad - smRect.width)
    top = rect.bottom + 6
  }

  top = clamp(top, pad, vh - pad - smRect.height)

  submenuStyle.value = {
    ...submenuStyle.value,
    left: `${Math.round(left)}px`,
    top: `${Math.round(top)}px`
  }
}

function onProviderEnter(key) {
  if (singleProviderMode.value) return
  clearHoverCloseTimer()
  hoverProvider.value = key
  lastHoverProvider.value = key
}

function onProviderLeave(key) {
  if (singleProviderMode.value) return
  if (hoverProvider.value === key && !pinnedProvider.value) scheduleCloseHover(220)
}

function onSubmenuEnter() {
  submenuHovering.value = true
  clearHoverCloseTimer()
  if (!pinnedProvider.value && !hoverProvider.value && lastHoverProvider.value) {
    hoverProvider.value = lastHoverProvider.value
  }
}

function onSubmenuLeave() {
  submenuHovering.value = false
  if (!pinnedProvider.value) scheduleCloseHover(220)
}

function toggleProviderPin(key) {
  if (singleProviderMode.value) return
  clearHoverCloseTimer()
  pinnedProvider.value = pinnedProvider.value === key ? null : key
  if (pinnedProvider.value) {
    hoverProvider.value = pinnedProvider.value
    lastHoverProvider.value = pinnedProvider.value
  }
}

function closeAll() {
  isOpen.value = false
  hoverProvider.value = null
  pinnedProvider.value = null
  lastHoverProvider.value = null
  submenuHovering.value = false
  clearHoverCloseTimer()
}

function toggleMenu() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    hoverProvider.value = null
    pinnedProvider.value = null
    lastHoverProvider.value = null
    submenuHovering.value = false
    nextTick(() => updateDropdownPosition())
  } else {
    closeAll()
  }
}

function selectModel(model) {
  if (isModelDisabled(model) && !props.allowDisabledSelection) return
  selectedModel.value = model.value
  emit('update:modelValue', model.value)
  emit('change', model)
  closeAll()
}

async function loadModels() {
  loading.value = true
  try {
    const result = await callTool('nisb_chat_models', {
      include_disabled: props.includeDisabled,
      refresh: false
    })

    const sourceProviders =
      result?.tool_results?.providers ||
      result?.providers ||
      {}

    const keys = orderedProviderKeys(sourceProviders)
    providers.value = keys.map((key) => buildProviderEntry(key, sourceProviders[key]))

    if (!selectedModel.value) {
      const defaultModel =
        result?.tool_results?.default_model ||
        result?.default ||
        ''
      if (defaultModel) {
        selectedModel.value = String(defaultModel)
      }
    }
  } catch {
    providers.value = [
      {
        key: 'openai',
        icon: '🤖',
        name: 'OpenAI',
        enabled: true,
        models: [
          { provider: 'openai', model_id: 'gpt-5', value: 'gpt-5', label: 'GPT-5', badge: 'New', enabled: true, aliases: [], priority: 0 },
          { provider: 'openai', model_id: 'gpt-5-mini', value: 'gpt-5-mini', label: 'GPT-5 Mini', badge: 'Recommended', enabled: true, aliases: [], priority: 1 },
          { provider: 'openai', model_id: 'gpt-4o', value: 'gpt-4o', label: 'GPT-4o', badge: 'Latest', enabled: true, aliases: [], priority: 2 },
          { provider: 'openai', model_id: 'gpt-4o-mini', value: 'gpt-4o-mini', label: 'GPT-4o Mini', badge: 'Recommended', enabled: true, aliases: [], priority: 3 }
        ]
      },
      {
        key: 'anthropic',
        icon: '🧠',
        name: 'Anthropic',
        enabled: false,
        models: [
          { provider: 'anthropic', model_id: 'claude-sonnet-4-5-20250929', value: 'claude-sonnet-4-5-20250929', label: 'Claude Sonnet 4.5', badge: 'Strongest', enabled: false, aliases: [], priority: 0 }
        ]
      },
      {
        key: 'deepseek',
        icon: '🔍',
        name: 'DeepSeek',
        enabled: false,
        models: [
          { provider: 'deepseek', model_id: 'deepseek-chat', value: 'deepseek-chat', label: 'DeepSeek Chat', badge: '', enabled: false, aliases: [], priority: 0 }
        ]
      }
    ]
  } finally {
    loading.value = false
  }
}

function onGlobalPointerDown(e) {
  if (!isOpen.value) return
  const path = typeof e.composedPath === 'function' ? e.composedPath() : []
  const t = e.target

  const inSelector = selectorRef.value && (selectorRef.value.contains(t) || path.includes(selectorRef.value))
  const inDropdown = dropdownRef.value && (dropdownRef.value.contains(t) || path.includes(dropdownRef.value))
  const inSubmenu = submenuRef.value && (submenuRef.value.contains(t) || path.includes(submenuRef.value))

  if (inSelector || inDropdown || inSubmenu) return
  closeAll()
}

watch(
  () => props.modelValue,
  (val) => {
    const next = String(val || '').trim()
    if (next !== selectedModel.value) selectedModel.value = next
  },
  { immediate: true }
)

watch(
  () => props.provider,
  async () => {
    if (!isOpen.value) return
    await nextTick()
    await updateDropdownPosition()
  }
)

watch(isOpen, (val) => {
  if (val) {
    window.addEventListener('scroll', updateDropdownPosition, true)
    window.addEventListener('resize', updateDropdownPosition)
  } else {
    window.removeEventListener('scroll', updateDropdownPosition, true)
    window.removeEventListener('resize', updateDropdownPosition)
  }
})

watch(activeProviderKey, async () => {
  if (!isOpen.value || singleProviderMode.value) return
  await nextTick()
  await updateSubmenuPosition()
})

onMounted(() => {
  document.addEventListener('pointerdown', onGlobalPointerDown, true)
  loadModels()
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onGlobalPointerDown, true)
  window.removeEventListener('scroll', updateDropdownPosition, true)
  window.removeEventListener('resize', updateDropdownPosition)
  clearHoverCloseTimer()
})
</script>

<style scoped>
.model-selector {
  position: relative;
  width: 100%;
  min-width: 0;
}

.model-btn {
  width: 100%;
  min-width: 160px;
  height: 30px;
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 56%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 34%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 720;
  line-height: 1;
  text-align: left;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.model-btn:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--selected-bg) 52%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  color: var(--text-main, var(--text));
}

.model-btn.active {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 62%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 8%, transparent)
    );
  color: var(--selected);
  font-weight: 780;
}

.model-btn.open {
  border-color: color-mix(in srgb, var(--selected) 74%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 76%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 14%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 12%, transparent),
    0 10px 26px rgba(0, 0, 0, 0.12);
  font-weight: 820;
}

.model-btn:active {
  transform: translateY(1px);
}

.model-icon {
  flex-shrink: 0;
  font-size: 0.95rem;
  line-height: 1;
}

.model-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1;
}

.dropdown-arrow {
  flex-shrink: 0;
  color: inherit;
  font-size: 0.68rem;
  line-height: 1;
  opacity: 0.84;
  transition:
    transform 0.2s ease,
    opacity 0.15s ease;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
  opacity: 1;
}

.model-dropdown,
.model-submenu-float {
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 42%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 18px 46px rgba(0, 0, 0, 0.30),
    0 2px 14px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(16px);
}

.dropdown-inner {
  max-height: 70vh;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 6px;
  scrollbar-width: thin;
}

.loading-state,
.empty-state {
  padding: 0.95rem;
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 700;
  line-height: 1.45;
  text-align: center;
  overflow-wrap: break-word;
}

.provider-item {
  border-bottom: 1px solid color-mix(in srgb, var(--line) 62%, transparent);
}

.provider-item:last-child {
  border-bottom: none;
}

.provider-header,
.provider-inline-head {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid transparent;
  border-radius: 10px;
  user-select: none;
}

.provider-header {
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.provider-header:hover {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
}

.provider-header.disabled,
.provider-inline-head.disabled {
  opacity: 0.78;
}

.provider-icon {
  flex-shrink: 0;
  font-size: 1.05rem;
  line-height: 1;
}

.provider-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--text-main, var(--text));
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 760;
}

.provider-status,
.provider-status-pill {
  flex-shrink: 0;
  padding: 0.13rem 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 740;
  line-height: 1.2;
}

.expand-arrow {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 1.1rem;
  line-height: 1;
  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.expand-arrow.open {
  color: var(--selected);
  transform: rotate(90deg);
}

.single-provider-list {
  padding: 0.15rem 0;
}

.model-option {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.58rem;
  padding: 0.58rem 0.72rem;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.model-option:hover {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, var(--editor-bg));
}

.model-option.selected {
  border-color: color-mix(in srgb, var(--selected) 32%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 66%, var(--editor-bg)),
      color-mix(in srgb, var(--selected) 10%, transparent)
    );
  color: var(--selected);
}

.model-option.disabled {
  opacity: 0.72;
}

.model-option.disabled:hover {
  border-color: color-mix(in srgb, var(--line) 74%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 36%, transparent);
}

.model-check {
  flex-shrink: 0;
  width: 1rem;
  color: var(--selected);
  font-weight: 820;
  line-height: 1;
}

.model-label-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.model-label {
  overflow: hidden;
  color: var(--text-main, var(--text));
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 720;
  line-height: 1.25;
}

.model-option.selected .model-label {
  color: var(--selected);
  font-weight: 820;
}

.model-id {
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  line-height: 1.25;
}

.model-meta {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
}

.model-badge,
.model-disabled-tag {
  padding: 0.18rem 0.42rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1.15;
}

.model-badge {
  border: 1px solid color-mix(in srgb, var(--selected) 34%, transparent);
  background: color-mix(in srgb, var(--selected) 14%, transparent);
  color: var(--selected);
}

.model-disabled-tag {
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-5px) scale(0.99);
}

.submenu-enter-active,
.submenu-leave-active {
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.submenu-enter-from,
.submenu-leave-to {
  opacity: 0;
  transform: translateX(-6px) scale(0.99);
}

@media (max-width: 520px) {
  .model-btn {
    min-width: 0;
  }

  .model-dropdown,
  .model-submenu-float {
    border-radius: 13px;
  }

  .model-option {
    min-height: 36px;
  }
}
</style>
