# [구현·검증 보고서] Rule 5-1-2 개발·검증·배포 순서 보강

작성일: 2026-09-08
작업 모드: 승인된 Rule 개정 및 동기화
기준 Rule SHA-256: `0366391F84CF1F9C6AA30DB4E8E60927A05903A159E13AB815A2C586445AD7EB`
반영 Rule SHA-256: `CF8428BFDC14058B2D2BFE934751514DCA0D3E2655A9274D9AF40F043535F79E`
결론: **완료 — Rule, 실행 노드, 추적성, 기준선, manifest 동기화 확인**

## 반영 내용

- `Rule.md` 5-1-2에 운영 소스 반영과 Linux 서비스 적용의 정의를 추가했다.
- Staging 구현부터 Linux pull·격리 검증·서비스 시작까지의 10단계 표준 순서를 추가했다.
- Linux 실행 검증이 미완료라는 이유로 사용자 승인된 운영 소스 병합이나 Git push를 선행 차단하지 않도록 명시했다.
- Linux 검증 실패 시 서버에서 직접 수정하지 않고 Windows Staging 흐름으로 복귀하도록 정했다.
- Linux 검증 대상은 미니서버 또는 사용자가 지정한 백업 Linux 서버로 명확히 했다.
- `HUMAN-5.1.2-ORDER`를 Rule 포인터, `operations.server-execution`, human-rule-map에 연결했다.
- manifest 거버넌스 버전을 `1.1.1`로 올리고 새 Rule hash와 5-1-2 섹션 hash, 실행 노드 digest를 반영했다.

## Validation 1~8

### 1단계 — 거버넌스: 통과

변경 전 `sync-status`는 기준 hash와 현재 hash 일치, 변경 0건을 확인했다. 변경 후 `sync-plan`은 5-1-2와 `operations.server-execution`을 정확한 대상로 산출했고, 정규 파서 `validate --expected-rule-sha`는 오류 0건, 경고 0건으로 통과했다.

### 2단계 — 사용자 의도: 통과

사용자가 지정한 순서인 Staging 정적 판단, 운영 소스 병합, Git push, Linux pull, Linux 실행 검증을 10개 단계로 고정했다. 운영 소스 반영과 Linux 서비스 적용을 다른 용어로 분리했다.

### 3단계 — 정적 논리: 통과

Windows 로컬 실행 금지, Staging 비구동 정적 검토, 승인 후 운영 병합·Staging 정리 규칙과 일관된다. Linux에서만 실제 테스트할 수 있다는 제약과 Git 전달 순서가 충돌하지 않는다.

### 4단계 — 운영 영향: 통과

애플리케이션 코드, DB, systemd 설정, 실행 중 서비스에는 변경이 없다. 이후 작업에서 Linux 실행 검증 미완료를 이유로 승인된 운영 소스 병합과 push를 잘못 차단하는 해석만 제거한다.

### 5단계 — 보안과 예외: 통과

Linux 검증은 정확한 Git commit pull과 일치 확인 뒤 수행하도록 했다. 운영 DB 자동 시험이나 자격증명·주소의 Rule 추가는 하지 않았다. 백업 Linux 사용은 사용자가 검증 대상으로 지정한 경우로 제한한다.

### 6단계 — 롤백: 통과

변경은 Rule·노드·원장·기준선·manifest의 단일 변경 묶음이다. 문제 발생 시 이 묶음을 이전 Git commit으로 되돌릴 수 있고, 변경 전·후 Rule hash가 본 보고서에 남아 있다.

### 7단계 — 휴먼 에러 방지: 통과

10단계 번호 목록, 용어 정의, Linux 실패 시 Windows Staging으로 복귀하는 경로를 함께 제공한다. 순서의 생략·재배열과 서버 직접 수정 가능성을 줄인다.

### 8단계 — AI 메타: 통과

변경 범위를 5-1-2와 이미 매핑된 실행 노드로 제한했다. 새 노드·router·애플리케이션 코드를 추가하지 않았다. 기존 마스터 데이터 Staging 산출물은 읽거나 수정하거나 정리하지 않았다.

## 검증 결과

- `node .agent-governance/tooling/governance-tool.mjs validate --expected-rule-sha CF8428BFDC14058B2D2BFE934751514DCA0D3E2655A9274D9AF40F043535F79E`: 통과
- `node .agent-governance/tooling/governance-tool.mjs sync-status`: 변경 0건, `inSync: true`
- Rule 5-1-2에 정의 문구, 10단계 번호, Git push 이후 Linux pull, Linux 실패 복귀 문구가 모두 있는지 정적 검사: 통과

