"""Synthetic HTTP/SSE and real TLS. The last socket hop goes exclusively to loopback."""
import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import unittest
from unittest.mock import patch
import uuid
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from test_equipment_ai import AssistantTests
from utils.ai_assistant.policy import AssistantError
from utils.ai_assistant.provider_trust import certificate, origin, resolve_addresses, RevisionPolicy, STRATA_HTTP
from utils.ai_assistant.providers import LEGACY_GROUP, LEGACY_MODEL, LEGACY_PROVIDER, PROTOCOL
from utils.ai_assistant.transport import model_request
from utils.ai_assistant.worker import Worker


A, B = '192.168.0.51', '192.168.0.52'
HOST_A, HOST_B = 'gpu-a.fixture.test', 'gpu-b.fixture.test'
URL_A, URL_B = 'https://' + HOST_A + ':8443', 'https://' + HOST_B + ':8443'
MODEL = 'fixture-chat'
STRATA_MODEL = 'qwen3.8-flash-next-iq3_xxs'


def issue(name, issuer=None, hosts=(), validity=(-1,7), signing=True):
    key = ec.generate_private_key(ec.SECP256R1())
    dn = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    ca = issuer is None
    issuer_dn, signer = (dn,key) if ca else (issuer[0].subject,issuer[1])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(dn).issuer_name(issuer_dn).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now + timedelta(days=validity[0]))
            .not_valid_after(now + timedelta(days=validity[1]))
            .add_extension(x509.BasicConstraints(ca=ca,path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True,False,False,False,False,ca and signing,ca and signing,False,False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signer.public_key()), False))
    if not ca:
        values = [x509.IPAddress(ipaddress.ip_address(h)) if h[0].isdigit() else x509.DNSName(h) for h in hosts]
        cert = cert.add_extension(x509.SubjectAlternativeName(values), False).add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
    return cert.sign(signer, hashes.SHA256()), key


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode('ascii')


class MockProvider:
    def __init__(self, root, stack, *, pair=None, key='', models=(MODEL,)):
        self.calls, self.key, self.models = [], key, list(models)
        self.redirect = False
        self.barrier = None
        self.bad_nonce = False
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_api(self, payload=None):
                auth = self.headers.get('Authorization', '')
                provider.calls.append((self.command, self.path, self.headers['Host'], auth, payload))
                if provider.redirect:
                    self.send_response(302)
                    self.send_header('Location','http://169.254.169.254/latest/meta-data/')
                elif auth != ('Bearer ' + provider.key if provider.key else ''):
                    self.send_response(401)
                elif payload is None:
                    self.send_response(200)
                    self.send_header('Content-Type','application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'data':[{'id':m} for m in provider.models]}).encode())
                    return
                else:
                    if provider.barrier:
                        provider.barrier.wait(timeout=5)
                    self.send_response(200)
                    self.send_header('Content-Type','text/event-stream')
                    self.end_headers()
                    text = payload['messages'][-1]['content']
                    nonce = (re.findall(r'[0-9a-f]{32}',text) or ['fixture answer'])[-1]
                    delta = {'content':'wrong nonce' if provider.bad_nonce else nonce}
                    if payload.get('tools') and payload['tools'][0]['function']['name'] == 'assistant_probe':
                        delta = {'tool_calls':[{'index':0,'id':'probe','function':{'name':'assistant_probe',
                            'arguments':json.dumps({'nonce':nonce})}}]}
                    if payload.get('reasoning_effort') not in (None,'none'):
                        delta['reasoning_content'] = 'synthetic trace'
                    frame = {'choices':[{'delta':delta,'finish_reason':'tool_calls' if 'tool_calls' in delta else 'stop'}]}
                    self.wfile.write(('data: '+json.dumps(frame)+'\n\ndata: [DONE]\n\n').encode())
                    return
                self.end_headers()

            def do_GET(self):
                self.handle_api()

            def do_POST(self):
                self.handle_api(json.loads(self.rfile.read(int(self.headers['Content-Length']))))

        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        stack.callback(self.server.server_close)
        if pair:
            tag = uuid.uuid4().hex
            crt, key_file = root/(tag+'.pem'), root/(tag+'.key')
            crt.write_text(pem(pair[0]),encoding='ascii')
            key_file.write_bytes(pair[1].private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(crt,key_file)
            self.server.socket = ctx.wrap_socket(self.server.socket,server_side=True)
        thread = threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        thread.start()
        stack.callback(thread.join,2)
        stack.callback(self.server.shutdown)


class ProviderCaTests(unittest.TestCase):
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit

    def setUp(self):
        AssistantTests.setUp(self)
        self.registry = self.app.extensions['equipment_assistant']['registry']
        self.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        self.app.config['USER_AI_STRATA_KEY'] = 'fixture-legacy'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.ca_a, self.ca_b = issue('fixture CA A'), issue('fixture CA B')
        self.ca_pem = pem(self.ca_a[0])
        self.leaf_a = issue('A',self.ca_a,(HOST_A,A))
        self.leaf_b = issue('B',self.ca_b,(HOST_B,B))
        self.a = MockProvider(self.root,self.stack,pair=self.leaf_a,key='fixture-A')
        self.b = MockProvider(self.root,self.stack,pair=self.leaf_b,key='fixture-B')
        self.legacy = MockProvider(self.root,self.stack,key='fixture-legacy',models=(STRATA_MODEL,))
        self.peers = {(A,8443):self.a, (B,8443):self.b, ('192.168.0.14',8080):self.legacy}
        self.dns = {HOST_A:[A],HOST_B:[B]}
        original_info, original_connect = socket.getaddrinfo, socket.create_connection

        def dns(host, port, *args, **kwargs):
            if host in self.dns:
                return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,port)) for ip in self.dns[host]]
            ipaddress.ip_address(host)  # Fail before contacting a DNS server for an unknown name.
            return original_info(host,port,*args,**kwargs)

        def connect(peer, timeout=None, source_address=None):
            server = self.peers[peer].server
            return original_connect(('127.0.0.1',server.server_port),timeout,source_address)

        self.stack.enter_context(patch('socket.getaddrinfo',dns))
        self.stack.enter_context(patch('socket.create_connection',connect))
        self.login(1)
        self.worker = Worker('http://127.0.0.1:5000',self.app.config['USER_AI_WORKER_TOKEN'],
                             STRATA_HTTP,'fixture-legacy',STRATA_MODEL)
        self.worker.post = self.internal

    def internal(self, path, data):
        response = self.app.test_client().post(path,json=data,headers=self.worker_headers)
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()

    def claim(self):
        return self.internal('/internal/ai/claim',{'worker':'fixture-worker','protocol':PROTOCOL})['job']

    def request(self, path, data, status=200):
        response = self.client.post(path,json=data,headers=self.headers)
        self.assertEqual(response.status_code,status,response.get_json())
        return response.get_json()

    def save(self, pid=None, status=None, **overrides):
        data = dict(name='Fixture A',base_url=URL_A,adapter='openai',enabled=True,manual=False,
                    resource_group=LEGACY_GROUP,revision=0,trust_mode='private',ca_pem=self.ca_pem,api_key='fixture-A')
        for field,value in overrides.items():
            if value is None:
                data.pop(field,None)
            else:
                data[field] = value
        return self.request('/api/admin/ai/providers'+('/'+pid if pid else ''),data,status or (200 if pid else 201)).get('id')

    def provider(self,pid):
        return next(p for p in self.client.get('/api/admin/ai/providers').get_json()['providers'] if p['id']==pid)

    def discover(self,pid,rev,status=200):
        return self.request('/api/admin/ai/providers/'+pid+'/discover',{'candidate_revision':rev},status)

    def queue_probe(self,pid,rev,mid,tools=False,reasoning=False,context=32768):
        return self.request('/api/admin/ai/models/'+mid+'/probe',dict(client_key=uuid.uuid4().hex,tools=tools,
                            reasoning=reasoning,provider_id=pid,candidate_revision=rev,context_tokens=context),202)['job_id']

    def activate(self, **options):
        pid = self.save(**options)
        self.discover(pid,1)
        mid = self.provider(pid)['candidate']['models'][0]['id']
        self.assertNotIn(mid,[m['id'] for m in self.registry.choices()['models']])
        self.queue_probe(pid,1,mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.provider(pid)['revision'],1)
        self.assertNotIn(mid,[m['id'] for m in self.registry.choices()['models']])
        self.request('/api/admin/ai/providers/'+pid+'/models',
                     dict(id=mid,label='Fixture model',published=True,sort_order=0,context_tokens=32768,revision=1))
        return pid,mid

    def queue_chat(self,mid):
        self.login(2)
        cid = self.conversation()
        with self.store.db() as db:
            version=db.execute('SELECT selection_revision FROM conversations WHERE id=?',(cid,)).fetchone()[0]
        self.request('/api/ai/conversations/'+cid+'/selection',dict(selection_id=mid,reasoning_version=2,level='default',revision=version))
        return cid,self.submit(cid,level='default')

    def state(self,jid):
        with self.store.db() as db:
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())

    def test_admin_register_discover_probe_publish_stream_reopen(self):
        page = self.client.get('/admin/ai/providers')
        self.assertEqual(page.status_code,200)
        for field in ('ca_file','trust_mode','provider-candidate-discover','provider-revoke'):
            self.assertIn(field,page.get_data(as_text=True))
        pid,mid = self.activate()
        rev = self.provider(pid)
        self.assertEqual(rev['fingerprint'],self.ca_a[0].fingerprint(hashes.SHA256()).hex())
        self.assertEqual(rev['expires'],self.ca_a[0].not_valid_after_utc.isoformat())
        self.assertIsNone(rev['candidate'])
        cid,jid = self.queue_chat(mid)
        packet = self.claim()
        self.assertIsNotNone(packet,self.state(jid)['error'])
        self.assertNotIn('ca_pem',self.state(jid)['route_snapshot'])
        self.assertNotIn('credential',self.state(jid)['route_snapshot'])
        self.worker.run_job(packet)
        self.assertEqual(self.state(jid)['state'],'done')
        self.login(2)
        messages = self.client.get('/api/ai/conversations/'+cid+'/messages').get_json()
        self.assertIn('fixture answer',[m['content'] for m in messages['messages']])
        self.assertNotIn(URL_A,json.dumps(messages))
        self.assertEqual([(c[0],c[1]) for c in self.a.calls],
                         [('GET','/v1/models'),('POST','/v1/chat/completions'),('POST','/v1/chat/completions')])
        self.assertTrue(all(c[2]==HOST_A+':8443' and c[3]=='Bearer fixture-A' for c in self.a.calls))
        self.assertNotIn('strata_mcp',self.a.calls[-1][4])
        logs = json.dumps(self.audit_logs)
        for secret in ('fixture-A','BEGIN CERTIFICATE','fernet:'):
            self.assertNotIn(secret,logs)
        with self.store.db() as db:
            events = db.execute('SELECT actor,origin,fingerprint,result FROM ai_provider_trust_events WHERE provider=? ORDER BY id',(pid,)).fetchall()
        self.assertEqual([r['result'] for r in events],['candidate_saved','models_passed','worker_probe_passed','activated'])
        self.assertTrue(all(r['actor']==1 and r['origin']==URL_A and r['fingerprint']==rev['fingerprint'] for r in events))

    def test_changed_origin_never_inherits_key_or_ca_and_failed_candidate_serves_old_model(self):
        pid,mid = self.activate()
        self.save(pid,revision=1,base_url=URL_B,ca_pem=None,api_key=None,status=422)
        self.save(pid,revision=1,base_url=URL_B,ca_pem=pem(self.ca_b[0]),api_key=None)
        draft = self.provider(pid)['candidate']
        self.assertFalse(draft['has_key'])
        self.login(2)
        self.app.config['USER_AI_MODEL_DISCOVERY'] = True
        with self.store.db(True) as db:
            db.execute('UPDATE ai_providers SET last_checked=NULL WHERE id=?',(pid,))
        self.assertEqual(self.client.get('/api/ai/models').status_code,200)
        self.assertEqual(self.b.calls,[])
        self.login(1)
        self.assertIn('API 키',self.discover(pid,2,422)['message'])
        self.assertEqual(self.b.calls[-1][3],'')
        self.assertEqual(self.provider(pid)['revision'],1)
        _,jid = self.queue_chat(mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.state(jid)['state'],'done')
        self.assertEqual(self.a.calls[-1][3],'Bearer fixture-A')

    def test_disjoint_ca_and_key_for_two_live_connections_and_impersonated_worker_peer(self):
        p1,m1 = self.activate()
        p2 = self.save(name='Fixture B',base_url=URL_B,ca_pem=pem(self.ca_b[0]),api_key='fixture-B')
        self.discover(p2,1)
        m2 = self.provider(p2)['candidate']['models'][0]['id']
        self.queue_probe(p2,1,m2)
        self.worker.run_job(self.claim())
        self.request('/api/admin/ai/providers/'+p2+'/models',dict(id=m2,label='B',published=True,sort_order=0,context_tokens=32768,revision=1))
        self.assertEqual({m['id'] for m in self.registry.choices()['models'] if m['available']},{LEGACY_MODEL,m1,m2})
        self.assertEqual(self.b.calls[-1][3],'Bearer fixture-B')
        _,jid = self.queue_chat(m2)
        job = self.claim()
        wrong = MockProvider(self.root,self.stack,pair=issue('forged B',self.ca_a,(HOST_B,B)),key='fixture-B')
        self.peers[(B,8443)] = wrong
        self.worker.run_job(job)
        self.assertEqual((self.state(jid)['state'],self.state(jid)['error_code']),('failed','PROVIDER_TLS'))
        self.assertEqual(wrong.calls,[])
        self.login(1)
        result=self.request('/api/admin/ai/providers/'+p2+'/discover',{},422)
        self.assertIn('인증서',result['message'])
        self.assertEqual(wrong.calls,[])
        _,jid = self.queue_chat(m1)
        self.worker.run_job(self.claim())
        self.assertEqual(self.state(jid)['state'],'done')

    def test_hostname_validity_san_and_system_vs_private_roots(self):
        pid = self.save()
        for pair in (issue('wrong',self.ca_a,('elsewhere.fixture.test',)),
                     issue('expired',self.ca_a,(HOST_A,),validity=(-4,-1)),
                     issue('future',self.ca_a,(HOST_A,),validity=(1,4)),
                     issue(HOST_A,self.ca_a,())):
            with self.subTest(subject=pair[0].subject):
                invalid = MockProvider(self.root,self.stack,pair=pair,key='fixture-A')
                self.peers[(A,8443)] = invalid
                self.assertIn('인증서',self.discover(pid,1,422)['message'])
                self.assertFalse(invalid.calls)
        self.peers[(A,8443)] = self.a
        self.save(base_url='https://'+A+':8443',trust_mode='system',ca_pem=None)
        system = next(p for p in self.registry.admin_list()['providers'] if p['candidate'] and p['id']!=pid)
        self.assertIn('인증서',self.discover(system['id'],1,422)['message'])
        system_ca = self.root/'fixture-system.pem'
        system_ca.write_text(self.ca_pem,encoding='ascii')
        with patch.dict(os.environ,{'SSL_CERT_FILE':str(system_ca)}):
            self.discover(system['id'],1)
            private = self.save(base_url='https://'+A+':8443',ca_pem=pem(self.ca_b[0]))
            count=len(self.a.calls)
            self.assertIn('인증서',self.discover(private,1,422)['message'])
            self.assertEqual(len(self.a.calls),count)
        self.peers[(A,8443)] = MockProvider(self.root,self.stack,pair=issue('DNS only',self.ca_a,(HOST_A,)),key='fixture-A')
        by_ip = self.save(base_url='https://'+A+':8443')
        self.assertIn('인증서',self.discover(by_ip,1,422)['message'])
        self.assertFalse(self.peers[(A,8443)].calls)

    def test_private_key_non_ca_expired_bundle_and_oversize_rejected_before_storage_or_logging(self):
        private_key = self.leaf_a[1].private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()).decode()
        for invalid in (private_key,self.ca_pem+private_key,pem(self.leaf_a[0]),pem(issue('expired',validity=(-4,-1))[0]),
                        pem(issue('no signing',signing=False)[0]),self.ca_pem+self.ca_pem,'x'*16385,{'path':'fixture.pem'}):
            self.save(ca_pem=invalid,status=422)
        response=self.client.post('/api/admin/ai/providers',data=b'{"api_key":"fixture-malformed-private',
                                  content_type='application/json',headers=self.headers)
        self.assertEqual(response.status_code,400)
        log = json.dumps(self.audit_logs)
        for value in ('PRIVATE KEY','fixture-malformed-private','fixture-A',private_key.splitlines()[1]):
            self.assertNotIn(value,log)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_provider_revisions').fetchone()[0],1)

    def test_destination_all_answers_rebinding_self_and_redirects(self):
        for base in ('http://8.8.8.8:8080','http://169.254.169.254','http://192.168.0.24','https://user:password@'+A,'https://*.fixture.test','https://192.168.0.0/24',
                     'https://192.168.0.24','https://192.168.0.0','https://192.168.0.255','https://127.0.0.1',
                     'https://0.0.0.0','https://169.254.169.254','https://224.0.0.1','https://[::1]',
                     'https://8.8.8.8','https://192.168.1.8',URL_A+'/v1/admin',URL_A+'?',URL_A+'#'):
            with self.subTest(base=base),self.assertRaises(AssistantError):
                resolve_addresses(base,'new')
        with patch.object(socket.socket,'bind',return_value=None),self.assertRaises(AssistantError):
            resolve_addresses(URL_A,'new')
        self.dns[HOST_A] = [A,'169.254.169.254']
        self.save(status=422)
        self.dns[HOST_A] = [A]
        pid = self.save()
        for answers in ([B],[A,B],[A,'127.0.0.1']):
            self.dns[HOST_A] = answers
            self.discover(pid,1,422)
            self.assertEqual(self.a.calls+self.b.calls,[])
        self.dns[HOST_A] = [A]
        self.a.redirect = True
        self.assertIn('리디렉션',self.discover(pid,1,422)['message'])
        self.assertEqual(len(self.a.calls),1)

    def test_authority_origin_csrf_and_worker_protocol(self):
        path = '/api/admin/ai/providers'
        self.login(2)
        self.request(path,{},403)
        self.assertEqual(self.app.test_client().post(path,json={},headers=self.worker_headers).status_code,401)
        self.login(1)
        for suffix, payload in (('',{}),('/'+LEGACY_PROVIDER+'/revoke-trust',{'revision':1}),
                                ('/'+LEGACY_PROVIDER+'/discover',{'candidate_revision':1})):
            for headers in ({},{'Origin':'https://untrusted.test','X-CSRFToken':'fixture-csrf'}):
                self.assertEqual(self.client.post(path+suffix,json=payload,headers=headers).status_code,403)
        self.assertEqual(self.client.post('/internal/ai/claim',json={'worker':'old','protocol':3},headers=self.worker_headers).status_code,409)
        headers = {**self.worker_headers,'X-Forwarded-For':'127.0.0.1'}
        self.assertEqual(self.client.post('/internal/ai/claim',json={'worker':'bad','protocol':4},headers=headers).status_code,403)

    def test_queue_pins_prior_version_through_cutover_and_serializes_candidate_and_chat(self):
        pid,mid = self.activate()
        self.save(pid,revision=1,base_url=URL_B,ca_pem=pem(self.ca_b[0]),api_key='fixture-B')
        self.discover(pid,2)
        probe_id=self.queue_probe(pid,2,mid)
        probe=self.claim()
        self.assertEqual(probe['id'],probe_id)
        _,chat_id=self.queue_chat(mid)
        snapshot=self.state(chat_id)['route_snapshot']
        self.assertIsNone(self.claim())
        self.worker.run_job(probe)
        queued=self.claim()
        self.assertEqual((queued['id'],queued['route']['revision'],queued['route']['trust']['origin']),(chat_id,1,URL_A))
        self.assertEqual(self.state(chat_id)['route_snapshot'],snapshot)
        self.worker.run_job(queued)
        self.assertEqual(self.state(chat_id)['state'],'done')
        _,next_id=self.queue_chat(mid)
        new=self.claim()
        self.assertEqual((new['id'],new['route']['revision'],new['route']['trust']['origin']),(next_id,2,URL_B))
        self.worker.run_job(new)
        self.assertEqual((self.a.calls[-1][3],self.b.calls[-1][3]),('Bearer fixture-A','Bearer fixture-B'))

    def test_failed_worker_probe_and_concurrent_save_leave_active_revision_in_service(self):
        pid,mid = self.activate()
        self.save(pid,revision=1,base_url=URL_A+'/v1/',ca_pem=None,api_key=None)
        self.assertTrue(self.provider(pid)['candidate']['has_key'])
        self.discover(pid,2)
        self.a.bad_nonce=True
        jid=self.queue_probe(pid,2,mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.state(jid)['state'],'failed')
        self.assertEqual(self.registry.resolve(mid)['revision'],1)
        self.a.bad_nonce=False
        self.queue_probe(pid,2,mid)
        stale=self.claim()
        data=dict(name='racing edit',base_url=URL_A,adapter='openai',resource_group=LEGACY_GROUP,
                  enabled=True,manual=False,revision=1,candidate_revision=2)
        barrier=threading.Barrier(2)
        def save_one():
            barrier.wait(timeout=5)
            try:
                self.registry.save(data,pid,1)
                return 200
            except AssistantError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(save_one) for _ in range(2)]
            self.assertEqual(sorted(f.result() for f in futures),[200,409])
        self.worker.run_job(stale)
        self.assertEqual(self.state(stale['id'])['state'],'failed')
        self.assertEqual((self.provider(pid)['revision'],self.provider(pid)['candidate']['revision']),(1,3))
        _,jid=self.queue_chat(mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.state(jid)['state'],'done')

    def test_explicit_revocation_stops_queued_work_and_preserves_history(self):
        pid,mid = self.activate()
        old_cid,done=self.queue_chat(mid)
        self.worker.run_job(self.claim())
        _,queued=self.queue_chat(mid)
        before=self.state(queued)['route_snapshot']
        self.login(1)
        self.request('/api/admin/ai/providers/'+pid+'/revoke-trust',{'revision':1})
        self.assertEqual((self.state(queued)['state'],self.state(queued)['error_code']),('failed','PROVIDER_REVOKED'))
        self.assertEqual(self.state(queued)['route_snapshot'],before)
        self.assertIsNone(self.claim())
        with self.assertRaises(AssistantError):
            self.registry.resolve(mid)
        self.assertEqual(self.state(done)['state'],'done')
        self.login(2)
        self.assertIn('fixture answer',self.client.get('/api/ai/conversations/'+old_cid+'/messages').get_data(as_text=True))

    def test_existing_revision_six_positional_schema_8080_and_pinned_historical_job(self):
        from utils.ai_assistant.provider_candidates import migrate_trust
        with self.store.db(True) as db:
            for table in ('ai_candidate_models','ai_provider_candidates','ai_provider_trust_events','ai_provider_trust'):
                db.execute('DROP TABLE '+table)
            db.execute('''INSERT INTO ai_provider_revisions SELECT provider,6,base_url,adapter,resource_group,credential,created
                          FROM ai_provider_revisions WHERE provider=? AND revision=1''',(LEGACY_PROVIDER,))
            db.execute('UPDATE ai_providers SET name=?,revision=6 WHERE id=?',('260Strata',LEGACY_PROVIDER))
            db.execute('UPDATE ai_provider_models SET verified_revision=6 WHERE id=?',(LEGACY_MODEL,))
            migrate_trust(db)
        self.registry.discover(LEGACY_PROVIDER,True)
        self.login(2)
        cid=self.conversation()
        jid=self.submit(cid)
        # Snapshot in the exact older format, including an environment credential reference.
        frozen=json.loads(self.state(jid)['route_snapshot'])
        frozen['credential']='env:USER_AI_STRATA_KEY'
        with self.store.db(True) as db:
            db.execute('UPDATE jobs SET route_snapshot=? WHERE id=?',(json.dumps(frozen),jid))
        job=self.claim()
        self.assertEqual((job['route']['revision'],job['route']['trust']['origin'],job['route']['resource_group']),(6,STRATA_HTTP,LEGACY_GROUP))
        self.worker.run_job(job)
        self.assertEqual(self.state(jid)['state'],'done')
        self.assertEqual([(c[0],c[1]) for c in self.legacy.calls],[('GET','/v1/models'),('POST','/v1/chat/completions')])
        payload=self.legacy.calls[-1][4]
        self.assertEqual((payload['model'],payload['reasoning_effort'],payload['strata_mcp']),(STRATA_MODEL,'medium',False))
        self.assertEqual(self.legacy.calls[-1][3],'Bearer fixture-legacy')
        self.assertEqual(json.loads(self.state(jid)['route_snapshot']),frozen)
    def test_new_http_provider_discovery_probe_chat_and_dns_change(self):
        """Exercise an independent LAN origin through the web registry and a real worker stream."""
        plain = MockProvider(self.root, self.stack, key='fixture-A')
        self.peers[(A,8080)] = plain
        base = 'http://' + HOST_A + ':8080'
        pid, mid = self.activate(base_url=base, trust_mode='system', ca_pem=None)
        _, jid = self.queue_chat(mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.state(jid)['state'], 'done')
        self.assertEqual([call[0] for call in plain.calls], ['GET','POST','POST'])
        self.assertEqual({call[3] for call in plain.calls}, {'Bearer fixture-A'})
        self.dns[HOST_A] = [A, '169.254.169.254']
        with self.assertRaises(AssistantError):
            self.registry.discover(pid, True)
        self.assertEqual(len(plain.calls), 3)

    def test_unversioned_network_and_bootstrap_remain_restricted(self):
        from pathlib import Path
        from urllib.parse import urlsplit
        def function(file, name):
            node=next(n for n in ast.parse(file.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name==name)
            scope={'urlsplit':urlsplit}
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(file),'exec'),scope)
            return scope[name]
        from utils.ai_assistant.transport import EndpointPolicy
        project = Path(__file__).resolve().parents[1]
        with self.assertRaises(AssistantError):
            EndpointPolicy([STRATA_HTTP]).destination(STRATA_HTTP)
        guard=function(project/'tools/deploy_user_ai.py','provider_origin')
        self.assertEqual(guard(STRATA_HTTP,existing=True),STRATA_HTTP)
        self.assertEqual(guard(URL_A),URL_A)
        with self.assertRaises(ValueError):
            guard(STRATA_HTTP)
        for value in ('http://192.168.0.15:8080','http://127.0.0.1','http://user@192.168.0.14:8080'):
            with self.assertRaises(ValueError):
                guard(value,existing=True)

    def test_all_working_published_models_must_pass_before_atomic_cutover(self):
        self.a.models.append('zz-second')
        pid,mid=self.activate()
        second=next(m['id'] for m in self.provider(pid)['models'] if m['upstream']=='zz-second')
        self.request('/api/admin/ai/providers/'+pid+'/models',dict(id=second,label='Second',published=True,
                     sort_order=1,context_tokens=32768,revision=1))
        self.request('/api/admin/ai/models/'+second+'/probe',dict(tools=True,reasoning=False,client_key=uuid.uuid4().hex),202)
        for _ in range(2):
            self.worker.run_job(self.claim())
        self.save(pid,revision=1,base_url=URL_B,ca_pem=pem(self.ca_b[0]),api_key='fixture-B')
        self.discover(pid,2)
        self.queue_probe(pid,2,mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.registry.resolve(second)['revision'],1)
        self.b.models.append('zz-second')
        self.discover(pid,2)
        self.queue_probe(pid,2,mid)
        self.worker.run_job(self.claim())
        self.queue_probe(pid,2,second)
        self.worker.run_job(self.claim())
        self.assertEqual(self.provider(pid)['revision'],1)
        self.queue_probe(pid,2,second,tools=True)
        for _ in range(2):
            self.worker.run_job(self.claim())
        self.assertIsNone(self.provider(pid)['candidate'])
        self.assertEqual([self.registry.resolve(model)['revision'] for model in (mid,second)],[2,2])
        self.assertTrue(self.registry.resolve(second)['profile']['tools'])

    def test_worker_rechecks_dns_redirect_and_authentication_and_releases_known_failures(self):
        pid,mid=self.activate()
        self.save(pid,revision=1,base_url=URL_B,ca_pem=pem(self.ca_b[0]),api_key='fixture-B')
        self.discover(pid,2)
        for failure,code in (('dns','PROVIDER_ADDRESS'),('redirect','PROVIDER_ADDRESS'),('auth','PROVIDER_AUTH')):
            with self.subTest(failure=failure):
                self.queue_probe(pid,2,mid)
                job=self.claim()
                count=len(self.b.calls)
                if failure=='dns':
                    self.dns[HOST_B]=[A]
                self.b.redirect=failure=='redirect'
                self.b.key='changed' if failure=='auth' else 'fixture-B'
                self.worker.run_job(job)
                self.assertEqual(len(self.b.calls)-count,int(failure!='dns'))
                self.assertEqual(self.state(job['id'])['error_code'],code)
                self.assertEqual(self.registry.resolve(mid)['revision'],1)
                self.dns[HOST_B]=[B]
                self.b.key='fixture-B'
                self.b.redirect=False

    def test_distinct_resource_groups_run_concurrently_and_address_alias_cannot_split_group(self):
        pid=self.save()
        self.save(base_url='https://'+A+':8443',new_group='alias',status=409)
        other=self.save(base_url=URL_B,new_group='another GPU',ca_pem=pem(self.ca_b[0]),api_key='fixture-B')
        for provider in (pid,other):
            self.discover(provider,1)
            mid=self.provider(provider)['candidate']['models'][0]['id']
            self.queue_probe(provider,1,mid)
        jobs=[self.claim(),self.claim()]
        self.assertEqual(len({j['route']['resource_group'] for j in jobs}),2)
        self.a.barrier=self.b.barrier=threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(self.worker.run_job,jobs))
        self.assertTrue(all(self.state(j['id'])['state']=='done' for j in jobs))

    def test_revocation_after_claim_before_admission_sends_no_http_request(self):
        pid=self.save()
        self.discover(pid,1)
        mid=self.provider(pid)['candidate']['models'][0]['id']
        jid=self.queue_probe(pid,1,mid)
        job=self.claim()
        self.request('/api/admin/ai/providers/'+pid+'/revoke-trust',{'revision':1})
        self.worker.run_job(job)
        self.assertEqual([c[0] for c in self.a.calls],['GET'])
        self.assertEqual(self.state(jid)['error_code'],'PROVIDER_REVOKED')
        self.assertEqual(self.provider(pid)['retired'],1)

    def test_tiny_nonce_probe_cannot_promote_a_candidate_that_cannot_fit_normal_chat(self):
        pid=self.save()
        self.discover(pid,1)
        mid=self.provider(pid)['candidate']['models'][0]['id']
        jid=self.queue_probe(pid,1,mid,context=4096)
        self.assertIsNone(self.claim())
        self.assertEqual(self.state(jid)['error_code'],'PROVIDER_CONTEXT')
        self.assertEqual(self.provider(pid)['revision'],0)
        self.assertEqual([c[0] for c in self.a.calls],['GET'])

    def test_worker_legacy_direct_fallback_cannot_reuse_8080_or_legacy_secret_on_a_new_peer(self):
        # Authentic server leases, then corrupt the private packet in this worker-only negative test.
        self.login(2)
        jid=self.submit()
        job=self.claim()
        del job['route'], job['protocol']
        self.worker.run_job(job)
        self.assertEqual(self.state(jid)['error_code'],'PROVIDER_ADDRESS')
        self.assertEqual(self.legacy.calls,[])
        self.login(1)
        pid,mid=self.activate()
        _,jid=self.queue_chat(mid)
        job=self.claim()
        job['route']['legacy_worker_key']=True
        count=len(self.a.calls)
        self.worker.run_job(job)
        self.assertEqual(self.state(jid)['error_code'],'PROVIDER_ADDRESS')
        self.assertEqual(len(self.a.calls),count)

    def test_new_adapter_cannot_hide_or_downgrade_an_existing_published_reasoning_contract(self):
        self.a.models=[STRATA_MODEL]
        pid,mid=self.activate()
        active=self.provider(pid)['models'][0]
        data=dict(id=mid,label='Custom Qwen',published=True,sort_order=0,context_tokens=32768,revision=1,
                  profile_revision=active['profile_revision'],reasoning_levels=['max'],reasoning_default='max')
        self.request('/api/admin/ai/providers/'+pid+'/models',data)
        self.request('/api/admin/ai/models/'+mid+'/probe',dict(tools=False,reasoning=True,client_key=uuid.uuid4().hex),202)
        for _ in range(2):
            self.worker.run_job(self.claim())
        self.b.models=[STRATA_MODEL]
        self.save(pid,revision=1,base_url=URL_B,adapter='strata',api_key='fixture-B',ca_pem=pem(self.ca_b[0]))
        self.discover(pid,2)
        self.assertEqual(self.provider(pid)['candidate']['models'][0]['profile']['enabled_levels'],[])
        self.queue_probe(pid,2,mid)
        self.worker.run_job(self.claim())
        self.assertEqual(self.registry.resolve(mid)['profile']['levels'],['max'])
        self.assertEqual(self.provider(pid)['revision'],1)
