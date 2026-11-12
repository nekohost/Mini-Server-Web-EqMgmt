"""Run a scoped, entirely synthetic Node/Chromium regression on the authorized Linux host.

Transfers approved source text over SSH stdin, runs in /dev/shm and removes fixture.
Does not touch production databases, runtime files or server process.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[2]
project = next(p for p in (ROOT, *ROOT.parents) if (p / "AGENTS.md").is_file())
tests = [
    "tests/test_menu_workflows_static.mjs",
    "tests/test_mail_translation_ui.js",
    "tests/test_provider_ca_ui.js",
    "tests/test_access_log_cleanup_ui.mjs",
    "tests/test_access_log_session.mjs",
    "tests/test_admin_accounts_ui.mjs",
]
included = {}
for root in ("templates", "static/js", "static/css", "tests"):
    folder = project / root
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".js", ".mjs", ".css", ".html"):
            relative = path.relative_to(project).as_posix()
            included[relative] = path.read_text(encoding="utf-8-sig")
for name in tests:
    assert name in included

encoded = base64.b64encode(zlib.compress(json.dumps(included, ensure_ascii=False).encode(), 7)).decode()
remote = '''
import base64,json,os,pathlib,shutil,subprocess,tempfile,zlib
files=json.loads(zlib.decompress(base64.b64decode(PAYLOAD)))
folder=pathlib.Path(tempfile.mkdtemp(prefix='eq-nodeqa-',dir='/dev/shm'))
try:
    for name,source in files.items():
        p=folder/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(source,encoding='utf-8')
    env=os.environ.copy()
    env['NODE_PATH']='/home/nekohost/.hermes/hermes-agent/node_modules'
    env['PYTHON']='/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python'
    env['ADMIN_ACCOUNTS_BROWSER']='1'
    chrome=shutil.which('chromium') or shutil.which('chromium-browser')
    if chrome: env['CHROME_BIN']=chrome
    env['TMPDIR']='/dev/shm'
    node='/home/nekohost/.hermes/node/bin/node'
    cases=CASES
    r=subprocess.run([node,'--test',*cases],cwd=folder,env=env,text=True,capture_output=True,timeout=240)
    lines=r.stdout.splitlines()
    summary=[x.strip() for x in lines if x.strip().startswith(('ℹ tests','ℹ pass','ℹ fail','ℹ skipped','ℹ duration'))]
    if r.returncode:
        print('NODE_TEST_FAILURE_DETAIL='+r.stderr[-2000:]+r.stdout[-3500:])
    print('NODE_QA='+json.dumps({'exit':r.returncode,'summary':summary,'browser_path':chrome,'test_files':len(cases)},ensure_ascii=False))
finally:
    shutil.rmtree(folder,ignore_errors=True)
'''.replace("PAYLOAD",repr(encoded)).replace("CASES",repr(tests))
result = subprocess.run(
    ["ssh","-o","BatchMode=yes","eqmgmt-backup",
     "/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python","-"],
    input=remote,encoding="utf-8",text=True,capture_output=True,timeout=300
)
print(result.stdout.encode('ascii','backslashreplace').decode('ascii'))
if result.stderr: print(result.stderr[-2200:].encode('ascii','backslashreplace').decode('ascii'))
raise SystemExit(result.returncode)
