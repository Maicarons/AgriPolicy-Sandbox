#!/usr/bin/env bash
# ============================================================
#  AgriPolicy Sandbox · 完整实验运行脚本（根目录）
#
#  用法：
#    ./run_full_experiment.sh smoke      门1+门2：连通性自检 + 冒烟计时/token 基准
#    ./run_full_experiment.sh full       门3：正式批次（多进程并行 + 断点续跑）
#    ./run_full_experiment.sh analyze    回放分析（summary.json / summary.csv）
#    ./run_full_experiment.sh status     查看正式批次进度
#    ./run_full_experiment.sh webui      启动实验可视化 Web（Ctrl+C 停止）
#
#  运行前：
#    1) 填好 .env 的 LLM 凭证；pip install -r requirements.txt
#    2) 正式批次结果写入 results/formal（独立目录，勿与 results/ 混扫）
#    3) 预算自适应：先跑 smoke 记录 秒/户季 与 token，再按
#       full-experiment-plan.md §6 决定是否调整 REPEATS
# ============================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# ---------- 可调参数 ----------
FORMAL_DIR="results/formal"
SMOKE_DIR="results/smoke"
PARALLEL=8                 # 并行进程数（决策 D4：8 并行；注意 LLM API 并发限流）
AGENTS=50
BASELINE_STEPS=8
POLICY_STEPS=8
REPEATS=10                 # 正式批次重复次数（预算自适应后可调低）
SEED=42
ECONOMICS="configs/economics.calibrated.json"   # 标定参数（决策 D3：先标定再跑正式批）
WEBUI_PORT=8000             # 可视化 Web 端口（webui 子命令）
SCENARIOS=(baseline grain_subsidy insurance_subsidy land_transfer_subsidy combined)

log() { echo "[$(date '+%F %T')] $*"; }

# ------------------------------------------------------------
cmd_smoke() {
  log "门 1：连通性自检（baseline，3 户 × 1+1 季）"
  python -m agri_sandbox.run_experiment --scenario baseline --agents 3 \
      --baseline-steps 1 --policy-steps 1 --repeats 1 --economics "$ECONOMICS" --results-dir "$SMOKE_DIR"

  log "门 2：冒烟批次（combined，10 户 × 2+2 季）计时基准"
  start=$(date +%s)
  python -m agri_sandbox.run_experiment --scenario combined --agents 10 \
      --baseline-steps 2 --policy-steps 2 --repeats 1 --economics "$ECONOMICS" --results-dir "$SMOKE_DIR"
  end=$(date +%s)
  secs=$((end - start))
  rate=$(awk -v s="$secs" 'BEGIN{printf "%.1f", s/40}')   # 10 户 × 4 季 = 40 户季
  log "冒烟完成：总耗时 ${secs}s（≈ ${rate}s/户季）"
  log "下一步：按 full-experiment-plan.md §6 预算模型，用实测单价/token 锁定 REPEATS，再执行 ./run_full_experiment.sh full"
}

# ------------------------------------------------------------
cmd_full() {
  mkdir -p "$FORMAL_DIR"
  # 用 Python subprocess 调度（scripts/run_parallel.py）：规避 Windows 下 MSYS bash
  # fork 大量重进程的内存映射失败；断点续跑（跳过已完成）在调度器内实现。
  python scripts/run_parallel.py \
      --parallel "$PARALLEL" \
      --agents "$AGENTS" \
      --baseline-steps "$BASELINE_STEPS" \
      --policy-steps "$POLICY_STEPS" \
      --repeats "$REPEATS" \
      --seed "$SEED" \
      --economics "$ECONOMICS" \
      --results-dir "$FORMAL_DIR"
  log "正式批次全部完成 → 运行分析"
  cmd_analyze
}

# ------------------------------------------------------------
cmd_analyze() {
  if [ ! -d "$FORMAL_DIR" ]; then
    log "尚未生成 $FORMAL_DIR，请先执行 ./run_full_experiment.sh full"
    return 1
  fi
  python -m agri_sandbox.analyze --results-dir "$FORMAL_DIR" --out "$FORMAL_DIR"
  log "分析输出：$FORMAL_DIR/summary.json、summary.csv"
}

# ------------------------------------------------------------
cmd_status() {
  local done_count=0
  if [ -d "$FORMAL_DIR" ]; then
    done_count=$(find "$FORMAL_DIR" -name run_meta.json 2>/dev/null | wc -l)
  fi
  local total=$(( ${#SCENARIOS[@]} * REPEATS ))
  log "正式批次进度：$done_count / $total 完成"
  if [ "$done_count" -gt 0 ]; then
    for f in $(find "$FORMAL_DIR" -name run_meta.json 2>/dev/null | sort); do
      python - "$f" <<'PY'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"  {str(m.get('scenario_key','?')):22s} repeat_{m.get('repeat','?')}  "
      f"finished={str(m.get('finished_at','?'))[:19]}  model={m.get('model','?')}")
PY
    done
  fi
}

# ------------------------------------------------------------
cmd_webui() {
  log "启动实验可视化 Web：http://127.0.0.1:${WEBUI_PORT}（结果目录 $FORMAL_DIR；Ctrl+C 停止）"
  python webview/server.py --results-dir "$FORMAL_DIR" --port "$WEBUI_PORT"
}

# ------------------------------------------------------------
case "${1:-}" in
  smoke)   cmd_smoke ;;
  full)    cmd_full ;;
  analyze) cmd_analyze ;;
  status)  cmd_status ;;
  webui)   cmd_webui ;;
  *)
    echo "用法: $0 {smoke|full|analyze|status|webui}"
    echo "  smoke    门1 连通性自检 + 门2 冒烟计时基准"
    echo "  full     门3 正式批次（并行 + 断点续跑）"
    echo "  analyze  回放分析"
    echo "  status   查看正式批次进度"
    echo "  webui    启动实验可视化 Web（端口 $WEBUI_PORT）"
    exit 1
    ;;
esac
