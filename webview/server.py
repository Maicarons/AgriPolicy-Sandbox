"""AgriPolicy Sandbox · 实验可视化 Web 服务（FastAPI）。

功能：
- 多项目（project）支持：results 根目录下每个含运行数据的一级子目录视为一个独立
  project（如 formal / smoke / baseline…），可在前端切换查看；
- 实验运行时实时观察进展（轮询 run_progress.json，步骤级进度）；
- 可视化村庄场景（读取回放 SQLite 最新一步快照）与指标时间序列。

用法：
    pip install fastapi uvicorn
    python webview/server.py --results-dir results --port 8000
    # 浏览器打开 http://127.0.0.1:8000

API：
    GET /api/projects                                全部 project 列表（名称 / run 统计）
    GET /api/overview?project=NAME                   指定 project 的运行总览（默认第一个）
    GET /api/scenarios                               政策情景定义
    GET /api/config                                  当前标定参数（configs 快照）
    GET /api/run/{project}/{scenario}/{repeat}       单 run：meta + progress + 最新场景快照
    GET /api/run/{project}/{scenario}/{repeat}/timeseries   env 指标时间序列（step 级）
    GET /api/run/{project}/{scenario}/{repeat}/agent-series 农户净收入均值±离散度时间序列
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"

# 运行时由 main() 用 argparse 注入
PROJECTS_ROOT: Path = Path("results")
CONFIG_PATH: Path = Path("configs/policy_scenarios.json")
ECONOMICS_PATH: Path = Path("configs/economics.json")

# 卡死判定阈值：run_progress.json 超过该秒数未更新且状态为 running，视为中断
STALE_SECONDS = 300

app = FastAPI(title="AgriPolicy Sandbox · 实验可视化", version="1.0.0")


# ---------------------------------------------------------------------------
# 数据读取辅助
# ---------------------------------------------------------------------------
def _read_json(p: Path) -> Any | None:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now().isoformat()


def _elapsed_sec(started_at: str, updated_at: str | None = None) -> float | None:
    try:
        t0 = datetime.fromisoformat(started_at)
        t1 = datetime.fromisoformat(updated_at) if updated_at else datetime.now()
        return max(0.0, (t1 - t0).total_seconds())
    except Exception:
        return None


def _load_scenario_defs() -> dict[str, Any]:
    cfg = _read_json(CONFIG_PATH) or {}
    return {
        "defaults": cfg.get("defaults", {}),
        "scenarios": cfg.get("scenarios", {}),
    }


# ---------------------------------------------------------------------------
# Project 发现 / 定位
# ---------------------------------------------------------------------------
def _has_run_data(d: Path) -> bool:
    """目录内是否存在运行数据（run_meta / run_progress / sqlite.db）。"""
    for cand in ("run_meta.json", "run_progress.json", "sqlite.db"):
        if next(d.rglob(cand), None) is not None:
            return True
    return False


def _list_projects() -> list[Path]:
    """results 根目录下每个含运行数据的一级子目录 = 一个 project。"""
    if not PROJECTS_ROOT.is_dir():
        return []
    out: list[Path] = []
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and _has_run_data(d):
            out.append(d)
    return out


def _resolve_project(name: str | None) -> Path:
    """按名称解析 project 目录；默认返回第一个；非法名称抛 404。"""
    projects = _list_projects()
    if name:
        for p in projects:
            if p.name == name:
                return p
        raise HTTPException(status_code=404, detail=f"project '{name}' 不存在")
    if not projects:
        raise HTTPException(status_code=404, detail=f"'{PROJECTS_ROOT}' 下未发现任何 project")
    return projects[0]


def _run_dir(project: Path, scenario: str, repeat: int) -> Path:
    """定位 run 目录。兼容两种布局：
    1. 嵌套：<project>/<scenario>/repeat_N（如 results/formal/baseline/repeat_0）
    2. 扁平：<project>/repeat_N（顶层早期实验，project 目录即情景目录，如 results/baseline/repeat_0）
    """
    nested = project / scenario / f"repeat_{repeat}"
    if nested.exists():
        return nested
    return project / f"repeat_{repeat}"


def _is_running(prog: dict[str, Any] | None) -> bool:
    return bool(prog and prog.get("status") == "running")


def _is_stale(prog: dict[str, Any] | None) -> bool:
    """running 但超过 STALE_SECONDS 未更新 → 中断残留（非真实运行中）。"""
    if not _is_running(prog):
        return False
    updated = prog.get("updated_at")
    if not updated:
        return True  # 无时间戳的 running 视为不可信
    try:
        age = (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
    except Exception:
        return True
    return age > STALE_SECONDS


# ---------------------------------------------------------------------------
# 运行总览
# ---------------------------------------------------------------------------
def _scan_runs(project: Path) -> list[dict[str, Any]]:
    """聚合指定 project 内所有 run：run_meta.json（完成）与 run_progress.json（运行中）为准。"""
    scenario_defs = _load_scenario_defs()["scenarios"]
    seen: dict[tuple[str, int], dict[str, Any]] = {}

    # 运行中 / 刚结束：run_progress.json
    for prog_f in sorted(project.rglob("run_progress.json")):
        prog = _read_json(prog_f)
        if not prog:
            continue
        sk = prog.get("scenario_key"); rep = prog.get("repeat")
        if sk is None or rep is None:
            continue
        seen[(sk, rep)] = {
            "scenario_key": sk,
            "scenario_label": scenario_defs.get(sk, {}).get("label", sk),
            "repeat": rep,
            "status": prog.get("status", "running"),
            "stale": _is_stale(prog),
            "phase": prog.get("phase"),
            "step": prog.get("step"),
            "step_total": prog.get("step_total"),
            "started_at": prog.get("started_at"),
            "updated_at": prog.get("updated_at"),
            "elapsed_sec": _elapsed_sec(prog.get("started_at"), prog.get("updated_at")),
            "run_dir": str(prog_f.parent),
        }

    # 已完成：run_meta.json（补充 meta 信息；无 progress 的历史数据也视为 done）
    for meta_f in sorted(project.rglob("run_meta.json")):
        meta = _read_json(meta_f)
        if not meta:
            continue
        sk = meta.get("scenario_key"); rep = meta.get("repeat")
        if sk is None or rep is None:
            continue
        entry = seen.setdefault((sk, rep), {
            "scenario_key": sk,
            "scenario_label": scenario_defs.get(sk, {}).get("label", sk),
            "repeat": rep,
            "status": "done",
            "stale": False,
            "run_dir": str(meta_f.parent),
        })
        entry["status"] = "done"
        entry["scenario_label"] = scenario_defs.get(sk, {}).get("label", sk)
        entry.update({
            "num_agents": meta.get("num_agents"),
            "seed": meta.get("seed"),
            "baseline_steps": meta.get("baseline_steps"),
            "policy_steps": meta.get("policy_steps"),
            "model": meta.get("model"),
            "finished_at": meta.get("finished_at"),
            "elapsed_sec": _elapsed_sec(meta.get("started_at"), meta.get("finished_at")),
        })

    runs = sorted(seen.values(), key=lambda r: (r["scenario_key"], r["repeat"]))
    return runs


# ---------------------------------------------------------------------------
# 场景快照 / 时间序列（读回放 SQLite）
# ---------------------------------------------------------------------------
def _connect(project: Path, scenario: str, repeat: int) -> sqlite3.Connection | None:
    db = _run_dir(project, scenario, repeat) / "sqlite.db"
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def _latest_state(project: Path, scenario: str, repeat: int) -> dict[str, Any] | None:
    con = _connect(project, scenario, repeat)
    if con is None:
        return None
    try:
        env = con.execute(
            "SELECT * FROM agri_policy_env_state ORDER BY step DESC LIMIT 1"
        ).fetchone()
        if env is None:
            return {"env": None, "agents": [], "step": 0}
        step = int(env["step"])
        agents = [
            dict(r) for r in con.execute(
                "SELECT * FROM agri_policy_agent_state WHERE step = ? ORDER BY agent_id",
                (step,),
            )
        ]
        # 解析生产结构
        for a in agents:
            try:
                a["plan"] = json.loads(a.pop("crop_mix_json") or "{}")
            except Exception:
                a["plan"] = {}
        return {"env": dict(env), "agents": agents, "step": step}
    finally:
        con.close()


def _env_timeseries(project: Path, scenario: str, repeat: int) -> list[dict[str, Any]]:
    con = _connect(project, scenario, repeat)
    if con is None:
        return []
    try:
        rows = con.execute("SELECT * FROM agri_policy_env_state ORDER BY step").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _agent_series(project: Path, scenario: str, repeat: int) -> list[dict[str, Any]]:
    """农户净收入按 step 聚合：均值 ± 标准差（SQLite 无 stdev，用 Python 计算）。"""
    import statistics
    con = _connect(project, scenario, repeat)
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT step, net_income FROM agri_policy_agent_state ORDER BY step"
        ).fetchall()
        by_step: dict[int, list[float]] = {}
        for r in rows:
            by_step.setdefault(int(r["step"]), []).append(float(r["net_income"]))
        out: list[dict[str, Any]] = []
        for step in sorted(by_step):
            vals = by_step[step]
            out.append({
                "step": step,
                "avg_net": statistics.fmean(vals),
                "sd_net": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                "n_agents": len(vals),
            })
        return out
    finally:
        con.close()


# ---------------------------------------------------------------------------
# API 路由
# ---------------------------------------------------------------------------
@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    projects = []
    for p in _list_projects():
        runs = _scan_runs(p)
        projects.append({
            "name": p.name,
            "path": str(p),
            "total": len(runs),
            "running": sum(1 for r in runs if r["status"] == "running" and not r["stale"]),
            "stale": sum(1 for r in runs if r["status"] == "running" and r["stale"]),
            "done": sum(1 for r in runs if r["status"] == "done"),
        })
    return {"projects": projects, "root": str(PROJECTS_ROOT)}


@app.get("/api/overview")
def api_overview(project: str | None = None) -> dict[str, Any]:
    proj = _resolve_project(project)
    runs = _scan_runs(proj)
    scenarios = _load_scenario_defs()["scenarios"]
    by_sc: dict[str, dict[str, Any]] = {}
    for sk, sc in scenarios.items():
        by_sc[sk] = {"scenario_key": sk, "label": sc.get("label", sk),
                     "total": 0, "running": 0, "done": 0, "stale": 0, "pending": 0}
    for r in runs:
        agg = by_sc.setdefault(r["scenario_key"], {
            "scenario_key": r["scenario_key"], "label": r["scenario_label"],
            "total": 0, "running": 0, "done": 0, "stale": 0, "pending": 0,
        })
        agg["total"] += 1
        st = r["status"]
        if st == "running":
            agg["stale" if r["stale"] else "running"] += 1
        else:
            agg["done" if st == "done" else "pending"] += 1

    totals = {"total": len(runs),
              "running": sum(1 for r in runs if r["status"] == "running" and not r["stale"]),
              "done": sum(1 for r in runs if r["status"] == "done"),
              "stale": sum(1 for r in runs if r["status"] == "running" and r["stale"]),
              "pending": sum(1 for r in runs if r["status"] not in ("running", "done"))}
    return {"project": proj.name, "totals": totals, "scenarios": list(by_sc.values()),
            "runs": runs, "results_dir": str(proj), "server_time": _now_iso()}


@app.get("/api/scenarios")
def api_scenarios() -> dict[str, Any]:
    return _load_scenario_defs()


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    return {
        "policy_scenarios": _read_json(CONFIG_PATH) or {},
        "economics": _read_json(ECONOMICS_PATH) or {},
    }


@app.get("/api/run/{project}/{scenario}/{repeat}")
def api_run(project: str, scenario: str, repeat: int) -> dict[str, Any]:
    proj = _resolve_project(project)
    rd = _run_dir(proj, scenario, repeat)
    if not rd.exists():
        raise HTTPException(status_code=404, detail=f"run {scenario}/repeat_{repeat} 不存在")
    meta = _read_json(rd / "run_meta.json")
    prog = _read_json(rd / "run_progress.json")
    state = _latest_state(proj, scenario, repeat)
    return {
        "project": proj.name,
        "scenario_key": scenario,
        "repeat": repeat,
        "meta": meta,
        "progress": prog,
        "state": state,
        "run_dir": str(rd),
    }


@app.get("/api/run/{project}/{scenario}/{repeat}/timeseries")
def api_timeseries(project: str, scenario: str, repeat: int) -> dict[str, Any]:
    proj = _resolve_project(project)
    rows = _env_timeseries(proj, scenario, repeat)
    if not rows:
        raise HTTPException(status_code=404, detail="该 run 无回放数据（sqlite.db 不存在或为空）")
    return {"project": proj.name, "scenario_key": scenario, "repeat": repeat, "series": rows}


@app.get("/api/run/{project}/{scenario}/{repeat}/agent-series")
def api_agent_series(project: str, scenario: str, repeat: int) -> dict[str, Any]:
    proj = _resolve_project(project)
    rows = _agent_series(proj, scenario, repeat)
    if not rows:
        raise HTTPException(status_code=404, detail="该 run 无农户级回放数据")
    return {"project": proj.name, "scenario_key": scenario, "repeat": repeat, "series": rows}


@app.get("/api/run/{project}/{scenario}/{repeat}/log")
def api_run_log(project: str, scenario: str, repeat: int,
                tail: int = 200, offset: int = 0) -> dict[str, Any]:
    """读取 run.log 尾部内容（默认 200 行；offset>0 时从第 offset 行读到末尾）。

    前端每 3s 轮询可实现类似 tail -f 的实时日志。
    """
    proj = _resolve_project(project)
    rd = _run_dir(proj, scenario, repeat)
    log_f = rd / "run.log"
    if not log_f.exists():
        raise HTTPException(status_code=404, detail=f"run {scenario}/repeat_{repeat} 无日志文件")
    try:
        text = log_f.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {e}")
    lines = text.splitlines()
    total = len(lines)
    if offset > 0:
        chunk = lines[offset - 1:]
    else:
        chunk = lines[-max(1, min(tail, 5000)):]
    return {
        "project": proj.name,
        "scenario_key": scenario,
        "repeat": repeat,
        "total": total,
        "start_line": (offset if offset > 0 else max(1, total - len(chunk) + 1)),
        "lines": chunk,
        "file": str(log_f),
        "mtime": log_f.stat().st_mtime,
        "server_time": _now_iso(),
    }


# ---------------------------------------------------------------------------
# 静态前端
# ---------------------------------------------------------------------------
@app.middleware("http")
async def no_store_static(request, call_next):
    """开发期静态资源不做缓存，避免前端改动后浏览器仍用旧版。"""
    import time
    response = await call_next(request)
    if request.url.path.startswith("/assets/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


# ---------------------------------------------------------------------------
def main() -> None:
    global PROJECTS_ROOT, CONFIG_PATH, ECONOMICS_PATH
    ap = argparse.ArgumentParser(description="AgriPolicy Sandbox 实验可视化 Web")
    ap.add_argument("--results-dir", type=Path, default=Path("results"),
                    help="projects 根目录：其下每个含运行数据的一级子目录 = 一个 project（默认 ./results）")
    ap.add_argument("--config", type=Path, default=Path("configs/policy_scenarios.json"),
                    help="情景配置文件")
    ap.add_argument("--economics", type=Path, default=Path("configs/economics.json"),
                    help="标定参数文件")
    ap.add_argument("--host", type=str, default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    PROJECTS_ROOT = args.results_dir
    CONFIG_PATH = args.config
    ECONOMICS_PATH = args.economics

    import uvicorn
    print(f"* AgriPolicy Sandbox 可视化: http://{args.host}:{args.port}")
    print(f"* projects 根目录: {PROJECTS_ROOT.resolve()}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
