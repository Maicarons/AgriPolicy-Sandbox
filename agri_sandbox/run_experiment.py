"""农业政策沙盒实验运行器（CLI 入口）。

运行方式（需先填 .env 中的 LLM 凭证）：
    python -m agri_sandbox.run_experiment --all
    python -m agri_sandbox.run_experiment --scenario grain_subsidy --repeats 3
    python -m agri_sandbox.run_experiment --scenario combined --agents 80 --baseline-steps 6 --policy-steps 10
    python -m agri_sandbox.run_experiment --scenario baseline --repeat 2   # 单点调度（并行/断点续跑）
    ./run_full_experiment.sh full                                          # 完整实验流程（见脚本）

默认采用"分阶段反事实"设计（见 :mod:`agri_sandbox.experiment`）：
  阶段一（baseline_steps）：空政策运行；
  阶段二（policy_steps）：施加所选情景政策后继续运行。
同一批农户在前后两阶段的表现差异，即为该政策的因果式处理效应估计。

编排逻辑在 experiment.py；本文件只负责命令行解析与参数装配（薄层）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# 必须在导入 agentsociety2 之前加载 .env（agentsociety2.config 在导入时校验 API Key）
from .llm_config import ensure_llm_config

ensure_llm_config()

from .experiment import ExperimentSpec, run_all  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE.parent / "configs" / "policy_scenarios.json"

# 卡死判定阈值：run_progress.json 超过该秒数未更新且状态为 running，视为中断残留
STALE_SECONDS = 300


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _default_results_dir() -> Path:
    """未指定 --results-dir 时，默认使用 results/<YYYY-MM-DD> 日期目录。"""
    return Path("results") / date.today().isoformat()


def _cleanup_stale_run(run_dir: Path) -> None:
    """清理上次中断残留（running 且超过 5 分钟未更新），避免续跑混入脏数据。

    仅删除回放库与完成标记；run.log 保留以便追溯。
    """
    prog_f = run_dir / "run_progress.json"
    if not prog_f.exists():
        return
    try:
        prog = json.loads(prog_f.read_text(encoding="utf-8"))
    except Exception:
        return
    if prog.get("status") != "running":
        return
    updated = prog.get("updated_at")
    if not updated:
        return
    try:
        from datetime import datetime
        age = (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
    except Exception:
        age = STALE_SECONDS + 1  # 无法解析时间戳，按陈旧处理
    if age <= STALE_SECONDS:
        return  # 可能正在运行，不动
    for f in ("sqlite.db", "run_meta.json"):
        p = run_dir / f
        if p.exists():
            p.unlink()
    print(f"  [清理] {run_dir}: 上次运行中断残留已清理（进度停留在 {updated}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="农业政策沙盒实验运行器")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="policy_scenarios.json 路径")
    parser.add_argument("--scenario", type=str, default=None,
                        help="单个情景键（见 configs）")
    parser.add_argument("--all", action="store_true",
                        help="运行 configs 中全部情景")
    parser.add_argument("--repeats", type=int, default=None,
                        help="重复次数（覆盖 configs 默认）")
    parser.add_argument("--repeat", type=int, default=None,
                        help="仅运行指定重复编号（须与 --scenario 联用；用于并行调度断点续跑）")
    parser.add_argument("--agents", type=int, default=None,
                        help="农户数（覆盖 configs 默认）")
    parser.add_argument("--baseline-steps", type=int, default=None)
    parser.add_argument("--policy-steps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--economics", type=Path, default=None,
                        help="标定参数 JSON（默认 configs/economics.json）")
    parser.add_argument("--results-dir", type=Path, default=None,
                        help="结果根目录（默认 results/<YYYY-MM-DD> 日期目录，已被 .gitignore 忽略）")
    parser.add_argument("--no-phased", action="store_true",
                        help="不使用分阶段反事实，政策从第一步即生效")
    args = parser.parse_args()

    cfg = _load_config(args.config)
    scenarios = cfg["scenarios"]
    d = cfg["defaults"]

    if args.all:
        keys = list(scenarios.keys())
    elif args.scenario:
        if args.scenario not in scenarios:
            sys.stderr.write(f"未知情景：{args.scenario}（可选：{', '.join(scenarios)}）\n")
            raise SystemExit(2)
        keys = [args.scenario]
    else:
        # 默认仅跑 baseline 做连通性自检
        keys = ["baseline"]

    results_dir = args.results_dir or _default_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    phased = not args.no_phased
    repeats = int(d["repeats"])

    overrides = {
        "num_agents": args.agents,
        "repeats": args.repeats,
        "baseline_steps": args.baseline_steps,
        "policy_steps": args.policy_steps,
        "seed": args.seed,
    }
    economics_path = args.economics

    if args.repeat is not None:
        # 单点调度：仅运行指定的 (情景, 重复编号)，供并行/续跑脚本使用
        if not args.scenario:
            sys.stderr.write("--repeat 必须与 --scenario 一起使用\n")
            raise SystemExit(2)
        keys = [args.scenario]
        reps = [args.repeat]
    else:
        reps = range(args.repeats if args.repeats is not None else repeats)

    specs = [
        ExperimentSpec.from_config(
            sk,
            cfg,
            results_dir=results_dir,
            phased=phased,
            repeat=r,
            overrides=overrides,
        )
        for sk in keys
        for r in reps
    ]
    for s in specs:
        if economics_path is not None:
            s.economics_path = economics_path
        # 续跑保护：清理上次中断残留（正在运行的不动）
        _cleanup_stale_run(s.run_dir)

    print(
        f"== 农业政策沙盒实验 == 情景={keys} 重复={len(specs) // max(1, len(keys))} "
        f"农户={specs[0].num_agents if specs else '?'} 分阶段={phased} 结果目录={results_dir}"
    )

    metas = asyncio.run(run_all(specs))

    summary_path = results_dir / "runs_index.json"
    summary_path.write_text(
        json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"== 完成 {len(metas)} 个实验；索引写入 {summary_path}")


if __name__ == "__main__":
    main()
