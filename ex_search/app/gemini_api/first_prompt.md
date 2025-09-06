## あなたは Python3.13 の熟練した開発者です。

### 要求事項

- 渡した HTML をサンプルにパーサクラスを作成してください。
- コンストラクタに HTML 文字列を渡せるようにして下さい。
- execute()メソッドでパーサを実行するようにして下さい。excute()では list[dic]t 型でパーサした結果を返却してください。
- 使用してよいライブラリは`re`と`bs4`です。
- パーサする内容は返却する list[dict]のサンプルに当てはまるようにして下さい。

### execute()で返却する list[dict]の dict の key のサンプル

- title : 商品のタイトル : str
- price : 商品の価格 : int
- condition : 商品の状態 ( 新品、中古など) : str
- on_sale : 商品が割引中かどうか : bool
- is_success : 在庫があるか : bool
- image_url : 商品の画像の URL : str
- stock_quantity : 商品の在庫数 ( 分からない場合は 0) : int
- point : 商品購入時にもらえるポイント（わからない場合は 0) : int
- others : その他の商品固有の情報。 :dict
- detail_url : 商品への URL : str
