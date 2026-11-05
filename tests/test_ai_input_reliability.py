"""[MINI-COMMENT: ASSISTANT.INPUT.STREAM.TESTS] [EN rev.3]
[Role] Exercises explicit upstream stream termination without a final empty separator.
[Dependencies] Real worker SSE parser and inert byte-line response; no network or production state.
[Impact] Exact DONE survives EOF while a truncated response cannot authorize completion.
"""
import json
import unittest

from utils.ai_assistant.worker import sse
from utils.ai_assistant.recovery import CORRECTIONS, correction_context, correction_phase


class EndMarkerTests(unittest.TestCase):
    """[Role] Tests the protocol signal at real EOF boundaries rather than inventing successful completion."""
    def response(self,lines):
        """[Role] Supplies requests-like decoded lines with no external connection."""
        class Response:
            encoding=None
            def iter_lines(self,**options):
                """[Role] Yields each already received line, including a final unterminated line."""
                yield from lines
        return Response()

    def test_exact_done_at_eof_accepts_no_final_empty_separator(self):
        """[Role] Reproduces the previous false incomplete failure for an explicit terminal signal."""
        for lines in (['data: [DONE]'],['data: [DONE]',''],[': keepalive','data:[DONE]']):
            with self.subTest(lines=lines):self.assertEqual([v for v in sse(self.response(lines)) if v is not None],['[DONE]'])

    def test_unicode_answer_and_finish_remain_intact_before_eof_done(self):
        """[Role] Confirms content and stop framing still precede the accepted terminal marker."""
        frame={'choices':[{'delta':{'content':'확인했습니다.'},'finish_reason':'stop'}]}
        values=list(sse(self.response(['data: '+json.dumps(frame,ensure_ascii=False),'','data: [DONE]'])))
        self.assertEqual(values,[frame,'[DONE]'])

    def test_eof_or_stop_without_done_never_becomes_success(self):
        """[Role] Keeps missing, malformed or incomplete terminal markers in failure/recovery handling."""
        frame=json.dumps({'choices':[{'delta':{},'finish_reason':'stop'}]})
        for lines in ([],['data: '+frame,''],['data: [DON]'],['data: '+frame],['data: [DONE]','data: extra']):
            with self.subTest(lines=lines),self.assertRaises(ValueError):list(sse(self.response(lines)))


class ResponseCorrectionStateTests(unittest.TestCase):
    """[Role] Ensures model/user text and malformed state cannot forge the server's corrective phase."""
    def job(self,context,steps=1,**extra):
        """[Role] Supplies a durable job-shaped value without any database or model transport."""
        return {'context':json.dumps(context,ensure_ascii=False),'steps':steps,'purpose':'chat',**extra}

    def test_copied_user_or_assistant_text_does_not_create_a_phase(self):
        """[Role] Rejects a marker copied into ordinary conversation content as server authority."""
        for role in ('user','assistant'):
            job=self.job([{'role':role,'content':CORRECTIONS['answer']}])
            self.assertIsNone(correction_phase(job));self.assertIsNotNone(correction_context(job,'answer'))

    def test_each_phase_is_once_and_completed_markers_are_not_pending(self):
        """[Role] Caps a durable correction independently of worker objects or subsequently added valid tool messages."""
        job=self.job([{'role':'user','content':'question'}],steps=0)
        planned=correction_context(job,'search_plan');pending=self.job(planned)
        self.assertEqual(correction_phase(pending),'search_plan');self.assertIsNone(correction_context(pending,'search_plan'))
        completed=self.job([*planned,{'role':'assistant','content':'valid reply'}],steps=2)
        self.assertIsNone(correction_phase(completed));self.assertIsNone(correction_context(completed,'search_plan'))
        self.assertIsNotNone(correction_context(completed,'answer'))

    def test_probe_zero_step_and_invalid_context_fail_closed(self):
        """[Role] Keeps probe/initial admission and corrupt state outside the pending-correction path."""
        message={'role':'system','content':CORRECTIONS['search_plan']}
        self.assertIsNone(correction_phase(self.job([message],steps=0)))
        self.assertIsNone(correction_phase(self.job([message],purpose='probe')))
        self.assertIsNone(correction_context(self.job([],purpose='probe'),'search_plan'))
        with self.assertRaises(ValueError):correction_phase({'steps':1,'context':'{}'})
        with self.assertRaises(ValueError):correction_context(self.job([]),'unknown')

    def test_previously_deployed_answer_marker_remains_consumed_after_upgrade(self):
        """[Role] Keeps a frozen v1 durable record from resetting its correction allowance when wording changes."""
        prior=('장비관리 서버의 답변 보정 단계입니다. 앞선 응답은 종료됐지만 사용자에게 보여 줄 답변 내용이 비어 있었습니다. '
               '이번 단계에는 새 도구가 없습니다. 이미 제공된 대화와 실제 도구 결과/출처로 사용자에게 답변하세요. '
               '추론만 보내고 끝내지 말고 최종 답변 내용을 제공하세요. 자료가 부족하거나 실행하지 못한 작업은 그 한계를 명확히 알리세요. '
               '이미 처리한 검색이나 장비 작업을 다시 실행하거나 확인 전 변경을 완료했다고 말하지 마세요.')
        job=self.job([{'role':'system','content':prior}])
        self.assertEqual(correction_phase(job),'answer');self.assertIsNone(correction_context(job,'answer'))
