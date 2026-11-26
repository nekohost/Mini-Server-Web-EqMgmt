"""웹 접근 로그의 출발지 대조와 AI 검토에 쓰는 최소 증거."""

import gzip
import ipaddress
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from .policy import AssistantError, canonical

PURPOSE = 'access_ip_review'
WINDOWS = (24, 72, 168, 336)
MAX_ERRORS = 30_000
MAX_CANDIDATES = 64
MAX_EDGE_BYTES = 96 * 1024 * 1024
KST = timezone(timedelta(hours=9))
STAMP = '%Y-%m-%d %H:%M:%S'
LOGFILE = re.compile(r'access\.log(?:\.\d+(?:\.gz)?)?\Z')
EDGE = re.compile(rb'^(\S+) \S+ \S+ \[([^]]+)\] "([^" ]+) ([^" ]+) HTTP/[^"]+" (\d{3}) ')
ENGLISH_MONTH = {name: n for n, name in enumerate(
    ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1)}
ESCAPE = re.compile(r'\\x([0-9a-fA-F]{2})')

# 공격 문자열은 로컬에서만 판별합니다. 모델에는 정해진 지표 이름과 건수만 전달합니다.
SECRET = re.compile(
    r'/(?:\.env(?:[._~-](?!(?:example|sample|dist|template)(?:$|[._~-]))[a-z0-9_.~-]+)?'
    r'|\.git/(?:config|head|index|logs/head)|\.aws/(?:credentials|config)'
    r'|\.ssh/id_(?:rsa|ed25519|ecdsa|dsa)|\.kube/config|\.docker/config\.json'
    r'|\.htpasswd|(?:equipment|database|backup|dump)\.(?:sql(?:\.gz)?|sqlite3?|db)'
    r'|actuator/(?:env|heapdump|configprops))$'
)
PHP = re.compile(r'\.(?:php[34578]?|phtml)$')
SHELL = re.compile(r'(?:alfa(?:cgi)?|wso\d*|c99(?:shell)?|r57(?:shell)?|b374k|webshell|shell|cmd|wp_filemanager|adminfuns|xleet|chosen|xmlrpcs)\.php$')
SYSTEM_FILE = re.compile(r'/(?:etc/(?:passwd|shadow)|proc/(?:self|1)/environ|windows/win\.ini)(?:$|[/?&])')
INJECTION = re.compile(r'\bunion\s+(?:all\s+)?select\b|\b(?:pg_sleep|sleep)\s*\(\s*\d+\s*\)|\$\{jndi:|\bauto_prepend_file\s*=')
PROMPT = (
    'Review suspicious request evidence already attributed to a public source by both the application and its Nginx log. '
    'Each row has an integer id, exploit signal names and counts, and evidence from the strongest short request burst. '
    'Select only ids with convincing evidence of deliberate abuse. Strong signals include unusual exploit-specific payloads, '
    'multiple private credentials or source-file probes, or concentrated enumeration of PHP paths with multiple webshell names. '
    'Treat a normal login error, 404, server error, or volume alone as insufficient. You may abstain. '
    'Return exactly one JSON object of the form {"selected":[1,2]}, with no prose or markdown. '
    'Use only ids from the evidence. Do not use tools or infer addresses or identities.'
)


def public_ipv4(raw):
    if not isinstance(raw, str):
        return None
    try:
        ip = ipaddress.IPv4Address(raw)
    except (ipaddress.AddressValueError, TypeError):
        return None
    return str(ip) if ip.is_global and not ip.is_multicast and not ip.is_reserved else None


def edge_time(raw):
    date, offset = raw.decode('ascii').split()
    day, month, tail = date.split('/')
    year, hour, minute, second = map(int, tail.split(':'))
    minutes = int(offset[1:3]) * 60 + int(offset[3:5])
    source_zone = timezone(timedelta(minutes=minutes if offset[0] == '+' else -minutes))
    return datetime(year, ENGLISH_MONTH[month], int(day), hour, minute, second, tzinfo=source_zone).astimezone(KST)


def signals(path, query, method):
    resource = unquote(unquote(path)).lower().replace('\\', '/').rstrip('/')
    args = unquote(unquote(query)).lower().replace('+', ' ')
    request = resource + '?' + args
    leaf = resource.rsplit('/', 1)[-1]
    shell = leaf if SHELL.fullmatch(leaf) else ''
    explicit = tuple(name for name, matched in (
        ('system_file', SYSTEM_FILE.search(request)),
        ('injection_pattern', INJECTION.search(args)),
        ('exchange_proxy_powershell', resource == '/autodiscover/autodiscover.json' and args.startswith('@') and '/powershell' in args),
        ('gateway_config_traversal', resource == '/remote/fgt_lang' and '../' in args and '/dev/cmdb' in args),
        ('php_eval_endpoint', resource.endswith('/util/php/eval-stdin.php')),
        ('webshell_write', bool(shell) and method in ('POST', 'PUT', 'PATCH')),
    ) if matched)
    return resource, explicit, bool(SECRET.search(resource)), bool(PHP.search(resource)), shell


def edge_matches(directory, expected, since, until):
    """동일 IP·시각·메서드·경로·상태로 대조하고 충돌하는 요청은 제외합니다."""
    observed = defaultdict(Counter)
    scanned = 0
    saw_log = False
    try:
        for path in sorted(directory.iterdir()):
            if not LOGFILE.fullmatch(path.name) or not path.is_file():
                continue
            saw_log = True
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rb') as stream:
                while line := stream.readline(65537):
                    scanned += len(line)
                    if scanned > MAX_EDGE_BYTES or len(line) > 65536:
                        raise AssistantError('Nginx 로그 상한을 초과했습니다. 로그 보존량을 확인해 주세요.', 413)
                    row = EDGE.match(line)
                    if not row or not (b'400' <= row[5] <= b'599'):
                        continue
                    ip = row[1].decode('ascii', 'ignore')
                    if ip not in expected:
                        continue
                    try:
                        instant = edge_time(row[2])
                    except (UnicodeError, ValueError, KeyError, OverflowError):
                        continue
                    if not since <= instant <= until:
                        continue
                    target = ESCAPE.sub(lambda m: chr(int(m[1], 16)), row[4].decode('utf-8', 'replace'))
                    target = re.sub(r'^https?://[^/?#]+', '', target, flags=re.I)
                    raw_path, _, query = target.partition('?')
                    method, request_path = row[3].decode('ascii', 'ignore'), unquote(raw_path or '/')
                    key = (instant.strftime(STAMP), method, request_path, int(row[5]))
                    if key in expected[ip]:
                        observed[ip, key][signals(request_path, query, method)] += 1
    except (OSError, EOFError) as error:
        raise AssistantError('Nginx 접근 로그를 읽을 수 없습니다. 서비스 계정의 읽기 권한을 확인해 주세요.', 503) from error
    if not saw_log:
        raise AssistantError('대조할 Nginx 접근 로그가 없습니다.', 503)
    for (ip, key), counts in observed.items():
        if len(counts) == 1 and counts.total() == expected[ip][key]:
            yield ip, datetime.strptime(key[0], STAMP), next(iter(counts)), counts.total()


def burst(events):
    """10분 안에 서로 다른 비밀 경로 또는 여러 웹셸 이름이 함께 관측됐는지 확인합니다."""
    window = deque()
    secrets, php, shells = Counter(), Counter(), Counter()
    best = (0, 0, 0)
    explicit = Counter()

    def update(signal, amount):
        path, _, secret, is_php, shell = signal
        for counter, key, include in ((secrets, path, secret), (php, path, is_php), (shells, shell, bool(shell))):
            if include:
                counter[key] += amount
                if not counter[key]:
                    del counter[key]

    for at, signal, count in sorted(events):
        for name in signal[1]:
            explicit[name] += count
        if not any(signal[1:]):
            continue
        while window and at - window[0][0] > timedelta(minutes=10):
            update(window.popleft()[1], -1)
        update(signal, 1)
        window.append((at, signal))
        current = (len(secrets), len(php), len(shells))
        if current[0] >= 2 or (current[1] >= 8 and current[2] >= 2):
            if sum(current) > sum(best):
                best = current
    return explicit, best


def collect(db, directory, hours, now=None):
    """본문·인증정보를 조회하지 않고 운영자용 후보 증거를 생성합니다."""
    until = (now or datetime.now(KST)).replace(microsecond=0)
    since = until - timedelta(hours=hours)
    start, end = since.strftime(STAMP), until.strftime(STAMP)
    rows = db.execute('''SELECT IpAddress, CreatedAt, HttpMethod, RequestPath, StatusCode FROM access_logs
        WHERE CreatedAt BETWEEN ? AND ? AND StatusCode BETWEEN 400 AND 599 LIMIT ?''',
        (start, end, MAX_ERRORS + 1)).fetchall()
    if len(rows) > MAX_ERRORS:
        raise AssistantError('오류 로그가 너무 많습니다. 분석 기간을 줄여 주세요.', 413)
    logins = {public_ipv4(row[0]) for row in db.execute("SELECT DISTINCT IpAddress FROM audit_logs WHERE Action='LOGIN_SUCCESS'")}
    expected = defaultdict(Counter)
    for raw_ip, stamp, method, path, status in rows:
        ip = public_ipv4(raw_ip)
        if ip and ip not in logins and path and len(path) <= 8192:
            expected[ip][stamp, method, path, status] += 1
    per_ip = defaultdict(list)
    corroborated = 0
    if expected:
        for ip, instant, signal, count in edge_matches(directory, expected, since, until):
            per_ip[ip].append((instant, signal, count))
            corroborated += count
        if not corroborated:
            raise AssistantError('기간 내 Nginx와 일치하는 오류 로그를 찾지 못했습니다.', 409)
    candidates = []
    for ip in sorted(per_ip, key=ipaddress.IPv4Address):
        explicit, (secret_paths, php_paths, shell_names) = burst(per_ip[ip])
        if explicit or secret_paths or shell_names:
            candidates.append({'id': len(candidates)+1, 'ip': ip, 'signals': dict(explicit),
                               'secret_paths': secret_paths, 'php_paths': php_paths, 'shell_names': shell_names})
    if len(candidates) > MAX_CANDIDATES:
        raise AssistantError('검토할 후보가 너무 많습니다. 분석 기간을 줄여 주세요.', 413)
    return {'start': start, 'end': end, 'errors': len(rows), 'corroborated': corroborated, 'candidates': candidates}


def review_messages(evidence):
    candidate_data = [{key: value for key, value in row.items() if key != 'ip'} for row in evidence['candidates']]
    return [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': canonical(candidate_data)}]


def packet(job, route, protocol):
    """기존 worker 전송 형식을 사용하고 로그 증거와 도구 권한을 분리합니다."""
    sanitized_route = dict(route)
    evidence = sanitized_route.pop(PURPOSE)
    messages = review_messages(evidence)
    output_tokens = min(8192, max(512, route['context_tokens']//4))
    if len(canonical(messages).encode()) + output_tokens + 512 > route['context_tokens']:
        raise AssistantError('선택한 모델의 문맥이 부족합니다. 분석 기간 또는 모델을 변경해 주세요.', 413)
    return {'id': job['id'], 'lease': job['lease'], 'steps': 0, 'messages': messages, 'tools': [],
            'route': sanitized_route, 'reasoning_effort': route['reasoning_effort'],
            'max_tokens': output_tokens, 'protocol': protocol}


def selected_rows(evidence, content):
    """응답은 서버에 저장된 후보 번호만 선택할 수 있습니다."""
    try:
        result = json.loads(content) if isinstance(content, str) and len(content) <= 2048 else None
        ids = result['selected'] if isinstance(result, dict) and set(result) == {'selected'} else None
        known = {row['id'] for row in evidence['candidates']}
        if (not isinstance(ids, list) or any(type(i) is not int or i not in known for i in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError
    except (ValueError, RecursionError):
        raise AssistantError('AI 판정 응답을 검증할 수 없습니다. 다시 분석해 주세요.', 409) from None
    return [row for row in evidence['candidates'] if row['id'] in ids and public_ipv4(row['ip'])]
