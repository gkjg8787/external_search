import pytest
import json

from fastapi.testclient import TestClient

from main import app
from domain.schemas.search import SearchRequest, SearchResponse
from domain.schemas.search.search import SearchResult
from app.search_api.enums import SupportedSiteName

client = TestClient(app)
prefix = "/api"


class TestSearch:

    def test_api_get_search_result_no_json(test_db, mocker):
        response = client.post(f"{prefix}/search/")
        assert response.status_code == 422

    def test_api_get_search_result_sofmap_url(test_db, mocker):
        url = "https://www.sofmap.com/search_result.aspx?gid=001240&keyword=%83%7D%83%8A%83I%83J%81%5B%83g%83%8F%81%5B%83%8B%83h"
        reqdata = SearchRequest(
            url=url,
            sitename=SupportedSiteName.SOFMAP.value,
            options={},
        )
        response = client.post(
            f"{prefix}/search/", json=json.loads(reqdata.model_dump_json())
        )
        assert response.status_code == 200
        correct_dict_list = [
            {
                "title": "マリオカート ワールド 【Switch2ゲームソフト】",
                "price": 9480,
                "taxin": True,
                "condition": "",
                "on_sale": False,
                "salename": "",
                "is_success": True,
                "url": url,
                "sitename": SupportedSiteName.SOFMAP.value,
                "image_url": "https://image.sofmap.com/images/product/large/4902370553260.jpg",
                "stock_msg": "在庫限り（1）",
                "stock_quantity": 1,
                "sub_urls": None,
                "shops_with_stock": "",
                "others": {
                    "point": 948,
                    "sub_price": -1,
                },
            }
        ]
        searchresults = [SearchResult(**d) for d in correct_dict_list]
        correct = SearchResponse(results=searchresults)
        assert response.json() == json.loads(correct.model_dump_json())
