"""Required provenance for promotion; measurements originate in trusted graders."""
import re

CATEGORIES={'arithmetic':'reasoning','word-problem':'reasoning','instruction':'instruction','code':'coding',
            'plan':'planning','calculator':'tool','recall':'memory','agent':'agent'}


def evidence_error(report):
    if report.get('baseline_config')==report.get('candidate_config'):
        return 'no controlled configuration change'
    identity=report.get('identity',{})
    if identity.get('model')!='qwen3.5:2b-q4_K_M' or not re.fullmatch('[a-f0-9]{64}',identity.get('digest','')):
        return 'invalid model identity'
    if not re.fullmatch('[a-f0-9]{40}',report.get('code_revision','')) or not re.fullmatch('[a-f0-9]{64}',report.get('suite_hash','')):
        return 'missing immutable code or suite identity'
    if report.get('suite_version') not in ('synthetic-v1','synthetic-v2') or not isinstance(report.get('hypothesis'),str):
        return 'missing hypothesis or suite version'
    if not isinstance(report.get('proposal_metrics',{}).get('text'),str):
        return 'missing generated proposal evidence'
    if report['suite_version']=='synthetic-v2':
        hardware=identity.get('hardware',{})
        if not hardware.get('cpu') or not re.fullmatch('[a-f0-9]{64}',hardware.get('host_hash','')) or not report.get('version_manifest'):
            return 'missing hardware or component versions'
        manifest=report['version_manifest']
        if manifest.get('model')!=identity['digest'] or manifest.get('code')!=report['code_revision']:
            return 'component identity mismatch'
        for key in ('evaluation','tools','agents','memory','configuration'):
            if not re.fullmatch('[a-f0-9]{64}',manifest.get(key,'')):return 'incomplete component manifest'
        for key in ('baseline','candidate'):
            if not re.fullmatch('[a-f0-9]{64}',manifest.get('prompts',{}).get(key,'')):return 'incomplete prompt manifest'
    for variant in ('baseline','candidate'):
        samples=report.get('samples',{}).get(variant,{})
        if set(samples)!=set(CATEGORIES):return 'incomplete sample set'
        for name,sample in samples.items():
            if sample.get('id')!=name or sample.get('category')!=CATEGORIES[name] or type(sample.get('passed')) is not bool:
                return 'invalid task identity or category'
            outputs=sample.get('outputs')
            if not isinstance(outputs,list):return 'missing inference evidence'
            if sample['passed'] and (not outputs or sample.get('eval_count',0)<=0 or sample.get('error')):
                return 'success without completed inference'
            if sample['passed'] and any(x.get('truncated') for x in outputs):return 'success from truncated inference'
            if any(not isinstance(x.get('text'),str) or type(x.get('eval_count')) is not int for x in outputs):
                return 'invalid inference output'
            if sum(x['eval_count'] for x in outputs)!=sample.get('eval_count'):return 'inconsistent token usage'
    return None
