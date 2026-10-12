import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
let api;
try { api = await import('../cloud/worker.js'); } catch { api = null; }
const sample = (id, passed, latency_s = 2) => ({ id, category: 'reasoning', passed, latency_s, eval_count: 10, error: null });

test('coordinator recomputes promotion rather than trusts client claim', () => {
  assert.ok(api, 'cloud coordinator not implemented');
  assert.equal(api.compare([sample('a', true)], [sample('a', false)], ['a']).accepted, false);
  assert.equal(api.compare([sample('a', false)], [sample('a', true)], ['a']).accepted, true);
  assert.equal(api.compare([sample('a', true)], [], ['a']).accepted, false);
});

test('candidate cannot replace model or increase resource limits', () => {
  assert.ok(api, 'cloud coordinator not implemented');
  assert.throws(() => api.validateConfig({model: 'other'}));
  assert.throws(() => api.validateConfig({...api.BASE_CONFIG, num_thread: 128}));
  assert.throws(() => api.validateConfig({...api.BASE_CONFIG, think: 'true'}));
  assert.doesNotThrow(() => api.validateConfig(api.BASE_CONFIG));
});

test('promotion refuses incomplete, duplicate or nonfinite timing', () => {
  assert.ok(api, 'cloud coordinator not implemented');
  assert.equal(api.compare([sample('a', false)], [sample('a', true, NaN)], ['a']).accepted, false);
  assert.equal(api.compare([sample('a', false)], [sample('a', true), sample('a', true)], ['a']).accepted, false);
});

test('real durable coordinator enforces auth, exclusivity, checkpoints and completion', async () => {
  const token='infrastructure-test-token-123456789';
  const mf=new Miniflare(convertV4MiniflareOptions({name:'coordinator-test',modules:true,scriptPath:'cloud/worker.js',compatibilityDate:'2026-10-12',
    durableObjects:{COORDINATOR:{className:'Coordinator',useSQLite:true}},
    bindings:{RSI_TOKEN:token,PUBLIC_ORIGIN:'https://example.test'}}));
  try {
    const call=async(path,body,authorized=true)=>{
      const headers={'Content-Type':'application/json'};
      if(authorized)headers.Authorization='Bearer '+token;
      const result=await mf.dispatchFetch('https://test'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body)});
      return {status:result.status,data:await result.json()};
    };
    assert.equal((await call('/claim',{owner:'one'},false)).status,401);
    const first=(await call('/claim',{owner:'one'})).data;
    assert.equal((await call('/claim',{owner:'two'})).data,null);
    assert.equal((await call('/claim',{owner:'one'})).data.token,first.token);
    assert.equal((await call('/checkpoint',{id:first.id,token:'wrong',payload:first.payload})).status,409);
    first.payload.identity={model:api.BASE_CONFIG.model,digest:'fixture-only'};
    first.payload.candidate={hypothesis:'infrastructure test only',config:api.BASE_CONFIG};
    assert.equal((await call('/checkpoint',{id:first.id,token:first.token,payload:first.payload})).status,200);
    const resumed=(await call('/claim',{owner:'one'})).data;
    assert.equal(resumed.payload.candidate.hypothesis,'infrastructure test only');
    assert.equal((await call('/finish',{id:first.id,token:first.token,report:{decision:{accepted:true}}})).status,409);
    assert.equal((await call('/status')).data.validated.version,1);
    for(const id of ['arithmetic','word-problem','instruction','code','plan','calculator','recall','agent']) {
      first.payload.samples.baseline[id]=sample(id,true);
      first.payload.samples.candidate[id]=sample(id,false);
    }
    assert.equal((await call('/checkpoint',{id:first.id,token:first.token,payload:first.payload})).status,200);
    const report={samples:first.payload.samples,identity:first.payload.identity,baseline_config:api.BASE_CONFIG,
      candidate_config:api.BASE_CONFIG,suite_seed:first.payload.seed,suite_hash:'fixture-only',decision:{accepted:true}};
    const done=await call('/finish',{id:first.id,token:first.token,report});
    assert.equal(done.status,200); assert.equal(done.data.accepted,false);
    assert.deepEqual((await call('/finish',{id:first.id,token:first.token,report})).data,done.data);
    const status=(await call('/status')).data;
    assert.equal(status.validated.version,1);
    assert.equal(status.jobs[0].id,2); assert.equal(status.jobs[0].status,'queued');
    assert.equal(JSON.stringify(status).includes(first.token),false);
    await call('/pause',{paused:true}); assert.equal((await call('/claim',{owner:'three'})).data,null);
  } finally {await mf.dispose();}
});
