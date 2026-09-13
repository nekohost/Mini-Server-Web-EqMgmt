"""Linux 회귀시험 전용 v2 synthetic fixture 생성. 운영 migration/down 도구가 아닙니다."""
from pathlib import Path
from utils.database_contract import connect_database, assert_contract_version
from utils import roadmap_schema


def make_v2_fixture(path, fixture_root):
    """[역할] 새 기능 자료 없는 임시 사본만 이전 구조로 구성. [의존성 관계] tests fixture. [변경 시 영향도] 운영 경로 거부."""
    root = Path(fixture_root).resolve()
    path = Path(path).resolve(strict=True)
    if root.name.startswith(('contract-test-', 'roadmap-test-')) is False or path.parent != root:
        raise ValueError('synthetic fixture path required')
    connection = connect_database(path)
    try:
        if assert_contract_version(connection) == 2:
            return
        connection.execute('BEGIN IMMEDIATE')
        if any(connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in roadmap_schema.TABLES):
            raise ValueError('new feature records exist in fixture')
        if connection.execute('SELECT 1 FROM equipments WHERE warranty_end_date IS NOT NULL OR replacement_due_date IS NOT NULL LIMIT 1').fetchone():
            raise ValueError('deadline values exist in fixture')
        if connection.execute('SELECT 1 FROM users WHERE notification_verified_email IS NOT NULL LIMIT 1').fetchone():
            raise ValueError('verified address exists in fixture')
        for name in roadmap_schema.OBJECTS:
            kind = 'TRIGGER' if name.startswith('roadmap_') else 'INDEX'
            connection.execute(f'DROP {kind} {name}')
        for name in roadmap_schema.TABLES:
            connection.execute('DROP TABLE ' + name)
        for column in roadmap_schema.COLUMNS:
            connection.execute('ALTER TABLE equipments DROP COLUMN ' + column.split()[0])
        connection.execute('ALTER TABLE users DROP COLUMN notification_verified_email')
        connection.execute('DELETE FROM sys_migrations WHERE MigrationName=?', (roadmap_schema.MIGRATION,))
        connection.execute('PRAGMA user_version=2')
        assert_contract_version(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
