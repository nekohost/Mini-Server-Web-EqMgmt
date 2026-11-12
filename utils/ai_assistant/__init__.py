"""[MINI-COMMENT: ASSISTANT.HTTP]
[EN rev.16]
[Role] Installs private chat and mail translation, administrator provider verification and revision-bound worker handoff.
[Dependencies] Existing login/DB/maintenance services; private assistant Store and Domain.
[Impact] Explicit single-mail translations use an isolated, tool-free step and a checked terminal report. Ordinary chat corrections, immutable consent and execution guards are preserved.
"""
from contextlib import closing
from datetime import datetime
import json
import os
import re
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, abort, g, jsonify, render_template, request, send_file, session, url_for
from flask.sessions import SecureCookieSessionInterface

from utils.roadmap_validation import InputError
from utils.lineup_node_service import LineupNodeError
from utils import roadmap_equipment as equipment, roadmap_files as files
from .domain import Domain
from .policy import (AssistantError, DEFAULT_LEVEL, ERROR_REASONS, LEGACY_LEVELS, LEVELS, LEVEL_LABELS, MAX_CONTENT, MAX_REASONING,
                     SYSTEM, TERMINAL, TOOL_MAP, canonical, digest, identity, mac, object_only,
                     opaque, stream_text, text, validate_schema, normalized_tool_arguments)
from .store import Store
from .providers import Registry, PROTOCOL, public_source
from . import admin_logs, provider_candidates
from .provider_trust import BeforeSendError, RevisionPolicy
from .reasoning import VERSION as REASONING_VERSION, normalize_profile
from .context import DRAFT_TOOL, TASK_DRAFT_TOOL, build_context
from .audit import preserve_export
from .status import read_status
from .web_search import SearchService, WebSearchError, MAX_SEARCHES, public_searches, search_mode, search_planning, search_permitted
from .recovery import CORRECTIONS, correction_context, correction_phase, model_context
from .translation import explicit_mail, translation_completion, translation_packet


def enabled(value):
    """[Role] Parses deployment flags explicitly; truthy string 'false' never enables writes.
    [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
    [Impact] Preserves the module's owner/validation/transaction boundary described above.
    """
    return value is True or isinstance(value,str) and value.lower() in ('1','true','yes','on')


def visible_assistant_menus(rows, role, config):
    """[MINI-COMMENT: ASSISTANT.MENUS]
    [EN rev.1]
    [Role] Publishes the enabled user assistant and its admin-only settings menu.
    [Dependencies] Current server role and feature flag; business grant checks still run at routes.
    [Impact] An erroneous user grant cannot expose AI connection administration.
    """
    active=enabled(config.get('USER_AI_ENABLED',False))
    return [dict(r) for r in rows if (r['MenuCode'] not in ('equipment_ai','equipment_ai_settings',admin_logs.MENU) or
            active and (r['MenuCode']=='equipment_ai' or role=='admin'))]


class PassiveSessionInterface(SecureCookieSessionInterface):
    """[Role] Prevents background reads from extending permanent login cookies."""
    def should_set_cookie(self, app, current):
        """[Role] Suppresses the sliding expiry on idle reads.
        [Dependencies] Session checks, assistant GETs and marked access-log list/statistics GETs.
        [Impact] Manual reads and session mutations retain Flask's normal cookie behavior.
        """
        if request.method == 'GET' and not current.modified:
            if request.path == '/api/check_session' or request.path.startswith('/api/ai/'):
                return False
            if (request.path in ('/api/access_logs', '/api/access_logs/stats')
                    and request.headers.get('X-Access-Log-Poll') == '1'):
                return False
        return super().should_set_cookie(app, current)


def install_assistant(app, services):
    """[MINI-COMMENT: ASSISTANT.INSTALL]
    [EN rev.7]
    [Role] Wires disabled-by-default assistant, owner-authorized rename and passive status routes with injected application contracts.
    [Dependencies] A stable strong app secret, independent worker secret and explicit public origin.
    [Impact] Enabling upgrades the AI store and reparents only the verified admin menu while preserving business data/grants.
    """
    app.config.setdefault('USER_AI_ENABLED',enabled(os.getenv('USER_AI_ENABLED','')))
    app.config.setdefault('USER_AI_WRITE_TOOLS',enabled(os.getenv('USER_AI_WRITE_TOOLS','')))
    app.config.setdefault('USER_AI_WORKER_TOKEN',os.getenv('USER_AI_WORKER_TOKEN',''))
    app.config.setdefault('USER_AI_PUBLIC_ORIGIN',os.getenv('USER_AI_PUBLIC_ORIGIN','https://nekohost.org'))
    app.config.setdefault('USER_AI_DATABASE',os.getenv('USER_AI_DATABASE',str(Path(app.instance_path)/'ai'/'assistant.sqlite3')))
    app.config.setdefault('USER_AI_COMPLETION_RESERVE_CHARS',os.getenv('USER_AI_COMPLETION_RESERVE_CHARS','32000000'))
    for key, default in {'USER_AI_STRATA_URL':'http://192.168.0.14:8080', 'USER_AI_STRATA_KEY':'',
            'USER_AI_MODEL':'qwen3.8-flash-next-iq3_xxs', 'USER_AI_PROVIDER_ENCRYPTION_KEY':'',
            'USER_AI_PROVIDER_PREVIOUS_KEYS':'[]',
            'USER_AI_ALLOWED_ENDPOINTS':None, 'USER_AI_MODEL_DISCOVERY':True,
            'USER_AI_DATABASE_EPOCH':'initial-v3',
            'USER_AI_AUDIT_MAX_BYTES':2147483648}.items():
        app.config.setdefault(key, os.getenv(key,default))
    app.config.setdefault('USER_AI_AUDIT_ROOT',str(Path(app.instance_path)/'ai'/'audit-originals'))
    connect=services['get_db_connection']
    login=services['login_required']
    bp=Blueprint('equipment_assistant',__name__)
    is_enabled=enabled(app.config['USER_AI_ENABLED'])
    store=None
    registry=None
    domain=Domain(connect,app.secret_key,services['get_maintenance_state'],
        SearchService(app.root_path,enabled(os.getenv('USER_AI_WEB_SEARCH','true'))))
    if type(app.session_interface) is SecureCookieSessionInterface:
        app.session_interface=PassiveSessionInterface()
    if is_enabled:
        if (not app.secret_key or len(app.secret_key)<32 or app.secret_key=='default_secret_key_if_not_found'
                or len(app.config['USER_AI_WORKER_TOKEN'])<32 or app.secret_key==app.config['USER_AI_WORKER_TOKEN']):
            raise ValueError('assistant requires independent strong server secrets')
        origin=urlsplit(app.config['USER_AI_PUBLIC_ORIGIN'])
        if origin.scheme not in ('http','https') or not origin.netloc or origin.path or origin.query or origin.fragment or origin.username:
            raise ValueError('invalid assistant public origin')
        if type(app.session_interface) is not PassiveSessionInterface:
            raise ValueError('assistant passive session adapter requires an audited session interface')
        if origin.scheme=='https':
            app.config['SESSION_COOKIE_SECURE']=True
        store=Store(app.config['USER_AI_DATABASE'],int(app.config['USER_AI_COMPLETION_RESERVE_CHARS']),app.config['USER_AI_DATABASE_EPOCH'])
        registry=Registry(store,app.config)
        db=connect()
        try:
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row=db.execute("SELECT Url FROM menus WHERE MenuCode='equipment_ai'").fetchone()
            if row and row[0]!='/assistant':
                raise ValueError('assistant menu collision')
            db.execute("INSERT OR IGNORE INTO menus(MenuCode,MenuName,Url,Description,ParentMenuCode,SortOrder,CreatedAt,UpdatedAt) VALUES('equipment_ai','AI 도우미','/assistant','내 장비 조회·등록·수정과 신청',NULL,51,?,?)",(now,now))
            for role in ('admin','user'):
                db.execute("INSERT OR IGNORE INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt) VALUES(?,'equipment_ai',1,?)",(role,now))
            admin_logs.register_admin_menu(db, 'equipment_ai_settings', 'AI 연결 관리', '/admin/ai/providers',
                                           '장비관리 AI 연결·공개 모델 관리', 52, now)
            admin_logs.register_admin_menu(db, admin_logs.MENU, 'AI 도우미 기록', admin_logs.PAGE_URL,
                                           '사용자 질문과 최종 답변, 작업 결과와 CSV 영수증 조회', 53, now)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    app.extensions['equipment_assistant']={'store':store,'domain':domain,'registry':registry}

    def active():
        """[Role] Rechecks the feature flag on every boundary, including an in-flight write.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if store is None or not enabled(app.config.get('USER_AI_ENABLED')):
            raise AssistantError('AI 도우미를 사용할 수 없습니다.',404)

    def body(maximum=32768):
        """[Role] Requires bounded JSON; multipart/files remain in the existing authenticated UI APIs.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if not request.is_json or request.content_length is None or request.content_length>maximum:
            raise AssistantError('요청 크기와 JSON 형식을 확인해 주세요.',413)
        return request.get_json(silent=True)

    def browser(write=False):
        """[MINI-COMMENT: ASSISTANT.BROWSER.AUTH]
        [EN rev.1]
        [Role] Revalidates signed-session identity, live DB token, menu grants and browser write intent.
        [Dependencies] The original login decorator and explicit Origin/CSRF for every browser mutation.
        [Impact] Editing cookie claims/IDs or possessing a worker token cannot impersonate another owner.
        """
        active()
        user=session.get('user') or {}
        uid=identity(user.get('UserId'))
        token=session.get('session_token')
        if not isinstance(token,str) or not token:
            raise AssistantError('다시 로그인해 주세요.',401)
        binding=domain.binding(uid,token)
        db=connect()
        try:
            actor=domain.actor(db,uid,binding)
        finally:
            db.close()
        if store.revoked(binding):
            raise AssistantError('다시 로그인해 주세요.',401)
        g.assistant_display_context=mac(app.secret_key,'display',uid,binding)[:32]
        if write:
            csrf=request.headers.get('X-CSRFToken','')
            if request.headers.get('Origin','')!=app.config['USER_AI_PUBLIC_ORIGIN'] or not isinstance(session.get('csrf_token'),str) or not csrf or not secrets.compare_digest(csrf,session['csrf_token']):
                raise AssistantError('요청을 확인할 수 없습니다. 화면을 새로고침해 주세요.',403)
        return actor

    def worker(*, require_store=True):
        """[Role] Authenticates only local worker requests, independently from browser/account cookies.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if require_store and store is None:
            raise AssistantError('AI 도우미가 설정되지 않았습니다.',404)
        expected=app.config.get('USER_AI_WORKER_TOKEN','')
        given=request.headers.get('Authorization','')
        peer = request.environ.get('werkzeug.proxy_fix.orig', {}).get('REMOTE_ADDR', request.remote_addr)
        if (peer not in ('127.0.0.1','::1') or request.remote_addr not in ('127.0.0.1','::1')
                or request.headers.get('X-Forwarded-For') or not expected or not secrets.compare_digest(given,'Bearer '+expected)):
            raise AssistantError('처리 권한이 없습니다.',403)

    def claim_worker():
        worker(require_store=False)
        data = object_only(body(), ('worker', 'protocol'), ('worker', 'protocol'))
        if data['protocol'] != PROTOCOL:
            raise AssistantError('AI 서버/worker 프로토콜 버전이 일치하지 않습니다.', 409)
        return text(data['worker'], 100)

    def planned_worker_wait():
        if request.endpoint != 'equipment_assistant.claim' or request.method != 'POST':
            return False
        try:
            claim_worker()
        except AssistantError:
            return False
        g.planned_worker_wait = True
        return True

    app.extensions['equipment_assistant']['planned_worker_wait'] = planned_worker_wait

    def worker_lease_boundary(jid,token,outcome=None):
        """[MINI-COMMENT: ASSISTANT.WORKER.LIFECYCLE.BOUNDARY]
        [EN rev.1]
        [Role] Resolves a live lease or a content-free deletion guard, including a concurrent purge.
        [Dependencies] The caller first authenticates the loopback worker; every guard rechecks its lease.
        [Impact] Known completion delivery cannot strand a purged request or restore its discarded text.
        """
        def guarded():
            """[Role] Chooses one bounded guard check. [Dependencies] Validated outcome. [Impact] Does not run tools."""
            return store.guard_finish(jid,token,outcome) if outcome is not None else store.guard_event(jid,token)
        result=guarded()
        if result is not None:
            return None,result
        try:
            with store.db() as db:
                return store.lease(db,jid,token),None
        except AssistantError as error:
            if error.status in (404,409):
                result=guarded()
                if result is not None:
                    return None,result
            raise

    def require_administrator_grant(db,actor):
        """[MINI-COMMENT: ASSISTANT.ADMIN.CURRENT.GRANT]
        [EN rev.1]
        [Role] Rechecks actual administrator status and the dedicated menu without trusting projected roles.
        [Dependencies] An already authenticated live actor and current business-DB role/grant rows.
        [Impact] A revoked admin cannot inspect old diagnostics or publish a newly verified model profile.
        """
        role=db.execute('SELECT Role FROM users WHERE UserId=?',(actor['UserId'],)).fetchone()
        grant=db.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role='admin' AND MenuCode='equipment_ai_settings'").fetchone()
        if not role or role['Role']!='admin' or not grant or not grant[0]:
            raise AssistantError('관리자 AI 연결 관리 권한이 필요합니다.',403)

    def job_actor(job):
        """[Role] Checks job expiry/revocation and current rights before each step/tool response.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if services['get_maintenance_state']()['state']!='NORMAL':
            raise AssistantError('시스템 점검으로 이 작업을 중단했습니다.',503)
        if job['expires']<time.time() or store.revoked(job['binding']):
            raise AssistantError('로그인 작업 권한이 만료되었습니다.',401)
        db=connect()
        try:
            actor=domain.actor(db,job['owner'],job['binding'])
            if actor['account_key']!=job['account_key']:
                raise AssistantError('계정 식별정보가 변경되었습니다.',401)
            if job['purpose']=='probe':
                require_administrator_grant(db,actor)
            return actor
        finally:
            db.close()

    def maintenance_cleanup():
        """[MINI-COMMENT: ASSISTANT.MAINTENANCE.LEASE]
        [EN rev.2]
        [Role] Authenticates only fixed cleanup callbacks without opening the equipment DB.
        [Dependencies] Loopback worker secret and a current AI-only job or detached execution-guard lease.
        [Impact] New claims/admin/browser operations cannot use this maintenance exception.
        """
        if not store or request.method!='POST' or not re.fullmatch(r'/internal/ai/jobs/[0-9a-f]{32}/(?:event|finish)',request.path):
            return False
        try:
            worker()
            data=body(2097152)
            if not isinstance(data,dict):
                return False
            jid=request.path.split('/')[4]
            with store.db() as db:
                try:
                    store.lease(db,jid,data.get('lease'))
                except AssistantError as error:
                    if error.status not in (404,409):
                        raise
                    store._guard_lease(db,jid,data.get('lease'))
            return True
        except Exception:
            return False

    app.extensions['equipment_assistant']['maintenance_cleanup']=maintenance_cleanup

    def administrator(write=False):
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMINISTRATOR]
        [EN rev.1]
        [Role] Requires the actual current DB admin role plus the dedicated management menu and CSRF.
        [Dependencies] Existing signed-session validation, never Role supplied by the browser or model.
        [Impact] Ordinary user sessions and worker credentials cannot administer providers.
        """
        actor=browser(write)
        db=connect()
        try:
            require_administrator_grant(db,actor)
        finally:
            db.close()
        return actor

    def ordinary_conversation(actor,cid,db,view='active'):
        """[MINI-COMMENT: ASSISTANT.CONVERSATION.PURPOSE]
        [EN rev.1]
        [Role] Keeps pure administrator diagnostics outside ordinary chat while preserving mixed legacy history.
        [Dependencies] Current owner/account lifecycle and persisted job purposes, never a title/nonce heuristic.
        [Impact] Existing user turns stay accessible; a diagnostic record cannot become a new normal-chat context.
        """
        conv=store.conversation(actor['UserId'],cid,db,actor['account_key'],view=view)
        purposes=db.execute("SELECT COUNT(*) AS total,SUM(CASE WHEN purpose='chat' THEN 1 ELSE 0 END) AS chats FROM jobs WHERE conversation=?",(cid,)).fetchone()
        if purposes['total'] and not purposes['chats']:
            raise AssistantError('기능 시험 기록은 관리자 연결 화면에서 확인해 주세요. 일반 질문은 새 대화에서 시작해 주세요.',409)
        return conv

    def selected(actor,cid=None,explicit=None,level=None):
        """[MINI-COMMENT: ASSISTANT.HTTP.SELECTED]
        [EN rev.3]
        [Role] Restores a conversation's choice before considering defaults for new/unselected chats.
        [Dependencies] Current published/verified registry profile and active owner-bound ordinary conversation.
        [Impact] Removed/offline saved models raise a reselection reason instead of silent failover.
        """
        conv=None
        if cid:
            with store.db() as db:
                conv=ordinary_conversation(actor,cid,db)
        mid=explicit or (conv['selection_id'] if conv else None) or registry.choices()['default_model']
        if not mid:
            raise AssistantError('사용 가능한 모델이 없습니다. 관리자에게 연결/모델 시험을 요청해 주세요.',503)
        route=registry.resolve(opaque(mid))
        level=level if level is not None else (conv['next_level'] if conv else route['profile']['default_level'])
        levels=route['profile'].get('levels',[])
        if type(level) is not str or (level not in levels if levels else level != DEFAULT_LEVEL):
            raise AssistantError('이 모델이 지원하는 추론 수준을 다시 선택해 주세요.',409)
        route['reasoning_effort']=LEVELS[level] if levels else None
        return route,level,conv

    @bp.errorhandler(AssistantError)
    @bp.errorhandler(InputError)
    @bp.errorhandler(LineupNodeError)
    def expected_error(error):
        """[Role] Returns safe domain errors without disguising failure as a successful operation.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        return jsonify(success=False,message=str(error)),getattr(error,'status',getattr(error,'status_code',400))

    @bp.errorhandler(Exception)
    def unexpected_error(error):
        """[Role] Logs only exception class; no model input, credentials or traceback is returned.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        app.logger.error('assistant failure type=%s',type(error).__name__)
        return jsonify(success=False,message='요청을 완료하지 못했습니다. 저장된 처리 상태를 확인해 주세요.'),500

    @bp.after_request
    def private(response):
        """[Role] Disables caching and framing of user-owned chat and worker responses.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'})
        response.headers.setdefault('Content-Security-Policy',"frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        if getattr(g,'assistant_display_context',None):
            response.headers['X-Assistant-Account']=g.assistant_display_context
        return response

    @app.before_request
    def capture_logout():
        """[Role] Captures this signed login binding before the existing logout clears its cookie.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        if store and request.method=='POST' and request.endpoint=='logout':
            user=session.get('user') or {}
            token=session.get('session_token')
            if type(user.get('UserId')) is int and isinstance(token,str):
                g.assistant_logout_binding=domain.binding(user['UserId'],token)

    @app.after_request
    def revoke_logout(response):
        """[Role] Stops only assistant jobs delegated by the login being explicitly logged out.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        binding=getattr(g,'assistant_logout_binding',None)
        if binding and response.status_code in (302, 303) and not session.get('user'):
            store.revoke(binding)
        return response

    def load_admin_logs():
        active()
        uid = identity(session['user']['UserId'])
        token = session.get('session_token')
        if not isinstance(token, str) or not token:
            raise AssistantError('다시 로그인해 주세요.', 401)
        maintenance = services['get_maintenance_state']()
        if maintenance['state'] != 'NORMAL':
            raise AssistantError('점검 중입니다. 잠시 후 다시 이용해 주세요.', 503)
        protected = (app.secret_key, app.config.get('USER_AI_WORKER_TOKEN'), app.config.get('USER_AI_STRATA_KEY'),
                     app.config.get('USER_AI_PROVIDER_ENCRYPTION_KEY'), token, session.get('csrf_token'),
                     request.cookies.get(app.config.get('SESSION_COOKIE_NAME', 'session')))
        try:
            with closing(connect()) as db:
                return admin_logs.read_records(store.path, db, uid, token, domain.binding(uid, token, maintenance),
                    request.args, tuple(s for s in protected if isinstance(s, str) and s))
        except sqlite3.Error as error:
            app.logger.error('assistant record read failed type=%s', type(error).__name__)
            raise AssistantError('기록 저장소를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.', 503) from None

    @bp.get(admin_logs.PAGE_URL)
    @login
    def admin_logs_page():
        try:
            data = load_admin_logs()
        except AssistantError as error:
            return render_template('equipment_ai_logs.html', user=session['user'], error=str(error)), error.status

        def page_url(**changes):
            params = {**request.args.to_dict(), **changes}
            if data['view'] == 'questions' and ('before' in changes or 'after' in changes):
                params.pop('question_page', None)
            return url_for('.admin_logs_page', **{k: v for k, v in params.items() if v is not None})

        return render_template('equipment_ai_logs.html', user=session['user'], data=data, page_url=page_url,
            job_states=admin_logs.JOB_STATES, proposal_states=admin_logs.PROPOSAL_STATES,
            operations=admin_logs.OPERATIONS, log_time=admin_logs.log_time)

    @bp.get('/api' + admin_logs.PAGE_URL)
    @login
    def admin_logs_api():
        return jsonify(success=True, **load_admin_logs())

    @bp.get('/assistant')
    @login
    def page():
        """[MINI-COMMENT: ASSISTANT.HTTP.PAGE] [EN rev.1]
        [Role] Renders the independent assistant with this authenticated account's initial input action.
        [Dependencies] The current browser actor, an owner-scoped read of existing PreferencesJSON and a fixed newline/send mapping.
        [Impact] The first keystroke preserves a saved mode before asynchronous settings load; reads never migrate rows and malformed/missing settings default to send.
        """
        actor=browser()
        if not session.get('csrf_token'):
            session['csrf_token']=secrets.token_hex(32)
        db=connect()
        try: row=db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=?',(actor['UserId'],)).fetchone()
        finally: db.close()
        try: preferences=json.loads(row[0] or '{}') if row else {}
        except (ValueError,TypeError): preferences={}
        enter_action='newline' if isinstance(preferences,dict) and preferences.get('ai_enter_action')=='newline' else 'send'
        return render_template('equipment_ai.html',user=session['user'],assistant_csrf=session['csrf_token'],assistant_enter_action=enter_action)

    @bp.get('/api/ai/capabilities')
    @login
    def capabilities():
        """[Role] Returns only server-approved levels and available user tools, without secrets.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser()
        return jsonify(success=True,model='서버에서 공개한 모델 선택',reasoning_version=REASONING_VERSION,levels=[{'id':k,'label':v} for k,v in LEVEL_LABELS.items()],
            tools=[t['function']['name'] for t in domain.tools(actor) if enabled(app.config['USER_AI_WRITE_TOOLS']) or not t['function']['name'].startswith('prepare_')],
            scopes=(['my','draft'] if 'my_equipment' in actor['menus'] else [])+(['public'] if 'public_equipment' in actor['menus'] else []),
            writes=enabled(app.config['USER_AI_WRITE_TOOLS']),file_tools='my_equipment' in actor['menus'] and enabled(app.config['USER_AI_WRITE_TOOLS']),
            web_search={'available':domain.search_service.available,'mode':'auto','providers':getattr(domain.search_service,'providers',[]),'notice':'질문에 필요한 경우 AI가 공개 검색어를 외부 검색 제공자에게 보냅니다. 계정·인증·시리얼·비공개 메모는 검색하지 않습니다.'},
            storage=store.storage_status(actor['UserId'],actor['account_key']))

    @bp.get('/api/ai/models')
    @login
    def models():
        """[MINI-COMMENT: ASSISTANT.HTTP.MODELS]
        [EN rev.1]
        [Role] Returns cached/discovered sanitized choices and automatic initial selection.
        [Dependencies] Backend-only fixed model-list calls, throttled to one attempt per 60 seconds.
        [Impact] The browser never calls LAN providers or receives endpoints/credentials/raw metadata.
        """
        browser()
        if enabled(app.config['USER_AI_MODEL_DISCOVERY']):
            with store.db() as db:
                ids=[r[0] for r in db.execute('SELECT id FROM ai_providers WHERE enabled=1 AND retired=0 AND (last_checked IS NULL OR last_checked<?)',(time.time()-60,))]
            for pid in ids:
                try:
                    registry.discover(pid)
                except AssistantError:
                    pass
        return jsonify(success=True,**registry.choices())

    @bp.post('/api/ai/conversations/<cid>/selection')
    @login
    def selection(cid):
        """[MINI-COMMENT: ASSISTANT.HTTP.SELECTION]
        [EN rev.2]
        [Role] Changes only the next-turn choice and persists supported reasoning for this conversation.
        [Dependencies] Live browser owner, model profile and optimistic selection revision.
        [Impact] In-flight requests and signed confirmation cards retain their accepted contracts.
        """
        actor=browser(True)
        data=object_only(body(),('selection_id','level','revision','reasoning_version'),('selection_id','level','revision'))
        if type(data.get('reasoning_version')) is not int or data['reasoning_version'] != REASONING_VERSION:
            raise AssistantError('추론 설정 형식이 변경되었습니다. 화면을 새로고침해 주세요.',409)
        route,level,conv=selected(actor,opaque(cid),opaque(data['selection_id']),data['level'])
        revision=store.select_model(actor['UserId'],cid,actor['account_key'],route['selection_id'],level,data['revision'])
        return jsonify(success=True,revision=revision,selection_id=route['selection_id'],level=level)

    @bp.get('/admin/ai/providers')
    @login
    def admin_page():
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMIN_PAGE]
        [EN rev.1]
        [Role] Serves the independent basic provider-management screen to actual administrators only.
        [Dependencies] Existing frame, live admin/menu check and per-session CSRF.
        [Impact] Deferred advanced endpoint customization is not exposed.
        """
        administrator()
        if not session.get('csrf_token'):
            session['csrf_token']=secrets.token_hex(32)
        return render_template('equipment_ai_providers.html',user=session['user'],assistant_csrf=session['csrf_token'])

    @bp.route('/api/admin/ai/providers',methods=['GET','POST'])
    @login
    def admin_providers():
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMIN_PROVIDERS]
        [EN rev.1]
        [Role] Lists safe basic connection settings or creates an encrypted immutable revision.
        [Dependencies] Actual admin/menu, CSRF/Origin on mutation and registry validation.
        [Impact] No original/encrypted credentials are returned by this API.
        """
        actor=administrator(request.method=='POST')
        if request.method=='POST':
            return jsonify(success=True,id=registry.save(body(),actor=actor['UserId'])),201
        return jsonify(success=True,**registry.admin_list())

    @bp.post('/api/admin/ai/providers/<pid>')
    @login
    def admin_provider_save(pid):
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMIN_PROVIDER_SAVE]
        [EN rev.1]
        [Role] Adds a revision or soft-retires a provider, preserving accepted job routes/history.
        [Dependencies] Current administrator and optimistic revision.
        [Impact] Retiring never deletes records or controls upstream processes.
        """
        actor=administrator(True)
        return jsonify(success=True,id=registry.save(body(),opaque(pid),actor['UserId']))

    @bp.post('/api/admin/ai/providers/<pid>/revoke-trust')
    @login
    def admin_revoke_trust(pid):
        actor=administrator(True)
        data=object_only(body(),('revision',),('revision',))
        if type(data['revision']) is not int or data['revision']<1:
            raise AssistantError('철회할 연결 버전을 선택해 주세요.')
        registry.revoke_trust(opaque(pid),data['revision'],actor['UserId'])
        return jsonify(success=True)

    @bp.post('/api/admin/ai/providers/<pid>/discover')
    @login
    def admin_discover(pid):
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMIN_DISCOVER]
        [EN rev.1]
        [Role] Explicitly refreshes a provider's model inventory without assuming readiness/tool support.
        [Dependencies] Administrator CSRF/Origin and fixed pinned models adapter.
        [Impact] An error retains last-known records and an actionable connection status.
        """
        actor=administrator(True)
        data=object_only(body(),('candidate_revision',))
        if 'candidate_revision' in data and type(data['candidate_revision']) is not int:
            raise AssistantError('후보 버전을 확인해 주세요.')
        registry.discover(opaque(pid),True,data.get('candidate_revision'),actor['UserId'])
        return jsonify(success=True,**registry.admin_list())

    @bp.post('/api/admin/ai/providers/<pid>/models')
    @login
    def admin_model(pid):
        """[MINI-COMMENT: ASSISTANT.HTTP.ADMIN_MODEL]
        [EN rev.2]
        [Role] Manages model aliases/publication/context and explicitly optional manual registration.
        [Dependencies] Live admin and revision-checked registry; capability tests remain separate.
        [Impact] A name in the inventory alone never grants model tools or reasoning support.
        """
        administrator(True)
        return jsonify(success=True,id=registry.update_model(opaque(pid),body()))

    @bp.post('/api/admin/ai/models/<mid>/probe')
    @login
    def admin_probe(mid):
        """[MINI-COMMENT: ASSISTANT.PROBE.QUEUE]
        [EN rev.3]
        [Role] Queues inert model capability checks through the same account quotas and physical group slot.
        [Dependencies] Admin-only intent, current route, nonce and the ordinary private worker protocol.
        [Impact] Probe tools never touch equipment; accepted parameters alone do not prove reasoning output.
        """
        actor=administrator(True)
        data=object_only(body(),('tools','reasoning','client_key','provider_id','candidate_revision','context_tokens'),('tools','reasoning','client_key'))
        if type(data['tools']) is not bool or type(data['reasoning']) is not bool:
            raise AssistantError('시험할 기능을 확인해 주세요.')
        mid=opaque(mid)
        if 'candidate_revision' in data or 'provider_id' in data:
            if type(data.get('candidate_revision')) is not int:
                raise AssistantError('후보 버전을 확인해 주세요.')
            with store.db() as db:
                route=provider_candidates.probe_route(db,opaque(data.get('provider_id')),data['candidate_revision'],mid,
                                                     context_tokens=data.get('context_tokens'))
        else:
            if 'context_tokens' in data:
                raise AssistantError('활성 모델의 컨텍스트 한도는 모델 설정에서 변경해 주세요.')
            route=registry.resolve(mid,True)
        if data['reasoning'] and not route['profile']['enabled_levels']:
            raise AssistantError('관리자 모델 설정에서 시험할 추론 수준을 먼저 허용해 주세요.')
        if data['tools'] and route['context_tokens']<8192:
            raise AssistantError('장비 도구용 컨텍스트는 8,192 token 이상으로 검증해 주세요.')
        route['probe_nonce']=secrets.token_hex(16)
        route['reasoning_effort']=None
        plan=['chat']+(['tools'] if data['tools'] else [])+(route['profile']['enabled_levels'] if data['reasoning'] else [])
        with store.db() as db:
            previous=db.execute('SELECT j.* FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.owner=? AND j.client_key=? AND c.account_key=?',(actor['UserId'],opaque(data['client_key']),actor['account_key'])).fetchone()
        if previous:
            prior_route=json.loads(previous['route_snapshot'])
            if (previous['purpose']!='probe' or previous['selection_id']!=mid or json.loads(previous['probe_plan'])!=plan
                    or prior_route['revision']!=route['revision'] or prior_route.get('candidate_generation')!=route.get('candidate_generation')
                    or prior_route['context_tokens']!=route['context_tokens']):
                raise AssistantError('같은 접수 키로 다른 시험을 요청할 수 없습니다.',409)
            return jsonify(success=True,job_id=previous['id'],conversation_id=previous['conversation']),202
        cid=store.create_conversation(actor['UserId'],actor['account_key'])
        jid=store.enqueue(actor['UserId'],cid,'관리자 모델 기능 시험','low',opaque(data['client_key']),actor['binding'],time.time()+1800,actor['account_key'],route,'probe',plan)
        return jsonify(success=True,job_id=jid,conversation_id=cid),202

    @bp.get('/api/admin/ai/probes')
    @login
    def admin_probe_lookup():
        """[MINI-COMMENT: ASSISTANT.PROBE.LOOKUP]
        [EN rev.1]
        [Role] Resolves an uncertain probe acknowledgement without resubmitting model work.
        [Dependencies] Actual administrator, owner/account identity and an opaque client idempotency key.
        [Impact] A read returns only this administrator's probe IDs, never nonce, prompt or credentials.
        """
        actor=administrator()
        if set(request.args)!= {'client_key'}:
            raise AssistantError('시험 확인 식별자를 확인해 주세요.')
        key=opaque(request.args.get('client_key'))
        with store.db() as db:
            row=db.execute("SELECT j.id,j.conversation FROM jobs j JOIN conversations c ON c.id=j.conversation WHERE j.owner=? AND j.client_key=? AND c.account_key=? AND j.purpose='probe' AND c.is_deleted=0",
                           (actor['UserId'],key,actor['account_key'])).fetchone()
        return jsonify(success=True,found=bool(row),**({'job_id':row['id'],'conversation_id':row['conversation']} if row else {}))

    @bp.route('/api/ai/conversations',methods=['GET','POST'])
    @login
    def conversations():
        """[Role] Lists/creates only the authenticated owner's durable conversations.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(request.method=='POST')
        if request.method=='POST':
            object_only(body(),())
            cid=store.create_conversation(actor['UserId'],actor['account_key'])
            choice=registry.choices()['default_model']
            if choice:
                initial=registry.resolve(choice)['profile']['default_level']
                store.select_model(actor['UserId'],cid,actor['account_key'],choice,initial,0)
            return jsonify(success=True,id=cid,selection_revision=1 if choice else 0),201
        return jsonify(success=True,**store.conversations(actor['UserId'],actor['account_key'],request.args.get('cursor'),view=request.args.get('view','active'), resume=request.args.get('resume') == '1'))

    @bp.get('/api/ai/conversations/<cid>/messages')
    @login
    def messages(cid):
        """[Role] Hydrates bounded owner-only history, including collapsible saved reasoning.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser()
        try:
            before=int(request.args['before']) if 'before' in request.args else None
        except ValueError:
            raise AssistantError('이전 대화 내용의 위치를 확인해 주세요.') from None
        view=request.args.get('view','active')
        with store.db() as db:
            ordinary_conversation(actor,opaque(cid),db,view=view)
        return jsonify(success=True,**store.snapshot(actor['UserId'],cid,actor['account_key'],before,view=view),storage=store.storage_status(actor['UserId'],actor['account_key']))

    @bp.post('/api/ai/conversations/<cid>/rename')
    @login
    def conversation_rename(cid):
        """[MINI-COMMENT: ASSISTANT.CONVERSATION.RENAME.HTTP]
        [EN rev.1]
        [Role] Accepts only a real user's explicit current-account conversation rename.
        [Dependencies] Live identity/menu authorization, Origin/CSRF and strict title/revision/operation fields.
        [Impact] Administrators cannot rename another owner's chat; receipt retries cannot overwrite a later title or bypass trash protection.
        """
        actor=browser(True)
        fields=('title','expected_title','lifecycle_revision','operation_id')
        data=object_only(body(),fields,fields)
        result=store.rename_conversation(actor['UserId'],opaque(cid),actor['account_key'],data['title'],
            data['expected_title'],data['lifecycle_revision'],opaque(data['operation_id']))
        return jsonify(success=True,**result)

    @bp.post('/api/ai/conversations/<cid>/trash')
    @bp.post('/api/ai/conversations/<cid>/restore')
    @bp.post('/api/ai/conversations/<cid>/purge')
    @login
    def conversation_lifecycle(cid):
        """[MINI-COMMENT: ASSISTANT.CONVERSATION.LIFECYCLE.HTTP]
        [EN rev.1]
        [Role] Applies only a real user's explicitly requested trash, restore or permanent deletion.
        [Dependencies] Current owner/account, CSRF/Origin, strict revision/idempotency input and Store's transaction.
        [Impact] The server alone sets retention times; models cannot delete conversations or business data.
        """
        actor=browser(True)
        data=object_only(body(),('lifecycle_revision','operation_id'),('lifecycle_revision','operation_id'))
        revision=data['lifecycle_revision']
        if type(revision) is not int or not 0<=revision<=2**63-1:
            raise AssistantError('대화 상태를 새로 확인해 주세요.',409)
        action=request.path.rsplit('/',1)[-1]
        result=store.lifecycle(actor['UserId'],opaque(cid),actor['account_key'],action,revision,opaque(data['operation_id']))
        return jsonify(success=True,**result,storage=store.storage_status(actor['UserId'],actor['account_key']))

    @bp.post('/api/ai/conversations/first-turn', defaults={'cid': None})
    @bp.post('/api/ai/conversations/<cid>/turns')
    @login
    def submit(cid):
        """[Role] Authenticates first and subsequent turns with the same content, model, CSRF and search policy.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(True)
        data=object_only(body(),('content','level','client_key','selection_id','reasoning_version','web_search'),('content','level','client_key'))
        content=text(data['content'],8000)
        if not isinstance(data['level'],str) or data['level'] not in (*LEVELS,DEFAULT_LEVEL):
            raise AssistantError('추론 수준을 확인해 주세요.')
        if type(data.get('reasoning_version')) is not int or data['reasoning_version'] != REASONING_VERSION:
            raise AssistantError('추론 설정 형식이 변경되었습니다. 화면을 새로고침해 주세요.',409)
        key=opaque(data['client_key'])
        model = opaque(data['selection_id']) if 'selection_id' in data else None
        legacy_search=data.get('web_search')
        if 'web_search' in data and type(legacy_search) is not bool:
            raise AssistantError('웹 검색 사용 여부는 true/false여야 합니다.')
        owner, account = actor['UserId'], actor['account_key']
        if cid is None:
            # Bind retries to the submitted settings, even if the live model is later retired.
            fingerprint = digest(['first-turn-v1', content, data['level'], model, legacy_search, REASONING_VERSION])
            with store.db() as db:
                receipt = store.first_turn_receipt(db, owner, account, key, fingerprint)
            if receipt:
                return jsonify(success=True, conversation_id=receipt[0], job_id=receipt[1]), 202
        route, level, _ = selected(actor, opaque(cid) if cid is not None else None, model, data['level'])
        mail = explicit_mail(content)
        available=domain.search_service.available and bool(route['profile'].get('tools'))
        if not mail and legacy_search is True and not available:
            raise AssistantError('현재 서버 또는 선택한 모델에서 웹 검색을 사용할 수 없습니다.')
        route['web_search_mode']='required' if legacy_search is True else 'off' if legacy_search is False else 'auto'
        route['web_search_allowed']=available and legacy_search is not False
        expires = time.time() + min(1800, app.permanent_session_lifetime.total_seconds())
        if cid is None:
            new_cid, jid = store.enqueue_first(owner, account, content, level, key, actor['binding'], expires, route, fingerprint, mail=mail)
            return jsonify(success=True, conversation_id=new_cid, job_id=jid), 202
        jid=store.enqueue(owner,opaque(cid),content,level,key,actor['binding'],expires,account,route,mail=mail)
        return jsonify(success=True,job_id=jid),202

    @bp.get('/api/ai/status')
    @login
    def assistant_status():
        """[MINI-COMMENT: ASSISTANT.HTTP.STATUS]
        [EN rev.1]
        [Role] Supplies expiring app-local queue and selected-provider evidence to the title icon.
        [Dependencies] Current signed actor/menu authorization and passive read-only observations.
        [Impact] No model request, credential exposure or cross-service cancellation is introduced.
        """
        actor = browser()
        if set(request.args) - {'selection_id', 'job_id'} or any(len(request.args.getlist(key)) != 1 for key in request.args):
            raise AssistantError('AI 상태 요청을 확인해 주세요.')
        mid = opaque(request.args['selection_id']) if request.args.get('selection_id') else None
        jid = opaque(request.args['job_id']) if request.args.get('job_id') else None
        if not mid and not jid:
            mid = registry.choices()['default_model']
        return jsonify(success=True, **read_status(store, actor, mid, jid))

    @bp.get('/api/ai/jobs/<jid>')
    @login
    def job_view(jid):
        """[Role] Sends bounded text deltas with server code-point cursors, not repeated full histories.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser()
        try:
            ro,co=int(request.args.get('r','0')),int(request.args.get('c','0'))
            search_version=int(request.args.get('w','-1'))
            if not 0<=ro<=100000 or not 0<=co<=64000 or not -1<=search_version<=2:
                raise ValueError()
        except ValueError:
            raise AssistantError('응답 위치가 올바르지 않습니다.') from None
        with store.db() as db:
            job=store.job(jid,db,actor['UserId'],actor['account_key'])
            if job['purpose']=='probe':
                access=connect()
                try:
                    require_administrator_grant(access,actor)
                finally:
                    access.close()
            msg=db.execute("SELECT id,reasoning,content FROM messages WHERE job=? AND role='assistant'",(jid,)).fetchone()
            # Content may reset for a continuation. Steps lets the UI reset only the provisional answer.
            generation=job['steps']+(1 if job['state'] in ('running','draining','recovery_required') else 0)
            # The final mail footer may replace an already streamed prefix of the same length.
            if (job['state'] == 'done' and json.loads(job['route_snapshot'] or '{}').get('mail_translation')
                    and db.execute('SELECT 1 FROM message_steps WHERE job=? AND step=0 AND content<>?',
                                   (jid, msg['content'])).fetchone()):
                generation += 1
            if request.args.get('v')!=str(generation):
                co=0
            co=min(co,len(msg['content']))
            reasoning,content=msg['reasoning'][ro:ro+8192],msg['content'][co:co+8192]
            cards=[dict(r) for r in db.execute('SELECT id,job,operation,payload,before_json,state,result,expires FROM proposals WHERE job=? AND owner=? ORDER BY created',(jid,actor['UserId']))]
            answer_started=bool(db.execute("SELECT 1 FROM message_steps WHERE job=? AND content<>'' LIMIT 1",(jid,)).fetchone())
            web_searches=public_searches(job['context'])
            position=db.execute("SELECT COUNT(*)+1 FROM jobs WHERE state='queued' AND resource_group=? AND queue_order<?",(job['resource_group'],job['queue_order'])).fetchone()[0] if job['state']=='queued' else None
        return jsonify(success=True,id=jid,state=job['state'],error=job['error'],error_code=job['error_code'],steps=job['steps'],generation=generation,position=position,
            web_search_version=len(web_searches),web_searches=web_searches if search_version!=len(web_searches) else None,
            worker_stale=bool(job['heartbeat'] and job['state'] in ('running','draining') and time.time()-job['heartbeat']>45),
            message_id=msg['id'],reasoning=reasoning,content=content,r=ro+len(reasoning),c=co+len(content),
            content_length=len(msg['content']),reasoning_length=len(msg['reasoning']),proposals=cards,answer_started=answer_started,
            storage=store.storage_status(actor['UserId'],actor['account_key']),source=public_source(job['route_snapshot']))

    @bp.post('/api/ai/jobs/<jid>/cancel')
    @login
    def cancel(jid):
        """[Role] Cancels an owner-local job; there is no model/server kill endpoint.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(True)
        object_only(body(),())
        return jsonify(success=True,state=store.cancel(actor['UserId'],jid,actor['account_key']))

    @bp.post('/api/ai/proposals/<pid>/confirm')
    @login
    def confirm(pid):
        """[MINI-COMMENT: ASSISTANT.CONFIRM.HTTP]
        [EN rev.3]
        [Role] Requires a live owner's explicit CSRF-protected confirmation of frozen server content.
        [Dependencies] Current active-conversation execution gate and Domain's atomic business receipt transaction.
        [Impact] Trash blocks new confirmations; already admitted commits remain authoritative without duplicate writes.
        """
        actor=browser(True)
        if not enabled(app.config['USER_AI_WRITE_TOOLS']):
            raise AssistantError('현재 AI 변경 기능은 비활성 상태입니다.',403)
        object_only(body(),())
        with store.db() as db:
            row=db.execute('SELECT j.conversation FROM proposals p JOIN jobs j ON j.id=p.job JOIN conversations c ON c.id=j.conversation WHERE p.id=? AND p.owner=? AND c.account_key=?',(opaque(pid),actor['UserId'],actor['account_key'])).fetchone()
            if row is None:
                raise AssistantError('확인 항목을 찾을 수 없습니다.',404)
            cid=row['conversation']
        # Only this short local business transaction holds the lifecycle writer; no model/network wait runs here.
        with store.execution_gate(actor['UserId'],cid,actor['account_key']) as db:
            row=db.execute('SELECT * FROM proposals WHERE id=? AND owner=?',(opaque(pid),actor['UserId'])).fetchone()
            if row is None:
                raise AssistantError('확인 항목을 찾을 수 없습니다.',404)
            proposal=dict(row)
            job=store.job(proposal['job'],db,actor['UserId'],actor['account_key'])
            result=domain.execute(proposal,job)
            # Equipment commit is authoritative. A retry reads its receipt if this separate AI update rolls back.
            db.execute("UPDATE proposals SET state='applied',result=? WHERE id=?",(canonical(result),pid))
            display_result={k:v for k,v in result.items() if k!='replayed'}
            record='장비관리 서버 확인 완료 ['+pid+']: '+canonical(display_result)
            store.record_result(db,job,record)
            store.expire(db)
        return jsonify(success=True,result=result)

    @bp.post('/internal/ai/claim')
    def claim():
        """[Role] Supplies one private worker with minimal model context, including a bounded correction when the prior response completed.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        name = claim_worker()
        if not enabled(app.config.get('USER_AI_ENABLED')) or services['get_maintenance_state']()['state']!='NORMAL':
            g.routine_ai_worker = True
            return jsonify(success=True,job=None)
        if store is None:
            raise AssistantError('AI 도우미가 설정되지 않았습니다.', 404)
        job=store.claim(name)
        if job is None:
            g.routine_ai_worker = True
            return jsonify(success=True,job=None)
        try:
            actor=job_actor(job)
            route=json.loads(job['route_snapshot'])
            if not route or not job['selection_id']:
                raise AssistantError('이전 요청의 연결 식별을 확인하지 못했습니다. 관리자 확인이 필요합니다.',409)
            with store.db() as db:
                if 'candidate_generation' in route:
                    if job['purpose']!='probe':
                        raise AssistantError('후보 연결은 관리자 시험에만 사용할 수 있습니다.',403)
                    provider_candidates.check_probe(db,route)
                else:
                    current=db.execute('''SELECT p.enabled,p.retired,p.revision,m.present FROM ai_providers p
                        JOIN ai_provider_models m ON m.provider=p.id WHERE m.id=? AND p.id=?''',(job['selection_id'],route['provider_id'])).fetchone()
                    if not current or not current['enabled'] or current['retired'] or (current['revision']==route['revision'] and not current['present']):
                        raise AssistantError('접수한 모델/연결이 중지되어 요청을 실행하지 않았습니다.',409)
            trust,credential=registry.connection(route['provider_id'],route['revision'])
            RevisionPolicy(route['provider_id'],trust).destination(route['base_url'])
            route['trust']=trust
            route['api_key']=registry.secret(credential)
            route['legacy_worker_key']=credential=='env:USER_AI_STRATA_KEY' and not route['api_key']
            route.pop('credential',None)
            if 'mail_translation' in route:
                packet = translation_packet(job, route, PROTOCOL)
                response = jsonify(success=True, job=packet)
                g.routine_ai_worker = True
                return response
            planning=search_planning(job,route)
            correcting=correction_phase(job)
            search_allowed=search_permitted(job,route)
            searches_remaining=max(0,MAX_SEARCHES-len(public_searches(job['context'])))
            tools=domain.tools(actor,search_allowed and searches_remaining>0,planning) if route['profile'].get('tools') and correcting!='answer' else []
            # Copy only the advertised function, never mutate shared TOOL_MAP descriptions.
            tools=[{**t,'function':{**t['function'],'description':t['function']['description']+f' 현재 요청의 남은 검색은{searches_remaining}회입니다. 한 단계에 검색 하나만 요청하세요.'}}
                   if t['function']['name'] in ('web_search','plan_web_search') else t for t in tools]
            if tools and not planning:
                tools=[*tools,DRAFT_TOOL,TASK_DRAFT_TOOL]
            if not enabled(app.config['USER_AI_WRITE_TOOLS']):
                tools=[t for t in tools if not t['function']['name'].startswith('prepare_')]
            system=SYSTEM+'\n서울 기준 오늘 날짜: '+datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
            if search_allowed and searches_remaining==0:
                system+='\n현재 요청의 남은 웹 검색 횟수:0/2. 이미 수행한 검색 출처로 답하고 확인 한계를 알리세요. 추가 검색 도구는 제공하지 않습니다.'
            elif route.get('web_search_allowed') is True and not search_allowed and search_mode(route)=='auto':
                system+='\n현재 요청은 AI가 외부 검색 없이 처리하기로 결정했습니다. 검색을 했다고 주장하지 말고 기존 대화/장비 업무 도구로 처리하세요.'
            elif search_allowed and domain.search_service.available:
                system+='\n현재 요청 웹 검색: '+('허용됨. '+('반드시 web_search로 공개 키워드를 실제 검색한 뒤 답변하세요.' if searches_remaining==MAX_SEARCHES else '이미 받은 실제 출처를 우선 사용하고 필요한 경우에만 추가 검색하세요.')+' 비공개 정보가 필요하면 검색하지 말고 중단 사유를 알리세요.' if search_mode(route)=='required' else '자동. 질문 맥락상 최신 사실·외부 근거·공개 저장소/이슈 확인이 필요할 때 web_search를 사용하세요. 인사·일반 설명·내 장비 업무에 검색을 강제하지 마세요.')
                system+=f'\n현재 요청의 남은 웹 검색 횟수:{searches_remaining}/2. 한 단계에 검색 하나만 요청하세요. 미실행 제어 결과는 검색 근거가 아닙니다.'
                providers=getattr(domain.search_service,'providers',[])
                if providers:
                    system+='\n검색 제공자 상태: '+canonical(providers)+'. 사용 가능한 제공자만 선택하고 사용하지 않은 검색 엔진으로 검색했다고 주장하지 마세요.'
            else:
                system+='\n현재 요청 웹 검색: 사용 불가. 외부 검색을 수행하거나 검색했다고 주장하지 말고 현재 접수/모델/서버에서 검색이 제공되지 않음을 알리세요. 검색 버튼을 켜라고 안내하지 마세요.'
            if not route['profile'].get('tools'):
                system+='\n이 모델은 대화 전용입니다. 장비 작업 제안 도구를 호출하지 말고 업무 가능 모델 선택/수동 화면을 안내하세요.'
            output_tokens=min(8192,max(512,route['context_tokens']//4))
            overhead=len(canonical([{'role':'system','content':system},tools]).encode())+1024
            if job['purpose']=='probe':
                if 'candidate_generation' in route and not job['steps']:
                    # The nonce alone can fit even when a minimal equipment chat cannot. Check the
                    # normal local admission budget without sending equipment context to a candidate.
                    with store.db() as db:
                        try:
                            build_context(db,job,route['context_tokens']-output_tokens-overhead)
                        except AssistantError as error:
                            if error.status!=413:
                                raise
                            raise BeforeSendError(ERROR_REASONS['PROVIDER_CONTEXT'],'PROVIDER_CONTEXT') from None
                db=connect()
                try:
                    if db.execute('SELECT Role FROM users WHERE UserId=?',(actor['UserId'],)).fetchone()[0]!='admin':
                        raise AssistantError('관리자 시험 권한이 변경되었습니다.',403)
                finally:
                    db.close()
                stage=json.loads(job['probe_plan'])[job['steps']]
                nonce=route['probe_nonce']
                tools=[{'type':'function','function':{'name':'assistant_probe','description':'Inert capability test. Call exactly once with the nonce.',
                    'parameters':{'type':'object','properties':{'nonce':{'type':'string'}},'required':['nonce'],'additionalProperties':False}}}] if stage=='tools' else []
                context=[{'role':'user','content':('Call assistant_probe with nonce '+nonce if stage=='tools' else 'Reply with exactly '+nonce+'. This is an inert capability test.')}]
                effort_map=LEVELS if route['profile'].get('reasoning_version') == REASONING_VERSION else LEGACY_LEVELS
                route['reasoning_effort']=effort_map.get(stage)
                system='You are running an inert model capability test. No real equipment operations exist in this test.'
                output_tokens=512 if stage in ('chat','tools') else min(4096,max(512,route['context_tokens']//4))
            elif not job['steps']:
                with store.db(True) as db:
                    context=build_context(db,job,route['context_tokens']-output_tokens-overhead)
                    store.charge_handoff(db,job,context)
                    db.execute('UPDATE jobs SET context=? WHERE id=?',(canonical(context),job['id']))
            else:
                context=json.loads(job['context'])
            if correcting is not None:
                system+='\n'+CORRECTIONS[correcting]
            messages=[{'role':'system','content':system},*model_context(context)]
            if len(canonical([messages,tools]).encode())+output_tokens+512>route['context_tokens'] or len(canonical(context))>120000:
                raise AssistantError('선택한 모델의 문맥 한도로 작업을 중단했습니다. 기록을 확인하고 질문을 줄이거나 더 큰 모델을 선택해 주세요.',413)
            packet={'id':job['id'],'lease':job['lease'],'steps':job['steps'],'messages':messages,'tools':tools,
                    'reasoning_effort':route.get('reasoning_effort'),'route':route,'max_tokens':output_tokens,'protocol':PROTOCOL,
                    'required_tool':'plan_web_search' if planning else None,
                    'web_search_required':job['purpose']=='chat' and route.get('web_search_allowed') is True and search_mode(route)=='required' and not public_searches(context)}
            canonical(packet)
            response = jsonify(success=True, job=packet)
            g.routine_ai_worker = True
            return response
        except Exception as error:
            reason=str(error) if isinstance(error,AssistantError) else ERROR_REASONS['PROCESSING_FAILED']
            app.logger.warning('assistant pre-dispatch failure job=%s type=%s',job['id'],type(error).__name__)
            auth_failure=isinstance(error,AssistantError) and error.status in (401,403)
            try:
                code=error.code if isinstance(error,BeforeSendError) else 'AUTH_EXPIRED' if auth_failure else 'PROCESSING_FAILED'
                store.finish(job['id'],job['lease'],'cancelled' if auth_failure else 'failed',reason,error_code=code)
            except AssistantError as lifecycle_error:
                # No model was dispatched. A concurrent purge may have removed its job but must not strand its guard.
                if lifecycle_error.status not in (404,409) or store.guard_finish(job['id'],job['lease'],'failed') is None:
                    raise
            return jsonify(success=True,job=None)

    @bp.post('/internal/ai/jobs/<jid>/event')
    def event(jid):
        """[MINI-COMMENT: ASSISTANT.WORKER.EVENT]
        [EN rev.2]
        [Role] Stores active deltas or discards a trashed/purged request while its own response drains.
        [Dependencies] Worker authentication, a current job or minimal execution-guard lease and offset checks.
        [Impact] Late chunks cannot recreate deleted dialogue or release an unconfirmed upstream slot.
        """
        worker()
        data=object_only(body(262144),('lease','reasoning','content','reasoning_offset','content_offset'),('lease',))
        job,guarded=worker_lease_boundary(jid,data['lease'])
        if guarded is not None:
            return jsonify(success=True,**guarded)
        try:
            job_actor(job)
        except Exception as error:
            reason=str(error) if isinstance(error,AssistantError) else ERROR_REASONS['PROCESSING_FAILED']
            store.cancel(job['owner'],jid,error=reason,error_code='AUTH_EXPIRED' if isinstance(error,AssistantError) and error.status in (401,403) else 'PROCESSING_FAILED')
        if not enabled(app.config.get('USER_AI_ENABLED')):
            store.cancel(job['owner'],jid,error='AI 기능이 중지되어 이 작업을 중단했습니다.',error_code='USER_CANCELLED')
        accepted=False
        try:
            cancelled=store.append(jid,data['lease'],stream_text(data.get('reasoning','')),
                stream_text(data.get('content','')),data.get('reasoning_offset'),data.get('content_offset'))
            accepted=True
        except AssistantError as error:
            guarded=store.guard_event(jid,data['lease'])
            if guarded is not None:
                return jsonify(success=True,**guarded)
            store.cancel(job['owner'],jid,error=ERROR_REASONS['INVALID_RESPONSE']+' '+str(error),error_code='INVALID_RESPONSE')
            cancelled=True
        with store.db() as db:
            step=db.execute('SELECT length(reasoning) AS r,length(content) AS c FROM message_steps WHERE job=? AND step=?',(jid,job['steps'])).fetchone()
        if step is None:
            guarded=store.guard_event(jid,data['lease'])
            if guarded is not None:
                return jsonify(success=True,**guarded)
            raise AssistantError('응답 저장 위치를 확인할 수 없습니다.',409)
        g.routine_ai_worker = accepted and not cancelled and enabled(app.config.get('USER_AI_ENABLED'))
        return jsonify(success=True,accepted=accepted,reasoning_offset=step['r'],content_offset=step['c'],cancel=cancelled or not enabled(app.config.get('USER_AI_ENABLED')))

    @bp.post('/internal/ai/jobs/<jid>/finish')
    def finish(jid):
        """[MINI-COMMENT: ASSISTANT.WORKER.FINALIZE]
        [EN rev.7]
        [Role] Enforces search decisions and bounded correction for completed missing output or an explicitly terminated output-token limit.
        [Dependencies] Verified lease, optional typed termination evidence, immutable route and server correction context.
        [Impact] Mail translations have a single tool-free attempt and require DONE, stop and a complete-looking email. Ordinary correction and historical completion contracts are preserved.
        """
        def finished(state, **details):
            # Status is the committed job/guard outcome. An HTTP 200 alone cannot classify it.
            g.routine_ai_worker = state in ('done', 'queued') and not details.get('error_code') and not g.get('ai_tool_error', False)
            return jsonify(success=True, state=state, **details)

        worker()
        data=body(2097152)
        if not isinstance(data,dict) or 'lease' not in data:
            raise AssistantError('작업 완료 권한을 확인해 주세요.')
        outcome=data.get('outcome')
        if outcome in ('complete','failed','recovery_required','cancelled'):
            job,guarded=worker_lease_boundary(jid,data['lease'],outcome)
            if guarded is not None:
                return finished(guarded)
        else:
            with store.db() as db:
                job=store.lease(db,jid,data['lease'])
        known=outcome in ('complete','failed','cancelled')
        code='INVALID_RESPONSE'
        try:
            route=json.loads(job['route_snapshot'])
            termination=data.get('termination')
            if ('mail_translation' in route and outcome == 'complete'
                    and (not isinstance(termination, dict) or termination.get('done') is not True)):
                outcome, known, code = 'recovery_required', False, 'STREAM_INCOMPLETE'
            object_only(data,('lease','calls','content','reasoning','outcome','error_code','termination'),('lease','outcome'))
            if outcome not in ('complete','failed','recovery_required','cancelled'):
                raise AssistantError('작업 완료 상태가 올바르지 않습니다.')
            supplied=data.get('error_code')
            if supplied is not None and (not isinstance(supplied,str) or supplied not in ERROR_REASONS):
                raise AssistantError('작업 중단 사유 형식이 올바르지 않습니다.')
            if code == 'STREAM_INCOMPLETE':
                supplied = code
            if 'termination' in data:
                object_only(termination,('done','finish_reason'),('done','finish_reason'))
                if type(termination['done']) is not bool or termination['finish_reason'] not in (None,'stop','tool_calls','length','content_filter','unrecognized'):
                    raise AssistantError('응답 종료 확인 정보 형식이 올바르지 않습니다.')
            # Display output is evidence, even if the completed structured tool response is invalid.
            store.reconcile(jid,data['lease'],
                stream_text(data['reasoning'],MAX_REASONING) if 'reasoning' in data else None,
                stream_text(data['content'],MAX_CONTENT) if 'content' in data else None)
            if services['get_maintenance_state']()['state']!='NORMAL':
                store.cancel(job['owner'],jid,error='시스템 점검으로 이 작업을 중단했습니다.',error_code='PROCESSING_FAILED')
                return finished(store.finish(jid,data['lease'],'failed' if known else 'recovery_required',error_code='PROCESSING_FAILED'))
            if not enabled(app.config.get('USER_AI_ENABLED')) and outcome!='recovery_required':
                outcome='cancelled'
            # A DONE+length report is a known-ended model response, unlike character overflow,
            # timeout or an EOF without DONE. Discard incomplete calls; never execute them.
            if 'mail_translation' not in route and outcome=='failed' and supplied=='LENGTH_LIMIT' and termination=={'done':True,'finish_reason':'length'} and data.get('calls',[])==[] and job['purpose']=='chat':
                # Historical required-search jobs must not skip their still-unperformed search.
                if search_mode(route)!='required' or public_searches(job['context']):
                    try:
                        job_actor(job)
                    except AssistantError as error:
                        return finished(store.finish(jid,data['lease'],'cancelled',str(error),error_code='AUTH_EXPIRED'))
                    phase='search_plan' if search_planning(job,route) else 'answer'
                    corrected=correction_context(job,phase)
                    if corrected is not None and len(canonical(corrected))<=120000:
                        state=store.finish(jid,data['lease'],'queued',context=corrected)
                        if state=='queued':
                            app.logger.warning('assistant correction job=%s phase=%s trigger=token_limit step=%s',jid,phase,job['steps'])
                        return finished(state,response_correction=phase if state=='queued' else None)
            if outcome in ('failed','recovery_required','cancelled'):
                final_code=supplied or ('STREAM_INCOMPLETE' if outcome=='recovery_required' else 'USER_CANCELLED' if outcome=='cancelled' else 'PROCESSING_FAILED')
                return finished(store.finish(jid,data['lease'],outcome,
                    ERROR_REASONS[final_code],error_code=final_code))
            try:
                actor=job_actor(job)
            except AssistantError as error:
                return finished(store.finish(jid,data['lease'],'cancelled',str(error),error_code='AUTH_EXPIRED'))
            with store.db() as db:
                current=store.lease(db,jid,data['lease'])
            if current['cancel']:
                return finished(store.finish(jid,data['lease'],'cancelled'))
            if 'mail_translation' in route:
                state, error_code, reason = translation_completion(job, route['mail_translation'], data)
                state = store.finish(jid, data['lease'], state, reason, error_code=error_code)
                return finished(state)
            if job['purpose']=='probe':
                stage=json.loads(job['probe_plan'])[job['steps']]
                calls=data.get('calls',[])
                nonce=route['probe_nonce']
                if stage=='tools':
                    if not isinstance(calls,list) or len(calls)!=1 or calls[0].get('name')!='assistant_probe' or json.loads(calls[0].get('arguments','{}'))!={'nonce':nonce}:
                        raise AssistantError('구조화 도구 시험에 실패했습니다.')
                else:
                    effort_map=LEVELS if route['profile'].get('reasoning_version') == REASONING_VERSION else LEGACY_LEVELS
                    effort=effort_map.get(stage)
                    invalid=calls or nonce not in data.get('content','') or (effort not in (None,'none') and not data.get('reasoning')) or (effort=='none' and data.get('reasoning'))
                    if invalid:
                        raise AssistantError('대화/추론 출력 시험에 실패했습니다.')
                plan=json.loads(job['probe_plan'])
                last=job['steps']==len(plan)-1
                if last:
                    profile={**route['profile'],'chat':True,'tools':'tools' in plan,'levels':[s for s in plan if s in LEVELS],
                             'evidence':'내부 자원 그룹 큐에서 nonce 대화/구조화 도구/추론 출력 시험 통과. 컨텍스트 한도는 관리자 검증값.'}
                    if profile.get('reasoning_version') == REASONING_VERSION:
                        profile['verified_levels']=profile['levels']
                    profile=normalize_profile(route['model'],route['adapter'],profile)
                    with store.db(True) as db:
                        live=store.lease(db,jid,data['lease'])
                        store.conversation(live['owner'],live['conversation'],db,live['account_key'])
                        if live['cancel']:
                            raise AssistantError('시험이 중단되어 설정을 갱신하지 않았습니다.',409)
                        access=connect()
                        try:
                            require_administrator_grant(access,actor)
                        finally:
                            access.close()
                        if 'candidate_generation' in route:
                            provider_candidates.record_proof(db,route,profile,actor['UserId'])
                            return finished(store.finish(jid,data['lease'],'done',transaction=db))
                        version=db.execute('''SELECT p.revision,m.profile_revision FROM ai_providers p JOIN ai_provider_models m ON m.provider=p.id
                            JOIN ai_provider_trust t ON t.provider=p.id AND t.revision=p.revision
                            WHERE m.id=? AND p.retired=0 AND p.enabled=1 AND t.revoked IS NULL''',(job['selection_id'],)).fetchone()
                        if not version or tuple(version)!=(route['revision'],route['profile_revision']):
                            raise AssistantError('시험 중 연결 설정이 변경되었습니다. 현재 설정에서 다시 시험해 주세요.',409)
                        db.execute('UPDATE ai_provider_models SET profile=?,verified_revision=?,profile_revision=profile_revision+1,checked=? WHERE id=?',(canonical(profile),route['revision'],time.time(),job['selection_id']))
                return finished(store.finish(jid,data['lease'],'done' if last else 'queued'))
            code='INVALID_TOOL_CALL'
            calls=data.get('calls',[])
            if not isinstance(calls,list) or len(calls)>4:
                raise AssistantError('도구 호출 수를 확인해 주세요.')
            planning=search_planning(job,route)
            correcting=correction_phase(job)
            if planning and not calls:
                corrected=correction_context(job,'search_plan')
                if corrected is None:
                    raise WebSearchError('WEB_SEARCH_PLAN_RECOVERY_FAILED')
                if len(canonical(corrected))>120000:
                    code='LENGTH_LIMIT'
                    raise ValueError('correction context limit')
                state=store.finish(jid,data['lease'],'queued',context=corrected)
                if state=='queued':
                    app.logger.warning('assistant correction job=%s phase=search_plan step=%s',jid,job['steps'])
                return finished(state,response_correction='search_plan' if state=='queued' else None)
            if planning and len(calls)!=1:
                raise WebSearchError('WEB_SEARCH_PLAN_REQUIRED')
            if correcting=='answer' and calls:
                raise AssistantError('답변 보정 단계에서는 새로운 작업 도구를 실행할 수 없습니다.')
            prepared=[]
            ids=set()
            # Validate the entire response before allowing even its first tool to prepare a card.
            for call in calls:
                object_only(call,('id','name','arguments'),('id','name','arguments'))
                cid=text(call['id'],100)
                if cid in ids:
                    raise AssistantError('도구 호출 식별자가 중복되었습니다.')
                ids.add(cid)
                name=text(call['name'],100)
                if planning and name!='plan_web_search':
                    raise WebSearchError('WEB_SEARCH_PLAN_REQUIRED')
                if not planning and name=='plan_web_search':
                    raise AssistantError('이 단계에서는 검색 계획 도구를 사용할 수 없습니다.')
                allowed={**TOOL_MAP,'save_equipment_draft':DRAFT_TOOL['function'],'save_task_draft':TASK_DRAFT_TOOL['function']}
                if not route['profile'].get('tools') or name not in allowed:
                    raise AssistantError('제공되지 않은 작업 도구가 요청되었습니다.')
                arguments=text(call['arguments'],16384)
                args=json.loads(arguments)
                if name in TOOL_MAP:
                    args=normalized_tool_arguments(name,args)
                else:
                    validate_schema(args,allowed[name]['parameters'])
                prepared.append((cid,name,arguments,args))
            search_count=sum(name in ('web_search','plan_web_search') for _,name,_,_ in prepared)
            search_only=bool(prepared) and all(name=='web_search' for _,name,_,_ in prepared)
            if search_count>1 and not search_only:
                raise AssistantError('웹 검색은 한 단계에 한 번씩 요청해 주세요.')
            # Search failure must occur before even preparing an unrelated business confirmation card.
            prepared.sort(key=lambda item: item[1] not in ('web_search','plan_web_search'))
            context=json.loads(job['context'])
            searches_used=len(public_searches(context))
            searches_this_step=0
            if search_only and searches_used>=MAX_SEARCHES:
                raise WebSearchError('WEB_SEARCH_LIMIT')
            if search_only and search_count>1:
                # Validate every public query/actor boundary without I/O before the
                # first child can run; a later private query must not discard an earlier search.
                for _,name,_,args in prepared:
                    domain.read_or_prepare(name,args,job,store,search_control=max(0,MAX_SEARCHES-searches_used-1))
            content=stream_text(data.get('content',''),MAX_CONTENT)
            code='PROCESSING_FAILED'
            if route.get('web_search_allowed') is True and search_mode(route)=='required' and not public_searches(context) and not any(name=='web_search' for _,name,_,_ in prepared):
                raise WebSearchError('WEB_SEARCH_REQUIRED')
            if not prepared and not content.strip():
                corrected=correction_context(job,'answer')
                if corrected is None:
                    code='EMPTY_RESPONSE'
                    raise ValueError('empty completed answer after correction')
                if len(canonical(corrected))>120000:
                    code='LENGTH_LIMIT'
                    raise ValueError('correction context limit')
                state=store.finish(jid,data['lease'],'queued',context=corrected)
                if state=='queued':
                    app.logger.warning('assistant correction job=%s phase=answer step=%s',jid,job['steps'])
                return finished(state,response_correction='answer' if state=='queued' else None)
            if prepared:
                assistant={'role':'assistant','content':content,'tool_calls':[]}
                results=[]
                for cid,name,arguments,args in prepared:
                    # A previous tool may have overlapped a user's trash action. Do not admit the next one.
                    with store.db() as db:
                        live=store.lease(db,jid,data['lease'])
                        store.conversation(live['owner'],live['conversation'],db,live['account_key'])
                    if live['cancel']:
                        return finished(store.finish(jid,data['lease'],'cancelled'))
                    job=live
                    try:
                        if name.startswith('prepare_') and not enabled(app.config['USER_AI_WRITE_TOOLS']):
                            raise AssistantError('현재 변경 제안 기능은 비활성 상태입니다.',403)
                        if name in ('save_equipment_draft','save_task_draft'):
                            operation={'create':'equipment_create','update':'equipment_update'}.get(args['operation'],args['operation'])
                            actor=job_actor(job)
                            if 'prepare_'+operation not in {t['function']['name'] for t in domain.tools(actor)}:
                                raise AssistantError('이 업무 초안을 저장할 권한이 없습니다.',403)
                            draft_fields=args['fields'] if name=='save_equipment_draft' else json.loads(args['fields_json'])
                            if not isinstance(draft_fields,dict):
                                raise AssistantError('업무 초안 필드는 객체여야 합니다.')
                            if draft_fields.get('equipment_id'):
                                db=connect()
                                try:
                                    domain.own(db,actor,draft_fields['equipment_id'],True)
                                finally:
                                    db.close()
                            result=store.save_draft(job,args)
                        elif name=='web_search' and search_only and searches_this_step:
                            # One eight-second child fits the finish HTTP timeout. Correlate every
                            # remaining read call without executing it or fabricating source evidence.
                            result=domain.read_or_prepare(name,args,job,store,search_control=max(0,MAX_SEARCHES-searches_used))
                        else:
                            result=domain.read_or_prepare(name,args,job,store)
                    except (AssistantError,InputError,LineupNodeError) as error:
                        g.ai_tool_error = True
                        # A legitimate business validation (for example an unknown equipment ID) is data for the answer.
                        result={'error':str(error)}
                    assistant['tool_calls'].append({'id':cid,'type':'function','function':{'name':name,'arguments':arguments}})
                    result_text=canonical(result)
                    search_result=name in ('web_search','plan_web_search') and isinstance(result,dict) and result.get('kind')=='web_search'
                    if search_result:
                        searches_this_step+=1
                        searches_used+=1
                    if search_result and len(result_text)>32000:
                        raise WebSearchError('WEB_SEARCH_UNAVAILABLE')
                    if not search_result and len(result_text)>16000:
                        result_text=canonical({'error':'조회 결과가 많습니다. 검색 조건을 좁혀 주세요.'})
                    results.append({'role':'tool','tool_call_id':cid,'content':result_text})
                context.extend([assistant,*results])
            else:
                context.append({'role':'assistant','content':content})
            if len(canonical(context))>120000:
                raise AssistantError('대화 자료가 길어 작업을 중단했습니다. 저장된 내용을 확인하고 새 대화로 이어 주세요.')
            return finished(store.finish(jid,data['lease'],'queued' if prepared else 'done',context=context))
        except Exception as error:
            # A trusted worker already reported completion: rejecting its syntax must still release its lease.
            if outcome in ('complete','failed','recovery_required','cancelled'):
                guarded=store.guard_finish(jid,data['lease'],outcome)
                if guarded is not None:
                    return finished(guarded)
            reason=ERROR_REASONS[code]
            if isinstance(error,WebSearchError):
                code=error.code
                reason=str(error)
            elif isinstance(error,(AssistantError,InputError,LineupNodeError)):
                reason+=' '+str(error)
            app.logger.warning('assistant stopped job=%s code=%s type=%s',jid,code,type(error).__name__)
            state=store.finish(jid,data['lease'],'failed' if known else 'recovery_required',reason,error_code=code)
            return finished(state,error_code=code,message=reason)

    @bp.post('/internal/ai/jobs/<jid>/acknowledge-finished')
    def acknowledge(jid):
        """[Role] Lets an operator acknowledge only a recovered own request, never stop another service.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        worker()
        data=object_only(body(),('acknowledgement',),('acknowledgement',))
        if data['acknowledgement']!='OWN_REQUEST_CONFIRMED_FINISHED':
            raise AssistantError('자체 요청 종료 확인이 필요합니다.',409)
        store.acknowledge_finished(jid)
        return jsonify(success=True)

    @bp.route('/api/ai/equipment/<int:eid>/files',methods=['POST'])
    @login
    def upload(eid):
        """[Role] Attaches one explicitly selected file after live user/menu/owner checks, using existing validators.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(True)
        domain.require_menu(actor,'my_equipment')
        if not enabled(app.config['USER_AI_WRITE_TOOLS']):
            raise AssistantError('변경 기능이 비활성 상태입니다.',403)
        if request.content_length is None or request.content_length>10*1024*1024+65536:
            raise AssistantError('파일 크기를 확인해 주세요.',413)
        storage=files.storage_directory(services['ROADMAP_ATTACHMENT_ROOT'])
        db=connect()
        stored=None
        committed=False
        try:
            db.execute('BEGIN IMMEDIATE')
            actor=domain.actor(db,actor['UserId'],actor['binding'])
            domain.own(db,actor,eid,True)
            if len(request.files)!=1 or 'file' not in request.files:
                raise AssistantError('파일 하나를 선택해 주세요.')
            stored=files.add_attachment(db,storage,eid,actor['UserId'],request.files['file'])
            db.commit()
            committed=True
            return jsonify(success=True,id=stored['id'],name=stored['name'])
        finally:
            if not committed:
                db.rollback()
                if stored:
                    files.stored_path(storage,stored['storage_key']).unlink(missing_ok=True)
            db.close()

    @bp.get('/api/ai/equipment/<int:eid>/files/<int:fid>/download')
    @login
    def download(eid,fid):
        """[Role] Provides only a current owner's permitted attachment, without exposing a storage path.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser()
        db=connect()
        try:
            domain.own(db,actor,eid,True)
            row=db.execute('SELECT storage_key,original_name,mime_type FROM equipment_files WHERE id=? AND equipment_id=? AND deleted_at IS NULL',(fid,eid)).fetchone()
            if row is None:
                raise AssistantError('첨부를 찾을 수 없습니다.',404)
            path=files.stored_path(services['ROADMAP_ATTACHMENT_ROOT'],row['storage_key'])
            response=send_file(path,as_attachment=True,download_name=row['original_name'],mimetype=row['mime_type'],conditional=False)
            response.headers['Content-Security-Policy']="sandbox; default-src 'none'"
            return response
        finally:
            db.close()

    @bp.post('/api/ai/csv/preview')
    @login
    def csv_preview():
        """[Role] Creates an owner-bound existing CSV preview token; raw file content never enters a prompt.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(True)
        domain.require_menu(actor,'my_equipment')
        if not enabled(app.config['USER_AI_WRITE_TOOLS']):
            raise AssistantError('변경 기능이 비활성 상태입니다.',403)
        if request.content_length is None or request.content_length>1024*1024+65536 or len(request.files)!=1 or 'file' not in request.files:
            raise AssistantError('1MiB 이하 CSV 파일 하나를 선택해 주세요.',413)
        upload=request.files['file']
        if not upload.filename.lower().endswith('.csv'):
            raise AssistantError('CSV 파일을 선택해 주세요.')
        db=connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            actor=domain.actor(db,actor['UserId'],actor['binding'])
            domain.require_menu(actor,'my_equipment')
            raw=upload.stream.read(equipment.CSV_LIMIT+1)
            result=equipment.preview_import(db,raw,actor)
            db.commit()
            return jsonify(success=True,**result)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @bp.get('/api/ai/csv/export')
    @login
    def csv_export():
        """[Role] Exports an explicitly user-scoped list; an admin login never expands the public CSV scope.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser()
        scope=request.args.get('scope','my')
        if scope not in ('my','public'):
            raise AssistantError('내보내기 범위가 올바르지 않습니다.')
        domain.require_menu(actor,'my_equipment' if scope=='my' else 'public_equipment')
        db=connect()
        try:
            rows=equipment.list_equipment(db,{'type':scope},actor,paginated=False,export=True)
            raw=equipment.export_csv(rows)
            preserve_export(store,app.config['USER_AI_AUDIT_ROOT'],raw,actor,scope,len(rows),int(app.config['USER_AI_AUDIT_MAX_BYTES']))
            response=Response(raw,content_type='text/csv; charset=utf-8')
            response.headers['Content-Disposition']='attachment; filename="equipment.csv"'
            return response
        finally:
            db.close()

    @bp.post('/api/ai/csv/commit')
    @login
    def csv_commit():
        """[Role] Confirms the original CSV token once using current owner/menu checks and atomic audit.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        actor=browser(True)
        domain.require_menu(actor,'my_equipment')
        if not enabled(app.config['USER_AI_WRITE_TOOLS']):
            raise AssistantError('변경 기능이 비활성 상태입니다.',403)
        data=object_only(body(),('token',),('token',))
        db=connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            actor=domain.actor(db,actor['UserId'],actor['binding'])
            domain.require_menu(actor,'my_equipment')
            result=equipment.commit_import(db,text(data['token'],128),actor)
            db.commit()
            return jsonify(success=True,**result)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.register_blueprint(bp)
