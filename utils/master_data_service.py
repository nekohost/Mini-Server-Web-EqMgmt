"""Atomic category/manufacturer deletion and merge without severing node references."""

import json  # 대기 승인 요청의 논리 참조를 검사합니다.

MASTER_TYPES = {  # 외부 문자열을 SQL 식별자로 직접 사용하지 않습니다.
    'categories': ('CategoryId', 'category_id', 'Category', 'ADD_CATEGORY'),
    'manufacturers': ('ManufacturerId', 'manufacturer_id', 'Manufacturer', 'ADD_MANUFACTURER'),
}


class MasterDataError(ValueError):
    """[역할] 예상된 관리자 오류를 표현합니다. [의존성 관계] API. [변경 시 영향도] 상태·참조 건수 응답."""
    def __init__(self, message, status=409, references=None):
        """[역할] 공개 오류 정보를 설정합니다. [의존성 관계] ValueError. [변경 시 영향도] 내부 SQL 비노출."""
        super().__init__(message)  # 안전한 안내 문구만 저장합니다.
        self.status = status  # 입력/대상/충돌 오류를 구분합니다.
        self.references = references or {}  # 관리자에게 표시할 집계입니다.


def master_type(target_type):
    """[역할] 허용된 마스터 종류를 반환합니다. [의존성 관계] MASTER_TYPES. [변경 시 영향도] SQL 경계."""
    if target_type not in MASTER_TYPES:  # 고정 종류 이외의 경로를 거부합니다.
        raise MasterDataError('유효하지 않은 마스터 종류입니다.', 400)  # SQL 실행 전 종료합니다.
    return MASTER_TYPES[target_type]  # 컬럼명은 코드 상수로 고정됩니다.


def valid_ids(values):
    """[역할] 중복·bool·0·과대 일괄 입력을 거부합니다. [의존성 관계] delete/merge. [변경 시 영향도] 정확한 대상."""
    if not isinstance(values, list) or not 1 <= len(values) <= 500:  # 명시적 요청 상한입니다.
        raise MasterDataError('1~500개의 항목을 선택해 주세요.', 400)  # 변수 한도와 UI 오류를 방어합니다.
    if any(type(value) is not int or value < 1 or value > 2**63 - 1 for value in values):  # bool은 정수 ID가 아닙니다.
        raise MasterDataError('항목 ID는 양의 정수여야 합니다.', 400)  # 변환 추측을 하지 않습니다.
    if len(set(values)) != len(values):  # 중복 ID가 삭제 건수를 왜곡하지 못하게 합니다.
        raise MasterDataError('중복된 항목이 선택되었습니다.', 400)  # 명확히 알려 줍니다.
    return values  # 검증된 ID 목록을 그대로 사용합니다.


def reference_counts(connection, target_type, item_id):
    """[역할] 노드·장비·레거시·대기 승인 참조를 집계합니다.
    [의존성 관계] 3-Tier와 approval_requests; 독립 감사 이력은 참조 차단 대상이 아닙니다.
    [변경 시 영향도] 관리자 목록 및 삭제/병합의 공통 사전 검사입니다.
    """
    id_col, node_col, legacy_col, request_type = master_type(target_type)  # SQL 종류를 제한합니다.
    item = connection.execute(f'SELECT Name FROM {target_type} WHERE {id_col}=?', (item_id,)).fetchone()  # name 기반 승인도 확인합니다.
    if not item:  # 사라진 선택은 조용히 성공시키지 않습니다.
        raise MasterDataError('해당 마스터 항목을 찾을 수 없습니다.', 404)  # 재조회하도록 안내합니다.
    nodes = {row[0] for row in connection.execute(f'SELECT id FROM lineup_nodes WHERE {node_col}=?', (item_id,))}  # 계층 전체가 참조 대상입니다.
    options = {row[0] for row in connection.execute(f'SELECT o.id FROM equipment_options o JOIN lineup_nodes n ON n.id=o.lineup_node_id WHERE n.{node_col}=?', (item_id,))}  # 옵션 경유 승인도 확인합니다.
    equipment_count = connection.execute(f'SELECT COUNT(*) FROM equipments e JOIN equipment_options o ON o.id=e.option_id JOIN lineup_nodes n ON n.id=o.lineup_node_id WHERE n.{node_col}=?', (item_id,)).fetchone()[0]  # draft도 포함합니다.
    legacy_count = 0  # 레거시 테이블은 과도기 동안 선택적입니다.
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='equipment'").fetchone():  # 테이블 부재를 허용합니다.
        legacy_count = connection.execute(f'SELECT COUNT(*) FROM equipment WHERE {id_col}=? OR {legacy_col}=? OR {legacy_col}=?', (item_id, str(item_id), item[0])).fetchone()[0]  # 과거 문자열 참조까지 보호합니다.
    pending = 0  # 완료 승인/감사는 역사 기록으로 유지합니다.
    for kind, payload in connection.execute("SELECT RequestType,RequestDataJSON FROM approval_requests WHERE Status='PENDING'"):  # 쓰기 트랜잭션 안에서 최신 상태를 읽습니다.
        try:  # 비정상 JSON은 참조 없음으로 단정하지 않습니다.
            data = json.loads(payload)  # 전체 요청을 한 번 파싱합니다.
            if not isinstance(data, dict):  # 객체가 아닌 요청도 안전하게 차단합니다.
                raise ValueError('invalid request object')  # 아래 공개 오류로 변환합니다.
        except (TypeError, ValueError):  # 현재 대기 요청을 복구한 뒤 작업하도록 합니다.
            raise MasterDataError('형식이 잘못된 대기 승인 요청을 먼저 확인해 주세요.')  # 내용은 노출하지 않습니다.
        direct = any(str(data.get(key)) == str(item_id) for key in (node_col, id_col))  # 두 명명 규약을 지원합니다.
        node_ref = any(str(data.get('node_id')) == str(node) for node in nodes)  # Lineup_Node 승인입니다.
        option_ref = any(str(data.get('option_id')) == str(option) for option in options)  # Equipment_Option 승인입니다.
        if direct or node_ref or option_ref or (kind == request_type and data.get('name') == item[0]):  # 승인 대상의 해석을 보존합니다.
            pending += 1  # 한 요청을 중복 집계하지 않습니다.
    return {'nodes': len(nodes), 'options': len(options), 'equipments': equipment_count, 'legacy_equipment': legacy_count, 'pending_approvals': pending}  # 화면과 mutation이 같은 집계를 사용합니다.


def delete_masters(connection, target_type, item_ids, audit):
    """[역할] 참조가 없는 마스터만 전부 또는 전무로 삭제합니다.
    [의존성 관계] reference_counts, 같은 연결의 감사 callback.
    [변경 시 영향도] 단건·일괄 삭제에서 NOT NULL 참조와 기존 업무 데이터를 보존합니다.
    """
    id_col, _, _, _ = master_type(target_type)  # 외부 SQL 식별자를 제한합니다.
    ids = valid_ids(item_ids)  # mutation 전에 대상 형식을 검증합니다.
    connection.execute('BEGIN IMMEDIATE')  # 참조 검사와 삭제 사이 writer 경쟁을 막습니다.
    try:  # 감사 실패도 전체 rollback 대상입니다.
        references = {str(item_id): reference_counts(connection, target_type, item_id) for item_id in ids}  # 모든 대상부터 검사합니다.
        if any(any(counts.values()) for counts in references.values()):  # 일부만 삭제하지 않습니다.
            totals = {key: sum(counts[key] for counts in references.values()) for key in next(iter(references.values()))}  # 안내용 합계입니다.
            raise MasterDataError(f"참조 중인 항목은 삭제할 수 없습니다. 노드 {totals['nodes']}개, 장비 {totals['equipments']}개, 레거시 장비 {totals['legacy_equipment']}개, 대기 승인 {totals['pending_approvals']}개입니다. 승인 처리 후 통폐합을 이용해 주세요.", references=references)  # 다음 가능한 동선을 안내합니다.
        marks = ','.join('?' for _ in ids)  # 값은 바인딩합니다.
        before = [dict(row) for row in connection.execute(f'SELECT * FROM {target_type} WHERE {id_col} IN ({marks})', ids)]  # 삭제 전 상태를 감사에 보존합니다.
        connection.execute(f'DELETE FROM {target_type} WHERE {id_col} IN ({marks})', ids)  # 관계값을 NULL로 바꾸지 않습니다.
        audit(connection, 'DELETE_MASTER_SELECTED' if len(ids) > 1 else 'DELETE_MASTER', ids[0] if len(ids) == 1 else None, before, None, table=target_type)  # 같은 트랜잭션의 감사입니다.
        connection.commit()  # 변경과 감사를 동시에 확정합니다.
        return len(ids)  # 실제 검증·삭제한 건수를 반환합니다.
    except Exception:  # 입력 충돌·DB·감사 오류 모두 처리합니다.
        connection.rollback()  # 중간 삭제를 복구합니다.
        raise  # API가 예상/내부 오류를 구분합니다.


def merge_masters(connection, target_type, target_id, source_ids, audit):
    """[역할] 승인된 마스터의 계층을 충돌 없이 원자적으로 병합합니다.
    [의존성 관계] master 관리 API와 reference_counts; 기존 UI의 merge_from 요청.
    [변경 시 영향도] 모든 하위 노드·레거시 참조가 이동하고 현재 장비/옵션 ID는 보존됩니다.
    """
    id_col, node_col, legacy_col, _ = master_type(target_type)  # 허용된 종류만 처리합니다.
    ids = valid_ids(source_ids)  # 중복·과대 입력을 거부합니다.
    if target_id in ids:  # 자기 자신이 삭제되는 기존 결함을 막습니다.
        raise MasterDataError('기준 항목은 통합 원본으로 선택할 수 없습니다.', 400)  # 사용자 선택 오류입니다.
    connection.execute('BEGIN IMMEDIATE')  # 조회와 모든 변경을 원자화합니다.
    try:  # 오류 시 이동도 삭제도 모두 취소합니다.
        for item_id in [target_id] + ids:  # 대상과 원본의 존재/승인 상태를 확인합니다.
            row = connection.execute(f'SELECT IsApproved FROM {target_type} WHERE {id_col}=?', (item_id,)).fetchone()  # 고정 이름과 바인딩 값입니다.
            if not row:  # 부분 선택 성공은 허용하지 않습니다.
                raise MasterDataError('통합할 마스터 항목을 찾을 수 없습니다.', 404)  # 화면을 새로 조회해야 합니다.
            if row[0] != 1:  # 결재를 우회해 PENDING을 승인하지 않습니다.
                raise MasterDataError('승인 완료된 마스터만 통폐합할 수 있습니다.')  # 먼저 승인함에서 처리하도록 합니다.
            if reference_counts(connection, target_type, item_id)['pending_approvals']:  # 승인 JSON을 잘못된 ID로 남기지 않습니다.
                raise MasterDataError('관련 대기 승인 요청을 처리한 후 통폐합해 주세요.')  # 승인 데이터는 임의 수정하지 않습니다.
        roots = set()  # 병합 후의 루트 고유성을 Python casefold 기준으로 검사합니다.
        for category, manufacturer, name in connection.execute('SELECT category_id,manufacturer_id,name FROM lineup_nodes WHERE parent_id IS NULL'):  # 모든 루트의 결과 키를 계산합니다.
            if target_type == 'categories' and category in ids:  # 변경되는 분류만 치환합니다.
                category = target_id  # 다른 분류 축은 유지합니다.
            if target_type == 'manufacturers' and manufacturer in ids:  # 제조사 병합도 같은 계약입니다.
                manufacturer = target_id  # 카테고리 축은 유지합니다.
            key = (category, manufacturer, name.strip().casefold())  # SQLite NULL UNIQUE의 빈틈을 검사합니다.
            if key in roots:  # 자동으로 노드를 삭제/합치지 않습니다.
                raise MasterDataError('통합 후 중복되는 루트 노드가 있습니다. 노드 명칭을 구분한 후 다시 시도해 주세요.')  # 충돌 시 전체 작업이 중단됩니다.
            roots.add(key)  # 형제 루트의 고유성을 기록합니다.
        marks = ','.join('?' for _ in ids)  # source 값은 모두 바인딩합니다.
        connection.execute(f'UPDATE lineup_nodes SET {node_col}=? WHERE {node_col} IN ({marks})', (target_id, *ids))  # 부모와 자식 모두 같은 축을 이동합니다.
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='equipment'").fetchone():  # 과도기 레거시를 보존합니다.
            for item_id in ids:  # 문자열 참조도 누락하지 않습니다.
                name = connection.execute(f'SELECT Name FROM {target_type} WHERE {id_col}=?', (item_id,)).fetchone()[0]  # 원본 마스터 명칭입니다.
                connection.execute(f'UPDATE equipment SET {id_col}=?,{legacy_col}=? WHERE {id_col}=? OR {legacy_col}=? OR {legacy_col}=?', (target_id, str(target_id), item_id, str(item_id), name))  # 레거시 ID와 표현을 함께 이동합니다.
        connection.execute(f'DELETE FROM {target_type} WHERE {id_col} IN ({marks})', ids)  # 참조를 옮긴 원본만 삭제합니다.
        audit(connection, 'MERGE_MASTER', target_id, {'SourceIds': ids}, {'TargetId': target_id}, table=target_type)  # 감사와 이동은 원자적입니다.
        connection.commit()  # 모든 변경을 동시에 확정합니다.
        return len(ids)  # 성공한 원본 개수입니다.
    except Exception:  # 충돌과 감사 쓰기 실패도 rollback합니다.
        connection.rollback()  # 계층과 마스터를 이전 상태로 복구합니다.
        raise  # API에서 안전한 안내를 제공합니다.

