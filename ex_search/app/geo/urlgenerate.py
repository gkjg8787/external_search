from urllib.parse import urlencode, quote


def build_search_url(
    search_keyword: str,
    query_encode_type: str = "shift_jis",
):
    base_url = "https://ec.geo-online.co.jp/shop/goods/search.aspx"
    search_query = f"keyword={quote(search_keyword, encoding=query_encode_type)}"
    search_query += f"&submit1={quote("送信", encoding=query_encode_type)}"
    param = {
        "search": "x",
    }
    final_url = f"{base_url}?{urlencode(param)}&{search_query}"
    return final_url
