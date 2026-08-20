# AgriPolicy Sandbox · 实验可视化 Web

在实验运行时实时观察进展、可视化村庄场景与村级指标的 Web 仪表盘（零前端依赖：原生 HTML + SVG + JS）。

## 功能

- **实时进展**：`agri_sandbox/experiment.py` 现在按"生产季"逐步执行（等价于一次跑多步，见 `_run_steps`），
  每步写入 `<run_dir>/run_progress.json`；仪表盘每 3s 轮询 `/api/overview` 展示全部情景/重复的
  状态（运行中/完成/待运行）、阶段（基线期/政策期）、步骤进度、耗时；
- **村庄场景可视化**：选中某个运行后，读取回放 SQLite 最新一步，以 SVG 村庄地图渲染每个农户——
  节点颜色=主作物、青色描边=已投保、▲=租入、▼=转出，点击农户查看收支详情；
- **村级指标时间序列**：净收入（均值±农户间标准差带）、保险覆盖率、平均种植面积、补贴支出，
  并标注"政策分界"（基线/政策期切换点）；
- **运行进度表**：全部运行一览，点击任意行切换场景。

## 安装与启动

```bash
pip install fastapi uvicorn

# 默认使用 ./results（可切到正式实验目录）
python webview/server.py --results-dir results --port 8000
# 浏览器打开 http://127.0.0.1:8000
```

可选参数：`--results-dir`（结果根目录，默认 `results`）、`--config`、`--economics`、
`--host`（默认 127.0.0.1）、`--port`（默认 8000）。

## API

| 端点 | 说明 |
| --- | --- |
| `GET /api/overview` | 运行总览：totals + 情景聚合 + 全部 run 状态 |
| `GET /api/scenarios` | 政策情景定义（configs/policy_scenarios.json） |
| `GET /api/config` | 当前标定参数（policy_scenarios + economics） |
| `GET /api/run/{scenario}/{repeat}` | 单运行：meta + progress + 最新场景快照（env + 农户列表） |
| `GET /api/run/{scenario}/{repeat}/timeseries` | env 指标时间序列（step 级） |
| `GET /api/run/{scenario}/{repeat}/agent-series` | 农户净收入均值±标准差（step 级） |

## 协作机制

- 实验端：`agri_sandbox/experiment.py` 的 `run_one` 每步写 `run_progress.json`
  （scenario/repeat/status/phase/step/step_total/started_at/updated_at），结束写 `run_meta.json` 与 config 快照；
- 可视化端：只读 `results/**/` 下的 progress/meta/回放 SQLite，**不干预实验进程**；
- 并行运行：每个 (情景, 重复) 独立目录，多进程并行时 Web 自动聚合全部运行。

## 目录结构

```
webview/
├── server.py          # FastAPI 后端（API + 静态服务）
├── static/
│   ├── index.html     # 仪表盘页面
│   ├── style.css      # 暗色主题
│   └── app.js         # 渲染逻辑（SVG 村庄 + 手绘折线图 + 轮询）
└── README.md
```
