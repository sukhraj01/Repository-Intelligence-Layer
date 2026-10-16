# tests/

Testing is design, not an afterthought — tests are written with the code.

| Directory | What | Run by |
|---|---|---|
| `unit/` | one function at a time: validation, correctness, same-input-same-output | `make test` |
| `integration/` | components together: parser → index → retriever; loader → metric | `make test-all` |
| `reproducibility/` | same code + same seed ⇒ same result; byte-identical where claimed (e.g. `assemble`) | `make test-all` |
| `leakage/` | **must always pass** — see below | `make test-all`, and in the commit hook once data exists |

## Leakage tests (critical)

- (a) training-pool repositories ∩ {CORE-Bench L2/L3, SWE-bench Verified} repositories = ∅
- (b) no patch / gold text in any training query
- (c) the quality-signal encoder is not the encoder being trained
- (d) no evaluation data reachable from a training code path

`tests/fixtures/` holds small tracked fixtures (exempted from the ignored extensions in `.gitignore`).
