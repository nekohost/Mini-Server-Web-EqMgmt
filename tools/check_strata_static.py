"""Parse the merged Strata sources without importing the application or opening DBs."""

import ast
import json
from pathlib import Path
import subprocess

from jinja2 import Environment


def inspect(root):
    """[MINI-COMMENT: STRATA.STATIC.CHECK]
    [EN rev.1]
    [Role] Checks source syntax and the three approved app integration points.
    [Dependencies] Python AST, Jinja parser and node --check; no app imports.
    [Impact] Safe on the Windows authoring PC; does not run behavior tests.
    """
    python_files = ['app.py', 'utils/strata_integration.py',
                    'tools/write_strata_nginx_key.py', 'tools/check_strata_static.py',
                    'tests/test_strata_integration.py']
    javascript_files = ['static/js/strata_bridge.js', 'static/js/strata_page.js',
                        'static/vendor/strata/app.js', 'tests/test_strata_bridge.mjs']
    templates = ['templates/strata.html', 'templates/strata_console.html']
    for name in python_files:
        ast.parse((root / name).read_text(encoding='utf-8-sig'), filename=name)
    app = ast.parse((root / 'app.py').read_text(encoding='utf-8-sig'))
    assert any(isinstance(n, ast.ImportFrom) and n.module == 'utils.strata_integration'
               for n in app.body)
    calls = [n for n in ast.walk(app) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'install_strata']
    assert len(calls) == 1
    portal = next(n for n in app.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'get_portal_menus')
    assert 'visible_portal_menus(rows, role, app.config)' in ast.unparse(portal)
    for name in javascript_files:
        check = subprocess.run(['node', '--check', str(root / name)],
                               capture_output=True, text=True, check=False)
        assert check.returncode == 0, check.stderr
    parser = Environment()
    for name in templates:
        parser.parse((root / name).read_text(encoding='utf-8'))
    return {'status': 'pass', 'mode': 'static-only', 'python': len(python_files),
            'javascript': len(javascript_files), 'templates': len(templates),
            'application_started': False, 'database_opened': False,
            'behavior_tests_run': False}


if __name__ == '__main__':
    print(json.dumps(inspect(Path(__file__).resolve().parents[1]), indent=2))
