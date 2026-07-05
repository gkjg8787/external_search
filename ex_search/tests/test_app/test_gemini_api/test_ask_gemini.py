import pytest
from app.gemini_api.ask_gemini import is_safe_code


def test_allowed_imports():
    code = "import json; import math; from bs4 import BeautifulSoup"
    assert is_safe_code(code) == (True, None)


def test_allowed_future_import():
    code = "from __future__ import annotations"
    assert is_safe_code(code) == (True, None)


def test_blocked_imports():
    code = "import os"
    assert is_safe_code(code)[0] is False
    assert "not allowed" in is_safe_code(code)[1]

    code = "from sys import exit"
    assert is_safe_code(code)[0] is False


def test_mixed_imports():
    # 許可されたものと禁止されたものが混ざっている場合（1つでもNGならブロック）
    code = "from __future__ import annotations, os"
    assert is_safe_code(code)[0] is False


def test_dangerous_functions():
    code = "eval('print(1)')"
    assert is_safe_code(code)[0] is False

    code = "open('file.txt')"
    assert is_safe_code(code)[0] is False


def test_attribute_access():
    # 危険な組み込み属性の制限
    code = "obj.__class__"
    assert is_safe_code(code)[0] is False

    # 許可されている属性
    code = "obj.__init__"
    assert is_safe_code(code) == (True, None)


def test_builtins_access():
    code = "builtins.print"
    assert is_safe_code(code)[0] is False


def test_syntax_error():
    code = "import json ;"  # 構文エラーになるようなコード
    # ※構文によってはASTパース自体でSyntaxErrorが出ることを確認
    result, msg = is_safe_code("import = invalid")
    assert result is False
    assert "Syntax error" in msg
