"""Staging candidate for safe lineup-node tree operations.

This module deliberately has no Flask or production-database dependency.  Route
handlers can call it with their request-scoped SQLite connection, while the
Staging test suite can exercise every invariant against an in-memory database.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Mapping
from utils.model_names import normalize_official_model_name  # 공식명은 분류명과 별도 계약으로 검증합니다.


MAX_TREE_DEPTH = 50
MAX_NODE_NAME_LENGTH = 100
ALLOWED_NODE_STATUSES = {"APPROVED", "PENDING", "REJECTED"}


class LineupNodeError(ValueError):
    """[역할] 클라이언트에 안전하게 반환할 노드 검증 오류와 HTTP 상태를 보관합니다.

    [의존성 관계] 노드 서비스의 생성·수정·삭제 함수가 공통으로 사용합니다.
    [변경 시 영향도] route adapter의 오류 응답 코드와 사용자 안내 문구에 영향을 줍니다.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _required_int(value: Any, label: str) -> int:
    """[역할] bool을 제외한 양의 정수 식별자로 요청 값을 정규화합니다.

    [의존성 관계] category/manufacturer/node 식별자 입력 검증에 사용합니다.
    [변경 시 영향도] 잘못된 JSON 형식의 허용·거부 범위가 달라집니다.
    """

    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise LineupNodeError(f"{label} 식별자가 올바르지 않습니다.")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise LineupNodeError(f"{label} 식별자가 올바르지 않습니다.") from error
    if normalized <= 0:
        raise LineupNodeError(f"{label} 식별자가 올바르지 않습니다.")
    return normalized


def _optional_int(value: Any, label: str) -> int | None:
    """[역할] 비어 있는 부모 식별자는 None, 나머지는 양의 정수로 정규화합니다.

    [의존성 관계] 루트 생성과 루트 이동을 같은 API 계약으로 처리합니다.
    [변경 시 영향도] parent_id의 JSON 표현 호환성에 영향을 줍니다.
    """

    if value in (None, ""):
        return None
    return _required_int(value, label)


def _node_name(value: Any) -> str:
    """[역할] 라인업 노드 이름의 공백·형식·길이를 검증합니다.

    [의존성 관계] 생성과 이름 변경에 동일한 명명 정책을 적용합니다.
    [변경 시 영향도] 관리자 화면과 장비등록 화면에서 허용되는 이름 범위가 달라집니다.
    """

    if not isinstance(value, str):
        raise LineupNodeError("노드 이름을 입력해 주세요.")
    normalized = value.strip()
    if not normalized:
        raise LineupNodeError("노드 이름을 입력해 주세요.")
    if len(normalized) > MAX_NODE_NAME_LENGTH:
        raise LineupNodeError(f"노드 이름은 {MAX_NODE_NAME_LENGTH}자 이하여야 합니다.")
    return normalized



def _official_model_name(value: Any) -> str | None:
    """[역할] 공통 공식명 검증 오류를 안전한 노드 API 오류로 변환합니다.
    [의존성 관계] model_names.normalize_official_model_name.
    [변경 시 영향도] 관리자 생성·수정의 400 응답과 미지정 표현.
    """
    try:  # 공통 입력 계약을 우회하지 않습니다.
        return normalize_official_model_name(value)  # 빈값은 NULL로 저장합니다.
    except ValueError as error:  # 예상된 사용자 입력 오류만 변환합니다.
        raise LineupNodeError(str(error)) from error  # 내부 예외는 기존 route의 500 처리를 따릅니다.


def _fetch_node(cursor: Any, node_id: int) -> dict[str, Any] | None:
    """[역할] row_factory 설정과 무관하게 단일 노드를 사전 형태로 조회합니다.

    [의존성 관계] 생성 부모 검증, 이동, 삭제에서 공통 사용합니다.
    [변경 시 영향도] 노드 서비스가 기대하는 lineup_nodes 컬럼 계약에 영향을 줍니다.
    """

    cursor.execute(
        """
        SELECT id, parent_id, category_id, manufacturer_id, name, depth, status,
               requested_by, created_at, official_model_name
        FROM lineup_nodes
        WHERE id = ?
        """,
        (node_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


def _ensure_approved_master(cursor: Any, table: str, id_column: str, item_id: int, label: str) -> None:
    """[역할] 선택된 카테고리 또는 제조사가 존재하고 승인 상태인지 확인합니다.

    [의존성 관계] categories/manufacturers의 IsApproved 계약을 사용합니다.
    [변경 시 영향도] 미승인 마스터 아래에 노드를 만들 수 있는지 여부에 영향을 줍니다.
    """

    cursor.execute(
        f"SELECT IsApproved FROM {table} WHERE {id_column} = ?",  # table/column은 내부 상수만 전달합니다.
        (item_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LineupNodeError(f"선택한 {label}를 찾을 수 없습니다.", 404)
    if int(row[0]) != 1:
        raise LineupNodeError(f"승인되지 않은 {label}에는 노드를 등록할 수 없습니다.", 409)


def _actual_depth(cursor: Any, node: Mapping[str, Any]) -> int:
    """[역할] 저장된 depth를 신뢰하지 않고 부모 연결을 따라 실제 깊이를 계산합니다.

    [의존성 관계] lineup_nodes.parent_id와 MAX_TREE_DEPTH를 사용합니다.
    [변경 시 영향도] 기존 손상 트리를 발견하는 시점과 최대 깊이 판정에 영향을 줍니다.
    """

    seen = {int(node["id"])}
    depth = 1
    parent_id = node["parent_id"]
    while parent_id is not None:
        normalized_parent_id = int(parent_id)
        if normalized_parent_id in seen:
            raise LineupNodeError("기존 트리에서 순환 참조가 발견되었습니다.", 409)
        seen.add(normalized_parent_id)
        parent = _fetch_node(cursor, normalized_parent_id)
        if parent is None:
            raise LineupNodeError("기존 트리에서 연결이 끊긴 상위 노드가 발견되었습니다.", 409)
        if (
            int(parent["category_id"]) != int(node["category_id"])
            or int(parent["manufacturer_id"]) != int(node["manufacturer_id"])
        ):
            raise LineupNodeError("기존 트리의 카테고리·제조사 연결이 일치하지 않습니다.", 409)
        depth += 1
        if depth > MAX_TREE_DEPTH:
            raise LineupNodeError("기존 트리가 허용된 최대 깊이를 초과했습니다.", 409)
        parent_id = parent["parent_id"]
    return depth


def _subtree_offsets(cursor: Any, root_id: int) -> dict[int, int]:
    """[역할] 루트 기준 각 자손의 상대 깊이를 계산하고 기존 순환을 탐지합니다.

    [의존성 관계] lineup_nodes.id/parent_id 전체 연결을 사용합니다.
    [변경 시 영향도] 이동 시 갱신할 노드 집합과 최대 깊이 검증에 영향을 줍니다.
    """

    cursor.execute("SELECT id, parent_id FROM lineup_nodes")
    children: dict[int, list[int]] = defaultdict(list)
    for child_id, parent_id in cursor.fetchall():
        if parent_id is not None:
            children[int(parent_id)].append(int(child_id))

    offsets = {root_id: 0}
    queue = deque([root_id])
    while queue:
        current_id = queue.popleft()
        for child_id in children.get(current_id, []):
            if child_id in offsets:
                raise LineupNodeError("기존 트리에서 순환 참조가 발견되었습니다.", 409)
            offsets[child_id] = offsets[current_id] + 1
            queue.append(child_id)
    return offsets


def _ensure_no_sibling_duplicate(
    cursor: Any,
    *,
    parent_id: int | None,
    category_id: int,
    manufacturer_id: int,
    name: str,
    exclude_node_id: int | None = None,
) -> None:
    """[역할] 루트 또는 동일 부모 아래의 이름 중복을 대소문자 구분 없이 차단합니다.

    [의존성 관계] SQLite LOWER와 parent_id/category_id/manufacturer_id를 사용합니다.
    [변경 시 영향도] 동일 경로에서 허용되는 노드 이름의 유일성에 영향을 줍니다.
    """

    params: list[Any]
    if parent_id is None:
        query = """
            SELECT id FROM lineup_nodes
            WHERE parent_id IS NULL AND category_id = ? AND manufacturer_id = ?
              AND LOWER(name) = LOWER(?)
        """
        params = [category_id, manufacturer_id, name]
    else:
        query = """
            SELECT id FROM lineup_nodes
            WHERE parent_id = ? AND LOWER(name) = LOWER(?)
        """
        params = [parent_id, name]
    if exclude_node_id is not None:
        query += " AND id <> ?"
        params.append(exclude_node_id)
    cursor.execute(query, params)
    if cursor.fetchone() is not None:
        raise LineupNodeError("같은 위치에 동일한 이름의 노드가 이미 존재합니다.", 409)


def create_node(
    connection: Any,
    payload: Mapping[str, Any],
    actor: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """[역할] 관리자 즉시 승인 또는 일반 사용자 승인 요청 방식으로 노드를 생성합니다.

    [의존성 관계] categories, manufacturers, lineup_nodes, approval_requests를 사용합니다.
    [변경 시 영향도] 장비등록 화면과 관리자 화면의 새 노드 생성 결과에 영향을 줍니다.
    """

    if not isinstance(payload, dict):
        raise LineupNodeError("JSON 객체를 입력해 주세요.")
    cursor = connection.cursor()
    name = _node_name(payload.get("name"))
    if actor.get("Role") != "admin" and "official_model_name" in payload:  # 일반 노드 결재로 공식명 지정 권한을 우회하지 못하게 합니다.
        raise LineupNodeError("공식 모델명은 관리자만 지정할 수 있습니다.", 403)  # 아직 어떤 행도 생성하지 않았습니다.
    official_name = _official_model_name(payload.get("official_model_name"))  # 생략한 기존 요청은 NULL로 저장합니다.
    category_id = _required_int(payload.get("category_id"), "카테고리")
    manufacturer_id = _required_int(payload.get("manufacturer_id"), "제조사")
    parent_id = _optional_int(payload.get("parent_id"), "상위 노드")
    _ensure_approved_master(cursor, "categories", "CategoryId", category_id, "카테고리")
    _ensure_approved_master(cursor, "manufacturers", "ManufacturerId", manufacturer_id, "제조사")

    depth = 1
    if parent_id is not None:
        parent = _fetch_node(cursor, parent_id)
        if parent is None:
            raise LineupNodeError("상위 노드를 찾을 수 없습니다.", 404)
        if parent["status"] != "APPROVED":
            raise LineupNodeError("승인된 상위 노드 아래에만 하위 노드를 등록할 수 있습니다.", 409)
        if int(parent["category_id"]) != category_id or int(parent["manufacturer_id"]) != manufacturer_id:
            raise LineupNodeError("상위 노드의 카테고리·제조사 조합이 요청과 일치하지 않습니다.", 409)
        depth = _actual_depth(cursor, parent) + 1
        if depth > MAX_TREE_DEPTH:
            raise LineupNodeError(f"트리의 최대 깊이({MAX_TREE_DEPTH}단계)를 초과할 수 없습니다.")

    _ensure_no_sibling_duplicate(
        cursor,
        parent_id=parent_id,
        category_id=category_id,
        manufacturer_id=manufacturer_id,
        name=name,
    )

    is_admin = actor.get("Role") == "admin"
    status = "APPROVED" if is_admin else "PENDING"
    actor_id = _required_int(actor.get("UserId"), "사용자")
    created_at = now or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO lineup_nodes
            (parent_id, category_id, manufacturer_id, name, depth, status, requested_by, created_at, official_model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (parent_id, category_id, manufacturer_id, name, depth, status, actor_id, created_at, official_name),  # 값은 SQL과 분리해 바인딩합니다.
    )
    node_id = int(cursor.lastrowid)

    if not is_admin:
        request_data = json.dumps(
            {
                "type": "Lineup_Node",
                "node_id": node_id,
                "name": name,
                "parent_id": parent_id,
                "category_id": category_id,
                "manufacturer_id": manufacturer_id,
                "depth": depth,
            },
            ensure_ascii=False,
        )
        cursor.execute(
            """
            INSERT INTO approval_requests
                (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt)
            VALUES (?, 'Lineup_Node', ?, 'PENDING', ?, ?)
            """,
            (actor_id, request_data, created_at, created_at),
        )

    return {"node_id": node_id, "status": status, "depth": depth, "name": name, "official_model_name": official_name}  # 생성 응답과 감사에 공식명도 포함합니다.


def update_node(connection: Any, node_id_value: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """[역할] 관리자가 노드 이름·부모를 변경하고 서브트리 전체 깊이를 원자적으로 보정합니다.

    [의존성 관계] lineup_nodes의 재귀 부모 관계와 MAX_TREE_DEPTH를 사용합니다.
    [변경 시 영향도] 관리자 노드 이동 및 장비 카탈로그 경로 표시에 영향을 줍니다.
    """

    if not isinstance(payload, dict):
        raise LineupNodeError("JSON 객체를 입력해 주세요.")
    cursor = connection.cursor()
    node_id = _required_int(node_id_value, "노드")
    node = _fetch_node(cursor, node_id)
    if node is None:
        raise LineupNodeError("수정할 노드를 찾을 수 없습니다.", 404)
    if node["status"] != "APPROVED":
        raise LineupNodeError("승인 대기 노드는 전자결재함에서 처리해 주세요.", 409)

    name = _node_name(payload.get("name", node["name"]))
    official_name = _official_model_name(payload.get("official_model_name", node["official_model_name"]))  # 키 생략은 유지, null/빈값은 해제합니다.
    parent_id = _optional_int(payload.get("parent_id", node["parent_id"]), "상위 노드")
    if parent_id == node_id:
        raise LineupNodeError("자기 자신을 상위 노드로 지정할 수 없습니다.")

    subtree = _subtree_offsets(cursor, node_id)
    if parent_id in subtree:
        raise LineupNodeError("자신의 하위 노드를 상위 노드로 지정할 수 없습니다.")

    new_depth = 1
    if parent_id is not None:
        parent = _fetch_node(cursor, parent_id)
        if parent is None:
            raise LineupNodeError("지정한 상위 노드를 찾을 수 없습니다.", 404)
        if parent["status"] != "APPROVED":
            raise LineupNodeError("승인된 상위 노드 아래로만 이동할 수 있습니다.", 409)
        if (
            int(parent["category_id"]) != int(node["category_id"])
            or int(parent["manufacturer_id"]) != int(node["manufacturer_id"])
        ):
            raise LineupNodeError("다른 카테고리·제조사 조합으로 노드를 이동할 수 없습니다.", 409)
        new_depth = _actual_depth(cursor, parent) + 1

    deepest_depth = new_depth + max(subtree.values())
    if deepest_depth > MAX_TREE_DEPTH:
        raise LineupNodeError(f"이동 후 트리가 최대 깊이({MAX_TREE_DEPTH}단계)를 초과합니다.")
    _ensure_no_sibling_duplicate(
        cursor,
        parent_id=parent_id,
        category_id=int(node["category_id"]),
        manufacturer_id=int(node["manufacturer_id"]),
        name=name,
        exclude_node_id=node_id,
    )

    cursor.execute(
        "UPDATE lineup_nodes SET name = ?, parent_id = ?, depth = ?, official_model_name = ? WHERE id = ?",  # 이름·이동·공식명은 같은 transaction입니다.
        (name, parent_id, new_depth, official_name, node_id),  # 자손의 공식명은 수정하거나 상속하지 않습니다.
    )
    for descendant_id, offset in subtree.items():
        if descendant_id != node_id:
            cursor.execute(
                "UPDATE lineup_nodes SET depth = ? WHERE id = ?",
                (new_depth + offset, descendant_id),
            )
    return {"node_id": node_id, "name": name, "parent_id": parent_id, "depth": new_depth, "official_model_name": official_name, "before": node}  # 같은 감사에 이전·이후 값을 보관합니다.


def delete_node(connection: Any, node_id_value: Any) -> dict[str, Any]:
    """[역할] 자식과 옵션이 없는 노드만 관리자가 삭제할 수 있게 검증합니다.

    [의존성 관계] lineup_nodes와 equipment_options 연결 상태를 사용합니다.
    [변경 시 영향도] 관리자 삭제 안전성과 기존 장비 참조 보존에 영향을 줍니다.
    """

    cursor = connection.cursor()
    node_id = _required_int(node_id_value, "노드")
    node = _fetch_node(cursor, node_id)
    if node is None:
        raise LineupNodeError("삭제할 노드를 찾을 수 없습니다.", 404)
    if node["status"] != "APPROVED":
        raise LineupNodeError("승인 대기 노드는 전자결재함에서 처리해 주세요.", 409)
    cursor.execute("SELECT COUNT(*) FROM lineup_nodes WHERE parent_id = ?", (node_id,))
    if int(cursor.fetchone()[0]) > 0:
        raise LineupNodeError("하위 노드가 있어 삭제할 수 없습니다.", 409)
    cursor.execute("SELECT COUNT(*) FROM equipment_options WHERE lineup_node_id = ?", (node_id,))
    if int(cursor.fetchone()[0]) > 0:
        raise LineupNodeError("연결된 옵션이 있어 삭제할 수 없습니다.", 409)
    cursor.execute("DELETE FROM lineup_nodes WHERE id = ?", (node_id,))
    return {"node_id": node_id, "name": node["name"], "official_model_name": node["official_model_name"]}  # 삭제 감사에서도 기존 공식명을 보존합니다.


def get_admin_snapshot(connection: Any) -> dict[str, list[dict[str, Any]]]:
    """[역할] 관리자 화면에 마스터·전체 노드 상태·연결 사용량을 한 번에 제공합니다.

    [의존성 관계] categories, manufacturers, lineup_nodes, equipment_options, equipments를 사용합니다.
    [변경 시 영향도] 관리자 트리 필터와 삭제 가능 여부 표시에 영향을 줍니다.
    """

    cursor = connection.cursor()
    cursor.execute(
        "SELECT CategoryId, Name, IsApproved FROM categories ORDER BY Name COLLATE NOCASE, CategoryId"
    )
    categories = [
        {"id": int(item_id), "name": name, "is_approved": bool(is_approved)}
        for item_id, name, is_approved in cursor.fetchall()
    ]
    cursor.execute(
        "SELECT ManufacturerId, Name, IsApproved FROM manufacturers ORDER BY Name COLLATE NOCASE, ManufacturerId"
    )
    manufacturers = [
        {"id": int(item_id), "name": name, "is_approved": bool(is_approved)}
        for item_id, name, is_approved in cursor.fetchall()
    ]
    cursor.execute(
        """
        SELECT n.id, n.parent_id, n.category_id, n.manufacturer_id, n.name,
               n.depth, n.status, n.requested_by, n.created_at, n.official_model_name,
               (SELECT COUNT(*) FROM lineup_nodes child WHERE child.parent_id = n.id) AS child_count,
               (SELECT COUNT(*) FROM equipment_options opt WHERE opt.lineup_node_id = n.id) AS option_count,
               (SELECT COUNT(*)
                  FROM equipments equipment
                  JOIN equipment_options opt ON opt.id = equipment.option_id
                 WHERE opt.lineup_node_id = n.id) AS equipment_count
        FROM lineup_nodes n
        ORDER BY n.category_id, n.manufacturer_id, n.depth, n.name COLLATE NOCASE, n.id
        """
    )
    columns = [description[0] for description in cursor.description]
    nodes = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.execute("""
        SELECT opt.id, opt.lineup_node_id, opt.option_name, opt.specs_json, opt.status,
               opt.requested_by, opt.created_at,
               SUM(CASE WHEN e.id IS NOT NULL AND COALESCE(e.is_draft, 0) = 0 THEN 1 ELSE 0 END) AS active_equipment_count,
               SUM(CASE WHEN e.id IS NOT NULL AND COALESCE(e.is_draft, 0) <> 0 THEN 1 ELSE 0 END) AS draft_equipment_count
        FROM equipment_options opt LEFT JOIN equipments e ON e.option_id = opt.id
        GROUP BY opt.id ORDER BY opt.option_name COLLATE NOCASE, opt.id
    """)
    columns = [description[0] for description in cursor.description]
    options = [dict(zip(columns, row)) for row in cursor.fetchall()]
    usage = defaultdict(lambda: [0, 0])
    for option in options:
        try:
            option["specs"] = json.loads(option["specs_json"] or "{}")
            if not isinstance(option["specs"], dict):
                option["specs"] = {}
        except (ValueError, TypeError):
            option["specs"] = {}
        usage[option["lineup_node_id"]][0] += option["active_equipment_count"]
        usage[option["lineup_node_id"]][1] += option["draft_equipment_count"]
    for node in nodes:
        node["active_equipment_count"], node["draft_equipment_count"] = usage[node["id"]]
    return {"categories": categories, "manufacturers": manufacturers, "nodes": nodes, "options": options}


def add_full_model_names(connection: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[역할] 기존 ModelName/ID/FullModelName을 유지하고 공식명과 우선 표시명을 추가합니다.
    [의존성 관계] 부모 연결을 1회 조회하며 요청 내 경로를 캐시합니다.
    [변경 시 영향도] 나의/공개 장비와 대시보드 모델 표시. 손상 트리는 말단명 폴백.
    """
    if not items:
        return items
    nodes = {row[0]: row for row in connection.execute(
        "SELECT id, parent_id, name, category_id, manufacturer_id, official_model_name FROM lineup_nodes")}
    cache: dict[int, tuple[str, ...] | None] = {}
    for item in items:
        leaf_id = item.get("LineupNodeId")
        item["OfficialModelName"] = nodes[leaf_id][5] if leaf_id in nodes else None  # 해당 노드의 값만 사용하며 조상 값을 상속하지 않습니다.
        trail, seen, current, base = [], set(), leaf_id, ()
        valid = current in nodes
        while valid and current is not None:
            if current in seen or len(trail) >= MAX_TREE_DEPTH or current not in nodes:
                valid = False
                break
            row = nodes[current]
            if row[3:5] != nodes[leaf_id][3:5] or not isinstance(row[2], str) or not row[2].strip():
                valid = False
                break
            if current in cache:
                base = cache[current]
                valid = base is not None and len(base) + len(trail) <= MAX_TREE_DEPTH
                break
            seen.add(current)
            trail.append(current)
            current = row[1]
        if valid:
            for node_id in reversed(trail):
                base = (*base, nodes[node_id][2])
                cache[node_id] = base
            path = cache.get(leaf_id, base)
            item["FullModelName"] = " / ".join(path)
        else:
            # Do not cache a failure caused by this leaf's total depth as a
            # failure of its otherwise valid ancestors.
            item["FullModelName"] = item.get("ModelName") or "-"
        item["DisplayModelName"] = item["OfficialModelName"] or item["FullModelName"] or item.get("ModelName") or "-"  # 기존 두 이름의 의미는 보존합니다.
    return items


def save_option(connection: Any, payload: Mapping[str, Any], actor: Mapping[str, Any], option_id=None) -> dict[str, Any]:
    """[역할] 옵션 생성·이름/스펙 수정을 검증하고 일반 사용자는 결재를 생성합니다.
    [의존성 관계] 호출자가 BEGIN IMMEDIATE, 감사, commit/rollback을 담당합니다.
    [변경 시 영향도] 승인 우회 및 중복·잘못된 옵션 참조를 방지합니다.
    """
    if not isinstance(payload, dict):
        raise LineupNodeError("JSON 객체를 입력해 주세요.")
    cursor = connection.cursor()
    before = None
    if option_id is not None:
        before = _editable_option(cursor, option_id)
        if actor.get("Role") != "admin":
            raise LineupNodeError("관리자만 옵션을 수정할 수 있습니다.", 403)
        if "lineup_node_id" in payload and _required_int(payload["lineup_node_id"], "노드") != before["lineup_node_id"]:
            raise LineupNodeError("옵션의 소속 노드는 변경할 수 없습니다.", 409)
    node_id = before["lineup_node_id"] if before else _required_int(payload.get("lineup_node_id"), "노드")
    node = _fetch_node(cursor, node_id)
    if not node:
        raise LineupNodeError("소속 모델 노드를 찾을 수 없습니다.", 404)
    if node["status"] != "APPROVED":
        raise LineupNodeError("승인된 노드에만 옵션을 등록·수정할 수 있습니다.", 409)
    name = payload.get("option_name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise LineupNodeError("옵션 이름은 1~100자로 입력해 주세요.")
    name = name.strip()
    specs = payload.get("specs", {})
    if not isinstance(specs, dict) or any(not isinstance(k, str) or not k.strip() or len(k) > 100 or
        not isinstance(v, (str, int, float, bool, type(None))) for k, v in specs.items()):
        raise LineupNodeError("스펙은 이름과 단일 값으로 이루어진 JSON 객체여야 합니다.")
    try:
        specs_json = json.dumps(specs, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise LineupNodeError("스펙에 올바른 JSON 값을 입력해 주세요.") from error
    if len(specs_json.encode("utf-8")) > 16384:
        raise LineupNodeError("옵션 스펙은 16KB 이하여야 합니다.")
    if cursor.execute("SELECT id FROM equipment_options WHERE lineup_node_id=? AND LOWER(option_name)=LOWER(?) AND id<>?",
                      (node_id, name, option_id or 0)).fetchone():
        raise LineupNodeError("같은 노드에 동일 이름의 옵션이 있습니다.", 409)
    actor_id = _required_int(actor.get("UserId"), "사용자")
    status = "APPROVED" if actor.get("Role") == "admin" else "PENDING"
    if before:
        cursor.execute("UPDATE equipment_options SET option_name=?, specs_json=? WHERE id=? AND status='APPROVED'",
                       (name, specs_json, option_id))
    else:
        cursor.execute("INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by) VALUES (?,?,?,?,?)",
                       (node_id, name, specs_json, status, actor_id))
        option_id = cursor.lastrowid
        if status == "PENDING":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            request_data = json.dumps({"type": "Equipment_Option", "option_id": option_id, "option_name": name,
                                      "lineup_node_id": node_id, "specs": specs}, ensure_ascii=False)
            cursor.execute("INSERT INTO approval_requests (RequesterId,RequestType,RequestDataJSON,Status,CreatedAt,UpdatedAt) VALUES (?,'Equipment_Option',?,'PENDING',?,?)",
                           (actor_id, request_data, now, now))
    return {"option_id": option_id, "lineup_node_id": node_id, "option_name": name, "specs": specs, "status": status, "before": before}


def _editable_option(cursor: Any, option_id: Any) -> dict[str, Any]:
    """Fetch an existing approved option; pending/rejected items stay in approvals."""
    option_id = _required_int(option_id, "옵션")
    cursor.execute("SELECT id, lineup_node_id, option_name, specs_json, status FROM equipment_options WHERE id=?", (option_id,))
    row = cursor.fetchone()
    if not row:
        raise LineupNodeError("옵션을 찾을 수 없습니다.", 404)
    result = dict(zip([item[0] for item in cursor.description], row))
    if result["status"] != "APPROVED":
        raise LineupNodeError("미승인 옵션은 전자결재함에서 처리해 주세요.", 409)
    return result


def delete_option(connection: Any, option_id: Any) -> dict[str, Any]:
    """[역할] 활성/임시저장 장비 참조가 모두 0인 승인 옵션만 삭제합니다.
    [의존성 관계] 호출자의 BEGIN IMMEDIATE 및 같은 transaction 감사 기록.
    [변경 시 영향도] 마지막 장비 삭제 뒤 남은 카탈로그를 명시적으로 정리합니다.
    """
    cursor = connection.cursor()
    before = _editable_option(cursor, option_id)
    count = cursor.execute("SELECT COUNT(*) FROM equipments WHERE option_id=?", (option_id,)).fetchone()[0]
    if count:
        raise LineupNodeError(f"활성 또는 임시저장 장비 {count}건이 사용 중이므로 삭제할 수 없습니다.", 409)
    cursor.execute("DELETE FROM equipment_options WHERE id=? AND status='APPROVED' AND NOT EXISTS (SELECT 1 FROM equipments WHERE option_id=?)", (option_id, option_id))
    if cursor.rowcount != 1:
        raise LineupNodeError("옵션 상태가 변경되었습니다. 새로고침 후 다시 시도해 주세요.", 409)
    return before
