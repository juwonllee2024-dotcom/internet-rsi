"""Set project-scoped secrets via stdin; never print credentials."""
import argparse
import json
import secrets
import subprocess
import shutil
from pathlib import Path


def run(arguments, input_text=None):
    prefix = ['rtk', 'proxy'] if shutil.which('rtk') else []
    result = subprocess.run(prefix + arguments, input=input_text, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if result.returncode:
        raise RuntimeError('Configuration failed: ' + ' '.join(arguments[:3]) + '\n' + result.stderr[-1000:])
    print('Configured ' + ' '.join(arguments[:3]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('coordinator')
    parser.add_argument('--repo',default='juwonllee2024-dotcom/internet-rsi')
    parser.add_argument('--local-only',action='store_true')
    args=parser.parse_args()
    if not args.coordinator.startswith('https://'):
        parser.error('HTTPS coordinator required')
    path=Path('.env')
    existing={}
    if path.exists():
        existing=dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
    token=existing.get('RSI_TOKEN') or secrets.token_urlsafe(32)
    path.write_text('RSI_URL='+args.coordinator+'\nRSI_TOKEN='+token+'\n',encoding='utf-8')
    Path('.dev.vars').write_text('RSI_TOKEN='+token+'\n',encoding='utf-8')
    Path('web/config.json').write_text(json.dumps({'coordinator':args.coordinator})+'\n',encoding='utf-8')
    if not args.local_only:
        run(['npx','wrangler','secret','put','RSI_TOKEN'],token+'\n')
        run(['gh','secret','set','RSI_TOKEN','--repo',args.repo],token)
        run(['gh','variable','set','RSI_URL','--repo',args.repo,'--body',args.coordinator])
    print('Project configuration saved. Token stays private in ignored .env and service secret stores.')


if __name__=='__main__':
    main()
