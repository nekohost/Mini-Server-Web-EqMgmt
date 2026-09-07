# app.py 인코딩·문법 복구 검증 보고서

## 결론

`app.py` 376행의 미완성 UTF-8 바이트와 `init_db()` docstring 종료 누락을 복구했다. 이어서 714행 이후에 잘못 삽입된 접근 로그 메뉴 마이그레이션 중복 파편 180행을 제거했다. 정상 SQL, 스키마, 라우트, DB 데이터는 변경하지 않는다.

## 1~8단계 검증

1. 거버넌스: Staging 복구 초안과 영구 계획을 먼저 만들고, 활성 거버넌스 검증이 오류·경고 0건으로 통과했다.
2. 사용자 의도: 로컬 기동 없이 Git Push 후 미니서버에서 확인하는 배포 흐름을 유지한다.
3. 정적 논리: 원시 바이트 검사에서 손상 위치는 376행의 1개였고, 복구 후 전체 파일은 유효한 UTF-8이다. `proposal_036_access_logs` 호출은 1개만 남으며 바로 다음에 `migrate_access_logs_payload()`가 선언된다. Windows에는 Python 인터프리터가 없어 Python 문법 검사는 미니서버에서 수행한다.
4. 운영 영향: 애플리케이션 동작·라우트·DB 정의는 변경하지 않는다. 서버에는 Git Pull 후 반영된다.
5. 보안: 인증·권한·입력 처리에 변경이 없다.
6. 롤백: Git 커밋 되돌리기와 `Staging/app.py.pre-encoding-repair.bak` 원본 백업을 사용할 수 있다.
7. 휴먼 에러: 미니서버에서는 `python3 -m py_compile app.py`를 먼저 실행해 기동 전 문법 실패를 차단한다.
8. AI 메타: `.vscode/`와 Staging 산출물은 커밋·푸시 대상에서 제외한다.

## 배포 후 필수 확인

```bash
git pull origin main
python3 -m py_compile app.py && python3 app.py
```

`py_compile`이 실패하면 서버 기동을 중단하고 해당 출력으로 후속 진단한다.
