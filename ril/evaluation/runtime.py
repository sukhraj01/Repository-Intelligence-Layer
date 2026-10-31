"""Explicit Slurm and Colab execution admission without importing a model runtime.

The Colab host kernel issues a current-VM receipt before a separate project interpreter runs.
Re-probing that host avoids treating an environment flag as sufficient admission. These checks
are operational guards for an owned notebook, not security attestation against its operator.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

VERSION = "execution-runtime/v1"
CONTENT_ROOT = Path("/content")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
Record = dict[str, Any]

# Runs in Colab's original interpreter, never the project's isolated Python environment.
_PROBE = r"""
import importlib, json, pathlib, subprocess, sys
module = importlib.import_module("google.colab")
root = pathlib.Path("/content")
if not root.is_dir() or not module.__file__:
    raise SystemExit("a Colab host kernel is required")
gpus = []
try:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        gpus = [line.strip() for line in result.stdout.splitlines() if line.strip()]
except (OSError, subprocess.TimeoutExpired):
    pass
# Driver failure must not turn an attached GPU into a CPU-only admission.
driver = pathlib.Path("/proc/driver/nvidia/gpus")
if not gpus and driver.is_dir() and any(driver.iterdir()):
    gpus = ["NVIDIA device attached; driver inventory unavailable"]
print(json.dumps({
    "boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "host_python": str(pathlib.Path(sys.executable).resolve()),
    "colab_module": str(pathlib.Path(module.__file__).resolve()),
    "gpus": gpus,
}, sort_keys=True))
"""


def _probe_colab(host_python: str) -> Record:
    """Inspect only safe hardware/runtime fields; never emit an environment dump."""
    path = Path(host_python)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("the Colab host interpreter is unavailable")
    try:
        result = subprocess.run(
            [str(path), "-I", "-c", _PROBE],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        if len(result.stdout) > 16384:
            raise ValueError("oversized runtime proof")
        proof = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError("Colab host verification failed; rerun the notebook setup cell") from exc
    keys = {"boot_id", "host_python", "colab_module", "gpus"}
    if (
        not isinstance(proof, dict)
        or set(proof) != keys
        or any(not isinstance(proof[k], str) or not proof[k] for k in keys - {"gpus"})
        or not isinstance(proof["gpus"], list)
        or any(not isinstance(gpu, str) or not gpu or len(gpu) > 512 for gpu in proof["gpus"])
        or len(proof["gpus"]) > 16
    ):
        raise RuntimeError("invalid Colab host verification")
    return proof


def issue_colab_receipt(path: str | Path) -> Record:
    """Call from the original Colab kernel after extraction, before project installation.

    Pass RIL_RUNTIME=colab and RIL_COLAB_RECEIPT=<path> to project subprocesses. Reissue after
    runtime restart or switching accelerator. The receipt intentionally contains no credentials.
    """
    if not CONTENT_ROOT.is_dir():
        raise RuntimeError("a Colab host kernel is required to issue a runtime receipt")
    target = Path(path)
    if not target.is_absolute() or not target.resolve().is_relative_to(CONTENT_ROOT.resolve()):
        raise ValueError("Colab runtime receipts must be stored beneath /content")
    proof = _probe_colab(str(Path(sys.executable).resolve()))
    if proof["boot_id"] != BOOT_ID.read_text().strip():
        raise RuntimeError("Colab host and project VM identities differ")
    value = {"version": VERSION, "runtime": "colab", "proof": proof}
    target.parent.mkdir(parents=True, exist_ok=True)
    # Receipt admission rechecks the host; an interrupted write safely fails and is reissued.
    target.write_text(json.dumps(value, sort_keys=True) + "\n")
    return value


def _slurm_gpus(env: Mapping[str, str]) -> bool:
    # SLURM_JOB_GPUS=0 denotes device index zero, not a zero-device allocation.
    return bool(env.get("SLURM_JOB_GPUS")) or any(
        env.get(key, "") not in {"", "0"} for key in ("SLURM_GPUS_ON_NODE", "SLURM_GPUS")
    )


def require_runtime(
    *,
    cpu_only: bool = True,
    require_gpu: bool = False,
    environ: Mapping[str, str] | None = None,
) -> Record:
    """Admit a selected execution runtime before network or model imports occur."""
    if cpu_only and require_gpu:
        raise ValueError("CPU-only and required-GPU modes are mutually exclusive")
    env = os.environ if environ is None else environ
    mode = env.get("RIL_RUNTIME", "slurm")
    if mode == "slurm":
        job = env.get("SLURM_JOB_ID", "")
        if env.get("RIL_CLUSTER") != "1" or not job.isdecimal() or int(job) < 1:
            raise RuntimeError("execution requires a verified Slurm cluster job or Colab receipt")
        gpus = _slurm_gpus(env)
        if cpu_only and gpus:
            raise RuntimeError("data acquisition requires a CPU-only allocation")
        if require_gpu and not gpus:
            raise RuntimeError("encoding requires a verified Slurm GPU allocation")
        return {"runtime": "slurm", "job_id": job, "gpu_allocated": gpus}
    if mode != "colab":
        raise RuntimeError("runtime must be explicitly admitted as slurm or colab")
    if env.get("SLURM_JOB_ID") or env.get("RIL_CLUSTER"):
        raise RuntimeError("Colab admission must not spoof Slurm identifiers or cluster flags")
    raw = env.get("RIL_COLAB_RECEIPT", "")
    path = Path(raw)
    if (
        not raw
        or not path.is_absolute()
        or not CONTENT_ROOT.is_dir()
        or not path.resolve().is_relative_to(CONTENT_ROOT.resolve())
        or not path.is_file()
        or path.stat().st_size > 16384
    ):
        raise RuntimeError("a current Colab host runtime receipt is required")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RuntimeError("invalid Colab runtime receipt; rerun setup") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "runtime", "proof"}
        or value.get("version") != VERSION
        or value.get("runtime") != "colab"
        or not isinstance(value.get("proof"), dict)
    ):
        raise RuntimeError("invalid Colab runtime receipt identity")
    proof = value["proof"]
    if proof.get("boot_id") != BOOT_ID.read_text().strip():
        raise RuntimeError("Colab VM changed; rerun the notebook setup cell")
    host = proof.get("host_python")
    if not isinstance(host, str) or _probe_colab(host) != proof:
        raise RuntimeError("Colab host or accelerator changed; rerun the notebook setup cell")
    gpus = bool(proof["gpus"])
    if cpu_only and gpus:
        raise RuntimeError("switch Colab to a CPU runtime before data or model acquisition")
    if require_gpu and not gpus:
        raise RuntimeError("switch Colab to an NVIDIA GPU runtime before encoding")
    return {"runtime": "colab", "proof": proof, "gpu_allocated": gpus}


def runtime_record() -> Record:
    """Safe hardware/proof provenance for one admitted execution attempt, without model imports."""
    admitted = require_runtime(cpu_only=False)
    proof = admitted.get("proof")
    return {
        "version": VERSION,
        **admitted,
        "proof_sha256": hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "cpu_cores": os.cpu_count(),
        "host_alias": "colab" if admitted["runtime"] == "colab" else "slurm",
    }
