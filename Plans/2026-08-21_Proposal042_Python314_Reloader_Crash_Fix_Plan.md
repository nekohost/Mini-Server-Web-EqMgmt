# [기획서] [제안-042] Python 3.14 런타임 안정화 및 Reloader 세마포어 크래시 방어

## 1. 개요 및 배경
- **배경**: Python 3.14 런타임 환경에서 Flask/Werkzeug 개발 서버를 `python3 app.py`로 직접 구동 시, Werkzeug Auto-Reloader가 자식 프로세스를 분기/추적하는 과정에서 POSIX 세마포어 추적 오류(`multiprocessing/resource_tracker.py: UserWarning: resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown: {'/mp-...}`)가 발생하며 서비스가 시작 직후 무음 크래시(Silent Exit)되는 현상이 발생함.
- **목적**:
  1. `app.run()` 구동 시 `use_reloader=False`를 명시하여 Werkzeug의 불필요한 자식 프로세스 생성을 원천 차단하고 단일 프로세스로 안정 구동.
  2. 서버 구동 진입점(`if __name__ == '__main__':`)에 `try...except` 및 `traceback.print_exc()` 방어 블록을 적용하여 포트 충돌이나 소켓 바인딩 실패 시 원인 로그를 콘솔에 100% 명확히 출력.

---

## 2. 변경 대상 및 세부 구현 내용

### 1) 백엔드 서버 진입점 개선 ([app.py](file:///d:/Project/Mini-Server-Web-EqMgmt/app.py))
- 최하단 `if __name__ == '__main__':` 블록 수정:
```python
if __name__ == '__main__':
    try:
        # .env 파일에서 FLASK_DEBUG 값을 가져와 True/False로 변환
        is_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        print(f"[Server Startup] Starting Flask on http://0.0.0.0:5000 (debug={is_debug}, reloader=False)...")
        # [Python 3.14 안정화] use_reloader=False 명시로 서브프로세스 IPC 세마포어 누수 및 크래시 원천 방어
        app.run(host='0.0.0.0', port=5000, debug=is_debug, use_reloader=False)
    except Exception as e:
        import traceback
        print(f"[Server Fatal Error] Failed to start server: {e}")
        traceback.print_exc()
```

---

## 3. 영향도 및 기술적 고려사항
- **긍정적 영향**:
  - Python 3.14의 서브프로세스 세마포어 추적 충돌이 원천 차단되어 단일 프로세스로 안정 구동됨.
  - 포트 점유 충돌(`Address already in use`)이나 권한 문제 발생 시 원인 Traceback이 콘솔에 즉시 출력되어 트러블슈팅 용이.
  - DB 스키마나 라우팅 변경이 없으므로 데이터 무결성 100% 보존 및 사이드이펙트 0%.
- **부정적 영향 / 고려사항**:
  - 개발 시 코드 수정 후 서버 자동 재시작이 동작하지 않으므로, 수동으로 `python3 app.py`를 재실행해야 함 (운영 환경 표준 동작).

---

## 4. 진행 단계 (Phases)
- **Phase 1**: 기획서 작성 및 거버넌스(`PROPOSALS.md`, `UNIMPLEMENTED_PROPOSALS.md`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md`) 등록
- **Phase 2**: `Staging/` 디렉토리에 격리 모의 구현 (`Staging/Staging_PLAN.md`, `Staging/app.py`)
- **Phase 3**: `VALIDATION_METHODOLOGY.md` 8단계 자체 검증 및 검증 보고서 작성
- **Phase 4**: 사용자 승인 후 프로덕션 병합 및 원격 배포
