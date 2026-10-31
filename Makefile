# Targets for local development. Python 3.11 is pinned (see pyproject.toml).
#
# Local:  Poetry creates .venv in the project (POETRY_VIRTUALENVS_IN_PROJECT).
# Ada:    use uv inside an srun allocation (login-node installs run out of memory; see
#         docs/COMPUTE.md):
#           srun --pty bash
#           uv venv --python 3.11 .venv && uv pip install -e . pytest pytest-cov ruff mypy types-pyyaml
#         then run the targets below with RUN= (empty) after `source .venv/bin/activate`.
#
# torch is an optional Poetry group: `make setup` never installs it (the local box is 8 GB and runs
# no training, encoding or model loading); `make setup-train` adds it, on Ada only. `make test` runs
# the unit tests without the `torch` and `slow` markers on one worker; `make test-all` (every test,
# torch ones included) is for Ada only.

PYTHON ?= python3.11
BASE ?= main
export POETRY_VIRTUALENVS_IN_PROJECT = true
RUN ?= poetry run

.PHONY: setup setup-train test test-all lint format bench bench-check bench-graph hooks review review-flags

setup:
	poetry env use $(PYTHON)
	poetry sync
	$(RUN) python scripts/check_env.py

# Ada only: adds the optional training group (torch).
setup-train:
	poetry env use $(PYTHON)
	poetry sync --with train
	$(RUN) python scripts/check_env.py

test:
	$(RUN) pytest tests/unit -q -p no:xdist -m "not torch and not slow"

# Ada only (needs `make setup-train`).
test-all:
	$(RUN) pytest tests -q -p no:xdist

lint:
	$(RUN) ruff check ril tests scripts
	$(RUN) ruff format --check ril tests scripts
	$(RUN) mypy

format:
	$(RUN) ruff check --fix ril tests scripts
	$(RUN) ruff format ril tests scripts

bench:
	$(RUN) python scripts/bench.py run

bench-check:
	$(RUN) python scripts/bench.py check

# Real parse and graph_build throughput and graph expansion latency (all storage options) for the
# checkouts under data/raw/repos (flask, requests and, if present, django); appends to results/latency.
bench-graph:
	$(RUN) python -m ril.bench.graph_measure all \
	  --repo flask=data/raw/repos/pallets__flask=pallets/flask \
	  --repo requests=data/raw/repos/psf__requests=psf/requests \
	  --work data/processed/p_graph/work --log-dir results/latency --out data/processed/p_graph/graph_measure.json

hooks:
	@sh scripts/hooks/install.sh

# Flags on the added lines of this branch against BASE, and a trace of ledger numbers to results/
# (docs/REVIEW.md). Exits non-zero on a blocking finding.
review-flags:
	$(RUN) python scripts/review_flags.py --base $(BASE)
	$(RUN) python scripts/review_flags.py --tree

# What a pull request must show: lint, the fast tests and the flags.
review: lint test review-flags
