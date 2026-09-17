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

/* ---------- PDFs ---------- */

function renderPdfs(pdfs) {
  const list = $("pdf-list");
  list.replaceChildren();
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
    meta.textContent = `${pdf.pages} page${pdf.pages === 1 ? "" : "s"}` +
      (pdf.chunks === 0 ? " · no text found" : "");
    info.append(name, meta);

    const del = document.createElement("button");
    del.className = "icon-btn";
    del.type = "button";
    del.textContent = "×";
    del.title = "Remove";
    del.setAttribute("aria-label", `Remove ${pdf.filename}`);
    del.addEventListener("click", async () => {
      try {
        await api("DELETE", `/api/pdfs/${pdf.doc_id}`);
        loadPdfs();
      } catch (e) {
        setUploadStatus(e.message, true);
      }
    });

    li.append(info, del);
    list.append(li);
  }
}

async function loadPdfs() {
  renderPdfs(await api("GET", "/api/pdfs"));
}

function setUploadStatus(text, isError = false) {
  const el = $("upload-status");
  el.hidden = !text;
  el.textContent = text || "";
  el.classList.toggle("error", isError);
}

async function uploadFiles(fileList) {
  const files = [...fileList].filter((f) => f.name.toLowerCase().endsWith(".pdf"));
  if (!files.length) {
    setUploadStatus("Please choose PDF files.", true);
    return;
  }
  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  const zone = $("dropzone");
  zone.classList.add("busy");
  setUploadStatus(`Indexing ${files.length} file${files.length === 1 ? "" : "s"}…`);
  try {
    await api("POST", "/api/pdfs", form);
    setUploadStatus("");
  } catch (e) {
    setUploadStatus(e.message, true);
  } finally {
    zone.classList.remove("busy");
    $("file-input").value = "";
    loadPdfs();
  }
}

const zone = $("dropzone");
$("file-input").addEventListener("change", (e) => uploadFiles(e.target.files));
["dragenter", "dragover"].forEach((type) =>
  zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((type) =>
  zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
zone.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));

/* ---------- Settings ---------- */

function renderSettings(s) {
  $("provider").value = s.provider;
  const badge = $("key-status");
  badge.textContent = s.has_key ? "Key set" : "No key";
  badge.classList.toggle("ok", s.has_key);
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
    addMessage("error", err.message);
  }
});

/* ---------- Chat ---------- */

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

function addMessage(kind, text, sources = []) {
  $("welcome")?.remove();
  const msg = document.createElement("div");
  msg.className = `msg ${kind}`;
  if (kind === "bot") {
    msg.classList.add("markdown");
    msg.innerHTML = renderMarkdown(text);
  } else {
    msg.textContent = text;
  }

  if (sources.length) {
    const wrap = document.createElement("div");
    wrap.className = "sources";
    for (const s of sources) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `${s.filename} · p.${s.page}`;
      wrap.append(chip);
    }
    msg.append(wrap);
  }

  const box = $("messages");
  box.append(msg);
  box.scrollTop = box.scrollHeight;
  return msg;
}

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
  if (!text) return;

  addMessage("user", text);
  question.value = "";
  autoresize();
  $("send").disabled = true;
  const thinking = addMessage("bot thinking", "Thinking…");

  try {
    const res = await api("POST", "/api/ask", { question: text });
    thinking.remove();
    addMessage("bot", res.answer, res.sources);
  } catch (err) {
    thinking.remove();
    addMessage("error", err.message);
  } finally {
    $("send").disabled = false;
    question.focus();
  }
});

/* ---------- Init ---------- */

loadPdfs().catch(() => {});
api("GET", "/api/settings").then(renderSettings).catch(() => {});
