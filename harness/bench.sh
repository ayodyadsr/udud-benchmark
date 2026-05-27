#!/usr/bin/env bash
# Single-corpus benchmark harness (D_unified.full).
#
# This is the canonical bench script: one input, five tools, N trials
# per cell, best-of-N timing reported. Output goes to
# raw/trials_unified.csv (per trial) and raw/results_unified.csv
# (per tool, best run).
#
# Run order:
#   1. ./harness/bench_unified.sh       -> trials_unified.csv
#   2. python3 harness/synth_eval.py    -> synth_*.csv (quality)
#   3. python3 harness/stats.py         -> results_unified.csv (best run)
#
# Why one corpus only: the previous design mixed Wayback (cost/reach
# without ground truth) and D_synth (small, with ground truth). That
# meant the FMR row of the headline table came from a different input
# than the throughput row, which made the report harder to verify by
# hand. D_unified is one input that supports every metric.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DATA="$ROOT/data"
RAW="$ROOT/raw"
OUTDIR="$RAW/outputs"
RUNSTAT=/home/osa/recon/tools/xcull/runstat
PIN="taskset -c 2"
N=5                            # timed trials per tool (best-of-N)
TIMEOUT=600                    # per-run wall cap (s); above = DNF
CSV="$RAW/trials_unified.csv"
LOG="$RAW/bench_unified.log"
DATASET="D_unified.full"
IN="$DATA/$DATASET"

mkdir -p "$OUTDIR"
echo "tool,trial,wall_s,cpu_s,peak_rss_kb,out_lines,exit,status,sha256" > "$CSV"
: > "$LOG"

LINES=$(wc -l < "$IN")
BYTES=$(wc -c < "$IN")
echo "dataset=$DATASET lines=$LINES bytes=$BYTES" | tee -a "$LOG"

# prime page cache
cat "$IN" > /dev/null

TOOLS=(xcull uro urldedupe urless uddup)

# uddup is O(n^2); on a 780k input it cannot finish. We still RUN it
# (no skip-by-name) so the DNF is measured rather than asserted; the
# warm-up timeout catches it without wasting N trials.
trials_for(){ [ "$1" = uddup ] && echo 1 || echo "$N"; }

toolcmd() {
  case "$1" in
    xcull)      echo "xcull < '$IN' > '$OUT'" ;;
    uro)       echo "uro -i '$IN' > '$OUT'" ;;
    urldedupe) echo "urldedupe < '$IN' > '$OUT'" ;;
    urless)    echo "urless -nb < '$IN' > '$OUT'" ;;
    uddup)     echo "uddup -u '$IN' -o '$OUT'" ;;
  esac
}

log(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG" ; }

for tool in "${TOOLS[@]}"; do
  NT=$(trials_for "$tool")
  OUT="/tmp/bench_unified.$tool.out"
  export IN OUT
  CMD=$(toolcmd "$tool")
  reap(){ pkill -9 -f "bin/$tool" 2>/dev/null
          pkill -9 -x "$tool" 2>/dev/null
          pkill -9 -f "bench_unified\.$tool\." 2>/dev/null; : ; }

  # warm-up run (untimed); validates command and catches DNF early
  log "$tool warm-up"
  timeout -k 10 "$TIMEOUT" $PIN sh -c "$CMD" >/dev/null 2>>"$LOG"
  wrc=$?; reap
  if [ $wrc -eq 124 ] || [ $wrc -eq 137 ]; then
    log "  $tool DNF (warm-up exceeded ${TIMEOUT}s)"
    echo "$tool,0,NA,NA,NA,NA,$wrc,DNF," >> "$CSV"
    continue
  fi

  first_sha=""; det=1
  for t in $(seq 1 "$NT"); do
    rs=$($PIN timeout -k 10 "$TIMEOUT" "$RUNSTAT" "$tool" -- sh -c "$CMD" 2>&1 >/dev/null)
    ec=$?
    if [ "$ec" -eq 124 ] || [ "$ec" -eq 137 ]; then
      reap
      log "  $tool DNF (trial $t exceeded ${TIMEOUT}s)"
      echo "$tool,$t,NA,NA,NA,NA,$ec,DNF," >> "$CSV"
      break
    fi
    wall=$(echo "$rs" | grep -oE 'wall=[ ]*[0-9.]+' | grep -oE '[0-9.]+')
    cpu=$(echo  "$rs" | grep -oE 'cpu=[ ]*[0-9.]+'  | grep -oE '[0-9.]+')
    rss=$(echo  "$rs" | grep -oE 'peakRSS=[ ]*[0-9]+' | grep -oE '[0-9]+')
    ol=$(wc -l < "$OUT" 2>/dev/null || echo NA)
    sh=$(sha256sum "$OUT" 2>/dev/null | cut -d' ' -f1)
    [ -z "$first_sha" ] && first_sha="$sh"
    [ "$sh" != "$first_sha" ] && det=0
    echo "$tool,$t,${wall:-NA},${cpu:-NA},${rss:-NA},$ol,$ec,OK,$sh" >> "$CSV"
  done

  # keep canonical output for the quality eval
  if [ -s "$OUT" ]; then
    cp "$OUT" "$OUTDIR/$DATASET.$tool.out"
  fi
  rm -f "$OUT"
  log "$tool done  (deterministic=$det)"
done

log "BENCH COMPLETE"
