"""One-time import of actual standalone evidence before cloud work starts."""
import json
from pathlib import Path
from rsi.__main__ import load_env
from rsi.remote import RemoteStore
from rsi.store import Store
import os


load_env()
report=Store().export(1)
if not report:
    raise SystemExit('No completed local cycle to import')
remote=RemoteStore(os.environ['RSI_URL'],os.environ['RSI_TOKEN'])
result=remote.request('/import-local',{'report':report})
Path('artifacts').mkdir(exist_ok=True)
Path('artifacts/cycle-local-1.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
