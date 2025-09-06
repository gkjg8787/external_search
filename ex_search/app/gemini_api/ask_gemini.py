import re
import pathlib
import inspect
from typing import Any, List, Dict
from urllib.parse import urljoin


from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types
from bs4 import BeautifulSoup

from .models import AskGeminiResult, AskGeminiErrorInfo, ResultItems
from .parserlog import UpdateParserLog
from domain.models.ai import repository as a_repo


model_ids = {
    "pro": "gemini-2.5-pro",
    "flash": "gemini-2.5-flash",
    "flash-lite": "gemini-2.5-flash-lite",
    "live": "gemini-live-2.5-flash-preview",
    "image": "gemini-2.5-flash-image-preview",
}
CLASS_NAME_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")


class ParserRequestPrompt:
    first_prompt_fpath: str

    def __init__(
        self,
        first_prompt_fpath: str = str(
            pathlib.Path(__file__).resolve().parent / "first_prompt.md"
        ),
    ):
        self.first_prompt_fpath = first_prompt_fpath

    def get_first_prompt(self) -> str:
        p = pathlib.Path(self.first_prompt_fpath)
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")


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
            class_type = await self._get_saved_parser()

        if class_type is None:
            client = genai.Client()
            result_dict = await self._request_parser(client=client)
            if isinstance(result_dict, AskGeminiErrorInfo):
                return AskGeminiResult(error_info=result_dict)
            class_type = await self._get_parser_class(result_dict)
            log = await self._save_log(response=result_dict, error_info=None)
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
            return None

        class_type = await self._get_parser_class(latest_log.response)
        return class_type

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
        first_prompt = self.prompt.get_first_prompt()
        if not first_prompt:
            return AskGeminiErrorInfo(error_type="NoPrompt", error="No first prompt")

        contents = [
            types.Part.from_text(text=self.html_str),
            first_prompt,
        ]
        try:
            response = await client.aio.models.generate_content(
                model=model_ids["flash"],
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(code_execution=types.ToolCodeExecution)],
                ),
            )
            return response.model_dump()
        except Exception as e:
            return AskGeminiErrorInfo(error_type=type(e).__name__, error=str(e))

    async def _get_parser_class(self, result: dict) -> type | None:
        if not result.get("candidates"):
            return None

        for part in result["candidates"][0]["content"]["parts"]:
            if "```python" not in part["text"]:
                continue
            lines = part["text"].splitlines()
            trim_lines = lines[1:-1]
            new_part = "\n".join(trim_lines)
            exec_scope = {}
            exec(new_part, globals(), exec_scope)
            cname = CLASS_NAME_PATTERN.findall(new_part)[0]
            MyClass = exec_scope.get(cname)
            if MyClass is not None and inspect.isclass(MyClass):
                return MyClass
        return None
