"""[MINI-COMMENT: ASSISTANT.UX.INTEGRATION.TESTS]
[EN rev.1]
[Role] Exercises the seven-improvement API boundaries on source-derived synthetic Linux fixtures.
[Dependencies] Existing AssistantTests helpers, staged routes/store and temporary business/AI SQLite only.
[Impact] Tests real normalization, lifecycle, diagnostic segregation and menu migration without production access.
"""
import json
import os
import unittest
import uuid
from unittest.mock import patch

from flask import Flask
from assistant_fixture_tests import AssistantTests
from utils.ai_assistant import install_assistant, visible_assistant_menus
from utils.ai_assistant.policy import AssistantError, canonical, normalized_tool_arguments


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class UXIntegrationTests(unittest.TestCase):
    setUp = AssistantTests.setUp
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit
    claim = AssistantTests.claim
    finish = AssistantTests.finish
    prepare = AssistantTests.prepare
    count = AssistantTests.count

    def lifecycle(self, cid, action, revision, operation_id=None):
        """[Role] Sends one explicit user lifecycle action. [Dependencies] Fixture CSRF/session. [Impact] No model or business tool can request deletion."""
        return self.client.post('/api/ai/conversations/' + cid + '/' + action,
            json={'lifecycle_revision': revision, 'operation_id': operation_id or uuid.uuid4().hex}, headers=self.headers)

    def test_empty_read_filters_share_strict_canonical_contract(self):
        """[Role] Covers the actual refused status value and nearby invalid inputs. [Dependencies] Shared production validator. [Impact] Read convenience never weakens write enums or closed schemas."""
        raw={'scope':'my','query':'','page':1,'status':'','due':''}
        self.assertEqual(normalized_tool_arguments('search_equipment',raw),{'scope':'my','query':'','page':1})
        self.assertEqual(raw['status'],'')
        for invalid in (None,False,[],{},'active',' ACTIVE','INVALID'):
            with self.subTest(invalid=invalid),self.assertRaises(AssistantError):
                normalized_tool_arguments('search_equipment',{'status':invalid})
        with self.assertRaises(AssistantError):
            normalized_tool_arguments('search_equipment',{'owner':3})
        with self.assertRaises(AssistantError):
            normalized_tool_arguments('prepare_equipment_status',{'equipment_id':2,'status':'','reason':'test'})

    def test_refused_empty_filter_request_now_reaches_real_owner_query(self):
        """[Role] Sends the original failed tool input through HTTP validation and domain dispatch. [Dependencies] Real fixture equipment services. [Impact] Verifies the fix instead of only checking schema text."""
        cid=self.conversation()
        jid=self.submit(cid,content='내 장비 리스트를 표 형태로 출력해주세요')
        job=self.claim()
        raw=canonical({'scope':'my','query':'','page':1,'status':'','due':''})
        result=self.finish(job,[{'id':'read-empty','name':'search_equipment','arguments':raw}])
        self.assertEqual(result['state'],'queued')
        with self.store.db() as db:
            context=json.loads(db.execute('SELECT context FROM jobs WHERE id=?',(jid,)).fetchone()[0])
        tool_result=json.loads(next(item['content'] for item in context if item['role']=='tool'))
        self.assertNotIn('error',tool_result)
        self.assertGreaterEqual(tool_result['total'],1)
        self.assertEqual(tool_result['scope'],'my')
        original=next(item for item in context if item['role']=='assistant' and item.get('tool_calls'))
        self.assertEqual(original['tool_calls'][0]['function']['arguments'],raw)

    def test_mixed_history_keeps_chat_but_excludes_probe_nonce_from_model_context(self):
        """[Role] Reproduces mixed legacy diagnostics without altering their original records. [Dependencies] Persisted job purpose and actual claim context builder. [Impact] A nonce never becomes normal user dialogue."""
        cid=self.conversation()
        self.submit(cid,content='normal source question')
        self.finish(self.claim(),content='normal saved answer')
        probe_id=self.submit(cid,content='private probe nonce-42')
        self.finish(self.claim(),content='private probe nonce-42')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET purpose='probe' WHERE id=?",(probe_id,))
        self.submit(cid,content='next ordinary question')
        job=self.claim()
        serialized=canonical(job['messages'])
        self.assertIn('normal source question',serialized)
        self.assertNotIn('nonce-42',serialized)
        rows=self.client.get('/api/ai/conversations').get_json()['conversations']
        self.assertIn(cid,[row['id'] for row in rows])
        with self.store.db() as db:
            self.assertTrue(db.execute("SELECT 1 FROM messages WHERE job=? AND content LIKE '%nonce-42%'",(probe_id,)).fetchone())

    def test_pure_probe_is_admin_diagnostic_and_cannot_become_normal_chat(self):
        """[Role] Uses durable purpose instead of a title heuristic. [Dependencies] Ordinary list/read/submit guards. [Impact] Empty new chats and mixed conversations remain available."""
        cid=self.conversation()
        jid=self.submit(cid)
        self.finish(self.claim())
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET purpose='probe' WHERE id=?",(jid,))
        self.assertNotIn(cid,[c['id'] for c in self.client.get('/api/ai/conversations').get_json()['conversations']])
        self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages').status_code,409)
        response=self.client.post('/api/ai/conversations/'+cid+'/turns',
            json={'content':'new','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(response.status_code,409)

    def test_trash_restore_and_manual_purge_have_owner_csrf_revision_boundaries(self):
        """[Role] Exercises lifecycle through browser routes, including read-only history. [Dependencies] Signed fixture login and server-owned timestamps. [Impact] Deleted conversations cannot accept new work or leak to another account."""
        cid=self.conversation()
        self.submit(cid,content='retained dialogue')
        self.finish(self.claim(),content='retained answer')
        self.login(3)
        self.assertEqual(self.lifecycle(cid,'trash',0).status_code,404)
        self.login(2)
        missing_csrf=self.client.post('/api/ai/conversations/'+cid+'/trash',json={'lifecycle_revision':0,'operation_id':uuid.uuid4().hex})
        self.assertEqual(missing_csrf.status_code,403)
        key=uuid.uuid4().hex
        response=self.lifecycle(cid,'trash',0,key)
        self.assertEqual(response.status_code,200,response.get_json())
        deleted=response.get_json()['conversation']
        self.assertEqual(deleted['purge_after']-deleted['deleted_at'],30*24*60*60)
        replay=self.lifecycle(cid,'trash',0,key)
        self.assertEqual(replay.status_code,200,replay.get_json())
        self.assertEqual(replay.get_json()['conversation']['deleted_at'],deleted['deleted_at'])
        self.assertNotIn(cid,[c['id'] for c in self.client.get('/api/ai/conversations').get_json()['conversations']])
        trash=self.client.get('/api/ai/conversations?view=trash').get_json()['conversations']
        self.assertIn(cid,[c['id'] for c in trash])
        history=self.client.get('/api/ai/conversations/'+cid+'/messages?view=trash')
        self.assertEqual(history.status_code,200,history.get_json())
        self.assertIn('retained answer',canonical(history.get_json()))
        self.assertNotEqual(self.client.get('/api/ai/conversations/'+cid+'/messages').status_code,200)
        restored=self.lifecycle(cid,'restore',deleted['lifecycle_revision'])
        self.assertEqual(restored.status_code,200,restored.get_json())
        self.assertIsNone(restored.get_json()['conversation']['purge_after'])
        self.assertEqual(self.lifecycle(cid,'trash',0).status_code,409)
        revision=restored.get_json()['conversation']['lifecycle_revision']
        trashed=self.lifecycle(cid,'trash',revision).get_json()['conversation']
        purged=self.lifecycle(cid,'purge',trashed['lifecycle_revision'])
        self.assertEqual(purged.status_code,200,purged.get_json())
        self.assertTrue(purged.get_json()['purged'])
        self.assertEqual(self.client.get('/api/ai/conversations/'+cid+'/messages?view=trash').status_code,404)

    def test_purged_running_job_discards_late_chunks_and_releases_only_on_known_finish(self):
        """[Role] Covers the dangerous API boundary after the job's content rows are gone. [Dependencies] Minimal guard, real worker auth and fake completion. [Impact] Purge cannot cause overlapping requests or resurrect response text."""
        cid=self.conversation()
        jid=self.submit(cid)
        job=self.claim()
        trashed=self.lifecycle(cid,'trash',0)
        self.assertEqual(trashed.status_code,200,trashed.get_json())
        revision=trashed.get_json()['conversation']['lifecycle_revision']
        purged=self.lifecycle(cid,'purge',revision)
        self.assertEqual(purged.status_code,200,purged.get_json())
        other=self.submit(content='wait for own completion')
        self.assertIsNone(self.claim())
        event=self.client.post('/internal/ai/jobs/'+jid+'/event',
            json={'lease':job['lease'],'content':'must never return','content_offset':0},headers=self.worker_headers)
        self.assertEqual(event.status_code,200,event.get_json())
        self.assertTrue(event.get_json()['cancel'])
        self.assertFalse(event.get_json()['accepted'])
        self.finish(job,content='also discarded')
        self.assertEqual(self.claim()['id'],other)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM conversations WHERE id=?',(cid,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages WHERE conversation=?',(cid,)).fetchone()[0],0)

    def test_settings_menu_migration_is_idempotent_and_preserves_custom_metadata(self):
        """[Role] Runs the real install migration against an old menu row twice. [Dependencies] Fresh Flask containers and the synthetic existing business DB. [Impact] Only the verified parent changes; user grants never expose administration."""
        db=self.connect()
        db.execute("UPDATE menus SET ParentMenuCode=NULL,MenuName='Custom admin AI',Description='keep description',SortOrder=88 WHERE MenuCode='equipment_ai_settings'")
        db.commit()
        db.close()
        for i in range(2):
            app=Flask('menu_migration_'+str(i))
            app.config.update(self.app.config)
            install_assistant(app,{'get_db_connection':self.connect,'login_required':lambda f:f,
                'get_maintenance_state':lambda:self.maintenance,'ROADMAP_ATTACHMENT_ROOT':str(self.root/'attachments')})
            db=self.connect()
            row=dict(db.execute("SELECT * FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone())
            self.assertEqual((row['ParentMenuCode'],row['MenuName'],row['Description'],row['SortOrder']),
                             ('admin_center','Custom admin AI','keep description',88))
            if i==0:
                db.execute("UPDATE menus SET UpdatedAt='keep-second-pass' WHERE MenuCode='equipment_ai_settings'")
                db.commit()
            else:
                self.assertEqual(row['UpdatedAt'],'keep-second-pass')
            db.close()
        self.assertFalse(visible_assistant_menus([{'MenuCode':'equipment_ai_settings'}],'user',{'USER_AI_ENABLED':True}))

    def test_purge_between_initial_guard_and_lease_still_acknowledges_event_and_finish(self):
        """[Role] Forces the narrow deletion race at both worker entry points. [Dependencies] Original guard methods and real temporary purge transactions. [Impact] No completion report is stranded behind a vanished job row."""
        for endpoint in ('event','finish'):
            with self.subTest(endpoint=endpoint):
                cid=self.conversation()
                jid=self.submit(cid)
                job=self.claim()
                with self.store.db() as db:
                    account=db.execute('SELECT account_key FROM conversations WHERE id=?',(cid,)).fetchone()[0]
                method='guard_event' if endpoint=='event' else 'guard_finish'
                original=getattr(self.store,method)
                interleaved=[]
                def interleave(*args):
                    """[Role] Purges only after the original live guard check. [Dependencies] One test invocation. [Impact] Deterministic race without sleeps or real models."""
                    result=original(*args)
                    if not interleaved:
                        interleaved.append(True)
                        value=self.store.lifecycle(2,cid,account,'trash',0,uuid.uuid4().hex)
                        self.store.lifecycle(2,cid,account,'purge',value['conversation']['lifecycle_revision'],uuid.uuid4().hex)
                    return result
                payload={'lease':job['lease']}
                if endpoint=='finish':
                    payload.update(outcome='complete',content='discard',calls=[])
                with patch.object(self.store,method,side_effect=interleave):
                    response=self.client.post('/internal/ai/jobs/'+jid+'/'+endpoint,json=payload,headers=self.worker_headers)
                self.assertEqual(response.status_code,200,response.get_json())
                if endpoint=='event':
                    self.assertTrue(response.get_json()['cancel'])
                    self.finish(job)
                with self.store.db() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs WHERE id=?',(jid,)).fetchone()[0],0)
                    self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?',(jid,)).fetchone()[0],'released')

    def test_probe_ack_lookup_is_admin_owner_only_and_read_only(self):
        """[Role] Recovers an acknowledgement without adding queued model work. [Dependencies] Existing opaque client key and actual administrator role check. [Impact] An ordinary session cannot inspect diagnostics or trigger a retry."""
        key=uuid.uuid4().hex
        self.assertEqual(self.client.get('/api/admin/ai/probes?client_key='+key).status_code,403)
        self.login(1)
        response=self.client.get('/api/admin/ai/probes?client_key='+key)
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertFalse(response.get_json()['found'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        cid=self.conversation()
        jid=self.submit(cid,key=key)
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET purpose='probe' WHERE id=?",(jid,))
        found=self.client.get('/api/admin/ai/probes?client_key='+key).get_json()
        self.assertTrue(found['found'])
        self.assertEqual((found['job_id'],found['conversation_id']),(jid,cid))
        db=self.connect()
        db.execute("UPDATE users SET Role='admin' WHERE UserId=3")
        db.commit()
        db.close()
        self.login(3)
        other=self.client.get('/api/admin/ai/probes?client_key='+key)
        self.assertEqual(other.status_code,200,other.get_json())
        self.assertFalse(other.get_json()['found'])

    def test_pre_dispatch_purge_and_preparation_fault_release_only_own_guard(self):
        """Purge after the worker acquires a guard and fails to prepare its frozen provider revision."""
        cid = self.conversation()
        jid = self.submit(cid)
        other_job = uuid.uuid4().hex
        other_group = uuid.uuid4().hex
        with self.store.db(True) as db:
            job = self.store.job(jid, db)
            account = job['account_key']
            route = json.loads(job['route_snapshot'])
            # Another physical group still has an unconfirmed request after its conversation was purged.
            db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?)', (other_group, 'Independent fixture GPU'))
            db.execute("""INSERT INTO ai_execution_guards(job,resource_group,owner,account_key,epoch,state,created,updated)
                VALUES(?,?,?,?,?,'recovery_required',?,?)""",
                       (other_job, other_group, job['owner'], account, self.store.epoch, job['created'], job['created']))

        registry = self.app.extensions['equipment_assistant']['registry']
        guard_after_purge = []

        def fail_after_purge(provider_id, revision):
            moved = self.store.lifecycle(2, cid, account, 'trash', 0, uuid.uuid4().hex)
            self.store.lifecycle(2, cid, account, 'purge', moved['conversation']['lifecycle_revision'], uuid.uuid4().hex)
            with self.store.db() as db:
                guard_after_purge.extend(row[0] for row in db.execute(
                    'SELECT state FROM ai_execution_guards WHERE job=?', (jid,)))
            raise ValueError('synthetic preparation failure after purge')

        with patch.object(registry, 'connection', autospec=True, side_effect=fail_after_purge) as prepare_connection:
            self.assertIsNone(self.claim())
        prepare_connection.assert_called_once_with(route['provider_id'], route['revision'])
        self.assertEqual(guard_after_purge, ['draining'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs WHERE id=?', (jid,)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid,)).fetchone()[0], 'released')
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (other_job,)).fetchone()[0], 'recovery_required')

    def test_trash_after_first_tool_stops_remaining_model_tool_calls(self):
        """[Role] Moves a conversation between two validated tool calls. [Dependencies] Real domain query and lifecycle writer. [Impact] No subsequent read/tool is admitted after deletion takes effect."""
        cid=self.conversation()
        self.submit(cid)
        job=self.claim()
        with self.store.db() as db:
            account=db.execute('SELECT account_key FROM conversations WHERE id=?',(cid,)).fetchone()[0]
        original=self.domain.read_or_prepare
        invoked=[]
        def read_then_trash(*args):
            """[Role] Deletes after one legitimate read. [Dependencies] Synthetic user/DB. [Impact] Deterministic cancellation boundary."""
            invoked.append(True)
            result=original(*args)
            self.store.lifecycle(2,cid,account,'trash',0,uuid.uuid4().hex)
            return result
        calls=[{'id':'read-'+str(i),'name':'search_equipment','arguments':canonical({'scope':'my'})} for i in range(2)]
        with patch.object(self.domain,'read_or_prepare',side_effect=read_then_trash):
            result=self.finish(job,calls)
        self.assertEqual(len(invoked),1)
        self.assertEqual(result['state'],'cancelled')

    def test_maintenance_accepts_detached_cleanup_without_business_database_access(self):
        """[Role] Reports a purged request's known completion during RESTORING. [Dependencies] Real maintenance exception and guard lease. [Impact] Cleanup never opens business data or strands the slot."""
        cid=self.conversation()
        jid=self.submit(cid)
        job=self.claim()
        moved=self.lifecycle(cid,'trash',0).get_json()['conversation']
        self.assertEqual(self.lifecycle(cid,'purge',moved['lifecycle_revision']).status_code,200)
        self.maintenance.update(state='RESTORING')
        before=self.equipment_connections
        event=self.client.post('/internal/ai/jobs/'+jid+'/event',json={'lease':job['lease']},headers=self.worker_headers)
        self.assertEqual(event.status_code,200,event.get_json())
        self.assertTrue(event.get_json()['cancel'])
        self.finish(job)
        self.assertEqual(self.equipment_connections,before)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?',(jid,)).fetchone()[0],'released')

    def test_revoked_probe_admin_cannot_read_diagnostics_or_verify_model(self):
        """[Role] Revokes role/menu after claim. [Dependencies] Real probe queue and worker finish. [Impact] A past admin session cannot publish capability results or read diagnostics."""
        registry=self.app.extensions['equipment_assistant']['registry']
        for revoke in ('role','grant'):
            with self.subTest(revoke=revoke):
                db=self.connect()
                db.execute("UPDATE users SET Role='admin' WHERE UserId=1")
                db.execute("UPDATE role_menu_permissions SET IsAllowed=1 WHERE Role='admin' AND MenuCode='equipment_ai_settings'")
                db.commit()
                db.close()
                self.login(1)
                mid=registry.choices()['default_model']
                response=self.client.post('/api/admin/ai/models/'+mid+'/probe',json={'tools':False,'reasoning':False,'client_key':uuid.uuid4().hex},headers=self.headers)
                self.assertEqual(response.status_code,202,response.get_json())
                job=self.claim()
                with self.store.db() as db:
                    before=tuple(db.execute('SELECT profile,verified_revision,profile_revision FROM ai_provider_models WHERE id=?',(mid,)).fetchone())
                db=self.connect()
                if revoke=='role':
                    db.execute("UPDATE users SET Role='user' WHERE UserId=1")
                else:
                    db.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE Role='admin' AND MenuCode='equipment_ai_settings'")
                db.commit()
                db.close()
                self.assertEqual(self.client.get('/api/ai/jobs/'+job['id']).status_code,403)
                result=self.finish(job,content=job['route']['probe_nonce'])
                self.assertIn(result['state'],('failed','cancelled'))
                with self.store.db() as db:
                    self.assertEqual(tuple(db.execute('SELECT profile,verified_revision,profile_revision FROM ai_provider_models WHERE id=?',(mid,)).fetchone()),before)

    def test_probe_final_writer_rechecks_role_after_context_validation(self):
        """[Role] Revokes an admin at the last profile-normalization boundary. [Dependencies] Actual final writer. [Impact] Earlier authorization cannot outlive a current revocation."""
        from utils.ai_assistant.reasoning import normalize_profile
        self.login(1)
        registry=self.app.extensions['equipment_assistant']['registry']
        mid=registry.choices()['default_model']
        response=self.client.post('/api/admin/ai/models/'+mid+'/probe',json={'tools':False,'reasoning':False,'client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(response.status_code,202,response.get_json())
        job=self.claim()
        with self.store.db() as db:
            before=tuple(db.execute('SELECT profile,verified_revision,profile_revision FROM ai_provider_models WHERE id=?',(mid,)).fetchone())
        def revoke_after_validation(*args,**kwargs):
            """[Role] Forces revocation just before the writer. [Dependencies] Temporary role row. [Impact] Deterministic final-boundary test."""
            result=normalize_profile(*args,**kwargs)
            db=self.connect()
            db.execute("UPDATE users SET Role='user' WHERE UserId=1")
            db.commit()
            db.close()
            return result
        with patch('utils.ai_assistant.normalize_profile',side_effect=revoke_after_validation):
            result=self.finish(job,content=job['route']['probe_nonce'])
        self.assertEqual(result['state'],'failed')
        with self.store.db() as db:
            self.assertEqual(tuple(db.execute('SELECT profile,verified_revision,profile_revision FROM ai_provider_models WHERE id=?',(mid,)).fetchone()),before)


if __name__ == '__main__':
    unittest.main()
