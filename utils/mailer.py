import os
import requests
from dotenv import load_dotenv

load_dotenv()

"""
[역할] Microsoft Graph API OAuth 2.0 (Client Credentials Flow) 토큰 취득 함수
[의존성 관계] os.getenv, requests 모듈, .env 파일 (MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET)
[변경 시 영향도] Microsoft Graph API 인증 실패 시 메일 전송 모듈(send_email) 작동 불능
"""
def get_graph_access_token():
    tenant_id = os.getenv('MS_TENANT_ID')
    client_id = os.getenv('MS_CLIENT_ID')
    client_secret = os.getenv('MS_CLIENT_SECRET')

    if not all([tenant_id, client_id, client_secret]):
        print("[Mailer Error] Microsoft Graph API 환경 변수(MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET)가 설정되지 않았습니다.")
        return None

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    payload = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(token_url, data=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"[Mailer Token Error] {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"[Mailer Token Exception] {e}")
        return None

"""
[역할] Exchange Online / Graph API를 활용하여 지정된 수신자에게 HTML 메일을 발송합니다.
[의존성 관계] get_graph_access_token(), requests 모듈, .env 파일 (MAIL_SENDER_ADDRESS)
[변경 시 영향도] 회원가입 PIN 발송, 비밀번호 재설정 링크 발송, 결재/보증기간 알림 등 이메일 연동 시스템 전반에 직접 영향
"""
def send_email(to_email, subject, body_html):
    sender_address = os.getenv('MAIL_SENDER_ADDRESS')
    if not sender_address:
        print("[Mailer Error] MAIL_SENDER_ADDRESS 환경 변수가 설정되지 않았습니다.")
        return False, "발신자 이메일 주소(MAIL_SENDER_ADDRESS)가 설정되지 않았습니다."

    access_token = get_graph_access_token()
    if not access_token:
        return False, "Microsoft Graph API 인증 토큰을 취득하지 못했습니다."

    send_mail_url = f"https://graph.microsoft.com/v1.0/users/{sender_address}/sendMail"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    email_payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }

    try:
        response = requests.post(send_mail_url, json=email_payload, headers=headers, timeout=10)
        if response.status_code in [200, 202]:
            return True, "메일이 성공적으로 발송되었습니다."
        else:
            print(f"[Mailer Send Error] {response.status_code}: {response.text}")
            return False, f"메일 발송 실패 ({response.status_code})"
    except Exception as e:
        print(f"[Mailer Send Exception] {e}")
        return False, f"메일 전송 중 예외 발생: {str(e)}"
