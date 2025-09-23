import asyncio
from typing import Any

import httpx
from pydantic import BaseModel

from domain.schemas.search import search as schema
from common.read_config import get_nodriver_options


class DownloadResponse(BaseModel):
    result: str = ""
    cookies: list[dict[str, Any]] = []
    error: schema.ErrorDetail = schema.ErrorDetail()


async def get_from_nodriver_api(
    url: str,
    nodriver_options: schema.NodriverOptions,
    timeout: float = 30,
    max_retries: int = 0,
    delay_seconds: float = 1,
):
    nodriver_config = get_nodriver_options()
    api_url = f"{nodriver_config.base_url}/download"
    data = {
        "url": url,
    } | nodriver_options.model_dump(mode="json", exclude_none=True)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for attempt in range(max_retries + 1):
            try:
                res = await client.post(api_url, timeout=timeout, json=data)
                res.raise_for_status()
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < max_retries:
                    await asyncio.sleep(delay_seconds)
                else:
                    raise e
            except Exception as e:
                raise e
        res_json = res.json()
        if not isinstance(res_json, dict):
            raise ValueError(
                f"invalid type response, type:{type(res_json).__name__}, {res_json}"
            )
        return DownloadResponse(**res_json)
