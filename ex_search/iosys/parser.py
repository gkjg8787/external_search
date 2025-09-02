import re

from bs4 import BeautifulSoup

from .model import ParseResult, ParseResults
from .constants import IOSYS, NONE_PRICE


class SearchResultParser:
    html_str: str
    results: ParseResults
    url: str = ""

    def __init__(self, html_str: str, url: str = ""):
        self.html_str = html_str
        self.results = ParseResults()
        self.url = url

    def get_results(self) -> ParseResults:
        return self.results

    def execute(self):
        soup = BeautifulSoup(self.html_str, "html.parser")
        ptn = r"ul.items-container li.item"
        elems = soup.select(ptn)
        if not elems:
            return

        results = ParseResults()
        for elem in elems:
            result = ParseResult()
            result.sitename = IOSYS
            result.image_url = self._get_image_url(elem)
            result.title = self._get_title(elem)
            result.price = self._get_price(elem)
            result.condition = self._get_condition(elem)
            result.is_success = True
            result.manufacturer = self._get_maker(elem)
            result.release_date = self._get_release_date(elem)
            result.accessories = self._get_accessories(elem)
            result.stock_quantity = self._get_stock_quantity(elem)
            result.detail_url = self._get_detail_url(elem)
            result.sub_infos = self._get_sub_infos(elem)
            if self.url:
                result.url = self.url
            results.results.append(result)
        self.results = results

    @classmethod
    def _trim_str(cls, text: str) -> str:
        table = str.maketrans(
            {
                "\u3000": "",
                "\r": "",
                "\n": "",
                "\t": " ",
                "\xa0": " ",
            }
        )
        return text.translate(table).strip()

    def _get_image_url(self, elem) -> str:
        ptn = r"div.photo picture source"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return tag.get("data-srcset", "")

    def _get_title(self, elem) -> str:
        ptn = r"p.name"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text))

    def _get_price(self, elem) -> int:
        ptn = r"div.price p"
        tag = elem.select_one(ptn)
        if not tag:
            return NONE_PRICE
        price = int(re.sub("\\D", "", tag.text))
        return price

    def _get_condition(self, elem) -> str:
        ptn = r"p.condition"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text))

    def _get_maker(self, elem) -> str:
        ptn = r"p.maker"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text).replace("メーカー：", ""))

    def _get_release_date(self, elem) -> str:
        ptn = r"p.release"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text).replace("発売日：", ""))

    def _get_accessories(self, elem) -> str:
        ptn = r"p.accessory"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text).replace("付属品:", ""))

    def _get_stock_quantity(self, elem) -> str:
        ptn = r"p.stock"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        return self._trim_str(str(tag.text).replace("在庫数：", ""))

    def _get_detail_url(self, elem) -> str:
        ptn = r"a"
        tag = elem.select_one(ptn)
        if not tag:
            return ""
        href = tag.get("href", "")
        if href.startswith("http"):
            return href
        return f"https://iosys.co.jp{href}"

    def _get_sub_infos(self, elem) -> dict:
        infos = {}
        ptn = r"div.photo div"
        tags = elem.select(ptn)
        if not tags:
            return infos
        for tag in tags:
            keys = tag.get("class", [])
            if not keys:
                continue
            text = self._trim_str(str(tag.text))
            infos[keys[-1]] = text
        return infos
