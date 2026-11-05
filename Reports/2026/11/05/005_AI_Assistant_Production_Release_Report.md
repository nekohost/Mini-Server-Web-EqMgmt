---
artifact_id: REPORT-20261105-005
work_id: RELEASE-20261105-AI-UX
owner: Codex
created_at: 2026-11-05
status: in-progress
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
