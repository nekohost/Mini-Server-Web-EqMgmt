"""Read-only live business/AI DB and feature menu verification via SSH."""
import subprocess

script = r'''
from contextlib import closing
import json,os,sqlite3,subprocess
from pathlib import Path
root=Path("/home/nekohost/services/Mini-Server-Web-EqMgmt")
equipment=root/"equipment.db"
assistant=root/"instance/ai/assistant.sqlite3"
check={"git":subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,check=True).stdout.strip()}
with closing(sqlite3.connect(equipment.as_uri()+"?mode=ro",uri=True)) as db:
    check["users"]=db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    check["menus"]=db.execute("SELECT COUNT(*) FROM menus WHERE MenuCode='equipment_ai_logs'").fetchone()[0]
    check["ai_menu_permissions"]=list(db.execute("SELECT Role,IsAllowed FROM role_menu_permissions WHERE MenuCode='equipment_ai_logs' ORDER BY Role"))
    check["equipment_integrity"]=db.execute("PRAGMA integrity_check").fetchone()[0]
    check["equipment_fks"]=len(db.execute("PRAGMA foreign_key_check").fetchall())
with closing(sqlite3.connect(assistant.as_uri()+"?mode=ro",uri=True)) as db:
    check["ai_conversations"]=db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    check["ai_jobs"]=db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    check["ai_messages"]=db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    check["ai_integrity"]=db.execute("PRAGMA integrity_check").fetchone()[0]
    check["ai_fks"]=len(db.execute("PRAGMA foreign_key_check").fetchall())
worker=subprocess.run(["systemctl","--user","show","equipment-ai-worker.service","--property=MainPID","--value"],capture_output=True,text=True,check=True)
check["worker_pid"]=int(worker.stdout.strip())
check["active"]=subprocess.run(["systemctl","--user","is-active","equipment-ai-worker.service"],capture_output=True,text=True,check=True).stdout.strip()
check["status"]="pass" if (check["git"].startswith("b8192a1") and check["users"]==8 and check["menus"]==1 and
                              ["admin",1] in [list(row) for row in check["ai_menu_permissions"]] and
                              check["ai_jobs"]>=54 and check["worker_pid"]==1653197 and check["active"]=="active" and
                              check["equipment_integrity"]=="ok" and check["ai_integrity"]=="ok" and
                              check["equipment_fks"]==0 and check["ai_fks"]==0) else "fail"
print(json.dumps(check,ensure_ascii=True))
raise SystemExit(0 if check["status"]=="pass" else 1)
'''
r=subprocess.run(["ssh","-o","BatchMode=yes","eqmgmt-backup",
                  "/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python","-"],
                 input=script,encoding="utf-8",text=True,capture_output=True,timeout=45)
print(r.stdout.encode("ascii","backslashreplace").decode("ascii"))
if r.stderr: print(r.stderr[-2400:].encode("ascii","backslashreplace").decode("ascii"))
print("CHECK_EXIT="+str(r.returncode))
raise SystemExit(r.returncode)
