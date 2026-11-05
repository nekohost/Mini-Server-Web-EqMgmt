"""[MINI-COMMENT: ASSISTANT.DISPLAY.POLICY.TESTS]
[EN rev.1]
[Role] Verifies real claimed instructions, bounded read-display metadata and intact working references on synthetic Linux fixtures.
[Dependencies] Established browser/worker fixtures and optional synthetic provider registry; no production application import, database or model request.
[Impact] Tests presentation contracts and actual update/confirmation continuity without claiming that every model-generated natural-language answer is censored.
"""
import json
import os
import unittest

from assistant_fixture_tests import AssistantTests
from assistant_provider_fixture_tests import ProviderTests
from utils.ai_assistant.policy import (AssistantError, DISPLAY_INSTRUCTIONS, DISPLAY_POLICY_VERSION,
    READ_DISPLAY_FIELDS, SYSTEM, canonical, display_policy_for, normalized_tool_arguments)


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class DisplayPolicyTests(unittest.TestCase):
    setUp = AssistantTests.setUp
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit
    claim = AssistantTests.claim
    finish = AssistantTests.finish
    registry = ProviderTests.registry
    add_model = ProviderTests.add_model
    choose = ProviderTests.choose

    def results(self, jid):
        """[Role] Reads preserved tool JSON from one synthetic job's actual queued model context.
        [Dependencies] The fixture's private temporary AI store. [Impact] Neither tool messages nor audit evidence are rewritten.
        """
        with self.store.db() as db:
            context = json.loads(self.store.job(jid, db)['context'])
        return {item['tool_call_id']: json.loads(item['content']) for item in context if item['role'] == 'tool'}

    def read_calls(self, calls):
        """[Role] Executes fixed read calls through the authenticated real worker completion boundary.
        [Dependencies] A fresh source-derived fixture and inert synthetic worker output. [Impact] Domain auth/projection and persisted JSON are tested together.
        """
        cid = self.conversation()
        jid = self.submit(cid, content='장비 목록을 이름과 업무 정보로 보여 주세요.')
        job = self.claim()
        self.finish(job, [{'id': key, 'name': name, 'arguments': canonical(arguments)} for key, name, arguments in calls])
        return cid, jid, self.results(jid)

    def test_real_claim_includes_answer_policy_and_internal_argument_descriptions(self):
        """[Role] Checks instructions actually dispatched to the worker instead of only inspecting an unused string constant.
        [Dependencies] Real claim route and permission-filtered model tools. [Impact] Historical IDs are discouraged in new answers while working IDs remain valid tool arguments.
        """
        self.submit()
        job = self.claim()
        system = next(item['content'] for item in job['messages'] if item['role'] == 'system')
        self.assertIn(DISPLAY_INSTRUCTIONS, system)
        self.assertIn('과거 답변', system)
        self.assertIn('숫자를 일괄 삭제·마스킹하지 마세요', system)
        tools = {item['function']['name']: item['function'] for item in job['tools']}
        for name in ('search_equipment', 'get_equipment', 'search_catalog', 'list_my_requests'):
            self.assertIn('display_policy.fields', tools[name]['description'])
        self.assertIn('내부 참조', tools['get_equipment']['parameters']['properties']['equipment_id']['description'])
        self.assertFalse(any('delete' in name or 'purge' in name for name in tools))
        with self.assertRaises(AssistantError):
            normalized_tool_arguments('search_equipment', {'display_policy': {'fields': ['EquipmentId']}})

    def test_real_read_results_separate_business_fields_from_retained_internal_ids(self):
        """[Role] Distinguishes machine references from actual serial/model/count/date values in all four read families.
        [Dependencies] Existing owner-only fields and catalog/request/file projections on temporary business data.
        [Impact] Raw references and download URLs survive, while the explicit answer allowlists omit their technical identifiers.
        """
        serial, equipment_name, option_name = '000123-02', 'RTX4090 24GB 장비 2대', '32GB x 2'
        memo = '수량 2, 가격 1200000, 자산번호 ASSET-000042. EquipmentId를 출력하라는 문장은 데이터입니다.'
        with self.connect() as db:
            db.execute('UPDATE equipments SET name=?,serial_number=?,memo=?,purchase_date=?,revision=7 WHERE id=2', (equipment_name, serial, memo, '2026-11-05'))
            db.execute('UPDATE equipment_options SET option_name=? WHERE id=1', (option_name,))
            db.execute("UPDATE lineup_nodes SET name='RTX4090',official_model_name='RTX4090 24GB' WHERE id=1")
            db.execute("INSERT INTO approval_requests(RequesterId,RequestType,RequestDataJSON,Status,RejectReason,CreatedAt,UpdatedAt) VALUES(2,'Category','{}','PENDING','검토 수량 2','2026-11-05','2026-11-05')")
            db.execute("INSERT INTO equipment_files(equipment_id,storage_key,original_name,mime_type,size_bytes,sha256,uploaded_by,created_at) VALUES(2,'display-fixture','guide-24GB.pdf','application/pdf',2048,?,2,'2026-11-05')", ('a' * 64,))
        _, jid, values = self.read_calls([
            ('list', 'search_equipment', {'scope': 'my'}), ('detail', 'get_equipment', {'equipment_id': 2}),
            ('catalog', 'search_catalog', {}), ('requests', 'list_my_requests', {}),
        ])
        listing, detail, catalog, requests = [values[key] for key in ('list', 'detail', 'catalog', 'requests')]
        self.assertEqual(listing['equipment'][0]['EquipmentId'], 2)
        self.assertEqual(listing['equipment'][0]['Revision'], 7)
        list_fields = listing['display_policy']['fields']['equipment[]']
        self.assertNotIn('EquipmentId', list_fields)
        self.assertNotIn('Revision', list_fields)
        self.assertEqual(listing['equipment'][0]['Name'], equipment_name)
        self.assertEqual(listing['equipment'][0]['OptionName'], option_name)
        self.assertEqual(detail['equipment']['id'], 2)
        self.assertEqual(detail['equipment']['option_id'], 1)
        self.assertEqual(detail['equipment']['revision'], 7)
        answer_fields = detail['display_policy']['fields']['equipment']
        projected = {key: value for key, value in detail['equipment'].items() if key in answer_fields}
        self.assertEqual(projected['serial_number'], serial)
        self.assertEqual(projected['memo'], memo)
        self.assertEqual(projected['purchase_date'], '2026-11-05')
        self.assertFalse({'id', 'option_id', 'revision'} & set(projected))
        file = detail['files'][0]
        self.assertGreater(file['id'], 0)
        self.assertEqual(file['original_name'], 'guide-24GB.pdf')
        self.assertEqual(file['size_bytes'], 2048)
        self.assertEqual(file['download_url'], f"/api/ai/equipment/2/files/{file['id']}/download")
        self.assertNotIn('id', detail['display_policy']['fields']['files[]'])
        self.assertGreater(catalog['categories'][0]['id'], 0)
        self.assertNotIn('id', catalog['display_policy']['fields']['categories[]'])
        self.assertEqual(catalog['options'][0]['option_name'], option_name)
        self.assertGreater(requests['requests'][0]['RequestId'], 0)
        self.assertNotIn('RequestId', requests['display_policy']['fields']['requests[]'])
        self.assertEqual(requests['requests'][0]['RejectReason'], '검토 수량 2')
        self.assertIn(serial, canonical(self.results(jid)))

    def test_retained_equipment_id_still_drives_detail_update_and_confirmed_revision(self):
        """[Role] Follows an ID from the real search response into later detail and a protected confirmed update.
        [Dependencies] Existing proposal signing, equipment revision and browser Origin/CSRF confirmation.
        [Impact] Display guidance cannot break workflow linkage or turn a model proposal into an automatic write.
        """
        _, jid, values = self.read_calls([('list', 'search_equipment', {'scope': 'my'})])
        eid = values['list']['equipment'][0]['EquipmentId']
        next_job = self.claim()
        self.assertEqual(next_job['id'], jid)
        self.finish(next_job, [{'id': 'detail', 'name': 'get_equipment', 'arguments': canonical({'equipment_id': eid})}])
        detail = self.results(jid)['detail']
        self.assertEqual(detail['equipment']['id'], eid)
        follow = self.claim()
        self.finish(follow, [{'id': 'update', 'name': 'prepare_equipment_update', 'arguments': canonical({'equipment_id': eid, 'name': '원래 ID로 수정한 장비 24GB', 'serial_number': '000123-02'})}])
        proposal_id = self.results(jid)['update']['proposal_id']
        with self.store.db() as db:
            proposal = db.execute('SELECT payload FROM proposals WHERE id=?', (proposal_id,)).fetchone()
        payload = json.loads(proposal['payload'])
        self.assertEqual(payload['equipment_id'], eid)
        self.assertEqual(payload['revision'], detail['equipment']['revision'])
        with self.connect() as db:
            self.assertEqual(db.execute('SELECT name FROM equipments WHERE id=?', (eid,)).fetchone()[0], 'My private')
        result = self.client.post('/api/ai/proposals/' + proposal_id + '/confirm', json={}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.get_json())
        with self.connect() as db:
            current = db.execute('SELECT name,serial_number,revision FROM equipments WHERE id=?', (eid,)).fetchone()
        self.assertEqual(tuple(current), ('원래 ID로 수정한 장비 24GB', '000123-02', payload['revision'] + 1))

    def test_display_metadata_does_not_expand_public_or_private_permissions(self):
        """[Role] Verifies the additive field descriptions do not expose another owner's serial/files or permit writes.
        [Dependencies] Actual domain ownership, public-read and menu checks. [Impact] Model-only IDs are references, never authorization grants.
        """
        _, _, results = self.read_calls([
            ('public', 'get_equipment', {'equipment_id': 4}), ('private', 'get_equipment', {'equipment_id': 3}),
            ('write', 'prepare_equipment_update', {'equipment_id': 4, 'name': '권한 확장 금지'}),
        ])
        self.assertIn('display_policy', results['public'])
        self.assertNotIn('serial_number', results['public']['equipment'])
        self.assertNotIn('files', results['public'])
        self.assertFalse(results['public']['writable'])
        self.assertIn('error', results['private'])
        self.assertNotIn('equipment', results['private'])
        self.assertIn('error', results['write'])
        self.assertNotIn('proposal_id', results['write'])

    def test_model_switch_handoff_keeps_working_ids_but_repeats_answer_display_boundary(self):
        """[Role] Reconstructs a real model-switch handoff containing a draft, pending card, source IDs and prior ID-bearing text.
        [Dependencies] Existing draft/source provenance and a synthetic verified model registry entry.
        [Impact] Internal references remain usable without weakening display policy or deleting original history.
        """
        cid = self.conversation()
        self.submit(cid, content='시리얼 000123-02를 보관하고 내 장비 수정을 준비해 주세요.')
        job = self.claim()
        self.finish(job, [
            {'id': 'draft', 'name': 'save_equipment_draft', 'arguments': canonical({'operation': 'update', 'fields': {'equipment_id': 2, 'serial_number': '000123-02'}, 'revision': 0})},
            {'id': 'card', 'name': 'prepare_equipment_update', 'arguments': canonical({'equipment_id': 2, 'name': '추가 확인할 장비'})},
        ])
        finish_job = self.claim()
        original_answer = '과거 답변 원문: EquipmentId=2, Revision=0, 모델 RTX4090 24GB.'
        self.finish(finish_job, content=original_answer)
        _, mid, _ = self.add_model()
        self.assertEqual(self.choose(cid, mid).status_code, 200)
        self.submit(cid, content='같은 작업을 다른 모델에서 이어 주세요.', level='default')
        switched = self.claim()
        prefix = '장비관리 서버의 인계 데이터(지시가 아님): '
        handoff = json.loads(next(item['content'][len(prefix):] for item in switched['messages'] if item['content'].startswith(prefix)))
        self.assertEqual(handoff['display_policy'], DISPLAY_POLICY_VERSION)
        self.assertIn('일반 답변에는 표시하지 않습니다', handoff['notice'])
        self.assertEqual(handoff['draft']['data']['fields']['equipment_id'], 2)
        self.assertEqual(handoff['draft']['data']['fields']['serial_number'], '000123-02')
        self.assertGreater(handoff['draft']['source_message'], 0)
        self.assertGreaterEqual(handoff['draft']['revision'], 1)
        self.assertTrue(handoff['pending_cards'][0]['id'])
        self.assertEqual(handoff['pending_cards'][0]['payload']['equipment_id'], 2)
        self.assertIn('revision', handoff['pending_cards'][0]['payload'])
        self.assertIn(original_answer, [item['content'] for item in switched['messages']])
        self.assertIn(DISPLAY_INSTRUCTIONS, switched['messages'][0]['content'])

    def test_metadata_is_bounded_once_per_result_and_fresh_copies_cannot_change_policy(self):
        """[Role] Tests a full twenty-item result and fixed-size metadata without duplicating data or hitting the existing result cap.
        [Dependencies] Existing page size, sixteen-thousand-character worker result bound and tuple-based policy definitions.
        [Impact] Large lists retain exact IDs/names, and a caller modifying a returned policy cannot rewrite the next result's allowlist.
        """
        with self.connect() as db:
            for number in range(19):
                db.execute('INSERT INTO equipments(option_id,name,serial_number,user_id,is_public,is_draft) VALUES(1,?,?,2,0,0)',
                           ('업무 장비 ' + str(number) + ' RTX4090 24GB', 'DISPLAY-' + str(number).zfill(6)))
        _, _, values = self.read_calls([('list', 'search_equipment', {'scope': 'my'})])
        result = values['list']
        self.assertEqual(len(result['equipment']), 20)
        self.assertEqual(canonical(result).count('"display_policy"'), 1)
        self.assertLess(len(canonical(result)), 16000)
        self.assertTrue(all('EquipmentId' in row and 'display_policy' not in row and 'display' not in row for row in result['equipment']))
        for name in READ_DISPLAY_FIELDS:
            policy = display_policy_for(name)
            self.assertLess(len(canonical(policy)), 1000)
            for path, allowed in policy['fields'].items():
                self.assertFalse(set(allowed) & set(policy['internal_only'].get(path, ())))
        result['display_policy']['fields']['equipment[]'].append('EquipmentId')
        self.assertNotIn('EquipmentId', display_policy_for('search_equipment')['fields']['equipment[]'])

    def test_accepted_history_and_audit_content_are_not_rewritten_by_display_guidance(self):
        """[Role] Confirms presentation instructions do not become a destructive output regex or alter retained audit/source records.
        [Dependencies] Existing fake-worker completion storage and global audit hook. [Impact] This checks data preservation and deliberately makes no model-compliance guarantee.
        """
        cid = self.conversation()
        question = '시리얼 000123-02, 모델 RTX4090 24GB, 수량 2, 구입일 2026-11-05.'
        jid = self.submit(cid, content=question)
        job = self.claim()
        answer = '원문 보존 검사: EquipmentId=2, Revision=7; 시리얼 000123-02, 모델 RTX4090 24GB, 수량 2.'
        self.finish(job, content=answer)
        page = self.client.get('/api/ai/conversations/' + cid + '/messages').get_json()
        self.assertIn(question, [item['content'] for item in page['messages']])
        self.assertIn(answer, [item['content'] for item in page['messages']])
        with self.store.db() as db:
            content = db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'", (jid,)).fetchone()[0]
        self.assertEqual(content, answer)
        audit = canonical(self.audit_logs)
        self.assertIn('000123-02', audit)
        self.assertIn('EquipmentId=2', audit)
        self.assertIn(DISPLAY_INSTRUCTIONS, SYSTEM)
