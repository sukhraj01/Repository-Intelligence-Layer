"""Reproducibility: one checkout builds byte-identical units and graph (specs/parse_one_repo.md)."""

import os
import subprocess
import sys
from pathlib import Path

from ril.parsing.build import BuildConfig, build_repository, write_artifacts


def test_two_builds_write_identical_bytes(mini_repo: Path, tmp_path: Path) -> None:
    cfg = BuildConfig(repo_id="acme/mini", with_history=False, seed=0)
    first = write_artifacts(build_repository(str(mini_repo), cfg), str(tmp_path / "a"))
    second = write_artifacts(build_repository(str(mini_repo), cfg), str(tmp_path / "b"))
    assert first == second
    for name in first:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_digest_does_not_depend_on_hash_randomization(mini_repo: Path, tmp_path: Path) -> None:
    code = (
        "import sys\n"
        "from ril.parsing.build import BuildConfig, build_repository\n"
        "r = build_repository(sys.argv[1], BuildConfig(repo_id='acme/mini', with_history=False))\n"
        "sys.stdout.write(r.graph.digest())\n"
    )
    digests = set()
    for seed in ("1", "2", "random"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(
            [sys.executable, "-I", "-c", code, str(mini_repo)],
            capture_output=True,
            text=True,
            check=True,
            env=env,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        digests.add(out.stdout)
    assert len(digests) == 1
