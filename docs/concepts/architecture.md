# 整体架构

AgriPolicy Sandbox 在 [AgentSociety²](https://agentsociety2.readthedocs.io/zh-cn/latest/index.html)
之上构建，核心设计原则是 **分层解耦**：经济模型、环境工具、农户智能体、实验编排、CLI、回放分析各自独立，
便于替换平台版本、单独复测核算公式，或在答辩时逐项审计"政策冲击 → 农户行为 → 宏观涌现"的因果链条。

## 分层视图

```text
┌─────────────────────────────────────────────────────────────┐
│                         CLI 入口                              │
│              run_experiment.py  (参数装配，薄层)               │
└───────────────────────────┬─────────────────────────────────┘
                            │  ExperimentSpec
┌───────────────────────────▼─────────────────────────────────┐
│                    实验编排 experiment.py                     │
│   ExperimentSpec · build_world · run_one · run_all            │
│   分阶段反事实：基线阶段 → apply_policy → 政策阶段            │
└───────┬───────────────────────────────┬──────────────────────┘
        │ 构造                          │ 构造
┌───────▼──────────┐            ┌────────▼─────────┐      ┌──────────────┐
│  FarmerAgent      │  ask_env   │  AgriPolicyEnv    │      │  AgentSociety │
│ (AgentBase 子类)  │ ────────▶  │  (EnvBase 子类)   │      │  (ReActRouter)│
│ 观察→LLM决策→提交 │            │  工具 + 政策 +回放 │      │              │
└──────────────────┘            └────────┬─────────┘      └──────────────┘
                                         │ 调用纯函数核算
                                ┌────────▼─────────┐
                                │  economics.py     │  零平台依赖 · 可单测
                                │  EconomicsParams  │  configs/economics.json
                                │  compute_farmer_  │  标定参数（可覆盖）
                                │  accounting /     │
                                │  village_summary  │
                                └────────┬─────────┘
                                         │ 逐帧写回放
                                ┌────────▼─────────┐
                                │  回放 SQLite       │  analyze.py 读取
                                │  agent_state /    │  → 处理效应摘要
                                │  env_state        │
                                └──────────────────┘
```

## 解耦原则

| 层 | 职责 | 依赖 |
| --- | --- | --- |
| `economics.py` | 纯经济核算模型（收支、补贴、赔付、汇总） | **零平台依赖**，仅标准库 |
| `configs/economics.json` | 标定参数 | 被 `EconomicsParams.from_file` 加载 |
| `agri_policy_env.py` | 环境工具面 + 政策状态 + 逐帧回放 | 依赖 `economics` + `agentsociety2.env` |
| `farmer_agent.py` | 农户智能体（手写 step + ask_env 提交工具） | 依赖 `agentsociety2` |
| `profiles.py` | 异质农户画像生成 | 标准库 |
| `experiment.py` | 由 spec 构造世界、运行分阶段反事实 | 依赖 `agentsociety2` + 上述各层 |
| `run_experiment.py` | 命令行解析与参数装配 | 仅依赖 `experiment` |
| `analyze.py` | 读回放库算处理效应 | 仅 `sqlite3` + 标准库 |

> **关键收益**：`economics.py` 不 import 任何 `agentsociety2` 组件，因此可在无平台、无网络的
> 环境下单独跑单元测试（`tests/test_economics.py`），保证"账怎么算"始终透明、可审计。

## 数据流

1. `profiles.make_farmer_profiles` 生成 N 个异质农户画像；
2. `build_world` 由 `ExperimentSpec` 构造 `AgriPolicyEnv` + N 个 `FarmerAgent` + `ReActRouter` + `AgentSociety`；
3. `AgentSociety.run(baseline_steps)` → 空政策运行若干季；
4. `env.apply_policy(policy)` 施加情景政策；
5. `AgentSociety.run(policy_steps)` → 政策后运行若干季；
6. 每季 `AgriPolicyEnv.step` 调用 `compute_farmer_accounting` 逐户核算，并写入回放表；
7. `analyze` 读回放库，输出处理效应摘要。

下一步：[农户智能体 FarmerAgent](/concepts/farmer-agent)。
