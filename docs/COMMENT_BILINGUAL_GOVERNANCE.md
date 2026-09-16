# Mini-Server 이중언어 주석 동기화 규격

## 1. 목적
ChatGPT/Codex는 구현과 기술적 영문 기준 주석을 담당하고, Gemini는 실제 코드와 EN을 감사한 뒤 한국어 설명을 동기화한다.
기존 Mini-Server의 `[역할]`, `[의존성 관계]`, `[변경 시 영향도]` 계약은 삭제하지 않고 EN/KO 블록 안에 보존한다.

실행 경로는 AGENTS의 runtime profile 결과를 따른다. 이 규격을 참고했다는 이유로 legacy 절차·역할 강제를 독립 노드에 재적용하지 않는다. 실제 감사자와 승인 근거는 감사 보고서에 정확히 기록하며 다른 모델이 수행한 것으로 표기하지 않는다.

## 2. 우선순위
1. 실제 실행 코드·데이터 계약
2. `[EN rev.N]` 기준 주석
3. `[KO rev.N]` 한국어 감사본

소스와 EN이 다르면 Gemini는 KO를 갱신하지 않고 `CONTRACT-DIVERGENCE`로 보고한다.

## 3. 표준 블록
```text
[MINI-COMMENT: EQUIPMENT.CATALOG.TREE]
[EN rev.2]
[Role] Returns the approved catalog tree.
[Dependencies] lineup repository and equipment registration UI.
[Impact] Changes cascade into model selection and admin management.
[KO rev.2]
[역할] 승인된 카탈로그 트리를 반환한다.
[의존성 관계] 라인업 저장소와 장비 등록 UI가 사용한다.
[변경 시 영향도] 모델 선택과 관리자 관리 화면에 영향을 준다.
```

## 4. Revision과 상태
- ChatGPT/Codex가 추적 코드 계약 또는 EN 본문을 바꾸면 EN revision을 증가시킨다.
- Gemini는 소스와 EN을 확인한 뒤 KO 본문과 KO revision만 동기화한다.
- `EN > KO`: `TRANSLATION-PENDING`.
- `KO > EN`: `INVALID-KO-AHEAD`.
- source hash가 바뀌고 EN rev가 같으면 `REVISION-SUSPECT`.
- EN/KO 본문 hash가 바뀌고 해당 rev가 같으면 각각 revision suspect로 본다.
- baseline에 있던 Comment ID가 사라지면 `MISSING-COMMENT`, 중복되면 `DUPLICATE-ID`다.
- 파일 이동은 ID를 유지하되 `LOCATION-CHANGED`로 재감사한다.
- 기존 baseline보다 EN/KO revision이 낮아지면 `REVISION-REGRESSION`이다.
- 양쪽 revision이 같아도 baseline과 내용/revision/hash가 달라졌으면 `AUDIT-REQUIRED`이며 재감사 전 `check`는 성공하지 않는다.
- ID/EN/KO marker는 순서대로 각각 한 번만 선언한다. EN은 1 이상, KO는 0 이상의 안전한 정수여야 하며 필수 메타에는 빈 label만이 아니라 설명이 있어야 한다.

## 5. Comment ID
ID는 파일명보다 책임을 나타내는 대문자 ASCII와 `.` 조합을 사용한다.
함수명·파일 이동만으로 ID를 바꾸지 않으며 삭제된 ID를 다른 의미로 재사용하지 않는다.

## 6. 추적 대상
모듈·공개 API·라우트·비자명한 내부 계약·권한·저장·트랜잭션·실패 복구 등 사람이 설계 의도를 다시 읽어야 하는 주석을 우선 추적한다.
자명한 행 설명을 모두 이중언어화하지 않는다. 기존 행 단위 상세 주석 규칙은 별도로 유지한다.

## 7. Gemini 권한 경계
Gemini의 주석 감사 작업에서 기본 허용은 KO 본문·KO revision·용어집·comment-sync state·명시된 감사 보고서다.
실행 코드, EN 본문/EN revision, API·DB 스키마·설정·테스트 동작 변경은 금지한다.
불일치가 코드 결함으로 보여도 구현 작업자에게 보고하며 별도 구현 지시 없이는 수정하지 않는다.

## 8. Git diff guard
감사 시작 전 snapshot을 만들고 종료 후 같은 HEAD에서 delta를 검사한다.
선행 dirty 파일은 snapshot 내용과 비교해 다른 작업자의 기존 변경을 허위 위반으로 잡지 않는다.
소스 파일은 KO 영역을 마스킹한 전후 내용이 완전히 같아야 하며, 그 외 변화가 있으면 fail-closed한다.
감사 도중 HEAD가 바뀌면 다른 작업자 commit 가능성이 있으므로 검사를 중단하고 새 snapshot으로 재시작한다.

snapshot은 작업트리와 Git index의 별도 기준을 보존한다. 한국어·공백·화살표 등이 포함된 경로도 NUL-delimited Git 출력으로 검사한다. 스테이징된 코드 변경을 작업 파일 원복으로 숨길 수 없다.
작업마다 `.agent-governance/comment-sync/audit-snapshot-<작업별 식별자>.json`처럼 새로운 이름을 선택하고 snapshot/check에 같은 경로를 쓴다. 기존 snapshot을 덮어쓰지 않는다. 이 로컬 파일은 다른 작업자의 원문을 포함하므로 `.gitignore`에서 제외하며 공개 보고서에 첨부하지 않는다.
`--allow-path` 추가 허용은 구체적인 `Reports/*.md` 감사 보고서에만 사용한다. 소스·설정·테스트를 이 옵션으로 허용하지 않는다.
guard는 Git-visible 작업트리/index 변화의 검사 도구이지 접근 제어 장벽이 아니다. 이미 Git에서 무시한 파일·외부 시스템·도구나 snapshot 자체의 악의적 동시 변조까지 보장하지 않는다.

## 9. Baseline
`baseline --accept-audited`는 EN/KO revision이 같고 3대 메타 필드가 모두 존재하며 중복 ID가 없을 때만 허용한다.
state 파일만 수정해 경고를 숨기지 않는다. baseline은 실제 소스/EN 감사가 끝난 뒤의 승인 원장이다.
추적 블록과 baseline이 모두 0개인 최초 상태의 `check`는 `BOOTSTRAP-PENDING`을 정보성 성공으로 보고한다. 첫 baseline이 생긴 뒤부터는 누락·revision·hash 이상을 strict fail-closed로 처리한다.
신규 구현에서 EN만 준비된 블록은 KO marker가 없어도 `TRANSLATION-PENDING + NEW-UNBASELINED`로 인계할 수 있다. 반면 이미 baseline된 블록에서 KO가 사라지면 `FORMAT-ERROR`다.
기존 한국어 메타 주석을 최초 전환할 때는 문구를 바꾸지 않고 `[KO rev.0]`으로 감쌀 수 있다. 이는 감사 완료가 아니며 Gemini가 실제 소스와 EN을 확인한 뒤 EN revision으로 올려야 baseline 대상이 된다.
초기 도입은 핵심 파일부터 점진적으로 수행하며 전체 저장소를 한 번에 기계 변환하지 않는다.

baseline 갱신도 이전 원장과 비교한다. revision suspect/regression, 삭제 ID, 형식·메타 오류가 있으면 쓰기 전에 거부한다. 신규 ID·정상 재감사·경로 이동은 실제 감사 완료 후 수용할 수 있다. 의도적인 ID 폐기는 별도의 검토된 원장 변경으로 다루며 일반 갱신으로 조용히 제거하지 않는다.
없는 config root나 손상된 state를 빈 최초 상태로 취급하지 않는다. 원장 저장은 같은 디렉터리의 임시 파일을 원자 교체한다.
감사 증거는 `--audit-report=Reports/...md --auditor="실제 감사자"` 쌍으로 원장에 남길 수 있다. `--accept-audited`는 감사 완료의 명시적 주장이지 감사 자체를 수행하거나 신원을 인증하는 기능이 아니다.

## 10. 다중언어 범위
초기 parser는 Python `#`/triple-quoted comment block, JavaScript `//`/`/* */`, HTML `<!-- -->`의 명시적 `MINI-COMMENT` 블록을 추적한다.
`comment-format.mjs`를 검사기와 guard가 공유한다. 독립된 주석과 명확한 Python docstring(모듈 첫 문장 또는 한 줄 def/class 선언의 첫 문장)을 지원한다. 대입·f-string·JS template·HTML 속성/script/style/textarea·Jinja 문자열 속 주석 모양 데이터는 번역 대상으로 취급하지 않는다. HTML 주석 내 Jinja 구문도 실행될 수 있어 KO-only 변경으로 허용하지 않는다.
완전한 언어 AST parser는 아니다. 여러 줄 함수 선언 등 판별이 어려운 문법은 독립 `#` 주석 형식 또는 별도의 구현 검토로 처리한다.
초기 source hash는 현재 블록 끝부터 다음 추적 블록 또는 EOF까지의 보수적 범위를 사용한다. false positive 재감사는 허용하되 실제 코드 변경 누락보다 안전을 우선한다.
블록 앞의 import/상수나 외부 호출자·DB 계약은 이 hash에 포함되지 않으므로 별도의 의미 감사가 필요하다.
추적 밀도가 올라가면 source 범위가 자연스럽게 좁아진다. 의미 기반 parser로 개선할 경우 별도 검증 후 교체한다.

## 11. Git 기록 언어
AI 작업자가 만드는 일반 commit은 `feat:`, `fix:`, `docs:`, `test:`, `refactor:` 등 Conventional Commit type을 유지하고 제목과 본문 설명은 한국어를 기본으로 한다.
API명·파일명·심벌·표준 고유명사는 원문을 유지한다. 자동 생성 merge/revert 메시지는 별도 도구 계약을 따른다.
`commit-message-check.mjs`는 전체 여러 줄 메시지 또는 `--file <메시지 파일>`을 받으며 제목과 본문(존재 시)의 한국어 포함 여부를 확인한다. 이는 언어 휴리스틱이며 문장 품질 검증은 아니다. 자동 메시지 예외도 정해진 형식만 수용한다.
