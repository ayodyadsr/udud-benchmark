#!/usr/bin/env bash
# udud benchmark harness - performance measurement
#
# Design (systems/measurement-paper style):
#   - single SUT core pinned with taskset -c 2, performance governor,
#     turbo disabled (see ../raw/environment.txt)
#   - per (dataset,tool) cell: prime page cache, 1 untimed warm-up run,
#     then N timed trials measured with runstat (fork+wait4+getrusage)
#   - every trial records wall, cpu, peakRSS, output line count, sha256
#   - per-run wall cap = TIMEOUT s; a tool that exceeds it is DNF and is
#     not run on any larger dataset (monotone in input size)
#   - all tools read a file and write a file as a single process so the
#     getrusage maxrss is the tool, not a `cat` pipeline
#
# output: ../raw/trials.csv  (one row per trial)
set -u

WS=/home/osa/recon/bench
DATA="$WS/data"
RAW="$WS/raw"
OUTDIR="$RAW/outputs"          # canonical outputs kept for the quality eval
RUNSTAT=/home/osa/recon/tools/udud/runstat
PIN="taskset -c 2"
N=10                            # timed trials per cell
TIMEOUT=300                     # per-run wall cap (s); exceeding => DNF
CSV="$RAW/trials.csv"
LOG="$RAW/bench.log"

mkdir -p "$OUTDIR"
echo "dataset,lines,bytes,tool,trial,wall_s,cpu_s,peak_rss_kb,out_lines,exit,status,sha256" > "$CSV"
: > "$LOG"

# datasets, ascending size (subsets first so a DNF skips bigger ones)
DATASETS=(
  D_example_wb.25000 D_example_wb.50000 D_example_wb.100000
  D_example_wb.200000 D_example_wb.400000 D_example_wb.full
  D_vulnweb.full D_example_gau.full
)
TOOLS=(udud uro urldedupe urless uddup)

# per-tool overrides. uddup is O(n^2): N=10 tight-CI runs are wasted on a
# baseline whose contribution is the asymptotic blow-up, and >50k it
# costs >>300s. We measure it with N=3 on inputs <=UDDUP_MAX plus the
# two secondary corpora (curve established), DNF beyond. This is a
# deliberate, documented asymmetry, not a fair-run violation: every
# tool that competes on the head-to-head (linear-time) gets the full
# N=10 + 95% CI.
trials_for(){ [ "$1" = uddup ] && echo 3 || echo "$N"; }
UDDUP_MAX=50000     # lines; uddup skipped above this (O(n^2) -> DNF)

# tool command template: $IN dataset path, $OUT output path. single process,
# documented default invocation for each tool (see harness/INVOCATION.md).
toolcmd() {
  case "$1" in
    udud)      echo "udud < '$IN' > '$OUT'" ;;
    uro)       echo "uro -i '$IN' > '$OUT'" ;;
    urldedupe) echo "urldedupe < '$IN' > '$OUT'" ;;
    urless)    echo "urless -nb < '$IN' > '$OUT'" ;;   # -i broken in 2.7; -nb cosmetic only
    uddup)     echo "uddup -u '$IN' -o '$OUT'" ;;
  esac
}

log(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG" ; }

declare -A DNF_AT               # DNF_AT[tool]=lines at first timeout

for ds in "${DATASETS[@]}"; do
  IN="$DATA/$ds"
  LINES=$(wc -l < "$IN"); BYTES=$(wc -c < "$IN")
  cat "$IN" > /dev/null         # prime page cache for this dataset
  log "dataset $ds  lines=$LINES bytes=$BYTES"
  for tool in "${TOOLS[@]}"; do
    NT=$(trials_for "$tool")
    # uddup O(n^2) size cap: skip oversized inputs WITHOUT poisoning the
    # smaller secondary corpora later in the list.
    if [ "$tool" = uddup ] && [ "$LINES" -gt "$UDDUP_MAX" ]; then
      log "  uddup SKIP (lines=$LINES > UDDUP_MAX=$UDDUP_MAX; O(n^2) -> DNF)"
      echo "$ds,$LINES,$BYTES,$tool,0,NA,NA,NA,NA,NA,SKIP_SIZE," >> "$CSV"
      continue
    fi
    # size-aware monotone-DNF skip: only skip inputs at least as large
    # as the one this tool already timed out on.
    if [ -n "${DNF_AT[$tool]:-}" ] && [ "$LINES" -ge "${DNF_AT[$tool]}" ]; then
      log "  $tool SKIP (DNF at ${DNF_AT[$tool]} lines; this >= that)"
      echo "$ds,$LINES,$BYTES,$tool,0,NA,NA,NA,NA,NA,SKIP_AFTER_DNF," >> "$CSV"
      continue
    fi
    OUT="/tmp/bench.$tool.$ds.out"
    export IN OUT
    CMD=$(toolcmd "$tool")
    # reap orphaned grandchildren after a kill. python tools show up as
    # python3, so match the binary path fragment (bin/<tool>) too.
    reap(){ pkill -9 -f "bin/$tool" 2>/dev/null
            pkill -9 -x "$tool" 2>/dev/null
            pkill -9 -f "bench\.$tool\." 2>/dev/null; : ; }

    # untimed warm-up (interpreter import + code pages); also validates cmd.
    # timeout WRAPS runstat so getrusage maxrss is the tool (dash exec-opt),
    # never `timeout`; -k force-kills, reap() clears any orphaned grandchild.
    timeout -k 10 "$TIMEOUT" $PIN sh -c "$CMD" >/dev/null 2>>"$LOG"
    wrc=$?; reap
    if [ $wrc -eq 124 ] || [ $wrc -eq 137 ]; then
      DNF_AT[$tool]=$LINES
      log "  $tool DNF (warm-up exceeded ${TIMEOUT}s) on $ds"
      echo "$ds,$LINES,$BYTES,$tool,0,NA,NA,NA,NA,$wrc,DNF," >> "$CSV"
      continue
    fi

    first_sha=""; det=1
    for t in $(seq 1 "$NT"); do
      rs=$($PIN timeout -k 10 "$TIMEOUT" "$RUNSTAT" "$tool" -- sh -c "$CMD" 2>&1 >/dev/null)
      ec=$?; [ "$ec" -eq 124 ] || [ "$ec" -eq 137 ] && reap
      # runstat line: "<label>  wall=  X.XXXs  cpu=  Y.YYYs  peakRSS=  Z KB"
      wall=$(echo "$rs" | grep -oE 'wall=[ ]*[0-9.]+' | grep -oE '[0-9.]+')
      cpu=$(echo  "$rs" | grep -oE 'cpu=[ ]*[0-9.]+'  | grep -oE '[0-9.]+')
      rss=$(echo  "$rs" | grep -oE 'peakRSS=[ ]*[0-9]+' | grep -oE '[0-9]+')
      if [ "$ec" -eq 124 ] || [ "$ec" -eq 137 ]; then
        DNF_AT[$tool]=$LINES
        log "  $tool DNF (trial $t exceeded ${TIMEOUT}s) on $ds"
        echo "$ds,$LINES,$BYTES,$tool,$t,NA,NA,NA,NA,$ec,DNF," >> "$CSV"
        break
      fi
      ol=$(wc -l < "$OUT" 2>/dev/null || echo NA)
      sh=$(sha256sum "$OUT" 2>/dev/null | cut -d' ' -f1)
      [ -z "$first_sha" ] && first_sha="$sh"
      [ "$sh" != "$first_sha" ] && det=0
      echo "$ds,$LINES,$BYTES,$tool,$t,${wall:-NA},${cpu:-NA},${rss:-NA},$ol,$ec,OK,$sh" >> "$CSV"
    done

    # keep one canonical output per tool for the largest corpora (quality eval)
    case "$ds" in
      D_example_wb.full|D_vulnweb.full|D_example_gau.full)
        [ -s "$OUT" ] && cp "$OUT" "$OUTDIR/$ds.$tool.out" ;;
    esac
    rm -f "$OUT"
    log "  $tool done on $ds  (deterministic=$det)"
  done
done
log "BENCH COMPLETE"
