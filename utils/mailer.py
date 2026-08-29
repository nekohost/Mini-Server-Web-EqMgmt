"""
================================================================================
[파일명]: Staging/utils/mailer.py
[역할]: Microsoft Graph API(Exchange Online) 기반 OAuth 2.0 비동기/동기 메일 발송 유틸리티
[의존성 관계]:
  - 외부 라이브러리: requests, python-dotenv, os
  - 설정 파일: .env (MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MAIL_SENDER_ADDRESS)
  - 호출 모듈: app.py (회원가입 인증코드 발송, 비밀번호 재설정 링크 발송, 관리자 알림 등)
[변경 시 영향도]:
  - 토큰 획득 로직이나 이메일 발송 페이로드 포맷 변경 시 시스템 전반의 모든 이메일 알림 기능 중단 위험
================================================================================
"""

# [1] 시스템 및 환경 변수 접근을 위한 표준 라이브러리 임포트
import os

# [2] Microsoft OAuth 2.0 엔드포인트 및 Graph API 호출을 위한 HTTP 요청 라이브러리 임포트
import requests

# [3] .env 파일에 정의된 환경 변수를 os.environ으로 로드하기 위한 dotenv 함수 임포트
from dotenv import load_dotenv

# [4] 로컬 환경의 .env 파일에서 환경 변수(MS 테넌트 ID, 클라이언트 ID/Secret 등)를 메모리로 로드
load_dotenv()


def get_graph_access_token():
    """
    [역할]: Microsoft Entra ID (구 Azure AD) OAuth 2.0 Client Credentials Flow를 통해 Graph API 액세스 토큰을 취득합니다.
    [의존성 관계]:
      - .env 환경 변수: MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET
      - HTTP 통신: Microsoft Online OAuth 2.0 토큰 발급 엔드포인트
    [변경 시 영향도]:
      - 인증 실패 또는 유효하지 않은 토큰 반환 시 send_email() 함수가 작동 불능에 빠져 시스템의 모든 메일 발송 실패
    """
    # [1] 환경 변수에서 Microsoft Azure/Entra ID 테넌트 고유 ID 조회
    tenant_id = os.getenv('MS_TENANT_ID')

    # [2] 환경 변수에서 앱 등록(클라이언트) 고유 ID 조회
    client_id = os.getenv('MS_CLIENT_ID')

    # [3] 환경 변수에서 앱 등록 시 생성된 클라이언트 시크릿(비밀키) 조회
    client_secret = os.getenv('MS_CLIENT_SECRET')

    # [4] 필수 환경 변수 누락 여부 검증 (하나라도 누락 시 조기 차단)
    if not all([tenant_id, client_id, client_secret]):
        # 누락된 경우 콘솔에 명확한 에러 로그를 출력하여 관리자 인지 유도
        print("[Mailer Error] Microsoft Graph API 환경 변수(MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET)가 설정되지 않았습니다.")
        # 인증을 진행할 수 없으므로 None을 반환하고 함수 조기 종료
        return None

    # [5] 테넌트 ID를 기반으로 Microsoft OAuth 2.0 토큰 발급 엔드포인트 URL 조립
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    # [6] OAuth 2.0 Client Credentials Grant Type에 맞춘 HTTP POST 요청 본문(Payload) 딕셔너리 생성
    payload = {
        'client_id': client_id,                               # 앱 등록 클라이언트 ID
        'scope': 'https://graph.microsoft.com/.default',       # 기본 부여된 Graph API 앱 권한 범위
        'client_secret': client_secret,                       # 앱 비밀키
        'grant_type': 'client_credentials'                    # 서버 간 인증(Client Credentials) 방식 지정
    }

    # [7] 네트워크 I/O 예외 상황(타임아웃, DNS 오류 등) 방어를 위한 try-except 블록
    try:
        # Microsoft OAuth 엔드포인트로 POST 요청 전송 (최대 10초 대기)
        response = requests.post(token_url, data=payload, timeout=10)

        # [8] 응답 상태 코드가 HTTP 200 OK인지 판별
        if response.status_code == 200:
            # JSON 응답 본문을 파싱하여 'access_token' 문자열을 추출 후 반환
            return response.json().get('access_token')
        else:
            # 200 이외의 응답(400 Bad Request, 401 Unauthorized 등) 시 에러 로그 출력
            print(f"[Mailer Token Error] {response.status_code}: {response.text}")
            # 토큰 취득 실패로 None 반환
            return None
    except Exception as e:
        # 네트워크 단절 또는 타임아웃 등 예외 발생 시 예외 메시지 출력
        print(f"[Mailer Token Exception] {e}")
        # 예외 상황 시 안전하게 None 반환
        return None


def send_email(to_email, subject, body_html):
    """
    [역할]: Microsoft Graph API(/users/{sender}/sendMail)를 호출하여 지정된 수신자에게 HTML 형식의 이메일을 발송합니다.
    [의존성 관계]:
      - 내부 함수: get_graph_access_token()
      - .env 환경 변수: MAIL_SENDER_ADDRESS
      - 외부 서비스: Microsoft Graph API 엔드포인트
    [변경 시 영향도]:
      - 회원가입 인증메일, 비밀번호 초기화, 결재 승인 알림 등 비즈니스 알림 전반의 성공/실패 여부에 직접 영향
    [매개변수]:
      - to_email (str): 수신자 이메일 주소
      - subject (str): 메일 제목
      - body_html (str): HTML 형식의 메일 본문 내용
    [반환값]:
      - tuple(bool, str): (성공여부, 결과메시지)
    """
    # [1] 환경 변수에서 발신자 이메일 주소(Exchange Online 사서함 계정) 조회
    sender_address = os.getenv('MAIL_SENDER_ADDRESS')

    # [2] 발신자 주소 설정 여부 검증
    if not sender_address:
        # 발신자 주소가 비어있는 경우 에러 콘솔 출력
        print("[Mailer Error] MAIL_SENDER_ADDRESS 환경 변수가 설정되지 않았습니다.")
        # 실패 상태(False)와 안내 메시지를 튜플로 반환하여 호출 측에 전달
        return False, "발신자 이메일 주소(MAIL_SENDER_ADDRESS)가 설정되지 않았습니다."

    # [3] Microsoft Graph API 호출용 Bearer 액세스 토큰 획득 시도
    access_token = get_graph_access_token()

    # [4] 토큰 획득 성공 여부 검증
    if not access_token:
        # 토큰 발급에 실패한 경우 즉시 실패 튜플 반환
        return False, "Microsoft Graph API 인증 토큰을 취득하지 못했습니다."

    # [5] 발신자 사서함을 통한 메일 발송용 Graph API 엔드포인트 URL 생성
    send_mail_url = f"https://graph.microsoft.com/v1.0/users/{sender_address}/sendMail"

    # [6] HTTP 헤더에 Bearer 토큰 및 JSON 콘텐츠 타입 명시
    headers = {
        'Authorization': f'Bearer {access_token}',  # OAuth 인증 토큰 주입
        'Content-Type': 'application/json'          # JSON 페이로드 규격 설정
    }

    # [7] Microsoft Graph API sendMail 규격에 맞춘 JSON 본문(Email Payload) 조립
    email_payload = {
        "message": {
            "subject": subject,                     # 이메일 제목 바인딩
            "body": {
                "contentType": "HTML",              # HTML 렌더링 지원 지정
                "content": body_html                # HTML 마크업 본문 주입
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email         # 수신자 이메일 주소 바인딩
                    }
                }
            ]
        },
        "saveToSentItems": "true"                   # 보낸 편지함에 발송 이메일 사본 저장 활성화
    }

    # [8] Graph API 엔드포인트로 메일 발송 비동기 요청 전송
    try:
        # sendMail API 엔드포인트로 JSON 페이로드와 인증 헤더를 실어 POST 요청 전송 (최대 10초 대기)
        response = requests.post(send_mail_url, json=email_payload, headers=headers, timeout=10)

        # [9] Graph API의 메일 발송 성공 상태 코드(200 OK 또는 202 Accepted) 확인
        if response.status_code in [200, 202]:
            # 발송 성공 시 True와 성공 안내 문구 반환
            return True, "메일이 성공적으로 발송되었습니다."
        else:
            # 실패 시(403 권한 부족, 404 사서함 미존재 등) 상태 코드와 응답 텍스트 출력
            print(f"[Mailer Send Error] {response.status_code}: {response.text}")
            # 실패 상태(False)와 상태 코드가 포함된 안내 메시지 반환
            return False, f"메일 발송 실패 ({response.status_code})"
    except Exception as e:
        # 네트워크 지연, 연결 끊김 등 런타임 예외 발생 시 에러 로그 출력
        print(f"[Mailer Send Exception] {e}")
        # 예외 객체 메시지를 포함한 실패 튜플 반환
        return False, f"메일 전송 중 예외 발생: {str(e)}"
