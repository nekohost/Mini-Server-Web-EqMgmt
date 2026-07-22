# ==========================================
# 1. 필요한 외부 라이브러리 불러오기
# ==========================================
from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

# ==========================================
# 2. DB 공통 모듈 (모든 DB 관련 함수가 이 모듈에 의존함)
# ==========================================

def get_db_connection():
    """
    [역할] DB 연결 객체를 생성하고 결과를 Dict(사전) 형태로 반환하도록 설정하는 공통 함수
    
    [의존성 관계]
    - 의존하는 대상: 'equipment.db' 파일
    - 이 함수에 의존하는 대상: init_db(), get_equipment(), add_equipment(), delete_equipment()
    
    [변경 시 영향도]
    - 만약 DB 파일명이 바뀌거나, PostgreSQL/MSSQL 등 다른 DB로 교체될 경우
      오직 이 함수 내부의 sqlite3.connect() 부분만 수정하면 됩니다.
    """
    conn = sqlite3.connect('equipment.db')
    
    # row_factory를 sqlite3.Row로 설정하면 DB 조회 결과가 (튜플)이 아닌 {키: 값} 형태로 반환됩니다.
    # ★ 이 설정 덕분에 DB에 칼럼이 추가되어도 파이썬의 조회 코드를 고칠 필요가 없어집니다!
    conn.row_factory = sqlite3.Row 
    return conn


def init_db():
    """
    [역할] 테이블 구조를 초기화 및 관리하는 함수
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection()
    - 이 함수에 의존하는 대상: 서버 스타트업 로직
    
    [★ DB 칼럼 확장 시 수정 지침]
    - 새로운 칼럼(예: 가격 'price', 보증기간 'warranty_date' 등)을 추가하고 싶다면
      아래 CREATE TABLE 구문 안에 칼럼을 추가하세요. (예: price INTEGER, warranty_date TEXT)
    - 이미 만들어진 DB 파일이 있다면, 칼럼 추가 후 'equipment.db' 파일을 삭제하고
      서버를 재시작해야 새 테이블 구조가 적용됩니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            manufacturer TEXT,
            model_name TEXT,
            purchase_date TEXT,
            serial_number TEXT,
            memo TEXT
            /* ★ 칼럼 추가 시 여기에 작성 (예: price INTEGER, location TEXT) */
        )
    ''')
    conn.commit()
    conn.close()

# 서버 실행 시 DB 준비
init_db()


# ==========================================
# 3. 화면 제공 라우터
# ==========================================

@app.route('/')
def index():
    """
    [역할] 메인 HTML 화면 출력
    [의존성 관계] templates/index.html 파일에 의존함
    """
    return render_template('index.html')


# ==========================================
# 4. RESTful API 모듈 (각 기능이 철저히 분리됨)
# ==========================================

# ------------------------------------------
# [기능 A] 장비 목록 전체 조회 API
# ------------------------------------------
@app.route('/api/equipment', methods=['GET'])
def get_equipment():
    """
    [역할] DB의 모든 장비 데이터를 JSON 배열로 반환
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블
    - 이 API에 의존하는 대상: 프론트엔드(index.html)의 fetchEquipment() 자바스크립트 함수
    
    [★ 칼럼 확장 시 영향도]
    - row_factory = sqlite3.Row 덕분에 DB 칼럼이 추가되어도 이 파이썬 함수는 수정할 필요가 없습니다.
    - 단, 프론트엔드(index.html)의 fetchEquipment()에서 새 칼럼을 화면에 그려주는 코드는 추가해야 합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipment ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    # dict(row)를 통해 DB 행 데이터를 { "칼럼명": "값" } 형태의 파이썬 사전으로 자동 변환
    equipment_list = [dict(row) for row in rows]
    return jsonify(equipment_list)


# ------------------------------------------
# [기능 B] 신규 장비 등록 API
# ------------------------------------------
@app.route('/api/equipment', methods=['POST'])
def add_equipment():
    """
    [역할] 클라이언트가 보낸 JSON 데이터를 받아 DB에 저장
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블
    - 이 API에 의존하는 대상: 프론트엔드(index.html)의 등록 폼 이벤트 제출 로직
    
    [★ DB 칼럼 추가 시 수정 위치]
    1. 아래 INSERT INTO equipment (...) 구문 안에 새 칼럼명을 추가해야 합니다.
    2. VALUES (?, ?, ...) 에 물음표 하나를 추가하고,
    3. data.get('새칼럼명')을 튜플 목록 마지막에 추가해야 합니다.
    4. 동시에 프론트엔드(index.html)의 payload 객체에도 '새칼럼명'을 보내도록 수정해야 합니다.
    """
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 동적 처리를 하지 않고 SQL 표준 안전성을 위해 동적 바인딩 유지
    cursor.execute('''
        INSERT INTO equipment (name, category, manufacturer, model_name, purchase_date, serial_number, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('name'), 
        data.get('category'), 
        data.get('manufacturer'), 
        data.get('model_name'), 
        data.get('purchase_date'), 
        data.get('serial_number'), 
        data.get('memo')
        # ★ 칼럼 추가 시 data.get('새칼럼명') 추가 필요
    ))
    
    conn.commit()
    conn.close()
    return jsonify({"message": "성공적으로 등록되었습니다!"})


# ------------------------------------------
# [기능 C] 기존 장비 삭제 API
# ------------------------------------------
@app.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
def delete_equipment(eq_id):
    """
    [역할] ID를 받아 해당 장비 삭제
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블의 'id' PK 칼럼
    - 이 API에 의존하는 대상: 프론트엔드(index.html)의 deleteEquipment(id) 자바스크립트 함수
    
    [★ 칼럼 확장 시 영향도]
    - 칼럼이 추가되거나 변경되어도 이 삭제 기능은 'id' 기준이므로 전혀 영향받지 않습니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM equipment WHERE id = ?", (eq_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "삭제되었습니다."})


# ==========================================
# 5. 서버 가동
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)