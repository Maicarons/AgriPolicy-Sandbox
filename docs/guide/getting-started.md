# 快速开始

本文带你在本机跑通 AgriPolicy Sandbox 的完整链路：安装依赖 → 配置 LLM → 运行实验 → 分析结果。

## 1. 环境要求

- Python ≥ 3.11（项目在 3.12 下验证）
- 一个可用的 LLM API（[AgentSociety²](https://agentsociety2.readthedocs.io/zh-cn/latest/index.html) 支持的大模型，如 OpenAI 兼容端点）
- 比赛平台账号与 API 额度（约 200 元），用于平台侧凭证

## 2. 安装依赖

```bash
# 建议在虚拟环境中安装
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

> **已知坑**：`agentsociety2` 依赖较重（含 torch / mineru 等）。若 `pip install -r requirements.txt`
> 装全量依赖遇到冲突，可改为 `--no-deps` 安装平台后再逐个补缺：
> ```bash
> pip install --no-deps agentsociety2
> # 按 import 报错补：json-repair、litellm、aiosqlite、mem0ai、faiss-cpu、ruamel-yaml、stringcase
> ```
> 项目 `agri_sandbox/llm_config.py` 内置了 `json_repair.dumps` 等上游兼容补丁，已验证可跑通。

## 3. 配置 LLM 凭证

```bash
cp .env.example .env
```

编辑 `.env`，填入以下字段（`.env` 已被 `.gitignore` 忽略，请勿提交）：

```dotenv
AGENTSOCIETY_LLM_API_KEY=sk-xxxx
AGENTSOCIETY_LLM_API_BASE=https://your-endpoint/v1
AGENTSOCIETY_LLM_MODEL=gpt-4o-mini
```

> ⚠️ `agentsociety2` 在**导入时**即校验 `AGENTSOCIETY_LLM_API_KEY`，请务必先填好 `.env` 再运行。

## 4. 连通性自检（推荐先做）

只用 1 个农户、1+1 个季度跑一次 baseline（空政策），快速验证"平台 → 环境 → 智能体 → 回放"链路是否通畅：

```bash
python -m agri_sandbox.run_experiment --scenario baseline --repeats 1 --agents 1 --baseline-steps 1 --policy-steps 1
```

## 5. 运行全部情景

```bash
# 运行 configs 中全部情景（baseline + 4 个政策情景），每情景默认 3 次重复
python -m agri_sandbox.run_experiment --all

# 自定义：单情景、80 农户、基线 6 季、政策 10 季
python -m agri_sandbox.run_experiment --scenario combined --agents 80 \
    --baseline-steps 6 --policy-steps 10 --repeats 5
```

每个 `(情景, 重复)` 组合写入独立目录，回放数据落入 `results/<情景>/repeat_*/sqlite.db`，
并生成 `results/runs_index.json` 实验索引。

## 6. 分析结果

```bash
python -m agri_sandbox.analyze --results-dir results
```

输出 `results/summary.csv` 与 `results/summary.json`，并在终端打印 Markdown 摘要表，包含：
平均家庭净收入、平均补贴收入、保险覆盖率、平均种植面积、全村补贴支出的
**基线 vs 政策**对比与处理效应（Δ 与相对变化），以及农户级净收入处理效应的均值与离散度。

## 7. 目录速览

```
AgriPolicy-Sandbox/
├── configs/                 # 情景与标定参数
├── agri_sandbox/            # 实验代码包（分层解耦）
├── tests/                   # 经济核算纯函数单测
├── paper/                   # 论文源文件（本地保留，未随仓库发布）
└── results/                 # 运行产出（回放 SQLite / 分析摘要，已被忽略）
```

下一步：[配置说明](/guide/configuration) 了解参数如何标定，或 [运行实验](/guide/running-experiments) 查看完整 CLI 选项。
