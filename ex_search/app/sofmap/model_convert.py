from domain.schemas.search import search
from sofmap.model import ParseResults, ParseResult


class ModelConverter:
    @classmethod
    def parseresults_to_searchresults(
        cls, results: ParseResults, remove_duplicates: bool = True
    ) -> search.SearchResults:
        if remove_duplicates:
            new_results = cls.remove_duplicates_of_parseresults(
                results=results, update_stock_quantity=True
            )
        else:
            new_results = results
        searchresults = search.SearchResults()
        for parseresult in new_results.results:
            if parseresult.used_list_url:
                sub_urls = [parseresult.used_list_url]
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
                stock_quantity=parseresult.stock_quantity,
                sub_urls=sub_urls,
                shops_with_stock=parseresult.shops_with_stock,
                others={
                    "point": parseresult.point,
                    "sub_price": parseresult.sub_price,
                },
            )
            searchresults.results.append(searchresult)
        return searchresults

    @classmethod
    def remove_duplicates_of_parseresults(
        cls, results: ParseResults, update_stock_quantity: bool = True
    ):
        """
        update_stock_quantity : stock_quantityが初期値ゼロの場合のみ更新する。元から値が入っている場合は変更しない。
        """

        def is_update_stock_quantity(p: ParseResult):
            return update_stock_quantity and p.stock_quantity == 0

        unique_results = ParseResults()
        unique_dict: dict[str, ParseResult] = {}
        update_stock_dict: dict[str, ParseResult] = {}
        exclude_value = {"shops_with_stock"}
        for result in results.results:
            result_str = result.model_dump_json(exclude=exclude_value)
            if not unique_results.results:
                unique_results.results.append(result)
                unique_dict[result_str] = result
                if is_update_stock_quantity(result):
                    result.stock_quantity = 1
                    update_stock_dict[result_str] = result
                continue
            if result_str in unique_dict:
                if update_stock_quantity and result_str in update_stock_dict:
                    unique_dict[result_str].stock_quantity += 1
                continue
            unique_results.results.append(result)
            unique_dict[result_str] = result
            if is_update_stock_quantity(result):
                result.stock_quantity = 1
                update_stock_dict[result_str] = result
        return unique_results
