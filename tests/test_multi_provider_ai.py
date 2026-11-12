"""[MINI-COMMENT: ASSISTANT.PROVIDER.FIXTURES]
[EN rev.3]
[Role] Exercises registry and queue boundaries through verified HTTPS candidates on synthetic Linux fixtures.
[Dependencies] Existing source-derived Flask fixture, loopback fake model servers and temporary keys/DBs.
[Impact] No real provider, equipment DB or production credential is used.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import io
import json
import os
import re
import socket
import sqlite3
import ssl
from types import SimpleNamespace
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from assistant_fixture_tests import AssistantTests
from utils.ai_assistant import install_assistant
from utils.ai_assistant.audit import audit_body, preserve_export
from utils.ai_assistant.context import build_context
from utils.ai_assistant.policy import AssistantError, canonical
from utils.ai_assistant.providers import LEGACY_MODEL, LEGACY_GROUP, PROTOCOL, Registry
from utils.ai_assistant.store import Store
from utils.ai_assistant.transport import EndpointPolicy, model_request
from utils.ai_assistant.worker import Worker


def fixture_certificate(case, address):
    """Make a new short-lived CA and an IP-SAN leaf in this case's disposable directory."""
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'fixture CA '+uuid.uuid4().hex)])
    template = (x509.CertificateBuilder().issuer_name(issuer).not_valid_before(now-timedelta(days=1))
                .not_valid_after(now+timedelta(days=2)))
    ca = (template.subject_name(issuer).public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .add_extension(x509.BasicConstraints(ca=True,path_length=0),True)
          .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),False)
          .sign(ca_key,hashes.SHA256()))
    leaf = (template.subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'fixture GPU')]))
            .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address))]),False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False)
            .sign(ca_key,hashes.SHA256()))
    stem = uuid.uuid4().hex
    cert_path, key_path = case.root/(stem+'.pem'), case.root/(stem+'.key')
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path,key_path)
    return context,ca.public_bytes(serialization.Encoding.PEM).decode('ascii')


def loopback_socket(case, address, port):
    """Map only provisioned, already-validated IP/port pairs onto local listening sockets."""
    if not hasattr(case,'fixture_sockets'):
        case.fixture_sockets = {}
        original = socket.create_connection
        def connect(peer, *args, **kwargs):
            if peer in case.fixture_sockets:
                peer = case.fixture_sockets[peer]
            elif not ipaddress.ip_address(peer[0]).is_loopback:
                raise AssertionError('Unregistered fixture destination')
            return original(peer,*args,**kwargs)
        case.enterContext(patch('socket.create_connection',connect))
    case.fixture_sockets[(address,port)] = ('127.0.0.1',port)


@contextmanager
def fake_provider(case=None, *, models=None, reject=False, address='192.168.0.51'):
    """A loopback HTTP fixture for direct transport tests, or an enrolled HTTPS model PC."""
    peer = SimpleNamespace(calls=[],models=models if models is not None else [
        {'id':'fixture-chat'},{'id':'fixture-embedding','type':'embedding'}],
        reject=reject,barrier=None,keys=set(),ca_pem=None)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def authorized(self):
            if peer.keys and self.headers.get('Authorization') not in {'Bearer '+key for key in peer.keys}:
                self.send_response(401)
                self.end_headers()
                return False
            return True

        def do_GET(self):
            peer.calls.append({'method':'GET','path':self.path,'authorization':self.headers.get('Authorization')})
            if not self.authorized():
                return
            self.send_response(302 if peer.reject else 200)
            self.send_header('Content-Type','application/json')
            if peer.reject:
                self.send_header('Location','http://169.254.169.254/latest/meta-data/')
            self.end_headers()
            self.wfile.write(canonical({'data':peer.models}).encode())

        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            peer.calls.append({'method':'POST','path':self.path,'payload':payload,'authorization':self.headers.get('Authorization')})
            if not self.authorized():
                return
            if peer.barrier:
                peer.barrier.wait(timeout=5)
            content=payload['messages'][-1]['content']
            nonce=(re.findall(r'[0-9a-f]{32}',content) or ['fake-answer'])[-1]
            delta={'content':nonce}
            if payload.get('tools') and payload['tools'][0]['function']['name']=='assistant_probe':
                delta={'tool_calls':[{'index':0,'id':'probe-call','function':{'name':'assistant_probe','arguments':canonical({'nonce':nonce})}}]}
            if payload.get('reasoning_effort') in ('low','medium','high','xhigh','max'):
                delta['reasoning_content']='Synthetic reasoning output.'
            self.send_response(200)
            self.send_header('content-type','text/event-stream')
            self.end_headers()
            frame={'choices':[{'delta':delta,'finish_reason':'tool_calls' if delta.get('tool_calls') else 'stop'}]}
            self.wfile.write(('data: '+canonical(frame)+'\n\ndata: [DONE]\n\n').encode())

    with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        peer.base_url = 'http://127.0.0.1:'+str(server.server_port)
        if case is not None:
            context,peer.ca_pem = fixture_certificate(case,address)
            server.socket = context.wrap_socket(server.socket,server_side=True)
            loopback_socket(case,address,server.server_port)
            peer.base_url = 'https://'+address+':'+str(server.server_port)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        thread.start()
        try:
            yield peer
        finally:
            server.shutdown()
            thread.join(timeout=2)
            if case is not None:
                del case.fixture_sockets[(address,server.server_port)]


def admin_post(case, path, data, status=200):
    response = case.client.post(path,json=data,headers=case.headers)
    case.assertEqual(response.status_code,status,response.get_json())
    return response.get_json()


def queue_candidate(case, pid, mid, revision, *, tools, reasoning=False):
    return admin_post(case,'/api/admin/ai/models/'+mid+'/probe',dict(
        provider_id=pid,candidate_revision=revision,context_tokens=65536,client_key=uuid.uuid4().hex,
        tools=tools,reasoning=reasoning),202)['job_id']


def publish_model(case, pid, mid, revision=1):
    admin_post(case,'/api/admin/ai/providers/'+pid+'/models',dict(
        id=mid,label='Fixture model',published=True,sort_order=0,context_tokens=65536,revision=revision))


@unittest.skipUnless(os.name=='posix','Linux-only isolated behavior fixtures')
class ProviderTests(unittest.TestCase):
    setUp=AssistantTests.setUp
    connect=AssistantTests.connect
    login=AssistantTests.login
    conversation=AssistantTests.conversation
    submit=AssistantTests.submit
    claim=AssistantTests.claim
    finish=AssistantTests.finish
    prepare=AssistantTests.prepare
    count=AssistantTests.count

    @property
    def registry(self):
        """[Role] Implements registry within this module's fixed boundary.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        return self.app.extensions['equipment_assistant']['registry']

    def add_model(self, peer=None, group=None, verified=True, tools=True, adapter='openai', upstream='fixture-chat', manual=True):
        """Register/discover a real TLS candidate. Leave it private when the test owns the probe."""
        if peer is None:
            peer=self.enterContext(fake_provider(self,models=[{'id':upstream}]))
        if not self.app.config.get('USER_AI_PROVIDER_ENCRYPTION_KEY'):
            self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']=Fernet.generate_key().decode()
        key='synthetic-model-key-'+uuid.uuid4().hex
        peer.keys.add(key)
        with self.client.session_transaction() as session:
            previous_user=session['user']['UserId']
        self.login(1)
        try:
            data=dict(name='Fixture '+uuid.uuid4().hex[:6],base_url=peer.base_url,adapter=adapter,enabled=True,
                      manual=manual,revision=0,api_key=key,resource_group=group or LEGACY_GROUP,
                      trust_mode='private',ca_pem=peer.ca_pem)
            pid=admin_post(self,'/api/admin/ai/providers',data,201)['id']
            registry=admin_post(self,'/api/admin/ai/providers/'+pid+'/discover',{'candidate_revision':1})
            candidate=next(p for p in registry['providers'] if p['id']==pid)['candidate']
            mid=next(m['id'] for m in candidate['models'] if m['upstream']==upstream)
            self.assertNotIn(mid,[m['id'] for m in self.registry.choices()['models']])
            if verified:
                jid=queue_candidate(self,pid,mid,1,tools=tools)
                for _ in range(2 if tools else 1):
                    job=self.claim()
                    self.assertIsNotNone(job)
                    self.assertEqual(job['id'],jid)
                    ProviderTests.run_one(self,job)
                with self.store.db() as db:
                    self.assertEqual(self.store.job(jid,db)['state'],'done')
                publish_model(self,pid,mid)
                self.assertEqual(self.registry.resolve(mid)['profile']['tools'],tools)
            return pid,mid,key
        finally:
            self.login(previous_user)

    def choose(self, cid, mid, level='default', revision=None):
        """[Role] Implements choose within this module's fixed boundary.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with self.store.db() as db:
            conv=db.execute('SELECT selection_revision FROM conversations WHERE id=?',(cid,)).fetchone()
        return self.client.post('/api/ai/conversations/'+cid+'/selection',json={'selection_id':mid,'reasoning_version':2,'level':level,'revision':conv[0] if revision is None else revision},headers=self.headers)

    def run_one(self, job):
        """[Role] Implements run one within this module's fixed boundary.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        worker=Worker('http://127.0.0.1:5000',self.app.config['USER_AI_WORKER_TOKEN'],self.app.config['USER_AI_STRATA_URL'],'legacy-key','unused-model')
        def post(path,data):
            """[Role] Implements post within this module's fixed boundary.
            [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
            [Impact] Detects regressions without production data changes or real model calls.
            """
            response=self.app.test_client().post(path,json=data,headers=self.worker_headers)
            self.assertEqual(response.status_code,200,response.get_json())
            return response.get_json()
        worker.post=post
        worker.run_job(job)

    def test_admin_role_menu_csrf_and_write_only_encrypted_secret(self):
        """[Role] Verifies admin role menu csrf and write only encrypted secret on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        self.assertEqual(self.client.get('/api/admin/ai/providers').status_code,403)
        with self.client.session_transaction() as session:
            session['user']['Role']='admin'
        self.assertEqual(self.client.get('/api/admin/ai/providers').status_code,403)
        self.login(1)
        self.assertEqual(self.client.get('/admin/ai/providers').status_code,200)
        self.assertEqual(self.client.post('/api/admin/ai/providers',json={}).status_code,403)
        _,mid,key=self.add_model()
        response=self.client.get('/api/admin/ai/providers')
        self.assertNotIn(key,response.get_data(as_text=True))
        self.assertNotIn('fernet:',response.get_data(as_text=True))
        with self.store.db() as db:
            credential=db.execute('SELECT credential FROM ai_provider_revisions WHERE provider=(SELECT provider FROM ai_provider_models WHERE id=?)',(mid,)).fetchone()[0]
        self.assertTrue(credential.startswith('fernet:'))
        self.assertNotIn(key,credential)
        self.assertEqual(self.registry.secret(credential),key)
        self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']=Fernet.generate_key().decode()
        with self.assertRaises(AssistantError):
            self.registry.secret(credential)

    def test_admin_mutation_audit_protects_new_key_keeps_business(self):
        """[Role] Verifies admin mutation audit protects new key keeps business on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        self.login(1)
        self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']=Fernet.generate_key().decode()
        peer=self.enterContext(fake_provider(self))
        key='synthetic-audited-model-key-123456789'
        response=self.client.post('/api/admin/ai/providers',json={'name':'Audited office AI','base_url':peer.base_url,'adapter':'openai','enabled':True,'manual':False,'revision':0,'resource_group':LEGACY_GROUP,'api_key':key,'trust_mode':'private','ca_pem':peer.ca_pem},headers=self.headers)
        self.assertEqual(response.status_code,201,response.get_json())
        record=self.audit_logs[-1]
        self.assertEqual((record['StatusCode'], record['RequestPayload'], record['ResponsePayload']), (201, None, None))
        self.assertNotIn(key, canonical(record))
        self.assertIn('Audited office AI', canonical(self.registry.admin_list()))

    def test_endpoint_allowlist_url_paths_dns_rebinding_and_ports(self):
        """[Role] Verifies endpoint allowlist url paths dns rebinding and ports on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        policy=EndpointPolicy(['http://127.0.0.1:18999',{'host':'192.168.0.0/24','port':8080,'scheme':'https'},{'host':'192.168.0.0/24','port':8080,'scheme':'http'}])
        self.assertEqual(policy.destination('https://192.168.0.7:8080/v1')[1],'192.168.0.7')
        with self.assertRaises(AssistantError):
            policy.destination('http://192.168.0.7:8080/v1')
        for url in ('http://127.0.0.1:19000','http://169.254.169.254:8080','http://192.168.0.7:80','http://user:pass@192.168.0.7:8080','http://192.168.0.7:8080/load','http://192.168.0.7:8080/v1?x=1','http://192.168.0.7:8080/#x','http://192.168.0.7:8080/\n'):
            with self.subTest(url=url),self.assertRaises(AssistantError):
                policy.destination(url)
            secure_url=url.replace('http://','https://',1)
            with self.subTest(url=secure_url),self.assertRaises(AssistantError):
                policy.destination(secure_url)
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('192.168.0.10',8080))]):
            dns=EndpointPolicy(['https://approved.example:8080'])
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',8080))]),self.assertRaises(AssistantError):
            dns.destination('https://approved.example:8080')

    def test_real_pinned_models_transport_ignores_proxy_and_rejects_redirect(self):
        """[Role] Verifies real pinned models transport ignores proxy and rejects redirect on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with fake_provider() as peer,patch.dict(os.environ,{'HTTP_PROXY':'http://127.0.0.1:1','HTTPS_PROXY':'http://127.0.0.1:1'}):
            policy=EndpointPolicy([peer.base_url])
            with model_request(policy,peer.base_url+'/v1','/models','synthetic-key') as response:
                self.assertEqual(response.status_code,200)
                self.assertEqual(len(response.json()['data']),2)
            self.assertEqual(peer.calls[0]['path'],'/v1/models')
        with fake_provider(reject=True) as peer:
            with model_request(EndpointPolicy([peer.base_url]),peer.base_url,'/models') as response:
                with self.assertRaises(AssistantError):
                    response.raise_for_status()
            self.assertEqual(len(peer.calls),1)

    def test_discovery_default_auto_manual_opt_in_and_embedding_exclusion(self):
        """[Role] Verifies discovery default auto manual opt in and embedding exclusion on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with fake_provider(self) as peer:
            pid,mid,_=self.add_model(peer,manual=False,tools=False)
            with self.store.db() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_provider_models WHERE provider=?',(pid,)).fetchone()[0],1)
            with self.assertRaises(AssistantError):
                self.registry.update_model(pid,{'upstream':'manual-id','label':'Manual','published':True,'sort_order':0,'context_tokens':4096,'revision':1})
            self.registry.discover(pid)
            self.assertEqual([call['method'] for call in peer.calls],['GET','POST'])
            # Change a tested limit through the normal API so this published model really needs a new probe.
            self.registry.update_model(pid,{'id':mid,'label':'Fixture model','published':True,'sort_order':0,'context_tokens':32768,'revision':1})
            self.assertEqual(self.registry.choices()['default_model'],LEGACY_MODEL)
            self.assertFalse(next(m for m in self.registry.choices()['models'] if m['id']==mid)['available'])

    def test_failed_discovery_keeps_inventory_and_blocks_saved_selection(self):
        """[Role] Verifies failed discovery keeps inventory and blocks saved selection on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with fake_provider(self) as peer:
            pid,mid,_=self.add_model(peer,manual=False)
            cid=self.conversation()
            self.assertEqual(self.choose(cid,mid).status_code,200)
            peer.reject=True
            with self.assertRaises(AssistantError):
                self.registry.discover(pid,True)
            value=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Still here','reasoning_version':2,'level':'default','client_key':uuid.uuid4().hex},headers=self.headers)
            self.assertEqual(value.status_code,503)
            with self.store.db() as db:
                self.assertEqual(db.execute('SELECT selection_id FROM conversations WHERE id=?',(cid,)).fetchone()[0],mid)

    def test_same_session_switch_restores_selection_and_frozen_turn_source(self):
        """[Role] Verifies same session switch restores selection and frozen turn source on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        jid=self.submit(cid,level='medium')
        self.assertEqual(self.choose(cid,mid).status_code,200)
        job=self.claim()
        self.assertEqual(job['route']['selection_id'],LEGACY_MODEL)
        self.finish(job)
        page=self.client.get('/api/ai/conversations/'+cid+'/messages').get_json()
        self.assertEqual(page['conversation']['selection_id'],mid)
        self.assertEqual(page['conversation']['next_level'],'default')
        self.assertEqual(page['jobs'][0]['source']['model_label'],'Qwen3.8 Flash Next')
        self.submit(cid,level='default')
        next_job=self.claim()
        self.assertEqual(next_job['route']['selection_id'],mid)
        self.assertNotIn('추론 출력',canonical(next_job['messages']))

    def test_selection_owner_revision_unsupported_level_and_idempotency(self):
        """[Role] Verifies selection owner revision unsupported level and idempotency on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        self.assertEqual(self.choose(cid,mid,revision=0).status_code,409)
        self.assertEqual(self.choose(cid,mid,level='high').status_code,409)
        self.assertEqual(self.choose(cid,mid).status_code,200)
        key=uuid.uuid4().hex
        self.submit(cid,level='default',key=key)
        self.assertEqual(self.choose(cid,LEGACY_MODEL,level='medium').status_code,200)
        response=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Help','reasoning_version':2,'level':'default','client_key':key},headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.login(3)
        response=self.client.post('/api/ai/conversations/'+cid+'/selection',json={'selection_id':mid,'reasoning_version':2,'level':'default','revision':2},headers=self.headers)
        self.assertEqual(response.status_code,404)

    def test_revision_keeps_queued_credentials_and_history_immutable(self):
        """[Role] Verifies revision keeps queued credentials and history immutable on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        peer=self.enterContext(fake_provider(self))
        pid,mid,old_key=self.add_model(peer,tools=False)
        self.login(1)
        new_key='synthetic-new-key-123456789'
        peer.keys.add(new_key)  # Both keys remain valid upstream during its rotation window.
        admin_post(self,'/api/admin/ai/providers/'+pid,dict(name='Renamed provider',base_url=peer.base_url,
                   adapter='openai',resource_group=LEGACY_GROUP,enabled=True,manual=True,revision=1,api_key=new_key))
        self.assertEqual(self.registry.resolve(mid)['revision'],1)
        admin_post(self,'/api/admin/ai/models/'+mid+'/probe',dict(provider_id=pid,candidate_revision=2,
                   tools=False,reasoning=False,client_key=uuid.uuid4().hex),409)
        admin_post(self,'/api/admin/ai/providers/'+pid+'/discover',{'candidate_revision':2})
        probe_id=queue_candidate(self,pid,mid,2,tools=False)
        probe=self.claim()
        self.assertEqual(probe['id'],probe_id)
        self.login(2)
        cid=self.conversation()
        self.assertEqual(self.choose(cid,mid).status_code,200)
        jid=self.submit(cid,level='default')
        with self.store.db() as db:
            accepted=self.store.job(jid,db)['route_snapshot']
        self.run_one(probe)
        self.assertEqual(self.registry.resolve(mid)['revision'],2)
        self.assertEqual(peer.calls[-1]['authorization'],'Bearer '+new_key)
        job=self.claim()
        self.assertEqual((job['id'],job['route']['revision'],job['route']['api_key']),(jid,1,old_key))
        self.assertNotEqual(job['route']['provider_name'],'Renamed provider')
        self.run_one(job)
        self.assertEqual(peer.calls[-1]['authorization'],'Bearer '+old_key)
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual((row['state'],row['route_snapshot']),('done',accepted))

    def test_group_slots_allow_independent_pcs_and_hold_unknown_only_own_group(self):
        """[Role] Verifies group slots allow independent pcs and hold unknown only own group on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with self.store.db(True) as db:
            group=uuid.uuid4().hex
            db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?)',(group,'Independent PC'))
        _,mid,_=self.add_model(group=group)
        first=self.submit()
        a=self.claim()
        second_cid=self.conversation()
        self.choose(second_cid,mid)
        second=self.submit(second_cid,level='default')
        b=self.claim()
        self.assertEqual((a['id'],b['id']),(first,second))
        self.finish(a,outcome='recovery_required')
        self.finish(b)
        self.submit(second_cid,level='default')
        self.assertIsNotNone(self.claim())
        with self.store.db() as db:
            self.assertEqual(self.store.job(first,db)['state'],'recovery_required')

    def test_same_group_two_providers_are_serial_and_account_quota_aggregates(self):
        """[Role] Verifies same group two providers are serial and account quota aggregates on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        self.submit()
        a=self.claim()
        cid=self.conversation()
        self.choose(cid,mid)
        self.submit(cid,level='default')
        self.assertIsNone(self.claim())
        response=self.client.post('/api/ai/conversations/'+self.conversation()+'/turns',json={'content':'third','reasoning_version':2,'level':'medium','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(response.status_code,429)
        self.finish(a)
        self.assertIsNotNone(self.claim())

    def test_protocol_mismatch_does_not_claim_and_preparation_fault_releases(self):
        """[Role] Verifies protocol mismatch does not claim and preparation fault releases on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        jid=self.submit()
        for obsolete in sorted({2,PROTOCOL-1}):
            response=self.client.post('/internal/ai/claim',json={'worker':'old','protocol':obsolete},headers=self.worker_headers)
            self.assertEqual(response.status_code,409)
            with self.store.db() as db:
                self.assertEqual(self.store.job(jid,db)['state'],'queued')
        with patch.object(self.domain,'tools',side_effect=sqlite3.OperationalError('synthetic fault')):
            self.assertIsNone(self.claim())
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual((row['state'],row['error_code'],row['reserved_chars']),('failed','PROCESSING_FAILED',0))
        self.submit()
        self.assertIsNotNone(self.claim())

    def test_decryption_fault_before_dispatch_releases_group(self):
        """[Role] Verifies decryption fault before dispatch releases group on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        self.choose(cid,mid)
        jid=self.submit(cid,level='default')
        self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']='broken-key'
        self.assertIsNone(self.claim())
        with self.store.db() as db:
            self.assertEqual(self.store.job(jid,db)['state'],'failed')

    def test_maintenance_full_global_gate_cleanup_does_not_open_equipment_db(self):
        """[Role] Verifies maintenance full global gate cleanup does not open equipment db on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        jid=self.submit()
        job=self.claim()
        for state in ('DRAINING','RESTORING','RECOVERY'):
            self.maintenance={'state':state}
            response=self.app.test_client().post('/internal/ai/claim',json={'worker':'fixture','protocol':PROTOCOL},headers=self.worker_headers)
            self.assertEqual(response.status_code,503)
            with patch.object(self.domain,'connect',side_effect=AssertionError('equipment must not be opened')):
                before=self.equipment_connections
                response=self.app.test_client().post('/internal/ai/jobs/'+jid+'/event',json={'lease':job['lease']},headers=self.worker_headers)
                self.assertEqual(response.status_code,200,response.get_json())
                self.assertTrue(response.get_json()['cancel'])
                self.assertEqual(self.equipment_connections,before)
            bad=self.app.test_client().post('/internal/ai/jobs/'+jid+'/event',json={'lease':'bad'},headers=self.worker_headers)
            self.assertEqual(bad.status_code,503)
        response=self.app.test_client().post('/internal/ai/jobs/'+jid+'/finish',json={'lease':job['lease'],'outcome':'complete','content':'Finished'},headers=self.worker_headers)
        self.assertEqual(response.get_json()['state'],'failed')
        with self.store.db() as db:
            self.assertIn('점검',self.store.job(jid,db)['error'])

    def test_first_error_cause_and_rejected_chunk_ack_are_preserved(self):
        """[Role] Verifies first error cause and rejected chunk ack are preserved on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        jid=self.submit()
        job=self.claim()
        self.store.cancel(2,jid,error='Original cause',error_code='PROCESSING_FAILED')
        result=self.client.post('/internal/ai/jobs/'+jid+'/event',json={'lease':job['lease'],'content':'bad','content_offset':99},headers=self.worker_headers).get_json()
        self.assertFalse(result['accepted'])
        self.assertEqual(result['content_offset'],0)
        self.assertTrue(result['cancel'])
        self.finish(job,content='',outcome='failed')
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual((row['state'],row['error'],row['error_code']),('failed','Original cause','PROCESSING_FAILED'))

    def test_chat_only_model_cannot_call_equipment_tools(self):
        """[Role] Verifies chat only model cannot call equipment tools on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model(tools=False)
        cid=self.conversation()
        self.choose(cid,mid)
        self.submit(cid,level='default')
        job=self.claim()
        self.assertEqual(job['tools'],[])
        result=self.finish(job,[{'id':'evil','name':'prepare_equipment_create','arguments':canonical({'name':'No','option_id':1})}])
        self.assertEqual(result['state'],'failed')
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],0)

    def test_normalized_draft_survives_model_switch_with_sources_budget_and_no_reasoning(self):
        """[Role] Verifies normalized draft survives model switch with sources budget and no reasoning on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        self.submit(cid,content='My serial is TEST 42. Help create a new device.')
        job=self.claim()
        self.finish(job,[{'id':'draft','name':'save_equipment_draft','arguments':canonical({'operation':'create','fields':{'serial_number':'  TEST 42  '},'revision':0})}],reasoning='PRIVATE HIDDEN REASONING')
        follow=self.claim()
        self.finish(follow)
        self.choose(cid,mid)
        self.submit(cid,content='Continue the same task',level='default')
        switched=self.claim()
        serialized=canonical(switched['messages'])
        self.assertIn('UNCONFIRMED_DRAFT',serialized)
        self.assertIn('TEST 42',serialized)
        self.assertIn('source_message',serialized)
        self.assertNotIn('PRIVATE HIDDEN REASONING',serialized)
        with self.store.db() as db:
            used=db.execute('SELECT used_chars FROM storage_accounts WHERE owner=2').fetchone()[0]
            real=db.execute("SELECT SUM(length(content)+length(reasoning)) FROM messages m JOIN conversations c ON c.id=m.conversation WHERE c.owner=2").fetchone()[0]
            draft=db.execute('SELECT length(data) FROM ai_task_drafts WHERE conversation=?',(cid,)).fetchone()[0]
            handoff=db.execute('SELECT COALESCE(SUM(handoff_chars),0) FROM jobs').fetchone()[0]
            self.assertEqual(used,real+draft+handoff)

    def test_small_context_refuses_question_without_destroying_original(self):
        """[Role] Verifies small context refuses question without destroying original on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model(tools=False)
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET context_tokens=2048 WHERE id=?',(mid,))
        cid=self.conversation()
        self.choose(cid,mid)
        jid=self.submit(cid,content='한글'*2000,level='default')
        self.assertIsNone(self.claim())
        page=self.client.get('/api/ai/conversations/'+cid+'/messages').get_json()
        self.assertEqual(page['jobs'][0]['state'],'failed')
        self.assertEqual(page['messages'][0]['content'],'한글'*2000)

    def test_real_adapter_capability_probe_then_user_turn_openai_excludes_strata_flag(self):
        """[Role] Verifies real adapter capability probe then user turn openai excludes strata flag on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        with fake_provider(self) as peer:
            pid,mid,_=self.add_model(peer,verified=False)
            self.login(1)
            queue_candidate(self,pid,mid,1,tools=True)
            for _ in range(2):
                job=self.claim()
                self.run_one(job)
            publish_model(self,pid,mid)
            self.assertTrue(self.registry.resolve(mid)['profile']['tools'])
            self.login(2)
            cid=self.conversation()
            self.choose(cid,mid)
            self.submit(cid,level='default')
            self.run_one(self.claim())
            self.assertEqual(len([c for c in peer.calls if c['method']=='POST']),3)
            self.assertNotIn('strata_mcp',peer.calls[-1]['payload'])
            self.assertNotIn('reasoning_effort',peer.calls[-1]['payload'])

    def test_real_strata_probe_verifies_four_preset_reasoning_outputs(self):
        """[Role] Verifies Strata preset efforts through the real worker/loopback transport on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        model='qwen3.8-flash-next-iq3_xxs'
        with fake_provider(self,models=[{'id':model}]) as peer:
            pid,mid,_=self.add_model(peer,verified=False,adapter='strata',upstream=model)
            self.login(1)
            queue_candidate(self,pid,mid,1,tools=True,reasoning=True)
            for _ in range(6):
                self.run_one(self.claim())
            publish_model(self,pid,mid)
            route=self.registry.resolve(mid)
            self.assertEqual(route['profile']['levels'],['off','low','medium','xhigh'])
            self.assertEqual([c['method'] for c in peer.calls],['GET']+['POST']*6)
            self.assertTrue(all(c['payload']['strata_mcp'] is False for c in peer.calls if c['method']=='POST'))

    def test_retire_keeps_history_and_rejects_stale_reactivation(self):
        """[Role] Verifies retire keeps history and rejects stale reactivation on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        pid,mid,_=self.add_model()
        current=next(p for p in self.registry.admin_list()['providers'] if p['id']==pid)
        self.registry.save({'name':current['name'],'base_url':current['base_url'],'adapter':'openai','enabled':False,'retired':True,'manual':True,'resource_group':LEGACY_GROUP,'revision':1},pid)
        self.assertEqual(len(self.registry.admin_list()['providers']),2)
        with self.assertRaises(AssistantError):
            self.registry.resolve(mid)
        with self.assertRaises(AssistantError):
            self.registry.save({'name':'No resurrection','base_url':current['base_url'],'adapter':'openai','enabled':True,'manual':True,'resource_group':LEGACY_GROUP,'revision':2},pid)

    def test_binary_rejection_is_logged_without_consuming_wire_and_csv_artifact_budget(self):
        """[Role] Verifies binary rejection is logged without consuming wire and csv artifact budget on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        response=self.client.post('/api/ai/equipment/3/files',data={'file':(io.BytesIO(b'\x00\xffbinary'),'bad.pdf')},headers=self.headers)
        self.assertEqual(response.status_code,404)
        record=self.audit_logs[-1]
        self.assertEqual(record['StatusCode'], 404)
        self.assertEqual((record['RequestPayload'],record['ResponsePayload']), (None, None))
        response=self.client.get('/api/ai/csv/export?scope=my')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(self.audit_logs[-1]['ResponsePayload'])
        self.assertNotIn('SERIAL-2',canonical(self.audit_logs))
        self.assertEqual(len(list((self.root/'audit').glob('*.csv'))),1)
        self.app.config['USER_AI_AUDIT_MAX_BYTES']=1048576
        response=self.client.get('/api/ai/csv/export?scope=my')
        self.assertEqual(response.status_code,200)
        with self.store.db(True) as db:
            ids=db.execute('SELECT id,blob_id FROM ai_audit_artifacts').fetchall()
            self.assertEqual(len(ids),2)
            self.assertNotEqual(ids[0][0],ids[1][0])
            self.assertEqual(ids[0][1],ids[1][1])
            self.assertEqual(len(list((self.root/'audit').glob('*.csv'))),1)
            db.execute("INSERT INTO ai_audit_artifacts(id,sha256,bytes,owner,scope,row_count,created) VALUES('reserved','other',1048576,1,'my',1,0)")
        response=self.client.get('/api/ai/csv/export?scope=public')
        self.assertEqual(response.status_code,507)
        self.assertIn('감사',response.get_json()['message'])

    def test_v2_migration_keeps_unknown_locks_and_never_invents_old_answer_provenance(self):
        """[Role] Verifies v2 migration keeps unknown locks and never invents old answer provenance on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        cid=self.conversation()
        jid=self.submit(cid)
        job=self.claim()
        self.finish(job,outcome='recovery_required')
        with self.store.db(True) as db:
            db.execute('UPDATE ai_meta SET version=2')
            db.execute("UPDATE jobs SET route_snapshot='{}',selection_id=NULL WHERE id=?",(jid,))
        upgraded=Store(self.store.path)
        with upgraded.db() as db:
            self.assertEqual(db.execute('SELECT version FROM ai_meta').fetchone()[0],4)
            row=upgraded.job(jid,db)
            self.assertEqual((row['state'],row['resource_group']),('recovery_required',LEGACY_GROUP))
        self.assertIsNone(upgraded.claim('different-worker'))

    def test_replacing_card_cancels_only_explicit_same_owner_pending_card(self):
        """[Role] Verifies replacing card cancels only explicit same owner pending card on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        cid=self.conversation()
        self.submit(cid)
        first=self.claim()
        self.finish(first,[{'id':'p1','name':'prepare_equipment_create','arguments':canonical({'name':'First draft','option_id':1})}])
        self.finish(self.claim())
        with self.store.db() as db:
            previous=db.execute("SELECT id FROM proposals WHERE state='pending'").fetchone()[0]
        self.submit(cid,content='Change name to reviewed replacement')
        job=self.claim()
        self.finish(job,[{'id':'p2','name':'prepare_equipment_create','arguments':canonical({'name':'Replacement','option_id':1,'supersedes_proposal':previous})}])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM proposals WHERE id=?',(previous,)).fetchone()[0],'superseded')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM proposals WHERE state='pending'").fetchone()[0],1)
        self.assertEqual(self.client.post('/api/ai/proposals/'+previous+'/confirm',json={},headers=self.headers).status_code,409)

    def test_group_fairness_prefers_waiting_other_owner_and_keeps_fifo_fallback(self):
        """[Role] Verifies group fairness prefers waiting other owner and keeps fifo fallback on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        first=self.submit()
        job=self.claim()
        second=self.submit(self.conversation())
        self.login(3)
        third=self.submit(self.conversation())
        self.finish(job)
        self.assertEqual(self.claim()['id'],third)

    def test_model_profile_revision_is_frozen_and_changes_idempotency_contract(self):
        """[Role] Verifies model profile revision is frozen and changes idempotency contract on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        self.choose(cid,mid)
        key=uuid.uuid4().hex
        jid=self.submit(cid,level='default',key=key)
        route=self.registry.resolve(mid)
        with self.store.db(True) as db:
            db.execute('UPDATE ai_provider_models SET profile_revision=profile_revision+1 WHERE id=?',(mid,))
        response=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Help','reasoning_version':2,'level':'default','client_key':key},headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.claim()['route']['profile_revision'],route['profile_revision'])

    def test_ai_metadata_collection_does_not_read_ordinary_payloads(self):
        hook = self.app.after_request_funcs[None][-1]
        with patch.dict(hook.__globals__, legacy_audit_payloads=None):
            response = self.client.get('/api/ai/capabilities')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.audit_logs[-1]['StatusCode'], 200)
        self.assertEqual((self.audit_logs[-1]['RequestPayload'], self.audit_logs[-1]['ResponsePayload']), (None, None))

    def test_worker_stops_chunks_after_rejected_ack_but_delivers_own_finish(self):
        """[Role] Verifies worker stops chunks after rejected ack but delivers own finish on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        worker=Worker('http://127.0.0.1:5000','synthetic-worker-secret-0123456789abcdef','http://192.168.0.14:8080','synthetic-key','model')
        events=[]
        jid=self.submit()
        job=self.claim()
        self.assertEqual((job['id'],job['protocol']),(jid,PROTOCOL))
        class Reply:
            status_code=200
            headers={'Content-Type':'text/event-stream'}
            def __enter__(self):
                """[Role] Implements enter within this module's fixed boundary.
                [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
                [Impact] Detects regressions without production data changes or real model calls.
                """
                return self
            def __exit__(self,*_):
                """[Role] Implements exit within this module's fixed boundary.
                [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
                [Impact] Detects regressions without production data changes or real model calls.
                """
                pass
            def raise_for_status(self):
                """[Role] Implements raise for status within this module's fixed boundary.
                [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
                [Impact] Detects regressions without production data changes or real model calls.
                """
                pass
            def iter_lines(self,**_):
                """[Role] Implements iter lines within this module's fixed boundary.
                [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
                [Impact] Detects regressions without production data changes or real model calls.
                """
                for content in ('x'*4100,'y'*4100,'z'*4100):
                    yield 'data: '+canonical({'choices':[{'delta':{'content':content},'finish_reason':None}]})
                    yield ''
                yield 'data: '+canonical({'choices':[{'delta':{},'finish_reason':'stop'}]})
                yield ''
                yield 'data: [DONE]'
                yield ''
        def post(path,data):
            """[Role] Implements post within this module's fixed boundary.
            [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
            [Impact] Detects regressions without production data changes or real model calls.
            """
            events.append((path,data))
            if path.endswith('/event') and not data.get('reasoning') and not data.get('content'):
                return {'success':True,'accepted':True,'reasoning_offset':0,'content_offset':0,'cancel':False}
            return {'success':True,'accepted':False,'reasoning_offset':0,'content_offset':0,'cancel':True}
        worker.post=post
        with patch('utils.ai_assistant.worker.model_request',return_value=Reply()) as transport:
            worker.run_job(job)
        transport.assert_called_once()
        self.assertEqual(transport.call_args.args[1:4],(job['route']['trust']['origin'],'/chat/completions','synthetic-key'))
        chunks=[data for path,data in events if path.endswith('/event') and data.get('content')]
        self.assertEqual(len(chunks),1)
        self.assertEqual(events[-1][1]['outcome'],'cancelled')

    def test_dispatcher_really_runs_independent_groups_concurrently(self):
        """[Role] Verifies dispatcher really runs independent groups concurrently on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        barrier=threading.Barrier(2)
        with fake_provider(self) as peer_a,fake_provider(self,address='192.168.0.52') as peer_b:
            _,a,_=self.add_model(peer_a)
            with self.store.db(True) as db:
                group=uuid.uuid4().hex
                db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?)',(group,'Second synthetic PC'))
            _,b,_=self.add_model(peer_b,group=group)
            initial_a,initial_b=len(peer_a.calls),len(peer_b.calls)
            peer_a.barrier=peer_b.barrier=barrier
            for mid in (a,b):
                cid=self.conversation()
                self.choose(cid,mid)
                self.submit(cid,level='default')
            worker=Worker('http://127.0.0.1:5000','synthetic-worker-secret-0123456789abcdef','http://192.168.0.14:8080','unused-key','unused-model')
            completed=[]
            def post(path,data):
                """[Role] Implements post within this module's fixed boundary.
                [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
                [Impact] Detects regressions without production data changes or real model calls.
                """
                response=self.app.test_client().post(path,json=data,headers=self.worker_headers)
                if response.status_code!=200:
                    raise ValueError('synthetic internal API rejected dispatcher')
                result=response.get_json()
                if path.endswith('/finish'):
                    completed.append(result)
                    if len(completed)==2:
                        worker.stop.set()
                return result
            worker.post=post
            thread=threading.Thread(target=worker.run,daemon=True)
            thread.start()
            thread.join(timeout=12)
            worker.stop.set()
            self.assertFalse(thread.is_alive(),'dispatcher must let both independent model calls reach the barrier')
            self.assertEqual([r['state'] for r in completed],['done','done'])
            self.assertEqual(([c['method'] for c in peer_a.calls[initial_a:]],[c['method'] for c in peer_b.calls[initial_b:]]),(['POST'],['POST']))

    def test_restored_ai_database_epoch_rejects_delayed_old_lease(self):
        """[Role] Verifies restored ai database epoch rejects delayed old lease on synthetic fixtures.
        [Dependencies] Isolated Linux fixtures and temporary synthetic data; no production application or database.
        [Impact] Detects regressions without production data changes or real model calls.
        """
        jid=self.submit()
        job=self.claim()
        restored=Store(self.store.path,epoch='restored-fixture-epoch')
        with restored.db() as db,self.assertRaises(AssistantError):
            restored.lease(db,jid,job['lease'])
        self.assertIsNone(restored.claim('cannot-steal-old-job'))

    def test_key_rotation_reads_old_revision_without_reusing_flask_signing_key(self):
        """[Role] Checks a retained external decryption key across primary-key rotation.
        [Dependencies] Standard MultiFernet and only synthetic independent test keys.
        [Impact] Accepted old snapshots stay decryptable without changing their immutable contents.
        """
        _,mid,key=self.add_model()
        route=self.registry.resolve(mid)
        cid=self.conversation()
        self.assertEqual(self.choose(cid,mid).status_code,200)
        jid=self.submit(cid,level='default')
        with self.store.db() as db:
            before=self.store.job(jid,db)['route_snapshot']
        old=self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']
        self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']=Fernet.generate_key().decode()
        self.app.config['USER_AI_PROVIDER_PREVIOUS_KEYS']=canonical([old])
        trust,credential=self.registry.connection(route['provider_id'],route['revision'])
        self.assertEqual(trust['origin'],route['base_url'])
        self.assertNotIn('credential',route)
        self.assertTrue(credential.startswith('fernet:'))
        self.assertEqual(self.registry.secret(credential),key)
        self.assertNotEqual(self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY'],self.app.secret_key)
        job=self.claim()
        self.assertEqual((job['id'],job['route']['revision'],job['route']['api_key']),(jid,route['revision'],key))
        self.run_one(job)
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual((row['state'],row['route_snapshot']),('done',before))

    def test_partial_v3_schema_fails_closed_without_recreating_missing_slot_index(self):
        """[Role] Rejects an incomplete current schema before startup can repair away missing safety state.
        [Dependencies] Temporary v3 database and its authoritative group uniqueness index.
        [Impact] Partial deployments cannot silently start a second model request.
        """
        with self.store.db(True) as db:
            db.execute('DROP INDEX one_group_request')
        with self.assertRaises(ValueError):
            Store(self.store.path)

    def test_unknown_legacy_route_is_quarantined_without_inventing_a_model(self):
        """[Role] Holds an old active request whose actual provider/model was never recorded.
        [Dependencies] Synthetic legacy routing gap and current registry startup reconciliation.
        [Impact] A new default cannot relabel/reissue old inference or free its physical group slot.
        """
        jid=self.submit()
        job=self.claim()
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET selection_id=NULL,route_snapshot='{}' WHERE id=?",(jid,))
        Registry(self.store,self.app.config)
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual(row['state'],'recovery_required')
            self.assertIsNone(row['selection_id'])
            self.assertEqual(row['route_snapshot'],'{}')
            self.assertIn('실제 모델/연결 기록이 없습니다',row['error'])
        self.assertIsNone(self.claim())

    def test_legacy_queued_route_gap_stops_before_dispatch_and_keeps_history(self):
        """[Role] Finalizes an undispatched old request that cannot prove its accepted model.
        [Dependencies] Registry reconciliation and existing reservation/history ledger.
        [Impact] No new default is substituted and the original user message remains readable.
        """
        jid=self.submit(content='Preserve original accepted intent')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET selection_id=NULL,route_snapshot='{}' WHERE id=?",(jid,))
        Registry(self.store,self.app.config)
        with self.store.db() as db:
            row=self.store.job(jid,db)
            self.assertEqual((row['state'],row['reserved_chars']),('failed',0))
            self.assertEqual(db.execute("SELECT content FROM messages WHERE job=? AND role='user'",(jid,)).fetchone()[0],'Preserve original accepted intent')

    def test_catalog_task_draft_keeps_missing_fields_and_source_across_model_change(self):
        """[Role] Carries an unfinished catalog request through the ordinary-user draft schema.
        [Dependencies] Existing request tool schema, source IDs, normalized text and model selection API.
        [Impact] Missing kind is requested again; draft storage never submits an approval request.
        """
        _,mid,_=self.add_model()
        cid=self.conversation()
        self.submit(cid,content='Help request maker Draft Maker')
        self.finish(self.claim(),[{'id':'draft','name':'save_task_draft','arguments':canonical({'operation':'catalog_request','fields_json':canonical({'name':'  Draft Maker  '}),'revision':0})}])
        self.finish(self.claim())
        with self.store.db() as db:
            data=json.loads(db.execute('SELECT data FROM ai_task_drafts WHERE conversation=?',(cid,)).fetchone()[0])
            self.assertEqual(data['fields']['name'],'Draft Maker')
            self.assertIn('kind',data['missing'])
            self.assertIn('name',data['field_sources'])
        self.assertEqual(self.count('approval_requests'),0)
        self.choose(cid,mid)
        self.submit(cid,content='Continue that request',level='default')
        self.assertIn('Draft Maker',canonical(self.claim()['messages']))

    def test_generic_draft_cannot_add_owner_or_an_unoffered_business_operation(self):
        """[Role] Rejects unknown operations and privilege fields inside partial business JSON.
        [Dependencies] Closed operation schemas and the server's ordinary-user tool allowlist.
        [Impact] Draft persistence cannot add an owner/role or bypass confirmation/admin boundaries.
        """
        from utils.ai_assistant.context import normalized_draft
        for operation,fields in (('catalog_request',{'name':'Bad','owner':3}),('equipment_delete',{'equipment_id':2}),('preferences',{'Role':'admin'})):
            with self.subTest(operation=operation),self.assertRaises(AssistantError):
                normalized_draft({'operation':operation,'fields_json':canonical(fields),'revision':0})

    def test_persisted_handoff_summary_charged_once_and_seeded_after_ledger_rebuild(self):
        """[Role] Counts persisted handoff state separately from display messages and draft data.
        [Dependencies] First-step reservation, tool continuation and additive ledger reconstruction.
        [Impact] A derived summary cannot bypass account storage limits or be charged twice on continuation.
        """
        jid=self.submit(content='Count the saved handoff summary')
        first=self.claim()
        with self.store.db() as db:
            handoff=db.execute('SELECT handoff_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0]
            self.assertGreater(handoff,0)
            self.assertLessEqual(handoff,16384)
        self.finish(first,[{'id':'read','name':'search_equipment','arguments':'{}'}])
        second=self.claim()
        self.finish(second)
        with self.store.db(True) as db:
            self.assertEqual(db.execute('SELECT handoff_chars FROM jobs WHERE id=?',(jid,)).fetchone()[0],handoff)
            before=db.execute('SELECT used_chars FROM storage_accounts WHERE owner=2').fetchone()[0]
            db.execute('DELETE FROM storage_accounts')
        rebuilt=Store(self.store.path)
        with rebuilt.db() as db:
            self.assertEqual(db.execute('SELECT used_chars FROM storage_accounts WHERE owner=2').fetchone()[0],before)

    def test_first_new_turn_records_choice_for_an_unattributed_old_conversation(self):
        """[Role] Persists the first explicit new choice without inventing a source for old answers.
        [Dependencies] Owner-bound admission and the conversation selection revision/event transaction.
        [Impact] An old conversation cannot inherit another session's remembered model preference.
        """
        cid=self.conversation()
        with self.store.db(True) as db:
            db.execute('UPDATE conversations SET selection_id=NULL WHERE id=?',(cid,))
        self.submit(cid,level='medium')
        with self.store.db() as db:
            row=db.execute('SELECT selection_id,next_level,selection_revision FROM conversations WHERE id=?',(cid,)).fetchone()
            self.assertEqual(tuple(row),(LEGACY_MODEL,'medium',2))

    def test_standard_efforts_have_distinct_wire_values_and_old_browser_fails_closed(self):
        """[Role] Distinguishes new low from old off and blocks unsupported/stale-client admissions.
        [Dependencies] Real owner routes and synthetic accepted jobs; no external model call.
        [Impact] Disabled controls remain server-enforced and cached old clients cannot reinterpret low/high.
        """
        cid=self.conversation()
        choice=next(m for m in self.registry.choices()['models'] if m['id']==LEGACY_MODEL)
        self.assertEqual(choice['levels'],['off','low','medium','xhigh'])
        self.assertEqual(choice['default_level'],'medium')
        self.assertEqual(choice['level_reasons']['high'],'모델 미지원')
        for level in ('high','max'):
            response=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Help','level':level,'reasoning_version':2,'client_key':uuid.uuid4().hex},headers=self.headers)
            self.assertEqual(response.status_code,409,response.get_json())
        stale=self.client.post('/api/ai/conversations/'+cid+'/turns',json={'content':'Help','level':'low','client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(stale.status_code,409)
        self.assertIn('새로고침',stale.get_json()['message'])
        with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        for level,effort in (('off','none'),('low','low')):
            self.submit(cid,level=level)
            job=self.claim();self.assertEqual(job['reasoning_effort'],effort)
            self.finish(job)

    def test_admin_effort_policy_is_atomic_versioned_and_server_enforced(self):
        """[Role] Restricts known model policy/defaults and proves frozen accepted work survives later admin changes.
        [Dependencies] Admin CSRF/role checks, model profile revision and isolated AI Store.
        [Impact] Invalid settings cannot partially save or silently change an existing route.
        """
        cid=self.conversation();jid=self.submit(cid,level='medium')
        with self.store.db() as db:before=db.execute('SELECT route_snapshot FROM jobs WHERE id=?',(jid,)).fetchone()[0]
        self.login(1)
        route=self.registry.resolve(LEGACY_MODEL)
        payload={'id':LEGACY_MODEL,'label':'Qwen preset','published':True,'sort_order':0,'context_tokens':65536,'revision':1,
                 'reasoning_levels':['off','medium'],'reasoning_default':'off','profile_revision':route['profile_revision']}
        for extra in ({'reasoning_levels':['max']},{'reasoning_levels':['off','off']},{'reasoning_levels':'off'},
                      {'reasoning_default':'xhigh'},{'reasoning_levels':[True]}):
            response=self.client.post('/api/admin/ai/providers/'+route['provider_id']+'/models',json={**payload,**extra},headers=self.headers)
            self.assertEqual(response.status_code,400,response.get_json())
        response=self.client.post('/api/admin/ai/providers/'+route['provider_id']+'/models',json=payload,headers=self.headers)
        self.assertEqual(response.status_code,200,response.get_json())
        stale=self.client.post('/api/admin/ai/providers/'+route['provider_id']+'/models',json=payload,headers=self.headers)
        self.assertEqual(stale.status_code,409)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT route_snapshot FROM jobs WHERE id=?',(jid,)).fetchone()[0],before)
            self.assertIsNone(db.execute('SELECT verified_revision FROM ai_provider_models WHERE id=?',(LEGACY_MODEL,)).fetchone()[0])
        job=self.claim();self.assertEqual(job['reasoning_effort'],'medium');self.finish(job)
        # Explicitly simulate a completed capability verification, as in the other ready-model fixtures.
        with self.store.db(True) as db:db.execute('UPDATE ai_provider_models SET verified_revision=1 WHERE id=?',(LEGACY_MODEL,))
        self.login(2);fresh=self.conversation()
        with self.store.db() as db:self.assertEqual(db.execute('SELECT next_level FROM conversations WHERE id=?',(fresh,)).fetchone()[0],'off')
        rejected=self.client.post('/api/ai/conversations/'+fresh+'/turns',json={'content':'Help','level':'low','reasoning_version':2,'client_key':uuid.uuid4().hex},headers=self.headers)
        self.assertEqual(rejected.status_code,409)
        denied=self.client.post('/api/admin/ai/providers/'+route['provider_id']+'/models',json=payload,headers=self.headers)
        self.assertEqual(denied.status_code,403)

    def test_unknown_model_custom_efforts_require_real_fixture_probe(self):
        """[Role] Verifies all configured custom efforts through the actual worker and loopback SSE transport.
        [Dependencies] Unknown OpenAI-compatible synthetic provider, private group queue and nonce checks.
        [Impact] A configured high/max is not accepted on an unknown model until the complete probe succeeds.
        """
        with fake_provider(self) as peer:
            pid,mid,_=self.add_model(peer,tools=False)
            self.login(1)
            levels=['off','low','medium','high','xhigh','max']
            version=self.registry.resolve(mid)['profile_revision']
            first=len(peer.calls)
            self.registry.update_model(pid,{'id':mid,'label':'Custom effort model','published':True,'sort_order':0,'context_tokens':65536,
                'revision':1,'reasoning_levels':levels,'reasoning_default':'max','profile_revision':version})
            self.assertFalse(next(m for m in self.registry.choices()['models'] if m['id']==mid)['available'])
            response=self.client.post('/api/admin/ai/models/'+mid+'/probe',json={'tools':True,'reasoning':True,'client_key':uuid.uuid4().hex},headers=self.headers)
            self.assertEqual(response.status_code,202,response.get_json())
            for _ in range(8):self.run_one(self.claim())
            route=self.registry.resolve(mid)
            self.assertEqual(route['profile']['levels'],levels)
            self.assertEqual(route['profile']['default_level'],'max')
            self.assertEqual([c['payload'].get('reasoning_effort') for c in peer.calls[first:]],[None,None,'none','low','medium','high','xhigh','max'])

    def test_legacy_reasoning_upgrade_preserves_history_and_accepted_snapshot(self):
        """[Role] Converts only next-turn alias names and proves startup migration is idempotent.
        [Dependencies] A synthetic pre-versioned profile/conversation and frozen accepted route.
        [Impact] Historical job levels/route bytes remain unchanged; legacy low still dispatches none.
        """
        cid=self.conversation();jid=self.submit(cid,level='off')
        legacy={'chat':True,'tools':True,'levels':['low','medium','high']}
        with self.store.db(True) as db:
            frozen=json.loads(db.execute('SELECT route_snapshot FROM jobs WHERE id=?',(jid,)).fetchone()[0]);frozen['profile']=legacy
            frozen=canonical(frozen)
            db.execute('UPDATE jobs SET route_snapshot=?,level=? WHERE id=?',(frozen,'low',jid))
            db.execute('UPDATE ai_provider_models SET profile=? WHERE id=?',(canonical(legacy),LEGACY_MODEL))
            db.execute("UPDATE conversations SET next_level='high' WHERE id=?",(cid,))
        Registry(self.store,self.app.config)
        with self.store.db() as db:
            self.assertEqual(tuple(db.execute('SELECT route_snapshot,level FROM jobs WHERE id=?',(jid,)).fetchone()),(frozen,'low'))
            selection=tuple(db.execute('SELECT next_level,selection_revision FROM conversations WHERE id=?',(cid,)).fetchone())
            self.assertEqual(selection[0],'xhigh')
        Registry(self.store,self.app.config)
        with self.store.db() as db:self.assertEqual(tuple(db.execute('SELECT next_level,selection_revision FROM conversations WHERE id=?',(cid,)).fetchone()),selection)
        self.assertEqual(self.claim()['reasoning_effort'],'none')

    def test_legacy_probe_aliases_keep_original_wire_contract(self):
        """[Role] Completes a pre-standardization probe without reinterpreting low/high under the new enum.
        [Dependencies] Versionless frozen probe profile and the actual fake-provider worker path.
        [Impact] An already accepted probe dispatches none/medium/xhigh and records a standard verified profile.
        """
        model='qwen3.8-flash-next-iq3_xxs'
        with fake_provider(self,models=[{'id':model}]) as peer:
            _,mid,_=self.add_model(peer,tools=False,adapter='strata',upstream=model)
            first=len(peer.calls)
            self.login(1)
            response=self.client.post('/api/admin/ai/models/'+mid+'/probe',json={'tools':False,'reasoning':True,'client_key':uuid.uuid4().hex},headers=self.headers)
            self.assertEqual(response.status_code,202,response.get_json());jid=response.get_json()['job_id']
            with self.store.db(True) as db:
                frozen=json.loads(db.execute('SELECT route_snapshot FROM jobs WHERE id=?',(jid,)).fetchone()[0])
                frozen['profile']={'chat':False,'tools':False,'levels':['low','medium','high']}
                db.execute('UPDATE jobs SET route_snapshot=?,probe_plan=? WHERE id=?',(canonical(frozen),canonical(['chat','low','medium','high']),jid))
            for _ in range(4):self.run_one(self.claim())
            self.assertEqual([c['payload'].get('reasoning_effort') for c in peer.calls[first:]],[None,'none','medium','xhigh'])
            self.assertEqual(self.registry.resolve(mid)['profile']['verified_levels'],['off','medium','xhigh'])

    def test_first_registry_seed_upgrades_old_null_selection_but_new_rows_use_default(self):
        """[Role] Separates pre-registry low aliases from new unselected model-default conversations.
        [Dependencies] Synthetic v2-style conversation and first registry seeding.
        [Impact] Old choices do not become real low and an unknown configured model is not auto-approved.
        """
        cid=self.conversation()
        with self.store.db(True) as db:
            account=db.execute('SELECT account_key FROM conversations WHERE id=?',(cid,)).fetchone()[0]
            db.execute("UPDATE conversations SET selection_id=NULL,next_level='low' WHERE id=?",(cid,))
            db.execute('DELETE FROM ai_provider_models')
            db.execute('DELETE FROM ai_provider_trust')
            db.execute('DELETE FROM ai_provider_revisions')
            db.execute('DELETE FROM ai_providers')
        Registry(self.store,{**self.app.config,'USER_AI_MODEL':'unrecognized-custom-model'})
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT next_level FROM conversations WHERE id=?',(cid,)).fetchone()[0],'off')
            self.assertIsNone(db.execute('SELECT verified_revision FROM ai_provider_models WHERE id=?',(LEGACY_MODEL,)).fetchone()[0])
        fresh=self.store.create_conversation(2,account)
        Registry(self.store,self.app.config)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT next_level FROM conversations WHERE id=?',(fresh,)).fetchone()[0],'default')

