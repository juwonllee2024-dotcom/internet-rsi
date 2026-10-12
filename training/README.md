# Resource-gated model experiments

The inspected laptop has an Intel integrated GPU. No CUDA training was run. `experiment.json` pins Qwen/Qwen3.5-2B to an immutable Hugging Face revision and hashes a separate, tiny development dataset. This dataset is a plumbing example, not evidence of learning or a recommended training corpus.

Admission checks and Internet queue records are tested. The optional GPU training path is **not hardware-validated in this session**. Run it only on intentionally provisioned compatible CUDA compute, in its own Python environment with PyTorch, Transformers supporting Qwen3.5 and PEFT. No optional dependencies were installed into the laptop's existing Python environments.

```powershell
rtk proxy python -m training.lora
# Future compatible CUDA environment only:
rtk proxy python -m training.lora --execute --output .state/adapters/candidate-1
```

Training uses 20 optimizer steps, rank-4 LoRA, batch size one and 256-token sequences. Eight GiB VRAM is an admission floor, not a promise that every CUDA setup fits. An OOM remains a failed experiment. Output is a separate unvalidated adapter with loss and peak-VRAM provenance. It is never applied to the validated Ollama model automatically.

Full model-level RSI remains resource blocked: provide compatible compute, a meaningful clean training dataset, a tested adapter inference backend and paired holdouts against unchanged weights. Until those run, no model-improvement claim or adapter promotion is allowed. Cloudflare and standard hosted Actions CPU runners are not GPU training services.
