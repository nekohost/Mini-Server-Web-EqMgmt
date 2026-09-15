"""[역할] 공통 신청 HTTP 경계. [의존성 관계] 앱 인증/CSRF/메뉴/감사 주입. [변경 시 영향도] 3종 신청서."""
from flask import Blueprint, jsonify, request, session  # 기존 Flask 경계를 사용합니다.
from utils.catalog_request_service import submit_catalog_request  # 서비스는 운영 DB를 직접 열지 않습니다.
from utils.lineup_node_service import LineupNodeError  # 기존 오류 계약을 공유합니다.

def build_catalog_request_blueprint(get_connection, login_required, csrf_required, check_permission, audit, logger):
    """[역할] 의존성을 주입합니다. [의존성 관계] app.py. [변경 시 영향도] 관리자 처리 API와는 별개입니다."""
    blueprint = Blueprint('catalog_requests', __name__)  # 기존 blueprint 이름과 겹치지 않습니다.
    @blueprint.post('/api/catalog_requests')  # 세 폼에 공통인 신규 URL입니다.
    @login_required  # 활성 로그인 검증은 앱의 기존 decorator가 맡습니다.
    @csrf_required  # 기존 CSRF 헤더 정책을 그대로 적용합니다.
    def create_request():
        """[역할] 접수·감사를 함께 확정합니다. [의존성 관계] session/메뉴 권한. [변경 시 영향도] 원자적 결재 생성."""
        if not any(check_permission(menu) for menu in ('my_approvals', 'my_equipment', 'public_equipment')):  # 허용된 진입점이 하나 이상 있어야 합니다.
            return jsonify(success=False, message='카탈로그 신청 접근 권한이 없습니다.'), 403  # 관리자 처리 권한은 부여하지 않습니다.
        if request.content_length is None or request.content_length > 8192:  # 작은 JSON 신청만 받습니다.
            return jsonify(success=False, message='신청 내용의 크기를 확인해 주세요.'), 413  # 과도한 본문은 파싱하지 않습니다.
        payload = request.get_json(silent=True)  # 타입 오류는 서비스가 안전하게 거부합니다.
        connection = get_connection()  # 요청별 기존 DB 연결을 사용합니다.
        try:  # 감사까지 성공해야 접수가 확정됩니다.
            connection.execute('BEGIN IMMEDIATE')  # 중복 검사/마스터/결재 쓰기를 직렬화합니다.
            result = submit_catalog_request(connection, payload, session.get('user') or {})  # actor를 본문에서 받지 않습니다.
            audit(connection, 'CREATE_CATALOG_REQUEST', result['target_id'], None, result, table=result['target_table'])  # 같은 writer로 감사 기록합니다.
            connection.commit()  # 마스터/노드·결재·감사를 한 번에 확정합니다.
            message = '등록되었습니다. 새로고침 후 선택할 수 있습니다.' if result['status'] == 'APPROVED' else '신청이 접수되었습니다. 관리자 승인 후 선택할 수 있습니다.'  # 두 결과를 구분합니다.
            return jsonify(success=True, **result, message=message), 201  # 성공 시에만 생성 응답입니다.
        except LineupNodeError as error:  # 예상된 사용자 오류입니다.
            connection.rollback()  # 미완료 쓰기를 모두 취소합니다.
            return jsonify(success=False, message=str(error)), error.status_code  # 내부 정보가 없는 도메인 오류만 전달합니다.
        except Exception as error:  # 감사/DB 장애는 정상 접수로 숨기지 않습니다.
            connection.rollback()  # 마스터만 남는 부분 성공을 방지합니다.
            logger.error('catalog-request failed reason=%s', type(error).__name__)  # 본문과 비밀을 로그에 넣지 않습니다.
            return jsonify(success=False, message='신청을 접수하지 못했습니다. 입력을 보존한 상태에서 다시 시도해 주세요.'), 500  # 안전한 메시지입니다.
        finally:  # 정상/오류 모두 연결을 반환합니다.
            connection.close()  # 기존 추적 연결의 수명주기를 지킵니다.
    return blueprint  # 앱이 명시적으로 등록해야 활성화됩니다.
