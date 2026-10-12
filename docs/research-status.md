# Verified research status

2026-10-12: Qwen3.5-2B runs locally and on a standard GitHub-hosted Linux CPU runner. Worker plus SQLite-backed Durable Object is deployed; Pages is live. Four Internet cycles/day maximum; no paid GPU provisioned.

| Cycle | Compute | Baseline | Candidate | Decision |
|---|---|---|---|---|
| 1 | Local Windows CPU | 1/8 | 4/8 | Rejected: candidate execution failures |
| 2 | Hosted GitHub Linux CPU | 2/8 | 2/8 | Rejected: individual task regression |
| 3 | Hosted GitHub Linux CPU, repaired synthetic-v2 | 1/8 | 0/8 | Rejected: individual task regression |

No validated improvement established by these three cycles. Last validated system remains version 1; model weights unchanged. Cycle 4 is queued, and the six-hour Actions schedule continues. Cycles remain in cloud history, with exported synthetic evidence under artifacts/.

Initial synthetic-v1 reports lost consumed token counts for truncated outputs because the runtime raised before returning telemetry. Original reports are preserved as historical evidence; summary marks their affected token totals incomplete and omits misleading token-efficiency ratios. Synthetic-v2 retains truncated outputs/token counts and rejects them as successful inference. It also checks real tool arguments/results, fingerprints hardware/source, binds immutable provenance, and archives compute/source handoffs.

Verification: 26 Python tests and 5 Node tests pass, including real SQLite-backed Durable Object acceptance/rejection, auth, token fencing, distinct client sessions, idempotent completion, checkpoint recovery, safe AST, dirty-source detection, local process exclusion and failed-upload outbox persistence. Test fixtures stay inside temporary infrastructure storage and are never research evidence.

Resource-gated LoRA task is preserved, pinned to Qwen/Qwen3.5-2B revision 15852e8c16360a2fea060d615a32b45270f8a8fc and a hashed separate development dataset. Local CUDA admission correctly reports blocked. Optional training path and adapter inference/evaluation remain unverified without compatible CUDA hardware. No trained adapter promoted.

Next work runs automatically through the configured schedule when eligible compute is available. Source changes and hardware handoffs remeasure a partial pair while retaining older evidence. Network failures retain a private checkpoint outbox; expired fencing tokens cannot replay writes. Service outages/quotas can delay progress. Independent external/private evaluations, repeated seeds and confidence intervals remain necessary for general capability claims.

Hosted verification runs: [cycle 2](https://github.com/juwonllee2024-dotcom/internet-rsi/actions/runs/38300453647), [repaired cycle 3](https://github.com/juwonllee2024-dotcom/internet-rsi/actions/runs/38304062374). Cycle 3 completed in 2m27s, used Linux Ollama 0.40.3 and the same pinned Q4_K_M model digest as the local Ollama 0.33.3 run. Both sides of each paired comparison use the same runtime; scores across different suite versions/seeds are not direct controlled comparisons.
