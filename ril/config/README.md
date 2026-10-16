# ril/config/

**Planned files:** `parameters.py`, `paths.py`. Depends on nothing internal.

- `paths.py` — all paths resolved from the repository root; no hard-coded absolute paths; separate
  roots for local vs Ada data.
- `parameters.py` — typed defaults (dataclasses) for the values in `docs/09_architecture.md` "Defaults
  to start from". Loading a YAML from `configs/` yields a frozen, hashable config.

Invariant: the config hash is recorded with every run. `configs/frozen/` is immutable after the freeze.
