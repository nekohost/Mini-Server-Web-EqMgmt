"""Linux-only official-model migration and backup compatibility regressions."""

import os  # Windows에서는 실제 DB fixture를 실행하지 않습니다.
import sqlite3  # 독립 사본에서만 SQL을 실행합니다.
import unittest  # 동일한 프로젝트 테스트 실행기를 사용합니다.
from unittest.mock import patch  # 실패 지점을 명시적으로 주입합니다.
import test_database_contract as fixtures  # 운영 파일을 열지 않는 앱 fixture를 재사용합니다.
from utils.database_contract import connect_database, migrate_contract, rollback_contract, rollback_official_models, assert_contract_version, OFFICIAL_MODEL_MIGRATION, schema_contract  # 실제 후보 migration을 검증합니다.


@unittest.skipIf(os.name == "nt", "Linux execution only")  # 로컬 앱 실행을 차단합니다.
class OfficialModelMigrationTests(unittest.TestCase):
    """[역할] 버전 전이/복구를 검증합니다. [의존성 관계] 격리 앱 DB. [변경 시 영향도] 백업·기동."""
    setUpClass = classmethod(fixtures.DatabaseContractTests.setUpClass.__func__)  # 이 클래스 전용 임시 앱을 만듭니다.
    tearDownClass = classmethod(fixtures.DatabaseContractTests.tearDownClass.__func__)  # 전용 자원을 반환합니다.
    setUp = fixtures.DatabaseContractTests.setUp  # 업무 행의 기준 fixture를 재사용합니다.

    def copy_at(self, version):
        """[역할] 원하는 이전 버전의 독립 사본을 준비합니다. [의존성 관계] 안전 down. [변경 시 영향도] 원본 fixture 보존."""
        path = self.root / (self._testMethodName + f"-v{version}.db")  # 테스트 이름·버전별로 파일을 격리합니다.
        copy = connect_database(path)  # 임시 디렉터리 안의 새 파일입니다.
        self.connection.backup(copy)  # fixture 기준선을 복제합니다.
        copy.close()  # down에 잠금을 남기지 않습니다.
        if version < 2:  # 기존 값은 모두 NULL이라 안전 down이 가능합니다.
            rollback_official_models(path, self.root / "down-backups")  # 먼저 v2→1입니다.
        if version == 0:  # 0→2 전체 업그레이드를 재현합니다.
            rollback_contract(path, self.root / "down-backups")  # 기존 v1 인덱스만 제거합니다.
        return path  # 운영 DB 경로는 한 번도 전달하지 않습니다.

    def rows(self, path):
        """[역할] 기존 업무값과 ID를 고정 조회합니다. [의존성 관계] 명시 컬럼. [변경 시 영향도] additive 비교."""
        copy = connect_database(path)  # 임시 사본만 엽니다.
        try:  # 추가 컬럼이 tuple 길이를 바꾸는 오판을 피합니다.
            return (copy.execute("SELECT * FROM equipments ORDER BY id").fetchall(), copy.execute("SELECT id,parent_id,name,category_id,manufacturer_id,depth FROM lineup_nodes ORDER BY id").fetchall())  # 원래 값만 비교합니다.
        finally:  # 연결 수명을 제한합니다.
            copy.close()  # 사본 잠금을 정리합니다.

    def test_v1_upgrade_preserves_rows_and_is_idempotent(self):
        """[역할] v1→2·백업·반복을 검사합니다. [의존성 관계] migration. [변경 시 영향도] 기존 행 보존."""
        path = self.copy_at(1)  # 기존 서비스 버전입니다.
        before = self.rows(path)  # 원래 ID/값입니다.
        result = migrate_contract(path, self.root / "up-backups")  # 실제 후보를 호출합니다.
        self.assertEqual(result["version"], 2)  # 버전은 이력과 함께 승격됩니다.
        self.assertEqual(self.rows(path), before)  # 기존 행을 보존합니다.
        backup = connect_database(result["backup_path"])  # migration 이전 사본입니다.
        self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 1)  # 복구 기준선이 올바릅니다.
        backup.close()  # 잠금을 반환합니다.
        self.assertFalse(migrate_contract(path, self.root / "up-backups")["applied"])  # 재실행이 중복 ALTER하지 않습니다.
        self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)  # fresh/upgraded 스키마가 동등합니다.
        self.module.validate_database_compatibility(self.module.DATABASE_PATH, path)  # 반대 방향도 검사합니다.

    def test_v0_upgrade_is_single_transaction(self):
        """[역할] v1 인덱스와 새 컬럼의 통합 경로를 검사합니다. [의존성 관계] 이전 무버전 사본. [변경 시 영향도] 신규 설치."""
        path = self.copy_at(0)  # 이전 두 단계를 제거한 사본입니다.
        before = self.rows(path)  # 행 기준선을 보관합니다.
        self.assertEqual(migrate_contract(path, self.root / "up-backups")["version"], 2)  # 0→2를 한 번에 적용합니다.
        self.assertEqual(self.rows(path), before)  # 데이터는 변경되지 않습니다.

    def test_failure_after_alter_rolls_back_column_history_and_version(self):
        """[역할] ALTER 이후 실패도 원복하는지 확인합니다. [의존성 관계] 무결성 주입. [변경 시 영향도] 원자성."""
        for version in (0, 1):  # 인덱스까지 추가되는 v0와 컬럼만 추가되는 v1을 함께 검사합니다.
            path = self.copy_at(version)  # ALTER 전 기준선입니다.
            with patch("utils.database_contract.assert_official_model_schema", side_effect=ValueError("fixture-after-alter")):  # 적용 후 검증 지점에서 실패합니다.
                with self.assertRaisesRegex(ValueError, "fixture-after-alter"):  # 예외를 숨기지 않습니다.
                    migrate_contract(path, self.root / "up-backups")  # commit 전에 실패합니다.
            copy = connect_database(path)  # 실패 후 상태를 다시 엽니다.
            self.assertEqual(assert_contract_version(copy), version)  # 컬럼·두 이력·인덱스·버전이 함께 복귀합니다.
            copy.close()  # 파일 핸들을 반환합니다.

    def test_backup_failure_prevents_alter(self):
        """[역할] 백업 실패 후 변경을 금지합니다. [의존성 관계] private_snapshot. [변경 시 영향도] 선행 복구 조건."""
        path = self.copy_at(1)  # 변경 전 사본입니다.
        with patch("utils.database_contract.private_snapshot", side_effect=OSError("fixture-backup")):  # 사본 생성 실패입니다.
            with self.assertRaises(OSError):  # 저장 공간 오류를 상위로 전달합니다.
                migrate_contract(path, self.root / "up-backups")  # ALTER를 수행하면 안 됩니다.
        copy = connect_database(path)  # 원본 상태를 확인합니다.
        self.assertEqual(assert_contract_version(copy), 1)  # 컬럼/버전/이력 모두 유지됩니다.
        copy.close()  # 핸들을 반환합니다.

    def test_old_backup_rejected_without_mutation(self):
        """[역할] v1 백업의 자동 승격·복원을 막습니다. [의존성 관계] 읽기 전용 validator. [변경 시 영향도] 원본 업로드 보존."""
        path = self.copy_at(1)  # 구버전 백업을 재현합니다.
        before = path.read_bytes()  # fixture 파일의 원형입니다.
        with self.assertRaisesRegex(ValueError, "버전"):  # 명확한 호환성 오류여야 합니다.
            self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)  # 운영 호환성 함수입니다.
        self.assertEqual(path.read_bytes(), before)  # 원본을 자동 변환하지 않습니다.

    def test_missing_v2_history_is_rejected_by_migration_and_restore(self):
        """[역할] 표면 스키마가 같은 부분 이력을 거부합니다. [의존성 관계] 이력·정수 교차 검사. [변경 시 영향도] 거짓 성공."""
        path = self.copy_at(2)  # 정상 v2 사본입니다.
        copy = connect_database(path)  # 부분 이력을 의도적으로 만듭니다.
        copy.execute("DELETE FROM sys_migrations WHERE MigrationName=?", (OFFICIAL_MODEL_MIGRATION,))  # 해당 이력 하나만 제거합니다.
        copy.commit()  # 고장 fixture를 확정합니다.
        copy.close()  # 검사 함수가 독립 연결로 확인합니다.
        with self.assertRaises(ValueError):  # 이력 없는 컬럼을 채택하지 않습니다.
            migrate_contract(path, self.root / "up-backups")  # 자동 복구를 하지 않습니다.
        with self.assertRaisesRegex(ValueError, "버전"):  # 백업 복원도 거부합니다.
            self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)  # 실제 validator를 통과하지 못합니다.

    def test_populated_down_is_blocked_and_null_down_up_keeps_rows(self):
        """[역할] 새 값 유실을 방지합니다. [의존성 관계] 2→1 gate. [변경 시 영향도] rollback 절차."""
        path = self.copy_at(2)  # 공식명이 없는 v2 사본입니다.
        copy = connect_database(path)  # 새 값을 저장합니다.
        copy.execute("UPDATE lineup_nodes SET official_model_name='Beelink SER8'")  # 신규 데이터입니다.
        copy.commit()  # 독립된 변경을 확정합니다.
        copy.close()  # down이 직접 상태를 검사합니다.
        with self.assertRaisesRegex(ValueError, "lose data"):  # 유실 가능성을 명시합니다.
            rollback_official_models(path, self.root / "down-backups")  # 자동 삭제하지 않습니다.
        copy = connect_database(path)  # 거부 후 값을 확인합니다.
        self.assertEqual(copy.execute("SELECT official_model_name FROM lineup_nodes").fetchone()[0], "Beelink SER8")  # 그대로 보존됩니다.
        copy.execute("UPDATE lineup_nodes SET official_model_name=NULL")  # 테스트 fixture에서만 명시 해제합니다.
        copy.commit()  # 빈값 down 조건을 만듭니다.
        copy.close()  # 잠금을 반환합니다.
        before = self.rows(path)  # 기존 행 기준선을 고정합니다.
        self.assertEqual(rollback_official_models(path, self.root / "down-backups")["version"], 1)  # NULL 컬럼만 제거합니다.
        migrate_contract(path, self.root / "up-backups")  # 다시 전진합니다.
        self.assertEqual(self.rows(path), before)  # ID/원래 값이 보존됩니다.
