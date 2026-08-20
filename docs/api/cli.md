# API · 命令行 `CLI`

## `run_experiment`

运行入口：`python -m agri_sandbox.run_experiment`

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--config PATH` | `configs/policy_scenarios.json` | 情景配置文件 |
| `--scenario KEY` | 无 | 单情景（如 `combined`） |
| `--all` | 关 | 运行全部情景 |
| `--repeats N` | 配置默认(3) | 重复次数 |
| `--agents N` | 配置默认(50) | 农户数 |
| `--baseline-steps N` | 配置默认(8) | 阶段一步数 |
| `--policy-steps N` | 配置默认(8) | 阶段二步数 |
| `--seed N` | 配置默认(42) | 基础随机种子 |
| `--economics PATH` | `configs/economics.json` | 标定参数文件 |
| `--results-dir PATH` | `./results` | 结果根目录 |
| `--no-phased` | 关 | 政策从第一步即生效（非分阶段） |

若既不传 `--all` 也不传 `--scenario`，默认只跑 `baseline` 一次作为连通性自检。

**产物**：`results/<情景>/repeat_<r>/sqlite.db`、`run_meta.json`，以及 `results/runs_index.json`。

## `analyze`

分析入口：`python -m agri_sandbox.analyze`

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--results-dir PATH` | `./results` | 结果根目录（递归查找 `**/run_meta.json`） |
| `--baseline-steps N` | 取 `run_meta.json` | 覆盖基线阶段步数 |
| `--out PATH` | 同 `--results-dir` | 摘要输出目录 |

**产物**：`summary.json`、`summary.csv`，并打印 Markdown 摘要表（基线 vs 政策 + 处理效应 Δ / 相对变化 + 农户级净收入效应均值 ± 标准差）。

## `unittest`（纯核算单测）

```bash
python -m unittest discover -s tests -v
```

仅测试 `agri_sandbox/economics.py` 纯函数，无需平台 / 网络。

## 退出码

- `run_experiment`：未知情景键 → 退出码 2（并提示可用情景）；
- `analyze`：结果目录不存在 → 退出码 2。

相关：[运行实验](/guide/running-experiments) · [回放分析](/guide/analysis)。
