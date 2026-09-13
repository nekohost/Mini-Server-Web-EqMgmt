"""제안 묶음 HTTP 통합. 기존 로그인/CSRF/점검/DB 연결 정책을 재사용합니다."""
from contextlib import closing
from functools import wraps
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from flask import Blueprint, current_app, g, jsonify, request, session, send_file, Response
from utils import roadmap_equipment as equipment, roadmap_files as files, roadmap_auth as auth
from utils.roadmap_validation import InputError, json_object, text_value, integer, password, login_id, email_address, equipment_fields, specs, flag, day


def deadline_values(data, old=None):
    """[역할] 신규/수정의 기한 기본값과 날짜 역전 확인. [의존성 관계] 기존 CRUD. [변경 시 영향도] 누락은 유지/빈값은 삭제."""
    old = old or {}
    warranty = day(data.get('WarrantyEndDate', data.get('warranty_end_date', old.get('warranty_end_date'))), '보증 종료일')
    replacement = day(data.get('ReplacementDueDate', data.get('replacement_due_date', old.get('replacement_due_date'))), '교체 예정일')
    purchase = day(data.get('PurchaseDate', data.get('purchase_date', old.get('purchase_date'))), '구입일')
    if purchase and any(value and value < purchase for value in (warranty, replacement)):
        raise InputError('보증/교체 기한은 구입일보다 빠를 수 없습니다.')
    return warranty, replacement


def validate_payload(endpoint, value):
    """[역할] 기존 endpoint별 공통 입력 검증. [의존성 관계] before_request. [변경 시 영향도] 기존 로그인 강도 유지."""
    data = dict(json_object(value))
    if endpoint in ('add_equipment', 'update_equipment', 'api_equipments_v2'):
        return equipment_fields(data)
    if endpoint == 'login_page':
        data['LoginId'] = text_value(data.get('LoginId'), '아이디', 256, True, trim=False)
        data['Password'] = password(data.get('Password'))
    if endpoint == 'register_page':
        data['LoginId'] = login_id(data.get('LoginId'))
        for key in ('Name', 'NickName'):
            data[key] = text_value(data.get(key), key, 100, True)
        data['Password'] = password(data.get('Password'), new=True)
        data['Email'] = email_address(data.get('Email'))
    for key in ('current_password', 'password', 'CurrentPassword'):
        if key in data:
            data[key] = password(data[key])
    if endpoint in ('api_change_my_password', 'api_reset_password_logic', 'api_reset_user_password'):
        if endpoint != 'api_reset_user_password' or 'new_password' in data:
            data['new_password'] = password(data.get('new_password'), new=True)
    if endpoint == 'api_reset_user_password':
        data['temp_password'] = password(data.get('temp_password'), new=True)
    if endpoint == 'api_update_profile':
        candidate = text_value(data.get('login_id'), '아이디', 256, True)
        data['login_id'] = candidate if candidate == session.get('user', {}).get('LoginId') else login_id(candidate)
        data['name'] = text_value(data.get('name'), '이름', 100, True)
        data['nickname'] = text_value(data.get('nickname'), '닉네임', 100, True)
    for key in ('email', 'Email', 'new_email'):
        if key in data:
            data[key] = email_address(data[key])
    if endpoint == 'api_verify_pin_logic':
        data['pin'] = text_value(data.get('pin'), 'PIN', 6, True)
        if not re.fullmatch('[0-9]{6}', data['pin']):
            raise InputError('PIN은 숫자 6자리여야 합니다.')
    if 'token' in data:
        data['token'] = text_value(data['token'], '토큰', 256, True)
    if endpoint.startswith('lineup_node_management_candidate.') or endpoint in ('create_equipment_option', 'manage_equipment_option', 'get_or_create_master_management_item', 'update_or_delete_master_item'):
        for key in ('Name', 'NameKo', 'NameEn', 'name', 'option_name'):
            if key in data:
                data[key] = text_value(data[key], key, 100, key in ('Name', 'name', 'option_name'))
        for key in ('parent_id', 'category_id', 'manufacturer_id', 'lineup_node_id', 'target_parent_id'):
            if data.get(key) is not None:
                data[key] = integer(data[key], key)
        if 'specs' in data:
            json_object(data['specs'], '사양', 16384)
        if 'specs_json' in data:
            data['specs_json'] = specs(data['specs_json'])
    return data


def install_roadmap(app, services):
    """[역할] 기존 app에 guarded API/설정/검증 연결. [의존성 관계] 모든 route 정의 후. [변경 시 영향도] 운영은 승격 후만 적용."""
    blueprint = Blueprint('roadmap', __name__)
    get_connection = services['get_db_connection']
    login_required = services['login_required']
    csrf_required = services['csrf_required']
    admin_required = services['admin_required']
    root = Path(services['ROADMAP_ATTACHMENT_ROOT']).resolve()
    if root == Path(app.static_folder).resolve() or Path(app.static_folder).resolve() in root.parents:
        raise ValueError('attachment storage must be outside static')
    guarded = set(auth.POLICIES) | {'add_equipment', 'update_equipment', 'api_equipments_v2', 'api_update_email', 'api_update_profile',
        'api_reset_user_password', 'api_user_settings', 'create_equipment_option', 'manage_equipment_option',
        'get_or_create_master_management_item', 'update_or_delete_master_item'}

    @app.errorhandler(InputError)
    def invalid_input(error):
        """[역할] 예상 오류 응답. [의존성 관계] 입력/권한 서비스. [변경 시 영향도] 내부 예외 은닉."""
        return jsonify(success=False, error=str(error), message=str(error)), error.status

    @app.errorhandler(413)
    def oversized(error):
        """[역할] 요청 크기 실패 안내. [의존성 관계] Flask per-request limit. [변경 시 영향도] chunked body 포함."""
        return jsonify(success=False, error='요청 또는 파일 크기 제한을 초과했습니다.', message='요청 또는 파일 크기 제한을 초과했습니다.'), 413

    @app.before_request
    def validate_and_limit():
        """[역할] 타입 검증 및 인증 한도 연결. [의존성 관계] 기존 점검 gate 다음. [변경 시 영향도] 파일/DB 전용 크기 독립."""
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return None
        endpoint = request.endpoint or ''
        if endpoint in ('roadmap.upload_attachment', 'roadmap.csv_preview'):
            request.max_content_length = (files.FILE_LIMIT if endpoint.endswith('upload_attachment') else equipment.CSV_LIMIT) + 65536
            request.max_form_parts = 4
            request.max_form_memory_size = 65536
            return None  # CSRF와 로그인은 decorator에서 body보다 먼저 확인합니다.
        if endpoint not in guarded and not endpoint.startswith(('lineup_node_management_candidate.', 'roadmap.')):
            return None
        request.max_content_length = 65536  # Flask 3.1의 실제 stream 제한입니다.
        original = request.get_json(silent=True) if request.is_json else dict(request.form) if endpoint == 'login_page' else None
        data = validate_payload(endpoint, original if original is not None else {} if endpoint == 'roadmap.full_backup' else original)
        if isinstance(original, dict):
            original.clear()
            original.update(data)  # public get_json cache를 공유하여 기존 view에서도 같은 검증값을 읽습니다.
        g.roadmap_payload = data
        if endpoint in auth.POLICIES:
            if endpoint != 'login_page' and (not request.headers.get('X-CSRFToken') or request.headers.get('X-CSRFToken') != session.get('csrf_token')):
                raise InputError('CSRF 토큰 검증에 실패했습니다.', 403)
            account = str(data.get('LoginId') or data.get('email') or data.get('Email') or session.get('user', {}).get('UserId') or '')
            peer = auth.peer_address(request, os.getenv('AUTH_TRUSTED_PROXY_CIDRS', '127.0.0.1/32,::1/128'))
            with closing(get_connection()) as connection:
                connection.execute('BEGIN IMMEDIATE')
                retry = auth.consume(connection, endpoint, account, peer, app.secret_key)
                connection.commit()
            if retry:
                response = jsonify(success=False, message='인증 요청이 많습니다. 잠시 후 다시 시도해 주세요.', retry_after=retry)
                response.status_code = 429
                response.headers['Retry-After'] = str(retry)
                response.headers['Cache-Control'] = 'no-store'
                return response
        return None

    def actor(connection):
        """[역할] 새 API의 현재 DB 역할/계정 검사. [의존성 관계] login_required. [변경 시 영향도] 오래된 세션 권한 차단."""
        row = connection.execute('SELECT UserId,LoginId,Role,IsDeleted,IsDeactivated FROM users WHERE UserId=?', (session['user']['UserId'],)).fetchone()
        if not row or row['IsDeleted'] == 'Y' or row['IsDeactivated'] == 'Y':
            raise InputError('사용할 수 없는 계정입니다.', 403)
        return dict(row)

    def transaction(write=False):
        """[역할] route의 connection/commit/rollback 통일. [의존성 관계] Blueprint. [변경 시 영향도] 부분 저장 차단."""
        def decorate(function):
            """[역할] route wrapper 생성. [의존성 관계] transaction. [변경 시 영향도] endpoint 이름 보존."""
            @wraps(function)
            def run(*args, **kwargs):
                """[역할] transaction 실행. [의존성 관계] actor. [변경 시 영향도] 감사 실패도 rollback."""
                with closing(get_connection()) as connection:
                    try:
                        connection.execute('BEGIN IMMEDIATE' if write and request.method != 'GET' else 'BEGIN')
                        result = function(connection, actor(connection), *args, **kwargs)
                        connection.commit()
                        return result
                    except InputError:
                        connection.rollback()
                        raise
                    except (sqlite3.Error, OSError, ValueError) as error:
                        connection.rollback()
                        error_id = uuid.uuid4().hex[:12]
                        app.logger.error('roadmap request failed id=%s endpoint=%s type=%s', error_id, request.endpoint, type(error).__name__)
                        return jsonify(success=False, message='작업을 완료하지 못했습니다. 새로고침 후 다시 시도해 주세요.', error_id=error_id), 500
            return run
        return decorate

    @login_required
    @transaction()
    def equipment_list(connection, user):
        """[역할] 기존 배열/선택 페이지 계약. [의존성 관계] 목록 UI/WebMCP. [변경 시 영향도] 필터 없는 배열 보존."""
        paginated = request.args.get('paginated') == '1'
        result = equipment.list_equipment(connection, request.args, user, paginated=paginated)
        return jsonify(result)

    app.view_functions['get_equipment'] = equipment_list

    @blueprint.get('/api/equipment/<int:equipment_id>/lifecycle')
    @login_required
    @transaction()
    def lifecycle(connection, user, equipment_id):
        """[역할] 상태·기한·이력 상세. [의존성 관계] 독립 감사. [변경 시 영향도] 공개 장비에 내부 변경 사유 비공개."""
        row = equipment.require_equipment(connection, equipment_id, user)
        writable = equipment.can_write(row, user)
        history = []
        if writable:
            before_id = integer(request.args.get('before_id', 2147483647), '이력 커서')
            history = [dict(item) for item in connection.execute("SELECT id,old_value,new_value,changed_by,changed_at FROM equipments_audit_log WHERE equipment_id=? AND action_type='STATUS_CHANGE' AND id<? ORDER BY id DESC LIMIT 100", (equipment_id, before_id))]
            for item in history:
                item['before'] = json.loads(item.pop('old_value') or '{}')
                item['after'] = json.loads(item.pop('new_value') or '{}')
        return jsonify(success=True, equipment=row, states=equipment.STATES, transitions=equipment.TRANSITIONS.get(row['status'], ()) if writable and not row['is_draft'] else (),
                       writable=writable, history=history, next_before_id=history[-1]['id'] if len(history) == 100 else None)

    @blueprint.post('/api/equipment/<int:equipment_id>/status')
    @login_required
    @csrf_required
    @transaction(write=True)
    def update_status(connection, user, equipment_id):
        """[역할] 상태 전이 route. [의존성 관계] CSRF/revision/audit. [변경 시 영향도] 이력과 저장 원자성."""
        return jsonify(success=True, **equipment.change_status(connection, equipment_id, user, g.roadmap_payload))

    @blueprint.get('/api/equipment/<int:equipment_id>/files')
    @login_required
    @transaction()
    def attachment_list(connection, user, equipment_id):
        """[역할] 허가된 메타데이터만 조회. [의존성 관계] 장비 공개 범위. [변경 시 영향도] 저장키 숨김."""
        equipment.require_equipment(connection, equipment_id, user)
        return jsonify(success=True, files=[dict(row) for row in connection.execute('SELECT id,original_name,mime_type,size_bytes,created_at FROM equipment_files WHERE equipment_id=? AND deleted_at IS NULL ORDER BY id DESC', (equipment_id,))])

    @blueprint.post('/api/equipment/<int:equipment_id>/files')
    @login_required
    @csrf_required
    def upload_attachment(equipment_id):
        """[역할] 파일/DB 보상 transaction. [의존성 관계] 검증된 storage root. [변경 시 영향도] commit 실패 시 새 파일 제거."""
        stored = None
        committed = False
        with closing(get_connection()) as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                user = actor(connection)
                equipment.require_equipment(connection, equipment_id, user, write=True)
                upload = request.files.get('file')
                if upload is None or len(request.files) != 1:
                    raise InputError('파일 한 개를 선택해 주세요.')
                stored = files.add_attachment(connection, files.storage_directory(root), equipment_id, user['UserId'], upload)
                connection.commit()
                committed = True
                return jsonify(success=True, id=stored['id'], name=stored['name'])
            except InputError:
                connection.rollback()
                raise
            except (OSError, sqlite3.Error, ValueError) as error:
                connection.rollback()
                app.logger.error('attachment upload failed type=%s', type(error).__name__)
                return jsonify(success=False, message='첨부 저장에 실패했습니다.'), 500
            finally:
                if stored and not committed:
                    files.stored_path(root, stored['storage_key']).unlink(missing_ok=True)

    @blueprint.get('/api/equipment/<int:equipment_id>/files/<int:file_id>/download')
    @login_required
    @transaction()
    def download_attachment(connection, user, equipment_id, file_id):
        """[역할] 매번 권한 확인 후 attachment 전송. [의존성 관계] 불변 저장소. [변경 시 영향도] 공개 해제 즉시 반영."""
        equipment.require_equipment(connection, equipment_id, user)
        row = connection.execute('SELECT * FROM equipment_files WHERE id=? AND equipment_id=? AND deleted_at IS NULL', (file_id, equipment_id)).fetchone()
        if not row:
            raise InputError('첨부를 찾을 수 없습니다.', 404)
        path = files.stored_path(root, row['storage_key'])
        if not path.is_file():
            raise InputError('첨부 파일을 찾을 수 없습니다. 관리자에게 복구를 요청해 주세요.', 404)
        response = send_file(path, as_attachment=True, download_name=row['original_name'], mimetype=row['mime_type'], conditional=False)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'"
        return response

    @blueprint.delete('/api/equipment/<int:equipment_id>/files/<int:file_id>')
    @login_required
    @csrf_required
    @transaction(write=True)
    def delete_attachment(connection, user, equipment_id, file_id):
        """[역할] 첨부 tombstone과 감사 보존. [의존성 관계] 장비 소유자. [변경 시 영향도] 원본은 전체 백업/복구를 위해 보관."""
        equipment.require_equipment(connection, equipment_id, user, write=True)
        row = connection.execute('SELECT id,original_name,sha256 FROM equipment_files WHERE id=? AND equipment_id=? AND deleted_at IS NULL', (file_id, equipment_id)).fetchone()
        if not row:
            raise InputError('첨부를 찾을 수 없습니다.', 404)
        connection.execute('UPDATE equipment_files SET deleted_at=? WHERE id=?', (equipment.utc_now(), file_id))
        equipment.audit(connection, equipment_id, 'DELETE_ATTACHMENT', user['UserId'], dict(row), None)
        return jsonify(success=True, message='첨부를 목록에서 삭제했습니다. 원본은 복구용으로 보관됩니다.')

    @blueprint.get('/api/equipment/csv/export')
    @login_required
    @transaction()
    def csv_export(connection, user):
        """[역할] 현재 범위/필터 전체 CSV. [의존성 관계] SQL 공통 권한. [변경 시 영향도] 현재 페이지뿐 아니라 총 필터 결과."""
        rows = [] if request.args.get('template') == '1' else equipment.list_equipment(connection, request.args, user, paginated=False, export=True)
        response = Response(equipment.export_csv(rows), content_type='text/csv; charset=utf-8')
        response.headers['Content-Disposition'] = 'attachment; filename="equipment.csv"'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @blueprint.post('/api/equipment/csv/preview')
    @login_required
    @csrf_required
    @transaction(write=True)
    def csv_preview(connection, user):
        """[역할] 행별 검증과 15분 preview. [의존성 관계] 파일/행 상한. [변경 시 영향도] 장비 생성 없음."""
        upload = request.files.get('file')
        if not upload or not upload.filename.lower().endswith('.csv'):
            raise InputError('CSV 파일을 선택해 주세요.')
        return jsonify(success=True, **equipment.preview_import(connection, upload.stream.read(equipment.CSV_LIMIT + 1), user))

    @blueprint.post('/api/equipment/csv/commit')
    @login_required
    @csrf_required
    @transaction(write=True)
    def csv_commit(connection, user):
        """[역할] 명시 확인 토큰 확정. [의존성 관계] 동일 사용자/idempotency. [변경 시 영향도] all-or-none."""
        return jsonify(success=True, **equipment.commit_import(connection, g.roadmap_payload.get('token'), user))

    @login_required
    @csrf_required
    @transaction(write=True)
    def settings_route(connection, user):
        """[역할] 기존 설정에 스킨/명시 수신 동의 병합. [의존성 관계] PreferencesJSON. [변경 시 영향도] 다른 설정 보존."""
        row = connection.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=?', (user['UserId'],)).fetchone()
        try:
            settings = json.loads(row[0] or '{}') if row else {}
            if not isinstance(settings, dict):
                settings = {}
        except (ValueError, TypeError):
            settings = {}
        if request.method == 'POST':
            data = g.roadmap_payload
            if 'layout_skin' in data and data['layout_skin'] not in ('standard', 'edge'):
                raise InputError('레이아웃은 standard 또는 edge만 선택할 수 있습니다.')
            if 'theme' in data and data['theme'] not in ('light', 'dark', 'system'):
                raise InputError('올바른 테마를 선택해 주세요.')
            if 'deadline_email_opt_in' in data:
                if type(data['deadline_email_opt_in']) is not bool:
                    raise InputError('이메일 수신 동의는 true/false여야 합니다.')
                if data['deadline_email_opt_in'] and not connection.execute('SELECT 1 FROM users u WHERE u.UserId=? AND u.Email IS NOT NULL AND (u.notification_verified_email=u.Email OR EXISTS(SELECT 1 FROM email_verifications v WHERE v.Email=u.Email AND v.IsVerified=1))', (user['UserId'],)).fetchone():
                    raise InputError('먼저 본인의 이메일 인증을 완료해 주세요.')
            settings.update(data)
            json_object(settings, '설정')
            connection.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?) ON CONFLICT(UserId) DO UPDATE SET PreferencesJSON=excluded.PreferencesJSON,UpdatedAt=excluded.UpdatedAt',
                               (user['UserId'], json.dumps(settings, ensure_ascii=False), equipment.utc_now()))
        settings['layout_skin'] = settings.get('layout_skin') if settings.get('layout_skin') in ('standard', 'edge') else 'standard'
        settings['deadline_email_opt_in'] = settings.get('deadline_email_opt_in') is True
        return jsonify(success=True, settings=settings)

    app.view_functions['api_user_settings'] = settings_route

    @blueprint.post('/api/admin/database/full-backup')
    @login_required
    @admin_required
    @csrf_required
    def full_backup():
        """[역할] 점검 중 DB+모든 보관 첨부 ZIP. [의존성 관계] 기존 온라인 백업/감사. [변경 시 영향도] DB-only 병행."""
        if services['get_maintenance_state']()['state'] not in ('DRAINING', 'RECOVERY'):
            raise InputError('전체 백업은 점검 모드에서만 가능합니다.', 409)
        with closing(get_connection()) as connection:
            user = actor(connection)
            if user['Role'] != 'admin':
                raise InputError('관리자 권한이 필요합니다.', 403)
            size = connection.execute('SELECT COALESCE(SUM(size_bytes),0) FROM equipment_files').fetchone()[0]
        services['ensure_database_operation_space'](size + 2 * os.path.getsize(services['DATABASE_PATH']) + 64 * 1024 * 1024)
        directory = Path(services['ensure_database_operation_directories']()['backups'])
        key = 'equipment-full-' + uuid.uuid4().hex
        db_path, archive_path = directory / (key + '.db'), directory / (key + '.zip')
        try:
            services['create_online_backup'](db_path)
            summary = files.build_archive(db_path, root, archive_path, services['connect_database'])
            services['write_database_operation_audit']('DOWNLOAD_FULL_BACKUP', user['LoginId'], summary)
            services['write_database_operation_journal']('DOWNLOAD_FULL_BACKUP', user['LoginId'], summary)
            response = send_file(archive_path, as_attachment=True, download_name=key + '.zip', mimetype='application/zip', conditional=False)
            response.headers['Cache-Control'] = 'no-store'
            response.direct_passthrough = False
            response.call_on_close(lambda: services['remove_database_operation_file'](archive_path))
            return response
        except Exception as error:
            services['remove_database_operation_file'](archive_path)
            app.logger.error('full backup failed type=%s', type(error).__name__)
            return jsonify(success=False, message='전체 백업을 완료하지 못했습니다. 첨부와 저장 공간을 확인해 주세요.'), 500
        finally:
            services['remove_database_operation_file'](db_path)

    app.register_blueprint(blueprint)
