#!/usr/bin/env python3
"""Quality evaluation: security-surface retention (honest ground truth).

A URL de-duplicator is correct only if every *distinct, real* piece of
security-relevant surface in the input keeps at least one representative
in the output. Three things must NOT be conflated:

  (1) real surface  - a distinct .js/.html/source-disclosure file, a
      ;jsessionid= auth endpoint, a redirect/SSRF/LFI parameter, a real
      subdomain. Losing the whole class is destruction.
  (2) value variants - many URLs that differ only by an id / slug /
      title / session value / locale. Folding these to one
      representative is the deduper's job, NOT destruction.
  (3) scanner garbage - payload pseudo-URLs and mangled hosts. A clean
      tool dropping these is correct, NOT destruction.

So the ground-truth key for every class identifies a distinct
*endpoint-class template*, not a distinct value:

  - the path is templated: a digit run -> N, a UUID -> U, a hex>=12
    blob -> H. /2021/06/x.html and /2021/07/x.html collapse to the same
    template (a deduper SHOULD keep one; that is not a loss).
  - matrix params are keyed by NAME only (the ;jsessionid= *value* is
    stripped): every ...buystyle.css;jsessionid=<session> is one truth
    member. A tool that keeps any one survivor retains it; a tool that
    deletes the ;jsessionid= class entirely scores 0 (real destruction).
  - redirect/SSRF/LFI params are keyed by a tightened sink list (locale
    / pagination / tracking keys removed) and by name, not value.

retention = templated truth elements with >=1 survivor / templated
truth elements. This is the correct tool-independent definition of
non-destructive for a *structural* deduper: it rewards correct folding
and penalises only deletion of a whole class. It does NOT reward a tool
that "retains everything" by barely deduplicating - that shows up
instead in the compression ratio (out/in lines) reported by stats.py
and in `raw_distinct_cov` here (descriptive only).

The ground truth is also gated to well-formed URLs with valid hosts and
no URL-in-path injection, so scanner payloads do not inflate it.

--audit dumps the lost templated members per (corpus,tool,class) to
../raw/audit/ for hand classification before any claim is made.

stdlib only. Inputs: ../data/D_*.full and ../raw/outputs/<ds>.<tool>.out
Output: ../raw/quality.csv ../raw/origbytes.csv ../raw/coverage.csv
        ../raw/quality.txt  [+ ../raw/audit/* with --audit]
"""
import csv, os, re, sys, html as _html
from urllib.parse import urlsplit, parse_qsl, unquote

RAW  = os.path.join(os.path.dirname(__file__), "..", "raw")
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
OUT  = os.path.join(RAW, "outputs")
AUDIT_DIR = os.path.join(RAW, "audit")
AUDIT = "--audit" in sys.argv

CORPORA = ["D_example_wb.full", "D_vulnweb.full", "D_example_gau.full"]
TOOLS   = ["udud", "uro", "urldedupe", "urless", "uddup"]

SRC_EXT = {"bak","old","orig","save","swp","swo","tmp","temp","sql","db",
           "sqlite","mdb","zip","tar","gz","tgz","bz2","rar","7z","war",
           "jar","phps","inc","conf","config","cfg","ini","env","log",
           "pem","key","crt","p12","pfx","passwd","htpasswd"}
SRC_DIR = ("/.git/","/.svn/","/.hg/","/.env","/.git","/.svn","/.aws/",
           "/.ssh/")
# tightened redirect / SSRF / LFI sinks: the keys a pentester actually
# fuzzes. Ambiguous generic/locale/pagination/tracking keys (l,u,q,r,
# page,pg,site,view,to,data,img,src,...) are deliberately excluded so
# the metric is not dominated by locale/paging noise.
RI_KEYS = {"redirect","redirect_uri","redirect_url","redir","redirecturl",
           "url","returnurl","return_url","next","dest","destination",
           "continue","goto","forward","fromurl","file","filename",
           "filepath","include","document","load","template","callback",
           "feed","domain","fwd","rurl","checkout_url","image_url",
           "go","link_url","window"}

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                  r"[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HEX  = re.compile(r"^[0-9a-f]{12,}$", re.I)
# real matrix-URI params (RFC 3986) and Servlet ;jsessionid= names are
# plain tokens; a dotted name (;x.htmlFor= ;o.id= ;s.linkTrackVars=) is
# a JavaScript member expression captured by wayback, not surface, and
# is excluded from the ground truth for every tool alike.
MATRIX = re.compile(r";([A-Za-z0-9_\-]+)=[^;/]*")
HOSTLABEL = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)"
                       r"+[a-z]{2,63}$")
IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
BADURL = re.compile(r"""[\s<>"'`{}|\\^\[\]()]|%3c|%3e|%22|%27|script|alert\(""",
                    re.I)

def valid_host(h):
    if not h: return False
    if IPV4.match(h):
        return all(0 <= int(o) <= 255 for o in h.split("."))
    return bool(HOSTLABEL.match(h))

# Standard URL canonicalization applied IDENTICALLY to the ground truth
# and to every tool's output, so the metric measures "is this endpoint
# class still reachable" and never "did the tool keep my exact input
# bytes". This is RFC 3986 sec.6 syntax-based normalisation (scheme/host
# case, default port already dropped by urlsplit.hostname, percent
# decoding, path) plus the universally deployed DirectoryIndex
# convention (/foo/index.html == /foo/ == /foo) and HTML entity
# unescaping (&amp; -> &). It is tool-independent: a tool that DELETES a
# whole class still scores 0 because a removed line cannot be
# normalised back; it only stops penalising a tool for canonicalising.
INDEX_RE = re.compile(r"/(?:index|default|home)\.(?:html?|php[0-9]?|aspx?|"
                      r"jsp|jspx|do|action|cfm|cgi|pl|py)$", re.I)

def _remove_dot_segments(path):
    """RFC 3986 sec.5.2.4 path-only dot-segment removal: /a/../b -> /b,
    /a/./b -> /a/b. Applies to the PATH component only, never to a
    query value, so an LFI payload ?file=../../etc/passwd is untouched."""
    out = []
    for seg in path.split("/"):
        if seg == "..":
            if out: out.pop()
        elif seg != ".":
            out.append(seg)
    res = "/".join(out)
    if path.startswith("/") and not res.startswith("/"): res = "/" + res
    return res or "/"

def canon_path(path):
    """RFC3986 + DirectoryIndex canonical path used for every key.
    percent-decoded per segment (an encoded %2F stays inside its
    segment, never re-splits), dot-segments removed, trailing index
    file and trailing slash collapsed so /a/b/index.html, /a/b/ and
    /a/b are one endpoint."""
    path = _remove_dot_segments(path)
    path = INDEX_RE.sub("", path)
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"

def parts(line):
    u = line.strip()
    if not u: return None
    raw = u
    u = _html.unescape(u)               # &amp; -> & (udud does this; symmetric)
    if "://" not in u: u = "http://" + u
    try: s = urlsplit(u)
    except ValueError: return None
    host = (s.hostname or "").lower()    # default :80/:443 already dropped
    path = s.path or "/"
    return s, host, path, raw

def seg_t(seg):
    seg = unquote(seg)                   # %2e -> .  etc. (symmetric)
    if seg.isdigit(): return "N"
    if UUID.match(seg): return "U"
    if HEX.match(seg):  return "H"
    return seg.lower()

def tpath(path, strip_matrix=False):
    """templated path. value variants (digits/uuid/hex) collapse; with
    strip_matrix the ;k=v matrix parts are removed from each segment."""
    out = []
    for seg in path.split("/"):
        if seg == "": continue
        if strip_matrix:
            seg = MATRIX.sub("", seg)
            seg = re.sub(r";+$", "", seg)
        out.append(seg_t(seg))
    return "/".join(out)

LOSS_CLASSES = ["host","js","html","srcdisc","matrix","param_ri"]

def classify(line):
    """class -> (template_key, raw_key). template_key is the fair
    tool-independent identity; raw_key is host+raw-path for the
    descriptive raw-distinct coverage. `endpoint` is always recorded."""
    p = parts(line)
    if p is None: return {}
    s, host, path, raw = p
    out = {}
    cp  = canon_path(path)              # RFC3986 + DirectoryIndex canonical
    sig = host + "/" + tpath(cp)        # canonical endpoint signature
    if host:
        out["endpoint"] = (sig, None)
    path_injection = "://" in path
    if (BADURL.search(raw) or not valid_host(host) or path_injection):
        return out
    rawk = host + path
    out["host"] = (host, host)
    # class membership is decided on the RAW last segment (a
    # /dir/app.js is a js endpoint) but the KEY is the canonical
    # endpoint signature, so a tool that emits the page in its
    # canonical directory form (/dir/index.html -> /dir) still scores
    # as retaining it -- only true deletion is a loss.
    last = path.rsplit("/", 1)[-1]
    base = MATRIX.sub("", last)
    ext  = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if ext == "js":            out["js"]   = (sig, rawk)
    if ext in ("htm","html"):  out["html"] = (sig, rawk)
    if ext in SRC_EXT or any(d in path for d in SRC_DIR):
        out["srcdisc"] = (sig, rawk)
    # matrix is matched against the tool's matrix set on purpose: the
    # security artefact is the session-token-in-URL itself, so only a
    # tool that still emits a ;name= URL for this endpoint+name class
    # retains it; the per-session VALUE is stripped (thousands of
    # ;jsessionid=<sid> are one truth member, correct to fold).
    mk = MATRIX.findall(path)
    if mk:
        out["matrix"] = (host + "/" + tpath(cp, strip_matrix=True) + ";"
                         + ",".join(sorted(k.lower() for k in mk)), rawk)
    qk = sorted({k.lower() for k, _ in parse_qsl(_html.unescape(s.query),
                 keep_blank_values=True)} & RI_KEYS)
    if qk:
        out["param_ri"] = (host + "/" + tpath(cp) + "?" + ",".join(qk), rawk)
    return out

def signature(host, path):
    return host + "/" + tpath(canon_path(path))

def keyset(path_to_file, keep_examples=False):
    tk = {c: set() for c in LOSS_CLASSES + ["endpoint"]}
    rk = {c: set() for c in LOSS_CLASSES}
    ex = {c: {} for c in LOSS_CLASSES} if keep_examples else None
    lines = set()
    with open(path_to_file, "r", errors="replace") as f:
        for ln in f:
            lines.add(ln.rstrip("\n"))
            for c, kv in classify(ln).items():
                key = kv[0]
                tk[c].add(key)
                if c in rk and kv[1] is not None:
                    rk[c].add(kv[1])
                if ex is not None and c in ex and key not in ex[c]:
                    ex[c][key] = ln.rstrip("\n")
    return tk, rk, lines, ex

def main():
    os.makedirs(AUDIT_DIR, exist_ok=True)
    qrows, orows, crows = [], [], []
    for ds in CORPORA:
        ipath = os.path.join(DATA, ds)
        if not os.path.exists(ipath):
            print(f"skip {ds}: no input", file=sys.stderr); continue
        T, TR, in_lines, examples = keyset(ipath, keep_examples=AUDIT)
        for tool in TOOLS:
            opath = os.path.join(OUT, f"{ds}.{tool}.out")
            if not os.path.exists(opath):
                qrows.append(dict(dataset=ds, tool=tool, klass="-",
                    truth=0, kept=0, retained_pct="", raw_truth=0,
                    raw_kept=0, raw_cov_pct="", note="no output (DNF/missing)"))
                continue
            K, KR, o_lines, _ = keyset(opath)
            # js/html/srcdisc keys ARE canonical endpoint signatures, so
            # they are matched against the tool's full endpoint set: a
            # page kept in its canonical directory form still counts as
            # retained. host/matrix/param_ri keep their own class set
            # (matrix deliberately requires a surviving ;name= URL).
            for c in LOSS_CLASSES:
                ktarget = K["endpoint"] if c in ("js","html","srcdisc") else K[c]
                t  = len(T[c]);  kept  = len(T[c]  & ktarget)
                rt = len(TR[c]); rkept = len(TR[c] & KR[c])
                qrows.append(dict(dataset=ds, tool=tool, klass=c,
                    truth=t, kept=kept,
                    retained_pct=round(100.0*kept/t, 3) if t else "",
                    raw_truth=rt, raw_kept=rkept,
                    raw_cov_pct=round(100.0*rkept/rt, 3) if rt else "",
                    note=("LOSS" if t and kept < t else "")))
                if AUDIT and t and kept < t:
                    lost = sorted(T[c] - ktarget)
                    with open(os.path.join(AUDIT_DIR,
                              f"{ds}.{tool}.{c}.lost"), "w") as af:
                        for k in lost:
                            af.write(examples[c].get(k, k) + "\n")
            crows.append(dict(dataset=ds, tool=tool,
                in_endpoints=len(T["endpoint"]),
                out_endpoints=len(K["endpoint"]),
                endpoint_coverage_pct=round(
                    100.0*len(T["endpoint"] & K["endpoint"]) /
                    len(T["endpoint"]), 3) if T["endpoint"] else ""))
            verb = sum(1 for L in o_lines if L in in_lines)
            tot  = len(o_lines)
            orows.append(dict(dataset=ds, tool=tool,
                out_distinct_lines=tot, verbatim_input_lines=verb,
                verbatim_pct=round(100.0*verb/tot, 3) if tot else "",
                emits_original=("yes" if tot and verb == tot else "no")))

    def dump(name, rows, fields):
        with open(os.path.join(RAW, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            for r in rows: w.writerow(r)
    dump("quality.csv", qrows,
         ["dataset","tool","klass","truth","kept","retained_pct",
          "raw_truth","raw_kept","raw_cov_pct","note"])
    dump("origbytes.csv", orows,
         ["dataset","tool","out_distinct_lines","verbatim_input_lines",
          "verbatim_pct","emits_original"])
    dump("coverage.csv", crows,
         ["dataset","tool","in_endpoints","out_endpoints",
          "endpoint_coverage_pct"])

    with open(os.path.join(RAW,"quality.txt"),"w") as f:
        cur=None
        for r in qrows:
            tag=(r["dataset"],r["tool"])
            if tag!=cur:
                cur=tag; f.write(f"\n--- {r['dataset']} / {r['tool']} ---\n")
            if r["klass"]=="-":
                f.write(f"  {r['note']}\n"); continue
            f.write(f"  {r['klass']:<9} truth={r['truth']:>6} "
                    f"kept={r['kept']:>6} retained={r['retained_pct']}%"
                    f"   (raw-distinct {r['raw_cov_pct']}%)  {r['note']}\n")
        f.write("\n=== endpoint coverage (descriptive, not a loss metric) ===\n")
        for r in crows:
            f.write(f"  {r['dataset']:<18} {r['tool']:<10} "
                    f"in={r['in_endpoints']:>7} out={r['out_endpoints']:>7} "
                    f"cov={r['endpoint_coverage_pct']}%\n")
        f.write("\n=== emits original URL bytes ===\n")
        for r in orows:
            f.write(f"  {r['dataset']:<18} {r['tool']:<10} "
                    f"verbatim={r['verbatim_pct']}%  "
                    f"emits_original={r['emits_original']}\n")
    print("wrote raw/quality.csv raw/origbytes.csv raw/coverage.csv "
          "raw/quality.txt" + (" + raw/audit/*" if AUDIT else ""))
    print(open(os.path.join(RAW,"quality.txt")).read())

if __name__ == "__main__":
    main()
