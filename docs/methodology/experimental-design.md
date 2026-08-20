# 实验设计

## 1. 农户智能体（FarmerAgent）

采用平台官方"行为实验"模式（`AgentBase` + 手写 `step` + `ask_env` 模板提交）：继承 `AgentBase`，
手写 step，每季「观察 → LLM 决策 → 模板模式提交环境工具」，不启用通用认知循环，LLM 调用少、行为可控。

- **画像（profile）**：区域（华北/东北/长江中游/西南）、经营规模（小农<10 亩 / 中农 10–50 / 大户>50）、
  风险偏好、初始资产、家庭兼业收入、年龄、教育、可用作物；
- **每季流程**：`observe_market` 获取价格/补贴/保险/天气 → LLM 依画像与观察输出
  `{"plan":{作物:亩}, "insured":{作物:亩}, "transfer_in":亩, "transfer_out":亩}` →
  通过 `ask_env`（模板模式）提交 `decide_planting` / `buy_insurance` / `transfer_land`；
- 决策历史保留在智能体内（`decision_history`），用于机制分析。

## 2. 村庄农业经济环境（AgriPolicyEnv）

基于 `EnvBase` 实现：

- **工具面**：`observe_market`、`decide_planting`、`buy_insurance`、`transfer_land`（租入/转出）、`report_status`；
- **政策干预工具**：`set_subsidy`、`set_insurance_subsidy_rate`、`set_land_transfer_out_subsidy`，
  可直接编程调用，也可经 `AgentSociety.intervene` 以自然语言触发；
- 每步（一个生产季）更新价格与天气冲击、逐户核算收支，写入回放表
  （`agri_policy_agent_state` / `agri_policy_env_state`），分析阶段直接读 SQLite。

**标定参数独立成文件**：作物目录、单产、价格、成本、保费、租金、灾害阈值全部集中在 `configs/economics.json`，
由 `economics.py` 加载，不改代码即可替换参数。核算公式是纯函数（零平台依赖，有单元测试），答辩时可直接逐项讲清。

## 3. 政策情景与反事实

| 情景 | 政策设置 |
| --- | --- |
| baseline | 现状：无新增补贴（反事实对照） |
| grain_subsidy | 小麦/玉米/水稻 120 元/亩，大豆 60 元/亩 |
| insurance_subsidy | 政府承担 80% 保费 |
| land_transfer_subsidy | 转出补贴 200 元/亩 |
| combined | 上述组合 |

识别策略是**分阶段反事实**：同一批农户先跑 `baseline_steps` 个季度（空政策），随后施加情景政策再跑
`policy_steps` 个季度。前后两阶段的差异就是处理效应估计，农户个体异质性被同一批样本控制住。
每个情景重复多次（不同随机种子），估计效应分布与置信区间。详见 [识别策略](/methodology/identification)。

## 4. 代码结构

```
agri_sandbox/
  economics.py         # 纯经济核算模型（零平台依赖，可单测、可标定）
  profiles.py          # 异质农户画像生成
  farmer_agent.py      # FarmerAgent（AgentBase 子类，手写 step + ask_env）
  agri_policy_env.py   # AgriPolicyEnv（EnvBase 子类，工具 + 回放）
  experiment.py        # ExperimentSpec + build_world + run_one（编排核心）
  run_experiment.py    # CLI 入口（薄层）
  analyze.py           # 回放 SQLite 分析：均值、处理效应、农户级净收入效应
  llm_config.py        # .env 加载与 LLM 配置校验
  patches.py           # 上游兼容补丁（json_repair.dumps / Windows fsync / slice_text_page）
configs/
  policy_scenarios.json   # 情景定义（默认 50 农户、8+8 季、90 天/季、3 次重复）
  economics.json          # 标定参数（作物/价格/成本/保费/租金/灾害阈值）
tests/test_economics.py   # 核算纯函数单测
```

## 5. 数据采集与分析方法

### 数据源

- `agri_policy_agent_state`：逐季逐户的种植面积、投保面积、流转、毛收入、补贴、赔付、成本、净收入；
- `agri_policy_env_state`：逐季全村均值、投保覆盖率、补贴总额、天气冲击；
- 农户工作区决策日志与对话记录：用于机制质性分析。

### 指标

- **结果指标**：粮食播种面积占比、农户人均纯收入、务农劳动力占比、土地流转率、保险参与率；
- **分配指标**：收入基尼系数（按规模分组）；
- **成本指标**：单位增收的财政成本（补贴总额 / 增收额）；
- **权衡**：粮食安全指数对增收指数的 Pareto 前沿。

### 分析

- 情景均值对比 + bootstrap 95% 置信区间；
- 按规模 / 年龄 / 风险偏好分群的异质性比较；
- 机制检验：对智能体决策日志做质性编码，看"风险预期路径"与"收益比较路径"是否出现；
- 可复现：固定种子、存档 `run_dir`、记录模型版本与温度。

## 6. 风险与边界

- **外部效度**：模拟是受控实验，不等于真实政策效果，结论定位为"机制性启示"；
- **参数示意性**：当前 `economics.json` 是示意值，正式实验需按公开统计年鉴与农户调查数据标定，报告写明参数来源与敏感性；
- **额度约束**：200 元 API 额度有限，先小样本跑通链路再放大，决策用 NANO 档模型；
- **刻板印象**：农户画像基于统计分布生成，不代表任何具体个体，论文声明抽样逻辑；
- **学术诚信**：代码与工作区随作品提交，明确说明 AI 在流程中的角色。
