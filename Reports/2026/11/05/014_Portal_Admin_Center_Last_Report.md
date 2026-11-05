---
artifact_id: REPORT-20261105-014
work_id: PLANNED-20261105-PORTAL-ADMIN-LAST
owner: Codex
status: completed-plan-registration
implementation_status: not-started
---

# 메인 포털 관리자 센터 마지막 고정 계획 등록 검토

recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0 및 context 선택을 확인했다. 직전에 읽은 변경 없는 공통/검증 노드를 승계하고 계획/제안 원장 규칙과 반응형 규칙을 확인했다.

현행 `templates/portal.html`은 API 응답을 그대로 공유 renderer에 전달한다. `static/js/menu_cards.js`의 `orderAdmin`은 관리자 센터 내부 메뉴 순서용이고, `app.py`의 관리자 센터 식별자는 `admin_center`다. 이번에는 이 소스를 수정하지 않고 포털 범위의 후속 계획을 등록했다.

## 계획 Validation1~8

1. 거버넌스: Plan/Task/Report014와 두 제안 원장만 기록한다. 기존 dirty 기록·미실현011/013과 기능 소스를 보존한다.
2. 의도: 관리자 센터 항상 마지막, 나의 결재함·AI 도우미·향후 메뉴는 그 앞에 표시하는 요구를 명시했다.
3. 논리: 나머지 메뉴의 상대 순서를 보존하고 신규 메뉴·재로드에도 유지되는 규칙을 계획했다. 단순 DB 정렬값 상향만으로 완료하지 않는다.
4. 운영 영향: 메인 포털로 범위를 한정하고 관리자 센터 내부 정렬·공유 renderer의 다른 화면에 영향을 주지 않도록 했다. 이번 등록의 실행 영향은 없다.
5. 보안: 권한 필터를 유지하며 일반 사용자에게 관리자 메뉴를 새로 노출하지 않는다.
6. 복구: 문서 가산 기록만 수행한다. 코드/DB 변경에 대한 rollback은 해당 없으며 기존 원장 본문과 과거 계획을 보존한다.
7. UX: 화면·DOM·키보드 순서 일치, 메뉴 누락/중복, 관리자/일반 사용자·빈 목록·신규 메뉴·모바일/PC를 향후 확인 항목으로 뒀다.
8. 메타: 계획 등록 완료와 구현 미착수를 구분한다. 기능 테스트·스크린샷 검사·서버 배포를 수행한 것으로 집계하지 않는다.

대상은 [계획014](../../../../Plans/2026/11/05/014_Portal_Admin_Center_Last_Plan.md), [등록 Task](../../../../Tasks/2026/11/05/014_Portal_Admin_Center_Last_Task.md), [제안 원장](../../../../PROPOSALS.md), [미구현 목록](../../../../UNIMPLEMENTED_PROPOSALS.md)이다. 문서 링크·동일 work_id·원장 중복 여부와 변경 전 소스/기존 계획 해시를 대조한다.

등록 검증 결과: 세 문서의 work_id 일치, 두 원장에 신규 항목 각1개, 관련 링크9개 모두 확인했다. 두 원장의 기존 본문은 보존했고 포털 template·공유 JS·app 및 기존011/013 계획, 총5개 참고 파일의 SHA가 변경 전과 동일하다. 기능 코드/DB·Staging 변경, 테스트 실행·서버 배포는 수행하지 않았다.
