# reports/

LaTeX sources for the written deliverables (compile with `tectonic`, as in the engineer's earlier
projects). Build products are gitignored; sources are tracked.

```
reports/
├── proposal/   the proposal (state the contribution as an empirical study, not a discovery)
└── final/      the final report and presentation
```

Claim discipline: RQ2 says *matched optimization budgets*; use the approved
sentence from `docs/02_research_questions.md`; never "first systematic study" / "no one has studied" /
"novel approach to code retrieval". Raise threats to validity yourself (`docs/08_experimental_design.md`).
Every figure traces to `results/` and `RESULTS.md`; paper-reported numbers are labelled as such.
Check the report's page count against the venue/rubric with a script (e.g. `pypdf`) — do not eyeball it.
