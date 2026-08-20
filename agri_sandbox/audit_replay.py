"""回放数据审计（对应 full-experiment-plan.md §7.3）。

对结果目录下每个运行检查：

- `sqlite.db` 存在、回放表行数完整（agent_state 行数 = 农户数 × 总季数；env_state 行数 = 总季数）；
- 异常占比：净收入 ≤ 0、`planted_area=0`（非首步）、投保面积 > 种植面积（无流转时通常不应出现）；
- 抽样提示：`n_planting_farmers` 为 0 的季度数。

用法：
    python -m agri_sandbox.audit_replay --results-dir results

退出码：发现异常 → 1（可用于脚本门控）；全部正常 → 0。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

AGENT_TABLE = "agri_policy_agent_state"
ENV_TABLE = "agri_policy_env_state"


def _query(db: Path, sql: str) -> list[dict]:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql).fetchall()]
    finally:
        con.close()


def audit_run(run_dir: Path) -> dict:
    db = run_dir / "sqlite.db"
    meta_f = run_dir / "run_meta.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {}
    sk = meta.get("scenario_key", run_dir.parent.name)
    rep = meta.get("repeat", 0)
    problems: list[str] = []

    if not db.exists():
        return {"scenario": sk, "repeat": rep, "ok": False, "problems": ["sqlite.db 缺失"], "detail": {}}

    n_agents = meta.get("num_agents")
    steps = int(meta.get("baseline_steps", 0)) + int(meta.get("policy_steps", 0))
    rows = _query(db, f"SELECT COUNT(*) AS n FROM {AGENT_TABLE}")
    n_agent_rows = rows[0]["n"] if rows else 0
    rows = _query(db, f"SELECT COUNT(*) AS n FROM {ENV_TABLE}")
    n_env_rows = rows[0]["n"] if rows else 0

    if n_agents and steps and n_agent_rows != n_agents * steps:
        problems.append(f"agent_state 行数 {n_agent_rows} ≠ 期望 {n_agents}×{steps}={n_agents * steps}")
    if steps and n_env_rows != steps:
        problems.append(f"env_state 行数 {n_env_rows} ≠ 期望 {steps}")

    detail: dict = {"agent_rows": n_agent_rows, "env_rows": n_env_rows}
    try:
        all_rows = _query(db, f"SELECT * FROM {AGENT_TABLE} ORDER BY step, agent_id")
        nonfirst = [r for r in all_rows if int(r["step"]) > 1]
        if nonfirst:
            detail["net_le0_pct"] = round(
                100.0 * sum(1 for r in nonfirst if (r.get("net_income") or 0) <= 0) / len(nonfirst), 2)
            detail["planted0_pct"] = round(
                100.0 * sum(1 for r in nonfirst if (r.get("planted_area_mu") or 0) <= 0) / len(nonfirst), 2)
            detail["insured_gt_planted_pct"] = round(
                100.0 * sum(1 for r in nonfirst if (r.get("insured_area_mu") or 0) > (r.get("planted_area_mu") or 0) * 1.05)
                / len(nonfirst), 2)
            for label, key in (("净收入 ≤ 0", "net_le0_pct"), ("种植面积为 0", "planted0_pct"),
                               ("投保 > 种植", "insured_gt_planted_pct")):
                if detail[key] > 20:
                    problems.append(f"{label} 占比 {detail[key]}% > 20%")
        env_rows = _query(db, f"SELECT * FROM {ENV_TABLE}")
        zero_plant_q = sum(1 for r in env_rows if (r.get("n_planting_farmers") or 0) == 0)
        detail["zero_planting_quarters"] = zero_plant_q
        if zero_plant_q > 0:
            problems.append(f"有 {zero_plant_q} 个季度 n_planting_farmers=0")
    except Exception as e:
        problems.append(f"审计查询失败：{e}")

    return {"scenario": sk, "repeat": rep, "ok": not problems, "problems": problems, "detail": detail}


def main() -> None:
    ap = argparse.ArgumentParser(description="回放数据审计")
    ap.add_argument("--results-dir", type=Path, default=Path("results"))
    args = ap.parse_args()
    if not args.results_dir.exists():
        sys.stderr.write(f"结果目录不存在：{args.results_dir}\n")
        raise SystemExit(2)

    metas = sorted(args.results_dir.rglob("run_meta.json"))
    if not metas:
        print(f"（{args.results_dir} 下未找到 run_meta.json）")
        raise SystemExit(2)

    print(f"# 回放审计：{args.results_dir}（{len(metas)} 个运行）\n")
    n_bad = 0
    for mf in metas:
        a = audit_run(mf.parent)
        flag = "OK" if a["ok"] else "FAIL"
        if not a["ok"]:
            n_bad += 1
        print(f"[{flag}] {a['scenario']:22s} repeat_{a['repeat']}  "
              f"rows={a['detail'].get('agent_rows', '?')}/{a['detail'].get('env_rows', '?')}  "
              f"{'；'.join(a['problems']) if a['problems'] else '正常'}")
    print(f"\n审计结果：{len(metas) - n_bad}/{len(metas)} 通过")
    raise SystemExit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
