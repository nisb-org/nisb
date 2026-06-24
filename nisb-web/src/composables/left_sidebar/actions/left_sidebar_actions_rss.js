// /opt/mcp-gateway/nisb-web/src/composables/left_sidebar/actions/left_sidebar_actions_rss.js

export function create_left_sidebar_rss_actions({
  call_tool,
  toast,
  hide_context_menu,
  pick_cm,
  cm_target_id,
  cm_target_name
}) {
  async function handle_rss_rename(cm_in) {
    const cm = pick_cm(cm_in)
    const feed_id = cm_target_id(cm)
    const old_name = cm_target_name(cm) || ''
    const new_name = window.prompt('新名称：', old_name)
    if (!new_name || new_name.trim() === old_name.trim()) return hide_context_menu()

    const r = await call_tool('nisb_rss_update_feed', { feed_id, custom_name: new_name.trim() })
    if (r?.success) {
      toast(`✅ 已重命名：${new_name.trim()}`, 'success')
      window.dispatchEvent(new CustomEvent('nisb-rss-refresh'))
    } else {
      toast(`❌ 重命名失败：${r?.message || r?.detail || '未知错误'}`, 'error')
    }
    hide_context_menu()
  }

  async function handle_rss_edit_tags(cm_in) {
    const cm = pick_cm(cm_in)
    const feed_id = cm_target_id(cm)
    const raw = window.prompt('标签（逗号分隔）：', '') || ''
    const tags = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    const r = await call_tool('nisb_rss_update_feed', { feed_id, tags })
    if (r?.success) {
      toast('✅ 标签已更新', 'success')
      window.dispatchEvent(new CustomEvent('nisb-rss-refresh'))
    } else {
      toast(`❌ 标签更新失败：${r?.message || r?.detail || '未知错误'}`, 'error')
    }
    hide_context_menu()
  }

  async function handle_rss_delete(cm_in) {
    const cm = pick_cm(cm_in)
    const feed_id = cm_target_id(cm)
    const name = cm_target_name(cm) || feed_id
    if (!window.confirm(`删除订阅「${name}」？（将同时删除本地文章与状态）`)) return hide_context_menu()

    const r = await call_tool('nisb_rss_delete_feed', { feed_id, delete_files: true })
    if (r?.success) {
      toast('✅ 已删除订阅', 'success')
      window.dispatchEvent(new CustomEvent('nisb-rss-refresh'))
    } else {
      toast(`❌ 删除失败：${r?.message || r?.detail || '未知错误'}`, 'error')
    }
    hide_context_menu()
  }

  return {
    handle_rss_rename,
    handle_rss_edit_tags,
    handle_rss_delete
  }
}

