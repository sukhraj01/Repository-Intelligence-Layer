# Spec: context assembly

**Status: v1, `provisional: D102`** (2026-11-06; `ASSEMBLY_VERSION = "assembly/v1"`). Implements the last
step of `docs/09_architecture.md` "Online retrieval": a ranked list of units becomes the text an agent reads.
Code: `ril/assembly/`. Decision record: D102 and the addendum in `decisions/ADR-014-context-assembly.md`.
It is the same for every retriever, so that what differs between RQ2 arms (and RQ3 runs) is the ranked list and
nothing after it.

## Interface

```python
assemble(candidates: Sequence[Candidate], snapshot: Mapping[str, UnitText],
         config: AssemblyConfig, tok: Tokenizer) -> Assembled   # .context: str, .manifest: Manifest
gold_in_context(manifest, gold_units, gold_files) -> GoldInContext
```

- `Candidate(unit_id, score, stages)`: one entry of the ranked list, best first. `score` and `stages` are
  kept in the manifest and **not used** by the policy (so a score scale never changes the text).
- `UnitText(unit_id, file, start_line, end_line, unit_type, qualified_name, source)`: what the assembler needs
  of a unit; `ril.assembly.snapshot` builds it from a parsed `CodeUnit`. **Class units arrive in header form**
  (`BuildConfig(class_source="header")`): the methods of a class are units of their own, so a class block that
  repeated them would spend the budget twice. This changes only the text shown; the index keeps `full` (D25),
  ids and spans are the same in every form (ADR-013 addendum), and the CodeUnit schema is untouched.
- `Tokenizer`: `name` and `count(text)`, pure and deterministic. The default `ApproxTokenizer`
  (`approx-words-v1`) counts one token per ASCII word, digit or other non-space character plus one per
  newline; it is additive over a newline split. Its ratio to a real tokenizer is measured on 200 sampled units
  (`tests/unit/test_assembly_tokens.py`, slow; `scripts/assembly_run.py ratio`) and recorded in E-ASSEMBLY. **The
  final agent run must pass the agent model's own tokenizer, so that the budget is in the agent's tokens;
  until then budgets are in approximate tokens.**
- `AssemblyConfig(budget, max_unit_tokens=1000)`. No default budget: none is chosen for the agent. The grid
  4,000 / 8,000 / 16,000 / 32,000 is for measurement only. `max_unit_tokens` is provisional (reasoned, not tuned).

## Policy

1. Walk the candidates in rank order (rank = 1-based position in the input list). Skip, with a reason in the
   manifest: `duplicate` (a unit id seen earlier; the first occurrence counts), `unknown_unit` (not in the
   snapshot), `empty_text` (whitespace only).
2. Cut the unit's text at `max_unit_tokens`: whole lines are kept while the text plus a one-line marker
   (`# ... truncated, N more lines`) stays within the cap; if not even the first line fits, it is cut by
   characters. A text within the cap is kept whole. The marker counts toward the cap.
3. A block is the header line (`### <path>:<start>-<end> <unit_type> <qualified_name> (rank <r>)`), a newline and
   the (cut) text. Its cost is its token count plus one separator (`"\n\n"`). If the cost is more than the
   budget left, the unit is skipped (`does_not_fit`, with the tokens it needed) and the walk **continues** with
   the next candidate; no other reordering happens. The walk ends when the list ends.
4. Sort the included blocks by (file, start line, end line, unit id) and join them with the separator. Every file
   then reads top to bottom.
5. Check the finished string: if its token count exceeds the budget (possible only for a tokenizer that is not
   additive), drop the included block of the worst rank, repeatedly, until it fits (`final_check`).

No graph or same-file expansion happens in the default (E-GRAPH-ROLE: typed edges do not beat the same-file
control). Expansion is an option that is off; if it is ever used it is reported separately.

## Output

`Assembled.context` and `Manifest`: budget, unit cap, tokenizer name, configuration hash, `total_tokens` (the
count of the finished string, always at most the budget), `context_sha256`, the included entries in context order
(unit id, rank, file, lines, tokens, truncated, stages) and every skipped candidate (rank, reason, tokens needed).
`Manifest.to_json()` is canonical (sorted keys). The same inputs give the same bytes (test).

`gold_in_context(manifest, gold_units, gold_files)` returns counts: gold units included, gold units included
intact (not cut by the unit cap), gold files with at least one included unit; `no_gold_file` is true when gold
exists and none of its files is in the context. It supports the retrieval-versus-reasoning split of RQ3: an
instance whose gold is absent failed in retrieval or assembly; one whose gold is present and unresolved failed
in reasoning or in the edit. A gold unit that is present but cut is counted present and not intact.

## Measurement

E-ASSEMBLY (`docs/experiments/B.md`): share of gold files and gold units in the context by budget and first
stage, on the dev instances and Verified-six, from the E3 cache and the stored dense scores. Latency: stages
`assemble` and `end_to_end` (BM25 only) under query sets `assembly-<repo>-b<budget>-v1`
(`ril/bench/assembly_measure.py`).

## Limitations (stated, not hidden)

- A unit inside another included unit (a nested definition, a module unit that holds residual code) is not
  deduplicated against it; only the same unit id is.
- The text is the unit's source as parsed: no callee signatures, no imports, no file preamble. The master document's
  description of `assemble()` ("attach callee signatures") is not implemented (DEV-033).
- The approximate tokenizer is a stand-in; budgets in other tokenizers' units differ by the measured ratio.
- Token counting dominates the time (about 90% of `assemble` in a profile; flask, 200 candidates, budget 8,000:
  p50 about 14 ms on an Apple M3). Counts of unit texts do not depend on rank and could be computed once at
  index time; not done.
