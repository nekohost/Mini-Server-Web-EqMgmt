"""Linux release checks using private snapshots; never import the app against live DB during copy checks."""

import argparse  # 운영 명령의 대상을 명시합니다.
import hashlib  # 행 보존 지문을 계산합니다.
import importlib.util  # 사본 DB에만 앱을 로드합니다.
import json  # 비민감한 배포 증거를 기록합니다.
import os  # 환경·파일 권한을 통제합니다.
from pathlib import Path  # 프로젝트 경로를 고정합니다.
import socket  # 서비스 포트의 기존 사용 여부를 확인합니다.
import subprocess  # 승인된 앱 프로세스를 시작합니다.
import sys  # 동일 가상환경 Python을 재사용합니다.
import time  # 기동 확인의 제한된 재시도를 수행합니다.
import urllib.request  # 실제 HTTP 응답을 확인합니다.
ROOT = Path(__file__).resolve().parents[1]  # 이 스크립트의 저장소를 owner로 고정합니다.
sys.path.insert(0, str(ROOT))  # 공통 DB 계약 모듈을 사용합니다.
from utils.database_contract import connect_database, assert_integrity, private_snapshot, quote_identifier, migrate_contract, rollback_contract, SCHEMA_VERSION  # 공유된 migration만 실행합니다.


def query_measurements(connection):
    """[역할] 실제 조회 조건의 전후 계획·평균 시간을 측정합니다. [의존성 관계] 운영 사본. [변경 시 영향도] 인덱스 채택 근거."""
    queries = {  # 실제 API의 핵심 조건과 정렬을 유지합니다.
        'owner': ('SELECT id FROM equipments WHERE user_id=? AND (is_draft=0 OR is_draft IS NULL) ORDER BY id DESC', (1,)),
        'public': ('SELECT id FROM equipments WHERE is_public=1 AND user_id!=? AND (is_draft=0 OR is_draft IS NULL) ORDER BY id DESC', (1,)),
        'password': ('SELECT ExpiresAt FROM password_resets WHERE UserId=? ORDER BY ExpiresAt DESC LIMIT 1', (1,)),
        'approval': ("SELECT RequestId FROM approval_requests WHERE RequestType='ADD_CATEGORY' AND Status='PENDING' AND json_extract(RequestDataJSON,'$.name')=?", ('fixture',)),
    }
    result = {}  # 민감한 조회 결과는 기록하지 않습니다.
    for name, (query, params) in queries.items():  # 각 조회를 동일 횟수 실행합니다.
        plan = [row[3] for row in connection.execute('EXPLAIN QUERY PLAN ' + query, params)]  # optimizer의 선택입니다.
        start = time.perf_counter()  # 짧은 쿼리의 고해상도 시간을 측정합니다.
        for _ in range(100):  # 작은 DB의 단발성 흔들림을 완화합니다.
            connection.execute(query, params).fetchall()  # 결과값은 즉시 폐기합니다.
        result[name] = {'plan': plan, 'mean_ms': (time.perf_counter() - start) * 10}  # 100회 평균 밀리초입니다.
    return result  # 전후 차이를 보고서에 사용합니다.


def row_fingerprints(connection):
    """[역할] 업무 행의 원문을 출력하지 않고 보존 여부를 확인합니다. [의존성 관계] SQLite. [변경 시 영향도] 배포 게이트."""
    result = {}  # 모든 기존 테이블의 typed-row 지문을 기록합니다.
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='sys_migrations' ORDER BY name").fetchall():  # migration 이력만 변화가 허용됩니다.
        digest, count = hashlib.sha256(), 0  # 한 테이블씩 처리합니다.
        for row in connection.execute(f'SELECT * FROM {quote_identifier(name)} ORDER BY rowid'):  # 현재 스키마는 rowid 테이블입니다.
            digest.update(repr(tuple(row)).encode('utf-8'))  # NULL·JSON·문자열을 구분합니다.
            digest.update(b'\n')  # 행 경계를 보존합니다.
            count += 1  # 건수를 별도로 기록합니다.
        result[name] = {'count': count, 'sha256': digest.hexdigest()}  # 원문은 포함하지 않습니다.
    return result  # 동작 후 동일 결과와 대조합니다.


def check_copy(database, backups):
    """[역할] 실제 DB 사본에서 기동·행 보존·down/up을 검증합니다.
    [의존성 관계] app.py, 검증된 온라인 백업과 FK migration.
    [변경 시 영향도] 운영 DB는 읽기만 하며 모든 앱 쓰기는 별도 사본에 격리됩니다.
    """
    source = connect_database(database.as_uri() + '?mode=ro', uri=True)  # 실제 운영 DB는 읽기 전용입니다.
    try:  # 사본 생성 전 기준선을 계산합니다.
        assert_integrity(source)  # 현재의 선언·논리 참조를 확인합니다.
        before = row_fingerprints(source)  # 코드 기동 전 기존 행을 지문화합니다.
        query_before = query_measurements(source)  # 인덱스 적용 전 실제 DB를 읽기만 합니다.
        path = Path(private_snapshot(source, database, backups, 'release-check'))  # 전체 DB를 일관되게 복제합니다.
    finally:  # 운영 reader를 기동 전에 반환합니다.
        source.close()  # 운영 앱과 추가 경합을 남기지 않습니다.
    os.environ.update(DATABASE_PATH=str(path), DATABASE_OPERATION_ROOT=str(backups / 'copy-operations'), MAINTENANCE_STATE_PATH=str(backups / 'copy-maintenance.json'), SECRET_KEY='isolated-release-copy')  # 모든 파일 쓰기를 사본 영역으로 고정합니다.
    spec = importlib.util.spec_from_file_location('release_copy_app', ROOT / 'app.py')  # 현재 commit 앱을 대상으로 합니다.
    module = importlib.util.module_from_spec(spec)  # 독립 모듈을 준비합니다.
    try:  # 앱 migration 실행을 실제 Linux에서 시험합니다.
        spec.loader.exec_module(module)  # 환경 경로 설정 후에만 import합니다.
        module.ACCESS_LOG_ACCEPTING.clear()  # 사본 smoke는 로그 원문을 생성하지 않습니다.
        module.shutdown_event.set()  # 사본 logger만 종료합니다.
        module.logger_thread.join(timeout=3)  # 종료 시간을 제한합니다.
        copy = connect_database(path)  # migration 결과를 검사합니다.
        try:  # 검사 연결의 수명을 제한합니다.
            assert_integrity(copy)  # FK와 계층 무결성을 재확인합니다.
            after = row_fingerprints(copy)  # 테이블 데이터가 그대로인지 대조합니다.
            query_after = query_measurements(copy)  # 동일 조건으로 적용 후 계획을 측정합니다.
            if before != after:  # 자동 초기화에 의한 예상 밖 변화도 차단합니다.
                raise ValueError('production copy row preservation failed')  # 운영 적용을 진행하지 않습니다.
            if copy.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:  # 목표 버전입니다.
                raise ValueError('copy schema version mismatch')  # 부분 migration을 거부합니다.
        finally:  # down/up 전에 잠금을 해제합니다.
            copy.close()  # 열린 reader가 남지 않습니다.
        rollback_contract(path, backups / 'copy-rollback')  # 사본에서만 다운 리허설을 실행합니다.
        migrate_contract(path, backups / 'copy-rollback')  # 전진 재적용의 멱등성을 확인합니다.
        repeat = migrate_contract(path, backups / 'copy-rollback')  # 두 번째 실행은 변경이 없어야 합니다.
        if repeat['applied']:  # 반복 쓰기를 허용하지 않습니다.
            raise ValueError('migration not idempotent')  # 검증 실패로 처리합니다.
        return {'copy_check': 'pass', 'rows_preserved': before, 'schema_version': SCHEMA_VERSION, 'rollback': 'pass', 'copy': str(path), 'queries_before': query_before, 'queries_after': query_after}  # 검증 증거만 반환합니다.
    finally:  # import 후 실패에서도 독립 worker를 정리합니다.
        if hasattr(module, 'shutdown_event'):  # 부분 import를 고려합니다.
            module.shutdown_event.set()  # 해당 모듈 worker에만 종료 신호를 줍니다.


def start_service(database, backups, expected_head):
    """[역할] 정확한 commit과 비어 있는 포트에서 승인된 운영 앱을 시작합니다.
    [의존성 관계] Git pull 완료, check-copy 통과, 기존 수동 app.py 실행 방식.
    [변경 시 영향도] 운영 DB 사본을 먼저 보존하며 무관한 프로세스는 종료하지 않습니다.
    """
    actual_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()  # 배포할 코드를 확인합니다.
    if actual_head != expected_head:  # 기대 commit이 다르면 실행하지 않습니다.
        raise ValueError('deployment commit mismatch')  # 부분 배포를 차단합니다.
    with socket.socket() as probe:  # 운영 포트의 현재 사용 여부를 확인합니다.
        probe.bind(('0.0.0.0', 5000))  # 이미 실행 중이면 예외로 중단하고 기존 프로세스는 유지합니다.
    source = connect_database(database.as_uri() + '?mode=ro', uri=True)  # 변경 전 읽기 연결입니다.
    try:  # 실제 적용 전 사본을 보존합니다.
        backup = private_snapshot(source, database, backups, 'production-before')  # WAL을 포함한 복구 사본입니다.
    finally:  # 실행 전에 운영 reader를 닫습니다.
        source.close()  # 포트 기동과 별도로 DB 핸들을 반환합니다.
    environment = os.environ.copy()  # 기존 서비스 설정을 승계합니다.
    environment['DATABASE_PATH'] = str(database)  # 확인한 운영 파일을 명시합니다.
    environment['FLASK_DEBUG'] = '0'  # 배포 중 디버그 서버를 노출하지 않습니다.
    log_path = backups / 'service-start.log'  # 제한된 배포 디렉터리에 로그를 남깁니다.
    descriptor = os.open(log_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)  # 로그 파일은 기존 내용을 보존합니다.
    with os.fdopen(descriptor, 'ab', buffering=0) as stream:  # 부모 종료 후에도 자식 stdout을 유지합니다.
        process = subprocess.Popen([sys.executable, '-u', 'app.py'], cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)  # 기존 수동 실행과 같은 앱을 분리 세션으로 시작합니다.
    for _ in range(30):  # 기동 확인을 최대 15초로 제한합니다.
        if process.poll() is not None:  # 앱 초기화 실패를 즉시 탐지합니다.
            raise RuntimeError('service exited during startup; inspect private release log')  # 로그의 민감 내용은 자동 출력하지 않습니다.
        try:  # 실제 요청으로 가용성을 검사합니다.
            with urllib.request.urlopen('http://127.0.0.1:5000/api/check_session', timeout=1) as response:  # 비인증 세션 상태를 확인합니다.
                if response.status == 200:  # 정상 응답만 성공으로 판정합니다.
                    return {'service': 'running', 'pid': process.pid, 'commit': actual_head, 'backup': backup, 'http': 200}  # 복구에 필요한 최소 정보입니다.
        except OSError:  # 아직 초기화 중인 경우만 다시 시도합니다.
            time.sleep(0.5)  # 사용자 업데이트를 막지 않는 짧은 재시도입니다.
    process.terminate()  # 이 호출이 생성한 정확한 프로세스만 종료합니다.
    raise RuntimeError('service health timeout')  # 불명확한 서비스 상태를 성공으로 표시하지 않습니다.


def main():
    """[역할] 명시적 check-copy/start 명령을 처리합니다. [의존성 관계] argparse. [변경 시 영향도] 배포 대상 고정."""
    parser = argparse.ArgumentParser()  # 인수 없는 실행은 usage로 종료됩니다.
    parser.add_argument('action', choices=('check-copy', 'start'))  # 일반 삭제나 임의 SQL 모드는 없습니다.
    parser.add_argument('--database', required=True, type=Path)  # DB 파일을 명시합니다.
    parser.add_argument('--backups', required=True, type=Path)  # 사본 영역을 명시합니다.
    parser.add_argument('--expected-head')  # start에서 필수로 대조합니다.
    args = parser.parse_args()  # 검증된 인수만 사용합니다.
    if os.name == 'nt':  # 프로젝트의 실행 환경 제약을 코드에서도 지킵니다.
        parser.error('Linux only')  # Windows 앱 구동을 차단합니다.
    database = args.database.resolve(strict=True)  # DB가 실제 존재해야 합니다.
    backups = args.backups.absolute()  # private_snapshot이 링크·소유자·권한을 추가 검사합니다.
    result = check_copy(database, backups) if args.action == 'check-copy' else start_service(database, backups, args.expected_head)  # 승인된 정확한 동작을 선택합니다.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))  # 읽기 쉬운 검증 결과를 반환합니다.


if __name__ == '__main__':  # import에는 부작용이 없습니다.
    main()  # 명시적 CLI 호출만 실행합니다.
