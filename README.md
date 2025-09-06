# external_search

## 概要

- 検索した結果を返す API

## 目次

- [対応サイト](#対応サイト)
- [前提](#前提)
- [起動](#起動)
- [使い方](#使い方)
  - [検索](#検索)
    - [検索の例](#検索の例)
    - [sofmap の検索オプション](#sofmap-の検索オプション)
    - [geo の検索オプション](#geo-の検索オプション)
    - [Response のパラメータ](#response-のパラメータ)
  - [カテゴリー一覧の取得](#カテゴリー一覧の取得)
    - [カテゴリーのオプション](#カテゴリーのオプション)
    - [カテゴリー一覧の取得例](#カテゴリー一覧の取得例)
  - [gemini](#gemini)
    - [gemini の検索オプション](#gemini-の検索オプション)
    - [gemini の検索例](#gemini-の検索例)

## 対応サイト

- sofmap
  - 検索結果`https://www.sofmap.com/search_result.aspx`に対応。個別ページ`https://www.sofmap.com/product_detail.aspx`には非対応。akiba sofmap`https://a.sofmap.com/`も同様。
- geo
  - 検索結果`https://ec.geo-online.co.jp/shop/goods/search.aspx`に対応。個別ページ`https://ec.geo-online.co.jp/shop/g/`には非対応。
- iosys

  - 検索結果`https://iosys.co.jp/items?q=`に対応。個別ページ`https://iosys.co.jp/items/`には非対応。

- その他のサイト
  - gemini api を使用して指定ページのパーサを作り、取得した情報を返す。パーサ作成に失敗したりもする。詳細は[gemini によるパーサ作成スクレイピング](#gemini)を参照。

[TOP](#概要)

## 前提

- docker 導入済み
- .env ファイルを用意する。(※gemini api を使用する場合は`GEMINI_API_KEY`を.env に記述)

[TOP](#概要)

## 起動

- `docker compose up --build -d`

[TOP](#概要)

## 使い方

- api には検索の search と検索で使用するカテゴリー一覧の取得の search/info がある。

[TOP](#概要)

### 検索

- このサーバの`/api/search/`を POST し JSON でパラメータを指定する。以下は必須パラメータ。

| パラメータ名   | 説明                                 | 設定する値             | デフォルト |
| -------------- | ------------------------------------ | ---------------------- | ---------- |
| url            | データを取得したい URL を直接指定    | 有効な URL             |            |
| search_keyword | URL を指定しない場合の検索キーワード | 検索したい文字列       |            |
| sitename       | 検索対象のサイト(必須)               | sofmap or geo or iosys |            |
| options        | 検索や動作のオプション               | dict 型                |            |

- 応答は以下の形式で返ってくる。
  - 正常:`{"results":[] , "error_msg":""}`
    - results の値として list 型で取得したデータを返す。
  - 異常:`{"results":[], "error_msg":""}` または `{"detail":""}`としてメッセージエラーが乗って返る。

[TOP](#概要)

#### 検索の例

- curl

```
curl -X 'POST' \
  'http://localhost:8060/api/search/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "url": "https://www.sofmap.com/search_result.aspx?product_type=USED&new_jan=4902370536485&gid=001240&keyword=%83%7d%83%8a%83I%83J%81%5b%83g8",
  "search_keyword": "",
  "sitename": "sofmap",
  "options": {
  }
}'
```

- response

```
{
  "results": [
    {
      "title": "〔中古品〕 マリオカート８ デラックス",
      "price": 4980,
      "taxin": true,
      "condition": "RankA",
      "on_sale": false,
      "salename": "",
      "is_success": true,
      "url": "https://www.sofmap.com/search_result.aspx?product_type=USED&new_jan=4902370536485&gid=001240&keyword=%83%7d%83%8a%83I%83J%81%5b%83g8",
      "sitename": "sofmap",
      "image_url": "https://image.sofmap.com/images/product/large/4902370536485.jpg",
      "stock_msg": "",
      "stock_quantity": 24,
      "sub_urls": null,
      "shops_with_stock": "AKIBA アミューズメント館",
      "others": {
        "point": 0,
        "sub_price": -1
      }
    }
  ],
  "error_msg": ""
}
```

[TOP](#概要)

#### sofmap の検索オプション

- sitename に sofmap を指定した際のオプションで`{"name":"value"}`の形で指定する。複数の場合は`{"name1":"value1", "name2":"value2"}`というようにカンマで区切る。value は型に合わせた書き方で。
- ページ指定はないので結果が多い場合は検索ワードや gid で絞る必要がある。

| オプション名             | 説明                                                                                                                                                         | 設定する値           | 有効な種別。URL なら URL 指定の際に動作 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------- | --------------------------------------- |
| convert_to_direct_search | URL が`https://〜search_result.aspx`の場合、`https://〜product_list_parts.aspx`に変更する。selenium ではなく httpx で取得するため動作が軽い。                | true or false        | URL or keyword                          |
| gid                      | カテゴリー ID                                                                                                                                                | `001240`などの文字列 | keyword                                 |
| is_akiba                 | akiba sofmap で検索する。                                                                                                                                    | true                 | keyword                                 |
| direct_search            | convert_to_direct_search と同様で検索する URL を`product_list_parts.aspx`にする。                                                                            | true                 | keyword                                 |
| product_type             | 商品コンディション                                                                                                                                           | USED or NEW or ALL   | keyword                                 |
| order_by                 | 並び順                                                                                                                                                       | DEFAULT 等           | keyword                                 |
| display_count            | 表示数                                                                                                                                                       | 数値                 | keyword                                 |
| category                 | gid を指定していない場合でカテゴリーを文字列で指定。サイトの検索カテゴリ名と完全一致が必要。`家電・照明`のような複数が一行になっているものも完全一致が必要。 | ゲーム等             | keyword                                 |
| remove_duplicates        | 検索結果の重複を削除する。検索サイトにより動作が違う。sofmap は店舗名以外が同じ場合重複扱い。デフォルトは true で重複削除。                                  | true or false        | URL or keyword                          |

[TOP](#概要)

#### geo の検索オプション

- ゲオには検索オプションなし。

[TOP](#概要)

#### iosys の検索オプション

- sitename に iosys を指定した際のオプションで`{"name":"value"}`の形で指定する。複数の場合は`{"name1":"value1", "name2":"value2"}`というようにカンマで区切る。value は型に合わせた書き方で。
- ページ指定はない

| オプション名 | 説明                                                                       | 設定する値         |
| ------------ | -------------------------------------------------------------------------- | ------------------ |
| condition    | 商品の状態。新品/未使用品、中古（全般）、ランク A                          | new or used or a   |
| sort         | 並び順。l:価格が安い順、h:価格が高い順、vh:在庫が多い順、vl:在庫が少ない順 | l or h or vh or vl |
| min_price    | 下限価格                                                                   | 数値               |
| max_price    | 上限価格                                                                   | 数値               |

[TOP](#概要)

#### Response のパラメータ

- results の値の取得したデータの説明。価格がない場合は price:-1 になる。

| key 名           | 説明                                                             | 設定される値  |
| ---------------- | ---------------------------------------------------------------- | ------------- |
| title            | 商品名                                                           | 文字列        |
| price            | 商品の価格                                                       | 数値          |
| taxin            | 税込かどうか。現状税込固定                                       | true          |
| condition        | 商品の状態。画像左上に表示されているランク表示が主に設定される。 | 文字列        |
| on_sale          | セール中か。現在未設定                                           | false         |
| salename         | セール名。現在未設定                                             | 文字列        |
| is_success       | 取得に成功しているか。在庫はあるか。                             | true or false |
| url              | 検索した URL。キーワード指定だと生成された URL                   | 文字列        |
| sitename         | 検索対象のサイト名                                               | 文字列        |
| image_url        | 画像の URL                                                       | 文字列        |
| stock_msg        | 在庫関連の情報                                                   | 文字列        |
| stock_quantity   | 在庫数                                                           | 数値          |
| sub_urls         | 中古一覧等がある場合、ここに設定される。相対パス                 | list or null  |
| shops_with_stock | 取り扱い店舗名。設定されない場合もある。                         | 文字列        |
| others           | その他の情報。サイトによって違う。                               | dict          |

- sofmap の others

| key 名    | 説明                               | 設定される値 |
| --------- | ---------------------------------- | ------------ |
| point     | 付与されるポイント                 | 数値         |
| sub_price | 中古等のリンクがある場合の中古価格 | 数値         |

- geo の others

| key 名   | 説明             | 設定される値 |
| -------- | ---------------- | ------------ |
| category | 対象のカテゴリー | 文字列       |

- iosys の others
  - 下記以外にも製品の種類により key-value が入る。例.`{"docomo":"", "volume":"64GB", "sim_size":"nanosim"}` , `{"top":"Win11搭載", "wifi":"Wi-Fiモデル"}`など

| key 名       | 説明       | 設定される値 |
| ------------ | ---------- | ------------ |
| manufacturer | メーカー名 | 文字列       |
| release_date | 発売日     | 日時         |
| accessories  | 付属品     | 文字列       |

[TOP](#概要)

### カテゴリー一覧の取得

- `/api/search/info`を POST し JSON でパラメータを指定する。
- sofmap のみ対応。

| パラメータ名 | 説明           | 設定する値 | デフォルト |
| ------------ | -------------- | ---------- | ---------- |
| sitename     | 対象サイト名   | sofmap     |            |
| infoname     | 取得する情報名 | category   |            |
| options      | オプション     | dict       |            |

[TOP](#概要)

#### カテゴリーのオプション

- 現在オプションはアキバソフマップを対象にするかどうかの`is_akiba`のみ。<br>
  `{"is_akiba":true}`

[TOP](#概要)

#### カテゴリー一覧の取得例

- curl

```
curl -X 'POST' \
  'http://localhost:8060/api/search/info/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "sitename": "sofmap",
  "infoname": "category",
  "options": {

  }
}'
```

- response

```
{
  "results": [
    {
      "gid": "",
      "name": "全てのカテゴリ"
    },
    {
      "gid": "001010",
      "name": "パソコン"
    },
    {
      "gid": "001020",
      "name": "ゲーミングPC・周辺機器"
    },
    : 多いので省略
  ],
  "error_msg": ""
}
```

[TOP](#概要)

### gemini

- gemini api を使用したスクレイピング。直接 URL を AI にスクレイピングしてもらうのではなくパーサを作成してもらいそれを活用する。URL のダウンロードは selenium or httpx を使用するがボット対策などされているサイトの場合はダウンロードができないので対象外。
- 使い方は[検索](#検索)と同じ API(`api/search`)を使用する。
- ラベルに対してパーサを作成する。
- パーサを新規作成時は時間がかかる。うまく作成できない場合は何度かやり直す必要がある。gemini api にはリクエスト制限があるので注意。

| パラメータ名   | 説明                                                       | 設定する値 | デフォルト |
| -------------- | ---------------------------------------------------------- | ---------- | ---------- |
| url            | データを取得したい URL を直接指定                          | 有効な URL |            |
| search_keyword | gemini では未使用だが必須。                                |            |            |
| sitename       | gemini を指定。結果に入れるサイト名は options で設定する。 | gemini     |            |
| options        | 検索や動作のオプション                                     | dict 型    |            |

[TOP](#概要)

#### gemini の検索オプション

- gemini の options に設定するパラメータ。

| オプション名    | 説明                                                                                                                  | 設定する値    |
| --------------- | --------------------------------------------------------------------------------------------------------------------- | ------------- |
| sitename        | 返却するアイテム情報に含むサイト名                                                                                    | 文字列        |
| label           | 作成したパーサのラベル。別の URL、または同じ URL で作成済みの同じパーサを使いたい場合は一致したものにする必要がある。 | 文字列        |
| recreate_parser | label で指定した作成済みパーサがある場合、再作成するかどうか。                                                        | true or false |
| selenium        | ダウンロードする方法を selenium(chrome)を指定する場合のオプション。                                                   | dict          |

- selenium のオプション

| オプション名      | 説明                                                 | 設定する値    |
| ----------------- | ---------------------------------------------------- | ------------- |
| use_selenium      | true だと selenium を使用。                          | true or false |
| wait_css_selector | 指定したタグ(css セレクタ)が描写されるまで待つ       | 文字列        |
| page_load_timeout | ページの読み込みのタイムアウト秒                     | 数値          |
| tag_wait_timeout  | wait_css_selector で指定したタグのタイムアウト秒     | 数値          |
| page_wait_time    | wait_css_selector を指定しない場合の読み込み待ち時間 | 数値          |

[TOP](#概要)

#### gemini の検索例

- curl

```
curl -X 'POST' \
  'http://localhost:8060/api/search/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "url": "https://used.sofmap.com/r/category/smp?categories1%5B%5D=smp",
  "search_keyword": "",
  "sitename": "gemini",
  "options": {
    "sitename":"sofmap",
    "label":"https://used.sofmap.com/r/category/",
    "recreate_parser":true,
    "selenium":{
        "use_selenium":true,
        "wait_css_selector":"#search-result-div"
    }
  }
}'
```

- response
  - AI によるパーサ生成のため取得できる情報は異なる結果になる場合があります。

```
{
  "results": [
    {
      "title": "〔中古品〕 Speed Wi-Fi 5G X12 NAR03SKU シャドーブラック SIMフリー",
      "price": 5880,
      "taxin": true,
      "condition": "中古 (複数在庫あり)",
      "on_sale": false,
      "salename": "",
      "is_success": true,
      "url": "https://used.sofmap.com/r/category/smp?categories1%5B%5D=smp",
      "sitename": "sofmap",
      "image_url": "https://image.sofmap.com/images/product/large/2133058365680_1.jpg",
      "stock_msg": "",
      "stock_quantity": 3,
      "sub_urls": [
        "/r/item?_matome=0&categories1%5B%5D=smp&jan=4941787119393&_returnto=%2Fr%2Fcategory%2Fsmp%3Fcategories1%255B%255D%3Dsmp#product-search-matome"
      ],
      "shops_with_stock": null,
      "others": {
        "brand": "WIMAX"
      }
    },
    : 多いので省略
  ],
  "error_msg": ""
}
```

[TOP](#概要)
