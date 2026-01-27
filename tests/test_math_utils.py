"""
수학 표현식 변환 테스트
"""
import pytest
from services.math_utils import process_math_response


class TestProcessMathResponse:
    """process_math_response 함수 테스트"""

    def test_basic_fraction(self):
        """기본 분수 변환"""
        assert process_math_response(r'\frac{6}{13}') == '13분의 6'

    def test_simple_fraction(self):
        """단순 분수"""
        assert process_math_response(r'\frac{1}{2}') == '2분의 1'

    def test_inline_delimiter(self):
        r"""인라인 구분자 \( \) 제거"""
        assert process_math_response(r'\( \frac{6}{13} \)') == ' 13분의 6 '

    def test_display_delimiter(self):
        r"""디스플레이 구분자 \[ \] 제거"""
        assert process_math_response(r'\[ \frac{3}{4} \]') == ' 4분의 3 '

    def test_dollar_inline(self):
        """$ 인라인 구분자"""
        assert process_math_response(r'$ \frac{1}{3} $') == ' 3분의 1 '

    def test_double_dollar(self):
        """$$ 디스플레이 구분자"""
        assert process_math_response(r'$$ \frac{2}{5} $$') == ' 5분의 2 '

    def test_fraction_in_sentence(self):
        """문장 내 분수 변환"""
        text = r'답은 \frac{6}{13}입니다.'
        assert process_math_response(text) == '답은 13분의 6입니다.'

    def test_multiple_fractions(self):
        """다중 분수 변환"""
        text = r'\frac{1}{2} + \frac{1}{3} = \frac{5}{6}'
        result = process_math_response(text)
        assert '2분의 1' in result
        assert '3분의 1' in result
        assert '6분의 5' in result

    def test_no_fraction_passthrough(self):
        """분수 없는 텍스트는 그대로 통과"""
        text = '안녕하세요, 오늘 날씨가 좋네요.'
        assert process_math_response(text) == text

    def test_empty_string(self):
        """빈 문자열"""
        assert process_math_response('') == ''

    def test_none_input(self):
        """None 입력"""
        assert process_math_response(None) == ''

    def test_dollar_without_frac(self):
        """분수 없는 $ 구분자는 그대로 유지"""
        text = '$x + y$'
        assert process_math_response(text) == '$x + y$'

    def test_complex_numerator(self):
        """복잡한 분자/분모"""
        text = r'\frac{2x+1}{3y-2}'
        assert process_math_response(text) == '3y-2분의 2x+1'
