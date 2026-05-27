# xcull benchmark: the full report

This is the evidence behind the summary in [`README.md`](README.md). The
question it answers is direct: for a recon pipeline, why run xcull instead of
one of the four established deduplicators, and what does that choice cost or
save across a fleet of assets?

Every number in this report comes from one input: the 780,200-URL
known-answer corpus `data/D_unified.full`. The corpus is generated
deterministically by `harness/synth_gen.py`, so the ground truth, the
reduction ratio, the throughput, the peak memory, and the false merge
rate all share the same source data. The recipe is in Section 7 and the
raw measurement files live under `raw/`.

## 1. The stage and what it has to deliver

A URL deduplicator sits at the front of a recon pipeline. It takes the raw
URLs harvested for each asset in scope and reduces them to the working set
that scanners and testers process. In a continuous program that runs across a
large fleet, the deduplicator decides three outcomes:

- Capacity and cost. Its throughput sets how many assets a worker clears per
  cycle; its memory sets how many workers fit on a box.
- Reach. Whether very large assets finish at all.
- Security quality. Every distinct endpoint it folds away by mistake is an
  endpoint nothing downstream ever tests.

The properties below are listed in the order a platform owner weighs them.

1. Completion time, the wall clock on one input.
2. Throughput, in URLs per second.
3. Peak memory.
4. Attack surface retained.
5. False merge rate, the security quality metric.
6. Streaming behaviour.
7. Reduction ratio.
8. CPU efficiency.

This report takes them in that order, then gives methodology, the passthrough
caveat, the reproduce recipe, and the limitations.

## 2. Result summary

One corpus, 780,200 URLs, every tool in its documented default mode, pinned
to one core, page cache primed, best of five timed trials.

| Metric | xcull | urldedupe | uro | urless | uddup |
|---|---:|---:|---:|---:|---:|
| Completion time | **1.73 s** | 2.27 s | 7.36 s | 8.83 s | DNF (>600 s) |
| Throughput | **451,000 URLs/s** | 343,000 URLs/s | 106,000 URLs/s | 88,000 URLs/s | DNF |
| Peak RAM | **22.6 MB** | 193.8 MB | 27.6 MB | 40.5 MB | DNF |
| Output lines | 115,764 | 380,650 | 64,667 | 64,138 | DNF |
| Reduction | 85.2 % | 51.2 % (near-passthrough) | 91.7 % | 91.8 % | DNF |
| Attack surface retained | **100 %** | 100 % (passthrough) | 97.77 % | 96.82 % | DNF |
| False merge rate | **0 %** | 0 % (passthrough) | 2.23 % | 3.18 % | DNF |

xcull is first on completion time, first on throughput, first on peak RAM, and
first on false merge rate in the same run. `urldedupe` matches xcull on false
merge rate only as a passthrough artifact: it keeps 380,650 lines for 55,920
canonical groups, so it cannot merge two groups by mistake because it folds
almost nothing. `uro` and `urless` produce a shorter list by destroying whole
endpoint classes (Section 4.2). `uddup` does not finish a 780k input; its
cost grows quadratically and it times out past roughly 50,000 URLs.

## 3. Capacity and cost

### 3.1 Completion time

Completion time is the wall clock to finish one input on one core. It is the
most direct answer to "how fast does my pipeline move".

| Tool | Completion (780,200 URLs) | Relative to xcull |
|---|---:|---:|
| **xcull** | **1.73 s** | 1.0x |
| urldedupe | 2.27 s | 1.31x slower |
| uro | 7.36 s | 4.25x slower |
| urless | 8.83 s | 5.10x slower |
| uddup | did not finish (>600 s) | n/a |

### 3.2 Throughput

Throughput is the input rate a single worker sustains. In a continuous program
it sets fleet capacity directly: at 451k URLs/sec one xcull worker clears a
780k-URL asset in under two seconds.

| Tool | Throughput | Relative to xcull |
|---|---:|---:|
| **xcull** | **451,000 URLs/s** | 1.0x |
| urldedupe | 343,000 URLs/s | 0.76x (near-passthrough) |
| uro | 106,000 URLs/s | 0.24x |
| urless | 88,000 URLs/s | 0.20x |
| uddup | did not finish | n/a |

### 3.3 Peak memory

Peak resident memory sets cost per worker and how many run side by side.

| Tool | Peak memory | Relative to xcull |
|---|---:|---:|
| **xcull** | **22.6 MB** | 1.0x |
| uro | 27.6 MB | 1.22x |
| urless | 40.5 MB | 1.79x |
| urldedupe | 193.8 MB | 8.6x |
| uddup | did not finish | n/a |

xcull has the lowest peak memory of every tool that produces output. Run a
dozen assets in parallel and the difference between 22.6 MB and 193.8 MB per
job is the difference between one small shared box and a dedicated server.

## 4. Security quality

### 4.1 False merge rate on the known-answer corpus

Because `D_unified.full` is generated with a fixed set of canonical endpoint
groups whose correct groupings are recorded in `data/D_unified.truth.json`,
every merge that destroys a group can be counted exactly. False merge rate is
the fraction of canonical groups for which the tool's output contains zero
representatives. Lower is better, because each wrong merge removes an endpoint
from every downstream scan.

| Tool | Canonical groups | Destroyed | False merge rate | Surface retained |
|---|---:|---:|---:|---:|
| **xcull** | 55,920 | 0 | **0.00 %** | 100.00 % |
| urldedupe | 55,920 | 0 | 0.00 % (near-passthrough) | 100.00 % |
| uro | 55,920 | 1,248 | 2.23 % | 97.77 % |
| urless | 55,920 | 1,777 | 3.18 % | 96.82 % |
| uddup | — | — | DNF | DNF |

xcull has a 0 % false merge rate, the same as `urldedupe`, but reaches it the
opposite way: `urldedupe`'s 0 % is the passthrough artifact, a tool that
keeps 380,650 lines for 55,920 groups cannot merge two groups by mistake and
has not deduplicated either. xcull reaches 0 % while removing 85.2 % of the
input, so it is the only tool in the table that achieves zero false merges
and a real reduction at the same time.

### 4.2 What `uro` and `urless` actually destroy

The per-class detail in [`raw/synth_eval.csv`](raw/synth_eval.csv) shows the
false merges as full-class deletions, not as scattered noise:

| Class | Total groups | xcull kept | uro kept | urless kept |
|---|---:|---:|---:|---:|
| GENUINE_DISTINCT | 50,000 | **50,000** | 49,034 | 48,488 |
| JSESSIONID | 5 | **5** | **0** | **0** |
| TITLE_SLUG | 260 | **260** | **0** | **0** |
| UUID | 15 | **15** | **0** | 15 |
| NUMERIC_ID | 30 | **30** | 28 | **30** |
| CACHE_BUST | 250 | 250 | 250 | 250 |
| HEX_HASH | 10 | 10 | 10 | 10 |
| LFI_PARAM | 50 | 50 | 50 | 50 |
| OPEN_REDIRECT | 50 | 50 | 50 | 50 |
| PARAM_ORDER | 50 | 50 | 50 | 50 |
| SRCDISC | 200 | 200 | 200 | 200 |
| TRAILING_SLASH | 5,000 | 5,000 | 5,000 | 5,000 |

`uro` deletes every JSESSIONID, every TITLE_SLUG, every UUID, and two
NUMERIC_ID classes; `urless` deletes every JSESSIONID and every TITLE_SLUG.
Each deleted class is one endpoint surface that no downstream scan ever
visits. xcull keeps every canonical group.

### 4.3 The one trade xcull makes on purpose

xcull is keep-biased. When a URL is ambiguous, for example it carries an
object ID, a session token, or an opaque hash, the default keeps it rather
than fold it away, because that is where broken-object-level-authorization
and IDOR bugs hide. Collapsing `/order/1001` and `/order/1002` to one line
erases the evidence that other objects exist.

The cost is a larger output than the aggressive folders produce. On
`D_unified.full` xcull emits 115,764 lines against `uro`'s 64,667. Part of
that gap is real surface xcull keeps and `uro` deletes (Section 4.2); part is
genuine redundancy xcull chose not to risk folding, for example the same
endpoint reached with many rotating session tokens. The trade is intentional:
a few thousand lines a scanner absorbs in seconds, in exchange for not
silently dropping a testable endpoint. Teams that prefer a smaller, more
aggressively folded list can run `-F`. Every number here is the shipping
default, which optimizes for not losing surface.

### 4.4 Two scoring views, both published

Section 4.1 measures "did the tool keep at least one representative per
endpoint class". That is the right question when the unit of work is the
endpoint template. It is the wrong question when the unit of work is the
distinct object: an IDOR scan against 15,000 distinct `/order-N/<UUID>` URLs
is 15,000 authorization checks, not one. Under the canonical-group metric, a
tool that keeps all 15,000 distinct UUIDs takes the 14,985 extra survivors
as false positives and is penalized for preserving the enumeration surface.

[`raw/synth_prf_recon.csv`](raw/synth_prf_recon.csv) answers the second
question alongside the first. For the three classes where each distinct
value is a distinct attack target (`UUID`, `HEX_HASH`, `JSESSIONID`), it
counts true positives at the object level: distinct values preserved out of
distinct values in the input. Every other class reuses the canonical-group
score unchanged, so the two metrics agree wherever object-level distinctness
is not a recon question. Both files are written on every run; nothing in
Section 4.1 changes.

## 5. Streaming, reduction, and CPU

### 5.1 Streaming

xcull reads standard input and writes standard output, so it drops into any
pipeline between collection and scanning. The default mode buffers until end
of input because a covering superset of a query key-set can arrive after a
subset, so the kept output is written once, in first-seen order, at end of
input. The `-k` and `-x` modes stream one line at a time in constant memory
for pipelines that need backpressure rather than a single ordered pass.

### 5.2 Reduction ratio

Reduction is how much redundant scanner work the stage removes. It is only
meaningful next to surface retained, because deleting real classes also
shrinks the output.

| Tool | Output lines | Reduction | Surface retained |
|---|---:|---:|---:|
| **xcull** | 115,764 | 85.2 % | **100 %** |
| urldedupe | 380,650 | 51.2 % | 100 % (pass) |
| uro | 64,667 | 91.7 % | 97.77 % |
| urless | 64,138 | 91.8 % | 96.82 % |

`uro` and `urless` show a higher reduction only by deleting whole endpoint
classes (Section 4.2). xcull removes 85 % of the lines while keeping every
canonical group.

### 5.3 CPU efficiency

xcull uses 1.74 CPU-seconds on `D_unified.full`, single core, against
`urldedupe`'s 2.27 and `uro`'s 7.36. Wall time and CPU time match because
the run is single-threaded, so the wall figures in Section 3 are also the
CPU cost.

## 6. How each number was measured

Two ideas are kept separate, because conflating them is how deduplicators get
marketed dishonestly:

1. Quality: did the real attack surface survive, and how often did the tool
   merge distinct endpoints by mistake. Reported as surface retained (Section
   4.1) and the per-class detail in Section 4.2.
2. Cost: completion time, throughput, peak memory, and CPU to get there
   (Section 3, Section 5).

A tool that copies its input scores a perfect surface-retained while folding
nothing, which is why surface retained is always shown next to output size
and `urldedupe`'s 100 % is labelled passthrough throughout.

Quality is computed by `harness/synth_eval.py`, which maps every output URL
to a (class, group_id) under the same parsing rules as `harness/synth_gen.py`
uses to label the input. RFC 3986 directory-index equivalence and trailing-
slash equivalence are applied to both ground truth and tool output, so a
tool that emits `/dir` is credited for a truth entry of `/dir/index.html`
and vice versa. Normalizing both sides means a tool is never penalized for
emitting the same endpoint in a cosmetically different form.

`synth_eval.py` emits two scoring views on every run. The canonical-group
view (`raw/synth_prf.csv`, `raw/synth_prf_byclass.csv`) is the Section 4.1
false merge metric: one true positive per endpoint class. The enumeration-
surface view (`raw/synth_prf_recon.csv`, `raw/synth_prf_recon_byclass.csv`,
Section 4.4) is identical for non-enumerable classes; for `UUID`,
`HEX_HASH`, and `JSESSIONID` it counts true positives at the object level.
Both files are generated from the same single run of each tool, so the two
views are directly comparable line by line.

Cost is measured on a pinned clock so timings are low-variance and
comparable: each tool is pinned to one core (`taskset -c 2`), the page cache
is primed before the first trial, and the reported wall time is the best of
five trials. Peak memory is the maximum resident set across runs, measured
via `runstat`'s `getrusage` capture. xcull figures are the shipping default
(xcull v23). Competitor figures use the documented invocation for each tool
(Section 7).

## 7. Reproducing the benchmark

Input is frozen and checksummed (SHA-256 in `raw/datasets.csv`):

| Corpus | URLs | Bytes | Canonical groups |
|---|---:|---:|---:|
| `D_unified.full` | 780,200 | 44,168,044 | 55,920 |

Recipe:

```sh
# 1. regenerate the corpus from its deterministic generator
#    (random seed is fixed, so the bytes match raw/datasets.csv)
python3 harness/synth_gen.py

# 2. verify the corpus matches the published SHA-256
sha256sum -c <(awk -F, 'NR>1{print $4"  data/"$1}' raw/datasets.csv)

# 3. build xcull (default configuration)
git clone https://github.com/xcull/xcull /tmp/xcull
cc -O3 -march=native -flto -Wall -Wno-misleading-indentation \
   -o /usr/local/bin/xcull /tmp/xcull/xcull.c

# 4. measure cost (one input, five tools, five trials per tool)
harness/bench.sh

# 5. measure quality (false merge rate, surface retained, per-class detail)
python3 harness/synth_eval.py
```

Tool invocations (also in `harness/INVOCATION.md`):

| Tool | Invocation |
|---|---|
| xcull | `xcull < D_unified.full > out` |
| uro | `uro -i D_unified.full > out` |
| urldedupe | `urldedupe < D_unified.full > out` |
| urless | `urless -nb < D_unified.full > out` (`-i` is inert under a pipe) |
| uddup | `uddup -u D_unified.full -o out` |

Each tool's output on `D_unified.full` is published under `raw/outputs/` so
quality can be recomputed without re-running the tools.

## 8. Limitations, stated plainly

- One input. The benchmark is run on one 780k known-answer corpus. The
  corpus distribution is designed to match the shape of a real recon
  capture (heavy templated bulk plus a long tail of distinct endpoints
  plus a small enumerable IDOR surface), but it is one design. A team
  running real traffic should also measure their own corpora.
- One machine. Timings are from a single CPU under a pinned clock.
  Absolute seconds differ on other hardware; the ratios between tools are
  the portable result.
- Surface retained is a corpus-defined notion of a real endpoint. The
  classifier and ground truth encode the corpus author's judgement about
  what counts as a distinct endpoint. The raw outputs and the labelled
  input are published so that judgement can be re-checked.
- xcull's keep-bias is a default, not a law. This report measures the
  shipping default, which favors surface retained over a minimal output.
  Teams optimizing purely for output size should measure their preferred
  configuration (`-F` for the most aggressive fold).
- `uddup` is reported as DNF on `D_unified.full`. Its cost grows
  quadratically and it times out well before 780k URLs. Its behaviour on
  much smaller inputs is not in scope of this report.

## 9. Recommendation

For a recon deduplication stage, xcull is the recommended tool. In one run on
the same 780k known-answer input it leads on completion time, on throughput,
on peak memory, and on false merge rate, including on the object-ID
endpoints where access-control bugs live. The trade, a larger output than
the most aggressive folders, is the correct one for a security pipeline and
is configurable for teams with different priorities.
