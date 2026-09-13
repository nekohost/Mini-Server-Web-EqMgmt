"""제안 묶음의 additive v3 DB 계약; 업무 행을 재작성하거나 DROP하지 않습니다."""
MIGRATION = 'roadmap_batch_v3'
COLUMNS = (
    'revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0)',
    'warranty_end_date TEXT',
    'replacement_due_date TEXT',
)
USER_COLUMN = 'notification_verified_email TEXT'  # 이메일 인증 소비 후에도 인증한 주소를 보존합니다.
TABLES = {
    'equipment_files': '''CREATE TABLE equipment_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER NOT NULL,
        storage_key TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL, mime_type TEXT NOT NULL,
        size_bytes INTEGER NOT NULL CHECK(size_bytes > 0 AND size_bytes <= 10485760),
        sha256 TEXT NOT NULL, uploaded_by INTEGER NOT NULL, created_at TEXT NOT NULL, deleted_at TEXT)''',
    'auth_rate_buckets': '''CREATE TABLE auth_rate_buckets (
        bucket_key TEXT PRIMARY KEY, attempts INTEGER NOT NULL CHECK(attempts >= 0), expires_at INTEGER NOT NULL)''',
    'equipment_imports': '''CREATE TABLE equipment_imports (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, payload_json TEXT NOT NULL,
        digest TEXT NOT NULL, expires_at INTEGER NOT NULL, result_json TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(UserId) ON DELETE CASCADE)''',
    'equipment_notification_log': '''CREATE TABLE equipment_notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        kind TEXT NOT NULL, due_date TEXT NOT NULL, send_day TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('SENDING','SENT','FAILED','UNKNOWN')),
        attempts INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
        UNIQUE(equipment_id,user_id,kind,due_date,send_day))''',
}
OBJECTS = {
    'idx_roadmap_files_equipment': 'CREATE INDEX idx_roadmap_files_equipment ON equipment_files(equipment_id,deleted_at,id)',
    'idx_roadmap_rate_expiry': 'CREATE INDEX idx_roadmap_rate_expiry ON auth_rate_buckets(expires_at)',
    'idx_roadmap_import_expiry': 'CREATE INDEX idx_roadmap_import_expiry ON equipment_imports(expires_at)',
    'idx_roadmap_equipment_filter': 'CREATE INDEX idx_roadmap_equipment_filter ON equipments(user_id,status,purchase_date,id)',
    'idx_roadmap_history': 'CREATE INDEX idx_roadmap_history ON equipments_audit_log(equipment_id,id DESC)',
    'roadmap_equipment_revision': '''CREATE TRIGGER roadmap_equipment_revision AFTER UPDATE ON equipments
        WHEN NEW.revision=OLD.revision BEGIN
        UPDATE equipments SET revision=OLD.revision+1 WHERE id=NEW.id; END''',
    'roadmap_equipment_files_retention': '''CREATE TRIGGER roadmap_equipment_files_retention AFTER DELETE ON equipments BEGIN
        UPDATE equipment_files SET deleted_at=COALESCE(deleted_at,CURRENT_TIMESTAMP) WHERE equipment_id=OLD.id; END''',
}


def apply_schema(connection):
    """[역할] caller transaction 안에서 v3 확장. [의존성 관계] migrate_contract. [변경 시 영향도] 기존 ID/감사 보존."""
    for column in COLUMNS:
        connection.execute('ALTER TABLE equipments ADD COLUMN ' + column)
    connection.execute('ALTER TABLE users ADD COLUMN ' + USER_COLUMN)
    for sql in (*TABLES.values(), *OBJECTS.values()):
        connection.execute(sql)  # 이름 충돌은 부분 적용을 허용하지 않고 rollback합니다.


def assert_schema(connection, sql_tokens, table_definition):
    """[역할] 실제 DDL/이력 교차검증. [의존성 관계] database_contract. [변경 시 영향도] 불완전 복원 거부."""
    equipment_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='equipments'").fetchone()[0]
    if any(sql_tokens(column) not in table_definition(equipment_sql)[0] for column in COLUMNS):
        raise ValueError('roadmap equipment columns mismatch')
    user_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    if sql_tokens(USER_COLUMN) not in table_definition(user_sql)[0]:
        raise ValueError('roadmap email verification column mismatch')
    for name, sql in {**TABLES, **OBJECTS}.items():
        row = connection.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()
        if not row or sql_tokens(row[0]) != sql_tokens(sql):
            raise ValueError('roadmap schema object mismatch')
    if connection.execute('SELECT 1 FROM equipment_files f LEFT JOIN equipments e ON e.id=f.equipment_id WHERE f.deleted_at IS NULL AND e.id IS NULL LIMIT 1').fetchone():
        raise ValueError('roadmap active attachment reference mismatch')
