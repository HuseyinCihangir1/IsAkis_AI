# FlowAgent: Yerel LLM Destekli Doküman İşleme & Onay Akış Sistemi

Kurumsal satın alma taleplerini (PDF, taranmış faturalar, resimler veya serbest metinler) yerel bilgisayarınızda çalışan **Ollama (qwen3.5:0.8b)** modeli ile işleyen, bütçe denetimini gerçekleştiren ve insan onayına (Human-in-the-Loop) sunan uçtan uca akıllı iş akışı platformu.

---

## 🌟 Öne Çıkan Özellikler & Teknolojiler

- **Yerel LLM (Ollama - qwen3.5:0.8b):** Hiçbir dış bulut servisi veya OpenAI API anahtarı gerektirmeden, tamamen yerel makinede (`http://localhost:11434`) çalışan yapısal veri çıkarımı ve karar mekanizması.
- **OCR (Optical Character Recognition):** Dijital PDF'ler, taranmış faturalar ve görsellerden (`PNG`, `JPG`) `pdfplumber`, `pytesseract` ve `pdf2image` ile metin okuma.
- **Yerel Tool Calling (API Entegrasyonu):** Modelin ihtiyaca göre ERP tedarikçi doğrulama ve departman bütçe sorgulama araçlarını yönlendirip çağırması.
- **Yerel RAG (ChromaDB):** Şirket prosedür kurallarının ChromaDB vektör veritabanına indekslenmesi ve yerel Qwen modeliyle bütçe limit denetimi yapılması.
- **İzlenebilir Görev Akışı (Workflow Timeline):** OCR -> Qwen Parsing -> Tool Calling -> RAG adımlarını milisaniye hassasiyetinde takip eden görsel süreç zaman çizelgesi.
- **İnsan Onayı (Human-in-the-Loop):** Yöneticinin talebi inceleyip **Onayla / Reddet** kararı vermesi.
- **Kalıcı SQLite Veritabanı:** Tüm talepler, kalemler ve onay geçmişi yerleşik `flowagent.db` veritabanında saklanır.

---

## 📁 Proje Dizin Yapısı

```text
IsAkis_AI_Project/
├── app.py                # Streamlit tabanlı kullanıcı ve insan-onay arayüzü
├── utils.py              # Yerel Ollama (Qwen), OCR, Tool Calling, RAG ve Workflow motoru
├── database.py           # SQLite bağlantı, tablo oluşturma ve CRUD fonksiyonları
├── prosedurler.txt       # Şirket satın alma prosedürleri ve kategori limitleri
├── requirements.txt      # Gerekli Python kütüphaneleri
├── test_ollama.py        # Yerel Ollama entegrasyon doğrulama testi
└── flowagent.db          # SQLite veritabanı dosyası (otomatik oluşturulur)
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Ollama'da Modeli Başlatın
Terminalinizde:
```bash
ollama run qwen3.5:0.8b
```

### 2. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatın
```bash
streamlit run app.py
```
