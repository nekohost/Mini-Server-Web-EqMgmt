"""[MINI-COMMENT: ASSISTANT.REASONING]
[EN rev.1]
[Role] Separates standard UI efforts, known model ceilings, admin policy and verified custom capabilities.
[Dependencies] Fixed policy values and versioned model profile JSON; no network or model execution.
[Impact] An unsupported/disabled effort cannot become selectable through browser tampering or label aliases.
"""
import re

from .policy import AssistantError, DEFAULT_LEVEL, LEVELS

VERSION = 2
LEGACY_UI = {'low': 'off', 'medium': 'medium', 'high': 'xhigh'}
QWEN_LEVELS = ('off', 'low', 'medium', 'xhigh')


def known_levels(model, adapter):
    """[Role] Recognizes the Strata Qwen Flash Next family by upstream ID, never a mutable display label.
    [Dependencies] Qwen official model card and the existing Strata none/effort wire contract.
    [Impact] Unrelated models/engines do not inherit a guessed reasoning capability.
    """
    normalized = model.lower().replace('_', '-').replace(' ', '-')
    return list(QWEN_LEVELS) if adapter == 'strata' and re.fullmatch(r'(?:.*/)?qwen3\.8-flash-next(?:-.*)?', normalized) else None


def validate_settings(levels, default, ceiling=None):
    """[Role] Validates the complete bounded admin effort set/default atomically.
    [Dependencies] Standard enum and optional known model ceiling; bool/string/coercion are rejected.
    [Impact] Empty sets explicitly mean model-default behavior, never a claim that thinking is disabled.
    """
    if not isinstance(levels, list) or len(levels) > len(LEVELS) or any(type(level) is not str or level not in LEVELS for level in levels) or len(set(levels)) != len(levels):
        raise AssistantError('허용할 추론 수준은 중복 없는 표준 단계 목록이어야 합니다.')
    if ceiling is not None and not set(levels) <= set(ceiling):
        raise AssistantError('이 모델이 지원하지 않는 추론 수준은 허용할 수 없습니다.')
    if type(default) is not str or (default not in levels if levels else default != DEFAULT_LEVEL):
        raise AssistantError('기본 추론 수준은 허용한 단계 중에서 선택해 주세요.')
    return [level for level in LEVELS if level in levels]


def normalize_profile(model, adapter, original):
    """[MINI-COMMENT: ASSISTANT.REASONING.PROFILE]
    [EN rev.1]
    [Role] Produces a standard profile while keeping legacy aliases distinct from new low/high values.
    [Dependencies] Server-owned profile JSON; known presets or genuinely probed custom levels.
    [Impact] Old verified off/medium/xhigh retain meaning; new unknown levels require an explicit successful probe.
    """
    profile = dict(original)
    if 'reasoning_version' in profile and profile['reasoning_version'] != VERSION:
        raise AssistantError('모델 추론 설정 버전을 확인해 주세요.', 503)
    known = known_levels(model, adapter)
    modern = profile.get('reasoning_version') == VERSION
    verified = profile.get('verified_levels', profile.get('levels', []))
    if not modern:
        verified = [LEGACY_UI[level] for level in verified if level in LEGACY_UI]
    verified = [level for level in LEVELS if level in verified]
    enabled = profile.get('enabled_levels', []) if modern else (known if known is not None else verified)
    default = profile.get('default_level', DEFAULT_LEVEL) if modern else ('medium' if 'medium' in enabled else enabled[0] if enabled else DEFAULT_LEVEL)
    enabled = validate_settings(enabled, default, known)
    available = [level for level in enabled if level in (known if known is not None else verified)]
    profile.update(reasoning_version=VERSION, enabled_levels=enabled, default_level=default,
                   verified_levels=verified, levels=available)
    return profile


def public_settings(model, adapter, profile):
    """[Role] Projects model-level support, policy and verification reasons without upstream credentials.
    [Dependencies] A normalized profile and fixed known-model metadata.
    [Impact] Both admin and user screens can explain visible disabled options consistently.
    """
    known = known_levels(model, adapter)
    enabled, usable = profile['enabled_levels'], profile['levels']
    reasons = {}
    for level in LEVELS:
        reasons[level] = ''
        if known is not None and level not in known:
            reasons[level] = '모델 미지원'
        elif level not in enabled:
            reasons[level] = '관리자 미허용'
        elif level not in usable:
            reasons[level] = '기능 시험 필요'
    return {'supported_levels': known if known is not None else list(LEVELS), 'known_reasoning': known is not None,
            'enabled_levels': enabled, 'default_level': profile['default_level'], 'level_reasons': reasons,
            'reasoning_version': VERSION}
