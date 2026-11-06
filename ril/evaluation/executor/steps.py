"""Run one shell step with a timeout, a process-group kill and the child's peak memory.

Implements ``docs/RQ3_PILOT.md`` ("If measured on the cluster, the steps"). The peak is the
largest resident size of the step's process tree as reported by ``wait4`` (the maximum over the
terminated, waited-for descendants), not a sampled value.
"""

from __future__ import annotations

import os
import resource
import signal
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

POLL_SECONDS = 0.05
TAIL_BYTES = 4000


@dataclass(frozen=True)
class StepResult:
    """Outcome of one step; ``output`` is the whole combined output (the caller trims it)."""

    exit_code: int
    seconds: float
    peak_rss_mb: float
    timed_out: bool
    output: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _rss_to_mb(ru_maxrss: int) -> float:
    """``ru_maxrss`` is bytes on macOS and kilobytes on Linux."""
    return ru_maxrss / (1024 * 1024) if sys.platform == "darwin" else ru_maxrss / 1024


def run_step(
    command: str,
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
    timeout: float,
) -> StepResult:
    """Run ``command`` under ``bash -c``; kill its process group at ``timeout`` seconds."""
    start = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as sink:
        proc = subprocess.Popen(
            ["bash", "-c", command],
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        timed_out = False
        status = 0
        peak = 0.0
        while True:
            pid, raw, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                status = raw
                peak = _rss_to_mb(usage.ru_maxrss)
                break
            if time.monotonic() - start > timeout and not timed_out:
                timed_out = True
                _kill_group(proc.pid)
            time.sleep(POLL_SECONDS)
        # Popen has not reaped the child: mark it done so its destructor does not warn.
        proc.returncode = os.waitstatus_to_exitcode(status)
    # stragglers of the step's process group (daemons the tests started) do not outlive it
    _kill_group(proc.pid)
    output = log_path.read_bytes().decode("utf-8", "replace")
    return StepResult(
        exit_code=124 if timed_out else proc.returncode,
        seconds=round(time.monotonic() - start, 3),
        peak_rss_mb=round(peak, 1),
        timed_out=timed_out,
        output=output,
    )


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


def self_peak_rss_mb() -> float:
    """Peak resident size of this process, for job-level records."""
    return round(_rss_to_mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), 1)
