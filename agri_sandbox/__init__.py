"""农业政策沙盒（AgriPolicy Sandbox）。

基于 AgentSociety²（清华大学 AgentSociety 平台）的农业政策反事实模拟实验包。

该包实现：
- 异质农户智能体（FarmerAgent，继承自 PersonAgent）
- 村庄农业经济环境（AgriPolicyEnv，继承自 EnvBase），含市场观测、种植/保险/土地流转决策工具、
  政策干预工具与逐帧回放状态
- 多情景、可重复运行的实验编排（run_experiment）
- 基于回放 SQLite 的宏观指标分析（analyze）

本代码为 AgentSociety 比赛（数智公共管理与国家治理赛道）的"农业政策沙盒"方向实践骨架。
由参赛团队维护。
"""

__version__ = "0.1.0"
__author__ = "AgriPolicy Sandbox 参赛团队"
