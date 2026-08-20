"""农户智能体画像生成。

生成具有异质性的农户画像（profile），作为 FarmerAgent 的初始化输入。异质性维度包括：
- 区域（region）：华北平原 / 东北平原 / 长江中下游 / 西南丘陵
- 经营规模（farm_size_mu）：小农(<10) / 中农(10-50) / 规模户(>50)
- 风险态度（risk_attitude 0~1）：越高越厌恶风险、越倾向保险与保守作物
- 家庭资产（assets）：影响抗冲击能力
- 兼业程度（off_farm_income_annual）：工资性收入占比，影响务农 vs 务工权衡
- 年龄 / 受教育年限：影响信息获取与技术采纳

这些维度对应农林经济管理研究中农户行为的关键调节变量（见研究计划 §3 理论框架）。
"""

from __future__ import annotations

import random
from typing import Any

REGIONS = {
    "north_china": {"label": "华北平原", "water": 0.6, "logistics": 0.8},
    "northeast": {"label": "东北平原", "water": 0.85, "logistics": 0.7},
    "middle_yangtze": {"label": "长江中下游", "water": 0.95, "logistics": 0.85},
    "southwest": {"label": "西南丘陵", "water": 0.7, "logistics": 0.45},
}

# 区域→主导作物（用于初始种植结构与作物可得性）
REGION_CROPS = {
    "north_china": ["wheat", "corn", "soybean"],
    "northeast": ["corn", "soybean", "rice"],
    "middle_yangtze": ["rice", "vegetable", "wheat"],
    "southwest": ["vegetable", "corn", "soybean"],
}


def _weighted_region(rng: random.Random) -> str:
    # 小农为主，西南丘陵略多以贴合现实小农户分布
    weights = {
        "north_china": 0.30,
        "northeast": 0.20,
        "middle_yangtze": 0.27,
        "southwest": 0.23,
    }
    r = rng.random()
    cum = 0.0
    for k, w in weights.items():
        cum += w
        if r <= cum:
            return k
    return "north_china"


def make_farmer_profile(idx: int, rng: random.Random) -> dict[str, Any]:
    """生成单个农户画像。"""
    region = _weighted_region(rng)
    region_label = REGIONS[region]["label"]

    # 经营规模（亩），对数正态近似
    u = rng.lognormvariate(1.4, 0.9)
    farm_size = max(2.0, round(u, 1))
    if farm_size < 10:
        scale = "小农户"
    elif farm_size < 50:
        scale = "中农户"
    else:
        scale = "规模经营户"

    risk_attitude = round(min(1.0, max(0.0, rng.gauss(0.5, 0.22))), 2)
    assets = int(max(5_000, rng.lognormvariate(10.4, 0.6)))  # 万元级资产（元）
    off_farm = max(0, int(rng.gauss(18_000, 12_000)))  # 年工资性收入（元）
    age = int(min(72, max(24, rng.gauss(48, 11))))
    edu = int(min(16, max(0, rng.gauss(9, 3))))

    name = f"农户-{idx+1:03d}"
    gender = rng.choice(["男", "女"])

    persona = (
        f"你是一名{region_label}的{scale}，现年{age}岁，"
        f"受教育{edu}年，家庭经营耕地约{farm_size}亩。"
        f"你的风险厌恶程度{'较高' if risk_attitude>0.6 else '中等' if risk_attitude>0.35 else '较低'}。"
        f"你每年还有约{off_farm}元的务工/工资性收入。"
        f"你关心家庭年净收入最大化，同时希望尽量规避自然灾害与市场波动带来的损失。"
    )
    background_story = (
        f"你世代务农，近年粮价波动、农资成本上升，村里鼓励参加农业保险与土地流转。"
        f"你会在每个生产季开始时，根据市场行情、政府补贴与自家风险承受能力，"
        f"决定种什么、种多少、是否买保险、是否转入或转出土地。"
    )

    return {
        "name": name,
        "gender": gender,
        "age": age,
        "education": edu,
        "region": region,
        "region_label": region_label,
        "farm_size_mu": farm_size,
        "scale": scale,
        "risk_attitude": risk_attitude,
        "assets": assets,
        "off_farm_income_annual": off_farm,
        "available_crops": REGION_CROPS[region],
        "persona": persona,
        "background_story": background_story,
        "occupation": "农户",
        "marriage_status": "married",
    }


def make_farmer_profiles(n: int = 50, seed: int = 42) -> list[dict[str, Any]]:
    """生成 n 个农户画像（可复现：固定 seed）。"""
    rng = random.Random(seed)
    return [make_farmer_profile(i, rng) for i in range(n)]
