import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
let api;
try { api = await import('../cloud/worker.js'); } catch { api = null; }
const sample = (id, passed, latency_s = 2) => ({ id, category: 'reasoning', passed, latency_s, eval_count: 10, error: null });

test('study ends at its deadline and cannot carry unused quota beyond 24 hours', () => {
  const study={started_at:0,ends_at:1000,started:1,completed:0,max_cycles:2};
  assert.equal(api.studyStatus(study,999).active,true);
  assert.equal(api.studyStatus(study,1000).active,false);
  assert.equal(api.studyStatus({...study,completed:2},500).active,false);
  assert.equal(api.studyStatus(null,500),null);
});

test('study-bound claim cannot start baseline work after stop or a different study', async () => {
  const token='infrastructure-test-token-123456789';
  const mf=new Miniflare(convertV4MiniflareOptions({name:'study-scope-test',modules:true,scriptPath:'cloud/worker.js',compatibilityDate:'2026-10-12',
    durableObjects:{COORDINATOR:{className:'Coordinator',useSQLite:true}},bindings:{RSI_TOKEN:token,PUBLIC_ORIGIN:'https://example.test'}}));
  try {
    const call=async(path,body)=>(await mf.dispatchFetch('https://test'+path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)})).json();
    const study=await call('/study',{hours:1,max_cycles:2});
    const claim={owner:'study-test',session:'a'.repeat(32),study_id:study.id};
    assert.equal(await call('/claim',{...claim,study_id:'00000000-0000-0000-0000-000000000000'}),null);
    await call('/study',{action:'stop'});
    assert.equal(await call('/claim',claim),null);
    const replacement=await call('/study',{hours:1,max_cycles:2});
    assert.equal(await call('/claim',claim),null);
    const current=await call('/claim',{...claim,study_id:replacement.id});
    assert.ok(current.id);
  } finally { await mf.dispose(); }
});

test('temporary study respects auth, fixed bounds, pause, unique reservations and failure accounting', async () => {
  const token='infrastructure-test-token-123456789';
  const mf=new Miniflare(convertV4MiniflareOptions({name:'study-test',modules:true,scriptPath:'cloud/worker.js',compatibilityDate:'2026-10-12',
    durableObjects:{COORDINATOR:{className:'Coordinator',useSQLite:true}},
    bindings:{RSI_TOKEN:token,PUBLIC_ORIGIN:'https://example.test'}}));
  try {
    const call=async(path,body,authorized=true)=>{
      const headers={'Content-Type':'application/json'};
      if(authorized)headers.Authorization='Bearer '+token;
      return mf.dispatchFetch('https://test'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body)});
    };
    assert.equal((await call('/study',{hours:24,max_cycles:2},false)).status,401);
    for(const body of [{hours:25,max_cycles:2},{hours:24,max_cycles:49},{hours:0,max_cycles:2},{hours:24,max_cycles:0},{hours:24,max_cycles:2,extra:true}])
      assert.equal((await call('/study',body)).status,409);
    await call('/pause',{paused:true});
    assert.equal((await call('/study',{hours:24,max_cycles:2})).status,409);
    await call('/pause',{paused:false});
    const initial=await (await call('/study',{hours:24,max_cycles:2})).json();
    assert.equal(initial.active,true);
    assert.equal(initial.ends_at-initial.started_at,86400000);
    assert.equal((await call('/study',{hours:24,max_cycles:2})).status,409);
    const claim=()=>call('/claim',{owner:'study-test',session:'a'.repeat(32)});
    for(let i=0;i<2;i++) {
      const job=await (await claim()).json();
      const resumed=await (await claim()).json();
      assert.equal(resumed.id,job.id);
      const running=await (await call('/status')).json();
      assert.equal(running.study.started,i+1);
      assert.equal((await call('/fail',{id:job.id,token:job.token,failure:'controlled temporary test'})).status,200);
      assert.equal((await call('/fail',{id:job.id,token:job.token,failure:'repeat'})).status,409);
    }
    const done=await (await call('/status')).json();
    assert.equal(done.study.completed,2);
    assert.equal(done.study.active,false);
    assert.equal(done.daily_cycle_limit,4);
    assert.equal((await call('/study',{action:'stop'})).status,200);
    const second=await (await call('/study',{hours:1,max_cycles:48})).json();
    assert.notEqual(second.id,initial.id);
    for(let i=2;i<48;i++) {
      const job=await (await claim()).json();
      assert.ok(job);
      await call('/fail',{id:job.id,token:job.token,failure:'controlled temporary test'});
    }
    assert.equal(await (await claim()).json(),null);
    await call('/study',{action:'stop'});
    assert.equal((await (await call('/status')).json()).study.active,false);
  } finally { await mf.dispose(); }
});

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
      if(path==='/claim' && !body.session)body={...body,session:'a'.repeat(32)};
      const headers={'Content-Type':'application/json'};
      if(authorized)headers.Authorization='Bearer '+token;
      const result=await mf.dispatchFetch('https://test'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body)});
      return {status:result.status,data:await result.json()};
    };
    assert.equal((await call('/claim',{owner:'one'},false)).status,401);
    const first=(await call('/claim',{owner:'one'})).data;
    assert.equal((await call('/claim',{owner:'one',session:'b'.repeat(32)})).data,null);
    assert.equal((await call('/claim',{owner:'two'})).data,null);
    assert.equal((await call('/claim',{owner:'one'})).data.token,first.token);
    assert.equal((await call('/checkpoint',{id:first.id,token:'wrong',payload:first.payload})).status,409);
    first.payload.identity={model:api.BASE_CONFIG.model,digest:'d'.repeat(64)};
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
      candidate_config:api.BASE_CONFIG,hypothesis:first.payload.candidate.hypothesis,suite_seed:first.payload.seed,suite_hash:'e'.repeat(64),code_revision:'f'.repeat(40),suite_version:'synthetic-v2',decision:{accepted:true}};
    const done=await call('/finish',{id:first.id,token:first.token,report});
    assert.equal(done.status,200); assert.equal(done.data.accepted,false);
    assert.deepEqual((await call('/finish',{id:first.id,token:first.token,report})).data,done.data);
    const status=(await call('/status')).data;
    assert.equal(status.validated.version,1);
    assert.equal(status.jobs[0].id,2); assert.equal(status.jobs[0].status,'queued');
    assert.equal(JSON.stringify(status).includes(first.token),false);
    await call('/pause',{paused:true}); assert.equal((await call('/claim',{owner:'three'})).data,null);
    await call('/pause',{paused:false});
    const next=(await call('/claim',{owner:'one'})).data;
    const changed={...api.BASE_CONFIG,system_prompt:'Use concise JSON answers and verify arithmetic.'};
    next.payload.identity={model:api.BASE_CONFIG.model,digest:'d'.repeat(64),hardware:{cpu:'infrastructure fixture',host_hash:'c'.repeat(64)}};
    next.payload.candidate={hypothesis:'Infrastructure fixture, not research evidence',config:changed};
    const categories={arithmetic:'reasoning','word-problem':'reasoning',instruction:'instruction',code:'coding',plan:'planning',calculator:'tool',recall:'memory',agent:'agent'};
    for(const [id,category] of Object.entries(categories))for(const [variant,passed] of [['baseline',false],['candidate',true]])
      next.payload.samples[variant][id]={...sample(id,passed),category,outputs:[{text:'{"answer":1}',eval_count:10}]};
    await call('/checkpoint',{id:next.id,token:next.token,payload:next.payload});
    const complete={samples:next.payload.samples,identity:next.payload.identity,baseline_config:api.BASE_CONFIG,candidate_config:changed,
      suite_seed:next.payload.seed,suite_hash:'e'.repeat(64),code_revision:'f'.repeat(40),suite_version:'synthetic-v2',
      hypothesis:next.payload.candidate.hypothesis,proposal_metrics:{text:'{"hypothesis":"infrastructure test"}'},
      version_manifest:{model:'d'.repeat(64),code:'f'.repeat(40),evaluation:'e'.repeat(64),tools:'e'.repeat(64),agents:'e'.repeat(64),memory:'e'.repeat(64),configuration:'e'.repeat(64),prompts:{baseline:'e'.repeat(64),candidate:'e'.repeat(64)}}};
    assert.notEqual(api.validateEvidence({...complete,version_manifest:{}}),null);
    Object.assign(next.payload,{code_revision:complete.code_revision,suite_version:complete.suite_version,suite_hash:complete.suite_hash,version_manifest:complete.version_manifest,proposal_metrics:complete.proposal_metrics});
    await call('/checkpoint',{id:next.id,token:next.token,payload:next.payload});
    assert.equal((await call('/finish',{id:next.id,token:next.token,report:{...complete,code_revision:'0'.repeat(40)}})).status,409);
    assert.equal(api.validateEvidence(complete),null);
    const promotion=await call('/finish',{id:next.id,token:next.token,report:complete});
    assert.equal(promotion.status,200);assert.equal(promotion.data.accepted,true);
    const promoted=(await call('/status')).data;
    assert.equal(promoted.validated.version,2);assert.equal(promoted.validated.config.system_prompt,changed.system_prompt);
    assert.equal(promoted.jobs.find(j=>j.id===next.id).progress.candidate,8);
    assert.equal(promoted.jobs[0].id,3);
  } finally {await mf.dispose();}
});

test('empty model identity and incomplete provenance cannot support promotion',()=>{
  assert.ok(api.validateEvidence,'evidence schema not implemented');
  const invalid={identity:{model:api.BASE_CONFIG.model,digest:''},suite_hash:'',samples:{baseline:{},candidate:{}}};
  assert.notEqual(api.validateEvidence(invalid),null);
});
