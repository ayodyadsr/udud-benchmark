#!/usr/bin/env python3
"""Aggregate raw/trials.csv into per-(dataset,tool) statistics.

For wall, cpu and peak RSS we report n, mean, sample sd, median, min,
max, the 95% confidence interval half-width (Student t, two-sided) and
the coefficient of variation. Throughput is derived from mean wall time.
Determinism is whether every OK trial in the cell produced an identical
sha256. DNF cells are carried through with status=DNF.

stdlib only. Output: raw/summary.csv and raw/summary.txt
"""
import csv, math, os, statistics as st
from collections import defaultdict, OrderedDict

RAW = os.path.join(os.path.dirname(__file__), "..", "raw")
TR  = os.path.join(RAW, "trials.csv")

# Student t, 0.975 quantile (two-sided 95%) by degrees of freedom.
T975 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,
        8:2.306,9:2.262,10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,
        15:2.131,20:2.086,25:2.060,30:2.042}
def tval(df):
    if df <= 0: return float("nan")
    if df in T975: return T975[df]
    keys = sorted(T975)
    for k in keys:
        if df <= k: return T975[k]
    return 1.960  # large-sample normal limit

def desc(xs):
    n = len(xs)
    if n == 0: return None
    m = st.fmean(xs)
    sd = st.stdev(xs) if n > 1 else 0.0
    ci = tval(n-1) * sd / math.sqrt(n) if n > 1 else 0.0
    cov = (sd/m*100.0) if m else 0.0
    return dict(n=n, mean=m, sd=sd, median=st.median(xs),
                min=min(xs), max=max(xs), ci95=ci, cov=cov)

cells = defaultdict(lambda: dict(wall=[], cpu=[], rss=[], sha=set(),
                                 lines=None, bytes=None, status="OK"))
order = OrderedDict()
with open(TR) as f:
    for r in csv.DictReader(f):
        key = (r["dataset"], r["tool"])
        order.setdefault(key, True)
        c = cells[key]
        c["bytes"] = c["bytes"] or r["bytes"]
        if r["status"] in ("DNF", "SKIP_AFTER_DNF", "SKIP_SIZE"):
            c["status"] = r["status"]; continue
        if r["status"] != "OK":
            continue
        try:
            c["wall"].append(float(r["wall_s"]))
            c["cpu"].append(float(r["cpu_s"]))
            c["rss"].append(int(r["peak_rss_kb"]))
            c["lines"] = int(r["out_lines"])
            c["sha"].add(r["sha256"])
        except ValueError:
            pass

cols = ["dataset","tool","status","n","out_lines","deterministic",
        "wall_mean_s","wall_sd","wall_median_s","wall_min_s","wall_max_s",
        "wall_ci95_s","wall_cov_pct",
        "cpu_mean_s","cpu_ci95_s",
        "rss_mean_kb","rss_sd_kb","rss_max_kb","rss_ci95_kb","rss_cov_pct",
        "throughput_lines_per_s","throughput_MB_per_s"]
rows = []
for key in order:
    ds, tool = key
    c = cells[key]
    if c["status"] != "OK" or not c["wall"]:
        rows.append(dict(dataset=ds, tool=tool,
                         status=(c["status"] if c["status"] != "OK"
                                 else "NO_DATA"),
                         n=0, out_lines="", deterministic=""))
        continue
    w, cp, rs = desc(c["wall"]), desc(c["cpu"]), desc(c["rss"])
    by = int(c["bytes"])
    rows.append(dict(
        dataset=ds, tool=tool, status="OK", n=w["n"],
        out_lines=c["lines"],
        deterministic=(len(c["sha"]) == 1),
        wall_mean_s=round(w["mean"],4), wall_sd=round(w["sd"],4),
        wall_median_s=round(w["median"],4), wall_min_s=round(w["min"],4),
        wall_max_s=round(w["max"],4), wall_ci95_s=round(w["ci95"],4),
        wall_cov_pct=round(w["cov"],2),
        cpu_mean_s=round(cp["mean"],4), cpu_ci95_s=round(cp["ci95"],4),
        rss_mean_kb=round(rs["mean"],1), rss_sd_kb=round(rs["sd"],1),
        rss_max_kb=int(rs["max"]), rss_ci95_kb=round(rs["ci95"],1),
        rss_cov_pct=round(rs["cov"],2),
        throughput_lines_per_s=round(c["lines"]/w["mean"],1) if w["mean"] else "",
        throughput_MB_per_s=round(by/1e6/w["mean"],1) if w["mean"] else ""))

with open(os.path.join(RAW,"summary.csv"),"w",newline="") as f:
    wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader()
    for r in rows: wr.writerow({k:r.get(k,"") for k in cols})

with open(os.path.join(RAW,"summary.txt"),"w") as f:
    cur = None
    for r in rows:
        if r["dataset"] != cur:
            cur = r["dataset"]; f.write(f"\n=== {cur} ===\n")
        if r["status"] != "OK":
            f.write(f"  {r['tool']:<10} {r['status']}\n"); continue
        f.write(
          f"  {r['tool']:<10} out={r['out_lines']:>7}  "
          f"wall={r['wall_mean_s']:.3f}s ±{r['wall_ci95_s']:.3f} "
          f"(CoV {r['wall_cov_pct']:.1f}%)  "
          f"rss={r['rss_mean_kb']/1024:.1f}MB  "
          f"{r['throughput_MB_per_s']}MB/s  det={r['deterministic']}\n")
print("wrote raw/summary.csv and raw/summary.txt")
print(open(os.path.join(RAW,"summary.txt")).read())
