import json
import re
import pathlib
import inspect
import ast
import os
import multiprocessing
import asyncio
import traceback
import importlib

from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types, errors
import structlog
from bs4 import BeautifulSoup


from .models import (
    AskGeminiResult,
    AskGeminiErrorInfo,
    ResultItems,
    HTMLConfigSearchResult,
)
from .parserlog import UpdateParserLog
from domain.models.ai import repository as a_repo
from common.read_config import get_model_escalation_list

logger = structlog.get_logger(__name__)

MODEL_ESCALATION_LIST = get_model_escalation_list()


CLASS_NAME_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")
IMPORT_PATTERN = re.compile(r"(?:from\s+(\S+)\s+import\s+(\S+))|(?:import\s+(\S+))")
CURRENT_PATH = pathlib.Path(__file__).resolve().parent


def is_safe_code(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    allowed_modules = {
        "bs4",
        "lxml",
        "re",
        "json",
        "datetime",
        "typing",
        "collections",
        "math",
        "urllib",
    }
    allowed_from_imports = {
        ("__future__", "annotations"),
        # 必要に応じてここに追加
    }
    dangerous_functions = {
        "eval",
        "exec",
        "open",
        "compile",
        "__import__",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "input",
    }

    def check_node_names(node):
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            if top_level not in allowed_modules:
                return False, f"Import of module '{alias.name}' is not allowed."
        return True, None

    for node in ast.walk(tree):
        # 1. Check imports
        if isinstance(node, ast.Import):
            is_allowed, error_msg = check_node_names(node)
            if not is_allowed:
                return False, error_msg
        elif isinstance(node, ast.ImportFrom):
            if node.module:

                for alias in node.names:
                    if (node.module, alias.name) in allowed_from_imports:
                        continue

                    if node.module.split(".")[0] not in allowed_modules:
                        return (
                            False,
                            f"Import from module '{node.module}' is not allowed.",
                        )
            else:
                return False, "Relative imports are not allowed."

        # 2. Check function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    return False, f"Call to function '{node.func.id}' is not allowed."
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_functions:
                    return (
                        False,
                        f"Call to attribute '{node.func.attr}' is not allowed.",
                    )

        # 3. Check dangerous name access
        if isinstance(node, ast.Name):
            if node.id in ("__builtins__", "builtins"):
                return False, f"Access to '{node.id}' is not allowed."

        # 4. Check dangerous attribute access
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr not in {
                "__init__",
                "__name__",
                "__annotations__",
            }:
                return False, f"Access to attribute '{node.attr}' is not allowed."

    return True, None


def _sandbox_worker(code: str, html_str: str, queue: multiprocessing.Queue):
    try:
        # Enforce memory and CPU limits
        try:
            import resource

            mem_limit = 512 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        except (ImportError, ValueError, OSError):
            pass

        # Drop privileges
        try:
            if os.name == "posix" and os.getuid() == 0:
                import pwd

                nobody = pwd.getpwnam("nobody")
                nobody_uid = nobody.pw_uid
                nobody_gid = nobody.pw_gid

                os.setgroups([])
                os.setgid(nobody_gid)
                os.setuid(nobody_uid)
                os.environ["USER"] = "nobody"
                os.environ["HOME"] = "/nonexistent"
        except Exception:
            pass

        allowed_imports = [
            "bs4",
            "lxml",
            "re",
            "json",
            "datetime",
            "typing",
            "collections",
            "math",
            "urllib",
        ]
        sandbox_globals = {
            "__builtins__": __builtins__,
        }

        for mod_name in allowed_imports:
            try:
                sandbox_globals[mod_name] = importlib.import_module(mod_name)
            except ImportError:
                pass

        exec(code, sandbox_globals)

        # Detect the parser class
        class_name = None
        cnames = CLASS_NAME_PATTERN.findall(code)
        if cnames:
            class_name = cnames[0]

        if not class_name:
            # Fallback scan
            for k, v in sandbox_globals.items():
                if inspect.isclass(v) and v.__module__ == "__main__":
                    class_name = k
                    break

        if not class_name or class_name not in sandbox_globals:
            raise ValueError("No parser class found in the generated code.")

        parser_cls = sandbox_globals[class_name]
        parser_instance = parser_cls(html_str)
        parsed_result = parser_instance.execute()

        queue.put({"success": True, "data": parsed_result})
    except Exception as e:
        queue.put(
            {
                "success": False,
                "error_type": type(e).__name__,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )


def run_in_sandbox_sync(code: str, html_str: str, timeout: float) -> list:
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_sandbox_worker, args=(code, html_str, q))
    p.start()

    p.join(timeout=timeout)

    if p.is_alive():
        p.terminate()
        p.join()
        raise TimeoutError(
            f"Code execution exceeded the timeout limit of {timeout} seconds."
        )

    if not q.empty():
        result = q.get()
        if result["success"]:
            return result["data"]
        else:
            error_msg = result.get("error", "Unknown error inside sandbox.")
            error_type = result.get("error_type", "RuntimeError")
            raise RuntimeError(f"[{error_type}] {error_msg}")
    else:
        exitcode = p.exitcode
        raise RuntimeError(
            f"Sandbox process terminated abnormally with exit code {exitcode}."
        )


async def run_in_sandbox_async(code: str, html_str: str, timeout: float = 5.0) -> list:
    return await asyncio.to_thread(run_in_sandbox_sync, code, html_str, timeout)


class NoModelsAvailableError(Exception):
    pass


class ParserRequestPrompt:
    first_prompt_fpath: str
    add_prompt: str

    def __init__(
        self,
        first_prompt_fpath: str = str(CURRENT_PATH / "create_parser_prompt.md"),
        add_prompt: str = "",
    ):
        self.first_prompt_fpath = first_prompt_fpath
        self.add_prompt = add_prompt

    def get_prompt(self) -> str:
        p = pathlib.Path(self.first_prompt_fpath)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8")
        if self.add_prompt:
            text += "\n" + self.add_prompt
        return text


class ParserGeneratorForJSON:
    html_str: str
    label: str
    update_parserlog: UpdateParserLog
    prompt: ParserRequestPrompt
    target_url: str = ""
    recreate: bool = False

    def __init__(
        self,
        html_str: str,
        label: str,
        session: AsyncSession,
        parserlog_repository: a_repo.IParserGenerationLogRepository,
        url: str = "",
        prompt: ParserRequestPrompt = ParserRequestPrompt(
            first_prompt_fpath=str(CURRENT_PATH / "create_parser_json.prompt")
        ),
        recreate: bool = False,
    ):
        self.html_str = html_str
        self.label = label
        self.update_parserlog = UpdateParserLog(session, parserlog_repository)
        self.target_url = url
        self.prompt = prompt
        self.recreate = recreate

    async def execute(self) -> AskGeminiResult:
        subinfo = {}

        if self.recreate:
            code_str = None
            subinfo["recreate"] = True
        else:
            code_str = await self._get_saved_parser_code()

        if code_str is None:
            client = genai.Client()
            result_dict = await self._request_parser(client=client)
            if isinstance(result_dict, AskGeminiErrorInfo):
                return AskGeminiResult(error_info=result_dict)
            log = await self._save_log(response=result_dict, error_info=None)
            code_str = self._extract_parser_code(result_dict)
        else:
            log = await self.update_parserlog.get_log(
                label=self.label, target_url=self.target_url, is_error=False
            )

        if code_str is None:
            error_info = AskGeminiErrorInfo(
                error_type="NoClass", error="No class found"
            )
            await self.update_parserlog.update_log(
                log_entry=log, error_info=error_info, add_subinfo=subinfo
            )
            return AskGeminiResult(error_info=error_info)

        # AST validation
        is_safe, error_msg = is_safe_code(code_str)
        if not is_safe:
            error_info = AskGeminiErrorInfo(
                error_type="SecurityError", error=f"Unsafe code block: {error_msg}"
            )
            await self.update_parserlog.update_log(
                log_entry=log, error_info=error_info, add_subinfo=subinfo
            )
            return AskGeminiResult(error_info=error_info)

        try:
            parsed_result = await run_in_sandbox_async(code_str, self.html_str)
            if not isinstance(parsed_result, list):
                raise ValueError(
                    f"parsed_result is not list, type:{type(parsed_result).__name__}, value:{parsed_result}"
                )
            askresult = AskGeminiResult(parsed_result=ResultItems(items=parsed_result))
            return askresult
        except Exception as e:
            error_info = AskGeminiErrorInfo(error_type=type(e).__name__, error=str(e))
            await self.update_parserlog.update_log(
                log_entry=log, error_info=error_info, add_subinfo=subinfo
            )
            return AskGeminiResult(error_info=error_info)

    async def _get_saved_parser_code(self) -> str | None:
        latest_log = await self.update_parserlog.get_log(
            label=self.label, target_url=self.target_url, is_error=False
        )
        if not latest_log:
            return None

        return self._extract_parser_code(latest_log.response)

    async def _save_log(
        self, response: dict, error_info: None | AskGeminiErrorInfo, subinfo: dict = {}
    ):
        log = await self.update_parserlog.save_log(
            label=self.label,
            target_url=self.target_url,
            query=self.html_str,
            response=response,
            error_info=error_info,
            subinfo=subinfo,
        )
        return log

    async def _request_parser(self, client: genai.Client):
        first_prompt = self.prompt.get_prompt()
        if not first_prompt:
            return AskGeminiErrorInfo(error_type="NoPrompt", error="No first prompt")
        json_str = json.dumps(html_to_minimal_dict(self.html_str), ensure_ascii=False)
        contents = [
            types.Part.from_text(text=json_str),
            first_prompt,
        ]
        for gmodel in MODEL_ESCALATION_LIST:
            try:
                response = await client.aio.models.generate_content(
                    model=gmodel, contents=contents
                )
                return response.model_dump(mode="json")
            except errors.APIError as e:
                if e.code == 429:
                    logger.warning(f"Escalte from {gmodel} to the next model")
                    continue
                return AskGeminiErrorInfo(error_type=type(e).__name__, error=e.message)
            except Exception as e:
                return AskGeminiErrorInfo(error_type=type(e).__name__, error=str(e))
        return AskGeminiErrorInfo(
            error_type=NoModelsAvailableError.__name__,
            error="No models available or Escalation limit exceeded.",
        )

    def _extract_parser_code(self, result: dict) -> str | None:
        if not result.get("candidates"):
            return None

        for part in result["candidates"][0]["content"]["parts"]:
            text = part.get("text")
            if not text or "```python" not in text:
                continue
            lines = text.splitlines()
            trim_lines = lines[1:-1]
            new_part = "\n".join(["from __future__ import annotations"] + trim_lines)
            return new_part
        return None


class HTMLSelectorConfigGeneratorForJSON:
    html_str: str
    prompt: ParserRequestPrompt
    search_word: str

    def __init__(
        self,
        html_str: str,
        search_word: str,
        prompt: ParserRequestPrompt = ParserRequestPrompt(
            first_prompt_fpath=str(
                CURRENT_PATH / "checking_json_for_search_result_prompt.txt"
            )
        ),
    ):
        self.html_str = html_str
        self.prompt = prompt
        self.search_word = search_word

    async def _get_generate_config_result(
        self, client, contents
    ) -> AskGeminiErrorInfo | HTMLConfigSearchResult:
        for gmodel in MODEL_ESCALATION_LIST:
            try:
                response = await client.aio.models.generate_content(
                    model=gmodel,
                    contents=contents,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": HTMLConfigSearchResult.model_json_schema(),
                    },
                )
                return HTMLConfigSearchResult.model_validate_json(response.text)

            except errors.APIError as e:
                if e.code == 429:
                    logger.warning(f"Escalte from {gmodel} to the next model")
                    continue
                return AskGeminiErrorInfo(error_type=type(e).__name__, error=e.message)
            except Exception as e:
                return AskGeminiErrorInfo(error_type=type(e).__name__, error=str(e))
        return AskGeminiErrorInfo(
            error_type=NoModelsAvailableError.__name__,
            error="No models available or Escalation limit exceeded.",
        )

    async def execute(self):
        client = genai.Client()
        first_prompt = self.prompt.get_prompt()
        if not first_prompt:
            return AskGeminiErrorInfo(error_type="NoPrompt", error="No first prompt")
        json_str = json.dumps(html_to_minimal_dict(self.html_str), ensure_ascii=False)
        contents = [
            types.Part.from_text(text=json_str),
            first_prompt.format(search_keyword=self.search_word),
        ]
        result = await self._get_generate_config_result(
            client=client, contents=contents
        )
        if isinstance(result, HTMLConfigSearchResult) and result.error_msg:
            return AskGeminiErrorInfo(
                error_type=RuntimeError.__name__, error=result.error_msg
            )
        return result


def _element_to_minimal_dict(element, text_limit: int | None = 10):
    # 基本のタグ名
    res = {"t": element.name}

    # 主要な属性があれば短縮キーで格納
    if element.get("id"):
        res["i"] = element.get("id")
    if element.get("class"):
        res["c"] = ".".join(element.get("class"))
    if element.get("href"):
        res["h"] = element.get("href")
    if element.get("src"):
        res["s"] = element.get("src")

    if element.name == "img" and element.get("alt"):
        res["a"] = element.get("alt")  # a: alt属性

    children = []
    for child in element.children:
        if child.name:
            # 再帰的に子要素を処理
            children.append(_element_to_minimal_dict(child))
        elif child.strip():
            # テキストは中身が推測できる程度（10文字）にカット
            if not text_limit:
                children.append(child.strip())
            else:
                text = child.strip()
                short_text = (
                    (text[:text_limit] + "..") if len(text) > text_limit else text
                )
                children.append(short_text)

    if children:
        res["ch"] = children
    return res


def html_to_minimal_dict(html: str, text_limit: int | None = 10) -> dict:
    """
    HTMLをGemini解析用に圧縮。
    t: tag, i: id, c: class, h: href, s: src, ch: children
    """
    soup = BeautifulSoup(html, "lxml")
    for s in soup(
        ["script", "style", "head", "meta", "link", "header", "footer", "nav"]
    ):
        s.decompose()
    return _element_to_minimal_dict(soup.body, text_limit=text_limit)
