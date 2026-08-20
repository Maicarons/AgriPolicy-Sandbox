"""农户智能体（FarmerAgent v2）。

采用 AgentSociety² 官方"行为实验"模式（参考 contrib/public_goods_agent.py）：

- 继承 :class:`agentsociety2.agent.base.AgentBase`，手写 :meth:`step`；
- 每步流程：观察环境（ask_env readonly）→ LLM 决策（种植结构/投保/土地流转）→
  通过 ask_env 以模板模式提交决策到环境工具；
- 不启用 PersonAgent 的通用认知循环（needs/emotion/intention），避免智能体
  在工具探索上浪费时间，LLM 调用次数少、行为可控、便于复现。

决策输出为 JSON：``{"plan": {crop: 亩}, "insured": {crop: 亩}, "transfer_in": 亩, "transfer_out": 亩}``。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from agentsociety2.agent.base import AgentBase


class FarmerAgent(AgentBase):
    """农业政策沙盒中的农户智能体。"""

    def __init__(self, id: int, profile: dict[str, Any], name: str | None = None):
        super().__init__(id=id, profile=profile, name=name)
        self._profile = profile
        self.decision_history: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    async def ask(self, message: str, readonly: bool = True) -> str:
        """回答外部问题（简单 LLM 问答）。"""
        profile_str = json.dumps(self._profile, ensure_ascii=False, indent=2)
        prompt = (
            f"你是{self._name}，一位农户。你的情况：\n{profile_str}\n\n"
            f"问题：{message}\n\n请结合你的情况简短回答。"
        )
        try:
            resp = await self.acompletion([{"role": "user", "content": prompt}], stream=False)
            if resp and resp.choices and resp.choices[0].message:
                return resp.choices[0].message.content or ""
            return "[无响应]"
        except Exception as e:
            return f"[错误] {type(e).__name__}: {e}"

    async def step(self, tick: int, t: datetime) -> str:
        """执行一个生产季：观察 → 决策 → 提交 → 记录。"""
        # 1) 观察（只读）
        try:
            _, obs = await self.ask_env(
                {},
                "请调用 observe_market 获取当前市场环境、政策与天气信息，并原样返回。",
                readonly=True,
            )
        except Exception as e:
            obs = f"[观察失败] {type(e).__name__}: {e}"

        # 2) LLM 决策
        decision = await self._decide(obs, t)

        # 3) 提交决策（模板模式：变量替换后执行对应环境工具）
        for crop, area in (decision.get("plan") or {}).items():
            if area > 0:
                await self._safe_submit(
                    "decide_planting", {"crop": crop, "area": area},
                    "请调用 decide_planting，参数 crop={crop}, area_mu={area}。",
                )
        for crop, area in (decision.get("insured") or {}).items():
            if area > 0:
                await self._safe_submit(
                    "buy_insurance", {"crop": crop, "area": area},
                    "请调用 buy_insurance，参数 crop={crop}, area_mu={area}。",
                )
        tin = float(decision.get("transfer_in") or 0.0)
        tout = float(decision.get("transfer_out") or 0.0)
        if tin > 0:
            await self._safe_submit(
                "transfer_land", {"direction": "in", "area": tin},
                "请调用 transfer_land，参数 direction={direction}, area_mu={area}。",
            )
        elif tout > 0:
            await self._safe_submit(
                "transfer_land", {"direction": "out", "area": tout},
                "请调用 transfer_land，参数 direction={direction}, area_mu={area}。",
            )

        # 4) 记录决策
        record = {"tick": tick, "time": t.isoformat(), **decision}
        self.decision_history.append(record)
        return json.dumps(record, ensure_ascii=False)

    async def _safe_submit(self, tool_hint: str, variables: dict, message: str) -> None:
        """模板模式提交，异常不中断。"""
        try:
            await self.ask_env(
                {"variables": variables},
                message,
                readonly=False,
                template_mode=True,
            )
        except Exception as e:  # noqa: BLE001
            self._logger.warning(f"[{self.name}] {tool_hint} submit failed: {e}")

    async def _decide(self, observation: str, t: datetime) -> dict[str, Any]:
        """LLM 生成决策 JSON；解析失败时回退为"不种、不保、不流转"。"""
        p = self._profile
        available = ", ".join(p.get("available_crops") or [])
        prompt = (
            f"你是{p.get('name', self._name)}，一名{ p.get('region_label', '某地')}的农户。\n"
            f"【你的经营情况】规模 {p.get('farm_size_mu')} 亩（{p.get('scale', '')}），"
            f"风险偏好系数 {p.get('risk_attitude')}（0 保守 ~ 1 冒险），"
            f"资产 {p.get('assets')} 元，年兼业收入 {p.get('off_farm_income_annual')} 元。\n"
            f"可种植作物：{available}\n\n"
            f"【当前市场与政策】\n{observation}\n\n"
            "【决策要求】在风险约束下最大化本季家庭净收入（种植收入+补贴+保险赔付+兼业收入-成本）。\n"
            "输出且仅输出一个 JSON 对象（不要解释）：\n"
            '{"plan": {"作物名": 亩数}, "insured": {"作物名": 亩数}, "transfer_in": 亩数, "transfer_out": 亩数}\n'
            "规则：plan 与 insured 的作物必须来自可种植列表；面积为 0 表示不做；"
            "总面积不要超过经营规模的 1.5 倍；风险厌恶时可投保对冲。"
        )
        try:
            resp = await self.acompletion([{"role": "user", "content": prompt}], stream=False)
            content = ""
            if resp and resp.choices and resp.choices[0].message:
                content = resp.choices[0].message.content or ""
            raw = self._extract_json(content)
            decision = json.loads(raw)
            return self._sanitize(decision)
        except Exception as e:  # noqa: BLE001
            self._logger.warning(f"[{self.name}] decision parse failed: {e}")
            return {"plan": {}, "insured": {}, "transfer_in": 0.0, "transfer_out": 0.0}

    @staticmethod
    def _extract_json(text: str) -> str:
        m = re.search(r"\{.*\}", text or "", re.DOTALL)
        return m.group(0) if m else "{}"

    def _sanitize(self, decision: dict[str, Any]) -> dict[str, Any]:
        """规范化决策：作物限于可种植列表，面积非负。"""
        ok_crops = set(self._profile.get("available_crops") or [])

        def norm_crop_map(d: Any) -> dict[str, float]:
            out: dict[str, float] = {}
            if not isinstance(d, dict):
                return out
            for crop, area in d.items():
                crop = str(crop).strip().lower()
                try:
                    area_f = max(0.0, float(area))
                except (TypeError, ValueError):
                    area_f = 0.0
                if crop in ok_crops and area_f > 0:
                    out[crop] = area_f
            return out

        return {
            "plan": norm_crop_map(decision.get("plan")),
            "insured": norm_crop_map(decision.get("insured")),
            "transfer_in": max(0.0, float(decision.get("transfer_in") or 0.0)),
            "transfer_out": max(0.0, float(decision.get("transfer_out") or 0.0)),
        }

    async def dump(self) -> dict[str, Any]:
        """序列化智能体状态。"""
        return {
            "id": self._id,
            "name": self._name,
            "profile": self._profile,
            "decision_history": self.decision_history,
        }

    async def load(self, dump_data: dict[str, Any]) -> None:
        """从字典加载智能体状态。"""
        self._id = dump_data.get("id", self._id)
        self._name = dump_data.get("name", self._name)
        if dump_data.get("profile"):
            self._profile = dump_data["profile"]
        self.decision_history = dump_data.get("decision_history", [])
