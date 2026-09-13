"""008: 수신 동의/검증 주소/일별 발송 원장. 실제 예약 실행은 Linux CLI만 사용합니다."""
from contextlib import closing
import html
import json
import os
from utils.roadmap_equipment import due_badge, kst_today, utc_now


def configured():
    """[역할] 실제 발송 자격 설정. [의존성 관계] 기존 Graph mailer. [변경 시 영향도] 미설정 서버는 UI만 제공."""
    return all(os.getenv(key) for key in ('MS_TENANT_ID', 'MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MAIL_SENDER_ADDRESS'))


def opted_in(value):
    """[역할] 명시 true만 동의. [의존성 관계] PreferencesJSON. [변경 시 영향도] 잘못된/레거시 값은 미동의."""
    try:
        settings = json.loads(value or '{}')
        return isinstance(settings, dict) and settings.get('deadline_email_opt_in') is True
    except (TypeError, ValueError):
        return False


def run_notifications(connect, send_email, dry_run=True, retry_unknown=False, today=None, mail_configured=None):
    """[역할] 기한 알림 1회 실행. [의존성 관계] CLI flock, shared ledger. [변경 시 영향도] 기본 dry-run/실패 재발송 명시."""
    today = today or kst_today()
    summary = {'eligible': 0, 'sent': 0, 'skipped': 0, 'unknown': 0, 'dry_run': dry_run}
    with closing(connect()) as connection:
        rows = connection.execute('''SELECT e.id,e.name,e.user_id,e.warranty_end_date,e.replacement_due_date,u.Email,s.PreferencesJSON
            FROM equipments e JOIN users u ON u.UserId=e.user_id JOIN user_settings s ON s.UserId=u.UserId
            WHERE COALESCE(e.is_draft,0)=0 AND e.status<>'DISPOSED' AND COALESCE(u.IsDeleted,'N')='N'
            AND COALESCE(u.IsDeactivated,'N')='N' AND u.Email IS NOT NULL AND (u.notification_verified_email=u.Email OR EXISTS(SELECT 1 FROM email_verifications v WHERE v.Email=u.Email AND v.IsVerified=1))''').fetchall()
    for equipment_id, name, user_id, warranty, replacement, address, preferences in rows:
        if not opted_in(preferences):
            continue
        for kind, due in (('warranty', warranty), ('replacement', replacement)):
            days = due_badge(due, today)['days']
            if days not in (30, 7, 1, 0):
                continue  # 매일 스팸 대신 30/7/1/당일 네 시점만 안내합니다.
            summary['eligible'] += 1
            if dry_run or not (configured() if mail_configured is None else mail_configured):
                summary['skipped'] += 1
                continue
            key = (equipment_id, user_id, kind, due, today.isoformat())
            with closing(connect()) as connection:
                connection.execute('BEGIN IMMEDIATE')
                # 직전 실행이 비정상 종료했다면 SENDING은 자동으로 다시 보내지 않습니다.
                old = connection.execute('SELECT state,attempts FROM equipment_notification_log WHERE equipment_id=? AND user_id=? AND kind=? AND due_date=? AND send_day=?', key).fetchone()
                if old and (old[0] == 'SENT' or old[1] >= 3 or not retry_unknown):
                    connection.rollback()
                    summary['skipped'] += 1
                    continue
                fresh = connection.execute('''SELECT u.Email,s.PreferencesJSON,e.warranty_end_date,e.replacement_due_date
                    FROM equipments e JOIN users u ON u.UserId=e.user_id JOIN user_settings s ON s.UserId=u.UserId
                    WHERE e.id=? AND e.user_id=? AND e.is_draft=0 AND e.status<>'DISPOSED' AND u.IsDeleted='N' AND u.IsDeactivated='N'
                    AND u.Email IS NOT NULL AND (u.notification_verified_email=u.Email OR EXISTS(SELECT 1 FROM email_verifications v WHERE v.Email=u.Email AND v.IsVerified=1))''', (equipment_id, user_id)).fetchone()
                if not fresh or not opted_in(fresh[1]) or fresh[2 if kind == 'warranty' else 3] != due:
                    connection.rollback()
                    summary['skipped'] += 1
                    continue
                address = fresh[0]
                connection.execute('''INSERT INTO equipment_notification_log(equipment_id,user_id,kind,due_date,send_day,state,updated_at)
                    VALUES(?,?,?,?,?,'SENDING',?) ON CONFLICT(equipment_id,user_id,kind,due_date,send_day)
                    DO UPDATE SET state='SENDING',attempts=attempts+1,updated_at=excluded.updated_at''', (*key, utc_now()))
                connection.commit()  # 외부 메일 호출 전에 claim을 확정합니다.
            try:
                success, message = send_email(address, '[미니서버] 장비 기한 알림',
                    '<p>' + html.escape(name) + ': ' + ('보증 종료' if kind == 'warranty' else '교체 예정') + ' ' + html.escape(due) + '</p><p>수신 설정은 마이페이지에서 변경할 수 있습니다.</p>')
            except Exception:
                success = False  # 원문 이메일/오류를 출력하지 않습니다.
            state = 'SENT' if success else 'UNKNOWN'  # 응답 유실은 배달 실패로 단정하지 않습니다.
            with closing(connect()) as connection:
                connection.execute('UPDATE equipment_notification_log SET state=?,updated_at=? WHERE equipment_id=? AND user_id=? AND kind=? AND due_date=? AND send_day=?', (state, utc_now(), *key))
                connection.commit()
            summary['sent' if success else 'unknown'] += 1
    return summary
