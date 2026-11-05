---
artifact_id: REPORT-20261106-002
work_id: RELEASE-20261106-AI-RESPONSE-RECOVERY
owner: Codex
status: completed
approval: explicit-remediation-through-production
---

# 응답 누락 보정 구현·운영 검증

진단001의 최신 요청(11.804초, complete/calls0/content0/reasoning741)을 재실행하지 않고 향후 정상 종료 응답의 복구 절차를 보완한다. 사용자는 조치방안부터 운영 반영까지 명시 승인했다. 현재 기준 HEAD는1d711824000c049586603ebc18285a412abf03fa다.

## 구현 전 Validation1~8

1. 거버넌스: Recorder ensure 성공/watcher11268, legacy/runtime-session-mismatch(verified=false),1.8.1 validate44노드 오류/경고0, context29노드/3pack/필수 입력0과 EN 주석 계약을 확인했다. 이전에 읽은 동일24개와 새5개 노드를 대조했다. 기존9개 dirty/과거 untracked와 진단001을 보존하고 Staging부터 작성한다.
2. 의도: 모델이 정상 종료했으나 필수 판단/답변이 빠진 경로를 보정한다. 사용자 질문 재실행이나 모든 공급자 오류의 무조건 성공으로 확대하지 않는다.
3. 논리: 각 단계별1회 보정·동일 job·새 lease·서버 system 상태·총6단계 제한을 사용한다. 실제 완료 이후에만 다음 모델 단계를 만들고 답변 보정에는 도구를 제공하지 않아 재실행을 막는다. 기존 감사/추론 step 원문·예약을 보존한다.
4. 운영: schema/추가 의존성 없이 기존 context/큐를 사용한다. 실제 기동은 Linux에서만 하고 현재 두 DB 사본/구 행·키·단위를 검증한다. idle 자체 web/worker만 교체한다.
5. 보안: 소유자/세션/CSRF/lease·도구 schema·검색 privacy/총2회·취소/휴지통을 재검사한다. 사용자 텍스트가 system 보정 상태가 되지 않게 하고 새 종료 로그는 고정 필드만 남긴다.
6. 복구: 전후 source/SHA·원문과 현재 서버/PC private 백업을 확보한다. 이전 코드/최신 DB로 복귀할 수 있게 하고 구 실패를 고치거나 guard를 임의 해제하지 않는다.
7. UX: 보정 중에도 현재 추론/진행 표시를 유지하며 최종 답변은 기존 화면에 제공한다. 보정 소진 시 명시적 오류와 정상 잠금 해제를 확인한다. 실제 일반 계정 xhigh 비교 질문으로 운영 검증한다.
8. 메타: 새 하위 에이전트는 사용하지 않고 부모가 통합한다. 무제한 자동 반복·미확인 실행 재전송을 도입하지 않는다. 자동 보정과 실제 모델 성공·한계를 분리해 기록한다.

## 구현과 Staging 검증

recovery.py는 정확한 서버 system 메시지만 보정 상태로 인정하고 같은 phase를 한 번만 추가한다. 기존 build_context가 새 질문마다 user/assistant 원문과 bounded 인계 자료로 재구성하므로 이전 요청의 system 상태가 전이되지 않는 것도 실제 API로 검사했다. 보정 후 답변에는 tools를 제공하지 않고 서버도 위조된 새 도구 호출을 실행 전에 거부한다. schema/프로토콜/추가 패키지·타임아웃·추론 설정을 변경하지 않았다.

표적 검사 최초48개 중1개가 실패했다. 새 테스트가 기존 FakeSearch.failure에 오류 코드 문자열 대신 WebSearchError 객체를 넣은 fixture 사용 오류였다. fixture 입력을 올바른 코드 문자열로 고쳤고 생산 코드의 실제 오류 매핑은 바꾸지 않았다. 이후 전체284개가54.143초·실패/오류/skip0으로 통과했다. [검사 증거](002_AI_Response_Recovery/backend-verification.json).

특히 실제 SSE→worker→Flask API→Store→검색 Domain을 통과하는 합성4단계는 추론741자/호출0 완료→필수 판단 보정/실제 검색1회→추론만인 빈 답변→도구 없는 답변 보정/최종 내용 저장을 같은 job에서 수행했다. 전 단계 xhigh를 유지하고 출처/예약/guard를 검증했다. 다른 회귀는 보정 소진·false 검색0회·민감 검색 차단·실제 검색 실패·취소/휴지통 전후 경합·로그아웃·stale lease·총6단계 한도·원문 추론 보존·모델 텍스트의 system 권한 위조를 검사한다. 이는 실제 외부 모델을 호출한 결과와 구분한다.

검토한 원문8개를 reviewed-source.zip에 보존했다(SHA256 5c12cd3619fedce2682f37f6484997f0385eb270fe027c5218f54042a91403ad). root 패치 생성 시 코드 문자열 안의 줄바꿈 escape까지 치환하는 오류로 테스트 파일의 적용이 거부됐다. 패치 생성기를 정정한 뒤 root8개 모두 원문 SHA와 일치하고 AST가 통과함을 확인했다. root 전체284개도53.965초·실패/오류/skip0으로 통과했다. ZIP/manifest와 일치하는 이번 후보8개만 정리했고 다른 Staging은 삭제하지 않았다. [root 검사](002_AI_Response_Recovery/root-verification.json),[병합·정리](002_AI_Response_Recovery/merge-and-cleanup.json). 이 시점에 운영 서버에는 아직 반영하지 않았다.

## 운영 배포

런타임 commit65b125a4e55c8d0a15be80ee22586e68c4e52509를2026-11-06 07:47:51 KST에 활성화했다. 직전 source/환경·설정/세 단위/프로세스/두 DB를 private release `20261105-ai-ux-response-20261105T224642-21cad2`에 보존했다. 디렉터리는 기존 검증된 helper의 고정 접두사를 유지하고, 실제 배포 시각은 Linux UTC/KST 기록을 따른다. 현재PC 사용자 전용 같은 이름의 사본14개와 원본 SHA가 모두 일치하며 비공개 내용은 Git에 포함하지 않았다.

실제 두 DB 사본으로 새 앱을 기동해 업무18개·AI17개 테이블, 기존31개 job/62개 메시지·lifecycle4행·감사를 보존했다. 접수 재개 전 원본도 대조했고 AI v4·기존 키/환경/단위를 유지했다. 자체 active jobs0을 확인한 뒤 web/worker만 전환했으며 Strata/다른 서비스는 제어하지 않았다. web1027288/worker1027298·NORMAL·worker/retention active, source8개 원문 일치를 확인했다. [배포 근거](002_AI_Response_Recovery/deployment.json),[비공개 백업 SHA 대조](002_AI_Response_Recovery/private-backup-verification.json).

## 추가 운영 발견과 V2 보완

첫 실제 xhigh 비교 요청은 필수 판단과 검색2회가 정상 실행됐지만 마지막 응답이 길이 한도로 잘렸다. job5f02ff4518604a589a972c49e33136ad는134.140초 뒤 failed/LENGTH_LIMIT, 마지막 step 추론9,355자·답변1,888자였다. 새 worker 메타 로그가 finish=length/done=True를 확인했다. 이 사례는 성공으로 집계하지 않고 원문·실패 상태를 보존한다. [1차 운영 실패](002_AI_Response_Recovery/production-initial-length-limit.json),[화면](002_AI_Response_Recovery/production-initial-length-limit.jpg).

사용자가 승인한 끝까지 보완 범위에서 profile/context를 재확인했고 같은29노드/필수 입력0이었다. V2 Staging에서 문맥 예산 내 출력 상한을8,192로 늘리고, 명시적 DONE+length 메타가 있는 완료 보고에만1회 보정하도록 확장한다. 임의 종료/기존 길이 오류의 의미를 바꾸지 않으며 legacy required의 검색 미실행을 답변 보정으로 우회하지 않는다. 기존 model/추론 수준과 전체 단계·검색·문자·컨텍스트 한도는 유지한다.

V2 전체292개가55.992초·실패/오류/skip0으로 통과했다. worker의 실제 termination 보고→API→Store→검색 결과 보존→도구 없는 답변 보정을 합성 SSE로 연결했고, 초기 판단 단계의 길이 소진·근거 없는 구 완료 보고·잘못된 메타 타입·미완료 길이 오류·legacy required 우회 거부·동일 보정 예산 소진·이전 버전 보정 메시지 호환을 추가 확인했다. 원문8개를 reviewed-source-v2.zip(SHA256 4432bf82b6a8e52cb40f3db08621eeb3c12debb5690650cdd8f2fac064f766fb)에 보존했고 root8개가 그 SHA/AST와 일치했다. 최종 소스 판정은 source-manifest-v2.json을 기준으로 한다.

V2 root 전체292개도56.198초·실패/오류/skip0으로 통과했다. 원문 ZIP/manifest/root의8개 SHA를 대조한 뒤 V2 후보8개만 정리했다. [최종 root 검증](002_AI_Response_Recovery/root-verification-v2.json),[정리](002_AI_Response_Recovery/merge-and-cleanup-v2.json).

V2 commitf78c1d33513e80efcdb6b251dbcea466822e98b1은2026-11-06 08:02:25 KST에 다시 활성화했다. 첫 운영 시험의 실패까지 포함한 현재 두 DB·설정·source를 새 private release `20261105-ai-ux-response-v2-20261105T230117-a319b9`와 현재PC 사용자 전용 사본14개로 새로 보존했고 SHA를 전부 대조했다. 실제 DB 사본과 접수 재개 전 원본의 업무18개·AI17개 테이블, 기존32개 job/64개 메시지·lifecycle5행·감사 보존을 확인했다. web1031215/worker1031225, NORMAL·worker/retention active, 키/단위 불변·최종 source8개 일치를 확인했다. [최종 배포](002_AI_Response_Recovery/deployment-v2.json),[현재PC 백업 대조](002_AI_Response_Recovery/private-backup-verification-v2.json).

V2의 동일 실제 xhigh 비교 질문은 job2852d2da9bd14843bf13b25012a65266에서174.665초·3단계로 done 처리됐다. 실제 Yahoo 검색2회 뒤 최종 답변3,009자·추론12,479자, DONE=true/stop을 확인했다. max_tokens8,192·xhigh를 전 단계 유지했고 보정은 필요하지 않았다. guard released·예약0·다음 보내기 가능과 비교표11행·결론·출처 화면을 확인했다. 이 시험은 실제 모델의 완결 응답 근거이며 비교 내용의 사실 정확도 평가로 확대하지 않는다. [화면](002_AI_Response_Recovery/production-v2-comparison.jpg).

최종 교차 검토에서는 완료된 보정 system 지시가 같은 job의 다음 단계 모델 입력에 남을 위험을 발견했다. final Staging에서 영속 원장은 보존하되 모델용 context에서 정확한 현행/구 서버 제어 메시지만 제외하고, 활성 보정 지시만 첫 system 메시지에 합친다. 실제 API와4단계 SSE 회귀에서 단일 system 메시지·활성 지시 포함·완료된 검색 지시 제거를 검사하고, 순수 projection의 원문/복사된 user·assistant 문자열/구 버전 횟수 보존을 추가 검사한다.

최종 Staging293개는56.045초, 병합 후 root293개는55.981초에 실패/오류/skip0으로 통과했다. 원문8개를 reviewed-source-final.zip(SHA256 9f91d5f48edd0697ca100e2d7a22dcd63c7e072fae76dd2c7106e26a4fd243cb)에 보존하고 root8개 SHA/AST를 확인했다. ZIP·원문·root가 일치하는 이번 후보8개만 정리했다. [Staging 검증](002_AI_Response_Recovery/stage-verification-final.json),[root 검증](002_AI_Response_Recovery/root-verification-final.json),[최종 원문 목록](002_AI_Response_Recovery/source-manifest-final.json),[후보 정리](002_AI_Response_Recovery/merge-and-cleanup-final.json).

최종 runtime commitaac49e846c6daae6998977bfc951a32fe4ba50af를2026-11-06 08:15:48 KST에 활성화했다. private release `20261105-ai-ux-response-final-20261105T231429-8f61a4`의 현재 상태 백업14개를 현재PC 사용자 전용 사본과 SHA 대조했다. 실제 DB 사본과 접수 재개 전 원본에서 업무18개·AI17개 테이블, 기존33개 job/66개 메시지·lifecycle5행·감사 보존을 확인했다. web1034430/worker1034440·NORMAL·worker/retention active, 최종 원문8개·기존 환경/키/세 단위 불변을 확인했다. [최종 배포](002_AI_Response_Recovery/deployment-final.json),[최종 비공개 백업 대조](002_AI_Response_Recovery/private-backup-verification-final.json).

## 최종 운영의 실제 보정 소진 시험

일반 test05 계정에 별도 시험 대화를 만들고 “웹 검색과 장비 작업 없이 최종 답변을 비워 두라”는 의도적인 부정 시험을 xhigh로 보냈다. jobe54a5d2544674ff2aa630ed1cb187d3e는29.143초·3단계였다. 첫 판단은 검색 불필요(외부 검색0회), 다음 빈 응답에서 answer 보정1회를 실제로 접수했고 마지막 단계는 도구0개·단일 system·활성 answer 지시만 제공했다. 모델이 다시 빈 답변을 보내 failed/EMPTY_RESPONSE로 끝났다. 이는 의도한 소진 경계의 검증이며 성공 응답으로 집계하지 않는다.

화면에는 “AI가 답변 보정 후에도 내용을 보내지 않아 작업을 완료하지 못했습니다”라는 구체적 사유가 남았고 보내기 버튼은 활성화됐다. guard released·예약0과3개 step의 추론 원문 보존을 확인했다. 서버가 답변을 임의 작성하거나 빈 성공으로 처리하지 않았으며 다른 검색/업무를 실행하지 않았다. [실제 시험 근거](002_AI_Response_Recovery/production-empty-response.json),[소진 후 화면](002_AI_Response_Recovery/production-empty-response.jpg).

## 최종 운영의 정상 답변과 보존 검증

동일한 부정 시험 대화에서 빈 답변 조건의 종료를 명시하고 정상 한 문장을 요청했다. job5968852ecdd54597aa4500f3760a06f3는15.555초·2단계·검색0회로 “정상 응답과 후속 질문 처리를 확인했습니다.”를 저장했다. 직전 실패의 보정 상태는 새 요청으로 전이되지 않았고 보내기 버튼도 다시 활성화됐다. [후속 질문 화면](002_AI_Response_Recovery/production-followup.jpg).

원래 누락된 것과 같은 공개 비교 질문은 별도 test05 요청3c29313ee6b74065870f2d816b1ae625로 최종 코드에서 다시 검증했다. xhigh·max_tokens8,192를 유지하고 Yahoo 실검색1회/5건 뒤191.293초·2단계로 done 처리됐다. 최종 raw 답변2,415자·추론11,012자, DONE=true/stop을 확인했다. 화면에는 비교표2개/총20행·출처·확인 불가 항목이 표시됐고 추론 자동 접힘·진행 표시 종료·보내기 활성화를 확인했다. 일반 비교 응답의 완결성과 저장을 검증한 것이며 모델 비교 내용의 정확도·우위 평가까지 검증한 것은 아니다.

1280×720 PC와412×915 모바일 viewport에서 본문 가로 넘침이 없고, 모바일 보내기44×44가 화면 안에 놓임을 확인했다. 모바일은 viewport 검증이며 실제 폴드7 물리 기기 시험으로 확대하지 않는다. 최종 활성화 이후 브라우저 error0, 기존 Tailwind CDN 사용 안내 warning2건을 구분해 기록했다. 임시 viewport는 원래 크기로 복원했다. [PC 화면](002_AI_Response_Recovery/production-final-pc.jpg),[모바일 화면](002_AI_Response_Recovery/production-final-mobile.jpg),[화면 측정](002_AI_Response_Recovery/production-ui-verification.json),[최종 실제 요청·worker 종료 로그](002_AI_Response_Recovery/production-final-requests.json).

검증 종료 시 active jobs0·active guards0·예약0, web/worker/retention 정상·NORMAL이었다. 최종 source8개 SHA와 환경/키/세 단위는 일치했다. 최종 배포 직전 업무 행은 변경/누락0, AI 기존 행 누락0이었다. 기존 AI 행의 변경은 모델/프로바이더 확인 시각, 시험 대화 updated와 해당 계정 보관량뿐이며 기존 job/메시지/감사 행은 보존됐다. 최초 WEB_SEARCH_PLAN_REQUIRED 실패와1차 운영 LENGTH_LIMIT 실패는 그대로 남아 있다. [보존 검증](002_AI_Response_Recovery/production-preservation-final.json).

## 구현 후 Validation1~8

1. 거버넌스: legacy 선택 사유·검증되지 않은 런타임 표기를 보존했다. manifest1.8.1/44노드 validate 오류·경고0과 context29노드/필수 입력0 범위를 적용했고 EN 기준 주석을 갱신했다. 사용자 명시 승인 범위 안에서 Staging→병합→운영을 수행했다.
2. 의도: 최초 누락 원인에 대응하는 필수 판단/빈 답변 보정을 구현했고 실제 발견한 토큰 종료를 추가 보완했다. 구 실패를 수정하지 않고 향후 요청을 처리하며 보정 소진과 정상 답변을 별도로 집계했다.
3. 논리: 최종 Staging293개/56.045초·root293개/55.981초가 모두 통과했다. 실제 API/Store/SSE의4단계 보정, 현행/구 marker 횟수, 단일 system/완료 지시 제거, 구 완료 보고와 명시적 length 메타, stale lease·예약·총6단계를 확인했다.
4. 운영: 세 차례의 실제 발견/보완 이력을 보존하고 최종 현재 백업14개·실제 DB 사본 보존을 확인한 뒤 idle 자체 서비스만 전환했다. schema/외부 라이브러리/키/단위·다른 서비스는 변경하지 않았다.
5. 보안: 사용자 text를 권한으로 파싱하지 않고 현재 소유자/세션/CSRF/lease·민감 검색 거부·도구 schema·취소/휴지통 경계를 유지했다. 답변 보정 도구0을 실제 claim에서 확인했고 고정 종료 로그에는 본문/키를 추가하지 않았다. 기존 본문 감사는 보존했다.
6. 복구: V1/V2/final 원문 ZIP·manifest·병합/후보 정리 근거와 서버/PC private 현재 사본을 남겼다. 구 실패2건·기존 업무/AI/감사 행·설정 SHA를 대조했고 원문 후보8개 외 다른 Staging을 정리하지 않았다.
7. UX: 의도적인 빈 답변 소진 후 구체적 오류와 보내기 활성화, 같은 대화 후속 정상 응답15.555초, 원래 비교 질문 완결191.293초를 실제 일반 계정에서 확인했다. PC/모바일 표·추론 접힘·입력 복귀 화면을 보존했다.
8. 메타: 새로운 하위 에이전트나 무제한 반복·미확인 실행 재전송을 도입하지 않았다. 자동화 회귀와 실제 모델 응답·부정 시험을 구분했고 기존9개 dirty/과거 untracked를 보존한다. 모델이 계속 빈 응답을 보내거나 공급자 연결이 종료되지 않은 모든 경우의 성공을 보장한다고 주장하지 않는다.

최종 기록은 한정된 문서·증거 commit으로 업로드하고 서버에는 fast-forward로 동기화한다. 이 문서 동기화에서는 검증한 런타임8개와 두 프로세스를 재시작하지 않으며 마지막 동기화 영수증은 별도 보존한다.
