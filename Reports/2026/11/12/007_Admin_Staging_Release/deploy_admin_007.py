"""One-shot, fail-closed administrator release with private SQLite online backups.

Run through SSH only on the authorized Linux host after release source has been
independently reviewed and pushed to origin/main. Never embeds secrets.
"""
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from urllib import request, error

ROOT = Path("/home/nekohost/services/Mini-Server-Web-EqMgmt")
BASE = "920edeffbb9642eb3cc77f244f325af6d4a2336f"
DB = ROOT / "equipment.db"
AI = ROOT / "instance/ai/assistant.sqlite3"
RELEASES = ROOT / "instance/releases"
SPOOL = ROOT / "instance/http-audit/pending.sqlite3"
WORKER = "equipment-ai-worker.service"
PYTHON = str(ROOT / ".venv/bin/python")


def command(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def git(*args):
    return command("git", "--no-optional-locks", *args)


def web_pids():
    result = []
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            if proc.stat().st_uid != os.geteuid() or (proc / "cwd").resolve() != ROOT:
                continue
            values = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            if values == [PYTHON, "-u", "app.py"]:
                result.append(int(proc.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError, UnicodeError):
            pass
    return sorted(result)


def private_json(path, data):
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def row_fingerprint(db_path, sql):
    digest = hashlib.sha256()
    count = 0
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        for row in db.execute(sql):
            b = repr(tuple(row)).encode("utf-8")
            digest.update(len(b).to_bytes(8, "big"))
            digest.update(b)
            count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def backup_database(path, dest):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=20)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst, pages=500)
        dst.commit()
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        fks = dst.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or fks:
        raise ValueError("database backup failed integrity / foreign key check")
    os.chmod(dest, 0o600)
    digest = hashlib.sha256()
    with dest.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": dest.stat().st_size, "integrity": "ok", "fk_violations": 0}


def session_fingerprint():
    return row_fingerprint(DB, "SELECT UserId,SessionToken FROM users ORDER BY UserId")


def active_work():
    with closing(sqlite3.connect(AI.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        jobs = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running','draining','recovery_required')").fetchone()[0]
        guards = db.execute("SELECT COUNT(*) FROM ai_execution_guards WHERE state IN ('running','draining','recovery_required')").fetchone()[0]
    return {"jobs": jobs, "guards": guards}


def request_page(page):
    with request.urlopen("http://127.0.0.1:5000" + page, timeout=5) as response:
        return response.status, response.read()


def old_handler_is_safe(pid):
    proc = Path("/proc") / str(pid)
    flags = int(re.search(r"^SigCgt:\s*([0-9a-fA-F]+)", (proc / "status").read_text(), re.M)[1], 16)
    if not flags & (1 << (signal.SIGINT - 1)):
        raise RuntimeError("current web lacks safe SIGINT shutdown handler")


def stop_web(pid):
    if web_pids() != [pid]:
        raise RuntimeError("web identity changed; do not stop")
    old_handler_is_safe(pid)
    os.kill(pid, signal.SIGINT)
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if not web_pids():
            return
        time.sleep(0.2)
    raise RuntimeError("old web did not stop gracefully; do not force-kill")


def launch_web(release_dir, env, logfile):
    if web_pids():
        raise RuntimeError("web port already owned by another process")
    logpath = release_dir / logfile
    fd = os.open(logpath, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as log:
        child = subprocess.Popen([PYTHON, "-u", "app.py"], cwd=ROOT, env=env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 start_new_session=True)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("new web exited before readiness")
        try:
            code, html = request_page("/login")
            if code == 200 and b"loginForm" in html and web_pids() == [child.pid]:
                return child.pid
        except (OSError, error.URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("new web failed readiness check")


def expected_runtime(pid):
    proc = Path("/proc") / str(pid)
    if proc.stat().st_uid != os.geteuid() or (proc / "cwd").resolve() != ROOT:
        raise RuntimeError("unexpected web process owner or root")
    args = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
    if args != [PYTHON, "-u", "app.py"]:
        raise RuntimeError("unexpected web process command")
    env = dict(v.decode().split("=", 1) for v in (proc / "environ").read_bytes().split(b"\0") if v and b"=" in v)
    if Path(env.get("DATABASE_PATH", "")).resolve() != DB or Path(env.get("USER_AI_DATABASE", "")).resolve() != AI:
        raise RuntimeError("unexpected running database paths")
    return env


def main():
    os.umask(0o077)
    dry_run = len(sys.argv) == 3 and sys.argv[1] == "--preflight"
    if not (len(sys.argv) == 2 or dry_run) or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[-1]):
        raise ValueError("exact target Git SHA required")
    target = sys.argv[-1]
    if socket.gethostname() != "nkhst-pentium" or ROOT.stat().st_uid != os.geteuid():
        raise RuntimeError("server identity mismatch")
    if git("branch", "--show-current") != "main" or git("rev-parse", "HEAD") != BASE or git("rev-parse", "origin/main") != target:
        raise RuntimeError("Git baseline/remote target mismatch")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked source is not clean")
    if not RELEASES.is_dir() or RELEASES.is_symlink():
        raise RuntimeError("release private directory missing")
    if json.loads((ROOT / "instance/maintenance-state.json").read_text())["state"] != "NORMAL":
        raise RuntimeError("existing maintenance state is not NORMAL")
    if SPOOL.exists() or any(SPOOL.parent.glob("pending.sqlite3-*")):
        raise RuntimeError("legacy web log spool must be reviewed first")
    if command("systemctl", "--user", "is-active", WORKER) != "active":
        raise RuntimeError("AI worker is not active")
    worker_pid = int(command("systemctl", "--user", "show", WORKER, "--property=MainPID", "--value"))
    if worker_pid <= 0:
        raise RuntimeError("AI worker PID missing")
    old = web_pids()
    if len(old) != 1:
        raise RuntimeError("expected exactly one authorized web")
    env = expected_runtime(old[0])
    old_handler_is_safe(old[0])
    if active_work() != {"jobs": 0, "guards": 0}:
        raise RuntimeError("unfinished AI work; do not deploy")
    if request_page("/login")[0] != 200:
        raise RuntimeError("existing public login not healthy")
    old_sessions = session_fingerprint()
    if dry_run:
        print(json.dumps({"preflight":"pass", "current":BASE, "target":target,
                          "old_web_pid":old[0], "worker_pid":worker_pid,
                          "active_work":active_work(), "users_sessions":old_sessions["rows"]}))
        return

    release_dir = RELEASES / ("admin-007-" + secrets.token_hex(6))
    release_dir.mkdir(mode=0o700)
    private_json(release_dir / "preflight.json", {
        "baseline": BASE, "target": target, "worker_pid": worker_pid,
        "old_web_pid": old[0], "time_utc": datetime.now(timezone.utc).isoformat()
    })
    backup_equipment = backup_database(DB, release_dir / "equipment-before.sqlite3")
    backup_ai = backup_database(AI, release_dir / "assistant-before.sqlite3")
    before_users = row_fingerprint(release_dir / "equipment-before.sqlite3", "SELECT * FROM users ORDER BY UserId")
    before_jobs = row_fingerprint(release_dir / "assistant-before.sqlite3", "SELECT * FROM jobs ORDER BY id")
    private_json(release_dir / "backup-proof.json", {"equipment": backup_equipment, "assistant": backup_ai,
        "users": before_users, "jobs": before_jobs, "session_tokens": old_sessions})
    started = time.monotonic()
    changed_git = False
    new_pid = None
    try:
        # Holding the existing AI writer reservation prevents late task admissions until the old web exits.
        with closing(sqlite3.connect(AI.as_uri() + "?mode=rw", uri=True, timeout=20)) as ai:
            ai.execute("BEGIN IMMEDIATE")
            if active_work()["jobs"] or active_work()["guards"]:
                raise RuntimeError("AI work admitted during backup")
            stop_web(old[0])
            ai.rollback()
        if web_pids():
            raise RuntimeError("web remains active after normal shutdown")
        if SPOOL.exists() or any(SPOOL.parent.glob("pending.sqlite3-*")):
            raise RuntimeError("web spool pending after shutdown")
        git("merge", "--ff-only", target)
        changed_git = True
        if git("rev-parse", "HEAD") != target:
            raise RuntimeError("target commit not checked out")
        new_pid = launch_web(release_dir, env, "new-web.log")
        login_status, login_body = request_page("/login")
        register_status, register_body = request_page("/register")
        if login_status != 200 or register_status != 200 or "이름 (선택)".encode() not in register_body:
            raise RuntimeError("public login/register smoke test failed")
        if worker_pid != int(command("systemctl", "--user", "show", WORKER, "--property=MainPID", "--value")):
            raise RuntimeError("existing AI worker unexpectedly changed")
        if session_fingerprint() != old_sessions:
            raise RuntimeError("pre-existing session tokens changed during deployment")
        if row_fingerprint(DB, "SELECT * FROM users ORDER BY UserId") != before_users:
            raise RuntimeError("existing user records changed during release")
        if row_fingerprint(AI, "SELECT * FROM jobs ORDER BY id") != before_jobs:
            raise RuntimeError("existing AI job records changed during release")
        for db_path in (DB, AI):
            with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("post-release DB integrity failed")
        result = {"status": "active", "old": BASE, "new": target,
                  "old_web_pid": old[0], "new_web_pid": new_pid,
                  "worker_pid_preserved": worker_pid, "user_rows_preserved": before_users["rows"],
                  "ai_job_rows_preserved": before_jobs["rows"], "sessions_preserved": old_sessions["rows"],
                  "equipment_backup": backup_equipment, "ai_backup": backup_ai,
                  "public_login": login_status, "public_register": register_status,
                  "elapsed_seconds": round(time.monotonic()-started, 3),
                  "backup_location": str(release_dir)}
        private_json(release_dir / "result.json", result)
        print(json.dumps(result, ensure_ascii=False))
    except BaseException as exc:
        if changed_git:
            web_now = web_pids()
            if len(web_now) == 1 and web_now[0] != old[0]:
                stop_web(web_now[0])
            if not web_pids():
                if git("status", "--porcelain", "--untracked-files=no"):
                    raise RuntimeError("source dirty after failed deployment; preserve for manual recovery") from exc
                git("reset", "--keep", BASE)
        if not web_pids():
            launch_web(release_dir, env, "recovery-web.log")
        print(json.dumps({"status":"rolled_back","reason":str(exc),
                          "current_head":git("rev-parse","HEAD"),"web_pids":web_pids(),
                          "backup_location":str(release_dir)},ensure_ascii=False))
        raise


if __name__ == "__main__":
    main()
