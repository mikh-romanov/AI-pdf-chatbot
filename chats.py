"""Chats saved to data/chats.json: each chat has a name, its PDFs and its questions and answers."""
import json
import os
import threading
import time
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHATS_FILE = os.path.join(DATA_DIR, "chats.json")
DEFAULT_NAME = "New chat"

_lock = threading.Lock()


def _load():
    try:
        with open(CHATS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save(chats):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CHATS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CHATS_FILE)


def summary(chat):
    return {"id": chat["id"], "name": chat["name"], "pdf_count": len(chat["pdfs"]), "updated": chat["updated"]}


def list_chats():
    with _lock:
        chats = _load().values()
    return sorted((summary(c) for c in chats), key=lambda c: c["updated"], reverse=True)


def get_chat(chat_id):
    with _lock:
        return _load().get(chat_id)


def create_chat():
    now = time.time()
    chat = {"id": uuid.uuid4().hex, "name": DEFAULT_NAME, "renamed": False, "titled": False,
            "created": now, "updated": now, "pdfs": [], "messages": []}
    with _lock:
        chats = _load()
        chats[chat["id"]] = chat
        _save(chats)
    return chat


def update_chat(chat_id, change):
    """Apply change(chat) to a saved chat and return it, or None if the chat doesn't exist."""
    with _lock:
        chats = _load()
        chat = chats.get(chat_id)
        if chat is None:
            return None
        change(chat)
        _save(chats)
    return chat


def rename_chat(chat_id, name):
    def change(chat):
        chat["name"] = name
        chat["renamed"] = True
    return update_chat(chat_id, change)


def suggest_name(chat_id, name):
    """Name a chat from the model's suggestion, unless the user named it by hand."""
    def change(chat):
        if not chat["renamed"]:
            chat["name"] = name
            chat["titled"] = True
    return update_chat(chat_id, change)


def add_pdf(chat_id, pdf):
    def change(chat):
        chat["pdfs"].append(pdf)
        if not chat["renamed"] and not chat.get("titled") and chat["name"] == DEFAULT_NAME:
            chat["name"] = os.path.splitext(pdf["filename"])[0]
        chat["updated"] = time.time()
    return update_chat(chat_id, change)


def remove_pdf(chat_id, doc_id):
    def change(chat):
        chat["pdfs"] = [p for p in chat["pdfs"] if p["doc_id"] != doc_id]
    return update_chat(chat_id, change)


def add_message(chat_id, message):
    def change(chat):
        chat["messages"].append(message)
        chat["updated"] = time.time()
    return update_chat(chat_id, change)


def delete_chat(chat_id):
    with _lock:
        chats = _load()
        if chats.pop(chat_id, None) is None:
            return False
        _save(chats)
    return True
