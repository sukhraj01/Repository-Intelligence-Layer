"""Context assembly: budget, order, skipping, truncation, determinism, manifest."""

from __future__ import annotations

import random
import re

import pytest

from ril.assembly.assemble import (
    HEADER_PREFIX,
    SEPARATOR,
    Candidate,
    UnitText,
    assemble,
    block_header,
    snapshot_of,
    truncate_text,
)
from ril.assembly.config import MIN_MAX_UNIT_TOKENS, AssemblyConfig
from ril.assembly.gold import gold_in_context
from ril.assembly.tokens import ApproxTokenizer

TOK = ApproxTokenizer()


def unit(i: int, file: str = "pkg/a.py", n_lines: int = 3, start: int | None = None) -> UnitText:
    s = start if start is not None else 10 * i + 1
    body = "\n".join(f"    value_{i}_{j} = {j}" for j in range(n_lines))
    return UnitText(
        unit_id=f"{file}::f{i}",
        file=file,
        start_line=s,
        end_line=s + n_lines,
        unit_type="function",
        qualified_name=f"f{i}",
        source=f"def f{i}():\n{body}",
    )


def cands(units: list[UnitText]) -> list[Candidate]:
    return [Candidate(u.unit_id, 1.0 / (r + 1), ("bm25",)) for r, u in enumerate(units)]


def test_includes_in_rank_order_then_orders_by_file_and_line() -> None:
    a = unit(1, "z.py", start=5)
    b = unit(2, "a.py", start=40)
    c = unit(3, "a.py", start=2)
    snap = snapshot_of([a, b, c])
    out = assemble(cands([a, b, c]), snap, AssemblyConfig(budget=2000), TOK)
    assert [e.unit_id for e in out.manifest.entries] == [c.unit_id, b.unit_id, a.unit_id]
    assert [e.rank for e in out.manifest.entries] == [3, 2, 1]
    heads = [ln for ln in out.context.split("\n") if ln.startswith(HEADER_PREFIX)]
    assert heads == [block_header(c, 3), block_header(b, 2), block_header(a, 1)]


def test_skips_a_unit_that_does_not_fit_and_continues() -> None:
    small1 = unit(1, n_lines=2)
    big = unit(2, n_lines=200)
    small2 = unit(3, n_lines=2)
    snap = snapshot_of([small1, big, small2])
    budget = 3 * TOK.count(small1.source) + 60
    out = assemble(
        cands([small1, big, small2]),
        snap,
        AssemblyConfig(budget=budget, max_unit_tokens=2000),
        TOK,
    )
    assert out.manifest.unit_ids() == [small1.unit_id, small2.unit_id]
    skipped = {s.unit_id: s for s in out.manifest.skipped}
    assert skipped[big.unit_id].reason == "does_not_fit"
    assert skipped[big.unit_id].rank == 2
    assert skipped[big.unit_id].tokens_needed > budget - out.manifest.total_tokens


def test_duplicates_unknown_and_empty_are_skipped_with_reasons() -> None:
    a = unit(1)
    blank = UnitText("x.py::blank", "x.py", 1, 1, "function", "blank", "  \n ")
    snap = snapshot_of([a, blank])
    lst = [
        Candidate(a.unit_id, 3.0),
        Candidate(a.unit_id, 2.0),
        Candidate("nope::g", 1.5),
        Candidate(blank.unit_id, 1.0),
    ]
    out = assemble(lst, snap, AssemblyConfig(budget=1000), TOK)
    assert out.manifest.unit_ids() == [a.unit_id]
    assert [(s.rank, s.reason) for s in out.manifest.skipped] == [
        (2, "duplicate"),
        (3, "unknown_unit"),
        (4, "empty_text"),
    ]


def test_snapshot_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError):
        snapshot_of([unit(1), unit(1)])


def test_truncation_boundary_and_marker() -> None:
    text = "\n".join(f"x{i} = {i}" for i in range(100))
    full = TOK.count(text)
    same, cut = truncate_text(text, full, TOK)
    assert (same, cut) == (text, False)
    out, cut = truncate_text(text, full - 1, TOK)
    assert cut and TOK.count(out) <= full - 1
    kept = out.split("\n")[:-1]
    assert kept == text.split("\n")[: len(kept)]
    assert out.endswith("more lines")
    left = int(re.search(r"truncated, (\d+) more lines", out).group(1))  # type: ignore[union-attr]
    assert left == 100 - len(kept)
    # one more kept line would not fit
    longer = "\n".join(
        text.split("\n")[: len(kept) + 1] + [f"# ... truncated, {left - 1} more lines"]
    )
    assert TOK.count(longer) > full - 1


def test_truncation_cuts_a_single_long_line_by_characters() -> None:
    text = "x = " + " + ".join(f"name{i}" for i in range(500)) + "\ny = 1"
    out, cut = truncate_text(text, 40, TOK)
    assert cut and TOK.count(out) <= 40
    assert out.split("\n")[-1].startswith("# ... truncated, 1 more lines")


def test_unit_cap_marks_the_entry_truncated() -> None:
    big = unit(1, n_lines=300)
    out = assemble(
        cands([big]), snapshot_of([big]), AssemblyConfig(budget=5000, max_unit_tokens=100), TOK
    )
    (entry,) = out.manifest.entries
    assert entry.truncated
    body = out.context.split("\n", 1)[1]
    assert TOK.count(body) <= 100


def test_budget_smaller_than_any_block_gives_empty_context() -> None:
    a = unit(1)
    out = assemble(cands([a]), snapshot_of([a]), AssemblyConfig(budget=5), TOK)
    assert out.context == "" and out.manifest.total_tokens == 0 and out.manifest.entries == ()
    assert out.manifest.skipped[0].reason == "does_not_fit"


def test_manifest_matches_string() -> None:
    rng = random.Random(3)
    units = [
        unit(i, f"d{rng.randint(0, 3)}/m{rng.randint(0, 3)}.py", rng.randint(1, 40))
        for i in range(30)
    ]
    units = list({u.unit_id: u for u in units}.values())
    out = assemble(cands(units), snapshot_of(units), AssemblyConfig(budget=1200), TOK)
    blocks = out.context.split(SEPARATOR)
    assert len(blocks) == len(out.manifest.entries)
    for block, e in zip(blocks, out.manifest.entries, strict=True):
        head = block.split("\n", 1)[0]
        assert head.startswith(f"{HEADER_PREFIX}{e.file}:{e.start_line}-{e.end_line} ")
        assert head.endswith(f"(rank {e.rank})")
        assert TOK.count(block) == e.tokens
    assert TOK.count(out.context) == out.manifest.total_tokens
    import hashlib

    assert hashlib.sha256(out.context.encode()).hexdigest() == out.manifest.context_sha256


def test_deterministic_bytes() -> None:
    rng = random.Random(5)
    units = [unit(i, f"f{i % 4}.py", rng.randint(1, 30)) for i in range(40)]
    snap = snapshot_of(units)
    lst = cands(units)
    first = assemble(lst, snap, AssemblyConfig(budget=900), TOK)
    second = assemble(list(lst), dict(snap), AssemblyConfig(budget=900), TOK)
    assert first.context == second.context
    assert first.manifest.to_json() == second.manifest.to_json()


def test_unit_cap_below_floor_is_rejected() -> None:
    with pytest.raises(ValueError):
        AssemblyConfig(budget=100, max_unit_tokens=MIN_MAX_UNIT_TOKENS - 1)
    with pytest.raises(ValueError):
        AssemblyConfig(budget=0)


def test_stages_are_kept_and_do_not_change_the_text() -> None:
    a, b = unit(1), unit(2)
    snap = snapshot_of([a, b])
    plain = assemble(
        [Candidate(a.unit_id, 2.0), Candidate(b.unit_id, 1.0)],
        snap,
        AssemblyConfig(budget=900),
        TOK,
    )
    tagged = assemble(
        [Candidate(a.unit_id, 9.0, ("bm25", "dense")), Candidate(b.unit_id, 0.1, ("dense",))],
        snap,
        AssemblyConfig(budget=900),
        TOK,
    )
    assert plain.context == tagged.context
    assert tagged.manifest.entries[0].stages == ("bm25", "dense")


class _Lumpy:
    """Counts tokens non-additively: a long text costs extra (BPE merges across a boundary)."""

    name = "lumpy"

    def count(self, text: str) -> int:
        return TOK.count(text) + len(text) // 300


def test_final_check_drops_worst_ranked_when_counting_is_not_additive() -> None:
    units = [unit(i, "a.py", 6) for i in range(12)]
    snap = snapshot_of(units)
    tok = _Lumpy()
    # fill the budget exactly under additive counting; blocks are under 300 characters, so the
    # lumpy per-block counts equal the additive ones and only the joined string costs more
    additive = assemble(cands(units), snap, AssemblyConfig(budget=600), TOK).manifest.total_tokens
    budget = additive + TOK.count(SEPARATOR)  # the accounting charges one separator per block
    assert all(len(unit_block) < 300 for unit_block in (u.source for u in units))
    out = assemble(cands(units), snap, AssemblyConfig(budget=budget), tok)
    assert tok.count(out.context) <= budget
    assert out.manifest.total_tokens == tok.count(out.context)
    dropped = [s for s in out.manifest.skipped if s.reason == "final_check"]
    assert dropped, "this fixture must trigger the final check"
    kept_ranks = [e.rank for e in out.manifest.entries]
    assert max(kept_ranks) < min(s.rank for s in dropped)


@pytest.mark.parametrize("seed", range(25))
def test_properties_on_random_inputs(seed: int) -> None:
    rng = random.Random(seed)
    n = rng.randint(0, 60)
    units = [
        unit(
            i,
            f"p{rng.randint(0, 5)}/m{rng.randint(0, 4)}.py",
            rng.randint(0, 80),
            start=rng.randint(1, 500),
        )
        for i in range(n)
    ]
    snap = snapshot_of(units)
    ids = [u.unit_id for u in units] + ["ghost::x"] * rng.randint(0, 3)
    lst = (
        [Candidate(rng.choice(ids), rng.random()) for _ in range(rng.randint(0, 90))] if ids else []
    )
    budget = rng.choice([40, 200, 1000, 4000])
    cap = rng.choice([MIN_MAX_UNIT_TOKENS, 60, 300, 1000])
    cfg = AssemblyConfig(budget=budget, max_unit_tokens=cap)
    out = assemble(lst, snap, cfg, TOK)
    m = out.manifest
    assert TOK.count(out.context) <= budget
    assert m.total_tokens == TOK.count(out.context) <= budget
    ids_in = m.unit_ids()
    assert len(ids_in) == len(set(ids_in))
    keys = [(e.file, e.start_line, e.end_line, e.unit_id) for e in m.entries]
    assert keys == sorted(keys)
    assert len(m.entries) + len(m.skipped) == len(lst)
    assert {s.reason for s in m.skipped} <= {
        "duplicate",
        "unknown_unit",
        "empty_text",
        "does_not_fit",
    }
    for e in m.entries:
        assert e.tokens <= budget
    for s in m.skipped:
        if s.reason == "does_not_fit":
            assert s.tokens_needed > 0
    # a rerun on the same input gives the same bytes
    again = assemble(lst, snap, cfg, TOK)
    assert again.context == out.context and again.manifest.to_json() == m.to_json()


def test_a_candidate_ranked_earlier_is_never_displaced_by_a_later_one() -> None:
    """First-fit: dropping the last candidate never changes what the earlier ones got."""
    rng = random.Random(11)
    units = [unit(i, f"f{i % 3}.py", rng.randint(1, 60)) for i in range(25)]
    snap = snapshot_of(units)
    cfg = AssemblyConfig(budget=700)
    full = assemble(cands(units), snap, cfg, TOK)
    prefix = assemble(cands(units[:-1]), snap, cfg, TOK)
    got_full = {e.unit_id for e in full.manifest.entries} - {units[-1].unit_id}
    got_prefix = {e.unit_id for e in prefix.manifest.entries}
    assert got_full == got_prefix


def test_gold_in_context_counts_units_files_and_truncation() -> None:
    a = unit(1, "a.py", n_lines=2)
    b = unit(2, "b.py", n_lines=400)
    c = unit(3, "c.py", n_lines=2)
    snap = snapshot_of([a, b, c])
    out = assemble(cands([a, b, c]), snap, AssemblyConfig(budget=3000, max_unit_tokens=100), TOK)
    g = gold_in_context(out.manifest, [a.unit_id, b.unit_id, "ghost::z"], ["a.py", "b.py", "z.py"])
    assert (g.n_units, g.units_in, g.units_intact) == (3, 2, 1)
    assert (g.n_files, g.files_in) == (3, 2)
    assert g.unit_share == pytest.approx(2 / 3) and g.file_share == pytest.approx(2 / 3)
    assert not g.no_gold_file
    none = gold_in_context(out.manifest, ["ghost::z"], ["z.py"])
    assert none.no_gold_file and none.units_in == 0
    empty = gold_in_context(out.manifest, [], [])
    assert not empty.no_gold_file and empty.unit_share != empty.unit_share  # nan
