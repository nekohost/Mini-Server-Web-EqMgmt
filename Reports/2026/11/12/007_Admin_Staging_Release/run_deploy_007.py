"""Transmit a reviewed Linux release utility in memory over an SSH stdin pipeline."""
import pathlib
import subprocess
import sys

source = pathlib.Path(__file__).with_name("deploy_admin_007.py").read_text(encoding="utf-8")
args = sys.argv[1:]
if not (len(args) == 1 or len(args) == 2 and args[0] == "--preflight"):
    raise ValueError("expected --preflight <full commit> or <full commit>")
command = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "eqmgmt-backup",
    "/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python", "-", *args,
]
result = subprocess.run(command, input=source, text=True, encoding="utf-8",
                        capture_output=True, timeout=900)
print(result.stdout.encode("ascii", "backslashreplace").decode("ascii"))
if result.stderr:
    print("RELEASE_STDERR=" + result.stderr[-4500:].encode("ascii", "backslashreplace").decode("ascii"))
print("RELEASE_EXIT=" + str(result.returncode))
raise SystemExit(result.returncode)
