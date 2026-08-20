---
layout: home

hero:
  name: AgriPolicy Sandbox
  text: 农业政策反事实模拟沙盒
  tagline: 把"农户"做成带真实偏好的 LLM 智能体，在可干预的村庄农业经济环境中估计政策处理效应
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/getting-started
    - theme: alt
      text: 研究方法
      link: /methodology/
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/Maicarons/AgriPolicy-Sandbox

features:
  - title: 可解释的经济核算
    details: 收支核算集中在 economics.py 的纯函数 + configs/economics.json 标定参数，零平台依赖、有单元测试，换数据不改代码，答辩可逐项审计。
    icon: 📊
  - title: 分层解耦架构
    details: 经济模型 / 环境工具 / 农户智能体 / 实验编排 / CLI / 回放分析各自独立，便于替换平台版本或单独复测核算公式。
    icon: 🧩
  - title: 分阶段反事实识别
    details: 同一批农户先跑基线（空政策）、再施加情景政策，前后两阶段差异即为政策处理效应估计，个体异质性被同批样本控制。
    icon: 🔁
  - title: 全链路可复现
    details: 固定随机种子、分情景分重复落库回放 SQLite、记录模型版本与温度；analyze 直接读库输出处理效应摘要。
    icon: 🔒
---

## 这是什么

**AgriPolicy Sandbox** 是一个面向 **数智公共管理与国家治理** 赛道的科研沙盒原型，基于
[AgentSociety²](https://agentsociety2.readthedocs.io/zh-cn/latest/index.html)（清华大学 · 计算社会科学与国家治理实验室）
将"农户"建模为具有真实偏好、风险态度与家庭约束的 LLM 智能体，放在一个可标定的村庄农业经济环境里，
通过**干预 API** 施加补贴、农业保险保费补贴、土地流转补贴等政策冲击，做**反事实政策评估**：
同一批农户在"政策前 / 政策后"的净收入、保险参与、种植结构与土地流转变化，即为政策的处理效应估计。

> 结论定位为"机制性启示"而非"因果估计"——模拟是受控实验，不等于真实政策效果。

## 最快上手

```bash
pip install -r requirements.txt
cp .env.example .env          # 填入 AGENTSOCIETY_LLM_API_KEY 等
python -m agri_sandbox.run_experiment --all
python -m agri_sandbox.analyze
```

详细步骤见 [快速开始](/guide/getting-started)。
