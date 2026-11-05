---
artifact_id: REPORT-20261105-009
work_id: STAGING-20261105-AI-VIEWPORT
owner: Codex
status: completed-in-staging
---

# AI 화면 높이·scrollbar Staging 통합 기록

scope는 사용자 승인된1/2번의 계획·현재 Staging 병합/검증이다. web_search는 검토/구현하지 않는다. recorder/profile legacy(runtime-session-mismatch)·governance1.8.1 validate와 context26개(이미 읽은 변경 없는 공통/검증 노드)를 확인했다. 기존007 기능·8개 후보와 원래 root11개 SHA를 보존한다.

## 사전 Validation1~8

1. 거버넌스: 같은 CSV Staging만 변경한다. 운영 root/DB/서비스·다른 dirty는 보존한다. 이전 완료007 증거를 수정해 덮지 않고 원문 ZIP/해시와 새009를 연결한다.
2. 의도: 최소 조건 충족 시 문서 전체 세로 스크롤을 없애고, 실제 대화/표 안의 스크롤 UI를 다크/라이트에 맞춘다. 최소 미충족 화면은 잘라 숨기지 않는다. CSV 기능과 상태는 유지한다.
3. 논리: viewport/top/main 여백·고정 제어 높이를 실측한다. observer→rAF로 배치하고 동일 값 쓰기를 생략해 resize 반복을 막는다. page scroll에 따라 높이가 늘어나는 피드백을 피하고 viewport/폰트·header 크기 변경을 처리한다.
4. 영향: 독립 AI CSS/JS와 검사 보조만 병합한다. 공통 프레임 파일·테마 배경·백엔드 API/스키마는 변경하지 않는다. 이전 backend178은 재집계하지 않고 실제 프론트엔드 변경 범위와 CSV/lifecycle 회귀를 재검증한다.
5. 보안: 새 서버/외부 요청·권한·모델 도구가 없다. 측정 값은 스타일/상태용이며 데이터·사용자·권한을 바꾸지 않는다. forced-colors/스크롤 접근성도 유지한다.
6. 복구:007 원문과 root baseline을 보존한다. observer/dispose·CSS fallback을 독립적으로 되돌릴 수 있다. 화면 상태를 reset하거나 코드/DB를 과거로 되감지 않는다.
7. 휴먼 에러: 좁고 낮은 창·키보드/확대 상황에서도 최소 높이와 페이지 스크롤을 허용한다. native scrollbar 기능·focus·CSV 닫기/등록 확인을 유지하고, 배경 page overflow를 숨기는 방식으로 버튼을 자르지 않는다.
8. 메타: 실제 document 높이/모드/내부 스크롤 이동을 기록한다. CSS 색상 선언만으로 검증 성공을 주장하지 않는다. 합성 Chromium/리사이즈 검사와 실제 모바일 키보드·타 브라우저 범위를 구분한다.

## 통합 구현 및 보존

007 원문 overlay8개와 README/baseline 총10개를 [원본 ZIP](007_AI_Assistant_CSV_Popup/reviewed-csv-popup-sources.zip)에 보존했다. SHA256은 `0a83a9629bae9e359bcb83a4ed0dbe409c1260f5449ce386ceccd81b58bca62c`이며 [보존 메타데이터](009_AI_Viewport_Scrollbar/parent-007-archive.json)에 파일별 해시도 남겼다. 기존007 검증 문서/결과는 변경하지 않는다.

현재 후보의 CSS/JS에 실측 높이와 AI 영역 scrollbar 테마를 가산했다. 기존 template/policy·CSV popup·명시적 등록 확인·권한 API는 그대로다. JS는 viewport 높이에서 root의 문서 기준 top 및 조상 하단 여백/테두리를 빼고 1px의 반올림 여유를 둔다. 기본 최소는 PC620px/모바일550px이고, 실제 고정 제어 영역과 대화 읽기120px가 더 필요하면 최소를 올린다. 부족한 화면/핀치 확대는 minimum 모드로 두어 문서 스크롤을 허용한다. 최대1250px 제한은 유지한다.

root/main/내비게이션/대화 크기와 window/visualViewport/폰트 변화는 rAF 하나로 모아 측정하며 같은 값은 다시 쓰지 않는다. pagehide에서 observer·listener·예약 frame을 해제한다. resize 중 대화/초안/모델/추론 및 읽는 위치를 재생성하거나 새 업무 요청을 보내지 않는다.

스크롤은 native 동작을 유지하고 대화·좌측 목록·가로 표·코드/추론/입력·CSV 미리보기/팝업 내부에만 테마별 track/thumb/얇은 폭을 적용했다. dark track은 `#111a27`, thumb는 `#61758d`이며 밝은 테마는 `#edf1f6`/`#748399`다. forced-colors에서는 OS의 auto 대비 설정으로 복귀한다. 공통 프레임/다른 화면·테마 배경은 변경하지 않았다.

## 높이 검사 방식과 중간 결과

첫 가상 시간 검사(round1)는8개 모두 fixture 완료 결과를 반환하지 못했다. 타이머로 완료 대기를 바꾼 round2에서는 rAF/observer 반영 전의 이전 크기가 남아8개가 실패했다. 이 실패 기록을 보존하고, 제품 코드를 검사에 맞춰 우회하지 않았다. 대신 격리 Chromium의 private CDP pipe를 통해 실시간 프레임을 사용하는 검사 보조를 추가했다. 추가 설치/디버거 TCP 포트/운영 브라우저는 사용하지 않으며 종료 시 프로세스 그룹과 fd를 정리한다. 기존 회귀 검사의 가상 시간 경로는 그대로다.

[실시간 프레임 round3](009_AI_Viewport_Scrollbar/screenshots-viewport-round3/results.json)에서320/390/820/1440px × 두 테마,8개 화면/284개 검사가 모두 통과했다. 합성 보관량 초과 안내·긴 대화 목록·20열 표/50문단을 넣어 제어 영역이 커지는 상황도 포함한다.

| 화면 | viewport / document 높이 | AI 높이 | 판정 |
|---|---:|---:|---|
| 모바일390×844 | 844 / 844px | 710px | 문서 세로 scrollbar 없음 |
| 좁은 모바일320×844 | 844 / 844px | 710px | 내용 기준 최소589px도 충족 |
| PC1440×900 | 900 / 900px | 772px | 문서 세로 scrollbar 없음 |
| 모바일390×1100 | 1100 / 1100px | 966px | 늘어난 높이 자동 반영 |
| 같은 모바일의 내비게이션48px 증가 | 1100 / 1100px | 918px | 상단 증가만큼 AI 높이 감소 |
| 모바일390×420 | 420 / 683px | 550px | minimum 모드, 페이지 스크롤 허용 |
| PC1440×420 | 420 / 747px | 620px | minimum 모드, 페이지 스크롤 허용 |

가로 표 scrollLeft/대화 scrollTop 이동, 테마 즉시 전환, breakpoint 왕복,12회 관찰 시 높이 안정성, 초안/모델/추론/DOM 노드/읽는 위치 보존, resize에 따른 POST 증가 없음 및 기존 CSV 팝업 열기/닫기를 확인했다. 강제 색상 환경·실물 터치/스크롤 thumb 드래그·실제 모바일 키보드/브라우저 확대는 이 Chromium 합성 검사와 구분한다.

## 최종 통합 검증

| 검사 | 결과 | 증거 |
|---|---|---|
| 기존 대화/휴지통/모델/CSV + 신규 높이/scrollbar 통합 | 43개 화면/3215개 검사, 실패0 | [전체 결과](009_AI_Viewport_Scrollbar/screenshots-merged/results.json) |
| 짧은 모바일 팝업320×620/390×844, 두 테마 | 4개 화면/112개 검사, 실패0 | [추가 결과](009_AI_Viewport_Scrollbar/screenshots-short-mobile/results.json) |
| 이번 브라우저 최종 합계 | **47개 화면/3327개 검사, 실패0** | 신규8개/284개는 통합43개에 포함, round3 재실행은 중복 집계하지 않음 |
| Staging Python AST/JavaScript node --check | 통과 | [검증·소스 해시](009_AI_Viewport_Scrollbar/validation.json) |
| 원래 root11개 SHA256 | 모두 baseline 일치 | 운영 소스 미변경 |
| 거버넌스1.8.1 validate | 통과, 오류0/경고0 | manifest44개 |
| backend | 007의178개 통과 증거 승계 | 업무 Python 소스 미변경, 이번 browser-only의 unittest0과 구분 |

통합 fixture digest: `d8b0587d14b246123bb6b50091e3967030b8ae1c9b013fe26536a634dd4e2c0a`. 짧은 모바일 digest: `5901505070693770918d1ffe905b80069f5530e7b00dabdbd2d58c485983762d`. 검토 당시 Staging과 안내는 [검토한 통합 원문 ZIP](009_AI_Viewport_Scrollbar/reviewed-merged-sources.zip)에 보존한다. 후속010 및 [012 운영 반영](012_AI_Staging_Production_Release_Report.md)과 원문 보존 후 정리는 별도 이력이다.

직접 확인한 대표 화면:

- PC1440×900 스크롤: [라이트](009_AI_Viewport_Scrollbar/screenshots-merged/screen-041.png) / [다크](009_AI_Viewport_Scrollbar/screenshots-merged/screen-042.png)
- 모바일390×844 스크롤: [라이트](009_AI_Viewport_Scrollbar/screenshots-merged/screen-037.png) / [다크](009_AI_Viewport_Scrollbar/screenshots-merged/screen-038.png)
- PC CSV 가져오기: [다크](009_AI_Viewport_Scrollbar/screenshots-merged/screen-034.png)
- 짧은 모바일 첨부: [320×620 라이트](009_AI_Viewport_Scrollbar/screenshots-short-mobile/screen-000.png)
- 모바일 CSV 가져오기: [390×844 다크](009_AI_Viewport_Scrollbar/screenshots-short-mobile/screen-003.png)

추가로 발견된 화면 결함은 없다. 스크롤 화면에는 보관 예산 초과 안내/긴 목록/큰 표를 넣었고, sidebar와 표를 일부 스크롤한 상태가 캡처되어 있다. 합성 제목의 `<img src=x>`는 기존 보안 검사용 일반 텍스트이며 HTML 실행이 아니다. 최소 조건에 부족한320×620 첨부 화면은 의도대로 바깥 문서 scrollbar가 남지만 팝업은 viewport 안에 있고 닫기/첨부 버튼이 접근 가능하다.

## 사후 Validation1~8

1. 거버넌스: 계획·Task·보고서와 원문/검증 해시를 연결했다. 사용자 승인 범위의 현재 Staging에만 병합했다.
2. 의도: 최소 충족 시 외부 세로 스크롤 제거와 AI 내부 테마 scrollbar를 측정으로 확인했다. web_search는 검토/구현하지 않았다.
3. 논리: 실제 프레임에서 높이/너비·상단 변경·breakpoint 왕복과 안정화를 검증했다. 가상 시간 실패를 성공으로 숨기지 않고 별도 보존했다.
4. 영향: 대화/모델/추론/초안/내부 위치와 CSV 가져오기/내보내기·첨부, 대화 휴지통 회귀가 통과했다. 공통 프레임/백엔드/DB를 변경하지 않았다.
5. 보안: 권한·CSRF·고정 링크·명시적 등록 확인을 유지했다. 새 외부 연결/도구/디버거 포트는 없다. 운영 계정/모델/DB를 사용하지 않았다.
6. 복구:007 원본과 현재009 원본을 각각 보존하고 파일 해시로 연결했다. root11개 SHA가 모두 유지되어 운영 복귀 조치는 필요하지 않다.
7. 휴먼 에러: 최소 미충족 시 스크롤을 허용하고 팝업 닫기/등록 버튼을 보존했다. resize/테마 변화가 업무 요청을 재전송하지 않는다.
8. 메타: 47개 화면/3327개만 최종 집계하고 round3/기존 backend는 중복 집계하지 않았다. native 실기기 키보드/핀치/다른 브라우저 및 실제 모델 사용 검증은 남아 있다.

재현은 Staging README의 Linux 격리 runner를 사용하며 결과 디렉터리는 매번 새 경로를 지정한다. Git commit/push, 운영 root 병합, 서버 배포 및 운영 DB 변경은 수행하지 않았다.
