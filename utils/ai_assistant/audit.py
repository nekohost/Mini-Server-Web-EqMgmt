"""[MINI-COMMENT: ASSISTANT.AUDIT]
[EN rev.6]
[Role] Redacts credentials in ordinary HTTP JSON and preserves authorized CSV export evidence.
[Dependencies] HMAC, the private export directory and the assistant artifact ledger.
[Impact] Web traffic monitoring needs no copy of an assistant request, response, or attachment.
"""
import json
import re
import hashlib
import os
from utils.equipment_audit_migration import private_directory
import time
import uuid

from .policy import canonical, mac

SENSITIVE_KEYS = frozenset({
    'authorization', 'cookie', 'set-cookie', 'password', 'session_token', 'csrf_token',
    'current_password', 'new_password', 'temp_password', 'candidate_admin_password', 'pin', 'pin_code',
    'confirmation_token', 'preview_token', 'confirmation_nonce', 'access_token', 'refresh_token', 'api_key', 'worker_token', 'strata_key', 'lease', 'token', 'credential', 'ca_pem',
})

NORMALIZED_CREDENTIALS = frozenset(key.replace('-', '').replace('_', '') for key in SENSITIVE_KEYS)


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
            return {key: protected(item) if key.lower().replace('-', '').replace('_', '') in NORMALIZED_CREDENTIALS
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


def preserve_export(store, root, raw, actor, scope, row_count, maximum=2147483648):
    """[MINI-COMMENT: ASSISTANT.AUDIT.EXPORT]
    [EN rev.2]
    [Role] Durably preserves CSV originals under a separate physical audit budget before reporting success.
    [Dependencies] Private 0700 directory/0600 immutable files and an AI-only artifact ledger transaction.
    [Impact] Each export keeps a receipt. Identical bytes reuse a verified file within the same account and are charged once.
    """
    from .policy import AssistantError
    raw = raw.encode('utf-8') if isinstance(raw, str) else raw
    if not isinstance(raw, bytes) or type(maximum) is not int or maximum < 1048576:
        raise ValueError('invalid audit artifact configuration')
    try:
        root = private_directory(root)
    except (OSError, ValueError) as error:
        raise AssistantError('감사 원문 보관 경로를 확인해 주세요.', 503) from error
    aid = uuid.uuid4().hex
    sha = hashlib.sha256(raw).hexdigest()
    owner = actor['UserId']
    created = time.time()
    new_file = None
    try:
        with store.db(True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS ai_audit_artifacts(id TEXT PRIMARY KEY,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,owner INTEGER NOT NULL,scope TEXT NOT NULL,row_count INTEGER NOT NULL,created REAL NOT NULL,blob_id TEXT)')
            if 'blob_id' not in {r[1] for r in db.execute('PRAGMA table_info(ai_audit_artifacts)')}:
                db.execute('ALTER TABLE ai_audit_artifacts ADD COLUMN blob_id TEXT')
            db.execute('CREATE INDEX IF NOT EXISTS ai_artifact_owner_hash ON ai_audit_artifacts(owner,sha256,bytes)')
            db.execute('CREATE INDEX IF NOT EXISTS ai_artifact_rate ON ai_audit_artifacts(owner,created)')
            recent = db.execute('SELECT COUNT(*) FROM ai_audit_artifacts WHERE owner=? AND created>?', (owner, created-60)).fetchone()[0]
            if recent >= 30:
                raise AssistantError('내보내기 요청이 많습니다. 잠시 후 다시 시도해 주세요.', 429)
            prior = db.execute("""SELECT COALESCE(blob_id,id) FROM ai_audit_artifacts
                                  WHERE owner=? AND sha256=? AND bytes=? LIMIT 1""", (owner, sha, len(raw))).fetchone()
            if prior:
                blob = prior[0]
                if not isinstance(blob, str) or not re.fullmatch('[0-9a-f]{32}', blob):
                    raise AssistantError('감사 원본 식별자를 확인해 주세요.', 503)
                existing = root / (blob + '.csv')
                if existing.is_symlink() or not existing.is_file() or existing.stat().st_size != len(raw):
                    raise AssistantError('기존 감사 원본 파일을 확인해 주세요.', 503)
                digest = hashlib.sha256()
                with existing.open('rb') as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        digest.update(block)
                if digest.hexdigest() != sha:
                    raise AssistantError('기존 감사 원본 무결성을 확인해 주세요.', 503)
            else:
                total, personal = db.execute("""SELECT COALESCE(SUM(bytes),0),COALESCE(SUM(CASE WHEN owner=? THEN bytes ELSE 0 END),0)
                                                FROM ai_audit_artifacts WHERE blob_id IS NULL OR blob_id=id""", (owner,)).fetchone()
                if total + len(raw) > maximum or personal + len(raw) > max(1048576, maximum // 2):
                    raise AssistantError('감사 원문 보관 예산이 부족하여 내보내기를 중단했습니다. 관리자에게 문의해 주세요.', 507)
                blob = aid
                target = root / (blob + '.csv')
                with open(target, 'xb') as stream:
                    new_file = target
                    os.chmod(target, 0o600)
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            db.execute("""INSERT INTO ai_audit_artifacts(id,sha256,bytes,owner,scope,row_count,created,blob_id)
                          VALUES(?,?,?,?,?,?,?,?)""", (aid, sha, len(raw), owner, scope, row_count, created, blob))
    except Exception:
        if new_file is not None:
            new_file.unlink(missing_ok=True)
        raise
    return {'id':aid,'blob_id':blob,'sha256':sha,'bytes':len(raw),'owner':owner,'scope':scope,'row_count':row_count}
