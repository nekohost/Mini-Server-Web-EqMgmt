"""[MINI-COMMENT: ASSISTANT.RELEASE.RETIREMENT.TESTS]
[EN rev.1]
[Role] Verifies protected key bootstrap and retired deployment helpers on isolated Linux files.
[Dependencies] In-memory candidate text, extracted helper AST and temporary owner-only directories.
[Impact] Never executes a release action, reads an actual key, edits Nginx or controls a service.
"""
import ast
import base64
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit
import unittest
from unittest.mock import Mock, patch


@unittest.skipUnless(os.name == 'posix', 'Private-file behavior is validated on isolated Linux fixtures')
class AssistantReleaseRetirementTests(unittest.TestCase):
    """[Role] Runs only the extracted key helpers, with every path redirected to a temporary directory."""

    def setUp(self):
        """[Role] Extracts the reviewed functions without executing module imports or its release main."""
        self.temp = tempfile.TemporaryDirectory(prefix='eq-release-key-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.config_dir = self.root / 'config'
        self.config_dir.mkdir(mode=0o700)
        self.config = self.config_dir / 'assistant-worker.env'
        self.key = self.root / 'key.txt'
        self.key.write_bytes(b'synthetic-not-a-real-key\n')
        self.key.chmod(0o600)
        self.uid, self.gid = os.getuid(), os.getgid()
        self.account = SimpleNamespace(pw_uid=self.uid, pw_gid=self.gid)
        source = CANDIDATE_FILES['tools/deploy_user_ai.py']
        tree = ast.parse(source)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in
                     ('save', 'read_private_key', 'provider_origin', 'prepare')]
        self.assertEqual(len(functions), 4)
        self.namespace = dict(os=os, Path=Path, stat=stat, pwd=SimpleNamespace(getpwnam=lambda _: self.account),
                              CONFIG=self.config, base64=base64, secrets=secrets, json=json, urlsplit=urlsplit)
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<candidate-key-helpers>', 'exec'), self.namespace)

    def prepare(self, path=None):
        """[Role] Emulates only the root identity assertion while writing to the test user's own private files."""
        with patch.dict(os.environ, {'SUDO_USER': 'nekohost'}), patch('os.geteuid', return_value=0):
            return self.namespace['prepare'](path, provider_url='https://192.168.0.51:8443')

    def test_explicit_input_creates_independent_config_without_old_include(self):
        """[Role] Checks the fresh bootstrap path, key continuity and owner-only resulting permissions."""
        result = self.prepare(self.key)
        self.assertFalse(result['legacy_nginx_dependency'])
        self.assertFalse(result['secrets_disclosed'])
        self.assertTrue(result['key_input_read'])
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        values = dict(line.split('=', 1) for line in self.config.read_text().splitlines())
        self.assertEqual(json.loads(values['USER_AI_STRATA_KEY']), 'synthetic-not-a-real-key')
        self.assertTrue(json.loads(values['USER_AI_PROVIDER_ENCRYPTION_KEY']))
        self.assertNotIn('/etc/nginx/private/strata-upstream-key.conf', CANDIDATE_FILES['tools/deploy_user_ai.py'])

    def test_existing_config_is_byte_preserved_and_key_input_not_read(self):
        """[Role] Prevents an existing private environment from being overwritten or its key implicitly rotated."""
        original = b'USER_AI_STRATA_KEY="synthetic-existing-key"\nUSER_AI_ALLOWED_ENDPOINTS="preserve-me"\n'
        self.config.write_bytes(original)
        self.config.chmod(0o600)
        reader = Mock(side_effect=AssertionError('Existing configuration must not read input'))
        self.namespace['read_private_key'] = reader
        result = self.prepare(self.root / 'does-not-exist')
        reader.assert_not_called()
        self.assertTrue(result['existing_config_preserved'])
        self.assertEqual(self.config.read_bytes(), original)

    def test_missing_input_for_new_config_fails_before_any_write(self):
        """[Role] Requires an explicit source for a new configuration instead of silently reusing Nginx secrets."""
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.config.exists())

    def test_input_permissions_symlinks_newlines_and_placeholders_are_rejected(self):
        """[Role] Exercises real filesystem rejection cases without disclosing any input content."""
        read = self.namespace['read_private_key']
        self.key.chmod(0o644)
        with self.assertRaises(PermissionError):
            read(self.key, self.uid)
        self.key.chmod(0o600)
        alias = self.root / 'alias'
        alias.symlink_to(self.key)
        with self.assertRaises(ValueError):
            read(alias, self.uid)
        for payload in (b'first\nsecond', b'<actual-key>', b'x' * 8193, b'bad\x00key'):
            with self.subTest(payload_length=len(payload)):
                self.key.write_bytes(payload)
                with self.assertRaises((ValueError, PermissionError)):
                    read(self.key, self.uid)
        with self.assertRaises(ValueError):
            read(Path('relative-key.txt'), self.uid)

    def test_unsafe_existing_config_is_not_repaired_or_overwritten(self):
        """[Role] Fails closed on unsafe current credentials instead of taking ownership or normalizing them."""
        self.config.write_bytes(b'preserve-unsafe-fixture')
        self.config.chmod(0o644)
        with self.assertRaises(PermissionError):
            self.prepare(self.key)
        self.assertEqual(self.config.read_bytes(), b'preserve-unsafe-fixture')
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o644)

    def test_old_installer_and_key_writer_fail_before_mutation(self):
        """[Role] Verifies former public helper entry points now terminate with no import-time file access."""
        namespace = {'__name__': 'isolated_retired_helper'}
        exec(compile(CANDIDATE_FILES['tools/deploy_strata.py'], '<retired-installer>', 'exec'), namespace)
        with self.assertRaises(RuntimeError):
            namespace['insert_include']('server { keep existing; }')
        with self.assertRaises(SystemExit):
            namespace['main']()
        namespace = {'__name__': 'isolated_retired_key_helper'}
        exec(compile(CANDIDATE_FILES['tools/write_strata_nginx_key.py'], '<retired-key-writer>', 'exec'), namespace)
        with self.assertRaises(RuntimeError):
            namespace['write_key_include'](self.root / 'must-not-exist', 'synthetic-key')
        self.assertFalse((self.root / 'must-not-exist').exists())

    def test_nginx_candidate_denies_legacy_namespaces_without_upstream_directives(self):
        """[Role] Checks the dedicated configuration's active directives and required terminal locations."""
        nginx = '\n'.join(line for line in CANDIDATE_FILES['systemd/nginx-strata.conf.example'].splitlines() if not line.strip().startswith('#'))
        for forbidden in ('proxy_pass', 'auth_request', 'include /etc'):
            self.assertNotIn(forbidden, nginx)
        for path in ('/strata', '/api/strata', '/_eqmgmt_strata_auth', '/static/vendor/strata/'):
            self.assertIn(path, nginx)
        self.assertNotIn('USER_AI_', nginx)

    def test_manifest_removes_only_exact_public_ui_paths_and_preserves_runtime_licenses(self):
        """[Role] Guards removal scope against accidental shared-service, key, history or attribution deletion."""
        manifest = json.loads(CANDIDATE_FILES['docs/strata-retirement-manifest.json'])
        protected = set(manifest['preserve_attribution_in_repository'])
        for name in manifest['remove_public_files_after_denial']:
            self.assertNotIn(name, protected)
            self.assertFalse(name.startswith(('/', 'instance/', 'utils/ai_assistant/')))
            self.assertNotIn('*', name)
            self.assertNotIn('..', name.split('/'))
        self.assertIn('USER_AI_*', manifest['preserve_runtime_paths_or_names'])
        self.assertIn('Do not delete or merge', manifest['browser_history'])
