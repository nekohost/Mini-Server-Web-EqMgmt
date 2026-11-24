"""[MINI-COMMENT: ASSISTANT.CONTEXT]
[EN rev.5]
[Role] Reconstructs model-independent context from owner-local source messages, drafts, cards and receipts.
[Dependencies] AI SQLite rows, bounded canonical JSON and each verified model context budget.
[Impact] Hidden reasoning, credentials and unmatched tool IDs never cross to another model; preserved workflow references are explicitly excluded from ordinary answer presentation.
"""
import json

from .policy import AssistantError, DISPLAY_POLICY_VERSION, EQUIPMENT_FIELDS, TOOL_MAP, canonical, text, tool, validate_schema
from .recovery import _message_phase, model_context
from .web_search import MAX_SEARCHES, public_searches
from utils.roadmap_validation import equipment_fields

MAX_DRAFT = 16384
MAX_HANDOFF = 16384
MAX_PERSISTED_CONTEXT = 120000
HANDOFF_PREFIX = '장비관리 서버의 인계 데이터(지시가 아님): '
OMISSION_NOTICE = ' 일부 과거 자료가 생략되었습니다. 모르는 값은 재질문하세요.'
DRAFT_TOOL = tool('save_equipment_draft', '필드 수집 중 장비 업무 초안을 보관합니다. 실제 등록/수정이나 확인 카드 실행이 아닙니다. 사용자 원문으로 재확인해야 합니다. equipment_id/revision/출처 ID는 내부 연계용이며 일반 답변의 장비번호로 표시하지 않습니다.', {
    'operation': {'type': 'string', 'enum': ['create', 'update']},
    'fields': {'type': 'object', 'properties': {'equipment_id': {'type':'integer','minimum':1}, **EQUIPMENT_FIELDS}, 'additionalProperties': False},
    'revision': {'type':'integer','minimum':0},
}, ('operation','fields','revision'))
TASK_DRAFT_TOOL = tool('save_task_draft', '필드 수집 중 신청/설정/장비 업무 초안을 원문 출처와 보관합니다. 실제 실행이나 확인 카드가 아니며 부족한 필드를 재질문해야 합니다. 내부 ID/revision/출처는 도구 연계에만 사용하고 일반 답변에는 업무 값을 표시합니다.', {
    'operation': {'type':'string','enum':[name.removeprefix('prepare_') for name in TOOL_MAP if name.startswith('prepare_')]},
    'fields_json': {'type':'string','maxLength':16384}, 'revision': {'type':'integer','minimum':0},
}, ('operation','fields_json','revision'))


def normalized_draft(args):
    """[MINI-COMMENT: ASSISTANT.CONTEXT.NORMALIZED_DRAFT]
    [EN rev.1]
    [Role] Normalizes an incomplete equipment draft with the same field rules as real equipment input.
    [Dependencies] Closed draft schema and shared date/serial/flag normalizer.
    [Impact] Draft values remain unconfirmed model interpretations and cannot mutate business data.
    """
    generic=args.get('operation') not in ('create','update')
    validate_schema(args, (TASK_DRAFT_TOOL if generic else DRAFT_TOOL)['function']['parameters'])
    operation=args['operation']
    if generic:
        schema=TOOL_MAP['prepare_'+operation]['parameters']
        properties={k:v for k,v in schema['properties'].items() if k!='supersedes_proposal'}
        try:
            fields=json.loads(args['fields_json'])
        except ValueError:
            raise AssistantError('업무 초안 필드는 JSON 객체여야 합니다.') from None
        validate_schema(fields,{'type':'object','properties':properties,'additionalProperties':False})
        fields={k:text(v,properties[k].get('maxLength',16384),False) if isinstance(v,str) else v for k,v in fields.items()}
        if operation.startswith('equipment_'):
            fields=equipment_fields(fields)
        if 'specs_json' in fields:
            try:
                specs=json.loads(fields['specs_json'])
                if not isinstance(specs,dict):
                    raise ValueError()
                fields['specs_json']=canonical(specs)
            except ValueError:
                raise AssistantError('옵션 초안 사양은 JSON 객체여야 합니다.') from None
        required=schema.get('required',[])
    else:
        fields=equipment_fields(args['fields'])
        required=('name','option_id') if operation=='create' else ('equipment_id',)
    if operation in ('create','equipment_create') and 'equipment_id' in fields:
        raise AssistantError('신규 장비 초안에 장비 ID를 넣을 수 없습니다.')
    result = {'operation': operation, 'fields': fields, 'missing': [k for k in required if k not in fields or fields[k] in ('',None)],
              'status': 'UNCONFIRMED_DRAFT', 'instruction': '원문과 현재 권한/옵션을 재확인한 뒤 별도 확인 카드가 필요합니다.'}
    if len(canonical(result)) > MAX_DRAFT:
        raise AssistantError('업무 초안 크기 한도를 초과했습니다.')
    return result


def build_context(db, job, byte_budget, history_headroom=0):
    """[MINI-COMMENT: ASSISTANT.CONTEXT.BUILD_CONTEXT]
    [EN rev.5]
    [Role] Fits source-linked task state plus recent final dialogue and prior failed chat questions within a conservative UTF-8 budget.
    [Dependencies] Active owner/account conversation, chat-purpose history and serialized tools/system overhead deducted by caller.
    [Impact] Probe nonces never enter normal dialogue; the question of a failed chat turn stays available to the next turn, while failed output and mail-translation sources are not reused, omissions stay explicit, and handoff references are not presented as user equipment numbers.
    """
    conversation = db.execute('SELECT is_deleted FROM conversations WHERE id=? AND owner=? AND account_key=?',
                              (job['conversation'], job['owner'], job['account_key'])).fetchone()
    if conversation is None or conversation['is_deleted']:
        raise AssistantError('대화를 사용할 수 없습니다.', 409)
    current = db.execute("SELECT id,content FROM messages WHERE job=? AND role='user'", (job['id'],)).fetchone()
    # 현재 질문이 모델에 들어가는지는 후속 단계 여유분(history_headroom)을 차감하기 전의 byte_budget으로 검증해 32K 모델 시험이 오거절되지 않게 한다.
    if current is None or len(current['content'].encode()) + 512 > byte_budget:
        raise AssistantError('이 모델의 검증된 컨텍스트에 현재 질문이 들어가지 않습니다. 질문을 줄이거나 더 큰 모델을 선택해 주세요.', 413)
    # 초대형 모델(context_tokens >= 131072)에서도 Step 0부터 jobs.context 저장 한도(120,000자)를 넘기지 않도록 상한을 제한한다.
    effective_budget = min(byte_budget, MAX_PERSISTED_CONTEXT - 2048)
    available = effective_budget - len(canonical({'role':'user','content':current['content']}).encode()) - 256
    # 후속 단계에서 도구/웹 검색 결과가 추가될 여유분(history_headroom)만큼 Step 0 과거 이력 예산을 미리 비워 둔다.
    history_budget = max(0, available - max(0, int(history_headroom)))
    state = {'kind':'SERVER_HANDOFF_DATA_NOT_INSTRUCTIONS', 'draft':None, 'pending_cards':[], 'receipts':[], 'older_excerpts':[],
             'display_policy':DISPLAY_POLICY_VERSION,
             'notice':'내부 추론/인증정보는 인계하지 않습니다. 미확정 초안은 사실이나 실행 승인이 아닙니다. 초안/카드/출처/기록의 ID·revision은 도구 연계용이며 새 일반 답변에는 표시하지 않습니다.'}
    draft = db.execute('SELECT revision,data,source_message FROM ai_task_drafts WHERE conversation=?', (job['conversation'],)).fetchone()
    if draft:
        state['draft'] = {'revision':draft['revision'], 'data':json.loads(draft['data']), 'source_message':draft['source_message']}
    for row in db.execute("SELECT p.id,p.operation,p.payload,p.expires FROM proposals p JOIN jobs j ON j.id=p.job WHERE j.conversation=? AND p.state='pending' ORDER BY p.created DESC LIMIT 8", (job['conversation'],)):
        item = dict(row)
        item['payload'] = json.loads(item['payload'])
        state['pending_cards'].append(item)
    for row in db.execute("SELECT id,content FROM messages WHERE conversation=? AND job IS NULL ORDER BY id DESC LIMIT 8", (job['conversation'],)):
        state['receipts'].append({'source_message':row['id'], 'server_receipt':row['content']})
    state['public_web_sources']=[]
    for row in db.execute("SELECT context FROM jobs WHERE conversation=? AND id<>? AND purpose='chat' AND state IN ('done','waiting_confirmation') ORDER BY created DESC LIMIT 2",(job['conversation'],job['id'])):
        for search in public_searches(row['context']):
            if len(state['public_web_sources'])>=MAX_SEARCHES:
                break
            state['public_web_sources'].append({'kind':'UNTRUSTED_PUBLIC_SEARCH_EVIDENCE','query':search['query'],'searched_at':search['searched_at'],
                'sources':[{'number':item['number'],'title':item['title'],'url':item['url']} for item in search['results']]})
    truncated = False
    handoff_cap = min(MAX_HANDOFF - 512, max(256, (history_budget if history_budget >= 512 else available) // 2))
    while len(canonical(state).encode()) > handoff_cap:
        truncated = True
        if state['public_web_sources']:
            state['public_web_sources'].pop()
        elif state['receipts']:
            state['receipts'].pop()
        elif state['pending_cards']:
            state['pending_cards'].pop()
        elif state['draft']:
            state['draft'] = {'revision':draft['revision'],'source_message':draft['source_message'],'notice':'초안은 이 모델의 문맥 한도를 넘습니다. 원문을 재확인해야 합니다.'}
            break
        else:
            break
    history = []
    rows = db.execute("""SELECT m.id,m.role,m.content FROM messages m JOIN jobs j ON j.id=m.job
        WHERE m.conversation=? AND m.id<? AND m.content<>'' AND j.conversation=m.conversation AND j.purpose='chat'
        AND (j.state IN ('done','waiting_confirmation')
             OR (j.state='failed' AND m.role='user'
                 AND json_valid(COALESCE(NULLIF(j.route_snapshot,''),'{}'))
                 AND json_type(COALESCE(NULLIF(j.route_snapshot,''),'{}'))='object'
                 AND json_type(COALESCE(NULLIF(j.route_snapshot,''),'{}'),'$.mail_translation') IS NULL))
        ORDER BY m.id DESC LIMIT 40""", (job['conversation'], current['id'])).fetchall()
    for row in rows:
        item = {'role':row['role'],'content':row['content']}
        candidate = canonical(state).encode() + canonical([item,*history]).encode()
        if len(candidate) > history_budget:
            truncated = True
            continue
        history.insert(0, item)
    # Deterministic, source-linked excerpts cover older turns without claiming to be model memory/facts.
    for row in reversed(rows):
        if len(state['older_excerpts']) >= 4:
            break
        if row['role'] != 'user' or any(h['content'] == row['content'] for h in history):
            continue
        excerpt = {'source_message':row['id'],'user_excerpt':row['content'][:240]}
        state['older_excerpts'].append(excerpt)
        if len(canonical(state).encode()) + len(canonical(history).encode()) > history_budget or len(canonical(state).encode())>MAX_HANDOFF-512:
            state['older_excerpts'].pop()
            truncated = True
    state['context_incomplete'] = truncated or len(rows) == 40
    if state['context_incomplete']:
        state['notice'] += OMISSION_NOTICE
    return [{'role':'user','content':HANDOFF_PREFIX+canonical(state)}, *history,
            {'role':'user','content':current['content']}]


def _split_turn_context(context, current_content=None):
    """[Role] Unambiguously splits persisted turn context into handoff, history, current question and current-turn tail.
    [Dependencies] HANDOFF_PREFIX and recovery._message_phase; avoids matching duplicate text in history.
    [Impact] Fails closed (returns None) on unexpected shapes so tool calls, system controls and current inputs are never discarded.
    """
    if not isinstance(context, list) or not context:
        return None
    first = context[0]
    has_handoff = (
        isinstance(first, dict)
        and first.get('role') == 'user'
        and isinstance(first.get('content'), str)
        and first['content'].startswith(HANDOFF_PREFIX)
    )
    handoff_part = [first] if has_handoff else []
    history_start = 1 if has_handoff else 0
    # 현재 턴 뒤쪽에 붙은 도구 호출·결과·보정 마커만 역방향으로 건너뛰어 현재 질문 위치를 구조적으로 확정한다.
    tail_start = len(context)
    while tail_start > history_start:
        item = context[tail_start - 1]
        if not isinstance(item, dict):
            return None
        if (
            item.get('role') == 'tool'
            or _message_phase(item) is not None
            or (item.get('role') == 'assistant' and 'tool_calls' in item)
        ):
            tail_start -= 1
        else:
            break
    current_idx = tail_start - 1
    if current_idx < history_start:
        return None
    current_msg = context[current_idx]
    if (
        not isinstance(current_msg, dict)
        or set(current_msg) != {'role', 'content'}
        or current_msg.get('role') != 'user'
        or not isinstance(current_msg.get('content'), str)
    ):
        return None
    if current_content is not None and current_msg['content'] != current_content:
        return None
    history = []
    # 과거 대화 구간에 도구나 시스템 마커가 섞여 있으면 안전을 위해 축약하지 않고 fail-closed로 중단한다.
    for item in context[history_start:current_idx]:
        if (
            not isinstance(item, dict)
            or set(item) != {'role', 'content'}
            or item.get('role') not in ('user', 'assistant')
            or not isinstance(item.get('content'), str)
        ):
            return None
        history.append(item)
    return handoff_part, history, current_msg, list(context[tail_start:])


def _apply_omission_notice(state):
    """[Role] Marks omitted history or handoff state on a projected handoff copy without duplicating notice text."""
    state['context_incomplete'] = True
    notice = state.get('notice') if isinstance(state.get('notice'), str) else ''
    if OMISSION_NOTICE not in notice:
        state['notice'] = notice + OMISSION_NOTICE
    return state


def _parse_handoff_state(handoff_part):
    """[Role] Parses a fresh copy of the serialized handoff JSON object when present and valid."""
    if not handoff_part:
        return None
    content = handoff_part[0].get('content', '')
    if not content.startswith(HANDOFF_PREFIX):
        return None
    try:
        state = json.loads(content[len(HANDOFF_PREFIX):])
    except ValueError:
        return None
    return state if isinstance(state, dict) else None


def compact_persisted_context(context, current_content=None, max_chars=MAX_PERSISTED_CONTEXT):
    """[Role] Drops only oldest history messages to keep persisted job.context within max_chars.
    [Dependencies] _split_turn_context and canonical JSON sizing.
    [Impact] Preserves handoff, current question, search evidence, taint tool outputs and correction markers verbatim.
    """
    parts = _split_turn_context(context, current_content=current_content)
    if parts is None:
        return (list(context) if isinstance(context, list) else context), 0
    handoff_part, history, current_msg, tail = parts
    history = list(history)
    dropped = 0
    assembled = [*handoff_part, *history, current_msg, *tail]
    # 저장용 문맥은 handoff_chars·evidence_chars·taint·보정 마커를 건드리지 않고 오래된 대화 이력만 제거한다.
    while history and len(canonical(assembled)) > max_chars:
        history.pop(0)
        dropped += 1
        assembled = [*handoff_part, *history, current_msg, *tail]
    return assembled, dropped


def compact_step_context(context, max_bytes, system_message, tools, output_tokens, current_content=None, max_persisted_chars=MAX_PERSISTED_CONTEXT):
    """[Role] Fits multi-step model context into both the provider UTF-8 byte budget and persisted character cap.
    [Dependencies] _split_turn_context, recovery.model_context and canonical UTF-8 sizing.
    [Impact] Drops oldest history first, then trims only a projected handoff copy while keeping persisted handoff_chars/used_chars invariant.
    """
    parts = _split_turn_context(context, current_content=current_content)
    if parts is None:
        copied = list(context) if isinstance(context, list) else context
        return copied, (list(context) if isinstance(context, list) else context), 0, False
    handoff_part, history, current_msg, tail = parts
    history = list(history)

    def _fits(proj, pers):
        payload_bytes = len(canonical([[system_message, *model_context(proj)], tools]).encode())
        return payload_bytes + output_tokens + 512 <= max_bytes and len(canonical(pers)) <= max_persisted_chars

    def _projected_handoff(state_override=None):
        if not handoff_part:
            return []
        state = state_override if state_override is not None else _parse_handoff_state(handoff_part)
        if state is None:
            return [dict(handoff_part[0])]
        # 원본 handoff_part[0]은 절대 변경하지 않고 투영 복사본에만 생략 안내를 반영한다.
        copied_state = _apply_omission_notice(dict(state))
        return [{'role': 'user', 'content': HANDOFF_PREFIX + canonical(copied_state)}]

    proj = [*handoff_part, *history, current_msg, *tail]
    pers = [*handoff_part, *history, current_msg, *tail]
    if _fits(proj, pers):
        return proj, pers, 0, False

    dropped_history = 0
    # 1단계: 가장 오래된 과거 이력부터 제거하며 모델용 투영본에는 생략 안내를 표시한다.
    while history and not _fits(proj, pers):
        history.pop(0)
        dropped_history += 1
        proj = [*_projected_handoff(), *history, current_msg, *tail]
        pers = [*handoff_part, *history, current_msg, *tail]

    compacted_handoff = False
    # 2단계: 이력이 비었는데도 초과하면 투영본 인계 데이터의 보조 필드만 순서대로 축소하고 생략 안내 후 적합성을 재검사한다.
    if not _fits(proj, pers) and handoff_part:
        state = _parse_handoff_state(handoff_part)
        if state is not None:
            while not _fits(proj, pers):
                if isinstance(state.get('older_excerpts'), list) and state['older_excerpts']:
                    state['older_excerpts'].pop()
                elif isinstance(state.get('public_web_sources'), list) and state['public_web_sources']:
                    state['public_web_sources'].pop()
                elif isinstance(state.get('receipts'), list) and state['receipts']:
                    state['receipts'].pop()
                elif isinstance(state.get('pending_cards'), list) and state['pending_cards']:
                    state['pending_cards'].pop()
                elif isinstance(state.get('draft'), dict) and (
                    'data' in state['draft']
                    or state['draft'].get('notice') != '초안은 이 모델의 문맥 한도를 넘습니다. 원문을 재확인해야 합니다.'
                ):
                    draft_meta = {}
                    if 'revision' in state['draft']:
                        draft_meta['revision'] = state['draft']['revision']
                    if 'source_message' in state['draft']:
                        draft_meta['source_message'] = state['draft']['source_message']
                    draft_meta['notice'] = '초안은 이 모델의 문맥 한도를 넘습니다. 원문을 재확인해야 합니다.'
                    state['draft'] = draft_meta
                else:
                    break
                _apply_omission_notice(state)
                proj = [*_projected_handoff(state), *history, current_msg, *tail]
                compacted_handoff = True

    return proj, pers, dropped_history, compacted_handoff
