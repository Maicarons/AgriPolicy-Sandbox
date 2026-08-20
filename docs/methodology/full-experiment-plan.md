# 下一步完整实验计划（Full Experiment Plan）

> 版本：v1（2026-08-21）
> 前置：演示实验（8 户 × 3+3 季 × 单重复，seed=42）已完成并产出正式论文
> 状态：✅ **决策点 D1–D8 已确认（2026-08-21）**——B 档（50 户 × 8+8 季 × 10 重复）、预算无限、
> 先标定再跑正式批、8 并行夜间批、四区域全覆盖、analyze 全做；进入执行阶段

---

## 0. 目标与现状差距

演示实验证明了"政策沙盒"链路可行（5 情景全部跑通、回放可审计、论文已出），但正式论文结论受两处硬伤约束，本计划的目标就是补齐它们：

| 维度 | 演示实验（已做） | 完整实验（本计划） | 论文影响 |
| --- | --- | --- | --- |
| 农户数 | 8 | 50（推荐） | 农户级效应分布、异质性分组样本量 |
| 步数 | 3+3 季 | 8+8 季（推荐） | 年景覆盖、效应收敛 |
| 重复次数 | 1 | 10（推荐，预算自适应） | 置信区间、剔除"运气年景" |
| 经济参数 | 示意值 | 公开年鉴标定 | 绝对数值可解读、结论可外推 |
| 分析 | 均值对比 | bootstrap CI + 异质性 + 机制 + 稳健性 | 从"机制性启示"升级为"统计支持" |
| 可复现 | 记录种子 | 模型版本/温度/代码 commit/config 快照 | 全链路审计 |

**一句话定位**：以"统计效力 + 标定参数 + 全链路可复现"三个标准，跑完支撑论文正式结论的一轮完整实验。

---

## 1. 研究问题与假设的正式检验映射

| 假设 | 对应情景 | 判定指标 | 检验口径 |
| --- | --- | --- | --- |
| H1 直补提高粮食面积占比，小农更明显 | `grain_subsidy` | 粮作面积占比、Δ净收入 | 政策期 vs 基线期配对差异 + 按规模分组 |
| H2 保费补贴提高高价值作物/规模意愿 | `insurance_subsidy` | 覆盖率、种植面积、投保农户占比 | 同上 + 灾害季剔除敏感性 |
| H3 流转激励促进规模经营、可能短期离农 | `land_transfer_subsidy` | 流转参与率、转出/租入面积、规模分布 | 同上 + 转出户种植变化 |
| H4 组合兼顾安全与增收、有财政成本权衡 | `combined` | 面积/收入双指标、单位补贴增益 | 与单项政策的增量对比 |

辅助目标：

- **G1** 给出 5 情景 × 农户级处理效应的点估计与 95% 置信区间；
- **G2** 报告异质性（经营规模 / 风险态度 / 区域）下的效应差异；
- **G3** 完成机制质性编码（"风险预期路径" vs "收益比较路径"）；
- **G4** 输出成本效益：单位补贴的净收入增益与 Pareto 前沿。

---

## 2. 实验规模设计

### 2.1 三档配置（推荐 B，最终按 §6 预算实测锁定）

| 配置 | 农户 | 步数(基+政) | 重复 r | 单情景运行数 | 总 LLM 决策调用 | 估计墙钟（串行/8 并行） | 用途 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A 最小 | 50 | 6+6 | 3 | 15 | 9,000 | 2.1 天 / 6.3 小时 | 预算紧张兜底 |
| **B 推荐** | **50** | **8+8** | **10** | 50 | 40,000 | 11.7 天 / 1.5 天 | 正式结论主配置 |
| C 完整 | 80 | 10+10 | 15 | 75 | 120,000 | 35 天 / 4.4 天 | 追求功效上限 |

> 调用次数公式：`n_agents × (baseline+policy) × 情景数 × repeats`。
> 墙钟依据：演示实验实测 **≈25 秒/户季**（8 户×6 季 ≈ 20 分钟；LLM 决策延迟主导）。

### 2.2 统计功效论证（为什么 10 次重复）

- 处理效应 $\tau = \bar y^{policy} - \bar y^{baseline}$，置信区间半宽 ≈ $t \cdot s/\sqrt{r}$（r=情景重复数，s=重复间效应标准差）；
- 演示实验农户级效应方差较大（保险情景赔付受年景驱动），r=3 时 CI 宽度约为 r=10 的 1.8 倍，无法区分"政策效应"与"年景运气"；
- **r=10** 时重复间均值可给出可用的 bootstrap CI，且允许剔除 1–2 个极端年景重复后做敏感性（仍剩 8–9 个）；
- 农户数 n=50 保证按规模/风险分组后每组 ≥15 户，分组均值稳定。

### 2.3 随机化设计

- 每 (情景, 重复) 用 `seed = 42 + repeat`（沿用 `ExperimentSpec.effective_seed()`），保证跨重复冲击序列不同、可复现；
- 同一情景的所有重复共用同一批画像分布（`make_farmer_profiles(n, seed)`），隔离"画像抽样"与"政策效应"；
- 基线阶段空政策、政策阶段 `apply_policy` 施加，全链路 `phased=True`；
- 保留 `start_date=2025-01-01`；如需跨年景，可在敏感性中改用多 `start_date` 变体。

---

## 3. 性能与并行调度（关键约束）

演示实验为**顺序执行**（每季逐户 LLM 决策），规模放大后墙钟是最大瓶颈，必须实测基准 + 并行化。

### 3.1 计时基准（门控前置）

正式批次开始前，先跑一次 `10 户 × 2+2 季 × 1 重复` 冒烟，记录：

- 每户季平均耗时（预期 ~25s，实测为准）；
- 单次 LLM 调用的输入/输出 token 数（用于 §6 成本）；
- API 是否限流（连续调用是否有退避/429）。

### 3.2 并行调度方案

- **多进程并行**：每进程运行一个 (情景, 重复)（`python -m agri_sandbox.run_experiment --scenario X --repeats 1 --results-dir results/formal`），各 run 写入独立 `run_dir`（SQLite 互不冲突，可安全并行）；
- 并行度建议 4–8（视 API 限流与机器内存；50 户单 run 内存开销小，瓶颈在 LLM API 速率）；
- 用 `scripts/run_parallel.py`（或 shell `xargs -P`）调度，输出 `runs_index.json`；
- **断点续跑**：重启时扫描 `results/formal/**/run_meta.json`，已完成的 (情景,重复) 自动跳过（避免重复花钱）。

### 3.3 时间预算

- 配置 B：50 运行 × 5.6 小时 ≈ 280 小时串行；8 并行 ≈ 35 小时（约 1.5 天）；
- 配置 A：15 运行 ≈ 84 小时串行 / ~10 小时并行；
- 建议安排 2 个夜间批（每晚 8 并行 × ~10 小时）完成 B 配置。

---

## 4. 参数标定方案（替换示意值）

### 4.1 数据来源清单

| 参数组 | 建议来源 | 备注 |
| --- | --- | --- |
| 作物单产 yield | 《全国农产品成本收益资料汇编》/《中国农村统计年鉴》 | 取近 3 年均值，标注年份 |
| 收购价 price | 国家发改委农产品价格监测 / 主产区批发价 | 用年度均价，注明价格口径 |
| 物化成本 cost | 《全国农产品成本收益资料汇编》 | 物质与服务费用 |
| 保费 premium / 保产基准 insured_yield | 各省农业保险条款（保额×费率） | 区分主粮与经济作物 |
| 地租 rent_in/out | 《中国农村经营管理情况年报》流转均价 | 分省/分区域 |
| 灾害阈值与赔付比例 | 保险条款 + 历年气象灾害频率 | 对应 `disaster_threshold` / `insurance_payout_ratio` |
| 价格/天气冲击参数 | 历史价格波动率、气象站点年际波动 | 对应 `*_shock_*` 参数 |

### 4.2 标定流程

1. 收集 → 清洗 → 按作物/区域对齐（华北/东北/长江中游/西南，与画像区域一致）；
2. 映射到 `configs/economics.json`（字段名见 §4.3），保留一份 `configs/economics.calibrated.json` 与原始来源表（`docs/calibration-sources.csv`）；
3. 敏感性分析：单参数 ±20% 扰动，观察处理效应方向是否稳健（纳入 §8 稳健性）。

### 4.3 字段映射（对齐 `agri_sandbox/economics.py`）

```
crops.<crop>.yield / price / cost / premium / insured_yield
rent_in_per_mu / rent_out_per_mu
disaster_threshold / insurance_payout_ratio
price_shock_bounds / price_shock_sigma
weather_shock_bounds / weather_shock_mu / weather_shock_sigma
```

> 边界：标定目标是把"绝对数值"变得可解读；若数据不全，至少完成主粮（小麦/玉米/水稻/大豆）四项核心参数，经济作物（蔬菜）可保留行业参考值并在论文注明。

---

## 5. 实验矩阵与执行门控

### 5.1 实验矩阵

| 批次 | 情景 | 重复 | 种子 | 前置条件 |
| --- | --- | --- | --- | --- |
| 门 1 连通性 | `baseline` | 1 | 42 | `.env` 凭证可用 |
| 门 2 冒烟 | `baseline` + `combined` | 1 | 42 | 门 1 通过；记录计时/token 基准 |
| 门 3 正式 | 全部 5 情景 | r（自适应） | 42..41+r | 门 2 基准合理 + 预算确认 |

### 5.2 命令清单

```bash
# 门 1：连通性自检
python -m agri_sandbox.run_experiment --scenario baseline --agents 3 \
    --baseline-steps 1 --policy-steps 1 --repeats 1 --results-dir results/smoke

# 门 2：冒烟批次（计时 + token 基准）
python -m agri_sandbox.run_experiment --scenario baseline --agents 10 \
    --baseline-steps 2 --policy-steps 2 --repeats 1 --results-dir results/smoke
python -m agri_sandbox.run_experiment --scenario combined  --agents 10 \
    --baseline-steps 2 --policy-steps 2 --repeats 1 --results-dir results/smoke

# 门 3：正式批次（推荐 B：50 户 × 8+8 季 × 10 重复；并行调度见 §3.2）
python -m agri_sandbox.run_experiment --all --repeats 10 --results-dir results/formal

# 分析
python -m agri_sandbox.analyze --results-dir results/formal --out results/formal
```

### 5.3 质量门控（每批执行后检查）

- [ ] `runs_index.json` 数量 = 情景 × 重复，无缺失；
- [ ] 每个 `run_meta.json` 含模型版本/温度/commit/config 快照（见 §7）；
- [ ] 抽样 2 个 run 检查回放表 `n_planting_farmers`、净收入分布无异常（如 0 种植户占比过高）；
- [ ] `analyze` 输出无 `-`（缺数据）单元格。

---

## 6. 预算与 LLM 成本模型

### 6.1 调用量与 token 估算

| 配置 | 调用次数 | 输入 token（≈3k/次） | 输出 token（≈0.4k/次） |
| --- | --- | --- | --- |
| A | 9,000 | 27M | 3.6M |
| B | 40,000 | 120M | 16M |
| C | 120,000 | 360M | 48M |

### 6.2 单价三档与总额（对照 200 元额度）

| 单价（元/百万 token，输入侧） | A | B | C |
| --- | --- | --- | --- |
| 0.3 | ~9 元 | ~41 元 | ~122 元 |
| 0.8 | ~24 元 | ~109 元 | ~326 元 |
| 1.5 | ~45 元 | ~204 元 | ~612 元 |

> 估算以输入侧为主（输出按约 1/3 计），实际以门 2 冒烟实测的 token 与单价为准。

### 6.3 预算自适应决策点（重要）

1. 门 2 冒烟后，实测"单次调用 token 数 + 单价"，反推 200 元额度可支撑的调用次数上限；
2. 若上限 ≥40,000 → 按配置 B 执行；
3. 若上限仅 15,000–40,000 → 降为 B-：50 户 × 8+8 季 × 4–8 重复（按上限取整）；
4. 若上限 <15,000 → 降为配置 A 并优先保 `combined` 与 `insurance_subsidy` 两个关键情景；
5. 全程保留 ~15% 预算用于重试/异常。

### 6.4 降本手段

- 模板模式（`ask_env(template_mode=True)`）已启用，省去工具推理 token；
- 精简 `observe_market` 输出（只保留农户可用作物）可再降输入 token；
- 避免高频重试：LLM 输出解析失败次数应统计，若 >5% 需先修 prompt 再跑正式批。

---

## 7. 数据管理与产物规范

### 7.1 目录结构

```
results/formal/
├── runs_index.json              # 全部运行索引（含扩展元信息）
├── summary.json / summary.csv   # analyze 输出（基础处理效应）
├── summary_full.json / summary_full.csv   # analyze_full 输出（bootstrap CI 等，见 §8）
├── <scenario>/repeat_<r>/
│   ├── sqlite.db                # 回放（agent_state / env_state / profile）
│   ├── run_meta.json            # 元信息（增强版：model / code_commit / 步数 / 政策）
│   ├── run_progress.json        # 运行进度（运行中每季实时更新，供 webview）
│   ├── config_snapshot.json     # 政策 + 生效标定参数快照
│   └── run.log                  # 运行日志（脚本 full 模式写入）
```

### 7.2 run_meta 增强（已实现于 `experiment.run_one`）

在原有字段（scenario/repeat/seed/steps/policy/economics_path/run_dir/finished_at）基础上，`run_one` 已增加：

```json
{
  "model": "mimo-v2.5",          // 已实现：_model_name() 读取 NANO/LLM 模型 env
  "code_commit": "<git rev-parse HEAD>",  // 已实现：_code_commit()
  "config_snapshot": "config_snapshot.json"  // 已实现：run_dir 内政策+标定参数快照
}
```

> 说明：`temperature` / `sec_per_agent_step` / `llm_calls` 暂未写入 meta（平台使用默认温度；耗时与调用数可在冒烟批次后由工具补充），如需可扩展 `run_one`。

另外，`run_one` 现按"生产季"逐步执行并写 `run_progress.json`（scenario/repeat/status/phase/step/step_total/started_at/updated_at），供 `webview/` 实时可视化。

### 7.3 回放审计（已实现于 `agri_sandbox/audit_replay.py`）

```bash
python -m agri_sandbox.audit_replay --results-dir results/formal   # 有异常退出码 1，可接入脚本门控
```

检查项：回放表行数完整性（agent_state = 农户数 × 总季数；env_state = 总季数）、净收入 ≤ 0 占比、
`planted_area=0` 占比、投保面积 > 种植面积占比、`n_planting_farmers=0` 季度数；异常占比 > 20% 标记 FAIL。

---

## 8. 分析方案升级

分析实现（**已实现于 `agri_sandbox/analyze_full.py`**，演示数据已验证）：

```bash
python -m agri_sandbox.analyze_full --results-dir results/formal --bootstrap 2000
# 输出 <out>/summary_full.json / summary_full.csv，并打印 Markdown 摘要
```

| 分析 | 方法 | 输出 |
| --- | --- | --- |
| 主效应 | 分情景 基线 vs 政策 配对差异 + **bootstrap 95% CI**（农户级抽样，b 可调） | 表：Δ、Δ%、CI |
| 异质性 | 按经营规模分组（`core_agent_profile.profile.scale`：小农户/中农户/规模经营户） | 分组 Δ 与 n |
| 机制 | 决策日志质性编码："风险预期"（保险/灾害/风险/减产/赔付/亏）与"收益比较"（价格/补贴/成本/收益/收入/划算）关键词频次；日志缺失时降级为无数据 | 机制编码表 |
| 稳健性 | 多重复（r>2）时剔除偏离中位数最大的重复后重算 | 剔除前后 Δ 对比 |
| 成本效益 | 单位补贴净收入增益 = 全村 Δ净收入 / 政策期补贴支出；粮食安全（种植面积）—增收 Pareto 点 | 效益表 + Pareto 数据 |

---

## 9. 质量与复现保障

- **固定种子**：`seed = 42 + repeat`，跨运行可复现；
- **模型与温度**：`.env` 锁定 `AGENTSOCIETY_NANO_LLM_MODEL`（mimo-v2.5），统一温度（建议 0.2），写入 run_meta；
- **代码版本**：正式批次前记录 `git rev-parse HEAD`，每批写入 run_meta；
- **config 快照**：每 run 写 `run_dir/config_snapshot.json`（政策 + 生效标定参数，`run_one` 自动生成）；
- **复现清单**（交付时附）：`requirements.txt` 版本、`.env.example`、种子方案、模型/温度、代码 commit、config 快照、数据提取脚本 `paper/result/extract_data.py`。

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| API 额度超支 | 实验中断 | §6 预算自适应 + 15% 预留 + 断点续跑 |
| 墙钟过长 | 赶不上节点 | 8 并行夜间批 + 配置降档（A/B-） |
| LLM 输出格式异常率升高 | 决策失效、数据污染 | 门 2 统计解析失败率，>5% 先修 prompt |
| 年景运气主导保险效应 | 结论误导 | r≥10 + 剔除极端重复的稳健性 |
| 平台版本升级破坏 API | 无法运行 | 锁定 `agentsociety2` 版本，记录于 requirements |
| 断点重启重复花钱 | 预算浪费 | 扫描 run_meta 自动跳过已完成运行 |
| 标定数据口径不一 | 数值偏差 | 来源表登记 + 论文注明口径与年份 |

---

## 11. 时间表（对齐比赛节点）

| 阶段 | 时间 | 任务 | 里程碑 |
| --- | --- | --- | --- |
| 定题与组队 | 8/21–8/31 | 确认决策点（§13）；标定数据收集启动；组队分工 | 决策点确认 |
| 原型与标定 | 9/1–9/14 | 门 1/门 2 冒烟；标定完成（economics.calibrated.json） | **初筛 9/15 前提交**（含完整实验设计） |
| 正式实验 | 9/10–9/22 | 门 3 正式批次（并行调度）；analyze 升级 | runs_index + summary_full |
| 实验与写作 | 9/16–9/30 | bootstrap CI / 异质性 / 机制编码；论文初稿（答疑 9/17） | 论文 v2 初稿 |
| 迭代完善 | 10/1–10/17 | 稳健性、参数敏感性、论文打磨 | 论文 v2 定稿 |
| 演示准备 | 10/18–10/24 | 海报 / 交互演示（replay 可视化） | 演示产物 |
| 现场评审 | 10/25 | 答辩 | 完成 |

> 说明：正式实验与论文写作并行（9/10–9/30），先出"有效数据"再补写结果章节，避免最后一刻集中跑批。

---

## 12. 验收标准（Definition of Done）

1. 每情景有效重复 ≥3（推荐 10），`runs_index.json` 完整、无缺失；
2. `configs/economics.calibrated.json` 交付，含来源表与口径说明；
3. `analyze` 输出含 bootstrap 95% CI 的 `summary_full`（json+csv）；
4. 异质性表、机制编码表、稳健性表齐备；
5. 论文 v2 结果/讨论章节更新为正式实验数据，局限部分按新规模改写；
6. 复现清单（§9）齐全，第三方可据此重跑。

---

## 13. 待确认决策点（执行前需用户拍板）

| # | 决策点 | 选项 |
| --- | --- | --- |
| D1 | 规模档位 | A 最小 / **B 推荐（50 户×8+8 季×10 重复）** / C 完整 |
| D2 | 预算上限 | 200 元额度内 / 可追加 |
| D3 | 是否先做参数标定 | 先标定再跑正式批 / 先用示意值跑、标定作二期 |
| D4 | 并行度与跑批时段 | 4 / 8 并行；白天 / 夜间批 |
| D5 | 区域范围 | 四区域全覆盖 / 单区域（如华北）先做 |
| D6 | 是否升级 analyze（bootstrap/异质性/机制） | 本计划范围全做 / 只做主效应+CI |
| D7 | 队伍分工 | 需填写：数据标定 / 实验运行 / 分析 / 论文 |
| D8 | 计划落档 | 是否同步进 `docs/` 文档站（新增「实验计划」页） |
