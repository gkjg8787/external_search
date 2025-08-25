from domain.schemas.search import search
from geo.model import ParseResults, ParseResult
from .constants import INIT_STOCK_NUM


class ModelConverter:
    @classmethod
    def parseresults_to_searchresults(
        cls, results: ParseResults
    ) -> search.SearchResults:
        searchresults = search.SearchResults()
        for parseresult in results.results:
            if parseresult.detail_url:
                sub_urls = [parseresult.detail_url]
            else:
                sub_urls = None
            searchresult = search.SearchResult(
                title=parseresult.title,
                price=parseresult.price,
                taxin=True,
                condition=parseresult.condition,
                on_sale=parseresult.on_sale,
                salename=parseresult.salename,
                is_success=parseresult.is_success,
                url=parseresult.url,
                sitename=parseresult.sitename,
                image_url=parseresult.image_url,
                stock_msg=parseresult.stock_msg,
                stock_quantity=INIT_STOCK_NUM,
                sub_urls=sub_urls,
                others={"category": parseresult.category},
            )
            searchresults.results.append(searchresult)
        return searchresults
