read: full — 38 pages incl. appendices, PDF v3, pdftotext -layout (poppler), 2026-11-08

# OpenHands — Wang, Li, Song, Xu, Tang, Zhuge, et al., Neubig (arXiv 2407.16741v3, 18 Apr 2025; ICLR 2025)

Source: https://arxiv.org/abs/2407.16741, PDF https://arxiv.org/pdf/2407.16741v3 (v3 is the latest version; v1 and v2 have 39 pages and
were not used), retrieved 2026-11-08. The PDF has 38 pages (body pp.1-10, references pp.11-16, appendix A-K pp.17-38); the
extracted text has 38 pages and no blank page (`scripts/check_paper_note.py`). Every page was read, including the
appendix prompts and the list of browser and file skills (the browser-action docstrings of Sec. J, pp.26-34, were read as
API listings; they carry no claim). Figures 1, 2, 4 and 5 are architecture or interface pictures with no numbers.

## What it established

- A platform, not one agent: an event stream of actions and observations, a Docker sandbox with a bash shell, an IPython
  server and a Chromium browser behind a REST action API, an `AgentSkills` library of Python tools (file viewing and
  editing adapted from an earlier agent interface and another tool, lexical search), agent delegation, and a harness for
  15 benchmarks (Sec. 2-4, pp.3-10).
- The default generalist agent (CodeAct) acts by writing bash, Python or browser commands; on SWE-bench Lite with a
  closed-source model it resolves 22.0% and with another 26.0% (Table 4, p.8).
- Integration tests with the LLM mocked by stored prompt-response pairs, so agent changes can be tested without model calls
  (Sec. E, p.19).

## What it did not establish

- No retrieval component and no retrieval comparison: the agent finds code with bash and the lexical `search_dir`,
  `search_file` and `find_file` skills (Sec. 2.3, p.5; Sec. I, pp.24-25). Nothing swaps or ablates a retriever.
- No decoding settings, seeds, maximum number of turns, retry rule or run count for any software-engineering row: the words
  temperature, seed, variance and standard deviation do not occur in the 38 pages. Every cell is one number.
- No interval or test; no per-instance outcome table; no repository-level breakdown.
- No contamination analysis for SWE-bench Lite; the agent's tool set is not restricted to the repository (it has a browser).
- Costs are single averages with no definition of which instances they average over (Table 4, p.8).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| SWE-bench Lite (300, no hint text), CodeAct v1.8: small closed-source model / mid / strong, resolved % | 7.0; 22.0; 26.0 | Table 4, p.8 |
| Same rows, average dollars per instance | 0.01; 1.72; 1.10 | Table 4, p.8 |
| Same small model in the overview table | 6.3 | Table 3, p.7 |
| Copied Lite rows: SWE-agent / AutoCodeRover / Aider / Moatless / Agentless (closed-source model) | 18.0; 19.0; 26.3; 26.7; 27.3 | Table 3, p.7 |
| Cost of the whole test set at a conservative 3 dollars per instance | 6.9k | Sec. 4.2, footnote 2, p.7 |
| Cost of one Lite evaluation with the mid model | 600 USD | Sec. E, footnote 4, p.19 |
| Benchmarks integrated | 15 | Sec. 4, p.6 |
| HumanEvalFix Python, 0-shot, CodeAct v1.5 / SWE-agent 1-shot | 79.3; 87.7 | Table 4, p.8; Sec. 4.2.1, p.7 |
| Lite instances; HumanEvalFix instances | 300; 164 | Table 4, p.8 |

## Method details we need

- **State and actions (Sec. 2.1, pp.3-4).** The state holds the event stream and the accumulated cost of LLM calls;
  `CmdRunAction` and `IPythonRunCellAction` run arbitrary bash and Python in the sandbox, `BrowseInteractiveAction` drives
  a browser; an agent is a class with a `step(state)` function (Figure 3, p.4).
- **Skills (Sec. 2.3, p.5; Sec. I, pp.23-26).** `open_file`, `goto_line`, `scroll_up`, `scroll_down`, `create_file`,
  `edit_file(start, end, content)`, `search_dir`, `search_file`, `find_file` and document parsers; an inclusion rule: a skill
  is added only when writing code directly is not readily achievable for the model or it calls an external model.
- **Runtime (Sec. 2.2, pp.4-5; Sec. F, pp.20-22).** One container per task session built from any user image with a
  hash-tagged and a generic tag; actions and observations travel over a REST API.
- **Evaluation (Sec. 4.2, p.7).** Software-engineering results are reported "without using hint text", on Lite by
  default "for cost-saving consideration", with one number per model.
- **Delegation (Sec. 2.4, p.5).** A generalist agent can hand a web task to a browsing agent.

## Implications for this project's scaffold (ADR-007, E-POWER, the claim)

Evidence class: read in full for what the paper does; inference for what it means here.

- **Why D113 rejects it holds on the paper's own evidence.** A shell-and-Python agent cannot be given "the retriever as the
  only thing that changes": bash and lexical search are always available, so an injected retriever competes with the
  agent's own `grep` (inference from Sec. 2.2-2.3, pp.4-5). The paper offers no switch to turn them off.
- **Cost.** The paper's own estimate is 600 dollars for one Lite evaluation with the mid model, 1.72 dollars per instance
  (p.19, Table 4 p.8); the project's single-call arm-run is about 2 dollars on the cheapest candidate (`docs/RQ3_PILOT.md`,
  estimated at stored unverified prices), so the loop would be about two orders of magnitude dearer per arm-run.
- **What it supplies instead.** Mocked-model integration tests with stored prompt-response pairs (Sec. E, p.19) are the
  same idea as the project's replay test of the driver (30 of 30 on the real executor); it is a design precedent, not
  evidence.
- **Reporting precedent, not a protocol.** One number per cell and no interval is the norm in this literature
  (also in the other four papers read here); the project's paired interval plan (D113) goes beyond it.
- **Change suggested, none made.** None to D113.

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ2: nothing.
- RQ3: names a scaffold family from ADR-007's list; its software-engineering results are single-run, undefined-cost
  numbers for agents with their own search; no retrieval swap.

## Discrepancies

- **Internal:** the small closed-source model resolves 6.3% in Table 3 (p.7) and 7.0% in Table 4 (p.8) on the same
  300 instances, both for CodeAct v1.8; the paper does not say why.
- **Cost footnotes:** a conservative 3 dollars per instance gives 6.9k for 2,294 instances (p.7); Table 4's 1.72 dollars
  times 300 is 516 dollars, against the 600 dollars of footnote 4 (p.19); the footnotes' basis is not given.
- **Against Agentless (read in full, Table 1, p.10 of that paper):** Table 3 here lists Agentless at 27.3 on Lite; Agentless
  v2 reports 32.00%. The version cited here is not stated (cause not established).
- **Against `docs/EVAL_API.md` ("OpenHands v3: pin one agent and test its retrieval extension and bypass policy"):** the
  paper has no retrieval extension and no policy for bypassing search; "retry, usage and termination records" are only
  partly present: accumulated cost is in the state (Sec. 2.1, p.3), retry and termination rules are not described.
- **Against another note (CodeGrep, frozen OpenHands with temperature 0 and a 100-round maximum):** those settings come from
  that paper; this paper fixes neither.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README "alternative scaffold" | confirmed | Abstract, p.1 | A platform with several agents; the software-engineering agent is a tool-using loop. |
| ADR-007: tool loop adds variance and cost | partly confirmed | Table 4, p.8; Sec. E footnote 4, p.19 | Cost shown; variance never measured. |
| EVAL_API: retrieval extension and bypass policy | not found | Sec. 2.3, p.5 | Lexical skills and shell only. |
| EVAL_API: termination records | not found | Sec. 2.1, p.3 | Not described beyond the finish action in Figure 3, p.4. |
