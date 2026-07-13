import pytest
from unittest.mock import AsyncMock, patch

from app.gemini_api.ask_gemini import is_safe_code, ParserGeneratorForJSON
from databases.sql.ai import repository as ai_repo
from domain.models.ai import ailog as m_ailog, command as a_cmd


@pytest.mark.asyncio
async def test_execute_logs_error_when_code_is_unsafe(test_db):
    parserlog_repo = ai_repo.ParserGenerationLogRepository(test_db)
    errorcodelog_repo = ai_repo.CodeValidationErrorsRepository(test_db)
    parser_generator = ParserGeneratorForJSON(
        html_str="<html></html>",
        label="test_label",
        session=test_db,
        parserlog_repository=parserlog_repo,
        errorcodelog_repository=errorcodelog_repo,
        url="http://example.com",
    )

    unsafe_code = "eval('print(1)')"

    parser_generator._get_saved_parser_code = AsyncMock(return_value=unsafe_code)

    dummy_log = m_ailog.ParserGenerationLog(
        id=1,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        label="test_label",
        target_url="http://example.com",
        query="<html><title>target_html</title></html>",
        response={
            "candidates": [
                {"content": {"parts": {"text": "```python\neval('print(1)')\n```"}}}
            ]
        },
        error_info=None,
        meta={},
    )
    parser_generator.update_parserlog.update_log = AsyncMock(return_value=dummy_log)
    parser_generator.update_parserlog.get_log = AsyncMock(return_value=dummy_log)
    parser_generator._request_parser = AsyncMock(return_value=dummy_log.response)

    with patch(
        "app.gemini_api.ask_gemini.is_safe_code",
        return_value=(False, "Call to function 'eval' is not allowed."),
    ):
        result = await parser_generator.execute()

    assert result.error_info.error_type == "SecurityError"
    assert "Unsafe code block" in result.error_info.error

    result = await errorcodelog_repo.get(
        a_cmd.CodeValidationErrorsGetCommand(
            label="test_label", target_url="http://example.com"
        )
    )
    assert result is not None
    assert result[0].model_dump(
        exclude={"id", "created_at", "updated_at"}
    ) == m_ailog.CodeValidationErrors(
        label="test_label",
        target_url="http://example.com",
        raw_input_code=unsafe_code,
        error_type="SecurityError",
        error_details={"message": "Call to function 'eval' is not allowed."},
    ).model_dump(
        exclude={"id", "created_at", "updated_at"}
    )


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


def test_compile_behavior():
    # 1. 許可されるケース: re.compile は利用可能であるべき
    code_safe = "import re; re.compile(r'pattern')"
    is_safe, message = is_safe_code(code_safe)
    assert is_safe is True

    # 2. 禁止されるケース: 組み込みの compile() はブロックされるべき
    code_blocked = "compile('print(1)', '<string>', 'exec')"
    is_safe, message = is_safe_code(code_blocked)
    assert is_safe is False
    assert "Built-in function 'compile' is not allowed" in message


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
