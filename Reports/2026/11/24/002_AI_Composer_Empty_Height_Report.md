---
artifact_id: REPORT-20261124-002
work_id: FIX-20261124-AI-COMPOSER-EMPTY-HEIGHT
owner: Claude
status: deployed-and-verified
approval: user-explicit-approval-through-production-deployment
---

# AI 도우미 빈 입력창 높이 복원 검증 보고서

## 1. 원인과 변경

- **원인:** textarea 높이는 `input` 이벤트에서만 계산되는데, 전송 성공 시 코드가 `value = ''`로 비우면 이 이벤트가 발생하지 않아 긴 입력의 인라인 `height`가 남았다.
- **변경:** `fitInputHeight(input)`을 추가해 인라인 높이를 먼저 제거하고 값이 있을 때만 `min(scrollHeight, 160px)`을 적용한다. 사용자 입력, 전송 후 비움, 모바일 줄바꿈 편집 복원에서 호출한다.
- **유지:** 최대 높이 160px, 전송 중 새로 입력한 초안 보존, 거부된 요청의 초안 보존, 서버 API와 DB.

## 2. Validation 1~8단계

| 단계 | 결과 | 근거와 위험 |
| --- | --- | --- |
| 1. 거버넌스 | 통과 | `validate` 오류 0건. 경고 1건은 기존 WebMCP 보완 항목의 stale 상태이며 본 작업 대상과 무관하다. Staging 패치를 먼저 검증했고 외부 의존성 추가는 없다. |
| 2. 사용자 의도 | 통과 | 삭제와 전송 두 경로 모두 빈 입력창이 기본 높이로 돌아온다. 공백만 있는 입력은 사용자가 입력한 내용이므로 비어 있는 상태로 보지 않는다. |
| 3. 논리적 구동 | 통과 | 동기 DOM 갱신이며 반복 호출이나 새 타이머가 없다. 전송 중 다른 초안을 입력하면 `value === raw` 조건이 거짓이므로 초안과 높이를 유지한다. |
| 4. 운영 영향 | 통과 | 프런트엔드 JS 1개와 테스트 1개만 변경한다. 라우트·권한·설정·DB 변경이 없다. 뷰포트 맞춤은 기존 `ResizeObserver`로 재계산된다. |
| 5. 보안·엣지 | 통과 | 사용자 입력을 DOM에 새로 삽입하지 않고 길이만 측정한다. 빈 값 경로는 측정 없이 인라인 높이만 제거한다. |
| 6. 롤백 | 통과 | 데이터 변경이 없어 해당 commit의 `git revert` 후 같은 배포 절차로 복구된다. 이전 JS가 캐시되어도 데이터 호환 문제는 없다. |
| 7. 휴먼 에러 | 통과 | 중복 전송, 거부, IME, 모바일 줄바꿈 경로의 기존 브라우저 검사가 유지된다. 파괴적 UI 동작은 추가되지 않았다. |
| 8. AI 메타 | 통과 | 실제 작업자 Claude, 구현·운영 반영 모드, 사용자 명시 승인 범위를 기록했다. 기존 미커밋 변경은 commit 대상에서 제외한다. 이 파일의 주석은 파일 관행대로 EN만 갱신했고 KO 동기화는 수행하지 않았다. |

## 3. 검증 결과

검증 대상은 `HEAD` 임시 사본에 Staging 패치를 적용한 후보이며, 실제 모델 호출과 운영 DB 접근 없이 `eqmgmt-backup`의 Linux tmpfs와 Chromium에서 실행했다.

| 검증 | 결과 |
| --- | --- |
| 입력 설정 브라우저(`input-preferences`) | 18/18 통과, 866개 확인 |
| 전송 버튼 hitbox | 14/14 통과, 1,358개 확인 |
| Fold7 커버 화면 | 8/8 통과, 736개 확인 |
| viewport | 8/8 통과, 284개 확인 |
| 모델 패널(`disclosure`) | 8/8 통과, 168개 확인 |
| 전체 백엔드 | 356/356 통과, `production_database_opened: false` |
| 정적 보안·구문 검사 | 통과 |
| 회귀 검출: 수정 전 JS | 새 검사 `uncancelable-empty-edit-restores-default-height` 실패 |
| 회귀 검출: 전송 후 복원만 제거 | 새 검사 `sent-long-draft-restores-default-composer-height` 실패 |

## 4. 병합 산출물

Staging 후보와 운영 소스는 LF 정규화 기준으로 일치한다. 본 작업 Staging 폴더는 병합 후 삭제했다.

| 파일 | LF 바이트 | LF SHA-256 |
| --- | ---: | --- |
| `static/js/equipment_ai.js` | 167,452 | `8f18a0f660d2ab2c5ff6ceac002680d963646b2ce2f232fe46210d14d0d8cc19` |
| `tests/test_ai_input_preferences.js` | 29,774 | `2c67b012e176bcffb7977e3ed4e53576196aa568cfafce8c18686df83473dbc1` |

## 5. 배포 결과

- **코드 릴리스:** `8491b796afd93410765203f45666256fbe596a2c` (`origin/main` push 완료, 본 작업 5개 파일 한정).
- **반영 서버:** `eqmgmt-backup`. 작업 시점에 미니서버(`192.168.0.166:5000`)는 접속되지 않았고 SSH 설정도 없어 반영하지 않았다.
- **배포 절차:** `tools/deploy_ai_ux_release.py`의 `pause → git pull --ff-only → check-copy → activate`를 수행했다. 사전 활성 작업은 0건이었다.
- **사본 기동 시험:** 통과. 업무 테이블 18개와 AI 테이블 21개의 기존 행과 감사 행을 보존했고, 실제 모델 호출과 운영 DB 변경은 없었다.
- **활성화:** `2026-11-24 11:24:51 KST`, 웹 `PID 3067221`, 워커 `active`.

라이브 비파괴 검증(`2026-11-24 11:25 KST`):

| 항목 | 결과 |
| --- | --- |
| 서버 `HEAD`와 추적 파일 | `8491b79`, 변경 없음 |
| 유지보수 상태 | `NORMAL` |
| 워커·보존 타이머 | 모두 `active` |
| 시작 로그 Traceback | 0건 |
| HTTP | `/login` 200, `/assistant` 302, `/api/ai/capabilities` 401 |
| 제공 중인 `equipment_ai.js` | 4절 SHA-256과 일치, `Cache-Control: no-cache` |
| SQLite `integrity_check` | `equipment.db`, `assistant.sqlite3` 모두 `ok` |

**확인 한계:** 실제 계정으로 로그인해 라이브 화면을 조작하지는 않았다. 동작은 동일 해시의 JS를 격리 Chromium에서 검증했다. 배포 전에 열어 둔 탭은 새로고침해야 새 JS가 적용된다.
