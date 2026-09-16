# Mini-Server 기술 주석 용어집

| English | 권장 한국어 | 주의 |
| --- | --- | --- |
| canonical | 기준 / 기준본 | EN 기준 주석 문맥 |
| invariant | 불변조건 | 항상 유지해야 하는 계약 |
| transaction | 트랜잭션 | DB 원자성 문맥 |
| atomic / atomically | 원자적 / 원자적으로 | 부분 저장이 없음을 의미 |
| rollback | 롤백 / 원복 | DB와 Git 문맥을 구분 |
| snapshot | 스냅샷 | 특정 시점 상태 |
| source hash | 소스 해시 | 주석이 설명하는 코드 범위의 SHA-256 |
| revision | revision / 변경 번호 | 릴리스 버전과 구분 |
| approval | 승인 / 결재 | UI의 결재 요청과 사용자 승인 문맥 구분 |
| pending | 승인 대기 / 처리 중 | 상태 계약에 맞춤 |
| stale | 오래된 / 무효화가 필요한 | 캐시·선택 상태 문맥 |
| fail closed | 안전하게 거부 | 불확실할 때 허용하지 않음 |
| idempotent | 멱등 | 반복 요청 결과 계약 |
| dependency | 의존성 | 코드·파일·UI 소비자 포함 |
| impact | 변경 시 영향도 | 기존 메타 주석과 동일 의미 |

API·함수·클래스·컬럼·파일명·HTTP 상태·Git 명령·프로토콜 식별자는 원문을 유지한다.
새 용어는 기존 뜻을 뒤집지 않고 문맥 차이가 있으면 주의 칸에 구분 기준을 적는다.
