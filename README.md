# 🪖 RAG HSE Pertambangan - Job Safety Analysis Assistant

> Asisten virtual berbasis **Retrieval-Augmented Generation (RAG)** untuk menjawab pertanyaan seputar **Job Safety Analysis (JSA)** di lingkungan pertambangan Indonesia.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Qdrant](https://img.shields.io/badge/Qdrant-VectorDB-red?logo=qdrant)
![Ollama](https://img.shields.io/badge/Ollama-LocalLLM-black?logo=ollama)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 
Proyek ini dibangun untuk membantu **Safety Officer (HSE)** di perusahaan pertambangan agar dapat:

- Mencari informasi JSA secara cepat dan akurat
- Menjawab pertanyaan terkait bahaya, tindakan pengendalian, dan APD
- Mengakses dokumen JSA dalam format PDF maupun MDX
- Mendapatkan jawaban dalam **Bahasa Indonesia** yang terstruktur

Sistem ini menggabungkan **Vector Database (Qdrant)**, **Embedding Model (mxbai-embed-large)**, dan **LLM lokal (Llama 3)** sehingga data perusahaan tetap **privat** dan **tidak dikirim ke cloud**.

---

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                     DOKUMEN INPUT                           │
│   📄 PDF (JSA)  │  📝 MDX (Artikel HSE)                    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│              PDF PARSER (Multi-Method)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PyMuPDF    │  │ pdfplumber   │  │ Tesseract OCR    │  │
│  │ (teks biasa)│  │ (tabel JSA)  │  │ (PDF scan)       │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│         SMART CHUNKING (1200 char + overlap 300)            │
│         Break di akhir kalimat/paragraf                     │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│     Ollama Embedding (mxbai-embed-large, 1024 dim)          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│              🗄️ QDRANT VECTOR DATABASE                       │
│              Collection: "jsample"                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼ (Saat user bertanya)
┌─────────────────────────────────────────────────────────────┐
│   Query Expansion + Semantic Search (top-8 chunks)          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│   LLM Llama 3 + Prompt Terstruktur (Bahasa Indonesia)       │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
         JAWABAN
```

---

## Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| **Multi-Format Parser** | Mendukung file `.mdx` (dengan YAML frontmatter) dan `.pdf` |
| **Smart PDF Extraction** | Otomatis memilih metode terbaik: PyMuPDF, pdfplumber, atau OCR |
| **Tabel JSA Aware** | `pdfplumber` mengekstrak tabel JSA dengan struktur yang terjaga |
| **Query Expansion** | Memperkaya query user dengan kata kunci domain HSE |
| **Smart Chunking** | Memotong teks di akhir kalimat/paragraf, bukan di tengah kata |
| **Bahasa Indonesia** | Prompt dirancang agar LLM selalu menjawab dalam Bahasa Indonesia |
| **Structured Answer** | Jawaban terformat: Tahap → Bahaya → Tindakan → APD |
| **Auto-Recovery** | Collection otomatis dibuat ulang setelah di-reset |
| **Error Handling** | Graceful fallback untuk chunk yang gagal di-embed |

---

## 📋 Prasyarat

Sebelum memulai, pastikan Anda sudah menginstal:

| Software | Versi Minimum | Link |
|----------|---------------|------|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) |
| **uv** (Package Manager) | Terbaru | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| **Docker Desktop** | Terbaru | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Ollama** | Terbaru | [ollama.com](https://ollama.com/) |
| **Tesseract OCR** *(opsional, untuk PDF scan)* | 5.x | [UB-Mannheim/wiki](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Poppler** *(opsional, untuk OCR)* | Terbaru | [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) |

---

## Instalasi

### 1️⃣ Clone / Siapkan Folder Proyek

```powershell
mkdir C:\Users\advan\Documents\RAG
cd C:\Users\advan\Documents\RAG
```

### 2️⃣ Inisialisasi Proyek dengan `uv`

```powershell
uv init
uv venv
.\.venv\Scripts\Activate.ps1
```

### 3️⃣ Install Dependensi Python

```powershell
uv pip install pymupdf pdfplumber pytesseract pdf2image Pillow requests qdrant-client pyyaml
```

### 4️⃣ Install Model Ollama

Buka terminal baru dan jalankan:

```powershell
ollama pull llama3
ollama pull mxbai-embed-large
```

### 5️⃣ Jalankan Qdrant dengan Docker

```powershell
docker run -d -p 6333:6333 -p 6334:6334 ^
  -v qdrant_storage:/qdrant/storage ^
  --name qdrant ^
  qdrant/qdrant
```

Verifikasi Qdrant berjalan:
```powershell
curl http://localhost:6333
```

### 6️⃣ (Opsional) Instal Tesseract OCR untuk PDF Scan

Jika Anda memiliki dokumen JSA hasil scan (gambar), instal Tesseract:

1. Download installer dari [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Instal dengan opsi **bahasa Indonesia** (`ind`)
3. Tambahkan ke PATH: `C:\Program Files\Tesseract-OCR`
4. Instal bahasa Indonesia:
   ```powershell
   # Download ind.traineddata ke folder tessdata
   ```

---

## 📁 Struktur Proyek

```
RAG/
├── .venv/                  # Virtual environment
├── articles/               # 📂 Folder dokumen input
│   ├── 00-INDEX-jsa-pertambangan.mdx
│   ├── 01-jsa-pengeboran-drilling.mdx
│   ├── ...
│   ├── Jsa-coal-hauling.pdf
│   ├── jsa-dumping.pdf
│   ├── jsa-membuat-parit-di-tambang.pdf
│   ├── jsa-melakukan-peledakan-ulang.pdf
│   └── jsa-mengevakuasi-unit-amblas.pdf
├── main.py                 # 🎯 Entry point aplikasi
├── pdf_parser.py           # 📄 Parser PDF multi-method
├── pyproject.toml          # Konfigurasi uv
└── README.md               # 📘 Dokumentasi ini
```

---

## 💻 Cara Menjalankan

### Step 1: Pastikan Layanan Berjalan

**Terminal 1** — Qdrant:
```powershell
docker start qdrant
```

**Terminal 2** — Ollama:
```powershell
ollama serve
```

### Step 2: Jalankan Aplikasi

```powershell
cd C:\Users\advan\Documents\RAG
.\.venv\Scripts\Activate.ps1
uv run main.py
```

### Step 3: Gunakan Menu

```
==================================================
📋 MENU APLIKASI RAG HSE
==================================================
1. Ingest Articles (MDX & PDF)
2. Reset Collection (Hapus semua data)
3. Ask Question
4. Exit
```

---

## 🎮 Panduan Penggunaan

### 🔄 Pertama Kali Menggunakan

1. Pilih **Menu 1** → Ingest semua dokumen
2. Tunggu hingga semua file selesai diproses
3. Pilih **Menu 3** untuk mulai bertanya

### 🧹 Reset Database

Jika ingin memulai dari awal:
1. Pilih **Menu 2** → Ketik `y`
2. Pilih **Menu 1** → Ingest ulang

### ❓ Contoh Pertanyaan

| Pertanyaan | Sumber Jawaban |
|------------|----------------|
| *"Apa APD wajib untuk pekerjaan membuat parit?"* | `jsa-membuat-parit-di-tambang.pdf` |
| *"Bagaimana tindakan pengendalian saat unit mundur ke dumping point?"* | `jsa-dumping.pdf` |
| *"Sebutkan prosedur menangani peledakan mangkir"* | `jsa-melakukan-peledakan-ulang.pdf` |
| *"Apa saja bahaya saat loading pada coal hauling?"* | `Jsa-coal-hauling.pdf` |
| *"Bagaimana prosedur mengevakuasi unit amblas?"* | `jsa-mengevakuasi-unit-amblas.pdf` |

---

## 🔧 Troubleshooting

### Error: `Collection doesn't exist`
**Solusi:** Program sekarang otomatis membuat collection. Jika masih error, pilih Menu 2 lalu Menu 1.

### Error: `500 Server Error` saat embedding
**Penyebab:** Chunk terlalu panjang untuk model embedding.
**Solusi:** Sudah diatasi dengan `chunk_size=1200`. Jika masih error, turunkan ke `1000` di `main.py`.

### Error: `Tesseract is not installed`
**Solusi:** Instal Tesseract OCR dan tambahkan ke PATH. Atau abaikan jika tidak butuh OCR.

### Jawaban LLM dalam Bahasa Inggris
**Solusi:** Prompt sudah diperkuat. Jika masih terjadi, pertimbangkan ganti model ke `qwen2.5:7b` yang lebih baik di bahasa Indonesia:
```powershell
ollama pull qwen2.5:7b
```
Lalu ubah di `main.py`:
```python
"model": "qwen2.5:7b"
```

### Jawaban tidak akurat untuk pertanyaan JSA
**Penyebab:** Tabel JSA terpotong saat chunking.
**Solusi:** Gunakan model embedding multilingual:
```powershell
ollama pull nomic-embed-text
```
Lalu ubah di `main.py`:
- `size=1024` → `size=768`
- `"model": "mxbai-embed-large"` → `"model": "nomic-embed-text"`

---

## 💡 Tips Optimasi

### 📈 Meningkatkan Akurasi

1. **Gunakan model embedding multilingual** (`nomic-embed-text`) untuk dokumen berbahasa Indonesia
2. **Gunakan LLM yang lebih baik di bahasa Indonesia** (`qwen2.5:7b` atau `qwen2.5:14b`)
3. **Perkaya dokumen** dengan metadata YAML pada file MDX
4. **Tambahkan kata kunci domain** di fungsi `expand_query()` sesuai kebutuhan

### ⚡ Meningkatkan Kecepatan

1. Turunkan `limit` di fungsi `search()` dari 8 menjadi 5
2. Gunakan model LLM lebih kecil (`llama3:8b` → `phi3:mini`)
3. Kurangi `chunk_size` agar lebih banyak chunk paralel

### 📊 Monitoring Qdrant

Akses dashboard Qdrant di browser:
```
http://localhost:6334/dashboard
```

---

## 📚 Teknologi yang Digunakan

| Komponen | Teknologi | Fungsi |
|----------|-----------|--------|
| **Vector DB** | [Qdrant](https://qdrant.tech/) | Menyimpan & mencari vektor embedding |
| **Embedding** | [mxbai-embed-large](https://ollama.com/library/mxbai-embed-large) | Mengubah teks menjadi vektor |
| **LLM** | [Llama 3](https://llama.meta.com/) | Menghasilkan jawaban dari konteks |
| **PDF Parser** | PyMuPDF, pdfplumber, Tesseract | Ekstrak teks dari PDF |
| **Orchestrator** | Python + `requests` | Menghubungkan semua komponen |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) | Manajemen dependensi cepat |

---

## 📝 Format Dokumen yang Didukung

### 📄 PDF
- ✅ PDF berbasis teks (PyMuPDF)
- ✅ PDF dengan tabel kompleks (pdfplumber)
- ✅ PDF hasil scan/gambar (Tesseract OCR)

### 📝 MDX (Markdown + YAML)
```markdown
---
title: Judul Dokumen
author: Nama Author
date: 2026-06-19
tags: [HSE, JSA, Tambang]
---

Konten artikel di sini...
```

---

## 🤝 Kontribusi

Proyek ini bersifat open. Silakan fork, modifikasi, dan sesuaikan dengan kebutuhan perusahaan Anda.

---

## 📄 Lisensi

MIT License - Bebas digunakan untuk keperluan internal perusahaan.

---

## 👨‍💻 Author

Dibangun untuk mendukung **Safety Officer** pertambangan Indonesia dalam mengelola dan mengakses dokumen JSA dengan cepat dan akurat.

**Selamat bekerja dengan aman! 🦺⛑️**
