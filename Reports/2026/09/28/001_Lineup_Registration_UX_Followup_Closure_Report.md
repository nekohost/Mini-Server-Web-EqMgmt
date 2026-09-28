---
artifact_id: REPORT-20260928-001
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-28T16:35:07+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/008_Lineup_Registration_UX_Followup_Production_Merge_Task.md
  - ../../../../Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md
  - ../10/017_Lineup_Registration_UX_Followup_Production_Merge_Report.md
---

# Task 008 잔여 검증 및 운영 완료 보고서

판정: **완료**. 오래된 Git·Linux 미완료 기록을 대조하고 실제 Chrome 검증에서 발견한 스크롤 결함까지 수정·배포했다. 현재 운영 대상은 사용자가 지정한 Linux 백업 서버이며, 미니서버 별도 배포는 이 완료 판정의 조건이 아니다.

## 1. 기존 작업과 이번 변경

- 원래 모달·노드 선택 UX 구현은 `31f8027b9494b28f0df0ff8c7d0949091fa31523`에 이미 커밋되어 main에 포함되어 있었다. Task 체크리스트가 이후 배포 상태를 반영하지 못했다.
- 잔여 작업 확인 과정에서 백업 서버를 `9537829`까지 fast-forward 동기화했고, 실제 사용자 화면 검증을 수행했다.
- VS Code 확장 세션에서는 브라우저 URL 판별 오류로 중단되었다. ChatGPT Windows 앱 세션의 Chrome 확장 연결에서는 URL·DOM·스크린샷이 정상 제공되어 검증을 재개했다. Edge는 사용하지 않았다.
- 계정 생성 보고서가 지정한 기존 일반 사용자 계정 `guide_test_user`로 로그인했다. 서버의 0600 자격증명 파일을 사용했으며, 평문 비밀번호를 보고서·Git·대화에 기록하거나 재설정하지 않았다.

## 2. 실제 결함과 수정

모달 본문을 아래로 스크롤한 뒤 취소하고 재열면 `scrollTop=393`이 남았다. 기존 `openModal()`은 `display:none`인 모달 본문에 먼저 `scrollTop=0`을 쓴 뒤 표시했다. 실제 Chrome에서는 이 쓰기가 적용되지 않아 표시 후 이전 위치가 복원됐다.

`templates/index.html`에서 기존 초기화 두 줄을 `modal.classList.remove('hidden')` 직후로 옮겼다. 카탈로그 선택 복원·저장·API·DB 스키마·권한은 변경하지 않았다.

기존 회귀는 초기화 코드 문자열의 존재만 확인하므로 순서 결함을 검출하지 못했다. 이를 실제 `openModal()`을 실행하고 숨겨진 본문의 스크롤 쓰기가 무시되는 DOM fixture로 교체했다. 신규·수정 모달 모두 첫 열기와 재열기를 검증한다.

| 검증 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 신규·수정 모달 실행 회귀 | 두 경우 모두 `393 !== 0` 실패 | 통과 |
| 등록 UI 회귀 전체 | 13/15, 위 두 실패 재현 | 15/15 PASS |
| 카탈로그 정적 회귀 | 변경 영향 점검 | 5/5 PASS |
| 운영 Chrome 취소 후 재열기 | 이전 위치 393 유지 | 393 → 0 |
| 운영 Chrome X 닫기 후 재열기 | 후속 검증 대상 | 328 → 0 |

## 3. 실브라우저 검증

`https://nekohost.org/my_equipment?page=1`, Chrome, 일반 사용자 권한으로 수행했다. 노드 추가를 위한 신청서만 열고 취소했으며 실제 등록 신청·장비 저장·임시저장은 제출하지 않았다.

- 카테고리·제조사 선택 직후에는 노드 추가 신청 진입 UI가 나타나지 않는다.
- 최상위 노드 추가 항목 선택 시 신청 버튼이 나타나고, 빈 값·기존 노드 선택 시 제거된다.
- 하위 노드 추가 항목에서도 같은 전환이 동작한다. 신청서에는 스마트폰·삼성·부모 갤럭시가 정확히 전달된다.
- 기존 경로 `갤럭시 → S 시리즈 → 21 → 울트라`와 옵션 `256GB/블랙`을 선택할 수 있다.
- 자식이 없는 말단 노드의 선택기에 빈 상태 안내와 노드 추가 항목이 표시된다. 추가에서 빈 값으로 돌아오면 신청 UI가 사라지고 기존 옵션 영역이 복원된다.
- 본문 스크롤 `194 → 722` 동안 header Y=17, footer Y=714가 유지됐다.
- 보완 배포 후 취소와 X 닫기 모두 재열기 스크롤 0을 확인했다. 브라우저 console error는 0건이었다.

| Chrome viewport | 모달 높이 | 상단 영역 Y | 하단 영역 Y | 결과 |
| --- | ---: | ---: | ---: | --- |
| 320×640 | 608 | 17 | 458 | 화면 내 배치·본문 스크롤·모든 하단 버튼 경계 통과 |
| 390×844 | 812 | 17 | 714 | 동일 통과 |
| 768×600 | 568 | 17 | 486 | 동일 통과 |
| 1235×653 | 621 | 17 | 539 | 동일 통과 |

검증 종료 후 viewport override를 해제하고 테스트 계정에서 로그아웃했다. 원래 사용자가 열어둔 로그인 탭은 닫지 않았다.

### 범위의 한계

운영 DB에 테스트 데이터를 남기지 않기 위해 APPROVED/PENDING 생성 제출과 저장은 실행하지 않았다. 승인 결과 재선택·수정 연결 보존은 격리 Node 회귀로 확인했다. 운영에는 비어 있는 최상위 카테고리/제조사 조합이 없어 최상위 빈 안내 문구는 fixture, 말단의 빈 하위 안내는 실제 브라우저로 확인했다. 수정 장비의 스크롤 초기화는 fixture로 검증했으며 테스트 계정에 실제 소유 장비를 새로 만들지는 않았다.

## 4. Git 및 백업 서버 적용

- 수정 커밋: `3ced6e8a064c3dca691df838d9863be3c1e699e8` — `fix: 장비 등록 모달 표시 후 스크롤 초기화`, origin/main push 완료.
- 서버: `eqmgmt-backup` / `/home/nekohost/services/Mini-Server-Web-EqMgmt`.
- 현재 HEAD·추적 파일 무변경·프로세스 경로를 선검사하고, 원격 후보의 Jinja 구문 검사 후 fast-forward pull했다.
- 템플릿 캐시를 갱신하기 위해 기존과 동일한 실행 명령·환경으로 재시작했다. 환경의 비밀 값은 출력하거나 보관하지 않았다.
- 웹 프로세스: `119262 → 261921`. localhost와 공개 HTTPS `/login` 모두 HTTP 200, 배포 후 기존 일반 사용자 세션의 실제 화면도 정상 동작했다.
- 배포 전 온라인 DB 백업과 원본 템플릿을 private release 디렉터리에 보존했다. 실패 시 템플릿만 복원하고 서비스 재기동하는 경로를 준비했으며, 실제 복구는 필요하지 않았다.
- DB `integrity_check=ok`, 외래키 위반 0건, 배포 전후 업무 테이블 10개의 행 수·내용 해시 동일. 정상 로그인·로그아웃·접속 감사 기록은 별도로 발생할 수 있다.
- 배포 템플릿 SHA-256: `98bfa63b313c9fcd04e4bce0f2a6ebaca2942f9ca8849eacf620d34ae8d8fff2`, Windows 작업본과 Linux 파일 일치.
- 복구 보관 위치: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/lineup-modal-scroll-20260928T073149772470Z`.
- 기존 서버 `.venv.incomplete-20260907/` 및 기존 복구 자산을 보존했다. 다른 작업자의 Report 016 수정도 편집·커밋하지 않았다.

## 5. 증거 및 문서 정리

- [실제 배포 결과](./lineup-registration-ux-closure/deployment-result.json)
- [검토 후 실행한 제한 배포 스크립트](./lineup-registration-ux-closure/deploy_template_fix.py)
- [모바일 390px 수정 후](./lineup-registration-ux-closure/mobile-390-after-fix.png)
- [모바일 320px 수정 후](./lineup-registration-ux-closure/mobile-320-after-fix.png)
- [낮은 화면 768px 수정 후](./lineup-registration-ux-closure/short-768-after-fix.png)
- [PC 수정 후](./lineup-registration-ux-closure/desktop-after-fix.png)

`desktop-modal.png`, `mobile-390-model-path.png`, `mobile-390-scroll-bottom.png`, `mobile-320-modal.png`는 보완 배포 전 기능 확인·결함 재현 증거다. `*-after-fix.png`가 수정 이후 증거이며, full-page 캡처는 viewport 아래의 배경 페이지까지 포함할 수 있다. 실제 수용 판정은 위 DOM viewport·경계 측정과 화면 확인을 함께 사용했다.

Task 008의 Git 및 Linux·실브라우저 두 잔여 항목, Task 일자 index, Plan 004와 기존 Report 017의 현재 상태를 완료로 갱신했다. 2026-09-10 당시의 테스트 수·해시·미수행 기록은 역사적 기록으로 명시하여 보존했다.

최종 정합성 검사: governance 1.8.1 errors/warnings 0, 문서 링크 10건 유효, `git diff --check` 통과. 보존 대상 Report 016의 작업 전후 SHA-256은 `3BCF109AB1FFB4F1D568D60E360AE5FC6C2317D384E41A317221B61A887072E3`로 동일하다.
