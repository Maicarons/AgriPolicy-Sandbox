"""村庄农业经济环境（AgriPolicyEnv）。

继承自 AgentSociety² 的 EnvBase，为农户智能体提供：
- 市场与环境观测工具（observe_market）
- 生产决策工具（decide_planting / buy_insurance / transfer_land）
- 政策干预工具（set_subsidy / set_insurance_subsidy_rate / set_land_transfer_out_subsidy）
- 决策状态查询（report_status）
并在每个仿真步（生产季）核算农户收支、把逐帧状态写入回放 SQLite（供 analyze 读取）。

经济学模型为可解释、可审计的简化结构（详见研究计划 §5 与代码内注释），便于把
"政策冲击 → 农户行为 → 宏观涌现"的因果链条讲清楚，服务于反事实政策评估。
"""

from __future__ import annotations

import json
import random
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from agentsociety2.env import EnvBase, tool
from agentsociety2.storage import ColumnDef

# ---------------------------------------------------------------------------
# 作物目录与单位经济参数（示意值，可在 configs/policy_scenarios.json 之外另行标定）
# yield: 单产 kg/亩；price: 收购价 元/kg；cost: 物化成本 元/亩；
# premium: 纯保费 元/亩；insured_yield: 保险保产基准 kg/亩
# ---------------------------------------------------------------------------
CROPS: dict[str, dict[str, float]] = {
    "wheat": {"yield": 400, "price": 2.6, "cost": 500, "premium": 15, "insured_yield": 400},
    "corn": {"yield": 500, "price": 2.4, "cost": 450, "premium": 18, "insured_yield": 500},
    "rice": {"yield": 550, "price": 2.8, "cost": 700, "premium": 25, "insured_yield": 550},
    "soybean": {"yield": 180, "price": 5.0, "cost": 300, "premium": 12, "insured_yield": 180},
    "vegetable": {"yield": 2500, "price": 2.0, "cost": 1500, "premium": 40, "insured_yield": 2500},
}
GRAINS = {"wheat", "corn", "rice", "soybean"}

# 土地流转市场（元/亩/季）
RENT_IN_PER_MU = 500.0
RENT_OUT_PER_MU = 500.0

# 灾害阈值：天气冲击低于该值视为灾害年景，触发保险赔付
DISASTER_THRESHOLD = -0.15
INSURANCE_PAYOUT_RATIO = 0.7  # 赔付保产基准的 70%


class AgriPolicyEnv(EnvBase):
    """农业政策沙盒环境模块。"""

    # ---- 回放表声明（自动建表 + 注册 dataset）----
    _agent_state_columns: ClassVar[list] = [
        ColumnDef("crop_mix_json", "JSON", nullable=False,
                  description="该农户当前生产结构（作物->面积 亩）", logical_type="json"),
        ColumnDef("planted_area_mu", "REAL", nullable=False, unit="亩",
                  description="已种植面积合计", analysis_role="measure"),
        ColumnDef("insured_area_mu", "REAL", nullable=False, unit="亩",
                  description="投保面积合计", analysis_role="measure"),
        ColumnDef("transfer_in_mu", "REAL", nullable=False, unit="亩",
                  description="转入（租入）土地面积"),
        ColumnDef("transfer_out_mu", "REAL", nullable=False, unit="亩",
                  description="转出（租出）土地面积"),
        ColumnDef("gross_revenue", "REAL", nullable=False, unit="元",
                  description="农业毛收入", analysis_role="measure"),
        ColumnDef("subsidy_income", "REAL", nullable=False, unit="元",
                  description="获得的生产/价格/流转补贴合计", analysis_role="measure"),
        ColumnDef("insurance_payout", "REAL", nullable=False, unit="元",
                  description="保险赔付收入", analysis_role="measure"),
        ColumnDef("total_cost", "REAL", nullable=False, unit="元",
                  description="成本合计（物化+保费+租入）", analysis_role="measure"),
        ColumnDef("net_income", "REAL", nullable=False, unit="元",
                  description="本季家庭净收入（含兼业）", analysis_role="measure"),
    ]

    _env_state_columns: ClassVar[list] = [
        ColumnDef("avg_net_income", "REAL", nullable=False, unit="元",
                  description="全体农户平均净收入", analysis_role="measure"),
        ColumnDef("avg_subsidy_income", "REAL", nullable=False, unit="元",
                  description="平均补贴收入", analysis_role="measure"),
        ColumnDef("insurance_coverage_rate", "REAL", nullable=False,
                  description="投保面积 / 种植面积 的均值", analysis_role="measure"),
        ColumnDef("avg_planted_area", "REAL", nullable=False, unit="亩",
                  description="平均种植面积", analysis_role="measure"),
        ColumnDef("n_planting_farmers", "INTEGER", nullable=False,
                  description="有种植行为的农户数"),
        ColumnDef("total_subsidy", "REAL", nullable=False, unit="元",
                  description="全村补贴支出合计", analysis_role="measure"),
        ColumnDef("weather_shock", "REAL", nullable=False,
                  description="本季天气冲击系数（负为减产）", analysis_role="measure"),
    ]

    def __init__(
        self,
        profiles: list[dict[str, Any]],
        policy: dict[str, Any] | None = None,
        seed: int = 42,
    ):
        """初始化环境。

        :param profiles: 农户画像列表（顺序与智能体 id 对应）。
        :param policy: 初始政策字典（见 configs/policy_scenarios.json 的 policy 字段）。
        :param seed: 随机种子（天气/价格冲击可复现）。
        """
        super().__init__()
        self._rng = random.Random(seed)
        self._step_counter = 0

        # 政策状态（可由工具或 apply_policy 修改）
        self._policy = self._normalize_policy(policy or {})

        # 市场冲击（每步随机游走）
        self._price_shock = {c: 0.0 for c in CROPS}
        self._weather_shock = 0.0

        # 农户权威状态：name -> dict（含属性与动态决策/上一季结果）
        self._farmers: dict[str, dict[str, Any]] = {}
        for i, p in enumerate(profiles):
            name = p.get("name") or f"农户-{i+1:03d}"
            self._farmers[name] = {
                "id": i,
                "name": name,
                "farm_size_mu": float(p.get("farm_size_mu", 10.0)),
                "risk_attitude": float(p.get("risk_attitude", 0.5)),
                "off_farm_income_annual": float(p.get("off_farm_income_annual", 0.0)),
                "available_crops": list(p.get("available_crops", list(CROPS.keys()))),
                # 动态决策（跨季持续，可被智能体每季修订）
                "plan": {},        # crop -> area_mu
                "insured": {},     # crop -> area_mu
                "transfer_in": 0.0,
                "transfer_out": 0.0,
                # 上一季核算结果
                "last": {},
            }

    # ------------------------------------------------------------------
    # 策略/政策辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
        return {
            "subsidy_per_mu": dict(policy.get("subsidy_per_mu", {}) or {}),
            "insurance_subsidy_rate": float(policy.get("insurance_subsidy_rate", 0.0) or 0.0),
            "land_transfer_out_subsidy_per_mu": float(
                policy.get("land_transfer_out_subsidy_per_mu", 0.0) or 0.0
            ),
            "grain_price_support": float(policy.get("grain_price_support", 0.0) or 0.0),
        }

    def apply_policy(self, policy: dict[str, Any]) -> str:
        """确定性地施加政策（供 run_experiment 在基线阶段后调用，保证可复现）。"""
        self._policy = self._normalize_policy(policy)
        return (
            f"政策已生效：补贴={self._policy['subsidy_per_mu']}，"
            f"保险保费补贴率={self._policy['insurance_subsidy_rate']}，"
            f"转出补贴={self._policy['land_transfer_out_subsidy_per_mu']}元/亩，"
            f"粮价支持={self._policy['grain_price_support']}元/亩。"
        )

    # ------------------------------------------------------------------
    # 工具：观测
    # ------------------------------------------------------------------
    @tool(readonly=True)
    def observe_market(self, agent_name: str) -> str:
        """观测当前市场环境与政策（价格、补贴、保险、天气）。每季开始时调用。"""
        f = self._farmers.get(agent_name)
        if f is None:
            return f"未知农户：{agent_name}"
        lines = ["【当前市场环境与政策】"]
        lines.append(
            f"天气冲击系数：{self._weather_shock:+.2f}"
            f"（{'灾害年景' if self._weather_shock < DISASTER_THRESHOLD else '正常/偏好年景'}）"
        )
        lines.append("— 收购价（元/kg，含市场冲击）：")
        for c, spec in CROPS.items():
            if c in f["available_crops"]:
                eff = spec["price"] * (1.0 + self._price_shock.get(c, 0.0))
                lines.append(f"  {c}: {eff:.2f}（基准 {spec['price']}）")
        lines.append("— 生产性补贴（元/亩）：")
        sub = self._policy["subsidy_per_mu"]
        lines.append("  " + (", ".join(f"{c}={v}" for c, v in sub.items()) or "无"))
        lines.append(f"— 农业保险：政府承担保费比例 {self._policy['insurance_subsidy_rate']:.0%}")
        lines.append(
            f"— 土地流转：转出补贴 {self._policy['land_transfer_out_subsidy_per_mu']:.0f} 元/亩"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 工具：生产决策
    # ------------------------------------------------------------------
    @tool(readonly=False)
    def decide_planting(self, agent_name: str, crop: str, area_mu: float) -> str:
        """决定某种植作物的面积（亩）。可多次调用以设定全部作物的生产结构；设 0 表示不种。"""
        f = self._farmers.get(agent_name)
        if f is None:
            return f"未知农户：{agent_name}"
        crop = (crop or "").strip().lower()
        if crop not in CROPS:
            return f"不支持的作物：{crop}（可选：{', '.join(CROPS)}）"
        if crop not in f["available_crops"]:
            return f"你所在区域不可种植 {crop}（可选：{', '.join(f['available_crops'])}）"
        area_mu = max(0.0, float(area_mu))
        if area_mu <= 0:
            f["plan"].pop(crop, None)
        else:
            f["plan"][crop] = area_mu
        return f"已更新生产结构：{f['plan']}"

    @tool(readonly=False)
    def buy_insurance(self, agent_name: str, crop: str, area_mu: float) -> str:
        """为某作物投保指定面积（亩）。设 0 表示退保该作物。"""
        f = self._farmers.get(agent_name)
        if f is None:
            return f"未知农户：{agent_name}"
        crop = (crop or "").strip().lower()
        if crop not in CROPS:
            return f"不支持的作物：{crop}"
        area_mu = max(0.0, float(area_mu))
        if area_mu <= 0:
            f["insured"].pop(crop, None)
        else:
            f["insured"][crop] = area_mu
        return f"已更新保险：{f['insured']}"

    @tool(readonly=False)
    def transfer_land(self, agent_name: str, direction: str, area_mu: float) -> str:
        """土地流转：direction='in' 租入（扩大经营），direction='out' 转出（退出承包）。"""
        f = self._farmers.get(agent_name)
        if f is None:
            return f"未知农户：{agent_name}"
        direction = (direction or "").strip().lower()
        area_mu = max(0.0, float(area_mu))
        if direction == "in":
            f["transfer_in"] = area_mu
            f["transfer_out"] = 0.0
        elif direction == "out":
            f["transfer_out"] = area_mu
            f["transfer_in"] = 0.0
        else:
            return "direction 必须是 'in' 或 'out'"
        return f"已更新土地流转：转入 {f['transfer_in']} 亩 / 转出 {f['transfer_out']} 亩"

    @tool(readonly=True)
    def report_status(self, agent_name: str) -> str:
        """查询本农户上一季的核算结果与当前决策，便于复盘。"""
        f = self._farmers.get(agent_name)
        if f is None:
            return f"未知农户：{agent_name}"
        last = f.get("last") or {}
        return json.dumps(
            {
                "plan": f["plan"],
                "insured": f["insured"],
                "transfer_in": f["transfer_in"],
                "transfer_out": f["transfer_out"],
                "last_net_income": last.get("net_income"),
                "last_subsidy": last.get("subsidy_income"),
                "last_insurance_payout": last.get("insurance_payout"),
            },
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # 工具：政策干预（可由 society.intervene 以自然语言触发，也可直接编程调用）
    # ------------------------------------------------------------------
    @tool(readonly=False)
    def set_subsidy(self, crop: str, amount_per_mu: float) -> str:
        """设定某作物生产性补贴（元/亩）。amount_per_mu=0 表示取消。"""
        crop = (crop or "").strip().lower()
        if crop not in CROPS:
            return f"不支持的作物：{crop}"
        amount = max(0.0, float(amount_per_mu))
        if amount <= 0:
            self._policy["subsidy_per_mu"].pop(crop, None)
        else:
            self._policy["subsidy_per_mu"][crop] = amount
        return f"补贴已更新：{self._policy['subsidy_per_mu']}"

    @tool(readonly=False)
    def set_insurance_subsidy_rate(self, rate: float) -> str:
        """设定政府承担的农业保险保费比例（0~1）。"""
        rate = min(1.0, max(0.0, float(rate)))
        self._policy["insurance_subsidy_rate"] = rate
        return f"保险保费补贴率已设为 {rate:.0%}"

    @tool(readonly=False)
    def set_land_transfer_out_subsidy(self, amount_per_mu: float) -> str:
        """设定土地转出（退出承包）补贴（元/亩）。"""
        self._policy["land_transfer_out_subsidy_per_mu"] = max(0.0, float(amount_per_mu))
        return f"土地转出补贴已设为 {self._policy['land_transfer_out_subsidy_per_mu']:.0f} 元/亩"

    # ------------------------------------------------------------------
    # 仿真步：核算 + 回放
    # ------------------------------------------------------------------
    async def step(self, tick: int, t: datetime):
        """推进一个生产季：更新市场冲击、核算每户收支、写入回放。"""
        self._step_counter += 1

        # 1) 更新市场/天气冲击
        for c in CROPS:
            self._price_shock[c] = max(
                -0.4, min(0.4, self._price_shock[c] + self._rng.gauss(0, 0.05))
            )
        self._weather_shock = max(-0.5, min(0.3, self._rng.gauss(-0.02, 0.18)))

        # 2) 逐户核算
        net_incomes: list[float] = []
        subsidy_incomes: list[float] = []
        coverage_rates: list[float] = []
        planted_areas: list[float] = []
        n_planting = 0
        total_subsidy = 0.0

        for f in self._farmers.values():
            gross = 0.0
            cost = 0.0
            subsidy = 0.0
            insurance_payout = 0.0
            planted_area = sum(f["plan"].values())
            insured_area = sum(f["insured"].values())

            for crop, area in f["plan"].items():
                spec = CROPS[crop]
                eff_price = spec["price"] * (1.0 + self._price_shock.get(crop, 0.0))
                yield_ = spec["yield"] * (1.0 + self._weather_shock)
                gross += yield_ * area * eff_price
                cost += spec["cost"] * area

                sub = self._policy["subsidy_per_mu"].get(crop, 0.0)
                subsidy += area * sub
                if crop in GRAINS:
                    subsidy += area * self._policy["grain_price_support"]

                ins_area = f["insured"].get(crop, 0.0)
                premium = spec["premium"] * ins_area * (1.0 - self._policy["insurance_subsidy_rate"])
                cost += premium
                if self._weather_shock < DISASTER_THRESHOLD and ins_area > 0:
                    insurance_payout += (
                        ins_area * spec["insured_yield"] * eff_price * INSURANCE_PAYOUT_RATIO
                    )

            rent_income = (
                f["transfer_out"] * RENT_OUT_PER_MU
                + f["transfer_out"] * self._policy["land_transfer_out_subsidy_per_mu"]
            )
            cost += f["transfer_in"] * RENT_IN_PER_MU
            off_farm_quarter = f["off_farm_income_annual"] / 4.0

            net = gross + subsidy + insurance_payout + rent_income + off_farm_quarter - cost

            f["last"] = {
                "gross_revenue": gross,
                "subsidy_income": subsidy,
                "insurance_payout": insurance_payout,
                "total_cost": cost,
                "net_income": net,
                "planted_area_mu": planted_area,
                "insured_area_mu": insured_area,
            }

            net_incomes.append(net)
            subsidy_incomes.append(subsidy)
            planted_areas.append(planted_area)
            if planted_area > 0:
                n_planting += 1
                coverage_rates.append(min(1.0, insured_area / planted_area) if planted_area else 0.0)
            total_subsidy += subsidy

            # 3) 逐户回放行
            await self._write_agent_state(
                agent_id=f["id"],
                step=self._step_counter,
                t=t,
                crop_mix_json=json.dumps(f["plan"], ensure_ascii=False),
                planted_area_mu=planted_area,
                insured_area_mu=insured_area,
                transfer_in_mu=f["transfer_in"],
                transfer_out_mu=f["transfer_out"],
                gross_revenue=gross,
                subsidy_income=subsidy,
                insurance_payout=insurance_payout,
                total_cost=cost,
                net_income=net,
            )

        # 4) 环境级回放行
        await self._write_env_state(
            step=self._step_counter,
            t=t,
            avg_net_income=statistics.fmean(net_incomes) if net_incomes else 0.0,
            avg_subsidy_income=statistics.fmean(subsidy_incomes) if subsidy_incomes else 0.0,
            insurance_coverage_rate=statistics.fmean(coverage_rates) if coverage_rates else 0.0,
            avg_planted_area=statistics.fmean(planted_areas) if planted_areas else 0.0,
            n_planting_farmers=n_planting,
            total_subsidy=total_subsidy,
            weather_shock=self._weather_shock,
        )

        self.t = t

    # ------------------------------------------------------------------
    # 技能发现（让农户智能体自动激活决策技能）
    # ------------------------------------------------------------------
    @classmethod
    def get_agent_skills_dirs(cls) -> list[Path]:
        return [Path(__file__).parent / "agent_skills"]

    def get_default_skill(self) -> str | None:
        return "agri-decision"
