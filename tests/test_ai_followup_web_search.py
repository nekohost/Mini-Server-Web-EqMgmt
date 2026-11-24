"""[MINI-COMMENT: ASSISTANT.FOLLOWUP.WEB_SEARCH.TESTS]
[EN rev.2]
[Role] Exercises multi-step follow-up web search compatibility, expanded search budget, projection, bounded recovery and safety boundaries in isolated Linux fixtures.
[Dependencies] assistant_fixture_tests, assistant_provider_fixture_tests, real Flask routes/store/domain and fake transport/search services; never opens production data.
[Impact] Verifies multi-step real-case replay up to MAX_SEARCHES, raw DB immutability, search_decided recovery, privacy taint/query blocks, compaction ledger invariants and 32K overhead bounds.
"""
import json
import os
import unittest
import uuid

from cryptography.fernet import Fernet

import assistant_fixture_tests
import assistant_provider_fixture_tests
from utils.ai_assistant import project_search_messages
from utils.ai_assistant.policy import PLANNING_INSTRUCTIONS, canonical
from utils.ai_assistant.providers import LEGACY_GROUP
from utils.ai_assistant.recovery import CORRECTIONS, correction_phase, model_context
from utils.ai_assistant.web_search import MAX_SEARCHES, evidence_chars, public_searches, search_permitted, validate_query

AssistantTests = assistant_fixture_tests.AssistantTests
ProviderTests = assistant_provider_fixture_tests.ProviderTests
admin_post = assistant_provider_fixture_tests.admin_post
fake_provider = assistant_provider_fixture_tests.fake_provider
_OMIT = object()


class _FollowupFakeSearch:
    """Deterministic fake search backend returning public_searches-compatible payloads."""

    def __init__(self, available=True, snippet_size=40):
        self.available = available
        self.snippet_size = snippet_size
        self.providers = [
            {'id': 'yahoo', 'label': 'Yahoo', 'available': True, 'scopes': ['web']},
            {'id': 'github', 'label': 'GitHub', 'available': True, 'scopes': ['repositories', 'issues']},
        ]
        self.calls = []
        self.failure = None

    def search(self, query, max_results=5, sensitive=(), provider='auto', scope=None):
        validated = validate_query(query, sensitive)
        self.calls.append({
            'query': validated,
            'max_results': max_results,
            'sensitive': tuple(sensitive),
            'provider': provider,
            'scope': scope,
        })
        if self.failure is not None:
            raise self.failure
        resolved_provider = 'yahoo' if provider == 'auto' else provider
        resolved_engine = {'yahoo': 'Yahoo', 'google': 'Google', 'github': 'GitHub'}[resolved_provider]
        resolved_scope = scope or ('repositories' if resolved_provider == 'github' else 'web')
        snippet = f'Public spec #{len(self.calls)} for {validated}'.ljust(self.snippet_size, 'x')
        return {
            'kind': 'web_search',
            'version': 1,
            'engine': resolved_engine,
            'scope': resolved_scope,
            'query': validated,
            'searched_at': '2026-11-24T09:00:00+09:00',
            'status': 'ok',
            'results': [
                {
                    'number': 1,
                    'title': f'{resolved_engine} result for {validated}',
                    'url': 'https://example.org/spec/' + str(len(self.calls)),
                    'snippet': snippet,
                }
            ],
        }


def _call(cid, name, args):
    return {'id': cid, 'name': name, 'arguments': canonical(args) if isinstance(args, dict) else args}


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class FollowupWebSearchTests(unittest.TestCase):
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    claim = AssistantTests.claim
    finish = AssistantTests.finish
    registry = ProviderTests.registry
    add_model = ProviderTests.add_model
    choose = ProviderTests.choose

    def setUp(self):
        AssistantTests.setUp(self)
        self.search = _FollowupFakeSearch()
        self.domain.search_service = self.search

    def _submit(self, cid=None, content='LGA 2011-3 non-ECC DDR4 메인보드 추천', level='medium', web_search=_OMIT, key=None):
        cid = cid or self.conversation()
        body = {
            'content': content,
            'reasoning_version': 2,
            'level': level,
            'client_key': key or uuid.uuid4().hex,
        }
        if web_search is not _OMIT:
            body['web_search'] = web_search
        response = self.client.post('/api/ai/conversations/' + cid + '/turns', json=body, headers=self.headers)
        self.assertEqual(response.status_code, 202, response.get_json())
        return cid, response.get_json()['job_id']

    def _job(self, jid):
        with self.store.db() as db:
            return dict(self.store.job(jid, db))

    def _job_status(self, jid):
        response = self.client.get('/api/ai/jobs/' + jid, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _setup_model_with_context(self, context_tokens=32768):
        peer = self.enterContext(fake_provider(self, models=[{'id': f'followup-{context_tokens}'}]))
        if not self.app.config.get('USER_AI_PROVIDER_ENCRYPTION_KEY'):
            self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        key = 'synthetic-model-key-' + uuid.uuid4().hex
        peer.keys.add(key)
        with self.client.session_transaction() as sess:
            previous_user = sess['user']['UserId']
        self.login(1)
        try:
            data = dict(
                name='Fixture ' + uuid.uuid4().hex[:6],
                base_url=peer.base_url,
                adapter='openai',
                enabled=True,
                manual=True,
                revision=0,
                api_key=key,
                resource_group=LEGACY_GROUP,
                trust_mode='private',
                ca_pem=peer.ca_pem,
            )
            pid = admin_post(self, '/api/admin/ai/providers', data, 201)['id']
            reg = admin_post(self, f'/api/admin/ai/providers/{pid}/discover', {'candidate_revision': 1})
            candidate = next(p for p in reg['providers'] if p['id'] == pid)['candidate']
            mid = next(m['id'] for m in candidate['models'] if m['upstream'] == f'followup-{context_tokens}')
            jid = admin_post(
                self,
                f'/api/admin/ai/models/{mid}/probe',
                dict(
                    provider_id=pid,
                    candidate_revision=1,
                    context_tokens=context_tokens,
                    client_key=uuid.uuid4().hex,
                    tools=True,
                    reasoning=False,
                ),
                202,
            )['job_id']
            for _ in range(2):
                job = self.claim()
                self.assertIsNotNone(job)
                self.assertEqual(job['id'], jid)
                ProviderTests.run_one(self, job)
            admin_post(
                self,
                f'/api/admin/ai/providers/{pid}/models',
                dict(id=mid, label='Fixture model', published=True, sort_order=0, context_tokens=context_tokens, revision=1),
            )
            return pid, mid
        finally:
            self.login(previous_user)

    def _seed_history(self, cid, pairs):
        now = 1700000000.0
        with self.store.db(True) as db:
            for index, (question, answer) in enumerate(pairs):
                jid = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO jobs(id,conversation,owner,client_key,input_hash,binding,expires,level,state,queue_order,context,steps,purpose,route_snapshot,resource_group,handoff_chars,reserved_chars,created,updated)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (jid, cid, 2, 'seed-' + uuid.uuid4().hex, 'hash', 'bind', now + 1800, 'default', 'done', index + 1, '[]', 1, 'chat', '{}', LEGACY_GROUP, 0, 0, now + index, now + index),
                )
                db.execute("INSERT INTO messages(conversation,job,role,reasoning,content,created) VALUES(?,?,'user','',?,?)", (cid, jid, question, now + index))
                db.execute("INSERT INTO messages(conversation,job,role,reasoning,content,created) VALUES(?,?,'assistant','',?,?)", (cid, jid, answer, now + index))
            db.execute('DELETE FROM storage_accounts')

    def test_01_step0_plan_step1_followup_plan_replay_and_complete(self):
        _, jid = self._submit(level='medium')
        step0 = self.claim()
        self.assertEqual(step0['required_tool'], 'plan_web_search')
        self.assertIn(PLANNING_INSTRUCTIONS, step0['messages'][0]['content'])
        self.assertIn(f'남은 웹 검색 횟수:{MAX_SEARCHES}/{MAX_SEARCHES}', step0['messages'][0]['content'])
        self.assertEqual([t['function']['name'] for t in step0['tools']], ['plan_web_search'])

        res0 = self.finish(step0, calls=[_call('c0', 'plan_web_search', {
            'needed': True,
            'query': 'dual socket LGA 2011-3 motherboard support non-ECC DDR4 8 DIMM slots',
        })], content='')
        self.assertEqual(res0['state'], 'queued')
        self.assertEqual(len(self.search.calls), 1)

        step1 = self.claim()
        self.assertIsNone(step1['required_tool'])
        self.assertNotIn(PLANNING_INSTRUCTIONS, step1['messages'][0]['content'])
        tool_names = {t['function']['name'] for t in step1['tools']}
        self.assertIn('web_search', tool_names)
        self.assertNotIn('plan_web_search', tool_names)
        self.assertIn(f'남은 웹 검색 횟수:{MAX_SEARCHES - 1}/{MAX_SEARCHES}', step1['messages'][0]['content'])
        projected_step0_call = next(m['tool_calls'][0]['function'] for m in step1['messages'] if m.get('tool_calls'))
        self.assertEqual(projected_step0_call['name'], 'web_search')
        self.assertNotIn('needed', json.loads(projected_step0_call['arguments']))

        # Simulate the real-incident model re-invoking plan_web_search on Step 1, then deep research up to MAX_SEARCHES.
        res1 = self.finish(step1, calls=[_call('c1', 'plan_web_search', {
            'needed': True,
            'query': 'ASUS Z10PE-D8 WS non-ECC UDIMM DDR4 support',
        })], content='')
        self.assertEqual(res1['state'], 'queued')
        for idx in range(2, MAX_SEARCHES):
            step_n = self.claim()
            self.assertIn(f'남은 웹 검색 횟수:{MAX_SEARCHES - idx}/{MAX_SEARCHES}', step_n['messages'][0]['content'])
            tool_name = 'plan_web_search' if idx % 2 == 1 else 'web_search'
            call_args = {'needed': True, 'query': f'Followup board verification #{idx}'} if tool_name == 'plan_web_search' else {'query': f'Followup board verification #{idx}'}
            self.assertEqual(self.finish(step_n, calls=[_call(f'c{idx}', tool_name, call_args)], content='')['state'], 'queued')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)

        final_step = self.claim()
        final_names = {t['function']['name'] for t in final_step['tools']}
        self.assertNotIn('web_search', final_names)
        self.assertNotIn('plan_web_search', final_names)
        self.assertIn(f'남은 웹 검색 횟수:0/{MAX_SEARCHES}', final_step['messages'][0]['content'])

        res_done = self.finish(final_step, content='확인한 공식 사양 기준 비교 결과입니다 [1][2][3].')
        self.assertEqual(res_done['state'], 'done')
        view = self._job_status(jid)
        self.assertEqual(view['state'], 'done')
        self.assertEqual(view['web_search_version'], MAX_SEARCHES)
        self.assertEqual(len(view['web_searches']), MAX_SEARCHES)
        self.assertEqual(view['web_searches'][1]['query'], 'ASUS Z10PE-D8 WS non-ECC UDIMM DDR4 support')
        ack = self.client.get(f'/api/ai/jobs/{jid}?w={MAX_SEARCHES}', headers=self.headers)
        self.assertEqual(ack.status_code, 200)
        self.assertIsNone(ack.get_json()['web_searches'])
        self.assertEqual(self.client.get(f'/api/ai/jobs/{jid}?w={MAX_SEARCHES + 1}', headers=self.headers).status_code, 400)

    def test_02_raw_db_immutable_vs_projected_payload_only(self):
        _, jid = self._submit()
        step0 = self.claim()
        self.finish(step0, calls=[_call('c0', 'plan_web_search', {
            'needed': True,
            'query': 'server ram spec',
            'provider': 'github',
            'scope': 'repositories',
            'max_results': 3,
        })], content='')

        step1 = self.claim()
        projected_fn = next(m['tool_calls'][0]['function'] for m in step1['messages'] if m.get('tool_calls'))
        self.assertEqual(projected_fn['name'], 'web_search')
        self.assertEqual(json.loads(projected_fn['arguments']), {
            'max_results': 3,
            'provider': 'github',
            'query': 'server ram spec',
            'scope': 'repositories',
        })

        raw_context = json.loads(self._job(jid)['context'])
        raw_fn = next(m['tool_calls'][0]['function'] for m in raw_context if m.get('tool_calls'))
        self.assertEqual(raw_fn['name'], 'plan_web_search')
        self.assertIs(json.loads(raw_fn['arguments'])['needed'], True)
        self.assertEqual(model_context(raw_context)[-2]['tool_calls'][0]['function']['name'], 'plan_web_search')

        sample = [
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'x1', 'type': 'function', 'function': {'name': 'plan_web_search', 'arguments': '{"needed":true,"query":"ddr4"}'}}]},
            {'role': 'tool', 'tool_call_id': 'x1', 'content': canonical({'kind': 'web_search', 'version': 1, 'query': 'ddr4'})},
        ]
        snapshot = canonical(sample)
        inactive = project_search_messages(sample, active=False)
        self.assertEqual(inactive[0]['tool_calls'][0]['function']['name'], 'plan_web_search')
        active = project_search_messages(sample, active=True)
        self.assertEqual(active[0]['tool_calls'][0]['function']['name'], 'web_search')
        self.assertEqual(canonical(sample), snapshot)

    def test_03_plan_false_followup_recovery_after_both_true_and_false(self):
        # Case A: Step 0 plan(true) -> Step 1 plan(false) -> 1-time search_decided recovery
        _, jid_a = self._submit()
        self.finish(self.claim(), calls=[_call('a0', 'plan_web_search', {'needed': True, 'query': 'ddr4 udimm spec'})], content='')
        res_a1 = self.finish(self.claim(), calls=[_call('a1', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_a1['state'], 'queued')
        self.assertEqual(res_a1['response_correction'], 'search_decided')

        job_a = self._job(jid_a)
        ctx_a = json.loads(job_a['context'])
        self.assertIs(search_permitted(job_a, json.loads(job_a['route_snapshot'])), True)
        self.assertEqual(correction_phase(job_a), 'search_decided')
        self.assertFalse(any(m.get('role') == 'tool' and 'web_search_plan' in m.get('content', '') for m in ctx_a))

        step_a2 = self.claim()
        self.assertIn(CORRECTIONS['search_decided'], step_a2['messages'][0]['content'])
        self.assertNotIn(PLANNING_INSTRUCTIONS, step_a2['messages'][0]['content'])
        names_a2 = {t['function']['name'] for t in step_a2['tools']}
        self.assertIn('search_equipment', names_a2)
        self.assertIn('web_search', names_a2)

        res_a2 = self.finish(step_a2, calls=[_call('a2', 'search_equipment', {'query': 'My'})], content='')
        self.assertEqual(res_a2['state'], 'queued')
        res_a3 = self.finish(self.claim(), content='내 장비와 검색 출처를 함께 정리했습니다 [1].')
        self.assertEqual(res_a3['state'], 'done')

        # Case A repeat: calling plan(false) a second time after search_decided consumed fails
        _, jid_a_rep = self._submit()
        self.finish(self.claim(), calls=[_call('r0', 'plan_web_search', {'needed': True, 'query': 'ddr4 udimm spec'})], content='')
        self.finish(self.claim(), calls=[_call('r1', 'plan_web_search', {'needed': False})], content='')
        res_a_rep = self.finish(self.claim(), calls=[_call('r2', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_a_rep['state'], 'failed')
        self.assertEqual(res_a_rep['error_code'], 'INVALID_TOOL_CALL')

        # Case B: Step 0 plan(false) -> Step 1 plan(false) -> 1-time search_decided recovery
        _, jid_b = self._submit(content='내 장비 목록 보여줘')
        self.finish(self.claim(), calls=[_call('b0', 'plan_web_search', {'needed': False})], content='')
        res_b1 = self.finish(self.claim(), calls=[_call('b1', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_b1['state'], 'queued')
        self.assertEqual(res_b1['response_correction'], 'search_decided')
        step_b2 = self.claim()
        self.assertIn(CORRECTIONS['search_decided'], step_b2['messages'][0]['content'])
        self.assertNotIn('web_search', {t['function']['name'] for t in step_b2['tools']})
        self.assertIn('search_equipment', {t['function']['name'] for t in step_b2['tools']})
        self.assertEqual(self.finish(step_b2, content='보유 장비를 기준으로 답변드립니다.')['state'], 'done')

    def test_04_step0_plan_false_then_step1_plan_true_rejected(self):
        _, jid = self._submit(content='일반 설명 해줘')
        self.finish(self.claim(), calls=[_call('c0', 'plan_web_search', {'needed': False})], content='')
        res = self.finish(self.claim(), calls=[_call('c1', 'plan_web_search', {'needed': True, 'query': 'forbidden search'})], content='')
        self.assertEqual(res['state'], 'failed')
        self.assertEqual(res['error_code'], 'INVALID_TOOL_CALL')
        self.assertEqual(len(self.search.calls), 0)
        self.assertEqual(self._job(jid)['state'], 'failed')

    def test_05_required_and_off_reject_plan_web_search_immediately(self):
        # Required mode: Step 0 web_search -> Step 1 plan(true) or plan(false) fails immediately
        self._submit(web_search=True)
        self.finish(self.claim(), calls=[_call('req0', 'web_search', {'query': 'flask official docs'})], content='')
        res_req = self.finish(self.claim(), calls=[_call('req1', 'plan_web_search', {'needed': True, 'query': 'extra query'})], content='')
        self.assertEqual(res_req['state'], 'failed')
        self.assertEqual(res_req['error_code'], 'INVALID_TOOL_CALL')
        self.assertEqual(len(self.search.calls), 1)

        self._submit(web_search=True)
        self.finish(self.claim(), calls=[_call('rf0', 'web_search', {'query': 'flask docs'})], content='')
        res_rf = self.finish(self.claim(), calls=[_call('rf1', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_rf['state'], 'failed')
        self.assertEqual(res_rf['error_code'], 'INVALID_TOOL_CALL')

        # Off mode: Step 0 plan_web_search(false) or (true) fails immediately
        self._submit(web_search=False)
        res_off = self.finish(self.claim(), calls=[_call('off0', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_off['state'], 'failed')
        self.assertEqual(res_off['error_code'], 'INVALID_TOOL_CALL')

        self._submit(web_search=False)
        res_off2 = self.finish(self.claim(), calls=[_call('off1', 'plan_web_search', {'needed': True, 'query': 'not allowed'})], content='')
        self.assertEqual(res_off2['state'], 'failed')
        self.assertEqual(res_off2['error_code'], 'INVALID_TOOL_CALL')

    def test_06_auto_exhausted_limit_recovers_once_then_limit(self):
        # Subcase 1: web_search at 0/MAX_SEARCHES recovers once then completes
        self._submit()
        self.finish(self.claim(), calls=[_call('s0', 'plan_web_search', {'needed': True, 'query': 'spec 0'})], content='')
        for idx in range(1, MAX_SEARCHES):
            self.finish(self.claim(), calls=[_call(f's{idx}', 'web_search', {'query': f'spec {idx}'})], content='')
        res_recover = self.finish(self.claim(), calls=[_call('s_over', 'web_search', {'query': 'extra spec'})], content='')
        self.assertEqual(res_recover['state'], 'queued')
        self.assertEqual(res_recover['response_correction'], 'search_decided')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)

        final_step = self.claim()
        self.assertIn(CORRECTIONS['search_decided'], final_step['messages'][0]['content'])
        self.assertNotIn('web_search', {t['function']['name'] for t in final_step['tools']})
        self.assertEqual(self.finish(final_step, content='이미 검색한 결과로 안내드립니다 [1][2].')['state'], 'done')

        # Subcase 2: plan_web_search(needed=True) at 0/MAX_SEARCHES recovers once, repeating hits WEB_SEARCH_LIMIT
        self.search.calls.clear()
        self._submit()
        self.finish(self.claim(), calls=[_call('p0', 'plan_web_search', {'needed': True, 'query': 'q 0'})], content='')
        for idx in range(1, MAX_SEARCHES):
            self.finish(self.claim(), calls=[_call(f'p{idx}', 'plan_web_search', {'needed': True, 'query': f'q {idx}'})], content='')
        res_p2 = self.finish(self.claim(), calls=[_call('p_over', 'plan_web_search', {'needed': True, 'query': 'extra q'})], content='')
        self.assertEqual(res_p2['state'], 'queued')
        self.assertEqual(res_p2['response_correction'], 'search_decided')
        res_p3 = self.finish(self.claim(), calls=[_call('p_rep', 'web_search', {'query': 'repeat q'})], content='')
        self.assertEqual(res_p3['state'], 'failed')
        self.assertEqual(res_p3['error_code'], 'WEB_SEARCH_LIMIT')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)

    def test_07_required_exhausted_limit_fails_immediately_with_limit(self):
        self._submit(web_search=True)
        for idx in range(MAX_SEARCHES):
            self.finish(self.claim(), calls=[_call(f'q{idx}', 'web_search', {'query': f'required q {idx}'})], content='')
        res = self.finish(self.claim(), calls=[_call('q_over', 'web_search', {'query': 'extra required'})], content='')
        self.assertEqual(res['state'], 'failed')
        self.assertEqual(res['error_code'], 'WEB_SEARCH_LIMIT')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)

    def test_08_batch_types_and_missing_query_validation(self):
        # 1. Pure [web_search, plan(true)] multi-search batch with 1 remaining runs 1st and controls 2nd
        self._submit()
        self.finish(self.claim(), calls=[_call('b0', 'plan_web_search', {'needed': True, 'query': 'base q 0'})], content='')
        for idx in range(1, MAX_SEARCHES - 1):
            self.finish(self.claim(), calls=[_call(f'b{idx}', 'web_search', {'query': f'base q {idx}'})], content='')
        res_multi = self.finish(self.claim(), calls=[
            _call('m1', 'web_search', {'query': 'alpha follow'}),
            _call('m2', 'plan_web_search', {'needed': True, 'query': 'beta follow'}),
        ], content='')
        self.assertEqual(res_multi['state'], 'queued')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)
        next_step = self.claim()
        tool_msgs = [json.loads(m['content']) for m in next_step['messages'] if m.get('role') == 'tool']
        self.assertEqual(tool_msgs[-1]['kind'], 'web_search_control')
        self.assertEqual(tool_msgs[-1]['reason'], 'budget_exhausted')
        self.assertEqual(self.finish(next_step, content='Batch handled.')['state'], 'done')

        # 2. Mixed [plan(true), search_equipment] rejected before any I/O
        self.search.calls.clear()
        self._submit()
        self.finish(self.claim(), calls=[_call('x0', 'plan_web_search', {'needed': True, 'query': 'base q'})], content='')
        res_mix_t = self.finish(self.claim(), calls=[
            _call('mt1', 'plan_web_search', {'needed': True, 'query': 'alpha'}),
            _call('mt2', 'search_equipment', {'query': 'My'}),
        ], content='')
        self.assertEqual(res_mix_t['state'], 'failed')
        self.assertEqual(res_mix_t['error_code'], 'INVALID_TOOL_CALL')
        self.assertEqual(len(self.search.calls), 1)

        # 3. Mixed [plan(false), search_equipment] rejected before any I/O
        self._submit()
        self.finish(self.claim(), calls=[_call('y0', 'plan_web_search', {'needed': True, 'query': 'base q'})], content='')
        res_mix_f = self.finish(self.claim(), calls=[
            _call('mf1', 'plan_web_search', {'needed': False}),
            _call('mf2', 'search_equipment', {'query': 'My'}),
        ], content='')
        self.assertEqual(res_mix_f['state'], 'failed')
        self.assertEqual(res_mix_f['error_code'], 'INVALID_TOOL_CALL')

        # 4. Missing query -> INVALID_TOOL_CALL; <2 char query -> WEB_SEARCH_BLOCKED (both before search I/O)
        for bad_args, expected_code in (({'needed': True}, 'INVALID_TOOL_CALL'), ({'needed': True, 'query': 'a'}, 'WEB_SEARCH_BLOCKED')):
            self.search.calls.clear()
            self._submit()
            self.finish(self.claim(), calls=[_call('z0', 'plan_web_search', {'needed': True, 'query': 'base q'})], content='')
            res_bad = self.finish(self.claim(), calls=[_call('z1', 'plan_web_search', bad_args)], content='')
            self.assertEqual(res_bad['state'], 'failed')
            self.assertEqual(res_bad['error_code'], expected_code)
            self.assertEqual(len(self.search.calls), 1)

    def test_09_quoted_booleans_normalized_before_routing(self):
        # String "False" normalizes to Python False -> search_decided recovery, never executes search
        self._submit()
        self.finish(self.claim(), calls=[_call('q0', 'plan_web_search', {'needed': True, 'query': 'base'})], content='')
        res_f = self.finish(self.claim(), calls=[_call('q1', 'plan_web_search', '{"needed":"False","query":"should not run"}')], content='')
        self.assertEqual(res_f['state'], 'queued')
        self.assertEqual(res_f['response_correction'], 'search_decided')
        self.assertEqual(len(self.search.calls), 1)

        # String "True" normalizes to Python True -> runs valid second search
        res_t = self.finish(self.claim(), calls=[_call('q2', 'plan_web_search', '{"needed":"True","query":"valid second"}')], content='')
        self.assertEqual(res_t['state'], 'queued')
        self.assertEqual(len(self.search.calls), 2)

        # Invalid string boolean "maybe" fails schema check immediately
        self._submit()
        res_bad = self.finish(self.claim(), calls=[_call('q3', 'plan_web_search', '{"needed":"maybe","query":"x"}')], content='')
        self.assertEqual(res_bad['state'], 'failed')
        self.assertEqual(res_bad['error_code'], 'INVALID_TOOL_CALL')

    def test_10_privacy_and_equipment_taint_block_before_recovery(self):
        # A: Taint after get_equipment blocks follow-up plan_web_search(true) with WEB_SEARCH_BLOCKED
        self._submit()
        self.finish(self.claim(), calls=[_call('t0', 'plan_web_search', {'needed': True, 'query': 'motherboard'})], content='')
        self.finish(self.claim(), calls=[_call('t1', 'get_equipment', {'equipment_id': 2})], content='')
        res_a = self.finish(self.claim(), calls=[_call('t2', 'plan_web_search', {'needed': True, 'query': 'followup public'})], content='')
        self.assertEqual(res_a['state'], 'failed')
        self.assertEqual(res_a['error_code'], 'WEB_SEARCH_BLOCKED')
        self.assertEqual(len(self.search.calls), 1)

        # B: Taint at 0/MAX_SEARCHES blocks BEFORE search_decided recovery
        self.search.calls.clear()
        self._submit()
        self.finish(self.claim(), calls=[_call('u0', 'plan_web_search', {'needed': True, 'query': 'public q 0'})], content='')
        for idx in range(1, MAX_SEARCHES):
            self.finish(self.claim(), calls=[_call(f'u{idx}', 'web_search', {'query': f'public q {idx}'})], content='')
        self.finish(self.claim(), calls=[_call('u_eq', 'get_equipment', {'equipment_id': 2})], content='')
        res_b = self.finish(self.claim(), calls=[_call('u_over', 'web_search', {'query': 'third public'})], content='')
        self.assertEqual(res_b['state'], 'failed')
        self.assertEqual(res_b['error_code'], 'WEB_SEARCH_BLOCKED')

        # C: Sensitive serial / LoginId in query at 0/MAX_SEARCHES blocks BEFORE search_decided recovery
        for leak in ('check SERIAL-2 spec', 'account fixture-2 lookup'):
            self._submit()
            self.finish(self.claim(), calls=[_call('l0', 'plan_web_search', {'needed': True, 'query': 'ok q 0'})], content='')
            for idx in range(1, MAX_SEARCHES):
                self.finish(self.claim(), calls=[_call(f'l{idx}', 'web_search', {'query': f'ok q {idx}'})], content='')
            res_c = self.finish(self.claim(), calls=[_call('l_over', 'web_search', {'query': leak})], content='')
            self.assertEqual(res_c['state'], 'failed')
            self.assertEqual(res_c['error_code'], 'WEB_SEARCH_BLOCKED')

    def test_11_duplicate_query_auto_recovery_vs_distinct_provider_scope(self):
        # Case- and whitespace-normalized exact duplicate in auto triggers 1-time search_decided without I/O
        self._submit()
        self.finish(self.claim(), calls=[_call('d0', 'plan_web_search', {'needed': True, 'query': 'LGA 2011-3 DDR4'})], content='')
        res_dup = self.finish(self.claim(), calls=[_call('d1', 'web_search', {'query': '  lga   2011-3 ddr4 '})], content='')
        self.assertEqual(res_dup['state'], 'queued')
        self.assertEqual(res_dup['response_correction'], 'search_decided')
        self.assertEqual(len(self.search.calls), 1)

        # Different provider/scope with same keywords executes normally
        step2 = self.claim()
        self.assertIn(CORRECTIONS['search_decided'], step2['messages'][0]['content'])
        res_gh = self.finish(step2, calls=[_call('d2', 'web_search', {'query': 'LGA 2011-3 DDR4', 'provider': 'github', 'scope': 'repositories'})], content='')
        self.assertEqual(res_gh['state'], 'queued')
        self.assertEqual(len(self.search.calls), 2)
        self.assertEqual(self.finish(self.claim(), content='Yahoo 및 GitHub 결과를 정리했습니다 [1][2].')['state'], 'done')

        # Repeating same duplicate after search_decided consumed executes remaining 1 quota without looping
        self.search.calls.clear()
        self._submit()
        self.finish(self.claim(), calls=[_call('r0', 'plan_web_search', {'needed': True, 'query': 'DDR4 spec'})], content='')
        res_r1 = self.finish(self.claim(), calls=[_call('r1', 'plan_web_search', {'needed': True, 'query': 'ddr4   spec'})], content='')
        self.assertEqual(res_r1['response_correction'], 'search_decided')
        res_r2 = self.finish(self.claim(), calls=[_call('r2', 'web_search', {'query': 'ddr4 spec'})], content='')
        self.assertEqual(res_r2['state'], 'queued')
        self.assertIsNone(res_r2.get('response_correction'))
        self.assertEqual(len(self.search.calls), 2)
        self.assertEqual(self.finish(self.claim(), content='Done after duplicate.')['state'], 'done')

        # Required mode duplicate runs immediately without search_decided (backward compatibility)
        self.search.calls.clear()
        self._submit(web_search=True)
        self.finish(self.claim(), calls=[_call('rq0', 'web_search', {'query': 'Flask docs'})], content='')
        res_rq = self.finish(self.claim(), calls=[_call('rq1', 'web_search', {'query': 'Flask docs'})], content='')
        self.assertEqual(res_rq['state'], 'queued')
        self.assertIsNone(res_rq.get('response_correction'))
        self.assertEqual(len(self.search.calls), 2)
        self.assertEqual(self.finish(self.claim(), content='Required done.')['state'], 'done')

    def test_12_cross_step_reused_tool_call_id_projection(self):
        # Ordering A: Step 0 non-search call with id='shared', Step 1 plan_web_search with same id='shared'
        items_a = [
            {'role': 'user', 'content': 'check'},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'shared', 'type': 'function', 'function': {'name': 'search_equipment', 'arguments': '{"query":"My"}'}}]},
            {'role': 'tool', 'tool_call_id': 'shared', 'content': canonical({'equipment': [], 'total': 0})},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'shared', 'type': 'function', 'function': {'name': 'plan_web_search', 'arguments': '{"needed":true,"query":"ddr4"}'}}]},
            {'role': 'tool', 'tool_call_id': 'shared', 'content': canonical({'kind': 'web_search', 'version': 1, 'query': 'ddr4'})},
        ]
        proj_a = project_search_messages(items_a, active=True)
        self.assertEqual(proj_a[1]['tool_calls'][0]['function']['name'], 'search_equipment')
        self.assertEqual(proj_a[3]['tool_calls'][0]['function']['name'], 'web_search')
        self.assertEqual(json.loads(proj_a[3]['tool_calls'][0]['function']['arguments']), {'query': 'ddr4'})

        # Ordering B: Step 0 plan_web_search(web_search) id='shared', Step 1 get_equipment id='shared'
        items_b = [
            {'role': 'user', 'content': 'check'},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'shared', 'type': 'function', 'function': {'name': 'plan_web_search', 'arguments': '{"needed":true,"query":"ddr4"}'}}]},
            {'role': 'tool', 'tool_call_id': 'shared', 'content': canonical({'kind': 'web_search', 'version': 1, 'query': 'ddr4'})},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'shared', 'type': 'function', 'function': {'name': 'search_equipment', 'arguments': '{"query":"My"}'}}]},
            {'role': 'tool', 'tool_call_id': 'shared', 'content': canonical({'equipment': [], 'total': 0})},
        ]
        proj_b = project_search_messages(items_b, active=True)
        self.assertEqual(proj_b[1]['tool_calls'][0]['function']['name'], 'web_search')
        self.assertEqual(proj_b[3]['tool_calls'][0]['function']['name'], 'search_equipment')

        # plan_web_search(needed=false) result (web_search_plan) must never project to web_search
        items_plan = [
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'shared', 'type': 'function', 'function': {'name': 'plan_web_search', 'arguments': '{"needed":false}'}}]},
            {'role': 'tool', 'tool_call_id': 'shared', 'content': canonical({'kind': 'web_search_plan', 'needed': False})},
        ]
        self.assertEqual(project_search_messages(items_plan, active=True)[0]['tool_calls'][0]['function']['name'], 'plan_web_search')

    def test_13_compaction_and_evidence_ledger_invariants(self):
        _, mid = self._setup_model_with_context(49152)
        cid = self.conversation()
        self.assertEqual(self.choose(cid, mid, level='default').status_code, 200)
        self._seed_history(cid, [(f'Past question {i}: ' + ('x' * 900), f'Past answer {i}: ' + ('y' * 900)) for i in range(6)])

        # Large search result (~18KB) plus ~11KB Step 0 history triggers compaction on Step 1 under 49152 budget
        self.search.snippet_size = 18000
        _, jid = self._submit(cid=cid, content='스펙 비교해 줘', level='default')
        step0 = self.claim()
        self.assertEqual(self.finish(step0, calls=[_call('k0', 'plan_web_search', {'needed': True, 'query': 'big spec'})], content='')['state'], 'queued')

        with self.assertLogs(self.app.logger, level='INFO') as step_logs:
            step1 = self.claim()
        self.assertIsNotNone(step1)
        self.assertTrue(any('assistant context compacted' in msg for msg in step_logs.output))
        payload_bytes = len(canonical([step1['messages'], step1['tools']]).encode())
        self.assertLessEqual(payload_bytes + step1['max_tokens'] + 512, 49152)
        projected_step0 = next(m['tool_calls'][0]['function'] for m in step1['messages'] if m.get('tool_calls'))
        self.assertEqual(projected_step0['name'], 'web_search')

        # Trigger search_decided recovery while compacted and verify no self-413 and accurate ledger
        self.finish(step1, calls=[_call('k1', 'plan_web_search', {'needed': False})], content='')
        step2 = self.claim()
        self.assertIsNotNone(step2)
        self.assertLessEqual(len(canonical([step2['messages'], step2['tools']]).encode()) + step2['max_tokens'] + 512, 49152)
        self.assertIn(CORRECTIONS['search_decided'], step2['messages'][0]['content'])
        self.assertEqual(self.finish(step2, content='압축된 맥락에서도 정상 완료되었습니다 [1].')['state'], 'done')

        raw_job = self._job(jid)
        raw_fn = next(m['tool_calls'][0]['function'] for m in json.loads(raw_job['context']) if m.get('tool_calls'))
        self.assertEqual(raw_fn['name'], 'plan_web_search')
        before_rebuild = self.store.storage_status(2, raw_job['account_key'])
        self.assertEqual(before_rebuild['reserved_chars'], 0)
        with self.store.db(True) as db:
            db.execute('DELETE FROM storage_accounts')
            rebuilt = self.store._account(db, 2, raw_job['account_key'])
        self.assertEqual(before_rebuild['used_chars'], rebuilt)
        self.assertGreater(evidence_chars(raw_job['context']), 18000)

    def test_14_mid_turn_service_outage_recovery_and_repeat_unavailable(self):
        # Recovery then clean answer when search service goes down mid-turn
        self._submit()
        self.finish(self.claim(), calls=[_call('o0', 'plan_web_search', {'needed': True, 'query': 'initial public'})], content='')
        self.search.available = False

        step1 = self.claim()
        self.assertIn('현재 웹 검색 서비스를 추가로 사용할 수 없습니다. 추가 검색을 요청하지 말고 이미 수행한 검색 출처로 답하고', step1['messages'][0]['content'])
        self.assertNotIn('web_search', {t['function']['name'] for t in step1['tools']})
        res_rec = self.finish(step1, calls=[_call('o1', 'web_search', {'query': 'followup outage'})], content='')
        self.assertEqual(res_rec['state'], 'queued')
        self.assertEqual(res_rec['response_correction'], 'search_decided')
        self.assertEqual(self.finish(self.claim(), content='기존 출처 기준으로 답변합니다 [1].')['state'], 'done')

        # Repeat search call during outage fails with WEB_SEARCH_UNAVAILABLE (for both web_search & plan_web_search)
        for bad_call in (
            _call('o3', 'web_search', {'query': 'repeat outage'}),
            _call('o4', 'plan_web_search', {'needed': True, 'query': 'repeat outage'}),
        ):
            self.search.available = True
            self._submit()
            self.finish(self.claim(), calls=[_call('ox0', 'plan_web_search', {'needed': True, 'query': 'first ok'})], content='')
            self.search.available = False
            self.assertEqual(self.finish(self.claim(), calls=[bad_call], content='')['response_correction'], 'search_decided')
            res_fail = self.finish(self.claim(), calls=[_call('ox2', 'web_search', {'query': 'still unavailable'})], content='')
            self.assertEqual(res_fail['state'], 'failed')
            self.assertEqual(res_fail['error_code'], 'WEB_SEARCH_UNAVAILABLE')

    def test_15_answer_correction_prompt_and_tool_guard(self):
        self._submit()
        self.finish(self.claim(), calls=[_call('n0', 'plan_web_search', {'needed': True, 'query': 'ddr4 qvl'})], content='')
        res_empty = self.finish(self.claim(), calls=[], content='', reasoning='Thinking only.')
        self.assertEqual(res_empty['state'], 'queued')
        self.assertEqual(res_empty['response_correction'], 'answer')

        step2 = self.claim()
        self.assertEqual(step2['tools'], [])
        sys_prompt = step2['messages'][0]['content']
        self.assertIn(CORRECTIONS['answer'], sys_prompt)
        self.assertNotIn(PLANNING_INSTRUCTIONS, sys_prompt)
        self.assertNotIn('현재 요청 웹 검색:', sys_prompt)
        self.assertNotIn('남은 웹 검색 횟수:', sys_prompt)

        res_tool = self.finish(step2, calls=[_call('n1', 'search_equipment', {'query': 'My'})], content='')
        self.assertEqual(res_tool['state'], 'failed')
        self.assertEqual(res_tool['error_code'], 'INVALID_TOOL_CALL')

    def test_16_step_limit_and_cancel_trash_logout_races(self):
        # MAX_SEARCHES + 4 steps (0..8 for MAX_SEARCHES=5) hits STEP_LIMIT cleanly
        _, jid_s = self._submit()
        self.assertEqual(self.finish(self.claim(), calls=[], content='')['response_correction'], 'search_plan')  # step 0
        self.assertEqual(self.finish(self.claim(), calls=[_call('s1', 'plan_web_search', {'needed': True, 'query': 'q1'})], content='')['state'], 'queued')  # step 1
        self.assertEqual(self.finish(self.claim(), calls=[_call('s2', 'plan_web_search', {'needed': False})], content='')['response_correction'], 'search_decided')  # step 2
        for idx in range(2, MAX_SEARCHES + 1):
            self.assertEqual(self.finish(self.claim(), calls=[_call(f's{idx + 1}', 'web_search', {'query': f'q{idx}'})], content='')['state'], 'queued')
        self.assertEqual(self.finish(self.claim(), calls=[_call('seq', 'search_equipment', {'query': 'My'})], content='')['state'], 'queued')  # penultimate step
        res_limit = self.finish(self.claim(), calls=[_call('slim', 'get_equipment', {'equipment_id': 2})], content='')  # final step -> STEP_LIMIT
        self.assertEqual(res_limit['state'], 'failed')
        self.assertEqual(self._job(jid_s)['error_code'], 'STEP_LIMIT')
        self.assertEqual(self._job_status(jid_s)['error_code'], 'STEP_LIMIT')
        self.assertEqual(len(self.search.calls), MAX_SEARCHES)

        # Cancel race before follow-up finish
        _, jid_c = self._submit()
        self.finish(self.claim(), calls=[_call('c0', 'plan_web_search', {'needed': True, 'query': 'cancel q'})], content='')
        step_c = self.claim()
        self.assertEqual(self.client.post('/api/ai/jobs/' + jid_c + '/cancel', json={}, headers=self.headers).status_code, 200)
        res_c = self.finish(step_c, calls=[_call('c1', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res_c['state'], 'cancelled')
        self.assertEqual(len(public_searches(self._job(jid_c)['context'])), 1)

        # Trash race before follow-up finish
        self.search.calls.clear()
        cid_t, jid_t = self._submit()
        self.finish(self.claim(), calls=[_call('t0', 'plan_web_search', {'needed': True, 'query': 'trash q'})], content='')
        step_t = self.claim()
        before_trash = len(self.search.calls)
        conv = self.client.get('/api/ai/conversations', headers=self.headers).get_json()['conversations']
        rev = next(c['lifecycle_revision'] for c in conv if c['id'] == cid_t)
        self.assertEqual(self.client.post(f'/api/ai/conversations/{cid_t}/trash', json={'lifecycle_revision': rev, 'operation_id': uuid.uuid4().hex}, headers=self.headers).status_code, 200)
        res_t = self.finish(step_t, calls=[_call('t1', 'plan_web_search', {'needed': True, 'query': 'late'})], content='')
        self.assertIn(res_t['state'], ('failed', 'cancelled'))
        self.assertEqual(len(self.search.calls), before_trash)
        with self.store.db() as db:
            row = db.execute('SELECT is_deleted FROM conversations WHERE id=?', (cid_t,)).fetchone()
            self.assertEqual(row['is_deleted'], 1)

        # Logout race before follow-up finish
        self.search.calls.clear()
        _, jid_l = self._submit()
        self.finish(self.claim(), calls=[_call('l0', 'plan_web_search', {'needed': True, 'query': 'logout q'})], content='')
        step_l = self.claim()
        self.assertEqual(self.client.post('/logout').status_code, 302)
        res_l = self.finish(step_l, calls=[_call('l1', 'plan_web_search', {'needed': True, 'query': 'after logout'})], content='')
        self.assertEqual(res_l['state'], 'cancelled')
        self.assertEqual(self._job(jid_l)['error_code'], 'AUTH_EXPIRED')
        self.assertEqual(len(self.search.calls), 1)

    def test_17_32k_tool_budget_fits_step0_and_search_decided(self):
        _, mid = self._setup_model_with_context(32768)
        cid = self.conversation()
        self.assertEqual(self.choose(cid, mid, level='default').status_code, 200)
        _, jid = self._submit(cid=cid, content='이 서버 스펙을 웹에서 검색해 줘', level='default')

        step0 = self.claim()
        self.assertIsNotNone(step0, '32K model must admit Step 0 even with search_decided worst_overhead')
        self.assertEqual(self.finish(step0, calls=[_call('w0', 'plan_web_search', {'needed': True, 'query': 'server board spec'})], content='')['state'], 'queued')

        step1 = self.claim()
        self.assertIsNotNone(step1)
        res1 = self.finish(step1, calls=[_call('w1', 'plan_web_search', {'needed': False})], content='')
        self.assertEqual(res1['state'], 'queued')
        self.assertEqual(res1['response_correction'], 'search_decided')

        step2 = self.claim()
        self.assertIsNotNone(step2)
        self.assertLessEqual(len(canonical([step2['messages'], step2['tools']]).encode()) + step2['max_tokens'] + 512, 32768)
        self.assertEqual(self.finish(step2, content='32K 모델에서도 보정 후 정상 완료했습니다 [1].')['state'], 'done')
        self.assertEqual(self._job(jid)['state'], 'done')
