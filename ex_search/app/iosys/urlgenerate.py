from typing import Literal
from urllib.parse import urlencode, quote


def build_search_url(
    search_keyword: str,
    query_encode_type: str = "utf-8",
    condition: Literal["new", "used", "a"] | None = None,
    sort: Literal["l", "h", "vl", "vh"] | None = None,
):
    base_url = "https://iosys.co.jp/items"
    search_query = f"q={quote(search_keyword, encoding=query_encode_type)}"
    param = {
        "not": "",
        "min": "10000",
        "max": "20000",
    }
    if condition:
        param["cond"] = condition
    if sort:
        param["sort"] = sort
    final_url = f"{base_url}?{urlencode(param)}&{search_query}"
    return final_url
