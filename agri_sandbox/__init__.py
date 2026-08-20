"""农业政策沙盒（AgriPolicy Sandbox）。

基于 AgentSociety²（清华大学 AgentSociety 平台）的农业政策反事实模拟实验包。

该包实现（分层解耦）：
- 纯经济核算模型（economics）：零平台依赖的作物参数/逐户收支核算/村级汇总，可单测、可标定
- 异质农户智能体（FarmerAgent，继承自 AgentBase，行为实验模式：观察→LLM决策→ask_env提交）
- 村庄农业经济环境（AgriPolicyEnv，继承自 EnvBase）：市场观测/种植/保险/土地流转决策工具、
  政策干预工具与逐帧回放状态，参数由 economics 提供
- 实验编排（experiment）：ExperimentSpec + build_world + run_one，与 CLI 解耦
- 多情景、可重复运行的实验入口（run_experiment）
- 基于回放 SQLite 的宏观指标分析（analyze）

本代码为 AgentSociety 比赛（数智公共管理与国家治理赛道）的"农业政策沙盒"方向实践骨架。
由参赛团队维护。
"""

__version__ = "0.2.0"
__author__ = "AgriPolicy Sandbox 参赛团队"
