"""Connection policy, order-independent schema contracts and reversible v1 migration."""

import hashlib  # 백업과 스키마 지문을 계산합니다.
import json  # 비민감 검증 증거를 기록합니다.
import os  # 사본 권한을 제한합니다.
from pathlib import Path  # DB의 명시적 경로를 처리합니다.
import re  # SQL의 문자열과 구분자를 분리합니다.
import sqlite3  # 연결과 온라인 백업을 제공합니다.
from datetime import datetime, timezone  # migration 시각은 UTC로 기록합니다.
import uuid  # 백업 파일 이름 충돌을 방지합니다.
from utils.equipment_audit_migration import private_directory  # 검증된 사본 디렉터리 보호를 재사용합니다.

SCHEMA_VERSION = 1  # 최초로 명시한 현재 3-Tier 계약 버전입니다.
FINGERPRINT_VERSION = 2  # 컬럼 물리 순서를 제외하는 지문 형식입니다.
MIGRATION = 'database_contract_v1'  # 명명 이력과 정수 버전을 연결합니다.
REQUIRED_TABLES = frozenset({  # 레거시 equipment는 현재 기능의 필수 테이블이 아닙니다.
    'users', 'user_settings', 'menus', 'role_menu_permissions', 'categories',
    'manufacturers', 'lineup_nodes', 'equipment_options', 'equipments',
    'equipments_audit_log', 'audit_logs', 'access_logs', 'approval_requests',
    'email_verifications', 'password_resets', 'sys_migrations',
})
INDEXES = {  # 실제 WHERE/ORDER BY와 일치하는 후보를 Linux에서 검증합니다.
    'idx_contract_equipment_owner': 'CREATE INDEX idx_contract_equipment_owner ON equipments(user_id, id DESC)',
    'idx_contract_equipment_public': 'CREATE INDEX idx_contract_equipment_public ON equipments(id DESC) WHERE is_public=1 AND (is_draft=0 OR is_draft IS NULL)',
    'idx_contract_password_latest': 'CREATE INDEX idx_contract_password_latest ON password_resets(UserId, ExpiresAt DESC)',
    'idx_contract_approval_pending': 'CREATE INDEX idx_contract_approval_pending ON approval_requests(RequestType, Status)',
}


def configure_connection(connection, timeout=5.0):
    """[역할] 트랜잭션 전에 FK·대기시간을 적용하고 실패하면 연결을 반환하지 않습니다.
    [의존성 관계] connect_database/open_application_database.
    [변경 시 영향도] 모든 정상 쓰기와 백업·복원 연결의 무결성에 영향을 줍니다.
    """
    connection.execute('PRAGMA foreign_keys=ON')  # SQLite 기본값에 의존하지 않습니다.
    connection.execute(f'PRAGMA busy_timeout={max(0, min(int(timeout * 1000), 30000))}')  # 잠금 대기를 제한합니다.
    if connection.execute('PRAGMA foreign_keys').fetchone()[0] != 1:  # transaction 중의 무효 설정도 감지합니다.
        raise sqlite3.OperationalError('foreign key enforcement unavailable')  # 안전한 초기화 실패로 처리합니다.
    return connection  # 기존 Row/factory 설정은 호출자가 유지합니다.


def connect_database(database, timeout=5.0, **kwargs):
    """[역할] 일반/읽기 전용 연결을 동일한 FK 정책으로 만듭니다.
    [의존성 관계] sqlite3.connect, configure_connection.
    [변경 시 영향도] migration과 복원 보조 연결의 실패 시 핸들 정리에 영향을 줍니다.
    """
    connection = sqlite3.connect(database, timeout=timeout, **kwargs)  # URI와 factory는 그대로 전달합니다.
    try:  # 초기화가 완료된 연결만 밖으로 노출합니다.
        return configure_connection(connection, timeout)  # 연결마다 FK를 활성화합니다.
    except Exception:  # 설정 실패도 열린 핸들을 남기지 않습니다.
        connection.close()  # 파일 잠금을 즉시 반환합니다.
        raise  # 원인을 호출자에게 전달합니다.


def quote_identifier(name):
    """[역할] 스키마에서 읽은 이름을 인용합니다. [의존성 관계] PRAGMA. [변경 시 영향도] 특수문자 객체."""
    return '"' + name.replace('"', '""') + '"'  # 값 매개변수를 쓸 수 없는 식별자만 처리합니다.


def sql_tokens(sql):
    """[역할] 문자열 내용은 보존하며 공백만 무시합니다. [의존성 관계] schema_contract. [변경 시 영향도] CHECK/기본값 비교."""
    return tuple(re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|--[^\n]*|/\*[\s\S]*?\*/|[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]", sql or ''))  # 문자열 내부 공백을 축약하지 않습니다.


def table_definition(sql):
    """[역할] 컬럼 선언 순서만 정규화하고 제약 SQL 전체를 보존합니다.
    [의존성 관계] sql_tokens, schema_contract.
    [변경 시 영향도] SessionToken 순서 허용; CHECK/COLLATE/STRICT/생성 컬럼 변화는 계속 거부합니다.
    """
    tokens = sql_tokens(sql)  # 인용부 안의 쉼표와 괄호는 단일 토큰입니다.
    start = tokens.index('(')  # 일반 CREATE TABLE의 선언부를 찾습니다.
    parts, current, depth = [], [], 0  # 최상위 쉼표만 선언 구분자로 사용합니다.
    for offset, token in enumerate(tokens[start + 1:], start + 1):  # 테이블명 자체의 인용 차이는 제외합니다.
        if token == ')' and depth == 0:  # 최상위 선언부 끝입니다.
            parts.append(tuple(current))  # 마지막 컬럼/제약을 보존합니다.
            return tuple(sorted(parts)), tokens[offset + 1:]  # STRICT 등 테이블 옵션을 보존합니다.
        if token == ',' and depth == 0:  # 컬럼 정의 내부 쉼표는 분리하지 않습니다.
            parts.append(tuple(current))  # 완전한 선언을 추가합니다.
            current = []  # 다음 선언을 시작합니다.
        else:  # 표현식·문자열·하위 괄호를 원형대로 보존합니다.
            current.append(token)  # 단어 대소문자도 임의 변환하지 않습니다.
            depth += (token == '(') - (token == ')')  # 괄호 깊이를 추적합니다.
    raise ValueError('unsupported table definition')  # 불명확한 SQL은 동등하다고 판단하지 않습니다.


def schema_contract(connection):
    """[역할] 물리 cid·인덱스 나열 순서 이외의 구조를 보존합니다.
    [의존성 관계] table_xinfo, index_xinfo, foreign_key_list, sqlite_master.
    [변경 시 영향도] 백업 후보 호환성과 migration 지문의 기준입니다.
    """
    result = {}  # 객체명을 키로 사용합니다.
    objects = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type IN ('table','index','view','trigger') ORDER BY type,name")  # 모든 앱 객체를 조회합니다.
    for kind, name, table, sql in objects.fetchall():  # 별도 PRAGMA 실행 전에 결과를 고정합니다.
        if kind != 'table':  # 표현식/부분 인덱스와 trigger/view SQL을 빠짐없이 비교합니다.
            result[(kind, name)] = (table, sql_tokens(sql))  # SQL 문자열 리터럴은 보존합니다.
            continue  # 테이블 전용 검사를 건너뜁니다.
        columns = tuple(sorted(tuple(row)[1:] for row in connection.execute(f'PRAGMA table_xinfo({quote_identifier(name)})')))  # 물리 cid만 제외합니다.
        foreign_keys = tuple(sorted(tuple(row)[1:] for row in connection.execute(f'PRAGMA foreign_key_list({quote_identifier(name)})')))  # FK 나열 ID만 제외합니다.
        indexes = []  # 자동 UNIQUE 인덱스도 의미로 비교합니다.
        for row in connection.execute(f'PRAGMA index_list({quote_identifier(name)})').fetchall():  # 반환 순서는 계약에 넣지 않습니다.
            columns_in_index = tuple((col[0], col[2], col[3], col[4], col[5]) for col in connection.execute(f'PRAGMA index_xinfo({quote_identifier(row[1])})'))  # cid 대신 컬럼 이름을 사용합니다.
            indexes.append((row[2], row[3], row[4], columns_in_index))  # unique/origin/partial을 보존합니다.
        result[(kind, name)] = (table_definition(sql), columns, foreign_keys, tuple(sorted(indexes, key=repr)))  # 정의·PRAGMA를 교차 보존합니다.
    return result  # tuple key는 호출자가 직렬화합니다.


def schema_fingerprint(connection):
    """[역할] 정렬된 계약의 SHA를 반환합니다. [의존성 관계] schema_contract. [변경 시 영향도] 증거 파일."""
    return hashlib.sha256(repr(sorted(schema_contract(connection).items())).encode('utf-8')).hexdigest()  # 민감한 행 데이터는 지문에 넣지 않습니다.


def assert_integrity(connection):
    """[역할] 실제 FK와 운영에 필요한 논리 참조를 검증합니다.
    [의존성 관계] 현재 3-Tier 테이블; 감사의 과거 actor/equipment ID는 독립 보존합니다.
    [변경 시 영향도] migration/배포를 고아 데이터가 있는 상태에서 중단합니다.
    """
    if [row[0] for row in connection.execute('PRAGMA integrity_check')] != ['ok']:  # 파일 무결성을 확인합니다.
        raise ValueError('database integrity check failed')  # 행 값은 오류에 넣지 않습니다.
    if connection.execute('PRAGMA foreign_key_check').fetchone():  # 현재 선언된 모든 FK를 검사합니다.
        raise ValueError('database foreign key violation')  # 첫 위반에서 중단합니다.
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}  # 현재 스키마 집합입니다.
    if not REQUIRED_TABLES.issubset(tables):  # 필수 3-Tier 테이블을 확인합니다.
        raise ValueError('required current schema missing')  # 레거시 단일 테이블로 통과할 수 없습니다.
    relations = (('equipments', 'user_id', 'users', 'UserId'), ('password_resets', 'UserId', 'users', 'UserId'), ('role_menu_permissions', 'MenuCode', 'menus', 'MenuCode'))  # FK 없는 현재 소유/권한 관계입니다.
    for child, key, parent, target in relations:  # 모두 코드에 고정된 식별자입니다.
        if connection.execute(f'SELECT 1 FROM {child} c LEFT JOIN {parent} p ON c.{key}=p.{target} WHERE c.{key} IS NOT NULL AND p.{target} IS NULL LIMIT 1').fetchone():  # NULL 허용 관계는 유지합니다.
            raise ValueError(f'logical reference violation: {child}.{key}')  # 식별자만 기록합니다.
    if connection.execute('SELECT 1 FROM lineup_nodes n JOIN lineup_nodes p ON n.parent_id=p.id WHERE n.category_id!=p.category_id OR n.manufacturer_id!=p.manufacturer_id OR n.depth!=p.depth+1 LIMIT 1').fetchone():  # 계층 분류 일치를 검사합니다.
        raise ValueError('lineup hierarchy mismatch')  # 계층 손상을 통과시키지 않습니다.
    if connection.execute('SELECT 1 FROM lineup_nodes WHERE depth<1 OR depth>50 OR (parent_id IS NULL AND depth!=1) LIMIT 1').fetchone():  # depth 단조 증가와 최대 깊이로 순환도 차단합니다.
        raise ValueError('invalid lineup depth')  # 모델 경로 무결성을 보존합니다.


def private_snapshot(connection, database_path, backup_root, label):
    """[역할] 활성 writer와 별도의 reader로 검증된 DB 사본·증거를 보존합니다.
    [의존성 관계] Online Backup API, private_directory.
    [변경 시 영향도] migration 실패 시 코드와 DB의 독립 복구 경로입니다.
    """
    root = private_directory(backup_root)  # 전용 디렉터리는 0700입니다.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')  # UTC 시각을 파일 이름에 넣습니다.
    path = root / f'{label}-{stamp}-{uuid.uuid4().hex}.db'  # 기존 파일을 덮어쓰지 않습니다.
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)  # 처음부터 파일 접근을 제한합니다.
    os.close(descriptor)  # SQLite가 별도 핸들로 파일을 엽니다.
    reader = connect_database(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True, timeout=30)  # writer 자체를 backup하지 않습니다.
    backup = connect_database(path, timeout=30)  # 검증할 목적지입니다.
    try:  # 실패한 사본도 조사용으로 보존합니다.
        reader.backup(backup)  # WAL을 포함한 일관된 스냅샷을 생성합니다.
        assert_integrity(backup)  # 사본의 무결성과 논리 관계를 확인합니다.
        evidence = {'schema_version': backup.execute('PRAGMA user_version').fetchone()[0], 'schema_fingerprint': schema_fingerprint(backup), 'integrity': 'ok', 'foreign_keys': 0, 'migrations': [r[0] for r in backup.execute('SELECT MigrationName FROM sys_migrations ORDER BY MigrationName')]}  # 민감 값 없이 기준선을 남깁니다.
        evidence['counts'] = {name: backup.execute(f'SELECT COUNT(*) FROM {quote_identifier(name)}').fetchone()[0] for name in sorted(REQUIRED_TABLES)}  # 행 수를 비교합니다.
    finally:  # 파일 해시 전에 DB 핸들을 닫습니다.
        backup.close()  # 사본의 기록을 완료합니다.
        reader.close()  # 운영 reader를 반환합니다.
    with path.open('rb') as stream:  # 사본 바이트를 스트리밍으로 해시합니다.
        evidence['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()  # Linux Python 3.12에서 지원합니다.
    descriptor = os.open(path.with_suffix('.json'), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)  # 증거 파일도 보호합니다.
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:  # 제한된 파일 핸들로 씁니다.
        json.dump(evidence, stream, ensure_ascii=False, indent=2)  # 민감 데이터 원문은 저장하지 않습니다.
    return str(path)  # 호출자는 복구 위치만 보고합니다.


def migrate_contract(database_path, backup_root):
    """[역할] 기존 행을 보존하고 인덱스·정수 버전을 원자적으로 적용합니다.
    [의존성 관계] init_db와 기존 migration 완료 후 호출; sys_migrations.
    [변경 시 영향도] 실패 시 rollback, 사전 검증 사본은 자동 삭제하지 않습니다.
    """
    connection = connect_database(database_path, timeout=30)  # 정상 FK 정책을 적용합니다.
    try:  # 전체 변경을 하나의 writer 트랜잭션으로 묶습니다.
        connection.execute('BEGIN IMMEDIATE')  # 다른 writer와 migration 경합을 방지합니다.
        version = connection.execute('PRAGMA user_version').fetchone()[0]  # 예상치 못한 버전은 거부합니다.
        recorded = connection.execute('SELECT 1 FROM sys_migrations WHERE MigrationName=?', (MIGRATION,)).fetchone()  # 명명 이력을 교차 검사합니다.
        if version not in (0, SCHEMA_VERSION) or bool(recorded) != (version == SCHEMA_VERSION):  # 부분 migration을 자동 승인하지 않습니다.
            raise ValueError('database schema version/history mismatch')  # 현재 코드의 지원 범위를 벗어났습니다.
        assert_integrity(connection)  # 적용 전 파일·논리 무결성을 검사합니다.
        if recorded:  # 재실행은 스키마 계약을 확인하고 종료합니다.
            for name, sql in INDEXES.items():  # 누락/변조된 인덱스도 탐지합니다.
                row = connection.execute('SELECT sql FROM sqlite_master WHERE type=\'index\' AND name=?', (name,)).fetchone()  # 이름 충돌을 확인합니다.
                if not row or sql_tokens(row[0]) != sql_tokens(sql):  # 동일 이름의 잘못된 구조를 거부합니다.
                    raise ValueError('database contract index mismatch')  # 무조건 IF NOT EXISTS로 숨기지 않습니다.
            connection.rollback()  # 검증만 한 writer 잠금을 해제합니다.
            return {'applied': False, 'version': version}  # 반복 적용을 명확히 보고합니다.
        backup = private_snapshot(connection, database_path, backup_root, 'contract-before')  # 변경 전에 복구 사본을 확정합니다.
        for sql in INDEXES.values():  # 기존 업무 행은 변경하지 않습니다.
            connection.execute(sql)  # 이름 충돌도 정상적으로 실패 처리합니다.
        connection.execute('INSERT INTO sys_migrations(MigrationName,AppliedAt) VALUES(?,?)', (MIGRATION, datetime.now(timezone.utc).isoformat()))  # 성공할 트랜잭션 안에서만 이력을 남깁니다.
        connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')  # 정수 버전을 이력과 함께 적용합니다.
        assert_integrity(connection)  # 적용 후 검증 실패 시 commit하지 않습니다.
        connection.commit()  # 인덱스·버전·이력을 동시에 확정합니다.
        return {'applied': True, 'version': SCHEMA_VERSION, 'backup_path': backup}  # 복구 정보를 반환합니다.
    except Exception:  # 모든 실패 경로에서 변경을 취소합니다.
        connection.rollback()  # 원본 행과 버전을 보존합니다.
        raise  # 서비스 시작 또는 배포 검증을 중단합니다.
    finally:  # 호출 결과와 무관하게 잠금을 반환합니다.
        connection.close()  # 연결을 해제합니다.


def rollback_contract(database_path, backup_root):
    """[역할] v1 인덱스·버전만 되돌립니다. [의존성 관계] 서비스 중지 후 CLI. [변경 시 영향도] 업무 행·감사·레거시를 보존합니다."""
    connection = connect_database(database_path, timeout=30)  # FK를 끄지 않습니다.
    try:  # down 변경도 원자적으로 묶습니다.
        connection.execute('BEGIN IMMEDIATE')  # 새로운 쓰기를 직렬화합니다.
        if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:  # 대상 버전을 확인합니다.
            raise ValueError('rollback requires schema version 1')  # 다른 버전을 수정하지 않습니다.
        backup = private_snapshot(connection, database_path, backup_root, 'contract-down-before')  # down 직전 사본을 남깁니다.
        for name in INDEXES:  # 이 migration의 인덱스만 제거합니다.
            connection.execute(f'DROP INDEX {quote_identifier(name)}')  # 사용자 인덱스는 유지합니다.
        connection.execute('DELETE FROM sys_migrations WHERE MigrationName=?', (MIGRATION,))  # 이 명명 이력만 되돌립니다.
        connection.execute('PRAGMA user_version=0')  # 이전 버전으로 복귀합니다.
        assert_integrity(connection)  # 업무 데이터 보존을 확인합니다.
        connection.commit()  # 검증 후 변경을 확정합니다.
        return {'version': 0, 'backup_path': backup}  # 코드 rollback과 연결할 정보를 반환합니다.
    except Exception:  # 누락 인덱스 등 예상치 못한 상태도 rollback합니다.
        connection.rollback()  # 부분 down을 허용하지 않습니다.
        raise  # 운영자에게 실패를 전달합니다.
    finally:  # 연결을 반드시 닫습니다.
        connection.close()  # 파일 잠금을 해제합니다.

