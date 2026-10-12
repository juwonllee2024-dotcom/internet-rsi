"""Preserve a pinned model experiment until compatible compute is available."""
import json
import os
from pathlib import Path
from rsi.__main__ import load_env
from rsi.remote import RemoteStore
from training.lora import admission

load_env()
job=json.loads(Path('training/experiment.json').read_text())
admission(job,False,0)
remote=RemoteStore(os.environ['RSI_URL'],os.environ['RSI_TOKEN'])
result=remote.request('/resource-job',{'kind':'lora','model_revision':job['model_revision'],'dataset_sha256':job['dataset_sha256']})
print(json.dumps(result))
