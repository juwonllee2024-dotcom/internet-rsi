"""Export synthetic research evidence and a concise measured summary."""
import json
import os
import statistics
from pathlib import Path
from rsi.__main__ import load_env
from rsi.remote import RemoteStore

load_env()
store=RemoteStore(os.environ['RSI_URL'],os.environ['RSI_TOKEN'])
summaries=[]
for job in store.status()['jobs']:
    if job['status'] not in ('done','failed'):continue
    report=store.export(job['id'])
    if not report:continue
    Path('artifacts').mkdir(exist_ok=True)
    Path(f'artifacts/cycle-{job["id"]}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    summary={'cycle':job['id'],'suite_version':report.get('suite_version'),'decision':report['decision'],'variants':{}}
    for name,samples in report.get('samples',{}).items():
        rows=list(samples.values())
        if not rows:continue
        durations=[r['latency_s'] for r in rows]
        tokens=sum(r['eval_count'] for r in rows)
        coverage=not any(r.get('error') and not r.get('outputs') for r in rows)
        passed=sum(r['passed'] for r in rows)
        allocations=[o.get('model_allocated_bytes') for r in rows for o in r.get('outputs',[]) if o.get('model_allocated_bytes') is not None]
        peak=max(allocations) if allocations else None
        summary['variants'][name]={'successes':passed,'tasks':len(rows),'median_latency_s':statistics.median(durations),
            'total_latency_s':sum(durations),'generated_tokens_observed':tokens,'token_count_complete':coverage,'successful_tasks_per_1000_output_tokens':passed*1000/tokens if tokens and coverage else None,
            'successful_tasks_per_second':passed/sum(durations),'peak_model_allocated_bytes_observed':peak,
            'success_rate_per_gib_model_allocation':(passed/len(rows))/(peak/1024**3) if peak else None,
            'failures':len(rows)-passed,'cost_usd':None,'energy_joules':None}
    summaries.append(summary)
Path('artifacts/summary.json').write_text(json.dumps(summaries,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summaries))
