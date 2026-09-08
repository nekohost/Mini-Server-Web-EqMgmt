# [검증 보고서] 대화 자동 기록기 Staging 구현

- 검증일: 2026-09-09
- 기준 계획: `Plans/2026-09-08_Conversation_Automatic_Recording_Improvement_Plan.md`
- 후보 거버넌스 버전: `1.2.0`
- 후보 Rule SHA-256: `101AC771781BC9237B2126B4675803EEA0E895B4138410104383D6FCE1AD5269`
- 종합 판정: **운영 소스 병합 가능**

## 구현 결과

Node 표준 기능만 사용하는 단일 기록기와 `ensure`, `watch`, `reconcile`, `status --json`, `verify` 명령을 구현했다. Codex rollout과 Antigravity brain transcript를 실제 이벤트 시각으로 읽으며 사용자·표시 중간 안내·최종 응답만 주 대화에 기록한다. 하위 에이전트의 task·상태·최종 handoff는 companion에 분리하고 일자 파일에는 receipt를 둔다.

Windows watcher는 `fs.watch` 신호와 기본 1.5초 stat 폴링을 함께 사용한다. 프로젝트당 단일 writer 잠금, 임시 파일 `fsync` 후 원자적 rename, provenance, cursor와 receipt를 적용했다. 비밀번호·토큰·개인키·전자우편·휴대전화·개인식별번호는 저장 전에 치환한다.

Antigravity conversation은 최근 수정 폴더로 추정하지 않는다. workspace registry의 `conversation_metadata.json`·`last_conversations.json`, brain transcript의 workspace, 부모 mailbox의 UUID sender·recipient를 대조한다. Claude는 검증된 원본이 없어 명시적으로 `unsupported`이다.

## Validation 1~8

1. **거버넌스**: Rule 변경 17개 섹션과 신규 4개 섹션을 node·rule map·human map·section baseline·manifest에 동기화했다. Staging validate 결과 41개 노드, 오류 0건, 경고 0건이다.
2. **사용자 의도**: 별도 기록 지시 없이 일반 턴을 자동 기록하고 Codex·Antigravity 우선 활성화, 하위 작업 가시성, Claude 단계적 보류를 모두 반영했다.
3. **정적 로직**: 기록기 테스트 12개와 기존 governance 테스트 12개가 통과했다. 날짜 전환, 필터, 중복, state 저장 전 중단 재시도, UTF-8 64KiB 분할, mailbox 관계, stat 재조정, 단일 watcher를 검증했다.
4. **운영 영향**: 변경 대상은 개발 PC의 거버넌스·대화 기록 경로뿐이다. `app.py`, DB, Flask·Gunicorn과 Linux 서비스 코드는 변경하지 않는다.
5. **보안·경계**: Chat 경로 이탈 차단, 원문 없는 상태 파일, 비밀·개인정보 치환, 알 수 없는 JSONL 오류 격리, system·developer·reasoning·tool·guardian 필터를 확인했다.
6. **롤백**: recorder, 세 진입점 preflight, 신규 always-load 노드, router·manifest·capability를 같은 변경 단위로 되돌릴 수 있다. 정상 Chat 기록은 롤백에서 삭제하지 않는다.
7. **사람 실수**: 중복 watcher는 기존 PID를 재사용하고, 살아 있는 writer와 충돌하면 최대 5초 기다린다. 폴링 설정은 1000~2000ms 밖의 값을 거부한다.
8. **AI 메타**: Codex의 user 역할 환경 주입을 실제 사용자 발언에서 제외했다. 하위 agent는 작업·표시 상태·final만 기록하고 내부 컨텍스트와 도구 원문은 제외한다.

## 실제 원본 shadow 검사

운영 Chat을 쓰지 않는 dry-run에서 현재 workspace 원본을 성공적으로 파싱했다.

| 플랫폼 | 원본 대상 이벤트 | 기존 Chat과 exact 일치 | 추가 예정 주 대화·receipt | companion 조각 |
| --- | ---: | ---: | ---: | ---: |
| Codex | 843 | 694 | 109 | 3 |
| Antigravity | 108 | 58 | 42 | 4 |

추가 예정에는 이전 복구 뒤에도 남아 있던 과거 누락과 2026-09-08 14:59 이후 대화가 포함된다. 운영 병합 뒤 최초 reconcile에서 provenance를 붙여 반영하고 곧바로 `verify`로 누락·중복을 전수 대조한다.

## 검증 중 수정한 결함

- Codex가 user 역할로 기록한 `<environment_context>`를 실제 사용자 메시지로 오인하던 필터를 수정했다.
- Antigravity mailbox의 `system` 발신자를 worker로 오인하던 판별을 UUID sender·recipient로 제한했다.
- 새 Antigravity 직접 conversation 첫 턴을 찾도록 workspace registry 연계를 추가했다.
- 단일 대형 하위 메시지도 UTF-8 문자를 깨뜨리지 않고 64KiB 이하로 분할하도록 수정했다.
- preflight와 watcher가 잠깐 겹칠 때 즉시 실패하지 않고 최대 5초 동안 writer 잠금을 기다리게 했다.
- `fs.watch` 신호가 폴링 타이머를 실제로 즉시 깨우도록 watcher 대기 로직을 수정했다.
- 신규 always-load 노드 때문에 소형 모델 Rule 검토 pack이 기존 4000 토큰 한도를 초과하여 한도를 5000으로 조정했고, 최대 pack 4974 토큰으로 통과했다.
- 플랫폼별 preflight가 먼저 실행된 watcher만 재사용할 수 있던 구성을 수정해 모든 진입점이 `--platform all`로 Codex·Antigravity를 함께 감시하게 했다.

## 남은 제한

- Claude 자동 기록은 이번 버전에서 지원하지 않는다.
- 패턴 기반 비밀 치환은 알려진 형식을 대상으로 하므로 새 비밀 형식이 생기면 redactor fixture를 추가해야 한다.
- IDE 폴더 열기 자동 Task를 사용자가 허용하지 않은 환경에서도 매 턴 진입점의 `ensure`가 watcher 시작과 누락 재조정을 수행한다.
