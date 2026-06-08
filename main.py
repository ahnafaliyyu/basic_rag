import requests
import yaml
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

# =====================================================
# CONFIG
# =====================================================

COLLECTION_NAME = "jsample"

client = QdrantClient(
    url="http://localhost:6333"
)

# =====================================================
# COLLECTION
# =====================================================

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    )

# =====================================================
# MDX PARSER
# =====================================================

def extract_metadata_from_mdx(file_path):

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)

    if len(parts) < 3:
        return {}, content

    raw_metadata = parts[1]
    article_content = parts[2].strip()

    try:
        metadata = yaml.safe_load(raw_metadata)

        if metadata is None:
            metadata = {}

    except yaml.YAMLError:
        metadata = {}

    return metadata, article_content

# =====================================================
# CHUNKING
# =====================================================

def create_chunks(
    text,
    chunk_size=1000,
    overlap=150
):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks

# =====================================================
# EMBEDDING
# =====================================================

def generate_embedding(text):

    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "mxbai-embed-large",
            "prompt": text
        }
    )

    response.raise_for_status()

    data = response.json()

    embedding = data.get("embedding", [])

    return embedding

# =====================================================
# LLM
# =====================================================

def generate_response(prompt):

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    response.raise_for_status()

    return response.json()["response"]

# =====================================================
# INGEST ONE FILE
# =====================================================

def ingest_file(file_path):

    print(f"Processing: {file_path}")

    metadata, article_content = extract_metadata_from_mdx(
        file_path
    )

    chunks = create_chunks(article_content)

    points = []

    for idx, chunk in enumerate(chunks):

        embedding = generate_embedding(chunk)

        if len(embedding) == 0:
            print(
                f"Embedding kosong pada chunk {idx}"
            )
            continue

        point_id = abs(
            hash(f"{file_path}-{idx}")
        ) % (10**12)

        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "source": str(file_path),
                    "chunk_index": idx,
                    "text": chunk,
                    "metadata": metadata
                }
            )
        )

    if points:

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )

        print(
            f"Inserted {len(points)} chunks"
        )

# =====================================================
# INGEST FOLDER
# =====================================================

def ingest_articles():

    articles_folder = Path("articles")

    files = list(
        articles_folder.glob("*.mdx")
    )

    print(
        f"Found {len(files)} files"
    )

    for file in files:
        ingest_file(file)

# =====================================================
# SEARCH
# =====================================================

def search(query, limit=5):

    embedding = generate_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        limit=limit,
        with_payload=True
    )

    return results.points

# =====================================================
# RAG
# =====================================================

def ask_rag(question):

    points = search(question)

    if not points:
        return "Data tidak ditemukan."

    context = "\n\n".join(
        point.payload["text"]
        for point in points
    )

    prompt = f"""
Anda adalah asisten HSE pertambangan.

Gunakan konteks berikut untuk menjawab.

====================
KONTEKS
====================

{context}

====================
PERTANYAAN
====================

{question}

====================
ATURAN
====================

- Jawab hanya berdasarkan konteks.
- Jika informasi tidak tersedia,
  katakan bahwa informasi tidak ditemukan.
- Berikan jawaban ringkas namun jelas.

====================
JAWABAN
====================
"""

    return generate_response(prompt)

# =====================================================
# MENU
# =====================================================

def main():

    while True:

        print("\n===== MENU =====")
        print("1. Ingest Articles")
        print("2. Ask Question")
        print("3. Exit")

        choice = input(
            "\nPilih menu: "
        )

        if choice == "1":

            ingest_articles()

        elif choice == "2":

            question = input(
                "\nPertanyaan: "
            )

            answer = ask_rag(question)

            print("\n===== JAWABAN =====")
            print(answer)

        elif choice == "3":

            break

        else:

            print(
                "Pilihan tidak valid"
            )

if __name__ == "__main__":
    main()