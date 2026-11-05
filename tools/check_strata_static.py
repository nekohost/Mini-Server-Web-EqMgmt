"""Statically check the retired gateway and administrator candidate without importing the app or opening DBs."""
import ast
import json
from pathlib import Path
import re
import subprocess

from jinja2 import Environment


def inspect(root):
    """[MINI-COMMENT: STRATA.STATIC.CHECK]
    [EN rev.2]
    [Role] Parses retirement/admin sources and validates that Nginx cannot proxy the old UI.
    [Dependencies] Python AST, Jinja parsing, node --check and the exact removal manifest.
    [Impact] Safe on Windows: does not run application imports, behavior tests, services or database access.
    """
    python_files = ['app.py', 'utils/strata_integration.py', 'tools/deploy_user_ai.py',
                    'tools/deploy_strata.py', 'tools/write_strata_nginx_key.py',
                    'tools/check_strata_static.py', 'tests/test_strata_integration.py', 'tests/test_admin_release.py',
                    'tests/admin_providers_browser_fixture.py']
    javascript_files = ['static/js/equipment_ai_providers.js', 'tests/test_strata_bridge.mjs']
    templates = ['templates/strata_retired.html', 'templates/equipment_ai_providers.html']
    for name in python_files:
        ast.parse((root / name).read_text(encoding='utf-8-sig'), filename=name)
    app = ast.parse((root / 'app.py').read_text(encoding='utf-8-sig'))
    calls = [node for node in ast.walk(app) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'install_strata']
    assert len(calls) == 1
    for name in javascript_files:
        check = subprocess.run(['node', '--check', str(root / name)], capture_output=True, text=True, check=False)
        assert check.returncode == 0, check.stderr
    parser = Environment()
    for name in templates:
        parser.parse((root / name).read_text(encoding='utf-8'))
    nginx = (root / 'systemd/nginx-strata.conf.example').read_text(encoding='utf-8')
    assert not re.search(r'(?m)^\s*(?:proxy_pass|auth_request|include)\b', nginx)
    manifest = json.loads((root / 'docs/strata-retirement-manifest.json').read_text(encoding='utf-8'))
    for name in manifest['remove_public_files_after_denial']:
        assert not name.startswith(('/', '\\')) and '..' not in name.split('/') and '*' not in name
        assert name.startswith(('templates/strata', 'static/js/strata_', 'static/css/strata', 'static/vendor/strata/'))
        assert name not in manifest['preserve_attribution_in_repository']
    release = (root / 'tools/deploy_user_ai.py').read_text(encoding='utf-8')
    assert '/etc/nginx/private/strata-upstream-key.conf' not in release
    return {'status': 'pass', 'mode': 'static-only', 'python': len(python_files),
            'javascript': len(javascript_files), 'templates': len(templates),
            'manifest_removal_files': len(manifest['remove_public_files_after_denial']),
            'application_started': False, 'database_opened': False, 'behavior_tests_run': False}


if __name__ == '__main__':
    print(json.dumps(inspect(Path(__file__).resolve().parents[1]), indent=2))
