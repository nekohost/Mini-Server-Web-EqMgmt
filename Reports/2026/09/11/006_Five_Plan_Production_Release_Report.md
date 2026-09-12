---
artifact_id: REPORT-20260911-006
work_id: WORK-20260911-FIVE-PLAN-PRODUCTION-RELEASE
created_at: 2026-09-11T10:27:58.365+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/11/005_Five_Plan_Production_Release_Task.md
---

# 5개 계획 운영 반영 검증 보고서

- 작성: 2026-09-11T10:27:58.365+09:00 (파일 생성 시각 기준)
- 상태: 2026-09-12 Git·백업 Linux 실검증/적용 완료 / 주 서버 SSH 인증 불가. 아래 이전 수행 기록은 원형 보존.

## 검증 1~8: 사전 검토 (순서대로 적용)

1. 거버넌스: recorder ensure 성공, governance 1.5.0 validate 오류/경고 0. 전체 intent/path 및 Rule 6-3-1 context 등록 확인. 기존 dirty worktree 보존.
2. 의도: 미구현 4건과 수신 AI 기록 1건만 구현. app.py 주석 전면 재구축 제외. 사용자 승인에 운영 소스 병합·commit/push 포함.
3. 정적 논리: ModelName 호환 유지와 FullModelName 추가, 옵션 참조 검사와 변경의 동일 트랜잭션, 감사 이력 무손실·멱등 migration, WebMCP 현재 API 및 안전한 미지원 폴백 검토.
4. 운영 영향: Staging 후보 작성 후 운영 소스 반영. Windows 앱 실행 금지. Linux 미검증을 소스 반영 성공과 혼동하지 않음. 기존 실행 프로세스/DB 무단 종료·교체 금지.
5. 보안·경계: 기존 세션/관리자/CSRF 유지, PENDING 승인 우회 금지, draft 포함 옵션 참조 차단, WebMCP 범위 내 읽기 및 사용자 수동 제출, 임의 FK 오류 허용 금지.
6. 복구: migration 전 독립 백업 및 원자적 rollback, SQL 이력 보존. 소스는 명시적 diff와 git revert 가능한 commit. 서버 DB는 실제 검증 전 변경하지 않음.
7. 사용자 오류: 사용 중 옵션 삭제 사유·미사용 옵션 구분, 옵션 JSON 검증, 모델 경로 손상 폴백, 백업 오류 식별자 제공.
8. AI 메타: 오래된 Staging 통째 덮어쓰기 금지. 기존 recorder/routed-ingest 변경 보존. 구현·정적 검증·Linux 검증 상태를 별도 보고. 수신 AI 표기는 향후 이벤트부터 적용.

## 실행 결과

- SSH: 192.168.0.166 도달 가능, 비대화형 인증 거절. 다른 승인된 연결 경로 확인 예정.
- 백업 서버 역시 같은 비대화형 인증 거절. 로컬 SSH 디렉터리에 사용할 개인키/config가 없으며 인증정보를 추측·탐색하지 않았다. Linux DB·프로세스는 변경하지 않았다.

## Staging 구현 후 검증 1~8 (순차 완료)

1. 거버넌스: 승인된 최신 운영 기준 위에 후보를 작성했다. Rule 6-3-1만 변경되었고 sync-status → 동일 hash의 sync-plan → node digest/map/baseline/manifest 1.5.1 갱신 → 정규 validator overlay 검증(42노드, 오류/경고 0)을 완료했다. 기준 Rule SHA는 `FB892DF180847BCF752908665697761D3259F5E04CE1063AD0BEB0D0B03FCF5B`이다.
2. 의도: 계획 09/03/006, 09/09/004, 09/11/001·002·003의 다섯 범위를 연결했다. 09/11/004 전체 미구현 로드맵 계획 Task는 별도 작업이므로 수정·커밋 대상에서 제외했다. app.py 주석 전면 재구축은 하지 않았다.
3. 논리: API 3곳에 같은 경로 helper 적용(노드 1회 조회·캐시·최대 50단계·사이클/고아/분류 불일치 폴백). 옵션 CRUD와 감사는 BEGIN IMMEDIATE로 직렬화한다. 장비 생성/수정도 같은 writer 잠금 아래 옵션 존재·상태를 재확인한다. 감사 migration은 알려진 DDL만 허용하며 typed-row 지문·명시적 count/min/max/NULL·sqlite_sequence·인덱스를 대조한다. 백업은 활성 writer 자체가 아닌 별도 읽기 연결에서 수행하여 자기 잠금 대기를 피한다.
4. 운영 영향: `ModelName`과 ID 유지, `FullModelName` 추가. 기존 등록 화면과 노드 관리 URL 유지. 관리자 옵션 관리만 확장하며 기존 등록 내 옵션 생성 정책은 전면 개편하지 않는다. v2 목록은 본인/공개(관리자는 전체) 정식 장비로 제한한다. migration은 시작 시 실행되며 알 수 없는 스키마/기타 FK 위반이면 시작을 중단한다. 기존 Rule/PID/routed-ingest 변경을 덮어쓰지 않았다.
5. 보안·경계: 관리자·세션·CSRF 유지, PENDING 옵션 관리자 직접 변경 차단 및 일반 사용자 POST 결재 생성. 임시저장/정식 참조가 있으면 옵션 삭제 409. WebMCP는 현재 화면 범위의 GET 2개만 노출하며 등록 폼은 신규/표시 중에만 활성화하고 자동 제출 속성을 사용하지 않는다. 내부 SQL·경로는 오류 응답/상관관계 로그에 노출하지 않는다. 사본 생성 0600, 작업 루트/하위 0700 적용.
6. 복구: migration 사전 DB 사본과 JSON 지문 증거는 `migration-backups`에 자동 정리와 분리 보존한다. 실패 시 transaction rollback하며 사본은 보존한다. 감사 FK를 되살리는 자동 역 migration은 금지한다. 소스 후보→운영 diff 및 Git commit으로 복구 경로를 제공한다.
7. 사용자 오류: 옵션 수와 활성/임시저장 장비 수 분리, 미사용 옵션 필터, JSON 편집 오류, 승인함 안내, 사용 중 삭제 사유, 삭제 전 명시 확인, 성공 후 스냅샷/캐시 갱신을 추가했다. 모델 경로는 HTML escape와 줄바꿈을 적용한다.
8. AI 메타: 기존 Staging 전체를 덮어쓰지 않고 수신 AI 변경만 최신 기록기에 재기반했다. 안정 event_id와 과거 헤더·본문을 보존한다. 정적/격리 Node 검사와 Linux DB 실증을 구분하며, SSH 실패를 기능 성공으로 대체하지 않는다. 미지원 HTTP 브라우저는 기존 UI를 유지한다.

## 교차 시나리오 및 시험 증거

- Python AST: Staging 8개 파일 파싱 성공. app import/DB 실행 없음.
- 프론트엔드·등록 선택기: Node 격리 16개 통과. 미지원 환경, 조회 범위, 비정상 입력, 취소, 수동 제출, 기존 노드 선택 동선 포함.
- 수신 AI: 기존 6개 통과. 추가로 역방향 legacy 호환·다른 AI 오매칭 방지·event_id 유지 회귀를 포함하고 재검증한다.
- 기존 운영 대화 기록/routed-ingest/cross-scope: 25개 통과(병합 전 기준).
- Linux용 모의 DB/API 테스트 18개를 추가하고 기존 노드 fixture를 실제 스키마 컬럼에 맞췄다. 실제 Linux 실행은 인증 차단으로 미수행이며 통과로 주장하지 않는다.
- 전체 archive 검사에서 기존 다른 작업의 잘못된 시각/미생성 문서 링크를 발견했다. 본 Task의 번호 중복·front matter는 자체 수정했다. 별도 작업의 미완성 문서는 보존하며 오류가 남으면 구분 보고한다.

## API 확인 근거

WebMCP는 변경 중인 API이므로 현재 공식 문서의 `document.modelContext.registerTool`, 취소 signal, 수동 폼 제출 규약을 사용했다. 디스커버리 JSON은 프로젝트 관례이며 W3C 필수 manifest라고 표기하지 않는다. [Imperative API](https://developer.chrome.com/docs/ai/webmcp/imperative-api?hl=en), [Declarative API](https://developer.chrome.com/docs/ai/webmcp/declarative-api).

SQLite 재구축은 새 테이블 생성→명시적 복사→원본 제거→새 이름 확정 순서로 제한한다. [SQLite ALTER TABLE](https://www.sqlite.org/lang_altertable.html).
## 2026-09-11 최종 통합 게이트

- Staging/Release_20260911 후보 25개와 현재 운영 트리의 대응 파일 SHA-256: **25/25 MATCH**.
- governance v1.5.1 validate: **errors 0 / warnings 0**, sync-status: **inSync=true**.
- governance/tooling 전체 회귀: **54/54 PASS**.
- 5개 기능 및 Proposal047 연동 Node 격리 회귀: **23/23 PASS**.
- Python 대상 소스 AST 정적 파싱: **8/8 PASS**. 앱 import·Windows DB 실행은 하지 않았다.
- conversation recorder verify: **ok=true**, sourceEvents 1336, missing 0, missingReceipts 0, duplicates 0.
- git diff --check: **PASS**.
- archive validator 잔여 3건은 별도 WORK-20260911-ALL-UNIMPLEMENTED-ROADMAP-PLANNING의 Task 004 timestamp 및 아직 생성되지 않은 Plan 004/Report 005 링크이며 본 릴리스 결함으로 처리하지 않는다. 해당 별도 세션 문서는 수정하지 않았다.
- Git commit/push와 Linux DB migration·서비스/브라우저 검증은 당시 아직 수행하지 않았으므로 완료로 주장하지 않았다.

## 2026-09-12 재개 결과

기존 39개 Linux 회귀가 모두 통과했다. 이후 DB 계약 개선을 포함한 55개 Linux 회귀, 23개 Node 기능 회귀와 54개 거버넌스 회귀가 통과했다. commit/push와 백업 서버 실제 서비스 적용을 완료하고 과거 DRAINING 상태를 NORMAL로 정상 종료했다. 백업 서버의 main fetch/upstream 누락도 수정했다.

실행 코드 87e28bc, PID 48811. 주 서버 192.168.0.166은 제공 키의 인증이 거절되어 적용하지 못했다. 상세 증거와 복구 사본은 [DB 계약 운영 반영 보고서](../12/003_Database_Contract_Production_Release_Report.md)에 기록한다.
