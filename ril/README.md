# ril/ — the package

Python 3.11, type-hinted, `mypy --strict`. `__init__.py` files and tooling arrive in the
week-1 bootstrap; until then each subdirectory holds only a README stating its contract.
Design: `docs/ARCHITECTURE.md` (live) and `docs/09_architecture.md` (master-derived).

```
ril/
├── config/       parameters, paths                      depends on: nothing
├── parsing/      repository parser, CodeUnit, call graph  depends on: config
├── retrieval/    BM25, dense encoder, hybrid, ranking     depends on: parsing, config
├── training/     loss, training loop, data loader, supervision arms   depends on: parsing, config
├── evaluation/   metrics, CORE-Bench loaders, agent integration       depends on: retrieval, parsing, config
├── bench/        latency harness, stage profiling         may call everything
└── analysis/     error analysis, visualization            reads results/ only
```

Rules: `CodeUnit` is the only type shared across component boundaries; no `print`;
every entry point takes `--seed`; docstrings cite the doc/ADR they implement; no magic constants.
