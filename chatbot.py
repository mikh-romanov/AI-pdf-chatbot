import fitz
import chromadb
from llm import ask_llm


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
collection = client.create_collection(name="pdf")

def index_pdf(path):
    chunks = load_pdf(path)
    collection.add(
        documents=[c[0] for c in chunks],
        ids=[f"{i}" for i in range(len(chunks))],
        metadatas=[{"page": c[1]} for c in chunks]
    )


def ask(question):
    results = collection.query(query_texts=[question], n_results=5)
    context = "\n\n".join(results["documents"][0])
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    return ask_llm(prompt)


if __name__ == '__main__':
    index_pdf('ai-pdf-chatbot-test.pdf')
    while True:
        q = input("\nAsk: ")
        if q == 'exit':
            break
        print(ask(q))