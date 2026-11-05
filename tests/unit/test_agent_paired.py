"""Persistent dispatch, hidden-input identity, accounting and diagnostic contracts."""

from __future__ import annotations

import copy
import multiprocessing
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from ril.agent import paired, pilot
from ril.agent.contracts import FileEdit, ModelResponse, Usage
from ril.agent.fixtures import make_fixtures
from ril.agent.grading import FixtureTestGrader
from ril.agent.scripted import ScriptedRepair


@pytest.fixture(autouse=True)
def no_redundant_power_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    # C3/shared-stat tests cover exact power. These tests exercise dispatch and pairing statistics.
    monkeypatch.setattr(pilot, "_fixture_mde", lambda n, d: None)


def config(tmp_path: Path, *, n: int = 2) -> Path:
    cfg = yaml.safe_load(Path("configs/agent/c_paired_fixture.yaml").read_text())
    cfg.update(instances=n, bootstrap_draws=30, output=str(tmp_path / "run"))
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


def change(path: Path, **values: Any) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    cfg.update(values)
    path.write_text(yaml.safe_dump(cfg))
    return cfg


def checkpoint(path: Path) -> Path:
    return Path(yaml.safe_load(path.read_text())["output"]) / "checkpoint.json"


def test_resume_reuses_exact_pair_bytes_without_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    first = paired.run_config(str(path))
    before = checkpoint(path).read_bytes()
    report_before = (checkpoint(path).parent / "results.json").read_bytes()

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("completed pair was executed again")

    monkeypatch.setattr(ScriptedRepair, "propose", fail)
    monkeypatch.setattr(FixtureTestGrader, "grade", fail)
    second = paired.run_config(str(path))
    assert first["report"] == second["report"]
    assert second["invocation"] == {"new_model_calls": 0, "reused_pairs": 4, "actual_usd": 0.0}
    assert checkpoint(path).read_bytes() == before
    assert (checkpoint(path).parent / "results.json").read_bytes() == report_before
    assert first["report"]["budget"]["observed_usd"] > 0
    assert first["report"]["budget"]["reserved_usd"] <= 1


@pytest.mark.parametrize(
    "field,value", [("seed", 9), ("temperature", 1), ("instances", 3), ("max_output_tokens", 4000)]
)
def test_config_change_refused(tmp_path: Path, field: str, value: Any) -> None:
    path = config(tmp_path)
    paired.run_config(str(path))
    change(path, **{field: value})
    with pytest.raises(ValueError, match="identity mismatch|temperature"):
        paired.run_config(str(path))


def test_retriever_parameters_under_same_id_refused(tmp_path: Path) -> None:
    path = config(tmp_path)
    paired.run_config(str(path))
    cfg = yaml.safe_load(path.read_text())
    cfg["retrievers"][0]["top_k"] = 2
    change(path, retrievers=cfg["retrievers"])
    with pytest.raises(ValueError, match="identity mismatch"):
        paired.run_config(str(path))


@pytest.mark.parametrize("kind", ["source", "snapshot", "hidden_tests", "gold", "reference"])
def test_execution_identity_drift_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = config(tmp_path)
    paired.run_config(str(path))
    if kind == "source":
        monkeypatch.setattr(paired, "source_manifest", lambda: {"sha256": "different"})
    else:
        fixtures = make_fixtures(2)
        item = fixtures[0]
        if kind == "snapshot":
            item = replace(
                item, task=replace(item.task, files={**item.task.files, "more.py": "x=1"})
            )
        elif kind == "hidden_tests":
            item = replace(item, test_source=item.test_source + "# changed\n")
        elif kind == "gold":
            item = replace(item, gold_files=("decoy.py",))
        else:
            item = replace(item, reference_edits=(("decoy.py", "old", "new"),))
        fixtures[0] = item
        monkeypatch.setattr(paired, "make_fixtures", lambda n: fixtures)
    with pytest.raises(ValueError, match="identity mismatch"):
        paired.run_config(str(path))


@pytest.mark.parametrize("kind", ["bytes", "row", "missing", "checkpoint_removed"])
def test_corruption_and_missing_pairs_fail_closed(tmp_path: Path, kind: str) -> None:
    path = config(tmp_path)
    paired.run_config(str(path))
    cp = checkpoint(path)
    if kind == "bytes":
        cp.write_text("{invalid")
    elif kind == "checkpoint_removed":
        cp.unlink()
    else:
        state = paired.load_checkpoint(cp)
        key = next(iter(state["pairs"]))
        if kind == "missing":
            del state["pairs"][key]
        else:
            state["pairs"][key]["row"]["resolved"] = False
        paired.save_checkpoint(cp, state)
    with pytest.raises(ValueError, match="corrupt|missing|checksum|diagnostic"):
        paired.run_config(str(path))


def test_partial_completion_crash_resume_no_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    original = paired.save_checkpoint
    calls = 0

    def crash_after_first_completion(cp: Path, state: dict[str, Any]) -> None:
        nonlocal calls
        original(cp, state)
        calls += 1
        if calls == 3:  # initial state, reservation, first completion durably committed
            raise KeyboardInterrupt

    monkeypatch.setattr(paired, "save_checkpoint", crash_after_first_completion)
    with pytest.raises(KeyboardInterrupt):
        paired.run_config(str(path))
    first_row = next(
        e["row"]
        for e in paired.load_checkpoint(checkpoint(path))["pairs"].values()
        if e["status"] == "complete"
    )
    monkeypatch.setattr(paired, "save_checkpoint", original)
    result = paired.run_config(str(path))
    assert result["invocation"]["new_model_calls"] == 3
    assert result["invocation"]["reused_pairs"] == 1
    assert first_row in result["report"]["rows"]
    assert result["report"]["statistics_status"] == "complete"


@pytest.mark.parametrize("crash_at", ["reservation", "model", "grade"])
def test_ambiguous_dispatch_never_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_at: str
) -> None:
    path = config(tmp_path)
    original_save = paired.save_checkpoint
    original_model = ScriptedRepair.propose
    original_grade = FixtureTestGrader.grade

    def interrupt(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    def after_reservation(cp: Path, state: dict[str, Any]) -> None:
        original_save(cp, state)
        if any(e["status"] == "reserved" for e in state["pairs"].values()):
            raise KeyboardInterrupt

    if crash_at == "reservation":
        monkeypatch.setattr(paired, "save_checkpoint", after_reservation)
    elif crash_at == "model":
        monkeypatch.setattr(ScriptedRepair, "propose", interrupt)
    else:
        monkeypatch.setattr(FixtureTestGrader, "grade", interrupt)
    with pytest.raises(KeyboardInterrupt):
        paired.run_config(str(path))
    monkeypatch.setattr(paired, "save_checkpoint", original_save)
    monkeypatch.setattr(ScriptedRepair, "propose", original_model)
    monkeypatch.setattr(FixtureTestGrader, "grade", original_grade)
    result = paired.run_config(str(path))
    report = result["report"]
    assert result["invocation"]["new_model_calls"] == 3
    assert report["completed_pairs"] == 3 and report["requested_pairs"] == 4
    assert report["complete_paired_instances"] == 1
    assert report["summary"] is None
    assert report["statistics_status"] == "blocked_incomplete_pairs"
    assert report["missing_pairs"][0]["reason"] == "dispatch_outcome_unknown"
    assert report["budget"]["reserved_usd"] > report["budget"]["observed_usd"]
    assert all(type(row["resolved"]) is bool for row in report["rows"])


def test_cap_persists_before_dispatch_and_never_refunds_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    cfg = yaml.safe_load(path.read_text())
    maximum = paired.quote(make_fixtures(2)[0], cfg)["synthetic_usd_max"]
    change(path, synthetic_cap_usd=maximum)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated unknown result")

    monkeypatch.setattr(ScriptedRepair, "propose", fail)
    first = paired.run_config(str(path))
    second = paired.run_config(str(path), report_dir=str(tmp_path / "after"))
    assert first["invocation"]["new_model_calls"] == 1
    assert second["invocation"]["new_model_calls"] == 0
    assert second["report"]["budget"]["reserved_usd"] == maximum
    assert second["report"]["summary"] is None
    assert all(
        x["reason"] == "synthetic_budget_exhausted"
        for x in second["report"]["missing_pairs"]
        if x["status"] == "pending"
    )


def test_overquote_recorded_and_blocks_grade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    change(path, max_output_tokens=1)
    graded = []
    monkeypatch.setattr(
        ScriptedRepair, "propose", lambda self, req: ModelResponse((), Usage(1, 1000, 2.0))
    )
    monkeypatch.setattr(FixtureTestGrader, "grade", lambda *args: graded.append(True))
    result = paired.run_config(str(path))
    assert not graded
    assert result["report"]["budget"]["observed_usd"] == 2
    assert result["report"]["budget"]["actual_usd"] == 0
    assert result["report"]["missing_pairs"][0]["reason"] == "quoted_maximum_exceeded"
    assert result["report"]["completed_pairs"] == 0
    assert result["report"]["summary"] is None


def test_gold_flags_and_failure_proxy_all_categories() -> None:
    row = {"resolved": False, "retrieved": [{"path": "a.py"}], "edits": []}
    result = paired.diagnose(row, ("a.py", "b.py"))
    assert result["gold_file_hits"] == [
        {"path": "a.py", "retrieved": True, "attempted_edit": False},
        {"path": "b.py", "retrieved": False, "attempted_edit": False},
    ]
    assert result["failure_diagnostic"] == "retrieved_not_used"
    assert paired.diagnose(row, ("b.py",))["failure_diagnostic"] == "not_retrieved"
    row["edits"] = [{"path": "a.py", "old": "x", "new": "wrong"}]
    assert paired.diagnose(row, ("a.py", "b.py"))["failure_diagnostic"] == "used_wrong"
    row["resolved"] = True
    row["retrieved"] = []
    assert paired.diagnose(row, ("b.py",))["failure_diagnostic"] is None


def test_wrong_edit_on_gold_is_independently_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path, n=1)
    monkeypatch.setattr(
        ScriptedRepair,
        "propose",
        lambda self, req: ModelResponse(
            (FileEdit("module_0.py", "return value - 2", "return value - 8"),),
            Usage(1, 1, 0.000003),
        ),
    )
    result = paired.run_config(str(path))
    for row in result["report"]["rows"]:
        assert row["resolved"] is False
        assert row["failure_diagnostic"] == "used_wrong"
        assert row["grade_status"] == "tests_failed"


def test_abstained_gold_and_missing_gold_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path, n=1)
    cfg = yaml.safe_load(path.read_text())
    cfg["retrievers"][0].update(id="none", kind="none")
    change(path, retrievers=cfg["retrievers"])
    monkeypatch.setattr(
        ScriptedRepair, "propose", lambda self, req: ModelResponse((), Usage(1, 1, 0.000003))
    )
    rows = paired.run_config(str(path))["report"]["rows"]
    assert [row["failure_diagnostic"] for row in rows] == ["not_retrieved", "retrieved_not_used"]


@pytest.mark.parametrize(
    "values",
    [
        {"synthetic_cap_usd": float("nan")},
        {"seed": True},
        {"temperature": float("inf")},
        {"max_output_tokens": 0},
        {"mode": "test"},
        {"mode": "dev"},
        {"synthetic_pricing": {"input_per_million": -1, "output_per_million": 2}},
        {
            "retrievers": [{"id": "x", "kind": "bm25", "top_k": 1, "k1": float("nan"), "b": 0.75}]
            * 2
        },
    ],
)
def test_invalid_contracts_fail_before_checkpoint(tmp_path: Path, values: dict[str, Any]) -> None:
    path = config(tmp_path)
    change(path, **values)
    with pytest.raises(ValueError):
        paired.run_config(str(path))
    assert not checkpoint(path).exists()


def test_atomic_write_failure_preserves_prior_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cp = tmp_path / "checkpoint.json"
    paired.save_checkpoint(cp, {"number": 1})
    before = cp.read_bytes()

    def fail(*args: Any) -> Any:
        raise OSError("simulated interruption before rename")

    monkeypatch.setattr(paired.os, "replace", fail)
    with pytest.raises(OSError):
        paired.save_checkpoint(cp, {"number": 2})
    assert cp.read_bytes() == before
    assert list(tmp_path.iterdir()) == [cp]


def _worker(path: str, queue: Any) -> None:
    try:
        queue.put(paired.run_config(path)["invocation"])
    except Exception as exc:
        queue.put({"error": repr(exc)})


def test_concurrent_invocations_dispatch_each_pair_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    calls_path = tmp_path / "calls.txt"
    original = ScriptedRepair.propose

    def slow(self: ScriptedRepair, request: Any) -> Any:
        with calls_path.open("a") as stream:
            stream.write(request.instance_id + "\n")
        time.sleep(0.03)
        return original(self, request)

    monkeypatch.setattr(ScriptedRepair, "propose", slow)
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    workers = [ctx.Process(target=_worker, args=(str(path), queue)) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)
        assert worker.exitcode == 0
    results = [queue.get(timeout=2) for _ in workers]
    assert sorted(r["new_model_calls"] for r in results) == [0, 4]
    assert len(calls_path.read_text().splitlines()) == 4


def test_model_requests_never_contain_hidden_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    original = ScriptedRepair.propose
    requests = []

    def inspect(self: ScriptedRepair, request: Any) -> Any:
        requests.append(request)
        assert set(request.__dataclass_fields__) == {
            "instance_id",
            "issue",
            "context",
            "seed",
            "temperature",
        }
        assert "unittest" not in request.issue
        assert "return value +" not in request.issue
        return original(self, request)

    monkeypatch.setattr(ScriptedRepair, "propose", inspect)
    paired.run_config(str(path))
    assert len(requests) == 4


def test_quote_violation_halts_all_future_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    calls = []

    def excessive(self: ScriptedRepair, request: Any) -> Any:
        calls.append(request.instance_id)
        return ModelResponse((), Usage(1, 1000, 2.0))

    monkeypatch.setattr(ScriptedRepair, "propose", excessive)
    first = paired.run_config(str(path))
    second = paired.run_config(str(path), report_dir=str(tmp_path / "resumed-report"))
    assert len(calls) == 1
    assert second["invocation"]["new_model_calls"] == 0
    assert second["report"]["budget"]["dispatch_halted"] is True
    assert first["report"]["budget"]["observed_cap_exceeded"] is True


def test_all_multigold_flags_persist_in_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path, n=1)
    original = make_fixtures(1)[0]
    multigold = replace(original, gold_files=("module_0.py", "decoy.py"))
    monkeypatch.setattr(paired, "make_fixtures", lambda n: [multigold])
    report = paired.run_config(str(path))["report"]
    assert len(report["rows"]) == 2
    for row in report["rows"]:
        assert len(row["gold_file_hits"]) == 2
        assert {f["path"] for f in row["gold_file_hits"]} == {"module_0.py", "decoy.py"}
        assert sum(f["retrieved"] for f in row["gold_file_hits"]) == 1


def test_fresh_seeded_replay_semantics(tmp_path: Path) -> None:
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    a = paired.run_config(str(config(first_dir)))["report"]
    b = paired.run_config(str(config(second_dir)))["report"]

    def semantics(report: dict[str, Any]) -> Any:
        result = copy.deepcopy(report["rows"])
        for row in result:
            for field in (
                "execution_identity",
                "row_sha256",
                "wall_seconds",
                "retrieval_ms",
                "test_log",
            ):
                del row[field]
        return result

    assert semantics(a) == semantics(b)
    assert a["summary"]["comparisons"] == b["summary"]["comparisons"]


def test_no_model_dispatch_when_cap_below_first_quote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path)
    change(path, synthetic_cap_usd=0.00000001)

    def fail(*args: Any) -> Any:
        raise AssertionError("dispatch before budget check")

    monkeypatch.setattr(ScriptedRepair, "propose", fail)
    report = paired.run_config(str(path))["report"]
    assert report["completed_pairs"] == 0
    assert report["requested_pairs"] == 4
    assert report["budget"]["reserved_usd"] == 0
    assert report["summary"] is None
