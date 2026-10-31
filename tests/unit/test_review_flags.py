"""Tests for ril.util.review_flags: every rule fires on a planted problem and stays quiet on the
ordinary form of the same code.

Implements docs/REVIEW.md "Flags and trace-to-source". Each test builds a small throwaway
repository, commits a base, commits the change on a branch and scans the difference. Strings that
the rules look for are assembled from parts so that this file does not trip its own scan.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ril.util.review_flags import (
    BLOCKING,
    WARNING,
    FileDiff,
    Finding,
    Git,
    GitError,
    Hunk,
    Scan,
    branch_name,
    changed_defaults,
    is_shared_path,
    main,
    parse_diff,
    scan,
    scan_tree,
)

NOQA = "# " + "no" + "qa"
TYPE_IGNORE = "# type" + ": ignore"
PRAGMA = "# pragma" + ": no cover"
SKIP = "@pytest.mark." + "skip"
XFAIL = "@pytest.mark." + "xfail"
TOKEN = "gh" + "p_" + "a" * 36
HOME_PATH = "/Users/" + "alice" + "/project/data"
BARE_EXCEPT = "    except" + ":"
MARKER = "TO" + "DO"
TEMP = "tempo" + "rary"

Files = dict[str, "str | bytes | None"]


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        self.run("init", "-q", "-b", "main")

    def run(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    def commit(self, files: Files, message: str = "change") -> None:
        for rel, content in files.items():
            path = self.root / rel
            if content is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        self.run("add", "-A")
        self.run("commit", "-q", "-m", message)

    def branch(self, name: str) -> None:
        self.run("switch", "-q", "-c", name)

    def findings(self, branch: str = "b/feature", numbers: bool = True) -> list[Finding]:
        found, _, _ = scan(Git(self.root), "main", "HEAD", branch=branch, numbers=numbers)
        return found

    def rules(self, severity: str | None = None, **kw: object) -> set[str]:
        return {
            f.rule
            for f in self.findings(**kw)  # type: ignore[arg-type]  # keyword passthrough in tests
            if severity is None or f.severity == severity
        }


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    r = Repo(tmp_path)
    r.commit({"README.md": "base\n"}, "base")
    r.branch("b/feature")
    return r


LEDGER_HEADER = (
    "| date | run_id | kind | what | config_hash | seed | hardware | headline result | log |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def ledger_row(headline: str, log: str = "`results/logs/run.json`") -> str:
    return f"| 2026-01-01 | r1 | measured | x | abc | 0 | cpu | {headline} | {log} |\n"


# -- diff parsing --------------------------------------------------------------------------------


def test_parse_diff_reports_new_side_line_numbers(repo: Repo) -> None:
    repo.commit({"a.py": "one\ntwo\nthree\n"}, "add")
    repo.commit({"a.py": "one\nTWO\nthree\nfour\n"}, "edit")
    diff = parse_diff(repo.run("diff", "-U0", "HEAD~1", "HEAD"))
    assert [d.path for d in diff] == ["a.py"]
    assert diff[0].added == [(2, "TWO"), (4, "four")]
    assert diff[0].hunks[0].removed == [(2, "two")]


def test_parse_diff_marks_new_deleted_and_binary(repo: Repo) -> None:
    repo.commit({"gone.txt": "x\n", "blob.dat": b"\x00\x01\x02"})
    repo.commit({"gone.txt": None, "new.txt": "y\n", "blob.dat": b"\x00\x09\x02"})
    diff = {d.path: d for d in parse_diff(repo.run("diff", "-U0", "HEAD~1", "HEAD"))}
    assert diff["gone.txt"].status == "D"
    assert diff["new.txt"].status == "A"
    assert diff["blob.dat"].binary


# -- blocking: tests and suppressions ------------------------------------------------------------


def test_added_skip_and_xfail_in_tests_block(repo: Repo) -> None:
    body = (
        f"import pytest\n\n\n{SKIP}\ndef test_a():\n    assert True\n\n\n"
        f"{XFAIL}\ndef test_b():\n    pass\n"
    )
    repo.commit({"tests/unit/test_a.py": body})
    found = [f for f in repo.findings() if f.rule == "test-skip"]
    assert {f.line for f in found} == {4, 9}
    assert all(f.severity == BLOCKING for f in found)


def test_importorskip_and_skip_outside_tests_are_not_flagged(repo: Repo) -> None:
    repo.commit(
        {
            "tests/unit/test_a.py": 'import pytest\n\ntorch = pytest.importorskip("torch")\n',
            "ril/mod.py": f"{SKIP}\n",
        }
    )
    assert "test-skip" not in repo.rules()


@pytest.mark.parametrize("directive", [NOQA + ": E402", TYPE_IGNORE + "[arg-type]", PRAGMA, NOQA])
def test_suppression_without_reason_blocks(repo: Repo, directive: str) -> None:
    repo.commit({"ril/mod.py": f"x = 1  {directive}\n"})
    assert "suppression-without-reason" in repo.rules(BLOCKING)


@pytest.mark.parametrize(
    "directive",
    [
        NOQA + ": E402  # path is set on the line above",
        TYPE_IGNORE + "[arg-type]  # stub lacks the overload",
        PRAGMA + "  -- only reached on the cluster",
    ],
)
def test_suppression_with_reason_passes(repo: Repo, directive: str) -> None:
    repo.commit({"ril/mod.py": f"x = 1  {directive}\n"})
    assert "suppression-without-reason" not in repo.rules()


def test_the_word_in_prose_is_not_a_suppression(repo: Repo) -> None:
    repo.commit({"docs/note.md": "the noqa marker is discussed here\n"})
    assert not repo.rules(BLOCKING)


def test_bare_except_and_swallowed_exceptions_block(repo: Repo) -> None:
    body = "\n".join(
        [
            "def f():",
            "    try:",
            "        g()",
            BARE_EXCEPT,
            "        raise",
            "    try:",
            "        g()",
            "    except Exception:",
            "        pass",
            "    try:",
            "        g()",
            "    except BaseException: pass",
            "    with contextlib." + "suppress(" + "Exception):",
            "        g()",
            "",
        ]
    )
    repo.commit({"ril/mod.py": body})
    found = {(f.rule, f.line) for f in repo.findings() if f.severity == BLOCKING}
    assert ("bare-except", 4) in found
    assert ("swallowed-exception", 8) in found
    assert ("swallowed-exception", 12) in found
    assert ("swallowed-exception", 13) in found


def test_specific_or_handled_exceptions_pass(repo: Repo) -> None:
    body = "\n".join(
        [
            "def f():",
            "    try:",
            "        g()",
            "    except ValueError:",
            "        pass",
            "    try:",
            "        g()",
            "    except Exception as exc:",
            "        raise RuntimeError('x') from exc",
            "",
        ]
    )
    repo.commit({"ril/mod.py": body})
    assert not repo.rules(BLOCKING)


# -- blocking: weakened tests --------------------------------------------------------------------

BASE_TEST = (
    "import pytest\n\n\ndef test_a():\n    assert f(1) == 2\n"
    "    assert g() == pytest.approx(0.5, abs=1e-6)\n"
    "    assert len(h()) == 3\n"
)


def test_removed_assert_blocks(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": BASE_TEST})
    repo.branch("b/two")
    repo.commit({"tests/unit/test_a.py": BASE_TEST.replace("    assert f(1) == 2\n", "")})
    assert "assert-removed" in {
        f.rule for f in scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    }


def test_tolerance_widened_blocks(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": BASE_TEST})
    repo.branch("b/two")
    repo.commit({"tests/unit/test_a.py": BASE_TEST.replace("abs=1e-6", "abs=1e-2")})
    rules = {f.rule for f in scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]}
    assert "tolerance-widened" in rules


def test_expected_number_changed_blocks(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": BASE_TEST})
    repo.branch("b/two")
    repo.commit({"tests/unit/test_a.py": BASE_TEST.replace("== 3", "== 4")})
    rules = {f.rule for f in scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]}
    assert "expected-number-changed" in rules


def test_tightened_tolerance_and_added_asserts_pass(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": BASE_TEST})
    repo.branch("b/two")
    edited = BASE_TEST.replace("abs=1e-6", "abs=1e-9") + "    assert h() == [1, 2, 3]\n"
    repo.commit({"tests/unit/test_a.py": edited})
    found = scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    assert not [f for f in found if f.severity == BLOCKING]


def test_assert_moved_within_a_file_passes(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": BASE_TEST})
    repo.branch("b/two")
    moved = BASE_TEST.replace("    assert f(1) == 2\n", "") + "    assert f(1) == 2\n"
    repo.commit({"tests/unit/test_a.py": moved})
    found = scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    assert not [f for f in found if f.severity == BLOCKING]


# -- blocking: ownership, size, files, secrets, paths --------------------------------------------


@pytest.mark.parametrize(
    ("branch", "blocked"), [("a/rq1", True), ("c/eval", True), ("b/lead", False)]
)
def test_frozen_config_only_changes_on_lead_branch(repo: Repo, branch: str, blocked: bool) -> None:
    repo.commit({"configs/frozen/main.yaml": "seed: 0\nfrozen: true\n"})
    assert ("frozen-config" in repo.rules(BLOCKING, branch=branch)) is blocked


def test_large_file_blocks_and_small_file_passes(repo: Repo) -> None:
    repo.commit({"data/big.csv": "a," * (3 * 1024 * 1024), "data/small.csv": "a,b\n"})
    found = [f for f in repo.findings() if f.rule == "large-file"]
    assert [f.path for f in found] == ["data/big.csv"]


@pytest.mark.parametrize(
    "name",
    [
        "model.safetensors",
        "ckpt/best.pt",
        "dump.tar.gz",
        "export.zip",
        ".env",
        "deploy/id_ed25519",
        "k.pem",
    ],
)
def test_forbidden_files_block(repo: Repo, name: str) -> None:
    repo.commit({name: "x\n"})
    assert "forbidden-file" in repo.rules(BLOCKING)


def test_env_example_is_allowed(repo: Repo) -> None:
    repo.commit({".env.example": "KEY=\n"})
    assert "forbidden-file" not in repo.rules()


def test_token_shaped_text_blocks(repo: Repo) -> None:
    repo.commit({"ril/mod.py": f'TOKEN = "{TOKEN}"\n'})
    assert "secret" in repo.rules(BLOCKING)


def test_hash_and_ordinary_text_are_not_tokens(repo: Repo) -> None:
    repo.commit({"docs/a.md": "commit 1453b23d6f0c2a and sk-learn style names\n"})
    assert "secret" not in repo.rules()


def test_home_directory_path_blocks_and_placeholder_passes(repo: Repo) -> None:
    repo.commit({"scripts/run.sh": f"cd {HOME_PATH}\n", "docs/a.md": "see /home/user/data\n"})
    found = [f for f in repo.findings() if f.rule == "home-path"]
    assert [f.path for f in found] == ["scripts/run.sh"]


def test_tree_scan_finds_home_paths_in_every_format_and_file_name(repo: Repo) -> None:
    json_line = '{"result_dir": "/home2/' + "carol" + '/runs/a"}\n'
    repo.commit(
        {
            "results/logs/run.json": json_line,
            "results/tables/t.csv": "path\n/Users/" + "dave" + "/x\n",
            "docs/a.md": "see /home/user/data and /home/<user>/data\n",
            "results/home/" + "erin" + "/note.txt": "ok\n",
        }
    )
    found = scan_tree(Git(repo.root), "HEAD")
    assert {(f.path, f.line) for f in found} == {
        ("results/logs/run.json", 1),
        ("results/tables/t.csv", 2),
    }


def test_tree_scan_cli_exit_code(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.commit({"docs/a.md": "see /home/user/data\n"})
    assert main(["--tree", "--root", str(repo.root)]) == 0
    repo.commit({"docs/b.md": "cd /home/" + "frank" + "/p\n"})
    assert main(["--tree", "--root", str(repo.root)]) == 1
    assert "docs/b.md:1" in capsys.readouterr().out


# -- blocking: the Verified split in tuning configs ----------------------------------------------


def test_verified_in_a_sweep_config_blocks(repo: Repo) -> None:
    cfg = (
        "seed: 0\npurpose: parameter sweep\nfolders:\n- dataset: SWE-bench_Verified\n  role: dev\n"
    )
    repo.commit({"configs/experiments/sweep_a.yaml": cfg})
    assert "verified-in-tuning-config" in repo.rules(BLOCKING)


def test_verified_with_role_test_in_a_dev_config_passes(repo: Repo) -> None:
    cfg = (
        "seed: 0\nfolders:\n- dataset: SWE-bench_Verified\n  role: test\n"
        "- dataset: Pro\n  role: dev\n"
    )
    repo.commit({"configs/experiments/e1_dev.yaml": cfg})
    assert "verified-in-tuning-config" not in repo.rules()


def test_verified_in_a_final_config_passes(repo: Repo) -> None:
    cfg = "seed: 0\npurpose: final evaluation\nfolders:\n- dataset: SWE-bench_Verified\n"
    repo.commit({"configs/experiments/final.yaml": cfg})
    assert "verified-in-tuning-config" not in repo.rules()


# -- blocking: numbers without a source ----------------------------------------------------------


def test_hand_typed_ledger_number_blocks(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER, "results/logs/run.json": '{"ndcg": 41.7}\n'})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("nDCG@10 44.3")})
    assert "unsourced-number" in repo.rules(BLOCKING)


def test_ledger_number_found_in_its_log_passes(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER, "results/logs/run.json": '{"ndcg": 41.7}\n'})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("nDCG@10 41.7")})
    assert "unsourced-number" not in repo.rules()


def test_fraction_in_log_supports_percent_in_ledger(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER, "results/logs/run.json": '{"recall": 0.4172}\n'})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("recall 41.72")})
    assert "unsourced-number" not in repo.rules()


def test_number_present_only_in_another_file_does_not_count(repo: Repo) -> None:
    files: Files = {
        "RESULTS.md": LEDGER_HEADER,
        "results/logs/run.json": '{"ndcg": 41.7}\n',
        "results/logs/other.json": '{"ndcg": 44.3}\n',
    }
    repo.commit(files)
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("nDCG@10 44.3")})
    assert "unsourced-number" in repo.rules(BLOCKING)


def test_ledger_row_naming_no_file_blocks(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("MRR 18.7", log="n/a")})
    assert "unsourced-number" in repo.rules(BLOCKING)


def test_integers_without_separators_and_prose_are_not_traced(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("100 of 100 updates, p50")})
    assert "unsourced-number" not in repo.rules()


def test_result_line_number_is_traced_to_the_section_files(repo: Repo) -> None:
    section = "## E-X: a\n\nTable `results/tables/x.csv`.\n\n"
    repo.commit({"docs/EXPERIMENTS.md": section, "results/tables/x.csv": "m\n12.34\n"})
    repo.commit({"docs/EXPERIMENTS.md": section + "**Result.** 12.34 points and 55.55 points.\n"})
    found = [f for f in repo.findings() if f.rule == "unsourced-number"]
    assert len(found) == 1
    assert "55.55" in found[0].message


def test_numbers_check_can_be_switched_off(repo: Repo) -> None:
    repo.commit({"RESULTS.md": LEDGER_HEADER})
    repo.commit({"RESULTS.md": LEDGER_HEADER + ledger_row("MRR 18.7", log="n/a")})
    assert "unsourced-number" not in repo.rules(numbers=False)


# -- warnings ------------------------------------------------------------------------------------


def test_unfinished_markers_warn(repo: Repo) -> None:
    repo.commit(
        {
            "ril/mod.py": f"# {MARKER}: later\nx = 1  # a {TEMP} measure\n",
            "RESULTS.md": f"{MARKER}\n",
        }
    )
    found = [f for f in repo.findings() if f.rule == "unfinished-marker"]
    assert {(f.path, f.severity) for f in found} == {("ril/mod.py", WARNING)}
    assert len(found) == 2


def test_definition_without_a_test_warns_and_referenced_one_does_not(repo: Repo) -> None:
    repo.commit(
        {
            "ril/mod.py": (
                "def covered():\n    return 1\n\n\ndef bare():\n    return 2\n\n\n"
                "def _private():\n    return 3\n"
            ),
            "tests/unit/test_mod.py": (
                "from ril.mod import covered\n\n\ndef test_it():\n    assert covered() == 1\n"
            ),
        }
    )
    messages = [f.message for f in repo.findings() if f.rule == "untested-definition"]
    assert len(messages) == 1
    assert "bare" in messages[0]


def test_new_config_markers(repo: Repo) -> None:
    repo.commit(
        {
            "configs/experiments/a.yaml": "label: x\n",
            "configs/experiments/b.yaml": "seed: 0\nprovisional: [ADR-001]\n",
        }
    )
    found = {(f.rule, f.path) for f in repo.findings() if f.severity == WARNING}
    assert ("config-no-seed", "configs/experiments/a.yaml") in found
    assert ("config-no-marker", "configs/experiments/a.yaml") in found
    assert not [f for f in found if f[1].endswith("b.yaml")]


def test_changed_default_in_shared_module_warns(repo: Repo) -> None:
    repo.commit({"ril/util/stats.py": "def ci(x, level=0.95, *, draws=2000):\n    return x\n"})
    repo.branch("b/two")
    repo.commit({"ril/util/stats.py": "def ci(x, level=0.90, *, draws=2000):\n    return x\n"})
    found = scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    changed = [f for f in found if f.rule == "changed-default"]
    assert len(changed) == 1
    assert "0.95" in changed[0].message


def test_changed_defaults_helper_ignores_unchanged_and_added_parameters() -> None:
    old = "class A:\n    def f(self, a=1, b=2):\n        pass\n"
    new = "class A:\n    def f(self, a=1, b=3, c=4):\n        pass\n"
    assert changed_defaults(old, new) == [("A.f(b)", 2, "2", "3")]
    assert changed_defaults(old, old) == []
    assert changed_defaults("def f(:", new) == []


def test_changed_default_outside_shared_modules_is_ignored(repo: Repo) -> None:
    repo.commit({"ril/other.py": "def f(a=1):\n    return a\n"})
    repo.branch("b/two")
    repo.commit({"ril/other.py": "def f(a=2):\n    return a\n"})
    found = scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    assert "changed-default" not in {f.rule for f in found}


def test_deleted_test_and_result_files_warn_but_placeholders_do_not(repo: Repo) -> None:
    repo.commit({"tests/unit/test_a.py": "x\n", "results/t.csv": "a\n", "tests/.gitkeep": ""})
    repo.branch("b/two")
    repo.commit({"tests/unit/test_a.py": None, "results/t.csv": None, "tests/.gitkeep": None})
    found = scan(Git(repo.root), "b/feature", "HEAD", "b/two")[0]
    deleted = {f.path for f in found if f.rule == "deleted-file"}
    assert deleted == {"tests/unit/test_a.py", "results/t.csv"}


REGISTRY_HEAD = (
    "| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |\n"
    "|---|---|---|---|---|---|---|\n"
)


def test_done_registry_row_without_output_warns(repo: Repo) -> None:
    repo.commit({"docs/EXPERIMENTS.md": REGISTRY_HEAD})
    row = "| E-FOO | RQ1 | a | b | 0 | c | done 2026-01-01 |\n"
    repo.commit({"docs/EXPERIMENTS.md": REGISTRY_HEAD + row})
    assert "done-without-output" in repo.rules(WARNING)


def test_done_registry_row_with_a_section_path_passes(repo: Repo) -> None:
    repo.commit({"docs/EXPERIMENTS.md": REGISTRY_HEAD})
    row = "| E-FOO | RQ1 | a | b | 0 | c | done 2026-01-01 |\n"
    section = "\n## E-FOO: foo\n\nTable `results/tables/foo.csv`.\n"
    repo.commit({"docs/EXPERIMENTS.md": REGISTRY_HEAD + row + section})
    assert "done-without-output" not in repo.rules()


# -- the planted branch, end to end --------------------------------------------------------------


def test_a_branch_with_every_planted_problem_is_caught_and_a_clean_one_is_not(
    repo: Repo, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.commit(
        {
            "tests/unit/test_a.py": BASE_TEST,
            "RESULTS.md": LEDGER_HEADER,
            "results/logs/run.json": '{"ndcg": 41.7}\n',
        }
    )
    repo.branch("a/bad")
    bad_test = (
        BASE_TEST.replace("abs=1e-6", "abs=1e-2") + f"\n\n{SKIP}\ndef test_late():\n    pass\n"
    )
    repo.commit(
        {
            "tests/unit/test_a.py": bad_test,
            "ril/mod.py": f"x = 1  {NOQA}\n",
            "RESULTS.md": LEDGER_HEADER + ledger_row("nDCG@10 44.3"),
            "data/big.bin": b"0" * (6 * 1024 * 1024),
            "scripts/run.sh": f"cd {HOME_PATH}\n",
            "configs/frozen/main.yaml": "seed: 0\nfrozen: true\n",
        }
    )
    rules = {
        f.rule
        for f in scan(Git(repo.root), "b/feature", "HEAD", "a/bad")[0]
        if f.severity == BLOCKING
    }
    assert {
        "test-skip",
        "tolerance-widened",
        "suppression-without-reason",
        "unsourced-number",
        "large-file",
        "home-path",
        "frozen-config",
        "forbidden-file",
    } <= rules
    assert (
        main(["--root", str(repo.root), "--base", "main", "--head", "HEAD", "--branch", "a/bad"])
        == 1
    )
    assert "BLOCKING" in capsys.readouterr().out

    repo.run("switch", "-q", "-c", "b/clean", "main")
    repo.commit({"docs/note.md": "an ordinary note\n"})
    assert (
        main(["--root", str(repo.root), "--base", "main", "--head", "HEAD", "--branch", "b/clean"])
        == 0
    )


def test_unknown_revision_exits_with_two(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo.root), "--base", "no-such-ref"]) == 2
    assert "review_flags" in capsys.readouterr().err


def test_row_appended_below_another_table_is_still_traced(repo: Repo) -> None:
    anchors = "\n## Anchors\n\n| source | quantity | value |\n|---|---|---|\n| a | b | 1.5 |\n"
    repo.commit({"RESULTS.md": LEDGER_HEADER + anchors})
    repo.commit({"RESULTS.md": LEDGER_HEADER + anchors + ledger_row("MRR 63.47")})
    assert "unsourced-number" in repo.rules(BLOCKING)


def test_shared_paths_are_the_util_config_metrics_and_statistics_modules() -> None:
    assert is_shared_path("ril/util/seed.py")
    assert is_shared_path("ril/config/parameters.py")
    assert is_shared_path("ril/evaluation/metrics.py")
    assert is_shared_path("ril/analysis/stats_tables.py")
    assert not is_shared_path("ril/retrieval/bm25_index.py")
    assert not is_shared_path("tests/unit/test_seed.py")


def test_branch_name_prefers_the_ci_environment(
    repo: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    assert branch_name(Git(repo.root)) == "b/feature"
    monkeypatch.setenv("GITHUB_REF_NAME", "a/from-ci")
    assert branch_name(Git(repo.root)) == "a/from-ci"
    monkeypatch.setenv("GITHUB_HEAD_REF", "c/pr-branch")
    assert branch_name(Git(repo.root)) == "c/pr-branch"


def test_scan_record_types_and_errors(repo: Repo) -> None:
    with pytest.raises(GitError):
        Git(repo.root).resolve("no-such-ref")
    git = Git(repo.root)
    head = git.resolve("HEAD")
    fd = FileDiff(path="a.py", hunks=[Hunk(old_start=1, new_start=1, added=[(1, "x")])])
    scanner = Scan(
        git=git, base=head, head=head, branch="b/x", root_rev=head, files=[fd], numbers=False
    )
    scanner.scan_added_lines()
    assert scanner.findings == []
    assert fd.added == [(1, "x")]
