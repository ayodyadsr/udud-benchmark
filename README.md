# udud-benchmark

A reproducible, paper-grade benchmark of single-pass URL structural
deduplication. System under test:
[**udud**](https://github.com/ayodyadsr/udud), a from-scratch C URL
deduplicator. Baselines: `uro`, `urldedupe`, `urless`, `uddup`.

Three real-world corpora, frozen and checksummed:

| Corpus | Lines | Bytes |
|---|---|---|
| `D_example_wb.full` (Wayback, de-identified) | 781,398 | 134,533,990 |
| `D_example_gau.full` (gau, de-identified) | 44,943 | 5,291,538 |
| `D_vulnweb.full` (vulnweb test targets) | 15,185 | 1,210,645 |

## Start here

- [`BENCHMARK.md`](BENCHMARK.md): the full report. Methodology, pinned
  clock protocol, results, per-class retention, threats to validity,
  reproducibility recipe.
- [`AUDIT.md`](AUDIT.md): per-line security audit. Every URL udud removes
  that the metric counts against it, classified by hand.
- [`ANONYMIZATION.md`](ANONYMIZATION.md): the cipher, the verbatim-kept
  vocabulary, the three-check residue gate, the rationale for re-running
  the benchmark on de-identified bytes rather than relabelling the
  originals.

## Headline (D_example_wb.full, 781,398 lines, 134.5 MB)

| Tool | Output | Wall (s) 95% CI | Peak RSS | Retention |
|---|---|---|---|---|
| **udud v14** | 125,837 | **9.364 +/- 0.296** | **18.4 MB** | js 99.25%, matrix folded with auth endpoint kept |
| urldedupe 1.0.4 | 293,420 | 9.412 +/- 0.062 | 335.9 MB | passthrough, near-verbatim |
| uro 1.0.2 | 78,470 | 39.763 +/- 0.184 | 35.1 MB | js 11.4%, matrix 0% |
| urless v2.7 | 74,737 | 172.161 +/- 1.024 | 45.3 MB | js 11.5%, matrix 0% |
| uddup 0.9.3 | DNF | > 300 s | n/a | n/a |

udud is the only tool that is simultaneously the fastest (modulo
urldedupe, which uses 18 times the memory), the lowest RAM, and lossless
on real attack surface by complete per-line audit. The full per-class
table is in `BENCHMARK.md` Section 7.1; the per-line classification is in
`AUDIT.md`.

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
   +- environment.txt     pinned-clock environment manifest
   +- datasets.csv        sha256 / line count / byte count
   +- trials.csv          every per-trial timing
   +- summary.{csv,txt}   N=10 means with 95% CI and CoV
   +- quality.{csv,txt}   per-class canonical retention
   +- coverage.csv        endpoint coverage (descriptive)
   +- origbytes.csv       verbatim-bytes ratio
   +- outputs/            each tool's output on each corpus
   +- audit/              every removed line, per tool, per class
   +- v13/                archived v13 outputs and audit (lineage)
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
