-- ナレッジ集約アプリ DBスキーマ

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL CHECK (type IN ('manual', 'credential')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_entry_tags_tag_id ON entry_tags(tag_id);

CREATE TABLE IF NOT EXISTS entry_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id_a INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    entry_id_b INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (entry_id_a <> entry_id_b),
    UNIQUE (entry_id_a, entry_id_b)
);

-- 全文検索用のFTS5仮想テーブル（standalone。entriesとはid=rowidで対応付け、
-- アプリ側で同期する。credentialタイプのbodyは平文で入らないため body 列は空文字とする）
-- 日本語は単語分割なしで書かれるためunicode61では長い1トークンになりがちで検索精度が落ちる。
-- trigramトークナイザ（3文字連続一致）にすることで分かち書き不要な部分一致検索を実現する。
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    body,
    tags_text,
    tokenize = 'trigram'
);
