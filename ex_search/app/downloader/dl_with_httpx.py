import asyncio

import httpx


async def _set_cookies(cookie_dict_list: list[dict]):
    cookies = httpx.Cookies()
    for cookie_dict in cookie_dict_list:
        cookies.set(**cookie_dict)
    return cookies


async def async_get(
    url: str,
    timeout: float = 5,
    max_retries: int = 0,
    delay_seconds: float = 1,
    cookie_dict_list: list[dict] = [],
):
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for attempt in range(max_retries + 1):
            try:
                cookies = await _set_cookies(cookie_dict_list=cookie_dict_list)
                res = await client.get(url, timeout=timeout, cookies=cookies)
                res.raise_for_status()
                return res.text
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < max_retries:
                    await asyncio.sleep(delay_seconds)
                else:
                    raise e
            except Exception as e:
                raise e
