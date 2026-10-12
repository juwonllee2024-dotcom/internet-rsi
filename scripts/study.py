"""Owner control for a temporary, bounded public-repository research study."""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rsi.__main__ import load_env
from rsi.remote import RemoteStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    parser.add_argument('--hours', type=int, default=24)
    parser.add_argument('--cycles', type=int, default=48)
    args = parser.parse_args()
    if not 1 <= args.hours <= 24 or not 1 <= args.cycles <= 48:
        parser.error('hours must be 1..24; cycles must be 1..48')
    load_env()
    store = RemoteStore(os.environ['RSI_URL'], os.environ['RSI_TOKEN'])
    if args.action == 'start':
        request = urllib.request.Request('https://api.github.com/repos/juwonllee2024-dotcom/internet-rsi', headers={'User-Agent': 'internet-rsi/0.1'})
        with urllib.request.urlopen(request, timeout=30) as response:
            repository = json.load(response)
        if repository.get('private') is not False or repository.get('disabled'):
            raise RuntimeError('Study requires the enabled public repository and standard hosted runner')
        result = store.request('/study', dict(hours=args.hours, max_cycles=args.cycles))
    elif args.action == 'stop':
        result = store.request('/study', dict(action='stop'))
    else:
        result = store.status().get('study')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
