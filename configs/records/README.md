# configs/records/ — settings recorded for provenance

Settings recorded for provenance, not consumed by final runs. Nothing here is a frozen
configuration and no test guards these files against change.

| Record | What it records |
|---|---|
| `rq1_dev_selection.json` | the setting the RQ1 development selected on the development set (CodeRankEmbed at 1,024 tokens, RRF k 100) and the ladder's configuration, with the stored dev difference to the frozen settings and a latency snapshot |

A record enters `configs/frozen/` only when a registered or built artefact depends on it.
