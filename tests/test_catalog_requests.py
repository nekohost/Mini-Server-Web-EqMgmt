"""독립 카탈로그 신청 서비스의 메모리 DB 회귀 테스트입니다."""
import sqlite3  # 운영 DB 대신 메모리 SQLite를 사용합니다.
import unittest  # 표준 테스트 러너만 사용합니다.

from utils.catalog_request_service import submit_catalog_request  # 실제 운영 후보 서비스를 검증합니다.
from utils.lineup_node_service import LineupNodeError  # 기존 노드 도메인 오류 계약을 재사용합니다.


class CatalogRequestTests(unittest.TestCase):
    """[역할] 카테고리·제조사·노드 신청 불변식을 검증합니다.

    [의존성 관계] catalog_request_service와 lineup_node_service의 최소 스키마를 재현합니다.
    [변경 시 영향도] 결재 타입·권한·중복·노드 종속성 회귀를 탐지합니다.
    """

    def setUp(self):
        """[역할] 각 테스트에 독립된 메모리 DB와 사용자 역할을 준비합니다.

        [의존성 관계] 서비스가 실제 참조하는 여섯 테이블만 생성합니다.
        [변경 시 영향도] 운영 DB 접근과 테스트 간 상태 누수를 차단합니다.
        """
        self.db = sqlite3.connect(":memory:")  # 디스크 파일을 만들지 않습니다.
        self.db.executescript("""
            CREATE TABLE categories (CategoryId INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT NOT NULL, IsApproved INTEGER NOT NULL, CreatedAt TEXT);
            CREATE TABLE manufacturers (ManufacturerId INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT NOT NULL, IsApproved INTEGER NOT NULL, CreatedAt TEXT);
            CREATE TABLE lineup_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER, category_id INTEGER NOT NULL, manufacturer_id INTEGER NOT NULL, name TEXT NOT NULL, depth INTEGER NOT NULL, status TEXT NOT NULL, requested_by INTEGER, created_at TEXT, official_model_name TEXT);
            CREATE TABLE equipment_options (id INTEGER PRIMARY KEY AUTOINCREMENT, lineup_node_id INTEGER NOT NULL, option_name TEXT NOT NULL, specs_json TEXT DEFAULT '{}', status TEXT DEFAULT 'APPROVED', requested_by INTEGER, created_at TEXT);
            CREATE TABLE equipments (id INTEGER PRIMARY KEY AUTOINCREMENT, option_id INTEGER NOT NULL, is_draft INTEGER DEFAULT 0);
            CREATE TABLE approval_requests (RequestId INTEGER PRIMARY KEY AUTOINCREMENT, RequesterId INTEGER NOT NULL, RequestType TEXT NOT NULL, RequestDataJSON TEXT NOT NULL, Status TEXT NOT NULL, CreatedAt TEXT NOT NULL, UpdatedAt TEXT NOT NULL);
            INSERT INTO categories (Name,IsApproved) VALUES ('서버',1),('미승인',0);
            INSERT INTO manufacturers (Name,IsApproved) VALUES ('제조사A',1),('제조사B',1);
        """)  # 기존 서비스에 필요한 최소 컬럼 계약입니다.
        self.db.commit()  # 각 테스트가 명시적 transaction을 시작할 수 있게 합니다.
        self.user = {"UserId": 2, "Role": "user"}  # 일반 사용자 신청자입니다.
        self.admin = {"UserId": 1, "Role": "admin"}  # 기존 즉시 승인 정책 검증용 관리자입니다.

    def tearDown(self):
        """[역할] 테스트 DB를 닫습니다.

        [의존성 관계] unittest 수명주기입니다.
        [변경 시 영향도] 파일 핸들 및 테스트 자원 누수를 방지합니다.
        """
        self.db.close()  # 메모리 DB를 폐기합니다.

    def submit(self, kind="category", name="새 항목", actor=None, **extra):
        """[역할] 실제 서비스 함수를 간결하게 호출합니다.

        [의존성 관계] submit_catalog_request의 전체 검증 경로를 사용합니다.
        [변경 시 영향도] 테스트가 서비스 검증을 우회하지 않게 합니다.
        """
        return submit_catalog_request(self.db, {"kind": kind, "name": name, **extra}, actor or self.user)  # 서버 actor를 별도 전달합니다.

    def test_category_and_manufacturer_create_existing_request_types(self):
        """일반 사용자 두 마스터 신청은 기존 결재 타입과 PENDING 상태를 유지해야 합니다."""
        category = self.submit("category", "새 카테고리")  # 카테고리 독립 신청입니다.
        manufacturer = self.submit("manufacturer", "새 제조사")  # 제조사 독립 신청입니다.
        rows = self.db.execute("SELECT RequestType,Status FROM approval_requests ORDER BY RequestId").fetchall()  # 저장된 결재 계약을 읽습니다.
        self.assertEqual(rows, [("ADD_CATEGORY", "PENDING"), ("ADD_MANUFACTURER", "PENDING")])  # 기존 처리기가 인식하는 타입입니다.
        self.assertEqual(category["status"], "PENDING")  # 일반 사용자는 즉시 승인되지 않습니다.
        self.assertEqual(manufacturer["status"], "PENDING")  # 제조사도 동일합니다.

    def test_admin_master_registration_is_immediate_without_request(self):
        """관리자 마스터 등록은 기존 정책대로 즉시 승인되고 대기 결재를 만들지 않아야 합니다."""
        result = self.submit("category", "관리자 카테고리", self.admin)  # 신뢰된 관리자 actor를 전달합니다.
        self.assertEqual(result["status"], "APPROVED")  # 즉시 사용 가능 상태입니다.
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0], 0)  # 허위 대기 이력을 만들지 않습니다.

    def test_node_requires_approved_same_root_and_reuses_lineup_contract(self):
        """노드는 승인된 카테고리·제조사 조합에만 종속되어야 합니다."""
        root = self.submit("node", "루트", self.admin, category_id=1, manufacturer_id=1, parent_id=None)  # 관리자 승인 루트입니다.
        child = self.submit("node", "자식", self.user, category_id=1, manufacturer_id=1, parent_id=root["node_id"])  # 같은 조합의 일반 사용자 요청입니다.
        self.assertEqual(child["status"], "PENDING")  # 노드 결재가 필요합니다.
        with self.assertRaises(LineupNodeError):  # 다른 카테고리로 부모를 위장할 수 없습니다.
            self.submit("node", "잘못된 자식", self.user, category_id=2, manufacturer_id=1, parent_id=root["node_id"])  # 미승인·다른 조합입니다.

    def test_duplicate_forged_fields_and_invalid_actor_are_rejected(self):
        """중복 항목과 클라이언트 권한 위조 및 잘못된 actor를 거부해야 합니다."""
        self.submit("category", "중복")  # 첫 요청은 정상입니다.
        with self.assertRaises(LineupNodeError):  # 대소문자·공백 중복을 다시 만들지 않습니다.
            self.submit("category", " 중복 ")  # 동일 이름 재요청입니다.
        with self.assertRaises(LineupNodeError):  # RequesterId는 본문에서 받을 수 없습니다.
            submit_catalog_request(self.db, {"kind": "category", "name": "위조", "RequesterId": 999}, self.user)  # 위조 필드입니다.
        with self.assertRaises(LineupNodeError):  # 세션 actor가 없으면 쓰기를 시작하지 않습니다.
            submit_catalog_request(self.db, {"kind": "category", "name": "무세션"}, {})  # 잘못된 서버 actor입니다.

    def test_caller_rollback_removes_master_and_approval_together(self):
        """감사 등 상위 route 실패 시 마스터와 결재가 같은 transaction에서 함께 롤백되어야 합니다."""
        before = self.db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]  # 변경 전 행 수입니다.
        self.db.execute("BEGIN IMMEDIATE")  # 실제 route의 writer transaction을 모의합니다.
        self.submit("category", "롤백 대상")  # 마스터와 결재가 같은 연결에 쓰입니다.
        self.db.rollback()  # 감사 실패 등 상위 예외를 모의합니다.
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM categories").fetchone()[0], before)  # 마스터가 남지 않습니다.
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0], 0)  # 결재만 남지도 않습니다.


if __name__ == "__main__":
    unittest.main()  # 단독 실행에서도 표준 unittest 결과를 반환합니다.
