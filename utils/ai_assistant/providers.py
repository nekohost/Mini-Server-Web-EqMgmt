"""[MINI-COMMENT: ASSISTANT.PROVIDERS]
[EN rev.2]
[Role] Stores immutable connections and verified, published model identities in the private AI database.
[Dependencies] Store v3, deployment endpoint policy and optional standard Fernet with an external key.
[Impact] Browser/model callers receive opaque choices; active jobs retain their accepted route and credentials.
"""
import json
import time
import uuid

from .policy import AssistantError, LEVELS, canonical, object_only, text
from .reasoning import LEGACY_UI, VERSION as REASONING_VERSION, known_levels, normalize_profile, public_settings, validate_settings
from .transport import EndpointPolicy, model_request

PROTOCOL = 3
LEGACY_PROVIDER = '0' * 31 + '1'
LEGACY_MODEL = '0' * 31 + '2'
LEGACY_GROUP = '0' * 31 + '3'


def public_source(snapshot):
    """[MINI-COMMENT: ASSISTANT.PROVIDERS.PUBLIC_SOURCE]
    [EN rev.1]
    [Role] Projects immutable answer provenance without disclosing API addresses, IDs or credentials.
    [Dependencies] Server-owned route JSON; historical unattributed jobs remain explicitly unattributed.
    [Impact] Renaming a provider/model cannot relabel earlier accepted responses.
    """
    route=json.loads(snapshot)
    return {k:route.get(k) for k in ('provider_name','model_label','revision','reasoning_effort')} if route else None

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
    [EN rev.1]
    [Role] Adds v3 routing/selection/draft fields while preserving v1/v2 history and unknown locks.
    [Dependencies] Store's single startup writer transaction; old workers must be stopped before migration.
    [Impact] Legacy active requests retain a dedicated group; no global slot is silently freed.
    """
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)
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
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_group_request ON jobs(resource_group) WHERE state IN ('running','draining','recovery_required')")
    db.execute('CREATE INDEX IF NOT EXISTS group_queue ON jobs(resource_group,state,queue_order)')
    db.execute('UPDATE ai_meta SET version=3')


class Registry:
    """[Role] Provides server-only registry mutations, sanitized choices and immutable job routes.
    [Dependencies] Live admin checks at HTTP boundary, AI Store and deployment-owned network/secret settings.
    [Impact] No provider administration operation is exposed as a model tool.
    """
    def __init__(self, store, config):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.INIT]
        [EN rev.2]
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
                'resource_group': row['resource_group'], 'credential': row['credential'], 'profile': profile, 'profile_revision':row['profile_revision'], 'context_tokens': row['context_tokens']}

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
        [EN rev.2]
        [Role] Returns editable basic settings and credential-presence only to the authenticated admin.
        [Dependencies] Fixed column projection and protected HTTP route.
        [Impact] Encryption tokens and original secrets are never returned, even to administrators.
        """
        with self.store.db() as db:
            providers = [dict(r) for r in db.execute('''SELECT p.*,r.base_url,r.adapter,r.resource_group,(r.credential<>'') AS has_key
                FROM ai_providers p JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision ORDER BY p.sort_order,p.name''')]
            for p in providers:
                p['models'] = [dict(r) for r in db.execute('SELECT id,upstream,label,published,present,manual,sort_order,context_tokens,profile,verified_revision,profile_revision FROM ai_provider_models WHERE provider=? ORDER BY sort_order,label', (p['id'],))]
                for model in p['models']:
                    profile = normalize_profile(model['upstream'], p['adapter'], json.loads(model['profile']))
                    model['profile'] = canonical(profile)
                    model.update(public_settings(model['upstream'], p['adapter'], profile))
            groups = [dict(r) for r in db.execute('SELECT * FROM ai_resource_groups ORDER BY name')]
            default = db.execute('SELECT default_model FROM ai_provider_settings WHERE id=1').fetchone()[0]
        return {'providers': providers, 'groups': groups, 'default_model': default, 'encryption_configured': bool(self.config.get('USER_AI_PROVIDER_ENCRYPTION_KEY'))}

    def save(self, data, pid=None):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.SAVE]
        [EN rev.1]
        [Role] Saves a new immutable basic revision under optimistic admin revision checking.
        [Dependencies] Server network allowlist and separate encrypted key storage.
        [Impact] Existing jobs retain their old revision; retired providers cannot be resurrected by stale forms.
        """
        object_only(data, ('name','base_url','adapter','resource_group','new_group','enabled','retired','manual','sort_order','revision','api_key'), ('name','base_url','adapter','enabled','manual','revision'))
        name, base = text(data['name'], 80), text(data['base_url'], 256)
        self.policy.destination(base)
        if data['adapter'] not in ('strata', 'openai') or any(type(data[k]) is not bool for k in ('enabled','manual')) or type(data['revision']) is not int:
            raise AssistantError('연결 종류와 상태를 확인해 주세요.')
        retired = data.get('retired', False)
        order = data.get('sort_order', 0)
        if type(retired) is not bool or type(order) is not int or not 0 <= order <= 10000:
            raise AssistantError('공개 순서/폐기 상태를 확인해 주세요.')
        credential = self.encrypt(data['api_key']) if 'api_key' in data else None
        with self.store.db(True) as db:
            old = db.execute('SELECT * FROM ai_providers WHERE id=?', (pid,)).fetchone() if pid else None
            if (pid and not old) or data['revision'] != (old['revision'] if old else 0):
                raise AssistantError('다른 관리자가 연결을 수정했습니다. 새로고침해 주세요.', 409)
            if old and old['retired']:
                raise AssistantError('폐기한 연결은 다시 활성화할 수 없습니다. 새 연결을 등록해 주세요.', 409)
            group = data.get('resource_group')
            if data.get('new_group'):
                group = uuid.uuid4().hex
                db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?)', (group, text(data['new_group'], 80)))
            if not db.execute('SELECT 1 FROM ai_resource_groups WHERE id=?', (group,)).fetchone():
                raise AssistantError('물리 PC/백엔드 자원 그룹을 선택해 주세요.')
            shared=db.execute('SELECT resource_group FROM ai_provider_revisions WHERE base_url=? AND resource_group<>? LIMIT 1',(base.rstrip('/'),group)).fetchone()
            if shared:
                raise AssistantError('같은 API 주소의 연결은 기존 물리 자원 그룹을 공유해야 합니다.',409)
            if old:
                old_group=db.execute('SELECT resource_group FROM ai_provider_revisions WHERE provider=? AND revision=?',(pid,old['revision'])).fetchone()[0]
                if old_group!=group and db.execute("SELECT 1 FROM jobs WHERE selection_id IN (SELECT id FROM ai_provider_models WHERE provider=?) AND state IN ('queued','running','draining','recovery_required')",(pid,)).fetchone():
                    raise AssistantError('접수/실행 요청을 정리한 뒤 물리 자원 그룹을 변경해 주세요.',409)
            if not old and db.execute('SELECT COUNT(*) FROM ai_providers').fetchone()[0]>=100:
                raise AssistantError('연결 등록 한도(100개)에 도달했습니다.',429)
            pid = pid or uuid.uuid4().hex
            rev = (old['revision'] if old else 0) + 1
            if credential is None:
                credential = db.execute('SELECT credential FROM ai_provider_revisions WHERE provider=? AND revision=?', (pid, old['revision'])).fetchone()[0] if old else ''
            db.execute('INSERT INTO ai_provider_revisions VALUES(?,?,?,?,?,?,?)', (pid, rev, base.rstrip('/'), data['adapter'], group, credential, time.time()))
            if old:
                db.execute('UPDATE ai_providers SET name=?,revision=?,enabled=?,retired=?,manual=?,sort_order=?,last_error=NULL WHERE id=?', (name, rev, data['enabled'], retired, data['manual'], order, pid))
                # Every changed connection needs a fresh capability probe before new requests.
                db.execute('UPDATE ai_provider_models SET verified_revision=NULL WHERE provider=?', (pid,))
            else:
                db.execute('INSERT INTO ai_providers(id,name,revision,enabled,retired,manual,sort_order) VALUES(?,?,?,?,?,?,?)', (pid, name, rev, data['enabled'], retired, data['manual'], order))
        return pid

    def discover(self, pid, force=False):
        """[MINI-COMMENT: ASSISTANT.PROVIDERS.REGISTRY.DISCOVER]
        [EN rev.1]
        [Role] Fetches bounded model IDs outside DB transactions and preserves last known data on failure.
        [Dependencies] Pinned fixed models endpoint and credential decryption; 60-second success cache.
        [Impact] Discovery never loads/unloads a model or treats a listed model as verified/loaded.
        """
        with self.store.db() as db:
            row = db.execute('SELECT p.*,r.* FROM ai_providers p JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision WHERE p.id=?', (pid,)).fetchone()
            if row is None or row['retired']:
                raise AssistantError('연결을 찾을 수 없습니다.', 404)
            row = dict(row)
        if not force and row['last_checked'] and time.time()-row['last_checked'] < 60:
            return
        try:
            with model_request(self.policy, row['base_url'], '/models', self.secret(row['credential']), timeout=15) as response:
                response.raise_for_status()
                result = response.json()
            items = result.get('data') if isinstance(result, dict) else None
            if not isinstance(items, list) or len(items) > 500:
                raise ValueError('invalid model list')
            ids = []
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError('invalid model')
                mid = text(item.get('id'), 200)
                if '/' in mid or '\\' in mid:
                    # A path may be a valid upstream ID; never publish that path as a user-facing label.
                    label = mid.replace('\\', '/').rsplit('/', 1)[-1]
                else:
                    label = mid
                if item.get('type') in ('embedding','embeddings','tts','audio','image') or any(x in mid.lower() for x in ('embedding', 'embed-', 'tts-')):
                    continue
                ids.append((mid, label))
            with self.store.db(True) as db:
                if db.execute('SELECT revision FROM ai_providers WHERE id=?', (pid,)).fetchone()[0] != row['revision']:
                    raise AssistantError('조회 중 연결 설정이 변경되었습니다. 다시 조회해 주세요.', 409)
                db.execute('UPDATE ai_provider_models SET present=manual WHERE provider=?', (pid,))
                existing={r[0] for r in db.execute('SELECT upstream FROM ai_provider_models WHERE provider=?',(pid,))}
                if len(existing|{mid for mid,_ in ids})>500:
                    raise AssistantError('모델 보관 한도(연결별 500개)를 초과했습니다.',429)
                for mid, label in ids:
                    db.execute('''INSERT INTO ai_provider_models(id,provider,upstream,label,present,checked) VALUES(?,?,?,?,1,?)
                        ON CONFLICT(provider,upstream) DO UPDATE SET present=1,checked=excluded.checked''', (uuid.uuid4().hex, pid, mid, label, time.time()))
                db.execute('UPDATE ai_providers SET last_checked=?,last_error=NULL WHERE id=?', (time.time(), pid))
        except Exception as error:
            with self.store.db(True) as db:
                db.execute('UPDATE ai_providers SET last_checked=?,last_error=? WHERE id=? AND revision=?', (time.time(), '모델 목록 확인 실패 (' + type(error).__name__ + ')', pid, row['revision']))
            raise AssistantError('모델 목록을 확인하지 못했습니다. 이전 목록은 보관되며 자동 대체하지 않습니다.', 503) from None

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
