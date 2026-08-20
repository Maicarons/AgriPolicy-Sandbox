# 政策环境 AgriPolicyEnv

`agri_sandbox/agri_policy_env.py` 中的 `AgriPolicyEnv` 继承 AgentSociety² 的 `EnvBase`，
为农户智能体提供**观测 / 生产决策 / 政策干预 / 复盘**四类工具，并在每个仿真步（一个生产季）
核算农户收支、把逐帧状态写入回放 SQLite。

## 工具面

### 观测

| 工具 | 只读 | 说明 |
| --- | --- | --- |
| `observe_market(agent_id)` | ✅ | 观测当前市场环境与政策：天气冲击系数、各作物收购价、生产性补贴、保险保费补贴率、土地流转转出补贴 |

### 生产决策

| 工具 | 只读 | 说明 |
| --- | --- | --- |
| `decide_planting(agent_id, crop, area_mu)` | ❌ | 设定某作物种植面积（亩）；可多次调用设定全部生产结构；设 0 表示不种 |
| `buy_insurance(agent_id, crop, area_mu)` | ❌ | 为某作物投保指定面积；设 0 表示退保 |
| `transfer_land(agent_id, direction, area_mu)` | ❌ | 土地流转：`direction='in'` 租入（扩大经营）/`'out'` 转出（退出承包） |
| `report_status(agent_id)` | ✅ | 查询本农户上一季核算结果与当前决策，便于复盘 |

### 政策干预

这些工具**可由 `AgentSociety.intervene` 以自然语言触发，也可在基线阶段后由 `run_experiment` 直接编程调用**
（`env.apply_policy`），以保证可复现：

| 工具 | 说明 |
| --- | --- |
| `set_subsidy(crop, amount_per_mu)` | 设定某作物生产性补贴（元/亩）；`amount_per_mu=0` 取消 |
| `set_insurance_subsidy_rate(rate)` | 设定政府承担的保费比例（0~1） |
| `set_land_transfer_out_subsidy(amount_per_mu)` | 设定土地转出补贴（元/亩） |

## 政策状态与施加

- 环境的政策状态是一个规范字典：`{ subsidy_per_mu, insurance_subsidy_rate, land_transfer_out_subsidy_per_mu, grain_price_support }`，由 `_normalize_policy` 归一并补全缺省；
- 分阶段反事实下，`build_world` 初始政策为空（基线阶段）；`run_one` 在基线阶段后调用 `env.apply_policy(spec.policy)` 施加情景政策;
- 若 `--no-phased`，则 `build_world` 直接用 `spec.policy` 初始化，政策从第一步生效。

## 每步核算与回放

`AgriPolicyEnv.step(tick, t)` 做四件事：

1. **更新市场 / 天气冲击**：价格、天气冲击按配置的高斯随机游走更新（可复现，由 `seed` 控制）；
2. **逐户核算**：对每户调用 `economics.compute_farmer_accounting`，得到毛收入 / 成本 / 补贴 / 赔付 / 净收入等；
3. **写逐户回放行**：写入 `agri_policy_agent_state` 表（每步每农户一行）；
4. **写环境级回放行**：对全村汇总，写入 `agri_policy_env_state` 表（每步一行）。

回放表字段定义见 [回放数据表](/api/data-schema)。

## 技能发现

环境通过 `get_agent_skills_dirs()` 暴露 `agri_sandbox/agent_skills` 目录，`get_default_skill()`
返回 `"agri-decision"`，让农户智能体自动激活决策技能（`agri_decision/SKILL.md`）。

下一步：[经济核算模型](/concepts/economics-model)。
