# Qwen3.5-2B persistent RSI design

User intent: extract measurable capability and efficiency from Qwen3.5-2B on small hardware and preserve Internet-side research when the local machine is off. No replacement model, frontier-equivalence claim, arbitrary computer control, or fabricated training.

## Inspected environment
Empty Git repository (no remote or commits). Windows, i7-1360P, 32 GB RAM, Intel integrated graphics, approximately 10 GB free RAM. Ollama 0.33.3, Python 3.11.15, Node 26.5.0, authenticated GitHub CLI. Wrangler OAuth configuration exists; account access still to be verified. Existing 4B model is not the selected model and will not be used.

## First end-to-end slice
Ollama `qwen3.5:2b-q4_K_M`, four CPU threads, context 2048, one inference at a time, bounded outputs and a memory headroom check. Record actual model digest, parameter size, quantization, Ollama version, code commit, evaluation hash, prompt and options. Python standard library implementation avoids installing into another application's Python environment.

Cloudflare Worker coordinates authenticated clients and scheduled maintenance, with a SQLite-backed Durable Object as Internet authority. SQLite is the standalone local authority when no coordinator is configured. A cloud-connected client may cache evidence but never starts an independent offline cycle. Jobs use expiring leases with fencing tokens; checkpoint after every inference, renew before slow work, and retry only idempotent writes. Cloud failure stops connected work without inventing a successful upload. Completion and creation of the next job are recoverable. Last validated configuration remains separate from candidates.

GitHub public source repository and Pages are intentionally within the user's requested deployment scope. Only synthetic benchmark research is public. No tokens, private memory, or computer paths in public output. Actions has read-only source permissions, except Pages deployment, uses an authenticated coordinator token from GitHub Secrets, runs CPU inference on hosted Linux, and publishes durable results to durable storage. A six-hour schedule bounds inference to four runs/day; Worker cron creates or recovers work, independent of the PC. No Workers LLM hosting or Pages server execution claim. Standard runner availability and scheduler timing are not guaranteed.

## Actual RSI cycle
Observe aggregate failure categories and current configuration. Ask Qwen3.5-2B for a JSON hypothesis and candidate system prompt/thinking configuration, excluding evaluation answers. Validate a narrow schema and bounds. Compare baseline and candidate on exactly the same newly generated, seeded holdout tasks and same runtime fingerprint. Tasks exercise arithmetic reasoning, instruction following, pure Python coding, dependency planning, memory retrieval, calculator tool use and bounded multi-step agent execution. Tools are arithmetic and episode-local memory only. Model-generated code is interpreted through a restricted AST; it is never executed by Python or a shell.

Checkpoint proposals, every task output, failures, latency, token usage, available memory and runtime model allocation. Server-side promotion gate requires complete paired evidence, no individual task regression, no category regression, and either improved success with acceptable latency or equal quality with at least 10% lower warm latency. Unknown electricity, cloud billing and VRAM values are null, never zero. Reject ties and regressions; accepted changes are labeled system or execution improvements, never model weight improvements. Reports include capability per token, per second, per GB and cost when known.

## Evaluation integrity and limits
Fresh deterministic holdout seed per cycle; generators and suite are versioned. Proposal gets categories and aggregate weaknesses, not heldout prompts, answers or previous output. Baseline and candidate alternate order across tasks to reduce warm-up bias. This small smoke suite establishes plumbing and exploratory evidence, not general intelligence. Public generator tasks are not a hidden external benchmark; repeated optimization can overfit. Broader private independent evaluation and repeated seeds are required for research-grade claims.

## Model experiments
Preserve resource-gated LoRA jobs requiring a compatible CUDA GPU and explicit resource budget; no training is run on this integrated-GPU laptop. An optional training entry point must use Qwen/Qwen3.5-2B and pinned dataset/model identities. Adapter promotion requires the same paired holdout gate and separate model-change provenance. Until training can actually be run and evaluated, jobs remain blocked and no model-improvement claim is made.

## Recovery, control and costs
Restart resumes an unexpired owned job or reclaims after expiration. Partial work never promotes; duplicate completion is idempotent. Stale workers cannot mutate current jobs. A pause control prevents new leasing; existing work can checkpoint. Credentials remain ignored local files, Cloudflare secrets and GitHub Secrets. No arbitrary program execution or public write permission. Daily cycle ceiling, bounded retry and timeout limits prevent unbounded work. Retain every cycle and result in durable storage plus exportable evidence. Database retention is subject to service limits; expose status rather than deleting history automatically.

## Acceptance
Real selected-model local inference; real paired cycle recorded; next cycle queued and exercised; actual cloud coordinator deployed and authenticated; Pages reachable; hosted Actions inference completes without a local endpoint; recovery, fencing, promotion rejection and secret hygiene tests pass. Missing credentials or unavailable service must be reported as unfinished, with concrete deployment artifacts preserved.

## Alternatives considered
Local-only SQLite cannot operate while the PC is off. GitHub-only state commits introduce conflicts and rely on Actions for coordination. Worker+Durable Object plus compute clients is selected for durable leases, low fixed cost and small scope.

User's explicit autonomous development/build/run/test/commit/continue command authorizes implementing and deploying this slice. Implement inline; no repeated design approvals.
