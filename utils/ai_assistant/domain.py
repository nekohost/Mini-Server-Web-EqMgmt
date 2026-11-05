"""[MINI-COMMENT: ASSISTANT.DOMAIN]
[EN rev.5]
[Role] Adapts only ordinary-user equipment services to reads and confirmed mutations.
[Dependencies] Existing roadmap validation/status, catalog/option services and tracked DB connections.
[Impact] Actors are owner-scoped users; read results retain exact working references and business values while adding one bounded display allowlist. Reviewed equipment values and stored values share one normalization contract.
"""
import json
import secrets
import time

from utils import roadmap_equipment as equipment
from utils.roadmap_validation import equipment_fields, InputError
from utils.catalog_request_service import submit_catalog_request
from utils.lineup_node_service import save_option, LineupNodeError
from .policy import AssistantError, TOOL_MAP, canonical, digest, identity, mac, text, validate_schema, normalized_tool_arguments, display_policy_for
from .web_search import WebSearchError, MAX_SEARCHES, public_searches

WRITE_MENUS = ('my_equipment',)
READ_MENUS = ('my_equipment','public_equipment')


class Domain:
    """[Role] Receives existing connection/maintenance dependencies without importing the app."""
    def __init__(self, connect, secret, maintenance, search_service=None):
        """[Role] Keeps credentials and DB gating in the trusted equipment-server process.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        self.connect,self.secret,self.maintenance=connect,secret,maintenance
        self.search_service=search_service

    def actor(self, db, uid, binding=None):
        """[MINI-COMMENT: ASSISTANT.ACTOR]
        [EN rev.1]
        [Role] Revalidates current session/account and projects a user-only actor from server data.
        [Dependencies] users.SessionToken and role_menu_permissions; opaque browser claims are not trusted.
        [Impact] Admin status never broadens assistant data scope or directly approves catalog changes.
        """
        maintenance=self.maintenance()
        if maintenance['state']!='NORMAL':
            raise AssistantError('점검 중입니다. 잠시 후 다시 이용해 주세요.',503)
        row=db.execute('SELECT UserId,LoginId,Role,SessionToken,IsDeleted,IsDeactivated,CreatedAt FROM users WHERE UserId=?',(identity(uid),)).fetchone()
        if row is None or row['IsDeleted']=='Y' or row['IsDeactivated']=='Y':
            raise AssistantError('사용할 수 없는 계정입니다.',403)
        current=dict(row)
        if current['Role'] not in ('user','admin') or not current.get('SessionToken'):
            raise AssistantError('로그인을 확인해 주세요.',401)
        if not isinstance(current.get('CreatedAt'),str) or not current['CreatedAt'].strip():
            raise AssistantError('계정 생성 식별정보를 확인해야 합니다. 관리자에게 문의해 주세요.',409)
        account_key=digest(['account',uid,current['CreatedAt']])
        actual=self.binding(uid,current['SessionToken'],maintenance)
        if binding is not None and not secrets.compare_digest(binding,actual):
            raise AssistantError('로그인 작업 권한이 만료되었습니다.',401)
        ai=db.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role=? AND MenuCode='equipment_ai'",(current['Role'],)).fetchone()
        if ai is None or ai[0]!=1:
            raise AssistantError('AI 도우미 접근 권한이 없습니다.',403)
        # Use current user-role menu grants, rather than the admin bypass in the original UI.
        allowed={r[0] for r in db.execute("SELECT MenuCode FROM role_menu_permissions WHERE Role='user' AND IsAllowed=1")}
        return {'UserId':uid,'LoginId':current['LoginId'],'Role':'user','menus':allowed,'binding':actual,'account_key':account_key}

    def binding(self, uid, token, maintenance=None):
        """[Role] Binds a login to the external maintenance revision, invalidating pre-restore delegations.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        state=maintenance if maintenance is not None else self.maintenance()
        return mac(self.secret,'session',uid,token,state.get('revision',0))

    def require_menu(self, actor, *menus):
        """[Role] Enforces business capabilities independently of the AI menu grant.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if not any(m in actor['menus'] for m in menus):
            raise AssistantError('이 기능에 접근할 권한이 없습니다.',403)

    def own(self, db, actor, eid, write=False):
        """[Role] Applies existing private/public/draft rules and menu checks for each record.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        row=equipment.require_equipment(db,identity(eid),actor,write=write)
        if row['user_id']==actor['UserId']:
            self.require_menu(actor,'my_equipment')
        else:
            self.require_menu(actor,'public_equipment')
        return row

    def tools(self, actor, web_search_allowed=False):
        """[Role] Advertises only available user tools; execution checks the same permissions again.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        names=set()
        if actor['menus'] & set(READ_MENUS):
            names.update(('search_equipment','get_equipment','search_catalog','prepare_csv_export','prepare_catalog_request','prepare_option_request'))
        if 'my_equipment' in actor['menus']:
            names.update(('prepare_equipment_create','prepare_equipment_update','prepare_equipment_status'))
        if 'my_approvals' in actor['menus']:
            names.update(('list_my_requests','prepare_catalog_request','prepare_option_request'))
        names.add('prepare_preferences')
        if web_search_allowed and self.search_service is not None and self.search_service.available:
            names.add('web_search')
        return [dict(type='function',function=TOOL_MAP[n]) for n in sorted(names)]

    def read_or_prepare(self, name, args, job, store):
        """[MINI-COMMENT: ASSISTANT.DOMAIN.DISPATCH]
        [EN rev.3]
        [Role] Routes a canonically validated tool call to a fixed user operation.
        [Dependencies] Shared normalized_tool_arguments; current actor, account and tool permissions.
        [Impact] Empty optional read filters agree with HTTP validation without weakening writes or owner scope; one additive display policy separates answer fields from retained tool-linkage IDs without duplicating rows or rewriting source values.
        """
        if name not in TOOL_MAP:
            raise AssistantError('허용되지 않은 작업입니다.',403)
        args=normalized_tool_arguments(name,args)
        supersedes=args.pop('supersedes_proposal',None)
        db=self.connect()
        try:
            actor=self.actor(db,job['owner'],job['binding'])
            if actor['account_key']!=job['account_key']:
                raise AssistantError('계정 식별정보가 변경되었습니다.',401)
            if time.time()>job['expires'] or job['cancel']:
                raise AssistantError('로그인 작업 권한이 만료되었거나 취소되었습니다.',401)
            search_allowed=json.loads(job.get('route_snapshot') or '{}').get('web_search_allowed') is True
            if name=='web_search' and not search_allowed:
                raise WebSearchError('WEB_SEARCH_DISABLED')
            if name=='web_search' and (self.search_service is None or not self.search_service.available):
                raise WebSearchError('WEB_SEARCH_UNAVAILABLE')
            if name not in {t['function']['name'] for t in self.tools(actor,search_allowed)}:
                raise AssistantError('허용되지 않은 작업입니다.',403)
            if name=='web_search':
                context=json.loads(job['context'])
                if len(public_searches(context))>=MAX_SEARCHES:
                    raise WebSearchError('WEB_SEARCH_LIMIT')
                # Detailed private values must never become a later web-search query in this turn.
                for entry in context:
                    if entry.get('role')=='tool':
                        value=json.loads(entry['content'])
                        equipment_value=value.get('equipment') if isinstance(value,dict) else None
                        if isinstance(equipment_value,dict) and ('serial_number' in equipment_value or 'memo' in equipment_value):
                            raise WebSearchError('WEB_SEARCH_BLOCKED')
                private=list(db.execute('SELECT serial_number,memo FROM equipments WHERE user_id=? LIMIT 1001',(actor['UserId'],)))
                if len(private)>1000:
                    raise WebSearchError('WEB_SEARCH_BLOCKED')
                sensitive=[actor['LoginId'],*[v for row in private for v in row if v]]
                db.close();db=None
                result=self.search_service.search(args['query'],args.get('max_results',5),sensitive)
                # Search I/O holds no business DB connection/transaction; revalidate the actor afterwards.
                db=self.connect()
                self.actor(db,job['owner'],job['binding'])
                return result
            if name=='search_equipment':
                scope=args.get('scope','my')
                self.require_menu(actor,'public_equipment' if scope=='public' else 'my_equipment')
                query={'type':'public' if scope=='public' else 'my','is_draft':'1' if scope=='draft' else '0',
                       'keyword':args.get('query',''),'page':str(args.get('page',1)),'per_page':'20','due':args.get('due','')}
                if args.get('status'):
                    query['status']=args['status']
                result=equipment.list_equipment(db,query,actor)
                # Project the list rather than returning internal user IDs or arbitrary DB columns.
                rows=result.get('data',result.get('equipments',result.get('items',[]))) if isinstance(result,dict) else result
                return {'equipment':[{k:v for k,v in r.items() if k in ('EquipmentId','Name','ModelName','FullModelName','OfficialModelName','DisplayModelName','OptionName','Status','Revision','WarrantyEndDate','ReplacementDueDate')} for r in rows],
                        'page':args.get('page',1),'scope':scope,'total':result['total'],'pages':result['pages'],'per_page':20,
                        'display_policy':display_policy_for(name)}
            if name=='get_equipment':
                row=self.own(db,actor,args['equipment_id'])
                owned=row['user_id']==actor['UserId']
                fields=('id','name','option_id','status','revision','is_public','is_draft','purchase_date','warranty_end_date','replacement_due_date')
                result={'equipment':{k:row[k] for k in fields},'writable':owned,'display_policy':display_policy_for(name)}
                if owned:
                    result['equipment'].update(serial_number=row['serial_number'],memo=row['memo'])
                    result['files']=[dict(r) for r in db.execute('SELECT id,original_name,mime_type,size_bytes FROM equipment_files WHERE equipment_id=? AND deleted_at IS NULL ORDER BY id DESC LIMIT 50',(row['id'],))]
                    for item in result['files']:
                        item['download_url']=f"/api/ai/equipment/{row['id']}/files/{item['id']}/download"
                result['transitions']=[s for s in equipment.TRANSITIONS.get(row['status'],()) if s!='DISPOSED'] if owned and not row['is_draft'] else []
                return result
            if name=='search_catalog':
                self.require_menu(actor,*READ_MENUS)
                needle='%'+args.get('query','').replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                return {
                    'display_policy':display_policy_for(name),
                    'categories':[dict(r) for r in db.execute("SELECT CategoryId AS id,Name AS name FROM categories WHERE IsApproved=1 AND Name LIKE ? ESCAPE '\\' LIMIT 10",(needle,))],
                    'manufacturers':[dict(r) for r in db.execute("SELECT ManufacturerId AS id,Name AS name FROM manufacturers WHERE IsApproved=1 AND Name LIKE ? ESCAPE '\\' LIMIT 10",(needle,))],
                    'nodes':[dict(r) for r in db.execute("SELECT id,name,parent_id,category_id,manufacturer_id FROM lineup_nodes WHERE status='APPROVED' AND name LIKE ? ESCAPE '\\' LIMIT 20",(needle,))],
                    'options':[dict(r) for r in db.execute("SELECT o.id,o.lineup_node_id,o.option_name,n.name AS model FROM equipment_options o JOIN lineup_nodes n ON n.id=o.lineup_node_id WHERE o.status='APPROVED' AND n.status='APPROVED' AND (o.option_name LIKE ? ESCAPE '\\' OR n.name LIKE ? ESCAPE '\\') LIMIT 20",(needle,needle))]}
            if name=='list_my_requests':
                self.require_menu(actor,'my_approvals')
                status=args.get('status','')
                return {'requests':[dict(r) for r in db.execute('SELECT RequestId,RequestType,Status,RejectReason,CreatedAt,UpdatedAt FROM approval_requests WHERE RequesterId=? AND (?=\'\' OR Status=?) ORDER BY RequestId DESC LIMIT 20',(actor['UserId'],status,status))],
                        'display_policy':display_policy_for(name)}
            before={}
            operation=name.removeprefix('prepare_')
            payload=dict(args)
            if operation in ('equipment_create','equipment_update'):
                self.require_menu(actor,*WRITE_MENUS)
                if operation=='equipment_update':
                    before=self.own(db,actor,payload.pop('equipment_id'),True)
                    payload['equipment_id']=before['id']
                    payload['revision']=before['revision']
                normalized=self.validate_equipment(db,actor,payload,before)
                payload={**normalized,**({k:payload[k] for k in ('equipment_id','revision')} if operation=='equipment_update' else {})}
                before={**before,'_selected_option':self.option_snapshot(db,payload.get('option_id',before.get('option_id')))}
            elif operation=='equipment_status':
                self.require_menu(actor,*WRITE_MENUS)
                before=self.own(db,actor,payload['equipment_id'],True)
                if before['is_draft'] or payload['status'] not in equipment.TRANSITIONS.get(before['status'],()):
                    raise AssistantError('허용되지 않는 상태 변경입니다.',409)
                payload['revision']=before['revision']
            elif operation in ('catalog_request','option_request'):
                self.require_menu(actor,'my_equipment','public_equipment','my_approvals')
                if operation=='catalog_request':
                    if payload['kind']!='node' and set(payload)-{'kind','name'}:
                        raise AssistantError('분류/제조사 신청에는 이름만 입력해 주세요.')
                elif 'specs_json' in payload:
                    payload['specs']=json.loads(payload.pop('specs_json'))
                    if not isinstance(payload['specs'],dict) or len(canonical(payload['specs']))>16000:
                        raise AssistantError('옵션 사양 형식을 확인해 주세요.')
            elif operation=='preferences':
                if not payload:
                    raise AssistantError('변경할 설정을 선택해 주세요.')
                before=self.preferences(db,actor)
            elif operation=='csv_export':
                self.require_menu(actor,'my_equipment' if payload['scope']=='my' else 'public_equipment')
            else:
                raise AssistantError('허용되지 않은 작업입니다.',403)
            return store.proposal(job,operation,payload,before,self.secret,supersedes)
        finally:
            if db is not None:
                db.close()

    def validate_equipment(self, db, actor, payload, old):
        """[Role] Uses the returned shared normalization for the exact reviewed and stored equipment snapshot.
        [Dependencies] Merged existing fields, equipment_fields and owner-only pending-option rules.
        [Impact] Date/serial whitespace cannot bypass the normal UI's comparison or storage contract.
        """
        keys=('name','option_id','serial_number','purchase_date','warranty_end_date','replacement_due_date','memo','is_draft','is_public')
        normalized=equipment_fields({k:payload.get(k,old.get(k)) for k in keys if k in payload or k in old})
        name=text(normalized.get('name',''),200)
        oid=identity(normalized.get('option_id'))
        draft=normalized.get('is_draft',False)
        if old and not old['is_draft'] and draft:
            raise AssistantError('정식 장비를 임시저장으로 되돌릴 수 없습니다.',409)
        option=db.execute('SELECT o.status,o.requested_by,n.status AS node_status FROM equipment_options o JOIN lineup_nodes n ON n.id=o.lineup_node_id WHERE o.id=?',(oid,)).fetchone()
        if option is None or (option['status']!='APPROVED' and not (draft and option['status']=='PENDING' and option['requested_by']==actor['UserId'])) or option['node_status']!='APPROVED':
            raise AssistantError('승인된 옵션 또는 본인의 임시저장용 옵션을 선택해 주세요.',409)
        serial=normalized.get('serial_number') or None
        if serial and db.execute('SELECT 1 FROM equipments WHERE serial_number=? AND id<>?',(serial,old.get('id',0))).fetchone():
            raise AssistantError('이미 등록된 시리얼 번호입니다.',409)
        dates={k:normalized.get(k) or None for k in ('purchase_date','warranty_end_date','replacement_due_date')}
        if dates['purchase_date'] and any(v and v<dates['purchase_date'] for k,v in dates.items() if k!='purchase_date'):
            raise AssistantError('보증/교체 기한은 구입일보다 빠를 수 없습니다.')
        return {'name':name,'option_id':oid,'serial_number':serial,**dates,'memo':normalized.get('memo',''),
                'is_draft':bool(draft),'is_public':False if draft else bool(normalized.get('is_public',False))}

    def option_snapshot(self, db, option_id):
        """[Role] Binds reviewed catalog meaning as well as its ID, detecting renames/spec changes before commit.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        row=db.execute('SELECT o.id,o.option_name,o.specs_json,o.status,n.name AS model,n.official_model_name,n.status AS node_status FROM equipment_options o JOIN lineup_nodes n ON n.id=o.lineup_node_id WHERE o.id=?',(identity(option_id),)).fetchone()
        if row is None:
            raise AssistantError('옵션을 찾을 수 없습니다.',404)
        return dict(row)

    def preferences(self, db, actor):
        """[Role] Loads only this user's settings; unknown existing keys are preserved on writes.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        row=db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=?',(actor['UserId'],)).fetchone()
        try:
            value=json.loads(row[0] or '{}') if row else {}
            return value if isinstance(value,dict) else {}
        except ValueError:
            return {}

    def execute(self, proposal, job):
        """[MINI-COMMENT: ASSISTANT.CONFIRM.TRANSACTION]
        [EN rev.1]
        [Role] Executes an immutable owner-confirmed operation once, with its receipt in the same transaction.
        [Dependencies] Existing audit_logs and BEGIN IMMEDIATE; caller checks browser CSRF and proposal signature.
        [Impact] A cross-DB/UI failure cannot repeat a committed mutation; no equipment schema changes are needed.
        """
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            actor=self.actor(db,job['owner'])
            if actor['account_key']!=job['account_key']:
                raise AssistantError('계정 식별정보가 변경되었습니다.',401)
            pid=proposal['id']
            target=int(pid[:15],16)
            fingerprint=digest([pid,proposal['operation'],proposal['payload'],proposal['before_json']])
            old=db.execute("SELECT NewValue FROM audit_logs WHERE ActorId=? AND Action='AI_EXECUTE' AND TargetTable='ai_operations' AND TargetId=? ORDER BY AuditId DESC LIMIT 1",(actor['UserId'],target)).fetchone()
            if old:
                receipt=json.loads(old[0])
                if receipt.get('proposal_id')!=pid or receipt.get('hash')!=fingerprint:
                    raise AssistantError('실행 기록이 일치하지 않습니다.',409)
                db.rollback()
                return {**receipt['result'],'replayed':True}
            actor=self.actor(db,job['owner'],job['binding'])
            if proposal['expires']<time.time() or job['expires']<time.time() or proposal['state']!='pending' or job['cancel']:
                raise AssistantError('확인 권한이 만료되었거나 취소되었습니다.',409)
            data=json.loads(proposal['payload'])
            before=json.loads(proposal['before_json'])
            expected=mac(self.secret,pid,job['id'],job['owner'],job['binding'],proposal['operation'],data,before,proposal['expires'])
            if not secrets.compare_digest(expected,proposal['signature']):
                raise AssistantError('확인 내용이 일치하지 않습니다.',409)
            operation=proposal['operation']
            result=self.mutate(db,actor,operation,data,before)
            receipt={'proposal_id':pid,'hash':fingerprint,'result':result}
            db.execute('INSERT INTO audit_logs(ActorId,ActorLoginId,TargetTable,TargetId,Action,OldValue,NewValue,CreatedAt) VALUES(?,?,?,?,?,?,?,?)',
                (actor['UserId'],actor['LoginId'],'ai_operations',target,'AI_EXECUTE',canonical({'operation':operation,'before':before}),canonical(receipt),equipment.utc_now()))
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def mutate(self, db, actor, operation, data, before):
        """[Role] Uses a fixed mutation registry inside the caller's writer transaction; never commits itself.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if operation in ('equipment_create','equipment_update','equipment_status'):
            self.require_menu(actor,*WRITE_MENUS)
        if operation in ('equipment_update','equipment_status'):
            old=self.own(db,actor,data['equipment_id'],True)
            if old['revision']!=data['revision']:
                raise AssistantError('장비가 변경되었습니다. 새 확인 내용을 준비해 주세요.',409)
        if operation=='equipment_status':
            result=equipment.change_status(db,old['id'],actor,{'status':data['status'],'reason':data['reason'],'revision':data['revision']})
            return {'equipment_id':old['id'],**result,'message':'장비 상태를 변경했습니다.'}
        if operation in ('equipment_create','equipment_update'):
            if self.option_snapshot(db,data.get('option_id',before.get('option_id')))!=before.get('_selected_option'):
                raise AssistantError('카탈로그 정보가 변경되었습니다. 새 확인 내용을 준비해 주세요.',409)
            values=self.validate_equipment(db,actor,data,old if operation.endswith('update') else {})
            fields=('name','option_id','serial_number','purchase_date','warranty_end_date','replacement_due_date','memo','is_draft','is_public')
            if operation=='equipment_create':
                cursor=db.execute('INSERT INTO equipments('+','.join(fields)+',user_id,status,created_at,updated_at) VALUES('+','.join('?' for _ in range(len(fields)+4))+')',
                    [*[values[f] for f in fields],actor['UserId'],'ACTIVE',equipment.utc_now(),equipment.utc_now()])
                eid=cursor.lastrowid
            else:
                eid=old['id']
                result=db.execute('UPDATE equipments SET '+','.join(f+'=?' for f in fields)+',revision=revision+1,updated_at=? WHERE id=? AND user_id=? AND revision=?',
                    [*[values[f] for f in fields],equipment.utc_now(),eid,actor['UserId'],data['revision']])
                if result.rowcount!=1:
                    raise AssistantError('동시 변경이 발생했습니다.',409)
            equipment.audit(db,eid,'AI_CREATE' if operation.endswith('create') else 'AI_UPDATE',actor['UserId'],before,values)
            return {'equipment_id':eid,'is_draft':values['is_draft'],'message':'장비를 임시저장했습니다.' if values['is_draft'] else '장비를 등록했습니다.' if operation.endswith('create') else '장비를 수정했습니다.'}
        if operation in ('catalog_request','option_request'):
            self.require_menu(actor,'my_equipment','public_equipment','my_approvals')
            result=submit_catalog_request(db,data,actor) if operation=='catalog_request' else save_option(db,data,actor)
            result.pop('before',None)
            if result.get('status')=='PENDING' and not result.get('request_id'):
                request_type='Equipment_Option' if operation=='option_request' else 'Lineup_Node'
                created=db.execute("SELECT RequestId FROM approval_requests WHERE RequestId=last_insert_rowid() AND RequesterId=? AND RequestType=? AND Status='PENDING'",(actor['UserId'],request_type)).fetchone()
                if created is None:
                    raise AssistantError('신청 처리 기록을 확인하지 못했습니다.',409)
                result['request_id']=created['RequestId']
            return {**result,'message':'신청이 접수되었습니다. 관리자 승인 후 사용할 수 있습니다.'}
        if operation=='preferences':
            if self.preferences(db,actor)!=before:
                raise AssistantError('설정이 변경되었습니다. 새 확인 내용을 준비해 주세요.',409)
            if data.get('deadline_email_opt_in') and not db.execute('SELECT 1 FROM users u WHERE u.UserId=? AND u.Email IS NOT NULL AND (u.notification_verified_email=u.Email OR EXISTS(SELECT 1 FROM email_verifications v WHERE v.Email=u.Email AND v.IsVerified=1))',(actor['UserId'],)).fetchone():
                raise AssistantError('먼저 본인의 이메일 인증을 완료해 주세요.')
            settings={**before,**data}
            db.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?) ON CONFLICT(UserId) DO UPDATE SET PreferencesJSON=excluded.PreferencesJSON,UpdatedAt=excluded.UpdatedAt',
                (actor['UserId'],canonical(settings),equipment.utc_now()))
            return {'settings':data,'message':'개인 설정을 변경했습니다.'}
        if operation=='csv_export':
            self.require_menu(actor,'my_equipment' if data['scope']=='my' else 'public_equipment')
            return {'download_url':'/api/ai/csv/export?scope='+data['scope'],'message':'현재 권한으로 CSV를 내려받을 수 있습니다.'}
        raise AssistantError('허용되지 않은 작업입니다.',403)
