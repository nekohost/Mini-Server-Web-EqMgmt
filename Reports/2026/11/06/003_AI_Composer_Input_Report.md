---
artifact_id: REPORT-20261106-003
work_id: RELEASE-20261106-AI-COMPOSER-INPUT
owner: Codex
status: in-progress
---

# AI 입력 공간·Enter 처리 정밀 검토

## 구현 전 Validation1~8

1. 거버넌스: Recorder ensure 성공/watcher11268, profile legacy/runtime-session-mismatch·verified=false를 확인했다. validate1.8.1/44노드 오류·경고0이다. 최초 context의 미등록 merge intent는 구현 전에 catalog의 merge-production으로 바로잡았고 validate/context 재성공·최종32노드/3pack·필수 입력0을 확인했다. 기존9개 dirty/과거 untracked를 보존하며 Staging부터 작업한다.
2. 의도: 접수 모델 변경/현재 키 설정의 불필요한 하단 문구만 제거한다. 유효한 기존 두 모드를 유지하고 미설정 기본만 send로 변경한다. 실제 키 감각은 이벤트·포커스·지연/잠금 조건을 재현해 판단한다.
3. 논리: 키 처리 원본은 keydown에만 연결되며, 조합 플래그는 compositionend 외에 해제 경로가 없다. 모바일 beforeinput-only와 조합 중 focus 이탈/복귀를 격리 재현한다. 이벤트 중복, 비취소 편집, 선택 영역, 임의 편집과 다음 초안을 함께 검사한다.
4. 운영: 기존 PreferencesJSON/동일 API와 폼을 재사용하고 schema·엔진·외부 의존성을 추가하지 않는다. server/client/개인 설정 UI의 fallback을 함께 바꿔 부분 기본값 불일치를 막는다. 실제 실행은 Linux 격리와 승인된 운영 서버에서만 한다.
5. 보안: 현재 세션·계정·CSRF/값 검증과 중복 접수 방어를 유지한다. IME229 자체나 임의 input 내용만으로 보내지 않고 확인 가능한 줄바꿈 의도와 준비 상태를 확인한다. 불명확한 편집·진행 중 요청은 자동 전송하지 않는다.
6. 복구: 원문/새 소스·manifest·현재 두 DB/환경/단위를 보존한다. GET은 기존 행을 쓰지 않으며 유효 저장 값과 나머지 JSON을 유지해 코드 복귀가 schema에 의존하지 않는다. 후보 정리는 이번 정확한 파일에 한정한다.
7. UX: 안내 제거로 실제 세로 공간이 줄어드는지 확인한다. 기본 send·기존 newline 모두 네이티브 Enter/Shift+Enter와 한글 확정·포커스 복귀·삭제/붙여넣기를 검사하고 모드 표시는 개인 설정에서만 제공한다. 물리 폴드7 키보드를 직접 시험했다고 주장하지 않는다.
8. 메타: 새 하위 에이전트 없이 현재 작업자가 통합한다. 기존 요청의 실패·새 시험 결과를 수정하거나 장비 업무를 실행하지 않는다. 원본 재현, 합성 입력, 실제 모델/브라우저 확인을 구분한다.

## 조사 근거

현재 원본의 bindInputShortcuts는 keydown만 처리하고 beforeinput/input 보조 경로 및 blur 정리가 없다. 이 구조에서의 재현 결과를 먼저 남긴 뒤 보완한다. IME의 조합 종료와 keydown 순서가 달라질 수 있다는 점은 [MDN keydown 설명](https://developer.mozilla.org/en-US/docs/Web/API/Element/keydown_event)을 참조했다. beforeinput의 비취소/미발생 가능성은 [MDN beforeinput 설명](https://developer.mozilla.org/en-US/docs/Web/API/Element/beforeinput_event), 편집 의도·조합/줄바꿈 입력 종류는 [W3C Input Events](https://w3c.github.io/input-events/)를 참고한다. 이 자료는 특정 폴드7 기기의 실제 재현 근거와 구분한다.

## 원본 재현과 추가 경합

원본 생산 클라이언트와 확장된 격리 Chromium 이벤트 검사16개를 조합했다.9개는 통과했고7개는 실패했다. 실패는 모바일 beforeinput-only, legacy229 뒤 실제 줄바꿈, 조합 중 focus 이탈/복귀, keydown과 편집 이벤트의 결합, 기존 newline 모드의 모바일 Shift 입력, 진행 중 모바일 전송의 초안 유지, 비취소 선택 영역 편집이었다. 기본 키/초기 목록·대화 생성 경합의 기존 검사는 유지됐으며 새 원본 재현은 [baseline-browser/results.json](003_AI_Composer_Input/baseline-browser/results.json)에 남겼다. 이는 원본의 이벤트 경로 공백을 재현한 합성 시험이며 실제 폴드7 기기에서7개 고장을 관찰했다는 의미가 아니다.

보완 후 첫412px/dark 표적 시험은3화면·64개 UI 검사와 이벤트 검사16개 모두 통과했다. 첫 전체 백엔드295개도56.632초·실패/오류/skip0이었다. 그 뒤 설정 fetch 전 기존 사용자 모드를 확정할 서버 HTML bootstrap 필요성을 추가 확인했다. 실제 대상에 HTTP page를 추가한 context는 동일32노드·필수 입력0이었고, 현재 계정의 PreferencesJSON 읽기만으로 초기 모드를 전달하도록 보완했다. 구현 전3~8단계 재검토에서 schema/저장/권한 변화가 없고 최초 입력의 경합을 줄이는 범위임을 확인했다. 기존 두 모드·다른 계정·잘못된 JSON에서 HTML/API 일치와 무쓰기 검사를 추가한다.

## 최종 Staging 검증과 원문 보존

최종 백엔드296개는64.408초·실패/오류/skip0이었다. HTML/API의 현재 계정 모드 일치, 유효한 기존 두 값·다른 JSON·CSRF/계정 경계·GET 무쓰기를 확인했다. JS3개 구문 검사와 후보 Python AST도 통과했다. [백엔드 근거](003_AI_Composer_Input/stage-backend-verification.json).

320/412/820/1440px와 light/dark의 키 입력·초기 목록/대화 생성 경합24화면·712개 UI 검사가 통과했다. 이 안의200개 textarea hit 지점이 모두 실제 입력칸에 도달했고, 별도의16개 모바일/IME 편집 교차 검사를8회(총128개) 통과했다. 네이티브 Chromium Enter/Shift+Enter는 실제 키로 검증하고, IME/모바일 특수 이벤트는 합성으로 구분했다. [키 입력 결과](003_AI_Composer_Input/stage-input-browser-final/results.json).

412/1440px·양 테마의 보내기 hitbox4화면·388개 검사도 통과했다. 별도의384px/DPR3/touch 모바일 probe는 standard/edge 두 스킨에서92개 검사·101개 네이티브 동작·52개 신뢰된 보내기 클릭/합성 요청을 통과했다. 화면/키보드 높이 변화·하단 클릭·포커스/초안/선택 영역·확대 fallback을 확인했으며 물리 폴드7은 시험하지 않았다. [버튼 검사](003_AI_Composer_Input/stage-hitbox-browser/results.json),[모바일 probe](003_AI_Composer_Input/stage-fold7-browser-final/results.json).

320px dark와1440px light 산출물을 시각 검토해 두 안내가 사라지고 입력칸·추론/접힘 제어·보내기가 유지되는 것을 확인했다. 전역 Enter 가로채기 여부를 관련 static/templates에서 검색했으며 AI 입력 외 공통 가로채기는 발견하지 못했다. [좁은 화면](003_AI_Composer_Input/stage-input-browser-final/screen-001.png),[PC 화면](003_AI_Composer_Input/stage-input-browser-final/screen-006.png).

원문11개를 reviewed-source.zip(SHA256 8d44ab0f1ea19459cee04407ff8d039a2bdcc2d3efa0fc969b585bd83c01e5c8)에 보존한 뒤 변경9개를 root에 병합했다. root11개 SHA가 원문과 일치하고 Python/JS 정적 검사가 통과했다. root 동작 검증·후보 정리는 이어서 수행한다. [원문 목록](003_AI_Composer_Input/source-manifest.json).

root 백엔드296개도85.656초·실패/오류/skip0으로 통과했다. root의 입력24화면·712개 검사/128개 이벤트 교차 및 버튼4화면·388개 검사가 모두 통과했다. ZIP/후보/root11개 SHA를 대조한 뒤 정확한 후보11개만 정리했고 다른 Staging은 건드리지 않았다. [root 백엔드](003_AI_Composer_Input/root-backend-verification.json),[root 입력](003_AI_Composer_Input/root-input-browser/results.json),[root 버튼](003_AI_Composer_Input/root-hitbox-browser/results.json),[정리 증거](003_AI_Composer_Input/merge-and-cleanup.json).

운영 반영 전 조회에서 test05는 기존 newline을 저장했고 test04는 설정 값이 없음을 확인했다. 운영 검증 때 두 계정의 설정을 수정하지 않고 각각 기존 동작과 새 기본 동작을 확인한다. 이 시점의 서버는8aa22036a59965aff44506b3cfa982f81a8667a1·web1034430/worker1034440·active jobs0이었다. [사전 상태](003_AI_Composer_Input/production-before.json).
