# specs/ — acceptance contracts

A spec says **what "done" means** for a deliverable and which parts are settled vs still open for
the engineer/team to decide. Specs are short and testable. The design rationale lives in `docs/`; the
spec is what the work is held to.

| Spec | Deliverable |
|---|---|
| `code_unit.md` | The CodeUnit schema — the one type every component reads |
| `held_out_repos.md` | Held-out repository list + disjointness filter + leakage test |
| `latency_harness.md` | Per-commit latency/throughput harness and its CSV contract |
| `repo_graph.md` | The RepoGraph typed edge store: DRAFT v0, options only, own version constant |
| `parse_one_repo.md` | Parse one real repo end to end; ten CodeUnits; edge-recovery % |

Specs to add when their week arrives (do not write them early): a supervision-arms spec (week 6),
an RQ3 protocol (week 10) and a graph-extension spec (week 7).

Each spec has the same sections: **Purpose · Inputs · Outputs · Settled · Open design questions ·
Acceptance criteria · Tests.**
