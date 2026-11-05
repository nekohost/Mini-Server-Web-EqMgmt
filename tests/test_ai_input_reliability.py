"""[MINI-COMMENT: ASSISTANT.INPUT.STREAM.TESTS] [EN rev.1]
[Role] Exercises explicit upstream stream termination without a final empty separator.
[Dependencies] Real worker SSE parser and inert byte-line response; no network or production state.
[Impact] Exact DONE survives EOF while a truncated response cannot authorize completion.
"""
import json
import unittest

from utils.ai_assistant.worker import sse


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
