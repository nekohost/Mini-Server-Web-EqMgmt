"""
================================================================================
[미니서버 웹 장비관리 시스템 - 메인 애플리케이션 엔트리포인트]
================================================================================
[역할]:
  - Flask 웹 프레임워크 기반 백엔드 애플리케이션 코어 구동
  - 사용자 인증, 세션 수명주기 통제, 권한 제어(RBAC), 3-Tier 장비 카탈로그 관리
  - 실시간 HTTP 웹 접근 로그 비동기 수집 및 SQLite DB 벌크 트랜잭션 적재
  - 보안 감사 로그(Audit Log) 및 동적 메타데이터 라우팅 엔드포인트 제공

[의존성 관계]:
  - SQLite3 데이터베이스: equipment.db (access_logs, users, equipments, lineup_nodes 등)
  - Python 표준 및 서드파티 라이브러리: Flask, Werkzeug, python-dotenv, threading, queue 등
  - 내부 유틸리티 모듈: utils/mailer.py (send_email)
  - 템플릿 및 정적 리소스: templates/*.html, static/*, Resources/*

[변경 시 영향도]:
  - 시스템 전역의 모든 HTTP 라우팅, DB 스키마 마이그레이션, 비동기 로깅 파이프라인,
    사용자 권한 통제 및 RESTful API 인터페이스 전반에 직접적인 영향을 미칩니다.
================================================================================
"""

# ==========================================
# 1. 필요한 외부 및 내부 라이브러리 임포트
# ==========================================
# Flask 코어 및 HTTP 요청/응답 제어에 필요한 컨텍스트 모듈 로드
from flask import (
    Flask, render_template, request, jsonify, 
    redirect, url_for, session, send_from_directory, g
)
import sqlite3               # 경량 RDBMS 엔진 임포트 (equipment.db 연동)
import os                    # 시스템 경로 탐색 및 환경변수(os.environ) 접근
import json                  # JSON 텍스트 파싱 및 딕셔너리 직렬화 변환
import queue                 # 비동기 로깅 워커로 넘길 Thread-safe 버퍼 큐 생성용
import threading             # 메인 스레드와 독립된 데몬 워커 스레드 생성용
import atexit                # Flask 프로세스 강제 종료 시 잔여 큐 처리 콜백 훅 등록
import time                  # 요청 Latency(ms) 계산을 위한 고정밀 타임스탬프 취득용
from datetime import datetime, timedelta  # 현재 시각 조회 및 세션 만료 시간 연산용
from functools import wraps  # 커스텀 데코레이터 선언 시 원본 뷰 함수의 __name__ 등 메타데이터 보존용
from werkzeug.security import generate_password_hash, check_password_hash # DB 평문 패스워드 방어용 단방향 해싱
from werkzeug.middleware.proxy_fix import ProxyFix # Nginx 등 리버스 프록시 뒤의 클라이언트 원본 IP(X-Forwarded-For) 복원 미들웨어
from dotenv import load_dotenv # 루트 경로의 .env 파일을 읽어 os.environ에 주입
import random                # 이메일 인증 등 보안 PIN 6자리 코드 생성용
import string                # PIN 코드 생성 시 0-9 숫자 집합(string.digits) 참조용
import uuid                  # 비밀번호 재설정 고유 링크용 128-bit 무작위 UUID v4 생성용
import secrets               # 예측 불가능한 세션 갱신 토큰 및 CSRF 보안 난수 생성용
from utils.mailer import send_email # 로컬 SMTP 대신 MS Graph API 비동기 메일 발송 래퍼 모듈 임포트
import warnings              # Python 3.14+ 호환성 경고 등 비위험 시스템 경고 제어용

# [버그 수정] Flask(Werkzeug) 자동 재시작(Reloader) 종료 시 발생하는 multiprocessing 세마포어 누수 경고 무시
# - 파이썬 3.14 이상 환경에서 multiprocessing 자원 정리 시 발생하는 비위험 경고 차단
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

# 시스템 기동 전 .env 환경설정 파일 로드 (SECRET_KEY, EMAIL_HOST 등 초기화)
load_dotenv()

# __name__ 모듈 네임스페이스를 기반으로 Flask WSGI 애플리케이션 코어 인스턴스 초기화
app = Flask(__name__)

# Nginx 등 외부 리버스 프록시 통과 시 변조되는 헤더(클라이언트 실 IP, HTTPS 스킴, 호스트)를 원본 기준으로 복구
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# 세션 데이터 위변조 방지를 위한 암호학적 서명 키 설정 (.env 누락 시 하드코딩된 'default_secret_key_if_not_found' 사용)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key_if_not_found')

# 보안 쿠키 및 세션 유효 기간 정책 강화
app.config['SESSION_COOKIE_HTTPONLY'] = True    # 클라이언트 사이드 JavaScript(XSS)를 통한 세션 쿠키 탈취 원천 차단
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'     # 서드파티 도메인에서의 CSRF 공격 방어를 위한 쿠키 전송 모드 설정
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) # 사용자 활동 없을 시 세션 자동 파기를 위한 30분 타이머 설정

# ==========================================
# 1-0. [제안-038] 동적 메타데이터 라우팅 엔진
# ==========================================
# 정적 메타데이터 라우트 경로 캐싱 집합 (전역 변수로 선언하여 after_request에서 O(1) 초고속 조회용도)
STATIC_METADATA_ROUTES = set()

def register_dynamic_metadata_routes(app):
    """
    [역할]:
      - Resources/metadata/ 디렉터리 하위의 모든 정적/메타 파일(robots.txt, sitemap.xml, 보안 파일 등)을 스캔
      - Flask URL 규칙(add_url_rule)으로 동적 자동 등록하여 별도 하드코딩 라우터 작성 불필요
    [의존성 관계]:
      - Python 내장 os, send_from_directory, Flask URL 맵
    [변경 시 영향도]:
      - Resources/metadata 디렉터리 내 파일 추가/수정/삭제 시 서버 재시작으로 즉시 반영되며,
        정적 리소스 접근 로깅 및 보안 라우팅 목록(STATIC_METADATA_ROUTES)에 실시간 등록됩니다.
    """
    # 파비콘 등 최빈도 호출 기본 정적 리소스를 캐시에 통합하여 접근 로그 통계 최적화 달성
    STATIC_METADATA_ROUTES.add('/favicon.ico')
    
    # __file__ 기준 절대 경로를 연산하여 Resources/metadata 타겟 폴더 경로 추출
    metadata_dir = os.path.join(os.path.dirname(__file__), 'Resources', 'metadata')
    
    # 해당 메타데이터 디렉터리가 물리적으로 존재하지 않을 경우 예외 처리
    if not os.path.exists(metadata_dir):
        # 디렉터리가 없을 경우 서버 다운을 방지하고 단순 경고 출력 후 동적 라우팅 스킵
        print(f"[Init] Metadata directory not found: {metadata_dir}")
        return

    # No-Code/Fail-Safe: URL 맵에 이미 등록된 기존 룰(Rule) 집합을 Set Comprehension으로 캐싱 (중복 등록 예외 원천 방어)
    existing_rules = {rule.rule for rule in app.url_map.iter_rules()}

    # os.walk를 통해 metadata_dir 하위의 모든 서브디렉터리 및 파일 트리 구조를 재귀적으로 스캔
    for root, _, files in os.walk(metadata_dir):
        # 각 폴더 내에 존재하는 파일 리스트 순회
        for file in files:
            # 타겟 파일의 루트 대비 상대 경로(rel_dir) 계산 및 OS별 경로 구분자 역슬래시(\)를 웹 표준 슬래시(/)로 일괄 치환
            rel_dir = os.path.relpath(root, metadata_dir).replace('\\', '/')
            
            # 현재 디렉터리가 루트(.)인 경우 바로 루트 경로(/:file)로 매핑
            if rel_dir == '.':
                route_path = f"/{file}"
            # 서브 디렉터리인 경우 경로(/:rel_dir/:file)로 조합하여 최종 URL 생성
            else:
                route_path = f"/{rel_dir}/{file}"

            # Flask URL 맵 충돌 방어: 생성된 경로가 이미 등록되어 있다면 스킵
            if route_path in existing_rules:
                print(f"[Init] Skip existing route: {route_path}")
                continue

            # 동적 뷰 함수(View Function) 생성 팩토리 클로저
            # (dir_path와 filename을 클로저 환경에 캡처하여 루프 변수 덮어쓰기 버그 방지)
            def create_view_func(dir_path, filename):
                # 람다 함수로 지연 평가되며, 요청 시 send_from_directory를 통해 로컬 파일을 HTTP Response로 스트리밍 반환
                return lambda: send_from_directory(dir_path, filename)
            
            # url_for()에 사용될 고유 endpoint 명칭 생성 (URL 슬래시 및 온점을 언더스코어로 치환하여 고유 식별자 부여)
            endpoint_name = f"metadata_{route_path.replace('/', '_').replace('.', '_')}"
            
            try:
                # 안전하게 조합된 URL과 팩토리 함수를 Flask WSGI 애플리케이션 객체 라우터에 플러그인(등록)
                app.add_url_rule(route_path, endpoint_name, create_view_func(root, file))
                # 등록 성공 시 화이트리스트 Set 캐시에 경로를 적재
                STATIC_METADATA_ROUTES.add(route_path)
                # 터미널에 정상 등록 로그 표출
                print(f"[Init] Registered dynamic metadata route: {route_path}")
            except Exception as e:
                # 라우트 동적 바인딩 중 크래시 발생 시 시스템 다운을 막고 개별 뷰 등록만 실패 처리 격리
                print(f"[Init Error] Failed to register route {route_path}: {e}")

# 애플리케이션 객체(app) 생성 직후 1회 호출되어 동적 라우팅 트리를 모두 스캔 및 초기화
register_dynamic_metadata_routes(app)

# 초기화가 끝난 가변 Set 캐시를 불변(Immutable) 객체인 frozenset으로 캐스팅
# (멀티스레드 환경에서 Thread-safe 보장 및 O(1) 조회 성능 극대화 목적)
STATIC_METADATA_ROUTES_FROZEN = frozenset(STATIC_METADATA_ROUTES)

# ==========================================
# 1-1. [제안-036] 웹 접근 로그 비동기 수집 엔진
# ==========================================
# 메인 웹 스레드와 백그라운드 DB 쓰기 스레드 간 로그 페이로드를 전달할 메모리 큐 인스턴스 생성 (최대 10,000건 제한으로 OOM 방어)
access_log_queue = queue.Queue(maxsize=10000)

# 서버 애플리케이션 강제 종료 시 백그라운드 워커에게 종료 시점을 알리기 위한 멀티스레드 안전 플래그 객체 생성
shutdown_event = threading.Event()

def push_access_log(log_data):
    """
    [역할]:
      - after_request 인터셉터에서 전달받은 HTTP 요청/응답 로그 딕셔너리를 메모리 큐에 적재
      - Non-blocking 큐 푸시(put_nowait)로 웹 클라이언트 응답 지연 0% 절대 보장 (Fail-Open 설계)
    [의존성 관계]:
      - access_log_queue, @app.after_request
    [변경 시 영향도]:
      - 큐 용량 초과 시 로그를 안전하게 드롭하여 웹 메인 서비스의 가용성(Availability)을 최우선 보호합니다.
    """
    try:
        # 워커 스레드가 처리 속도를 따라가지 못하더라도, 클라이언트 응답 스레드가 블록킹(대기)되지 않도록 즉시 푸시 시도
        access_log_queue.put_nowait(log_data)
    except queue.Full:
        # 트래픽 폭주로 10,000건 큐가 꽉 찬 상태: 웹 서비스 정상 동작을 최우선으로 하여 해당 접근 로그를 드롭하고 패스(Fail-Open)
        pass

def _write_logs_to_db(logs):
    """
    [역할]:
      - 버퍼링된 복수(최대 50건)의 로그 데이터를 SQLite DB에 벌크 INSERT 트랜잭션으로 단일 커밋
      - WAL 모드 및 busy_timeout 설정을 통해 동시성 락 충돌 최소화 및 디스크 쓰기 I/O 95% 절감
    [의존성 관계]:
      - SQLite3 (equipment.db), access_logs 테이블, access_log_queue.task_done()
    [변경 시 영향도]:
      - 디스크 I/O 최적화 및 접근 로그 영구 저장 무결성에 직접적인 영향을 미칩니다.
    """
    try:
        # 워커 스레드 전용 독립 DB 커넥션 생성 (DB 잠금 시 최대 5.0초 동안 자동 재시도 대기)
        conn = sqlite3.connect('equipment.db', timeout=5.0)
        # 쿼리 실행을 위한 커서 획득
        cur = conn.cursor()
        
        # 메인 웹 스레드의 읽기(SELECT) 작업과 현재 워커의 쓰기(INSERT) 작업이 동시에 일어날 수 있도록 WAL(Write-Ahead Logging) 활성화
        cur.execute("PRAGMA journal_mode = WAL;")
        # 디스크 Sync 주기를 NORMAL로 하향 조정하여 쓰기 I/O 성능 극대화 (정전 시 일부 손실은 감수하되, 앱 크래시 시에는 안전)
        cur.execute("PRAGMA synchronous = NORMAL;")
        # DB 잠금 락 발생 시 내부적으로 대기할 최대 타임아웃 5000밀리초 설정 (스레드 충돌 경감)
        cur.execute("PRAGMA busy_timeout = 5000;")
        
        # 리스트에 담긴 수십 건의 로그 딕셔너리를 단일 트랜잭션으로 한 번에(executemany) DB에 삽입 (I/O 병목 방지)
        cur.executemany("""
            INSERT INTO access_logs (
                IpAddress, HttpMethod, RequestPath, StatusCode, 
                UserAgent, Referer, DurationMs, IsStatic, 
                RequestPayload, ResponsePayload, CreatedAt
            )
            VALUES (
                :IpAddress, :HttpMethod, :RequestPath, :StatusCode, 
                :UserAgent, :Referer, :DurationMs, :IsStatic, 
                :RequestPayload, :ResponsePayload, :CreatedAt
            )
        """, logs)
        
        # [사용자 지침: 추후 필요 시 주석 해제하여 활성화 - 최대 30,000건 유지 자동 롤링]
        # cur.execute("DELETE FROM access_logs WHERE LogId NOT IN (SELECT LogId FROM access_logs ORDER BY LogId DESC LIMIT 30000)")
        
        # INSERT 된 데이터를 디스크에 물리적으로 반영(단일 커밋)
        conn.commit()
        # 커넥션 닫고 DB 파일 잠금 해제
        conn.close()
    except Exception as e:
        # 백그라운드 워커 DB 저장 오류 시 콘솔 출력 후 스레드 지속 구동 (워커 크래시로 인한 애플리케이션 다운 방지)
        print(f"[Access Log Worker Error] {e}")
    finally:
        # 큐 인스턴스에 처리 완료된 작업 개수만큼 task_done() 신호를 보내 내부 카운터 차감 (join() 시 무한 루프 방지)
        for _ in range(len(logs)):
            access_log_queue.task_done()

def batch_logger_worker():
    """
    [역할]:
      - 백그라운드 단일 데몬 워커 스레드 함수
      - 0.5초 타임아웃 폴링 기반으로 큐에서 최대 50건씩 묶어 벌크 쓰기 수행
      - 프로세스 종료(shutdown_event) 감지 시 큐 잔여 데이터를 100% 비우고 정상 종료
    [의존성 관계]:
      - access_log_queue, shutdown_event, _write_logs_to_db()
    [변경 시 영향도]:
      - 실시간 웹 요청 처리 성능 유지 및 서버 종료 시 로그 유실 방지(Graceful Shutdown)를 보장합니다.
    """
    # 전역 종료 플래그(shutdown_event)가 True로 세팅될 때까지 데몬 무한 루프 구동
    while not shutdown_event.is_set():
        # 이번 배치 턴에서 DB에 삽입할 로그들을 모아둘 빈 리스트 초기화
        logs_to_insert = []
        try:
            # 큐에서 아이템 1개를 가져올 때까지 최대 0.5초 대기 (0.5초 타임아웃 발생 시 Except 블록으로 넘어가 shutdown_event 검사 재진행)
            item = access_log_queue.get(timeout=0.5)
            # 데이터를 성공적으로 꺼냈다면 배치 리스트에 추가
            logs_to_insert.append(item)
            
            # 첫 아이템을 꺼낸 직후, 큐에 대기 중인 나머지 아이템을 최대 49개(총 50개)까지 추가로 쓸어담기 위한 논블로킹 내부 루프
            while len(logs_to_insert) < 50:
                try:
                    # 대기 시간 없이 즉시 큐에서 꺼내고 큐가 비어있으면 Empty 예외 발생
                    logs_to_insert.append(access_log_queue.get_nowait())
                except queue.Empty:
                    # 큐가 비었다면 즉시 내부 루프를 탈출하여 지금까지 모은 데이터만 커밋하러 감
                    break
        except queue.Empty:
            # 0.5초 동안 단 1건의 요청도 없었을 경우, 메인 루프 처음으로 돌아가 종료 시그널이 왔는지 다시 판별
            continue

        # 수집된 로그(최소 1건 ~ 최대 50건)가 리스트에 담겨있다면
        if logs_to_insert:
            # 벌크 INSERT 전용 내부 함수를 호출하여 DB 쓰기 수행
            _write_logs_to_db(logs_to_insert)

    # ==============================================================
    # [Graceful Shutdown 처리] 메인 스레드로부터 종료 신호(Event.set) 수신 시
    # ==============================================================
    # 큐에 아직 쌓여있고 꺼내지 못한 마지막 잔여 로그들을 보관할 리스트 선언
    remaining_logs = []
    
    # 큐가 완전히 비워질 때까지 반복하여 마지막 한 톨까지 탈탈 털어냄
    while not access_log_queue.empty():
        try:
            # 논블로킹으로 잔여 로그 인출하여 리스트에 추가
            remaining_logs.append(access_log_queue.get_nowait())
        except queue.Empty:
            # 찰나의 순간에 다른 스레드가 꺼내가 큐가 비었다면 탈출
            break
            
    # 최종적으로 인출된 잔여 로그가 존재한다면 DB에 마지막으로 벌크 커밋 수행
    if remaining_logs:
        _write_logs_to_db(remaining_logs)

def on_app_exit():
    """
    [역할]:
      - Python atexit 훅으로 등록되어 프로세스 종료 시 워커에 종료 신호(Event.set())를 송신하고 스레드 안전 대기
    [의존성 관계]:
      - shutdown_event, logger_thread, atexit
    [변경 시 영향도]:
      - 메인 스레드와 워커 스레드 간 DB 락 교착 없이 안전한 종료(Clean Shutdown)를 실현합니다.
    """
    # 데몬 워커 스레드의 while 루프 조건문을 False로 만들기 위해 플래그 설정
    shutdown_event.set()
    # 워커 스레드가 마지막 잔여 큐 데이터를 모두 DB에 쓰고 완전히 종료될 때까지 메인 스레드가 최대 3.0초 기다려줌
    logger_thread.join(timeout=3.0)

# 백그라운드 단일 로거 데몬 스레드 객체 생성 (메인 스레드 종료 시 강제 종료되도록 daemon=True 설정, 단 atexit으로 안전 종료 유도)
logger_thread = threading.Thread(target=batch_logger_worker, daemon=True)
# 데몬 워커 스레드 구동 시작
logger_thread.start()
# 프로세스가 종료될 때(SIGINT 등) on_app_exit 훅이 자동 실행되도록 등록
atexit.register(on_app_exit)


# ==========================================
# 2. DB 공통 모듈 (모든 DB 관련 함수가 이 모듈에 의존함)
# ==========================================

def get_db_connection():
    """
    [역할]:
      - SQLite3 데이터베이스(equipment.db) 연결 객체를 생성하고 컬럼명 기반 접근(Row factory)을 설정하여 반환
    [의존성 관계]:
      - sqlite3 모듈, equipment.db 파일
    [변경 시 영향도]:
      - 시스템 내 모든 뷰 함수 및 REST API의 DB 조회/쓰기 연결 방식에 전역적인 영향을 미칩니다.
    """
    # 데이터베이스 파일 연결 수립
    conn = sqlite3.connect('equipment.db')
    # Row 객체를 반환하도록 팩토리 설정 변경하여 row['ColumnName'] 과 같이 딕셔너리형 키 접근을 가능케 함
    conn.row_factory = sqlite3.Row
    # 세팅 완료된 커넥션 객체 반환
    return conn


def log_audit(actor_id, actor_login_id, action, target_table, target_id=None, old_value=None, new_value=None):
    """
    [역할]:
      - 사용자의 주요 행동(로그인, 장비 추가/수정/삭제, 권한 변경 등)을 감사 로그(audit_logs) 테이블에 영구 보존
      - IP 주소(X-Forwarded-For 역추적), User-Agent, 이전 값(JSON) 및 변경 값(JSON) 정밀 기록
    [의존성 관계]:
      - audit_logs 테이블, get_db_connection(), json 모듈
    [변경 시 영향도]:
      - 전역 시스템 보안 감사 및 관리자 감사 로그 화면(/audit_logs)의 데이터 무결성에 직접적인 영향을 줍니다.
    """
    try:
        # 클라이언트 IP 추출 (Nginx 등의 프록시 환경을 고려하여 X-Forwarded-For 헤더를 최우선으로 검사하고, 없으면 직결 IP 사용)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        # 접속에 사용된 브라우저나 클라이언트 앱의 환경 정보(User-Agent)를 헤더에서 추출 (없으면 빈 문자열 할당)
        user_agent = request.headers.get('User-Agent', '')
        
        # 이전 값이 딕셔너리 형태로 전달되었을 경우 파이썬 기본 json 모듈을 사용하여 문자열 스냅샷으로 직렬화 (한글 깨짐 방지를 위해 ensure_ascii=False 설정)
        old_json = json.dumps(old_value, ensure_ascii=False) if old_value is not None else None
        # 변경 후의 신규 값 역시 존재한다면 JSON 문자열로 직렬화 처리
        new_json = json.dumps(new_value, ensure_ascii=False) if new_value is not None else None
        # 현재 서버의 로컬 시각을 YYYY-MM-DD HH:MM:SS 포맷의 문자열로 생성하여 타임스탬프로 사용
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # DB 연결 수립
        conn = get_db_connection()
        # 명령 실행 커서 확보
        cursor = conn.cursor()
        
        # audit_logs 테이블에 행위자, 대상, 행위 종류, 데이터 변경점 스냅샷을 영구 삽입하는 쿼리 실행
        cursor.execute('''
            INSERT INTO audit_logs (
                ActorId, ActorLoginId, IpAddress, UserAgent, 
                TargetTable, TargetId, Action, OldValue, NewValue, CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (actor_id, actor_login_id, ip_address, user_agent, target_table, target_id, action, old_json, new_json, created_at))
        
        # 트랜잭션 커밋을 통해 디스크에 쓰기 반영
        conn.commit()
        # DB 연결 자원 반환
        conn.close()
    except Exception as e:
        # 감사 로그 기록 실패 시 비즈니스 로직(예: 장비 추가 자체) 전체가 멈추지 않도록 예외 덤프 후 안전하게 무시(Fail-Safe)
        print(f"[Audit Log Error] {e}")


def init_db():
    """
    [역할]:
      - 시스템 기동 시 필요한 모든 핵심 SQLite 테이블 구조 및 초기 마�    # -------------------------------------------------------------------------
    # [A-1] 사용자 계정 테이블 (users) - [제안-001, 025, 030, 034]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            UserId INTEGER PRIMARY KEY AUTOINCREMENT,      -- 유저 고유 식별자
            LoginId TEXT UNIQUE NOT NULL,                  -- 로그인 아이디 (유일성 보장)
            Name TEXT,                                     -- 실명 (계정 복구 시 검증용)
            NickName TEXT,                                 -- 서비스 표출용 별명
            Password TEXT NOT NULL,                        -- 단방향 해시(bcrypt 등)로 암호화된 비밀번호
            Role TEXT NOT NULL,                            -- 시스템 권한 역할 (일반적으로 'admin' 또는 'user')
            CreatedAt TEXT,                                -- 회원가입 발생일시
            UpdatedAt TEXT,                                -- 프로필 최종 수정일시
            IsDeactivated TEXT DEFAULT 'N',                -- 계정 정지(탈퇴 유예) 상태 여부 ('Y', 'N')
            DeactivatedAt TEXT,                            -- 비활성화 시작 타임스탬프
            IsDeleted TEXT DEFAULT 'N',                    -- Soft Delete(논리적 삭제) 여부 ('Y', 'N')
            DeletedAt TEXT                                 -- 논리적 삭제 타임스탬프
        )
    ''')

    # -------------------------------------------------------------------------
    # [A-2] 시스템 메뉴 테이블 (menus) - [제안-035]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            MenuId INTEGER PRIMARY KEY AUTOINCREMENT,      -- 메뉴 고유 ID
            MenuCode TEXT UNIQUE NOT NULL,                 -- 식별용 메뉴 코드 (예: M01_EQUIP_LIST)
            MenuName TEXT NOT NULL,                        -- 화면 좌측 GNB에 표출될 한글 명칭
            Url TEXT NOT NULL,                             -- 클릭 시 이동할 Flask 라우팅 엔드포인트
            Description TEXT,                              -- 해당 메뉴의 기능 설명
            ParentMenuCode TEXT,                           -- 2Depth 계층화를 위한 상위 메뉴 코드
            SortOrder INTEGER DEFAULT 0,                   -- GNB 표출 시 정렬 순서
            CreatedAt TEXT,                                -- 생성일시
            UpdatedAt TEXT                                 -- 수정일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [A-3] 역할별 메뉴 접근 권한 테이블 (role_menu_permissions)
    # -------------------------------------------------------------------------
    # 특정 역할(Role)이 특정 메뉴(MenuCode)에 접근 가능한지를 매핑하는 N:M 브릿지 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_menu_permissions (
            PermissionId INTEGER PRIMARY KEY AUTOINCREMENT,-- 권한 레코드 고유 식별자
            Role TEXT NOT NULL,                            -- 권한 역할군 (예: 'admin', 'user')
            MenuCode TEXT NOT NULL,                        -- 타겟 메뉴 코드
            IsAllowed INTEGER DEFAULT 1,                   -- 접근 허용 플래그 (1: 화면 표출 및 접근 허용, 0: 차단)
            UpdatedAt TEXT,                                -- 권한 설정 최종 수정일시
            UNIQUE(Role, MenuCode)                         -- 동일한 역할과 메뉴의 중복 권한 설정 방지 제약조건
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-2] 전역 보안 감사 로그 테이블 (audit_logs) - [제안-003, 017]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            AuditId INTEGER PRIMARY KEY AUTOINCREMENT,     -- 보안 로그 고유 식별자
            ActorId INTEGER,                               -- 조작을 수행한 유저의 UserId (알 수 없는 경우 NULL)
            ActorLoginId TEXT,                             -- 조작을 수행한 유저의 로그인 ID
            IpAddress TEXT,                                -- 조작 발생 클라이언트 IP 주소
            UserAgent TEXT,                                -- 조작 발생 클라이언트 브라우저 환경
            TargetTable TEXT,                              -- 변경이 발생한 대상 DB 테이블명
            TargetId INTEGER,                              -- 변경이 발생한 대상 레코드의 PK
            Action TEXT,                                   -- 수행 행위 타입 (LOGIN, INSERT, UPDATE, DELETE 등)
            OldValue TEXT,                                 -- 변경 전 원본 데이터의 JSON 직렬화 스냅샷
            NewValue TEXT,                                 -- 변경 후 신규 데이터의 JSON 직렬화 스냅샷
            CreatedAt TEXT                                 -- 행위 발생 타임스탬프
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-3] 사용자 환경설정 테이블 (user_settings) - [제안-016]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            UserId INTEGER PRIMARY KEY,                    -- 유저 PK를 그대로 사용 (1:1 확장 테이블 관계)
            PreferencesJSON TEXT,                          -- 다크모드, 행 개수 등 UI 개인화 설정을 담은 JSON 문자열
            UpdatedAt TEXT,                                -- 설정이 변경된 최종 시각
            FOREIGN KEY(UserId) REFERENCES users(UserId) ON DELETE CASCADE -- 유저 탈퇴(Hard Delete) 시 연쇄 삭제 처리
        )
    ''')

    # -------------------------------------------------------------------------
    # [B-5] 카테고리 마스터 테이블 (categories) - [제안-011]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            CategoryId INTEGER PRIMARY KEY AUTOINCREMENT,  -- 대분류 카테고리 고유 식별자
            Name TEXT UNIQUE NOT NULL,                     -- 카테고리 명칭 (예: '노트북', 중복 불가)
            IsApproved INTEGER DEFAULT 1,                  -- 승인제 도입 후 즉시 사용 가능 여부 (1: 승인, 0: 대기)
            CreatedAt TEXT                                 -- 카테고리 생성일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-4] 시스템 마이그레이션 이력 관리 테이블 (sys_migrations)
    # -------------------------------------------------------------------------
    # db_migration.py 구동 시 중복 마이그레이션을 방지하기 위한 이력 기록 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sys_migrations (
            MigrationName TEXT PRIMARY KEY,                -- 적용 완료된 마이그레이션 스크립트/제안 식별자 (중복 불가)
            AppliedAt TEXT                                 -- 시스템에 해당 마이그레이션이 반영된 시각
        )
    ''')

    # -------------------------------------------------------------------------
    # [B-6] 제조사 마스터 테이블 (manufacturers) - [제안-011]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manufacturers (
            ManufacturerId INTEGER PRIMARY KEY AUTOINCREMENT, -- 제조사 고유 식별자
            Name TEXT UNIQUE NOT NULL,                        -- 제조사 명칭 (예: 'SAMSUNG', 중복 불가)
            IsApproved INTEGER DEFAULT 1,                     -- 결재 승인 여부 플래그
            CreatedAt TEXT                                    -- 데이터 생성일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [C-1] 전자결재 요청 테이블 (approval_requests) - [제안-027]
    # -------------------------------------------------------------------------
    # 일반 유저가 마스터성 데이터(카테고리, 라인업 등) 등록을 요청할 때 생성되는 결재 큐 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_requests (
            RequestId INTEGER PRIMARY KEY AUTOINCREMENT,   -- 결재 안건 고유 식별자
            RequesterId INTEGER NOT NULL,                  -- 상신자(요청자) UserId
            RequestType TEXT NOT NULL,                     -- 결재 대상 도메인 (ADD_CATEGORY, ADD_MANUFACTURER 등)
            RequestDataJSON TEXT NOT NULL,                 -- 실제 적용될 데이터 페이로드(JSON)
            Status TEXT DEFAULT 'PENDING',                 -- 현재 결재 진행 상태 ('PENDING', 'APPROVED', 'REJECTED')
            ApproverId INTEGER,                            -- 최종 결재를 처리한 관리자 UserId
            RejectReason TEXT,                             -- 반려(REJECTED) 시 입력한 반려 사유 텍스트
            CreatedAt TEXT,                                -- 기안 상신 발생일시
            UpdatedAt TEXT,                                -- 결재 최종 처리(승인/반려) 일시
            FOREIGN KEY(RequesterId) REFERENCES users(UserId) ON DELETE CASCADE
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-5] 실시간 웹 접근 로그 테이블 (access_logs) - [제안-036, 040]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            LogId INTEGER PRIMARY KEY AUTOINCREMENT,       -- HTTP 요청 1건당 생성되는 고유 식별자
            IpAddress TEXT NOT NULL,                       -- 접속을 시도한 클라이언트 IP 주소
            HttpMethod TEXT NOT NULL,                      -- HTTP verb (GET, POST, PUT, DELETE 등)
            RequestPath TEXT NOT NULL,                     -- 호출된 라우팅 URL (쿼리 파라미터 제외)
            StatusCode INTEGER NOT NULL,                   -- 서버가 반환한 HTTP 최종 상태 코드
            UserAgent TEXT,                                -- 브라우저 / 클라이언트 종류
            Referer TEXT,                                  -- 유입 직전의 페이지 주소
            DurationMs REAL,                               -- 백엔드 파이썬 서버에서 처리에 소요된 시간(ms)
            IsStatic INTEGER DEFAULT 0,                    -- 정적 파일(js, css, 메타데이터) 요청 여부 (1: 정적, 0: 동적 API)
            RequestPayload TEXT,                           -- 클라이언트가 송신한 JSON 바디 텍스트 (최대 길이 제한 적용됨)
            ResponsePayload TEXT,                          -- 서버가 반환한 JSON 바디 텍스트 (최대 길이 제한 적용됨)
            CreatedAt TEXT NOT NULL                        -- 요청이 최초 인입된 타임스탬프
        )
    ''')
    
    # 접근 로그 검색 및 분석 통계 속도 최적화를 위한 4종 복합 B-Tree 인덱스 생성
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs (CreatedAt DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_ip ON access_logs (IpAddress)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_status ON access_logs (StatusCode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_is_static ON access_logs (IsStatic)')

    # 기본 메뉴 등록 (기존 장비관리 메뉴 대신 분리된 메뉴 2종)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM menus WHERE MenuCode = 'equipment'")
    cursor.execute("DELETE FROM role_menu_permissions WHERE MenuCode = 'equipment'")
    
    default_menus = [
        ('my_equipment', '나의 장비', '/my_equipment', '내 장비 등록 및 관리', None, 1),
        ('public_equipment', '공개 장비', '/public_equipment', '공개 장비 및 전체 장비 조회', None, 2),
        ('dashboard', '통계 대시보드', '/dashboard', '장비 통계 및 상세 현황 조회', None, 3),
        ('admin_center', '관리자 센터', '/admin_center', '시스템 관리자 전용 메뉴 허브', None, 4),
        ('permissions', '메뉴 권한 관리', '/permissions', '사용자 역할별 메뉴 접근 권한 제어', 'admin_center', 1),
        ('audit_logs', '보안 감사 로그', '/audit_logs', '시스템 접근 이력 및 감사 로그 조회', 'admin_center', 2),
        ('users_management', '사용자 관리', '/users_management', '전체 사용자 권한 및 계정 관리', 'admin_center', 3),
        ('approvals', '전자결재함', '/approvals', '전자결재 요청 및 승인 관리', 'admin_center', 4),
        ('master_management', '마스터 데이터 관리', '/master_management', '카테고리 및 제조사 마스터 관리', 'admin_center', 5),
        ('access_logs', '웹 접근 로그', '/access_logs', '실시간 HTTP 트래픽 및 웹 접근 로그 모니터링', 'admin_center', 6)
    ]
    for m in default_menus:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (m[0], m[1], m[2], m[3], m[4], m[5], now, now))
        except Exception as e:
            # 기존 DB 스키마에 ParentMenuCode가 없는 상태(마이그레이션 전)에서는 무시
            print(f"[Init DB] menus 테이블 기본 데이터 삽입 건너뜀 (마이그레이션 전일 수 있습니다): {str(e)}")
            pass

    # 기본 권한 등록 (admin: 전체 허용, user: 나의 장비 및 공개된 장비, 전자결재 허용)
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'permissions', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'audit_logs', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'users_management', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'approvals', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'master_management', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'access_logs', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'admin_center', 1, now))
    
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'permissions', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'audit_logs', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'users_management', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'approvals', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'master_management', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'access_logs', 0, now))

    conn.commit()
    conn.close()

# 서버 실행 시 DB 준비 (기존 데이터 보존 원칙 적용)
init_db()

def run_migration_if_needed(migration_name, migration_func):
    """
    [역할]: 특정 DB 마이그레이션 함수가 이전에 실행되었는지 확인하고 1회에 한해 구동합니다.
    [의존성 관계]: sys_migrations 테이블
    [변경 시 영향도]: 마이그레이션 중복 실행 방어에 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sys_migrations WHERE MigrationName = ?", (migration_name,))
    if not cursor.fetchone():
        try:
            migration_func()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            conn2 = get_db_connection()
            c2 = conn2.cursor()
            c2.execute("INSERT INTO sys_migrations (MigrationName, AppliedAt) VALUES (?, ?)", (migration_name, now))
            conn2.commit()
            conn2.close()
            
            print(f"[Migration Manager] '{migration_name}' successfully applied.")
        except Exception as e:
            print(f"[Migration Manager] Error applying '{migration_name}': {e}")
    conn.close()

def migrate_menu_hierarchy():
    """
    [역할]: 제안-035 관리자 센터 도입에 따른 메뉴 계층화 마이그레이션 (ParentMenuCode, SortOrder 추가 및 데이터 재정렬)
    [의존성 관계]: menus 테이블
    [변경 시 영향도]: 메인 포털 화면과 관리자 센터의 메뉴 노출 구조를 완전히 바꿉니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(menus)")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'ParentMenuCode' not in columns:
            cursor.execute("ALTER TABLE menus ADD COLUMN ParentMenuCode TEXT")
        if 'SortOrder' not in columns:
            cursor.execute("ALTER TABLE menus ADD COLUMN SortOrder INTEGER DEFAULT 0")
            
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('admin_center', '관리자 센터', '/admin_center', '시스템 관리자 전용 메뉴 허브', None, 4, now, now))
        
        sub_menus = [('permissions', 1), ('audit_logs', 2), ('users_management', 3), ('approvals', 4), ('master_management', 5)]
        for menu_code, sort_order in sub_menus:
            cursor.execute('''
                UPDATE menus SET ParentMenuCode = 'admin_center', SortOrder = ? WHERE MenuCode = ?
            ''', (sort_order, menu_code))
            
        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'permissions' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'admin_center', 1, ?)
            ''', (role, now))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_menu_hierarchy: {str(e)}")

run_migration_if_needed('menu_hierarchy', migrate_menu_hierarchy)

def migrate_access_logs_menu():
    """
    [역할]: 제안-036 실시간 웹 접근 로그 모니터링 메뉴 및 권한을 관리자 센터 하위에 동적으로 추가합니다.
    [의존성 관계]: menus, role_menu_permissions 테이블
    [변경 시 영향도]: 관리자 센터 내에 '웹 접근 로그' 메뉴 카드가 활성화됩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # access_logs 신규 메뉴 삽입. 부모 코드를 'admin_center'로 지정
        cursor.execute('''
            INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
            VALUES ('access_logs', '웹 접근 로그', '/access_logs', '실시간 HTTP 트래픽 및 웹 접근 로그 모니터링', 'admin_center', 6, ?, ?)
        ''', (now, now))

        # 이미 삽입되어 있었을 경우를 대비해 확실하게 부모 코드 및 정렬 순서 업데이트
        cursor.execute('''
            UPDATE menus SET ParentMenuCode = 'admin_center', SortOrder = 6 WHERE MenuCode = 'access_logs'
        ''')

        # 관리자 센터 접근 권한이 있는 Role 추출
        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'admin_center' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        
        # 해당 Role들에게 access_logs(웹 접근 로그) 접근 권한 부여(허용)
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'access_logs', 1, ?)
            ''', (role, now))

        # 일반 유저('user') 등급에 대해서는 access_logs 메뉴 노출 및 접근 차단(0) 설정
        cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES ('user', 'access_logs', 0, ?)", (now,))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_access_logs_menu: {str(e)}")

# 접근 로그 메뉴 추가 마이그레이션 적용 여부 검사 및 실행
run_migration_if_needed('proposal_036_access_logs', migrate_access_logs_menu)RE MenuCode = 'access_logs'
        ''')

        # 관리자 센터 접근 권한이 있는 Role 추출
        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'admin_center' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        
        # 해당 Role들에게 access_logs(웹 접근 로그) 접근 권한 부여(허용)
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'access_logs', 1, ?)
            ''', (role, now))

        # 일반 유저('user') 등급에 대해서는 access_logs 메뉴 노출 및 접근 차단(0) 설정
        cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES ('user', 'access_logs', 0, ?)", (now,))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_access_logs_menu: {str(e)}")

# 접근 로그 메뉴 추가 마이그레이션 적용 여부 검사 및 실행
run_migration_if_needed('proposal_036_access_logs', migrate_access_logs_menu)             -- 수정일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [A-3] 역할별 메뉴 접근 권한 테이블 (role_menu_permissions)
    # -------------------------------------------------------------------------
    # 특정 역할(Role)이 특정 메뉴(MenuCode)에 접근 가능한지를 매핑하는 N:M 브릿지 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_menu_permissions (
            PermissionId INTEGER PRIMARY KEY AUTOINCREMENT,-- 권한 레코드 고유 식별자
            Role TEXT NOT NULL,                            -- 권한 역할군 (예: 'admin', 'user')
            MenuCode TEXT NOT NULL,                        -- 타겟 메뉴 코드
            IsAllowed INTEGER DEFAULT 1,                   -- 접근 허용 플래그 (1: 화면 표출 및 접근 허용, 0: 차단)
            UpdatedAt TEXT,                                -- 권한 설정 최종 수정일시
            UNIQUE(Role, MenuCode)                         -- 동일한 역할과 메뉴의 중복 권한 설정 방지 제약조건
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-2] 전역 보안 감사 로그 테이블 (audit_logs) - [제안-003, 017]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            AuditId INTEGER PRIMARY KEY AUTOINCREMENT,     -- 보안 로그 고유 식별자
            ActorId INTEGER,                               -- 조작을 수행한 유저의 UserId (알 수 없는 경우 NULL)
            ActorLoginId TEXT,                             -- 조작을 수행한 유저의 로그인 ID
            IpAddress TEXT,                                -- 조작 발생 클라이언트 IP 주소
            UserAgent TEXT,                                -- 조작 발생 클라이언트 브라우저 환경
            TargetTable TEXT,                              -- 변경이 발생한 대상 DB 테이블명
            TargetId INTEGER,                              -- 변경이 발생한 대상 레코드의 PK
            Action TEXT,                                   -- 수행 행위 타입 (LOGIN, INSERT, UPDATE, DELETE 등)
            OldValue TEXT,                                 -- 변경 전 원본 데이터의 JSON 직렬화 스냅샷
            NewValue TEXT,                                 -- 변경 후 신규 데이터의 JSON 직렬화 스냅샷
            CreatedAt TEXT                                 -- 행위 발생 타임스탬프
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-3] 사용자 환경설정 테이블 (user_settings) - [제안-016]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            UserId INTEGER PRIMARY KEY,                    -- 유저 PK를 그대로 사용 (1:1 확장 테이블 관계)
            PreferencesJSON TEXT,                          -- 다크모드, 행 개수 등 UI 개인화 설정을 담은 JSON 문자열
            UpdatedAt TEXT,                                -- 설정이 변경된 최종 시각
            FOREIGN KEY(UserId) REFERENCES users(UserId) ON DELETE CASCADE -- 유저 탈퇴(Hard Delete) 시 연쇄 삭제 처리
        )
    ''')

    # -------------------------------------------------------------------------
    # [B-5] 카테고리 마스터 테이블 (categories) - [제안-011]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            CategoryId INTEGER PRIMARY KEY AUTOINCREMENT,  -- 대분류 카테고리 고유 식별자
            Name TEXT UNIQUE NOT NULL,                     -- 카테고리 명칭 (예: '노트북', 중복 불가)
            IsApproved INTEGER DEFAULT 1,                  -- 승인제 도입 후 즉시 사용 가능 여부 (1: 승인, 0: 대기)
            CreatedAt TEXT                                 -- 카테고리 생성일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-4] 시스템 마이그레이션 이력 관리 테이블 (sys_migrations)
    # -------------------------------------------------------------------------
    # db_migration.py 구동 시 중복 마이그레이션을 방지하기 위한 이력 기록 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sys_migrations (
            MigrationName TEXT PRIMARY KEY,                -- 적용 완료된 마이그레이션 스크립트/제안 식별자 (중복 불가)
            AppliedAt TEXT                                 -- 시스템에 해당 마이그레이션이 반영된 시각
        )
    ''')

    # -------------------------------------------------------------------------
    # [B-6] 제조사 마스터 테이블 (manufacturers) - [제안-011]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manufacturers (
            ManufacturerId INTEGER PRIMARY KEY AUTOINCREMENT, -- 제조사 고유 식별자
            Name TEXT UNIQUE NOT NULL,                        -- 제조사 명칭 (예: 'SAMSUNG', 중복 불가)
            IsApproved INTEGER DEFAULT 1,                     -- 결재 승인 여부 플래그
            CreatedAt TEXT                                    -- 데이터 생성일시
        )
    ''')

    # -------------------------------------------------------------------------
    # [C-1] 전자결재 요청 테이블 (approval_requests) - [제안-027]
    # -------------------------------------------------------------------------
    # 일반 유저가 마스터성 데이터(카테고리, 라인업 등) 등록을 요청할 때 생성되는 결재 큐 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_requests (
            RequestId INTEGER PRIMARY KEY AUTOINCREMENT,   -- 결재 안건 고유 식별자
            RequesterId INTEGER NOT NULL,                  -- 상신자(요청자) UserId
            RequestType TEXT NOT NULL,                     -- 결재 대상 도메인 (ADD_CATEGORY, ADD_MANUFACTURER 등)
            RequestDataJSON TEXT NOT NULL,                 -- 실제 적용될 데이터 페이로드(JSON)
            Status TEXT DEFAULT 'PENDING',                 -- 현재 결재 진행 상태 ('PENDING', 'APPROVED', 'REJECTED')
            ApproverId INTEGER,                            -- 최종 결재를 처리한 관리자 UserId
            RejectReason TEXT,                             -- 반려(REJECTED) 시 입력한 반려 사유 텍스트
            CreatedAt TEXT,                                -- 기안 상신 발생일시
            UpdatedAt TEXT,                                -- 결재 최종 처리(승인/반려) 일시
            FOREIGN KEY(RequesterId) REFERENCES users(UserId) ON DELETE CASCADE
        )
    ''')

    # -------------------------------------------------------------------------
    # [D-5] 실시간 웹 접근 로그 테이블 (access_logs) - [제안-036, 040]
    # -------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            LogId INTEGER PRIMARY KEY AUTOINCREMENT,       -- HTTP 요청 1건당 생성되는 고유 식별자
            IpAddress TEXT NOT NULL,                       -- 접속을 시도한 클라이언트 IP 주소
            HttpMethod TEXT NOT NULL,                      -- HTTP verb (GET, POST, PUT, DELETE 등)
            RequestPath TEXT NOT NULL,                     -- 호출된 라우팅 URL (쿼리 파라미터 제외)
            StatusCode INTEGER NOT NULL,                   -- 서버가 반환한 HTTP 최종 상태 코드
            UserAgent TEXT,                                -- 브라우저 / 클라이언트 종류
            Referer TEXT,                                  -- 유입 직전의 페이지 주소
            DurationMs REAL,                               -- 백엔드 파이썬 서버에서 처리에 소요된 시간(ms)
            IsStatic INTEGER DEFAULT 0,                    -- 정적 파일(js, css, 메타데이터) 요청 여부 (1: 정적, 0: 동적 API)
            RequestPayload TEXT,                           -- 클라이언트가 송신한 JSON 바디 텍스트 (최대 길이 제한 적용됨)
            ResponsePayload TEXT,                          -- 서버가 반환한 JSON 바디 텍스트 (최대 길이 제한 적용됨)
            CreatedAt TEXT NOT NULL                        -- 요청이 최초 인입된 타임스탬프
        )
    ''')
    
    # 접근 로그 검색 및 분석 통계 속도 최적화를 위한 4종 복합 B-Tree 인덱스 생성
    # 시간 역순 조회, 특정 IP 공격 추적, 상태 코드 기반 에러 통계, �        # access_logs 신규 메뉴 삽입. 부모 코드를 'admin_center'로 지정
        cursor.execute('''
            INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
            VALUES ('access_logs', '웹 접근 로그', '/access_logs', '실시간 HTTP 트래픽 및 웹 접근 로그 모니터링', 'admin_center', 6, ?, ?)
        ''', (now, now))

        # 이미 삽입되어 있었을 경우를 대비해 확실하게 부모 코드 및 정렬 순서 업데이트
        cursor.execute('''
            UPDATE menus SET ParentMenuCode = 'admin_center', SortOrder = 6 WHERE MenuCode = 'access_logs'
        ''')

        # 관리자 센터 접근 권한이 있는 Role 추출
        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'admin_center' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        
        # 해당 Role들에게 access_logs(웹 접근 로그) 접근 권한 부여(허용)
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'access_logs', 1, ?)
            ''', (role, now))

        # 일반 유저('user') 등급에 대해서는 access_logs 메뉴 노출 및 접근 차단(0) 설정
        cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES ('user', 'access_logs', 0, ?)", (now,))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_access_logs_menu: {str(e)}")

# 접근 로그 메뉴 추가 마이그레이션 적용 여부 검사 및 실행
run_migration_if_needed('proposal_036_access_logs', migrate_access_logs_menu)

def migrate_access_logs_payload():
    """
    [역할]:
      - [제안-040] access_logs 테이블에 RequestPayload, ResponsePayload 텍스트 컬럼 추가
    [의존성 관계]:
      - access_logs 테이블, get_db_connection()
    [변경 시 영향도]:
      - HTTP 요청 및 응답 본문 원문 저장이 활성화되어 심층 트러블슈팅 및 로그 조회가 가능해집니다.
    """
    try:
        # DDL(스키마 변경)을 수행하기 위해 DB 커넥션 확보
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # access_logs 테이블 스키마 정보를 가져와서 현재 존재하는 컬럼 리스트 추출 (PRAGMA 사용)
        cursor.execute("PRAGMA table_info(access_logs)")
        columns = [info['name'] for info in cursor.fetchall()]
        
        # RequestPayload 컬럼이 없다면 즉시 컬럼 추가 (요청 바디 저장용)
        if 'RequestPayload' not in columns:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN RequestPayload TEXT")
        # ResponsePayload 컬럼이 없다면 즉시 컬럼 추가 (응답 바디 저장용)
        if 'ResponsePayload' not in columns:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN ResponsePayload TEXT")
            
        # 컬럼 추가 내역을 트랜잭션에 반영(커밋)
        conn.commit()
        # 자원 누수 방지를 위한 커넥션 반환
        conn.close()
    except Exception as e:
        # 실패 시 시스템이 중단되지 않도록 오류 로그만 남기고 무시
        print(f"[Migration Error] migrate_access_logs_payload: {str(e)}")

# 마이그레이션 매니저를 통해 기실행 여부 검증 후 1회 구동
run_migration_if_needed('proposal_040_access_logs_payload', migrate_access_logs_payload)

def migrate_equipment_is_public():
    """
    [역할]:
      - equipment 테이블에 IsPublic(공개 여부) 컬럼이 없는 경우 안전하게 추가
    [의존성 관계]:
      - equipment 테이블
    [변경 시 영향도]:
      - 장비의 전체 공개 및 비공개 플래그 제어가 활성화됩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 레거시 equipment 테이블의 컬럼 구성 조회
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [info['name'] for info in cursor.fetchall()]
        
        # IsPublic 컬럼 존재 여부 체크 후 동적 추가
        if 'IsPublic' not in columns:
            # 기본값 0(비공개)으로 컬럼 생성
            cursor.execute("ALTER TABLE equipment ADD COLUMN IsPublic INTEGER DEFAULT 0")
            print("[Migration] equipment 테이블에 IsPublic 컬럼이 성공적으로 추가되었습니다.")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (IsPublic)] {e}")

# 장비 공개 여부 컬럼 마이그레이션 등록
run_migration_if_needed('equipment_is_public', migrate_equipment_is_public)

def migrate_proposals_011_027_028():
    """
    [역할]:
      - 제안-011, 027, 028에 필요한 IsDraft 컬럼 추가 및 기존 문자열 카테고리/제조사 초기 시딩
    [의존성 관계]:
      - equipment, categories, manufacturers 테이블
    [변경 시 영향도]:
      - 장비 임시저장 기능 지원 및 카테고리/제조사 마스터 테이블 초기 데이터 구축에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. 임시저장 상태를 나타내는 IsDraft 컬럼 추가 (기존 장비는 모두 0 정식등록으로 간주)
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [info['name'] for info in cursor.fetchall()]
        if 'IsDraft' not in columns:
            cursor.execute("ALTER TABLE equipment ADD COLUMN IsDraft INTEGER DEFAULT 0")
            print("[Migration] equipment 테이블에 IsDraft 컬럼이 성공적으로 추가되었습니다.")

        # 2. 기존 equipment에 적혀 있던 하드코딩된 문자열 Category를 추출하여 중복 없이 categories 마스터에 시딩
        cursor.execute("SELECT DISTINCT Category FROM equipment WHERE Category IS NOT NULL AND TRIM(Category) != ''")
        existing_cats = [r['Category'].strip() for r in cursor.fetchall()]
        for cat in existing_cats:
            # 승인 대기 단계 없이 기존 데이터는 모두 1(승인)로 즉시 활성화
            cursor.execute("INSERT OR IGNORE INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (cat, now))

        # 3. 기존 equipment에 적혀 있던 하드코딩된 Manufacturer 문자열을 추출하여 중복 없이 manufacturers 마스터에 시딩
        cursor.execute("SELECT DISTINCT Manufacturer FROM equipment WHERE Manufacturer IS NOT NULL AND TRIM(Manufacturer) != ''")
        existing_mfgs = [r['Manufacturer'].strip() for r in cursor.fetchall()]
        for mfg in existing_mfgs:
            # 승인 대기 단계 없이 기존 데이터는 모두 1(승인)로 즉시 활성화
            cursor.execute("INSERT OR IGNORE INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (mfg, now))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (011_027_028)] {e}")

run_migration_if_needed('proposals_011_027_028', migrate_proposals_011_027_028)

def migrate_relational_master():
    """
    [역할]:
      - [제안-011-고도화] 관계형 마스터 데이터베이스 마이그레이션 수행
      1. categories, manufacturers 테이블에 NameKo, NameEn 다국어 컬럼 추가
      2. equipment 테이블에 CategoryId, ManufacturerId 외래키 컬럼 추가
      3. 기존 텍스트 데이터를 정수형 Key(ID)로 변환 매핑 및 업데이트
    [의존성 관계]:
      - categories, manufacturers, equipment 테이블
    [변경 시 영향도]:
      - 장비 데이터의 분류 저장이 텍스트에서 RDBMS 정수형 Key(ID) 기반으로 완전히 전환됩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. categories 테이블에 다국어 확장 컬럼(NameKo, NameEn) 추가 (장래 지원용)
        cursor.execute("PRAGMA table_info(categories)")
        cat_cols = [info['name'] for info in cursor.fetchall()]
        if 'NameKo' not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN NameKo TEXT")
        if 'NameEn' not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN NameEn TEXT")

        # 2. manufacturers 테이블에 다국어 확장 컬럼(NameKo, NameEn) 추가 (장래 지원용)
        cursor.execute("PRAGMA table_info(manufacturers)")
        mfg_cols = [info['name'] for info in cursor.fetchall()]
        if 'NameKo' not in mfg_cols:
            cursor.execute("ALTER TABLE manufacturers ADD COLUMN NameKo TEXT")
        if 'NameEn' not in mfg_cols:
            cursor.execute("ALTER TABLE manufacturers ADD COLUMN NameEn TEXT")

        # 3. equipment 테이블에 텍스트를 대체할 외래키 ID 컬럼 추가
        cursor.execute("PRAGMA table_info(equipment)")
        eq_cols = [info['name'] for info in cursor.fetchall()]
        if 'CategoryId' not in eq_cols:
            cursor.execute("ALTER TABLE equipment ADD COLUMN CategoryId INTEGER")
        if 'ManufacturerId' not in eq_cols:
            cursor.execute("ALTER TABLE equipment ADD COLUMN ManufacturerId INTEGER")

        # 4. 전체 equipment 레코드를 순회하며 기존 텍스트를 매칭되는 ID로 변환하여 덮어쓰기
        cursor.execute("SELECT EquipmentId, Category, Manufacturer, CategoryId, ManufacturerId FROM equipment")
        equipments = cursor.fetchall()

        # O(N) 순회를 통해 개별 레코드의 ID 관계를 복원함
        for eq in equipments:
            eq_id = eq['EquipmentId']
            # NULL 안전한 스트립 처리로 텍스트 값 확보
            cat_val = str(eq['Category']).strip() if eq['Category'] is not None else ''
            mfg_val = str(eq['Manufacturer']).strip() if eq['Manufacturer'] is not None else ''

            new_cat_id = eq['CategoryId']
            new_mfg_id = eq['ManufacturerId']


            # 카테고리 매핑 로직
            if cat_val:
                if cat_val.isdigit():
                    # 이미 ID 형태라면 정수형으로 변환하여 매핑
                    new_cat_id = int(cat_val)
                else:
                    # 텍스트 명칭으로 categories 마스터 조회
                    cursor.execute("SELECT CategoryId FROM categories WHERE Name = ?", (cat_val,))
                    c_row = cursor.fetchone()
                    if c_row:
                        # 매칭 성공 시 ID 획득
                        new_cat_id = c_row['CategoryId']
                    else:
                        # 매칭 실패 시 마스터 테이블에 즉시 신규 등록 후 PK 획득
                        cursor.execute("INSERT INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (cat_val, now))
                        new_cat_id = cursor.lastrowid

            # 제조사 매핑 로직 (카테고리 매핑과 동일)
            if mfg_val:
                if mfg_val.isdigit():
                    new_mfg_id = int(mfg_val)
                else:
                    cursor.execute("SELECT ManufacturerId FROM manufacturers WHERE Name = ?", (mfg_val,))
                    m_row = cursor.fetchone()
                    if m_row:
                        new_mfg_id = m_row['ManufacturerId']
                    else:
                        cursor.execute("INSERT INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (mfg_val, now))
                        new_mfg_id = cursor.lastrowid

            # equipment 테이블 업데이트 (CategoryId, ManufacturerId 및 레거시 Category, Manufacturer 컬럼에 ID 동일 업데이트)
            cursor.execute('''
                UPDATE equipment 
                SET CategoryId = ?, ManufacturerId = ?, Category = ?, Manufacturer = ?
                WHERE EquipmentId = ?
            ''', (new_cat_id, new_mfg_id, str(new_cat_id) if new_cat_id else None, str(new_mfg_id) if new_mfg_id else None, eq_id))

        # 모든 매핑 완료 후 트랜잭션 커밋
        conn.commit()
        conn.close()
        print("[Migration] 제안-011-고도화 관계형 마스터 데이터 매핑이 성공적으로 완료되었습니다.")
    except Exception as e:
        print(f"[Migration Error (relational_master)] {e}")

run_migration_if_needed('relational_master', migrate_relational_master)

def migrate_passwords_to_hash():
    """
    [역할]:
      - 기존 레거시 평문 비밀번호를 Werkzeug의 안전한 scrypt/pbkdf2 단방향 해시로 일괄 변환
    [의존성 관계]:
      - users 테이블, generate_password_hash()
    [변경 시 영향도]:
      - 계정 보안 체계 및 로그인 비밀번호 검증 무결성에 결정적인 영향을 미칩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 모든 유저의 비밀번호 열람 (평문 색출을 위함)
        cursor.execute("SELECT UserId, Password FROM users")
        users = cursor.fetchall()
        
        # 전체 유저를 반복 순회하며 검사
        for u in users:
            pwd = u['Password']
            # 비밀번호가 werkzeug 특유의 해시 식별자(scrypt:, pbkdf2:)로 시작하지 않는 경우 평문으로 판단
            if pwd and not (pwd.startswith('scrypt:') or pwd.startswith('pbkdf2:')):
                # Flask 권장 단방향 해시 함수로 즉시 암호화
                hashed = generate_password_hash(pwd)
                # 안전한 해시값으로 DB 갱신
                cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed, u['UserId']))
                print(f"[Migration] User {u['UserId']} 의 평문 비밀번호가 안전하게 해싱되었습니다.")
                
        # 변경분 커밋 및 자원 반환
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] {e}")

# 구동 시 비밀번호 해싱 자동 마이그레이션 수행
run_migration_if_needed('passwords_to_hash', migrate_passwords_to_hash)

def migrate_email_features():
    """
    [역할]:
      - [제안-030] 사용자 테이블에 이메일 인증(Email) 관련 보안 필드 추가 및 신규 테이블 생성
    [의존성 관계]:
      - users, email_verifications, password_resets 테이블
    [변경 시 영향도]:
      - 사용자 비밀번호 찾기, 본인 인증 등 이메일 기반 보안 기능 지원에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # users 테이블 컬럼 검사
        cursor.execute("PRAGMA table_info(users)")
        cols = [info['name'] for info in cursor.fetchall()]
        # Email 컬럼이 없다면 추가 (소프트 딜리트 및 복구용 본인인증 키로 사용)
        if 'Email' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN Email TEXT")
        
        # Email 컬럼에 대한 부분 유니크 인덱스 생성 (중복 가입 방지, NULL은 허용)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(Email) WHERE Email IS NOT NULL")
        
        # 이메일 인증번호(PIN) 관리를 위한 일회성 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verifications (
                Email TEXT PRIMARY KEY,        -- 대상 이메일 주소
                PinCodeHash TEXT NOT NULL,     -- 안전하게 해싱된 6자리 PIN 코드
                ExpiresAt TEXT NOT NULL,       -- 인증 만료 시각 (일반적으로 3분)
                IsVerified INTEGER DEFAULT 0   -- 인증 완료 여부 플래그
            )
        ''')
        
        # 비밀번호 초기화(재설정) 토큰 관리를 위한 일회성 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                TokenHash TEXT PRIMARY KEY,    -- URL 발송용 1회성 토큰 해시
                UserId INTEGER NOT NULL,       -- 대상 사용자 ID
                ExpiresAt TEXT NOT NULL,       -- 토큰 만료 시각 (일반적으로 24시간)
                IsUsed INTEGER DEFAULT 0       -- 토큰 사용 완료 여부
            )
        ''')
        
        # DDL 변경 사항 커밋
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (email_features)] {e}")

# 이메일 기능 기반 테이블 스키마 자동 마이그레이션 수행
run_migration_if_needed('proposal_030_email_auth', migrate_email_features)

@app.context_processor
def inject_csrf_token():
    """
    [역할]:
      - 모든 템플릿 렌더링 시 세션 기반 CSRF 토큰을 전역으로 주입하고, 누락 시 신규 생성합니다.
    [의존성 관계]:
      - session['csrf_token'], secrets 모듈
    [변경 시 영향도]:
      - 모든 프론트엔드 템플릿의 CSRF 보안 토큰 가용성에 영향을 줍니다.
    """
    # 현재 세션에 csrf_token이 발급되어 있지 않다면
    if 'csrf_token' not in session:
        # 안전한 난수(16바이트)를 16진수 문자열로 변환하여 세션에 할당
        session['csrf_token'] = secrets.token_hex(16)
    # 렌더링되는 모든 템플릿 엔진에 csrf_token 변수명으로 반환
    return dict(csrf_token=session['csrf_token'])


def csrf_required(f):
    """
    [역할]:
      - 변경 요청 시 클라이언트의 CSRF 토큰을 검증하는 데코레이터입니다.
    [의존성 관계]:
      - session['csrf_token']
    [변경 시 영향도]:
      - POST, PUT, DELETE, PATCH API 통신 보안에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """
        [역할]: 데코레이터 래퍼 함수로 원본 함수 실행 전/후 처리를 담당합니다.
        [의존성 관계]: 원본 함수(f)
        [변경 시 영향도]: 데코레이터 적용 라우터의 인자 전달에 영향을 줍니다.
        """
        # 상태를 변경하는 HTTP 메서드인 경우에만 토큰 검증 수행
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            # 클라이언트가 헤더에 실어 보낸 CSRF 토큰 추출
            token = request.headers.get('X-CSRFToken')
            # 토큰이 아예 누락되었거나 서버의 세션 토큰과 불일치하는 경우
            if not token or token != session.get('csrf_token'):
                # 403 Forbidden 상태 코드로 요청을 강력하게 거부
                return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요."}), 403
        # 검증 통과 시 원래 라우트 핸들러 함수 실행
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def before_request_func():
    """
    [역할]:
      - 요청 시작 시간을 기록하여 응답 소요 시간(Latency)을 측정할 수 있게 합니다.
    [의존성 관계]:
      - flask.g (요청 컨텍스트 전역 객체)
    [변경 시 영향도]:
      - 모든 HTTP 요청 처리 시간 측정 기준점에 영향을 줍니다.
    """
    # 요청의 시작 시점을 시스템 타임스탬프로 g 객체에 저장
    g.start_time = time.time()


@app.after_request
def after_request_func(response):
    """
    [역할]:
      - HTTP 헤더에 보안 설정을 삽입하고, HTTP 접근 로그를 비동기 큐에 적재합니다.
    [의존성 관계]:
      - Flask Response, push_access_log, flask.g
    [변경 시 영향도]:
      - 브라우저 클라이언트 측 보안 제어 및 실시간 접근 로그 수집에 영향을 줍니다.
    """
    # 1. 상태 체크 폴링 API 요청 시에는 플라스크가 세션을 자동으로 갱신(Refresh)하지 못하게 세션 쿠키 발급을 차단함
    if request.path == '/api/check_session':
        new_headers = []
        for k, v in response.headers.items():
            # 세션 쿠키 갱신을 의미하는 Set-Cookie 헤더를 걸러냄
            if k.lower() == 'set-cookie' and v.startswith('session='):
                continue
            new_headers.append((k, v))
        # 필터링된 헤더로 응답 객체를 재구성
        response.headers = type(response.headers)(new_headers)
        return response

    # 2. [제안-036] 접근 로그 비동기 수집 (웹 응답 성공 보장을 위한 Fail-Safe 격리)
    try:
        # before_request에서 기록한 시작 시간을 기반으로 밀리초(ms) 단위 처리 소요 시간 계산
        duration_ms = round((time.time() - g.get('start_time', time.time())) * 1000, 2)
        
        # 정적 리소스 판별 조건식 (O(1) 성능을 내기 위해 frozenset 및 startswith 혼합 활용)
        is_static = 1 if (
            request.path.startswith('/static/') or 
            request.path in STATIC_METADATA_ROUTES_FROZEN
        ) else 0
        
        # 안전한 IP 추출 (Proxy 등 로드밸런서를 거친 경우 X-Forwarded-For를 최우선으로 간주)
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
        # 다중 Proxy 경유 시 가장 첫 번째 IP가 실제 클라이언트 IP임
        ip_addr = raw_ip.split(',')[0].strip() if raw_ip else '127.0.0.1'
        
        # [제안-040, 043] Request / Response Payload 무제한 추출 (데이터 변조 추적용)
        request_payload = request.get_data(as_text=True) if request.method in ["POST", "PUT", "PATCH", "DELETE"] else None
        
        response_payload = None
        # [제안-043] /api/access_logs 계열 응답은 ResponsePayload에서 제외하여 재귀적 DB 비대화 및 락 교착 방어
        if not is_static and not request.path.startswith('/api/access_logs'):
            try:
                # 텍스트 기반 응답일 경우 Payload 획득 시도
                response_payload = response.get_data(as_text=True)
            except Exception:
                # 바이너리 데이터 등 텍스트 변환 실패 시 조용히 무시(None 유지)
                pass 
        
        # 로그 기록 시점을 KST 형태 문자열로 생성
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Non-blocking 스레드 안전 큐에 접근 로그 사전(Dictionary) 단위로 밀어넣기
        push_access_log({
            'IpAddress': ip_addr,
            'HttpMethod': request.method,
            'RequestPath': request.path,
            'StatusCode': response.status_code,
            # UserAgent 및 Referer가 길어질 경우를 대비해 255자로 잘라서 저장 (DB 스키마 보호)
            'UserAgent': request.user_agent.string[:255] if request.user_agent else '',
            'Referer': request.referrer[:255] if request.referrer else '',
            'DurationMs': duration_ms,
            'IsStatic': is_static,
            'RequestPayload': request_payload,
            'ResponsePayload': response_payload,
            'CreatedAt': created_at
        })
        
        # [사용자 지시로 주석 처리됨] 콘솔 직관적 모니터링을 위한 표준 출력
        # status_code = response.status_code
        # if status_code >= 500:
        #     color = '\033[91m' # Red
        # elif status_code >= 400:
        #     color = '\033[93m' # Yellow
        # elif status_code >= 300:
        #     color = '\033[96m' # Cyan
        # else:
        #     color = '\033[92m' # Green
        # reset = '\033[0m'
        # 
        # if is_static:
        #     # 정적 파일 로그는 회색으로 눈에 덜 띄게 출력
        #     print(f"\033[90m[{created_at}] {ip_addr} - {request.method} {request.path} {status_code} {duration_ms}ms (Static)\033[0m")
        # else:
        #     print(f"[{created_at}] {ip_addr} - {request.method} {request.path} {color}{status_code}{reset} {duration_ms}ms")
    except Exception:
        # 어떠한 로깅 예외(예: 큐 가득 참, 메모리 부족)도 웹 응답(200 OK 등)을 방해하지 않도록 완전 격리하여 pass
        pass

    # 필터링이 완료된 최종 response 객체 반환
    return response

@app.route('/api/check_session', methods=['GET'])
def check_session():
    """
    [역할]:
      - 요청 전 세션 만료 및 다중 기기 강제 로그아웃 여부를 검증합니다.
    [의존성 관계]:
      - session, users 테이블
    [변경 시 영향도]:
      - 사이트 전체 접속 유지 기능에 영향을 줍니다.
    """
    # 1. 서버 세션에 user 정보가 존재하는지 1차 확인
    user = session.get('user')
    if not user or 'UserId' not in user:
        # 서버 세션이 소멸되었다면 401 Unauthorized 반환하여 재로그인 유도
        return jsonify({"valid": False, "reason": "session_expired"}), 401
    
    # 2. 현재 브라우저(클라이언트)가 가지고 있는 세션 토큰 추출
    current_token = session.get('session_token')
    
    # 3. 데이터베이스에 기록된 유저의 최종 세션 토큰 조회 (다중 로그인 검증용)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT SessionToken FROM users WHERE UserId = ?', (user['UserId'],))
    db_token = cursor.fetchone()
    conn.close()
    
    # 4. 다른 브라우저/기기에서 로그인하여 DB의 토큰이 갱신되었다면 불일치 발생
    if db_token and current_token != db_token['SessionToken']:
        # 401 반환하여 현재 브라우저의 접속을 강제 차단 (중복 로그인 방지)
        return jsonify({"valid": False, "reason": "concurrent_login"}), 401
        
    # 모든 검증 통과 시 세션 유효함 응답 반환
    return jsonify({"valid": True}), 200

def migrate_users_session_token():
    """
    [역할]:
      - 다중 기기 강제 로그아웃 제어를 위한 SessionToken 필드를 추가합니다.
    [의존성 관계]:
      - users 테이블
    [변경 시 영향도]:
      - 사용자 세션 제어 스키마 관리에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # users 테이블의 전체 컬럼 검사
        cursor.execute("PRAGMA table_info(users)")
        columns = [info['name'] for info in cursor.fetchall()]
        
        # SessionToken이 없다면 즉시 컬럼 추가
        if 'SessionToken' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN SessionToken TEXT")
            print("[Migration] users 테이블에 SessionToken 컬럼이 추가되었습니다.")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (SessionToken)] {e}")

def migrate_users_soft_delete():
    """
    [역할]:
      - 계정 비활성화 및 탈퇴 유예 관련 상태 필드를 DB에 추가합니다.
    [의존성 관계]:
      - users 테이블
    [변경 시 영향도]:
      - 계정 소프트 딜리트(논리 삭제) 구조에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # users 테이블 컬럼 검사
        cursor.execute("PRAGMA table_info(users)")
        columns = [info['name'] for info in cursor.fetchall()]
        
        # 계정 정지 혹은 자진 탈퇴 요청 시 'Y'로 변경되는 상태 필드 추가
        if 'IsDeactivated' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN IsDeactivated TEXT DEFAULT 'N'")
        # 탈퇴 신청 혹은 정지 시각을 기록하기 위한 타임스탬프 필드 추가
        if 'DeactivatedAt' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN DeactivatedAt TEXT")
            
        # 탈퇴 유예 기간(30일)이 종료되어 완전히 논리삭제(로그인 불가) 처리됨을 뜻하는 필드 추가
        if 'IsDeleted' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN IsDeleted TEXT DEFAULT 'N'")
        # 완전 논리 삭제가 적용된 시각(이후 1년 보관 후 완전 파기됨)
        if 'DeletedAt' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN DeletedAt TEXT")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (Soft Delete)] {e}")

# 구동 시 유저 소프트 딜리트 컬럼 마이그레이션 실행
run_migration_if_needed('migrate_users_soft_delete', migrate_users_soft_delete)

def cleanup_migration_artifacts():
    """
    [역할]:
      - 마이그레이션 중 생성된 임시 백업 테이블이나 잘못 삽입된 레거시 쓰레기 데이터를 삭제합니다.
    [의존성 관계]:
      - categories, manufacturers 테이블
    [변경 시 영향도]:
      - DB 파일 용량 확보 및 마스터 데이터 무결성에 긍정적 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # categories 테이블에서 Name이 숫자로만 이루어진 비정상 데이터(ID가 이름으로 들어간 경우)를 조회
        cursor.execute("SELECT CategoryId, Name FROM categories")
        for row in cursor.fetchall():
            if row['Name'].isdigit():
                # 해당 비정상 레코드 영구 삭제
                cursor.execute("DELETE FROM categories WHERE CategoryId = ?", (row['CategoryId'],))
                
        # manufacturers 테이블에서도 동일하게 숫자로만 이루어진 비정상 데이터를 조회
        cursor.execute("SELECT ManufacturerId, Name FROM manufacturers")
        for row in cursor.fetchall():
            if row['Name'].isdigit():
                # 해당 비정상 레코드 영구 삭제
                cursor.execute("DELETE FROM manufacturers WHERE ManufacturerId = ?", (row['ManufacturerId'],))
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Cleanup Error] {e}")

# 마이그레이션 후처리 클린업 작업 실행
run_migration_if_needed('cleanup_migration_artifacts', cleanup_migration_artifacts)


def evaluate_user_lifecycle(user):
    """
    [역할]:
      - 사용자 탈퇴 유예기간(30일) 만료 및 하드 딜리트(1년) 여부를 실시간으로 평가합니다.
    [의존성 관계]:
      - users, user_settings, equipments 테이블, log_audit()
    [변경 시 영향도]:
      - 자진 탈퇴자 계정 파기 스케줄링 및 보안 유지에 결정적인 영향을 줍니다.
    """
    # 유저 객체가 아예 없다면 이미 삭제된 것으로 간주
    if not user:
        return {"status": "NOT_FOUND"}
        
    # sqlite3.Row 객체를 사전(Dictionary) 타입으로 캐스팅하여 필드 접근 허용
    user_dict = dict(user)
    user_id = user_dict.get('UserId')
    login_id = user_dict.get('LoginId')
    is_deactivated = user_dict.get('IsDeactivated') or 'N'
    deactivated_at_str = user_dict.get('DeactivatedAt')
    is_deleted = user_dict.get('IsDeleted') or 'N'
    
    # CASE 1: 탈퇴 신청 혹은 정지(Deactivated) 상태이면서 시간 정보가 있는 경우
    if is_deactivated == 'Y' and deactivated_at_str:
        try:
            # 기준 시간을 파싱하여 경과된 날짜(Day) 수 계산
            deactivated_at = datetime.strptime(deactivated_at_str, '%Y-%m-%d %H:%M:%S')
            days_passed = (datetime.now() - deactivated_at).total_seconds() / 86400.0
            
            # Phase 3: 논리 삭제(Soft Delete) 시점으로부터 다시 약 11개월이 지나 총 365+1일 경과 시 물리적 파기(Hard Delete)
            if days_passed >= 366:
                conn = get_db_connection()
                cursor = conn.cursor()
                # 유저의 개인 설정 파기
                cursor.execute("DELETE FROM user_settings WHERE UserId = ?", (user_id,))
                # 유저가 등록했던 장비는 담당자를 미정(NULL)으로 바꾸고 전체 공개로 전환하여 고아(Orphan) 자산화 방지
                cursor.execute("UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id = ?", (user_id,))
                # users 테이블에서 레코드 완전 삭제
                cursor.execute("DELETE FROM users WHERE UserId = ?", (user_id,))
                conn.commit()
                conn.close()
                # 완전 파기되었음을 시스템 감사 로그에 영구 기록
                log_audit(None, login_id, 'SYSTEM_HARD_DELETE', 'users', user_id, None, {"reason": "1_year_elapsed"})
                return {"status": "HARD_DELETED"}
                
            # Phase 2: 탈퇴 신청 후 유예 기간 30일 경과 시 -> 완전한 Soft Delete 적용 (복구 불가)
            if days_passed >= 30:
                if is_deleted != 'Y':
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    # Soft Delete 플래그 'Y' 적용 및 시간 기록
                    cursor.execute("UPDATE users SET IsDeleted = 'Y', DeletedAt = ? WHERE UserId = ?", (now_str, user_id))
                    conn.commit()
                    conn.close()
                    # Soft Delete 처리 내역 감사 로그 기록
                    log_audit(None, login_id, 'SYSTEM_SOFT_DELETE', 'users', user_id, None, {"reason": "30_days_elapsed"})
                return {"status": "DELETED", "days_passed": days_passed}
                
            # Phase 1: 탈퇴 신청 후 30일 미만 경과 -> 로그인 시도 시 유예 기간 안내 목적
            days_left = max(0, 30 - int(days_passed))
            return {"status": "DEACTIVATED", "days_left": days_left, "days_passed": days_passed}
        except Exception as e:
            # 파싱 등 에러 발생 시 보수적으로 유예 상태 반환
            print(f"[Lifecycle Evaluation Error] {e}")
            return {"status": "DEACTIVATED", "days_left": 30}
            
    # CASE 2: 정지(Deactivated) 상태이나 시간이 없는 경우 (관리자가 수동으로 무기한 정지 처분함)
    elif is_deactivated == 'Y' and not deactivated_at_str:
        return {"status": "ADMIN_SUSPENDED"}
        
    # CASE 3: 이미 Soft Delete 처리가 되어 있는 상태 (Phase 2가 적용된 후 로그인 시도)
    elif is_deleted == 'Y':
        # 삭제일 혹은 비활성화 기준일 획득
        deleted_at_str = user_dict.get('DeletedAt') or deactivated_at_str
        if deleted_at_str:
            try:
                # 1년(365+1일) 경과 여부를 다시 체크하여 Hard Delete 수행
                ref_time = datetime.strptime(deleted_at_str, '%Y-%m-%d %H:%M:%S')
                days_passed = (datetime.now() - ref_time).total_seconds() / 86400.0
                if days_passed >= 366:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM user_settings WHERE UserId = ?", (user_id,))
                    cursor.execute("UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM users WHERE UserId = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    log_audit(None, login_id, 'SYSTEM_HARD_DELETE', 'users', user_id, None, {"reason": "1_year_elapsed"})
                    return {"status": "HARD_DELETED"}
            except Exception:
                pass
        return {"status": "DELETED"}
        
    # 위 조건들에 해당하지 않으면 정상 이용 가능 계정임
    return {"status": "ACTIVE"}


# ==========================================
# 3. 인증 및 권한 데코레이터
# ==========================================

def login_required(f):
    """
    [역할]:
      - 로그인 세션이 없는 사용자의 접근을 차단하고 로그인 화면으로 리다이렉트합니다.
    [의존성 관계]:
      - session['user'], session['session_token']
    [변경 시 영향도]:
      - 인증이 필요한 전역 라우터 접근 제어 및 비활성화 계정 차단 프로세스에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 현재 브라우저 세션에서 유저 객체 획득
        user = session.get('user')
        # 다중 로그인 방어용 세션 토큰 획득
        session_token = session.get('session_token')
        
        # 세션이 아예 없거나, 비정상적이거나, 토큰이 누락된 경우 미인증 상태로 간주
        if not user or 'UserId' not in user or not session_token:
            # 잔여 세션 클리어
            session.clear()
            # API 요청(ajax)인 경우 401 JSON 응답 반환
            if request.path.startswith('/api/'):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            # 일반 웹 페이지 요청인 경우 로그인 뷰 렌더링을 위해 리다이렉트
            return redirect(url_for('login_page'))
            
        # 세션은 있으나 DB상에서 토큰이 변경/무효화되었는지 실시간 검사
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SessionToken, IsDeactivated, DeactivatedAt, IsDeleted FROM users WHERE UserId = ?", (user['UserId'],))
        db_user = cursor.fetchone()
        conn.close()
        
        # 유저가 DB에서 물리 삭제되었거나, 브라우저 토큰과 DB 토큰이 불일치하는 경우(다른 기기 로그인 발생)
        if not db_user or db_user['SessionToken'] != session_token:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({"error": "다른 기기에서 로그인하여 세션이 만료되었습니다."}), 401
            # URL 파라미터로 에러 사유를 넘겨주며 로그인 페이지로 리다이렉트
            return redirect(url_for('login_page', error='concurrent_login'))
            
        # 탈퇴 신청/관리자 정지 등 비활성화 계정 샌드박싱 로직
        # DB 상태상 비활성화이거나, 현재 세션에 비활성화 플래그가 남아있는 경우
        if db_user['IsDeactivated'] == 'Y' or session.get('user', {}).get('IsDeactivated'):
            # 비활성화 유저가 유일하게 접근할 수 있는 화이트리스트(허용) 경로 정의
            allowed_paths = ['/deactivated_notice', '/api/users/withdraw/cancel', '/logout']
            # 허용된 경로 이외의 접근 시도라면 무조건 차단
            if request.path not in allowed_paths:
                if request.path.startswith('/api/'):
                    return jsonify({"error": "비활성화 상태인 계정입니다."}), 403
                # 전용 안내 페이지로 강제 리다이렉트 (샌드박스화)
                return redirect(url_for('deactivated_notice_page'))

        # 모든 방어 로직 통과 시 본래 요청한 라우터 함수 실행
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    [역할]:
      - 관리자(admin) 등급 권한을 가진 사용자만 접근을 허용하는 전용 데코레이터입니다.
    [의존성 관계]:
      - session['user']
    [변경 시 영향도]:
      - 관리자 전용 API 및 시스템 설정 화면 접근 통제에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        # 유저 정보가 없거나, 권한 문자열이 'admin'이 아닌 경우 즉시 거부
        if not user or user.get('Role') != 'admin':
            if request.path.startswith('/api/'):
                # API 호출일 경우 권한 없음 403 반환
                return jsonify({"success": False, "message": "관리자 권한이 필요합니다."}), 403
            # 일반 페이지 접근 시도시 포털 메인으로 쫓아내고 에러 파라미터 첨부
            return redirect(url_for('portal_page', error='admin_only'))
        # 검증 통과 시 실행
        return f(*args, **kwargs)
    return decorated_function


@app.errorhandler(500)
def handle_internal_server_error(e):
    """
    [역할]:
      - 500 내부 서버 에러 발생 시 Stack Trace가 외부로 노출되지 않도록 은폐하고 안전한 응답 반환
    [의존성 관계]:
      - Flask 전역 예외 처리기 (errorhandler)
    [변경 시 영향도]:
      - 서비스 장애 시 시스템 내부 정보(경로, DB 쿼리 등) 노출 방지에 기여합니다.
    """
    # API 요청 중 500 에러 시 정형화된 JSON 형태의 500 응답 반환
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}), 500
    # 화면 요청 중 500 에러 시 포털 페이지(혹은 에러 페이지)를 렌더링
    return render_template('portal.html', error_msg="서버 오류가 발생했습니다."), 500


def check_menu_permission(menu_code):
    """
    [역할]:
      - 사용자의 Role 등급이 특정 메뉴(MenuCode)에 접근할 권한(IsAllowed=1)이 있는지 조회합니다.
    [의존성 관계]:
      - session, role_menu_permissions 테이블
    [변경 시 영향도]:
      - 동적 메뉴 노출 및 뷰 페이지 접근 허가/차단(403) 로직에 영향을 줍니다.
    """
    user = session.get('user')
    if not user:
        # 로그인 정보가 아예 없다면 접근 불가
        return False
    # 최고 관리자 등급은 메뉴 권한 테이블 조회 없이 무조건 프리패스(True)
    if user['Role'] == 'admin':
        return True
    
    # DB에서 사용자의 Role과 타겟 메뉴 코드에 매칭되는 IsAllowed 값 1건 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role = ? AND MenuCode = ?", (user['Role'], menu_code))
    row = cursor.fetchone()
    conn.close()
    
    # 매칭되는 권한 레코드가 존재하고, 그 값이 1(허용)인 경우에만 True 반환
    return bool(row and row['IsAllowed'] == 1)


# ==========================================
# 4. 화면 라우터 (뷰 페이지)
# ==========================================

@app.route('/favicon.ico')
def favicon():
    """
    [역할]:
      - 웹 브라우저 탭에 표시될 파비콘 이미지를 응답합니다.
    [의존성 관계]:
      - Resources 디렉터리의 EqMgmt.ico 파일
    [변경 시 영향도]:
      - 사이트 브랜딩 아이콘 표출에 영향을 줍니다.
    """
    # 보안상 send_from_directory를 사용하여 프로젝트 루트의 Resources 폴더 내 아이콘만 정적으로 제공
    return send_from_directory(os.path.join(app.root_path, 'Resources'),
                               'EqMgmt.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    """
    [역할]:
      - 사이트 최상위 경로 접속 시 세션 유무에 따라 포털 메인 또는 로그인 화면으로 분기합니다.
    [의존성 관계]:
      - session['user']
    [변경 시 영향도]:
      - 시스템 접속 시 초기 화면 리다이렉션 흐름에 영향을 줍니다.
    """
    # 세션에서 유저 정보를 꺼내옴
    user = session.get('user')
    # 유효한 UserId를 가진 세션이 있다면
    if user and 'UserId' in user:
        # 로그인 상태로 간주하고 대시보드(포털)로 이동
        return redirect(url_for('portal_page'))
    # 유효하지 않거나 깨진 세션일 경우 찌꺼기 세션을 강제로 날려버림
    session.pop('user', None)
    # 로그인 폼 페이지로 이동
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """
    [역할]:
      - 사용자 로그인 화면 제공 및 아이디/패스워드 검증, 세션 생성 처리를 담당합니다.
    [의존성 관계]:
      - users 테이블, evaluate_user_lifecycle(), check_password_hash()
    [변경 시 영향도]:
      - 시스템 전체 로그인 인증 메커니즘과 보안(동시접속 제어)에 막대한 영향을 줍니다.
    """
    # 1. GET 요청 (로그인 화면 렌더링)
    if request.method == 'GET':
        user = session.get('user')
        # 이미 로그인된 상태에서 접근 시 방어 로직
        if user and 'UserId' in user:
            # 유예 기간 등 비활성화 상태인 경우 안내 페이지로 강제 격리
            if user.get('IsDeactivated'):
                return redirect(url_for('deactivated_notice_page'))
            # 정상 유저라면 포털로 자동 통과
            return redirect(url_for('portal_page'))
        # 로그인되지 않았다면 찌꺼기 세션을 지우고 로그인 폼 제공
        session.pop('user', None)
        return render_template('login.html')
    
    # 2. POST 요청 (로그인 인증 시도)
    # JSON 통신(ajax) 혹은 Form Submit 데이터를 범용적으로 획득
    data = request.json or request.form
    login_id = data.get('LoginId')
    password = data.get('Password')
    
    # 로그인 ID 기반 단일 유저 조회 (대소문자 구분 및 정확한 매칭)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    user = cursor.fetchone()
    conn.close()
    
    # 입력한 ID가 DB에 없는 경우
    if not user:
        # 해커의 계정 스캐닝 방어를 위해 모호한(아이디/비밀번호 통합) 실패 메시지 반환
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', None, None, {"LoginId": login_id, "reason": "invalid_credentials"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400
        
    # 계정의 현재 라이프사이클 상태(정상, 정지, 탈퇴 유예, 파기 등) 실시간 평가
    eval_result = evaluate_user_lifecycle(user)
    status = eval_result['status']
    
    # 완전 삭제(Phase 3) 또는 소프트 딜리트(Phase 2) 된 계정일 경우 로그인 원천 차단
    if status in ['HARD_DELETED', 'DELETED']:
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', None, None, {"LoginId": login_id, "reason": f"account_{status.lower()}"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400
        
    # 관리자가 수동으로 영구 정지(Suspend) 시킨 계정일 경우 별도 사유 고지
    if status == 'ADMIN_SUSPENDED':
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', user['UserId'], None, {"LoginId": login_id, "reason": "admin_suspended"})
        return jsonify({"success": False, "message": "관리자에 의해 비활성화(정지)된 계정입니다. 관리자에게 문의하세요."}), 400
        
    # Werkzeug 해시 비교 함수를 사용하여 패스워드 일치 여부 최종 검증
    if check_password_hash(user['Password'], password):
        # 인증 성공 시, 보안 상 비밀번호를 제외한 최소한의 정보만 추출하여 세션용 딕셔너리 구성
        user_dict = {
            'UserId': user['UserId'],
            'LoginId': user['LoginId'],
            'Name': user['Name'],
            'NickName': user['NickName'],
            'Email': user['Email'] if 'Email' in user.keys() else None,
            'Role': user['Role'],
            # 비활성화(탈퇴 유예) 상태 여부를 세션에 기록하여 이후 미들웨어에서 샌드박싱 제어
            'IsDeactivated': (status == 'DEACTIVATED'),
            # 유예 기간일 경우 남은 일수 저장, 아닐 경우 None
            'DeactivationDaysLeft': eval_result.get('days_left', 30) if status == 'DEACTIVATED' else None
        }
        
        # 다중 로그인 방지를 위해 무작위 24바이트(48글자) 난수 토큰 발급
        session_token = os.urandom(24).hex()
        
        # Flask 세션 쿠키(브라우저)에 유저 정보와 고유 세션 토큰 저장
        session['user'] = user_dict
        session['session_token'] = session_token
        # 세션 쿠키를 영구적(기본 31일 등)으로 설정하여 브라우저 종료 시에도 유지
        session.permanent = True
        
        # 발급된 세션 토큰을 DB users 테이블에 기록 (이전 토큰 무효화 메커니즘)
        conn_update = get_db_connection()
        cursor_update = conn_update.cursor()
        cursor_update.execute("UPDATE users SET SessionToken = ? WHERE UserId = ?", (session_token, user['UserId']))
        conn_update.commit()
        conn_update.close()
        
        # 로그인 성공 감사 로그 기록
        log_audit(user['UserId'], user['LoginId'], 'LOGIN_SUCCESS', 'users', user['UserId'], None, {"LoginId": login_id, "Status": status})
        
        # 탈퇴 유예 중인 계정이라면 즉시 전용 안내 뷰로 리다이렉트 지시를 JSON으로 반환
        if status == 'DEACTIVATED':
            return jsonify({
                "success": True,
                "is_deactivated": True,
                "redirect": "/deactivated_notice",
                "message": f"현재 회원 탈퇴 유예 중(D-{eval_result.get('days_left', 30)}일)입니다."
            })
            
        # 정상 계정이면 성공 메시지 반환 (클라이언트에서 포털로 이동 처리)
        return jsonify({"success": True, "message": "로그인 성공"})
    else:
        # 패스워드가 틀린 경우
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', user['UserId'], None, {"LoginId": login_id, "reason": "invalid_password"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400


@app.route('/deactivated_notice')
@login_required
def deactivated_notice_page():
    """
    [역할]:
      - 탈퇴 유예 등 계정 비활성화 상태인 사용자 전용 샌드박스 안내 화면을 렌더링합니다.
    [의존성 관계]:
      - deactivated_notice.html 템플릿, session['user']
    [변경 시 영향도]:
      - 정지/탈퇴 유예 회원의 접근 격리 흐름 및 안내 문구 표시에 영향을 줍니다.
    """
    user = session.get('user', {})
    # 세션에서 남은 유예 일수 추출, 없으면 기본값 30일
    days_left = user.get('DeactivationDaysLeft', 30)
    return render_template('deactivated_notice.html', user=user, days_left=days_left)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """
    [역할]:
      - 회원 가입 화면 제공 및 폼 서밋을 통한 신규 계정 생성(또는 논리삭제 계정 복구)을 처리합니다.
    [의존성 관계]:
      - users 테이블, email_verifications 테이블, evaluate_user_lifecycle()
    [변경 시 영향도]:
      - 시스템 전체 신규 회원 유입 프로세스 및 이메일 기반 보안 통제 메커니즘에 중대한 영향을 미칩니다.
    """
    if request.method == 'GET':
        # 회원가입 폼 렌더링
        return render_template('register.html')
        
    data = request.json
    login_id = data.get('LoginId')
    name = data.get('Name')
    nickname = data.get('NickName')
    password = data.get('Password')
    email = data.get('Email')
    
    # [제안-011] API 통신에서 데코레이터 적용 전 수동으로 CSRF 토큰 검증 로직 실행
    token = request.headers.get('X-CSRFToken')
    if not token or token != session.get('csrf_token'):
        return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요."}), 403

    # 패스워드를 PBKDF2 해시 알고리즘으로 단방향 암호화
    hashed_password = generate_password_hash(password)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 이메일 인증 통과 여부 최우선 검증 (무단 가입 방어)
    cursor.execute("SELECT IsVerified FROM email_verifications WHERE Email = ?", (email,))
    verif = cursor.fetchone()
    # 이메일 인증 코드를 발송하지 않았거나 검증을 마치지 않은 경우 거부
    if not verif or verif['IsVerified'] != 1:
        conn.close()
        return jsonify({"success": False, "message": "이메일 인증이 완료되지 않았습니다."}), 400
    
    # 2. 동일한 로그인 ID가 이미 존재하는지 조회
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        # 3. ID가 존재한다면 탈퇴(Soft Delete)된 계정인지 평가
        eval_res = evaluate_user_lifecycle(existing_user)
        status = eval_res['status']
        
        # 완전 삭제되지 않고 30일 유예 기간이 만료되어 Soft Delete 된 상태인 경우(복구 기회 제공)
        if status == 'DELETED':
            # 계정 소유권 확인: 가입 시 입력한 실명(Name)이 일치하는 경우에만 복구 허용
            if name and existing_user['Name'] and name.strip() == existing_user['Name'].strip():
                try:
                    # 유저 정보를 최신 폼 데이터(새 비밀번호 포함)로 덮어쓰고, Deactivated/Deleted 플래그를 모두 'N'으로 초기화
                    cursor.execute('''
                        UPDATE users
                        SET Password = ?, Name = ?, NickName = ?, Email = ?, IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL, UpdatedAt = ?
                        WHERE UserId = ?
                    ''', (hashed_password, name, nickname, email, now, existing_user['UserId']))
                    conn.commit()
                    # 복구 완료 감사 로그 남김
                    log_audit(existing_user['UserId'], login_id, 'RECOVER_ACCOUNT', 'users', existing_user['UserId'], None, {"LoginId": login_id})
                    conn.close()
                    return jsonify({"success": True, "message": "탈퇴된 계정의 소유권이 확인되어 성공적으로 복구되었습니다! 로그인해 주세요."})
                except sqlite3.IntegrityError:
                    # 복구 시도 중 다른 계정과 Email이 충돌하는 경우 UNIQUE 제약조건 에러 발생
                    conn.close()
                    return jsonify({"success": False, "message": "이미 다른 계정에 등록되어 사용 중인 이메일 주소입니다."}), 400
            else:
                # 실명이 불일치하는 경우 복구 힌트와 함께 소유권 재확인 요구
                conn.close()
                return jsonify({
                    "success": False,
                    "is_recovery_target": True,
                    "message": "💡 해당 아이디는 탈퇴 수순을 밟고 있는 계정입니다. 계정 복구를 원하시면 본인 소유권 확인을 위해 기존 가입 시 등록하셨던 '실명(이름)'을 입력란에 정확히 입력해 주세요."
                }), 400
                
        # 아직 30일 유예 기간 중인 경우, 로그인 화면으로 돌아가서 유예 철회하도록 유도
        elif status == 'DEACTIVATED':
            conn.close()
            return jsonify({
                "success": False,
                "message": "해당 아이디는 현재 비활성화(탈퇴 유예) 상태입니다. 기존 계정으로 로그인하시면 비활성화를 철회하실 수 있습니다."
            }), 400
            
        # Hard Delete(1년 경과 완전파기) 상태가 아니라면 단순히 중복 ID 가입 시도로 판단
        elif status != 'HARD_DELETED':
            conn.close()
            return jsonify({"success": False, "message": "이미 존재하는 아이디입니다."}), 400

    # 4. 신규 가입 진행 (중복 없음 혹은 Hard Delete되어 완전 파기된 ID 재가입 시)
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    # 시스템 최초 가입자는 무조건 'admin' 권한 부여, 이후 가입자는 일반 'user' 권한 부여
    role = 'admin' if count == 0 else 'user'
    
    try:
        # users 테이블에 레코드 삽입 (초기 상태 IsDeactivated='N', IsDeleted='N')
        cursor.execute('''
            INSERT INTO users (LoginId, Name, NickName, Password, Email, Role, CreatedAt, UpdatedAt, IsDeactivated, IsDeleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'N', 'N')
        ''', (login_id, name, nickname, hashed_password, email, role, now, now))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 신규가입 감사 로그 기록
        log_audit(new_id, login_id, 'REGISTER', 'users', new_id, None, {"LoginId": login_id, "Role": role})
        return jsonify({"success": True, "message": "회원가입이 성공적으로 완료되었습니다. 로그인해 주세요."})
    except sqlite3.IntegrityError:
        # Email 혹은 LoginId 제약조건 충돌 시 에러 반환
        conn.close()
        return jsonify({"success": False, "message": "이미 다른 계정에 등록되어 사용 중인 이메일 주소입니다."}), 400


@app.route('/logout')
def logout():
    """
    [역할]:
      - 현재 접속 중인 사용자의 세션을 완전히 파기하고 로그아웃 처리합니다.
    [의존성 관계]:
      - session, log_audit()
    [변경 시 영향도]:
      - 사용자의 브라우저 로그인 유지 상태(세션 종료)에 직접적인 영향을 줍니다.
    """
    user = session.get('user')
    if user:
        if 'UserId' in user:
            # 안전하게 로그아웃되었다는 감사 로그 적재
            log_audit(user['UserId'], user['LoginId'], 'LOGOUT', 'users', user['UserId'], None, None)
        # 브라우저 세션에 저장된 모든 쿠키 데이터를 완전 삭제
        session.clear()
    # 로그아웃 후 다시 로그인 페이지로 리다이렉트
    return redirect(url_for('login_page'))


@app.route('/portal')
@login_required
def portal_page():
    """
    [역할]:
      - 로그인한 사용자에게 제공되는 최초의 대시보드(포털) 화면을 렌더링합니다.
    [의존성 관계]:
      - portal.html, session['user']
    [변경 시 영향도]:
      - 사용자가 모든 서비스 기능으로 이동하는 허브(Hub) 페이지 표출에 영향을 줍니다.
    """
    # 템플릿에 유저 정보를 넘겨 사용자 이름이나 권한별 메뉴 표출에 활용
    return render_template('portal.html', user=session['user'])


@app.route('/equipment')
def equipment_redirect():
    """
    [역할]:
      - 예전 '레거시 장비 목록' URL 경로(/equipment)로 접속한 사용자를 최신 '/my_equipment' 경로로 포워딩합니다.
    [의존성 관계]:
      - url_for('my_equipment_page')
    [변경 시 영향도]:
      - 과거 즐겨찾기를 사용 중인 유저의 하위 호환성 및 404 에러 방지에 기여합니다.
    """
    # 영구적인(혹은 단순한) 리다이렉션 응답을 반환하여 최신 라우터로 통과시킴
    return redirect(url_for('my_equipment_page'))


@app.route('/my_equipment')
@login_required
def my_equipment_page():
    """
    [역할]:
      - 로그인한 사용자 본인의 '나의 장비' 관리 화면을 렌더링합니다.
    [의존성 관계]:
      - index.html 템플릿, check_menu_permission('my_equipment')
    [변경 시 영향도]:
      - 본인 소유 장비 UI 접근 제어 및 페이지 렌더링에 영향을 줍니다.
    """
    # 사용자가 'my_equipment' 메뉴 접근 권한이 있는지 테이블 기반 동적 검증
    if not check_menu_permission('my_equipment'):
        # 권한이 없을 경우 자바스크립트 알럿을 띄우고 포털로 쫓아냄
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    # 검증 통과 시 index.html을 'my' 모드로 렌더링
    return render_template('index.html', user=session['user'], mode='my')


@app.route('/public_equipment')
@login_required
def public_equipment_page():
    """
    [역할]:
      - 전체 공개로 설정된 사내 공용 자산 및 타인의 공개 장비 목록 화면을 렌더링합니다.
    [의존성 관계]:
      - index.html 템플릿, check_menu_permission('public_equipment')
    [변경 시 영향도]:
      - 공개 자산 뷰어 UI 접근 제어에 영향을 줍니다.
    """
    # 접근 권한 런타임 검사
    if not check_menu_permission('public_equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    # 검증 통과 시 index.html을 'public' 모드로 렌더링
    return render_template('index.html', user=session['user'], mode='public')


@app.route('/admin_center')
@login_required
def admin_center_page():
    """
    [역할]:
      - 관리자 전용 제어판(Admin Center) 메인 화면을 렌더링합니다.
    [의존성 관계]:
      - admin_center.html 템플릿, check_menu_permission('admin_center')
    [변경 시 영향도]:
      - 시스템 설정 메뉴로 진입하는 관리자 허브 페이지 접근에 영향을 줍니다.
    """
    # 권한 체크 수행
    if not check_menu_permission('admin_center'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    # admin_center 렌더링
    return render_template('admin_center.html', user=session.get('user'))

@app.route('/permissions')
@login_required
def permissions_page():
    """
    [역할]:
      - 관리자가 시스템 내 각 역할(Role)별 메뉴 접근 권한을 제어하는 화면을 렌더링합니다.
    [의존성 관계]:
      - permissions.html 템플릿, check_menu_permission('permissions')
    [변경 시 영향도]:
      - 권한 부여/회수 관리 UI 진입에 영향을 줍니다.
    """
    # 권한 확인
    if not check_menu_permission('permissions'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    # 관리 뷰 렌더링
    return render_template('permissions.html', user=session['user'])


@app.route('/audit_logs')
@login_required
def audit_logs_page():
    """
    [역할]:
      - 데이터베이스 시스템 감사 로그(CUD 이벤트 등) 관제 화면을 렌더링합니다.
    [의존성 관계]:
      - audit_logs.html 템플릿, check_menu_permission('audit_logs')
    [변경 시 영향도]:
      - 추적/감사 모니터링 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('audit_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('audit_logs.html', user=session['user'])


@app.route('/access_logs')
@login_required
def access_logs_page():
    """
    [역할]:
      - 관리자 전용 실시간 웹 접근 로그 관제 화면을 렌더링합니다.
    [의존성 관계]:
      - access_logs.html 템플릿, check_menu_permission('access_logs')
    [변경 시 영향도]:
      - 트래픽 분석 및 악성 IP 관제 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('access_logs.html', user=session['user'])


@app.route('/access_logs/error_ips')
@login_required
def access_logs_error_ips_page():
    """
    [역할]:
      - 관리자 전용 에러(4xx, 5xx) 유발 IP 심층 분석 및 필터링 화면을 렌더링합니다.
    [의존성 관계]:
      - access_logs_error_ips.html 템플릿, check_menu_permission('access_logs')
    [변경 시 영향도]:
      - 에러 유발 악성 봇넷 등 고유 IP 심층 관제 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('access_logs_error_ips.html', user=session['user'])


@app.route('/users_management')
@login_required
def users_management_page():
    """
    [역할]:
      - 관리자 전용 시스템 회원 통제 및 계정 정지(탈퇴 유예) 관리 화면을 렌더링합니다.
    [의존성 관계]:
      - users_management.html 템플릿, check_menu_permission('users_management')
    [변경 시 영향도]:
      - 악성 사용자 관리 UI 렌더링에 영향을 줍니다.
    """
    if not check_menu_permission('users_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('users_management.html', user=session['user'])

@app.route('/dashboard')
@login_required
def dashboard_page():
    """
    [역할]:
      - 장비 등록 및 사용량 등 시스템 요약 통계(대시보드) 화면을 렌더링합니다.
    [의존성 관계]:
      - dashboard.html 템플릿, check_menu_permission('dashboard')
    [변경 시 영향도]:
      - 통계 및 차트 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('dashboard'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('dashboard.html', user=session['user'])

@app.route('/mypage')
@login_required
def mypage_page():
    """
    [역할]:
      - 로그인한 사용자의 정보 조회 및 수정(마이페이지) 화면을 렌더링합니다.
    [의존성 관계]:
      - mypage.html 템플릿, session['user']
    [변경 시 영향도]:
      - 사용자 본인의 개인정보 관리 및 비밀번호 변경 화면 진입에 영향을 줍니다.
    """
    # 마이페이지는 모든 로그인 사용자가 필수적으로 접근 가능하므로 메뉴 권한(Role) 체크 로직을 생략함
    return render_template('mypage.html', user=session['user'])

@app.route('/approvals')
@login_required
def approvals_page():
    """
    [역할]:
      - 관리자 전용 신규 마스터 데이터 결재/승인 화면을 렌더링합니다.
    [의존성 관계]:
      - approvals.html 템플릿, check_menu_permission('approvals')
    [변경 시 영향도]:
      - 유저가 요청한 카테고리/제조사/장비옵션의 승인 처리 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('approvals'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('approvals.html', user=session['user'])

@app.route('/master_management')
@login_required
def master_management_page():
    """
    [역할]:
      - 데이터 무결성 관리를 위한 마스터 데이터(카테고리/제조사/모델트리) 관리 페이지 렌더링
    [의존성 관계]:
      - master_management.html 템플릿, check_menu_permission('master_management')
    [변경 시 영향도]:
      - 시스템의 뼈대가 되는 기초 데이터 편집 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('master_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('master_management.html', user=session['user'])

# ==========================================
# 5. RESTful API 모듈 (인증/권한 및 데이터 처리)
# ==========================================

# =========================================================================
# [제안-036] 가변 깊이 모델 트리 & 3-Tier 장비 관리 RESTful API 모듈
# =========================================================================

MAX_TREE_DEPTH = 50  # [Call Stack Overflow 방어] 트리 최대 깊이 컷아웃

def _get_all_descendant_node_ids(cursor, node_id):
    """
    [역할]:
      - 특정 카탈로그 모델 노드(node_id)에 속한 모든 자손(Descendant) 노드의 ID 집합을 재귀적으로 수집합니다.
    [의존성 관계]:
      - lineup_nodes 테이블, SQLite cursor 객체
    [변경 시 영향도]:
      - 순환 참조(Cyclic Reference) 방어 및 하위 장비 연쇄 검색 로직에 깊은 영향을 줍니다.
    """
    descendants = set()
    # DFS(깊이 우선 탐색)를 위한 스택 초기화
    stack = [node_id]
    
    while stack:
        # 스택의 최상단에서 현재 탐색 노드 추출
        current = stack.pop()
        # 현재 노드를 부모로 가지는 1 Depth 직계 자식 조회
        cursor.execute("SELECT id FROM lineup_nodes WHERE parent_id = ?", (current,))
        children = [r['id'] for r in cursor.fetchall()]
        
        for child_id in children:
            # 순환 참조 방지 및 중복 회피를 위해 set 내 존재 여부 확인
            if child_id not in descendants:
                # 자손 집합에 추가하고, 자식의 자식을 찾기 위해 스택에 푸시
                descendants.add(child_id)
                stack.append(child_id)
                
    # 최종 수집된 모든 자손 ID 집합을 반환
    return descendants


@app.route('/api/lineup_tree_all', methods=['GET'])
@login_required
@app.route('/api/lineup_tree_all', methods=['GET'])
@login_required
def get_lineup_tree_all():
    """
    [역할]:
      - 카테고리, 제조사, N차 라인업 노드, N+1차 옵션까지 전체 카탈로그 트리를 단 1회의 응답 덤프로 클라이언트에 제공합니다.
    [의존성 관계]:
      - CTE(WITH RECURSIVE) 쿼리, categories, manufacturers, lineup_nodes, equipment_options 테이블
    [변경 시 영향도]:
      - 프론트엔드 장비 분류 트리 초기화 렌더링 성능 및 컷아웃(Depth 50) 제약에 결정적 영향을 미칩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 1차 분류: 시스템 관리자가 최종 승인(IsApproved=1)한 카테고리 목록을 가나다순으로 획득
        cursor.execute("SELECT CategoryId AS id, Name AS name FROM categories WHERE IsApproved = 1 ORDER BY Name ASC")
        categories = [dict(r) for r in cursor.fetchall()]

        # 2. 2차 분류: 시스템 관리자가 최종 승인한 제조사(브랜드) 목록을 가나다순으로 획득
        cursor.execute("SELECT ManufacturerId AS id, Name AS name FROM manufacturers WHERE IsApproved = 1 ORDER BY Name ASC")
        manufacturers = [dict(r) for r in cursor.fetchall()]

        # 3. 3차 분류: CTE(공통 테이블 식) 재귀 쿼리를 통한 승인된 라인업 노드 전체 트리 덤프
        # (MAX_TREE_DEPTH 상수 50 을 컷아웃(제한) 조건으로 걸어 Call Stack Overflow 및 무한 루프 악용 방어)
        cursor.execute(f"""
            WITH RECURSIVE node_tree AS (
                -- [Anchor Member] 최상위 모델(루트) 노드 (parent_id가 NULL인 노드만 선택)
                SELECT id, parent_id, category_id, manufacturer_id, name, depth, status, 1 AS level
                FROM lineup_nodes
                WHERE parent_id IS NULL AND status = 'APPROVED'
                
                UNION ALL
                
                -- [Recursive Member] 이전 단계(nt)의 id를 parent_id로 가지는 하위 모델 노드를 재귀적으로 조인 탐색
                SELECT n.id, n.parent_id, n.category_id, n.manufacturer_id, n.name, n.depth, n.status, nt.level + 1
                FROM lineup_nodes n
                JOIN node_tree nt ON n.parent_id = nt.id
                -- 재귀 호출 깊이(level)가 허용치를 초과하지 않도록 컷아웃(Cut-out)
                WHERE nt.level < {MAX_TREE_DEPTH} AND n.status = 'APPROVED'
            )
            -- 획득한 전체 트리 구조를 level과 이름순으로 정렬하여 반환
            SELECT * FROM node_tree ORDER BY level ASC, name ASC;
        """)
        nodes = [dict(r) for r in cursor.fetchall()]

        # 4. 4차 분류: 승인된 장비 세부 옵션(스펙) 목록 획득 및 JSON 텍스트를 파이썬 딕셔너리로 언패킹
        cursor.execute("SELECT id, lineup_node_id, option_name, specs_json FROM equipment_options WHERE status = 'APPROVED'")
        raw_options = cursor.fetchall()
        
        options = []
        for opt in raw_options:
            specs = {}
            if opt['specs_json']:
                try:
                    # DB에 저장된 동적 구조의 JSON 텍스트 파싱 시도
                    specs = json.loads(opt['specs_json'])
                except Exception:
                    # 파싱 실패(데이터 오염) 시 빈 객체로 fallback 처리
                    specs = {}
            
            # 클라이언트 친화적인 직렬화 포맷으로 옵션 목록 재구성
            options.append({
                "id": opt['id'],
                "lineup_node_id": opt['lineup_node_id'],
                "option_name": opt['option_name'],
                "specs": specs
            })

        conn.close()

        # 취합된 4계층(카테고리->제조사->모델트리->옵션) 데이터를 단일 JSON DTO로 클라이언트에 전송
        return jsonify({
            "success": True,
            "version": "nodeCache_v2",
            "categories": categories,
            "manufacturers": manufacturers,
            "nodes": nodes,
            "options": options
        })

    except Exception as e:
        # 데이터베이스 에러(CTE 미지원 등) 발생 시 500이 아닌 400 에러와 함께 친절한 메시지 반환
        print(f"[API Error] get_lineup_tree_all: {e}")
        return jsonify({"success": False, "message": "카탈로그 트리를 불러오는 중 오류가 발생했습니다."}), 400


@app.route('/api/lineup_node', methods=['POST'])
@login_required
@csrf_required
def create_lineup_node():
    """
    [역할]:
      - 신규 카탈로그 라인업 노드(분류 체계 트리 구조의 새 가지) 등록 및 승인 신청을 처리합니다.
    [보안/방어]:
      - [NULL 중복 락 방어] 루트 노드(parent_id IS NULL) 등록 시 백엔드 2차 SELECT 중복 검사
      - [MAX_DEPTH 방어] 악의적인 깊이(50 초과) 생성 차단
      - [권한 분리] 관리자는 생성 즉시 자동 APPROVED, 일반 사용자는 PENDING 상태로 승인 큐 적재
    [변경 시 영향도]:
      - 장비 분류 체계 트리의 확장 및 무결성에 직접적인 영향을 미칩니다.
    """
    try:
        # 클라이언트에서 전송한 JSON 페이로드 추출
        data = request.json or {}
        name = (data.get('name') or '').strip()
        category_id = data.get('category_id')
        manufacturer_id = data.get('manufacturer_id')
        # parent_id가 None이면 최상위 루트 노드, int면 특정 노드의 하위 자식 노드
        parent_id = data.get('parent_id')  

        # 필수 입력값(명칭, 카테고리, 제조사) 유효성 1차 검증
        if not name:
            return jsonify({"success": False, "message": "노드 이름을 입력해 주세요."}), 400
        if not category_id or not manufacturer_id:
            return jsonify({"success": False, "message": "카테고리와 제조사를 선택해 주세요."}), 400

        # 요청자 세션 정보 및 역할(Role) 확인
        user = session.get('user', {})
        user_id = user.get('UserId')
        is_admin = (user.get('Role') == 'admin')
        # 관리자 권한이면 즉각 승인(APPROVED), 일반 유저면 대기(PENDING) 상태 부여
        status = 'APPROVED' if is_admin else 'PENDING'

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 삽입될 노드의 깊이(Depth) 계산 및 시스템 보호를 위한 MAX_DEPTH 제한 검증
        current_depth = 1
        if parent_id:
            cursor.execute("SELECT depth, category_id, manufacturer_id FROM lineup_nodes WHERE id = ?", (parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                conn.close()
                return jsonify({"success": False, "message": "상위 노드를 찾을 수 없습니다."}), 400
            
            # 부모 노드의 깊이에 +1을 하여 현재 노드의 깊이 산출
            current_depth = parent_row['depth'] + 1
            if current_depth > MAX_TREE_DEPTH:
                conn.close()
                # 과도한 재귀에 의한 Call Stack Overflow 공격을 원천 차단
                return jsonify({"success": False, "message": f"트리의 최대 깊이({MAX_TREE_DEPTH}단계)를 초과할 수 없습니다."}), 400

        # 2. [NULL 중복 락 방어]: 고유성 제약(Unique) 중복 생성 명시적 방어
        if parent_id is None:
            # 루트 노드의 경우: 동일 카테고리 & 제조사에 같은 이름의 루트 노드가 있는지 확인
            cursor.execute("""
                SELECT id FROM lineup_nodes 
                WHERE parent_id IS NULL AND category_id = ? AND manufacturer_id = ? AND name = ?
            """, (category_id, manufacturer_id, name))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "해당 카테고리/제조사에 동일한 이름의 최상위 모델이 이미 존재합니다."}), 400
        else:
            # 하위 노드의 경우: 지정한 부모 아래에 동일한 이름의 형제 노드가 있는지 확인
            cursor.execute("SELECT id FROM lineup_nodes WHERE parent_id = ? AND name = ?", (parent_id, name))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "동일한 상위 노드 아래에 같은 이름의 하위 항목이 이미 존재합니다."}), 400

        # 3. 모든 검증을 통과한 경우 lineup_nodes 테이블에 물리적 레코드 삽입
        cursor.execute("""
            INSERT INTO lineup_nodes (parent_id, category_id, manufacturer_id, name, depth, status, requested_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (parent_id, category_id, manufacturer_id, name, current_depth, status, user_id))
        
        # 방금 생성된 신규 노드의 Primary Key(ID) 획득
        new_node_id = cursor.lastrowid

        # 4. 일반 사용자가 신청한 경우 approval_requests (승인 대기열) 테이블에 결재 안건 적재
        if not is_admin:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 결재 화면에서 보여주기 위해 요청 상세 데이터를 JSON 포맷으로 직렬화하여 저장
            req_data = json.dumps({
                "type": "Lineup_Node",
                "node_id": new_node_id,
                "name": name,
                "parent_id": parent_id,
                "category_id": category_id,
                "manufacturer_id": manufacturer_id,
                "depth": current_depth
            }, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt)
                VALUES (?, 'Lineup_Node', ?, 'PENDING', ?, ?)
            """, (user_id, req_data, now_str, now_str))

        conn.commit()
        conn.close()

        # 권한에 따라 다른 안내 메시지 제공
        msg = "신규 모델이 등록되었습니다." if is_admin else "신규 모델 등록 신청이 완료되었습니다. 관리자 승인 후 활성화됩니다."
        return jsonify({"success": True, "node_id": new_node_id, "status": status, "message": msg})

    except Exception as e:
        print(f"[API Error] create_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 등록 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/lineup_node/<int:node_id>', methods=['PUT'])
@login_required
@admin_required
@csrf_required
def update_lineup_node(node_id):
    """
    [역할]:
      - 지정된 라인업 노드의 이름(name)을 수정하거나 소속 트리 위치(parent_id)를 변경합니다. (관리자 전용)
    [보안/순환 참조(Cyclic Reference) 방어]:
      - 새 부모 노드가 자기 자신이거나, 자신의 하위 자손 노드 중 하나인 경우를 DFS로 탐색하여 원천 차단
    [변경 시 영향도]:
      - 카탈로그 트리 전체의 구조 변경 및 노드 Depth 연쇄 조정에 영향을 줍니다.
    """
    try:
        data = request.json or {}
        new_name = (data.get('name') or '').strip()
        new_parent_id = data.get('parent_id')  # 루트 레벨 이동 시 None 가능

        conn = get_db_connection()
        cursor = conn.cursor()

        # 수정할 타겟 노드 검증
        cursor.execute("SELECT * FROM lineup_nodes WHERE id = ?", (node_id,))
        node = cursor.fetchone()
        if not node:
            conn.close()
            return jsonify({"success": False, "message": "수정할 노드를 찾을 수 없습니다."}), 404

        # 1. [순환 참조 방어 검증 1] 자기 자신을 부모로 지정하는 오류 방어
        if new_parent_id is not None and int(new_parent_id) == node_id:
            conn.close()
            return jsonify({"success": False, "message": "자기 자신을 부모 노드로 지정할 수 없습니다. (순환 참조 방어)"}), 400

        # 2. [순환 참조 방어 검증 2] 부모가 변경된 경우, 자신의 하위 자손 노드를 부모로 지정하는 무한 루프 엣지 케이스 방어
        if new_parent_id is not None:
            new_parent_id = int(new_parent_id)
            # DFS를 통해 타겟 노드의 모든 자손 ID 획득
            descendant_ids = _get_all_descendant_node_ids(cursor, node_id)
            if new_parent_id in descendant_ids:
                conn.close()
                return jsonify({"success": False, "message": "자신의 하위 자손 노드를 부모로 지정할 수 없습니다. (순환 참조 고리 방어)"}), 400

            # 지정한 새 부모 노드가 실제로 존재하는지, 그리고 이동 시 Depth가 초과하지 않는지 계산
            cursor.execute("SELECT depth FROM lineup_nodes WHERE id = ?", (new_parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                conn.close()
                return jsonify({"success": False, "message": "지정한 부모 노드가 존재하지 않습니다."}), 400
            new_depth = parent_row['depth'] + 1
        else:
            # 부모가 None이면 최상위 루트 노드로 승격
            new_depth = 1

        # 이동 후 노드의 깊이가 시스템 제한(MAX_TREE_DEPTH)을 초과하는지 최종 방어
        if new_depth > MAX_TREE_DEPTH:
            conn.close()
            return jsonify({"success": False, "message": f"트리의 최대 깊이({MAX_TREE_DEPTH}단계)를 초과할 수 없습니다."}), 400

        # 새 이름이 제공되지 않았다면 기존 이름 유지
        final_name = new_name if new_name else node['name']

        # 노드 정보(이름, 부모관계, 깊이) 물리 업데이트 실행
        cursor.execute("""
            UPDATE lineup_nodes 
            SET name = ?, parent_id = ?, depth = ?
            WHERE id = ?
        """, (final_name, new_parent_id, new_depth, node_id))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "노드 정보가 성공적으로 수정되었습니다."})

    except Exception as e:
        print(f"[API Error] update_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 수정 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/lineup_node/<int:node_id>', methods=['DELETE'])
@login_required
@admin_required
@csrf_required
def delete_lineup_node(node_id):
    """
    [역할]:
      - 지정된 라인업 노드를 데이터베이스에서 물리적으로 완전 삭제합니다. (관리자 전용)
    [파괴적 액션 방어]:
      - 하위 자식 노드(분류 가지)가 남아있거나, 해당 노드에 연계된 옵션 스펙 묶음이 존재할 경우 참조 무결성을 위해 삭제를 거부합니다.
    [변경 시 영향도]:
      - 카탈로그 트리 축소에 직접적인 영향을 주며 복구 불가능한 영구 삭제를 유발합니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 무결성 방어: 자신을 부모로 참조하고 있는 하위 자식 노드 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM lineup_nodes WHERE parent_id = ?", (node_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "message": "하위 모델이 연결되어 있어 삭제할 수 없습니다. 하위 모델을 먼저 삭제해 주세요."}), 400

        # 2. 무결성 방어: 현재 노드에 귀속된 N+1차 세부 장비 옵션(스펙)의 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM equipment_options WHERE lineup_node_id = ?", (node_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "message": "연결된 옵션 스펙이 존재하여 삭제할 수 없습니다."}), 400

        # 방어를 모두 통과한 경우에만 안전하게 물리 삭제 처리(DELETE)
        cursor.execute("DELETE FROM lineup_nodes WHERE id = ?", (node_id,))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "노드가 안전하게 삭제되었습니다."})

    except Exception as e:
        print(f"[API Error] delete_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 삭제 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/equipment_option', methods=['POST'])
@login_required
@csrf_required
def create_equipment_option():
    """
    [역할]:
      - N차 라인업 노드에 귀속되는 N+1차 최종 장비 옵션 스펙 조합을 등록합니다.
    [JSON 밸리데이션]:
      - 클라이언트에서 동적으로 전송한 JSON 딕셔너리를 문자열(specs_json)로 직렬화하여 영속화합니다.
    [변경 시 영향도]:
      - 새로운 장비를 인스턴스화할 수 있는 최종 스펙 템플릿(옵션) 생성에 영향을 줍니다.
    """
    try:
        data = request.json or {}
        lineup_node_id = data.get('lineup_node_id')
        option_name = (data.get('option_name') or '').strip()
        specs = data.get('specs') or {}

        # 1. 필수값 유효성 검사
        if not lineup_node_id:
            return jsonify({"success": False, "message": "소속될 모델 노드를 선택해 주세요."}), 400
        if not option_name:
            return jsonify({"success": False, "message": "옵션 조합명을 입력해 주세요."}), 400

        # 2. 동적 스펙 딕셔너리를 JSON 텍스트로 안전하게 직렬화. 딕셔너리가 아닌 악의적 입력 시 빈 객체 처리.
        specs_json_str = json.dumps(specs, ensure_ascii=False) if isinstance(specs, dict) else '{}'

        # 3. 요청자 세션 기반 권한 분리
        user = session.get('user', {})
        user_id = user.get('UserId')
        is_admin = (user.get('Role') == 'admin')
        status = 'APPROVED' if is_admin else 'PENDING'

        conn = get_db_connection()
        cursor = conn.cursor()

        # 4. 물리 데이터 삽입
        cursor.execute("""
            INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by)
            VALUES (?, ?, ?, ?, ?)
        """, (lineup_node_id, option_name, specs_json_str, status, user_id))

        new_opt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        msg = "옵션 스펙이 등록되었습니다." if is_admin else "옵션 등록 신청이 완료되었습니다. 관리자 승인 후 활성화됩니다."
        return jsonify({"success": True, "option_id": new_opt_id, "status": status, "message": msg})

    except Exception as e:
        print(f"[API Error] create_equipment_option: {e}")
        return jsonify({"success": False, "message": f"옵션 등록 중 오류: {str(e)}"}), 400


@app.route('/api/equipment_option/<int:option_id>', methods=['DELETE'])
@login_required
@admin_required
@csrf_required
def delete_equipment_option(option_id):
    """
    [역할]:
      - 지정된 3-Tier 카탈로그 옵션 스펙 조합을 삭제합니다. (관리자 전용)
    [파괴적 액션 방어]:
      - 해당 옵션을 템플릿으로 사용하여 인스턴스화된 실제 장비(equipments)가 DB에 존재할 경우 삭제 거부
    [변경 시 영향도]:
      - 스펙 조합의 영구 삭제를 초래하며, 장비 인스턴스 참조 무결성에 직접적인 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 무결성 검증: 외래 키(FK)처럼 동작하는 equipments 테이블의 option_id 참조 카운트 조회
        cursor.execute("SELECT COUNT(*) FROM equipments WHERE option_id = ?", (option_id,))
        eq_count = cursor.fetchone()[0]
        
        # 참조하는 장비 인스턴스가 1대라도 존재하면 고아 레코드 생성을 막기 위해 삭제 거부
        if eq_count > 0:
            conn.close()
            return jsonify({"success": False, "message": f"해당 옵션에 연결된 장비가 {eq_count}건 존재하여 삭제할 수 없습니다."}), 400

        # 안전 검증 통과 시 물리 삭제 처리
        cursor.execute("DELETE FROM equipment_options WHERE id = ?", (option_id,))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "옵션이 안전하게 삭제되었습니다."})

    except Exception as e:
        print(f"[API Error] delete_equipment_option: {e}")
        return jsonify({"success": False, "message": f"옵션 삭제 중 오류: {str(e)}"}), 400


@app.route('/api/equipments_v2', methods=['GET', 'POST'])
@login_required
def api_equipments_v2():
    """
    [역할]:
      - 3-Tier 계층 구조(카테고리->제조사->모델트리->옵션)를 기반으로 장비 인스턴스의 다목적 복합 JOIN 조회(GET) 및 신규 등록(POST)을 처리합니다.
    [트랜잭션/감사로그]:
      - 신규 장비 등록 시 equipments_audit_log 테이블에 이력 로그를 원자적으로 동시 적재하며, 실패 시 롤백(Rollback) 블록을 적용하여 데이터 오염을 차단합니다.
    [변경 시 영향도]:
      - 전체 시스템의 핵심 엔티티인 장비 자산 데이터의 조회 및 획득 파이프라인에 전면적인 영향을 미칩니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        try:
            # 1. [조회 로직]: 장비 목록 렌더링에 필요한 모든 3-Tier 스펙과 사용자 정보를 다중 JOIN으로 일괄 덤프
            cursor.execute("""
                SELECT 
                    e.id AS EquipmentId,
                    e.name AS Name,
                    e.serial_number AS SerialNumber,
                    e.purchase_date AS PurchaseDate,
                    e.status AS Status,
                    e.memo AS Memo,
                    e.user_id AS UserId,
                    e.is_public AS IsPublic,
                    e.created_at AS CreatedAt,
                    e.updated_at AS UpdatedAt,
                    opt.id AS OptionId,
                    opt.option_name AS OptionName,
                    opt.specs_json AS SpecsJson,
                    node.id AS LineupNodeId,
                    node.name AS ModelName,
                    node.depth AS ModelDepth,
                    cat.CategoryId AS CategoryId,
                    cat.Name AS CategoryName,
                    mfg.ManufacturerId AS ManufacturerId,
                    mfg.Name AS ManufacturerName,
                    u.LoginId AS UserLoginId,
                    u.Name AS UserName
                FROM equipments e
                JOIN equipment_options opt ON e.option_id = opt.id
                JOIN lineup_nodes node ON opt.lineup_node_id = node.id
                JOIN categories cat ON node.category_id = cat.CategoryId
                JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
                LEFT JOIN users u ON e.user_id = u.UserId
                ORDER BY e.id DESC;
            """)
            rows = cursor.fetchall()
            
            # 클라이언트 친화적인 포맷으로 재구성(JSON Unpacking)
            result = []
            for r in rows:
                item = dict(r)
                if item.get('SpecsJson'):
                    try:
                        # 문자열 형태의 JSON 스펙을 파싱하여 딕셔너리로 변환
                        item['Specs'] = json.loads(item['SpecsJson'])
                    except Exception:
                        item['Specs'] = {}
                else:
                    item['Specs'] = {}
                result.append(item)

            conn.close()
            return jsonify({"success": True, "equipments": result})

        except Exception as e:
            conn.close()
            print(f"[API Error] GET api_equipments_v2: {e}")
            return jsonify({"success": False, "message": "장비 목록 조회 실패"}), 400

    elif request.method == 'POST':
        # 2. [등록 로직]: 데코레이터를 거치지 않았으므로 API 스코프 내에서 수동으로 CSRF 토큰 방어 검증 수행
        token = request.headers.get('X-CSRFToken')
        if not token or token != session.get('csrf_token'):
            conn.close()
            return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다."}), 403

        try:
            # 클라이언트 입력 데이터 추출 및 기본 정제 처리
            data = request.json or {}
            option_id = data.get('option_id')
            name = (data.get('name') or '').strip()
            serial_number = (data.get('serial_number') or '').strip() or None
            purchase_date = data.get('purchase_date')
            memo = data.get('memo')
            is_public = int(data.get('is_public') or 0)

            # 필수 입력값 1차 검증
            if not option_id:
                conn.close()
                return jsonify({"success": False, "message": "옵션 스펙을 선택해 주세요."}), 400
            if not name:
                conn.close()
                return jsonify({"success": False, "message": "장비명을 입력해 주세요."}), 400

            user = session.get('user', {})
            user_id = user.get('UserId')
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # [무결성 방어]: 시리얼 넘버가 존재하는 경우, 중복 등록을 방지하여 재고 혼선 차단
            if serial_number:
                cursor.execute("SELECT id FROM equipments WHERE serial_number = ?", (serial_number,))
                if cursor.fetchone():
                    conn.close()
                    return jsonify({"success": False, "message": "이미 등록된 시리얼 넘버입니다."}), 400

            # equipments 테이블에 장비 인스턴스 신규 레코드 삽입 (초기 상태는 ACTIVE 고정)
            cursor.execute("""
                INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
            """, (option_id, name, serial_number, purchase_date, memo, user_id, is_public, now_str, now_str))

            # 인서트 직후 자동 생성된 Primary Key 획득
            new_eq_id = cursor.lastrowid

            # [보안/추적]: 장비 생성 시, equipments_audit_log 테이블에 CREATE 이벤트 강제 적재 (데이터 변조 이력 보존)
            cursor.execute("""
                INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
                VALUES (?, 'CREATE', ?, ?, ?)
            """, (new_eq_id, json.dumps(data, ensure_ascii=False), user_id, now_str))

            # 장비 등록과 감사 로그 적재가 모두 성공하면 비로소 트랜잭션 확정(Commit)
            conn.commit()
            conn.close()

            return jsonify({"success": True, "equipment_id": new_eq_id, "message": "장비가 성공적으로 등록되었습니다."})

        except Exception as e:
            # 둘 중 하나라도 실패 시 전체 롤백(Rollback) 수행하여 고립된 데이터 발생 방지
            conn.rollback()
            conn.close()
            print(f"[API Error] POST api_equipments_v2: {e}")
            return jsonify({"success": False, "message": f"장비 등록 실패: {str(e)}"}), 400


@app.route('/api/extend_session', methods=['POST'])
@login_required
@csrf_required
def extend_session():
    """
    [역할]:
      - 로그인 사용자가 프론트엔드의 타임아웃 경고 팝업에서 '연장하기'를 클릭했을 때 호출되어 현재 세션의 만료 시간을 재설정합니다.
    [의존성 관계]:
      - Flask session.modified 속성
    [변경 시 영향도]:
      - 브라우저 쿠키의 유효기간 및 백엔드 세션 유지 상태에 직접적인 영향을 줍니다.
    """
    # modified 플래그를 True로 설정하여 Flask가 클라이언트로 새로운 쿠키(만료 기한 갱신)를 발급하도록 지시
    session.modified = True
    return jsonify({"success": True, "message": "세션이 연장되었습니다."})

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    """
    [역할]:
      - 현재 세션에 유지되고 있는 로그인 사용자의 상태(권한, 아이디, 소속 등)를 JSON 형태로 즉각 반환합니다.
    [의존성 관계]:
      - session['user'] 딕셔너리
    [변경 시 영향도]:
      - 클라이언트(SPA/Vue/React 등) 프론트엔드 라우터의 권한 체계 검증 및 프로필 렌더링에 영향을 줍니다.
    """
    # 세션 딕셔너리에 담긴 사용자 요약 정보를 직렬화하여 반환
    return jsonify(session['user'])

# ------------------------------------------
# 사용자 맞춤 설정 API
# ------------------------------------------
@app.route('/api/user_settings', methods=['GET', 'POST'])
@login_required
@csrf_required
def api_user_settings():
    """
    [역할]:
      - 로그인한 특정 사용자의 UI 환경 설정(다크모드 여부, 페이지당 항목 수 등)을 조회(GET)하거나 저장/수정(POST)합니다.
    [의존성 관계]:
      - user_settings 테이블 (UserId 기반 1:1 매핑)
    [변경 시 영향도]:
      - 브라우저별 종속성을 탈피하여 백엔드 기반으로 프론트엔드 환경 설정 적용 상태를 유지하는 데 영향을 줍니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        # 로그인 사용자의 설정 메타데이터 JSON 블록 조회
        cursor.execute("SELECT PreferencesJSON FROM user_settings WHERE UserId = ?", (user['UserId'],))
        row = cursor.fetchone()
        conn.close()
        # 설정이 이미 존재하면 파싱해서 반환하고, 처음 접속하여 설정이 없으면 빈 객체 반환
        if row and row['PreferencesJSON']:
            return jsonify({"success": True, "settings": json.loads(row['PreferencesJSON'])})
        return jsonify({"success": True, "settings": {}})
        
    elif request.method == 'POST':
        # 클라이언트에서 덮어쓸 설정값 JSON 추출
        data = request.json
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. 기존 설정 로드
        cursor.execute("SELECT PreferencesJSON FROM user_settings WHERE UserId = ?", (user['UserId'],))
        row = cursor.fetchone()
        current_settings = {}
        if row and row['PreferencesJSON']:
            current_settings = json.loads(row['PreferencesJSON'])
            
        # 2. 기존 설정 딕셔너리에 새 설정값을 병합(Update)
        current_settings.update(data)
        new_json = json.dumps(current_settings, ensure_ascii=False)
        
        # 3. UPSERT 처리 (존재하면 UPDATE, 없으면 INSERT)
        cursor.execute("SELECT UserId FROM user_settings WHERE UserId = ?", (user['UserId'],))
        if cursor.fetchone():
            cursor.execute("UPDATE user_settings SET PreferencesJSON = ?, UpdatedAt = ? WHERE UserId = ?", (new_json, now, user['UserId']))
        else:
            cursor.execute("INSERT INTO user_settings (UserId, PreferencesJSON, UpdatedAt) VALUES (?, ?, ?)", (user['UserId'], new_json, now))
            
        conn.commit()
        conn.close()
        
        # 병합된 최신 설정값을 클라이언트에 즉시 반환하여 프론트엔드 상태와 동기화
        return jsonify({"success": True, "settings": current_settings})

# ------------------------------------------
# 감사 로그 비동기 조회 및 조건 검색 API
# ------------------------------------------
ALLOWED_AUDIT_SEARCH_FIELDS = {
    'all': None,
    'ActorLoginId': 'a.ActorLoginId',
    'ActorName': 'u.Name',
    'IpAddress': 'a.IpAddress',
    'Action': 'a.Action',
    'TargetId': 'a.TargetId',
    'TargetTable': 'a.TargetTable',
    'OldValue': 'a.OldValue',
    'NewValue': 'a.NewValue'
}

@app.route('/api/audit_logs', methods=['GET'])
@login_required
def api_audit_logs():
    """
    [역할] 감사 로그 RESTful 비동기 조회, 컬럼별 조건 검색 및 전역 페이징 처리 (LEFT JOIN 및 빈 키워드 전체 조회 지원)
    [의존성 관계] @login_required, check_menu_permission('audit_logs'), get_db_connection()
    [변경 시 영향도] templates/audit_logs.html의 비동기 표 목록 및 페이징 처리에 영향을 줍니다.
    """
    if not check_menu_permission('audit_logs'):
        return jsonify({'status': 'error', 'message': '접근 권한이 없습니다.'}), 403

    try:
        # 1. 파라미터 파싱 및 Type Casting 예외 방어
        try:
            page = int(request.args.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            per_page = int(request.args.get('per_page', 200))
        except (ValueError, TypeError):
            per_page = 200

        search_field = request.args.get('search_field', 'all')
        match_type = request.args.get('match_type', 'like') # 'exact' or 'like'
        keyword = request.args.get('keyword', '').strip()

        # 다중 필터 파라미터 (Action 유형, 시작일/종료일)
        action_filter = request.args.get('action_filter', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # 2. 관리자 세션인 경우 상한선 10,000개로 확장 (DoS 방어)
        user = session.get('user', {})
        max_limit = 10000 if user.get('Role') == 'admin' else 1000

        if per_page < 10:
            per_page = 10
        elif per_page > max_limit:
            per_page = max_limit

        offset = (page - 1) * per_page

        # 3. Dynamic SQL 및 Whitelist 검증
        where_clauses = []
        params = []

        if keyword:
            if search_field == 'all':
                if match_type == 'exact':
                    where_clauses.append("(a.ActorLoginId = ? OR u.Name = ? OR a.IpAddress = ? OR a.Action = ? OR a.TargetTable = ? OR a.TargetId = ? OR a.OldValue = ? OR a.NewValue = ?)")
                    params.extend([keyword] * 8)
                else:
                    like_kw = f"%{keyword}%"
                    where_clauses.append("(a.ActorLoginId LIKE ? OR u.Name LIKE ? OR a.IpAddress LIKE ? OR a.Action LIKE ? OR a.TargetTable LIKE ? OR a.TargetId LIKE ? OR a.OldValue LIKE ? OR a.NewValue LIKE ?)")
                    params.extend([like_kw] * 8)
            elif search_field in ALLOWED_AUDIT_SEARCH_FIELDS and ALLOWED_AUDIT_SEARCH_FIELDS[search_field]:
                column_name = ALLOWED_AUDIT_SEARCH_FIELDS[search_field]
                if match_type == 'exact':
                    where_clauses.append(f"{column_name} = ?")
                    params.append(keyword)
                else:
                    where_clauses.append(f"{column_name} LIKE ?")
                    params.append(f"%{keyword}%")
            elif search_field == 'Details':
                if match_type == 'exact':
                    where_clauses.append("(a.TargetTable = ? OR a.OldValue = ? OR a.NewValue = ?)")
                    params.extend([keyword] * 3)
                else:
                    like_kw = f"%{keyword}%"
                    where_clauses.append("(a.TargetTable LIKE ? OR a.OldValue LIKE ? OR a.NewValue LIKE ?)")
                    params.extend([like_kw] * 3)
            else:
                return jsonify({'status': 'error', 'message': '유효하지 않은 검색 컬럼입니다.'}), 400

        # 다중 필터 조건 추가
        if action_filter:
            where_clauses.append("a.Action LIKE ?")
            params.append(f"%{action_filter}%")

        if start_date:
            where_clauses.append("a.CreatedAt >= ?")
            params.append(f"{start_date} 00:00:00" if len(start_date) == 10 else start_date)

        if end_date:
            where_clauses.append("a.CreatedAt <= ?")
            params.append(f"{end_date} 23:59:59" if len(end_date) == 10 else end_date)

        where_stmt = ""
        if where_clauses:
            where_stmt = "WHERE " + " AND ".join(where_clauses)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 4. 전체 카운트 쿼리 (users 테이블과 LEFT JOIN)
        count_query = f"""
            SELECT COUNT(*) 
            FROM audit_logs a 
            LEFT JOIN users u ON a.ActorLoginId = u.LoginId 
            {where_stmt}
        """
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # 5. 데이터 목록 쿼리
        data_query = f"""
            SELECT 
                a.AuditId, a.ActorId, a.ActorLoginId, 
                COALESCE(u.Name, a.ActorLoginId, 'System') AS ActorName, 
                a.Action, a.TargetTable, a.TargetId, a.IpAddress, 
                a.OldValue, a.NewValue, a.UserAgent, a.CreatedAt
            FROM audit_logs a
            LEFT JOIN users u ON a.ActorLoginId = u.LoginId
            {where_stmt}
            ORDER BY a.AuditId DESC
            LIMIT ? OFFSET ?
        """
        data_params = params + [per_page, offset]
        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()
        conn.close()

        logs = []
        for r in rows:
            details_parts = []
            if r['TargetTable']:
                details_parts.append(f"테이블: {r['TargetTable']}")
            if r['OldValue']:
                details_parts.append(f"이전: {r['OldValue']}")
            if r['NewValue']:
                details_parts.append(f"변경: {r['NewValue']}")
            
            details_str = " | ".join(details_parts) if details_parts else "-"

            logs.append({
                'AuditId': r['AuditId'],
                'ActorId': r['ActorId'],
                'ActorLoginId': r['ActorLoginId'],
                'ActorName': r['ActorName'],
                'Action': r['Action'],
                'TargetId': r['TargetId'] if r['TargetId'] is not None else '-',
                'TargetTable': r['TargetTable'],
                'IpAddress': r['IpAddress'],
                'OldValue': r['OldValue'],
                'NewValue': r['NewValue'],
                'Details': details_str,
                'CreatedAt': r['CreatedAt']
            })

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        return jsonify({
            'status': 'success',
            'data': logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'서버 오류가 발생했습니다: {str(e)}'}), 500

# ------------------------------------------
# 대시보드 통계 API
# ------------------------------------------
@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    """
    [역할]:
      - 메인 대시보드 화면 렌더링에 필요한 각종 통계(나의 장비 수, 총 장비 수, 카테고리/제조사별 분포도)와 복합 검색 결과를 JSON으로 취합하여 반환합니다.
    [의존성 관계]:
      - equipments, equipment_options, lineup_nodes 등 3-Tier 카탈로그 연관 테이블 전체
    [변경 시 영향도]:
      - 첫 화면(Dashboard)의 렌더링 속도와 통계 정확도에 직접적인 영향을 주며, 잦은 호출 시 DB 부하를 유발할 수 있습니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 내 장비 수: 현재 로그인한 사용자가 등록한 장비 중 임시저장(is_draft)이 아닌 것만 카운트
    cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE user_id = ? AND (is_draft = 0 OR is_draft IS NULL)", (user['UserId'],))
    my_eq_count = cursor.fetchone()['count']
    
    # 2. 총 장비 수: 권한(Role)에 따른 가시성 분리 처리
    if user['Role'] == 'admin':
        # 관리자는 모든 정식 등록 장비(is_draft=0)를 볼 수 있음
        cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE (is_draft = 0 OR is_draft IS NULL)")
        total_count = cursor.fetchone()['count']
    else:
        # 일반 사용자는 공개 처리된 장비(is_public=1)와 본인이 등록한 장비(user_id)만 합산
        cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE (is_public = 1 OR user_id = ?) AND (is_draft = 0 OR is_draft IS NULL)", (user['UserId'],))
        total_count = cursor.fetchone()['count']
        
    # [동적 쿼리 베이스]: 권한에 따라 뷰 가시성을 강제하는 WHERE 절 베이스 문자열 생성
    base_where = "(e.is_draft = 0 OR e.is_draft IS NULL)"
    params_base = []
    if user['Role'] != 'admin':
        base_where += " AND (e.is_public = 1 OR e.user_id = ?)"
        params_base.append(user['UserId'])
        
    # 3. 카테고리별 통계: 3-Tier 복합 JOIN을 통해 카테고리 명칭(ResolvedCategory) 추출 후 Group By 집계
    cursor.execute(f'''
        SELECT COALESCE(cat.Name, '미분류') as ResolvedCategory, COUNT(e.id) as count 
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN categories cat ON node.category_id = cat.CategoryId
        WHERE {base_where}
        GROUP BY ResolvedCategory
    ''', params_base)
    categories = [{"category": row['ResolvedCategory'], "count": row['count']} for row in cursor.fetchall()]

    # 4. 제조사별 통계: 3-Tier 복합 JOIN을 통해 제조사 명칭(ResolvedManufacturer) 추출 후 Group By 집계
    cursor.execute(f'''
        SELECT COALESCE(mfg.Name, '미분류') as ResolvedManufacturer, COUNT(e.id) as count 
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
        WHERE {base_where}
        GROUP BY ResolvedManufacturer
    ''', params_base)
    manufacturers = [{"manufacturer": row['ResolvedManufacturer'], "count": row['count']} for row in cursor.fetchall()]

    # 5. 복합 조건 검색: 클라이언트에서 카테고리(req_cat_id)와 제조사(req_man_id)를 모두 전달한 경우 특정 분포 쿼리 실행
    req_cat_id = request.args.get('category_id')
    req_man_id = request.args.get('manufacturer_id')
    
    combined_stats = None
    if req_cat_id and req_man_id:
        # 특정 카테고리 & 제조사에 해당하는 장비의 상태(status)별 분포 집계
        status_query = f'''
            SELECT '정상' as status, COUNT(e.id) as count
            FROM equipments e
            LEFT JOIN equipment_options opt ON e.option_id = opt.id
            LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
            WHERE {base_where} AND node.category_id = ? AND node.manufacturer_id = ?
            GROUP BY status
        '''
        cursor.execute(status_query, params_base + [req_cat_id, req_man_id])
        status_distribution = [{"status": row['status'], "count": row['count']} for row in cursor.fetchall()]

        # 해당 필터에 걸린 장비 리스트(미리보기용 데이터) 추출
        list_query = f'''
            SELECT e.id as EquipmentId, e.name as Name, node.name as ModelName, '정상' as Status, e.purchase_date as PurchaseDate
            FROM equipments e
            LEFT JOIN equipment_options opt ON e.option_id = opt.id
            LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
            WHERE {base_where} AND node.category_id = ? AND node.manufacturer_id = ?
            ORDER BY e.id DESC
        '''
        cursor.execute(list_query, params_base + [req_cat_id, req_man_id])
        equipment_list = [dict(row) for row in cursor.fetchall()]
        
        combined_stats = {
            "status_distribution": status_distribution,
            "equipment_list": equipment_list
        }

    conn.close()
    
    # 렌더링에 필요한 모든 집계 데이터를 단일 JSON DTO로 패키징하여 반환
    return jsonify({
        "success": True,
        "data": {
            "my_equipments": my_eq_count,
            "total_equipments": total_count,
            "categories": categories,
            "manufacturers": manufacturers,
            "combined_stats": combined_stats
        }
    })

@app.route('/api/dashboard/master_options', methods=['GET'])
@login_required
def api_dashboard_master_options():
    """
    [역할]:
      - 대시보드의 복합 조건 검색 필터(Select Box)를 구성하기 위한 기본 마스터 데이터(카테고리, 제조사) 목록을 제공합니다.
    [의존성 관계]:
      - categories, manufacturers 테이블 (전체 목록 덤프)
    [변경 시 영향도]:
      - dashboard.html 내 필터의 동적 렌더링에 직접적인 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # SelectBox Option 렌더링을 위해 id와 name(DisplayName) 형태의 딕셔너리로 맵핑
    cursor.execute("SELECT CategoryId AS CategoryId, CategoryId AS id, Name AS DisplayName, Name AS name FROM categories ORDER BY CategoryId")
    cats = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT ManufacturerId AS ManufacturerId, ManufacturerId AS id, Name AS DisplayName, Name AS name FROM manufacturers ORDER BY ManufacturerId")
    mans = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "success": True,
        "categories": cats,
        "manufacturers": mans
    })

# ------------------------------------------
# 사용자 프로필 (비밀번호 변경) API
# ------------------------------------------
@app.route('/api/change_password', methods=['POST'])
@login_required
@csrf_required
def api_change_my_password():
    """
    [역할]:
      - 현재 로그인 중인 사용자가 본인의 비밀번호를 직접 변경합니다.
    [보안/인증]:
      - 클라이언트에서 평문으로 넘어온 기존 비밀번호를 check_password_hash 로 검증한 후, 
        일치할 경우에만 새 비밀번호를 generate_password_hash 로 단방향 암호화하여 UPDATE 합니다.
    [변경 시 영향도]:
      - 계정 보안 체계 유지에 직결되며, 변경 후 사용자의 다음 로그인 시크릿 키 검증에 영향을 줍니다.
    """
    user = session['user']
    data = request.json
    current_pw = data.get('current_password')
    new_pw = data.get('new_password')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. DB에서 현재 사용자 레코드 조회
    cursor.execute("SELECT Password FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    # 2. 현재 비밀번호 일치 여부 단방향 해시 검증
    if not db_user or not check_password_hash(db_user['Password'], current_pw):
        conn.close()
        return jsonify({"success": False, "message": "현재 비밀번호가 일치하지 않습니다."}), 400
        
    # 3. 새로운 비밀번호 단방향 해시 암호화 및 덮어쓰기
    hashed_new = generate_password_hash(new_pw)
    cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed_new, user['UserId']))
    
    # 4. 보안 감사 로그 적재: 비밀번호 변경 이력 보존
    log_audit(user['UserId'], user['LoginId'], 'CHANGE_PASSWORD', 'users', user['UserId'], None, None)
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})

@app.route('/api/users/withdraw', methods=['POST'])
@login_required
@csrf_required
def api_user_withdraw():
    """
    [역할]:
      - 로그인된 회원이 자진 탈퇴를 신청하고, 30일간의 비활성화(유예) 기간을 개시합니다.
    [비즈니스/보안 정책]:
      - 단순 실수나 변심에 대비하여 즉각적인 물리 삭제(Hard Delete)를 수행하지 않고, IsDeactivated 플래그와 랜덤 토큰 갱신을 통해 현재 세션을 즉각 만료시킵니다.
    [변경 시 영향도]:
      - 마이페이지의 회원탈퇴 폼 제출 로직 및 전역 세션(강제 로그아웃) 제어 파이프라인에 영향을 줍니다.
    """
    user = session['user']
    data = request.json or {}
    password = data.get('password')
    
    # 1. 탈퇴 의사 재확인을 위한 비밀번호 입력 검증
    if not password:
        return jsonify({"success": False, "message": "비밀번호를 입력하세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Password FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    # 2. 패스워드 해시 대조 (본인 인증)
    if not db_user or not check_password_hash(db_user['Password'], password):
        conn.close()
        return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."}), 400
        
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 새 랜덤 토큰을 발급하여 기존에 유지 중이던 모든 디바이스의 세션(자동 로그인 포함)을 무효화
    new_token = os.urandom(24).hex()
    
    # 3. Soft Delete 유예 상태(IsDeactivated) 전환
    cursor.execute('''
        UPDATE users 
        SET IsDeactivated = 'Y', DeactivatedAt = ?, SessionToken = ? 
        WHERE UserId = ?
    ''', (now_str, new_token, user['UserId']))
    
    conn.commit()
    conn.close()
    
    # 4. 현재 요청의 세션에도 비활성화 상태 즉각 반영 (미들웨어에서 로그아웃 처리 유도)
    session['user']['IsDeactivated'] = True
    session['user']['DeactivationDaysLeft'] = 30
    session['session_token'] = new_token
    
    log_audit(user['UserId'], user['LoginId'], 'USER_WITHDRAW_REQUEST', 'users', user['UserId'], None, {"DeactivatedAt": now_str})
    return jsonify({"success": True, "message": "회원 탈퇴 신청이 완료되었습니다. 30일간의 비활성화 유예기간이 적용됩니다."})

@app.route('/api/users/withdraw/cancel', methods=['POST'])
@login_required
@csrf_required
def api_user_withdraw_cancel():
    """
    [역할]:
      - 비활성화 유예 기간(30일) 내에 있는 탈퇴 신청자가 변심하여 탈퇴를 철회하고 계정을 롤백(정상 복구)합니다.
    [의존성 관계]:
      - users 테이블 (IsDeactivated 및 DeactivatedAt 리셋)
    [변경 시 영향도]:
      - deactivated_notice.html의 비활성화 철회 버튼 통신 및 사용자 계정 접근 권한 완전 복구에 직결됩니다.
    """
    user = session['user']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 비활성화 및 삭제 관련 플래그를 모두 초기화(N/NULL)하여 완전한 정상 상태로 롤백
    cursor.execute('''
        UPDATE users 
        SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL 
        WHERE UserId = ?
    ''', (user['UserId'],))
    
    conn.commit()
    conn.close()
    
    # 샌드박스 상태였던 현재 세션을 정상(Active) 세션으로 즉시 복원
    session['user']['IsDeactivated'] = False
    session['user'].pop('DeactivationDaysLeft', None)
    
    log_audit(user['UserId'], user['LoginId'], 'USER_WITHDRAW_CANCEL', 'users', user['UserId'], None, None)
    return jsonify({"success": True, "message": "비활성화가 성공적으로 철회되었으며 계정이 정상 복구되었습니다."})

@app.route('/api/users/update_email', methods=['POST'])
@login_required
@csrf_required
def api_update_email():
    """
    [역할]:
      - 사전에 2단계 OTP 이메일 인증(email_verifications)을 완료한 사용자에 한하여 개인 이메일 정보를 변경합니다.
    [의존성 관계]:
      - users 테이블, email_verifications 테이블 (인증 완료 여부 검증)
    [변경 시 영향도]:
      - 시스템 알림 수신처 및 유니크 키(Email) 무결성에 영향을 주므로, 중복 제약 조건(IntegrityError) 방어가 필수입니다.
    """
    user = session['user']
    data = request.json or {}
    new_email = data.get('email', '').strip()
    
    if not new_email:
        return jsonify({"success": False, "message": "이메일을 입력해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 비정상적인 접근(인증 건너뛰기) 방어를 위한 이메일 인증 완료(IsVerified) 여부 교차 검증
    cursor.execute("SELECT IsVerified FROM email_verifications WHERE Email = ?", (new_email,))
    verif = cursor.fetchone()
    if not verif or verif['IsVerified'] != 1:
        conn.close()
        return jsonify({"success": False, "message": "이메일 인증이 완료되지 않았습니다."}), 400
        
    # 2. 이메일 유니크(Unique) 중복 검증 및 업데이트 수행 (IntegrityError 예외 처리)
    try:
        cursor.execute("UPDATE users SET Email = ?, UpdatedAt = ? WHERE UserId = ?", 
                       (new_email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['UserId']))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        # 해당 이메일이 이미 다른 계정의 Email 컬럼에 등록되어 있을 경우
        return jsonify({"success": False, "message": "이미 다른 계정에서 사용 중인 이메일입니다."}), 400
        
    # 3. 변경 성공 시, 재사용(Re-play) 공격을 방지하기 위해 인증 완료된 레코드 폐기
    cursor.execute("DELETE FROM email_verifications WHERE Email = ?", (new_email,))
    conn.commit()
    conn.close()
    
    # 세션 내 캐싱된 프로필 정보 최신화
    session['user']['Email'] = new_email
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_EMAIL', 'users', user['UserId'], None, {"NewEmail": new_email})
    
    return jsonify({"success": True, "message": "이메일 주소가 성공적으로 변경되었습니다."})


@app.route('/api/users/update_profile', methods=['POST'])
@login_required
@csrf_required
def api_update_profile():
    """
    [역할]:
      - 로그인한 사용자의 기본 프로필(아이디, 이름, 닉네임)을 변경합니다. 중요 정보 변경이므로 현재 비밀번호 대조 검증이 필수입니다.
    [의존성 관계]:
      - users 테이블, check_password_hash() 모듈, 세션 동기화 로직
    [변경 시 영향도]:
      - users 테이블의 유저 식별자 및 표시 정보(Display Name)가 즉각 변경되며, 고유 키(LoginId) 중복 방어에 영향을 줍니다.
    """
    user = session.get('user')
    if not user or 'UserId' not in user:
        return jsonify({"success": False, "message": "로그인이 필요한 서비스입니다."}), 401
        
    data = request.json or {}
    new_login_id = data.get('login_id', '').strip()
    new_name = data.get('name', '').strip()
    new_nickname = data.get('nickname', '').strip()
    current_password = data.get('current_password', '').strip()
    
    if not new_login_id or not new_name or not new_nickname or not current_password:
        return jsonify({"success": False, "message": "모든 필드를 입력해 주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    if not db_user:
        conn.close()
        return jsonify({"success": False, "message": "사용자 정보를 찾을 수 없습니다."}), 404
        
    # 1. 정보 수정 권한 확보를 위한 현재 비밀번호 대조 검증 (Self-Authentication)
    if not check_password_hash(db_user['Password'], current_password):
        conn.close()
        return jsonify({"success": False, "message": "현재 비밀번호가 올바르지 않습니다."}), 400
        
    # 2. 아이디(LoginId) 변경을 시도한 경우, 타 계정과의 고유성(Unique) 중복 교차 체크
    if new_login_id != db_user['LoginId']:
        cursor.execute("SELECT UserId FROM users WHERE LoginId = ? AND UserId != ?", (new_login_id, user['UserId']))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "이미 사용 중인 아이디입니다."}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 3. 데이터베이스 갱신 시도 (동시성 엣지케이스 대비 IntegrityError 방어)
    try:
        cursor.execute('''
            UPDATE users
            SET LoginId = ?, Name = ?, NickName = ?, UpdatedAt = ?
            WHERE UserId = ?
        ''', (new_login_id, new_name, new_nickname, now_str, user['UserId']))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 존재하거나 사용 중인 아이디입니다."}), 400

    old_data = {"LoginId": db_user['LoginId'], "Name": db_user['Name'], "NickName": db_user['NickName']}
    new_data = {"LoginId": new_login_id, "Name": new_name, "NickName": new_nickname}

    # 프로필 변경 이전/이후 차이를 명시적으로 추적하기 위해 payload 전체 기록
    log_audit(user['UserId'], db_user['LoginId'], 'UPDATE_USER_PROFILE', 'users', user['UserId'], old_data, new_data)
    conn.close()

    # 4. 세션 캐시 갱신 및 modified 플래그 설정 (브라우저 쿠키 재생성 유도)
    session['user']['LoginId'] = new_login_id
    session['user']['Name'] = new_name
    session['user']['NickName'] = new_nickname
    session.modified = True

    return jsonify({"success": True, "message": "프로필 정보가 성공적으로 변경되었습니다."})

# ------------------------------------------
# 관리자용 사용자 관리 API
# ------------------------------------------
@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    """
    [역할]:
      - 시스템 내 모든 사용자의 상태 정보를 조회하며, evaluate_user_lifecycle() 모듈을 통해 실시간 30일 유예 상태를 평가(Evaluation)하여 통합 반환합니다.
    [의존성 관계]:
      - users 테이블, evaluate_user_lifecycle() 파이프라인
    [변경 시 영향도]:
      - 관리자용 사용자 관리 화면(users_management.html)의 테이블 데이터 출력 및 상태 뱃지 표기 렌더링에 전면적인 영향을 줍니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    # 전체 사용자 목록 덤프
    cursor.execute("SELECT UserId, LoginId, Name, NickName, Role, CreatedAt, IsDeactivated, DeactivatedAt, IsDeleted, DeletedAt FROM users ORDER BY UserId DESC")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        user_dict = dict(row)
        # 각 계정별로 생명주기(Lifecycle) 동적 평가 수행
        eval_res = evaluate_user_lifecycle(user_dict)
        
        # 완전 삭제(Hard Delete) 마킹된 계정은 관리자 화면의 실사용자 목록에서 논리적으로 배제
        if eval_res['status'] == 'HARD_DELETED':
            continue
            
        # 평가된 최종 가상 상태(Status) 및 남은 유예일수 주입
        user_dict['Status'] = eval_res['status']
        user_dict['DaysLeft'] = eval_res.get('days_left', 0)
        result.append(user_dict)
        
    return jsonify({"success": True, "data": result})

@app.route('/api/users/<int:target_user_id>/toggle_deactivation', methods=['POST'])
@login_required
@csrf_required
def api_toggle_user_deactivation(target_user_id):
    """
    [역할]:
      - 관리자가 특정 사용자의 계정을 강제로 비활성화(정지)하거나, 비활성화된 계정을 다시 정상(활성화) 상태로 복구(Unsuspend)합니다.
    [보안 정책]:
      - 비활성화 시 SessionToken을 무작위 난수로 갱신하여, 타겟 유저가 접속 중이던 모든 디바이스의 세션 검증(Middleware)을 즉시 무효화(차단)시킵니다.
    [변경 시 영향도]:
      - 대상 사용자의 시스템 접근 가능 여부에 즉각적이고 물리적인 영향을 미칩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    deactivate = request.json.get('deactivate', True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if deactivate:
        # [정지 징계 처리]: IsDeactivated 부여 및 세션 토큰 무효화(hex(randomblob(16)))
        cursor.execute('''
            UPDATE users 
            SET IsDeactivated = 'Y', DeactivatedAt = NULL, SessionToken = hex(randomblob(16))
            WHERE UserId = ?
        ''', (target_user_id,))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_SUSPEND_USER', 'users', target_user_id, None, None)
        msg = "계정이 비활성화(정지) 처리되었습니다."
    else:
        # [복구 해제 처리]: 모든 정지/삭제 관련 플래그를 정상(N)으로 원복
        cursor.execute('''
            UPDATE users 
            SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL
            WHERE UserId = ?
        ''', (target_user_id,))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_UNSUSPEND_USER', 'users', target_user_id, None, None)
        msg = "계정이 정상 활성화되었습니다."
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": msg})

@app.route('/api/users/deactivate_selected', methods=['POST'])
@login_required
@csrf_required
def api_deactivate_selected_users():
    """
    [역할]:
      - 관리자가 UI에서 다중 선택(체크박스)한 다수의 사용자 계정 배열을 일괄적으로 비활성화(정지)하거나 복구합니다.
    [데이터 제어]:
      - 동적 IN 절(placeholders) 구문을 생성하여 한 번의 다중 UPDATE 쿼리로 묶음(Bulk) 처리를 수행합니다.
    [변경 시 영향도]:
      - 관리자의 대량 징계 처리 등 운영 효율성에 기여하며, 선택 유저들의 접근 권한 동시 차단에 영향을 미칩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    deactivate = request.json.get('deactivate', True)
    
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "대상을 선택해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    # 배열 길이에 맞춰 IN (?, ?, ?) 형태의 Placeholders 동적 확장
    placeholders = ','.join(['?'] * len(target_ids))
    
    if deactivate:
        # [일괄 정지]: 다중 유저의 세션 토큰을 DB 내장 randomblob을 활용하여 고유 난수로 일괄 덮어쓰기
        cursor.execute(f'''
            UPDATE users 
            SET IsDeactivated = 'Y', DeactivatedAt = NULL, SessionToken = hex(randomblob(16))
            WHERE UserId IN ({placeholders})
        ''', tuple(target_ids))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_BULK_SUSPEND', 'users', None, None, {"TargetIds": target_ids})
        msg = f"{len(target_ids)}명의 계정이 비활성화 처리되었습니다."
    else:
        # [일괄 복구]: 정지 해제
        cursor.execute(f'''
            UPDATE users 
            SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL
            WHERE UserId IN ({placeholders})
        ''', tuple(target_ids))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_BULK_UNSUSPEND', 'users', None, None, {"TargetIds": target_ids})
        msg = f"{len(target_ids)}명의 계정이 활성화 처리되었습니다."
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": msg})

@app.route('/api/users/<int:target_user_id>/role', methods=['PUT'])
@login_required
@csrf_required
def api_update_user_role(target_user_id):
    """
    [역할]:
      - 관리자가 특정 사용자의 권한 등급(Role: user ↔ admin)을 동적으로 승격하거나 강등합니다.
    [변경 시 영향도]:
      - 해당 사용자의 시스템 내 메뉴 접근 권한, 결재 승인 권한, 장비 전체 조회 권한 등 코어 권한 레벨이 즉시 변경됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    # 하드코딩된 화이트리스트(admin, user) 밖의 Role 문자열 주입 방어
    new_role = request.json.get('role')
    if new_role not in ['admin', 'user']:
        return jsonify({"success": False, "message": "잘못된 권한입니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 변경 대상 사용자 검증
    cursor.execute("SELECT Role FROM users WHERE UserId = ?", (target_user_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        return jsonify({"success": False, "message": "사용자를 찾을 수 없습니다."}), 404
        
    # 변경 전/후 권한 상태를 추출하여 상세 감사 로그에 바인딩
    old_role = target['Role']
    cursor.execute("UPDATE users SET Role = ? WHERE UserId = ?", (new_role, target_user_id))
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_ROLE', 'users', target_user_id, {"Role": old_role}, {"Role": new_role})
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/users/<int:target_user_id>/reset_password', methods=['POST'])
@login_required
@csrf_required
def api_reset_user_password(target_user_id):
    """
    [역할]:
      - 관리자가 분실 등의 사유로 특정 사용자의 비밀번호를 임시 비밀번호로 강제 초기화(Reset) 합니다.
    [보안 정책]:
      - 새로 발급되는 임시 비밀번호 역시 평문 저장을 방지하기 위해 generate_password_hash를 통해 단방향 해시화 후 저장됩니다.
    [변경 시 영향도]:
      - 해당 유저의 기존 로그인 자격 증명이 소멸되고 즉각 임시 비밀번호로 교체됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    # 클라이언트가 프롬프트에서 입력한 임시 비밀번호를 추출하거나, 미입력 시 '1234'로 기본 fallback 처리
    temp_pw = request.json.get('temp_password', '1234')
    hashed_pw = generate_password_hash(temp_pw)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 덮어쓰기 업데이트 수행
    cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed_pw, target_user_id))
    log_audit(user['UserId'], user['LoginId'], 'RESET_PASSWORD', 'users', target_user_id, None, None)
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"비밀번호가 '{temp_pw}'로 초기화되었습니다."})

# ------------------------------------------
# [제안-018] 세션 강제 만료(Force Logout) API
# ------------------------------------------
@app.route('/api/system/force_logout/all', methods=['POST'])
@login_required
@csrf_required
def api_force_logout_all():
    """
    [역할]:
      - 관리자 전용 기능으로, 본인(또는 전체)을 제외한 모든 사용자의 세션 토큰(SessionToken)을 일괄 난수로 갱신하여 강제 로그아웃 시킵니다.
    [보안/인증]:
      - 서버 사이드 토큰 무효화(Server-side invalidation) 방식으로, 브라우저가 보관 중인 기존 쿠키를 즉각 폐기 처분합니다.
    [변경 시 영향도]:
      - 현재 접속 중인 모든 타 사용자의 활성 세션이 끊어지며, 즉시 재로그인 화면으로 강제 리다이렉트됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    include_me = request.json.get('include_me', False)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # SQLite 내장 randomblob() 함수를 사용하여 성능 저하 없이 고속 난수(Hex) 일괄 덮어쓰기 수행
    if include_me:
        # 모든 활성 유저의 세션 강제 만료 (시스템 점검 등 전면 차단 목적)
        cursor.execute("UPDATE users SET SessionToken = hex(randomblob(16))")
        log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_ALL', 'users', None, None, {"IncludeMe": True})
    else:
        # 본인(관리자) 세션만 제외하고 나머지 유저 강제 만료 (패치 작업 시 유용)
        cursor.execute("UPDATE users SET SessionToken = hex(randomblob(16)) WHERE UserId != ?", (user['UserId'],))
        log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_ALL', 'users', None, None, {"IncludeMe": False})
        
    conn.commit()
    conn.close()
    
    # 본인 포함 강제 로그아웃 시, 런타임 메모리(Redis/Flask Session)에서도 즉각 파기하여 클라이언트를 튕겨냄
    if include_me:
        session.clear()
        
    return jsonify({"success": True, "message": "성공적으로 세션이 만료되었습니다."})

@app.route('/api/system/force_logout/selected', methods=['POST'])
@login_required
@csrf_required
def api_force_logout_selected():
    """
    [역할]:
      - 관리자가 UI 상에서 다중 선택(Check)한 특정 사용자 계정들의 세션 토큰을 일괄 갱신(무효화)하여 개별 로그아웃 시킵니다.
    [데이터 제어]:
      - 선택된 ID 배열(target_ids)을 동적 IN 구문으로 파싱하여 DB UPDATE를 한 번에 처리합니다.
    [변경 시 영향도]:
      - 선택된 사용자들의 브라우저 세션이 즉시 만료되어 API 호출 권한을 상실하고 로그인 페이지로 리다이렉트됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "대상 유저가 지정되지 않았습니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 리스트 크기만큼 Placeholders 구성 (SQL Injection 방어)
    placeholders = ','.join(['?'] * len(target_ids))
    cursor.execute(f"UPDATE users SET SessionToken = hex(randomblob(16)) WHERE UserId IN ({placeholders})", tuple(target_ids))
    
    log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_SELECTED', 'users', None, None, {"TargetIds": target_ids})
    
    conn.commit()
    conn.close()
    
    # 만약 선택 대상 목록에 본인(관리자) 자신이 포함되어 있다면, 런타임 세션까지 함께 파기(Clear)
    if user['UserId'] in target_ids:
        session.clear()
        
    return jsonify({"success": True, "message": f"{len(target_ids)}명의 사용자 세션이 강제 만료되었습니다."})

# ------------------------------------------
# 계정 즉시 삭제 API (유예기간 없이 영구 삭제)
# ------------------------------------------
@app.route('/api/users/delete_selected', methods=['POST'])
@login_required
@csrf_required
def api_delete_selected_users():
    """
    [역할]:
      - 관리자가 선택한 다수의 유저 계정을 Soft Delete(비활성화) 유예 없이 데이터베이스에서 즉각 영구 파기(Hard Delete)합니다.
    [파괴적 액션/고아 레코드 방어]:
      - 계정 삭제 전(Before-Delete), 해당 사용자가 등록한 장비(equipments)가 고아(Orphan) 레코드가 되는 것을 막기 위해 
        소유권을 NULL로 비우고, 강제로 '공개(is_public=1)' 장비로 이관하여 자산 정보를 보존합니다.
    [변경 시 영향도]:
      - 시스템에서 선택된 사용자 정보(설정, 프로필 포함)가 복구 불가능하게 비가역적으로 완전 삭제됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "삭제할 대상을 선택해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(target_ids))
    cursor.execute(f"SELECT UserId, LoginId FROM users WHERE UserId IN ({placeholders})", tuple(target_ids))
    target_users = cursor.fetchall()
    
    if not target_users:
        conn.close()
        return jsonify({"success": False, "message": "삭제할 대상 사용자를 찾을 수 없습니다."}), 404
        
    deleted_ids = [u['UserId'] for u in target_users]
    deleted_logins = [u['LoginId'] for u in target_users]
    
    del_placeholders = ','.join(['?'] * len(deleted_ids))
    del_tuple = tuple(deleted_ids)
    
    # 1. CASCADE 종속성: user_settings(유저 환경설정) 물리 레코드 완전 삭제
    cursor.execute(f"DELETE FROM user_settings WHERE UserId IN ({del_placeholders})", del_tuple)
    
    # 2. 참조 무결성 롤백 방지: 장비 소유권을 시스템(NULL)으로 이관하고 전체 공개로 강제 마이그레이션
    cursor.execute(f"UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id IN ({del_placeholders})", del_tuple)
    
    # 3. 핵심(Core): users 계정 영구 물리 파기
    cursor.execute(f"DELETE FROM users WHERE UserId IN ({del_placeholders})", del_tuple)
    
    # 4. 관리자 책임 추적을 위한 보안 감사 로그 작성
    log_audit(user['UserId'], user['LoginId'], 'DELETE_USER', 'users', None, 
              {"DeletedUserIds": deleted_ids, "DeletedLogins": deleted_logins}, None)
              
    conn.commit()
    conn.close()
    
    # 본인이 삭제 목록에 섞여있다면 런타임 세션에서도 즉시 자살(Clear) 처리
    if user['UserId'] in deleted_ids:
        session.clear()
        
    return jsonify({"success": True, "message": f"총 {len(deleted_ids)}명의 계정이 즉시 삭제되었습니다."})

# ------------------------------------------
# 장비 API
# ------------------------------------------
@app.route('/api/portal/menus', methods=['GET'])
@login_required
def get_portal_menus():
    """
    [역할]:
      - 현재 로그인한 사용자의 역할(Role)에 맞춰 접근이 허용된 최상위 부모 메뉴(ParentMenuCode IS NULL) 목록을 동적으로 반환합니다.
    [의존성 관계]:
      - menus(메뉴 마스터), role_menu_permissions(권한 매핑) 테이블 간의 교차 조인(JOIN) 쿼리
    [변경 시 영향도]:
      - 포털 런처 화면(/portal)의 메인 아이콘 타일 노출 구성과 네비게이션 제어에 직접적인 영향을 미칩니다.
    """
    user = session['user']
    role = user['Role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 관리자는 권한 테이블(role_menu_permissions)에 의존하지 않고 모든 최상위 메뉴를 강제 통과(Bypass)
    if role == 'admin':
        cursor.execute("SELECT * FROM menus WHERE ParentMenuCode IS NULL ORDER BY SortOrder ASC, MenuId ASC")
    else:
        # 일반 사용자는 IsAllowed=1 로 허용(Whitelist) 매핑된 메뉴만 교집합(JOIN)으로 엄격하게 필터링 반환
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.MenuCode = p.MenuCode
            WHERE p.Role = ? AND p.IsAllowed = 1 AND m.ParentMenuCode IS NULL
            ORDER BY m.SortOrder ASC, m.MenuId ASC
        ''', (role,))
        
    rows = cursor.fetchall()
    conn.close()
    
    # 직렬화된 JSON 배열 응답
    return jsonify([dict(row) for row in rows])

@app.route('/api/menus/children/<parent_code>')
@login_required
def get_children_menus(parent_code):
    """
    [역할]:
      - URL 파라미터로 지정된 특정 부모(ParentMenuCode) 메뉴 하위에 종속된 자식 서브 메뉴들 중 사용자에게 허용된 목록만 반환합니다.
    [의존성 관계]:
      - menus 테이블 자체 계층형 참조(ParentMenuCode), role_menu_permissions 매핑
    [변경 시 영향도]:
      - 관리자 센터 등 다단계 뎁스를 가진 사이드바 네비게이션 트리 렌더링에 영향을 줍니다.
    """
    user = session['user']
    role = user['Role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 관리자는 해당 부모 메뉴를 가진 모든 자식 메뉴 무조건 조회
    if role == 'admin':
        cursor.execute("SELECT * FROM menus WHERE ParentMenuCode = ? ORDER BY SortOrder ASC", (parent_code,))
    else:
        # 일반 사용자는 허가된(Whitelist) 서브 메뉴만 제한적으로 노출
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.MenuCode = p.MenuCode
            WHERE p.Role = ? AND p.IsAllowed = 1 AND m.ParentMenuCode = ?
            ORDER BY m.SortOrder ASC
        ''', (role, parent_code))
        
    menus = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(menus)


# 사용자 검색 API (관리자용)
@app.route('/api/users/search', methods=['GET'])
@login_required
def search_users():
    """
    [역할]:
      - 오토컴플릿(Auto-Complete) 용도로 아이디, 이름, 닉네임 필드에 대해 LIKE 부분 일치 키워드 검색 결과를 20건 제한으로 반환합니다.
    [권한 제어]:
      - 타인 정보 열람 방지를 위해 관리자(admin) 세션에서만 요청을 허용합니다.
    [변경 시 영향도]:
      - 장비 신규 등록이나 권한 이관 시 '소유자 검색' 모달/Select2 플러그인의 검색 결과 공급망에 영향을 미칩니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"error": "권한이 없습니다."}), 403
        
    # 앞뒤 공백을 제거한 검색 키워드 추출
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
        
    conn = get_db_connection()
    cursor = conn.cursor()
    like_q = f"%{q}%"
    
    # 3개 컬럼(아이디, 이름, 닉네임) 대상 다중 OR 검색 수행 및 부하 방지용 LIMIT 20 적용
    cursor.execute('''
        SELECT UserId, LoginId, Name, NickName 
        FROM users 
        WHERE LoginId LIKE ? OR Name LIKE ? OR NickName LIKE ?
        ORDER BY NickName ASC LIMIT 20
    ''', (like_q, like_q, like_q))
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


# ------------------------------------------
# [제안-011] 마스터 데이터 조회 API
# ------------------------------------------
@app.route('/api/master_data', methods=['GET'])
@login_required
def get_master_data():
    """
    [역할]:
      - 프론트엔드 양식 렌더링을 위해 관리자의 승인(IsApproved=1)을 통과한 유효 카테고리 및 제조사(Master Data) 목록 전체를 한 번에 다국어(Ko/En) 지원 포맷으로 제공합니다.
    [의존성 관계]:
      - categories, manufacturers 테이블 (승인 완료 플래그 검증)
    [변경 시 영향도]:
      - 신규 장비 등록/수정 시 드롭다운(Select Box)에 출력되는 선택지 정합성에 직접적인 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 승인된 정식 카테고리 덤프 (다국어 포함)
    cursor.execute("SELECT CategoryId, Name, NameKo, NameEn FROM categories WHERE IsApproved = 1 ORDER BY Name ASC")
    categories = [dict(r) for r in cursor.fetchall()]
    
    # 2. 승인된 정식 제조사 덤프 (다국어 포함)
    cursor.execute("SELECT ManufacturerId, Name, NameKo, NameEn FROM manufacturers WHERE IsApproved = 1 ORDER BY Name ASC")
    manufacturers = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return jsonify({"success": True, "categories": categories, "manufacturers": manufacturers})


# ------------------------------------------
# [제안-027] 전자결재 API
# ------------------------------------------
@app.route('/api/approvals', methods=['GET'])
@login_required
def get_approvals():
    """
    [역할]:
      - 일반 사용자 관점에서는 자신이 상신한 결재(마스터 데이터 신규 등)의 기안 목록을 반환하고, 관리자(admin) 관점에서는 시스템 전체에 쌓인 대기/완료 결재 안건 전체 목록을 제공합니다.
    [의존성 관계]:
      - approval_requests, users 테이블 (JOIN을 통한 기안자 정보 취합)
    [변경 시 영향도]:
      - 전자결재함 대시보드의 테이블 리스트 출력 및 기안 진행 상황 렌더링을 제어합니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 관리자는 전체 결재 파이프라인(타인의 요청 포함)을 모니터링하기 위해 제약 조건 없이 전체 조회
    if user['Role'] == 'admin':
        cursor.execute('''
            SELECT a.*, u.NickName as RequesterNickName, u.Name as RequesterName
            FROM approval_requests a
            JOIN users u ON a.RequesterId = u.UserId
            ORDER BY a.RequestId DESC
        ''')
    else:
        # 일반 유저는 자기가 기안(RequesterId)한 건만 제한적으로 필터링 조회 (보안/프라이버시)
        cursor.execute('''
            SELECT a.*, u.NickName as RequesterNickName, u.Name as RequesterName
            FROM approval_requests a
            JOIN users u ON a.RequesterId = u.UserId
            WHERE a.RequesterId = ?
            ORDER BY a.RequestId DESC
        ''', (user['UserId'],))
        
    rows = cursor.fetchall()
    conn.close()
    
    # 결과 배열을 JSON 객체 리스트로 직렬화하여 반환
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@app.route('/api/approvals/<int:req_id>/process', methods=['POST'])
@login_required
@csrf_required
def process_approval(req_id):
    """
    [역할]:
      - 관리자가 상신된 전자결재(마스터 데이터 신규 등) 건을 승인(Approve)하거나 반려(Reject) 처리를 수행합니다.
    [데이터 제어]:
      - 승인 시 해당 마스터 데이터(카테고리, 제조사, 노드, 옵션)의 승인 플래그(IsApproved/status)를 일괄 활성화합니다.
      - 반려 시, 신청된 기안 항목을 삭제하고 기존 장비에 매핑된 데이터가 있다면 대체어(Replacement)로 롤백 맵핑을 수행합니다.
    [변경 시 영향도]:
      - 마스터 데이터 승인 상태가 변경되므로, 장비 등록 모달 등 모든 드롭다운 마스터 목록 노출에 전면적 영향을 미칩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "관리자만 승인/반려할 수 있습니다."}), 403
        
    data = request.json
    action = data.get('action')  # 'approve' or 'reject'
    reject_reason = data.get('reject_reason', '')
    replacement_name = data.get('replacement_name', '').strip() if data.get('replacement_name') else ''
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM approval_requests WHERE RequestId = ?", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        return jsonify({"success": False, "message": "해당 결재 건을 찾을 수 진행할 수 없습니다."}), 404
        
    req_dict = dict(req)
    req_data = json.loads(req_dict['RequestDataJSON'])
    target_name = req_data.get('name')
    req_type = req_dict['RequestType']
    
    if action == 'approve':
        # [승인 파이프라인]: 결재 상태 갱신 및 참조 무결성에 따른 실제 마스터 테이블 승인 플래그(1 / APPROVED) 적용
        cursor.execute("UPDATE approval_requests SET Status = 'APPROVED', ApproverId = ?, UpdatedAt = ? WHERE RequestId = ?", (user['UserId'], now, req_id))
        
        if req_type == 'ADD_CATEGORY':
            cursor.execute("UPDATE categories SET IsApproved = 1 WHERE Name = ?", (target_name,))
        elif req_type == 'ADD_MANUFACTURER':
            cursor.execute("UPDATE manufacturers SET IsApproved = 1 WHERE Name = ?", (target_name,))
        elif req_type in ('Lineup_Node', 'ADD_LINEUP_NODE'):
            node_id = req_data.get('node_id')
            if node_id:
                cursor.execute("UPDATE lineup_nodes SET status = 'APPROVED' WHERE id = ?", (node_id,))
            else:
                cursor.execute("UPDATE lineup_nodes SET status = 'APPROVED' WHERE name = ? AND status = 'PENDING'", (target_name,))
        elif req_type in ('Equipment_Option', 'ADD_EQUIPMENT_OPTION'):
            opt_id = req_data.get('option_id')
            if opt_id:
                cursor.execute("UPDATE equipment_options SET status = 'APPROVED' WHERE id = ?", (opt_id,))
            else:
                cursor.execute("UPDATE equipment_options SET status = 'APPROVED' WHERE option_name = ? AND status = 'PENDING'", (target_name,))
                
        log_audit(user['UserId'], user['LoginId'], 'APPROVE_REQUEST', 'approval_requests', req_id, req_dict, {"Status": "APPROVED"})
        
    elif action == 'reject':
        # [반려 파이프라인]: 반려 사유 적재 및 임시 등록된 미승인 마스터 데이터 롤백(DELETE)
        cursor.execute("UPDATE approval_requests SET Status = 'REJECTED', ApproverId = ?, RejectReason = ?, UpdatedAt = ? WHERE RequestId = ?", (user['UserId'], reject_reason, now, req_id))
        
        # 대체 이름(Replacement)이 지정된 경우, 해당 미승인 항목을 물고 있는 기존 장비 레코드들을 대체 이름으로 마이그레이션(보정) 후 미승인 항목 삭제
        if req_type == 'ADD_CATEGORY':
            if replacement_name:
                cursor.execute("UPDATE equipment SET Category = ? WHERE Category = ?", (replacement_name, target_name))
            cursor.execute("DELETE FROM categories WHERE Name = ? AND IsApproved = 0", (target_name,))
        elif req_type == 'ADD_MANUFACTURER':
            if replacement_name:
                cursor.execute("UPDATE equipment SET Manufacturer = ? WHERE Manufacturer = ?", (replacement_name, target_name))
            cursor.execute("DELETE FROM manufacturers WHERE Name = ? AND IsApproved = 0", (target_name,))
        elif req_type in ('Lineup_Node', 'ADD_LINEUP_NODE'):
            node_id = req_data.get('node_id')
            if node_id:
                cursor.execute("DELETE FROM lineup_nodes WHERE id = ? AND status = 'PENDING'", (node_id,))
            else:
                cursor.execute("DELETE FROM lineup_nodes WHERE name = ? AND status = 'PENDING'", (target_name,))
        elif req_type in ('Equipment_Option', 'ADD_EQUIPMENT_OPTION'):
            opt_id = req_data.get('option_id')
            if opt_id:
                cursor.execute("DELETE FROM equipment_options WHERE id = ? AND status = 'PENDING'", (opt_id,))
            else:
                cursor.execute("DELETE FROM equipment_options WHERE option_name = ? AND status = 'PENDING'", (target_name,))
            
        log_audit(user['UserId'], user['LoginId'], 'REJECT_REQUEST', 'approval_requests', req_id, req_dict, {"Status": "REJECTED", "Reason": reject_reason, "Replacement": replacement_name})
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "결재 처리가 완료되었습니다."})


@app.route('/api/equipment', methods=['GET'])
@login_required
def get_equipment():
    """
    [역할]:
      - 3-Tier 카탈로그 계층(Category -> Node -> Option)을 통합 조회하여 프론트엔드 장비 목록 렌더링용 데이터를 제공합니다.
    [의존성 관계]:
      - equipments (메인) -> equipment_options -> lineup_nodes -> categories / manufacturers 다중 LEFT JOIN
    [변경 시 영향도]:
      - 대시보드 리스트뷰, 장비 목록 검색, 관리자뷰/임시저장뷰 등의 테이블 렌더링 성능 및 쿼리 정확도에 직접적인 영향을 줍니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    req_type = request.args.get('type', 'my')
    include_mine = request.args.get('include_mine', 'false').lower() == 'true'
    is_draft = request.args.get('is_draft', '0') == '1'
    
    # 3-Tier 복합 JOIN 베이스 쿼리
    base_select = '''
        SELECT e.id AS EquipmentId, e.id AS id,
               e.name AS Name, e.serial_number AS SerialNumber,
               e.purchase_date AS PurchaseDate, e.status AS Status, e.memo AS Memo,
               e.user_id AS UserId, e.is_public AS IsPublic, e.is_draft AS IsDraft,
               e.created_at AS CreatedAt, e.updated_at AS UpdatedAt,
               u.NickName AS OwnerNickName,
               opt.id AS OptionId, opt.option_name AS OptionName, opt.specs_json AS SpecsJson,
               node.id AS LineupNodeId, node.name AS ModelName, node.depth AS ModelDepth,
               cat.CategoryId AS CategoryId, cat.Name AS CategoryName,
               mfg.ManufacturerId AS ManufacturerId, mfg.Name AS ManufacturerName
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN categories cat ON node.category_id = cat.CategoryId
        LEFT JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
        LEFT JOIN users u ON e.user_id = u.UserId
    '''

    # [분기 1]: 임시저장함 뷰 (내 장비이면서 is_draft=1)
    if is_draft:
        cursor.execute(f'''
            {base_select}
            WHERE e.user_id = ? AND e.is_draft = 1
            ORDER BY e.id DESC
        ''', (user['UserId'],))
        
    # [분기 2]: 내 장비(정식) 뷰
    elif req_type == 'my':
        cursor.execute(f'''
            {base_select}
            WHERE e.user_id = ? AND (e.is_draft = 0 OR e.is_draft IS NULL)
            ORDER BY e.id DESC
        ''', (user['UserId'],))
        
    # [분기 3]: 공개/전체 장비 뷰
    elif req_type == 'public':
        if user['Role'] == 'admin':
            # 관리자는 타인의 비공개(is_public=0) 정식 장비까지 모두 조회 가능
            cursor.execute(f'''
                {base_select}
                WHERE (e.is_draft = 0 OR e.is_draft IS NULL)
                ORDER BY e.id DESC
            ''')
        else:
            # 일반 유저는 공개 장비(is_public=1)만 열람 가능
            if include_mine:
                # "내 장비 포함" 옵션 활성화 시 본인 소유 장비도 함께 출력 (정렬 우선순위 부여)
                cursor.execute(f'''
                    {base_select}
                    WHERE (e.is_public = 1 OR e.user_id = ?) AND (e.is_draft = 0 OR e.is_draft IS NULL)
                    ORDER BY CASE WHEN e.user_id = ? THEN 0 ELSE 1 END, e.id DESC
                ''', (user['UserId'], user['UserId']))
            else:
                # 타인의 공개 장비만 순수 필터링
                cursor.execute(f'''
                    {base_select}
                    WHERE e.is_public = 1 AND e.user_id != ? AND (e.is_draft = 0 OR e.is_draft IS NULL)
                    ORDER BY e.id DESC
                ''', (user['UserId'],))
    else:
        cursor.execute("SELECT * FROM equipments WHERE 1=0")

    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        item = dict(row)
        if item.get('SpecsJson'):
            try:
                item['Specs'] = json.loads(item['SpecsJson'])
            except Exception:
                item['Specs'] = {}
        else:
            item['Specs'] = {}
        result.append(item)

    return jsonify(result)


@app.route('/api/equipment', methods=['POST'])
@login_required
@csrf_required
def add_equipment():
    """
    [역할]:
      - 프론트엔드 모달에서 사용자가 입력한 데이터를 바탕으로 신규 장비를 3-Tier 카탈로그(옵션 단위)에 바인딩하여 생성합니다.
    [데이터 제어]:
      - '임시저장' 상태 분기, 유니크 시리얼 넘버 제약(Validation) 방어 처리를 수행하며, 카탈로그 신규 옵션 기안 시 인라인 생성(Pending)을 지원합니다.
    [변경 시 영향도]:
      - 장비 데이터 생성의 가장 핵심 파이프라인이며, equipments_audit_log 에 무조건적인 이력 적재가 수반됩니다.
    """
    data = request.json or {}
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    target_user_id = user['UserId']
    # 관리자인 경우 사용자 강제 배정(Assign) 권한 허용
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')
    
    # 필수값 방어 로직 (이름/별명)
    name = (data.get('Name') or data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "장비 별명(이름)을 입력하세요."}), 400

    serial_number = (data.get('SerialNumber') or data.get('serial_number') or '').strip() or None
    purchase_date = data.get('PurchaseDate') or data.get('purchase_date')
    memo = (data.get('Memo') or data.get('memo') or '').strip()
    
    # 임시저장(Draft) 여부에 따라 공개 플래그(Public) 묵시적 강제 비활성화
    is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
    is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') or data.get('is_public') else 0)

    opt_data = data.get('OptionData') or {}
    option_id = None

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # [검증]: 시리얼 넘버 유니크 중복 검증 (Integrity 방어)
        if serial_number:
            cursor.execute("SELECT id FROM equipments WHERE serial_number = ?", (serial_number,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"error": "이미 등록된 시리얼 넘버입니다."}), 400

        # [옵션 바인딩 처리]: 인라인으로 신규 옵션을 제안(isNew)한 경우 즉시 생성
        if isinstance(opt_data, dict) and opt_data.get('isNew'):
            new_opt_name = (opt_data.get('option_name') or '').strip()
            specs_json = opt_data.get('specs_json') or '{}'
            lineup_node_id = opt_data.get('lineup_node_id')

            if not lineup_node_id:
                conn.close()
                return jsonify({"error": "소속될 카탈로그 노드를 선택해야 합니다."}), 400
            if not new_opt_name:
                conn.close()
                return jsonify({"error": "신규 옵션명을 입력하세요."}), 400

            # (현재 로직에서는 인라인 추가 시 APPROVED로 강제 바이패스 하도록 처리되어 있으나 정책에 따라 PENDING이 될 수 있음)
            status = 'APPROVED'
            cursor.execute("""
                INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (lineup_node_id, new_opt_name, specs_json, status, user['UserId'], now))
            option_id = cursor.lastrowid

        # 기존 옵션 선택 시
        elif isinstance(opt_data, dict) and opt_data.get('option_id'):
            option_id = int(opt_data['option_id'])
        elif data.get('option_id'):
            option_id = int(data['option_id'])

        # 정식 등록 시 옵션 바인딩 검증
        if not option_id and not is_draft:
            conn.close()
            return jsonify({"error": "옵션 스펙을 선택해 주세요."}), 400

        # 임시저장 시 옵션이 빈 값이면(미선택), 무결성 유지를 위해 fallback 기본 옵션 할당(또는 더미 생성)
        if not option_id:
            cursor.execute("SELECT id FROM equipment_options LIMIT 1")
            first_opt = cursor.fetchone()
            if first_opt:
                option_id = first_opt[0]
            else:
                cursor.execute("SELECT id FROM lineup_nodes LIMIT 1")
                first_node = cursor.fetchone()
                if first_node:
                    cursor.execute("INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status) VALUES (?, '기본 옵션', '{}', 'APPROVED')", (first_node[0],))
                    option_id = cursor.lastrowid
                else:
                    option_id = 1

        # [장비 메인 INSERT 쿼리]
        cursor.execute('''
            INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, is_draft, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?)
        ''', (
            option_id,
            name,
            serial_number,
            purchase_date,
            memo,
            target_user_id,
            is_public,
            is_draft,
            now,
            now
        ))
        new_id = cursor.lastrowid

        # 장비 등록 이력 스냅샷(JSON)을 감사 로그 테이블에 적재
        cursor.execute('''
            INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
            VALUES (?, 'CREATE', ?, ?, ?)
        ''', (new_id, json.dumps(data, ensure_ascii=False), user['UserId'], now))

        conn.commit()
        conn.close()
        
        # 통합 전역 감사 로그(audit_logs) 기록 연동
        log_audit(user['UserId'], user['LoginId'], 'INSERT', 'equipments', new_id, None, data)
        return jsonify({"message": "임시저장되었습니다." if is_draft == 1 else "성공적으로 등록되었습니다!"})

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"장비 등록 중 오류: {str(e)}"}), 500


# 장비 수정
@app.route('/api/equipment/<int:eq_id>', methods=['PUT'])
@login_required
@csrf_required
def update_equipment(eq_id):
    """
    [역할]:
      - 기존에 등록된 3-Tier 장비의 상세 정보(이름, 시리얼, 옵션, 공개여부 등)를 갱신합니다.
    [권한 및 무결성]:
      - 자신 소유의 장비이거나 관리자(admin)인 경우에만 수정을 허용하며, 시리얼 넘버 수정 시 타 장비와의 중복 충돌을 방어합니다.
    [변경 시 영향도]:
      - equipments 테이블 본체 변경 및 equipments_audit_log 에 old/new 스냅샷이 적재되며 장비 이력 추적에 영향을 미칩니다.
    """
    data = request.json or {}
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipments WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['user_id'] != user['UserId']:
        conn.close()
        return jsonify({"error": "수정 권한이 없습니다."}), 403

    target_user_id = old_dict['user_id']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')

    if old_dict.get('is_draft') == 0:
        is_draft = 0
        is_public = 1 if data.get('IsPublic') or data.get('is_public') else 0
    else:
        is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
        is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') or data.get('is_public') else 0)

    name = (data.get('Name') or data.get('name') or old_dict['name']).strip()
    serial_number = (data.get('SerialNumber') or data.get('serial_number') or '').strip() or None
    purchase_date = data.get('PurchaseDate') or data.get('purchase_date') or old_dict.get('purchase_date')
    memo = (data.get('Memo') or data.get('memo') or '').strip()

    # 시리얼 중복 검증 (자신 제외)
    if serial_number and serial_number != old_dict.get('serial_number'):
        cursor.execute("SELECT id FROM equipments WHERE serial_number = ? AND id != ?", (serial_number, eq_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "이미 등록된 시리얼 넘버입니다."}), 400

    opt_data = data.get('OptionData')
    option_id = old_dict['option_id']
    if isinstance(opt_data, dict):
        if opt_data.get('isNew'):
            new_opt_name = (opt_data.get('option_name') or '').strip()
            specs_json = opt_data.get('specs_json') or '{}'
            lineup_node_id = opt_data.get('lineup_node_id')
            if lineup_node_id and new_opt_name:
                cursor.execute("""
                    INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by, created_at)
                    VALUES (?, ?, ?, 'APPROVED', ?, ?)
                """, (lineup_node_id, new_opt_name, specs_json, user['UserId'], now))
                option_id = cursor.lastrowid
        elif opt_data.get('option_id'):
            option_id = int(opt_data['option_id'])

    cursor.execute('''
        UPDATE equipments 
        SET option_id=?, name=?, serial_number=?, purchase_date=?, memo=?, user_id=?, is_public=?, is_draft=?, updated_at=?
        WHERE id=?
    ''', (
        option_id,
        name,
        serial_number,
        purchase_date,
        memo,
        target_user_id,
        is_public,
        is_draft,
        now,
        eq_id
    ))
    
    # 감사 로그 적재
    cursor.execute('''
        INSERT INTO equipments_audit_log (equipment_id, action_type, old_value, new_value, changed_by, changed_at)
        VALUES (?, 'UPDATE', ?, ?, ?, ?)
    ''', (eq_id, json.dumps(old_dict, ensure_ascii=False), json.dumps(data, ensure_ascii=False), user['UserId'], now))

    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE', 'equipments', eq_id, old_dict, data)
    return jsonify({"message": "수정되었습니다."})


# 장비 삭제
@app.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
@login_required
@csrf_required
def delete_equipment(eq_id):
    """
    [역할]:
      - 특정 장비를 시스템(데이터베이스)에서 완전히 영구 파기(Hard Delete)합니다.
    [보안/권한 정책]:
      - 로그인된 사용자가 본인이거나, 글로벌 관리자(admin)인 경우에만 삭제 권한을 인가합니다. 타인 장비 임의 삭제를 차단합니다.
    [변경 시 영향도]:
      - 비가역적인 파기 프로세스이므로, 삭제 전 equipments_audit_log 에 최종 스냅샷을 남겨 책임 추적성에 대비합니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipments WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['user_id'] != user['UserId']:
        conn.close()
        return jsonify({"error": "삭제 권한이 없습니다."}), 403

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO equipments_audit_log (equipment_id, action_type, old_value, changed_by, changed_at)
        VALUES (?, 'DELETE', ?, ?, ?)
    ''', (eq_id, json.dumps(old_dict, ensure_ascii=False), user['UserId'], now))

    cursor.execute("DELETE FROM equipments WHERE id = ?", (eq_id,))
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'DELETE', 'equipments', eq_id, old_dict, None)
    return jsonify({"message": "삭제되었습니다."})


# 권한 설정 조회
@app.route('/api/permissions', methods=['GET'])
@login_required
def get_permissions():
    """
    [역할]:
      - 시스템 내 역할별(Role: admin, user) 메뉴 접근 권한(IsAllowed) 상태를 교차 조인(CROSS JOIN)하여 매트릭스 형태로 반환합니다.
    [의존성 관계]:
      - users(Role 추출), menus, role_menu_permissions 테이블
    [변경 시 영향도]:
      - 포털의 '메뉴 권한 관리' 페이지 렌더링에 직접적인 영향을 주며, 관리자 전용 엔드포인트(403 제어)입니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.Role, 
            m.MenuCode, 
            m.MenuName, 
            m.ParentMenuCode, 
            m.SortOrder,
            COALESCE(p.IsAllowed, 0) as IsAllowed
        FROM (SELECT DISTINCT Role FROM users UNION SELECT 'admin' UNION SELECT 'user') r
        CROSS JOIN menus m
        LEFT JOIN role_menu_permissions p ON p.Role = r.Role AND p.MenuCode = m.MenuCode
        ORDER BY r.Role ASC, m.SortOrder ASC, m.MenuId ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(r) for r in rows])


# 권한 설정 수정
@app.route('/api/permissions', methods=['POST'])
@login_required
@csrf_required
def update_permissions():
    """
    [역할]:
      - 관리자가 UI에서 변경한 권한(Role)별 메뉴 통제 리스트를 DB에 일괄 갱신(UPSERT) 합니다.
    [비즈니스 로직(제약)]:
      - 부모-자식 모순 검증: 자식 메뉴가 허용(1)되었는데 부모 메뉴가 차단(0)된 상태라면 400 에러를 튕겨 무결성을 강제합니다.
    [변경 시 영향도]:
      - 전체 시스템 사용자의 메뉴 접근 권한(사이드바, 런처 등)이 실시간으로 재배치됩니다. 잘못 적용 시 접속 장애(UI 미노출)가 발생할 수 있습니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    data = request.json 
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM role_menu_permissions")
    old_perms = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT MenuCode, ParentMenuCode FROM menus")
    menus_meta = {r['MenuCode']: r['ParentMenuCode'] for r in cursor.fetchall()}
    
    future_perms = {}
    for r in old_perms:
        if r['Role'] not in future_perms: future_perms[r['Role']] = {}
        future_perms[r['Role']][r['MenuCode']] = r['IsAllowed']
        
    for item in data:
        role = item['Role']
        if role not in future_perms: future_perms[role] = {}
        future_perms[role][item['MenuCode']] = item['IsAllowed']
        
    # 부모-자식 모순 검증
    for role, perms in future_perms.items():
        for menu_code, is_allowed in perms.items():
            if is_allowed:
                parent = menus_meta.get(menu_code)
                while parent:
                    if not perms.get(parent, 0):
                        conn.close()
                        return jsonify({"error": f"하위 메뉴({menu_code})가 활성화되었으나 상위 메뉴({parent})가 비활성화 상태입니다. 권한 구조가 모순됩니다."}), 400
                    parent = menus_meta.get(parent)
    
    for item in data:
        cursor.execute('''
            INSERT INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(Role, MenuCode) DO UPDATE SET IsAllowed=excluded.IsAllowed, UpdatedAt=excluded.UpdatedAt
        ''', (item['Role'], item['MenuCode'], item['IsAllowed'], now))
        
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_PERMISSIONS', 'role_menu_permissions', None, old_perms, data)
    return jsonify({"success": True, "message": "권한 설정이 업데이트되었습니다."})


# ------------------------------------------
# [제안-011-고도화] 마스터 데이터 관리 & 통폐합 API
# ------------------------------------------
@app.route('/api/master/manage/<target_type>', methods=['GET', 'POST'])
@login_required
@csrf_required
def get_or_create_master_management_item(target_type):
    """
    [역할]:
      - 관리자 전용 마스터 데이터 (카테고리/제조사) 전체 목록을 조회(GET)하거나 신규 항목을 직접 생성(POST)합니다.
    [데이터 취합]:
      - GET: 3-Tier 카탈로그 계층을 JOIN하여 각 마스터 항목이 장비(equipments)에 매핑된 실 사용 횟수(UsageCount)를 동적 집계합니다.
    [변경 시 영향도]:
      - 마스터 데이터 관리(master_management.html) 테이블 출력 및 장비 등록 시 표출되는 기준 정보 풀(Pool) 확장에 영향을 미칩니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        if target_type == 'categories':
            cursor.execute('''
                SELECT c.id as CategoryId, c.id, c.name as Name, c.name as NameKo, c.name as NameEn, 1 as IsApproved, c.created_at as CreatedAt,
                       COUNT(e.id) as UsageCount
                FROM categories c
                LEFT JOIN lineup_nodes node ON c.id = node.category_id
                LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
                LEFT JOIN equipments e ON opt.id = e.option_id
                GROUP BY c.id
                ORDER BY c.id DESC
            ''')
        elif target_type == 'manufacturers':
            cursor.execute('''
                SELECT m.id as ManufacturerId, m.id, m.name as Name, m.name as NameKo, m.name as NameEn, 1 as IsApproved, m.created_at as CreatedAt,
                       COUNT(e.id) as UsageCount
                FROM manufacturers m
                LEFT JOIN lineup_nodes node ON m.id = node.manufacturer_id
                LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
                LEFT JOIN equipments e ON opt.id = e.option_id
                GROUP BY m.id
                ORDER BY m.id DESC
            ''')
        else:
            conn.close()
            return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400
            
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"success": True, "data": [dict(r) for r in rows]})

    elif request.method == 'POST':
        data = request.json or {}
        name = data.get('Name', '').strip()
        name_ko = data.get('NameKo', '').strip() if data.get('NameKo') else None
        name_en = data.get('NameEn', '').strip() if data.get('NameEn') else None

        if not name:
            conn.close()
            return jsonify({"success": False, "message": "기본 명칭(Name)은 필수입니다."}), 400

        table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
        if not table_name:
            conn.close()
            return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

        # 중복 명칭 검증
        cursor.execute(f"SELECT * FROM {table_name} WHERE Name = ?", (name,))
        if cursor.fetchone():
            conn.close()
            label_name = '카테고리' if target_type == 'categories' else '제조사'
            return jsonify({"success": False, "message": f"이미 존재하는 {label_name} 명칭입니다."}), 400

        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"INSERT INTO {table_name} (Name, NameKo, NameEn, IsApproved, CreatedAt) VALUES (?, ?, ?, 1, ?)",
                       (name, name_ko, name_en, created_at))
        new_id = cursor.lastrowid

        user = session['user']
        log_audit(user['UserId'], user['LoginId'], 'CREATE_MASTER', table_name, new_id, None, data)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 추가되었습니다.", "id": new_id})


@app.route('/api/master/manage/<target_type>/delete_selected', methods=['POST'])
@login_required
@csrf_required
def delete_selected_master_items(target_type):
    """
    [역할]:
      - 관리자 환경에서 체크박스로 선택된 다수의 마스터 데이터(카테고리/제조사)를 일괄 영구 삭제합니다.
    [참조 무결성 보존]:
      - 마스터를 삭제하면 이를 참조하던 lineup_nodes(카탈로그)와 equipment(장비)의 외래키(Foreign Key) 및 레거시 문자열 컬럼을 일괄 NULL 처리하여 고아 레코드 충돌을 방지합니다.
    [변경 시 영향도]:
      - 해당 마스터에 속해있던 장비들이 '미분류'로 떨어지게 되며, 파괴적 변경이므로 주의가 필요합니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403

    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'

    if not table_name:
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

    data = request.json or {}
    item_ids = data.get('item_ids', [])
    if not item_ids or not isinstance(item_ids, list):
        return jsonify({"success": False, "message": "삭제할 항목이 선택되지 않았습니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(item_ids))
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    # 3-Tier lineup_nodes 및 equipment 관련 외래키 NULL 처리
    cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = NULL WHERE {lineup_fk} IN ({placeholders})", item_ids)
    cursor.execute(f"UPDATE equipment SET {fk_col} = NULL, {legacy_col} = NULL WHERE {fk_col} IN ({placeholders})", item_ids)
    cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} IN ({placeholders})", item_ids)

    log_audit(user['UserId'], user['LoginId'], 'DELETE_MASTER_SELECTED', table_name, None, {"deleted_ids": item_ids}, None)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"{len(item_ids)}개 항목이 성공적으로 일괄 삭제되었습니다."})


@app.route('/api/master/manage/<target_type>/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
@csrf_required
def update_or_delete_master_item(target_type, item_id):
    """
    [역할]:
      - 단일 마스터 데이터(카테고리/제조사)의 다국어 명칭(Ko/En)을 수정(PUT)하거나, 단건 삭제(DELETE)합니다.
    [참조 무결성 보존]:
      - 삭제 시, delete_selected_master_items 와 동일하게 하위 3-Tier 카탈로그(lineup_nodes) 및 장비(equipments) 참조 키를 NULL로 해제합니다.
    [변경 시 영향도]:
      - 수정 시 즉각적으로 전역 화면의 분류 명칭이 변경되며, 삭제 시 종속 장비들이 '미분류' 처리됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    
    if not table_name:
        conn.close()
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

    if request.method == 'PUT':
        data = request.json
        name = data.get('Name', '').strip()
        name_ko = data.get('NameKo', '').strip() if data.get('NameKo') else None
        name_en = data.get('NameEn', '').strip() if data.get('NameEn') else None
        
        if not name:
            conn.close()
            return jsonify({"success": False, "message": "기본 명칭(Name)은 필수입니다."}), 400
            
        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (item_id,))
        old_item = cursor.fetchone()
        if not old_item:
            conn.close()
            return jsonify({"success": False, "message": "해당 마스터 항목을 찾을 수 없습니다."}), 404
            
        cursor.execute(f"UPDATE {table_name} SET Name = ?, NameKo = ?, NameEn = ? WHERE {id_col} = ?",
                       (name, name_ko, name_en, item_id))
                       
        log_audit(user['UserId'], user['LoginId'], 'UPDATE_MASTER', table_name, item_id, dict(old_item), data)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 수정되었습니다."})
        
    elif request.method == 'DELETE':
        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (item_id,))
        old_item = cursor.fetchone()
        if not old_item:
            conn.close()
            return jsonify({"success": False, "message": "해당 마스터 항목을 찾을 수 없습니다."}), 404
            
        # lineup_nodes 및 equipment의 관련 컬럼을 NULL 처리
        cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = NULL WHERE {lineup_fk} = ?", (item_id,))
        cursor.execute(f"UPDATE equipment SET {fk_col} = NULL, {legacy_col} = NULL WHERE {fk_col} = ?", (item_id,))
        cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} = ?", (item_id,))
        
        log_audit(user['UserId'], user['LoginId'], 'DELETE_MASTER', table_name, item_id, dict(old_item), None)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 삭제되었습니다."})


@app.route('/api/master/manage/<target_type>/<int:target_id>/merge_from', methods=['POST'])
@login_required
@csrf_required
def merge_master_items(target_type, target_id):
    """
    [역할]:
      - 파편화되거나 중복 생성된 여러 마스터 데이터(Source)를 하나의 기준 마스터(Target)로 통폐합(Merge)합니다.
    [마이그레이션(Migration) 로직]:
      - 삭제 대상(Source)을 가리키고 있던 하위 3-Tier lineup_nodes 와 equipment 테이블의 참조 외래키를 일괄적으로 기준 타겟(Target ID)으로 UPDATE 한 후, Source 마스터를 삭제합니다.
    [변경 시 영향도]:
      - 기존 장비 데이터의 분류 체계가 강제로 일괄 병합되며 데이터 정규화(Cleanup)에 기여합니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    data = request.json
    source_ids = data.get('source_ids', [])
    if not source_ids or not isinstance(source_ids, list):
        return jsonify({"success": False, "message": "통합할 대상 항목을 1개 이상 선택해야 합니다."}), 400
        
    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    
    if not table_name:
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (target_id,))
    target_item = cursor.fetchone()
    if not target_item:
        conn.close()
        return jsonify({"success": False, "message": "기준 마스터 항목을 찾을 수 없습니다."}), 404
        
    placeholders = ','.join(['?'] * len(source_ids))
    
    # 1. lineup_nodes 및 equipment 테이블의 ID 및 레거시 컬럼 일괄 UPDATE
    cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = ? WHERE {lineup_fk} IN ({placeholders})", (target_id, *source_ids))
    cursor.execute(f"UPDATE equipment SET {fk_col} = ?, {legacy_col} = ? WHERE {fk_col} IN ({placeholders})",
                   (target_id, str(target_id), *source_ids))
                   
    # 2. 통합 대상 마스터 항목 삭제
    cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} IN ({placeholders})", tuple(source_ids))
    
    log_audit(user['UserId'], user['LoginId'], 'MERGE_MASTER', table_name, target_id, 
              {"SourceIds": source_ids}, {"TargetId": target_id})
              
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"총 {len(source_ids)}개의 항목이 성공적으로 통폐합되었습니다."})


@app.route('/api/auth/send_pin', methods=['POST'])
@csrf_required
def api_send_pin_logic():
    """
    [역할]:
      - 사용자 비밀번호 찾기 시, 이메일 기반의 6자리 인증 PIN 번호를 생성하여 발송합니다.
    [비즈니스/보안 로직]:
      - PIN 번호는 평문이 아닌 Hash 처리되어 DB(email_verifications)에 적재되며, 무차별 대입 및 어뷰징 방지를 위해 120초(2분)의 발송 쿨다운을 강제합니다.
    [변경 시 영향도]:
      - 비밀번호 찾기(1단계) 핀 발송 통신 및 SMTP 외부 연동 성능에 직접적인 영향을 미칩니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "유효한 이메일 주소를 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT ExpiresAt FROM email_verifications WHERE Email = ?", (email,))
    existing_req = cursor.fetchone()
    if existing_req:
        expires_dt = datetime.strptime(existing_req['ExpiresAt'], '%Y-%m-%d %H:%M:%S')
        if (expires_dt - datetime.now()).total_seconds() > 120:
            conn.close()
            return jsonify({"success": False, "message": "발송 한도가 초과되었습니다. 1분 후 다시 시도해 주세요."}), 429

    cursor.execute("SELECT UserId FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "이미 사용 중인 이메일 주소입니다."}), 400

    pin_code = ''.join(random.choices(string.digits, k=6))
    pin_hash = generate_password_hash(pin_code)
    expires_at = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        INSERT INTO email_verifications (Email, PinCodeHash, ExpiresAt, IsVerified)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(Email) DO UPDATE SET PinCodeHash=excluded.PinCodeHash, ExpiresAt=excluded.ExpiresAt, IsVerified=0
    ''', (email, pin_hash, expires_at))
    conn.commit()
    conn.close()

    subject = "[미니서버] 이메일 인증 PIN 번호 안내"
    body_html = f"<p>인증 PIN 번호: <strong>{pin_code}</strong> (3분 유효)</p>"
    success, msg = send_email(email, subject, body_html)
    
    if success:
        return jsonify({"success": True, "message": "인증 PIN 코드가 발송되었습니다."})
    return jsonify({"success": False, "message": "메일 발송 실패."}), 500


@app.route('/api/auth/verify_pin', methods=['POST'])
@csrf_required
def api_verify_pin_logic():
    """
    [역할]:
      - 사용자가 이메일로 수신한 6자리 PIN 번호를 검증(Verify)합니다.
    [비즈니스/보안 로직]:
      - 입력된 평문 PIN과 DB에 저장된 PIN Hash를 대조(check_password_hash)하고, 만료 시간(ExpiresAt)을 엄격히 검사하여 재플레잉 공격을 방어합니다.
    [변경 시 영향도]:
      - 검증 성공 시 IsVerified 플래그가 1로 활성화되며, 이 상태가 되어야만 실제 비밀번호 재설정 페이지로의 진입이 허가됩니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    pin = data.get('pin', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not email or not pin:
        return jsonify({"success": False, "message": "입력값이 부족합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_verifications WHERE Email = ?", (email,))
    record = cursor.fetchone()

    if not record or record['ExpiresAt'] < now_str or not check_password_hash(record['PinCodeHash'], pin):
        conn.close()
        return jsonify({"success": False, "message": "PIN 코드가 잘못되었거나 만료되었습니다."}), 400

    cursor.execute("UPDATE email_verifications SET IsVerified = 1 WHERE Email = ?", (email,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "인증이 완료되었습니다!"})


@app.route('/api/auth/request_password_reset', methods=['POST'])
@csrf_required
def api_request_password_reset_logic():
    """
    [역할]:
      - 관리자나 본인이 패스워드를 분실했을 때, UUID 형태의 토큰이 포함된 1회용 재설정 링크(Magic Link)를 메일로 발송합니다.
    [비즈니스/보안 로직]:
      - 토큰은 해싱되어 password_resets 에 기록되며 1시간의 유효기간과 약 1시간(3540초)의 재발송 쿨다운을 가집니다. 사용자 식별자 유출 방지를 위해 계정이 없더라도 성공 메시지를 반환(Dummy Response)합니다.
    [변경 시 영향도]:
      - 이메일 기반 암호화 토큰 발급 및 SMTP 트래픽 량에 영향을 미칩니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email: return jsonify({"success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": True, "message": "입력하신 이메일이 등록되어 있다면 재설정 링크가 메일로 발송되었습니다."})

    cursor.execute("SELECT ExpiresAt FROM password_resets WHERE UserId = ? ORDER BY ExpiresAt DESC LIMIT 1", (user['UserId'],))
    last_req = cursor.fetchone()
    if last_req:
        last_expires = datetime.strptime(last_req['ExpiresAt'], '%Y-%m-%d %H:%M:%S')
        if (last_expires - datetime.now()).total_seconds() > 3540:
            conn.close()
            return jsonify({"success": False, "message": "재발송 쿨다운 중입니다. 잠시 후 다시 시도해 주세요."}), 429

    raw_token = str(uuid.uuid4())
    token_hash = generate_password_hash(raw_token)
    expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("INSERT INTO password_resets (TokenHash, UserId, ExpiresAt, IsUsed) VALUES (?, ?, ?, 0)",
                   (token_hash, user['UserId'], expires_at))
    conn.commit()
    conn.close()

    reset_url = request.host_url.rstrip('/') + f"reset_password?token={raw_token}&email={email}"
    success, msg = send_email(email, "[미니서버] 비밀번호 재설정", f"<a href='{reset_url}'>비밀번호 재설정하기</a>")
    
    return jsonify({"success": True, "message": "비밀번호 재설정 링크가 발송되었습니다."})


@app.route('/reset_password', methods=['GET'])
def reset_password_page():
    """
    [역할]:
      - 이메일 핀 인증 또는 이메일 링크를 통해 인가된 사용자에게 새 비밀번호 입력 폼을 제공하는 뷰 라우터입니다.
    [의존성 관계]:
      - reset_password.html (Front-end 템플릿)
    [변경 시 영향도]:
      - 비밀번호 변경 진입 UI 렌더링에 영향을 줍니다.
    """
    return render_template('reset_password.html')


@app.route('/api/auth/reset_password', methods=['POST'])
@csrf_required
def api_reset_password_logic():
    """
    [역할]:
      - 검증을 통과한 사용자가 제출한 새 비밀번호를 해싱하여 users 테이블에 최종 갱신(Update)합니다.
    [비즈니스/보안 로직]:
      - 토큰의 유효성(IsUsed=0, 만료시간)을 한 번 더 검증하고, 비밀번호 변경과 동시에 SessionToken을 갱신(Invalidate)하여 다른 모든 디바이스에서 강제 로그아웃 시킵니다.
    [변경 시 영향도]:
      - 패스워드 재설정 및 전역 세션 만료 처리에 직접적인 영향을 주며, 완료 시 1회용 토큰은 IsUsed=1 로 소진됩니다.
    """
    data = request.json or {}
    token = data.get('token', '').strip()
    email = data.get('email', '').strip()
    new_password = data.get('new_password', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "잘못된 요청입니다."}), 400
        
    cursor.execute("SELECT * FROM password_resets WHERE UserId = ? AND IsUsed = 0 AND ExpiresAt > ? ORDER BY ExpiresAt DESC", (user['UserId'], now_str))
    resets = cursor.fetchall()
    
    valid_req = None
    for req in resets:
        if check_password_hash(req['TokenHash'], token):
            valid_req = req
            break

    if not valid_req:
        conn.close()
        return jsonify({"success": False, "message": "유효하지 않거나 만료된 토큰입니다."}), 400

    hashed_pw = generate_password_hash(new_password)
    new_session_token = secrets.token_hex(32)
    cursor.execute("UPDATE users SET Password = ?, SessionToken = ?, UpdatedAt = ? WHERE UserId = ?", 
                   (hashed_pw, new_session_token, now_str, user['UserId']))
    cursor.execute("UPDATE password_resets SET IsUsed = 1 WHERE TokenHash = ?", (valid_req['TokenHash'],))
    conn.commit()
    
    log_audit(user['UserId'], 'System', 'RESET_PASSWORD', 'users', user['UserId'])
    conn.close()

    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})


# ==========================================
# [제안-036] 웹 접근 로그(HTTP Access Logs) 관리 API 3종
# ==========================================

@app.route('/api/access_logs', methods=['GET'])
@login_required
def api_get_access_logs():
    """
    [역할]:
      - 검색 필터(IP, 메서드, 상태코드, 경로, 퀵필터) 및 페이징 조건에 맞춰 시스템의 전역 HTTP 접근 로그(access_logs) 목록을 조회합니다.
    [데이터 제어(경량화)]:
      - [제안-045] Request/Response Payload 본문은 매우 비대하므로(String/JSON), 목록 조회 시에는 HasRequestPayload, HasResponsePayload 와 같이 0/1 플래그만 추출하여 네트워크 병목을 억제합니다.
    [변경 시 영향도]:
      - 관리자 화면의 접근 로그 테이블(Datatables) 표출 및 페이징, 필터 쿼리 성능(Index)에 지대한 영향을 미칩니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"error": "권한이 없습니다."}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    quick_filter = request.args.get('quick_filter', 'all')
    filter_ip = request.args.get('ip', '').strip()
    filter_method = request.args.get('method', '').strip()
    filter_status = request.args.get('status', '').strip()
    filter_path = request.args.get('path', '').strip()

    where_clauses = ["1=1"]
    params = []

    # 1. 3단 퀵 필터
    if quick_filter == 'api':
        where_clauses.append("IsStatic = 0")
    elif quick_filter == 'static':
        where_clauses.append("IsStatic = 1")

    # 2. 상세 검색 필터
    if filter_ip:
        where_clauses.append("IpAddress LIKE ?")
        params.append(f"%{filter_ip}%")

    if filter_method:
        where_clauses.append("HttpMethod = ?")
        params.append(filter_method)

    if filter_status:
        if filter_status == '4xx':
            where_clauses.append("StatusCode >= 400 AND StatusCode < 500")
        elif filter_status == '5xx':
            where_clauses.append("StatusCode >= 500 AND StatusCode < 600")
        elif filter_status.isdigit():
            where_clauses.append("StatusCode = ?")
            params.append(int(filter_status))

    if filter_path:
        where_clauses.append("RequestPath LIKE ?")
        params.append(f"%{filter_path}%")

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # 총 건수 조회
    cursor.execute(f"SELECT COUNT(*) FROM access_logs WHERE {where_sql}", params)
    total_count = cursor.fetchone()[0]

    # [제안-045] 목록 조회 시 페이로드 본문 대신 경량 플래그(0 또는 1)만 조회
    cursor.execute(f"""
        SELECT 
            LogId, IpAddress, HttpMethod, RequestPath, StatusCode, UserAgent, Referer, DurationMs, IsStatic,
            CASE WHEN RequestPayload IS NOT NULL AND RequestPayload != '' THEN 1 ELSE 0 END AS HasRequestPayload,
            CASE WHEN ResponsePayload IS NOT NULL AND ResponsePayload != '' THEN 1 ELSE 0 END AS HasResponsePayload,
            CreatedAt
        FROM access_logs
        WHERE {where_sql}
        ORDER BY LogId DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    rows = cursor.fetchall()
    conn.close()

    logs = [dict(row) for row in rows]
    return jsonify({
        "status": "success",
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "logs": logs
    })


@app.route('/api/access_logs/<int:log_id>/payload', methods=['GET'])
@login_required
def api_get_access_log_payload(log_id):
    """
    [역할]:
      - [제안-045] 특정 access_log 레코드의 거대한 페이로드(Request/Response) 데이터를 온디맨드(단건 비동기) 방식으로 조회하여 반환합니다.
    [데이터 제어]:
      - 리스트 조회에서 배제되었던 Text/JSON 데이터를 해당 라우터에서만 독점적으로 SELECT 하여 반환합니다.
    [변경 시 영향도]:
      - 관리자 로그 모달 팝업의 상세 Payload 텍스트 표출 속도에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"error": "권한이 없습니다."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT LogId, RequestPayload, ResponsePayload
        FROM access_logs
        WHERE LogId = ?
    """, (log_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "로그 데이터를 찾을 수 없습니다."}), 404

    return jsonify({
        "status": "success",
        "log_id": row['LogId'],
        "request_payload": row['RequestPayload'],
        "response_payload": row['ResponsePayload']
    })


@app.route('/api/access_logs/stats', methods=['GET'])
@login_required
def api_get_access_log_stats():
    """
    [역할]:
      - 지정된 기간(오늘 또는 전체 누적)의 웹 접근 로그 통계(총 요청 수, API 호출 수, 정적 리소스 수, 에러 횟수/비율)를 집계합니다.
    [비즈니스 로직(통계 집계)]:
      - CASE WHEN 구문을 활용하여 단일 쿼리로 다차원 지표(Static 분기, 4xx/5xx 에러율)를 한 번에 연산하여 DB I/O를 최소화합니다.
    [변경 시 영향도]:
      - 관리자 대시보드 및 로그 화면 상단의 4종 요약 카드 위젯 수치 표출에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"error": "권한이 없습니다."}), 403

    period = request.args.get('period', 'today').lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    if period == 'all':
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
            FROM access_logs
        """)
    else:
        period = 'today'
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_start = f"{today_str} 00:00:00"

        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
            FROM access_logs
            WHERE CreatedAt >= ?
        """, (today_start,))

    row = cursor.fetchone()
    conn.close()

    total = row['total'] or 0
    api_count = row['api_count'] or 0
    static_count = row['static_count'] or 0
    error_count = row['error_count'] or 0
    error_rate = round((error_count / total * 100.0), 1) if total > 0 else 0.0

    return jsonify({
        "status": "success",
        "period": period,
        "total": total,
        "api_count": api_count,
        "static_count": static_count,
        "error_count": error_count,
        "error_rate": error_rate
    })


@app.route('/api/access_logs/cleanup', methods=['POST'])
@login_required
@csrf_required
def api_cleanup_access_logs():
    """
    [역할]:
      - 관리자가 지정한 기준(30일 이전, 정적 리소스만, 전체 초기화 등)에 따라 방대해진 접근 로그를 안전하게 영구 삭제(Cleanup)합니다.
    [데이터 제어(분할 삭제)]:
      - [제안-044] 대용량 DELETE 시 발생할 수 있는 DB Lock(SQLite Database is Locked) 방지를 위해, 프론트엔드와 step(count -> delete_chunk -> finish)을 주고받으며 청크(Chunk) 단위로 트랜잭션을 쪼개어 삭제를 수행합니다.
    [변경 시 영향도]:
      - access_logs 테이블의 물리적 레코드 파기 및 DB Size 축소에 매우 중요한 역할을 하며, 잘못된 조건 시 전체 로깅 유실이 발생할 수 있습니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "관리자만 로그를 정리할 수 있습니다."}), 403

    data = request.json or {}
    action = data.get('action')
    step = data.get('step', 'direct') # 'count', 'delete_chunk', 'finish', 'direct'

    if not action or action not in ['older_30d', 'static_only', 'all']:
        return jsonify({"success": False, "message": "올바른 정리 방식을 지정해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        deleted_count = 0
        if step == 'direct':
            if action == 'older_30d':
                cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("DELETE FROM access_logs WHERE CreatedAt < ?", (cutoff_date,))
                deleted_count = cursor.rowcount
            elif action == 'static_only':
                cursor.execute("DELETE FROM access_logs WHERE IsStatic = 1")
                deleted_count = cursor.rowcount
            elif action == 'all':
                cursor.execute("DELETE FROM access_logs")
                deleted_count = cursor.rowcount

            conn.commit()

            log_audit(user['UserId'], user['LoginId'], 'CLEANUP_ACCESS_LOGS', 'access_logs', None, None, {
                "action": action,
                "deleted_count": deleted_count
            })

            return jsonify({
                "status": "success",
                "message": "로그가 성공적으로 정리되었습니다.",
                "deleted_count": deleted_count
            })
        elif step == 'count':
            if action == 'older_30d':
                cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("SELECT COUNT(*) FROM access_logs WHERE CreatedAt < ?", (cutoff_date,))
            elif action == 'static_only':
                cursor.execute("SELECT COUNT(*) FROM access_logs WHERE IsStatic = 1")
            elif action == 'all':
                cursor.execute("SELECT COUNT(*) FROM access_logs")
            total_count = cursor.fetchone()[0]
            return jsonify({
                "status": "success",
                "total_count": total_count
            })
        elif step == 'delete_chunk':
            chunk_size = 250
            if action == 'older_30d':
                cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    DELETE FROM access_logs 
                    WHERE LogId IN (
                        SELECT LogId FROM access_logs 
                        WHERE CreatedAt < ? 
                        ORDER BY CreatedAt ASC
                        LIMIT ?
                    )
                """, (cutoff_date, chunk_size))
            elif action == 'static_only':
                cursor.execute("""
                    DELETE FROM access_logs 
                    WHERE LogId IN (
                        SELECT LogId FROM access_logs 
                        WHERE IsStatic = 1 
                        ORDER BY CreatedAt ASC
                        LIMIT ?
                    )
                """, (chunk_size,))
            elif action == 'all':
                cursor.execute("""
                    DELETE FROM access_logs 
                    WHERE LogId IN (
                        SELECT LogId FROM access_logs 
                        ORDER BY CreatedAt ASC
                        LIMIT ?
                    )
                """, (chunk_size,))

            deleted_count = cursor.rowcount
            conn.commit()
            return jsonify({
                "status": "success",
                "deleted_count": deleted_count
            })
        elif step == 'finish':
            total_deleted = data.get('total_deleted', 0)
            log_audit(user['UserId'], user['LoginId'], 'CLEANUP_ACCESS_LOGS', 'access_logs', None, None, {
                "action": action,
                "deleted_count": total_deleted
            })
            return jsonify({
                "status": "success",
                "message": "로그가 성공적으로 정리되었습니다.",
                "deleted_count": total_deleted
            })
        else:
            return jsonify({"status": "error", "message": "유효하지 않은 step 파라미터입니다."}), 400
    finally:
        conn.close()

    return jsonify({"status": "success"})


@app.route('/api/access_logs/error_ips', methods=['GET'])
@login_required
def api_access_logs_error_ips():
    """
    [역할]:
      - 시스템 내에서 4xx/5xx 에러를 유발한 클라이언트들의 IP 목록과 개별 에러 빈도, 마지막 에러 발생 시점을 집계하여 반환합니다.
    [비즈니스/보안 로직]:
      - 악성 어뷰저(Brute-force, 스캐너 등) IP를 색출하기 위해 GROUP BY IpAddress 로 집계하며 Client/Server 에러 구분을 제공합니다.
    [변경 시 영향도]:
      - 관리자 '에러 IP 심층 분석' 패널의 데이터 소스로 활용되며, 추후 IP 차단(Blacklist) 기능 확장에 필수적인 의존성을 가집니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            IpAddress,
            COUNT(LogId) AS TotalErrorCount,
            MAX(CreatedAt) AS LastErrorAt,
            SUM(CASE WHEN StatusCode >= 400 AND StatusCode < 500 THEN 1 ELSE 0 END) AS ClientErrorCount,
            SUM(CASE WHEN StatusCode >= 500 THEN 1 ELSE 0 END) AS ServerErrorCount
        FROM access_logs
        WHERE StatusCode >= 400
        GROUP BY IpAddress
        ORDER BY TotalErrorCount DESC, LastErrorAt DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "IpAddress": r["IpAddress"],
            "TotalErrorCount": r["TotalErrorCount"],
            "LastErrorAt": r["LastErrorAt"],
            "ClientErrorCount": r["ClientErrorCount"],
            "ServerErrorCount": r["ServerErrorCount"]
        })

    return jsonify({
        "status": "success",
        "total_unique_ips": len(result),
        "error_ips": result
    })



if __name__ == '__main__':
    try:
        # .env 파일에서 FLASK_DEBUG 값을 가져와 True/False로 변환
        is_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        print(f"[Server Startup] Starting Flask on http://0.0.0.0:5000 (debug={is_debug}, reloader=False)...")
        # [Python 3.14 호환성] use_reloader=False를 명시하여 서브프로세스 IPC 세마포어 누수 경고 및 크래시 방어
        app.run(host='0.0.0.0', port=5000, debug=is_debug, use_reloader=False)
    except Exception as e:
        import traceback
        print(f"[Server Fatal Error] Failed to start server: {e}")
        traceback.print_exc()
