"""Static review of the security candidate. Does not import the application or open a DB."""
import ast
from pathlib import Path
import re
import subprocess
import unittest

from jinja2 import Environment


CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = CANDIDATE.parents[1] if CANDIDATE.parent.name == 'Staging' else CANDIDATE


def source(name):
    candidate = CANDIDATE / name
    return (candidate if candidate.is_file() else ROOT / name).read_text(encoding='utf-8-sig')


def files(pattern, folders):
    found = set()
    for tree in (ROOT, CANDIDATE):
        for folder in folders:
            found.update(p.relative_to(tree).as_posix() for p in (tree / folder).rglob(pattern) if p.is_file())
    return sorted(found)


APP = source('app.py')


def function(name, code=APP):
    node = next(item for item in ast.walk(ast.parse(code))
                if isinstance(item, ast.FunctionDef) and item.name == name)
    return ast.get_source_segment(code, node)


class StaticSecurity(unittest.TestCase):
    def test_all_first_party_python(self):
        names = files('*.py', ['utils', 'tools', 'tests'])
        names += sorted({p.name for p in ROOT.glob('*.py')})
        for name in names:
            with self.subTest(file=name):
                compile(source(name), name, 'exec')
        print('Python files compiled:', len(names))

    def test_templates_and_javascript(self):
        js = files('*.js', ['static/js'])
        for name in js:
            with self.subTest(file=name):
                subprocess.run(['node', '--check', '-'], input=source(name), encoding='utf-8', check=True)
        templates = files('*.html', ['templates'])
        inline = 0
        for name in templates:
            content = source(name)
            Environment().parse(content)
            for block in re.findall(r'<script\b[^>]*>(.*?)</script>', content, re.I | re.S):
                if not block.strip():
                    continue
                block = re.sub(r'{{.*?}}', '0', block, flags=re.S)
                block = re.sub(r'{[%#].*?[%#]}', '', block, flags=re.S)
                with self.subTest(file=name, block=inline):
                    subprocess.run(['node', '--check', '-'], input=block, encoding='utf-8', check=True)
                inline += 1
        print('JS files, Jinja templates, inline JS blocks:', len(js), len(templates), inline)

    def test_audit_xss(self):
        for name, fields in [('access_logs', ['log.UserAgent', 'log.RequestPath', 'log.IpAddress', 'log.HttpMethod']),
                             ('audit_logs', ['log.ActorLoginId', 'log.ActorName', 'log.Details', 'log.Action']),
                             ('users_management', ['u.LoginId', 'u.Name', 'u.NickName'])]:
            markup = source(f'templates/{name}.html')
            for field in fields:
                self.assertIn('window.escapeMarkup(' + field, markup)
                self.assertNotIn(' + field + ', markup)
        for name in ('users_management', 'index'):
            handlers = re.findall(r'\bon(?:click|change)="([^"]*)"', source(f'templates/{name}.html'))
            self.assertFalse(any('u.LoginId' in item or 'u.NickName' in item for item in handlers))
        self.assertIn('this.dataset.nickname', source('templates/index.html'))
        self.assertIn('&#39;', source('static/js/common.js'))

    def test_audit_data(self):
        hook = function('after_request_func')
        self.assertNotIn('request.get_data', hook)
        self.assertIn('legacy_audit_payloads(', hook)
        self.assertIn('http_payloads(request, response, g)', hook)
        self.assertIn('audit_body(response_payload', hook)
        security = source('utils/http_security.py')
        for term in ['api_send_pin_logic', 'api_verify_pin_logic', 'api_reset_password_logic',
                     'register_page', 'api_change_my_password', 'api_update_profile', 'not response.is_streamed']:
            self.assertIn(term, security)
        self.assertIn("urlsplit(raw or '').path", security)
        self.assertIn('@admin_required\ndef api_get_access_log_payload', APP)
        detail = function('api_get_access_log_payload')
        self.assertIn('None if sensitive', detail)
        self.assertIn('http_audit_queue.protected_path(path)', detail)
        self.assertIn("'/internal/ai/'", source('utils/http_audit_queue.py'))
        self.assertIn('client_ip(request)', function('log_audit'))
        self.assertIn('referrer_path(request.referrer)', hook)
        self.assertIn('%%(U)s', source('systemd/mini-server-eqmgmt.service'))

    def test_account_and_session(self):
        self.assertNotIn("os.getenv('SECRET_KEY',", APP)
        self.assertIn("os.getenv('BOOTSTRAP_ADMIN_EMAIL'", function('register_page'))
        self.assertIn('SessionToken=NULL WHERE UserId=? AND SessionToken=?', function('logout'))
        self.assertIn("@app.route('/logout', methods=['POST'])", APP)
        for form in ('deactivated_notice', 'miniserver_frame'):
            self.assertIn('name="csrf_token"', source(f'templates/{form}.html'))
        policy = function('validate_and_limit', source('utils/roadmap_routes.py'))
        self.assertNotIn("endpoint != 'login_page'", policy)
        self.assertIn('if not csrf or csrf !=', policy)
        self.assertIn('AND Password=?', function('login_page'))
        cancel = function('api_user_withdraw_cancel')
        self.assertIn("SessionToken=? AND IsDeactivated='Y' AND IsDeleted='N'", cancel)
        self.assertIn('DeactivatedAt>?', cancel)
        self.assertIn('not db_token or not current_token', function('check_session'))
        passive = function('should_set_cookie', source('utils/ai_assistant/__init__.py'))
        self.assertNotIn("request.headers.get('X-Assistant-Poll')", passive)

    def test_email_and_reset(self):
        email = function('api_update_email')
        order = ['BEGIN IMMEDIATE', 'matches_email_verification', 'DELETE FROM email_verifications', 'UPDATE users', 'conn.commit()']
        self.assertEqual(sorted(email.index(v) for v in order), [email.index(v) for v in order])
        self.assertIn('AND PinCodeHash=? AND ExpiresAt>=?', function('api_verify_pin_logic'))
        self.assertIn('secrets.randbelow', function('api_send_pin_logic'))
        issue = function('api_request_password_reset_logic')
        self.assertNotIn('request.host', issue)
        self.assertIn("'/reset_password#'", issue)
        self.assertIn('window.location.hash.slice(1) || window.location.search', source('templates/reset_password.html'))
        consume = function('api_reset_password_logic')
        claim = 'WHERE TokenHash=? AND UserId=? AND IsUsed=0 AND ExpiresAt>?'
        self.assertLess(consume.index(claim), consume.index('UPDATE users SET Password='))
        self.assertIn('WHERE UserId=? AND IsUsed=0', consume)
        for name in ['api_change_my_password', 'api_reset_user_password', 'api_update_email']:
            self.assertIn('DELETE FROM password_resets', function(name))

    def test_web_grants_and_limits(self):
        for name in ('add_equipment', 'update_equipment', 'delete_equipment', 'api_dashboard_stats', 'api_dashboard_master_options', 'api_equipments_v2'):
            node = next(item for item in ast.parse(APP).body if getattr(item, 'name', '') == name)
            self.assertTrue(any(ast.unparse(dec).startswith('menu_required(') for dec in node.decorator_list))
        eq = source('utils/roadmap_equipment.py')
        self.assertIn('has_equipment_menu', function('require_equipment', eq))
        self.assertIn('has_equipment_menu', function('query_contract', eq))
        routes = source('utils/roadmap_routes.py')
        for name in ['csv_preview', 'csv_commit', 'csv_export']:
            self.assertIn('has_equipment_menu', function(name, routes))
        self.assertIn('SessionToken=?', function('actor', routes))
        self.assertIn('min(per_page, 1000)', function('api_get_access_logs'))
        self.assertIn('request.max_content_length = DATABASE_UPLOAD_LIMIT', function('api_upload_database_candidate'))

    def test_restore_must_have_verified_backup(self):
        restore = function('_run_database_restore_job')
        order = ['inspect_database_file(before_restore_path)', 'snapshot_verified = True', 'validate_database_compatibility(',
                 'live_write_started = True', 'candidate.backup(live_target', 'if live_write_started and snapshot_verified:',
                 'rollback_source.backup(live_target']
        self.assertEqual(sorted(restore.index(v) for v in order), [restore.index(v) for v in order])
        self.assertIn('candidate_contract.keys() - baseline_contract.keys()', function('validate_database_compatibility'))
        self.assertIn("lower(name) NOT GLOB 'sqlite_*'", source('utils/database_contract.py'))

    def test_required_audit_commit_and_cleanup(self):
        queued = source('utils/http_audit_queue.py')
        route = function('push_access_log')
        self.assertLess(route.index('_insert_access_logs([log_data], durable=True)'), route.index('access_log_queue.put_nowait'))
        self.assertIn('http_audit_queue.enqueue(AUDIT_SPOOL, log_data)', route)
        self.assertIn('access_log_bytes + size > ACCESS_LOG_QUEUE_BYTES', route)
        self.assertIn('access_log_bytes -=', function('_write_logs_to_db'))
        deliver = function('drain', queued)
        self.assertLess(deliver.index('persist(['), deliver.index('DELETE FROM pending WHERE id=?'))
        self.assertIn('PRAGMA synchronous=FULL', queued)
        self.assertIn('app.logger.critical', function('after_request_func'))
        cleanup = function('api_cleanup_access_logs')
        self.assertIn('http_audit_queue.cleanup_filter()', cleanup)
        self.assertIn("table='access_logs'", cleanup)
        self.assertNotIn("data.get('total_deleted'", cleanup)
        for event in ('UPDATE_ROLE', 'UPDATE_PERMISSIONS', 'FORCE_LOGOUT_SELECTED', 'CREATE_MASTER', 'UPDATE_MASTER'):
            self.assertIn("audit_lineup_change(conn, '" + event, APP)

    def test_scoped_one_time_approval(self):
        handler = function('process_approval')
        steps = ['BEGIN IMMEDIATE', 'SELECT * FROM approval_requests', "WHERE RequestId=? AND Status='PENDING'",
                 'decide(conn,', 'audit_lineup_change(', 'conn.commit()']
        self.assertEqual([handler.index(s) for s in steps], sorted(handler.index(s) for s in steps))
        decision = source('utils/approval_decision.py')
        for part in ('requested_by=?', 'e.user_id=? AND e.is_draft=1', 'n.id=? AND o.id=?',
                     "row['category_ready'] and row['maker_ready']", 'actual != allowed', 'len(rows) != 1'):
            self.assertIn(part, decision)
        self.assertIn('is_draft=0,is_public=0 WHERE id=? AND user_id=?', decision)
        add = function('add_equipment')
        self.assertIn('$.linked_equipment[#]', add)
        self.assertIn("AND RequesterId=? AND Status='PENDING'", add)
        self.assertNotIn('WHERE name = ? AND status', handler)

    def test_model_network_and_search_boundaries(self):
        provider = function('save', source('utils/ai_assistant/providers.py'))
        self.assertIn("origin(previous['base_url']) == base", provider)
        self.assertIn("previous['revoked'] is None", provider)
        self.assertIn("previous['credential'] if inherit else ''", provider)
        self.assertIn("if url.scheme == 'http' and not ip.is_loopback", source('utils/ai_assistant/transport.py'))
        trust = function('resolve_addresses', source('utils/ai_assistant/provider_trust.py'))
        self.assertIn('for address in answers:', trust)
        self.assertIn('check_peer(address)', trust)
        peers = function('check_peer', source('utils/ai_assistant/provider_trust.py'))
        self.assertIn('ip not in EQUIPMENT_LAN', peers)
        self.assertIn('EQUIPMENT_SERVER', peers)
        dispatch = function('run_job', source('utils/ai_assistant/worker.py'))
        self.assertIn("urlsplit(self.strata).hostname not in ('127.0.0.1','::1')", dispatch)
        deployment = source('tools/deploy_user_ai.py')
        self.assertIn("provider_origin(settings.get('USER_AI_STRATA_URL'), existing=True)", deployment)
        from urllib.parse import urlsplit
        namespace = {'urlsplit': urlsplit}
        exec(function('provider_origin', deployment), namespace)
        guard = namespace['provider_origin']
        legacy = 'http://192.168.0.14:8080'
        self.assertEqual(guard(legacy, existing=True), legacy)
        with self.assertRaises(ValueError):
            guard(legacy)
        for changed in ('http://192.168.0.15:8080', 'http://192.168.0.14:8081', 'http://key@192.168.0.14:8080'):
            with self.assertRaises(ValueError):
                guard(changed, existing=True)
        worker = function('worker', source('utils/ai_assistant/__init__.py'))
        self.assertIn('werkzeug.proxy_fix.orig', worker)
        self.assertIn("request.headers.get('X-Forwarded-For')", worker)
        boundary = function('read_or_prepare', source('utils/ai_assistant/domain.py'))
        self.assertIn("WHERE job=? AND role='user' AND conversation=?", boundary)
        self.assertLess(boundary.index('current_search_terms('), boundary.index('self.search_service.search('))
        self.assertIn("unicodedata.normalize('NFKC'", source('utils/ai_assistant/web_search.py'))

    def test_export_account_budget_and_legacy_state(self):
        export = function('preserve_export', source('utils/ai_assistant/audit.py'))
        for part in ('WHERE owner=? AND sha256=? AND bytes=?', 'blob_id IS NULL OR blob_id=id',
                     'recent >= 30', 'maximum // 2', 'digest.hexdigest() != sha', 'if new_file is not None:'):
            self.assertIn(part, export)
        self.assertIn('ALTER TABLE ai_audit_artifacts ADD COLUMN blob_id TEXT', export)
        self.assertIn("is_public = row['IsPublic'] if not is_draft", source('db_migration.py'))
        for name in ('migrate_passwords_to_hash', 'migrate_email_features'):
            node = ast.parse(function(name)).body[0]
            self.assertTrue(any(isinstance(item, ast.Raise) for item in ast.walk(node)))
        self.assertIn("len(app.secret_key.strip().encode('utf-8')) < 32", APP)
        email = function('api_update_email')
        self.assertLess(email.index("check_password_hash(account['Password']"), email.index('DELETE FROM email_verifications'))
        self.assertIn("'api_update_email': (5,", source('utils/roadmap_auth.py'))

    def test_application_wheel_lock(self):
        self.assertIn('-r requirements-app.lock', source('requirements.txt'))
        lock = source('requirements-app.lock')
        self.assertIn('--only-binary=:all:', lock)
        self.assertIn('--require-hashes', lock)
        groups = re.split(r'(?m)(?=^[A-Za-z0-9_-]+==)', lock)[1:]
        for group in groups:
            self.assertTrue(re.search(r'--hash=sha256:[0-9a-f]{64}(?:\s|$)', group))
        for direct in ('Flask', 'requests', 'python-dotenv', 'cryptography'):
            self.assertTrue(any(group.startswith(direct + '==') for group in groups))

    def test_third_party_browser_code(self):
        self.assertNotIn('cdn.tailwindcss.com', source('templates/root_frame.html'))
        for name in ['templates/root_frame.html', 'templates/dashboard.html']:
            for tag in re.findall(r'<(?:script|link)\b[^>]+>', source(name)):
                if re.search(r'(?:src|href)="https://', tag):
                    self.assertIn('integrity="sha384-', tag)
                    self.assertIn('crossorigin="anonymous"', tag)


if __name__ == '__main__':
    unittest.main(verbosity=2)
