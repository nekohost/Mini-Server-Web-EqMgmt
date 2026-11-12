"""Verify release cleanup on a disposable online backup of an equipment snapshot.

python clone_scope.py --snapshot ABS_FILE --workdir ABS_DIR --source ABS_RELEASE
python clone_scope.py --self-test --workdir ABS_DIR --source ABS_RELEASE

ABS_RELEASE may be the unpacked release root or candidate.zip. Only the two
verified Python modules are loaded. The caller supplies a private local workdir.
One full database copy, SQLite journal space and multiple data scans are needed.
A frozen snapshot with pending journals also needs space for a private input image.
The comparison covers tables in the supplied database. Digests stay in memory.
"""

import argparse
from contextlib import ExitStack, closing
from datetime import datetime
import hashlib
import json
import marshal
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from zipfile import ZipFile


# SHA-256 of the two source files in the release, with LF line endings.
CANDIDATE = {
    "http_audit_queue.py": "fd1d10a5894d9389d907322bee91be8daf4b1c40aea62e3c69f777e5e533076b",
    "access_log_cleanup.py": "504e17e83b75637d96c6dff3a14e8856b8b967b607c4f18df7aa525a5b2827b6",
}
ACTOR = 2**62  # Synthetic metadata, only on the disposable copy.
AI_ROOTS = ("/assistant", "/admin/ai", "/api/ai", "/internal/ai", "/api/admin/ai")
# Independent of the candidate's deletion SQL. A slash terminates each segment.
AI_CONDITION = " OR ".join("instr(RequestPath || '/', ?) = 1" for _ in AI_ROOTS)
AI_PREFIXES = tuple(root + "/" for root in AI_ROOTS)
MARKER_PATHS = ("/__clone_scope_marker__", "/api/ai/__clone_scope_marker__")


class CheckFailed(Exception):
    """Only constant diagnostic codes may be reported."""


def check(condition, code):
    if not condition:
        raise CheckFailed(code)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckFailed("invalid_arguments")


def absolute(value):
    path = Path(value)
    check(path.is_absolute(), "absolute_path_required")
    return path.resolve()


def candidate(source, scratch):
    # Import from private, verified bytes, without running app.py, a release
    # package initializer or pre-existing bytecode from the supplied source.
    package = scratch / "_clone_scope_candidate"
    package.mkdir()
    (package / "__init__.py").touch()
    with ExitStack() as files:
        archive = None if source.is_dir() else files.enter_context(ZipFile(source))
        for name, expected in CANDIDATE.items():
            member = "utils/" + name
            data = archive.read(member) if archive else (source / member).read_bytes()
            check(hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == expected,
                  "candidate_source_mismatch")
            (package / name).write_bytes(data)
    sys.path.insert(0, str(scratch))
    try:
        from _clone_scope_candidate import access_log_cleanup
        return access_log_cleanup
    finally:
        sys.path.pop(0)


def scalar(db, sql, params=()):
    return db.execute(sql, params).fetchone()[0]


def fingerprint(db, sql, params=()):
    """Stream ordered, type- and length-framed rows; compare within this run."""
    rows = db.execute(sql, params)
    digest = hashlib.sha256()
    digest.update(marshal.dumps(tuple(column[0] for column in rows.description), 2))
    count = 0
    for row in rows:
        # Format 2 has no identity-based reference sharing. SQLite NULL, text,
        # blob, signed integer and double retain distinct binary encodings.
        digest.update(marshal.dumps(tuple(row), 2))
        count += 1
    return count, digest.digest()


def identifier(name):
    return '"' + name.replace('"', '""') + '"'


def business_state(db):
    state = {}
    for (name,) in db.execute("""
        SELECT name FROM main.sqlite_master WHERE type='table'
        AND name NOT GLOB 'sqlite_*' AND name COLLATE NOCASE NOT IN ('audit_logs', 'access_logs')
    """):
        table = identifier(name)
        columns = list(db.execute(f"PRAGMA main.table_info({table})"))
        keys = [c["name"] for c in sorted(columns, key=lambda c: c["pk"]) if c["pk"]]
        projection = "*"
        if not keys:  # Preserve the implicit row identity of a heap table too.
            names = {c["name"].lower() for c in columns}
            keys = [k for k in ("_rowid_", "rowid", "oid") if k not in names][:1]
            if keys:
                projection = keys[0] + ", *"
            else:
                keys = [c["name"] for c in columns]
        order = ", ".join(identifier(k) for k in keys)
        state[name] = fingerprint(db, f"SELECT {projection} FROM main.{table} ORDER BY {order}")
    return state


def original_audits(db, ceiling):
    return fingerprint(db, "SELECT * FROM audit_logs WHERE AuditId <= ? ORDER BY AuditId", (ceiling,))


def historical_ai(db, ceiling):
    return fingerprint(db, f"""
        SELECT * FROM access_logs WHERE LogId <= ? AND ({AI_CONDITION}) ORDER BY LogId
    """, (ceiling, *AI_PREFIXES))


def audit(db, event, target_id, details):
    # app.api_cleanup_access_logs -> audit_lineup_change(..., before=None).
    # That function stores the JSON text "null" and leaves commit to its caller.
    db.execute("""
        INSERT INTO audit_logs (ActorId, ActorLoginId, IpAddress, UserAgent, TargetTable,
                                TargetId, Action, OldValue, NewValue, CreatedAt)
        VALUES (?, 'clone-scope', '127.0.0.1', 'clone_scope', 'access_logs', ?, ?, ?, ?, ?)
    """, (ACTOR, target_id, event, json.dumps(None), json.dumps(details, ensure_ascii=False),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def add_markers(db, ceiling):
    # Both would be old enough even for a timestamp-based purge. The IDs are
    # assigned by SQLite after begin() commits, as in a subsequent log write.
    columns = {r["name"] for r in db.execute("PRAGMA table_info(access_logs)")}
    fields = {"RequestPath": "", "IpAddress": "127.0.0.1", "HttpMethod": "GET",
              "StatusCode": 200, "IsStatic": 0, "CreatedAt": "2000-01-01 00:00:00"}
    fields = {k: v for k, v in fields.items() if k in columns}
    check("RequestPath" in fields, "access_schema")
    sql = (f"INSERT INTO access_logs ({', '.join(fields)}) "
           f"VALUES ({', '.join(':' + k for k in fields)})")
    ids = []
    with db:
        for path in MARKER_PATHS:
            fields["RequestPath"] = path
            ids.append(db.execute(sql, fields).lastrowid)
    check(all(i > ceiling for i in ids) and len(set(ids)) == len(ids), "marker_boundary")
    sql = """SELECT * FROM access_logs WHERE (LogId=? AND RequestPath=?)
             OR (LogId=? AND RequestPath=?) ORDER BY LogId"""
    params = (ids[0], MARKER_PATHS[0], ids[1], MARKER_PATHS[1])
    before = fingerprint(db, sql, params)
    check(before[0] == len(ids), "marker_insert")
    return sql, params, before


def check_receipts(db, floor, operation, action, ceiling, expected, chunks):
    start_id, nonce = operation.split(".")
    start_id = int(start_id)
    starts = deletes = total = 0
    for row in db.execute("SELECT * FROM audit_logs WHERE AuditId > ? ORDER BY AuditId", (floor,)):
        details = json.loads(row["NewValue"])
        check(row["ActorId"] == ACTOR and row["TargetTable"] == "access_logs"
              and details["action"] == action, "unexpected_new_audit")
        if row["Action"] == "CLEANUP_ACCESS_LOGS_START":
            check(row["AuditId"] == start_id and row["TargetId"] is None
                  and details["nonce"] == nonce and details["bound"] == ceiling
                  and details["total_count"] == expected, "start_receipt")
            starts += 1
        else:
            check(row["Action"] == "CLEANUP_ACCESS_LOGS" and row["TargetId"] == start_id,
                  "chunk_receipt")
            deletes += 1
            total += details["deleted_count"]
    check((starts, deletes, total) == (1, chunks, expected), "receipt_totals")
    return {"start": starts, "delete": deletes, "deleted_rows": total}


def run_scope(db, api, action, expected, original_audit_bound, result):
    ceiling = scalar(db, "SELECT COALESCE(MAX(LogId), 0) FROM access_logs")
    audit_floor = scalar(db, "SELECT COALESCE(MAX(AuditId), 0) FROM audit_logs")
    prior_sql = "SELECT * FROM audit_logs WHERE AuditId > ? AND AuditId <= ? ORDER BY AuditId"
    prior_bounds = (original_audit_bound, audit_floor)
    prior_receipts = fingerprint(db, prior_sql, prior_bounds)
    start = api.begin(db, action, ACTOR, audit, ceiling)
    result.update(expected_targets=expected, begin_targets=start["total_count"])
    check(start["status"] == "success" and start["total_count"] == expected, "begin_targets")
    operation = start["operation_id"]
    marker_sql, marker_params, before_markers = add_markers(db, ceiling)
    deleted = chunks = 0
    while True:
        part = api.advance(db, action, ACTOR, operation, "delete_chunk", audit)
        n = part["deleted_count"]
        check(part["status"] == "success" and type(n) is int
              and 0 <= n <= min(api.CHUNK_SIZE, expected - deleted), "chunk_count")
        if n == 0:
            break
        chunks += 1
        deleted += n
    end = api.advance(db, action, ACTOR, operation, "finish", audit)
    result.update(deleted=end["deleted_count"], finish_remaining=end["remaining_count"])
    check(end["status"] == "success" and deleted == end["deleted_count"] == expected
          and end["remaining_count"] == 0, "finish_totals")
    after_markers = fingerprint(db, marker_sql, marker_params)
    outside = scalar(db, "SELECT COUNT(*) FROM access_logs WHERE LogId > ?", (ceiling,))
    result.update(markers_preserved=after_markers[0], marker_contents_match=after_markers == before_markers)
    check(after_markers == before_markers and outside == len(MARKER_PATHS), "post_begin_markers")
    result["new_receipts"] = check_receipts(db, audit_floor, operation, action, ceiling, expected, chunks)
    check(fingerprint(db, prior_sql, prior_bounds) == prior_receipts, "prior_receipts_changed")
    return ceiling


def verify(db, api, report):
    db.row_factory = sqlite3.Row
    db.text_factory = lambda raw: raw.decode("utf-8", "surrogateescape")
    db.execute("PRAGMA trusted_schema=OFF")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA temp_store=MEMORY")
    initial_bound = scalar(db, "SELECT COALESCE(MAX(LogId), 0) FROM access_logs")
    audit_bound = scalar(db, "SELECT COALESCE(MAX(AuditId), 0) FROM audit_logs")
    rows = scalar(db, "SELECT COUNT(*) FROM access_logs")
    ai = historical_ai(db, initial_bound)
    audits = original_audits(db, audit_bound)
    business = business_state(db)
    report["snapshot"] = dict(access_rows=rows, historical_ai=ai[0], original_audits=audits[0],
                              ai_execute_audits=scalar(db, "SELECT COUNT(*) FROM audit_logs WHERE Action='AI_EXECUTE'"),
                              business_tables=len(business), business_rows=sum(v[0] for v in business.values()))

    for action in ("all", "all_including_ai"):
        result = report[action] = {}
        # The first pair of markers is now inside the second operation's bound.
        expected = rows - ai[0] if action == "all" else ai[0] + len(MARKER_PATHS)
        ceiling = run_scope(db, api, action, expected, audit_bound, result)
        old_rows = scalar(db, "SELECT COUNT(*) FROM access_logs WHERE LogId <= ?", (ceiling,))
        if action == "all":
            remaining_ai = historical_ai(db, initial_bound)
            result.update(historical_ai_remaining=remaining_ai[0], historical_ai_contents_match=remaining_ai == ai)
            check(remaining_ai == ai, "historical_ai_changed")
            old_rows -= remaining_ai[0]
        result["remaining_targets"] = old_rows
        check(old_rows == 0, "rows_within_scope")
        result["original_audits_match"] = original_audits(db, audit_bound) == audits
        result["business_contents_match"] = business_state(db) == business
        check(result["original_audits_match"], "original_audits_changed")
        check(result["business_contents_match"], "business_rows_changed")


def file_stamp(path):
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def backup_snapshot(snapshot, target, db):
    # SQLite may create or update a WAL index even on a mode=ro connection.
    # An immutable reader works for a standalone frozen file, but ignores
    # outstanding WAL commits. Stage those bytes together in that case.
    parts = {suffix: Path(str(snapshot) + suffix) for suffix in ("", "-wal", "-journal")}
    stamps = {suffix: file_stamp(path) for suffix, path in parts.items()}
    journals = [s for s in ("-wal", "-journal") if stamps[s] and stamps[s][2]]
    if journals:
        staged = target.parent / "input-image.sqlite3"
        for suffix in ("", *journals):
            shutil.copyfile(parts[suffix], str(staged) + suffix)
        if "-journal" in journals:
            # Recovery can write. Only the disposable staging image is eligible.
            with closing(sqlite3.connect(staged.as_uri() + "?mode=rw", uri=True)) as recovery:
                recovery.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        read_uri = staged.as_uri() + "?mode=ro"
    else:
        read_uri = snapshot.as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(read_uri, uri=True)) as origin:
        origin.execute("PRAGMA query_only=ON")
        origin.backup(db, pages=1024)
    check(stamps == {s: file_stamp(p) for s, p in parts.items()}, "snapshot_changed_during_backup")


def create_clone(snapshot, target):
    check(target.resolve() != snapshot.resolve() and
          not (target.exists() and target.samefile(snapshot)), "snapshot_clone_alias")
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    check(not target.samefile(snapshot), "snapshot_clone_alias")
    return sqlite3.connect(target.as_uri() + "?mode=rw", uri=True)


def run_snapshot(snapshot, scratch, api, report):
    check(snapshot.is_file(), "snapshot_file_required")
    with tempfile.TemporaryDirectory(prefix="db-", dir=scratch) as folder:
        target = Path(folder) / "verification.sqlite3"
        with closing(create_clone(snapshot, target)) as db:
            backup_snapshot(snapshot, target, db)
            verify(db, api, report)


def synthetic(snapshot, populated):
    # The two log tables use the release's app.py column types and constraints.
    with closing(sqlite3.connect(snapshot)) as db, db:
        db.executescript("""
            CREATE TABLE access_logs (LogId INTEGER PRIMARY KEY AUTOINCREMENT,
                IpAddress TEXT NOT NULL, HttpMethod TEXT NOT NULL, RequestPath TEXT NOT NULL,
                StatusCode INTEGER NOT NULL, UserAgent TEXT, Referer TEXT, DurationMs REAL,
                IsStatic INTEGER DEFAULT 0, RequestPayload TEXT, ResponsePayload TEXT, CreatedAt TEXT NOT NULL);
            CREATE TABLE audit_logs (AuditId INTEGER PRIMARY KEY AUTOINCREMENT, ActorId INTEGER,
                ActorLoginId TEXT, IpAddress TEXT, UserAgent TEXT, TargetTable TEXT, TargetId INTEGER,
                Action TEXT, OldValue TEXT, NewValue TEXT, CreatedAt TEXT);
            CREATE TABLE equipments (id INTEGER PRIMARY KEY, name TEXT, receipt BLOB);
            CREATE TABLE equipments_audit_log (id INTEGER PRIMARY KEY, equipment_id INTEGER, new_value TEXT);
        """)
        if populated:
            ai_paths = [p for root in AI_ROOTS for p in (root, root + "/", root + "/child")]
            web_paths = ["/"] + [p for root in AI_ROOTS for p in (root + "-other", root.upper())]
            paths = [ai_paths[i % len(ai_paths)] for i in range(257)]
            paths += [web_paths[i % len(web_paths)] for i in range(503)]
            db.executemany("""
                INSERT INTO access_logs (IpAddress,HttpMethod,RequestPath,StatusCode,IsStatic,
                                         RequestPayload,ResponsePayload,DurationMs,CreatedAt)
                VALUES ('192.0.2.1','GET',?,200,?,?,?,0.75,'2000-01-01 00:00:00')
            """, ((p, i % 2, f"fixture-{i}", bytes([i % 256])) for i, p in enumerate(paths)))
            db.executescript("""
                INSERT INTO equipments VALUES (1,'fixture',X'0001');
                INSERT INTO equipments_audit_log VALUES (1,1,'fixture');
                INSERT INTO audit_logs (Action,TargetTable,NewValue) VALUES ('AI_EXECUTE','equipments','{}');
                INSERT INTO audit_logs (Action,TargetTable,NewValue) VALUES ('CLEANUP_ACCESS_LOGS','access_logs','{}');
            """)


def self_test(scratch, api, report):
    for populated, name in ((True, "populated"), (False, "empty")):
        snapshot = scratch / (name + ".sqlite3")
        synthetic(snapshot, populated)
        before = hashlib.sha256(snapshot.read_bytes()).digest()  # Small synthetic file only.
        case = report[name] = {}
        run_snapshot(snapshot, scratch, api, case)
        check(hashlib.sha256(snapshot.read_bytes()).digest() == before, "self_test_snapshot_changed")
        check(case["all"]["deleted"] == (503 if populated else 0)
              and case["all"]["historical_ai_remaining"] == (257 if populated else 0)
              and case["all_including_ai"]["deleted"] == (259 if populated else 2)
              and case["snapshot"]["original_audits"] == (2 if populated else 0)
              and case["snapshot"]["business_rows"] == (2 if populated else 0), "self_test_totals")
        case["snapshot_bytes_match"] = True


def main():
    report = {"ok": False}
    try:
        parser = Parser(description=__doc__)
        inputs = parser.add_mutually_exclusive_group(required=True)
        inputs.add_argument("--snapshot")
        inputs.add_argument("--self-test", action="store_true")
        parser.add_argument("--source", required=True)
        parser.add_argument("--workdir", required=True)
        args = parser.parse_args()
        source, workdir = absolute(args.source), absolute(args.workdir)
        snapshot = absolute(args.snapshot) if args.snapshot is not None else None
        check(workdir != snapshot, "snapshot_workdir_alias")
        if snapshot is not None:
            check(snapshot.is_file(), "snapshot_file_required")
        workdir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="clone-scope-", dir=workdir) as folder:
            scratch = Path(folder)
            api = candidate(source, scratch)
            if args.self_test:
                self_test(scratch, api, report)
            else:
                run_snapshot(snapshot, scratch, api, report)
        report["ok"] = True
    except CheckFailed as failure:
        report["error"] = str(failure)
    except (Exception, KeyboardInterrupt) as failure:
        # SQLite, filenames, argument values and candidate exceptions may carry
        # private data. Only the exception class / SQLite symbolic code is safe.
        report["error"] = getattr(failure, "sqlite_errorname", None) or type(failure).__name__
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
