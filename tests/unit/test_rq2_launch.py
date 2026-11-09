"""Preflight, submit refusals and the job graph the submit script prints (no torch, no cluster).

``ril.bench.rq2_launch`` and ``scripts/rq2_{preflight,submit}.py``; implements D124 and the
launch checklist of ``docs/RQ2_LAUNCH_PLAN.md``.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

from ril.bench import rq2_launch as rl
from ril.training import rq2_plan as rp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=rl.UTC)


@pytest.fixture(autouse=True)
def _dev_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    import ril.evaluation.eval_plan as ep

    monkeypatch.setattr(ep, "plan_sets", lambda sets, **k: {"ready": True, "sets": []})


def _work(tmp_path: Path, family: str, *, examples: int = 5800, size: int = 3450) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    inputs = tmp_path / rl.INPUTS_HOME_REL[family] if family in rl.INPUTS_HOME_REL else work
    inputs.mkdir(parents=True, exist_ok=True)
    for f in rl.INPUTS[family]:
        (inputs / f).write_text("x")
    (work / "registration.json").write_text(
        json.dumps({"cell_table_sha256": rp.cell_table_digest()})
    )
    (work / "leakage_ok.json").write_text(json.dumps({"commit": "abc", "failed": 0, "passed": 19}))
    (work / "prep_summary.json").write_text(
        json.dumps(
            {
                "examples": examples,
                "filter_size": size,
                "held_out_rows": 0,
                "drop_list_applied": True,
            }
        )
    )
    return work


def _checks(tmp_path: Path, family: str, **kw: object) -> dict[str, rl.Check]:
    work = _work(tmp_path, family, **{k: v for k, v in kw.items() if k in ("examples", "size")})
    args: dict = dict(
        family=family,
        repo=str(ROOT),
        work=str(work),
        home=str(tmp_path),
        commit="abc",
        retain_dir=str(tmp_path / "retained") if family == "mined" else None,
        free_gb=50.0,
    )
    args.update({k: v for k, v in kw.items() if k not in ("examples", "size")})
    return {c.id: c for c in rl.run_checks(**args)}


def test_every_check_passes_on_a_complete_mined_launch(tmp_path: Path) -> None:
    c = _checks(tmp_path, "mined")
    assert all(x.ok for x in c.values()), {k: v.detail for k, v in c.items() if not v.ok}
    assert {
        "commit_recorded",
        "cell_table_registered",
        "seeds_fresh",
        "prep_summary",
        "configs_conform",
        "inputs_present",
        "memory_request",
        "space",
        "retain_dir",
        "dev_set_ready",
        "leakage_tests",
        "distinct_examples_stated",
    } <= set(c)
    assert "0.55 passes" in c["distinct_examples_stated"].detail


def _fresh(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    return d


def test_injected_launch_needs_no_retention_and_no_prep_summary(tmp_path: Path) -> None:
    c = _checks(_fresh(tmp_path, "a"), "injected")
    assert all(x.ok for x in c.values()), {k: v.detail for k, v in c.items() if not v.ok}
    assert "prep_summary" not in c
    assert not _checks(_fresh(tmp_path, "b"), "injected", retain_dir="/somewhere")["retain_dir"].ok


def test_injected_inputs_are_read_in_place_from_the_noise_pilot_directory(tmp_path: Path) -> None:
    c = _checks(_fresh(tmp_path, "a"), "injected")
    assert c["inputs_present"].ok
    gone = _fresh(tmp_path, "b")
    _work(gone, "injected")
    (gone / rl.INPUTS_HOME_REL["injected"] / "pool_A.jsonl.gz").unlink()
    got = {
        x.id: x
        for x in rl.run_checks(
            family="injected",
            repo=str(ROOT),
            work=str(gone / "work"),
            home=str(gone),
            commit="abc",
            retain_dir=None,
            free_gb=50.0,
        )
    }
    assert not got["inputs_present"].ok and "pool_A" in got["inputs_present"].detail


def test_a_short_filter_pool_is_stated_not_blocked(tmp_path: Path) -> None:
    c = _checks(tmp_path, "mined", examples=3000, size=2000)
    assert c["distinct_examples_stated"].ok and "D133" in c["distinct_examples_stated"].detail
    assert "shortfall 1200" in c["distinct_examples_stated"].detail


@pytest.mark.parametrize(
    "mutate, check",
    [
        (lambda w: (w / "registration.json").write_text("{}"), "cell_table_registered"),
        (
            lambda w: (w / "leakage_ok.json").write_text(
                json.dumps({"commit": "zzz", "failed": 0})
            ),
            "leakage_tests",
        ),
        (
            lambda w: (w / "leakage_ok.json").write_text(
                json.dumps({"commit": "abc", "failed": 2})
            ),
            "leakage_tests",
        ),
        (lambda w: (w / "mined.jsonl.gz").unlink(), "inputs_present"),
        (
            lambda w: (w / "prep_summary.json").write_text(
                json.dumps(
                    {"examples": 9, "filter_size": 3, "held_out_rows": 4, "drop_list_applied": True}
                )
            ),
            "prep_summary",
        ),
        (lambda w: (w / "prep_summary.json").unlink(), "prep_summary"),
    ],
)
def test_missing_or_wrong_inputs_fail_the_named_check(tmp_path: Path, mutate, check: str) -> None:  # type: ignore[no-untyped-def]
    work = _work(tmp_path, "mined")
    mutate(work)
    c = {
        x.id: x
        for x in rl.run_checks(
            family="mined",
            repo=str(ROOT),
            work=str(work),
            home=str(tmp_path),
            commit="abc",
            retain_dir=str(tmp_path / "r"),
            free_gb=50.0,
        )
    }
    assert not c[check].ok


def test_space_commit_and_retention_checks(tmp_path: Path) -> None:
    cases = (
        ("space", dict(free_gb=2.0)),
        ("commit_recorded", dict(head_commit="def")),
        ("retain_dir", dict(retain_dir=None)),
        ("retain_dir", dict(retain_dir="relative/dir")),
        ("retain_dir", dict(retain_dir=str(ROOT / "models"))),  # inside a git work tree
    )
    for i, (check, kw) in enumerate(cases):
        assert not _checks(_fresh(tmp_path, f"case{i}"), "mined", **kw)[check].ok


def test_conditional_cell_needs_a_measurement_at_most_six_gpu_hours(tmp_path: Path) -> None:
    work = _work(tmp_path, "mined")
    (work / "features_mined.csv").write_text("directory,bm25_rank,swerankembed-small_rank\n")
    kw = dict(
        family="mined",
        repo=str(ROOT),
        work=str(work),
        home=str(tmp_path),
        commit="abc",
        retain_dir=str(tmp_path / "r"),
        free_gb=50.0,
        include_conditional=True,
    )
    assert not {c.id: c for c in rl.run_checks(**kw)}["dense_teacher_gate"].ok  # no measurement yet
    (work / "teacher_measure.json").write_text(json.dumps({"full_store_gpu_hours": 7.5}))
    assert not {c.id: c for c in rl.run_checks(**kw)}["dense_teacher_gate"].ok
    (work / "teacher_measure.json").write_text(json.dumps({"full_store_gpu_hours": 5.2}))
    assert {c.id: c for c in rl.run_checks(**kw)}["dense_teacher_gate"].ok


def test_memory_request_is_read_from_the_script_and_below_the_ceiling() -> None:
    assert (
        rl._mem_mb("#SBATCH --mem=30G\n") == 30 * 1024 and rl._mem_mb("#SBATCH --mem=512M\n") == 512
    )
    assert rl._mem_mb("nothing") is None
    for fam, script in rl.SCRIPTS.items():
        assert (
            rl._mem_mb((ROOT / script).read_text()) == rp.MEM_REQUEST_MB[fam] <= rp.MEM_CEILING_MB
        )


def _pre(tmp_path: Path, **over: object) -> str:
    rec = rl.write_preflight(
        str(tmp_path / "pre.json"),
        account=str(over.get("account", "C")),
        family="mined",
        commit="abc",
        include_conditional=bool(over.get("cond", False)),
        checks=over.get("checks", [rl.Check("x", True, "ok")]),  # type: ignore[arg-type]
        now=NOW,
    )
    return str(tmp_path / "pre.json") if rec["version"] else ""


def _refusals(path: str | None, **kw: object) -> list[str]:
    base = dict(account="C", family="mined", commit="abc", include_conditional=False, now=NOW)
    base.update(kw)
    return rl.preflight_refusals(path, **base)  # type: ignore[arg-type]


def test_preflight_file_is_required_and_must_match(tmp_path: Path) -> None:
    ok = _pre(tmp_path)
    assert _refusals(ok) == []
    assert "no preflight file" in _refusals(None)[0]
    assert _refusals(str(tmp_path / "missing.json"))
    assert any("account" in r for r in _refusals(ok, account="A"))
    assert any("commit" in r for r in _refusals(ok, commit="other"))
    assert any("conditional" in r for r in _refusals(ok, include_conditional=True))
    assert any("old" in r for r in _refusals(ok, now=NOW + dt.timedelta(hours=60)))
    failing = _pre(tmp_path, checks=[rl.Check("space", False, "low")])
    assert any("space" in r for r in _refusals(failing))


def test_graph_is_one_job_per_run_chained_and_printed() -> None:
    subs = rl.submissions("mined", commit="abc", retain_dir="/r", date="2026-11-12")
    assert len(subs) == 15 and all(
        s.export["RETAIN_DIR"] == "/r" and s.export["DATE"] == "2026-11-12" for s in subs
    )
    assert not any("filter_srs" in s.run_id for s in subs)  # conditional cells wait for D125
    assert (
        len(
            rl.submissions(
                "mined", commit="a", retain_dir="/r", date="2026-11-12", include_conditional=True
            )
        )
        == 18
    )
    inj = rl.submissions("injected", commit="abc", retain_dir=None, date="2026-11-12")
    assert len(inj) == 18 and all("RETAIN_DIR" not in s.export for s in inj)
    text = rl.render_graph(subs, "C", "mined")
    assert (
        "15 GPU jobs" in text
        and "afterany" in text
        and sum("mem 30 GB" in ln for ln in text.splitlines()) == 15
    )
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        rl.submissions("mined", commit="a", retain_dir=None, date="tomorrow")


def test_submit_chains_with_afterany_and_never_submits_twice() -> None:
    subs = rl.submissions("injected", commit="abc", retain_dir=None, date="2026-11-12")[:3]
    cmds: list[list[str]] = []

    def runner(cmd: list[str]) -> str:
        cmds.append(cmd)
        return f"{100 + len(cmds)};cluster\n"

    ids = rl.submit(subs, runner=runner, queued_names=lambda: [])
    assert [i for _, i in ids] == ["101", "102", "103"]
    assert not any(a.startswith("--dependency") for a in cmds[0])
    assert "--dependency=afterany:101" in cmds[1] and "--dependency=afterany:102" in cmds[2]
    assert all("--parsable" in c and c[-1].endswith("rq2f_injected_run.sbatch") for c in cmds)
    assert any(
        a.startswith("--export=ALL,DATE=2026-11-12,RIL_COMMIT=abc,RUN_ID=inj_") for a in cmds[0]
    )
    with pytest.raises(RuntimeError, match="already queued"):
        rl.submit(subs, runner=runner, queued_names=lambda: [subs[1].job_name])
    assert len(cmds) == 3  # nothing more was submitted


def test_submit_cli_refuses_without_confirmation_and_with_a_bad_preflight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import rq2_submit

    monkeypatch.setenv("RIL_COMMIT", "abc")
    calls: list[list[str]] = []
    monkeypatch.setattr(rq2_submit, "_run", lambda cmd: calls.append(cmd) or "1")
    monkeypatch.setattr(rq2_submit, "_queued", lambda: [])
    base = ["--family", "mined", "--account", "C", "--date", "2026-11-12", "--retain-dir", "/r"]
    assert rq2_submit.main([*base, "--print-graph"]) == 0
    assert "15 GPU jobs" in capsys.readouterr().out
    assert rq2_submit.main(base) == 2  # no --confirm-launch
    assert "--confirm-launch" in capsys.readouterr().err
    assert rq2_submit.main([*base, "--confirm-launch"]) == 2  # no preflight file
    assert "no preflight file" in capsys.readouterr().err
    assert (
        rq2_submit.main(
            ["--family", "mined", "--account", "A", "--date", "2026-11-12", "--confirm-launch"]
        )
        == 2
    )
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert rq2_submit.main([*base, "--confirm-launch", "--preflight", str(bad)]) == 2
    assert calls == []  # nothing was ever submitted


def test_registration_and_leakage_records_feed_the_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import rq2_record

    work = tmp_path / "w"
    assert rq2_record.main(["registration", "--work", str(work)]) == 0
    reg = json.loads((work / "registration.json").read_text())
    assert reg["cell_table_sha256"] == rp.cell_table_digest()
    out = tmp_path / "pytest.txt"
    out.write_text("..........\n41 passed in 40.63s\n")
    monkeypatch.setenv("RIL_COMMIT", "abc")
    assert rq2_record.main(["leakage", "--work", str(work), "--pytest-output", str(out)]) == 0
    assert json.loads((work / "leakage_ok.json").read_text()) == {
        "commit": "abc",
        "passed": 41,
        "failed": 0,
    }
    for bad in (
        "1 failed, 40 passed in 3.1s\n",
        "3 passed, 1 error in 3.1s\n",
        "no summary here\n",
    ):
        out.write_text(bad)
        assert rq2_record.main(["leakage", "--work", str(work), "--pytest-output", str(out)]) == 2
    monkeypatch.delenv("RIL_COMMIT")
    assert rq2_record.main(["leakage", "--work", str(work), "--pytest-output", str(out)]) == 2
