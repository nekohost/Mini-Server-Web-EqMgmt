"""Linux-only official model service regression; no production DB is opened."""

import os  # Windows에서는 동작 테스트를 실행하지 않습니다.
import unittest  # Linux 회귀 실행기를 사용합니다.
import test_proposal047_nodes as fixtures  # 기존 독립 메모리 fixture만 재사용합니다.
from utils.lineup_node_service import create_node, update_node, get_admin_snapshot, add_full_model_names, LineupNodeError  # 실제 후보 서비스의 계약을 검증합니다.


@unittest.skipIf(os.name == "nt", "Linux execution only")  # Windows 구동 제한을 유지합니다.
class OfficialModelServiceTests(unittest.TestCase):
    """[역할] 분류명/공식명/경로 계약을 검사합니다. [의존성 관계] 메모리 fixture. [변경 시 영향도] 노드·목록."""
    setUp = fixtures.LineupNodeServiceTests.setUp  # 테스트마다 새로운 DB를 준비합니다.
    tearDown = fixtures.LineupNodeServiceTests.tearDown  # 테스트별 DB를 반환합니다.
    make_node = fixtures.LineupNodeServiceTests.make_node  # 기존 관리자 생성 흐름을 사용합니다.

    def names(self, node_id, leaf="분류"):
        """[역할] 공통 조회를 호출합니다. [의존성 관계] add_full_model_names. [변경 시 영향도] API 공통 필드."""
        return add_full_model_names(self.connection, [{"LineupNodeId": node_id, "ModelName": leaf}])[0]  # 실제 API와 같은 키를 사용합니다.

    def test_create_read_update_omit_and_clear(self):
        """[역할] 입력 전체 수명을 확인합니다. [의존성 관계] 생성/수정/snapshot. [변경 시 영향도] UI 계약."""
        payload = {"name": "분류", "category_id": 1, "manufacturer_id": 1, "official_model_name": "  Beelink SER8  "}  # 앞뒤 공백은 정규화합니다.
        node = create_node(self.connection, payload, self.admin)  # 실제 관리자 경로입니다.
        node_id = node["node_id"]  # ID는 업데이트에도 유지합니다.
        self.assertEqual(node["official_model_name"], "Beelink SER8")  # 저장 정규화를 확인합니다.
        self.assertEqual(get_admin_snapshot(self.connection)["nodes"][0]["official_model_name"], "Beelink SER8")  # 조회 필드가 누락되지 않습니다.
        result = update_node(self.connection, node_id, {"name": "새 분류"})  # 공식명 키 생략은 유지입니다.
        self.assertEqual(result["official_model_name"], "Beelink SER8")  # 기존 값을 지우지 않습니다.
        self.assertEqual(result["before"]["name"], "분류")  # 감사 이전값도 보존합니다.
        for empty in ("", "   ", None):  # 명시적인 해제 표현을 전부 점검합니다.
            update_node(self.connection, node_id, {"official_model_name": "Product"})  # 이전 값을 재설정합니다.
            update_node(self.connection, node_id, {"official_model_name": empty})  # 명시 해제를 수행합니다.
            self.assertIsNone(self.names(node_id)["OfficialModelName"])  # NULL 저장을 확인합니다.
            self.assertEqual(self.names(node_id)["DisplayModelName"], "새 분류")  # 경로 표시로 복귀합니다.

    def test_parent_never_inherits_and_shared_node_uses_one_query(self):
        """[역할] 비상속·공유·쿼리 수를 확인합니다. [의존성 관계] 부모/자식. [변경 시 영향도] 오표시·N+1."""
        parent = self.make_node("시리즈")["node_id"]  # 분류용 조상입니다.
        child = self.make_node("8세대", parent)["node_id"]  # 별도 제품 노드입니다.
        update_node(self.connection, parent, {"official_model_name": "Parent Product"})  # 조상에만 이름을 줍니다.
        self.assertIsNone(self.names(child)["OfficialModelName"])  # 자식 제품에 상속하지 않습니다.
        update_node(self.connection, child, {"official_model_name": "Beelink SER8"})  # 해당 모델에 직접 지정합니다.
        statements = []  # 추가 SQL 수를 기록합니다.
        self.connection.set_trace_callback(statements.append)  # fixture 연결만 추적합니다.
        items = add_full_model_names(self.connection, [{"LineupNodeId": child, "ModelName": "8세대", "EquipmentId": number} for number in range(25)])  # 같은 노드의 여러 장비입니다.
        self.connection.set_trace_callback(None)  # 이후 SQL은 집계하지 않습니다.
        self.assertEqual(len(statements), 1)  # 장비별 SQL을 추가하지 않습니다.
        self.assertTrue(all(item["DisplayModelName"] == "Beelink SER8" and item["FullModelName"] == "시리즈 / 8세대" for item in items))  # 두 의미를 구분합니다.
        self.assertEqual(items[0]["ModelName"], "8세대")  # 기존 말단명 의미를 유지합니다.

    def test_regular_user_cannot_set_official_name(self):
        """[역할] 일반 사용자 승인 우회를 차단합니다. [의존성 관계] create_node. [변경 시 영향도] 403과 행 보존."""
        payload = {"name": "일반 요청", "category_id": 1, "manufacturer_id": 1}  # 기존 요청은 유효합니다.
        for value in ("Bypass", "", None):  # null도 관리자 전용 필드의 직접 지정입니다.
            with self.assertRaises(LineupNodeError) as caught:  # 어떤 행도 만들기 전에 실패해야 합니다.
                create_node(self.connection, {**payload, "official_model_name": value}, self.user)  # 변조 요청입니다.
            self.assertEqual(caught.exception.status_code, 403)  # 권한 오류로 구분합니다.
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM lineup_nodes").fetchone()[0], 0)  # 부분 생성이 없습니다.
        self.assertEqual(create_node(self.connection, payload, self.user)["status"], "PENDING")  # 기존 결재는 정상입니다.

    def test_invalid_types_length_controls_and_boundary(self):
        """[역할] 문자열 경계를 검사합니다. [의존성 관계] 공통 정규화. [변경 시 영향도] 저장 타입·XSS 원문."""
        node_id = self.make_node("분류")["node_id"]  # 변하지 않아야 할 기준 노드입니다.
        for value in (True, 123, [], {}, "x" * 201, "A\nB", "A\0B", "A\tB", "\x85"):  # 형식/크기/제어문자 오류입니다.
            with self.assertRaises(LineupNodeError):  # 모두 사용자 오류로 거부합니다.
                update_node(self.connection, node_id, {"official_model_name": value})  # DB에 쓰지 않습니다.
        self.assertIsNone(self.names(node_id)["OfficialModelName"])  # 실패 뒤 값이 남지 않습니다.
        for value in ("한" * 200, "<img src=x onerror=alert(1)>", "O'Reilly / Model"):  # HTML/인용부는 문자열이며 화면에서 escape합니다.
            update_node(self.connection, node_id, {"official_model_name": value})  # SQL 바인딩을 검증합니다.
            self.assertEqual(self.names(node_id)["DisplayModelName"], value)  # 원문 제품명은 변경하지 않습니다.

    def test_broken_path_and_missing_node_keep_fallback(self):
        """[역할] 손상 경로가 공식명을 상속하거나 전체 조회를 실패시키지 않습니다. [의존성 관계] 공통 조회. [변경 시 영향도] 예외 표시."""
        node_id = self.make_node("Leaf")["node_id"]  # 유효한 공식명을 지정합니다.
        update_node(self.connection, node_id, {"official_model_name": "Actual Model"})  # 자체 값만 보관합니다.
        self.connection.execute("UPDATE lineup_nodes SET parent_id=id WHERE id=?", (node_id,))  # 메모리 fixture의 순환을 주입합니다.
        item = self.names(node_id, "Leaf")  # 경로 오류는 말단 폴백입니다.
        self.assertEqual(item["FullModelName"], "Leaf")  # 기존 손상 처리 계약입니다.
        self.assertEqual(item["DisplayModelName"], "Actual Model")  # 해당 노드 자체 공식명은 유지합니다.
        self.assertEqual(self.names(None, None)["DisplayModelName"], "-")  # 끊긴 옵션 연결도 안전합니다.
        self.assertEqual(add_full_model_names(self.connection, []), [])  # 빈 결과에서 SQL을 실행하지 않습니다.
