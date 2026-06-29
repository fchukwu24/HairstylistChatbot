"""Haircare knowledge base: chunking, embedding, and retrieval with FAISS.
"""

import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VECTOR_DB_DIR = os.path.join(os.path.dirname(__file__), ".faiss_vector_db")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

vector_db = None  # lazily loaded/built on first use


def load_documents():
    docs = []
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".md"):
            continue
        with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
            text = f.read()
        docs.append(Document(page_content=text, metadata={"source": filename}))
    return docs


def build_vector_db():
    """Chunk file(s) in data/ and build a fresh FAISS vectorDB, saved to disk."""
    raw_docs = load_documents()
    chunks = splitter.split_documents(raw_docs)
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(VECTOR_DB_DIR)
    print(f"Indexed {len(chunks)} chunks from {len(raw_docs)} file(s) into {VECTOR_DB_DIR}")
    return db


def load_vector_db():
    """Load the saved vectorDB, building it the first time it doesn't exist yet.
    """
    global vector_db
    if vector_db is not None:
        return vector_db
    vector_db_file = os.path.join(VECTOR_DB_DIR, "index.faiss")
    if not os.path.exists(vector_db_file):
        vector_db = build_vector_db()
    else:
        vector_db = FAISS.load_local(
            VECTOR_DB_DIR, embeddings, allow_dangerous_deserialization=True
        )
    return vector_db


def search_knowledge_base(query: str, k: int = 2, max_distance: float = 0.95,
) -> str | None:
    """Retrieve the most relevant haircare chunks for a query.
    This is what the search_haircare_knowledge tool calls."""
    vector_db = load_vector_db()
    results = vector_db.similarity_search_with_score(query, k=k)
    if not results:
        return "No relevant haircare information was found."
    
    relevant_results = [
        (doc, score)
        for doc, score in results
        if score <= max_distance
    ]
    if not relevant_results:
        return "No relevant haircare information was found."
    return "\n\n---\n\n".join(f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"for doc, score in relevant_results)

    