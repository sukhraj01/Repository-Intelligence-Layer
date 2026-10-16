# ril/training/

**Planned files:** `contrastive_loss.py`, `training.py`, `data_loader.py`, `supervision.py`.
Design: `docs/08_experimental_design.md`, `docs/04_data_and_ground_truth.md`.

- Multi-positive InfoNCE (τ=0.05) with repository-local hard negatives; batch size = in-batch negative count.
- `supervision.py` isolates the four arms (RAW, FILTER, WEIGHT, CURRICULUM) — the **only** place the
  experiment's independent variable lives.
- Quality signal = SweRank K-rank from a **separately pretrained** encoder, never the model being trained.
- Matched **optimizer updates** across arms; record GPU-hours, unique examples seen, effective epochs.
- ≥3 seeds per arm.
- The data loader must pass the repository-level disjointness check (`tests/leakage/`).

Depends on: `parsing/`, `config/` (imports the encoder *class* from `retrieval/`, never trained weights, for K-rank).
