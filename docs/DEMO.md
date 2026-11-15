# Retriever demonstration

A short terminal run that shows the retrieval layer working on one real issue and one real
repository: it is a demonstration of the pipeline, not a measurement. It calls the library
functions the experiments call, with the settings recorded in `configs/frozen/rq3_contexts.json`
(RRF k 100, 200 candidates, unit cap 1,000 approximate tokens, budget 8,000), and it changes no
stored result.

## What it shows

| Stage | What is printed | Library code |
|---|---|---|
| 1. Parse | files, units by kind, typed edges by type and resolution status | `ril/parsing/build.py` |
| 2. BM25 | top 10 units for the issue text | `ril/retrieval/bm25_index.py` |
| 3. Dense | top 10 from the untrained encoder's scores over the flat exact index | stored scores, see below |
| 4. Fusion | reciprocal rank fusion of the two, then same-file expansion of the top 5; top 10 with the signal of each unit | `ril/evaluation/x2_eval.py`, `s1_graph_role.py` |
| 5. Assembly | budget, units included and skipped, first three block headers, total tokens, comparison with the stored context | `ril/assembly/assemble.py` |
| 6. Gold | the functions the reference patch edits, their rank in each list, whether they are in the context | `ril/data_mining/mapping.py` |

Every stage heading carries its measured wall time.

## How to run it

```
make demo                              # all six stages, about 2 s of compute
make demo DEMO_ARGS="--pause"          # waits for Enter before each stage, for talking over it
make demo DEMO_ARGS="--no-dense"       # fast mode: BM25 only, no dense stage, no fusion
make demo-record                       # writes results/demo/demo_transcript.txt
python scripts/demo_retrieve.py INSTANCE   # another held-out instance (no selection rule applied)
```

Options: `--color auto|always|never` (colour only on stage headings and gold markers),
`--archive FILE` (compare the context byte by byte with the stored file as well as by SHA-256),
`--repo-dir DIR` (a checkout at the base commit instead of the export from the local clone).

Runtime: about 2 s of computation on a laptop; with `--pause` the length is the speaker's, so the
60 to 75 seconds of a recorded run come from the pauses.

## The instance rule

Among the 50 held-out instances (`results/rq3_driver/ids_heldout.txt`), the one whose repository
snapshot has the fewest units, counted from the stored unit records (`results/rq3_units/instances.csv`,
and the instance caches for the four instances that table does not list), ties broken by identifier.
No outcome is looked at. The rule selects `psf__requests-1142` (581 units; the next smallest has
4,405). The script refuses to apply the rule when any of the 50 has no stored record.

## Settings and one departure to know about

- **Dense stage reads stored scores.** The scores are the untrained CodeRankEmbed encoder's
  (revision recorded in the frozen record, 512 tokens), one per unit of the snapshot, produced on the
  cluster. No model is loaded on the machine that runs the demo (the local machine has no GPU and no
  torch, by the project's rule), so the stage is a lookup and reports no device. Encoding the query
  and the units live is not part of this demo.
- **Same-file expansion is shown, not assembled.** The frozen configuration has expansion off, and
  the stored contexts were assembled from the fused list without it. The demo prints the expansion
  in stage 4 and assembles the frozen list in stage 5, so the context can be compared with the
  stored one.
- **Stored-context check.** The SHA-256 of the assembled context is compared with the record in
  `results/rq3_contexts/rq3_contexts_contexts.csv` for the same instance, arm (`rrf`, or `bm25` in
  fast mode) and budget. A difference makes the script exit with a non-zero status.
- **Gold mapping.** Edited units come from the miner's mapping of the reference patch onto
  base-commit units. Lines added after a method's last line are credited to the class that holds
  the method, so the output can list a class beside the method.

## Honesty line

The run ends with: this is one illustrative instance chosen by a fixed rule, not a measurement. The
gold ranks it prints are whatever the stages produce; a single instance says nothing about how the
retriever does on others. Measured results are in `RESULTS.md` and the report.
