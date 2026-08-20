"""农业政策沙盒实验运行器（CLI 入口）。

运行方式（需先填 .env 中的 LLM 凭证）：
    python -m agri_sandbox.run_experiment --all
    python -m agri_sandbox.run_experiment --scenario grain_subsidy --repeats 3
    python -m agri_sandbox.run_experiment --scenario combined --agents 80 --baseline-steps 6 --policy-steps 10

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
from pathlib import Path

# 必须在导入 agentsociety2 之前加载 .env（agentsociety2.config 在导入时校验 API Key）
from .llm_config import ensure_llm_config

ensure_llm_config()

from .experiment import ExperimentSpec, run_all  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE.parent / "configs" / "policy_scenarios.json"


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    parser.add_argument("--agents", type=int, default=None,
                        help="农户数（覆盖 configs 默认）")
    parser.add_argument("--baseline-steps", type=int, default=None)
    parser.add_argument("--policy-steps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--economics", type=Path, default=None,
                        help="标定参数 JSON（默认 configs/economics.json）")
    parser.add_argument("--results-dir", type=Path, default=Path("results"),
                        help="结果根目录（默认 ./results，已被 .gitignore 忽略）")
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

    results_dir = args.results_dir
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
        for r in range(args.repeats if args.repeats is not None else repeats)
    ]
    for s in specs:
        if economics_path is not None:
            s.economics_path = economics_path

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
