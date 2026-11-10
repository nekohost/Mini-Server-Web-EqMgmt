"""[MINI-COMMENT: ASSISTANT.POLISH.STATUS.TESTS]
[EN rev.1]
[Role] Exercises authenticated queue evidence, outage aging and incremental worker delivery.
[Dependencies] Source-derived temporary Linux fixtures and a loopback-only SSE server.
[Impact] Never imports app.py, reads production DBs or sends requests to a real provider.
"""
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests
from assistant_fixture_tests import AssistantTests, ProtocolTests
from utils.ai_assistant.worker import sse


@unittest.skipUnless(os.name == 'posix', 'Linux synthetic fixtures only')
class StatusTests(unittest.TestCase):
    """[Role] Reuses fixture construction without rerunning imported baseline TestCases."""
    setUp = AssistantTests.setUp
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit
    claim = AssistantTests.claim
    finish = AssistantTests.finish

    def status(self, suffix=''):
        """[Role] Reads only the synthetic user's safe status API."""
        return self.client.get('/api/ai/status' + suffix)

    def age_observations(self):
        """[Role] Ages health observations without touching jobs or extending any lease."""
        with self.store.db(True) as db:
            db.execute('UPDATE ai_providers SET last_checked=?,last_error=NULL', (time.time() - 90,))
            db.execute('UPDATE ai_provider_models SET checked=?', (time.time() - 90,))

    def test_ready_reply_has_no_route_or_identity(self):
        """[Role] Verifies a fresh known connection and its minimal safe response."""
        reply = self.status()
        self.assertEqual(reply.status_code, 200, reply.get_json())
        value = reply.get_json()
        self.assertEqual(value['state'], 'ready')
        self.assertEqual(set(value), {'success', 'state', 'scope', 'checked_at', 'expires_at', 'message'})
        self.assertGreater(value['expires_at'], value['checked_at'])
        self.assertNotIn('127.0.0.1', json.dumps(value))
        self.assertEqual(reply.headers['Cache-Control'], 'no-store')

    def test_local_other_owner_guard_is_yellow_and_private(self):
        """[Role] Confirms only actual local resource blocking changes a queued own job to waiting."""
        self.login(1)
        predecessor = self.submit()
        self.assertEqual(self.claim()['id'], predecessor)
        self.login(2)
        own = self.submit()
        value = self.status('?job_id=' + own).get_json()
        self.assertEqual((value['state'], value['scope']), ('waiting_other', 'job'))
        self.assertNotIn(predecessor, json.dumps(value))
        self.assertEqual(self.status('?job_id=' + predecessor).status_code, 404)

    def test_other_conversation_same_owner_is_also_waiting(self):
        """[Role] Handles multiple sessions of one user through the same local group guard."""
        first = self.submit()
        self.assertEqual(self.claim()['id'], first)
        other = self.submit()
        self.assertEqual(self.status('?job_id=' + other).get_json()['state'], 'waiting_other')

    def test_expired_evidence_and_long_prefill_never_turn_red(self):
        """[Role] Keeps old observations and output-free long generation distinct from a confirmed failure."""
        self.age_observations()
        self.assertEqual(self.status().get_json()['state'], 'stale')
        own = self.submit()
        self.claim()
        self.assertNotEqual(self.status('?job_id=' + own).get_json()['state'], 'unavailable')

    def test_connectivity_error_red_then_ages_and_recovers(self):
        """[Role] Checks actual connection errors, observation expiry and later successful evidence."""
        self.age_observations()
        own = self.submit()
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET state='failed',error_code='CONNECTION_TIMEOUT',updated=? WHERE id=?", (time.time(), own))
        self.assertEqual(self.status().get_json()['state'], 'unavailable')
        with self.store.db(True) as db:
            db.execute('UPDATE jobs SET updated=? WHERE id=?', (time.time() - 90, own))
        self.assertEqual(self.status().get_json()['state'], 'stale')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET state='done',error_code=NULL,updated=? WHERE id=?", (time.time(), own))
        self.assertEqual(self.status().get_json()['state'], 'ready')

    def test_inventory_configuration_failure_is_not_no_response(self):
        """[Role] Separates rejected configuration/auth inventory checks from an unresponsive connection."""
        self.age_observations()
        with self.store.db(True) as db:
            db.execute("UPDATE ai_providers SET last_checked=?,last_error='모델 목록 확인 실패 (HTTPError)'", (time.time(),))
        self.assertEqual(self.status().get_json()['state'], 'checking')

    def test_status_auth_and_input_boundaries(self):
        """[Role] Rejects forged IDs, unknown/duplicate parameters, mutations and logged-out requests."""
        self.assertEqual(self.status('?selection_id=bad').status_code, 404)
        self.assertEqual(self.status('?selection_id=' + 'f' * 32).status_code, 404)
        self.assertEqual(self.status('?job_id=' + 'f' * 32).status_code, 404)
        self.assertEqual(self.status('?provider_url=http://127.0.0.1').status_code, 400)
        self.assertEqual(self.status('?selection_id=' + 'f' * 32 + '&selection_id=' + 'e' * 32).status_code, 400)
        self.assertEqual(self.client.post('/api/ai/status', json={}, headers=self.headers).status_code, 405)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.status().status_code, 200)
        self.client.post('/logout', headers=self.headers)
        self.assertEqual(self.status().status_code, 401)


@unittest.skipUnless(os.name == 'posix', 'Linux loopback fixtures only')
class DeliveryTests(unittest.TestCase):
    """[Role] Measures temporal delivery through the actual parser and worker without real models."""
    def test_small_sse_frame_is_visible_before_connection_finishes(self):
        """[Role] Detects the former byte-buffer wait using a held-open local HTTP response."""
        release = threading.Event()
        observed = threading.Event()
        values = []

        class Handler(BaseHTTPRequestHandler):
            """[Role] Emits one small frame, then waits for the test to permit completion."""
            def log_message(self, *_):
                """[Role] Suppresses synthetic server access logs."""
                pass

            def do_GET(self):
                """[Role] Serves loopback SSE without accessing an upstream model."""
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n')
                self.wfile.flush()
                release.wait(3)
                self.wfile.write(b'data: [DONE]\n\n')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def consume():
            """[Role] Records the first complete upstream frame while the server remains open."""
            with requests.get('http://127.0.0.1:' + str(server.server_port), stream=True, timeout=(2, 4)) as reply:
                for value in sse(reply):
                    if isinstance(value, dict):
                        values.append(value)
                        observed.set()

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        try:
            self.assertTrue(observed.wait(1.5), 'small complete SSE frame waited for extra bytes or EOF')
            self.assertFalse(release.is_set())
            self.assertEqual(values[0]['choices'][0]['delta']['content'], 'a')
        finally:
            release.set()
            reader.join(5)
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_small_worker_batches_arrive_before_done_and_keep_offsets(self):
        """[Role] Exercises 200ms synthetic token arrivals and exact final Unicode across several batches."""
        frames = []
        for value in ('생각😀', ' 더 생각', ' 답변'):
            frames += ['data: ' + json.dumps({'choices': [{'delta': {'content': value}}]}), '']
        frames += ['data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]}), '', 'data: [DONE]', '']
        clock = iter(index * .2 for index in range(100))
        helper = ProtocolTests('runTest')
        with patch('utils.ai_assistant.worker.time.monotonic', side_effect=lambda: next(clock)):
            reports, _ = helper.fake_worker(frames)
        events = [data for path, data in reports if path.endswith('/event') and data.get('content')]
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual(''.join(item['content'] for item in events), '생각😀 더 생각 답변')
        self.assertEqual([item['content_offset'] for item in events], [0, len('생각😀'), len('생각😀 더 생각')])
        self.assertEqual(reports[-1][1]['content'], '생각😀 더 생각 답변')
        self.assertEqual(reports[-1][1]['outcome'], 'complete')
