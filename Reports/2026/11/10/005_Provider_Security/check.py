"""Run isolated equipment regressions on Linux against a checkout with no production secrets."""
import importlib
import ipaddress
import json
import os
from pathlib import Path
import sys
import unittest

root = Path.cwd().resolve()
assert sys.platform.startswith('linux') and not (root / '.env').exists() and not (root / 'equipment.db').exists()
os.environ.update(EQ_TEST_PROJECT_ROOT=str(root), USER_AI_WEB_SEARCH='false', PYTHONDONTWRITEBYTECODE='1',
                  SECRET_KEY='synthetic-provider-security-qa-secret-only-000')
sys.path[:0] = [str(root/'tests'), str(root)]


def local_sockets_only(event, args):
    if event in ('socket.connect','socket.sendto'):
        target = args[1]
        if not isinstance(target,tuple) or not ipaddress.ip_address(target[0]).is_loopback:
            raise AssertionError('non-loopback socket in isolated regression')


sys.addaudithook(local_sockets_only)
import test_equipment_ai
sys.modules['assistant_fixture_tests'] = test_equipment_ai
import test_multi_provider_ai
sys.modules['assistant_provider_fixture_tests'] = test_multi_provider_ai
suite = unittest.TestSuite()
for name in sys.argv[1:]:
    module = importlib.import_module(name)
    if name in ('test_admin_release','test_strata_integration'):
        module.SOURCE_APP = (root/'app.py').read_text()
        module.CANDIDATE_ASSETS = {p.relative_to(root).as_posix():p.read_text() for p in (root/'templates').glob('*.html')}
        files = ('tools/deploy_user_ai.py','tools/deploy_strata.py','tools/write_strata_nginx_key.py',
                 'systemd/nginx-strata.conf.example','docs/strata-retirement-manifest.json')
        module.CANDIDATE_FILES = {k:(root/k).read_text() for k in files}
    if name == 'test_ai_conversation_lifecycle':
        cli = 'tools/ai_retention_cleanup.py'
        module.CANDIDATE_FILES = {cli:(root/cli).read_text()}
    for item in vars(module).values():
        if isinstance(item,type) and issubclass(item,unittest.TestCase) and item.__module__ == name:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(item))
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps(dict(run=result.testsRun, failures=[t.id() for t,_ in result.failures],
                      errors=[t.id() for t,_ in result.errors], skipped=len(result.skipped))),flush=True)
raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
