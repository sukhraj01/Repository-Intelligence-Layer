# Spec: CodeUnit

**Status: DRAFT v0 — not frozen.** Freezing needs the engineer's sign-off (week 1). After the freeze,
changing a field means re-indexing and re-running everything, so it requires an ADR, a version bump
and a re-index plan. Source: `docs/09_architecture.md` ("The CodeUnit — freeze this in week 1").

## Purpose

The interface between the parser, all three retrieval signals, the training-data builder and the
evaluation harness. Every component reads it. It is the only data type shared across component boundaries.

## Schema (as given in the master doc — implement exactly)

```python
@dataclass
class CodeUnit:
    # identity
    id: str                 # "auth.py::TokenManager.verify_jwt"
    repo_id: str
    language: str

    # location
    file: str
    start_line: int
    end_line: int

    # structure -> feeds the dense encoder
    unit_type: str          # function | method | class
    name: str
    qualified_name: str
    signature: str
    docstring: str | None

    # content
    source: str

    # relationships -> feeds the structural signal
    calls: list[str]
    called_by: list[str]
    tests: list[str]
    configs: list[str]

    # metadata
    is_test: bool
    loc: int
    last_modified: str
```

## Settled (implement as stated)

- Fields, names and types above; `unit_type ∈ {function, method, class}`; Python only (`language` is always `"python"` for now).
- In the graph, the function is the smallest node and its `source` is the retrieval document.
- Serialization is **canonical and deterministic** (stable key order, stable list order) so that identical input ⇒ byte-identical output.
- A module-level constant `CODEUNIT_SCHEMA_VERSION` exists and is recorded with every index.

## Open design questions — the freeze must answer these

Record the options and a proposal for each; the engineer closes each.

1. Do `calls`, `called_by`, `tests`, `configs` hold **CodeUnit ids**, qualified names, or file paths? (`configs` entries are files, not functions.)
2. What is `repo_id` — `owner/name`, `owner/name@commit`, or something else? It must support repo-level disjointness checks and match CORE-Bench's repository naming.
3. How are nested functions, lambdas, properties, decorated callables, and class-level attributes represented?
4. Relationship to CORE-Bench chunks (ADR-004): is a chunk id a field, a derived mapping, or external?
5. Source of `last_modified` (git commit time vs mtime vs absent for benchmark snapshots).
6. The rule for `is_test` (path convention, name convention, framework markers).
7. Is `tests` populated at parse time or by the graph extension (weeks 7–10)? Empty list until then?
8. The exact `id` format. The master's CodeUnit example is `auth.py::TokenManager.verify_jwt` (double colon), while the LocAgent graph schema it adopts uses `src/utils.py:MathUtils.calculate_sum` (single colon, fully qualified name). Pick one, and if both are kept, define the mapping.

## Acceptance criteria

- [ ] `ril/parsing/code_unit.py` defines the dataclass exactly as above, with type hints and a docstring citing this spec.
- [ ] Round-trip: `from_dict(to_dict(u)) == u` and canonical JSON is byte-stable across runs.
- [ ] Validation rejects: `end_line < start_line`, unknown `unit_type`, empty `id`, negative `loc`.
- [ ] Unit tests cover the above plus edge cases (empty docstring vs `None`, unicode source).
- [ ] The eight questions above are written up, each with options and a proposal.
- [ ] `docs/ARCHITECTURE.md` (parsing → Interface) updated.

## Freeze procedure (engineer)

When the eight questions are closed: set status here to **FROZEN vN**, bump `CODEUNIT_SCHEMA_VERSION`,
record an ADR ("CodeUnit vN frozen"), and note it in `PROJECT_STATE.md`. From then on, schema
changes follow the change-control rule in the first paragraph.
