"""[MINI-COMMENT: ASSISTANT.CONTEXT.BUDGET.TESTS]
[EN rev.1]
[Role] Exercises context budget reservation, multi-step compaction, persisted cap recovery and CONTEXT_LIMIT error handling on isolated Linux fixtures.
[Dependencies] Established AssistantTests and ProviderTests fixtures with inert local transports; no production DB or network access.
[Impact] Verifies 65K/32K tool budgets, answer-correction headroom, invariant handoff/evidence ledgers, taint/correction preservation and queued cancel metadata.
"""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

if 'assistant_fixture_tests' not in sys.modules:
    _tests_dir = str(Path(__file__).resolve().parent)
    if _tests_dir not in sys.path:
        sys.path.insert(0, _tests_dir)
    sys.modules['assistant_fixture_tests'] = importlib.import_module('test_equipment_ai')

if 'assistant_provider_fixture_tests' not in sys.modules:
    _tests_dir = str(Path(__file__).resolve().parent)
    if _tests_dir not in sys.path:
        sys.path.insert(0, _tests_dir)
    sys.modules['assistant_provider_fixture_tests'] = importlib.import_module('test_multi_provider_ai')

import assistant_fixture_tests as _fixture
import assistant_provider_fixture_tests as _provider_fixture
from utils.ai_assistant import admin_logs
from utils.ai_assistant.context import (
    HANDOFF_PREFIX,
    MAX_PERSISTED_CONTEXT,
    OMISSION_NOTICE,
    _split_turn_context,
    compact_persisted_context,
    compact_step_context,
)
from utils.ai_assistant.policy import ERROR_REASONS, canonical
from utils.ai_assistant.providers import LEGACY_MODEL
from utils.ai_assistant.recovery import CORRECTIONS
from utils.ai_assistant.web_search import (
    WebSearchError,
    evidence_chars,
    project_results,
    public_searches,
    validate_query,
)


class _ConfigurableFakeSearch:
    """[Role] Preserves real public-query privacy guards while returning deterministic bounded Yahoo results."""
    available = True

    def __init__(self):
        """[Role] Tracks outbound queries and allows each test to size synthetic Yahoo search payloads."""
        self.calls = []
        self.raw_results = None

    def search(self, query, max_results=5, sensitive=(), provider='auto', scope=None):
        """[Role] Enforces validate_query before returning synthetic Yahoo evidence."""
        query = validate_query(query, sensitive)
        self.calls.append((query, provider, scope))
        raw = self.raw_results
        if raw is None:
            raw = [
                {
                    'title': f'Workstation Reference {i} - Xeon E5 Dual Socket Guide',
                    'url': f'https://docs.example.org/workstations/model-{i}',
                    'snippet': ('Official dual-socket LGA2011-3 server and workstation compatibility guide '
                                'supporting Xeon E5-2699 v4 processors, ECC DDR4 RDIMM, PCIe lanes. ') * 3,
                }
                for i in range(5)
            ]
        return {
            'kind': 'web_search',
            'version': 1,
            'status': 'ok',
            'query': query,
            'engine': 'Yahoo' if provider in ('auto', 'yahoo') else 'GitHub',
            'scope': scope or ('repositories' if provider == 'github' else 'web'),
            'searched_at': '2026-11-23T07:00:00+00:00',
            'results': project_results(raw)[:max_results],
            'notice': '공개 검색 결과의 제목/요약입니다. [번호]로 근거를 인용하세요.',
        }


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class ContextBudgetAndCompactionTests(unittest.TestCase):
    """[Role] Exercises end-to-end Flask/Store/Context behavior across all context budget and compaction scenarios."""
    connect = _fixture.AssistantTests.connect
    login = _fixture.AssistantTests.login
    conversation = _fixture.AssistantTests.conversation
    claim = _fixture.AssistantTests.claim
    finish = _fixture.AssistantTests.finish
    registry = _provider_fixture.ProviderTests.registry
    add_model = _provider_fixture.ProviderTests.add_model
    choose = _provider_fixture.ProviderTests.choose
    run_one = _provider_fixture.ProviderTests.run_one

    def setUp(self):
        """[Role] Initializes an isolated fixture with configurable inert search transport."""
        _fixture.AssistantTests.setUp(self)
        self.search = _ConfigurableFakeSearch()
        self.domain.search_service = self.search

    def submit(self, cid=None, content='Help', level='medium', key=None, web_search=None):
        """[Role] Submits a browser turn using the real turns route."""
        cid = cid or self.conversation()
        payload = {'content': content, 'reasoning_version': 2, 'level': level, 'client_key': key or uuid.uuid4().hex}
        if web_search is not None:
            payload['web_search'] = web_search
        result = self.client.post('/api/ai/conversations/' + cid + '/turns', json=payload, headers=self.headers)
        self.assertEqual(result.status_code, 202, result.get_json())
        return result.get_json()['job_id']

    def seed_history(self, cid, turn_count, target_bytes_each, prefix='이전 질문', ascii_fill=False):
        """[Role] Seeds real completed turns directly in the synthetic AI store to model long conversations."""
        now = 1700000000.0
        ko_unit = '장비 사양 및 호환성 비교 문의 '
        en_unit = 'Xeon E5-2699 v4 dual-socket workstation analysis summary. '
        ko_unit_bytes = len(ko_unit.encode())
        en_unit_bytes = len(en_unit.encode())
        with self.store.db(True) as db:
            account = db.execute('SELECT account_key FROM conversations WHERE id=?', (cid,)).fetchone()[0]
            route = canonical({'provider_id': 'seed', 'model_label': 'seed', 'revision': 1})
            for idx in range(turn_count):
                jid = uuid.uuid4().hex
                if ascii_fill:
                    q = f'{prefix}-{idx}: ' + ('Q' * max(1, target_bytes_each))
                    a = f'Answer-{idx}: ' + ('A' * max(1, target_bytes_each))
                else:
                    q = f'{prefix}-{idx}: ' + (ko_unit * max(1, (target_bytes_each + ko_unit_bytes - 1) // ko_unit_bytes))
                    a = f'이전 답변-{idx}: ' + (en_unit * max(1, (target_bytes_each + en_unit_bytes - 1) // en_unit_bytes))
                db.execute(
                    """INSERT INTO jobs(id,conversation,owner,client_key,input_hash,binding,expires,level,state,queue_order,
                    purpose,route_snapshot,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (jid, cid, 2, uuid.uuid4().hex, uuid.uuid4().hex, 'seed-binding', now + 999999999,
                     'medium', 'done', idx + 1, 'chat', route, now + idx, now + idx),
                )
                db.execute("INSERT INTO messages(conversation,job,role,content,created) VALUES(?,?,'user',?,?)", (cid, jid, q, now + idx))
                db.execute("INSERT INTO messages(conversation,job,role,content,created) VALUES(?,?,'assistant',?,?)", (cid, jid, a, now + idx))
                db.execute('UPDATE storage_accounts SET used_chars=used_chars+? WHERE owner=2 AND account_key=?', (len(q) + len(a), account))

    def test_1_65k_tool_auto_search_with_42kb_history_completes_all_14_tools(self):
        """[Role] Reproduces the 65,536-token tool + auto search + ~42KB mixed history flow through Step 0 and Step 1."""
        cid = self.conversation()
        self.seed_history(cid, turn_count=10, target_bytes_each=2200)
        with self.store.db() as db:
            history_bytes = sum(len(r[0].encode()) for r in db.execute('SELECT content FROM messages WHERE conversation=?', (cid,)))
        self.assertGreaterEqual(history_bytes, 40000)

        jid = self.submit(cid, content='Xeon E5-2699 v4 듀얼 소켓 워크스테이션을 웹검색으로 찾아 비교해 주세요.', web_search=None)
        step0 = self.claim()
        self.assertIsNotNone(step0)
        self.assertEqual(step0['id'], jid)
        self.assertEqual(step0['required_tool'], 'plan_web_search')
        self.assertEqual([t['function']['name'] for t in step0['tools']], ['plan_web_search'])

        # 약 3KB 크기의 Yahoo 검색 결과를 반환하도록 구성한다.
        self.search.raw_results = [
            {
                'title': f'Workstation Spec {i} - Dual Xeon E5-2699 v4',
                'url': f'https://docs.example.org/workstations/xeon-{i}',
                'snippet': 'Dual LGA2011-3 C612 chipset workstation supporting two E5-2699 v4 CPUs and DDR4 ECC. ' * 5,
            }
            for i in range(5)
        ]
        plan_res = self.finish(
            step0,
            [{'id': 'plan1', 'name': 'plan_web_search',
              'arguments': canonical({'needed': True, 'query': 'Xeon E5-2699 v4 dual socket workstation', 'provider': 'yahoo'})}],
        )
        self.assertEqual(plan_res['state'], 'queued')

        step1 = self.claim()
        self.assertIsNotNone(step1)
        self.assertEqual(step1['id'], jid)
        self.assertEqual(len(step1['tools']), 14)
        self.assertIn('web_search', [t['function']['name'] for t in step1['tools']])
        payload_bytes = len(canonical([step1['messages'], step1['tools']]).encode())
        self.assertLessEqual(payload_bytes + step1['max_tokens'] + 512, 65536)

        done_res = self.finish(step1, content='웹 검색 근거를 바탕으로 워크스테이션 모델을 비교 정리했습니다. [1]')
        self.assertEqual(done_res['state'], 'done')
        with self.store.db() as db:
            row = self.store.job(jid, db)
            self.assertEqual(row['state'], 'done')
            self.assertIsNone(row['error_code'])
            self.assertEqual(len(public_searches(row['context'])), 1)

    def test_2_32k_tool_model_and_candidate_probe_accept_while_4096_probe_rejects(self):
        """[Role] Verifies 32,768-token tool probes and normal chat succeed while 4,096-token candidate probes fail PROVIDER_CONTEXT."""
        pid, mid, key = self.add_model(verified=False, tools=True)
        self.login(1)
        probe_res = self.client.post(
            '/api/admin/ai/models/' + mid + '/probe',
            json={'provider_id': pid, 'candidate_revision': 1, 'context_tokens': 32768,
                  'tools': True, 'reasoning': False, 'client_key': uuid.uuid4().hex},
            headers=self.headers,
        )
        self.assertEqual(probe_res.status_code, 202, probe_res.get_json())
        probe_jid = probe_res.get_json()['job_id']
        for _ in range(2):
            job = self.claim()
            self.assertIsNotNone(job)
            self.assertEqual(job['id'], probe_jid)
            self.run_one(job)
        pub_res = self.client.post(
            '/api/admin/ai/providers/' + pid + '/models',
            json={'id': mid, 'label': '32K Tool Model', 'published': True, 'sort_order': 0,
                  'context_tokens': 32768, 'revision': 1},
            headers=self.headers,
        )
        self.assertEqual(pub_res.status_code, 200, pub_res.get_json())

        # 기존 32K 도구 모델의 후보 리비전 전환 시험(test_provider_ca.py:547 불변량)이 통과해야 한다.
        save_res = self.client.post(
            '/api/admin/ai/providers/' + pid,
            json={'name': 'Updated 32K', 'base_url': self.registry.resolve(mid)['base_url'],
                  'adapter': 'openai', 'enabled': True, 'manual': True, 'revision': 1,
                  'api_key': key, 'resource_group': self.registry.resolve(mid)['resource_group'],
                  'trust_mode': 'private', 'ca_pem': self.registry.connection(pid, 1)[0]['ca_pem']},
            headers=self.headers,
        )
        self.assertEqual(save_res.status_code, 200, save_res.get_json())
        disc_res = self.client.post('/api/admin/ai/providers/' + pid + '/discover',
                                    json={'candidate_revision': 2}, headers=self.headers)
        self.assertEqual(disc_res.status_code, 200, disc_res.get_json())
        cutover_probe = self.client.post(
            '/api/admin/ai/models/' + mid + '/probe',
            json={'provider_id': pid, 'candidate_revision': 2, 'tools': True, 'reasoning': False,
                  'client_key': uuid.uuid4().hex},
            headers=self.headers,
        )
        self.assertEqual(cutover_probe.status_code, 202, cutover_probe.get_json())
        for _ in range(2):
            job = self.claim()
            self.assertIsNotNone(job)
            self.run_one(job)

        # 32K 도구 모델의 일반 대화도 Step 0과 Step 1을 정상 통과한다.
        self.login(2)
        cid = self.conversation()
        self.assertEqual(self.choose(cid, mid, level='default').status_code, 200)
        chat_jid = self.submit(cid, content='내 장비 목록 요약해 주세요.', level='default', web_search=None)
        step0 = self.claim()
        self.assertIsNotNone(step0)
        self.assertEqual(self.finish(step0, [{'id': 'p0', 'name': 'plan_web_search', 'arguments': '{"needed":false}'}])['state'], 'queued')
        step1 = self.claim()
        self.assertIsNotNone(step1)
        self.assertEqual(self.finish(step1, content='장비 목록 요약 완료')['state'], 'done')
        with self.store.db() as db:
            self.assertEqual(self.store.job(chat_jid, db)['state'], 'done')

        # 4,096 token 후보 프로브는 여전히 PROVIDER_CONTEXT로 거절되어야 한다.
        pid_small, mid_small, _ = self.add_model(verified=False, tools=False)
        self.login(1)
        small_probe = self.client.post(
            '/api/admin/ai/models/' + mid_small + '/probe',
            json={'provider_id': pid_small, 'candidate_revision': 1, 'context_tokens': 4096,
                  'tools': False, 'reasoning': False, 'client_key': uuid.uuid4().hex},
            headers=self.headers,
        )
        self.assertEqual(small_probe.status_code, 202, small_probe.get_json())
        small_jid = small_probe.get_json()['job_id']
        self.assertIsNone(self.claim())
        with self.store.db() as db:
            self.assertEqual(self.store.job(small_jid, db)['error_code'], 'PROVIDER_CONTEXT')

    def test_3_chat_only_reserves_answer_correction_overhead_on_step0(self):
        """[Role] Ensures chat-only models reserve CORRECTIONS['answer'] headroom at Step 0 so Step 1 repair never self-fails 413."""
        _, mid, _ = self.add_model(verified=True, tools=False)
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET context_tokens=16384 WHERE id=?', (mid,))
        cid = self.conversation()
        self.assertEqual(self.choose(cid, mid, level='default').status_code, 200)
        self.seed_history(cid, turn_count=12, target_bytes_each=1500)

        jid = self.submit(cid, content='핵심 요약만 간단히 답해 주세요.', level='default')
        step0 = self.claim()
        self.assertIsNotNone(step0)
        self.assertEqual(step0['tools'], [])
        # 빈 응답으로 Step 1 답변 보정을 유발한다.
        repair_res = self.finish(step0, content='', reasoning='내부 검토만 수행')
        self.assertEqual((repair_res['state'], repair_res['response_correction']), ('queued', 'answer'))

        step1 = self.claim()
        self.assertIsNotNone(step1)
        self.assertEqual(step1['id'], jid)
        self.assertEqual(step1['tools'], [])
        self.assertIn(CORRECTIONS['answer'], step1['messages'][0]['content'])
        self.assertEqual(self.finish(step1, content='보정 단계에서 생성한 최종 답변입니다.')['state'], 'done')

    def test_4_multistep_compaction_preserves_sources_taint_corrections_ledgers_and_duplicate_question(self):
        """[Role] Verifies step>=1 compaction drops oldest history while keeping citations, taint, corrections, handoff_chars and duplicate current text."""
        cid = self.conversation()
        duplicate_q = '동일 질문: 장비 점검과 외부 문서를 비교해 주세요.'
        # 과거 이력에 현재 질문과 완전히 동일한 문장을 포함해 위치 기반 분할이 오작동하지 않는지 검증한다.
        self.seed_history(cid, turn_count=10, target_bytes_each=2600, prefix=duplicate_q)
        with self.store.db(True) as db:
            db.execute("UPDATE messages SET content=? WHERE id=(SELECT MAX(id) FROM messages WHERE conversation=? AND role='user')",
                       (duplicate_q, cid))

        jid = self.submit(cid, content=duplicate_q, web_search=None)
        step0 = self.claim()
        self.assertIsNotNone(step0)
        with self.store.db() as db:
            handoff_before = db.execute('SELECT handoff_chars FROM jobs WHERE id=?', (jid,)).fetchone()[0]
            used_before = self.store.storage_status(2, self.store.job(jid, db)['account_key'])['used_chars']
            account_key = self.store.job(jid, db)['account_key']
        self.assertGreater(handoff_before, 0)

        # Step 1에서 65K 예산을 확실히 넘기도록 ~24KB 규모의 검색 결과를 주입한다.
        self.search.raw_results = [
            {
                'title': '한글제목' + ('가' * 150) + f'-{i}',
                'url': f'https://docs.example.org/spec/{"x" * 1200}/{i}',
                'snippet': '상세스펙요약' + ('나' * 650),
            }
            for i in range(5)
        ]
        self.assertEqual(
            self.finish(step0, [{'id': 'p1', 'name': 'plan_web_search',
                                 'arguments': canonical({'needed': True, 'query': 'Xeon workstation guide', 'provider': 'yahoo'})}])['state'],
            'queued',
        )
        with self.store.db() as db:
            ctx_after_search = json.loads(self.store.job(jid, db)['context'])
            ev_chars = evidence_chars(ctx_after_search)
            ctx_bytes_after_search = len(canonical(ctx_after_search).encode())
        # project_results의 개별 필드 길이 상한을 고려해 1회 한국어 검색 결과가 9,000자 이상·Step 1 예산을 넘길 수준인지 확인한다.
        self.assertGreater(ev_chars, 9000)
        self.assertGreater(ctx_bytes_after_search + 18000 + 8192 + 512, 65536)

        # Step 1 claim에서 과거 이력을 축약해 예산 내에 맞춘다.
        step1 = self.claim()
        self.assertIsNotNone(step1)
        payload_bytes = len(canonical([step1['messages'], step1['tools']]).encode())
        self.assertLessEqual(payload_bytes + step1['max_tokens'] + 512, 65536)
        handoff_proj = json.loads(step1['messages'][1]['content'].split(HANDOFF_PREFIX, 1)[1])
        self.assertTrue(handoff_proj['context_incomplete'])
        self.assertIn(OMISSION_NOTICE, handoff_proj['notice'])
        # 현재 질문은 중복 이력이 제거되더라도 tool_calls 직전에 그대로 보존되어야 한다.
        tool_call_idx = next(i for i, m in enumerate(step1['messages']) if m.get('role') == 'assistant' and 'tool_calls' in m)
        self.assertEqual(step1['messages'][tool_call_idx - 1], {'role': 'user', 'content': duplicate_q})

        with self.store.db() as db:
            job_row = self.store.job(jid, db)
            self.assertEqual(job_row['handoff_chars'], handoff_before)
            self.assertEqual(len(public_searches(job_row['context'])), 1)
            # handoff_chars는 불변이고 step0 완료 시점에는 evidence_chars만 storage_accounts에 추가 반영된다.
            self.assertEqual(self.store.storage_status(2, account_key)['used_chars'], used_before + ev_chars)

        # get_equipment 결과를 추가한 뒤에도 taint 보호가 유지되어야 한다.
        self.assertEqual(
            self.finish(step1, [{'id': 'eq1', 'name': 'get_equipment', 'arguments': '{"equipment_id":2}'}])['state'],
            'queued',
        )
        step2 = self.claim()
        self.assertIsNotNone(step2)
        tainted_search = self.finish(
            step2,
            [{'id': 'ws2', 'name': 'web_search', 'arguments': canonical({'query': 'public workstation model'})}],
        )
        self.assertEqual((tainted_search['state'], tainted_search['error_code']), ('failed', 'WEB_SEARCH_BLOCKED'))

        # 보정 마커(CORRECTIONS)는 step>=1 축약 이후에도 jobs.context에 보존되어 1회 보정 제한이 유지되어야 한다.
        jid2 = self.submit(cid, content='검색 판단 누락 후 큰 검색 결과를 받는 질문', web_search=None)
        s0 = self.claim()
        self.assertEqual(self.finish(s0, content='', reasoning='검토')['response_correction'], 'search_plan')
        s1 = self.claim()
        self.assertIn(CORRECTIONS['search_plan'], s1['messages'][0]['content'])
        self.assertEqual(
            self.finish(s1, [{'id': 'p2', 'name': 'plan_web_search',
                              'arguments': canonical({'needed': True, 'query': 'Xeon workstation review'})}])['state'],
            'queued',
        )
        s2 = self.claim()
        self.assertIsNotNone(s2)
        # Step 2에서 빈 답변 보정 1회를 거친 뒤 다시 빈 응답이면 search_plan/answer 마커가 보존되어 EMPTY_RESPONSE로 종료된다.
        self.assertEqual(self.finish(s2, content='')['response_correction'], 'answer')
        s3 = self.claim()
        self.assertIsNotNone(s3)
        final_empty = self.finish(s3, content='')
        self.assertEqual((final_empty['state'], final_empty['error_code']), ('failed', 'EMPTY_RESPONSE'))
        with self.store.db() as db:
            saved_ctx = json.loads(self.store.job(jid2, db)['context'])
        self.assertTrue(any(m.get('role') == 'system' and m.get('content') == CORRECTIONS['search_plan'] for m in saved_ctx))
        self.assertTrue(any(m.get('role') == 'system' and m.get('content') == CORRECTIONS['answer'] for m in saved_ctx))

    def test_5_unrecoverable_overflow_records_context_limit_and_safe_metadata_logs(self):
        """[Role] Confirms unrecoverable Step 0 and Step 1+ overflows fail with CONTEXT_LIMIT, released guards and zero prompt/secret leaks."""
        # ERROR_REASONS['CONTEXT_LIMIT']는 admin_logs._PRIVATE_TEXT에 걸리지 않아야 한다.
        self.assertIsNone(admin_logs._PRIVATE_TEXT.search(ERROR_REASONS['CONTEXT_LIMIT']))
        self.assertEqual(admin_logs.display_text(ERROR_REASONS['CONTEXT_LIMIT'], 512, ()), ERROR_REASONS['CONTEXT_LIMIT'])

        # Case 5a: Step 0 복구 불가 초과
        _, mid_small, _ = self.add_model(verified=True, tools=False)
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET context_tokens=2048 WHERE id=?', (mid_small,))
        cid = self.conversation()
        self.assertEqual(self.choose(cid, mid_small, level='default').status_code, 200)
        secret_user_text = 'TOP_SECRET_USER_PROMPT_TEXT_12345 ' * 60
        jid0 = self.submit(cid, content=secret_user_text, level='default')
        with self.assertLogs(self.app.logger, level='WARNING') as logs0:
            self.assertIsNone(self.claim())
        self.assertTrue(any('code=CONTEXT_LIMIT' in line and 'status=413' in line and 'context_tokens=2048' in line for line in logs0.output))
        for sensitive in ('TOP_SECRET_USER_PROMPT_TEXT_12345', self.app.config['USER_AI_WORKER_TOKEN']):
            self.assertFalse(any(sensitive in line for line in logs0.output))
        with self.store.db() as db:
            row0 = self.store.job(jid0, db)
            self.assertEqual((row0['state'], row0['error_code'], row0['error'], row0['reserved_chars']),
                             ('failed', 'CONTEXT_LIMIT',
                              '이 모델의 검증된 컨텍스트에 현재 질문이 들어가지 않습니다. 질문을 줄이거나 더 큰 모델을 선택해 주세요.', 0))
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid0,)).fetchone()[0], 'released')

        # Case 5b: Step 1+ 복구 불가 초과 (이력/인계를 다 비워도 tail 자체가 모델 한도를 초과하는 경우)
        _, mid_32k, _ = self.add_model(verified=True, tools=True)
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET context_tokens=32768 WHERE id=?', (mid_32k,))
        cid2 = self.conversation()
        self.assertEqual(self.choose(cid2, mid_32k, level='default').status_code, 200)
        self.search.raw_results = [
            {
                'title': '한글제목' + ('가' * 150) + f'-{i}',
                'url': f'https://docs.example.org/overflow/{"y" * 1200}/{i}',
                'snippet': '초과스니펫' + ('나' * 650),
            }
            for i in range(5)
        ]
        jid1 = self.submit(cid2, content='32K 모델에서 큰 도구 결과를 반복 호출', level='default', web_search=None)
        s0 = self.claim()
        self.assertEqual(
            self.finish(s0, [{'id': 'p1', 'name': 'plan_web_search',
                              'arguments': canonical({'needed': True, 'query': 'Xeon workstation large'})}])['state'],
            'queued',
        )
        # ~24KB 도구 결과가 더해지면 32K 모델(system+14tools+8192)에서 Step 1이 복구 불가능한 초과가 된다.
        with self.assertLogs(self.app.logger, level='WARNING') as logs1:
            self.assertIsNone(self.claim())
        self.assertTrue(any('code=CONTEXT_LIMIT' in line and 'status=413' in line and 'context_tokens=32768' in line for line in logs1.output))
        self.assertFalse(any('초과스니펫' in line or self.app.config['USER_AI_WORKER_TOKEN'] in line for line in logs1.output))
        with self.store.db() as db:
            row1 = self.store.job(jid1, db)
            self.assertEqual((row1['state'], row1['error_code'], row1['error'], row1['reserved_chars']),
                             ('failed', 'CONTEXT_LIMIT', ERROR_REASONS['CONTEXT_LIMIT'], 0))
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid1,)).fetchone()[0], 'released')

    def test_6_finish_persisted_cap_compacts_history_first_and_fails_with_context_limit_when_unrecoverable(self):
        """[Role] Verifies finish() compacts old history before checking 120,000 chars and sets CONTEXT_LIMIT when unrecoverable."""
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET context_tokens=262144 WHERE id=?', (LEGACY_MODEL,))
        cid = self.conversation()
        # 약 100KB의 과거 이력을 채운 뒤 Step 0이 build_context 상한(<=117,952B) 안에서 context를 구성하도록 한다.
        self.seed_history(cid, turn_count=20, target_bytes_each=2500, ascii_fill=True)
        jid = self.submit(cid, content='긴 대화에서 도구 실행 후 최종 답변 저장 테스트', web_search=False)
        step0 = self.claim()
        self.assertIsNotNone(step0)
        with self.store.db() as db:
            before_ctx = json.loads(self.store.job(jid, db)['context'])
        self.assertLessEqual(len(canonical(before_ctx)), MAX_PERSISTED_CONTEXT)
        self.assertGreater(len(canonical(before_ctx)), 85000)

        # Step 0에서 대량 도구 결과(prepared 분기)로 120,000자를 넘겼다가 과거 이력 축약으로 queued 전환 후 Step 1 대용량 최종 답변도 성공시킨다.
        big_tool_result = {'equipment': {'name': 'R' * 14000}}
        with patch.object(self.domain, 'read_or_prepare', return_value=big_tool_result):
            prep_res = self.finish(
                step0,
                [{'id': f'eq{i}', 'name': 'search_equipment', 'arguments': '{}'} for i in range(4)],
            )
        self.assertEqual(prep_res['state'], 'queued')
        step1 = self.claim()
        self.assertIsNotNone(step1)
        big_answer = '최종 요약 ' + ('A' * 55000)
        self.assertEqual(self.finish(step1, content=big_answer)['state'], 'done')
        with self.store.db() as db:
            done_ctx = json.loads(self.store.job(jid, db)['context'])
        self.assertLessEqual(len(canonical(done_ctx)), MAX_PERSISTED_CONTEXT)
        self.assertEqual(done_ctx[-1]['content'], big_answer)
        self.assertTrue(done_ctx[0]['content'].startswith(HANDOFF_PREFIX))

        # 복구 불가 케이스: 과거 이력이 비어 있어도 tail + 최종 답변이 120,000자를 넘으면 CONTEXT_LIMIT으로 실패한다.
        cid2 = self.conversation()
        jid2 = self.submit(cid2, content='질문 ' + ('Q' * 7900), web_search=None)
        s0 = self.claim()
        self.assertIsNotNone(s0)
        self.search.raw_results = [
            {
                'title': 'Title' + ('T' * 160) + f'-{i}',
                'url': f'https://docs.example.org/huge/{"z" * 1300}/{i}',
                'snippet': 'Snippet' + ('S' * 680),
            }
            for i in range(5)
        ]
        self.assertEqual(
            self.finish(s0, [{'id': 'p0', 'name': 'plan_web_search',
                              'arguments': canonical({'needed': True, 'query': 'huge search one'})}])['state'],
            'queued',
        )
        s1 = self.claim()
        self.assertEqual(
            self.finish(s1, [{'id': 'ws1', 'name': 'web_search',
                              'arguments': canonical({'query': 'huge search two'})}])['state'],
            'queued',
        )
        s2 = self.claim()
        self.assertIsNotNone(s2)
        with self.store.db() as db:
            ctx_len = len(self.store.job(jid2, db)['context'])
        # tail(검색 2건 ~30KB) + handoff + 질문(8KB) + 인위적 대용량 assistant 응답(64KB)이 120KB를 넘도록
        # 보정 단계 또는 직접 64KB 최종 응답에 추가 대형 tool 결과로 120,000자 초과를 재현한다.
        if ctx_len + 64000 <= MAX_PERSISTED_CONTEXT:
            # 16KB 미만의 여러 read 도구 결과를 추가해 history 없이 120,000자를 넘긴다.
            huge_tool_result = {'equipment': {'name': 'X' * 15000}}
            with patch.object(self.domain, 'read_or_prepare', return_value=huge_tool_result):
                self.assertEqual(
                    self.finish(s2, [{'id': f'r{i}', 'name': 'search_equipment', 'arguments': '{}'} for i in range(4)])['state'],
                    'queued',
                )
            s3 = self.claim()
            self.assertIsNotNone(s3)
        else:
            s3 = s2
        over_res = self.finish(s3, content='B' * 64000)
        self.assertEqual((over_res['state'], over_res['error_code']), ('failed', 'CONTEXT_LIMIT'))
        self.assertIn(ERROR_REASONS['CONTEXT_LIMIT'], over_res['message'])
        with self.store.db() as db:
            row2 = self.store.job(jid2, db)
            self.assertEqual((row2['state'], row2['error_code'], row2['reserved_chars']), ('failed', 'CONTEXT_LIMIT', 0))
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid2,)).fetchone()[0], 'released')

    def test_7_queued_cancel_records_user_cancelled_code_and_reason(self):
        """[Role] Verifies cancelling a queued job via HTTP sets error_code='USER_CANCELLED' and non-empty error."""
        jid = self.submit(content='대기 중 취소할 질문입니다.', web_search=False)
        cancel_res = self.client.post('/api/ai/jobs/' + jid + '/cancel', json={}, headers=self.headers)
        self.assertEqual(cancel_res.status_code, 200, cancel_res.get_json())
        self.assertEqual(cancel_res.get_json()['state'], 'cancelled')

        view = self.client.get('/api/ai/jobs/' + jid).get_json()
        self.assertEqual(view['state'], 'cancelled')
        self.assertEqual(view['error_code'], 'USER_CANCELLED')
        self.assertEqual(view['error'], ERROR_REASONS['USER_CANCELLED'])
        with self.store.db() as db:
            row = self.store.job(jid, db)
            self.assertEqual((row['state'], row['error_code'], row['error'], row['reserved_chars']),
                             ('cancelled', 'USER_CANCELLED', ERROR_REASONS['USER_CANCELLED'], 0))

        self.login(1)
        admin_job = self.client.get('/api/admin/ai/logs', query_string={'view': 'job', 'id': jid}).get_json()['job']
        self.assertEqual(admin_job['error_code'], 'USER_CANCELLED')
        self.assertEqual(admin_job['reason'], ERROR_REASONS['USER_CANCELLED'])


class ContextCompactionUnitTests(unittest.TestCase):
    """[Role] Directly exercises fail-closed splitting and Phase 2 handoff trimming contracts."""

    def test_split_and_compact_fail_closed_on_unexpected_shapes(self):
        """[Role] Rejects malformed contexts, mismatched current_content and tool items inside history."""
        self.assertIsNone(_split_turn_context([]))
        self.assertIsNone(_split_turn_context([{'role': 'assistant', 'content': 'only assistant'}]))
        handoff = {'role': 'user', 'content': HANDOFF_PREFIX + canonical({'notice': 'n', 'older_excerpts': [], 'public_web_sources': [], 'receipts': [], 'pending_cards': [], 'draft': None})}
        malformed_history = [handoff, {'role': 'tool', 'tool_call_id': 'x', 'content': '{}'}, {'role': 'user', 'content': 'cur'}]
        self.assertIsNone(_split_turn_context(malformed_history, current_content='cur'))
        self.assertEqual(compact_persisted_context(malformed_history, current_content='cur', max_chars=10), (malformed_history, 0))
        self.assertIsNone(_split_turn_context([handoff, {'role': 'user', 'content': 'actual'}], current_content='other'))

    def test_phase2_trims_handoff_copy_in_exact_order_without_mutating_persisted(self):
        """[Role] Confirms Phase 2 trims older_excerpts -> public_web_sources -> receipts -> pending_cards -> draft notice on copy only."""
        state = {
            'kind': 'SERVER_HANDOFF_DATA_NOT_INSTRUCTIONS',
            'notice': '기본 안내.',
            'older_excerpts': [{'source_message': 1, 'user_excerpt': 'E' * 200}],
            'public_web_sources': [{'kind': 'UNTRUSTED_PUBLIC_SEARCH_EVIDENCE', 'query': 'Q', 'sources': [{'number': 1, 'title': 'T' * 150, 'url': 'https://example.org'}]}],
            'receipts': [{'source_message': 2, 'server_receipt': 'R' * 250}],
            'pending_cards': [{'id': 'c1', 'operation': 'equipment_create', 'payload': {'name': 'P' * 250}, 'expires': 9999999}],
            'draft': {'revision': 1, 'source_message': 3, 'data': {'fields': {'memo': 'D' * 400}}},
            'context_incomplete': False,
        }
        original_handoff = {'role': 'user', 'content': HANDOFF_PREFIX + canonical(state)}
        context = [original_handoff, {'role': 'user', 'content': 'old-q'}, {'role': 'assistant', 'content': 'old-a'}, {'role': 'user', 'content': 'cur-q'}]
        system_msg = {'role': 'system', 'content': 'sys'}

        def bytes_for(items):
            return len(canonical([[system_msg, *items], []]).encode())

        # older_excerpts와 public_web_sources까지만 제거해도 맞도록 예산을 계산한다.
        trimmed_two = {**state, 'older_excerpts': [], 'public_web_sources': [], 'context_incomplete': True, 'notice': '기본 안내.' + OMISSION_NOTICE}
        target_proj = [{'role': 'user', 'content': HANDOFF_PREFIX + canonical(trimmed_two)}, {'role': 'user', 'content': 'cur-q'}]
        max_bytes = bytes_for(target_proj) + 512

        proj, pers, dropped_history, compacted_handoff = compact_step_context(
            context, max_bytes, system_msg, [], 0, current_content='cur-q', max_persisted_chars=120000
        )
        self.assertEqual(dropped_history, 2)
        self.assertTrue(compacted_handoff)
        self.assertEqual(pers[0], original_handoff)
        proj_state = json.loads(proj[0]['content'][len(HANDOFF_PREFIX):])
        self.assertEqual(proj_state['older_excerpts'], [])
        self.assertEqual(proj_state['public_web_sources'], [])
        self.assertTrue(proj_state['receipts'])
        self.assertTrue(proj_state['pending_cards'])
        self.assertIn('data', proj_state['draft'])
        self.assertTrue(proj_state['context_incomplete'])
        self.assertEqual(proj_state['notice'].count(OMISSION_NOTICE), 1)
        self.assertLessEqual(bytes_for(proj) + 512, max_bytes)

        # 극단적으로 작은 예산이면 receipts -> pending_cards -> draft notice 순서로 모두 축약한다.
        min_draft = {'revision': 1, 'source_message': 3, 'notice': '초안은 이 모델의 문맥 한도를 넘습니다. 원문을 재확인해야 합니다.'}
        fully_trimmed = {**trimmed_two, 'receipts': [], 'pending_cards': [], 'draft': min_draft}
        min_proj = [{'role': 'user', 'content': HANDOFF_PREFIX + canonical(fully_trimmed)}, {'role': 'user', 'content': 'cur-q'}]
        proj2, pers2, _, compacted2 = compact_step_context(
            context, bytes_for(min_proj) + 512, system_msg, [], 0, current_content='cur-q', max_persisted_chars=120000
        )
        self.assertTrue(compacted2)
        self.assertEqual(pers2[0], original_handoff)
        proj2_state = json.loads(proj2[0]['content'][len(HANDOFF_PREFIX):])
        self.assertEqual(proj2_state['receipts'], [])
        self.assertEqual(proj2_state['pending_cards'], [])
        self.assertEqual(proj2_state['draft'], min_draft)


if __name__ == '__main__':
    unittest.main(verbosity=2)
