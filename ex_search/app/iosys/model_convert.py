from domain.schemas.search import search
from iosys.model import ParseResults


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
                stock_quantity=parseresult.stock_quantity,
                sub_urls=sub_urls,
                others={
                    "manufacturer": parseresult.manufacturer,
                    "release_date": parseresult.release_date,
                    "accessories": parseresult.accessories,
                }
                | parseresult.sub_infos,
            )
            searchresults.results.append(searchresult)
        return searchresults
