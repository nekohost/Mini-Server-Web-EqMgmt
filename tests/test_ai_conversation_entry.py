"""Real Flask admission and SQLite durability checks using the ordinary isolated assistant fixture."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
import unittest
import uuid

import test_equipment_ai as fixture


@unittest.skipUnless(os.name == 'posix', 'Actual behavior tests run on isolated Linux fixtures only')
class EntryTests(unittest.TestCase):
    def setUp(self):
        """Use a new private equipment/AI DB and ordinary signed account for each case."""
        self.fx = fixture.AssistantTests()
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()
        self.store = self.fx.store
        self.client = self.fx.client
        self.url = '/api/ai/conversations/first-turn'
        inventory = self.fx.app.extensions['equipment_assistant']['registry'].choices()
        self.payload = dict(content='첫 질문', selection_id=inventory['default_model'], level='medium',
                            client_key=uuid.uuid4().hex, reasoning_version=2)

    def send(self, **changes):
        """Exercise the browser route with the same immutable key unless explicitly replaced."""
        return self.client.post(self.url, json={**self.payload, **changes}, headers=self.fx.headers)

    def counts(self):
        """Count real rows, including the separate assistant response placeholder."""
        with self.store.db() as db:
            return tuple(db.execute(query).fetchone()[0] for query in (
                'SELECT COUNT(*) FROM conversations', "SELECT COUNT(*) FROM messages WHERE role='user'",
                "SELECT COUNT(*) FROM messages WHERE role='assistant'", 'SELECT COUNT(*) FROM jobs'))

    def test_reads_repeated_acceptance_followup_and_model_error(self):
        for url in ('/assistant', '/api/ai/capabilities', '/api/ai/models', '/api/ai/conversations?view=active&resume=1'):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        result = self.send()
        self.assertEqual(result.status_code, 202, result.get_json())
        ack = result.get_json()
        self.assertEqual(self.send().get_json(), ack)
        self.assertEqual(self.counts(), (1, 1, 1, 1))
        cid = ack['conversation_id']
        with self.store.db() as db:
            row = db.execute('SELECT title,next_level,selection_id FROM conversations WHERE id=?', (cid,)).fetchone()
            self.assertEqual(tuple(row), (self.payload['content'], 'medium', self.payload['selection_id']))
        job = self.fx.claim()
        self.fx.finish(job, content='', outcome='failed')
        snapshot = self.client.get('/api/ai/conversations/' + cid + '/messages').get_json()
        self.assertEqual(snapshot['jobs'][0]['state'], 'failed')
        self.assertTrue(snapshot['jobs'][0]['error'])
        self.fx.submit(cid, '후속 질문')
        self.assertEqual(self.counts(), (1, 2, 2, 2))

    def test_concurrent_calls_and_receipt_after_inventory_change(self):
        cookie = self.client.get_cookie('session').value
        gate = Barrier(6)
        def fire(_):
            """Release six independent authenticated HTTP clients on the same submission."""
            client = self.fx.app.test_client()
            client.set_cookie('session', cookie)
            gate.wait(timeout=8)
            response = client.post(self.url, json=self.payload, headers=self.fx.headers)
            return response.status_code, response.get_json()
        with ThreadPoolExecutor(max_workers=6) as pool:
            answers = list(pool.map(fire, range(6)))
        self.assertEqual({status for status, _ in answers}, {202})
        self.assertEqual(len({(r['conversation_id'], r['job_id']) for _, r in answers}), 1)
        self.assertEqual(self.counts(), (1, 1, 1, 1))
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET published=0')
        self.assertEqual(self.send().get_json(), answers[0][1])
        for changes in (dict(content='수정'), dict(level='off'), dict(web_search=False), dict(selection_id='a'*32)):
            self.assertEqual(self.send(**changes).status_code, 409)
        self.assertEqual(self.counts(), (1, 1, 1, 1))

    def test_rejections_and_rollback(self):
        for changes in (dict(content='  '), dict(content='x'*8001), dict(level='invalid'),
                        dict(selection_id='0'*32), dict(reasoning_version=1), dict(owner=3)):
            self.assertGreaterEqual(self.send(**changes).status_code, 400, changes.keys())
        for headers in ({}, {**self.fx.headers, 'Origin':'https://other.example'}):
            self.assertEqual(self.client.post(self.url, json=self.payload, headers=headers).status_code, 403)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.store.turn_limit_minute = 0
        self.assertEqual(self.send().status_code, 429)
        self.store.turn_limit_minute = 10
        self.store.history_limit = self.store.completion_reserve = 0
        self.assertEqual(self.send().status_code, 429)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.store.history_limit = 32000000
        with self.store.db(True) as db:
            db.execute("""CREATE TRIGGER fail_placeholder BEFORE INSERT ON messages WHEN NEW.role='assistant'
                BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END""")
        self.assertEqual(self.send().status_code, 500)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        with self.store.db(True) as db:
            db.execute('DROP TRIGGER fail_placeholder')
        self.assertEqual(self.send().status_code, 202)
        self.assertEqual(self.counts(), (1, 1, 1, 1))

    def test_deletion_replay_and_account_isolation(self):
        original = self.send().get_json()
        cid = original['conversation_id']
        self.fx.login(3)
        self.assertIsNone(self.client.get('/api/ai/conversations?resume=1').get_json()['resume_conversation'])
        self.assertEqual(self.client.get('/api/ai/conversations/' + cid + '/messages').status_code, 404)
        other = self.send().get_json()
        self.assertNotEqual(other['conversation_id'], cid)
        self.fx.login(2)
        for action, status, revision in [('trash', 409, 0), ('purge', 410, 1)]:
            response = self.client.post('/api/ai/conversations/' + cid + '/' + action,
                json=dict(lifecycle_revision=revision, operation_id=uuid.uuid4().hex), headers=self.fx.headers)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(self.send().status_code, status)
        self.assertEqual(self.counts(), (1, 1, 1, 1))

    def test_resume_beyond_page_and_conversation_quota(self):
        cid = self.send().get_json()['conversation_id']
        with self.store.db(True) as db:
            account = db.execute('SELECT account_key FROM conversations WHERE id=?', (cid,)).fetchone()[0]
            for _ in range(199):
                self.store._insert_conversation(db, 2, account, uuid.uuid4().hex)
        listing = self.client.get('/api/ai/conversations?view=active&resume=1').get_json()
        self.assertEqual(len(listing['conversations']), 50)
        self.assertNotIn(cid, [c['id'] for c in listing['conversations']])
        self.assertEqual(listing['resume_conversation']['id'], cid)
        self.assertEqual(self.send().status_code, 202)
        self.assertEqual(self.send(client_key=uuid.uuid4().hex).status_code, 429)
        self.assertEqual(self.counts(), (200, 1, 1, 1))

    def test_probe_only_legacy_history_and_queue_limit(self):
        """Empty/probe sessions can't displace real history; a full owner queue admits no phantom chat."""
        old = self.fx.conversation()
        self.assertIsNone(self.client.get('/api/ai/conversations?resume=1').get_json()['resume_conversation'])
        probe = self.send().get_json()
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET purpose='probe' WHERE id=?", (probe['job_id'],))
            db.execute("INSERT INTO messages(conversation,role,content,created) VALUES(?,'user','legacy',1)", (probe['conversation_id'],))
            db.execute("INSERT INTO messages(conversation,role,content,created) VALUES(?,'user','legacy',1)", (old,))
        listing = self.client.get('/api/ai/conversations?resume=1').get_json()
        self.assertEqual(listing['resume_conversation']['id'], old)
        self.assertNotIn(probe['conversation_id'], [item['id'] for item in listing['conversations']])
        self.assertEqual(self.send(client_key=uuid.uuid4().hex).status_code, 202)
        before = self.counts()
        self.assertEqual(self.send(client_key=uuid.uuid4().hex).status_code, 429)
        self.assertEqual(self.counts(), before)
