"""Isolated in-memory tests for the lineup-node Staging service."""

import sqlite3
import unittest

from utils.lineup_node_service import (
    LineupNodeError,
    create_node,
    delete_node,
    get_admin_snapshot,
    update_node,
)


class LineupNodeServiceTests(unittest.TestCase):
    """[역할] 운영 DB 없이 노드 생성·이동·삭제 불변식을 회귀 검증합니다.

    [의존성 관계] sqlite3 :memory:와 lineup_node_service 후보를 사용합니다.
    [변경 시 영향도] Staging 후보가 운영 병합 가능한지 판단하는 근거가 됩니다.
    """

    def setUp(self) -> None:
        """[역할] 각 테스트마다 독립된 최소 3-Tier 스키마와 승인 마스터를 준비합니다.

        [의존성 관계] 서비스가 실제로 참조하는 테이블·컬럼 계약을 재현합니다.
        [변경 시 영향도] 테스트 간 상태 누수와 운영 DB 접근 가능성을 차단합니다.
        """

        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            """
            CREATE TABLE categories (
                CategoryId INTEGER PRIMARY KEY,
                Name TEXT NOT NULL,
                IsApproved INTEGER NOT NULL
            );
            CREATE TABLE manufacturers (
                ManufacturerId INTEGER PRIMARY KEY,
                Name TEXT NOT NULL,
                IsApproved INTEGER NOT NULL
            );
            CREATE TABLE lineup_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                category_id INTEGER NOT NULL,
                manufacturer_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                depth INTEGER NOT NULL,
                status TEXT NOT NULL,
                requested_by INTEGER,
                created_at TEXT
            );
            CREATE TABLE equipment_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lineup_node_id INTEGER NOT NULL,
                option_name TEXT NOT NULL
            );
            CREATE TABLE equipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                option_id INTEGER NOT NULL
            );
            CREATE TABLE approval_requests (
                RequestId INTEGER PRIMARY KEY AUTOINCREMENT,
                RequesterId INTEGER NOT NULL,
                RequestType TEXT NOT NULL,
                RequestDataJSON TEXT NOT NULL,
                Status TEXT NOT NULL,
                CreatedAt TEXT NOT NULL,
                UpdatedAt TEXT NOT NULL
            );
            INSERT INTO categories VALUES (1, '서버', 1), (2, '네트워크', 1), (3, '미승인', 0);
            INSERT INTO manufacturers VALUES (1, '제조사A', 1), (2, '제조사B', 1);
            """
        )
        self.admin = {"UserId": 1, "Role": "admin"}
        self.user = {"UserId": 2, "Role": "user"}

    def tearDown(self) -> None:
        """[역할] 테스트별 메모리 연결을 닫아 격리 상태를 종결합니다.

        [의존성 관계] unittest 수명주기와 sqlite3 연결을 사용합니다.
        [변경 시 영향도] 테스트 자원 누수 여부에 영향을 줍니다.
        """

        self.connection.close()

    def make_node(self, name: str, parent_id=None, category_id=1, manufacturer_id=1):
        """[역할] 테스트 가독성을 위해 관리자 승인 노드를 생성합니다.

        [의존성 관계] create_node의 실제 검증 경로를 우회하지 않고 재사용합니다.
        [변경 시 영향도] 다단 트리 픽스처의 생성 방식에 영향을 줍니다.
        """

        return create_node(
            self.connection,
            {
                "name": name,
                "parent_id": parent_id,
                "category_id": category_id,
                "manufacturer_id": manufacturer_id,
            },
            self.admin,
            now="2026-09-10 17:00:00",
        )

    def test_admin_creation_is_immediately_approved(self):
        """관리자 생성은 즉시 승인되고 실제 깊이를 저장해야 합니다."""

        root = self.make_node("PowerEdge")
        child = self.make_node("R760", root["node_id"])
        self.assertEqual("APPROVED", root["status"])
        self.assertEqual(2, child["depth"])

    def test_regular_user_creation_is_pending_with_approval_request(self):
        """일반 사용자 생성은 사용 가능한 노드가 아니라 승인 요청으로 남아야 합니다."""

        result = create_node(
            self.connection,
            {"name": "승인 대기 모델", "category_id": 1, "manufacturer_id": 1, "parent_id": None},
            self.user,
            now="2026-09-10 17:00:00",
        )
        request_row = self.connection.execute(
            "SELECT RequestType, Status FROM approval_requests WHERE RequesterId = 2"
        ).fetchone()
        self.assertEqual("PENDING", result["status"])
        self.assertEqual(("Lineup_Node", "PENDING"), request_row)

    def test_cross_root_child_is_rejected(self):
        """부모와 다른 카테고리 또는 제조사로 위장한 자식 생성을 막아야 합니다."""

        parent = self.make_node("Parent")
        with self.assertRaisesRegex(LineupNodeError, "조합이 요청과 일치"):
            self.make_node("Invalid Child", parent["node_id"], category_id=2)

    def test_duplicate_root_is_case_insensitive(self):
        """SQLite NULL 고유키의 빈틈과 대소문자 변형 중복을 서비스가 막아야 합니다."""

        self.make_node("ThinkPad")
        with self.assertRaisesRegex(LineupNodeError, "동일한 이름"):
            self.make_node("thinkpad")

    def test_move_updates_every_descendant_depth(self):
        """서브트리 이동 시 루트뿐 아니라 모든 자손 깊이가 함께 갱신되어야 합니다."""

        root_a = self.make_node("A")
        child = self.make_node("A-1", root_a["node_id"])
        grandchild = self.make_node("A-1-a", child["node_id"])
        root_b = self.make_node("B")
        target = self.make_node("B-1", root_b["node_id"])

        update_node(
            self.connection,
            child["node_id"],
            {"name": "A-1", "parent_id": target["node_id"]},
        )
        depths = dict(
            self.connection.execute(
                "SELECT id, depth FROM lineup_nodes WHERE id IN (?, ?)",
                (child["node_id"], grandchild["node_id"]),
            ).fetchall()
        )
        self.assertEqual(3, depths[child["node_id"]])
        self.assertEqual(4, depths[grandchild["node_id"]])

    def test_cycle_and_cross_root_move_are_rejected(self):
        """자손 밑 이동과 다른 루트 조합 이동을 모두 거부해야 합니다."""

        root = self.make_node("Root")
        child = self.make_node("Child", root["node_id"])
        foreign = self.make_node("Foreign", category_id=2)
        with self.assertRaisesRegex(LineupNodeError, "하위 노드"):
            update_node(self.connection, root["node_id"], {"parent_id": child["node_id"]})
        with self.assertRaisesRegex(LineupNodeError, "다른 카테고리"):
            update_node(self.connection, child["node_id"], {"parent_id": foreign["node_id"]})

    def test_creation_beyond_maximum_depth_is_rejected(self):
        """50단계 경로 아래에 51번째 노드를 추가할 수 없어야 합니다."""

        parent = self.make_node("Depth-1")
        for depth in range(2, 51):
            parent = self.make_node(f"Depth-{depth}", parent["node_id"])
        with self.assertRaisesRegex(LineupNodeError, "최대 깊이"):
            self.make_node("Depth-51", parent["node_id"])

    def test_delete_requires_existing_unused_leaf(self):
        """존재하지 않거나 자식·옵션이 연결된 노드는 삭제할 수 없어야 합니다."""

        root = self.make_node("Root")
        child = self.make_node("Child", root["node_id"])
        with self.assertRaisesRegex(LineupNodeError, "하위 노드"):
            delete_node(self.connection, root["node_id"])
        self.connection.execute(
            "INSERT INTO equipment_options (lineup_node_id, option_name) VALUES (?, '기본')",
            (child["node_id"],),
        )
        with self.assertRaisesRegex(LineupNodeError, "연결된 옵션"):
            delete_node(self.connection, child["node_id"])
        with self.assertRaisesRegex(LineupNodeError, "찾을 수 없습니다") as error:
            delete_node(self.connection, 9999)
        self.assertEqual(404, error.exception.status_code)

    def test_admin_snapshot_contains_usage_counts(self):
        """관리 화면 스냅샷은 상태와 삭제 판단에 필요한 연결 수를 제공해야 합니다."""

        node = self.make_node("Used")
        option_id = self.connection.execute(
            "INSERT INTO equipment_options (lineup_node_id, option_name) VALUES (?, '32GB')",
            (node["node_id"],),
        ).lastrowid
        self.connection.execute("INSERT INTO equipments (option_id) VALUES (?)", (option_id,))
        snapshot = get_admin_snapshot(self.connection)
        used = next(item for item in snapshot["nodes"] if item["id"] == node["node_id"])
        self.assertEqual(1, used["option_count"])
        self.assertEqual(1, used["equipment_count"])


    def test_fractional_and_boolean_ids_are_rejected(self):
        """[역할] 변조 ID 검증. [의존성 관계] create_node. [변경 시 영향도] 잘못된 부모 연결 차단."""
        for value in (1.5, True, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(LineupNodeError):
                    self.make_node("Invalid", category_id=value)

    def test_non_object_payload_is_rejected(self):
        """[역할] JSON 형식 검증. [의존성 관계] create/update. [변경 시 영향도] 안전한 400 응답."""
        node = self.make_node("Existing")
        for payload in (None, [], 1, "text"):
            with self.assertRaises(LineupNodeError):
                create_node(self.connection, payload, self.admin)
            with self.assertRaises(LineupNodeError):
                update_node(self.connection, node["node_id"], payload)

    def test_pending_nodes_require_approval_workflow(self):
        """[역할] 결재 이력 보존. [의존성 관계] update/delete. [변경 시 영향도] 승인 문서 정합성."""
        node = create_node(self.connection, {"name": "Pending", "category_id": 1, "manufacturer_id": 1}, self.user)
        with self.assertRaises(LineupNodeError):
            update_node(self.connection, node["node_id"], {"name": "Changed"})
        with self.assertRaises(LineupNodeError):
            delete_node(self.connection, node["node_id"])

    def test_failed_move_preserves_original_tree(self):
        """[역할] 실패 원자성 검증. [의존성 관계] update_node. [변경 시 영향도] 기존 계층 보존."""
        root = self.make_node("Root")
        child = self.make_node("Child", root["node_id"])
        before = self.connection.execute("SELECT * FROM lineup_nodes ORDER BY id").fetchall()
        with self.assertRaises(LineupNodeError):
            update_node(self.connection, root["node_id"], {"parent_id": child["node_id"]})
        self.assertEqual(before, self.connection.execute("SELECT * FROM lineup_nodes ORDER BY id").fetchall())


if __name__ == "__main__":
    unittest.main()
