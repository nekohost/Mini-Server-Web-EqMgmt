"""Admin-only Strata pages and short authorization checks; never proxy an AI stream.

[MINI-COMMENT: STRATA.INTEGRATION]
[EN rev.1]
[Role] Adds a disabled-by-default admin console and checks each Nginx request.
[Dependencies] Existing session validation, menu DB, CSRF session, requests and Nginx.
[Impact] No model runs here; upstream credentials stay in the private Nginx include.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime
from urllib.parse import urlsplit

import requests
from flask import Blueprint, abort, jsonify, render_template, request, session

MENU_CODE = 'strata'
PROXY_PREFIX = '/strata/'
MAX_HEALTH_BYTES = 65536
READ_PATHS = frozenset({
    '/strata/health', '/strata/metrics', '/strata/status', '/strata/mcp',
    '/strata/config', '/strata/settings', '/strata/v1/models', '/strata/models',
    '/strata/api/requests', '/strata/v1/telemetry',
})
WRITE_PATHS = frozenset({
    '/strata/v1/chat/completions', '/strata/v1/images/generations',
    '/strata/config', '/strata/settings',
})
FONT_PATH = re.compile(r'/strata/fonts/[A-Za-z0-9_.-]+\.woff2\Z')
IMAGE_PATH = re.compile(r'/strata/v1/images/files/[a-fA-F0-9]{32}(?:\.png)?\Z')


def visible_portal_menus(rows, role, config):
    """[역할] 비활성 기능과 비관리자의 Strata 메뉴를 숨깁니다.
    [의존성 관계] 기존 포털 목록과 STRATA_ENABLED; [변경 시 영향도] 다른 메뉴는 보존합니다.
    """
    return [dict(row) for row in rows if row['MenuCode'] != MENU_CODE or
            (config.get('STRATA_ENABLED') is True and role == 'admin')]


def request_allowed(method, original_uri):
    """[MINI-COMMENT: STRATA.PROXY.PATHS]
    [EN rev.1]
    [Role] Allows only the console's canonical upstream paths and methods.
    [Dependencies] Nginx's original URI and method, not a client-selected upstream.
    [Impact] Rejects traversal, encoded paths, model load/unload and unknown APIs.
    """
    if not isinstance(original_uri, str) or not original_uri.startswith(PROXY_PREFIX):
        return False
    path = original_uri.partition('?')[0]
    if any(ord(char) < 32 or ord(char) == 127 for char in original_uri):
        return False
    if '%' in path or '\\' in path or '//' in path or '..' in path.split('/'):
        return False
    if method == 'GET':
        return path in READ_PATHS or bool(FONT_PATH.fullmatch(path) or IMAGE_PATH.fullmatch(path))
    return method == 'POST' and path in WRITE_PATHS


def canonical_origin(value):
    """[역할] 인증된 공개 origin만 정규화합니다.
    [의존성 관계] urlsplit; [변경 시 영향도] 사용자 정보·경로가 섞인 Origin은 거부합니다.
    """
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.path or parsed.query or parsed.fragment:
            return None
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        return parsed.scheme.lower(), parsed.hostname.lower(), port
    except (ValueError, TypeError):
        return None


def register_menu(get_connection):
    """[MINI-COMMENT: STRATA.MENU.REGISTER]
    [EN rev.1]
    [Role] Registers a new admin menu idempotently without rewriting existing rows.
    [Dependencies] Existing menus and role_menu_permissions tables.
    [Impact] Adds metadata only; equipment tables and existing grants are preserved.
    """
    connection = get_connection()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        existing = connection.execute('SELECT Url FROM menus WHERE MenuCode=?', (MENU_CODE,)).fetchone()
        if existing and existing['Url'] != '/ai':
            raise ValueError('Strata menu code is already in use; no existing menu was overwritten')
        connection.execute('''INSERT OR IGNORE INTO menus
            (MenuCode,MenuName,Url,Description,ParentMenuCode,SortOrder,CreatedAt,UpdatedAt)
            VALUES (?,?,?,?,NULL,?,?,?)''',
            (MENU_CODE, 'Strata AI', '/ai', '관리자용 AI 채팅과 Strata 상태 확인', 50, now, now))
        connection.execute('''INSERT OR IGNORE INTO role_menu_permissions
            (Role,MenuCode,IsAllowed,UpdatedAt) VALUES ('admin',?,1,?)''', (MENU_CODE, now))
        connection.execute('''INSERT OR IGNORE INTO role_menu_permissions
            (Role,MenuCode,IsAllowed,UpdatedAt) VALUES ('user',?,0,?)''', (MENU_CODE, now))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def upstream_health(url):
    """[역할] 고정된 서버의 작은 health 응답만 읽고 모델 생성은 요청하지 않습니다.
    [의존성 관계] requests, 관리자가 설정한 URL; [변경 시 영향도] 대용량·리다이렉트·느린 응답을 제한합니다.
    """
    target = urlsplit(url)
    if target.scheme not in ('http', 'https') or not target.hostname or target.username or target.password:
        raise ValueError('invalid upstream')
    if target.path not in ('', '/') or target.query or target.fragment:
        raise ValueError('upstream must be a configured origin')
    deadline = time.monotonic() + 3.0
    with requests.Session() as client:
        client.trust_env = False
        with client.get(url.rstrip('/') + '/health', timeout=(1.0, 2.0),
                        allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError('upstream unavailable')
            body = bytearray()
            for chunk in response.iter_content(chunk_size=4096):
                body.extend(chunk)
                if len(body) > MAX_HEALTH_BYTES or time.monotonic() > deadline:
                    raise ValueError('health response limit')
    data = json.loads(body)
    if not isinstance(data, dict) or data.get('service') != 'strata' or data.get('status') != 'ok':
        raise ValueError('invalid Strata health')
    if data.get('api_key') is not True:
        return {'connected': False, 'state': 'configuration',
                'message': 'Strata의 API 키 인증을 확인해 주세요.'}
    return {'connected': True, 'state': 'ready' if data.get('loaded') else 'idle',
            'message': 'Strata에 연결되었습니다.' if data.get('loaded') else 'Strata 연결됨 · 모델 대기 중'}


def install_strata(app, get_connection, login_required, check_permission):
    """[MINI-COMMENT: STRATA.ROUTES.INSTALL]
    [EN rev.1]
    [Role] Registers admin views, bounded health and a no-secret Nginx auth endpoint.
    [Dependencies] Existing login_required verifies the current DB session on every request.
    [Impact] The disabled flag denies proxy access and hides the menu after rollback.
    """
    app.config.setdefault('STRATA_ENABLED', os.getenv('STRATA_ENABLED', '').lower() in ('1', 'true', 'yes', 'on'))
    app.config.setdefault('STRATA_PUBLIC_ORIGIN', os.getenv('STRATA_PUBLIC_ORIGIN', 'https://nekohost.org'))
    app.config.setdefault('STRATA_UPSTREAM_URL', os.getenv('STRATA_UPSTREAM_URL', 'http://192.168.0.14:8080'))
    blueprint = Blueprint('strata_admin', __name__)

    def admin_allowed():
        """[역할] 활성 기능과 현재 관리자만 허용합니다. [의존성 관계] 기존 로그인 검사 후 세션·메뉴 권한.
        [변경 시 영향도] 일반 역할의 잘못된 메뉴 grant도 API 접근으로 이어지지 않습니다.
        """
        return (app.config.get('STRATA_ENABLED') is True and
                session.get('user', {}).get('Role') == 'admin' and check_permission(MENU_CODE))

    @blueprint.after_request
    def private_response(response):
        """[역할] 로그인 문서·진단을 캐시하지 않고 동일 origin 삽입만 허용합니다.
        [의존성 관계] 이 blueprint 응답; [변경 시 영향도] 다른 장비관리 페이지 헤더는 변경하지 않습니다.
        """
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'; base-uri 'self'; object-src 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @blueprint.get('/ai')
    @login_required
    def page():
        """[역할] 관리자의 Strata 메뉴 프레임입니다. [의존성 관계] 공통 화면·활성 로그인.
        [변경 시 영향도] 직접적인 내부 IP나 API 키를 HTML에 넣지 않습니다.
        """
        if not admin_allowed():
            abort(403 if app.config.get('STRATA_ENABLED') is True else 404)
        return render_template('strata.html', user=session['user'])

    @blueprint.get('/ai/console')
    @login_required
    def console():
        """[MINI-COMMENT: STRATA.CONSOLE.CONTEXT]
        [EN rev.1]
        [Role] Renders pinned UI with CSRF and a session-scoped storage namespace.
        [Dependencies] Current user/session token and application signing key.
        [Impact] No upstream key or raw login token is exposed to the browser.
        """
        if not admin_allowed():
            abort(403 if app.config.get('STRATA_ENABLED') is True else 404)
        if not session.get('csrf_token'):
            session['csrf_token'] = secrets.token_hex(16)
        signing_key = app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key
        identity = f"strata-storage-v1:{session['user']['UserId']}:{session.get('session_token', '')}".encode()
        namespace = hmac.new(signing_key, identity, hashlib.sha256).hexdigest()[:32]
        return render_template('strata_console.html', strata_csrf=session['csrf_token'],
                               strata_namespace=namespace)

    @blueprint.get('/api/strata/status')
    @login_required
    def status():
        """[역할] 관리자에게 비밀 없는 연결 상태를 반환합니다. [의존성 관계] 고정 upstream health.
        [변경 시 영향도] 실패한 AI 연결이 다른 메뉴의 영구 의존성이 되지 않습니다.
        """
        if not admin_allowed():
            return jsonify(message='관리자용 Strata 기능에 접근할 수 없습니다.'), 403
        try:
            result = upstream_health(app.config['STRATA_UPSTREAM_URL'])
            return jsonify(result), 200 if result['connected'] else 503
        except (requests.RequestException, ValueError, TypeError):
            return jsonify(connected=False, state='unavailable', message='Strata에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'), 503

    @blueprint.get('/api/strata/access')
    @login_required
    def proxy_access():
        """[MINI-COMMENT: STRATA.PROXY.AUTHORIZE]
        [EN rev.1]
        [Role] Allows a protected Nginx subrequest only for an admin and allowed path/method.
        [Dependencies] Original request headers, configured origin and the session CSRF token.
        [Impact] Returns 204/401/403 only; never emits an upstream API key.
        """
        if not admin_allowed():
            return '', 403
        method = request.headers.get('X-Strata-Original-Method', '')
        uri = request.headers.get('X-Strata-Original-URI', '')
        if not request_allowed(method, uri):
            return '', 403
        if method == 'POST':
            expected_origin = canonical_origin(app.config.get('STRATA_PUBLIC_ORIGIN'))
            received_origin = canonical_origin(request.headers.get('X-Strata-Original-Origin', ''))
            given_token = request.headers.get('X-CSRFToken', '')
            expected_token = session.get('csrf_token', '')
            if (not expected_origin or received_origin != expected_origin or
                    not given_token or len(given_token) > 256 or
                    not isinstance(expected_token, str) or not expected_token or
                    not hmac.compare_digest(given_token.encode('utf-8'), expected_token.encode('utf-8'))):
                return '', 403
        return '', 204

    app.register_blueprint(blueprint)
    if app.config['STRATA_ENABLED'] is True:
        register_menu(get_connection)
