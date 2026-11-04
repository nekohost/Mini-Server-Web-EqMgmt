"""[MINI-COMMENT: ASSISTANT.STORE]
[EN rev.5]
[Role] Persists owner-bound chats, step snapshots and reserved completion storage in the app-only queue.
[Dependencies] Private SQLite v3 additive migration and epoch-bound group leases; equipment transactions stay in Domain.
[Impact] Keeps existing data and unknown-request locks; accepted output is never evicted to admit new input.
"""
import base64
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import time
import uuid

from .policy import (AssistantError, ERROR_REASONS, MAX_CONTENT, MAX_PROPOSALS, MAX_REASONING,
                     MAX_RECEIPT, OUTPUT_RESERVATION, TERMINAL, canonical, digest, mac, opaque)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_meta(version INTEGER NOT NULL);
INSERT INTO ai_meta SELECT 2 WHERE NOT EXISTS(SELECT 1 FROM ai_meta);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,owner INTEGER NOT NULL,account_key TEXT NOT NULL,title TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS conversation_owner ON conversations(owner,updated);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,conversation TEXT NOT NULL REFERENCES conversations(id),job TEXT,role TEXT NOT NULL,content TEXT NOT NULL DEFAULT '',reasoning TEXT NOT NULL DEFAULT '',created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation,id);
CREATE INDEX IF NOT EXISTS message_job ON messages(job,role);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,conversation TEXT NOT NULL REFERENCES conversations(id),owner INTEGER NOT NULL,client_key TEXT NOT NULL,input_hash TEXT NOT NULL,binding TEXT NOT NULL,expires REAL NOT NULL,level TEXT NOT NULL,state TEXT NOT NULL,queue_order INTEGER NOT NULL,context TEXT NOT NULL DEFAULT '[]',steps INTEGER NOT NULL DEFAULT 0,lease_hash TEXT,worker TEXT,heartbeat REAL,cancel INTEGER NOT NULL DEFAULT 0,error TEXT,error_code TEXT,reserved_chars INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,updated REAL NOT NULL,UNIQUE(owner,client_key));
CREATE INDEX IF NOT EXISTS queue_order ON jobs(state,queue_order);
CREATE INDEX IF NOT EXISTS job_owner ON jobs(owner,created);
CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,job TEXT NOT NULL REFERENCES jobs(id),owner INTEGER NOT NULL,operation TEXT NOT NULL,payload TEXT NOT NULL,before_json TEXT NOT NULL,signature TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL DEFAULT 'pending',result TEXT,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS proposal_job ON proposals(job,owner);
CREATE TABLE IF NOT EXISTS revocations(binding TEXT PRIMARY KEY,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS message_steps(job TEXT NOT NULL REFERENCES jobs(id),step INTEGER NOT NULL,reasoning TEXT NOT NULL DEFAULT '',content TEXT NOT NULL DEFAULT '',PRIMARY KEY(job,step));
CREATE TABLE IF NOT EXISTS storage_accounts(owner INTEGER NOT NULL,account_key TEXT NOT NULL,used_chars INTEGER NOT NULL DEFAULT 0 CHECK(used_chars>=0),PRIMARY KEY(owner,account_key));
'''


class Store:
    """[Role] Owns short AI-only transactions. [Dependencies] SQLite/WAL. [Impact] Never spans inference."""
    def __init__(self, path, completion_reserve=32000000, epoch='initial-v3'):
        """[Role] Adds private v3 tables/columns while preserving all v1/v2 messages, jobs and unknown locks.
        [Dependencies] A protected local path and explicit bounded extension budget, not equipment.db.
        [Impact] Existing over-budget history remains readable; only new admissions can be refused.
        """
        if type(completion_reserve) is not int or not 0 <= completion_reserve <= 1024000000:
            raise ValueError('invalid assistant completion reserve')
        self.path = Path(path).absolute()
        if not isinstance(epoch,str) or not 8<=len(epoch)<=128:
            raise ValueError('invalid assistant database epoch')
        self.epoch=epoch
        self.history_limit, self.completion_reserve = 32000000, completion_reserve
        self.output_reservation = OUTPUT_RESERVATION
        self.turn_limit_minute, self.turn_limit_day = 10, 200
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError('assistant database must not be a symlink')
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_meta'").fetchone():
                prior=[r[0] for r in db.execute('SELECT version FROM ai_meta')]
                if prior==[3]:
                    required={'conversations':{'selection_id','next_level','selection_revision','account_key'},
                        'jobs':{'selection_id','route_snapshot','resource_group','purpose','probe_plan','handoff_chars'},
                        'ai_provider_models':{'profile_revision','verified_revision'},
                        'ai_resource_groups':{'last_owner'},'ai_provider_revisions':{'credential'},
                        'ai_task_drafts':{'revision','source_message'}}
                    for table,columns in required.items():
                        if not columns<={r[1] for r in db.execute('PRAGMA table_info('+table+')')}:
                            raise ValueError('incomplete assistant v3 schema')
                    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='one_group_request'").fetchone():
                        raise ValueError('incomplete assistant v3 slot index')
            db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA)
            versions = [r[0] for r in db.execute('SELECT version FROM ai_meta')]
            if versions not in ([1], [2], [3]):
                raise ValueError('unsupported assistant schema')
            if 'account_key' not in {r[1] for r in db.execute('PRAGMA table_info(conversations)')}:
                raise ValueError('incomplete assistant account identity schema')
            columns = {r[1] for r in db.execute('PRAGMA table_info(jobs)')}
            if 'error_code' not in columns:
                db.execute('ALTER TABLE jobs ADD COLUMN error_code TEXT')
            if 'reserved_chars' not in columns:
                db.execute('ALTER TABLE jobs ADD COLUMN reserved_chars INTEGER NOT NULL DEFAULT 0')
            if versions == [1]:
                # Preserve the surviving legacy snapshot; do not invent reasoning already lost by v1.
                db.execute("""INSERT OR IGNORE INTO message_steps(job,step,reasoning,content)
                    SELECT j.id,CASE WHEN j.state IN ('running','draining','recovery_required') THEN j.steps
                    ELSE MAX(j.steps-1,0) END,m.reasoning,m.content FROM jobs j JOIN messages m ON m.job=j.id
                    WHERE m.role='assistant'""")
                db.execute("""UPDATE jobs SET reserved_chars=? WHERE state NOT IN ('done','failed','cancelled')
                    OR EXISTS(SELECT 1 FROM proposals p WHERE p.job=jobs.id AND p.state='pending')""",
                    (self.output_reservation,))
            from .providers import migrate
            migrate(db)
            db.execute("""INSERT OR IGNORE INTO storage_accounts(owner,account_key,used_chars)
                SELECT c.owner,c.account_key,COALESCE(SUM(length(m.content)+length(m.reasoning)),0)
                +COALESCE((SELECT SUM(j.handoff_chars) FROM jobs j JOIN conversations hc ON hc.id=j.conversation WHERE hc.owner=c.owner AND hc.account_key=c.account_key),0)
                +COALESCE((SELECT SUM(length(d.data)) FROM ai_task_drafts d JOIN conversations dc ON dc.id=d.conversation WHERE dc.owner=c.owner AND dc.account_key=c.account_key),0)
                FROM conversations c LEFT JOIN messages m ON m.conversation=c.id GROUP BY c.owner,c.account_key""")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self, write=False):
        """[Role] Always closes one short transaction after commit or rollback.
        [Dependencies] Fixed local AI database and BEGIN IMMEDIATE for mutations.
        [Impact] Model/network waits never hold this writer.
        """
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def conversation(self, owner, cid, db, account_key):
        """[Role] Hides foreign conversation existence with both owner and account identity.
        [Dependencies] A freshly authenticated server actor and opaque conversation ID.
        [Impact] Pagination cannot expand access to another account.
        """
        row = db.execute('SELECT * FROM conversations WHERE id=? AND owner=? AND account_key=?',
                         (opaque(cid), owner, account_key)).fetchone()
        if row is None:
            raise AssistantError('대화를 찾을 수 없습니다.', 404)
        return dict(row)

    def conversations(self, owner, account_key, cursor=None):
        """[MINI-COMMENT: ASSISTANT.HISTORY.PAGE]
        [EN rev.1]
        [Role] Pages stable owner-local title ordering without making cursor contents an auth grant.
        [Dependencies] Explicit owner/account predicates on every page and bounded cursor decoding.
        [Impact] All 200 retained conversations remain reachable; concurrent promotions may repeat, never leak.
        """
        anchor = None
        if cursor:
            try:
                if not isinstance(cursor, str) or len(cursor) > 200:
                    raise ValueError()
                anchor = json.loads(base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True))
                if not isinstance(anchor, list) or len(anchor) != 2 or type(anchor[0]) not in (int, float) or not math.isfinite(anchor[0]) or not 0 < anchor[0] < 32503680000:
                    raise ValueError()
                opaque(anchor[1])
            except (ValueError, TypeError):
                raise AssistantError('대화 목록 위치를 확인해 주세요.') from None
        with self.db() as db:
            sql, args = 'SELECT id,title,updated FROM conversations WHERE owner=? AND account_key=?', [owner, account_key]
            if anchor:
                sql += ' AND (updated<? OR (updated=? AND id<?))'
                args += [anchor[0], anchor[0], anchor[1]]
            rows = [dict(r) for r in db.execute(sql + ' ORDER BY updated DESC,id DESC LIMIT 51', args)]
            page = rows[:50]
            next_cursor = base64.urlsafe_b64encode(canonical([page[-1]['updated'], page[-1]['id']]).encode()).decode().rstrip('=') if len(rows) > 50 else None
            return {'conversations': page, 'next_cursor': next_cursor}

    def create_conversation(self, owner, account_key):
        """[Role] Creates only a bounded owner-local conversation on user intent.
        [Dependencies] Private storage quota identity and the unchanged 200-conversation count.
        [Impact] Existing records are never deleted to admit a new title.
        """
        cid = uuid.uuid4().hex
        with self.db(True) as db:
            if db.execute('SELECT COUNT(*) FROM conversations WHERE owner=? AND account_key=?', (owner, account_key)).fetchone()[0] >= 200:
                raise AssistantError('대화 보관 한도에 도달했습니다. 관리자에게 문의해 주세요.', 429)
            now = time.time()
            db.execute('INSERT INTO conversations(id,owner,account_key,title,next_level,created,updated) VALUES(?,?,?,?,?,?,?)', (cid, owner, account_key, '새 대화', 'default', now, now))
            self._account(db, owner, account_key)
        return cid

    def _account(self, db, owner, account_key):
        """[MINI-COMMENT: ASSISTANT.STORAGE.BUDGET]
        [EN rev.1]
        [Role] Reads the logical message-character ledger; reservations budget already admitted completion.
        [Dependencies] The same AI writer transaction as every message mutation and terminal transition.
        [Impact] Base 32M plus extension is explicit; internal snapshots/log bytes are not counted as messages.
        """
        row = db.execute('SELECT used_chars FROM storage_accounts WHERE owner=? AND account_key=?', (owner, account_key)).fetchone()
        if row is None:
            used = db.execute("""SELECT COALESCE(SUM(length(m.content)+length(m.reasoning)),0) FROM messages m
                JOIN conversations c ON c.id=m.conversation WHERE c.owner=? AND c.account_key=?""", (owner, account_key)).fetchone()[0]
            used+=db.execute('SELECT COALESCE(SUM(j.handoff_chars),0) FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE c.owner=? AND c.account_key=?',(owner,account_key)).fetchone()[0]
            used+=db.execute('SELECT COALESCE(SUM(length(d.data)),0) FROM ai_task_drafts d JOIN conversations c ON c.id=d.conversation WHERE c.owner=? AND c.account_key=?',(owner,account_key)).fetchone()[0]
            db.execute('INSERT INTO storage_accounts VALUES(?,?,?)', (owner, account_key, used))
            return used
        return row[0]

    def storage_status(self, owner, account_key):
        """[Role] Returns human-display budget totals without re-scanning retained message text.
        [Dependencies] O(1) ledger and owner-local outstanding reservations.
        [Impact] Crossing the base triggers notice; new input needs space for its complete reserved output.
        """
        with self.db() as db:
            row = db.execute('SELECT used_chars FROM storage_accounts WHERE owner=? AND account_key=?', (owner, account_key)).fetchone()
            used = row[0] if row else 0
            reserved = db.execute("""SELECT COALESCE(SUM(j.reserved_chars),0) FROM jobs j JOIN conversations c ON c.id=j.conversation
                WHERE j.owner=? AND c.account_key=?""", (owner, account_key)).fetchone()[0]
            total = self.history_limit + self.completion_reserve
            return {'base_chars': self.history_limit, 'extension_chars': self.completion_reserve,
                    'total_chars': total, 'used_chars': used, 'reserved_chars': reserved,
                    'available_chars': max(0, total-used-reserved), 'above_base': used > self.history_limit}

    def _charge(self, db, job, delta):
        """[Role] Charges saved output against its pre-reserved budget atomically.
        [Dependencies] Bounded per-turn text/receipt limits and the current writer transaction.
        [Impact] Preserves results admitted under old budgets too; over-budget history blocks new admissions.
        """
        used = self._account(db, job['owner'], job['account_key'])
        reserved = db.execute('SELECT reserved_chars FROM jobs WHERE id=?', (job['id'],)).fetchone()[0]
        remaining = max(0, reserved-delta)
        # Valid production output fits the reservation; legacy/committed results are still kept if policy shrank.
        db.execute('UPDATE storage_accounts SET used_chars=? WHERE owner=? AND account_key=?',
                   (used+delta, job['owner'], job['account_key']))
        db.execute('UPDATE jobs SET reserved_chars=? WHERE id=?', (remaining, job['id']))

    def _message_text(self, db, job, reasoning, content):
        """[Role] Replaces one display snapshot and reconciles its ledger delta.
        [Dependencies] A verified step snapshot; same owner/job and bounded text.
        [Impact] Clearing provisional content refunds its reservation without deleting historical step data.
        """
        old = db.execute("SELECT length(reasoning)+length(content) FROM messages WHERE job=? AND role='assistant'", (job['id'],)).fetchone()
        self._charge(db, job, len(reasoning)+len(content)-old[0])
        db.execute("UPDATE messages SET reasoning=?,content=? WHERE job=? AND role='assistant'", (reasoning, content, job['id']))

    def record_result(self, db, job, record):
        """[Role] Saves one already committed business receipt once without discarding its evidence.
        [Dependencies] Equipment atomic receipt, AI transaction and the per-turn receipt reservation.
        [Impact] Duplicate confirms do not consume storage twice; actual results survive policy reductions.
        """
        if db.execute('SELECT 1 FROM messages WHERE conversation=? AND job IS NULL AND content=?', (job['conversation'], record)).fetchone():
            return
        self._charge(db, job, len(record))
        db.execute("INSERT INTO messages(conversation,role,content,created) VALUES(?,'assistant',?,?)", (job['conversation'], record, time.time()))

    def enqueue(self, owner, cid, content, level, client_key, binding, expires, account_key, route=None, purpose='chat', probe_plan=None):
        """[MINI-COMMENT: ASSISTANT.QUEUE.ACCEPT]
        [EN rev.3]
        [Role] Accepts input once only when the full bounded completion has reserved storage.
        [Dependencies] Current owner auth, idempotency, rate/admission limits and base plus extension budget.
        [Impact] Crossing the base does not discard generated results; insufficient remaining budget rejects new input.
        """
        with self.db(True) as db:
            conv=self.conversation(owner, cid, db, account_key)
            fingerprint = digest([cid, content, level, route['selection_id'], route['revision'], route.get('profile_revision'), purpose]) if route else digest([cid, content, level])
            old = db.execute('SELECT j.id,j.input_hash,c.account_key FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.owner=? AND j.client_key=?', (owner, client_key)).fetchone()
            if old:
                if old['account_key']!=account_key:
                    raise AssistantError('접수 키를 새로 만들어 다시 보내 주세요.',409)
                if old['input_hash'] != fingerprint:
                    raise AssistantError('같은 접수 키에 다른 내용이 전달되었습니다.', 409)
                return old['id']
            if route:
                model=db.execute('SELECT p.revision,p.enabled,p.retired,m.profile_revision,m.verified_revision,m.present,m.published FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider WHERE m.id=?',(route['selection_id'],)).fetchone()
                if not model or model['revision']!=route['revision'] or model['profile_revision']!=route.get('profile_revision') or not model['enabled'] or model['retired'] or not model['present'] or (purpose=='chat' and (not model['published'] or model['verified_revision']!=model['revision'])):
                    raise AssistantError('접수 중 모델 설정이 변경되었습니다. 모델을 다시 확인해 주세요.',409)
            now = time.time()
            minute, day = db.execute('SELECT SUM(created>=?),COUNT(*) FROM jobs WHERE owner=? AND created>=?',
                                     (now-60, owner, now-86400)).fetchone()
            if (minute or 0) >= self.turn_limit_minute or day >= self.turn_limit_day:
                raise AssistantError('요청 한도에 도달했습니다. 잠시 후 다시 이용해 주세요.', 429)
            self.expire(db)
            used = self._account(db, owner, account_key)
            reserved = db.execute("""SELECT COALESCE(SUM(j.reserved_chars),0) FROM jobs j JOIN conversations c ON c.id=j.conversation
                WHERE j.owner=? AND c.account_key=?""", (owner, account_key)).fetchone()[0]
            if used + reserved + len(content) + self.output_reservation > self.history_limit + self.completion_reserve:
                raise AssistantError('보관 예산에서 답변을 끝까지 저장할 공간을 확보하지 못했습니다. 기존 기록은 보존됩니다. 관리자에게 추가 예산을 문의해 주세요.', 429)
            if shutil.disk_usage(self.path.parent).free < 128*1024*1024:
                raise AssistantError('대화 저장 공간이 부족합니다. 기존 기록은 보존됩니다. 관리자에게 문의해 주세요.', 507)
            if db.execute("SELECT COUNT(*) FROM jobs WHERE state NOT IN ('done','failed','cancelled')").fetchone()[0] >= 20:
                raise AssistantError('요청이 많습니다. 잠시 후 다시 보내 주세요.', 429)
            if db.execute("SELECT COUNT(*) FROM jobs WHERE owner=? AND state NOT IN ('done','failed','cancelled')", (owner,)).fetchone()[0] >= 2:
                raise AssistantError('진행 중인 요청을 먼저 확인해 주세요.', 429)
            if db.execute("SELECT 1 FROM jobs WHERE conversation=? AND state IN ('queued','running','draining','recovery_required')", (cid,)).fetchone():
                raise AssistantError('이 대화의 이전 응답을 기다려 주세요.', 409)
            jid = uuid.uuid4().hex
            order = db.execute('SELECT COALESCE(MAX(queue_order),0)+1 FROM jobs').fetchone()[0]
            history = [dict(r) for r in db.execute("""SELECT role,content FROM messages WHERE conversation=? AND content<>''
                AND (job IS NULL OR job IN (SELECT id FROM jobs WHERE state IN ('done','waiting_confirmation')))
                ORDER BY id DESC LIMIT 12""", (cid,))][::-1][-8:]
            history.append({'role': 'user', 'content': content})
            db.execute("""INSERT INTO jobs(id,conversation,owner,client_key,input_hash,binding,expires,level,state,queue_order,
                context,reserved_chars,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (jid, cid, owner, client_key, fingerprint, binding, expires, level, 'queued', order,
                 canonical(history), self.output_reservation, now, now))
            db.execute('INSERT INTO messages(conversation,job,role,content,created) VALUES(?,?,?,?,?)', (cid, jid, 'user', content, now))
            db.execute('INSERT INTO messages(conversation,job,role,created) VALUES(?,?,?,?)', (cid, jid, 'assistant', now))
            if route:
                db.execute('UPDATE jobs SET selection_id=?,route_snapshot=?,resource_group=?,purpose=?,probe_plan=? WHERE id=?',
                    (route['selection_id'], canonical(route), route['resource_group'], purpose, canonical(probe_plan or []), jid))
                if purpose=='chat' and conv['selection_id']==route['selection_id']:
                    db.execute('UPDATE conversations SET next_level=? WHERE id=?',(level,cid))
                elif purpose=='chat' and conv['selection_id'] is None:
                    db.execute('UPDATE conversations SET selection_id=?,next_level=?,selection_revision=selection_revision+1 WHERE id=?',(route['selection_id'],level,cid))
                    db.execute('INSERT INTO ai_selection_events(conversation,selection,level,revision,created) VALUES(?,?,?,?,?)',(cid,route['selection_id'],level,conv['selection_revision']+1,now))
            else:
                from .providers import LEGACY_GROUP
                db.execute('UPDATE jobs SET resource_group=? WHERE id=?', (LEGACY_GROUP, jid))
            db.execute('UPDATE storage_accounts SET used_chars=used_chars+? WHERE owner=? AND account_key=?', (len(content), owner, account_key))
            db.execute("UPDATE conversations SET updated=?,title=CASE WHEN title='새 대화' THEN ? ELSE title END WHERE id=?", (now, content[:50], cid))
            return jid

    def expire(self, db):
        """[Role] Expires closed waits and releases unused completion reservations.
        [Dependencies] The current AI writer and preserved terminal/pending state.
        [Impact] Unknown active requests retain their lock and reservation; no records are deleted.
        """
        now = time.time()
        db.execute("UPDATE proposals SET state='expired' WHERE state='pending' AND expires<?", (now,))
        db.execute("UPDATE jobs SET state='done' WHERE state='waiting_confirmation' AND NOT EXISTS(SELECT 1 FROM proposals p WHERE p.job=jobs.id AND p.state='pending')")
        db.execute("UPDATE jobs SET state='cancelled',error=?,error_code='AUTH_EXPIRED' WHERE state='queued' AND expires<?", (ERROR_REASONS['AUTH_EXPIRED'], now))
        db.execute("""UPDATE jobs SET reserved_chars=0 WHERE state IN ('done','failed','cancelled')
            AND NOT EXISTS(SELECT 1 FROM proposals p WHERE p.job=jobs.id AND p.state='pending')""")

    def job(self, jid, db, owner=None, account_key=None):
        """[Role] Reads one job under owner auth or a separately verified worker lease.
        [Dependencies] Explicit account filters for all browser callers.
        [Impact] Internal lease validation never authorizes a browser confirmation.
        """
        sql, args = 'SELECT j.*,c.account_key FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.id=?', [opaque(jid)]
        if owner is not None:
            sql += ' AND j.owner=?'
            args.append(owner)
        if account_key is not None:
            sql += ' AND c.account_key=?'
            args.append(account_key)
        row = db.execute(sql, args).fetchone()
        if row is None:
            raise AssistantError('요청을 찾을 수 없습니다.', 404)
        return dict(row)

    def snapshot(self, owner, cid, account_key, before=None):
        """[Role] Pages owner-local messages without cutting off older retained history.
        [Dependencies] A positive before cursor, latest 60 messages and only their jobs/cards plus live work.
        [Impact] Pagination never exposes bindings, leases, raw context or another account.
        """
        if before is not None and (type(before) is not int or not 1 <= before <= 2**63-1):
            raise AssistantError('이전 대화 내용의 위치를 확인해 주세요.')
        with self.db(True) as db:
            conv = self.conversation(owner, cid, db, account_key)
            self.expire(db)
            sql, args = 'SELECT id,job,role,content,reasoning FROM messages WHERE conversation=?', [cid]
            if before is not None:
                sql += ' AND id<?'
                args.append(before)
            rows = [dict(r) for r in db.execute(sql+' ORDER BY id DESC LIMIT 61', args)]
            messages = rows[:60][::-1]
            visible = {m['job'] for m in messages if m['job']}
            live = [r[0] for r in db.execute("SELECT id FROM jobs WHERE conversation=? AND state NOT IN ('done','failed','cancelled')", (cid,))]
            ids = sorted(visible | set(live))
            jobs, cards = [], []
            if ids:
                placeholders = ','.join('?' for _ in ids)
                for row in db.execute('SELECT id,state,level,error,error_code,queue_order,created,steps,route_snapshot FROM jobs WHERE owner=? AND conversation=? AND id IN ('+placeholders+') ORDER BY created DESC', [owner, cid, *ids]):
                    item = dict(row)
                    from .providers import public_source
                    item['source']=public_source(item.pop('route_snapshot'))
                    group=db.execute('SELECT resource_group FROM jobs WHERE id=?',(row['id'],)).fetchone()[0]
                    item['position'] = db.execute("SELECT COUNT(*)+1 FROM jobs WHERE state='queued' AND resource_group=? AND queue_order<?", (group,row['queue_order'])).fetchone()[0] if row['state'] == 'queued' else None
                    item['answer_started'] = bool(db.execute("SELECT 1 FROM message_steps WHERE job=? AND content<>'' LIMIT 1", (row['id'],)).fetchone())
                    jobs.append(item)
                cards = [dict(r) for r in db.execute('SELECT id,job,operation,payload,before_json,expires,state,result FROM proposals WHERE owner=? AND job IN ('+placeholders+') ORDER BY created', [owner, *ids])]
            return {'conversation': {k: conv[k] for k in ('id','title','created','updated','selection_id','next_level','selection_revision')}, 'messages': messages,
                    'jobs': jobs, 'proposals': cards, 'next_before': messages[0]['id'] if len(rows) > 60 else None}

    def claim(self, worker):
        """[MINI-COMMENT: ASSISTANT.QUEUE.CLAIM]
        [EN rev.3]
        [Role] Claims one app request and initializes its isolated stream step atomically.
        [Dependencies] Partial unique index, fresh actor checks by HTTP and retained completion reservation.
        [Impact] Prior reasoning stays intact; a stale/unknown request is never stolen or reissued.
        """
        with self.db(True) as db:
            self.expire(db)
            row = db.execute("""SELECT j.*,c.account_key FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.state='queued'
                AND NOT EXISTS(SELECT 1 FROM jobs active WHERE active.resource_group=j.resource_group AND active.state IN ('running','draining','recovery_required'))
                ORDER BY j.queue_order LIMIT 1""").fetchone()
            if row is None:
                return None
            # At most one already queued turn from the last owner may defer another owner's group turn.
            last=db.execute('SELECT last_owner FROM ai_resource_groups WHERE id=?',(row['resource_group'],)).fetchone()
            if last and last[0]==row['owner']:
                fair=db.execute("SELECT j.*,c.account_key FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.state='queued' AND j.resource_group=? AND j.owner<>? ORDER BY j.queue_order LIMIT 1",(row['resource_group'],row['owner'])).fetchone()
                if fair:
                    row=fair
            token = secrets.token_hex(32)
            db.execute("UPDATE jobs SET state='running',worker=?,lease_hash=?,heartbeat=?,updated=? WHERE id=?", (worker, digest([self.epoch,token]), time.time(), time.time(), row['id']))
            db.execute('UPDATE ai_resource_groups SET last_owner=? WHERE id=?',(row['owner'],row['resource_group']))
            db.execute('INSERT OR IGNORE INTO message_steps(job,step) VALUES(?,?)', (row['id'], row['steps']))
            job = {**dict(row), 'state': 'running', 'lease': token}
            reasoning = db.execute("SELECT reasoning FROM messages WHERE job=? AND role='assistant'", (row['id'],)).fetchone()[0]
            self._message_text(db, job, reasoning, '')
            return job

    def lease(self, db, jid, token):
        """[Role] Verifies the current worker step lease before any stream or final update.
        [Dependencies] A private worker boundary, active state and constant-time hash comparison.
        [Impact] Late reports cannot alter a newer step or bypass owner confirmation.
        """
        row = self.job(jid, db)
        if row['state'] not in ('running','draining') or not isinstance(token, str) or not secrets.compare_digest(row['lease_hash'] or '', digest([self.epoch,token])):
            raise AssistantError('이 작업의 처리 권한이 만료되었습니다.', 409)
        return row

    def _step_snapshot(self, db, job, reasoning, content):
        """[MINI-COMMENT: ASSISTANT.STREAM.SNAPSHOT]
        [EN rev.1]
        [Role] Stores one step and composes append-only reasoning across all model steps.
        [Dependencies] Exact offsets/snapshot prefixes, per-turn display bounds and reserved ledger updates.
        [Impact] Completion cannot overwrite earlier reasoning or silently move an observed reasoning cursor backwards.
        """
        previous = db.execute('SELECT reasoning,content FROM message_steps WHERE job=? AND step=?', (job['id'], job['steps'])).fetchone()
        if previous is None:
            raise AssistantError('응답 단계 정보를 확인하지 못했습니다.', 409)
        if not reasoning.startswith(previous['reasoning']) or not content.startswith(previous['content']):
            raise AssistantError('이미 받은 응답과 완료 내용이 일치하지 않습니다.', 409)
        old_parts = [r[0] for r in db.execute('SELECT reasoning FROM message_steps WHERE job=? AND step<? ORDER BY step', (job['id'], job['steps']))]
        combined = '\n\n'.join(part for part in [*old_parts, reasoning] if part)
        if len(combined) > MAX_REASONING or len(content) > MAX_CONTENT:
            raise AssistantError('응답 표시 한도에 도달하여 작업을 중단했습니다. 이미 받은 내용은 보관됩니다.', 413)
        db.execute('UPDATE message_steps SET reasoning=?,content=? WHERE job=? AND step=?', (reasoning, content, job['id'], job['steps']))
        self._message_text(db, job, combined, content)
        db.execute('UPDATE jobs SET heartbeat=?,updated=? WHERE id=?', (time.time(), time.time(), job['id']))

    def append(self, jid, token, reasoning='', content='', reasoning_offset=None, content_offset=None):
        """[Role] Appends one offset-identified delta, acknowledging exact retry duplicates without appending twice.
        [Dependencies] Current lease/step and a short AI writer; legacy callers without offsets append once.
        [Impact] Lost HTTP acknowledgements do not duplicate reasoning or consume its completion budget twice.
        """
        with self.db(True) as db:
            job = self.lease(db, jid, token)
            previous = db.execute('SELECT reasoning,content FROM message_steps WHERE job=? AND step=?', (jid, job['steps'])).fetchone()
            values = []
            for field, delta, offset in (('reasoning', reasoning, reasoning_offset), ('content', content, content_offset)):
                current = previous[field]
                offset = len(current) if offset is None else offset
                if type(offset) is not int or not 0 <= offset <= len(current):
                    raise AssistantError('응답 조각의 순서가 올바르지 않습니다.', 409)
                if offset == len(current):
                    values.append(current+delta)
                elif current[offset:offset+len(delta)] == delta:
                    values.append(current)
                else:
                    raise AssistantError('중복 응답 조각의 내용이 일치하지 않습니다.', 409)
            self._step_snapshot(db, job, *values)
            return bool(job['cancel'])

    def reconcile(self, jid, token, reasoning=None, content=None):
        """[Role] Reconciles the final complete current-step text against already accepted event prefixes.
        [Dependencies] The full worker snapshot and the same lease; no equipment operation is performed.
        [Impact] Missing final display chunks are recovered while prior-step reasoning is retained.
        """
        with self.db(True) as db:
            job = self.lease(db, jid, token)
            old = db.execute('SELECT reasoning,content FROM message_steps WHERE job=? AND step=?', (jid, job['steps'])).fetchone()
            self._step_snapshot(db, job, old['reasoning'] if reasoning is None else reasoning, old['content'] if content is None else content)

    def cancel(self, owner, jid, account_key=None, error=None, error_code=None):
        """[Role] Stops further own work and cancels pending proposals without controlling shared inference.
        [Dependencies] Current owner/account or trusted internal job validation.
        [Impact] An active request drains; committed results remain untouched.
        """
        with self.db(True) as db:
            row = self.job(jid, db, owner, account_key)
            if row['state'] in TERMINAL:
                return row['state']
            state = 'draining' if row['state'] in ('running','draining') else row['state'] if row['state'] == 'recovery_required' else 'cancelled'
            db.execute('UPDATE jobs SET state=?,cancel=1,error=COALESCE(error,?),error_code=COALESCE(error_code,?),updated=? WHERE id=?',
                       (state, error, error_code, time.time(), jid))
            db.execute("UPDATE proposals SET state='cancelled' WHERE job=? AND state='pending'", (jid,))
            self.expire(db)
            return state

    def proposal(self, job, operation, payload, before, secret, supersedes=None):
        """[Role] Freezes validated write intent; only the real owner's confirmation can mutate equipment.
        [Dependencies] A live running job, deterministic per-step ID and current expiry.
        [Impact] Tool retries reuse one card and cannot exceed the per-turn proposal/receipt reservation.
        """
        pid, expires = digest([job['id'], job['steps'], operation, payload])[:32], min(job['expires'], time.time()+900)
        signature = mac(secret, pid, job['id'], job['owner'], job['binding'], operation, payload, before, expires)
        with self.db(True) as db:
            current = self.job(job['id'], db)
            if current['cancel'] or current['state'] != 'running':
                raise AssistantError('작업이 취소되었습니다.', 409)
            if db.execute('SELECT 1 FROM proposals WHERE id=?', (pid,)).fetchone():
                return {'proposal_id': pid, 'operation': operation, 'status': 'WAITING_CONFIRMATION', 'message': '기존 확인 카드를 확인해 주세요.'}
            if db.execute('SELECT COUNT(*) FROM proposals WHERE job=?', (job['id'],)).fetchone()[0] >= MAX_PROPOSALS:
                raise AssistantError('한 요청의 확인 항목이 너무 많습니다.', 429)
            if supersedes:
                old=db.execute('SELECT p.* FROM proposals p JOIN jobs j ON j.id=p.job WHERE p.id=? AND p.owner=? AND j.conversation=?',(opaque(supersedes),job['owner'],job['conversation'])).fetchone()
                if not old or old['operation']!=operation or old['state']!='pending':
                    raise AssistantError('대체할 미확정 확인 카드가 없거나 이미 처리되었습니다.',409)
                db.execute("UPDATE proposals SET state='superseded' WHERE id=?",(supersedes,))
            db.execute('INSERT INTO proposals(id,job,owner,operation,payload,before_json,signature,expires,created) VALUES(?,?,?,?,?,?,?,?,?)',
                       (pid, job['id'], job['owner'], operation, canonical(payload), canonical(before), signature, expires, time.time()))
        return {'proposal_id': pid, 'operation': operation, 'status': 'WAITING_CONFIRMATION', 'message': '아직 적용되지 않았습니다. 화면에서 내용을 확인한 뒤 실행해 주세요.'}

    def finish(self, jid, token, state, error=None, context=None, error_code=None):
        """[MINI-COMMENT: ASSISTANT.QUEUE.FINISH]
        [EN rev.1]
        [Role] Finalizes outcomes while limiting ordinary tasks to six steps and fixed capability plans to eight.
        [Dependencies] Current lease, authoritative response outcome and pending confirmations.
        [Impact] Failed model responses cannot leave the app queue running or leave executable pending proposals.
        """
        with self.db(True) as db:
            row = self.lease(db, jid, token)
            if row['cancel'] and state != 'recovery_required':
                error_code = row['error_code'] or error_code or 'USER_CANCELLED'
                error = row['error'] or error
                state = 'cancelled' if error_code in ('USER_CANCELLED','AUTH_EXPIRED') else 'failed'
            last_step = min(8, max(1, len(json.loads(row['probe_plan'])))) - 1 if row['purpose'] == 'probe' else 5
            if state == 'queued' and row['steps'] >= last_step:
                state, error_code = 'failed', 'STEP_LIMIT'
            if state in ('failed','cancelled','recovery_required'):
                error = error or ERROR_REASONS.get(error_code or 'PROCESSING_FAILED')
                error_code = error_code or ('STREAM_INCOMPLETE' if state == 'recovery_required' else 'PROCESSING_FAILED')
                db.execute("UPDATE proposals SET state='cancelled' WHERE job=? AND state='pending'", (jid,))
            if state == 'done' and db.execute("SELECT 1 FROM proposals WHERE job=? AND state='pending'", (jid,)).fetchone():
                state = 'waiting_confirmation'
            order = db.execute('SELECT COALESCE(MAX(queue_order),0)+1 FROM jobs').fetchone()[0]
            db.execute('UPDATE jobs SET state=?,error=COALESCE(error,?),error_code=COALESCE(error_code,?),context=?,steps=steps+1,queue_order=?,updated=? WHERE id=?',
                       (state, error, error_code, canonical(context) if context is not None else row['context'], order, time.time(), jid))
            self.expire(db)
            return state

    def revoked(self, binding):
        """[Role] Tests explicit logout revocation in addition to current DB token checks.
        [Dependencies] A server-derived HMAC binding, never a browser-provided owner.
        [Impact] An old signed cookie cannot reopen delegated work after logout.
        """
        with self.db() as db:
            return db.execute('SELECT 1 FROM revocations WHERE binding=?', (binding,)).fetchone() is not None

    def revoke(self, binding):
        """[Role] Revokes only one login's jobs/cards and frees completed reservations.
        [Dependencies] The existing logout hook and current AI transaction.
        [Impact] Active inference drains; unknown requests are not reissued and no audit/history is removed.
        """
        with self.db(True) as db:
            db.execute('INSERT OR IGNORE INTO revocations VALUES(?,?)', (binding, time.time()))
            db.execute("""UPDATE jobs SET cancel=1,state=CASE WHEN state IN ('running','draining') THEN 'draining'
                WHEN state='recovery_required' THEN state ELSE 'cancelled' END,error=COALESCE(error,?),error_code=COALESCE(error_code,'AUTH_EXPIRED')
                WHERE binding=? AND state NOT IN ('done','failed','cancelled')""", (ERROR_REASONS['AUTH_EXPIRED'], binding))
            db.execute("UPDATE proposals SET state='cancelled' WHERE state='pending' AND job IN (SELECT id FROM jobs WHERE binding=?)", (binding,))
            self.expire(db)

    def select_model(self, owner, cid, account_key, mid, level, revision):
        """[MINI-COMMENT: ASSISTANT.SELECTION]
        [EN rev.1]
        [Role] Saves the next-turn selection under an owner-bound optimistic revision.
        [Dependencies] HTTP-verified model/profile and the same AI writer as the selection event.
        [Impact] Queued/running jobs and existing proposal signatures are never changed.
        """
        with self.db(True) as db:
            conv = self.conversation(owner, cid, db, account_key)
            if type(revision) is not int or revision != conv['selection_revision']:
                raise AssistantError('다른 탭에서 모델 선택을 바꿨습니다. 대화를 다시 열어 주세요.', 409)
            db.execute('UPDATE conversations SET selection_id=?,next_level=?,selection_revision=selection_revision+1 WHERE id=?', (mid, level, cid))
            # Bounded per-conversation selection audit; access log retains the mutation request too.
            if db.execute('SELECT COUNT(*) FROM ai_selection_events WHERE conversation=?', (cid,)).fetchone()[0] >= 1000:
                raise AssistantError('대화의 모델 변경 이력 한도입니다. 새 대화를 사용해 주세요.', 429)
            db.execute('INSERT INTO ai_selection_events(conversation,selection,level,revision,created) VALUES(?,?,?,?,?)', (cid, mid, level, revision+1, time.time()))
            return revision+1

    def save_draft(self, job, args):
        """[MINI-COMMENT: ASSISTANT.DRAFT]
        [EN rev.1]
        [Role] Stores a normalized unconfirmed task draft with source and revision in the reserved ledger.
        [Dependencies] Server-normalized partial fields, current uncancelled lease and per-turn draft cap.
        [Impact] Neither a model switch nor this storage tool executes or confirms equipment changes.
        """
        from .context import MAX_DRAFT, normalized_draft
        normalized = normalized_draft(args)
        with self.db(True) as db:
            current = self.job(job['id'], db)
            if current['state'] != 'running' or current['cancel']:
                raise AssistantError('작업이 중단되었습니다.', 409)
            old = db.execute('SELECT * FROM ai_task_drafts WHERE conversation=?', (job['conversation'],)).fetchone()
            revision = old['revision'] if old else 0
            if args['revision'] != revision:
                raise AssistantError('업무 초안이 변경되었습니다. 최신 초안을 확인해 주세요.', 409)
            source = db.execute("SELECT id FROM messages WHERE job=? AND role='user'", (job['id'],)).fetchone()[0]
            previous=json.loads(old['data']) if old else {}
            normalized['field_sources']={name:previous.get('field_sources',{}).get(name,source) if previous.get('fields',{}).get(name)==value else source for name,value in normalized['fields'].items()}
            data=canonical(normalized)
            if len(data)>MAX_DRAFT:
                raise AssistantError('업무 초안과 출처 크기 한도를 초과했습니다.',413)
            self._charge(db, job, len(data)-(len(old['data']) if old else 0))
            db.execute('INSERT INTO ai_task_drafts VALUES(?,?,?,?,?) ON CONFLICT(conversation) DO UPDATE SET revision=excluded.revision,data=excluded.data,source_message=excluded.source_message,updated=excluded.updated', (job['conversation'], revision+1, data, source, time.time()))
            return {'status':'UNCONFIRMED_DRAFT','revision':revision+1,'source_message':source,'data':json.loads(data)}

    def charge_handoff(self, db, job, context):
        """[MINI-COMMENT: ASSISTANT.HANDOFF.BUDGET]
        [EN rev.1]
        [Role] Charges the bounded persisted source summary against its separately reserved allowance.
        [Dependencies] First-step ContextBuilder output and the same writer as jobs.context persistence.
        [Impact] Derived summaries cannot create an unaccounted persistent storage path.
        """
        from .context import MAX_HANDOFF
        size=len(context[0]['content'])
        if size>MAX_HANDOFF:
            raise AssistantError('인계 요약의 보관 한도를 초과했습니다.',413)
        old=db.execute('SELECT handoff_chars FROM jobs WHERE id=?',(job['id'],)).fetchone()[0]
        self._charge(db,job,size-old)
        db.execute('UPDATE jobs SET handoff_chars=? WHERE id=?',(size,job['id']))
