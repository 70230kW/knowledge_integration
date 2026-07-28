"use strict";

/* ===================== API helper ===================== */
const api = {
  async request(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
    if (res.status === 204) return null;
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    if (!res.ok) {
      const message = (data && data.detail) || `リクエストに失敗しました (${res.status})`;
      throw new Error(message);
    }
    return data;
  },
  get(path) {
    return this.request("GET", path);
  },
  post(path, body) {
    return this.request("POST", path, body ?? {});
  },
  put(path, body) {
    return this.request("PUT", path, body ?? {});
  },
  del(path) {
    return this.request("DELETE", path);
  },
};

/* ===================== Utils ===================== */
function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// FTS5のsnippet()関数が付ける [[ ]] を <mark> に変換して表示する
function renderSnippet(snippet) {
  if (!snippet) return "";
  const escaped = escapeHtml(snippet);
  return escaped.replace(/\[\[/g, "<mark>").replace(/\]\]/g, "</mark>");
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function formatDateTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return iso;
  }
}

const TYPE_LABEL = { manual: "📘 MANUAL", credential: "🔑 CREDENTIAL" };

/* ===================== State ===================== */
const state = {
  activeType: "",
  activeTag: "",
  query: "",
  entries: [],
  tags: [],
  editingEntryId: null,
  pendingLinks: new Map(), // create-mode: id -> {id, title, type}
};

/* ===================== DOM refs ===================== */
const el = {
  authScreen: document.getElementById("auth-screen"),
  authForm: document.getElementById("auth-form"),
  authSub: document.getElementById("auth-sub"),
  authPassword: document.getElementById("auth-password"),
  authConfirmField: document.getElementById("auth-confirm-field"),
  authConfirm: document.getElementById("auth-password-confirm"),
  authSubmit: document.getElementById("auth-submit"),
  authError: document.getElementById("auth-error"),

  app: document.getElementById("app"),
  searchInput: document.getElementById("search-input"),
  newEntryBtn: document.getElementById("new-entry-btn"),
  logoutBtn: document.getElementById("logout-btn"),
  typeFilters: document.getElementById("type-filters"),
  tagCloud: document.getElementById("tag-cloud"),
  listTitle: document.getElementById("list-title"),
  listCount: document.getElementById("list-count"),
  entryList: document.getElementById("entry-list"),

  detailModal: document.getElementById("detail-modal"),
  detailContent: document.getElementById("detail-content"),

  editModal: document.getElementById("edit-modal"),
  editModalTitle: document.getElementById("edit-modal-title"),
  editForm: document.getElementById("edit-form"),
  editId: document.getElementById("edit-id"),
  editTypeToggle: document.getElementById("edit-type-toggle"),
  editTitle: document.getElementById("edit-title"),
  editBody: document.getElementById("edit-body"),
  editBodyLabel: document.getElementById("edit-body-label"),
  editTags: document.getElementById("edit-tags"),
  suggestBox: document.getElementById("suggest-box"),
  suggestList: document.getElementById("suggest-list"),
  linkBox: document.getElementById("link-box"),
  currentLinkList: document.getElementById("current-link-list"),
  deleteEntryBtn: document.getElementById("delete-entry-btn"),

  bulkImportBtn: document.getElementById("bulk-import-btn"),
  bulkModal: document.getElementById("bulk-modal"),
  bulkForm: document.getElementById("bulk-form"),
  bulkTypeToggle: document.getElementById("bulk-type-toggle"),
  bulkText: document.getElementById("bulk-text"),
  bulkPreview: document.getElementById("bulk-preview"),
  bulkPreviewTitle: document.getElementById("bulk-preview-title"),
  bulkPreviewList: document.getElementById("bulk-preview-list"),
  bulkStatus: document.getElementById("bulk-status"),
  bulkSubmitBtn: document.getElementById("bulk-submit-btn"),
};

/* ===================== Auth ===================== */
async function checkAuth() {
  const status = await api.get("/api/auth/status");
  if (!status.authenticated) {
    showAuthScreen(status.initialized);
    return false;
  }
  el.authScreen.hidden = true;
  el.app.hidden = false;
  return true;
}

function showAuthScreen(initialized) {
  el.app.hidden = true;
  el.authScreen.hidden = false;
  if (initialized) {
    el.authSub.textContent = "MASTER PASSWORD AUTHENTICATION REQUIRED";
    el.authSubmit.querySelector("span").textContent = "LOGIN";
    el.authConfirmField.hidden = true;
    el.authConfirm.required = false;
  } else {
    el.authSub.textContent = "初回起動: マスターパスワードを設定してください";
    el.authSubmit.querySelector("span").textContent = "SET MASTER PASSWORD";
    el.authConfirmField.hidden = false;
    el.authConfirm.required = true;
  }
}

el.authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  el.authError.hidden = true;
  const status = await api.get("/api/auth/status");
  const password = el.authPassword.value;
  try {
    if (!status.initialized) {
      if (password !== el.authConfirm.value) {
        throw new Error("パスワードが一致しません。");
      }
      await api.post("/api/auth/setup", { password });
    } else {
      await api.post("/api/auth/login", { password });
    }
    el.authForm.reset();
    await bootApp();
  } catch (err) {
    el.authError.textContent = err.message;
    el.authError.hidden = false;
  }
});

el.logoutBtn.addEventListener("click", async () => {
  await api.post("/api/auth/logout");
  location.reload();
});

/* ===================== List rendering ===================== */
async function loadTags() {
  state.tags = await api.get("/api/tags");
  renderTagCloud();
}

function renderTagCloud() {
  if (state.tags.length === 0) {
    el.tagCloud.innerHTML = '<p class="muted">タグはまだありません</p>';
    return;
  }
  el.tagCloud.innerHTML = state.tags
    .map(
      (t) => `
      <button class="tag-pill ${state.activeTag === t.name ? "is-active" : ""}" data-tag="${escapeHtml(t.name)}">
        ${escapeHtml(t.name)}<span class="tag-pill__count">${t.count}</span>
      </button>`
    )
    .join("");
}

el.tagCloud.addEventListener("click", (e) => {
  const btn = e.target.closest(".tag-pill");
  if (!btn) return;
  const tag = btn.dataset.tag;
  state.activeTag = state.activeTag === tag ? "" : tag;
  renderTagCloud();
  loadEntries();
});

el.typeFilters.addEventListener("click", (e) => {
  const btn = e.target.closest(".filter-chip");
  if (!btn) return;
  state.activeType = btn.dataset.type;
  [...el.typeFilters.children].forEach((c) => c.classList.toggle("is-active", c === btn));
  loadEntries();
});

el.searchInput.addEventListener(
  "input",
  debounce((e) => {
    state.query = e.target.value.trim();
    loadEntries();
  }, 250)
);

async function loadEntries() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.activeType) params.set("type", state.activeType);
  if (state.activeTag) params.set("tag", state.activeTag);
  el.entryList.innerHTML = '<p class="muted">読み込み中...</p>';
  const entries = await api.get(`/api/entries?${params.toString()}`);
  state.entries = entries;
  renderEntryList();
}

function renderEntryList() {
  el.listTitle.textContent = state.query ? `SEARCH: "${state.query}"` : "ALL ENTRIES";
  el.listCount.textContent = `${state.entries.length} 件`;

  if (state.entries.length === 0) {
    el.entryList.innerHTML = '<p class="muted">該当するエントリがありません。</p>';
    return;
  }
  el.entryList.innerHTML = state.entries
    .map((entry) => {
      const icon = entry.type === "credential" ? "🔑" : "📘";
      const tags = entry.tags
        .map((t) => `<span class="entry-card__tag">${escapeHtml(t)}</span>`)
        .join("");
      const snippet = entry.snippet
        ? `<p class="entry-card__snippet">${renderSnippet(entry.snippet)}</p>`
        : "";
      return `
      <div class="entry-card" data-id="${entry.id}">
        <span class="entry-card__icon">${icon}</span>
        <div class="entry-card__body">
          <p class="entry-card__title">${escapeHtml(entry.title)}</p>
          ${snippet}
          <div class="entry-card__meta">${tags}</div>
        </div>
        <span class="entry-card__type">${formatDateTime(entry.updated_at)}</span>
      </div>`;
    })
    .join("");
}

el.entryList.addEventListener("click", (e) => {
  const card = e.target.closest(".entry-card");
  if (!card) return;
  openDetail(Number(card.dataset.id));
});

/* ===================== Detail modal ===================== */
async function openDetail(id) {
  const entry = await api.get(`/api/entries/${id}`);
  const isCredential = entry.type === "credential";
  const tags = entry.tags.map((t) => `<span class="entry-card__tag">${escapeHtml(t)}</span>`).join("");
  const links = entry.linked_entries.length
    ? entry.linked_entries
        .map(
          (l) => `
        <div class="detail-link-item" data-id="${l.id}">
          <span>${l.type === "credential" ? "🔑" : "📘"}</span>
          <span>${escapeHtml(l.title)}</span>
        </div>`
        )
        .join("")
    : '<p class="muted">関連するエントリはありません。</p>';

  const bodyBlockId = `body-${entry.id}`;
  const bodyHtml = isCredential
    ? `<button class="reveal-toggle" id="reveal-${entry.id}">👁 内容を表示</button>
       <div class="detail-body" id="${bodyBlockId}" style="display:none">${escapeHtml(entry.body)}</div>`
    : `<div class="detail-body" id="${bodyBlockId}">${escapeHtml(entry.body) || '<span class="muted">本文なし</span>'}</div>`;

  el.detailContent.innerHTML = `
    <div class="detail-header">
      <h2 class="detail-title">${escapeHtml(entry.title)}</h2>
      <span class="detail-type-badge detail-type-badge--${entry.type}">${TYPE_LABEL[entry.type]}</span>
    </div>
    <div class="detail-meta">UPDATED ${formatDateTime(entry.updated_at)} / CREATED ${formatDateTime(entry.created_at)}</div>
    ${bodyHtml}
    <div class="detail-tags">${tags || '<span class="muted">タグなし</span>'}</div>
    <h3 class="detail-section-title">🔗 関連するエントリ</h3>
    <div class="detail-links">${links}</div>
    <div class="detail-actions">
      <button class="btn btn--primary" id="detail-edit-btn">編集</button>
    </div>
  `;

  if (isCredential) {
    document.getElementById(`reveal-${entry.id}`).addEventListener("click", (e) => {
      const block = document.getElementById(bodyBlockId);
      const willShow = block.style.display === "none";
      block.style.display = willShow ? "block" : "none";
      e.target.textContent = willShow ? "🙈 内容を隠す" : "👁 内容を表示";
    });
  }

  el.detailContent.querySelectorAll(".detail-link-item").forEach((item) => {
    item.addEventListener("click", () => openDetail(Number(item.dataset.id)));
  });

  document.getElementById("detail-edit-btn").addEventListener("click", () => {
    closeDetail();
    openEdit(entry);
  });

  el.detailModal.hidden = false;
}

function closeDetail() {
  el.detailModal.hidden = true;
  el.detailContent.innerHTML = "";
}

document.querySelectorAll("[data-close-detail]").forEach((b) => b.addEventListener("click", closeDetail));
el.detailModal.addEventListener("click", (e) => {
  if (e.target === el.detailModal) closeDetail();
});

/* ===================== Edit modal ===================== */
function resetEditForm() {
  state.editingEntryId = null;
  state.pendingLinks = new Map();
  el.editForm.reset();
  el.editId.value = "";
  setEditType("manual");
  el.suggestBox.hidden = true;
  el.suggestList.innerHTML = "";
  el.linkBox.hidden = true;
  el.currentLinkList.innerHTML = "";
  el.deleteEntryBtn.hidden = true;
}

function setEditType(type) {
  [...el.editTypeToggle.children].forEach((c) => c.classList.toggle("is-active", c.dataset.type === type));
  el.editBodyLabel.textContent = type === "credential" ? "BODY (暗号化して保存されます)" : "BODY";
}

el.editTypeToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".type-toggle__opt");
  if (!btn) return;
  setEditType(btn.dataset.type);
});

function currentEditType() {
  return el.editTypeToggle.querySelector(".is-active").dataset.type;
}

function openEdit(entry) {
  resetEditForm();
  if (entry) {
    state.editingEntryId = entry.id;
    el.editModalTitle.textContent = "EDIT ENTRY";
    el.editId.value = entry.id;
    el.editTitle.value = entry.title;
    el.editBody.value = entry.body;
    el.editTags.value = entry.tags.join(", ");
    setEditType(entry.type);
    el.deleteEntryBtn.hidden = false;
    renderCurrentLinks(entry.linked_entries);
  } else {
    el.editModalTitle.textContent = "NEW ENTRY";
  }
  el.editModal.hidden = false;
  el.editTitle.focus();
  runSuggestion();
}

function closeEdit() {
  el.editModal.hidden = true;
  resetEditForm();
}

el.newEntryBtn.addEventListener("click", () => openEdit(null));
document.querySelectorAll("[data-close-edit]").forEach((b) => b.addEventListener("click", closeEdit));
el.editModal.addEventListener("click", (e) => {
  if (e.target === el.editModal) closeEdit();
});

function parseTags(raw) {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function renderCurrentLinks(linkedEntries) {
  if (!linkedEntries || linkedEntries.length === 0) {
    el.linkBox.hidden = true;
    return;
  }
  el.linkBox.hidden = false;
  el.currentLinkList.innerHTML = linkedEntries
    .map(
      (l) => `
      <div class="link-item" data-id="${l.id}">
        <span>${l.type === "credential" ? "🔑" : "📘"} ${escapeHtml(l.title)}</span>
        <button type="button" class="btn btn--sm btn--danger" data-unlink="${l.id}">解除</button>
      </div>`
    )
    .join("");
}

el.currentLinkList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-unlink]");
  if (!btn || !state.editingEntryId) return;
  const targetId = Number(btn.dataset.unlink);
  const updated = await api.del(`/api/entries/${state.editingEntryId}/links/${targetId}`);
  renderCurrentLinks(updated.linked_entries);
  await loadEntries();
});

/* ---- Suggestion (auto-suggest related entries) ---- */
const runSuggestion = debounce(async () => {
  const title = el.editTitle.value.trim();
  const body = el.editBody.value.trim();
  const tags = parseTags(el.editTags.value);
  if (!title && !body && tags.length === 0) {
    el.suggestBox.hidden = true;
    return;
  }
  const payload = { title, body, tags, exclude_id: state.editingEntryId };
  let results;
  try {
    results = await api.post("/api/entries/suggestions", payload);
  } catch (err) {
    return;
  }
  renderSuggestions(results);
}, 400);

[el.editTitle, el.editBody, el.editTags].forEach((input) => {
  input.addEventListener("input", runSuggestion);
});

function renderSuggestions(results) {
  if (!results || results.length === 0) {
    el.suggestBox.hidden = true;
    return;
  }
  el.suggestBox.hidden = false;
  el.suggestList.innerHTML = results
    .map((r) => {
      const reasons = [];
      if (r.matched_tags.length) reasons.push(`タグ一致: ${r.matched_tags.join(", ")}`);
      if (r.matched_keywords.length) reasons.push(`キーワード一致: ${r.matched_keywords.slice(0, 5).join(", ")}`);
      const isCreateMode = state.editingEntryId === null;
      const isPending = state.pendingLinks.has(r.id);
      const label = isCreateMode ? (isPending ? "✓ 追加済み" : "＋ リンク予定に追加") : "🔗 リンクする";
      return `
      <div class="suggest-item" data-id="${r.id}">
        <div>
          <div>${r.type === "credential" ? "🔑" : "📘"} ${escapeHtml(r.title)}</div>
          <div class="suggest-item__meta">${reasons.join(" / ")}</div>
        </div>
        <button type="button" class="btn btn--sm ${isPending ? "" : "btn--primary"}" data-link-suggestion="${r.id}" data-title="${escapeHtml(r.title)}" data-type="${r.type}">${label}</button>
      </div>`;
    })
    .join("");
}

el.suggestList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-link-suggestion]");
  if (!btn) return;
  const targetId = Number(btn.dataset.linkSuggestion);

  if (state.editingEntryId === null) {
    if (state.pendingLinks.has(targetId)) {
      state.pendingLinks.delete(targetId);
    } else {
      state.pendingLinks.set(targetId, { id: targetId, title: btn.dataset.title, type: btn.dataset.type });
    }
    const results = await api.post("/api/entries/suggestions", {
      title: el.editTitle.value.trim(),
      body: el.editBody.value.trim(),
      tags: parseTags(el.editTags.value),
      exclude_id: null,
    });
    renderSuggestions(results);
  } else {
    const updated = await api.post(`/api/entries/${state.editingEntryId}/links`, { target_id: targetId });
    renderCurrentLinks(updated.linked_entries);
    await loadEntries();
  }
});

el.editForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    title: el.editTitle.value.trim(),
    body: el.editBody.value,
    type: currentEditType(),
    tags: parseTags(el.editTags.value),
  };
  let saved;
  if (state.editingEntryId) {
    saved = await api.put(`/api/entries/${state.editingEntryId}`, payload);
  } else {
    saved = await api.post("/api/entries", payload);
    for (const target of state.pendingLinks.values()) {
      await api.post(`/api/entries/${saved.id}/links`, { target_id: target.id });
    }
  }
  closeEdit();
  await Promise.all([loadEntries(), loadTags()]);
});

el.deleteEntryBtn.addEventListener("click", async () => {
  if (!state.editingEntryId) return;
  if (!confirm("このエントリを削除しますか？この操作は取り消せません。")) return;
  await api.del(`/api/entries/${state.editingEntryId}`);
  closeEdit();
  await Promise.all([loadEntries(), loadTags()]);
});

/* ===================== Bulk import ===================== */
function parseBulkText(raw) {
  const blocks = raw.split(/^[ \t]*---[ \t]*$/m);
  const items = [];
  const errors = [];

  blocks.forEach((block, idx) => {
    const lines = block.split("\n");
    while (lines.length && lines[0].trim() === "") lines.shift();
    while (lines.length && lines[lines.length - 1].trim() === "") lines.pop();
    if (lines.length === 0) return;

    const title = lines[0].trim();
    if (!title) {
      errors.push({ block: idx + 1, message: "タイトルが空です（スキップされます）" });
      return;
    }

    let tags = [];
    const bodyLines = [];
    for (let i = 1; i < lines.length; i++) {
      const m = lines[i].match(/^\s*tags?\s*[:：]\s*(.*)$/i);
      if (m) {
        tags = m[1]
          .split(/[,、]/)
          .map((t) => t.trim())
          .filter((t) => t.length > 0);
      } else {
        bodyLines.push(lines[i]);
      }
    }
    items.push({ title, body: bodyLines.join("\n").trim(), tags });
  });

  return { items, errors };
}

function bulkCurrentType() {
  return el.bulkTypeToggle.querySelector(".is-active").dataset.type;
}

function resetBulkForm() {
  el.bulkForm.reset();
  [...el.bulkTypeToggle.children].forEach((c) => c.classList.toggle("is-active", c.dataset.type === "credential"));
  el.bulkPreview.hidden = true;
  el.bulkPreviewList.innerHTML = "";
  el.bulkStatus.textContent = "";
  el.bulkSubmitBtn.disabled = true;
}

function openBulkModal() {
  resetBulkForm();
  el.bulkModal.hidden = false;
  el.bulkText.focus();
}

function closeBulkModal() {
  el.bulkModal.hidden = true;
  resetBulkForm();
}

el.bulkImportBtn.addEventListener("click", openBulkModal);
document.querySelectorAll("[data-close-bulk]").forEach((b) => b.addEventListener("click", closeBulkModal));
el.bulkModal.addEventListener("click", (e) => {
  if (e.target === el.bulkModal) closeBulkModal();
});

el.bulkTypeToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".type-toggle__opt");
  if (!btn) return;
  [...el.bulkTypeToggle.children].forEach((c) => c.classList.toggle("is-active", c === btn));
});

function renderBulkPreview() {
  const { items, errors } = parseBulkText(el.bulkText.value);
  if (items.length === 0 && errors.length === 0) {
    el.bulkPreview.hidden = true;
    el.bulkSubmitBtn.disabled = true;
    return { items, errors };
  }

  el.bulkPreview.hidden = false;
  el.bulkPreviewTitle.textContent = `解析結果: ${items.length}件登録可能${errors.length ? ` / ${errors.length}件エラー` : ""}`;

  const itemRows = items
    .map(
      (it) => `
      <div class="bulk-preview-item">
        <span>${escapeHtml(it.title)}</span>
        <span class="bulk-preview-item__meta">${it.tags.length ? escapeHtml(it.tags.join(", ")) : "タグなし"}</span>
      </div>`
    )
    .join("");
  const errorRows = errors
    .map(
      (e) => `
      <div class="bulk-preview-item bulk-preview-item--error">
        <span>ブロック${e.block}</span>
        <span class="bulk-preview-item__meta">${escapeHtml(e.message)}</span>
      </div>`
    )
    .join("");
  el.bulkPreviewList.innerHTML = itemRows + errorRows;
  el.bulkSubmitBtn.disabled = items.length === 0;
  return { items, errors };
}

el.bulkText.addEventListener("input", debounce(renderBulkPreview, 200));

el.bulkForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const { items } = renderBulkPreview();
  if (items.length === 0) return;

  el.bulkSubmitBtn.disabled = true;
  el.bulkStatus.textContent = "登録中...";
  try {
    const result = await api.post("/api/entries/bulk", { type: bulkCurrentType(), items });
    el.bulkStatus.textContent = `${result.created_count}件登録しました`;
    await Promise.all([loadEntries(), loadTags()]);
    setTimeout(closeBulkModal, 800);
  } catch (err) {
    el.bulkStatus.textContent = err.message;
    el.bulkSubmitBtn.disabled = false;
  }
});

/* ===================== Boot ===================== */
async function bootApp() {
  const ok = await checkAuth();
  if (!ok) return;
  await Promise.all([loadEntries(), loadTags()]);
}

bootApp().catch((err) => {
  console.error(err);
});
