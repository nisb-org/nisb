from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_sys_path() -> None:
    current = Path(__file__).resolve()
    project_root = current.parents[3]
    project_root_str = str(project_root)

    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_sys_path()
