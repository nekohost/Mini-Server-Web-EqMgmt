# ==========================================
# [제안-019] 사용자 맞춤형 레이아웃 스킨(Skin) 시스템 적용 (Staging)
# ==========================================
# 기존의 `app.py` 내 `@app.route('/audit_logs')` 라우터를 
# 아래와 같이 분기 처리 로직으로 교체합니다.

from flask import render_template, session
import json

@app.route('/audit_logs')
@login_required
def audit_logs_page():
    if not check_menu_permission('audit_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
        
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. user_settings 테이블에서 설정 JSON 가져오기
    cursor.execute("SELECT PreferencesJSON FROM user_settings WHERE UserId = ?", (user['UserId'],))
    row = cursor.fetchone()
    conn.close()
    
    # 2. 설정 확인 후 템플릿 분기 (기본값은 'standard')
    skin = 'standard' # default
    if row and row['PreferencesJSON']:
        try:
            prefs = json.loads(row['PreferencesJSON'])
            skin = prefs.get('layout_skin', 'standard')
        except:
            pass
            
    # 3. 레이아웃(Skin) 값에 따른 템플릿 분기 서빙
    if skin == 'edge':
        return render_template('audit_logs_edge.html', user=user)
    else:
        return render_template('audit_logs_standard.html', user=user)

# ==========================================
# ※ /api/user_settings 연동 참고사항:
# 클라이언트 단(JS)에서 스킨 전환 버튼을 누르면,
# { "layout_skin": "edge" } 또는 { "layout_skin": "standard" } 
# 형태의 JSON을 /api/user_settings 에 POST로 전달합니다.
# 
# 기존의 /api/user_settings 엔드포인트 로직은 
# current_settings.update(data) 형태로 들어온 JSON의 key를 기존 설정에 병합(Merge)하므로, 
# 백엔드 API 코드는 단 한 줄도 수정할 필요 없이 그대로 활용 가능합니다!
# ==========================================
