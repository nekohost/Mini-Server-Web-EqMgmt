# Staging Rule 도구 정책 동기화 계획

## 목적

사용자가 `Staging/Rule.md`에 직접 추가한 백업 서버 정보를 운영 반영 시에도 보존하고 실제 실행 노드에 동기화한다. 대화 저장 및 일반 파일 편집의 도구 우선순위를 플랫폼 능력과 Undo 가능성에 따라 명확히 한다.

## 적용 범위

1. `Staging/Rule.md`
2. 백업 서버·대화 저장·파일 편집·Staging 병합 관련 노드
3. Codex, Gemini/Antigravity, Claude capability profile
4. `human-rule-map.yaml`, manifest 및 관련 진입점

## 정책 결정

- 백업 서버 IP `192.168.0.24`는 사용자가 직접 추가한 승인 대기 정책으로 보존하며 `context.deployment-topology`에 투영한다.
- `[제안-013]` 구현 전 실제 DB 스키마 확인은 이번 작업에서 제외한다.
- Chat 저장은 플랫폼의 구조화된 편집 도구가 원문 완전성·Diff·Undo를 제공하면 이를 우선한다.
- Antigravity의 과거 누락·오기입 경험은 모든 플랫폼에 일반화하지 않고 해당 capability에 기록한다.
- 일반 파일의 터미널 쓰기는 기본 금지한다. 구조화된 편집 도구로 조치할 수 없고, 플랫폼이 Diff와 신뢰 가능한 Undo 또는 동등한 복구를 보장할 때에만 정확한 방법·영향·복구 절차를 제안하고 사용자 명시 승인 후 예외적으로 사용할 수 있다.

## 검증

- Rule 포인터와 노드 `human_rule_sections`의 양방향 일치
- manifest의 Staging Rule SHA-256 갱신
- 관련 제품 진입점과 capability의 의미 일치
- YAML 파싱 및 포인터 대상 파일 존재 확인
- Validation 1~8단계에서 문서 변경에 해당하는 관찰점 검토

## 제외 범위

- 루트 운영 `Rule.md`, `GEMINI.md`, `VALIDATION_METHODOLOGY.md` 변경
- 실제 운영 병합
- 실제 DB 또는 백업 DB 열람과 스키마 확정

