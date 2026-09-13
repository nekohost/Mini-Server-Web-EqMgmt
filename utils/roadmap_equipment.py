"""022/033·023·026: 권한·상태·검색·CSV의 단일 장비 계약."""
import csv  # 표준 UTF-8 CSV만 지원합니다.
import hashlib  # 가져오기 내용과 확인 토큰을 식별합니다.
import io  # 제한된 CSV 메모리 스트림입니다.
import json  # 감사 스냅샷과 미리보기를 직렬화합니다.
import secrets  # 추측 불가능한 미리보기 토큰입니다.
import time  # 토큰의 만료 기준입니다.
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo  # UI와 알림의 날짜는 서울 달력입니다.
from utils.roadmap_validation import InputError, text_value, integer, day, equipment_fields
from utils.lineup_node_service import add_full_model_names

STATES = {'ACTIVE': '정상', 'LOANED': '대여', 'REPAIR': '수리', 'DISPOSED': '폐기'}
TRANSITIONS = {'ACTIVE': ('LOANED', 'REPAIR', 'DISPOSED'), 'LOANED': ('ACTIVE', 'REPAIR'),
               'REPAIR': ('ACTIVE', 'DISPOSED'), 'DISPOSED': ('ACTIVE',)}
CSV_FIELDS = ('Name', 'OptionId', 'SerialNumber', 'PurchaseDate', 'WarrantyEndDate', 'ReplacementDueDate', 'IsPublic', 'Memo')
CSV_LIMIT = 1024 * 1024
CSV_ROWS = 500
EXPORT_LIMIT = 10000
FROM_SQL = ''' FROM equipments e
 LEFT JOIN equipment_options opt ON opt.id=e.option_id
 LEFT JOIN lineup_nodes node ON node.id=opt.lineup_node_id
 LEFT JOIN categories cat ON cat.CategoryId=node.category_id
 LEFT JOIN manufacturers mfg ON mfg.ManufacturerId=node.manufacturer_id
 LEFT JOIN users u ON u.UserId=e.user_id '''
SELECT_SQL = '''SELECT e.id AS EquipmentId,e.id AS id,e.name AS Name,e.option_id AS OptionId,
 e.serial_number AS SerialNumber,e.purchase_date AS PurchaseDate,e.status AS Status,e.memo AS Memo,
 e.user_id AS UserId,e.is_public AS IsPublic,e.is_draft AS IsDraft,e.created_at AS CreatedAt,e.updated_at AS UpdatedAt,
 e.revision AS Revision,e.warranty_end_date AS WarrantyEndDate,e.replacement_due_date AS ReplacementDueDate,
 opt.option_name AS OptionName,opt.specs_json AS SpecsJson,node.id AS LineupNodeId,node.name AS ModelName,node.depth AS ModelDepth,
 cat.CategoryId,cat.Name AS CategoryName,cat.NameKo AS CategoryNameKo,cat.NameEn AS CategoryNameEn,
 mfg.ManufacturerId,mfg.Name AS ManufacturerName,mfg.NameKo AS ManufacturerNameKo,mfg.NameEn AS ManufacturerNameEn,
 u.NickName AS OwnerNickName '''
PATH_CTE = '''WITH RECURSIVE paths(id,full_name,depth) AS (
 SELECT id,name,1 FROM lineup_nodes WHERE parent_id IS NULL
 UNION ALL SELECT n.id,p.full_name || ' / ' || n.name,p.depth+1 FROM lineup_nodes n
 JOIN paths p ON n.parent_id=p.id WHERE p.depth<50) '''


def utc_now():
    """[역할] 정렬 가능한 감사 시각. [의존성 관계] 모든 새 쓰기. [변경 시 영향도] UTC ISO 기록."""
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def kst_today():
    """[역할] 동일한 날짜 경계. [의존성 관계] 기한/알림. [변경 시 영향도] 서버 TZ와 독립."""
    return datetime.now(ZoneInfo('Asia/Seoul')).date()


def due_badge(value, today=None):
    """[역할] 기한 배지 계약. [의존성 관계] 목록/알림. [변경 시 영향도] 기존 비정상 일자는 표시만 격리."""
    if not value:
        return {'state': 'unset', 'label': '미설정', 'days': None}
    try:
        days = (date.fromisoformat(value) - (today or kst_today())).days
    except (TypeError, ValueError):
        return {'state': 'invalid', 'label': '날짜 확인 필요', 'days': None}
    return {'state': 'expired' if days < 0 else 'soon' if days <= 30 else 'normal',
            'label': f'{abs(days)}일 경과' if days < 0 else '오늘 만료' if days == 0 else f'D-{days}', 'days': days}


def can_write(row, user):
    """[역할] 장비 변경 권한. [의존성 관계] 상태/파일/기한. [변경 시 영향도] 공개는 쓰기 허용 아님."""
    return user.get('Role') == 'admin' or row['user_id'] == user['UserId']


def require_equipment(connection, equipment_id, user, write=False):
    """[역할] 상세 권한 공통화. [의존성 관계] 모든 장비 부속 API. [변경 시 영향도] 비공개 존재 은닉."""
    row = connection.execute('SELECT * FROM equipments WHERE id=?', (equipment_id,)).fetchone()
    if not row or not (can_write(row, user) or not write and row['is_public'] == 1 and not row['is_draft']):
        raise InputError('장비를 찾을 수 없거나 접근 권한이 없습니다.', 404)
    if row['is_draft'] and row['user_id'] != user['UserId']:
        raise InputError('다른 사용자의 임시저장 장비에는 접근할 수 없습니다.', 404)
    return dict(row)


def query_contract(args, user):
    """[역할] 권한 AND 필터와 정렬 allowlist. [의존성 관계] 목록/export. [변경 시 영향도] SQL 주입/범위 분리 방지."""
    mode = args.get('type', 'my')
    if mode not in ('my', 'public'):
        raise InputError('목록 범위가 올바르지 않습니다.')
    draft = args.get('is_draft', '0')
    include = args.get('include_mine', 'false')
    if str(draft) not in ('0', '1') or str(include) not in ('true', 'false'):
        raise InputError('목록 옵션이 올바르지 않습니다.')
    conditions, values = [], []
    if str(draft) == '1':
        conditions += ['e.user_id=?', 'e.is_draft=1']
        values += [user['UserId']]
    else:
        conditions += ['COALESCE(e.is_draft,0)=0']
        if mode == 'my':
            conditions += ['e.user_id=?']
            values += [user['UserId']]
        elif user.get('Role') != 'admin':
            conditions += ['(e.is_public=1 OR e.user_id=?)' if include == 'true' else '(e.is_public=1 AND (e.user_id IS NULL OR e.user_id<>?))']
            values += [user['UserId']]
    for key, column in (('category_id', 'node.category_id'), ('manufacturer_id', 'node.manufacturer_id')):
        if args.get(key):
            conditions.append(column + '=?')
            values.append(integer(args[key], key))
    if args.get('status'):
        if args['status'] not in STATES:
            raise InputError('지원하지 않는 장비 상태입니다.')
        conditions += ['e.status=?']
        values += [args['status']]
    start, end = day(args.get('purchase_from'), '시작일'), day(args.get('purchase_to'), '종료일')
    if start and end and start > end:
        raise InputError('시작일은 종료일보다 빠르거나 같아야 합니다.')
    for value, op in ((start, '>='), (end, '<=')):
        if value:
            conditions.append('e.purchase_date' + op + '?')
            values.append(value)
    due = args.get('due', '')
    if due not in ('', 'soon', 'expired'):
        raise InputError('기한 필터가 올바르지 않습니다.')
    if due:
        today = kst_today().isoformat()
        expression = "{c} < ?" if due == 'expired' else "{c} BETWEEN ? AND date(?, '+30 days')"
        conditions.append('(' + ' OR '.join(expression.format(c=c) for c in ('e.warranty_end_date', 'e.replacement_due_date')) + ')')
        values.extend([today] * (2 if due == 'expired' else 4))
    keyword = text_value(args.get('keyword', ''), '검색어', 200)
    cte = ''
    if keyword:
        cte = PATH_CTE
        like = '%' + keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        fields = ('e.name', 'e.serial_number', 'e.memo', 'node.name', 'node.official_model_name', 'cat.Name', 'cat.NameKo', 'cat.NameEn', 'mfg.Name', 'mfg.NameKo', 'mfg.NameEn', 'opt.option_name', '(SELECT full_name FROM paths WHERE paths.id=node.id)')
        conditions.append('(' + ' OR '.join(f"{column} LIKE ? ESCAPE '\\'" for column in fields) + ')')
        values.extend([like] * len(fields))
    sorts = {'newest': 'e.id DESC', 'oldest': 'e.id ASC', 'name': 'e.name COLLATE NOCASE,e.id DESC',
             'purchase_desc': 'e.purchase_date DESC,e.id DESC', 'purchase_asc': 'e.purchase_date ASC,e.id DESC',
             'updated': 'e.updated_at DESC,e.id DESC'}
    sort = args.get('sort', 'newest')
    if sort not in sorts:
        raise InputError('정렬 항목이 올바르지 않습니다.')
    order = sorts[sort]
    if mode == 'public' and include == 'true':
        order = f'CASE WHEN e.user_id={integer(user["UserId"], "사용자")} THEN 0 ELSE 1 END,' + order
    return cte, ' WHERE ' + ' AND '.join(conditions), values, ' ORDER BY ' + order


def list_equipment(connection, args, user, paginated=True, export=False):
    """[역할] 서버 필터/총수/안정적 페이지. [의존성 관계] query_contract/모델명. [변경 시 영향도] 배열 API 호환."""
    cte, where, values, order = query_contract(args, user)
    page = integer(args.get('page', 1), '페이지', 1, 1000000)
    per_page = integer(args.get('per_page', 25), '페이지 크기', 1, 100)
    # caller read transaction으로 count와 rows가 같은 snapshot을 보게 합니다.
    total = connection.execute(cte + 'SELECT COUNT(*)' + FROM_SQL + where, values).fetchone()[0]
    if export and total > EXPORT_LIMIT:
        raise InputError('내보내기는 10,000건 이하로 필터를 좁혀 주세요.', 413)
    limit = ' LIMIT ? OFFSET ?' if paginated else ''
    bindings = values + [per_page, (page - 1) * per_page] if paginated else values
    result = [dict(row) for row in connection.execute(cte + SELECT_SQL + FROM_SQL + where + order + limit, bindings)]
    add_full_model_names(connection, result)
    for item in result:
        try:
            item['Specs'] = json.loads(item['SpecsJson'] or '{}')
        except (TypeError, ValueError):
            item['Specs'] = {}
        item['StatusLabel'] = STATES.get(item['Status'], '기존 상태: ' + str(item['Status']))
        item['WarrantyBadge'] = due_badge(item['WarrantyEndDate'])
        item['ReplacementBadge'] = due_badge(item['ReplacementDueDate'])
    return {'items': result, 'total': total, 'page': page, 'per_page': per_page, 'pages': (total + per_page - 1) // per_page} if paginated else result


def audit(connection, equipment_id, action, user_id, before, after):
    """[역할] 독립 이력에 동일 transaction 기록. [의존성 관계] 상태/CSV/파일. [변경 시 영향도] 삭제 뒤 감사 보존."""
    connection.execute('INSERT INTO equipments_audit_log(equipment_id,action_type,old_value,new_value,changed_by,changed_at) VALUES(?,?,?,?,?,?)',
                       (equipment_id, action, json.dumps(before, ensure_ascii=False) if before is not None else None,
                        json.dumps(after, ensure_ascii=False) if after is not None else None, user_id, utc_now()))


def change_status(connection, equipment_id, user, data):
    """[역할] 상태 전이/revision 경합/사유 감사. [의존성 관계] writer transaction. [변경 시 영향도] 대여·반납·폐기 복구."""
    row = require_equipment(connection, equipment_id, user, write=True)
    state = text_value(data.get('status'), '상태', 16, True)
    reason = text_value(data.get('reason'), '변경 사유', 1000, True)
    revision = integer(data.get('revision'), 'revision', 0)
    if row['revision'] != revision:
        raise InputError('다른 변경이 저장되었습니다. 새로고침 후 다시 시도해 주세요.', 409)
    if row['is_draft'] or state not in TRANSITIONS.get(row['status'], ()):
        raise InputError('허용되지 않는 상태 전이입니다.', 409)
    result = connection.execute('UPDATE equipments SET status=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?',
                                (state, utc_now(), equipment_id, revision))
    if result.rowcount != 1:
        raise InputError('동시 변경이 감지되었습니다.', 409)
    after = {'status': state, 'revision': revision + 1, 'reason': reason}
    audit(connection, equipment_id, 'STATUS_CHANGE', user['UserId'], {'status': row['status'], 'revision': revision}, after)
    return after


def approved_option(connection, option_id):
    """[역할] CSV가 결재를 우회하지 못하게 검사. [의존성 관계] 실제 마스터/노드. [변경 시 영향도] 신규 마스터 생성 없음."""
    row = connection.execute('''SELECT o.status,n.status,c.IsApproved,m.IsApproved FROM equipment_options o
        JOIN lineup_nodes n ON n.id=o.lineup_node_id JOIN categories c ON c.CategoryId=n.category_id
        JOIN manufacturers m ON m.ManufacturerId=n.manufacturer_id WHERE o.id=?''', (option_id,)).fetchone()
    if not row or tuple(row) != ('APPROVED', 'APPROVED', 1, 1):
        raise InputError('승인된 카탈로그 옵션 ID를 선택해 주세요.')


def safe_csv_cell(value):
    """[역할] 스프레드시트 수식 주입 방어. [의존성 관계] export. [변경 시 영향도] 위험 접두사에 apostrophe 추가."""
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().lstrip('\ufeff').lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


def export_csv(rows):
    """[역할] BOM CSV와 import 공통 컬럼. [의존성 관계] scoped list. [변경 시 영향도] 외부 xlsx 의존성 없음."""
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(CSV_FIELDS)
    for row in rows:
        writer.writerow([safe_csv_cell(row.get(key)) for key in CSV_FIELDS])
    return stream.getvalue().encode('utf-8-sig')


def validate_csv(connection, raw):
    """[역할] 미리보기 행별 오류/중복/옵션 검증. [의존성 관계] preview와 확정 재검사. [변경 시 영향도] 부분 import 금지."""
    if len(raw) > CSV_LIMIT:
        raise InputError('CSV 파일은 1MiB 이하여야 합니다.', 413)
    try:
        decoded = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded, newline=''), strict=True)
        if reader.fieldnames != list(CSV_FIELDS):
            raise InputError('CSV 헤더/순서를 내려받은 양식과 동일하게 맞춰 주세요.')
        rows, errors, serials = [], [], set()
        for number, original in enumerate(reader, 2):
            if number > CSV_ROWS + 1:
                raise InputError('한 번에 최대 500행을 가져올 수 있습니다.', 413)
            try:
                if None in original or any(value is None for value in original.values()):
                    raise InputError('CSV 열 개수가 올바르지 않습니다.')
                item = dict(original)
                if item['IsPublic'] not in ('0', '1'):
                    raise InputError('IsPublic은 0 또는 1이어야 합니다.')
                item['IsPublic'] = int(item['IsPublic'])
                item = equipment_fields(item)
                item['Name'] = text_value(item['Name'], '장비명', 200, True)
                item['OptionId'] = integer(item['OptionId'], 'OptionId')
                approved_option(connection, item['OptionId'])
                serial = item.get('SerialNumber')
                if serial and (serial in serials or connection.execute('SELECT 1 FROM equipments WHERE serial_number=?', (serial,)).fetchone()):
                    raise InputError('이미 사용 중이거나 CSV에서 중복된 시리얼입니다.')
                if serial:
                    serials.add(serial)
                rows.append(item)
            except InputError as error:
                errors.append({'row': number, 'message': str(error)})
        if not rows and not errors:
            raise InputError('장비 데이터가 없는 CSV입니다.')
        return rows, errors
    except (UnicodeError, csv.Error, ValueError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError('UTF-8 CSV 형식과 따옴표/열 구성을 확인해 주세요.') from None


def preview_import(connection, raw, user):
    """[역할] 검증된 내용만 15분 토큰에 연결. [의존성 관계] authenticated writer. [변경 시 영향도] 행 생성은 안 함."""
    rows, errors = validate_csv(connection, raw)
    result = {'rows': rows, 'errors': errors, 'count': len(rows), 'token': None}
    if errors:
        return result
    now = int(time.time())
    connection.execute('DELETE FROM equipment_imports WHERE token_hash IN (SELECT token_hash FROM equipment_imports WHERE expires_at<? AND result_json IS NULL LIMIT 100)', (now,))
    if connection.execute('SELECT COUNT(*) FROM equipment_imports WHERE user_id=? AND result_json IS NULL', (user['UserId'],)).fetchone()[0] >= 5:
        raise InputError('진행 중인 미리보기가 많습니다. 15분 뒤 다시 시도해 주세요.', 429)
    token = secrets.token_urlsafe(32)
    connection.execute('INSERT INTO equipment_imports(token_hash,user_id,payload_json,digest,expires_at,created_at) VALUES(?,?,?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user['UserId'], raw.decode('utf-8-sig'), hashlib.sha256(raw).hexdigest(), now + 900, utc_now()))
    result['token'] = token
    return result


def commit_import(connection, token, user):
    """[역할] 재검증/전체 원자적 삽입/중복 확인. [의존성 관계] BEGIN IMMEDIATE. [변경 시 영향도] 기존 장비 변경 없음."""
    token = text_value(token, '미리보기 토큰', 128, True)
    key = hashlib.sha256(token.encode()).hexdigest()
    record = connection.execute('SELECT * FROM equipment_imports WHERE token_hash=? AND user_id=?', (key, user['UserId'])).fetchone()
    if not record:
        raise InputError('유효한 미리보기 토큰이 아닙니다.', 404)
    if record['result_json']:
        return {**json.loads(record['result_json']), 'replayed': True}
    if record['expires_at'] < time.time():
        raise InputError('미리보기가 만료되었습니다. 다시 검증해 주세요.', 409)
    rows, errors = validate_csv(connection, record['payload_json'].encode('utf-8'))
    if errors:
        raise InputError('검증 후 장비/카탈로그가 변경되었습니다. CSV 미리보기를 다시 실행해 주세요.', 409)
    ids = []
    for item in rows:
        cursor = connection.execute('''INSERT INTO equipments(option_id,name,serial_number,purchase_date,memo,user_id,is_public,is_draft,
             warranty_end_date,replacement_due_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,0,?,?,?,?)''',
            (item['OptionId'], item['Name'], item['SerialNumber'] or None, item['PurchaseDate'], item['Memo'], user['UserId'], item['IsPublic'],
             item['WarrantyEndDate'], item['ReplacementDueDate'], utc_now(), utc_now()))
        ids.append(cursor.lastrowid)
        audit(connection, cursor.lastrowid, 'CSV_IMPORT', user['UserId'], None, {'import_id': key, **item})
    result = {'equipment_ids': ids, 'count': len(ids), 'import_id': key, 'replayed': False}
    connection.execute('UPDATE equipment_imports SET result_json=?,payload_json=? WHERE token_hash=?', (json.dumps(result), '', key))
    return result  # caller commit 후에만 응답합니다.
