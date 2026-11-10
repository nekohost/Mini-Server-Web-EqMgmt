"""[MINI-COMMENT: ASSISTANT.PROVIDERS]
[EN rev.5]
[Role] Stores immutable connections and verified, published model identities in the private AI database.
[Dependencies] Store v4 lifecycle/guard migration, deployment endpoint policy and optional standard Fernet with an external key.
[Impact] Browser/model callers receive opaque choices; active jobs retain their accepted route and credentials.
"""
import json
import time
import uuid
from urllib.parse import urlsplit

from .policy import AssistantError, LEVELS, canonical, object_only, text
from .reasoning import LEGACY_UI, VERSION as REASONING_VERSION, known_levels, normalize_profile, public_settings, validate_settings
from .transport import EndpointPolicy, model_request
from .provider_trust import BeforeSendError, LEGACY_PROVIDER, STRATA_HTTP, RevisionPolicy, certificate, check_peer, origin, resolve_addresses
from . import provider_candidates as candidates

PROTOCOL = 4
LEGACY_MODEL = '0' * 31 + '2'
LEGACY_GROUP = '0' * 31 + '3'


def public_source(snapshot):
    """[MINI-COMMENT: ASSISTANT.PROVIDERS.PUBLIC_SOURCE]
    [EN rev.2]
    [Role] Projects immutable answer provenance without disclosing API addresses, IDs or credentials.
    [Dependencies] Server-owned route JSON; historical unattributed jobs remain explicitly unattributed.
    [Impact] An isolated mail turn is identifiable in live and restored history using its accepted route.
    """
    route=json.loads(snapshot)
    if not route:
        return None
    source = {k:route.get(k) for k in ('provider_name','model_label','revision','reasoning_effort')}
    if 'mail_translation' in route:
        source['mail_translation'] = route['mail_translation']
    return source

SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_resource_groups(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS ai_providers(id TEXT PRIMARY KEY,name TEXT NOT NULL,revision INTEGER NOT NULL,enabled INTEGER NOT NULL,retired INTEGER NOT NULL DEFAULT 0,manual INTEGER NOT NULL DEFAULT 0,sort_order INTEGER NOT NULL DEFAULT 0,last_checked REAL,last_error TEXT);
CREATE TABLE IF NOT EXISTS ai_provider_revisions(provider TEXT NOT NULL,revision INTEGER NOT NULL,base_url TEXT NOT NULL,adapter TEXT NOT NULL,resource_group TEXT NOT NULL REFERENCES ai_resource_groups(id),credential TEXT NOT NULL DEFAULT '',created REAL NOT NULL,PRIMARY KEY(provider,revision));
CREATE TABLE IF NOT EXISTS ai_provider_models(id TEXT PRIMARY KEY,provider TEXT NOT NULL REFERENCES ai_providers(id),upstream TEXT NOT NULL,label TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 1,present INTEGER NOT NULL DEFAULT 1,manual INTEGER NOT NULL DEFAULT 0,sort_order INTEGER NOT NULL DEFAULT 0,context_tokens INTEGER NOT NULL DEFAULT 4096,profile TEXT NOT NULL DEFAULT '{}',verified_revision INTEGER,checked REAL,UNIQUE(provider,upstream));
CREATE TABLE IF NOT EXISTS ai_provider_settings(id INTEGER PRIMARY KEY CHECK(id=1),default_model TEXT);
INSERT OR IGNORE INTO ai_provider_settings(id) VALUES(1);
CREATE TABLE IF NOT EXISTS ai_task_drafts(conversation TEXT PRIMARY KEY REFERENCES conversations(id),revision INTEGER NOT NULL,data TEXT NOT NULL,source_message INTEGER NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ai_selection_events(id INTEGER PRIMARY KEY,conversation TEXT NOT NULL,selection TEXT,level TEXT NOT NULL,revision INTEGER NOT NULL,created REAL NOT NULL);
'''


def migrate(db):
    """[MINI-COMMENT: ASSISTANT.PROVIDERS.MIGRATE]
    [EN rev.3]
    [Role] Adds routing/selection/draft fields without downgrading a v4 lifecycle/guard database.
    [Dependencies] Store's startup writer transaction and per-revision trust migration.
    [Impact] Legacy active requests retain a dedicated group; no global slot is silently freed.
    """
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)
    candidates.migrate_trust(db)
    additions = {
        'conversations': {'selection_id': 'TEXT', 'next_level': "TEXT NOT NULL DEFAULT 'low'", 'selection_revision': 'INTEGER NOT NULL DEFAULT 0'},
        'jobs': {'selection_id': 'TEXT', 'route_snapshot': "TEXT NOT NULL DEFAULT '{}'", 'resource_group': 'TEXT', 'purpose': "TEXT NOT NULL DEFAULT 'chat'", 'probe_plan': "TEXT NOT NULL DEFAULT '[]'", 'handoff_chars':'INTEGER NOT NULL DEFAULT 0'},
    }
    for table, columns in additions.items():
        existing = {r[1] for r in db.execute('PRAGMA table_info(' + table + ')')}
        for name, sql in columns.items():
            if name not in existing:
                db.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + name + ' ' + sql)
    if 'last_owner' not in {r[1] for r in db.execute('PRAGMA table_info(ai_resource_groups)')}:
        db.execute('ALTER TABLE ai_resource_groups ADD COLUMN last_owner INTEGER')
    if 'profile_revision' not in {r[1] for r in db.execute('PRAGMA table_info(ai_provider_models)')}:
        db.execute('ALTER TABLE ai_provider_models ADD COLUMN profile_revision INTEGER NOT NULL DEFAULT 1')
    db.execute('INSERT OR IGNORE INTO ai_resource_groups(id,name) VALUES(?,?)', (LEGACY_GROUP, '기존 Strata 자원'))
    db.execute('UPDATE jobs SET resource_group=? WHERE resource_group IS NULL', (LEGACY_GROUP,))
    # Historical messages are deliberately not attributed to an invented provider/model.
    db.execute('DROP INDEX IF EXISTS one_application_request')
    if db.execute('SELECT version FROM ai_meta').fetchone()[0] < 4:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_group_request ON jobs(resource_group) WHERE state IN ('running','draining','recovery_required')")
    db.execute('CREATE INDEX IF NOT EXISTS group_queue ON jobs(resource_group,state,queue_order)')
    db.execute('UPDATE ai_meta SET version=3 WHERE version<3')


class Registry:
    """[Role] Provides server-only registry mutations, sanitized choices and immutable job routes.
    [Dependencies] Live admin checks at HTTP boundary, AI Store and deployment-owned network/secret settings.
    [Impact] No provider administration operation is exposed as a model tool.
    """
    def __init__(self, store, config):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.INIT]
        [EN rev.3]
        [Role] Implements init within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        self.store, self.config = store, config
        base = config.get('USER_AI_STRATA_URL', 'http://192.168.0.14:8080')
        rules = config.get('USER_AI_ALLOWED_ENDPOINTS')
        self.policy = EndpointPolicy(json.loads(rules) if isinstance(rules, str) else rules if rules is not None else [base])
        with store.db(True) as db:
            upgraded = False
            if not db.execute('SELECT 1 FROM ai_providers LIMIT 1').fetchone():
                upgraded = bool(db.execute('SELECT 1 FROM conversations LIMIT 1').fetchone())
                db.execute('INSERT INTO ai_providers(id,name,revision,enabled,last_checked) VALUES(?,?,?,?,?)', (LEGACY_PROVIDER, '기존 Strata', 1, 1, time.time()))
                db.execute('INSERT INTO ai_provider_revisions VALUES(?,?,?,?,?,?,?)', (LEGACY_PROVIDER, 1, base, 'strata', LEGACY_GROUP, 'env:USER_AI_STRATA_KEY', time.time()))
                db.execute('INSERT INTO ai_provider_trust(provider,revision,origin) VALUES(?,1,?)', (LEGACY_PROVIDER,origin(base)))
                model_id = config.get('USER_AI_MODEL', 'qwen3.8-flash-next-iq3_xxs')
                approved = known_levels(model_id, 'strata') is not None
                profile = normalize_profile(model_id, 'strata', {'chat': approved, 'tools': approved, 'levels': ['low','medium','high'] if approved else [], 'evidence': '기존 승인된 Qwen/Strata 프로필 및 공식 모델의 지원 단계 사전 설정; 신규 연결은 별도 시험 필요'})
                db.execute('INSERT INTO ai_provider_models(id,provider,upstream,label,context_tokens,profile,verified_revision,checked) VALUES(?,?,?,?,?,?,?,?)', (LEGACY_MODEL, LEGACY_PROVIDER, model_id, 'Qwen3.8 Flash Next' if approved else '기존 연결 모델 · 시험 필요', 65536, canonical(profile), 1 if approved else None, time.time()))
                db.execute('UPDATE ai_provider_settings SET default_model=?', (LEGACY_MODEL,))
            # Upgrade only next-turn choices and profile names. Accepted route snapshots/history stay byte-for-byte intact.
            for model in db.execute('''SELECT m.id,m.upstream,m.profile,r.adapter FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider
                    JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision''').fetchall():
                old_profile = json.loads(model['profile'])
                if old_profile.get('reasoning_version') == REASONING_VERSION:
                    continue
                profile = normalize_profile(model['upstream'], model['adapter'], old_profile)
                db.execute('UPDATE ai_provider_models SET profile=? WHERE id=?', (canonical(profile), model['id']))
                for old, new in LEGACY_UI.items():
                    next_level = 'default' if not profile['levels'] and old == 'low' else new
                    db.execute('UPDATE conversations SET next_level=?,selection_revision=selection_revision+1 WHERE selection_id=? AND next_level=?', (next_level, model['id'], old))
                upgraded = True
            if upgraded:
                db.execute("UPDATE conversations SET next_level=CASE next_level WHEN 'low' THEN 'off' WHEN 'high' THEN 'xhigh' ELSE next_level END,selection_revision=selection_revision+1 WHERE selection_id IS NULL AND next_level IN ('low','high')")
            # v1/v2 did not store the actual route. A new environment default is not evidence of that route.
            for row in db.execute("SELECT id,level FROM jobs WHERE selection_id IS NULL AND state IN ('queued','running','draining','recovery_required')").fetchall():
                db.execute("""UPDATE jobs SET state=CASE WHEN state='queued' THEN 'failed' ELSE 'recovery_required' END,
                    cancel=1,error=COALESCE(error,'이전 버전 요청의 실제 모델/연결 기록이 없습니다. 자체 요청 종료 확인 후 새 요청으로 이어 주세요.'),
                    error_code=COALESCE(error_code,'PROCESSING_FAILED') WHERE id=?""",(row['id'],))
                db.execute("UPDATE proposals SET state='cancelled' WHERE job=? AND state='pending'",(row['id'],))
                db.execute("""UPDATE ai_execution_guards SET state='recovery_required',cancel=1,updated=?
                    WHERE job=? AND state IN ('running','draining','recovery_required')""", (time.time(), row['id']))
            store.expire(db)

    def secret(self, credential, legacy_worker=False):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.SECRET]
        [EN rev.1]
        [Role] Resolves encrypted or fixed legacy env credentials only in the server/worker boundary.
        [Dependencies] Dedicated external Fernet key, never Flask's signing key or a browser-selected env name.
        [Impact] Credentials cannot be read back through administrator or user list APIs.
        """
        if credential == 'env:USER_AI_STRATA_KEY':
            return self.config.get('USER_AI_STRATA_KEY', '')
        if not credential:
            return ''
        if not credential.startswith('fernet:'):
            raise AssistantError('연결 인증 설정을 확인해 주세요.', 503)
        try:
            from cryptography.fernet import Fernet, MultiFernet
            previous=self.config.get('USER_AI_PROVIDER_PREVIOUS_KEYS','[]')
            previous=json.loads(previous) if isinstance(previous,str) else previous
            if not isinstance(previous,list) or len(previous)>8:
                raise ValueError('invalid previous-key ring')
            keys=[self.config['USER_AI_PROVIDER_ENCRYPTION_KEY'],*previous]
            return MultiFernet([Fernet(key) for key in keys]).decrypt(credential[7:].encode()).decode()
        except Exception:
            raise AssistantError('연결 인증키를 복원하지 못했습니다. 관리자에게 문의해 주세요.', 503) from None

    def encrypt(self, value):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.ENCRYPT]
        [EN rev.1]
        [Role] Encrypts one submitted API key with maintained authenticated cryptography.
        [Dependencies] cryptography.Fernet and a deployment key outside the AI DB/backup.
        [Impact] Missing dependency/key fails closed before a connection revision is saved.
        """
        if not isinstance(value, str) or len(value) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise AssistantError('인증키 형식을 확인해 주세요.')
        if not value:
            return ''
        try:
            from cryptography.fernet import Fernet
            return 'fernet:' + Fernet(self.config['USER_AI_PROVIDER_ENCRYPTION_KEY']).encrypt(value.encode()).decode()
        except Exception:
            raise AssistantError('서버의 독립 암호화 키와 cryptography 설치를 먼저 확인해 주세요.', 503) from None

    def _resolve(self, db, mid, allow_unverified=False, allow_disabled=False):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.RESOLVE]
        [EN rev.2]
        [Role] Builds a frozen route/profile from the current model and connection revision.
        [Dependencies] Registry writer/read transaction; no network call while a writer is held.
        [Impact] A missing/disabled saved choice is rejected, never silently replaced.
        """
        row = db.execute('''SELECT m.*,p.name,p.enabled,p.retired,p.revision,p.last_checked,p.last_error,r.base_url,r.adapter,r.resource_group,r.credential
            FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider
            JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision WHERE m.id=?''', (mid,)).fetchone()
        if row is None:
            raise AssistantError('선택한 모델이 없습니다. 모델을 다시 선택해 주세요.', 409)
        row = dict(row)
        if not allow_disabled and (not row['enabled'] or row['retired'] or not row['present'] or (not allow_unverified and not row['published'])):
            raise AssistantError('이 모델의 공개/연결이 중지되었습니다. 다시 선택해 주세요.', 409)
        profile = normalize_profile(row['upstream'], row['adapter'], json.loads(row['profile']))
        if not allow_unverified and (row['verified_revision'] != row['revision'] or not profile.get('chat') or profile['enabled_levels'] and not profile['levels']):
            raise AssistantError('현재 연결 설정의 모델 시험이 필요합니다.', 409)
        if not allow_unverified and row['last_error'] and not row['manual']:
            raise AssistantError('모델 목록 연결 확인에 실패했습니다. 관리자의 재확인 후 이용해 주세요.', 503)
        return {'selection_id': row['id'], 'provider_id': row['provider'], 'provider_name': row['name'], 'model': row['upstream'],
                'model_label': row['label'], 'revision': row['revision'], 'base_url': row['base_url'], 'adapter': row['adapter'],
                'resource_group': row['resource_group'], 'profile': profile, 'profile_revision':row['profile_revision'], 'context_tokens': row['context_tokens']}

    def resolve(self, mid, allow_unverified=False):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.RESOLVE]
        [EN rev.1]
        [Role] Implements resolve within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        with self.store.db() as db:
            return self._resolve(db, mid, allow_unverified)

    def choices(self):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.CHOICES]
        [EN rev.2]
        [Role] Publishes only safe labels/capabilities/status, never upstream IDs, addresses or keys.
        [Dependencies] Administrator publication order and last verified revision.
        [Impact] Identical upstream names on two providers remain distinct opaque choices.
        """
        with self.store.db() as db:
            models = []
            for row in db.execute('''SELECT m.*,p.name,p.revision,p.enabled,p.retired,p.last_checked,p.last_error,r.adapter FROM ai_provider_models m
                    JOIN ai_providers p ON p.id=m.provider JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision
                    WHERE m.published=1 ORDER BY p.sort_order,p.name,m.sort_order,m.label,m.id'''):
                profile = normalize_profile(row['upstream'], row['adapter'], json.loads(row['profile']))
                ready = bool(row['enabled'] and not row['retired'] and row['present'] and row['verified_revision'] == row['revision'] and profile.get('chat') and (not profile['enabled_levels'] or profile['levels']) and (not row['last_error'] or row['manual']))
                models.append({'id': row['id'], 'provider': row['name'], 'label': row['label'], 'available': ready,
                    'reason': '' if ready else '연결/공개 상태 또는 현재 설정의 모델 시험을 확인해 주세요.', 'tools': bool(profile.get('tools')) if ready else False,
                    'levels': profile.get('levels', []) if ready else [], 'last_checked': row['last_checked'],
                    **public_settings(row['upstream'], row['adapter'], profile)})
            default = db.execute('SELECT default_model FROM ai_provider_settings WHERE id=1').fetchone()[0]
        eligible = [m['id'] for m in models if m['available']]
        return {'models': models, 'default_model': default if default in eligible else (eligible[0] if eligible else None)}

    def admin_list(self):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.ADMIN_LIST]
        [EN rev.3]
        [Role] Shows active and candidate settings, approved IPs, CA metadata and probe progress to the admin.
        [Dependencies] Fixed column projection and protected HTTP route.
        [Impact] Encryption tokens and original secrets are never returned, even to administrators.
        """
        with self.store.db() as db:
            providers = [dict(r) for r in db.execute('''SELECT p.*,r.base_url,r.adapter,r.resource_group,
                (r.credential<>'') AS has_key,t.fingerprint,t.expires,t.addresses,t.revoked FROM ai_providers p
                LEFT JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision
                LEFT JOIN ai_provider_trust t ON t.provider=p.id AND t.revision=p.revision ORDER BY p.sort_order,p.name''')]
            for p in providers:
                row = db.execute('''SELECT c.revision,c.name,c.enabled,c.manual,c.sort_order,c.result,c.generation,
                    c.discovered,r.base_url,r.adapter,r.resource_group,(r.credential<>'') AS has_key,t.fingerprint,t.expires,t.addresses
                    FROM ai_provider_candidates c JOIN ai_provider_revisions r USING(provider,revision)
                    JOIN ai_provider_trust t USING(provider,revision) WHERE c.provider=?''', (p['id'],)).fetchone()
                p['candidate'] = dict(row) if row else None
                p['addresses'] = json.loads(p['addresses'] or '[]')
                if row:
                    p['candidate']['addresses'] = json.loads(row['addresses'])
                    p['candidate']['models'] = [dict(m) for m in db.execute('''SELECT c.id,c.upstream,c.label,
                        (c.proof IS NOT NULL) AS passed, m.context_tokens,m.profile FROM ai_candidate_models c
                        LEFT JOIN ai_provider_models m ON m.id=c.id WHERE c.provider=? ORDER BY c.label''', (p['id'],))]
                    for m in p['candidate']['models']:
                        m['profile'] = candidates.candidate_profile(m['upstream'], row['adapter'], m['profile'])
                p['trust_history'] = [dict(r) for r in db.execute('''SELECT revision,origin,fingerprint,expires,revoked
                    FROM ai_provider_trust WHERE provider=? ORDER BY revision DESC''', (p['id'],))]
                p['models'] = [dict(r) for r in db.execute('SELECT id,upstream,label,published,present,manual,sort_order,context_tokens,profile,verified_revision,profile_revision FROM ai_provider_models WHERE provider=? ORDER BY sort_order,label', (p['id'],))]
                for model in p['models']:
                    profile = normalize_profile(model['upstream'], p['adapter'], json.loads(model['profile']))
                    model['profile'] = canonical(profile)
                    model.update(public_settings(model['upstream'], p['adapter'], profile))
            groups = [dict(r) for r in db.execute('SELECT * FROM ai_resource_groups ORDER BY name')]
            default = db.execute('SELECT default_model FROM ai_provider_settings WHERE id=1').fetchone()[0]
        return {'providers': providers, 'groups': groups, 'default_model': default, 'encryption_configured': bool(self.config.get('USER_AI_PROVIDER_ENCRYPTION_KEY'))}

    def connection(self, pid, revision):
        """Resolve only an immutable DB version. Older rows seal their deployment-approved pins once."""
        with self.store.db() as db:
            row = db.execute('''SELECT t.*,r.credential,r.base_url,r.adapter FROM ai_provider_trust t
                JOIN ai_provider_revisions r USING(provider,revision) WHERE provider=? AND revision=?''', (pid, revision)).fetchone()
        if not row or row['revoked'] is not None:
            raise AssistantError('이 연결 버전의 신뢰가 철회되었거나 승인 정보가 없습니다.', 409)
        base = origin(row['base_url'])
        if origin(row['origin']) != base:
            raise BeforeSendError('저장된 주소와 승인한 출처가 다릅니다.')
        if row['addresses'] is None:
            if pid == LEGACY_PROVIDER and base == STRATA_HTTP:
                _, addresses, _ = resolve_addresses(base, pid)
            else:
                _, addresses, _ = self.policy.destination(base, all_addresses=True)
                for address in addresses:
                    check_peer(address)
            with self.store.db(True) as db:
                db.execute('''UPDATE ai_provider_trust SET origin=?,addresses=? WHERE provider=? AND revision=?
                    AND addresses IS NULL AND revoked IS NULL''', (base,canonical(addresses),pid,revision))
            return self.connection(pid, revision)
        trust = {'origin':base, 'addresses':json.loads(row['addresses']), 'ca_pem':row['ca_pem']}
        credential = row['credential']
        if credential == 'env:USER_AI_STRATA_KEY' and (pid != LEGACY_PROVIDER or
                base != origin(self.config.get('USER_AI_STRATA_URL', STRATA_HTTP))):
            raise AssistantError('기존 환경 키의 승인 출처가 다릅니다. 전용 키로 다시 등록해 주세요.', 409)
        return trust, credential

    @staticmethod
    def _editor(db, pid, data):
        old = db.execute('SELECT * FROM ai_providers WHERE id=?', (pid,)).fetchone()
        candidate = db.execute('SELECT revision FROM ai_provider_candidates WHERE provider=?', (pid,)).fetchone()
        if (data['revision'] != (old['revision'] if old else 0) or old and old['retired']
                or data.get('candidate_revision', 0) != (candidate[0] if candidate else 0)):
            raise AssistantError('다른 관리자가 연결을 변경했습니다. 새로고침해 주세요.', 409)
        revision = candidate[0] if candidate else old['revision'] if old else 0
        previous = db.execute('''SELECT r.*,t.ca_pem,t.fingerprint,t.expires,t.revoked,t.addresses
            FROM ai_provider_revisions r JOIN ai_provider_trust t USING(provider,revision)
            WHERE provider=? AND revision=?''', (pid, revision)).fetchone()
        return old, previous

    def save(self, data, pid=None, actor=0):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.SAVE]
        [EN rev.4]
        [Role] Saves an immutable revision and checks both active and candidate editor versions.
        [Dependencies] Server-approved LAN pins, origin-bound credentials and per-revision CA.
        [Impact] Only dedicated candidate probes can use an unpromoted address.
        """
        object_only(data, ('name','base_url','adapter','resource_group','new_group','enabled','retired','manual',
                           'sort_order','revision','api_key','candidate_revision','trust_mode','ca_pem'),
                    ('name','base_url','adapter','enabled','manual','revision'))
        name, base = text(data['name'], 80), origin(data['base_url'])
        retired, order = data.get('retired', False), data.get('sort_order', 0)
        if (data['adapter'] not in ('strata','openai') or any(type(data[k]) is not bool for k in ('enabled','manual'))
                or type(retired) is not bool or type(order) is not int or not 0 <= order <= 10000
                or type(data['revision']) is not int or type(data.get('candidate_revision',0)) is not int):
            raise AssistantError('연결 종류·상태·버전을 확인해 주세요.')
        creating = pid is None
        pid = pid or uuid.uuid4().hex
        with self.store.db() as db:
            old, previous = self._editor(db, pid, data)
            if not creating and not old:
                raise AssistantError('연결을 찾을 수 없습니다.', 404)
        same = bool(previous and origin(previous['base_url']) == base)
        # Stopping/retiring an unreachable active service is a local operation.
        pause = (old and old['enabled'] and not data['enabled'] and not data.get('candidate_revision') and same
                 and previous['adapter'] == data['adapter'] and previous['resource_group'] == data.get('resource_group')
                 and not data.get('new_group') and 'api_key' not in data and 'ca_pem' not in data
                 and data.get('trust_mode', 'private' if previous['fingerprint'] else 'system') == ('private' if previous['fingerprint'] else 'system'))
        if retired or pause:
            if not old:
                raise AssistantError('기존 연결에서만 중지·폐기할 수 있습니다.')
            with self.store.db(True) as db:
                self._editor(db, pid, data)
                db.execute('DELETE FROM ai_provider_candidates WHERE provider=?', (pid,))
                if pause and not retired:
                    # Advance the editor token without changing already accepted routes.
                    rev = db.execute('SELECT MAX(revision)+1 FROM ai_provider_revisions WHERE provider=?', (pid,)).fetchone()[0]
                    db.execute('''INSERT INTO ai_provider_revisions SELECT provider,?,base_url,adapter,resource_group,credential,?
                        FROM ai_provider_revisions WHERE provider=? AND revision=?''',(rev,time.time(),pid,old['revision']))
                    db.execute('''INSERT INTO ai_provider_trust SELECT provider,?,origin,addresses,ca_pem,fingerprint,expires,revoked
                        FROM ai_provider_trust WHERE provider=? AND revision=?''',(rev,pid,old['revision']))
                    db.execute('UPDATE ai_providers SET revision=?,enabled=0,name=?,manual=?,sort_order=? WHERE id=?',
                               (rev,name,data['manual'],order,pid))
                    db.execute('UPDATE ai_provider_models SET verified_revision=? WHERE provider=? AND verified_revision=?',(rev,pid,old['revision']))
                else:
                    rev = previous['revision']
                    db.execute('UPDATE ai_providers SET enabled=0,retired=1 WHERE id=?',(pid,))
                candidates.audit(db,pid,rev,actor,'retired' if retired else 'paused')
            return pid

        _, addresses, _ = resolve_addresses(base, pid)
        if base == STRATA_HTTP and data['adapter'] != 'strata':
            raise BeforeSendError('기존 260Strata 8080은 Strata 연결에서만 사용할 수 있습니다.')
        inherit = same and previous['revoked'] is None
        mode = data.get('trust_mode', 'private' if inherit and previous['fingerprint'] else 'system')
        if mode not in ('private', 'system') or mode == 'private' and not base.startswith('https://'):
            raise AssistantError('HTTPS 연결의 신뢰 방식을 확인해 주세요.')
        pem, fingerprint, expires = '', None, None
        if mode == 'private':
            pem, fingerprint, expires = certificate(data.get('ca_pem', previous['ca_pem'] if inherit else ''))
        elif 'ca_pem' in data:
            raise AssistantError('공개 CA를 등록하려면 사설 CA 방식을 선택해 주세요.')
        credential = (self.encrypt(data['api_key']) if 'api_key' in data else previous['credential'] if inherit else '')
        with self.store.db(True) as db:
            _, checked = self._editor(db, pid, data)
            if previous and checked['revoked'] != previous['revoked']:
                raise AssistantError('저장 중 연결 신뢰가 변경되었습니다. 새로고침해 주세요.',409)
            group = data.get('resource_group')
            if data.get('new_group'):
                group_name = text(data['new_group'], 80)
                if db.execute('SELECT 1 FROM ai_resource_groups WHERE name=?', (group_name,)).fetchone():
                    raise AssistantError('이미 등록된 자원 그룹 이름입니다.',409)
                group = uuid.uuid4().hex
                db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?)', (group,group_name))
            if not db.execute('SELECT 1 FROM ai_resource_groups WHERE id=?', (group,)).fetchone():
                raise AssistantError('물리 PC/백엔드 자원 그룹을 선택해 주세요.')
            endpoint = urlsplit(base)
            port = endpoint.port or (443 if endpoint.scheme == 'https' else 80)
            for other in db.execute('''SELECT r.base_url,t.addresses FROM ai_provider_revisions r
                    LEFT JOIN ai_provider_trust t USING(provider,revision) WHERE r.resource_group<>?''',(group,)):
                peer = urlsplit(origin(other['base_url']))
                peer_port = peer.port or (443 if peer.scheme == 'https' else 80)
                pins = json.loads(other['addresses']) if other['addresses'] else [peer.hostname]
                if port == peer_port and (endpoint.hostname == peer.hostname or set(addresses).intersection(pins)):
                    raise AssistantError('같은 API 주소·포트는 기존 물리 자원 그룹을 공유해야 합니다.',409)
            candidates.group_available(db, pid, group)
            if creating:
                if db.execute('SELECT COUNT(*) FROM ai_providers').fetchone()[0] >= 100:
                    raise AssistantError('연결 등록 한도(100개)에 도달했습니다.',429)
                db.execute('INSERT INTO ai_providers(id,name,revision,enabled) VALUES(?,?,0,0)',(pid,name))
            rev = db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM ai_provider_revisions WHERE provider=?',(pid,)).fetchone()[0]
            db.execute('INSERT INTO ai_provider_revisions VALUES(?,?,?,?,?,?,?)',(pid,rev,base,data['adapter'],group,credential,time.time()))
            db.execute('''INSERT INTO ai_provider_trust(provider,revision,origin,addresses,ca_pem,fingerprint,expires)
                VALUES(?,?,?,?,?,?,?)''',(pid,rev,base,canonical(addresses),pem,fingerprint,expires))
            if data.get('candidate_revision'):
                candidates.audit(db,pid,data['candidate_revision'],actor,'superseded')
            db.execute('DELETE FROM ai_provider_candidates WHERE provider=?',(pid,))
            db.execute('''INSERT INTO ai_provider_candidates(provider,revision,parent,name,enabled,manual,sort_order,result)
                VALUES(?,?,?,?,?,?,?,?)''',(pid,rev,data['revision'],name,data['enabled'],data['manual'],order,'주소 승인 · 모델 목록 조회 대기'))
            candidates.audit(db,pid,rev,actor,'candidate_saved')
        return pid

    def _inventory(self, pid, revision):
        trust, credential = self.connection(pid, revision)
        with model_request(RevisionPolicy(pid, trust), trust['origin'], '/models', self.secret(credential), timeout=15) as response:
            if response.status_code in (401,403):
                raise AssistantError('API 키 인증 단계에서 모델 서버가 조회를 거절했습니다.', 422)
            if 300 <= response.status_code < 400:
                raise AssistantError('주소 단계에서 리디렉션을 거절했습니다.', 422)
            if not 200 <= response.status_code < 300:
                raise AssistantError('모델 목록 단계에서 모델 서버가 조회를 거절했습니다.', 422)
            result = response.json()
        items = result.get('data') if isinstance(result, dict) else None
        if not isinstance(items, list) or len(items) > 500:
            raise AssistantError('모델 목록 형식 또는 개수를 확인해 주세요.', 422)
        ids = []
        for item in items:
            if not isinstance(item, dict):
                raise AssistantError('모델 목록 항목을 확인해 주세요.', 422)
            mid = text(item.get('id'), 200)
            if item.get('type') in ('embedding','embeddings','tts','audio','image') or any(x in mid.lower() for x in ('embedding','embed-','tts-')):
                continue
            ids.append((mid, mid.replace('\\','/').rsplit('/',1)[-1] or mid))
        return ids

    def discover(self, pid, force=False, candidate_revision=None, actor=0):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.DISCOVER]
        [EN rev.2]
        [Role] Reads a pinned inventory outside the writer transaction.
        [Dependencies] An explicit admin candidate revision, or the active version for ordinary discovery.
        [Impact] A late or failed candidate response cannot change the published catalogue.
        """
        with self.store.db(candidate_revision is not None) as db:
            if candidate_revision is None:
                row = db.execute('SELECT * FROM ai_providers WHERE id=? AND retired=0 AND revision>0',(pid,)).fetchone()
                if not row:
                    raise AssistantError('활성 연결을 찾을 수 없습니다.',404)
                revision = row['revision']
                if not force and row['last_checked'] and time.time()-row['last_checked'] < 60:
                    return
            else:
                row = candidates.pending(db,pid,candidate_revision)
                revision, generation = row['revision'], row['generation']+1
                db.execute("UPDATE ai_provider_candidates SET generation=?,discovered=0,result='모델 목록 조회 중' WHERE provider=?", (generation,pid))
        try:
            items = self._inventory(pid, revision)
            with self.store.db(True) as db:
                if candidate_revision is not None:
                    cand = candidates.pending(db,pid,revision,generation)
                    candidates.record_inventory(db,cand,items)
                    candidates.audit(db,pid,revision,actor,'models_passed')
                    return
                if not db.execute('''SELECT 1 FROM ai_providers p JOIN ai_provider_trust t ON t.provider=p.id AND t.revision=p.revision
                    WHERE p.id=? AND p.revision=? AND p.retired=0 AND t.revoked IS NULL''',(pid,revision)).fetchone():
                    raise AssistantError('조회 중 연결 설정이 변경되었습니다.',409)
                existing = {r[0] for r in db.execute('SELECT upstream FROM ai_provider_models WHERE provider=?',(pid,))}
                if len(existing | {mid for mid,_ in items}) > 500:
                    raise AssistantError('모델 보관 한도를 초과했습니다.',429)
                db.execute('UPDATE ai_provider_models SET present=manual WHERE provider=?',(pid,))
                for mid,label in items:
                    db.execute('''INSERT INTO ai_provider_models(id,provider,upstream,label,present,checked) VALUES(?,?,?,?,1,?)
                       ON CONFLICT(provider,upstream) DO UPDATE SET present=1,checked=excluded.checked''',(uuid.uuid4().hex,pid,mid,label,time.time()))
                db.execute('UPDATE ai_providers SET last_checked=?,last_error=NULL WHERE id=?',(time.time(),pid))
        except Exception as error:
            reason = str(error) if isinstance(error,AssistantError) else '모델 목록 응답을 확인하지 못했습니다.'
            with self.store.db(True) as db:
                if candidate_revision is not None:
                    candidates.pending(db,pid,revision,generation)
                    db.execute('UPDATE ai_provider_candidates SET result=? WHERE provider=?',(reason,pid))
                    candidates.audit(db,pid,revision,actor,reason)
                else:
                    db.execute('UPDATE ai_providers SET last_checked=?,last_error=? WHERE id=? AND revision=?',(time.time(),reason,pid,revision))
            raise AssistantError(reason, error.status if isinstance(error,AssistantError) else 422) from None

    def revoke_trust(self, pid, revision, actor):
        with self.store.db(True) as db:
            changed = db.execute('UPDATE ai_provider_trust SET revoked=? WHERE provider=? AND revision=? AND revoked IS NULL',
                                 (time.time(),pid,revision)).rowcount
            if not changed:
                raise AssistantError('철회할 연결 버전을 찾을 수 없습니다.',409)
            db.execute('''UPDATE ai_providers SET retired=1 WHERE id=? AND revision=0 AND EXISTS(
                SELECT 1 FROM ai_provider_candidates WHERE provider=? AND revision=?)''',(pid,pid,revision))
            db.execute('DELETE FROM ai_provider_candidates WHERE provider=? AND revision=?',(pid,revision))
            db.execute('UPDATE ai_provider_models SET verified_revision=NULL WHERE provider=? AND verified_revision=?',(pid,revision))
            reason = '관리자가 이 연결 버전의 신뢰를 철회하여 요청을 중단했습니다.'
            db.execute('UPDATE ai_providers SET last_error=? WHERE id=? AND revision=?',(reason,pid,revision))
            db.execute("""UPDATE jobs SET cancel=1,error=COALESCE(error,?),error_code=COALESCE(error_code,'PROVIDER_REVOKED'),
                state=CASE state WHEN 'queued' THEN 'failed' WHEN 'running' THEN 'draining' ELSE state END
                WHERE json_extract(route_snapshot,'$.provider_id')=? AND json_extract(route_snapshot,'$.revision')=?
                AND state IN ('queued','running','draining','recovery_required')""",(reason,pid,revision))
            db.execute("""UPDATE ai_execution_guards SET cancel=1,state=CASE state WHEN 'running' THEN 'draining' ELSE state END,updated=?
                WHERE state IN ('running','draining','recovery_required') AND job IN (SELECT id FROM jobs WHERE cancel=1
                AND json_extract(route_snapshot,'$.provider_id')=? AND json_extract(route_snapshot,'$.revision')=?)""",(time.time(),pid,revision))
            candidates.audit(db,pid,revision,actor,'revoked')
            self.store.expire(db)

    def update_model(self, pid, data):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.UPDATE_MODEL]
        [EN rev.2]
        [Role] Updates publication/context and bounded model reasoning policy, invalidating changed tested contracts.
        [Dependencies] Current provider revision, explicit manual opt-in, bounded basic profile fields.
        [Impact] Arbitrary request bodies/headers/API modes remain outside this admin surface.
        """
        object_only(data, ('id','upstream','label','published','sort_order','context_tokens','revision','default','reasoning_levels','reasoning_default','profile_revision'), ('label','published','sort_order','context_tokens','revision'))
        configuring = 'reasoning_levels' in data or 'reasoning_default' in data
        if configuring and not {'reasoning_levels','reasoning_default'} <= data.keys():
            raise AssistantError('허용 단계와 기본 추론 수준을 함께 저장해 주세요.')
        label = text(data['label'], 80)
        if type(data['revision']) is not int or type(data['published']) is not bool or type(data['sort_order']) is not int or not 0 <= data['sort_order'] <= 10000 or type(data['context_tokens']) is not int or not 2048 <= data['context_tokens'] <= 1048576 or type(data.get('default',False)) is not bool:
            raise AssistantError('모델 공개·순서·검증한 컨텍스트 한도를 확인해 주세요.')
        with self.store.db(True) as db:
            p = db.execute('SELECT * FROM ai_providers WHERE id=?', (pid,)).fetchone()
            if not p or p['retired'] or p['revision'] != data['revision']:
                raise AssistantError('연결 설정이 변경되었습니다. 새로고침해 주세요.', 409)
            if data.get('id'):
                m = db.execute('SELECT * FROM ai_provider_models WHERE id=? AND provider=?', (data['id'], pid)).fetchone()
                if not m:
                    raise AssistantError('모델을 찾을 수 없습니다.', 404)
                mid = m['id']
                if configuring and (type(data.get('profile_revision')) is not int or data['profile_revision'] != m['profile_revision']):
                    raise AssistantError('다른 관리자가 모델 설정을 수정했습니다. 새로고침해 주세요.', 409)
                adapter = db.execute('SELECT adapter FROM ai_provider_revisions WHERE provider=? AND revision=?', (pid, p['revision'])).fetchone()[0]
                profile = normalize_profile(m['upstream'], adapter, json.loads(m['profile']))
                prior = (profile['enabled_levels'], profile['default_level'])
                if configuring:
                    profile['enabled_levels'] = validate_settings(data['reasoning_levels'], data['reasoning_default'], known_levels(m['upstream'], adapter))
                    profile['default_level'] = data['reasoning_default']
                    profile = normalize_profile(m['upstream'], adapter, profile)
                changed = m['context_tokens'] != data['context_tokens'] or prior != (profile['enabled_levels'], profile['default_level'])
                db.execute('UPDATE ai_provider_models SET label=?,published=?,sort_order=?,verified_revision=?,profile_revision=profile_revision+?,context_tokens=?,profile=? WHERE id=?',
                           (label, data['published'], data['sort_order'], None if changed else m['verified_revision'], int(changed), data['context_tokens'], canonical(profile), mid))
            else:
                if not p['manual']:
                    raise AssistantError('수동 모델 등록은 이 연결의 관리자 선택사항을 켠 뒤 사용할 수 있습니다.', 403)
                if db.execute('SELECT COUNT(*) FROM ai_provider_models WHERE provider=?',(pid,)).fetchone()[0]>=500:
                    raise AssistantError('연결의 모델 등록 한도(500개)입니다.',429)
                mid = uuid.uuid4().hex
                upstream=text(data.get('upstream'),200)
                if db.execute('SELECT 1 FROM ai_provider_models WHERE provider=? AND upstream=?',(pid,upstream)).fetchone():
                    raise AssistantError('이 연결에 이미 등록된 모델 ID입니다. 기존 모델을 수정해 주세요.',409)
                adapter = db.execute('SELECT adapter FROM ai_provider_revisions WHERE provider=? AND revision=?', (pid, p['revision'])).fetchone()[0]
                profile = normalize_profile(upstream, adapter, {})
                if configuring:
                    profile['enabled_levels'] = validate_settings(data['reasoning_levels'], data['reasoning_default'], known_levels(upstream, adapter))
                    profile['default_level'] = data['reasoning_default']
                    profile = normalize_profile(upstream, adapter, profile)
                db.execute('INSERT INTO ai_provider_models(id,provider,upstream,label,published,manual,sort_order,context_tokens,profile) VALUES(?,?,?,?,?,1,?,?,?)', (mid, pid, upstream, label, data['published'], data['sort_order'], data['context_tokens'], canonical(profile)))
            if data.get('default'):
                db.execute('UPDATE ai_provider_settings SET default_model=? WHERE id=1', (mid,))
        return mid

