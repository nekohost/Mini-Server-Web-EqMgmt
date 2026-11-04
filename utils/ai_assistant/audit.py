"""[MINI-COMMENT: ASSISTANT.AUDIT]
[EN rev.2]
[Role] Preserves AI audit content while replacing reusable credentials with correlated fingerprints.
[Dependencies] Python JSON/regex and the server HMAC helper; no database, request or model access.
[Impact] AI events remain auditable; formatter failure never falls back to a raw credential body.
"""
import json
import re
import hashlib
import os
from pathlib import Path
import time
import uuid

from .policy import canonical, mac

SENSITIVE_KEYS = frozenset({
    'authorization', 'cookie', 'set-cookie', 'password', 'session_token', 'csrf_token',
    'access_token', 'refresh_token', 'api_key', 'worker_token', 'strata_key', 'lease', 'token', 'credential',
})


def audit_body(raw, secret, known_secrets=()):
    """[Role] Keeps business content verbatim in JSON and fingerprints only credential fields/known secrets.
    [Dependencies] A stable server HMAC key, bounded HTTP bodies and explicitly known current credentials.
    [Impact] A fingerprint correlates events but cannot authorize a browser confirmation or worker report.
    """
    if raw is None:
        return None
    raw = raw if isinstance(raw, str) else str(raw)

    def protected(value):
        """[Role] Produces a domain-separated, non-reusable credential fingerprint.
        [Dependencies] The server secret and canonical value; neither is returned in plaintext.
        [Impact] Equal credentials correlate within this server without expanding log-reader permissions.
        """
        return '[보호된 인증값:' + mac(secret, 'assistant-audit', value)[:24] + ']'

    replacements = {value: protected(value) for value in known_secrets if isinstance(value, str) and len(value) >= 16}

    def sanitize(value):
        """[Role] Traverses parsed protocol objects without interpreting user content strings as commands.
        [Dependencies] Fixed credential field names and current server-known secrets.
        [Impact] Ordinary prompts, reasoning, proposals and outcomes are retained for audit.
        """
        if isinstance(value, dict):
            return {key: protected(item) if key.lower().replace('-', '_') in {k.replace('-', '_') for k in SENSITIVE_KEYS}
                    and item not in (None, '') else sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, str):
            for original, replacement in replacements.items():
                value = value.replace(original, replacement)
        return value

    try:
        return canonical(sanitize(json.loads(raw)))
    except (ValueError, TypeError, RecursionError):
        # Non-JSON HTML keeps its audit content, but exact current CSRF/session values are removed.
        result = raw
        for original, replacement in replacements.items():
            result = result.replace(original, replacement)
        pattern = re.compile(r'(?i)(["\'](?:lease|token|csrf_token|session_token|api_key|access_token|refresh_token|password|worker_token)["\']\s*:\s*)(["\'])(.*?)(\2)', re.DOTALL)
        try:
            return pattern.sub(lambda match: match[1] + json.dumps(protected(match[3]), ensure_ascii=False), result)
        except Exception:
            return canonical({'audit_format_error': True, 'body_fingerprint': mac(secret, 'assistant-audit-body', raw)})


def http_payloads(request, response, context):
    """[Role] Captures AI business JSON or validated binary metadata without rereading rejected wire bodies.
    [Dependencies] Flask's already cached JSON bytes and route-owned file/export audit references.
    [Impact] 413/disconnect/parser errors cannot skip metadata logging or duplicate binary/CSV payloads.
    """
    raw = getattr(request, '_cached_data', None)
    metadata = {'content_type':request.mimetype, 'declared_bytes':request.content_length,
                'outcome':response.status_code, 'validated_file':getattr(context, 'assistant_audit_file', None)}
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if raw is not None and request.is_json:
            request_body = raw.decode('utf-8', errors='replace')
        else:
            request_body = canonical({'wire_body_not_reparsed':True, **metadata})
    else:
        request_body = None
    artifact = getattr(context, 'assistant_audit_export', None)
    if artifact:
        response_body = canonical({'protected_export':artifact, 'outcome':response.status_code})
    elif response.is_json or response.mimetype in ('text/html','text/plain'):
        try:
            response_body = response.get_data(as_text=True)
        except Exception as error:
            response_body = canonical({'body_unavailable':type(error).__name__, **metadata})
    else:
        response_body = canonical({'binary_not_text':True, **metadata})
    return request_body, response_body


def preserve_export(store, root, raw, actor, scope, row_count, maximum=2147483648):
    """[MINI-COMMENT: ASSISTANT.AUDIT.EXPORT]
    [EN rev.1]
    [Role] Durably preserves CSV originals under a separate physical audit budget before reporting success.
    [Dependencies] Private 0700 directory/0600 immutable files and an AI-only artifact ledger transaction.
    [Impact] Exhausted audit budget refuses export; no original is silently lost or charged to chat characters.
    """
    from .policy import AssistantError
    raw = raw.encode('utf-8') if isinstance(raw, str) else raw
    if not isinstance(raw, bytes) or type(maximum) is not int or maximum < 1048576:
        raise ValueError('invalid audit artifact configuration')
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise AssistantError('감사 원문 보관 경로를 확인해 주세요.', 503)
    os.chmod(root, 0o700)
    aid, sha = uuid.uuid4().hex, hashlib.sha256(raw).hexdigest()
    target = root / (aid + '.csv')
    try:
        with store.db(True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS ai_audit_artifacts(id TEXT PRIMARY KEY,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,owner INTEGER NOT NULL,scope TEXT NOT NULL,row_count INTEGER NOT NULL,created REAL NOT NULL)')
            used = db.execute('SELECT COALESCE(SUM(bytes),0) FROM ai_audit_artifacts').fetchone()[0]
            if used + len(raw) > maximum:
                raise AssistantError('감사 원문 보관 예산이 부족하여 내보내기를 중단했습니다. 관리자에게 문의해 주세요.', 507)
            with open(target, 'xb') as stream:
                os.chmod(target, 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            db.execute('INSERT INTO ai_audit_artifacts VALUES(?,?,?,?,?,?,?)', (aid, sha, len(raw), actor['UserId'], scope, row_count, time.time()))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {'id':aid,'sha256':sha,'bytes':len(raw),'owner':actor['UserId'],'scope':scope,'row_count':row_count}
