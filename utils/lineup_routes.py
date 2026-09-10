"""Flask route adapter candidate for ``lineup_node_service``.

The production merge should replace the existing lineup-node CRUD handlers with
this blueprint contract and add the new admin snapshot endpoint.  This file is
kept in Staging and is not imported by the running application.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request, session

from .lineup_node_service import (
    LineupNodeError,
    create_node,
    delete_node,
    get_admin_snapshot,
    update_node,
)


def build_lineup_node_blueprint(
    get_connection: Callable[[], Any],
    login_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    admin_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    csrf_required: Callable[[Callable[..., Any]], Callable[..., Any]],
    audit_callback: Callable[[Any, str, int | None, Any, Any], None] | None = None,
    error_logger: Callable[[str], None] | None = None,
) -> Blueprint:
    """[역할] 운영 앱의 인증·DB·감사 의존성을 주입받아 노드 API Blueprint를 구성합니다.

    [의존성 관계] Flask, lineup_node_service, 운영 login/admin/csrf decorator를 사용합니다.
    [변경 시 영향도] 장비등록 노드 생성과 관리자 노드 CRUD API 계약에 영향을 줍니다.
    """

    blueprint = Blueprint("lineup_node_management_candidate", __name__)

    def record_audit(connection: Any, action: str, node_id: int | None, before: Any, after: Any) -> None:
        """[역할] 감사 콜백이 제공된 경우에만 노드 변경 이력을 전달합니다.

        [의존성 관계] 운영 병합 시 log_audit 호출을 감싼 callback을 주입합니다.
        [변경 시 영향도] 노드 변경의 보안 감사 추적성에 영향을 줍니다.
        """

        if audit_callback is not None:
            audit_callback(connection, action, node_id, before, after)

    def log_unexpected(operation: str, error: Exception) -> None:
        """[역할] 내부 예외는 서버 로그에만 남기고 응답에는 상세를 노출하지 않습니다.

        [의존성 관계] 운영 logger adapter를 선택적으로 사용합니다.
        [변경 시 영향도] 장애 진단 가능성과 정보 노출 경계에 영향을 줍니다.
        """

        if error_logger is not None:
            error_logger(f"[lineup-node:{operation}] {type(error).__name__}: {error}")

    @blueprint.get("/api/admin/lineup_nodes")
    @login_required
    @admin_required
    def admin_lineup_nodes_snapshot():
        """[역할] 관리자에게 PENDING을 포함한 전체 노드와 연결 사용량을 반환합니다.

        [의존성 관계] get_admin_snapshot, admin_required, 요청 단위 DB 연결을 사용합니다.
        [변경 시 영향도] 관리자 노드 관리 화면의 필터·트리·삭제 상태에 영향을 줍니다.
        """

        connection = get_connection()
        try:
            return jsonify({"success": True, **get_admin_snapshot(connection)})
        except Exception as error:  # 내부 정보는 로그에만 기록합니다.
            log_unexpected("snapshot", error)
            return jsonify({"success": False, "message": "노드 목록을 불러오지 못했습니다."}), 500
        finally:
            connection.close()

    @blueprint.post("/api/lineup_node")
    @login_required
    @csrf_required
    def create_lineup_node_route():
        """[역할] 관리자 즉시 승인 또는 일반 사용자 승인 요청으로 노드를 생성합니다.

        [의존성 관계] create_node, login_required, csrf_required, session user를 사용합니다.
        [변경 시 영향도] 장비등록 화면과 관리자 화면의 노드 추가에 영향을 줍니다.
        """

        connection = get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")  # 중복 검사와 변경을 직렬화합니다.
            result = create_node(connection, request.get_json(silent=True), session.get("user") or {})
            record_audit(connection, "CREATE_LINEUP_NODE", result["node_id"], None, result)
            connection.commit()
            message = (
                "신규 노드가 등록되었습니다."
                if result["status"] == "APPROVED"
                else "신규 노드 등록 신청이 완료되었습니다. 관리자 승인 후 사용할 수 있습니다."
            )
            return jsonify({"success": True, **result, "message": message}), 201
        except LineupNodeError as error:
            connection.rollback()
            return jsonify({"success": False, "message": str(error)}), error.status_code
        except Exception as error:
            connection.rollback()
            log_unexpected("create", error)
            return jsonify({"success": False, "message": "노드를 등록하지 못했습니다."}), 500
        finally:
            connection.close()

    @blueprint.put("/api/lineup_node/<int:node_id>")
    @login_required
    @admin_required
    @csrf_required
    def update_lineup_node_route(node_id: int):
        """[역할] 관리자가 노드 이름과 부모를 변경하고 서브트리 깊이를 보정합니다.

        [의존성 관계] update_node와 관리자·CSRF 보호를 사용합니다.
        [변경 시 영향도] 관리자 트리 편집과 장비 모델 경로에 영향을 줍니다.
        """

        connection = get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")  # 중복 검사와 변경을 직렬화합니다.
            result = update_node(connection, node_id, request.get_json(silent=True))
            record_audit(connection, "UPDATE_LINEUP_NODE", node_id, None, result)
            connection.commit()
            return jsonify({"success": True, **result, "message": "노드가 수정되었습니다."})
        except LineupNodeError as error:
            connection.rollback()
            return jsonify({"success": False, "message": str(error)}), error.status_code
        except Exception as error:
            connection.rollback()
            log_unexpected("update", error)
            return jsonify({"success": False, "message": "노드를 수정하지 못했습니다."}), 500
        finally:
            connection.close()

    @blueprint.delete("/api/lineup_node/<int:node_id>")
    @login_required
    @admin_required
    @csrf_required
    def delete_lineup_node_route(node_id: int):
        """[역할] 관리자가 연결 없는 말단 노드만 안전하게 삭제합니다.

        [의존성 관계] delete_node와 관리자·CSRF 보호를 사용합니다.
        [변경 시 영향도] 관리자 삭제 동작과 기존 카탈로그 참조 보존에 영향을 줍니다.
        """

        connection = get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")  # 중복 검사와 변경을 직렬화합니다.
            result = delete_node(connection, node_id)
            record_audit(connection, "DELETE_LINEUP_NODE", node_id, result, None)
            connection.commit()
            return jsonify({"success": True, **result, "message": "노드가 삭제되었습니다."})
        except LineupNodeError as error:
            connection.rollback()
            return jsonify({"success": False, "message": str(error)}), error.status_code
        except Exception as error:
            connection.rollback()
            log_unexpected("delete", error)
            return jsonify({"success": False, "message": "노드를 삭제하지 못했습니다."}), 500
        finally:
            connection.close()

    return blueprint
