"""[MINI-COMMENT: ASSISTANT.FAILED.HISTORY.TESTS]
[EN rev.1]
[Role] Exercises failed chat question continuity alongside excluded failed answers, cancelled turns and failed mail-translation sources.
[Dependencies] Established AssistantTests Linux fixtures and Store SQLite persistence; no production app import or model network calls.
[Impact] Verifies follow-up context continuity after failed chat turns without leaking partial output, cancelled inputs or mail sources.
"""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
import uuid

if 'assistant_fixture_tests' not in sys.modules:
    _tests_dir = str(Path(__file__).resolve().parent)
    if _tests_dir not in sys.path:
        sys.path.insert(0, _tests_dir)
    sys.modules['assistant_fixture_tests'] = importlib.import_module('test_equipment_ai')

import assistant_fixture_tests as _fixture
from utils.ai_assistant.context import build_context
from utils.ai_assistant.policy import canonical


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class FailedTurnHistoryTests(unittest.TestCase):
    """[Role] Reuses real browser/worker routes and Store SQLite to test build_context history selection."""
    connect = _fixture.AssistantTests.connect
    login = _fixture.AssistantTests.login
    conversation = _fixture.AssistantTests.conversation
    claim = _fixture.AssistantTests.claim
    finish = _fixture.AssistantTests.finish

    def setUp(self):
        """[Role] Initializes the isolated assistant fixture with search disabled so ordinary turns finish in one step."""
        _fixture.AssistantTests.setUp(self)
        self.domain.search_service.enabled = False

    def submit(self, cid=None, content='Help', level='medium', key=None, web_search=False):
        """[Role] Submits a browser turn using the real turns route with deterministic search consent."""
        cid = cid or self.conversation()
        payload = {'content': content, 'reasoning_version': 2, 'level': level, 'client_key': key or uuid.uuid4().hex}
        if web_search is not None:
            payload['web_search'] = web_search
        result = self.client.post('/api/ai/conversations/' + cid + '/turns', json=payload, headers=self.headers)
        self.assertEqual(result.status_code, 202, result.get_json())
        return result.get_json()['job_id']

    def cancel(self, jid):
        """[Role] Cancels an owner job through the real browser cancel endpoint."""
        result = self.client.post('/api/ai/jobs/' + jid + '/cancel', json={}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.get_json())
        return result.get_json()['state']

    def stored_context(self, jid):
        """[Role] Reads the persisted server context stored on a claimed job."""
        with self.store.db() as db:
            return json.loads(self.store.job(jid, db)['context'])

    def test_failed_chat_turn_question_appears_before_current_without_failed_assistant_output(self):
        """[Role] Covers failed chat question retention and failed assistant text exclusion across consecutive turns.
        [Dependencies] Real submit, claim, finish and SQLite messages/jobs rows. [Impact] Follow-up questions keep context while partial output stays out.
        """
        cid = self.conversation()
        failed_question = 'intel xeon e5 2699v4 를 2개 장착 가능한 워크스테이션을 찾아줘'
        failed_partial = '실패한 부분 응답: Xeon 워크스테이션 초안'
        followup_question = '장비관리시스템 내부가 아니고 웹검색을 통해서 알아봐줘'

        failed_jid = self.submit(cid, content=failed_question)
        self.finish(self.claim(), content=failed_partial, outcome='failed')
        with self.store.db() as db:
            job_row = self.store.job(failed_jid, db)
            assistant_row = db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'", (failed_jid,)).fetchone()
        self.assertEqual(job_row['state'], 'failed')
        self.assertEqual(assistant_row['content'], failed_partial)

        next_jid = self.submit(cid, content=followup_question)
        claimed = self.claim()
        self.assertEqual(claimed['id'], next_jid)
        self.assertEqual(claimed['messages'][0]['role'], 'system')
        self.assertEqual(claimed['messages'][1]['role'], 'user')
        self.assertEqual(claimed['messages'][2:], [
            {'role': 'user', 'content': failed_question},
            {'role': 'user', 'content': followup_question},
        ])
        self.assertNotIn(failed_partial, canonical(claimed['messages']))
        self.assertEqual(self.stored_context(next_jid)[1:], [
            {'role': 'user', 'content': failed_question},
            {'role': 'user', 'content': followup_question},
        ])

    def test_cancelled_turn_question_does_not_appear_in_next_turn(self):
        """[Role] Ensures queued-cancelled and draining-cancelled turns never enter subsequent model history.
        [Dependencies] Real cancel endpoint, worker finish boundary and build_context. [Impact] Cancelled inputs stay excluded.
        """
        cid = self.conversation()
        queued_cancelled_q = '대기 상태에서 취소할 질문'
        running_cancelled_q = '실행 중 취소할 질문'
        running_cancelled_a = '취소 직전 부분 응답'
        next_q = '취소 이후 새로운 일반 질문'

        queued_jid = self.submit(cid, content=queued_cancelled_q)
        self.assertEqual(self.cancel(queued_jid), 'cancelled')

        running_jid = self.submit(cid, content=running_cancelled_q)
        running_job = self.claim()
        self.assertEqual(self.cancel(running_jid), 'draining')
        self.finish(running_job, content=running_cancelled_a, outcome='cancelled')

        with self.store.db() as db:
            self.assertEqual(self.store.job(queued_jid, db)['state'], 'cancelled')
            self.assertEqual(self.store.job(running_jid, db)['state'], 'cancelled')

        next_jid = self.submit(cid, content=next_q)
        claimed = self.claim()
        self.assertEqual(claimed['messages'][2:], [{'role': 'user', 'content': next_q}])
        serialized = canonical(claimed['messages']) + canonical(self.stored_context(next_jid))
        for forbidden in (queued_cancelled_q, running_cancelled_q, running_cancelled_a):
            self.assertNotIn(forbidden, serialized)

    def test_failed_mail_translation_source_does_not_appear_in_ordinary_chat_turn(self):
        """[Role] Confirms failed mail-translation turns never leak source emails or failed translations into chat history.
        [Dependencies] Real explicit_mail routing, route_snapshot mail_translation flag and build_context. [Impact] Mail sources stay isolated.
        """
        cid = self.conversation()
        mail_source_1 = 'Subject: Inspection of LT-31\n\nHi Jae,\n\nPlease inspect LT-31.'
        mail_request_1 = '다음 이메일을 한국어로 번역해 주세요.\n\n' + mail_source_1
        mail_partial_1 = '제목: 실패한 번역 초안'
        mail_source_2 = 'Subject: Delivery of PX-99\n\nHi Lee,\n\nPlease hold PX-99.'
        mail_request_2 = '다음 이메일을 한국어로 번역해 주세요.\n\n' + mail_source_2
        mail_partial_2 = '제목: 본문 없는 실패 번역'
        chat_q = '일반 장비 상태를 알려줘'

        mail_jid_1 = self.submit(cid, content=mail_request_1, web_search=None)
        mail_job_1 = self.claim()
        self.assertIn('mail_translation', mail_job_1['route'])
        self.finish(mail_job_1, content=mail_partial_1, outcome='failed')

        mail_jid_2 = self.submit(cid, content=mail_request_2, web_search=None)
        mail_job_2 = self.claim()
        self.assertIn('mail_translation', mail_job_2['route'])
        reply = self.client.post('/internal/ai/jobs/' + mail_jid_2 + '/finish', json={
            'lease': mail_job_2['lease'], 'outcome': 'complete', 'content': mail_partial_2,
            'calls': [], 'termination': {'done': True, 'finish_reason': 'stop'},
        }, headers=self.worker_headers)
        self.assertEqual(reply.status_code, 200, reply.get_json())
        self.assertEqual(reply.get_json()['state'], 'failed')

        with self.store.db() as db:
            self.assertEqual(self.store.job(mail_jid_1, db)['state'], 'failed')
            self.assertEqual(self.store.job(mail_jid_2, db)['state'], 'failed')

        chat_jid = self.submit(cid, content=chat_q)
        claimed = self.claim()
        self.assertEqual(claimed['messages'][2:], [{'role': 'user', 'content': chat_q}])
        serialized = canonical(claimed['messages']) + canonical(self.stored_context(chat_jid))
        for forbidden in ('LT-31', 'PX-99', '다음 이메일을 한국어로 번역해 주세요', mail_partial_1, mail_partial_2):
            self.assertNotIn(forbidden, serialized)

    def test_done_turn_still_includes_both_user_and_assistant_in_chronological_order(self):
        """[Role] Verifies completed turns retain both user and assistant messages alongside an intervening failed chat question.
        [Dependencies] Real multi-turn submit/claim/finish flow. [Impact] Existing done-turn history contract remains intact.
        """
        cid = self.conversation()
        q1, a1 = '첫 번째 완료 질문', '첫 번째 완료 답변'
        q2, a2 = '두 번째 실패 질문', '두 번째 실패 부분 응답'
        q3, a3 = '세 번째 완료 질문', '세 번째 완료 답변'
        q4 = '네 번째 현재 질문'

        self.submit(cid, content=q1)
        self.finish(self.claim(), content=a1, outcome='complete')

        self.submit(cid, content=q2)
        self.finish(self.claim(), content=a2, outcome='failed')

        self.submit(cid, content=q3)
        self.finish(self.claim(), content=a3, outcome='complete')

        self.submit(cid, content=q4)
        claimed = self.claim()
        self.assertEqual(claimed['messages'][2:], [
            {'role': 'user', 'content': q1},
            {'role': 'assistant', 'content': a1},
            {'role': 'user', 'content': q2},
            {'role': 'user', 'content': q3},
            {'role': 'assistant', 'content': a3},
            {'role': 'user', 'content': q4},
        ])
        self.assertNotIn(a2, canonical(claimed['messages']))

    def test_waiting_confirmation_non_terminal_and_route_snapshot_boundaries(self):
        """[Role] Checks waiting_confirmation retention, queued/running/recovery_required exclusion and route_snapshot JSON guards.
        [Dependencies] Real proposals/jobs rows and direct build_context invocation on Store SQLite. [Impact] No stale or unverified states enter context.
        """
        cid = self.conversation()
        q_wait, a_wait = '확인 대기 질문', '확인 카드를 생성했습니다.'
        q_rec, a_rec = '복구 필요 질문', '복구 필요 응답'
        q_run, a_run = '실행 중 질문', '실행 중 응답'
        q_queued, a_queued = '대기 중 질문', '대기 중 응답'
        q_fail_empty_route, a_fail_empty_route = '빈 route_snapshot 실패 질문', '빈 route_snapshot 실패 응답'
        q_fail_null_mail, a_fail_null_mail = 'mail_translation null 실패 질문', 'mail_translation null 실패 응답'
        q_cur = '최종 현재 질문'

        wait_jid = self.submit(cid, content=q_wait)
        self.finish(self.claim(), [{'id': 'p1', 'name': 'prepare_equipment_create',
            'arguments': canonical({'name': '확인 대기 장비', 'option_id': 1})}], content='카드 준비')
        self.finish(self.claim(), content=a_wait)

        rec_jid = self.submit(cid, content=q_rec)
        self.finish(self.claim(), content=a_rec)
        run_jid = self.submit(cid, content=q_run)
        self.finish(self.claim(), content=a_run)
        queued_jid = self.submit(cid, content=q_queued)
        self.finish(self.claim(), content=a_queued)

        fail_empty_jid = self.submit(cid, content=q_fail_empty_route)
        self.finish(self.claim(), content=a_fail_empty_route, outcome='failed')
        fail_null_mail_jid = self.submit(cid, content=q_fail_null_mail)
        self.finish(self.claim(), content=a_fail_null_mail, outcome='failed')

        cur_jid = self.submit(cid, content=q_cur)

        with self.store.db(True) as db:
            self.assertEqual(self.store.job(wait_jid, db)['state'], 'waiting_confirmation')
            db.execute("UPDATE jobs SET state='recovery_required' WHERE id=?", (rec_jid,))
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (run_jid,))
            db.execute("UPDATE jobs SET state='queued' WHERE id=?", (queued_jid,))
            db.execute("UPDATE jobs SET route_snapshot='' WHERE id=?", (fail_empty_jid,))
            db.execute("UPDATE jobs SET route_snapshot='{\"mail_translation\":null}' WHERE id=?", (fail_null_mail_jid,))
            current_job = self.store.job(cur_jid, db)
            context = build_context(db, current_job, 65536)

        self.assertEqual(context[1:], [
            {'role': 'user', 'content': q_wait},
            {'role': 'assistant', 'content': a_wait},
            {'role': 'user', 'content': q_fail_empty_route},
            {'role': 'user', 'content': q_cur},
        ])
        serialized = canonical(context)
        for forbidden in (q_rec, a_rec, q_run, a_run, q_queued, a_queued,
                          a_fail_empty_route, q_fail_null_mail, a_fail_null_mail):
            self.assertNotIn(forbidden, serialized)


if __name__ == '__main__':
    unittest.main(verbosity=2)
