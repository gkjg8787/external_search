import re
from bs4 import BeautifulSoup
from .model import ParseResult, ParseResults, PageInfo
from .constants import ERROR_IMAGE_URL, NONE_PRICE


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
        results = ParseResults()
        results = self._parse_items(soup)
        results.pageinfo = self._parse_page(soup)
        self.results = results

    def _parse_items(self, soup):
        q = r"ul.itemList li"
        ret = soup.select(q)
        results = ParseResults()
        if len(ret) == 0:
            return results
        for elem in ret:
            result = ParseResult()
            result.title, sub_url = self._get_title(elem)
            result.detail_url = sub_url
            result.image_url = self._get_image(elem)
            result.category = self._get_category(elem)
            result.price = self._get_price(elem)
            result.condition, result.stock_msg = self._get_condition(elem)
            result.is_success = True
            result.url = self.url

            results.results.append(result)
        return results

    def _get_title(self, elem):
        titleo = elem.select(".itemName")
        title = titleo[0].text.replace("\u3000", " ")
        titleurlo = elem.select("a.sendDatalayer")
        sub_url = self._create_geo_full_url(titleurlo[0]["href"])
        return title, sub_url

    def _create_geo_full_url(self, url):
        ptn = r"^/"
        m = re.findall(ptn, url)
        if m is None or len(m) == 0:
            return url
        return "https://ec.geo-online.co.jp" + url

    def _get_category(self, elem):
        cateo = elem.select(".itemCarrier")
        return cateo[0].text.replace("\u3000", " ")

    def _get_image(self, elem):
        imageo = elem.select(".itemImage img")
        if len(imageo) == 0:
            return ERROR_IMAGE_URL
        return imageo[0]["src"]

    def _del_space(self, text):
        return text.replace(" ", "")

    def _trim_str(self, text):
        table = str.maketrans({"\u3000": "", "\n": "", "\xa0": ""})
        return text.translate(table).strip()

    def _trim_html(self, text):
        text = self._del_space(text)
        text = self._trim_str(text)
        return text

    def _get_price(self, elem):
        q = r".sellPtnLeftPrice"
        priceo = elem.select(q)
        pricetext = self._trim_html(priceo[0].text)
        try:
            price = int(re.sub("\\D", "", pricetext))
        except Exception:
            return NONE_PRICE
        return price

    def _get_condition(self, elem):
        q = r".labelSituation"
        tro = elem.select(q)
        condition = ""
        yoyaku = ""
        for tr in tro:
            if "予約" in tr.text:
                yoyaku = tr.text
                continue
            if condition == "":
                condition = tr.text
        return condition, yoyaku

    def _parse_page_num(self, soup):
        q = r".pager li"
        pages = soup.select(q)
        if len(pages) == 0:
            return 0, 0
        text = str(pages)
        ptn = r">([0-9]+)<"
        m = re.findall(ptn, text)
        pmin = -1
        pmax = -1
        for v in m:
            if pmin == -1:
                pmin = int(v)
                pmax = int(v)
                continue
            if pmin > int(v):
                pmin = int(v)
            if pmax < int(v):
                pmax = int(v)
        return pmin, pmax

    def _parse_page(self, soup):
        result = PageInfo()
        result.min_page, result.max_page = self._parse_page_num(soup)
        if (
            result.min_page > 0
            and result.max_page > 0
            and result.min_page != result.max_page
        ):
            result.enable = True
        result.current_page = self._get_current_page(soup)
        result.more_page = self._get_more_page(soup)
        return result

    def _get_current_page(self, soup):
        q = r".pager li.current"
        cur = soup.select(q)
        if not cur:
            return 0
        return int(cur[0].text)

    def _get_more_page(self, soup):
        q = r".pager li.next"
        moreo = soup.select(q)
        if len(moreo) == 0:
            return False
        nmo = moreo[0].get("class")
        if "noMove" in nmo:
            return False
        return True
