"""[MINI-COMMENT: ASSISTANT.TRANSPORT]
[EN rev.1]
[Role] Connects only fixed model API paths to approved, pinned destinations.
[Dependencies] Server endpoint allowlist, stdlib HTTP/TLS/DNS; never browser URLs or environment proxies.
[Impact] Redirects, credentials in URLs and DNS rebinding cannot expand the configured network boundary.
"""
import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlsplit

from .policy import AssistantError


class EndpointPolicy:
    """[Role] Compiles explicit origins/CIDRs; DNS origin entries pin their initially approved addresses.
    [Dependencies] Deployment-owned JSON list, not administrator/browser request fields.
    [Impact] LAN is supported without granting arbitrary local network or metadata access.
    """
    def __init__(self, rules):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.ENDPOINTPOLICY.INIT]
        [EN rev.1]
        [Role] Implements init within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        self.rules = []
        for rule in rules:
            if isinstance(rule, str):
                value = self.parse(rule)
                host, port, scheme = value.hostname, value.port or (443 if value.scheme == 'https' else 80), value.scheme
            elif isinstance(rule, dict) and set(rule) == {'host', 'port', 'scheme'}:
                host, port, scheme = rule['host'], rule['port'], rule['scheme']
            else:
                raise ValueError('invalid endpoint allowlist rule')
            if scheme not in ('http', 'https') or type(port) is not int or not 1 <= port <= 65535:
                raise ValueError('invalid endpoint allowlist port/scheme')
            try:
                network = ipaddress.ip_network(host, strict=False)
                addresses = None
            except ValueError:
                network = None
                addresses = frozenset(item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
                if not addresses:
                    raise ValueError('allowlisted host has no addresses')
            self.rules.append((host.lower(), port, scheme, network, addresses))

    @staticmethod
    def parse(base):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.ENDPOINTPOLICY.PARSE]
        [EN rev.1]
        [Role] Accepts a base origin or /v1 only, excluding all userinfo/query/fragment/control characters.
        [Dependencies] urllib parsing and a bounded deployment/admin string.
        [Impact] API suffixes cannot be used to reach arbitrary control/download routes.
        """
        if not isinstance(base, str) or not 1 <= len(base) <= 256 or any(ord(c) < 33 or ord(c) == 127 for c in base):
            raise AssistantError('연결 주소를 확인해 주세요.')
        try:
            url = urlsplit(base)
            port = url.port
        except ValueError:
            raise AssistantError('연결 주소와 포트를 확인해 주세요.') from None
        if url.scheme not in ('http', 'https') or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment or url.path not in ('', '/', '/v1', '/v1/') or '\\' in base:
            raise AssistantError('http(s) 연결의 기본 주소 또는 /v1만 사용할 수 있습니다.')
        if port is not None and not 1 <= port <= 65535:
            raise AssistantError('연결 포트를 확인해 주세요.')
        return url

    def destination(self, base):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.ENDPOINTPOLICY.DESTINATION]
        [EN rev.1]
        [Role] Resolves once, checks every result and returns the checked IP for the actual socket.
        [Dependencies] Fixed compiled origin/CIDR rules and normal TLS hostname validation.
        [Impact] Validation and connection use the same address; no second DNS lookup occurs.
        """
        url = self.parse(base)
        port = url.port or (443 if url.scheme == 'https' else 80)
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(url.hostname, port, type=socket.SOCK_STREAM)})
        except OSError:
            raise AssistantError('연결 대상의 주소를 확인하지 못했습니다.', 503) from None
        if not addresses:
            raise AssistantError('연결 대상의 주소가 없습니다.', 503)
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                raise AssistantError('허용되지 않은 연결 대상입니다.', 403)
            allowed = any(p == port and s == url.scheme and (
                (n is not None and ip.version == n.version and ip in n) or
                (n is None and h == url.hostname.lower() and address in a))
                for h, p, s, n, a in self.rules)
            if not allowed:
                raise AssistantError('서버 허용 목록에 없는 주소/포트입니다.', 403)
        return url, addresses[0], port


class ModelResponse:
    """[Role] Owns one pinned HTTP response with bounded UTF-8 stream lines and no redirects.
    [Dependencies] http.client connection; used by discovery and the SSE worker.
    [Impact] Connection closure affects only this request, never shared model state.
    """
    def __init__(self, connection, response):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.INIT]
        [EN rev.1]
        [Role] Implements init within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        self.connection, self.response = connection, response
        self.status_code = response.status
        self.headers = response.headers
        self.encoding = 'utf-8'

    def __enter__(self):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.ENTER]
        [EN rev.1]
        [Role] Implements enter within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        return self

    def __exit__(self, *_):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.EXIT]
        [EN rev.1]
        [Role] Implements exit within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        self.response.close()
        self.connection.close()

    def raise_for_status(self):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.RAISE_FOR_STATUS]
        [EN rev.1]
        [Role] Implements raise for status within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        if not 200 <= self.status_code < 300:
            raise AssistantError('AI 연결이 요청을 거부했습니다.', 502)

    def json(self):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.JSON]
        [EN rev.1]
        [Role] Implements json within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        raw = self.response.read(1048577)
        if len(raw) > 1048576:
            raise AssistantError('모델 목록이 허용 크기를 초과했습니다.', 502)
        return json.loads(raw)

    def iter_lines(self, chunk_size=256, decode_unicode=True):
        """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODELRESPONSE.ITER_LINES]
        [EN rev.1]
        [Role] Implements iter lines within this module's fixed boundary.
        [Dependencies] This module's explicit resources and fixed protocol; no caller-selected service.
        [Impact] Preserves this module's protected network, model selection and immutable route boundary.
        """
        while True:
            line = self.response.readline(262146)
            if not line:
                return
            if len(line) > 262145:
                raise ValueError('oversized model stream line')
            yield line.rstrip(b'\r\n').decode('utf-8', errors='strict')


def model_request(policy, base, path, key='', payload=None, timeout=1800):
    """[MINI-COMMENT: ASSISTANT.TRANSPORT.MODEL_REQUEST]
    [EN rev.1]
    [Role] Calls only GET models or POST chat completions over a checked pinned socket.
    [Dependencies] EndpointPolicy and standard certificate verification, with no proxy/redirect support.
    [Impact] JSON discovery is bounded and inference is never automatically retried.
    """
    if path not in ('/models', '/chat/completions') or (path == '/models') != (payload is None):
        raise ValueError('unsupported adapter path/method')
    url, address, port = policy.destination(base)
    cls = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    options = {'timeout': 5}
    if url.scheme == 'https':
        options['context'] = ssl.create_default_context()
    connection = cls(url.hostname, port, **options)
    # http.client retains the original Host and TLS SNI while its socket uses the validated IP.
    connection._create_connection = lambda _address, timeout=5, source_address=None: socket.create_connection((address, port), timeout, source_address)
    headers = {'Accept': 'application/json' if payload is None else 'text/event-stream'}
    if key:
        if not isinstance(key, str) or len(key) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in key):
            raise ValueError('invalid model credential')
        headers['Authorization'] = 'Bearer ' + key
    body = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    try:
        connection.connect()
        connection.sock.settimeout(timeout)
        connection.request('GET' if payload is None else 'POST', '/v1' + path, body=body, headers=headers)
        return ModelResponse(connection, connection.getresponse())
    except Exception:
        connection.close()
        raise
