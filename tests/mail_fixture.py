"""In-process assistant blueprint and real worker on synthetic SQLite. No server listens."""
from contextlib import ExitStack, contextmanager
from datetime import timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask
import requests

MODEL = 'qwen3.8-flash-next-iq3_xxs'
# Exercise the migrated provider revision and intercept transport before any model socket opens.
ORIGIN = 'http://192.168.0.14:8080'
TOKEN = 'synthetic-mail-worker-token-for-fixture-only'


class Response:
    """The wire reply is supplied by the caller; a stop reason never implies [DONE]."""
    def __init__(self, reply):
        if reply.get('transport_error') in ('timeout', 'connection'):
            error = requests.Timeout if reply['transport_error'] == 'timeout' else requests.ConnectionError
            raise error('recorded transport failure')
        self.status_code = reply.get('status', 200)
        self.headers = {'Content-Type': reply.get('content_type', 'text/event-stream')}
        self.lines = reply['lines']

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise requests.HTTPError('recorded HTTP error')

    def iter_lines(self, **_):
        yield from self.lines


class Fixture:
    def __init__(self, assistant, root, search_available, stack):
        from utils.ai_assistant import worker, web_search
        self.root = root
        db_file = root / 'fixture.sqlite'

        def connect():
            db = sqlite3.connect(db_file)
            db.row_factory = sqlite3.Row
            return db

        db = connect()
        try:
            db.executescript("""
                CREATE TABLE menus(MenuCode PRIMARY KEY, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt);
                CREATE TABLE users(UserId INTEGER PRIMARY KEY, LoginId, Role, SessionToken, IsDeleted, IsDeactivated, CreatedAt);
                CREATE TABLE role_menu_permissions(Role, MenuCode, IsAllowed, UpdatedAt, PRIMARY KEY(Role, MenuCode));
                INSERT INTO users VALUES(1,'admin','admin','fixture-1','N','N','2000-01-01'),
                                        (2,'user','user','fixture-2','N','N','2000-01-02');
                INSERT INTO role_menu_permissions VALUES ('user','my_equipment',1,0),('user','public_equipment',1,0),('user','my_approvals',1,0);
            """)
        finally:
            db.close()
        self.app = Flask('mail_fixture', root_path=str(root), static_folder=None)
        self.app.config.update(TESTING=True, SECRET_KEY='isolated-mail-fixture-signing-key-only',
                               USER_AI_ENABLED=True, USER_AI_WRITE_TOOLS=True, USER_AI_WORKER_TOKEN=TOKEN,
                               USER_AI_PUBLIC_ORIGIN='http://localhost', USER_AI_DATABASE=str(root / 'chat.sqlite'),
                               USER_AI_STRATA_URL=ORIGIN, USER_AI_ALLOWED_ENDPOINTS=[ORIGIN],
                               USER_AI_STRATA_KEY='', USER_AI_MODEL=MODEL, USER_AI_MODEL_DISCOVERY=False,
                               USER_AI_DATABASE_EPOCH='mail-fixture-1', USER_AI_AUDIT_ROOT=str(root / 'audit'))
        assistant.install_assistant(self.app, {'get_db_connection': connect, 'login_required': lambda f: f,
                                             'get_maintenance_state': lambda: {'state': 'NORMAL'}})
        ext = self.app.extensions['equipment_assistant']
        self.store, self.domain, self.registry = ext['store'], ext['domain'], ext['registry']
        # Exercise the actual planner and tool schema in the current path. Only the
        # inert negative search decision can run. Never invent search results.
        stack.enter_context(patch.object(web_search.SearchService, 'available', property(lambda _: search_available)))
        original_dispatch = self.domain.read_or_prepare
        self.blocked_tools = []

        def dispatch(name, args, *pos, **kwargs):
            if name == 'plan_web_search' and args.get('needed') is False:
                return original_dispatch(name, args, *pos, **kwargs)
            self.blocked_tools.append(name)
            if name in ('plan_web_search', 'web_search'):
                raise web_search.WebSearchError('WEB_SEARCH_UNAVAILABLE')
            raise RuntimeError('equipment tools are disabled in the replay fixture')

        def block_draft(*_):
            self.blocked_tools.append('save_draft')
            raise RuntimeError('draft writes are disabled in the replay fixture')

        stack.enter_context(patch.object(self.domain, 'read_or_prepare', side_effect=dispatch))
        stack.enter_context(patch.object(self.store, 'save_draft', side_effect=block_draft))
        try:
            ZoneInfo('Asia/Seoul')
        except ZoneInfoNotFoundError:
            stack.enter_context(patch.object(assistant, 'ZoneInfo', return_value=timezone(timedelta(hours=9))))
        with patch.dict(os.environ, {'USER_AI_ALLOWED_ENDPOINTS': '["' + ORIGIN + '"]', 'USER_AI_DISPATCHERS': '1'}):
            self.worker = worker.Worker('http://localhost', TOKEN, ORIGIN, '', MODEL)
        self.worker.post = self.internal
        self.client = self.app.test_client()
        self.login(2)
        self.finish_reports = []

    def login(self, uid):
        with self.client.session_transaction() as session:
            session.clear()
            session['user'] = {'UserId': uid}
            session['session_token'] = f'fixture-{uid}'
            session['csrf_token'] = 'fixture'

    def post(self, path, data):
        return self.client.post(path, json=data, headers={'Origin': 'http://localhost', 'X-CSRFToken': 'fixture'})

    def submit(self, content, cid=None, level='medium', key=None, **extra):
        path = '/api/ai/conversations/' + (f'{cid}/turns' if cid else 'first-turn')
        return self.post(path, {'content': content, 'level': level, 'reasoning_version': 2,
                                'client_key': key or uuid.uuid4().hex, **extra})

    def internal(self, path, data):
        response = self.app.test_client(use_cookies=False).post(path, json=data, headers={'Authorization': 'Bearer ' + TOKEN})
        value = response.get_json()
        if response.status_code != 200 or value.get('success') is not True:
            raise RuntimeError(f'fixture worker HTTP {response.status_code}: {value.get("message")}')
        if path.endswith('/finish'):
            self.finish_reports.append((data, value))
        return value

    def claim(self):
        from utils.ai_assistant.providers import PROTOCOL
        return self.internal('/internal/ai/claim', {'worker': 'fixture', 'protocol': PROTOCOL})['job']

    def drive(self, job, respond, *, expected_origin=None):
        from utils.ai_assistant import worker

        def exchange(policy, base, path, key, payload, timeout):
            if (base, path, key) != (expected_origin or ORIGIN, '/chat/completions', ''):
                raise AssertionError('unexpected fixture destination')
            return Response(respond(payload))

        with patch.object(worker, 'model_request', side_effect=exchange):
            self.worker.run_job(job)


@contextmanager
def fixture(assistant, search_available=True):
    with ExitStack() as stack:
        root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='equipment-mail-fixture-')))
        yield Fixture(assistant, root, search_available, stack)
