# knowledge/ — the project's engineering wiki

Research, notes and references accumulate here so knowledge is not rediscovered. It is **not**
loaded by default; read a file here only when the task needs it.

```
knowledge/
├── papers/         reading-status table + one note per paper once read (papers/<slug>.md)
└── datasets/       what each dataset is, how we got it, provenance
```

Conventions:

- A paper note records: what it established, what it did *not* establish, numbers we may quote
  (with page/table), and whether it was **read in full**. Never quote exact figures from a paper not
  read in full.
- Dataset notes link to `data/raw/<dataset>/provenance.json` rather than duplicating hashes.
