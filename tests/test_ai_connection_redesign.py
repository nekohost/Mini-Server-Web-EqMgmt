"""[MINI-COMMENT: ASSISTANT.PROVIDERS.REDESIGN.TESTS]
[EN rev.1]
[Role] Verifies the AI connection redesign contracts: immediate display saves, pending route changes that keep a
rename through cutover, pending-change cancellation, served-only user choices and the stored-record archive.
[Dependencies] Established source-derived Flask fixture, loopback TLS fake model servers and the real worker path.
[Impact] No real provider, production database or credential is used.
"""
import os
import unittest

from assistant_fixture_tests import AssistantTests
from assistant_provider_fixture_tests import ProviderTests, admin_post, fake_provider, queue_candidate
from utils.ai_assistant.policy import canonical
from utils.ai_assistant.providers import LEGACY_GROUP


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class ConnectionRedesignTests(unittest.TestCase):
    setUp = AssistantTests.setUp
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit
    claim = AssistantTests.claim
    finish = AssistantTests.finish
    registry = ProviderTests.registry
    add_model = ProviderTests.add_model
    choose = ProviderTests.choose
    run_one = ProviderTests.run_one

    def provider_row(self, pid):
        """[Role] Reads the stored active row and pending revision for one synthetic connection."""
        with self.store.db() as db:
            row = dict(db.execute('SELECT name,revision,enabled,retired,sort_order FROM ai_providers WHERE id=?', (pid,)).fetchone())
            pending = db.execute('SELECT revision FROM ai_provider_candidates WHERE provider=?', (pid,)).fetchone()
        row['pending'] = pending[0] if pending else None
        return row

    def admin_view(self, pid):
        """[Role] Returns one connection from the real admin list API."""
        return next(p for p in self.client.get('/api/admin/ai/providers').get_json()['providers'] if p['id'] == pid)

    def test_display_save_applies_immediately_and_reaches_user_choices(self):
        """A rename needs no new revision or probe and is visible in the next user model list."""
        with fake_provider(self) as peer:
            pid, mid, _ = self.add_model(peer, tools=False)
            self.login(1)
            before = self.provider_row(pid)
            value = admin_post(self, '/api/admin/ai/providers/' + pid + '/display',
                               {'name': 'Renamed GPU', 'sort_order': 3, 'manual': False, 'revision': before['revision']})
            self.assertEqual(value['applied'], 'immediate')
            after = self.provider_row(pid)
            self.assertEqual((after['name'], after['revision'], after['pending'], after['sort_order']), ('Renamed GPU', before['revision'], None, 3))
            self.assertEqual(next(m for m in self.registry.choices()['models'] if m['id'] == mid)['provider'], 'Renamed GPU')
            # Optimistic revision and strict field list are kept.
            admin_post(self, '/api/admin/ai/providers/' + pid + '/display', {'name': 'Late', 'sort_order': 0, 'manual': False, 'revision': before['revision'] + 1}, 409)
            admin_post(self, '/api/admin/ai/providers/' + pid + '/display', {'name': 'X', 'sort_order': 0, 'manual': False, 'revision': before['revision'], 'base_url': peer.base_url}, 400)

    def test_route_save_without_route_change_is_immediate(self):
        """The ordinary save endpoint no longer turns a name-only change into a pending revision."""
        with fake_provider(self) as peer:
            pid, _, _ = self.add_model(peer, tools=False)
            self.login(1)
            before = self.provider_row(pid)
            value = admin_post(self, '/api/admin/ai/providers/' + pid, dict(
                name='Same route new name', base_url=peer.base_url, adapter='openai', resource_group=LEGACY_GROUP,
                enabled=True, manual=True, sort_order=0, revision=before['revision']))
            self.assertEqual(value['applied'], 'immediate')
            after = self.provider_row(pid)
            self.assertEqual((after['name'], after['revision'], after['pending']), ('Same route new name', before['revision'], None))

    def test_route_change_is_pending_keeps_rename_through_cutover(self):
        """An address change waits for probes; a rename made meanwhile survives the automatic cutover."""
        with fake_provider(self) as peer:
            pid, mid, _ = self.add_model(peer, tools=False)
            self.login(1)
            with fake_provider(self, models=[{'id': 'fixture-chat'}], address='192.168.0.52') as moved:
                value = admin_post(self, '/api/admin/ai/providers/' + pid, dict(
                    name='Moving GPU', base_url=moved.base_url, adapter='openai', resource_group=LEGACY_GROUP, enabled=True,
                    manual=True, sort_order=0, revision=1, trust_mode='private', ca_pem=moved.ca_pem))
                self.assertEqual(value['applied'], 'pending_change')
                row = self.provider_row(pid)
                self.assertEqual((row['revision'], row['pending'], row['name']), (1, 2, 'Moving GPU'))
                view = self.admin_view(pid)
                self.assertIn('base_url', view['candidate']['changes'])
                self.assertIn('api_key', view['candidate']['changes'])
                self.assertEqual([(m['id'], m['passed']) for m in view['candidate']['required']], [(mid, 0)])
                admin_post(self, '/api/admin/ai/providers/' + pid + '/display', {'name': 'Renamed while pending', 'sort_order': 0, 'manual': True, 'revision': 1})
                admin_post(self, '/api/admin/ai/providers/' + pid + '/discover', {'candidate_revision': 2})
                jid = queue_candidate(self, pid, mid, 2, tools=False)
                job = self.claim()
                self.assertEqual(job['id'], jid)
                self.run_one(job)
                row = self.provider_row(pid)
                self.assertEqual((row['revision'], row['pending'], row['name']), (2, None, 'Renamed while pending'))

    def test_cancel_pending_keeps_active_connection(self):
        """Cancelling discards only the pending revision; a never-activated connection is retired instead."""
        with fake_provider(self) as peer:
            pid, mid, _ = self.add_model(peer, tools=False)
            self.login(1)
            with fake_provider(self, address='192.168.0.53') as moved:
                admin_post(self, '/api/admin/ai/providers/' + pid, dict(
                    name='Fixture', base_url=moved.base_url, adapter='openai', resource_group=LEGACY_GROUP, enabled=True,
                    manual=True, sort_order=0, revision=1, trust_mode='private', ca_pem=moved.ca_pem))
                admin_post(self, '/api/admin/ai/providers/' + pid + '/pending/cancel', {'revision': 3}, 409)
                admin_post(self, '/api/admin/ai/providers/' + pid + '/pending/cancel', {'revision': 2})
                row = self.provider_row(pid)
                self.assertEqual((row['revision'], row['pending'], row['enabled'], row['retired']), (1, None, 1, 0))
                self.assertTrue(next(m for m in self.registry.choices()['models'] if m['id'] == mid)['available'])
                created = admin_post(self, '/api/admin/ai/providers', dict(
                    name='Never applied', base_url=moved.base_url, adapter='openai', resource_group=LEGACY_GROUP, enabled=True,
                    manual=False, revision=0, trust_mode='private', ca_pem=moved.ca_pem), 201)
                self.assertEqual(created['applied'], 'pending_change')
                admin_post(self, '/api/admin/ai/providers/' + created['id'] + '/pending/cancel', {'revision': 1})
                self.assertEqual(self.provider_row(created['id'])['retired'], 1)

    def test_absent_model_leaves_user_choices_and_appears_in_archive(self):
        """A stored model the connection no longer serves is not offered; the archive shows it and it returns when served."""
        with fake_provider(self, models=[{'id': 'fixture-chat'}]) as peer:
            pid, mid, key = self.add_model(peer, tools=False)
            self.login(1)
            peer.models = [{'id': 'other-chat'}]
            self.registry.discover(pid, True)
            self.assertNotIn(mid, [m['id'] for m in self.registry.choices()['models']])
            view = self.admin_view(pid)
            self.assertNotIn(mid, [m['id'] for m in view['models']])
            self.assertEqual(view['archived_count'], 1)
            response = self.client.get('/api/admin/ai/models/archive?provider=' + pid)
            self.assertEqual(response.status_code, 200)
            archive = response.get_json()
            self.assertEqual([(m['id'], m['published']) for m in archive['models']], [(mid, 1)])
            text = canonical(archive)
            for secret in (key, 'fernet:', peer.base_url, 'credential', 'base_url'):
                self.assertNotIn(secret, text)
            self.assertEqual(self.client.get('/admin/ai/models/archive').status_code, 200)
            peer.models = [{'id': 'fixture-chat'}]
            self.registry.discover(pid, True)
            self.assertTrue(next(m for m in self.registry.choices()['models'] if m['id'] == mid)['available'])
            self.assertEqual(self.admin_view(pid)['archived_count'], 1)  # 'other-chat' is now the absent record

    def test_new_connection_keeps_display_fields_and_stale_unpublish_is_rejected(self):
        """Review fixes: a new connection stores manual/order on its own row; an archive unpublish with a stale
        profile revision cannot overwrite newer model settings."""
        with fake_provider(self) as peer:
            pid, mid, _ = self.add_model(peer, tools=False)
            self.login(1)
            with fake_provider(self, address='192.168.0.54') as other:
                created = admin_post(self, '/api/admin/ai/providers', dict(
                    name='Ordered new', base_url=other.base_url, adapter='openai', resource_group=LEGACY_GROUP, enabled=True,
                    manual=True, sort_order=7, revision=0, trust_mode='private', ca_pem=other.ca_pem), 201)
                view = self.admin_view(created['id'])
                self.assertEqual((view['manual'], view['sort_order']), (1, 7))
            with self.store.db() as db:
                current = db.execute('SELECT profile_revision FROM ai_provider_models WHERE id=?', (mid,)).fetchone()[0]
            stale = dict(id=mid, label='Fixture model', published=False, sort_order=0, context_tokens=65536, revision=1, profile_revision=current + 1)
            admin_post(self, '/api/admin/ai/providers/' + pid + '/models', stale, 409)
            admin_post(self, '/api/admin/ai/providers/' + pid + '/models', {**stale, 'profile_revision': current})

    def test_archive_and_new_mutations_require_admin(self):
        """Ordinary sessions cannot read the archive or use the new mutation routes."""
        self.assertEqual(self.client.get('/api/admin/ai/models/archive').status_code, 403)
        self.assertEqual(self.client.get('/admin/ai/models/archive').status_code, 403)
        pid = '0' * 31 + '1'
        for path in ('/display', '/pending/cancel'):
            self.assertEqual(self.client.post('/api/admin/ai/providers/' + pid + path, json={}, headers=self.headers).status_code, 403)
