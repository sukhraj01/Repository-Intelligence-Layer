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

Final report: `reports/final/final_report.tex` compiles with `tectonic final_report.tex` (the PDF is not committed). Tables in
`reports/final/generated/` are written by `python scripts/report_tables.py` from the stored results; do not edit them by hand
(`tests/unit/test_report_tables.py` rebuilds them and compares). A caption states the evidence class, n and the experiment entry.
Slots still empty are `\todo{...}` naming the entry that fills them; `docs/REPORT_GAPS.md` ranks the missing claims.
