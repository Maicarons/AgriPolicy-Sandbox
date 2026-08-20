"""LLM 配置加载与校验。

AgentSociety² 通过以下环境变量读取 LLM 凭证（详见 agentsociety2.config）：
- AGENTSOCIETY_LLM_API_KEY   （必填）
- AGENTSOCIETY_LLM_API_BASE  （默认 https://api.openai.com/v1）
- AGENTSOCIETY_LLM_MODEL     （默认 gpt-5.4）
- AGENTSOCIETY_CODER_LLM_*    （可选，回退到 LLM_*）
- AGENTSOCIETY_NANO_LLM_*     （可选，回退到 LLM_*）
- AGENTSOCIETY_ANALYSIS_LLM_* （可选，回退到 LLM_*）

本模块负责：
1. 从项目根目录的 .env 加载上述变量（若存在）；
2. 在真正构建仿真前校验关键变量是否齐全，给出清晰报错。

注意：本文件不写入任何密钥；.env 已被 .gitignore 忽略，切勿提交。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRED_VARS = ("AGENTSOCIETY_LLM_API_KEY",)
OPTIONAL_VARS = (
    "AGENTSOCIETY_LLM_API_BASE",
    "AGENTSOCIETY_LLM_MODEL",
    "AGENTSOCIETY_CODER_LLM_API_KEY",
    "AGENTSOCIETY_CODER_LLM_API_BASE",
    "AGENTSOCIETY_CODER_LLM_MODEL",
    "AGENTSOCIETY_NANO_LLM_API_KEY",
    "AGENTSOCIETY_NANO_LLM_API_BASE",
    "AGENTSOCIETY_NANO_LLM_MODEL",
    "AGENTSOCIETY_ANALYSIS_LLM_API_KEY",
    "AGENTSOCIETY_ANALYSIS_LLM_API_BASE",
    "AGENTSOCIETY_ANALYSIS_LLM_MODEL",
)


def _find_dotenv(start: Path | None = None) -> Path | None:
    """从 start（默认当前工作目录）向上查找 .env 文件。"""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        cand = parent / ".env"
        if cand.is_file():
            return cand
    return None


def load_dotenv_if_present(start: Path | None = None) -> bool:
    """若存在 .env 则加载到环境变量（不覆盖已存在的变量）。

    优先使用 python-dotenv；不可用时退化为手工解析，避免引入硬依赖。
    返回是否找到并加载了 .env。
    """
    dotenv_path = _find_dotenv(start)
    if dotenv_path is None:
        return False

    try:
        from dotenv import dotenv_values  # type: ignore

        values = dotenv_values(dotenv_path)
    except Exception:
        # 退化解析：KEY=VALUE，跳过注释与空行
        values: dict[str, str] = {}
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip().strip('"').strip("'")

    loaded = False
    for k, v in values.items():
        if v and k not in os.environ:
            os.environ[k] = v
            loaded = True
    return loaded


def _patch_json_repair_dumps() -> None:
    """兼容 agentsociety2 对 ``json_repair.dumps`` 的调用（实现见 patches.py）。"""
    from .patches import patch_json_repair_dumps

    patch_json_repair_dumps()


def ensure_llm_config(quiet: bool = False) -> None:
    """校验 LLM 关键配置；缺失则打印清晰指引并以非零码退出。

    同时应用上游兼容性补丁（json_repair.dumps）。
    """
    _patch_json_repair_dumps()
    load_dotenv_if_present()
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        if not quiet:
            sys.stderr.write(
                "\n[配置缺失] 未设置以下必需环境变量：\n"
                + "\n".join(f"  - {v}" for v in missing)
                + "\n\n请复制 .env.example 为 .env 并填入你的 LLM API Key，"
                "或将变量导出到环境中。\n"
                "参考：AGENTSOCIETY_LLM_API_KEY / AGENTSOCIETY_LLM_API_BASE / "
                "AGENTSOCIETY_LLM_MODEL\n\n"
            )
        raise SystemExit(2)
