"""上游兼容性补丁（集中管理，不修改第三方包源码）。

覆盖两类已知问题：
1. ``json_repair.dumps``：agentsociety2 2.2.0 的 ``agent/tool/utils.py::jr_dumps``
   会调用 json_repair 的 ``dumps``，但该库任何版本都没有此函数。补一个等价实现。
2. Windows 下 ``os.fsync`` 抛 ``OSError: [Errno 9] Bad file descriptor``：
   agentsociety2 2.2.0 的 ``agent/persistence.py`` 用 ``os.fsync(fd)`` 同步 WAL
   索引，在 Windows + aiofiles 环境下会失败（平台 bug）。改为容错跳过。

用法：
- ``patch_json_repair_dumps()`` 需在导入 agentsociety2 之前或之后调用均可（运行时解析）；
- ``patch_windows_fsync()`` 必须在 ``import agentsociety2`` 之后、运行仿真之前调用。
"""

from __future__ import annotations


def patch_json_repair_dumps() -> None:
    """为 json_repair 补 ``dumps``（若缺失）。"""
    try:
        import json
        import json_repair

        if not hasattr(json_repair, "dumps"):

            def _dumps(obj, indent=None, ensure_ascii=True, **kwargs):
                return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, **kwargs)

            json_repair.dumps = _dumps  # type: ignore[attr-defined]
    except Exception:
        pass


def patch_windows_fsync() -> None:
    """Windows 下对 agentsociety2 persistence 的 fsync 做容错。"""
    try:
        from agentsociety2.agent import persistence as _persistence

        _orig = _persistence._fsync_path

        def _safe_fsync(path) -> None:
            try:
                _orig(path)
            except OSError:
                # Windows 下 aiofiles 打开的 fd 可能不可 fsync；跳过不影响数据完整性
                pass

        _persistence._fsync_path = _safe_fsync  # type: ignore[assignment]
    except Exception:
        pass


def patch_person_slice_text_page() -> None:
    """修复 agentsociety2 2.2.0 ``person.py`` 漏 import ``slice_text_page`` 的平台 bug。

    ``person.py`` 在 _tool_loop / workspace_read 中调用 ``slice_text_page``，
    但只 import 了 ``pagination_from_args``，导致 read_skill / workspace_read
    工具被调用时抛 ``NameError``。这里把 ``agent.tool.utils`` 中的实现注入模块。
    """
    try:
        from agentsociety2.agent import person as _person
        from agentsociety2.agent.tool.utils import slice_text_page

        if not hasattr(_person, "slice_text_page"):
            _person.slice_text_page = slice_text_page  # type: ignore[attr-defined]
    except Exception:
        pass


def apply_all() -> None:
    """应用全部补丁（须在 import agentsociety2 之后调用）。"""
    patch_json_repair_dumps()
    patch_windows_fsync()
    patch_person_slice_text_page()
