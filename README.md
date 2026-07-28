# knowledge_integration

マニュアルや各種ID/Passを一元管理する個人用ナレッジ集約アプリ。
新規情報と既存情報が連携しない・データを探しにくいという既存ツールの課題を、
**全文検索**・**エントリ間の明示的なリンク**・**新規追加時の自動サジェスト**で解決します。

- バックエンド: FastAPI (Python)
- DB: SQLite + FTS5 (trigramトークナイザによる日本語対応全文検索)
- フロントエンド: ビルドステップなしのHTML/CSS/JS（ダーク×サイバーなUI）
- 想定実行環境: GitHub Codespaces + `uvicorn`

## 1. セットアップ (Codespaces)

このリポジトリをCodespacesで開くと、Python環境が自動的に使えます。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 環境変数の設定

`.env.example` をコピーして `.env` を作成し、Cookie署名用の秘密鍵を設定してください。

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"  # 出力をSESSION_SECRET_KEYに設定
```

`.env` は `.gitignore` 済みでリポジトリにはコミットされません。

## 2. 起動

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Codespacesの「PORTS」タブでポート8000が自動検知されるので、
表示されたURLをブラウザで開いてください（`--host 0.0.0.0` によりポートフォワーディング経由でアクセス可能）。

## 3. 初回利用

初回アクセス時は「マスターパスワードの設定」画面が表示されます。
ここで設定したパスワードが `credential` タイプのエントリを暗号化・復号するための鍵になります。
ブラウザのセッションを終了して再度開いた場合は、同じマスターパスワードでログインします。

- マスターパスワードはどこにも平文で保存されません（`data/salt.bin` にソルト、`data/verify.token` に検証用の暗号化トークンのみを保存）。
- `credential` タイプの本文はFernet（対称鍵暗号）で暗号化してDBに保存し、ログイン中のセッションでのみ復号されます。
- `data/` 以下のDBファイルや鍵関連ファイルは `.gitignore` によりリポジトリから除外されています。

## 4. 主な機能

- **エントリのCRUD**: `manual`（マニュアル）と `credential`（ID/Pass等）を共通のUIで管理し、typeにより表示を切り替え
- **全文検索**: タイトル・本文・タグを横断した検索（FTS5 trigram、3文字未満の短い検索語はLIKE検索にフォールバック）
- **関連エントリのリンク**: エントリ同士を明示的に紐付け、詳細画面に「関連するエントリ」として表示
- **新規追加時の自動サジェスト**: タグ・キーワードが重複する既存エントリをリアルタイムに検出し、その場でリンクを提案
- **タグ管理**: 自由入力のタグで分類・絞り込み
- **一括登録 (BULK IMPORT)**: `manual`/`credential`いずれかのタイプで複数エントリをまとめて登録。
  画面右上の「📥 BULK IMPORT」から、以下の書式でテキストを貼り付けます。

  ```
  自宅Wi-Fi
  tags: ネットワーク
  SSID: home-network
  password: hunter2
  ---
  社内VPN
  tags: 仕事, VPN
  ID: employee01
  PW: abc123
  ```

  - エントリ同士は `---` のみの行で区切る
  - 各エントリの1行目がタイトル
  - `tags:` で始まる行はカンマ区切りのタグとして扱われ、本文には含まれない
  - 残りの行がそのまま本文になる

  貼り付けと同時に解析結果がプレビュー表示されるので、内容を確認してから「一括登録する」を押してください。

## 5. データモデル

`app/schema.sql` を参照してください。

- `entries`: id / title / body / type(`manual`|`credential`) / created_at / updated_at
- `tags`, `entry_tags`: 多対多のタグ付け
- `entry_links`: エントリ同士の明示的な関連付け
- `entries_fts`: 全文検索用のFTS5仮想テーブル（trigramトークナイザ）。`credential`の本文は平文で索引化されません。

## 6. テスト

```bash
pytest
```

CRUD・全文検索・暗号化・認証・自動サジェストの各機能をカバーしています。

## 7. ディレクトリ構成

```
app/
  main.py          FastAPIアプリ本体
  config.py        環境変数・パス設定
  database.py      SQLite接続・スキーマ初期化
  schema.sql        DBスキーマ定義
  security.py       マスターパスワード検証・Fernet鍵導出・セッション管理
  repository.py     エントリ/タグ/リンクのCRUDとFTS同期・サジェストロジック
  schemas.py        Pydanticモデル
  deps.py           FastAPI依存関係（DB接続・認証）
  routers/          auth / entries / tags の各APIルーター
static/
  index.html / css/style.css / js/app.js   ビルドステップなしのフロントエンド
tests/              pytestテスト一式
```
