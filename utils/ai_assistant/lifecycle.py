"""[MINI-COMMENT: ASSISTANT.LIFECYCLE]
[EN rev.3]
[Role] Adds owner-bound trash, title CAS receipts and content-free execution guards to AI v4.
[Dependencies] Store's short BEGIN IMMEDIATE transactions; no equipment database or model connection.
[Impact] Purging conversation content never frees an unconfirmed upstream request or deletes business/audit data.
"""
from contextlib import contextmanager
import math
import secrets
import time
import unicodedata

from .policy import AssistantError, ERROR_REASONS, digest, opaque

RETENTION_SECONDS = 30 * 86400
ACTIVE_GUARDS = ('running', 'draining', 'recovery_required')
LIFECYCLE_COLUMNS = {'is_deleted', 'deleted_at', 'purge_after', 'lifecycle_revision'}
METADATA = ('id', 'is_deleted', 'deleted_at', 'purge_after', 'lifecycle_revision')
TITLE_LIMIT = 100
TITLE_BIDI_CONTROLS = frozenset('\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_execution_guards(job TEXT PRIMARY KEY,resource_group TEXT NOT NULL,owner INTEGER NOT NULL,account_key TEXT NOT NULL,worker TEXT,lease_hash TEXT,epoch TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('running','draining','recovery_required','released')),cancel INTEGER NOT NULL DEFAULT 0 CHECK(cancel IN (0,1)),heartbeat REAL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_group_request ON ai_execution_guards(resource_group) WHERE state IN ('running','draining','recovery_required');
CREATE INDEX IF NOT EXISTS execution_guard_owner ON ai_execution_guards(owner,account_key,state);
CREATE TABLE IF NOT EXISTS ai_lifecycle_operations(owner INTEGER NOT NULL,account_key TEXT NOT NULL,operation_id TEXT NOT NULL,conversation TEXT NOT NULL,action TEXT NOT NULL,expected_revision INTEGER NOT NULL,resulting_revision INTEGER NOT NULL,is_deleted INTEGER NOT NULL,deleted_at REAL,purge_after REAL,purged INTEGER NOT NULL DEFAULT 0,removed_chars INTEGER NOT NULL DEFAULT 0,released_reservation INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,PRIMARY KEY(owner,account_key,operation_id));
CREATE INDEX IF NOT EXISTS lifecycle_operation_conversation ON ai_lifecycle_operations(conversation);
CREATE INDEX IF NOT EXISTS lifecycle_operation_owner_time ON ai_lifecycle_operations(owner,account_key,created);
CREATE TABLE IF NOT EXISTS ai_lifecycle_tombstones(conversation TEXT PRIMARY KEY,owner INTEGER NOT NULL,account_key TEXT NOT NULL,lifecycle_revision INTEGER NOT NULL,operation_id TEXT NOT NULL,purged_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS conversation_active_owner ON conversations(owner,account_key,is_deleted,updated DESC,id DESC);
CREATE INDEX IF NOT EXISTS conversation_trash_owner ON conversations(owner,account_key,is_deleted,deleted_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS conversation_expiry ON conversations(purge_after,id) WHERE is_deleted=1;
'''


def validate_schema(db):
    """[Role] Rejects partial v4 deployments before any startup repair can conceal missing protection.
    [Dependencies] Existing schema metadata and the authoritative guard index, never table contents.
    [Impact] Old v3 code and incomplete migrations cannot silently reactivate trashed conversations.
    """
    if not LIFECYCLE_COLUMNS <= {r[1] for r in db.execute('PRAGMA table_info(conversations)')}:
        raise ValueError('incomplete assistant v4 lifecycle schema')
    for table, columns in {
        'ai_execution_guards': {'job', 'resource_group', 'owner', 'account_key', 'worker', 'lease_hash', 'epoch', 'state', 'cancel', 'heartbeat', 'created', 'updated'},
        'ai_lifecycle_operations': {'owner', 'account_key', 'operation_id', 'conversation', 'action', 'expected_revision', 'resulting_revision', 'is_deleted', 'deleted_at', 'purge_after', 'purged', 'removed_chars', 'released_reservation', 'created'},
        'ai_lifecycle_tombstones': {'conversation', 'owner', 'account_key', 'lifecycle_revision', 'operation_id', 'purged_at'},
    }.items():
        if not columns <= {r[1] for r in db.execute('PRAGMA table_info(' + table + ')')}:
            raise ValueError('incomplete assistant v4 control schema')
    index = db.execute("SELECT tbl_name,sql FROM sqlite_master WHERE type='index' AND name='one_group_request'").fetchone()
    expected = "createuniqueindexone_group_requestonai_execution_guards(resource_group)wherestatein('running','draining','recovery_required')"
    actual = ''.join(index['sql'].lower().split()).replace('ifnotexists', '') if index and index['sql'] else ''
    if index is None or index['tbl_name'] != 'ai_execution_guards' or actual != expected:
        raise ValueError('incomplete assistant v4 slot index')
    indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if not {'conversation_active_owner', 'conversation_trash_owner', 'conversation_expiry', 'lifecycle_operation_owner_time'} <= indexes:
        raise ValueError('incomplete assistant v4 lifecycle indexes')
    if db.execute("""SELECT 1 FROM conversations WHERE NOT (
        (is_deleted=0 AND deleted_at IS NULL AND purge_after IS NULL) OR
        (is_deleted=1 AND deleted_at IS NOT NULL AND purge_after=deleted_at+?))
        OR typeof(is_deleted)<>'integer' OR typeof(lifecycle_revision)<>'integer'
        OR lifecycle_revision<0 OR lifecycle_revision>=9223372036854775807
        OR (is_deleted=1 AND NOT (deleted_at>0 AND purge_after<32503680000)) LIMIT 1""", (RETENTION_SECONDS,)).fetchone():
        raise ValueError('inconsistent assistant lifecycle state')
    if db.execute("""SELECT 1 FROM jobs j LEFT JOIN ai_execution_guards g ON g.job=j.id
        WHERE j.state IN ('running','draining','recovery_required') AND
        (g.job IS NULL OR g.state NOT IN ('running','draining','recovery_required')
        OR g.resource_group<>j.resource_group OR g.lease_hash IS NOT j.lease_hash) LIMIT 1""").fetchone():
        raise ValueError('inconsistent assistant execution guard')
    if db.execute('SELECT 1 FROM conversations c JOIN ai_lifecycle_tombstones t ON t.conversation=c.id LIMIT 1').fetchone():
        raise ValueError('purged assistant conversation was restored without reconciliation')


def migrate(db, epoch):
    """[MINI-COMMENT: ASSISTANT.LIFECYCLE.MIGRATE]
    [EN rev.1]
    [Role] Upgrades v3 additively and transfers active slots before removing the jobs-bound index.
    [Dependencies] The same startup writer as provider migration; all old workers stopped by deployment.
    [Impact] Existing conversations default active; duplicate active groups abort the whole migration.
    """
    existing = {r[1] for r in db.execute('PRAGMA table_info(conversations)')}
    for name, sql in {
        'is_deleted': 'INTEGER NOT NULL DEFAULT 0 CHECK(is_deleted IN (0,1))',
        'deleted_at': 'REAL', 'purge_after': 'REAL',
        'lifecycle_revision': 'INTEGER NOT NULL DEFAULT 0 CHECK(lifecycle_revision>=0)',
    }.items():
        if name not in existing:
            db.execute('ALTER TABLE conversations ADD COLUMN ' + name + ' ' + sql)
    previous = db.execute("SELECT tbl_name FROM sqlite_master WHERE type='index' AND name='one_group_request'").fetchone()
    if previous and previous[0] == 'jobs':
        db.execute('DROP INDEX one_group_request')
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)
    db.execute("""INSERT OR IGNORE INTO ai_execution_guards
        (job,resource_group,owner,account_key,worker,lease_hash,epoch,state,cancel,heartbeat,created,updated)
        SELECT j.id,j.resource_group,j.owner,c.account_key,j.worker,j.lease_hash,?,j.state,j.cancel,j.heartbeat,j.created,j.updated
        FROM jobs j JOIN conversations c ON c.id=j.conversation
        WHERE j.state IN ('running','draining','recovery_required')""", (epoch,))
    db.execute('UPDATE ai_meta SET version=4')
    validate_schema(db)


class LifecycleStore:
    """[Role] Supplies lifecycle operations to Store without importing equipment or provider services.
    [Dependencies] Store.db, Store._account and the v4 control tables.
    [Impact] Every mutation and its content-free receipt commit or roll back together.
    """

    def _view(self, view):
        """[Role] Validates explicit history state. [Dependencies] Fixed values. [Impact] No implicit all-state access."""
        if view not in ('active', 'trash'):
            raise AssistantError('대화 목록 구분을 확인해 주세요.')
        return view

    @contextmanager
    def execution_gate(self, owner, cid, account_key):
        """[MINI-COMMENT: ASSISTANT.LIFECYCLE.BUSINESS_GATE]
        [EN rev.1]
        [Role] Serializes a short explicit business confirmation against trash/purge.
        [Dependencies] The caller re-reads its proposal and saves its receipt using this yielded AI writer.
        [Impact] Already entered commits finish before trash; inference/network waits must never enter this gate.
        """
        with self.db(True) as db:
            self.conversation(owner, cid, db, account_key)
            yield db

    def _operation_result(self, db, row, replayed=False):
        """[Role] Projects a durable mutation receipt without retaining title or message content.
        [Dependencies] The owner-bound operation row and optionally the current conversation state.
        [Impact] Replayed older operations report current metadata and never reapply an old deletion.
        """
        current = db.execute('SELECT * FROM conversations WHERE id=? AND owner=? AND account_key=?',
                             (row['conversation'], row['owner'], row['account_key'])).fetchone()
        metadata = {k: current[k] for k in METADATA} if current else {
            'id': row['conversation'], 'is_deleted': 1, 'deleted_at': row['deleted_at'],
            'purge_after': row['purge_after'], 'lifecycle_revision': row['resulting_revision']}
        tombstone = db.execute('SELECT lifecycle_revision FROM ai_lifecycle_tombstones WHERE conversation=?', (row['conversation'],)).fetchone()
        if tombstone:
            metadata['lifecycle_revision'] = tombstone[0]
        purged = current is None and tombstone is not None
        metadata['read_only'] = bool(metadata['is_deleted'])
        # A receipt never bypasses the thirty-day read boundary, even before the cleanup timer runs.
        renamed = row['action'].startswith('rename:')
        expired = current is not None and bool(current['is_deleted']) and time.time() >= current['purge_after']
        if renamed and current is not None and not expired:
            metadata['title'] = current['title']
        result = {'conversation': metadata, 'action': 'rename' if renamed else row['action'], 'operation_id': row['operation_id'],
                  'replayed': replayed, 'purged': purged, 'server_time': time.time()}
        if renamed:
            result['expired'] = bool(expired)
        return result

    def rename_conversation(self, owner, cid, account_key, title, expected_title, revision, operation_id):
        """[MINI-COMMENT: ASSISTANT.CONVERSATION.RENAME]
        [EN rev.2]
        [Role] Renames one active owner/account chat with title and lifecycle compare-and-swap checks.
        [Dependencies] The existing short writer and durable operation receipts; only a digest of both titles is retained in action.
        [Impact] Concurrent automatic titles, renames and trash cannot be overwritten silently. A retained rename receipt marks even the literal default title as manual without adding schema or copying title content into audit receipts; expired receipt replay returns state without revealing the title.
        """
        opaque(cid)
        opaque(operation_id)
        if not isinstance(title, str) or len(title) > 200 or any(unicodedata.category(char) in ('Cc', 'Cs', 'Zl', 'Zp') or char in TITLE_BIDI_CONTROLS for char in title):
            raise AssistantError('대화 이름에는 줄바꿈이나 제어 문자를 사용할 수 없습니다.')
        title = title.strip()
        if not 1 <= len(title) <= TITLE_LIMIT:
            raise AssistantError('대화 이름은 공백을 제외하고 1~100자로 입력해 주세요.')
        if not isinstance(expected_title, str) or len(expected_title) > 1000 or any(unicodedata.category(char) == 'Cs' for char in expected_title):
            raise AssistantError('현재 대화 이름을 새로 확인해 주세요.', 409)
        if type(revision) is not int or not 0 <= revision < 2**63-1:
            raise AssistantError('대화 상태를 새로 확인해 주세요.', 409)
        action = 'rename:' + digest([title, expected_title])
        with self.db(True) as db:
            previous = db.execute('SELECT * FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND operation_id=?',
                                  (owner, account_key, operation_id)).fetchone()
            if previous:
                if previous['conversation'] != cid or previous['action'] != action or previous['expected_revision'] != revision:
                    raise AssistantError('같은 조작 식별자에 다른 요청이 전달되었습니다.', 409)
                return self._operation_result(db, previous, True)
            if db.execute('SELECT COUNT(*) FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND created>=?',
                          (owner, account_key, time.time() - 60)).fetchone()[0] >= 60:
                raise AssistantError('대화 변경 요청이 많습니다. 잠시 후 다시 시도해 주세요.', 429)
            current = self.conversation(owner, cid, db, account_key)
            purposes = db.execute("SELECT COUNT(*),SUM(CASE WHEN purpose='chat' THEN 1 ELSE 0 END) FROM jobs WHERE conversation=?", (cid,)).fetchone()
            if purposes[0] and not purposes[1]:
                raise AssistantError('기능 시험 기록의 이름은 일반 대화 화면에서 바꿀 수 없습니다.', 409)
            if current['lifecycle_revision'] != revision or current['title'] != expected_title:
                raise AssistantError('다른 화면에서 대화 이름이나 상태가 변경되었습니다. 현재 이름을 확인해 주세요.', 409)
            db.execute('UPDATE conversations SET title=?,lifecycle_revision=lifecycle_revision+1 WHERE id=?', (title, cid))
            metadata = dict(current, title=title, lifecycle_revision=revision + 1)
            receipt = self._save_operation(db, owner, account_key, cid, action, revision, operation_id, metadata)
            return self._operation_result(db, receipt)

    def _save_operation(self, db, owner, account_key, cid, action, revision, operation_id, metadata, purged=0, removed=0, reserved=0):
        """[Role] Stores only identity/state/count evidence for exact mutation retries.
        [Dependencies] The mutation's existing AI writer. [Impact] Purged content is never copied into receipts.
        """
        db.execute('''INSERT INTO ai_lifecycle_operations(owner,account_key,operation_id,conversation,action,
            expected_revision,resulting_revision,is_deleted,deleted_at,purge_after,purged,removed_chars,released_reservation,created)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (owner, account_key, operation_id, cid, action, revision, metadata['lifecycle_revision'],
             metadata['is_deleted'], metadata['deleted_at'], metadata['purge_after'], purged, removed, reserved, time.time()))
        return db.execute('SELECT * FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND operation_id=?',
                          (owner, account_key, operation_id)).fetchone()

    def _stop_conversation(self, db, cid, now):
        """[Role] Cancels queued/proposed work and drains only this conversation's own active requests.
        [Dependencies] Existing AI writer and content-free guards. [Impact] Committed business results are preserved.
        """
        db.execute("""UPDATE ai_execution_guards SET cancel=1,
            state=CASE WHEN state='running' THEN 'draining' ELSE state END,updated=?
            WHERE job IN (SELECT id FROM jobs WHERE conversation=?) AND state IN ('running','draining','recovery_required')""", (now, cid))
        db.execute("""UPDATE jobs SET cancel=1,state=CASE WHEN state IN ('running','draining') THEN 'draining'
            WHEN state='recovery_required' THEN state ELSE 'cancelled' END,
            error=COALESCE(error,'대화가 휴지통으로 이동되어 작업이 중단되었습니다.'),
            error_code=COALESCE(error_code,'USER_CANCELLED'),updated=?
            WHERE conversation=? AND state NOT IN ('done','failed','cancelled')""", (now, cid))
        db.execute("UPDATE proposals SET state='cancelled' WHERE state='pending' AND job IN (SELECT id FROM jobs WHERE conversation=?)", (cid,))
        self.expire(db)

    def lifecycle(self, owner, cid, account_key, action, revision, operation_id):
        """[MINI-COMMENT: ASSISTANT.LIFECYCLE.MUTATE]
        [EN rev.1]
        [Role] Applies one owner/account/revision-bound trash, restore or explicit purge operation.
        [Dependencies] Server UTC, a 32-hex operation identity and the same writer as business confirmation.
        [Impact] Duplicate moves do not extend retention; restore never restarts cancelled requests or proposals.
        """
        opaque(cid)
        opaque(operation_id)
        if action not in ('trash', 'restore', 'purge') or type(revision) is not int or not 0 <= revision < 2**63-1:
            raise AssistantError('대화 변경 요청을 확인해 주세요.')
        with self.db(True) as db:
            old = db.execute('SELECT * FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND operation_id=?',
                             (owner, account_key, operation_id)).fetchone()
            if old:
                if old['conversation'] != cid or old['action'] != action or old['expected_revision'] != revision:
                    raise AssistantError('같은 조작 식별자에 다른 요청이 전달되었습니다.', 409)
                return self._operation_result(db, old, True)
            if db.execute('SELECT COUNT(*) FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND created>=?',
                          (owner, account_key, time.time() - 60)).fetchone()[0] >= 60:
                raise AssistantError('대화 변경 요청이 많습니다. 잠시 후 다시 시도해 주세요.', 429)
            conv = db.execute('SELECT * FROM conversations WHERE id=? AND owner=? AND account_key=?', (cid, owner, account_key)).fetchone()
            if conv is None:
                raise AssistantError('대화를 찾을 수 없습니다.', 404)
            if conv['lifecycle_revision'] != revision:
                raise AssistantError('다른 화면에서 대화 상태가 변경되었습니다. 목록을 다시 확인해 주세요.', 409)
            now = time.time()
            if action == 'trash':
                if not conv['is_deleted']:
                    self._stop_conversation(db, cid, now)
                    db.execute('UPDATE conversations SET is_deleted=1,deleted_at=?,purge_after=?,lifecycle_revision=lifecycle_revision+1 WHERE id=?',
                               (now, now + RETENTION_SECONDS, cid))
                elif now >= conv['purge_after']:
                    raise AssistantError('보관 기간이 끝난 대화입니다.', 410)
            elif action == 'restore':
                if conv['is_deleted']:
                    if now >= conv['purge_after']:
                        raise AssistantError('보관 기간이 끝나 복구할 수 없습니다.', 410)
                    db.execute('UPDATE conversations SET is_deleted=0,deleted_at=NULL,purge_after=NULL,lifecycle_revision=lifecycle_revision+1 WHERE id=?', (cid,))
            else:
                if not conv['is_deleted']:
                    raise AssistantError('휴지통으로 이동한 대화만 영구삭제할 수 있습니다.', 409)
                row = self._purge_record(db, dict(conv), operation_id, now)
                return self._operation_result(db, row)
            current = dict(db.execute('SELECT * FROM conversations WHERE id=?', (cid,)).fetchone())
            row = self._save_operation(db, owner, account_key, cid, action, revision, operation_id, current)
            return self._operation_result(db, row)

    def _purge_record(self, db, conv, operation_id, now):
        """[MINI-COMMENT: ASSISTANT.LIFECYCLE.PURGE]
        [EN rev.1]
        [Role] Deletes one conversation's content in FK order and charges its actual retained characters once.
        [Dependencies] Validated current row, AI writer, independent execution guards and storage ledger.
        [Impact] Audit artifacts, business data, providers, keys, revocations and active guard occupancy survive.
        """
        cid, owner, account_key = conv['id'], conv['owner'], conv['account_key']
        if db.execute('''SELECT 1 FROM messages m JOIN jobs j ON j.id=m.job
            WHERE j.conversation=? AND m.conversation<>? LIMIT 1''', (cid, cid)).fetchone():
            raise ValueError('cross-conversation assistant message reference')
        self._stop_conversation(db, cid, now)
        used = self._account(db, owner, account_key)
        removed = db.execute('SELECT COALESCE(SUM(length(content)+length(reasoning)),0) FROM messages WHERE conversation=?', (cid,)).fetchone()[0]
        removed += db.execute('SELECT COALESCE(SUM(handoff_chars),0) FROM jobs WHERE conversation=?', (cid,)).fetchone()[0]
        removed += db.execute('SELECT COALESCE(SUM(length(data)),0) FROM ai_task_drafts WHERE conversation=?', (cid,)).fetchone()[0]
        reserved = db.execute('SELECT COALESCE(SUM(reserved_chars),0) FROM jobs WHERE conversation=?', (cid,)).fetchone()[0]
        if used < removed:
            raise ValueError('assistant storage ledger does not cover purged content')
        changed = db.execute('UPDATE storage_accounts SET used_chars=used_chars-? WHERE owner=? AND account_key=? AND used_chars>=?',
                             (removed, owner, account_key, removed)).rowcount
        if changed != 1:
            raise ValueError('assistant storage ledger changed during purge')
        db.execute('DELETE FROM proposals WHERE job IN (SELECT id FROM jobs WHERE conversation=?)', (cid,))
        db.execute('DELETE FROM message_steps WHERE job IN (SELECT id FROM jobs WHERE conversation=?)', (cid,))
        db.execute('DELETE FROM ai_task_drafts WHERE conversation=?', (cid,))
        db.execute('DELETE FROM ai_selection_events WHERE conversation=?', (cid,))
        db.execute('DELETE FROM messages WHERE conversation=? OR job IN (SELECT id FROM jobs WHERE conversation=?)', (cid, cid))
        db.execute('DELETE FROM jobs WHERE conversation=?', (cid,))
        db.execute('DELETE FROM conversations WHERE id=?', (cid,))
        metadata = dict(conv, lifecycle_revision=conv['lifecycle_revision'] + 1, is_deleted=1)
        db.execute('INSERT INTO ai_lifecycle_tombstones VALUES(?,?,?,?,?,?)',
                   (cid, owner, account_key, metadata['lifecycle_revision'], operation_id, now))
        return self._save_operation(db, owner, account_key, cid, 'purge', conv['lifecycle_revision'], operation_id,
                                    metadata, 1, removed, reserved)

    def _purge_candidate(self, db, candidate, now):
        """[Role] Rechecks an expired scan candidate inside its deleting writer transaction.
        [Dependencies] State, revision and exact deadline match. [Impact] Restored/retrashed rows defeat stale GC scans.
        """
        row = db.execute('SELECT * FROM conversations WHERE id=? AND is_deleted=1 AND lifecycle_revision=? AND purge_after=? AND purge_after<=?',
                         (candidate['id'], candidate['lifecycle_revision'], candidate['purge_after'], now)).fetchone()
        if row is None:
            return False
        operation_id = digest(['assistant-retention-v4', row['id'], row['lifecycle_revision'], row['purge_after']])[:32]
        self._purge_record(db, dict(row), operation_id, now)
        return True

    def purge_expired(self, batch_size=25, max_batches=4):
        """[Role] Catches up expired content using indexed bounded batches and one short writer per batch.
        [Dependencies] Caller-owned process lock; failure rolls the current batch back for the next timer run.
        [Impact] No login/model request is needed and an older active execution guard remains occupied.
        """
        if type(batch_size) is not int or not 1 <= batch_size <= 100 or type(max_batches) is not int or not 1 <= max_batches <= 100:
            raise ValueError('invalid retention batch bounds')
        removed, batches = 0, 0
        for _ in range(max_batches):
            with self.db(True) as db:
                now = time.time()
                candidates = db.execute('SELECT id,lifecycle_revision,purge_after FROM conversations INDEXED BY conversation_expiry WHERE is_deleted=1 AND purge_after<=? ORDER BY purge_after,id LIMIT ?',
                                        (now, batch_size)).fetchall()
                if not candidates:
                    break
                count = sum(self._purge_candidate(db, dict(row), now) for row in candidates)
            removed += count
            batches += 1
            if len(candidates) < batch_size:
                break
        with self.db() as db:
            remaining = bool(db.execute('SELECT 1 FROM conversations WHERE is_deleted=1 AND purge_after<=? LIMIT 1', (time.time(),)).fetchone())
        return {'purged': removed, 'batches': batches, 'more_expired': remaining}

    def _guard_lease(self, db, jid, token):
        """[Role] Authenticates a content-independent worker lease, including late reports after purge.
        [Dependencies] Current server epoch and constant-time comparison. [Impact] Old restored-DB leases stay invalid.
        """
        row = db.execute('SELECT * FROM ai_execution_guards WHERE job=?', (opaque(jid),)).fetchone()
        if row is None or row['epoch'] != self.epoch or not isinstance(token, str) or not secrets.compare_digest(row['lease_hash'] or '', digest([self.epoch, token])):
            raise AssistantError('이 작업의 처리 권한이 만료되었습니다.', 409)
        return dict(row)

    def guard_event(self, jid, token):
        """[Role] Acknowledges discarded chunks after trash/purge without saving any model output.
        [Dependencies] Authenticated internal route and a retained execution lease.
        [Impact] Late worker traffic cannot recreate a deleted job/conversation or consume storage again.
        """
        with self.db(True) as db:
            job = db.execute('SELECT j.steps,j.cancel,c.is_deleted FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.id=?', (opaque(jid),)).fetchone()
            if job is not None and not job['is_deleted'] and not job['cancel']:
                return None
            guard = self._guard_lease(db, jid, token)
            if guard['state'] in ACTIVE_GUARDS:
                db.execute('UPDATE ai_execution_guards SET heartbeat=?,updated=?,cancel=1 WHERE job=?', (time.time(), time.time(), jid))
            step = db.execute('SELECT length(reasoning),length(content) FROM message_steps WHERE job=? AND step=?', (jid, job['steps'])).fetchone() if job else None
            return {'accepted': False, 'cancel': True, 'reasoning_offset': step[0] if step else 0,
                    'content_offset': step[1] if step else 0}

    def guard_finish(self, jid, token, outcome):
        """[MINI-COMMENT: ASSISTANT.LIFECYCLE.GUARD_FINISH]
        [EN rev.1]
        [Role] Finalizes stopped requests without output while preserving their first cause and terminal classification.
        [Dependencies] Retained lease and Store.finish's distinction between user/auth cancellation and other failures.
        [Impact] Unknown upstream termination stays occupied; repeated known completion cannot relabel a saved failure.
        """
        if outcome not in ('complete', 'failed', 'cancelled', 'recovery_required'):
            raise AssistantError('작업 완료 상태가 올바르지 않습니다.')
        with self.db(True) as db:
            job = db.execute('SELECT j.*,c.is_deleted FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.id=?', (opaque(jid),)).fetchone()
            if job is not None and not job['is_deleted'] and not job['cancel']:
                return None
            guard = self._guard_lease(db, jid, token)
            if guard['state'] == 'released':
                return job['state'] if job is not None and job['state'] in ('failed', 'cancelled') else 'cancelled'
            unknown = outcome == 'recovery_required'
            error_code = (job['error_code'] if job is not None else None) or ('STREAM_INCOMPLETE' if unknown else 'USER_CANCELLED')
            state = 'recovery_required' if unknown else 'cancelled' if error_code in ('USER_CANCELLED', 'AUTH_EXPIRED') else 'failed'
            now = time.time()
            db.execute('UPDATE ai_execution_guards SET state=?,cancel=1,updated=? WHERE job=?', ('recovery_required' if unknown else 'released', now, jid))
            if job:
                db.execute('UPDATE jobs SET state=?,cancel=1,error=COALESCE(error,?),error_code=COALESCE(error_code,?),updated=? WHERE id=?',
                           (state, ERROR_REASONS.get(error_code, ERROR_REASONS['PROCESSING_FAILED']), error_code, now, jid))
                db.execute("UPDATE proposals SET state='cancelled' WHERE job=? AND state='pending'", (jid,))
                self.expire(db)
            return state

    def acknowledge_finished(self, jid):
        """[Role] Releases one explicitly confirmed finished own request even after its content was purged.
        [Dependencies] Trusted operator-only HTTP acknowledgement; never a browser/model authorization.
        [Impact] No timeout or automatic cleanup guesses whether shared upstream work has stopped.
        """
        with self.db(True) as db:
            row = db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (opaque(jid),)).fetchone()
            if row is None or row[0] not in ACTIVE_GUARDS:
                raise AssistantError('복구 대상 상태가 아닙니다.', 409)
            now = time.time()
            db.execute("UPDATE ai_execution_guards SET state='released',cancel=1,updated=? WHERE job=?", (now, jid))
            db.execute("UPDATE jobs SET state='failed',cancel=1,error=COALESCE(error,'이전 자체 요청 종료 확인 후 복구되었습니다.'),error_code=COALESCE(error_code,'PROCESSING_FAILED'),updated=? WHERE id=?", (now, jid))
            db.execute("UPDATE proposals SET state='cancelled' WHERE job=? AND state='pending'", (jid,))
            self.expire(db)

    def export_deletion_ledger(self):
        """[MINI-COMMENT: ASSISTANT.LIFECYCLE.RESTORE_LEDGER]
        [EN rev.1]
        [Role] Exports content-free purge/expired decisions before an operator replaces/restores the AI database.
        [Dependencies] An offline restore procedure that preserves this latest ledger outside the restored DB.
        [Impact] A historical backup cannot independently authorize re-exposing an already purged conversation.
        """
        with self.db() as db:
            rows = db.execute('SELECT conversation,owner,account_key,lifecycle_revision,operation_id,purged_at FROM ai_lifecycle_tombstones ORDER BY conversation LIMIT 10001').fetchall()
            records = [dict(row) for row in rows]
            if len(records) > 10000:
                raise ValueError('deletion ledger exceeds the reviewed export bound')
            expired = db.execute('''SELECT id,owner,account_key,lifecycle_revision,purge_after FROM conversations
                WHERE is_deleted=1 AND purge_after<=? ORDER BY purge_after,id LIMIT ?''', (time.time(), 10001 - len(records))).fetchall()
            for row in expired:
                records.append({'conversation': row['id'], 'owner': row['owner'], 'account_key': row['account_key'],
                                'lifecycle_revision': row['lifecycle_revision'] + 1,
                                'operation_id': digest(['assistant-retention-v4', row['id'], row['lifecycle_revision'], row['purge_after']])[:32],
                                'purged_at': row['purge_after']})
            if len(records) > 10000 or len({row['conversation'] for row in records}) != len(records):
                raise ValueError('deletion ledger exceeds bounds or contains conflicting identities')
            return {'format': 'assistant-deletion-ledger-v1', 'tombstones': records}

    def reconcile_deletion_ledger(self, ledger):
        """[Role] Reapplies a retained purge ledger to a restored v4 DB before any service can serve its content.
        [Dependencies] Closed bounded metadata, exact owner/account identities and maintenance-only process access.
        [Impact] Purges restored bodies transactionally and preserves tombstones/receipts; reruns are idempotent.
        """
        if not isinstance(ledger, dict) or set(ledger) != {'format', 'tombstones'} or ledger['format'] != 'assistant-deletion-ledger-v1' or not isinstance(ledger['tombstones'], list) or len(ledger['tombstones']) > 10000:
            raise ValueError('invalid deletion ledger format')
        fields = {'conversation', 'owner', 'account_key', 'lifecycle_revision', 'operation_id', 'purged_at'}
        seen = set()
        seen_operations = set()
        for item in ledger['tombstones']:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError('invalid deletion ledger fields')
            opaque(item['conversation'])
            opaque(item['operation_id'])
            if item['conversation'] in seen or type(item['owner']) is not int or not 0 < item['owner'] < 2**63 or not isinstance(item['account_key'], str) or not 1 <= len(item['account_key']) <= 256 or type(item['lifecycle_revision']) is not int or not 1 <= item['lifecycle_revision'] < 2**63-1 or type(item['purged_at']) not in (int, float) or not math.isfinite(item['purged_at']) or not 0 < item['purged_at'] < 32503680000:
                raise ValueError('invalid deletion ledger identity/state')
            operation = (item['owner'], item['account_key'], item['operation_id'])
            if operation in seen_operations:
                raise ValueError('duplicate deletion ledger operation identity')
            seen.add(item['conversation'])
            seen_operations.add(operation)
        removed = 0
        # Full identity preflight occurs before any batch commits. A service must remain stopped until all batches succeed.
        with self.db() as db:
            for item in ledger['tombstones']:
                for table, key in (('conversations', 'id'), ('ai_lifecycle_tombstones', 'conversation')):
                    old = db.execute('SELECT owner,account_key FROM ' + table + ' WHERE ' + key + '=?', (item['conversation'],)).fetchone()
                    if old and (old['owner'] != item['owner'] or old['account_key'] != item['account_key']):
                        raise ValueError('deletion ledger owner/account collision')
                old = db.execute('SELECT conversation,action FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND operation_id=?',
                                 (item['owner'], item['account_key'], item['operation_id'])).fetchone()
                if old and (old['conversation'] != item['conversation'] or old['action'] != 'purge'):
                    raise ValueError('deletion ledger operation collision')
                current = db.execute('SELECT lifecycle_revision FROM conversations WHERE id=?', (item['conversation'],)).fetchone()
                if current and current['lifecycle_revision'] >= item['lifecycle_revision']:
                    raise ValueError('restored conversation has a conflicting lifecycle revision')
        for offset in range(0, len(ledger['tombstones']), 25):
            with self.db(True) as db:
                for item in ledger['tombstones'][offset:offset + 25]:
                    cid = item['conversation']
                    current = db.execute('SELECT * FROM conversations WHERE id=?', (cid,)).fetchone()
                    old_tombstone = db.execute('SELECT * FROM ai_lifecycle_tombstones WHERE conversation=?', (cid,)).fetchone()
                    if current and (current['owner'] != item['owner'] or current['account_key'] != item['account_key']):
                        raise ValueError('deletion ledger owner/account changed')
                    if old_tombstone and (old_tombstone['owner'] != item['owner'] or old_tombstone['account_key'] != item['account_key']):
                        raise ValueError('deletion tombstone owner/account changed')
                    if current and current['lifecycle_revision'] >= item['lifecycle_revision']:
                        raise ValueError('restored conversation has a conflicting lifecycle revision')
                    if old_tombstone and old_tombstone['lifecycle_revision'] > item['lifecycle_revision']:
                        if current:
                            raise ValueError('stale deletion ledger for restored content')
                        continue
                    if current:
                        db.execute('DELETE FROM ai_lifecycle_tombstones WHERE conversation=?', (cid,))
                        self._purge_record(db, dict(current), secrets.token_hex(16), time.time())
                        removed += 1
                    db.execute('''INSERT INTO ai_lifecycle_tombstones VALUES(?,?,?,?,?,?)
                        ON CONFLICT(conversation) DO UPDATE SET lifecycle_revision=excluded.lifecycle_revision,
                        operation_id=excluded.operation_id,purged_at=excluded.purged_at''',
                        (cid, item['owner'], item['account_key'], item['lifecycle_revision'], item['operation_id'], item['purged_at']))
                    if not db.execute('SELECT 1 FROM ai_lifecycle_operations WHERE owner=? AND account_key=? AND operation_id=?',
                                      (item['owner'], item['account_key'], item['operation_id'])).fetchone():
                        metadata = {'lifecycle_revision': item['lifecycle_revision'], 'is_deleted': 1, 'deleted_at': None, 'purge_after': None}
                        self._save_operation(db, item['owner'], item['account_key'], cid, 'purge', item['lifecycle_revision'] - 1,
                                             item['operation_id'], metadata, 1)
        return {'reconciled': len(ledger['tombstones']), 'purged_restored': removed}
