---
artifact_id: REPORT-20261109-002
work_id: STAGING-20261109-EQUIPMENT-TOOLBAR
owner: Codex
status: completed
---

# 장비 도구줄 개선 검증

구현 전 Validation 1–8:

1. Recorder ensure 성공·watcher 11268 유지. profile은 legacy/runtime-session-mismatch이며 임의 모델 선언으로 우회하지 않았다. 정책 1.8.1의 44개 노드 오류 0, 이번 context 25개는 앞선 작업에서 읽은 동일 노드의 부분집합이며 필수 입력은 0. 기존 변경과 운영 소스를 보존한다.
2. 요구는 넓은 PC의 기본 도구줄 한 줄, 가용 폭에 따른 자동 줄바꿈, 동일한 컨트롤 크기와 기능 확장성이다. 현재 승인 범위인 Staging 및 검증까지 수행한다.
3. 기존 JS는 roadmap-filter.elements에서 검색 값을 읽고 다른 버튼은 ID로 연결한다. 검색 form을 바깥으로 확장하되 입력 소유와 type=button 계약을 유지한다. 모달의 별도 form은 바깥 형제이므로 중첩 form을 만들지 않는다.
4. 기본 CSS는 장비 도구줄에만 범위를 둔다. 상단 바와 다른 메뉴, AI 전용 높이 계산을 변경하지 않는다. 운영 JS·API·권한·DB의 변경은 없다.
5. 숨긴 상세 검색은 hidden/disabled 의미를 유지하고 일반 검색에서 사용하지 않는 필터가 섞이지 않도록 기존 동작을 검증한다. 검색 외 버튼의 자동 submit, 중복 이벤트, 긴 건수와 추가 버튼의 화면 넘침을 확인한다.
6. 원문 SHA와 Git 기준선을 기록하며 모든 후보는 Staging에 둔다. 원본 변경 없이 후보 제거로 되돌릴 수 있고 검증 원문은 보고서와 함께 보존한다.
7. DOM/시각/탭 순서를 맞추고 버튼의 글자를 잘라 감추지 않는다. 좁은 화면에서 기능 묶음과 입력 최소 폭을 유지한다. 오류 안내는 빈 상태에도 살아 있는 aria-live 영역으로 둔다.
8. Windows에서 Flask를 기동하지 않는다. 기존 Linux 루프백 합성 브라우저를 사용하고 실제 계정/장비 저장·모델 호출·서비스 제어는 수행하지 않는다. 화면·동작 판정과 검증 한계를 함께 기록한다.

구현 후 Validation 1–8:

1. 후보는 `Staging/20261109-equipment-toolbar/`의 6개 파일이다. 본문 부품·CSS 2개와 검증/기존 검사 적응 4개로 구성한다. 운영 소스와 Git HEAD `16c34d902cebc87422a01359864a9ffef49f7e46`은 유지한다.
2. 같은 DOM을 자동 줄바꿈시키며 등록/임시저장/CSV→검색→페이지 순으로 배치했다. 기본 도구줄은 동일 높이 44px·글꼴 13px이고 검색 입력은 남는 폭을 사용한다. 화면 폭만으로 기기 종류를 추측하거나 특정 버튼 개수를 고정하지 않는다.
3. [정적 검사](002_Equipment_Toolbar/stage-static-final.json)는 기존 회귀 25개 통과, opt-in 1개는 별도 Linux 실제 브라우저로 대체했다. JS 문법 및 Python AST 검사도 통과했다. [구조 대조](002_Equipment_Toolbar/structure-verification.json)에서 ID 30개와 원래 이벤트/type/name/ARIA 등 52개 속성을 보존했고 기존 모달 원문이 동일함을 확인했다.
4. 검색 form의 소유 범위를 조정했지만 모든 검색 필드는 같은 form.elements에 남는다. 검색만 submit이고 그 외 도구는 type=button이다. 실제 브라우저의 기본 제출 대상도 검색임을 확인했다. 상세 검색 fieldset·CSV 패널은 도구줄 아래 전체 폭을 사용하며 JS·API·권한·DB는 변경하지 않는다.
5. [최종 26개 화면·663개 판정](002_Equipment_Toolbar/verification.json)이 통과했다. 검색·이전/다음·일반/조건 검색 전환과 숨김 필터 제외, CSV 접힘의 무제출·가져오기 창, 등록/수정 창, 임시저장 왕복, 빈 결과·조회 오류 후 재시도를 확인했다. 공개 장비의 포함 범위 체크박스는 검색 form 밖에서 기존 이벤트를 유지한다.
6. [검토 원문 ZIP](002_Equipment_Toolbar/reviewed-source.zip)과 [SHA 목록](002_Equipment_Toolbar/source-manifest.json)에 후보 6개를 보존했다. 운영 참조 8개 SHA가 기준선과 같고 변경 사항은 Staging 및 계획/작업/보고서에 한정된다. 운영 배포는 이번 작업 범위에 포함하지 않았다.
7. PC/모바일·라이트/Standard·다크/Edge에서 스크린샷을 직접 검토했다. 추가 기능 예시 버튼을 주입했을 때 기존 컨트롤을 숨기거나 밀어내지 않고 모바일에서 네 번째 줄을 사용한다. 긴 건수도 잘리지 않으며 기본 320/384/412px는 3줄, 820px는 2줄, 1440px는 1줄이다. 기본·조건검색·CSV·긴 수량·확장 예시·편집·빈 결과·오류 화면에서 페이지 전체 가로 넘침이나 버튼 겹침을 발견하지 않았다.
8. 1440px 화면에서 1280→1024→820→640→412→384→320→1440으로 실제 iframe 폭을 연속 변경했다. 두 테마 모두 검색어·숨겨 둔 상세 조건·범위를 유지하고 장비 조회를 추가하지 않았다. 1024/1280px도 1줄, 640/820px는 2줄이었다. 모바일은 CSS 뷰포트 검증이며 실기기/물리 키보드 검증은 아니다. 데이터는 합성 대표 장비·페이지 수로 실제 보유량이 아니다.

기존 제각각의 패딩/높이 때문에 같은 시각적 행에도 컨트롤의 y 좌표가 달랐다. 비교 행 수는 단순 y 좌표 개수 대신 세로 영역이 겹치는지를 기준으로 산정했다. 기본 상태에서의 실측은 다음과 같다. 펼침 패널과 실제 오류 안내가 나타나면 필요한 공간을 추가로 사용한다.

| CSS 화면 폭 | 개선 전 시각적 행 | 개선 후 시각적 행 | 도구 영역 높이 전→후 | 비교 이미지 |
|---|---:|---:|---:|---|
| 1440px | 2 | 1 | 132.16px → 44px | [전](002_Equipment_Toolbar/baseline-final/my-1440-light.png) / [후](002_Equipment_Toolbar/rows-final/my-1440-light.png) |
| 820px | 3 | 2 | 182.16px → 96px | [전](002_Equipment_Toolbar/baseline-final/my-820-light.png) / [후](002_Equipment_Toolbar/rows-final/my-820-light.png) |
| 384px | 5 | 3 | 278.55px → 148px | [전](002_Equipment_Toolbar/baseline-final/my-384-light.png) / [후](002_Equipment_Toolbar/form-final/my-384-light.png) |

| 검증 화면 | PC | 모바일 |
|---|---|---|
| 기본 도구줄 | [다크 한 줄](002_Equipment_Toolbar/rows-final/my-1440-dark.png) | [384px 세 줄](002_Equipment_Toolbar/form-final/my-384-light.png) / [320px](002_Equipment_Toolbar/matrix/my-320-dark.png) |
| 공개 장비 | [기본 도구줄](002_Equipment_Toolbar/matrix/public-1440-dark.png) | [포함 범위 체크박스](002_Equipment_Toolbar/matrix/public-384-light.png) |
| 임시저장함 | [등록 버튼 숨김](002_Equipment_Toolbar/matrix/draft-1440-dark.png) | [목록 복귀](002_Equipment_Toolbar/matrix/draft-384-light.png) |
| 조건검색·CSV | [전체 폭 조건검색](002_Equipment_Toolbar/matrix/advanced-1440-dark.png) | [조건검색](002_Equipment_Toolbar/matrix/advanced-384-light.png) / [CSV](002_Equipment_Toolbar/matrix/csv-384-light.png) |
| 확장과 예외 | [추가 기능 예시](002_Equipment_Toolbar/matrix/future-1440-dark.png) | [추가 버튼](002_Equipment_Toolbar/matrix/future-384-light.png) / [긴 건수](002_Equipment_Toolbar/matrix/long-384-light.png) / [오류](002_Equipment_Toolbar/form-final/error-384-light.png) |
| 기존 수정 창 | [PC](002_Equipment_Toolbar/matrix/edit-1440-dark.png) | [모바일](002_Equipment_Toolbar/matrix/edit-384-light.png) |

납품 상태는 Staging 검증 완료다. 기존 코드와 제어권을 보존하며 운영 소스 병합·서비스 재시작·실제 데이터 저장은 수행하지 않았다.
