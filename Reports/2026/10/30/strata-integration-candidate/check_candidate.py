"""Static-only candidate validation. Does not import or start the application."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from jinja2 import Environment


def inspect_candidate(candidate):
    """[역할] 후보의 문법·통합·자원·인증 구성을 실행 없이 확인합니다.
    [의존성 관계] 원본 해시, AST, Jinja parser, node --check.
    [변경 시 영향도] 앱 import, DB 열기, 코드 병합과 서버 실행을 수행하지 않습니다.
    """
    candidate = candidate.resolve()
    project = candidate.parent.parent
    overlay = candidate / 'overlay'
    manifest = json.loads((candidate / 'candidate.json').read_text(encoding='utf-8'))
    original_bytes = (project / 'app.py').read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    assert original_hash == manifest['base_app_sha256'], 'app.py changed; rebase the candidate instead of overwriting it'
    source = original_bytes.decode('utf-8-sig')
    for change in manifest['app_edits']:
        assert source.count(change['find']) == 1, 'An integration anchor is missing or ambiguous'
        source = source.replace(change['find'], change['replace'], 1)
    parsed_app = ast.parse(source, filename='candidate/app.py')
    assert any(isinstance(node, ast.ImportFrom) and node.module == 'utils.strata_integration' for node in parsed_app.body)
    install_calls = [node for node in ast.walk(parsed_app) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == 'install_strata']
    assert len(install_calls) == 1, 'Integration must be installed exactly once'
    checked = {'python': [], 'javascript': [], 'templates': []}
    for filename in overlay.rglob('*'):
        if filename.is_file():
            assert not (project / filename.relative_to(overlay)).exists(), 'An overlay target already exists; review instead of overwriting it'
    for filename in sorted(overlay.rglob('*.py')):
        ast.parse(filename.read_text(encoding='utf-8-sig'), filename=str(filename))
        checked['python'].append(str(filename.relative_to(overlay)))
    ast.parse(Path(__file__).read_text(encoding='utf-8'), filename=__file__)
    for filename in sorted([*overlay.rglob('*.js'), *overlay.rglob('*.mjs')]):
        result = subprocess.run(['node', '--check', str(filename)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        checked['javascript'].append(str(filename.relative_to(overlay)))
    environment = Environment()
    for filename in sorted((overlay / 'templates').glob('*.html')):
        text = filename.read_text(encoding='utf-8')
        environment.parse(text)
        for resource in re.findall(r'(?:href|src)="(/static/[^"#]+)', text):
            assert (overlay / resource.lstrip('/')).is_file() or (project / resource.lstrip('/')).is_file(), resource
        checked['templates'].append(filename.name)
    module = (overlay / 'utils/strata_integration.py').read_text(encoding='utf-8')
    module_ast = ast.parse(module)
    install = next(n for n in module_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'install_strata')
    routes = [n for n in install.body if isinstance(n, ast.FunctionDef) and any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and isinstance(d.func.value, ast.Name) and
        d.func.value.id == 'blueprint' and d.func.attr == 'get' for d in n.decorator_list)]
    assert len(routes) == 4
    assert all(any(isinstance(d, ast.Name) and d.id == 'login_required' for d in n.decorator_list) for n in routes)
    assert all('admin_allowed' in ast.unparse(n) for n in routes)
    assert 'STRATA_API_KEY' not in module, 'The application must not hold or return the shared key'
    assert not re.search(r'\b(?:DELETE FROM|DROP TABLE|UPDATE menus)\b', module, re.I)
    assert 'INSERT OR IGNORE INTO menus' in module and 'hmac.compare_digest' in module
    assert "app.config.get('STRATA_ENABLED') is True" in module
    config = (overlay / 'systemd/nginx-strata.conf.example').read_text(encoding='utf-8')
    for required in ('auth_request /_eqmgmt_strata_auth;', 'internal;', 'proxy_buffering off;',
                     'proxy_cache off;', 'proxy_next_upstream off;', 'proxy_ignore_client_abort off;',
                     'proxy_set_header Cookie "";', 'proxy_set_header X-CSRFToken "";',
                     'set $strata_original_method $request_method;', 'set $strata_original_uri $request_uri;',
                     'include /etc/nginx/private/strata-upstream-key.conf;'):
        assert required in config, required
    assert not re.search(r'proxy_pass\s+\$', config), 'Client-selected upstreams are forbidden'
    console = (overlay / 'templates/strata_console.html').read_text(encoding='utf-8')
    assert console.index("filename='js/strata_bridge.js'") < console.index('/static/vendor/strata/app.js')
    assert '<base href="/strata/">' in console and 'data-managed-api-key' in console
    vendor = (overlay / 'static/vendor/strata/app.js').read_text(encoding='utf-8')
    assert 'const base = location.origin;' not in vendor and 'const SPRITE = "web/' not in vendor
    assert 'runs on this PC. Nothing leaves it.' not in vendor and 'mcp: false' in vendor
    assert 'MIT License' in (overlay / 'static/vendor/strata/LICENSE.txt').read_text(encoding='utf-8')
    bridge = (overlay / 'static/js/strata_bridge.js').read_text(encoding='utf-8')
    for required in ("headers.delete('Authorization')", "headers.delete('x-api-key')",
                     "headers.set('X-CSRFToken', csrf)", "cache:'no-store'", "key === 'strata.apikey'",
                     "new URL(input instanceof Request ? input.url : input, document.baseURI)"):
        assert required in bridge, required
    test_ast = ast.parse((overlay / 'tests/test_strata_integration.py').read_text(encoding='utf-8'))
    tests = [node.name for node in ast.walk(test_ast) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    assert len(tests) >= 16
    return {'status': 'pass', 'mode': 'static-only', 'baseAppSha256': original_hash,
            'appIntegrationEdits': len(manifest['app_edits']), 'overlayTargetsNew': True, 'checks': checked,
            'linuxTestsPrepared': len(tests), 'bridgeTestsPrepared': 6,
            'applicationStarted': False, 'databaseOpened': False,
            'runtimeTestsRun': False, 'productionSourceModified': False,
            'overlayFiles': sum(1 for item in overlay.rglob('*') if item.is_file())}


if __name__ == '__main__':
    print(json.dumps(inspect_candidate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent),
                     ensure_ascii=False, indent=2))
