---
artifact_id: REPORT-20261105-007
work_id: STAGING-20261105-AI-CSV-POPUP
owner: Codex
status: staging-validated
---

# AI 하단 정리·CSV 팝업 검증

이번 범위는 계획/Staging/정적·격리 화면 검사다. profile은 legacy/runtime-session-mismatch(verified=false)이며 recorder ensure 및 governance1.8.1 validate가 통과했다. context28개는 이전에 읽은 변경 없는 공통/검증 노드와 이번 stack·주석·반응형 본문으로 확인했다. 비밀번호나 실제 사용자 데이터는 후보/fixture에 포함하지 않는다.

## 사전 Validation1~8

1. 거버넌스: 사용자 지시의 Staging 범위에서만 구현한다. root 소스·운영 데이터·Git 배포는 건드리지 않는다. 구조화 편집과 Linux 격리 검증을 사용한다.
2. 의도: 하단 상시 문구와 CSV 영역을 제거하며 기능 안내는 요청 시 대화에서 제공한다. CSV 링크→모달→기존 미리보기/다운로드 흐름으로 공간을 줄인다. 기존 첨부도 팝업으로 옮겨 보존한다.
3. 논리: 서버에 새 임의 파일 실행 권한/라우트/모델 도구를 추가하지 않는다. 현재 고정 CSV API와 명시적 확인 카드를 재사용한다. 팝업 상태와 비동기 응답은 현재 대화/계정에 결합하고 중복 submit·이전 파일/토큰 재사용을 막는다.
4. 영향: template/JS/CSS/SYSTEM 안내와 테스트 harness만 overlay에서 바꾼다. 현재 생성/큐·모델/추론 선택·표·휴지통/v4는 그대로 유지하며 기존2657개 화면 검사와 backend 회귀로 확인한다. 실제 서비스나 프로세스를 재시작하지 않는다.
5. 보안: 모델 출력은 DOM text/정확한 내부 링크 allowlist만 사용한다. 외부/변형 query/HTML/임의 이벤트 링크는 실행하지 않는다. 파일 업로드·CSV token·등록·export는 기존 로그인/메뉴/본인/CSRF/감사 API가 재검증한다. 일반 사용자에게 관리자 권한을 추가하지 않는다.
6. 복구: root baseline과 diff/hash를 보존한다. 이번 후보만 제외하면 기존 운영으로 복귀 가능하며 DB migration은 없다. 닫기나 대화 이동이 업로드·CSV 등록을 자동 재실행하지 않아야 한다. 이미 서버가 받은 명시 등록 결과는 모호 상태와 구분한다.
7. 휴먼 에러: 팝업 제목·선택 범위·현재 작업·로컬 결과 안내, Escape/닫기/focus, preview token 만료·파일 변경·잘못된 파일·중복 submit을 확인한다. 모바일에서 footer를 다시 늘리지 않고 내부 스크롤로 전체 결과와 확인 버튼에 접근한다.
8. 메타: 단순히 footer를 숨긴 것을 CSV 기능 완료로 주장하지 않는다. 실제 링크 클릭과 미리보기/확인/다운로드·오류·상태 경합을 합성 브라우저로 검증하고 실제 픽셀 폭/테마를 근거에 남긴다. 실모델이 안내 문구를 따르는 확률이나 운영 검증으로 확대하지 않는다.

## 구현 결과

[검토 원문·Staging 안내](007_AI_Assistant_CSV_Popup/reviewed-csv-popup-sources.zip)의 overlay8개 파일에만 후보를 작성했다. 운영 대상은 template/JS/CSS/SYSTEM policy4개, 나머지4개는 검증 보조다. 기준 root11개 파일의 SHA가 그대로임을 확인했다. 이 검증 시점에는 root 운영 소스 병합,commit/push,서비스 재시작·CSV 운영 데이터 변경은 수행하지 않았다. 이후009/010 병합과 [012 운영 반영](012_AI_Staging_Production_Release_Report.md)을 별도로 추적하며 병합된 Staging은 원문 보존 후 정리한다.

- 하단 상시 업무 안내와 파일/CSV details를 제거했다. 등록·수정·신청의 사용자 확인 카드와 서버 권한 검사는 유지하며 SYSTEM은 기능 문의 시 허용 도구 범위에서 설명하도록 한다.
- CSV 가져오기·첨부는 고정 내부 링크에서 native dialog로 열린다. 기존 CSV export 확인 카드 및 영수증/대화의 다운로드 링크는 범위를 표시하는 팝업으로 연다. 요청 전에는 팝업/파일 form이 레이아웃을 차지하지 않는다.
- CSV 미리보기·명시 등록·기존 업로드/내보내기 API·CSRF/현재 소유자·한도·감사 경로를 재사용했다. 파일 원문은 모델에 전달하지 않는다. 모델 HTML·외부 URL·추가 query/owner·지원하지 않는 scope는 링크로 실행하지 않는다.
- 닫기/재열기는 미리보기나 등록을 재전송하지 않는다. 파일 변경·다른 대화·휴지통/계정 경계에서 파일과 token을 비우고 늦은 preview를 무시한다. 이미 접수한 실제 쓰기 결과는 같은 계정의 이전 대화 결과 안내로 남기며 새 대화의 미리보기로 섞지 않는다. ACK 유실은 사유를 보여 주고 자동 재등록하지 않는다.

## 검사 결과

| 검사 | 결과 |
| --- | --- |
| 정적 구문 | 후보 Python AST 및 두 JS의 node --check 통과. 실제 Jinja/CSS는 격리 Linux 렌더링으로 확인 |
| Backend | 178개,실패/오류/skip0,34.715초. 실제 운영 앱/DB 미사용 |
| 기본 브라우저 | 35개 화면·2931개 검사,실패0.320/360/390/430/760/761/820/1440px 및 라이트/다크·기존 회귀/측정 포함 |
| 추가 모바일 팝업 | 320×620/390×844,각 라이트/다크4개 화면·112개 검사,실패0 |
| 브라우저 합계 | 39개 화면·3043개 검사 통과 |
| 핵심 경합 | 요청 없는 화면·허용 링크·미리보기/명시 등록·중복 submit·닫기/재열기·파일 변경·422·commit ACK 유실·대화 전환 중 preview/commit·CSRF·첨부 보존 통과 |
| 기존 기능 | 모델·추론·표·대화/휴지통·관리자 회귀와 기존 권한/CSV 서버 검사를 유지 |

Backend 결과 digest는 `acdd8f1bf5581ae4ace79de5006d18139ae890ae8c177673d1750b3cd8d3f35a`, 최종35개 화면은 `1f78c798bed7bada0547699d2cef763fb43a0979e8d32a17d23407e1dd90dd7b`, 추가 모바일은 `26644f42255381f6b3ec8123681a327b94decdf7fb0c8e8158a8819be8ea5e5e`다. Backend 이후 변경은 프론트엔드/검증 보조였으므로178개를 다시 집계하지 않고 영향을 받는 브라우저를 재검증했다. browser-only 실행의 unittest0/NO TESTS RAN은 backend 결과가 아니다.

첫 실행은 sparse overlay 포장에서 변경 없는 strata_retired.html을 누락해178개 중오류2개였다. 해당 기준 자산을 포함하도록 harness를 고친 뒤178개 전체 통과를 확인했다. 브라우저35개 통과 뒤 원문 JSON stdout이 도구 출력 한도에서 잘려 결과 파싱이 실패한 것은 검사 자체 실패와 구분했다. 이후 full results.json 저장과 요약 출력으로 변경해 전체 근거를 보존했다.

## 스크린샷 검토·공간 개선

PC/모바일 및 라이트/다크의 기본 대화·CSV 가져오기·내보내기·첨부 대표9개 이미지를 직접 확인했다. 가로 넘침·컨트롤 겹침·읽을 수 없는 글자·팝업 잘림은 최종 화면에서 발견되지 않았다. 닫기 버튼은44px 이상이고,390×844에서370×554.42px,320×620에서300×421.92px 팝업이 뷰포트 안에 들어온다.

동일 합성 fixture·1000px 높이·기존 검증 기준과 비교했을 때 대화 스크롤 영역은390px 화면에서399.547→474.422px(**74.875px 증가**),1440px 화면에서576.125→631.813px(**55.688px 증가**)였다. 실제 기기 글꼴/높이/조건부 안내에 따라 증가 폭은 달라진다.

스크린샷 검토 중 닫힌 팝업의 결과 안내가 재열기 후에도 외부 배너에 중복되던 부분을 수정했다. 파일 안내에 별도 source를 부여해 재열기 시 자기 배너만 지우며 다른 오류는 유지한다. 관련 회귀와 최종39개 화면이 통과했다. 미해결 시각적 결함은 없다.

- [하단을 정리한 PC 기본 대화](007_AI_Assistant_CSV_Popup/screenshots-final/screen-023.png)
- [PC CSV 가져오기·다크](007_AI_Assistant_CSV_Popup/screenshots-final/screen-034.png),[라이트](007_AI_Assistant_CSV_Popup/screenshots-final/screen-033.png)
- [모바일390×844 CSV 가져오기](007_AI_Assistant_CSV_Popup/screenshots-short-mobile/screen-003.png)
- [CSV 내보내기 팝업](007_AI_Assistant_CSV_Popup/screenshots-final/screen-032.png)
- [모바일320×620 첨부 팝업](007_AI_Assistant_CSV_Popup/screenshots-short-mobile/screen-000.png)
- [통합 검증·소스 해시](007_AI_Assistant_CSV_Popup/validation.json),[기본 전체 결과](007_AI_Assistant_CSV_Popup/screenshots-final/results.json),[추가 모바일 전체 결과](007_AI_Assistant_CSV_Popup/screenshots-short-mobile/results.json)

이미지는 실제 후보 DOM/CSS를 Linux Chromium에서 합성 데이터로 렌더링한 Staging 근거다. 프로그램 focus 및 native dialog cancel 이벤트를 검사했으며 실기기 키보드·native Tab·실모델의 고정 링크 안내 준수나 실제 운영 CSV 전송을 검증한 결과는 아니다. SYSTEM 변경을 포함한 같은 후보를 운영에 적용하는 후속 단계는 이번 지시에 포함되지 않는다.

## 추가 지시·최종 판정

작업 도중 추가 지시한 test03/테스트3,test04/테스트4,test05/테스트5 생성은 GPT-6.1 Sol/max로 요청한 하위 에이전트의 독립 운영 작업으로 완료했다. Fast는 도구에 별도 옵션이 없어 적용을 단정하지 않는다. 일반 사용자·이메일 없음·지정 규칙의 비밀번호와 실제 HTTPS 로그인/관리자 API403을 확인한 [Report008](008_Test_User_Accounts_03_05_Report.md)을 별도로 보존한다. CSV 후보의 운영 DB 미사용과 이 승인된 계정 가산을 구분한다.

요청된 계획→Staging→정적/스크린샷 검사가 완료됐다. 기존 root 소스와 다른 dirty/기록·보류037/AI-TECHDEBT-001은 유지하며 이 후보를 운영에 병합하거나 배포하지 않았다.
