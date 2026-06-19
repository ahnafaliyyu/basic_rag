import requests
import yaml
import re  # Penting untuk regex di create_chunks
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

# Import parser PDF
from pdf_parser import extract_pdf_content, clean_extracted_text

# =====================================================
# CONFIG
# =====================================================

COLLECTION_NAME = "jsample"

client = QdrantClient(url="http://localhost:6333")

# =====================================================
# COLLECTION MANAGEMENT
# =====================================================

def ensure_collection_exists():
    """Pastikan collection ada, jika belum maka buat."""
    if not client.collection_exists(COLLECTION_NAME):
        print("ℹ️ Collection tidak ditemukan. Membuat collection baru...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=1024,
                distance=Distance.COSINE
            )
        )

# Jalankan saat startup
ensure_collection_exists()

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
# PDF PARSER (MULTI-METHOD)
# =====================================================

def extract_metadata_and_text_from_pdf(file_path):
    """Wrapper untuk parser PDF multi-method."""
    print(f"  📄 Menganalisis PDF: {Path(file_path).name}")
    
    metadata, raw_text = extract_pdf_content(file_path)
    cleaned_text = clean_extracted_text(raw_text)
    
    print(f"  ✓ Berhasil mengekstrak {len(cleaned_text)} karakter")
    
    return metadata, cleaned_text


# =====================================================
# CHUNKING (AMAN UNTUK OLLAMA EMBEDDING)
# =====================================================

def create_chunks(text, chunk_size=1200, overlap=300):
    """
    Chunking yang lebih pintar untuk dokumen JSA:
    - chunk_size 1200 karakter (aman untuk mxbai-embed-large)
    - overlap 300 agar konteks antar chunk tidak hilang
    - mencari batas chunk yang "pintar": akhir kalimat/paragraf
    """
    chunks = []
    start = 0
    
    # Normalisasi teks
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    while start < len(text):
        end = start + chunk_size
        
        # Cari batas chunk yang "pintar"
        if end < len(text):
            window = text[start:end]
            
            # Prioritas 1: akhir paragraf (\n\n)
            last_para = window.rfind('\n\n')
            # Prioritas 2: akhir kalimat (. atau \n)
            last_sentence = max(window.rfind('. '), window.rfind('.\n'), window.rfind('\n'))
            
            # Pilih pemotong terbaik yang berada di paruh kedua chunk
            best_break = -1
            if last_para > chunk_size // 2:
                best_break = last_para + 2
            elif last_sentence > chunk_size // 2:
                best_break = last_sentence + 1
            
            if best_break > 0:
                end = start + best_break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Hitung start berikutnya dengan overlap
        next_start = end - overlap
        if next_start <= start:  # Mencegah infinite loop
            next_start = start + chunk_size // 2
        start = next_start
    
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
    return data.get("embedding", [])


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
# QUERY EXPANSION
# =====================================================

def expand_query(question):
    """
    Memperkaya query user dengan kata kunci domain HSE/JSA
    agar pencarian vektor lebih akurat.
    """
    q = question.lower()
    keywords_to_add = []
    
    if any(w in q for w in ['bahaya', 'risiko', 'hazard', 'risk']):
        keywords_to_add.append("analisa keselamatan kerja")
    
    if any(w in q for w in ['tindakan', 'pengendalian', 'kontrol', 'preventif']):
        keywords_to_add.append("prosedur pencegahan kecelakaan")
    
    if any(w in q for w in ['apd', 'alat pelindung', 'helm', 'sepatu']):
        keywords_to_add.append("alat pelindung diri wajib")
    
    if any(w in q for w in ['jsa', 'job safety', 'jsea']):
        pass
    else:
        keywords_to_add.append("job safety analysis JSA tambang")
    
    if keywords_to_add:
        expanded = question + " " + " ".join(keywords_to_add)
        return expanded
    
    return question


# =====================================================
# SEARCH
# =====================================================

def search(query, limit=8):
    """Ambil lebih banyak kandidat agar konteks lebih lengkap."""
    expanded_query = expand_query(query)
    print(f"  🔍 Query asli   : {query}")
    print(f"  🔍 Query diperkaya: {expanded_query}")
    
    embedding = generate_embedding(expanded_query)
    
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        limit=limit,
        with_payload=True
    )
    return results.points


# =====================================================
# RAG (PROMPT DIPERKUAT)
# =====================================================

def ask_rag(question):
    points = search(question)
    
    if not points:
        return "❌ Data tidak ditemukan dalam knowledge base."
    
    # Bangun konteks dengan sumber yang jelas
    context_parts = []
    sources_seen = set()
    
    for i, point in enumerate(points, 1):
        source = point.payload.get("source", "tidak diketahui")
        source_name = Path(source).name
        text = point.payload["text"]
        
        context_parts.append(
            f"--- DOKUMEN #{i} (sumber: {source_name}) ---\n{text}"
        )
        sources_seen.add(source_name)
    
    context = "\n\n".join(context_parts)
    sources_list = ", ".join(sources_seen)
    
    # PROMPT YANG JAUH LEBIH KUAT
    prompt = f"""Anda adalah seorang Safety Officer (HSE) senior di perusahaan pertambangan Indonesia yang sangat berpengalaman dalam Job Safety Analysis (JSA).

ATURAN WAJIB - PATUHI DENGAN KETAT:
1. 🇮🇩 SELALU JAWAB DALAM BAHASA INDONESIA YANG BAKU DAN JELAS. JANGAN PERNAH menggunakan bahasa Inggris kecuali untuk istilah teknis yang memang tidak punya padanan (seperti "blind spot", "dumping point", "high wall").
2. Jawab HANYA berdasarkan KONTEKS di bawah ini. Jangan mengarang atau menggunakan pengetahuan umum di luar konteks.
3. Jika informasi yang diminta TIDAK ADA di konteks, jawab dengan jujur: "Maaf, informasi tersebut tidak ditemukan dalam dokumen JSA yang tersedia. Sumber yang saya miliki: {sources_list}."
4. Jika pertanyaan tentang suatu pekerjaan, SEBUTKAN nama pekerjaan dan tahapannya dengan jelas.
5. Untuk pertanyaan tentang bahaya/tindakan, gunakan FORMAT TERSTRUKTUR:
   - Tahap pekerjaan: ...
   - Potensi bahaya: ...
   - Tindakan pengendalian: ...
6. Jika ada APD yang disebutkan, DAFTARKAN dengan bullet points.
7. Gunakan penomoran dan bullet points agar jawaban mudah dibaca.

====================
KONTEKS DOKUMEN JSA
====================
{context}

====================
PERTANYAAN PENGGUNA
====================
{question}

====================
JAWABAN (dalam Bahasa Indonesia)
====================
"""
    
    return generate_response(prompt)


# =====================================================
# INGEST ONE FILE
# =====================================================

def ingest_file(file_path):
    print(f"\n{'='*50}")
    print(f"Processing: {file_path}")
    print(f"{'='*50}")
    
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext == ".mdx":
        metadata, article_content = extract_metadata_from_mdx(file_path)
    elif file_ext == ".pdf":
        metadata, article_content = extract_metadata_and_text_from_pdf(file_path)
    else:
        print(f"⚠️ Format file tidak didukung: {file_ext}")
        return

    if not article_content.strip():
        print("⚠️ Tidak ada konten yang bisa diekstrak. Melewati file ini.")
        return

    chunks = create_chunks(article_content)
    points = []

    for idx, chunk in enumerate(chunks):
        try:
            embedding = generate_embedding(chunk)
        except Exception as e:
            print(f"  ⚠️ Gagal generate embedding chunk {idx}: {e}")
            continue

        if len(embedding) == 0:
            print(f"  ⚠️ Embedding kosong pada chunk {idx}")
            continue

        point_id = abs(hash(f"{file_path}-{idx}")) % (10**12)

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
        try:
            # PERBAIKAN PENTING: Pastikan collection ada sebelum upsert
            ensure_collection_exists()
            
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True
            )
            print(f"✓ Inserted {len(points)} chunks")
        except Exception as e:
            print(f"⚠️ Gagal upsert ke Qdrant: {e}")
    else:
        print("⚠️ Tidak ada chunk yang berhasil di-insert")


# =====================================================
# INGEST FOLDER
# =====================================================

def ingest_articles():
    # Pastikan collection ada sebelum mulai ingest
    ensure_collection_exists()

    articles_folder = Path("articles")
    
    if not articles_folder.exists():
        print(f"⚠️ Folder '{articles_folder}' tidak ditemukan!")
        return
    
    files = list(articles_folder.glob("*.mdx")) + list(articles_folder.glob("*.pdf"))
    
    print(f"\n📁 Found {len(files)} files di folder '{articles_folder}'")

    for file in files:
        ingest_file(file)
    
    print(f"\n✅ Selesai memproses {len(files)} file")


# =====================================================
# MENU
# =====================================================

def main():
    while True:
        print("\n" + "="*50)
        print("📋 MENU APLIKASI RAG HSE")
        print("="*50)
        print("1. Ingest Articles (MDX & PDF)")
        print("2. Reset Collection (Hapus semua data)")
        print("3. Ask Question")
        print("4. Exit")

        choice = input("\nPilih menu: ")

        if choice == "1":
            ingest_articles()
        elif choice == "2":
            if input("⚠️ Yakin hapus semua data? (y/n): ").lower() == 'y':
                try:
                    client.delete_collection(COLLECTION_NAME)
                    print("✅ Collection dihapus. Silakan ingest ulang.")
                except Exception as e:
                    print(f"⚠️ Gagal menghapus collection: {e}")
        elif choice == "3":
            question = input("\n❓ Pertanyaan: ")
            print("\n⏳ Sedang memproses...")
            answer = ask_rag(question)
            print("\n" + "="*50)
            print("💡 JAWABAN:")
            print("="*50)
            print(answer)
        elif choice == "4":
            print("👋 Sampai jumpa!")
            break
        else:
            print("⚠️ Pilihan tidak valid")


if __name__ == "__main__":
    main()