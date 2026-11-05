"""Create deterministic, explicitly synthetic API recordings for the pilot plumbing."""

from __future__ import annotations

from typing import Any

from ril.data_mining.github import ISSUE_QUERY, digest, search_path


def synthetic_recording(repositories: int = 200, prs_per_repo: int = 10) -> dict[str, Any]:
    """A generated recording, never an observation about GitHub or scientific yield."""
    query = "language:Python archived:false fork:false stars:>=100 pushed:<=2026-10-30"
    config = {
        "repositories": repositories,
        "pull_requests": 2000,
        "repository_query": query,
        "seed": 0,
        "provisional": "ADR-001; D1 current names; D3 Loc-Bench on",
    }
    core, loc = "held/core", "held/localization"
    names = [core, "renamed/core-copy", loc][: min(3, repositories)]
    names.extend(f"synthetic/package-{i:03d}" for i in range(repositories - len(names)))
    document: dict[str, Any] = {
        "source_kind": "synthetic_recorded_responses",
        "config": config,
        "held_out": {
            "schema_version": 2,
            "repos": {core: []},
            "tiers": {"loc_bench": {"repos": {loc: []}}},
            "aliases": {},
        },
        "responses": {},
        "snapshots": {},
    }

    def add(
        path: str,
        data: Any,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        key = digest(["POST" if body else "GET", url, body])
        document["responses"][key] = [{"status": 200, "data": data, "headers": headers or {}}]

    first = search_path(query)
    for start in range(0, len(names), 100):
        path = first if start == 0 else first + f"&page={start // 100 + 1}"
        headers = (
            {}
            if start + 100 >= len(names)
            else {"Link": f'<https://api.github.com{first}&page={start // 100 + 2}>; rel="next"'}
        )
        add(
            path,
            {
                "incomplete_results": False,
                "items": [{"full_name": r} for r in names[start : start + 100]],
            },
            headers=headers,
        )
    for repo in sorted(set(names) | {core, loc}):
        add(f"/repos/{repo}", {"full_name": core if repo == "renamed/core-copy" else repo})
        if repo in (core, loc, "renamed/core-copy"):
            continue
        prs: list[dict[str, Any]] = [
            {"number": n, "merged_at": "2026-10-01T00:00:00Z"} for n in range(1, prs_per_repo + 1)
        ]
        add(f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100", prs)
        for pr in prs:
            number = int(pr["number"])
            issues = (
                []
                if number == 1
                else [
                    {
                        "number": number + 100,
                        "title": "broken_cache regression",
                        "body": "Synthetic issue text for transport validation only.",
                        "url": f"https://github.com/{repo}/issues/{number + 100}",
                        "repository": {"nameWithOwner": repo},
                    }
                ]
            )
            owner, name = repo.split("/")
            body = {
                "query": ISSUE_QUERY,
                "variables": {"owner": owner, "name": name, "number": number, "cursor": None},
            }
            add(
                "/graphql",
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "closingIssuesReferences": {
                                    "nodes": issues,
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    }
                },
                body,
            )
            if not issues:
                continue
            base, head = digest([repo, number, "base"])[:40], digest([repo, number, "head"])[:40]
            add(
                f"/repos/{repo}/pulls/{number}",
                {
                    "base": {"sha": base},
                    "head": {"sha": head},
                    "merge_commit_sha": digest([repo, number, "merge"])[:40],
                    "merged_at": pr["merged_at"],
                    "html_url": f"https://github.com/{repo}/pull/{number}",
                },
            )
            add(f"/repos/{repo}/compare/{base}...{head}", {"merge_base_commit": {"sha": base}})
            merged = digest([repo, number, "merge"])[:40]
            add(f"/repos/{repo}/git/commits/{merged}", {"parents": [{"sha": base}, {"sha": head}]})
            source = "def changed():\n    return 1\n\ndef second():\n    return 2\n"
            source += "\n".join(
                f"def broken_cache_{i}():\n    return 'broken_cache'\n" for i in range(12)
            )
            diff = (
                "diff --git a/code.py b/code.py\n--- a/code.py\n+++ b/code.py\n"
                "@@ -2 +2 @@\n-    return 1\n+    return 3\n"
            )
            if number == 2:
                source = "def invalid(:\n"
            elif number == 3:
                diff = (
                    "diff --git a/new.py b/new.py\n--- /dev/null\n+++ b/new.py\n"
                    "@@ -0,0 +1,2 @@\n+def new():\n+    return 1\n"
                )
            elif number == 4:
                diff = diff.replace("b/code.py", "b/renamed.py")
            elif number == 5:
                diff = (
                    "diff --git a/code.py b/code.py\n--- a/code.py\n+++ b/code.py\n"
                    "@@ -1,0 +2 @@\n+    extra = 1\n"
                )
            elif number == 6:
                diff = (
                    "diff --git a/code.py b/code.py\n--- a/code.py\n+++ /dev/null\n"
                    "@@ -1,2 +0,0 @@\n-def changed():\n-    return 1\n"
                )
            elif number == 7:
                diff += "@@ -5 +5 @@\n-    return 2\n+    return 3\n"
            elif number == 8:
                diff = diff.replace("@@ -2 +2 @@", "@@ -7 +7 @@")
            document["snapshots"][digest([repo, base, head])] = {
                "files": {"code.py": source},
                "diff": diff,
            }
    return document
