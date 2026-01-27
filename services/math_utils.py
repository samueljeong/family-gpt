"""
수학 표현식 후처리 모듈
LaTeX 분수를 한국식 표기로 변환
"""
import re


# LaTeX 분수 패턴: \frac{분자}{분모}
_FRAC_PATTERN = re.compile(r'\\frac\{([^}]+)\}\{([^}]+)\}')

# LaTeX 구분자 패턴: \( ... \), \[ ... \], $ ... $, $$ ... $$
_DELIMITERS = [
    (re.compile(r'\\\[(.+?)\\\]', re.DOTALL), r'\1'),
    (re.compile(r'\\\((.+?)\\\)', re.DOTALL), r'\1'),
    (re.compile(r'\$\$(.+?)\$\$', re.DOTALL), r'\1'),
    (re.compile(r'\$(.+?)\$'), r'\1'),
]


def _frac_to_korean(match: re.Match) -> str:
    """\\frac{분자}{분모} → '분모분의 분자'"""
    numerator = match.group(1).strip()
    denominator = match.group(2).strip()
    return f"{denominator}분의 {numerator}"


def process_math_response(text: str) -> str:
    """
    GPT 응답에서 LaTeX 분수를 한국식 표기로 변환

    변환 예시:
        \\frac{6}{13} → "13분의 6"
        \\( \\frac{6}{13} \\) → "13분의 6"
        $ \\frac{1}{2} $ → "2분의 1"

    Args:
        text: GPT 응답 텍스트

    Returns:
        한국식 분수 표기로 변환된 텍스트
    """
    if not text or '\\frac' not in text:
        return text or ''

    result = text

    # 1. 구분자 제거 (분수가 포함된 경우만)
    for pattern, replacement in _DELIMITERS:
        result = pattern.sub(
            lambda m: replacement.replace('\\1', m.group(1)) if '\\frac' in m.group(1) else m.group(0),
            result
        )

    # 2. \frac{분자}{분모} → 한국식 변환
    result = _FRAC_PATTERN.sub(_frac_to_korean, result)

    return result
