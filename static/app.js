const $ = (id) => document.getElementById(id);

async function api(method, url, body) {
  const options = { method };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    if (location.protocol === "file:") throw new TypeError("opened as a file");
    res = await fetch(url, options);
  } catch {
    $("server-banner").hidden = false;
    throw new Error("Can't reach the server. Start it and open http://127.0.0.1:8000");
  }
  $("server-banner").hidden = true;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data;
}

/* ---------- Chats ---------- */

let chat = null;       // the open chat: {id, name, pdfs, messages}
let chatList = [];     // summaries for the shelf: {id, name, pdf_count}
const LAST_CHAT_KEY = "pdf-chatbot:last-chat";

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function remember(id) {
  try { localStorage.setItem(LAST_CHAT_KEY, id); } catch {}
}

function remembered() {
  try { return localStorage.getItem(LAST_CHAT_KEY); } catch { return null; }
}

function renderChatList() {
  const ul = $("chat-list");
  ul.replaceChildren();
  for (const c of chatList) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chat-link";
    if (chat && c.id === chat.id) button.setAttribute("aria-current", "true");
    const name = document.createElement("span");
    name.className = "chat-link-name";
    name.textContent = c.name;
    const meta = document.createElement("span");
    meta.className = "chat-link-meta";
    meta.textContent = c.pdf_count ? plural(c.pdf_count, "PDF") : "No PDFs";
    button.append(name, meta);
    button.addEventListener("click", () => openChat(c.id));
    li.append(button);
    ul.append(li);
  }
}

async function refreshChatList() {
  chatList = await api("GET", "/api/chats");
  renderChatList();
}

// Show a chat returned by the server and keep the shelf summary in step with it.
function showChat(data, { redrawThread = true } = {}) {
  chat = data;
  remember(chat.id);
  const name = $("chat-name");
  if (document.activeElement !== name) name.value = chat.name;
  renderPdfs();
  if (redrawThread) renderThread();

  const summary = chatList.find((c) => c.id === chat.id);
  if (summary) {
    summary.name = chat.name;
    summary.pdf_count = chat.pdfs.length;
  }
  renderChatList();
}

async function openChat(id) {
  if (chat && chat.id === id) return;
  setUploadStatus("");
  try {
    showChat(await api("GET", `/api/chats/${id}`));
  } catch (e) {
    await refreshChatList();
    if (chatList.length) showChat(await api("GET", `/api/chats/${chatList[0].id}`));
  }
}

async function newChat() {
  const created = await api("POST", "/api/chats");
  chatList.unshift({ id: created.id, name: created.name, pdf_count: 0 });
  showChat(created);
  question.focus();
}

$("new-chat").addEventListener("click", () => newChat().catch(() => {}));

async function saveName() {
  const input = $("chat-name");
  const name = input.value.trim();
  if (!chat) return;
  if (!name || name === chat.name) {
    input.value = chat.name;
    return;
  }
  try {
    showChat(await api("PATCH", `/api/chats/${chat.id}`, { name }), { redrawThread: false });
  } catch {
    input.value = chat.name;
  }
}

$("chat-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); e.target.blur(); }
  if (e.key === "Escape") { e.target.value = chat ? chat.name : ""; e.target.blur(); }
});
$("chat-name").addEventListener("blur", saveName);

$("delete-chat").addEventListener("click", async () => {
  if (!chat) return;
  const pdfNote = chat.pdfs.length ? ` and its ${plural(chat.pdfs.length, "PDF")}` : "";
  if (!confirm(`Delete "${chat.name}"${pdfNote}? This can't be undone.`)) return;
  try {
    await api("DELETE", `/api/chats/${chat.id}`);
    chatList = chatList.filter((c) => c.id !== chat.id);
    chat = null;
    if (chatList.length) await openChat(chatList[0].id);
    else await newChat();
  } catch {}
});

/* ---------- PDFs in the open chat ---------- */

function renderPdfs() {
  const pdfs = chat ? chat.pdfs : [];
  const ul = $("pdf-list");
  ul.replaceChildren();
  $("pdf-empty").hidden = pdfs.length > 0;

  for (const pdf of pdfs) {
    const li = document.createElement("li");

    const info = document.createElement("div");
    info.className = "pdf-info";
    const name = document.createElement("div");
    name.className = "pdf-name";
    name.textContent = pdf.filename;
    name.title = pdf.filename;
    const meta = document.createElement("div");
    meta.className = "pdf-meta";
    meta.textContent = pdf.chunks === 0
      ? `${plural(pdf.pages, "page")}, no readable text`
      : plural(pdf.pages, "page");
    info.append(name, meta);

    const remove = document.createElement("button");
    remove.className = "remove";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", `Remove ${pdf.filename}`);
    remove.addEventListener("click", async () => {
      try {
        showChat(await api("DELETE", `/api/chats/${chat.id}/pdfs/${pdf.doc_id}`), { redrawThread: false });
        updateDropHint();
      } catch (e) {
        setUploadStatus(e.message, true);
      }
    });

    li.append(info, remove);
    ul.append(li);
  }
}

function updateDropHint() {
  const hint = document.querySelector("#welcome .drop-hint");
  if (!hint) return;
  const count = chat ? chat.pdfs.length : 0;
  hint.replaceChildren();
  if (count) {
    hint.textContent = `${plural(count, "PDF")} ready. Type your question below, or drop another PDF onto this page.`;
  } else {
    const link = document.createElement("span");
    link.className = "link";
    link.textContent = "choose files";
    hint.append("Drop a PDF onto this page, or ", link, ".");
  }
}

function setUploadStatus(text, isError = false) {
  const el = $("upload-status");
  el.hidden = !text;
  el.textContent = text || "";
  el.classList.toggle("error", isError);
}

async function uploadFiles(fileList) {
  if (!chat) return;
  const files = [...fileList].filter((f) => f.name.toLowerCase().endsWith(".pdf"));
  if (!files.length) {
    setUploadStatus("Only PDF files can be added.", true);
    return;
  }
  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  const target = chat.id;
  const label = files.length === 1 ? files[0].name : plural(files.length, "PDF");
  $("add-pdf").classList.add("busy");
  setUploadStatus(`Reading ${label}…`);
  try {
    const updated = await api("POST", `/api/chats/${target}/pdfs`, form);
    if (chat && chat.id === target) {
      showChat(updated, { redrawThread: false });
      updateDropHint();
      setUploadStatus(`Added ${label}.`);
    } else {
      await refreshChatList();
    }
  } catch (e) {
    setUploadStatus(e.message, true);
  } finally {
    $("add-pdf").classList.remove("busy");
    $("file-input").value = "";
  }
}

$("file-input").addEventListener("change", (e) => uploadFiles(e.target.files));

// Drop a PDF anywhere on the reading area to add it to the open chat.
const readingArea = $("reading");
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
readingArea.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth++;
  document.body.classList.add("dragging");
});
readingArea.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
readingArea.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) document.body.classList.remove("dragging");
});
readingArea.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("dragging");
  uploadFiles(e.dataTransfer.files);
});

/* ---------- Model settings ---------- */

function renderSettings(s) {
  $("provider").value = s.provider;
  const status = $("key-status");
  status.textContent = s.has_key ? "Key saved" : "No key yet";
  status.classList.toggle("ok", s.has_key);
}

$("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const s = await api("POST", "/api/settings", {
      provider: $("provider").value,
      api_key: $("api-key").value,
    });
    $("api-key").value = "";
    renderSettings(s);
  } catch (err) {
    const status = $("key-status");
    status.textContent = err.message;
    status.classList.remove("ok");
  }
});

/* ---------- Questions and answers ---------- */

// Minimal markdown for model answers: headings, bullet/numbered lists, **bold**, *italic*, `code`.
// Text is HTML-escaped before any tags are added, so model output can't inject markup.
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function inlineMarkdown(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}

function renderMarkdown(text) {
  const html = [];
  let list = null;
  const closeList = () => { if (list) { html.push(`</${list}>`); list = null; } };

  for (const line of text.split("\n")) {
    const bullet = line.match(/^\s*[-*]\s+(.*)/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)/);
    const heading = line.match(/^#{1,6}\s+(.*)/);
    if (bullet || numbered) {
      const tag = bullet ? "ul" : "ol";
      if (list !== tag) { closeList(); html.push(`<${tag}>`); list = tag; }
      html.push(`<li>${inlineMarkdown((bullet || numbered)[1])}</li>`);
    } else {
      closeList();
      if (heading) html.push(`<h4>${inlineMarkdown(heading[1])}</h4>`);
      else if (line.trim()) html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }
  closeList();
  return html.join("");
}

function scrollToEnd() {
  const box = $("messages");
  box.scrollTop = box.scrollHeight;
}

function renderThread() {
  hideSlip();
  const box = $("messages");
  box.replaceChildren();
  if (!chat.messages.length) {
    box.append($("welcome-template").content.cloneNode(true));
    updateDropHint();
    box.scrollTop = 0;
    return;
  }
  for (const m of chat.messages) {
    addAnswer(addQuestion(m.question), "answer", m.answer, m.sources, { fresh: false });
  }
  scrollToEnd();
}

function addQuestion(text) {
  $("welcome")?.remove();
  const entry = document.createElement("div");
  entry.className = "entry";
  const q = document.createElement("p");
  q.className = "question";
  q.textContent = text;
  entry.append(q);
  $("messages").append(entry);
  scrollToEnd();
  return entry;
}

function addAnswer(entry, kind, text, sources = [], { fresh = true } = {}) {
  const a = document.createElement("div");
  a.className = kind === "answer" ? "answer" : `answer ${kind}`;
  if (fresh) a.classList.add("fresh"); // only new answers draw their highlighter tabs
  if (kind === "answer") a.innerHTML = renderMarkdown(text);
  else a.textContent = text;

  // Cited pages, grouped by file: the file name once, then a highlighter tab per page.
  // Hovering, focusing or tapping a tab shows the text the answer was built from.
  const byFile = new Map();
  for (const s of sources) {
    if (!byFile.has(s.filename)) byFile.set(s.filename, []);
    byFile.get(s.filename).push(s);
  }
  let i = 0;
  for (const [filename, fileSources] of byFile) {
    const group = document.createElement("div");
    group.className = "source";
    const name = document.createElement("span");
    name.className = "source-file";
    name.textContent = filename;
    const tabs = document.createElement("span");
    tabs.className = "tabs";
    for (const source of [...fileSources].sort((x, y) => x.page - y.page)) {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "tab";
      tab.style.setProperty("--i", i++);
      tab.textContent = `p. ${source.page}`;
      tab.setAttribute("aria-label", `Page ${source.page} of ${filename}: show the text used`);
      attachExcerpt(tab, source);
      tabs.append(tab);
    }
    group.append(name, tabs);
    a.append(group);
  }

  entry.append(a);
  scrollToEnd();
  return a;
}

/* ---------- Excerpt slip for a cited page ---------- */

const slip = $("excerpt");
let slipAnchor = null;
let hideTimer = null;

function fillSlip(source) {
  $("excerpt-where").textContent = `${source.filename}, page ${source.page}`;
  const body = $("excerpt-text");
  body.replaceChildren();
  const excerpts = source.excerpts || [];
  if (!excerpts.length) {
    const p = document.createElement("p");
    p.className = "excerpt-missing";
    p.textContent = "This answer was saved before excerpts were kept. Ask the question again to see the text.";
    body.append(p);
    return;
  }
  for (const text of excerpts) {
    const p = document.createElement("p");
    p.textContent = `…${text}…`; // chunks are cut mid-sentence, so mark both ends as partial
    body.append(p);
  }
}

function placeSlip(tab) {
  const gap = 10;
  const margin = 12;
  const r = tab.getBoundingClientRect();
  const w = slip.offsetWidth;
  const h = slip.offsetHeight;
  const left = Math.min(Math.max(r.left + r.width / 2 - w / 2, margin), innerWidth - w - margin);
  const above = r.top - h - gap;
  const top = above >= margin ? above : Math.min(r.bottom + gap, innerHeight - h - margin);
  slip.style.left = `${left}px`;
  slip.style.top = `${top}px`;
}

function showSlip(tab, source) {
  clearTimeout(hideTimer);
  if (slipAnchor && slipAnchor !== tab) slipAnchor.removeAttribute("aria-describedby");
  slipAnchor = tab;
  fillSlip(source);
  slip.hidden = false;
  $("excerpt-text").scrollTop = 0;
  placeSlip(tab);
  tab.setAttribute("aria-describedby", "excerpt");
  tab.setAttribute("aria-expanded", "true");
}

function hideSlip() {
  clearTimeout(hideTimer);
  slip.hidden = true;
  if (slipAnchor) {
    slipAnchor.removeAttribute("aria-describedby");
    slipAnchor.setAttribute("aria-expanded", "false");
  }
  slipAnchor = null;
}

// A short delay lets the pointer move from the tab onto the slip to scroll a long excerpt.
function hideSlipSoon() {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(hideSlip, 180);
}

function attachExcerpt(tab, source) {
  tab.setAttribute("aria-expanded", "false");
  tab.addEventListener("mouseenter", () => showSlip(tab, source));
  tab.addEventListener("mouseleave", hideSlipSoon);
  tab.addEventListener("focus", () => showSlip(tab, source));
  tab.addEventListener("blur", hideSlipSoon);
  tab.addEventListener("click", () => (slipAnchor === tab && !slip.hidden ? hideSlip() : showSlip(tab, source)));
}

slip.addEventListener("mouseenter", () => clearTimeout(hideTimer));
slip.addEventListener("mouseleave", hideSlipSoon);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !slip.hidden) hideSlip(); });
document.addEventListener("pointerdown", (e) => {
  if (!slip.hidden && !slip.contains(e.target) && !e.target.closest(".tab")) hideSlip();
});
$("messages").addEventListener("scroll", () => { if (!slip.hidden) hideSlip(); });
addEventListener("resize", () => { if (!slip.hidden) hideSlip(); });

const question = $("question");

function autoresize() {
  question.style.height = "auto";
  question.style.height = `${question.scrollHeight}px`;
}
question.addEventListener("input", autoresize);
question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("ask-form").requestSubmit();
  }
});

$("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = question.value.trim();
  if (!text || !chat) return;

  const target = chat;
  const entry = addQuestion(text);
  question.value = "";
  autoresize();
  $("send").disabled = true;
  const names = target.pdfs.map((p) => p.filename);
  const waiting = addAnswer(entry, "thinking",
    names.length === 1 ? `Reading ${names[0]}…` : names.length ? `Reading ${plural(names.length, "PDF")}…` : "Reading…");

  try {
    const message = await api("POST", `/api/chats/${target.id}/ask`, { question: text });
    target.messages.push(message);
    waiting.remove();
    if (chat === target) addAnswer(entry, "answer", message.answer, message.sources);
    const summary = chatList.find((c) => c.id === target.id);
    if (summary) chatList = [summary, ...chatList.filter((c) => c !== summary)]; // most recent first
    renderChatList();
  } catch (err) {
    waiting.remove();
    if (chat === target) addAnswer(entry, "error", err.message);
  } finally {
    $("send").disabled = false;
    question.focus();
  }
});

/* ---------- Start ---------- */

async function start() {
  await refreshChatList();
  const last = remembered();
  const first = chatList.find((c) => c.id === last) || chatList[0];
  if (first) await openChat(first.id);
  else await newChat();
}

start().catch(() => {});
api("GET", "/api/settings").then(renderSettings).catch(() => {});
