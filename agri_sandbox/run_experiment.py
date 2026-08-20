"""实验编排：农业政策沙盒的反事实模拟运行。

运行方式（需先填 .env 中的 LLM 凭证）：
    python -m agri_sandbox.run_experiment --all
    python -m agri_sandbox.run_experiment --scenario grain_subsidy --repeats 3
    python -m agri_sandbox.run_experiment --scenario combined --agents 80 --baseline-steps 6 --policy-steps 10

默认采用"分阶段反事实"设计：
  阶段一（baseline_steps）：空政策（或基准情景政策）运行；
  阶段二（policy_steps）：施加所选情景政策后继续运行。
同一批农户在前后两阶段的表现差异，即为该政策的因果式处理效应估计。

每个 (情景, 重复) 组合写入独立 run_dir，回放数据落入 run_dir/sqlite.db，供 analyze 读取。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 必须在导入 agentsociety2 之前加载 .env（agentsociety2.config 在导入时校验 API Key）
from .llm_config import ensure_llm_config

ensure_llm_config()

from agentsociety2.env import ReActRouter  # noqa: E402
from agentsociety2.society import AgentSociety  # noqa: E402
from .profiles import make_farmer_profiles  # noqa: E402
from .farmer_agent import FarmerAgent  # noqa: E402
from .agri_policy_env import AgriPolicyEnv  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE.parent / "configs" / "policy_scenarios.json"


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_one(
    scenario_key: str,
    repeat: int,
    cfg: dict,
    scenarios: dict,
    base_dir: Path,
    phased: bool,
) -> dict:
    """运行单个 (情景, 重复) 实验，返回元信息。"""
    d = cfg["defaults"]
    n = int(d["num_agents"])
    seed = int(d["seed"]) + repeat
    baseline_steps = int(d["baseline_steps"])
    policy_steps = int(d["policy_steps"])
    tick = int(d["tick_seconds"])
    start_t = datetime.fromisoformat(d["start_date"])

    scenario = scenarios[scenario_key]
    scenario_policy = scenario["policy"]

    # 分阶段：阶段一空政策；阶段二施加情景政策
    init_policy = {} if phased else scenario_policy
    profiles = make_farmer_profiles(n=n, seed=seed)
    env = AgriPolicyEnv(profiles=profiles, policy=init_policy, seed=seed)
    agents = [FarmerAgent(id=i, profile=p) for i, p in enumerate(profiles)]
    router = ReActRouter(env_modules=[env])

    run_dir = base_dir / scenario_key / f"repeat_{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)

    society = AgentSociety(
        agents=agents,
        env_router=router,
        start_t=start_t,
        run_dir=run_dir,
    )

    print(f"[run] scenario={scenario_key} repeat={repeat} agents={n} -> {run_dir}")
    async with society:
        await society.run(num_steps=baseline_steps, tick=tick)
        if phased:
            msg = env.apply_policy(scenario_policy)
            print(f"      -> 施加政策：{msg}")
        await society.run(num_steps=policy_steps, tick=tick)

    meta = {
        "scenario_key": scenario_key,
        "scenario_label": scenario["label"],
        "repeat": repeat,
        "num_agents": n,
        "seed": seed,
        "baseline_steps": baseline_steps,
        "policy_steps": policy_steps,
        "tick_seconds": tick,
        "phased": phased,
        "policy": scenario_policy,
        "run_dir": str(run_dir),
        "finished_at": datetime.now().isoformat(),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


async def run_all(
    scenario_keys: list[str],
    repeats: int,
    cfg: dict,
    scenarios: dict,
    results_dir: Path,
    phased: bool,
) -> list[dict]:
    metas: list[dict] = []
    for sk in scenario_keys:
        for r in range(repeats):
            metas.append(
                await run_one(sk, r, cfg, scenarios, results_dir, phased)
            )
    return metas


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
    parser.add_argument("--results-dir", type=Path, default=Path("results"),
                        help="结果根目录（默认 ./results，已被 .gitignore 忽略）")
    parser.add_argument("--no-phased", action="store_true",
                        help="不使用分阶段反事实，政策从第一步即生效")
    args = parser.parse_args()

    cfg = _load_config(args.config)
    scenarios = cfg["scenarios"]
    d = cfg["defaults"]

    if args.agents is not None:
        d["num_agents"] = args.agents
    if args.repeats is not None:
        d["repeats"] = args.repeats
    if args.baseline_steps is not None:
        d["baseline_steps"] = args.baseline_steps
    if args.policy_steps is not None:
        d["policy_steps"] = args.policy_steps
    if args.seed is not None:
        d["seed"] = args.seed

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

    print(f"== 农业政策沙盒实验 == 情景={keys} 重复={d['repeats']} 农户={d['num_agents']} "
          f"分阶段={phased} 结果目录={results_dir}")

    metas = asyncio.run(
        run_all(keys, int(d["repeats"]), cfg, scenarios, results_dir, phased)
    )

    summary_path = results_dir / "runs_index.json"
    summary_path.write_text(
        json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"== 完成 {len(metas)} 个实验；索引写入 {summary_path}")


if __name__ == "__main__":
    main()
