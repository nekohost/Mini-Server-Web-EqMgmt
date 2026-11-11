"""Exercise the real login page against a private Linux fixture using the project's ChromeDriver."""
from contextlib import closing, contextmanager
import json
import logging
import tempfile
import threading
import time
from unittest.mock import patch

from itsdangerous.timed import TimestampSigner
from werkzeug.serving import make_server
from werkzeug.wrappers import Response

from capture_ai_conversation_entry import Browser
from test_roadmap_batch import RoadmapBatchTests


class LoginTraffic:
    """Observe method, representation and status only. Faults are confined to this test process."""
    def __init__(self, app):
        self.app = app
        self.events = []
        self.age_next_form = True
        self.fail_next_prepare = False

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'] != '/login':
            return self.app(environ, start_response)
        method = environ['REQUEST_METHOD']
        wants_json = environ.get('HTTP_ACCEPT') == 'application/json'
        kind = 'prepare' if wants_json and method == 'GET' else method

        def record(status, headers, exc_info=None):
            self.events.append((kind, int(status.split()[0])))
            return start_response(status, headers, exc_info)

        if self.age_next_form and kind == 'GET':
            self.age_next_form = False
            with patch.object(TimestampSigner, 'get_timestamp', return_value=int(time.time()) - 8546):
                return self.app(environ, record)
        if self.fail_next_prepare and kind == 'prepare':
            self.fail_next_prepare = False
            return Response(status=503)(environ, record)
        return self.app(environ, record)


@contextmanager
def fixture():
    """Run the candidate on an ephemeral loopback port with synthetic accounts and SQLite."""
    RoadmapBatchTests.setUpClass()
    try:
        case = RoadmapBatchTests()
        case.setUp()
        traffic = LoginTraffic(case.module.app)
        with make_server('127.0.0.1', 0, traffic) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield case, traffic, 'http://127.0.0.1:' + str(server.server_port)
            finally:
                server.shutdown()
                thread.join()
    finally:
        RoadmapBatchTests.tearDownClass()


def fill(browser, account, password):
    """Set only the temporary fixture's visible inputs."""
    browser.call('POST', browser.sid + '/execute/sync', {
        'script': "document.getElementById('LoginId').value=arguments[0]; document.getElementById('Password').value=arguments[1];",
        'args': [account, password],
    })


def run(width, height):
    """Use independent browser actions and server events to check each POST count."""
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with fixture() as (case, traffic, site), tempfile.TemporaryDirectory() as profile:
        browser = Browser(profile, width, height)
        try:
            def open_form():
                browser.call('POST', browser.sid + '/url', {'url': site + '/login'})
                browser.until("document.getElementById('loginForm')")

            def expect_events(start, expected):
                actual = traffic.events[start:]
                assert actual == expected, (expected, actual)

            def session_marker(user_id):
                with closing(case.connection()) as conn:
                    return conn.execute('SELECT SessionToken FROM users WHERE UserId=?', (user_id,)).fetchone()[0]

            open_form()
            fill(browser, 'fixture-20002', 'GoodPass1!')
            start = len(traffic.events)
            browser.js("const f=document.getElementById('loginForm'); f.querySelector('[type=submit]').click(); f.requestSubmit(); f.requestSubmit();")
            browser.until("location.pathname === '/portal'")
            expect_events(start, [('prepare', 200), ('POST', 200)])

            browser.call('DELETE', browser.sid + '/cookie')
            open_form()
            first = browser.call('GET', browser.sid + '/window')
            fill(browser, 'fixture-20003', 'incorrect-fixture')
            start = len(traffic.events)
            field = browser.call('POST', browser.sid + '/element', {'using': 'css selector', 'value': '#Password'})
            field_id = field['element-6066-11e4-a52e-4f735466cecf']
            browser.call('POST', browser.sid + '/element/' + field_id + '/value', {'text': '\ue007', 'value': ['\ue007']})
            browser.until("!document.getElementById('errorMessage').classList.contains('hidden')")
            expect_events(start, [('prepare', 200), ('POST', 400)])
            assert browser.js("return document.getElementById('Password').value==='incorrect-fixture' && document.getElementById('LoginId').value==='fixture-20003'")

            traffic.fail_next_prepare = True
            start = len(traffic.events)
            browser.js("document.getElementById('loginForm').requestSubmit()")
            browser.until("document.getElementById('errorMessage').textContent.includes('불러오지 못했습니다')")
            expect_events(start, [('prepare', 503)])
            assert browser.js("return !document.querySelector('#loginForm [type=submit]').disabled && document.getElementById('Password').value==='incorrect-fixture'")

            other = browser.call('POST', browser.sid + '/window/new', {'type': 'tab'})['handle']
            browser.call('POST', browser.sid + '/window', {'handle': other})
            open_form()
            fill(browser, 'fixture-20002', 'GoodPass1!')
            # Simulate a connection that loses the acknowledgement after the server commits the login.
            browser.js("""
                const nativeFetch=window.fetch.bind(window);
                window.fetch=async (url, options) => {
                    const response=await nativeFetch(url, options);
                    if (options?.method==='POST') { window.fetch=nativeFetch; throw new TypeError('fixture'); }
                    return response;
                };
            """)
            start = len(traffic.events)
            browser.js("document.getElementById('loginForm').requestSubmit()")
            browser.until("document.getElementById('errorMessage').textContent.includes('응답을 확인하지 못했습니다')")
            expect_events(start, [('prepare', 200), ('POST', 200)])
            active = session_marker(20002)
            untouched = session_marker(20003)
            start = len(traffic.events)
            browser.js("document.getElementById('loginForm').requestSubmit()")
            browser.until("location.pathname === '/portal'")
            expect_events(start, [('prepare', 302)])

            browser.call('POST', browser.sid + '/window', {'handle': first})
            fill(browser, 'fixture-20003', 'GoodPass1!')
            start = len(traffic.events)
            browser.js("document.getElementById('loginForm').requestSubmit()")
            browser.until("location.pathname === '/portal'")
            expect_events(start, [('prepare', 302)])
            assert session_marker(20002) == active and session_marker(20003) == untouched
            return {'viewport': [width, height], 'expired_seconds': 8546, 'expired_and_duplicate_submit': 1,
                    'invalid_password_preserved': True, 'failed_prepare_posts': 0,
                    'lost_ack_retry_posts': 0, 'other_tab_posts': 0, 'account_sessions_preserved': True}
        finally:
            browser.close()


if __name__ == '__main__':
    print(json.dumps([run(390, 844), run(1440, 900)], sort_keys=True))
