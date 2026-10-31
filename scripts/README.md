# scripts/

**Thin command-line wrappers. No logic.** Logic lives in `ril/` where it is unit-tested; a script
parses arguments (always `--seed`), calls into `ril/`, and writes outputs. `scripts/` and
`ril/bench/` may call everything; nothing calls back into them.

- `scripts/ada/` — Slurm job scripts and helpers for the Ada cluster (see its README).
- No CLI entry point / console script is built until ADR-010 (usable by others?) is decided.
- `scripts/check_docs.py` — lists dangling links, paths and ADR / DEV / Q numbers in the tracked
  documents (`ril/util/doc_check.py`); run `python -I scripts/check_docs.py` after editing any
  document. It is also a unit test (`tests/unit/test_doc_check.py`).
- `scripts/review_flags.py` — scans the added lines of a branch for shortcuts and traces ledger numbers
  to files under `results/` (`ril/util/review_flags.py`, rules and limits in `docs/REVIEW.md`); run it as
  `make review-flags BASE=main`. Exit status 1 on a blocking finding. Tests: `tests/unit/test_review_flags.py`.
