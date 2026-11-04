"""[MINI-COMMENT: ASSISTANT.TESTS]
[EN rev.3]
[Role] Exercises real auth/services with synthetic Linux-only databases and a fake model.
[Dependencies] unittest, Flask test client and current source CREATE statements; never imports app.py.
[Impact] Also covers real global audit-hook integration, persistent stop reasons, pagination, v1 migration, reserved storage and normalization without production data/model access.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import wraps
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from flask import Flask, g, jsonify, redirect, request, session, url_for
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from utils import roadmap_schema
from utils.ai_assistant import install_assistant
from utils.ai_assistant.audit import audit_body
from utils.ai_assistant.policy import canonical, LEVELS
from utils.ai_assistant.store import Store
from utils.ai_assistant.worker import sse, Worker
import requests

PROJECT=Path(os.environ.get('EQ_TEST_PROJECT_ROOT',Path.cwd()))
CANDIDATE_ASSETS=globals().get('CANDIDATE_ASSETS',{})


@unittest.skipUnless(os.name=='posix','Actual behavior tests run on isolated Linux fixtures only')
class AssistantTests(unittest.TestCase):
    """[Role] Covers adversarial boundaries, queue races, receipts and real ordinary-user services."""
    def setUp(self):
        """[Role] Creates a fresh source-derived fixture including the actual global audit hook.
        [Dependencies] Extracted CREATE/auth/audit functions, temporary SQLite and a Flask test client.
        [Impact] Exercises integration without importing the production app or opening its database.
        """
        self.tmp=tempfile.TemporaryDirectory(prefix='eq-assistant-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/'equipment-fixture.sqlite3'
        source=ast.parse(globals().get('SOURCE_APP') or (PROJECT/'app.py').read_text(encoding='utf-8-sig'))
        init=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='init_db')
        db=self.connect()
        try:
            for node in ast.walk(init):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='execute' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                    sql=node.args[0].value
                    if sql.lstrip().upper().startswith('CREATE TABLE'):
                        db.execute(sql)
            for table,definitions in {
                'users':{'SessionToken':'TEXT','IsDeleted':"TEXT DEFAULT 'N'",'IsDeactivated':"TEXT DEFAULT 'N'",'DeactivatedAt':'TEXT'},
                'categories':{'NameKo':'TEXT','NameEn':'TEXT'},'manufacturers':{'NameKo':'TEXT','NameEn':'TEXT'},
                'lineup_nodes':{'official_model_name':'TEXT'}}.items():
                columns={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
                for name,definition in definitions.items():
                    if name not in columns:
                        db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
            roadmap_schema.apply_schema(db)
            for uid,role in ((1,'admin'),(2,'user'),(3,'user')):
                db.execute("INSERT INTO users(UserId,LoginId,Password,Name,NickName,Role,SessionToken,IsDeleted,IsDeactivated) VALUES(?,?,?,?,?,?,?,'N','N')",
                    (uid,'fixture-'+str(uid),'not-a-real-password','Fixture','Fixture '+str(uid),role,'token-'+str(uid)))
                db.execute('UPDATE users SET CreatedAt=? WHERE UserId=?',('2026-01-01 00:00:0'+str(uid),uid))
            for menu in ('my_equipment','public_equipment','my_approvals'):
                db.execute("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt) VALUES('user',?,1,'fixture')",(menu,))
            db.execute("INSERT INTO categories(CategoryId,Name,IsApproved) VALUES(1,'Computer',1)")
            db.execute("INSERT INTO manufacturers(ManufacturerId,Name,IsApproved) VALUES(1,'Fixture maker',1)")
            db.execute("INSERT INTO lineup_nodes(id,category_id,manufacturer_id,name,depth,status,official_model_name) VALUES(1,1,1,'Node',1,'APPROVED','Fixture Model')")
            db.execute("INSERT INTO equipment_options(id,lineup_node_id,option_name,specs_json,status) VALUES(1,1,'Base','{}','APPROVED')")
            for eid,owner,public,name in ((2,2,0,'My private'),(3,3,0,'Other private'),(4,3,1,'Other public'),(5,1,0,'Admin private')):
                db.execute('INSERT INTO equipments(id,option_id,name,serial_number,user_id,is_public,is_draft) VALUES(?,1,?,?,?, ?,0)',(eid,name,'SERIAL-'+str(eid),owner,public))
            db.commit()
        finally:
            db.close()
        self.app=Flask('assistant_fixture',static_folder=str(PROJECT/'static'))
        self.app.config.update(TESTING=True,SECRET_KEY='synthetic-assistant-fixture-secret-0123456789',
            USER_AI_ENABLED=True,USER_AI_WRITE_TOOLS=True,USER_AI_WORKER_TOKEN='synthetic-worker-secret-0123456789abcdef',
            USER_AI_PUBLIC_ORIGIN='https://fixture.example',USER_AI_DATABASE=str(self.root/'ai'/'assistant.sqlite3'),
            USER_AI_MODEL_DISCOVERY=False,USER_AI_AUDIT_ROOT=str(self.root/'audit'))
        self.app.jinja_loader=ChoiceLoader([DictLoader({k.removeprefix('templates/'):v for k,v in CANDIDATE_ASSETS.items() if k.startswith('templates/')}),FileSystemLoader(PROJECT/'templates')])
        self.app.add_url_rule('/login','login_page',lambda:'login')
        self.app.add_url_rule('/deactivated_notice','deactivated_notice_page',lambda:'inactive')
        self.app.add_url_rule('/api/check_session','check_session',lambda:jsonify(valid=True))

        @self.app.get('/logout')
        def logout():
            """[Role] Emulates existing cookie clearing so the real assistant revocation hook is exercised."""
            session.clear()
            return 'logout'

        functions=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='login_required']
        namespace=dict(wraps=wraps,session=session,request=request,jsonify=jsonify,redirect=redirect,url_for=url_for,get_db_connection=self.connect)
        exec(compile(ast.Module(body=functions,type_ignores=[]),'real-login-fixture','exec'),namespace)
        self.maintenance={'state':'NORMAL'}
        gate=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='maintenance_request_gate')
        gate.decorator_list=[]
        gate_namespace=dict(app=self.app,request=request,session=session,
            get_maintenance_state=lambda:self.maintenance,STATIC_METADATA_ROUTES_FROZEN=frozenset(),
            get_server_session_role=lambda:(session.get('user') or {}).get('Role'),
            maintenance_block_response=lambda state:(jsonify(success=False,message='점검 중입니다.'),503))
        exec(compile(ast.Module(body=[gate],type_ignores=[]),'real-maintenance-hook-fixture','exec'),gate_namespace)
        self.app.before_request(gate_namespace['maintenance_request_gate'])
        install_assistant(self.app,{'get_db_connection':self.connect,'login_required':namespace['login_required'],
            'get_maintenance_state':lambda:self.maintenance,'ROADMAP_ATTACHMENT_ROOT':str(self.root/'attachments')})
        self.audit_logs=[]
        hook=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='after_request_func')
        hook.decorator_list=[]
        audit_namespace=dict(app=self.app,request=request,session=session,g=g,time=time,datetime=datetime,json=json,
            STATIC_METADATA_ROUTES_FROZEN=frozenset(),push_access_log=self.audit_logs.append,audit_body=audit_body)
        exec(compile(ast.Module(body=[hook],type_ignores=[]),'real-audit-hook-fixture','exec'),audit_namespace)
        self.app.after_request(audit_namespace['after_request_func'])
        self.store=self.app.extensions['equipment_assistant']['store']
        self.domain=self.app.extensions['equipment_assistant']['domain']
        self.client=self.app.test_client()
        self.headers={'Origin':'https://fixture.example','X-CSRFToken':'fixture-csrf'}
        self.worker_headers={'Authorization':'Bearer '+self.app.config['USER_AI_WORKER_TOKEN']}
        self.login(2)

    def connect(self):
        """[Role] Opens only the temporary synthetic fixture with SQLite rows and foreign-key checks."""
        self.equipment_connections=getattr(self,'equipment_connections',0)+1
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def login(self,uid):
        """[Role] Installs a synthetic signed login, not a production cookie or password."""
        with self.client.session_transaction() as current:
            current.clear()
            current.permanent=True
            current['user']={'UserId':uid,'LoginId':'fixture-'+str(uid),'Role':'admin' if uid==1 else 'user','NickName':'Fixture'}
            current['session_token']='token-'+str(uid)
            current['csrf_token']='fixture-csrf'

    def conversation(self):
        """[Role] Creates an owner conversation through the real browser API."""
        response=self.client.post('/api/ai/conversations',json={},headers=self.headers)
        self.assertEqual(response.status_code,201,response.get_json())
        return response.get_json()['id']

    def submit(self,cid=None,content='Help',level='medium',key=None):
        """[Role] Submits a bounded normal browser turn and returns its durable ID."""
        cid=cid or self.conversation()
        result=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':content,'reasoning_version':2,'level':level,'client_key':key or uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(result.status_code,202,result.get_json())
        return result.get_json()['job_id']

    def claim(self):
        """[Role] Claims one application job with the private fixture worker token."""
        result=self.client.post('/internal/ai/claim',json={'worker':'fixture-worker','protocol':3},headers=self.worker_headers)
        self.assertEqual(result.status_code,200,result.get_json())
        return result.get_json()['job']

    def finish(self,job,calls=None,content='Answer',reasoning='',outcome='complete'):
        """[Role] Reports a known completed fake-model step; it does not call Strata."""
        result=self.client.post('/internal/ai/jobs/'+job['id']+'/finish',json={'lease':job['lease'],'outcome':outcome,'content':content,'reasoning':reasoning,'calls':calls or []},headers=self.worker_headers)
        self.assertEqual(result.status_code,200,result.get_json())
        return result.get_json()

    def prepare(self,name='prepare_equipment_create',args=None):
        """[Role] Obtains a frozen proposal through structured tools without committing a business change."""
        jid=self.submit()
        job=self.claim()
        self.assertEqual(job['id'],jid)
        self.finish(job,[{'id':'fixture-call','name':name,'arguments':canonical(args or {'name':'New fixture','option_id':1})}])
        with self.store.db() as db:
            row=db.execute('SELECT * FROM proposals WHERE job=?',(jid,)).fetchone()
        self.assertIsNotNone(row)
        return dict(row)

    def count(self,table):
        """[Role] Reads a known synthetic table count to detect unexpected side effects."""
        db=self.connect()
        try:
            return db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
        finally:
            db.close()

    def test_six_standard_ui_levels(self):
        """[Role] Verifies six standard ui levels and the explicit off wire mapping. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.assertEqual(LEVELS,{'off':'none','low':'low','medium':'medium','high':'high','xhigh':'xhigh','max':'max'})
        result=self.client.get('/api/ai/capabilities').get_json()
        self.assertEqual([v['id'] for v in result['levels']],['off','low','medium','high','xhigh','max'])
        self.assertNotIn('token-2',canonical(result))

    def test_anonymous_and_tampered_cookie(self):
        """[Role] Verifies anonymous and tampered cookie. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.client.set_cookie('session','tampered')
        self.assertEqual(self.client.get('/api/ai/conversations').status_code,401)

    def test_csrf_and_origin_required(self):
        """[Role] Verifies csrf and origin required. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        for headers in ({},{'Origin':'https://fixture.example'},{'X-CSRFToken':'fixture-csrf','Origin':'https://evil.example'}):
            self.assertEqual(self.client.post('/api/ai/conversations',json={},headers=headers).status_code,403)

    def test_client_cannot_supply_roles_or_owner(self):
        """[Role] Verifies client cannot supply roles or owner. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.assertEqual(self.client.post('/api/ai/conversations',json={'owner':3},headers=self.headers).status_code,400)
        cid=self.conversation()
        self.assertEqual(self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Hi','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex,'role':'system'},headers=self.headers).status_code,400)

    def test_cross_user_conversation_job_proposal(self):
        """[Role] Verifies cross user conversation job proposal. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        cid=self.conversation();jid=self.submit(cid)
        self.login(3)
        self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages').status_code,404)
        self.assertEqual(self.client.get('/api/ai/jobs/'+jid).status_code,404)
        self.assertEqual(self.client.post('/api/ai/jobs/'+jid+'/cancel',json={},headers=self.headers).status_code,404)

    def test_cross_user_confirmation_is_404(self):
        """[Role] Verifies cross user confirmation is 404. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        proposal=self.prepare();self.login(3)
        self.assertEqual(self.client.post('/api/ai/proposals/'+proposal['id']+'/confirm',json={},headers=self.headers).status_code,404)
        self.assertEqual(self.count('equipments'),4)

    def test_replay_key_content_bound(self):
        """[Role] Verifies replay key content bound. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        cid=self.conversation();key=uuid.uuid4().hex
        first=self.submit(cid,key=key)
        self.assertEqual(self.submit(cid,key=key),first)
        changed=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Different','reasoning_version':2,'level':'medium','client_key':key},headers=self.headers)
        self.assertEqual(changed.status_code,409)

    def test_queue_claim_race_only_one_application_request(self):
        """[Role] Verifies queue claim race only one application request. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.submit();self.login(3);self.submit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.store.claim,['worker-a','worker-b']))
        self.assertEqual(sum(x is not None for x in results),1)

    def test_step_continuation_goes_behind_other_user(self):
        """[Role] Verifies step continuation goes behind other user. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        a=self.submit();self.login(3);b=self.submit();job=self.claim();self.assertEqual(job['id'],a)
        self.finish(job,[{'id':'read','name':'search_equipment','arguments':'{}'}])
        self.assertEqual(self.claim()['id'],b)

    def test_confirmation_wait_does_not_hold_model_request(self):
        """[Role] Verifies confirmation wait does not hold model request. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare();job=self.claim();self.finish(job)
        self.login(3);jid=self.submit()
        self.assertEqual(self.claim()['id'],jid)
        with self.store.db() as db:
            self.assertEqual(self.store.job(p['job'],db)['state'],'waiting_confirmation')

    def test_logout_revokes_queued_job(self):
        """[Role] Verifies logout revokes queued job. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        jid=self.submit();self.client.get('/logout')
        self.assertIsNone(self.claim())
        with self.store.db() as db:self.assertEqual(self.store.job(jid,db)['state'],'cancelled')

    def test_changed_database_token_cancels_queued_job(self):
        """[Role] Verifies changed database token cancels queued job. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        jid=self.submit()
        with self.connect() as db:db.execute("UPDATE users SET SessionToken='new-login' WHERE UserId=2")
        self.assertIsNone(self.claim())
        with self.store.db() as db:self.assertEqual(self.store.job(jid,db)['state'],'cancelled')

    def test_expiry_does_not_replay(self):
        """[Role] Verifies expiry does not replay. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        jid=self.submit()
        with self.store.db(True) as db:db.execute('UPDATE jobs SET expires=? WHERE id=?',(time.time()-1,jid))
        self.assertIsNone(self.claim())

    def test_passive_reads_do_not_refresh_cookie(self):
        """[Role] Verifies passive reads do not refresh cookie. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.assertNotIn('Set-Cookie',self.client.get('/api/ai/conversations').headers)
        self.assertNotIn('Set-Cookie',self.client.get('/api/check_session',headers={'X-Assistant-Poll':'1'}).headers)
        self.assertIn('Set-Cookie',self.client.get('/api/check_session').headers)

    def test_private_account_context_changes_without_exposing_token(self):
        """[Role] Verifies private account context changes without exposing token. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        first=self.client.get('/api/ai/capabilities').headers['X-Assistant-Account']
        self.login(3)
        second=self.client.get('/api/ai/capabilities').headers['X-Assistant-Account']
        self.assertNotEqual(first,second);self.assertEqual(len(second),32);self.assertNotIn('token-',second)

    def test_reasoning_spacing_and_no_tool_execution(self):
        """[Role] Verifies reasoning spacing and no tool execution. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.submit();job=self.claim()
        for value in ('hello ',' world\n<tool_call>delete</tool_call>'):
            r=self.client.post('/internal/ai/jobs/'+job['id']+'/event',json={'lease':job['lease'],'reasoning':value},headers=self.worker_headers)
            self.assertEqual(r.status_code,200)
        view=self.client.get('/api/ai/jobs/'+job['id']).get_json()
        self.assertEqual(view['reasoning'],'hello  world\n<tool_call>delete</tool_call>')
        self.assertEqual(self.count('equipments'),4)

    def test_saved_reasoning_not_in_later_model_context(self):
        """[Role] Verifies saved reasoning not in later model context. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        cid=self.conversation();self.submit(cid);job=self.claim();self.finish(job,reasoning='PRIVATE_SYNTHETIC_THOUGHT')
        self.submit(cid,content='Next question');next_job=self.claim()
        self.assertNotIn('PRIVATE_SYNTHETIC_THOUGHT',canonical(next_job['messages']))

    def test_preview_does_not_write_and_confirm_is_idempotent(self):
        """[Role] Verifies preview does not write and confirm is idempotent. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare();self.assertEqual(self.count('equipments'),4)
        for _ in range(2):
            r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
            self.assertEqual(r.status_code,200,r.get_json())
        self.assertEqual(self.count('equipments'),5)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_logs WHERE Action='AI_EXECUTE'").fetchone()[0],1)

    def test_lost_ai_state_recovers_equipment_receipt(self):
        """[Role] Verifies lost ai state recovers equipment receipt. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        with self.store.db() as db:job=self.store.job(p['job'],db)
        self.domain.execute(p,job)  # Simulates a committed business transaction before the AI DB update.
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json());self.assertTrue(r.get_json()['result']['replayed'])
        self.assertEqual(self.count('equipments'),5)

    def test_revision_conflict(self):
        """[Role] Verifies revision conflict. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare('prepare_equipment_update',{'equipment_id':2,'name':'AI name'})
        with self.connect() as db:db.execute("UPDATE equipments SET name='Manual change' WHERE id=2")
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,409,r.get_json())

    def test_frozen_proposal_tampering(self):
        """[Role] Verifies frozen proposal tampering. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        with self.store.db(True) as db:db.execute('UPDATE proposals SET payload=? WHERE id=?',(canonical({'name':'Tampered','option_id':1}),p['id']))
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.count('equipments'),4)

    def test_receipt_failure_rolls_back_business_write(self):
        """[Role] Verifies receipt failure rolls back business write. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare();original=self.domain.mutate
        def fail(*args):
            """[Role] Injects a failure after a write but before the receipt commit."""
            original(*args);raise sqlite3.OperationalError('synthetic failure')
        with patch.object(self.domain,'mutate',side_effect=fail):
            self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,500)
        self.assertEqual(self.count('equipments'),4)

    def test_admin_uses_only_own_equipment_and_pending_requests(self):
        """[Role] Verifies admin uses only own equipment and pending requests. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.login(1)
        p=self.prepare('prepare_catalog_request',{'kind':'manufacturer','name':'New maker'})
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json());self.assertEqual(r.get_json()['result']['status'],'PENDING')
        export=self.client.get('/api/ai/csv/export?scope=public').data.decode('utf-8-sig')
        self.assertIn('Other public',export);self.assertNotIn('Other private',export);self.assertNotIn('Admin private',export)

    def test_delete_and_privilege_arguments_never_create_proposal(self):
        """[Role] Verifies delete and privilege arguments never create proposal. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        for name,args in (('delete_equipment',{'equipment_id':2}),('prepare_equipment_create',{'name':'Bad','option_id':1,'UserId':3})):
            self.submit();job=self.claim()
            self.assertEqual(self.finish(job,[{'id':uuid.uuid4().hex,'name':name,'arguments':canonical(args)}])['state'],'failed')
            self.assertIsNone(self.claim())
        with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],0)
        self.assertEqual(self.count('equipments'),4)

    def test_writes_flag_checked_again_at_confirmation(self):
        """[Role] Verifies writes flag checked again at confirmation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare();self.app.config['USER_AI_WRITE_TOOLS']=False
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,403)

    def test_worker_secret_and_local_peer_required(self):
        """[Role] Verifies worker secret and local peer required. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.assertEqual(self.client.post('/internal/ai/claim',json={'worker':'evil'}).status_code,403)
        r=self.client.post('/internal/ai/claim',json={'worker':'evil'},headers=self.worker_headers,environ_overrides={'REMOTE_ADDR':'192.0.2.99'})
        self.assertEqual(r.status_code,403)

    def test_browser_cannot_acknowledge_or_confirm_with_worker_only(self):
        """[Role] Verifies browser cannot acknowledge or confirm with worker only. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        self.assertEqual(self.client.post('/internal/ai/jobs/'+p['job']+'/acknowledge-finished',json={'acknowledgement':'OWN_REQUEST_CONFIRMED_FINISHED'}).status_code,403)
        self.client.set_cookie('session','')
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.worker_headers).status_code,401)

    def test_unknown_request_blocks_replay_and_cancellation_drains(self):
        """[Role] Verifies unknown request blocks replay and cancellation drains. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        jid=self.submit();job=self.claim()
        self.client.post('/api/ai/jobs/'+jid+'/cancel',json={},headers=self.headers)
        self.assertIsNone(self.claim())
        self.finish(job,outcome='recovery_required')
        self.assertIsNone(self.claim())

    def test_user_queue_admission_limit(self):
        """[Role] Verifies user queue admission limit. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.submit();self.submit()
        cid=self.conversation()
        r=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Third','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(r.status_code,429)

    def test_file_owner_and_signature_checks(self):
        """[Role] Verifies file owner and signature checks. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        r=self.client.post('/api/ai/equipment/3/files',data={'file':(io.BytesIO(b'%PDF-1.7\nfixture\n%%EOF'),'x.pdf')},headers=self.headers)
        self.assertEqual(r.status_code,404)
        r=self.client.post('/api/ai/equipment/2/files',data={'file':(io.BytesIO(b'<script>evil</script>'),'x.pdf')},headers=self.headers)
        self.assertEqual(r.status_code,400)

    def test_csv_token_is_owner_bound_and_idempotent(self):
        """[Role] Verifies csv token is owner bound and idempotent. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        raw=b'Name,OptionId,SerialNumber,PurchaseDate,WarrantyEndDate,ReplacementDueDate,IsPublic,Memo\nCSV fixture,1,CSV-UNIQUE,,,,0,Note\n'
        r=self.client.post('/api/ai/csv/preview',data={'file':(io.BytesIO(raw),'fixture.csv')},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json());token=r.get_json()['token'];self.assertTrue(token,r.get_json())
        self.login(3)
        self.assertEqual(self.client.post('/api/ai/csv/commit',json={'token':token},headers=self.headers).status_code,404)
        self.login(2)
        for _ in range(2):self.assertEqual(self.client.post('/api/ai/csv/commit',json={'token':token},headers=self.headers).status_code,200)
        self.assertEqual(self.count('equipments'),5)

    def test_menu_revocation_disables_existing_proposal(self):
        """[Role] Verifies menu revocation disables existing proposal. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        with self.connect() as db:db.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE Role='user' AND MenuCode='my_equipment'")
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,403)

    def test_invalid_levels_and_message_size(self):
        """[Role] Verifies invalid levels and message size. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        cid=self.conversation()
        for level in ('unsupported','admin',[],{}):
            r=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Hello','reasoning_version':2,'level':level,'client_key':uuid.uuid4().hex},headers=self.headers)
            self.assertEqual(r.status_code,400,r.get_json())

    def test_reviewed_option_change_blocks_confirmation(self):
        """[Role] Verifies reviewed option change blocks confirmation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        with self.connect() as db:db.execute("UPDATE equipment_options SET option_name='Changed' WHERE id=1")
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.count('equipments'),4)

    def test_simultaneous_confirmations_create_only_once(self):
        """[Role] Verifies simultaneous confirmations create only once. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        with self.store.db() as db:job=self.store.job(p['job'],db)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.domain.execute(p,job),range(2)))
        self.assertEqual(results[0]['equipment_id'],results[1]['equipment_id'])
        self.assertEqual(self.count('equipments'),5)

    def test_search_only_own_matches_and_reports_total(self):
        """[Role] Verifies search only own matches and reports total. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.submit();job=self.claim()
        self.finish(job,[{'id':'read','name':'search_equipment','arguments':canonical({'query':'private','scope':'my'})}])
        with self.store.db() as db:context=json.loads(self.store.job(job['id'],db)['context'])
        result=json.loads(context[-1]['content'])
        self.assertEqual(result['total'],1)
        self.assertEqual([r['Name'] for r in result['equipment']],['My private'])

    def test_cancelled_proposal_cannot_be_confirmed(self):
        """[Role] Verifies cancelled proposal cannot be confirmed. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare()
        self.client.post('/api/ai/jobs/'+p['job']+'/cancel',json={},headers=self.headers)
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.count('equipments'),4)

    def test_status_change_uses_revision_and_audit(self):
        """[Role] Verifies status change uses revision and audit. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare('prepare_equipment_status',{'equipment_id':2,'status':'REPAIR','reason':'검사 중'})
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json())
        with self.connect() as db:
            row=db.execute('SELECT status,revision FROM equipments WHERE id=2').fetchone()
        self.assertEqual(tuple(row),('REPAIR',1))

    def test_option_request_has_pending_receipt_number(self):
        """[Role] Verifies option request has pending receipt number. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare('prepare_option_request',{'lineup_node_id':1,'option_name':'Requested','specs_json':'{"RAM":"32 GB"}'})
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json())
        self.assertEqual(r.get_json()['result']['status'],'PENDING')
        self.assertIsInstance(r.get_json()['result']['request_id'],int)

    def test_node_request_has_pending_receipt_number(self):
        """[Role] Verifies node request has pending receipt number. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        p=self.prepare('prepare_catalog_request',{'kind':'node','name':'New node','category_id':1,'manufacturer_id':1,'parent_id':1})
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json());self.assertIsInstance(r.get_json()['result']['request_id'],int)

    def test_preferences_preserve_existing_keys_and_actual_result_in_history(self):
        """[Role] Verifies preferences preserve existing keys and actual result in history. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        with self.connect() as db:db.execute("INSERT INTO user_settings(UserId,PreferencesJSON) VALUES(2,'{\"unrelated\":\"keep\"}')")
        p=self.prepare('prepare_preferences',{'theme':'dark'})
        r=self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_json())
        with self.connect() as db:settings=json.loads(db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=2').fetchone()[0])
        self.assertEqual(settings,{'unrelated':'keep','theme':'dark'})
        with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM messages WHERE job IS NULL').fetchone()[0],1)

    def test_maintenance_revision_invalidates_old_delegation(self):
        """[Role] Verifies maintenance revision invalidates old delegation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        jid=self.submit()
        self.maintenance['revision']=1
        self.assertIsNone(self.claim())
        with self.store.db() as db:self.assertEqual(self.store.job(jid,db)['state'],'cancelled')

    def test_turn_rate_limit_does_not_charge_idempotent_retries(self):
        """[Role] Verifies turn rate limit does not charge idempotent retries. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.store.turn_limit_minute=1
        cid=self.conversation();key=uuid.uuid4().hex
        first=self.submit(cid,key=key)
        self.assertEqual(self.submit(cid,key=key),first)
        other=self.conversation()
        r=self.client.post('/api/ai/conversations/'+other+'/turns',json={'content':'More','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(r.status_code,429)

    def test_storage_quota_preserves_existing_input(self):
        """[Role] Verifies storage quota preserves existing input. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        self.store.history_limit=5
        self.store.completion_reserve=0
        cid=self.conversation()
        r=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Too much input','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(r.status_code,429)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)

    def test_reused_user_number_cannot_rebind_previous_chat_or_proposal(self):
        """[Role] Simulates restored/reused IDs with even the same token. [Dependencies] Synthetic account birth identity. [Impact] Old conversations/results remain private and preserved."""
        p=self.prepare()
        with self.store.db() as db:old_job=self.store.job(p['job'],db)
        with self.connect() as db:db.execute("UPDATE users SET LoginId='replacement',CreatedAt='2027-01-01 00:00:00' WHERE UserId=2")
        self.assertEqual(self.client.get('/api/ai/conversations').get_json()['conversations'],[])
        self.assertEqual(self.client.get('/api/ai/conversations/'+old_job['conversation']+'/messages').status_code,404)
        self.assertEqual(self.client.get('/api/ai/jobs/'+p['job']).status_code,404)
        self.assertEqual(self.client.post('/api/ai/proposals/'+p['id']+'/confirm',json={},headers=self.headers).status_code,404)
        self.assertIsNone(self.claim())
        with self.store.db() as db:self.assertGreater(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)

    def test_login_name_change_keeps_account_chat(self):
        """[Role] Keeps the original account's history through a profile rename. [Dependencies] Stable source CreatedAt. [Impact] Does not confuse mutable login names with a new person."""
        cid=self.conversation()
        with self.connect() as db:db.execute("UPDATE users SET LoginId='renamed' WHERE UserId=2")
        self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages').status_code,200)

    def test_global_audit_preserves_ai_content_and_protects_lease(self):
        """[Role] Tests the actual global hook, not a separate logging mock. [Dependencies] AST-extracted hook and synthetic private lease. [Impact] Business content remains auditable without reusable worker grants."""
        jid=self.submit(content='감사할 비공개 업무 내용');job=self.claim()
        self.finish(job,content='보관할 업무 답변',reasoning='보관할 추론 내용')
        payloads=canonical(self.audit_logs)
        for value in ('감사할 비공개 업무 내용','보관할 업무 답변','보관할 추론 내용'):
            self.assertIn(value,payloads)
        self.assertNotIn(job['lease'],payloads)
        self.assertNotIn(self.app.config['USER_AI_WORKER_TOKEN'],payloads)
        self.assertIn('보호된 인증값:',payloads)
        claim=next(log for log in self.audit_logs if log['RequestPath']=='/internal/ai/claim')
        finish=next(log for log in self.audit_logs if log['RequestPath'].endswith('/finish'))
        self.assertEqual(json.loads(claim['ResponsePayload'])['job']['lease'],json.loads(finish['RequestPayload'])['lease'])
        self.assertEqual(self.client.get('/api/ai/jobs/'+jid).get_json()['state'],'done')

    def test_audit_csv_token_and_html_csrf_fingerprint_keep_content(self):
        """[Role] Checks browser tokens and malformed JSON fallback. [Dependencies] Global hook and pure formatter with a stable synthetic key. [Impact] Token protection does not suppress audit events or ordinary token discussion."""
        with self.client.session_transaction() as current:current['csrf_token']='synthetic-csrf-secret-0123456789'
        response=self.client.get('/assistant');self.assertEqual(response.status_code,200)
        self.assertNotIn('synthetic-csrf-secret-0123456789',self.audit_logs[-1]['ResponsePayload'])
        key=self.app.secret_key
        body=audit_body(canonical({'token':'csv-once-only-12345','content':'장비 토큰에 관해 설명해 줘'}),key)
        self.assertIn('장비 토큰에 관해 설명해 줘',body);self.assertNotIn('csv-once-only-12345',body)
        self.assertIn('보호된 인증값:',audit_body('{"lease":"secret-grant-12345", broken',key))
        self.assertEqual(audit_body(None,key),None)

    def test_bad_completed_calls_fail_release_queue_and_save_reason(self):
        """[Role] Stops duplicate/missing tool IDs before preparing any proposal. [Dependencies] Valid worker completion and a second owner's queued job. [Impact] Bad responses cannot poison the shared application queue or leave executable cards."""
        jid=self.submit();job=self.claim();self.login(3);other=self.submit();self.login(2)
        calls=[{'id':'same','name':'prepare_equipment_create','arguments':canonical({'name':'X','option_id':1})}]*2
        result=self.finish(job,calls,content='수신한 부분 답변',reasoning='수신한 부분 추론')
        self.assertEqual(result['state'],'failed');self.assertEqual(result['error_code'],'INVALID_TOOL_CALL')
        view=self.client.get('/api/ai/jobs/'+jid).get_json()
        self.assertTrue(view['error']);self.assertIn('수신한 부분 답변',view['content'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM proposals WHERE job=?',(jid,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT reserved_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0],0)
        self.assertEqual(self.claim()['id'],other)

    def test_invalid_tool_protocol_stops_for_each_malformed_shape(self):
        """[Role] Rejects blank IDs, unknown tools, malformed argument JSON and unknown fields. [Dependencies] Real completion finalizer. [Impact] Protocol errors end the job with a persisted safe reason."""
        for call in ({'id':'','name':'search_equipment','arguments':'{}'},
                     {'id':'x','name':'execute_sql','arguments':'{}'},
                     {'id':'x','name':'search_equipment','arguments':'{'},
                     {'id':'x','name':'search_equipment','arguments':'{}','owner':1}):
            with self.subTest(call=call):
                self.submit();job=self.claim();result=self.finish(job,[call])
                self.assertEqual(result['state'],'failed')
                self.assertTrue(self.client.get('/api/ai/jobs/'+job['id']).get_json()['error'])

    def test_unexpected_domain_error_finalizes_and_cancels_earlier_card(self):
        """[Role] Stops a later processing exception after a valid earlier proposal. [Dependencies] Injected fixture exception and real proposal cancellation. [Impact] Failed answers leave no pending action for the user to execute."""
        self.submit();job=self.claim()
        original=self.domain.read_or_prepare;count=0
        def injected(*args,**kwargs):
            """[Role] Raises only on the second synthetic tool. [Dependencies] Original domain function. [Impact] Exercises partial preparation rollback-by-cancellation."""
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('DO_NOT_EXPOSE_PRIVATE_STACK')
            return original(*args,**kwargs)
        calls=[{'id':str(i),'name':'prepare_equipment_create','arguments':canonical({'name':'X'+str(i),'option_id':1})} for i in range(2)]
        with patch.object(self.domain,'read_or_prepare',side_effect=injected):result=self.finish(job,calls)
        self.assertEqual(result['state'],'failed');self.assertNotIn('DO_NOT_EXPOSE_PRIVATE_STACK',canonical(result))
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM proposals WHERE job=? AND state='pending'",(job['id'],)).fetchone()[0],0)

    def test_unknown_response_stopped_reason_and_explicit_own_recovery(self):
        """[Role] Keeps an uncertain request locked while showing a saved interruption reason. [Dependencies] Private own-request acknowledgement. [Impact] No inference replay or other-service control occurs; confirmed shutdown releases reservation."""
        jid=self.submit();job=self.claim()
        result=self.client.post('/internal/ai/jobs/'+jid+'/finish',json={'lease':job['lease'],'outcome':'recovery_required','error_code':'CONNECTION_TIMEOUT','content':'부분','reasoning':'검토','calls':[]},headers=self.worker_headers)
        self.assertEqual(result.status_code,200)
        view=self.client.get('/api/ai/jobs/'+jid).get_json()
        self.assertEqual(view['state'],'recovery_required');self.assertIn('시간',view['error'])
        self.assertIsNone(self.claim())
        result=self.client.post('/internal/ai/jobs/'+jid+'/acknowledge-finished',json={'acknowledgement':'OWN_REQUEST_CONFIRMED_FINISHED'},headers=self.worker_headers)
        self.assertEqual(result.status_code,200)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT reserved_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0],0)

    def test_known_failed_outcome_keeps_length_reason_and_partial_output(self):
        """[Role] Persists a model length-stop reason and accepted text. [Dependencies] Known finished worker report. [Impact] The queue becomes available without presenting a failed answer as success."""
        jid=self.submit();job=self.claim()
        result=self.client.post('/internal/ai/jobs/'+jid+'/finish',json={'lease':job['lease'],'outcome':'failed','error_code':'LENGTH_LIMIT','content':'받은 결과','reasoning':'받은 추론','calls':[]},headers=self.worker_headers)
        self.assertEqual(result.get_json()['state'],'failed')
        view=self.client.get('/api/ai/jobs/'+jid).get_json()
        self.assertEqual(view['error_code'],'LENGTH_LIMIT');self.assertIn('받은 결과',view['content']);self.assertTrue(view['error'])

    def test_multistep_reasoning_and_repeated_offset_do_not_duplicate(self):
        """[Role] Retains both reasoning steps and acknowledges a lost-ack retry. [Dependencies] Actual event offsets and final snapshot reconciliation. [Impact] Cursors stay monotonic and storage is charged once."""
        jid=self.submit();job=self.claim()
        payload={'lease':job['lease'],'reasoning':'첫 단계 생각','content':'도구 호출 설명','reasoning_offset':0,'content_offset':0}
        for _ in range(2):self.assertEqual(self.client.post('/internal/ai/jobs/'+jid+'/event',json=payload,headers=self.worker_headers).status_code,200)
        self.finish(job,[{'id':'x','name':'search_equipment','arguments':canonical({'scope':'my'})}],reasoning='첫 단계 생각',content='도구 호출 설명')
        next_job=self.claim();self.assertEqual(next_job['id'],jid)
        self.finish(next_job,reasoning='둘째 단계 생각',content='최종 답변')
        view=self.client.get('/api/ai/jobs/'+jid).get_json()
        self.assertEqual(view['reasoning'],'첫 단계 생각\n\n둘째 단계 생각');self.assertTrue(view['answer_started'])
        self.assertEqual(view['content'],'최종 답변')
        with self.store.db() as db:
            actual=db.execute('SELECT SUM(length(m.content)+length(m.reasoning)) FROM messages m').fetchone()[0]+db.execute('SELECT COALESCE(SUM(handoff_chars),0) FROM jobs').fetchone()[0]
            self.assertEqual(actual,db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0])

    def test_all_two_hundred_conversations_reachable_without_foreign_leak(self):
        """[Role] Traverses the full retained title limit and hostile foreign cursors. [Dependencies] Owner/account key predicates on each stable page. [Impact] The old recent-100 cutoff is removed without expanding visibility."""
        cid=self.conversation()
        with self.store.db(True) as db:
            account=db.execute('SELECT account_key FROM conversations WHERE id=?',(cid,)).fetchone()[0]
            for i in range(199):db.execute('INSERT INTO conversations(id,owner,account_key,title,created,updated) VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,2,account,str(i),time.time()-i-10,time.time()-i-10))
        seen=set();cursor=None
        for _ in range(4):
            result=self.client.get('/api/ai/conversations',query_string={'cursor':cursor} if cursor else {}).get_json()
            seen.update(item['id'] for item in result['conversations']);cursor=result['next_cursor']
        self.assertEqual(len(seen),200);self.assertIsNone(cursor)
        self.login(3)
        foreign=self.client.get('/api/ai/conversations',query_string={'cursor':'%%%'});self.assertEqual(foreign.status_code,400)
        import base64
        crafted=base64.urlsafe_b64encode(canonical([time.time()+100,cid]).encode()).decode()
        self.assertEqual(self.client.get('/api/ai/conversations',query_string={'cursor':crafted}).get_json()['conversations'],[])

    def test_more_than_sixty_messages_reachable_and_owner_guarded(self):
        """[Role] Reads every retained message across before pages. [Dependencies] Synthetic older rows and owner-scoped conversation access. [Impact] No saved message is hidden behind the old sixty-message cutoff."""
        cid=self.conversation()
        with self.store.db(True) as db:
            for i in range(135):db.execute("INSERT INTO messages(conversation,role,content,created) VALUES(?,'user',?,?)",(cid,str(i),time.time()))
        seen=[];before=None
        for _ in range(3):
            result=self.client.get('/api/ai/conversations/'+cid+'/messages',query_string={'before':before} if before else {}).get_json()
            seen+=result['messages'];before=result['next_before']
        self.assertEqual(len({item['id'] for item in seen}),135);self.assertIsNone(before)
        self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages?before=-1').status_code,400)
        self.login(3);self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages?before=100').status_code,404)

    def test_extended_storage_reserves_completion_and_retains_output_over_base(self):
        """[Role] Admits a completion beyond the base using explicit extra budget. [Dependencies] Small synthetic limits and the real character ledger. [Impact] Input, reasoning and final answer remain stored and reported above the baseline."""
        self.store.history_limit=5;self.store.completion_reserve=3000;self.store.output_reservation=2000
        jid=self.submit(content='four');job=self.claim();self.finish(job,reasoning='123456',content='abcdefghij')
        view=self.client.get('/api/ai/jobs/'+jid).get_json()
        with self.store.db() as db:handoff=db.execute('SELECT handoff_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0]
        self.assertEqual(view['storage']['used_chars'],20+handoff);self.assertTrue(view['storage']['above_base'])
        self.assertEqual(view['storage']['reserved_chars'],0)

    def test_storage_reservations_prevent_oversubscription_and_release_on_cancel(self):
        """[Role] Reserves future completion before admitting another conversation. [Dependencies] Small fixture allowance and normal cancellation. [Impact] Concurrent accepted jobs cannot spend the same completion space."""
        self.store.history_limit=0;self.store.completion_reserve=10000;self.store.output_reservation=6000
        jid=self.submit(content='one');cid=self.conversation()
        response=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'two','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(response.status_code,429)
        self.assertEqual(self.client.post('/api/ai/jobs/'+jid+'/cancel',json={},headers=self.headers).status_code,200)
        self.submit(cid,content='two')

    def test_confirmed_receipt_counted_once_and_survives_budget_reduction(self):
        """[Role] Counts a real confirmation receipt once even after a policy reduction. [Dependencies] Atomic equipment receipt and AI reservation ledger. [Impact] Completed business evidence is preserved; new work alone is blocked."""
        proposal=self.prepare();job=self.claim();self.finish(job)
        self.store.history_limit=1;self.store.completion_reserve=0
        path='/api/ai/proposals/'+proposal['id']+'/confirm'
        self.assertEqual(self.client.post(path,json={},headers=self.headers).status_code,200)
        with self.store.db() as db:used=db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0]
        self.assertEqual(self.client.post(path,json={},headers=self.headers).status_code,200)
        with self.store.db() as db:
            self.assertEqual(used,db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0])
            self.assertEqual(db.execute('SELECT SUM(length(content)+length(reasoning)) FROM messages').fetchone()[0]+db.execute('SELECT COALESCE(SUM(handoff_chars),0) FROM jobs').fetchone()[0],used)
            self.assertEqual(db.execute('SELECT SUM(reserved_chars) FROM jobs').fetchone()[0],0)

    def test_v1_additive_migration_preserves_history_and_uncertain_lock(self):
        """[Role] Reopens a genuine v1 table layout with a live uncertain job. [Dependencies] Synthetic prior schema columns and retained rows, never production DB. [Impact] Migration is additive/idempotent and never steals the old request lock."""
        jid=self.submit();job=self.claim();self.store.append(jid,job['lease'],'보존할 추론','보존할 내용')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET state='recovery_required' WHERE id=?",(jid,))
            db.execute('DROP TABLE message_steps');db.execute('DROP TABLE storage_accounts')
            db.execute('ALTER TABLE jobs DROP COLUMN error_code');db.execute('ALTER TABLE jobs DROP COLUMN reserved_chars')
            db.execute('UPDATE ai_meta SET version=1')
        for _ in range(2):
            migrated=Store(self.store.path)
            self.assertIsNone(migrated.claim('fixture-new-worker'))
            with migrated.db() as db:
                self.assertEqual(db.execute('SELECT version FROM ai_meta').fetchone()[0],3)
                self.assertEqual(db.execute("SELECT reasoning FROM messages WHERE job=? AND role='assistant'",(jid,)).fetchone()[0],'보존할 추론')
                actual=db.execute('SELECT SUM(length(content)+length(reasoning)) FROM messages').fetchone()[0]+db.execute('SELECT COALESCE(SUM(handoff_chars),0) FROM jobs').fetchone()[0]
                self.assertEqual(actual,db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0])
                self.assertGreater(db.execute('SELECT reserved_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0],0)

    def test_normalized_equipment_proposal_and_stored_values_match(self):
        """[Role] Freezes normalized dates/serial and uses the same values at commit. [Dependencies] Shared validator return and real domain confirmation. [Impact] Padded valid dates no longer fail and canonical serial duplicates are caught."""
        proposal=self.prepare(args={'name':' 정규화 장비 ','option_id':1,'serial_number':' SERIAL-NORMAL ','purchase_date':' 2026-11-04 '})
        payload=json.loads(proposal['payload'])
        self.assertEqual(payload['purchase_date'],'2026-11-04');self.assertEqual(payload['serial_number'],'SERIAL-NORMAL')
        result=self.client.post('/api/ai/proposals/'+proposal['id']+'/confirm',json={},headers=self.headers).get_json()
        self.assertTrue(result['success'])
        with self.connect() as db:
            row=db.execute('SELECT serial_number,purchase_date FROM equipments WHERE id=?',(result['result']['equipment_id'],)).fetchone()
            self.assertEqual(tuple(row),('SERIAL-NORMAL','2026-11-04'))


@unittest.skipUnless(os.name=='posix','Linux-only protocol tests')
class ProtocolTests(unittest.TestCase):
    """[Role] Verifies real SSE parser/worker payload boundaries with deterministic fake transports."""
    def response(self,frames):
        """[Role] Builds a fake response without any network/GPU request."""
        class Reply:
            status_code=200
            headers={'Content-Type':'text/event-stream'}
            def __enter__(self): """[Role] Implements the synthetic __enter__ transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return self
            def __exit__(self,*args): """[Role] Implements the synthetic __exit__ transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return False
            def raise_for_status(self): """[Role] Implements the synthetic raise_for_status transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return None
            def iter_lines(self,**kwargs): """[Role] Implements the synthetic iter_lines transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return iter(frames)
        return Reply()

    def test_sse_whitespace_unicode_and_done(self):
        """[Role] Verifies sse whitespace unicode and done. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        reply=self.response([': pulse','','data: '+json.dumps({'choices':[{'delta':{'reasoning_content':'공백 '}}]}),'','data: [DONE]',''])
        items=list(sse(reply));self.assertEqual(items[-1],'[DONE]');self.assertEqual(items[2]['choices'][0]['delta']['reasoning_content'],'공백 ')

    def test_sse_without_done_is_failure(self):
        """[Role] Verifies sse without done is failure. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        with self.assertRaises(ValueError):list(sse(self.response(['data: {}',''])))

    def test_worker_uses_separate_reasoning_and_no_shared_control(self):
        """[Role] Verifies worker uses separate reasoning and no shared control. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
        frames=[]
        for delta,finish in (({'reasoning_content':'Inspect '},None),({'reasoning_content':'safely. '},None),({'content':'Answer'},'stop')):
            frames.extend(['data: '+json.dumps({'choices':[{'delta':delta,'finish_reason':finish}]}),''])
        frames.extend(['data: [DONE]',''])
        reply=self.response(frames)
        class Client:
            def __enter__(self): """[Role] Implements the synthetic __enter__ transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return self
            def __exit__(self,*args): """[Role] Implements the synthetic __exit__ transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access.""";return False
            def post(self,*args,**kwargs):
                """[Role] Implements the synthetic post transport/context operation. [Dependencies] Isolated Linux fixture and deterministic inputs. [Impact] Detects regressions without production data/model access."""
                self.request=(args,kwargs);return reply
        client=Client()
        worker=Worker('http://127.0.0.1:5000','worker-fixture-key-0123456789012345','http://127.0.0.1:9000','strata-fixture-key','fixture-model')
        reports=[]
        worker.post=lambda path,data:(reports.append((path,data)) or {'success':True,'cancel':False})
        with patch('utils.ai_assistant.worker.requests.Session',return_value=client):
            worker.run_job({'id':'a'*32,'lease':'private-lease','messages':[{'role':'user','content':'Hi'}],'tools':[],'reasoning_effort':'xhigh'})
        payload=client.request[1]['json']
        self.assertFalse(payload['strata_mcp']);self.assertEqual(payload['reasoning_effort'],'xhigh')
        self.assertNotIn('strata-fixture-key',canonical(payload))
        self.assertEqual(reports[-1][1]['reasoning'],'Inspect safely. ')
        self.assertEqual(reports[-1][1]['content'],'Answer');self.assertEqual(reports[-1][1]['outcome'],'complete')
        self.assertTrue(all('/internal/ai/jobs/' in path for path,_ in reports))

    def fake_worker(self,frames=(),status=200,exception=None,retry_report=False):
        """[Role] Runs a synthetic response through the real worker. [Dependencies] Fake requests transport and private report sink. [Impact] Never contacts Strata; counts inference versus finish-report delivery separately."""
        reply=self.response(frames);reply.status_code=status
        client=MagicMock();client.__enter__.return_value=client
        if exception:client.post.side_effect=exception
        else:client.post.return_value=reply
        worker=Worker('http://127.0.0.1:5000','worker-fixture-key-0123456789012345','http://127.0.0.1:9000','strata-fixture-key','fixture-model')
        reports=[]
        def report(path,data):
            """[Role] Captures reports with optional first-delivery loss. [Dependencies] Fixture report list. [Impact] Tests report retries without repeating inference."""
            reports.append((path,data))
            if retry_report and path.endswith('/finish') and sum(item[0].endswith('/finish') for item in reports)==1:raise requests.ConnectionError('synthetic delivery loss')
            return {'success':True,'cancel':False}
        worker.post=report
        with patch('utils.ai_assistant.worker.requests.Session',return_value=client),patch.object(worker.stop,'wait',return_value=False):
            worker.run_job({'id':'a'*32,'lease':'private-lease','messages':[],'tools':[],'reasoning_effort':'medium'})
        return reports,client

    def test_worker_known_rejection_and_length_stop_have_safe_reasons(self):
        """[Role] Classifies definitive HTTP rejection and length termination. [Dependencies] Real worker with synthetic SSE. [Impact] Known failures are reported as stopped, never as successful tool continuation."""
        reports,_=self.fake_worker(status=429)
        self.assertEqual((reports[-1][1]['outcome'],reports[-1][1]['error_code']),('failed','UPSTREAM_REJECTED'))
        reports,_=self.fake_worker(['data: '+json.dumps({'choices':[{'delta':{'content':'부분'},'finish_reason':'length'}]}),'','data: [DONE]',''])
        self.assertEqual((reports[-1][1]['outcome'],reports[-1][1]['error_code']),('failed','LENGTH_LIMIT'))
        self.assertEqual(reports[-1][1]['content'],'부분')

    def test_worker_timeout_and_broken_stream_hold_only_uncertain_own_lock(self):
        """[Role] Classifies timeout and missing DONE without replay. [Dependencies] Real worker and failed synthetic transport. [Impact] User receives safe stop codes while unknown upstream completion remains reserved."""
        reports,client=self.fake_worker(exception=requests.ReadTimeout('PRIVATE_ENDPOINT_DETAILS'))
        self.assertEqual((reports[-1][1]['outcome'],reports[-1][1]['error_code']),('recovery_required','CONNECTION_TIMEOUT'))
        self.assertNotIn('PRIVATE_ENDPOINT_DETAILS',canonical(reports));self.assertEqual(client.post.call_count,1)
        reports,client=self.fake_worker(['data: {}',''])
        self.assertEqual(reports[-1][1]['error_code'],'STREAM_INCOMPLETE');self.assertEqual(client.post.call_count,1)

    def test_worker_retries_finish_delivery_without_replaying_inference(self):
        """[Role] Retries only a fixed completion report after delivery loss. [Dependencies] One synthetic model response. [Impact] A transient local API failure cannot silently leave a known job running or repeat a model/tool request."""
        reports,client=self.fake_worker(['data: '+json.dumps({'choices':[{'delta':{'content':'끝'},'finish_reason':'stop'}]}),'','data: [DONE]',''],retry_report=True)
        finishes=[data for path,data in reports if path.endswith('/finish')]
        self.assertEqual(len(finishes),2);self.assertEqual(finishes[0],finishes[1]);self.assertEqual(client.post.call_count,1)

    def test_worker_flushes_explicit_step_offsets(self):
        """[Role] Attaches monotonic per-step offsets to separate text batches. [Dependencies] Synthetic multi-frame response and real flush boundary. [Impact] A retried event is distinguishable from new text and cannot duplicate reasoning."""
        frames=[]
        for delta,finish in (({'reasoning_content':'가'*4096},None),({'reasoning_content':'나','content':'답변'},'stop')):
            frames.extend(['data: '+json.dumps({'choices':[{'delta':delta,'finish_reason':finish}]}),''])
        frames.extend(['data: [DONE]',''])
        reports,_=self.fake_worker(frames)
        events=[data for path,data in reports if path.endswith('/event') and 'reasoning' in data]
        self.assertEqual([data['reasoning_offset'] for data in events],[0,4096])
        self.assertEqual([data['content_offset'] for data in events],[0,0])


if __name__=='__main__':
    unittest.main()
