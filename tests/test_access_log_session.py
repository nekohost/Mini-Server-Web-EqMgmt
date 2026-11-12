"""Exercise signed Flask cookies in request contexts without starting the application."""
import ast
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import wraps
from http.cookies import SimpleCookie
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask, jsonify, redirect, request, session, url_for
from itsdangerous.timed import TimestampSigner

from utils import http_audit_queue
from utils.ai_assistant import PassiveSessionInterface
from utils.http_security import referrer_path


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
LIFETIME = timedelta(minutes=30)
LOG_POLL = {'X-Access-Log-Poll': '1'}
AI_POLL = {'X-Assistant-Poll': '1'}


def register_fixture_routes(app, directory):
    # Keep the production route decorators, SQL and cookie lifecycle without running app.py's startup.
    source = Path(__file__).resolve().parents[1] / 'app.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    names = {'login_required', 'csrf_required', 'api_get_access_logs', 'api_get_access_log_stats',
             'extend_session', 'logout', 'check_session'}
    routes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    log_table = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                     and isinstance(n.value, str) and n.value.lstrip().startswith('CREATE TABLE IF NOT EXISTS access_logs ('))

    def connect():
        db = sqlite3.connect(Path(directory) / 'fixture.sqlite')
        db.row_factory = sqlite3.Row
        return db

    with closing(connect()) as db, db:
        db.execute(log_table)
        db.execute('CREATE TABLE users(UserId, SessionToken, Role, IsDeleted, IsDeactivated, DeactivatedAt)')
        db.execute("INSERT INTO users VALUES(1, 'fixture-session', 'admin', 'N', 'N', NULL)")
    app.add_url_rule('/login', endpoint='login_page')
    scope = dict(app=app, wraps=wraps, session=session, request=request, jsonify=jsonify,
                 redirect=redirect, url_for=url_for, get_db_connection=connect, datetime=datetime,
                 get_maintenance_state=lambda: {'state': 'NORMAL'}, log_audit=Mock(),
                 check_menu_permission=lambda menu: menu == 'access_logs',
                 http_audit_queue=http_audit_queue, referrer_path=referrer_path)
    exec(compile(ast.Module(body=routes, type_ignores=[]), str(source), 'exec'), scope)


class AccessLogSessionCookies(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, static_folder=None)
        self.app.secret_key = 'access-log-session-fixture'
        self.app.permanent_session_lifetime = LIFETIME
        self.app.session_interface = PassiveSessionInterface()
        self.cookie_value = ''
        with self.request_at(0, '/login', 'POST'):
            session.permanent = True
            session['user'] = {'UserId': 1, 'LoginId': 'fixture', 'Role': 'admin'}
            session['session_token'] = 'fixture-session'
            session['csrf_token'] = 'fixture-csrf'
            self.assertEqual(parsedate_to_datetime(self.save_cookie()['expires']), START + LIFETIME)

    @contextmanager
    def request_at(self, seconds, path, method='GET', headers=None):
        now = START + timedelta(seconds=seconds)
        headers = dict(headers or {})
        if self.cookie_value:
            headers['Cookie'] = 'session=' + self.cookie_value
        with patch.object(TimestampSigner, 'get_timestamp', return_value=int(now.timestamp())), \
                patch('flask.sessions.datetime') as clock:
            clock.now.return_value = now
            with self.app.test_request_context(path, method=method, headers=headers):
                yield

    def save_cookie(self):
        response = self.app.response_class()
        self.app.session_interface.save_session(self.app, session, response)
        header = response.headers.get('Set-Cookie')
        if header is None:
            return None
        cookie = SimpleCookie(header)['session']
        self.cookie_value = cookie.value
        return cookie

    def test_polling_never_moves_the_original_expiration(self):
        for seconds in (5, 1500, 1799):
            for path, headers in (
                ('/api/access_logs?page=2', LOG_POLL),
                ('/api/access_logs/stats?period=all', LOG_POLL),
                ('/api/check_session', {}),
                ('/api/check_session', AI_POLL),
                ('/api/ai/status', AI_POLL),
                ('/api/ai/conversations', {}),
            ):
                with self.subTest(seconds=seconds, path=path), self.request_at(seconds, path, headers=headers):
                    self.assertIn('user', session)
                    self.assertIsNone(self.save_cookie())
        # Present even the saved cookie after its signed lifetime has elapsed.
        with self.request_at(1801, '/api/access_logs', headers=LOG_POLL):
            self.assertNotIn('user', session)
            self.assertIsNone(self.save_cookie())

    def test_marker_requires_the_exact_log_read_and_value(self):
        for method, path, headers in (
            ('GET', '/api/access_logs', AI_POLL),
            ('GET', '/api/access_logs/stats', {'X-Access-Log-Poll': '0'}),
            ('GET', '/api/access_logs/error_ips', LOG_POLL),
            ('GET', '/api/access_logs/123/payload', LOG_POLL),
            ('GET', '/api/me?next=/api/access_logs', LOG_POLL),
            ('HEAD', '/api/access_logs', LOG_POLL),
            ('POST', '/api/access_logs/stats', LOG_POLL),
            ('POST', '/api/access_logs/cleanup', LOG_POLL),
            ('POST', '/api/ai/conversations', AI_POLL),
        ):
            with self.subTest(method=method, path=path), self.request_at(60, path, method, headers):
                self.assertIsNotNone(self.save_cookie())

    def test_real_log_routes_extension_and_logout(self):
        with tempfile.TemporaryDirectory() as directory:
            register_fixture_routes(self.app, directory)

            def response():
                return self.app.make_response(self.app.view_functions[request.endpoint]())

            for path in ('/api/access_logs?page=2', '/api/access_logs/stats?period=today'):
                with self.subTest(path=path), self.request_at(1500, path, headers=LOG_POLL):
                    self.assertEqual(response().get_json()['status'], 'success')
                    self.assertIsNone(self.save_cookie())
            for minutes, path in ((25, '/api/access_logs?ip=192.0.2.18'), (50, '/api/access_logs?page=3'),
                                  (75, '/api/access_logs/stats?period=all')):
                with self.subTest(path=path), self.request_at(minutes * 60, path):
                    self.assertEqual(response().get_json()['status'], 'success')
                    expiry = parsedate_to_datetime(self.save_cookie()['expires'])
                    self.assertEqual(expiry, START + timedelta(minutes=minutes) + LIFETIME)
            csrf = {'X-CSRFToken': 'fixture-csrf'}
            with self.request_at(6000, '/api/extend_session', 'POST', csrf):
                self.assertTrue(response().get_json()['success'])
                self.assertTrue(session.modified)
                self.assertEqual(parsedate_to_datetime(self.save_cookie()['expires']), START + timedelta(minutes=130))
            previous_cookie = self.cookie_value
            with self.request_at(6305, '/api/check_session'):
                self.assertTrue(response().get_json()['valid'])
                self.assertIsNone(self.save_cookie())
            with self.request_at(6310, '/logout', 'POST', csrf):
                self.assertEqual(response().location, '/login')
                self.assertEqual(self.save_cookie()['max-age'], '0')
            with self.request_at(6315, '/api/check_session'):
                expired = response()
                self.assertEqual((expired.status_code, expired.get_json()['reason']), (401, 'session_expired'))
                self.assertIsNone(self.save_cookie())
            self.cookie_value = previous_cookie
            with self.request_at(6320, '/api/check_session'):
                revoked = response()
                self.assertEqual((revoked.status_code, revoked.get_json()['reason']), (401, 'concurrent_login'))
                self.assertIsNone(self.save_cookie())

    def test_passive_read_still_saves_session_changes_and_invalidation(self):
        with self.request_at(60, '/api/access_logs', headers=LOG_POLL):
            session['user'] = dict(session['user'], Role='user')
            self.assertIsNotNone(self.save_cookie())
        with self.request_at(65, '/api/access_logs', headers=LOG_POLL):
            self.assertEqual(session['user']['Role'], 'user')
            session.clear()
            self.assertEqual(self.save_cookie()['max-age'], '0')
            self.assertEqual(self.cookie_value, '')


if __name__ == '__main__':
    unittest.main()
