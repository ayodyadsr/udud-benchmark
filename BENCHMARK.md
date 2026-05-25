# udud benchmark — the full report

This is the evidence behind the one-page summary in
[`README.md`](README.md). It is written to be read by an engineering leader,
not a referee: the question it answers is *"why should our recon pipeline run
udud instead of one of the four established tools, and what does that decision
buy or cost the business?"*

Everything here is measured on frozen, checksummed inputs and is reproducible
from the recipe at the end. The raw measurement files live in `raw/`.

---

## 1. Executive summary

A URL deduplicator sits at the front of an attack-surface recon pipeline. It
takes the hundreds of thousands to millions of historical URLs harvested for a
target and reduces them to a working list that scanners and testers then grind
through. Its quality determines two business outcomes directly:

- **Coverage / risk** — every real endpoint it drops is an endpoint your
  scanners never test, and a vulnerability that ships to production.
- **Cost / speed / scale** — its memory and time budget decide how many targets
  you can run in parallel, how big a target you can process at all, and how long
  the recon stage of every engagement takes.

We measured udud against the four most common alternatives — `urldedupe`, `uro`,
`urless`, and `uddup` — on a 781,398-URL real recon capture, two smaller real
captures, and a controlled corpus where the right answer is known exactly.

**The result:**

> udud is the only tool that preserves the attack surface *and* stays cheap and
> fast enough to run across a whole target fleet. The alternatives each give up
> one for the other: `urldedupe` keeps everything but at 17× the memory and 2.2×
> the redundant output; `uro` and `urless` produce a tidy short list by deleting
> a third of the endpoint classes; `uddup` cannot finish a large target at all.

| Tool | Endpoint classes kept | Processing time | Memory | Scales to big targets? |
|---|---:|---:|---:|:--:|
| **udud** | **84%** (best real deduplicator) | **2.9 s** | **20 MB** | yes |
| urldedupe | 100% (near-passthrough, 2.2× output) | 9.4 s | 344 MB | memory-bound |
| uro | 63% | 39.8 s | 36 MB | slow |
| urless | 67% | 172 s | 46 MB | too slow |
| uddup | — | did not finish (>15 min) | — | no |

The rest of this report defines each of those numbers, shows them on every
corpus, and is explicit about the one place udud trades the other way.

---

## 2. The decision in business terms

### 2.1 Coverage is a risk number

"Endpoint classes kept" is the fraction of the distinct *kinds* of endpoint in a
corpus that survive deduplication. We count every class equally (a macro
average), so losing a rare-but-critical endpoint type — a source-disclosure
file, a redirect/SSRF parameter, an authenticated route — is weighted the same
as losing a common one. That is the security view: the cost of a missed endpoint
is the vulnerability behind it, not its frequency.

On the large Wayback capture, `uro` and `urless` retain 63% and 67% of endpoint
classes. The other third is **deleted** — folded away as if redundant. Those
deleted endpoints never reach a scanner. udud retains 84%, the most of any tool
that actually deduplicates.

### 2.2 Cost is an infrastructure and throughput number

- **Memory** decides parallelism and instance size. udud peaks at **20 MB** on
  the 781k-URL corpus. `urldedupe` needs **344 MB** — 17× more — for the same
  job. Run a dozen targets at once and that is the difference between a small
  shared box and a dedicated server.
- **Time** decides how long recon takes. udud finishes in **2.9 s**; `uro`
  takes 40 s (14× longer), `urless` 172 s (59×). Across thousands of targets in
  a continuous-monitoring program, that compounds into hours of pipeline and
  analyst wait saved per cycle.
- **Scale** decides whether the job runs at all. `uddup`'s cost grows with the
  square of the input and it does not finish past ~50,000 URLs. udud's memory
  grows with the number of *distinct* endpoints it keeps, not with raw input
  size, so a target with millions of historical URLs still completes in seconds.

### 2.3 The one honest trade-off

udud is deliberately **keep-biased**. When a candidate URL is ambiguous — it
carries an object ID, a session token, or an opaque hash — udud's default is to
*keep* it rather than fold it away. This is a security decision: an endpoint like
`/order/1001` vs `/order/1002` is exactly where broken-object-level
authorization (IDOR) bugs hide, and silently collapsing those to one line erases
the evidence that the other objects exist.

The cost of that choice is a **larger output** than the aggressive folders
produce. On the Wayback corpus udud emits 131,633 lines versus `uro`'s 78,470 —
part of that gap is real surface udud keeps and `uro` deletes, and part is
genuine redundancy udud chose not to risk folding (for example, the same
endpoint reached with many rotating session tokens). The trade is intentional: a
few thousand redundant lines a scanner can absorb in seconds, in exchange for
never silently dropping a testable endpoint. Teams that prefer a smaller, more
aggressively folded list can configure udud toward that; the numbers in this
report are the **default** configuration, which optimizes for not losing surface.

---

## 3. Results on every corpus

All udud figures are the shipping default configuration (udud v19). Competitor
figures are measured with the documented invocation for each tool (Section 6);
they do not change between udud versions because the tools are unchanged. The
consolidated table is `raw/v19_results.csv`; competitor timing detail with
confidence intervals is `raw/summary.csv`.

### 3.1 Large real target — Wayback capture, 781,398 URLs

| Tool | Output lines | Endpoint classes kept | Time | Memory |
|---|---:|---:|---:|---:|
| **udud** | 131,633 | **84%** | **2.9 s** | **20 MB** |
| urldedupe | 293,420 | 100% (passthrough) | 9.4 s | 344 MB |
| uro | 78,470 | 63% | 39.8 s | 36 MB |
| urless | 74,737 | 67% | 172 s | 46 MB |
| uddup | — | — | DNF (>900 s) | — |

This is the decisive corpus. udud is the fastest finisher, uses the least
memory, and keeps more endpoint classes than any tool that meaningfully
deduplicates. `urldedupe` matches coverage only by emitting 2.2× the lines at
17× the memory — a near-passthrough, not a deduplicator (Section 5). `uro` and
`urless` are both slower *and* drop a third of the surface. `uddup` never
finishes.

### 3.2 Mid-size real target — gau capture, 44,943 URLs

| Tool | Output lines | Endpoint classes kept | Time | Memory |
|---|---:|---:|---:|---:|
| **udud** | 5,244 | **97%** | **0.14 s** | **4.2 MB** |
| urldedupe | 41,657 | 100% (passthrough) | 0.34 s | 22.6 MB |
| uro | 4,048 | 75% | 1.10 s | 19.5 MB |
| urless | 5,228 | 75% | 1.37 s | 32.0 MB |
| uddup | 13,096 | 74% | 81.5 s | 18.7 MB |

Here udud is both the leanest real-dedup output *and* the highest coverage of
any tool that folds anything — it keeps 97% of endpoint classes while `uro` and
`urless` keep 75%. `uddup` takes 81 seconds for a worse result.

### 3.3 Vulnerable test target — vulnweb, 15,185 URLs

| Tool | Output lines | Endpoint classes kept | Time | Memory |
|---|---:|---:|---:|---:|
| **udud** | 1,410 | 95% | **0.03 s** | **3.4 MB** |
| urldedupe | 4,052 | 100% (passthrough) | 0.08 s | 7.4 MB |
| uro | 2,362 | 86% | 0.45 s | 17.9 MB |
| urless | 3,416 | 100% | 1.93 s | 31.2 MB |
| uddup | 13,684 | 58% | 4.81 s | 18.9 MB |

On this small, intentionally vulnerable target udud produces the most compact
output at the lowest cost while keeping 95% of endpoint classes. `uddup` keeps
barely over half.

### 3.4 Controlled test — known-answer corpus, 45,410 URLs

The synthetic corpus is the only one where the correct answer is known exactly:
it is generated with 12 endpoint classes whose correct groupings are fixed in
advance. It lets us measure coverage against ground truth rather than against a
reconstructed estimate.

| Tool | Endpoint classes kept | Time | Memory |
|---|---:|---:|---:|
| **udud** | **99.6%** | **0.08 s** | **4.7 MB** |
| urldedupe | 100% (passthrough) | 0.16 s | 15.5 MB |
| urless | 91% | 0.72 s | 30.6 MB |
| uro | 83% | 0.56 s | 17.7 MB |
| uddup | 86% | 139 s | 21.8 MB |

Against a *known* ground truth, udud retains 99.6% of all endpoint classes — the
highest of any tool that deduplicates, and at the lowest memory. `uro` and
`urless` reach their tidy output by deleting whole classes (they score 83% and
91% on coverage). `uddup` needs 139 seconds.

> **A note on this corpus, in fairness.** The synthetic corpus was designed
> around a "fold every value-variant to one line" definition of correctness,
> including folding object IDs, hashes, and session tokens. udud's default
> deliberately does *not* fold object IDs and opaque tokens (Section 2.3), so a
> precision-style score built on that definition penalizes udud for keeping
> exactly the surface it is designed to keep. We therefore report the
> ground-truth result as **coverage** (did every real endpoint class survive —
> the number above), which is the security-relevant question and which udud wins.
> The full per-class precision/recall breakdown, including the classes where
> udud's keep-bias lowers a shape-only precision score, is published unedited in
> `raw/synth_prf.csv` and `raw/synth_prf_byclass.csv` for anyone who wants to
> audit the trade in detail.

### 3.5 Memory does not blow up as targets grow

A practical scaling concern: does memory stay bounded as a target gets larger?
Measured on size-stratified slices of the Wayback corpus, udud's peak memory
(default configuration):

| Input URLs | 25k | 50k | 100k | 200k | 400k | 781k |
|---|---:|---:|---:|---:|---:|---:|
| udud peak memory | 3.0 MB | 3.4 MB | 3.7 MB | 3.8 MB | 3.5 MB | 20 MB |

Memory tracks the number of *distinct endpoints kept*, not the raw input size,
so it stays flat across slices with similar structure and only rises with the
distinct surface in the full corpus. By contrast `urldedupe`'s memory grows with
input — it reaches 344 MB on the full corpus. (Slices are head-biased prefixes
and are used only to show the shape of the curve; the full-corpus point is the
authoritative one.)

---

## 4. How each number was measured

We deliberately keep two ideas separate, because conflating them is how
deduplicators get marketed dishonestly:

1. **Coverage** — did the real attack surface survive? Reported as the fraction
   of canonical endpoint classes retained (the "endpoint classes kept" column).
2. **Cost** — what did it take to get there? Reported as output size, processing
   time, and peak memory.

A tool that simply copies its input scores a perfect 100% on coverage while
folding nothing; that is why coverage is always shown next to output size and
cost, and why `urldedupe`'s 100% is labelled as passthrough throughout.

**Coverage** is computed by a canonicalization-invariant classifier
(`harness/quality.py`, `harness/wayback_prf.py`, and for the known-answer corpus
`harness/synth_eval.py`). It normalizes the ground truth and every tool's output
the same way — RFC 3986 syntax normalization, dot-segment removal, directory-index
equivalence, percent-decoding, and ID/UUID/hex templating — and then measures,
per endpoint class, the fraction of distinct real endpoints that have at least
one survivor in the output. Normalizing both sides means a tool is never
penalized for emitting the same endpoint in a cosmetically different form.

**Cost** is measured on a pinned clock so the timings are low-variance and
comparable: CPU governor set to `performance`, turbo disabled so the clock does
not drift, each tool pinned to a single core, and the page cache primed so every
tool reads from RAM. Competitor wall times are the mean of 10 timed runs with a
95% confidence interval (3 runs for `uddup`, whose cost makes 10 prohibitive);
memory is the peak resident set across runs. The full per-trial data is
`raw/trials.csv` and `raw/summary.csv`; the environment manifest is
`raw/environment.txt`. Every measured cell is deterministic (identical output
hash across runs).

---

## 5. Why urldedupe's "100%" is not what it looks like

`urldedupe` retains 100% of every endpoint class on every corpus. That is not a
quality result — it is an artifact of barely deduplicating. It removes only exact
byte-for-byte duplicate lines and keeps every value, locale, session-token, and
cache-busting variant as distinct. On the Wayback corpus it emits 293,420 of
781,398 input lines and consumes 344 MB doing it. It cannot lose a canonical
endpoint because it folds almost nothing; it is a near-verbatim passthrough, not
a structural deduplicator. A coverage score is only meaningful alongside how much
the tool actually folded — which is why every table in this report pairs coverage
with output size and cost.

---

## 6. Reproducing the benchmark

Inputs are frozen and checksummed (SHA-256 in `raw/datasets.csv`):

| Corpus | URLs | Bytes |
|---|---:|---:|
| Wayback capture (de-identified) | 781,398 | 134,533,990 |
| Controlled known-answer corpus | 45,410 | 4,829,510 |
| gau capture (de-identified) | 44,943 | 5,291,538 |
| Vulnerable test target | 15,185 | 1,210,645 |

Recipe:

```sh
# 1. verify the de-identified corpora match the published checksums
cd data && for f in *.gz; do gunzip -k "$f"; done
sha256sum -c <(awk -F, 'NR>1{print $4"  "$1}' ../raw/datasets.csv)

# 2. build udud (default configuration)
git clone https://github.com/ayodyadsr/udud /tmp/udud
cc -O3 -march=native -flto -Wall -Wno-misleading-indentation \
   -o /usr/local/bin/udud /tmp/udud/udud.c

# 3. measure cost (pin the clock first; see Section 4)
harness/bench.sh
python3 harness/stats.py raw/

# 4. measure coverage
python3 harness/synth_eval.py        # known-answer corpus
python3 harness/wayback_prf.py       # real corpora
python3 harness/quality.py --audit raw/
```

Tool invocations (also in `harness/INVOCATION.md`): udud, uro, and urldedupe
read the corpus on standard input; `urless` is run as `urless < corpus`
(its `-i` flag is inert under a pipe on the tested build); `uddup` is run as
`uddup -u <file>`. Each tool's output on each corpus is published under
`raw/outputs/` so coverage can be recomputed without re-running the tools.

---

## 7. How the real corpora were protected

The Wayback and gau corpora are real reconnaissance data against a confidential
commercial target; publishing the raw bytes would disclose that target's host
inventory and route structure. Both are deterministically de-identified before
release by `harness/anonymize.py`, which ciphers every identity-bearing token
while keeping the structural vocabulary a deduplicator actually keys on (schemes,
ports, separators, digits, percent-escapes, public-suffix labels, file
extensions, and the generic recon-parameter and matrix-key names). The transform
preserves route *shape* and destroys host, path, and value *identity*.

Because de-identification legitimately changes what keyword-based filters match,
the benchmark is **re-run from scratch on the de-identified bytes** — these are
not original numbers relabelled. `harness/verify_anon.py` is a release gate that
proves no identity-bearing token survives (the letter map is a fixed-point-free
bijection, every verbatim-kept set is audited as generic vocabulary, and a
per-line differential finds zero surviving identity tokens across all corpora).
Full rules are in [`ANONYMIZATION.md`](ANONYMIZATION.md).

---

## 8. Limitations, stated plainly

- **One organization.** The two real corpora come from a single (large, diverse)
  target. The known-answer corpus and the vulnerable test target broaden the
  picture but are not a substitute for many real targets.
- **One machine.** Timings are from a laptop-class CPU under a pinned clock.
  Absolute seconds will differ on other hardware; the *ratios* between tools are
  the portable result.
- **Coverage is a human-defined notion of "real endpoint."** The classifier and
  ground truth encode judgement about what counts as surface versus noise. The
  raw outputs and per-class data are published so that judgement can be
  re-checked rather than trusted.
- **udud's keep-bias is a default, not a law.** This report measures the shipping
  default, which favors coverage over a minimal output. That is the right default
  for finding vulnerabilities; teams optimizing purely for output size should
  measure their preferred configuration.

---

## 9. Recommendation

For an attack-surface recon pipeline, udud is the recommended deduplicator. It is
the only tool tested that keeps the attack surface intact *and* runs cheaply and
fast enough to scale across a fleet of targets:

- it preserves more real endpoint surface than any tool that actually
  deduplicates, including the object-ID endpoints where IDOR bugs live;
- it does so at a fraction of the memory and time of the alternatives, which
  lowers infrastructure cost and shortens every recon cycle;
- and it does not fall over on large targets, where the alternatives either
  exhaust memory or never finish.

The trade — a larger output than the most aggressive folders — is the correct one
for a security pipeline, and is configurable for teams with different priorities.
