# configs/experiments/

One YAML per registered experiment, named by its ID in `docs/EXPERIMENTS.md`
(e.g. `E-RQ2-FILTER.yaml`). Each file:

- declares which `frozen/` config it extends and only overrides what the experiment varies,
- names the seed(s), the dataset split, and the hardware class intended,
- is hashed; the hash is stored in the result directory and in `RESULTS.md`.

Immutable once a run has used it — a changed experiment is a new file and a new registry row.
