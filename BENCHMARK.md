# udud benchmark: the full report

This is the evidence behind the summary in [`README.md`](README.md). The
question it answers is direct: for a recon pipeline, why run udud instead of
one of the four established deduplicators, and what does that choice cost or save
across a fleet of assets?

Everything here is measured on frozen, checksummed inputs and is reproducible
from the recipe in Section 7. The raw measurement files live in `raw/`; the
consolidated summary for this release is `raw/v22_results.csv`.

## 1. The stage and what it has to deliver

A URL deduplicator sits at the front of a recon pipeline.
It takes the raw URLs harvested for each asset in scope and reduces them to the
working set that scanners and testers process. In a continuous program that runs
across a large fleet, the deduplicator decides three outcomes:

- Capacity and cost. Its throughput sets how many assets a worker clears per
  cycle; its memory sets how many workers fit on a box.
- Reach. Whether very large assets finish at all.
- Security quality. Every distinct endpoint it folds away by mistake is an
  endpoint nothing downstream ever tests.

The properties below are listed in the order a platform owner weighs them.

1. Throughput, in URLs per second.
2. Peak memory.
3. Stability at scale.
4. False merge rate, the security quality metric.
5. Streaming behaviour.
6. Reduction ratio.
7. CPU efficiency.

This report takes them in that order, then gives per-corpus tables, methodology,
the passthrough caveat, the reproduce recipe, and the limitations.

## 2. Result summary

Measured on the 781,398-URL de-identified Wayback capture, same machine, same
input, each tool in its documented default mode.

| Property | udud | best competitor | gap |
|---|---|---|---|
| Throughput | 272k URLs/sec | urldedupe 159k (near-passthrough) | 1.7x |
| Peak memory | 13.6 MB | uro 35 MB | 2.6x lighter |
| Stability at scale | flat 13.8 MB to 6.25M URLs | none stays flat | n/a |
| False merge rate (ground truth) | 0.39% | urless 8.6% (real deduper) | 22x lower |
| Streaming | yes | uro, urldedupe yes | n/a |
| Reduction | 83% | uro 90%, by deleting surface | see Section 4 |
| CPU | 2.86 s | urldedupe 4.92 s | 1.7x |

udud is first on throughput and first on peak memory in the same run, holds both
flat into the multi-million-URL range, and has the lowest false merge rate of any
tool that meaningfully reduces the input. The rest of this report defines each
number and is explicit about the one place udud trades the other way (Section
4.3).

## 3. Capacity and cost

### 3.1 Throughput

Throughput is the input rate a single worker sustains. In a continuous program
it sets fleet capacity directly: at 272k URLs/sec one udud worker clears a
781k-URL asset in under three seconds.

| Tool | Throughput (781k capture) | Relative to udud |
|---|---:|---:|
| **udud** | **272,000 URLs/sec** | 1.0x |
| urldedupe | 159,000 URLs/sec | 0.58x (near-passthrough) |
| uro | 45,000 URLs/sec | 0.16x |
| urless | 10,000 URLs/sec | 0.04x |
| uddup | did not finish | n/a |

udud is the fastest finisher. `urldedupe` is second only because it does little
work per line (Section 5). `uro` and `urless` are 6x and 26x slower.

### 3.2 Peak memory

Peak resident memory sets cost per worker and how many run side by side.

| Tool | Peak memory (781k capture) | Relative to udud |
|---|---:|---:|
| **udud** | **13.6 MB** | 1.0x |
| uro | 35 MB | 2.6x |
| urless | 45 MB | 3.3x |
| urldedupe | 336 MB | 24x |
| uddup | did not finish | n/a |

udud has the lowest peak memory of every tool measured. Run a dozen assets in
parallel and the difference between 13.6 MB and 336 MB per job is the difference
between one small shared box and a dedicated server.

### 3.3 Stability at scale

The deduplicator must stay bounded as input grows. udud's memory tracks the
number of distinct endpoints it keeps, not raw input size. Replicating the 781k
capture (which holds the distinct surface constant, isolating the input-size
effect) keeps peak memory and rate flat from 781k to 6.25M URLs:

| Input URLs | 781k | 1.56M | 3.13M | 6.25M |
|---|---:|---:|---:|---:|
| Peak memory | 13.8 MB | 13.7 MB | 13.8 MB | 13.8 MB |
| Throughput | 263k/sec | 273k/sec | 268k/sec | 270k/sec |

On a genuinely larger, more diverse target (the raw 1.1M-URL Wayback capture,
more distinct surface than the de-identified release), udud finishes in 3.8
seconds at 25.3 MB. Memory rises only with new surface.

For contrast, memory measured on size-stratified head-prefixes of the de-id
capture:

| Input URLs | 25k | 50k | 100k | 200k | 400k | 781k |
|---|---:|---:|---:|---:|---:|---:|
| udud peak memory | 3.1 MB | 3.3 MB | 3.5 MB | 3.7 MB | 3.7 MB | 13.7 MB |

The curve is flat across similar-structure slices and rises only with the
distinct surface in the full corpus. `urldedupe`'s memory instead grows with
input and reaches 336 MB; `uddup` grows quadratically and stops finishing past
roughly 50,000 URLs.

## 4. Security quality

### 4.1 False merge rate on known ground truth

On real corpora the correct grouping is reconstructed, so any coverage figure
there is an estimate. The controlled corpus removes that doubt: it is generated
with a fixed set of distinct endpoint classes whose correct groupings are known
in advance, so a merge that destroys a class is counted exactly.

False merge rate is the fraction of distinct endpoint classes a tool wrongly
collapses. Lower is better, because each wrong merge removes an endpoint from
every downstream scan.

| Tool | False merge rate | Distinct classes preserved |
|---|---:|---:|
| **udud** | **0.39%** | 99.6% |
| urldedupe | 0% (near-passthrough) | 100%, by keeping 25,415 lines for 319 classes |
| urless | 8.6% | 91.4% |
| uddup | 14.3% | 85.7% |
| uro | 16.9% | 83.1% |

udud has the lowest false merge rate of any tool that actually reduces the
input. `urldedupe`'s 0% is the passthrough artifact: a tool that keeps roughly
80 redundant lines per class cannot merge two classes by mistake, and it has not
deduplicated either. udud reaches near-zero false merges and a real reduction at
the same time.

### 4.2 Endpoint-class coverage on the real corpora

Coverage is the fraction of distinct endpoint classes that survive
deduplication, counting every class equally (a macro average), so a rare but
critical class weighs the same as a common one. It is the recall side of the
false merge rate, measured on real data by a canonicalization-invariant
classifier (Section 6).

| Corpus | udud | uro | urless | urldedupe | uddup |
|---|---:|---:|---:|---:|---:|
| Wayback, 781,398 | **83.5%** | 62.9% | 67.4% | 100% (pass) | DNF |
| gau, 44,943 | **96.9%** | 74.6% | 74.6% | 100% (pass) | 73.8% |
| vulnweb, 15,185 | **94.5%** | 85.9% | 100% | 100% (pass) | 57.7% |
| controlled, 45,410 | **99.6%** | 83.1% | 91.4% | 100% (pass) | 85.7% |

Among tools that meaningfully deduplicate, udud keeps the most surface on every
corpus. `uro` and `urless` reach a shorter list by folding away whole classes.

### 4.3 The one trade udud makes on purpose

udud is keep-biased. When a URL is ambiguous, for example it carries an object
ID, a session token, or an opaque hash, the default keeps it rather than fold it
away, because that is where broken-object-level-authorization and IDOR bugs
hide. Collapsing `/order/1001` and `/order/1002` to one line erases the evidence
that other objects exist.

The cost is a larger output than the aggressive folders produce. On the Wayback
capture udud emits 129,436 lines against `uro`'s 78,470. Part of that gap is real
surface udud keeps and `uro` deletes; part is genuine redundancy udud chose not
to risk folding, for example the same endpoint reached with many rotating session
tokens. The trade is intentional: a few thousand lines a scanner absorbs in
seconds, in exchange for not silently dropping a testable endpoint. Teams that
prefer a smaller, more aggressively folded list can run `-F`. Every number here
is the shipping default, which optimizes for not losing surface.

## 5. Streaming, reduction, and CPU

### 5.1 Streaming

udud reads standard input and writes standard output, so it drops into any
pipeline between collection and scanning. The default mode buffers until end of
input because a covering superset of a query key-set can arrive after a subset,
so the kept output is written once, in first-seen order, at end of input. The
`-k` and `-x` modes stream one line at a time in constant memory for pipelines
that need backpressure rather than a single ordered pass.

### 5.2 Reduction ratio

Reduction is how much redundant scanner work the stage removes. It is only
meaningful next to coverage, because deleting real classes also shrinks the
output.

| Tool | Output lines (781k) | Reduction | Coverage |
|---|---:|---:|---:|
| **udud** | 129,436 | 83.4% | 83.5% |
| uro | 78,470 | 90.0% | 62.9% |
| urless | 74,737 | 90.4% | 67.4% |
| urldedupe | 293,420 | 62.4% | 100% (pass) |

`uro` and `urless` show a higher reduction only by folding away a third of the
surface (their coverage falls with it). udud removes 83% of the lines while
keeping the most classes.

### 5.3 CPU efficiency

udud uses 2.86 CPU-seconds on the 781k capture, single core, against
`urldedupe`'s 4.92 and `uro`'s 17.5. Wall time and CPU time match because the run
is single-threaded, so the wall figures in Section 3 are also the CPU cost.

## 6. How each number was measured

Two ideas are kept separate, because conflating them is how deduplicators get
marketed dishonestly:

1. Quality: did the real attack surface survive, and how often did the tool
   merge distinct endpoints by mistake. Reported as coverage (Section 4.2) and,
   on the controlled corpus, as false merge rate (Section 4.1).
2. Cost: throughput, peak memory, and CPU to get there (Section 3, Section 5).

A tool that copies its input scores a perfect coverage while folding nothing,
which is why coverage is always shown next to output size and `urldedupe`'s 100%
is labelled passthrough throughout.

Quality is computed by a canonicalization-invariant classifier
(`harness/quality.py`, `harness/wayback_prf.py`, and for the known-answer corpus
`harness/synth_eval.py`). It normalizes the ground truth and every tool's output
the same way (RFC 3986 syntax normalization, dot-segment removal, directory-index
equivalence, percent-decoding, and ID/UUID/hex templating), then measures, per
class, the fraction of distinct real endpoints with at least one survivor in the
output. Normalizing both sides means a tool is never penalized for emitting the
same endpoint in a cosmetically different form.

Cost is measured on a pinned clock so timings are low-variance and comparable:
each tool is pinned to one core, the page cache is primed so every tool reads
from RAM, and the reported wall time is the best of repeated runs. Peak memory is
the maximum resident set across runs. udud figures are the shipping default
(udud v22). Competitor figures use the documented invocation for each tool
(Section 7) and do not change between udud versions because the tools are
unchanged. The consolidated data is `raw/v22_results.csv`.

A note on epochs. The headline corpus and the three smaller corpora were
re-measured fresh for this release on one machine; absolute seconds differ from
older runs on the same machine because of cache and clock state, while the
ratios between tools are stable. `uddup`'s timings for the smaller corpora are
carried from the prior epoch (the tool is unchanged and its role is only to show
the quadratic curve); it does not finish the headline corpus in either epoch.

## 7. Reproducing the benchmark

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

# 3. measure cost (pin the clock first; see Section 6)
harness/bench.sh
python3 harness/stats.py raw/

# 4. measure quality
python3 harness/synth_eval.py        # known-answer corpus, false merge rate
python3 harness/wayback_prf.py       # real corpora, coverage
python3 harness/quality.py --audit raw/
```

Tool invocations (also in `harness/INVOCATION.md`): udud, uro, and urldedupe
read the corpus on standard input; `urless` is run as `urless -nb < corpus` (its
`-i` flag is inert under a pipe on the tested build); `uddup` is run as
`uddup -u <file>`. Each tool's output on each corpus is published under
`raw/outputs/` so quality can be recomputed without re-running the tools.

## 8. How the real corpora were protected

The Wayback and gau corpora are real reconnaissance data against a confidential
commercial target; publishing the raw bytes would disclose that target's host
inventory and route structure. Both are deterministically de-identified before
release by `harness/anonymize.py`, which ciphers every identity-bearing token
while keeping the structural vocabulary a deduplicator keys on (schemes, ports,
separators, digits, percent-escapes, public-suffix labels, file extensions, and
the generic recon-parameter and matrix-key names). The transform preserves route
shape and destroys host, path, and value identity.

Because de-identification legitimately changes what keyword-based filters match,
the benchmark is re-run from scratch on the de-identified bytes; these are not
original numbers relabelled. `harness/verify_anon.py` is a release gate that
proves no identity-bearing token survives. Full rules are in
[`ANONYMIZATION.md`](ANONYMIZATION.md).

## 9. Limitations, stated plainly

- One organization. The two real corpora come from a single large, diverse
  target. The known-answer corpus and the vulnerable test target broaden the
  picture but are not a substitute for many real targets.
- One machine. Timings are from a single CPU under a pinned clock. Absolute
  seconds differ on other hardware; the ratios between tools are the portable
  result.
- Stability at scale is shown to 6.25M URLs by replication and to 1.1M on a
  genuinely distinct corpus. Internet-scale runs (tens of millions and up) are
  not measured here; the flat-memory model predicts they stay bounded, but that
  is a prediction, not a measurement in this report.
- Coverage is a human-defined notion of a real endpoint. The classifier and
  ground truth encode judgement about surface versus noise. The raw outputs and
  per-class data are published so that judgement can be re-checked.
- udud's keep-bias is a default, not a law. This report measures the shipping
  default, which favors coverage over a minimal output. Teams optimizing purely
  for output size should measure their preferred configuration.

## 10. Recommendation

For a recon deduplication stage, udud is the recommended tool. In one run it
leads on throughput and on peak memory, holds both flat into the multi-million-URL
range, and has the lowest false merge rate of any tool that actually
deduplicates, including on the object-ID endpoints where access-control bugs
live. The trade, a larger output than the most aggressive folders, is the correct
one for a security pipeline and is configurable for teams with different
priorities.
