import uuid

import pymupdf as fitz
import chromadb
from llm import ask_llm, get_provider_and_key


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


client = chromadb.Client()
collection = client.get_or_create_collection(name="pdf")


def index_pdf(path, filename=None):
    """Index a PDF and return (doc_id, number of chunks)."""
    filename = filename or path
    doc_id = uuid.uuid4().hex
    chunks = load_pdf(path)
    if chunks:
        collection.add(
            documents=[c[0] for c in chunks],
            ids=[f"{doc_id}-{i}" for i in range(len(chunks))],
            metadatas=[{"page": c[1], "filename": filename, "doc_id": doc_id} for c in chunks]
        )
    return doc_id, len(chunks)


def remove_pdf(doc_id):
    collection.delete(where={"doc_id": doc_id})


def ask(question, provider, api_key):
    if collection.count() == 0:
        return {"answer": "Upload a PDF first.", "sources": []}

    results = collection.query(query_texts=[question], n_results=min(5, collection.count()))
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context = "\n\n".join(
        f"[{m['filename']} p.{m['page']}]\n{d}" for d, m in zip(documents, metadatas)
    )
    prompt = f"Context:\n{context}\n\nQuestion: {question}"

    sources = []
    for m in metadatas:
        source = {"filename": m["filename"], "page": m["page"]}
        if source not in sources:
            sources.append(source)

    return {"answer": ask_llm(prompt, provider, api_key), "sources": sources}


if __name__ == '__main__':
    provider, api_key = get_provider_and_key()
    index_pdf('ai-pdf-chatbot-test.pdf')
    while True:
        q = input("\nAsk: ")
        if q == 'exit':
            break
        print(ask(q, provider, api_key)["answer"])
