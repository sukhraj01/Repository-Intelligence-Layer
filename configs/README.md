# configs/

Run configurations. The split is deliberate and comes straight from the design: **a good experiment
freezes the retrieval stack so only one variable moves; a good product tunes it however it takes.**
Both exist; they must never be confused.

| Directory | What | Mutable? |
|---|---|---|
| `frozen/` | The retrieval-stack configuration held identical across all RQ2 arms | **Immutable after the freeze** (before week 6). Changing it invalidates the RQ2 comparison. |
| `demo/` | The tuned configuration for the portfolio/product demo | Free to change |
| `experiments/` | One YAML per registered experiment (`docs/EXPERIMENTS.md`) | Immutable once a run used it (new run ⇒ new file) |

Rules:

- Every run records the **config hash**; the hash and the seed identify the result.
- No magic constants in code: values live in `ril/config/` defaults or here.
- Provisional settings carry a `provisional: ADR-0NN` field and may **never** appear in `frozen/`.
