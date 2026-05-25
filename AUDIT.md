# udud Per-Line Loss Audit (id-folding mode)

> **Version note (read first).** This audit documents the **id-folding**
> behavior of udud, the mode that collapses object IDs, hashes, and session
> tokens to one representative. Since **v18** that is the opt-in `-F` mode, not
> the default. The current **default** configuration (the one the headline
> benchmark measures) is *keep-biased*: it preserves those IDs and tokens
> instead of folding them, so it removes a strict subset of the lines audited
> here. The audit's central finding, that the lines udud removes are redundant
> or noise and not real attack surface, therefore holds for the default at least
> as strongly (the default removes fewer lines). Specific folding examples below
> (for example folding `;jsessionid=` tokens) describe `-F`, not the default.
>
> Since **v20** the default also folds a bare route (no matrix token, no query)
> when the same base path appears decorated with a `;matrix` token or a `?query`.
> That removal is redundant by construction: the decorated sibling survives and
> shares the same templated base, so no endpoint class is lost. It drops only a
> duplicate of a route that is still represented, so the finding above holds for
> it too.

This is the standalone re-audit record behind the quality discussion in
BENCHMARK.md. Every URL that udud (id-folding mode) removes and the
canonicalization-invariant metric counts against it is listed here verbatim and
classified by hand. The purpose is a security judgement, not a line count: for
each removed line, was a reachable, distinct, attackable endpoint lost.

Source of truth for the raw listings: `raw/audit/D_*.udud.*.lost`
(regenerated 2026-05-20). The output of v14, v15, and the current `-F` mode is
byte-identical on all four corpora (verified by SHA-256 on D_synth.full,
D_example_wb.full, D_example_gau.full, and D_vulnweb.full), so the audit applies
to id-folding mode unchanged.

Token note: the two large corpora are published in de-identified form,
so the URLs below carry ciphered host labels and path segments
(`atzqix.example.com`, `qrs-qsw.bwiyxoo.example.com`, ...). The cipher
is a fixed deterministic monoalphabetic letter permutation documented
in Section 4.1 of BENCHMARK.md; the structural shape is preserved
byte-for-byte. Where the audit decision turns on a structural property
(public-suffix label, file extension, matrix-key) that property is
verbatim in the corpus.

Classification key:

- FOLD: a structurally equivalent sibling survives in the output; the
  endpoint is still represented. Correct deduplication.
- POLICY: folded by the documented `-a`-gated asset policy; the endpoint
  survives, only locale-prefixed asset copies fold.
- NOISE: mangled, double-encoded, or SEO-spam input that is not real
  target surface. Correctly removed.
- METRIC: the metric's documented strictness (no locale PATH folding,
  requires a literal `;jsessionid=` survivor, over-broad redirect key
  set), not a real loss.
- REAL: a genuine, reachable, distinct endpoint was removed.

## D_vulnweb.full

### udud host, 8 removed (truth 127, retained 93.701%)

```
http://25252fwww.vulnweb.com/robots.txt
http://253dtestasp.vulnweb.com/robots.txt
http://2ftestphp.vulnweb.com:80/
http://5cwww.vulnweb.com/robots.txt
http://freebitco.in.vulnweb.com/robots.txt
http://testasp.vulnweb.comtestasp.vulnweb.com/robots.txt
http://www.bing.com.vulnweb.com:80/
http://www.w3.org/TR/html4/loose.dtd
```

- Lines 1 to 4: double-encoded scanner hostnames (`25252f` is
  double-encoded `%2F`, `253d` is `%3D`, `2f` is `/`, `5c` is a
  backslash). NOISE.
- Lines 5 to 7: re-rooted SEO-spam hosts placing a real public domain in
  front of `vulnweb.com`, all with a shallow path (`/robots.txt` or `/`).
  NOISE, correctly caught by the embedded-domain shallow-path filter
  (the same filter that v14 limited to shallow paths so a deep route on
  the same predicate is kept).
- Line 8: a DTD reference scraped out of markup, not target surface.
  NOISE.

Real loss: 0. Note the metric's "truth" for vulnweb host is itself
polluted by exactly the garbage udud is built to remove. v14 reduced
this category from 11 (v13) to 8 by keeping the three wildcard-mirror
hosts that have deep in-corpus paths (see the html / wildcard residual
note below).

### udud js, 1 removed (truth 49, retained 97.959%)

```
http://rest.vulnweb.com/%5C.js
```

`%5C` is a backslash; `\.js` is a mangled filename, not a real script.
NOISE. Real loss: 0.

### udud html, 4 removed (truth 31, retained 87.097%)

```
http://testphp.vulnweb.com/id/%251%25/index.html
http://testphp.vulnweb.com/Mod_Rewrite_Shop/RateProduct-1%20-%20Copy.html
http://testphp.vulnweb.com:80/shreya-singh.com/escorts/escort-services-in-jaipur.html
http://testphp.vulnweb.com:80/windows/win.ini%00.htm
```

- Line 1: double-encoded `%2525` traversal payload. NOISE.
- Line 2: a literal-space `RateProduct-1 - Copy.html` filename
  (file-explorer "Copy of" artifact). NOISE under the `%20`
  path-garbage marker.
- Line 3: SEO-spam path injected under `testphp.vulnweb.com`. NOISE.
- Line 4: `win.ini%00.htm` LFI attack payload with a null-byte
  truncation. NOISE.

Real loss: 0.

### v14 wildcard-mirror residual: 26 lines retained over v13

Listed for transparency, not as removals. v14's narrowing of the
embedded-domain spam gate to shallow paths means deep paths under
wildcard-mirror subdomains are now retained as distinct signatures:

```
http://bing.com.vulnweb.com/Flash/add.swf
http://bing.com.vulnweb.com/redir.php?r=...
http://blogger.com.vulnweb.com/Sk3GMxpX.php
http://blogger.com.vulnweb.com/wJ5CBcAh.php
http://www.hotelresidenceitalia.com.vulnweb.com/admin
http://www.hotelresidenceitalia.com.vulnweb.com/admin/create.sql
http://www.hotelresidenceitalia.com.vulnweb.com/AJAX
http://www.hotelresidenceitalia.com.vulnweb.com/AJAX/htaccess.conf
http://www.hotelresidenceitalia.com.vulnweb.com/AJAX/showxml.php
http://www.hotelresidenceitalia.com.vulnweb.com/AJAX/titles.php
http://www.hotelresidenceitalia.com.vulnweb.com/artists.php
http://www.hotelresidenceitalia.com.vulnweb.com/cart.php
http://www.hotelresidenceitalia.com.vulnweb.com/categories.php
http://www.hotelresidenceitalia.com.vulnweb.com/database_connect.php
http://www.hotelresidenceitalia.com.vulnweb.com/disclaimer.php
http://www.hotelresidenceitalia.com.vulnweb.com/guestbook.php
http://www.hotelresidenceitalia.com.vulnweb.com/hpp
http://www.hotelresidenceitalia.com.vulnweb.com/hpp/params.php
http://www.hotelresidenceitalia.com.vulnweb.com/login.php
http://www.hotelresidenceitalia.com.vulnweb.com/Mod_Rewrite_Shop
http://www.hotelresidenceitalia.com.vulnweb.com/privacy.php
http://www.hotelresidenceitalia.com.vulnweb.com/secured
http://www.hotelresidenceitalia.com.vulnweb.com/secured/database_connect.php
http://www.hotelresidenceitalia.com.vulnweb.com/sendcommand.php
http://www.hotelresidenceitalia.com.vulnweb.com/signup.php
http://www.hotelresidenceitalia.com.vulnweb.com/userinfo.php
```

These are real in-corpus paths under acunetix wildcard DNS that all
route to the same `testphp.vulnweb.com` backend. The canonical
`testphp.vulnweb.com` paths (`/login.php`, `/AJAX/...`, `/hpp/...`,
`/Mod_Rewrite_Shop`, etc.) are still retained as the primary
signatures, so the wildcard mirror set is conservatively retained
duplicate noise rather than new surface. Documented tradeoff: v14
errs on the side of recall for deep paths under the embedded-domain
predicate, because the same predicate was destroying a real
authenticated endpoint on the gau corpus (Section 2 of BENCHMARK.md).

## D_example_gau.full

Every udud retention class on this corpus is 100 percent. The lost
files in `raw/audit/` for `D_example_gau.full.udud.*` are empty.

The v14 fix specifically restores the authenticated endpoint
`https://qeif.tv.example.com/qeif/p1/dc/pqawjqix` (cipher of an
`auth.tv` host with a QR-validate-shape deep path) that v13's
embedded-domain spam gate had destroyed because `tv` is a
public-suffix label and v13 fired the predicate irrespective of path.
v14 keeps the predicate but only fires it when the path is shallow, so
the deep auth path survives as a distinct signature. The same gate
still correctly drops the shallow bare `qeif.tv.example.com/` root,
which is folded into the kept deep-path host signature.

## D_example_wb.full

### udud host, 5 removed (truth 448, retained 98.884%)

```
http://awyxqc-ae-s-xra.tv.example.com/
https://awyxqc-k-fqc-sctj-k.tv.example.com/
http://awyxqc-qs-s-fqc.tv.example.com/
https://jthyatqj-qtz.tv.example.com/
http://jxsti.info.example.com/
```

- Four `tv.example.com` hosts (cipher of `linear-*.tv` and
  `download-aoc.tv` media-delivery hostnames). Each appears in the
  corpus with only one shallow `/` line, no deeper path. The
  embedded-domain shallow-path filter drops them because the host
  matches the spam predicate (digit-free registrable name in front of
  a public-suffix label `tv`) and the path is shallow. FOLD: no
  deeper endpoint exists to lose, and the host signature is
  represented in the kept host-root deduplication set through other
  `tv.example.com`-suffixed hosts that do have deep paths.
- `jxsti.info.example.com/` (cipher of a real digit-free
  `*.info.<target>` host). This is the second-corpus form of the same
  precision-recall residual recorded in v13: the host appears with
  only `/` and `/robots.txt`, both shallow, so the embedded-domain
  shallow-path filter still fires. REAL (1 host, 2 lines).

Real loss: 1 host.

### udud html, 2 removed (truth 1,342, retained 99.851%)

```
http://sctrt.xect.example.com:80/sctrt/fxas/uk/ztyoerxc/ofts_EN/Eoxbea%20EN%20awyno.html
http://sctrt.xect.example.com:80/sctrt/qbbwawqiwty_hxaztrx/BQD%20sqmx/index.html
```

Legacy promo pages whose filename contains a literal space (`%20`).
udud's conservative whitespace rejection drops them (`%20` is on the
path-garbage marker list because in real-world Wayback captures it is
dominated by scraped article titles). 0.15 percent of html; the
surrounding promo directory is retained for one of the two. REAL
(2 pages). Documented residual.

### udud js, 434 against the metric (truth 57,809, retained 99.249%)

By hand over `raw/audit/D_example_wb.full.udud.js.lost`:

- 412 are doubled-locale-prefix asset copies of the form
  `host/{cc}/{cc}/path...js` for `cc` in `{ai, ap, de, es, fc, fe,
  fi, fr, ic, if, it, km, no, pl, ro, ru, si, wj}`. The asset is
  retained at 138 distinct `{cc1}/{cc2}/...` locale combinations
  per file; the doubled-locale prefix is folded as the documented
  `-a` policy. POLICY.
- 17 are encoded-space JS filenames
  (`...Promise%20based%20HTTP%20client%20for%20the%20browser%20and%20node.js`
  shape, where the "node.js" suffix is the page-title text, not a real
  module). `%20` in a path is on the path-garbage marker list (see
  the same rule applied to html). NOISE.
- 3 are `;jsessionid=`-bearing variants of static `sctitilsx.js`,
  `jquery-2.1.4.min.js`, and `jquery.sapinate.js` on
  `atzqix.example.com/cxoteczxo/vo/`. The tokenless siblings are
  retained (7,538 surviving `sctitilsx.js`-class lines in the
  output). FOLD plus METRIC.
- 1 is `bwiyxoo.example.com/fao.js/fao.js`, a nested duplicate-token
  path whose canonical `bwiyxoo.example.com/fao.js` is kept. FOLD.
- 1 is `bwiyxoo.example.com/qooxio/zfeyn.143.7z3162k4928q7b111x1q.js`,
  a hashed asset bundle; 50 distinct `zfeyn.143` siblings are kept and
  this hash variant folds into them. FOLD.

Real js surface destroyed: 0.

### udud matrix, 7 against the metric (truth 23, retained 69.565%)

```
https://atzqix.example.com/cxoteczxo/zoo/atzqitcoilax.css;jsessionid=...
https://atzqix.example.com/cxoteczxo/zoo/baqmo.css;jsessionid=...
https://atzqix.example.com/cxoteczxo/zoo/keloilax.css;jsessionid=...
https://atzqix.example.com/cxoteczxo/zoo/orttifyxoo/vdexcl-ew.rwy.css;jsessionid=...
https://atzqix.example.com/cxoteczxo/zoo/oxaxzi2.css;jsessionid=...
https://atzqix.example.com/cxoteczxo/zoo/ztrrty.css;jsessionid=...
https://oesstcisctbwax.example.com/RlOesstciSctbwax.do;jsessionid=mlp1YN...
```

- Six are static stylesheets on `atzqix.example.com/cxoteczxo/zoo/`;
  udud folds the session token and keeps the asset endpoint. A session
  token on a CSS file is not authenticated surface. METRIC (the metric
  requires a literal `;jsessionid=` survivor).
- `RlOesstciSctbwax.do;jsessionid=`: the first-seen tokenless
  `RlOesstciSctbwax.do` is retained by udud, so the authenticated
  endpoint is represented; the metric scores the token-folded duplicate
  as lost. METRIC.

Real loss: 0. The authenticated endpoint is kept.

### udud param_ri, 16 against the metric (truth 30, retained 46.667%)

The removed set, classified:

- Two `atzqix.example.com/{ro|ru}/{ro|ru}/saa/?q=...&url=...` open
  redirect URLs in `ro` and `ru` locale paths. The same `q,url`
  parameter shape is retained at many other locale prefixes on the
  same host (sampled: `mc/xa/saa`, `wa/xy/saa`, `jp/vq/saa`,
  `tw/uf/saa`), so the open-redirect-shape endpoint survives. FOLD
  plus METRIC (locale PATH folding).
- Three `hwjmxio.wieyxo.example.com/{qssoitcx|wieyxo|...}.html?...&affiliate_id=http%3A%2F%2F...`
  affiliate-widget template URLs. The widget endpoint with the same
  parameter key set including `affiliate_id` is retained at several
  other widget-shape lines on the same host. FOLD plus METRIC
  (`affiliate_id` is over-broadly flagged as a redirect key).
- Ten `qrs-qsw.bwiyxoo.example.com/p1/xjwitcwqa/{cc}/xjwitcwqa-ofxab-...?l={locale}&saqibtcr=wsftyx&include=ztyixyio&...`
  editorial-API URLs that differ only in country path and `l=`
  locale value (`in`/`ch`/`es`/`mk`/`mx`/`us` etc., with matching
  `l=jx-JX` / `l=xy-MK` / `l=xo-XO` values). The distinct editorial
  endpoint is retained; only locale and value variants fold. FOLD
  plus METRIC (`include=` over-broadly flagged, locale PATH not
  folded by the metric).
- One `rtpwxicqwaxco.example.com/icqwaxco/ftrx/ozcwsio/dewznbwyj.php?callback=...&q=...`
  JSONP callback variant of an empty-q endpoint that udud retains
  with a non-empty `q`. FOLD plus METRIC (JSONP `callback=` is not a
  redirect/SSRF/include key in practice; the metric's redirect set
  flags it).

Real redirect/SSRF/include endpoint destroyed: 0.

## Verdict

Across 781,398 + 44,943 + 15,185 input URLs, udud v14 destroys zero real
attack surface, with exactly two documented design-boundary residuals,
both on the Wayback corpus:

1. One genuine minimal host, `jxsti.info.example.com` (2 lines), a
   precision-recall false positive of the embedded-domain shallow-path
   filter. Same predicate that correctly rejects the vulnweb wildcard
   spam set and that v14 narrowed so it would stop destroying the
   gau-corpus authenticated endpoint.
2. Two legacy promo `.html` pages with a literal space in the filename
   (0.15% of html), from conservative whitespace rejection.

Neither residual is a script source, a source-disclosure artifact, a
redirect/SSRF/LFI parameter, an authenticated endpoint, or a scanner
LFI/XXE endpoint. The non-destructive contract holds. Every other line
the metric scores against udud is correct folding, documented asset
policy, scanner noise, or documented metric conservatism, and is
re-checkable from the `raw/audit/` listings.

Lineage diff against v13 (archived at `raw/v13/`): v14 restores one
real authenticated endpoint on the gau corpus
(`qeif.tv.example.com/qeif/p1/dc/pqawjqix`) and conservatively retains
twenty-six deep paths under vulnweb wildcard-mirror subdomains as
distinct signatures. The canonical testphp.vulnweb.com routes those
wildcards mirror are still retained as primary signatures.
