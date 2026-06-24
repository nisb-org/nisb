<template>
  <!-- 目前只是一个轻量壳子，保留统一样式和插槽扩展点 -->
  <div class="actions-bar">
    <div class="side left">
      <slot name="left" />
    </div>
    <div class="spacer" />
    <div class="side right">
      <slot name="right" />
    </div>
  </div>
</template>

<script setup>
// 暂时不需要逻辑，保留将来扩展注册表/动态组件的空间
</script>

<style scoped>
.actions-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.6rem;
  border-top: 1px solid var(--line);
  background: var(--sidebar-bg);
  min-height: 32px;
}

.side {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.spacer {
  flex: 1;
}

/* 通用动作按钮样式，供子组件复用 */
.action-btn {
  height: 28px;
  padding: 0 0.6rem;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.8rem;
  font-family: inherit;
  white-space: nowrap;
}

.action-btn:hover {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.action-btn.toggle-on {
  border-color: var(--selected);
  color: var(--selected);
}
</style>

