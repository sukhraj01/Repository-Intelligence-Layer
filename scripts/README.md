# scripts/

**Thin command-line wrappers. No logic.** Logic lives in `ril/` where it is unit-tested; a script
parses arguments (always `--seed`), calls into `ril/`, and writes outputs. `scripts/` and
`ril/bench/` may call everything; nothing calls back into them.

- `scripts/ada/` — Slurm job scripts and helpers for the Ada cluster (see its README).
- No CLI entry point / console script is built until ADR-010 (usable by others?) is decided.
