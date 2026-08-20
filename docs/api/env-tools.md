# API · 环境工具 `env tools`

`AgriPolicyEnv`（`agri_sandbox/agri_policy_env.py`，继承 AgentSociety² `EnvBase`）暴露以下工具。
工具通过 AgentSociety² 的 `@tool` 装饰器声明，`readonly` 标记是否改变环境状态。

## 观测

### `observe_market(agent_id: int) -> str`  `readonly=True`

观测当前市场环境与政策：天气冲击系数、各作物收购价（含市场冲击）、生产性补贴、保险保费补贴率、土地流转转出补贴。

## 生产决策

### `decide_planting(agent_id: int, crop: str, area_mu: float) -> str`  `readonly=False`

设定某种植作物的面积（亩）。可多次调用以设定全部作物的生产结构；设 0 表示不种。
`crop` 必须为 `params.crops` 且在该农户 `available_crops` 内（否则返回错误提示）。

### `buy_insurance(agent_id: int, crop: str, area_mu: float) -> str`  `readonly=False`

为某作物投保指定面积（亩）。设 0 表示退保该作物。

### `transfer_land(agent_id: int, direction: str, area_mu: float) -> str`  `readonly=False`

土地流转：`direction='in'` 租入（扩大经营），`direction='out'` 转出（退出承包）。`in` 与 `out` 互斥。

### `report_status(agent_id: int) -> str`  `readonly=True`

查询本农户上一季核算结果与当前决策（plan / insured / transfer / last_net_income 等），便于复盘。

## 政策干预

这些工具**可由 `AgentSociety.intervene` 以自然语言触发，也可由 `experiment.run_one` 在基线阶段后直接编程调用**
（`env.apply_policy`）。

### `set_subsidy(crop: str, amount_per_mu: float) -> str`  `readonly=False`

设定某作物生产性补贴（元/亩）。`amount_per_mu=0` 表示取消该作物补贴。

### `set_insurance_subsidy_rate(rate: float) -> str`  `readonly=False`

设定政府承担的农业保险保费比例（0~1，自动 clamp）。

### `set_land_transfer_out_subsidy(amount_per_mu: float) -> str`  `readonly=False`

设定土地转出（退出承包）补贴（元/亩）。

## 环境方法

### `apply_policy(policy: dict) -> str`

确定性地施加政策（分阶段反事实下由 `run_one` 在基线阶段后调用，保证可复现）。内部经 `_normalize_policy` 归一。

### `step(tick: int, t: datetime)`  `async`

推进一个生产季：更新市场/天气冲击 → 逐户核算（`compute_farmer_accounting`）→ 写逐户回放行 → 写环境级回放行。

### `get_agent_skills_dirs() -> list[Path]` / `get_default_skill() -> str | None`

技能发现：`agri_sandbox/agent_skills` 目录，`"agri-decision"` 为默认技能。

## 政策字典规范

`AgriPolicyEnv._normalize_policy` 归一并补全缺省的规范结构：

```python
{
    "subsidy_per_mu": dict,                 # {作物: 元/亩}
    "insurance_subsidy_rate": float,        # 0~1
    "land_transfer_out_subsidy_per_mu": float,
    "grain_price_support": float,           # 元/kg，作用于主粮
}
```

相关：[政策环境 AgriPolicyEnv](/concepts/policy-environment)。
