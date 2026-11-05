"""[MINI-COMMENT: ASSISTANT.STATUS]
[EN rev.1]
[Role] Reports only app-local queue blocking and fresh evidence about one selected connection.
[Dependencies] Existing owner-bound jobs, execution guards and provider observations; no network probe.
[Impact] Never controls another service, exposes another actor or treats slow generation as an outage.
"""
import json
import time

from .policy import AssistantError, opaque


def read_status(store, actor, selection_id=None, job_id=None, now=None):
    """[MINI-COMMENT: ASSISTANT.STATUS.READ]
    [EN rev.1]
    [Role] Resolves an accepted own job before a next-turn model and returns safe, expiring status.
    [Dependencies] Current HTTP actor, private Store and the same group fairness rule as claim().
    [Impact] An unknown/stale observation stays neutral; a current local predecessor alone is yellow.
    """
    now = time.time() if now is None else now
    scope = 'job' if job_id else 'selection'

    def result(state, message, checked=None, lifetime=60):
        """[Role] Restricts the public result to labels and timestamps, never route or actor metadata."""
        checked = now if checked is None else checked
        return dict(state=state, scope=scope, checked_at=checked,
                    expires_at=min(now + lifetime, checked + lifetime), message=message)

    with store.db() as db:
        job = store.job(opaque(job_id), db, actor['UserId'], actor['account_key']) if job_id else None
        if job and job['purpose'] != 'chat':
            raise AssistantError('이 대화 요청의 상태를 확인할 수 없습니다.', 404)
        mid = job['selection_id'] if job else selection_id
        if not mid:
            return result('checking', 'AI 모델을 선택해 주세요.', lifetime=5)
        row = db.execute('''SELECT m.id,m.provider,m.published,m.present,m.checked,m.verified_revision,m.profile,
            p.revision,p.enabled,p.retired,p.last_checked,p.last_error,r.resource_group
            FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider
            JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision WHERE m.id=?''', (opaque(mid),)).fetchone()
        if row is None or (not job and not row['published']):
            raise AssistantError('선택한 AI 모델을 확인해 주세요.', 404)
        frozen = json.loads(job['route_snapshot']) if job else None
        group = frozen.get('resource_group', row['resource_group']) if frozen else row['resource_group']
        revision = frozen.get('revision', row['revision']) if frozen else row['revision']
        provider = frozen.get('provider_id', row['provider']) if frozen else row['provider']
        if job and job['state'] == 'queued':
            guard = db.execute("SELECT job FROM ai_execution_guards WHERE resource_group=? AND state IN ('running','draining','recovery_required') AND job<>? LIMIT 1", (group, job['id'])).fetchone()
            first = db.execute("SELECT id,owner FROM jobs WHERE state='queued' AND resource_group=? ORDER BY queue_order LIMIT 1", (group,)).fetchone()
            previous = db.execute('SELECT last_owner FROM ai_resource_groups WHERE id=?', (group,)).fetchone()
            if first and previous and previous[0] == first['owner']:
                other = db.execute("SELECT id,owner FROM jobs WHERE state='queued' AND resource_group=? AND owner<>? ORDER BY queue_order LIMIT 1", (group, first['owner'])).fetchone()
                first = other or first
            if guard or (first and first['id'] != job['id']):
                return result('waiting_other', '장비관리의 다른 사용자 또는 대화 요청이 먼저 처리되고 있습니다.', lifetime=6)

        observations = []
        if row['revision'] == revision:
            if row['last_checked']:
                error = row['last_error'] or ''
                if not error:
                    observations.append((row['last_checked'], 'ready', '선택한 AI 연결의 응답을 확인했습니다.'))
                elif any(name in error for name in ('ConnectionError', 'ConnectTimeout', 'ReadTimeout', 'TimeoutError')):
                    observations.append((row['last_checked'], 'unavailable', '선택한 AI 연결에서 응답을 받지 못했습니다.'))
                else:
                    observations.append((row['last_checked'], 'checking', '선택한 AI 연결 설정을 다시 확인해야 합니다.'))
            if row['checked'] and row['verified_revision'] == revision and json.loads(row['profile']).get('chat'):
                observations.append((row['checked'], 'ready', '선택한 AI 모델의 응답을 확인했습니다.'))
        recent = db.execute('''SELECT j.state,j.error_code,j.updated,j.route_snapshot,
            EXISTS(SELECT 1 FROM messages m WHERE m.job=j.id AND m.role='assistant' AND (m.content<>'' OR m.reasoning<>'')) AS has_output
            FROM jobs j JOIN ai_provider_models m ON m.id=j.selection_id
            WHERE m.provider=? AND j.updated>? ORDER BY j.updated DESC LIMIT 12''', (provider, now - 60)).fetchall()
        for entry in recent:
            route = json.loads(entry['route_snapshot'])
            if route.get('revision') != revision or route.get('provider_id') != provider:
                continue
            if entry['error_code'] in ('CONNECTION_TIMEOUT', 'CONNECTION_FAILED'):
                observations.append((entry['updated'], 'unavailable', '선택한 AI 연결에서 응답을 받지 못했습니다.'))
            elif entry['state'] == 'done' or (entry['state'] == 'running' and entry['has_output']):
                observations.append((entry['updated'], 'ready', '선택한 AI 연결에서 응답을 받고 있습니다.' if entry['state'] == 'running' else '선택한 AI 연결의 응답을 확인했습니다.'))
        if not job and (not row['enabled'] or row['retired'] or not row['present']):
            return result('checking', '이 모델의 연결 또는 공개 설정을 확인해 주세요.', lifetime=6)
        if not observations:
            return result('checking', '최근 연결 상태를 확인 중입니다. 정상 생성이 길어져도 장애로 판단하지 않습니다.', lifetime=6)
        checked, state, message = max(observations, key=lambda item: item[0])
        if checked > now + 2 or now - checked >= 60:
            return result('stale', '최근 연결 확인 정보가 오래되었습니다.', lifetime=6)
        return result(state, message, checked)
