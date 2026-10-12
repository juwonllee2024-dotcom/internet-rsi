"""Ollama client: one bounded request at a time; no provider substitution."""
import ctypes
import hashlib
import json
import os
import platform
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

MODEL = 'qwen3.5:2b-q4_K_M'
BASE_CONFIG = {'model': MODEL, 'system_prompt': 'Follow instructions carefully. Use available tools when needed.',
               'think': False, 'num_ctx': 2048, 'num_predict': 192, 'num_thread': 4, 'temperature': 0, 'seed': 0}


def free_memory_bytes():
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (key, ctypes.c_ulonglong) for key in ('total', 'free', 'page_total', 'page_free', 'virtual', 'virtual_free', 'extended')]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            return memory.free
    elif os.path.exists('/proc/meminfo'):
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) * 1024
    return None


class OllamaRuntime:
    def __init__(self, url='http://127.0.0.1:11434', timeout=180):
        self.url = url.rstrip('/')
        self.timeout = timeout
        self.identity = None

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.url + path, data, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def inspect(self):
        free = free_memory_bytes()
        if free is not None and free < 5 * 1024 ** 3:
            raise RuntimeError('Less than 5 GiB available RAM; inference deferred')
        model = next((x for x in self.request('/api/tags')['models'] if x['name'] == MODEL), None)
        if not model:
            raise RuntimeError('Selected model missing. Run: ollama pull ' + MODEL)
        details = self.request('/api/show', {'model': MODEL})['details']
        cpu=platform.processor()
        if os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo') as info:
                cpu=next((line.split(':',1)[1].strip() for line in info if line.startswith('model name')),cpu)
        hardware={'cpu':cpu,'logical_cpus':os.cpu_count(),'architecture':platform.machine(),
                  'host_hash':hashlib.sha256(socket.gethostname().encode()).hexdigest()}
        source_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
        self.identity = {'model': MODEL, 'digest': model['digest'], 'size_bytes': model['size'], 'hardware':hardware,'source_hash':source_hash,
                         'details': details, 'ollama': self.request('/api/version')['version'],
                         'platform': platform.system(), 'threads': 4}
        return self.identity

    def generate(self, messages, config):
        if config.get('model') != MODEL:
            raise ValueError('Only selected Qwen3.5-2B runtime is allowed')
        started = time.monotonic()
        result = self.request('/api/chat', {
            'model': MODEL, 'messages': messages, 'stream': False, 'format': 'json',
            'think': config['think'], 'keep_alive': '2m',
            'options': {k: config[k] for k in ('num_ctx', 'num_predict', 'num_thread', 'temperature', 'seed')}})
        truncated = not result.get('done') or result.get('done_reason') == 'length'
        try:
            allocated = next((x.get('size') for x in self.request('/api/ps').get('models', []) if x['name'] == MODEL), None)
        except Exception:
            allocated = None  # optional telemetry failure must not erase completed inference
        return {'text': result['message']['content'], 'latency_s': time.monotonic() - started,'truncated':truncated,
                'eval_count': result.get('eval_count', 0), 'prompt_eval_count': result.get('prompt_eval_count', 0),
                'inference_duration_s': result.get('total_duration', 0) / 1e9,
                'model_allocated_bytes': allocated, 'available_memory_bytes': free_memory_bytes(),
                'cost_usd': None, 'energy_joules': None}


def code_revision():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'uncommitted'


def source_dirty(directory='.'):
    try:
        return bool(subprocess.check_output(['git','-C',str(directory),'status','--porcelain','--untracked-files=all','--','rsi'],text=True))
    except (OSError,subprocess.CalledProcessError):
        return True
