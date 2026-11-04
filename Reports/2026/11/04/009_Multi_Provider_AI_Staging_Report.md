---
artifact_id: REPORT-20261104-009
created_at: 2026-11-04
owner: Codex
status: completed-staging
related_artifacts: [PLAN-20261104-006, PLAN-20261104-009, TASK-20261104-009, REPORT-20261104-008]
---

# 다중 프로바이더 AI Staging 구현 기록

## 사전 Validation (순차)

1. **거버넌스:** recorder 정상, validate 1.8.1/44 nodes/0 errors, context 전체 적용. legacy reason=runtime-session-mismatch. Staging 한정 사용자 승인이 확인되었다. 표준 암호화 추가는 006 명세에 포함되며 보호된 env 참조 대안도 유지한다.
2. **사용자 의도:** 다중 LAN provider, 관리자 기본 연결 관리, 자동 발견/선택 기본, 선택형 수동 등록, 같은 세션 모델 전환/복원, 내부 그룹 큐만 구현한다. 고급 설정·일괄 주석 보완은 제외한다.
3. **논리:** 현재 전역 unique index/순차 worker와 claim 준비 예외가 확장의 차단점이다. 별도 v3 migration, DB 슬롯, dispatcher, 불변 요청 스냅샷, 준비 실패 종결과 ACK offset으로 해소한다. 네트워크 동안 writer를 보유하지 않는다.
4. **운영 영향:** 기존 004/005/008 산출물은 역사 기록이다. 현재 overlay만 갱신하고 운영 root는 보존한다. 서버/worker/DB v3 동시 배포, feature flags, 비밀 key/allowlist가 필요하다. 이번에 실제 배포하지 않는다.
5. **보안:** 실제 관리자 재검사, CSRF/Origin, owner predicate, 암호화 key 분리, 고정 API 경로/접속 IP 검증, redirect/proxy 차단과 기존 일반 사용자 도구 allowlist를 적용한다. 감사에서 업무 내용은 유지하고 재사용 credential 원문만 보호한다.
6. **복구:** additive schema/history/미종료 잠금 보존. 여러 active job 뒤 v2 글로벌 index 복귀는 안전하지 않으므로 drain+검증된 일관 백업 또는 v3 호환 롤백을 요구한다. 삭제/down migration은 하지 않는다.
7. **UX:** 현재 선택/다음 요청 적용/대화 전용/목록 장애/재선택 사유를 보여주고, 오류/중단 원인을 보존한다. 모델 변경이 카드 확인이나 기존 요청 재발신을 유발하지 않는다.
8. **메타:** Codex의 승인된 Staging 구현이며 실제 서버 검증과 합성 결과를 구분한다. 원본 Gemini의 잘못된 세부 주장은 복제하지 않는다. 68/45 기존 시험은 신규 기능 통과 근거로 재사용하지 않는다.

사전 검토의 차단점은 구현 대상 결함으로 특정했으며, 미승인 운영 조치나 추가 사용자 결정은 없다. 아래 후속 검증에는 실제 새 결과만 기록한다.

## 구현 및 후속 검증

수정 범위는 기존 Staging overlay, 이 후보의 README/설치 안내, 009 Plan/Task/Report와 새 검증 manifest다. 운영 root·DB·서버 소스/환경/서비스·Git에는 반영하지 않았다. 원본 Gemini 005 Plan/Task/Report와 007 비교 보고서, 운영 `app.py`, `utils/lineup_node_service.py`의 기존 6개 SHA-256이 그대로다. 기존 dirty 9개도 유지했다.

| 구현 영역 | 실제 결과 |
| --- | --- |
| 관리자 `/admin/ai/providers` | 실제 DB admin Role+전용 메뉴+서명 세션+CSRF/Origin. 복수 기본 연결, 활성/폐기, 물리 그룹, API 키 교체, 모델 공개/별칭/기본값/공개 순서·검증한 context. 기존 화면과 독립적인 전용 UI. |
| 모델 발견/기능 | 자동 목록 조회·60초 cache 기본. 수동 ID는 관리자 opt-in. 목록/적재/검증을 구분하고 nonce 대화·무해한 구조화 도구·Strata 추론 출력 시험을 내부 그룹 큐로 처리. embedding/TTS 등 알려진 비대화 유형 제외. 일반 호환 API는 대화/도구 adapter, native Ollama는 구현하지 않음. |
| 키/네트워크 | 별도 외부 Fernet primary/previous-key ring, 원문 readback 없음. 서버 host/IP/CIDR+port 허용 목록, DNS 결과 재검사와 실제 socket pinning, TLS hostname/인증서 검증, 고정 `/v1/models`·`/v1/chat/completions`. redirect/proxy/userinfo/임의 관리 경로 차단. Strata 전용 옵션은 Strata에만 사용. |
| 대화/작업 | 세션별 provider/model/추론 복원, unavailable 사유·재선택. 새 대화 자동 선택. 요청 수락 시 연결/기능 revision·자원 그룹·실제 추론을 고정하고 모든 tool round에 유지. 변경은 다음 요청부터, 답변 출처는 과거 스냅샷 유지. 선택 기록 없는 구 대화가 다른 대화의 모델을 이어받지 않도록 분리. |
| 업무 인계 | 원문 message ID/필드별 출처·revision·미입력 항목을 가진 미확정 장비/카탈로그·옵션/기존 일반 사용자 업무 초안. 서버 영수증·미확정 카드·최근 최종 대화·한도 내 출처 발췌. 내부 추론/비밀/미해결 tool ID 제외. 모델 변경은 카드 실행이 아니며 내용 변경은 명시적 supersede. |
| 그룹 큐 | AI DB v3의 jobs 그룹/현재 lease가 authoritative slot이며 partial unique index로 그룹당 1개. 같은 그룹은 직렬, 독립 그룹은 실제 bounded dispatcher 병행. 사용자 교대/FIFO fallback와 도구 후속 재진입. 같은 계정의 열린 작업/속도/문자 제한 합산. 종료 불명확 잠금은 해당 그룹과 대화에 유지. 외부 서비스 요청/idle/취소/load/unload 제어 없음. |
| 저장/이전 | AI DB만 v1/v2→v3 가산. 과거 모델 추정 금지. 실제 route 없는 구 queued는 발신 전 실패, active/unknown은 종료 확인 잠금 보존. 불완전 v3/누락 slot index·protocol mismatch fail-closed. 외부 DB epoch로 복원 후 옛 callback 차단. |

저장 기준선 32,000,000자와 기본 추가 32,000,000자는 유지한다. 기존 응답/영수증 426,144자에 초안/출처 16,384자와 저장 인계 요약 16,384자를 더해 **458,912자/turn**을 예약한다. 요약/초안은 실제 사용량에 포함하고 후속 단계/동일 전송을 중복 계산하지 않는다. 원장을 다시 만들 때도 메시지+초안+요약을 복구한다. CSV 감사 원문은 논리 문자 원장과 별도인 기본 2GiB 보호 예산이며, 부족하면 내보내기 성공 전에 거부한다.

| Gemini 선행 항목 | 조치와 검증 경계 |
| --- | --- |
| S01 | 실제 전역 로그 훅이 AI binary/multipart를 재소비하지 않도록 분기. 검증 파일 metadata/hash, JSON 업무 내용과 거부 사유, CSV 보호 원문·참조/해시/행 수·주체/범위 보관. body capture 실패도 metadata push까지 진행. 원래 전역 access-log queue의 fail-open/점검 중 수집 중지 정책 전체를 교체하거나 트랜잭션 무손실을 보장했다고 주장하지 않음. |
| S02 | 전역 maintenance gate에 고정 POST event/finish+loopback worker 인증+현재 lease만 통과하는 cleanup 계약. 신규 claim/모델 호출/업무 DB 접근 차단. 시험에서 기존 cleanup 전후 equipment connection 수가 증가하지 않음을 확인. AI DB 자체 교체는 quiesce+백업+외부 epoch 절차로 분리. |
| S03 | claim 이후 actor/tools/context/연결·키·목적지/응답 packet 준비 전체 예외 안전망. 알려진 발신 전 실패는 카드/예약/슬롯 정리·사유 보관. 미확인 외부 실행과 구분하며 재발신/lease 탈취 없음. |
| S04 | 최초 error/error_code 보존, 실제 권한 차단은 계속 적용. 조각 수락 여부와 서버 ACK offset 반환. worker가 거절한 조각을 저장했다고 가정하거나 취소 뒤 일반 조각을 계속 보내지 않고 자체 응답 drain/heartbeat/최종 보고만 유지. |

## 후속 Validation (순차)

1. **거버넌스 준수성:** Staging 격리/Task→Plan→사전 1~8→구현을 지켰다. 원본 평가·운영 소스 보존을 SHA로 확인했다. 표준 암호화 의존성은 006 승인 범위이며 임시 Linux test dependency에만 설치했다. 일반 파일 편집은 구조화 patch로 수행했다. legacy reason은 runtime-session-mismatch이며 별도 모델 인증을 주장하지 않는다. 차단: 운영 병합은 이번 승인 범위 밖이다.
2. **사용자 의도:** 독립 대화 UI와 복수 LAN provider, 자동 기본/선택형 수동 모델, 같은 세션 이어가기/복원, 일반 사용자 업무만, 장비 삭제 불가, 자체 요청 그룹 큐를 대조했다. 고급 endpoint customization과 D07/KO 감사는 보류 상태를 유지했다. 모델의 일반 질문 응답 경로는 대화 전용 모델에서도 유지한다.
3. **논리/예외:** 같은 그룹 직렬·다른 그룹 병행·unknown 격리·사용자 교대·tool requeue·멱등 충돌·선택 revision·키/준비 fault·ACK 거절·최초 오류·초안/요약 원장/예약을 교차 검사했다. 실제 두 가짜 HTTP 모델 서버의 barrier로 worker 병행을 검증했다. 마지막 대조에서 인계 요약의 영속 저장도 문자 원장/완료 예약에 포함하도록 보완했고 해당 원장 재생성 회귀를 추가했다. 모델 대기 동안 DB writer를 유지하지 않는다.
4. **운영 영향:** backend 테스트는 local candidate AST의 실제 auth/maintenance/audit hook와 임시 업무/AI DB를 사용했다. 전체 운영 app.py import/서비스 기동은 하지 않았다. browser fixture도 배포 서버의 공통 frame에 의존하지 않게 현재 로컬 frame/static 원문을 pack해 검사한다. 서버/worker/DB v3 동시 적용과 설정 준비가 필요하며 시험에서 실제 배포하지 않았다.
5. **보안/엣지:** admin spoof/CSRF·Origin/다른 owner/미제공 도구/초안 owner·Role 주입/대화 전용 도구 시도, 키 비노출·교체, SSRF·포트·DNS 재바인딩·redirect·proxy, 잘못된 stream/회수된 권한을 검사했다. model/provider HTML은 text로 렌더링된다. 재사용 key/lease는 지문 보호하고 업무 내용은 감사 대상이다. 실제 HTTP LAN 암호화 및 운영망 배치는 별도 확인 사항이다.
6. **복구:** 가산 이전과 unknown lock·원문 보존, 외부 epoch 변경 후 old lease 거절, 구 route 추정 금지, 부분 schema fail-closed를 확인했다. v3에 다중 active가 생긴 뒤 v2 코드만 복귀하는 방법은 허용하지 않는다. drain 후 v3 호환 코드 또는 검증된 일관 백업/코드/키·epoch를 함께 복원한다. 실제 복구 훈련은 운영 반영 전 별도 검증한다.
7. **UX/실수:** 사용자/관리자 desktop 1440px·mobile 430px DOM을 검사하고 화면을 시각 확인했다. 추론 자동 접힘/재열기, 과거 페이지, 실제 결과 표시, 모델별 지원값/대화 전용·중단 사유, 답변 출처·다음 요청 변경, optional manual·키 readback 없음·soft retire와 no-overflow를 확인했다. 구 선택 없는 대화는 다른 대화의 모델을 복제하지 않고 다음 기본 선택임을 설명한다.
8. **메타/근거:** 실제 Linux 실행 결과·정적 검사·원본 hash와 합성/실서버 미검증 범위를 분리한다. 기존 004의 68/45 결과를 신규 통과로 전용하지 않는다. 이번 결과는 별도 manifest로 재현 경로/소스 SHA와 함께 보존한다. Gemini 원문의 잘못된 함수명/Unicode 원인 설명을 그대로 구현 근거로 복제하지 않았다. 기존 주석 일괄 보완과 KO 번역을 대신 수행하지 않았다.

## 최종 실행 근거

| 검사 | 실제 결과 |
| --- | --- |
| Linux backend | **106개 통과, 실패 0, 오류 0, skip 0. 210.945초.** 기존 68개와 확장/회귀 38개를 같은 최종 실행에서 검증. Python 3.12.3, eqmgmt-backup의 기존 venv + 임시 cryptography dependency. |
| 실제 Chromium DOM | **83개 통과.** 사용자 1440px 30개/430px 31개, 관리자 1440px 11개/430px 11개. 현재 로컬 root/miniserver frame과 공통 static도 함께 pack. 외부 CDN을 차단한 합성 UI이며 네 화면을 시각 검토. |
| 정적 검사 | overlay Python **14개 AST parse**, JavaScript **3개 node --check** 통과. Windows에서는 앱/행동 시험을 실행하지 않음. |
| 정책 검사 | governance 1.8.1, 44 nodes, errors/warnings 0. recorder preflight 정상. |
| 보존/재현 | 운영 app.py SHA `6244893711252F6C78BF36C53CC010BBB485E22C773EBFF038D8F7D3EEE8A581` 및 005 원본 등 6개 동일. 후보 source/guide 25개와 공통 fixture base의 SHA-256을 별도 JSON에 기록. |

최종 기능 시험 후 새 핵심 함수에 한정해 Comment ID/EN metadata를 붙였다. 해당 4개 Python 모듈은 docstring을 제외한 AST digest가 시험 시점과 일치함을 확인했다. 이후 Python AST/JS syntax와 source hashes를 다시 확인했으며 기존 D07 일괄 보완/KO 동기화는 수행하지 않았다.

재현 명령은 `python Staging/20261104-user-ai-assistant/overlay/tests/run_assistant_fixture.py --browser`다. 소스만 로컬에서 pack해 SSH stdin으로 전달하며 운영 app import/DB open은 모두 false다. 실제 실행 수치/각 browser check 이름/소스 SHA/공통 base와 한계는 `Reports/2026/11/04/multi-provider-ai-validation.json`에 보존한다. 이 시간은 합성 기능 시험 시간이며 실제 모델 생성 속도·품질 수치가 아니다.

## 실제 적용 전 남은 확인

- 실제 두 PC/기타 LAN 서버의 허용 주소·키·API 규약/현재 모델·context 한도와 도구/추론 호환·장비 질문 품질은 운영 연결에서 검증해야 한다. 이번에는 가짜 모델 HTTP/SSE와 합성 DB만 사용했다.
- 현재 지원은 Strata와 OpenAI 호환 Chat Completions다. native Ollama, 임의 헤더/body/template/API mode UI는 포함하지 않는다.
- 실제 운영 전체 앱 기동·장비 DB 복구 훈련·대용량/장기 부하·운영 로그인/실모델 생성은 수행하지 않았다. 65K 장문 성능이나 모델 일반 지능을 검증한 결과가 아니다.
- 로컬 모델 매니저의 바인딩/방화벽, 다른 서비스의 큐/세션/프로세스는 바꾸지 않았다. 새 메뉴/스키마/설정/worker의 실제 활성화도 후속 운영 범위다.
- 최종 설치/원문 보존·키 분리/회전·epoch/롤백 절차는 `Staging/20261104-user-ai-assistant/MULTI-PROVIDER-SETUP.md`에 명시했다. 미해결 Staging 코드 결함이 아니라 실환경 적용 전의 검증 경계와 사용자 보류 사항이다.
