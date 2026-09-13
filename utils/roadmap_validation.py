"""제안 002: transport와 업무 서비스가 공유하는 무의존 입력 계약."""
import json  # JSON의 구조와 바이트 크기를 검증합니다.
import re  # 허용 문자와 고정 날짜 형식을 검증합니다.
from datetime import date  # 윤년을 포함한 실제 날짜를 검사합니다.


class InputError(ValueError):
    """[역할] 안전한 사용자 오류. [의존성 관계] API errorhandler. [변경 시 영향도] 400/409 응답."""
    def __init__(self, message, status=400):
        super().__init__(message)  # 내부 예외나 데이터베이스 경로는 담지 않습니다.
        self.status = status  # 권한/경합 오류도 같은 응답 형식을 사용합니다.


def text_value(value, field, maximum=200, required=False, trim=True):
    """[역할] 문자열 타입/길이/제어문자 검사. [의존성 관계] 모든 입력. [변경 시 영향도] 기존 값은 일괄 변경하지 않음."""
    if value is None and not required:
        return ''  # 선택 필드는 명시적 비움으로 정규화합니다.
    if not isinstance(value, str):
        raise InputError(f'{field}: 문자열이어야 합니다.')
    result = value.strip() if trim else value  # 비밀번호는 공백을 보존합니다.
    if len(result) > maximum or (required and not result):
        raise InputError(f'{field}: {1 if required else 0}~{maximum}자로 입력해 주세요.')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in result):
        raise InputError(f'{field}: 제어문자를 사용할 수 없습니다.')
    return result


def integer(value, field, minimum=1, maximum=2147483647):
    """[역할] bool/실수와 정수 구별. [의존성 관계] ID/페이지/revision. [변경 시 영향도] SQL 바인딩."""
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'\d+', str(value)):
        raise InputError(f'{field}: 정수만 사용할 수 있습니다.')
    result = int(value)
    if not minimum <= result <= maximum:
        raise InputError(f'{field}: {minimum}~{maximum} 범위여야 합니다.')
    return result


def flag(value, field):
    """[역할] JSON 논리값과 기존 0/1 호환. [의존성 관계] 공개/임시. [변경 시 영향도] 문자열 false 우회 방지."""
    if type(value) is bool or type(value) is int and value in (0, 1):
        return bool(value)
    raise InputError(f'{field}: true/false 또는 0/1이어야 합니다.')


def day(value, field):
    """[역할] 실제 ISO 달력 일자. [의존성 관계] 기한/검색/CSV. [변경 시 영향도] 윤년/빈값."""
    if value in (None, ''):
        return None
    value = text_value(value, field, 10, True)
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        date.fromisoformat(value)
    except ValueError:
        raise InputError(f'{field}: 올바른 YYYY-MM-DD 날짜를 입력해 주세요.') from None
    return value


def password(value, new=False):
    """[역할] 신규 비밀번호 정책. [의존성 관계] 가입/변경. [변경 시 영향도] 기존 로그인은 강도 재검사 없음."""
    value = text_value(value, '비밀번호', 256, True, trim=False)
    if new and (len(value) < 8 or not re.search('[A-Za-z]', value) or not re.search('[0-9]', value) or not re.search(r'[^A-Za-z0-9\s]', value)):
        raise InputError('새 비밀번호는 8~256자이며 영문·숫자·특수문자를 포함해야 합니다.')
    return value


def login_id(value):
    """[역할] 신규/변경 ID 허용 문자. [의존성 관계] 가입/프로필. [변경 시 영향도] 기존 로그인 ID 유지."""
    value = text_value(value, '아이디', 64, True)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}', value):
        raise InputError('아이디는 3~64자 영문·숫자·_.@- 조합이어야 합니다.')
    return value  # 기존 case-sensitive 로그인/UNIQUE 계약을 유지합니다.


def email_address(value):
    """[역할] 이메일 타입/구문/길이. [의존성 관계] 기존 인증. [변경 시 영향도] 원래 대소문자 보존."""
    value = text_value(value, '이메일', 254, True)
    if not re.fullmatch(r'[^\s@<>"\x00-\x1f]+@[^\s@<>".]+(?:\.[^\s@<>".]+)+', value):
        raise InputError('유효한 이메일 주소를 입력해 주세요.')
    return value


def json_object(value, field='입력', maximum=65536):
    """[역할] 최상위 JSON 객체/깊이/크기. [의존성 관계] 요청/옵션. [변경 시 영향도] 배열/NaN 거부."""
    if not isinstance(value, dict):
        raise InputError(f'{field}: JSON 객체여야 합니다.')
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode('utf-8')) > maximum:
            raise ValueError()
        def check(node, depth=0):
            """[역할] JSON 깊이 제한. [의존성 관계] json_object. [변경 시 영향도] 중첩 입력."""
            if depth > 12:
                raise ValueError()
            if isinstance(node, dict):
                for key, child in node.items():
                    text_value(key, 'JSON 키', 200, True)
                    check(child, depth + 1)
            elif isinstance(node, list):
                for child in node:
                    check(child, depth + 1)
        check(value)
    except (ValueError, TypeError, RecursionError):
        raise InputError(f'{field}: JSON은 {maximum}바이트/12단계 이하여야 합니다.') from None
    return value


def equipment_fields(data):
    """[역할] 화면/v2/CSV 장비 입력 통일. [의존성 관계] request guard. [변경 시 영향도] 기존 키 호환."""
    data = dict(json_object(data))
    aliases = {'Name': 'name', 'SerialNumber': 'serial_number', 'PurchaseDate': 'purchase_date', 'Memo': 'memo',
               'IsPublic': 'is_public', 'IsDraft': 'is_draft', 'WarrantyEndDate': 'warranty_end_date', 'ReplacementDueDate': 'replacement_due_date'}
    for upper, lower in aliases.items():
        if upper in data and lower in data and data[upper] != data[lower]:
            raise InputError(f'{upper}: 중복 키 값이 서로 다릅니다.')
        for key in (upper, lower):
            if key not in data:
                continue
            if upper in ('IsPublic', 'IsDraft'):
                data[key] = flag(data[key], key)
            elif upper.endswith('Date'):
                data[key] = day(data[key], key)
            else:
                data[key] = text_value(data[key], key, 4000 if upper == 'Memo' else 200, upper == 'Name')
    purchase = data.get('PurchaseDate', data.get('purchase_date'))
    for key in ('WarrantyEndDate', 'ReplacementDueDate', 'warranty_end_date', 'replacement_due_date'):
        if purchase and data.get(key) and data[key] < purchase:
            raise InputError('보증/교체 기한은 구입일보다 빠를 수 없습니다.')
    for key in ('option_id', 'UserId'):
        if data.get(key) not in (None, ''):
            data[key] = integer(data[key], key)
    for nested in ('RootData', 'OptionData'):
        if nested not in data or data[nested] is None:
            continue
        value = dict(json_object(data[nested], nested))
        for key in ('categoryCustom', 'manufacturerCustom', 'option_name'):
            if key in value:
                value[key] = text_value(value[key], key)
        for key in ('lineup_node_id', 'option_id', 'categoryId', 'manufacturerId'):
            if key in ('categoryId', 'manufacturerId') and value.get(key) == '__custom__':
                continue  # 사용자 정의 sentinel은 분류/제조사 선택에만 허용합니다.
            if value.get(key) not in (None, ''):
                value[key] = integer(value[key], key)
        if 'isNew' in value:
            value['isNew'] = flag(value['isNew'], 'isNew')
        if 'specs_json' in value:
            value['specs_json'] = specs(value['specs_json'])
        data[nested] = value
    return data


def specs(value):
    """[역할] 옵션 specs 객체 계약. [의존성 관계] 노드/등록. [변경 시 영향도] 저장 JSON 문자열."""
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except (ValueError, RecursionError):
        raise InputError('사양 JSON 형식이 올바르지 않습니다.') from None
    return json.dumps(json_object(value, '사양', 16384), ensure_ascii=False, allow_nan=False)
