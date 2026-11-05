---
artifact_id: REPORT-20261105-012
work_id: RELEASE-20261105-AI-CSV-LAYOUT
owner: Codex
status: complete
---

# AI CSV·화면·모델 접기 운영 반영

현재 사용자 지시는 검증된 Staging 운영 배포이며 신규 상단 아이콘/상태 색상·두 줄 메뉴는 미실현 계획011로 분리한다. recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0과 context32개를 확인했다. 직전 읽은 변경 없는 공통/검증 노드를 승계하고 운영/데이터 보존·보안·완료/제안 원장 노드를 추가 확인했다.

사전 서버는 기존 운영 host/user, local/server HEAD `cb1d72c6abfd4abdb288315138501a9d9a7fe28a`, web PID824644의 정확한 `.venv/bin/python -u app.py`와 일치했다. worker/retention timer active, maintenance NORMAL, AI schema4이며 자체 job은 done15/failed1/cancelled1이고 진행 중0이다. 서버 tracked dirty는 없으며 기존 미완료 가상환경 untracked 폴더는 보존한다. 배포 helper의 local/server SHA가 일치했다. 초기 설치 helper는 사용하지 않는다.

## 사전 Validation1~8

1. 거버넌스: 현재 후보만 병합하고 두 신규 건은 미실현으로 기록한다. 기존 dirty9개·다른 Staging·운영 DB/비밀을 보존한다. 사용자 운영 배포 승인과 해당 소스 정리 범위를 적용한다.
2. 의도: CSV 요청형 팝업·하단 정리, 실제 높이/내부 scrollbar, 기본 접힌 모델 선택을 함께 반영한다.011·web_search·다른 유지보수를 끼워 넣지 않는다.
3. 논리: native details 및 기존 API/CSRF/도구 계약을 보존한다. root 병합은 검토 source 해시와 비교하고 승인 commit만 서버에 적용한다. 기존 진행 job은 정상 종료를 기다리고 중복 실행/강제 취소하지 않는다.
4. 운영 영향: template/JS/CSS/policy4개와 검사 보조7개가 대상이다. app/worker 코드·스키마·Nginx·키·다른 서비스는 바꾸지 않는다. 기존 업그레이드 helper로 정확한 idle web/worker만 정상 전환한다.
5. 보안: private 두 DB·환경·프로세스 설정을 보존하고 비밀/실제 대화 원문은 공개 결과/Git에 출력하지 않는다. 익명/일반 권한과 오류·CSV 명시적 확인을 유지한다. 실제 장비 쓰기로 검증하지 않는다.
6. 복구: 현행 commit/설정/일관 DB 백업을 먼저 보존한다. 무스키마 변경이므로 코드별 복귀가 가능하나 최신 AI 기록/삭제 원장을 과거 DB로 덮지 않는다. 백업·원문·해시를 확인한 뒤만 Staging을 정리한다.
7. UX: 실제 운영 브라우저에서 접힘/펼침·새로고침·모바일/PC 높이를 검증하고 원인이 보이는 오류/팝업을 확인한다. 필요한 로그인은 권한 있는 기존 계정의 정상 흐름으로만 진행한다.
8. 메타: 기존55개 화면/3543개와 이번 운영 검증을 분리한다. PC 요약 행 추가로 약26px 높아지는 기존010 측정도 숨기지 않는다. 실제 확인 전 배포 성공으로 표시하지 않으며 남은 한계를 최종 기록한다.

## 병합·보존 및 배포 helper 보완

검토 원문13개 ZIP/해시를 대조하고 원래 후보11개 파일이 root와 바이트 단위로 일치함을 확인했다. Python AST7개/JS 문법2개 통과 후 해당 Staging13개만 구조화 정리했다. 기존 다른 dirty9개는 보존하고 원장4개에는 이번 단락만 index에 분리했다. 기존 원장의 삽입 지점이 EOF가 아니었던 한 곳은 원래 본문 SHA 복구 대조로 확인했으며 기존 본문을 commit에 섞지 않았다.

기능 commit은 `bb48ac586b61e75331a256d007b39728743d5eba`이며 GitHub main에 push했다. Git 작성자 기본 설정이 없어 기존 nekohost noreply 식별자를 commit 한 번에만 지정했고 전역 설정은 바꾸지 않았다. 서버는 아직 이전 commit/정상 서비스 상태에서 백업·사전 검증했다.

서버 private release는 `instance/releases/20261105-ai-ux-csv-layout-20261105T055225Z-121eb6`(0700)이며 업무/AI 일관 DB와 환경·worker/retention 설정은0600으로 보존했다. 현재PC의 사용자 전용 ACL `.codex/private-releases/20261105-ai-ux-csv-layout-20261105T055225Z-121eb6`에도7개 핵심 파일을 받아 해시를 확인했다. 비밀은 출력/Git에 포함하지 않았다.

사전 읽기 점검에서 기존 대화5개에 정상 lifecycle/휴지통·복구 이력이 확인됐다. 기존 helper의 초기 이전용 '이력0' 조건을 그대로 쓰면 정상 데이터를 오류로 보게 된다. 서비스 정지 전에 별도 Staging에서 기존 lifecycle count를 전후 비교하도록 최소 수정했다. 기존 모든 AI 원본 행/열 fingerprint 비교는 유지하여 count만 같게 조작한 상태도 통과하지 못한다.

수정 helper를 Linux에서 메모리로 실행한 실제 DB 사본 `copy-8d0255f331cf/result.json`은 업무18개/AI17개 테이블, 기존 대화8/메시지34/job17 및 lifecycle5개·감사/익명 경계 보존을 통과했다. 실제 모델 호출/운영 DB 수정은 없었다. [helper 검토 원문](012_AI_Staging_Production_Release/reviewed-release-helper.zip)을 보존한 뒤 root에 반영하고 해당 임시 파일1개도 구조화 정리했다. 이 수정은011 계획의 구현과 관계없다.

## 실제 배포·운영 확인

실행 코드 최종 commit은 `43a01945b0b2d3dd15a2bed5bdc07e42682c081c`다. idle/정확한 PID를 재확인한 기존 helper로 접수를 닫고 웹/자체 worker만 정상 종료한 뒤 fast-forward pull했다. 공유 Strata와 다른 서비스는 제어하지 않았다. 서버 tracked diff는 없었다.

서버 pull 후 root Linux 격리 회귀 **178개 통과**, 실패/오류/skip0,34.974초다. digest `e01e64fd1ae3f52ef2b000a5eeeb1da7ca3f90bd6f269982ea6e9d3121b1b394`. 실제 DB의 정지 시점 사본 `copy-ba56a0a4fac9/result.json`에서도 업무18개/AI17개 테이블·기존 모든 행/열·감사/익명 경계와 lifecycle5개가 보존됐다. 기존55개 화면/3543개 Staging 결과는 원문11개 동일성으로 승계하며 이를 운영 실기기 수로 합산하지 않는다.

2026-11-05 **15:00:28 KST** 새 웹 PID867701·자체 worker를 기동했다. 접수 재개 전 두 DB의 기존 행/열과 비밀 설정 보존을 확인했고 maintenance NORMAL·worker/retention timer active다. .env/worker 설정은 백업과 값 전체가 같으며 이번에는 설정/키·스키마·Nginx 변경이 없다. 정지 시점 두 DB·프로세스 환경·기동/정지 결과도 서버 private 경로와 현재PC 사용자 전용 ACL에 별도로 보존한다.

| 운영 확인 | 결과 |
|---|---|
| HTTPS 익명 | login200,assistant/admin302,AI capabilities401 |
| 배포 파일 | 원래 후보11개 SHA가 root/서버 일치,HTTP로 받은 JS/CSS도 동일 |
| 일반 계정 | test05(user)로 정상 로그인·AI 화면/기본 접힘 확인,관리자 권한 부여 없음 |
| 모델/새로고침 | 260Strata / Qwen3.8 Flash Next,새로고침 완료 시 선택/펼침 유지·오류 없음 |
| 실제 CSV 안내 | off,1단계,접수→종료7.003초,done/오류 없음,CSV 가져오기 고정 링크 반환 |
| 실제 팝업 | 반환 링크를 클릭해 가져오기 dialog 열림·닫힘/Escape 확인,파일 업로드/장비 등록 확정은 하지 않음 |
| 대화 지속성 | reload 후 동일 링크/모델/추론 복원,모델 선택은 다시 기본 접힘 |
| 실행 점유 | 진행 job0,guard8개 released,예약 문자0,해당 job의 업무 proposal0 |
| 브라우저 | console error0,viewport override 해제·기본 화면 복귀 |

실제 UI 요청으로 test05의 검증 대화1개·메시지2개·done job1개가 추가됐다. 이전 done15/failed1/cancelled1은 보존되어 현재 done16/failed1/cancelled1이다. 기존 대화/메시지/job/proposal 원본 행은 모두 유지되며 lifecycle5개도 동일하다. 업무17개 테이블은 동일하고 사용자 행은 로그인 SessionToken열 외의 모든 값이 동일하다. 감사 행은 append-only로 보존됐다. 등록/수정/신청 확정은 없으며 사용자가 보관한 대화를 삭제하지 않았다.

## 실제 화면 검증

| 화면 | 결과·근거 |
|---|---|
| PC1440×1000 기본 접힘 | 문서 높이1000px/가로1440px,footer 안내/파일 toolbar 없음. [기본 화면](012_AI_Staging_Production_Release/production-desktop-collapsed.jpg) |
| PC 모델 펼침 | 모델136×36px,새로고침36px·추론36px,지원 off/low/medium/xhigh·high/max 비활성. [펼침](012_AI_Staging_Production_Release/production-desktop-expanded.jpg) |
| 모바일390×844 접힘/펼침 | 문서 높이844px/가로390px,mode fit. 모델136×44px,새로고침/추론44px. [접힘](012_AI_Staging_Production_Release/production-mobile-collapsed.jpg),[펼침](012_AI_Staging_Production_Release/production-mobile-expanded.jpg) |
| 모바일 실제 CSV 팝업 | x10~380px/y266.672~577.328px,370×310.656px,명시적 등록 버튼은 미리보기 전 숨김. [팝업](012_AI_Staging_Production_Release/production-mobile-csv-popup.jpg) |

추가로 발견된 화면 오류는 없다. 실제 브라우저는 시스템 다크 테마였고 라이트/다크 전체 분기는 기존55개 합성 화면에서 검증한 범위다. 실제 파일 전송/CSV 등록·다른 LAN 모델·다른 사용자 동시 실행·실물 모바일 키보드/터치·장문/모델 성능은 추가로 시험한 것이 아니다.7.003초는 짧은 안내 요청의 접수→종료 시간으로 일반 성능으로 확대하지 않는다. 상단 별/상태 색상·좁은 폭 메뉴 두 줄011은 이번에 구현하지 않았으며 기존 상단 레이아웃이 보이는 것이 의도된 범위다.

## 사후 Validation1~8·복구

1. 거버넌스: 원문/검증 해시·private 백업을 대조하고 해당 Staging13개와 helper 임시1개만 정리했다. 원래 다른 dirty9개는 보존했다.
2. 의도: 검증된007/009/010만 실제 운영에 반영하고011은 PROPOSALS/UNIMPLEMENTED_PROPOSALS 및 별도 계획으로 남겼다.
3. 논리: root178개와 실제 DB 사본을 통과했고 기존 lifecycle 이력을 허위 오류로 보던 helper 조건을 원본 대조로 보완했다.
4. 운영 영향: 정확한 Git commit·own PID/worker만 전환했다. .env/키·DB 스키마·Nginx/다른 서비스는 보존했다.
5. 보안: 일반 계정·익명 경계와 CSRF/명시적 등록 흐름을 유지했다. 비밀/DB는 private에만 보존하고 결과에는 원문을 넣지 않았다.
6. 복구: 이전 commit과 정지 시점 두 DB/설정/프로세스 환경·후보 ZIP을 서버/현재PC에 보존했다. 코드 복귀 때는 최신 대화·휴지통/삭제 원장·감사 행을 유지하고 과거 DB로 덮지 않는다.
7. UX: 실제 접기·새로고침·CSV 링크/팝업/Escape·reload와 두 viewport를 확인했다. 부족한 화면의 스크롤 허용과 오류 재시도 분기는 합성 검증으로 구분한다.
8. 메타: 합성/실제 검증·테스트 부수 기록을 구분하고 PC 요약 행의 공간 변화 및 미검증 범위를 명시했다. 승인 요청 없이 새 기능/권한/외부 메시지를 추가하지 않았다.

기계 근거는 [production-verification.json](012_AI_Staging_Production_Release/production-verification.json),[실제 UI 측정](012_AI_Staging_Production_Release/production-ui-verification.json),[병합 전 검증](012_AI_Staging_Production_Release/validation-before-deploy.json)이다. 마지막 문서/스크린샷 이력 commit은 실행 파일을 변경하지 않는 별도 commit으로 서버에 fast-forward 동기화하며 서비스 재시작을 반복하지 않는다.
