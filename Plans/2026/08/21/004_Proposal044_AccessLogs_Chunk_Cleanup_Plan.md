# [기획서] [제안-044] 웹 접근 로그 청크(Chunk) 단위 분할 삭제 및 진행률 UI 적용

## 1. 개요 및 배경

### 1-1. 배경
[제안-043]을 통해 재귀적 로깅 루프는 차단되었으나, 이전에 누적된 방대한 로그나 장기간 축적된 로그를 "전체 로그 완전 초기화" 또는 "30일 이전 로그 정리"로 삭제할 때 여전히 문제가 남아있습니다. 한 번의 쿼리로 수만~수십만 건의 데이터를 `DELETE` 할 경우, SQLite의 배타적 파일 락(Exclusive Lock)이 장시간 유지되어 다른 요청 처리가 지연되고 5초(기본 타임아웃) 경과 시 `OperationalError: database is locked` 장애를 유발할 수 있습니다. 
또한 거대한 페이로드를 단일 요청으로 삭제하는 과정에서 타임아웃 실패가 발생하면 삭제가 롤백되거나 부분적으로 끊길 수 있습니다.

### 1-2. 목적
- 로그 삭제 단위를 사용자가 지정한 **250건 단위의 청크(Chunk)**로 분할하여, 한 번의 트랜잭션이 차지하는 시간을 최소화(수 밀리초 이내)합니다.
- 삭제 작업 중간에 락이 해제되어 백그라운드 워커 등 다른 스레드의 대기 지연을 해소합니다.
- 삭제가 진행되는 동안 사용자 화면(팝업 및 로딩 오버레이)에 실시간 **진행률(%)**을 애니메이션으로 시각화하여 UX를 개선합니다.

---

## 2. 세부 구현 방안

### 2-1. 백엔드 API 수정 (`Staging/Staging_app.py` ➡️ `app.py`)
기존 `/api/access_logs/cleanup` API를 3단계(`step`) 모드로 분할합니다.
- `step='count'`: 조건에 맞는 전체 삭제 대상 건수(`COUNT(*)`)만 반환.
- `step='delete_chunk'`: `LIMIT 250`을 적용한 서브쿼리를 사용하여 정확히 250건씩만 삭제하고 성공 건수를 반환.
  *(예: `DELETE FROM access_logs WHERE LogId IN (SELECT LogId FROM access_logs WHERE ... ORDER BY CreatedAt ASC LIMIT 250)`)*
  *(추가: 삭제 단위가 진행될 때 반드시 가장 오래된 로그부터 순차적으로 파기되도록 `ORDER BY CreatedAt ASC` 를 서브쿼리 내부에 명시합니다.)*
- `step='finish'`: 삭제가 모두 끝난 후, 전달받은 총 삭제 건수(`total_deleted`)를 바탕으로 단 1회의 감사 로그(`log_audit`)를 기록.

### 2-2. 프론트엔드 연동 (`Staging/Staging_access_logs.html` ➡️ `templates/access_logs.html`)
`executeCleanup()` JavaScript 함수를 다음과 같이 개선:
1. `step='count'`로 총량을 파악합니다.
2. `while (deleted < total)` 루프를 돌며 `step='delete_chunk'` API를 반복 호출합니다.
3. 매 반복마다 `(deleted / total) * 100`으로 퍼센트를 계산하여, 삭제 버튼과 `showGlobalLoading()` 텍스트에 진행률(예: `삭제 중... (45%)`)을 갱신 표출합니다.
4. 삭제가 완료되면 `step='finish'`를 호출하고 팝업을 닫으며 목록을 재조회합니다.
