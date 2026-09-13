# 미구현 제안 일괄 스테이징 후보

work_id: WORK-20260913-ROADMAP-BATCH-STAGING

이 폴더는 운영 소스 기준 `62a933f9e0e1c81dc25b050d823604a6c6db6956`의 **overlay 후보**다. 독립 실행 환경이 아니며 Windows에서 Flask/DB를 구동하지 않는다. 운영 루트, 운영 DB, 서비스, Git commit/push는 이번 작업에서 변경하지 않았다.

## 스테이징 구현 범위

| 제안 | 구현 후보 | 사용 위치 |
|---|---|---|
| 002 | 공통 JSON/타입/길이/날짜/비밀번호/노드·옵션 입력 검증 | 가입·프로필·비밀번호·장비·관리자 마스터 API |
| 007 | 공유 SQLite 인증 버킷, 만료 정리, 계정+IP 및 IP 제한, 429/Retry-After | 로그인/PIN/재설정/계정 변경 |
| 022·033 | 상태 전이, revision 경합 방어, 사유·행위자 이력, 실제 상태 통계 | 장비 목록의 `상태/첨부`, 대시보드 |
| 023 | 복합 필터, 공식명/전체 경로/제조사 별칭 검색, 서버 페이지·정렬, URL 복원 | 나의 장비·공개 장비 |
| 010 | PNG/JPEG/PDF 첨부, 권한 다운로드, 삭제 보관, DB+첨부 전체 ZIP/검증 복구 도구 | `상태/첨부`, 관리자 DB 백업 |
| 008 | 보증 종료/교체 예정일, 서울 날짜 배지, 명시 수신 동의, 중복 방지 메일 job 후보 | 등록/수정·목록·상세·마이페이지 |
| 019 | Standard/Edge 공통 UI 스킨, 계정별 설정 저장 | 마이페이지의 화면 및 기한 알림 |
| 026 | BOM CSV export/양식/미리보기/행별 오류/명시 확정/원자적 import·동일 토큰 재시도 | 장비 목록 상단 |

별도 계획(app.py 전체 주석 재구축, 변경형 WebMCP, systemd 서비스화)은 제외했다. 기존 공식 모델명·제조사·카탈로그 수정 선택 복원·옵션 관리 기능은 보존했다. 루트 제안/로드맵의 운영 완료 표시는 아직 변경하지 않는다.

## 계약과 제한

- GET `/api/equipment`의 기본 배열 응답은 유지하며, 화면은 `paginated=1`의 `{items,total,page,per_page,pages}`를 사용한다. CSV는 같은 권한/필터의 **전체 결과**, 최대 10,000건이다. 페이지는 25/50/100개이며 서버 상한 100이다.
- 상태는 ACTIVE(정상), LOANED(대여), REPAIR(수리), DISPOSED(폐기). 폐기→정상은 사유가 필요한 복구 전이다. 알 수 없는 기존 상태는 원본을 유지하며 자동 변환하지 않는다. 내부 상태 사유/행위자 이력은 소유자·관리자만 조회한다.
- 수정창을 열 때 revision을 보관한다. 상태 변경은 revision 필수이고, 기존 CRUD 클라이언트는 선택 필드로 호환한다. 생략된 수정 기한/메모/시리얼/공개 여부는 유지하고 빈 날짜는 해제한다.
- 일반 사용자의 신규 옵션은 기존 승인 서비스에 연결한다. 신규 장비는 승인 대기 임시저장이 되고, 승인 후 임시저장함에서 정식 등록한다. 정식 장비 수정에는 승인된 옵션만 연결한다.
- 신규 비밀번호는 8~256자, 영문·숫자·특수문자 조합. 기존 비밀번호 로그인은 강도 재검사하지 않는다. 새/변경 ID는 3~64자 영문·숫자·_.@- 조합이며, 기존 case-sensitive 로그인/UNIQUE 정책은 유지한다.
- 인증은 성공/실패를 포함한 시도 한도다. 로그인 10회/계정+IP, 60회/IP/15분. PIN 발송·재설정 요청은 3회/계정+IP, 20회/IP/15분, PIN 검증 5회/계정+IP, 40회/IP/15분. 전체 정책은 `utils/roadmap_auth.py`에 명시했다. 초과 요청으로 만료를 연장하지 않는다.
- Flask 3.1 이상 요청별 body 제한을 사용한다. 백업 서버 설치 버전은 읽기 전용 조회에서 3.1.3이었다. `requirements.txt`에 기존 설치 의존성을 명시했으며 이번에 설치/업데이트한 패키지는 없다. [Flask 공식 요청 크기 제한 계약](https://flask.palletsprojects.com/en/stable/api/#flask.Request.max_content_length).
- `AUTH_TRUSTED_PROXY_CIDRS` 기본값은 loopback이다. 실제 peer가 이 범위일 때만 ProxyFix 전달 IP를 한도 키로 사용한다. LAN 프록시라면 배포 시 실제 프록시의 좁은 주소 범위를 설정해야 하며 LAN 전체를 자동 신뢰하지 않는다.
- `EQUIPMENT_ATTACHMENT_ROOT` 기본값은 `instance/equipment-files`. static 외부, 디렉터리 0700, 파일 0600, UUID 키. 파일당 10MiB, 장비당 활성 50개, 업로더별 삭제 보관본 포함 512MiB. PNG/JPEG/PDF 확장자·MIME·서명 검사이며 악성코드 검사/완전한 문서 파싱은 아니다. 브라우저 inline 렌더 대신 attachment/nosniff로 내려준다.
- 장비 또는 첨부 삭제 시 파일은 복구용으로 보관하고 다운로드를 차단한다. 물리 purge는 구현하지 않았으며 별도 보존 정책 없이 자동 삭제하지 않는다. 전체 ZIP은 보관 첨부까지 포함하고 최대 2GiB다. 기존 DB 업로드 상한 512MiB는 유지한다.
- CSV는 UTF-8/BOM, 헤더 순서 `Name,OptionId,SerialNumber,PurchaseDate,WarrantyEndDate,ReplacementDueDate,IsPublic,Memo`. 파일 1MiB/500행, 미리보기 15분/사용자당 5개. 정식 승인된 OptionId만 사용한다. `IsPublic`은 0/1이며 자신의 장비만 신규 생성한다. 수식 방어용 apostrophe는 import 때 임의 제거하지 않는다. preview에 오류가 있으면 확정 토큰을 발급하지 않는다.
- 수신 동의 기본값은 false. 검증된 현재 이메일로 서울 날짜 기준 30/7/1일 전·당일만 알린다. 이메일 변경 때 인증 기록이 소비되는 기존 흐름을 위해 `users.notification_verified_email`을 추가했다. 기존 인증 증거가 없으면 같은 본인 이메일을 다시 인증해야 한다.
- 메일은 SMTP/Graph와 SQLite의 분산 transaction이 아니다. SENDING/UNKNOWN은 자동 재발송하지 않고 운영자가 전달 여부를 확인한 뒤 `--retry-unknown`으로 최대 3회까지 재시도할 수 있다. 실제 발송/예약 등록은 이번에 하지 않았다.

## DB v3 / 복구

기존 v0/v1/v2→v3를 private snapshot 뒤 한 transaction으로 적용한다. equipments에 revision·두 기한, users에 인증 주소를 추가하고 첨부·인증 제한·CSV 요청·알림 원장을 추가한다. 기존 사용자/장비/노드/옵션/감사 ID는 보존하며 공식명은 재작성하지 않는다. 반영 실패는 이력·PRAGMA 버전까지 rollback한다.

v3 데이터가 생긴 뒤 v2 코드/DB로 무조건 되돌리면 새 자료가 유실된다. 이 후보는 v3→v2 자동 down을 **거부**한다. 복구 시 점검 모드·알림 중지로 새 작업을 막고 현재 DB+첨부를 보존한 채 v3 호환 코드로 수정 전진한다. 배포 전 snapshot으로 되돌릴 필요가 있으면 신규 자료/감사 유실 여부를 별도 대조해야 한다. tests의 `make_v2_fixture`는 검증된 임시 디렉터리의 비어 있는 추가 구조만 다루는 과거 버전 시험 도구이며 운영 복구 도구가 아니다.

전체 ZIP 복구 후보 도구는 운영 DB를 교체하지 않는다:

```bash
# 아래는 향후 Linux 운영 반영 단계에서 검증 후 사용할 명령이며 이번에 실행하지 않았다.
.venv/bin/python tools/prepare_equipment_full_restore.py --archive /explicit/backup.zip --destination /explicit/new-recovery-folder
# 검증 완료 후, attachment-root를 명시하면 누락된 불변 파일만 보충한다. 충돌 파일은 덮어쓰지 않는다.
.venv/bin/python tools/prepare_equipment_full_restore.py --archive /explicit/backup.zip --destination /explicit/another-new-recovery-folder --attachment-root /explicit/equipment-files
```

검증된 `equipment.db`를 기존 관리자 후보 검증·양쪽 인증·이중 확인 복원 절차에 제출한다. DB-only 후보는 모든 참조 첨부의 해시가 현재 저장소와 일치해야 한다. ZIP 경로 순회·중복 항목·크기·manifest·DB/FK/스키마·파일 해시가 검증 대상이며 실패 자료는 새 격리 폴더에만 남는다.

알림 CLI 역시 아직 예약 등록하지 않았다:

```bash
.venv/bin/python tools/equipment_notifications.py --database /explicit/equipment.db --maintenance-state /explicit/maintenance-state.json
# 검증 후 --send를 추가하면 실제 발송. 같은 명령을 하루 1회 예약하는 방식이다.
```

DB 복원과 알림 job은 같은 `<DB 파일명>.notification.lock`을 사용한다. 실행 중이면 복원은 DB 변경 전에 실패하며, 점검 상태에서는 알림 연결을 fail-closed로 중단한다. 기존 서비스의 실행 방식이나 systemd 설정은 바꾸지 않는다.

## 검증 상태 / 다음 운영 게이트

Node VM/문법/정적 연결 및 기존 모델명·제조사·카탈로그 복원 회귀를 실행했다. Python은 SSH 표준 입력으로 AST만 분석하고 Jinja는 구문만 파싱했다. 앱 import/DB 동작/실제 업로드/메일/브라우저 테스트를 실행한 것이 아니다.

Linux용 `tests/test_roadmap_batch.py`는 입력 경계, 인증 제한/만료, 상태 권한/경합/감사 실패, 2,000행 필터·EXPLAIN, CSV 확정/중복/카탈로그 변경, 첨부 권한/삭제/전체 백업·복구, 기한·스킨, 알림 중복·불확실 재시도, v2→v3 실패 rollback을 준비했다. 기존 v2 migration 회귀도 역사적 경로로 유지했다.

운영 승격 시 필수 순서: 기준선 해시 확인 → 승인된 파일만 운영 소스 병합 → 정적 재검사 → Git → Linux pull → 격리 DB 전체 unittest 및 복구 리허설 → 실제 서버 설정/저장소/프록시 확인 → 서비스 적용 → 모바일/키보드/브라우저 실사용. 스테이징 정적 통과를 Linux/API/사용자 검증 완료로 대신하지 않는다.

관련 실행 기록: `Plans/2026/09/13/002_Roadmap_Batch_Staging_Plan.md`, `Tasks/2026/09/13/002_Roadmap_Batch_Staging_Task.md`, `Reports/2026/09/13/002_Roadmap_Batch_Staging_Report.md`.

## 2026-09-13 운영 승격 안내

WORK-20260913-ROADMAP-BATCH-RELEASE에서 명시 승인된 배포를 진행한다. CLI는 기존 운영 도구 경로 tools/로 배치하고 database_release.py의 v3 사본 검사도 함께 보정한다. 위 내용은 스테이징 완료 시점의 기록이며 실제 배포 결과는 003_Roadmap_Batch_Release_Report.md를 따른다.
