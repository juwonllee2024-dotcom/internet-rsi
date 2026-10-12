const el = (id) => document.getElementById(id);
const states = { queued: '다음 실험 대기', running: '실험 진행 중', done: '실험 완료', failed: '실험 중단', blocked: '장비 준비 대기' };
const number = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
let endpoint = '';
let refreshing = false;
let hasData = false;
let examples = [];

function decisionText(decision) {
  if (!decision) return '평가가 끝나면 채택 여부를 표시합니다.';
  const reason = decision.reason || '';
  if (reason.includes('individual task regression')) return '기존에 풀던 문제를 새 설정이 틀려 원래 설정을 유지했습니다.';
  if (reason.includes('candidate execution failure')) return '새 설정의 답변 중 오류가 있어 원래 설정을 유지했습니다.';
  if (reason.includes('no qualifying improvement')) return '점수나 답변 시간이 채택 기준만큼 좋아지지 않았습니다.';
  if (reason.includes('higher holdout success')) return '기존에 풀던 문제를 유지하면서 더 많은 문제를 통과했습니다.';
  if (reason.includes('lower median latency')) return '통과한 문제 수를 유지하면서 답변 시간이 줄었습니다.';
  if (reason.includes('invalid provenance') || reason.includes('invalid metrics')) return '측정 기록을 검증할 수 없어 원래 설정을 유지했습니다.';
  if (reason.includes('failed experiment')) return '실험 중 오류가 발생했습니다. 중단 기록을 보관했습니다.';
  if (reason.includes('incomplete') || reason.includes('mismatch')) return '평가 기록이 부족하거나 맞지 않아 채택하지 않았습니다.';
  return decision.accepted ? '평가 기준을 통과해 새 설정을 채택했습니다.' : '평가 기준을 통과하지 못해 원래 설정을 유지했습니다.';
}

async function api(path, body) {
  if (!endpoint) throw new Error('실험 서버 주소를 아직 불러오지 못했습니다.');
  const headers = {};
  if (body !== undefined) {
    const token = el('token').value.trim();
    if (!token) throw new Error('소유자 인증키를 입력해 주세요.');
    headers['Content-Type'] = 'application/json';
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${endpoint}${path}`, {
    method: body === undefined ? 'GET' : 'POST', headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) throw new Error('소유자 인증키 또는 접근 권한을 확인해 주세요.');
    if (response.status === 409) {
      const reason = await response.json().catch(() => ({}));
      if (reason.error === 'Study already active; deadline cannot be extended') throw new Error('이미 24시간 연구가 진행 중입니다. 현재 종료 시간은 유지됩니다.');
      if (reason.error === 'Resume experiments before starting a study') throw new Error('현재 일시 중지 상태입니다. 자동 실험 재개 후 연구를 시작해 주세요.');
      throw new Error('요청을 현재 작업 상태에 적용할 수 없습니다. 새로고침 후 확인해 주세요.');
    }
    throw new Error(`실험 서버가 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요. (오류 ${response.status})`);
  }
  return response.json();
}

function scoreText(job, variant) {
  const score = job.scores?.[variant];
  const progress = job.progress?.[variant] ?? 0;
  if (job.status !== 'done' && progress === 0) return '평가 전';
  if (Number.isFinite(score)) return `${score}/8 통과${progress > 0 && progress < 8 ? ' · 평가 중' : ''}`;
  return job.status === 'done' || job.status === 'failed' ? '기록 부족' : '평가 전';
}

function renderStatus(data) {
  const jobs = data.jobs || [];
  const active = jobs.find((job) => job.status === 'running') || jobs.find((job) => job.status === 'queued');
  el('version').textContent = `v${data.validated?.version ?? '확인 중'}`;
  const adopted = jobs.filter((job) => job.decision?.accepted).length;
  el('adoptions').textContent = `표시된 최근 기록에서 ${adopted}회 채택`;
  el('state').textContent = data.paused ? '일시 중지' : active ? (states[active.status] || '상태 확인 중') : '다음 기록 대기';
  el('progress').textContent = data.paused ? '소유자가 재개하면 예약 실행에서 실험을 이어갑니다.' : active ? `${active.id}번째 실험 · ${active.status === 'running' ? '결과를 저장하고 있습니다.' : 'GitHub 실행 차례를 기다립니다.'}` : '저장된 작업 상태를 확인했습니다.';
  if (data.study?.active) {
    el('budget-title').textContent = '24시간 한정 연구';
    el('budget').textContent = `${data.study.completed} / ${data.study.max_cycles}회 완료`;
    el('budget-help').textContent = `30분 간격 예약 · ${new Date(data.study.ends_at).toLocaleString('ko-KR')}까지 · 오늘 완료 한도 ${data.daily_cycle_limit}회`;
  } else {
    el('budget-title').textContent = '오늘 온라인 실험';
    el('budget').textContent = `${data.completed_today ?? 0} / ${data.daily_cycle_limit ?? 4}회 완료`;
    el('budget-help').textContent = `${data.study ? '24시간 연구 종료 · ' : ''}기본은 6시간 간격입니다. 하루 집계는 서버 날짜 기준입니다.`;
  }
  const rows = jobs.map((job) => {
    const row = document.createElement('tr');
    const progress = job.progress || {};
    for (const value of [
      `${job.id}번째`,
      `${states[job.status] || '상태 확인 중'} · 평가 기록 ${progress.baseline ?? 0}/8 + ${progress.candidate ?? 0}/8`,
      scoreText(job, 'baseline'), scoreText(job, 'candidate'),
    ]) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.append(cell);
    }
    const cell = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `pill${job.decision?.accepted ? ' adopted' : ''}`;
    badge.textContent = job.decision ? (job.decision.accepted ? '채택' : '미채택') : '결과 대기';
    const explanation = document.createElement('p');
    explanation.className = 'reason';
    explanation.textContent = decisionText(job.decision);
    cell.append(badge, explanation);
    row.append(cell);
    return row;
  });
  if (!rows.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = '아직 표시할 실험이 없습니다. 첫 실험이 실행되면 여기에 기록됩니다.';
    row.append(cell);
    rows.push(row);
  }
  el('jobs').replaceChildren(...rows);
  const blocked = (data.resource_jobs || []).some((job) => job.status === 'blocked');
  el('resources').textContent = blocked
    ? '현재 가벼운 추가 학습(LoRA)은 GPU 장비가 없어 대기 중입니다. 실행 중인 실험은 답변 방식과 설정을 비교하며, 모델 자체의 추가 학습 성공은 아직 확인되지 않았습니다.'
    : '실험에서 채택하는 것은 검증된 답변 방식과 설정입니다. 추가 학습 성공은 별도의 실행·검증 기록으로 확인해야 합니다.';
  hasData = true;
}

function errorText(error) {
  if (error.name === 'TimeoutError' || error.name === 'AbortError') return '서버 응답을 기다리는 시간이 길어졌습니다. 잠시 후 새로고침해 주세요.';
  if (error instanceof TypeError) return '실험 서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 새로고침해 주세요.';
  return error.message;
}

function showConnectionError(error) {
  el('message').textContent = `${errorText(error)}${hasData ? ' 아래에는 마지막으로 확인한 기록을 표시합니다.' : ''}`;
  if (hasData) return;
  el('version').textContent = '연결 대기';
  el('state').textContent = '연결 대기';
  el('budget').textContent = '연결 대기';
  el('progress').textContent = '서버 연결 후 실제 작업 상태를 표시합니다.';
  el('adoptions').textContent = '아직 최신 채택 기록을 확인하지 못했습니다.';
  el('jobs').textContent = '';
  const row = document.createElement('tr');
  const cell = document.createElement('td');
  cell.colSpan = 5;
  cell.textContent = '서버에 연결하면 최근 실험 결과를 표시합니다.';
  row.append(cell);
  el('jobs').append(row);
}

async function refresh() {
  if (refreshing || !endpoint) return;
  refreshing = true;
  el('refresh').disabled = true;
  try {
    renderStatus(await api('/status'));
    el('message').textContent = `실험 서버에 연결됨 · ${new Date().toLocaleTimeString('ko-KR')} 확인 · 1분마다 자동 갱신`;
  } catch (error) {
    showConnectionError(error);
  } finally {
    refreshing = false;
    el('refresh').disabled = false;
  }
}

function readableAnswer(sample) {
  const output = [...(sample.outputs || [])].reverse().find((item) => item.text?.trim());
  if (!output) return sample.truncated ? '답변을 끝내지 못했습니다. 출력 제한에 도달해 정답을 내놓지 못했습니다.' : '완성된 답변이 기록되지 않았습니다.';
  try {
    const parsed = JSON.parse(output.text);
    if (Object.hasOwn(parsed, 'answer')) return typeof parsed.answer === 'string' ? parsed.answer : JSON.stringify(parsed.answer);
  } catch { /* Show the original recorded text without executing it. */ }
  return output.text;
}

function renderExample() {
  const task = examples[Number(el('example-task').value)];
  if (!task) return;
  el('example-details').hidden = false;
  el('example-question').textContent = task.question_ko;
  el('example-correct').textContent = String(task.expected);
  el('example-original').textContent = `실제로 실행한 영문 문제: ${task.prompt}`;
  for (const side of ['baseline', 'candidate']) {
    const sample = task[side];
    el(`example-${side}`).textContent = readableAnswer(sample);
    el(`example-${side}-result`).textContent = `${sample.passed ? '통과' : sample.truncated ? '미통과 · 답변 미완성' : '미통과 · 오답'} · ${number.format(sample.latency_s)}초 · 출력 ${sample.eval_count}토큰`;
  }
  el('example-raw').textContent = JSON.stringify({
    '기존 설정의 실제 출력': task.baseline.outputs,
    '새 설정의 실제 출력': task.candidate.outputs,
  }, null, 2);
}

async function loadExamples() {
  try {
    const response = await fetch('./examples.json');
    if (!response.ok) throw new Error('기록 불러오기 실패');
    const data = await response.json();
    examples = data.tasks;
    el('example-task').replaceChildren(...examples.map((task, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = task.label_ko;
      return option;
    }));
    el('example-task').disabled = false;
    el('example-message').textContent = `${data.cycle}번째 실험의 보관 기록 · 토큰은 AI가 처리하는 글 조각의 수입니다.`;
    renderExample();
  } catch {
    el('example-message').textContent = '예시 기록을 불러오지 못했습니다. 새로고침하거나 원본 실험 기록을 확인해 주세요.';
  }
}

el('refresh').addEventListener('click', refresh);
el('example-task').addEventListener('change', renderExample);
for (const action of ['pause', 'resume']) {
  el(action).addEventListener('click', async () => {
    el('pause').disabled = el('resume').disabled = true;
    try {
      await api('/pause', { paused: action === 'pause' });
      el('control-message').textContent = action === 'pause'
        ? '새 실험을 일시 중지했습니다. 진행 중인 실험은 완료될 수 있습니다.'
        : '실험을 재개했습니다. 다음 예약 실행 또는 GitHub 수동 실행에서 이어갑니다.';
      await refresh();
    } catch (error) {
      el('control-message').textContent = errorText(error);
    } finally {
      el('pause').disabled = el('resume').disabled = false;
    }
  });
}
el('clear').addEventListener('click', () => {
  el('token').value = '';
  el('control-message').textContent = '이 화면에 입력한 인증키를 지웠습니다.';
});

for (const action of ['study-start', 'study-stop']) {
  el(action).addEventListener('click', async () => {
    el('study-start').disabled = el('study-stop').disabled = true;
    try {
      await api('/study', action === 'study-start' ? { hours: 24, max_cycles: 48 } : { action: 'stop' });
      el('control-message').textContent = action === 'study-start'
        ? '24시간 연구를 시작했습니다. 다음 예약부터 실험하며, 24시간 후 또는 최대 48회 완료 시 기본 예약으로 돌아갑니다.'
        : '24시간 연구를 종료했습니다. 기본 예약은 유지되며, 진행 중인 실험은 완료될 수 있습니다.';
      await refresh();
    } catch (error) {
      el('control-message').textContent = errorText(error);
    } finally {
      el('study-start').disabled = el('study-stop').disabled = false;
    }
  });
}

const exampleLoad = loadExamples();
try {
  const response = await fetch('./config.json');
  if (!response.ok) throw new Error('배포 설정을 불러오지 못했습니다. 페이지를 새로고침해 주세요.');
  const config = await response.json();
  const url = new URL(config.coordinator);
  if (url.protocol !== 'https:' || !url.hostname.endsWith('.workers.dev') || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('배포된 실험 서버 주소를 확인해야 합니다.');
  endpoint = url.origin;
  el('endpoint').value = endpoint;
  await refresh();
} catch (error) {
  showConnectionError(error);
}
await exampleLoad;
setInterval(refresh, 60000);
