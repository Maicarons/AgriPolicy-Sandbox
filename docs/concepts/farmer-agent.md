# 农户智能体 FarmerAgent

`agri_sandbox/farmer_agent.py` 中的 `FarmerAgent` 继承 AgentSociety² 的 `AgentBase`，
采用平台官方推荐的**"行为实验"模式**：不启用通用认知循环，而是**手写 `step`**，每季走
"观察 → LLM 决策 → 模板模式 `ask_env` 提交环境工具"的确定性流程。这样 LLM 调用少、行为可控、便于机制分析。

## 画像（profile）

每个农户在生成时带有异质属性（由 `profiles.make_farmer_profiles` 按统计分布生成）：

| 属性 | 说明 |
| --- | --- |
| 区域 | 华北 / 东北 / 长江中游 / 西南 |
| 经营规模 | 小农 <10 亩 / 中农 10–50 亩 / 大户 >50 亩 |
| 风险偏好 | 连续值（影响保守/冒险种植倾向） |
| 初始资产 | 家庭资产基线 |
| 家庭兼业收入 | 年兼业收入（按季折算 1/4 计入净收入） |
| 年龄 / 教育 | 影响信息获取与采纳 |
| 可用作物 | 受区域约束的可种植作物集合 |

> 画像基于统计分布生成，不代表任何具体个体；论文中声明抽样逻辑，避免刻板印象。

## 每季决策流程

```text
observe_market ──▶ LLM 依画像 + 观察输出决策 JSON ──▶ ask_env 提交工具
       │                                                      │
       │            {"plan":{作物:亩}, "insured":{作物:亩},    │
       │             "transfer_in":亩, "transfer_out":亩}     │
       ▼                                                      ▼
   获取价格/补贴/保险/天气                          decide_planting / buy_insurance / transfer_land
```

- `observe_market`：每季开始观测当前市场价格、补贴、保险、天气冲击；
- LLM 依据画像与观察，输出结构化决策（生产结构、投保、土地流转）；
- 通过 `ask_env`（模板模式）提交 `decide_planting` / `buy_insurance` / `transfer_land`；
- 决策历史保留在智能体内（`decision_history`），供机制分析。

## 决策如何落到环境

工具参数使用 **`agent_id`（int）** 而非自然语言名字——这是 AgentSociety² 官方 `economy_space` 的同款设计，
避免 LLM 猜错农户名字导致决策错配。环境侧 `AgriPolicyEnv` 据此维护权威的农户状态字典。

## 行为实验模式的价值

- **可控**：不启用自由认知循环，行为由模板约束，可复现；
- **可解释**：每季决策是显式 JSON，配合 `report_status` 可在复盘时查看上一季核算与当前决策；
- **低成本**：LLM 仅在每季决策时调用一次，配合 NANO 档模型做高频决策，在 200 元额度内可跑通 50 农户 × 8+8 季 × 3 重复。

下一步：[政策环境 AgriPolicyEnv](/concepts/policy-environment)。
