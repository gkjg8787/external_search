import re
import pathlib
import inspect

from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types
import structlog

from .models import AskGeminiResult, AskGeminiErrorInfo, ResultItems
from .parserlog import UpdateParserLog
from domain.models.ai import repository as a_repo

logger = structlog.get_logger(__name__)

model_ids = {
    "pro": "gemini-2.5-pro",
    "flash": "gemini-2.5-flash",
    "flash-lite": "gemini-2.5-flash-lite",
    "live": "gemini-live-2.5-flash-preview",
    "image": "gemini-2.5-flash-image-preview",
}
CLASS_NAME_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")
IMPORT_PATTERN = re.compile(r"(?:from\s+(\S+)\s+import\s+(\S+))|(?:import\s+(\S+))")
CURRENT_PATH = pathlib.Path(__file__).resolve().parent


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
