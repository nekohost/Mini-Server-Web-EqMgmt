# [기획서] [제안-043] 접근 로그 API 자기 참조 ResponsePayload 재귀 루프 차단

## 1. 개요 및 배경

### 1-1. 배경
[제안-040]에서 웹 접근 로그에 `RequestPayload` 및 `ResponsePayload`를 원본 그대로 수집하는 기능이 도입되었습니다. 그러나 `@app.after_request` 인터셉터에서 모든 비정적(non-static) 응답의 Body를 제한 없이 추출하여 저장함에 따라, `/api/access_logs` (로그 목록 조회 API)가 호출될 때마다 50건의 로그가 담긴 거대한 JSON 응답 Body(수십~수백 KB)가 다시 `access_logs` 테이블의 `ResponsePayload` 컬럼에 적재되는 **재귀적 자기 참조(Self-Referential) 로깅 루프**가 발생하였습니다.

5초 자동 새로고침과 맞물려 `ResponsePayload` 내부에 이전의 `ResponsePayload`들이 중첩되며 데이터가 기하급수적으로 팽창하였고, 이로 인해:
1. `equipment.db` 파일 급격한 비대화 및 `SELECT` 조회/집계 I/O 지연 ("로그 데이터를 갱신 중입니다..." 무한 대기)
2. `DELETE FROM access_logs` 시 SQLite 단일 파일 배타적 락(Exclusive Lock) 장시간 유지로 인한 동시 요청 교착(Deadlock) 및 삭제 팝업 무한 대기
3. 메모리 과다 사용에 따른 프로세스 비정상 셧다운 현상이 발생하였습니다.

### 1-2. 목적
`@app.after_request` 인터셉터에서 `/api/access_logs` 경로(접근 로그 조회/통계/정리 등)의 응답은 `ResponsePayload` 캡처 대상에서 제외하여, 재귀적 로깅 루프를 원천 차단하고 DB 리소스 및 웹 서비스 응답성을 안정화합니다.

---

## 2. 세부 구현 방안 (방안 A)

### 2-1. 백엔드 인터셉터 수정 (`app.py`)
`@app.after_request` 내부의 `ResponsePayload` 수집 조건식을 다음과 같이 변경:

```python
# [수정 전]
response_payload = None
if not is_static:
    try:
        response_payload = response.get_data(as_text=True)
    except Exception:
        pass

# [수정 후]
response_payload = None
if not is_static and not request.path.startswith('/api/access_logs'):
    try:
        response_payload = response.get_data(as_text=True)
    except Exception:
        pass
```

### 2-2. 영향도 및 의존성 분석
- **긍정적 효과 (Positive)**:
  - `/api/access_logs` 계열 API 응답이 `ResponsePayload`에 적재되지 않으므로 자기 참조 재귀 루프가 100% 차단됨.
  - `access_logs` 테이블 비대화 방지, 쿼리 속도 정상화, 삭제 시 SQLite 파일 락 경합 해소.
  - 일반 업무 API(장비 CRUD, 계정 관리, 권한 관리 등)의 Request/Response Payload는 정상적으로 수집되어 [제안-040]의 원래 취지(트러블슈팅 및 감사)는 완벽히 유지됨.
- **부정적/제약적 효과 (Negative)**:
  - 관리자 접근 로그 조회/통계 API 자체의 응답 JSON은 `ResponsePayload`에 저장되지 않음. (실무적으로 로그 조회 결과를 다시 로그에 남길 필요가 없으므로 시스템 기능 손실 없음)

---

## 3. 개발 및 검증 파이프라인
1. **Phase 1**: 기획서 작성 및 거버넌스(`PROPOSALS.md`, `UNIMPLEMENTED_PROPOSALS.md`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md`) 등록.
2. **Phase 2**: `Staging/Staging_PLAN.md` 및 `Staging/app.py` 생성 후 격리 모의 구현.
3. **Phase 3**: `VALIDATION_METHODOLOGY.md` 8단계 심층 자체 검증 수행 및 보고서 작성.
4. **Phase 4**: 프로덕션 병합, Staging 정리, `FEATURES.md` 갱신, Git 커밋/푸시 및 대화 기록 저장.
