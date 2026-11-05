---
artifact_id: REPORT-20261105-012
work_id: RELEASE-20261105-AI-CSV-LAYOUT
owner: Codex
status: in-progress
---

# AI CSV·화면·모델 접기 운영 반영

현재 사용자 지시는 검증된 Staging 운영 배포이며 신규 상단 아이콘/상태 색상·두 줄 메뉴는 미실현 계획011로 분리한다. recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0과 context32개를 확인했다. 직전 읽은 변경 없는 공통/검증 노드를 승계하고 운영/데이터 보존·보안·완료/제안 원장 노드를 추가 확인했다.

사전 서버는 기존 운영 host/user, local/server HEAD `cb1d72c6abfd4abdb288315138501a9d9a7fe28a`, web PID824644의 정확한 `.venv/bin/python -u app.py`와 일치했다. worker/retention timer active, maintenance NORMAL, AI schema4이며 자체 job은 done15/failed1/cancelled1이고 진행 중0이다. 서버 tracked dirty는 없으며 기존 미완료 가상환경 untracked 폴더는 보존한다. 배포 helper의 local/server SHA가 일치했다. 초기 설치 helper는 사용하지 않는다.

## 사전 Validation1~8

1. 거버넌스: 현재 후보만 병합하고 두 신규 건은 미실현으로 기록한다. 기존 dirty9개·다른 Staging·운영 DB/비밀을 보존한다. 사용자 운영 배포 승인과 해당 소스 정리 범위를 적용한다.
2. 의도: CSV 요청형 팝업·하단 정리, 실제 높이/내부 scrollbar, 기본 접힌 모델 선택을 함께 반영한다.011·web_search·다른 유지보수를 끼워 넣지 않는다.
3. 논리: native details 및 기존 API/CSRF/도구 계약을 보존한다. root 병합은 검토 source 해시와 비교하고 승인 commit만 서버에 적용한다. 기존 진행 job은 정상 종료를 기다리고 중복 실행/강제 취소하지 않는다.
4. 운영 영향: template/JS/CSS/policy4개와 검사 보조7개가 대상이다. app/worker 코드·스키마·Nginx·키·다른 서비스는 바꾸지 않는다. 기존 업그레이드 helper로 정확한 idle web/worker만 정상 전환한다.
5. 보안: private 두 DB·환경·프로세스 설정을 보존하고 비밀/실제 대화 원문은 공개 결과/Git에 출력하지 않는다. 익명/일반 권한과 오류·CSV 명시적 확인을 유지한다. 실제 장비 쓰기로 검증하지 않는다.
6. 복구: 현행 commit/설정/일관 DB 백업을 먼저 보존한다. 무스키마 변경이므로 코드별 복귀가 가능하나 최신 AI 기록/삭제 원장을 과거 DB로 덮지 않는다. 백업·원문·해시를 확인한 뒤만 Staging을 정리한다.
7. UX: 실제 운영 브라우저에서 접힘/펼침·새로고침·모바일/PC 높이를 검증하고 원인이 보이는 오류/팝업을 확인한다. 필요한 로그인은 권한 있는 기존 계정의 정상 흐름으로만 진행한다.
8. 메타: 기존55개 화면/3543개와 이번 운영 검증을 분리한다. PC 요약 행 추가로 약26px 높아지는 기존010 측정도 숨기지 않는다. 실제 확인 전 배포 성공으로 표시하지 않으며 남은 한계를 최종 기록한다.
