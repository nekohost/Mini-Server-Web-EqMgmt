"""One-release, allowlisted UI deployment. No DB migration or credential output."""
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
FILES = {"static/css/layout.css","static/js/roadmap_equipment.js","templates/miniserver_frame.html","templates/roadmap_equipment.html","templates/index.html","templates/master_management.html","templates/approvals.html","templates/audit_logs.html","templates/access_logs.html","templates/access_logs_error_ips.html","templates/admin_center.html","templates/users_management.html","templates/permissions.html","templates/lineup_management.html"}
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

data = json.load(sys.stdin)
assert ROOT.resolve() == ROOT and ROOT.is_dir()
assert RELEASES.resolve() == RELEASES and RELEASES.stat().st_uid == os.getuid()
assert set(data["files"]) == FILES
git_env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, env=git_env, text=True).strip()
assert head == data["head"], "remote HEAD changed"
old_pid = data["pid"]
proc = Path("/proc/" + str(old_pid))
assert (proc / "cwd").resolve() == ROOT
command_bytes = (proc / "cmdline").read_bytes().split(b"\0")[:-1]
command = [x.decode() for x in command_bytes]
assert command == [str(ROOT / ".venv/bin/python"), "-u", "app.py"]
# Retain the running service's configuration in memory, never stdout/artifacts.
environment = dict(item.decode().split("=", 1) for item in (proc / "environ").read_bytes().split(b"\0") if item)
originals = {}
candidates = {}
for name, entry in data["files"].items():
    path = ROOT / name
    assert path.parent.resolve().is_relative_to(ROOT) and not path.is_symlink()
    candidate = base64.b64decode(entry["content"], validate=True)
    assert sha(candidate) == entry["sha256"]
    candidates[name] = candidate
    if entry["baseline"] is None:
        assert name in {"static/js/navigation.js", "static/js/menu_cards.js"} and not path.exists()
        originals[name] = None
    else:
        old = path.read_bytes()
        assert sha(normalized(old)) == entry["baseline"], "baseline mismatch: " + name
        originals[name] = (old, stat.S_IMODE(path.stat().st_mode))
# Full local candidate syntax before stopping the live app; no app import.
import jinja2
candidate_templates = {p.name: p.read_text() for p in (ROOT / "templates").glob("*.html")}
candidate_templates.update({Path(n).name: b.decode() for n, b in candidates.items() if n.startswith("templates/")})
for name, source in candidate_templates.items():
    jinja2.Environment().parse(source, name=name)
database = ROOT / "equipment.db"
before = db_state(database)
assert before["integrity"] == "ok" and before["foreign_key_violations"] == 0
if not data["apply"]:
    print(json.dumps({"status": "ready", "baseline_head": head, "pid": old_pid, "file_count": len(FILES), "db": before}))
    sys.exit(0)
release = RELEASES / ("ui-header-csv-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
assert not release.exists()
private_dir(release)
private_dir(release / "before")
private_dir(release / "candidate")
for name in FILES:
    for folder in ("before", "candidate"):
        private_dir((release / folder / name).parent)
    write_atomic(release / "candidate" / name, candidates[name], 0o600)
    if originals[name] is not None:
        write_atomic(release / "before" / name, originals[name][0], 0o600)
snapshot = release / "equipment-before.db"
with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
    descriptor = os.open(snapshot, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with sqlite3.connect(snapshot) as target:
        source.backup(target)
evidence = {"baseline_head": head, "old_pid": old_pid, "release": str(release),
            "db_before": before, "files": {n: {"before": sha(originals[n][0]) if originals[n] else None,
                                           "after": sha(candidates[n])} for n in sorted(FILES)}}
write_atomic(release / "manifest.json", json.dumps(evidence, indent=2).encode(), 0o600)
changed = []
stopped = False
new_process = None
try:
    stop_pid(old_pid, command_bytes)
    stopped = True
    for name in sorted(FILES):
        mode = originals[name][1] if originals[name] else 0o644
        write_atomic(ROOT / name, candidates[name], mode)
        changed.append(name)
    for name in FILES:
        assert sha((ROOT / name).read_bytes()) == data["files"][name]["sha256"]
    new_process = start_process(command, environment, release, "service-start")
    after = db_state(database)
    assert after == before, "business counts or integrity changed"
    evidence.update(status="deployed", new_pid=new_process.pid, db_after=after, health=200)
except BaseException as error:
    if new_process is not None and new_process.poll() is None:
        stop_pid(new_process.pid)
    for name in reversed(changed):
        if originals[name] is None:
            assert sha((ROOT / name).read_bytes()) == sha(candidates[name])
            (ROOT / name).unlink()
        else:
            write_atomic(ROOT / name, originals[name][0], originals[name][1])
    if stopped:
        recovered = start_process(command, environment, release, "service-rollback")
        evidence.update(rollback_pid=recovered.pid, rollback_health=200)
    evidence.update(status="failed", error_type=type(error).__name__)
    write_atomic(release / "result.json", json.dumps(evidence, indent=2).encode(), 0o600)
    print(json.dumps(evidence))
    raise
write_atomic(release / "result.json", json.dumps(evidence, indent=2).encode(), 0o600)
print(json.dumps(evidence))
