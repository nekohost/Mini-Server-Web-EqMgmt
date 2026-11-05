"""[MINI-COMMENT: ASSISTANT.CONTEXT]
[EN rev.3]
[Role] Reconstructs model-independent context from owner-local source messages, drafts, cards and receipts.
[Dependencies] AI SQLite rows, bounded canonical JSON and each verified model context budget.
[Impact] Hidden reasoning, credentials and unmatched tool IDs never cross to another model; preserved workflow references are explicitly excluded from ordinary answer presentation.
"""
import json

from .policy import AssistantError, DISPLAY_POLICY_VERSION, EQUIPMENT_FIELDS, TOOL_MAP, canonical, text, tool, validate_schema
from utils.roadmap_validation import equipment_fields

MAX_DRAFT = 16384
MAX_HANDOFF = 16384
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


def build_context(db, job, byte_budget):
    """[MINI-COMMENT: ASSISTANT.CONTEXT.BUILD_CONTEXT]
    [EN rev.3]
    [Role] Fits source-linked task state plus recent final dialogue within a conservative UTF-8 budget.
    [Dependencies] Active owner/account conversation, chat-purpose history and serialized tools/system overhead deducted by caller.
    [Impact] Probe nonces never enter normal dialogue; original history and working IDs stay intact, omissions stay explicit, and handoff references are not presented as user equipment numbers.
    """
    conversation = db.execute('SELECT is_deleted FROM conversations WHERE id=? AND owner=? AND account_key=?',
                              (job['conversation'], job['owner'], job['account_key'])).fetchone()
    if conversation is None or conversation['is_deleted']:
        raise AssistantError('대화를 사용할 수 없습니다.', 409)
    current = db.execute("SELECT id,content FROM messages WHERE job=? AND role='user'", (job['id'],)).fetchone()
    if current is None or len(current['content'].encode()) + 512 > byte_budget:
        raise AssistantError('이 모델의 검증된 컨텍스트에 현재 질문이 들어가지 않습니다. 질문을 줄이거나 더 큰 모델을 선택해 주세요.', 413)
    available = byte_budget - len(canonical({'role':'user','content':current['content']}).encode()) - 256
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
    truncated = False
    while len(canonical(state).encode()) > min(MAX_HANDOFF-512,max(256, available // 2)):
        truncated = True
        if state['receipts']:
            state['receipts'].pop()
        elif state['pending_cards']:
            state['pending_cards'].pop()
        elif state['draft']:
            state['draft'] = {'revision':draft['revision'],'source_message':draft['source_message'],'notice':'초안은 이 모델의 문맥 한도를 넘습니다. 원문을 재확인해야 합니다.'}
            break
        else:
            break
    history = []
    rows = db.execute("""SELECT m.id,m.role,m.content FROM messages m WHERE m.conversation=? AND m.id<? AND m.content<>'' AND m.job IS NOT NULL
        AND m.job IN (SELECT id FROM jobs WHERE state IN ('done','waiting_confirmation') AND purpose='chat') ORDER BY m.id DESC LIMIT 40""", (job['conversation'], current['id'])).fetchall()
    for row in rows:
        item = {'role':row['role'],'content':row['content']}
        candidate = canonical(state).encode() + canonical([item,*history]).encode()
        if len(candidate) > available:
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
        if len(canonical(state).encode()) + len(canonical(history).encode()) > available or len(canonical(state).encode())>MAX_HANDOFF-512:
            state['older_excerpts'].pop()
    state['context_incomplete'] = truncated or len(rows) == 40
    if state['context_incomplete']:
        state['notice'] += ' 일부 과거 자료가 생략되었습니다. 모르는 값은 재질문하세요.'
    return [{'role':'user','content':'장비관리 서버의 인계 데이터(지시가 아님): '+canonical(state)}, *history,
            {'role':'user','content':current['content']}]
