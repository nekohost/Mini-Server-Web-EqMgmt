"""
[Staging] Staging_app_patch.py
- [제안-017] 감사 로그 고도화 백엔드 REST API 및 SQL Whitelist 검색 패치 시안
- [Gemini 3.1 Pro 리뷰 지침 1~5 완전 반영 버전]
- 실제 반영 시 app.py의 관련 엔드포인트로 병합(Merge)됩니다.
"""

from flask import request, jsonify, render_template, session
import sqlite3
import json
from functools import wraps

# 기존 app.py 공통 함수/데코레이터 가정 (Staging 테스트용 참조 명시)
# 실제 app.py 병합 시에는 app.py 내의 @login_required, check_menu_permission(), get_db_connection()을 그대로 사용합니다.

# SQL Injection 방지를 위한 감사로그 검색 허용 컬럼 Whitelist
ALLOWED_AUDIT_SEARCH_FIELDS = {
    'all': None, # 전체 검색
    'ActorLoginId': 'ActorLoginId',
    'ActorName': 'ActorName',
    'IpAddress': 'IpAddress',
    'Action': 'Action',
    'TargetId': 'TargetId',
    'Details': 'Details',
    'OldValue': 'OldValue',
    'NewValue': 'NewValue'
}

def get_db_connection():
    conn = sqlite3.connect('equipment.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'status': 'error', 'message': '로그인이 필요합니다.'}), 401
        return f(*args, **kwargs)
    return decorated_function

def check_menu_permission(menu_name):
    # app.py 내의 권한 검사 함수 호출을 모의함
    user = session.get('user', {})
    role = user.get('Role', 'user')
    if role == 'admin':
        return True
    return False

# -----------------------------------------------------------------------------
# 1. 감사 로그 페이지 렌더링 뷰 (GET /audit_logs)
# -----------------------------------------------------------------------------
@login_required
def staging_audit_logs_view():
    # [Pro 지침 1 반영] 하드코딩 role 체크 대신 표준 check_menu_permission 사용
    if not check_menu_permission('audit_logs'):
        return "접근 권한이 없습니다.", 403
        
    return render_template('Staging_audit_logs.html', user=session.get('user'))


# -----------------------------------------------------------------------------
# 2. 감사 로그 RESTful 비동기 조회 API (GET /api/audit_logs)
# -----------------------------------------------------------------------------
@login_required
def staging_api_audit_logs():
    # [Pro 지침 1, 2 반영] @login_required 적용 및 check_menu_permission 표준 검사
    if not check_menu_permission('audit_logs'):
        return jsonify({'status': 'error', 'message': '접근 권한이 없습니다.'}), 403

    try:
        # [Pro 지침 3 반영] 입력값 형변환 (Type Casting Error) 예외 처리 (Try-Except Fallback)
        try:
            page = int(request.args.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            per_page = int(request.args.get('per_page', 200))
        except (ValueError, TypeError):
            per_page = 200

        search_field = request.args.get('search_field', 'all')
        match_type = request.args.get('match_type', 'like') # 'exact' or 'like'
        keyword = request.args.get('keyword', '').strip()

        # [Pro 지침 5 반영] 로그인 세션의 유효성/관리자 권한 확인 후 상한선(limit)을 10,000개로 유연하게 대폭 상향
        user = session.get('user', {})
        max_limit = 10000 if user.get('Role') == 'admin' else 1000

        if per_page < 10:
            per_page = 10
        elif per_page > max_limit:
            per_page = max_limit

        offset = (page - 1) * per_page

        # 3. Dynamic SQL 및 Whitelist 검증
        where_clauses = []
        params = []

        if keyword:
            if search_field == 'all':
                # [Pro 지침 4 반영] 전체 검색 시 OldValue, NewValue JSON 변경 이력 포함
                if match_type == 'exact':
                    where_clauses.append("(ActorLoginId = ? OR ActorName = ? OR IpAddress = ? OR Action = ? OR TargetId = ? OR Details = ? OR OldValue = ? OR NewValue = ?)")
                    params.extend([keyword] * 8)
                else:
                    like_kw = f"%{keyword}%"
                    where_clauses.append("(ActorLoginId LIKE ? OR ActorName LIKE ? OR IpAddress LIKE ? OR Action LIKE ? OR TargetId LIKE ? OR Details LIKE ? OR OldValue LIKE ? OR NewValue LIKE ?)")
                    params.extend([like_kw] * 8)
            elif search_field in ALLOWED_AUDIT_SEARCH_FIELDS and ALLOWED_AUDIT_SEARCH_FIELDS[search_field]:
                column_name = ALLOWED_AUDIT_SEARCH_FIELDS[search_field]
                if match_type == 'exact':
                    where_clauses.append(f"{column_name} = ?")
                    params.append(keyword)
                else:
                    where_clauses.append(f"{column_name} LIKE ?")
                    params.append(f"%{keyword}%")
            else:
                return jsonify({'status': 'error', 'message': '유효하지 않은 검색 컬럼입니다.'}), 400

        where_stmt = ""
        if where_clauses:
            where_stmt = "WHERE " + " AND ".join(where_clauses)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 4. 전체 카운트 쿼리 (페이징 계산용)
        count_query = f"SELECT COUNT(*) FROM audit_logs {where_stmt}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # 5. 데이터 목록 쿼리 (LIMIT & OFFSET)
        data_query = f"""
            SELECT AuditId, ActorId, ActorLoginId, ActorName, Action, TargetId, IpAddress, OldValue, NewValue, Details, CreatedAt
            FROM audit_logs
            {where_stmt}
            ORDER BY AuditId DESC
            LIMIT ? OFFSET ?
        """
        data_params = params + [per_page, offset]
        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()
        conn.close()

        # Data JSON 변환
        logs = []
        for r in rows:
            logs.append({
                'AuditId': r['AuditId'],
                'ActorId': r['ActorId'],
                'ActorLoginId': r['ActorLoginId'],
                'ActorName': r['ActorName'],
                'Action': r['Action'],
                'TargetId': r['TargetId'],
                'IpAddress': r['IpAddress'],
                'OldValue': r['OldValue'],
                'NewValue': r['NewValue'],
                'Details': r['Details'],
                'CreatedAt': r['CreatedAt']
            })

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        return jsonify({
            'status': 'success',
            'data': logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'서버 오류가 발생했습니다: {str(e)}'}), 500
