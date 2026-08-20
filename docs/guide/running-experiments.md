# 运行实验

实验运行器是 `agri_sandbox/run_experiment.py`（CLI 薄层），真正的编排逻辑在 `agri_sandbox/experiment.py`
（`ExperimentSpec` / `build_world` / `run_one` / `run_all`），可被脚本与测试直接复用。

## 命令总览

```bash
python -m agri_sandbox.run_experiment [选项]
```

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--config PATH` | `configs/policy_scenarios.json` | 情景配置文件路径 |
| `--scenario KEY` | 无 | 运行单个情景（见 `configs` 的 `scenarios` 键） |
| `--all` | 关 | 运行 `configs` 中全部情景 |
| `--repeats N` | 配置默认(3) | 重复次数（覆盖配置） |
| `--agents N` | 配置默认(50) | 农户数（覆盖配置） |
| `--baseline-steps N` | 配置默认(8) | 阶段一（空政策）步数 |
| `--policy-steps N` | 配置默认(8) | 阶段二（施加政策）步数 |
| `--seed N` | 配置默认(42) | 基础随机种子 |
| `--economics PATH` | `configs/economics.json` | 标定参数 JSON（覆盖默认） |
| `--results-dir PATH` | `./results` | 结果根目录（已被 `.gitignore` 忽略） |
| `--no-phased` | 关 | 不使用分阶段反事实，政策从第一步即生效 |

> 若既不传 `--all` 也不传 `--scenario`，默认只跑 `baseline` 一次作为连通性自检。

## 典型用法

```bash
# 1) 连通性自检：仅 baseline，1 农户 × 1+1 季
python -m agri_sandbox.run_experiment --scenario baseline --repeats 1

# 2) 全部情景，每情景 3 次重复（configs 默认）
python -m agri_sandbox.run_experiment --all

# 3) 单情景放大：combined，80 农户，6+10 季，5 次重复
python -m agri_sandbox.run_experiment --scenario combined --agents 80 \
    --baseline-steps 6 --policy-steps 10 --repeats 5

# 4) 覆盖标定参数（可编辑 economics.json，或换文件）
python -m agri_sandbox.run_experiment --scenario grain_subsidy --economics configs/economics.json

# 5) 非分阶段：政策从第一步即生效
python -m agri_sandbox.run_experiment --scenario combined --no-phased
```

## 运行阶段与产物

采用**分阶段反事实**设计（默认 `phased=True`）：

1. 先以空政策运行 `baseline_steps` 个生产季（建立"政策前"基准）；
2. `env.apply_policy(spec.policy)` 施加所选情景政策；
3. 再运行 `policy_steps` 个生产季（观察"政策后"动态）。

每步（一个生产季）环境会核算每户收支、逐帧写入回放 SQLite（`agri_policy_agent_state` /
`agri_policy_env_state`），详见 [回放数据表](/api/data-schema)。

运行结束后产出：

- `results/<情景>/repeat_<r>/sqlite.db` —— 该次实验回放数据库
- `results/<情景>/repeat_<r>/run_meta.json` —— 该次实验元信息（情景/种子/步数/政策/参数路径）
- `results/runs_index.json` —— 所有实验的索引

## 单元测试（纯核算，无需平台/网络）

```bash
python -m unittest discover -s tests -v
```

仅测试 `agri_sandbox/economics.py` 的纯函数，可在无 `agentsociety2` 环境下运行。
