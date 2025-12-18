import asyncio
from urllib.parse import urlparse
from pathlib import Path
import json

import structlog
import httpx

from common.read_config import get_cookie_dir_path


class CookieManager:
    def __init__(self, filepath: str = "cookies.json"):
        self.filepath = Path(filepath)
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def save_cookies(self, client: httpx.AsyncClient):
        """クライアント内のCookieをファイルに保存する"""
        cookies_dict = client.cookies.jar._cookies
        # httpxの内部構造からシリアライズ可能な形式に変換
        cookie_data = []
        for domain, paths in cookies_dict.items():
            for path, names in paths.items():
                for name, cookie in names.items():
                    cookie_data.append(
                        {
                            "name": cookie.name,
                            "value": cookie.value,
                            "domain": cookie.domain,
                            "path": cookie.path,
                        }
                    )
        if self.filepath.parent != Path("."):
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(json.dumps(cookie_data, indent=2))
        self.logger.debug(f"Cookies saved to {self.filepath}")

    async def load_cookies(
        self, client: httpx.AsyncClient, add_cookies: list[dict] = []
    ):
        """ファイルからCookieを読み込んでクライアントにセットする"""
        if not self.filepath.exists():
            self.logger.warning(f"Cookie file {self.filepath} does not exist.")
            return

        cookie_data = json.loads(self.filepath.read_text())
        for c in cookie_data:
            client.cookies.set(
                c["name"], c["value"], domain=c["domain"], path=c["path"]
            )
        for c in add_cookies:
            client.cookies.set(
                c["name"], c["value"], domain=c.get("domain"), path=c.get("path")
            )


async def _set_cookies(cookie_dict_list: list[dict]):
    cookies = httpx.Cookies()
    for cookie_dict in cookie_dict_list:
        cookies.set(**cookie_dict)
    return cookies


async def add_missing_cookies(domain: str, cookie_dict_list: list[dict]):
    result_cookies = []
    for cookie_dict in cookie_dict_list:
        if cookie_dict.get("name") is None or cookie_dict.get("value") is None:
            return cookie_dict_list
        result_cookies.append(cookie_dict)
        if cookie_dict.get("domain") is None:
            result_cookies["domain"] = domain
        if cookie_dict.get("path") is None:
            result_cookies["path"] = "/"
    return result_cookies


async def async_get(
    url: str,
    timeout: float = 5,
    max_retries: int = 0,
    delay_seconds: float = 1,
    cookie_dict_list: list[dict] = [],
    cookie_save: bool = False,
    cookie_load: bool = False,
):
    if cookie_dict_list is None:
        cookie_dict_list = []

    if cookie_load or cookie_save:
        domain = urlparse(url).netloc
        cookie_manager = CookieManager(
            filepath=f"{get_cookie_dir_path()}/{domain}.json"
        )
    cookie_dict_list = await add_missing_cookies(
        domain=urlparse(url).netloc, cookie_dict_list=cookie_dict_list
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        if cookie_load:
            await cookie_manager.load_cookies(client, add_cookies=cookie_dict_list)
        for attempt in range(max_retries + 1):
            try:
                if not cookie_load:
                    cookies = await _set_cookies(cookie_dict_list=cookie_dict_list)
                    res = await client.get(url, timeout=timeout, cookies=cookies)
                else:
                    res = await client.get(url, timeout=timeout)
                res.raise_for_status()
                if cookie_save:
                    await cookie_manager.save_cookies(client)
                return res.text
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < max_retries:
                    await asyncio.sleep(delay_seconds)
                else:
                    raise e
            except Exception as e:
                raise e
