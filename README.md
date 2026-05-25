# udud benchmark — the business case

**Bottom line for decision-makers:** in an attack-surface recon pipeline, a
URL deduplicator decides which endpoints your scanners ever look at. Pick the
wrong one and you either (a) silently throw away real endpoints — and the
vulnerabilities behind them are never found — or (b) keep everything at a memory
and time cost that makes large targets impossible to process.

This benchmark measures four off-the-shelf deduplicators against **udud** on the
two things that actually matter to the business: **how much real attack surface
survives** (coverage / risk) and **what it costs to run** (infrastructure spend,
pipeline speed, and whether it scales at all).

**The finding, in one sentence:** udud is the only tool that keeps the attack
surface intact *and* stays cheap and fast enough to run across a whole target
fleet. Every competitor sacrifices one for the other.

---

## Why this is a business problem, not a tooling detail

A recon pipeline collects hundreds of thousands to millions of historical URLs
per target, then deduplicates them into a clean list that scanners and testers
work through. Two failure modes have direct business consequences:

| If the deduplicator… | The business impact is… |
|---|---|
| **deletes real endpoints** (over-aggressive folding) | endpoints are never scanned → vulnerabilities (including IDOR / broken object-level authorization, the #1 API risk) are never found → they ship to production and surface as incidents or bug-bounty payouts |
| **keeps everything / barely dedupes** | the scanner wastes hours on duplicate work, and the tool's memory blows up so you can't run targets in parallel → slower assessments, bigger cloud bills, big targets simply don't finish |

"Fewest output lines" is **not** the goal. The goal is **maximum reduction of
redundant work with zero loss of real attack surface** — and that has to be
proven endpoint by endpoint, not asserted. This repository publishes every
removed URL so the claim can be audited rather than trusted.

---

## Results at a glance

Headline corpus: a real Wayback recon capture of **781,398 URLs** (de-identified
for release). Four competitors plus udud, same machine, same input.

| Tool | Endpoint classes kept | Time to process | Memory footprint | Runs at fleet scale? |
|---|---:|---:|---:|:--:|
| **udud** | **84%** (best of the real deduplicators) | **2.9 s** | **20 MB** | ✅ yes |
| urldedupe | 100% — but by barely deduplicating (near-passthrough, 2.2× more lines) | 9.4 s | 344 MB | ⚠️ memory-bound |
| uro | 63% — deletes ~37% of endpoint classes | 40 s | 36 MB | ⚠️ slow |
| urless | 67% — deletes ~33% of endpoint classes | 172 s | 46 MB | ❌ too slow |
| uddup | n/a | did not finish (>15 min) | n/a | ❌ fails |

"Endpoint classes kept" is the security view: of all the distinct kinds of
endpoint in the corpus, what fraction survived to be scanned. (Counting every
class equally — the macro-average — so losing a rare-but-critical endpoint type
is weighted the same as losing a common one.)

How to read this:

- **udud and urldedupe are the only two that don't throw away attack surface.**
  But urldedupe achieves it by barely deduplicating — its output is **2.2×
  larger** (more redundant scanner work) and it needs **17× the memory** (344 MB
  for one target). Run a dozen targets in parallel and that's the difference
  between fitting on a small instance and needing a server.
- **uro and urless produce a "clean" short list by deleting a third of the
  endpoint classes.** That short list looks tidy in a demo and is a liability in
  production: those deleted endpoints are exactly what never gets scanned.
- **uddup cannot process a large target at all** — it runs out of time on
  anything past ~50,000 URLs.
- **udud is the only tool that is good on every axis at once:** it keeps the most
  surface of any real deduplicator, it's the fastest, it uses the least memory,
  and it scales. udud is deliberately *keep-biased* — when in doubt it retains a
  candidate rather than silently dropping it — so its output is larger than the
  aggressive folders. That is the intended trade: a few redundant lines the
  scanner can absorb, in exchange for never losing a testable endpoint.

This pattern holds on every corpus tested (large Wayback capture, mid-size `gau`
capture, and a vulnerable-by-design test target). Full numbers and the
controlled ground-truth validation are in **[`BENCHMARK.md`](BENCHMARK.md)**.

---

## What this means for you

- **Lower risk of missed findings.** udud preserves the endpoints that
  fold-happy tools delete — including object-ID endpoints (`/order/1001`,
  `/order/1002`, …) where IDOR / broken-object-level-authorization bugs live.
  More real surface reaching the scanner means fewer vulnerabilities slipping
  through to production.
- **Lower infrastructure cost.** A ~20 MB footprint means you can run many
  targets concurrently on commodity hardware instead of provisioning large,
  memory-heavy instances for a single 344 MB-per-target tool.
- **Faster assessments.** Processing that takes seconds instead of minutes
  shortens the recon stage of every engagement; across thousands of targets
  that compounds into hours of analyst and pipeline time saved.
- **It doesn't fall over on big targets.** udud's memory grows with the number
  of *distinct* endpoints it keeps, not with raw input size, so a target with
  millions of historical URLs still completes in seconds — where the
  alternatives either exhaust memory or never finish.

---

## How to trust these numbers (for the technically inclined)

The headline above is deliberately free of jargon. The rigor behind it is not:

- **[`BENCHMARK.md`](BENCHMARK.md)** — the full report: how each tool was timed
  and measured, the controlled corpus with *known* correct answers, results on
  three real corpora, and the honest trade-offs (including where udud chooses
  coverage over a smaller output).
- **[`AUDIT.md`](AUDIT.md)** — a per-line security audit of udud's most
  aggressive (id-folding) mode: every URL it removes is classified by hand to
  confirm it removed redundancy, not surface. The shipping default removes a
  strict subset of those lines, so the finding carries over.
- **[`ANONYMIZATION.md`](ANONYMIZATION.md)** — how the real corpora were
  de-identified before release, and the gate that proves no customer-identifying
  data survived.
- **`raw/`** — the underlying measurement data (CSV) for anyone who wants to
  recompute everything from scratch. `raw/v19_results.csv` is the consolidated
  summary; the rest is the full per-trial detail.

The corpora are frozen and checksummed, and the build and run recipe is in
[`BENCHMARK.md`](BENCHMARK.md), so every number here is reproducible.

---

## Corpora

| Corpus | URLs | What it is |
|---|---:|---|
| Wayback capture (de-identified) | 781,398 | a real large recon target — the scale case |
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
