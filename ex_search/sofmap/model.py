from pydantic import BaseModel, Field

NONE_PRICE = -1
NONE_POINT = 0
NONE_STOCK_NUM = 0

# リコレ非対応
SOFMAP = "sofmap"
A_SOFMAP = "akiba sofmap"


class ParseResult(BaseModel):
    title: str = ""
    price: int = NONE_PRICE
    condition: str = ""
    on_sale: bool = False
    salename: str = ""
    is_success: bool = False
    url: str = ""
    sitename: str = SOFMAP
    image_url: str = ""
    stock_msg: str = ""
    brand: str = ""
    release_date: str = ""
    point: int = NONE_POINT
    stock_quantity: int = NONE_STOCK_NUM
    used_list_url: str = ""
    sub_price: int = NONE_PRICE
    shops_with_stock: str = ""


class ParseResults(BaseModel):
    results: list[ParseResult] = Field(default_factory=list)


class CategoryResult(BaseModel):
    gid_to_name: dict[str, str] = Field(default_factory=dict)
    name_to_gid: dict[str, str] = Field(default_factory=dict)

    def set_gid_and_category_name(self, gid: str, category_name: str):
        self.gid_to_name[gid] = category_name
        self.name_to_gid[category_name] = gid

    def get_gid(self, category_name: str) -> str:
        return self.name_to_gid.get(category_name, "")

    def get_category_name(self, gid: str) -> str:
        return self.gid_to_name.get(gid, "")
