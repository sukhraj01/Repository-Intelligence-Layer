# Compute — local box and Ada

Live document. Read before any cluster job, dataset fetch, or memory-heavy step.
**Facts about Ada below are inherited from earlier projects' state files (Aug–Oct 2026). They are
dated and the cluster changes — re-verify before relying on any number.** When you verify or find
something new, update this file and say so in the commit message.

## Machines

| | Spec | Use for |
|---|---|---|
| Local dev box | 8 GB RAM, no GPU | parsing, unit tests, linting, tiny subsamples, writing sbatch scripts |
| Ada (IIIT-H Slurm cluster) | HPC cluster; 128 GB RAM nodes; Ada GPUs | CORE-Bench-scale indexing, training, the RQ2 arms, any GPU work, **all dataset acquisition** |

Every benchmark records the exact hardware it ran on. Latency numbers from different machines are
never compared without saying so.

## Data acquisition rule

The engineer does **not** download datasets by hand. Data arrives on Ada via scripts in
`scripts/ada/`, each of which:

1. downloads **resumably** (`wget -c --tries=10 --retry-connrefused` or the library's resume path),
2. verifies size/checksum and writes `data/raw/<dataset>/provenance.json` (source URL, date, sha256, row counts),
3. is idempotent (re-running a finished fetch is a no-op),
4. runs as a **CPU-only job** — never hold a GPU during a download.

If a source is unreachable from Ada, write the job and the exact command, record a *data* blocker in
`PROJECT_STATE.md`, and continue with work that does not need that data.

## Datasets and where they live

| Dataset | Source (per master doc) | Notes |
|---|---|---|
| CORE-Bench (L1/L2/L3, REWRITE) | Hugging Face `zhangfw123/CORE-Bench`, code `CORE-Bench-Eval` | eval only; layout `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl`; L2 ≈ 9.4M chunks / 632 repos, L3 ≈ 2.6M chunks / 97 repos |
| SweLoc | released with SweRank | primary training pool candidate (ADR-001) |
| SWE-bench Verified | official | RQ3 outcome measure; instances overlap L2/L3 |
| Loc-Bench | released with LocAgent | 660 examples; contamination check |
| CodeSearchNet, CoIR | public | transfer-gap arm / generalisation (cut first if behind) |

**Disk is a first-order risk.** Measure the on-disk size of each corpus before staging it, and
compare against the quota (Open question Q6). Earlier projects saw `$HOME` at ~25.6 GB total with ~5 GB free.

## Inherited Ada lessons (verify; dated 2026-08 → 2026-10)

**Access & scheduling**
- `ssh ada` is a host entry in `~/.ssh/config`; the login node moved to `ada-gw1.iiit.ac.in` after the 2026-09-29→10-01 maintenance. If `ssh ada` fails, check that entry first.
- Slurm. The partition that actually worked was found with `sinfo` (`u22`); the Ada wiki's example partition name (`long`) was stale. Always `sinfo` before writing `#SBATCH --partition`.
- QOS has changed repeatedly (a `low` tier of 10 CPU / 1 GPU / 32,000 MB per user was seen; changed twice in a week). Run `myallocation` and `sacctmgr show qos` before sizing any job instead of trusting numbers here. Put all `#SBATCH` lines before any shell command (an ordering bug broke a job once). `QOSMaxCpuPerUserLimit` blocks occur when an idle interactive session still holds CPUs.
- Chain stages with `--dependency=afterok:` / `afterany:`.

**GPU nodes**
- Some GPU nodes were bad: one had a mismatched driver (`nvidia-smi` exits non-zero); another had a GTX 1080 Ti (sm_61) that the installed torch build does not support — and `torch.cuda.is_available()` still returned `True`. Gate every GPU job with a **real CUDA matmul** capability check, and request a supported card with `--constraint=` (the 2080 Ti constraint worked).
- Jobs that hold a GPU while idle get wasted or cancelled: split pipelines into a CPU-only download/prepare stage and a GPU stage that starts using the GPU within seconds.

**Environment**
- Environment modules were broken, and Miniconda's installer refused (glibc 2.17). **`uv`** (static binary + portable Python) worked.
- `uv pip install` crashed on the login node (memory ceiling) — run it inside an `srun` allocation.
- Match the PyTorch wheel to the node driver's max CUDA (a cu121 wheel worked when the driver supported up to 12.8; the default wheel wanted a newer CUDA). Check `nvidia-smi` on the target node.
- `/ssd_scratch` is **local to each compute node**, not shared; data staged in one session is invisible to a job that lands on another node. Stage into `$HOME` (NFS) or have the job fetch its own data idempotently. `/share1` was **not mounted on compute nodes**.

**Network**
- Outbound downloads from Ada were heavily throttled in earlier projects: PyPI ~0.1–0.4 MB/s, a Stanford mirror 15–50 KB/s, an S3 bucket ~18 KB/s. A 116 MB fetch took roughly an hour elsewhere. Assume multi-hour fetches for large corpora and design for resumability. Hugging Face throughput from Ada is **unknown** — probing it is the first step of the held-out repository job (`specs/held_out_repos.md`).

## Memory-estimation discipline

Before running any step at a new scale for the first time: measure per-unit memory on a small sample,
project to full scale, and compare against the machine ceiling **with OS headroom**. If close to the
margin, go to Ada immediately; do not try locally first.

## Log of cluster verification

| date | what was verified | result |
|---|---|---|
| 2026-10-17 | `ssh -o BatchMode=yes ada hostname` works non-interactively (key auth, login node `ada-gw1.iiit.ac.in`, python 3.9.25, no `uv`, no pyarrow/pandas/huggingface_hub) | verified |
| 2026-10-17 | Login node reaches huggingface.co (0.10 s HEAD), github.com (0.17 s), pypi.org (0.07 s), raw.githubusercontent.com (30 s once, 0.35 s from a compute node) | verified |
| 2026-10-17 | HF throughput, 50 MB HTTP Range request: login node 8.87 MB/s, compute node gnode002 6.46 MB/s (not throttled to the KB/s seen in earlier projects) | measured, `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | Slurm: `srun -p u22 -A research -q low` works; `-p u22-cpu` is rejected for account `research` ("Invalid account or account/partition combination"); `--output=%h/...` is not expanded (creates a literal `%h` directory), use a path relative to the submit directory | verified |
| 2026-10-17 | Space: `$HOME` = `ada5:/home2` 50 GB, 27 GB used, 24 GB free. `quota -s` reports a different filesystem (`/share1`, 25 GB soft quota, 3.6 MB used). CORE-Bench whole repo is 32.2 GB (does not fit); L2+L3 originals 17.0 GB (fits, leaves about 7 GB) | measured |
| 2026-10-17 | Tree listing: `GET /api/datasets/<id>/tree/main/<path>?recursive=true&limit=1000` paginates via the `Link` header; adding `expand=true` with `limit=1000` returns HTTP 400 | verified |
| 2026-10-17 | Compute nodes run Python 3.10.12, the login node 3.9.25: a venv built on the login node (`python3 -m venv`, `pip install pyarrow`) imports pyarrow there and fails on a node ("No module named pyarrow", two failed jobs). Key venvs by interpreter version and build them inside the job (`scripts/ada/pool_repo_counts.sbatch`). `python3 -m venv` plus `pip` works on the login node; pyarrow 21.0.0 installed from PyPI | verified |
| 2026-10-17 | Aggregate streaming throughput from Hugging Face with 4 parallel connections on one compute node: 13.8 GB of corpus files in 17 min (about 13.6 MB/s), 6.1 GB of queries/qrels in 19.6 min; two jobs of 4 CPU each ran concurrently on gnode002. A third 4-CPU job stayed pending (`QOSMaxCpuPerUserLimit`, 8 CPUs per user in qos low). Transient `Name or service not known` errors occurred on gnode002 (retried by the scripts) | measured, `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | Unauthenticated GitHub API from the login node: 60 requests per hour per address (used up after 42 repository lookups; reset time is in `X-RateLimit-Reset`); no credentials are stored anywhere, so repository lookups at scale need an engineer decision | verified |
| 2026-10-17 | `$HOME` after the S4 streaming runs: 23 GB free (350 MB of derived files under `~/ril_s2`); nothing large was staged | measured |
| 2026-10-17 | `GITHUB_TOKEN` on the cluster: not set in a login shell, in `bash -lc`, or in `~/.bashrc` and `~/.bash_profile` (presence tested with `[ -n "$GITHUB_TOKEN" ]`, value never printed). Unauthenticated `GET /rate_limit` from the login node: 60 per hour, 53 left at the start of the run; `scripts/ada/resolve_renames.py` used 49 and stopped at the reserve | measured, `results/logs/d_resolve_renames_2026-10-17.json` |
| 2026-10-17 | `ril` copied to `~/ril_d/ril` runs unchanged under the login node's Python 3.9 (stdlib-only modules `rename_resolution`, `content_overlap`, `repo_id`, `unit_id`); `srun -p u22 -A research -q low -c 2 --mem=4G` ran the content-overlap audit (job 25469, gnode002, 20 CPUs visible) and `sbatch` the is_test validation (job 25468); the audit streamed about 70 pool members by HTTP Range request from Hugging Face | verified |
