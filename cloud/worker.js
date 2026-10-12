export const BASE_CONFIG = {model: 'qwen3.5:2b-q4_K_M', system_prompt: 'Follow instructions carefully. Use available tools when needed.',
  think: false, num_ctx: 2048, num_predict: 192, num_thread: 4, temperature: 0, seed: 0};
const TASKS = ['arithmetic', 'word-problem', 'instruction', 'code', 'plan', 'calculator', 'recall', 'agent'];
const CATEGORIES = {arithmetic:'reasoning','word-problem':'reasoning',instruction:'instruction',code:'coding',plan:'planning',calculator:'tool',recall:'memory',agent:'agent'};
const LEASE_MS = 1200000;
const STUDY_DAILY_LIMIT = 48;
const median = a => { const b = [...a].sort((x,y) => x-y); const m = Math.floor(b.length/2); return b.length%2 ? b[m] : (b[m-1]+b[m])/2; };

export function validateConfig(config) {
  if (!config || Object.keys(config).sort().join() !== Object.keys(BASE_CONFIG).sort().join()) throw Error('Invalid configuration fields');
  for (const key of ['model','num_ctx','num_predict','num_thread','temperature','seed']) {
    if (config[key] !== BASE_CONFIG[key]) throw Error('Model or resource bounds cannot change');
  }
  if (typeof config.think !== 'boolean' || typeof config.system_prompt !== 'string' || config.system_prompt.length < 5 || config.system_prompt.length > 1200) throw Error('Invalid prompt or thinking setting');
}

export function compare(baseline, candidate, expected = TASKS) {
  const reject = reason => ({accepted: false, kind: null, reason});
  if (!expected.length || baseline.length !== expected.length || candidate.length !== expected.length) return reject('incomplete paired evidence');
  for (const group of [baseline,candidate]) {
    if (new Set(group.map(x=>x.id)).size !== expected.length || group.some(x=>!expected.includes(x.id))) return reject('mismatched or duplicate tasks');
    if (group.some(x=>typeof x.passed !== 'boolean' || !Number.isFinite(x.latency_s) || x.latency_s <= 0 || !Number.isInteger(x.eval_count) || x.eval_count < 0)) return reject('invalid metrics');
  }
  const old = new Map(baseline.map(x=>[x.id,x]));
  if (candidate.some(x=>old.get(x.id).category !== x.category)) return reject('category mismatch');
  if (candidate.some(x=>old.get(x.id).passed && !x.passed)) return reject('individual task regression');
  if (candidate.some(x=>x.error)) return reject('candidate execution failure');
  const bscore = baseline.filter(x=>x.passed).length/baseline.length, cscore = candidate.filter(x=>x.passed).length/candidate.length;
  const bl = median(baseline.map(x=>x.latency_s)), cl = median(candidate.map(x=>x.latency_s));
  const metrics = {baseline_score:bscore,candidate_score:cscore,baseline_latency_s:bl,candidate_latency_s:cl};
  if (cscore > bscore && cl <= bl*1.5) return {accepted:true,kind:'system',reason:'higher holdout success; no task regression',...metrics};
  if (cscore === bscore && cscore > 0 && cl <= bl*0.9) return {accepted:true,kind:'execution',reason:'equal holdout success; lower median latency',...metrics};
  return {accepted:false,kind:null,reason:'no qualifying improvement',...metrics};
}

const response = (data,status=200) => Response.json(data,{status});
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);

export function studyStatus(study, now = Date.now()) {
  return study ? {...study,active:now >= study.started_at && now < study.ends_at && study.completed < study.max_cycles} : null;
}

export function validateEvidence(report) {
  if(same(report.baseline_config,report.candidate_config))return 'no controlled configuration change';
  const identity=report.identity || {};
  if(identity.model!==BASE_CONFIG.model || !/^[a-f0-9]{64}$/.test(identity.digest || ''))return 'invalid model identity';
  if(!/^[a-f0-9]{40}$/.test(report.code_revision || '') || !/^[a-f0-9]{64}$/.test(report.suite_hash || ''))return 'missing immutable code or suite identity';
  if(!['synthetic-v1','synthetic-v2'].includes(report.suite_version) || typeof report.hypothesis!=='string' || typeof report.proposal_metrics?.text!=='string')return 'missing hypothesis, suite version or generated proposal';
  if(report.suite_version==='synthetic-v2' && (!identity.hardware?.cpu || !/^[a-f0-9]{64}$/.test(identity.hardware?.host_hash || '') || !report.version_manifest))return 'missing hardware or component versions';
  if(report.suite_version==='synthetic-v2') {
    const manifest=report.version_manifest;
    if(manifest.model!==identity.digest || manifest.code!==report.code_revision)return 'component identity mismatch';
    if(['evaluation','tools','agents','memory','configuration'].some(k=>!/^[a-f0-9]{64}$/.test(manifest[k] || '')))return 'incomplete component manifest';
    if(['baseline','candidate'].some(k=>!/^[a-f0-9]{64}$/.test(manifest.prompts?.[k] || '')))return 'incomplete prompt manifest';
  }
  for(const variant of ['baseline','candidate']) {
    const samples=report.samples?.[variant] || {};
    if(Object.keys(samples).length!==TASKS.length)return 'incomplete sample set';
    for(const name of TASKS) {
      const sample=samples[name];
      if(!sample || sample.id!==name || sample.category!==CATEGORIES[name] || typeof sample.passed!=='boolean')return 'invalid task identity or category';
      if(!Array.isArray(sample.outputs))return 'missing inference evidence';
      if(sample.passed && (!sample.outputs.length || sample.eval_count<=0 || sample.error))return 'success without completed inference';
      if(sample.passed && sample.outputs.some(x=>x.truncated))return 'success from truncated inference';
      if(sample.outputs.some(x=>typeof x.text!=='string' || !Number.isInteger(x.eval_count)))return 'invalid inference output';
      if(sample.outputs.reduce((n,x)=>n+x.eval_count,0)!==sample.eval_count)return 'inconsistent token usage';
    }
  }
  return null;
}

// SQLite-backed Durable Object. Each transaction atomically persists progress and version changes.
export class Coordinator {
  constructor(state, env) { this.storage = state.storage; this.env = env; }
  async ensure(tx) {
    let meta = await tx.get('meta');
    if (!meta) meta = {validated:{version:1,config:BASE_CONFIG},paused:false,cycle:0,active:null,completed_day:'',completed_count:0,resource_jobs:[]};
    const active = meta.active ? await tx.get('job:'+meta.active) : null;
    if (!active || ['done','failed'].includes(active.status)) {
      meta.cycle++;
      const bytes = crypto.getRandomValues(new Uint8Array(6));
      const seed = bytes.reduce((n,x)=>n*256+x,0);
      const job = {id:meta.cycle,status:'queued',token:null,expires:0,payload:{baseline:meta.validated,seed,candidate:null,
        identity:null,samples:{baseline:{},candidate:{}},observations:meta.observations || {targets:['reasoning','coding','instruction','planning','tool','memory','agent']}}};
      meta.active = job.id;
      await tx.put('job:'+job.id,job);
    }
    await tx.put('meta',meta);
    return meta;
  }
  check(job, token) {
    if (!job || job.status !== 'running' || job.token !== token || job.expires <= Date.now()) throw Error('Stale or expired lease');
  }
  async recordCompletion(tx, meta, job) {
    const today=new Date().toISOString().slice(0,10);
    meta.completed_count=meta.completed_day===today ? meta.completed_count+1 : 1;
    meta.completed_day=today;
    if(job.study_id) {
      const study=meta.study?.id===job.study_id ? meta.study : await tx.get('study:'+job.study_id);
      if(study) { study.completed++; await tx.put('study:'+study.id,study); }
      job.report.research_study_id=job.study_id;
    }
  }
  async fetch(request) {
    const path = new URL(request.url).pathname;
    try {
      if (request.method === 'GET') {
        return await this.storage.transaction(async tx => {
          const meta = await this.ensure(tx);
          if (path === '/export') {
            const id = Number(new URL(request.url).searchParams.get('job'));
            const job = await tx.get('job:'+id);
            return response(job?.report || null);
          }
          const jobs=[];
          for (let id=meta.cycle;id>Math.max(0,meta.cycle-20);id--) {
            const job=await tx.get('job:'+id);
            if(job) jobs.push({id,status:job.status,expires:job.expires,study_id:job.study_id || null,decision:job.report?.decision || null,
              baseline_version:job.payload.baseline.version,completed_at:job.completed_at || null,
              scores:{baseline:Object.values(job.report?.samples?.baseline || {}).filter(x=>x.passed).length,candidate:Object.values(job.report?.samples?.candidate || {}).filter(x=>x.passed).length},
              progress:{baseline:Object.keys(job.report?.samples?.baseline || job.payload.samples.baseline).length,candidate:Object.keys(job.report?.samples?.candidate || job.payload.samples.candidate).length}});
          }
          const study=studyStatus(meta.study);
          return response({model:BASE_CONFIG.model,validated:meta.validated,paused:meta.paused,jobs,study,
            completed_today:meta.completed_day === new Date().toISOString().slice(0,10) ? meta.completed_count : 0,
            daily_cycle_limit:study?.active ? STUDY_DAILY_LIMIT : 4,resource_jobs:meta.resource_jobs,compute:'Bounded GitHub Actions CPU jobs and compatible local clients; no LLM inference in Worker.'});
        });
      }
      const raw = await request.text();
      if (new TextEncoder().encode(raw).byteLength > 110000) return response({error:'Checkpoint exceeds storage budget'},413);
      const data = raw ? JSON.parse(raw) : {};
      return await this.storage.transaction(async tx => {
        const meta = await this.ensure(tx);
        if (path === '/tick') return response({active:meta.active});
        if (path === '/pause') { meta.paused=Boolean(data.paused); await tx.put('meta',meta); return response({paused:meta.paused}); }
        if (path === '/study') {
          if(data.action==='stop' && Object.keys(data).length===1) {
            if(meta.study) { meta.study.ends_at=Date.now(); await tx.put('study:'+meta.study.id,meta.study); await tx.put('meta',meta); }
            return response(studyStatus(meta.study));
          }
          if(Object.keys(data).sort().join()!=='hours,max_cycles' || !Number.isInteger(data.hours) || data.hours<1 || data.hours>24
            || !Number.isInteger(data.max_cycles) || data.max_cycles<1 || data.max_cycles>48) throw Error('Study must be 1..24 hours and 1..48 cycles');
          if(meta.paused) throw Error('Resume experiments before starting a study');
          if(studyStatus(meta.study)?.active) throw Error('Study already active; deadline cannot be extended');
          const started_at=Date.now();
          meta.study={id:crypto.randomUUID(),started_at,ends_at:started_at+data.hours*3600000,max_cycles:data.max_cycles,started:0,completed:0,interval_minutes:30};
          await tx.put('study:'+meta.study.id,meta.study); await tx.put('meta',meta);
          return response(studyStatus(meta.study));
        }
        if (path === '/resource-job') {
          if (meta.resource_jobs.length >= 30) throw Error('Resource queue full');
          if (data.kind !== 'lora' || !/^[a-f0-9]{40}$/.test(data.model_revision || '') || !/^[a-f0-9]{64}$/.test(data.dataset_sha256 || '')) throw Error('Pinned model revision and dataset hash required');
          const job = {id:crypto.randomUUID(),kind:'lora',status:'blocked',base_model:'Qwen/Qwen3.5-2B',
            required:{cuda:true,min_vram_gb:8},model_revision:data.model_revision,dataset_sha256:data.dataset_sha256,
            reason:'Requires intentionally provisioned CUDA compute and separately evaluated adapter; no training performed'};
          meta.resource_jobs.push(job); await tx.put('meta',meta); return response(job);
        }
        const job = await tx.get('job:'+meta.active);
        if (path === '/claim') {
          const today=new Date().toISOString().slice(0,10);
          const study=studyStatus(meta.study);
          if(data.study_id!==undefined && (!study?.active || data.study_id!==study.id))return response(null);
          if (typeof data.owner !== 'string' || data.owner.length > 80 || data.owner.length < 1) throw Error('Invalid owner');
          if (!/^[a-f0-9]{32}$/.test(data.session || ''))throw Error('Distinct client session required');
          if (job.status === 'running' && job.expires > Date.now() && (job.owner !== data.owner || job.session !== data.session)) return response(null);
          const resume = job.status === 'running' && job.expires > Date.now() && job.owner === data.owner && job.session === data.session;
          const limit=study?.active ? STUDY_DAILY_LIMIT : 4;
          if(meta.paused || (!resume && meta.completed_day===today && meta.completed_count>=limit)) return response(null);
          if(study?.active && job.study_id!==study.id) {
            if(study.started>=study.max_cycles)return response(null);
            job.study_id=study.id; meta.study.started++;
            await tx.put('study:'+study.id,meta.study); await tx.put('meta',meta);
          }
          job.token = resume ? job.token : crypto.randomUUID(); job.owner=data.owner; job.session=data.session; job.status='running'; job.expires=Date.now()+LEASE_MS;
          await tx.put('job:'+job.id,job);
          return response({id:job.id,token:job.token,expires:job.expires/1000,payload:job.payload});
        }
        if (path === '/import-local') {
          if(meta.cycle !== 1 || job.status !== 'queued' || job.token) throw Error('Import only allowed before first Internet lease');
          const report=data.report;
          validateConfig(report.baseline_config); validateConfig(report.candidate_config);
          if(report.identity?.model !== BASE_CONFIG.model || !report.identity.digest || !Number.isSafeInteger(report.suite_seed)) throw Error('Invalid imported identity');
          if(Object.keys(report.samples?.baseline || {}).length !== 8 || Object.keys(report.samples?.candidate || {}).length !== 8) throw Error('Incomplete imported evidence');
          report.decision=compare(Object.values(report.samples.baseline),Object.values(report.samples.candidate));
          job.payload={baseline:{version:1,config:report.baseline_config},seed:report.suite_seed,candidate:{config:report.candidate_config,hypothesis:report.hypothesis},identity:report.identity,samples:report.samples};
          job.status='done'; job.report=report; job.completed_at=new Date().toISOString();
          if(report.decision.accepted) meta.validated={version:2,config:report.candidate_config,identity:report.identity,source_job:job.id};
          const failed={}; for(const s of Object.values(report.samples.baseline)) if(!s.passed) failed[s.category]=(failed[s.category] || 0)+1;
          meta.observations={failure_categories:failed,last_decision:report.decision.reason};
          await tx.put('job:'+job.id,job);await tx.put('meta',meta);await this.ensure(tx);
          return response({imported:job.id,decision:report.decision});
        }
        const requested = await tx.get('job:'+data.id);
        if (path === '/finish' && requested?.status === 'done' && requested.token === data.token) return response(requested.report.decision);
        this.check(requested,data.token);
        if (requested.id !== meta.active) throw Error('Job is not active');
        if(path === '/fail') {
          requested.status='failed';requested.completed_at=new Date().toISOString();
          requested.report={failure:String(data.failure).slice(0,300),samples:requested.payload.samples,
            decision:{accepted:false,kind:null,reason:'failed experiment: '+String(data.failure).slice(0,160)}};
          meta.observations={proposal_failure:String(data.failure).slice(0,160)};
          await this.recordCompletion(tx,meta,requested);
          await tx.put('job:'+requested.id,requested);await tx.put('meta',meta);await this.ensure(tx);return response(requested.report);
        }
        if(path === '/restart-attempt') {
          if(data.identity?.digest !== requested.payload.identity?.digest || data.identity?.model !== BASE_CONFIG.model) throw Error('Model digest cannot change during handoff');
          const attempts=requested.payload.attempts || [];
          // Each archived attempt uses its own durable key, preserving history beyond per-value limits.
          await tx.put('attempt:'+requested.id+':'+attempts.length,{identity:requested.payload.identity,samples:requested.payload.samples,code_revision:requested.payload.code_revision});
          requested.payload.attempts=[...attempts,{archive_key:'attempt:'+requested.id+':'+attempts.length,identity:requested.payload.identity,code_revision:requested.payload.code_revision}];
          requested.payload.identity=data.identity; requested.payload.samples={baseline:{},candidate:{}};
          for(const key of ['suite_version','suite_hash','version_manifest'])delete requested.payload[key];
          if(data.code_revision)requested.payload.code_revision=data.code_revision;
          requested.expires=Date.now()+LEASE_MS; await tx.put('job:'+requested.id,requested);return response(requested.payload);
        }
        if (path === '/checkpoint') {
          const payload=data.payload;
          if (!payload || payload.seed !== requested.payload.seed || !same(payload.baseline,requested.payload.baseline)) throw Error('Baseline or holdout cannot change');
          if (payload.identity?.model !== BASE_CONFIG.model || !/^[a-f0-9]{64}$/.test(payload.identity.digest || '')) throw Error('Selected model identity required');
          if(meta.validated.identity?.digest && payload.identity.digest!==meta.validated.identity.digest)throw Error('Validated model digest cannot change');
          if (requested.payload.identity && !same(payload.identity,requested.payload.identity)) throw Error('Runtime identity changed mid-cycle');
          if (payload.candidate) validateConfig(payload.candidate.config);
          if (requested.payload.candidate && !same(payload.candidate,requested.payload.candidate)) throw Error('Candidate changed mid-cycle');
          for(const key of ['code_revision','suite_version','suite_hash','version_manifest','proposal_metrics'])
            if(requested.payload[key]!==undefined && !same(payload[key],requested.payload[key]))throw Error('Saved provenance cannot change');
          for (const variant of ['baseline','candidate']) {
            const samples=payload.samples?.[variant];
            if (!samples || Object.keys(samples).some(k=>!TASKS.includes(k))) throw Error('Invalid sample set');
            for (const [id, prior] of Object.entries(requested.payload.samples[variant])) {
              if (!same(prior,samples[id])) throw Error('Completed evidence cannot change');
            }
          }
          requested.payload=payload; requested.expires=Date.now()+LEASE_MS; await tx.put('job:'+requested.id,requested);
          return response({saved:true});
        }
        if (path === '/finish') {
          const report=data.report, payload=requested.payload;
          if (!report || !payload.candidate || !same(report.samples,payload.samples) || !same(report.identity,payload.identity)
            || !same(report.baseline_config,payload.baseline.config) || !same(report.candidate_config,payload.candidate.config)
            || report.suite_seed !== payload.seed || typeof report.suite_hash !== 'string') throw Error('Report differs from saved evidence');
          if (Object.keys(report.samples.baseline).length !== 8 || Object.keys(report.samples.candidate).length !== 8) throw Error('Incomplete evidence');
          for(const key of ['code_revision','suite_version','suite_hash','version_manifest','proposal_metrics'])
            if(payload[key]!==undefined && !same(report[key],payload[key]))throw Error('Report provenance differs from checkpoint');
          if(payload.candidate.hypothesis!==undefined && report.hypothesis!==payload.candidate.hypothesis)throw Error('Hypothesis differs from checkpoint');
          const provenanceError=validateEvidence(report);
          const decision=provenanceError ? {accepted:false,kind:null,reason:'invalid provenance: '+provenanceError} : compare(Object.values(report.samples.baseline),Object.values(report.samples.candidate));
          report.decision=decision; requested.status='done'; requested.report=report; requested.completed_at=new Date().toISOString();
          if (decision.accepted) meta.validated={version:meta.validated.version+1,config:payload.candidate.config,identity:payload.identity,source_job:requested.id};
          else if(!provenanceError && !meta.validated.identity)meta.validated.identity=payload.identity;
          const failed={}; for(const sample of Object.values(report.samples.baseline)) if(!sample.passed) failed[sample.category]=(failed[sample.category] || 0)+1;
          meta.observations={failure_categories:failed,last_decision:decision.reason};
          requested.payload.samples={baseline:{},candidate:{}}; // one durable copy of full completed evidence
          await this.recordCompletion(tx,meta,requested);
          await tx.put('job:'+requested.id,requested); await tx.put('meta',meta); await this.ensure(tx);
          return response(decision);
        }
        return response({error:'Unknown operation'},404);
      });
    } catch (error) { return response({error:error.message},409); }
  }
}

function tokenEqual(a,b) { if(typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length || b.length < 24) return false; let diff=0; for(let i=0;i<a.length;i++) diff |= a.charCodeAt(i)^b.charCodeAt(i); return diff===0; }
export default {
  async fetch(request,env) {
    const url=new URL(request.url), origin=request.headers.get('Origin');
    const headers={'Access-Control-Allow-Origin':env.PUBLIC_ORIGIN,'Vary':'Origin','Access-Control-Allow-Methods':'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers':'Content-Type,Authorization','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
    if (origin && origin !== env.PUBLIC_ORIGIN) return response({error:'Origin not permitted'},403);
    if (request.method === 'OPTIONS') return new Response(null,{status:204,headers});
    if(url.pathname === '/health') return new Response(JSON.stringify({ok:true,model:BASE_CONFIG.model}),{headers:{...headers,'Content-Type':'application/json'}});
    const publicRead=request.method === 'GET' && url.pathname === '/status';
    if (!publicRead && !tokenEqual(request.headers.get('Authorization')?.replace(/^Bearer /,''),env.RSI_TOKEN)) return new Response(JSON.stringify({error:'Unauthorized'}),{status:401,headers});
    if (!['/status','/claim','/checkpoint','/finish','/pause','/study','/export','/resource-job','/tick','/import-local','/restart-attempt','/fail'].includes(url.pathname)) return new Response('Not found',{status:404,headers});
    const stub=env.COORDINATOR.get(env.COORDINATOR.idFromName('research'));
    const result=await stub.fetch(request);
    const outgoing=new Response(result.body,result); for(const [key,value] of Object.entries(headers)) outgoing.headers.set(key,value);
    return outgoing;
  },
  async scheduled(event,env,ctx) {
    const stub=env.COORDINATOR.get(env.COORDINATOR.idFromName('research'));
    ctx.waitUntil(stub.fetch('https://coordinator/tick',{method:'POST',body:'{}'}));
  }
};
