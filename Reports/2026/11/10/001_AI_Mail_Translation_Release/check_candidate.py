"""Run the production-baseline regression fixture on a separate Linux checkout."""
import ast
import hashlib
import importlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from jinja2 import Environment

root=Path.cwd()
m=json.loads((root/'SOURCE_SHA256.json').read_text('utf8'))
assert m['variant']=='translation-only'
for name,expected in m['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected
for p in [root/'app.py', *(root/'utils').rglob('*.py'), *(root/'tests').rglob('*.py')]:
    ast.parse(p.read_text('utf-8-sig'),filename=str(p))
for p in (root/'templates').rglob('*.html'):
    Environment().parse(p.read_text('utf-8-sig'))
for k in m['files']:
    if k.endswith('.js'):
        subprocess.run([shutil.which('node') or 'node','--check',k],check=True)

def loopback(event,args):
    if event in {'socket.connect','socket.sendto'}:
        target=args[1]
        if not isinstance(target,tuple) or not ipaddress.ip_address(target[0]).is_loopback:
            raise RuntimeError('external connection in synthetic regression')

sys.addaudithook(loopback)
for k in tuple(os.environ):
    if k.startswith('USER_AI_'):del os.environ[k]
os.environ.update(EQ_TEST_PROJECT_ROOT=str(root),USER_AI_WEB_SEARCH='false',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=[str(root/'tests'),str(root)]
import test_equipment_ai
sys.modules['assistant_fixture_tests']=test_equipment_ai
import test_multi_provider_ai
sys.modules['assistant_provider_fixture_tests']=test_multi_provider_ai
modules=['test_mail_translation','test_equipment_ai','test_multi_provider_ai','test_ai_input_reliability',
         'test_ai_conversation_entry','test_ai_conversation_lifecycle','test_ai_ux_integration',
         'test_ai_display_policy','test_ai_input_preferences','test_ai_release_guard','test_ai_web_search',
         'test_ai_polish_lifecycle','test_ai_polish_status']
suite=unittest.TestSuite()
for name in modules:
    mod=importlib.import_module(name)
    if name=='test_ai_conversation_lifecycle':
        cli='tools/ai_retention_cleanup.py'
        mod.CANDIDATE_FILES={cli:(root/cli).read_text('utf8')}
    for cls in vars(mod).values():
        if isinstance(cls,type) and issubclass(cls,unittest.TestCase) and cls.__module__==mod.__name__:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
result=unittest.TextTestRunner(verbosity=1).run(suite)
summary={'run':result.testsRun,'skipped':len(result.skipped),'failures':[x.id() for x,_ in result.failures],
         'errors':[x.id() for x,_ in result.errors],'python':sys.version.split()[0]}
print(json.dumps(summary),flush=True)
if result.wasSuccessful() and not result.skipped:
    (root.parent/'linux-qa.json').write_text(json.dumps(summary,indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
