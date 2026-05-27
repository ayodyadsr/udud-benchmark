<!-- staged section, integrated into BENCHMARK.md during regeneration.
     numeric drift figures marked {{...}} are filled from the de-identified
     run's summary/quality output, not carried over from the original. -->

## Anonymization

### Why the corpus is transformed

The largest corpus in this benchmark is a real `waybackurls` capture of a
confidential commercial target. The benchmark needs a corpus with real
URL structure, real scanner noise, real session tokens and real
parameter shapes, because that structure is exactly what a deduplicator
is judged on. A synthetic corpus would not exercise the gates the tools
disagree on. Publishing the raw capture would disclose the target's host
inventory and route structure, so the corpus is de-identified before
release and only the de-identified bytes are published, measured and
audited.

### What the transform does

`harness/anonymize.py` applies a fixed deterministic monoalphabetic
letter permutation to the identity-bearing letters of each URL. The
permutation is case-preserving and letter/digit-class preserving. It is
applied to the letters of host labels, path segments, userinfo, query
values and the fragment. The confidential registrable domain is remapped
to the RFC 2606 reserved domain `example.com`.

It deliberately keeps the following verbatim, because every structural
decision the five tools make is taken on these and the experiment is
only the same experiment if they are byte-identical between the original
and the published corpus:

- the scheme, the port, every separator, every digit, every
  percent-escape `%xx`
- recognised public-suffix labels at any position (the embedded-domain
  and re-rooted-spam gates inspect interior labels)
- recognised file extensions and well-known structural filename stems
  (`robots`, `sitemap`, `index`, ...)
- the canonical recon parameter vocabulary (open-redirect / SSRF / LFI /
  pagination / locale / session / tracking keys), so the
  open-redirect/SSRF/LFI narrative stays concretely demonstrable on the
  published corpus
- the matrix-parameter key names (`;jsessionid=`, `;sid=`, ...), with
  only the session value ciphered, so the authenticated-endpoint gate
  sees a byte-identical token
- the four url-structural value tokens (`http`, `https`, `ftp`, `www`)
  inside query values, so redirect-target and SSRF value detection stays
  truthful

Every kept set is generic vocabulary that carries no target identity. A
parameter name, host label or path token that is not in one of these
generic sets (a product or brand custom token) is ciphered.

### Why the published numbers are a fresh measurement, not a relabel

The transform is near-invariant for the decisions a purely structural
deduplicator makes: same byte-classes, same lengths, same separators,
same public-suffix and extension structure, same query key set. `xcull`
and `urldedupe` are largely structural, so their per-cell output is
close to invariant under it. `urldedupe` is the near-invariance anchor
(it is close to a verbatim passthrough); its output count moves by only
{{urldedupe_drift_pct}} between the original and de-identified corpora,
the residual coming from the whitelist breaking perfect bijectivity at
the token level.

But `xcull`'s noise filters and the keyword blacklists in `uro`, `urless`
and `uddup` key on literal English tokens. De-identification
legitimately changes what those filters match. For that reason the
published artifact is not the original numbers relabelled. The entire
benchmark was re-run from scratch on the de-identified corpus under the
same pinned clock and the same N. Every figure in this document is
measured on exactly the bytes that are published, and every per-line
audit listing in `AUDIT.md` is regenerated against those same bytes.

### Confidentiality argument

The claim is that no original identity-bearing token survives the
transform. It rests on three checks, all reproducible with
`harness/verify_anon.py`:

1. The letter map is a bijection over the alphabet with no fixed point.
   Every letter, upper and lower, maps to a different letter, so any
   alphabetic run routed through the cipher cannot equal its input.
2. Every verbatim-kept set is audited and contains no identity-bearing
   token; it is public-suffix, file-extension, structural-stem, scheme,
   generic-recon-parameter and matrix-key vocabulary only.
3. A decisive per-line differential over every corpus: a token is a real
   survival only if it is a maximal alphabetic token in both an input
   line and its corresponding output line. `anonymize.py` is strictly
   line-wise, so the lines align. This check returns zero across all
   corpora. A scrambled run that merely happens to spell a short brand
   substring was a different token in the input line and is correctly
   not counted, which is unavoidable noise of any monoalphabetic cipher
   over a corpus this size and is not a leak.

`verify_anon.py` exits non-zero if any of the three fails, and it is run
as a release gate before the corpus is published.

### Stated limitations

The relabelling is not cryptographic. The permutation key is fixed in
source as a determinism and readability device, not as a confidentiality
control; confidentiality rests on the destruction of every
identity-bearing token, not on secrecy of the key. URL path and route
structure is retained by design, because a structural deduplicator
benchmark is meaningless without it; the published corpus therefore
still exposes the route shapes of the original capture, with all host,
path and value identity removed. The reverse map is not published. The
de-identified datasets are frozen with their own sha256 in
`raw/datasets.csv` and are the only corpus the published numbers refer
to.
