"""Allowlisted menu-workflow release with rehearsed metadata migration and targeted rollback."""
import base64
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path("/home/nekohost/services/Mini-Server-Web-EqMgmt")
FILES = {"app.py","static/css/layout.css","static/js/menu_cards.js","static/js/session_timer.js","static/js/permissions.js","static/js/my_approvals.js","templates/miniserver_frame.html","templates/index.html","templates/master_management.html","templates/permissions.html","templates/admin_center.html","templates/audit_logs.html","templates/access_logs.html","templates/access_logs_error_ips.html","templates/lineup_management.html","templates/approvals.html","templates/mypage.html","templates/my_approvals.html"}
RELEASES = Path("/home/nekohost/.local/share/mini-server-eqmgmt/releases")
sha = lambda b: hashlib.sha256(b).hexdigest()
normalized = lambda b: b.replace(b"\r\n", b"\n")
def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert not path.is_symlink() and path.stat().st_uid == os.getuid()
    path.chmod(0o700)
def write_atomic(path, data, mode):
    assert not path.is_symlink()
    temporary = path.with_name(path.name + ".ui-release-" + str(os.getpid()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
def db_state(database):
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as c:
        return {"integrity": c.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_key_violations": len(c.execute("PRAGMA foreign_key_check").fetchall()),
                "rows": {name: c.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                         for name in ("users", "equipments", "equipment_options", "lineup_nodes")}}
def stop_pid(pid, expected_cmd=None):
    handle = os.pidfd_open(pid)
    try:
        if expected_cmd is not None:
            assert Path("/proc/" + str(pid) + "/cwd").resolve() == ROOT
            assert Path("/proc/" + str(pid) + "/cmdline").read_bytes().split(b"\0")[:-1] == expected_cmd
        signal.pidfd_send_signal(handle, signal.SIGTERM)
        if not select.select([handle], [], [], 15)[0]:
            raise RuntimeError("exact process did not stop; no SIGKILL attempted")
    finally:
        os.close(handle)
def healthy():
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/login", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False
def start_process(command, environment, release, label):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("0.0.0.0", 5000))
    log = release / (label + ".log")
    with os.fdopen(os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError("new app exited; inspect private release log")
        if healthy():
            return process
        time.sleep(.5)
    stop_pid(process.pid)
    raise RuntimeError("new app health timeout")


META = ("menus", "role_menu_permissions", "sys_migrations")
MARKER = "personal_approvals_portal_20260914"
TESTED = RELEASES / "menu-workflows-fixture-_91qq70t"
def metadata(database):
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        return {name: [dict(row) for row in c.execute("SELECT * FROM " + name + " ORDER BY rowid")] for name in META}

def verify_metadata(before, after):
    bm = {r["MenuCode"]: r for r in before["menus"]}
    am = {r["MenuCode"]: r for r in after["menus"]}
    assert set(am) - set(bm) == {"my_approvals"} and set(bm) <= set(am)
    assert all(am[k] == v for k,v in bm.items())
    assert am["my_approvals"]["Url"] == "/my_approvals" and am["my_approvals"]["ParentMenuCode"] is None
    bp = {(r["Role"], r["MenuCode"]): r for r in before["role_menu_permissions"]}
    ap = {(r["Role"], r["MenuCode"]): r for r in after["role_menu_permissions"]}
    assert set(bp) <= set(ap)
    moved = []
    for key, original in bp.items():
        role, menu = key
        if menu == "approvals" and role != "admin" and original["IsAllowed"] == 1 and bp.get((role,"admin_center"),{}).get("IsAllowed",0) != 1:
            assert ap[key]["IsAllowed"] == 0
            assert all(ap[key][k] == v for k,v in original.items() if k not in {"IsAllowed","UpdatedAt"})
            moved.append(role)
        else:
            assert ap[key] == original, "unrelated permission changed"
    roles = set(r["Role"] for r in before["role_menu_permissions"]) | {"admin","user"}
    assert set(ap) - set(bp) == {(role,"my_approvals") for role in roles}
    assert all(ap[(role,"my_approvals")]["IsAllowed"] == 1 for role in roles)
    bs = {r["MigrationName"]:r for r in before["sys_migrations"]}
    ass = {r["MigrationName"]:r for r in after["sys_migrations"]}
    assert set(ass) - set(bs) == {MARKER} and all(ass[k] == v for k,v in bs.items())
    return {"new_menu":"my_approvals","personal_roles":sorted(roles),"legacy_grants_moved":moved,
            "other_metadata_unchanged":True}

def rollback_metadata(database, before):
    current = metadata(database)
    if current == before:
        return
    moved = verify_metadata(before, current)["legacy_grants_moved"]
    # Restore only the one-time migration's exact keys, never the whole live DB.
    with sqlite3.connect(database) as c:
        c.execute("BEGIN IMMEDIATE")
        c.row_factory = sqlite3.Row
        locked = {name: [dict(row) for row in c.execute("SELECT * FROM " + name + " ORDER BY rowid")] for name in META}
        assert locked == current, "metadata changed concurrently; rollback stops"
        c.execute("DELETE FROM role_menu_permissions WHERE MenuCode=?", ("my_approvals",))
        c.execute("DELETE FROM menus WHERE MenuCode=?", ("my_approvals",))
        c.execute("DELETE FROM sys_migrations WHERE MigrationName=?", (MARKER,))
        for role in moved:
            old = next(r for r in before["role_menu_permissions"] if r["Role"] == role and r["MenuCode"] == "approvals")
            c.execute("UPDATE role_menu_permissions SET IsAllowed=?,UpdatedAt=? WHERE Role=? AND MenuCode=?",
                      (old["IsAllowed"], old["UpdatedAt"], role, "approvals"))
    assert metadata(database) == before

def snapshot_db(database, target):
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(target) as dest:
            source.backup(dest)

data = json.load(sys.stdin)
assert ROOT.resolve() == ROOT and ROOT.is_dir()
assert RELEASES.resolve() == RELEASES and RELEASES.stat().st_uid == os.getuid()
assert set(data["files"]) == FILES
assert TESTED.resolve() == TESTED and not TESTED.is_symlink()
tested = json.loads((TESTED / "check-result.json").read_text())
rehearsal = json.loads((TESTED / "rehearsal-result.json").read_text())
assert tested["test_exit_code"] == 0 and tested["rehearsal_exit_code"] == 0
assert rehearsal["status"] == "pass" and rehearsal["migration_repeat_noop"]
git_env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,env=git_env,text=True).strip()
assert head == data["head"], "remote HEAD changed"
old_pid = data["pid"]
proc = Path("/proc/" + str(old_pid))
assert (proc / "cwd").resolve() == ROOT
command_bytes = (proc / "cmdline").read_bytes().split(b"\0")[:-1]
command = [x.decode() for x in command_bytes]
assert command == [str(ROOT / ".venv/bin/python"), "-u", "app.py"]
environment = dict(item.decode().split("=",1) for item in (proc / "environ").read_bytes().split(b"\0") if item)
originals, candidates = {}, {}
for name, entry in data["files"].items():
    target = ROOT / name
    assert target.parent.resolve().is_relative_to(ROOT) and not target.is_symlink()
    candidate = base64.b64decode(entry["content"],validate=True)
    assert sha(candidate) == entry["sha256"] == tested["files"][name], "candidate differs from tested source"
    candidates[name] = candidate
    if entry["baseline"] is None:
        assert name in {"static/js/permissions.js","static/js/my_approvals.js","templates/my_approvals.html"} and not target.exists()
        originals[name] = None
    else:
        old = target.read_bytes()
        assert sha(normalized(old)) == entry["baseline"], "baseline mismatch: " + name
        originals[name] = (old, stat.S_IMODE(target.stat().st_mode))
import ast, jinja2
ast.parse(candidates["app.py"].decode())
for name, source in candidates.items():
    if name.startswith("templates/"):
        jinja2.Environment().parse(source.decode(), name=name)
database = ROOT / "equipment.db"
before = db_state(database)
meta_before = metadata(database)
assert before["integrity"] == "ok" and before["foreign_key_violations"] == 0
assert not any(r["MenuCode"] == "my_approvals" for r in meta_before["menus"])
if not data["apply"]:
    print(json.dumps({"status":"ready","baseline_head":head,"pid":old_pid,"file_count":len(FILES),"db":before,
                      "tested_candidate":str(TESTED),"rehearsal":"pass"}))
    sys.exit(0)
release = RELEASES / ("ui-menu-workflows-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
assert not release.exists()
private_dir(release)
for folder in ("before","candidate"):
    private_dir(release / folder)
for name in FILES:
    for folder in ("before","candidate"):
        private_dir((release / folder / name).parent)
    write_atomic(release / "candidate" / name,candidates[name],0o600)
    if originals[name] is not None:
        write_atomic(release / "before" / name, originals[name][0],0o600)
evidence = {"baseline_head":head,"old_pid":old_pid,"release":str(release),"db_before":before,
            "tested_candidate":str(TESTED),"files":{n:{"before":sha(originals[n][0]) if originals[n] else None,
                                                   "after":sha(candidates[n])} for n in sorted(FILES)}}
write_atomic(release / "manifest.json",json.dumps(evidence,indent=2).encode(),0o600)
changed, stopped, new_process = [], False, None
try:
    stop_pid(old_pid,command_bytes)
    stopped = True
    # Logger is drained before the consistent backup; no environment/credential dump.
    snapshot_db(database, release / "equipment-before.db")
    meta_before = metadata(database)
    for name in sorted(FILES):
        write_atomic(ROOT / name,candidates[name],originals[name][1] if originals[name] else 0o644)
        changed.append(name)
    new_process = start_process(command,environment,release,"service-start")
    after = db_state(database)
    assert before == after, "business counts/integrity changed"
    migration = verify_metadata(meta_before, metadata(database))
    assert all(sha((ROOT / n).read_bytes()) == sha(candidates[n]) for n in FILES)
    evidence.update(status="deployed",new_pid=new_process.pid,db_after=after,health=200,migration=migration)
except BaseException as error:
    if new_process is not None and new_process.poll() is None:
        stop_pid(new_process.pid)
    if stopped:
        rollback_metadata(database,meta_before)
        for name in reversed(changed):
            if originals[name] is None:
                assert sha((ROOT / name).read_bytes()) == sha(candidates[name])
                (ROOT / name).unlink()
            else:
                write_atomic(ROOT / name,originals[name][0],originals[name][1])
        recovered = start_process(command,environment,release,"service-rollback")
        evidence.update(rollback_pid=recovered.pid,rollback_health=200,metadata_rollback=True)
    evidence.update(status="failed",error_type=type(error).__name__)
    write_atomic(release / "result.json",json.dumps(evidence,indent=2).encode(),0o600)
    print(json.dumps(evidence))
    raise
write_atomic(release / "result.json",json.dumps(evidence,indent=2).encode(),0o600)
print(json.dumps(evidence))
