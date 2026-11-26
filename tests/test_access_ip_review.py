"""Linux 격리 fixture에서 접근 로그와 AI 작업 계약을 확인합니다."""

import gzip
import json
import locale
import sys
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta

if 'assistant_fixture_tests' in sys.modules:
    import assistant_fixture_tests as fixture
else:
    try:
        from . import test_equipment_ai as fixture
    except ImportError:
        import test_equipment_ai as fixture
from utils.ai_assistant import access_ip_review as review


API = '/api/admin/ai/access-ip-reviews'
TOKEN = 'synthetic-private-query'


@unittest.skipUnless(sys.platform.startswith('linux'), 'isolated Linux fixture only')
class AccessIpReviewTests(unittest.TestCase):
    connect = fixture.AssistantTests.connect
    login = fixture.AssistantTests.login
    claim = fixture.AssistantTests.claim

    def setUp(self):
        fixture.AssistantTests.setUp(self)
        self.directory = self.root / 'nginx'
        self.directory.mkdir()
        self.app.config['ACCESS_IP_NGINX_LOG_DIR'] = str(self.directory)
        self.login(1)
        self.change("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed) VALUES('admin','access_logs',1)")
        self.now = datetime.now(review.KST).replace(microsecond=0) - timedelta(minutes=1)
        self.nginx = []

    def change(self, sql, parameters=()):
        with closing(self.connect()) as db, db:
            db.execute(sql, parameters)

    def seed(self, ip, path, seconds=0, *, edge=True, query='', status=404, app_ip=None, method='GET'):
        at = self.now + timedelta(seconds=seconds)
        self.change('''INSERT INTO access_logs
            (IpAddress,HttpMethod,RequestPath,StatusCode,CreatedAt,RequestPayload)
            VALUES(?,?,?,?,?,?)''', (app_ip or ip, method, path, status, at.strftime(review.STAMP), TOKEN))
        if edge:
            original = locale.setlocale(locale.LC_TIME)
            try:
                locale.setlocale(locale.LC_TIME, 'C')
                timestamp = at.strftime('%d/%b/%Y:%H:%M:%S %z')
            finally:
                locale.setlocale(locale.LC_TIME, original)
            self.nginx.append(f'{ip} - - [{timestamp}] "{method} {path}{query} HTTP/1.1" {status} 9 "-" "fixture"\n')
            with gzip.open(self.directory / 'access.log.2.gz', 'wt', encoding='ascii') as stream:
                stream.writelines(self.nginx)

    def create(self, key=None, level='xhigh'):
        config = self.client.get(API).json
        return self.client.post(API, headers=self.headers, json={'client_key': key or uuid.uuid4().hex,
            'hours': 24, 'level': level, 'selection_id': config['default_model']})

    def report(self, job, content, termination=None, calls=None):
        return self.client.post('/internal/ai/jobs/' + job['id'] + '/finish', headers=self.worker_headers,
            json={'lease': job['lease'], 'content': content, 'outcome': 'complete', 'calls': calls or [],
                  'termination': termination or {'done': True, 'finish_reason': 'stop'}}).json

    def test_queue_review_download_and_history(self):
        self.seed('1.2.3.4', '/.env', query='?note=' + TOKEN)
        self.seed('1.2.3.4', '/.git/config', 1)
        self.seed('8.8.4.4', '/.env')
        self.seed('8.8.4.4', '/.git/config', 1, edge=False)
        self.seed('8.8.8.8', '/etc/passwd', app_ip='9.9.9.9')
        self.seed('2.3.4.5', '/missing', status=500)
        self.seed('9.9.9.9', '/.env', status=200)
        key = uuid.uuid4().hex
        created = self.create(key)
        self.assertEqual(created.status_code, 202, created.json)
        jid = created.json['job_id']
        self.assertEqual(self.create(key).json['job_id'], jid)
        self.assertEqual(self.create(key, 'medium').status_code, 409)
        self.assertEqual(self.client.get(API + '/' + jid + '/blocklist.txt').status_code, 409)

        job = self.claim()
        self.assertEqual(job['reasoning_effort'], 'xhigh')
        self.assertEqual(job['tools'], [])
        self.assertNotIn('1.2.3.4', json.dumps(job))
        self.assertNotIn(TOKEN, json.dumps(job))
        self.assertEqual(json.loads(job['messages'][1]['content']), [
            {'id': 1, 'signals': {}, 'secret_paths': 2, 'php_paths': 0, 'shell_names': 0}])
        self.assertEqual(self.client.get('/api/ai/jobs/' + jid).status_code, 404)
        self.assertEqual(self.report(job, '{"selected":[1]}')['state'], 'done')

        self.login(1)
        history = self.client.get(API + '/history').json
        self.assertEqual(len(history['items']), 1)
        self.assertEqual(history['items'][0]['count'], 1)
        self.assertEqual(history['items'][0]['level'], 'xhigh')
        self.assertEqual(history['items'][0]['job_id'], jid)
        detail = self.client.get(API + '/' + jid).json
        self.assertEqual([row['ip'] for row in detail['verified']], ['1.2.3.4'])
        self.assertEqual(detail['evidence']['errors'], 6)
        download = self.client.get(API + '/' + jid + '/blocklist.txt')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b'1.2.3.4\n')
        self.assertIn('attachment;', download.headers['Content-Disposition'])
        self.assertEqual(download.headers['Cache-Control'], 'no-store')

        self.change("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode='access_logs'")
        self.assertEqual(self.client.get(API + '/history').status_code, 403)
        self.assertEqual(self.client.get(API + '/' + jid + '/blocklist.txt').status_code, 403)

    def test_model_cannot_export_unknown_number_or_unfinished_output(self):
        self.seed('1.2.3.4', '/etc/passwd')
        job_id = self.create().json['job_id']
        job = self.claim()
        self.assertEqual(self.report(job, '{"selected":[999]}')['state'], 'failed')
        self.assertEqual(self.client.get(API + '/' + job_id + '/blocklist.txt').status_code, 409)
        self.assertEqual(self.client.get(API + '/history').json['items'], [])

        job_id = self.create().json['job_id']
        job = self.claim()
        self.assertEqual(self.report(job, '{"selected":[1]}', {'done': False, 'finish_reason': None})['state'], 'recovery_required')
        self.assertEqual(self.client.get(API + '/' + job_id + '/blocklist.txt').status_code, 409)

    def test_refuses_user_forgery_csrf_and_ambiguous_edge(self):
        self.seed('1.2.3.4', '/etc/passwd')
        self.seed('1.2.3.4', '/etc/passwd', edge=False)
        self.login(2)
        self.assertEqual(self.client.get(API).status_code, 403)
        self.assertEqual(self.client.get(API + '/history').status_code, 403)
        self.login(1)
        self.assertEqual(self.client.post(API, json={}).status_code, 403)
        self.assertEqual(self.create().status_code, 409)
