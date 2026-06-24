<!-- /opt/mcp-gateway/nisb-web/src/components/common/Drawer.vue -->
<template>
  <Transition name="drawer-fade">
    <div v-if="modelValue" class="drawer-overlay" @click="handleClose">
      <div 
        class="drawer-content"
        :class="[`drawer-${position}`, heightClass]"
        :style="contentStyle"
        @click.stop
      >
        <!-- 顶部把手（仅底部抽屉） -->
        <div v-if="position === 'bottom'" class="drawer-handle-bar">
          <div class="drawer-handle"></div>
        </div>
        
        <!-- 头部（可选） -->
        <div v-if="title" class="drawer-header">
          <h3 class="drawer-title">{{ title }}</h3>
          <button class="drawer-close" @click="handleClose">×</button>
        </div>
        
        <!-- 内容区 -->
        <div class="drawer-body" :class="{ 'has-header': title }">
          <slot></slot>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  position: { type: String, default: 'bottom' }, // 'bottom' | 'right'
  height: { type: String, default: '60%' }, // 仅 bottom 生效
  width: { type: String, default: '400px' }, // 仅 right 生效
  title: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

const heightClass = computed(() => {
  if (props.position !== 'bottom') return ''
  if (props.height === '100%') return 'drawer-full'
  if (props.height.includes('%') && parseInt(props.height) >= 80) return 'drawer-tall'
  return 'drawer-medium'
})

const contentStyle = computed(() => {
  if (props.position === 'bottom') {
    return { height: props.height }
  }
  return { width: props.width }
})

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 999;
  display: flex;
}

.drawer-content {
  background: var(--editor-bg);
  overflow-y: auto;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
}

/* 底部抽屉 */
.drawer-bottom {
  align-self: flex-end;
  width: 100%;
  border-radius: 16px 16px 0 0;
  max-height: 90vh;
}

/* 右侧抽屉 */
.drawer-right {
  align-self: stretch;
  margin-left: auto;
  height: 100vh;
  border-radius: 0;
}

.drawer-handle-bar {
  padding: 12px 0;
  display: flex;
  justify-content: center;
  cursor: grab;
  flex-shrink: 0;
}

.drawer-handle {
  width: 40px;
  height: 4px;
  background: var(--line);
  border-radius: 2px;
  opacity: 0.6;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.drawer-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  margin: 0;
}

.drawer-close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1.5rem;
  line-height: 1;
  transition: all var(--transition-normal) var(--ease-smooth);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-close:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.drawer-body {
  padding: 1rem;
  overflow-y: auto;
  flex: 1;
}

.drawer-body.has-header {
  padding-top: 0.75rem;
}

/* 动画 */
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.25s ease;
}

.drawer-fade-enter-active .drawer-content,
.drawer-fade-leave-active .drawer-content {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-fade-enter-from .drawer-bottom,
.drawer-fade-leave-to .drawer-bottom {
  transform: translateY(100%);
}

.drawer-fade-enter-from .drawer-right,
.drawer-fade-leave-to .drawer-right {
  transform: translateX(100%);
}

/* 移动端优化 */
@media (max-width: 768px) {
  .drawer-bottom {
    border-radius: 12px 12px 0 0;
  }
  
  .drawer-body {
    padding: 0.75rem;
  }
}
</style>
