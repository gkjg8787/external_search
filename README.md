# external_search

## 概要

- 検索した結果を返す API

## 対応サイト

- sofmap
  - 検索結果`https://www.sofmap.com/search_result.aspx`に対応。個別ページ`https://www.sofmap.com/product_detail.aspx`には非対応。akiba sofmap`https://a.sofmap.com/`も同様。

## 前提

- docker 導入済み

## 起動

- `docker compose up --build -d`

## 使い方

- api には検索の search と検索で使用するカテゴリー一覧の取得の search/info がある。

### 検索

- このサーバの`/api/search/`を POST し JSON でパラメータを指定する。

| パラメータ名   | 説明                                 | 設定する値       | デフォルト |
| -------------- | ------------------------------------ | ---------------- | ---------- |
| url            | データを取得したい URL を直接指定    | 有効な URL       | null       |
| search_keyword | URL を指定しない場合の検索キーワード | 検索したい文字列 | null       |
| sitename       | 検索対象のサイト(必須)               | sofmap 等        |            |
| options        | 検索や動作のオプション               | dict 型          | {}         |

- 応答は以下の形式で返ってくる。
  - 正常:`{"results":[] , "error_msg":""}`
    - results の値として list 型で取得したデータを返す。
  - 異常:`{"results":[], "error_msg":""}` または `{"detail":""}`としてメッセージエラーが乗って返る。

#### 例

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

### カテゴリー一覧の取得

- `/api/search/info`を POST し JSON でパラメータを指定する。

| パラメータ名 | 説明           | 設定する値 | デフォルト |
| ------------ | -------------- | ---------- | ---------- |
| sitename     | 対象サイト名   | sofmap     |            |
| infoname     | 取得する情報名 | category   |            |
| options      | オプション     | dict       |            |

#### カテゴリーのオプション

- 現在オプションはアキバソフマップを対象にするかどうかの`is_akiba`のみ。<br>
  `{"is_akiba":true}`

#### 例

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
