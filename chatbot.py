import os
import uuid

import pymupdf as fitz
import chromadb
from llm import ask_llm, get_provider_and_key

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HISTORY_TURNS = 4           # earlier questions and answers sent along with a new question
HISTORY_ANSWER_CHARS = 1200


def load_pdf(path):
    doc = fitz.open(path)
    chunks = []
    for i, page in enumerate(doc):
        text = page.get_text()
        for j in range(0, len(text), 800):
            chunk = text[j:j+800]
            if chunk.strip():
                chunks.append((chunk, i + 1))
    return chunks


# Saved on disk, so indexed PDFs survive a server restart.
client = chromadb.PersistentClient(path=os.path.join(DATA_DIR, "chroma"))
collection = client.get_or_create_collection(name="pdf")


def index_pdf(path, filename=None, chat_id="default"):
    """Index a PDF for one chat and return (doc_id, number of chunks)."""
    filename = filename or path
    doc_id = uuid.uuid4().hex
    chunks = load_pdf(path)
    if chunks:
        collection.add(
            documents=[c[0] for c in chunks],
            ids=[f"{doc_id}-{i}" for i in range(len(chunks))],
            metadatas=[{"page": c[1], "filename": filename, "doc_id": doc_id, "chat_id": chat_id} for c in chunks]
        )
    return doc_id, len(chunks)


def remove_pdf(doc_id):
    collection.delete(where={"doc_id": doc_id})


def remove_chat(chat_id):
    collection.delete(where={"chat_id": chat_id})


def ask(question, provider, api_key, chat_id="default", history=()):
    """Answer from the PDFs of one chat. history is a list of earlier {"question", "answer"} pairs."""
    where = {"chat_id": chat_id}
    count = len(collection.get(where=where, include=[])["ids"])
    if count == 0:
        return {"answer": "Upload a PDF first.", "sources": []}

    results = collection.query(query_texts=[question], n_results=min(5, count), where=where)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context = "\n\n".join(
        f"[{m['filename']} p.{m['page']}]\n{d}" for d, m in zip(documents, metadatas)
    )
    earlier = "\n\n".join(
        f"Q: {h['question']}\nA: {h['answer'][:HISTORY_ANSWER_CHARS]}" for h in list(history)[-HISTORY_TURNS:]
    )
    prompt = f"Context:\n{context}\n\n"
    if earlier:
        prompt += f"Earlier in this conversation:\n{earlier}\n\n"
    prompt += f"Question: {question}"

    return {"answer": ask_llm(prompt, provider, api_key),
            "sources": collect_sources(results["ids"][0], documents, metadatas)}


def collect_sources(ids, documents, metadatas):
    """One source per (file, page), in the order they were found, with the text used from that page.

    Chunks are cut every 800 characters, so neighbouring chunks of a page are joined back together
    before being shown as one excerpt."""
    pages = {}
    for chunk_id, text, m in zip(ids, documents, metadatas):
        key = (m["filename"], m["page"])
        pages.setdefault(key, []).append((int(chunk_id.rsplit("-", 1)[1]), text))

    sources = []
    for (filename, page), chunks in pages.items():
        excerpts, last = [], None
        for index, text in sorted(chunks):
            if last is not None and index == last + 1:
                excerpts[-1] += text
            else:
                excerpts.append(text)
            last = index
        sources.append({
            "filename": filename,
            "page": page,
            "excerpts": [" ".join(e.split()) for e in excerpts],
        })
    return sources


if __name__ == '__main__':
    provider, api_key = get_provider_and_key()
    remove_chat("cli")  # start fresh instead of piling up copies in the saved index
    index_pdf('ai-pdf-chatbot-test.pdf', chat_id="cli")
    history = []
    while True:
        q = input("\nAsk: ")
        if q == 'exit':
            break
        answer = ask(q, provider, api_key, chat_id="cli", history=history)["answer"]
        history.append({"question": q, "answer": answer})
        print(answer)
