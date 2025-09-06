from domain.schemas.search import search
from .models import ResultItems, ResultItem
from .constants import INIT_STOCK_NUM


class ModelConverter:
    @classmethod
    def resultitems_to_searchresults(
        cls,
        results: ResultItems,
        sitename: str = "",
        url: str = "",
        remove_duplicates: bool = False,
    ) -> search.SearchResults:
        if remove_duplicates:
            new_results = cls.remove_duplicates_of_resultitems(
                results=results, update_stock_quantity=True
            )
        else:
            new_results = results
        searchresults = search.SearchResults()
        for item in new_results.items:
            if item.detail_url:
                sub_urls = [item.detail_url]
            else:
                sub_urls = None
            searchresult = search.SearchResult(
                title=item.title,
                price=item.price,
                taxin=True,
                condition=item.condition,
                on_sale=item.on_sale,
                salename="",
                is_success=item.is_success,
                url=url,
                sitename=sitename,
                image_url=item.image_url,
                stock_msg="",
                stock_quantity=item.stock_quantity,
                sub_urls=sub_urls,
                others=item.others,
            )
            searchresults.results.append(searchresult)
        return searchresults

    @classmethod
    def remove_duplicates_of_resultitems(
        cls, results: ResultItems, update_stock_quantity: bool = True
    ):
        """
        update_stock_quantity : stock_quantityが初期値ゼロの場合のみ更新する。元から値が入っている場合は変更しない。
        """

        def is_update_stock_quantity(p: ResultItem):
            return update_stock_quantity and p.stock_quantity == 0

        unique_results = ResultItems()
        unique_dict: dict[str, ResultItem] = {}
        update_stock_dict: dict[str, ResultItem] = {}
        for result in results.items:
            result_str = result.model_dump_json()
            if not unique_results.items:
                unique_results.items.append(result)
                unique_dict[result_str] = result
                if is_update_stock_quantity(result):
                    result.stock_quantity = 1
                    update_stock_dict[result_str] = result
                continue
            if result_str in unique_dict:
                if update_stock_quantity and result_str in update_stock_dict:
                    unique_dict[result_str].stock_quantity += 1
                continue
            unique_results.items.append(result)
            unique_dict[result_str] = result
            if is_update_stock_quantity(result):
                result.stock_quantity = 1
                update_stock_dict[result_str] = result
        return unique_results
