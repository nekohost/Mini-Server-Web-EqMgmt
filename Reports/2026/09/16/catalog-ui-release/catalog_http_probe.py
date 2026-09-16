"""[역할] Linux 격리 Flask HTTP 검증. [의존성 관계] 기존 ReleaseApiTests 임시 DB. [변경 시 영향도] 운영 DB/계정 미사용."""
import json, os, sqlite3  # 결과와 메모리/임시 fixture를 사용합니다.
from test_release_api import ReleaseApiTests as Fixture  # 검토된 별도 DB/app 로더입니다.
assert os.name == 'posix'  # Linux에서만 실제 앱 fixture를 실행합니다.
Fixture.setUpClass(); case = Fixture(); checks = []  # 운영 환경이 아닌 합성 앱입니다.
try:  # 실패해도 fixture 환경을 정리합니다.
    case.setUp(); case.login('user'); client = case.client; url = '/api/catalog_requests'  # 합성 사용자 세션입니다.
    def expect(response, status, label):
        """[역할] HTTP 계약 검사. [의존성 관계] test_client. [변경 시 영향도] 실제 라우트/decorator 실행."""
        assert response.status_code == status, (label, response.status_code, response.get_data(as_text=True)[:300]); checks.append(label); return response.get_json()  # 실제 실패를 유지합니다.
    expect(case.module.app.test_client().post(url, json={'kind':'category','name':'NeverCreated'}), 401, 'anonymous-401')  # 로그인 우회 거부입니다.
    expect(client.post(url, json={'kind':'category','name':'NeverCreated'}), 403, 'missing-csrf-403')  # 실제 CSRF 검사입니다.
    expect(client.post(url, json=[], headers=case.headers), 400, 'invalid-json-400')  # 타입 오류를 안전하게 거부합니다.
    category = expect(client.post(url, json={'kind':'category','name':'DeployFixtureCategory'}, headers=case.headers), 201, 'category-pending')  # 장비와 무관한 신청입니다.
    assert category['status'] == 'PENDING' and category['request_id']  # 실제 결재 접수 번호입니다.
    own = expect(client.get('/api/my_approvals?status=PENDING'), 200, 'own-history'); assert category['request_id'] in [x['RequestId'] for x in own['data']]  # 본인 결재함 연결입니다.
    expect(client.post(url, json={'kind':'category','name':'DeployFixtureCategory'}, headers=case.headers), 409, 'duplicate-409')  # 중복 생성 차단입니다.
    manufacturer = expect(client.post(url, json={'kind':'manufacturer','name':'DeployFixtureMaker'}, headers=case.headers), 201, 'manufacturer-pending'); assert manufacturer['status']=='PENDING'  # 독립 제조사 신청입니다.
    node = expect(client.post(url, json={'kind':'node','name':'DeployFixtureNode','category_id':10001,'manufacturer_id':10001,'parent_id':10001}, headers=case.headers), 201, 'node-pending'); assert node['status']=='PENDING'  # 승인 부모 종속성입니다.
    expect(client.post(url, json={'kind':'node','name':'BadDependency','category_id':category['target_id'],'manufacturer_id':10001}, headers=case.headers), 409, 'pending-master-blocked')  # 대기 마스터 아래 노드 차단입니다.
    expect(client.post(url, json={'kind':'category','name':'Forged','Role':'admin'}, headers=case.headers), 400, 'actor-forgery-blocked')  # 사용자 권한은 본문에서 받지 않습니다.
    expect(client.post('/api/approvals/'+str(category['request_id'])+'/process', json={'action':'approve'}, headers=case.headers), 403, 'user-processing-blocked')  # 승인 권한을 확장하지 않습니다.
    case.login('admin'); approved = expect(client.post(url, json={'kind':'category','name':'DeployAdminCategory'}, headers=case.headers), 201, 'admin-immediate'); assert approved['status']=='APPROVED'  # 기존 관리자 정책입니다.
    with sqlite3.connect(case.module.DATABASE_PATH) as con:  # 실패를 주입하는 대상도 fixture뿐입니다.
        before = con.execute('SELECT COUNT(*) FROM approval_requests').fetchone()[0]  # 부분 결재 방지 기준입니다.
        con.execute("CREATE TRIGGER deploy_audit_fail BEFORE INSERT ON audit_logs WHEN NEW.Action='CREATE_CATALOG_REQUEST' BEGIN SELECT RAISE(ABORT,'fixture-only'); END")  # 실제 audit 경계에서 실패합니다.
    case.login('user'); expect(client.post(url, json={'kind':'category','name':'RollbackFixture'}, headers=case.headers), 500, 'audit-failure-500')  # 원자적 rollback입니다.
    with sqlite3.connect(case.module.DATABASE_PATH) as con:  # 실제 저장되지 않았는지 확인합니다.
        assert con.execute("SELECT COUNT(*) FROM categories WHERE Name='RollbackFixture'").fetchone()[0]==0  # 마스터만 남지 않습니다.
        assert con.execute('SELECT COUNT(*) FROM approval_requests').fetchone()[0]==before  # 결재만 남지 않습니다.
        con.execute('DROP TRIGGER deploy_audit_fail'); assert con.execute('PRAGMA foreign_key_check').fetchall()==[]  # fixture 내 무결성입니다.
    checks.append('atomic-rollback-and-fk'); case.login('admin')  # 관리자 전용 페이지도 임시 앱에서 렌더합니다.
    for route in ('/portal','/admin_center','/my_equipment','/public_equipment','/my_approvals'):  # 이번 관련 실제 Jinja 라우트입니다.
        response=client.get(route); assert response.status_code==200, (route,response.status_code); assert b'/static/js/catalog_requests.js' in response.data  # 공통 자산 연결입니다.
        checks.append('render'+route)  # 실제 렌더 성공입니다.
    print(json.dumps({'status':'pass','cases':len(checks),'checks':checks,'database_scope':'fresh temporary fixture only'}))  # 실제 운영 쓰기는 없습니다.
finally: Fixture.tearDownClass()  # 환경과 임시 DB를 정리합니다.
