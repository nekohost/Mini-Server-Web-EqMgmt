"""010: 비공개 불변 파일 저장소와 DB+첨부 manifest 백업/복구 후보."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import uuid
import zipfile
from utils.roadmap_validation import InputError, text_value
from utils.roadmap_equipment import audit, utc_now

FILE_LIMIT = 10 * 1024 * 1024
USER_QUOTA = 512 * 1024 * 1024  # 삭제 보관본도 포함하여 반복 업로드의 디스크 소진을 제한합니다.
ARCHIVE_LIMIT = 2 * 1024 * 1024 * 1024
KEY = re.compile(r'[a-f0-9]{32}\.(?:png|jpg|pdf)\Z')


def storage_directory(value):
    """[역할] 전용 root 보호. [의존성 관계] 서버 설정. [변경 시 영향도] static 외부만 사용."""
    root = Path(value).absolute()
    if root.is_symlink():
        raise ValueError('attachment root must not be a symlink')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root.resolve()


def stored_path(root, key):
    """[역할] 저장키와 root 경계 검사. [의존성 관계] 모든 파일 읽기/쓰기. [변경 시 영향도] traversal/symlink 차단."""
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError('invalid attachment key')
    target = Path(root) / key
    if target.is_symlink() or target.resolve().parent != Path(root).resolve():
        raise ValueError('attachment path boundary violation')
    return target


def detect_file(raw, filename, declared_type):
    """[역할] 확장자/MIME/파일 서명 교차검사. [의존성 관계] 업로드. [변경 시 영향도] 안전한 다운로드 전용, 악성코드 검사 아님."""
    filename = text_value(filename, '파일명', 200, True)
    if '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
        raise InputError('파일명에 경로나 제어문자를 사용할 수 없습니다.')
    extension = Path(filename).suffix.lower()
    if not raw or len(raw) > FILE_LIMIT:
        raise InputError('파일은 1바이트~10MiB여야 합니다.', 413)
    kind = None
    if extension == '.png' and raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 45 and raw[12:16] == b'IHDR' and raw[-12:] == b'\x00\x00\x00\x00IEND\xaeB`\x82':
        width, height = struct.unpack('>II', raw[16:24])
        if width and height and width * height <= 40000000:
            kind = ('png', 'image/png')
    elif extension in ('.jpg', '.jpeg') and raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9'):
        kind = ('jpg', 'image/jpeg')
    elif extension == '.pdf' and re.match(rb'%PDF-(?:1\.[0-7]|2\.0)[\r\n]', raw) and raw.rstrip().endswith(b'%%EOF'):
        kind = ('pdf', 'application/pdf')
    if kind is None or declared_type not in (kind[1], '', 'application/octet-stream'):
        raise InputError('서명과 확장자가 일치하는 PNG/JPEG/PDF만 첨부할 수 있습니다.')
    return filename, *kind


def add_attachment(connection, root, equipment_id, user_id, upload):
    """[역할] 검증→불변 파일→transaction 매핑. [의존성 관계] route 보상 정리. [변경 시 영향도] rollback 시 새 파일만 제거."""
    if connection.execute('SELECT COUNT(*) FROM equipment_files WHERE equipment_id=? AND deleted_at IS NULL', (equipment_id,)).fetchone()[0] >= 50:
        raise InputError('장비당 활성 첨부는 최대 50개입니다.', 409)
    raw = upload.stream.read(FILE_LIMIT + 1)
    name, extension, mime = detect_file(raw, upload.filename, upload.mimetype or '')
    used = connection.execute('SELECT COALESCE(SUM(size_bytes),0) FROM equipment_files WHERE uploaded_by=?', (user_id,)).fetchone()[0]
    if used + len(raw) > USER_QUOTA:
        raise InputError('삭제 보관본을 포함한 사용자 첨부 한도 512MiB를 초과했습니다.', 413)
    if shutil.disk_usage(root).free < len(raw) + 64 * 1024 * 1024:
        raise InputError('첨부 저장 공간이 부족합니다.', 507)
    key = uuid.uuid4().hex + '.' + extension
    path = stored_path(root, key)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        digest = hashlib.sha256(raw).hexdigest()
        cursor = connection.execute('''INSERT INTO equipment_files(equipment_id,storage_key,original_name,mime_type,size_bytes,sha256,uploaded_by,created_at)
            VALUES(?,?,?,?,?,?,?,?)''', (equipment_id, key, name, mime, len(raw), digest, user_id, utc_now()))
        audit(connection, equipment_id, 'ATTACH_FILE', user_id, None, {'file_id': cursor.lastrowid, 'name': name, 'sha256': digest})
        return {'id': cursor.lastrowid, 'name': name, 'storage_key': key}
    except Exception:
        path.unlink(missing_ok=True)  # 이 요청이 방금 생성한 UUID 파일만 보상합니다.
        raise


def assert_files(connection, root):
    """[역할] DB가 참조하는 불변 첨부 해시 전수 확인. [의존성 관계] backup/restore. [변경 시 영향도] DB-only 누락 복원 차단."""
    rows = connection.execute('SELECT storage_key,size_bytes,sha256 FROM equipment_files').fetchall()
    for key, size, digest in rows:
        path = stored_path(root, key)
        if not path.is_file() or path.stat().st_size != size:
            raise ValueError('required attachment missing or size mismatch')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('required attachment hash mismatch')
    return rows


def build_archive(database_path, root, archive_path, connect):
    """[역할] 일관된 DB snapshot + 모든 보존 첨부 + manifest. [의존성 관계] create_online_backup. [변경 시 영향도] DB-only와 구분."""
    connection = connect(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = assert_files(connection, root)
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        if sum(row[1] for row in rows) + Path(database_path).stat().st_size > ARCHIVE_LIMIT:
            raise InputError('전체 백업은 2GiB 이하만 지원합니다.', 413)
        entries = []
        with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_STORED) as archive:
            os.chmod(archive_path, 0o600)
            for name, path in [('equipment.db', Path(database_path)), *[('attachments/' + row[0], stored_path(root, row[0])) for row in rows]]:
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                archive.write(path, name)
                entries.append({'path': name, 'size': path.stat().st_size, 'sha256': digest})
            archive.writestr('manifest.json', json.dumps({'format': 'eqmgmt-full-backup-v1', 'schema_version': version,
                'created_at': utc_now(), 'files': entries}, ensure_ascii=False))
        return {'files': len(entries), 'schema_version': version, 'size': Path(archive_path).stat().st_size}
    finally:
        connection.close()


def prepare_archive(archive_path, destination, connect, validate_database):
    """[역할] 전체 ZIP을 새 격리 디렉터리에 검증 복구. [의존성 관계] 복구 CLI. [변경 시 영향도] 운영 DB 교체 없음."""
    destination = Path(destination).absolute()
    if destination.exists():
        raise ValueError('restore destination must be new')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 100002 or 'manifest.json' not in names or 'equipment.db' not in names:
            raise ValueError('invalid full backup entries')
        infos = archive.infolist()
        if any(info.flag_bits & 1 for info in infos) or sum(info.file_size for info in infos) > ARCHIVE_LIMIT:
            raise ValueError('full backup size/encryption unsupported')
        if archive.getinfo('manifest.json').file_size > 16 * 1024 * 1024:
            raise ValueError('manifest too large')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 'eqmgmt-full-backup-v1' or manifest.get('schema_version') != 3:
            raise ValueError('unsupported full backup format')
        entries = manifest.get('files')
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ValueError('invalid manifest')
        mapped = {entry.get('path'): entry for entry in entries}
        if len(mapped) != len(entries) or set(mapped) != set(names) - {'manifest.json'}:
            raise ValueError('manifest entry mismatch')
        for name, entry in mapped.items():
            if name != 'equipment.db' and (not name.startswith('attachments/') or not KEY.fullmatch(name[12:])):
                raise ValueError('unsafe archive path')
            if type(entry.get('size')) is not int or entry['size'] != archive.getinfo(name).file_size or not re.fullmatch('[a-f0-9]{64}', str(entry.get('sha256'))):
                raise ValueError('invalid manifest metadata')
        destination.mkdir(mode=0o700)  # 부모는 운영자가 지정한 기존 workspace여야 합니다.
        attachments = storage_directory(destination / 'attachments')
        for name, entry in mapped.items():
            target = destination / 'equipment.db' if name == 'equipment.db' else stored_path(attachments, name[12:])
            digest = hashlib.sha256()
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with archive.open(name) as source, os.fdopen(descriptor, 'wb') as out:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != entry['sha256']:
                raise ValueError('full backup content mismatch; isolated evidence retained')
        connection = connect((destination / 'equipment.db').as_uri() + '?mode=ro', uri=True)
        try:
            validate_database(connection)  # 실제 DDL/버전/FK를 검사합니다.
            rows = assert_files(connection, attachments)
            if {'equipment.db', *('attachments/' + row[0] for row in rows)} != set(mapped):
                raise ValueError('archive/database attachment map mismatch')
        finally:
            connection.close()
    return destination  # 실패 사본도 이 격리 경로에 남기며 기존 데이터를 지우지 않습니다.


def restore_missing_files(source, target):
    """[역할] 검증된 첨부를 기존 불변 저장소에 보충. [의존성 관계] 복구 CLI 명시 옵션. [변경 시 영향도] 덮어쓰기/DB 교체 없음."""
    target = storage_directory(target)
    restored = 0
    for path in Path(source).iterdir():
        destination = stored_path(target, path.name)
        with path.open('rb') as stream:
            expected = hashlib.file_digest(stream, 'sha256').hexdigest()
        if destination.exists():
            with destination.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('existing attachment conflicts; never overwritten')
            continue
        temporary = target / (uuid.uuid4().hex + '.partial')
        try:
            with path.open('rb') as incoming, temporary.open('xb') as out:
                os.chmod(temporary, 0o600)
                shutil.copyfileobj(incoming, out)
                out.flush()
                os.fsync(out.fileno())
            os.link(temporary, destination)  # 완성한 파일만 no-overwrite 방식으로 공개합니다.
            restored += 1
        finally:
            temporary.unlink(missing_ok=True)
    return restored
