# Antigravity 작업별 반복 오류 분석 보고서

작성일: 2026-09-09
작성자: Codex
조사 방식: 원본 변경 없는 읽기 전용 분석

## 1. 결론

Antigravity가 작업을 시작할 때마다 오류가 나타난다는 관찰은 로그로 확인된다. 가장 직접적인 원인은 현재 conversation에 누적된 **잘못된 형식의 영구 명령 허용 기록**이다. Antigravity는 새 작업을 시작할 때 이 기록을 다시 읽으며, 매번 동일한 `invalid grant string` 경고 23건을 발생시킨다.

동시에 Antigravity의 `grep_search`는 `D:\Project\...` 같은 Windows 절대경로를 올바르게 처리하지 못한다. 검색 결과의 드라이브 문자 뒤 콜론을 행 번호 구분자로 잘못 해석하여 한 번의 검색에서 수십~수백 건의 `Error parsing grep result`를 기록한다.

대화 전사 수집기는 현재 정상이다. Git 인덱스 0바이트 손상은 Antigravity IDE의 과도한 Git 자동 조회와 시간상 인접하지만, 현재 기록만으로 인덱스를 실제로 절단한 프로세스를 확정할 수 없다.

## 2. 조사 자료

- 활성 conversation: `3dadc1a5-03c4-4507-890a-f6524ca7e2b1`
- 표준 전사: `%USERPROFILE%\.gemini\antigravity\brain\<conversation-id>\.system_generated\logs\transcript.jsonl`
- 상세 전사: 같은 경로의 `transcript_full.jsonl`
- Antigravity language server 로그: `%USERPROFILE%\.gemini\antigravity\cli.log`
- conversation DB: `%USERPROFILE%\.gemini\antigravity\conversations\<conversation-id>.db`
- IDE Git 로그: `%APPDATA%\Antigravity IDE\logs\20260908T110417\window1\exthost\vscode.git\Git.log`
- Git 인덱스 손상본 3개와 현재 인덱스 메타데이터

전사 원문은 약 2.5MB, 1,700행 이상이며 사용자 입력, Gemini 응답, tool call, tool 결과 및 시각을 포함한다. 비밀정보가 포함될 수 있으므로 원문 사본을 프로젝트에 추가하지 않았다.

## 3. 확정된 반복 오류 1: 잘못된 permission grant

로그에는 다음 형식의 경고가 반복된다.

```text
permission_grant_store.go:366] ignoring invalid allow entry "command(node -e \"...다중행 명령...\")": invalid grant string
```

발생 묶음은 다음과 같다.

| 시각(KST) | 동일 경고 수 |
| --- | ---: |
| 2026-09-08 14:52 | 23 |
| 2026-09-09 10:14 | 23 |
| 2026-09-09 11:49 | 23 |
| 2026-09-09 11:59 | 23 |

각 묶음은 새 사용자 작업이 시작되거나 기존 작업이 다시 로드되는 시각과 일치한다. DB의 `steps.permissions`를 읽기 전용으로 조사한 결과, 과거에 허용된 `node -e`, `python -c`, `powershell -Command` 다중행 명령이 protobuf blob 안에 남아 있었다. 다중행 권한 기록은 현재 grant parser가 받아들이는 단순 명령 패턴이 아니므로 로딩할 때마다 거부된다.

이 오류는 프로젝트 코드나 conversation recorder가 만든 오류가 아니다. Antigravity가 자기 conversation DB에 저장한 과거 명령 권한과 현재 권한 파서의 호환 문제다.

### 영향

- 매 작업 시작 시 같은 경고가 반복된다.
- 해당 잘못된 allow 항목은 무시되므로 이전의 자동 허용이 적용되지 않는다.
- 작업 결과 파일을 직접 손상시키는 오류는 아니지만 로그를 오염시키고 실제 오류 식별을 어렵게 한다.

## 4. 확정된 반복 오류 2: Windows 경로 grep 파서

`grep_search`가 반환한 경로가 `D:/Project/...`이면 Antigravity 내부 parser가 `D:`의 콜론 뒤 문자열을 행 번호로 변환하려고 한다. 그 결과 다음 오류가 발생한다.

```text
grep_handler.go:518] Error parsing grep result: strconv.Atoi: parsing "/Project/Mini-Server-Web-EqMgmt/Rule.md": invalid syntax
```

집계 결과는 다음과 같다.

| 시각(KST) | 파싱 오류 수 | 관련 검색 |
| --- | ---: | --- |
| 2026-09-09 10:15 | 248 | Rule 및 프로젝트 경로 검색 |
| 2026-09-09 10:21 | 2 | 문서 검색 |
| 2026-09-09 12:00 | 24 | recorder 파일 검색 |

오류 수가 실제 검색 횟수보다 큰 이유는 검색 결과 한 줄마다 같은 파싱 오류가 발생하기 때문이다. 저장소 내용의 문제가 아니라 Antigravity의 Windows 절대경로 처리 결함이다.

### 영향

- 일부 검색 결과가 누락되거나 검색 도구가 실패한 것처럼 보일 수 있다.
- Gemini가 불완전한 검색 결과를 근거로 결론을 낼 가능성이 있다.
- `run_command`에서 작업 디렉터리를 프로젝트 루트로 고정하고 `rg`의 상대경로 결과를 사용하면 우회할 수 있다.

## 5. 별도 일회성 오류

- 2026-09-08 시작 시 Playwright 1.57.0 Windows driver 다운로드 URL이 404를 반환했다.
- 이전 CLI conversation의 `.pb` trajectory 파일 2개를 찾지 못했다.

이 오류는 시작 시 한 번 발생했으며 작업마다 반복된 23건 경고와는 별개다.

## 6. conversation recorder 점검

`conversation-recorder ensure` 결과 Codex와 Antigravity 모두 `status: ok`이며 오류는 0건이었다. 이번 조사 시 112개 Antigravity 이벤트를 읽었고 기존 기록과 정상 대조했다. watcher PID 29904도 실행 중이다.

따라서 transcript를 읽고 Chat으로 투영하는 과정 자체가 Antigravity의 `invalid grant string`이나 grep parser 오류를 만든 것은 아니다.

다만 recorder는 `Chat/.state/conversation-recorder.json` 약 291KB를 1.5초마다 다시 쓴다. 내용 변화가 없어도 수정 시각이 계속 바뀌며 Antigravity IDE Git 확장은 이를 감지해 약 5초마다 `git status -z -uall`과 관련 명령을 실행한다. 이 동작은 기능상 오류는 아니지만 불필요한 디스크·Git 조회를 만든다.

## 7. Git 인덱스 손상과의 관계

확인된 0바이트 인덱스 시각은 다음과 같다.

| 손상본 | 마지막 수정 시각(KST) |
| --- | --- |
| `index.corrupt.bak` | 2026-09-07 14:29:44.776 |
| `index.corrupt.20260908-093640.bak` | 2026-09-08 09:36:40.278 |
| `index.corrupt.20260909-113251.bak` | 2026-09-09 11:32:51.702 |

9월 9일 전사를 대조하면 Gemini의 직전 작업은 10:22에 끝났고 다음 작업은 11:49에 시작했다. 즉 11:32:51에는 Gemini tool call이 없었다. 9월 8일 손상도 09:34 작업 종료와 09:38 다음 요청 사이에 기록되었다.

IDE Git 로그에서는 9월 9일 11:32:51 전후로 같은 저장소에 `git status -z -uall`이 매우 자주 실행되었지만, 그 로그에는 fatal이나 인덱스 절단 명령이 없다. 전사와 저장소 스크립트에서도 `.git/index`를 직접 쓰는 명령은 발견되지 않았다.

따라서 다음 두 사실을 분리해야 한다.

1. Antigravity IDE와 recorder가 Git 조회 빈도를 크게 높이는 것은 확인됐다.
2. Antigravity 또는 recorder가 인덱스를 직접 0바이트로 만들었다는 증거는 아직 없다.

Git의 정상 인덱스 갱신은 `.git/index.lock`을 작성한 뒤 교체하는 방식이다. 단순한 읽기 충돌만으로 기존 인덱스가 0바이트가 되었다고 단정할 수 없다. 다음 재현 때 `SetEndOfFile` 또는 0바이트 `WriteFile`을 실행한 프로세스를 기록해야 직접 원인이 확정된다.

## 8. 권고 순서

1. **Antigravity 반복 경고 격리**: 새 conversation에서 같은 작업을 한 번 실행해 23건 경고가 사라지는지 확인한다. 사라지면 현재 conversation DB의 과거 다중행 grant가 원인임이 재현된다.
2. **grep 우회**: Antigravity의 `grep_search` 대신 프로젝트 루트에서 `rg`를 실행하고 상대경로를 출력한다.
3. **권한 원장 정리 계획**: 현재 conversation DB를 백업한 뒤 잘못된 permission blob만 정리하거나 conversation을 새로 시작한다. DB 직접 수정은 원본 대화 무결성과 복구 검증이 필요하므로 별도 작업으로 수행한다.
4. **recorder 쓰기 감소**: 상태가 실제로 달라졌을 때만 state를 원자적으로 갱신하고, heartbeat가 필요하면 별도 작은 파일과 긴 주기를 사용한다.
5. **IDE Git 부하 완화**: `Chat/.state/**`를 Antigravity IDE watcher 제외 대상으로 지정하거나 조사 기간에 Git 자동 새로고침을 중지한다.
6. **인덱스 직접 원인 포착**: 다음 재현 전에 Process Monitor에서 대상 경로를 `D:\Project\Mini-Server-Web-EqMgmt\.git\index`로 제한하고 `WriteFile`, `SetEndOfFile`, rename 이벤트와 프로세스명을 기록한다.

## 9. 최종 판단

사용자가 매 작업마다 본 반복 오류는 주로 **현재 Antigravity conversation에 누적된 23개 잘못된 command grant**에서 발생한다. 검색 작업에서는 **Windows 드라이브 경로 parser 결함**이 추가로 대량 오류를 만든다. 이 두 문제는 로그와 DB에서 재현 가능한 수준으로 확인됐다.

Git 인덱스 손상은 IDE·자동화의 과도한 동시 Git 접근과 관련 가능성이 있으나 직접 작성 프로세스는 아직 확인되지 않았다. recorder를 직접 원인으로 단정한 기존 Gemini 설명은 증거보다 앞선 결론이다.
