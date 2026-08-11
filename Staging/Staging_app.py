import sys
import os
from flask import render_template, request, jsonify, session

# Parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import jinja2
from dotenv import load_dotenv

from app import app, get_db_connection, login_required

# Rule 7-3-2 (모의 소스코드 위치) 시정을 위해 Jinja2 Loader 오버라이딩
# Staging/ 디렉토리와 templates/ 디렉토리 모두에서 템플릿을 찾을 수 있도록 설정
my_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader(os.path.abspath(os.path.dirname(__file__)))
])
app.jinja_loader = my_loader

# ------------------------------------------
# Staging Routes
# ------------------------------------------

@app.route('/staging/dashboard', methods=['GET'])
@login_required
def staging_dashboard():
    """
    [역할] 카테고리/제조사별 통계 및 복합 검색(Staging) 대시보드 UI를 렌더링합니다.
    [의존성 관계] Staging_dashboard.html 템플릿 파일
    [변경 시 영향도] Staging 환경의 대시보드 화면 표출에 영향을 줍니다.
    """
    return render_template('Staging_dashboard.html', user=session['user'])

@app.route('/api/staging/dashboard/stats', methods=['GET'])
@login_required
def api_staging_dashboard_stats():
    """
    [역할] 대시보드 통계용(나의 장비, 총 장비, 카테고리/제조사 분포, 복합 조건 검색결과) JSON 데이터를 반환합니다.
    [의존성 관계] equipment, categories, manufacturers 테이블
    [변경 시 영향도] Staging_dashboard.html 내의 차트 및 테이블 렌더링(Ajax)에 영향을 줍니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 내 장비 수
    cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE UserId = ? AND (IsDraft = 0 OR IsDraft IS NULL)", (user['UserId'],))
    my_eq_count = cursor.fetchone()['count']
    
    # 2. 총 장비 수
    if user['Role'] == 'admin':
        cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE (IsDraft = 0 OR IsDraft IS NULL)")
        total_count = cursor.fetchone()['count']
    else:
        cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE (IsPublic = 1 OR UserId = ?) AND (IsDraft = 0 OR IsDraft IS NULL)", (user['UserId'],))
        total_count = cursor.fetchone()['count']
        
    # 권한별 기본 WHERE절 조건 (AND로 이어붙일 앞부분)
    base_where = "(e.IsDraft = 0 OR e.IsDraft IS NULL)"
    params_base = []
    if user['Role'] != 'admin':
        base_where += " AND (e.IsPublic = 1 OR e.UserId = ?)"
        params_base.append(user['UserId'])
        
    # 3. 카테고리별 통계
    cursor.execute(f'''
        SELECT COALESCE(c.NameKo, c.Name, e.Category, '미분류') as ResolvedCategory, COUNT(e.EquipmentId) as count 
        FROM equipment e
        LEFT JOIN categories c ON e.CategoryId = c.CategoryId
        WHERE {base_where}
        GROUP BY ResolvedCategory
    ''', params_base)
    categories = [{"category": row['ResolvedCategory'], "count": row['count']} for row in cursor.fetchall()]

    # 4. 제조사별 통계 (신규)
    cursor.execute(f'''
        SELECT COALESCE(m.NameKo, m.Name, e.Manufacturer, '미분류') as ResolvedManufacturer, COUNT(e.EquipmentId) as count 
        FROM equipment e
        LEFT JOIN manufacturers m ON e.ManufacturerId = m.ManufacturerId
        WHERE {base_where}
        GROUP BY ResolvedManufacturer
    ''', params_base)
    manufacturers = [{"manufacturer": row['ResolvedManufacturer'], "count": row['count']} for row in cursor.fetchall()]

    # 5. 복합 조건 검색 (카테고리 + 제조사 모두 선택 시)
    req_cat_id = request.args.get('category_id')
    req_man_id = request.args.get('manufacturer_id')
    
    combined_stats = None
    if req_cat_id and req_man_id:
        # 상태(Status)별 분포 쿼리
        status_query = f'''
            SELECT COALESCE(e.Status, '미지정') as status, COUNT(e.EquipmentId) as count
            FROM equipment e
            WHERE {base_where} AND e.CategoryId = ? AND e.ManufacturerId = ?
            GROUP BY e.Status
        '''
        cursor.execute(status_query, params_base + [req_cat_id, req_man_id])
        status_distribution = [{"status": row['status'], "count": row['count']} for row in cursor.fetchall()]

        # 조건 부합 장비 목록 쿼리
        list_query = f'''
            SELECT e.EquipmentId, e.Name, e.ModelName, COALESCE(e.Status, '미지정') as Status, e.PurchaseDate
            FROM equipment e
            WHERE {base_where} AND e.CategoryId = ? AND e.ManufacturerId = ?
            ORDER BY e.EquipmentId DESC
        '''
        cursor.execute(list_query, params_base + [req_cat_id, req_man_id])
        equipment_list = [dict(row) for row in cursor.fetchall()]
        
        combined_stats = {
            "status_distribution": status_distribution,
            "equipment_list": equipment_list
        }

    conn.close()
    
    return jsonify({
        "success": True,
        "data": {
            "my_equipments": my_eq_count,
            "total_equipments": total_count,
            "categories": categories,
            "manufacturers": manufacturers,
            "combined_stats": combined_stats
        }
    })

@app.route('/api/staging/master/options', methods=['GET'])
@login_required
def api_staging_master_options():
    """
    [역할] 카테고리와 제조사 목록을 제공하여 복합 조건 검색용 Select Box를 동적으로 채웁니다.
    [의존성 관계] categories, manufacturers 테이블
    [변경 시 영향도] Staging_dashboard.html의 select 태그 옵션 목록에 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CategoryId, COALESCE(NameKo, Name) as DisplayName FROM categories ORDER BY CategoryId")
    cats = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT ManufacturerId, COALESCE(NameKo, Name) as DisplayName FROM manufacturers ORDER BY ManufacturerId")
    mans = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        "success": True,
        "categories": cats,
        "manufacturers": mans
    })

if __name__ == '__main__':
    # Rule 4-5-2 시정: 환경변수를 통해 FLASK_DEBUG 제어
    load_dotenv()
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Run staging app on port 5001
    app.run(host='0.0.0.0', port=5001, debug=is_debug)
