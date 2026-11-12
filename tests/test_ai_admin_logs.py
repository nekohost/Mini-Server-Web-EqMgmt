"""Exercise the administrator HTML, JSON and menu routes with disposable SQLite and an in-process client."""
import ast
from contextlib import closing
from functools import wraps
import hashlib
import sqlite3
import sys
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid
from html.parser import HTMLParser

from flask import jsonify, redirect, request, session, url_for
if 'assistant_fixture_tests' in sys.modules:
    import assistant_fixture_tests as fixture
else:
    import test_equipment_ai as fixture
from utils.ai_assistant import admin_logs, visible_assistant_menus
from utils.ai_assistant.policy import canonical, digest
from utils.strata_integration import visible_portal_menus


PAGE = '/admin/ai/logs'
API = '/api/admin/ai/logs'
MENU = 'equipment_ai_logs'


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.urls = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.append(dict(attrs).get('href', ''))


class AdminLogTests(unittest.TestCase):
    connect = fixture.AssistantTests.connect
    login = fixture.AssistantTests.login

    def setUp(self):
        # Extracted login/maintenance/HTTP audit hooks only. app.py has import-time services.
        fixture.AssistantTests.setUp(self)
        tree = ast.parse(globals().get('SOURCE_APP') or (fixture.PROJECT / 'app.py').read_text(encoding='utf-8-sig'))
        names = {'login_required', 'check_menu_permission', 'get_children_menus'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = dict(app=self.app, session=session, request=request, jsonify=jsonify, redirect=redirect,
                     url_for=url_for, wraps=wraps, get_db_connection=self.connect,
                     visible_assistant_menus=visible_assistant_menus, visible_portal_menus=visible_portal_menus)
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<fixture-menu>', 'exec'), scope)
        self.login(1)

    def change(self, sql, params=()):
        with closing(self.connect()) as db, db:
            db.execute(sql, params)

    def conversation(self, title='장비 문의', owner=2):
        key = digest(['account', owner, '2026-01-01 00:00:0' + str(owner)])
        cid = self.store.create_conversation(owner, key)
        with self.store.db(True) as ai:
            ai.execute('UPDATE conversations SET title=? WHERE id=?', (title, cid))
        return cid

    def job(self, cid, state='done', question='장비 상태를 알려주세요.', answer='정상입니다.', owner=2,
            purpose='chat', reason=None, code=None):
        jid = uuid.uuid4().hex
        now = time.time()
        with self.store.db(True) as ai:
            ai.execute('''INSERT INTO jobs(id,conversation,owner,client_key,input_hash,binding,expires,level,state,
                queue_order,created,updated,purpose,error,error_code) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (jid, cid, owner, uuid.uuid4().hex, 'PRIVATE-INPUT-HASH', 'PRIVATE-JOB-BINDING', now + 900,
                 'low', state, 1, now, now, purpose, reason, code))
            ai.executemany('INSERT INTO messages(conversation,job,role,content,reasoning,created) VALUES(?,?,?,?,?,?)',
                           [(cid, jid, 'user', question, '', now),
                            (cid, jid, 'assistant', answer, 'PRIVATE-INTERNAL-REASONING', now)])
        return jid

    def proposal(self, jid, state='applied', owner=2, expires=None):
        pid = uuid.uuid4().hex
        with self.store.db(True) as ai:
            ai.execute('''INSERT INTO proposals(id,job,owner,operation,payload,before_json,signature,expires,state,result,created)
                VALUES(?,?,?,'equipment_update',?,?,?,?,?,?,?)''', (pid, jid, owner, '{"private":"PAYLOAD"}',
                '{"private":"BEFORE"}', 'PRIVATE-SIGNATURE', expires or time.time()+900, state, 'PRIVATE-RESULT', time.time()))
        return pid

    def api(self, **params):
        response = self.client.get(API, query_string=params)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.json['success'])
        return response.json

    def assert_access(self, html_status, api_status):
        for view in ('conversations', 'jobs', 'job', 'receipts', 'questions'):
            params = {'view': view}
            for path, status in ((PAGE, html_status), (API, api_status)):
                with self.subTest(view=view, path=path):
                    response = self.client.get(path, query_string=params)
                    self.assertEqual(response.status_code, status)
                    self.assertNotIn('PRIVATE', response.get_data(as_text=True))

    def test_regular_or_demoted_account_with_spurious_grant(self):
        self.change("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed) VALUES('user',?,1)", (MENU,))
        self.login(2)
        with self.client.session_transaction() as cookie:
            cookie['user'] = dict(cookie['user'], Role='admin')
        self.assert_access(403, 403)
        self.login(1)
        self.change("UPDATE users SET Role='user' WHERE UserId=1")
        self.assert_access(403, 403)

    def test_revoked_or_missing_grant_and_independent_read_grant(self):
        self.change("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode IN ('equipment_ai','equipment_ai_settings')")
        self.assertEqual(self.client.get(PAGE).status_code, 200)
        self.assertEqual(self.api()['items'], [])
        self.change("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode=?", (MENU,))
        self.assert_access(403, 403)
        self.change("DELETE FROM role_menu_permissions WHERE MenuCode=?", (MENU,))
        self.assert_access(403, 403)

    def test_revocation_logout_rotation_and_account_state(self):
        binding = self.domain.binding(1, 'token-1')
        self.store.revoke(binding)
        self.assert_access(401, 401)
        with self.store.db(True) as ai:
            ai.execute('DELETE FROM revocations')
        self.change("UPDATE users SET SessionToken='rotated' WHERE UserId=1")
        self.assert_access(302, 401)
        self.change("UPDATE users SET SessionToken='token-1',IsDeactivated='Y' WHERE UserId=1")
        self.login(1)
        self.assert_access(302, 403)
        self.change("UPDATE users SET IsDeactivated='N',IsDeleted='Y' WHERE UserId=1")
        self.assert_access(302, 401)

    def test_menu_visibility_and_feature_flag(self):
        def codes():
            response = self.client.get('/api/menus/children/admin_center')
            self.assertEqual(response.status_code, 200)
            return [menu['MenuCode'] for menu in response.json]
        self.assertIn(MENU, codes())
        self.change("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode=?", (MENU,))
        self.assertNotIn(MENU, codes())
        self.change("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed) VALUES('user','admin_center',1)")
        self.change("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed) VALUES('user',?,1)", (MENU,))
        self.login(2)
        self.assertNotIn(MENU, codes())
        self.login(1)
        self.change("UPDATE role_menu_permissions SET IsAllowed=1 WHERE MenuCode=?", (MENU,))
        with patch.dict(self.app.config, USER_AI_ENABLED=False):
            self.assertNotIn(MENU, codes())
            self.assert_access(404, 404)

    def test_menu_reinitialization_and_collisions(self):
        def register(db):
            admin_logs.register_admin_menu(db, MENU, 'AI 도우미 기록', PAGE, '새 설명', 53, '새 시각')
        with closing(self.connect()) as db, db:
            db.execute("UPDATE menus SET MenuName='기존 이름',ParentMenuCode=NULL,SortOrder=83 WHERE MenuCode=?", (MENU,))
            db.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode=?", (MENU,))
            register(db)
            db.execute("UPDATE menus SET UpdatedAt='이전 시각' WHERE MenuCode=?", (MENU,))
            register(db)
            self.assertEqual(tuple(db.execute('SELECT MenuName,ParentMenuCode,SortOrder,UpdatedAt FROM menus WHERE MenuCode=?',
                                             (MENU,)).fetchone()), ('기존 이름','admin_center',83,'이전 시각'))
            self.assertEqual(db.execute('SELECT IsAllowed FROM role_menu_permissions WHERE MenuCode=?', (MENU,)).fetchone()[0], 0)
            for column, value in (('Url','/other'), ('ParentMenuCode','unrelated')):
                db.execute(f'UPDATE menus SET {column}=? WHERE MenuCode=?', (value, MENU))
                with self.assertRaises(ValueError):
                    register(db)
                self.assertEqual(db.execute(f'SELECT {column} FROM menus WHERE MenuCode=?', (MENU,)).fetchone()[0], value)
                db.execute("UPDATE menus SET Url=?,ParentMenuCode='admin_center' WHERE MenuCode=?", (PAGE, MENU))
            db.execute("UPDATE menus SET MenuCode='other_code' WHERE MenuCode=?", (MENU,))
            with self.assertRaises(ValueError):
                register(db)

    def test_stored_question_final_answer_and_failure_reason(self):
        cid = self.conversation('장비 <목록>')
        question = '점검할 장비는 <A>입니다.'
        answer = '답변 시작\n' + '가' * admin_logs.BODY_PAGE + '<script>fixture</script> 끝'
        jid = self.job(cid, question=question, answer=answer)
        failed = self.job(cid, 'failed', answer='PRIVATE-PARTIAL', reason='응답 길이를 초과했습니다.', code='LENGTH_LIMIT')
        wrong_cid = self.conversation(owner=3)
        wrong_owner = self.job(cid, owner=3)
        with self.store.db(True) as ai:
            ai.execute("INSERT INTO messages(conversation,job,role,content,created) VALUES(?,?,'user','PRIVATE-OTHER-QUESTION',0)",
                       (wrong_cid, jid))
            ai.execute("INSERT INTO messages(conversation,role,content,created) VALUES(?,'assistant','PRIVATE-SERVER-RECEIPT',0)", (cid,))
            ai.execute("INSERT INTO message_steps VALUES(?,0,'PRIVATE-STEP','PRIVATE-DRAFT')", (jid,))
            ai.execute("UPDATE jobs SET context='PRIVATE-CONTEXT',route_snapshot='PRIVATE-ROUTE',lease_hash='PRIVATE-LEASE' WHERE id=?", (jid,))
        self.assertEqual({j['id'] for j in self.api(view='jobs', conversation=cid)['items']}, {jid, failed})
        self.assertEqual(self.client.get(API, query_string=dict(view='job',id=wrong_owner)).status_code, 404)
        job = self.api(view='jobs', owner='2', state='failed')['items'][0]
        self.assertEqual((job['id'], job['error_code'], job['reason']), (failed, 'LENGTH_LIMIT', '응답 길이를 초과했습니다.'))
        self.assertEqual(self.api(view='job', id=failed)['answer']['text'], '')
        first = self.api(view='job', id=jid)
        second = self.api(view='job', id=jid, answer_page=2)
        self.assertEqual(first['question']['text'], question)
        self.assertEqual(len(first['answer']['text']), admin_logs.BODY_PAGE)
        self.assertEqual(first['answer']['text'] + second['answer']['text'], answer)
        html = self.client.get(PAGE, query_string=dict(view='job', id=jid, answer_page=2)).get_data(as_text=True)
        self.assertIn('&lt;script&gt;fixture&lt;/script&gt;', html)
        self.assertNotIn('PRIVATE', canonical([first, second, html]))
        self.assertTrue(all(log['RequestPayload'] is None and log['ResponsePayload'] is None for log in self.audit_logs))

    def test_unfinished_or_probe_text_and_retention_boundary(self):
        cid = self.conversation()
        running = self.job(cid, 'running', answer='PRIVATE-IN-PROGRESS')
        probe = self.job(cid, purpose='probe', question='PRIVATE-PROBE', answer='PRIVATE-NONCE')
        waiting = self.job(cid, 'waiting_confirmation')
        self.assertEqual(self.api(view='job', id=running)['answer']['text'], '')
        self.assertNotIn('PRIVATE', canonical(self.api(view='job', id=probe)))
        self.assertEqual(self.api(view='job', id=waiting)['answer']['text'], '정상입니다.')
        now = time.time()
        with self.store.db(True) as ai:
            ai.execute('UPDATE conversations SET is_deleted=1,deleted_at=?,purge_after=? WHERE id=?', (now, now+100, cid))
        self.assertTrue(self.api()['items'][0]['is_deleted'])
        with self.store.db(True) as ai:
            ai.execute('UPDATE conversations SET purge_after=? WHERE id=?', (now-1, cid))
        self.assertEqual(self.api()['items'], [])
        self.assertEqual(self.api(view='jobs')['items'], [])
        for path in (API, PAGE):
            for query in (dict(view='jobs', conversation=cid), dict(view='job', id=waiting)):
                self.assertEqual(self.client.get(path, query_string=query).status_code, 404)

    def test_mail_signoff_remains_readable_and_signed_credentials_are_hidden(self):
        question = '영문 메일 서명을 확인해 주세요.\n서명: 홍길동'
        answer = 'Signature: Jane Smith'
        jid = self.job(self.conversation(), question=question, answer=answer)
        detail = self.api(view='job', id=jid)
        self.assertEqual(detail['question']['text'], question)
        self.assertEqual(detail['answer']['text'], answer)
        for credential in ('signature: abcd12345678-wxyz', '제안 서명: private', '서명: ' + 'ab' * 32):
            self.assertEqual(admin_logs.display_text(credential, 2000, ()), admin_logs.PROTECTED)

    def test_sensitive_text_is_checked_before_paging(self):
        cid = self.conversation('api_key = PRIVATE-TITLE')
        jid = self.job(cid, reason='authorization: PRIVATE-ERROR', code='PROVIDER_AUTH',
                       question='참고 ' + self.app.config['USER_AI_WORKER_TOKEN'],
                       answer='가' * (admin_logs.BODY_PAGE-2) + 'Bearer PRIVATE-TOKEN\n다음 줄')
        for result in (self.api(), self.api(view='jobs'), self.api(view='job', id=jid)):
            self.assertNotIn('PRIVATE', canonical(result))
            self.assertNotIn(self.app.config['USER_AI_WORKER_TOKEN'], canonical(result))
        detail = self.api(view='job', id=jid)
        self.assertEqual(detail['answer'], dict(text='[보호된 내용]', page=1, pages=1))
        self.assertEqual(detail['question']['text'], '[보호된 내용]')
        self.assertEqual(self.client.get(API, query_string=dict(view='job', id=jid, answer_page=2)).status_code, 404)
        self.assertEqual(detail['job']['reason'], 'API 키 인증 단계에서 모델 서버가 요청을 거절했습니다.')

    def test_unlinked_legacy_questions_remain_readable_without_inventing_an_answer(self):
        cid = self.conversation()
        long = '장' * admin_logs.BODY_PAGE + '마지막'
        with self.store.db(True) as ai:
            ai.executemany('INSERT INTO messages(conversation,role,content,created) VALUES(?,?,?,?)',
                [(cid,'user','이전 질문',1), (cid,'user',long,2), (cid,'assistant','PRIVATE-CONFIRMATION',3)])
        self.assertTrue(self.api(view='jobs', conversation=cid)['has_unlinked_questions'])
        params = dict(view='questions', conversation=cid)
        latest = self.api(**params)
        self.assertEqual(latest['items'][0]['question']['text'], long[:admin_logs.BODY_PAGE])
        response = self.client.get(PAGE, query_string=dict(params,question_page=2))
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('마지막', html)
        self.assertNotIn('PRIVATE-CONFIRMATION', html)
        older = next(url for url in Links(html).urls if 'before' in parse_qs(urlsplit(url).query))
        self.assertIn('이전 질문', self.client.get(older).get_data(as_text=True))
        self.assertFalse(self.api(**params, before=latest['paging']['older'])['paging']['older'])

    def test_verified_business_receipt_and_split_commit(self):
        with closing(self.connect()) as db:
            actor = self.domain.actor(db, 2)
        cid = self.store.create_conversation(2, actor['account_key'])
        jid = self.store.enqueue(2, cid, '테마 변경', 'low', uuid.uuid4().hex, actor['binding'], time.time()+900, actor['account_key'])
        job = self.store.claim('fixture-worker')
        pid = self.store.proposal(job, 'preferences', {'theme':'dark'}, {}, self.app.secret_key)['proposal_id']
        with self.store.db() as ai:
            proposal = dict(ai.execute('SELECT * FROM proposals WHERE id=?', (pid,)).fetchone())
        # Real business writer has committed, but its companion AI state update has not yet happened.
        self.domain.execute(proposal, job)
        item = self.api(view='job', id=jid)['items'][0]
        self.assertEqual((item['state'], item['audit']['action']), ('pending','AI_EXECUTE'))
        self.assertEqual(set(item['audit']), {'id','action','created'})
        self.assertNotIn(proposal['signature'], canonical(item))
        self.assertNotIn('theme', canonical(item))
        self.login(2)
        response = self.client.post('/api/ai/proposals/' + pid + '/confirm', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.login(1)
        applied = self.api(view='job', id=jid)['items'][0]
        self.assertEqual((applied['state'], applied['audit']), ('applied',item['audit']))

    def test_unverified_audits_never_attached_by_prefix_owner_time_or_state(self):
        jid = self.job(self.conversation())
        pid = self.proposal(jid)
        foreign = self.proposal(jid, owner=3)
        target = int(pid[:15], 16)
        fingerprint = digest([pid, 'equipment_update', '{"private":"PAYLOAD"}', '{"private":"BEFORE"}'])
        receipt = {'proposal_id':pid, 'hash':fingerprint, 'result':{'value':'PRIVATE-AUDIT-RESULT'}}
        sql = '''INSERT INTO audit_logs(ActorId,Action,TargetTable,TargetId,OldValue,NewValue,CreatedAt)
                 VALUES(?,?,?,?,'PRIVATE-BEFORE',?,'2026-11-12T00:00:00+00:00')'''
        with closing(self.connect()) as db, db:
            for owner, action, table, tid, value in (
                (3,'AI_EXECUTE','ai_operations',target,canonical(receipt)),
                (2,'OTHER','ai_operations',target,canonical(receipt)),
                (2,'AI_EXECUTE','other',target,canonical(receipt)),
                (2,'AI_EXECUTE','ai_operations',target+1,canonical(receipt)),
                (2,'AI_EXECUTE','ai_operations',target,canonical(dict(receipt,proposal_id=pid[:15]+'0'*17))),
                (2,'AI_EXECUTE','ai_operations',target,canonical(dict(receipt,hash='wrong'))),
                (2,'AI_EXECUTE','ai_operations',target,canonical(dict(receipt,result=None))),
                (2,'AI_EXECUTE','ai_operations',target,'malformed PRIVATE-AUDIT')):
                db.execute(sql, (owner, action, table, tid, value))
        detail = self.api(view='job', id=jid)
        self.assertEqual([p['id'] for p in detail['items']], [pid])
        self.assertIsNone(detail['items'][0]['audit'])
        self.assertNotIn(foreign, canonical(detail))
        with closing(self.connect()) as db, db:
            audit_id = db.execute(sql, (2,'AI_EXECUTE','ai_operations',target,canonical(receipt))).lastrowid
        linked = self.api(view='job', id=jid)['items'][0]
        self.assertEqual(linked['audit']['id'], audit_id)
        self.assertNotIn('PRIVATE', canonical(linked))
        self.assertNotIn(fingerprint, canonical(linked))

    def test_legacy_csv_metadata_and_missing_ledger_are_read_only(self):
        with self.store.db() as watch:
            self.assertIsNone(watch.execute("SELECT 1 FROM sqlite_master WHERE name='ai_audit_artifacts'").fetchone())
        self.assertEqual(self.api(view='receipts')['items'], [])
        self.assertIn('조회된 CSV 영수증이 없습니다.', self.client.get(PAGE+'?view=receipts').get_data(as_text=True))
        with self.store.db(True) as ai:
            self.assertIsNone(ai.execute("SELECT 1 FROM sqlite_master WHERE name='ai_audit_artifacts'").fetchone())
            ai.execute('CREATE TABLE ai_audit_artifacts(id TEXT PRIMARY KEY,sha256 TEXT,bytes INTEGER,owner INTEGER,scope TEXT,row_count INTEGER,created REAL)')
            content_hash = hashlib.sha256(b'PRIVATE-CSV-ORIGINAL').hexdigest()
            for owner in (2, 2, 3):
                ai.execute('INSERT INTO ai_audit_artifacts VALUES(?,?,20,?,?,1,?)',
                           (uuid.uuid4().hex, content_hash, owner,'public',time.time()))
        with patch('builtins.open', side_effect=AssertionError('CSV file access')):
            result = self.api(view='receipts', owner=2, limit=1)
            older = self.api(view='receipts', owner=2, limit=1, before=result['paging']['older'])
        self.assertNotEqual(result['items'][0]['id'], older['items'][0]['id'])
        self.assertEqual(result['items'][0]['sha256'], content_hash)
        self.assertEqual(set(result['items'][0]), {'id','owner','scope','row_count','bytes','created','sha256'})
        with self.store.db() as ai:
            self.assertNotIn('blob_id', [r[1] for r in ai.execute('PRAGMA table_info(ai_audit_artifacts)')])
        self.assertNotIn('PRIVATE', canonical(result))

    def test_keyset_pages_drilldown_and_proposal_states(self):
        conversations = [self.conversation(str(i)) for i in range(4)]
        jid = self.job(conversations[-1])
        states = ('pending','applied','expired','cancelled','superseded')
        for state in states:
            self.proposal(jid, state, expires=time.time()-1)
        first = self.api(limit=2)
        self.conversation('나중에 추가')
        second = self.api(before=first['paging']['older'], limit=2)
        self.assertEqual([r['id'] for r in first['items']+second['items']], conversations[::-1])
        back = self.api(after=second['paging']['newer'], limit=2)
        self.assertEqual(back['items'], first['items'])
        url = PAGE + '?view=job&id=' + jid + '&limit=2'
        html = self.client.get(url).get_data(as_text=True)
        self.assertIn('제안 처리 기록', html)
        older_url = next(url for url in Links(html).urls if 'before' in parse_qs(urlsplit(url).query))
        self.assertEqual(self.client.get(older_url).status_code, 200)
        all_states = self.api(view='job', id=jid)['items']
        self.assertEqual([p['state'] for p in all_states], list(reversed(states)))
        self.assertTrue(all_states[-1]['past_due'])
        with self.store.db() as ai:
            self.assertEqual(ai.execute("SELECT COUNT(*) FROM proposals WHERE state='pending'").fetchone()[0], 1)

    def test_readers_use_only_source_columns_and_never_open_csv_originals(self):
        cid = self.conversation()
        jid = self.job(cid)
        self.proposal(jid)
        with self.store.db(True) as ai:
            ai.execute('''CREATE TABLE ai_audit_artifacts(id TEXT PRIMARY KEY,sha256 TEXT,bytes INTEGER,owner INTEGER,
                       scope TEXT,row_count INTEGER,created REAL,blob_id TEXT)''')
            ai.execute("INSERT INTO ai_audit_artifacts VALUES(?,?,125,2,'my',2,?,'PRIVATE-BLOB-ID')",
                       (uuid.uuid4().hex,'a'*64,time.time()))
        forbidden_columns = {'jobs': {'binding','context','route_snapshot','lease_hash','client_key','probe_plan'},
                             'proposals': {'signature','result'}, 'messages': {'reasoning'},
                             'ai_audit_artifacts': {'blob_id'}, 'audit_logs': {'OldValue','IpAddress','UserAgent'}}
        def authorize(action, table, column, *_):
            if action == sqlite3.SQLITE_READ and (table in {'access_logs','message_steps','ai_provider_revisions'}
                    or column in forbidden_columns.get(table, ())):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        original = sqlite3.connect
        def guarded(*args, **kwargs):
            db = original(*args, **kwargs)
            db.set_authorizer(authorize)
            return db
        with patch.object(sqlite3, 'connect', guarded), patch('pathlib.Path.open', side_effect=AssertionError('CSV read')):
            for params in ({}, dict(view='jobs',conversation=cid), dict(view='job',id=jid), dict(view='receipts')):
                result = self.api(**params)
                self.assertTrue(result['items'])
                self.assertNotIn('PRIVATE', canonical(result))

    def test_empty_invalid_unavailable_and_method_errors(self):
        cid = self.conversation()
        for view, expected in (('jobs','조회된 작업이 없습니다.'), ('receipts','조회된 CSV 영수증이 없습니다.')):
            html = self.client.get(PAGE, query_string=dict(view=view,owner=''))
            self.assertEqual(html.status_code, 200)
            self.assertIn(expected, html.get_data(as_text=True))
        self.assertEqual(self.api(view='jobs', conversation=cid)['items'], [])
        for query in ('limit=51','before=-1','after=0','before=1&after=2','owner=1&owner=2',
                      'view=jobs&state=invalid','view=access_logs','limit=9999999999999999999999'):
            for path in (PAGE, API):
                self.assertEqual(self.client.get(path+'?'+query).status_code, 400, query)
        for path in (PAGE, API):
            self.assertEqual(self.client.get(path+'?view=job&id='+uuid.uuid4().hex).status_code, 404)
            self.assertEqual(self.client.post(path).status_code, 405)
        missing = self.root / 'does-not-exist.db'
        with patch.object(self.store, 'path', missing):
            for path in (PAGE, API):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                body = response.get_data(as_text=True) if path == PAGE else response.json['message']
                self.assertIn('기록 저장소를 조회하지 못했습니다.', body)
                self.assertNotIn(str(missing), body)
            self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
