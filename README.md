# zTranzlator - Project Zomboid (Build 42) Mod Translator Suite

[![GitHub Repository](https://img.shields.io/badge/GitHub-unelmapjt%2FzTranslator-blue?logo=github)](https://github.com/unelmapjt/zTranslator)
[![Project Zomboid](https://img.shields.io/badge/Project%20Zomboid-Build%2042%20Ready-green)](https://projectzomboid.com)
[![License](https://img.shields.io/badge/License-MIT-orange)](#-クレジット--credits)

Skyrim の傑作翻訳ツール「xTranslator」に着想を得た、**Project Zomboid Build 42 向け・完全非破壊・差分更新対応のAI翻訳ツール**です。  
直感的なモダンGUI（CustomTkinter / Meiryo UI）を備え、公式対訳辞書（35,000語）によるオフライン即時翻訳から、最新のローカルLLM（Ollama）や超高速クラウドAI（Gemini / Groq / DeepSeek / OpenAI）による文脈翻訳まで幅広く対応します。

---

## ☕ 制作の想い / はじめに
Project Zomboid が発売されてからずいぶん経ちますが、今でもたくさんのプレイヤーや配信者・コミュニティに愛され続けています。  
MOD文化も非常に活発に動いていますが、一方で「言語の壁」は依然として大きく、素晴らしいMODに出会っても導入を躊躇してしまう壁になっていると感じていました。  

「まだ翻訳MODがないMODでも、誰でももっと簡単に母国語で楽しめるようにしたい」という想いから本ツールを作りました。  

現在はアルファ版なので全然完璧ではありませんが、よかったらぜひ使ってみてください！  
うまく翻訳できないMODがあったらごめんなさい！  
*Project Zomboid が、これからもずっとみんなで楽しめるものでありますように！*

---

## 🌟 主な特徴

1. **完全非破壊（Zero-Destruction）**
   - ゲーム本体ファイルや元MODのファイルを1文字も改変しません。
   - すべて独立したパッチMOD（`<MOD_ID>_JA`）として生成され、元MOD（`require=<MOD_ID>`）に自動連動。ゲーム本体のアップデートでも壊れません。
2. **すべてのMOD形式を全自動判別・Build 42 ハイブリッド対応**
   - **Type A (公式JSON)**: `Translate/JP/*.json` および `JA/*.json` 形式を自動構築（旧B41レガシーTXTもB42仕様へ自動昇格）。
   - **サブバージョン完全対応**: `42.0`, `42.15`, `42.18`, `common`, `42` など全サブフォルダへ自動生成。
   - **多重キー完全救済**: Wandering Zombies などのように同一英語が複数キー（250個以上）に割り当てられているサンドボックス設定もキーの重複脱落なく100%復元・適用。
   - **Type B (メディア/手記)**: The Ark のような `printMedia/txt/*.txt` の大容量ストーリーテキストに対応。
   - **Type C (ハードコードUI)**: Viewpoint のようにソースコードに直書きされたUI・JARも、安全な基底UIフックLuaを自動生成して翻訳。
3. **複数MODの一括選択 ＆ 連続自動翻訳**
   - Ctrl / Shift クリックでの複数MOD選択に対応。
   - 上部の「**全て選択**」「**未翻訳のみ選択**」「**選択解除**」ボタンで、大量のMODを一瞬でまとめてターゲット指定可能。
   - 「一括AI翻訳を実行」を押すだけで、選択した全MODを順番に自動翻訳していきます。
4. **作業ドラフトの自動永続化（作業中断・再開も安心）**
   - 翻訳途中でMODを切り替えたり、アプリを終了しても、作業途中の訳文は `mod_draft_cache.json` にリアルタイム自動保存されます。
   - 次回起動時にも作業途中のドラフトが瞬時に復元されるため、翻訳データが消える心配がありません。
5. **差分更新（Incremental Update）エンジン**
   - ターゲットMODが更新（v1 ➡ v2）されても、以前翻訳した内容を**100%自動継承**。
   - MOD側で削除された旧テキストも破棄せず、`[廃止キー(温存)]` としてアーカイブ保持。
   - 新規に追加されたテキストだけを未翻訳（赤）として抽出し、ワンクリックで差分翻訳が可能。
6. **左側リストでの「日本語率（％）」＆適用状態の一目管理**
   - MOD一覧に「日本語率」列を新設。`100% (適用済)`、`65% (作業中)`、`未着手` などがカラーで常時表示。
   - MOD選択・AI翻訳・手動編集・パッチ適用のすべての操作にリアルタイム連動し、次回起動時も一瞬で状態を復元（キャッシュ永続化）。
7. **UI文字幅セーフ（はみ出し防止＆リアルタイムアシスト）**
   - 英語固定幅ボタンからの突き抜けを防ぐ「⚠️幅注意」自動検知機能。
   - セルのダブルクリック編集時に、原文に対する文字幅比率（％）とアドバイスをリアルタイム表示。
   - プロンプトレベルで漢字熟語優先（`Configuration` ➡ `設定`、`Auto Reload` ➡ `自動装填`）と半角英数正規化を徹底。
8. **多彩なAIエンジン切り替え**
   - **内蔵スマート辞書**: 公式対訳 35,000語 ＋ 短縮ルール。完全オフライン・GPU/APIキー不要で即動作。
   - **Ollama ローカルLLM**: 未起動時は自動でバックグラウンド起動。PC内のインストール済みモデル一覧（GBサイズ付き）を即時検出・一覧表示し、クリックで選択可能。モデルのワンクリック導入にも対応。
   - **クラウドAI API**: Google Gemini（無料枠あり）や OpenAI 互換（Groq の超高速LPU、DeepSeek、OpenAI、OpenRouter）に対応。
9. **ゲーム内リアルタイム切り替え（ModOptions連動）**
   - ゲーム内の「Mod設定 (Mod Options)」から、ゲームを再起動することなくいつでも即座に日本語と英語を切り替え可能。

---

## 🚀 クイックスタート

### 1. 起動方法
フォルダ内の **`run_zTranzlator.bat`** をダブルクリックして起動します。

> ※ 初回実行時に必要なライブラリ（`customtkinter`, `pillow`）が自動チェック・セットアップされます。  
> ※ Python環境すら不要な配布用EXEを作りたい場合は、`build_exe.bat` を実行してください。

### 2. 翻訳の3ステップ
1. **MODを選択**:
   - 画面左側のMOD一覧から翻訳したいMODを選択します（Ctrl / Shift や「未翻訳のみ」ボタンで複数同時選択も可能）。
2. **一括AI翻訳を実行**:
   - 画面左下の「**一括AI翻訳を実行**」ボタンをクリック。選択したMODの未翻訳項目が順番に自動翻訳されます。
   - 大きなLLMモデルの実行で時間がかかりすぎたりスタックした場合は、隣の「**⏹️ 中断 (停止)**」ボタンでいつでも安全に即時停止可能（翻訳済みの項目はエディタ・ドラフトに温存されます）。
   - 表内のセルをダブルクリックすることで、訳文を手動でいつでも微調整できます。
3. **ローカルMOD適用**:
   - 画面中央の目立つエメラルドボタン **「✨ ローカルMOD適用 (Zomboid/mods)」** をクリック。
   - これだけで `C:\Users\<ユーザー>\Zomboid\mods\<MOD_ID>_JA` にパッチMODが自動配置されます。

### 3. ゲーム内での有効化
1. Project Zomboid を起動し、タイトルメニューの「**MOD**」を開きます。
2. 一覧から **`〇〇 日本語化 (zTranzlator)`** を有効化（チェック）して戻るだけです！

---

## 🎨 グリッドエディタの色分け（ステータス表示）

| カラー表示 | ステータス | 意味・動作 |
| :--- | :--- | :--- |
| **青緑** | **既存継承** | 以前翻訳したパッチから引き継がれた翻訳（差分更新） |
| **緑** | **公式一致** | Project Zomboid 公式の日本語訳（35,000語）と完全に一致した用語 |
| **青** | **AI翻訳** | AIエンジン（Ollama / Gemini / OpenAI互換）によって自動翻訳された項目 |
| **シアン** | **手動修正** | ユーザーがダブルクリックして直接好みの言い回しに書き換えた項目 |
| **赤** | **未翻訳** | MOD更新などで新しく増えた未翻訳テキスト。「一括AI翻訳」の対象 |
| **灰** | **廃止キー** | MOD更新で削除されたがアーカイブとして安全に温存された旧訳文 |
| **黄 (警告)** | **〇〇 ⚠️** | 原文に対して描画幅が145%を超えており、UI枠からはみ出すリスクがある項目 |

---

## 📖 ユーザーマニュアル（HTML版）
より詳しいクリーンインストール手順、各LLM（Ollama / Groq / DeepSeek / Gemini）の設定方法、UIはみ出し制限の解説、配布ZIPの作成手順などは、アプリ内の **［マニュアル (HTML)］** ボタン、またはブラウザで **`MANUAL.html`** を開いてご覧いただけます。

---

## 📜 作成した日本語化MODの公開・再配布規約（ライセンス表記）

本ツール（zTranzlator）を使用して作成した日本語化MODを Steam ワークショップや外部サイト等で公開される際は、以下のクレジット表記をお願いいたします：

1. **元MOD制作者様へのリスペクト**:
   - 元MODの著作権を尊重し、元MODのURLおよび必須MOD指定（`require=<MOD_ID>`）を必ず明記してください。
2. **日本語化ツールのクレジット表記**:
   - ワークショップの概要欄等に「**Translation Tool: zTranzlator (Author: Uni-SJ)**」および [Uni-SJ Steam Workshop](https://steamcommunity.com/profiles/76561198062851438/myworkshopfiles?appid=108600) へのリンクを明記してください。

> 💡 **投稿用テンプレート自動出力**:
> パッチMODの生成時（および配布用ZIP内）に、Steam投稿用の説明文テンプレート（`WORKSHOP_DESCRIPTION.txt`）およびライセンス注意事項（`README_LICENSE.txt`）が自動生成されます。そのままコピー＆ペーストしてご利用いただけます。

---

## 📦 ファイル構成

```text
zTranzlator/
├── workshop.txt            # Steamワークショップ公開用設定ファイル (B42 Uploader対応)
├── preview.png             # ワークショップ掲載用プレビューポスター (512x512)
├── Contents/               # Steamサブスクライブ用MOD配信ディレクトリ
│   └── mods/zTranzlator/   # サブスクライバーへ配信されるツール一式
├── app_gui.py              # メインGUIアプリケーション (CustomTkinter / Meiryo UI)
├── run_zTranzlator.bat     # アプリ起動用バッチ (自動依存関係チェック付き)
├── build_exe.bat           # 配布用EXEビルドスクリプト (PyInstaller)
├── dict_builder.py         # バニラ公式辞書(Translate/JP)自動構築モジュール
├── mod_scanner.py          # Type A/B/C 静的抽出 ＆ 差分更新スキャナー
├── translator_engine.py    # Ollama / Gemini / OpenAI互換 / スマート辞書エンジン
├── mod_generator.py        # 独立パッチMOD ＆ ポスター画像自動生成モジュール
├── vanilla_dict.json       # バニラ公式対訳辞書 (35,000語)
├── MANUAL.html             # スタイリッシュな公式ユーザーマニュアル (ブラウザ閲覧)
├── SPECIFICATION.md        # 詳細技術仕様書
└── README.md               # 概要取扱説明書 (本ファイル)
```

---

## 👤 クレジット / Credits
- **Author**: Uni-SJ
- **GitHub**: [https://github.com/unelmapjt/zTranslator](https://github.com/unelmapjt/zTranslator)
- **Steam Workshop**: [Uni-SJ Workshop Files](https://steamcommunity.com/profiles/76561198062851438/myworkshopfiles?appid=108600)
- *背後に気をつけて。幸運を祈る。*

