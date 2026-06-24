# /opt/mcp-gateway/mcp-nisb/tools/filesystem/__init__.py
"""
Filesystem tool package with guarded capability_gate entry points.
"""

from .core import (
    nisb_file_move,
    nisb_file_copy,
)

from .search import (
    nisb_file_list,
    nisb_file_search,
    nisb_file_info,
)

from .batch import (
    nisb_file_read_multiple,
    nisb_file_batch_delete,
    nisb_file_batch_tag,
)

from .backup import (
    create_backup,
    list_backups,
    restore_backup,
    should_backup,
)

from .hebbian import (
    nisb_note_to_brain,
    nisb_batch_notes_to_brain,
)

from .favorites import (
    nisb_favorites_list_files,
    nisb_favorites_toggle_file,
    nisb_favorites_set_highlight,
    nisb_favorites_clear_highlight,
)

from .send_to_library_tool import (
    nisb_fs_send_to_library,
    nisb_fs_send_dir_to_library,
    nisb_fs_library_status_batch,
)

from .audit_tools import (
    nisb_fs_audit_tail,
    nisb_fs_restore_backup,
    nisb_fs_audit_search,
)

from .batch_apply import (
    nisb_fs_apply_batch,
)

from .trash_batches import nisb_fs_trash_batches_list
from .trash_batch_detail import nisb_fs_trash_batch_get, nisb_fs_trash_batch_purge
from .trash_purge_all import nisb_fs_trash_purge_all

from .file_read_base64 import nisb_file_read_base64
from .file_write_base64 import nisb_file_write_base64, nisb_file_write_base64_chunk
from .backups_tools import nisb_fs_backups_stats, nisb_fs_backups_purge_all


from .guarded_tools import (
    nisb_file_create,
    nisb_file_read,
    nisb_file_update,
    nisb_file_delete,
    nisb_file_move_path,
    nisb_file_rename,

    nisb_dir_create,
    nisb_dir_list,
    nisb_dir_tree,
    nisb_file_list_allowed_directories,

    nisb_dir_delete,
    nisb_dir_delete_recursive,
    nisb_dir_move_path,

    nisb_fs_snapshot,
    nisb_fs_trash_list,
    nisb_fs_trash_restore,

    nisb_fs_bulk_delete,
    nisb_fs_bulk_restore,
)

__all__ = [
    "nisb_file_create",
    "nisb_file_read",
    "nisb_file_update",
    "nisb_file_delete",
    "nisb_file_move",
    "nisb_file_move_path",
    "nisb_file_copy",
    "nisb_file_rename",

    "nisb_dir_create",
    "nisb_dir_list",
    "nisb_dir_tree",
    "nisb_file_list_allowed_directories",
    "nisb_dir_delete",
    "nisb_dir_delete_recursive",
    "nisb_dir_move_path",

    "nisb_file_list",
    "nisb_file_search",
    "nisb_file_info",

    "nisb_file_read_multiple",
    "nisb_file_batch_delete",
    "nisb_file_batch_tag",

    "create_backup",
    "list_backups",
    "restore_backup",
    "should_backup",

    "nisb_note_to_brain",
    "nisb_batch_notes_to_brain",

    "nisb_favorites_list_files",
    "nisb_favorites_toggle_file",
    "nisb_favorites_set_highlight",
    "nisb_favorites_clear_highlight",

    "nisb_fs_send_to_library",
    "nisb_fs_send_dir_to_library",
    "nisb_fs_library_status_batch",

    "nisb_fs_audit_tail",
    "nisb_fs_restore_backup",
    "nisb_fs_audit_search",
    "nisb_fs_apply_batch",

    "nisb_fs_snapshot",
    "nisb_fs_trash_list",
    "nisb_fs_trash_restore",
    "nisb_fs_bulk_delete",
    "nisb_fs_bulk_restore",

    "nisb_fs_trash_batches_list",
    "nisb_fs_trash_batch_get",
    "nisb_fs_trash_batch_purge",
    "nisb_fs_trash_purge_all",

    "nisb_file_read_base64",
    "nisb_file_write_base64",
    "nisb_file_write_base64_chunk",

    "nisb_fs_backups_stats",
    "nisb_fs_backups_purge_all",
]
