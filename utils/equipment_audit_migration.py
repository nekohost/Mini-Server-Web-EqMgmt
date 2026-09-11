"""Preserve equipment history independently of the lifetime of its equipment.

Only the known equipment_id foreign key is removed. Unknown schema changes fail
closed; user backup/restore validation continues to reject every FK violation.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
import uuid


TABLE = "equipments_audit_log"
COLUMNS = "id, equipment_id, action_type, old_value, new_value, changed_by, changed_at"
DDL = """CREATE TABLE equipments_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by INTEGER,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""
MIGRATION = "equipment_audit_independent_history_v1"


def private_directory(path):
    """[역할] 지정 작업 디렉터리만 0700으로 보호합니다.
    [의존성 관계] pathlib/os; 심볼릭 링크·다른 소유자 경로는 거부합니다.
    [변경 시 영향도] DB 사본 저장소의 접근 경계에 영향을 줍니다.
    """
    target = Path(path).absolute()
    if target.resolve() != target or target == Path(target.anchor):
        raise ValueError("unsafe database workspace")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not target.is_dir() or target.is_symlink():
        raise ValueError("invalid database workspace")
    if hasattr(os, "getuid") and target.stat().st_uid != os.getuid():
        raise PermissionError("database workspace owner mismatch")
    os.chmod(target, 0o700)
    return target


def _canonical(sql):
    """Normalize only formatting, never constraints, for known-schema checks."""
    return re.sub(r"[\s;\"`\[\]]", "", sql).lower().replace("ifnotexists", "")


def _fingerprint(connection, table):
    """Hash typed rows in ID order, preserving NULL, JSON bytes and timestamps."""
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(f'SELECT {COLUMNS} FROM "{table}" ORDER BY id'):
        digest.update(repr(tuple(row)).encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def _row_summary(connection, table):
    """Record explicit row/ID/NULL evidence in addition to the typed digest."""
    fields = COLUMNS.split(', ')
    nulls = ', '.join(f'SUM(CASE WHEN {name} IS NULL THEN 1 ELSE 0 END)' for name in fields)
    row = connection.execute(f'SELECT COUNT(*), MIN(id), MAX(id), {nulls} FROM {table}').fetchone()
    return {"count": row[0], "min_id": row[1], "max_id": row[2], "nulls": dict(zip(fields, row[3:]))}


def migrate_equipment_audit_log(database_path, backup_root):
    """[역할] 백업·무손실 대조 후 감사 FK만 멱등·원자적으로 제거합니다.
    [의존성 관계] SQLite 온라인 백업, BEGIN IMMEDIATE, sys_migrations(존재 시).
    [변경 시 영향도] 삭제 감사 보존 및 제안013 FK 검증에 영향을 줍니다.
    실패하면 DB transaction은 rollback되며 검증된 사전 백업은 보존합니다.
    """
    source_path = Path(database_path).resolve(strict=True)
    connection = sqlite3.connect(source_path.as_uri() + "?mode=rw", uri=True, timeout=30)
    backup_path = None
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone()
        if schema is None:
            raise ValueError("audit table missing")
        foreign_keys = list(connection.execute(f"PRAGMA foreign_key_list({TABLE})"))
        if not foreign_keys:
            if _canonical(schema[0]) != _canonical(DDL):
                raise ValueError("unexpected independent audit schema")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_equipments_audit_equipment_id ON equipments_audit_log(equipment_id)")
            connection.commit()
            return {"applied": False, "backup_path": None}
        expected = DDL.rstrip().removesuffix(")") + ", FOREIGN KEY (equipment_id) REFERENCES equipments(id))"
        if _canonical(schema[0]) != _canonical(expected) or len(foreign_keys) != 1:
            raise ValueError("unexpected audit schema; manual review required")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("database integrity check failed")
        violations = list(connection.execute("PRAGMA foreign_key_check"))
        if any(row[0] != TABLE or row[2] != "equipments" or row[3] != foreign_keys[0][0] for row in violations):
            raise ValueError("unrelated foreign key violation")
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            quoted = '"' + name.replace('"', '""') + '"'
            if any(row[2] == TABLE for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")):
                raise ValueError("incoming audit FK requires manual review")
        if any(re.search(r"\bequipments_audit_log\b", sql or "", re.I) for (sql,) in
               connection.execute("SELECT sql FROM sqlite_master WHERE type='view'")):
            raise ValueError("dependent audit view requires manual review")
        artifacts = list(connection.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL", (TABLE,)))
        before = _fingerprint(connection, TABLE)
        before_summary = _row_summary(connection, TABLE)
        sequence = connection.execute("SELECT seq FROM sqlite_sequence WHERE name=?", (TABLE,)).fetchone()

        # A separate read connection can back up under our reserved writer lock.
        # Backing up the active write connection itself can wait indefinitely.
        backup_dir = private_directory(backup_root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_dir / f"audit-before-{stamp}-{uuid.uuid4().hex}.db"
        descriptor = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True, timeout=30)
        backup = sqlite3.connect(backup_path)
        try:
            source.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("migration backup integrity failed")
            if list(backup.execute("PRAGMA foreign_key_check")) != violations or _fingerprint(backup, TABLE) != before:
                raise ValueError("migration backup mismatch")
        finally:
            backup.close()
            source.close()
        os.chmod(backup_path, 0o600)
        backup_digest = hashlib.sha256()
        with backup_path.open('rb') as backup_file:
            for chunk in iter(lambda: backup_file.read(1024 * 1024), b''):
                backup_digest.update(chunk)
        evidence = {"migration": MIGRATION, "backup_sha256": backup_digest.hexdigest(),
                    "integrity": "ok", "foreign_key_violations": violations,
                    "audit_sha256": before[1], "audit_summary": before_summary,
                    "sqlite_sequence": sequence[0] if sequence else None}
        evidence_path = backup_path.with_suffix('.json')
        descriptor = os.open(evidence_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as evidence_file:
            json.dump(evidence, evidence_file, ensure_ascii=False, indent=2)
            evidence_file.flush()
            os.fsync(evidence_file.fileno())

        # Create-copy-drop-rename preserves IDs without rewriting parent links.
        connection.execute(DDL.replace(TABLE, TABLE + "_new", 1))
        connection.execute(f"INSERT INTO {TABLE}_new ({COLUMNS}) SELECT {COLUMNS} FROM {TABLE}")
        if _fingerprint(connection, TABLE + "_new") != before or _row_summary(connection, TABLE + "_new") != before_summary:
            raise ValueError("audit copy mismatch")
        connection.execute(f"DROP TABLE {TABLE}")
        connection.execute(f"ALTER TABLE {TABLE}_new RENAME TO {TABLE}")
        for (sql,) in artifacts:
            connection.execute(sql)
        if sequence:
            connection.execute("UPDATE sqlite_sequence SET seq=? WHERE name=?", (sequence[0], TABLE))
        connection.execute("CREATE INDEX IF NOT EXISTS idx_equipments_audit_equipment_id ON equipments_audit_log(equipment_id)")
        if _fingerprint(connection, TABLE) != before or connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("post-migration audit/FK mismatch")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("post-migration integrity failed")
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sys_migrations'").fetchone():
            connection.execute("INSERT OR IGNORE INTO sys_migrations (MigrationName, AppliedAt) VALUES (?, ?)",
                               (MIGRATION, datetime.now(timezone.utc).isoformat(timespec="milliseconds")))
        connection.commit()
        return {"applied": True, "backup_path": str(backup_path), "audit_count": before[0], "audit_sha256": before[1], "historical_orphans": len(violations)}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
