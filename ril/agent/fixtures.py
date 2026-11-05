"""Twenty deliberately simple development fixtures, never benchmark instances."""

from __future__ import annotations

from dataclasses import dataclass

from ril.agent.contracts import Task


@dataclass(frozen=True)
class Fixture:
    task: Task
    gold_files: tuple[str, ...]
    test_source: str
    reference_edits: tuple[tuple[str, str, str], ...]


def make_fixtures(n: int = 20) -> list[Fixture]:
    if type(n) is not int or not 1 <= n <= 20:
        raise ValueError("fixture pilot size must be between 1 and 20")
    out: list[Fixture] = []
    for i in range(n):
        kind, offset = i % 5, i + 2
        target = f"module_{i}.py"
        function = f"transform_{i}"
        source = f"def {function}(value):\n    return value - {offset}\n"
        decoy = f"def unrelated(value):\n    return value - {offset}\n"
        if kind == 0:
            issue = f"In {target}, add {offset} to the input instead of subtracting."
        elif kind in (1, 2):
            issue = f"{function} must add {offset} to the value; it currently subtracts it."
        elif kind == 3:
            issue = "The value adjustment must add its configured amount rather than subtract."
            decoy = "# value adjustment configured amount subtract add\n" + decoy
        else:
            issue = f"{function} must multiply its input by {offset}."
        operator = "*" if kind == 4 else "+"
        tests = (
            "import importlib.util\nimport unittest\nfrom pathlib import Path\n"
            f"spec = importlib.util.spec_from_file_location('subject', Path({target!r}))\n"
            "subject = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(subject)\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_fail_to_pass(self):\n"
            f"        self.assertEqual(subject.{function}(7), 7 {operator} {offset})\n"
            "    def test_pass_to_pass(self):\n"
            f"        self.assertIsInstance(subject.{function}(7), int)\n"
            "unittest.main()\n"
        )
        out.append(
            Fixture(
                Task(
                    f"fixture-{i:03d}",
                    f"fixture/dev-{i // 5}",
                    issue,
                    {"decoy.py": decoy, target: source},
                ),
                (target,),
                tests,
                ((target, f"return value - {offset}", f"return value {operator} {offset}"),),
            )
        )
    return out
