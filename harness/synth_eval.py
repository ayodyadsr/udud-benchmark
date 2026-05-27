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

    Some tools (notably xcull) blank a sink param value as part of the
    signature canonicalisation: the output URL is /page?file= rather
    than /page?file=<payload>. The endpoint+param-name surface is the
    same as the input; the classifier must not lose it."""
    return _parse_qs(q, keep_blank_values=True)

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(HERE, "..", "data", "D_unified.full")
TRUTH = os.path.join(HERE, "..", "data", "D_unified.truth.json")


# RFC 3986 directory-index equivalence: /dir/index.html resolves to /dir/
# on every common web server, so a deduper that strips the index file is
# correct. The eval used to treat /druid/index.html and /druid as different
# canonical groups, which counted a correct strip as a false merge. This
# function canonicalizes both the truth groups (at load time) and the
# tool's output paths (in classify) under the same rule. The accepted index
# files are the ones xcull's own is_index() recognises.
_INDEX_RE = re.compile(r"/(?:index|default)\.(?:html?|php|aspx?|jsp)$", re.I)

def _canon_path(p):
    if not p:
        return p
    p = _INDEX_RE.sub("", p) or "/"
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def load_truth():
    with open(TRUTH) as fh:
        t = json.load(fh)
    # Canonicalize the GENUINE_DISTINCT list so that index-file forms
    # collapse to their directory form; recompute n_canonical_groups in
    # case the original list contained both /dir/ and /dir/index.html.
    gd = t.get("GENUINE_DISTINCT")
    if gd and "groups" in gd:
        canon = sorted({_canon_path(g) for g in gd["groups"]})
        gd["groups"] = canon
        gd["n_canonical_groups"] = len(canon)
    return t


# ---- enumeration-aware scoring (v2 extension) ----
#
# The existing canonical-group metric (synth_eval.csv + synth_prf*.csv) treats
# every keep BEYOND the first as a false positive. That fairly answers the
# question "did the tool keep at least one representative per endpoint
# template?". It DOES NOT answer the recon-pipeline question "did the tool
# preserve enumeration paths whose distinct values each represent a distinct
# attack target (IDOR/object enumeration, rotating-session probing, content-
# addressed lookup)?". For those classes, every distinct VALUE in the input is
# its own surface element, and folding 5000 distinct UUIDs to one witness
# DELETES 4999 attack targets from every downstream scan.
#
# ENUMERABLE_CLASSES lists the classes where each distinct value is its own
# surface element. For those classes the recon-aware view uses object-level
# recall (distinct values kept / distinct values in input). For every other
# class the recon-aware view reuses the existing canonical-group view, so the
# two metrics agree on collapsible and 1:1 surface classes.
#
# The choice is per-class and per-dataset: a /product/<N> path under a
# content-section parent is a templated listing where folding is correct
# (NUMERIC_ID stays OUT of enumerable here, matching xcull's default-mode
# content-section template). A /order/<uuid> path under no content-section
# parent IS an enumerable object surface (UUID stays IN). HEX_HASH and
# JSESSIONID are kept enumerable because the synth corpus uses them as
# distinct object identifiers and rotating session tokens respectively,
# both of which a recon pipeline tests value-by-value.
ENUMERABLE_CLASSES = {"UUID", "HEX_HASH", "JSESSIONID"}

# extract the object value for an enumerable class so two outputs that keep
# the same {uuid, hex, jsessionid} value collapse to one. used only for the
# recon-aware count; the canonical view never calls this.
def object_value(klass, url):
    if klass == "UUID":
        m = re.search(r"/order-\d+/([0-9a-fA-F-]{32,36})", url)
        return m.group(1).lower() if m else None
    if klass == "HEX_HASH":
        m = re.search(r"/asset-\d+/([0-9a-fA-F]{64})", url)
        return m.group(1).lower() if m else None
    if klass == "JSESSIONID":
        m = re.search(r";jsessionid=([^;/?&]+)", url, re.I)
        return m.group(1) if m else None
    return None


# bases used for the templated enumeration classes. Kept in sync with
# synth_gen_v2.py: a change there must change the bases here.
NUMERIC_ID_BASES = ("product", "item", "post", "comment", "order-item",
                    "report", "ticket", "issue", "task", "review")
CACHE_BASES = ("main", "app", "vendor", "runtime", "polyfill")

_NUMERIC_RE = re.compile(
    r"^/(" + "|".join(NUMERIC_ID_BASES) + r")-(\d+)/(\d+)/?$"
)
_UUID_RE      = re.compile(r"^/order-(\d+)/[0-9a-fA-F-]{32,36}/?$")
_HEX_RE       = re.compile(r"^/asset-(\d+)/[0-9a-fA-F]{64}/?$")
_SLUG_RE      = re.compile(r"^/blog-(\d+)/[a-z][a-z0-9-]+-\d+/?$")
_CACHE_RE     = re.compile(
    r"^/(" + "|".join(CACHE_BASES) + r")-(\d+)\.js$"
)
_AUTH_RE      = re.compile(r"^/auth-(\d+)(;.*)?$", re.I)
_REDIR_RE     = re.compile(r"^/redir-(\d+)$")
_PAGE_RE      = re.compile(r"^/page-(\d+)$")
_API_RE       = re.compile(r"^/api-(\d+)$")
_WIDGET_RE    = re.compile(r"^/widget(\d+)/?$")


def _build_srcdisc_set():
    bases = [
        ".env", ".env.production", ".env.local", ".env.staging", ".env.development",
        ".git/config", ".git/HEAD", ".git/index", ".git/logs/HEAD",
        "db.sql", "backup.sql", "dump.sql", "database.sql", "data.sql",
        "backup.zip", "backup.tar.gz", "backup.tar", "backup.7z",
        "index.php.bak", "config.php.bak", "wp-config.php.bak",
        "config.bak", "settings.bak", "app.bak",
        ".htaccess.bak", ".htpasswd",
        "config.php.swp", ".DS_Store",
        "credentials.json", "secrets.yml", "secrets.json", "vault.yml",
        ".aws/credentials", ".ssh/id_rsa", ".ssh/id_ed25519",
        "WEB-INF/web.xml.bak", "META-INF/context.xml.bak",
        "private.pem", "server.key", "ca.crt",
    ]
    projects = ["", "/app", "/web", "/site", "/portal"]
    out = set()
    for proj in projects:
        for f in bases:
            out.add("%s/%s" % (proj, f) if proj else "/%s" % f)
    return out


SRCDISC_SET = _build_srcdisc_set()


def classify(url):
    try:
        p = urlparse(url.strip())
    except Exception:
        return None
    path = p.path or ""
    q = p.query or ""

    # NUMERIC_ID: /<base>-<n>/<digits>
    m = _NUMERIC_RE.match(path)
    if m:
        return ("NUMERIC_ID", "%s-%s" % (m.group(1), m.group(2)))
    # UUID: /order-<n>/<uuid4>
    m = _UUID_RE.match(path)
    if m:
        return ("UUID", "order-%s" % m.group(1))
    # HEX_HASH: /asset-<n>/<64-hex>
    m = _HEX_RE.match(path)
    if m:
        return ("HEX_HASH", "asset-%s" % m.group(1))
    # TITLE_SLUG: /blog-<n>/<slug-words-N>
    m = _SLUG_RE.match(path)
    if m:
        return ("TITLE_SLUG", "blog-%s" % m.group(1))
    # CACHE_BUST: /<filebase>-<n>.js with empty/`_`-keyed query
    m = _CACHE_RE.match(path)
    if m:
        keys = set(parse_qs(q).keys())
        if "_" in keys or not q:
            return ("CACHE_BUST", "%s-%s.js" % (m.group(1), m.group(2)))
    # JSESSIONID: /auth-<n>;jsessionid=<sid>  (also catches plain /auth-N if a
    # tool stripped the matrix parameter, which still folds to one group)
    if ";jsessionid=" in url.lower():
        m = _AUTH_RE.match(path)
        if m:
            return ("JSESSIONID", "auth-%s" % m.group(1))
    elif _AUTH_RE.match(path) and ";" in path:
        m = _AUTH_RE.match(path)
        return ("JSESSIONID", "auth-%s" % m.group(1))
    # OPEN_REDIRECT: /redir-<n> with empty or url= query
    m = _REDIR_RE.match(path)
    if m:
        keys = set(parse_qs(q).keys())
        if "url" in keys or not q:
            return ("OPEN_REDIRECT", "redir-%s" % m.group(1))
    # LFI_PARAM: /page-<n> with empty or file= query
    m = _PAGE_RE.match(path)
    if m:
        keys = set(parse_qs(q).keys())
        if "file" in keys or not q:
            return ("LFI_PARAM", "page-%s" % m.group(1))
    # PARAM_ORDER: /api-<n> with empty or {a,b} query
    m = _API_RE.match(path)
    if m:
        keys = set(parse_qs(q).keys())
        if keys == {"a", "b"} or keys == set():
            return ("PARAM_ORDER", "api-%s" % m.group(1))
    # TRAILING_SLASH: /widget<n>[/]
    m = _WIDGET_RE.match(path)
    if m:
        return ("TRAILING_SLASH", "widget%s" % m.group(1))
    # SRCDISC: known set
    if path in SRCDISC_SET:
        return ("SRCDISC", path)
    # GENUINE_DISTINCT: any other path in the synth host - fall through
    # to the ground-truth list. Canonicalize under the same index/slash
    # rule load_truth() applies so a tool that emits /dir matches a truth
    # entry of /dir/index.html (RFC 3986 directory-index equivalence).
    return ("GENUINE_DISTINCT", _canon_path(path))


def evaluate_output(out_path, truth):
    """Return per-class {surviving_groups, kept_urls, total_groups,
    distinct_values_kept}. distinct_values_kept is the count of unique
    object values seen in the output for ENUMERABLE_CLASSES (used by the
    recon-aware view); for non-enumerable classes it equals surviving
    groups so the two views agree."""
    by_class = {}                                # class -> set(group_id)
    kept_urls = {}                               # class -> count
    by_value = {}                                # class -> set(object_value)
    gd_groups = set(truth.get("GENUINE_DISTINCT", {}).get("groups", []))

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
            # restrict GENUINE_DISTINCT to the ground-truth set (O(1) lookup
            # matters when GENUINE_DISTINCT carries tens of thousands of
            # groups in the unified corpus).
            if klass == "GENUINE_DISTINCT":
                if gid not in gd_groups:
                    continue
            by_class.setdefault(klass, set()).add(gid)
            kept_urls[klass] = kept_urls.get(klass, 0) + 1
            if klass in ENUMERABLE_CLASSES:
                ov = object_value(klass, url)
                if ov is not None:
                    by_value.setdefault(klass, set()).add(ov)

    out = {}
    for klass, meta in truth.items():
        total = meta["n_canonical_groups"]
        kept = len(by_class.get(klass, set()))
        urls_kept = kept_urls.get(klass, 0)
        distinct_values = (len(by_value.get(klass, set()))
                           if klass in ENUMERABLE_CLASSES else kept)
        out[klass] = {
            "total_groups": total,
            "surviving_groups": kept,
            "destroyed_groups": total - kept,
            "kept_urls": urls_kept,
            "distinct_values_kept": distinct_values,
            "recall": kept / total if total else 0.0,
            "over_keep_ratio": (urls_kept / kept) if kept else None,
            "lossless": (kept == total),
        }
    return out


def run_tool(tool, input_path, out_dir):
    name = tool
    out = os.path.join(out_dir, "D_unified.full.%s.out" % name)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out, None
    bin_path = {
        "xcull": "/usr/local/bin/xcull",
        "uro": "uro",
        "urldedupe": "urldedupe",
        "urless": "urless",
        "uddup": "uddup",
    }[name]
    try:
        if name == "uddup":
            # uddup is O(n^2). On the 780k unified corpus it cannot finish;
            # we still call it so the DNF is measured, with a tight cap.
            proc = subprocess.run([bin_path, "-u", input_path],
                                  capture_output=True, timeout=120)
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
    except subprocess.TimeoutExpired:
        # write an empty file so the caller treats this as DNF without
        # crashing the rest of the eval.
        with open(out, "wb") as fh:
            pass
        return out, b"TIMEOUT"
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


def count_input_object_values(input_path):
    """Count distinct object values present in the input for every
    ENUMERABLE_CLASSES member. Returns {class: n_distinct_input_values}.
    This is the denominator for object-level recall."""
    seen = {k: set() for k in ENUMERABLE_CLASSES}
    with open(input_path, "rb") as fh:
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
            klass, _ = label
            if klass in ENUMERABLE_CLASSES:
                ov = object_value(klass, url)
                if ov is not None:
                    seen[klass].add(ov)
    return {k: len(v) for k, v in seen.items()}


def aggregate_prf_recon(per_class, input_distinct):
    """Recon-aware aggregation. Identical to aggregate_prf for non-
    enumerable classes; for ENUMERABLE_CLASSES the unit is one distinct
    object value (not one canonical group), and only TRUE duplicate
    emissions of the same value count as FP.

    For an enumerable class:
      TP_recon = distinct values kept in output
      FN_recon = distinct values in input that did NOT survive
      FP_recon = kept_urls - distinct values kept   (same-value duplicates)
      Recall   = kept_distinct / input_distinct     "did the enumeration survive?"
      Precision= kept_distinct / kept_urls          "is the output free of dupes?"

    A tool that folds 5000 distinct UUIDs to one canonical witness gets
    recall = 1/5000 here (the recon-honest score), even though it scores
    1.0 under the canonical-group view in aggregate_prf."""
    tp_t = fn_t = fp_t = kept_t = 0
    p_sum = r_sum = f_sum = 0.0
    n_classes = 0
    per = {}
    for klass, v in per_class.items():
        if klass in ENUMERABLE_CLASSES:
            in_distinct = input_distinct.get(klass, v["total_groups"])
            tp = v["distinct_values_kept"]
            fn = max(0, in_distinct - tp)
            fp = max(0, v["kept_urls"] - tp)
        else:
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
    input_distinct = count_input_object_values(INPUT)

    results = {}
    for tool in ["xcull", "uro", "urldedupe", "urless", "uddup"]:
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

    # ---- recon-aware view ---------------------------------------------
    # Same shape as the strict files above, but for ENUMERABLE_CLASSES the
    # unit is one distinct object value, not one canonical group. A tool
    # that preserves IDOR enumeration (every distinct UUID/HEX/JSESSIONID
    # survives) scores high here; a tool that folds all 5000 distinct
    # UUIDs into one canonical witness scores ~0. Non-enumerable classes
    # are identical to the strict view, so the two metrics agree wherever
    # value-level distinctness is not a recon question.
    prf_recon_csv = os.path.join(HERE, "..", "raw", "synth_prf_recon.csv")
    with open(prf_recon_csv, "w") as fh:
        fh.write("tool,canonical_groups,tp,fn,fp,kept_urls,"
                 "micro_precision,micro_recall,micro_f1,"
                 "macro_precision,macro_recall,macro_f1\n")
        for tool, per in results.items():
            if per is None:
                fh.write("%s,DNF,,,,,,,,,,\n" % tool)
                continue
            a = aggregate_prf_recon(per, input_distinct)
            fh.write("%s,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n" % (
                tool, a["canonical_groups"], a["tp"], a["fn"], a["fp"],
                a["kept_urls"],
                a["micro_precision"], a["micro_recall"], a["micro_f1"],
                a["macro_precision"], a["macro_recall"], a["macro_f1"],
            ))
            print("%-10s  recon  micro R=%.4f P=%.4f F1=%.4f   macro R=%.4f P=%.4f F1=%.4f" % (
                tool,
                a["micro_recall"], a["micro_precision"], a["micro_f1"],
                a["macro_recall"], a["macro_precision"], a["macro_f1"],
            ))
    print("wrote %s" % prf_recon_csv)

    prf_recon_byclass_csv = os.path.join(HERE, "..", "raw",
                                         "synth_prf_recon_byclass.csv")
    with open(prf_recon_byclass_csv, "w") as fh:
        fh.write("tool,klass,enumerable,tp,fn,fp,precision,recall,f1\n")
        for tool, per in results.items():
            if per is None:
                continue
            a = aggregate_prf_recon(per, input_distinct)
            for klass in sorted(a["per_class"].keys()):
                v = a["per_class"][klass]
                fh.write("%s,%s,%s,%d,%d,%d,%.4f,%.4f,%.4f\n" % (
                    tool, klass,
                    "yes" if klass in ENUMERABLE_CLASSES else "no",
                    v["tp"], v["fn"], v["fp"],
                    v["precision"], v["recall"], v["f1"],
                ))
    print("wrote %s" % prf_recon_byclass_csv)


if __name__ == "__main__":
    main()
