import argparse
import json
import os
import time
from .lock import ClientLock
from pathlib import Path
from .runtime import OllamaRuntime, BASE_CONFIG
from .store import Store
from .engine import run_cycle


def load_env():
    path = Path('.env')
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


def main():
    # Run/doctor both infer; read-only status/control commands may run concurrently.
    import sys
    if len(sys.argv)>1 and sys.argv[1] in ('run','doctor'):
        with ClientLock():return execute()
    return execute()


def execute():
    load_env()
    parser = argparse.ArgumentParser(description='Measured Qwen3.5-2B RSI')
    parser.add_argument('command', choices=['doctor', 'run', 'status', 'pause', 'resume', 'export'])
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--continuous', action='store_true')
    parser.add_argument('--owner', default='local-cpu')
    parser.add_argument('--local', action='store_true', help='Explicit standalone authority; do not use for cloud synchronization')
    parser.add_argument('--job', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 4:
        parser.error('cycles must be 1..4 per invocation')
    runtime = OllamaRuntime(os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434'))
    if args.command == 'doctor':
        identity = runtime.inspect()
        smoke = runtime.generate([{'role': 'user', 'content': 'Return JSON: answer is 42.'}], BASE_CONFIG)
        print(json.dumps({'runtime': identity, 'smoke': smoke}, indent=2))
        return
    endpoint = os.environ.get('RSI_URL')
    if endpoint and not args.local:
        from .remote import RemoteStore
        store = RemoteStore(endpoint, os.environ.get('RSI_TOKEN', ''))
    else:
        store = Store(os.environ.get('RSI_DB', '.state/research.sqlite'))
    if args.command in ('pause', 'resume'):
        store.pause(args.command == 'pause')
    elif args.command == 'status':
        print(json.dumps(store.status(), indent=2))
    elif args.command == 'export':
        print(json.dumps(store.export(args.job), indent=2))
    elif args.command == 'run':
        while True:
            for _ in range(args.cycles):
                if run_cycle(store, runtime, args.owner, 'artifacts/private') is None:
                    print('No eligible job: paused, leased, or daily budget reached.', flush=True)
                    break
            if not args.continuous:
                break
            time.sleep(900)  # explicit user-started daemon; no OS startup/service changes


if __name__ == '__main__':
    main()
