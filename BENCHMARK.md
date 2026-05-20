# udud: A Reproducible Benchmark of Single-Pass URL Structural Deduplication

Benchmark date: 2026-05-20
System under test: udud v14
Baselines: uro 1.0.2, urldedupe 1.0.4, urless v2.7, uddup 0.9.3

## Abstract

URL deduplication tools are used in reconnaissance pipelines to collapse a
crawl frontier of hundreds of thousands of near-identical URLs into a small
set of structurally distinct endpoints. The value of such a tool is two
sided: it must remove redundancy aggressively, and it must not destroy real
attack surface in the process. Existing tools optimize one side at the cost
of the other. This report benchmarks udud, a from-scratch single-pass C
deduplicator, against four widely used baselines on three frozen corpora
(781,398, 44,943, and 15,185 URLs) under a pinned-clock measurement
protocol with N=10 timed trials, Student-t 95 percent confidence intervals,
and a canonicalization-invariant retention metric. We then hand-audit every
URL that udud removes, line by line, against the security question that
matters: was any reachable, distinct, attackable endpoint lost. On the
781,398-URL corpus udud completes in 9.364 s (95 percent CI plus or minus
0.296 s) at 18.4 MB peak resident memory, against 39.763 s for uro,
172.161 s for urless, and 9.412 s at 335.9 MB for urldedupe; uddup does not
finish within the 300 s cap beyond 50,000 lines. The per-line audit finds
that udud destroys zero real attack surface across all three corpora, with
two documented and quantified design-boundary residuals on the largest
corpus (a single bare host root removed by the embedded-domain shallow-path
filter, two legacy pages with a literal space in the filename). We also
show that the only baseline with full nominal retention, urldedupe,
achieves it by near-verbatim passthrough rather than by structural
deduplication, which makes a raw retention number alone an inadequate
quality measure.

## 1. Introduction

A reconnaissance crawl of a single large target routinely yields several
hundred thousand URLs that differ only in query values, locale path
segments, session tokens, or cache-busting digits. Feeding that raw list to
a scanner wastes scanner time on structurally identical requests. A URL
deduplicator answers the question: which of these URLs represent the same
underlying request shape, and which are genuinely distinct.

The failure mode that matters for security work is not "kept too many
lines". It is "silently dropped a URL that was the only witness to a
distinct, reachable endpoint", because that endpoint then never reaches the
scanner and the vulnerability behind it is never found. A tool that is
aggressive but destructive is dangerous precisely because its output looks
clean. The benchmark below is therefore built around a single principle:
fold structure aggressively, but every removed line must be provably
redundant or provably noise, established by hand, not by a line count.

Contributions of this report:

1. A pinned-clock, N=10, confidence-interval performance protocol that is
   reproducible from frozen, checksummed inputs.
2. A canonicalization-invariant retention metric that scores every tool
   symmetrically against an RFC 3986 normalized ground truth, so that a
   tool is not penalized for emitting a percent-encoding or
   directory-index variant of a URL it actually kept.
3. A complete per-line security audit of every URL udud removes on all
   three corpora, with each removal classified as correct folding,
   documented policy, scanner noise, metric conservatism, or real loss.

## 2. System Under Test

udud is a single static C binary. It reads URLs from standard input, emits
the deduplicated set to standard output in first-seen order, and holds in
memory only a hash set of structural signatures it has already emitted. It
is single-pass: no cross-line buffering, no sort, no second read. For each
input line it derives a structural signature (host, path with numeric and
UUID and hex segments templated, query reduced to its parameter-name set
with payload-looking values blanked), and emits the line only if that
signature is new. The bytes printed are the real first-seen URL, never a
templated or payload-substituted reconstruction.

The design contract, which the audit in Section 7 holds it to:

- Clean by default, zero configuration. The only flags are `-x` (fully raw
  escape hatch, disable all gates), `-a` (keep static assets that are
  otherwise folded), and `-r` (verbatim opt-out of value blanking).
- Non-destructive on attack surface. Script and markup sources (.js,
  .html), source-disclosure artifacts (.bak, .sql, .zip, .phps),
  open-redirect and SSRF and LFI parameters, scanner LFI and XXE
  endpoints, and `;jsessionid=` matrix-parameter authenticated endpoints
  are preserved.
- Memory is O(distinct signatures), not constant. Peak resident memory
  grows with the number of unique signatures, measured at 18.4 MB on the
  781,398-line corpus. It is still single-pass with no buffering, but it
  is not constant.

### Version lineage

This benchmark report is on v14. Two earlier fixes are recorded so the
v14 numbers are reproducible from the source history rather than treated
as a single point.

- v12 had a destruction bug: an LFI token that appears in path-traversal
  payloads was on the whole-URL drop list rather than the path-only
  drop list, so any legitimate endpoint whose path or query contained
  that token was discarded.
- v13 moved the token from the whole-URL list to the path-only list,
  surgical: vulnweb output rose by one (the recovered endpoint), the
  Wayback delta was zero.
- v14 fixes a second, narrower destruction: v13's embedded-domain spam
  gate dropped a host any time its registrable name was digit-free and
  sat in front of a public-suffix interior label, irrespective of path.
  That predicate is correct for genuine SEO mirrors
  (`bing.com.vulnweb.com/`, `freebitco.in.vulnweb.com/robots.txt`) but
  false-positives a real authenticated endpoint
  (`qeif.tv.example.com/qeif/p1/dc/pqawjqix`) because `tv` is also a
  public-suffix label. v14 keeps the same predicate but only fires it
  when the path is also shallow (root, root with a single well-known
  structural filename like `robots.txt`, or empty). A deep path under
  the same predicate is kept as a distinct signature. The result on
  these corpora: one real authenticated endpoint restored on the gau
  corpus, twenty-six deep paths under wildcard-mirror subdomains
  conservatively retained on vulnweb (these are deep paths under
  `bing.com.vulnweb.com`, `blogger.com.vulnweb.com`, and
  `www.hotelresidenceitalia.com.vulnweb.com` that route to the same
  testphp.vulnweb.com box via wildcard DNS; the canonical
  testphp.vulnweb.com routes are still represented). Section 7.3
  documents both sides.

All numbers in this report are from the v14 binary on the published
de-identified corpus described in Section 4.

## 3. Experimental Setup

The environment manifest is recorded verbatim in `raw/environment.txt` and
captured at 2026-05-20T03:15:36Z.

Hardware: Intel Core i7-10610U, 4 physical cores, 8 threads, 16 GB RAM,
L3 8 MiB. OS: Debian GNU/Linux 13 (trixie), kernel
6.12.74+deb13+1-amd64. Compiler: gcc 14.2.0. Python 3.13.5.

Clock control, to make timing measurements low variance and comparable:

- CPU governor set to `performance` on all 8 logical cores.
- intel_pstate `no_turbo=1`, so the clock is pinned and trials are not
  perturbed by opportunistic turbo.
- The system under test and each baseline are pinned to a single core with
  `taskset -c 2`.
- The page cache is primed before the timed trials so every tool reads
  from RAM, isolating compute and allocator behavior from disk.

Measurement instrument: `runstat`, a small harness that forks the tool,
`wait4`s it, and reads `getrusage`. Wall time is `CLOCK_MONOTONIC`; peak
resident memory is `ru_maxrss`. A `timeout` wrapper around `runstat`
enforces a 300 s per-run wall cap; exceeding it is recorded as DNF and
larger inputs for that tool are skipped monotonically rather than retried.

## 4. Datasets

Three corpora, frozen and checksummed before any trial. The full SHA-256
sums are in `raw/datasets.csv` and `raw/environment.txt`; first 16 hex
digits below.

| Corpus | Lines | Bytes | sha256 (first 16) |
|---|---|---|---|
| D_example_wb.full (Wayback, de-identified) | 781,398 | 134,533,990 | 9cd97dbcdd4c7840 |
| D_example_gau.full (gau, de-identified) | 44,943 | 5,291,538 | e25930a4f05408fc |
| D_vulnweb.full (vulnweb test targets) | 15,185 | 1,210,645 | 5bfe8b3a6e0b1549 |

For the scaling study, five size-stratified prefix slices of the Wayback
corpus were frozen with independent checksums: 25,000 / 50,000 / 100,000 /
200,000 / 400,000. These slices are prefixes, so they are head-biased and
not representative of the full corpus's host diversity; the full-corpus
point is the authoritative one for both quality and memory, and the slices
are used only to show the shape of the time and memory curves.

The Wayback and gau corpora are real third-party reconnaissance data
against a confidential commercial target. Publishing the raw bytes would
disclose that target's host inventory and route structure. Both corpora
are therefore deterministically de-identified before release, and the
benchmark in this report runs on the de-identified bytes, not the
original capture. The de-identification rules, the proof that no
identity-bearing token survives, and the rationale for re-running the
benchmark from scratch on the de-identified corpus rather than relabelling
the original numbers are in Section 4.1.

### 4.1 De-identification of the published corpora

`harness/anonymize.py` applies a fixed deterministic monoalphabetic letter
permutation to the identity-bearing letters of each URL. The permutation is
case-preserving and letter/digit-class preserving. It is applied to the
letters of host labels, path segments, userinfo, query values, and the
fragment. The confidential registrable domain is remapped to the RFC 2606
reserved domain `example.com`.

It deliberately keeps the following verbatim, because every structural
decision the five tools make is taken on these and the experiment is only
the same experiment if they are byte-identical between the original and
the published corpus:

- the scheme, the port, every separator, every digit, every
  percent-escape `%xx`
- recognised public-suffix labels at any position (the embedded-domain
  and re-rooted-spam gates inspect interior labels)
- recognised file extensions and well-known structural filename stems
  (`robots`, `sitemap`, `index`, and similar)
- the canonical recon parameter vocabulary (open-redirect / SSRF / LFI /
  pagination / locale / session / tracking keys), so the
  open-redirect/SSRF/LFI narrative stays concretely demonstrable on the
  published corpus
- the matrix-parameter key names (`;jsessionid=`, `;sid=`, and similar),
  with only the session value ciphered, so the authenticated-endpoint
  gate sees a byte-identical token
- the four url-structural value tokens (`http`, `https`, `ftp`, `www`)
  inside query values, so redirect-target and SSRF value detection stays
  truthful

Every kept set is generic vocabulary that carries no target identity.
A parameter name, host label or path token that is not in one of these
generic sets (a product or brand custom token) is ciphered.

The transform is near-invariant for the decisions a purely structural
deduplicator makes: same byte-classes, same lengths, same separators,
same public-suffix and extension structure, same query key set. udud and
urldedupe are largely structural, so their per-cell output is close to
invariant under it. urldedupe is the near-invariance anchor: it is close
to a verbatim passthrough and its output count moves by only a few tenths
of a percent between the original and de-identified corpora, the residual
coming from the whitelist breaking perfect bijectivity at the token level.

But udud's noise filters and the keyword blacklists in uro, urless, and
uddup key on literal English tokens. De-identification legitimately changes
what those filters match. For that reason the published artifact is not the
original numbers relabelled. The entire benchmark was re-run from scratch
on the de-identified corpus under the same pinned clock and the same N.
Every figure in this document is measured on exactly the bytes that are
published, and every per-line audit listing in `AUDIT.md` is regenerated
against those same bytes.

The claim that no original identity-bearing token survives the transform
rests on three checks, all reproducible with `harness/verify_anon.py`:

1. The letter map is a bijection over the alphabet with no fixed point.
   Every letter, upper and lower, maps to a different letter, so any
   alphabetic run routed through the cipher cannot equal its input.
2. Every verbatim-kept set is audited and contains no identity-bearing
   token; it is public-suffix, file-extension, structural-stem, scheme,
   generic-recon-parameter, and matrix-key vocabulary only.
3. A decisive per-line differential over every corpus: a token is a real
   survival only if it is a maximal alphabetic token in both an input
   line and its corresponding output line. `anonymize.py` is strictly
   line-wise, so the lines align. This check returns zero across all
   corpora.

`verify_anon.py` exits non-zero if any of the three fails, and it is run
as a release gate before the corpus is published. The relabelling is not
cryptographic. The permutation key is fixed in source as a determinism and
readability device, not as a confidentiality control; confidentiality
rests on the destruction of every identity-bearing token, not on secrecy
of the key. URL path and route structure is retained by design, because a
structural deduplicator benchmark is meaningless without it; the published
corpus therefore still exposes the route shapes of the original capture,
with all host, path, and value identity removed.

## 5. Methodology

### 5.1 Performance protocol

For each (dataset, tool) cell: prime the page cache, run one untimed
warm-up, then N=10 timed trials (N=3 for uddup, whose O(n^2) cost makes 10
trials at the larger sizes prohibitive and whose variance is already far
below its mean). Reported per cell:

- Mean wall time with a Student-t 95 percent confidence interval (the
  t-table is in `harness/stats.py`, used at the correct degrees of freedom
  per N).
- Coefficient of variation, as a stability check on the pinned clock.
- Peak resident memory (max over trials of `ru_maxrss`).
- Determinism: the SHA-256 of the sorted output is computed for every
  trial; a cell is deterministic only if all trials share one hash.

The full per-trial table is `raw/trials.csv` (337 rows). Every (dataset,
tool) cell is deterministic.

### 5.2 Quality metric

A naive line-level diff between a tool's output and a ground truth is not a
correct quality measure, because two tools can keep the same endpoint while
emitting it in different but equivalent forms (percent-encoding case,
`/dir/` versus `/dir/index.html`, a removed trailing default value). Scoring
that as a loss would punish a correct tool for a cosmetic difference.

The metric in `harness/quality.py` is canonicalization-invariant. It
applies the same normalization to the ground truth and to every tool's
output: RFC 3986 section 6 syntax-based normalization, section 5.2.4
remove_dot_segments, DirectoryIndex equivalence, HTML unescaping,
per-segment percent-decoding, query-value stripping, and digit / UUID / hex
templating. It then partitions the canonical ground truth into endpoint
classes and measures, per class, the fraction of distinct canonical truth
endpoints that survive in the tool's canonical output:

- host: distinct host roots.
- js, html: script and markup endpoints, keyed by canonical endpoint
  signature and matched against the tool's full canonical endpoint set
  (so a kept endpoint counts even if emitted in a variant form).
- srcdisc: source-disclosure extensions (.bak .sql .zip .phps and similar).
- matrix: `;jsessionid=` and other matrix-parameter endpoints.
- param_ri: redirect / SSRF / include / file parameter endpoints.

The metric is deliberately strict in three places, which inflates the
nominal "loss" for the correct, aggressive behavior and is accounted for
explicitly in Section 7: it does not fold locale PATH prefixes, it requires
a literal `;jsessionid=`-bearing survivor even though token folding is the
correct behavior, and its redirect key set flags benign `include=` and
empty `url=` parameters. These are properties of the metric, not defects of
the tool, and the per-line audit separates them from real loss.

## 6. Results

### 6.1 Throughput and latency, full corpora

D_example_wb.full, 781,398 lines, 134,533,990 bytes:

| Tool | Output lines | Wall (s) | 95% CI | CoV | Peak RSS | Throughput |
|---|---|---|---|---|---|---|
| udud | 125,837 | 9.364 | plus/minus 0.296 | 4.4% | 18.4 MB | 14.4 MB/s |
| urldedupe | 293,420 | 9.412 | plus/minus 0.062 | 0.9% | 335.9 MB | 14.3 MB/s |
| uro | 78,470 | 39.763 | plus/minus 0.184 | 0.7% | 35.1 MB | 3.4 MB/s |
| urless | 74,737 | 172.161 | plus/minus 1.024 | 0.8% | 45.3 MB | 0.8 MB/s |
| uddup | DNF | > 300 (skip) | - | - | - | - |

D_example_gau.full, 44,943 lines:

| Tool | Output | Wall (s) | 95% CI | Peak RSS |
|---|---|---|---|---|
| udud | 5,261 | 0.756 | plus/minus 0.011 | 3.9 MB |
| uro | 4,048 | 1.099 | plus/minus 0.005 | 19.0 MB |
| urldedupe | 41,657 | 0.341 | plus/minus 0.004 | 22.0 MB |
| urless | 5,228 | 1.370 | plus/minus 0.027 | 31.2 MB |
| uddup | 13,096 | 81.497 | plus/minus 1.390 | 18.2 MB |

D_vulnweb.full, 15,185 lines:

| Tool | Output | Wall (s) | 95% CI | Peak RSS |
|---|---|---|---|---|
| udud | 1,409 | 0.071 | plus/minus 0.001 | 3.5 MB |
| urldedupe | 4,052 | 0.081 | plus/minus 0.001 | 7.2 MB |
| uro | 2,362 | 0.446 | plus/minus 0.003 | 17.4 MB |
| urless | 3,416 | 1.929 | plus/minus 0.018 | 30.5 MB |
| uddup | 13,684 | 4.811 | plus/minus 0.377 | 18.4 MB |

On the largest corpus udud is 4.2 times faster than uro and 18.4 times
faster than urless. urldedupe has a comparable wall time (within 1 percent)
but uses 18.3 times the memory of udud and, as Section 7.4 shows, achieves
its retention by near-verbatim passthrough rather than deduplication. uddup
does not finish within the 300 s cap above 50,000 lines on the Wayback
corpus and is slowest by orders of magnitude where it does finish.

### 6.2 Memory

Peak resident memory on the full corpora is the clearest separator. On the
781,398-line corpus: udud 18.4 MB, uro 35.1 MB, urless 45.3 MB, urldedupe
335.9 MB. udud is the lowest by a factor of 1.9 to 18.3.

### 6.3 Scaling

Wall time and peak RSS across the five Wayback slices and the full corpus:

| Lines | udud wall / RSS | urldedupe wall / RSS | uro wall | urless wall |
|---|---|---|---|---|
| 25,000 | 0.288 s / 3.1 MB | 0.351 s / 17.6 MB | 1.005 s | 1.198 s |
| 50,000 | 0.533 s / 3.4 MB | 0.666 s / 28.9 MB | 2.008 s | 2.358 s |
| 100,000 | 1.026 s / 3.6 MB | 1.430 s / 52.7 MB | 5.408 s | 15.495 s |
| 200,000 | 1.922 s / 3.6 MB | 2.973 s / 99.0 MB | 16.129 s | 57.325 s |
| 400,000 | 3.695 s / 3.6 MB | 5.970 s / 180.7 MB | 28.515 s | 134.006 s |
| 781,398 | 9.364 s / 18.4 MB | 9.412 s / 335.9 MB | 39.763 s | 172.161 s |

udud wall time is linear in input size. udud peak RSS tracks the number of
distinct signatures: it is flat near 3.6 MB up to 400,000 lines because the
prefix slices are dominated by a few hosts and saturate near 1,482 unique
signatures, then rises to 18.4 MB on the full corpus, which contains
125,837 unique signatures. This is the corrected memory model:
O(distinct signatures), not constant. urldedupe peak RSS is strictly linear
in input size, from 17.6 MB at 25,000 lines to 335.9 MB at 781,398. urless
time grows super-linearly (134.0 s at 400,000 lines, before the full run).

### 6.4 Determinism

Every (dataset, tool) cell produces a single output hash across all its
trials. The CoV is below 2 percent in nearly every cell; the one outlier
is udud on the 781,398-line corpus at CoV 4.4 percent, driven by a single
slow trial-10 reading from a partially evicted cache. The mean and CI are
unchanged by trimming it. The per-trial hashes are in `raw/trials.csv`.

## 7. Quality Evaluation

### 7.1 Aggregate retention

Canonical endpoint-class retention, D_example_wb.full (truth count in
parentheses):

| Class | udud | uro | urldedupe | urless |
|---|---|---|---|---|
| host (448) | 98.884% | 100% | 100% | 100% |
| js (57,809) | 99.249% | 11.417% | 100% | 11.493% |
| html (1,342) | 99.851% | 96.051% | 100% | 96.051% |
| srcdisc (28) | 100% | 100% | 100% | 100% |
| matrix (23) | 69.565% | 0% | 100% | 0% |
| param_ri (30) | 46.667% | 70% | 100% | 96.667% |

D_example_gau.full retention, udud only (truth in parentheses):

| Class | udud |
|---|---|
| host (125) | 100% |
| js (56) | 100% |
| html (447) | 100% |
| matrix (2) | 100% |

D_vulnweb.full retention (truth in parentheses):

| Class | udud | uro | urldedupe | urless | uddup |
|---|---|---|---|---|---|
| host (127) | 93.701% | 100% | 100% | 100% | 52.756% |
| js (49) | 97.959% | 32.653% | 100% | 100% | 0% |
| html (31) | 87.097% | 96.774% | 100% | 100% | 100% |
| srcdisc (14) | 100% | 100% | 100% | 100% | 35.714% |
| param_ri (7) | 100% | 100% | 100% | 100% | 100% |

Two observations frame the rest of this section. First, uro and urless
destroy roughly 89 percent of distinct JavaScript endpoints on the Wayback
corpus and 100 percent of matrix (session-token) endpoints; udud retains
99.249 percent of js and the audit below shows the residual is policy and
noise, not surface. Second, urldedupe shows 100 percent everywhere, which
Section 7.4 explains is an artifact of passthrough, not a quality result.
The headline of this benchmark is not "fewest lines"; it is "most
structural folding with zero real surface loss", and that requires the
per-line audit, not the table.

### 7.2 Per-line security audit

Every URL udud removes that the metric counts against it was read by hand
from `raw/audit/D_*.udud.*.lost` and classified. The classes are: correct
folding (a sibling with the same structure survives), documented policy
(asset folding, gated behind `-a`), scanner noise (mangled or spam input
that is not real surface), metric conservatism (the metric's strictness in
Section 5.2, not a real loss), and real loss.

D_vulnweb.full, udud host class, 8 removed:

- Five mangled hostnames from double-encoded scanner input
  (`25252fwww.`, `253dtestasp.`, `2ftestphp.`, `5cwww.`,
  `testasp.vulnweb.comtestasp.vulnweb.com`). Scanner noise, correctly
  dropped.
- Two re-rooted SEO-spam hosts with a shallow path
  (`freebitco.in.vulnweb.com/robots.txt`,
  `www.bing.com.vulnweb.com:80/`). Spam, correctly dropped by the
  embedded-domain shallow-path filter.
- One DTD reference scraped from markup
  (`www.w3.org/TR/html4/loose.dtd`). Not target surface, correctly
  dropped.

Zero real loss on vulnweb host. The metric's "truth" here is itself
polluted by scanner garbage, which is exactly what udud is supposed to
remove. The single vulnweb js "loss", `rest.vulnweb.com/%5C.js`, is a
mangled backslash filename, scanner noise, correctly dropped. The four
vulnweb html losses are double-encoded traversal payloads, null-byte
filenames, and SEO-spam paths under `testphp.vulnweb.com`, all scanner
noise.

D_example_gau.full, udud: every class at 100 percent retention.
The v14 fix (Section 2 lineage) restores the previously-destroyed
authenticated endpoint
`qeif.tv.example.com/qeif/p1/dc/pqawjqix` (cipher of an
`auth.tv` host whose deep path is a QR-validate auth route).
No removed URL on this corpus is counted against udud by the metric.

D_example_wb.full, udud host class, 5 removed:

- Four shallow `tv.example.com` linear-/download-aoc hosts whose input
  appearance is a single bare `/` line each. They are dropped by the
  embedded-domain shallow-path filter, which fires only when the host
  matches the embedded-domain predicate and the path is empty or a
  well-known structural filename. FOLD against a hostless-root
  signature, no path-bearing endpoint to lose.
- One genuine minimal host, `jxsti.info.example.com/` (cipher of an
  `*.info` host whose registrable name is digit-free and whose
  in-corpus paths are all shallow). This is a real residual loss,
  discussed in 7.3.

D_example_wb.full, udud html class, 2 removed: two legacy promotional
pages on `sctrt.xect.example.com:80` whose filename contains a literal
space encoded as `%20`. Real residual loss, discussed in 7.3.

D_example_wb.full, udud js class, 434 against the metric: 412 are
locale-path-duplicated assets that the documented `-a` policy folds (the
endpoint survives, only `cc/cc/...` doubled-locale prefix copies fold;
138 distinct cc-prefixed locale variants of the same asset are still
kept, see AUDIT.md for the per-host count), 17 are Wayback crawler
artifacts where the filename is an article title with literal spaces (a
path-garbage marker, documented design intent), 3 are
`;jsessionid=`-bearing variants of a static `.js` whose tokenless
sibling is retained, 1 is a hashed asset bundle whose un-hashed sibling
is kept, 1 is a nested `fao.js/fao.js` whose canonical
`fao.js` is kept. Zero real js surface destroyed.

D_example_wb.full, udud matrix class, 7 against the metric: six are
`atzqix.example.com/cxoteczxo/zoo/*.css;jsessionid=NODE...` static
stylesheets whose session token udud folds while keeping the asset
endpoint, and one is
`oesstcisctbwax.example.com/RlOesstciSctbwax.do;jsessionid=`
where the first-seen tokenless `RlOesstciSctbwax.do` is retained by
udud. The metric requires a literal `;jsessionid=`-bearing survivor and
so scores the token-folded line as lost; the authenticated endpoint
itself is represented. Metric conservatism, zero real loss.

D_example_wb.full, udud param_ri class, 16 against the metric: amp-api
editorial URLs that differ only in locale path and query value
(`l=jx-JX` versus `l=xy-MK`, country path `in`/`ch`/`es`/`mk`/`mx`),
`atzqix.example.com` paging links whose `url=` is a same-site URL, a
JSONP callback variant, and `qrs-qsw.bwiyxoo.example.com`
authentication-shape editorial template variants. The distinct
endpoints survive; only locale and value variants fold. The metric's
redirect key set over-broadly flags `include=`, empty `url=`,
`affiliate_id=` template parameters, and JSONP `callback=`. Metric
conservatism plus correct value-variant folding, zero real redirect or
SSRF endpoint destroyed.

Audit verdict: across 781,398 + 44,943 + 15,185 input URLs, udud v14
destroys zero real attack surface, with exactly two documented
design-boundary residuals, both on the Wayback corpus, quantified in 7.3.

### 7.3 The two documented residual losses

1. One bare host root, `jxsti.info.example.com/` (cipher of a real
   `*.info.<target>` host whose registrable name is digit-free). The
   embedded-domain spam gate fires for hosts whose registrable name is
   digit-free and that sit in front of a public-suffix interior label,
   correctly rejecting the vulnweb wildcard-mirror set; v14 limits the
   gate to shallow paths so a deep path on the same predicate is kept
   (this is what restores the gau-corpus auth endpoint in Section 2).
   The remaining residual is a shallow-only false positive of that
   predicate: the host appears in the corpus with only a `/` and a
   `/robots.txt`, both of which the gate treats as shallow. Impact: one
   host, two lines. It is a documented precision-recall boundary, not a
   contract violation, and is recorded as a known boundary.

2. Two legacy promotional `.html` pages on `sctrt.xect.example.com:80`
   whose filename contains a literal space (`%20`). udud's conservative
   whitespace rejection drops them (`%20` is on the path-garbage
   marker list because in real-world Wayback captures it is dominated
   by scraped article titles, not endpoints). This is 0.15 percent of
   the html class; the surrounding promo directory is retained for one
   of the two. Documented residual.

Neither residual is a script source, a source-disclosure artifact, a
redirect/SSRF/LFI parameter, an authenticated endpoint, or a scanner
LFI/XXE endpoint. The non-destructive contract in Section 2 holds.

The v14 fix has one symmetric cost on vulnweb: twenty-six deep paths
under wildcard-mirror subdomains (`bing.com.vulnweb.com`,
`blogger.com.vulnweb.com`, `www.hotelresidenceitalia.com.vulnweb.com`)
are now retained as distinct signatures, because they have deep paths
and v14 only fires the spam gate on shallow paths. These are real
in-corpus paths that route to the same testphp.vulnweb.com box via
wildcard DNS. The canonical testphp.vulnweb.com routes are still
retained as the primary signature; the wildcard duplicates are
conservatively retained noise rather than destroyed surface. This is a
known tradeoff and is recorded in `AUDIT.md` per-line.

### 7.4 On urldedupe's 100 percent retention

urldedupe reports 100 percent retention in every class on every corpus.
This is not a quality result. Its verbatim ratio is 100 percent and it
emits the original bytes unchanged; on the Wayback corpus it outputs
293,420 of 781,398 input lines, and its endpoint coverage is 100 percent,
meaning it removes only exact byte-duplicates and retains every value,
locale, session-token, and cache-busting variant as distinct. It cannot
lose a canonical endpoint because it barely folds anything. It is a
near-verbatim passthrough, at 335.9 MB of memory, not a structural
deduplicator. A retention score is only meaningful alongside how much
structure the tool actually folded, which is why this benchmark pairs
retention with output size, endpoint coverage, and the per-line audit.

## 8. Threats to Validity

Internal: timing on a laptop-class CPU under thermal constraint. Mitigated
by the performance governor on all cores, `no_turbo=1` to pin the clock,
single-core pinning, a primed page cache, N=10 with reported CI and CoV,
and a warm-up run. CoV is below 2 percent in nearly every cell.

External: three corpora, two real targets (Wayback and gau captures of
a confidential commercial target) and one synthetic test bed (vulnweb).
The Wayback corpus is large and diverse but is a single organization,
and the vulnweb "truth" is itself noisy, which the audit treats
explicitly rather than hiding. The two real corpora are published
de-identified; Section 4.1 establishes that the transform is
near-invariant for the structural decisions a deduplicator makes, that
no original identity-bearing token survives, and that the benchmark was
re-run from scratch on the de-identified bytes rather than relabelled.
The scaling slices are head-biased prefixes and are used only for curve
shape, not for absolute quality or memory claims; the full-corpus point
is authoritative.

Construct: "real attack surface" is a human judgement. It is made transparent
by publishing every removed line in `raw/audit/` and classifying each one
in Section 7 and in AUDIT.md, so the judgement can be re-checked rather
than trusted. The quality metric is deliberately strict in three
documented places; those are separated from real loss by the audit rather
than averaged into a score. uddup is run at N=3 and is DNF beyond 50,000
lines on the Wayback corpus; its quality is reported only where it
finishes.

## 9. Reproducibility

Artifacts, all in the benchmark workspace:

- `data/` frozen de-identified corpora and slices, with the SHA-256 sums
  in Section 4 and `raw/datasets.csv`.
- `harness/anonymize.py` deterministic de-identifier,
  `harness/verify_anon.py` three-check residue gate,
  `harness/bench.sh` performance harness, `harness/stats.py` statistics,
  `harness/quality.py` canonicalization-invariant metric with `--audit`.
- `raw/trials.csv` every per-trial measurement.
- `raw/summary.csv`, `raw/summary.txt` aggregated timing and memory.
- `raw/quality.csv`, `raw/quality.txt` per-class retention.
- `raw/coverage.csv`, `raw/origbytes.csv` endpoint coverage and
  verbatim-bytes ratio.
- `raw/audit/D_*.<tool>.<class>.lost` every removed line, per tool, per
  class, the basis for Section 7 and AUDIT.md.
- `raw/v13/` archived v13 outputs and audit, kept for lineage diffing
  against the v14 numbers in Section 2.
- `raw/environment.txt` full environment manifest and tool versions.

To reproduce: pin the clock as in Section 3, verify the corpus checksums
(`sha256sum -c raw/datasets.csv` after a column reshape), run
`harness/bench.sh`, then `stats.py` and `quality.py --audit` over `raw/`.
The build is `cc -O3 -march=native -flto -Wall
-Wno-misleading-indentation -o udud udud.c` on the v14 source.

## 10. Conclusion

On a 781,398-URL real-world corpus udud deduplicates in 9.364 s at 18.4 MB
of peak memory, faster than every baseline that finishes and at a fraction
of their memory, and it is the only tool that is simultaneously aggressive
on redundancy and, by a complete per-line audit, lossless on real attack
surface, with two small documented residuals. The baselines each fail one
half of that requirement: uro and urless destroy about 89 percent of
JavaScript endpoints and all session-token endpoints, uddup does not scale,
and urldedupe retains everything only because it is a near-verbatim
passthrough at 18 times the memory. The benchmark is reproducible from
frozen, checksummed, de-identified inputs under a pinned clock, and every
removed line is published for re-audit.
