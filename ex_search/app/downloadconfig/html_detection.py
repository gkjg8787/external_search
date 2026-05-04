from typing import Literal
import re
from collections import Counter

from pydantic import BaseModel
from bs4 import BeautifulSoup

import html_detector as hd


class HTMLDetectionResult(BaseModel):
    total_score: int
    keyword_score: int
    keywords_found: list[str]
    input_evaluation_score: int
    input_evaluation_details: dict
    search_result_structure_score: int
    search_result_structure_details: dict
    item_selector: str | None = None
    search_results_selector: str | None = None
    search_results_displayed: Literal["displayed", "zero", "none", "error"]
    error_msg: str = ""


class HTMLDetection(BaseModel):
    score_groups: list[dict] = [
        {
            "score": 30,
            "search_type": "text",
            "words": ["検索結果", "の検索結果"],
        },
        {
            "score": 20,
            "search_type": "selector",
            "words": ["searchresult", "search_result", "search-result"],
        },
        {
            "score": 20,
            "search_type": "text",
            "words": ["該当", "件ヒット"],
        },
        {"score": 10, "search_type": "text", "words": ["件の"]},
        {"score": 10, "search_type": "selector", "words": ["search_item", "itemlist"]},
    ]

    html_str: str
    early_stopping_score: int
    searchword: str | None = None

    def __init__(
        self,
        html_str: str,
        early_stopping_score: int = 40,
        searchword: str | None = None,
        **data,
    ):
        super().__init__(
            html_str=html_str,
            early_stopping_score=early_stopping_score,
            searchword=searchword,
            **data,
        )

    async def prepare_sources(self, html_content: str):
        """HTMLから検索対象のクリーンなテキストを1回だけ生成する"""
        soup = BeautifulSoup(html_content, "lxml")
        # スクリプトとスタイルを除去
        for element in soup(["script", "style"]):
            element.decompose()

        return soup

    async def search_keywords_in_text(
        self, soup, keywords, ignore_case, search_type="text"
    ):
        results = {}
        flags = re.IGNORECASE if ignore_case else 0
        if search_type == "text":
            text = soup.get_text(separator="\n")
            lines = text.splitlines()
        elif search_type == "selector":
            pass
        else:
            raise ValueError("Invalid search type. Use 'text' or 'selector'.")

        for keyword in keywords:
            total_matches = 0
            if search_type == "selector":
                matches = soup.select(f'[id*="{keyword}"],[class*="{keyword}"]')
                if matches:
                    total_matches += len(matches)
            else:
                pattern = re.compile(re.escape(keyword), flags=flags)

                for i, line in enumerate(lines, 1):
                    matches = pattern.findall(line)
                    if matches:
                        total_matches += len(matches)

            results[keyword] = total_matches

        return results

    async def scoring_by_keywords(self):
        soup = await self.prepare_sources(self.html_str)
        total_score = 0
        for score_group in self.score_groups:
            keyword_results = await self.search_keywords_in_text(
                soup,
                score_group["words"],
                ignore_case=True,
                search_type=score_group["search_type"],
            )
            for keyword, result in keyword_results.items():
                if result > 0:
                    total_score += score_group["score"]
                    if (
                        self.early_stopping_score > 0
                        and total_score >= self.early_stopping_score
                    ):
                        return total_score, list(keyword_results.keys())
        return (
            total_score,
            list(keyword_results.keys()) if keyword_results else [],
        )

    async def evaluate_strict_search_result(self, html_content, input_query=None):
        soup = BeautifulSoup(html_content, "lxml")
        score = 0
        details = {}

        # --- 1. 検索ワードとの整合性 ---
        if input_query:
            # リスト要素を特定（前回のロジックで最も頻出したクラスなど）
            # 簡易的にすべての <a> タグ内のテキストで判定
            product_texts = [
                a.get_text() for a in soup.find_all("a") if len(a.get_text()) > 5
            ]
            hit_count = sum(
                1 for text in product_texts if input_query.lower() in text.lower()
            )

            hit_rate = hit_count / len(product_texts) if product_texts else 0
            if hit_rate > 0.3:
                score += 50
                details["keyword_hit_rate"] = "high"
            elif hit_rate > 0.1:
                score += 20
                details["keyword_hit_rate"] = "medium"

            # --- 3. フォーム同期チェック ---
            # inputタグの中に検索ワードが残っているか
            search_input = soup.find(
                "input", {"value": re.compile(f"^{input_query}$", re.I)}
            )
            if search_input:
                score += 20
                details["search_input_sync"] = "matched"

        # --- 2. 厳格な「件数表示」の判定 ---
        text_content = soup.get_text()
        # "1 - 20 / 450" や "500 items found" のような形式を狙う
        strict_count_pattern = [
            r"\d+\s*[--/]\s*\d+\s*(?:件|items|results)",
            r"検索結果[：:\s]*[\d,]+",
            r"of\s*[\d,]+\s*(?:results|items)",
        ]
        if any(re.search(p, text_content, re.IGNORECASE) for p in strict_count_pattern):
            score += 30
            details["strict_count_display"] = "found"

        negative_keywords = ["特集一覧", "おすすめキャンペーン", "閲覧履歴"]
        page_title = soup.title.string if soup.title else ""
        if any(nk in page_title for nk in negative_keywords):
            score -= 40
            details["negative_keyword_in_title"] = "found"

        return score, details

    async def calculate_search_result_score(self, html_content):
        soup = BeautifulSoup(html_content, "lxml")
        score = 0
        report = {}

        # --- Step 2: List Analysis (反復構造の検出) ---
        # 同一階層で同じクラス名を持つ要素をカウント
        all_classes = []
        for tag in soup.find_all(True):
            cls = tag.get("class")
            if cls:
                all_classes.append(".".join(sorted(cls)))

        class_counts = Counter(all_classes)
        # 最も頻出するクラス（商品カード候補）を特定
        # TOPページ対策として、ある程度の複雑性を持つ要素(div, li, section)に限定
        top_repeated_elements = [
            count for cls, count in class_counts.items() if count >= 5
        ]

        step2_score = 0
        if top_repeated_elements:
            max_repeat = max(top_repeated_elements)
            if max_repeat >= 10:
                step2_score = 40
            elif max_repeat >= 5:
                step2_score = 20

        score += step2_score
        report["Step2_RepeatStructure"] = step2_score

        # --- Step 3: Component Check (要素の充足率) ---
        # 最も頻出しているクラスの要素をサンプルとしてチェック
        best_cls = class_counts.most_common(1)[0][0] if all_classes else ""
        sample_items = soup.select(f'.{best_cls.replace(".", ".")}')[:10]

        filling_score = 0
        if sample_items:
            check_results = []
            for item in sample_items:
                has_img = 1 if item.find("img") else 0
                has_link = 1 if item.find("a") else 0
                # 価格表現 (￥, 円, $, 数値の塊)
                has_price = 1 if re.search(r"[￥$¥]|[\d,]{3,}", item.get_text()) else 0
                check_results.append(has_img + has_link + has_price)

            avg_fulfillment = sum(check_results) / len(sample_items)
            if avg_fulfillment >= 2.5:
                filling_score = 30  # 3要素ほぼ揃っている
            elif avg_fulfillment >= 1.5:
                filling_score = 15

        score += filling_score
        report["Step3_ComponentFulfillment"] = filling_score

        # --- Step 4: Meta UI Check (件数・ソート・ページネーション) ---
        ui_score = 0
        text_content = soup.get_text()

        # 件数表示 (例: 100件中、1-20表示、Showing 1-20 of 100)
        if re.search(r"\d+\s*(件|items|results)", text_content) or re.search(
            r"\d+\s*-\s*\d+", text_content
        ):
            ui_score += 15

        # ページネーション (数字が並んでいるか、「次へ」があるか)
        pagination_keywords = ["次へ", "Next", ">", "»", "前へ", "Prev"]
        if any(kw in text_content for kw in pagination_keywords) and re.search(
            r"\d\s+\d\s+\d", text_content
        ):
            ui_score += 10

        # ソート順 (セレクトボックスの存在)
        ok, selection_data = hd.detect(
            html_content, target_type=hd.TargetType.SORT_SELECT_TAG
        )
        if ok and not isinstance(selection_data, list):
            ui_score += 5

        score += ui_score
        report["Step4_MetaUI"] = ui_score

        return score, report

    async def find_item_selector(self, html_content, parent_selector):
        if not isinstance(html_content, str):
            return False, None

        soup = BeautifulSoup(html_content, "lxml")
        parent = soup.select_one(parent_selector)

        if not parent:
            return False, None

        candidates = []
        # 価格パターンの精度向上（円、¥、数字の組み合わせ）
        price_pattern = re.compile(
            r"[¥￥$]\s?\d{1,3}(?:,\d{3})*|\d{1,3}(?:,\d{3})*[円]"
        )

        # 子孫要素を走査
        for element in parent.find_all(True, recursive=True):
            if element == parent:
                continue

            # スコア計算
            has_img = 1 if element.find("img") else 0
            has_a = 1 if element.find("a") else 0
            # get_text() はタグ内の全テキストを拾うため、カード外のノイズを避ける
            text_content = element.get_text(strip=True)
            has_price = 1 if price_pattern.search(text_content) else 0

            score = (has_img * 2) + (has_a * 1) + (has_price * 3)

            # 商品カードとしての最低限の重みをチェック
            if score >= 4:
                class_list = element.get("class")

                # class属性が存在する場合のみ処理
                if class_list:
                    # BeautifulSoupの仕様で、通常はリストだが、稀に文字列の場合があるため考慮
                    if isinstance(class_list, list):
                        # 空の文字列を除去して結合
                        clean_classes = [c for c in class_list if c.strip()]
                        if not clean_classes:
                            continue
                        dot_classes = ".".join(clean_classes)
                    else:
                        dot_classes = class_list.strip()

                    tag_name = element.name
                    selector = f"{tag_name}.{dot_classes}"
                    candidates.append(selector)

        if not candidates:
            return False, None

        # 最も出現頻度が高いセレクターを特定
        selector_counts = Counter(candidates)
        # 最頻値が複数ある可能性も考慮
        most_common_data = selector_counts.most_common(1)

        if not most_common_data:
            return False, None

        most_common_selector = most_common_data[0][0]
        return True, most_common_selector

    async def execute(self):
        total_score = 0
        keyword_score, keywords = await self.scoring_by_keywords()
        total_score += keyword_score
        input_score, input_details = await self.evaluate_strict_search_result(
            self.html_str, input_query=self.searchword
        )
        if input_score > 0:
            total_score += 20
        sresult_score, sresult_details = await self.calculate_search_result_score(
            self.html_str
        )
        if sresult_score >= 60:
            total_score += 20
        score_detail = {
            "total_score": total_score,
            "keyword_score": keyword_score,
            "keywords_found": keywords,
            "input_evaluation_score": input_score,
            "input_evaluation_details": input_details,
            "search_result_structure_score": sresult_score,
            "search_result_structure_details": sresult_details,
        }

        candidate_res = hd.detect(
            self.html_str, target_type=hd.TargetType.SEARCH_RESULT_SELECTOR
        )
        for score, selector in candidate_res:
            if score <= 0:
                return HTMLDetectionResult(
                    **score_detail, search_results_displayed="none"
                )
            ok, item_selector = await self.find_item_selector(self.html_str, selector)
            if ok:
                score_detail["item_selector"] = item_selector
                score_detail["search_results_selector"] = selector
                score_detail["search_results_displayed"] = "displayed"
                return HTMLDetectionResult(**score_detail)
        score_detail["search_results_displayed"] = "none"
        return HTMLDetectionResult(**score_detail)
