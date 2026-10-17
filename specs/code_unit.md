# Spec: CodeUnit

**Status: FROZEN v1** (2026-10-17; `CODEUNIT_SCHEMA_VERSION = "v1"`; ADR-013). The schema below is the
interface between the parser, all three retrieval signals, the training-data builder and the
evaluation harness. After this freeze, changing a field means re-indexing and re-running everything,
so it requires an ADR, a version bump and a re-index plan. Source: `docs/09_architecture.md` ("The
CodeUnit — freeze this in week 1"). One question that does not change the schema (what a class unit's
`source` holds, Q28) is still open and is listed at the end.

## Purpose

The interface between the parser, all three retrieval signals, the training-data builder and the
evaluation harness. Every component reads it. It is the only data type shared across component boundaries.

## Schema (frozen)

```python
@dataclass
class CodeUnit:
    # identity
    id: str                 # "auth.py::TokenManager.verify_jwt"      (D11)
    repo_id: str            # "owner/name", case-folded               (D5)
    language: str           # always "python"

    # location
    file: str               # repo-relative posix path
    start_line: int
    end_line: int

    # structure -> feeds the dense encoder
    unit_type: str          # function | method | class | module      (D6)
    name: str
    qualified_name: str
    signature: str
    docstring: str | None

    # content
    source: str

    # relationships -> feeds the structural signal
    calls: list[str]        # resolved unit ids only                  (D4)
    called_by: list[str]
    tests: list[str]        # filled by the graph build; [] = not computed (D10)
    configs: list[str]      # repo-relative file paths of configuration artifacts

    # metadata
    is_test: bool           # file-level path rule                    (D9)
    loc: int
    last_modified: str      # "YYYY-MM-DDTHH:MM:SSZ" (UTC) or ""      (D8)
```

Code: `ril/parsing/code_unit.py` (type, validation, canonical serialization), `ril/parsing/unit_id.py`
(id builder and converter), `ril/parsing/repo_id.py` (repository identity), `ril/parsing/path_rules.py`
(`is_test`). Tests: `tests/unit/test_code_unit.py`, `test_unit_id.py`, `test_repo_id.py`,
`test_path_rules.py`; `tests/reproducibility/test_code_unit_repro.py` pins the canonical bytes.

## Settled by the master document

- Fields, names and types above; Python only (`language` is always `"python"`).
- In the graph, the function is the smallest node and its `source` is the retrieval document.
- Serialization is **canonical and deterministic** (sorted keys, compact separators, UTF-8 without
  ASCII escaping, list order as given by the producer) so that identical input gives byte-identical
  output. The v0 and v1 byte forms are identical for a unit that is valid under both.
- `CODEUNIT_SCHEMA_VERSION` is recorded with every index.

## Decision log

Engineer decisions of 2026-10-17. D4, D6 and D11 are defaults the engineer may still edit; the code
follows the text below. Each entry gives the decision, the reason, the evidence class (measured /
read in full / reasoned only), the cheapest experiment that could flip it and where it is registered,
and the conditions to revisit. The earlier question numbers (Q13 to Q20) are the numbers used in the
project state before the freeze.

### D4 (was Q13) What the relationship lists hold
- **Decision.** Relations live in a separate typed edge store (the RepoGraph, a separately versioned
  artifact). `calls`, `called_by`, `tests` and `configs` hold resolved CodeUnit ids (`configs`: file
  paths) only, as projections of that store. Ambiguous and unresolved edges stay in the edge store
  with a status and are never dropped silently.
- **Why.** An id is a stable key. Import, inherit, contain, co-change and mention relations cannot
  fit four lists, and a frozen CodeUnit must not block the knowledge graph from evolving.
- **Evidence class.** Reasoned only. Related reading: LARGER keeps typed links in per-file sidecars
  and LocAgent a typed graph (`knowledge/papers/larger-2605.16352.md`,
  `knowledge/papers/locagent-2503.09089.md`); neither measures resolution coverage.
- **Cheapest experiment that could flip it.** In the first parse-and-graph build, count call sites by
  status (resolved in the repository / external / ambiguous / unresolved). If so few resolve that the
  projections are nearly empty, the lists add nothing and could be dropped by a version bump.
  Time-box: inside that build, no extra run.
- **Conditions to revisit.** The edge-recovery numbers; a graph role that needs the projections
  (ADR-003); the edge store schema (ADR-011) being unable to reproduce the lists.

### D5 (was Q14) `repo_id`
- **Decision.** `owner/name`, case-folded. The commit (snapshot identity) lives in the container that
  holds a repository's units and graph, not in the CodeUnit. Renames go to an alias table.
- **Why.** GitHub names are case-insensitive; the disjointness test compares names; one repository
  has many snapshots and a unit's identity must not change with the snapshot.
- **Evidence class.** Measured for the rename part: of 108 repositories looked up on GitHub, 23 now
  have a different name (`data/held_out/rename_cache.json`, `results/logs/d_resolve_renames_2026-10-17.json`).
  The rest is reasoned.
- **Cheapest experiment that could flip it.** None cheap: a commit-qualified id would only be needed
  if one index mixed several snapshots of one repository; the evaluation plan does not (each query
  scores one snapshot). Revisit if an index ever holds two snapshots.
- **Conditions to revisit.** An index that mixes snapshots; the alias table failing to cover a
  rename seen in a pool or benchmark.
- **Code.** `normalize_repo_id` (accepts `owner/name`, `owner__name`, github.com URLs; refuses bare
  truncated folder names and `@commit` suffixes). `CodeUnit.validate` rejects any other form.

### D6 (was Q15) Which definitions are units, and the module unit
- **Decision.** Top-level functions, methods and classes are units; nested definitions fold into
  their parent; decorators are inside the span; lambdas and class attributes are never units. One
  residual unit of `unit_type = "module"` per file holds the lines outside any definition.
- **Why.** 16 of 160 sampled positives overlap no definition, so without a module unit about 10% of
  gold is unreachable at unit level; the module unit is also the file node of the graph.
- **Evidence class.** Measured (the 160-position sample, `results/logs/s3_codeunit_chunk_mapping_2026-10-17.json`:
  111 overlap one function or method, 28 overlap two or more, 5 only a class, 16 no definition; flask
  at the flask-5014 base commit: 513 nested defs, 613 decorated, 16 property-like, 24 lambdas, 114 class
  attributes). Sample of three repositories, so wide uncertainty.
- **Cheapest experiment that could flip it.** Pilot M (chunk-to-unit mapping on all instances of
  three repositories) measures the residual share exactly; pilot E1 runs BM25 at unit level with and
  without the module unit. If the module unit does not change recall and the residual share is small,
  drop it by a version bump. Time-box: those pilots.
- **Conditions to revisit.** The pilots; a granularity decision (ADR-004) that makes units larger or
  smaller.
- **Reading of the decision made in code (confirm, Q29).** The module unit has `name` and
  `qualified_name` `<module>` (not a Python identifier, so it never collides with a definition), id
  `path::<module>`, empty `signature`, `docstring` = the module docstring or `None`, `start_line` 1
  and `end_line` the last line of the file, `source` = the residual lines in order, `loc` = the number
  of non-blank residual lines. `validate` requires `unit_type == "module"` exactly when
  `qualified_name == "<module>"`.
- **Open inside D6 (Q28).** Whether a class unit's `source` is the full class text or the header
  only (the `Flask` class is 2,124 lines and its methods are units of their own). The schema does not
  change either way; the parser behind a flag `provisional: ADR-013` until the engineer decides.

### D7 (was Q16) Link to CORE-Bench chunks
- **Decision.** The chunk-to-unit link is a derived mapping built by the evaluation loader at the
  instance base commit, not a CodeUnit field.
- **Why.** Chunk definitions differ even inside one paper (mean chunk length 1,004.9 characters at
  evaluation against 2,188.4 in the training set), and the released corpus rows carry only `_id` and
  `text`; no file with paths or line spans exists.
- **Evidence class.** Read in full (`knowledge/papers/core-bench-2606.11864.md`: Tables 1 and 9;
  claim C2, no metadata file on the dataset repository) and measured (the data audit).
- **Cheapest experiment that could flip it.** Pilot M's match rate: locate every positive chunk in the
  base-commit files by exact text. If a large share does not match, the mapping is unusable and chunk
  level evaluation stays primary (ADR-004). Time-box: pilot M.
- **Conditions to revisit.** A released chunk metadata file; the match rate.

### D8 (was Q17) `last_modified`
- **Decision.** UTC ISO-8601 time of the last commit that touched the file, restricted to commits at
  or before the snapshot commit, or `""`. Never the file system time.
- **Why.** File system times break byte-identity and mean nothing in a checkout; restricting to the
  snapshot keeps the field free of the future, which matters for any recency use.
- **Evidence class.** Reasoned only. Related reading: GREPO's temporal anchors
  (`knowledge/papers/grepo-2602.13921.md`).
- **Cheapest experiment that could flip it.** Pilot E5 (a recency prior on BM25) measures what the
  field buys; the cost of the per-file history lookup is measured in the first parse build. If it buys
  nothing and costs much, set it to `""` by default. Time-box: those pilots.
- **Conditions to revisit.** E5; the lookup cost on the largest repository.
- **Format fixed in code (confirm, Q29).** `YYYY-MM-DDTHH:MM:SSZ` or `""`; `validate` rejects other
  spellings so the field compares and serializes one way.

### D9 (was Q18) `is_test`
- **Decision.** A file-level path rule: a `tests` or `test` directory component, or a file name
  `test_*.py`, `*_test.py` or `conftest.py`. `examples/` and `docs/` are not tests.
- **Why.** Cheap, deterministic, needs no parsing and no framework markers.
- **Evidence class.** Measured against pytest collection (`results/logs/d_is_test_rule_2026-10-17.json`,
  job 25468): on flask, requests and seaborn at their cached default commits, every file pytest
  collects tests from or fails to import (21, 9, 35) is flagged by the rule (0 missed). The rule also
  flags files pytest does not collect (27, 6 and 5): `conftest.py`, package `__init__.py` under tests,
  helper modules, tests under `examples/`, and modules that collect no item. That is by design (the
  field labels test code, not test modules). Three repositories only; some test dependencies were not
  installed (collection errors: 3, 0, 1).
- **Cheapest experiment that could flip it.** More repositories through the same script
  (`scripts/validate_is_test_rule.py`); a miss on any repository that matters (a collected module the
  rule does not flag) would change the rule. Time-box: one job per repository.
- **Conditions to revisit.** A repository whose tests live under another name (`testing/`,
  `check/`); pytest `python_files` overrides.
- **Code.** `ril.parsing.path_rules.is_test_path`.

### D10 (was Q19) `tests`
- **Decision.** Filled by the graph build, not at parse time; `[]` means "not computed", never
  "untested".
- **Why.** The link needs call resolution and naming heuristics that belong to the graph.
- **Evidence class.** Reasoned only. LARGER builds tested-by links with a fixed confidence and
  reports no ablation (`knowledge/papers/larger-2605.16352.md`, claim G1).
- **Cheapest experiment that could flip it.** The exploratory `tests` edges of the first graph build
  (sampled precision, n >= 50). If a name-convention rule is almost always right and cheap, fill it at
  parse time by a version bump. Time-box: that build.
- **Conditions to revisit.** The sampled precision; ADR-003.

### D11 (was Q20) `id`
- **Decision.** `id = <repo-relative posix path>::<Qual.name>`. On a collision the second and later
  occurrences get `#2`, `#3` (the first is unsuffixed; an ordinal in source order, not a line number,
  so ids survive edits above them). A deterministic converter maps to and from the pool form
  `path/Class/function`.
- **Why.** `::` follows the master example; a path-qualified name is stable across commits; an
  ordinal suffix is stable under edits where a line number is not.
- **Evidence class.** Measured for the converter: all 16,141 function ids of 70 sampled pool
  instances round-trip (`results/logs/d_content_overlap_audit_2026-10-17.json`); the id rule itself is
  reasoned. The collision rate is not yet measured.
- **Cheapest experiment that could flip it.** The first parse build counts same-name collisions per
  file on flask, requests and django. A high rate (many conditional redefinitions) would make `#n`
  ids unstable under insertions between duplicates and favour another scheme. Time-box: that build.
- **Conditions to revisit.** The collision rate; a pool whose ids do not follow `path/Class/function`.
- **Code.** `ril.parsing.unit_id`: `build_id`, `parse_id`, `assign_ids`, `id_to_pool`, `pool_to_id`.
  The pool form carries no ordinal, so `id_to_pool` drops it and `pool_to_id` returns the first
  occurrence unless an ordinal is given.

## Validation (code)

`CodeUnit.validate` rejects: empty `id` or an `id` that does not parse or does not agree with `file`
and `qualified_name`; `repo_id` not in the D5 form; `language` other than `python`; `unit_type` outside
{function, method, class, module}; `unit_type` and `<module>` disagreeing; `end_line < start_line`;
`loc < 0`; a `last_modified` that is neither empty nor `YYYY-MM-DDTHH:MM:SSZ`.

## Acceptance criteria (met)

- [x] `ril/parsing/code_unit.py` defines the dataclass exactly as above, with type hints and a docstring citing this spec.
- [x] Round-trip: `from_dict(to_dict(u)) == u` and canonical JSON is byte-stable across runs (pinned by a golden test).
- [x] Validation rejects the cases above; unit tests cover them plus empty docstring vs `None` and unicode source.
- [x] The eight questions are closed (D4 to D11) with reasons, evidence class, flip experiment and conditions.
- [x] `docs/ARCHITECTURE.md` (parsing, Interface) updated.

## Change control

A change to a field, a type, the enum or the meaning of a field: an ADR, `CODEUNIT_SCHEMA_VERSION`
bumped, and a re-index plan. Edits to D4, D6 or D11 by the engineer count as such a change once an
index exists.

## Open after the freeze

- **Q28** Class unit `source`: full class text or header only.
- **Q29** Confirm the readings recorded under D6 (module unit fields) and D8 (timestamp form).
