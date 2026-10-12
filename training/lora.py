"""Resource admission and optional bounded LoRA. No automatic adapter promotion."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

BASE_MODEL='Qwen/Qwen3.5-2B'


def admission(job, cuda, vram_gb):
    if job.get('base_model') != BASE_MODEL:
        raise ValueError('Only Qwen/Qwen3.5-2B is permitted')
    if not re.fullmatch('[a-f0-9]{40}',job.get('model_revision','')):
        raise ValueError('Immutable model revision required')
    if not re.fullmatch('[a-f0-9]{64}',job.get('dataset_sha256','')):
        raise ValueError('Pinned dataset hash required')
    if type(job.get('max_steps')) is not int or not 1 <= job['max_steps'] <= 100:
        raise ValueError('Training budget must be 1..100 optimizer steps')
    if not cuda or vram_gb < 8:
        return {'eligible':False,'status':'blocked','reason':'Requires CUDA and at least 8 GiB VRAM; no training performed'}
    return {'eligible':True,'status':'ready','reason':'Resources satisfy admission; actual training and evaluation still required'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--job',default='training/experiment.json')
    parser.add_argument('--execute',action='store_true',help='Run optional training only on compatible provisioned compute')
    parser.add_argument('--output',default='.state/adapters/candidate-1')
    args=parser.parse_args()
    job=json.loads(Path(args.job).read_text())
    cuda,vram=False,0
    if importlib.util.find_spec('torch'):
        import torch
        cuda=torch.cuda.is_available()
        if cuda:vram=torch.cuda.get_device_properties(0).total_memory/1024**3
    status=admission(job,cuda,vram)
    print(json.dumps(status))
    if not args.execute or not status['eligible']:
        return
    # These optional dependencies belong in a project-specific environment on CUDA compute.
    from peft import LoraConfig,get_peft_model
    from transformers import AutoTokenizer,Qwen3_5ForConditionalGeneration
    import torch
    data_path=Path(job['dataset'])
    if hashlib.sha256(data_path.read_bytes()).hexdigest() != job['dataset_sha256']:
        raise ValueError('Dataset changed since job was queued')
    output=Path(args.output).resolve()
    root=Path.cwd().resolve()
    if not output.is_relative_to(root) or output.exists():
        raise ValueError('New output directory within this checkout required')
    tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,revision=job['model_revision'],trust_remote_code=False)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model=Qwen3_5ForConditionalGeneration.from_pretrained(BASE_MODEL,revision=job['model_revision'],torch_dtype=dtype,trust_remote_code=False)
    model=get_peft_model(model,LoraConfig(r=4,lora_alpha=8,lora_dropout=0.05,target_modules=['q_proj','v_proj']))
    model.gradient_checkpointing_enable();model.enable_input_require_grads();model.config.use_cache=False;model.to('cuda');model.train()
    rows=[json.loads(line) for line in data_path.read_text().splitlines() if line.strip()]
    if not rows or len(rows)>1000:raise ValueError('Development dataset must contain 1..1000 rows')
    optimizer=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=1e-4)
    losses=[]
    for step in range(job['max_steps']):
        row=rows[step%len(rows)]
        text=tokenizer.apply_chat_template(row['messages'],tokenize=False,add_generation_prompt=False,enable_thinking=False)
        encoded=tokenizer(text,return_tensors='pt',truncation=True,max_length=256).to('cuda')
        # Tiny development experiment; full-sequence SFT, not a capability benchmark.
        loss=model(**encoded,labels=encoded['input_ids']).loss
        if not torch.isfinite(loss):raise RuntimeError('Non-finite loss; adapter not saved')
        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();optimizer.zero_grad()
        losses.append(float(loss.detach().cpu()))
    output.mkdir(parents=True)
    model.save_pretrained(output)
    (output/'provenance.json').write_text(json.dumps({'job':job,'losses':losses,'peak_vram_bytes':torch.cuda.max_memory_allocated(),
        'status':'unvalidated_adapter','promotion':'requires compatible adapter inference and independent paired holdout'},indent=2))
    print('Unvalidated adapter saved. Stable model unchanged.')


if __name__=='__main__':main()
