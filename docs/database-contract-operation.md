# Database contract v1 운영 안내

현재 필수 모델은 equipments → equipment_options → lineup_nodes다. equipment는 1차 전환에서 보존하며 삭제하지 않는다. 정상 연결은 FK ON을 강제하고 백업·복원은 schema version과 구조의 의미 계약을 비교한다.

## 사용자 동작

카테고리·제조사를 삭제할 때 노드·장비·옵션·대기 승인 참조가 남아 있으면 409와 건수를 표시한다. 일괄 삭제는 전부 또는 전무로 처리한다. 참조를 옮기려면 기존 수정 화면의 통폐합을 사용한다. 대상과 원본 모두 승인되어야 하며 대기 승인이나 중복 루트가 있으면 먼저 정리해야 한다.

노드·옵션·장비 ID와 독립 장비 감사 기록은 보존한다. 사용자 영구 삭제 시 비밀번호 재설정 토큰을 함께 제거한다. 결재 반려가 사용 중인 카탈로그를 삭제하려 하면 대기 상태로 rollback하고 원인을 안내한다.

## Linux 검증 및 적용

Git remote가 main을 fetch하는지 확인하고 승인 commit으로 fast-forward한다. 기존 서비스가 있으면 기존 실행 방식을 확인하여 종료/재기동하며, 아래 start는 빈 포트에서만 시작한다.

```bash
cd /home/nekohost/services/Mini-Server-Web-EqMgmt
git pull --ff-only
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
.venv/bin/python tools/database_release.py check-copy \
  --database /home/nekohost/services/Mini-Server-Web-EqMgmt/equipment.db \
  --backups /home/nekohost/.local/share/mini-server-eqmgmt/release-20260912
```

check-copy는 실제 DB를 mode=ro로 조회하고 사본에서 기동·migration·행 지문·down/up·조회 계획을 검증한다. 앱 프로세스가 없는 상태에서 start에 동일 DB·backups와 --expected-head의 전체 commit SHA를 전달하면 변경 전 사본을 남기고 기존 app.py 방식으로 기동한다. /login 200이 기동 확인이며 인증되지 않은 /api/check_session 401은 정상이다. 자동 재기동 서비스 등록은 이번 변경에 포함하지 않았다.

복구 사본과 JSON 증거는 제한된 디렉터리에 보존된다. 코드만 되돌려도 새 인덱스는 이전 코드와 공존한다. DB down이 필요하면 서비스를 중지하고 utils.database_contract.rollback_contract(database_path, backup_root)를 호출한다. 이는 v1 인덱스 4개·명명 이력 1개·user_version만 되돌리며 업무 행과 감사 테이블을 보존한다. 기존 down_migration.py는 평탄화 보관 기능이며 v1 rollback을 대신하지 않는다.

컬럼 물리 순서 이외의 정의 차이는 자동 허용하지 않는다. 새로운 제약·컬럼·뷰·트리거를 추가할 때 버전과 신규 DB/역사 DB 호환성 테스트를 함께 갱신해야 한다.
