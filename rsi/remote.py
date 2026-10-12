"""Internet authority client; failed writes raise and preserve local evidence."""
import json
import time
import urllib.error
import urllib.request


class RemoteStore:
    def __init__(self, url, token):
        if not url.startswith('https://') and not url.startswith('http://127.0.0.1:'):
            raise ValueError('HTTPS coordinator required')
        if len(token) < 24:
            raise ValueError('Coordinator token missing or too short')
        self.url, self.token = url.rstrip('/'), token

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

    def claim(self,owner): return self.request('/claim',{'owner':owner})
    def checkpoint(self,job_id,token,payload): return self.request('/checkpoint',{'id':job_id,'token':token,'payload':payload})
    def finish(self,job_id,token,report): return self.request('/finish',{'id':job_id,'token':token,'report':report})
    def restart_attempt(self,job_id,token,identity): return self.request('/restart-attempt',{'id':job_id,'token':token,'identity':identity})
    def fail(self,job_id,token,failure): return self.request('/fail',{'id':job_id,'token':token,'failure':str(failure)[:300]})
    def status(self): return self.request('/status')
    def pause(self,value): return self.request('/pause',{'paused':value})
    def export(self,job_id): return self.request('/export?job='+str(job_id))
