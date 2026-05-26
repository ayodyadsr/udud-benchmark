# udud benchmark: URL deduplication for recon at scale

udud is a security-aware URL canonicalization engine. In a recon pipeline it
sits at the front of the flow: it takes the raw URLs harvested for every asset
in scope and reduces them to the working set
that scanners, fuzzers, and testers actually process. That one stage sets three
things for the whole program: how many assets a worker can process per hour,
how much memory each worker costs, and whether a sensitive endpoint survives to
be tested at all.

This benchmark measures udud against the four deduplicators most teams already
run (`urldedupe`, `uro`, `urless`, `uddup`) on a 781,398-URL real recon capture,
two smaller real captures, and a controlled corpus where the correct answer is
known exactly.

Result in one line: udud leads on throughput and on peak memory at the same
time, holds both flat into the multi-million-URL range, and folds away the least
real attack surface of any tool that meaningfully deduplicates.

## What this stage has to deliver, in priority order

These are the properties a recon program actually buys when it picks a
deduplicator, ordered the way a platform owner weighs them.

| # | Property | Why it decides the program | udud on the 781k capture |
|---|---|---|---|
| 1 | Throughput (URLs/sec) | Sets continuous-monitoring capacity per worker | 260,000 URLs/sec, fastest measured |
| 2 | Peak memory | Sets cost per worker and how many run in parallel | 13.7 MB, lowest measured |
| 3 | Stability at scale | Decides whether large assets finish at all | flat 13.8 MB and constant rate to 6.25M URLs |
| 4 | False merge rate | Security quality: a wrong merge hides an endpoint | 0.39% on known ground truth, lowest of any real deduplicator |
| 5 | Streaming | Constant-memory stdin to stdout fits any pipeline | yes (`-k` / `-x`) |
| 6 | Reduction ratio | How much redundant scanner work is removed | 83% fewer lines |
| 7 | CPU efficiency | Single-core cost of the run | 3.00 CPU-seconds |

Properties 1 through 3 are capacity and cost. Property 4 is the security
question, and it is the one that justifies running a deduplicator at all: a tool
that merges two genuinely distinct endpoints into one removes the second from
every scan that follows. Everything below is built around proving 4 without
giving up 1 through 3.

## Headline results: de-identified Wayback capture, 781,398 URLs

Same machine, same input, each tool in its documented default mode, pinned to
one core, page cache primed, best of three timed runs.

| Tool | Throughput | Peak memory | Endpoint-class coverage | Output lines | Finishes at fleet scale |
|---|---:|---:|---:|---:|:--:|
| **udud** | **260k URLs/sec** | **13.7 MB** | **83.5%** (best real deduplicator) | 129,436 | yes |
| urldedupe | 159k URLs/sec | 336 MB | 100% by near-passthrough (2.3x the output) | 293,420 | memory-bound |
| uro | 45k URLs/sec | 35 MB | 62.9% (folds away 37% of classes) | 78,470 | slow |
| urless | 10k URLs/sec | 45 MB | 67.4% (folds away 33% of classes) | 74,737 | too slow |
| uddup | did not finish | n/a | n/a | n/a | no |

How to read it:

- udud is first on throughput and first on peak memory in the same run. It is
  1.7x the throughput of `urldedupe`, 6x `uro`, and 26x `urless`, while using
  less memory than any of them.
- `urldedupe` reaches 100% coverage only because it barely deduplicates. It
  removes exact byte duplicates and keeps every value, locale, and session-token
  variant, so it emits 2.3x udud's output and needs 24x the memory. It cannot
  drop a real endpoint because it folds almost nothing. That is a passthrough,
  not a deduplicator.
- `uro` and `urless` produce a short, tidy list by folding away a third of the
  endpoint classes. Those folded endpoints are exactly the ones a scanner then
  never sees.
- `uddup` does not finish a target this size. Its cost grows with the square of
  the input and it stops completing past roughly 50,000 URLs.

## The gold metric: false merge rate on known ground truth

On the real corpora the "correct" answer is reconstructed, so coverage there is
a strong estimate, not a proof. The controlled corpus removes that doubt. It is
generated with a fixed set of distinct endpoint classes whose correct groupings
are known in advance, so a merge that destroys a class can be counted exactly.

False merge rate is the fraction of distinct endpoint classes a tool wrongly
collapses, so a lower number means fewer endpoints silently removed from scope.

| Tool | False merge rate | Reads as |
|---|---:|---|
| **udud** | **0.39%** | preserves 99.6% of distinct classes |
| urldedupe | 0% (near-passthrough) | keeps 25,415 lines for 319 classes, so it folds almost nothing |
| urless | 8.6% | drops about 1 in 12 classes |
| uddup | 14.3% | drops about 1 in 7 classes |
| uro | 16.9% | drops about 1 in 6 classes |

udud has the lowest false merge rate of any tool that actually reduces the
input. `urldedupe`'s 0% is the passthrough artifact again: a tool that keeps
roughly 80 redundant lines per class cannot merge two classes by mistake, but it
also has not done the job. udud reaches near-zero false merges and a real 83%
reduction at the same time, which is the combination the other tools each miss.

This holds on every corpus tested. Full per-class numbers are in
[`BENCHMARK.md`](BENCHMARK.md) and the raw CSVs under `raw/`.

## Stability at scale

Recon runs continuously and some assets carry millions of historical URLs, so
the deduplicator has to stay bounded as input grows. udud's memory tracks the
number of distinct endpoints it keeps, not the size of the input. Replicating
the 781k capture up to 6.25M URLs (the distinct surface stays the same, so this
isolates the input-size effect) keeps peak memory and throughput flat:

| Input URLs | 781k | 1.56M | 3.13M | 6.25M |
|---|---:|---:|---:|---:|
| Peak memory | 13.8 MB | 13.7 MB | 13.8 MB | 13.8 MB |
| Throughput | 263k/sec | 273k/sec | 268k/sec | 270k/sec |

On a genuinely larger and more diverse target (a raw 1.1M-URL Wayback capture
with more distinct surface), udud finishes in 3.8 seconds at 25.3 MB. The memory
rises only with new surface, never with raw volume. `urldedupe`'s memory instead
grows with input and reaches 336 MB on the 781k capture; `uddup`'s cost grows
quadratically and it stops finishing well before this scale.

## What this means for a recon program

- More assets per worker. The highest throughput and the lowest memory in the
  same run means a single worker covers more scope per cycle, and more workers
  fit on the same hardware.
- Fewer missed findings. udud folds away the least real surface of any tool that
  deduplicates, including the object-ID endpoints (`/order/1001`, `/order/1002`)
  where broken-object-level-authorization and IDOR bugs live. A lower false
  merge rate is a direct reduction in endpoints that never get scanned.
- Large assets complete. Bounded memory and linear time mean a target with
  millions of URLs still finishes in seconds, where the alternatives either
  exhaust memory or never return.

## The one trade udud makes on purpose

udud is keep-biased. When a URL is ambiguous, for example it carries an object
ID, a session token, or an opaque hash, the default keeps it instead of folding
it away, because that is where access-control bugs hide. The cost is a larger
output than the most aggressive folders produce. The trade is deliberate: a few
redundant lines a scanner absorbs in seconds, in exchange for not silently
dropping a testable endpoint. Teams that want a smaller list can fold object IDs
with `-F`. Every number in this report is the shipping default, and the full
per-class data, including the cases where the keep-bias lowers a shape-only
precision score, is published unedited under `raw/`.

## How to trust these numbers

- [`BENCHMARK.md`](BENCHMARK.md): the full report. How each tool was run and
  measured, the controlled corpus with known answers, results on every corpus,
  and the trade-offs stated plainly.
- [`AUDIT.md`](AUDIT.md): a per-line security audit of udud's most aggressive
  id-folding mode. Every removed URL is classified by hand to confirm it removed
  redundancy, not surface. The shipping default removes a strict subset of those
  lines, so the finding carries over.
- [`ANONYMIZATION.md`](ANONYMIZATION.md): how the real corpora were
  de-identified before release, and the gate that proves no customer-identifying
  data survives.
- `raw/`: the underlying measurement data. `raw/v23_results.csv` is the
  consolidated summary for this release; the per-trial detail sits alongside it.

The corpora are frozen and checksummed and the build and run recipe is in
[`BENCHMARK.md`](BENCHMARK.md), so every number here is reproducible.

## Corpora

| Corpus | URLs | What it is |
|---|---:|---|
| Wayback capture (de-identified) | 781,398 | a real large recon target, the scale case |
| Controlled ground truth | 45,410 | synthetic corpus where the correct answer is known exactly |
| `gau` capture (de-identified) | 44,943 | a real mid-size recon target |
| Vulnerable test target | 15,185 | a deliberately vulnerable application |

## Confidentiality

The Wayback and `gau` corpora are real recon captures of a confidential
commercial target. They are deterministically de-identified before release so no
host inventory or route structure is disclosed; see
[`ANONYMIZATION.md`](ANONYMIZATION.md).

## License

AGPL-3.0. See `LICENSE`.
