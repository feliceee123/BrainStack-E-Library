/* E-Library AI - web app (Phase 2). Vanilla JS talking to the shared REST API. */
const API = "/api";
const COVERS = ["#7a0019", "#1f4e79", "#2e6b4f", "#6a3d9a", "#b5651d", "#37474f", "#a1304f"];
const $ = (sel) => document.querySelector(sel);

const session = {
  get token() { return localStorage.getItem("token"); },
  get user() { try { return JSON.parse(localStorage.getItem("user")); } catch { return null; } },
  save(data) { localStorage.setItem("token", data.access_token); localStorage.setItem("user", JSON.stringify(data.user)); },
  clear() { localStorage.removeItem("token"); localStorage.removeItem("user"); },
};
const isAdmin = () => session.user && session.user.role === "admin";

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (session.token) headers.Authorization = "Bearer " + session.token;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && session.token) { session.clear(); location.hash = "#/login"; }
    let detail = data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg.replace("Value error, ", "")).join(". ");
    throw new Error(detail || "Request failed");
  }
  return data;
}

/* DOM helper: uses textContent so server data can never inject HTML (XSS-safe) */
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
const show = (...nodes) => { $("#view").replaceChildren(...nodes); };
const cover = (b, cls = "") => h("div", { class: "cover " + cls, style: "background:" + COVERS[b.id % COVERS.length] }, b.title);
const bookCard = (b) => h("a", { class: "book", href: "#/book/" + b.id },
  cover(b), h("div", { class: "body" }, h("b", {}, b.title), h("small", {}, b.author), h("span", { class: "tag" }, b.category), h("small", {}, b.license)));

function renderNav() {
  const u = session.user, nav = $("#navlinks"), here = location.hash || "#/";
  const link = (href, text) => h("a", { href, class: here === href ? "active" : "" }, text);
  nav.replaceChildren();
  if (u) {
    nav.append(link("#/dashboard", "Dashboard"), link("#/books", "Books"), link("#/ai", "AI Assistant"));
    if (isAdmin()) nav.append(link("#/admin", "Admin"));
    nav.append(h("span", { style: "color:#6b6b70;font-size:.85rem;padding:0 8px" }, u.role === "guest" ? "Guest" : u.full_name));
    nav.append(h("button", { class: "btn ghost", onclick: logout }, "Log out"));
  } else nav.append(link("#/", "Home"), h("a", { href: "#/login", class: "btn" }, "Sign in"));
}
async function logout() {
  try { await api("/auth/logout", { method: "POST" }); } catch { /* token already invalid */ }
  session.clear(); location.hash = "#/";
}

/* ---------------- public views ---------------- */
function homeView() {
  show(
    h("section", { class: "hero" }, h("h1", {}, "Discover. Learn. Read. Smarter."), h("p", {}, "Your free digital library"),
      h("div", { class: "actions" },
        h("button", { class: "btn", onclick: guestLogin }, "Continue as Guest"),
        h("a", { class: "btn ghost", href: "#/register" }, "Create account"),
        h("a", { class: "btn ghost", href: "#/login" }, "Sign in"))),
    h("div", { class: "features" }, feature("200+", "Free, legal books"), feature("5", "Downloads in Guest Mode"),
      feature("10", "Downloads per registered user")));
}
const feature = (big, small) => h("div", { class: "feature" }, h("b", {}, big), small);
async function guestLogin() {
  try { session.save(await api("/auth/guest", { method: "POST" })); location.hash = "#/dashboard"; } catch (e) { alert(e.message); }
}
function authView(mode) {
  const isReg = mode === "register", msg = h("div");
  const field = (id, label, type, ph) => [h("label", { for: id }, label), h("input", { id, type, placeholder: ph || "", required: "" })];
  async function resendVerification() {
    try {
      const result = await api("/auth/resend-verification", {
        method: "POST",
        body: { email: $("#email").value },
      });
      msg.replaceChildren(h("div", { class: "msg ok" }, result.message));
    } catch (err) {
      msg.replaceChildren(h("div", { class: "msg err" }, err.message));
    }
  }
  const form = h("form", { onsubmit: async (e) => {
    e.preventDefault(); const btn = form.querySelector("button"); btn.disabled = true; msg.replaceChildren();
    try {
      const body = { email: $("#email").value, password: $("#password").value };
      if (isReg) body.full_name = $("#name").value;
      if (isReg) {
        const result = await api("/auth/register", { method: "POST", body });
        msg.replaceChildren(h("div", { class: "msg ok" }, result.message),
          h("button", { class: "btn ghost", type: "button", onclick: resendVerification }, "Resend verification email"));
      } else {
        session.save(await api("/auth/login", { method: "POST", body }));
        location.hash = session.user.role === "admin" ? "#/admin" : "#/dashboard";
      }
    } catch (err) {
      const children = [h("div", { class: "msg err" }, err.message)];
      if (isReg || err.message.toLowerCase().includes("verify")) {
        children.push(h("button", { class: "btn ghost", type: "button", onclick: resendVerification }, "Resend verification email"));
      }
      msg.replaceChildren(...children);
    }
    btn.disabled = false;
  } },
    ...(isReg ? field("name", "Full name", "text") : []), ...field("email", "Email", "email", "you@example.com"),
    ...field("password", "Password", "password", isReg ? "At least 8 characters, letters and numbers" : ""), msg,
    h("button", { class: "btn", style: "width:100%;margin-top:8px", type: "submit" }, isReg ? "Create account" : "Sign in"));
  show(h("div", { class: "panel" }, h("h2", {}, isReg ? "Create your account" : "Welcome back"), form,
    h("p", { style: "text-align:center;font-size:.9rem" }, isReg ? "Already registered? " : "No account yet? ",
      h("a", { href: isReg ? "#/login" : "#/register" }, isReg ? "Sign in" : "Register")),
    h("p", { style: "text-align:center" }, h("a", { href: "#/" }, "or browse as guest"))));
}

async function verifyEmailView(token) {
  const panel = h("div", { class: "panel" }, h("h2", {}, "Verify your email"), h("p", {}, "Checking your verification link..."));
  show(panel);
  if (!token) {
    panel.replaceChildren(h("h2", {}, "Invalid verification link"), h("p", {}, "The link is missing its verification token."));
    return;
  }
  try {
    const result = await api("/auth/verify-email", { method: "POST", body: { token } });
    panel.replaceChildren(h("h2", {}, "Email verified"), h("p", {}, result.message),
      h("a", { class: "btn", href: "#/login" }, "Sign in"));
  } catch (err) {
    panel.replaceChildren(h("h2", {}, "Could not verify email"), h("p", { class: "msg err" }, err.message),
      h("a", { href: "#/login" }, "Return to sign in"));
  }
}

/* ---------------- dashboard ---------------- */
async function dashboardView() {
  const me = await api("/auth/me");
  const [stats, mine, library] = await Promise.all([
    api("/stats"),
    api("/downloads"),
    me.role === "guest" ? Promise.resolve([]) : api("/library"),
  ]);
  session.save({ access_token: session.token, user: { ...session.user, role: me.role } });
  show(
    h("h2", {}, me.role === "guest" ? "Welcome, Guest" : "Welcome, " + me.full_name),
    h("p", { style: "color:#6b6b70" }, me.role === "guest" ? "Guest Mode: register to raise your limit from 5 to 10 downloads." : "Registered account"),
    h("div", { class: "stats" },
      stat(`${me.downloads_used} / ${me.download_limit}`, "Downloads used"), stat(me.downloads_remaining, "Downloads remaining"),
      stat(stats.books, "Books in the library"), stat(me.role, "Your role")),
    h("div", { class: "row" }, h("a", { class: "btn", href: "#/books" }, "Browse books"),
      isAdmin() ? h("a", { class: "btn ghost", href: "#/admin" }, "Admin dashboard") : null),
    h("h3", {}, "My downloads"),
    mine.length ? h("div", { class: "scroll" }, h("table", {}, h("tr", {}, h("th", {}, "Title"), h("th", {}, "Author"), h("th", {}, "Category")),
      mine.map((b) => h("tr", {}, h("td", {}, h("a", { href: "#/book/" + b.id }, b.title)), h("td", {}, b.author), h("td", {}, b.category)))))
      : h("p", { style: "color:#6b6b70" }, "You have not downloaded any books yet."),
    h("h3", {}, "My Library"),
    me.role === "guest"
      ? h("p", { style: "color:#6b6b70" }, "Guest accounts cannot use My Library. Create a registered account.")
      : library.length
        ? h("div", { class: "scroll" }, h("table", {}, h("tr", {}, h("th", {}, "Title"), h("th", {}, "Author"), h("th", {}, "Category")),
          library.map((b) => h("tr", {}, h("td", {}, h("a", { href: "#/book/" + b.id }, b.title)), h("td", {}, b.author), h("td", {}, b.category)))))
        : h("p", { style: "color:#6b6b70" }, "No favorites saved yet."));
}
const stat = (n, label) => h("div", { class: "stat" }, h("b", {}, String(n)), h("div", {}, label));

/* ---------------- catalog + details ---------------- */
async function booksView() {
  let category = "", q = "", page = 1;
  const grid = h("div", { class: "grid" }), count = h("p", { style: "color:#6b6b70" }), chips = h("div", { class: "chips" }), pager = h("div", { class: "pager" });
  const search = h("input", { type: "search", placeholder: "Search books or authors..." });
  async function load() {
    const params = new URLSearchParams({ page: String(page), page_size: "24" });
    if (q) params.set("q", q); if (category) params.set("category", category);
    const data = await api("/books?" + params), pages = Math.max(1, Math.ceil(data.total / 24));
    count.textContent = `${data.total} book(s) found`;
    grid.replaceChildren(...data.items.map(bookCard));
    if (!data.items.length) grid.replaceChildren(h("p", {}, "No books match your search."));
    pager.replaceChildren(h("button", { class: "btn ghost small", disabled: page <= 1 ? "" : null, onclick: () => { page--; load(); } }, "Previous"),
      h("span", {}, `Page ${page} of ${pages}`),
      h("button", { class: "btn ghost small", disabled: page >= pages ? "" : null, onclick: () => { page++; load(); } }, "Next"));
  }
  const cats = await api("/categories");
  const drawChips = () => chips.replaceChildren(...[{ name: "", label: "All" }, ...cats.map((c) => ({ name: c.name, label: `${c.name} (${c.count})` }))]
    .map((c) => h("button", { class: "chip" + (category === c.name ? " on" : ""), onclick: () => { category = c.name; page = 1; drawChips(); load(); } }, c.label)));
  let timer; search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { q = search.value.trim(); page = 1; load(); }, 300); });
  drawChips(); show(h("h2", {}, "Book catalog"), search, chips, count, grid, pager); await load();
}

async function bookView(id) {
  const b = await api("/books/" + id);
  const result = h("div");
  const btn = h("button", { class: "btn", onclick: async () => {
    btn.disabled = true; result.replaceChildren();
    try {
      const d = await api(`/books/${id}/download`, { method: "POST" });
      result.replaceChildren(h("div", { class: "msg ok" }, `Ready! ${d.downloads_remaining} of ${d.download_limit} downloads remaining. `,
        h("a", { href: d.download_url, target: "_blank", rel: "noopener noreferrer" }, "Open / download the book")));
    } catch (e) { result.replaceChildren(h("div", { class: "msg err" }, e.message)); }
    btn.disabled = false;
  } }, b.already_downloaded ? "Get download link again" : "Download");
  show(h("a", { class: "back", href: "#/books" }, "< Back to books"),
    h("div", { class: "detail" }, cover(b), h("div", {},
      h("span", { class: "tag" }, b.category), h("h2", {}, b.title), h("p", { style: "color:#6b6b70;margin-top:0" }, "by " + b.author),
      h("p", {}, b.description || "No description available."), h("p", {}, h("b", {}, "License: "), b.license),
      h("p", { style: "color:#6b6b70;font-size:.9rem" }, `Downloads used: ${b.downloads_used} of ${b.download_limit}` + (b.already_downloaded ? " · you already downloaded this book" : "")),
      btn, result)));
}

/* ---------------- Embedded Agentic AI assistant ---------------- */
function aiView() {
  const messages = [];
  const chat = h("div", { class: "ai-chat box", style: "max-height:520px;overflow:auto;margin-bottom:12px" });
  const input = h("input", { type: "text", placeholder: "Ask about books, topics, reading goals...", style: "width:100%", "aria-label":"Message the library assistant" });
  const send = h("button", { class: "btn", type: "button" }, "Send");
  const status = h("div");
  const quickPrompts = [
    ["🔎 Find books", "Find books about "],
    ["✨ Recommend a book", "Recommend a book for a beginner interested in "],
    ["📖 Study help", "Find books that can help me study "],
    ["⚖️ Compare books", "Compare books "],
    ["💾 My Library help", "How do I save a book to My Library?"]
  ];
  const suggestions = h("div", { class: "ai-suggestions" }, ...quickPrompts.map(([label, prompt]) =>
    h("button", { class: "chip", type:"button", onclick: () => { input.value = prompt; input.focus(); } }, label)));
  const welcome = h("div", { class:"ai-welcome" },
    h("div", { class:"ai-avatar" }, "✦"),
    h("h3", {}, "Your friendly library guide"),
    h("p", {}, "Tell me what you want to learn or read. I’ll search the real BrainStack catalog and help you choose."),
    suggestions);
  chat.append(welcome);

  const renderMessage = (role, content) => {
    chat.append(h("div", { class: "ai-message " + role },
      h("div", { class: "ai-message-label" }, role === "user" ? "You" : "BrainStack AI"),
      h("div", { class: "ai-bubble" }, content)));
  };

  async function submit() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    send.disabled = true;
    status.replaceChildren(h("p", { class:"ai-loading" }, "📚 Searching and checking the library..."));
    messages.push({ role: "user", content: text });
    welcome.remove();
    renderMessage("user", text);

    try {
      const data = await api("/ai/chat", { method: "POST", body: { messages: messages.slice(-12) } });
      messages.push({ role: "assistant", content: data.reply });
      renderMessage("assistant", data.reply);

      const calls = data.tool_calls_made || [];
      status.replaceChildren();
      if (calls.length) chat.append(h("div", { class: "ai-tool-note" },
        "✓ Verified with library data · " + calls.map((c) => c.tool.replaceAll("_"," ")).join(" → ")));

      if (data.books && data.books.length) {
        chat.append(h("div", { class: "ai-book-results" }, ...data.books.slice(0, 6).map((b) =>
          h("a", { class: "book", href: "#/book/" + b.id },
            cover(b), h("div", { class: "body" }, h("b", {}, b.title), h("small", {}, "by " + b.author),
              h("span", { class: "tag" }, b.category), h("small", {}, "View book details →"))))));
      }
      chat.scrollTop = chat.scrollHeight;
    } catch (e) {
      status.replaceChildren(h("div", { class: "msg err" }, "I couldn't connect to the library right now. Please try again. " + e.message));
    } finally {
      send.disabled = false; input.focus();
    }
  }
  send.onclick = submit;
  input.onkeydown = (e) => { if (e.key === "Enter") submit(); };

  show(h("section", { class:"ai-page" },
    h("div", { class:"ai-heading" }, h("div", {}, h("span", { class:"ai-eyebrow" }, "BRAINSTACK LIBRARY"), h("h2", {}, "AI Assistant"),
      h("p", {}, "Discover, compare, and choose books with a little help."))),
    chat, h("div", { class:"ai-composer" }, input, send), status,
    h("p", { class:"ai-disclaimer" }, "Book suggestions and details are based on the catalog available in this library. Ask follow-up questions anytime.")));

  api("/ai/history").then((data) => {
    const history = (data.messages || []).filter(m => m.role === "user" || m.role === "assistant");
    if (!history.length) return;
    welcome.remove();
    for (const message of history) {
      messages.push(message); renderMessage(message.role, message.content);
    }
    chat.scrollTop = chat.scrollHeight;
  }).catch(() => {});
}
/* ---------------- admin dashboard ---------------- */
async function adminView() {
  if (!isAdmin()) { show(h("div", { class: "msg err" }, "Administrator access required.")); return; }
  const [s, users, books] = await Promise.all([api("/admin/stats"), api("/admin/users"), api("/admin/books")]);
  const bars = (rows, k, v) => { const max = Math.max(1, ...rows.map((r) => r[v])); return h("div", { class: "bars" }, rows.length ? rows.map((r) =>
    h("div", { class: "bar" }, h("span", {}, r[k]), h("span", { class: "fill", style: `width:${(r[v] / max) * 60}%` }), h("span", {}, String(r[v])))) : h("small", {}, "No data yet"));};
  const t = s.totals;
  const formWrap = h("div"), tableWrap = h("div", { class: "scroll" });
  const catList = h("datalist", { id: "cats" }, s.books_by_category.map((c) => h("option", { value: c.category })));
  let filter = "";

  function bookForm(b) {
    const f = {}; const inp = (k, label, full) => { f[k] = h("input", { type: "text", value: b ? b[k] : "", ...(k === "category" ? { list: "cats" } : {}) }); return h("div", { class: full ? "full" : "" }, h("label", {}, label), f[k]); };
    f.description = h("textarea", {}, b ? b.description : "");
    const msg = h("div", { class: "full" });
    const form = h("form", { class: "form", onsubmit: async (e) => {
      e.preventDefault(); msg.replaceChildren();
      const body = Object.fromEntries(["title", "author", "category", "license", "download_url", "description"].map((k) => [k, f[k].value]));
      try { await api(b ? "/admin/books/" + b.id : "/admin/books", { method: b ? "PUT" : "POST", body }); adminView(); }
      catch (err) { msg.replaceChildren(h("div", { class: "msg err" }, err.message)); }
    } }, inp("title", "Title"), inp("author", "Author"), inp("category", "Category"), inp("license", "License"), inp("download_url", "Download URL (https://...)", true),
      h("div", { class: "full" }, h("label", {}, "Description"), f.description), msg,
      h("div", { class: "full row" }, h("button", { class: "btn", type: "submit" }, b ? "Save changes" : "Add book"), h("button", { class: "btn ghost", type: "button", onclick: () => formWrap.replaceChildren() }, "Cancel")));
    formWrap.replaceChildren(h("div", { class: "box" }, h("h3", {}, b ? "Edit book" : "Add a new book"), form)); formWrap.scrollIntoView({ behavior: "smooth" });
  }
  function drawTable() {
    const rows = books.filter((b) => (b.title + " " + b.author).toLowerCase().includes(filter)).slice(0, 60);
    tableWrap.replaceChildren(h("table", {}, h("tr", {}, ["Title", "Author", "Category", "Actions"].map((x) => h("th", {}, x))),
      rows.map((b) => h("tr", {}, h("td", {}, b.title), h("td", {}, b.author), h("td", {}, b.category), h("td", {},
        h("button", { class: "btn small ghost", onclick: () => bookForm(b) }, "Edit"), " ",
        h("button", { class: "btn small danger", onclick: async () => { if (confirm(`Delete "${b.title}"?`)) { await api("/admin/books/" + b.id, { method: "DELETE" }); adminView(); } } }, "Delete"))))));
  }
  const find = h("input", { type: "search", placeholder: "Filter books to manage (showing first 60)..." });
  find.addEventListener("input", () => { filter = find.value.toLowerCase(); drawTable(); });
  drawTable();
  show(h("h2", {}, "Admin dashboard"), catList,
    h("div", { class: "stats" }, stat(t.books, "Books"), stat(t.users, "Users"), stat(t.downloads, "Downloads"), stat(t.guest_downloads, "Guest downloads")),
    h("div", { class: "two" }, h("div", { class: "box" }, h("h3", {}, "Downloads by category"), bars(s.downloads_by_category, "category", "count")),
      h("div", { class: "box" }, h("h3", {}, "Most downloaded books"), bars(s.top_books, "title", "downloads")),
      h("div", { class: "box" }, h("h3", {}, "Books per category"), bars(s.books_by_category, "category", "count"))),
    h("h3", {}, "Book management ", h("button", { class: "btn small", onclick: () => bookForm(null) }, "+ Add book")), formWrap, find, tableWrap,
    h("h3", {}, "Users"), h("div", { class: "scroll" }, h("table", {}, h("tr", {}, ["Name", "Email", "Role", "Downloads", "Joined"].map((x) => h("th", {}, x))),
      users.map((u) => h("tr", {}, h("td", {}, u.full_name), h("td", {}, u.email), h("td", {}, u.role), h("td", {}, String(u.downloads)), h("td", {}, u.created_at))))));
}

/* ---------------- router ---------------- */
const PUBLIC = new Set(["#/", "#/login", "#/register", "#/verify-email"]);
async function route() {
  const hash = location.hash || "#/";
  const routeHash = hash.split("?")[0];
  if (!PUBLIC.has(routeHash) && !session.token) { location.hash = "#/login"; return; }
  if (PUBLIC.has(routeHash) && routeHash !== "#/" && routeHash !== "#/verify-email" && session.token) { location.hash = "#/dashboard"; return; }
  renderNav();
  try {
    const book = routeHash.match(/^#\/book\/(\d+)$/);
    if (routeHash === "#/") homeView();
    else if (routeHash === "#/login") authView("login");
    else if (routeHash === "#/register") authView("register");
    else if (routeHash === "#/verify-email") await verifyEmailView(new URLSearchParams(hash.split("?")[1] || "").get("token"));
    else if (routeHash === "#/dashboard") await dashboardView();
    else if (routeHash === "#/books") await booksView();
    else if (book) await bookView(book[1]);
    else if (routeHash === "#/ai") aiView();
    else if (routeHash === "#/admin") await adminView();
    else location.hash = "#/";
  } catch (e) { show(h("div", { class: "msg err" }, e.message)); }
}
window.addEventListener("hashchange", route);
route();
