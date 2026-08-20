"""实验编排核心（与 CLI 入口解耦，可被脚本/测试直接复用）。

- :class:`ExperimentSpec`：一次运行的完整参数（情景/重复/规模/步数/种子/政策/标定）。
- :func:`build_world`：由 spec 构造「环境 + 农户智能体 + Router + AgentSociety」。
- :func:`run_one`：运行单个分阶段反事实实验，写回放与元信息。
- :func:`run_all`：按 (情景, 重复) 顺序批量运行。

依赖注意：本模块 import agentsociety2（平台依赖），因此必须先调用
``llm_config.ensure_llm_config()`` 加载 .env 后再导入；纯逻辑部分见 :mod:`economics`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsociety2.env import ReActRouter
from agentsociety2.society import AgentSociety

from . import patches

# 应用上游兼容补丁（Windows fsync / json_repair.dumps），须在 import 平台后调用
patches.apply_all()

from .agri_policy_env import AgriPolicyEnv  # noqa: E402
from .economics import EconomicsParams  # noqa: E402
from .farmer_agent import FarmerAgent  # noqa: E402
from .profiles import make_farmer_profiles  # noqa: E402


@dataclass
class ExperimentSpec:
    """一次 (情景, 重复) 实验的完整参数。"""

    scenario_key: str
    scenario_label: str
    policy: dict[str, Any]
    repeat: int = 0
    num_agents: int = 50
    seed: int = 42
    baseline_steps: int = 8
    policy_steps: int = 8
    tick_seconds: int = 7776000
    start_date: str = "2025-01-01"
    phased: bool = True
    results_dir: Path = Path("results")
    economics_path: Path | None = None  # 可选：覆盖标定参数（configs/economics.json）

    @property
    def run_dir(self) -> Path:
        return self.results_dir / self.scenario_key / f"repeat_{self.repeat}"

    def effective_seed(self) -> int:
        """重复次数叠加到基础种子上，保证不同重复间情景/冲击不同但可复现。"""
        return self.seed + self.repeat

    @classmethod
    def from_config(
        cls,
        scenario_key: str,
        cfg: dict[str, Any],
        results_dir: Path,
        phased: bool = True,
        repeat: int = 0,
        overrides: dict[str, Any] | None = None,
    ) -> "ExperimentSpec":
        """从 policy_scenarios.json 的规范结构构造 spec。

        :param cfg: 完整 config（含 defaults 与 scenarios）。
        :param overrides: 可选覆盖（num_agents / repeats / baseline_steps /
            policy_steps / seed / economics_path）。
        """
        d = dict(cfg["defaults"])
        if overrides:
            d.update({k: v for k, v in overrides.items() if v is not None})
        sc = cfg["scenarios"][scenario_key]
        return cls(
            scenario_key=scenario_key,
            scenario_label=sc["label"],
            policy=sc["policy"],
            repeat=repeat,
            num_agents=int(d["num_agents"]),
            seed=int(d["seed"]),
            baseline_steps=int(d["baseline_steps"]),
            policy_steps=int(d["policy_steps"]),
            tick_seconds=int(d["tick_seconds"]),
            start_date=str(d.get("start_date", "2025-01-01")),
            phased=phased,
            results_dir=results_dir,
            economics_path=(
                Path(d["economics_path"]) if d.get("economics_path") else None
            ),
        )


def build_world(
    spec: ExperimentSpec,
) -> tuple[AgriPolicyEnv, AgentSociety, Path]:
    """由 spec 构造完整实验世界，返回 (env, society, run_dir)。

    分阶段设计下，初始政策为空（阶段一基线）；否则政策从第一步生效。
    """
    n = spec.num_agents
    seed = spec.effective_seed()
    profiles = make_farmer_profiles(n=n, seed=seed)

    econ = (
        EconomicsParams.from_file(spec.economics_path)
        if spec.economics_path is not None
        else EconomicsParams()
    )
    init_policy = {} if spec.phased else spec.policy

    env = AgriPolicyEnv(
        profiles=profiles,
        policy=init_policy,
        seed=seed,
        economics_params=econ,
    )
    agents = [FarmerAgent(id=i, profile=p) for i, p in enumerate(profiles)]

    router = ReActRouter(env_modules=[env])

    run_dir = spec.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    society = AgentSociety(
        agents=agents,
        env_router=router,
        start_t=datetime.fromisoformat(spec.start_date),
        run_dir=run_dir,
    )
    return env, society, run_dir


async def run_one(spec: ExperimentSpec) -> dict[str, Any]:
    """运行单个分阶段反事实实验，返回元信息。"""
    env, society, run_dir = build_world(spec)
    print(
        f"[run] scenario={spec.scenario_key} repeat={spec.repeat} "
        f"agents={spec.num_agents} seed={spec.effective_seed()} -> {run_dir}"
    )

    async with society:
        await society.run(num_steps=spec.baseline_steps, tick=spec.tick_seconds)
        if spec.phased:
            msg = env.apply_policy(spec.policy)
            print(f"      -> 施加政策：{msg}")
        await society.run(num_steps=spec.policy_steps, tick=spec.tick_seconds)

    meta: dict[str, Any] = {
        "scenario_key": spec.scenario_key,
        "scenario_label": spec.scenario_label,
        "repeat": spec.repeat,
        "num_agents": spec.num_agents,
        "seed": spec.effective_seed(),
        "baseline_steps": spec.baseline_steps,
        "policy_steps": spec.policy_steps,
        "tick_seconds": spec.tick_seconds,
        "start_date": spec.start_date,
        "phased": spec.phased,
        "policy": spec.policy,
        "economics_path": str(spec.economics_path) if spec.economics_path else None,
        "run_dir": str(run_dir),
        "finished_at": datetime.now().isoformat(),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


async def run_all(specs: list[ExperimentSpec]) -> list[dict[str, Any]]:
    """顺序批量运行一组 spec。"""
    return [await run_one(s) for s in specs]
