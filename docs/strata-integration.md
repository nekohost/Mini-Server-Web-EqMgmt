# 관리자용 Strata AI 연동

장비관리의 `/ai` 메뉴에서 기존 Strata 웹 화면을 제공한다. 모델은 260에서 실행하고, 장비관리 Flask는 로그인·권한 확인과 작은 health 응답만 담당한다. 장시간 답변은 Nginx가 `/strata/`에서 전달한다.

## 적용 범위와 설정

현재 구성은 관리자 전용이다. 일반 역할에 메뉴 권한을 잘못 부여해도 서버와 메뉴 목록에서 차단한다. 장비 데이터 스키마를 바꾸지 않고 기존 메뉴 테이블에 `strata` 항목을 추가한다. 기능이 꺼지면 메뉴가 숨겨지고 화면·중계 접근이 차단된다.

다음은 Linux 서비스가 읽는 환경 설정이다. 실제 비밀 값은 포함하지 않는다.

```dotenv
STRATA_ENABLED=true
STRATA_PUBLIC_ORIGIN=https://nekohost.org
STRATA_UPSTREAM_URL=http://192.168.0.14:8080
```

`STRATA_ENABLED`의 기본값은 비활성이다. `STRATA_PUBLIC_ORIGIN`에는 경로와 뒤의 `/` 없이 실제 HTTPS origin을 넣는다. upstream 주소는 관리자 설정이며 HTTP 요청에서 받지 않는다. upstream을 변경할 때에는 Nginx 설정의 `proxy_pass`, Host와 Origin도 함께 맞춘다.

현재 UI는 같은 origin에 포함되는 신뢰된 관리자 화면이다. iframe은 CSS·문서를 분리하지만 별도 보안 경계를 제공하지 않는다. 여러 일반 사용자에게 개방하려면 별도 권한·이력 설계 또는 다른 origin의 UI를 먼저 검토한다.

## Nginx와 비밀 설정

`systemd/nginx-strata.conf.example`을 실제 HTTPS `server` 블록에 맞춰 검토한다. 현재 설정은 Flask의 `127.0.0.1:5000`, Strata의 내부 8080 주소를 사용한다. `auth_request` 모듈이 필요하고 Flask 포트를 외부에 직접 공개하지 않는다.

Strata의 기존 API 키는 다음 파일에만 둔다.

```text
/etc/nginx/private/strata-upstream-key.conf
```

이 파일과 입력 키 파일은 Git에 넣지 않는다. parent 디렉터리는 해당 운영자의 0700, include 파일은 0600이어야 한다. Nginx master가 읽을 수 있는 소유자를 선택한다. 일반적인 root master 구성에서는 root가 생성한다.

```bash
# Linux에서 기존 키가 들어 있는 보호된 파일을 사용한다. 키를 명령행 값에 넣지 않는다.
sudo python3 tools/write_strata_nginx_key.py \
  --key-file /운영자가/관리하는/보호된/strata-key.txt \
  --output /etc/nginx/private/strata-upstream-key.conf
```

도구는 기존 출력 파일을 덮어쓰지 않으며 비밀 값을 출력하지 않는다. 키 변경은 이전 키 설정을 안전하게 보관한 뒤 별도 운영 절차로 수행한다. `nginx -T`는 include의 실제 키까지 출력할 수 있으므로 그 출력을 대화·보고서에 첨부하지 않는다.

Nginx 인증 서브요청은 원래 메서드·URI·Origin과 CSRF를 Flask에 전달한다. 허용된 관리자만 204를 받는다. Flask 인증 경로는 API 키를 반환하지 않으며 외부 Nginx URL로 직접 접근할 수 없도록 예시 설정에서 막는다. 실제 upstream 요청에서는 장비관리 Cookie와 CSRF를 제거하고 Nginx가 서버 API 키를 붙인다.

예시에서 `/load`, `/unload`, 임의 경로와 메서드는 허용하지 않는다. 현재 UI에 필요한 채팅, 이미지 생성, 설정, 모니터 조회, 폰트·이미지 파일 경로만 허용 목록으로 관리한다. 이 메뉴를 외부 OpenAI 호환 API 클라이언트용 공개 API로 사용하지 않는다. 브라우저 세션 인증이 필요하다.

## 적용 순서

1. Staging 결과 승인과 현재 소스 상태를 확인하고 후보의 원본 `app.py` 해시가 일치하는지 검사한다.
2. 승인된 overlay와 세 가지 app 통합 변경을 운영 소스에 병합한다. 기존 다른 작업자의 변경을 덮어쓰지 않는다.
3. 프로젝트 절차에 맞춰 commit·push, Linux pull과 commit 일치 확인을 수행한다.
4. 아래 Linux 격리 테스트를 수행한다. 운영 DB와 실제 API 키를 fixture에 사용하지 않는다.
5. 운영 서버에서 260의 연결과 API 키 인증이 정상인지 확인한다. 내부 HTTP를 사용하는 운영망의 신뢰 범위를 확인하고 필요 시 TLS나 사설 터널을 구성한다.
6. 실제 Nginx 모듈과 기존 설정을 확인하고 비공개 키 include, 전용 location을 준비한다. `sudo nginx -t`가 통과해야 reload한다.
7. Flask 환경을 활성화하고 승인된 서비스 적용 절차를 수행한다. 활성화된 앱이 신규 메뉴를 중복 없이 등록한다.
8. 관리자 로그인으로 메뉴·프레임·생성·취소·세션 만료를 확인한다. 일반 사용자와 익명 접근은 차단되어야 한다.

운영 환경의 실제 세션·프록시 설정을 보지 않고 예시를 기존 Nginx 전체 설정으로 덮어쓰지 않는다. 프록시 origin과 Nginx의 신뢰된 forwarded headers 설정도 함께 확인한다.

## 검증 명령과 확인 사항

Windows에서는 정적 검사만 수행한다. 애플리케이션을 import하거나 서버를 실행하지 않는다.

```powershell
.\.venv\Scripts\python.exe -B tools\check_strata_static.py
```

승인된 소스가 Linux에 반영된 뒤 프로젝트 루트에서 실행한다.

```bash
.venv/bin/python -m unittest discover -s tests -p test_strata_integration.py -v
node --test tests/test_strata_bridge.mjs
```

테스트는 임시 DB를 사용하고 실제 기존 로그인·권한 함수의 AST를 읽어 fixture에 넣는다. 운영 `app.py`를 import하지 않는다. 화면 렌더링, 계정 상태·역할 변경, CSRF·Origin, 허용 경로, 멱등 메뉴 등록과 비밀 노출 여부를 확인한다.

실제 Nginx에서는 익명·일반 사용자·관리자 GET과 관리자 POST를 각각 검사한다. 특히 인증 서브요청이 원래 POST 메서드와 Origin·CSRF를 받는지 확인한다. 변형 경로, 잘못된 CSRF, `/strata/unload`, 직접 `/api/strata/access`가 upstream에 도달해서는 안 된다.

브라우저에서는 Strata root·채팅·Monitor·About·설정, 모델 대기, 폰트·아이콘·복사·다운로드, 모바일 키보드와 높이를 확인한다. AI 답변이 조금씩 표시되는 동안 다른 장비관리 메뉴가 응답해야 한다. 취소 후 upstream 연결도 종료되어야 한다. 로그인 만료, 다른 기기 로그인, 관리자 역할 제거, 기능 비활성 후 새 요청이 거부되어야 한다.

공동 키가 브라우저 HTML·저장소·네트워크 요청에 포함되어서는 안 된다. 같은 브라우저의 계정 전환 시 이전 세션 이력이 표시되지 않아야 한다. 인증 실패 시 화면을 잠그고 현재 세션의 Strata 저장소를 정리한다. 단순 네트워크 오류에서는 원래 UI가 보관한 대화를 유지한다.

## 롤백

`STRATA_ENABLED=false`로 기능을 끄고 서비스를 승인된 절차로 적용하면 메뉴·페이지·접근 검사가 닫힌다. 전용 Nginx location도 제거하거나 차단해 중계 경로를 함께 닫는다. 코드 전체를 되돌리지 않아도 장비관리 업무 기능은 유지할 수 있다.

신규 메뉴의 DB 항목은 남겨도 비활성 상태에서는 표시되지 않는다. 장비 DB 전체를 이전 백업으로 덮어쓰거나 모델·Strata 파일을 삭제하지 않는다. 새 기능만 되돌리는 경우 후보 파일과 app 통합 부분만 원복한다. 실제 비밀 파일은 운영자의 별도 키 수명주기로 관리한다.
