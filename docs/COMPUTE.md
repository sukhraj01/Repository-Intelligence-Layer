# Compute — local box and Ada

Live document. Read before any cluster job, dataset fetch, or memory-heavy step.
**Facts about Ada below are inherited from earlier projects' state files (Aug–Oct 2026). They are
dated and the cluster changes — re-verify before relying on any number.** When you verify or find
something new, update this file and say so in the commit message.

## Machines

**Local machine: editing, `make lint`, `make test` (one worker) and git only.** The 8 GB machine crashed on
2026-10-25 while torch was being installed and CPU training tests ran next to the editor. Nothing that
imports torch, trains, encodes or loads a model runs locally, tiny tests included. torch is an optional
Poetry group: `make setup` never installs it; `make setup-train` (Ada only) adds it; `make test` skips the
`torch` and `slow` markers; `make test-all` is Ada only. The training stack's torch tests run as
`scripts/ada/t1_tests.sbatch`.

**Ada accounts.** Jobs are ledgered per account in `results/logs/ada_jobs.csv` (the lead's; workstreams A and C keep `results/logs/ada_jobs_a.csv` and `ada_jobs_c.csv` so that three people never append to one file; accounts named A, B, C in
tracked text); GPU budgets are summed across accounts; one job never spans two accounts; per-user QOS limits
apply per account. On 2026-10-25 only account A has an alias in the local SSH configuration (it answers
`ssh -o BatchMode=yes -o ConnectTimeout=10`); B and C have no alias yet, so whether homes are shared is
not measured (needs the engineer to add the aliases).

| | Spec | Use for |
|---|---|---|
| Local dev box | 8 GB RAM, no GPU | parsing, unit tests, linting, tiny subsamples, writing sbatch scripts |
| Ada (IIIT-H Slurm cluster) | HPC cluster; 128 GB RAM nodes; Ada GPUs | CORE-Bench-scale indexing, training, the RQ2 arms, any GPU work, **all dataset acquisition** |

Every benchmark records the exact hardware it ran on. Latency numbers from different machines are
never compared without saying so.

## Ada accounts

Three logins, all with SSH key authentication (no password prompt once the key is accepted).

| Login | Gateways | Slurm account / QOS | Limits (checked 2026-10-25) | `$HOME` |
|---|---|---|---|---|
| account A (primary, alias `ada`) | `ada-gw1.iiit.ac.in` | `-A research -q low` | 10 CPU, 1 GPU, 32,000 MB per user, 5 jobs (`myallocation`, 2026-10-23) | separate NFS home, about 25 GB |
| account B (course allocation) | `ada-gw1.iiit.ac.in` or `ada-gw2.iiit.ac.in`, own login | course account and QOS (`-A <course> -q <course>`) | `cpu=10,gres/gpu=1` per user, **1 job**, **6 h wall time**, priority 0 (`sacctmgr show qos`) | own home, 25 GB, empty at first login |
| account C (second login) | `ada-gw1.iiit.ac.in` or `ada-gw2.iiit.ac.in`, key-based login | `-A research -q low` | `cpu=10,gres/gpu=1,mem=32000M` per user, 5 jobs, 4-day wall time, priority 10 (`sacctmgr show qos low`) | own home, 50 GB, 13 GB already used by other files in the account at first check |

- The logins have separate homes, separate venvs and separate QOS limits; nothing staged under one is visible to the
  other. A job on another login needs its own copy of the code, environment and caches.
- QOS limits are per user, so each extra login adds its own 10 CPU / 1 GPU allowance. The course login's 1-job and
  6-hour limits mean only short or resumable jobs fit there (training jobs must checkpoint and resume, see `scripts/ada/t1_train.sbatch`).
- The GPU budget (decision D21, below) is counted per block of work across **all** logins.
- Account C has the same QOS as the primary and the most free disk (about 38 GB). Work under a project
  directory (e.g. `~/ril_*`) and never touch other files already in that home.
- Record which login and node a run used in its log; hardware comparisons follow the rule above.
- Optional convenience: one `~/.ssh/config` host entry per account (e.g. `ada2` for B, `ada3` for C, with the user and
  identity file set locally) so scripts can say `ssh ada2` / `ssh ada3`.

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

## GPU budget (decision D21, 2026-10-18)

GPU jobs are authorised within a budget per block of work: **block 1 at most 8 GPU-hours, block 2 at most 24 GPU-hours**,
summed over jobs and counted from `sacct` (elapsed time times allocated GPUs). Before sizing a job run `sinfo`,
`myallocation` and `sacctmgr show qos`. Every GPU job starts with a real CUDA matrix multiplication as a capability gate,
requests a supported card with `--constraint`, keeps CPU preparation in a separate job, and is idempotent and resumable.
A job that would take the block over its budget is not submitted; the item records its partial result and the resumable
command instead. Each GPU job gets a row here when it finishes.

| Date | Job id | Block | Purpose | GPUs x elapsed | GPU-hours | Block total |
|---|---|---|---|---|---|---|
| 2026-10-23 | 36104 | 1 | X2 dense encoding (CodeRankEmbed, Qwen3-Embedding-0.6B): dev unit texts at 512 and 1024 tokens, all query stores, Verified-six unit texts and dev/Verified-six chunk texts at 512, GPU latency rows; RTX 2080 Ti (gnode044), CUDA gate passed | 1 x 02:24:36 | 2.41 | 2.41 |
| 2026-10-25 | 38109 | 1 | X2: CodeRankEmbed at 1024 tokens on the Verified-six unit texts (the dev rule selected 1024 for this encoder) and, because the stage listed chunk stores too, on the chunk texts; texts the 512 cut left whole taken over from the 512 run; RTX 2080 Ti (gnode045), CUDA gate passed | 1 x 00:25:58 | 0.43 | 2.84 |
| 2026-10-25 | 38202 | 1 | X3 pool ranks: SweRankEmbed-Small and CodeRankEmbed on 160 sampled pool directories (188,566 functions, code text, 1,024 tokens, float16); RTX 2080 Ti (gnode045), CUDA gate passed | 1 x 00:19:33 | 0.33 | 3.17 |
| 2026-10-25 | 38213 | 1 | X3: SweRankEmbed-Small on the stored text of the same directories (sensitivity); gnode045 | 1 x 00:10:42 | 0.18 | 3.35 |
| 2026-10-25 | 38291, 38292 | 1 | X3 reference jobs that read the pool listing instead of the reference listing (every directory a lookup error; resubmitted) | 1 x 00:00:37 | 0.01 | 3.36 |
| 2026-10-25 | 38295 | 1 | X3 reference: SweRankEmbed-Small on 457 Verified-export directories (3.68 million functions, 161,946 encoded after per-repository dedup); gnode046 | 1 x 00:22:18 | 0.37 | 3.73 |
| 2026-10-25 | 38296 | 1 | X3 reference: CodeRankEmbed on the same; gnode046 | 1 x 00:21:31 | 0.36 | 4.09 |
| 2026-10-25 | 38741 | 2 | T1 training throughput, all shapes in one process (every shape out of memory after the first); account A, gnode045 | 1 x 00:00:52 | 0.01 | 0.01 |
| 2026-10-25 | 38746 | 2 | T1 throughput job submitted with a wrong commit label, cancelled; account A | 1 x 00:00:06 | 0.00 | 0.02 |
| 2026-10-25 | 38747 | 2 | T1 training throughput and peak memory per batch shape of CodeRankEmbed (fp32, float16 autocast, plus gradient checkpointing); account A, gnode046, CUDA gate passed | 1 x 00:06:55 | 0.12 | 0.13 |
| 2026-10-25 | 39098 | 2 | T2 teacher passes over the 2,000-directory cache A: CodeRankEmbed (66 min) then SweRankEmbed-Small (66 min), K-ranks and top-64 candidates at 1,024 tokens, float16; account A, gnode057, CUDA gate passed | 1 x 02:11:57 | 2.20 | 2.33 |
| 2026-10-25 | 39100 | 2 | T2 runs `t2_k_raw` seeds 0, 1 (63 updates each) with dev and Verified-six evaluation; account A, gnode044 | 1 x 01:24:33 | 1.41 | 3.74 |
| 2026-10-25 | 39101 | 2 | T2 runs `t2_leak_in` seeds 0, 1 with dev and Verified-six evaluation; account A, gnode044 | 1 x 01:24:38 | 1.41 | 5.15 |
| 2026-10-25 | 39188 | 2 | T2 run batch of 16 (FILTER under CodeRankEmbed, BM25, SweRankEmbed-Small K 10/20), dev evaluation; about 22 min per run, of which about 16 min encoding the dev unit texts (about 50 texts/s against X2's 201: the trained model's encode path); account A, gnode044 | 1 x 05:50:29 | 5.84 | 10.99 |
| 2026-10-26 | 39212 | 2 | T2 run batch of 16 (FILTER SweRankEmbed-Small K40 and agreement, NEG, WEIGHT, CURRICULUM), dev evaluation; account A, gnode044 | 1 x 05:53:02 | 5.88 | 16.87 |
| 2026-10-29 | 46134 | W4-1 | E7 training-step cost of Qwen3-Embedding-0.6B at batch 32 x (1+1), 512 tokens (out of memory) with three smaller shapes in the same process (carry-over peaks, not clean), CodeRankEmbed control; account A, gnode045, CUDA gate passed | 1 x 00:01:53 | 0.03 | 0.03 |
| 2026-10-29 | 46180 | W4-1 | E7 repeat: the shape list lost its commas in `--export` (Qwen3 shapes failed), CodeRankEmbed control, memory probe crashed at the optimizer step; account A, gnode046 | 1 x 00:01:23 | 0.02 | 0.05 |
| 2026-10-29 | 46183 | W4-1 | E7 clean rerun: Qwen3 shapes 4, 2, 1 (one process each, all out of memory), CodeRankEmbed at batch 8, memory probe (weights, gradients, optimizer state); account A, gnode046 | 1 x 00:01:01 | 0.02 | 0.07 |
| 2026-10-29 | 46273 | W4-2 | T3 pool: next 3,000 pool directories after selection A cached (CPU only, 2 CPUs, 43 min, MaxRSS about 1 GB; 428 MB file) | 0 | 0.00 | 0.00 |
| 2026-10-29 | 46827 | W4-2 | T3 first attempt (cancelled by us after the step-0 evaluation of the full dev set took 43 min and its cost per evaluation was seen); account A, gnode058 | 1 x 00:48:06 | 0.80 | 0.80 |
| 2026-10-29 | 46874, 46875 | W4-2 | T3 relaunch failed in seconds (cache metadata key names in the subset helper) | 1 x 00:00:04 | 0.00 | 0.80 |
| 2026-10-29 | 46876 | W4-2 | T3 learning curve, seed 0: RAW, 2,000 of the 3,000-update schedule, dev subset evaluations at 100, 300, 1000, 2000 updates (10 min each); training loop 1.49 h; MaxRSS 11.1 GB of 24 GB; account A | 1 x 02:11:27 | 2.19 | 2.99 |
| 2026-10-29 | 46879 | W4-2 | T3 learning curve, seed 1, same; MaxRSS 11.8 GB; account A | 1 x 02:09:04 | 2.15 | 5.14 |

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
| 2026-10-17 | Parse-and-graph build jobs (u22, qos low, `~/ril_p/`, Python 3.10.12 on gnode002): `python3 -m venv` plus `pip install` of numpy, pyyaml, pyarrow, networkx, rustworkx and kuzu works inside a job (cp310 wheels); the flask test suite (483 passed, 1 skipped) runs in 11 s under the tracer and 4 s untraced with the repository's pinned test requirements (job 25517, 13 s wall including the venv reuse); a full `git clone` of django/django (293 MB `.git`, 31,107 commits) from github.com takes 5 min 12 s in a one-CPU job (25519); the graph, storage and determinism measurement of flask, requests and django takes 11 min 37 s on 4 CPUs with a 1.5 GB peak (25550); a shallow fetch of one commit (`git fetch --depth 1 origin <sha>`) works (25530, four repositories in 1 min 32 s). A first storage run (25529) reported invalid peak memory because `ru_maxrss` is inherited across `fork` and `exec` on Linux; it was discarded and the measurement reads `VmHWM`. The Ada node reports 6 CPUs under `nproc` for a 4-CPU request | verified, jobs 25517, 25519, 25529, 25530, 25550 |
| 2026-10-17 | Pilot M jobs (u22, qos low, 2 CPUs, 12 GB requested, `~/ril_m/`, Python 3.10.12 on gnode002, git 2.34.1): a working clone from the bare cache in `~/ril_s2/raw/repo_cache` and `git checkout -f <base commit>` for 11 instances of three repositories, the parse and graph build of each snapshot with history, the location of 160 chunks and 200 random draws per positive and control took 31 s and 35 s of wall time (jobs 25572, 25573) with a peak of 136 MB resident; a venv with numpy, pyyaml and pyarrow builds inside the job | measured, jobs 25572, 25573 |
| 2026-10-18 | Pilot E jobs (u22, qos low, `~/ril_e/`, Python 3.10.12 on gnode002; `pystemmer`, numpy, pyyaml, pyarrow install into a job venv): fetch of 31 CORE-Bench folders (1.3 GB; Verified L2 and L3, five dev folders) by `hf_fetch.py`; bare clones of eight repositories took 28 min in one job (a job array is refused: `QOSMaxSubmitJobPerUserLimit`, 5 jobs per user); the whole BM25 chunk stage over 31 folders took 2.5 min; the unit stage (checkout, parse, locate, two BM25 indexes) over 438 instances took 49 min with a 3.8 GB peak; all 632 original L2 folders (fetch, score, delete one at a time, about 10.5 GB streamed) took 63 min and 16 GB requested was ample. The QOS limit appears to count a billing weight that grows with requested memory (a 24 GB request reads as billing 10 against 2 CPUs and 4 GB reading as 3): requests of 4 to 8 GB start next to a running 2-CPU job, 24 GB waits. Output file names that differ only in case (three Live folders) collide when copied to macOS; rename on the cluster before `rsync` | measured, jobs 25779, 25780, 25785, 25787, 25788, 25789, 25830 |
| 2026-10-18 | Pilot E3 to E5 jobs (u22, qos low, `~/ril_e/`, Python 3.10.12 on gnode002): per-instance cache (checkout, units, typed graph with history, BM25 scores) of 355 dev and 83 Verified instances took about 25 and 4 minutes as four shards of one 4-CPU job with 12 GB requested (jobs 25845, 25851; 3 GB per shard at most); the evaluation of all grids runs locally on the cache files (34 MB for 438 instances, 1.5 minutes for the 1,141-key dev grid). CodeRankEmbed on CPU: a venv with the CPU build of torch, `transformers` 4.44.2 (newer versions fail inside the model repository's own code with a missing `get_extended_attention_mask`), sentence-transformers 3.1.1, einops; the model downloads from huggingface.co (job 25855) and encodes 0.85 chunks of 1,500 characters per second on 4 CPUs; a count of distinct unit texts over six spread snapshots per dev repository (job 25857) gives about 52,000 texts for the five dev repositories. A job that asked for 4 CPUs and 8 GB started next to a running 4-CPU job (8 CPUs per user in qos low) | measured, jobs 25843, 25845, 25851, 25853, 25855, 25857 |
| 2026-10-23 | Structure-measurement jobs (u22, qos low, `~/ril_x1/`, reusing `~/ril_e/venv_ril310`, raw folders and bare clones by symbolic link): the QOS `low` limit is `cpu=10,gres/gpu=1,mem=32000M` per user and 5 jobs; Slurm rounds the CPU allocation up with the memory request (`--mem=16G` with 4 CPUs was allocated 6 CPUs, `--mem=12G` 5 or 6), so a second job waited on `QOSMaxCpuPerUserLimit` until resubmitted with `--cpus-per-task=4 --mem=10G` (allocated 4). Extras of 355 dev instances in 25.7 min (job 35493, 1.6 CPU-hours), 83 Verified-six instances in 22.5 min (job 35511, 1.0 CPU-hours, slower per instance: astropy and matplotlib with three parses each). The pilot-E1 unit stage on django takes about 1.5 min per instance on one process (35,000 units), so 136 django L3 instances take about 3.5 hours unsharded (jobs 35503, 35518; resumable) | measured |
| 2026-10-23 | Dense-measurement jobs (u22, qos low, `~/ril_x2/`): `sinfo` lists `2080ti` as a node feature on u22 (14 idle, 20 mixed nodes at the check); `myallocation` shows only account `research` with QOS `low` (`cpu=10,gres/gpu=1,mem=32000M` per user, 5 jobs); a GPU environment (torch 2.4.1 for CUDA 12.1, transformers 4.51.3, sentence-transformers 4.1.0, numpy 1.26.4) built inside a CPU job with `pip --no-cache-dir` takes 4.4 GB and about 15 minutes; CodeRankEmbed's modelling code needs transformers 4.44.2, kept as a `--target` overlay (transformers 4.44.2, sentence-transformers 3.1.1, tokenizers 0.19.1; 87 MB) put first on `PYTHONPATH`, so one torch serves both models; both models load offline (`HF_HUB_OFFLINE=1`) from the shared cache. `$HOME` had 9.4 GB free at the start (removed regenerable X1 working clones and the superseded CPU venv: 11 GB free). The QOS limit is per user, not per project: jobs of another project under the same login holding all 10 CPUs keep a GPU job pending on `QOSMaxCpuPerUserLimit`; Slurm priority is flat (500), so pending jobs start in submission order as CPUs free up | measured, jobs 36028, 36066, 36072, 36104 |
| 2026-10-25 | Pool-rank jobs (u22, qos low, `~/ril_x3/`, reusing `~/ril_x2/venv_gpu310` with the CodeRankEmbed overlay): SweRankEmbed-Small's configuration points to modelling code in another model repository whose weight loader looks the weights up by hub name at the default revision, so a pinned revision fails offline ("Model name ... was not found", job 38198); loading from the cached snapshot directory works (`dense_encoder.local_snapshot`). Range-request reads of pool directories inside a GPU job, fetched four ahead in threads, kept the GPU busy (5 GPU jobs, 0 fetch errors over 617 directories). A listing used for range reads must carry member offsets (the 2026-10-17 listing of `swe_bench_verified.zip` did not; re-listed with `scripts/ada/zip_remote_listing.py`). `$HOME` had 2.2 GB free at the start (SweRankEmbed-Small adds 0.55 GB to the model cache) and 1.9 GB at the end; nothing was staged | measured, jobs 38198, 38201, 38202, 38213, 38295, 38296 |
| 2026-10-25 | Training-stack validation jobs (u22, qos low, CPU only, `~/ril_t1/`, reusing `~/ril_x2/venv_gpu310`; jobs 38730, 38731, gnode004, 2.1 and 3.0 min): `/ssd_scratch` does not exist on the login node or gnode004; node-local `/tmp` on gnode004 had 1.7 TB free. One step checkpoint of CodeRankEmbed with AdamW state plus a half-precision final model took 1.8 GB (final model alone 274 MB), against 1.8 GB free in `$HOME`: training jobs keep checkpoints in node-local space and copy only the half-precision final model to `$HOME` (`scripts/ada/t1_train.sbatch`); a resubmission that lands on another node restarts from update 0. The E3 cache under `~/ril_e/e3_cache` lacks the D18 no-module gold readings (job 38730 failed on `gold_L2_units_nomod`); the X2 evaluation used the local copy with them, now also at `~/ril_t1/work/e3_cache`. CodeRankEmbed fine-tuning on 4 CPU threads (E5-2640 v4), batch 2, 128 tokens: 4.5 s per update | measured, jobs 38730, 38731 |
| 2026-10-25 | Account B (course allocation): `ssh -o BatchMode=yes` works on `ada-gw1` and `ada-gw2` (key auth); course account and QOS = `cpu=10,gres/gpu=1` per user, 1 job, 6 h wall time, priority 0; own home 25 GB, 0% used; login node Python 3.9.25; `sinfo` lists u22 (77 nodes), u22-cpu, ihub, plafnet2, rrc. Partition access for this account not yet tested with a job | verified |
| 2026-10-25 | Account C (second login, key-based): `ssh -o BatchMode=yes` works on `ada-gw1` and `ada-gw2`; account `research`, QOS `low` = `cpu=10,gres/gpu=1,mem=32000M` per user, 5 jobs, 4-day wall time, priority 10; own home 50 GB, 13 GB used, 38 GB free; no jobs queued. Not yet tested with a job | verified |
| 2026-10-29 | Full contamination scan (u22, qos low, account A, `~/ril_c/`, CPU only): 240 shards, 306.6 GB streamed, 17.9 worker-hours summed over shards; two 4-CPU jobs of 120 shards ran side by side on gnode002 in 2 h 13 min and 2 h 06 min (MaxRSS 4.7 GB and 1.7 GB, 8 GB requested); transient `Name or service not known` errors failed one shard after three attempts (rerun as its own job); a third job with 3 CPUs next to two 4-CPU jobs waited on `QOSMaxCpuPerUserLimit` (10), resubmitted with 2 CPUs and `--mem=3G` it started at once; `$HOME` stayed at about 1.0 GB free (`~/ril_c/out` 207 MB after the scan, of which the base-commit hash file is 154 MB gzipped) | measured, jobs 45620, 45621, 45623, 45774 |
| 2026-10-29 | Graph-role measurement S1 (u22, qos low, account A, `~/ril_x2/`, CPU only, 4 CPU, 195 MB peak resident, 8.1 min for four configurations, no GPU): first two submissions failed in seconds (a colon in a YAML title; the default `e3_cache` lacks the D18 readings, so the job reads `~/ril_t1/work/e3_cache`, the D18 cache the training stack evaluates on). Rows in `results/logs/ada_jobs.csv`; sbatch `scripts/ada/s1_graph_role.sbatch`. 0.0 GPU-hours. |
| 2026-10-29 | Training-step jobs of E7 (u22, qos low, `~/ril_t1/`, base environment of `~/ril_x2`): `--export=ALL,KEY=a,b` splits at the commas, so a shape list like `4,1,1,512` loses everything after the first comma (use `/` and convert inside the script); a for-loop over a quoted default that holds several words runs one process for all of them, and an out-of-memory shape then leaves its peak in the next shape's row (one process per shape, as T1 had already learned); a 2-CPU 8 GB request starts next to a 6-CPU job where a 4-CPU 16 GB request (rounded to 6) waits on `QOSMaxCpuPerUserLimit`; `sinfo` shows no card with more than 11 GB reachable from account `research` (`sbatch --test-only -p ihub|plafnet2|rrc` is refused: "Invalid account or account/partition combination"; the unlabelled `u22` nodes expose no card type); `$HOME` had 1.0 GB free | measured, jobs 46134, 46180, 46183 |
| 2026-10-29 | Edited-function follow-up of the contamination scan (u22, qos low, account A, `~/ril_c/`, CPU only; jobs 46133 and 46147, 1 min 55 s and 1 min 47 s, MaxRSS 0.61 and 0.41 GB, 8 GB requested): one `git apply` plus parse per patched Python file of 500 instances, join with the 240 scan shards and the 7.4 M-entry hash file. The patch table (a 0.8 MB JSON file, from the Verified table's `patch` column) is built locally and copied to `~/ril_c/work/`; it stays untracked | measured, jobs 46133, 46147 |
| 2026-10-29 | `GITHUB_TOKEN` on the cluster re-checked for E-POOL-DATES (D29): not set in the login shell of account A (`[ -n "${GITHUB_TOKEN:-}" ]`, value never printed; no `~/.github_token` or `~/.config/gh`), so E-POOL-DATES was **not run**; it needs the engineer to provide the read-only token on Ada (D2) | measured |
| 2026-10-29 | Pro ansible as a dev repository (u22, qos low, account A, CPU; job 46142, 43 min, MaxRSS 3.5 GB of 12 GB, 3 shards): 83 instances cached; working clones on node-local `/tmp` because `$HOME` had 1005 MB free; additions to `$HOME` about 450 MB (`~/ril_x2/prep` 833 MB to 1.2 GB, `~/ril_e/e3_cache_ansible` 25 MB, a 25 MB copy in `~/ril_t1/work/e3_cache`), leaving 547 MB free of 50 GB. The regenerable census working clones (`~/ril_x1/work_census_*`, 1.4 GB) are the obvious thing to delete: not deleted here, left to the engineer | measured, job 46142 |

| 2026-10-29 | T3 learning curve (u22, qos low, account A, `~/ril_t3/`, 2080ti, 4 CPUs, 24 GB): the evaluation of the full dev set (six repositories at L2, three at L3 including ansible) takes 43 min per checkpoint at 229 unit texts/s (590k texts, ansible alone 274k), so six evaluations per seed would have cost more than the whole remaining block; the curve evaluates the dev subset openlibrary, qutebrowser (L2, L3) and streamlink (L2), 10 min per checkpoint, and stops the 3,000-update schedule after 2,000 updates. Checkpoints (1.6 GB) and the half-precision copies live in `/tmp/ril_t3_seed<k>` (deleted at the end); `$HOME` had 128 MB free after the 428 MB pool file, results 3.2 MB. `#SBATCH --output=ril_t3/logs/...` is relative to the submit directory, so with `cd ~/ril_t3` the Slurm log lands in `~/ril_t3/ril_t3/logs/` | measured, jobs 46827, 46876, 46879 |
| 2026-10-30 | 48679 | 2 | Arms pilot stage 1 (E-PILOT-ARMS), seed 0: eight cells of 100 updates of the 3,000-update schedule, each followed by the dev-subset evaluation; RTX 2080 Ti (gnode049), CUDA gate passed | 1 x 02:00:06 | 2.00 | 24.14 |
| 2026-10-30 | 48747 | 2 | Stage 1, seed 1; gnode049 | 1 x 01:59:33 | 1.99 | 26.13 |
| 2026-10-30 | 48748 | 2 | Stage 1, seed 2: the CUDA gate failed on gnode077 (no CUDA), 24 s | 1 x 00:00:24 | 0.01 | 26.14 |
| 2026-10-31 | 49430 | 2 | Stage 1, seed 2 (resubmission); gnode044 | 1 x 01:52:38 | 1.88 | 28.02 |
| 2026-10-31 | 49624 | 2 | Stage 2 (E-PILOT-ARMS), seed 0: RAW, FILTER (CodeRankEmbed teacher) and CURRICULUM at 1,000 updates of the 3,000-update schedule; gnode063 | 1 x 02:45:25 | 2.76 | 30.78 |
| 2026-10-31 | 49625 | 2 | Stage 2, seed 1; gnode049 | 1 x 02:44:48 | 2.75 | 33.53 |
| 2026-10-31 | 50091 | 2 | Teacher pass, CodeRankEmbed, 3,000 pool directories outside selection A (1,024 tokens, float16); gnode054 | 1 x 01:35:08 | 1.59 | 35.12 |
| 2026-10-31 | 50092 | 2 | Teacher pass, SweRankEmbed-Small, same directories; gnode045 | 1 x 01:34:09 | 1.57 | 36.69 |
| 2026-10-31 | 50335 | 2 | Matched-pool arms pilot stage 1 (E-PILOT-ARMS2), seed 0: RAW, size-matched subsample, FILTER x3, WEIGHT, CURRICULUM at 100 updates, each evaluated on five dev repositories; gnode054 | 1 x 02:38:17 | 2.64 | 39.33 |
| 2026-10-31 | 50356 | 2 | Same, seed 1; gnode054 | 1 x 02:38:22 | 2.64 | 41.97 |
| 2026-10-31 | 50942 | 2 | Stage 2 (E-PILOT-ARMS2), seed 0: RAW, size-matched subsample and WEIGHT at 1,000 updates; time limit 3:50 so the block cap could not be passed; gnode054 | 1 x 03:10:37 | 3.18 | 45.15 |
| 2026-11-01 | 51410 | 2 | E-PILOT-NOISE N0: per-function SweRankEmbed-Small scores for the 5,000-directory pool (D48; the BM25 pass, job 51409, is CPU); gnode055 | 1 x 02:09:56 | 2.17 | 47.32 |
| 2026-10-31 | n/a | 2 | E-PILOT-ARMS2 cost and disk (account A, `~/ril_t5`): one run of 100 updates costs 0.38 GPU-hours (training loop 4.5 min, evaluation of 316k unit texts of five dev repositories 18 min at about 290 texts/s), 2.64 GPU-hours per seed of seven cells; a run of 1,000 updates 1.06 GPU-hours (training loop 44.8 min). The two pool files and the K-rank table are links to `~/ril_t3/work`; results of 17 runs, 11 MB and 551 files in all (`df` 8.3 GB available before and after; files quota 832 of 3,000 before the stage). Block 2 at 45.15 of 46; the third seed of stage 1 and the second seed and fourth cell of stage 2 were not run for that reason | measured, jobs 50335, 50356, 50942 |
| 2026-10-31 | n/a | 2 | GPU-hours per account at the end of Wave 6 (ledger `results/logs/ada_jobs.csv`, summed over its rows: 45.09; the table above sums to 45.15 by rounding per job): account A 45.09, account B 0, account C 0 (no alias for B and C on the local machine). Block 2 cap 46, 0.85 left by the table | measured, ledger |
| 2026-10-30 | n/a | 2 | Wave 5 disk note (account A, `~/ril_t4`): `df` showed 8.4 GB available and `quota -s` 3.17 GB to the soft quota before the stage, 8.3 GB after; the two pool files and the teacher tables are links to `~/ril_t2` and `~/ril_t3`, checkpoints and encoded stores are in node-local `/tmp`; results of 30 runs take 29 MB (1.25 MB per run, mostly the per-unit rows), the code copy 0.3 MB. The block cap was raised from 24 to 36 GPU-hours (33.53 used, 2.47 left). Jobs started 3 to 8 hours after submission (per-user CPU and GPU limits); one node had no usable GPU and was caught by the gate | measured |
| 2026-11-02 | PR-mined set, readiness check (account A login node, nothing submitted): `[ -n "${GITHUB_TOKEN:-}" ]` false in a login shell, no token file and no `gh` configuration (value never printed); `GET /rate_limit` answers 200 with the unauthenticated limit of 60 per hour (54 left at the check); `quota -s` 21,831 of 25,000 MB (soft), 832 of 3,000 files. The live stages of E-MINE-PILOT therefore did not run; the job stops with exit code 3 when the token is absent. Compute-node reachability of the API was not tested (no use without a token) | measured |

### Block 2 cap raised to 60 GPU-hours (D44, 2026-11-01)

The engineer raised the Block 2 cap from 46 to 60 GPU-hours for the noise dose-response pilot (E-PILOT-NOISE). Used at the end of the scoring stage: 47.32 (account A 47.26 by the ledger, accounts B and C 0). The scoring pass cost 2.17 GPU-hours against the 3.5 allowed by D48 (estimate 1.6; the cache pass over 4.9M functions took 7,732 s). Disk added: two score stores of 26.7 MB each and one separation file (`~/ril_n7`; `df` not remeasured). Stage N1 (36 runs of 100 updates, 0.377 GPU-hours each from E-PILOT-ARMS2, 13.6 in all) was not launched: it exceeds the 11 GPU-hours the brief allows for the stage and the 12.68 left under the cap. See the open question in `docs/EXPERIMENTS.md` E-PILOT-NOISE.

### N1 stage limit raised to 11 and Block 2 cap to 62 GPU-hours (D52, D53, 2026-11-01)

Measured cost of a noise-pilot run is 0.45 GPU-hours (job 51971, seed 0, r = 0.4: 2.71 GPU-hours for six cells), so the 24 runs of D49 cost about 10.8; the engineer raised the stage limit from 9.5 to 11 (D52) and the Block 2 cap from 60 to 62 (D53) so that the third-seed trigger (up to 2.3) still fits. Jobs 52143, 52144, 52145 (seed 0 r = 0.2, seed 1 r = 0.4, seed 1 r = 0.2) were submitted with the same code commit as 51971.

### Account C used for N1 (2026-11-01)

Accounts B and C answer on the gateway but the home directories are private to their owners (a read of account A's home from C is refused), so nothing is shared and each account needs its own copy. To run the last N1 job in parallel with account A's queue (one job at a time per user there), the venv, overlay, prep data, raw data, model cache, e3 cache and the code (about 10 GB, streamed from A to C without touching the local disk, 85 min with parallel streams) were staged under `~/ril_*` on C (quota 25 GB, 4 KB used before). Lesson: `tar -h` dereferences the venv's `python` links and copies the login node's Python 3.9 binary; the links must be restored to `/usr/bin/python3` (the compute nodes run 3.10). The CUDA gate (job 52384, real matmul on a 2080 Ti) passed. Job 52145 (seed 1, r = 0.2) was cancelled on A while pending and submitted on C as 52385; no job runs on two accounts. Account B was not staged (1 job, 6 h wall, no further job to place).

### N1 completed (2026-11-02)

Jobs: 51971 (A, 2.71 GPU-hours), 52143 (A, 2.23), 52144 (A, 2.25), 52385 (C, 2.24); 24 runs, 9.43 GPU-hours with the gate and queue overhead counted by job time (0.45 per run on the first node, 0.37 on the others). Ledger sum 56.69 of the cap 62 (A 54.45, C 2.24, B 0). Disk added: results 11 MB on A and a similar amount on C; the staged copy on C is about 10 GB in `~/ril_*` (quota 25 GB). Nothing deleted on either cluster account. The 24-run cost estimate that stopped the stage (10.8) was high because the first job ran on a slower node.

### Sibling-noise pilot (E-PILOT-NOISE-SIB, 2026-11-02)

Jobs on account A (`~/ril_n7`, no new staging): 52619 (CPU gate, 1 min 8 s), 52622 (seed 0, five cells, 1.86 GPU-hours), 52685 (seed 1, five cells, 1.86); 10 runs, 3.73 GPU-hours (0.37 per run on one 2080 Ti node; the first run's cost was checked before seed 1 was submitted, stage limit 5.0). Ledger sum 60.41 of the Block 2 cap 62 (A 58.17, C 2.24, B 0); 1.59 left. Only account A has an alias on the local machine, so no job ran elsewhere. Disk added: 10 result directories of about 0.65 MB each; `df` not remeasured. Nothing deleted.

### Third seed at r = 0.4 (D58, 2026-11-02)

D58: the Block 2 cap is raised from 62 to 66 GPU-hours (60.41 used before this run). Job 53271 on account A (`~/ril_n7`, no new staging): seed 2, r = 0.4, six cells, six runs, 02:23:53 on one 2080 Ti node (gnode067) = 2.40 GPU-hours (0.40 per run), submitted with the same command and `RIL_COMMIT` label as the other N1 jobs; the CUDA matmul gate runs inside each training and evaluation and passed. The cluster copy of the code equals the main branch at submission; it differs from the commit that labelled the earlier N1 jobs only by the sibling-noise kind, whose default is the uniform kind of E-PILOT-NOISE (`ril/training/noise.py`). Ledger sum 62.81 of the cap 66 (A 60.57, C 2.24, B 0); 3.19 left. `$HOME` on A before: 21,831 of 25,000 MB, files 832 of 3,000; unchanged after (six result directories, about 4 MB). Nothing deleted.

### Block 3: cap for the final RQ2 stage (D79, 2026-11-03)

The GPU budget is a project ledger, not a cluster limit; the cluster limits are per user (one GPU job at a time per account, up to four days of wall time on accounts A and C). The final RQ2 stage has its own block, **Block 3, capped at 46.7 GPU-hours**: the design of record (option E of `docs/RQ2_PROTOCOL.md`, 38.9 GPU-hours, 12 cells x 3 seeds with 8 extra evaluation repositories) plus 20%. Raised by the engineer (the lead) on 2026-11-03; nothing is used yet. Teacher scoring of the mined set and the M3 rank measurement are not in the 38.9 and are charged to this block's margin. Authorised totals by cap: Block 1 8, Block 2 66 (62.81 used, 3.19 left), Block 3 46.7; **120.7 GPU-hours** in all. Block 2 stays closed to the final stage. Final checkpoints that feed RQ3 and the report are archived to account B's storage (D76).

### PR-mined set live stages (E-MINE-PILOT, 2026-11-02 and 2026-11-03)

Account A, `~/ril_mine`. GPU: 1.99 GPU-hours of the M3 stage limit 2.0 (ledger rows L3; jobs 54914, 54915, 54936, 55027); Block 2 ledger total 64.80 of the cap 66 (D58). Two GPU jobs produced no ranks (a command-line error; CPU preparation inside the GPU job), one was held idle for 25 minutes by a node whose file-system client hung before the model loaded, so the CPU parts now run in separate jobs and the GPU job tests that torch starts within 5 minutes.

| Date | Finding | Evidence |
|---|---|---|
| 2026-11-02 | `GITHUB_TOKEN` is set in a non-interactive `ssh` command and in a submitted job; the API root answers 200 from a compute node; compute nodes run Python 3.10, the login node 3.9 (the package cannot be imported there) | job 53623 |
| 2026-11-02 | `quota -s` reports the mount the file server mount named share1 (25 GB, 3,000 files), not `$HOME` (`ada5:/home2`, shared 50 GB file system, 320,183 files in `$HOME`); the figure that binds is `df` of `$HOME` (7.7 GB free at the start, 2.9 GB at the end of M3) | `find`, `df` |
| 2026-11-02 | A shallow fetch of one commit of a large repository takes 100 to 300 s alone; the sequential run did about 1 pull request per minute at best; background fetches of the next 4 to 6 commits gave 5 to 6 pull requests per minute | jobs 54059, 54085, 54612 |
| 2026-11-02 | A write of a 33 MB corpus to `$HOME` stalled for more than 20 minutes at one point (`dd` of 50 MB with `fsync` on the login node: 1.1 MB/s); the corpus is stored gzip-compressed (1.84 MB per mined directory on average) | `dd`, job logs |
| 2026-11-03 | Processes on gnode004 and gnode044 sat in uninterruptible file-system waits (`rpc_wait_bit_killable`, state D) for tens of minutes while the same files read fast from the login node; jobs excluded these nodes afterwards (`--exclude`) | `ps` on the nodes |
| 2026-11-03 | The mining session peaked at 10,001,100 KB of 10 GB requested (all listings of 200 repositories in memory); the listing of a very large repository needs about 1,000 pages at 4 to 5 s | `sacct` job 54612 |
| 2026-11-03 | Disk added on A by this work: run roots `m1`, `m1b`, `validation`, `pilot` (2.56 GB of directories and 0.12 GB of listings in `pilot`) and `ranks/` (archives of the rank measurement); deleted by this work: three things it had just made (a 50 MB write-test file, an empty `ranks/` directory, a Python 3.9 venv of the login node); everything else stays | measured, `du`, `df` |

### Mined-set integration pilot (E-MINED-PILOT, D88, 2026-11-03 and 2026-11-04)

D88: the Block 2 cap is raised from 66 to 70 GPU-hours for this pilot (64.80 used before it). Account A, `~/ril_mp`. CPU job 55970 (51 min: pool-like archive packed in node-local space, BM25 of 1,286 directories, feature table, selection, cache of 1.25 GB written to `$HOME`); GPU jobs 56441 (seed 0, 1.30 GPU-hours) and 56571 (seed 1, 1.24) with three runs each, and two jobs that stopped within two minutes (56056, unreadable configuration file; 56565, CUDA gate failed on gnode069), 0.06 together. Stage 2.60 of the limit 3.2; ledger sum 67.41 of the cap 70 (A 65.17, C 2.24; B 0). `$HOME` on A: 2.9 GB free before, 288 MB after (cache 1.25 GB; other jobs of the account also write there); nothing was deleted. The archive of the reading is built in node-local space (1.3 GB) because `$HOME` cannot hold it next to the cache. The account's CPU limit (QOS) and the research account's GPU limit (`AssocGrpGRES`) held the first GPU job in the queue for 3 h 56 min (submitted 17:13, started 21:09); lowering its CPU request with `scontrol update` did not change that.

| Date | Finding | Evidence |
|---|---|---|
| 2026-11-03 | Building the example cache for 1,286 mined directories from the local archive took 756 s and 1.25 GB gzip (0.97 MB per directory); a pool-like archive of the same directories is about the size of the cache | job 55970 |
| 2026-11-04 | gnode069 has no CUDA (the gate stopped the job in 98 s); gnode004 and gnode044 stay excluded | job 56565 |
