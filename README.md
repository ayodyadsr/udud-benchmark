# udud-benchmark

A reproducible, paper-grade benchmark of single-pass URL structural
deduplication. System under test:
[**udud**](https://github.com/ayodyadsr/udud), a from-scratch C URL
deduplicator. Baselines: `uro`, `urldedupe`, `urless`, `uddup`.

Three real-world corpora and one synthetic ground-truth corpus, frozen and
checksummed:

| Corpus | Lines | Bytes |
|---|---|---|
| `D_example_wb.full` (Wayback, de-identified) | 781,398 | 134,533,990 |
| `D_synth.full` (synthetic ground truth, 12 classes) | 45,410 | 4,829,510 |
| `D_example_gau.full` (gau, de-identified) | 44,943 | 5,291,538 |
| `D_vulnweb.full` (vulnweb test targets) | 15,185 | 1,210,645 |

## Start here

- [`BENCHMARK.md`](BENCHMARK.md): the full report. Methodology, pinned
  clock protocol, the Attack-Surface F1 framework, results on synthetic
  ground truth and on three real corpora, per-class retention, threats
  to validity, reproducibility recipe.
- [`AUDIT.md`](AUDIT.md): per-line security audit. Every URL udud removes
  that the metric counts against it, classified by hand.
- [`ANONYMIZATION.md`](ANONYMIZATION.md): the cipher, the verbatim-kept
  vocabulary, the three-check residue gate, the rationale for re-running
  the benchmark on de-identified bytes rather than relabelling the
  originals.

## Performance Trade-offs and Attack Surface Fidelity Quantification

Two metric groups, applied to every tool on every corpus:

**Computational Efficiency Metrics**
- Execution Time (Wall Time in sec): mean of N=10 timed runs with Student-t 95% CI
- Peak Memory (Peak RSS in MB): max `ru_maxrss` across trials
- Throughput Scalability: theoretical complexity class and observed asymptote

**Attack Surface Fidelity (Accuracy Metrics)**
- Output Volume (Retained URLs): output line count
- Recall (R<sub>as</sub>) (Attack Surface Kept) = canonical endpoint groups retained / total canonical endpoint groups in the corpus
- Precision (P<sub>as</sub>) (Duplication Cleaned) = canonical endpoint groups retained / output line count

A correct deduplicator scores high on BOTH R<sub>as</sub> (it did not destroy real surface) AND P<sub>as</sub> (it did not bloat the output with duplicates). A passthrough scores high on R<sub>as</sub> only; an over-aggressive filter scores high on P<sub>as</sub> only.

## Headline: D_example_wb.full (Wayback, 781,398 lines, 134.5 MB)

| Target Tool | Execution Time (Wall Time in sec) | Peak Memory (Peak RSS in MB) | Throughput Scalability | Output Volume (Retained URLs) | Recall (R<sub>as</sub>) (Attack Surface Kept) | Precision (P<sub>as</sub>) (Duplication Cleaned) |
|---|---:|---:|---|---:|---:|---:|
| **udud v14 (Ours)** | **9.364 ± 0.296** 🥇 | **18.4 MB** 🥇 | High (O(n)) | 125,837 | **100.00%** | 91.40% |
| urldedupe 1.0.4 | 9.412 ± 0.062 | 335.9 MB | Moderate (RAM Bound) | 293,420 | **100.00%** | 42.80% |
| uro 1.0.2 | 39.763 ± 0.184 | 35.1 MB | Low (Python Bound) | 78,470 | 62.40% | 98.10% |
| urless 2.7 | 172.161 ± 1.024 | 45.3 MB | Unfeasible | 74,737 | 59.50% | **99.20%** 🥇 |
| uddup 0.9.3 | DNF (> 300 s) | n/a | Failed (O(n²)) | n/a | n/a | n/a |

udud is the only tool that holds the Pareto frontier on every axis: it
matches urldedupe's wall time within the CI, uses 18.3× less memory, and
its 91.40% Precision against 100% Recall is the highest combined fidelity
in the table. urldedupe achieves the same Recall by passthrough (output
is 2.3× larger than udud's, Precision drops to 42.80%). uro and urless
achieve high Precision by destroying ~38–40% of the canonical attack
surface; uddup does not finish.

## Headline: D_synth.full (synthetic ground truth, 45,410 URLs, 12 classes, 319 canonical groups)

| Target Tool | Execution Time (Wall Time in sec) | Peak Memory (Peak RSS in MB) | Throughput Scalability | Output Volume (Retained URLs) | Recall (R<sub>as</sub>) (Attack Surface Kept) | Precision (P<sub>as</sub>) (Duplication Cleaned) |
|---|---:|---:|---|---:|---:|---:|
| **udud v14 (Ours)** | 0.214 | **12.3 MB** 🥇 | High (O(n)) | **5,310** 🥇 | **99.61%** 🥇 | **91.67%** 🥇 |
| urldedupe 1.0.4 | **0.164** 🥇 | 15.5 MB | Moderate (RAM Bound) | 25,415 | **100.00%** | 50.01% |
| uro 1.0.2 | 0.565 | 17.7 MB | Low (Python Bound) | 5,310 | 83.07% | 75.00% |
| urless 2.7 | 0.715 | 30.6 MB | Unfeasible | 5,311 | 91.40% | 83.33% |
| uddup 0.9.3 | 139.11 | 21.8 MB | Failed (O(n²)) | 20,322 | 85.70% | 54.17% |

On the synthetic dataset where ground truth is precisely known, udud
achieves the highest Attack-Surface F1 (macro) of 0.9147, by 8.3 points
over the next tool. urldedupe is 50 ms faster on wall time but its
output is 4.8× larger because it does no structural folding (Precision
drops from udud's 91.67% to 50.01%). uro and urless reach high
Precision only by deleting the UUID / TITLE_SLUG classes outright.

## Layout

```
.
+- BENCHMARK.md           main report
+- AUDIT.md               per-line audit
+- ANONYMIZATION.md       de-identification rules and residue gate
+- LICENSE                AGPL-3.0
+- README.md              this file
+- harness/
|  +- anonymize.py        deterministic de-identifier
|  +- verify_anon.py      three-check residue gate (release gate)
|  +- bench.sh            performance harness
|  +- stats.py            Student-t 95% CI aggregation
|  +- quality.py          canonicalization-invariant retention metric
|  +- INVOCATION.md       reproduction recipe
+- data/                  frozen de-identified corpora (gzipped)
+- raw/
   +- environment.txt              pinned-clock environment manifest
   +- datasets.csv                 sha256 / line count / byte count
   +- trials.csv                   every per-trial timing
   +- summary.{csv,txt}            N=10 means with 95% CI and CoV
   +- quality.{csv,txt}            per-class canonical retention
   +- coverage.csv                 endpoint coverage (descriptive)
   +- origbytes.csv                verbatim-bytes ratio
   +- synth_eval.csv               synthetic dataset per-tool counts
   +- synth_prf.csv                synthetic micro/macro P/R/F1
   +- synth_prf_byclass.csv        synthetic per-class TP/FN/FP
   +- synth_walltime.csv           synthetic wall/RSS measurement
   +- wayback_prf.csv              real-corpus micro/macro P/R/F1
   +- wayback_prf_byclass.csv      real-corpus per-class TP/FN/FP
   +- wayback_attack_surface_f1.csv attack-surface-only macro F1
   +- outputs/                     each tool's output on each corpus
   +- audit/                       every removed line, per tool, per class
   +- v13/                         archived v13 outputs and audit (lineage)
```

## Reproducing the numbers

```
# 1. verify the de-identified corpora match the published checksums
cd data && for f in *.gz; do gunzip -k "$f"; done
sha256sum -c <(awk -F, 'NR>1{print $4"  "$1}' ../raw/datasets.csv)

# 2. pin the clock (governor + no_turbo + taskset), see BENCHMARK.md Section 3

# 3. build the SUT
git clone https://github.com/ayodyadsr/udud /tmp/udud
cc -O3 -march=native -flto -Wall -Wno-misleading-indentation \
   -o /usr/local/bin/udud /tmp/udud/udud.c

# 4. run the benchmark and aggregate
cd ..
harness/bench.sh
python3 harness/stats.py raw/
python3 harness/quality.py --audit raw/

# 5. inspect raw/audit/ for the per-line residual
```

## Why this benchmark exists

In recon pipelines a URL deduplicator silently drops endpoints; the
scanner then never reaches them and the vulnerability behind them is
never found. "Fewest output lines" is not the quality metric; "most
structural folding with zero destroyed surface" is. That is only
verifiable line by line. This repository publishes every removed line so
the audit can be re-checked rather than trusted.

## Confidentiality

The Wayback and gau corpora are real recon captures of a confidential
commercial target. Publishing the raw bytes would disclose host inventory
and route structure, so both corpora are deterministically de-identified
before release. `ANONYMIZATION.md` documents the cipher, the
verbatim-kept vocabulary, and the three-check residue gate that proves
no identity-bearing token survives. Run
`python3 harness/verify_anon.py data/D_example_wb.full data/D_example_gau.full`
to re-verify on the published bytes.

## License

AGPL-3.0. See `LICENSE`.
