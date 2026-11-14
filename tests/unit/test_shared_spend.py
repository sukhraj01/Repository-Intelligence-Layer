"""Shared total spend guard and the unusable-share stop (D167): no job can exceed the total."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Any

import pytest

from ril.agent.providers.driver import DriverConfig, StoredReplies, drive
from ril.agent.providers.gemini import CallResult
from ril.agent.providers.spend import (
    GuardedClient,
    Price,
    SharedSpend,
    SpendCapReached,
    SpendGuard,
)
from tests.unit.test_rq3_driver import Exec, reader_for, reply, result

PRICE = Price("m", 1.0, 1.0, False, "d")
CONTENTS = [{"role": "user", "parts": [{"text": "x" * 3000}]}]  # worst case 4096 + 1000 tokens


class FixedClient:
    def __init__(self, tokens_in: int = 1000, tokens_out: int = 100, fail: bool = False) -> None:
        self.tin, self.tout, self.fail = tokens_in, tokens_out, fail

    def generate(self, contents: Any, *, wait_for_daily: bool = False) -> CallResult:
        if self.fail:
            raise RuntimeError("provider fault")
        return CallResult(
            text="t",
            finish_reason="STOP",
            input_tokens=self.tin,
            output_tokens=self.tout,
            thought_tokens=0,
            status=200,
            retries=0,
            n_429=0,
            n_5xx=0,
            latency_s=0.0,
            error=None,
            request_sha256="",
        )


def _worker(args: tuple[str, str, int]) -> int:
    path, owner, n = args
    guard = SpendGuard(100.0, PRICE, 4096, shared=SharedSpend(path, owner, 0.5))
    client = GuardedClient(FixedClient(), guard)
    ok = 0
    for _ in range(n):
        try:
            client.generate(CONTENTS)
            ok += 1
        except SpendCapReached:
            break
    return ok


def test_processes_together_never_pass_the_shared_cap(tmp_path: Path) -> None:
    path = str(tmp_path / "ledger.json")
    SharedSpend(path, "init", 0.5)
    with mp.get_context("fork").Pool(4) as pool:
        counts = pool.map(_worker, [(path, f"arm{k}", 200) for k in range(4)])
    snap = SharedSpend(path, "reader").snapshot()
    assert snap["committed"] <= 0.5 + 1e-9
    assert snap["reserved"] == {}
    billed_each = PRICE.cost(1000, 100)
    assert snap["committed"] == pytest.approx(sum(counts) * billed_each)
    assert sum(counts) >= 1


def test_a_failed_call_releases_its_reservation(tmp_path: Path) -> None:
    led = SharedSpend(tmp_path / "l.json", "a", 1.0)
    client = GuardedClient(FixedClient(fail=True), SpendGuard(10.0, PRICE, 4096, shared=led))
    with pytest.raises(RuntimeError):
        client.generate(CONTENTS)
    snap = led.snapshot()
    assert snap["reserved"] == {} and snap["committed"] == 0.0


def test_the_cap_is_fixed_by_the_first_job(tmp_path: Path) -> None:
    SharedSpend(tmp_path / "l.json", "a", 1.0)
    with pytest.raises(ValueError):
        SharedSpend(tmp_path / "l.json", "b", 2.0)
    with pytest.raises(ValueError):
        SharedSpend(tmp_path / "new.json", "a", None)
    SharedSpend(tmp_path / "l.json", "b", 1.0)  # same cap: fine


def test_a_restart_clears_its_own_reservation_only(tmp_path: Path) -> None:
    a = SharedSpend(tmp_path / "l.json", "a", 1.0)
    b = SharedSpend(tmp_path / "l.json", "b", 1.0)
    a.reserve(0.1)
    b.reserve(0.2)
    SharedSpend(tmp_path / "l.json", "a", 1.0)
    assert b.snapshot()["reserved"] == {"b": pytest.approx(0.2)}


def test_the_run_stops_when_more_than_a_tenth_of_replies_is_unusable(tmp_path: Path) -> None:
    n = 120
    its = [
        {"instance_id": f"i{k}", "arm": "a", "paths": None, "template_version": "t"}
        for k in range(n)
    ]
    good, bad = reply("y = 2", "y = 3"), "no edit block here"
    src = StoredReplies({(f"i{k}", "a", 0): (bad if k % 5 == 0 else good) for k in range(n)})
    cfg = DriverConfig("m", mode="replay", max_unusable_share=0.10, unusable_min_units=50)
    s = drive(its, tmp_path / "o", src, Exec(result()), reader_for, cfg)
    assert s.stopped == "unusable_share" and s.written < n
    ok = StoredReplies({(f"i{k}", "a", 0): (bad if k % 20 == 0 else good) for k in range(n)})
    s2 = drive(its, tmp_path / "o2", ok, Exec(result()), reader_for, cfg)
    assert s2.stopped == "complete" and s2.written == n


def test_every_arm_has_the_selected_configuration_hash() -> None:
    """The pinned configuration of the model check (hash 0fe87a17bf1b...) is reproduced by the
    driver's hash input for any arm, because the arm field is the fixed comparator name."""
    import importlib.util

    from ril.agent.providers.model_check import run_config_sha256
    from ril.agent.providers.patch_format import TEMPLATE_VERSION

    script = Path(__file__).resolve().parents[2] / "scripts" / "rq3_driver.py"
    spec = importlib.util.spec_from_file_location("rq3_driver_hash", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "temperature": 0.0,
        "thinking": {"thinkingLevel": "low"},
        "max_output_tokens": 4096,
        "max_reasks": 2,
        "template_version": TEMPLATE_VERSION,
        "arm": mod.CONFIG_HASH_ARM,
    }
    assert run_config_sha256(cfg).startswith("0fe87a17bf1b41873ebedb03c09adcab")
