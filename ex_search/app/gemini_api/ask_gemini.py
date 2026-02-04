import json
import re
import pathlib
import inspect

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

logger = structlog.get_logger(__name__)

MODEL_ESCALATION_LIST = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


CLASS_NAME_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")
IMPORT_PATTERN = re.compile(r"(?:from\s+(\S+)\s+import\s+(\S+))|(?:import\s+(\S+))")
CURRENT_PATH = pathlib.Path(__file__).resolve().parent


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


class ParserGenerator:
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
        prompt: ParserRequestPrompt = ParserRequestPrompt(),
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
            class_type = None
            subinfo["recreate"] = True
        else:
            class_type, exec_scope = await self._get_saved_parser()

        if class_type is None:
            client = genai.Client()
            result_dict = await self._request_parser(client=client)
            if isinstance(result_dict, AskGeminiErrorInfo):
                return AskGeminiResult(error_info=result_dict)
            log = await self._save_log(response=result_dict, error_info=None)
            class_type, exec_scope = await self._get_parser_class(result_dict)
        else:
            log = await self.update_parserlog.get_log(
                label=self.label, target_url=self.target_url, is_error=False
            )

        if class_type is None:
            error_info = AskGeminiErrorInfo(
                error_type="NoClass", error="No class found"
            )
            await self.update_parserlog.update_log(
                log_entry=log, error_info=error_info, add_subinfo=subinfo
            )
            return AskGeminiResult(error_info=error_info)
        try:
            for k, v in exec_scope.items():
                if k == class_type.__name__:
                    continue
                if k in globals():
                    continue
                if k == "annotations":
                    continue
                globals()[k] = v
                logger.debug(f"imported {k} to globals")

            parser_instance = class_type(self.html_str)
            parsed_result = parser_instance.execute()
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

    async def _get_saved_parser(self):
        latest_log = await self.update_parserlog.get_log(
            label=self.label, target_url=self.target_url, is_error=False
        )
        if not latest_log:
            return None, {}

        return await self._get_parser_class(latest_log.response)

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

        contents = [
            types.Part.from_text(text=self.html_str),
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

    async def _get_parser_class(self, result: dict) -> tuple[type | None, dict]:
        if not result.get("candidates"):
            return None

        for part in result["candidates"][0]["content"]["parts"]:
            if not part["text"] or "```python" not in part["text"]:
                continue
            lines = part["text"].splitlines()
            trim_lines = lines[1:-1]
            new_part = "\n".join(["from __future__ import annotations"] + trim_lines)
            exec_scope = {}
            try:
                exec(new_part, globals(), exec_scope)
            except Exception:
                logger.exception("parser exec error")
                return None, {}
            cname = CLASS_NAME_PATTERN.findall(new_part)[0]
            MyClass = exec_scope.get(cname)
            if MyClass is not None and inspect.isclass(MyClass):
                return MyClass, exec_scope
        return None, {}


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
            class_type = None
            subinfo["recreate"] = True
        else:
            class_type, exec_scope = await self._get_saved_parser()

        if class_type is None:
            client = genai.Client()
            result_dict = await self._request_parser(client=client)
            if isinstance(result_dict, AskGeminiErrorInfo):
                return AskGeminiResult(error_info=result_dict)
            log = await self._save_log(response=result_dict, error_info=None)
            class_type, exec_scope = await self._get_parser_class(result_dict)
        else:
            log = await self.update_parserlog.get_log(
                label=self.label, target_url=self.target_url, is_error=False
            )

        if class_type is None:
            error_info = AskGeminiErrorInfo(
                error_type="NoClass", error="No class found"
            )
            await self.update_parserlog.update_log(
                log_entry=log, error_info=error_info, add_subinfo=subinfo
            )
            return AskGeminiResult(error_info=error_info)
        try:
            for k, v in exec_scope.items():
                if k == class_type.__name__:
                    continue
                if k in globals():
                    continue
                if k == "annotations":
                    continue
                globals()[k] = v
                logger.debug(f"imported {k} to globals")

            parser_instance = class_type(self.html_str)
            parsed_result = parser_instance.execute()
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

    async def _get_saved_parser(self):
        latest_log = await self.update_parserlog.get_log(
            label=self.label, target_url=self.target_url, is_error=False
        )
        if not latest_log:
            return None, {}

        return await self._get_parser_class(latest_log.response)

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

    async def _get_parser_class(self, result: dict) -> tuple[type | None, dict]:
        if not result.get("candidates"):
            return None

        for part in result["candidates"][0]["content"]["parts"]:
            if not part["text"] or "```python" not in part["text"]:
                continue
            lines = part["text"].splitlines()
            trim_lines = lines[1:-1]
            new_part = "\n".join(["from __future__ import annotations"] + trim_lines)
            exec_scope = {}
            try:
                exec(new_part, globals(), exec_scope)
            except Exception:
                logger.exception("parser exec error")
                return None, {}
            cname = CLASS_NAME_PATTERN.findall(new_part)[0]
            MyClass = exec_scope.get(cname)
            if MyClass is not None and inspect.isclass(MyClass):
                return MyClass, exec_scope
        return None, {}


class HTMLSelectorConfigGenerator:
    html_str: str
    prompt: ParserRequestPrompt
    search_word: str

    def __init__(
        self,
        html_str: str,
        search_word: str,
        prompt: ParserRequestPrompt = ParserRequestPrompt(
            first_prompt_fpath=str(
                CURRENT_PATH / "checking_for_search_result_prompt.txt"
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

        contents = [
            types.Part.from_text(text=self.html_str),
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
