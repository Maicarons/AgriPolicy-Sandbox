# 经济核算模型

`agri_sandbox/economics.py` 是整套沙盒的"账本"，**零平台依赖、纯函数、有单元测试**。
设计目标把"标定参数"与"逐户收支核算"从环境模块中剥离，实现三方面的解耦：

1. **参数与逻辑解耦**：作物目录、价格、成本、保费、租金、灾害阈值集中在 `configs/economics.json`，可覆盖、不改代码；
2. **平台依赖解耦**：本模块不 import 任何 `agentsociety2` 组件，可在无平台环境下直接测试与审计；
3. **模型可审计**：核算公式全部为纯函数，便于答辩时逐项讲解"政策冲击 → 农户行为 → 宏观涌现"。

## 经济学口径（简化但可解释，示意值）

$$
\begin{aligned}
\text{毛收入} &= \sum \text{单产}\times(1+\text{天气冲击}) \times \text{面积} \times \text{收购价}\times(1+\text{价格冲击}) \\
\text{成本}   &= \sum \text{物化成本}\times\text{面积} + \sum \text{保费}\times\text{投保面积}\times(1-\text{保费补贴率}) + \text{租入面积}\times\text{地租} \\
\text{补贴}   &= \sum \text{面积}\times\text{生产性补贴} + \text{粮作面积}\times\text{粮价支持} + \text{转出面积}\times(\text{地租}+\text{转出补贴}) \\
\text{赔付}   &= \text{灾害年景下 } \sum \text{投保面积}\times\text{保产基准}\times\text{价格}\times\text{赔付比例} \\
\text{净收入} &= \text{毛收入} + \text{补贴} + \text{赔付} + \text{租金收入} + \text{兼业收入(季)} - \text{成本}
\end{aligned}
$$

## 核心 API

### `EconomicsParams`

标定参数集合，支持 `EconomicsParams()`（默认值）与 `EconomicsParams.from_file(path)`（从 JSON 加载，缺省回落默认）。
只读属性 `grains` 返回主粮作物集合 `{wheat, corn, rice, soybean}`（享受粮价支持）。

### `compute_farmer_accounting(...)` → `FarmerAccounting`

逐户收支核算纯函数。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `plan` | `{作物: 面积}` | 生产结构 |
| `insured` | `{作物: 投保面积}` | 投保结构 |
| `transfer_in_mu` | float | 租入面积 |
| `transfer_out_mu` | float | 转出面积 |
| `policy` | dict | 规范政策字典（见 `_normalize_policy`） |
| `price_shock` | `{作物: 系数}` | 各作物价格冲击 |
| `weather_shock` | float | 天气冲击系数（负为减产） |
| `off_farm_income_annual` | float | 家庭年兼业收入（按季折算 1/4） |
| `params` | `EconomicsParams` | 标定参数，默认用模块级默认 |

返回 `FarmerAccounting`（`gross_revenue / total_cost / subsidy_income / insurance_payout / rent_income / off_farm_income / net_income / planted_area_mu / insured_area_mu`）。

### `village_summary(accounts, total_subsidy, weather_shock)` → dict

村级汇总：平均净收入、平均补贴收入、保险覆盖率（投保面积/种植面积均值）、平均种植面积、种植农户数、全村补贴支出、天气冲击。

## 为什么这样设计

- **换数据不改代码**：正式实验只需替换 `configs/economics.json`（基于统计年鉴标定），核算逻辑不变；
- **可单元测试**：`tests/test_economics.py` 覆盖纯函数（约 10 例），无需平台 / 网络；
- **透明可审计**：公式均为显式算术，答辩时可逐行解释每一笔账的来源。

完整签名见 [API · economics](/api/economics)。
