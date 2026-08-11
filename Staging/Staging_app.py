import sys
import os
from flask import render_template, request, jsonify, session

# Parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db_connection, login_required

# ------------------------------------------
# Staging Routes
# ------------------------------------------

@app.route('/staging/dashboard', methods=['GET'])
@login_required
def staging_dashboard():
    return render_template('Staging_dashboard.html', user=session['user'])

@app.route('/api/staging/dashboard/stats', methods=['GET'])
@login_required
def api_staging_dashboard_stats():
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
    # 카테고리와 제조사 목록을 제공하여 select box를 채우기 위한 API
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
    # Run staging app on port 5001
    app.run(host='0.0.0.0', port=5001, debug=True)
