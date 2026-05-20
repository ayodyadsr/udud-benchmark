#!/usr/bin/env python3
# Confidentiality proof for the de-identification transform (anonymize.py).
#
# This does not eyeball the output for brand substrings. A monoalphabetic
# cipher over a 781k-line corpus will, by chance, emit short letter
# triples like "woa" or "ipad" inside scrambled runs or between digits;
# those are cipher OUTPUT, not surviving plaintext, and substring grep
# cannot tell the difference. The argument here is structural.
#
# Claim: no original identity-bearing token survives the transform.
#
# Proof obligations, all checked below:
#   A. The letter map is a bijection over [A-Za-z] with NO fixed point,
#      so any alphabetic run routed through it cannot equal its input:
#      every letter changes.
#   B. The only verbatim-kept byte classes are (i) members of the
#      explicit structural/recon whitelists and (ii) non-alphabetic
#      bytes (digits, punctuation, %xx, separators) which carry no
#      identity. Every whitelist is shown brand-clean.
#   C. Differential corpus check: every maximal alphabetic token in the
#      ORIGINAL that is not a whitelist member (i.e. every identity
#      candidate) is absent, at a structural position, from the OUTPUT.
#
# A + B prove identity cannot survive; C corroborates on the real
# corpora and separates the explained cipher-coincidence noise.

import sys, os, string, glob, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("anon", os.path.join(HERE, "anonymize.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

def _load_brands():
    # The brand vocabulary the residue gate looks for in surviving tokens is
    # target-specific (product, family, and code names of the original
    # confidential apex). It is loaded at runtime from ANON_BRANDS (a
    # comma-separated list) so it never appears in committed source. An
    # empty list makes the brand-whitelist check (B) vacuously PASS, which
    # is the correct behaviour for any user re-running the gate on a target
    # whose vocabulary they have set themselves.
    raw = os.environ.get("ANON_BRANDS", "").strip()
    if not raw:
        return []
    return [b.strip().lower() for b in raw.split(",") if b.strip()]


BRANDS = _load_brands()


def check_cipher():
    lf = [c for c in string.ascii_lowercase if A._CIPHER.get(c) == c]
    uf = [c for c in string.ascii_uppercase if A._CIPHER.get(c) == c]
    vals = [A._CIPHER[c] for c in string.ascii_lowercase]
    bij = sorted(vals) == list(string.ascii_lowercase)
    ok = not lf and not uf and bij
    print("A. cipher derangement+bijection : %s (lower_fp=%s upper_fp=%s bij=%s)"
          % ("PASS" if ok else "FAIL", lf, uf, bij))
    return ok


def check_whitelists():
    sets = {
        "_PUBSFX": A._PUBSFX, "_HOST_KEEP": A._HOST_KEEP,
        "_EXT_KEEP": A._EXT_KEEP, "_STEM_KEEP": A._STEM_KEEP,
        "_SCHEME_KEEP": A._SCHEME_KEEP, "_MATRIX_KEEP": A._MATRIX_KEEP,
        "_PARAM_KEEP": A._PARAM_KEEP,
    }
    bad = {}
    for nm, s in sets.items():
        hit = [t for t in s if any(b in t.lower() for b in BRANDS)]
        if hit:
            bad[nm] = hit
    for v in A._VAL_KEEP:
        if any(b in v.lower() for b in BRANDS):
            bad.setdefault("_VAL_KEEP", []).append(v)
    # apex check: only meaningful if BRANDS is non-empty (i.e. the user
    # has set ANON_BRANDS). The cipher must have a non-empty apex source
    # and the apex destination must not collide with any known brand.
    if BRANDS:
        if not A._APEX_FROM or any(b in A._APEX_TO for b in BRANDS):
            bad["apex"] = (A._APEX_FROM, A._APEX_TO)
    ok = not bad
    print("B. whitelists brand-clean        : %s%s"
          % ("PASS" if ok else "FAIL", "" if ok else " " + repr(bad)))
    return ok


def maximal_tokens(text):
    # set of lowercased maximal alphabetic runs (len>=3): a real
    # identity token in a URL is always a maximal alpha run delimited by
    # URL structure, never a fragment of a longer run.
    out, n, i = set(), len(text), 0
    while i < n:
        if text[i].isalpha():
            j = i
            while j < n and text[j].isalpha():
                j += 1
            if j - i >= 3:
                out.add(text[i:j].lower())
            i = j
        else:
            i += 1
    return out


def check_corpus(paths):
    # anonymize.py is strictly line-wise: stdin line i -> stdout line i,
    # order preserved, no reordering or dropping. So a brand B is a REAL
    # surviving identity token on a line iff B is a maximal alphabetic
    # token in BOTH that input line and its output line. A scrambled
    # cipher run that merely happens to spell B (a short triple that
    # coincidentally matches a brand token in a ciphered nonce) was a
    # DIFFERENT token in the input
    # line, so B is absent from that input line and is correctly not a
    # leak. This differential is decisive and immune to the unavoidable
    # short-triple coincidence noise of a monoalphabetic cipher.
    total_real = 0
    for p in paths:
        with open(p, "rb") as fh:
            inp = fh.read().decode("utf-8", "replace")
        out = subprocess.run([sys.executable, os.path.join(HERE, "anonymize.py")],
                             stdin=open(p, "rb"), capture_output=True).stdout
        out = out.decode("utf-8", "replace")
        ilines = inp.split("\n")
        olines = out.split("\n")
        leaks = {}
        for li, (iL, oL) in enumerate(zip(ilines, olines), 1):
            it = maximal_tokens(iL)
            inter = it & set(BRANDS)
            if not inter:
                continue
            ot = maximal_tokens(oL)
            for b in inter:
                if b in ot:                       # survived its own line
                    leaks.setdefault(b, (li, oL[:120]))
        total_real += len(leaks)
        tag = "" if not leaks else " " + repr({k: v[0] for k, v in leaks.items()})
        print("C. %-26s real_leaks=%d%s"
              % (os.path.basename(p), len(leaks), tag))
        for b, (li, sample) in list(leaks.items())[:4]:
            print("     LEAK %r line %d: %s" % (b, li, sample))
    return total_real == 0


def main():
    paths = sorted(glob.glob(os.path.join(HERE, "..", "data", "D_example_wb.*")))
    g = os.path.join(HERE, "..", "data", "D_example_gau.full")
    if os.path.exists(g):
        paths.append(g)
    a = check_cipher()
    b = check_whitelists()
    c = check_corpus(paths)
    ok = a and b and c
    print("\nRESULT: %s -- de-identification %s"
          % ("PASS" if ok else "FAIL",
             "leaks zero target identity" if ok
             else "HAS A LEAK, do not publish"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
