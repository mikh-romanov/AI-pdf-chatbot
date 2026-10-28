import os
import tempfile

import pymupdf as fitz
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import chatbot
import chats
import llm
from llm import ERROR_MESSAGE, PROVIDERS, RATE_LIMIT_MESSAGE, default_settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="AI PDF Chatbot")

# The provider and key stay in memory only; chats and their PDFs are saved in data/.
provider, api_key = default_settings()
settings = {"provider": provider or "openrouter", "api_key": api_key,
            "models": dict(llm.DEFAULT_MODELS)}   # the chosen model, per provider


class Settings(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""


class Question(BaseModel):
    question: str


class Rename(BaseModel):
    name: str


def find_chat(chat_id):
    chat = chats.get_chat(chat_id)
    if chat is None:
        raise HTTPException(404, "This chat no longer exists")
    return chat


@app.get("/api/chats")
def list_chats():
    return chats.list_chats()


@app.post("/api/chats")
def create_chat():
    return chats.create_chat()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    return find_chat(chat_id)


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: Rename):
    name = body.name.strip()[:120]
    if not name:
        raise HTTPException(400, "A chat name can't be empty")
    find_chat(chat_id)
    return chats.rename_chat(chat_id, name)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    find_chat(chat_id)
    chatbot.remove_chat(chat_id)
    chats.delete_chat(chat_id)
    return {"ok": True}


@app.post("/api/chats/{chat_id}/pdfs")
def upload_pdfs(chat_id: str, files: list[UploadFile]):
    find_chat(chat_id)
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"{file.filename} is not a PDF")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file.file.read())
            path = tmp.name
        try:
            try:
                with fitz.open(path) as doc:
                    pages = doc.page_count
            except Exception:
                raise HTTPException(400, f"Could not read {file.filename}")
            doc_id, chunk_count = chatbot.index_pdf(path, file.filename, chat_id)
        finally:
            os.remove(path)

        chats.add_pdf(chat_id, {"doc_id": doc_id, "filename": file.filename, "pages": pages, "chunks": chunk_count})
    return find_chat(chat_id)


@app.delete("/api/chats/{chat_id}/pdfs/{doc_id}")
def delete_pdf(chat_id: str, doc_id: str):
    chat = find_chat(chat_id)
    if not any(p["doc_id"] == doc_id for p in chat["pdfs"]):
        raise HTTPException(404, "PDF not found in this chat")
    chatbot.remove_pdf(doc_id)
    return chats.remove_pdf(chat_id, doc_id)


@app.post("/api/chats/{chat_id}/title")
def title_chat(chat_id: str):
    """Name the chat after its first exchange. A chat you renamed yourself is left alone."""
    chat = find_chat(chat_id)
    if chat["renamed"] or not chat["messages"] or not settings["api_key"]:
        return chat

    first = chat["messages"][0]
    title = llm.suggest_title(first["question"], first["answer"], settings["provider"],
                              settings["api_key"], settings["models"][settings["provider"]])
    return chats.suggest_name(chat_id, title) if title else chat


@app.get("/api/settings")
def get_settings():
    return {"provider": settings["provider"], "has_key": bool(settings["api_key"]),
            "providers": PROVIDERS, "model": settings["models"][settings["provider"]]}


@app.get("/api/models")
def list_models():
    """Models the current provider offers for this key, for the dropdown."""
    provider, key = settings["provider"], settings["api_key"]
    if not key:
        raise HTTPException(400, f"Add an API key for {provider} first")
    try:
        models = llm.list_models(provider, key)
    except Exception as e:
        raise HTTPException(502, f"Could not load models: {e}")
    return {"models": models, "model": settings["models"][provider]}


@app.post("/api/settings")
def save_settings(new: Settings):
    if new.provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {new.provider}")
    key = new.api_key.strip()
    if not key and new.provider == settings["provider"]:
        key = settings["api_key"]  # keep the current key when only re-saving
    if not key:
        key = os.getenv(f"{new.provider.upper()}_API_KEY")  # fall back to .env
    model = new.model.strip() or settings["models"][new.provider]
    settings["models"][new.provider] = model
    settings.update(provider=new.provider, api_key=key or None)
    if key:
        llm.remember_settings(new.provider, key, model)  # so both survive a restart
    return get_settings()


@app.post("/api/chats/{chat_id}/ask")
def ask(chat_id: str, q: Question):
    chat = find_chat(chat_id)
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "Type a question first")
    if not chat["pdfs"]:
        raise HTTPException(400, "Add a PDF to this chat first")
    if not settings["api_key"]:
        raise HTTPException(400, f"Add an API key for {settings['provider']} under Model")

    result = chatbot.ask(question, settings["provider"], settings["api_key"], chat_id, chat["messages"],
                         model=settings["models"][settings["provider"]])
    if result["answer"] in (RATE_LIMIT_MESSAGE, ERROR_MESSAGE):
        raise HTTPException(502, result["answer"])  # don't save failed answers into the chat

    message = {"question": question, "answer": result["answer"], "sources": result["sources"]}
    chats.add_message(chat_id, message)
    return message


# Serve the page (index.html, style.css, app.js) at the site root. Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
