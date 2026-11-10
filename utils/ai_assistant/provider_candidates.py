"""Candidate inventory and probe evidence live outside the published model catalogue."""
import json
import time
import uuid

from .policy import AssistantError, DEFAULT_LEVEL, canonical
from .reasoning import known_levels, normalize_profile


SCHEMA = '''
CREATE TABLE IF NOT EXISTS ai_provider_trust(
    provider TEXT NOT NULL, revision INTEGER NOT NULL, origin TEXT NOT NULL, addresses TEXT,
    ca_pem TEXT NOT NULL DEFAULT '', fingerprint TEXT, expires TEXT, revoked REAL,
    PRIMARY KEY(provider,revision), FOREIGN KEY(provider,revision) REFERENCES ai_provider_revisions(provider,revision));
CREATE TABLE IF NOT EXISTS ai_provider_candidates(
    provider TEXT PRIMARY KEY REFERENCES ai_providers(id), revision INTEGER NOT NULL, parent INTEGER NOT NULL,
    name TEXT NOT NULL, enabled INTEGER NOT NULL, manual INTEGER NOT NULL, sort_order INTEGER NOT NULL,
    generation INTEGER NOT NULL DEFAULT 0, discovered INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL,
    FOREIGN KEY(provider,revision) REFERENCES ai_provider_trust(provider,revision));
CREATE TABLE IF NOT EXISTS ai_candidate_models(
    provider TEXT NOT NULL REFERENCES ai_provider_candidates(provider) ON DELETE CASCADE,
    id TEXT NOT NULL, upstream TEXT NOT NULL, label TEXT NOT NULL,
    proof TEXT, tested_profile INTEGER, tested_context INTEGER, PRIMARY KEY(provider,id), UNIQUE(provider,upstream));
CREATE TABLE IF NOT EXISTS ai_provider_trust_events(
    id INTEGER PRIMARY KEY, created REAL NOT NULL, actor INTEGER NOT NULL, provider TEXT NOT NULL,
    revision INTEGER NOT NULL, origin TEXT NOT NULL, fingerprint TEXT, result TEXT NOT NULL);
'''


def migrate_trust(db):
    installed = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_provider_trust'").fetchone()
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)
    if not installed:
        # Only pre-upgrade rows may bootstrap pins from the prior deployment policy.
        db.execute('''INSERT INTO ai_provider_trust(provider,revision,origin)
                      SELECT provider,revision,base_url FROM ai_provider_revisions''')


def audit(db, pid, revision, actor, result):
    db.execute('''INSERT INTO ai_provider_trust_events(created,actor,provider,revision,origin,fingerprint,result)
        SELECT ?,?,provider,revision,origin,fingerprint,? FROM ai_provider_trust
        WHERE provider=? AND revision=?''', (time.time(), actor, result, pid, revision))


def pending(db, pid, revision, generation=None):
    row = db.execute('''SELECT c.*,r.base_url,r.adapter,r.resource_group,r.credential,t.fingerprint,t.expires
        FROM ai_provider_candidates c JOIN ai_provider_revisions r USING(provider,revision)
        JOIN ai_provider_trust t USING(provider,revision) JOIN ai_providers p ON p.id=c.provider
        WHERE c.provider=? AND c.revision=? AND p.revision=c.parent AND p.retired=0 AND t.revoked IS NULL''',
                     (pid, revision)).fetchone()
    if row is None or generation is not None and row['generation'] != generation:
        raise AssistantError('후보 버전 또는 조회 결과가 변경되었습니다. 새로고침해 주세요.', 409)
    return row


def group_available(db, pid, group):
    old = db.execute('''SELECT r.resource_group FROM ai_providers p JOIN ai_provider_revisions r
        ON r.provider=p.id AND r.revision=p.revision WHERE p.id=?''', (pid,)).fetchone()
    if not old or old[0] == group:
        return
    if (db.execute("""SELECT 1 FROM jobs WHERE json_extract(route_snapshot,'$.provider_id')=?
                AND resource_group<>? AND state IN ('queued','running','draining','recovery_required') LIMIT 1""",
                   (pid, group)).fetchone()
            or db.execute("""SELECT 1 FROM ai_execution_guards WHERE resource_group=?
                AND state IN ('running','draining','recovery_required') LIMIT 1""", (old[0],)).fetchone()):
        raise AssistantError('접수·실행 요청을 정리한 뒤 물리 자원 그룹을 변경해 주세요.', 409)


def record_inventory(db, candidate, items):
    pid = candidate['provider']
    existing = {r['upstream']:r['id'] for r in db.execute(
        'SELECT upstream,id FROM ai_provider_models WHERE provider=?', (pid,))}
    if len(set(existing) | {item[0] for item in items}) > 500:
        raise AssistantError('모델 보관 한도(연결별 500개)를 초과했습니다.', 422)
    existing.update({r['upstream']:r['id'] for r in db.execute(
        'SELECT upstream,id FROM ai_candidate_models WHERE provider=?', (pid,))})
    db.execute('DELETE FROM ai_candidate_models WHERE provider=?', (pid,))
    for upstream, label in dict(items).items():
        db.execute('INSERT INTO ai_candidate_models(provider,id,upstream,label) VALUES(?,?,?,?)',
                   (pid, existing.get(upstream) or uuid.uuid4().hex, upstream, label))
    db.execute("UPDATE ai_provider_candidates SET discovered=1,result='모델 목록 조회 성공' WHERE provider=?", (pid,))


def candidate_profile(upstream, adapter, stored):
    """Project the saved policy onto the candidate adapter's supported levels for its own trial."""
    profile = json.loads(stored or '{}')
    ceiling = known_levels(upstream, adapter)
    if ceiling is not None and 'enabled_levels' in profile:
        levels = [level for level in profile['enabled_levels'] if level in ceiling]
        profile['enabled_levels'] = levels
        if profile.get('default_level') not in levels:
            profile['default_level'] = levels[0] if levels else DEFAULT_LEVEL
    return normalize_profile(upstream, adapter, profile)


def probe_route(db, pid, revision, mid, generation=None, context_tokens=None):
    cand = pending(db, pid, revision, generation)
    model = db.execute('''SELECT c.id,c.upstream,c.label,m.context_tokens,m.profile,m.verified_revision,
            COALESCE(m.profile_revision,0) AS profile_revision FROM ai_candidate_models c
            LEFT JOIN ai_provider_models m ON m.provider=c.provider AND m.id=c.id WHERE c.provider=? AND c.id=?''',
                       (pid, mid)).fetchone()
    if not cand['discovered'] or model is None:
        raise AssistantError('후보 주소의 모델 목록을 먼저 조회해 주세요.', 409)
    if context_tokens is None:
        context_tokens = model['context_tokens'] or 4096
    if (type(context_tokens) is not int or not 2048 <= context_tokens <= 1048576
            or model['context_tokens'] is not None and model['context_tokens'] != context_tokens):
        raise AssistantError('신규 모델은 확인한 컨텍스트 한도를 입력하고 기존 모델은 저장된 한도를 사용해 주세요.')
    profile = candidate_profile(model['upstream'], cand['adapter'], model['profile'])
    return {'provider_id':pid, 'provider_name':cand['name'], 'revision':revision, 'candidate_generation':cand['generation'],
            'base_url':cand['base_url'], 'adapter':cand['adapter'], 'resource_group':cand['resource_group'],
            'selection_id':mid, 'model':model['upstream'], 'model_label':model['label'],
            'profile':profile, 'profile_revision':model['profile_revision'], 'context_tokens':context_tokens}


def check_probe(db, route):
    current = probe_route(db, route['provider_id'], route['revision'], route['selection_id'],
                          route['candidate_generation'], route['context_tokens'])
    if current['profile_revision'] != route['profile_revision']:
        raise AssistantError('시험 중 모델 설정이 변경되었습니다. 현재 설정에서 다시 시험해 주세요.', 409)


def record_proof(db, route, profile, actor):
    """The caller owns the same writer transaction as the final job receipt and guard release."""
    check_probe(db, route)
    pid, revision = route['provider_id'], route['revision']
    cand = pending(db, pid, revision, route['candidate_generation'])
    db.execute('UPDATE ai_candidate_models SET proof=?,tested_profile=?,tested_context=? WHERE provider=? AND id=?',
               (canonical(profile), route['profile_revision'], route['context_tokens'], pid, route['selection_id']))
    audit(db, pid, revision, actor, 'worker_probe_passed')
    # Every published, working model keeps its prior contract through cutover. Missing models
    # require an explicit admin unpublish on the active revision, or a repaired candidate.
    models = db.execute('''SELECT m.id,m.profile,m.profile_revision,c.proof,c.tested_profile
        FROM ai_provider_models m LEFT JOIN ai_candidate_models c ON c.provider=m.provider AND c.id=m.id
        WHERE m.provider=? AND m.published=1 AND m.present=1 AND m.verified_revision=?''',
                        (pid, cand['parent'])).fetchall()
    for row in models:
        old, proof = json.loads(row['profile']), json.loads(row['proof'] or '{}')
        if (row['tested_profile'] != row['profile_revision'] or not proof.get('chat')
                or old.get('tools') and not proof.get('tools')
                or not set(old.get('levels', [])) <= set(proof.get('verified_levels', []))):
            db.execute("UPDATE ai_provider_candidates SET result='기존 공개 모델의 기능 시험 대기' WHERE provider=?", (pid,))
            return
    group_available(db, pid, cand['resource_group'])
    now = time.time()
    db.execute('UPDATE ai_provider_models SET present=manual WHERE provider=?', (pid,))
    for item in db.execute('SELECT * FROM ai_candidate_models WHERE provider=?', (pid,)).fetchall():
        db.execute('''INSERT INTO ai_provider_models(id,provider,upstream,label,published,present,context_tokens,checked)
            VALUES(?,?,?,?,0,1,?,?) ON CONFLICT(provider,upstream) DO UPDATE SET present=1,checked=excluded.checked''',
                   (item['id'], pid, item['upstream'], item['label'], item['tested_context'] or 4096, now))
        if item['proof']:
            db.execute('''UPDATE ai_provider_models SET profile=?,verified_revision=?,profile_revision=profile_revision+1
                WHERE provider=? AND id=? AND (profile_revision=? OR (?=0 AND profile_revision=1))''',
                       (item['proof'], revision, pid, item['id'], item['tested_profile'], item['tested_profile']))
    previous = db.execute('SELECT adapter FROM ai_provider_revisions WHERE provider=? AND revision=?',
                          (pid,cand['parent'])).fetchone()
    if previous and previous[0] != cand['adapter']:
        # Retained, untested models (including absent inventory) must remain readable in the new editor.
        for model in db.execute('SELECT id,upstream,profile FROM ai_provider_models WHERE provider=? AND verified_revision IS NOT ?',
                                (pid,revision)).fetchall():
            proposed = candidate_profile(model['upstream'],cand['adapter'],model['profile'])
            if proposed != json.loads(model['profile']):
                db.execute('UPDATE ai_provider_models SET profile=?,profile_revision=profile_revision+1 WHERE id=?',
                           (canonical(proposed),model['id']))
    db.execute('''UPDATE ai_providers SET revision=?,name=?,enabled=?,manual=?,sort_order=?,last_checked=?,last_error=NULL
        WHERE id=?''', (revision,cand['name'],cand['enabled'],cand['manual'],cand['sort_order'],now,pid))
    db.execute('DELETE FROM ai_provider_candidates WHERE provider=?', (pid,))
    audit(db, pid, revision, actor, 'activated')
