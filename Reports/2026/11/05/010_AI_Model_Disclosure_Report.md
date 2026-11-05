---
artifact_id: REPORT-20261105-010
work_id: STAGING-20261105-AI-MODEL-DISCLOSURE
owner: Codex
status: completed-in-staging
---

# AI 모델 선택 접이식 검토·검증

계획/구현 승인 범위는 현재 CSV+viewport Staging에 모델 선택/새로고침의 기본 접힘 배치를 병합하는 것이다. recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0 및 context26개를 두 pack 순서로 확인했다. 실제 앱 import/브라우저 검사는 Linux 격리 fixture에서만 수행한다.

## 사전 Validation1~8

1. 거버넌스: 기존009 overlay와 보고서를 보존하고010 계획/Task/검증만 추가한다. template/CSS와 필요한 검사 보조를 Staging에서 편집하며 운영 root/DB/서비스·다른 dirty 파일은 변경하지 않는다. 외부 라이브러리는 필요 없다.
2. 의도: 모델 선택과 목록 새로고침만 추론 아래·지원 안내 위의 접이식으로 이동한다. 기본 접힘으로 공간을 줄이며 추론 select/보내기를 계속 노출한다. 사용자가 펼치고 고르는 기능을 폐기하지 않는다.
3. 논리: native details를 사용하므로 새 토글 상태/저장소/비동기 로직이 필요 없다. 기존 ID/DOM을 유지하고 polling/selection rerender가 details를 바꾸지 않는다. 기존 ResizeObserver가 펼침 높이 변화를 처리하는지 검증한다.
4. 영향: 모델 select를 기존 actions 밖으로 옮기므로 CSS selector를 함께 조정한다. 기존 모델/새로고침 크기·포커스 검사는 펼침 상태에서 검사하도록 보완한다. API/업무 JS/스키마는 바꿀 필요 없다.
5. 보안: 기존 권한/CSRF·불투명 모델 ID/disabled 사유·대화별 모델 저장을 유지한다. summary는 고정 문자열이며 모델이 HTML을 삽입하는 경로는 추가하지 않는다. 오류는 접힘 밖에 노출한다.
6. 복구:009 검토 원문 ZIP과 파일 해시를 기준으로 필요한 template/CSS/검사 보조만 복구할 수 있다. 데이터 migration/운영 rollback은 해당 없다. 기존007/009 증거는 덮어쓰지 않는다.
7. 휴먼 에러: native summary가 클릭/키보드 접근 가능한 접기/펼치기를 제공한다. 접힘이 모델 재선택·새로고침·업무 실행을 유발하지 않게 한다. 좁은 화면·열림 중 오류/로딩·초안과 읽는 위치 보존을 점검한다.
8. 메타: 접힌 모델 control의 비노출 상태를 기존 항상 노출 기대값과 혼동하지 않는다. 기본 접힘·펼침 크기와 기능·최종 스크린샷을 구분하고, 실제 결과만 집계한다. web_search/서버 반영/운영 계정 작업을 추가하지 않는다.

## 구현 및 초기 검증

009 원문 ZIP12개 파일을 검증했고 overlay10개 모두 현재와 바이트/해시가 일치한 상태에서 시작했다. 원본은 `Reports/2026/11/05/009_AI_Viewport_Scrollbar/reviewed-merged-sources.zip`, SHA256 `d72f52fac03969c02230141e2e8bd85b85d3ac2ad8e8b1a5ed3cd4189006b973`에 보존되어 있다.

template의 모델 select/새로고침 DOM을 native `details#ai-model-settings`로 옮겼다. `AI 모델 선택` summary만 기본 표시하고 `open` 속성은 없다. 추론/보내기는 위에, 지원 안내는 아래에 있다. 모델 상태·오류/로딩은 details 밖에 유지한다. CSS는 이동한 select에도 기존 크기/폰트를 적용한다. 기존 업무 client JS와 policy는009와 해시가 일치하며 API·DB·권한 동작을 수정하지 않았다.

[전용 검사](010_AI_Model_Disclosure/screenshots-disclosure-round1/results.json)는320/390/820/1440px × 두 테마,8개 화면/168개 항목 모두 통과했다. native summary 클릭, 기본 접힘/펼침·초안/모델/추론/읽는 위치, 접기 동작의 불필요한 요청 없음, 로딩 중 접기, 접힌 상태의 오류 사유, 새로고침 재시도, 모델 저장/CSRF·별도 지원 안내를 확인했다. 전체 회귀는 별도로 진행한다.

| 폭 | 접힌 composer 높이 | 펼친 높이 | 접힘으로 확보되는 대화 높이 |
|---|---:|---:|---:|
| 320px | 204.781px | 256.781px | 52px |
| 390px | 179.188px | 231.188px | 52px |
| 820/1440px | 171.188px | 215.188px | 44px |

위 수치는 **새 UI의 펼침 대비 접힘** 비교다. 종전 PC는 모델·추론이 한 줄이어서 새로 요구된 세로 순서의 summary 행이 추가되면 종전보다 composer가 높아질 수 있다. 전체 이전/이후 세로 공간 감소로 해석하지 않는다. 종전과 동일한 초기 과제/화면의 비교 수치도 회귀 결과에서 구분해 남긴다. 모바일/PC 모두 기본 상태에서 모델 제어 자체는 노출되지 않는다.

닫힌 details 후손은 Chromium이 layout 측정값을 유지하므로 모델 select의 bounding rect만0인지로 숨김을 판정하지 않는다. 닫힌 panel과 summary의 높이가17.594px로 일치하고 실제 스크린샷에 제어가 보이지 않는지, 펼쳤을 때 visibility/44·52px의 공간 변화가 나타나는지를 함께 확인했다.

## 최종 검증 및 이전 화면 비교

| 검사 | 결과 | 증거 |
|---|---|---|
| 대화·휴지통·모델/추론·CSV·viewport·모델 접이식 통합 | 51개 화면/3431개 검사, 실패0 | [전체 결과](010_AI_Model_Disclosure/screenshots-merged-round1/results.json) |
| 짧은 모바일 팝업320×620/390×844 × 두 테마 | 4개 화면/112개 검사, 실패0 | [추가 결과](010_AI_Model_Disclosure/screenshots-short-mobile/results.json) |
| 최종 합계 | **55개 화면/3543개 검사, 실패0** | 전용8개/168개 재실행과 기존 backend는 중복 집계하지 않음 |
| Python AST / node --check | 7개 / 2개 통과 | [검증·소스 해시](010_AI_Model_Disclosure/validation.json) |
| root11개 / 업무 client JS·policy009 기준 | 모두 SHA 일치 | 운영 소스/API·DB 미변경 |
| governance1.8.1 validate | 오류0/경고0 | manifest44개 |

통합 fixture digest는 `4a2efb07e73aea670032e4394218addcc1c11e89aa432b377743c84e85072177`, 짧은 모바일은 `7ff1cb3823733e9ecb15b0118e2e37bfb0b3a12c52200daaf5bdbb05bb967ef2`다. 이번 browser-only의 unittest0은 backend를 실행한 수가 아니다. 변경 없는 backend178개는007 검증 증거를 승계한다. 새 소스는 [검토 원문 ZIP](010_AI_Model_Disclosure/reviewed-merged-sources.zip)에 보존한다.

009/010의 같은 초기 Qwen-medium 대화·너비·높이1000px 측정(kind=layout-measurement)을 대조했다. API 응답/안내/테마 조건이 같은 데이터다.

| 실제 폭 | 종전 composer | 현재 기본 접힘 composer | 대화 높이 변화 |
|---|---:|---:|---:|
| 모바일430px | 205.594px | 179.188px | **+26.406px** |
| PC1425/1440px | 145.594px | 171.188px | **−25.594px** |

모델 제어는 기본으로 숨겨지고 사용자가 필요할 때만 펼친다. 모바일에서는 기존 모델/추론 두 줄을 줄여 전체 높이도 절약한다. PC는 종전 제어가 한 줄이었고, 요청한 `추론 → AI 모델 선택 → 추론 단계 지원 안내`의 세로 순서를 지키면서 요약 행이 추가되어 전체 높이가 늘었다. 이를 전체 기기에서의 세로 공간 감소라고 보고하지 않는다.

직접 검토한 대표 화면:

- 기본 접힘 PC1440px: [라이트](010_AI_Model_Disclosure/screenshots-merged-round1/screen-022.png) / [다크](010_AI_Model_Disclosure/screenshots-merged-round1/screen-023.png)
- 기본 접힘 모바일390px: [다크](010_AI_Model_Disclosure/screenshots-merged-round1/screen-013.png)
- 펼침 PC1440px: [다크](010_AI_Model_Disclosure/screenshots-merged-round1/screen-042.png)
- 펼침 모바일390px: [라이트](010_AI_Model_Disclosure/screenshots-merged-round1/screen-037.png)
- 최소 높이/CSV 회귀: [모바일390×844 다크](010_AI_Model_Disclosure/screenshots-short-mobile/screen-003.png)

추가로 발견된 화면 결함은 없다. focus outline은 summary/보내기 버튼의 프로그램 포커스 표시이며 합성 데이터의 `<img ...>` 문자열은 HTML이 아닌 보안 검사용 텍스트다. 스크린샷에는 보관 예산/긴 대화 등 합성 상태가 포함되어 있다. 실제 모바일 키보드·Tab/Enter 키 조작·핀치 확대/터치 드래그·다른 브라우저/실모델 요청은 이번 검증에 포함되지 않았다.

## 사후 Validation1~8

1. 거버넌스:010 계획/Task/검증과009 원문/해시를 연결했다. 현재 Staging만 수정하고 기존 기록/다른 dirty 파일은 보존했다.
2. 의도: 추론 아래·지원 안내 위에 기본 접힘 모델 선택/새로고침을 배치했다. 기존 기능과 직접 펼치는 동작을 유지했다.
3. 논리: native details를 쓰고 새 상태 저장이나 비동기 호출을 추가하지 않았다. 크기/포커스 회귀는 펼친 상태, 기본 노출은 접힌 상태로 구분했다.
4. 영향: 기존 대화·휴지통·모델/추론·CSV·높이/테마 검사가 통과했다. root11개 및 업무 client JS/policy SHA가 유지되었다.
5. 보안: 선택 저장/CSRF·불투명 모델 ID/지원 단계 비활성화를 유지하고 접기 동작이 요청을 보내지 않는 것을 확인했다. 모델 오류는 접힘 밖에 보인다.
6. 복구:009/010 검토 원문을 별도 보존했다. template/CSS/검사 보조만 되돌릴 수 있고 DB/운영 복구는 필요 없다.
7. 휴먼 에러: 로딩/오류 중 접었다 펼쳐도 사유·초안·선택값을 유지하고 재시도할 수 있다. 좁은 화면과 CSV 팝업도 접근 가능했다.
8. 메타: 전용 검사를 중복 집계하지 않고 PC 높이 증가와 모바일 감소를 분리했다. 현재 증거의 합성/상호작용 한계를 명시했다.

검토 당시 Staging README/overlay는 [원문 ZIP](010_AI_Model_Disclosure/reviewed-merged-sources.zip)에 보존한다. 재현은 보존한 원문 또는 병합된 `tests/run_assistant_fixture.py`의 Linux fixture runner를 사용하며 결과 디렉터리는 새 경로로 지정한다. 이 검증 시점에는 Git commit/push·운영 root 병합·서버 배포·운영 DB 변경을 수행하지 않았다. 후속 [012 운영 반영](012_AI_Staging_Production_Release_Report.md)에서 원문 보존 후 해당 Staging을 정리한다. web_search는 기존 보류 상태를 유지한다.
