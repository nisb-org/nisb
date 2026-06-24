# /opt/mcp-gateway/mcp-nisb/tools/rss/__init__.py
from .tools import (
    nisb_rss_add_feed,
    nisb_rss_list_feeds,
    nisb_rss_fetch,
    nisb_rss_list_articles,
    nisb_rss_get_article,
    nisb_rss_set_state,
    nisb_rss_evidence_scope,
    nisb_rss_update_feed,
    nisb_rss_delete_feed,
    nisb_rss_list_tags,
    nisb_rss_gate_prefs_get,
    nisb_rss_gate_prefs_set,
    nisb_rss_delete_article,
    nisb_rss_override_article,
)

from .fetch_due import nisb_rss_fetch_due

from .semantic_search import nisb_rss_semantic_search
from .semantic_index import rebuild_index as nisb_rss_index_rebuild

from .gate_candidates import nisb_rss_gate_candidates

from .spam_blacklist import (
    nisb_rss_spam_add,
    nisb_rss_spam_list,
    nisb_rss_spam_delete,
)

from .gate_import_to_library import nisb_rss_gate_import_to_library
from .gate_bulk_delete import nisb_rss_gate_bulk_delete

from .auto_import_rules import (
    nisb_rss_auto_import_rules_get,
    nisb_rss_auto_import_rules_set,
    nisb_rss_auto_import_run_rule,
    nisb_rss_auto_import_run_due,
)

from .auto_fetch_scheduler import (
    nisb_rss_auto_fetch_config_get,
    nisb_rss_auto_fetch_config_set,
    nisb_rss_auto_fetch_run_now,
    nisb_rss_auto_fetch_config_delete,
)

# ✅ 新增：RSS 进程内缓存治理（按钮会调用）
from .cache_control import (
    nisb_rss_cache_stats,
    nisb_rss_cache_clear,
)

# ✅ 新增：RSS 数据真删除（原子落盘 + 可选流式重建 embeddings）
from .rss_data_cleanup import nisb_rss_data_cleanup

# ✅ 新增：RSS 自动清理配置/执行（配置落盘，供 scheduler tick 调用）
from .auto_cleanup_scheduler import (
    nisb_rss_auto_cleanup_config_get,
    nisb_rss_auto_cleanup_config_set,
    nisb_rss_auto_cleanup_run_now,
    nisb_rss_auto_cleanup_config_delete,
)

__all__ = [
    "nisb_rss_add_feed",
    "nisb_rss_list_feeds",
    "nisb_rss_fetch",
    "nisb_rss_list_articles",
    "nisb_rss_get_article",
    "nisb_rss_set_state",
    "nisb_rss_evidence_scope",
    "nisb_rss_update_feed",
    "nisb_rss_delete_feed",
    "nisb_rss_list_tags",
    "nisb_rss_semantic_search",
    "nisb_rss_index_rebuild",
    "nisb_rss_gate_candidates",
    "nisb_rss_spam_add",
    "nisb_rss_spam_list",
    "nisb_rss_spam_delete",
    "nisb_rss_gate_import_to_library",
    "nisb_rss_gate_prefs_get",
    "nisb_rss_gate_prefs_set",
    "nisb_rss_delete_article",
    "nisb_rss_override_article",
    "nisb_rss_gate_bulk_delete",
    "nisb_rss_fetch_due",
    # ⭐ 自动入库规则
    "nisb_rss_auto_import_rules_get",
    "nisb_rss_auto_import_rules_set",
    "nisb_rss_auto_import_run_rule",
    "nisb_rss_auto_import_run_due",
    # ⭐ 自动更新 RSS（计划任务：读配置 -> fetch_due）
    "nisb_rss_auto_fetch_config_get",
    "nisb_rss_auto_fetch_config_set",
    "nisb_rss_auto_fetch_run_now",
    "nisb_rss_auto_fetch_config_delete",
    # ✅ 新增：缓存治理工具
    "nisb_rss_cache_stats",
    "nisb_rss_cache_clear",
    # ✅ 新增：数据清理工具
    "nisb_rss_data_cleanup",
    # ✅ 新增：自动清理工具
    "nisb_rss_auto_cleanup_config_get",
    "nisb_rss_auto_cleanup_config_set",
    "nisb_rss_auto_cleanup_run_now",
    "nisb_rss_auto_cleanup_config_delete",
]

