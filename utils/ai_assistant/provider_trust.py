"""Connection-scoped destination and certificate policy for equipment model traffic."""
import base64
from datetime import datetime, timezone
import errno
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization

from .policy import AssistantError


LEGACY_PROVIDER = '0' * 31 + '1'
STRATA_HTTP = 'http://192.168.0.14:8080'
EQUIPMENT_LAN = ipaddress.ip_network('192.168.0.0/24')
EQUIPMENT_SERVER = ipaddress.ip_address('192.168.0.24')
MAX_CA_BYTES = 16384


class BeforeSendError(AssistantError):
    """No HTTP headers or model body have been sent when this error is raised."""
    def __init__(self, message, code='PROVIDER_ADDRESS'):
        super().__init__(message, 422)
        self.code = code


def origin(base):
    if (not isinstance(base, str) or not 1 <= len(base) <= 256 or not base.isascii()
            or any(ord(c) <= 32 or ord(c) == 127 for c in base)
            or any(c in base for c in '@?#\\%*')):
        raise BeforeSendError('주소 단계에서 거절했습니다. 내부망 HTTP 또는 HTTPS 주소를 입력해 주세요.')
    try:
        url = urlsplit(base)
        host = url.hostname
        port = url.port
        if (url.scheme not in ('https', 'http') or not host or port == 0
                or url.path not in ('', '/', '/v1', '/v1/') or url.netloc.endswith(':')):
            raise ValueError()
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            if (len(host) > 253 or re.fullmatch(r'[0-9.]+', host)
                    or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
                               for part in host.split('.'))):
                raise ValueError() from None
        else:
            host = '[' + addr.compressed + ']' if addr.version == 6 else str(addr)
        default = 443 if url.scheme == 'https' else 80
        return f'{url.scheme}://{host}' + (f':{port}' if port and port != default else '')
    except ValueError:
        raise BeforeSendError('주소 단계에서 거절했습니다. 기본 주소 또는 /v1만 사용할 수 있습니다.') from None


def check_peer(value):
    ip = ipaddress.ip_address(value)
    if ip not in EQUIPMENT_LAN or ip in (EQUIPMENT_LAN.network_address, EQUIPMENT_LAN.broadcast_address, EQUIPMENT_SERVER):
        raise BeforeSendError('주소 단계에서 장비관리 전용 내부망의 원격 PC만 승인할 수 있습니다.')
    # A local bind detects every local interface/alias, including ones absent from hostname DNS.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((str(ip), 0))
        except OSError as error:
            if error.errno not in (errno.EADDRNOTAVAIL, 10049):
                raise BeforeSendError('주소 단계에서 서버 자체 주소인지 확인하지 못했습니다.') from None
        else:
            raise BeforeSendError('주소 단계에서 장비관리 서버 자체 주소를 거절했습니다.')


def resolve_addresses(base, provider):
    """Pin every answer to the equipment LAN for registered HTTP and verified HTTPS alike."""
    url = urlsplit(origin(base))
    port = url.port or (443 if url.scheme == 'https' else 80)
    try:
        answers = sorted({str(ipaddress.ip_address(item[4][0])) for item in
                          socket.getaddrinfo(url.hostname, port, type=socket.SOCK_STREAM)})
    except (ValueError, OSError):
        raise BeforeSendError('주소 단계에서 DNS 응답을 확인하지 못했습니다.') from None
    if not 1 <= len(answers) <= 32:
        raise BeforeSendError('주소 단계에서 DNS 주소 개수를 확인해 주세요.')
    for address in answers:
        check_peer(address)
    return url, answers, port


def certificate(pem):
    try:
        if not isinstance(pem, str) or not pem.isascii() or not 0 < len(pem) <= MAX_CA_BYTES:
            raise ValueError()
        match = re.fullmatch(r'-----BEGIN CERTIFICATE-----\s+([A-Za-z0-9+/=\s]+?)\s+-----END CERTIFICATE-----',
                             pem.strip(), flags=re.ASCII)
        if not match:
            raise ValueError()
        der = base64.b64decode(''.join(match[1].split()), validate=True)
        cert = x509.load_der_x509_certificate(der)
        if (cert.public_bytes(serialization.Encoding.DER) != der
                or not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
                or not cert.not_valid_before_utc <= datetime.now(timezone.utc) < cert.not_valid_after_utc):
            raise ValueError()
        try:
            if not cert.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign:
                raise ValueError()
        except x509.ExtensionNotFound:
            pass
        return (cert.public_bytes(serialization.Encoding.PEM).decode('ascii'),
                cert.fingerprint(hashes.SHA256()).hex(), cert.not_valid_after_utc.isoformat())
    except (ValueError, TypeError, UnsupportedAlgorithm, x509.ExtensionNotFound, x509.DuplicateExtension):
        raise BeforeSendError('인증서 단계에서 거절했습니다. 유효한 공개 CA 인증서 한 장(PEM, 16 KiB 이하)을 올려 주세요.',
                              'PROVIDER_TLS') from None


class RevisionPolicy:
    """Created from a private, authenticated revision, never from a browser job payload."""
    def __init__(self, provider, trust):
        self.provider = provider
        self.origin = trust['origin']
        self.addresses = frozenset(trust['addresses'])
        self.pem = trust['ca_pem']

    def destination(self, base):
        if origin(base) != self.origin:
            raise BeforeSendError('승인한 연결 출처와 일치하지 않습니다.')
        url, addresses, port = resolve_addresses(base, self.provider)
        if not set(addresses) <= self.addresses:
            raise BeforeSendError('주소 단계에서 승인 이후 바뀐 IP를 발견했습니다. 주소를 다시 승인해 주세요.')
        return url, addresses[0], port

    def tls_context(self):
        if self.pem:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(cadata=self.pem)
            context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
        else:
            context = ssl.create_default_context()
        context.hostname_checks_common_name = False
        return context
