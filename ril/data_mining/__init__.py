"""PR-mined training set (workstream C2, rebuilt): unfiltered issue-to-function pairs.

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Modules: ``github_api`` (client),
``links`` (merged pull requests and closing issues), ``diff`` and ``mapping`` (hunks to units of
the base commit), ``snapshot`` (Python files at a commit), ``miner`` (one pull request to one
instance), ``store`` (directory-per-PR output, resumable state, provenance), ``population`` (the
repositories of the pool and the selection analysis). Output is read by
``ril.training.pool_reader`` unchanged.
"""
