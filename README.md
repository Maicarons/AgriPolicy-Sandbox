# 农业政策沙盒 · AgriPolicy Sandbox

> 基于 [AgentSociety²](https://agentsociety2.readthedocs.io/zh-cn/latest/index.html)（清华大学 · 计算社会科学与国家治理实验室）的农业政策反事实模拟实验。
>
> 对应比赛赛道：**数智公共管理与国家治理**。

📚 **项目文档（VitePress，由 GitHub Pages 自动发布）**：https://maicarons.github.io/AgriPolicy-Sandbox/

## 1. 项目简介

本项目把"农户"建模为具有真实偏好、风险态度与家庭约束的 LLM 智能体，在可定制的村庄农业经济环境中，
通过**干预 API** 施加补贴、农业保险保费补贴、土地流转补贴等政策冲击，做**反事实政策评估**：
同一批农户在"政策前 / 政策后"的净收入、保险参与、种植结构与土地流转变化，即为政策的处理效应估计。

- 研究方向：农业政策模拟与政策沙盒（农林经济管理视角）
- 能力依托：LLM 智能体 + 灵活环境模块 + 干预实验 + 大规模异步仿真 + 逐帧回放分析
- 理论框架：风险下农户生产决策模型、计划行为理论（TPB）、政策工具理论、反事实推断

## 2. 目录结构

```
AgriPolicy-Sandbox/
├── .env.example                 # LLM 配置模板（复制为 .env 后填密钥，勿提交）
├── .gitignore
├── requirements.txt
├── LICENSE
├── README.md
├── research-plan.md             # 研究计划（v2，含前沿文献与去AI化写作）
├── configs/
│   ├── policy_scenarios.json    # 政策情景与默认参数（情景/重复/步数/作物）
│   └── economics.json           # 标定参数（作物/价格/成本/保费/租金/灾害阈值）
├── agri_sandbox/                # 实验代码包（分层解耦）
│   ├── __init__.py
│   ├── llm_config.py            # .env 加载与 LLM 配置校验（含上游兼容补丁）
│   ├── economics.py             # 纯经济核算模型（零平台依赖，可单测、可标定）
│   ├── profiles.py              # 异质农户画像生成
│   ├── farmer_agent.py          # FarmerAgent(AgentBase，行为实验模式：观察→LLM决策→ask_env)
│   ├── agri_policy_env.py       # AgriPolicyEnv(EnvBase)：工具/政策/回放（核算调 economics）
│   ├── experiment.py            # ExperimentSpec + build_world + run_one（编排核心）
│   ├── run_experiment.py        # CLI 入口（薄层）
│   ├── analyze.py               # 回放分析（处理效应）
│   └── agent_skills/
│       └── agri_decision/       # 农户决策技能 SKILL.md
├── tests/
│   └── test_economics.py        # 核算纯函数单测
├── webview/                     # 实验可视化 Web（FastAPI + 原生前端，见 §10）
│   ├── server.py                # API（overview/场景快照/时间序列）+ 静态服务
│   └── static/                  # 暗色仪表盘（HTML/SVG/JS，零前端依赖）
├── run_full_experiment.sh       # 完整实验脚本（smoke/full/analyze/status/webui）
├── paper/                       # 论文源文件与 PDF（本地保留，未随仓库发布）
└── results/                     # 运行产出（回放 SQLite / 分析摘要，已被 .gitignore 忽略）
```

**解耦原则**：标定参数与核算公式独立于平台（`economics.py` + `configs/economics.json`，可单测、可审计）；
实验编排独立于命令行（`experiment.py` 可被脚本/测试复用）；CLI 只负责装配参数。

## 3. 安装与配置

```bash
# 1) 安装依赖（建议在虚拟环境中）
pip install -r requirements.txt
#   若遇到 mineru/torch 等重型依赖冲突：pip install --no-deps agentsociety2
#   再按 import 报错逐个补缺（本项目已验证：json-repair、litellm、aiosqlite、mem0ai、
#   faiss-cpu、ruamel-yaml、stringcase），llm_config.py 内置 json_repair.dumps 兼容补丁。

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

# 覆盖标定参数（可编辑 configs/economics.json，或用 --economics 指定其他文件）
python -m agri_sandbox.run_experiment --scenario grain_subsidy --economics configs/economics.json

# 单元测试（纯经济核算模型，无需平台/网络）
python -m unittest discover -s tests -v

# 完整实验流程（门1+门2 冒烟计时 → 门3 正式批次并行+断点续跑 → 自动分析）
./run_full_experiment.sh smoke && ./run_full_experiment.sh full
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
- **可解释经济学**：收支核算集中在 `agri_sandbox/economics.py`（纯函数 + 单元测试），
  参数集中在 `configs/economics.json`，换数据标定不改代码，答辩可逐项审计。
- **分层解耦**：经济模型 / 环境工具 / 智能体 / 实验编排 / CLI / 分析各自独立，
  便于替换平台版本或单独复测核算公式。
- **异质性**：农户在区域、规模、风险态度、资产、兼业程度、年龄/教育上异质，对应农户行为关键调节变量。
- **理论贡献空间**：公地治理 / 风险分担 / 劳动力再配置等政策机制可在本框架内机制化检验。

## 7. 论文

论文形式研究计划（XeLaTeX 源文件与 PDF）位于 `paper/` 目录，随本地保留，未随本仓库发布。

## 8. 免责声明

本仓库代码与数据均为科研沙盒原型，经济学参数均为示意值，不代表任何真实政策效果；
真实结论须以标定后的参数、平台运行数据与统计推断为准。

## 9. 文档站点

本项目文档使用 [VitePress](https://vitepress.dev/) 编写，位于 `docs/` 目录，由 GitHub Pages 通过
CI（`.github/workflows/deploy-docs.yml`）在推送 `main` 且 `docs/` 变更时自动构建并发布：

- **在线文档**：https://maicarons.github.io/AgriPolicy-Sandbox/
- **文档源**：`docs/index.md` 及 `guide/`、`concepts/`、`methodology/`、`api/`、`reference/` 子目录
- **本地预览**：`cd docs && npm install && npm run docs:dev`
- **本地构建**：`cd docs && npm run docs:build`（产物位于 `docs/.vitepress/dist`）

文档内容覆盖：快速开始、配置说明、运行实验、回放分析、核心概念（架构 / 农户智能体 / 政策环境 /
经济模型 / 情景）、研究方法（问题 / 设计 / 识别策略）、API 参考（economics / 环境工具 / CLI / 数据表）、
贡献指南与许可免责。

## 10. 实验可视化 Web

实验运行时可实时观察进展、可视化村庄场景与村级指标的 Web 仪表盘（原生 HTML + SVG + JS，零前端依赖）：

```bash
pip install fastapi uvicorn
python webview/server.py --results-dir results --port 8000
# 打开 http://127.0.0.1:8000
```

- **实时进展**：`experiment.run_one` 按生产季逐步执行并写 `run_progress.json`，仪表盘 3s 轮询展示
  各情景/重复的状态、阶段（基线期/政策期）、步骤进度与耗时；
- **村庄场景**：读取回放最新一步，SVG 渲染每个农户——颜色=主作物、青色描边=已投保、▲租入/▼转出，
  点击查看收支详情；
- **指标曲线**：净收入（均值±农户间标准差带）、保险覆盖率、种植面积、补贴支出，标注政策分界；
- 更多说明见 `webview/README.md`。