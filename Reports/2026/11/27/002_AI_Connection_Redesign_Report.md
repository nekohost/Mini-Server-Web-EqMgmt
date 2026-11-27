---
artifact_id: REPORT-20261127-002
work_id: FEAT-20261127-AI-CONNECTION-REDESIGN
owner: Claude
status: deployed-and-verified
approval: user-explicit-deployment-2026-11-27
---

# AI 연결 관리 화면·모델 목록 구조 개편 보고서

## 1. 배경과 확인한 원인

| 구분 | 사용자 지적 | 확인한 원인 |
| --- | --- | --- |
| 미서빙 모델 노출 | 서빙되지 않는 모델이 저장돼 있다는 이유로 목록에 보임 | `discover()`는 행을 삭제하지 않고 `present`만 `0`으로 내리지만, `choices()`는 `published=1`이면 `present`와 무관하게 사용자 목록에 포함했고 `admin_list()`도 전체 행을 단일 목록으로 반환함. |
| 연결 이름 미반영 | 연결 이름을 바꿔 저장해도 사용자 선택 카드에 반영되지 않음 | `save()`가 이름만 바꿔도 주소 변경과 같은 경로(새 연결 버전 + 후보 생성)를 탔고, 활성 이름은 모든 공개 모델의 워커 기능 시험 통과 후 자동 전환 때에만 갱신됨. 운영 DB 확인 결과 활성 이름은 `'260Strata'`(버전 6), 사용자가 저장한 `'STC'`는 후보 버전 8에서 '기존 공개 모델의 기능 시험 대기'로 정지 상태였으며 후보 취소 수단이 없었음. |
| 관리 화면·용어 혼선 | '후보'가 무엇인지 알기 어렵고 화면 자체가 보기 어려움 | 내부 개념(`ai_provider_candidates`)이 진행 단계·변경 비교·취소 수단 없이 그대로 노출됨. |

## 2. 변경 내용

| 구분 | 기존 → 변경 |
| --- | --- |
| 사용자 모델 목록 | `published=1`이면 `present`와 무관하게 표시 → `present=0`(현재 목록에 없는) 모델 제외. 이미 해당 모델을 선택한 대화는 `'이 대화의 이전 모델 · 현재 제공되지 않음'`(비활성)으로 표시. |
| 사용자 화면 | '사용할 수 없는 모델 안내'가 선택 패널 밖에 표시 → AI 모델 선택 패널 안으로 이동해 패널을 열었을 때만 표시(사용자 스크린샷 검토 후 요청 반영). |
| 표시 정보 즉시 저장 | 이름 변경도 새 연결 버전·후보 경로를 타고 자동 전환 시 이름을 덮어씀 → 이름·공개 순서·수동 등록 허용은 새 버전 없이 즉시 반영(`POST /api/admin/ai/providers/<pid>/display`, 일반 저장도 경로 변경이 없으면 즉시 처리, 응답 `applied: immediate \| pending_change`). 자동 전환은 이름을 덮어쓰지 않음. |
| 경로 변경 | 내부 명칭 '후보'로 진행 단계·비교 없이 표시 → 주소·종류·자원 그룹·키·인증서·신규 요청 허용 변경은 기존처럼 새 버전 + 기능 시험 후 자동 적용. 화면 명칭을 `'후보'` → `'변경 적용 대기'`로 변경하고 4단계 진행 표시, 변경 전/후 표, 남은 시험 모델 목록 제공. |
| 변경 적용 취소 | 취소 수단 없음 → `POST /api/admin/ai/providers/<pid>/pending/cancel` 추가(진행 중인 기능 시험이 있으면 거부, 한 번도 적용되지 않은 새 연결은 폐기). |
| 관리 화면 | 단일 목록 중심 구성 → 연결 목록 상태 칩, `개요` / `연결 설정` / `서빙 모델` 탭, 모델 요약 행 + 펼침 편집, 신뢰 철회는 접힌 `'고급'` 영역으로 정리. |
| 저장된 모델 기록 하위 화면 | 별도 화면 없음 → `/admin/ai/models/archive`, `GET /api/admin/ai/models/archive` 추가(관리자 전용, 주소·키 미반환, 삭제 기능 없음, 공개 해제만 지원). |
| DB 스키마 | 기존 테이블 유지 → 스키마 변경 없음(기존 `present`·`checked`·후보 테이블 사용). |

## 3. 독립 검토

`agy gemini-4-hydrogen-high` 읽기 전용 검토 결과 보안 취약점과 접수 요청 `route_snapshot` 불변성 회귀는 없었다. 정확성 지적 5건을 모두 반영하고 회귀 테스트를 추가했다.

1. 새 연결의 수동 허용·순서 유실
2. 진행 표시 '통과' 판정이 실제 전환 조건보다 느슨함
3. 기록 화면 공개 해제의 `profile_revision` 미확인
4. 신뢰 철회 차이 누락과 단정적 안내 문구
5. 새 연결 저장 후 탭 처리

## 4. 검증 결과

모든 격리 검증은 `eqmgmt-backup` Linux `tmpfs` + Chromium 환경에서 수행했으며 운영 DB·실모델·Strata는 사용하지 않았다.

| 검증 항목 | 결과 | 비고 |
| --- | --- | --- |
| 백엔드 전체 | 366/366 통과 | 신규 `test_ai_connection_redesign` 7개 포함 |
| 기존 테스트 계약 변경 | 1건 의도적 변경 | `'이름은 전환 전까지 바뀌지 않는다'` → `'이름은 즉시 바뀌고 접수된 요청의 경로·키·스냅샷은 유지'` |
| 연결 개편 화면 fixture | 16/16 통과 | 48개 확인, 데스크톱 1440px·Fold7 커버 384px |
| 대화 UI | 20/20 통과 | 3,238개 확인 |
| 모델 패널 | 8/8 통과 | 168개 확인 |
| Fold7 | 8/8 통과 | 736개 확인 |
| 전송 hitbox | 14/14 통과 | 1,358개 확인 |
| viewport | 8/8 통과 | 284개 확인 |
| 입력 설정 | 18/18 통과 | 866개 확인 |
| 출력 자동 스크롤 | 12/12 통과 | 148개 확인 |
| 정적 보안·구문 검사 | 통과 | — |
| 기존 관리 화면 fixture (`admin_providers_browser_fixture`) | 0/4 미완료 | 수정 전 `origin/main`에서도 동일하게 0/4인 기존 문제로 이번 범위 밖(셀렉터만 새 구조에 맞춤) |

## 5. 스크린샷

- 경로: `Reports/2026/11/27/001_AI_Connection_Redesign_Staging_Screens/`
- 가상 데이터는 RFC 5737 문서용 주소와 가짜 키만 사용했다.

| 순서 | 화면 | 데스크톱 | 모바일 |
| --- | --- | --- | --- |
| 1 | 개요(주소 변경 대기) | `screen-000` | `screen-008` |
| 2 | 개요(이전 방식 이름만 변경 대기) | `screen-001` | `screen-009` |
| 3 | 연결 설정 | `screen-002` | `screen-010` |
| 4 | 서빙 모델 | `screen-003` | `screen-011` |
| 5 | 연결 추가 | `screen-004` | `screen-012` |
| 6 | 저장된 모델 기록 | `screen-005` | `screen-013` |
| 7 | 사용자 모델 선택 | `screen-006` | `screen-014` |
| 8 | 이름 즉시 반영 결과 | `screen-007` | `screen-015` |

## 6. 롤백과 남은 일

- **롤백:** DB 스키마 변경이 없으므로 해당 커밋을 `git revert`한 뒤 동일한 배포 절차(`tools/deploy_ai_ux_release.py`)로 복구한다.
- **운영 대기 후보 정리:** 운영에 멈춘 `'STC'` 후보(버전 8)는 자동으로 정리하지 않는다. 관리자가 새 화면에서 이름을 즉시 저장하고 필요 없으면 `'변경 취소'`로 정리한다.
- **후속 과제:** 기존 관리 화면 fixture(`admin_providers_browser_fixture`) 복구는 별도 과제로 진행한다.

## 7. 배포 결과

- **코드 릴리스:** `c82354880be45dc09f9df597b2bcf72c38ff35ce`(`origin/main` push 완료, 본 작업 33개 파일로 한정: 소스·템플릿 11개, 테스트 5개, 스크린샷 16장과 `results.json`)
- **작업 방식:** 격리 worktree(`staging/ai-connection-redesign`)에서 구현·검증한 뒤 같은 커밋으로 `main`을 fast-forward했다. `main` 작업 트리의 다른 세션 미커밋 변경과 겹치는 파일은 없었다.
- **반영 서버:** `eqmgmt-backup`
- **배포 절차:** `tools/deploy_ai_ux_release.py`로 `pause → git pull --ff-only → JS 3개 SHA-256 대조 → check-copy → activate`를 수행했다. 사전 활성 작업은 0건이었다.
- **사본 기동 시험:** 통과. 업무 테이블 18개와 AI 테이블 21개의 기존 행과 감사 행을 보존했고, 실제 모델 호출과 운영 DB 변경은 없었다.
- **활성화:** `2026-11-27 11:26:23 KST`, 웹 `PID 3448404`, 워커 `active`

라이브 비파괴 검증(`2026-11-27 11:27 KST`):

| 항목 | 결과 |
| --- | --- |
| 서버 `HEAD`와 추적 파일 | `c823548`, 변경 없음 |
| 유지보수 상태 | `NORMAL` |
| 워커·보존 타이머 | 모두 `active` |
| 시작 로그 Traceback | 0건 |
| HTTP(비로그인) | `/login` 200, `/assistant` 302, `/admin/ai/providers` 302, `/admin/ai/models/archive` 302, `/api/ai/capabilities` 401, `/api/admin/ai/models/archive` 401 |
| 제공 중인 JS | `equipment_ai.js`, `equipment_ai_providers.js`, `equipment_ai_model_archive.js` 모두 커밋 SHA-256과 일치, `Cache-Control: no-cache` |
| SQLite `integrity_check` | `equipment.db`, `assistant.sqlite3` 모두 `ok` |

**확인 한계:** 실제 관리자 계정으로 로그인해 운영 화면을 조작하지는 않았다. 동작은 같은 코드로 격리 환경에서 검증했다. 배포 전에 열어 둔 관리 화면과 AI 도우미 탭은 새로고침해야 새 화면이 적용된다.
