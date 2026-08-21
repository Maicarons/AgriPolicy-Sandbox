"""正式批次并行调度器（对应 full-experiment-plan.md §3.2）。

用 Python ``subprocess`` 直接拉起 (情景, 重复) 任务，规避 Windows 下 MSYS bash
``fork`` 大量重进程时的内存映射失败问题（比 ``run_full_experiment.sh`` 的
``&``+``wait`` 方案更稳，二者逻辑等价）。

特性：
- 并行度可调（默认 8）；
- **断点续跑**：扫描 ``run_meta.json`` 跳过已完成运行，重启只补未完成/失败项；
- 每个 run 日志写入 ``<results_dir>/<情景>/repeat_<r>/run.log``；
- 单 run 失败不中断其余，结束时给出失败清单。

用法：
    python scripts/run_parallel.py [--parallel 8] [--repeats 10] [--results-dir results/formal]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

SCENARIOS = ["baseline", "grain_subsidy", "insurance_subsidy", "land_transfer_subsidy", "combined"]


def build_tasks(args) -> list[tuple[list[str], str]]:
    tasks: list[tuple[list[str], str]] = []
    for sk in SCENARIOS:
        for r in range(args.repeats):
            rd = Path(args.results_dir) / sk / f"repeat_{r}"
            if (rd / "run_meta.json").exists():
                print(f"  跳过已完成：{sk} repeat_{r}")
                continue
            rd.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable, "-m", "agri_sandbox.run_experiment",
                "--scenario", sk, "--repeat", str(r),
                "--agents", str(args.agents),
                "--baseline-steps", str(args.baseline_steps),
                "--policy-steps", str(args.policy_steps),
                "--seed", str(args.seed),
                "--economics", str(args.economics),
                "--results-dir", str(args.results_dir),
            ]
            tasks.append((cmd, str(rd / "run.log")))
    return tasks


def main() -> None:
    ap = argparse.ArgumentParser(description="正式批次并行调度器（subprocess，断点续跑）")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--agents", type=int, default=50)
    ap.add_argument("--baseline-steps", type=int, default=8)
    ap.add_argument("--policy-steps", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--economics", type=Path, default=Path("configs/economics.calibrated.json"))
    ap.add_argument("--results-dir", type=Path, default=None,
                    help="结果目录（默认 results/<YYYY-MM-DD> 日期目录；"
                         "续跑已有 project 时传该目录，如 --results-dir results/formal）")
    args = ap.parse_args()
    if args.results_dir is None:
        args.results_dir = Path("results") / date.today().isoformat()

    tasks = build_tasks(args)
    if not tasks:
        print("全部运行已完成，无需执行。")
        return

    total = len(tasks)
    print(f"待运行 {total} 个 (情景, 重复)，并行度 {args.parallel}；结果目录 {args.results_dir}")

    procs: dict[subprocess.Popen, str] = {}
    idx = 0
    failed: list[str] = []
    started = time.time()
    while idx < len(tasks) or procs:
        while len(procs) < args.parallel and idx < len(tasks):
            cmd, logp = tasks[idx]
            with open(logp, "a", encoding="utf-8") as f:
                p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
            procs[p] = logp
            tag = f"{cmd[cmd.index('--scenario') + 1]}_r{cmd[cmd.index('--repeat') + 1]}"
            print(f"[{time.strftime('%H:%M:%S')}] 启动 {tag:28s} pid={p.pid} -> {logp}", flush=True)
            idx += 1
        for p in list(procs):
            if p.poll() is not None:
                rc = p.returncode
                if rc != 0:
                    failed.append(procs[p])
                print(f"[{time.strftime('%H:%M:%S')}] 结束 pid={p.pid} rc={rc} ({procs[p]})", flush=True)
                del procs[p]
        time.sleep(5)

    elapsed = (time.time() - started) / 3600
    print(f"调度完成：{total - len(failed)}/{total} 成功，耗时 {elapsed:.1f} 小时")
    if failed:
        print("失败项（可重跑本脚本续跑）：")
        for f in failed:
            print(f"  {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
