# 实验可视化 Web

在实验运行时实时观察进展、可视化村庄场景与村级指标的 Web 仪表盘。
零前端依赖（原生 HTML + SVG + JS），无需构建步骤。

## 启动

```bash
# 直接启动（默认结果目录 ./results）
python webview/server.py --results-dir results --port 8000

# 或通过完整实验脚本（默认指向正式批次 results/formal）
./run_full_experiment.sh webui

# 打开浏览器
# http://127.0.0.1:8000
```

可选参数：`--results-dir`（结果根目录）、`--config`、`--economics`、`--host`（默认 127.0.0.1）、`--port`（默认 8000）。

> 建议为正式批次使用**独立结果目录**（`results/formal`），避免与演示结果混扫。

## 功能

- **实时进展**：`experiment.run_one` 按"生产季"逐步执行，每步写 `<run_dir>/run_progress.json`；
  仪表盘每 3s 轮询 `/api/overview`，展示全部情景/重复的状态（运行中/完成/待运行）、
  阶段（基线期/政策期）、步骤进度与耗时；
- **村庄场景**：读取回放 SQLite 最新一步，以 SVG 村庄地图渲染每个农户——
  节点颜色=主作物、青色描边=已投保、▲租入 / ▼转出；点击农户查看收支详情（净收入/成本/补贴/赔付/种植/投保/流转）；
- **指标时间序列**：净收入（均值 ± 农户间标准差带）、保险覆盖率、平均种植面积、补贴支出，
  并标注"政策分界"（基线/政策期切换点）；
- **运行进度表**：全部运行一览，点击任意行切换场景。

## API

| 端点 | 说明 |
| --- | --- |
| `GET /api/overview` | 运行总览：totals + 情景聚合 + 全部 run 状态 |
| `GET /api/scenarios` | 政策情景定义（configs/policy_scenarios.json） |
| `GET /api/config` | 当前标定参数（policy_scenarios + economics） |
| `GET /api/run/{scenario}/{repeat}` | 单运行：meta + progress + 最新场景快照（env + 农户列表） |
| `GET /api/run/{scenario}/{repeat}/timeseries` | env 指标时间序列（step 级） |
| `GET /api/run/{scenario}/{repeat}/agent-series` | 农户净收入均值 ± 标准差（step 级） |

## 协作机制

- 实验端只写（`run_progress.json` / `run_meta.json` / 回放 SQLite），可视化端只读，**不干预实验进程**；
- 多进程并行运行时，每个 (情景, 重复) 独立目录，Web 自动聚合全部运行；
- 依赖：`pip install fastapi uvicorn`（已登记于 requirements.txt）。

源码位于 `webview/`（`server.py` + `static/`），详见 [webview/README.md](https://github.com/Maicarons/AgriPolicy-Sandbox/blob/main/webview/README.md)。
