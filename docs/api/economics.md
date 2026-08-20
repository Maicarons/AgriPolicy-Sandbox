# API · 经济核算 `economics`

模块 `agri_sandbox/economics.py`，**零平台依赖、纯函数、可单测**。完整签名如下（省略部分类型标注）。

## `EconomicsParams`

标定参数集合。

```python
@dataclass
class EconomicsParams:
    crops: dict[str, dict[str, float]]          # 作物标定：yield/price/cost/premium/insured_yield
    rent_in_per_mu: float = 500.0               # 租入地租 元/亩/季
    rent_out_per_mu: float = 500.0              # 转出地租 元/亩/季
    disaster_threshold: float = -0.15           # 天气冲击低于该值视为灾害年景
    insurance_payout_ratio: float = 0.7         # 赔付比例
    price_shock_bounds: tuple[float, float] = (-0.4, 0.4)
    price_shock_sigma: float = 0.05
    weather_shock_bounds: tuple[float, float] = (-0.5, 0.3)
    weather_shock_mu: float = -0.02
    weather_shock_sigma: float = 0.18

    @property
    def grains(self) -> set[str]: ...           # {'wheat','corn','rice','soybean'}

    @classmethod
    def from_file(cls, path: str | Path) -> "EconomicsParams": ...
    def to_dict(self) -> dict[str, Any]: ...
```

- `EconomicsParams()`：使用模块级默认值；
- `EconomicsParams.from_file("configs/economics.json")`：从 JSON 加载，缺省字段回落默认。

## `compute_farmer_accounting(...)` → `FarmerAccounting`

逐户收支核算（纯函数）。

```python
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
) -> FarmerAccounting: ...
```

| 参数 | 说明 |
| --- | --- |
| `plan` | 生产结构 `{作物: 面积(亩)}` |
| `insured` | 投保结构 `{作物: 投保面积(亩)}` |
| `transfer_in_mu` | 租入面积 |
| `transfer_out_mu` | 转出面积 |
| `policy` | 规范政策字典（见 `AgriPolicyEnv._normalize_policy` 输出） |
| `price_shock` | 各作物价格冲击系数 `{作物: 浮点}` |
| `weather_shock` | 天气冲击系数（负为减产） |
| `off_farm_income_annual` | 家庭年兼业收入（按季折算 1/4） |
| `params` | 标定参数；默认用模块级默认 |

### `FarmerAccounting`

```python
@dataclass
class FarmerAccounting:
    gross_revenue: float = 0.0
    total_cost: float = 0.0
    subsidy_income: float = 0.0
    insurance_payout: float = 0.0
    rent_income: float = 0.0
    off_farm_income: float = 0.0
    net_income: float = 0.0
    planted_area_mu: float = 0.0
    insured_area_mu: float = 0.0

    def to_dict(self) -> dict[str, float]: ...
```

## `village_summary(...)` → dict

村级汇总统计（供环境级回放与分析）。

```python
def village_summary(
    accounts: list[FarmerAccounting],
    total_subsidy: float,
    weather_shock: float,
) -> dict[str, float]: ...
```

返回键：`avg_net_income`、`avg_subsidy_income`、`insurance_coverage_rate`、
`avg_planted_area`、`n_planting_farmers`、`total_subsidy`、`weather_shock`。

## 模块级常量

| 常量 | 含义 |
| --- | --- |
| `DEFAULT_CROPS` | 默认作物标定字典（wheat/corn/rice/soybean/vegetable） |
| `GRAINS` | 主粮作物集合 `{wheat, corn, rice, soybean}`（享受粮价支持） |
| `RENT_IN_PER_MU` / `RENT_OUT_PER_MU` | 默认地租 |
| `DISASTER_THRESHOLD` / `INSURANCE_PAYOUT_RATIO` | 灾害阈值 / 赔付比例 |
| `PRICE_SHOCK_*` / `WEATHER_SHOCK_*` | 市场与天气冲击分布参数 |

## 示例

```python
from agri_sandbox.economics import EconomicsParams, compute_farmer_accounting

params = EconomicsParams.from_file("configs/economics.json")
policy = {"subsidy_per_mu": {"wheat": 120}, "insurance_subsidy_rate": 0.0,
          "land_transfer_out_subsidy_per_mu": 0.0, "grain_price_support": 0.0}

acct = compute_farmer_accounting(
    plan={"wheat": 10.0}, insured={"wheat": 10.0},
    transfer_in_mu=0.0, transfer_out_mu=0.0,
    policy=policy, weather_shock=0.0,
    off_farm_income_annual=20000.0, params=params,
)
print(acct.net_income)
```

相关：[经济核算模型](/concepts/economics-model)。
