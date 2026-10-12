# Persistent RSI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. User requested autonomous build, run, test, measure, fix, verify, commit, continue.

**Goal:** Execute and record a real Qwen3.5-2B paired experiment and continue through durable Internet coordination.

**Architecture:** Python bounded inference/evaluation client, SQLite standalone state, Cloudflare Worker+Durable Object Internet authority, GitHub Actions CPU compute, GitHub Pages dashboard.

**Tech Stack:** Python standard library, Ollama, JavaScript, Wrangler 4.149.0, SQLite-backed Durable Object, GitHub Actions/Pages.

**Spec:** docs/superpowers/specs/2026-10-12-internet-rsi-design.md

## Global Constraints
- Qwen3.5-2B only. Preserve validated baseline. No arbitrary shell/code execution.
- One inference at a time, four CPU threads, 2048 context, bounded tokens.
- Missing measurements are null; no fabricated success, billing or training.
- Holdout separation, complete paired evidence and no regression are mandatory.
- Internet state is authoritative when configured; credentials never public.

## Review Focus
- Stale lease after restart must reject checkpoint and promotion.
- Partial/duplicate results must not replace stable configuration or lose next task.
- Failed network upload must preserve local evidence and report failure.
- Malicious model output must not access files, network, imports or the host shell.
- Incomplete/invalid metric evidence must reject promotion.

### Task 1: Local runtime and safe evaluation
Files: `rsi/runtime.py`, `rsi/evaluation.py`, `rsi/gate.py`, `tests/test_evaluation.py`, `tests/test_gate.py`.
Interfaces: `OllamaRuntime.generate(messages, config) -> dict`; `make_suite(seed) -> list[dict]`; `evaluate_task(runtime, config, task) -> dict`; `compare(baseline, candidate) -> dict`.
- [x] Write failing tests for arithmetic/code isolation, repeatable seeded tasks, strict paired gate, regression and incomplete metrics.
- [x] Run `rtk proxy python -m unittest discover -s tests -v`, verify RED.
- [x] Implement restricted tools/AST and actual Ollama metrics; verify GREEN and selected-model smoke inference.
- [x] Commit local evaluation slice.

### Task 2: Persistent resumable RSI
Files: `rsi/store.py`, `rsi/engine.py`, `rsi/__main__.py`, `tests/test_store.py`, `tests/test_engine.py`.
Interfaces: store `claim(owner)`, `checkpoint(job, token, payload)`, `finish(job, token, report)`; `run_cycle(store, runtime, owner)`.
- [x] Write RED tests for lease expiration/fencing, checkpoint restart, duplicate finish, stable-version retention and completed paired cycles.
- [x] Implement SQLite authority, deterministic job seeds, narrow Qwen hypothesis schema, checkpoint every sample, safe comparison, next queued cycle.
- [x] Verify GREEN, run real local paired experiment, save evidence and queue next.
- [x] Commit persistent core.

### Task 3: Internet coordination
Files: `cloud/worker.js`, `cloud/schema.sql`, `wrangler.jsonc`, `package.json`, `tests/cloud.test.mjs`, `rsi/remote.py`.
- [x] RED tests for authenticated control, Durable Object leases and invalid/duplicate completion on a real local Worker.
- [x] Implement Worker Durable Object state, cron recovery, authenticated claim/checkpoint/completion/status/pause; use lease fencing and recompute promotion at coordinator.
- [x] Test real Wrangler/Durable Object integration and remote Python cycle.
- [x] Deploy Worker/Durable Object through existing authentication; keep secrets private. Commit.

### Task 4: GitHub, Pages and independent compute
Files: `.github/workflows/check.yml`, `.github/workflows/rsi.yml`, `.github/workflows/pages.yml`, `web/index.html`, `scripts/deploy.py`, README and research evidence.
- [x] Build authenticated status/control interface with session-only token storage.
- [x] Create requested GitHub project, push verified source, enable Pages and configure coordinator secrets.
- [x] Run bounded hosted CPU inference workflow with chosen quantized model; record results in durable storage. Verify public page and next job.
- [x] Verify recovery and full suite, update evidence and commit.

### Task 5: Resource-gated model experiments and research continuation
Files: `training/lora.py`, `training/README.md`, `docs/research-status.md`.
- [x] Test resource admission and base-model constraints before optional trainer implementation.
- [x] Preserve blocked training job with explicit CUDA/memory/dataset requirements. No unverified adapter promotion.
- [x] Fresh review of whole change, repair important findings, verify suite and deployment, commit final evidence.
