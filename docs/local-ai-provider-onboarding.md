# 로컬 AI 프로바이더 준비와 관리자 화면 등록

| 담당 | 할 일 |
|---|---|
| 새 프로바이더 PC에서 작업하는 AI | 1~3단계에서 모델 API, 인증, 내부망 접속을 준비한다. 운영자에게 연결 주소·모델 ID·연결 종류와 필요한 공개 인증서를 전달한다. |
| 장비관리 관리자 | 4단계에서 **관리자 센터 → AI 연결 관리**를 열어 연결과 모델을 등록하고 검증한다. 기존 연결에서 모델만 추가할 때는 **모델 자동 조회**부터 진행한다. |

장비관리의 260Strata 운영 주소는 `http://192.168.0.14:8080`이다. 같은 관리망의 새 HTTP·HTTPS 주소는 관리자 화면에서 등록한다. 공인 CA로 발급된 인증서는 장비관리 서버의 기본 신뢰 저장소로 검증한다. 사설 CA가 필요하면 공개 PEM을 연결별로 등록한다. 일반 사용자의 PC·휴대폰에는 인증서를 설치할 필요가 없다.

아래의 `192.168.0.24`는 장비관리 서버, `192.168.0.50`은 새 프로바이더의 예시 주소, `lab-model`은 예시 모델 ID다.

## 1. 프로바이더 PC에서 모델 API 켜기

모델 엔진에서 **OpenAI 호환 Chat Completions API**를 켠다. 새 엔진은 `127.0.0.1:8080`에서 수신하게 하고 상시 제공할 모델은 부팅 후에도 기동되도록 설정한다.

- **Local LLM Studio**에서는 모델을 시작하고 **앱 연결**에서 BASE URL과 모델 이름을 확인한다. 이 엔진은 루프백에 열리며 API 키를 검사하지 않는다. 장비관리 전용 키를 비밀번호 관리자에서 생성하고 2단계의 프록시에서 검증한다. 화면 예시의 `local`은 인증용 키로 쓸 수 없다.
- **Strata 또는 키 인증을 제공하는 엔진**에서는 장비관리용 키를 준비한다. 기존 내부망 HTTP를 계속 쓰거나 HTTPS 입구를 함께 운영할 수 있다.

자동 등록에 쓸 모델 ID는 `GET /v1/models` 응답의 `data[].id`에서 확인한다. `POST /v1/chat/completions`는 `stream: true` 요청에 SSE(`text/event-stream`)로 응답해야 한다.

<details>
<summary>새 엔진으로 llama.cpp를 쓰는 경우의 실행 예</summary>

GGUF 경로와 키 파일을 준비한다. 키 파일에는 비밀번호 관리자로 생성한 충분히 긴 임의 키 한 줄을 저장하고 엔진 실행 계정과 관리자만 읽게 한다. 아래 명령을 기존 엔진 기동 방식에 등록하면 된다. [llama.cpp 서버 옵션](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

```powershell
& 'C:\llama.cpp\llama-server.exe' -m 'C:\Models\my-model.gguf' --alias lab-model --host 127.0.0.1 --port 8080 --api-key-file 'C:\ModelConfig\api-key.txt'
```

</details>

## 2. 프로바이더 PC의 접속 방식 선택

기존 내부망 HTTP API가 있다면 장비관리 서버에서 접근할 수 있도록 방화벽을 설정한 뒤 3단계로 진행한다. HTTP에서는 요청 내용과 API 키가 암호화되지 않는다. HTTPS를 선택하면 다음 절차를 따른다.

엔진이 HTTPS를 직접 제공하면 그 기능을 사용한다. 인증서는 관리자가 입력할 주소와 일치해야 한다. IP로 접속하면 인증서의 **IP SAN**, 이름으로 접속하면 **DNS SAN**에 해당 값이 있어야 한다. 방화벽에는 장비관리 서버의 실제 출발지 IP만 허용하고 공유기의 인터넷 포트 포워딩은 열지 않는다.

HTTP 엔진에는 **내부 IP의 TCP 8443 → 기존 모델 엔진**으로 전달하는 역방향 프록시를 둔다. 아래 설정은 장비관리 서버에서 오는 요청만 받아 API 키를 확인하고 스트리밍을 전달한다. 260Strata의 8443은 프로바이더 쪽 HTTPS 구성 사례다. 현재 장비관리의 운영 연결은 8080이다.

<details>
<summary>Windows에서 Caddy로 8443 서비스를 처음 만드는 순서</summary>

관리자 PowerShell에서 진행한다. 신뢰하는 사설 LAN 어댑터가 `Private`인지 `Get-NetConnectionProfile`로 확인한다. 8443이 비어 있고 같은 이름의 서비스가 없는 새 장비에 적용한다. 공식 Windows용 `caddy.exe`를 `C:\Program Files\EquipmentAIProxy`에 두고, 같은 폴더에 확장자 없는 `Caddyfile`을 아래 내용으로 저장한다. 주소 두 개와 실제 엔진 포트를 맞춘다. **Studio는 아래 예시 그대로 사용한다. 엔진 자체가 잘못된 키와 키 없는 생성 요청을 거부하는 장비에서만 `import` 한 줄을 생략할 수 있다.** [Caddy 배포 파일](https://github.com/caddyserver/caddy/releases) · [Windows 서비스](https://caddyserver.com/docs/running#windows-service)

```caddyfile
{
	admin off
	persist_config off
	auto_https disable_redirects
	skip_install_trust
	storage file_system {
		root C:/ProgramData/EquipmentAIProxy/data
	}
	servers {
		protocols h1 h2
	}
}

https://192.168.0.50:8443 {
	bind 192.168.0.50
	tls internal
	@equipment {
		remote_ip 192.168.0.24
		path /v1/models /v1/chat/completions
		import C:/ProgramData/EquipmentAIProxy/data/provider-auth.caddy
	}
	handle @equipment {
		reverse_proxy 127.0.0.1:8080
	}
	handle {
		respond 403
	}
}
```

다음 명령은 전용 서비스 계정의 비공개 폴더를 만들고, 지정한 주소 사이의 TCP 8443을 연다. 키 입력창이 뜨면 비밀번호 관리자에서 생성한 임의 영문·숫자 48자를 붙여 넣는다. 3단계에서 이 키를 관리자에게 안전하게 전달한다. 기존에 광범위한 인바운드 허용 규칙이 있다면 그 범위도 확인한다.

```powershell
$ErrorActionPreference = 'Stop'
$svc = 'EquipmentAIProxy'
$bin = "$env:ProgramFiles\$svc\caddy.exe"
$cfg = "$env:ProgramFiles\$svc\Caddyfile"
$data = "$env:ProgramData\$svc\data"
$providerIP = '192.168.0.50'
$equipmentIP = '192.168.0.24'
New-Service -Name $svc -BinaryPathName ('"{0}" run --config "{1}" --adapter caddyfile' -f $bin,$cfg) -StartupType Manual
sc.exe config $svc obj= "NT SERVICE\$svc"
if ($LASTEXITCODE -ne 0) { throw '서비스 계정 설정을 확인하세요.' }
New-Item -ItemType Directory -Path $data -Force | Out-Null
icacls.exe $data /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "NT SERVICE\${svc}:(OI)(CI)M"
if ($LASTEXITCODE -ne 0) { throw '개인키 폴더 권한을 확인하세요.' }
if (Select-String -LiteralPath $cfg -SimpleMatch 'import C:/ProgramData/EquipmentAIProxy/data/provider-auth.caddy' -Quiet) {
    $key = [Net.NetworkCredential]::new('', (Read-Host '장비관리 전용 키' -AsSecureString)).Password
    if ($key -cnotmatch '^[A-Za-z0-9_-]{40,128}$') { throw '임의 영문·숫자 48자로 다시 입력하세요.' }
    [IO.File]::WriteAllText("$data\provider-auth.caddy", ('header Authorization "Bearer {0}"' -f $key))
    Remove-Variable key
}
& $bin adapt --config $cfg --adapter caddyfile | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Caddyfile을 확인하세요.' }
New-NetFirewallRule -DisplayName "$svc LAN 8443" -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalAddress $providerIP -LocalPort 8443 -RemoteAddress $equipmentIP -Program $bin
Set-Service -Name $svc -StartupType Automatic
Start-Service $svc
Get-NetTCPConnection -State Listen -LocalPort 8443 | Select-Object LocalAddress,LocalPort,OwningProcess
```

지정한 내부 IP에서 8443이 수신 중이면 서비스가 준비됐다. 사설 CA의 **공개 루트 인증서**는 `C:\ProgramData\EquipmentAIProxy\data\pki\authorities\local\root.crt`다. 관리자 PowerShell에서 아래 명령으로 이 인증서의 SHA-256 지문을 기록한다. [Caddy 내부 HTTPS](https://caddyserver.com/docs/automatic-https#local-https)

```powershell
$publicCA = "$data\pki\authorities\local\root.crt"
$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($publicCA)
$sha = [System.Security.Cryptography.SHA256]::Create()
try { [BitConverter]::ToString($sha.ComputeHash($cert.RawData)).Replace('-', '') } finally { $sha.Dispose() }
```

</details>

## 3. 새 PC의 연결 정보 인계하기

프로바이더 PC에서 실제 모델 ID로 짧은 답변이 생성되는지 확인한다. 내부망 입구가 허용할 출발지 IP는 장비관리 서버의 주소다. 방화벽 범위를 넓혀서 시험하지 않는다.

| 관리자에게 전달할 항목 | 예시 또는 전달 방법 |
|---|---|
| 연결 이름 및 API 기본 주소 | 실험실 GPU PC, `https://192.168.0.50:8443` |
| 연결 종류 및 모델 ID | OpenAI 호환 Chat Completions, `lab-model` |
| 자원 그룹 | 새 물리 장비인지, 기존 PC·GPU를 공유하는지 표시 |
| API 키 | 비밀번호 관리자 등 신뢰하는 경로로 전달 |
| 사설 CA를 쓰는 경우 | 공개 루트 인증서와 SHA-256 지문을 전달한다. 개인키는 프로바이더 PC에 보관한다. |

새 프로바이더의 AI에게는 “이 PC의 모델을 장비관리 AI 도우미가 호출할 수 있게 설정하고 관리자에게 전달할 연결 정보를 정리해 주세요”라고 요청하면 된다.

## 4. 관리자 화면에서 연결·모델 등록하기

1. **관리자 센터 → AI 연결 관리 → 연결 추가**에서 연결 이름, HTTP 또는 HTTPS 기본 주소, 연결 종류, 필요한 API 키를 입력한다. 같은 GPU를 공유하면 기존 물리 자원 그룹을 선택한다.
2. HTTPS는 **기본 신뢰 저장소**를 사용한다. 사설 CA로 발급했다면 **이 연결 전용 사설 CA**를 선택하고 공개 PEM 한 장을 올린다. **연결 저장** 후 승인 IP와 SHA-256 지문을 대조한다. 주소를 다른 출처로 바꿀 때는 그 출처의 키와 필요한 CA를 입력한다.
3. **후보 모델 목록 조회 → 후보 워커 기능 시험**에서 실제 모델, 컨텍스트 한도와 사용할 기능을 시험한다. 기존 연결 교체 시에는 현재 공개한 모델의 기능 시험도 통과해야 전환된다.
4. 활성화된 연결에서 **사용자에게 공개**를 선택하고 **모델 설정 저장**을 누른다. 기존 연결에 모델만 추가하려면 해당 연결에서 **모델 자동 조회**를 사용한다.

## 5. 사용자가 실제로 받을 답변 확인하기

**AI 도우미 → 새 대화 → AI 모델 선택**에서 새 모델을 고른다. 짧은 질문 하나에 답변을 받은 다음, 1~2분 이상 걸릴 분량의 답변을 요청한다. **본문이 중간부터 계속 표시되고 마지막 답변까지 저장돼 대화를 다시 열어도 읽을 수 있으면 완료**다. 장비 도구를 공개했다면 ‘내 장비 목록을 보여 줘’처럼 실제 권한 범위의 읽기 작업도 확인한다. 기존 8080 이용자가 있는 장비는 그 클라이언트에서도 원래 주소로 한 번 호출해 확인한다.

문제가 생겨 새 연결의 제공을 보류할 때는 **AI 연결 관리 → 해당 연결 → 신규 요청 허용 해제 → 연결 저장**을 사용한다. 한 연결에서 새로 추가한 모델 하나만 보류할 때는 그 모델의 **사용자에게 공개**를 해제하고 **모델 설정 저장**을 누른다. [HTTP·HTTPS 운영 검증 기록](../Reports/2026/11/10/005_Provider_Security_Report.md)
