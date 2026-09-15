"""[역할] 독립 카탈로그 신청. [의존성 관계] 기존 노드 서비스/호출자 transaction. [변경 시 영향도] 결재함·장비 등록."""
import json  # 기존 결재 payload 형식을 재사용합니다.
from datetime import datetime  # 기존 저장 시각 형식을 유지합니다.
from utils.lineup_node_service import create_node, LineupNodeError  # 노드 불변식을 중복 구현하지 않습니다.

MASTERS = {  # 사용자 입력을 SQL 식별자로 사용하지 않는 허용 목록입니다.
    'category': ('categories', 'CategoryId', 'ADD_CATEGORY'),  # 기존 카테고리 결재 타입입니다.
    'manufacturer': ('manufacturers', 'ManufacturerId', 'ADD_MANUFACTURER'),  # 기존 제조사 결재 타입입니다.
}  # 노드는 별도 기존 서비스를 사용합니다.

def submit_catalog_request(connection, payload, actor):
    """[역할] 신청을 작성합니다. [의존성 관계] 승인 마스터/create_node. [변경 시 영향도] commit/audit는 호출자 책임입니다."""
    if not isinstance(payload, dict):  # 배열/null/문자열을 거부합니다.
        raise LineupNodeError('JSON 객체를 입력해 주세요.')  # 안전한 사용자 오류입니다.
    kind = payload.get('kind')  # 화면 종류만 입력으로 받습니다.
    if not isinstance(kind, str) or kind not in (*MASTERS, 'node'):  # 허용된 3종만 처리합니다.
        raise LineupNodeError('신청 종류가 올바르지 않습니다.')  # 임의 테이블 접근을 차단합니다.
    allowed = {'kind', 'name'} | ({'category_id', 'manufacturer_id', 'parent_id'} if kind == 'node' else set())  # 종류별 입력 계약입니다.
    if set(payload) - allowed:  # RequesterId/Role/status 등의 위조 필드를 허용하지 않습니다.
        raise LineupNodeError('허용되지 않은 신청 항목이 있습니다.')  # 권한은 세션으로만 결정합니다.
    actor_id = actor.get('UserId') if isinstance(actor, dict) else None  # 서버가 전달한 사용자입니다.
    if isinstance(actor_id, bool) or not isinstance(actor_id, int) or actor_id <= 0:  # 잘못된 세션은 거부합니다.
        raise LineupNodeError('로그인 정보를 확인해 주세요.', 401)  # 쓰기 전 종료합니다.
    name = payload.get('name')  # 명칭은 Unicode 원문을 보존합니다.
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or any(ord(c) < 32 for c in name):  # 공백/길이/제어문자를 검증합니다.
        raise LineupNodeError('이름은 제어문자 없이 1~100자로 입력해 주세요.')  # 서버에서도 검증합니다.
    name = name.strip()  # 앞뒤 공백만 제거합니다.
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 기존 결재 시각 계약입니다.
    if kind == 'node':  # 종속성·중복·깊이·승인 정책을 기존 서비스에 위임합니다.
        result = create_node(connection, {key: value for key, value in payload.items() if key != 'kind'}, actor, now=now)  # 권한을 위조하지 않습니다.
        result.update(kind=kind, target_table='lineup_nodes', target_id=result['node_id'])  # 감사 대상만 덧붙입니다.
        return result  # 기존 노드 결재 생성도 같은 transaction 안에 있습니다.
    table, id_column, request_type = MASTERS[kind]  # 내부 상수만 SQL에 삽입합니다.
    existing = connection.execute(f'SELECT {id_column}, IsApproved FROM {table} WHERE LOWER(Name)=LOWER(?)', (name,)).fetchone()  # 잠금 안에서 중복을 검사합니다.
    if existing is not None:  # 승인 여부와 무관하게 중복 마스터를 만들지 않습니다.
        raise LineupNodeError('같은 이름의 항목이 이미 등록되었거나 승인 대기 중입니다.', 409)  # 타인의 요청자 정보는 공개하지 않습니다.
    approved = actor.get('Role') == 'admin'  # 기존 관리자 즉시 등록 정책을 유지합니다.
    cursor = connection.execute(f'INSERT INTO {table} (Name, IsApproved, CreatedAt) VALUES (?, ?, ?)', (name, int(approved), now))  # 이름은 바인딩합니다.
    target_id = int(cursor.lastrowid)  # 실제 생성 식별자입니다.
    request_id = None  # 관리자 직접 등록은 결재 대기로 위장하지 않습니다.
    if not approved:  # 일반 사용자 요청만 기존 개인 결재함에 기록합니다.
        request_data = json.dumps({'name': name, 'master_id': target_id, 'kind': kind}, ensure_ascii=False)  # 기존 처리기가 사용하는 name을 보존합니다.
        cursor = connection.execute(  # 마스터와 결재를 원자적으로 저장합니다.
            "INSERT INTO approval_requests (RequesterId,RequestType,RequestDataJSON,Status,CreatedAt,UpdatedAt) VALUES (?,?,?,'PENDING',?,?)",  # 타입은 기존값입니다.
            (actor_id, request_type, request_data, now, now),  # 신청자 ID는 세션에서만 옵니다.
        )  # 상위 route가 오류 시 둘 다 rollback합니다.
        request_id = int(cursor.lastrowid)  # 본인 접수 번호입니다.
    return {'kind': kind, 'target_table': table, 'target_id': target_id, 'name': name, 'status': 'APPROVED' if approved else 'PENDING', 'request_id': request_id}  # 값·권한을 명시합니다.
