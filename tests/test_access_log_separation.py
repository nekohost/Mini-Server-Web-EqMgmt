"""Synthetic Linux HTTP tests for the ordinary queue, protected history and the retired spool."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from flask import Flask

SOURCE = Path(__file__).resolve().parents[1]
HEADERS = {'X-CSRFToken':'fixture-access-csrf', 'Origin':'https://fixture.example'}
SEED = 'synthetic-historic-body-for-separation'
INSERT = """INSERT INTO access_logs (IpAddress,HttpMethod,RequestPath,StatusCode,UserAgent,Referer,DurationMs,
            IsStatic,RequestPayload,ResponsePayload,CreatedAt)
            VALUES (:IpAddress,:HttpMethod,:RequestPath,:StatusCode,:UserAgent,:Referer,:DurationMs,
            :IsStatic,:RequestPayload,:ResponsePayload,:CreatedAt)"""


def event(path, body=None, status=200):
    return dict(IpAddress='192.0.2.45',HttpMethod='GET',RequestPath=path,StatusCode=status,UserAgent='fixture',
                Referer='',DurationMs=1,IsStatic=0,RequestPayload=body,ResponsePayload=body,CreatedAt='2026-11-12 10:00:00')


def fixture_app(root):
    environment = {'DATABASE_PATH':str(root/'equipment.sqlite3'),'DATABASE_OPERATION_ROOT':str(root/'operations'),
                   'USER_AI_ENABLED':'true','USER_AI_WRITE_TOOLS':'true','USER_AI_MODEL_DISCOVERY':'false',
                   'USER_AI_DATABASE':str(root/'ai'/'assistant.sqlite3'),'USER_AI_PUBLIC_ORIGIN':'https://fixture.example',
                   'MAINTENANCE_STATE_PATH':str(root/'maintenance.json'),'EQUIPMENT_ATTACHMENT_ROOT':str(root/'attachments'),
                   'USER_AI_WORKER_TOKEN':'synthetic-access-separation-worker-token-00001','PYTHON_DOTENV_DISABLED':'1',
                   'SECRET_KEY':'synthetic-access-separation-equipment-secret-00001','USER_AI_WEB_SEARCH':'false'}
    def isolated_flask(name, **kwargs):
        return Flask(name, root_path=str(SOURCE),instance_path=str(root/'instance'),**kwargs)
    with patch.dict(os.environ,environment), patch('flask.Flask',side_effect=isolated_flask):
        spec=importlib.util.spec_from_file_location('access_fixture_app', SOURCE/'app.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    with closing(sqlite3.connect(module.DATABASE_PATH)) as db, db:
        for uid, role in [(41201,'admin'),(41202,'user')]:
            db.execute("""INSERT OR IGNORE INTO users(UserId,LoginId,Password,Role,SessionToken,IsDeleted,IsDeactivated,CreatedAt)
                          VALUES(?,?,?,?,?,'N','N','2026-01-01')""",(uid,f'access-user-{uid}','fixture',role,f'session-{uid}'))
    return module


def client_for(module, uid=41201):
    client=module.app.test_client()
    with client.session_transaction() as session:
        session['user']={'UserId':uid,'Role':'admin' if uid==41201 else 'user','LoginId':f'access-user-{uid}','NickName':'fixture'}
        session['session_token']=f'session-{uid}'
        session['csrf_token']=HEADERS['X-CSRFToken']
    return client


def cleanup(client, action, step, op=None, headers=HEADERS):
    data=dict(action=action,step=step)
    if op is not None:
        data['operation_id']=op
    return client.post('/api/access_logs/cleanup', json=data, headers=headers)


@unittest.skipUnless(sys.platform=='linux','Linux filesystem and actual Flask app')
class WebSeparation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='log-separation-http-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = fixture_app(self.root)
        self.addCleanup(self.app.on_app_exit)
        self.admin = client_for(self.app)

    def test_old_payloads_and_error_ip_remain_distinct(self):
        with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db, db:
            ordinary = db.execute(INSERT,event('/api/business', 'synthetic ordinary')).lastrowid
            protected = [db.execute(INSERT,event(path,SEED,403)).lastrowid for path in
                         ('/assistant','/admin/ai/providers','/api/ai','/api/admin/ai/unknown','/internal/ai/claim')]
        listing = {item['LogId']:item for item in self.admin.get('/api/access_logs?per_page=1000').get_json()['logs']}
        viewer = client_for(self.app, 41202)
        for log_id in protected:
            row = listing[log_id]
            self.assertEqual((row['HasRequestPayload'],row['HasResponsePayload']),(0,0))
            path = f'/api/access_logs/{log_id}/payload'
            detail = self.admin.get(path).get_json()
            self.assertEqual((detail['request_payload'], detail['response_payload']), (None,None))
            self.assertEqual(viewer.get(path).status_code, 403)
        self.assertEqual(self.admin.get(f'/api/access_logs/{ordinary}/payload').get_json()['response_payload'],'synthetic ordinary')
        stats = self.admin.get('/api/access_logs/stats?period=all').get_json()
        self.assertGreaterEqual(stats['error_count'],len(protected))
        ips = self.admin.get('/api/access_logs/error_ips').get_json()['error_ips']
        self.assertTrue(any(row['IpAddress']=='192.0.2.45' and row['TotalErrorCount']==len(protected) for row in ips))
        with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM access_logs WHERE ResponsePayload=?',(SEED,)).fetchone()[0],len(protected))
        self.assertEqual(cleanup(viewer,'all_including_ai','direct').status_code,403)
        self.assertEqual(cleanup(self.admin,'all_including_ai','direct',headers={}).status_code,403)

    def test_admitted_batch_and_queue_precede_boundary_new_rows_survive(self):
        owned, release = threading.Event(), threading.Event()
        original = self.app._insert_access_logs
        def pause_once(batch):
            if any(item['RequestPath']=='/batch-before' for item in batch):
                owned.set()
                if not release.wait(8):
                    raise AssertionError('fixture writer was not released')
            return original(batch)
        # Release before joining the executor even when an assertion fails.
        with patch.object(self.app,'_insert_access_logs',pause_once), ThreadPoolExecutor(2) as pool:
            self.app.push_access_log(event('/batch-before'))
            try:
                self.assertTrue(owned.wait(5))
                self.app.push_access_log(event('/queue-before'))
                op=pool.submit(lambda:cleanup(client_for(self.app),'all_including_ai','count'))
                until=time.monotonic()+5
                while not self.app.access_log_ingress_lock.locked() and time.monotonic()<until:
                    time.sleep(0.01)
                self.assertTrue(self.app.access_log_ingress_lock.locked())
                fresh=pool.submit(self.app.push_access_log,event('/after-start'))
            finally:
                release.set()
            begin = op.result(timeout=8).get_json()
            fresh.result(timeout=5)
        self.assertGreaterEqual(begin['total_count'],2)
        op = begin['operation_id']
        unfinished=cleanup(self.admin,'all_including_ai','finish',op)
        self.assertNotEqual(unfinished.status_code,200)
        self.assertEqual(cleanup(self.admin,'all_including_ai','delete_chunk',op).status_code,200)
        finish=cleanup(self.admin,'all_including_ai','finish',op).get_json()
        self.assertEqual(finish['remaining_count'],0)
        self.assertEqual(finish['deleted_count'],begin['total_count'])
        self.app.access_log_queue.join()
        with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db:
            old = db.execute("SELECT COUNT(*) FROM access_logs WHERE RequestPath IN ('/batch-before','/queue-before')").fetchone()[0]
            new = db.execute("SELECT COUNT(*) FROM access_logs WHERE RequestPath='/after-start'").fetchone()[0]
        self.assertEqual((old,new),(0,1))

    def test_actual_cleanup_preserves_chat_job_and_csv_on_reopen(self):
        from utils.ai_assistant.providers import PROTOCOL
        import uuid
        user = client_for(self.app,41202)
        create = user.post('/api/ai/conversations',json={},headers=HEADERS)
        self.assertEqual(create.status_code,201,create.get_json())
        cid=create.get_json()['id']
        route='/api/ai/conversations/'+cid
        submit=user.post(route+'/turns',json={'content':'fixture private text','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=HEADERS)
        self.assertEqual(submit.status_code,202,submit.get_json())
        jid=submit.get_json()['job_id']
        internal=self.app.app.test_client()
        worker_headers={'Authorization':'Bearer '+self.app.app.config['USER_AI_WORKER_TOKEN']}
        packet=internal.post('/internal/ai/claim',json={'worker':'fixture','protocol':PROTOCOL},headers=worker_headers).get_json()['job']
        self.assertEqual(packet['id'],jid)
        final=internal.post('/internal/ai/jobs/'+jid+'/finish',json={'lease':packet['lease'],'outcome':'complete','calls':[],'content':'fixture retained answer'},headers=worker_headers)
        self.assertEqual(final.get_json()['state'],'done')
        with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db, db:
            category=db.execute("INSERT INTO categories(Name,IsApproved) VALUES ('Fixture category',1)").lastrowid
            maker=db.execute("INSERT INTO manufacturers(Name,IsApproved) VALUES ('Fixture maker',1)").lastrowid
            node=db.execute("""INSERT INTO lineup_nodes(category_id,manufacturer_id,name,depth,status,official_model_name)
                               VALUES (?,?,'fixture node',1,'APPROVED','fixture model')""",(category,maker)).lastrowid
            option=db.execute("""INSERT INTO equipment_options(lineup_node_id,option_name,specs_json,status)
                                 VALUES (?,'fixture option','{}','APPROVED')""",(node,)).lastrowid
        next_turn=user.post(route+'/turns',json={'content':'fixture equipment change','reasoning_version':2,
                            'level':'medium','client_key':uuid.uuid4().hex},headers=HEADERS)
        self.assertEqual(next_turn.status_code,202,next_turn.get_json())
        change=internal.post('/internal/ai/claim',json={'worker':'fixture','protocol':PROTOCOL},headers=worker_headers).get_json()['job']
        args=json.dumps({'name':'fixture approved equipment','option_id':option})
        proposed=internal.post('/internal/ai/jobs/'+change['id']+'/finish',json={'lease':change['lease'],'outcome':'complete',
                               'calls':[{'id':'fixture-create','name':'prepare_equipment_create','arguments':args}]},headers=worker_headers)
        self.assertEqual(proposed.get_json()['state'],'queued',proposed.get_json())
        store=self.app.app.extensions['equipment_assistant']['store']
        with store.db() as db:
            proposal_id=db.execute('SELECT id FROM proposals WHERE job=?',(change['id'],)).fetchone()[0]
        confirm='/api/ai/proposals/'+proposal_id+'/confirm'
        self.assertEqual(user.post(confirm,json={},headers=HEADERS).status_code,200)
        exported=user.get('/api/ai/csv/export?scope=my')
        self.assertEqual(exported.status_code,200,exported.get_json())
        def records():
            with store.db() as db:
                return {table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                        for table in ('conversations','messages','jobs','message_steps','proposals','ai_audit_artifacts')}
        def business_receipts():
            with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db:
                return (db.execute("SELECT id FROM equipments WHERE name='fixture approved equipment'").fetchall(),
                        db.execute("SELECT AuditId,NewValue FROM audit_logs WHERE Action='AI_EXECUTE'").fetchall())
        before, original = records(), business_receipts()
        self.assertEqual(tuple(map(len,original)),(1,1))
        self.assertEqual(cleanup(self.admin,'all_including_ai','direct').get_json()['remaining_count'],0)
        self.assertEqual(before,records())
        self.assertEqual(user.post(confirm,json={},headers=HEADERS).status_code,200)
        self.assertEqual(original,business_receipts())
        messages=client_for(self.app,41202).get(route+'/messages').get_json()['messages']
        self.assertIn('fixture retained answer',[row['content'] for row in messages])
        self.assertEqual(user.get('/api/ai/jobs/'+jid).get_json()['state'],'done')
        private_files=list(Path(self.app.app.config['USER_AI_AUDIT_ROOT']).glob('*.csv'))
        self.assertEqual([path.read_bytes() for path in private_files],[exported.data])

    def test_chromium_both_scopes_and_failed_finish(self):
        from capture_ai_conversation_entry import Browser
        from werkzeug.serving import make_server
        from werkzeug.wrappers import Response
        with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db, db:
            db.execute(INSERT,event('/api/ai/browser-historic',SEED))
            db.execute(INSERT,event('/browser-general-before'))
        fail_finish = threading.Event()
        def fixture_http(environ, start_response):
            if fail_finish.is_set() and environ['PATH_INFO']=='/api/access_logs/cleanup':
                # Consume the body only on the synthetic proxy and restore it for the real API.
                import io
                raw = environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH') or 0))
                environ['wsgi.input'] = io.BytesIO(raw)
                if json.loads(raw).get('step')=='finish':
                    return Response('{"status":"error"}',status=503,content_type='application/json')(environ,start_response)
            return self.app.app(environ,start_response)
        with make_server('127.0.0.1',0,fixture_http) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            browser=None
            try:
                browser=Browser(str(self.root/'browser-profile'),1100,820)
                origin='http://127.0.0.1:'+str(server.server_port)
                cookie=self.admin.get_cookie(self.app.app.config['SESSION_COOKIE_NAME'])
                browser.cdp('Network.setCookie',{'name':cookie.key,'value':cookie.value,'url':origin})
                browser.cdp('Page.addScriptToEvaluateOnNewDocument',{'source':'window.testNotices=[]; window.alert=s=>testNotices.push(s);'})
                browser.call('POST',browser.sid+'/url',{'url':origin+'/access_logs'})
                browser.until("document.querySelector('#confirmCleanupBtn') && typeof openCleanupModal==='function'")
                for index, (action, fail) in enumerate([('all',False),('all_including_ai',True),('all_including_ai',False)]):
                    if fail:
                        fail_finish.set()
                    else:
                        fail_finish.clear()
                    browser.js("""document.querySelector('[onclick="toggleCleanupMenu()"]').click();
                        document.querySelector('[onclick="openCleanupModal(\\'"""+action+"""\\')"]').click();""")
                    description=browser.js("return document.getElementById('cleanupModalDesc').innerText")
                    self.assertIn('구버전의 미전송 기록',description)
                    browser.js("document.getElementById('confirmCleanupBtn').click()")
                    browser.until('window.testNotices.length === '+str(index+1))
                    message=browser.js('return testNotices.at(-1)')
                    if fail:
                        self.assertIn('실패',message)
                        browser.js('closeCleanupModal()')
                    else:
                        self.assertIn('남은 대상은 0건',message)
                    with closing(sqlite3.connect(self.app.DATABASE_PATH)) as db:
                        kept=db.execute('SELECT COUNT(*) FROM access_logs WHERE RequestPath=?',('/api/ai/browser-historic',)).fetchone()[0]
                        self.assertEqual(kept,int(index==0))
            finally:
                if browser:
                    browser.close()
                server.shutdown()
                thread.join(4)

    def test_legacy_spool_does_not_reappear_after_inclusive_cleanup_and_restart(self):
        isolated=self.root/'restarted'
        spool=isolated/'instance'/'http-audit'/'pending.sqlite3'
        spool.parent.mkdir(parents=True)
        with closing(sqlite3.connect(spool)) as db, db:
            db.execute('CREATE TABLE pending(id INTEGER PRIMARY KEY,body TEXT NOT NULL)')
            db.execute('INSERT INTO pending(body) VALUES (?)',(json.dumps(event('/internal/ai/legacy-only',SEED)),))
        original=hashlib.sha256(spool.read_bytes()).digest()
        for phase in ('initial','restarted'):
            completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--spool-phase',phase,str(isolated)],
                                     cwd=SOURCE, stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=35)
            self.assertEqual(completed.returncode,0,completed.stdout[-3000:])
            self.assertEqual(hashlib.sha256(spool.read_bytes()).digest(), original)
        self.assertEqual([p.name for p in spool.parent.iterdir()],['pending.sqlite3'])


def spool_phase(phase, storage):
    module=fixture_app(storage)
    try:
        client=client_for(module)
        if phase=='initial':
            with closing(sqlite3.connect(module.DATABASE_PATH)) as db, db:
                db.execute(INSERT,event('/api/ai/historical-on-disk',SEED))
            result=cleanup(client,'all_including_ai','direct')
            assert result.status_code==200 and result.get_json()['remaining_count']==0,result.get_json()
        # Give the batch worker a full cycle in each fresh process.
        time.sleep(0.7)
        module.access_log_queue.join()
        with closing(sqlite3.connect(module.DATABASE_PATH)) as db:
            assert db.execute("SELECT COUNT(*) FROM access_logs WHERE RequestPath IN ('/internal/ai/legacy-only','/api/ai/historical-on-disk')").fetchone()[0]==0
    finally:
        module.on_app_exit()


if __name__=='__main__':
    if sys.argv[1:2]==['--spool-phase']:
        sys.path.insert(0,str(SOURCE))
        spool_phase(sys.argv[2],Path(sys.argv[3]))
    else:
        unittest.main()
