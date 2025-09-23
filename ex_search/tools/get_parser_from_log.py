from bs4 import BeautifulSoup
import re
import inspect
import pathlib
import asyncio
import argparse
import logging

from app.gemini_api.parserlog import UpdateParserLog
from databases.sql.ai import repository as ai_repo
from databases.sql import util as db_util
from domain.models.ai import ailog as m_ailog, command as a_cmd


log = logging.getLogger(__name__)

CLASS_NAME_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")


def set_argparse():
    parser = argparse.ArgumentParser(
        description="parsergenerationlogからパーサを抜き出します"
    )
    parser.add_argument(
        "--label",
        type=str,
        required=False,
    )
    parser.add_argument(
        "--id",
        type=int,
        required=False,
    )
    parser.add_argument("--error", type=str, choices=["true", "false", "none"])
    parser.add_argument("-f", "--file", type=str, default="output.html")
    parser.add_argument(
        "-v",
        "--view",
        type=str,
        choices=["all", "error", "class", "result"],
        default="all",
    )
    return parser.parse_args()


async def _get_parser_class(result: dict) -> tuple[type | None, str]:
    if not result.get("candidates"):
        return None, "", {}

    for part in result["candidates"][0]["content"]["parts"]:
        if not part["text"] or "```python" not in part["text"]:
            continue
        lines = part["text"].splitlines()
        trim_lines = lines[1:-1]
        new_part = "\n".join(["from __future__ import annotations"] + trim_lines)
        exec_scope = {}
        try:
            exec(new_part, globals(), exec_scope)
        except Exception as e:
            log.exception("exec error")
        cname = CLASS_NAME_PATTERN.findall(new_part)[0]
        MyClass = exec_scope.get(cname)
        return MyClass, new_part, exec_scope
        # if MyClass is not None and inspect.isclass(MyClass):
        #    return MyClass, new_part
    return None, "", {}


async def get_parser_log():
    async for db in db_util.get_async_session():
        cmd = a_cmd.ParserGenerationLogGetCommand(is_error=True)
        airepo = ai_repo.ParserGenerationLogRepository(db)
        ret = await airepo.get(cmd)
        print(ret)


async def main():
    argp = set_argparse()
    print(f"params = {argp}")

    if not argp.label and not argp.id:
        print("label or id is required")
        return
    if argp.label and argp.id:
        print("cannot specify both label and id")
        return

    view_dict = {
        "error": True,
        "class": True,
        "result": True,
    }
    if argp.view:
        if argp.view == "error":
            view_dict["class"] = False
            view_dict["result"] = False
        elif argp.view == "class":
            view_dict["result"] = False
            view_dict["error"] = False
        elif argp.view == "result":
            view_dict["class"] = False
            view_dict["error"] = False

    is_error = None
    if argp.error:
        if argp.error == "true":
            is_error = True
        elif argp.error == "false":
            is_error = False

    html = None
    if argp.file:
        html_path = pathlib.Path(argp.file)
        if html_path.exists():
            html = html_path.read_text()
    label = argp.label
    id = argp.id
    async for db in db_util.get_async_session():
        plog = UpdateParserLog(db, ai_repo.ParserGenerationLogRepository(db))
        log = await plog.get_log(label=label, id=id, is_error=is_error)
        if not log:
            print("log is None")
            return
        print(f"id:{log.id}, updated_at:{log.updated_at}, label:{log.label}")
        if view_dict["error"]:
            print("-------------------------------------------------------")
            print(log.error_info)
        class_type, code_text, scope = await _get_parser_class(log.response)
        if view_dict["class"]:
            print("-------------------------------------------------------")
            print(f"{class_type}, scope:{scope}")
            if code_text:
                print(code_text)
        if view_dict["result"]:
            print("-------------------------------------------------------")
            if html and class_type:
                for k, v in scope.items():
                    if k == class_type.__name__:
                        print("class : ", k)
                        continue
                    if k in globals():
                        print("exist : ", k)
                        continue
                    if k == "annotations":
                        print("not import : ", k)
                        continue
                    globals()[k] = v
                    print("add : ", k)
                parser = class_type(html)
                print(parser.execute())


asyncio.run(main())
# asyncio.run(get_parser_log())
