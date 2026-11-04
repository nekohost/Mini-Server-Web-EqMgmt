---
artifact_id: REPORT-20261104-010
work_id: REVIEW-20261104-AI-STAGING-SCREENS
owner: Codex
created_at: 2026-11-04
status: completed-with-findings
---

# 신규 AI 화면 샘플 스크린샷 검토

## 사전 Validation (순차)

1. **거버넌스:** recorder 정상, profile legacy/runtime-session-mismatch, governance 1.8.1/44 nodes/0 errors·warnings와 현재 context pack을 적용했다. 기존 후보는 read-only reference이며 캡처 fixture와 산출물만 신규 생성한다.
2. **의도:** 사용자 요청은 실제 Staging 화면 캡처·기록·문제 보고다. 기능 개발/운영 배포/테마 수정으로 확대하지 않는다. 두 신규 화면과 주요 상태의 desktop/mobile 샘플을 남긴다.
3. **구동/예외:** 기존 source-driven Linux 캡처와 동일하게 후보 템플릿/스크립트/스타일·공통 frame을 고정한다. API만 synthetic이며 모델/DB 미사용. 캡처 준비 완료 조건·DOM 오류·스크롤/가로 넘침을 기록한다.
4. **운영 영향:** Windows 앱 기동, 운영 app import·DB open·서비스 변경은 없다. 후보의 009 source/기존 보고서/manifest도 보존한다. 기존 파일 덮어쓰기 없이 별도 출력 폴더를 사용한다.
5. **보안:** 샘플 이름/장비/주소는 합성 값이며 실제 key·사용자 cookie를 넣지 않는다. browser 통신은 임시 loopback으로 제한한다. 원본 화면에 실사용자의 민감 데이터가 들어가지 않는다.
6. **복구:** 신규 fixture/생성 PNG·문서만 식별 가능한 경로로 추가한다. 기존 후보/기록을 삭제하거나 덮어쓰지 않는다. 캡처용 Linux profile·임시 서버/파일은 종료/정리한다.
7. **UX:** 추론/최종 답변/확인 카드/프로바이더·모델/중단 이유, theme/좁은 화면/스크롤/가독성/버튼 활성 상태를 검토한다. 문제가 보이면 증거와 사유를 남기며 정상으로 바꾸어 보고하지 않는다.
8. **메타:** 실제 브라우저 pixels와 샘플 조건을 구분한다. 이번 이미지는 실모델 생성·성능·권한 검사 통과의 증거가 아니다. 과거 009의 106/83 결과를 새 화면 검토 결과로 재사용하지 않는다.

## 캡처 및 검토 결과

현재 후보 소스에서 **기본 16장과 확인 카드 상세 2장, 총 18장**을 캡처하고 모두 시각 검토했다. **화면 결함 2건과 가독성 개선 권고 1건**을 발견했다. 기존 후보나 운영 화면은 수정하지 않았다. 검토 완료는 화면 결함이 해결되었다는 의미가 아니다.

- [18장 스크린샷 갤러리](010_AI_Staging_Screens/index.html)
- [실행별 조건·원문 소스 SHA·PNG SHA·DOM 측정 원장](010_AI_Staging_Screens/manifest.json)
- [캡처 도구](../../../../Staging/20261104-user-ai-screens/capture.py)

### 캡처 조건과 해석

009 후보의 실제 Jinja·JavaScript·CSS와 현재 로컬 공통 frame/static을 pack해 승인된 Linux `eqmgmt-backup`의 임시 loopback Flask/Chromium에서 렌더링했다. 화면 레이아웃이나 색을 보정하는 CSS를 추가하지 않았다. 외부 CDN 대신 기존 로컬 Tailwind fallback을 사용했고 외부 통신은 제한했다. Windows에서는 소스 pack과 신규 PNG 저장만 수행했다.

API 데이터는 읽기 전용 합성 응답이다. 샘플 계정·장비·프로바이더와 예약된 예시 주소를 사용했으며 실제 키, 사용자 대화, 운영 DB, 실모델을 사용하지 않았다. 실행/저장/삭제 버튼은 누르지 않았고 fixture의 POST는 차단했다. 따라서 이 자료는 화면 상태의 실제 픽셀을 검토하는 근거이며, 실제 모델 응답 품질·스트리밍 시간·권한 검사·업무 처리 성공을 검증한 결과가 아니다.

데스크톱의 실제 내부 viewport는 **1440×1000**, 모바일은 **390×844**다. Chromium CLI의 바깥 창 치수와 내부 높이 차이가 스크롤 캡처를 왜곡하지 않도록 두 크기 모두 명시적인 same-origin iframe으로 고정하고 DOM 측정치와 일치시켰다. 모바일 PNG 자체는 **500×844**이며 좌우 55px 회색 여백은 캡처 틀이다. 모바일 앱 화면을 500px로 확장해 찍은 것이 아니다.

### 장면별 검토

각 기본 장면을 desktop/mobile 두 장으로 남겼다. 표의 링크를 열면 원본 PNG를 볼 수 있다.

| 장면 | 테마 | 데스크톱 / 모바일 | 관찰 결과 |
| --- | --- | --- | --- |
| 새 대화·기본 제안 | 라이트 | [D](010_AI_Staging_Screens/final/01-user-welcome-desktop.png) / [M](010_AI_Staging_Screens/final/01-user-welcome-mobile.png) | 모델 선택·새 대화·업무 제안·입력 영역 표시. 모바일 제안은 한 열로 배치되고 내부 스크롤로 이어짐. 하단 안내문은 UI-I01 참고. |
| 추론 진행 | 다크 | [D](010_AI_Staging_Screens/final/02-user-thinking-desktop.png) / [M](010_AI_Staging_Screens/final/02-user-thinking-mobile.png) | 추론 영역이 열린 상태, 진행 안내·요청 취소·전송 비활성 표시. 출처의 영문 추론 값은 UI-02. 실시간 생성이나 취소 동작을 실행한 시험은 아님. |
| 최종 답변·등록 확인 | 라이트 | [D](010_AI_Staging_Screens/final/03-user-review-desktop.png) / [M](010_AI_Staging_Screens/final/03-user-review-mobile.png) | 최종 답변과 접힌 추론 영역 표시. 확인 카드가 메시지 뒤에 이어지므로 전체 내용·버튼은 추가 상세 캡처로 확인. |
| 같은 대화의 모델 변경 | 다크 | [D](010_AI_Staging_Screens/final/04-user-model-switch-desktop.png) / [M](010_AI_Staging_Screens/final/04-user-model-switch-mobile.png) | 현재 선택은 대화 전용 4B, 기존 답변의 출처는 Strata PC A로 각각 표시. 추론 설정 미지원 안내와 비활성 선택 표시. |
| 연결 중단·종료 확인·보관량 | 라이트 | [D](010_AI_Staging_Screens/final/05-user-recovery-desktop.png) / [M](010_AI_Staging_Screens/final/05-user-recovery-mobile.png) | 중단 사유·관리자 문의 안내·전송 비활성 및 추가 보관 예산 안내 표시. 모바일에서는 안내가 줄바꿈되며 가로 넘침 없음. |
| 관리자 신규 연결 | 라이트 | [D](010_AI_Staging_Screens/final/06-admin-new-desktop.png) / [M](010_AI_Staging_Screens/final/06-admin-new-mobile.png) | desktop 2열, mobile 1열 폼. 연결 종류·자원 그룹·선택형 수동 등록 항목 표시. 긴 모바일 폼은 세로 스크롤로 이어짐. |
| 관리자 기존 연결 | 라이트 | [D](010_AI_Staging_Screens/final/07-admin-provider-desktop.png) / [M](010_AI_Staging_Screens/final/07-admin-provider-mobile.png) | 선택된 연결 구분, 기존 키 원문 대신 보관 상태 placeholder, 설정 revision·저장/폐기 버튼 표시. |
| 관리자 공개 모델·기능 설정 | 다크 | [D](010_AI_Staging_Screens/final/08-admin-models-dark-desktop.png) / [M](010_AI_Staging_Screens/final/08-admin-models-dark-mobile.png) | 모델 이름·항목명·보조 문구의 대비 부족을 두 크기에서 확인. UI-01. |
| 확인 카드 상세 (추가) | 라이트 | [D](010_AI_Staging_Screens/confirmation-full/03-user-review-desktop.png) / [M](010_AI_Staging_Screens/confirmation-full/03-user-review-mobile.png) | 등록 값·선택 옵션 설명·실행 버튼을 하단 스크롤에서 확인. 실행 버튼이 두 크기에서 보이고 활성 상태. 실제 실행은 하지 않음. |

### 발견 사항과 권고

| ID / 판단 | 재현·증거 | 원인·사용자 영향 | 조치 권고 |
| --- | --- | --- | --- |
| **UI-01 / P2 결함** | 관리자 다크 모드의 공개 모델 화면. 위 08번 desktop/mobile PNG. 제목·label 실제 글자색 `#253044`, 배경 `#0f172a`, 계산 대비 **1.347:1**. | `equipment_ai_providers.css:7~8`이 현재 공통 frame에 정의되지 않은 `--text-primary`·`--text-secondary`의 밝은 테마 fallback을 사용하며 dark 대체가 없다. 제목·입력 항목명을 읽기 어렵다. 보조 설명 `#596579`도 같은 배경에서 대비 3.028:1이다. 흰 입력란의 값은 보이지만 무엇을 설정하는 필드인지 구분하기 어렵다. | 실제 공통 테마 값에 연결하거나 관리자 화면 범위의 dark 팔레트를 정의한다. 제목·label·설명·폼/카드·버튼을 함께 대조하고 같은 두 viewport로 다시 캡처한다. **이번 검토에서는 미수정.** |
| **UI-02 / P3 결함** | 02번 추론 화면과 04번 모델 변경 화면의 메시지 아래 `· medium` 표시. | `equipment_ai.js:151`의 `sourceLabel()`이 `reasoning_effort`를 그대로 표시한다. 선택 메뉴의 “중간 추론”과 표기가 달라 일반 사용자용 한글 명칭 기준에 맞지 않는다. | 표시 단계에서 한글 label을 매핑한다. API 원래 값과 과거 답변의 provider/model 스냅샷은 유지한다. **이번 검토에서는 미수정.** |
| **UI-I01 / 가독성 개선 권고** | 01번 모바일 하단의 등록·수정 확인 및 삭제·관리자 업무 범위 안내. DOM 계산 크기 **8px**. | `equipment_ai.css:101`의 모바일 규칙으로 작은 안내문이 된다. 가로 넘침·조작 불가 결함으로 분류하지는 않지만 실제 이미지에서 읽기가 작고 부담스럽다. | 안내 글자 크기를 키우고 대화·입력 영역 및 세로 스크롤을 함께 재검토한다. **접근성 전체 적합성 판정은 아님.** |

관리자 다크 모드 문제와 출처의 영문 값 노출은 검토 중 사용자에게 먼저 알렸다. 권한·감사 로그·모델 기능 같은 기존 구현을 이번 시각 검토만으로 정상 또는 실패로 다시 판정하지 않았다.

### 샘플·중간 산출물 구분

기본 16장은 `final/`, 확인 카드 상세 2장은 `confirmation-full/`에 있다. 상세 장면에서는 합성 데이터에 `_selected_option`의 사람이 읽는 모델/옵션명을 포함하고 카드 아래까지 스크롤했다. 실제 후보의 `proposalCard()`는 이 설명을 이미 표시한다. 초기 합성 샘플이 옵션 번호만 제공했던 현상을 제품 결함으로 기록하지 않았다. 두 실행의 캡처 스크립트·샘플·검사 스크립트 SHA는 manifest에 각각 보존했다. 기본 03번의 상단 맥락을 재현하려면 `inspect_sample.js`의 proposal scroll을 0으로 하고 샘플 `before_json`을 빈 객체로 두면 된다. 그 외 기본 상태는 동일하다.

중간 결과는 지우지 않고 갤러리에서 제외했다. `capture-diagnostic/`의 두 HTTP 500 화면은 최초 fixture static route의 인수 이름 오류이며 제품 문제가 아니다. `samples/`의 16장은 desktop CLI 스크롤 치수 불일치가 있어 최종 고정 viewport 16장으로 대체했다. `confirmation-details/`의 2장은 전체 구조화 metadata를 보존한 `confirmation-full/`로 대체했다. 이 20장은 검토 대상 18장 수치에 포함하지 않는다.

최종 캡처는 아래 명령으로 신규 출력 디렉터리에 재현한다. 기존 경로가 존재하면 덮어쓰기를 거부한다. 현재 도구의 03번 기본 동작은 상세 카드 하단 스크롤과 옵션 설명을 포함한다.

```text
python Staging/20261104-user-ai-screens/capture.py --output Reports/2026/11/04/010_AI_Staging_Screens/<new-run-directory>
python Staging/20261104-user-ai-screens/capture.py --scene 03-user-review --output Reports/2026/11/04/010_AI_Staging_Screens/<new-detail-directory>
```

## 후속 Validation (순차)

1. **거버넌스:** 기존 recorder/context와 legacy `runtime-session-mismatch` 경로를 유지했다. governance 1.8.1/44 nodes의 검사 결과 errors·warnings 0. Task/Plan/사전 1~8 후에 캡처했고 문서·fixture는 구조화 patch로 작성했다. PNG는 생성 도구가 신규 경로에만 저장했다.
2. **의도:** 신규 사용자 AI 화면과 관리자 연결 관리 화면의 8개 상태를 desktop/mobile로 캡처하고 확인 카드 상세 2장을 추가했다. 18장 갤러리·측정 원장·문제 보고를 남겼다. 화면 수정·운영 반영으로 범위를 확대하지 않았다.
3. **논리/예외:** 18장 모두 실제 후보 초기화 완료, Chromium exit 0, 수집한 JS 예외 0. 문서 가로 넘침은 0이다. desktop/mobile viewport가 1440×1000/390×844로 측정됐으며 상세 카드의 실행 버튼은 두 크기에서 viewport 안에 있다. 캡처 준비 실패나 빈 결과를 정상 화면으로 대체하지 않았다.
4. **운영 영향:** 운영 app import·운영 DB open·실모델 호출은 모두 false. 현재 후보/guide 25개, 공통 frame/static 11개, 보호된 기존 기록 6개가 009 원장의 SHA와 일치한다. 운영 `app.py` SHA는 `6244893711252F6C78BF36C53CC010BBB485E22C773EBFF038D8F7D3EEE8A581`로 동일하다. Git commit/push·배포·서비스 변경은 없다.
5. **보안/경계:** 합성 계정/장비/주소만 사용하고 실키·cookie·대화를 읽지 않았다. read-only fetch fixture와 loopback·외부 통신 제한을 사용했다. 관리자 화면에 원문 키가 없고 샘플에는 보관 상태만 있다. 실제 인증·권한·SSRF·도구 호출의 재검증으로 확대 해석하지 않는다.
6. **복구/보존:** 기존 PNG와 진단 결과를 덮어쓰거나 지우지 않았다. gallery/manifest는 최종 18장과 중간 결과를 구분한다. 임시 Flask 서버는 finally에서 종료하고 각 Chromium 임시 profile·파일은 TemporaryDirectory로 정리했다. 기존 후보·평가·manifest를 보존했다.
7. **UX:** 18개 PNG를 모두 직접 시각 검토했다. 추론 열림/최종 답변의 접힘 상태·모델 선택과 과거 출처·오류 사유·확인 카드·관리자 반응형 폼을 확인했다. UI-01/P2와 UI-02/P3은 실제 화면 결함이며 UI-I01은 별도 개선 권고다. 저대비 문제를 통과로 숨기지 않고 미수정 상태로 보고했다.
8. **메타/근거:** PNG signature·크기·SHA, 18개 gallery 참조, 캡처 소스와 제품 소스 보존을 별도 대조 완료했다(2026-11-04 20:31:54 KST, 오류 0). `capture.py`와 내장 remote code의 AST parse, 두 JS의 `node --check`를 수행했다. 과거 009의 106 backend/83 browser 결과는 이번 실행 결과로 재사용하지 않았다. 모바일 실기기·키보드·확대·스크린리더·다른 브라우저 및 모든 테마 조합은 미검증이다.

## 완료 판정

요청한 화면 샘플과 검토 기록을 남겼다. 관리자 다크 모드 결함의 수정이 우선이며 출처의 추론 명칭을 함께 정리할 수 있다. 발견한 세 항목은 모두 **미수정** 상태로 유지한다. 최종 파일 무결성 대조 결과는 `010_AI_Staging_Screens/verification.json`에 보존한다.
