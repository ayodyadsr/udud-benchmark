#!/usr/bin/env python3
# Attack-surface Precision/Recall/F1 on the wayback / vulnweb / gau
# inputs, using the same canonicalisation as harness/quality.py so the
# truth and tool outputs are scored on identical templated signatures.
#
# Per pattern class c (host, js, html, srcdisc, matrix, param_ri):
#
#   TP_c  = | T_c (input)  &  K_c (output, class-restricted signatures) |
#   FN_c  = | T_c  -  K_c |
#   FP_c  = #output_URLs_in_class_c  -  |K_c distinct survivors|
#
# Precision_c = TP / (TP + FP)
# Recall_c    = TP / (TP + FN)
# F1_c        = 2 P R / (P + R)
#
# Micro:  Sum TP, FN, FP across classes, then P/R/F1 from the totals.
# Macro:  P/R/F1 computed per class, then class-uniform mean. The macro
#         number is the security view (every pattern class counts the
#         same, no matter how many input URLs it had).
#
# stdlib only.

import csv
import gzip
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quality                                # reuse classify() etc.

RAW = os.path.join(HERE, "..", "raw")
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(RAW, "outputs")

INPUTS = ["D_example_wb.full", "D_vulnweb.full", "D_example_gau.full"]
TOOLS = ["xcull", "uro", "urldedupe", "urless", "uddup"]
CLASSES = ["host", "js", "html", "srcdisc", "matrix", "param_ri"]


def _open(path):
    if os.path.exists(path):
        return open(path, "r", errors="replace")
    gz = path + ".gz"
    if os.path.exists(gz):
        return gzip.open(gz, "rt", errors="replace")
    return None


def keyset_with_lines(path):
    """Per quality.py classify, plus per-class output-line counters.

    Returns:
      sigs[c]       set of canonical signatures present in this file for class c
      lines_in[c]   number of file lines that classify into c at least once
    """
    sigs = {c: set() for c in CLASSES + ["endpoint"]}
    lines_in = {c: 0 for c in CLASSES}
    fh = _open(path)
    if fh is None:
        return None, None
    with fh:
        for ln in fh:
            kv = quality.classify(ln)
            if not kv:
                continue
            if "endpoint" in kv:
                sigs["endpoint"].add(kv["endpoint"][0])
            for c in CLASSES:
                if c in kv:
                    sigs[c].add(kv[c][0])
                    lines_in[c] += 1
    return sigs, lines_in


def _prf(tp, fn, fp):
    r = tp / (tp + fn) if (tp + fn) else 0.0
    p = tp / (tp + fp) if (tp + fp) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def main():
    rows = []                                 # per-class P/R/F1 per (ds, tool)
    summary = []                              # micro / macro aggregate

    for ds in INPUTS:
        truth, truth_lines = keyset_with_lines(os.path.join(DATA, ds))
        if truth is None:
            print("skip %s: no input" % ds, file=sys.stderr)
            continue
        for tool in TOOLS:
            out_path = os.path.join(OUT, "%s.%s.out" % (ds, tool))
            ksigs, klines = keyset_with_lines(out_path)
            if ksigs is None:
                summary.append((ds, tool, "DNF", "", "", "", "", "", "", "", "", ""))
                continue

            # Per class: TP = |T_c & K_c|, FN = |T_c - K_c|,
            # FP = lines_in_output_for_class - |K_c| (duplicate noise
            # beyond the minimum needed to cover the surviving sigs).
            tp_sum = fn_sum = fp_sum = 0
            p_sum = r_sum = f_sum = 0.0
            n = 0
            for c in CLASSES:
                tp = len(truth[c] & ksigs[c])
                fn = len(truth[c] - ksigs[c])
                fp = max(klines[c] - len(ksigs[c]), 0)
                p, r, f = _prf(tp, fn, fp)
                rows.append((ds, tool, c, tp, fn, fp,
                             round(p, 4), round(r, 4), round(f, 4)))
                tp_sum += tp; fn_sum += fn; fp_sum += fp
                if (tp + fn) > 0:                     # class with truth signal
                    p_sum += p; r_sum += r; f_sum += f
                    n += 1
            p_mi, r_mi, f_mi = _prf(tp_sum, fn_sum, fp_sum)
            p_ma = p_sum / n if n else 0.0
            r_ma = r_sum / n if n else 0.0
            f_ma = f_sum / n if n else 0.0
            summary.append((ds, tool, "OK",
                            tp_sum, fn_sum, fp_sum,
                            round(p_mi, 4), round(r_mi, 4), round(f_mi, 4),
                            round(p_ma, 4), round(r_ma, 4), round(f_ma, 4)))
            print("%-22s %-10s  micro R=%.4f P=%.4f F1=%.4f  "
                  "macro R=%.4f P=%.4f F1=%.4f" % (
                      ds, tool, r_mi, p_mi, f_mi, r_ma, p_ma, f_ma))

    with open(os.path.join(RAW, "wayback_prf_byclass.csv"), "w") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset", "tool", "klass", "tp", "fn", "fp",
                    "precision", "recall", "f1"])
        w.writerows(rows)

    with open(os.path.join(RAW, "wayback_prf.csv"), "w") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset", "tool", "status", "tp", "fn", "fp",
                    "micro_precision", "micro_recall", "micro_f1",
                    "macro_precision", "macro_recall", "macro_f1"])
        w.writerows(summary)
    print("wrote raw/wayback_prf_byclass.csv raw/wayback_prf.csv")


if __name__ == "__main__":
    main()
