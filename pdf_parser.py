import fitz  # PyMuPDF
import pdfplumber
from pathlib import Path
import os
import re

# =====================================================
# FUNGSI UTAMA: DETEKSI & EKSTRAK PDF
# =====================================================

def extract_pdf_content(file_path):
    """
    Fungsi utama untuk mengekstrak teks dari PDF berbagai jenis.
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")
    
    # 1. Coba dengan PyMuPDF dulu (paling cepat)
    text_pymupdf, metadata = _extract_with_pymupdf(file_path)
    
    # Cek apakah teks yang dihasilkan cukup bermakna
    meaningful_chars = sum(1 for c in text_pymupdf if c.isalnum() or c.isspace())
    text_ratio = meaningful_chars / max(len(text_pymupdf), 1)
    
    # Jika rasio karakter bermakna < 30%, kemungkinan besar PDF scan
    if len(text_pymupdf.strip()) < 100 or text_ratio < 0.3:
        print(f"  → PDF terdeteksi sebagai SCAN/GAMBAR. Menggunakan OCR...")
        text_ocr = _extract_with_ocr(file_path)
        if len(text_ocr.strip()) > len(text_pymupdf.strip()):
            return metadata, text_ocr
    
    # 2. Coba dengan pdfplumber (lebih baik untuk tabel)
    # PERBAIKAN: Unpack tuple menjadi text_plumber dan _ (abaikan metadata kosong)
    text_plumber, _ = _extract_with_pdfplumber(file_path)
    
    # Pilih teks yang lebih panjang/lebih banyak informasinya
    if len(text_plumber.strip()) > len(text_pymupdf.strip()) * 1.2:
        return metadata, text_plumber
    
    return metadata, text_pymupdf


# =====================================================
# METHOD 1: PyMuPDF (Cepat, untuk PDF teks biasa)
# =====================================================

def _extract_with_pymupdf(file_path):
    """Ekstrak teks menggunakan PyMuPDF (fitz)."""
    doc = fitz.open(file_path)
    
    raw_metadata = doc.metadata or {}
    metadata = {k: str(v) for k, v in raw_metadata.items() if v}
    metadata["page_count"] = str(len(doc))
    
    text_parts = []
    for page_num, page in enumerate(doc, 1):
        page_text = page.get_text("text")
        if page_text.strip():
            text_parts.append(f"[Halaman {page_num}]\n{page_text.strip()}")
    
    doc.close()
    return "\n\n".join(text_parts), metadata


# =====================================================
# METHOD 2: pdfplumber (Lebih baik untuk tabel)
# =====================================================

def _extract_with_pdfplumber(file_path):
    """Ekstrak teks dengan fokus pada tabel menggunakan pdfplumber."""
    text_parts = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = []
                
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                                page_text.append(" | ".join(filter(None, cleaned_row)))
                
                plain_text = page.extract_text()
                if plain_text:
                    page_text.append(plain_text)
                
                if page_text:
                    unique_text = []
                    seen = set()
                    for line in page_text:
                        if line not in seen:
                            seen.add(line)
                            unique_text.append(line)
                    
                    text_parts.append(f"[Halaman {page_num}]\n" + "\n".join(unique_text))
    
    except Exception as e:
        print(f"  ⚠️ pdfplumber gagal: {e}")
        return "", {}
    
    return "\n\n".join(text_parts), {}


# =====================================================
# METHOD 3: OCR dengan Tesseract (Untuk PDF scan)
# =====================================================

def _extract_with_ocr(file_path):
    """Ekstrak teks dari PDF scan menggunakan OCR (Tesseract)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as e:
        print(f"  ⚠️ Library OCR tidak tersedia: {e}")
        return ""
    
    text_parts = []
    
    try:
        print("  → Mengkonversi PDF ke gambar (ini mungkin memakan waktu)...")
        images = convert_from_path(str(file_path), dpi=200)
        
        for page_num, image in enumerate(images, 1):
            try:
                page_text = pytesseract.image_to_string(image, lang='ind+eng')
            except Exception:
                page_text = pytesseract.image_to_string(image, lang='eng')
            
            if page_text.strip():
                text_parts.append(f"[Halaman {page_num}]\n{page_text.strip()}")
    
    except Exception as e:
        print(f"  ⚠️ OCR gagal: {e}")
        return ""
    
    return "\n\n".join(text_parts)


# =====================================================
# FUNGSI PEMBANTU: CLEANING TEKS
# =====================================================

def clean_extracted_text(text):
    """Membersihkan teks hasil ekstraksi agar lebih rapi."""
    # Hapus baris kosong berlebih
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Hapus spasi berlebih di akhir baris
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    
    # Normalisasi spasi
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()