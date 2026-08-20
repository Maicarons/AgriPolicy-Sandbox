# 政策情景与反事实

AgriPolicy Sandbox 用**分阶段反事实**识别政策效应：同一批农户先跑基线（空政策）、再施加情景政策，
前后两阶段差异即为该政策的处理效应估计，农户个体异质性被"同批样本"自然控制。

## 内置情景

| 情景 key | label | 政策设置 | 对应假设 |
| --- | --- | --- | --- |
| `baseline` | 基准情景（无新增补贴） | 所有补贴为 0 | 反事实对照 |
| `grain_subsidy` | 粮食直补（120 元/亩） | `wheat/corn/rice=120`、`soybean=60` 元/亩 | H1 |
| `insurance_subsidy` | 农业保险保费补贴（80%） | 政府承担 80% 保费 | H2 |
| `land_transfer_subsidy` | 土地流转激励（转出 200 元/亩） | 转出补贴 200 元/亩 | H3 |
| `combined` | 组合政策 | 直补 + 保险补贴 + 流转补贴 | H4 |

> 注：`policy_scenarios.json` 中的 `baseline` 当前写的是 `subsidy_per_mu: {}`、各补贴率为 0（与论文 v2 中
> "粮食直补 120 元/亩"的"现状基线"描述略有差异，代码侧以配置文件为准）。如需把现状直补纳入基线，
> 直接编辑 `configs/policy_scenarios.json` 的 `baseline.policy` 即可，无需改代码。

## 反事实识别逻辑

```text
阶段一（baseline_steps 季）：空政策运行 → 建立"政策前"基准
        │
        │  env.apply_policy(scenario.policy)
        ▼
阶段二（policy_steps 季）：施加情景政策 → 观察"政策后"动态

处理效应 ≈ 阶段二表现 − 阶段一表现（同批农户，个体异质性被控制）
```

每个 `(情景, 重复)` 组合用不同随机种子（`seed + repeat`）与农户抽样，估计效应分布与置信区间。

## 假设映射

- **H1**：提高粮食直补强度 → 提高粮食播种面积占比，对"粮经比"敏感的小农更明显（`grain_subsidy`）。
- **H2**：保费补贴 → 降低风险厌恶农户的保守种植倾向，提高高价值、高波动作物与规模经营意愿（`insurance_subsidy`）。
- **H3**：流转激励 → 土地向种粮大户集中，提高规模化与单产，但可能短期加剧小农离农（`land_transfer_subsidy`）。
- **H4**：单纯增收工具可能挤压粮食面积，"补贴 + 保险 + 流转"组合才可能兼顾安全与增收（`combined`）。

## 自定义情景

在 `configs/policy_scenarios.json` 的 `scenarios` 中增删条目即可，无需改代码；随后用
`--scenario <你的key>` 或继续 `--all` 运行。配置字段详见 [配置说明](/guide/configuration)。

相关：研究方法见 [实验设计](/methodology/experimental-design) 与 [识别策略](/methodology/identification)。
