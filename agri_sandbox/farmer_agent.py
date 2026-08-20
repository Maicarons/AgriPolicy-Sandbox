"""农户智能体定义。

FarmerAgent 继承自 AgentSociety² 的 PersonAgent（skills-first 工具代理）。
农户在每个仿真步内通过环境工具（observe_market / decide_planting / buy_insurance /
transfer_land）完成"观测-推理-行动"，其决策由 LLM 依据画像、风险态度与政策环境驱动。

环境（AgriPolicyEnv）持有农户的权威状态与属性；本类仅负责：
- 把农户画像注入身份（persona / background_story）；
- 在 agent 工作区写入 farm_profile.json 与 decision_log.jsonl 作为可读的起始状态与决策记录，
  便于 LLM 在工具循环中参考与追溯。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from agentsociety2 import PersonAgent


class FarmerAgent(PersonAgent):
    """农林经济管理场景下的农户智能体。

    :param id: 智能体唯一标识。
    :param profile: 农户画像字典（见 :mod:`agri_sandbox.profiles`）。
    :param name: 显示名；缺省时使用 profile["name"]。
    :param capability_kwargs: 透传给 PersonAgent 的能力参数（如 max_tool_rounds）。
    """

    def __init__(
        self,
        id: int,
        profile: dict[str, Any],
        name: Optional[str] = None,
        **capability_kwargs: Any,
    ):
        # 在 agent 工作区预置可读的农场画像与决策日志，便于 LLM 推理时参考
        farm_seed = {
            "farm_profile.json": json.dumps(
                {
                    "name": profile.get("name"),
                    "region_label": profile.get("region_label"),
                    "farm_size_mu": profile.get("farm_size_mu"),
                    "scale": profile.get("scale"),
                    "risk_attitude": profile.get("risk_attitude"),
                    "assets": profile.get("assets"),
                    "off_farm_income_annual": profile.get("off_farm_income_annual"),
                    "available_crops": profile.get("available_crops", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "decision_log.jsonl": "",
        }
        init_state = {"workspace_seed": farm_seed}
        super().__init__(
            id=id,
            profile=profile,
            name=name or profile.get("name"),
            init_state=init_state,
            max_tool_rounds=capability_kwargs.pop("max_tool_rounds", 12),
            **capability_kwargs,
        )
