import os
import tempfile

import pymupdf as fitz
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import chatbot
from llm import PROVIDERS, default_settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="AI PDF Chatbot")

# In-memory state: lives as long as the server process, like the Chroma collection.
pdfs = {}
provider, api_key = default_settings()
settings = {"provider": provider or "openrouter", "api_key": api_key}


class Settings(BaseModel):
    provider: str
    api_key: str = ""


class Question(BaseModel):
    question: str


@app.get("/api/pdfs")
def list_pdfs():
    return list(pdfs.values())


@app.post("/api/pdfs")
def upload_pdfs(files: list[UploadFile]):
    added = []
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
            doc_id, chunks = chatbot.index_pdf(path, file.filename)
        finally:
            os.remove(path)

        info = {"doc_id": doc_id, "filename": file.filename, "pages": pages, "chunks": chunks}
        pdfs[doc_id] = info
        added.append(info)
    return added


@app.delete("/api/pdfs/{doc_id}")
def delete_pdf(doc_id: str):
    if doc_id not in pdfs:
        raise HTTPException(404, "PDF not found")
    chatbot.remove_pdf(doc_id)
    del pdfs[doc_id]
    return {"ok": True}


@app.get("/api/settings")
def get_settings():
    return {"provider": settings["provider"], "has_key": bool(settings["api_key"]), "providers": PROVIDERS}


@app.post("/api/settings")
def save_settings(new: Settings):
    if new.provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {new.provider}")
    key = new.api_key.strip()
    if not key and new.provider == settings["provider"]:
        key = settings["api_key"]  # keep the current key when only re-saving
    if not key:
        key = os.getenv(f"{new.provider.upper()}_API_KEY")  # fall back to .env
    settings.update(provider=new.provider, api_key=key or None)
    return get_settings()


@app.post("/api/ask")
def ask(q: Question):
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")
    if not pdfs:
        raise HTTPException(400, "Upload a PDF first")
    if not settings["api_key"]:
        raise HTTPException(400, f"Set an API key for {settings['provider']} in Settings")
    return chatbot.ask(question, settings["provider"], settings["api_key"])


# Serve the page (index.html, style.css, app.js) at the site root. Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
