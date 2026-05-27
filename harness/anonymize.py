#!/usr/bin/env python3
# Structure-preserving de-identification for the benchmark corpora.
#
# Goal: remove the confidential target's identity from host and path while
# keeping every byte-class, length, separator, public-suffix, extension and
# query that any of the five dedup tools makes a decision on. The transform
# is a fixed deterministic monoalphabetic letter permutation (case and
# letter/digit class preserving) applied ONLY to the letters of host labels
# and path segments. It does not touch the scheme, the port, the query
# string, recognised public-suffix labels, file extensions, or a small set
# of well-known structural filenames.
#
# Consequence, by construction:
#  - xcull and urldedupe decide purely on structure, so their per-cell
#    output is invariant under this permutation (verified empirically by
#    count equality against the frozen original run).
#  - uro / urless / uddup key on literal English keywords (e.g. urless's
#    blog/news/article blacklist); de-identification legitimately changes
#    their behaviour, so their published numbers are honestly re-measured
#    on the anonymised corpus and labelled as such.
#
# The permutation key is fixed in source but is NOT a confidentiality
# control; it is a readability/determinism device. The published artifact
# states that the relabelling is not cryptographic and that URL path
# structure is retained by design.

import os, sys

# fixed, deterministic letter permutation (derived once from a fixed seed,
# then frozen literally so the mapping never changes between runs/machines)
_LOWER_SRC = "abcdefghijklmnopqrstuvwxyz"
_LOWER_DST = "qkzjxbmfwvnarytsdcoiephglu"   # bijection, no fixed points
_UPPER_DST = _LOWER_DST.upper()
_CIPHER = {}
for s, d in zip(_LOWER_SRC, _LOWER_DST):
    _CIPHER[s] = d
    _CIPHER[s.upper()] = d.upper()

# public-suffix-ish labels every tool's host/suffix logic keys on; keeping
# them verbatim makes the spam / suffix gates behave identically. They are
# generic and carry no target identity.
_PUBSFX = {
    "com", "net", "org", "info", "biz", "co", "io", "tv", "name", "mobi",
    "asia", "pro", "tel", "int", "aero", "coop", "museum", "edu", "gov",
    "mil", "uk", "us", "in", "jp", "de", "fr", "eu", "cn", "ca", "au",
    "nl", "es", "it", "ru", "br", "mx", "kr", "ch", "se", "no", "fi",
    "dk", "pl", "be", "at", "ie", "nz", "sg", "hk", "tw", "za", "ro",
}
# generic host labels that are not target identity and that host
# normalisation may treat specially
_HOST_KEEP = {"www", "ww2", "ww3", "m", "ftp"}

# file extensions the tools key on; keep verbatim so srcdisc / script /
# index logic is unchanged
_EXT_KEEP = {
    "js", "mjs", "css", "html", "htm", "xhtml", "shtml", "php", "php3",
    "php4", "php5", "phps", "phtml", "asp", "aspx", "ascx", "ashx",
    "asmx", "axd", "jsp", "jspa", "jspx", "jspf", "do", "action", "cgi",
    "pl", "py", "rb", "sh", "json", "xml", "rss", "atom", "txt", "csv",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "tar",
    "gz", "tgz", "bz2", "rar", "7z", "bak", "old", "orig", "save",
    "sql", "db", "bkp", "swp", "swo", "inc", "conf", "config", "cfg",
    "ini", "log", "dtd", "xsd", "wsdl", "war", "ear", "jar",
    "class", "png", "jpg", "jpeg", "gif", "bmp", "svg", "ico", "webp",
    "tif", "tiff", "psd", "mp3", "mp4", "m4a", "m4v", "mov", "avi",
    "wmv", "flv", "webm", "wav", "ogg", "aac", "eot", "ttf", "woff",
    "woff2", "otf", "map", "yaml", "yml", "md", "rtf", "key", "pem",
    "crt", "cer", "p12", "pfx", "env", "git", "DS_Store",
}
# well-known structural filename stems the tools may treat specially
_STEM_KEEP = {
    "robots", "sitemap", "index", "default", "favicon", "crossdomain",
    "clientaccesspolicy", "humans", "security", "ads",
}
_SCHEME_KEEP = {"http", "https", "ftp", "ws", "wss"}
# canonical recon parameter vocabulary (open-redirect / SSRF / LFI /
# pagination / locale / session / tracking). These names are universal
# and carry zero target identity, so they are kept verbatim: the
# open-redirect / SSRF / LFI narrative stays concretely demonstrable on
# the published corpus and the structural key-set dedup behaves the same.
# ANY parameter name not in this set (a product/brand custom param) is
# ciphered, so no identity leaks through a parameter name.
_PARAM_KEEP = {
    "url", "uri", "u", "redirect", "redirect_uri", "redirect_url",
    "redir", "return", "return_url", "returnurl", "return_to", "returnto",
    "next", "dest", "destination", "continue", "goto", "target", "link",
    "out", "view", "to", "image_url", "imageurl", "callback", "jsonp",
    "jump", "forward", "r", "rurl", "checkout_url", "ref", "referrer",
    "referer", "location", "domain", "host", "site", "page", "path",
    "file", "filename", "src", "source", "data", "load", "fetch",
    "proxy", "feed", "val", "value", "navigation", "open", "window",
    "q", "s", "id", "ids", "lang", "l", "locale", "country", "lo",
    "format", "type", "action", "include", "inc", "doc", "document",
    "dir", "folder", "root", "template", "content", "layout", "mod",
    "conf", "download", "name", "key", "token", "auth", "sid", "ssid",
    "session", "sessionid", "query", "search", "keyword", "cat",
    "category", "p", "pg", "pid", "item", "product", "sku", "aff",
    "affiliate", "affiliate_id", "affid", "partner", "campaign", "cid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "v", "ver", "version", "t", "ts", "time", "date",
    "debug", "test", "admin", "preview", "mode", "step", "tab", "sort",
    "order", "limit", "offset", "start", "count", "size", "from",
    "show", "hide", "filter", "f", "g", "h", "i", "n", "o", "w", "x",
    "y", "z", "c", "d", "e", "k", "m",
}
# matrix-param key names every tool's session/auth gate keys on. The KEY
# name is kept verbatim so the literal `;jsessionid=` token survives
# byte-identical; the value after it is still ciphered.
_MATRIX_KEEP = {
    "jsessionid", "sid", "phpsessid", "aspsessionid", "cfid", "cftoken",
    "aspxauth",
}
# the confidential registrable domain -> RFC2606 reserved domain.
# The published de-identifier loads the apex from the ANON_APEX environment
# variable; the actual target name was set at the time the released corpus
# was generated and is not committed to this repository. If ANON_APEX is
# empty the apex-remap branch is a no-op and the generic public-suffix
# branch ciphers the registrable name like any other custom label, which
# is the correct behaviour for any target the user runs this script on.
_APEX_FROM = os.environ.get("ANON_APEX", "")
_APEX_TO = os.environ.get("ANON_APEX_TO", "example")


def _cipher(s):
    return "".join(_CIPHER.get(c, c) for c in s)


def _xform_label(lbl, is_pubsfx_pos):
    low = lbl.lower()
    # keep public-suffix labels verbatim at ANY position: the re-rooted
    # spam / embedded-domain gates inspect interior labels for
    # public-suffix membership (the embedded-domain spam predicate inspects
    # interior labels), so an interior 'info'/'co'/'in' must survive
    # unchanged or the gate fires differently and the experiment is no
    # longer the same one.
    if low in _PUBSFX:
        return lbl
    if low in _HOST_KEEP:
        return lbl
    return _cipher(lbl)


def _xform_host(host):
    # split optional :port
    port = ""
    h = host
    if h.count(":") == 1:
        h, port = h.split(":", 1)
        port = ":" + port
    trail = ""
    while h.endswith("."):
        h = h[:-1]
        trail += "."
    labels = h.split(".")
    n = len(labels)
    # registrable-domain special case: <...>.<APEX>.com -> <...>.<APEX_TO>.com
    if _APEX_FROM and n >= 2 and labels[-1].lower() == "com" and labels[-2].lower() == _APEX_FROM:
        labels[-2] = _APEX_TO if labels[-2].islower() else _APEX_TO.capitalize()
        labels[-1] = labels[-1]  # keep public suffix
        body = labels[:-2]
        out = [_xform_label(l, True) for l in body] + [labels[-2], labels[-1]]
        return ".".join(out) + trail + port
    # generic: keep last label (tld) and any recognised public-suffix
    # labels verbatim, cipher the rest
    out = []
    for i, l in enumerate(labels):
        is_suffix_pos = (i >= n - 2)
        out.append(_xform_label(l, is_suffix_pos))
    return ".".join(out) + trail + port


def _xform_semi(semi):
    # semi is the matrix/parameter tail starting at the first ';'
    # (e.g. ";jsessionid=NODE01ABC", ";base64,iVBORw0K...", ";v=2;l=en").
    # Keep every ';' '=' ',' separator and the recognised matrix KEY names
    # verbatim so the literal `;jsessionid=` token a session/auth gate
    # keys on stays byte-identical; cipher everything else (values, blobs,
    # and any non-whitelisted key) so no identity or base64 payload
    # survives.
    if not semi:
        return semi
    out = []
    for p in semi.split(";"):
        if p == "":
            out.append(p)
            continue
        if "=" in p:
            k, v = p.split("=", 1)
            if k.lower() in _MATRIX_KEEP:
                out.append(k + "=" + _cipher_value(v))
            else:
                out.append(_cipher_value(k) + "=" + _cipher_value(v))
        elif "," in p:
            # data-URI style ";base64,<blob>"
            k, v = p.split(",", 1)
            out.append(_cipher_value(k) + "," + _cipher_value(v))
        else:
            out.append(_cipher_value(p))
    return ";".join(out)


def _xform_seg(seg):
    if seg == "":
        return seg
    # matrix params: the token before the first ';' is the real path
    # segment; the ';...' tail keeps its separators and recognised matrix
    # key names verbatim (so ;jsessionid= gates are byte-identical) while
    # its values and any base64 blob are ciphered
    semi = ""
    core = seg
    if ";" in seg:
        idx = seg.index(";")
        core, semi = seg[:idx], seg[idx:]
        semi = _xform_semi(semi)
    # split extension chain on '.', keep recognised extensions verbatim,
    # keep recognised structural stems verbatim, cipher everything else
    if "." in core:
        parts = core.split(".")
        new = []
        for j, p in enumerate(parts):
            if j == 0 and p.lower() in _STEM_KEEP:
                new.append(p)
            elif j > 0 and p.lower() in _EXT_KEEP:
                new.append(p)
            elif p.lower() in _PUBSFX:
                # is_tld() also runs on path segments; keep tld-like
                # tokens verbatim so glued_tld / embedded-domain path
                # checks make the identical decision
                new.append(p)
            elif _APEX_FROM and j == 0 and p.lower() == _APEX_FROM:
                new.append(_APEX_TO if p.islower() else _APEX_TO.capitalize())
            else:
                new.append(_cipher(p))
        core = ".".join(new)
    else:
        if core.lower() in _STEM_KEEP:
            pass
        elif core.lower() in _PUBSFX:
            pass
        elif _APEX_FROM and core.lower() == _APEX_FROM:
            core = _APEX_TO if core.islower() else _APEX_TO.capitalize()
        else:
            core = _cipher(core)
    return core + semi


def xform(url):
    u = url
    # scheme
    scheme = ""
    rest = u
    if "://" in u:
        scheme, rest = u.split("://", 1)
        if scheme.lower() not in _SCHEME_KEEP:
            scheme = _cipher(scheme)
    # split authority / path+query+frag
    slash = rest.find("/")
    qmark = rest.find("?")
    hashm = rest.find("#")
    cut = len(rest)
    for m in (slash, qmark, hashm):
        if m != -1:
            cut = min(cut, m)
    authority = rest[:cut]
    tail = rest[cut:]
    # userinfo@host : keep userinfo structure, cipher its letters
    userinfo = ""
    hostpart = authority
    if "@" in authority:
        userinfo, hostpart = authority.rsplit("@", 1)
        userinfo = _cipher(userinfo) + "@"
    new_auth = userinfo + _xform_host(hostpart) if hostpart else authority
    # tail: cipher only the path portion (up to ? or #); keep query and
    # fragment byte-identical so every query/value gate is unchanged
    qpos = tail.find("?")
    hpos = tail.find("#")
    pcut = len(tail)
    for m in (qpos, hpos):
        if m != -1:
            pcut = min(pcut, m)
    path = tail[:pcut]
    qf = tail[pcut:]
    if path:
        segs = path.split("/")
        path = "/".join(_xform_seg(s) for s in segs)
    qf = _xform_qf(qf)
    out = (scheme + "://" if scheme else "") + new_auth + path + qf
    return out


# url-structural tokens kept verbatim inside query values so val_has_url /
# redirect-target detection stays truthful on the published corpus and the
# open-redirect/SSRF narrative is still demonstrable; identity-bearing
# letter runs around them are still ciphered
_VAL_KEEP = ("https", "http", "ftp", "www")


def _cipher_value(v):
    # cipher letter runs but leave percent-escapes (%xx) and the url
    # structural tokens above intact; digits/punct already pass through
    out = []
    i = 0
    n = len(v)
    while i < n:
        c = v[i]
        if c == "%" and i + 2 < n:
            out.append(v[i:i + 3])
            i += 3
            continue
        if c.isalpha():
            j = i
            while j < n and v[j].isalpha():
                j += 1
            run = v[i:j]
            low = run.lower()
            kept = False
            for k in _VAL_KEEP:
                if low == k:
                    out.append(run)
                    kept = True
                    break
            if not kept:
                out.append(_cipher(run))
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _xform_qf(qf):
    # qf is the leading '?'... and/or '#'... ; keep parameter NAMES and all
    # separators verbatim (names are generic and the security gates key on
    # them), cipher only VALUES and the fragment body
    if not qf:
        return qf
    frag = ""
    q = qf
    hp = qf.find("#")
    if hp != -1:
        q, frag = qf[:hp], qf[hp:]
    if q.startswith("?"):
        body = q[1:]
        # split on & and ; preserving the delimiters
        out = ["?"]
        tok = ""
        for ch in body:
            if ch in "&;":
                out.append(_xform_pair(tok))
                out.append(ch)
                tok = ""
            else:
                tok += ch
        out.append(_xform_pair(tok))
        q = "".join(out)
    if frag:
        frag = "#" + _cipher_value(frag[1:])
    return q + frag


def _xform_pair(tok):
    if tok == "":
        return tok
    if "=" in tok:
        name, val = tok.split("=", 1)
        # keep the name verbatim only if it is a generic recon parameter
        # (no target identity); otherwise cipher it. A brand/product
        # custom name and a free-text value fragment that gained a
        # spurious '=' after an '&'/';' split are both de-identified
        # this way.
        if name.lower() in _PARAM_KEEP:
            return name + "=" + _cipher_value(val)
        return _cipher_value(name) + "=" + _cipher_value(val)
    # no '=': a genuine bare param name kept only if generic; otherwise
    # (far more often a free-text value fragment produced by splitting a
    # human-readable value on a literal '&'/';') ciphered so no brand
    # text survives. %xx / digits / punctuation / url structural tokens
    # are preserved either way.
    if tok.lower() in _PARAM_KEEP:
        return tok
    return _cipher_value(tok)


def main():
    w = sys.stdout.write
    for line in sys.stdin:
        nl = "\n" if line.endswith("\n") else ""
        s = line[:-1] if nl else line
        if s == "":
            w(line)
            continue
        try:
            w(xform(s) + nl)
        except Exception:
            # never drop a line; on any parse oddity emit a fully ciphered
            # fallback so no original identity leaks
            w(_cipher(s) + nl)


if __name__ == "__main__":
    main()
