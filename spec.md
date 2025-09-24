# 元素周期表EPUB 自動生成仕様書（v1）

## 0. 概要

* **名前**：PeriodicTable for Kindle（仮）
* **目的**：Kindle端末のスリープ画面で**表紙＝周期表**を参照でき、本文で**拡大版・族/周期別表・索引・凡例**を素早く引ける“参照特化EPUB”。
* **入力**：Wikipediaから取得した元素マスタ & 表データ
* **出力**：`dist/PeriodicTable.en.epub`（言語別の多言語展開に備え命名）、表紙画像（`cover_2560x1600.jpg` ほか）、生成ログ。
* **ビルド環境**：

  * 優先：Codex（ネット接続可）でPythonスクリプト実行
  * 代替：GitHub Actions（Ubuntu）で同スクリプト実行（キャッシュ・再現性担保）

---

## 1. データ取得方針

### 1.1 出典とライセンス

* **出典**：英語版Wikipedia（既定）
* **ライセンス**：Wikipediaのテキストは**CC BY-SA 4.0**（およびGFDL）で提供。**TASL原則（Title/Author/Source/License）に基づく帰属**をEPUB巻末に自動生成すること。 ([ウィキペディア][1])

### 1.2 取得API（いずれか／併用許可）

* **Wikimedia REST API**（推奨）：ページHTML/サマリ取得（安定・簡便）

  * `GET /core/v1/{project}/{lang}/page/{title}/html` でHTMLを取得、`wikitable`抽出。 ([api.wikimedia.org][2])
* **MediaWiki Action API**：wikitextのparseで表をHTML化（フォールバック） ([MediaWiki][3])
* **テーブル抽出**：周期表の代表ページ（例：`Periodic table`）から`<table class="wikitable">`を抽出し、列正規化（記号・原子番号・名称・相・族/周期・ブロック・標準原子量など）を行う。参考実装手法は既存Q\&Aの方針に準拠。 ([Stack Overflow][4])

### 1.3 データ正規化

* 列マッピング：

  * `atomic_number`（int）, `symbol`（str）, `name_en`（str）, `group`（int/None）, `period`（int）, `block`（s/p/d/f）, `standard_atomic_weight`（str; 範囲・括弧対応）, `category`（金属/非金属等）, `wiki_url`（出典リンク）
* クリーニング規則：

  * HTMLタグ除去、脚注・参照マーカー（`[1]`）除去
  * 長体・全角記号の半角正規化
  * 原子量の括弧・±表記の統一
* バージョン刻印：取得日時UTC、対象言語、API種別（REST/Action）を`data/meta.json`に保存

---

## 2. 表紙設計（スリープ画面活用）

### 2.1 画像仕様（KDP公式に準拠）

* **推奨サイズ**：**高さ2560 × 幅1600 px**（縦長、推奨は高さ2500px以上）
* **フォーマット**：JPEG（推奨）／PNG、**5MB以下**、300dpi目安（画素が主）。 ([Amazon Kindle Direct Publishing][5])
* **SVGは最終表紙では使用しない**（EPUB内では可だが、KFX前提ではラスター化して埋め込み）。

### 2.2 レイアウト方針（モノクロ最適化）

* **視認性最優先**：

  * 文字：原子番号（小）、**元素記号（特大・極太）**、名称（省略可）
  * マス：**コントラストの高い1色罫線**／網掛けは最小限
  * 情報密度：Paperwhite等6–7インチでも判読可能な文字寸法（最低x-height基準）
* **省略ルール**（表紙は一枚）：

  * 名称は省略または2文字略（言語別）
  * 原子量は省略、族/周期は行列配置で暗黙表現
* **生成プロセス**：

  1. **SVGテンプレート**（グリッド・フォント・罫線定義）にデータ流し込み
  2. レンダラ（librsvg/inkscape/imagick等）で**2560×1600にラスター化**
  3. 端の可読マージン確保（外周24–32px）

---

## 3. 本文コンテンツ構成（EPUB3）

### 3.1 目次構成

1. **Cover**（表紙画像）
2. **Elements A–Z 索引**（記号・名称でジャンプ）
3. **凡例（Legend）**：記号、略号、マークの説明
4. **出典・ライセンス**（TASL準拠、派生物としてのCC BY-SA表記） ([クリエイティブ・コモンズ][6])

### 3.2 スタイル（モノクロKindle最適化）

* フォント：汎用サンセリフ指定（端末依存）。記号は極太、番号は細め。
* 行間・余白：タップ誤爆防止のため行高とリンク間隔に余裕。
* 表は**固定幅グリッド**＋折返しなしを基本、狭幅端末は横スクロール（CSS overflow）許容。
* SVGは本文での図版に使用可（Kindle側でラスター化される前提のため**細線避け**）。

---

## 4. 生成パイプライン

### 4.1 リポジトリ構成

```
/
├─ scripts/
│   ├─ fetch_wiki.py          # Wikipedia取得（REST/Action切替可）
│   ├─ normalize.py           # テーブル→標準化JSON
│   ├─ build_cover_svg.py     # SVGテンプレ生成
│   ├─ rasterize_cover.py     # SVG→JPEG/PNG（2560x1600）
│   ├─ build_epub.py          # EPUB3組版（OPF/NCX/Nav/Spine生成）
│   └─ license_attribution.py # TASL自動生成（出典一覧）
├─ data/
│   ├─ raw/ ...               # APIレスポンス保存
│   ├─ tables.json            # 正規化後テーブル
│   └─ meta.json              # 取得メタ
├─ assets/
│   ├─ templates/cover.svg.j2 # 表紙テンプレ（Jinja2）
│   ├─ css/style.css          # モノクロ最適化CSS
│   └─ fonts/ (任意)          # 著作権/再配布条件に注意
├─ book/
│   ├─ OEBPS/                 # 生成物置き場
│   └─ dist/                  # 出力（.epub / 画像）
├─ ci/
│   └─ gh-actions.yml         # GitHub Actions用ワークフロー
└─ README.md                  # 使い方・ライセンス
```

### 4.2 ビルド手順（Codex/ローカル共通）

1. `python scripts/fetch_wiki.py --lang en --page "Periodic table"`

   * `data/raw/*.json` に保存、HTTPヘッダ・ETag管理
2. `python scripts/normalize.py` → `data/tables.json`
3. `python scripts/build_cover_svg.py --in data/tables.json --out assets/gen/cover.svg`
4. `python scripts/rasterize_cover.py --in assets/gen/cover.svg --out book/dist/cover_2560x1600.jpg`
5. `python scripts/build_epub.py --cover book/dist/cover_2560x1600.jpg --out book/dist/PeriodicTable.en.epub`
6. `python scripts/license_attribution.py --out OEBPS/attribution.xhtml`（自動で`nav`・`spine`へ追加）

### 4.3 主要スクリプト仕様

* **fetch\_wiki.py**

  * `--api=rest|action`（デフォルトrest）
  * `--lang=en` `--page="Periodic table"`
  * 失敗時フォールバック（REST→Action）
* **normalize.py**

  * HTMLの`wikitable`→pandas DataFrame→正規化
  * 列欠損は`None`、異体表記の統一ルールJSONで管理
* **build\_cover\_svg.py**

  * Jinja2で**等幅グリッド**へ割付、記号は最大級、番号・名称は最小限
  * 端の余白・行列ラベル（Period/Group）は**控えめ**に
* **rasterize\_cover.py**

  * inkscape or rsvg-convert or ImageMagick。出力：`2560x1600`、品質85–92（JPEG）
* **build\_epub.py**

  * OPF（`dc:title`, `dc:language`, `meta`に取得日時/出典残す）
  * Nav/NCX生成（A–Z・族・周期）
  * 画像は`max`辺2560px以内、`alt`必須
* **license\_attribution.py**

  * TASL：\*\*Title / Author（“Wikipedia contributors”）/ Source（URL）/ License（CC BY-SA 4.0リンク）\*\*を列挙、改変の有無記載。 ([クリエイティブ・コモンズ][6])

---

## 5. GitHub Actions（代替実行）

### 5.1 ワークフロー概要

* **トリガ**：`workflow_dispatch` および `schedule: cron("0 2 * * 1")`（週1再取得）
* **ジョブ**：`ubuntu-latest`
* **キャッシュ**：`~/.cache/pip` と `data/raw`（ETag活用）
* **ステップ**：

  1. Python 3.11 セットアップ
  2. `pip install -r requirements.txt`
  3. セクション「4.2 ビルド手順」を順実行
  4. `book/dist/*.epub` をActions Artifactsに保存

### 5.2 依存パッケージ（例）

* `requests`, `pandas`, `beautifulsoup4`, `lxml`, `jinja2`, `Pillow`, `cairosvg`（または `inkscape` CLI）, `python-slugify`

---

## 6. KFX（Kindle用変換）方針

* **Kindle Previewer**（デスクトップアプリ）でEPUB→KPF/KFXプレビュー変換を行う運用。CLI利用は基本的にPreviewer側のガイドに従う（自動化は限定的）。 ([アマゾン][7])
* QA手順：

  * Paperwhite世代表示確認（モノクロ可読性・リンク・目次）
  * “表紙をロック画面に表示”で**表紙カバーがスリープ画面に出ること**を手動検証
* **注意**：一部プラットフォーム（iPadアプリ等）はSVG非対応注記があるため、表紙は**必ずラスター**を配する。 ([Amazon Kindle Direct Publishing][5])

---

## 7. 文字設計・可読性基準（実測ベースで最終調整）

* 表紙マス内**元素記号**：最小でも端末実測で**x-height ≥ 9–10px相当**
* 罫線：1.5–2.0px相当（端末レンダ時に1px落ちしないよう）
* 見出し・凡例の日本語化対応（将来）：言語別辞書 `i18n/*.json` を想定

---

## 8. テスト & 検証

* **単体**：正規化関数（列数・欠損・型）
* **スナップショット**：表紙SVG→JPEGの画素一致（許容誤差±1–2%）
* **EPUB検証**：`epubcheck` をCIで実行
* **端末実機**：Paperwhite（11世代想定）での可読・ジャンプ確認

---

## 9. 配布と法的表記

* 巻末に**帰属表記（TASL）**、**本全体のライセンス**（CC BY-SA継承部分と、独自テンプレ部分のライセンス区分）を明確化。
* READMEに**再配布・改変条件**を記載（Wikipedia派生部分は**CC BY-SA 4.0**での共有義務）。 ([ウィキペディア][1])

---

## 10. 追加オプション（将来）

* **日本語版/多言語版**：`--lang=ja` で日本語Wikipediaから取得
* **拡張ページ**：電子配置図、外殻電子配置、融点/沸点ランキング
* **モノクロ強調**の代替版表紙（記号巨大＋番号のみ）を同梱
* **シリーズ統一**：カレンダー本と同じ装丁・凡例パターン

---

## 参考（公式情報）

* **KDPカバー推奨**：**2560×1600px**、JPEG推奨、5MB以下。 ([Amazon Kindle Direct Publishing][5])
* **Wikimedia REST API**（ページHTML/サマリ）・**MediaWiki Action API**（parse系）。 ([api.wikimedia.org][2])
* **Wikipediaの著作権/ライセンス**：**CC BY-SA 4.0**、帰属の推奨実務（TASL）。 ([ウィキペディア][1])

---

[1]: https://en.wikipedia.org/wiki/Wikipedia%3ACopyrights?utm_source=chatgpt.com "Wikipedia:Copyrights"
[2]: https://api.wikimedia.org/wiki/Core_REST_API/Reference/Pages/Get_HTML?utm_source=chatgpt.com "Core REST API/Reference/Pages/Get HTML"
[3]: https://www.mediawiki.org/wiki/API%3AAction_API?utm_source=chatgpt.com "API:Action API"
[4]: https://stackoverflow.com/questions/40210536/how-to-obtain-data-in-a-table-from-wikipedia-api?utm_source=chatgpt.com "How to obtain data in a table from Wikipedia API?"
[5]: https://kdp.amazon.com/en_US/help/topic/G6GTK3T3NUHKLEFX?utm_source=chatgpt.com "Cover Image Guidelines - Kindle Direct Publishing"
[6]: https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution?utm_source=chatgpt.com "Recommended practices for attribution"
[7]: https://www.amazon.com/Kindle-Previewer/b?ie=UTF8&node=21381691011&utm_source=chatgpt.com "Kindle Previewer: Kindle Store"
