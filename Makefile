# Targets for local development. Python 3.11 is pinned (see pyproject.toml).
#
# Local:  Poetry creates .venv in the project (POETRY_VIRTUALENVS_IN_PROJECT).
# Ada:    use uv inside an srun allocation (login-node installs run out of memory; see
#         docs/COMPUTE.md):
#           srun --pty bash
#           uv venv --python 3.11 .venv && uv pip install -e . pytest pytest-cov ruff mypy types-pyyaml
#         then run the targets below with RUN= (empty) after `source .venv/bin/activate`.

PYTHON ?= python3.11
export POETRY_VIRTUALENVS_IN_PROJECT = true
RUN ?= poetry run

.PHONY: setup test test-all lint format bench bench-check hooks

setup:
	poetry env use $(PYTHON)
	poetry install
	$(RUN) python scripts/check_env.py

test:
	$(RUN) pytest tests/unit -q

test-all:
	$(RUN) pytest tests -q

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

hooks:
	@sh scripts/hooks/install.sh
