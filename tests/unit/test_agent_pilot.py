from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
import yaml

from ril.agent.contracts import (
    FileEdit,
    ModelRequest,
    ModelResponse,
    RetrievedFile,
    Task,
    Usage,
    validate_path,
)
from ril.agent.fixtures import make_fixtures
from ril.agent.grading import FixtureTestGrader
from ril.agent.pilot import live_gate, run_config, run_instance, source_manifest, summarize
from ril.agent.scripted import ScriptedRepair
from ril.agent.tools import FileRetrieval


def test_fixture_reference_and_unmodified_controls() -> None:
    for fixture in make_fixtures():
        assert all(edit[2] not in fixture.task.issue for edit in fixture.reference_edits)
        assert fixture.test_source not in fixture.task.issue
        grader = FixtureTestGrader(fixture.test_source)
        assert not grader.grade(fixture.task, ()).resolved
        assert grader.grade(
            fixture.task, [FileEdit(*edit) for edit in fixture.reference_edits]
        ).resolved


def test_grader_rejects_wrong_and_escaping_edits() -> None:
    fixture = make_fixtures(1)[0]
    grader = FixtureTestGrader(fixture.test_source)
    assert not grader.grade(fixture.task, [FileEdit("module_0.py", "absent", "new")]).resolved
    assert not grader.grade(fixture.task, [FileEdit("_checks.py", "old", "new")]).resolved
    with pytest.raises(ValueError, match="relative paths"):
        grader.grade(fixture.task, [FileEdit("../escape.py", "old", "new")])
    with pytest.raises(ValueError, match="relative paths"):
        validate_path(".")


def test_grader_reports_timeout_and_test_error() -> None:
    task = make_fixtures(1)[0].task
    assert FixtureTestGrader("while True: pass", timeout_s=0.02).grade(task, ()).status == "timeout"
    assert not FixtureTestGrader("raise RuntimeError('broken test')").grade(task, ()).resolved


def test_retrieval_gold_boundary_and_deterministic_bm25() -> None:
    fixture = make_fixtures(2)[1]
    with pytest.raises(ValueError, match="only the oracle"):
        FileRetrieval(fixture.task.files, "bm25", gold_files=fixture.gold_files)
    with pytest.raises(ValueError, match="existing gold"):
        FileRetrieval(fixture.task.files, "oracle", gold_files=["missing.py"])
    bm25 = FileRetrieval(fixture.task.files, "bm25")
    first = bm25.search(fixture.task.issue, 1)
    assert first == bm25.search(fixture.task.issue, 1)
    assert [r.path for r in first] == list(fixture.gold_files)
    assert FileRetrieval(fixture.task.files, "none").search(fixture.task.issue, 1) == ()
    with pytest.raises(ValueError, match="positive"):
        bm25.search("query", 0)


def test_model_receives_no_reference_labels_or_hidden_checks() -> None:
    fixture = make_fixtures(1)[0]
    requests: list[dict[str, object]] = []

    class Spy:
        def propose(self, request: ModelRequest) -> ModelResponse:
            requests.append(asdict(request))
            return ModelResponse((), Usage(5, 4, 0.25))

    result = run_instance(
        fixture.task,
        retriever_id="none",
        tool=FileRetrieval(fixture.task.files, "none"),
        model=Spy(),
        grader=FixtureTestGrader(fixture.test_source),
        seed=0,
        temperature=0,
        top_k=1,
    )
    assert set(requests[0]) == {"instance_id", "issue", "context", "seed", "temperature"}
    assert requests[0]["context"] == ()
    assert not result["resolved"]
    assert result["usage"]["synthetic_usd"] == 0.25
    assert result["usage"]["actual_usd"] == 0
    with pytest.raises(TypeError):
        ModelResponse((), Usage(0, 0, 0), resolved=True)  # type: ignore[call-arg]


def test_retriever_cannot_forge_snapshot_content() -> None:
    fixture = make_fixtures(1)[0]

    class Forged:
        def search(self, query: str, limit: int) -> object:
            return FileRetrieval(
                {"module_0.py": "forged"}, "oracle", gold_files=["module_0.py"]
            ).search(query, limit)

    with pytest.raises(ValueError, match="snapshot"):
        run_instance(
            fixture.task,
            retriever_id="bm25",
            tool=Forged(),  # type: ignore[arg-type]
            model=ScriptedRepair(),
            grader=FixtureTestGrader(fixture.test_source),
            seed=0,
            temperature=0,
            top_k=1,
        )


@pytest.mark.parametrize("fault", ["duplicate", "over-limit", "nonfinite"])
def test_retriever_rejects_malformed_results(fault: str) -> None:
    fixture = make_fixtures(1)[0]
    path = fixture.gold_files[0]
    file = RetrievedFile(
        path, fixture.task.files[path], float("nan") if fault == "nonfinite" else 1
    )

    class Broken:
        def search(self, query: str, limit: int) -> tuple[RetrievedFile, ...]:
            return (file,) if fault == "nonfinite" else (file, file)

    with pytest.raises(ValueError, match="duplicate or over-limit|finite"):
        run_instance(
            fixture.task,
            retriever_id="bm25",
            tool=Broken(),
            model=ScriptedRepair(),
            grader=FixtureTestGrader(fixture.test_source),
            seed=0,
            temperature=0,
            top_k=1,
        )


def test_source_checksum_does_not_depend_on_caller_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = source_manifest()
    monkeypatch.chdir(tmp_path)
    assert source_manifest() == before
    assert "ril/agent/pilot.py" in before["files"]


def _config(tmp_path: Path) -> Path:
    cfg = yaml.safe_load(Path("configs/experiments/c_agent_pilot.yaml").read_text())
    cfg["output"] = str(tmp_path / "output")
    cfg["log_path"] = str(tmp_path / "log.json")
    cfg["bootstrap_draws"] = 100
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


def test_whole_pilot_actual_tests_statistics_and_reproducibility(tmp_path: Path) -> None:
    path = _config(tmp_path)
    first, second = run_config(str(path)), run_config(str(path))
    assert first["real_instances"] == 0
    assert first["scientific_cost_discordance_mde"] is None
    assert not first["published_scaffold_replication"]
    assert len(first["rows"]) == 60
    assert len(first["discordance_rows"]) == 60
    assert sum(r["discordant"] for r in first["discordance_rows"]) == 24
    rates = {r["retriever_id"]: r["resolved_rate"] for r in first["conditions"]}
    assert rates == {"none": 0.2, "bm25": 0.6, "oracle": 0.8}
    assert first["comparisons"] == second["comparisons"]
    for a, b in zip(first["rows"], second["rows"], strict=True):
        a, b = copy.deepcopy(a), copy.deepcopy(b)
        for timing in ("wall_seconds", "retrieval_ms", "test_log"):
            a.pop(timing)
            b.pop(timing)
        assert a == b
    assert first["source_manifest"] == source_manifest()
    assert sum(r["actual_usd"] for r in first["conditions"]) == 0
    assert all(r["synthetic_usd"] > 0 for r in first["conditions"])
    assert json.loads((tmp_path / "log.json").read_text())["config_hash"] == first["config_hash"]
    assert (tmp_path / "output" / "latency_log.csv").is_file()
    with pytest.raises(ValueError, match="duplicate"):
        summarize(first["rows"] + [first["rows"][0]], draws=10, seed=0)
    with pytest.raises(ValueError, match="missing"):
        summarize(first["rows"][1:], draws=10, seed=0)
    changed = copy.deepcopy(first["rows"])
    changed[0]["snapshot_sha256"] = "different"
    with pytest.raises(ValueError, match="differs"):
        summarize(changed, draws=10, seed=0)
    changed = copy.deepcopy(first["rows"])
    changed[0]["execution_identity"]["model"] = "different"
    with pytest.raises(ValueError, match="differs"):
        summarize(changed, draws=10, seed=0)


def test_live_gate_never_calls_an_adapter_or_prints_credentials() -> None:
    with pytest.raises(ValueError, match="positive spend cap"):
        live_gate({}, {})
    supplied = {
        "model_revision": "pinned",
        "scaffold_revision": "pinned",
        "harness_revision": "pinned",
        "adapter": "external",
        "spend_cap_usd": 1,
        "credential_env": "TEST_ACCESS",
    }
    with pytest.raises(ValueError, match="credential environment"):
        live_gate(supplied, {})
    with pytest.raises(ValueError, match="not installed") as error:
        live_gate(supplied, {"TEST_ACCESS": "must-never-appear"})
    assert "must-never-appear" not in str(error.value)


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan")])
def test_usage_rejects_invalid_cost(bad: float) -> None:
    with pytest.raises(ValueError):
        Usage(0, 0, bad)
    with pytest.raises(ValueError):
        ScriptedRepair(input_per_million=bad)


def test_no_real_or_verified_instance_can_enter_fixture_harness() -> None:
    task = make_fixtures(1)[0].task
    with pytest.raises(ValueError, match="synthetic fixtures only"):
        replace(task, role="test")
    with pytest.raises(ValueError, match="synthetic fixtures only"):
        replace(task, instance_id="django__django-123")
    with pytest.raises(ValueError, match="fixture repository"):
        Task("fixture-001", "ansible/ansible", "issue", task.files)
