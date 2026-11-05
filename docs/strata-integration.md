# 장비관리의 기존 Strata 웹 화면 폐기 후보

이 문서는 `STAGING-20261105-AI-UX-TRASH`의 Staging 후보다. 실제 운영 코드·DB·Nginx·서비스·API 키를 변경하거나 제거한 기록이 아니다. 승인 Plan은 `Plans/2026/11/05/001_AI_Assistant_UX_and_Strata_Retirement_Plan.md`이며 정확한 제거 whitelist는 `docs/strata-retirement-manifest.json`에 둔다.

기존 `/ai`와 `/ai/console`은 현재 로그인 검사를 거쳐 폐기 안내와 `/assistant` 링크를 제공한다. 브라우저 iframe·bridge·health 호출을 로드하지 않는다. 이전 POST를 새 AI 대화로 변환하지 않고 `eqmgmt.strata.*` localStorage를 삭제하거나 병합하지 않는다. 메뉴 코드 `strata`는 관리자/일반 사용자 목록에서 항상 숨기며 기존 메뉴·grant 행은 보존한다. `STRATA_ENABLED=true`가 남아 있어도 gateway가 다시 열리지 않는다.

`/strata`, `/strata/*`, `/api/strata/*`, `/_eqmgmt_strata_auth`와 전용 static 자산은 410 또는 404로 종료한다. Flask의 차단은 앱 fallback용이다. 실제 정적 파일을 직접 제공하는 Nginx에도 승인된 deny location이 필요하다. `systemd/nginx-strata.conf.example`은 해당 장비관리 HTTPS server에서만 기존 전용 snippet을 교체할 후보이며, `proxy_pass`, `auth_request`, 비밀 include를 사용하지 않는다.

## 보존 범위

- 신규 `/assistant`, `/admin/ai/providers`, `utils/ai_assistant`의 Strata adapter·모델 조회·worker·자원 그룹 큐를 보존한다.
- `USER_AI_STRATA_URL/KEY`, 독립 provider 암호화 키, worker token, allowlist, database epoch와 모든 기존 대화/초안/감사/업무 데이터를 보존한다.
- LAN Strata와 다른 서비스·사이트의 proxy, 키, 모델 프로세스를 변경하지 않는다.
- `/etc/nginx/private/strata-upstream-key.conf`는 공개 UI 자산이 아니다. 이번 절차에서 읽기·삭제·회전하지 않는다. 필요 시 운영자의 별도 키 수명주기 절차로만 관리한다.
- Git 이력 및 vendor의 README·MIT LICENSE·OFL 고지는 보존한다. 공개 static에서는 전체 vendor namespace를 차단해 고지를 포함한 옛 UI를 다시 실행하는 경로가 없게 한다.

## 신규 AI bootstrap의 키 입력

`tools/deploy_user_ai.py prepare-key`는 옛 Nginx include를 읽지 않는다. 이미 존재하는 서비스 계정 소유 0700 디렉터리/0600 `assistant-worker.env`는 그대로 보존하며 입력 키 파일을 열지 않는다. 기존 값을 재생성하거나 provider/API 키를 회전하지 않는다.

처음 준비하는 경우에만 운영자가 가진 **기존 API 키**의 절대 경로 `--key-file`을 명시한다. 입력은 root 또는 서비스 계정 소유의 0600 일반 파일, owner-only 디렉터리, symlink 없는 경로여야 한다. 입력 파일은 한 줄의 평문 키이며 Nginx directive/include 파일을 지정하지 않는다. 값은 인수·대화·로그에 넣지 않는다.

```bash
# Linux, 승인된 exact commit/운영 절차에서만 실행한다. 이 문서 작성 중에는 실행하지 않았다.
sudo python3 tools/deploy_user_ai.py prepare-key --commit <승인된-40자리-commit> \
  --key-file /운영자가/관리하는/비공개/strata-key.txt
```

기존 설정이 있으면 `--key-file` 없이 같은 action을 호출할 수 있다. 이 action은 기존 private 환경을 교체하지 않으므로 현재 운영 중인 환경·allowlist·키를 보존해 후속 승인된 검증에 사용한다. 옛 `tools/deploy_strata.py`와 `tools/write_strata_nginx_key.py`는 비활성 안내와 비정상 종료만 제공하며 재설치/키 쓰기를 수행하지 않는다. 기존 설치의 Git 이력은 그대로 남는다.

## 운영 적용 전 순서

1. 새 assistant의 표·일반 조회·모델 선택·관리자 저장/시험과 내부 worker 회귀를 통과한다. v4 lifecycle/점유 원장 이전과 호환 복귀 조건도 통합 검증한다.
2. 관련 환경·Nginx site/snippet·원본 메뉴/grant 행을 보호된 백업에 보존한다. 실제 DB 백업·참조 검토는 별도 승인 범위에서만 수행한다.
3. 옛 화면에서 실제 진행 중인 자기 요청의 정상 종료를 확인한다. 오래 걸린다는 이유로 공유 Strata의 전역 취소/unload/초기화를 수행하지 않는다.
4. 신규 AI가 기존 private `USER_AI_*` 설정으로 동작하고 bootstrap에 Nginx key 파일 의존성이 없는지 확인한다. UI 폐기와 키 회전을 묶지 않는다.
5. 앱 후보와 관리자 메뉴 metadata 이전을 검토·병합한다. `equipment_ai_settings`의 URL/code/name/order/grant를 보존한 채 부모만 `admin_center`로 멱등 이전한다.
6. 해당 HTTPS server의 전용 snippet만 deny 후보로 교체한다. 다른 사이트/global proxy 설정은 수정하지 않는다. `sudo nginx -t` 통과 후 승인된 reload를 수행한다. 비밀 값이 나올 수 있는 `nginx -T` 출력을 보고서에 붙이지 않는다.
7. 익명/일반/관리자의 모든 옛 proxy·auth·health·static GET/POST가 404/410인지 확인한다. 옛 auth location의 2xx를 허용하지 않는다. 새 assistant·모델 조회·worker와 다른 서비스 Strata 사용을 다시 확인한다.
8. 차단 확인 후 manifest의 정확한 `remove_public_files_after_denial` 목록만 배포에서 회수한다. glob/상위 디렉터리 재귀 삭제를 하지 않는다. Git/검토 아카이브와 라이선스 고지는 유지한다. 이 Staging 작업은 실제 원본 파일을 삭제하지 않는다.
9. 기존 메뉴·grant 행의 최종 삭제가 필요하면 FK/참조/정확한 행/원래 metadata 복구를 별도 확인한다. 현재 후보는 행 삭제나 grant 변경을 수행하지 않는다.
10. 옛 `STRATA_*` 환경 변수는 사용처가 더 없음을 확인한 뒤 운영 절차에서만 정리한다. `USER_AI_*`는 유지한다.

## 관리자 연결 화면의 결과 처리

모든 저장·연결 폐기·수동 모델 등록·모델 설정·자동 조회·명시적 목록 갱신은 기존 `showGlobalLoading()/hideGlobalLoading()`을 재사용한다. 처리 중 입력과 연결 전환을 잠그며 완료 후 native dialog로 결과를 알린다. 결과 dialog와 기능시험 상태는 화면 하단·키보드에서도 인식할 수 있다.

저장 완료 ACK 후 GET 실패는 “완료 · 목록 갱신 실패”다. POST 응답 유실이나 5xx는 “결과 확인 필요”다. 둘을 입력 검증 실패/409와 구분한다. 현재 ID/revision/폐기 상태 또는 수동 모델 ID를 GET으로 확인하고 사용자가 목록을 불러올 때까지 입력을 보존한다. 목록은 키 존재만 알려주므로 비밀 키 값의 일치를 확인했다고 주장하지 않는다. **연결 생성/모델 저장에는 서버 operation receipt가 없으므로 GET 목록만으로 특정 POST의 원자적 완료를 증명할 수 없다.** 자동 재전송·자동 재생성은 하지 않는다. 확인 상태 해제는 사용자의 명시적 선택으로 현재 목록만 다시 읽으며 이전 POST를 보내지 않는다.

기능시험은 기존 client_key 멱등 접수와 `GET /api/admin/ai/probes?client_key=...`를 이용한다. 접수 ACK 뒤 overlay는 즉시 닫는다. `done`만 성공이며 실패·취소·종료 확인 필요를 구분한다. 상태 조회 실패는 시험 실패가 아니고 보관한 job ID로 조회를 재개한다. 짧은 HTTP 관리 요청에는 30초 응답 대기를 두어 유실을 표시하지만, 모델 실행의 총시간 취소나 shared queue 초기화를 추가하지 않는다. 페이지 이탈/모달 닫기/화면 상태 추적 종료도 공유 모델을 취소하지 않는다.

## 검증과 복귀

Windows에서는 AST/Jinja parse와 `node --check`만 허용한다. 앱 import/기동/행동 테스트를 실행하지 않는다. Linux 격리 fixture에서 실제 로그인 함수·관리자 메뉴·seed 멱등성·옛 경로/정적 차단·보호 키 입력과 관리 UX를 검증한다. 테스트에는 실제 DB/로그인/키/모델 서버를 사용하지 않는다.

복귀는 보호한 개별 코드·설정·metadata 사본을 검토해 원래 값을 되돌리는 절차다. DB 전체를 과거 사본으로 덮어쓰거나 신규 AI 기록·업무·감사를 삭제하지 않는다. UI rollback과 v4 lifecycle rollback을 구분하며 v3 코드를 바로 기동하지 않는다. 실제 영구삭제한 대화를 기능 rollback으로 복구할 수 있다고 안내하지 않는다.
