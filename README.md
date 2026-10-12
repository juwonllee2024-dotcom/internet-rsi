# Qwen3.5-2B persistent RSI

**한국어 설명과 사용법: [README.ko.md](README.ko.md)** · [한국어 실험실](https://juwonllee2024-dotcom.github.io/internet-rsi/)

A small experimental system using **Qwen3.5-2B**, local CPU inference, Internet coordination, controlled paired evaluation and recoverable research history. No claim of AGI, frontier equivalence or model-weight improvement.

Live interface: https://juwonllee2024-dotcom.github.io/internet-rsi/

Coordinator: https://internet-rsi.juwonllee2026.workers.dev/status

## What actually runs

- Ollama `qwen3.5:2b-q4_K_M`, one inference at a time, four threads, 2048-token context, bounded output. Approximately 1.95 GB model download on the inspected system.
- Python standard-library runtime, seeded synthetic holdout generation, isolated arithmetic and memory tools, pure numeric Python AST interpreter (never `exec`, `eval` or model-generated shell commands).
- Qwen generates a hypothesis, system prompt and thinking setting. The selected model and runtime limits cannot change through this search.
- Baseline and candidate run the same eight tasks. Graders measure reasoning, instruction following, coding, planning, calculator use, memory retrieval and a multi-step agent episode.
- Complete paired evidence is required. Individual regressions, candidate execution errors, truncation, ties and invalid measurements reject promotion. More successful tasks must fit a 1.5x median-latency ceiling; equal quality must improve median latency at least 10%.
- SQLite standalone state; authenticated Cloudflare Worker with **SQLite-backed Durable Object** as Internet authority. D1 was initially considered, but the available OAuth credential lacks its scope. The deployed Durable Object uses existing Workers permission and preserves state transactionally.
- Every sample checkpoints before/after inference, with a private on-disk outbox before Internet writes. Leases expire after 20 minutes and use fencing tokens plus distinct client sessions. An OS lock allows one inference client per checkout. Compute/source handoff archives partial measurements and remeasures the pair; completed cycles remain intact. Research refuses uncommitted runtime source.
- GitHub Actions runs bounded hosted CPU inference every six hours, independent of this PC. Cloudflare cron maintains the queue every 15 minutes. Pages serves the interface and authenticated pause/resume controls.

## Local use

Python 3.11+ and existing Ollama are required. No pip packages are needed for inference/evaluation. RTK prefixes follow this workspace's user rule; Actions uses native binaries on its disposable runner.

```powershell
rtk proxy ollama pull qwen3.5:2b-q4_K_M
rtk proxy python -m rsi doctor
rtk proxy python -m rsi status
rtk proxy python -m rsi run --cycles 1
```

Ignored `.env` contains the deployed `RSI_URL` and private `RSI_TOKEN`. With that file, local commands synchronize with Internet authority. A failed cloud connection does **not** silently create a conflicting local research branch. `--local` explicitly selects the separate SQLite authority for standalone work.

```powershell
rtk proxy python -m rsi run --local --cycles 1
rtk proxy python -m rsi export --job 1
rtk proxy python -m rsi pause
rtk proxy python -m rsi resume
```

`run --continuous` starts a user-invoked loop; it does not install a startup service or change operating-system settings. Default runs end after one cycle. Four completed Internet cycles/day and a 30-minute Actions job timeout limit ongoing compute. Local inference defers below 5 GiB available RAM. This is a headroom guard, not a universal hardware compatibility promise.

## Reproducible verification

```powershell
rtk proxy python -m unittest discover -s tests -q
rtk proxy npm ci --ignore-scripts
rtk proxy npm test
rtk proxy npx wrangler deploy --dry-run
```

Node tests run the actual Worker in Miniflare with real SQLite-backed durable storage. Infrastructure fixtures never enter research history. Python tests cover restricted tools, promotion, restart, stale fencing, handoff, partial evidence, pause and CLI encoding.

## Deployment

Source is in the requested GitHub repository. `wrangler.jsonc` binds one Durable Object and scheduled maintenance. Wrangler 4.149.0 is locked. Project secrets are configured through stdin:

```powershell
rtk proxy npx wrangler deploy
rtk proxy python scripts/configure.py https://internet-rsi.juwonllee2026.workers.dev
```

The script sets the Cloudflare secret, GitHub Actions secret and coordinator variable. It never commits or prints the token. The page's control token is held only in memory; refresh/close clears it. Public status contains only synthetic research metadata. GitHub Pages is a static interface; no LLM runs there or inside the coordinator Worker.

Manual hosted run:

```powershell
rtk proxy gh workflow run rsi.yml --repo juwonllee2024-dotcom/internet-rsi
```

GitHub schedules can be delayed/dropped; public-repo schedules are disabled after 60 days without repository activity. The dashboard exposes queued/running progress. See [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). Free service quotas are finite; the system reports errors and retains progress instead of manufacturing output. Durable Objects operate on Workers Free with the SQLite backend; exceeding free quota fails operations ([Cloudflare limits and pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)). No paid GPU is provisioned.

## Evidence and research limitations

`artifacts/cycle-local-1.json` records actual initial local inference. Full Internet reports are available to authorized clients through `/export?job=N`, and completed clients retain an ignored local copy before completion upload. D1 permission failure did not cause research-state loss.

The suite is small, synthetic, deterministic and generated fresh per cycle. Proposal generation gets aggregate weaknesses, not holdout questions/answers. All tooling, prompts, model digests, code commit and suite seed/hash are recorded. This prevents direct copying into proposals but does not prove absence of overfitting to a public generator. Independent private benchmarks, multiple seeds, confidence intervals and larger task sets are required for stronger capability claims.

Power, billing, VRAM and compute quantities that cannot be measured are null. Per-task latency, token counts, inference duration, available memory and model allocation are actual observations. System prompt/tool improvements and execution efficiency are separate from model parameter changes. Training is resource gated; see `training/README.md`.

Credentials, real-user memories, arbitrary computer control and automatic code merging are outside this first loop. Future source and adapter candidates require isolated versions and evaluation before adoption.
