"""전체 ZIP을 새 격리 폴더에 검증 복구하는 운영 도구; 운영 DB는 교체하지 않습니다."""
import argparse
import json
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.database_contract import connect_database, assert_contract_version, assert_integrity
from utils.roadmap_files import prepare_archive, restore_missing_files


def validate(connection):
    """[역할] 파일/FK/DDL 버전 검증. [의존성 관계] 실제 DB 계약. [변경 시 영향도] 부분 스키마 거부."""
    assert_integrity(connection)
    if assert_contract_version(connection) != 3:
        raise ValueError('full restore requires schema 3')


def main():
    """[역할] 격리 복구 후 선택적 불변 첨부 보충. [의존성 관계] 운영자의 명시 경로. [변경 시 영향도] 덮어쓰기/서비스 변경 없음."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--destination', required=True, help='존재하지 않는 새 격리 디렉터리')
    parser.add_argument('--attachment-root', help='명시한 경우에만 검증된 첨부를 기존 저장소에 보충. 기존 파일을 덮어쓰지 않음.')
    options = parser.parse_args()
    if os.name != 'posix':
        parser.error('Linux에서만 실행합니다.')
    destination = prepare_archive(Path(options.archive).resolve(strict=True), options.destination, connect_database, validate)
    count = restore_missing_files(destination / 'attachments', options.attachment_root) if options.attachment_root else 0
    print(json.dumps({'verified': True, 'database_candidate': str(destination / 'equipment.db'), 'attachments_added': count,
                      'next': '점검 모드에서 기존 관리자 DB 후보 검증/복원 절차를 진행하십시오.'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
