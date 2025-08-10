from urllib.parse import urlencode, quote
from enum import auto

from common.enums import AutoUpperName
from .constants import (
    BASE_SEARCH_URL,
    A_BASE_SEARCH_URL,
    DIRECT_SEARCH_URL,
    A_DIRECT_SEARCH_URL,
    SHIFT_JIS,
    DEFAULT_SEARCH_DISPLAY_COUNT,
)


class ProductTypeOptions(AutoUpperName):
    NEW = auto()
    USED = auto()
    ALL = auto()


class OrderByOptions(AutoUpperName):
    DEFAULT = auto()
    SALES_DESC = auto()
    PRICE_ASC = auto()
    PRICE_DESC = auto()
    NAME_ASC = auto()
    MAKER_ASC = auto()
    DATE_DESC = auto()
    DATE_ASC = auto()

    @classmethod
    def is_name_in_enum(cls, name: str) -> bool:
        return name.upper() in cls.__members__


def build_search_url(
    search_keyword: str,
    is_akiba: bool = False,
    direct_search: bool = False,
    query_encode_type: str = SHIFT_JIS,
    gid: str = "",
    product_type: str = "",
    display_count: int = DEFAULT_SEARCH_DISPLAY_COUNT,
    order_by: str = OrderByOptions.DEFAULT.name,
) -> str:
    if direct_search:
        if is_akiba:
            base_url = A_DIRECT_SEARCH_URL
        else:
            base_url = DIRECT_SEARCH_URL
    elif is_akiba:
        base_url = A_BASE_SEARCH_URL
    else:
        base_url = BASE_SEARCH_URL
    search_query = f"keyword={quote(search_keyword, encoding=query_encode_type)}"

    param = {
        "gid": gid,
        "dispcnt": display_count,
    }
    if product_type and product_type.upper() in [pt.name for pt in ProductTypeOptions]:
        param["product_type"] = product_type.upper()
    if OrderByOptions.is_name_in_enum(name=order_by):
        param["order_by"] = order_by.upper()
    final_url = f"{base_url}?{urlencode(param)}&{search_query}"
    return final_url
