# Tool invocations

Every tool is run in its documented default mode, reading a file and
writing a file as a single process (so the getrusage maxrss measured by
runstat is the tool itself, not a `cat` pipeline). No behaviour-changing
flags are passed to any competitor.

| tool | version | command | notes |
|---|---|---|---|
| xcull | v12 (this repo) | `xcull < IN > OUT` | SUT; gcc -O3 -march=native -flto |
| uro | 1.0.2 (pip) | `uro -i IN > OUT` | `-i` and stdin produce byte-identical output (verified) |
| urldedupe | 1.0.4 | `urldedupe < IN > OUT` | stdin filter |
| urless | 2.7 (pip) | `urless -nb < IN > OUT` | see caveat below |
| uddup | 0.9.3 @ c3e19ed | `uddup -u IN -o OUT` | no stdin support; file in/out only |

## urless caveat (important for reproducibility)

In urless 2.7 the documented `-i FILE` input flag is **non-functional**:
the tool always reads **stdin**, and blocks indefinitely when stdin is
an open pipe with no EOF. `urless -i FILE -o OUT </dev/null` therefore
produces an empty file (it reads the empty stdin, not FILE). The only
correct invocation is the pipe form `urless < IN > OUT`. `-nb`
(no-banner) is cosmetic only and keeps the ANSI banner out of the timed
path and the output; it does not change which URLs are kept. `-dp`
(disregard-params) **is** behaviour-changing and is deliberately **not**
used.

## uddup measurement asymmetry (declared)

uddup is O(n^2) and buffers the whole input. It contributes no point to
the linear-time head-to-head; its scientific role is to show the
asymptotic blow-up. Running N=10 tight-CI trials on it is wasted, and
above ~50k lines a single run already exceeds the 300 s cap. It is
therefore measured with **N=3** on inputs <= 50,000 lines plus the two
secondary URL sets (enough to establish the quadratic curve), and marked
**DNF** (300 s wall cap) above that. Every tool that competes on the
linear-time head-to-head receives the full N=10 + 95% CI treatment.

## Per-run protocol

For each (dataset, tool) cell: prime the page cache (`cat dataset
>/dev/null`), one untimed warm-up run, then N timed trials. Each timed
run is `taskset -c 2 timeout -k 10 300 runstat <tool> -- sh -c '<cmd>'`.
`timeout` wraps `runstat` (not the reverse) so a killed run cannot make
runstat report `timeout`'s RSS instead of the tool's; dash exec-optimises
`sh -c '<single cmd>'` so the measured child is the tool. Output line
count and sha256 are recorded every trial; a cell is deterministic iff
all its trials produced an identical sha256.
