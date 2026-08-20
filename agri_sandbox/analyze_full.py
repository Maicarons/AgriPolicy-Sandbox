"""完整实验分析（对应 full-experiment-plan.md §8）：bootstrap CI / 异质性 / 机制编码 / 稳健性 / 成本效益。

在 ``analyze.py``（均值/处理效应）基础上提供统计升级，输出 ``summary_full.json`` / ``summary_full.csv``：

- **主效应**：分情景 基线 vs 政策 配对差异 + **农户级 bootstrap 95% CI**（以农户为抽样单元；
  单重复亦可计算；多重复时重复数 r 同样记录，供重复级推断）；
- **异质性**：按经营规模（小农户/中农户/规模经营户，来自 ``core_agent_profile.profile.scale``）分组；
- **机制编码**：扫描 run 目录下的决策日志/工作区文本，统计"风险预期"（保险/灾害/风险/减产/赔付/亏）与
  "收益比较"（价格/补贴/成本/收益/收入/划算）关键词频次（日志缺失时降级为无数据）；
- **稳健性**：多重复（r>1）时剔除偏离中位数的极端重复后重算效应；
- **成本效益**：单位补贴净收入增益 = 全村 Δ净收入 / 政策期补贴支出；粮食安全（种植面积）—增收 Pareto 点。

用法：
    python -m agri_sandbox.analyze_full --results-dir results --out results
    python -m agri_sandbox.analyze_full --results-dir results/formal --bootstrap 2000
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

AGENT_TABLE = "agri_policy_agent_state"
ENV_TABLE = "agri_policy_env_state"


def _query(db_path: Path, sql: str) -> list[dict]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql).fetchall()]
    finally:
        con.close()


def _load_meta(run_dir: Path) -> dict:
    p = run_dir / "run_meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _scale_map(db: Path) -> dict[int, str]:
    """agent_id -> 经营规模档位。core_agent_profile.id 与 agent_state.agent_id 同序对齐。"""
    out: dict[int, str] = {}
    try:
        for r in _query(db, "SELECT id, profile FROM core_agent_profile"):
            p = json.loads(r.get("profile") or "{}")
            out[int(r["id"])] = str(p.get("scale") or p.get("farm_scale") or "未知")
    except Exception:
        pass
    return out


def _farmer_effects(db: Path, bs: int) -> list[dict]:
    """每户的处理效应：政策期均值 − 基线期均值（net_income 等）。"""
    rows = _query(db, f"SELECT agent_id, step, net_income, planted_area_mu FROM {AGENT_TABLE} ORDER BY agent_id, step")
    by: dict[int, dict[str, list]] = {}
    for r in rows:
        a = int(r["agent_id"])
        d = by.setdefault(a, {"base": [], "pol": []})
        (d["base"] if int(r["step"]) <= bs else d["pol"]).append(float(r["net_income"]))
    out = []
    for a, d in by.items():
        if d["base"] and d["pol"]:
            out.append({
                "agent_id": a,
                "delta_net": statistics.fmean(d["pol"]) - statistics.fmean(d["base"]),
            })
    return out


def _phase_means(db: Path, bs: int, table: str, keys: list[str]) -> tuple[dict, dict]:
    rows = _query(db, f"SELECT * FROM {table} ORDER BY step")
    base = [r for r in rows if int(r["step"]) <= bs]
    pol = [r for r in rows if int(r["step"]) > bs]

    def avg(sub: list[dict]) -> dict:
        return {k: (statistics.fmean([float(r[k]) for r in sub if r.get(k) is not None])
                    if any(r.get(k) is not None for r in sub) else None)
                for k in keys}

    return avg(base), avg(pol)


def _bootstrap_ci(values: list[float], b: int, seed: int = 2026) -> tuple[float | None, float | None]:
    """以抽样单元（农户）做有放回 bootstrap，返回 95% CI。"""
    if len(values) < 2:
        return None, None
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(b):
        sample = [rng.choice(values) for _ in range(n)]
        means.append(statistics.fmean(sample))
    q = statistics.quantiles(means, n=40)  # 2.5% / 97.5%
    return q[0], q[38]


def _mechanism_counts(run_dir: Path) -> dict | None:
    """机制质性编码：决策日志/工作区文本关键词频次。无日志返回 None。"""
    texts: list[str] = []
    for pat in ("**/workspace/**/*.txt", "**/agents/**/*.txt", "**/*decision*.json",
                "**/logs/**/*.txt", "**/workspace/**/*.jsonl"):
        for f in run_dir.glob(pat):
            try:
                texts.append(Path(f).read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    if not texts:
        return None
    body = " ".join(texts)
    risk_kw = ["保险", "灾害", "风险", "减产", "赔付", "亏"]
    gain_kw = ["价格", "补贴", "成本", "收益", "收入", "划算"]
    return {
        "risk_hits": sum(body.count(k) for k in risk_kw),
        "gain_hits": sum(body.count(k) for k in gain_kw),
        "n_files": len(texts),
    }


def _analyze_run(run_dir: Path, bs: int) -> dict:
    db = run_dir / "sqlite.db"
    meta = _load_meta(run_dir)
    if not db.exists():
        return {"error": f"missing {db}"}
    env_b, env_p = _phase_means(db, bs, ENV_TABLE,
                                ["avg_net_income", "insurance_coverage_rate",
                                 "avg_planted_area", "total_subsidy"])
    agent_b, agent_p = _phase_means(db, bs, AGENT_TABLE,
                                    ["net_income", "planted_area_mu", "insured_area_mu"])
    return {
        "meta": meta,
        "env_b": env_b, "env_p": env_p,
        "agent_b": agent_b, "agent_p": agent_p,
        "farmer_effects": _farmer_effects(db, bs),
        "scale_map": _scale_map(db),
        "mechanism": _mechanism_counts(run_dir),
    }


def analyze_full(results_dir: Path, bs_override: int | None, b: int) -> dict[str, Any]:
    runs: list[dict] = []
    for meta_f in sorted(results_dir.rglob("run_meta.json")):
        info = _analyze_run(meta_f.parent, bs_override or _load_meta(meta_f.parent).get("baseline_steps", 8))
        if "error" not in info:
            runs.append(info)

    by_sc: dict[str, list[dict]] = {}
    for r in runs:
        by_sc.setdefault(r["meta"]["scenario_key"], []).append(r)

    out: dict[str, Any] = {"generated_at": datetime.now().isoformat(),
                           "results_dir": str(results_dir), "bootstrap_b": b,
                           "scenarios": [], "notes": []}
    for sk, items in sorted(by_sc.items()):
        label = items[0]["meta"].get("scenario_label", sk)
        n_agents = items[0]["meta"].get("num_agents")

        # ---- 主效应（农户级 Δ 合并 + bootstrap CI）----
        deltas = [e["delta_net"] for it in items for e in it["farmer_effects"]]
        b_mean = statistics.fmean(it["agent_b"]["net_income"] for it in items) if items else None
        p_mean = statistics.fmean(it["agent_p"]["net_income"] for it in items) if items else None
        eff = statistics.fmean(deltas) if deltas else None
        pct = ((p_mean - b_mean) / abs(b_mean) * 100.0) if (b_mean and b_mean != 0 and p_mean is not None) else None
        ci_lo, ci_hi = _bootstrap_ci(deltas, b)

        # 种植面积 / 覆盖率（政策期 − 基线期）
        pb = statistics.fmean(it["agent_b"]["planted_area_mu"] for it in items) if items else None
        pp = statistics.fmean(it["agent_p"]["planted_area_mu"] for it in items) if items else None
        plant_pct = ((pp - pb) / abs(pb) * 100.0) if (pb and pp is not None and pb != 0) else None
        cov_b = statistics.fmean(it["env_b"]["insurance_coverage_rate"] for it in items) if items else None
        cov_p = statistics.fmean(it["env_p"]["insurance_coverage_rate"] for it in items) if items else None
        subsidy_p = statistics.fmean(it["env_p"]["total_subsidy"] for it in items) if items else None

        # ---- 异质性：按规模分组（农户级 Δ）----
        het: dict[str, dict] = {}
        for it in items:
            for e in it["farmer_effects"]:
                sc = it["scale_map"].get(e["agent_id"], "未知")
                d = het.setdefault(sc, {"deltas": []})
                d["deltas"].append(e["delta_net"])
        het_out: dict[str, dict] = {}
        for sc, d in sorted(het.items()):
            het_out[sc] = {"delta_net": statistics.fmean(d["deltas"]), "n": len(d["deltas"])}

        # ---- 稳健性：多重复时剔除偏离中位数最大的重复 ----
        robust: dict | None = None
        if len(items) > 2:
            rep_deltas = [(it["meta"].get("repeat"), statistics.fmean(
                e["delta_net"] for e in it["farmer_effects"])) for it in items]
            med = statistics.median([x[1] for x in rep_deltas])
            worst = max(rep_deltas, key=lambda x: abs(x[1] - med))
            rest = [x[1] for x in rep_deltas if x != worst]
            robust = {"dropped_repeat": worst[0], "delta_before": statistics.fmean([x[1] for x in rep_deltas]),
                      "delta_after_drop": statistics.fmean(rest), "n_kept": len(rest)}

        # ---- 成本效益 ----
        cost_eff = None
        if subsidy_p and eff is not None and subsidy_p > 0:
            # 全村 Δ净收入 ≈ 农户级 Δ 均值 × 农户数；单位补贴增益 = Δ / 补贴支出
            cost_eff = {"unit_gain_per_yuan": (eff * n_agents) / subsidy_p if n_agents else None,
                        "total_subsidy_policy": subsidy_p}

        # ---- Pareto 点（粮食安全=种植面积政策期，增收=Δ净收入）----
        pareto = {"grain_safety": pp, "income_gain": eff}

        # ---- 机制（合并各 run）----
        mech_hits = [it["mechanism"] for it in items if it.get("mechanism")]
        mech = None
        if mech_hits:
            mech = {"risk_hits": sum(m["risk_hits"] for m in mech_hits),
                    "gain_hits": sum(m["gain_hits"] for m in mech_hits),
                    "n_files": sum(m["n_files"] for m in mech_hits)}
        elif len(items) and all(it.get("mechanism") is None for it in items):
            out["notes"].append(f"{sk}：未找到决策日志，机制编码跳过（检查 run 目录是否有工作区文本）")

        out["scenarios"].append({
            "scenario_key": sk, "scenario_label": label, "n_runs": len(items), "n_agents": n_agents,
            "net_income": {"baseline": b_mean, "policy": p_mean, "delta": eff,
                           "delta_pct": pct, "ci_lo": ci_lo, "ci_hi": ci_hi},
            "planted_area": {"baseline": pb, "policy": pp, "delta_pct": plant_pct},
            "coverage": {"baseline": cov_b, "policy": cov_p},
            "total_subsidy_policy": subsidy_p,
            "cost_effectiveness": cost_eff,
            "heterogeneity": het_out,
            "robustness": robust,
            "mechanism": mech,
            "pareto": pareto,
        })
    return out


def _print_markdown(summary: dict) -> None:
    print("\n# 农业政策沙盒 · 完整分析摘要（bootstrap CI）\n")
    for note in summary.get("notes", []):
        print(f"> 提示：{note}")
    for s in summary["scenarios"]:
        ni = s["net_income"]
        print(f"## {s['scenario_label']}（{s['scenario_key']}，{s['n_runs']} 次重复，{s['n_agents']} 户）\n")
        ci = f"[{ni['ci_lo']:,.0f}, {ni['ci_hi']:,.0f}]" if ni["ci_lo"] is not None else "—"
        print(f"- 净收入处理效应：{ni['delta']:+,.0f} 元/季（{ni['delta_pct']:+.1f}%）"
              f" · bootstrap 95% CI {ci}（b={summary['bootstrap_b']}）")
        pa = s["planted_area"]
        cov = s["coverage"]
        print(f"- 种植面积：{pa['baseline']:.2f} → {pa['policy']:.2f} 亩（{pa['delta_pct']:+.1f}%）"
              f" · 保险覆盖率：{cov['baseline']:.2f} → {cov['policy']:.2f}")
        if s["cost_effectiveness"]:
            ce = s["cost_effectiveness"]
            print(f"- 成本效益：每元补贴净收入增益 {ce['unit_gain_per_yuan']:+.3f} 元"
                  f"（全村补贴支出 {ce['total_subsidy_policy']:,.0f} 元/季）")
        if s["heterogeneity"]:
            print("- 异质性（农户级 Δ净收入）：")
            for sc, d in s["heterogeneity"].items():
                print(f"    {sc:8s} Δ={d['delta_net']:+,.0f}（n={d['n']}）")
        if s["robustness"]:
            rb = s["robustness"]
            print(f"- 稳健性：剔除重复 #{rb['dropped_repeat']} 后 Δ "
                  f"{rb['delta_before']:+,.0f} → {rb['delta_after_drop']:+,.0f}（n={rb['n_kept']}）")
        if s["mechanism"]:
            m = s["mechanism"]
            print(f"- 机制编码：风险预期 {m['risk_hits']} 次 / 收益比较 {m['gain_hits']} 次（{m['n_files']} 个日志文件）")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description="完整实验分析（bootstrap CI / 异质性 / 机制 / 稳健性 / 成本效益）")
    ap.add_argument("--results-dir", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=None, help="输出目录（默认与 results-dir 相同）")
    ap.add_argument("--baseline-steps", type=int, default=None)
    ap.add_argument("--bootstrap", type=int, default=2000, help="bootstrap 抽样次数")
    args = ap.parse_args()

    if not args.results_dir.exists():
        sys.stderr.write(f"结果目录不存在：{args.results_dir}\n")
        raise SystemExit(2)

    summary = analyze_full(args.results_dir, args.baseline_steps, args.bootstrap)
    out = args.out or args.results_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary_full.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    import csv
    with open(out / "summary_full.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario_key", "scenario_label", "n_runs", "n_agents",
                    "net_baseline", "net_policy", "delta", "delta_pct", "ci_lo", "ci_hi",
                    "planted_baseline", "planted_policy", "planted_pct",
                    "coverage_baseline", "coverage_policy", "subsidy_policy"])
        for s in summary["scenarios"]:
            ni, pa, cov = s["net_income"], s["planted_area"], s["coverage"]
            w.writerow([s["scenario_key"], s["scenario_label"], s["n_runs"], s["n_agents"],
                        ni["baseline"], ni["policy"], ni["delta"], ni["delta_pct"],
                        ni["ci_lo"], ni["ci_hi"],
                        pa["baseline"], pa["policy"], pa["delta_pct"],
                        cov["baseline"], cov["policy"], s["total_subsidy_policy"]])

    _print_markdown(summary)
    print(f"输出已写入：{out / 'summary_full.json'}、{out / 'summary_full.csv'}")


if __name__ == "__main__":
    main()
