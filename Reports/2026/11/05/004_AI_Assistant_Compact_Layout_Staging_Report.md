---
artifact_id: REPORT-20261105-004
work_id: STAGING-20261105-AI-COMPACT-LAYOUT
parent_work_id: PLAN-20261105-AI-COMPACT-LAYOUT
owner: Codex
created_at: 2026-11-05
status: complete
reviewed_at_utc: 2026-11-05T03:51:21Z
---

# AI 도우미 공간 절약 배치 병합·검증

승인 Plan 003을 기존 `Staging/20261105-ai-ux-trash`에 가산 병합한다. 기존 1~7번 기능, v4/worker/guard와 관리자/옛 화면 정리 후보를 보존한다. 실제 구현·실행 결과는 아래에 추가한다.

## 구현 전 Validation 1~8

1. 거버넌스: recorder ensure 성공, profile은 legacy/runtime-session-mismatch이며 verified=false다. manifest 1.8.1, 오류/경고 0. implement/review/frontend/ux/responsive/handoff/external-execution과 실제 후보/문서 경로로 context 두 pack의 필수 26개 노드를 읽었다. 사용자 승인에 따라 현재 Staging만 수정한다.
2. 사용자 의도: Plan 003의 1~10번을 그대로 승계한다. 기존 산출물의 재작성/폐기가 아니라 제목과 모델 컨트롤의 위치·크기·정상 안내를 개선한다. 선택/출처·권한·데이터 lifecycle은 보존한다.
3. 논리: 기존 DOM ID·이벤트·모델 선택 저장을 유지한다. 캡션 제거의 JS 참조, form 안 새로고침의 type=button, 동적 추론 사유와 모바일 서랍 top 결합을 함께 변경해야 한다. 너비 조정만으로 API/stream/초안을 초기화하지 않는다.
4. 운영 영향: backend/schema/프로바이더 관리/전역 테마에는 변경이 필요 없다. template/CSS/JS와 해당 fixture를 한 후보로 검증한다. 현재 운영 병합·배포를 하지 않는다.
5. 보안/예외: 텍스트 삽입과 미지원 단계 비활성, 실제 실패 사유, read-only 제어, 서버의 기존 권한·CSRF를 유지한다. “장비 업무 가능”만 제거하며 대화 전용 제한/설정 저장 실패를 감추지 않는다.
6. 보존/복귀: 기존 Report 002와 fingerprint는 변경 전 근거로 보존하고 최종 후보는 새 hash/결과로 식별한다. Staging 변경 외 기존 사용자 dirty·HEAD/index·root 주요 소스를 보존한다. DB 복구/삭제가 필요한 변경이 아니다.
7. UX: 760/761 경계·좁은 입력창·긴 이름·default 추론·초기/오류·휴지통·진행 응답·확대/키보드를 검사한다. 한 줄 강제로 작은 터치 영역이나 가로 넘침을 만들지 않는다. W0와 본문 높이를 변경 전후 같은 조건으로 비교한다.
8. 메타/판정: 계획 완료를 구현 완료로 오인하지 않고 실제 검사와 새 PNG를 수집한다. 하위 모델은 사용자가 요청한 gpt-6.1-sol/max로 지정하며 Fast 제어 미제공을 공개했다. 현 단계는 구현 착수 가능이며 실제 검증 결과는 아직 미수집이다.

## 변경 전 기준

기존 manifest의 후보 43개, root baseline의 주요 소스 24개 SHA-256이 모두 일치했다. HEAD와 기존 tracked dirty 9개도 보존한 상태로 시작했다. 새 측정 probe를 통해 기존 합성 Qwen3.8 Flash Next/medium 대화의 기하를 읽었다. 후보 소스는 메모리로 패키징한 뒤에만 작업자 편집을 시작해 변경 전후가 섞이지 않게 했다.

- 기존 사용자 화면: 390/430/820/1440 × light/dark, 8뷰·540 checks 모두 통과.
- 측정 전용: 초기 저장 표·동일 Qwen/medium, 430/1440 light 두 뷰. 측정 뷰를 기능 회귀 개수에 넣지 않는다.
- 변경 전 추론 외곽 폭 W0: 두 너비 모두 **136 CSS px**. 모델 select의 새 최대값으로 사용한다.
- 430px: 내부 헤더 70px, 상단 모델 영역 111.078125px, 본문 scroll 영역 382.859375px.
- 1440px: 내부 헤더 79.59375px, 상단 모델 영역 111.078125px, 본문 scroll 영역 413.046875px.
- 근거: `004_AI_Assistant_Compact_Layout_Staging/before-layout.json`와 `screenshots-before/`. fixture digest `3b8ba88727e35dff7b36be2d9ccd56f0e23d5da8dc5d25a20dc98ea19f91c53b`.

## 통합 중 발견과 수정

- 1차 전체 실행: backend 고유178개는 실패/오류/skip 없이 통과했다. compact16뷰는 공통 line-height 검사에서 중단됐다. Chrome native select가 명시한1.4 대신 `normal`, 버튼은16.8px로 계산했다. 공통 CSS를 native와 일치하는 `normal`로 바꿨으며 컨트롤 높이/글자 크기 기준을 낮추지 않았다. 상세는 `round1-results.json`에 보존한다.
- 정적 제어 흐름 교차 점검에서 기존 `newConversation()`이 생성 잠금을 해제한 뒤 `lifecycleControls()`만 호출하여 model/level/send 잠금이 남는 경로를 발견했다. `modelControls()`로 일관되게 갱신한다. 또한 일시적으로 사라진 모델에 대해 저장된 medium이 default로 덮이는 경로는 unavailable 상태의 disabled 선택으로 보존하고 복귀 시 자동 복원하도록 고쳤다. 실제 지원이 없는 available 모델의 기본값 예외는 유지한다.
- 2차 실행: backend178개, 기존/관리자8뷰는 통과했고 compact16뷰는 모델 목록 실패/재시도/소멸·복귀까지 통과했다. 다음 fallback 폭 검사는 native 화살표 여유를 임의20px로 가정해 중단됐다. 같은 폰트·여백·테두리·옵션을 가진 native select의 실제 고유 너비와1px 이내 비교 및 글자 여유 하한으로 검사 근거를 바꿨다. 실제 정상 폭102px/기본값113px는 각 reference와 같았으며 최소 글자 공간도 충족한다. `round2-results.json`과3차 sizing 지표에 근거가 있다.
- 정확한 뷰포트 검토에서 종전 iframe이 outer scrollbar 때문에 큰 요청 너비에서15px 줄어드는 것을 발견했다. 요청760/761/820/1440이 실제745/746/805/1425였다. `flex:none`과 outer margin을 적용하고 실제 `width`를 덮어쓰지 않으며 requested/actual 불일치 시 실패하도록 강화했다. 기본8너비를 정확히 실행한다. **변경 전 데스크톱 비교 측정은 실제1425px**였음을 정정하고, 같은 초기 상태의1425px와 추가1440px를 별도로 측정한다. 원래 파일의 요청 폭 표기는 과거 근거로 보존하며 이 정정과 함께 해석한다.
- 3차 화면 실행은 실제 요청 폭의 기능24뷰와 치수3뷰·2577 checks가 모두 통과했다. backend를 재집계하지 않는 browser-only 실행이며, backend178개가 통과한2차 이후 이 시점까지 제품 파일은 같고 UI fixture/probe만 변경됐다. 수치는 `round3-review.json`에 분리했다.
- 3차 PNG를 직접 보면서 설정 저장 재시도 성공 뒤에도 이전 global 오류 배너가 남는 UX를 발견했다. inventory/selection notice 소유자를 구분하여 해당 복구 성공이 자기 오류만 지우도록 보완한다. 다른 동시 오류나 backend 작업 실패 이력을 지우지 않으며, 겹친 목록 조회/설정 실패/복구 사례를 추가 검증한다. 최종 화면 실행 결과는 아래에 기록한다.

## 최종 병합 결과

제품 변경은 기존 후보의 `overlay/templates/equipment_ai.html`, `overlay/static/css/equipment_ai.css`, `overlay/static/js/equipment_ai.js` 세 파일에 병합했다. 저장소/v4·worker/guard·조회 정규화·관리자 연결 관리·옛 Strata 화면 정리 후보를 새로 쓰거나 제거하지 않았다.

| 영역 | 최종 동작 |
| --- | --- |
| 좁은 화면 | 760px 이하에서 대화 목록 버튼과 세션 제목 한 줄만 보인다. 긴 제목은 말줄임하며 전체 title/aria 이름을 유지한다. 서랍은 실제 헤더 끝에서 시작한다. |
| 넓은 화면 | 761px 이상에서는 내부 헤더가 display:none/높이0이다. 좌측 현재 세션 선택 강조로 식별한다. 공통 페이지 제목은 유지한다. |
| 모델/추론 | 입력창 하단에 AI 모델→목록 새로고침→추론→전송 순서다. 좁으면 줄바꿈하고 모델 select는 최대136px에서 축소한다(320px에서는95.125px). 정상 추론 폭102px, 필요한 기본값 예외113px는 native 고유 너비와 같다. |
| 크기/표시 | 선택 컨트롤과 새로고침은 font12px/weight400/line-height normal, PC36px·모바일44px 높이로 맞춘다. 상단 모델명·부가 문구·정상 “장비 업무 가능”과 빈 상태 높이를 제거했다. |
| 실패와 복구 | 불가/대화 전용/다음 요청 적용/원래 모델 기록 없음/목록 로딩·실패만 조건부로 표시한다. 동시 목록 조회 성공이 설정 실패를 지우지 않으며, 각각 자기 복구 성공 때만 자기 오류 배너를 지운다. |
| 기존 기능 | 표와 가로 스크롤, 추론 펼침, 모델별 대화 이어가기, 불변 응답 출처, 초안/진행 요청, 휴지통 읽기 전용·복구·영구삭제 확인, CSV/파일, 관리자 흐름을 회귀 검증했다. |

## 본문 공간 측정

같은 초기 저장 표·Qwen3.8 Flash Next·medium·light·세로1000px를 사용했다. 각 비교에서 모델/추론과 root 외곽 폭·높이가 일치하는지 확인한 뒤 scroll 영역 높이를 비교했다. 테스트용 대화 보관량 안내는 양쪽 모두 같은 상태로 유지했다.

| 실제 CSS 화면 폭 | 변경 전 본문 높이 | 변경 후 본문 높이 | 확보한 높이 |
| --- | ---: | ---: | ---: |
| 모바일430px | 382.859375px | 419.34375px | **36.484375px** |
| PC1425px | 413.046875px | 576.125px | **163.078125px** |

기존 desktop fixture의1440 요청은 실제1425였으므로 이를 같은1425 비교로 정정했다. 최종1440px도 정확히 따로 측정했고 본문576.125px, 헤더0, 모델136px·추론102px였다. 이 값은 이 합성 화면의 공간 측정이며 모든 대화/폰트/확대에서 같은 이득을 보장하는 수치는 아니다.

## 최종 검증 근거

| 검사 | 실제 결과 |
| --- | --- |
| Linux backend | **178개 통과, 실패/오류/skip0,35.258초.** Python3.12.3, Linux tmpfs 기능 fixture, WAL/FK/synchronous 변경 없음 |
| 기존 사용자 화면 | 1440/430,2뷰·65 checks 통과 |
| 관리자 화면 | 6뷰·198 checks 통과 |
| 추가 배치/기존 표·휴지통 | 정확한320/360/390/430/760/761/820/1440 × light/dark,16뷰·2394 checks 통과 |
| 최종 화면 전체 | **기능24뷰·2657 checks, 실패0.** 별도 치수 측정430/1425/1440 light3뷰도 통과하며 기능 검사 개수에 넣지 않는다. |
| 정적 | Python AST26개, 외부 JS3개 및 기존 fixture 내 JS2블록 구문 통과. Jinja는 최종 Linux 브라우저가 실제 template을 렌더링했다. |
| 보존 | root 주요24개 hash 동일, HEAD3d9dacc/index빈상태/기존 tracked dirty9개 목록 유지. 기존 후보43개 중35개 동일·8개 후속 수정, 측정fixture1개 추가로 manifest44개 |

backend 통과는2차 combined 실행 digest `9be45b740872dd560899be1d9abd0e6844042748b37596617ae5d15dcd913931`이다. 이후 backend Python22개는 최종 hash와 같다. 최종 notice 수정은 프론트엔드이며 browser-only 실행 digest `ddeb426dad548ea11ee72df43945ec36cc2721177ccccc8a8f66a0083516061e`에서 모든 기존/신규 화면을 다시 검사했다. browser-only의 tests=0을 backend178의 재실행으로 집계하지 않는다.

전체 check 이름/치수/요청 폭·실제 폭/PNG·한계는 [validation.json](004_AI_Assistant_Compact_Layout_Staging/validation.json), 최종44개 파일 hash/기존 변경 목록은 [source-manifest.json](004_AI_Assistant_Compact_Layout_Staging/source-manifest.json)에 있다. 기존 Report002와 중간 실패 JSON을 보존했다.

## 최종 Validation 1~8

1. **거버넌스:** 승인된 Plan003을 승계하고 현재 Staging에 병합했다. Task004와 구현 전 순차 검토 후 세 하위 작업자를 분담했으며 일반 편집은 apply_patch로 한정했다. recorder/profile/context를 통과했고 legacy 사유를 숨기지 않았다. Fast는 도구가 지정/검증 항목을 제공하지 않아 보장하지 않았다.
2. **사용자 의도:** 기존1~7번을 보존하면서1~10번 배치 요구를 적용했다. 공간 확보는 실제 높이로 확인했고 모델136px 상한과 새 추론102/113px를 구별한다. 실패 안내를 없애거나 현재 모델/추론 지원을 확대하지 않았다.
3. **논리/경합:** refresh 단일 pending read, 실패 후 기존 inventory 보존, unavailable 모델의 추론 복원, 새 대화 잠금 해제, notice 소유권을 검증했다. held inventory/동시 설정 실패/각 복구와 기본값 예외, resize 중 draft·stream·노드·설정·CSRF를 확인했다. 발견한 코드/fixture 결함과 중간 실패를 별도 기록했다.
4. **운영 영향:** 제품 변경은 프론트엔드3개이며 backend/schema/큐/서비스가 바뀌지 않는다. DOM 제거와 JS 참조, wrapper/CSS/상태 노드가 결합되어 세 파일을 함께 적용해야 한다. 이번 범위는 후보 병합이며 root 운영 소스 반영·commit/push·서버 배포·실제 DB migration/삭제/timer 설치를 수행하지 않았다.
5. **보안/예외:** 사용자 제목/모델/사유는 textContent/안전 DOM으로 유지한다. 비활성 단계·opaque 선택과 기존 서버 권한/owner/CSRF를 유지했다. 악성 HTML·표·링크·휴지통 쓰기 거절·모델 소멸·읽기/저장 오류·동시 오류를 검사했다. 복구한 자기 오류 외 다른 notice나 실제 작업 실패 이력을 지우지 않는다.
6. **보존/복귀:** 기존 후보를 폐기하지 않았고43개 중35개는 byte hash가 같다. 수정8개는 제품3/fixture3/문서2이며 신규 측정fixture1개다. root24개와 HEAD/index/기존dirty를 보존했다. DB 형식 변경 없이 프론트엔드3파일의 호환 버전 단위로 복귀하는 범위이며 기존1~7번 운영 적용/복귀 절차는 계속 유효하다.
7. **UX/시각:** 최종430 light,1440 dark,320 dark PNG를 직접 보아 줄바꿈·제목·표 내부 스크롤·컨트롤·복구 후 배너 제거를 확인했다. 760/761은 실제 폭 일치 guard로 검사한다. native select 크기는 실제 native reference/글자 여유로 검사했고 검증기 가정으로 제품을 비틀지 않았다. 포커스는 programmatic,720px 재배치와500px 높이는 emulation이므로 실제 Tab/브라우저 자체 확대/스마트폰 키보드 실기기 검증으로 표현하지 않는다.
8. **메타/판정:** 최종 기능24뷰와 치수3뷰를 구별하고 기존 backend178/최종 UI2657의 서로 다른 실행 digest와 보존 근거를 명시했다. 합성 검증을 실제 LAN 모델 품질/운영 부하/장문/디스크 내구성 시험으로 확대하지 않는다. 최종 판정은 **기존 Staging에 병합·검증 완료**이며 사용자 입력이 필요한 미해결 차단 사항은 없다.

대표 최종 화면은 합성 데이터이며 표 안의 XSS 검사용 문자열은 실행되지 않는 텍스트다.

- [430px light](004_AI_Assistant_Compact_Layout_Staging/screenshots-final/screen-014.png)
- [1440px dark](004_AI_Assistant_Compact_Layout_Staging/screenshots-final/screen-023.png)
- [320px dark](004_AI_Assistant_Compact_Layout_Staging/screenshots-final/screen-009.png)

설치/재현은 기존 후보의 `INSTALL-AND-VALIDATION.md`를 따르며 새 검증 경로는 Report004다. Plan001/002·Report002의 기존1~7번 설계/고정 근거는 계속 보존한다.
