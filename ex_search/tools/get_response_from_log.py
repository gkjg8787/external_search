from bs4 import BeautifulSoup
import re
import inspect
import pathlib
import asyncio
import argparse
from pprint import pprint

from app.gemini_api.parserlog import UpdateParserLog
from databases.sql.ai import repository as ai_repo
from databases.sql import util as db_util
from domain.models.ai import ailog as m_ailog, command as a_cmd


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
    parser.add_argument(
        "-v", "--view", type=str, choices=["all", "text", "meta"], default="all"
    )
    return parser.parse_args()


async def _get_text_and_usage_metadata(result: dict) -> tuple[str, dict]:
    if not result.get("candidates"):
        return "", {}
    text = ""
    for part in result["candidates"][0]["content"]["parts"]:
        text = part["text"]
        break

    return text, result.get("usage_metadata", {})


async def get_parser_log():
    async for db in db_util.get_async_session():
        cmd = a_cmd.ParserGenerationLogGetCommand(is_error=True)
        airepo = ai_repo.ParserGenerationLogRepository(db)
        ret = await airepo.get(cmd)
        print(ret)


async def main():
    argp = set_argparse()

    if not argp.label and not argp.id:
        print("label or id is required")
        return
    if argp.label and argp.id:
        print("cannot specify both label and id")
        return

    view_dict = {
        "text": True,
        "meta": True,
    }
    if argp.view:
        if argp.view == "text":
            view_dict["meta"] = False
        elif argp.view == "meta":
            view_dict["text"] = False

    is_error = None
    if argp.error:
        if argp.error == "true":
            is_error = True
        elif argp.error == "false":
            is_error = False

    label = argp.label
    id = argp.id
    async for db in db_util.get_async_session():
        plog = UpdateParserLog(db, ai_repo.ParserGenerationLogRepository(db))
        log = await plog.get_log(label=label, id=id, is_error=is_error)
        if not log:
            print("log is None")
            return
        print(f"id:{log.id}, updated_at:{log.updated_at}, label:{log.label}")
        if log.error_info:
            print("error_info : ", log.error_info)
        text, metadata = await _get_text_and_usage_metadata(log.response)
        if view_dict["text"]:
            print("=========================================")
            print("text : \n", text)
        if view_dict["meta"]:
            print("=========================================")
            print("usage_metadata : ")
            pprint(metadata)


asyncio.run(main())
# asyncio.run(get_parser_log())
