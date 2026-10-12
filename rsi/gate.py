"""Conservative exploratory promotion gate. No model-generated self-grading."""
import math
import statistics


def compare(baseline, candidate, expected_ids=None):
    reject = lambda reason: {'accepted': False, 'kind': None, 'reason': reason}
    expected = set(expected_ids if expected_ids is not None else [x['id'] for x in baseline])
    if not expected or len(baseline) != len(expected) or len(candidate) != len(expected):
        return reject('incomplete paired evidence')
    for group in (baseline, candidate):
        if {x.get('id') for x in group} != expected:
            return reject('mismatched or duplicate tasks')
        for x in group:
            latency = x.get('latency_s')
            if (type(x.get('passed')) is not bool or not isinstance(latency, (float, int))
                    or not math.isfinite(latency) or latency <= 0
                    or type(x.get('eval_count')) is not int or x['eval_count'] < 0):
                return reject('invalid metrics')
    old = {x['id']: x for x in baseline}
    new = {x['id']: x for x in candidate}
    if any(old[k]['category'] != new[k]['category'] for k in expected):
        return reject('category mismatch')
    if any(old[k]['passed'] and not new[k]['passed'] for k in expected):
        return reject('individual task regression')
    if any(x.get('error') for x in candidate):
        return reject('candidate execution failure')
    quality_old = sum(x['passed'] for x in baseline) / len(baseline)
    quality_new = sum(x['passed'] for x in candidate) / len(candidate)
    latency_old = statistics.median(x['latency_s'] for x in baseline)
    latency_new = statistics.median(x['latency_s'] for x in candidate)
    metrics = {'baseline_score': quality_old, 'candidate_score': quality_new,
               'baseline_latency_s': latency_old, 'candidate_latency_s': latency_new}
    if quality_new > quality_old and latency_new <= latency_old * 1.5:
        return dict(accepted=True, kind='system', reason='higher holdout success; no task regression', **metrics)
    if quality_new == quality_old and quality_new > 0 and latency_new <= latency_old * 0.9:
        return dict(accepted=True, kind='execution', reason='equal holdout success; lower median latency', **metrics)
    return dict(accepted=False, kind=None, reason='no qualifying improvement', **metrics)
