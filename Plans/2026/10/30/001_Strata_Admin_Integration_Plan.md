---
work_id: IMPL-20261030-STRATA-ADMIN
created_at: 2026-10-30
owner: Codex
workspace: C:/Project/Mini-Server-Web-EqMgmt
approval_basis: 사용자의 권장 방식 기능 구현 지시
---

# 관리자용 Strata 화면 통합 구현

검토 보고서의 권장안을 구현한다. `/ai` 메뉴 화면과 관리자 전용 iframe을 제공하고, Nginx는 별도 `/strata/` 경로에서 로그인·권한을 확인한 뒤 260으로 스트리밍을 중계한다. 공동 API 키는 Nginx의 비공개 설정에만 두고 브라우저에 전달하지 않는다.

Staging 후보는 `Staging/Strata_Integration_20261030/overlay/`에 작성한다. 기존 `app.py`는 직접 변경하지 않고, 원본 해시와 정확히 일치하는 문자열 교체 목록을 제공한다. 운영 소스 병합은 프로젝트 절차에 따른 검증 결과 승인 후 수행한다. Windows에서는 애플리케이션·동작 테스트를 실행하지 않는다.

구성은 메뉴 등록과 서버 권한·CSRF·Origin 검사 모듈, 원본 Strata UI의 고정된 텍스트 자원과 MIT 라이선스, iframe용 인증·저장소 어댑터, 상태·오류 안내 화면, Nginx 설정 예시, Linux 격리 테스트와 배포 안내로 나눈다. 기존 라이브러리 Flask·requests와 현재 Nginx를 재사용한다.

기능은 `STRATA_ENABLED`로 제어하며 기본 비활성이다. 관리자만 메뉴를 사용한다. 로그아웃·계정 전환 시 이전 세션의 Strata 브라우저 이력이 노출되지 않도록 별도 저장소 공간을 사용한다. 일반 사용자에게 전체 UI를 공개하거나 모델·Strata 서비스를 재설치하지 않는다.

운영 서버 접속은 현재 SSH 호스트 키를 검증할 수 없어 진행하지 않았다. 구현 후보와 정적 결과를 먼저 완성하고, 신뢰할 수 있는 Linux 서버 연결이 준비되면 격리 동작 테스트와 Nginx 설정 검사를 수행한다. 단일 worker Flask가 장시간 AI 스트림을 직접 전송하지 않도록 한다.
