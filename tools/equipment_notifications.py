"""Linux 예약 작업. 기본은 dry-run; --send를 명시해야 실제 메일을 보냅니다."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 승격된 프로젝트 utils만 import합니다.
from utils.database_contract import connect_database, assert_contract_version
from utils.roadmap_notifications import run_notifications
from utils.mailer import send_email
from utils.roadmap_job_lock import notification_lock


def main():
    """[역할] 단일 Linux job/명시 DB/발송 옵션. [의존성 관계] cron+flock. [변경 시 영향도] Flask import/서비스 기동 없음."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--maintenance-state', required=True)
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--retry-unknown', action='store_true', help='메일 배달 여부를 사람이 확인한 뒤만 사용. 중복 발송 가능.')
    options = parser.parse_args()
    if os.name != 'posix':
        parser.error('Linux에서만 실행합니다.')
    database = Path(options.database).resolve(strict=True)
    with notification_lock(database):  # 복원도 같은 lock을 사용합니다.
        def connect():
            """[역할] 기존 DB만 연결. [의존성 관계] FK/timeout. [변경 시 영향도] 오타 경로의 빈 DB 생성 방지."""
            state = json.loads(Path(options.maintenance_state).read_text(encoding='utf-8'))
            if state.get('state') != 'NORMAL':
                raise ValueError('notifications paused during maintenance')  # fail-closed로 다음 예약 시 재확인합니다.
            return connect_database(database.as_uri() + '?mode=rw', uri=True, timeout=30)
        connection = connect()
        try:
            if assert_contract_version(connection) != 3:
                raise ValueError('notifications require schema 3')
        finally:
            connection.close()
        print(json.dumps(run_notifications(connect, send_email, dry_run=not options.send, retry_unknown=options.retry_unknown)))


if __name__ == '__main__':
    main()
