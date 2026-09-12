"""Pure official-model-name input contract shared by service and schema migration."""

import unicodedata  # C0/C1 제어문자를 문자열 표시 경계에서 차단합니다.

MAX_OFFICIAL_MODEL_NAME_LENGTH = 200  # 모델명 전체를 노드 분류명과 별도로 제한합니다.
OFFICIAL_MODEL_COLUMN = "official_model_name TEXT CHECK (official_model_name IS NULL OR (typeof(official_model_name) = 'text' AND length(official_model_name) BETWEEN 1 AND 200))"  # 신규/기존 DB에 동일한 ALTER 정의를 사용합니다.


def normalize_official_model_name(value):
    """[역할] 선택적인 공식 모델명을 검증하고 미지정은 None으로 정규화합니다.
    [의존성 관계] 노드 생성/수정 및 migration 데이터 검사.
    [변경 시 영향도] 길이·타입·빈값 정책과 관리자 입력 안내를 함께 변경해야 합니다.
    """
    if value is None:  # JSON null은 명시적인 해제를 뜻합니다.
        return None  # DB에는 빈 문자열 대신 NULL을 보관합니다.
    if not isinstance(value, str):  # 숫자·bool·배열·객체를 문자열로 강제 변환하지 않습니다.
        raise ValueError("공식 모델명은 문자열 또는 빈값이어야 합니다.")  # 안전한 사용자 오류입니다.
    if any(unicodedata.category(character) == "Cc" for character in value):  # 줄바꿈·탭·NUL도 제품명에 저장하지 않습니다.
        raise ValueError("공식 모델명에는 제어문자를 사용할 수 없습니다.")  # 제어문자 원문은 노출하지 않습니다.
    normalized = value.strip()  # 분류 노드명 자체는 변경하지 않습니다.
    if len(normalized) > MAX_OFFICIAL_MODEL_NAME_LENGTH:  # Unicode 문자 수 기준 상한입니다.
        raise ValueError(f"공식 모델명은 {MAX_OFFICIAL_MODEL_NAME_LENGTH}자 이하여야 합니다.")  # UI와 같은 상한을 안내합니다.
    return normalized or None  # 공백만 있는 입력은 해제로 처리합니다.
