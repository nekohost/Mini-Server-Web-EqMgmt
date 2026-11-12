"""Bounded administrator cleanups. Existing audit receipts own the cutoff, cursor and actual totals."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import re
import secrets
import sqlite3

from .http_audit_queue import cleanup_filter

CHUNK_SIZE = 250
ACTIONS = ('all', 'older_30d', 'static_only', 'all_including_ai')
START = 'CLEANUP_ACCESS_LOGS_START'
DELETE = 'CLEANUP_ACCESS_LOGS'


class CleanupError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@contextmanager
def transaction(conn):
    # Each route supplies a fresh connection. A failed receipt rolls back its deletion.
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            yield
    except (sqlite3.Error, RuntimeError) as error:
        raise CleanupError('정리 결과를 저장할 수 없습니다. 다시 시도해 주세요.', 500) from error


def criteria(action, ceiling, cutoff):
    clauses, values = ['LogId <= ?'], [ceiling]
    if action != 'all_including_ai':
        condition, paths = cleanup_filter()
        clauses.append(condition)
        values.extend(paths)
    if action == 'older_30d':
        clauses.append('CreatedAt < ?')
        values.append(cutoff)
    elif action == 'static_only':
        clauses.append('IsStatic = 1')
    return ' AND '.join(clauses), values


def begin(conn, action, actor_id, audit, ceiling):
    if action not in ACTIONS or type(ceiling) is not int or ceiling < 0:
        raise CleanupError('정리 범위를 확인해 주세요.')
    if type(actor_id) is not int or actor_id <= 0:
        raise CleanupError('관리자 정보를 확인해 주세요.', 403)
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S') if action == 'older_30d' else None
    where, values = criteria(action, ceiling, cutoff)
    nonce = secrets.token_hex(16)
    with transaction(conn):
        count = conn.execute('SELECT COUNT(*) FROM access_logs WHERE ' + where, values).fetchone()[0]
        audit(conn, START, None, {'action':action, 'bound':ceiling, 'cutoff':cutoff, 'nonce':nonce, 'total_count':count})
        start_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    return {'status':'success', 'total_count':count, 'operation_id':f'{start_id}.{nonce}'}


def operation_details(conn, operation_id, action, actor_id):
    match = re.fullmatch(r'([1-9][0-9]{0,18})\.([0-9a-f]{32})', operation_id) if isinstance(operation_id,str) else None
    if not match or int(match[1]) > 2**63 - 1:
        raise CleanupError('정리 작업 번호를 확인해 주세요.')
    start_id = int(match[1])
    row = conn.execute("""SELECT ActorId, NewValue FROM audit_logs
                          WHERE AuditId=? AND Action=? AND TargetTable='access_logs'""", (start_id, START)).fetchone()
    if row is None:
        raise CleanupError('정리 작업을 찾을 수 없습니다.',404)
    details = json.loads(row['NewValue'])
    if row['ActorId'] != actor_id or not secrets.compare_digest(details['nonce'], match[2]):
        raise CleanupError('시작한 관리자만 이 정리 작업을 진행할 수 있습니다.',403)
    if action != details['action']:
        raise CleanupError('시작할 때 선택한 정리 범위를 확인해 주세요.')
    return start_id, details


def advance(conn, action, actor_id, operation_id, step, audit):
    if step not in ('count','delete_chunk','direct','finish'):
        raise CleanupError('지원하지 않는 정리 단계입니다.')
    with transaction(conn):
        start_id, details = operation_details(conn, operation_id, action, actor_id)
        where, values = criteria(action, details['bound'], details['cutoff'])
        receipts = """ FROM audit_logs WHERE AuditId>? AND TargetTable='access_logs'
                       AND TargetId=? AND ActorId=? AND Action=? """
        bindings = (start_id, start_id, actor_id, DELETE)
        if step in ('finish','count'):
            # Recheck every eligible row, including ranges skipped by the chunk cursor.
            remaining = conn.execute('SELECT COUNT(*) FROM access_logs WHERE '+where, values).fetchone()[0]
            if step == 'count':
                return {'status':'success', 'total_count':remaining, 'remaining_count':remaining}
            if remaining:
                raise CleanupError(f'기준 시점까지 정리할 웹 접근 로그가 {remaining}건 남았습니다.',409)
            total = conn.execute("SELECT COALESCE(SUM(json_extract(NewValue,'$.deleted_count')),0)" + receipts, bindings).fetchone()[0]
            return {'status':'success', 'remaining_count':0, 'deleted_count':total}

        if step == 'direct':
            deleted = conn.execute('DELETE FROM access_logs WHERE '+where,values).rowcount
            last_id = details['bound']
        else:
            previous = conn.execute("SELECT json_extract(NewValue,'$.last_id')" + receipts +
                                    ' ORDER BY AuditId DESC LIMIT 1', bindings).fetchone()
            if previous:
                where += ' AND LogId > ?'
                values.append(previous[0])
            ids = [r[0] for r in conn.execute('SELECT LogId FROM access_logs WHERE '+where+
                                               ' ORDER BY LogId LIMIT ?', (*values, CHUNK_SIZE))]
            if not ids:
                return {'status':'success', 'deleted_count':0}
            marks = ','.join('?' for _ in ids)
            deleted = conn.execute('DELETE FROM access_logs WHERE LogId IN ('+marks+')', ids).rowcount
            last_id = ids[-1]
        if deleted:
            audit(conn, DELETE, start_id, {'action':action,'deleted_count':deleted,'last_id':last_id})
        return {'status':'success','deleted_count':deleted}
