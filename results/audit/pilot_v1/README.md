# Pilot label audit, sample record

`sample_meta.json` records the seed, the hashes of the rank inputs, the stratum sizes, the truncation rules and the SHA-256 of the three sheets and of the key file. It is the record of what was drawn.

The sheets (`reader_overlap.csv`, `reader_1.csv`, `reader_2.csv`, about 3.0 MB together) and the key file are not tracked. The sheets quote public issue text and code verbatim, including tracebacks with other people's home paths and product names that the repository's provenance checks reject, and the key must stay away from the readers. They are kept under `data/review/label_audit_pilot_v1/` (untracked) and are rebuilt by `scripts/ada/label_audit.sbatch` from the same seed; the hashes in `sample_meta.json` say whether a rebuild is identical (the network fetch of the diffs is the one external input).

Instructions for the readers: `docs/LABEL_AUDIT.md`. Scorer: `scripts/label_audit_score.py`. Entry: E-LABEL-AUDIT-SHEET in `docs/experiments/B.md`.
