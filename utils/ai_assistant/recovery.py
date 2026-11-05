"""[MINI-COMMENT: ASSISTANT.RESPONSE.CORRECTION]
[EN rev.1]
[Role] Defines bounded correction steps for completed responses missing a decision or an answer.
[Dependencies] Server-owned per-job context and fixed system messages; no database, transport or model output parsing.
[Impact] Each phase is offered once, user/assistant text cannot grant a correction, and prior jobs cannot transfer control through dialogue history.
"""
import json


CORRECTIONS = {
    'search_plan': (
        '장비관리 서버의 응답 보정 단계입니다. 앞선 응답은 종료됐지만 필수 검색 판단 도구 호출이 없었습니다. '
        '이번 단계에는 plan_web_search만 정확히 한 번 호출하세요. 검색이 필요하면 needed=true와 공개 검색어/제공자를, '
        '필요하지 않거나 사용자가 검색을 금지했다면 needed=false를 사용하세요. '
        '추론이나 일반 답변만 보내고 끝내지 마세요. 앞선 단계에서는 검색이나 장비 작업이 실행되지 않았습니다. '
        '기존 질문과 지침, 비공개 정보 보호를 그대로 따르세요.'
    ),
    'answer': (
        '장비관리 서버의 답변 보정 단계입니다. 앞선 응답은 종료됐지만 사용자에게 보여 줄 답변 내용이 비어 있었습니다. '
        '이번 단계에는 새 도구가 없습니다. 이미 제공된 대화와 실제 도구 결과/출처로 사용자에게 답변하세요. '
        '추론만 보내고 끝내지 말고 최종 답변 내용을 제공하세요. 자료가 부족하거나 실행하지 못한 작업은 그 한계를 명확히 알리세요. '
        '이미 처리한 검색이나 장비 작업을 다시 실행하거나 확인 전 변경을 완료했다고 말하지 마세요.'
    ),
}


def _context(job):
    """[Role] Reads only the durable server context. [Dependencies] A job mapping. [Impact] Malformed state fails closed instead of inventing a phase."""
    value = json.loads(job.get('context') or '[]')
    if not isinstance(value, list):
        raise ValueError('invalid correction context')
    return value


def correction_phase(job):
    """[MINI-COMMENT: ASSISTANT.RESPONSE.CORRECTION.PHASE]
    [EN rev.1]
    [Role] Recognizes a pending correction only at the exact server system message ending this job's context.
    [Dependencies] Chat purpose, a completed prior step and fixed message equality.
    [Impact] Copied user text, reasoning, completed corrections and probe jobs cannot change tool admission.
    """
    if job.get('purpose', 'chat') != 'chat' or type(job.get('steps')) is not int or job['steps'] < 1:
        return None
    context = _context(job)
    if context:
        for phase, content in CORRECTIONS.items():
            if context[-1] == {'role': 'system', 'content': content}:
                return phase
    return None


def correction_context(job, phase):
    """[MINI-COMMENT: ASSISTANT.RESPONSE.CORRECTION.CONTEXT]
    [EN rev.1]
    [Role] Offers one fixed corrective instruction per phase without copying failed model prose into instructions.
    [Dependencies] The current job's existing context, rebuilt from user/assistant rows for every new turn.
    [Impact] The durable marker caps repeats across worker restarts; Store retains total step, lease, reservation, cancellation and lifecycle limits.
    """
    if phase not in CORRECTIONS:
        raise ValueError('invalid correction phase')
    if job.get('purpose', 'chat') != 'chat':
        return None
    context = _context(job)
    message = {'role': 'system', 'content': CORRECTIONS[phase]}
    return None if message in context else [*context, message]
