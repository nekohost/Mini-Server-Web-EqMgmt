"""HTTP security boundaries shared by the legacy Flask endpoints."""
import json
import os
from urllib.parse import urlsplit

from utils.ai_assistant.audit import audit_body
from utils.roadmap_auth import peer_address


# Account events retain method, route, actor audit, peer, status and timing.
# Password/PIN submissions must never enter the second (access-log) database.
CREDENTIAL_ENDPOINTS = frozenset({
    'login_page', 'logout', 'register_page', 'reset_password_page',
    'api_send_pin_logic', 'api_verify_pin_logic', 'api_request_password_reset_logic',
    'api_reset_password_logic', 'api_change_my_password', 'api_reset_user_password',
    'api_update_profile', 'api_user_withdraw', 'api_update_email',
    'api_enable_maintenance', 'api_disable_maintenance',
})
AUDIT_JSON_BYTES = 65536


def client_ip(request):
    return peer_address(request, os.getenv('AUTH_TRUSTED_PROXY_CIDRS', '127.0.0.1/32,::1/128'))


def referrer_path(raw):
    """Keep the originating path without credentials, query parameters or fragments."""
    try:
        return urlsplit(raw or '').path[:255]
    except ValueError:
        return ''


def password_reset_origin():
    value = os.getenv('PUBLIC_BASE_URL') or 'https://nekohost.org'
    origin = urlsplit(value)
    if (origin.scheme != 'https' or not origin.hostname or origin.username is not None
            or origin.password is not None or origin.path not in ('', '/') or origin.query
            or origin.fragment or any(c.isspace() or c in "<>'\"\\" for c in value)):
        raise ValueError('PUBLIC_BASE_URL must be a trusted HTTPS origin')
    return 'https://' + origin.netloc


def legacy_audit_payloads(request, response, secret, known_secrets):
    """Only read bounded, already materialized business JSON. Keep events even on failure."""
    if request.endpoint in CREDENTIAL_ENDPOINTS or request.endpoint is None:
        return None, None

    def capture(raw):
        if not isinstance(raw, bytes) or len(raw) > AUDIT_JSON_BYTES:
            return None
        try:
            body = raw.decode('utf-8')
            json.loads(body)
        except (UnicodeError, ValueError, RecursionError):
            return None
        return audit_body(body, secret, known_secrets)

    request_body = None
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.is_json:
        request_body = capture(getattr(request, '_cached_data', None))
    response_body = None
    if (response.is_json and not response.is_streamed and not response.direct_passthrough
            and response.content_length is not None and response.content_length <= AUDIT_JSON_BYTES):
        response_body = capture(response.get_data())
    return request_body, response_body
