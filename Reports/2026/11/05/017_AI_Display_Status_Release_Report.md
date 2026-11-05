---
artifact_id: REPORT-20261105-017
work_id: RELEASE-20261105-AI-DISPLAY-STATUS
owner: Codex
status: in-progress
approval: staging-and-production-explicit
---

# AI 표시 정책·상태 안내 누적 후보 운영 반영 검증

recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0 및32개 context 노드를 확인했다. 기존 공통 노드를 승계하고 이번 deploy/staging-merge/completion/server 경로를 확인했다. 사용자 명시 승인은 검증 결함 수정과 누적 Staging의 운영 서버 반영까지 포함하므로 재승인 질문 없이 수행한다.

## 구현 전 Validation1~8

1. 거버넌스: Task017과 계획을 먼저 기록하고 기존016 후보/원문을 보존한다. 운영 병합은 정적/화면 검증 후 수행하며 현재 사용자 승인으로 그 단계까지 허용된다.
2. 의도: 내부 ID는 일반 답변에서 배제하도록 암시하되 실제 도구 참조는 유지한다. 입력칸 위에 노랑/빨강 원인 안내를 추가하고 기존1~10을 포함해 운영 반영한다.
3. 논리: 도구 payload 중복/예산 초과·무차별 숫자 삭제를 피한다. 상태 banner는 기존 수신/TTL 렌더를 공유해 중복 poll과 상단/하단 불일치를 막는다.
4. 운영 영향: 현재 후보의 새 모듈·frame·worker까지 배포 대상 누락을 확인한다. 실제 DB 사본의 기동과 모든 기존 행/업무 데이터를 검증하고 동일 commit으로 전환한다.
5. 보안: 원문 감사/권한/CSRF·내부 도구 ID는 유지하고 사용자 데이터의 지시문을 신뢰하지 않는다. 상태 reason은 안전한 텍스트이며 endpoint/key/타 사용자 내용은 공개하지 않는다.
6. 복구: private DB/설정/소스/서비스 백업과 이전 commit을 보존한다. 기존 정상 요청·외부 서비스는 중지하지 않으며 실패 시 own web/worker만 원상 복귀한다.
7. UX: 표시용 필드/시리얼·수량 보존, banner의 위치/색/사유/TTL·긴 글자/낮은 높이·오류 notice 공존과 실제 운영 화면을 확인한다.
8. 메타: 기존016의 완료 증거는 불변이다. 정책 지침과 강제 보안 경계, 합성 검증과 실제 운영 확인을 구분하며 runtime 미검증 모델을 검증됐다고 기록하지 않는다.

## 구현·사전 감사

ID 지침은 SYSTEM/읽기 도구 설명과 결과당 한 번의 bounded `display_policy` 메타로 전달한다. 원본 ID/Revision/링크와 감사 내용은 그대로 유지한다. 실제 claim→조회→상세→수정 제안/확인, 모델 전환 인계, 업무 숫자 보존·권한 경계의 신규 Linux 합성7개는 전부 통과했다(2.729초, skip0). 이는 모델에 전달되는 표시 계약의 검증이며 임의 모델 답변의 강제 검열 증명은 아니다.

입력칸 안내는 상단과 하나의 동기 render/TTL을 공유한다. 최초390px dark 화면에서 긴 사유를 넣었을 때 채팅 최소 높이/가로 경계 검사1건이 실패했다. 이 실패는 `017_AI_Display_Status_Release/smoke-banner-01`에 보존하고 원인 수정 후 재검증한다. 정상 진행을 성공으로 바꾸거나 기준을 낮추지 않는다.

서버 읽기 감사: local/server HEAD `82a936175b28a2dd02942ded34d884c4ca17ec0b`, 정확한 own web PID867701/worker867719, queued/running/draining/recovery job 및 guard0, maintenance NORMAL revision12. retention timer active/waiting·service inactive다. 두 환경의 DB 경로·키/epoch·소유권/0600 및 실행 환경 일치를 값 비공개로 확인했다. 기존 helper는 원격과 SHA `cb525efd49e38c87a054a37ca00e36a45cc8b8cb05d0390ebd34828c15256830`가 같았다.

사전 감사에서 jobs 없는 active guard를 놓치는 helper 판정과 retention 전환 경쟁을 확인했다. 계획017에 두 gate의 동일 snapshot 판정 보강과 timer 상태 보존/일시 정지·실행 중 cleanup 정상 종료 대기를 추가했다. 최종 pull 후 실제 DB 사본 검사와 실패 시 접수 차단/최신 데이터 보존 복구는 부모가 단독 수행한다.

## Staging 통합 검증

Python AST23개/JavaScript 구문11개와 Node 출력 presenter18개가 통과했다. Linux 격리 backend는 **211개 통과**, 실패/오류/skip0,49.592초이며 digest `900a44f52170f031d3a0a26b34811b06f7bda5eaee7d1629da3c959c1fa73da1`다. 기존194개에 ID 표시7개와 배포 guard10개를 더한 수이며 운영 앱 import/DB 사용/모델 호출은 없다.

최초 배너 실패는 border-box 테두리2px 누락으로 pane117.953px가 된 실제 제품 결함이었다. `fitViewport`의 fixed 높이를 두 getBoundingClientRect 높이 차이로 계산하여 테두리·소수점을 포함했다. 신규8화면(320/390/820/1440×라이트/다크) **504개 검사 통과**.500자 사유 전문과 확대글자/620px 높이에서도 pane최소120.094px를 확보했다. 기존 기준 완화 없이 전문 보존 검사와 측정 완료 동기화를 강화했다. 별도 기존 UI4화면642개·viewport4화면142개도 통과했다. 원문과 스크린샷은 새017 결과에 보존한다.

## 배포 준비·백업

서버 private release `instance/releases/20261105-ai-ux-polish-20261105T073602Z-f7c02f`에 두 DB·환경2개·unit3개·maintenance·이전 Git 소스 archive·timer 상태를 보존했다. 두 SQLite main 파일은 immutable 읽기의 integrity/FK를 통과했다. 현재PC 사용자 단독 ACL `.codex/private-releases`에도 stable manifest 포함13개 파일의 SHA를 대조했다. 초기 manifest가 프로세스 종료 때 사라지는 SQLite WAL/SHM 임시 sidecar까지 기록한 문제는 원문을 남기고 별도 stable manifest에서 제외해, 독립 main DB 무결성을 확인한 후 재전송했다. ACL 적용은 numeric SID에 필요한 `*` 접두사를 보완한 뒤 성공했다. 인증정보/실제 대화 원문은 공개 결과에 넣지 않았다. 이 준비 단계에서 서비스는 변경하지 않았다.

## 후보 동결·운영 소스 병합

017 최종 후보40개를 별도 ZIP에 보존했고 SHA256은 `8d5223f49aeaca4fe7dae9987107a38d6262d8ed4174386d75b2490ba4144315`다.016 ZIP/32개 entry는 그대로다.017 실제 브라우저는 **40화면·2,120개 검사 전부 통과**했으며 기존1~10의 layout/lifecycle/실시간 출력과 모델 접기·viewport·신규 배너를 함께 검증했다. 기존016의 포털/CSV 결과는 별도 과거 증거로 유지하고 새40개에 합산하지 않았다.

검토용 README를 제외한39개(runtime18개·검사21개)를 Windows 운영 소스에 구조화 병합했다. 새 모듈·frame CSS·worker·policy/context/domain·배포 helper까지 포함한다. SHA와 정적 재검사 후 이 후보40개만 구조화 정리하고 관련 없는 기존 dirty 파일은 보존한다. 원문 목록/해시는 `validation-before-merge.json`, 병합 대조는 `root-merge-verification.json`에 기록한다.

병합39개는 검토 후보와 바이트 일치를 확인했다. 기존 frame의 CRLF는 검토 LF와 같게 구조화 재작성한 뒤 대조했다. merged root의 Linux backend도 **211개 통과**, 실패/오류/skip0,40.430초, digest `2993581ff48ef292d1bb008cd0cf3dc85c31e7ce9fc1c6180a7ba69d66eea9a0`다. Git whitespace 검사에서 새 EOF 공백 줄20개를 발견해 마지막 개행 한 개만 남겼고, ZIP과의 차이가 그 terminal blank뿐임을 각 파일별 assert했다. 구문23/11 및 scoped diff-check를 다시 통과했다.

최종 배포39개 소스의 별도 ZIP SHA는 `3dcc4271e0407852010122c9b8710b6ece905ed59765afa6b623df2945a1a799`이며 `release-source-verification.json`에 정확한 최종 SHA를 기록했다. 임시 Staging40개만 구조화 삭제했고 원문 ZIP/검증 증거와 기존 unrelated dirty4개 SHA는 보존됐다.

추가 검증·배포 및 실제 화면 결과는 아래에 누적한다.
