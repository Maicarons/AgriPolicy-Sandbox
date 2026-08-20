"""回放分析：从实验结果 SQLite 中计算政策处理效应。

运行方式：
    python -m agri_sandbox.analyze --results-dir results
    python -m agri_sandbox.analyze --results-dir results --baseline-steps 8

对每个 (情景) 聚合多个重复实验，分"基线阶段"与"政策阶段"计算宏观指标：
- 平均家庭净收入（元/季）
- 平均补贴收入（元/季）
- 保险覆盖率
- 平均种植面积（亩）
- 全村补贴支出（元/季）
并给出 政策 − 基线 的处理效应（绝对差与相对差），以及农户级净收入处理效应的均值与离散度。

输出：<results-dir>/summary.csv、summary.json，并打印 Markdown 表格。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from pathlib import Path

ENV_TABLE = "agri_policy_env_state"
AGENT_TABLE = "agri_policy_agent_state"


def _query(db_path: Path, sql: str) -> list[dict]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def _phase_means(rows: list[dict], baseline_steps: int) -> dict:
    """把 env_state 行按阶段拆分并求均值。"""
    base = [r for r in rows if r["step"] <= baseline_steps]
    pol = [r for r in rows if r["step"] > baseline_steps]

    def avg(key: str, subset: list[dict]) -> float | None:
        vals = [r[key] for r in subset if r.get(key) is not None]
        return statistics.fmean(vals) if vals else None

    return {
        "baseline": {k: avg(k, base) for k in (
            "avg_net_income", "avg_subsidy_income", "insurance_coverage_rate",
            "avg_planted_area", "total_subsidy", "weather_shock",
        )},
        "policy": {k: avg(k, pol) for k in (
            "avg_net_income", "avg_subsidy_income", "insurance_coverage_rate",
            "avg_planted_area", "total_subsidy", "weather_shock",
        )},
        "n_baseline": len(base),
        "n_policy": len(pol),
    }


def _agent_treatment(db_path: Path, baseline_steps: int) -> list[float]:
    """农户级净收入处理效应（政策期均值 − 基线期均值），返回所有农户的列表。"""
    rows = _query(
        db_path,
        f"SELECT agent_id, step, net_income FROM {AGENT_TABLE} ORDER BY agent_id, step",
    )
    by_agent: dict[int, dict[str, list[float]]] = {}
    for r in rows:
        aid = r["agent_id"]
        by_agent.setdefault(aid, {"base": [], "pol": []})
        if r["step"] <= baseline_steps:
            by_agent[aid]["base"].append(r["net_income"])
        else:
            by_agent[aid]["pol"].append(r["net_income"])
    effects: list[float] = []
    for v in by_agent.values():
        if v["base"] and v["pol"]:
            effects.append(statistics.fmean(v["pol"]) - statistics.fmean(v["base"]))
    return effects


def analyze(results_dir: Path, baseline_steps_override: int | None) -> dict:
    runs: list[dict] = []
    for meta_path in sorted(results_dir.glob("**/run_meta.json")):
        run_dir = meta_path.parent
        db = run_dir / "sqlite.db"
        if not db.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        bs = baseline_steps_override if baseline_steps_override is not None else meta.get("baseline_steps", 8)
        env_rows = _query(db, f"SELECT * FROM {ENV_TABLE} ORDER BY step")
        phases = _phase_means(env_rows, bs)
        agent_effects = _agent_treatment(db, bs)
        runs.append({
            "scenario_key": meta["scenario_key"],
            "scenario_label": meta.get("scenario_label"),
            "repeat": meta.get("repeat"),
            "phases": phases,
            "agent_effects": agent_effects,
        })

    # 按情景聚合
    by_scenario: dict[str, list[dict]] = {}
    for r in runs:
        by_scenario.setdefault(r["scenario_key"], []).append(r)

    summary: dict[str, Any] = {"scenarios": []}
    for sk, items in by_scenario.items():
        def agg(key: str) -> dict:
            base_vals = [it["phases"]["baseline"][key] for it in items if it["phases"]["baseline"][key] is not None]
            pol_vals = [it["phases"]["policy"][key] for it in items if it["phases"]["policy"][key] is not None]
            b = statistics.fmean(base_vals) if base_vals else None
            p = statistics.fmean(pol_vals) if pol_vals else None
            if b is not None and p is not None and b != 0:
                pct = (p - b) / abs(b) * 100.0
            else:
                pct = None
            return {"baseline": b, "policy": p, "delta": (p - b if (b is not None and p is not None) else None),
                    "delta_pct": pct}

        effects = [e for it in items for e in it["agent_effects"]]
        scenario_summary = {
            "scenario_key": sk,
            "scenario_label": items[0].get("scenario_label"),
            "n_runs": len(items),
            "avg_net_income": agg("avg_net_income"),
            "avg_subsidy_income": agg("avg_subsidy_income"),
            "insurance_coverage_rate": agg("insurance_coverage_rate"),
            "avg_planted_area": agg("avg_planted_area"),
            "total_subsidy": agg("total_subsidy"),
            "agent_net_effect_mean": statistics.fmean(effects) if effects else None,
            "agent_net_effect_std": statistics.pstdev(effects) if effects else None,
            "n_agents_with_effect": len(effects),
        }
        summary["scenarios"].append(scenario_summary)
    return summary


def _print_markdown(summary: dict) -> None:
    print("\n# 农业政策沙盒 · 处理效应摘要\n")
    for s in summary["scenarios"]:
        print(f"## {s['scenario_label']}（{s['scenario_key']}，{s['n_runs']} 次重复）\n")
        print("| 指标 | 基线 | 政策 | 处理效应(Δ) | 相对变化 |")
        print("|---|---|---|---|---|")
        rows = [
            ("平均家庭净收入(元/季)", "avg_net_income"),
            ("平均补贴收入(元/季)", "avg_subsidy_income"),
            ("保险覆盖率", "insurance_coverage_rate"),
            ("平均种植面积(亩)", "avg_planted_area"),
            ("全村补贴支出(元/季)", "total_subsidy"),
        ]
        for label, key in rows:
            m = s[key]
            b = m["baseline"]; p = m["policy"]; d = m["delta"]; pc = m["delta_pct"]
            b_s = f"{b:.2f}" if b is not None else "-"
            p_s = f"{p:.2f}" if p is not None else "-"
            d_s = f"{d:+.2f}" if d is not None else "-"
            pc_s = f"{pc:+.1f}%" if pc is not None else "-"
            print(f"| {label} | {b_s} | {p_s} | {d_s} | {pc_s} |")
        ae = s["agent_net_effect_mean"]; ae_s = s["agent_net_effect_std"]
        if ae is not None:
            print(f"\n农户级净收入处理效应：均值 {ae:+.2f} 元/季，标准差 {ae_s:.2f}（n={s['n_agents_with_effect']}）")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="农业政策沙盒回放分析")
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--baseline-steps", type=int, default=None,
                        help="覆盖 run_meta.json 中的基线步数")
    parser.add_argument("--out", type=Path, default=None,
                        help="输出目录（默认与 results-dir 相同）")
    args = parser.parse_args()

    if not args.results_dir.exists():
        sys.stderr.write(f"结果目录不存在：{args.results_dir}\n")
        raise SystemExit(2)

    summary = analyze(args.results_dir, args.baseline_steps)
    out = args.out or args.results_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # CSV
    import csv
    csv_path = out / "summary.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "scenario_key", "scenario_label", "n_runs",
            "net_income_baseline", "net_income_policy", "net_income_delta", "net_income_delta_pct",
            "subsidy_baseline", "subsidy_policy",
            "coverage_baseline", "coverage_policy",
            "planted_baseline", "planted_policy",
            "agent_effect_mean", "agent_effect_std",
        ])
        for s in summary["scenarios"]:
            ni = s["avg_net_income"]; su = s["avg_subsidy_income"]
            co = s["insurance_coverage_rate"]; pl = s["avg_planted_area"]
            w.writerow([
                s["scenario_key"], s["scenario_label"], s["n_runs"],
                ni["baseline"], ni["policy"], ni["delta"],
                (f"{ni['delta_pct']:.2f}" if ni["delta_pct"] is not None else ""),
                su["baseline"], su["policy"],
                co["baseline"], co["policy"],
                pl["baseline"], pl["policy"],
                s["agent_net_effect_mean"], s["agent_net_effect_std"],
            ])

    _print_markdown(summary)
    print(f"输出已写入：{out / 'summary.json'}、{csv_path}")


if __name__ == "__main__":
    main()
