# 配置说明

AgriPolicy Sandbox 的实验参数分为两类，全部以 JSON 文件形式集中管理、不写死在代码里：

| 文件 | 作用 |
| --- | --- |
| `configs/policy_scenarios.json` | 情景定义、默认规模 / 步数 / 种子 / 重复，以及每个情景的 `policy` 政策字典 |
| `configs/economics.json` | 农业经济学标定参数：作物单产 / 价格 / 成本 / 保费、租金、灾害阈值、市场与天气冲击分布 |

## policy_scenarios.json

结构为 `{ "defaults": {...}, "scenarios": { <key>: {...} } }`。

### defaults（全局默认，可被 CLI 覆盖）

| 字段 | 默认 | 含义 |
| --- | --- | --- |
| `num_agents` | 50 | 农户数（异质画像由 `profiles.make_farmer_profiles` 生成） |
| `seed` | 42 | 基础随机种子（叠加 `repeat` 得到每重复的可复现种子） |
| `baseline_steps` | 8 | 阶段一（空政策）运行的"生产季"数 |
| `policy_steps` | 8 | 阶段二（施加政策后）运行的"生产季"数 |
| `tick_seconds` | 7776000 | 每季对应的仿真时间步长（=90 天） |
| `repeats` | 3 | 每个情景的重复次数 |
| `start_date` | 2025-01-01T00:00:00 | 仿真起始日期 |
| `crops` | `["wheat","corn","soybean","rice","vegetable"]` | 可选作物清单 |

### scenarios（情景）

每个情景包含 `label` / `description` / `policy`。`policy` 字典的规范字段如下（由
`AgriPolicyEnv._normalize_policy` 归一并补全缺省）：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `subsidy_per_mu` | `{作物: 元/亩}` | 各作物的生产性补贴（如 `{"wheat":120}`） |
| `insurance_subsidy_rate` | float 0~1 | 政府承担的农业保险保费比例 |
| `land_transfer_out_subsidy_per_mu` | float | 土地转出（退出承包）补贴，元/亩 |
| `grain_price_support` | float | 粮作价格支持，元/kg（作用于 `wheat/corn/rice/soybean`） |

内置情景（与论文假设一一对应）：

| 情景 key | 含义 | 对应假设 |
| --- | --- | --- |
| `baseline` | 无新增补贴（对照） | — |
| `grain_subsidy` | 小麦/玉米/水稻 120 元/亩，大豆 60 元/亩 | H1 |
| `insurance_subsidy` | 政府承担 80% 保费 | H2 |
| `land_transfer_subsidy` | 转出补贴 200 元/亩 | H3 |
| `combined` | 直补 + 保险补贴 + 流转补贴 组合 | H4 |

## economics.json

覆盖 `agri_sandbox/economics.py` 中的模块级默认值；缺省字段回落到代码默认值。

| 字段 | 默认 | 含义 |
| --- | --- | --- |
| `crops.<crop>.yield` | 见代码 | 单产 kg/亩 |
| `crops.<crop>.price` | 见代码 | 收购价 元/kg |
| `crops.<crop>.cost` | 见代码 | 物化成本 元/亩 |
| `crops.<crop>.premium` | 见代码 | 纯保费 元/亩 |
| `crops.<crop>.insured_yield` | 见代码 | 保险保产基准 kg/亩 |
| `rent_in_per_mu` | 500 | 租入地租 元/亩/季 |
| `rent_out_per_mu` | 500 | 转出地租 元/亩/季 |
| `disaster_threshold` | -0.15 | 天气冲击低于该值视为灾害年景，触发赔付 |
| `insurance_payout_ratio` | 0.7 | 赔付 = 保产基准 × 价格 × 该比例 |
| `price_shock_bounds` | [-0.4, 0.4] | 价格冲击系数随机游走边界 |
| `price_shock_sigma` | 0.05 | 价格冲击每步高斯步长 |
| `weather_shock_bounds` | [-0.5, 0.3] | 天气冲击系数边界 |
| `weather_shock_mu` | -0.02 | 天气冲击漂移均值（略偏减产） |
| `weather_shock_sigma` | 0.18 | 天气冲击每步高斯步长 |

> **郑重提醒**：当前 `economics.json` 中的数值均为**示意值**。正式实验应基于公开统计年鉴与农户
> 调查数据重新标定，并在论文中写明参数来源与敏感性分析。核算公式为纯函数，换数据不改代码。
