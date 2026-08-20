"""农业经济学核算模型（纯逻辑，零平台依赖，可独立单元测试）。

设计目标：把"标定参数"与"逐户收支核算"从 AgentSociety² 环境模块中剥离，
实现三方面的解耦：

1. **参数与逻辑解耦**：作物目录、价格、成本、保费、租金、灾害阈值等标定参数
   集中在本模块，可通过 :func:`EconomicsParams.from_file` 从
   ``configs/economics.json`` 覆盖，不改代码即可标定。
2. **平台依赖解耦**：本模块不 import 任何 agentsociety2 组件，纯标准库，
   可在无平台环境下直接测试与审计核算公式。
3. **模型可审计**：核算公式全部为纯函数（给定决策与冲击 → 输出收支），
   便于答辩时逐项讲解"政策冲击 → 农户行为 → 宏观涌现"的因果链条。

经济学口径（简化但可解释，示意值）：
- 毛收入 = Σ 单产×(1+天气冲击) × 面积 × 收购价×(1+价格冲击)
- 成本   = Σ 物化成本×面积 + Σ 保费×投保面积×(1-保费补贴率) + 租入面积×地租
- 补贴   = Σ 面积×生产性补贴 + 粮作面积×粮价支持 + 转出面积×(地租+转出补贴)
- 赔付   = 灾害年景下 Σ 投保面积×保产基准×价格×赔付比例
- 净收入 = 毛收入 + 补贴 + 赔付 + 租金收入 + 兼业收入(季) − 成本
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 默认标定参数（示意值；正式实验应基于统计年鉴/固定观察点数据重新标定）
# yield: 单产 kg/亩；price: 收购价 元/kg；cost: 物化成本 元/亩；
# premium: 纯保费 元/亩；insured_yield: 保险保产基准 kg/亩
# ---------------------------------------------------------------------------
DEFAULT_CROPS: dict[str, dict[str, float]] = {
    "wheat": {"yield": 400, "price": 2.6, "cost": 500, "premium": 15, "insured_yield": 400},
    "corn": {"yield": 500, "price": 2.4, "cost": 450, "premium": 18, "insured_yield": 500},
    "rice": {"yield": 550, "price": 2.8, "cost": 700, "premium": 25, "insured_yield": 550},
    "soybean": {"yield": 180, "price": 5.0, "cost": 300, "premium": 12, "insured_yield": 180},
    "vegetable": {"yield": 2500, "price": 2.0, "cost": 1500, "premium": 40, "insured_yield": 2500},
}

# 主粮作物集合（享受粮价支持政策）
GRAINS: set[str] = {"wheat", "corn", "rice", "soybean"}

# 土地流转市场（元/亩/季）
RENT_IN_PER_MU = 500.0
RENT_OUT_PER_MU = 500.0

# 灾害与保险
DISASTER_THRESHOLD = -0.15   # 天气冲击低于该值视为灾害年景，触发赔付
INSURANCE_PAYOUT_RATIO = 0.7  # 赔付 = 保产基准 × 价格 × 该比例

# 市场/天气冲击随机游走参数
PRICE_SHOCK_BOUNDS = (-0.4, 0.4)
PRICE_SHOCK_SIGMA = 0.05
WEATHER_SHOCK_BOUNDS = (-0.5, 0.3)
WEATHER_SHOCK_MU = -0.02
WEATHER_SHOCK_SIGMA = 0.18


@dataclass
class EconomicsParams:
    """标定参数集合（支持从 JSON 文件加载覆盖）。"""

    crops: dict[str, dict[str, float]] = field(default_factory=lambda: dict(DEFAULT_CROPS))
    rent_in_per_mu: float = RENT_IN_PER_MU
    rent_out_per_mu: float = RENT_OUT_PER_MU
    disaster_threshold: float = DISASTER_THRESHOLD
    insurance_payout_ratio: float = INSURANCE_PAYOUT_RATIO
    price_shock_bounds: tuple[float, float] = PRICE_SHOCK_BOUNDS
    price_shock_sigma: float = PRICE_SHOCK_SIGMA
    weather_shock_bounds: tuple[float, float] = WEATHER_SHOCK_BOUNDS
    weather_shock_mu: float = WEATHER_SHOCK_MU
    weather_shock_sigma: float = WEATHER_SHOCK_SIGMA

    # ---- 便捷只读属性（供环境/分析使用）----
    @property
    def grains(self) -> set[str]:
        return GRAINS

    @classmethod
    def from_file(cls, path: str | Path) -> "EconomicsParams":
        """从 JSON 文件加载，缺省字段回落到默认值。"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        crops = data.get("crops", DEFAULT_CROPS)
        return cls(
            crops={k: dict(v) for k, v in crops.items()},
            rent_in_per_mu=float(data.get("rent_in_per_mu", RENT_IN_PER_MU)),
            rent_out_per_mu=float(data.get("rent_out_per_mu", RENT_OUT_PER_MU)),
            disaster_threshold=float(data.get("disaster_threshold", DISASTER_THRESHOLD)),
            insurance_payout_ratio=float(
                data.get("insurance_payout_ratio", INSURANCE_PAYOUT_RATIO)
            ),
            price_shock_bounds=tuple(data.get("price_shock_bounds", PRICE_SHOCK_BOUNDS)),
            price_shock_sigma=float(data.get("price_shock_sigma", PRICE_SHOCK_SIGMA)),
            weather_shock_bounds=tuple(data.get("weather_shock_bounds", WEATHER_SHOCK_BOUNDS)),
            weather_shock_mu=float(data.get("weather_shock_mu", WEATHER_SHOCK_MU)),
            weather_shock_sigma=float(data.get("weather_shock_sigma", WEATHER_SHOCK_SIGMA)),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "crops": self.crops,
            "rent_in_per_mu": self.rent_in_per_mu,
            "rent_out_per_mu": self.rent_out_per_mu,
            "disaster_threshold": self.disaster_threshold,
            "insurance_payout_ratio": self.insurance_payout_ratio,
            "price_shock_bounds": list(self.price_shock_bounds),
            "price_shock_sigma": self.price_shock_sigma,
            "weather_shock_bounds": list(self.weather_shock_bounds),
            "weather_shock_mu": self.weather_shock_mu,
            "weather_shock_sigma": self.weather_shock_sigma,
        }
        return out


@dataclass
class FarmerAccounting:
    """单户单季核算结果。"""

    gross_revenue: float = 0.0
    total_cost: float = 0.0
    subsidy_income: float = 0.0
    insurance_payout: float = 0.0
    rent_income: float = 0.0
    off_farm_income: float = 0.0
    net_income: float = 0.0
    planted_area_mu: float = 0.0
    insured_area_mu: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "gross_revenue": self.gross_revenue,
            "total_cost": self.total_cost,
            "subsidy_income": self.subsidy_income,
            "insurance_payout": self.insurance_payout,
            "rent_income": self.rent_income,
            "off_farm_income": self.off_farm_income,
            "net_income": self.net_income,
            "planted_area_mu": self.planted_area_mu,
            "insured_area_mu": self.insured_area_mu,
        }


def compute_farmer_accounting(
    plan: dict[str, float],
    insured: dict[str, float],
    transfer_in_mu: float,
    transfer_out_mu: float,
    policy: dict[str, Any],
    price_shock: dict[str, float] | None = None,
    weather_shock: float = 0.0,
    off_farm_income_annual: float = 0.0,
    params: EconomicsParams | None = None,
) -> FarmerAccounting:
    """逐户收支核算（纯函数）。

    :param plan: 生产结构 {作物: 面积(亩)}。
    :param insured: 投保结构 {作物: 投保面积(亩)}。
    :param transfer_in_mu: 租入面积。
    :param transfer_out_mu: 转出面积。
    :param policy: 政策参数字典（键见 ``AgriPolicyEnv._normalize_policy`` 输出的规范结构）。
    :param price_shock: 各作物价格冲击系数 {作物: 浮点}。
    :param weather_shock: 天气冲击系数（负为减产）。
    :param off_farm_income_annual: 家庭年兼业收入（按季折算 1/4）。
    :param params: 标定参数；默认使用模块级默认值。
    """
    p = params or EconomicsParams()
    crops = p.crops
    price_shock = price_shock or {}

    gross = 0.0
    cost = 0.0
    subsidy = 0.0
    insurance_payout = 0.0
    planted_area = sum(plan.values())
    insured_area = sum(insured.values())

    for crop, area in plan.items():
        spec = crops[crop]
        eff_price = spec["price"] * (1.0 + price_shock.get(crop, 0.0))
        yield_ = spec["yield"] * (1.0 + weather_shock)
        gross += yield_ * area * eff_price
        cost += spec["cost"] * area

        sub = policy.get("subsidy_per_mu", {}).get(crop, 0.0)
        subsidy += area * sub
        if crop in GRAINS:
            subsidy += area * policy.get("grain_price_support", 0.0)

        ins_area = insured.get(crop, 0.0)
        premium = (
            spec["premium"] * ins_area * (1.0 - policy.get("insurance_subsidy_rate", 0.0))
        )
        cost += premium
        if weather_shock < p.disaster_threshold and ins_area > 0:
            insurance_payout += (
                ins_area * spec["insured_yield"] * eff_price * p.insurance_payout_ratio
            )

    rent_income = transfer_out_mu * p.rent_out_per_mu + transfer_out_mu * policy.get(
        "land_transfer_out_subsidy_per_mu", 0.0
    )
    cost += transfer_in_mu * p.rent_in_per_mu
    off_farm_quarter = off_farm_income_annual / 4.0

    net = gross + subsidy + insurance_payout + rent_income + off_farm_quarter - cost

    return FarmerAccounting(
        gross_revenue=gross,
        total_cost=cost,
        subsidy_income=subsidy,
        insurance_payout=insurance_payout,
        rent_income=rent_income,
        off_farm_income=off_farm_quarter,
        net_income=net,
        planted_area_mu=planted_area,
        insured_area_mu=insured_area,
    )


def village_summary(accounts: list[FarmerAccounting], total_subsidy: float, weather_shock: float) -> dict[str, float]:
    """村级汇总统计（供环境级回放与分析使用）。"""
    n = len(accounts)
    coverage = [
        min(1.0, a.insured_area_mu / a.planted_area_mu)
        for a in accounts
        if a.planted_area_mu > 0
    ]
    return {
        "avg_net_income": statistics.fmean(a.net_income for a in accounts) if n else 0.0,
        "avg_subsidy_income": (
            statistics.fmean(a.subsidy_income for a in accounts) if n else 0.0
        ),
        # 首季农户尚未决策时 planted=0，coverage 为空列表，需回退 0.0
        "insurance_coverage_rate": statistics.fmean(coverage) if coverage else 0.0,
        "avg_planted_area": (
            statistics.fmean(a.planted_area_mu for a in accounts) if n else 0.0
        ),
        "n_planting_farmers": sum(1 for a in accounts if a.planted_area_mu > 0),
        "total_subsidy": total_subsidy,
        "weather_shock": weather_shock,
    }
