#!/usr/bin/env python3
# Score a tool's dedup output against the synthetic ground truth.
#
# Each output URL is mapped to a (class, group_id) via parsing rules
# that survive whatever normalisation the tool applied (trailing slash,
# query reorder, case, etc.). For every pattern class we then report:
#
#   surviving_groups  - distinct canonical endpoints represented in
#                       the output
#   destroyed_groups  - canonical endpoints missing from the output
#                       (this is the false-negative count: real surface
#                        deleted)
#   kept_urls         - output URLs that fell into the class
#   recall            = surviving_groups / total_groups          [1.0 is perfect]
#   over_keep_ratio   = kept_urls / surviving_groups             [1.0 is perfect;
#                       higher means redundant duplicates left behind]
#
# A row is LOSSLESS for that class if destroyed_groups == 0.

import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse, parse_qs as _parse_qs


def parse_qs(q):
    """parse_qs that keeps blank values so /page?file= still has key 'file'.

    Some tools (notably udud) blank a sink param value as part of the
    signature canonicalisation: the output URL is /page?file= rather
    than /page?file=<payload>. The endpoint+param-name surface is the
    same as the input; the classifier must not lose it."""
    return _parse_qs(q, keep_blank_values=True)

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(HERE, "..", "data", "D_synth.full")
TRUTH = os.path.join(HERE, "..", "data", "D_synth.truth.json")


def load_truth():
    with open(TRUTH) as fh:
        t = json.load(fh)
    return t


def classify(url):
    try:
        p = urlparse(url.strip())
    except Exception:
        return None
    path = p.path or ""
    q = p.query or ""

    # NUMERIC_ID: /product/<digits>
    if re.match(r"^/product/\d+/?$", path):
        return ("NUMERIC_ID", "product")
    # UUID: /order/<uuid4>
    if re.match(r"^/order/[0-9a-fA-F-]{32,36}/?$", path):
        return ("UUID", "order")
    # HEX_HASH: /asset/<64-hex>
    if re.match(r"^/asset/[0-9a-fA-F]{64}/?$", path):
        return ("HEX_HASH", "asset")
    # TITLE_SLUG: /blog/<slug-words-N>
    if re.match(r"^/blog/[a-z][a-z0-9-]+-\d+/?$", path):
        return ("TITLE_SLUG", "blog")
    # CACHE_BUST: /main.js + query containing _
    if path == "/main.js":
        keys = set(parse_qs(q).keys())
        if "_" in keys or not q:
            return ("CACHE_BUST", "main.js")
    # JSESSIONID: any path with ;jsessionid=
    if ";jsessionid=" in url.lower() or re.search(r"/auth(/|;|$)", path, re.I):
        if path.rstrip("/").endswith("/auth") or "/auth;" in url or path == "/auth":
            return ("JSESSIONID", "auth")
    # OPEN_REDIRECT: /redir + query containing url=
    if path == "/redir":
        keys = set(parse_qs(q).keys())
        if "url" in keys or not q:
            return ("OPEN_REDIRECT", "redir")
    # LFI_PARAM: /page + query containing file=
    if path == "/page":
        keys = set(parse_qs(q).keys())
        if "file" in keys or not q:
            return ("LFI_PARAM", "page")
    # PARAM_ORDER: /api + query with keys {a,b}
    if path == "/api":
        keys = set(parse_qs(q).keys())
        if keys == {"a", "b"} or keys == set():
            return ("PARAM_ORDER", "api")
    # TRAILING_SLASH: /widget<n>[/]
    m = re.match(r"^/widget(\d+)/?$", path)
    if m:
        return ("TRAILING_SLASH", "widget%s" % m.group(1))
    # SRCDISC: known set
    srcdisc = {
        "/.env", "/.env.production", "/.env.local",
        "/.git/config", "/.git/HEAD", "/.git/index",
        "/db.sql", "/backup.sql", "/dump.sql",
        "/backup.zip", "/backup.tar.gz",
        "/index.php.bak", "/config.php.bak", "/wp-config.php.bak",
        "/.htaccess.bak", "/.htpasswd",
        "/config.php.swp", "/.DS_Store",
        "/credentials.json", "/secrets.yml",
    }
    if path in srcdisc:
        return ("SRCDISC", path)
    # GENUINE_DISTINCT: any other path in the synth host - fall through
    # to the ground-truth list of 200 paths.
    return ("GENUINE_DISTINCT", path)


def evaluate_output(out_path, truth):
    """Return per-class {surviving_groups, kept_urls, total_groups}."""
    by_class = {}                                # class -> set(group_id)
    kept_urls = {}                               # class -> count

    with open(out_path, "rb") as fh:
        for line in fh:
            try:
                url = line.decode("utf-8", "replace").strip()
            except Exception:
                continue
            if not url:
                continue
            label = classify(url)
            if not label:
                continue
            klass, gid = label
            # restrict GENUINE_DISTINCT to the ground-truth list
            if klass == "GENUINE_DISTINCT":
                if gid not in truth.get("GENUINE_DISTINCT", {}).get("groups", []):
                    continue
            by_class.setdefault(klass, set()).add(gid)
            kept_urls[klass] = kept_urls.get(klass, 0) + 1

    out = {}
    for klass, meta in truth.items():
        total = meta["n_canonical_groups"]
        kept = len(by_class.get(klass, set()))
        urls_kept = kept_urls.get(klass, 0)
        out[klass] = {
            "total_groups": total,
            "surviving_groups": kept,
            "destroyed_groups": total - kept,
            "kept_urls": urls_kept,
            "recall": kept / total if total else 0.0,
            "over_keep_ratio": (urls_kept / kept) if kept else None,
            "lossless": (kept == total),
        }
    return out


def run_tool(tool, input_path, out_dir):
    name = tool
    out = os.path.join(out_dir, "D_synth.full.%s.out" % name)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out, None
    bin_path = {
        "udud": "/usr/local/bin/udud",
        "uro": "uro",
        "urldedupe": "urldedupe",
        "urless": "urless",
        "uddup": "uddup",
    }[name]
    if name == "uddup":
        # uddup needs -u flag
        proc = subprocess.run([bin_path, "-u", input_path],
                              capture_output=True, timeout=300)
    elif name == "urless":
        # urless reads -i only when stdin is a TTY; under subprocess
        # stdin is a pipe so urless reads (empty) stdin and ignores -i.
        # Workaround: pipe the file via stdin and let urless write to -o.
        proc = subprocess.run([bin_path, "-o", out],
                              stdin=open(input_path, "rb"),
                              capture_output=True, timeout=600)
        return out, proc.stderr
    else:
        proc = subprocess.run([bin_path],
                              stdin=open(input_path, "rb"),
                              capture_output=True, timeout=600)
    if proc.returncode != 0 and name != "uddup":
        print("%s exited %d: %s" % (name, proc.returncode, proc.stderr[:200]),
              file=sys.stderr)
    with open(out, "wb") as fh:
        fh.write(proc.stdout)
    return out, proc.stderr


def _prf(tp, fn, fp):
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0.0)
    return precision, recall, f1


def aggregate_prf(per_class):
    """Attack-surface Precision/Recall/F1 across all classes.

    Per class:
      TP  = surviving_groups           (canonical endpoints kept)
      FN  = destroyed_groups           (canonical endpoints deleted)
      FP  = kept_urls - surviving_groups
                                       (duplicates that escaped dedup; one
                                        representative per group is the minimum
                                        useful output - everything above is FP)

      Recall    = TP / (TP + FN)       "did real attack surface survive?"
      Precision = TP / (TP + FP)       "is the output free of duplicates?"
      F1        = 2 P R / (P + R)      "attack-surface fidelity"

    Two aggregations are reported:
      - micro: TP/FP/FN summed across classes, then P/R/F1 computed.
        Dominated by the heavy-cardinality classes (e.g. 5000-input
        cache-bust). Useful as a single bytes-on-the-wire number.
      - macro: P/R/F1 computed per class, then class-uniform averaged.
        Each pattern class counts equally regardless of input cardinality.
        Closer to the security view: losing the LFI class and losing the
        cache-bust class are equally bad findings.
    """
    tp_t = fn_t = fp_t = kept_t = 0
    p_sum = r_sum = f_sum = 0.0
    n_classes = 0
    per = {}
    for klass, v in per_class.items():
        tp = v["surviving_groups"]
        fn = v["destroyed_groups"]
        fp = v["kept_urls"] - tp
        p, r, f = _prf(tp, fn, fp)
        per[klass] = {"tp": tp, "fn": fn, "fp": fp,
                      "precision": p, "recall": r, "f1": f}
        tp_t += tp; fn_t += fn; fp_t += fp; kept_t += v["kept_urls"]
        p_sum += p; r_sum += r; f_sum += f
        n_classes += 1
    p_mi, r_mi, f_mi = _prf(tp_t, fn_t, fp_t)
    p_ma = p_sum / n_classes if n_classes else 0.0
    r_ma = r_sum / n_classes if n_classes else 0.0
    f_ma = f_sum / n_classes if n_classes else 0.0
    return {
        "per_class": per,
        "tp": tp_t, "fn": fn_t, "fp": fp_t,
        "kept_urls": kept_t,
        "canonical_groups": tp_t + fn_t,
        "micro_precision": p_mi, "micro_recall": r_mi, "micro_f1": f_mi,
        "macro_precision": p_ma, "macro_recall": r_ma, "macro_f1": f_ma,
    }


def main():
    truth = load_truth()
    out_dir = os.path.join(HERE, "..", "raw", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    results = {}
    for tool in ["udud", "uro", "urldedupe", "urless", "uddup"]:
        out_path, _ = run_tool(tool, INPUT, out_dir)
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            print("%s: DNF or empty output" % tool)
            results[tool] = None
            continue
        results[tool] = evaluate_output(out_path, truth)
        out_lines = sum(1 for _ in open(out_path, "rb"))
        print("%-10s -> %d lines" % (tool, out_lines))

    out_csv = os.path.join(HERE, "..", "raw", "synth_eval.csv")
    with open(out_csv, "w") as fh:
        fh.write("tool,klass,total_groups,surviving_groups,destroyed_groups,"
                 "kept_urls,recall,over_keep_ratio,lossless\n")
        for tool, per in results.items():
            if per is None:
                fh.write("%s,DNF,,,,,,,\n" % tool)
                continue
            for klass in sorted(per.keys()):
                v = per[klass]
                fh.write("%s,%s,%d,%d,%d,%d,%.4f,%s,%s\n" % (
                    tool, klass, v["total_groups"], v["surviving_groups"],
                    v["destroyed_groups"], v["kept_urls"],
                    v["recall"],
                    ("%.3f" % v["over_keep_ratio"]) if v["over_keep_ratio"] is not None else "",
                    "yes" if v["lossless"] else "no",
                ))
    print("wrote %s" % out_csv)

    # Attack-surface fidelity summary (Precision/Recall/F1 across all classes)
    prf_csv = os.path.join(HERE, "..", "raw", "synth_prf.csv")
    with open(prf_csv, "w") as fh:
        fh.write("tool,canonical_groups,tp,fn,fp,kept_urls,"
                 "micro_precision,micro_recall,micro_f1,"
                 "macro_precision,macro_recall,macro_f1\n")
        for tool, per in results.items():
            if per is None:
                fh.write("%s,DNF,,,,,,,,,,\n" % tool)
                continue
            a = aggregate_prf(per)
            fh.write("%s,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n" % (
                tool, a["canonical_groups"], a["tp"], a["fn"], a["fp"],
                a["kept_urls"],
                a["micro_precision"], a["micro_recall"], a["micro_f1"],
                a["macro_precision"], a["macro_recall"], a["macro_f1"],
            ))
            print("%-10s  micro R=%.4f P=%.4f F1=%.4f   macro R=%.4f P=%.4f F1=%.4f" % (
                tool,
                a["micro_recall"], a["micro_precision"], a["micro_f1"],
                a["macro_recall"], a["macro_precision"], a["macro_f1"],
            ))
    print("wrote %s" % prf_csv)

    # Per-class P/R/F1 (writable scaffold for the Q1-paper table that
    # discusses per-class winners/losers and class-uniform F1).
    prf_class_csv = os.path.join(HERE, "..", "raw", "synth_prf_byclass.csv")
    with open(prf_class_csv, "w") as fh:
        fh.write("tool,klass,tp,fn,fp,precision,recall,f1\n")
        for tool, per in results.items():
            if per is None:
                continue
            a = aggregate_prf(per)
            for klass in sorted(a["per_class"].keys()):
                v = a["per_class"][klass]
                fh.write("%s,%s,%d,%d,%d,%.4f,%.4f,%.4f\n" % (
                    tool, klass, v["tp"], v["fn"], v["fp"],
                    v["precision"], v["recall"], v["f1"],
                ))
    print("wrote %s" % prf_class_csv)


if __name__ == "__main__":
    main()
