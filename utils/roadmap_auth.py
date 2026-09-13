"""007: 다중 worker/재시작에 일관된 SQLite 인증 시도 한도."""
import hashlib
import hmac
import ipaddress
import time
from utils.roadmap_validation import InputError

POLICIES = {  # (계정+IP 한도, IP 한도, 초); 모든 시도를 소비하여 경합/실패회수 유실을 막습니다.
    'login_page': (10, 60, 900), 'register_page': (5, 30, 900),
    'api_send_pin_logic': (3, 20, 900), 'api_verify_pin_logic': (5, 40, 900),
    'api_request_password_reset_logic': (3, 20, 900), 'api_reset_password_logic': (5, 30, 900),
    'api_change_my_password': (5, 30, 900), 'api_update_profile': (10, 60, 900),
}


def peer_address(request, trusted_networks):
    """[역할] 실제 peer가 신뢰될 때만 ProxyFix IP 사용. [의존성 관계] 환경 allowlist. [변경 시 영향도] 전달 헤더 위조 제한."""
    original = request.environ.get('werkzeug.proxy_fix.orig', {})
    peer = original.get('REMOTE_ADDR', request.environ.get('REMOTE_ADDR', ''))
    try:
        address = ipaddress.ip_address(peer)
        trusted = any(address in ipaddress.ip_network(network.strip()) for network in trusted_networks.split(',') if network.strip())
        return str(ipaddress.ip_address(request.remote_addr if trusted else peer))
    except ValueError:
        return str(peer)[:64] or 'unknown'  # 파싱 실패가 전달 IP 신뢰로 이어지지 않습니다.


def consume(connection, endpoint, account, peer, secret, now=None):
    """[역할] 한 transaction에서 두 버킷 검사/소비. [의존성 관계] guard BEGIN IMMEDIATE. [변경 시 영향도] 유한 잠금/행수 제한."""
    now = int(time.time() if now is None else now)
    account_limit, peer_limit, period = POLICIES[endpoint]
    def key(kind, identity):
        """[역할] 개인정보 없는 키. [의존성 관계] 앱 시크릿. [변경 시 영향도] 한도 원장 원문 노출 방지."""
        return hmac.new(str(secret).encode(), f'{endpoint}:{kind}:{identity}'.encode(), hashlib.sha256).hexdigest()
    limits = [(key('peer', peer), peer_limit), (key('account-peer', account.casefold() + '\0' + peer), account_limit)]
    connection.execute('DELETE FROM auth_rate_buckets WHERE bucket_key IN (SELECT bucket_key FROM auth_rate_buckets WHERE expires_at<=? LIMIT 200)', (now,))
    retry = 0
    for bucket, maximum in limits:
        row = connection.execute('SELECT attempts,expires_at FROM auth_rate_buckets WHERE bucket_key=?', (bucket,)).fetchone()
        if row and row[1] > now and row[0] >= maximum:
            retry = max(retry, row[1] - now)
    if retry:
        return retry  # 초과 시 기존 만료를 연장하지 않으므로 영구 잠금이 아닙니다.
    if connection.execute('SELECT COUNT(*) FROM auth_rate_buckets').fetchone()[0] >= 20000:
        return 60  # 알려지지 않은 peer로 테이블을 무한 확장하지 않습니다.
    for bucket, maximum in limits:
        connection.execute('''INSERT INTO auth_rate_buckets(bucket_key,attempts,expires_at) VALUES(?,1,?)
            ON CONFLICT(bucket_key) DO UPDATE SET attempts=CASE WHEN expires_at<=? THEN 1 ELSE attempts+1 END,
            expires_at=CASE WHEN expires_at<=? THEN excluded.expires_at ELSE expires_at END''', (bucket, now + period, now, now))
    return 0
