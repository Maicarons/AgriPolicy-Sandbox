# API · 回放数据表

`AgriPolicyEnv.step` 每个生产季把状态写入两张回放表（由 AgentSociety² 存储层自动建表 + 注册 dataset）。
`analyze.py` 直接读取这两张表计算处理效应。

## `agri_policy_agent_state`（逐户 · 每步每农户一行）

| 列 | 类型 | 单位 | 说明 |
| --- | --- | --- | --- |
| `crop_mix_json` | JSON | — | 当前生产结构（作物→面积 亩） |
| `planted_area_mu` | REAL | 亩 | 已种植面积合计 |
| `insured_area_mu` | REAL | 亩 | 投保面积合计 |
| `transfer_in_mu` | REAL | 亩 | 转入（租入）土地面积 |
| `transfer_out_mu` | REAL | 亩 | 转出（租出）土地面积 |
| `gross_revenue` | REAL | 元 | 农业毛收入 |
| `subsidy_income` | REAL | 元 | 生产 / 价格 / 流转补贴合计 |
| `insurance_payout` | REAL | 元 | 保险赔付收入 |
| `total_cost` | REAL | 元 | 成本合计（物化 + 保费 + 租入） |
| `net_income` | REAL | 元 | 本季家庭净收入（含兼业） |

> 除 `crop_mix_json` 外，均带 `analysis_role="measure"` 标记，便于平台侧自动分析。

## `agri_policy_env_state`（村级 · 每步一行）

| 列 | 类型 | 单位 | 说明 |
| --- | --- | --- | --- |
| `avg_net_income` | REAL | 元 | 全体农户平均净收入 |
| `avg_subsidy_income` | REAL | 元 | 平均补贴收入 |
| `insurance_coverage_rate` | REAL | — | 投保面积 / 种植面积 的均值 |
| `avg_planted_area` | REAL | 亩 | 平均种植面积 |
| `n_planting_farmers` | INTEGER | — | 有种植行为的农户数 |
| `total_subsidy` | REAL | 元 | 全村补贴支出合计 |
| `weather_shock` | REAL | — | 本季天气冲击系数（负为减产） |

## 元信息 `run_meta.json`

每个 `(情景, 重复)` 目录下的 `run_meta.json` 记录：

```json
{
  "scenario_key": "combined",
  "scenario_label": "组合政策（直补+保险+流转）",
  "repeat": 0,
  "num_agents": 50,
  "seed": 42,
  "baseline_steps": 8,
  "policy_steps": 8,
  "tick_seconds": 7776000,
  "start_date": "2025-01-01T00:00:00",
  "phased": true,
  "policy": { "...": "..." },
  "economics_path": null,
  "run_dir": "results/combined/repeat_0",
  "finished_at": "2026-08-20T..."
}
```

`analyze` 用 `baseline_steps` 把 `step` 拆成基线期（`step <= baseline_steps`）与政策期（`step > baseline_steps`）。

## 示例查询

```sql
-- 某次实验的农户级净收入处理效应
SELECT agent_id,
       AVG(CASE WHEN step <= 8 THEN net_income END) AS base,
       AVG(CASE WHEN step  > 8 THEN net_income END) AS pol
FROM agri_policy_agent_state
GROUP BY agent_id;
```

相关：[回放分析](/guide/analysis)。
