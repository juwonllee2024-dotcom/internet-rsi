"""Standalone SQLite authority. Cloud-connected clients use RemoteStore instead."""
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from .runtime import BASE_CONFIG
from .gate import compare
from .evaluation import make_suite


def initial_payload(version):
    return {'baseline': version, 'seed': secrets.randbits(48), 'candidate': None,
            'samples': {'baseline': {}, 'candidate': {}}, 'identity': None}


def validate_report(payload, report):
    expected = [x['id'] for x in make_suite(payload['seed'])]
    samples = report.get('samples', {})
    decision = compare(list(samples.get('baseline', {}).values()),
                       list(samples.get('candidate', {}).values()), expected)
    if report.get('decision', {}).get('accepted') and not decision['accepted']:
        raise ValueError('Promotion rejected: ' + decision['reason'])
    return decision


class Store:
    def __init__(self, path='.state/research.sqlite', clock=time.time, lease_seconds=600):
        self.path, self.clock, self.lease_seconds = str(path), clock, lease_seconds
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);'
                             'CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY,status TEXT,owner TEXT,token TEXT,expires REAL,payload TEXT,report TEXT);')
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('validated', json.dumps({'version': 1, 'config': BASE_CONFIG})))
            db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('paused', 'false'))
            self._ensure_next(db)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _meta(self, db, key):
        return json.loads(db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()[0])

    def _ensure_next(self, db):
        if not db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone():
            db.execute("INSERT INTO jobs(status,payload) VALUES ('queued',?)", (json.dumps(initial_payload(self._meta(db, 'validated'))),))

    def claim(self, owner):
        with self.transaction() as db:
            if self._meta(db, 'paused'):
                return None
            self._ensure_next(db)
            row = db.execute("SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY id LIMIT 1").fetchone()
            if row['status'] == 'running' and row['expires'] > self.clock() and row['owner'] != owner:
                return None
            token = row['token'] if row['owner'] == owner and (row['expires'] or 0) > self.clock() else secrets.token_hex(16)
            expires = self.clock() + self.lease_seconds
            db.execute("UPDATE jobs SET status='running',owner=?,token=?,expires=? WHERE id=?", (owner, token, expires, row['id']))
            return {'id': row['id'], 'token': token, 'expires': expires, 'payload': json.loads(row['payload'])}

    def _check(self, db, job_id, token):
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['token'] != token or row['expires'] <= self.clock() or row['status'] != 'running':
            raise ValueError('Stale or expired lease')
        return row

    def checkpoint(self, job_id, token, payload):
        with self.transaction() as db:
            self._check(db, job_id, token)
            db.execute('UPDATE jobs SET payload=?,expires=? WHERE id=?',
                       (json.dumps(payload, allow_nan=False), self.clock() + self.lease_seconds, job_id))

    def finish(self, job_id, token, report):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row and row['status'] == 'done' and row['token'] == token:
                return json.loads(row['report'])['decision']
            row = self._check(db, job_id, token)
            payload = json.loads(row['payload'])
            decision = validate_report(payload, report)
            report['decision'] = decision
            if decision['accepted']:
                candidate = report['candidate_config']
                if candidate != payload['candidate']['config']:
                    raise ValueError('Candidate differs from checkpoint')
                db.execute('UPDATE meta SET value=? WHERE key=?',
                           (json.dumps({'version': payload['baseline']['version'] + 1, 'config': candidate,
                                        'identity': report['identity'], 'source_job': job_id}), 'validated'))
            db.execute("UPDATE jobs SET status='done',report=? WHERE id=?", (json.dumps(report, allow_nan=False), job_id))
            self._ensure_next(db)
            return decision

    def pause(self, value):
        with self.transaction() as db:
            db.execute("UPDATE meta SET value=? WHERE key='paused'", (json.dumps(bool(value)),))

    def status(self):
        with self.transaction() as db:
            rows = db.execute('SELECT id,status,expires,report FROM jobs ORDER BY id DESC LIMIT 20').fetchall()
            return {'validated': self._meta(db, 'validated'), 'paused': self._meta(db, 'paused'),
                    'jobs': [{'id': r['id'], 'status': r['status'], 'expires': r['expires'],
                              'decision': json.loads(r['report'])['decision'] if r['report'] else None} for r in rows]}

    def export(self, job_id):
        with self.transaction() as db:
            row = db.execute('SELECT report FROM jobs WHERE id=?', (job_id,)).fetchone()
            return json.loads(row[0]) if row and row[0] else None
