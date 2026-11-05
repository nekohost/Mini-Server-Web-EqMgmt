---
artifact_id: REPORT-20261105-005
work_id: RELEASE-20261105-AI-UX
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 운영 병합·배포 기록

사용자는 검증된 Staging을 운영 소스와 서버에 적용하도록 승인했다. 작업 owner는 Mini-Server이며 현재 운영 대상은 기존 문서의 백업서버 `eqmgmt-backup`을 실제 상태로 재확인한다. root profile은 legacy/runtime-session-mismatch(verified=false), recorder ensure 및 governance1.8.1 validate 성공, 전체 context34개 노드를 읽었다.

기존 후보의 v4/worker/guard·표/휴지통·관리자/옛 UI 정리 및 공간 절약을 함께 적용한다. 초기 설치용 배포 도구의 기존 .env/worker 유닛 부재 전제는 현재 업그레이드에 맞지 않을 수 있어 실제 상태를 먼저 읽는다. 일반 파일은 구조화 편집하며 원래 다른 dirty9개와 다른 Staging은 보존한다.

## 사전 확인과 Validation1~8

서버 실제 host/user는 기존 운영 대상과 일치하며 remote/local/origin main HEAD가 모두3d9dacc다. 웹은 검증된 .venv Python의 `-u app.py`, 워커는 user systemd의 `-m utils.ai_assistant.worker`다. root .env와 worker.env는0600이고 공통 비밀 설정이 일치한다. USER_AI_DATABASE는 양쪽에 명시되어 있지 않아 동일 private 절대 경로를 추가해야 하며 epoch는 이미 설정돼 있다. sudo 비대화형 인증은 아직 불가하다. 기존 initial activate는 설치된 env/unit 부재를 전제로 하므로 이번 upgrade에 사용하지 않는다.

1. 거버넌스: Staging 결과를 승인한 최신 사용자 배포 지시를 적용한다. 현재 scope의 운영 DB 사본/가산 이전·자기 서비스 전환은 그 지시의 필수 단계다. 비밀·기존 데이터와 다른 dirty를 보존한다. 정책/권한을 자동 완화하지 않는다.
2. 의도: 기존1~7번 및 compact 후보 전체를 배포하며 관리자/일반 사용자 범위·자체 큐·다중 모델·추론 지원 계약을 유지한다. 공유 Strata 또는 타 서비스 요청을 중단하지 않는다.
3. 논리: v3→v4/점유 guard/워커/환경을 함께 적용한다. 실제 DB 사본의 기존 메시지·프로바이더·설정·업무 행을 비교하고 현재 자체 job이 없거나 정상 종료한 뒤 전환한다. active/unknown 요청을 강제 성공·삭제하지 않는다.
4. 운영 영향: 정확한 Git commit만 pull하고 이미 설치된 env/unit을 보존하는 upgrade 경로를 사용한다. 메뉴 부모만 정확히 이전하며 충돌은 차단한다. private 경로/epoch와 timer sandbox 경로를 맞춘다.
5. 보안: 기존 Flask key/AI 암호키/토큰을 보존하며 값·대화·장비 내용을 로그/Git에 출력하지 않는다. DB/환경 백업은 private에 두고 SSH로 현재PC의 private 디렉터리에 받는다. 실제 사용자 권한·익명 거절·CSRF와 옛 UI 차단을 확인한다.
6. 복귀: 현재 commit/PID/프로세스 환경/웹·worker 설정/두 DB를 먼저 보존한다. v4 후에는 최신 삭제 원장과 epoch를 보존하며 과거 DB로 무조건 되돌리지 않는다. 해당 candidate를 보존한 뒤만 병합 정리한다.
7. UX: 실제 HTTPS에서 관리자 메뉴/모델/표/추론·모바일 및PC를 점검한다. 실제 로그인/sudo 인증이 반드시 필요한 경우 준비한 정확한 작업과 이유를 설명하고 현재PC에서 입력받는다. 데이터 초기화나 실장비 확정 업무로 검증하지 않는다.
8. 메타/판정: 기존 합성178/2657 검증을 실제 배포 성공으로 미리 집계하지 않는다. 각 백업·사본검증·merge·commit·pull·전환·실제화면 결과를 별도로 남긴다. 이번 단계는 사전 백업/진단 진행 가능이며 운영 전환은 아래 실제 검증 결과에 따른다.

## 병합·백업·사본 검증

- 서버 private 보존 경로: `instance/releases/20261105-ai-ux-20261105T035939Z-4309ab`(0700). 업무/AI DB의 일관 백업·두 환경 파일·worker unit은0600으로 보존하고 현재PC의 `.codex/private-releases/20261105-ai-ux-20261105T035939Z-4309ab`에 사용자 전용 ACL로 내려받아 해시를 대조했다. 비밀/DB는 Git에 포함하지 않는다.
- 실제 DB 사본 기동 결과: 업무18개 테이블, AI14개 테이블의 기존 행/열 보존과 감사 로그 append-only 보존을 통과했다. 기존 대화5·메시지22·job11·proposal1·provider1·model1을 보존하고 v4/관리자 메뉴 부모 `admin_center`·익명 경계를 확인했다. 모델 호출과 운영 DB 변경은 없었다. 서버 private 근거 `copy-36ac8019864d/result.json`.
- 후보42개 파일을 root에 병합하고 별도 nginx 보조 코드를 추가했다. 옛 공개 자산11개는 Git 이력을 보존한 상태로 제거했다. 원래 다른 dirty9개는 보존했으며 세 기능 원장에는 이번 항목만 추가하여 index에 분리 반영한다. 기존 미구현 원장 및037/AI-TECHDEBT-001 상태는 유지한다.
- root 전용 fixture 경로를 맞춘 뒤 Linux 격리 검증: backend178개 모두 통과(실패/오류/skip0,34.935초), 화면24개 기능 시나리오+3개 측정 화면,2657개 검사 모두 통과. 검증 digest `2d534e4a50a9b7ae6615a85a15c14035bea4d48a0371d998c65bcbde3a15e32c`. Windows에서 앱을 기동하지 않았다. 첫 root 검사에서 관련 없는 테스트가 함께 수집되는 harness 문제는 AI 테스트 allowlist로 수정한 뒤 위 결과를 얻었다.
- 현재 Staging49개 원문은 [보존 ZIP](005_AI_Assistant_Production_Release/staging-merged-candidate.zip)에 전부 보관하고 ZIP 내용/각 원문 SHA를 확인한 뒤 해당 후보 파일만 apply_patch로 정리했다. ZIP SHA256 `a779dd45254638a981de6fa218cffcd4d6f33e0648b2ebd68adbad61a9fb56aa`. 다른 Staging은 그대로다. [검증·원문 해시](005_AI_Assistant_Production_Release/validation-before-deploy.json).
- 업그레이드 도구는 정확한 host/user/commit/PID/cwd/argv와 자체 idle job을 확인하고 신규 접수 차단→worker/web 정상 종료→quiesced DB 백업→사본 검증→v4 기동/기존 행 확인→접수 재개 순서로 동작한다. 다른 서비스나 공유 Strata를 제어하지 않는다. Nginx 보조 도구는 기존 장비관리 include 하나만 백업·교체하고 구문/재적용 실패 시 원복하며 별도 upstream key를 열거나 바꾸지 않는다.

## 실제 서버 적용 결과

기능 커밋은 `055fcbfee5dde4abc2b0b623f8ce06d37546abf9`, 최종 실행 코드 커밋은 `a8c8a86bad43da7197d88f88cd49c95f4f0e01c0`다. 기존 다른 dirty9개를 포함하지 않고 기존 GitHub 계정의 main으로 push한 뒤 서버에서 fast-forward했다. 설치 전용 명령을 재사용하지 않았다.

2026-11-05 13:22 KST경 자체 미종료 job0을 확인해 접수를 닫고 기존 worker와 확인된 웹 PID719360을 정상 종료했다. 정지 시점 업무/AI 일관 백업을 다시 보존했다. CLI로 실행한 사본 검사에서 프로젝트 모듈 경로 누락이 발견됐고, 배포 보조 도구의 sys.path를 보완한 `a8c8a86`을 적용한 뒤 `copy-ce570f926bde/result.json`에서 같은 보존·v4·인증 검사를 통과했다. 이 오류 중에도 운영 DB 이전이나 기존 기록 초기화는 수행하지 않았다.

13:23:14 KST 웹 PID824644와 자체 worker를 기동했다. 접수 재개 전에 기존 업무18개 테이블·AI14개 테이블의 기존 행/열·감사 append-only와 비밀 설정을 확인했다. app/worker 환경에 같은 절대 AI DB 경로만 가산하고 Flask key/암호키/token/epoch는 보존했다. 기존 대화5·메시지22·job11은 유지됐다. v4와 메뉴 부모 `admin_center`를 확인한 뒤 접수를 재개했다.

사용자가 현재PC의 SSH 창에서 sudo 인증을 직접 수행했다. root Nginx 보조 도구로 `mini-server-backup` 사이트의 기존 전용 include 한 개만 백업·교체하고 `nginx -t`와 reload를 통과했다. 기존 별도 upstream key는 helper가 열지 않았고 metadata도 동일하다. 옛 공개 자산11개는 유지보수 중 같은 Git으로 교체했고 LICENSE/README/OFL·Git/후보 ZIP은 유지했다. 공유 Strata나 다른 사이트의 설정/프로세스는 수정하지 않았다.

| 실제 확인 | 결과 |
| --- | --- |
| HTTPS 익명 | login200, assistant/admin302, AI capabilities401 |
| 옛 gateway/auth/static | 8개 경로 GET/POST16개 모두410 |
| 실제 관리자 메뉴 | 메인 포털에는 AI 연결 관리 없음, 관리자 센터에 있음 |
| 실제 AI 조회 | `search_equipment`, off,2단계,9.224초,done,오류 없음,미확정 업무0 |
| 표 표시·지속성 | 본인 장비 총2건을 DOM table1개/본문1행으로 표시, 재진입 후 동일 응답 유지 |
| 실행 점유 | 해당 guard released,예약 문자0,자체 worker active |
| 휴지통 정리 | timer active;13:23 및13:25 실행 status ok/purged0/more_expired false |
| 운영 무결성 | AI integrity_check ok;장비/카탈로그 등 업무17개 테이블 동일;users3명 동일하고 직접 로그인으로 SessionToken만 갱신 |
| 기록 보존 | 기존 done9/failed1/cancelled1 유지,검증용 done1·대화1·메시지2만 추가;과거 실패를 성공으로 바꾸지 않음 |

실제 검증 대화는 “배포 검증: 내 장비 조회와 표…”로 계정에 남겼다. 장비/신청을 생성·수정·삭제하지 않았으며 기존 감사 행도 보존됐다. 휴지통은 빈 목록과30일/복구/재이동 기준 안내만 실제 확인했고 운영 대화를 삭제하거나 실제 연결 설정 revision을 변경하지 않았다. 휴지통 이동·복구·재이동·만료/영구삭제·일반 사용자 권한·관리자 저장/결과/응답 유실 분기는 Linux 격리178개와2657개 화면 검사에서 확인한 결과다. 실제 브라우저는 기존 관리자 계정으로 검증했으며 일반 사용자 실계정으로 별도 로그인했다고 주장하지 않는다.

## 실제 화면 결과와 한계

| 화면 | 결과·근거 |
| --- | --- |
| PC1440×1000 | 상단 대화 제목 숨김,좌측 선택1개,모델136px/추론100px,제어기36px/글자12px,가로 넘침 없음. [표 응답](005_AI_Assistant_Production_Release/production-desktop-table.jpg) |
| 모바일390×844 | 좌측 목록 자동 숨김,제목18px 한 줄/말줄임,모델136px/추론100px,제어기44px/글자12px,표285px/가로 넘침 없음. [표 응답](005_AI_Assistant_Production_Release/production-mobile-table.jpg) |
| 관리자 | [센터 메뉴](005_AI_Assistant_Production_Release/production-admin-center.jpg),[모바일 연결 설정](005_AI_Assistant_Production_Release/production-admin-mobile.jpg) |
| 휴지통 | [운영 빈 휴지통과 보관 안내](005_AI_Assistant_Production_Release/production-mobile-trash.jpg) |
| 옛 UI | [로그인된 폐기 안내](005_AI_Assistant_Production_Release/production-strata-retired.jpg),새 assistant 링크로 복귀 정상 |

PC/모바일에서 이번 배치로 인한 잘림·겹침·가로 넘침은 발견되지 않았다. 모바일 응답은 대화 영역을 스크롤해 표까지 확인했다. 브라우저 오류0이며 공통 기존 Tailwind CDN의 production 사용 경고2건은 관찰 기록으로 남긴다. 이번 기능의 실행 오류나 신규 회귀로 판정하지 않았고 공통 자산 빌드 전환으로 범위를 확대하지 않았다. 뷰포트 설정은 초기화하고 assistant 화면으로 복귀했다. 최초 모바일 측정이 다른 관리자 탭에 적용된 도구 대상 문제는 대상을 바로잡은 후 위390px 근거로 교체했으며 잘못된 측정은 최종 결과로 쓰지 않았다.

상세 기계 근거는 [production-verification.json](005_AI_Assistant_Production_Release/production-verification.json)이다. 검증 스크린샷에는 비밀 key·장비 상세·실제 대화 원문 전체를 담지 않았다. 짧은 읽기 전용 요청의 시간이며 장문·전체 모델 성능이나 일반 지능 평가가 아니다. 기존037 및 AI-TECHDEBT-001은 보류 상태를 유지한다.

## 복구와 보존

서버 private release 및 현재PC private 사본에는 초기/정지 시점 두 DB,원래 환경/worker unit/프로세스 환경,원래 maintenance 및 Nginx include를 보존했다. 정지 시점 업무 DB SHA256 `80f11b2f073e49280ee4cfe51cf93bdae9040b7156bc9cd3dbf3d0dc1ad75b8f`,AI DB SHA256 `f506a9c1328e6d4607e5594269dc0623224170adc43269ba42c255aac144fd28`이 양쪽에서 일치한다. Windows private 디렉터리는 현재 사용자만 상속 FullControl이며 Git 밖이다.

기능 복귀 시 먼저 자체 접수/진행 작업과 최신 v4 점유·삭제 원장을 확인한다. v3 코드만 단독 재기동하거나 과거 DB로 전체 덮어쓰지 않는다. 필요한 개별 코드/설정 복구는 보존 SHA/바이트와 새 기록을 함께 검토한다. Nginx include는 원래 바이트를 사용해 검사·reload할 수 있으나 키 회전·다른 사이트 변경과 묶지 않는다. 최종 운영 판정은 적용·읽기 전용 실모델/화면 검증 완료다.
