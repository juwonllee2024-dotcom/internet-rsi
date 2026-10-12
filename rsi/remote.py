"""Internet authority client; failed writes raise and preserve local evidence."""
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


class RemoteStore:
    def __init__(self, url, token, outbox=Path('.state/outbox')):
        if not url.startswith('https://') and not url.startswith('http://127.0.0.1:'):
            raise ValueError('HTTPS coordinator required')
        if len(token) < 24:
            raise ValueError('Coordinator token missing or too short')
        self.url, self.token = url.rstrip('/'), token
        self.session=uuid.uuid4().hex
        self.outbox=Path(outbox)

    def request(self, path, payload=None):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        request=urllib.request.Request(self.url+path,body,{'Content-Type':'application/json','Authorization':'Bearer '+self.token,'User-Agent':'internet-rsi/0.1'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request,timeout=30) as result:
                    return json.load(result)
            except urllib.error.HTTPError as error:
                if error.code < 500:
                    raise RuntimeError(f'Coordinator rejected request ({error.code}): {error.read().decode()[:180]}') from None
                if attempt == 2:
                    raise RuntimeError('Coordinator unavailable; evidence remains local') from None
            except (urllib.error.URLError,TimeoutError):
                if attempt == 2:
                    raise RuntimeError('Coordinator unavailable; evidence remains local') from None
            time.sleep(2**attempt)

    def claim(self,owner): return self.request('/claim',{'owner':owner,'session':self.session})
    def checkpoint(self,job_id,token,payload):
        packet={'id':job_id,'token':token,'payload':payload}
        self.outbox.mkdir(parents=True,exist_ok=True)
        path=self.outbox/f'job-{job_id}-{self.session}.json'
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(packet,allow_nan=False),encoding='utf-8');temporary.replace(path)
        result=self.request('/checkpoint',packet)
        path.unlink()  # only this client's confirmed packet; failures leave evidence on disk
        return result
    def finish(self,job_id,token,report): return self.request('/finish',{'id':job_id,'token':token,'report':report})
    def restart_attempt(self,job_id,token,identity,code_revision=None): return self.request('/restart-attempt',{'id':job_id,'token':token,'identity':identity,'code_revision':code_revision})
    def fail(self,job_id,token,failure): return self.request('/fail',{'id':job_id,'token':token,'failure':str(failure)[:300]})
    def status(self): return self.request('/status')
    def pause(self,value): return self.request('/pause',{'paused':value})
    def export(self,job_id): return self.request('/export?job='+str(job_id))
