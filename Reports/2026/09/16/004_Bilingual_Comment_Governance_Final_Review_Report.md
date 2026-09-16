---
artifact_id: REPORT-20260916-004
work_id: WORK-20260916-BILINGUAL-COMMENT-GOVERNANCE-ADOPTION
created_at: 2026-09-16T17:08:00+09:00
related_artifacts:
  - ../../../../Plans/2026/09/16/002_Bilingual_Comment_Governance_Adoption_Plan.md
  - ../../../../Tasks/2026/09/16/001_Bilingual_Comment_Governance_Adoption_Task.md
  - 003_Bilingual_Comment_Governance_Adoption_Report.md
---
# 이중언어 주석 도입 최종 교차검토 및 보완

## 판단과 승인 범위

도입 방향은 적합하지만 기존 27건 테스트만으로 완료 판정하기에는 검사 누락이 있었다. 추가 재현 시나리오 16건 중 15건이 기존 구현에서 실패했다. 기존 자료의 “100%”, “완벽하게 차단” 표현은 검증 범위를 넘어선다. 정상 사례와 거부 사례를 함께 보강한 뒤 완료한다.

사용자의 이번 요청은 상세 검토, 필요한 개선의 자동 반영, 잔여 작업 완료까지 명시 승인했다. 진입점 preflight와 runtime profile 결과는 `dedicated / verified-runtime-exact-match / codex / gpt-6-astra`다. 이 경로는 legacy 역할·고정 Staging·8단계를 상속하지 않는다. 기존 보고서는 과거 수행 기록으로 보존한다.

이번 파일럿 재감사와 KO 작성자는 **Codex / GPT-6 Astra**다. 연결된 Gemini 실행 도구/CLI가 없어 Gemini에게 감사했다고 기록하지 않는다. 사용자 승인하에 독립 실행 경로에서 실제 소스, 호출부, EN, 격리 계약 테스트를 직접 대조하여 종료한다. 이는 이번 수행의 귀속이며, legacy의 Codex 구현/EN ↔ Gemini 감사/KO 역할 분담이나 전용 노드의 적용 대상을 변경하지 않는다.

## 검토 대상별 결과

| 대상 | 확인 및 조치 |
|---|---|
| 계획 002 / Task 001 / 보고서 003 | 기존 도입은 커밋 완료, 파일럿 감사·최초 baseline이 미완료였음을 확인. 이번 후속 검토와 완료 근거를 연결 |
| HTCE 비교 보고서 002 | 도입 원칙은 유지. 과도한 확정 표현과 검사기의 보장 범위를 정정. 당시 HTCE 수치와 현 Mini-Server 검증 결과를 구분 |
| 이중언어 규격 / 용어집 | source > EN > KO, 3대 메타 필드, 안정 ID 유지. 용어 기준 변경 불필요. revision 회귀·재감사·지원 문법·도구 한계를 규격에 명시 |
| Rule / 실행 노드 4개 | Rule 1-3, 4-3, 7-4, 7-5와 노드 의미 대조. 이번에는 정책 본문 변경 불필요 |
| human/rule map / section baseline | 신규 섹션·RULE ID가 기존 노드에 연결됨. Rule hash 및 노드 section digest 보존 |
| manifest / 실행 프로필 | 도구 보완 버전 1.8.1, 변경된 governance-tool package hash와 registry seal 갱신. 독립/legacy 선택 계약 보존 |
| AGENTS / CHATGPT / GEMINI / Gemini capability | legacy 역할 구분을 독립 경로에 강제 상속하지 않음. Gemini snapshot 재사용 금지·로컬 보관 안내 보완 |
| comment-sync | baseline 덮어쓰기로 위반 은폐, revision 회귀, 양쪽 rev 증가 후 감사 누락, 손상 state/config, 잘못된 marker/빈 메타를 차단 |
| Gemini guard | 작업트리와 index를 각각 비교. Git NUL 경로, 실행 문자열 배제, 최초 KO 추가, 문서 allowlist, snapshot 덮어쓰기 금지 보강 |
| Commit 검사 | 한국어 여러 줄 메시지·본문 검사, `--file` 지원, 광범위한 Merge 접두사 예외 축소 |
| 회귀 / 신규 섹션 모델 | 단순 설계 모델만이 아니라 실제 sync-plan resolver를 직접 검증. 기존 27건과 별도 경계 회귀 유지 |
| 파일럿 | `_required_int`의 실제 호출부와 입력/오류 계약 대조. EN 의존성 설명 수정 후 EN/KO rev.2로 완료 대상 설정 |

## 재현된 문제와 수정

1. **기준선으로 위반을 덮어쓸 수 있었음.** `baseline --accept-audited`가 이전 원장과 비교하지 않아 코드만 바뀐 상태, 삭제 ID, revision 회귀를 승인했다. 이제 compare 결과 중 새 블록·정상 재감사·이동만 수용하고 나머지는 쓰기 전에 거부한다. 상태 파일은 같은 디렉터리의 임시 파일을 원자 교체한다.
2. **EN/KO revision만 같이 바꾸면 check가 성공했음.** 기존 baseline과 달라지면 `AUDIT-REQUIRED`, 과거 revision으로 되돌리면 `REVISION-REGRESSION`을 반환한다.
3. **실행 문자열을 KO 주석으로 취급했음.** Python 대입 triple-string, JavaScript template 안의 주석 모양 문자열, HTML/Jinja 실행 구문을 검사에서 제외할 수 있었다. 공유 `comment-format.mjs`에서 문자열과 지원되는 독립 주석을 분리하고 HTML 주석 안의 Jinja 구문은 번역 범위로 허용하지 않는다.
4. **Git index가 검사 대상에서 빠졌음.** 코드 변경을 stage한 다음 작업 파일만 원복하면 guard가 성공했다. snapshot에 index blob/mode를 보존하고 stage된 변경도 별도로 검사한다.
5. **한국어 경로가 Git의 따옴표/escape 출력에서 손실됐음.** `--porcelain=v1 -z --no-renames`와 NUL 기반 stage 목록을 사용하여 이름을 그대로 보존한다.
6. **정상 최초 KO 추가를 거부했음.** KO가 없는 EN-only 상태와 최초 번역 후 상태를 같은 비교 표현으로 만든다. EN 및 실행 코드의 변화는 계속 거부한다.
7. **allow-path와 snapshot의 경계가 넓었음.** 소스 파일을 `--allow-path`로 우회할 수 없게 하고 추가 허용은 명시한 `Reports/*.md`로 제한한다. 기존 snapshot은 덮어쓰지 않는다. schema/root/content hash 검증을 추가하고 로컬 snapshot을 Git ignore한다.
8. **입력 형식 검증이 불충분했음.** 중복/역순 marker, 빈 메타, 안전 정수 범위 밖 revision, 없는 root 및 손상 state는 실패한다.
9. **Commit 검사기가 실제 본문을 처리하지 못했음.** 제목/본문을 분리하고 한국어 포함 여부를 검사한다. `Merged anything` 같은 임의 문자열은 자동 메시지로 취급하지 않는다.

추가 테스트를 통과시키려고 검사 자체를 끄거나 규칙을 완화하지 않았다. 삭제 ID의 의도적 폐기는 별도 검토된 원장 변경으로 다루며, 일반 baseline 명령으로 조용히 지우지 않는다.

## 파일럿 소스 감사

대상은 `utils/lineup_node_service.py::_required_int`, ID `LINEUP.NODE.REQUIRED_INT`다.

- `bool`은 Python에서 `int`의 하위 타입이므로 첫 조건에서 명시 거부한다.
- `int` 또는 `str`만 `int(value)` 변환에 진입한다. float, bytes, None, dict, list는 거부한다.
- 문자열은 Python `int()`의 규칙을 따른다. 양끝 공백, `+`, 정수 구분용 `_`, 전각 숫자도 허용될 수 있으므로 “ASCII 숫자 문자열만 허용”이라고 쓰지 않는다.
- 결과가 0 이하이면 거부한다. 변환 오류를 `LineupNodeError`로 바꾸며 기본 status code는 400이다.
- 호출처는 category/manufacturer/node뿐 아니라 actor UserId, option ID 및 `_optional_int`도 포함한다.
- 기존 EN의 “Used by ... and LineupNodeError”는 의존 방향이 모호했다. 호출자와 발생시키는 오류를 분리하여 EN rev.2로 바로잡았다. 실행 코드는 바꾸지 않았다.

Linux 백업서버 SSH 연결을 확인하고, **로컬 후보 소스만 메모리로 보내는 격리 AST fixture**를 실행했다. 전체 모듈/Flask는 import하지 않고 DB에 연결하지 않는다. 양수/문자열 등 허용 7건, 거부 14건, 총 21건에서 값과 오류/status를 확인했다. Git HEAD와 주석/docstring을 제거한 전체 파일 AST도 동일하다. 이것은 운영 배포나 앱 통합 테스트를 수행했다는 뜻이 아니다.

재현 명령: `node .agent-governance/tooling/comment-pilot-linux.mjs eqmgmt-backup`.

## 검증 및 종료 증거

| 검사 | 결과 |
|---|---|
| 기존 `comment-sync.test.mjs` | 27/27 통과. 삭제 주석 검증은 파일을 유지한 채 블록을 제거하는 fixture로 명확히 분리 |
| 추가 `comment-hardening.test.mjs` | 25/25 통과. 초기 재현 16건 중 기존에서 15건 실패 → 수정 후 정상/거부 회귀 통과. 허용된 신규 보고서의 stage와 미종결 docstring도 추가 확인 |
| `governance-tool.test.mjs` | 19/19 통과. 실제 신규 섹션 resolver 성공·오류·원본 보존 포함 |
| `execution-profile.test.mjs` | 33/33 통과. 독립/legacy 분기 및 봉인 무결성 보존 |
| Linux 파일럿 격리 fixture | 21/21 통과, `PILOT-EXECUTABLE-AST: unchanged from Git HEAD` |
| 실제 파일럿 guard | `GEMINI-DIFF-GUARD: OK`, KO-only 소스 1개 + 허용된 state 생성만 탐지 |
| 실제 comment-sync | 추적 1, baseline 1, `COMMENT-SYNC: OK` |
| 거버넌스 validate | errors 0, warnings 0 |

최초 baseline 수용 시각: `2026-09-16T08:10:09.664Z` (17:10:09 KST). EN/KO rev.2, 감사자와 본 보고서 경로를 `comment-sync/state.json`에 기록했다.

실제 guard snapshot은 EN 정정과 도구 변경이 끝난 시점에서 만들었다. 그 이후의 KO 동기화·state 생성만 검사했으며 snapshot에 이미 있던 선행 수정은 기준으로 보존했다. 이후의 문서 정리는 별도 승인된 도입 마무리 작업이지 KO-only 작업으로 주장하지 않는다. snapshot 원문은 로컬 ignored 파일에만 보관한다.

Rule SHA-256은 `9DC100A665B2EE74D1D2CE1FC2E016BD5F617ED858DBF1786B06B90112180420`로 유지한다. Rule/human map/section baseline/실행 노드 자체는 바꾸지 않았으며 도구 구현 변경에 해당하는 package hash와 버전 1.8.1을 동기화했다. Git 최종 반영 결과는 완료 후 아래 기록에 추가한다.

## 한계와 보존 경계

- 주석 검사기는 명시된 ID와 config roots만 추적한다. 현재 파일럿 1개를 감사하는 작업이지 저장소 전체 주석의 정확성을 인증하는 작업이 아니다.
- source hash는 블록 뒤부터 다음 추적 블록/EOF까지다. 앞선 import·상수·호출자나 외부 DB 계약까지 의미적으로 추적하지 않는다. 의미 일치 판단은 소스 감사와 테스트의 책임이다.
- 공유 판독기는 완전한 Python/JS/HTML/Jinja parser가 아니다. 애매한 형식은 지원되는 독립 주석 형식 또는 별도 구현 검토로 다룬다.
- guard는 같은 HEAD의 Git-visible 작업트리/index를 검사하는 품질 게이트다. 이미 무시된 파일, 외부 시스템, 악의적 도구/snapshot 동시 변조에 대한 접근 제어·샌드박스가 아니다. snapshot hash와 감사 플래그도 실제 감사자의 신원을 암호학적으로 입증하지 않는다.
- Commit 언어 검사는 한국어 포함 여부의 정적 휴리스틱이지 문장 의미·번역 품질 검증이 아니다.
- 다른 작업자의 `Reports/2026/09/10/016_Lineup_Registration_UX_Followup_Review_Report.md`는 수정·stage하지 않는다. 시작 SHA-256: `3BCF109AB1FFB4F1D568D60E360AE5FC6C2317D384E41A317221B61A887072E3`.
- Rule 본문·DB·Flask 실행 코드는 불변이다. 거버넌스 도구/문서/주석만 반영하므로 운영 프로세스 재시작이나 DB migration은 하지 않는다.

복구는 이번 보완 commit의 scoped revert를 검토하여 수행한다. 신규 baseline과 해당 파일럿 주석을 같은 변경 단위로 되돌리고, 타 작업자의 dirty 파일이나 DB는 복구 대상으로 포함하지 않는다.
