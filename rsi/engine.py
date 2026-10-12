"""Observe, propose, paired holdout test, gate, record, continue."""
import json
import hashlib
from collections import Counter
from pathlib import Path
from .runtime import MODEL, code_revision, source_dirty, OllamaRuntime
from .evaluation import make_suite, suite_hash, evaluate_task
from .gate import compare


def component_versions(baseline,candidate,identity,revision):
    digest=lambda data:hashlib.sha256(data).hexdigest()
    evaluation=Path(__file__).with_name('evaluation.py').read_bytes()
    return {'model':identity['digest'],'code':revision,'evaluation':digest(evaluation),
            'tools':digest(evaluation),'agents':digest(evaluation),'memory':digest(evaluation),
            'prompts':{'baseline':digest(baseline['system_prompt'].encode()),'candidate':digest(candidate['system_prompt'].encode())},
            'configuration':digest(json.dumps({'baseline':baseline,'candidate':candidate},sort_keys=True).encode())}


def candidate_from_proposal(proposal, baseline):
    if not isinstance(proposal,dict) or set(proposal) != {'hypothesis', 'system_prompt', 'think'}:
        raise ValueError('Proposal must contain only hypothesis, system_prompt, think')
    if (not isinstance(proposal['hypothesis'], str) or not 5 <= len(proposal['hypothesis']) <= 1000
            or not isinstance(proposal['system_prompt'], str) or not 5 <= len(proposal['system_prompt']) <= 1200
            or type(proposal['think']) is not bool):
        raise ValueError('Proposal values outside permitted bounds')
    config = dict(baseline, system_prompt=proposal['system_prompt'], think=proposal['think'])
    if config['model'] != MODEL:
        raise ValueError('Primary model cannot change')
    return {'hypothesis': proposal['hypothesis'], 'config': config, 'change_type': 'system', 'generator': MODEL}


def run_cycle(store, runtime, owner='local-cpu', output_dir=None):
    if isinstance(runtime,OllamaRuntime) and source_dirty():
        raise RuntimeError('Commit runtime source before research; uncommitted source cannot produce reproducible paired evidence')
    job = store.claim(owner)
    if job is None:
        return None
    payload = job['payload']
    identity = runtime.inspect()
    revision = code_revision()
    if payload.get('identity') and (payload['identity'] != identity or payload.get('code_revision',revision) != revision):
        # Preserve partial evidence; remeasure the pair on the new compute client.
        payload=store.restart_attempt(job['id'],job['token'],identity,revision)
    payload['identity'] = identity
    baseline = payload['baseline']['config']
    pinned = payload['baseline'].get('identity', {}).get('digest')
    if pinned and pinned != identity['digest']:
        raise RuntimeError('Downloaded model digest differs from validated model')
    store.checkpoint(job['id'], job['token'], payload)
    if payload['candidate'] is None:
        observations = payload.get('observations', {'targets': ['reasoning', 'coding', 'instruction', 'planning', 'tool', 'memory', 'agent']})
        proposal_prompt = (
            'Propose one small system improvement for Qwen3.5-2B. Return JSON with exactly hypothesis (string), '
            'system_prompt (string, at most 1200 characters), think (boolean). Improve reliable reasoning and JSON tool use. '
            'No evaluation examples are provided. No model replacement or tool additions. Current prompt: '
            + baseline['system_prompt'] + '\nAggregate observations: ' + json.dumps(observations))
        try:
            response = runtime.generate([{'role': 'user', 'content': proposal_prompt}], dict(baseline, num_predict=384))
            payload['proposal_metrics'] = response
            store.checkpoint(job['id'],job['token'],payload)
            if response.get('truncated'):
                raise ValueError('Generated hypothesis truncated')
            payload['candidate'] = candidate_from_proposal(json.loads(response['text']), baseline)
        except (ValueError,KeyError,RuntimeError) as error:
            return store.fail(job['id'],job['token'],type(error).__name__+': '+str(error)[:160])
        store.checkpoint(job['id'], job['token'], payload)
    suite = make_suite(payload['seed'])
    payload['code_revision'] = revision
    payload['suite_version'] = 'synthetic-v2'
    payload['suite_hash'] = suite_hash(suite)
    payload['version_manifest'] = component_versions(baseline,payload['candidate']['config'],identity,revision)
    for index, task in enumerate(suite):
        order = ('baseline', 'candidate') if index % 2 == 0 else ('candidate', 'baseline')
        for variant in order:
            if task['id'] in payload['samples'][variant]:
                continue
            store.checkpoint(job['id'], job['token'], payload)  # renew before bounded inference
            config = baseline if variant == 'baseline' else payload['candidate']['config']
            sample = evaluate_task(runtime, config, task)
            payload['samples'][variant][task['id']] = sample
            store.checkpoint(job['id'], job['token'], payload)
            print(json.dumps({'job': job['id'], 'variant': variant, 'task': task['id'],
                              'passed': sample['passed'], 'latency_s': round(sample['latency_s'], 3),
                              'error': sample['error']}), flush=True)
    decision = compare(list(payload['samples']['baseline'].values()), list(payload['samples']['candidate'].values()),
                       [t['id'] for t in suite])
    report = {'job': job['id'], 'baseline_version': payload['baseline']['version'],
              'baseline_config': baseline, 'candidate_config': payload['candidate']['config'],
              'hypothesis': payload['candidate']['hypothesis'], 'change_type': 'system',
              'identity': identity, 'code_revision': revision, 'suite_version': 'synthetic-v2',
              'suite_seed': payload['seed'], 'suite_hash': suite_hash(suite), 'samples': payload['samples'],
              'proposal_metrics': payload.get('proposal_metrics'), 'decision': decision,
              'version_manifest':payload['version_manifest'],
              'attempts':payload.get('attempts',[]),
              'limitations': 'Exploratory synthetic holdout, one seed, no frontier/AGI or model-weight improvement claim.',
              'resource_metrics': {'cost_usd': None, 'energy_joules': None}}
    # Evidence reaches local disk before completion is submitted. Failed upload remains recoverable.
    if output_dir:
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f'cycle-{job["id"]}.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        temporary.replace(target)
    report['decision'] = store.finish(job['id'], job['token'], report)
    print(json.dumps({'job': job['id'], 'decision': report['decision']}), flush=True)
    return report
