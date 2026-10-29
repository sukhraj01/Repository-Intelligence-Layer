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

**Ada accounts.** Jobs are ledgered per account in `results/logs/ada_jobs.csv` (accounts named A, B, C in
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
| primary (`ssh ada`, `~/.ssh/config` host entry) | `ada-gw1.iiit.ac.in` | `-A research -q low` | 10 CPU, 1 GPU, 32,000 MB per user, 5 jobs (`myallocation`, 2026-10-23) | separate NFS home, about 25 GB |
| course: `[login]` | `ssh [login]@ada-gw1.iiit.ac.in` or `ssh [login]@ada-gw2.iiit.ac.in` | `-A [course] -q [course]` | `cpu=10,gres/gpu=1` per user, **1 job**, **6 h wall time**, priority 0 (`sacctmgr show qos [course]`) | `/home2/[login]`, 25 GB, empty at first login |
| teammate: `[login]` (key `~/.ssh/[key]`) | `ssh -i ~/.ssh/[key] [login]@ada-gw1.iiit.ac.in` or `…@ada-gw2.iiit.ac.in` | `-A research -q low` | `cpu=10,gres/gpu=1,mem=32000M` per user, 5 jobs, 4-day wall time, priority 10 (`sacctmgr show qos low`) | `/home2/[login]`, 50 GB, 13 GB already used by the account owner's files at first check |

- The logins have separate homes, separate venvs and separate QOS limits; nothing staged under one is visible to the
  other. A job on another login needs its own copy of the code, environment and caches.
- QOS limits are per user, so each extra login adds its own 10 CPU / 1 GPU allowance. The course login's 1-job and
  6-hour limits mean only short or resumable jobs fit there (training jobs must checkpoint and resume, see `scripts/ada/t1_train.sbatch`).
- The GPU budget (decision D21, below) is counted per block of work across **all** logins.
- The teammate login has the same QOS as the primary and the most free disk (about 38 GB). Work under a project
  directory (e.g. `~/ril_*`) and never touch the owner's existing files.
- Record which login and node a run used in its log; hardware comparisons follow the rule above.
- Optional convenience: extra `~/.ssh/config` host entries (e.g. `Host ada2` with `User [login]`, `Host ada3` with
  `User [login]` and `IdentityFile ~/.ssh/[key]`) so scripts can say `ssh ada2` / `ssh ada3`.

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
| 2026-10-25 | Course login `[login]`: `ssh -o BatchMode=yes` works on `ada-gw1` and `ada-gw2` (key auth); account `[course]`, QOS `[course]` = `cpu=10,gres/gpu=1` per user, 1 job, 6 h wall time, priority 0; `$HOME` `/home2/[login]` 25 GB, 0% used; login node Python 3.9.25; `sinfo` lists u22 (77 nodes), u22-cpu, ihub, plafnet2, rrc. Partition access for this account not yet tested with a job | verified |
| 2026-10-25 | Teammate login `[login]` (key `~/.ssh/[key]`): `ssh -o BatchMode=yes` works on `ada-gw1` and `ada-gw2`; account `research`, QOS `low` = `cpu=10,gres/gpu=1,mem=32000M` per user, 5 jobs, 4-day wall time, priority 10; `$HOME` `/home2/[login]` 50 GB, 13 GB used, 38 GB free; no jobs queued. Not yet tested with a job | verified |
| 2026-10-29 | Full contamination scan (u22, qos low, account A, `~/ril_c/`, CPU only): 240 shards, 306.6 GB streamed, 17.9 worker-hours summed over shards; two 4-CPU jobs of 120 shards ran side by side on gnode002 in 2 h 13 min and 2 h 06 min (MaxRSS 4.7 GB and 1.7 GB, 8 GB requested); transient `Name or service not known` errors failed one shard after three attempts (rerun as its own job); a third job with 3 CPUs next to two 4-CPU jobs waited on `QOSMaxCpuPerUserLimit` (10), resubmitted with 2 CPUs and `--mem=3G` it started at once; `$HOME` stayed at about 1.0 GB free (`~/ril_c/out` 207 MB after the scan, of which the base-commit hash file is 154 MB gzipped) | measured, jobs 45620, 45621, 45623, 45774 |
| 2026-10-29 | Graph-role measurement S1 (u22, qos low, account A, `~/ril_x2/`, CPU only, 4 CPU, 195 MB peak resident, 8.1 min for four configurations, no GPU): first two submissions failed in seconds (a colon in a YAML title; the default `e3_cache` lacks the D18 readings, so the job reads `~/ril_t1/work/e3_cache`, the D18 cache the training stack evaluates on). Rows in `results/logs/ada_jobs.csv`; sbatch `scripts/ada/s1_graph_role.sbatch`. 0.0 GPU-hours. |
| 2026-10-29 | Training-step jobs of E7 (u22, qos low, `~/ril_t1/`, base environment of `~/ril_x2`): `--export=ALL,KEY=a,b` splits at the commas, so a shape list like `4,1,1,512` loses everything after the first comma (use `/` and convert inside the script); a for-loop over a quoted default that holds several words runs one process for all of them, and an out-of-memory shape then leaves its peak in the next shape's row (one process per shape, as T1 had already learned); a 2-CPU 8 GB request starts next to a 6-CPU job where a 4-CPU 16 GB request (rounded to 6) waits on `QOSMaxCpuPerUserLimit`; `sinfo` shows no card with more than 11 GB reachable from account `research` (`sbatch --test-only -p ihub|plafnet2|rrc` is refused: "Invalid account or account/partition combination"; the unlabelled `u22` nodes expose no card type); `$HOME` had 1.0 GB free | measured, jobs 46134, 46180, 46183 |
