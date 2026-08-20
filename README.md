# 农业政策沙盒 · AgriPolicy Sandbox

> 基于 [AgentSociety²](https://agentsociety2.readthedocs.io/zh-cn/latest/index.html)（清华大学 · 计算社会科学与国家治理实验室）的农业政策反事实模拟实验。
>
> 对应比赛赛道：**数智公共管理与国家治理**。

## 1. 项目简介

本项目把"农户"建模为具有真实偏好、风险态度与家庭约束的 LLM 智能体，在可定制的村庄农业经济环境中，
通过**干预 API** 施加补贴、农业保险保费补贴、土地流转补贴等政策冲击，做**反事实政策评估**：
同一批农户在"政策前 / 政策后"的净收入、保险参与、种植结构与土地流转变化，即为政策的处理效应估计。

- 研究方向：农业政策模拟与政策沙盒（农林经济管理视角）
- 能力依托：LLM 智能体 + 灵活环境模块 + 干预实验 + 大规模异步仿真 + 逐帧回放分析
- 理论框架：风险下农户生产决策模型、计划行为理论（TPB）、政策工具理论、反事实推断

## 2. 目录结构

```
agentsociety-contest/
├── .env.example                 # LLM 配置模板（复制为 .env 后填密钥，勿提交）
├── .gitignore
├── requirements.txt
├── LICENSE
├── README.md
├── configs/
│   └── policy_scenarios.json    # 政策情景与默认参数（情景/重复/步数/作物）
├── agri_sandbox/                # 实验代码包
│   ├── __init__.py
│   ├── llm_config.py            # .env 加载与 LLM 配置校验
│   ├── profiles.py              # 异质农户画像生成
│   ├── farmer_agent.py          # FarmerAgent(PersonAgent)
│   ├── agri_policy_env.py       # AgriPolicyEnv(EnvBase)：工具/政策/回放/经济学核算
│   ├── run_experiment.py        # 实验编排（基线→施加政策→政策后）
│   ├── analyze.py               # 回放分析（处理效应）
│   └── agent_skills/
│       └── agri_decision/       # 农户决策技能 SKILL.md
├── paper/
│   └── research-plan-paper.pdf  # 论文形式研究计划（XeLaTeX 编译）
├── docs/
└── results/                     # 运行产出（回放 SQLite / 分析摘要，已被 .gitignore 忽略）
```

## 3. 安装与配置

```bash
# 1) 安装依赖（建议在虚拟环境中）
pip install -r requirements.txt
#   若报 mineru 等依赖冲突：pip install --no-deps agentsociety2 仅取包体阅读源码

# 2) 配置 LLM（复制模板并填入你的 Key）
cp .env.example .env
#   编辑 .env：AGENTSOCIETY_LLM_API_KEY / AGENTSOCIETY_LLM_API_BASE / AGENTSOCIETY_LLM_MODEL

# 3) 申请比赛平台账号与 API 额度（约 200 元），并在平台侧配置对应凭证
```

> 注意：`agentsociety2` 在**导入时**即校验 `AGENTSOCIETY_LLM_API_KEY`，请务必先填好 `.env` 再运行。

## 4. 运行实验

```bash
# 连通性自检：仅跑 baseline（空政策），快速验证链路
python -m agri_sandbox.run_experiment --scenario baseline --repeats 1

# 运行全部情景（baseline + 4 个政策情景），每情景 3 次重复
python -m agri_sandbox.run_experiment --all

# 自定义：单情景、80 农户、基线 6 步、政策 10 步
python -m agri_sandbox.run_experiment --scenario combined --agents 80 \
    --baseline-steps 6 --policy-steps 10 --repeats 5
```

实验采用**分阶段反事实**设计：先以空政策运行 `baseline_steps` 步，再施加所选情景政策运行
`policy_steps` 步。每个 (情景, 重复) 组合写入独立目录，回放数据落入 `results/<情景>/repeat_*/sqlite.db`。

## 5. 分析结果

```bash
python -m agri_sandbox.analyze --results-dir results
```

输出 `results/summary.csv` 与 `results/summary.json`，并在终端打印 Markdown 摘要表，包含：
平均家庭净收入、平均补贴收入、保险覆盖率、平均种植面积、全村补贴支出的
**基线 vs 政策**对比与处理效应（Δ 与相对变化），以及农户级净收入处理效应的均值与离散度。

## 6. 研究方法要点

- **反事实识别**：同一批农户前后对照，控制个体异质性，得到 cleaner 的政策处理效应。
- **可解释经济学**：环境内置简化但可审计的收支模型（单产×价格−成本+补贴+保险赔付±流转收支），
  所有假设集中在 `agri_policy_env.py` 顶部常量与 `step()` 注释中，便于标定与答辩。
- **异质性**：农户在区域、规模、风险态度、资产、兼业程度、年龄/教育上异质，对应农户行为关键调节变量。
- **理论贡献空间**：公地治理 / 风险分担 / 劳动力再配置等政策机制可在本框架内机制化检验。

## 7. 论文

论文形式研究计划（XeLaTeX 源文件与 PDF）位于 `paper/` 目录，随本地保留，未随本仓库发布。

## 8. 免责声明

本仓库代码与数据均为科研沙盒原型，经济学参数均为示意值，不代表任何真实政策效果；
真实结论须以标定后的参数、平台运行数据与统计推断为准。