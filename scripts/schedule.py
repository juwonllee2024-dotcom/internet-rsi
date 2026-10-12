"""Cheap preflight: extra scheduled jobs only install inference during a study."""
import json
import os
import time
import urllib.request
from pathlib import Path

BASE_SCHEDULE = '23 */6 * * *'


def eligible(status, event, schedule=None, now=None):
    now = time.time() * 1000 if now is None else now
    study = status.get('study') or {}
    active = (study.get('active') is not False and study.get('started_at', 0) <= now < study.get('ends_at', 0)
              and study.get('completed', 0) < study.get('max_cycles', 0))
    if event == 'schedule' and schedule != BASE_SCHEDULE and not active:
        return False
    if status.get('paused') or status.get('completed_today', 0) >= status.get('daily_cycle_limit', 4):
        return False
    if any(job['status'] == 'running' and job.get('expires', 0) > now for job in status.get('jobs', [])):
        return False
    recovering = any(job['status'] == 'running' and study.get('id')
                     and job.get('study_id') == study['id'] for job in status.get('jobs', []))
    if active and study.get('started', 0) >= study['max_cycles'] and not recovering:
        return False
    return True


def main():
    url = os.environ['RSI_URL'].rstrip('/')
    if not url.startswith('https://'):
        raise ValueError('HTTPS coordinator required')
    request = urllib.request.Request(url + '/status', headers={'User-Agent': 'internet-rsi/0.1'})
    with urllib.request.urlopen(request, timeout=30) as response:
        status = json.load(response)
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event = json.loads(Path(event_path).read_text(encoding='utf-8')) if event_path else {}
    ready = eligible(status, os.environ.get('GITHUB_EVENT_NAME', 'workflow_dispatch'), event.get('schedule'))
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
            output.write(f'eligible={str(ready).lower()}\n')
            study = status.get('study') or {}
            output.write(f'study_id={study["id"] if study.get("active") else ""}\n')
    print('Inference eligible.' if ready else 'No inference: outside study, paused, budget reached, or worker already active.')


if __name__ == '__main__':
    main()
