"""Read-only administrator projections of stored assistant records and verified business receipts."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import re
import sqlite3
import time

from utils.roadmap_equipment import CSV_FIELDS
from .audit import SENSITIVE_KEYS, execution_reference
from .lifecycle import TITLE_LIMIT
from .policy import AssistantError, ERROR_REASONS, MAX_CONTENT, identity, opaque


MENU = 'equipment_ai_logs'
PAGE_URL = '/admin/ai/logs'
JOB_STATES = {
    'queued': '대기 중', 'running': '처리 중', 'draining': '중단 처리 중',
    'recovery_required': '복구 필요', 'waiting_confirmation': '확인 대기',
    'done': '성공', 'failed': '실패', 'cancelled': '취소',
}
PROPOSAL_STATES = {
    'pending': '확인 대기', 'applied': '적용됨', 'expired': '만료됨',
    'cancelled': '취소됨', 'superseded': '새 제안으로 대체됨',
}
OPERATIONS = {
    'equipment_create': '장비 등록', 'equipment_update': '장비 수정', 'equipment_status': '장비 상태 변경',
    'catalog_request': '카탈로그 신청', 'option_request': '옵션 신청', 'preferences': '개인 설정 변경',
    'csv_export': 'CSV 내보내기',
}
BODY_PAGE = 2000
SEOUL = timezone(timedelta(hours=9))
PROTECTED = '[보호된 내용]'
OVER_LIMIT = '[표시 한도를 초과한 내용]'
CSV_HEADER = ','.join(CSV_FIELDS)
VISIBLE = '(c.is_deleted=0 OR (c.is_deleted=1 AND c.purge_after>?))'
CONVERSATION_FIELDS = f'c.id,c.owner,substr(c.title,1,{TITLE_LIMIT + 1}) AS title,c.created,c.updated,c.is_deleted'
JOB_FIELDS = f'''j.id,j.owner,j.conversation,substr(c.title,1,{TITLE_LIMIT + 1}) AS title,
    j.created,j.updated,j.state,j.purpose,substr(j.error,1,513) AS error,substr(j.error_code,1,80) AS error_code'''
JOB_SOURCE = ' FROM jobs j JOIN conversations c ON c.id=j.conversation AND c.owner=j.owner WHERE ' + VISIBLE

# Free text can itself quote a credential or a private model field. Check the complete bounded
# field before making any preview or page, so a page boundary cannot reveal part of the value.
_PRIVATE_KEYS = SENSITIVE_KEYS | {
    'secret', 'secret_key', 'client_secret', 'private_key', 'proposal_signature', 'signing_key', 'binding', 'lease_hash',
    'csrf', 'token', 'x_csrf_token', 'x_api_key', 'reasoning', 'reasoning_content', 'raw_csv',
    '비밀번호', '비밀키', '인증 토큰', '인증 서명', '제안 서명',
}
_KEY_PATTERN = '|'.join(re.escape(key).replace('_', '[-_ ]?') for key in sorted(_PRIVATE_KEYS))
_PRIVATE_TEXT = re.compile(
    rf'''(?:{_KEY_PATTERN})(?:\\?["'])?\s*[:=]|bearer\s+[a-z0-9._+/=-]+'''
    r'|Basic\s+(?-i:(?=[A-Za-z0-9+/]*[A-Z0-9+/])[A-Za-z0-9+/]{8,}={0,2})'
    r'|-----BEGIN [A-Z ]*PRIVATE KEY|</?(?:think|thinking|analysis|reasoning)\b'
    r'''|["']signature(?:\\?["'])\s*:'''
    r'''|(?:\bsignature|서명)(?:\\?["'])?\s*[:=]\s*["']?(?=[A-Za-z0-9_+/=.-]{12,})(?=[A-Za-z0-9_+/=.-]*[0-9_+/=.-])[A-Za-z0-9_+/=.-]+'''
    r'|(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)'
    r'|(?<![a-f0-9])(?:[a-f0-9]{32}|[a-f0-9]{48}|[a-f0-9]{64})(?![a-f0-9])', re.I)


def display_text(value, maximum, secrets):
    if not value:
        return ''
    if not isinstance(value, str) or len(value) > maximum:
        return OVER_LIMIT
    if _PRIVATE_TEXT.search(value) or CSV_HEADER in value or any(secret in value for secret in secrets):
        return PROTECTED
    return value


def log_time(value):
    """AI rows use Unix time. AI_EXECUTE receipts use equipment.utc_now() (UTC ISO 8601)."""
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromtimestamp(value, timezone.utc)
        return dt.astimezone(SEOUL).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OverflowError, OSError):
        return '시각 미상'


def register_admin_menu(db, code, name, url, description, order, now):
    """Seed a dedicated admin grant and adopt only a matching legacy top-level menu."""
    row = db.execute('SELECT Url,ParentMenuCode FROM menus WHERE MenuCode=?', (code,)).fetchone()
    if row and (row['Url'] != url or row['ParentMenuCode'] not in (None, 'admin_center')):
        raise ValueError('assistant admin menu collision: ' + code)
    if code == MENU and db.execute('SELECT 1 FROM menus WHERE Url=? AND MenuCode<>?', (url, code)).fetchone():
        raise ValueError('assistant admin menu collision: ' + code)
    db.execute('''INSERT OR IGNORE INTO menus(MenuCode,MenuName,Url,Description,ParentMenuCode,SortOrder,CreatedAt,UpdatedAt)
                  VALUES(?,?,?,?,'admin_center',?,?,?)''', (code, name, url, description, order, now, now))
    db.execute("""UPDATE menus SET ParentMenuCode='admin_center',UpdatedAt=?
                  WHERE MenuCode=? AND Url=? AND ParentMenuCode IS NULL""", (now, code, url))
    db.execute("""INSERT OR IGNORE INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt)
                  VALUES('admin',?,1,?)""", (code, now))


def read_records(path, business, uid, token, binding, args, secrets=()):
    """Recheck the actual account and dedicated grant before opening the independent AI reader."""
    business.execute('PRAGMA query_only=ON')
    business.execute('BEGIN')
    user = business.execute('''SELECT u.Role,u.IsDeleted,u.IsDeactivated,p.IsAllowed
        FROM users u LEFT JOIN role_menu_permissions p ON p.Role=u.Role AND p.MenuCode=?
        WHERE u.UserId=? AND u.SessionToken=?''', (MENU, identity(uid), token)).fetchone()
    if not token or not user or user['IsDeleted'] != 'N':
        raise AssistantError('다시 로그인해 주세요.', 401)
    if user['IsDeactivated'] != 'N' or user['Role'] != 'admin' or user['IsAllowed'] != 1:
        raise AssistantError('AI 도우미 기록 조회 권한이 필요합니다.', 403)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as ai:
        ai.row_factory = sqlite3.Row
        ai.execute('BEGIN')
        if ai.execute('SELECT 1 FROM revocations WHERE binding=?', (binding,)).fetchone():
            raise AssistantError('다시 로그인해 주세요.', 401)
        return _records(ai, business, args, secrets, time.time())


def number(args, key, default=None, maximum=2**63 - 1):
    if key not in args:
        return default
    raw = args[key]
    if not re.fullmatch(r'[1-9][0-9]{0,18}', raw) or int(raw) > maximum:
        raise AssistantError('조회 범위와 페이지 번호를 확인해 주세요.')
    return int(raw)


def page_bounds(args):
    limit = number(args, 'limit', 20, 50)
    before, after = number(args, 'before'), number(args, 'after')
    if before and after:
        raise AssistantError('한 방향의 목록 위치만 선택해 주세요.')
    return limit, before, after


def record_page(db, fields, source, params, position, bounds):
    """Seek in insertion order. Read one extra row to decide whether another page exists."""
    limit, before, after = bounds
    if before or after:
        source += f' AND {position} ' + ('> ?' if after else '< ?')
        params = [*params, after or before]
    order = 'ASC' if after else 'DESC'
    rows = db.execute(f'SELECT {position} AS position,{fields} {source} ORDER BY {position} {order} LIMIT ?',
                      (*params, limit + 1)).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    if after:
        rows.reverse()
    return rows, {
        'newer': rows[0]['position'] if rows and (before or after and more) else None,
        'older': rows[-1]['position'] if rows and (after or more) else None,
    }


def conversation_item(row, secrets):
    return dict(id=row['id'], owner=row['owner'], title=display_text(row['title'], TITLE_LIMIT, secrets),
                created=row['created'], updated=row['updated'], is_deleted=bool(row['is_deleted']))


def job_item(row, secrets):
    code = row['error_code'] if row['error_code'] in ERROR_REASONS else None
    reason = display_text(row['error'], 512, secrets)
    if code and reason in ('', PROTECTED, OVER_LIMIT):
        reason = ERROR_REASONS[code]
    return dict(id=row['id'], owner=row['owner'], conversation=row['conversation'],
                title=display_text(row['title'], TITLE_LIMIT, secrets), created=row['created'], updated=row['updated'],
                state=row['state'] if row['state'] in JOB_STATES else 'unknown',
                purpose=row['purpose'] if row['purpose'] in ('chat', 'probe') else 'unknown',
                error_code=code, reason=reason or None)


def message_page(ai, job, role, page, secrets):
    # Assistant snapshots also contain unfinished streamed text. Only a completed chat has a final answer.
    content = ''
    if job['purpose'] == 'chat' and (role == 'user' or job['state'] in ('done', 'waiting_confirmation')):
        row = ai.execute('''SELECT substr(content,1,?) FROM messages
            WHERE job=? AND conversation=? AND role=? ORDER BY id DESC LIMIT 1''',
            (MAX_CONTENT + 1, job['id'], job['conversation'], role)).fetchone()
        if row:
            content = display_text(row[0], MAX_CONTENT, secrets)
    return text_page(content, page)


def text_page(content, page):
    pages = max(1, (len(content) + BODY_PAGE - 1) // BODY_PAGE)
    if page > pages:
        raise AssistantError('해당 본문 페이지가 없습니다.', 404)
    return dict(text=content[(page - 1) * BODY_PAGE:page * BODY_PAGE], page=page, pages=pages)


def verified_audits(business, owner, proposals):
    references = []
    for proposal in proposals:
        if (not isinstance(proposal['id'], str) or not re.fullmatch('[0-9a-f]{32}', proposal['id'])
                or not all(isinstance(proposal[key], str) for key in ('operation', 'payload', 'before_json'))):
            continue
        target, fingerprint = execution_reference(proposal)
        references.append((target, proposal['id'], fingerprint))
    if not references:
        return {}
    values = ','.join('(?,?,?)' for _ in references)
    # TargetId alone is only 60 bits. Verify the writer's full receipt, also when the AI-side
    # state update failed after the business commit. Malformed/ambiguous records prove nothing.
    rows = business.execute(f'''WITH expected(target,pid,fingerprint) AS (VALUES {values})
        SELECT e.pid,a.AuditId,a.CreatedAt FROM audit_logs a JOIN expected e ON a.TargetId=e.target
        WHERE a.ActorId=? AND a.Action='AI_EXECUTE' AND a.TargetTable='ai_operations'
        AND CASE WHEN length(a.NewValue)<=131072 AND json_valid(a.NewValue) THEN
            json_extract(a.NewValue,'$.proposal_id')=e.pid AND json_extract(a.NewValue,'$.hash')=e.fingerprint
            AND json_type(a.NewValue,'$.result')='object' END
        GROUP BY e.pid HAVING count(*)=1''', (*[value for item in references for value in item], owner))
    return {r['pid']: dict(id=r['AuditId'], action='AI_EXECUTE', created=r['CreatedAt']) for r in rows}


def _records(ai, business, args, secrets, now):
    view = args.get('view', 'conversations')
    filters = {'conversations': {'owner'}, 'jobs': {'owner', 'conversation', 'state'},
               'job': {'id', 'question_page', 'answer_page'}, 'receipts': {'owner'},
               'questions': {'conversation', 'question_page'}}
    if (view not in filters or set(args) - filters[view] - {'view', 'limit', 'before', 'after'}
            or any(len(args.getlist(key)) != 1 for key in args)):
        raise AssistantError('조회 항목을 확인해 주세요.')
    owner = number(args, 'owner') if args.get('owner') else None
    bounds = page_bounds(args)
    owner_filter = ' AND c.owner=?' if owner else ''
    params = [now, owner] if owner else [now]
    result = {'view': view}
    if 'conversation' in args or view == 'questions':
        cid = opaque(args.get('conversation'))
        conversation = ai.execute(f'SELECT {CONVERSATION_FIELDS} FROM conversations c WHERE {VISIBLE} AND c.id=?',
                                  (now, cid)).fetchone()
        if not conversation:
            raise AssistantError('대화를 찾을 수 없습니다.', 404)
        result['conversation'] = conversation_item(conversation, secrets)
        # Some older user questions have no job. Standalone assistant rows include confirmation receipts.
        unlinked = """FROM messages m WHERE m.conversation=? AND m.job IS NULL AND m.role='user'
            AND (NOT EXISTS(SELECT 1 FROM jobs j WHERE j.conversation=m.conversation)
                 OR EXISTS(SELECT 1 FROM jobs j WHERE j.conversation=m.conversation AND j.owner=? AND j.purpose='chat'))"""
        unlinked_params = [cid, conversation['owner']]
        if view == 'questions':
            page = number(args, 'question_page', 1)
            rows, paging = record_page(ai, f'm.created,substr(m.content,1,{MAX_CONTENT + 1}) AS content',
                                       unlinked, unlinked_params, 'm.id', (1, bounds[1], bounds[2]))
            items = [dict(created=r['created'], question=text_page(display_text(r['content'], MAX_CONTENT, secrets), page))
                     for r in rows]
            return dict(result, paging=paging, items=items)
        result['has_unlinked_questions'] = ai.execute('SELECT 1 ' + unlinked + ' LIMIT 1', unlinked_params).fetchone() is not None
    if view == 'conversations':
        rows, paging = record_page(ai, CONVERSATION_FIELDS, 'FROM conversations c WHERE ' + VISIBLE + owner_filter,
                                   params, 'c.rowid', bounds)
        items = [conversation_item(row, secrets) for row in rows]
    elif view == 'jobs':
        source = JOB_SOURCE + owner_filter
        if 'conversation' in args:
            source += ' AND j.conversation=?'
            params.append(args['conversation'])
        if args.get('state'):
            if args['state'] not in JOB_STATES:
                raise AssistantError('작업 상태를 확인해 주세요.')
            source += ' AND j.state=?'
            params.append(args['state'])
        rows, paging = record_page(ai, JOB_FIELDS, source, params, 'j.rowid', bounds)
        items = [job_item(row, secrets) for row in rows]
    elif view == 'job':
        jid = opaque(args.get('id'))
        row = ai.execute(f'SELECT {JOB_FIELDS} {JOB_SOURCE} AND j.id=?', (now, jid)).fetchone()
        if not row:
            raise AssistantError('작업을 찾을 수 없습니다.', 404)
        job = result['job'] = job_item(row, secrets)
        for role, field in (('user', 'question'), ('assistant', 'answer')):
            result[field] = message_page(ai, job, role, number(args, field + '_page', 1), secrets)
        rows, paging = record_page(ai, '''p.id,p.operation,p.state,p.created,p.expires,
            CASE WHEN length(p.payload)<=131072 THEN p.payload END AS payload,
            CASE WHEN length(p.before_json)<=131072 THEN p.before_json END AS before_json''',
            'FROM proposals p WHERE p.job=? AND p.owner=?', [jid, job['owner']], 'p.rowid', bounds)
        audits = verified_audits(business, job['owner'], rows)
        items = [dict(id=p['id'], operation=p['operation'] if p['operation'] in OPERATIONS else 'unknown',
                      state=p['state'] if p['state'] in PROPOSAL_STATES else 'unknown', created=p['created'],
                      expires=p['expires'], past_due=p['state'] == 'pending' and p['expires'] <= now,
                      audit=audits.get(p['id'])) for p in rows]
    else:
        # The exporter creates this ledger on first use. A historical database can lack blob_id or the entire table.
        exists = ai.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_audit_artifacts'").fetchone()
        if not exists:
            return dict(result, items=[], paging={'newer': None, 'older': None})
        source = 'FROM ai_audit_artifacts a WHERE 1=1' + (' AND a.owner=?' if owner else '')
        fields = 'a.id,a.owner,a.scope,a.row_count,a.bytes,substr(a.sha256,1,65) AS sha256,a.created'
        rows, paging = record_page(ai, fields, source, [owner] if owner else [], 'a.rowid', bounds)
        items = [dict(id=r['id'], owner=r['owner'], scope=r['scope'] if r['scope'] in ('my', 'public') else 'unknown',
                      row_count=r['row_count'], bytes=r['bytes'], created=r['created'],
                      sha256=r['sha256'] if re.fullmatch('[0-9a-f]{64}', r['sha256']) else None) for r in rows]
    return dict(result, items=items, paging=paging)
