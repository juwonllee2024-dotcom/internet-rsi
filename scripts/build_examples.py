"""Publish two Korean explanations of an unchanged, real archived evaluation."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rsi.evaluation import make_suite, suite_hash


def main():
    report = json.loads((ROOT / 'artifacts/cycle-3.json').read_text(encoding='utf-8'))
    suite = make_suite(report['suite_seed'])
    if report['suite_hash'] != suite_hash(suite):
        raise ValueError('Archived suite does not match the current task generator')
    captions = {
        'arithmetic': ('산술 계산 — 괄호와 곱셈', '(23 + 12) × 6의 값은 얼마일까요?'),
        'word-problem': ('생활 속 계산 — 상자에 남은 물건', '상자 23개에 물건이 각각 12개씩 들어 있습니다. 전체에서 물건 6개를 꺼내면 몇 개가 남을까요?'),
    }
    tasks = []
    for task in suite:
        if task['id'] not in captions:
            continue
        label, question = captions[task['id']]
        item = dict(id=task['id'], label_ko=label, question_ko=question,
                    prompt=task['prompt'], expected=task['expected'])
        for side in ('baseline', 'candidate'):
            sample = report['samples'][side][task['id']]
            outputs = [dict(text=output['text'], truncated=output['truncated'])
                       for output in sample['outputs']]
            item[side] = dict(passed=sample['passed'], latency_s=sample['latency_s'],
                              eval_count=sample['eval_count'], outputs=outputs,
                              truncated=any(output['truncated'] for output in outputs))
        tasks.append(item)
    result = dict(cycle=report['job'], suite_version=report['suite_version'], tasks=tasks)
    (ROOT / 'web/examples.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {len(tasks)} archived examples from cycle {report["job"]}.')


if __name__ == '__main__':
    main()
